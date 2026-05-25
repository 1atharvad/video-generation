import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def generate_video(
    face_image: str | Path,
    audio: str | Path,
    output: str | Path,
    company: str,
    location: str,
    position: str,
    experience: str,
    skills: list[str],
    logo: str | Path | None = None,
    driving_max_secs: float = 5.0,
    face_restore: bool = True,
    face_restore_step: int = 3,
    expression_multiplier: float = 0.7,
    smooth_observation_variance: float = 3e-4,
) -> dict:
    from liveportrait.liveportrait import LivePortrait
    from video_creator.creator import create_video_with_text

    face_image = Path(face_image)
    audio      = Path(audio)
    output     = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    talking_head = output.with_suffix("._talking_head.mp4")

    print("=" * 60)
    print("Step 1/2 — LivePortrait + Wav2Lip")
    print("=" * 60)
    t0 = time.time()
    lp = LivePortrait()
    lp_result = lp.run(
        source_image              = face_image,
        audio                     = audio,
        output                    = talking_head,
        driving_max_secs          = driving_max_secs,
        face_restore              = face_restore,
        face_restore_step         = face_restore_step,
        expression_multiplier     = expression_multiplier,
        smooth_observation_variance = smooth_observation_variance,
    )
    if lp_result["status"] != "completed":
        return lp_result

    t = lp_result.get("timings", {})
    print(f"\nTalking head done in {time.time() - t0:.0f}s")
    if t:
        print(f"  LivePortrait : {t.get('liveportrait', 0):.0f}s")
        print(f"  Loop build   : {t.get('loop', 0):.0f}s")
        print(f"  Wav2Lip      : {t.get('wav2lip', 0):.0f}s")
        print(f"  Enhancement  : {t.get('enhancement', 0):.0f}s")

    print()
    print("=" * 60)
    print("Step 2/2 — Video Creator")
    print("=" * 60)
    vc_result = create_video_with_text(
        video_path  = talking_head,
        output_path = output,
        company     = company,
        location    = location,
        position    = position,
        experience  = experience,
        skills      = skills,
        logo_path   = Path(logo) if logo else None,
    )

    talking_head.unlink(missing_ok=True)

    if vc_result["status"] != "completed":
        return vc_result

    return {
        "status":      "completed",
        "output_path": vc_result["output_path"],
        "timings": {
            **t,
            **vc_result.get("timings", {}),
        },
    }


if __name__ == "__main__":
    result = generate_video(
        face_image  = BASE_DIR / "assets" / "test_face.jpg",
        audio       = BASE_DIR / "assets" / "60f04df5-45b5-4849-b8c3-c5d858c3ec24.wav",
        output      = BASE_DIR / "assets" / "final_output.mp4",
        logo        = BASE_DIR / "assets" / "company_logo.png",
        company     = "Sundayy",
        location    = "United States",
        position    = "Software Engineer (JS, TypeScript)",
        experience  = "Not specified",
        skills      = ["JavaScript", "TypeScript", "Software Development"],
    )

    if result["status"] == "completed":
        print(f"\nDone! Final video: {result['output_path']}")
    else:
        print(f"\nFailed: {result['error']}")
        if "stderr" in result:
            print(result["stderr"])
        sys.exit(1)
