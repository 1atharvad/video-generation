"""
Generate an HTML/CSS wireframe of the news-panel layout.
Run:  python3 api_v4/video_creator/wireframe_html.py
Output: assets/wireframe.html  (open in any browser)
"""
import sys
from pathlib import Path

# import layout directly to avoid triggering __init__ → creator → tqdm
sys.path.insert(0, str(Path(__file__).resolve().parent))
from layout import compute as compute_layout


def render_html(out_path: Path, target_height: int = 720) -> None:
    m = compute_layout(target_height)

    # unpack for readability
    H            = m.H
    total_w      = m.total_w
    face_w       = m.face_w
    text_w       = m.text_w
    PAD          = m.PAD
    inner        = m.inner
    bar_h        = m.bar_h
    ticker_h     = m.ticker_h
    ticker_y     = m.ticker_y
    content_h    = m.content_h
    logo_w       = m.logo_w
    logo_h       = m.logo_h
    badge_h      = m.badge_h
    header_h     = m.header_h
    title_font   = m.title_font
    label_font   = m.label_font
    value_font   = m.value_font
    company_font = m.company_font
    badge_font   = m.badge_font
    hiring_font  = m.hiring_font
    skill_font   = m.skill_font
    title_line_h = m.title_line_h
    title_h      = 2 * title_line_h      # worst-case 2 lines
    company_row_h = m.company_row_h
    row_h        = m.row_h
    row_gap      = m.row_gap
    tag_h        = m.tag_h
    tag_gy       = m.tag_gy
    tag_gx       = m.tag_gx
    skills_h     = 2 * (tag_h + tag_gy) - tag_gy   # worst-case 2 rows
    G1, G2, G3, G4, G5, G6 = m.G1, m.G2, m.G3, m.G4, m.G5, m.G6

    block_h = (
        title_h + G2 + 2 + G3
        + company_row_h + row_gap + row_h + G4 + 1 + G5
        + label_font + G6
        + skills_h
    )

    min_margin = int(content_h * 0.06)
    margin     = max(min_margin, (content_h - block_h) // 2)
    y          = bar_h + margin
    ox         = face_w

    fits   = block_h <= content_h
    status = f"fits ✓  margin: {margin}px top+bottom" if fits else f"OVERFLOW ✗  by {block_h - content_h}px"

    # scale down for comfortable browser viewing
    scale = min(1.0, 1200 / total_w)
    dw = int(total_w * scale)
    dh = int(H * scale)

    def px(v):  return f"{int(v * scale)}px"
    def raw(v): return int(v * scale)

    # build div helpers
    divs = []

    def div(left, top, width, height, label, cls="zone", tooltip="", extra_style=""):
        l, t, w, h = raw(left), raw(top), raw(width), raw(height)
        fs = max(8, min(12, h // 2))
        tip = tooltip or f"{label}\n{width}×{height}px"
        divs.append(
            f'<div class="{cls}" '
            f'style="left:{l}px;top:{t}px;width:{w}px;height:{h}px;'
            f'font-size:{fs}px;{extra_style}" '
            f'title="{tip}">'
            f'<span>{label}</span>'
            f'</div>'
        )

    def hline(top, left, right, color, thickness=1, label=""):
        l, t, w = raw(left), raw(top), raw(right - left)
        th = max(1, raw(thickness))
        tip = label or f"y={top}px"
        divs.append(
            f'<div class="hline" style="left:{l}px;top:{t}px;width:{w}px;'
            f'height:{th}px;background:{color};" title="{tip}"></div>'
        )

    def gap_arrow(left, top, height, label):
        l, t, h = raw(left), raw(top), raw(height)
        if h < 4:
            return
        divs.append(
            f'<div class="gap" style="left:{l}px;top:{t}px;height:{h}px;" title="{label}">'
            f'<span>{label}</span></div>'
        )

    # ── Frame ─────────────────────────────────────────────────────────────────
    div(0, 0, total_w, H, "", cls="frame", tooltip=f"Frame  {total_w}×{H}px")

    # ── Top bar ───────────────────────────────────────────────────────────────
    div(0, 0, total_w, bar_h, f"top bar  {bar_h}px", cls="zone accent",
        tooltip=f"Red accent bar\nheight: {bar_h}px")

    # ── Face area ─────────────────────────────────────────────────────────────
    div(0, bar_h, face_w, content_h, f"FACE VIDEO\n{face_w}×{content_h}px\n(33% width)",
        cls="zone face", tooltip=f"Face video area\n{face_w}px wide ({face_w*100//total_w}% of frame)\n{content_h}px tall (bar→ticker)")

    # ── Panel background ──────────────────────────────────────────────────────
    div(ox, bar_h, text_w, content_h, "", cls="zone panel-bg",
        tooltip=f"Text panel background\n{text_w}px wide ({text_w*100//total_w}%)\n{content_h}px tall")

    # ── Ticker strip ──────────────────────────────────────────────────────────
    div(0, ticker_y, total_w, ticker_h, f"TICKER  {ticker_h}px tall  ←  scrolling text  →",
        cls="zone ticker", tooltip=f"Ticker strip\ny: {ticker_y}–{H}px\nheight: {ticker_h}px ({ticker_h*100//H}% of H)")
    hline(ticker_y, 0, total_w, "#d2001e", 3, f"ticker red line  y={ticker_y}px")

    # ── Separator ─────────────────────────────────────────────────────────────
    divs.append(
        f'<div class="sep" style="left:{raw(ox)}px;top:{raw(bar_h)}px;'
        f'height:{raw(content_h)}px;" title="Face / panel separator"></div>'
    )

    # ── Content block outline ─────────────────────────────────────────────────
    block_top = bar_h + margin
    div(ox, block_top, text_w, block_h,
        "", cls="zone block-outline",
        tooltip=f"Content block\nheight: {block_h}px\nmargin: {margin}px top+bottom\n{status}")

    cur_y = y   # absolute coords

    # ── LIVE badge + NOW HIRING — top-right (floating) ────────────────────────
    bw_live  = int(text_w * 0.12)
    badge_y_ = bar_h + int(PAD * 0.4)
    div(total_w - PAD - bw_live, badge_y_, bw_live, badge_h,
        "LIVE", cls="zone badge",
        tooltip=f"LIVE badge — top-right corner\n{bw_live}×{badge_h}px\nfont: {badge_font}px bold")
    nh_w  = int(text_w * 0.20)
    nh_y_ = badge_y_ + badge_h + int(PAD * 0.2)
    # ── NOW HIRING — left of ticker strip, full ticker height ────────────────
    nh_approx_w = int(hiring_font * 6.5)
    div(total_w - nh_approx_w, ticker_y, nh_approx_w, ticker_h,
        "NOW HIRING", cls="zone now-hiring",
        tooltip=f"NOW HIRING label — right of ticker\nfull ticker height: {ticker_h}px\namber background, dark text\ntop layer (above face video)\ncarousel scrolls from behind it")

    # ── LOGO — trapezoid bottom-left, top layer ───────────────────────────────
    slant_raw = raw(logo_h // 2)
    lw_raw    = raw(logo_w)
    lh_raw    = raw(logo_h)
    div(0, H - logo_h, logo_w + logo_h // 2, logo_h,
        "LOGO", cls="zone logo",
        tooltip=f"Company logo — trapezoid bottom-left\n{logo_w}×{logo_h}px + {logo_h//2}px slant\ntop layer (on top of face video)",
        extra_style=f"clip-path:polygon(0 0,{lw_raw}px 0,{lw_raw+slant_raw}px {lh_raw}px,0 {lh_raw}px);")

    # ── Title ─────────────────────────────────────────────────────────────────
    div(ox + PAD, cur_y, inner, title_h,
        f"POSITION TITLE  (2 lines × {title_line_h}px)", cls="zone title",
        tooltip=f"Job title — up to 2 lines\nfont: {title_font}px bold\nline-height: {title_line_h}px\ntotal: {title_h}px")

    gap_arrow(ox + PAD // 3, cur_y + title_h, G2, f"G2 {G2}px")
    cur_y += title_h + G2

    # ── Red divider ───────────────────────────────────────────────────────────
    hline(cur_y, ox + PAD, ox + text_w - PAD, "#d2001e", 2, f"red divider  y={cur_y}px")
    gap_arrow(ox + PAD // 3, cur_y + 2, G3, f"G3 {G3}px")
    cur_y += 2 + G3

    # ── Info rows (card style) ────────────────────────────────────────────────
    # Company — full-width card
    div(ox + PAD, cur_y, inner, company_row_h,
        f"COMPANY  (font {company_font}px bold)  ·  {company_row_h}px",
        cls="zone info-card company",
        tooltip=f"Company card\nfull width: {inner}px\nheight: {company_row_h}px\nstacked label + bold value")
    cur_y += company_row_h

    gap_arrow(ox + PAD // 3, cur_y, row_gap, f"row_gap {row_gap}px")
    cur_y += row_gap

    # Location + Experience — side by side
    card_gap_px = int(text_w * 0.025)
    half_w      = (inner - card_gap_px) // 2
    div(ox + PAD, cur_y, half_w, row_h,
        f"LOCATION  (font {value_font}px)  ·  {row_h}px",
        cls="zone info-card",
        tooltip=f"Location card\nwidth: {half_w}px\nheight: {row_h}px")
    div(ox + PAD + half_w + card_gap_px, cur_y, half_w, row_h,
        f"EXPERIENCE  (font {value_font}px)  ·  {row_h}px",
        cls="zone info-card",
        tooltip=f"Experience card\nwidth: {half_w}px\nheight: {row_h}px")
    cur_y += row_h

    gap_arrow(ox + PAD // 3, cur_y, G4, f"G4 {G4}px")
    cur_y += G4

    # ── Thin divider ──────────────────────────────────────────────────────────
    hline(cur_y, ox + PAD, ox + text_w - PAD, "#2a3a5a", 1, f"thin divider  y={cur_y}px")
    gap_arrow(ox + PAD // 3, cur_y + 1, G5, f"G5 {G5}px")
    cur_y += 1 + G5

    # ── Skills label ──────────────────────────────────────────────────────────
    sl_w = 80
    sl_x = ox + (text_w - sl_w) // 2
    div(sl_x, cur_y, sl_w, label_font,
        "SKILLS", cls="zone skills-label",
        tooltip=f"SKILLS heading\nfont: {label_font}px bold amber\ncentered")

    gap_arrow(ox + PAD // 3, cur_y + label_font, G6, f"G6 {G6}px")
    cur_y += label_font + G6

    # ── Skill tags ────────────────────────────────────────────────────────────
    tag_w = (inner - 2 * tag_gx) // 3
    for _row in range(2):
        tx = ox + PAD
        for i in range(3):
            div(tx, cur_y, tag_w, tag_h,
                f"skill {_row*3+i+1}", cls="zone tag",
                tooltip=f"Skill tag\nfont: {skill_font}px\n{tag_w}×{tag_h}px\npadding: {int(text_w*0.020)}px H, {int(text_w*0.013)}px V\nrow gap: {tag_gy}px")
            tx += tag_w + tag_gx
        cur_y += tag_h + tag_gy

    # ── Ruler: right edge showing row heights ─────────────────────────────────
    ruler_x = ox + text_w + 2
    ruler_items = [
        (bar_h,        bar_h,                "bar",       "#d2001e"),
        (bar_h+margin, margin,               "margin",    "#556677"),
        (y,            header_h,             f"header {header_h}px", "#445588"),
        (y+header_h+G1, title_h,             f"title {title_h}px",   "#334477"),
        (y+header_h+G1+title_h+G2+2+G3, company_row_h, f"company {company_row_h}px", "#d2001e"),
        (y+header_h+G1+title_h+G2+2+G3+company_row_h+row_gap, row_h, f"loc+exp {row_h}px", "#445566"),
    ]

    # ── Assemble HTML ─────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Layout Wireframe — {total_w}×{H}px</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #111; font-family: 'SF Mono', 'Fira Code', monospace;
          display: flex; flex-direction: column; align-items: flex-start;
          padding: 24px; gap: 16px; color: #ccc; }}
  h1   {{ font-size: 14px; color: #aaa; font-weight: 400; }}
  .status {{ font-size: 12px; padding: 4px 10px; border-radius: 4px;
             background: {'#1a3a1a; color: #6f6' if fits else '#3a1a1a; color: #f66'}; }}
  .canvas  {{ position: relative; width: {dw}px; height: {dh}px;
              border: 1px solid #334; flex-shrink: 0; }}
  .frame   {{ position: absolute; inset: 0; background: #080c18; }}
  .zone    {{ position: absolute; display: flex; align-items: center;
              justify-content: center; text-align: center;
              white-space: pre-line; cursor: default;
              border: 1px solid #2a3a5a; color: #889; font-size: 10px;
              transition: outline 0.1s; }}
  .zone:hover {{ outline: 2px solid #88aaff; z-index: 99;
                 color: #fff !important; }}
  .zone span  {{ pointer-events: none; padding: 2px 4px; }}
  .face       {{ background: rgba(20,30,50,0.9); color: #5577aa; border-color: #2a3a6a; }}
  .panel-bg   {{ background: rgba(8,12,30,0.4); border-color: #1e2a4a; }}
  .accent     {{ background: #d2001e; color: #fff; border-color: #ff2040; font-size: 9px; }}
  .ticker     {{ background: rgba(18,24,50,0.9); color: #f5a623;
                 border-top: 2px solid #d2001e; border-bottom: none;
                 border-left: none; border-right: none; }}
  .block-outline {{ background: transparent; border: 1px dashed #3a4a6a;
                    pointer-events: none; }}
  .header-row    {{ background: transparent; border: 1px dashed #2a3a5a; }}
  .badge      {{ background: #d2001e; color: #fff; border-radius: 3px;
                 font-weight: bold; border-color: #ff2040; }}
  .now-hiring {{ background: rgba(20,28,50,0.8); color: #f5a623; border-color: #3a4a2a; }}
  .logo       {{ background: rgba(224,205,172,0.85); color: #7a6040; border-color: #b8955a;
                 border-style: solid; }}
  .title      {{ background: rgba(25,35,65,0.8); color: #dde; border-color: #3a4a7a;
                 font-size: 11px; font-weight: bold; }}
  .info-card  {{ background: rgba(18,26,50,0.95); color: #ccd; border-color: #1e2d50;
                 border-left: 3px solid #f5a623 !important; font-size: 10px; }}
  .info-card.company {{ color: #fff; font-weight: bold; background: rgba(18,26,50,0.98); }}
  .skills-label {{ background: transparent; color: #f5a623; border: none;
                   font-weight: bold; }}
  .tag        {{ background: rgba(22,30,70,0.9); color: #d4c07a; border-color: #f5a623;
                 border-radius: 3px; }}
  .hline      {{ position: absolute; pointer-events: none; z-index: 10; }}
  .sep        {{ position: absolute; width: 2px; background: #28324a; pointer-events: none; }}
  .gap        {{ position: absolute; width: 6px; display: flex; align-items: center;
                 justify-content: center; border-left: 1px dashed #334; border-right: 1px dashed #334;
                 z-index: 20; cursor: default; }}
  .gap span   {{ writing-mode: vertical-rl; font-size: 8px; color: #556;
                 transform: rotate(180deg); white-space: nowrap; }}

  .legend {{ display: flex; flex-wrap: wrap; gap: 8px 24px; font-size: 11px;
             max-width: {dw}px; }}
  .legend .item {{ display: flex; align-items: center; gap: 6px; }}
  .legend .swatch {{ width: 12px; height: 12px; border-radius: 2px; flex-shrink: 0; }}
  .specs  {{ font-size: 11px; color: #667; display: grid;
             grid-template-columns: repeat(3, 1fr); gap: 4px 32px;
             max-width: {dw}px; }}
  .specs .kv {{ display: flex; gap: 8px; }}
  .specs .k  {{ color: #556; }}
  .specs .v  {{ color: #9ab; }}
</style>
</head>
<body>

<h1>Layout Wireframe — {total_w}×{H}px  (displayed at {int(scale*100)}%)</h1>
<div class="status">{status}</div>

<div class="canvas">
{''.join(divs)}
</div>

<div class="legend">
  <div class="item"><div class="swatch" style="background:#d2001e"></div>Accent / LIVE badge</div>
  <div class="item"><div class="swatch" style="background:#1a3050"></div>Face video area</div>
  <div class="item"><div class="swatch" style="background:#19234b"></div>Skill tags</div>
  <div class="item"><div class="swatch" style="background:#12183299;border:1px solid #d2001e"></div>Ticker strip</div>
  <div class="item"><div class="swatch" style="background:transparent;border:1px dashed #3a4a6a"></div>Content block (dashed)</div>
  <div class="item"><div class="swatch" style="background:transparent;border:1px dashed #334466"></div>Logo (optional)</div>
</div>

<div class="specs">
  <div class="kv"><span class="k">canvas</span><span class="v">{total_w} × {H} px</span></div>
  <div class="kv"><span class="k">face_w</span><span class="v">{face_w} px  ({face_w*100//total_w}%)</span></div>
  <div class="kv"><span class="k">text_w</span><span class="v">{text_w} px  ({text_w*100//total_w}%)</span></div>
  <div class="kv"><span class="k">PAD</span><span class="v">{PAD} px</span></div>
  <div class="kv"><span class="k">bar_h</span><span class="v">{bar_h} px</span></div>
  <div class="kv"><span class="k">ticker_h</span><span class="v">{ticker_h} px</span></div>
  <div class="kv"><span class="k">content_h</span><span class="v">{content_h} px</span></div>
  <div class="kv"><span class="k">block_h</span><span class="v">{block_h} px</span></div>
  <div class="kv"><span class="k">margin</span><span class="v">{margin} px</span></div>
  <div class="kv"><span class="k">title_font</span><span class="v">{title_font} px bold</span></div>
  <div class="kv"><span class="k">company_font</span><span class="v">{company_font} px bold</span></div>
  <div class="kv"><span class="k">value_font</span><span class="v">{value_font} px</span></div>
  <div class="kv"><span class="k">G1–G6</span><span class="v">{G1} / {G2} / {G3} / {G4} / {G5} / {G6} px</span></div>
  <div class="kv"><span class="k">tag</span><span class="v">{tag_h}px tall  {tag_gx}px gap-x  {tag_gy}px gap-y</span></div>
  <div class="kv"><span class="k">scale</span><span class="v">{int(scale*100)}% ({dw}×{dh} px)</span></div>
</div>

<p style="font-size:10px;color:#445;margin-top:8px">Hover any zone for exact dimensions. Regenerate: <code>python3 api_v4/video_creator/wireframe_html.py [height]</code></p>
</body>
</html>"""

    out_path.write_text(html, encoding="utf-8")
    print(f"Wireframe HTML: {out_path}")
    print(f"  open {out_path}")


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "assets" / "wireframe.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    h = int(sys.argv[1]) if len(sys.argv) > 1 else 720
    render_html(out, target_height=h)
