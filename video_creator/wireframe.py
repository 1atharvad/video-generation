"""
Render a labeled wireframe of the news-panel layout.
Run:  python -m video_creator.wireframe   OR   python3 wireframe.py [height]
Output: assets/wireframe.png
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from layout import compute as compute_layout


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _box(d, xy, fill, outline="#ffffff", label="", label_color="#ffffff", font=None):
    d.rectangle(xy, fill=fill, outline=outline, width=1)
    if label and font:
        x0, y0, x1, y1 = xy
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        tw = d.textlength(label, font=font)
        th = font.size
        if tw < (x1 - x0) - 4 and th < (y1 - y0) - 4:
            d.text((cx - tw // 2, cy - th // 2), label, font=font, fill=label_color)


def render(out_path: Path, target_height: int = 720) -> None:
    m = compute_layout(target_height)

    H       = m.H
    total_w = m.total_w
    face_w  = m.face_w
    text_w  = m.text_w
    ox      = face_w
    inner   = m.inner
    PAD     = m.PAD

    title_h  = 2 * m.title_line_h
    tag_gy   = m.tag_gy
    skills_h = 2 * (m.tag_h + tag_gy) - tag_gy

    block_h = (
        title_h + m.G2 + 2 + m.G3
        + m.company_row_h + m.row_gap + m.row_h + m.G4 + 1 + m.G5
        + m.label_font + m.G6
        + skills_h
    )

    min_margin = int(m.content_h * 0.06)
    margin     = max(min_margin, (m.content_h - block_h) // 2)
    y          = m.bar_h + margin

    img = Image.new("RGB", (total_w, H), "#0d1117")
    d   = ImageDraw.Draw(img)

    lf  = _font(11)
    lf2 = _font(10)

    def panel_box(x0, y0, x1, y1, fill, label, lc="#ffffff"):
        _box(d, [x0, y0, x1, y1], fill=fill, outline="#445566", label=label, label_color=lc, font=lf)

    def dim_label(x, y, text):
        d.text((x, y), text, font=lf2, fill="#778899")

    # Face area
    _box(d, [0, m.bar_h, face_w, m.ticker_y],
         fill="#1a2030", label="FACE VIDEO", label_color="#aabbcc", font=_font(14))

    # Top red bar
    _box(d, [0, 0, total_w, m.bar_h], fill="#d2001e", label="", font=None)
    d.text((4, 0), f"top bar  {m.bar_h}px", font=_font(8), fill="#ffaaaa")

    # Ticker strip
    _box(d, [0, m.ticker_y, total_w, H],
         fill="#12183200", outline="#d2001e",
         label=f"TICKER  {m.ticker_h}px", label_color="#ffddaa", font=_font(11))
    d.rectangle([0, m.ticker_y, total_w, m.ticker_y + 3], fill="#d2001e")

    # Panel BG
    _box(d, [ox, m.bar_h, total_w, m.ticker_y], fill="#08181800", outline="#334")

    # Separator line
    d.rectangle([face_w, m.bar_h, face_w + 2, m.ticker_y], fill="#28324a")


    # ── TOP LAYER (drawn last — on top of face video) ────────────────────────
    # NOW HIRING — right side of ticker
    nh_w = int(m.hiring_font * 6.5)
    panel_box(total_w - nh_w, m.ticker_y, total_w, H, "#f5a623", "NOW HIRING", "#140a00")

    # LOGO — trapezoid bottom-left
    slant = m.logo_h // 2
    trap  = [(0, H - m.logo_h), (m.logo_w, H - m.logo_h), (m.logo_w + slant, H), (0, H)]
    d.polygon(trap, fill="#1a2040", outline="#aabbcc")
    lx = m.logo_w // 2
    ly = H - m.logo_h // 2
    tw_logo = d.textlength("LOGO", font=lf)
    d.text((lx - tw_logo // 2, ly - lf.size // 2), "LOGO", font=lf, fill="#88aacc")

    # TITLE
    panel_box(ox + PAD, y, total_w - PAD, y + title_h,
              "#1e2a40", f"TITLE  2 lines × {m.title_line_h}px  (font {m.title_font}px)", "#eef")
    y += title_h + m.G2

    # Red divider
    d.rectangle([ox + PAD, y, total_w - PAD, y + 2], fill="#d2001e")
    y += 2 + m.G3

    # Info rows — card style
    # Company: full-width card
    panel_box(ox + PAD, y, total_w - PAD, y + m.company_row_h,
              "#121a32", f"COMPANY  {m.company_row_h}px", "#f5a623")
    d.rectangle([ox + PAD, y + 5, ox + PAD + 3, y + m.company_row_h - 5], fill="#f5a623")
    dim_label(total_w - PAD + 2, y, f"{m.company_row_h}px")
    y += m.company_row_h + m.row_gap

    # Location + Experience: side-by-side half-width cards
    card_gap = int(text_w * 0.025)
    half_w   = (total_w - PAD - (ox + PAD) - card_gap) // 2
    for i, (lbl, clr) in enumerate([("LOCATION", "#dde"), ("EXPERIENCE", "#dde")]):
        x0 = ox + PAD + i * (half_w + card_gap)
        panel_box(x0, y, x0 + half_w, y + m.row_h, "#121a32", lbl, clr)
        d.rectangle([x0, y + 5, x0 + 3, y + m.row_h - 5], fill="#f5a623")
    dim_label(total_w - PAD + 2, y, f"{m.row_h}px")
    y += m.row_h + m.G4

    # Thin divider
    d.rectangle([ox + PAD, y, total_w - PAD, y + 1], fill="#23304b")
    y += 1 + m.G5

    # Skills label
    sl_x = ox + (text_w - int(d.textlength("SKILLS", font=lf))) // 2
    panel_box(sl_x - 4, y, sl_x + 60, y + m.label_font + 2,
              "#1c2840", "SKILLS", "#f5a623")
    y += m.label_font + m.G6

    # Skill tags (2 rows)
    for _row in range(2):
        tag_x = ox + PAD
        for i in range(3):
            tw = int(inner * 0.28)
            panel_box(tag_x, y, tag_x + tw, y + m.tag_h,
                      "#19234b", "SKILL", "#d4c07a")
            tag_x += tw + int(text_w * 0.015)
        dim_label(total_w - PAD + 2, y, f"{m.tag_h}px")
        y += m.tag_h + tag_gy

    # Dimension legend below frame
    legend_h = 36
    img2 = Image.new("RGB", (total_w, H + legend_h), "#0d1117")
    img2.paste(img, (0, 0))
    d2  = ImageDraw.Draw(img2)
    lf3 = _font(11)
    items = [
        (f"total: {total_w}×{H}", "#aabbcc"),
        (f"face: {face_w}px  ({face_w*100//total_w}%)", "#5577aa"),
        (f"panel: {text_w}px  ({text_w*100//total_w}%)", "#4488aa"),
        (f"content_h: {m.content_h}px", "#778899"),
        (f"block_h: {block_h}px", "#ff9944" if block_h > m.content_h else "#66cc88"),
        (f"margin: {margin}px", "#aabb88"),
    ]
    x_leg = 8
    for txt, clr in items:
        d2.text((x_leg, H + 4), txt, font=lf3, fill=clr)
        x_leg += int(d2.textlength(txt, font=lf3)) + 24

    img2.save(out_path)
    print(f"Wireframe saved: {out_path}")
    print(f"  Canvas  : {total_w}×{H}")
    print(f"  Face    : {face_w}px ({face_w*100//total_w}%)")
    print(f"  Panel   : {text_w}px ({text_w*100//total_w}%)")
    print(f"  Content : {m.content_h}px tall")
    print(f"  Block   : {block_h}px  ({'OVERFLOW' if block_h > m.content_h else 'fits, margin='+str(margin)+'px'})")


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent.parent / "assets" / "wireframe.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    h = int(sys.argv[1]) if len(sys.argv) > 1 else 720
    render(out, target_height=h)
