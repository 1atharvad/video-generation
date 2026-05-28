import json
import os
import sys
import time
from pathlib import Path

import redis

from liveportrait.liveportrait import LivePortrait

WORKER_ID = os.environ.get("WORKER_ID", "0")
r = redis.Redis(host=os.environ.get("REDIS_HOST", "localhost"), decode_responses=True)

JOB_TTL_SECS = 60 * 60 * 24  # 24 hours


def _cleanup_uploads(job: dict) -> None:
    for key in ("face_image_path", "audio_path", "driving_video_path"):
        val = job.get(key, "")
        if val:
            Path(val).unlink(missing_ok=True)


def main():
    print(f"[Worker {WORKER_ID}] Loading models...")
    lp = LivePortrait()
    print(f"[Worker {WORKER_ID}] Ready — waiting for jobs")

    while True:
        try:
            item = r.blpop(["video_jobs", "animate_jobs"], timeout=0)
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            print(f"[Worker {WORKER_ID}] Redis connection error: {e} — retrying in 5s")
            time.sleep(5)
            continue
        if not item:
            continue
        _, raw = item

        try:
            job = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[Worker {WORKER_ID}] Malformed job payload, skipping: {e}")
            continue

        job_id = job.get("job_id", "unknown")
        print(f"[Worker {WORKER_ID}] Processing {job_id} (type={job.get('type', 'generate')})")
        r.set(f"job:{job_id}:status", "processing", ex=JOB_TTL_SECS)

        try:
            if job.get("type") == "animate":
                result = lp.animate(
                    source_image=job["face_image_path"],
                    driving_video=job["driving_video_path"],
                    output=job["output_path"],
                    **job["params"],
                )
            else:
                result = lp.run(
                    source_image=job["face_image_path"],
                    audio=job["audio_path"],
                    output=job["output_path"],
                    **job["params"],
                )
            if result["status"] == "completed":
                r.set(f"job:{job_id}:status", "completed", ex=JOB_TTL_SECS)
                r.set(f"job:{job_id}:output", result["output_path"], ex=JOB_TTL_SECS)
                print(f"[Worker {WORKER_ID}] Done {job_id}")
            else:
                r.set(f"job:{job_id}:status", "failed", ex=JOB_TTL_SECS)
                r.set(f"job:{job_id}:error", result.get("error", "unknown"), ex=JOB_TTL_SECS)
                print(f"[Worker {WORKER_ID}] Failed {job_id}: {result.get('error')}")
        except Exception as e:
            r.set(f"job:{job_id}:status", "failed", ex=JOB_TTL_SECS)
            r.set(f"job:{job_id}:error", str(e), ex=JOB_TTL_SECS)
            print(f"[Worker {WORKER_ID}] Exception {job_id}: {e}")
        finally:
            _cleanup_uploads(job)


if __name__ == "__main__":
    main()
