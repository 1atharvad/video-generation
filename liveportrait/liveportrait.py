import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning)

try:
    from .config import DRIVING_VIDEOS_DIR
    from .setup import setup_all
    from .steps import make_seamless_loop, run_lipsync, run_liveportrait, trim_pkl
except ImportError:
    import sys
    from pathlib import Path as _P
    sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
    from liveportrait.config import DRIVING_VIDEOS_DIR
    from liveportrait.setup import setup_all
    from liveportrait.steps import make_seamless_loop, run_lipsync, run_liveportrait, trim_pkl


class LivePortrait:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            setup_all()
        return cls._instance

    def __init__(self, pads: tuple[int, int, int, int] = (0, 10, 0, 0)):
        self.pads = pads

    def run(
        self,
        source_image: str | Path,
        audio: str | Path,
        output: str | Path,
        driving_video: str | Path | None = None,
        driving_max_secs: float | None = 5.0,
        enhance: bool = True,
        face_restore: bool = True,
        face_restore_step: int = 1,
        nosmooth: bool = False,
        expression_multiplier: float = 1.0,
        flag_pasteback: bool = True,
        resize_factor: int = 1,
        animation_region: str = "pose_eyes",
        smooth_observation_variance: float = 1e-4,
    ) -> dict:
        source_image = Path(source_image)
        audio = Path(audio)
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)

        if not source_image.exists():
            return {"status": "failed", "error": f"Source image not found: {source_image}"}
        if not audio.exists():
            return {"status": "failed", "error": f"Audio file not found: {audio}"}

        import time

        if driving_video is None:
            pkl_candidates = list(DRIVING_VIDEOS_DIR.glob("*.pkl"))
            mp4_candidates = list(DRIVING_VIDEOS_DIR.glob("*.mp4"))
            if pkl_candidates:
                driving_video = pkl_candidates[0]
                print(f"Using driving template (pkl): {driving_video.name}")
            elif mp4_candidates:
                driving_video = mp4_candidates[0]
                print(f"Using driving video: {driving_video.name}")
            else:
                return {
                    "status": "failed",
                    "error": f"No driving video/template found in {DRIVING_VIDEOS_DIR}. Add a .mp4 or .pkl file there.",
                }
        else:
            driving_video = Path(driving_video)
            if not driving_video.exists():
                return {"status": "failed", "error": f"Driving video not found: {driving_video}"}

        if driving_max_secs is not None and driving_video.suffix == ".pkl":
            driving_video = trim_pkl(driving_video, driving_max_secs)

        timings: dict[str, float] = {}

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            animated_path = Path(f.name)

        # Step 1: LivePortrait — adds natural head/eye motion
        print("Step 1/3: Running LivePortrait...")
        t0 = time.time()
        lp_result = run_liveportrait(
            source_image=source_image,
            driving_video=driving_video,
            output=animated_path,
            expression_multiplier=expression_multiplier,
            flag_pasteback=flag_pasteback,
            animation_region=animation_region,
            smooth_observation_variance=smooth_observation_variance,
        )
        timings["liveportrait"] = time.time() - t0
        if lp_result["status"] == "failed":
            animated_path.unlink(missing_ok=True)
            return lp_result
        print(f"  LivePortrait done in {timings['liveportrait']:.0f}s")

        # Step 2: ping-pong loop animated clip to cover full audio duration
        print("Step 2/3: Building seamless loop...")
        t0 = time.time()
        looped_path = animated_path.with_suffix("._loop.mp4")
        looped = make_seamless_loop(animated_path, audio, looped_path)
        face_for_lipsync = looped if looped == looped_path else animated_path
        timings["loop"] = time.time() - t0

        # Step 3: Wav2Lip — syncs lips to audio
        print("Step 3/3: Running Wav2Lip...")
        t0 = time.time()
        ls_result = run_lipsync(
            face=face_for_lipsync,
            audio=audio,
            output=output,
            enhance=enhance,
            pads=self.pads,
            face_restore=face_restore,
            face_restore_step=face_restore_step,
            nosmooth=nosmooth,
            resize_factor=resize_factor,
        )
        timings["wav2lip"] = time.time() - t0
        timings["enhancement"] = ls_result.get("enhancement_time", 0.0)
        print(f"  Wav2Lip done in {timings['wav2lip']:.0f}s (enhancement: {timings['enhancement']:.0f}s)")

        animated_path.unlink(missing_ok=True)
        looped_path.unlink(missing_ok=True)

        if ls_result["status"] == "failed":
            return ls_result

        return {"status": "completed", "output_path": str(output), "timings": timings}


if __name__ == "__main__":
    import sys
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

    import time
    from liveportrait.config import BASE_DIR, AUDIO_DIR, DRIVING_VIDEOS_DIR as _DRV
    from liveportrait.liveportrait import LivePortrait as _LP

    FACE_IMAGE = _Path(BASE_DIR, "n8n_files", "test_face.jpg")
    AUDIO_FILE = _Path(AUDIO_DIR, "60f04df5-45b5-4849-b8c3-c5d858c3ec24.wav")
    OUTPUT_FILE = _Path(BASE_DIR, "n8n_files", "test_output_v4.mp4")

    print(f"Face   : {FACE_IMAGE}")
    print(f"Audio  : {AUDIO_FILE}")
    print(f"Output : {OUTPUT_FILE}\n")

    lp = _LP()
    start = time.time()
    result = lp.run(
        source_image=FACE_IMAGE,
        audio=AUDIO_FILE,
        output=OUTPUT_FILE,
        driving_video=_Path(_DRV, "d18.mp4"),
        driving_max_secs=5.0,
        resize_factor=1,
        face_restore=True,
        face_restore_step=3,
        expression_multiplier=0.7,
        smooth_observation_variance=3e-4,
    )
    elapsed = time.time() - start

    if result["status"] == "completed":
        mins, secs = divmod(int(elapsed), 60)
        print(f"\nDone! Video saved to: {result['output_path']}")
        print(f"Total: {mins}m {secs}s")
        t = result.get("timings", {})
        if t:
            print(f"  LivePortrait : {t.get('liveportrait', 0):.0f}s")
            print(f"  Loop build   : {t.get('loop', 0):.0f}s")
            print(f"  Wav2Lip      : {t.get('wav2lip', 0):.0f}s")
            print(f"  Enhancement  : {t.get('enhancement', 0):.0f}s")
    else:
        print(f"\nFailed: {result['error']}")
        if "stderr" in result:
            print("\n--- stderr ---")
            print(result["stderr"])
        sys.exit(1)
