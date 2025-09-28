#!/usr/bin/env python3
"""
Google Sheet -> Classement sur image (547x607)
- Team : aligné à GAUCHE dans sa colonne
- Games / Win / Loose : CENTRÉS dans leurs colonnes (72 px chacune)
- Ajustement auto de la taille de police pour tenir en largeur ET hauteur
- Vertical: 103 px de marge, puis (3 px ligne blanche + 80 px bande) x 6
- Marges texte dans chaque bande: 30 px haut + 30 px bas
"""

import os
from pathlib import Path
from typing import Tuple, Optional, List

import gspread
from PIL import Image, ImageDraw, ImageFont, ImageColor

# =================== CONFIG ===================
WORKSHEET_NAME = os.environ.get("WORKSHEET_NAME", "Feuille 1")
BASE_IMAGE_PATH = os.environ.get("BASE_IMAGE_PATH", "classement.png")
OUTPUT_PATH     = os.environ.get("OUTPUT_PATH", "render.png")

# Police et couleur
FONT_PATH  = os.environ.get("FONT_PATH", "Oswald-Medium.ttf")
TEXT_COLOR = os.environ.get("TEXT_COLOR", "#ffffff")
SHADOW     = os.environ.get("SHADOW", "1") == "1"

# Ton Google Sheet
SHEET_URL_DEFAULT = "https://docs.google.com/spreadsheets/d/1ESiWCUnd0ndupA6WocooLcbB6qqf_gx4jShZ0K6Ef7Y"

# Lignes à rendre
ROW_COUNT = int(os.environ.get("ROW_COUNT", "6"))

# ----- Colonnes (en % de la largeur de l'image 547 px) -----
TEAM_COL_L  = 0/547
TEAM_COL_R  = 280/547

GAMES_COL_L = 280/547   # [280, 352]
GAMES_COL_R = 352/547
WIN_COL_L   = 352/547   # [352, 424]
WIN_COL_R   = 424/547
LOOSE_COL_L = 424/547   # [424, 496]
LOOSE_COL_R = 496/547

# ----- Vertical (en PIXELS) -----
PRE_MARGIN_TOP_PX = 103
LINE_THICKNESS_PX = 3
BAND_HEIGHT_PX    = 80
MARGIN_TOP_PX     = 30
MARGIN_BOTTOM_PX  = 30
START_Y_PX        = PRE_MARGIN_TOP_PX + LINE_THICKNESS_PX  # 106

# Taille police
FONT_SIZE_MAX = int(os.environ.get("FONT_SIZE_MAX", "42"))
FONT_SIZE_MIN = int(os.environ.get("FONT_SIZE_MIN", "22"))

# Padding gauche pour Team
TEAM_LEFT_PADDING_PX = int(os.environ.get("TEAM_LEFT_PADDING_PX", "111"))

# Micro-décalages horizontaux (si besoin de corriger de 1–2 px)
GAMES_NUDGE_PX = int(os.environ.get("GAMES_NUDGE_PX", "-8"))
WIN_NUDGE_PX   = int(os.environ.get("WIN_NUDGE_PX", "2"))
LOOSE_NUDGE_PX = int(os.environ.get("LOOSE_NUDGE_PX", "6"))

# Debug (dessine repères)
DEBUG = os.environ.get("DEBUG", "0") == "1"

# Service account
SERVICE_ACCOUNT_FILE = (
    os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    or str(Path(__file__).with_name("service-account.json"))
)
# ===============================================


def parse_color(v: Optional[str]):
    try:
        return ImageColor.getrgb(v or "#ffffff")
    except Exception:
        return (255, 255, 255)


def try_load_font(paths: List[str], size: int) -> ImageFont.FreeTypeFont:
    for p in paths:
        if p and Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def load_font(size: int) -> ImageFont.FreeTypeFont:
    return try_load_font([FONT_PATH], size)


def fit_text_to_box(draw: ImageDraw.ImageDraw, text: str, box: Tuple[int, int, int, int]) -> ImageFont.FreeTypeFont:
    """Réduit la taille jusqu'à tenir en largeur ET hauteur de la box."""
    x0, y0, x1, y1 = box
    max_w = max(10, x1 - x0 - 4)
    max_h = max(6,  y1 - y0 - 4)
    size = FONT_SIZE_MAX
    while size >= FONT_SIZE_MIN:
        font = load_font(size)
        # Mesure bbox
        bx1, by1, bx2, by2 = draw.textbbox((0, 0), text, font=font)
        w = bx2 - bx1
        h = by2 - by1
        if w <= max_w and h <= max_h:
            return font
        size -= 1
    return load_font(FONT_SIZE_MIN)


def draw_shadowed_text(draw: ImageDraw.ImageDraw, xy, text: str, font, fill):
    if SHADOW:
        x, y = xy
        shadow_color = (0, 0, 0, 180)
        for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
            draw.text((x+dx, y+dy), text, font=font, fill=shadow_color)
    draw.text(xy, text, font=font, fill=fill)


def draw_in_box_center(draw, text: str, box: Tuple[int, int, int, int], fill, nudge_px: int = 0):
    """Centre horizontalement et verticalement dans la box (mesure bbox)."""
    x0, y0, x1, y1 = box
    font = fit_text_to_box(draw, text, box)

    bx1, by1, bx2, by2 = draw.textbbox((0, 0), text, font=font)
    w = bx2 - bx1
    h = by2 - by1

    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2

    x = cx - w / 2 + nudge_px
    y = cy - h / 2

    draw_shadowed_text(draw, (x, y), text, font, fill)


def draw_in_box_left(draw, text: str, box: Tuple[int, int, int, int], fill, padding_left: int = 0):
    """Aligne à gauche avec padding."""
    x0, y0, x1, y1 = box
    adj_box = (x0 + padding_left, y0, x1, y1)
    font = fit_text_to_box(draw, text, adj_box)
    bx1, by1, bx2, by2 = draw.textbbox((0, 0), text, font=font)
    h = by2 - by1
    x = adj_box[0]
    y = y0 + (y1 - y0 - h) / 2
    draw_shadowed_text(draw, (x, y), text, font, fill)


def open_worksheet(sheet_url: str):
    key_path = Path(SERVICE_ACCOUNT_FILE)
    if not key_path.exists():
        raise SystemExit(f"❌ Clé JSON introuvable : {key_path}")
    gc = gspread.service_account(filename=str(key_path))
    sh = gc.open_by_url(sheet_url)
    try:
        return sh.worksheet(WORKSHEET_NAME)
    except Exception:
        return sh.sheet1


def get_rows(sheet_url: str, row_count: int):
    ws = open_worksheet(sheet_url)
    rows = ws.get_all_records()
    rows = [r for r in rows if str(r.get("Classement", "")).strip() != ""]
    try:
        rows.sort(key=lambda r: int(r.get("Classement", 999999)))
    except Exception:
        pass
    return rows[:row_count]


def pct_to_px(p: float, total: int) -> int:
    return int(round(p * total))


def main():
    sheet_url = os.environ.get("SHEET_URL") or SHEET_URL_DEFAULT
    if not sheet_url or "docs.google.com" not in sheet_url:
        raise SystemExit("❌ SHEET_URL manquante ou invalide.")

    img_path = Path(BASE_IMAGE_PATH)
    if not img_path.exists():
        raise SystemExit(f"❌ Image modèle introuvable : {img_path.resolve()}")

    im = Image.open(img_path).convert("RGBA")
    W, H = im.size
    draw = ImageDraw.Draw(im)
    color = parse_color(TEXT_COLOR)

    def col_box(l_pct: float, r_pct: float, row_index: int) -> Tuple[int, int, int, int]:
        x0 = pct_to_px(l_pct, W)
        x1 = pct_to_px(r_pct, W)
        band_top = (95 + 3) + row_index * (80 + 3)
        y0 = band_top + 30
        y1 = band_top + 80 - 30
        return (x0, y0, x1, y1)

    rows = get_rows(sheet_url, ROW_COUNT)
    if not rows:
        print("⚠️ Aucune donnée. J'enregistre l'image telle quelle.")
        im.convert("RGB").save(OUTPUT_PATH)
        return

    if DEBUG:
        guide = ImageDraw.Draw(im)
        for l, r in [(TEAM_COL_L, TEAM_COL_R), (GAMES_COL_L, GAMES_COL_R),
                     (WIN_COL_L, WIN_COL_R), (LOOSE_COL_L, LOOSE_COL_R)]:
            x0 = pct_to_px(l, W); x1 = pct_to_px(r, W)
            guide.rectangle([x0, 0, x1, H], outline=(0, 255, 0, 255), width=2)
        for i in range(ROW_COUNT):
            band_top = (103 + 3) + i * (80 + 3)
            guide.rectangle([0, band_top, W, band_top + 80], outline=(255, 0, 0, 255), width=1)
            guide.rectangle([0, band_top + 30, W, band_top + 80 - 30],
                            outline=(255, 255, 0, 255), width=1)

    for i, r in enumerate(rows):
        team  = str(r.get("Team", "")).strip()
        games = str(r.get("Games", "")).strip()
        win   = str(r.get("Win", "")).strip()
        loose = str(r.get("Loose", "")).strip()

        draw_in_box_left(draw, team, col_box(TEAM_COL_L, TEAM_COL_R, i), color, padding_left=TEAM_LEFT_PADDING_PX)
        draw_in_box_center(draw, games, col_box(GAMES_COL_L, GAMES_COL_R, i), color, nudge_px=GAMES_NUDGE_PX)
        draw_in_box_center(draw, win,   col_box(WIN_COL_L,   WIN_COL_R,   i), color, nudge_px=WIN_NUDGE_PX)
        draw_in_box_center(draw, loose, col_box(LOOSE_COL_L, LOOSE_COL_R, i), color, nudge_px=LOOSE_NUDGE_PX)

    im.convert("RGB").save(OUTPUT_PATH)
    print(f"✅ Image générée : {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
