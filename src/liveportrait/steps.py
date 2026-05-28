import functools
import math
import pickle
import subprocess
import tempfile
from pathlib import Path

from .enhancement import enhance_video
from .lp_runner import run_liveportrait as _lp_run
from .w2l_runner import run_lipsync as _w2l_run


@functools.lru_cache(maxsize=1)
def _h264_encoder() -> tuple[str, list[str]]:
    """Pick the best available H.264 encoder: Apple VT → NVENC → software."""
    candidates = [
        ("h264_videotoolbox", ["-q:v", "75"]),
        ("h264_nvenc",        ["-cq",  "28"]),
        ("libx264",           ["-crf", "23", "-preset", "fast"]),
    ]
    for encoder, quality_args in candidates:
        r = subprocess.run(
            ["ffmpeg", "-f", "lavfi", "-i", "nullsrc=s=16x16:d=0.1",
             "-c:v", encoder, "-f", "null", "-"],
            capture_output=True,
        )
        if r.returncode == 0:
            return encoder, quality_args
    raise RuntimeError(
        "No H.264 encoder found. Install ffmpeg with libx264 support:\n"
        "  Mac:     brew install ffmpeg\n"
        "  Windows: https://www.gyan.dev/ffmpeg/builds/ (add bin/ to PATH)"
    )


def _ffprobe(args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["ffprobe"] + args, capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError(
            "ffprobe not found. Install ffmpeg:\n"
            "  Mac:     brew install ffmpeg\n"
            "  Windows: https://www.gyan.dev/ffmpeg/builds/ (add bin/ to PATH)"
        )


def prepare_driving_video(driving_video: Path, max_secs: int = 7, max_height: int = 512) -> Path:
    probe = _ffprobe(["-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(driving_video)])
    duration = float(probe.stdout.strip()) if probe.returncode == 0 and probe.stdout.strip() else 999.0

    probe_res = _ffprobe(["-v", "quiet", "-show_entries", "stream=height", "-of", "csv=p=0", str(driving_video)])
    height = int(probe_res.stdout.strip().split("\n")[0]) if probe_res.returncode == 0 and probe_res.stdout.strip() else 9999

    needs_trim = duration > max_secs
    needs_scale = height > max_height

    if not needs_trim and not needs_scale:
        return driving_video

    encoder, quality_args = _h264_encoder()
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as _f:
        tmp = Path(_f.name)
    vf_parts = []
    if needs_scale:
        vf_parts.append(f"scale=-2:{max_height}")
    vf_filter = ["-vf", ",".join(vf_parts)] if vf_parts else []
    trim_args = ["-t", str(max_secs)] if needs_trim else []

    r = subprocess.run(
        ["ffmpeg", "-y", "-i", str(driving_video), *trim_args, *vf_filter,
         "-c:v", encoder, *quality_args, "-an", str(tmp)],
        capture_output=True,
    )
    if r.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg failed preparing driving video:\n{r.stderr.decode()}")
    print(f"Driving video prepared: {duration:.1f}s→{min(duration, max_secs):.0f}s, "
          f"{height}px→{min(height, max_height)}px tall")
    return tmp


def run_liveportrait(
    source_image: Path,
    driving_video: Path,
    output: Path,
    expression_multiplier: float,
    flag_pasteback: bool,
    animation_region: str = "pose_eyes",
    smooth_observation_variance: float = 3e-4,
) -> dict:
    if driving_video.suffix.lower() == ".pkl":
        prepared = driving_video
        cleanup_prepared = False
    else:
        prepared = prepare_driving_video(driving_video)
        cleanup_prepared = prepared != driving_video

    try:
        return _lp_run(
            source_image=source_image,
            driving_video=prepared,
            output=output,
            expression_multiplier=expression_multiplier,
            flag_pasteback=flag_pasteback,
            animation_region=animation_region,
            smooth_observation_variance=smooth_observation_variance,
        )
    finally:
        if cleanup_prepared:
            prepared.unlink(missing_ok=True)


def make_seamless_loop(animated: Path, audio: Path, output: Path) -> Path:
    probe = _ffprobe(["-v", "quiet", "-show_entries", "format=duration",
                      "-of", "csv=p=0", str(audio)])
    if probe.returncode != 0 or not probe.stdout.strip():
        return animated
    audio_dur = float(probe.stdout.strip())

    probe2 = _ffprobe(["-v", "quiet", "-show_entries", "format=duration",
                       "-of", "csv=p=0", str(animated)])
    if probe2.returncode != 0 or not probe2.stdout.strip():
        return animated
    clip_dur = float(probe2.stdout.strip())

    encoder, quality_args = _h264_encoder()
    cycle_dur = clip_dur * 2
    n_cycles = math.ceil(audio_dur / cycle_dur) + 1

    pingpong_tmp = output.with_suffix("._pp.mp4")
    r = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(animated),
            "-filter_complex", "[0:v]reverse[r];[0:v][r]concat=n=2:v=1[out]",
            "-map", "[out]", "-c:v", encoder, *quality_args, "-an", str(pingpong_tmp),
        ],
        capture_output=True,
    )
    if r.returncode != 0 or not pingpong_tmp.exists():
        print(f"Warning: ping-pong step failed — using original clip (audio may loop abruptly):\n{r.stderr.decode()}")
        return animated

    r2 = subprocess.run(
        [
            "ffmpeg", "-y",
            "-stream_loop", str(n_cycles), "-i", str(pingpong_tmp),
            "-t", str(audio_dur + 0.5),
            "-c:v", encoder, *quality_args, "-an", str(output),
        ],
        capture_output=True,
    )
    pingpong_tmp.unlink(missing_ok=True)

    if r2.returncode != 0 or not output.exists():
        print(f"Warning: loop extension failed — using original clip (audio may loop abruptly):\n{r2.stderr.decode()}")
        return animated

    print(f"Seamless loop: {clip_dur:.1f}s clip → {audio_dur:.1f}s looped ({n_cycles} ping-pong cycles)")
    return output


def trim_pkl(src: Path, max_secs: float) -> Path:
    with open(src, "rb") as f:
        data = pickle.load(f)

    fps = data.get("output_fps", 25)
    total = data.get("n_frames", len(data.get("motion", [])))
    keep = min(total, max(1, math.floor(max_secs * fps)))

    if keep >= total:
        return src

    out = src.with_stem(f"{src.stem}_trim{keep}")
    if out.exists():
        print(f"Using cached trimmed pkl: {out.name} ({keep/fps:.1f}s)")
        return out

    trimmed = {k: v for k, v in data.items()}
    trimmed["n_frames"] = keep
    for key in ("motion", "c_eyes_lst", "c_lip_lst"):
        if key in trimmed:
            trimmed[key] = trimmed[key][:keep]

    with open(out, "wb") as f:
        pickle.dump(trimmed, f)

    print(f"Trimmed pkl: {total} → {keep} frames ({keep/fps:.1f}s) → {out.name}")
    return out


def merge_audio_from_video(video_source: Path, animated: Path, output: Path) -> dict:
    """Mux audio track from video_source into animated (which has no audio)."""
    encoder, quality_args = _h264_encoder()
    r = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(animated),
            "-i", str(video_source),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", encoder, *quality_args,
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(output),
        ],
        capture_output=True,
    )
    if r.returncode != 0:
        return {"status": "failed", "error": "ffmpeg audio merge failed", "stderr": r.stderr.decode()}
    return {"status": "completed"}


def run_lipsync(
    face: Path,
    audio: Path,
    output: Path,
    enhance: bool,
    pads: tuple[int, int, int, int] = (0, 10, 0, 0),
    face_restore: bool = True,
    face_restore_step: int = 1,
    nosmooth: bool = False,
    resize_factor: int = 1,
) -> dict:
    lipsync_out = output.with_suffix("._raw.mp4") if enhance else output

    result = _w2l_run(
        face=face,
        audio_path=audio,
        output=lipsync_out,
        pads=pads,
        resize_factor=resize_factor,
        nosmooth=nosmooth,
    )

    if result.get("status") == "failed":
        return result

    enh_time = 0.0
    if enhance:
        import time as _time
        t_enh = _time.time()
        try:
            enhance_video(
                lipsync_out, output,
                upscale=resize_factor,
                face_restore=face_restore,
                face_restore_step=face_restore_step,
            )
        except Exception as e:
            print(f"Enhancement failed ({e}), using raw output")
            lipsync_out.rename(output)
        else:
            lipsync_out.unlink(missing_ok=True)
        enh_time = _time.time() - t_enh

    return {"status": "completed", "enhancement_time": enh_time}
