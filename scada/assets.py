"""
ICSSI SCADA — P&ID Equipment Image Generator v3.0
Membuat gambar equipment P&ID menggunakan Pillow (ISA 5.1 style).
Semua gambar di-generate secara programatik, tidak ada file eksternal.
Retro enterprise palette — zero pure black.
"""

from PIL import Image, ImageDraw, ImageFont
import math
import io
import tkinter as tk


def _to_photoimage(img: Image.Image) -> tk.PhotoImage:
    """Konversi PIL Image ke tk.PhotoImage via PNG bytes."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return tk.PhotoImage(data=buf.read())


def _rgba(img_size, bg=(208, 211, 212, 0)):
    return Image.new("RGBA", img_size, bg)


# ── Warna P&ID ────────────────────────────────────────────────────────────────
C_PIPE_W  = (21,  67, 96)     # Water pipe — dark navy blue
C_PIPE_C  = (108, 52, 131)    # Chemical pipe — purple
C_PIPE_T  = (20,  90,  50)    # Treated pipe — forest green
C_EQUIP   = (197, 201, 204)   # Equipment body — steel gray
C_EQUIP_D = (127, 140, 141)   # Equipment shadow — mid gray
C_EQUIP_L = (240, 243, 244)   # Equipment highlight — near white
C_RUN_OK  = (30,  132,  73)   # Running/OK — forest green
C_FAULT   = (192,  57,  43)   # Fault — deep red
C_WARN    = (202, 111,  30)   # Warning — amber
C_TEXT    = (26,   37,  47)   # Label text — deep navy (not black)
C_WHITE   = (253, 254, 254)   # Off-white
C_BLACK   = (26,   37,  47)   # "Black" = deep navy
C_NAVY    = (26,   58,  92)   # Navy blue border
C_BLUE_D  = (26,   58,  92)   # Dark blue border (same as navy)
C_NAVY_DK = (28,  40,  64)    # Darkest navy (alarm bg)
C_STEEL   = (36,  113, 163)   # Steel blue accent


def _draw_bevel_rect(draw, x0, y0, x1, y1, depth=2, fill=C_EQUIP):
    """3-D raised rectangle."""
    draw.rectangle([x0, y0, x1, y1], fill=fill)
    for i in range(depth):
        draw.line([x0+i, y0+i, x1-i, y0+i], fill=C_EQUIP_L)
        draw.line([x0+i, y0+i, x0+i, y1-i], fill=C_EQUIP_L)
    for i in range(depth):
        draw.line([x0+i, y1-i, x1-i, y1-i], fill=C_EQUIP_D)
        draw.line([x1-i, y0+i, x1-i, y1-i], fill=C_EQUIP_D)


def _try_font(size: int, bold: bool = False):
    faces = ["arialbd.ttf" if bold else "arial.ttf",
             "Arial Bold.ttf" if bold else "Arial.ttf",
             "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for f in faces:
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            pass
    return ImageFont.load_default()


# ── Equipment Symbols ─────────────────────────────────────────────────────────

def make_pump(size=64, running=True, color=None) -> Image.Image:
    """Centrifugal pump — ISA 5.1: circle with impeller triangle."""
    img = _rgba((size, size))
    d = ImageDraw.Draw(img)
    cx, cy, r = size // 2, size // 2, size // 2 - 3

    fill_c = C_RUN_OK if running else C_FAULT

    # Body shell — 3-layer for depth
    d.ellipse([cx-r,   cy-r,   cx+r,   cy+r],   fill=C_EQUIP_D)
    d.ellipse([cx-r+2, cy-r+2, cx+r-2, cy+r-2], fill=C_EQUIP)
    d.ellipse([cx-r+3, cy-r+3, cx+r-4, cy+r-4], fill=C_EQUIP_L)
    d.ellipse([cx-r,   cy-r,   cx+r,   cy+r],   outline=C_BLUE_D, width=2)

    # Impeller (ISA: triangle pointing right = discharge direction)
    tri = int(r * 0.54)
    pts = [
        (cx + tri,                cy),
        (cx - int(tri * 0.55),    cy - int(tri * 0.68)),
        (cx - int(tri * 0.55),    cy + int(tri * 0.68)),
    ]
    d.polygon(pts, fill=fill_c, outline=C_NAVY)

    # Status LED top-right
    dr = max(4, size // 10)
    d.ellipse([size-dr*2-2, 2, size-3, dr*2+2],
              fill=fill_c, outline=C_NAVY)

    return img


def make_valve(size=40, open_pct=100) -> Image.Image:
    """Gate valve — ISA 5.1: two opposing triangles meeting at tip."""
    img = _rgba((size, size))
    d = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    half = size // 2 - 3
    fill_c = C_EQUIP_L if open_pct > 50 else C_FAULT

    d.polygon([(cx-half, cy-half), (cx-half, cy+half), (cx, cy)],
              fill=fill_c, outline=C_NAVY)
    d.polygon([(cx+half, cy-half), (cx+half, cy+half), (cx, cy)],
              fill=fill_c, outline=C_NAVY)
    # Stem + handwheel
    d.line([(cx, cy-half), (cx, cy-half-7)], fill=C_NAVY, width=2)
    d.ellipse([cx-5, cy-half-14, cx+5, cy-half-5], fill=C_EQUIP, outline=C_NAVY)

    return img


def make_tank(w=80, h=100, level_pct=80, label="", color_scheme="water") -> Image.Image:
    """Process vessel / tank with liquid level indicator."""
    img = _rgba((w, h))
    d = ImageDraw.Draw(img)

    wall, top_h = 4, 14

    # Body rectangle
    body = [wall, top_h, w-wall, h-wall]
    d.rectangle(body, fill=C_EQUIP_L, outline=C_BLUE_D, width=2)

    # 3-D side highlights
    d.line([wall+2, top_h+2, wall+2, h-wall-2], fill=C_EQUIP_L, width=2)
    d.line([w-wall-2, top_h+2, w-wall-2, h-wall-2], fill=C_EQUIP_D, width=2)

    # Dome top
    d.ellipse([wall, 2, w-wall, top_h*2], fill=C_EQUIP, outline=C_BLUE_D, width=2)

    # Liquid fill
    fill_h = int((h - wall - top_h) * level_pct / 100.0)
    if fill_h > 0:
        scheme_colors = {
            "water": (*C_PIPE_W, 180),
            "chem":  (*C_PIPE_C, 180),
            "treated": (*C_PIPE_T, 180),
        }
        fill_alpha = scheme_colors.get(color_scheme, (*C_PIPE_W, 180))
        fill_y0 = h - wall - fill_h
        fill_img = Image.new("RGBA", (w - wall*2 - 2, fill_h), fill_alpha)
        img.paste(fill_img, (wall+1, fill_y0), fill_img)

    # Level line
    if 5 < level_pct < 95:
        ly = h - wall - int((h - wall - top_h) * level_pct / 100.0)
        d.line([wall+2, ly, w-wall-2, ly], fill=(*C_WARN, 200), width=1)

    # Label
    if label:
        font = _try_font(9)
        bbox = d.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        tx = (w - tw) // 2
        d.text((tx, h//2 + 4), label, fill=C_TEXT, font=font)

    return img


def make_filter_unit(w=60, h=80) -> Image.Image:
    """Sand filter — rectangle with parallel horizontal media lines."""
    img = _rgba((w, h))
    d = ImageDraw.Draw(img)

    wall = 3
    _draw_bevel_rect(d, wall, wall, w-wall, h-wall, depth=3, fill=C_EQUIP)

    # Filter media lines (dashed look via shorter lines)
    for i in range(5):
        y = wall + 10 + i * ((h - wall*2 - 20) // 5)
        d.line([wall+6, y, w-wall-6, y], fill=C_EQUIP_D, width=2)

    # Inlet/outlet nozzles
    d.line([0, h//3, wall+2, h//3], fill=(*C_PIPE_W, 255), width=4)
    d.line([w-wall-2, h*2//3, w, h*2//3], fill=(*C_PIPE_T, 255), width=4)

    return img


def make_flowmeter(size=36) -> Image.Image:
    """Flow transmitter — ISA diamond shape with FM tag."""
    img = _rgba((size, size))
    d = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    r = size // 2 - 3

    # Diamond with 3-D fill
    pts = [(cx, cy-r), (cx+r, cy), (cx, cy+r), (cx-r, cy)]
    d.polygon(pts, fill=C_EQUIP_L, outline=C_BLUE_D, width=2)
    # Inner shadow for depth
    inner = [(cx, cy-r+4), (cx+r-4, cy), (cx, cy+r-4), (cx-r+4, cy)]
    d.polygon(inner, fill=C_EQUIP, outline=None)

    font = _try_font(8)
    d.text((cx-7, cy-5), "FM", fill=C_STEEL, font=font)
    return img


def make_chemical_tank(w=50, h=65, level_pct=80, label="NaOH") -> Image.Image:
    """Chemical storage tank — cylindrical."""
    return make_tank(w, h, level_pct, label=label, color_scheme="chem")


def make_dosing_pump(size=48, running=True) -> Image.Image:
    """Dosing / metering pump — circle with positive-displacement tick marks."""
    img = _rgba((size, size))
    d = ImageDraw.Draw(img)
    cx, cy, r = size // 2, size // 2, size // 2 - 3
    fill_c = C_RUN_OK if running else C_FAULT

    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=C_EQUIP_D)
    d.ellipse([cx-r+2, cy-r+2, cx+r-2, cy+r-2], fill=C_EQUIP)
    d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=C_BLUE_D, width=2)

    # Piston symbol inside
    tri = int(r * 0.48)
    pts = [(cx+tri, cy), (cx-tri, cy-tri), (cx-tri, cy+tri)]
    d.polygon(pts, fill=fill_c, outline=C_NAVY)

    # 4 tick marks on circumference (PD pump indicator)
    for deg in [0, 90, 180, 270]:
        a = math.radians(deg)
        x1 = int(cx + (r-2) * math.cos(a))
        y1 = int(cy + (r-2) * math.sin(a))
        x2 = int(cx + (r+3) * math.cos(a))
        y2 = int(cy + (r+3) * math.sin(a))
        d.line([(x1, y1), (x2, y2)], fill=C_NAVY, width=2)

    return img


def make_ph_sensor(size=32) -> Image.Image:
    """pH analyzer — ISA instrument circle, light blue fill."""
    img = _rgba((size, size))
    d = ImageDraw.Draw(img)
    cx, cy, r = size // 2, size // 2, size // 2 - 2

    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(180, 216, 243), outline=C_BLUE_D, width=2)
    font = _try_font(9, bold=True)
    d.text((cx-8, cy-6), "pH", fill=(21, 67, 96), font=font)
    return img


def make_level_sensor(size=32) -> Image.Image:
    """Level transmitter — ISA instrument circle, pale green fill."""
    img = _rgba((size, size))
    d = ImageDraw.Draw(img)
    cx, cy, r = size // 2, size // 2, size // 2 - 2

    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(180, 235, 200), outline=(20, 90, 50), width=2)
    font = _try_font(8, bold=True)
    d.text((cx-7, cy-5), "LT", fill=(20, 90, 50), font=font)
    return img


def make_alarm_tile(w=110, h=36, alarm_name="ALARM",
                    active=False, blink=False) -> Image.Image:
    """Classic SCADA annunciator tile — dark navy panel (NOT black)."""
    img = Image.new("RGBA", (w, h), (*C_NAVY_DK, 255))
    d = ImageDraw.Draw(img)

    if active and blink:
        bg = (176, 58, 46, 255)      # deep red blink
        fg = (253, 254, 254, 255)
    elif active:
        bg = (192, 57, 43, 255)      # alarm red steady
        fg = (253, 220, 200, 255)
    else:
        bg = (26, 92, 42, 255)       # normal — dark green
        fg = (169, 223, 191, 255)

    d.rectangle([1, 1, w-2, h-2], fill=bg)

    # Bevel
    hi = tuple(min(255, c + 40) for c in bg[:3]) + (255,)
    sh = tuple(max(0,   c - 40) for c in bg[:3]) + (255,)
    d.line([1, 1, w-2, 1], fill=hi)
    d.line([1, 1, 1, h-2], fill=hi)
    d.line([1, h-2, w-2, h-2], fill=sh)
    d.line([w-2, 1, w-2, h-2], fill=sh)

    font = _try_font(8)

    bbox = d.textbbox((0, 0), alarm_name, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = max(2, (w - tw) // 2)
    ty = max(1, (h - th) // 2 - 1)
    d.text((tx, ty), alarm_name, fill=fg, font=font)

    return img


def make_icssi_emblem(size=64) -> Image.Image:
    """
    ICSSI hexagonal badge / emblem for About dialog and header.
    Navy hexagon with steel blue border, white ICSSI text.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    r_out = size // 2 - 2
    r_in  = int(r_out * 0.78)

    # Hexagon points (flat-top orientation)
    def hex_pts(r, angle_offset=0):
        pts = []
        for i in range(6):
            a = math.radians(60 * i + angle_offset)
            pts.append((int(cx + r * math.cos(a)), int(cy + r * math.sin(a))))
        return pts

    outer = hex_pts(r_out, 30)
    inner = hex_pts(r_in,  30)

    # Shadow
    shadow = [(x+2, y+2) for x, y in outer]
    d.polygon(shadow, fill=(26, 37, 47, 120))

    # Outer hex — steel blue border
    d.polygon(outer, fill=(36, 113, 163), outline=(21, 67, 96), width=2)

    # Inner hex — deep navy fill
    d.polygon(inner, fill=(26, 58, 92), outline=(36, 113, 163), width=1)

    # "ICSSI" text
    font_big  = _try_font(max(9, size // 7), bold=True)
    font_small = _try_font(max(6, size // 11))

    label = "ICSSI"
    bb = d.textbbox((0, 0), label, font=font_big)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    d.text((cx - tw//2, cy - th//2 - 2), label,
           fill=(240, 248, 255), font=font_big)

    sub = "ICS-ID"
    bb2 = d.textbbox((0, 0), sub, font=font_small)
    sw = bb2[2] - bb2[0]
    d.text((cx - sw//2, cy + th//2 + 1), sub,
           fill=(127, 179, 211), font=font_small)

    return img


# ── Preload cache ─────────────────────────────────────────────────────────────
_CACHE: dict = {}

def get(key: str, **kw) -> tk.PhotoImage:
    cache_key = key + str(sorted(kw.items()))
    if cache_key not in _CACHE:
        makers = {
            "pump":          lambda: make_pump(**kw),
            "valve":         lambda: make_valve(**kw),
            "tank":          lambda: make_tank(**kw),
            "filter":        lambda: make_filter_unit(**kw),
            "flowmeter":     lambda: make_flowmeter(**kw),
            "chem_tank":     lambda: make_chemical_tank(**kw),
            "dosing_pump":   lambda: make_dosing_pump(**kw),
            "ph_sensor":     lambda: make_ph_sensor(**kw),
            "level_sensor":  lambda: make_level_sensor(**kw),
            "alarm_tile":    lambda: make_alarm_tile(**kw),
            "icssi_emblem":  lambda: make_icssi_emblem(**kw),
        }
        _CACHE[cache_key] = _to_photoimage(makers[key]())
    return _CACHE[cache_key]


def clear_cache():
    _CACHE.clear()
