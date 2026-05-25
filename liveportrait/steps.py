import math
import pickle
import subprocess
import tempfile
from pathlib import Path

from .enhancement import enhance_video
from .lp_runner import run_liveportrait as _lp_run
from .w2l_runner import run_lipsync as _w2l_run


def prepare_driving_video(driving_video: Path, max_secs: int = 7, max_height: int = 512) -> Path:
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(driving_video)],
        capture_output=True, text=True,
    )
    duration = float(probe.stdout.strip()) if probe.returncode == 0 and probe.stdout.strip() else 999.0

    probe_res = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "stream=height", "-of", "csv=p=0", str(driving_video)],
        capture_output=True, text=True,
    )
    height = int(probe_res.stdout.strip().split("\n")[0]) if probe_res.returncode == 0 and probe_res.stdout.strip() else 9999

    needs_trim = duration > max_secs
    needs_scale = height > max_height

    if not needs_trim and not needs_scale:
        return driving_video

    tmp = Path(tempfile.mktemp(suffix=".mp4"))
    vf_parts = []
    if needs_scale:
        vf_parts.append(f"scale=-2:{max_height}")
    vf_filter = ["-vf", ",".join(vf_parts)] if vf_parts else []
    trim_args = ["-t", str(max_secs)] if needs_trim else []

    subprocess.run(
        ["ffmpeg", "-y", "-i", str(driving_video), *trim_args, *vf_filter,
         "-c:v", "h264_videotoolbox", "-q:v", "75", "-an", str(tmp)],
        capture_output=True,
    )
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
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(audio)],
        capture_output=True, text=True,
    )
    if probe.returncode != 0 or not probe.stdout.strip():
        return animated
    audio_dur = float(probe.stdout.strip())

    probe2 = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(animated)],
        capture_output=True, text=True,
    )
    if probe2.returncode != 0 or not probe2.stdout.strip():
        return animated
    clip_dur = float(probe2.stdout.strip())

    cycle_dur = clip_dur * 2
    n_cycles = math.ceil(audio_dur / cycle_dur) + 1

    pingpong_tmp = output.with_suffix("._pp.mp4")
    r = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(animated),
            "-filter_complex", "[0:v]reverse[r];[0:v][r]concat=n=2:v=1[out]",
            "-map", "[out]", "-c:v", "h264_videotoolbox", "-q:v", "75", "-an", str(pingpong_tmp),
        ],
        capture_output=True,
    )
    if r.returncode != 0 or not pingpong_tmp.exists():
        return animated

    r2 = subprocess.run(
        [
            "ffmpeg", "-y",
            "-stream_loop", str(n_cycles), "-i", str(pingpong_tmp),
            "-t", str(audio_dur + 0.5),
            "-c:v", "h264_videotoolbox", "-q:v", "75", "-an", str(output),
        ],
        capture_output=True,
    )
    pingpong_tmp.unlink(missing_ok=True)

    if r2.returncode != 0 or not output.exists():
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
