"""Generated label, sign and screen textures (PIL) for physical decals in the lab twin.

Per the Cell 01 rendering specification, station IDs, barcodes, hazard markings and status displays are physical
decals/materials, not floating callouts. Everything here is drawn procedurally (no third-party artwork). Screen
contents that show values use the twin's own simulated state or are marked as illustrative; the barcodes are
visual only (the twin reads identities from labware attributes, not from pixels).
"""

import hashlib
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIR = "/usr/share/fonts/opentype/inter"
_FONTS = {}


def font(px, weight="SemiBold"):
    key = (px, weight)
    if key not in _FONTS:
        try:
            _FONTS[key] = ImageFont.truetype(os.path.join(FONT_DIR, f"Inter-{weight}.otf"), px)
        except OSError:
            _FONTS[key] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", px)
    return _FONTS[key]


def _save(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    return path


def _center_text(d, box, text, f, fill):
    x0, y0, x1, y1 = box
    bb = d.textbbox((0, 0), text, font=f)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((x0 + x1 - w) / 2 - bb[0], (y0 + y1 - h) / 2 - bb[1]), text, font=f, fill=fill)


def bars(text, n=70):
    """Deterministic pseudo-barcode bar widths for text (visual only)."""
    h = hashlib.sha256(text.encode()).digest()
    widths = [2, 1, 1, 2] + [1 + (b % 3) for b in h * 3][:n] + [2, 1, 1, 2]
    return widths


def draw_barcode(d, box, text, fg=(20, 20, 20)):
    x0, y0, x1, y1 = box
    w = bars(text)
    total = sum(w)
    unit = (x1 - x0) / total
    x = x0
    for i, k in enumerate(w):
        if i % 2 == 0:
            d.rectangle([x, y0, x + k * unit - 0.5, y1], fill=fg)
        x += k * unit


def station_plate(path, code, name, sub="AICOR Cell 01", w=1200, h=420, accent=(18, 62, 118)):
    """Engraved-look station ID plate: white face, accent bar, code, name, small barcode."""
    img = Image.new("RGB", (w, h), (238, 239, 238))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, 26], fill=accent)
    d.rectangle([0, h - 10, w, h], fill=(200, 202, 204))
    d.text((48, 52), code, font=font(int(h * 0.42), "Bold"), fill=(25, 28, 32))
    cb = d.textbbox((48, 52), code, font=font(int(h * 0.42), "Bold"))
    d.text((cb[2] + 48, 70), name, font=font(int(h * 0.15), "SemiBold"), fill=(35, 38, 44))
    d.text((cb[2] + 48, 70 + int(h * 0.20)), sub, font=font(int(h * 0.10), "Regular"), fill=(90, 94, 100))
    draw_barcode(d, (cb[2] + 48, h - 120, w - 60, h - 50), f"{code}-{name}")
    for x in (18, w - 30):   # rivets
        d.ellipse([x, h / 2 - 6, x + 12, h / 2 + 6], fill=(170, 172, 175))
    return _save(img, path)


def plain_sign(path, lines, w=1000, h=360, bg=(245, 245, 243), fg=(30, 32, 36), accent=None, sizes=None):
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    if accent:
        d.rectangle([0, 0, 24, h], fill=accent)
    sizes = sizes or [int(h * 0.30)] + [int(h * 0.14)] * (len(lines) - 1)
    y = h * 0.14
    for i, line in enumerate(lines):
        f = font(sizes[i], "Bold" if i == 0 else "Medium")
        d.text((60 if accent else 40, y), line, font=f, fill=fg)
        y += sizes[i] * 1.25
    return _save(img, path)


def _triangle(d, cx, cy, s, fill, border):
    pts = [(cx, cy - s * 0.58), (cx + s / 2, cy + s * 0.29), (cx - s / 2, cy + s * 0.29)]
    d.polygon(pts, fill=border)
    k = 0.80
    pts2 = [(cx, cy - s * 0.58 * k + s * 0.02), (cx + s / 2 * k, cy + s * 0.29 * k), (cx - s / 2 * k, cy + s * 0.29 * k)]
    d.polygon(pts2, fill=fill)


def _symbol(d, kind, cx, cy, s):
    k = (20, 20, 20)
    if kind == "robot":     # stylised arm
        d.line([(cx - s * 0.22, cy + s * 0.18), (cx - s * 0.05, cy - s * 0.05), (cx + s * 0.16, cy + s * 0.02)], fill=k,
               width=int(s * 0.07), joint="curve")
        d.rectangle([cx - s * 0.30, cy + s * 0.17, cx - s * 0.12, cy + s * 0.22], fill=k)
        d.ellipse([cx - s * 0.09, cy - s * 0.10, cx - s * 0.01, cy - s * 0.02], fill=k)
        d.line([(cx + s * 0.16, cy + s * 0.02), (cx + s * 0.16, cy + s * 0.12)], fill=k, width=int(s * 0.04))
    elif kind == "biohazard":
        for a in range(3):
            ang = math.radians(90 + 120 * a)
            x, y = cx + s * 0.09 * math.cos(ang), cy - s * 0.09 * math.sin(ang)
            d.ellipse([x - s * 0.11, y - s * 0.11, x + s * 0.11, y + s * 0.11], outline=k, width=int(s * 0.04))
        d.ellipse([cx - s * 0.04, cy - s * 0.04, cx + s * 0.04, cy + s * 0.04], fill=k)
    elif kind == "cold":
        for a in range(3):
            ang = math.radians(60 * a)
            dx, dy = s * 0.2 * math.cos(ang), s * 0.2 * math.sin(ang)
            d.line([(cx - dx, cy - dy), (cx + dx, cy + dy)], fill=k, width=int(s * 0.035))
    elif kind == "electric":
        d.polygon([(cx + s * 0.03, cy - s * 0.25), (cx - s * 0.10, cy + s * 0.02), (cx, cy + s * 0.02),
                   (cx - s * 0.05, cy + s * 0.22), (cx + s * 0.11, cy - s * 0.05), (cx + s * 0.01, cy - s * 0.05)], fill=k)
    elif kind == "gas":
        d.rounded_rectangle([cx - s * 0.07, cy - s * 0.18, cx + s * 0.07, cy + s * 0.22], radius=int(s * 0.06), fill=k)
        d.rectangle([cx - s * 0.03, cy - s * 0.25, cx + s * 0.03, cy - s * 0.17], fill=k)
    else:                   # general warning
        d.rectangle([cx - s * 0.03, cy - s * 0.18, cx + s * 0.03, cy + s * 0.06], fill=k)
        d.ellipse([cx - s * 0.035, cy + s * 0.11, cx + s * 0.035, cy + s * 0.18], fill=k)


def warning_sign(path, kind, text_lines, w=600, h=840):
    """ISO 7010-style warning: yellow triangle with symbol over a white text panel."""
    img = Image.new("RGB", (w, h), (250, 250, 248))
    d = ImageDraw.Draw(img)
    s = w * 0.86
    _triangle(d, w / 2, h * 0.36, s, (250, 205, 0), (20, 20, 20))
    _symbol(d, kind, w / 2, h * 0.40, s * 0.75)
    y = h * 0.66
    for i, line in enumerate(text_lines):
        f = font(int(h * (0.075 if i == 0 else 0.055)), "Bold" if i == 0 else "Medium")
        _center_text(d, (0, y, w, y + h * 0.08), line, f, (20, 20, 20))
        y += h * 0.09
    d.rectangle([0, 0, w - 1, h - 1], outline=(180, 180, 180), width=4)
    return _save(img, path)


def mandatory_sign(path, text_lines, w=600, h=840):
    """Blue mandatory-action disc (ISO 7010 M-series style, generic 'i' pictogram) + text."""
    img = Image.new("RGB", (w, h), (250, 250, 248))
    d = ImageDraw.Draw(img)
    r = w * 0.38
    d.ellipse([w / 2 - r, h * 0.33 - r, w / 2 + r, h * 0.33 + r], fill=(0, 82, 160))
    _center_text(d, (0, h * 0.33 - r, w, h * 0.33 + r), "i", font(int(r * 1.3), "Bold"), (255, 255, 255))
    y = h * 0.66
    for i, line in enumerate(text_lines):
        f = font(int(h * (0.07 if i == 0 else 0.052)), "Bold" if i == 0 else "Medium")
        _center_text(d, (0, y, w, y + h * 0.08), line, f, (20, 20, 20))
        y += h * 0.085
    return _save(img, path)


def exit_sign(path, w=900, h=320):
    img = Image.new("RGB", (w, h), (0, 150, 70))
    d = ImageDraw.Draw(img)
    # stylised running figure + arrow + door
    k = (255, 255, 255)
    d.rectangle([w * 0.06, h * 0.15, w * 0.24, h * 0.85], outline=k, width=10)
    d.ellipse([w * 0.31, h * 0.13, w * 0.37, h * 0.29], fill=k)
    d.line([(w * 0.34, h * 0.32), (w * 0.31, h * 0.58), (w * 0.27, h * 0.84)], fill=k, width=16)
    d.line([(w * 0.31, h * 0.58), (w * 0.37, h * 0.70), (w * 0.35, h * 0.86)], fill=k, width=16)
    d.line([(w * 0.27, h * 0.45), (w * 0.34, h * 0.36), (w * 0.40, h * 0.48)], fill=k, width=14)
    d.polygon([(w * 0.50, h * 0.42), (w * 0.62, h * 0.42), (w * 0.62, h * 0.30), (w * 0.78, h * 0.50),
               (w * 0.62, h * 0.70), (w * 0.62, h * 0.58), (w * 0.50, h * 0.58)], fill=k)
    d.text((w * 0.80, h * 0.33), "EXIT", font=font(int(h * 0.30), "Bold"), fill=k)
    return _save(img, path)


def brand_panel(path, w=2400, h=1000):
    """'AICOR Cell 01' rear panel graphic (the project's own brand, as in the Cell 01 concept renderings)."""
    img = Image.new("RGB", (w, h), (236, 238, 240))
    d = ImageDraw.Draw(img)
    navy = (22, 44, 82)
    d.text((140, 230), "AICOR", font=font(330, "Light"), fill=navy)
    d.text((150, 600), "Cell 01", font=font(150, "Regular"), fill=navy)
    d.line([(1350, 260), (1350, 760)], fill=(150, 160, 175), width=4)
    for i, t in enumerate(("Culture Handling &", "Liquid Intervention Cell", "Semantic Digital Twin")):
        d.text((1430, 320 + i * 130), t, font=font(90, "Regular"), fill=(40, 60, 95))
    return _save(img, path)


def stripe_texture(path, w=512, h=64, c1=(240, 190, 0), c2=(20, 20, 20)):
    img = Image.new("RGB", (w, h), c1)
    d = ImageDraw.Draw(img)
    for x in range(-h, w + h, 48):
        d.polygon([(x, h), (x + 24, h), (x + 24 + h, 0), (x + h, 0)], fill=c2)
    return _save(img, path)


# ------------------------------------------------------------------------------------------- screens
def _panel(d, box, title, bg=(28, 34, 44), fg=(210, 220, 235)):
    d.rounded_rectangle(box, radius=10, fill=bg)
    d.text((box[0] + 16, box[1] + 10), title, font=font(22, "SemiBold"), fill=fg)


def _sparkline(d, box, ys, color, lo=None, hi=None, width=3):
    x0, y0, x1, y1 = box
    ys = np.asarray(ys, float)
    lo = ys.min() if lo is None else lo
    hi = ys.max() if hi is None else hi
    xs = np.linspace(x0, x1, len(ys))
    py = y1 - (ys - lo) / max(hi - lo, 1e-9) * (y1 - y0)
    d.line(list(zip(xs, py)), fill=color, width=width)


def screen_hmi(path, stations, w=1280, h=800, title="Cell 01  |  AUTOMATIC  |  doors closed  |  safety OK"):
    """Cell HMI: station status tiles. stations: [(id, name, state, ok)]. States come from the twin's controllers."""
    img = Image.new("RGB", (w, h), (14, 18, 26))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, 70], fill=(22, 44, 82))
    d.text((24, 18), title, font=font(30, "SemiBold"), fill=(235, 240, 250))
    cols = 4
    tw, th = (w - 40 - (cols - 1) * 16) / cols, 150
    for i, (sid, name, state, ok) in enumerate(stations):
        x = 20 + (i % cols) * (tw + 16)
        y = 90 + (i // cols) * (th + 16)
        d.rounded_rectangle([x, y, x + tw, y + th], radius=12, fill=(30, 38, 52))
        d.rectangle([x, y, x + 8, y + th], fill=(40, 190, 90) if ok else (230, 160, 20))
        d.text((x + 24, y + 14), sid, font=font(40, "Bold"), fill=(240, 244, 250))
        d.text((x + 24, y + 66), name, font=font(20, "Medium"), fill=(160, 175, 195))
        d.text((x + 24, y + 104), state, font=font(22, "SemiBold"), fill=(120, 220, 150) if ok else (240, 190, 70))
    d.text((24, h - 44), "simulated twin state", font=font(20, "Regular"), fill=(110, 120, 140))
    return _save(img, path)


def screen_dashboard(path, w=1600, h=900, seed=3, camera_png=None, heading="Semantic Digital Twin - Cell 01"):
    """Operator dashboard: episode timeline, evidence log, a camera tile. All values illustrative (simulated)."""
    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (w, h), (12, 16, 22))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, 64], fill=(20, 30, 46))
    d.text((24, 14), heading, font=font(30, "SemiBold"), fill=(230, 236, 246))
    d.text((w - 360, 20), "SIMULATION  |  illustrative", font=font(22, "Medium"), fill=(140, 160, 190))
    _panel(d, (20, 84, 780, 470), "Episode timeline")
    steps = ["retrieve", "identify", "transport", "dose", "settle", "image", "QC", "return"]
    for i, s in enumerate(steps):
        y = 130 + i * 40
        d.text((40, y), s, font=font(20, "Medium"), fill=(170, 185, 205))
        a = 170 + rng.integers(0, 200)
        b = a + 60 + rng.integers(0, 200)
        d.rounded_rectangle([a + 30, y + 2, min(b + 30, 760), y + 26], radius=6,
                            fill=(60, 160, 230) if i != 5 else (70, 200, 120))
    _panel(d, (800, 84, 1580, 470), "Camera R01 cluster" if camera_png else "Evidence layer")
    if camera_png and os.path.exists(camera_png):
        cam = Image.open(camera_png).convert("RGB").resize((744, 330))
        img.paste(cam, (818, 124))
    _panel(d, (20, 490, 780, 880), "L10 environment (illustrative model)")
    t = np.linspace(0, 6, 200)
    _sparkline(d, (40, 560, 760, 700), np.sin(t) * 0.05 + rng.normal(0, 0.01, 200), (240, 120, 90))
    _sparkline(d, (40, 720, 760, 860), np.cos(t * 0.7) * 0.05 + rng.normal(0, 0.01, 200), (90, 180, 240))
    _panel(d, (800, 490, 1580, 880), "Records (committed / routed)")
    rows = ["transport  P30  R03 -> H2      committed", "identify   P17  L10 reader     committed",
            "dose       P17  L12 B05        committed", "image      P17  L17 10x A03    committed",
            "qc         REF-L21-001  L17    pass", "quarantine P18  H4             routed",
            "tool_frame T01  L21 datum      corrected"]
    for i, r in enumerate(rows):
        d.text((820, 540 + i * 44), r, font=font(22, "Regular"), fill=(190, 205, 225) if "routed" not in r
               else (240, 190, 80))
    return _save(img, path)


def screen_device(path, lines, w=480, h=300, bg=(8, 20, 34), fg=(200, 230, 255), accent=(60, 170, 255)):
    """Small device display (freezer, fridge, BSC, centrifuge). Values are equipment class set points."""
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, 8], fill=accent)
    y = 24
    for i, line in enumerate(lines):
        f = font(int(h * (0.30 if i == 0 else 0.11)), "SemiBold" if i == 0 else "Medium")
        d.text((22, y), line, font=f, fill=fg if i == 0 else (150, 180, 210))
        y += h * (0.36 if i == 0 else 0.15)
    return _save(img, path)


def screen_code(path, w=1600, h=900, seed=5):
    """Code editor / terminal look for engineering workstations (twin scripts)."""
    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (w, h), (24, 26, 32))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 260, h], fill=(30, 33, 40))
    for i in range(22):
        d.text((20, 30 + i * 36), ["assets/", "scenes/", "twin/", "scripts/", "tools/"][i % 5] + f"{'x' * (4 + i % 7)}.py",
               font=font(18, "Regular"), fill=(140, 150, 170))
    kw = [(198, 120, 221), (97, 175, 239), (152, 195, 121), (229, 192, 123), (171, 178, 191)]
    for i in range(34):
        x = 290 + 24 * int(rng.integers(0, 4))
        y = 20 + i * 25
        for _ in range(int(rng.integers(1, 6))):
            ln = int(rng.integers(30, 160))
            d.rounded_rectangle([x, y + 6, x + ln, y + 16], radius=4, fill=kw[int(rng.integers(0, 5))])
            x += ln + 12
    return _save(img, path)


def blur(path, radius=1.0):
    img = Image.open(path)
    img.filter(ImageFilter.GaussianBlur(radius)).save(path)
    return path
