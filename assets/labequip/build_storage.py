"""Storage-room and building-services equipment library (visual proxies) for the lab twin.

Run from the repo root:  env_cad/bin/python assets/labequip/build_storage.py [asset_name ...]
Writes assets/labequip/usd/<name>.usda (root prim /Asset, default prim) and generated label / screen textures under
assets/labequip/textures/.

Conventions (metres, Z up):
  * floor items: origin on the floor at the footprint centre, front (door / operator side) toward -Y;
  * wall items: origin on the wall surface at the mounting-height centre, the item extends toward -Y;
  * ceiling items: origin on the ceiling surface, the item hangs toward -Z.
Every build_<name>(k, **params) fills a meshkit Kit in local coordinates and returns the asset's semantics dict.
All dimensions are generic equipment-class dimensions (project-owned proxies, no manufacturer CAD, no brands).
Displays show equipment-class set points only; consumable labels are generic (project rule D016).
"""

import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from assets.common import decals  # noqa: E402
from assets.common.decals import draw_barcode, font  # noqa: E402
from assets.common.meshkit import Kit, new_asset, rot_x, rot_y, rot_z  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "textures")
USD_DIR = os.path.join(HERE, "usd")
DESIGN = "project-owned proxy with generic class dimensions; no manufacturer CAD"
BINDING = "visual_proxy_v1"


# =============================================================================================== local helpers
def _n(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def ccw(pts):
    P = np.asarray(pts, float)
    a = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    return P if a > 0 else P[::-1]


def quads(k, mat, centers, normal, up, w, h):
    """Many equal flat quads (slots, ports, LED dots, holes) in one mesh chunk."""
    C = np.atleast_2d(np.asarray(centers, float))
    if len(C) == 0:
        return
    nn = _n(normal)
    u = np.asarray(up, float)
    u = _n(u - nn * (u @ nn))
    r = np.cross(u, nn)
    cr = np.array([-r * w / 2 - u * h / 2, r * w / 2 - u * h / 2, r * w / 2 + u * h / 2, -r * w / 2 + u * h / 2])
    P = (C[:, None, :] + cr[None]).reshape(-1, 3)
    b = np.arange(len(C)) * 4
    T = np.concatenate([np.stack([b, b + 1, b + 2], 1), np.stack([b, b + 2, b + 3], 1)])
    UV = np.tile([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], (len(C), 1))
    k.add(mat, P, np.tile(nn, (len(P), 1)), T, UV)


def shell_box(k, mat, center, size, wall, r=0.004, seg=2, faces=None):
    """Thin-walled box (outer surface + inward-facing inner surface), e.g. shrink film or a moulded lid.
    faces: optional subset of '+x-x+y-y+z-z' (open ends let direct light reach the contents in a path tracer)."""
    k.rbox(mat, center, size, r=r, seg=seg, faces=faces)
    tmp = Kit()
    tmp.rbox(mat, center, np.asarray(size, float) - 2 * wall, r=max(r - wall, 0.0005), seg=seg, faces=faces)
    P, N, _, T = tmp.parts[mat][0]
    k.add(mat, P, -N, T[:, [0, 2, 1]])


def grid(center, normal, up, nx, ny, px, py):
    """Centres of an nx x ny grid on a plane (x along the plane's 'right', y along 'up')."""
    c = np.asarray(center, float)
    nn = _n(normal)
    u = np.asarray(up, float)
    u = _n(u - nn * (u @ nn))
    r = np.cross(u, nn)
    return [c + r * (i - (nx - 1) / 2) * px + u * (j - (ny - 1) / 2) * py for i in range(nx) for j in range(ny)]


def curved_decal(k, png, c, r, z0, z1, ang, width, seg=10, emissive=0.0):
    """Label wrapped around a vertical cylinder (axis through c=(x, y)), centred at angle ang (rad), radius r."""
    half = width / r / 2
    th = np.linspace(ang - half, ang + half, seg + 1)
    P, N, UV = [], [], []
    for i, t in enumerate(th):
        n = (math.cos(t), math.sin(t), 0.0)
        for z, v in ((z0, 0.0), (z1, 1.0)):
            P.append((c[0] + r * n[0], c[1] + r * n[1], z))
            N.append(n)
            UV.append((i / seg, v))
    T = []
    for i in range(seg):
        a, b, cc, d = 2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 3
        T += [(a, cc, d), (a, d, b)]
    key = ("screen:" if emissive > 0 else "decal:") + os.path.abspath(png) + (f"@{emissive}" if emissive else "")
    k.add(key, np.array(P), np.array(N), np.array(T), np.array(UV))


def disk_decal(k, png, center, normal, up, r, seg=32, emissive=0.0):
    """Round textured decal (dials, round labels); the texture's inscribed circle maps onto the disk."""
    nn = _n(normal)
    u = np.asarray(up, float)
    u = _n(u - nn * (u @ nn))
    rr = np.cross(u, nn)
    th = np.linspace(0, 2 * math.pi, seg + 1)[:-1]
    c = np.asarray(center, float)
    P = np.concatenate([[c], c + r * (np.outer(np.cos(th), rr) + np.outer(np.sin(th), u))])
    UV = np.concatenate([[[0.5, 0.5]], 0.5 + 0.5 * np.stack([np.cos(th), np.sin(th)], 1)])
    T = np.array([[0, 1 + i, 1 + (i + 1) % seg] for i in range(seg)])
    key = ("screen:" if emissive > 0 else "decal:") + os.path.abspath(png) + (f"@{emissive}" if emissive else "")
    k.add(key, P, np.tile(nn, (len(P), 1)), T, UV)


def foot(k, x, y, h, r=0.02, mat="RubberBlack"):
    """Levelling foot: rubber pad, hex nut, threaded stem up to height h."""
    k.cyl(mat, (x, y, 0), (x, y, 0.007), r, seg=20, r_edge=0.002)
    k.cyl("Chrome", (x, y, 0.007), (x, y, 0.014), r * 0.62, seg=6)
    k.cyl("Chrome", (x, y, 0.014), (x, y, h), 0.006, seg=12, caps=False)


def castor(k, x, y, wr=0.04, ww=0.028, yaw=0.0, fork="Chrome", brake=False):
    """Swivel castor; returns height of the mounting-plate top."""
    top = 2 * wr + 0.03
    with k.at((x, y, 0), yaw):
        off = 0.016
        k.cyl("RubberBlack", (-ww / 2, off, wr), (ww / 2, off, wr), wr, seg=24, r_edge=0.007)
        k.cyl("PlasticGrey", (-ww / 2 - 0.0008, off, wr), (ww / 2 + 0.0008, off, wr), wr * 0.5, seg=18)
        k.cyl("Chrome", (-ww / 2 - 0.007, off, wr), (ww / 2 + 0.007, off, wr), 0.0055, seg=10)
        for s in (-1, 1):
            k.box_between(fork, (min(s * (ww / 2 + 0.0015), s * (ww / 2 + 0.0045)), off - 0.013, wr - 0.006),
                          (max(s * (ww / 2 + 0.0015), s * (ww / 2 + 0.0045)), 0.014, 2 * wr + 0.012), r=0.0012, seg=1)
        k.box_between(fork, (-ww / 2 - 0.0045, -0.02, 2 * wr + 0.008), (ww / 2 + 0.0045, 0.02, 2 * wr + 0.016),
                      r=0.0015, seg=1)
        k.cyl(fork, (0, 0, 2 * wr + 0.016), (0, 0, 2 * wr + 0.025), 0.022, seg=20)
        k.box_between(fork, (-0.032, -0.032, top - 0.005), (0.032, 0.032, top), r=0.0015, seg=1)
        if brake:
            k.box_between("PlasticRed", (-0.012, -0.045, 2 * wr - 0.004), (0.012, -0.012, 2 * wr + 0.004), r=0.002, seg=1)
    return top


def screen_fy(k, png, x, yface, z, w, h, em=500.0, bez=0.005, d=0.003, mat="PlasticBlack"):
    """Display on a -Y facing surface at y=yface: bezel + emissive screen decal."""
    k.rbox(mat, (x, yface - d / 2, z), (w + 2 * bez, d, h + 2 * bez), r=0.0015, seg=1)
    k.decal(png, (x, yface - d - 0.0006, z), (0, -1, 0), (0, 0, 1), w, h, emissive=em)


def button_fy(k, x, yface, z, r=0.006, mat="PlasticGrey", h=0.003):
    k.cyl(mat, (x, yface, z), (x, yface - h, z), r, seg=16, r_edge=0.001)


def glass_bottle(k, base, R, H, rn, glass="GlassClear", cap="PlasticBlue", liquid=None, fill=0.6, wall=0.0025,
                 seg=28, label=None, label_ang=-math.pi / 2):
    """Lab bottle as a closed glass shell (outer + inner surface) with optional liquid volume and screw cap."""
    x, y, z = base
    sh = H * 0.70
    nb = H - 0.030
    prof = [(0.0, 0.0), (R - 0.008, 0.0), (R - 0.003, 0.001), (R, 0.006), (R, sh)]
    for a in np.linspace(0.15, math.pi / 2, 6):
        prof.append((rn + (R - rn) * math.cos(a), sh + (nb - sh) * math.sin(a)))
    prof += [(rn, H - 0.003), (rn - 0.001, H), (rn - wall, H), (rn - wall, nb)]
    for a in np.linspace(math.pi / 2, 0.15, 6):
        prof.append((rn - wall + (R - rn) * math.cos(a), sh + (nb - sh) * math.sin(a) - wall * 0.5))
    prof += [(R - wall, sh - wall * 0.5), (R - wall, wall + 0.004), (R - wall - 0.004, wall), (0.0, wall)]
    k.lathe(glass, prof, (x, y, z), seg=seg)
    if liquid:
        ri = R - wall - 0.0006
        fz = wall + fill * (sh - wall)
        k.lathe(liquid, [(0.0, wall + 0.0006), (ri - 0.004, wall + 0.0006), (ri, wall + 0.0046), (ri, fz), (0.0, fz)],
                (x, y, z), seg=seg, smooth=False)
    if cap:
        k.cyl(cap, (x, y, z + H - 0.024), (x, y, z + H + 0.003), rn + 0.0045, seg=seg, r_edge=0.0018)
        k.cyl(cap, (x, y, z + H - 0.032), (x, y, z + H - 0.0235), rn + 0.0055, seg=seg, r_edge=0.001)
    if label:
        curved_decal(k, label, (x, y), R + 0.0006, z + sh * 0.22, z + sh * 0.22 + min(0.5 * sh, 0.07), label_ang,
                     min(1.9 * R, 0.10))


def hdpe_bottle(k, base, R, H, cap="PlasticWhite", label=None, label_ang=-math.pi / 2):
    x, y, z = base
    rn = R * 0.42
    prof = [(0.0, 0.0), (R - 0.01, 0.0), (R - 0.002, 0.003), (R, 0.012), (R, H * 0.74)]
    for a in np.linspace(0.2, math.pi / 2, 5):
        prof.append((rn + (R - rn) * math.cos(a), H * 0.74 + (H * 0.92 - H * 0.74) * math.sin(a)))
    prof += [(rn, H), (0.0, H)]
    k.lathe("HdpeNatural", prof, (x, y, z), seg=28)
    k.cyl(cap, (x, y, z + H - 0.012), (x, y, z + H + 0.016), rn + 0.004, seg=24, r_edge=0.002)
    if label:
        curved_decal(k, label, (x, y), R + 0.0007, z + H * 0.22, z + H * 0.22 + min(0.4 * H, 0.09), label_ang,
                     min(1.8 * R, 0.10))


def chain(k, pts, mat="Chrome", link=0.026, wire=0.0024, width=0.013):
    """Short-link chain along a polyline (alternating link orientation)."""
    pts = np.asarray(pts, float)
    seglen = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seglen)])
    pitch = link - 2 * wire - 0.002
    th = np.linspace(0, 2 * math.pi, 13)
    for i, s in enumerate(np.arange(link / 2, cum[-1] - link / 2 + 1e-9, pitch)):
        j = min(np.searchsorted(cum, s) - 1, len(seglen) - 1)
        j = max(j, 0)
        f = (s - cum[j]) / seglen[j]
        p = pts[j] + f * (pts[j + 1] - pts[j])
        t = _n(pts[j + 1] - pts[j])
        side = _n(np.cross(t, (0, 0, 1)))
        a2 = np.array([0.0, 0, 1]) if i % 2 == 0 else side
        lx, ly = link / 2 - width / 2, width / 2 - wire
        loop = []
        for a in th:  # stadium
            ca, sa = math.cos(a), math.sin(a)
            loop.append(p + t * (np.sign(ca) * lx + ly * ca) + a2 * ly * sa)
        k.tube(mat, loop, wire, seg=6)


def needle_gauge(k, png, center, r, angle_deg, depth=0.022, case="Chrome"):
    """Round dial gauge facing local -Y (use inside k.at for other orientations)."""
    cx, cy, cz = center
    k.cyl(case, (cx, cy + depth, cz), (cx, cy, cz), r, seg=28, r_edge=0.003)
    k.cyl(case, (cx, cy - 0.0015, cz), (cx, cy + 0.002, cz), r * 1.04, seg=28, caps=False)
    disk_decal(k, png, (cx, cy - 0.0006, cz), (0, -1, 0), (0, 0, 1), r * 0.93)
    with k.at((cx, cy - 0.0016, cz), R=rot_y(angle_deg)):
        k.box("PlasticBlack", (0, 0, r * 0.32), (0.0018, 0.0006, r * 0.8))
    k.cyl("PlasticBlack", (cx, cy - 0.0012, cz), (cx, cy - 0.0028, cz), 0.003, seg=10)


# =============================================================================================== textures
_MADE = {}


def tx(name):
    return os.path.join(TEX, name)


def once(name, fn, *a, **kw):
    p = tx(name)
    if p not in _MADE:
        _MADE[p] = fn(p, *a, **kw)
    return p


def _save(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    return path


def _wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def tex_consumable(path, title, sub, code, band=(30, 90, 160), w=640, h=400):
    img = Image.new("RGB", (w, h), (244, 244, 240))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, 58], fill=band)
    d.text((22, 12), "LAB CONSUMABLE", font=font(30, "SemiBold"), fill=(250, 250, 250))
    y = 76
    for line in _wrap(d, title, font(50, "Bold"), w - 44)[:2]:
        d.text((22, y), line, font=font(50, "Bold"), fill=(25, 28, 32))
        y += 58
    d.text((22, y + 4), sub, font=font(30, "Medium"), fill=(70, 74, 80))
    draw_barcode(d, (22, h - 104, int(w * 0.66), h - 34), code)
    d.text((22, h - 30), code, font=font(22, "Medium"), fill=(40, 40, 40))
    d.rectangle([w - 120, h - 104, w - 24, h - 34], outline=(40, 40, 40), width=3)
    d.text((w - 108, h - 92), "LOT", font=font(22, "SemiBold"), fill=(40, 40, 40))
    return _save(img, path)


def tex_bin(path, code):
    img = Image.new("RGB", (600, 200), (248, 248, 246))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 600, 12], fill=(20, 70, 140))
    d.text((16, 22), code, font=font(66, "Bold"), fill=(20, 22, 26))
    draw_barcode(d, (16, 112, 584, 186), code)
    return _save(img, path)


def tex_tag(path, line1, line2, w=600, h=240):
    img = Image.new("RGB", (w, h), (214, 217, 221))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], outline=(150, 154, 160), width=4)
    d.text((22, 14), "AICOR", font=font(46, "Bold"), fill=(22, 44, 82))
    d.text((200, 26), line1, font=font(34, "SemiBold"), fill=(30, 34, 40))
    d.text((22, 78), line2, font=font(30, "Medium"), fill=(50, 54, 60))
    draw_barcode(d, (22, 130, w - 22, 218), f"{line1}|{line2}")
    return _save(img, path)


def tex_text(path, lines, w=800, h=240, bg=(240, 240, 238), fg=(30, 32, 36), sizes=None, center=False, bold0=True):
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    sizes = sizes or [int(h * 0.42)] + [int(h * 0.2)] * (len(lines) - 1)
    total = sum(s * 1.2 for s in sizes)
    y = (h - total) / 2
    for i, line in enumerate(lines):
        f = font(sizes[i], "Bold" if (i == 0 and bold0) else "Medium")
        tw = d.textlength(line, font=f)
        d.text(((w - tw) / 2 if center else 24, y), line, font=f, fill=fg)
        y += sizes[i] * 1.2
    return _save(img, path)


def tex_glove_side(path, size):
    img = Image.new("RGB", (960, 260), (246, 247, 248))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 960, 40], fill=(40, 90, 190))
    d.rectangle([0, 220, 960, 260], fill=(40, 90, 190))
    d.text((30, 62), "Nitrile gloves", font=font(64, "Bold"), fill=(25, 40, 80))
    d.text((30, 140), "powder-free | 100 pcs", font=font(36, "Medium"), fill=(70, 80, 100))
    d.ellipse([780, 52, 940, 212], fill=(40, 90, 190))
    tw = d.textlength(size, font=font(110, "Bold"))
    d.text((860 - tw / 2, 62), size, font=font(110, "Bold"), fill=(255, 255, 255))
    return _save(img, path)


def tex_glove_top(path):
    img = Image.new("RGB", (960, 500), (246, 247, 248))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 960, 30], fill=(40, 90, 190))
    d.rectangle([0, 470, 960, 500], fill=(40, 90, 190))
    d.ellipse([250, 150, 710, 350], fill=(225, 228, 232))
    d.ellipse([268, 166, 692, 334], fill=(60, 95, 175))
    d.polygon([(400, 180), (520, 172), (600, 250), (470, 300), (380, 260)], fill=(95, 135, 215))
    d.line([(420, 215), (560, 230)], fill=(130, 165, 230), width=8)
    return _save(img, path)


def tex_gauge(path, unit="bar", maxv=10):
    s = 400
    img = Image.new("RGB", (s, s), (40, 42, 44))
    d = ImageDraw.Draw(img)
    d.ellipse([4, 4, s - 4, s - 4], fill=(246, 246, 244))
    c = s / 2
    for i in range(41):
        a = math.radians(225 - 270 * i / 40)
        r0 = 0.40 * s if i % 4 else 0.36 * s
        d.line([(c + r0 * math.cos(a), c - r0 * math.sin(a)), (c + 0.45 * s * math.cos(a), c - 0.45 * s * math.sin(a))],
               fill=(20, 20, 20), width=5 if i % 4 == 0 else 2)
        if i % 8 == 0:
            v = str(int(maxv * i / 40))
            f = font(30, "SemiBold")
            tw = d.textlength(v, font=f)
            d.text((c + 0.28 * s * math.cos(a) - tw / 2, c - 0.28 * s * math.sin(a) - 18), v, font=f, fill=(20, 20, 20))
    d.arc([0.07 * s, 0.07 * s, 0.93 * s, 0.93 * s], -45 - 54, -45, fill=(200, 30, 20), width=8)
    f = font(34, "Medium")
    d.text((c - d.textlength(unit, font=f) / 2, c + 0.16 * s), unit, font=f, fill=(40, 40, 40))
    return _save(img, path)


def tex_carrier_list(path, w=1280, h=760):
    img = Image.new("RGB", (w, h), (14, 18, 26))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, 76], fill=(22, 44, 82))
    d.text((24, 18), "S1  AMR dispatch  |  carrier queue", font=font(36, "SemiBold"), fill=(235, 240, 250))
    d.text((w - 330, 26), "simulated twin state", font=font(24, "Regular"), fill=(150, 165, 190))
    cols = [(24, "Carrier"), (250, "Content"), (560, "Destination"), (900, "State")]
    for x, t in cols:
        d.text((x, 100), t, font=font(26, "SemiBold"), fill=(140, 160, 190))
    rows = [("C-0101", "SBS x4", "Cell 01 / H4", "staged", True), ("C-0102", "SBS x2", "Cell 01 / H4", "staged", True),
            ("C-0103", "tube rack x1", "Cell 01 / L09", "loading", False),
            ("C-0104", "SBS x4", "Cell 01 / H4", "queued", False),
            ("C-0105", "empty", "return S1", "AMR en route", False),
            ("C-0106", "SBS x1", "Cell 01 / L17", "queued", False)]
    for i, (c, cont, dest, st, ok) in enumerate(rows):
        y = 150 + i * 88
        d.rounded_rectangle([16, y, w - 16, y + 74], radius=10, fill=(28, 36, 50))
        d.text((24, y + 18), c, font=font(32, "Bold"), fill=(235, 240, 250))
        d.text((250, y + 22), cont, font=font(28, "Medium"), fill=(190, 200, 215))
        d.text((560, y + 22), dest, font=font(28, "Medium"), fill=(190, 200, 215))
        d.rounded_rectangle([890, y + 16, 1240, y + 58], radius=8, fill=(30, 110, 60) if ok else (60, 70, 92))
        d.text((906, y + 20), st, font=font(28, "SemiBold"), fill=(235, 245, 235))
    return _save(img, path)


def tex_extinguisher_sign(path, s=600):
    img = Image.new("RGB", (s, s), (200, 20, 25))
    d = ImageDraw.Draw(img)
    k = (255, 255, 255)
    d.rectangle([12, 12, s - 12, s - 12], outline=k, width=10)
    d.rounded_rectangle([0.22 * s, 0.30 * s, 0.42 * s, 0.86 * s], radius=int(0.08 * s), fill=k)   # body
    d.rectangle([0.28 * s, 0.20 * s, 0.36 * s, 0.31 * s], fill=k)                                   # valve
    d.line([(0.36 * s, 0.24 * s), (0.50 * s, 0.22 * s)], fill=k, width=14)                          # lever
    d.line([(0.33 * s, 0.22 * s), (0.18 * s, 0.30 * s), (0.14 * s, 0.50 * s)], fill=k, width=12)  # hose
    for i in range(3):   # flames
        x = 0.58 * s + i * 0.11 * s
        d.polygon([(x, 0.86 * s), (x + 0.045 * s, 0.62 * s - (i % 2) * 0.06 * s), (x + 0.09 * s, 0.86 * s)], fill=k)
    return _save(img, path)


def tex_first_aid(path, w=600, h=600):
    img = Image.new("RGB", (w, h), (0, 135, 75))
    d = ImageDraw.Draw(img)
    k = (255, 255, 255)
    d.rectangle([0.38 * w, 0.14 * h, 0.62 * w, 0.66 * h], fill=k)
    d.rectangle([0.12 * w, 0.28 * h, 0.88 * w, 0.52 * h], fill=k)
    f = font(int(h * 0.12), "Bold")
    t = "FIRST AID"
    d.text(((w - d.textlength(t, font=f)) / 2, 0.74 * h), t, font=f, fill=k)
    return _save(img, path)


def tex_contactless(path, s=300):
    img = Image.new("RGB", (s, s), (20, 21, 23))
    d = ImageDraw.Draw(img)
    for i, r in enumerate((0.10, 0.20, 0.30)):
        d.arc([s * (0.30 - r), s * (0.5 - r), s * (0.30 + r), s * (0.5 + r)], -50, 50, fill=(200, 205, 210), width=12)
    d.ellipse([s * 0.26, s * 0.46, s * 0.34, s * 0.54], fill=(200, 205, 210))
    return _save(img, path)


def tex_vent(path, w=512, h=512):
    """Perforated door / panel texture: light background with dark hex holes."""
    img = Image.new("RGB", (w, h), (24, 25, 28))
    d = ImageDraw.Draw(img)
    for j in range(0, h + 20, 20):
        for i in range(0, w + 20, 20):
            x = i + (10 if (j // 20) % 2 else 0)
            d.ellipse([x - 6, j - 6, x + 6, j + 6], fill=(4, 4, 5))
    return _save(img, path)


CONSUMABLES = [
    ("SBS 96-well plates, sterile", "flat bottom | 50 pcs", (30, 90, 160)),
    ("Conductive tips 50 µL", "filtered | 10 racks x 96", (30, 30, 34)),
    ("Conductive tips 200 µL", "filtered | 10 racks x 96", (30, 30, 34)),
    ("Tube racks 2 mL", "96 format | 24 pcs", (150, 60, 20)),
    ("Nitrile gloves M", "10 boxes x 100 pcs", (40, 90, 190)),
    ("Sealing film", "clear, pierceable | 100 sheets", (40, 120, 90)),
    ("Deep-well plates 2 mL", "sterile | 40 pcs", (30, 90, 160)),
    ("Reservoirs, 1-well", "sterile | 25 pcs", (110, 60, 140)),
    ("Plate lids, SBS", "sterile | 100 pcs", (30, 90, 160)),
    ("Lint-free wipes", "20 packs", (90, 90, 96)),
]


def consumable_png(i):
    t, s, b = CONSUMABLES[i]
    return once(f"cons_{i:02d}.png", tex_consumable, t, s, f"ST01-C{i + 1:03d}", b)


def asset_tag(k, code, line2, center, normal=(0, -1, 0), up=(0, 0, 1), w=0.07):
    png = once(f"tag_{code}.png", tex_tag, code, line2)
    k.decal(png, center, normal, up, w, w * 0.4)


# =============================================================================================== 1 shelving rack
DECKS = [0.14, 0.56, 0.98, 1.40, 1.82]


def _carton(k, c, size, label, yaw=0.0):
    w, d, h = size
    with k.at(c, yaw):
        k.rbox("Cardboard", (0, 0, h / 2), (w, d, h), r=0.003, seg=1)
        k.quad("PlasticBlack", (0, 0, h + 0.0004), (0, 0, 1), (0, 1, 0), 0.0016, d * 0.985)
        k.quad("HdpeNatural", (0, 0, h + 0.0007), (0, 0, 1), (0, 1, 0), 0.048, d * 0.985)   # packing tape
        k.quad("HdpeNatural", (0, -d / 2 - 0.0007, h - 0.03), (0, -1, 0), (0, 0, 1), 0.048, 0.06)
        lw = min(0.13, w * 0.55)
        if label:
            k.decal(label, (-w / 2 + lw / 2 + 0.02, -d / 2 - 0.0008, min(h * 0.5, h - lw * 0.32 - 0.01)), (0, -1, 0),
                    (0, 0, 1), lw, lw * 0.625)


def _plate_sleeve(k, cx, cy, zb, n=10, label=None):
    pw, pd, ph, pitch = 0.1278, 0.0855, 0.0142, 0.0146
    for i in range(n):
        k.rbox("PlasticWhite", (cx, cy, zb + 0.002 + ph / 2 + i * pitch), (pw, pd, ph), r=0.0015, seg=1)
    H = n * pitch + 0.004
    shell_box(k, "PolystyreneClear", (cx, cy, zb + H / 2), (pw + 0.005, pd + 0.005, H), 0.0008, r=0.005,
              faces="+x-x+y-y")
    if label:
        k.decal(label, (cx - 0.02, cy - pd / 2 - 0.0034, zb + H * 0.55), (0, -1, 0), (0, 0, 1), 0.07, 0.044)
    return H


def _tip_box(k, cx, cy, zb, lid, base_mat, tips, label=None):
    bw, bd, bh, lh = 0.122, 0.082, 0.058, 0.032
    k.rbox(base_mat, (cx, cy, zb + bh / 2), (bw, bd, bh), r=0.003, seg=1)
    k.box(base_mat, (cx, cy, zb + bh + 0.002), (bw - 0.006, bd - 0.006, 0.004))
    if tips:
        xs = (np.arange(12) - 5.5) * 0.009
        ys = (np.arange(8) - 3.5) * 0.009
        cen = [(cx + a, cy + b, zb + bh + 0.0045) for a in xs for b in ys]
        quads(k, "PlasticGrey", [(cx, cy, zb + bh + 0.0042)], (0, 0, 1), (0, 1, 0), bw - 0.008, bd - 0.008)
        for p in cen:
            k.disk("PlasticBlack", p, 0.0036, seg=8, r_in=0.0024)
        for p in cen:
            k.disk("RubberBlack", (p[0], p[1], p[2] - 0.0002), 0.0025, seg=8)
    if lid == "clear":
        shell_box(k, "PolystyreneClear", (cx, cy, zb + bh + lh / 2 - 0.006), (bw + 0.004, bd + 0.004, lh + 0.012),
                  0.0015, r=0.004)
    else:
        k.rbox(lid, (cx, cy, zb + bh + lh / 2 - 0.006), (bw + 0.004, bd + 0.004, lh + 0.012), r=0.004, seg=2)
    if label:
        k.decal(label, (cx, cy - bd / 2 - 0.0007, zb + bh * 0.45), (0, -1, 0), (0, 0, 1), 0.07, 0.044)
    return bh + lh


def _shelf_groups(rng, hc, shelf_idx):
    """Pick one content group; returns (width, draw(k, x0, zb, yf))."""
    kinds = ["carton", "plates", "tips", "gloves", "hdpe"]
    p = [0.38, 0.18, 0.18, 0.12, 0.14] if shelf_idx > 0 else [0.65, 0.1, 0.05, 0.05, 0.15]
    kind = kinds[rng.choice(len(kinds), p=p)]
    if kind == "carton":
        sizes = [(0.30, 0.38, 0.24), (0.38, 0.30, 0.28), (0.26, 0.34, 0.16), (0.40, 0.40, 0.34), (0.22, 0.30, 0.20),
                 (0.34, 0.26, 0.12), (0.17, 0.22, 0.07), (0.20, 0.25, 0.10)]
        sizes = [s for s in sizes if s[2] <= hc - 0.01]
        w, d, h = sizes[rng.integers(len(sizes))]
        nst = max(1, min(int((hc - 0.01) // (h + 0.002)), int(rng.integers(1, 4))))
        labs = [consumable_png(int(rng.integers(len(CONSUMABLES)))) if rng.random() < 0.85 else None for _ in range(nst)]
        yaws = rng.uniform(-2.0, 2.0, nst)
        dxs = rng.uniform(-0.006, 0.006, nst)
        dy = rng.uniform(0.0, 0.03)

        def draw(k, x0, zb, yf):
            for s in range(nst):
                _carton(k, (x0 + w / 2 + dxs[s], yf + d / 2 + dy, zb + s * (h + 0.0015)), (w, d, h), labs[s], yaws[s])
        return w + 0.012, draw
    if kind == "plates":
        high = int(min(2, (hc - 0.01) // 0.152))
        if high < 1:
            return None
        cols = int(rng.integers(2, 4))
        rows = int(rng.integers(1, 3))
        lab = consumable_png(0)

        def draw(k, x0, zb, yf):
            for c in range(cols):
                for r in range(rows):
                    for s in range(high):
                        _plate_sleeve(k, x0 + 0.068 + c * 0.136, yf + 0.046 + r * 0.095, zb + s * 0.1515,
                                      label=lab if (r == 0 and s == high - 1) else None)
        return cols * 0.136, draw
    if kind == "tips":
        nst = int(min(3, (hc - 0.012) // 0.092))
        if nst < 1:
            return None
        cols = int(rng.integers(2, 5))
        clear = rng.random() < 0.5
        lid = "clear" if clear else "PlasticBlue"
        base = "PlasticBlack" if rng.random() < 0.7 else "PlasticWhite"
        lab = consumable_png(1 if rng.random() < 0.5 else 2)
        rows = int(rng.integers(2, 5))
        heights = [[int(rng.integers(1, nst + 1)) for _ in range(cols)] for _ in range(rows)]

        def draw(k, x0, zb, yf):
            for r in range(rows):
                for c in range(cols):
                    for s in range(heights[r][c]):
                        _tip_box(k, x0 + 0.064 + c * 0.128, yf + 0.043 + r * 0.09, zb + s * 0.0905, lid, base,
                                 tips=clear and s == heights[r][c] - 1 and r == 0, label=lab if (s == 0 and r == 0) else None)
        return cols * 0.128, draw
    if kind == "gloves":
        nst = int(min(5, (hc - 0.01) // 0.0665))
        if nst < 1:
            return None
        cols = int(rng.integers(1, 4))
        sizes = [["S", "M", "L"][int(rng.integers(3))] if rng.random() < 0.4 else "M" for _ in range(cols)]
        heights = [int(rng.integers(max(1, nst - 2), nst + 1)) for _ in range(cols)]
        rows = int(rng.integers(1, 4))
        top = once("glove_top.png", tex_glove_top)

        def draw(k, x0, zb, yf):
            for c in range(cols):
                side = once(f"glove_side_{sizes[c]}.png", tex_glove_side, sizes[c])
                cx = x0 + 0.121 + c * 0.244
                for r in range(rows):
                    y = yf + r * 0.127
                    for s in range(max(1, heights[c] - r)):
                        z = zb + s * 0.0662
                        k.rbox("PaperWhite", (cx, y + 0.0625, z + 0.0325), (0.24, 0.125, 0.065), r=0.002, seg=1)
                        k.decal(side, (cx, y - 0.0007, z + 0.0325), (0, -1, 0), (0, 0, 1), 0.232, 0.0628)
                        if s == max(1, heights[c] - r) - 1:
                            k.decal(top, (cx, y + 0.0625, z + 0.0657), (0, 0, 1), (0, 1, 0), 0.232, 0.121)
        return cols * 0.244, draw
    if kind == "hdpe":
        big = hc > 0.30 and rng.random() < 0.5
        R, H = (0.068, 0.27) if big else (0.046, 0.20)
        if H + 0.02 > hc:
            return None
        cols = int(rng.integers(2, 5))
        rows = int(rng.integers(1, 3))
        lab = once("hdpe_water.png", tex_text, ["Deionised water", "HDPE bottle | AICOR stores"], 600, 300,
                   sizes=[64, 40])
        caps = ["PlasticBlue" if rng.random() < 0.6 else "PlasticWhite" for _ in range(cols * rows)]

        def draw(k, x0, zb, yf):
            for r in range(rows):
                for c in range(cols):
                    hdpe_bottle(k, (x0 + R + 0.004 + c * (2 * R + 0.008), yf + R + 0.005 + r * (2 * R + 0.01), zb), R,
                                H, cap=caps[r * cols + c], label=lab if r == 0 else None)
        return cols * (2 * R + 0.008), draw
    return None


def build_shelving_rack(k, seed=1, bays=1, rack=1):
    W1, D, H = 1.2, 0.5, 2.0
    Wt = W1 * bays
    a, t = 0.04, 0.0022
    xs = [-Wt / 2 + i * W1 for i in range(bays + 1)]
    # ---- uprights (slotted angles) with foot pads and top caps
    for i, x in enumerate(xs):
        for y, sy in ((-D / 2, 1), (D / 2, -1)):
            for sx in ([1] if i < bays else []) + ([-1] if i > 0 else []):
                prof = [(0, 0), (sx * a, 0), (sx * a, sy * t), (sx * t, sy * t), (sx * t, sy * a), (0, sy * a)]
                k.extrude("PowderGrey", ccw([(x + u, y + v) for u, v in prof]), (0, 0, 0.009), (0, 0, H - 0.006),
                          up=(0, 1, 0))
                zs = np.arange(0.06, H - 0.04, 0.0254)
                quads(k, "PlasticBlack", [(x + sx * a * 0.6, y - sy * 0.0004, z) for z in zs], (0, -sy, 0), (0, 0, 1),
                      0.0055, 0.013)
                if i in (0, bays):
                    quads(k, "PlasticBlack", [(x - sx * 0.0004, y + sy * a * 0.6, z) for z in zs], (-sx, 0, 0),
                          (0, 0, 1), 0.0055, 0.013)
                k.box_between("PlasticBlack", (min(x, x + sx * (a + 0.002)), min(y, y + sy * (a + 0.002)), 0),
                              (max(x, x + sx * (a + 0.002)), max(y, y + sy * (a + 0.002)), 0.009))
                k.box_between("PlasticBlack", (min(x, x + sx * a), min(y, y + sy * a), H - 0.006),
                              (max(x, x + sx * a), max(y, y + sy * a), H))
    locs = []
    for b in range(bays):
        xl, xr = xs[b] + t + 0.0008, xs[b + 1] - t - 0.0008
        bcx = (xl + xr) / 2
        yb0 = -D / 2 + t + 0.0005
        # back cross bracing (two flat straps, offset in y so they do not intersect)
        L = math.hypot(xr - xl - 0.06, H - 0.30)
        ang = math.degrees(math.atan2(H - 0.30, xr - xl - 0.06))
        for j, s in enumerate((1, -1)):
            with k.at((bcx, D / 2 + 0.0012 + j * 0.0026, H / 2), R=rot_y(-s * ang)):
                k.box("Galvanized", (0, 0, 0), (L, 0.002, 0.022))
            for e in (-1, 1):
                k.cyl("Chrome", (bcx + e * (xr - xl - 0.06) / 2, D / 2, H / 2 + e * s * (H - 0.30) / 2),
                      (bcx + e * (xr - xl - 0.06) / 2, D / 2 + 0.0075, H / 2 + e * s * (H - 0.30) / 2), 0.0045, seg=10)
        for si, zt in enumerate(DECKS):
            for side in (-1, 1):   # step beams front / back
                y0, y1 = sorted((side * yb0, side * (yb0 + 0.025)))
                k.box_between("PowderGrey", (xl, y0, zt - 0.045), (xr, y1, zt), r=0.0015, seg=1)
            k.box_between("Galvanized", (xl + 0.002, -0.2218, zt - 0.0012), (xr - 0.002, 0.2218, zt))
            for e in (xl + 0.002, xr - 0.0032):
                k.box_between("Galvanized", (e, -0.2218, zt - 0.03), (e + 0.0012, 0.2218, zt - 0.0012))
            for fx in (-0.25, 0.25):
                k.box_between("Galvanized", (bcx + fx * (xr - xl) - 0.015, -0.2215, zt - 0.022),
                              (bcx + fx * (xr - xl) + 0.015, 0.2215, zt - 0.0012))
            code = f"ST01-R{rack}-S{si + 1}" if bays == 1 else f"ST01-R{rack}-B{b + 1}-S{si + 1}"
            fname = f"loc_R{rack}_S{si + 1}" if bays == 1 else f"loc_R{rack}_B{b + 1}_S{si + 1}"
            k.decal(once(f"bin_{code}.png", tex_bin, code), (xl + 0.10, yb0 - 0.0007, zt - 0.0225), (0, -1, 0),
                    (0, 0, 1), 0.09, 0.03)
            k.frame(fname, (bcx, 0, zt))
            locs.append(code)
            # contents
            hc = (DECKS[si + 1] - 0.045 - zt - 0.012) if si + 1 < len(DECKS) else 0.34
            rng = np.random.default_rng(seed * 1000 + rack * 100 + b * 10 + si)
            x = xl + 0.02 + rng.uniform(0, 0.03)
            fails = 0
            while fails < 10:
                g = _shelf_groups(rng, hc, si)
                if g is None or x + g[0] > xr - 0.015:
                    fails += 1
                    continue
                g[1](k, x, zt + 0.0005, -0.215 + rng.uniform(0, 0.012))
                x += g[0] + rng.uniform(0.012, 0.035)
                if rng.random() < 0.06:
                    x += rng.uniform(0.06, 0.15)   # occasional gap
    k.collide((0, 0, H / 2), (Wt, D, H))
    return {"sdt:assetId": f"ST01-R{rack}", "sdt:class": "storage_shelving",
            "sdt:role": "Boltless steel shelving rack holding the lab's consumables stock (plates, tips, tube racks, "
                        "gloves, bottles) at addressable shelf locations.",
            "sdt:storageLocations": locs}


# =============================================================================================== fridge / freezers
def _plinth_grille(k, x0, x1, y_face, z0, z1, mat="PowderWhite"):
    """Ventilation grille in a recessed plinth: dark backing + horizontal slats."""
    k.box_between("PlasticBlack", (x0, y_face + 0.012, z0), (x1, y_face + 0.016, z1))
    n = int((z1 - z0) // 0.014)
    for i in range(n):
        z = z0 + 0.004 + i * (z1 - z0 - 0.008) / max(n - 1, 1)
        k.box_between(mat, (x0, y_face, z - 0.0035), (x1, y_face + 0.012, z + 0.0035), r=0.0012, seg=1)


def _upright_shell(k, W, D, H, door_y, z_door0, z_door1, body_mat="PowderWhite", hollow=None):
    """Upright cabinet body: hollow (glass door) or solid, fascia above the door, plinth grille below, feet.
    door_y: front plane of door/fascia (negative); body front face at door_y + 0.055."""
    yb = door_y + 0.055
    if hollow:
        (cx0, cx1), (cz0, cz1) = hollow
        k.box_between(body_mat, (-W / 2, yb, 0.03), (-cx1, D / 2, H), r=0.006, seg=2)
        k.box_between(body_mat, (cx1, yb, 0.03), (W / 2, D / 2, H), r=0.006, seg=2)
        k.box_between(body_mat, (-cx1 - 0.002, D / 2 - 0.055, 0.035), (cx1 + 0.002, D / 2 - 0.002, H - 0.004))
        k.box_between(body_mat, (-cx1 - 0.002, yb, 0.035), (cx1 + 0.002, D / 2 - 0.054, cz0))
        k.box_between(body_mat, (-cx1 - 0.002, yb, cz1), (cx1 + 0.002, D / 2 - 0.054, H - 0.004))
        # liner
        L = "PlasticWhite"
        yl0, yl1 = yb, D / 2 - 0.055
        k.box_between(L, (-cx1, yl0 + 0.003, cz0), (cx1, yl1, cz0 + 0.003))
        k.box_between(L, (-cx1, yl0 + 0.003, cz1 - 0.003), (cx1, yl1, cz1))
        k.box_between(L, (-cx1, yl0 + 0.003, cz0), (-cx1 + 0.003, yl1, cz1))
        k.box_between(L, (cx1 - 0.003, yl0 + 0.003, cz0), (cx1, yl1, cz1))
        k.box_between(L, (-cx1, yl1 - 0.003, cz0), (cx1, yl1, cz1))
        # liner front lip (breaker strip)
        for e in (-1, 1):
            k.box_between("PlasticGrey", (min(e * cx1, e * (cx1 + 0.012)), yb - 0.0006, cz0),
                          (max(e * cx1, e * (cx1 + 0.012)), yb + 0.004, cz1))
        k.box_between("PlasticGrey", (-cx1 - 0.012, yb - 0.0006, cz0 - 0.012), (cx1 + 0.012, yb + 0.004, cz0))
        k.box_between("PlasticGrey", (-cx1 - 0.012, yb - 0.0006, cz1), (cx1 + 0.012, yb + 0.004, cz1 + 0.012))
    else:
        k.box_between(body_mat, (-W / 2, yb, 0.03), (W / 2, D / 2, H), r=0.008, seg=2)
    # fascia above the door and plinth below, flush with the door front
    k.box_between(body_mat, (-W / 2 + 0.0005, door_y, z_door1 + 0.004), (W / 2 - 0.0005, yb + 0.003, H - 0.0005),
                  r=0.007, seg=2)
    k.box_between(body_mat, (-W / 2 + 0.0005, door_y + 0.004, 0.03), (-W / 2 + 0.06, yb + 0.003, z_door0 - 0.004),
                  r=0.004, seg=1)
    k.box_between(body_mat, (W / 2 - 0.06, door_y + 0.004, 0.03), (W / 2 - 0.0005, yb + 0.003, z_door0 - 0.004),
                  r=0.004, seg=1)
    _plinth_grille(k, -W / 2 + 0.06, W / 2 - 0.06, door_y + 0.008, 0.035, z_door0 - 0.008, body_mat)
    for x in (-W / 2 + 0.05, W / 2 - 0.05):
        for y in (door_y + 0.06, D / 2 - 0.05):
            foot(k, x, y, 0.032)
    # rear compressor grille + power cord
    quads(k, "PlasticBlack", grid((0, D / 2 + 0.0005, 0.25), (0, 1, 0), (0, 0, 1), 1, 14, 0, 0.02), (0, 1, 0),
          (0, 0, 1), W * 0.6, 0.008)
    k.tube("PlasticBlack", [(W / 2 - 0.08, D / 2, 0.42), (W / 2 - 0.08, D / 2 + 0.03, 0.40),
                            (W / 2 - 0.08, D / 2 + 0.04, 0.2), (W / 2 - 0.08, D / 2 + 0.05, 0.01)], 0.0045, seg=8)


def _door_gasket(k, x0, x1, z0, z1, yb, w=0.012):
    for lo, hi in (((x0, yb - 0.0056, z0), (x0 + w, yb - 0.0002, z1)), ((x1 - w, yb - 0.0056, z0), (x1, yb - 0.0002, z1)),
                   ((x0, yb - 0.0056, z0), (x1, yb - 0.0002, z0 + w)), ((x0, yb - 0.0056, z1 - w), (x1, yb - 0.0002, z1))):
        k.box_between("RubberBlack", lo, hi, r=0.003, seg=1)


def _fridge_panel(k, W, door_y, zc, code, lines, label_lines, alarm_lit=False):
    """Fascia controls: display, buttons, power/alarm LEDs, key switch, model label, asset tag. Returns display pos."""
    disp = once(f"disp_{code}.png", decals.screen_device, lines)
    dx = -W / 2 + 0.12
    screen_fy(k, disp, dx, door_y, zc, 0.08, 0.05, em=450)
    for i in range(3):
        button_fy(k, dx + 0.065 + i * 0.022, door_y, zc - 0.012, r=0.006)
    k.cyl("IndicatorGreen", (dx + 0.065, door_y, zc + 0.016), (dx + 0.065, door_y - 0.002, zc + 0.016), 0.0028, seg=12)
    k.cyl("IndicatorRed" if alarm_lit else "PlasticRed", (dx + 0.087, door_y, zc + 0.016),
          (dx + 0.087, door_y - 0.002, zc + 0.016), 0.0028, seg=12)
    k.cyl("Chrome", (dx + 0.135, door_y, zc), (dx + 0.135, door_y - 0.004, zc), 0.009, seg=20, r_edge=0.001)
    quads(k, "PlasticBlack", [(dx + 0.135, door_y - 0.0046, zc)], (0, -1, 0), (0, 0, 1), 0.0016, 0.008)
    lab = once(f"model_{code}.png", tex_text, label_lines, 1000, 200, sizes=[66, 40], bg=(236, 237, 236))
    k.decal(lab, (W / 2 - 0.13, door_y - 0.0007, zc + 0.012), (0, -1, 0), (0, 0, 1), 0.19, 0.038)
    asset_tag(k, code, "AICOR storage ST01", (W / 2 - 0.13, door_y - 0.0007, zc - 0.03), w=0.06)
    return (dx, door_y - 0.004, zc)


def _wire_shelf(k, x0, x1, y0, y1, z):
    m = "StainlessSatin"
    k.tube(m, [(x0, y0, z - 0.003), (x1, y0, z - 0.003), (x1, y1, z - 0.003), (x0, y1, z - 0.003), (x0, y0, z - 0.003)],
           0.003, seg=8)
    for x in np.arange(x0 + 0.02, x1 - 0.01, 0.021):
        k.cyl(m, (x, y0, z - 0.0018), (x, y1, z - 0.0018), 0.0018, seg=6, caps=False)
    for y in (y0 + 0.08, (y0 + y1) / 2, y1 - 0.08):
        k.cyl(m, (x0, y, z - 0.0052), (x1, y, z - 0.0052), 0.0025, seg=6, caps=False)
    for e in (x0, x1):
        for y in (y0 + 0.03, y1 - 0.03):
            k.box_between("PlasticWhite", (min(e, e - np.sign(e) * 0.012), y - 0.01, z - 0.016),
                          (max(e, e - np.sign(e) * 0.012), y + 0.01, z - 0.006))


def _fridge_level(k, rng, z, hmax, y0, y1, xw):
    """Bottles in front, boxes / more bottles behind, on one fridge level."""
    med = once("lab_medium500.png", tex_text, ["Medium", "500 mL  |  AICOR"], 500, 240, sizes=[84, 50])
    med1 = once("lab_medium1000.png", tex_text, ["Medium", "1000 mL  |  AICOR"], 500, 240, sizes=[84, 50])
    rea = once("lab_reagent.png", tex_text, ["Reagent", "keep closed"], 500, 240, sizes=[84, 50])
    box_lab = once("lab_reagentbox.png", tex_text, ["Reagent box", "store at +4 °C"], 640, 300, sizes=[76, 46])
    big = hmax > 0.26 and rng.random() < 0.5
    R, H, lab = (0.0505, 0.215, med1) if big else (0.043, 0.168, med)
    n = int(min(4, (2 * xw) // (2 * R + 0.02)))
    xs = np.linspace(-xw + R + 0.01, xw - R - 0.01, n) if n > 1 else [0.0]
    for x in xs:
        if rng.random() < 0.85:
            glass_bottle(k, (x + rng.uniform(-0.006, 0.006), y0 + R + 0.012, z), R, H, 0.0225, liquid="MediumPink",
                         fill=rng.uniform(0.72, 0.97), label=lab, label_ang=-math.pi / 2 + rng.uniform(-0.35, 0.35))
    # back row
    x = -xw + 0.01
    while x < xw - 0.08:
        if rng.random() < 0.5 and hmax > 0.16:
            Ra = 0.035
            glass_bottle(k, (x + Ra, y1 - 0.06 - rng.uniform(0, 0.05), z), Ra, 0.135, 0.016, glass="GlassAmber",
                         cap="PlasticBlack", label=rea, label_ang=-math.pi / 2 + rng.uniform(-0.4, 0.4))
            x += 2 * Ra + 0.02
        else:
            bw, bd, bh = 0.17, 0.12, 0.075
            if x + bw > xw:
                break
            nst = 2 if hmax > 0.2 and rng.random() < 0.5 else 1
            for s in range(nst):
                with k.at((x + bw / 2, y1 - bd / 2 - 0.02, z + s * (bh + 0.001)), rng.uniform(-3, 3)):
                    k.rbox("PaperWhite", (0, 0, bh / 2), (bw, bd, bh), r=0.0025, seg=1)
                    k.decal(box_lab, (0, -bd / 2 - 0.0007, bh / 2), (0, -1, 0), (0, 0, 1), 0.11, 0.052)
            x += bw + 0.02


def build_lab_fridge(k, seed=1, code="ST01-F1"):
    W, D, H = 0.6, 0.65, 1.85
    dy = -D / 2               # door front plane
    yb = dy + 0.055           # body front face
    z0, z1 = 0.13, 1.695      # door
    cx1, cz0, cz1 = 0.25, 0.20, 1.64
    _upright_shell(k, W, D, H, dy, z0, z1, hollow=((-cx1, cx1), (cz0, cz1)))
    # --- glass door: aluminium frame, double glazing with dark spacer, gasket, handle, lock, hinge caps
    fr = "AluAnodized"
    k.box_between(fr, (-0.297, dy, z0), (-0.252, yb - 0.006, z1), r=0.003, seg=2)
    k.box_between(fr, (0.252, dy, z0), (0.297, yb - 0.006, z1), r=0.003, seg=2)
    k.box_between(fr, (-0.256, dy, z0), (0.256, yb - 0.006, 0.225), r=0.003, seg=2)
    k.box_between(fr, (-0.256, dy, 1.645), (0.256, yb - 0.006, z1), r=0.003, seg=2)
    for (ya, yb_) in ((dy + 0.009, dy + 0.0145), (dy + 0.035, dy + 0.0405)):
        k.box_between("GlassClear", (-0.262, ya, 0.215), (0.262, yb_, 1.655))
    for lo, hi in (((-0.2525, dy + 0.0146, 0.224), (-0.244, dy + 0.0349, 1.646)),
                   ((0.244, dy + 0.0146, 0.224), (0.2525, dy + 0.0349, 1.646)),
                   ((-0.2525, dy + 0.0146, 0.2245), (0.2525, dy + 0.0349, 0.233)),
                   ((-0.2525, dy + 0.0146, 1.637), (0.2525, dy + 0.0349, 1.6455))):
        k.box_between("AluDark", lo, hi)
    _door_gasket(k, -0.293, 0.293, z0 + 0.004, z1 - 0.004, yb)
    k.handle_bar("Chrome", (-0.275, dy, 1.0), 0.32, standoff=0.032, r=0.0075)
    k.cyl("Chrome", (-0.205, dy, 0.177), (-0.205, dy - 0.006, 0.177), 0.009, seg=20, r_edge=0.0015)
    quads(k, "PlasticBlack", [(-0.205, dy - 0.0066, 0.177)], (0, -1, 0), (0, 0, 1), 0.0016, 0.008)
    for z in (z1 - 0.03, z0 + 0.03):
        k.box_between("PlasticGrey", (0.268, dy - 0.006, z - 0.03), (0.297, dy, z + 0.03), r=0.003, seg=1)
    # --- interior: LED strips, evaporator cover, shelves, contents
    for e in (-1, 1):
        x = e * (cx1 - 0.008)
        k.box_between("PlasticWhite", (min(x, e * (cx1 - 0.003)), yb + 0.006, 0.26),
                      (max(x, e * (cx1 - 0.003)), yb + 0.024, 1.58), r=0.002, seg=1)
        k.decal(once("led_white.png", lambda p: _save(Image.new("RGB", (16, 256), (255, 250, 240)), p)),
                (x - e * 0.0006, yb + 0.015, 0.92), (-e, 0, 0), (0, 0, 1), 0.009, 1.30, emissive=700)
    k.box_between("PlasticWhite", (-0.20, D / 2 - 0.13, 1.47), (0.20, D / 2 - 0.058, cz1 - 0.003), r=0.004, seg=1)
    quads(k, "PlasticBlack", grid((0, D / 2 - 0.1306, 1.555), (0, -1, 0), (0, 0, 1), 1, 7, 0, 0.018), (0, -1, 0),
          (0, 0, 1), 0.32, 0.007)
    levels = [cz0 + 0.003, 0.47, 0.75, 1.03, 1.31]
    rng = np.random.default_rng(seed)
    locs = []
    for i, z in enumerate(levels):
        if i > 0:
            _wire_shelf(k, -cx1 + 0.004, cx1 - 0.004, yb + 0.012, D / 2 - 0.065, z)
        top = levels[i + 1] - 0.012 if i + 1 < len(levels) else 1.46
        _fridge_level(k, rng, z + 0.0006, top - z, yb + 0.02, D / 2 - 0.07, cx1 - 0.012)
        locs.append(f"{code}-S{i + 1}")
        k.frame(f"loc_S{i + 1}", (0, (yb + D / 2 - 0.06) / 2, z))
    disp = _fridge_panel(k, W, dy, 1.775, code, ["+4 °C", "set  +4.0 °C", "door closed  |  alarm armed"],
                         ["Laboratory refrigerator", "+4 °C  |  glass door"])
    k.frame("handle", (-0.275, dy - 0.032, 1.0))
    k.frame("display", disp)
    k.collide((0, 0, H / 2), (W, D, H))
    return {"sdt:assetId": code, "sdt:class": "lab_refrigerator",
            "sdt:role": "+4 °C glass-door laboratory refrigerator storing media and reagent bottles for the cell.",
            "sdt:storageLocations": locs}


def build_freezer_m20(k, code="ST01-F2"):
    W, D, H = 0.6, 0.65, 1.85
    dy = -D / 2
    yb = dy + 0.055
    z0, z1 = 0.13, 1.695
    _upright_shell(k, W, D, H, dy, z0, z1)
    k.box_between("PowderWhite", (-0.297, dy, z0), (0.297, yb - 0.006, z1), r=0.008, seg=3)
    _door_gasket(k, -0.293, 0.293, z0 + 0.004, z1 - 0.004, yb)
    # recessed vertical handle strip + bar handle
    k.box_between("PlasticGrey", (-0.292, dy - 0.004, 0.75), (-0.262, dy + 0.002, 1.35), r=0.003, seg=1)
    k.handle_bar("PlasticGrey", (-0.277, dy - 0.004, 1.05), 0.5, standoff=0.03, r=0.009)
    k.cyl("Chrome", (-0.277, dy - 0.004, 0.70), (-0.277, dy - 0.010, 0.70), 0.009, seg=20, r_edge=0.0015)
    quads(k, "PlasticBlack", [(-0.277, dy - 0.0106, 0.70)], (0, -1, 0), (0, 0, 1), 0.0016, 0.008)
    for z in (z1 - 0.03, z0 + 0.03):
        k.box_between("PlasticGrey", (0.268, dy - 0.006, z - 0.03), (0.297, dy, z + 0.03), r=0.003, seg=1)
    k.decal(once("frz_note.png", tex_text, ["-20 °C", "keep door closed"], 600, 300, sizes=[110, 46], center=True),
            (0.0, dy - 0.0007, 1.45), (0, -1, 0), (0, 0, 1), 0.12, 0.06)
    disp = _fridge_panel(k, W, dy, 1.775, code, ["-20 °C", "set  -20.0 °C", "door closed  |  alarm armed"],
                         ["Laboratory freezer", "-20 °C  |  5 drawers"])
    locs = []
    for i, z in enumerate((0.25, 0.53, 0.81, 1.09, 1.37)):
        locs.append(f"{code}-D{i + 1}")
        k.frame(f"loc_D{i + 1}", (0, 0.0, z))
    k.frame("handle", (-0.277, dy - 0.034, 1.05))
    k.frame("display", disp)
    k.collide((0, 0, H / 2), (W, D, H))
    return {"sdt:assetId": code, "sdt:class": "lab_freezer",
            "sdt:role": "-20 °C upright laboratory freezer with five internal drawers for reagent storage.",
            "sdt:storageLocations": locs}


def build_ult_freezer(k, code="ST01-F3"):
    W, D, H = 0.87, 0.89, 1.98
    dy = -D / 2
    yb = dy + 0.075
    zb = 0.11
    k.box_between("PowderWhite", (-W / 2, yb, zb), (W / 2, D / 2, H), r=0.012, seg=2)
    # lower compressor section with front louvres
    k.box_between("PowderWhite", (-W / 2 + 0.002, dy + 0.004, zb + 0.004), (W / 2 - 0.002, yb + 0.004, 0.396),
                  r=0.008, seg=2)
    k.box_between("PlasticBlack", (-0.36, dy + 0.0005, 0.15), (0.36, dy + 0.006, 0.36))
    for i in range(12):
        z = 0.158 + i * 0.0175
        with k.at((0, dy + 0.0, z), R=rot_x(-20)):
            k.box_between("PowderWhite", (-0.36, -0.002, -0.004), (0.36, 0.006, 0.004), r=0.0012, seg=1)
    # door
    z0, z1 = 0.402, 1.68
    k.box_between("PowderWhite", (-W / 2 + 0.003, dy, z0), (W / 2 - 0.003, yb - 0.006, z1), r=0.016, seg=3)
    _door_gasket(k, -W / 2 + 0.01, W / 2 - 0.01, z0 + 0.006, z1 - 0.006, yb, w=0.016)
    k.box_between("PlasticGrey", (-W / 2 + 0.06, dy - 0.0006, z1 - 0.10), (W / 2 - 0.14, dy + 0.001, z1 - 0.094))
    # lever handle with lock (hinges left, handle right)
    hx = W / 2 - 0.07
    k.box_between("PowderAnthracite", (hx - 0.035, dy - 0.012, 0.86), (hx + 0.035, dy + 0.002, 1.30), r=0.008, seg=2)
    k.box_between("PlasticGrey", (hx - 0.022, dy - 0.07, 0.90), (hx + 0.022, dy - 0.035, 1.25), r=0.012, seg=2)
    k.box_between("PlasticGrey", (hx - 0.02, dy - 0.05, 1.21), (hx + 0.02, dy - 0.006, 1.27), r=0.008, seg=2)
    k.cyl("Chrome", (hx, dy - 0.012, 1.17), (hx, dy - 0.03, 1.17), 0.004, seg=12)
    k.cyl("Chrome", (hx, dy - 0.012, 0.885), (hx, dy - 0.02, 0.885), 0.011, seg=20, r_edge=0.0015)
    quads(k, "PlasticBlack", [(hx, dy - 0.0206, 0.885)], (0, -1, 0), (0, 0, 1), 0.002, 0.01)
    for z in (0.50, 1.58):  # hinges
        k.box_between("PowderAnthracite", (-W / 2 + 0.002, dy - 0.012, z - 0.07), (-W / 2 + 0.03, yb + 0.02, z + 0.07),
                      r=0.006, seg=2)
        k.cyl("Chrome", (-W / 2 + 0.016, dy - 0.006, z - 0.075), (-W / 2 + 0.016, dy - 0.006, z + 0.075), 0.007, seg=16)
    # fascia (darker) with touch display, key switch, USB, alarm LEDs, model label
    k.box_between("PowderAnthracite", (-W / 2 + 0.002, dy, 1.686), (W / 2 - 0.002, yb + 0.004, H - 0.002), r=0.012,
                  seg=2)
    disp = once(f"disp_{code}.png", decals.screen_device, ["-80 °C", "set  -80 °C  |  door closed",
                                                          "alarms armed", "ST01-F3"], 800, 500)
    screen_fy(k, disp, -0.17, dy, 1.835, 0.20, 0.125, em=450, bez=0.008)
    for i, m in enumerate(("IndicatorGreen", "PlasticOrange", "PlasticRed")):
        k.cyl(m, (0.02 + i * 0.022, dy, 1.89), (0.02 + i * 0.022, dy - 0.0025, 1.89), 0.0035, seg=12)
    k.cyl("Chrome", (0.04, dy, 1.80), (0.04, dy - 0.005, 1.80), 0.012, seg=20, r_edge=0.0015)
    quads(k, "PlasticBlack", [(0.04, dy - 0.0056, 1.80)], (0, -1, 0), (0, 0, 1), 0.002, 0.011)
    k.box_between("PlasticBlack", (0.07, dy - 0.003, 1.79), (0.10, dy, 1.81), r=0.002, seg=1)
    quads(k, "PlasticBlack", grid((0.18, dy - 0.0005, 1.84), (0, -1, 0), (0, 0, 1), 6, 6, 0.008, 0.008), (0, -1, 0),
          (0, 0, 1), 0.004, 0.004)
    lab = once("model_ult.png", tex_text, ["Ultra-low freezer", "-80 °C  |  upright"], 800, 200, sizes=[70, 40],
               bg=(205, 208, 212))
    k.decal(lab, (0.31, dy - 0.0007, 1.875), (0, -1, 0), (0, 0, 1), 0.17, 0.0425)
    asset_tag(k, code, "AICOR storage ST01", (0.31, dy - 0.0007, 1.79), w=0.07)
    # side access port (left wall) and rear condenser grille / power inlet
    k.cyl("PlasticGrey", (-W / 2, 0.10, 1.35), (-W / 2 - 0.03, 0.10, 1.35), 0.04, seg=28, r_edge=0.004)
    k.cyl("PlasticWhite", (-W / 2 - 0.03, 0.10, 1.35), (-W / 2 - 0.036, 0.10, 1.35), 0.028, seg=24, r_edge=0.002)
    quads(k, "PlasticBlack", grid((0, D / 2 + 0.0005, 0.42), (0, 1, 0), (0, 0, 1), 1, 22, 0, 0.022), (0, 1, 0),
          (0, 0, 1), 0.62, 0.009)
    k.box_between("PlasticBlack", (0.25, D / 2, 0.80), (0.33, D / 2 + 0.03, 0.88), r=0.004, seg=1)
    k.tube("PlasticBlack", [(0.29, D / 2 + 0.03, 0.84), (0.29, D / 2 + 0.06, 0.80), (0.29, D / 2 + 0.07, 0.02)], 0.005,
           seg=8)
    for x in (-W / 2 + 0.07, W / 2 - 0.07):
        for y in (dy + 0.12, D / 2 - 0.07):
            castor(k, x, y, wr=0.04, ww=0.03, brake=y < 0)
        foot(k, x, dy + 0.21, zb)
    k.frame("handle", (hx, dy - 0.07, 1.075))
    k.frame("display", (-0.17, dy - 0.004, 1.835))
    locs = []
    for i, z in enumerate((0.52, 0.76, 1.00, 1.24, 1.48)):
        locs.append(f"{code}-C{i + 1}")
        k.frame(f"loc_C{i + 1}", (0, 0.0, z))
    k.collide((0, 0.0, H / 2), (W, D, H))
    return {"sdt:assetId": code, "sdt:class": "ult_freezer",
            "sdt:role": "-80 °C upright ultra-low-temperature freezer with five inner compartments (closed door).",
            "sdt:storageLocations": locs}


# =============================================================================================== 5 LN2 dewar
def build_ln2_dewar(k, code="ST01-N1"):
    R = 0.325
    # 5-castor roller base
    top = 0
    for i in range(5):
        a = math.radians(90 + 72 * i)
        top = castor(k, 0.27 * math.cos(a), 0.27 * math.sin(a), wr=0.032, ww=0.024, yaw=math.degrees(a) + 90)
    k.lathe("StainlessSatin", [(0.0, top), (0.33, top), (0.345, top + 0.004), (0.35, top + 0.012), (0.35, top + 0.045),
                               (0.343, top + 0.05), (0.334, top + 0.045), (0.334, top + 0.02), (0.0, top + 0.02)],
            seg=48, smooth=False)
    zb = top + 0.02
    rn = 0.115
    prof = [(0.0, zb + 0.002), (R - 0.05, zb), (R - 0.012, zb + 0.006), (R, zb + 0.03), (R, zb + 0.72)]
    for a in np.linspace(0.1, math.pi / 2, 9):
        prof.append((rn + 0.03 + (R - rn - 0.03) * math.cos(a), zb + 0.72 + 0.13 * math.sin(a)))
    prof += [(rn + 0.025, zb + 0.855), (rn + 0.025, zb + 0.915), (rn + 0.04, zb + 0.918), (rn + 0.04, zb + 0.935),
             (rn + 0.03, zb + 0.938), (rn, zb + 0.938), (rn, zb + 0.85), (0.0, zb + 0.85)]
    k.lathe("StainlessBrushed", prof, (0, 0, 0), seg=64)
    zt = zb + 0.938
    # insulated lid with handle and lock
    k.lathe("PlasticGrey", [(0.0, zt - 0.03), (rn - 0.004, zt - 0.03), (rn - 0.004, zt), (0.168, zt + 0.001),
                            (0.17, zt + 0.006), (0.17, zt + 0.045), (0.16, zt + 0.06), (0.12, zt + 0.07), (0.0, zt + 0.074)],
            seg=48)
    k.handle_bar("PlasticBlack", (0, 0, zt + 0.07), 0.14, axis=(1, 0, 0), standoff=0.035, r=0.008, normal=(0, 0, 1))
    k.lathe("PlasticBlack", [(0.04, zt + 0.0715), (0.045, zt + 0.075), (0.0, zt + 0.076)], (0, 0, 0), seg=24)
    # hasp + padlock at front
    k.box_between("Chrome", (-0.012, -0.172, zt + 0.01), (0.012, -0.169, zt + 0.045), r=0.001, seg=1)
    k.box_between("Chrome", (-0.012, -(rn + 0.044), zt - 0.04), (0.012, -(rn + 0.041), zt - 0.005), r=0.001, seg=1)
    k.box_between("PlasticRed", (-0.016, -0.19, zt - 0.03), (0.016, -0.175, zt + 0.005), r=0.004, seg=2)
    k.tube("Chrome", [(-0.009, -0.1825, zt + 0.004), (-0.009, -0.1825, zt + 0.02), (0.0, -0.1825, zt + 0.028),
                      (0.009, -0.1825, zt + 0.02), (0.009, -0.1825, zt + 0.004)], 0.0025, seg=8)
    # lifting handles on the shoulder
    for s in (-1, 1):
        k.tube("StainlessSatin", [(s * 0.28, -0.07, zb + 0.74), (s * 0.31, -0.07, zb + 0.80), (s * 0.31, 0.07, zb + 0.80),
                                  (s * 0.28, 0.07, zb + 0.74)], 0.009, seg=12)
    # level-monitor controller on a bracket (front right), cable to the lid sensor port
    phi = math.radians(-58)
    with k.at(((R + 0.002) * math.cos(phi), (R + 0.002) * math.sin(phi), zb + 0.62), yaw=math.degrees(phi) + 90):
        for x in (-0.05, 0.044):   # bracket straps against the vessel wall
            k.box_between("StainlessSatin", (x, -0.017, -0.075), (x + 0.006, 0.004, 0.09), r=0.001, seg=1)
        k.box_between("StainlessSatin", (-0.06, -0.017, -0.075), (0.06, -0.014, 0.06), r=0.001, seg=1)
        with k.at((0, -0.017, 0)):
            k.box_between("PlasticGrey", (-0.08, -0.065, -0.07), (0.08, 0.0, 0.07), r=0.008, seg=2)
            lv = once("disp_ln2.png", decals.screen_device, ["LN2 level", "level OK  |  lid closed", "alarms armed"])
            screen_fy(k, lv, -0.025, -0.065, 0.02, 0.07, 0.044, em=400)
            for i in range(3):
                button_fy(k, 0.035 + i * 0.016, -0.065, 0.025, r=0.0045, mat="PlasticBlue")
            k.cyl("IndicatorGreen", (0.035, -0.065, -0.01), (0.035, -0.0675, -0.01), 0.0028, seg=12)
            k.cyl("PlasticRed", (0.051, -0.065, -0.01), (0.051, -0.0675, -0.01), 0.0028, seg=12)
            k.decal(once("lab_ln2mon.png", tex_text, ["LN2 level monitor", "AICOR ST01-N1"], 700, 160, sizes=[56, 36]),
                    (0.0, -0.0657, -0.045), (0, -1, 0), (0, 0, 1), 0.12, 0.0274)
            k.cyl("PlasticBlack", (0.05, -0.035, 0.07), (0.05, -0.035, 0.085), 0.006, seg=12)
            k.frame("display", (-0.025, -0.0686, 0.02))
    cx_, cy_ = (R - 0.03) * math.cos(phi), (R - 0.03) * math.sin(phi)
    g = np.array([(R + 0.002) * math.cos(phi), (R + 0.002) * math.sin(phi), zb + 0.62])
    g += rot_z(math.degrees(phi) + 90) @ np.array([0.05, -0.052, 0.085])
    k.tube("PlasticBlack", [tuple(g), tuple(g + (0, 0, 0.03)), (g[0] * 0.97, g[1] * 0.97, g[2] + 0.06),
                            (cx_, cy_, zb + 0.78), (0.6 * cx_, 0.6 * cy_, zb + 0.86), (0.10, -0.08, zt + 0.02),
                            (0.08, -0.06, zt + 0.074)], 0.003, seg=8)
    # cryogenic warning sticker, product label, asset tag (wrapped on the vessel)
    warn = once("warn_ln2.png", decals.warning_sign, "cold", ["LN2 / cryogenic", "cold burns - wear face shield",
                                                               "ventilate the room"])
    curved_decal(k, warn, (0, 0), R + 0.0007, zb + 0.30, zb + 0.30 + 0.196, -math.pi / 2, 0.14, seg=12)
    lab = once("lab_ln2.png", tex_text, ["LIQUID NITROGEN", "cryogenic storage vessel  |  UN 1977"], 900, 200,
               sizes=[72, 38])
    curved_decal(k, lab, (0, 0), R + 0.0007, zb + 0.56, zb + 0.56 + 0.05, -math.pi / 2 - 0.55, 0.225, seg=14)
    tag = once(f"tag_{code}.png", tex_tag, code, "AICOR storage ST01")
    curved_decal(k, tag, (0, 0), R + 0.0007, zb + 0.22, zb + 0.22 + 0.028, -math.pi / 2 + 0.45, 0.07, seg=6)
    locs = []
    for i in range(6):
        a = math.radians(60 * i)
        locs.append(f"{code}-R{i + 1}")
        k.frame(f"loc_R{i + 1}", (0.17 * math.cos(a), 0.17 * math.sin(a), zb + 0.05))
    k.frame("handle", (0, 0, zt + 0.105))
    k.collide((0, 0, (zt + 0.11) / 2), (0.72, 0.72, zt + 0.11))
    return {"sdt:assetId": code, "sdt:class": "ln2_dewar",
            "sdt:role": "Liquid-nitrogen cryostorage vessel on a roller base with level monitor; six inner racks.",
            "sdt:storageLocations": locs}


# =============================================================================================== 6 O2 monitor
def build_o2_monitor(k, code="ST01-O2"):
    W, Dd, Hh = 0.20, 0.06, 0.25
    k.box_between("PlasticGrey", (-W / 2 - 0.01, -0.004, -Hh / 2 - 0.01), (W / 2 + 0.01, 0.0, Hh / 2 + 0.01), r=0.002,
                  seg=1)
    k.box_between("PlasticWhite", (-W / 2, -Dd, -Hh / 2), (W / 2, -0.004, Hh / 2), r=0.01, seg=3)
    k.box_between("PlasticGrey", (-W / 2 + 0.012, -Dd - 0.002, -0.002), (W / 2 - 0.012, -Dd + 0.004, 0.09), r=0.004,
                  seg=1)
    disp = once("disp_o2.png", decals.screen_device, ["20.9 % O2", "oxygen   |   normal", "sensor OK"])
    screen_fy(k, disp, 0, -Dd - 0.002, 0.045, 0.12, 0.075, em=450)
    k.cyl("IndicatorGreen", (-0.06, -Dd, -0.025), (-0.06, -Dd - 0.002, -0.025), 0.0035, seg=12)
    k.cyl("PlasticOrange", (-0.04, -Dd, -0.025), (-0.04, -Dd - 0.002, -0.025), 0.0035, seg=12)
    k.cyl("PlasticRed", (-0.02, -Dd, -0.025), (-0.02, -Dd - 0.002, -0.025), 0.0035, seg=12)
    for i in range(2):
        button_fy(k, 0.035 + i * 0.03, -Dd, -0.025, r=0.008, mat="PlasticGrey")
    quads(k, "PlasticBlack", grid((0, -Dd - 0.0005, -0.075), (0, -1, 0), (0, 0, 1), 1, 5, 0, 0.007), (0, -1, 0),
          (0, 0, 1), 0.07, 0.003)
    k.decal(once("lab_o2.png", tex_text, ["O2 depletion monitor", "evacuate on alarm"], 800, 160, sizes=[56, 38]),
            (0, -Dd - 0.0006, -0.105), (0, -1, 0), (0, 0, 1), 0.15, 0.03)
    # beacon on top
    zt = Hh / 2
    k.cyl("PlasticBlack", (0, -Dd / 2, zt - 0.002), (0, -Dd / 2, zt + 0.018), 0.028, seg=24, r_edge=0.002)
    k.lathe("StackRed", [(0.0, zt + 0.018), (0.024, zt + 0.018), (0.024, zt + 0.05), (0.02, zt + 0.064),
                         (0.012, zt + 0.071), (0.0, zt + 0.073)], (0, -Dd / 2, 0), seg=24)
    # cable gland + conduit down the wall
    k.cyl("PlasticGrey", (0, -0.025, -Hh / 2), (0, -0.025, -Hh / 2 - 0.02), 0.009, seg=6)
    k.tube("PlasticGrey", [(0, -0.025, -Hh / 2 - 0.02), (0, -0.022, -Hh / 2 - 0.05), (0, -0.012, -Hh / 2 - 0.08),
                           (0, -0.012, -Hh / 2 - 0.40)], 0.008, seg=10)
    asset_tag(k, code, "AICOR safety", (0.0, -0.0006 - 0.004, Hh / 2 + 0.0) if False else (0.07, -Dd - 0.0006, -0.06),
              w=0.04)
    k.frame("display", (0, -Dd - 0.006, 0.045))
    k.collide((0, -Dd / 2, 0.02), (W + 0.02, Dd, Hh + 0.1))
    return {"sdt:assetId": code, "sdt:class": "o2_depletion_monitor",
            "sdt:role": "Wall-mounted oxygen-depletion monitor with beacon guarding the LN2 / CO2 storage room."}


# =============================================================================================== 7 gas cabinet
def build_gas_cabinet(k, code="ST01-G1"):
    W, D, H = 0.6, 0.5, 1.95
    dy = -D / 2
    yb = dy + 0.035
    M = "PowderGrey"
    # carcass
    k.box_between(M, (-W / 2, yb, 0.0), (-W / 2 + 0.025, D / 2, H), r=0.004, seg=2)
    k.box_between(M, (W / 2 - 0.025, yb, 0.0), (W / 2, D / 2, H), r=0.004, seg=2)
    k.box_between(M, (-W / 2 + 0.024, D / 2 - 0.025, 0.003), (W / 2 - 0.024, D / 2 - 0.002, H - 0.003))
    k.box_between(M, (-W / 2 + 0.024, yb, 0.003), (W / 2 - 0.024, D / 2 - 0.024, 0.06))
    k.box_between(M, (-W / 2 + 0.024, yb, H - 0.05), (W / 2 - 0.024, D / 2 - 0.024, H - 0.003))
    k.box_between("Galvanized", (-W / 2 + 0.025, yb + 0.01, 0.06), (W / 2 - 0.025, D / 2 - 0.03, 0.062))
    # door with vision window (pieces overlap to hide rounded joins), safety glass, gasket trim
    wx, wz0, wz1 = 0.20, 0.80, 1.70
    dz0, dz1 = 0.006, H - 0.006
    k.box_between(M, (-W / 2 + 0.003, dy, dz0), (-wx, yb - 0.004, dz1), r=0.004, seg=2)
    k.box_between(M, (wx, dy, dz0), (W / 2 - 0.003, yb - 0.004, dz1), r=0.004, seg=2)
    k.box_between(M, (-wx - 0.012, dy, dz0), (wx + 0.012, yb - 0.004, wz0), r=0.004, seg=2)
    k.box_between(M, (-wx - 0.012, dy, wz1), (wx + 0.012, yb - 0.004, dz1), r=0.004, seg=2)
    k.box_between("SafetyGlass", (-wx - 0.01, dy + 0.012, wz0 - 0.01), (wx + 0.01, dy + 0.018, wz1 + 0.01))
    for lo, hi in (((-wx - 0.008, dy - 0.0015, wz0 - 0.008), (-wx + 0.004, dy + 0.012, wz1 + 0.008)),
                   ((wx - 0.004, dy - 0.0015, wz0 - 0.008), (wx + 0.008, dy + 0.012, wz1 + 0.008)),
                   ((-wx + 0.003, dy - 0.0015, wz0 - 0.008), (wx - 0.003, dy + 0.012, wz0 + 0.004)),
                   ((-wx + 0.003, dy - 0.0015, wz1 - 0.004), (wx - 0.003, dy + 0.012, wz1 + 0.008))):
        k.box_between("RubberBlack", lo, hi, r=0.002, seg=1)
    _door_gasket(k, -W / 2 + 0.006, W / 2 - 0.006, dz0 + 0.004, dz1 - 0.004, yb, w=0.01)
    quads(k, "PlasticBlack", grid((0, dy - 0.0005, 0.20), (0, -1, 0), (0, 0, 1), 1, 9, 0, 0.022), (0, -1, 0), (0, 0, 1),
          0.34, 0.009)
    # handle (right) with lock, hinges (left)
    k.box_between("PlasticBlack", (0.232, dy - 0.01, 0.98), (0.262, dy + 0.001, 1.14), r=0.004, seg=2)
    k.box_between("PlasticBlack", (0.236, dy - 0.03, 1.02), (0.258, dy - 0.009, 1.13), r=0.006, seg=2)
    k.cyl("Chrome", (0.247, dy - 0.01, 1.0), (0.247, dy - 0.016, 1.0), 0.0075, seg=18, r_edge=0.001)
    quads(k, "PlasticBlack", [(0.247, dy - 0.0166, 1.0)], (0, -1, 0), (0, 0, 1), 0.0015, 0.007)
    for z in (0.25, 1.0, 1.75):
        k.cyl("Chrome", (-W / 2 + 0.002, dy - 0.004, z - 0.045), (-W / 2 + 0.002, dy - 0.004, z + 0.045), 0.0075, seg=14)
    # decals: CO2 label, gas warning, purpose, asset tag
    k.decal(once("lab_co2_big.png", tex_text, ["CO2", "carbon dioxide | compressed gas"], 800, 300, sizes=[140, 44],
                 center=True), (0.0, dy - 0.0007, 1.83), (0, -1, 0), (0, 0, 1), 0.24, 0.09)
    k.decal(once("warn_gas.png", decals.warning_sign, "gas", ["Compressed gas", "secure cylinders with chains"]),
            (-0.10, dy - 0.0007, 0.55), (0, -1, 0), (0, 0, 1), 0.12, 0.168)
    k.decal(once("lab_co2_supply.png", tex_text, ["CO2 supply", "incubators  |  2 bar outlet"], 700, 240,
                 sizes=[70, 44]), (0.10, dy - 0.0007, 0.58), (0, -1, 0), (0, 0, 1), 0.15, 0.05)
    asset_tag(k, code, "AICOR storage ST01", (0.10, dy - 0.0007, 0.50), w=0.07)
    # two CO2 cylinders with valves, pigtails, chains, rack
    locs = []
    for i, cx in enumerate((-0.13, 0.13)):
        cy = 0.06
        z0 = 0.0625
        prof = [(0.0, z0), (0.05, z0), (0.064, z0 + 0.006), (0.07, z0 + 0.03), (0.07, z0 + 1.24)]
        for a in np.linspace(0.15, math.pi / 2, 7):
            prof.append((0.024 + 0.046 * math.cos(a), z0 + 1.24 + 0.12 * math.sin(a)))
        prof += [(0.022, z0 + 1.37), (0.0, z0 + 1.37)]
        k.lathe("PlasticGrey", prof, (cx, cy, 0), seg=40)
        zt = z0 + 1.37
        k.cyl("Chrome", (cx, cy, zt - 0.012), (cx, cy, zt + 0.03), 0.017, seg=18, r_edge=0.002)
        k.box_between("Chrome", (cx - 0.016, cy - 0.016, zt + 0.03), (cx + 0.016, cy + 0.016, zt + 0.085), r=0.003, seg=1)
        k.cyl("Chrome", (cx, cy, zt + 0.085), (cx, cy, zt + 0.10), 0.006, seg=12)
        k.cyl("PlasticBlack", (cx, cy, zt + 0.10), (cx, cy, zt + 0.112), 0.028, seg=24, r_edge=0.003)
        k.cyl("Chrome", (cx, cy + 0.016, zt + 0.06), (cx, cy + 0.04, zt + 0.06), 0.008, seg=12)
        k.tube("StainlessSatin", [(cx, cy + 0.04, zt + 0.06), (cx, cy + 0.08, zt + 0.065), (cx * 0.8, 0.17, zt + 0.10),
                                  (cx * 0.5, 0.20, zt + 0.12), (cx * 0.5, 0.215, zt + 0.12)], 0.003, seg=8)
        lab = once("lab_cyl_co2.png", tex_text, ["CO2", "UN 1013  |  2.2"], 400, 300, sizes=[120, 50], center=True)
        curved_decal(k, lab, (cx, cy), 0.0707, 1.15, 1.25, -math.pi / 2 + (0.25 if cx < 0 else -0.25), 0.10, seg=8)
        for hz in (0.95, 1.30):
            pts = [(cx - 0.077, 0.152, hz)]
            for a in np.linspace(math.pi, 2 * math.pi, 13):
                pts.append((cx + 0.077 * math.cos(a), cy + 0.077 * math.sin(a), hz))
            pts.append((cx + 0.077, 0.152, hz))
            chain(k, pts, mat="Chrome")
        locs.append(f"{code}-C{i + 1}")
        k.frame(f"loc_C{i + 1}", (cx, cy, z0))
    for hz in (0.95, 1.30):
        k.box_between("Galvanized", (-W / 2 + 0.025, 0.15, hz - 0.025), (W / 2 - 0.025, D / 2 - 0.025, hz + 0.025),
                      r=0.002, seg=1)
    k.box_between("StainlessSatin", (-0.10, 0.205, 1.53), (0.10, 0.225, 1.57), r=0.003, seg=1)
    k.tube("StainlessSatin", [(0.10, 0.215, 1.55), (0.20, 0.215, 1.55), (0.25, 0.20, 1.47), (0.26, 0.06, 1.41),
                              (0.268, 0.025, 1.40), (W / 2 - 0.02, 0.02, 1.40)], 0.005, seg=10)
    # extraction duct stub on top
    k.cyl("Galvanized", (0, 0.05, H - 0.002), (0, 0.05, H + 0.012), 0.075, seg=32, r_edge=0.002)
    k.cyl("Galvanized", (0, 0.05, H + 0.012), (0, 0.05, H + 0.16), 0.05, seg=32, caps=False)
    k.cyl("Galvanized", (0, 0.05, H + 0.10), (0, 0.05, H + 0.11), 0.052, seg=32, caps=False)
    k.disk("PlasticBlack", (0, 0.05, H + 0.15), 0.0495, seg=32)
    quads(k, "PlasticBlack", grid((0.0, -0.10, H + 0.0005), (0, 0, 1), (0, 1, 0), 6, 1, 0.04, 0), (0, 0, 1), (0, 1, 0),
          0.008, 0.06)
    # pressure regulator panel on the right side wall (+X)
    with k.at((W / 2, 0.02, 1.40), yaw=90):   # local -Y = world +X
        k.box_between("StainlessSatin", (-0.15, -0.006, -0.25), (0.15, 0.0, 0.22), r=0.003, seg=1)
        k.cyl("Chrome", (0.0, -0.006, 0.0), (0.0, -0.06, 0.0), 0.028, seg=24, r_edge=0.004)
        k.cyl("Chrome", (0.0, -0.06, 0.0), (0.0, -0.075, 0.0), 0.034, seg=24, r_edge=0.004)
        k.cyl("PlasticBlack", (0.0, -0.075, 0.0), (0.0, -0.11, 0.0), 0.028, seg=20, r_edge=0.004)
        g1 = once("gauge_hp.png", tex_gauge, "bar", 100)
        g2 = once("gauge_lp.png", tex_gauge, "bar", 10)
        for gx, gp, ang in ((-0.07, g1, 40), (0.07, g2, -60)):
            k.tube("Chrome", [(gx * 0.3, -0.04, 0.02), (gx * 0.8, -0.04, 0.06), (gx, -0.04, 0.085)], 0.005, seg=8)
            needle_gauge(k, gp, (gx, -0.066, 0.10), 0.032, ang)
        # outlet: ball valve and pipe stub going up
        k.tube("StainlessSatin", [(0.0, -0.04, 0.025), (0.0, -0.04, 0.16), (0.0, -0.04, 0.70)], 0.006, seg=12)
        k.box_between("Chrome", (-0.014, -0.054, 0.18), (0.014, -0.026, 0.22), r=0.003, seg=1)
        k.box_between("PlasticYellow", (-0.004, -0.09, 0.193), (0.004, -0.054, 0.207), r=0.002, seg=1)
        k.cyl("Chrome", (0.0, -0.04, 0.68), (0.0, -0.04, 0.70), 0.009, seg=6)
        k.decal(once("lab_reg.png", tex_text, ["CO2 2 bar", "to incubators"], 600, 220, sizes=[80, 46]),
                (0.0, -0.0066, -0.18), (0, -1, 0), (0, 0, 1), 0.12, 0.044)
        k.decal(once("warn_gas.png", decals.warning_sign, "gas", ["Compressed gas", "secure cylinders with chains"]),
                (-0.09, -0.0066, -0.12), (0, -1, 0), (0, 0, 1), 0.06, 0.084)
    k.frame("handle", (0.247, dy - 0.03, 1.07))
    k.collide((0, 0, H / 2), (W, D, H))
    k.collide((W / 2 + 0.05, 0.02, 1.45), (0.1, 0.32, 0.5))
    return {"sdt:assetId": code, "sdt:class": "gas_cylinder_cabinet",
            "sdt:role": "Ventilated gas-cylinder cabinet holding two CO2 cylinders that supply the incubators "
                        "via a side-mounted pressure regulator.",
            "sdt:storageLocations": locs}


# =============================================================================================== 8 dispatch bench
def build_dispatch_bench(k, code="S1"):
    W, D, H = 1.4, 0.7, 0.90
    k.box_between("StainlessWorktop", (-W / 2, -D / 2, H - 0.04), (W / 2, D / 2 - 0.012, H), r=0.004, seg=2)
    k.box_between("StainlessWorktop", (-W / 2, D / 2 - 0.014, H - 0.04), (W / 2, D / 2, H + 0.06), r=0.004, seg=2)
    for x in (-W / 2 + 0.045, W / 2 - 0.045):
        for y in (-D / 2 + 0.045, D / 2 - 0.045):
            k.box_between("StainlessBrushed", (x - 0.02, y - 0.02, 0.03), (x + 0.02, y + 0.02, H - 0.04), r=0.003, seg=2)
            foot(k, x, y, 0.035, r=0.022, mat="PlasticGrey")
    for y in (-D / 2 + 0.045, D / 2 - 0.045):
        k.box_between("StainlessBrushed", (-W / 2 + 0.065, y - 0.015, H - 0.07), (W / 2 - 0.065, y + 0.015, H - 0.04),
                      r=0.002, seg=1)
    for x in (-W / 2 + 0.045, W / 2 - 0.045):
        k.box_between("StainlessBrushed", (x - 0.015, -D / 2 + 0.065, H - 0.07), (x + 0.015, D / 2 - 0.065, H - 0.04),
                      r=0.002, seg=1)
    # undershelf with folded edge
    k.box_between("StainlessBrushed", (-W / 2 + 0.065, -D / 2 + 0.03, 0.20), (W / 2 - 0.065, D / 2 - 0.03, 0.215),
                  r=0.002, seg=1)
    k.box_between("StainlessBrushed", (-W / 2 + 0.065, -D / 2 + 0.03, 0.17), (W / 2 - 0.065, -D / 2 + 0.042, 0.215),
                  r=0.002, seg=1)
    # front apron with station plate
    k.box_between("StainlessBrushed", (-W / 2 + 0.065, -D / 2 + 0.002, H - 0.12), (W / 2 - 0.065, -D / 2 + 0.014, H - 0.04),
                  r=0.002, seg=1)
    plate = once("plate_S1.png", decals.station_plate, "S1", "AMR dispatch", sub="AICOR storage ST01")
    k.decal(plate, (-0.35, -D / 2 + 0.0014, H - 0.08), (0, -1, 0), (0, 0, 1), 0.20, 0.07)
    # staging nest: SBS carrier seat with 4 corner posts
    nx, ny = -0.22, -0.06
    zt = H
    k.box_between("StainlessSatin", (nx - 0.09, ny - 0.068, zt), (nx + 0.09, ny + 0.068, zt + 0.008), r=0.0015, seg=1)
    seat = zt + 0.008
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = nx + sx * 0.0655, ny + sy * 0.0445
            k.cyl("StainlessSatin", (px, py, seat), (px, py, seat + 0.014), 0.0045, seg=16, r_edge=0.0015)
            k.box_between("StainlessSatin", (min(px, px + sx * 0.012), min(py, py + sy * 0.012), seat),
                          (max(px, px + sx * 0.012), max(py, py + sy * 0.012), seat + 0.006), r=0.001, seg=1)
    k.disk("IndicatorGreen", (nx + 0.075, ny - 0.058, seat + 0.0005), 0.003, seg=12)
    k.decal(once("lab_nest.png", tex_text, ["S1-N1", "carrier nest"], 500, 200, sizes=[80, 40]),
            (nx, ny - 0.068 - 0.0006, zt + 0.004), (0, -1, 0), (0, 0, 1), 0.04, 0.0065)
    k.frame("staging_nest", (nx, ny, seat))
    # label printer
    px, py = 0.30, 0.05
    k.box_between("PlasticWhite", (px - 0.065, py - 0.11, zt + 0.006), (px + 0.065, py + 0.11, zt + 0.10), r=0.012, seg=3)
    k.box_between("PlasticGrey", (px - 0.064, py - 0.07, zt + 0.10), (px + 0.064, py + 0.105, zt + 0.15), r=0.015, seg=3)
    k.box_between("PlasticBlack", (px - 0.045, py - 0.1105, zt + 0.07), (px + 0.045, py - 0.106, zt + 0.076))
    with k.at((px, py - 0.112, zt + 0.073), R=rot_x(-12)):
        k.box_between("PaperWhite", (-0.04, -0.03, -0.0004), (0.04, 0.0, 0.0004))
    button_fy(k, px + 0.04, py - 0.11, zt + 0.04, r=0.006, mat="PlasticGrey")
    k.cyl("IndicatorGreen", (px + 0.02, py - 0.11, zt + 0.04), (px + 0.02, py - 0.1115, zt + 0.04), 0.0025, seg=10)
    for sx in (-1, 1):
        for sy in (-1, 1):
            k.box_between("RubberBlack", (px + sx * 0.05 - 0.008, py + sy * 0.09 - 0.008, zt),
                          (px + sx * 0.05 + 0.008, py + sy * 0.09 + 0.008, zt + 0.006))
    # handheld barcode scanner resting in its cradle
    sx_, sy_ = 0.52, -0.12
    k.box_between("PlasticBlack", (sx_ - 0.045, sy_ - 0.055, zt), (sx_ + 0.045, sy_ + 0.055, zt + 0.022), r=0.008, seg=2)
    with k.at((sx_, sy_ + 0.01, zt + 0.022), R=rot_x(-30)):
        k.box_between("PlasticBlack", (-0.03, -0.02, 0.0), (0.03, 0.025, 0.06), r=0.006, seg=2)
        k.box_between("PlasticGrey", (-0.019, -0.016, 0.01), (0.019, 0.018, 0.135), r=0.012, seg=3)    # grip
        k.box_between("PlasticGrey", (-0.032, -0.07, 0.125), (0.032, 0.03, 0.17), r=0.014, seg=3)     # head
        k.box_between("PlasticYellow", (-0.0325, -0.069, 0.14), (0.0325, -0.02, 0.155), r=0.004, seg=1)
        quads(k, "StackRed", [(0.0, -0.0705, 0.148)], (0, -1, 0), (0, 0, 1), 0.04, 0.02)
        k.box_between("PlasticBlack", (-0.007, -0.04, 0.105), (0.007, -0.016, 0.125), r=0.003, seg=1)  # trigger
    k.tube("PlasticBlack", [(sx_, sy_ + 0.055, zt + 0.011), (sx_, sy_ + 0.12, zt + 0.003), (sx_ - 0.05, sy_ + 0.2, zt + 0.003),
                            (sx_ - 0.10, 0.26, zt + 0.003)], 0.0025, seg=8)
    # monitor on pole arm clamped to the back edge
    mx = 0.0
    k.box_between("AluDark", (mx - 0.035, D / 2 - 0.05, H - 0.07), (mx + 0.035, D / 2 + 0.015, H + 0.075), r=0.004, seg=1)
    k.cyl("AluAnodized", (mx, D / 2 - 0.03, H + 0.075), (mx, D / 2 - 0.03, H + 0.52), 0.017, seg=24)
    k.cyl("PlasticBlack", (mx, D / 2 - 0.03, H + 0.52), (mx, D / 2 - 0.03, H + 0.53), 0.018, seg=24)
    k.cyl("AluDark", (mx, D / 2 - 0.03, H + 0.36), (mx, D / 2 - 0.03, H + 0.40), 0.024, seg=24, r_edge=0.003)
    k.box_between("AluDark", (mx - 0.016, 0.12, H + 0.365), (mx + 0.016, D / 2 - 0.03, H + 0.395), r=0.006, seg=2)
    k.box_between("AluDark", (mx - 0.035, 0.09, H + 0.34), (mx + 0.035, 0.125, H + 0.42), r=0.006, seg=2)
    with k.at((mx, 0.085, H + 0.38), R=rot_x(-6)):
        k.box_between("PlasticBlack", (-0.25, -0.022, -0.155), (0.25, 0.0, 0.155), r=0.006, seg=2)
        k.box_between("PlasticBlack", (-0.08, 0.0, -0.08), (0.08, 0.012, 0.08), r=0.006, seg=1)
        lst = once("screen_carriers.png", tex_carrier_list)
        k.decal(lst, (0, -0.0226, 0.006), (0, -1, 0), (0, 0, 1), 0.476, 0.2826, emissive=400)
        k.cyl("IndicatorGreen", (0.22, -0.022, -0.145), (0.22, -0.0228, -0.145), 0.0015, seg=8)
    # keyboard
    with k.at((0.16, -0.17, zt)):
        k.box_between("PlasticBlack", (-0.21, -0.065, 0.0), (0.21, 0.065, 0.016), r=0.004, seg=2)
        cen = []
        for row in range(5):
            for col in range(20):
                if col > 14 and row == 0:
                    continue
                cen.append((-0.19 + col * 0.0195 + (0.004 if row % 2 else 0), -0.045 + row * 0.0195, 0.0168))
        quads(k, "PlasticGrey", cen, (0, 0, 1), (0, 1, 0), 0.0165, 0.0165)
        k.box_between("PlasticBlack", (-0.09, -0.065, 0.016), (0.09, -0.0505, 0.0168))
    # undershelf: tote and spare label rolls box
    tx_, ty_ = -0.35, 0.0
    zb = 0.215
    for lo, hi in (((tx_ - 0.20, ty_ - 0.15, zb), (tx_ + 0.20, ty_ + 0.15, zb + 0.005)),
                   ((tx_ - 0.20, ty_ - 0.15, zb), (tx_ - 0.195, ty_ + 0.15, zb + 0.22)),
                   ((tx_ + 0.195, ty_ - 0.15, zb), (tx_ + 0.20, ty_ + 0.15, zb + 0.22)),
                   ((tx_ - 0.195, ty_ - 0.15, zb), (tx_ + 0.195, ty_ - 0.145, zb + 0.22)),
                   ((tx_ - 0.195, ty_ + 0.145, zb), (tx_ + 0.195, ty_ + 0.15, zb + 0.22))):
        k.box_between("PlasticBlue", lo, hi, r=0.002, seg=1)
    k.box_between("PlasticBlue", (tx_ - 0.205, ty_ - 0.155, zb + 0.205), (tx_ + 0.205, ty_ + 0.155, zb + 0.22), r=0.003,
                  seg=1)
    _carton(k, (0.30, 0.02, zb + 0.0005), (0.30, 0.25, 0.14), once("lab_labels.png", tex_consumable,
                                                                   "Thermal labels 50 x 25 mm", "12 rolls",
                                                                   "ST01-C201", (90, 90, 96)))
    k.frame("operator_position", (0, -D / 2 - 0.35, 0), yaw=90)
    k.collide((0, 0, (H + 0.06) / 2), (W, D, H + 0.06))
    return {"sdt:assetId": "ST01-S1", "sdt:class": "amr_dispatch_bench",
            "sdt:role": "Station S1: stainless bench where staff stage sample carriers for the clean-sample AMR, "
                        "with label printer, barcode scanner and carrier-queue monitor.",
            "sdt:station": code}


# =============================================================================================== 9 server rack
def _rack_unit(k, kind, z0, nu, rng, x0=-0.2413, x1=0.2413, yf=-0.40):
    U = 0.04445
    z1 = z0 + nu * U - 0.0008
    zc = (z0 + z1) / 2
    face = yf - 0.006
    if kind.startswith("blank"):
        k.box_between("PlasticBlack", (x0, face, z0 + 0.0004), (x1, yf, z1), r=0.0008, seg=1)
        quads(k, "PlasticGrey", grid((0, face - 0.0004, zc), (0, -1, 0), (0, 0, 1), 1, max(1, nu * 2), 0, U / 2),
              (0, -1, 0), (0, 0, 1), 0.40, 0.0008)
        return []
    mat = "AluDark" if kind in ("server", "server1", "gpu", "storage") else "PlasticBlack"
    k.box_between(mat, (x0, face, z0 + 0.0004), (x1, yf, z1), r=0.0012, seg=1)
    k.box_between("Galvanized", (-0.217, yf, z0 + 0.001), (0.217, 0.36, z1 - 0.001))
    fn = (0, -1, 0)
    up = (0, 0, 1)
    yq = face - 0.0004
    leds_g, leds_b = [], []
    if kind in ("server", "server1", "storage", "gpu"):
        for e in (-1, 1):   # rack ears with handles
            k.handle_bar("Chrome", (e * 0.228, face, zc), max(nu * U - 0.02, 0.02), standoff=0.012, r=0.0028)
    if kind == "server" or kind == "server1":
        nb = 8 if kind == "server" else 10
        bh = (nu * U - 0.012) if kind == "server" else 0.03
        bays = [(-0.19 + i * 0.019, yq, zc) for i in range(nb)]
        quads(k, "PlasticGrey", bays, fn, up, 0.016, bh)
        quads(k, "PlasticBlack", [(b[0], yq - 0.0004, b[2] - bh * 0.3) for b in bays], fn, up, 0.012, 0.003)
        leds_g += [(b[0] - 0.005, yq - 0.0004, b[2] + bh * 0.42) for b in bays if rng.random() < 0.9]
        leds_b += [(b[0] + 0.005, yq - 0.0004, b[2] + bh * 0.42) for b in bays if rng.random() < 0.15]
        quads(k, "PlasticBlack", grid((0.10, yq, zc), fn, up, 14, max(2, nu * 3), 0.0075, 0.009), fn, up, 0.005, 0.006)
        k.cyl("PlasticGrey", (0.205, face, zc), (0.205, face - 0.003, zc), 0.004, seg=12)
        leds_g.append((0.205, yq - 0.0004, zc + 0.009))
        leds_b.append((0.192, yq - 0.0004, zc + 0.009))
    elif kind == "storage":
        bays = [(-0.15 + i * 0.07, yq, z0 + 0.015 + j * 0.029) for i in range(4) for j in range(nu * U // 0.029 > 2 and 3 or 2)]
        quads(k, "PlasticGrey", bays, fn, up, 0.066, 0.026)
        quads(k, "PlasticBlack", [(b[0] + 0.012, yq - 0.0004, b[2]) for b in bays], fn, up, 0.032, 0.012)
        leds_g += [(b[0] - 0.028, yq - 0.0004, b[2] + 0.008) for b in bays]
        leds_b += [(b[0] - 0.028, yq - 0.0004, b[2] - 0.006) for b in bays if rng.random() < 0.2]
    elif kind == "gpu":
        quads(k, "PlasticBlack", grid((-0.02, yq, zc), fn, up, 40, nu * 4, 0.0095, 0.0095), fn, up, 0.0065, 0.0065)
        k.cyl("PlasticGrey", (0.205, face, zc + 0.05), (0.205, face - 0.003, zc + 0.05), 0.004, seg=12)
        leds_g += [(0.205, yq - 0.0004, zc + 0.03), (0.205, yq - 0.0004, zc + 0.02)]
        leds_b.append((0.205, yq - 0.0004, zc + 0.01))
    elif kind == "switch":
        ports = [(-0.20 + (i // 2) * 0.0155 + (i // 12) * 0.008, yq, zc + (0.0075 if i % 2 == 0 else -0.0075))
                 for i in range(48)]
        quads(k, "StainlessSatin", ports, fn, up, 0.0135, 0.0112)
        quads(k, "PlasticBlack", [(p[0], p[1] - 0.0004, p[2]) for p in ports], fn, up, 0.0115, 0.0092)
        sfp = [(0.17 + i * 0.016, yq, zc) for i in range(4)]
        quads(k, "StainlessSatin", sfp, fn, up, 0.0145, 0.010)
        quads(k, "PlasticBlack", [(p[0], p[1] - 0.0004, p[2]) for p in sfp], fn, up, 0.012, 0.0045)
        leds_g += [(p[0] + 0.0045, p[1] - 0.0008, p[2] + (0.0042 if p[2] > zc else -0.0042)) for p in ports
                   if rng.random() < 0.6]
        leds_b.append((0.225, yq - 0.0004, zc + 0.012))
        return ports
    elif kind == "patch":
        ports = [(-0.18 + i * 0.0155 + (i // 12) * 0.012, yq, zc - 0.002) for i in range(24)]
        quads(k, "PlasticBlack", [(p[0], p[1] + 0.0002, p[2]) for p in ports], fn, up, 0.012, 0.0105)
        quads(k, "PaperWhite", [(0.0, yq, zc + 0.0135)], fn, up, 0.40, 0.006)
        return ports
    elif kind == "brush":
        quads(k, "PlasticGrey", [(0.0, yq, zc)], fn, up, 0.42, 0.010)
        quads(k, "PlasticBlack", grid((0.0, yq - 0.0004, zc), fn, up, 80, 1, 0.0052, 0), fn, up, 0.0012, 0.0095)
    elif kind == "ups":
        quads(k, "PlasticBlack", grid((0.06, yq, zc), fn, up, 22, nu * 4, 0.0095, 0.0095), fn, up, 0.0065, 0.0065)
        ups = once("disp_ups.png", decals.screen_device, ["ONLINE", "battery OK", "AICOR twin compute"])
        screen_fy(k, ups, -0.15, face, zc + 0.01, 0.05, 0.031, em=350, bez=0.004)
        for i in range(3):
            button_fy(k, -0.105 + i * 0.012, face, zc - 0.03, r=0.004)
        leds_g.append((-0.105, yq - 0.0004, zc + 0.03))
    if leds_g:
        quads(k, "IndicatorGreen", leds_g, fn, up, 0.003, 0.0025)
    if leds_b:
        quads(k, "StackBlue", leds_b, fn, up, 0.003, 0.0025)
    return []


def build_server_rack(k, seed=3, code="ST01-IT1"):
    W, D, H = 0.6, 1.0, 2.0
    A = "PowderAnthracite"
    zb0, zb1 = 0.075, 0.115
    k.box_between(A, (-W / 2, -D / 2 + 0.002, zb0), (W / 2, D / 2 - 0.002, zb1), r=0.004, seg=1)
    k.box_between(A, (-W / 2, -D / 2, H - 0.05), (W / 2, D / 2, H), r=0.006, seg=2)
    for e in (-1, 1):
        k.box_between(A, (min(e * W / 2, e * (W / 2 - 0.016)), -D / 2 + 0.024, zb1 + 0.003),
                      (max(e * W / 2, e * (W / 2 - 0.016)), D / 2 - 0.024, H - 0.053), r=0.004, seg=2)
    # front glass door, rear perforated door
    dz0, dz1 = zb1 + 0.004, H - 0.054
    k.box_between(A, (-W / 2 + 0.002, -D / 2, dz0), (-W / 2 + 0.05, -D / 2 + 0.022, dz1), r=0.004, seg=2)
    k.box_between(A, (W / 2 - 0.05, -D / 2, dz0), (W / 2 - 0.002, -D / 2 + 0.022, dz1), r=0.004, seg=2)
    k.box_between(A, (-W / 2 + 0.04, -D / 2, dz0), (W / 2 - 0.04, -D / 2 + 0.022, dz0 + 0.07), r=0.004, seg=2)
    k.box_between(A, (-W / 2 + 0.04, -D / 2, dz1 - 0.07), (W / 2 - 0.04, -D / 2 + 0.022, dz1), r=0.004, seg=2)
    k.box_between("SafetyGlass", (-W / 2 + 0.045, -D / 2 + 0.008, dz0 + 0.06), (W / 2 - 0.045, -D / 2 + 0.013, dz1 - 0.06))
    quads(k, "PlasticBlack", grid((0, -D / 2 - 0.0005, dz0 + 0.035), (0, -1, 0), (0, 0, 1), 22, 2, 0.022, 0.018),
          (0, -1, 0), (0, 0, 1), 0.014, 0.006)
    quads(k, "PlasticBlack", grid((0, -D / 2 - 0.0005, dz1 - 0.035), (0, -1, 0), (0, 0, 1), 22, 2, 0.022, 0.018),
          (0, -1, 0), (0, 0, 1), 0.014, 0.006)
    k.box_between(A, (-W / 2 + 0.002, D / 2 - 0.022, dz0), (W / 2 - 0.002, D / 2, dz1), r=0.004, seg=2)
    vent = once("perf_dark.png", tex_vent)
    k.decal(vent, (0, D / 2 + 0.0006, (dz0 + dz1) / 2), (0, 1, 0), (0, 0, 1), W - 0.08, dz1 - dz0 - 0.12)
    # handle with lock (right), hinges (left)
    k.box_between("PlasticBlack", (W / 2 - 0.038, -D / 2 - 0.008, 0.95), (W / 2 - 0.012, -D / 2 + 0.001, 1.15), r=0.004,
                  seg=2)
    k.box_between("PlasticBlack", (W / 2 - 0.034, -D / 2 - 0.022, 0.99), (W / 2 - 0.016, -D / 2 - 0.007, 1.13),
                  r=0.005, seg=2)
    k.cyl("Chrome", (W / 2 - 0.025, -D / 2 - 0.008, 0.97), (W / 2 - 0.025, -D / 2 - 0.013, 0.97), 0.006, seg=16)
    for z in (0.3, 1.0, 1.75):
        k.cyl("Chrome", (-W / 2 + 0.004, -D / 2 - 0.003, z - 0.03), (-W / 2 + 0.004, -D / 2 - 0.003, z + 0.03), 0.006,
              seg=12)
    asset_tag(k, code, "AICOR twin compute", (0.0, -D / 2 - 0.0007, dz1 - 0.035 + 0.0), w=0.09)
    # 19" rails with square holes
    U = 0.04445
    z0 = 0.13
    nU = 40
    for yr in (-0.40, 0.33):
        for e in (-1, 1):
            k.box_between("AluDark", (min(e * 0.2325, e * 0.2525), yr, z0 - 0.01),
                          (max(e * 0.2325, e * 0.2525), yr + 0.015, z0 + nU * U + 0.01))
            holes = [(e * 0.2425, yr - 0.0004, z0 + u * U + f) for u in range(nU) for f in (0.0064, 0.0222, 0.0381)]
            quads(k, "PlasticBlack", holes, (0, -1, 0), (0, 0, 1), 0.0055, 0.0055)
    layout = [(1, 3, "ups"), (4, 1, "blank"), (5, 2, "server"), (7, 2, "server"), (9, 2, "server"), (11, 1, "blank"),
              (12, 4, "gpu"), (16, 4, "gpu"), (20, 2, "blank"), (22, 1, "server1"), (23, 1, "server1"), (24, 1, "blank"),
              (25, 2, "storage"), (27, 3, "blank"), (30, 1, "switch"), (31, 1, "brush"), (32, 1, "patch"),
              (33, 1, "switch"), (34, 1, "brush"), (35, 1, "patch"), (36, 5, "blank")]
    rng = np.random.default_rng(seed)
    ports = {}
    for u, n, kind in layout:
        ports[u] = _rack_unit(k, kind, z0 + (u - 1) * U, n, rng)
    # patch cords: patch panel -> brush -> switch
    cols = ["PlasticBlue", "PlasticYellow", "PlasticBlue", "PlasticGreen", "PlasticBlue", "PlasticRed"]
    for sw, br, pp in ((30, 31, 32), (33, 34, 35)):
        zb_ = z0 + (br - 1) * U + U / 2
        sel = sorted(rng.choice(24, size=int(rng.integers(10, 18)), replace=False))
        for j, i in enumerate(sel):
            mcol = cols[int(rng.integers(len(cols)))]
            p = ports[pp][i]
            s = ports[sw][int(min(47, i * 2 + rng.integers(0, 2)))]
            for (q, dz) in ((p, 1), (s, -1)):
                k.box_between(mcol, (q[0] - 0.0055, q[1] - 0.022, q[2] - 0.0045), (q[0] + 0.0055, q[1] - 0.001,
                                                                                       q[2] + 0.0045), r=0.0015, seg=1)
            xm = (p[0] + s[0]) / 2
            k.tube(mcol, [(p[0], p[1] - 0.022, p[2]), (p[0], p[1] - 0.04, p[2] - 0.004),
                          (xm, -0.425 - 0.002 * (j % 5), zb_ + 0.004), (xm, -0.405, zb_),
                          (xm, -0.425 - 0.002 * (j % 5), zb_ - 0.004),
                          (s[0], s[1] - 0.04, s[2] + 0.004), (s[0], s[1] - 0.022, s[2])], 0.0022, seg=6)
    # vertical cable bundles both sides with straps
    for e in (-1, 1):
        for j in range(6):
            mcol = ["PlasticBlack", "PlasticBlue", "PlasticBlack", "PlasticGrey", "PlasticBlue", "PlasticBlack"][j]
            x = e * (0.266 + 0.006 * (j % 3))
            y = -0.36 + 0.007 * (j // 3)
            k.tube(mcol, [(x, y, H - 0.06), (x, y, 0.5), (x - e * 0.01, y + 0.02, 0.3), (x - e * 0.04, y + 0.15, 0.2)],
                   0.0035, seg=6)
        for z in np.arange(0.6, 1.9, 0.3):
            k.cyl("PlasticBlack", (e * 0.272, -0.353, z), (e * 0.272, -0.353, z + 0.012), 0.017, seg=12, caps=False)
    # top: fan grilles + cable entry brush
    for x in (-0.12, 0.12):
        k.disk("PlasticBlack", (x, 0.15, H + 0.0005), 0.06, seg=32)
        for r in (0.02, 0.035, 0.05):
            k.disk("AluDark", (x, 0.15, H + 0.0009), r + 0.002, seg=32, r_in=r)
    k.quad("PlasticBlack", (0, -0.30, H + 0.0005), (0, 0, 1), (0, 1, 0), 0.35, 0.05)
    # castors and levelling feet
    for x in (-W / 2 + 0.06, W / 2 - 0.06):
        for y in (-D / 2 + 0.08, D / 2 - 0.08):
            castor(k, x, y, wr=0.025, ww=0.022, yaw=0)
            foot(k, x, y + (0.07 if y < 0 else -0.07), zb0, r=0.02)
    k.frame("handle", (W / 2 - 0.025, -D / 2 - 0.022, 1.06))
    k.collide((0, 0, H / 2), (W, D, H))
    return {"sdt:assetId": code, "sdt:class": "server_rack",
            "sdt:role": "19-inch rack cabinet hosting the twin compute servers, GPU nodes, storage and network "
                        "switches for the lab automation."}


# =============================================================================================== 10 building services
def build_smoke_detector(k, code="BS-SD"):
    k.lathe("PlasticWhite", [(0.0, 0.0), (0.054, 0.0), (0.056, -0.006), (0.055, -0.016), (0.0, -0.016)],
            (0, 0, 0), seg=48, smooth=False)
    k.lathe("PlasticWhite", [(0.0, -0.0485), (0.022, -0.048), (0.040, -0.044), (0.046, -0.038), (0.047, -0.024),
                             (0.049, -0.018), (0.050, -0.0161), (0.0, -0.0161)], (0, 0, 0), seg=48)
    for i in range(24):
        a = 2 * math.pi * i / 24
        n = (math.cos(a), math.sin(a), 0)
        quads(k, "PlasticGrey", [(0.0476 * n[0], 0.0476 * n[1], -0.031)], n, (0, 0, 1), 0.007, 0.011)
    k.cyl("IndicatorRed", (0.025, 0.0, -0.0465), (0.025, 0.0, -0.0485), 0.0018, seg=10)
    k.disk("PlasticGrey", (0, 0, -0.0488), 0.012, normal=(0, 0, -1), seg=24)
    k.collide((0, 0, -0.025), (0.11, 0.11, 0.05))
    return {"sdt:assetId": code, "sdt:class": "smoke_detector",
            "sdt:role": "Ceiling-mounted optical smoke detector (building fire alarm system)."}


def build_sprinkler_head(k, code="BS-SPR"):
    k.lathe("Chrome", [(0.0, -0.003), (0.030, -0.003), (0.032, -0.006), (0.030, -0.008), (0.012, -0.012),
                       (0.0, -0.012)], (0, 0, 0), seg=40)
    k.cyl("Chrome", (0, 0, 0.0), (0, 0, -0.02), 0.0095, seg=6)
    k.cyl("Chrome", (0, 0, -0.02), (0, 0, -0.026), 0.008, seg=20)
    for s in (-1, 1):
        k.tube("Chrome", [(s * 0.006, 0, -0.024), (s * 0.010, 0, -0.035), (s * 0.010, 0, -0.050), (s * 0.003, 0, -0.058)],
               0.0018, seg=8)
    k.lathe("PlasticRed", [(0.0, -0.051), (0.0022, -0.050), (0.0028, -0.040), (0.0022, -0.030), (0.0, -0.029)],
            (0, 0, 0), seg=16)
    k.cyl("Chrome", (0, 0, -0.056), (0, 0, -0.060), 0.004, seg=12)
    k.lathe("Chrome", [(0.0, -0.0612), (0.0125, -0.0612), (0.0128, -0.0602), (0.0, -0.0600)], (0, 0, 0), seg=32)
    for i in range(16):
        a = 2 * math.pi * i / 16
        quads(k, "PlasticBlack", [(0.010 * math.cos(a), 0.010 * math.sin(a), -0.0614)], (0, 0, -1),
              (math.cos(a), math.sin(a), 0), 0.0012, 0.004)
    k.collide((0, 0, -0.03), (0.065, 0.065, 0.06))
    return {"sdt:assetId": code, "sdt:class": "sprinkler_head",
            "sdt:role": "Pendent fire sprinkler head with glass bulb and escutcheon (building fire protection)."}


def build_hvac_diffuser(k, code="BS-DIF"):
    S = 0.595
    k.box_between("PowderWhite", (-S / 2, -S / 2, -0.010), (S / 2, S / 2, 0.0), r=0.003, seg=1)
    k.box_between("PowderWhite", (-0.285, -0.285, -0.014), (0.285, 0.285, -0.009), r=0.002, seg=1)
    n = 48
    for ring, (r0, r1) in enumerate(((0.10, 0.17), (0.18, 0.25))):
        for i in range(n if ring else n // 2):
            a = 2 * math.pi * (i + 0.5 * ring) / (n if ring else n // 2)
            rm = (r0 + r1) / 2
            c = (rm * math.cos(a), rm * math.sin(a), -0.0144)
            radial = (math.cos(a + 0.35), math.sin(a + 0.35), 0)
            quads(k, "PlasticBlack", [c], (0, 0, -1), radial, 0.009, r1 - r0)
            quads(k, "PlasticGrey", [(c[0], c[1], c[2] - 0.0004)], (0, 0, -1), radial, 0.003, (r1 - r0) * 0.9)
    k.lathe("PowderWhite", [(0.0, -0.016), (0.06, -0.016), (0.065, -0.0146), (0.065, -0.012), (0.0, -0.012)],
            (0, 0, 0), seg=40, smooth=False)
    k.collide((0, 0, -0.008), (S, S, 0.016))
    return {"sdt:assetId": code, "sdt:class": "hvac_swirl_diffuser",
            "sdt:role": "600 x 600 mm ceiling swirl diffuser supplying conditioned air to the room."}


def build_fire_extinguisher(k, code="BS-FE"):
    R = 0.07
    yc = -0.02 - R
    zb, ztop = -0.30, 0.20
    # wall bracket
    k.box_between("PowderAnthracite", (-0.035, -0.004, -0.12), (0.035, 0.0, 0.26), r=0.002, seg=1)
    k.box_between("PowderAnthracite", (-0.02, -0.022, 0.15), (0.02, -0.004, 0.17), r=0.002, seg=1)
    k.box_between("PowderAnthracite", (-0.03, -0.022, -0.11), (0.03, -0.004, -0.09), r=0.002, seg=1)
    strap = [(0.03, -0.004, -0.10)] + [((R + 0.003) * math.cos(t), yc + (R + 0.003) * math.sin(t), -0.10)
                                       for t in np.linspace(math.pi * 0.1, -math.pi * 1.1, 24)] + [(-0.03, -0.004, -0.10)]
    k.tube("PowderAnthracite", strap, 0.0025, seg=6)
    # cylinder body
    prof = [(0.0, zb), (R - 0.02, zb), (R - 0.004, zb + 0.004), (R, zb + 0.02), (R, ztop)]
    for a in np.linspace(0.15, math.pi / 2, 7):
        prof.append((0.018 + (R - 0.018) * math.cos(a), ztop + 0.06 * math.sin(a)))
    prof += [(0.016, ztop + 0.065), (0.0, ztop + 0.065)]
    k.lathe("PlasticRed", prof, (0.0, yc, 0.0), seg=40)
    # valve head, lever, handle, pin, hose and horn
    vz = ztop + 0.065
    k.cyl("Chrome", (0, yc, vz - 0.005), (0, yc, vz + 0.045), 0.016, seg=20, r_edge=0.002)
    k.box_between("PlasticBlack", (-0.012, yc - 0.075, vz + 0.035), (0.012, yc + 0.02, vz + 0.047), r=0.003, seg=1)
    k.box_between("PlasticBlack", (-0.012, yc - 0.075, vz + 0.008), (0.012, yc - 0.01, vz + 0.020), r=0.003, seg=1)
    k.tube("PlasticYellow", [(-0.016, yc - 0.03, vz + 0.028), (0.016, yc - 0.03, vz + 0.028)], 0.0015, seg=6)
    k.tube("Chrome", [(0.016, yc - 0.03, vz + 0.028), (0.03, yc - 0.03, vz + 0.02), (0.035, yc - 0.03, vz + 0.0),
                      (0.025, yc - 0.03, vz - 0.01)], 0.0012, seg=6)
    k.cyl("Chrome", (0.016, yc, vz + 0.02), (0.03, yc, vz + 0.02), 0.006, seg=12)
    hx = R + 0.035
    k.tube("RubberBlack", [(0.03, yc, vz + 0.02), (0.06, yc, vz + 0.025), (hx, yc, vz - 0.01), (hx + 0.005, yc, vz - 0.06),
                           (hx, yc, vz - 0.10)], 0.007, seg=10)
    k.lathe("PlasticBlack", [(0.010, 0.0), (0.012, -0.02), (0.022, -0.12), (0.045, -0.26), (0.048, -0.265),
                             (0.044, -0.265), (0.041, -0.26), (0.0185, -0.12), (0.0085, -0.02)], (hx, yc, vz - 0.10),
            seg=28)
    k.box_between("PowderAnthracite", (hx - 0.035, yc - 0.012, 0.02), (hx + 0.002, yc + 0.012, 0.035), r=0.002, seg=1)
    # label on the body
    lab = once("lab_fe.png", tex_text, ["CO2  5 kg", "fire extinguisher", "class B  |  electrical"], 600, 500,
               sizes=[96, 54, 44], bg=(245, 245, 240))
    curved_decal(k, lab, (0.0, yc), R + 0.0007, -0.15, 0.06, -math.pi / 2 - 0.12, 0.12, seg=12)
    tag = once(f"tag_{code}.png", tex_tag, code, "AICOR safety")
    curved_decal(k, tag, (0.0, yc), R + 0.0007, -0.24, -0.216, -math.pi / 2 - 0.25, 0.06, seg=6)
    # wall sign above
    sign = once("sign_fe.png", tex_extinguisher_sign)
    k.decal(sign, (0.0, -0.0007, 0.47), (0, -1, 0), (0, 0, 1), 0.20, 0.20)
    k.box_between("PlasticWhite", (-0.102, -0.0006, 0.368), (0.102, 0.0, 0.572))
    k.frame("handle", (0.0, yc - 0.06, vz + 0.04))
    k.collide((0.03, yc + 0.01, -0.02), (0.22, 2 * R + 0.06, 0.62))
    return {"sdt:assetId": code, "sdt:class": "fire_extinguisher",
            "sdt:role": "Wall-mounted 5 kg CO2 fire extinguisher (suitable for electrical equipment) with location sign."}


def build_first_aid_box(k, code="BS-FA"):
    W, Dd, Hh = 0.32, 0.13, 0.30
    k.box_between("PlasticGreen", (-W / 2, -Dd + 0.03, -Hh / 2), (W / 2, 0.0, Hh / 2), r=0.008, seg=2)
    k.box_between("PlasticGreen", (-W / 2 + 0.003, -Dd, -Hh / 2 + 0.003), (W / 2 - 0.003, -Dd + 0.0335, Hh / 2 - 0.003),
                  r=0.01, seg=3)
    png = once("first_aid.png", tex_first_aid)
    k.decal(png, (0, -Dd - 0.0007, 0.0), (0, -1, 0), (0, 0, 1), 0.20, 0.20)
    for x in (-0.09, 0.09):
        k.box_between("PlasticWhite", (x - 0.018, -Dd - 0.01, Hh / 2 - 0.03), (x + 0.018, -Dd + 0.002, Hh / 2 - 0.012),
                      r=0.003, seg=1)
    for x in (-0.12, 0.12):
        k.box_between("PlasticGreen", (x - 0.02, -Dd + 0.028, -Hh / 2 - 0.006), (x + 0.02, -Dd + 0.045, -Hh / 2 + 0.004),
                      r=0.003, seg=1)
    asset_tag(k, code, "AICOR safety", (0.10, -Dd - 0.0007, -0.125), w=0.05)
    k.frame("handle", (0.0, -Dd - 0.01, Hh / 2 - 0.02))
    k.collide((0, -Dd / 2, 0), (W, Dd, Hh))
    return {"sdt:assetId": code, "sdt:class": "first_aid_box",
            "sdt:role": "Wall-mounted first-aid cabinet."}


def build_access_reader(k, code="BS-ACR"):
    # card reader
    k.box_between("PlasticBlack", (-0.0425, -0.022, -0.0625), (0.0425, 0.0, 0.0625), r=0.006, seg=2)
    k.box_between("PlasticGrey", (-0.038, -0.0226, -0.058), (0.038, -0.02, 0.058), r=0.004, seg=1)
    k.decal(once("contactless.png", tex_contactless), (0.0, -0.0232, 0.012), (0, -1, 0), (0, 0, 1), 0.05, 0.05)
    k.cyl("IndicatorRed", (-0.01, -0.0226, -0.035), (-0.01, -0.0238, -0.035), 0.003, seg=12)
    k.cyl("PlasticGreen", (0.01, -0.0226, -0.035), (0.01, -0.0238, -0.035), 0.003, seg=12)
    quads(k, "PlasticBlack", grid((0.0, -0.0234, -0.05), (0, -1, 0), (0, 0, 1), 6, 1, 0.006, 0), (0, -1, 0), (0, 0, 1),
          0.0025, 0.0025)
    # 'open' push button box
    bx = 0.14
    k.box_between("PlasticWhite", (bx - 0.043, -0.03, -0.043), (bx + 0.043, 0.0, 0.043), r=0.005, seg=2)
    k.cyl("PlasticGreen", (bx, -0.03, 0.0), (bx, -0.040, 0.0), 0.024, seg=32, r_edge=0.003)
    disk_decal(k, once("btn_open.png", tex_text, ["OPEN"], 300, 300, sizes=[96], center=True, bg=(16, 120, 60),
                       fg=(255, 255, 255)), (bx, -0.0406, 0.0), (0, -1, 0), (0, 0, 1), 0.021)
    k.decal(once("lab_exitbtn.png", tex_text, ["Door release"], 600, 120, sizes=[60], center=True),
            (bx, -0.0306, -0.034), (0, -1, 0), (0, 0, 1), 0.06, 0.012)
    k.frame("reader", (0.0, -0.025, 0.012))
    k.frame("button", (bx, -0.042, 0.0))
    k.collide((0.07, -0.02, 0.0), (0.24, 0.04, 0.13))
    return {"sdt:assetId": code, "sdt:class": "access_control_reader",
            "sdt:role": "Door access card reader with door-release push button."}


# =============================================================================================== main
ASSETS = {
    "shelving_rack": (build_shelving_rack, {"seed": 1, "bays": 1, "rack": 1}),
    "lab_fridge": (build_lab_fridge, {"seed": 1}),
    "freezer_m20": (build_freezer_m20, {}),
    "ult_freezer": (build_ult_freezer, {}),
    "ln2_dewar": (build_ln2_dewar, {}),
    "o2_monitor": (build_o2_monitor, {}),
    "gas_cabinet": (build_gas_cabinet, {}),
    "dispatch_bench": (build_dispatch_bench, {}),
    "server_rack": (build_server_rack, {}),
    "smoke_detector": (build_smoke_detector, {}),
    "sprinkler_head": (build_sprinkler_head, {}),
    "hvac_diffuser": (build_hvac_diffuser, {}),
    "fire_extinguisher": (build_fire_extinguisher, {}),
    "first_aid_box": (build_first_aid_box, {}),
    "access_reader": (build_access_reader, {}),
}


def write_asset(name, fn, params):
    k = Kit()
    sem = fn(k, **params)
    sem.update({"sdt:bindingStatus": BINDING, "sdt:designBasis": DESIGN, "sdt:assetName": name})
    st, root = new_asset(os.path.join(USD_DIR, f"{name}.usda"),
                         comment=f"Generated by assets/labequip/build_storage.py ({name}) - edit the script, not this file.")
    ntri = k.write(st, root, sem)
    st.GetRootLayer().Save()
    P = np.concatenate([p[0] for plist in k.parts.values() for p in plist])
    lo, hi = P.min(0), P.max(0)
    return ntri, lo, hi, len(k.frames), len(sem.get("sdt:storageLocations", []))


def main(names=None):
    for name, (fn, params) in ASSETS.items():
        if names and name not in names:
            continue
        ntri, lo, hi, nf, nl = write_asset(name, fn, params)
        ext = hi - lo
        print(f"{name:18s} tris {ntri:7d}  extent {ext[0]:.3f} x {ext[1]:.3f} x {ext[2]:.3f}  "
              f"z[{lo[2]:.3f},{hi[2]:.3f}]  frames {nf}  locations {nl}")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
