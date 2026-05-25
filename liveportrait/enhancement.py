import subprocess
from pathlib import Path

from tqdm import tqdm

from .config import GFPGAN_MODEL_PATH

_gfpgan = None


def patch_basicsr_for_mps():
    import torch
    if not torch.backends.mps.is_available():
        return

    import basicsr.ops.upfirdn2d.upfirdn2d as _uf
    from basicsr.ops.upfirdn2d.upfirdn2d import upfirdn2d_native, UpFirDn2d

    def _upfirdn2d_mps(input, kernel, up=1, down=1, pad=(0, 0)):
        if input.device.type in ('cpu', 'mps'):
            return upfirdn2d_native(input, kernel, up, up, down, down, pad[0], pad[1], pad[0], pad[1])
        return UpFirDn2d.apply(input, kernel, (up, up), (down, down), (pad[0], pad[1], pad[0], pad[1]))

    _uf.upfirdn2d = _upfirdn2d_mps
    import basicsr.ops.upfirdn2d as _uf_pkg
    _uf_pkg.upfirdn2d = _upfirdn2d_mps

    import basicsr.ops.fused_act.fused_act as _fa
    from torch.nn import functional as F
    _orig_flr = _fa.FusedLeakyReLUFunction

    def _fused_leaky_relu_mps(input, bias, negative_slope=0.2, scale=2 ** 0.5):
        if input.device.type in ('cpu', 'mps'):
            bv = bias.view(1, -1, 1, 1) if input.dim() == 4 else bias.view(1, -1)
            return F.leaky_relu(input + bv, negative_slope=negative_slope) * scale
        return _orig_flr.apply(input, bias, negative_slope, scale)

    _fa.fused_leaky_relu = _fused_leaky_relu_mps
    import basicsr.ops.fused_act as _fa_pkg
    _fa_pkg.fused_leaky_relu = _fused_leaky_relu_mps
    print("Patched basicsr ops for MPS.")


def load_gfpgan():
    global _gfpgan
    if _gfpgan is not None:
        return _gfpgan
    import torch
    from gfpgan import GFPGANer

    if torch.cuda.is_available():
        device = torch.device('cuda')
    elif torch.backends.mps.is_available():
        device = torch.device('mps')
    else:
        device = torch.device('cpu')
    print(f"Loading GFPGAN on device: {device}")
    _gfpgan = GFPGANer(
        model_path=str(GFPGAN_MODEL_PATH),
        upscale=1,
        arch='clean',
        channel_multiplier=2,
        bg_upsampler=None,
        device=device,
    )
    return _gfpgan


def enhance_video(
    input_path: Path,
    output_path: Path,
    upscale: int = 1,
    face_restore: bool = False,
    face_restore_step: int = 1,
):
    vf = "hqdn3d=0:0:3:3"
    if upscale > 1:
        vf = f"scale=iw*{upscale}:ih*{upscale}:flags=lanczos,{vf}"

    if not face_restore:
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(input_path),
                "-vf", vf,
                "-c:v", "hevc_videotoolbox", "-q:v", "65", "-tag:v", "hvc1",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k",
                str(output_path),
            ],
            capture_output=True,
        )
        return

    import cv2

    enhancer = load_gfpgan()

    cap = cv2.VideoCapture(str(input_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out_w, out_h = w * upscale, h * upscale

    tmp_video = input_path.with_suffix("._enh.mp4")
    writer = cv2.VideoWriter(str(tmp_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (out_w, out_h))

    last_restored = None
    for i in tqdm(range(frame_count), desc="GFPGAN"):
        ret, frame = cap.read()
        if not ret:
            break
        if i % face_restore_step == 0:
            _, _, restored = enhancer.enhance(frame, has_aligned=False, only_center_face=True, paste_back=True)
            last_restored = restored
        writer.write(last_restored if last_restored is not None else frame)

    cap.release()
    writer.release()

    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(tmp_video), "-i", str(input_path),
            "-map", "0:v", "-map", "1:a",
            "-vf", "hqdn3d=0:0:3:3",
            "-c:v", "hevc_videotoolbox", "-q:v", "65", "-tag:v", "hvc1",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            str(output_path),
        ],
        capture_output=True,
    )
    tmp_video.unlink(missing_ok=True)
