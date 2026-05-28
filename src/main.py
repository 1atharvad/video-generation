import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

from liveportrait.liveportrait import LivePortrait


def animate_video(
    face_image: str | Path,
    driving_video: str | Path,
    output: str | Path,
    expression_multiplier: float = 1.0,
    smooth_observation_variance: float = 1e-4,
    animation_region: str = "all",
) -> dict:
    face_image    = Path(face_image)
    driving_video = Path(driving_video)
    output        = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("LivePortrait — live anchor mode")
    print("=" * 60)
    t0 = time.time()
    lp = LivePortrait()
    result = lp.animate(
        source_image                = face_image,
        driving_video               = driving_video,
        output                      = output,
        expression_multiplier       = expression_multiplier,
        smooth_observation_variance = smooth_observation_variance,
        animation_region            = animation_region,
    )

    t = result.get("timings", {})
    if t:
        print(f"\nDone in {time.time() - t0:.0f}s")
        print(f"  LivePortrait : {t.get('liveportrait', 0):.0f}s")
        print(f"  Audio merge  : {t.get('merge', 0):.0f}s")

    return result


def generate_video(
    face_image: str | Path,
    audio: str | Path,
    output: str | Path,
    driving_max_secs: float = 5.0,
    face_restore: bool = True,
    face_restore_step: int = 3,
    expression_multiplier: float = 0.7,
    smooth_observation_variance: float = 3e-4,
) -> dict:
    face_image = Path(face_image)
    audio      = Path(audio)
    output     = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("LivePortrait + Wav2Lip")
    print("=" * 60)
    t0 = time.time()
    lp = LivePortrait()
    lp_result = lp.run(
        source_image                = face_image,
        audio                       = audio,
        output                      = output,
        driving_max_secs            = driving_max_secs,
        face_restore                = face_restore,
        face_restore_step           = face_restore_step,
        expression_multiplier       = expression_multiplier,
        smooth_observation_variance = smooth_observation_variance,
    )

    t = lp_result.get("timings", {})
    if t:
        print(f"\nDone in {time.time() - t0:.0f}s")
        print(f"  LivePortrait : {t.get('liveportrait', 0):.0f}s")
        print(f"  Loop build   : {t.get('loop', 0):.0f}s")
        print(f"  Wav2Lip      : {t.get('wav2lip', 0):.0f}s")
        print(f"  Enhancement  : {t.get('enhancement', 0):.0f}s")

    return lp_result


if __name__ == "__main__":
    result = generate_video(
        face_image = BASE_DIR / "assets" / "test_face.jpg",
        audio      = BASE_DIR / "assets" / "audio.wav",
        output     = BASE_DIR / "assets" / "final_output.mp4",
    )

    if result["status"] == "completed":
        print(f"\nDone! Final video: {result['output_path']}")
    else:
        print(f"\nFailed: {result['error']}")
        if "stderr" in result:
            print(result["stderr"])
        sys.exit(1)
