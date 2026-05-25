import os
import subprocess
import threading
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from tqdm import tqdm

try:
    from .layout import compute as compute_layout
except ImportError:
    import sys as _sys
    _sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
    from layout import compute as compute_layout

# ── News-show colour palette ──────────────────────────────────────────────────
BG         = (8,  12,  24)
ACCENT_RED = (210, 0,  30)
AMBER      = (245, 166, 35)
WHITE      = (255, 255, 255)
LIGHT_GREY = (210, 215, 225)
DIVIDER    = (35,  45,  75)
TICKER_BG  = (18,  24,  50)


# ── Font helpers ──────────────────────────────────────────────────────────────

_FONTS_DIR = Path(__file__).resolve().parent / "fonts"

def _load_font(size: int, bold: bool = False, semibold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        # bundled Inter (preferred)
        str(_FONTS_DIR / ("Inter-Bold.ttf" if bold else "Inter-SemiBold.ttf" if semibold else "Inter-Regular.ttf")),
        # system fallbacks
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.FreeTypeFont,
               max_width: int, draw: ImageDraw.Draw) -> list[str]:
    words  = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_rounded_rect(draw: ImageDraw.Draw, xy, radius: int, fill,
                       outline=None, width: int = 1) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill,
                           outline=outline, width=width)


# ── News panel renderer ───────────────────────────────────────────────────────

def _center_x(text: str, font: ImageFont.FreeTypeFont,
               draw: ImageDraw.Draw, width: int) -> int:
    return int((width - draw.textlength(text, font=font)) // 2)


def _make_top_layer(logo_path: Path | None, total_w: int, H: int, m) -> Image.Image:
    """
    RGBA layer composited on top of everything in ffmpeg.
    Draws: NOW HIRING amber block (right side of ticker) + trapezoid logo (bottom-left).
    Both sit above the face video.
    """
    layer = Image.new("RGBA", (total_w, H), (0, 0, 0, 0))

    # ── NOW HIRING — right side of ticker, full ticker height ─────────────────
    hiring_font = _load_font(m.hiring_font)
    d = ImageDraw.Draw(layer)
    htb    = d.textbbox((0, 0), "NOW HIRING", font=hiring_font)
    nh_pad = int(m.PAD * 0.6)
    nh_w   = (htb[2] - htb[0]) + nh_pad * 2
    nh_x   = total_w - nh_w
    d.rectangle([nh_x, m.ticker_y, total_w, H], fill=(*AMBER, 255))
    text_x = nh_x + (nh_w - (htb[2] - htb[0])) // 2
    text_y = m.ticker_y + (m.ticker_h - (htb[3] - htb[1])) // 2 - htb[1]
    d.text((text_x, text_y), "NOW HIRING", font=hiring_font, fill=(20, 10, 0, 255))

    # ── LOGO — trapezoid at bottom-left ───────────────────────────────────────
    if logo_path and Path(logo_path).exists():
        x, y_top, w, h = 0, H - m.logo_h, m.logo_w, m.logo_h
        slant = h // 2
        pad_x = max(10, h // 6)
        pad_y = max(4,  h // 12)
        trap  = [(0, y_top), (w, y_top), (w + slant, H), (0, H)]

        # drop shadow
        shadow = Image.new("RGBA", (total_w, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.polygon([(p[0] + 3, p[1] + 3) for p in trap], fill=(0, 0, 0, 110))
        shadow = shadow.filter(ImageFilter.GaussianBlur(6))
        layer  = Image.alpha_composite(layer, shadow)

        # champagne trapezoid background
        d = ImageDraw.Draw(layer)
        d.polygon(trap, fill=(224, 205, 172, 255))

        # logo image centred within the trapezoid's rectangular bounding box
        try:
            logo = Image.open(Path(logo_path)).convert("RGBA")
            logo.thumbnail((w - pad_x * 2, h - pad_y * 2), Image.LANCZOS)
            lw, lh = logo.size
            layer.paste(logo, ((w - lw) // 2, y_top + (h - lh) // 2), logo.split()[3])
        except Exception:
            pass

    return layer


def _make_news_panel(
    company: str,
    location: str,
    position: str,
    experience: str,
    skills: list[str],
    total_width: int,
    face_width: int,
    height: int,
    out_png: Path,
) -> None:
    m  = compute_layout(height)
    ox = face_width

    img = Image.new("RGB", (total_width, height), color=BG)
    d   = ImageDraw.Draw(img)

    # ── Chrome ────────────────────────────────────────────────────────────────
    d.rectangle([0, 0, total_width, m.bar_h],                    fill=ACCENT_RED)
    d.rectangle([0, m.ticker_y, total_width, height],            fill=TICKER_BG)
    d.rectangle([0, m.ticker_y, total_width, m.ticker_y + 3],   fill=ACCENT_RED)
    d.rectangle([face_width, m.bar_h, face_width + 2, m.ticker_y], fill=(40, 50, 90))

    # ── Fonts ─────────────────────────────────────────────────────────────────
    title_font   = _load_font(m.title_font,   bold=True)
    label_font   = _load_font(m.label_font,   bold=True)
    value_font   = _load_font(m.value_font)
    company_font = _load_font(m.company_font, bold=True)
    badge_font   = _load_font(m.badge_font,   bold=True)
    hiring_font  = _load_font(m.hiring_font)
    skill_font   = _load_font(m.skill_font)

    # ── Title: wrap and compute actual height ─────────────────────────────────
    title_lines = _wrap_text(position.upper(), title_font, m.inner, d)[:2]
    title_h     = len(title_lines) * m.title_line_h

    # ── Skill rows: wrap and compute actual height ────────────────────────────
    x_cur = skill_rows = 0
    for s in skills:
        tw = int(d.textlength(s, font=skill_font)) + m.tag_px * 2
        if x_cur > 0 and x_cur + tw > m.inner:
            skill_rows += 1
            x_cur = 0
        x_cur += tw + m.tag_gx
    skill_rows += 1
    skills_h = skill_rows * (m.tag_h + m.tag_gy) - m.tag_gy

    # ── Block height and vertical centering ─────────────────────────────────
    block_h = (
        title_h + m.G2 + 2 + m.G3
        + m.company_row_h + m.row_gap + m.row_h + m.G4 + 1 + m.G5
        + m.label_font + m.G6
        + skills_h
    )
    margin = max(int(m.content_h * 0.06), (m.content_h - block_h) // 2)
    y      = m.bar_h + margin

    # ── TITLE ─────────────────────────────────────────────────────────────────
    for line in title_lines:
        tx = ox + _center_x(line, title_font, d, m.text_w)
        d.text((tx, y), line, font=title_font, fill=WHITE)
        y += m.title_line_h
    y += m.G2

    # ── RED DIVIDER ───────────────────────────────────────────────────────────
    d.rectangle([ox + m.PAD, y, total_width - m.PAD, y + 2], fill=ACCENT_RED)
    y += 2 + m.G3

    # ── INFO ROWS (card style) ─────────────────────────────────────────────────
    _accent_w  = 3
    _card_px   = int(m.PAD * 0.50)
    _card_bg   = (18, 26, 50)
    _card_out  = (30, 45, 80)
    _lbl_clr   = (190, 140, 45)   # muted amber for small label
    _card_r    = 5

    def _info_card(x0, y0, x1, y1, lbl, val, vfont, val_color=WHITE):
        rh = y1 - y0
        _draw_rounded_rect(d, [x0, y0, x1, y1], radius=_card_r,
                           fill=_card_bg, outline=_card_out, width=1)
        d.rectangle([x0, y0 + _card_r, x0 + _accent_w, y1 - _card_r], fill=AMBER)
        tx = x0 + _accent_w + _card_px
        ltb       = d.textbbox((0, 0), lbl, font=label_font)
        lh        = ltb[3] - ltb[1]
        pad_top   = int(rh * 0.20)
        inner_gap = int(rh * 0.20)
        d.text((tx, y0 + pad_top - ltb[1]), lbl, font=label_font, fill=_lbl_clr)
        vtb = d.textbbox((0, 0), val, font=vfont)
        d.text((tx, y0 + pad_top + lh + inner_gap - vtb[1]), val, font=vfont, fill=val_color)

    cx0, cx1   = ox + m.PAD, total_width - m.PAD
    card_gap   = int(m.PAD * 0.35)
    half_w     = (cx1 - cx0 - card_gap) // 2

    _info_card(cx0, y, cx1, y + m.company_row_h, "COMPANY", company, company_font)
    y += m.company_row_h + m.row_gap

    _info_card(cx0,                    y, cx0 + half_w, y + m.row_h,
               "LOCATION",   location,   value_font, LIGHT_GREY)
    _info_card(cx0 + half_w + card_gap, y, cx1,         y + m.row_h,
               "EXPERIENCE", experience, value_font, LIGHT_GREY)
    y += m.row_h + m.G4

    # ── THIN DIVIDER ──────────────────────────────────────────────────────────
    d.rectangle([ox + m.PAD, y, total_width - m.PAD, y + 1], fill=DIVIDER)
    y += 1 + m.G5

    # ── SKILLS LABEL ──────────────────────────────────────────────────────────
    d.text((ox + _center_x("SKILLS", label_font, d, m.text_w), y),
           "SKILLS", font=label_font, fill=AMBER)
    y += m.label_font + m.G6

    # ── SKILL TAGS (centred row-by-row) ───────────────────────────────────────
    rows: list[list[str]] = []
    cur: list[str] = []
    x_cur = 0
    for s in skills:
        tw = int(d.textlength(s, font=skill_font)) + m.tag_px * 2
        if x_cur > 0 and x_cur + tw > m.inner:
            rows.append(cur); cur = []; x_cur = 0
        cur.append(s); x_cur += tw + m.tag_gx
    if cur:
        rows.append(cur)

    for row in rows:
        row_w = (
            sum(int(d.textlength(s, font=skill_font)) + m.tag_px * 2 for s in row)
            + m.tag_gx * (len(row) - 1)
        )
        x_cur = ox + (m.text_w - row_w) // 2
        for s in row:
            tw = int(d.textlength(s, font=skill_font)) + m.tag_px * 2
            _draw_rounded_rect(d, [x_cur, y, x_cur + tw, y + m.tag_h],
                               radius=4, fill=(25, 35, 75), outline=AMBER, width=1)
            d.text((x_cur + tw // 2, y + m.tag_h // 2), s,
                   font=skill_font, fill=LIGHT_GREY, anchor="mm")
            x_cur += tw + m.tag_gx
        y += m.tag_h + m.tag_gy

    img.save(out_png)


# ── Video info ────────────────────────────────────────────────────────────────

def _get_video_info(video: Path) -> tuple[int, int, float, float]:
    """Returns (width, height, duration_seconds, fps)."""
    res = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "stream=width,height,r_frame_rate:format=duration",
            "-of", "csv=p=0", str(video),
        ],
        capture_output=True, text=True,
    )
    width, height, duration, fps = 0, 0, 0.0, 25.0
    for line in res.stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) == 3:
            # stream line: width,height,r_frame_rate  e.g. 480,480,25/1
            try:
                width, height = int(parts[0]), int(parts[1])
                num, den = parts[2].split("/")
                fps = float(num) / float(den)
            except (ValueError, ZeroDivisionError):
                pass
        elif len(parts) == 1:
            try:
                duration = float(parts[0])
            except ValueError:
                pass
    return width, height, duration, fps


# ── ffmpeg with progress bar ──────────────────────────────────────────────────

def _run_ffmpeg(cmd: list[str], total_frames: int, desc: str) -> tuple[int, str]:
    """
    Run an ffmpeg command, streaming frame progress to a tqdm bar.
    Returns (returncode, stderr_text).
    """
    full_cmd = [cmd[0], "-nostats"] + cmd[1:] + ["-progress", "pipe:1"]

    process = subprocess.Popen(
        full_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stderr_lines: list[str] = []

    def _drain_stderr() -> None:
        for ln in process.stderr:
            stderr_lines.append(ln)

    t = threading.Thread(target=_drain_stderr, daemon=True)
    t.start()

    last_frame = 0
    with tqdm(
        total=total_frames,
        unit="fr",
        desc=f"  {desc}",
        ncols=72,
        colour="cyan",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} frames [{elapsed}<{remaining}]",
    ) as pbar:
        for line in process.stdout:
            line = line.strip()
            if line.startswith("frame="):
                try:
                    frame = int(line.split("=")[1])
                    delta = frame - last_frame
                    if delta > 0:
                        pbar.update(delta)
                        last_frame = frame
                except ValueError:
                    pass
        if last_frame < total_frames:
            pbar.update(total_frames - last_frame)

    process.wait()
    t.join()
    return process.returncode, "".join(stderr_lines)


# ── Public API ────────────────────────────────────────────────────────────────

def create_video_with_text(
    video_path: Path,
    output_path: Path,
    company: str,
    location: str,
    position: str,
    experience: str,
    skills: list[str],
    logo_path: Path | None = None,
    target_height: int = 720,
) -> dict:
    """
    Composite video_path (left 1/3) with a news-style job panel (right 2/3)
    in a 16:9 frame. The panel background (accent bar + ticker) spans the full
    width so padding areas around the face video share the same design.

    logo_path: optional path to a company logo image (PNG/JPG with transparency).
    target_height: output height in pixels (720 = HD, 1080 = Full HD).
    """
    t_total = time.time()
    video_path  = Path(video_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not video_path.exists():
        return {"status": "failed", "error": f"Video not found: {video_path}"}

    # Step 1 — probe video
    print("[1/3] Analysing video...", end=" ", flush=True)
    t0 = time.time()
    _, vid_h, duration, fps = _get_video_info(video_path)
    if vid_h == 0 or duration == 0.0:
        return {"status": "failed", "error": "Could not read video info"}
    print(f"done  ({time.time() - t0:.2f}s)")

    H       = max(target_height, vid_h)
    H       = H if H % 2 == 0 else H - 1
    total_w = int(round(H * 16 / 9 / 2) * 2)
    face_w  = int(round(total_w / 3 / 2) * 2)
    text_w  = total_w - face_w
    print(f"      output: {total_w}x{H}  (face {face_w}px | panel {text_w}px)")

    # Step 2 — render full-width background panel
    print("[2/3] Rendering news panel...", end=" ", flush=True)
    t0 = time.time()
    tmp      = Path(os.path.join(os.path.dirname(str(output_path)), f"_panel_{os.getpid()}.png"))
    tmp_logo = Path(os.path.join(os.path.dirname(str(output_path)), f"_logo_{os.getpid()}.png"))
    try:
        lm = compute_layout(H)

        _make_news_panel(
            company=company, location=location, position=position,
            experience=experience, skills=skills,
            total_width=total_w, face_width=face_w, height=H,
            out_png=tmp,
        )

        # Build top layer (NOW HIRING + optional trapezoid logo) — always present
        top_layer = _make_top_layer(logo_path, total_w, H, lm)
        top_layer.save(tmp_logo)

        print(f"done  ({time.time() - t0:.2f}s)")

        # Step 3 — ffmpeg: overlay scaled face onto full-width background
        print("[3/3] Compositing:")

        ticker_unit = (
            f"    {position.upper()}    |    {company}    |    {location}"
            f"    |    EXP: {experience}    |    " +
            "    |    ".join(s.upper() for s in skills) + "    |    "
        )
        # Repeat 10× so the scroll appears infinite for any reasonable video length
        ticker_text = ticker_unit * 10

        def _safe(t):
            # Escape for ffmpeg filter syntax: backslash, single-quote, colon
            return t.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")

        def _font_path(p: Path) -> str:
            # ffmpeg filter syntax needs forward slashes and escaped drive-letter colon
            return str(p).replace("\\", "/").replace(":/", "\\:/")

        ticker_safe = _safe(ticker_text)

        speed = 80

        _inter_italic = _FONTS_DIR / "Inter-Italic.ttf"
        if _inter_italic.exists():
            ffmpeg_font = _font_path(_inter_italic)
        elif Path("/System/Library/Fonts/Helvetica.ttc").exists():
            ffmpeg_font = "/System/Library/Fonts/Helvetica.ttc"
        else:
            ffmpeg_font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

        # 10× repeated text → tw ≈ 30,000 px → loops every ~6.5 min (effectively infinite)
        drawtext = (
            f"drawtext=fontfile='{ffmpeg_font}':"
            f"text='{ticker_safe}':"
            f"fontsize={lm.ticker_font}:"
            f"fontcolor=white:"
            f"x=w-mod(t*{speed}+w\\,tw+w):"
            f"y={lm.ticker_text_y}"
        )

        face_overlay = (
            f"[0:v]scale={face_w}:{lm.content_h}:"
            f"force_original_aspect_ratio=decrease:flags=lanczos[face_s];"
            f"[1:v][face_s]overlay="
            f"x=({face_w}-overlay_w)/2:y={lm.bar_h}+({lm.content_h}-overlay_h)/2,"
            f"{drawtext}"
        )

        filter_graph = face_overlay + "[composite];[composite][2:v]overlay=0:0[out]"
        extra_inputs = ["-loop", "1", "-i", str(tmp_logo)]

        total_frames = max(1, int(duration * fps))

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-loop", "1", "-i", str(tmp),
            *extra_inputs,
            "-filter_complex", filter_graph,
            "-map", "[out]",
            "-map", "0:a?",
            "-t", str(duration),
            "-c:v", "libx264", "-crf", "18", "-preset", "slow",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_path),
        ]

        t0 = time.time()
        rc, stderr = _run_ffmpeg(cmd, total_frames, "Encoding")
        encode_time = time.time() - t0

        if rc != 0:
            return {"status": "failed", "error": "ffmpeg failed", "stderr": stderr}

        print(f"      encode done  ({encode_time:.1f}s)")

    finally:
        tmp.unlink(missing_ok=True)
        tmp_logo.unlink(missing_ok=True)

    total_time = time.time() - t_total
    print(f"\nTotal: {total_time:.1f}s  →  {output_path}")

    return {
        "status": "completed",
        "output_path": str(output_path),
        "timings": {
            "total": round(total_time, 2),
            "encode": round(encode_time, 2),
        },
    }


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    N8N_FILES    = Path(__file__).resolve().parent.parent / "assets"
    input_video  = N8N_FILES / "test_output_v4.mp4"
    output_video = N8N_FILES / "new_test_output_v4.mp4"

    # Optional: place a logo PNG at assets/company_logo.png to test logo rendering
    logo = N8N_FILES / "company_logo.png"

    result = create_video_with_text(
        video_path  = input_video,
        output_path = output_video,
        company     = "Sundayy",
        location    = "United States",
        position    = "Software Engineer (Js, Typescript)",
        experience  = "Not specified",
        skills      = ["JavaScript", "TypeScript", "Software Development"],
        logo_path   = logo if logo.exists() else None,
    )

    if result["status"] != "completed":
        print(f"\nFailed: {result['error']}")
        if "stderr" in result:
            print(result["stderr"])
        sys.exit(1)
