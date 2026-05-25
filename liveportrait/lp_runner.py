import shutil
import sys
import tempfile
import threading
from pathlib import Path

import torch

from .config import LP_REPO_DIR

_pipeline = None
_lock = threading.Lock()


def _get_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _ensure_path():
    lp_root = str(LP_REPO_DIR)
    if lp_root not in sys.path:
        sys.path.insert(0, lp_root)


def _get_pipeline():
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    _ensure_path()
    from src.config.inference_config import InferenceConfig
    from src.config.crop_config import CropConfig
    from src.live_portrait_pipeline import LivePortraitPipeline

    device = _get_device()
    print(f"LivePortrait using device: {device}")

    # Try passing device_id as constructor arg; fall back to setting it after
    try:
        inf_cfg = InferenceConfig(device_id=device)
    except TypeError:
        inf_cfg = InferenceConfig()
        inf_cfg.device_id = device

    _pipeline = LivePortraitPipeline(
        inference_cfg=inf_cfg,
        crop_cfg=CropConfig(),
    )
    return _pipeline


def run_liveportrait(
    source_image: Path,
    driving_video: Path,
    output: Path,
    expression_multiplier: float,
    flag_pasteback: bool,
    animation_region: str = "pose_eyes",
    smooth_observation_variance: float = 3e-4,
) -> dict:
    _ensure_path()
    from src.config.argument_config import ArgumentConfig

    with _lock:
        pipeline = _get_pipeline()
        inf_cfg = pipeline.live_portrait_wrapper.inference_cfg
        inf_cfg.driving_multiplier = expression_multiplier
        inf_cfg.flag_pasteback = flag_pasteback
        inf_cfg.animation_region = animation_region
        inf_cfg.driving_smooth_observation_variance = smooth_observation_variance

        with tempfile.TemporaryDirectory() as tmp_dir:
            args = ArgumentConfig(
                source=str(source_image),
                driving=str(driving_video),
                output_dir=tmp_dir,
            )
            try:
                pipeline.execute(args)
            except Exception as e:
                return {"status": "failed", "error": str(e)}

            videos = list(Path(tmp_dir).glob("*.mp4"))
            plain = [v for v in videos if not v.name.endswith("_concat.mp4")]
            chosen = plain[0] if plain else (videos[0] if videos else None)

            if not chosen:
                return {"status": "failed", "error": "LivePortrait produced no output"}

            shutil.move(str(chosen), str(output))

    return {"status": "completed"}
