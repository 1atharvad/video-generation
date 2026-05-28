import json
import os
import shutil
import uuid
from pathlib import Path

import redis
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

app = FastAPI()
r = redis.Redis(host=os.environ.get("REDIS_HOST", "localhost"), decode_responses=True)

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

JOB_TTL_SECS = 60 * 60 * 24  # 24 hours
MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB

_ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png"}
_ALLOWED_AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac"}
_ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv"}


def _validate_job_id(job_id: str) -> None:
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(400, "Invalid job_id")


async def _save_upload(upload: UploadFile, dest: Path) -> None:
    total = 0
    with dest.open("wb") as f:
        while chunk := await upload.read(1024 * 256):
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"Upload exceeds {MAX_UPLOAD_BYTES // 1024 // 1024} MB limit")
            f.write(chunk)


@app.post("/generate")
async def generate(
    face_image: UploadFile = File(...),
    audio: UploadFile = File(...),
    driving_max_secs: float = Query(default=5.0, gt=0, le=60),
    face_restore: bool = True,
    face_restore_step: int = Query(default=3, ge=1, le=10),
    expression_multiplier: float = Query(default=0.7, gt=0, le=3.0),
    smooth_observation_variance: float = Query(default=3e-4, gt=0),
):
    face_suffix = Path(face_image.filename or "face.jpg").suffix.lower() or ".jpg"
    if face_suffix not in _ALLOWED_IMAGE_EXT:
        raise HTTPException(400, f"face_image must be one of {sorted(_ALLOWED_IMAGE_EXT)}")

    audio_suffix = Path(audio.filename or "audio.wav").suffix.lower() or ".wav"
    if audio_suffix not in _ALLOWED_AUDIO_EXT:
        raise HTTPException(400, f"audio must be one of {sorted(_ALLOWED_AUDIO_EXT)}")

    job_id = str(uuid.uuid4())
    face_path   = UPLOAD_DIR / f"{job_id}_face{face_suffix}"
    audio_path  = UPLOAD_DIR / f"{job_id}_audio{audio_suffix}"
    output_path = OUTPUT_DIR / f"{job_id}.mp4"

    await _save_upload(face_image, face_path)
    await _save_upload(audio, audio_path)

    job = {
        "job_id": job_id,
        "face_image_path": str(face_path),
        "audio_path": str(audio_path),
        "output_path": str(output_path),
        "params": {
            "driving_max_secs": driving_max_secs,
            "face_restore": face_restore,
            "face_restore_step": face_restore_step,
            "expression_multiplier": expression_multiplier,
            "smooth_observation_variance": smooth_observation_variance,
        },
    }

    r.set(f"job:{job_id}:status", "queued", ex=JOB_TTL_SECS)
    r.rpush("video_jobs", json.dumps(job))

    return {"job_id": job_id, "status": "queued"}


@app.post("/animate")
async def animate(
    face_image: UploadFile = File(...),
    driving_video: UploadFile = File(...),
    expression_multiplier: float = Query(default=1.0, gt=0, le=3.0),
    smooth_observation_variance: float = Query(default=1e-4, gt=0),
    animation_region: str = Query(default="all"),
):
    face_suffix = Path(face_image.filename or "face.jpg").suffix.lower() or ".jpg"
    if face_suffix not in _ALLOWED_IMAGE_EXT:
        raise HTTPException(400, f"face_image must be one of {sorted(_ALLOWED_IMAGE_EXT)}")

    video_suffix = Path(driving_video.filename or "driving.mp4").suffix.lower() or ".mp4"
    if video_suffix not in _ALLOWED_VIDEO_EXT:
        raise HTTPException(400, f"driving_video must be one of {sorted(_ALLOWED_VIDEO_EXT)}")

    job_id = str(uuid.uuid4())
    face_path   = UPLOAD_DIR / f"{job_id}_face{face_suffix}"
    video_path  = UPLOAD_DIR / f"{job_id}_driving{video_suffix}"
    output_path = OUTPUT_DIR / f"{job_id}.mp4"

    await _save_upload(face_image, face_path)
    await _save_upload(driving_video, video_path)

    job = {
        "job_id": job_id,
        "type": "animate",
        "face_image_path": str(face_path),
        "driving_video_path": str(video_path),
        "output_path": str(output_path),
        "params": {
            "expression_multiplier": expression_multiplier,
            "smooth_observation_variance": smooth_observation_variance,
            "animation_region": animation_region,
        },
    }

    r.set(f"job:{job_id}:status", "queued", ex=JOB_TTL_SECS)
    r.rpush("animate_jobs", json.dumps(job))

    return {"job_id": job_id, "status": "queued"}


@app.get("/status/{job_id}")
def status(job_id: str):
    _validate_job_id(job_id)
    job_status = r.get(f"job:{job_id}:status")
    if not job_status:
        raise HTTPException(404, "Job not found")
    resp = {"job_id": job_id, "status": job_status}
    if job_status == "failed":
        resp["error"] = r.get(f"job:{job_id}:error")
    return resp


@app.get("/result/{job_id}")
def result(job_id: str):
    _validate_job_id(job_id)
    job_status = r.get(f"job:{job_id}:status")
    if not job_status:
        raise HTTPException(404, "Job not found")
    if job_status != "completed":
        raise HTTPException(400, f"Job not ready — status: {job_status}")
    raw_path = r.get(f"job:{job_id}:output")
    if not raw_path:
        raise HTTPException(500, "Output path missing from job record")
    output_path = Path(raw_path)
    if not output_path.exists():
        raise HTTPException(404, "Output file not found")
    return FileResponse(str(output_path), media_type="video/mp4", filename=f"{job_id}.mp4")
