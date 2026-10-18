"""Procedural equipment library: culture-prep area, wash/waste area and operator station (visual proxies v1).

Every asset is a project-owned proxy with generic class dimensions (no manufacturer CAD, no real brands). Builders
fill a meshkit Kit in LOCAL coordinates:
  * floor-standing: origin on the floor at the footprint centre, front (operator side) toward -Y, Z up
  * benchtop (centrifuge, microscope, water bath, pipette stand): origin at the bottom centre
  * wall-mounted (glove dispenser, coat rack, whiteboard): origin at the wall surface at the mounting-height centre,
    the item extends toward -Y; emergency shower: origin on the floor at the wall line.
Device displays show equipment set points / states only (project rule D016).

Run: env_cad/bin/python assets/labequip/build_prep.py [asset ...]   -> assets/labequip/usd/<name>.usda
"""

import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from assets.common import decals  # noqa: E402
from assets.common.meshkit import Kit, new_asset, rot_x  # noqa: E402

TEX = os.path.join(ROOT, "assets", "labequip", "textures")
USD_DIR = os.path.join(ROOT, "assets", "labequip", "usd")
DESIGN = "project-owned proxy with generic class dimensions; no manufacturer CAD"
TAN10 = math.tan(math.radians(10))
NAVY = (22, 44, 82)
SAFE_GREEN = (0, 128, 74)


def tex(name):
    return os.path.join(TEX, "prep_" + name)  # prefix: the texture folder is shared with other builders


# ============================================================================================ local geometry helpers
def ccw(pts):
    P = np.asarray(pts, float)
    a = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    return P if a > 0 else P[::-1]


def ext_x(k, mat, prof_yz, x0, x1):
    """Prism of a (y, z) profile swept along +X from x0 to x1."""
    k.extrude(mat, ccw(prof_yz), (x0, 0, 0), (x1, 0, 0), up=(0, 0, 1))


def ext_y(k, mat, prof_xz, y0, y1):
    """Prism of an (x, z) profile swept along +Y."""
    P = np.asarray(prof_xz, float) * [-1.0, 1.0]
    k.extrude(mat, ccw(P), (0, y0, 0), (0, y1, 0), up=(0, 0, 1))


def ext_z(k, mat, prof_xy, z0, z1):
    """Prism of an (x, y) profile swept along +Z."""
    k.extrude(mat, ccw(prof_xy), (0, 0, z0), (0, 0, z1), up=(0, 1, 0))


def _orient(P, N, T):
    e = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    ref = N[T[:, 0]] + N[T[:, 1]] + N[T[:, 2]]
    flip = (e * ref).sum(1) < 0
    T[flip] = T[flip][:, [0, 2, 1]]
    return T


def grid_surface(k, mat, G, close_v=False, double=False, thick=0.0006, centres=None):
    """Smooth-shaded quad grid G[nu, nv, 3]. close_v wraps the v direction. centres[nu] orients normals outward."""
    G = np.asarray(G, float)
    if close_v:
        G = np.concatenate([G, G[:, :1]], 1)
    nu, nv = G.shape[:2]
    du = np.gradient(G, axis=0)
    if close_v:
        Gw = np.concatenate([G[:, -2:-1], G, G[:, 1:2]], 1)
        dv = (Gw[:, 2:] - Gw[:, :-2]) / 2
    else:
        dv = np.gradient(G, axis=1)
    N = np.cross(du, dv)
    ln = np.linalg.norm(N, axis=-1, keepdims=True)
    N = np.where(ln > 1e-12, N / np.maximum(ln, 1e-12), np.array([0, 0, 1.0]))
    if centres is not None:
        out = G - np.asarray(centres, float)[:, None, :]
        if (N * out).sum() < 0:
            N = -N
    P = G.reshape(-1, 3)
    N = N.reshape(-1, 3)
    ii, jj = np.meshgrid(np.arange(nu - 1), np.arange(nv - 1), indexing="ij")
    v0 = (ii * nv + jj).ravel()
    T = np.concatenate([np.stack([v0, v0 + nv, v0 + nv + 1], 1), np.stack([v0, v0 + nv + 1, v0 + 1], 1)])
    k.add(mat, P, N, _orient(P, N, T.copy()))
    if double:
        P2, N2 = P - N * thick, -N
        k.add(mat, P2, N2, _orient(P2, N2, T.copy()))


def sring(cx, cy, z, rx, ry, n=32, p=2.0, ripple=None):
    """Superellipse ring (exponent p) in a horizontal plane. ripple(theta) -> radial scale factor."""
    th = np.linspace(0, 2 * math.pi, n, endpoint=False)
    c, s = np.cos(th), np.sin(th)
    x = rx * np.sign(c) * np.abs(c) ** (2 / p)
    y = ry * np.sign(s) * np.abs(s) ** (2 / p)
    if ripple is not None:
        f = ripple(th)
        x, y = x * f, y * f
    return np.stack([cx + x, cy + y, np.full(n, z)], 1)


def loft(k, mat, rings, cap0=True, cap1=True):
    rings = [np.asarray(r, float) for r in rings]
    C = np.array([r.mean(0) for r in rings])
    grid_surface(k, mat, np.stack(rings), close_v=True, centres=C)
    for idx, nb in ((0, 1), (-1, -2)):
        if (idx == 0 and not cap0) or (idx == -1 and not cap1):
            continue
        r = rings[idx]
        c = C[idx]
        ax = C[idx] - C[nb]
        ax = ax / (np.linalg.norm(ax) + 1e-12)
        P = np.concatenate([[c], r])
        n = len(r)
        T = np.array([[0, 1 + i, 1 + (i + 1) % n] for i in range(n)])
        N = np.tile(ax, (len(P), 1))
        k.add(mat, P, N, _orient(P, N, T))


def lev_foot(k, x, y, z_top, r=0.022, pad="RubberBlack"):
    """Levelling foot: rubber pad, hex nut, threaded stem up to z_top."""
    k.lathe(pad, [(r, 0.0), (r, 0.006), (r * 0.75, 0.011), (0.009, 0.014), (0.0, 0.0145)], base=(x, y, 0), seg=20)
    k.lathe(pad, [(0.0, 0.0), (r, 0.0)], base=(x, y, 0.0001), seg=20)
    k.cyl("StainlessSatin", (x, y, 0.016), (x, y, 0.026), 0.012, seg=6)
    k.cyl("StainlessSatin", (x, y, 0.012), (x, y, z_top), 0.0065, seg=12, caps=False)


def castor(k, x, y, z_top, r=0.04, brake=False, mat="StainlessSatin"):
    """Swivel castor: mounting plate at z_top, fork, rubber wheel (bottom at z=0), trailing toward +Y."""
    k.rbox(mat, (x, y, z_top - 0.003), (0.062, 0.062, 0.006), r=0.002, seg=1)
    k.cyl(mat, (x, y, z_top - 0.006), (x, y, z_top - 0.016), 0.022, seg=16)
    yw = y + r * 0.45
    for sx in (-1, 1):
        k.box_between(mat, (x + sx * 0.0155 - 0.002, yw - 0.014, r - 0.006), (x + sx * 0.0155 + 0.002, y + 0.016, z_top - 0.016))
    k.box_between(mat, (x - 0.0175, yw - 0.004, z_top - 0.02), (x + 0.0175, y + 0.016, z_top - 0.016))
    k.cyl("RubberBlack", (x - 0.012, yw, r), (x + 0.012, yw, r), r, seg=28, r_edge=0.005)
    k.cyl("PlasticGrey", (x - 0.0128, yw, r), (x + 0.0128, yw, r), r * 0.5, seg=16)
    k.cyl("Chrome", (x - 0.0185, yw, r), (x + 0.0185, yw, r), 0.0045, seg=10)
    if brake:
        k.rbox("PlasticRed", (x, y - 0.03, z_top - 0.03), (0.028, 0.03, 0.006), r=0.002, seg=1)


def twin_castor(k, x, y, z_top, cr=0.025, mat="PlasticBlack"):
    k.cyl("StainlessSatin", (x, y, z_top), (x, y, cr + 0.012), 0.005, seg=10, caps=False)
    k.rbox(mat, (x, y + 0.004, cr + 0.006), (0.024, 0.034, 0.03), r=0.008, seg=2)
    for sx in (-1, 1):
        k.cyl(mat, (x + sx * 0.013, y + 0.01, cr), (x + sx * 0.026, y + 0.01, cr), cr, seg=20, r_edge=0.004)


def star_base(k, R=0.32, z=0.085, cr=0.025, mat="PlasticBlack", hub_r=0.036):
    k.cyl(mat, (0, 0, z - 0.03), (0, 0, z + 0.035), hub_r, seg=24, r_edge=0.008)
    for i in range(5):
        with k.at((0, 0, 0), yaw=90 + 72 * i):
            L = R - 0.03
            k.rbox(mat, (0.03 + L / 2, 0, z - 0.002), (L, 0.042, 0.03), r=0.01, seg=2)
            twin_castor(k, R - 0.022, 0, z - 0.016, cr)


def perforated(k, w, h, pitch, hole_r, mat="PlasticBlack", proud=0.0008, seg=6):
    """Hex pattern of dark hole disks on a -Y facing surface at y=0 (local), centred at the origin."""
    ny = int(h / (pitch * 0.866))
    nx = int(w / pitch)
    for j in range(ny):
        z = -h / 2 + (j + 0.5) * h / ny
        off = (pitch / 2) if j % 2 else 0.0
        for i in range(nx - (1 if j % 2 else 0)):
            x = -w / 2 + pitch / 2 + i * pitch + off
            k.disk(mat, (x, -proud, z), hole_r, normal=(0, -1, 0), seg=seg)


def slots(k, w, h, n, mat="PlasticBlack", proud=0.0008, frac=0.45):
    """n horizontal dark vent slots on a -Y facing surface at y=0 (local), centred at the origin."""
    pitch = h / n
    for i in range(n):
        z = -h / 2 + pitch * (i + 0.5)
        k.rbox(mat, (0, -proud / 2, z), (w, proud + 0.0006, pitch * frac), r=min(pitch * frac, proud) * 0.45, seg=1)


def socket_double(k):
    """Two-gang protective-contact socket outlet facing -Y on a surface at local y=0."""
    k.rbox("PlasticWhite", (0, -0.006, 0), (0.15, 0.012, 0.08), r=0.004, seg=2)
    for dx in (-0.036, 0.036):
        k.disk("PlasticGrey", (dx, -0.0126, 0), 0.0205, normal=(0, -1, 0), seg=28)
        for px in (-0.0095, 0.0095):
            k.disk("PlasticBlack", (dx + px, -0.0132, 0), 0.0026, normal=(0, -1, 0), seg=10)
        for pz in (-0.017, 0.017):
            k.rbox("StainlessSatin", (dx, -0.0132, pz), (0.008, 0.001, 0.003), r=0.0)


def socket_data(k):
    k.rbox("PlasticWhite", (0, -0.006, 0), (0.08, 0.012, 0.08), r=0.004, seg=2)
    for dx in (-0.016, 0.016):
        k.rbox("PlasticBlack", (dx, -0.0126, -0.004), (0.014, 0.0012, 0.012), r=0.0)
        k.rbox("PlasticBlue", (dx, -0.0126, 0.016), (0.012, 0.0012, 0.006), r=0.0)


def bottle(k, x, y, z, r=0.04, h=0.20, mat="GlassAmber", cap="PlasticBlue", neck=0.016):
    prof = [(0.0, 0.0), (r * 0.9, 0.0), (r, 0.006), (r, h * 0.70), (r * 0.8, h * 0.80), (neck * 1.1, h * 0.88),
            (neck, h * 0.90), (neck, h - 0.002), (0.0, h - 0.002)]
    k.lathe(mat, prof, base=(x, y, z), seg=32, smooth=False)
    k.cyl(cap, (x, y, z + h - 0.012), (x, y, z + h + 0.016), neck + 0.004, seg=24, r_edge=0.002)


def media_bottle(k, x, y, z, r=0.043, h=0.17, cap="PlasticBlue"):
    """Clear square-shouldered lab bottle with a GL45 style screw cap."""
    bottle(k, x, y, z, r=r, h=h, mat="GlassClear", cap=cap, neck=0.024)
    k.lathe("PlasticBlue" if cap == "PlasticBlue" else cap,
            [(0.025, 0.0), (0.03, 0.0), (0.03, 0.006), (0.025, 0.006)], base=(x, y, z + h - 0.015), seg=24)


def tube_rack(k, x, y, z, nx=6, ny=3, mat="PlasticBlue", fill=0.7, seed=0, tube_h=0.105):
    rng = np.random.default_rng(seed)
    p = 0.026
    w, d = nx * p + 0.012, ny * p + 0.012
    k.rbox(mat, (x, y, z + 0.003), (w, d, 0.006), r=0.002, seg=1)
    k.rbox(mat, (x, y, z + 0.060), (w, d, 0.005), r=0.002, seg=1)
    for sx in (-1, 1):
        k.rbox(mat, (x + sx * (w / 2 - 0.002), y, z + 0.032), (0.004, d, 0.062), r=0.0015, seg=1)
    caps = ["PlasticBlue", "PlasticYellow", "PlasticRed", "PlasticWhite", "PlasticGreen"]
    for i in range(nx):
        for j in range(ny):
            cx, cy = x - w / 2 + 0.006 + p * (i + 0.5), y - d / 2 + 0.006 + p * (j + 0.5)
            if rng.random() > fill:
                k.disk("PlasticBlack", (cx, cy, z + 0.0628), 0.0088, seg=16)
                continue
            k.lathe("PolystyreneClear", [(0.0, 0.006), (0.003, 0.008), (0.0082, 0.024), (0.0082, tube_h), (0.0, tube_h)],
                    base=(cx, cy, z), seg=16, smooth=False)
            k.cyl(caps[(i + j * 2 + seed) % len(caps)], (cx, cy, z + tube_h - 0.004), (cx, cy, z + tube_h + 0.010),
                  0.0098, seg=16, r_edge=0.0015)


def box_item(k, x, y, z, w, d, h, mat="Cardboard", label=None, yaw=0.0):
    with k.at((x, y, z), yaw=yaw):
        k.rbox(mat, (0, 0, h / 2), (w, d, h), r=0.0015, seg=1)
        if label:
            k.decal(label, (0, -d / 2 - 0.0006, h * 0.55), (0, -1, 0), (0, 0, 1), w * 0.7, min(h * 0.45, w * 0.35))


# ============================================================================================ textures
def asset_tag(code, line2):
    p = tex(f"tag_{code}.png")
    img = Image.new("RGB", (640, 260), (236, 237, 236))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 640, 60], fill=NAVY)
    d.text((20, 9), "AICOR", font=decals.font(38, "Bold"), fill=(255, 255, 255))
    d.text((190, 17), "asset tag", font=decals.font(26, "Medium"), fill=(185, 198, 220))
    d.text((20, 74), code, font=decals.font(58, "Bold"), fill=(20, 22, 26))
    d.text((20, 166), line2, font=decals.font(26, "Medium"), fill=(70, 74, 80))
    d.text((20, 210), "visual proxy v1", font=decals.font(22, "Regular"), fill=(110, 114, 120))
    decals.draw_barcode(d, (330, 80, 615, 150), code)
    os.makedirs(TEX, exist_ok=True)
    img.save(p)
    return p


def device_screen(name, lines, accent=(60, 170, 255)):
    return decals.screen_device(tex(f"scr_{name}.png"), lines, accent=accent)


def label(name, lines, bg=(245, 245, 243), fg=(30, 32, 36), accent=None, w=800, h=300):
    return decals.plain_sign(tex(f"lbl_{name}.png"), lines, w=w, h=h, bg=bg, fg=fg, accent=accent)


def safe_sign(name, kind, lines, w=600, h=840):
    """ISO 7010 E-series style safe-condition sign: green square with a white pictogram, white text below."""
    img = Image.new("RGB", (w, h), SAFE_GREEN)
    d = ImageDraw.Draw(img)
    wh = (255, 255, 255)
    m = 40
    d.rectangle([m, m, w - m, w - m], outline=wh, width=10)
    cx, cy, s = w / 2, w / 2, w - 2 * m
    if kind == "eyewash":
        # eye (almond) with pupil, water jets rising from a nozzle below
        ey = cy - s * 0.17
        d.ellipse([cx - s * 0.33, ey - s * 0.13, cx + s * 0.33, ey + s * 0.13], fill=wh)
        d.ellipse([cx - s * 0.11, ey - s * 0.11, cx + s * 0.11, ey + s * 0.11], fill=SAFE_GREEN)
        d.ellipse([cx - s * 0.045, ey - s * 0.045, cx + s * 0.045, ey + s * 0.045], fill=wh)
        d.rectangle([cx - s * 0.04, cy + s * 0.30, cx + s * 0.04, cy + s * 0.42], fill=wh)
        d.rectangle([cx - s * 0.16, cy + s * 0.27, cx + s * 0.16, cy + s * 0.31], fill=wh)
        for sx in (-1, 1):
            for spread in (0.10, 0.20):
                pts = [(cx + sx * spread * s * t, cy + s * 0.26 - s * 0.36 * (1 - (1 - t) ** 2))
                       for t in np.linspace(0, 1, 16)]
                d.line(pts, fill=wh, width=int(s * 0.028), joint="curve")
    else:  # shower: head + arm, drops, person
        d.rectangle([cx + s * 0.05, cy - s * 0.42, cx + s * 0.09, cy - s * 0.26], fill=wh)
        d.rectangle([cx - s * 0.10, cy - s * 0.42, cx + s * 0.09, cy - s * 0.38], fill=wh)
        d.pieslice([cx - s * 0.08, cy - s * 0.34, cx + s * 0.22, cy - s * 0.14], 180, 360, fill=wh)
        for i in range(5):
            for j in range(3):
                x = cx - s * 0.04 + i * s * 0.055
                y = cy - s * 0.18 + j * s * 0.08 + (i % 2) * s * 0.03
                d.line([(x, y), (x - s * 0.01, y + s * 0.035)], fill=wh, width=int(s * 0.015))
        d.ellipse([cx - s * 0.03, cy + s * 0.02, cx + s * 0.09, cy + s * 0.14], fill=wh)
        d.rounded_rectangle([cx - s * 0.03, cy + s * 0.15, cx + s * 0.09, cy + s * 0.34], radius=int(s * 0.03), fill=wh)
        d.rectangle([cx - s * 0.025, cy + s * 0.33, cx + s * 0.015, cy + s * 0.45], fill=wh)
        d.rectangle([cx + s * 0.045, cy + s * 0.33, cx + s * 0.085, cy + s * 0.45], fill=wh)
        d.line([(cx - s * 0.02, cy + s * 0.18), (cx - s * 0.14, cy + s * 0.05)], fill=wh, width=int(s * 0.035))
        d.line([(cx + s * 0.08, cy + s * 0.18), (cx + s * 0.18, cy + s * 0.04)], fill=wh, width=int(s * 0.035))
    y = w + 10
    for i, line in enumerate(lines):
        f = decals.font(int(h * (0.075 if i == 0 else 0.05)), "Bold" if i == 0 else "Medium")
        decals._center_text(d, (0, y, w, y + h * 0.09), line, f, wh)
        y += h * 0.095
    return decals._save(img, tex(f"sign_{name}.png"))


def gauge_dial(name, unit="bar", vmax=4):
    S = 512
    img = Image.new("RGB", (S, S), (246, 246, 244))
    d = ImageDraw.Draw(img)
    c = S / 2
    d.ellipse([6, 6, S - 6, S - 6], outline=(40, 40, 40), width=6)
    a0, a1 = 225, -45
    for i in range(vmax * 5 + 1):
        a = math.radians(a0 + (a1 - a0) * i / (vmax * 5))
        r0 = S * (0.36 if i % 5 == 0 else 0.40)
        d.line([(c + r0 * math.cos(a), c - r0 * math.sin(a)), (c + S * 0.44 * math.cos(a), c - S * 0.44 * math.sin(a))],
               fill=(20, 20, 20), width=6 if i % 5 == 0 else 3)
        if i % 5 == 0:
            v = str(i // 5)
            decals._center_text(d, (c + S * 0.28 * math.cos(a) - 30, c - S * 0.28 * math.sin(a) - 30,
                                    c + S * 0.28 * math.cos(a) + 30, c - S * 0.28 * math.sin(a) + 30),
                                v, decals.font(44, "SemiBold"), (20, 20, 20))
    # red band at the top of the scale
    d.arc([S * 0.08, S * 0.08, S * 0.92, S * 0.92], -45, -20, fill=(200, 30, 20), width=14)
    decals._center_text(d, (0, S * 0.62, S, S * 0.72), unit, decals.font(40, "Medium"), (40, 40, 40))
    a = math.radians(a0 - 2)
    d.line([(c, c), (c + S * 0.40 * math.cos(a), c - S * 0.40 * math.sin(a))], fill=(25, 25, 25), width=9)
    d.ellipse([c - 18, c - 18, c + 18, c + 18], fill=(25, 25, 25))
    return decals._save(img, tex(f"dial_{name}.png"))


def glove_face(size):
    W, H = 300, 576
    img = Image.new("RGB", (W, H), (244, 245, 246))
    d = ImageDraw.Draw(img)
    col = {"S": (110, 70, 160), "M": (30, 110, 190), "L": (20, 140, 110)}[size]
    d.rectangle([0, H - 150, W, H], fill=col)
    d.rectangle([0, 0, W, 20], fill=col)
    # dispensing opening (perforated oval) with glove cuffs inside
    d.ellipse([40, 50, W - 40, 200], fill=(40, 70, 120))
    d.ellipse([60, 70, W - 60, 180], fill=(70, 120, 190))
    decals._center_text(d, (0, 225, W, 300), "Nitrile", decals.font(52, "Bold"), (30, 32, 36))
    decals._center_text(d, (0, 295, W, 345), "examination gloves", decals.font(24, "Medium"), (70, 72, 78))
    decals._center_text(d, (0, 350, W, 410), "powder-free", decals.font(24, "Regular"), (90, 92, 98))
    decals._center_text(d, (0, H - 150, W, H), size, decals.font(120, "Bold"), (255, 255, 255))
    return decals._save(img, tex(f"gloves_{size}.png"))


def whiteboard_png():
    W, H = 2200, 1200
    rng = np.random.default_rng(11)
    img = Image.new("RGB", (W, H), (247, 248, 248))
    # faint eraser ghosts
    ghost = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(ghost)
    for _ in range(14):
        x, y = rng.integers(0, W), rng.integers(0, H)
        gd.ellipse([x - 160, y - 40, x + 220, y + 50], fill=int(rng.integers(6, 16)))
    ghost = ghost.filter(ImageFilter.GaussianBlur(30))
    img = Image.composite(Image.new("RGB", (W, H), (205, 210, 214)), img, ghost)
    d = ImageDraw.Draw(img)
    BLUE, BLACK, RED, GREEN = (25, 60, 170), (25, 25, 30), (190, 30, 30), (20, 120, 60)

    def hline(pts, col, width=7):
        P = np.asarray(pts, float)
        out = []
        for a, b in zip(P[:-1], P[1:]):
            n = max(2, int(np.linalg.norm(b - a) / 25))
            nrm = np.array([-(b - a)[1], (b - a)[0]]) / (np.linalg.norm(b - a) + 1e-9)
            wob = np.cumsum(rng.normal(0, 0.9, n + 1))
            wob -= np.linspace(wob[0], wob[-1], n + 1)
            for t, wv in zip(np.linspace(0, 1, n + 1), wob):
                out.append(tuple(a + (b - a) * t + nrm * wv))
        d.line(out, fill=col, width=width, joint="curve")
        d.line([(x + 1.2, y + 0.8) for x, y in out], fill=col, width=max(2, width - 3))

    def hbox(x0, y0, x1, y1, col):
        o = lambda: rng.normal(0, 4)  # noqa: E731
        hline([(x0 - 10, y0 + o()), (x1 + 8, y0 + o())], col)
        hline([(x1 + o(), y0 - 8), (x1 + o(), y1 + 10)], col)
        hline([(x1 + 10, y1 + o()), (x0 - 6, y1 + o())], col)
        hline([(x0 + o(), y1 + 8), (x0 + o(), y0 - 10)], col)

    def arrow(x0, y0, x1, y1, col):
        hline([(x0, y0), ((x0 + x1) / 2, (y0 + y1) / 2 + rng.normal(0, 3)), (x1, y1)], col)
        a = math.atan2(y1 - y0, x1 - x0)
        for s in (1, -1):
            b = a + math.pi + s * 0.45
            hline([(x1, y1), (x1 + 34 * math.cos(b), y1 + 34 * math.sin(b))], col)

    def htext(x, y, text, col, px, weight="Medium", ang=None):
        f = decals.font(px, weight)
        bb = d.textbbox((0, 0), text, font=f)
        lay = Image.new("RGBA", (bb[2] + 20, bb[3] + 20), (0, 0, 0, 0))
        ImageDraw.Draw(lay).text((10, 10), text, font=f, fill=col + (255,))
        lay = lay.rotate(rng.normal(0, 1.2) if ang is None else ang, resample=Image.BICUBIC, expand=True)
        img.paste(lay, (int(x), int(y)), lay)

    htext(90, 70, "Cell 01 - culture handling flow", BLACK, 78, "SemiBold", ang=0.8)
    hline([(90, 175), (1180, 168)], BLACK, 5)
    steps = ["retrieve", "identify", "dose", "image", "QC", "store"]
    notes = ["hotel", "ID reader", "dispenser", "imager", "reference", "hotel"]
    bw, gap, y0 = 250, 92, 420
    x0 = (W - (6 * bw + 5 * gap)) / 2
    for i, (s, nte) in enumerate(zip(steps, notes)):
        xa = x0 + i * (bw + gap)
        hbox(xa, y0, xa + bw, y0 + 150, BLUE if s != "QC" else RED)
        htext(xa + 22, y0 + 44, s, BLACK, 50, "SemiBold")
        htext(xa + 30, y0 + 175, nte, BLUE, 40)
        if i < 5:
            arrow(xa + bw + 14, y0 + 75, xa + bw + gap - 14, y0 + 75, BLACK)
    # QC fail branch
    qx = x0 + 4 * (bw + gap) + bw / 2
    arrow(qx, y0 + 240, qx, y0 + 420, RED)
    hbox(qx - 280, y0 + 440, qx + 250, y0 + 570, RED)
    htext(qx - 250, y0 + 475, "fail -> quarantine", RED, 48, "SemiBold")
    htext(qx + 30, y0 + 300, "fail", RED, 44)
    # loop back
    lx0, lx1 = x0 + bw / 2, x0 + 5 * (bw + gap) + bw / 2
    hline([(lx1, y0 - 18), (lx1, y0 - 110), (lx0 + 10, y0 - 116)], GREEN, 6)
    arrow(lx0 + 10, y0 - 116, lx0, y0 - 22, GREEN)
    htext(W / 2 - 160, y0 - 190, "next plate", GREEN, 48)
    # side notes
    htext(110, 930, "- every step writes a record", BLACK, 44)
    htext(110, 1000, "- IDs checked before dosing", BLACK, 44)
    htext(110, 1070, "- open items: tool frame check (L21)", BLUE, 44)
    hline([(1260, 1120), (1720, 1100)], RED, 5)
    htext(1240, 980, "review Fri", RED, 50, ang=3)
    return decals._save(img, tex("whiteboard_flow.png"))


# ============================================================================================ furniture helpers
def cabinet_row(k, L, depth, pattern, zt=0.87, front="PowderWhite", carcass="PowderGrey", carcass_top=None):
    """Base cabinet run in a local frame: fronts face -Y at y=-depth/2, units side by side along X."""
    n = len(pattern)
    uw = L / n
    yf = -depth / 2
    H = zt - 0.10
    for i, kind in enumerate(pattern):
        xc = -L / 2 + uw * (i + 0.5)
        if kind == "knee":
            k.rbox(carcass, (xc, depth / 2 - 0.01, (0.0 + zt) / 2), (uw - 0.002, 0.02, zt), r=0.002, seg=1)
            k.rbox(carcass, (xc, yf + 0.045, zt - 0.03), (uw - 0.002, 0.05, 0.06), r=0.003, seg=1)
            continue
        ct = zt if carcass_top is None else carcass_top
        k.rbox(carcass, (xc, yf + 0.02 + (depth - 0.02) / 2, 0.10 + (ct - 0.10) / 2), (uw - 0.002, depth - 0.02, ct - 0.10),
               r=0.002, seg=1)
        k.rbox("VinylSkirting", (xc, yf + 0.06 + (depth - 0.06) / 2, 0.05), (uw, depth - 0.06, 0.10), r=0.0)
        if kind == "drawers":
            hs = [0.14, 0.17, 0.20]
            hs.append(H - sum(hs))
            z = zt
            for h in hs:
                zc = z - h / 2
                k.rbox(front, (xc, yf + 0.0105, zc), (uw - 0.004, 0.019, h - 0.004), r=0.003, seg=2)
                k.handle_bar("StainlessSatin", (xc, yf + 0.001, z - 0.045), 0.16, axis=(1, 0, 0), standoff=0.026,
                             r=0.0055)
                z -= h
        elif kind in ("door", "doorL"):
            k.rbox(front, (xc, yf + 0.0105, 0.10 + H / 2), (uw - 0.004, 0.019, H - 0.004), r=0.003, seg=2)
            hx = xc + (uw / 2 - 0.05) * (1 if kind == "door" else -1)
            k.handle_bar("StainlessSatin", (hx, yf + 0.001, zt - 0.16), 0.16, axis=(0, 0, 1), standoff=0.026, r=0.0055)
        elif kind == "door2":
            for s in (-1, 1):
                k.rbox(front, (xc + s * uw / 4, yf + 0.0105, 0.10 + H / 2), (uw / 2 - 0.004, 0.019, H - 0.004), r=0.003,
                       seg=2)
                k.handle_bar("StainlessSatin", (xc + s * 0.04, yf + 0.001, zt - 0.16), 0.16, axis=(0, 0, 1),
                             standoff=0.026, r=0.0055)


def shelf_items(k, x0, x1, y, z, seed, depth=0.24):
    """Bottles, boxes and tube racks spread along a shelf from x0 to x1 (front row at y)."""
    rng = np.random.default_rng(seed)
    x = x0 + 0.04
    while x < x1 - 0.12:
        kind = rng.choice(["amber", "clear", "box", "rack", "bottle2", "gap"], p=[0.2, 0.2, 0.2, 0.15, 0.15, 0.1])
        jy = y + rng.uniform(-0.02, 0.03)
        if kind == "amber":
            r = rng.choice([0.035, 0.045])
            bottle(k, x + r, jy, z, r=r, h=r * 5.2, mat="GlassAmber", cap="PlasticBlack")
            x += 2 * r + 0.03
        elif kind == "clear":
            media_bottle(k, x + 0.043, jy, z, cap=str(rng.choice(["PlasticBlue", "PlasticRed", "PlasticYellow"])))
            x += 0.115
        elif kind == "bottle2":
            k.lathe("HdpeNatural", [(0.0, 0.0), (0.04, 0.0), (0.042, 0.01), (0.042, 0.15), (0.02, 0.18), (0.015, 0.19),
                                    (0.0, 0.19)], base=(x + 0.042, jy, z), seg=28)
            k.cyl("PlasticWhite", (x + 0.042, jy, z + 0.185), (x + 0.042, jy, z + 0.205), 0.018, seg=20, r_edge=0.002)
            x += 0.115
        elif kind == "box":
            w, h = rng.uniform(0.12, 0.22), rng.uniform(0.07, 0.16)
            box_item(k, x + w / 2, y + 0.06, z, w, min(depth - 0.02, rng.uniform(0.12, 0.2)), h,
                     mat=str(rng.choice(["Cardboard", "PlasticWhite"])), yaw=float(rng.normal(0, 3)))
            x += w + 0.025
        elif kind == "rack":
            tube_rack(k, x + 0.085, jy + 0.03, z, nx=6, ny=3, mat=str(rng.choice(["PlasticBlue", "PlasticYellow"])),
                      seed=int(rng.integers(0, 99)))
            x += 0.2
        else:
            x += 0.08


def plinth_end(k, x, y0, y1, zt):
    k.rbox("PowderGrey", (x, (y0 + y1) / 2, zt / 2), (0.02, y1 - y0, zt), r=0.003, seg=1)


# ============================================================================================ 1 BSC
def build_bsc_class2(k):
    zst, zw, zs, zf, zt, ztop = 0.72, 0.78, 0.98, 1.68, 1.93, 2.25

    def yf(z):
        return -0.36 + (z - 0.80) * TAN10

    W = "PowderWhite"
    # ---- stand
    for x in (-0.70, 0.70):
        for y in (-0.34, 0.34):
            k.rbox(W, (x, y, (0.05 + zst) / 2), (0.05, 0.05, zst - 0.05), r=0.004, seg=2)
            lev_foot(k, x, y, 0.05)
    for y in (-0.34, 0.34):
        k.rbox(W, (0, y, zst - 0.025), (1.35, 0.05, 0.05), r=0.004, seg=2)
    for x in (-0.70, 0.70):
        k.rbox(W, (x, 0, zst - 0.025), (0.05, 0.63, 0.05), r=0.004, seg=2)
        k.rbox(W, (x, 0, 0.16), (0.04, 0.63, 0.04), r=0.004, seg=2)
    k.rbox(W, (0, 0.34, 0.16), (1.35, 0.04, 0.04), r=0.004, seg=2)
    # footrest: brackets from the front legs + tilted plate with rubber strips
    for x in (-0.66, 0.66):
        k.rbox(W, (x, -0.40, 0.235), (0.03, 0.11, 0.03), r=0.004, seg=1)
    with k.at((0, -0.44, 0.255), R=rot_x(-12)):
        k.rbox("AluAnodized", (0, 0, 0), (1.36, 0.13, 0.012), r=0.003, seg=1)
        for i in range(4):
            k.rbox("RubberBlack", (0, -0.045 + i * 0.03, 0.0065), (1.30, 0.012, 0.003), r=0.0)
    # ---- cabinet base pan + lower front + armrest
    k.rbox(W, (0, 0, 0.74), (1.50, 0.80, 0.04), r=0.006, seg=2)
    k.rbox(W, (0, -0.3775, 0.775), (1.50, 0.045, 0.07), r=0.006, seg=2)
    k.rbox("PlasticGrey", (0, -0.385, 0.807), (1.40, 0.05, 0.028), r=0.012, seg=3)
    k.box_between("PlasticBlack", (-0.70, -0.356, 0.74), (0.70, -0.30, 0.769))
    with k.at((0, -0.328, 0.7705), R=rot_x(-90)):
        k.box("StainlessBrushed", (0, 0.001, 0), (1.40, 0.002, 0.054))
        perforated(k, 1.38, 0.050, 0.0075, 0.0022, mat="PlasticBlack", proud=0.0006, seg=6)
    k.rbox("StainlessWorktop", (0, -0.01, 0.77), (1.40, 0.58, 0.02), r=0.003, seg=2)
    # ---- side panels (outer powder-coat + stainless liner) with side windows
    z0 = 0.76
    pieces = [
        [(-0.40, z0), (0.40, z0), (0.40, 0.86), (yf(0.86) - 0.005, 0.86), (yf(0.82) - 0.005, 0.82), (-0.40, 0.82)],
        [(yf(1.55) - 0.005, 1.55), (0.40, 1.55), (0.40, zt), (yf(zt) - 0.005, zt)],
        [(yf(0.86) - 0.005, 0.86), (yf(0.86) + 0.065, 0.86), (yf(1.55) + 0.065, 1.55), (yf(1.55) - 0.005, 1.55)],
        [(0.05, 0.86), (0.40, 0.86), (0.40, 1.55), (0.05, 1.55)],
    ]
    glass = [(yf(0.855) + 0.06, 0.855), (0.055, 0.855), (0.055, 1.555), (yf(1.555) + 0.06, 1.555)]
    for s in (-1, 1):
        for pc in pieces:
            ext_x(k, W, pc, *sorted((s * 0.72, s * 0.75)))
            ext_x(k, "StainlessBrushed", pc, *sorted((s * 0.71, s * 0.72)))
        ext_x(k, "SafetyGlass", glass, *sorted((s * 0.712, s * 0.738)))
        # black window gasket on the outside
        gz = [(yf(0.86) + 0.065, 0.86), (0.05, 0.86), (0.05, 1.55), (yf(1.55) + 0.065, 1.55)]
        for a, b in zip(gz, gz[1:] + gz[:1]):
            pa, pb = np.array(a), np.array(b)
            dvec = (pb - pa) / np.linalg.norm(pb - pa)
            nrm = np.array([-dvec[1], dvec[0]]) * 0.006
            ext_x(k, "RubberBlack", [tuple(pa), tuple(pb), tuple(pb + nrm), tuple(pa + nrm)],
                  *sorted((s * 0.7505, s * 0.7525)))
    # ---- back, interior back wall, ceiling diffuser, LED
    k.rbox(W, (0, 0.385, (z0 + zt) / 2), (1.50, 0.03, zt - z0), r=0.006, seg=2)
    k.box_between("StainlessBrushed", (-0.71, 0.28, zw), (0.71, 0.29, 1.75))
    with k.at((0, 0.28, 0.815)):
        for i in range(36):
            k.rbox("PlasticBlack", (-0.63 + i * 0.036, -0.0005, 0), (0.024, 0.0012, 0.03), r=0.0)
    k.box_between(W, (-0.71, yf(1.75) + 0.01, 1.75), (0.71, 0.29, zt))
    k.box_between("PlasticWhite", (-0.70, yf(1.75) + 0.07, 1.746), (0.70, 0.28, 1.75))
    k.rbox("LedPanel", (0, yf(1.75) + 0.07, 1.744), (1.32, 0.09, 0.008), r=0.002, seg=1)
    # ---- fascia (sloped) with control panel
    ext_x(k, W, [(yf(zf), zf), (yf(zf) + 0.008, zf), (yf(zt) + 0.008, zt), (yf(zt), zt)], -0.72, 0.72)
    zc = 1.80
    scr = device_screen("bsc", ["Airflow OK", "Sash 200 mm", "Blower on   UV off", "Filter status OK"],
                        accent=(60, 200, 120))
    tag = asset_tag("PR-BSC1", "Biosafety cabinet class II")
    bio = decals.warning_sign(tex("warn_biohazard.png"), "biohazard", ["Biohazard"])
    with k.at((0, yf(zc), zc), R=rot_x(-10)):
        k.rbox("PowderAnthracite", (0.33, -0.003, 0), (0.44, 0.006, 0.13), r=0.004, seg=2)
        k.decal(scr, (0.24, -0.0066, 0.005), (0, -1, 0), (0, 0, 1), 0.144, 0.09, emissive=400)
        for i in range(5):
            k.rbox("PlasticGrey", (0.36 + i * 0.034, -0.0075, -0.025), (0.024, 0.004, 0.016), r=0.0015, seg=1)
        k.disk("IndicatorGreen", (0.36, -0.0062, 0.035), 0.0045, normal=(0, -1, 0), seg=12)
        k.disk("StackRed", (0.39, -0.0062, 0.035), 0.0045, normal=(0, -1, 0), seg=12)
        k.disk("StackAmber", (0.42, -0.0062, 0.035), 0.0045, normal=(0, -1, 0), seg=12)
        k.decal(tag, (-0.50, -0.0006, 0.0), (0, -1, 0), (0, 0, 1), 0.11, 0.045)
        k.decal(bio, (-0.30, -0.0006, -0.005), (0, -1, 0), (0, 0, 1), 0.06, 0.084)
    # ---- top blower / filter housing
    k.rbox(W, (0, 0.10, (zt + ztop) / 2), (1.50, 0.60, ztop - zt), r=0.01, seg=3)
    with k.at((0, -0.20, 2.09)):
        k.rbox("PowderGrey", (0, -0.0005, 0), (1.10, 0.002, 0.18), r=0.0)
        slots(k, 1.06, 0.16, 14, mat="PlasticBlack", proud=0.0015)
    with k.at((0, 0.12, ztop), R=rot_x(-90)):
        k.box("StainlessBrushed", (0, -0.001, 0), (0.90, 0.002, 0.34))
        perforated(k, 0.88, 0.32, 0.016, 0.005, proud=0.0026)
    k.cyl("PlasticGrey", (0.55, 0.30, ztop), (0.55, 0.30, ztop + 0.03), 0.03, seg=20)
    # ---- sash (sliding safety glass) in aluminium side channels
    L = 0.74
    with k.at((0, yf(zs) + 0.015, zs), R=rot_x(-10)):
        k.box("SafetyGlass", (0, 0, L / 2), (1.416, 0.008, L))
        k.rbox("AluAnodized", (0, -0.002, 0.014), (1.418, 0.03, 0.036), r=0.006, seg=2)
        k.rbox("PlasticGrey", (0, -0.02, 0.006), (0.50, 0.014, 0.012), r=0.005, seg=2)
    Lc = (zf - 0.82) / math.cos(math.radians(10))
    with k.at((0, yf(0.82) + 0.015, 0.82), R=rot_x(-10)):
        for s in (-1, 1):
            k.rbox("AluAnodized", (s * 0.704, 0, Lc / 2), (0.014, 0.03, Lc), r=0.003, seg=1)
    # ---- visible contents on the work surface
    tube_rack(k, -0.30, 0.02, zw, nx=6, ny=3, mat="PlasticBlue", seed=4)
    media_bottle(k, 0.10, 0.10, zw, cap="PlasticBlue")
    k.lathe("PolystyreneClear", [(0.0, 0.0), (0.045, 0.0), (0.05, 0.13), (0.0505, 0.131)], base=(0.32, 0.05, zw), seg=28)
    k.decal(tag, (0.55, -0.4006, 0.773), (0, -1, 0), (0, 0, 1), 0.075, 0.03)
    k.frame("work_surface", (0, -0.01, zw))
    k.frame("sash", (0, yf(zs) - 0.005, zs))
    k.frame("display", (0.24, yf(zc) - 0.01, zc + 0.005))
    k.frame("operator_position", (0, -0.80, 0))
    k.collide((0, 0, zst / 2), (1.50, 0.80, zst))
    k.collide((0, 0, (zst + ztop) / 2), (1.50, 0.80, ztop - zst))


# ============================================================================================ 2 CO2 incubators
def incubator_unit(k, z0, code, scr, tag, lower=True):
    W = "PowderWhite"
    with k.at((0, 0, z0)):
        for x in (-0.27, 0.27):
            for y in (-0.28, 0.30):
                k.cyl("RubberBlack", (x, y, 0.0), (x, y, 0.016), 0.02, seg=16, r_edge=0.003)
        k.rbox(W, (0, 0.024, 0.0155 + 0.442), (0.65, 0.702, 0.884), r=0.008, seg=3)
        # outer door (3 mm gap to the body front at y=-0.327)
        k.rbox(W, (0, -0.3525, 0.4975), (0.636, 0.045, 0.795), r=0.006, seg=2)
        k.rbox("PlasticGrey", (0, -0.3305, 0.0575), (0.60, 0.007, 0.06), r=0.003, seg=1)
        with k.at((0.08, -0.334, 0.0575)):
            slots(k, 0.30, 0.04, 5, proud=0.001)
        k.rbox("PlasticBlack", (-0.24, -0.3365, 0.0575), (0.024, 0.006, 0.03), r=0.002, seg=1)
        k.disk("IndicatorGreen", (-0.20, -0.334, 0.0575), 0.0035, normal=(0, -1, 0), seg=10)
        for zc in (0.20, 0.79):
            k.cyl("PowderGrey", (-0.322, -0.331, zc - 0.045), (-0.322, -0.331, zc + 0.045), 0.0095, seg=16)
            k.box_between("PowderGrey", (-0.326, -0.345, zc - 0.035), (-0.318, -0.330, zc + 0.035))
        k.handle_bar("AluAnodized", (0.272, -0.375, 0.50), 0.34, axis=(0, 0, 1), standoff=0.034, r=0.0085)
        k.rbox("PlasticBlack", (-0.03, -0.3765, 0.785), (0.26, 0.004, 0.115), r=0.004, seg=2)
        k.decal(scr, (-0.075, -0.3790, 0.785), (0, -1, 0), (0, 0, 1), 0.136, 0.085, emissive=380)
        for i in range(4):
            k.rbox("PlasticGrey", (0.035 + (i % 2) * 0.03, -0.3795, 0.80 - (i // 2) * 0.03), (0.022, 0.004, 0.018),
                   r=0.0015, seg=1)
        k.decal(tag, (-0.20, -0.3756, 0.17), (0, -1, 0), (0, 0, 1), 0.10, 0.041)
        # rear: gas inlet barb + inline filter + hose, power inlet, vents
        with k.at((0, 0.375, 0)):
            k.rbox("PlasticGrey", (0.18, 0.004, 0.76), (0.09, 0.008, 0.07), r=0.003, seg=1)
            k.cyl("Chrome", (0.16, 0.008, 0.76), (0.16, 0.035, 0.76), 0.0055, seg=12)
            k.cyl("Chrome", (0.20, 0.008, 0.76), (0.20, 0.02, 0.76), 0.007, seg=6)
            hose = [(0.16, 0.035, 0.76), (0.16, 0.06, 0.745), (0.16, 0.07, 0.70), (0.16, 0.07, 0.62)]
            k.tube("HdpeNatural", hose, 0.005, seg=10)
            k.cyl("PlasticWhite", (0.16, 0.07, 0.62), (0.16, 0.07, 0.56), 0.016, seg=16, r_edge=0.004)
            k.tube("HdpeNatural", [(0.16, 0.07, 0.56), (0.16, 0.07, 0.30), (0.16, 0.08, 0.05 - z0 + 0.20)
                                   if lower else (0.16, 0.07, 0.10)], 0.005, seg=10)
            k.rbox("PlasticBlack", (-0.20, 0.006, 0.12), (0.05, 0.012, 0.035), r=0.002, seg=1)
            with k.at((0, 0.0, 0.45), yaw=180):
                slots(k, 0.40, 0.22, 10, proud=0.001)
    return z0


def build_co2_incubator_stack(k):
    G = "PowderGrey"
    for x in (-0.29, 0.29):
        for y in (-0.33, 0.33):
            castor(k, x, y, 0.10, r=0.035, brake=(y < 0))
    k.rbox(G, (0, 0, 0.185), (0.68, 0.78, 0.03), r=0.004, seg=2)
    for x in (-0.32, 0.32):
        k.rbox(G, (x, 0, 0.12), (0.04, 0.78, 0.04), r=0.004, seg=2)
    for y in (-0.37, 0.37):
        k.rbox(G, (0, y, 0.12), (0.60, 0.04, 0.04), r=0.004, seg=2)
    for x in (-0.32, 0.32):
        for y in (-0.37, 0.37):
            k.rbox(G, (x, y, 0.155), (0.04, 0.04, 0.03), r=0.004, seg=1)
    scr = device_screen("incubator", ["37.0 °C", "5.0 % CO2  set point", "door closed", "manual culture"],
                        accent=(60, 170, 255))
    tag = asset_tag("PR-INC1", "CO2 incubator stack")
    incubator_unit(k, 0.20, "lower", scr, tag, lower=True)
    incubator_unit(k, 1.10, "upper", scr, tag, lower=False)
    k.frame("door_lower", (0.272, -0.41, 0.20 + 0.50))
    k.frame("door_upper", (0.272, -0.41, 1.10 + 0.50))
    k.frame("display", (-0.075, -0.39, 1.10 + 0.785))
    k.frame("operator_position", (0, -0.85, 0))
    k.collide((0, 0, 0.10), (0.68, 0.78, 0.20))
    k.collide((0, 0, 1.10), (0.65, 0.75, 1.80))


# ============================================================================================ 3 centrifuge
def build_centrifuge(k):
    for x in (-0.16, 0.16):
        for y in (-0.24, 0.24):
            k.cyl("RubberBlack", (x, y, 0), (x, y, 0.012), 0.016, seg=16, r_edge=0.003)
    k.rbox("PowderWhite", (0, 0, 0.012 + 0.1425), (0.40, 0.60, 0.285), r=0.03, seg=3)
    # lid (3 mm seam above the body top at 0.297), hinge cover, viewing window
    k.rbox("PlasticWhite", (0, -0.035, 0.3255), (0.37, 0.46, 0.051), r=0.024, seg=3)
    k.rbox("PlasticGrey", (0, 0.235, 0.312), (0.30, 0.06, 0.03), r=0.01, seg=2)
    k.disk("PlasticBlack", (0, -0.03, 0.3511), 0.068, seg=48)
    k.disk("Polycarbonate", (0, -0.03, 0.3517), 0.062, seg=48)
    k.disk("Chrome", (0, -0.03, 0.3519), 0.072, seg=48, r_in=0.062)
    k.rbox("PlasticGrey", (0, -0.262, 0.312), (0.16, 0.012, 0.012), r=0.004, seg=1)
    # sloped front control panel
    scr = device_screen("centrifuge", ["ready", "lid closed", "rotor: --", "0 rpm"], accent=(80, 200, 120))
    with k.at((0, -0.30, 0.17), R=rot_x(-8)):
        k.rbox("PlasticGrey", (0, -0.004, 0), (0.32, 0.008, 0.11), r=0.004, seg=2)
        k.decal(scr, (-0.07, -0.0086, 0.005), (0, -1, 0), (0, 0, 1), 0.10, 0.0625, emissive=380)
        for i, m in enumerate(("IndicatorGreen", "PlasticRed", "PlasticWhite")):
            k.cyl(m, (0.04 + i * 0.03, -0.008, -0.03), (0.04 + i * 0.03, -0.013, -0.03), 0.009, seg=16, r_edge=0.0015)
        k.cyl("PlasticBlack", (0.10, -0.008, 0.02), (0.10, -0.024, 0.02), 0.017, seg=24, r_edge=0.003)
        k.rbox("PlasticWhite", (0.10, -0.0245, 0.032), (0.003, 0.001, 0.008), r=0.0)
    for s in (-1, 1):
        with k.at((s * 0.2, 0.05, 0.16), yaw=-90 * s):
            slots(k, 0.24, 0.10, 8, proud=0.001)
    tag = asset_tag("PR-CFG1", "Benchtop centrifuge")
    k.decal(tag, (0.2006, -0.18, 0.08), (1, 0, 0), (0, 0, 1), 0.09, 0.037)
    with k.at((0, 0.30, 0.0), yaw=180):
        k.rbox("PlasticBlack", (0.10, -0.006, 0.08), (0.05, 0.012, 0.035), r=0.002, seg=1)
        k.rbox("PlasticBlack", (-0.10, -0.006, 0.08), (0.03, 0.012, 0.02), r=0.002, seg=1)
    k.frame("display", (-0.07, -0.32, 0.175))
    k.frame("lid", (0, -0.265, 0.33))
    k.collide((0, 0, 0.175), (0.40, 0.60, 0.35))


# ============================================================================================ 4 inverted microscope
def build_inverted_microscope(k):
    Wm, B = "PlasticWhite", "PlasticBlack"
    for x in (-0.12, 0.12):
        for y in (-0.19, 0.19):
            k.cyl("RubberBlack", (x, y, 0), (x, y, 0.006), 0.014, seg=14)
    k.rbox(Wm, (0, 0, 0.041), (0.30, 0.45, 0.07), r=0.02, seg=3)
    for s in (-1, 1):  # body cheeks either side of the nosepiece
        k.rbox(Wm, (s * 0.09, 0.06, 0.14), (0.05, 0.28, 0.13), r=0.012, seg=2)
    k.rbox(Wm, (0, 0.14, 0.14), (0.22, 0.12, 0.13), r=0.012, seg=2)
    # nosepiece turret with objectives (tilted toward the front)
    with k.at((0, -0.02, 0.165), R=rot_x(15)):
        k.lathe("Chrome", [(0.0, -0.008), (0.046, -0.008), (0.05, -0.002), (0.046, 0.006), (0.0, 0.008)], seg=40)
        cols = ["PlasticRed", "PlasticYellow", "PlasticGreen", "PlasticBlue", "PlasticWhite"]
        for i in range(5):
            a = math.radians(90 + 72 * i)
            p = (0.029 * math.cos(a), 0.029 * math.sin(a))
            k.lathe("Chrome", [(0.0, 0.0), (0.0105, 0.0), (0.0105, 0.022), (0.009, 0.03), (0.006, 0.036),
                               (0.0, 0.036)], base=(p[0], p[1], 0.006), seg=20, smooth=False)
            k.cyl(cols[i], (p[0], p[1], 0.019), (p[0], p[1], 0.022), 0.0107, seg=20, caps=False)
    k.cyl(Wm, (0, -0.02, 0.07), (0, -0.02, 0.157), 0.03, seg=24)
    # stage + plate holder + microplate
    k.rbox("AluDark", (0, -0.015, 0.222), (0.27, 0.20, 0.016), r=0.004, seg=2)
    hz = 0.2315
    for (cx, cy, sx, sy) in ((0, -0.02 - 0.0505, 0.16, 0.012), (0, -0.02 + 0.0505, 0.16, 0.012),
                             (-0.074, -0.02, 0.012, 0.113), (0.074, -0.02, 0.012, 0.113)):
        k.rbox("AluAnodized", (cx, cy, hz + 0.004), (sx, sy, 0.007), r=0.0015, seg=1)
    k.rbox("PolystyreneClear", (0, -0.02, hz + 0.008), (0.1275, 0.0855, 0.0144), r=0.002, seg=1)
    k.rbox("PolystyreneClear", (0, -0.02, hz + 0.0168), (0.1275, 0.0855, 0.003), r=0.0015, seg=1)
    # coaxial stage controls (right, below stage)
    k.cyl(B, (0.12, -0.08, 0.214), (0.12, -0.08, 0.15), 0.006, seg=12)
    k.cyl(B, (0.12, -0.08, 0.19), (0.12, -0.08, 0.17), 0.016, seg=24, r_edge=0.003)
    k.cyl(B, (0.12, -0.08, 0.165), (0.12, -0.08, 0.145), 0.012, seg=24, r_edge=0.003)
    # pillar, illuminator arm, lamp housing, condenser
    k.rbox(Wm, (0, 0.165, 0.38), (0.10, 0.09, 0.34), r=0.015, seg=2)
    k.rbox(Wm, (0, 0.08, 0.53), (0.085, 0.26, 0.055), r=0.012, seg=2)
    k.rbox(B, (0, 0.17, 0.598), (0.09, 0.11, 0.082), r=0.01, seg=2)
    with k.at((0.0451, 0.17, 0.598), yaw=90):
        slots(k, 0.08, 0.05, 6, mat="PlasticGrey", proud=0.001)
    k.cyl(B, (0, -0.02, 0.505), (0, -0.02, 0.385), 0.03, seg=28, r_edge=0.003)
    k.cyl("Chrome", (0, -0.02, 0.47), (0, -0.02, 0.455), 0.033, seg=28)
    k.rbox(B, (0.0, -0.02, 0.43), (0.13, 0.03, 0.012), r=0.003, seg=1)
    k.disk("GlassClear", (0, -0.02, 0.3848), 0.018, normal=(0, 0, -1), seg=20)
    # binocular head toward the operator (-Y), eyepieces 37 deg from vertical
    k.rbox(Wm, (0, -0.17, 0.16), (0.15, 0.09, 0.17), r=0.015, seg=2)
    with k.at((0, -0.185, 0.27), R=rot_x(36.87)):
        k.rbox(Wm, (0, 0, 0.0), (0.13, 0.06, 0.07), r=0.015, seg=2)
        for s in (-1, 1):
            k.cyl(B, (s * 0.032, 0, 0.02), (s * 0.032, 0, 0.105), 0.0145, seg=24)
            k.cyl("Chrome", (s * 0.032, 0, 0.075), (s * 0.032, 0, 0.082), 0.0155, seg=24, caps=False)
            k.lathe("RubberBlack", [(0.0, 0.0), (0.015, 0.0), (0.018, 0.012), (0.019, 0.022), (0.012, 0.022),
                                    (0.0, 0.016)], base=(s * 0.032, 0, 0.104), seg=24)
    # focus knobs
    for s in (-1, 1):
        k.cyl(B, (s * 0.115, 0.08, 0.11), (s * 0.142, 0.08, 0.11), 0.036, seg=32, r_edge=0.004)
        k.cyl(B, (s * 0.142, 0.08, 0.11), (s * 0.165, 0.08, 0.11), 0.024, seg=28, r_edge=0.003)
        k.cyl("Chrome", (s * 0.141, 0.08, 0.11), (s * 0.144, 0.08, 0.11), 0.026, seg=28, caps=False)
    # side camera port, dimmer, power LED
    k.cyl(B, (-0.115, 0.03, 0.15), (-0.17, 0.03, 0.15), 0.017, seg=20)
    k.rbox(B, (-0.195, 0.03, 0.15), (0.05, 0.05, 0.05), r=0.005, seg=2)
    k.cyl(B, (0.15, 0.15, 0.04), (0.165, 0.15, 0.04), 0.014, seg=20, r_edge=0.002)
    k.disk("IndicatorGreen", (0.1508, 0.11, 0.045), 0.003, normal=(1, 0, 0), seg=10)
    tag = asset_tag("PR-MIC1", "Inverted microscope")
    k.decal(tag, (0.0506, 0.165, 0.33), (1, 0, 0), (0, 0, 1), 0.075, 0.031)
    k.frame("stage", (0, -0.02, 0.247))
    k.frame("eyepieces", (0, -0.26, 0.37))
    k.collide((0, 0, 0.32), (0.30, 0.45, 0.64))


# ============================================================================================ 5 water bath
def build_water_bath(k):
    for x in (-0.14, 0.14):
        for y in (-0.11, 0.11):
            k.cyl("RubberBlack", (x, y, 0), (x, y, 0.01), 0.013, seg=14, r_edge=0.002)
    k.rbox("StainlessBrushed", (0, 0, 0.105), (0.35, 0.30, 0.19), r=0.006, seg=2)
    for (cx, cy, sx, sy) in ((0, -0.143, 0.35, 0.014), (0, 0.143, 0.35, 0.014), (-0.168, 0, 0.014, 0.30),
                             (0.168, 0, 0.014, 0.30)):
        k.rbox("StainlessSatin", (cx, cy, 0.2025), (sx, sy, 0.005), r=0.0015, seg=1)
    with k.at((0, 0, 0.205)):
        ext_x(k, "StainlessBrushed", [(-0.152, 0.0), (0.152, 0.0), (0.152, 0.006), (0.0, 0.048), (-0.152, 0.006)],
              -0.172, 0.172)
        k.cyl("PlasticBlack", (-0.06, 0, 0.0515), (0.06, 0, 0.0515), 0.006, seg=12)
        for x in (-0.06, 0.06):
            k.cyl("PlasticBlack", (x, 0, 0.044), (x, 0, 0.052), 0.004, seg=8)
    scr = device_screen("waterbath", ["37.0 °C", "set point", "heater ready"], accent=(240, 150, 40))
    k.rbox("PlasticGrey", (0, -0.153, 0.065), (0.30, 0.008, 0.07), r=0.004, seg=2)
    k.decal(scr, (-0.075, -0.1575, 0.067), (0, -1, 0), (0, 0, 1), 0.08, 0.05, emissive=350)
    for i in range(3):
        k.rbox("PlasticWhite", (0.02 + i * 0.03, -0.158, 0.067), (0.02, 0.004, 0.016), r=0.0015, seg=1)
    k.rbox("PlasticBlack", (0.12, -0.1595, 0.067), (0.018, 0.008, 0.028), r=0.002, seg=1)
    k.disk("IndicatorGreen", (0.12, -0.1640, 0.074), 0.003, normal=(0, -1, 0), seg=10)
    for s in (-1, 1):
        k.rbox("PlasticBlack", (s * 0.177, 0, 0.15), (0.008, 0.10, 0.02), r=0.003, seg=1)
    tag = asset_tag("PR-WB1", "Water bath")
    k.decal(tag, (0.1756, 0.06, 0.08), (1, 0, 0), (0, 0, 1), 0.07, 0.029)
    k.frame("display", (-0.075, -0.17, 0.067))
    k.frame("lid", (0, 0, 0.255))
    k.collide((0, 0, 0.127), (0.35, 0.30, 0.255))


# ============================================================================================ 6 pipette stand
def pipette(k, plunger):
    """Single-channel air-displacement pipette, local origin at the tip end, axis +Z (length ~0.25)."""
    k.lathe("PlasticWhite", [(0.0, 0.0), (0.0012, 0.0), (0.0035, 0.032), (0.0045, 0.05), (0.0045, 0.052)], seg=16)
    k.lathe("PlasticGrey", [(0.0045, 0.05), (0.006, 0.075), (0.0068, 0.105), (0.0, 0.105)], seg=16)
    k.lathe("PlasticWhite", [(0.0078, 0.07), (0.0088, 0.072), (0.0088, 0.105), (0.0078, 0.107)], seg=16)
    k.lathe("PlasticGrey", [(0.0, 0.104), (0.0115, 0.104), (0.0145, 0.12), (0.0155, 0.17), (0.0145, 0.205),
                            (0.012, 0.215), (0.0, 0.216)], seg=24)
    k.rbox("PlasticWhite", (0, 0.0151, 0.17), (0.012, 0.001, 0.022), r=0.0)
    k.rbox("PlasticGrey", (0, 0.016, 0.195), (0.016, 0.034, 0.012), r=0.004, seg=1)   # finger hook
    k.cyl("PlasticWhite", (0, 0, 0.215), (0, 0, 0.237), 0.004, seg=12)
    k.cyl(plunger, (0, 0, 0.237), (0, 0, 0.252), 0.0095, seg=20, r_edge=0.003)
    k.cyl("PlasticWhite", (0, 0.013, 0.20), (0, 0.013, 0.218), 0.0045, seg=10)


def build_pipette_stand(k):
    k.lathe("PlasticBlack", [(0.0, 0.0), (0.095, 0.0), (0.098, 0.006), (0.092, 0.018), (0.0, 0.02)], seg=48)
    k.cyl("AluAnodized", (0, 0, 0.02), (0, 0, 0.33), 0.011, seg=20)
    k.lathe("PlasticBlack", [(0.0, 0.294), (0.058, 0.294), (0.06, 0.299), (0.058, 0.304), (0.0, 0.304)], seg=48)
    k.lathe("PlasticBlack", [(0.0, 0.33), (0.02, 0.33), (0.02, 0.345), (0.0, 0.35)], seg=24)
    cols = ["PlasticOrange", "PlasticYellow", "PlasticBlue", "PlasticGreen", "PlasticRed", "PlasticGrey"]
    for i in range(6):
        a = 30 + 60 * i
        with k.at((0, 0, 0), yaw=a):
            k.rbox("PlasticBlack", (0.0, 0.07, 0.299), (0.008, 0.03, 0.01), r=0.002, seg=1)
        with k.at((0, 0, 0), yaw=a + 30):
            with k.at((0, 0.073, 0.304 - 0.189), yaw=180):
                pipette(k, cols[i])
    k.frame("pick", (0, -0.073, 0.30))
    k.collide((0, 0, 0.175), (0.19, 0.19, 0.35))


# ============================================================================================ 7 island bench
def build_lab_bench_island(k, length=2.4, depth=1.5):
    L, D = length, depth
    zt = 0.87
    k.rbox("PhenolicDark", (0, 0, 0.885), (L, D, 0.03), r=0.012, seg=3)
    cd = 0.58
    yc = -D / 2 + 0.02 + cd / 2
    n = max(1, int(round((L - 0.04) / 0.6)))
    pat_f = (["drawers"] + ["door2" if i % 2 == 0 else "door" for i in range(n - 2)] + ["drawers"]) if n > 1 else ["door"]
    pat_b = (["door"] + ["knee" if i == 0 else "drawers" for i in range(n - 2)] + ["doorL"]) if n > 1 else ["door"]
    with k.at((0, yc, 0)):
        cabinet_row(k, L - 0.04, cd, pat_f)
    with k.at((0, -yc, 0), yaw=180):
        cabinet_row(k, L - 0.04, cd, pat_b)
    k.box_between("PowderGrey", (-L / 2 + 0.02, yc + cd / 2, 0.10), (L / 2 - 0.02, -yc - cd / 2, zt))
    for s in (-1, 1):
        plinth_end(k, s * (L / 2 - 0.01), -D / 2 + 0.03, D / 2 - 0.03, zt)
    # central service spine with sockets on both sides, reagent shelf upstand
    G = "PowderGrey"
    k.rbox(G, (0, 0, 0.98), (L - 0.10, 0.16, 0.16), r=0.006, seg=2)
    nsock = max(1, int((L - 0.3) / 0.6))
    for side in (0, 180):
        with k.at((0, 0, 0), yaw=side):
            for i in range(nsock):
                x = -(L - 0.3) / 2 + (i + 0.5) * (L - 0.3) / nsock
                with k.at((x - 0.05, -0.08, 0.98)):
                    socket_double(k)
                with k.at((x + 0.10, -0.08, 0.98)):
                    socket_data(k)
    posts = [-(L / 2 - 0.12), 0.0, L / 2 - 0.12]
    for x in posts:
        k.rbox(G, (x, 0, 1.06 + 0.40), (0.04, 0.04, 0.80), r=0.003, seg=2)
        for zsh in (1.35, 1.70):
            k.rbox(G, (x, 0, zsh - 0.022), (0.03, 0.30, 0.03), r=0.003, seg=1)
    k.rbox(G, (0, 0, 1.875), (L - 0.20, 0.04, 0.03), r=0.003, seg=2)
    for zsh in (1.35, 1.70):
        k.rbox("GlassClear", (0, 0, zsh), (L - 0.16, 0.32, 0.01), r=0.002, seg=1)
        for y in (-0.165, 0.165):
            k.cyl("StainlessSatin", (-(L - 0.18) / 2, y, zsh + 0.045), ((L - 0.18) / 2, y, zsh + 0.045), 0.004, seg=10)
            for x in posts:
                k.cyl("StainlessSatin", (x, y, zsh + 0.005), (x, y, zsh + 0.045), 0.0035, seg=8)
    shelf_items(k, -L / 2 + 0.1, L / 2 - 0.1, -0.08, 1.355, seed=1)
    shelf_items(k, -L / 2 + 0.1, L / 2 - 0.1, -0.07, 1.705, seed=2)
    with k.at((0, 0, 0), yaw=180):
        shelf_items(k, -L / 2 + 0.1, L / 2 - 0.1, -0.08, 1.355, seed=3)
    # a few items on the worktop
    tube_rack(k, -L / 4 + 0.25, -0.45, 0.90, seed=7, mat="PlasticYellow")
    media_bottle(k, L / 4 - 0.2, -0.35, 0.90)
    tag = asset_tag("PR-BEN1", "Island lab bench")
    k.decal(tag, (-L / 2 + 0.25, -D / 2 + 0.0194, 0.92 - 0.10), (0, -1, 0), (0, 0, 1), 0.09, 0.037)
    k.frame("work_left", (-L / 4, -D / 2 + 0.35, 0.90))
    k.frame("work_right", (L / 4, -D / 2 + 0.35, 0.90))
    k.frame("shelf", (0, -0.10, 1.355))
    k.frame("operator_position", (0, -D / 2 - 0.35, 0))
    k.collide((0, 0, 0.45), (L, D, 0.90))
    k.collide((0, 0, 1.39), (L - 0.1, 0.34, 0.98))


# ============================================================================================ 8 wall bench
def build_wall_bench(k, length=3.0):
    L, D = length, 0.75
    zt = 0.87
    k.rbox("PhenolicDark", (0, 0, 0.885), (L, D, 0.03), r=0.012, seg=3)
    cd = 0.60
    yc = -D / 2 + 0.02 + cd / 2
    n = max(1, int(round((L - 0.04) / 0.6)))
    base = ["drawers", "door", "knee", "door2", "drawers", "doorL", "drawers"]
    pat = ["drawers"] + [base[1 + i % 5] for i in range(n - 2)] + ["drawers"] if n > 1 else ["door"]
    with k.at((0, yc, 0)):
        cabinet_row(k, L - 0.04, cd, pat)
    for s in (-1, 1):
        plinth_end(k, s * (L / 2 - 0.01), -D / 2 + 0.03, D / 2 - 0.005, zt)
    # rear service channel with outlets
    G = "PowderGrey"
    k.rbox(G, (0, D / 2 - 0.06, 0.98), (L - 0.04, 0.12, 0.16), r=0.006, seg=2)
    nsock = max(1, int(L / 0.6))
    for i in range(nsock):
        x = -L / 2 + (i + 0.5) * L / nsock
        with k.at((x - 0.05, D / 2 - 0.12, 0.98)):
            socket_double(k)
        if i % 2 == 0:
            with k.at((x + 0.10, D / 2 - 0.12, 0.98)):
                socket_data(k)
    # wall shelf 0.3 deep at 1.5 m on cantilever brackets
    k.rbox("PhenolicLight", (0, D / 2 - 0.15, 1.485), (L - 0.1, 0.30, 0.025), r=0.004, seg=2)
    nb = max(2, int(L / 0.9) + 1)
    for i in range(nb):
        x = -(L - 0.3) / 2 + i * (L - 0.3) / (nb - 1)
        k.rbox(G, (x, D / 2 - 0.006, 1.40), (0.03, 0.012, 0.30), r=0.002, seg=1)
        ext_y(k, G, [(x - 0.004, 1.3), (x + 0.004, 1.3), (x + 0.004, 1.472), (x - 0.004, 1.472)], D / 2 - 0.28, D / 2 - 0.012)
    with k.at((0, D / 2 - 0.15, 0)):
        shelf_items(k, -L / 2 + 0.1, L / 2 - 0.1, -0.05, 1.4975, seed=5, depth=0.28)
    tube_rack(k, -0.6, -0.05, 0.90, seed=9)
    bottle(k, 0.5, 0.0, 0.90, r=0.04, h=0.2, mat="GlassAmber", cap="PlasticBlack")
    tag = asset_tag("PR-BEN2", "Wall lab bench")
    k.decal(tag, (-L / 2 + 0.25, -D / 2 + 0.0194, 0.82), (0, -1, 0), (0, 0, 1), 0.09, 0.037)
    k.frame("work_surface", (0, -0.10, 0.90))
    k.frame("shelf", (0, D / 2 - 0.20, 1.4975))
    k.frame("operator_position", (0, -D / 2 - 0.35, 0))
    k.collide((0, 0, 0.45), (L, D, 0.90))
    k.collide((0, D / 2 - 0.06, 0.98), (L, 0.12, 0.16))
    k.collide((0, D / 2 - 0.15, 1.40), (L - 0.1, 0.30, 0.20))


# ============================================================================================ 9 sink unit
def build_lab_sink_unit(k):
    D = 0.65
    zt = 0.87
    with k.at((0, -D / 2 + 0.02 + 0.29, 0)):
        cabinet_row(k, 1.16, 0.58, ["door2"], zt=zt, carcass_top=0.66)
    for s in (-1, 1):
        plinth_end(k, s * 0.59, -D / 2 + 0.03, D / 2, zt)
    S, SW = "StainlessWorktop", "StainlessBrushed"
    bx0, bx1, by0, by1 = -0.50, -0.10, -0.20, 0.20
    zb = 0.90 - 0.20
    k.box_between(S, (-0.60, -D / 2, 0.87), (0.60, by0, 0.90))
    k.box_between(S, (-0.60, by1, 0.87), (0.60, D / 2, 0.90))
    k.box_between(S, (-0.60, by0, 0.87), (bx0, by1, 0.90))
    k.box_between(S, (bx1, by0, 0.87), (0.60, by1, 0.90))
    k.cyl(S, (-0.60, -D / 2 + 0.012, 0.888), (0.60, -D / 2 + 0.012, 0.888), 0.016, seg=20, r_edge=0.004)
    k.box_between(S, (-0.60, D / 2 - 0.02, 0.90), (0.60, D / 2, 1.00))
    # bowl
    k.box_between(SW, (bx0, by0, zb - 0.002), (bx1, by1, zb))
    k.box_between(SW, (bx0, by0, zb), (bx0 + 0.002, by1, 0.90))
    k.box_between(SW, (bx1 - 0.002, by0, zb), (bx1, by1, 0.90))
    k.box_between(SW, (bx0, by0, zb), (bx1, by0 + 0.002, 0.90))
    k.box_between(SW, (bx0, by1 - 0.002, zb), (bx1, by1, 0.90))
    cxb = (bx0 + bx1) / 2
    k.disk("Chrome", (cxb, 0.0, zb + 0.0006), 0.036, seg=32)
    k.disk("PlasticBlack", (cxb, 0.0, zb + 0.0012), 0.026, seg=32)
    k.rbox("Chrome", (cxb, 0.0, zb + 0.0016), (0.05, 0.003, 0.0006), r=0.0)
    k.rbox("Chrome", (cxb, 0.0, zb + 0.0016), (0.003, 0.05, 0.0006), r=0.0)
    # drainer grooves
    for i in range(14):
        x = bx1 + 0.06 + i * 0.033
        k.rbox(SW, (x, 0.0, 0.9008), (0.008, 0.36, 0.0016), r=0.0006, seg=1)
    # gooseneck tap with wrist-action lever
    tx, ty = cxb, 0.25
    k.cyl("Chrome", (tx, ty, 0.90), (tx, ty, 0.975), 0.022, seg=24, r_edge=0.004)
    arc = [(tx, ty, 0.975), (tx, ty, 1.13)]
    for a in np.linspace(0, math.pi, 14)[1:]:
        arc.append((tx, ty - 0.09 + 0.09 * math.cos(a), 1.13 + 0.09 * math.sin(a)))
    arc.append((tx, ty - 0.18, 1.08))
    k.tube("Chrome", arc, 0.011, seg=16)
    k.cyl("Chrome", (tx, ty - 0.18, 1.085), (tx, ty - 0.18, 1.06), 0.013, seg=16, r_edge=0.002)
    k.disk("PlasticBlack", (tx, ty - 0.18, 1.0598), 0.009, normal=(0, 0, -1), seg=12)
    k.cyl("Chrome", (tx + 0.02, ty, 0.955), (tx + 0.15, ty - 0.02, 0.965), 0.006, seg=12)
    k.cyl("Chrome", (tx + 0.15, ty - 0.02, 0.965), (tx + 0.165, ty - 0.022, 0.967), 0.009, seg=12, r_edge=0.003)
    # deck-mounted swivel eyewash (parked over the drainer)
    ex, ey = 0.02, 0.255
    Gn, Ye = "PlasticGreen", "PlasticYellow"
    k.cyl(Gn, (ex, ey, 0.90), (ex, ey, 1.03), 0.018, seg=20, r_edge=0.003)
    k.cyl(Gn, (ex, ey, 1.03), (ex + 0.20, ey, 1.03), 0.012, seg=16)
    k.cyl(Gn, (ex + 0.20, ey - 0.07, 1.03), (ex + 0.20, ey + 0.05, 1.03), 0.011, seg=16)
    for dy in (-0.07, 0.05):
        hy = ey + dy
        k.cyl(Gn, (ex + 0.20, hy, 1.03), (ex + 0.20, hy, 1.07), 0.02, seg=20, r_edge=0.003)
        k.lathe(Ye, [(0.0235, 0.0), (0.0245, 0.012), (0.019, 0.022), (0.008, 0.027), (0.0, 0.028)],
                base=(ex + 0.20, hy, 1.066), seg=24)
    k.rbox(Gn, (ex + 0.11, ey - 0.03, 1.03), (0.07, 0.006, 0.07), r=0.004, seg=1)
    # splashback, dispensers, eyewash sign
    k.box_between("PhenolicLight", (-0.60, D / 2 - 0.008, 1.00), (0.60, D / 2, 1.60))
    yw = D / 2 - 0.008
    with k.at((-0.47, yw, 1.30)):   # soap
        k.rbox("PlasticWhite", (0, -0.05, 0), (0.11, 0.10, 0.24), r=0.012, seg=2)
        k.rbox("PlasticGrey", (0, -0.096, -0.09), (0.08, 0.02, 0.05), r=0.006, seg=1)
        k.box("PlasticGrey", (0, -0.1008, 0.03), (0.05, 0.0012, 0.09))
        k.decal(label("soap", ["Soap"], w=600, h=220), (0, -0.1007, 0.09), (0, -1, 0), (0, 0, 1), 0.08, 0.03)
    with k.at((-0.16, yw, 1.30)):   # hand disinfectant, elbow lever
        k.rbox("PlasticWhite", (0, -0.06, 0), (0.12, 0.12, 0.27), r=0.012, seg=2)
        k.cyl("StainlessSatin", (-0.055, -0.12, 0.10), (0.055, -0.12, 0.10), 0.006, seg=12)
        ext_x(k, "StainlessSatin", [(-0.12, 0.10), (-0.13, 0.10), (-0.16, -0.12), (-0.15, -0.12)], -0.04, 0.04)
        k.cyl("PlasticBlack", (0, -0.10, -0.14), (0, -0.10, -0.155), 0.006, seg=10)
        k.decal(label("disinf", ["Hand disinfectant"], w=800, h=220), (0, -0.1206, 0.0), (0, -1, 0), (0, 0, 1), 0.10,
                0.028)
    with k.at((0.40, yw, 1.33)):   # paper towel dispenser
        k.rbox("PlasticWhite", (0, -0.065, 0), (0.28, 0.13, 0.36), r=0.015, seg=2)
        k.box("Polycarbonate", (0, -0.1305, 0.05), (0.08, 0.002, 0.12))
        k.box("PaperWhite", (0, -0.12, 0.05), (0.07, 0.01, 0.11))
        k.rbox("PlasticGrey", (0, -0.10, -0.181), (0.22, 0.04, 0.004), r=0.0015, seg=1)
        with k.at((0, -0.095, -0.19), R=rot_x(-12)):
            k.box("PaperWhite", (0, 0, -0.035), (0.20, 0.0012, 0.07))
    eye = safe_sign("eyewash", "eyewash", ["Eyewash"])
    k.rbox("PlasticWhite", (0.12, yw - 0.0015, 1.32), (0.16, 0.003, 0.224), r=0.001, seg=1)
    k.decal(eye, (0.12, yw - 0.0036, 1.32), (0, -1, 0), (0, 0, 1), 0.15, 0.21)
    tag = asset_tag("WW-SNK1", "Lab sink unit")
    k.decal(tag, (-0.45, -D / 2 + 0.0194, 0.80), (0, -1, 0), (0, 0, 1), 0.09, 0.037)
    k.frame("sink", (cxb, 0.0, zb))
    k.frame("tap", (tx, ty - 0.18, 1.06))
    k.frame("eyewash", (ex + 0.20, ey - 0.01, 1.095))
    k.frame("operator_position", (0, -D / 2 - 0.35, 0))
    k.collide((0, 0, 0.45), (1.2, D, 0.90))
    k.collide((0, D / 2 - 0.08, 1.30), (1.2, 0.16, 0.60))


# ============================================================================================ 10 emergency shower
def build_emergency_shower(k):
    P, r = "Galvanized", 0.017
    yo = -0.07
    k.cyl(P, (0, yo, 2.60), (0, yo, 2.36), r, seg=20, caps=False)
    pts = [(0, yo, 2.36)]
    for a in np.linspace(0, math.pi / 2, 8)[1:]:
        pts.append((0, yo - 0.05 + 0.05 * math.cos(a), 2.36 - 0.05 * math.sin(a)))
    k.tube(P, pts, r, seg=20)
    k.cyl(P, (0, yo - 0.05, 2.31), (0, -0.55, 2.31), r, seg=20, caps=False)
    pts = [(0, -0.55, 2.31)]
    for a in np.linspace(0, math.pi / 2, 8)[1:]:
        pts.append((0, -0.55 - 0.05 * math.sin(a), 2.26 + 0.05 * math.cos(a)))
    k.tube(P, pts, r, seg=20)
    hx, hy = 0, -0.60
    k.cyl(P, (hx, hy, 2.26), (hx, hy, 2.23), r, seg=20, caps=False)
    k.lathe("PlasticGreen", [(0.0, 0.0), (0.12, 0.0), (0.127, 0.006), (0.12, 0.016), (0.07, 0.05), (0.025, 0.065),
                             (0.0, 0.066)], base=(hx, hy, 2.165), seg=48)
    k.disk("StainlessSatin", (hx, hy, 2.1645), 0.11, normal=(0, 0, -1), seg=48)
    for ring_r, n in ((0.03, 8), (0.06, 14), (0.09, 20)):
        for i in range(n):
            a = 2 * math.pi * i / n
            k.disk("PlasticBlack", (hx + ring_r * math.cos(a), hy + ring_r * math.sin(a), 2.1639), 0.0035,
                   normal=(0, 0, -1), seg=8)
    # ball valve on the horizontal arm, lever + pull rod with triangle handle
    vy = -0.33
    k.rbox("PlasticYellow", (0, vy, 2.31), (0.06, 0.08, 0.06), r=0.012, seg=2)
    k.cyl("StainlessSatin", (0, vy, 2.28), (0.0, vy, 2.25), 0.006, seg=10)
    k.rbox("PlasticYellow", (0.0, vy - 0.06, 2.25), (0.02, 0.14, 0.012), r=0.004, seg=1)
    rx, ry = 0.0, vy - 0.125
    k.cyl("StainlessSatin", (rx, ry, 2.25), (rx, ry, 1.80), 0.005, seg=10)
    tri = [(rx, ry, 1.80), (rx - 0.09, ry, 1.66), (rx + 0.09, ry, 1.66), (rx, ry, 1.80)]
    k.tube("PlasticGreen", tri, 0.009, seg=12)
    k.cyl("PlasticGreen", (rx - 0.09, ry, 1.66), (rx + 0.09, ry, 1.66), 0.012, seg=16, r_edge=0.003)
    # pipe clamps on the wall
    for z in (2.52, 2.40):
        k.rbox("StainlessSatin", (0, -0.02, z), (0.06, 0.04, 0.025), r=0.004, seg=1)
        k.cyl("StainlessSatin", (0, yo, z - 0.0125), (0, yo, z + 0.0125), r + 0.004, seg=20)
    sign = safe_sign("shower", "shower", ["Emergency", "shower"])
    k.rbox("PlasticWhite", (0.30, -0.0015, 1.95), (0.20, 0.003, 0.28), r=0.001, seg=1)
    k.decal(sign, (0.30, -0.0036, 1.95), (0, -1, 0), (0, 0, 1), 0.19, 0.266)
    tag = asset_tag("WW-SHW1", "Emergency shower")
    k.decal(tag, (0.30, -0.0036, 1.775), (0, -1, 0), (0, 0, 1), 0.09, 0.037)
    k.rbox("PlasticWhite", (0.30, -0.0015, 1.775), (0.095, 0.003, 0.042), r=0.001, seg=1)
    k.frame("handle", (rx, ry, 1.66))
    k.frame("operator_position", (hx, hy, 0))
    k.collide((0, yo, 2.45), (0.05, 0.05, 0.30))
    k.collide((0, -0.33, 2.29), (0.05, 0.55, 0.06))
    k.collide((hx, hy, 2.20), (0.26, 0.26, 0.08))


# ============================================================================================ 11 autoclave
def build_autoclave(k):
    S = "StainlessBrushed"
    for x in (-0.30, 0.30):
        for y in (-0.33, 0.35):
            lev_foot(k, x, y, 0.06)
    k.rbox(S, (0, 0.01, 0.58), (0.70, 0.78, 1.04), r=0.01, seg=3)
    yfr = -0.38
    # control panel strip
    k.rbox("PowderAnthracite", (0, yfr - 0.006, 1.00), (0.66, 0.012, 0.16), r=0.006, seg=2)
    scr = device_screen("autoclave", ["ready", "door closed", "chamber 0.0 bar", "program: --"], accent=(240, 150, 40))
    k.decal(scr, (-0.15, yfr - 0.0126, 1.005), (0, -1, 0), (0, 0, 1), 0.17, 0.106, emissive=380)
    for i in range(6):
        k.rbox("PlasticGrey", (0.02 + (i % 3) * 0.04, yfr - 0.0135, 1.03 - (i // 3) * 0.04), (0.03, 0.004, 0.026),
               r=0.002, seg=1)
    k.disk("IndicatorGreen", (0.02, yfr - 0.0124, 1.065), 0.004, normal=(0, -1, 0), seg=10)
    k.disk("StackAmber", (0.05, yfr - 0.0124, 1.065), 0.004, normal=(0, -1, 0), seg=10)
    gx, gz = 0.235, 1.00
    dial = gauge_dial("autoclave")
    k.cyl("Chrome", (gx, yfr - 0.012, gz), (gx, yfr - 0.034, gz), 0.058, seg=40, r_edge=0.004)
    k.decal(dial, (gx, yfr - 0.0346, gz), (0, -1, 0), (0, 0, 1), 0.082, 0.082)
    k.disk("Chrome", (gx, yfr - 0.0352, gz), 0.0585, normal=(0, -1, 0), seg=40, r_in=0.040)
    k.disk("GlassClear", (gx, yfr - 0.0356, gz), 0.0405, normal=(0, -1, 0), seg=40)
    # round door with flange, gasket, radial locking handle
    dc = (0, yfr, 0.52)
    k.lathe("StainlessSatin", [(0.258, 0.0), (0.285, 0.0), (0.287, 0.012), (0.275, 0.018), (0.258, 0.018)],
            base=dc, axis=(0, -1, 0), seg=64, smooth=False)
    k.lathe("RubberBlack", [(0.248, 0.0), (0.258, 0.0), (0.258, 0.022), (0.248, 0.022)], base=dc, axis=(0, -1, 0),
            seg=64, smooth=False)
    k.lathe(S, [(0.25, 0.018), (0.25, 0.05), (0.24, 0.064), (0.20, 0.078), (0.12, 0.086), (0.0, 0.088)],
            base=dc, axis=(0, -1, 0), seg=64)
    hub = np.array([0, yfr - 0.088, 0.52])
    k.cyl("Chrome", tuple(hub), tuple(hub + [0, -0.055, 0]), 0.034, seg=32, r_edge=0.006)
    k.cyl("Chrome", tuple(hub + [0, -0.055, 0]), tuple(hub + [0, -0.07, 0]), 0.02, seg=24, r_edge=0.004)
    for i in range(4):
        a = math.radians(45 + 90 * i)
        dvec = np.array([math.cos(a), 0, math.sin(a)])
        p0 = hub + [0, -0.035, 0] + dvec * 0.03
        p1 = hub + [0, -0.035, 0] + dvec * 0.17
        k.cyl("Chrome", tuple(p0), tuple(p1), 0.011, seg=16)
        k.sphere("PlasticBlack", tuple(p1 + dvec * 0.018), 0.022, seg=20)
    for zc in (0.64, 0.40):   # hinge on the left
        k.rbox("StainlessSatin", (-0.30, yfr - 0.03, zc), (0.05, 0.06, 0.09), r=0.008, seg=2)
        k.rbox("StainlessSatin", (-0.25, yfr - 0.06, zc), (0.10, 0.02, 0.05), r=0.006, seg=1)
        k.cyl("Chrome", (-0.30, yfr - 0.062, zc - 0.05), (-0.30, yfr - 0.062, zc + 0.05), 0.012, seg=16)
    with k.at((0, yfr, 0.16)):
        k.rbox("StainlessSatin", (0, -0.001, 0), (0.60, 0.002, 0.13), r=0.0)
        slots(k, 0.56, 0.11, 7, proud=0.0026)
    k.cyl("PlasticBlack", (-0.22, -0.20, 1.10), (-0.22, -0.20, 1.12), 0.045, seg=32, r_edge=0.006)
    k.cyl("StainlessSatin", (0.22, 0.30, 1.10), (0.22, 0.30, 1.16), 0.018, seg=16, r_edge=0.003)
    with k.at((0, 0.40, 0), yaw=180):
        k.rbox("PlasticBlack", (0.20, -0.006, 0.20), (0.06, 0.012, 0.04), r=0.002, seg=1)
        k.cyl("StainlessSatin", (-0.15, 0, 0.25), (-0.15, -0.05, 0.25), 0.012, seg=14)
        k.tube("RubberBlack", [(-0.15, -0.05, 0.25), (-0.15, -0.09, 0.22), (-0.15, -0.10, 0.12), (-0.15, -0.11, 0.012)],
               0.011, seg=12)
    tag = asset_tag("WW-AC1", "Laboratory autoclave")
    k.decal(tag, (-0.25, yfr - 0.0006, 0.855), (0, -1, 0), (0, 0, 1), 0.10, 0.041)
    hot = decals.warning_sign(tex("warn_hot.png"), "general", ["Caution", "hot surface"])
    k.decal(hot, (0.27, yfr - 0.0006, 0.84), (0, -1, 0), (0, 0, 1), 0.06, 0.084)
    k.frame("door", (0, yfr - 0.09, 0.52))
    k.frame("handle", tuple(hub + [0, -0.07, 0]))
    k.frame("display", (-0.15, yfr - 0.02, 1.005))
    k.frame("operator_position", (0, -0.95, 0))
    k.collide((0, 0.0, 0.55), (0.70, 0.80, 1.10))


# ============================================================================================ 12 waste station
def pedal_bin(k, body, bag, decal_png, decal_w=0.13):
    """60 L pedal bin, local origin at the floor centre, front -Y."""
    rings = []
    for z, w, d in ((0.012, 0.36, 0.31), (0.03, 0.37, 0.32), (0.60, 0.42, 0.36), (0.615, 0.425, 0.365)):
        rings.append(sring(0, 0, z, w / 2, d / 2, n=48, p=5.0))
    loft(k, body, rings)
    loft(k, "RubberBlack", [sring(0, 0, 0.0, 0.175, 0.15, 48, 5.0), sring(0, 0, 0.013, 0.18, 0.155, 48, 5.0)])
    loft(k, bag, [sring(0, 0, 0.59, 0.218, 0.186, 48, 5.0), sring(0, 0, 0.625, 0.219, 0.187, 48, 5.0)])
    loft(k, body, [sring(0, 0.0, 0.627, 0.222, 0.19, 48, 5.0), sring(0, 0.0, 0.655, 0.218, 0.186, 48, 5.0),
                   sring(0, 0.01, 0.672, 0.19, 0.16, 48, 4.0)])
    k.rbox("PlasticBlack", (0, -0.178, 0.02), (0.18, 0.09, 0.02), r=0.006, seg=2)
    k.rbox("PlasticBlack", (0, -0.155, 0.045), (0.04, 0.02, 0.05), r=0.005, seg=1)
    for s in (-1, 1):
        k.cyl("PlasticBlack", (s * 0.13, 0.185, 0.035), (s * 0.16, 0.185, 0.035), 0.035, seg=20, r_edge=0.004)
    k.cyl("PlasticGrey", (-0.15, 0.19, 0.64), (0.15, 0.19, 0.64), 0.008, seg=12)
    a = math.atan2(0.025, 0.57)
    zc = 0.36
    yfc = -(0.16 + 0.02 * (zc - 0.03) / 0.57) - 0.0015
    k.decal(decal_png, (0, yfc, zc), (0, -math.cos(a), -math.sin(a)), (0, -math.sin(a), math.cos(a)), decal_w,
            decal_w * 1.4)


def build_waste_station(k):
    bio = decals.warning_sign(tex("warn_biohazard_bin.png"), "biohazard", ["Biohazard", "waste"])
    gen = decals.plain_sign(tex("lbl_general_waste.png"), ["General", "waste", "no lab waste"], w=600, h=840,
                            sizes=[120, 120, 56], bg=(240, 240, 238))
    with k.at((0.02, 0, 0)):
        pedal_bin(k, "PlasticYellow", "PlasticOrange", bio)
    with k.at((0.52, 0, 0)):
        pedal_bin(k, "PlasticGrey", "PlasticBlack", gen)
    # sharps container on a small floor stand
    with k.at((0.95, 0.02, 0)):
        k.lathe("PlasticGrey", [(0.0, 0.0), (0.16, 0.0), (0.165, 0.01), (0.15, 0.025), (0.03, 0.035), (0.0, 0.035)], seg=40)
        k.cyl("StainlessSatin", (0, 0, 0.03), (0, 0, 0.84), 0.017, seg=20)
        k.rbox("StainlessSatin", (0, 0, 0.845), (0.20, 0.17, 0.01), r=0.003, seg=1)
        for s in (-1, 1):
            k.rbox("StainlessSatin", (s * 0.105, 0, 0.88), (0.006, 0.17, 0.08), r=0.002, seg=1)
        k.rbox("PlasticYellow", (0, 0, 0.85 + 0.11), (0.20, 0.15, 0.22), r=0.01, seg=2)
        k.rbox("PlasticRed", (0, 0, 1.085), (0.205, 0.155, 0.03), r=0.008, seg=2)
        k.rbox("PlasticRed", (0, 0.0, 1.104), (0.15, 0.10, 0.012), r=0.005, seg=1)
        k.rbox("PlasticBlack", (0, -0.01, 1.1105), (0.08, 0.025, 0.002), r=0.0)
        sh = decals.warning_sign(tex("warn_sharps.png"), "biohazard", ["Sharps", "only"])
        k.decal(sh, (0, -0.0757, 0.955), (0, -1, 0), (0, 0, 1), 0.10, 0.14)
    # stainless waste trolley, 2 shelves
    with k.at((-0.68, 0.0, 0)):
        Lx, Ly = 0.80, 0.50
        for x in (-0.36, 0.36):
            for y in (-0.21, 0.21):
                castor(k, x, y, 0.13, r=0.05, brake=(x < 0 and y < 0))
                k.cyl("StainlessSatin", (x, y, 0.13), (x, y, 0.90), 0.0125, seg=16)
                k.cyl("PlasticGrey", (x, y, 0.90), (x, y, 0.915), 0.014, seg=16, r_edge=0.004)
        for zs in (0.22, 0.75):
            k.rbox("StainlessBrushed", (0, 0, zs), (Lx, Ly, 0.002), r=0.0)
            for (cx, cy, sx, sy) in ((0, -Ly / 2, Lx, 0.002), (0, Ly / 2, Lx, 0.002), (-Lx / 2, 0, 0.002, Ly),
                                     (Lx / 2, 0, 0.002, Ly)):
                k.rbox("StainlessBrushed", (cx, cy, zs + 0.015), (sx + 0.002, sy + 0.002, 0.03), r=0.0)
            k.rbox("StainlessBrushed", (0, 0, zs - 0.015), (Lx, 0.03, 0.03), r=0.002, seg=1)
        hp = [(0.36, -0.21, 0.88), (0.42, -0.21, 0.90), (0.43, -0.18, 0.95), (0.43, 0.18, 0.95), (0.42, 0.21, 0.90),
              (0.36, 0.21, 0.88)]
        k.tube("StainlessSatin", hp, 0.011, seg=14)
        k.rbox("PlasticYellow", (-0.15, 0.0, 0.222 + 0.11), (0.30, 0.30, 0.22), r=0.015, seg=2)
        k.rbox("PlasticYellow", (-0.15, 0.0, 0.222 + 0.225), (0.31, 0.31, 0.02), r=0.008, seg=1)
        k.decal(bio, (-0.15, -0.1506, 0.33), (0, -1, 0), (0, 0, 1), 0.08, 0.112)
        box_item(k, 0.20, 0.0, 0.222, 0.30, 0.30, 0.18, mat="Cardboard")
        box_item(k, -0.15, 0.02, 0.752, 0.30, 0.25, 0.10, mat="Cardboard", yaw=4)
    tag = asset_tag("WW-WST1", "Waste station")
    with k.at((-0.68, -0.25, 0.735)):
        k.rbox("StainlessBrushed", (0.2, -0.0005, 0), (0.10, 0.001, 0.045), r=0.0)
        k.decal(tag, (0.2, -0.0016, 0), (0, -1, 0), (0, 0, 1), 0.09, 0.037)
    k.frame("drop_point", (0.02, -0.05, 0.75))
    k.frame("drop_point_general", (0.52, -0.05, 0.75))
    k.frame("sharps", (0.95, 0.01, 1.12))
    k.frame("operator_position", (0.2, -0.65, 0))
    k.collide((-0.68, 0, 0.475), (0.86, 0.55, 0.95))
    k.collide((0.02, 0, 0.34), (0.43, 0.40, 0.68))
    k.collide((0.52, 0, 0.34), (0.43, 0.40, 0.68))
    k.collide((0.95, 0.02, 0.56), (0.33, 0.33, 1.12))


# ============================================================================================ 13 operator desk
def monitor(k, png, em=420):
    """27 in monitor, local: screen face at y=0 facing -Y, centred at the origin."""
    k.rbox("PlasticBlack", (0, 0.009, 0), (0.615, 0.018, 0.37), r=0.004, seg=2)
    k.decal(png, (0, -0.0007, 0.008), (0, -1, 0), (0, 0, 1), 0.597, 0.336, emissive=em)
    k.rbox("PlasticBlack", (0, 0.035, -0.015), (0.42, 0.04, 0.25), r=0.02, seg=2)
    k.rbox("PlasticGrey", (0, 0.06, 0), (0.12, 0.012, 0.12), r=0.004, seg=1)
    k.disk("IndicatorGreen", (0.29, -0.0006, -0.176), 0.0018, normal=(0, -1, 0), seg=8)


def office_chair(k):
    """Swivel office chair, local front (seat front) toward -Y."""
    star_base(k, R=0.33, z=0.085, cr=0.025)
    k.cyl("PlasticBlack", (0, 0, 0.11), (0, 0, 0.30), 0.028, seg=24)
    k.cyl("Chrome", (0, 0, 0.30), (0, 0, 0.40), 0.0145, seg=16)
    k.rbox("PlasticBlack", (0, 0.02, 0.405), (0.22, 0.26, 0.04), r=0.01, seg=2)
    k.cyl("PlasticBlack", (0.10, -0.05, 0.40), (0.19, -0.09, 0.40), 0.005, seg=8)
    k.sphere("PlasticBlack", (0.195, -0.092, 0.40), 0.011, seg=12)
    k.rbox("PlasticBlack", (0, 0, 0.431), (0.46, 0.44, 0.014), r=0.006, seg=2)
    k.rbox("FabricGrey", (0, 0, 0.468), (0.49, 0.47, 0.07), r=0.03, seg=3)
    k.tube("PlasticBlack", [(0, 0.12, 0.40), (0, 0.24, 0.405), (0, 0.28, 0.44), (0, 0.29, 0.56)], 0.022, seg=14)
    with k.at((0, 0.30, 0.82), R=rot_x(-8)):
        k.rbox("PlasticBlack", (0, 0.03, 0), (0.43, 0.02, 0.50), r=0.008, seg=2)
        k.rbox("FabricGrey", (0, 0.0, 0), (0.46, 0.055, 0.54), r=0.026, seg=3)
    for s in (-1, 1):
        k.rbox("PlasticBlack", (s * 0.18, 0.04, 0.405), (0.16, 0.05, 0.02), r=0.006, seg=1)
        k.rbox("PlasticBlack", (s * 0.255, 0.04, 0.53), (0.028, 0.05, 0.24), r=0.008, seg=2)
        k.rbox("PlasticBlack", (s * 0.255, 0.02, 0.655), (0.075, 0.25, 0.03), r=0.012, seg=2)


def build_operator_desk(k):
    O, Wf = "OakVeneer", "PowderWhite"
    k.rbox(O, (0, 0, 0.7275), (1.80, 0.80, 0.025), r=0.003, seg=2)
    for s in (-1, 1):
        x = s * 0.82
        k.rbox(Wf, (x, 0.0, 0.03), (0.06, 0.72, 0.04), r=0.006, seg=2)
        k.rbox(Wf, (x, 0.0, 0.70), (0.05, 0.70, 0.03), r=0.004, seg=2)
        k.rbox(Wf, (x, 0.0, 0.365), (0.07, 0.04, 0.65), r=0.005, seg=2)
        for y in (-0.33, 0.33):
            k.cyl("PlasticBlack", (x, y, 0.0), (x, y, 0.01), 0.016, seg=14)
    k.rbox(Wf, (0, 0.25, 0.685), (1.58, 0.05, 0.05), r=0.004, seg=2)
    k.rbox(Wf, (0, 0.32, 0.47), (1.56, 0.012, 0.36), r=0.004, seg=2)
    with k.at((0, 0.3135, 0.47)):
        perforated(k, 1.40, 0.30, 0.03, 0.006, mat="PowderGrey", proud=0.0008, seg=8)
    k.box_between(Wf, (-0.50, 0.16, 0.62), (0.50, 0.30, 0.624))
    k.box_between(Wf, (-0.50, 0.16, 0.624), (0.50, 0.163, 0.67))
    # monitor arm: clamp, pole, crossbar, three 27 in monitors
    k.rbox("PlasticBlack", (0, 0.36, 0.755), (0.08, 0.08, 0.03), r=0.006, seg=2)
    k.rbox("PlasticBlack", (0, 0.36, 0.700), (0.06, 0.06, 0.02), r=0.004, seg=1)
    k.cyl("AluDark", (0, 0.36, 0.77), (0, 0.36, 1.20), 0.02, seg=24, r_edge=0.003)
    k.rbox("AluDark", (0, 0.36, 1.12), (1.10, 0.04, 0.035), r=0.008, seg=2)
    centre_png = decals.screen_dashboard(tex("scr_desk_dashboard.png"))
    hmi_png = decals.screen_hmi(tex("scr_desk_hmi.png"), [
        ("H4", "Plate hotel", "ready", True), ("L09", "Plate hotel", "ready", True),
        ("L10", "ID reader", "idle", True), ("L12", "Dispenser", "idle", True),
        ("L17", "Imager", "ready", True), ("L21", "Reference", "ok", True),
        ("R02", "Robot", "auto", True), ("R03", "Robot", "paused", False)])
    code_png = decals.screen_code(tex("scr_desk_code.png"))
    zc = 1.11
    with k.at((0, 0.20, zc)):
        monitor(k, centre_png)
    k.cyl("AluDark", (0, 0.26, 1.11), (0, 0.345, 1.11), 0.012, seg=14)
    for s, png in ((-1, hmi_png), (1, code_png)):
        yaw = 30 * -s
        a = math.radians(yaw)
        hinge = np.array([s * 0.318, 0.20])
        c = hinge + s * 0.3075 * np.array([math.cos(a), math.sin(a)])
        with k.at((c[0], c[1], zc), yaw=yaw):
            monitor(k, png)
        back = c + 0.065 * np.array([-math.sin(a), math.cos(a)])
        k.tube("AluDark", [(back[0], back[1], 1.11), (s * 0.50, 0.32, 1.12), (s * 0.54, 0.36, 1.12)], 0.011, seg=12)
    # keyboard, mouse, phone, PC tower
    with k.at((0, -0.20, 0.74)):
        k.rbox("PlasticBlack", (0, 0, 0.011), (0.44, 0.14, 0.022), r=0.005, seg=2)
        for row in range(5):
            for col in range(15):
                k.rbox("PlasticGrey" if row else "PlasticBlack", (-0.196 + col * 0.028, -0.048 + row * 0.024, 0.0235),
                       (0.024, 0.02, 0.006), r=0.0)
        k.rbox("PlasticGrey", (0.0, -0.048, 0.0235), (0.14, 0.02, 0.006), r=0.0)
    loft(k, "PlasticBlack", [sring(0.33, -0.20, 0.74 + z, 0.031 * f, 0.055 * f, 32, 2.4)
                             for z, f in ((0.0, 0.92), (0.004, 1.0), (0.018, 0.95), (0.03, 0.75), (0.036, 0.45))])
    with k.at((-0.62, -0.10, 0.74), yaw=15):
        ext_x(k, "PlasticBlack", [(-0.09, 0.0), (0.09, 0.0), (0.09, 0.075), (-0.09, 0.035)], -0.10, 0.10)
        with k.at((0.0, 0.0, 0.055), R=rot_x(-12.5)):
            k.rbox("PlasticBlack", (-0.055, 0.02, 0.008), (0.06, 0.20, 0.03), r=0.012, seg=2)
            for i in range(12):
                k.rbox("PlasticGrey", (0.02 + (i % 3) * 0.022, -0.05 + (i // 3) * 0.018, 0.001),
                       (0.016, 0.012, 0.004), r=0.0)
            ph = device_screen("phone", ["ext 01", "Cell 01 desk"], accent=(120, 140, 160))
            k.decal(ph, (0.045, 0.055, 0.0007), (0, 0, 1), (0, 1, 0), 0.07, 0.044, emissive=150)
    with k.at((0.60, 0.05, 0)):
        for x in (-0.08, 0.08):
            for y in (-0.19, 0.19):
                k.cyl("RubberBlack", (x, y, 0), (x, y, 0.012), 0.012, seg=12)
        k.rbox("PowderAnthracite", (0, 0, 0.012 + 0.225), (0.20, 0.45, 0.45), r=0.006, seg=2)
        with k.at((0, -0.225, 0.237)):
            k.rbox("PlasticBlack", (0, -0.002, 0.0), (0.18, 0.004, 0.42), r=0.003, seg=1)
            slots(k, 0.14, 0.28, 18, mat="PowderAnthracite", proud=0.0045, frac=0.35)
            k.disk("StackBlue", (0, -0.0048, 0.18), 0.009, normal=(0, -1, 0), seg=20)
    with k.at((0, -0.62, 0), yaw=180):
        office_chair(k)
    tag = asset_tag("OP-DSK1", "Operator desk")
    k.decal(tag, (0.70, -0.2256, 0.42), (0, -1, 0), (0, 0, 1), 0.08, 0.033)
    k.frame("operator_position", (0, -0.70, 0))
    k.frame("screens", (0, 0.20, zc))
    k.frame("keyboard", (0, -0.20, 0.765))
    k.collide((0, 0, 0.37), (1.80, 0.80, 0.74))
    k.collide((0, 0.25, 1.06), (1.60, 0.30, 0.42))
    k.collide((0, -0.62, 0.50), (0.66, 0.66, 1.0))


# ============================================================================================ 14 lab stool
def build_lab_stool(k):
    star_base(k, R=0.30, z=0.085, cr=0.025, mat="AluDark")
    k.cyl("PlasticBlack", (0, 0, 0.11), (0, 0, 0.42), 0.028, seg=24)
    k.cyl("Chrome", (0, 0, 0.42), (0, 0, 0.56), 0.0145, seg=16)
    k.lathe("Chrome", [(0.214, 0.0), (0.226, 0.0)], base=(0, 0, 0.33), seg=48)
    k.tube("Chrome", [(0.22 * math.cos(a), 0.22 * math.sin(a), 0.33) for a in np.linspace(0, 2 * math.pi, 49)], 0.009,
           seg=12)
    k.cyl("Chrome", (0, 0, 0.32), (0, 0, 0.345), 0.04, seg=20, r_edge=0.004)
    for i in range(3):
        a = math.radians(90 + 120 * i)
        k.cyl("Chrome", (0.04 * math.cos(a), 0.04 * math.sin(a), 0.333), (0.215 * math.cos(a), 0.215 * math.sin(a), 0.33),
              0.007, seg=10)
    k.rbox("PlasticBlack", (0, 0, 0.57), (0.16, 0.16, 0.025), r=0.006, seg=1)
    k.lathe("PlasticBlack", [(0.0, 0.58), (0.17, 0.58), (0.176, 0.586), (0.172, 0.594), (0.0, 0.594)], seg=48)
    k.lathe("FabricGrey", [(0.0, 0.593), (0.172, 0.593), (0.18, 0.605), (0.18, 0.635), (0.168, 0.648), (0.12, 0.652),
                           (0.0, 0.653)], seg=48)
    k.cyl("PlasticBlack", (0.0, -0.06, 0.57), (0.13, -0.12, 0.565), 0.005, seg=8)
    k.frame("seat", (0, 0, 0.653))
    k.collide((0, 0, 0.33), (0.60, 0.60, 0.66))


# ============================================================================================ 15 glove dispenser
def build_glove_dispenser(k):
    A = "PolystyreneClear"
    W, H, D = 0.42, 0.27, 0.085
    k.rbox(A, (0, -0.0025, 0), (W, 0.005, H), r=0.002, seg=1)
    for x in (-W / 2 + 0.0025, -0.068, 0.068, W / 2 - 0.0025):
        k.rbox(A, (x, -D / 2, 0), (0.005, D, H), r=0.0015, seg=1)
    k.rbox(A, (0, -D / 2, -H / 2 + 0.0025), (W, D, 0.005), r=0.0015, seg=1)
    k.rbox(A, (0, -D / 2, H / 2 - 0.0025), (W, D, 0.005), r=0.0015, seg=1)
    k.rbox(A, (0, -D + 0.0025, -H / 2 + 0.025), (W, 0.005, 0.05), r=0.0015, seg=1)
    for x in (-W / 2 + 0.01, W / 2 - 0.01):
        for z in (-0.10, 0.10):
            k.cyl("StainlessSatin", (x, -0.005, z), (x, -0.008, z), 0.005, seg=12)
    for i, size in enumerate("SML"):
        x = -0.136 + i * 0.136
        bw, bh, bd = 0.126, 0.245, 0.068
        k.rbox("PaperWhite", (x, -0.006 - bd / 2, -H / 2 + 0.005 + bh / 2), (bw, bd, bh), r=0.0015, seg=1)
        png = glove_face(size)
        zc = -H / 2 + 0.005 + bh / 2
        k.decal(png, (x, -0.006 - bd - 0.0006, zc), (0, -1, 0), (0, 0, 1), bw - 0.003, bh - 0.003)
        oz = zc + bh / 2 - 0.003 - (bh - 0.003) * (125 / 576)
        _glove_tuft(k, x, oz, size)
        k.frame(f"glove_{size}", (x, -0.10, oz))
    tag = asset_tag("PR-GLV1", "Glove dispenser")
    k.decal(tag, (0.0, -D - 0.0006, -H / 2 + 0.025), (0, -1, 0), (0, 0, 1), 0.08, 0.033)
    k.collide((0, -D / 2, 0), (W, D, H))


def _glove_tuft(k, x, z, size):
    """A glove cuff poking out of the dispensing slot (crumpled loft)."""
    col = {"S": "PlasticBlue", "M": "PlasticBlue", "L": "PlasticBlue"}[size]
    rings = []
    for t, (dy, rx, rz, dz) in enumerate(((0.0, 0.030, 0.006, 0.0), (-0.008, 0.028, 0.010, -0.002),
                                           (-0.016, 0.022, 0.009, -0.010), (-0.020, 0.012, 0.006, -0.020),
                                           (-0.021, 0.004, 0.003, -0.026))):
        th = np.linspace(0, 2 * math.pi, 20, endpoint=False)
        wob = 1 + 0.12 * np.sin(3 * th + t)
        pts = np.stack([x + rx * np.cos(th) * wob + 0.003 * t, np.full(20, -0.0745 + dy), z + dz + rz * np.sin(th) * wob], 1)
        rings.append(pts)
    loft(k, col, rings)


# ============================================================================================ 16 lab coat rack
def lab_coat(k, hx, seed=0, scale=1.0):
    """White lab coat hung by its collar loop from a hook tip at (hx, -0.065, 0); tapered body, sleeves, pockets."""
    rng = np.random.default_rng(seed)
    C = "PaperWhite"
    Lc = 1.0 * scale
    ph = rng.uniform(0, 6.28)

    def hw_of(t):
        if t < 0.05:
            return (0.05 + t / 0.05 * 0.05) * scale
        if t < 0.20:
            return (0.10 + (t - 0.05) / 0.15 * 0.09) * scale
        return (0.19 + (t - 0.20) * 0.025) * scale

    def hd_of(t):
        return 0.022 + 0.030 * min(1.0, t / 0.2)

    def yc_of(t):
        return -0.062 + (0.062 - (hd_of(t) + 0.006)) * min(1.0, t / 0.12)
    rings = []
    for z in np.linspace(-0.01, -Lc, 30):
        t = -z / Lc

        def rip(th, t=t):
            return 1 + 0.035 * t ** 2 * np.sin(7 * th + ph) + 0.01 * np.sin(3 * th + 2 * t)
        rings.append(sring(hx, yc_of(t), z, hw_of(t), hd_of(t), n=40, p=2.8, ripple=rip))
    loft(k, C, rings)

    def front_y(x_off, z):
        t = -z / Lc
        u = min(0.98, abs(x_off) / hw_of(t))
        return yc_of(t) - hd_of(t) * (1 - u ** 2.8) ** (1 / 2.8)
    # sleeves hanging along the front sides of the body
    for sd in (-1, 1):
        sr = []
        for z in np.linspace(-0.12 * scale, -0.72 * scale, 12):
            t = -z / Lc
            r = (0.05 - 0.008 * (t - 0.12) / 0.6) * scale
            sx = hx + sd * (hw_of(t) - r * 0.55)
            sr.append(sring(sx, yc_of(t) - hd_of(t) * 0.55, z, r * 0.8, r * 0.75, n=20, p=2.2))
        loft(k, C, sr)
    # collar band, placket with buttons, pockets
    loft(k, C, [sring(hx, -0.058, -0.005, 0.06, 0.028, 32, 2.5), sring(hx, -0.056, -0.06, 0.075 * scale, 0.034, 32, 2.5)])
    for z in (-0.18, -0.34, -0.50, -0.66):
        y = front_y(0.0, z * scale)
        k.cyl("PlasticWhite", (hx, y + 0.001, z * scale), (hx, y - 0.003, z * scale), 0.007, seg=14, r_edge=0.0015)
    for z in np.linspace(-0.08, -0.98, 24):
        y = front_y(0.012, z * scale)
        k.box(C, (hx + 0.012, y - 0.0007, z * scale), (0.003, 0.0012, 0.04 * scale))
    for (px, pz, pw, phh) in ((0.08, -0.26, 0.09, 0.12), (-0.11, -0.66, 0.12, 0.15), (0.11, -0.66, 0.12, 0.15)):
        px, pz = px * scale, pz * scale
        y = min(front_y(px - pw / 2, pz), front_y(px + pw / 2, pz), front_y(px, pz))
        k.rbox(C, (hx + px, y - 0.0005, pz), (pw, 0.003, phh), r=0.001, seg=1)


def build_lab_coat_rack(k):
    k.rbox("AluAnodized", (0, -0.01, 0.0), (1.20, 0.02, 0.07), r=0.004, seg=2)
    for x in (-0.58, 0.58):
        k.cyl("Chrome", (x, -0.0201, 0.0), (x, -0.023, 0.0), 0.006, seg=12)
    hooks = [-0.45, -0.15, 0.15, 0.45]
    for x in hooks:
        k.rbox("Chrome", (x, -0.022, 0.0), (0.03, 0.006, 0.05), r=0.003, seg=1)
        pts = [(x, -0.022, 0.0), (x, -0.05, -0.01), (x, -0.065, -0.004), (x, -0.075, 0.02), (x, -0.073, 0.035)]
        k.tube("Chrome", pts, 0.005, seg=12)
        k.sphere("Chrome", (x, -0.073, 0.035), 0.0065, seg=12)
    with k.at((0, 0, -0.005)):
        lab_coat(k, hooks[0], seed=0, scale=1.0)
        lab_coat(k, hooks[2] - 0.02, seed=1, scale=0.94)
        lab_coat(k, hooks[3] + 0.05, seed=2, scale=1.02)
    tag = asset_tag("PR-COAT1", "Lab coat rail")
    k.decal(tag, (0.0, -0.0206, 0.0), (0, -1, 0), (0, 0, 1), 0.08, 0.033)
    for i, x in enumerate(hooks):
        k.frame(f"hook_{i + 1}", (x, -0.07, 0.0))
    k.collide((0, -0.06, -0.50), (1.2, 0.12, 1.06))


# ============================================================================================ 17 potted plant
def leaf(k, base, az, el, length, width, droop, rng, nu=12):
    s = np.linspace(0, 1, nu)
    elv = el - droop * s ** 1.5
    d = np.stack([np.cos(elv) * math.cos(az), np.cos(elv) * math.sin(az), np.sin(elv)], 1)
    pts = np.asarray(base, float) + np.cumsum(np.vstack([[0, 0, 0], d[:-1] * (length / (nu - 1))]), 0)
    side = np.array([-math.sin(az), math.cos(az), 0.0])
    tw = rng.normal(0, 0.25)
    vs = np.array([-1.0, -0.5, 0.0, 0.5, 1.0])
    G = np.zeros((nu, len(vs), 3))
    for i in range(nu):
        up = np.cross(side, d[i])
        up /= np.linalg.norm(up)
        sd = side * math.cos(tw * s[i]) + up * math.sin(tw * s[i])
        upv = np.cross(sd, d[i])
        w = width * (math.sin(math.pi * min(0.999, s[i] ** 0.7)) ** 0.8) + 0.002 * (1 - s[i])
        for j, v in enumerate(vs):
            G[i, j] = pts[i] + sd * v * w + upv * abs(v) * w * 0.28
    grid_surface(k, "Leaf", G, double=True, thick=0.0008)


def build_potted_plant(k):
    rng = np.random.default_rng(21)
    k.lathe("PlasticWhite", [(0.0, 0.0), (0.140, 0.0), (0.146, 0.006), (0.165, 0.40), (0.175, 0.44), (0.175, 0.45),
                             (0.162, 0.45), (0.158, 0.43)], seg=64)
    k.disk("Soil", (0, 0, 0.41), 0.159, seg=48)
    for _ in range(12):
        a, r = rng.uniform(0, 6.28), rng.uniform(0.02, 0.14)
        k.sphere("Soil", (r * math.cos(a), r * math.sin(a), 0.41), rng.uniform(0.008, 0.016), seg=8)
    canes = [((0.03, 0.02), 1.05), ((-0.05, 0.01), 1.45), ((0.01, -0.05), 1.75)]
    nleaf = 0
    for ci, ((cx, cy), top) in enumerate(canes):
        pts = [(cx, cy, 0.40)]
        for z in np.linspace(0.40, top, 6)[1:]:
            pts.append((cx + rng.normal(0, 0.012) + (z - 0.4) * 0.02 * (ci - 1), cy + rng.normal(0, 0.012), z))
        r = 0.028 - 0.004 * ci
        k.tube("Cardboard", pts, r, seg=14)
        k.disk("Cardboard", pts[-1], r, seg=14)
        tip = np.array(pts[-1])
        nl = 18
        for i in range(nl):
            az = i * 2.39996 + rng.normal(0, 0.15)
            frac = i / (nl - 1)
            el = math.radians(78 - 70 * frac + rng.normal(0, 6))
            ln = rng.uniform(0.38, 0.55) * (0.75 + 0.4 * frac)
            base = tip + [0.0, 0.0, -0.14 * frac + rng.normal(0, 0.01)]
            leaf(k, base, az, el, ln, rng.uniform(0.032, 0.045), math.radians(rng.uniform(40, 80)) * (0.4 + frac), rng)
            nleaf += 1
    k.frame("top", (0, 0, 1.9))
    k.collide((0, 0, 0.225), (0.35, 0.35, 0.45))
    k.collide((0, 0, 1.25), (0.8, 0.8, 1.0))
    return nleaf


# ============================================================================================ 18 whiteboard
def build_whiteboard(k):
    W, H = 1.80, 1.00
    k.rbox("PaperWhite", (0, -0.008, 0), (W - 0.02, 0.012, H - 0.02), r=0.0)
    k.rbox("PlasticWhite", (0, -0.0145, 0), (W - 0.03, 0.001, H - 0.03), r=0.0)
    png = whiteboard_png()
    k.decal(png, (0, -0.0157, 0), (0, -1, 0), (0, 0, 1), W - 0.034, H - 0.034)
    t = 0.018
    for (cx, cz, sx, sz) in ((0, H / 2 - t / 2, W, t), (0, -H / 2 + t / 2, W, t), (-W / 2 + t / 2, 0, t, H - 2 * t),
                             (W / 2 - t / 2, 0, t, H - 2 * t)):
        k.rbox("AluAnodized", (cx, -0.011, cz), (sx, 0.022, sz), r=0.005, seg=2)
    for sx in (-1, 1):
        for sz in (-1, 1):
            k.rbox("PlasticGrey", (sx * (W / 2 - 0.012), -0.0115, sz * (H / 2 - 0.012)), (0.03, 0.024, 0.03), r=0.008,
                   seg=2)
    # marker tray (aluminium L-profile) with markers and an eraser
    zt = -H / 2 - 0.005
    ext_x(k, "AluAnodized", [(-0.002, zt), (-0.002, zt - 0.03), (-0.075, zt - 0.03), (-0.075, zt - 0.012),
                             (-0.071, zt - 0.012), (-0.071, zt - 0.026), (-0.006, zt - 0.026), (-0.006, zt)],
          -0.60, 0.60)
    for i, m in enumerate(("PlasticBlue", "PlasticBlack", "PlasticRed", "PlasticGreen")):
        x0 = 0.05 + i * 0.13
        y = -0.025 - (i % 2) * 0.02
        k.cyl("PlasticWhite", (x0, y, zt - 0.0165), (x0 + 0.11, y, zt - 0.0165), 0.0095, seg=16, r_edge=0.002)
        k.cyl(m, (x0 + 0.105, y, zt - 0.0165), (x0 + 0.14, y, zt - 0.0165), 0.0105, seg=16, r_edge=0.003)
    k.rbox("PlasticBlack", (-0.35, -0.04, zt - 0.006), (0.14, 0.05, 0.03), r=0.005, seg=2)
    k.rbox("FabricGrey", (-0.35, -0.04, zt - 0.0235), (0.135, 0.045, 0.006), r=0.001, seg=1)
    tag = asset_tag("OP-WBD1", "Whiteboard")
    k.decal(tag, (W / 2 - 0.10, -0.0226, -H / 2 + 0.009), (0, -1, 0), (0, 0, 1), 0.035, 0.0145)
    k.frame("marker_tray", (0.2, -0.04, zt - 0.02))
    k.collide((0, -0.012, 0), (W, 0.024, H))


# ============================================================================================ catalogue + main
ASSETS = {
    "bsc_class2": (build_bsc_class2, "PR-BSC1", "biosafety_cabinet_class_II",
                   "Class II biosafety cabinet for open manual culture handling; sash at a 200 mm working aperture."),
    "co2_incubator_stack": (build_co2_incubator_stack, "PR-INC1", "co2_incubator_stack",
                            "Two stacked benchtop CO2 incubators on a castor stand for manual culture."),
    "centrifuge": (build_centrifuge, "PR-CFG1", "benchtop_centrifuge",
                   "Benchtop centrifuge for tube spin-down in the culture-prep area."),
    "inverted_microscope": (build_inverted_microscope, "PR-MIC1", "inverted_microscope",
                            "Inverted transmitted-light microscope for manual inspection of culture vessels."),
    "water_bath": (build_water_bath, "PR-WB1", "water_bath", "Small stainless water bath with a gabled lid."),
    "pipette_stand": (build_pipette_stand, "PR-PIP1", "pipette_carousel",
                      "Carousel holding six single-channel manual pipettes."),
    "lab_bench_island": (build_lab_bench_island, "PR-BEN1", "lab_bench_island",
                         "Double-sided island lab bench with base cabinets, service spine and reagent shelves."),
    "wall_bench": (build_wall_bench, "PR-BEN2", "lab_bench_wall",
                   "Single-sided wall bench with base cabinets, rear service channel and a wall shelf."),
    "lab_sink_unit": (build_lab_sink_unit, "WW-SNK1", "lab_sink_unit",
                      "Stainless lab sink with gooseneck tap, deck eyewash and wall dispensers for hand hygiene."),
    "emergency_shower": (build_emergency_shower, "WW-SHW1", "emergency_shower",
                         "Wall-fed emergency safety shower with pull-rod triangle handle."),
    "autoclave": (build_autoclave, "WW-AC1", "laboratory_autoclave",
                  "Floor-standing front-loading laboratory autoclave for waste and media sterilisation."),
    "waste_station": (build_waste_station, "WW-WST1", "waste_station",
                      "Waste collection point: biohazard and general pedal bins, sharps container and a waste trolley."),
    "operator_desk": (build_operator_desk, "OP-DSK1", "operator_desk",
                      "Control and monitoring desk with three monitors showing the twin dashboard and cell HMI."),
    "lab_stool": (build_lab_stool, "OP-STL1", "lab_stool", "Height-adjustable lab stool on castors."),
    "glove_dispenser": (build_glove_dispenser, "PR-GLV1", "glove_dispenser",
                        "Wall-mounted holder with three nitrile glove boxes (S/M/L)."),
    "lab_coat_rack": (build_lab_coat_rack, "PR-COAT1", "lab_coat_rack",
                      "Wall rail with four hooks and three hanging lab coats."),
    "potted_plant": (build_potted_plant, "OP-PLT1", "potted_plant", "Tall indoor plant in a white planter (decor)."),
    "whiteboard": (build_whiteboard, "OP-WBD1", "whiteboard",
                   "Wall whiteboard with a hand-drawn culture-handling process sketch."),
}


def build(name):
    fn, aid, cls, role = ASSETS[name]
    k = Kit()
    fn(k)
    st, root = new_asset(os.path.join(USD_DIR, f"{name}.usda"),
                         comment="Generated by assets/labequip/build_prep.py - edit the script, not this file.")
    sem = {"sdt:assetId": aid, "sdt:class": cls, "sdt:role": role, "sdt:bindingStatus": "visual_proxy_v1",
           "sdt:designBasis": DESIGN}
    ntri = k.write(st, root, sem)
    st.GetRootLayer().Save()
    P = np.concatenate([p[0] for plist in k.parts.values() for p in plist])
    lo, hi = P.min(0), P.max(0)
    return ntri, lo, hi, sorted(k.frames), len(k.colliders)


def main():
    names = sys.argv[1:] or list(ASSETS)
    os.makedirs(TEX, exist_ok=True)
    for n in names:
        ntri, lo, hi, frames, nc = build(n)
        sz = hi - lo
        print(f"{n:22s} tris {ntri:7d}  size {sz[0]:.2f} x {sz[1]:.2f} x {sz[2]:.2f}  "
              f"z[{lo[2]:.2f},{hi[2]:.2f}]  colliders {nc}  frames {', '.join(frames)}")


if __name__ == "__main__":
    main()
