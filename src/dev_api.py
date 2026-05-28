import asyncio
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from main import animate_video, generate_video

app = FastAPI()

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
_ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png"}
_ALLOWED_AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac"}
_ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv"}

_jobs: dict[str, dict] = {}
_queue: asyncio.Queue = asyncio.Queue()


async def _worker():
    loop = asyncio.get_event_loop()
    while True:
        job = await _queue.get()
        job_id = job["job_id"]
        _jobs[job_id]["status"] = "processing"
        try:
            if job.get("type") == "animate":
                fn = lambda: animate_video(
                    face_image=job["face_image_path"],
                    driving_video=job["driving_video_path"],
                    output=job["output_path"],
                    **job["params"],
                )
            else:
                fn = lambda: generate_video(
                    face_image=job["face_image_path"],
                    audio=job["audio_path"],
                    output=job["output_path"],
                    **job["params"],
                )
            result = await loop.run_in_executor(None, fn)
            if result["status"] == "completed":
                _jobs[job_id]["status"] = "completed"
                _jobs[job_id]["output"] = result["output_path"]
            else:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = result.get("error", "unknown")
        except Exception as e:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(e)
        finally:
            for key in ("face_image_path", "audio_path", "driving_video_path"):
                val = job.get(key, "")
                if val:
                    Path(val).unlink(missing_ok=True)
            _queue.task_done()


@app.on_event("startup")
async def startup():
    asyncio.create_task(_worker())


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
    face_path = UPLOAD_DIR / f"{job_id}_face{face_suffix}"
    audio_path = UPLOAD_DIR / f"{job_id}_audio{audio_suffix}"
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

    _jobs[job_id] = {"status": "queued"}
    await _queue.put(job)

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
    face_path  = UPLOAD_DIR / f"{job_id}_face{face_suffix}"
    video_path = UPLOAD_DIR / f"{job_id}_driving{video_suffix}"
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

    _jobs[job_id] = {"status": "queued"}
    await _queue.put(job)

    return {"job_id": job_id, "status": "queued"}


@app.get("/status/{job_id}")
def status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    resp = {"job_id": job_id, "status": job["status"]}
    if job["status"] == "failed":
        resp["error"] = job.get("error")
    return resp


@app.get("/result/{job_id}")
def result(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] != "completed":
        raise HTTPException(400, f"Job not ready — status: {job['status']}")
    output_path = Path(job["output"])
    if not output_path.exists():
        raise HTTPException(404, "Output file not found")
    return FileResponse(str(output_path), media_type="video/mp4", filename=f"{job_id}.mp4")
