"""
Single source of truth for all layout geometry.
Both creator.py and wireframe_html.py import from here.
"""
from dataclasses import dataclass


@dataclass
class L:
    # Frame
    total_w: int
    H: int
    face_w: int
    text_w: int
    inner: int          # text_w - 2*PAD
    PAD: int

    # Chrome
    bar_h: int
    ticker_h: int
    ticker_y: int       # top of ticker strip
    content_h: int      # bar_h → ticker_y

    # Font sizes (nominal px, relative to text_w)
    title_font:   int
    label_font:   int
    value_font:   int
    company_font: int
    badge_font:   int
    hiring_font:  int
    skill_font:   int
    ticker_font:  int

    # Header row
    logo_w:   int
    logo_h:   int
    badge_h:  int
    header_h: int      # max(badge_h, logo_h)

    # Row heights
    title_line_h:  int
    company_row_h: int
    row_h:         int
    row_gap:       int   # gap between company card and loc/exp side-by-side row

    # Tag geometry
    tag_px: int   # horizontal inner padding
    tag_py: int   # vertical inner padding
    tag_gx: int   # gap between tags
    tag_gy: int   # gap between tag rows
    tag_h:  int   # tag pill height

    # Gap rhythm (all derived from content_h)
    G1: int   # top margin for content block
    G2: int   # title   → red divider
    G3: int   # divider → info rows
    G4: int   # info    → thin divider
    G5: int   # divider → skills label
    G6: int   # label   → skill tags

    # ffmpeg ticker
    ticker_text_y: int  # drawtext y position (vertically centred in strip)


def compute(H: int = 720) -> L:
    total_w = int(round(H * 16 / 9 / 2) * 2)
    face_w  = int(round(total_w / 3 / 2) * 2)
    text_w  = total_w - face_w

    PAD      = int(text_w * 0.07)
    inner    = text_w - 2 * PAD

    bar_h    = max(5, int(H * 0.010))
    ticker_h = int(H * 0.075)
    ticker_y = H - ticker_h
    content_h = ticker_y - bar_h

    title_font   = int(text_w * 0.058)
    label_font   = int(text_w * 0.029)
    value_font   = int(text_w * 0.033)
    company_font = int(text_w * 0.033)
    badge_font   = int(text_w * 0.027)
    hiring_font  = int(text_w * 0.025)
    skill_font   = int(text_w * 0.022)
    ticker_font  = int(H * 0.028)

    logo_w   = int(text_w * 0.200)
    logo_h   = int(text_w * 0.100)
    badge_h  = int(text_w * 0.050)
    header_h = max(badge_h, logo_h)

    title_line_h  = int(title_font * 1.18)
    # card rows: stacked label + value with generous vertical padding (all equal height)
    company_row_h = int(content_h * 0.148)
    row_h         = int(content_h * 0.148)
    row_gap       = int(content_h * 0.014)

    tag_px = int(text_w * 0.030)
    tag_py = int(text_w * 0.015)
    tag_gx = int(text_w * 0.018)
    tag_gy = int(text_w * 0.022)
    tag_h  = int(skill_font * 2.10)

    G1 = int(content_h * 0.038)
    G2 = int(content_h * 0.020)
    G3 = int(content_h * 0.028)
    G4 = int(content_h * 0.018)
    G5 = int(content_h * 0.026)
    G6 = int(content_h * 0.038)

    ticker_text_y = ticker_y + (ticker_h - ticker_font) // 2 + 2

    return L(
        total_w=total_w, H=H, face_w=face_w, text_w=text_w,
        inner=inner, PAD=PAD,
        bar_h=bar_h, ticker_h=ticker_h, ticker_y=ticker_y, content_h=content_h,
        title_font=title_font, label_font=label_font, value_font=value_font,
        company_font=company_font, badge_font=badge_font, hiring_font=hiring_font,
        skill_font=skill_font, ticker_font=ticker_font,
        logo_w=logo_w, logo_h=logo_h, badge_h=badge_h, header_h=header_h,
        title_line_h=title_line_h, company_row_h=company_row_h, row_h=row_h, row_gap=row_gap,
        tag_px=tag_px, tag_py=tag_py, tag_gx=tag_gx, tag_gy=tag_gy, tag_h=tag_h,
        G1=G1, G2=G2, G3=G3, G4=G4, G5=G5, G6=G6,
        ticker_text_y=ticker_text_y,
    )
