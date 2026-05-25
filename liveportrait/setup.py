import re
import subprocess
import sys
import urllib.request
from pathlib import Path

from tqdm import tqdm

from .config import (
    LP_REPO_DIR, LP_REPO_URL,
    WAV2LIP_DIR, WAV2LIP_REPO_URL,
    CHECKPOINTS_DIR, CHECKPOINT_PATH, CHECKPOINT_HF_REPO, CHECKPOINT_HF_FILE,
    FACE_DET_DIR, FACE_DET_URL,
    GFPGAN_WEIGHTS_DIR, GFPGAN_MODEL_PATH, GFPGAN_MODEL_URL,
    DRIVING_VIDEOS_DIR,
)


def download_file(url: str, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    bar = tqdm(unit="B", unit_scale=True, unit_divisor=1024, desc=destination.name)

    def _progress(block_count, block_size, total_size):
        if bar.total is None and total_size > 0:
            bar.total = total_size
        bar.update(block_count * block_size - bar.n)

    try:
        urllib.request.urlretrieve(url, destination, reporthook=_progress)
        bar.close()
        print(f"Download complete: {destination}\n")
    except Exception as e:
        bar.close()
        print(f"Download error: {e}")


def clone_repo(url: str, dest: Path, name: str):
    if dest.exists():
        return
    print(f"Cloning {name}...")
    result = subprocess.run(
        ["git", "clone", url, str(dest)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Failed to clone {name}:\n{result.stderr}")
        sys.exit(1)
    print(f"Cloned {name} to {dest}\n")


def download_liveportrait_weights():
    weights_dir = Path(LP_REPO_DIR, "pretrained_weights")
    weights_dir.mkdir(parents=True, exist_ok=True)
    print("Downloading LivePortrait pretrained weights from HuggingFace (~1.5 GB)...")
    from huggingface_hub import snapshot_download
    snapshot_download(
        repo_id="KlingTeam/LivePortrait",
        local_dir=str(weights_dir),
        ignore_patterns=["*.git*", "README.md", "docs/*"],
    )
    print(f"Download complete: {weights_dir}\n")


def download_wav2lip_checkpoint():
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    print("Downloading wav2lip_gan.pth from HuggingFace (~700 MB)...")
    from huggingface_hub import hf_hub_download
    hf_hub_download(
        repo_id=CHECKPOINT_HF_REPO,
        filename=CHECKPOINT_HF_FILE,
        local_dir=str(CHECKPOINTS_DIR),
        local_dir_use_symlinks=False,
    )
    downloaded = Path(CHECKPOINTS_DIR, CHECKPOINT_HF_FILE)
    if downloaded != CHECKPOINT_PATH and downloaded.exists():
        downloaded.rename(CHECKPOINT_PATH)
    print(f"Download complete: {CHECKPOINT_PATH}\n")


def patch_liveportrait_for_pose_eyes():
    pipeline_py = Path(LP_REPO_DIR, "src", "live_portrait_pipeline.py")
    arg_cfg_py = Path(LP_REPO_DIR, "src", "config", "argument_config.py")
    inf_cfg_py = Path(LP_REPO_DIR, "src", "config", "inference_config.py")

    sentinel = '"pose_eyes"'
    text = pipeline_py.read_text(encoding="utf-8")
    if sentinel not in text:
        text = text.replace(
            '== "all" or inf_cfg.animation_region == "pose"',
            '== "all" or inf_cfg.animation_region == "pose" or inf_cfg.animation_region == "pose_eyes"',
        )
        text = text.replace(
            'animation_region == "eyes":',
            'animation_region in ("eyes", "pose_eyes"):',
        )
        pipeline_py.write_text(text, encoding="utf-8")
        print("Patched LivePortrait pipeline for pose_eyes support.")

    old_literal = 'Literal["exp", "pose", "lip", "eyes", "all"]'
    new_literal = 'Literal["exp", "pose", "lip", "eyes", "all", "pose_eyes"]'
    for cfg_py in (arg_cfg_py, inf_cfg_py):
        text = cfg_py.read_text(encoding="utf-8")
        if old_literal in text:
            cfg_py.write_text(text.replace(old_literal, new_literal), encoding="utf-8")


def patch_liveportrait_device():
    """Patch LivePortraitWrapper to use runtime device detection instead of hardcoded cuda."""
    wrapper_py = Path(LP_REPO_DIR, "src", "live_portrait_wrapper.py")
    if not wrapper_py.exists():
        return

    text = wrapper_py.read_text(encoding="utf-8")
    sentinel = "# device-patch"
    if sentinel in text:
        return

    patched = text

    # Variant A: f-string / string-concat torch.device(...) call
    device_expr = (
        'torch.device("cuda" if torch.cuda.is_available() else '
        '("mps" if hasattr(torch.backends, "mps") and torch.backends.mps.is_available() else "cpu"))'
        f'  {sentinel}'
    )
    for pat in [
        'torch.device(f"cuda:{inference_cfg.device_id}")',
        "torch.device(f'cuda:{inference_cfg.device_id}')",
        'torch.device("cuda:" + str(inference_cfg.device_id))',
    ]:
        if pat in patched:
            patched = patched.replace(pat, device_expr)
            break

    # Variant B: try/except block (nested inside else:) that assigns self.device directly
    old_block = (
        "            try:\n"
        "                if torch.backends.mps.is_available():\n"
        "                    self.device = 'mps'\n"
        "                else:\n"
        "                    self.device = 'cuda:' + str(self.device_id)\n"
        "            except:\n"
        "                self.device = 'cuda:' + str(self.device_id)"
    )
    new_block = (
        f"            if torch.cuda.is_available():  {sentinel}\n"
        "                self.device = 'cuda:' + str(self.device_id)\n"
        "            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():\n"
        "                self.device = 'mps'\n"
        "            else:\n"
        "                self.device = 'cpu'"
    )
    if old_block in patched:
        patched = patched.replace(old_block, new_block)

    if patched != text:
        wrapper_py.write_text(patched, encoding="utf-8")
        print("Patched LivePortrait wrapper for cross-platform device detection.")
    else:
        print("Warning: could not find device string pattern in live_portrait_wrapper.py — manual check needed.")


def patch_wav2lip_for_mps():
    inference_py = Path(WAV2LIP_DIR, "inference.py")
    core_py = Path(WAV2LIP_DIR, "face_detection", "detection", "core.py")

    old = "device = 'cuda' if torch.cuda.is_available() else 'cpu'"
    new = "device = 'cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu')"
    text = inference_py.read_text(encoding="utf-8")
    if old in text:
        inference_py.write_text(text.replace(old, new), encoding="utf-8")
        print("Patched Wav2Lip inference.py for MPS support.")

    old = "if 'cpu' not in device and 'cuda' not in device:"
    new = "if 'cpu' not in device and 'cuda' not in device and 'mps' not in device:"
    text = core_py.read_text(encoding="utf-8")
    if old in text:
        core_py.write_text(text.replace(old, new), encoding="utf-8")
        print("Patched Wav2Lip core.py for MPS support.")

    text = inference_py.read_text(encoding="utf-8")
    patched = text
    patched = patched.replace(
        "'ffmpeg -y -i {} -strict -2 {}'.format(args.audio, 'temp/temp.wav')",
        "'ffmpeg -y -loglevel error -i {} -strict -2 {}'.format(args.audio, 'temp/temp.wav')",
    )
    patched = patched.replace(
        "'ffmpeg -y -i {} -i {} -strict -2 -q:v 1 {}'.format(args.audio, 'temp/result.avi', args.outfile)",
        "'ffmpeg -y -loglevel error -i {} -i {} -strict -2 -q:v 1 {}'.format(args.audio, 'temp/result.avi', args.outfile)",
    )
    if patched != text:
        inference_py.write_text(patched, encoding="utf-8")
        print("Patched Wav2Lip inference.py to suppress ffmpeg output.")


def setup_all():
    clone_repo(LP_REPO_URL, LP_REPO_DIR, "LivePortrait")
    clone_repo(WAV2LIP_REPO_URL, WAV2LIP_DIR, "Wav2Lip")
    GFPGAN_WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    patch_liveportrait_for_pose_eyes()
    patch_liveportrait_device()
    patch_wav2lip_for_mps()

    lp_weights = Path(LP_REPO_DIR, "pretrained_weights", "liveportrait", "base_models", "appearance_feature_extractor.pth")
    if not lp_weights.exists():
        print("Missing model files:\n  • LivePortrait pretrained weights\n")
        download_liveportrait_weights()

    DRIVING_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    missing = [
        (Path(FACE_DET_DIR, "s3fd.pth"), FACE_DET_URL, "s3fd.pth (face detection)"),
        (GFPGAN_MODEL_PATH, GFPGAN_MODEL_URL, "GFPGANv1.4.pth (face restoration)"),
    ]
    missing = [(p, url, name) for p, url, name in missing if not p.exists()]
    if missing:
        print("Missing model files:")
        for _, _, name in missing:
            print(f"  • {name}")
        print()
        for path, url, _ in missing:
            download_file(url, path)

    if not CHECKPOINT_PATH.exists():
        print("Missing model files:\n  • wav2lip_gan.pth (Wav2Lip checkpoint)\n")
        download_wav2lip_checkpoint()
