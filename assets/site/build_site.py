"""AICOR Lab 1 building shell around Cell 01 (site layout proposal S1): hall, storage room, doors, windows, ceiling,
luminaires, floor markings, cable trays, the CO2 line to L10, utility panels, exterior context.

The Cell 01 specification bounds the cell (6.0 x 4.5 x 2.5 m, rear service access >= 1.0 m outside the cell, front
logistics lane); it does not define the surrounding laboratory. This shell is therefore a PROPOSAL (layout S1,
proposals/site/README.md), drawn in the Cell 01 frame (origin at the cell's floor centre, +Y toward the rear
instrument wall):

  hall          x -9.6 .. 9.6, y -7.0 .. 4.2, finished ceiling 3.2 m (suspended 600 mm tiles, 600 x 600 LED panels)
  storage ST01  x -9.6 .. -5.2, y -1.2 .. 4.2; automatic sliding door x -7.1 .. -5.7 on its south wall (AMR + staff)
  entrance      west wall, y -4.6 .. -3.0 (double door to the building corridor); gowning zone around it
  windows       south wall: four 3.0 m bays, sill 0.85 m, head 2.75 m, venetian blinds, radiators
  east door     to the neighbouring lab (y -2.6 .. -1.6)
  rear corridor between the cell (y 2.30) and the north wall: >= 1.9 m service access (spec: >= 1.0 m)
  AMR route     storage S1 dock (-6.4, 0.6) -> door -> lane y -3.3 -> Cell 01 AMR portal (x 1.15) -> H2 (floor-marked)

The storage sliding door is an articulation (fixed frame -> prismatic -> leaf, driven closed; twin/site_doors.py).
Lights are UsdLux RectLights behind emissive diffusers (path-traced and RTX real-time alike).

Run: env_cad/bin/python assets/site/build_site.py
"""

import math
import os
import sys

import numpy as np
from pxr import Gf, Sdf, UsdGeom, UsdLux, UsdPhysics

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
from assets.common import decals  # noqa: E402
from assets.common.meshkit import Kit, new_asset  # noqa: E402

USD = os.path.join(HERE, "usd")
TEX = os.path.join(HERE, "textures")
H = 3.20                                   # finished ceiling height
HALL = dict(x0=-9.6, x1=9.6, y0=-7.0, y1=4.2)
EXT_T, INT_T = 0.25, 0.12
STORE = dict(x0=-9.6, x1=-5.2, y0=-1.2, y1=4.2)
STORE_DOOR = (-7.1, -5.7, 2.40)            # x range, height (south wall of the storage room)
ENTRANCE = (-4.6, -3.0, 2.30)              # y range on the west wall, height
EAST_DOOR = (-2.6, -1.6, 2.20)
WINDOWS = [(-8.7, -5.7), (-3.3, -0.3), (0.3, 3.3), (5.7, 8.7)]
SILL, HEAD = 0.85, 2.75
AMR_ROUTE = [(-6.4, 0.6), (-6.4, -1.2), (-6.4, -3.3), (1.15, -3.3), (1.15, -2.25), (1.15, -1.0), (0.75, -0.28),
             (-0.415, -0.28)]
LANE_W = 1.30


def tex(name):
    return os.path.join(TEX, name)


# ------------------------------------------------------------------------------------------- walls
def wall(k, a, b, t, openings=(), h=H, inner_side=1, mat="WallPaint", collide=True, skirting=True):
    """Straight wall from a to b (centre line), thickness t, with openings [(s0, s1, z0, z1)] along it (s from a)."""
    a, b = np.array(a, float), np.array(b, float)
    L = np.linalg.norm(b - a)
    yaw = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    with k.at((a[0], a[1], 0), yaw=yaw):
        cuts = sorted(openings)
        s = 0.0
        pieces = []
        for (s0, s1, z0, z1) in cuts:
            if s0 > s:
                pieces.append((s, s0, 0.0, h))
            if z0 > 0:
                pieces.append((s0, s1, 0.0, z0))
            if z1 < h:
                pieces.append((s0, s1, z1, h))
            s = s1
        if s < L:
            pieces.append((s, L, 0.0, h))
        for (s0, s1, z0, z1) in pieces:
            k.box(mat, ((s0 + s1) / 2, 0, (z0 + z1) / 2), (s1 - s0, t, z1 - z0))
            if collide:
                k.collide(((s0 + s1) / 2, 0, (z0 + z1) / 2), (s1 - s0, t, z1 - z0))
        if skirting:
            for side in ((1, -1) if inner_side == 0 else (inner_side,)):
                s = 0.0
                spans = []
                for (s0, s1, z0, z1) in cuts:
                    if z0 <= 0.01:
                        spans.append((s, s0))
                        s = s1
                spans.append((s, L))
                for (s0, s1) in spans:
                    if s1 - s0 > 0.02:
                        k.box("VinylSkirting", ((s0 + s1) / 2, side * (t / 2 + 0.006), 0.05), (s1 - s0, 0.012, 0.10))


def door_frame(k, center, yaw, w, h, t):
    """Steel door frame (architrave) around an opening of width w, height h in a wall of thickness t."""
    with k.at(center, yaw=yaw):
        for x in (-w / 2 - 0.025, w / 2 + 0.025):
            k.rbox("PowderGrey", (x, 0, h / 2), (0.05, t + 0.03, h), r=0.004)
        k.rbox("PowderGrey", (0, 0, h + 0.025), (w + 0.10, t + 0.03, 0.05), r=0.004)


def swing_door_leaf(k, center, yaw, w, h, vision=True, push_bar=False, hinge_left=True):
    with k.at(center, yaw=yaw):
        k.rbox("DoorLaminate", (0, 0, h / 2), (w - 0.01, 0.045, h - 0.01), r=0.003)
        if vision:
            k.box("WindowGlass", (0, 0, 1.45), (0.25, 0.05, 0.70))
            for side in (-1, 1):
                k.rbox("PowderGrey", (0, side * 0.0235, 1.45), (0.29, 0.004, 0.74), r=0.002)
        hx = (w / 2 - 0.08) * (1 if hinge_left else -1)
        for side in (-1, 1):
            if push_bar:
                k.cyl("StainlessSatin", (-w / 2 + 0.08, side * 0.07, 1.0), (w / 2 - 0.08, side * 0.07, 1.0), 0.016, seg=16)
                for x in (-w / 2 + 0.08, w / 2 - 0.08):
                    k.rbox("StainlessSatin", (x, side * 0.047, 1.0), (0.03, 0.05, 0.08), r=0.004)
            else:
                k.rbox("StainlessSatin", (hx, side * 0.026, 1.05), (0.045, 0.008, 0.20), r=0.003)
                k.cyl("StainlessSatin", (hx, side * 0.03, 1.08), (hx, side * 0.07, 1.08), 0.010, seg=12)
                k.cyl("StainlessSatin", (hx, side * 0.07, 1.08), (hx - math.copysign(0.13, hx), side * 0.07, 1.08), 0.010, seg=12)
        k.rbox("AluDark", ((-w / 2 + 0.15) * (1 if hinge_left else -1), 0.05, h - 0.06), (0.30, 0.05, 0.05), r=0.005)


def window(k, x0, x1, y_inner):
    """Window bay in the south wall: frame, two sashes, double glazing, inner sill, blind, radiator."""
    t = EXT_T
    yc = y_inner - t / 2
    w = x1 - x0
    fr = 0.065
    # outer frame
    k.box("AluAnodized", ((x0 + x1) / 2, yc, SILL + fr / 2), (w, 0.08, fr))
    k.box("AluAnodized", ((x0 + x1) / 2, yc, HEAD - fr / 2), (w, 0.08, fr))
    for x in (x0 + fr / 2, (x0 + x1) / 2, x1 - fr / 2):
        k.box("AluAnodized", (x, yc, (SILL + HEAD) / 2), (fr if x != (x0 + x1) / 2 else 0.09, 0.08, HEAD - SILL))
    for (a, c) in ((x0 + fr, (x0 + x1) / 2 - 0.045), ((x0 + x1) / 2 + 0.045, x1 - fr)):
        k.box("WindowGlass", ((a + c) / 2, yc - 0.012, (SILL + HEAD) / 2), (c - a, 0.006, HEAD - SILL - 2 * fr))
        k.box("WindowGlass", ((a + c) / 2, yc + 0.012, (SILL + HEAD) / 2), (c - a, 0.006, HEAD - SILL - 2 * fr))
        k.rbox("AluAnodized", (c - 0.06 if a < (x0 + x1) / 2 else a + 0.06, yc + 0.045, (SILL + HEAD) / 2 - 0.25),
               (0.025, 0.02, 0.14), r=0.006)                                        # window handle
    # inner sill + reveal
    k.rbox("PhenolicLight", ((x0 + x1) / 2, y_inner + 0.06 - t / 2 + 0.0, SILL - 0.015), (w + 0.10, t / 2 + 0.12, 0.03), r=0.004)
    # venetian blind, lowered to 55 %, slats tilted (sun patterns)
    drop = 0.55 * (HEAD - SILL)
    k.rbox("PowderWhite", ((x0 + x1) / 2, y_inner + 0.06, HEAD - 0.03), (w - 0.10, 0.06, 0.05), r=0.004)
    n = int(drop / 0.045)
    for i in range(n):
        z = HEAD - 0.07 - i * 0.045
        R = np.array([[1, 0, 0], [0, math.cos(0.6), -math.sin(0.6)], [0, math.sin(0.6), math.cos(0.6)]])
        with k.at(((x0 + x1) / 2, y_inner + 0.06, z), R=R):
            k.box("PowderWhite", (0, 0, 0), (w - 0.12, 0.05, 0.0015))
    k.rbox("PowderWhite", ((x0 + x1) / 2, y_inner + 0.06, HEAD - 0.07 - n * 0.045), (w - 0.10, 0.055, 0.02), r=0.004)
    for x in ((x0 + x1) / 2 - w / 4, (x0 + x1) / 2 + w / 4):
        k.cyl("PlasticWhite", (x, y_inner + 0.045, HEAD - 0.05), (x, y_inner + 0.045, HEAD - 0.07 - n * 0.045), 0.001, seg=6)
    # radiator under the sill
    rw = w - 0.6
    k.rbox("PowderWhite", ((x0 + x1) / 2, y_inner + 0.06, 0.40), (rw, 0.10, 0.60), r=0.01)
    for i in range(int(rw / 0.05)):
        k.box("PowderGrey", ((x0 + x1) / 2 - rw / 2 + 0.025 + i * 0.05, y_inner + 0.115, 0.40), (0.012, 0.01, 0.56))
    k.cyl("Chrome", (x1 - 0.25, y_inner + 0.09, 0.15), (x1 - 0.25, y_inner + 0.09, 0.10), 0.012, seg=12)


# ------------------------------------------------------------------------------------------- ceiling + lights
def light_grid():
    """600 x 600 LED panel centres: hall grid 2.4 m, storage room grid 1.8 m (aligned with the tile grid)."""
    pts = []
    for x in np.arange(-4.5, 9.6, 2.4):
        for y in np.arange(-6.3, 4.2, 2.4):
            pts.append((round(x, 2) + 0.0, round(y, 2), "hall"))
    for x in (-8.7, -6.9):
        for y in (-0.3, 1.5, 3.3):
            pts.append((x, y, "storage"))
    # entrance / gowning zone west of the storage wall line
    for x in (-8.7, -6.9):
        for y in (-6.3, -3.9):
            pts.append((x, y, "hall"))
    return pts


def build_ceiling(k):
    k.box("CeilingTile", ((HALL["x0"] + HALL["x1"]) / 2, (HALL["y0"] + HALL["y1"]) / 2, H + 0.01),
          (HALL["x1"] - HALL["x0"], HALL["y1"] - HALL["y0"], 0.02), faces=["-z"])
    for (x, y, _) in light_grid():
        k.rbox("PowderWhite", (x, y, H - 0.012), (0.62, 0.62, 0.025), r=0.003)
        k.box("LedPanel", (x, y, H - 0.0255), (0.58, 0.58, 0.002), faces=["-z"])


def add_lights(st, root):
    UsdGeom.Scope.Define(st, f"{root}/Lights")
    for i, (x, y, zone) in enumerate(light_grid()):
        L = UsdLux.RectLight.Define(st, f"{root}/Lights/Panel_{i:02d}")
        L.CreateWidthAttr(0.58)
        L.CreateHeightAttr(0.58)
        L.CreateIntensityAttr(30000.0)
        L.CreateColorTemperatureAttr(5200.0)
        L.CreateEnableColorTemperatureAttr(True)
        L.AddTranslateOp().Set(Gf.Vec3d(x, y, H - 0.03))
        L.GetPrim().CreateAttribute("sdt:zone", Sdf.ValueTypeNames.String, custom=True).Set(zone)


# ------------------------------------------------------------------------------------------- markings
def tape_line(k, pts, w=0.05, mat="FloorTapeYellow", z=0.0008):
    for a, b in zip(pts[:-1], pts[1:]):
        a, b = np.array(a, float), np.array(b, float)
        d = b - a
        L = np.linalg.norm(d)
        yaw = math.degrees(math.atan2(d[1], d[0]))
        with k.at(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0), yaw=yaw):
            k.box(mat, (0, 0, z), (L + w, w, 0.0016), faces=["+z"])


def lane(k, pts, width, mat="FloorTapeYellow"):
    """Two edge lines offset from a polyline (miter joins)."""
    P = np.array(pts, float)
    for side in (-1, 1):
        off = []
        for i in range(len(P)):
            dirs = []
            if i > 0:
                dirs.append((P[i] - P[i - 1]) / np.linalg.norm(P[i] - P[i - 1]))
            if i < len(P) - 1:
                dirs.append((P[i + 1] - P[i]) / np.linalg.norm(P[i + 1] - P[i]))
            ns = [np.array([-d[1], d[0]]) for d in dirs]
            n = sum(ns) / np.linalg.norm(sum(ns))
            scale = 1.0 / max(0.5, float(n @ ns[0]))
            off.append(P[i] + side * n * width / 2 * scale)
        tape_line(k, off, 0.05, mat)


def build_markings(k):
    # AMR route lane (hall part, from the storage door to the cell portal), arrows + floor text
    hall_route = [(-6.4, -1.4), (-6.4, -3.3), (1.15, -3.3), (1.15, -2.40)]
    lane(k, hall_route, LANE_W)
    arrow = decals.plain_sign(tex("amr_floor.png"), ["AMR ROUTE"], w=1200, h=260, bg=(245, 245, 240),
                              fg=(30, 30, 30), sizes=[150])
    for (x, y, yaw) in ((-6.4, -2.4, 90), (-3.5, -3.3, 0), (-0.5, -3.3, 0)):
        with k.at((x, y, 0), yaw=yaw):
            k.decal(arrow, (0, 0, 0.0012), (0, 0, 1), (0, 1, 0), 1.0, 0.22)
            for dx in (0.75,):
                k.box("FloorTapeWhite", (dx, 0, 0.0010), (0.30, 0.05, 0.0016), faces=["+z"])
                for s in (-1, 1):
                    with k.at((dx + 0.15, 0, 0), yaw=s * 135):
                        k.box("FloorTapeWhite", (0.09, 0, 0.0010), (0.18, 0.05, 0.0016), faces=["+z"])
    # safety band around the cell enclosure (outside, 0.10 m off the frame), hatch at the AMR portal / doors
    e = 0.10 + 0.0225 + 0.03
    xw, yw = 3.025 + e, 2.275 + e
    tape_line(k, [(-xw, -yw), (0.45, -yw)], 0.075, "FloorTapeHatch")
    tape_line(k, [(1.85, -yw), (xw, -yw), (xw, yw), (-xw, yw), (-xw, -yw)], 0.075, "FloorTapeHatch")
    # door swing zones (rear service doors swing out into the corridor; front door into the hall)
    for (x0, x1, y, s) in ((-2.62, -1.58, 2.275, 1), (1.08, 2.12, 2.275, 1), (-1.12, -0.08, -2.275, -1)):
        r = x1 - x0
        arc = [(x0 + r * math.cos(a), y + s * r * math.sin(a)) for a in np.linspace(0, math.pi / 2, 10)]
        tape_line(k, arc, 0.04, "FloorTapeWhite")
    # walkway (pedestrian) lines along the front zone
    tape_line(k, [(-5.0, -4.15), (8.9, -4.15)], 0.05, "FloorTapeGreen")
    # BSC operator zones
    for y in (2.6, 0.8):
        tape_line(k, [(7.8, y - 0.8), (8.75, y - 0.8), (8.75, y + 0.8), (7.8, y + 0.8), (7.8, y - 0.8)], 0.04,
                  "FloorTapeBlue")


# ------------------------------------------------------------------------------------------- services
def build_services(k):
    # main cable tray along the rear corridor ceiling, branches into the cell trunking and to the prep area
    z = 2.92
    def tray(a, b, w=0.30):
        a, b = np.array(a, float), np.array(b, float)
        L = np.linalg.norm(b - a)
        yaw = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        with k.at(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, z), yaw=yaw):
            k.box("Galvanized", (0, 0, 0), (L, w, 0.003))
            for s in (-1, 1):
                k.box("Galvanized", (0, s * w / 2, 0.03), (L, 0.003, 0.06))
            for i in range(int(L / 1.5) + 1):                                      # hangers
                x = -L / 2 + 0.2 + i * 1.5
                if x < L / 2:
                    for s in (-1, 1):
                        k.cyl("Galvanized", (x, s * (w / 2 + 0.01), 0.0), (x, s * (w / 2 + 0.01), H - z), 0.005, seg=8)
                    k.box("Galvanized", (x, 0, -0.01), (0.04, w + 0.06, 0.02))
            for i in range(3):                                                       # cables in the tray
                k.box(["PlasticBlack", "PlasticGrey", "PlasticBlue"][i], (0, -w / 4 + i * w / 4, 0.012),
                      (L - 0.02, 0.025, 0.02))
    tray((-5.0, 3.4), (8.5, 3.4))
    tray((0.0, 3.4), (0.0, 2.48), w=0.2)
    tray((6.0, 3.4), (6.0, -3.6), w=0.2)
    # vertical trunking from the tray down onto the enclosure's rear trunking
    k.rbox("PowderGrey", (0.0, 2.345, (2.50 + z) / 2), (0.10, 0.06, z - 2.50), r=0.004)
    # CO2 line: storage gas cabinet (east wall, y 3.6) -> up -> along the ceiling -> into the cell -> down to L10
    pipe = [(-5.46, 3.6, 2.12), (-5.46, 3.6, 2.98), (-5.0, 3.6, 2.98), (-2.30, 3.6, 2.98), (-2.30, 1.95, 2.98),
            (-2.30, 1.95, 2.40)]
    k.tube("Chrome", pipe, 0.008, seg=10)
    for p in pipe[1:-1]:
        k.sphere("Chrome", p, 0.011, seg=10)
    for y in (3.0, 2.4):                                                             # pipe clamps
        k.rbox("Galvanized", (-2.30, y, 2.995), (0.04, 0.03, 0.03), r=0.003)
    k.rbox("PlasticYellow", (-3.6, 3.6, 2.98), (0.12, 0.02, 0.025), r=0.003)         # line label band
    # utility panels on the north wall (corridor): electrical distribution, network / BMS, compressed air
    for (x, w_, label) in ((-2.4, 0.80, ["Electrical distribution", "Cell 01 + Lab 1 circuits"]),
                           (-1.1, 0.60, ["Network / BMS", "twin data, door + safety I/O"]),
                           (0.6, 0.50, ["Gas manifold", "CO2 to L10 / incubators"])):
        k.rbox("PowderGrey", (x, HALL["y1"] - 0.13, 1.55), (w_, 0.25, 1.10), r=0.006)
        k.rbox("PowderGrey", (x, HALL["y1"] - 0.258, 1.55), (w_ - 0.03, 0.006, 1.07), r=0.003)
        k.rbox("AluDark", (x + w_ / 2 - 0.08, HALL["y1"] - 0.265, 1.55), (0.02, 0.012, 0.12), r=0.003)
        png = decals.plain_sign(tex(f"panel_{label[0].split()[0].lower()}.png"), label, w=900, h=260, accent=(18, 62, 118))
        k.decal(png, (x, HALL["y1"] - 0.2615, 1.95), (0, -1, 0), (0, 0, 1), 0.30, 0.087)
        warn = decals.warning_sign(tex("warn_electric.png"), "electric", ["Electrical", "hazard"])
        k.decal(warn, (x - w_ / 2 + 0.08, HALL["y1"] - 0.2615, 1.80), (0, -1, 0), (0, 0, 1), 0.08, 0.112)
        k.cyl("Galvanized", (x, HALL["y1"] - 0.13, 2.10), (x, HALL["y1"] - 0.13, z), 0.03, seg=12)


# ------------------------------------------------------------------------------------------- signs
def build_signs(k):
    store = decals.plain_sign(tex("sign_storage.png"), ["ST01  Storage", "consumables  |  cold storage  |  gases",
                                                        "AMR dispatch S1"], w=1100, h=420, accent=(18, 62, 118))
    k.decal(store, (-5.42, -1.2 - INT_T / 2 - 0.0006, 1.65), (0, -1, 0), (0, 0, 1), 0.44, 0.168)
    lab = decals.plain_sign(tex("sign_lab1.png"), ["AICOR Lab 1", "autonomous culture laboratory",
                                                   "Cell 01  |  prep  |  storage"], w=1200, h=420, accent=(18, 62, 118))
    k.decal(lab, (HALL["x0"] + 0.0006, -2.55, 1.65), (1, 0, 0), (0, 0, 1), 0.48, 0.168)
    ex = decals.exit_sign(tex("exit.png"))
    k.rbox("PlasticWhite", (HALL["x0"] + 0.04, (ENTRANCE[0] + ENTRANCE[1]) / 2, ENTRANCE[2] + 0.22), (0.07, 0.40, 0.15),
           r=0.006)
    k.decal(ex, (HALL["x0"] + 0.0755, (ENTRANCE[0] + ENTRANCE[1]) / 2, ENTRANCE[2] + 0.22), (1, 0, 0), (0, 0, 1),
            0.36, 0.128, emissive=120.0)
    lab2 = decals.plain_sign(tex("sign_lab2.png"), ["Lab 2", "Cell 02 (planned)"], w=900, h=300, accent=(120, 120, 130))
    k.decal(lab2, (HALL["x1"] - 0.0006, -1.15, 1.65), (-1, 0, 0), (0, 0, 1), 0.36, 0.12)
    ppe = decals.mandatory_sign(tex("ppe.png"), ["Lab coat + gloves", "beyond this point"])
    k.decal(ppe, (HALL["x0"] + 0.0006, -2.05, 1.55), (1, 0, 0), (0, 0, 1), 0.20, 0.28)
    # wall clock above the operator zone (storage south wall faces the hall)
    k.cyl("PlasticWhite", (-5.40, -1.2 - INT_T / 2, 2.45), (-5.40, -1.2 - INT_T / 2 - 0.04, 2.45), 0.16, seg=40)
    face = os.path.join(TEX, "clock.png")
    _clock(face)
    k.decal(face, (-5.40, -1.2 - INT_T / 2 - 0.0405, 2.45), (0, -1, 0), (0, 0, 1), 0.28, 0.28)


def _clock(path):
    from PIL import Image, ImageDraw
    n = 512
    img = Image.new("RGB", (n, n), (246, 246, 244))
    d = ImageDraw.Draw(img)
    for i in range(60):
        a = i * math.pi / 30
        r0 = 0.40 if i % 5 else 0.36
        d.line([(n / 2 + n * r0 * math.sin(a), n / 2 - n * r0 * math.cos(a)),
                (n / 2 + n * 0.45 * math.sin(a), n / 2 - n * 0.45 * math.cos(a))], fill=(20, 20, 20),
               width=3 if i % 5 else 9)
    for a, L, w_ in ((math.radians(10 * 30 + 9), 0.24, 14), (math.radians(9 * 6), 0.36, 8)):
        d.line([(n / 2, n / 2), (n / 2 + n * L * math.sin(a), n / 2 - n * L * math.cos(a))], fill=(20, 20, 20), width=w_)
    d.ellipse([n / 2 - 12, n / 2 - 12, n / 2 + 12, n / 2 + 12], fill=(200, 30, 30))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)


# ------------------------------------------------------------------------------------------- exterior
def build_exterior(k):
    k.box("Concrete", (0, -22.0, -0.06), (80, 29.5, 0.12), faces=["+z"])
    k.box("Concrete", (0, 30.0, -0.06), (80, 51.5, 0.12), faces=["+z"])
    for x in (-25.0, 25.0):
        k.box("Concrete", (x, 0, -0.06), (30.0, 12.0, 0.12), faces=["+z"])
    # building across the courtyard: facade with window bands
    k.box("WallPaint", (0, -34.0, 7.5), (70, 1.0, 15.0))
    for z in (1.5, 5.0, 8.5, 12.0):
        k.box("PowderAnthracite", (0, -33.49, z + 0.9), (66, 0.02, 1.6))
        for x in np.arange(-32, 33, 3.0):
            k.box("AluAnodized", (x, -33.47, z + 0.9), (0.08, 0.03, 1.6))
    # low hedge / planters along the courtyard
    for x in np.arange(-18, 19, 6.0):
        k.rbox("PowderAnthracite", (x, -12.0, 0.35), (4.0, 1.0, 0.7), r=0.02)
        k.rbox("Leaf", (x, -12.0, 0.85), (3.8, 0.85, 0.35), r=0.15, seg=3)


# ------------------------------------------------------------------------------------------- storage door
def add_sliding_door(st, root):
    """Automatic sliding door (hall side of the storage south wall): fixed frame -> prismatic -> leaf."""
    x0, x1, h = STORE_DOOR
    w = x1 - x0 + 0.10
    y = STORE["y0"] - INT_T / 2 - 0.035
    base = f"{root}/Doors/ST01_Sliding"
    UsdGeom.Xform.Define(st, f"{root}/Doors")
    door = UsdGeom.Xform.Define(st, base)
    door.AddTranslateOp().Set(Gf.Vec3d((x0 + x1) / 2, y, 0.0))
    dp = door.GetPrim()
    frame = UsdGeom.Xform.Define(st, f"{base}/Frame")
    leaf = UsdGeom.Xform.Define(st, f"{base}/Leaf")
    for p, mass in ((frame.GetPrim(), 1.0), (leaf.GetPrim(), 40.0)):
        UsdPhysics.RigidBodyAPI.Apply(p)
        UsdPhysics.MassAPI.Apply(p).CreateMassAttr(mass)
    k = Kit()
    k.rbox("DoorLaminate", (0, 0, h / 2 + 0.01), (w, 0.04, h), r=0.003)
    k.box("WindowGlass", (0, 0, 1.45), (0.50, 0.045, 0.90))
    for s in (-1, 1):
        k.rbox("PowderGrey", (0, s * 0.021, 1.45), (0.54, 0.004, 0.94), r=0.002)
        k.handle_bar("StainlessSatin", (w / 2 - 0.10, s * 0.02, 1.05), 0.40, axis=(0, 0, 1), standoff=0.035, r=0.012,
                     normal=(0, s, 0))
    k.collide((0, 0, h / 2 + 0.01), (w, 0.04, h))
    k.write(st, f"{base}/Leaf")
    # track / header box (static, part of the shell visuals: drawn with the shell kit)
    dp.AddAppliedSchema("PhysxArticulationAPI")
    UsdPhysics.ArticulationRootAPI.Apply(dp)
    dp.CreateAttribute("physxArticulation:enabledSelfCollisions", Sdf.ValueTypeNames.Bool).Set(False)
    dp.CreateAttribute("physxArticulation:sleepThreshold", Sdf.ValueTypeNames.Float).Set(0.0)
    fj = UsdPhysics.FixedJoint.Define(st, f"{base}/Joints/FrameJoint")
    fj.CreateBody1Rel().SetTargets([frame.GetPath()])
    fj.CreateLocalPos0Attr(Gf.Vec3f(0))
    fj.CreateLocalPos1Attr(Gf.Vec3f(0))
    sj = UsdPhysics.PrismaticJoint.Define(st, f"{base}/Joints/Slide")
    sj.CreateBody0Rel().SetTargets([frame.GetPath()])
    sj.CreateBody1Rel().SetTargets([leaf.GetPath()])
    sj.CreateLocalPos0Attr(Gf.Vec3f(0))
    sj.CreateLocalPos1Attr(Gf.Vec3f(0))
    sj.CreateLocalRot0Attr(Gf.Quatf(1, 0, 0, 0))
    sj.CreateLocalRot1Attr(Gf.Quatf(1, 0, 0, 0))
    sj.CreateAxisAttr("X")
    sj.CreateLowerLimitAttr(-(w + 0.02))
    sj.CreateUpperLimitAttr(0.0)
    dr = UsdPhysics.DriveAPI.Apply(sj.GetPrim(), "linear")
    dr.CreateTypeAttr("force")
    dr.CreateStiffnessAttr(4000.0)
    dr.CreateDampingAttr(800.0)
    dr.CreateMaxForceAttr(300.0)
    dr.CreateTargetPositionAttr(0.0)
    for kk, t, v in (("sdt:doorId", Sdf.ValueTypeNames.String, "ST01_Sliding"),
                     ("sdt:role", Sdf.ValueTypeNames.String, "automatic sliding door of the storage room (AMR + staff)"),
                     ("sdt:doorState", Sdf.ValueTypeNames.String, "closed"),
                     ("sdt:clearWidth_m", Sdf.ValueTypeNames.Double, float(x1 - x0)),
                     ("sdt:openTravel_m", Sdf.ValueTypeNames.Double, float(w + 0.02))):
        dp.CreateAttribute(kk, t, custom=True).Set(v)


# ------------------------------------------------------------------------------------------- main
def build():
    os.makedirs(TEX, exist_ok=True)
    k = Kit()
    hx0, hx1, hy0, hy1 = HALL["x0"], HALL["x1"], HALL["y0"], HALL["y1"]
    # floor (with collider) - covers hall and storage
    k.box("EpoxyFloor", ((hx0 + hx1) / 2, (hy0 + hy1) / 2, -0.025), (hx1 - hx0, hy1 - hy0, 0.05), faces=["+z"])
    k.collide(((hx0 + hx1) / 2, (hy0 + hy1) / 2, -0.05), (hx1 - hx0, hy1 - hy0, 0.10))
    # exterior walls: south (windows), west (entrance), east (door to lab 2), north
    t = EXT_T
    win = [(x0 - hx0 + t / 2, x1 - hx0 + t / 2, SILL, HEAD) for (x0, x1) in WINDOWS]
    wall(k, (hx0 - t / 2, hy0 - t / 2), (hx1 + t / 2, hy0 - t / 2), t, win, inner_side=1)
    # west wall runs from north to south so its inner side is +... keep explicit openings in s along a->b
    wall(k, (hx0 - t / 2, hy0 - t / 2), (hx0 - t / 2, hy1 + t / 2), t,
         [(ENTRANCE[0] - hy0 + t / 2, ENTRANCE[1] - hy0 + t / 2, 0.0, ENTRANCE[2])], inner_side=-1)
    wall(k, (hx1 + t / 2, hy0 - t / 2), (hx1 + t / 2, hy1 + t / 2), t,
         [(EAST_DOOR[0] - hy0 + t / 2, EAST_DOOR[1] - hy0 + t / 2, 0.0, EAST_DOOR[2])], inner_side=1)
    wall(k, (hx0 - t / 2, hy1 + t / 2), (hx1 + t / 2, hy1 + t / 2), t, inner_side=-1)
    # storage room partitions (east wall x -5.2, south wall y -1.2 with the sliding-door opening)
    sx0, sx1, sy0, sy1 = STORE["x0"], STORE["x1"], STORE["y0"], STORE["y1"]
    wall(k, (sx0, sy0), (sx1 + INT_T / 2, sy0), INT_T, [(STORE_DOOR[0] - sx0, STORE_DOOR[1] - sx0, 0.0, STORE_DOOR[2])],
         inner_side=0)
    wall(k, (sx1, sy0 - INT_T / 2), (sx1, sy1), INT_T, inner_side=0)
    # door frames, leaves (static: entrance double door, east door), sliding-door track header
    door_frame(k, (sx0 + (STORE_DOOR[0] + STORE_DOOR[1]) / 2 - sx0, sy0, 0), 0, STORE_DOOR[1] - STORE_DOOR[0],
               STORE_DOOR[2], INT_T)
    k.rbox("AluAnodized", ((STORE_DOOR[0] + STORE_DOOR[1]) / 2 - 0.75, sy0 - INT_T / 2 - 0.05, STORE_DOOR[2] + 0.10),
           (3.0, 0.10, 0.16), r=0.006)                                               # sliding-door operator box
    k.rbox("PlasticBlack", ((STORE_DOOR[0] + STORE_DOOR[1]) / 2, sy0 - INT_T / 2 - 0.105, STORE_DOOR[2] + 0.10),
           (0.20, 0.012, 0.06), r=0.004)                                             # motion / presence sensor
    ec = (ENTRANCE[0] + ENTRANCE[1]) / 2
    door_frame(k, (hx0 - t / 2, ec, 0), 90, ENTRANCE[1] - ENTRANCE[0], ENTRANCE[2], t)
    for s in (-1, 1):
        swing_door_leaf(k, (hx0 - t / 2, ec + s * 0.4, 0), 90, 0.79, ENTRANCE[2] - 0.01, push_bar=True,
                        hinge_left=s > 0)
    k.collide((hx0 - t / 2, ec, ENTRANCE[2] / 2), (0.06, ENTRANCE[1] - ENTRANCE[0], ENTRANCE[2]))
    edc = (EAST_DOOR[0] + EAST_DOOR[1]) / 2
    door_frame(k, (hx1 + t / 2, edc, 0), 90, EAST_DOOR[1] - EAST_DOOR[0], EAST_DOOR[2], t)
    swing_door_leaf(k, (hx1 + t / 2, edc, 0), 90, EAST_DOOR[1] - EAST_DOOR[0] - 0.01, EAST_DOOR[2] - 0.01)
    k.collide((hx1 + t / 2, edc, EAST_DOOR[2] / 2), (0.06, EAST_DOOR[1] - EAST_DOOR[0], EAST_DOOR[2]))
    for (x0, x1) in WINDOWS:
        window(k, x0, x1, hy0)
    build_ceiling(k)
    build_markings(k)
    build_services(k)
    build_signs(k)
    build_exterior(k)
    for name, pos in (("store_door", ((STORE_DOOR[0] + STORE_DOOR[1]) / 2, sy0, 0.0)),
                      ("entrance", (hx0, ec, 0.0)), ("east_door", (hx1, edc, 0.0))):
        k.frame(name, pos)
    st, root = new_asset(os.path.join(USD, "site_shell.usda"), "Site",
                         "Generated by assets/site/build_site.py - edit the script, not this file.")
    n = k.write(st, root, {"sdt:siteId": "AICOR-LAB1", "sdt:canonicalName": "AICOR Lab 1 (site layout proposal S1)",
                           "sdt:role": "Building shell around Cell 01: hall, storage room ST01, entrance, windows, "
                                       "services; proposal, not part of the Cell 01 v0.3 baseline",
                           "sdt:bindingStatus": "proposal_S1", "sdt:ceilingHeight_m": float(H)})
    add_lights(st, root)
    add_sliding_door(st, root)
    route = UsdGeom.BasisCurves.Define(st, f"{root}/AmrRoute_S1_to_H2")
    route.CreateTypeAttr(UsdGeom.Tokens.linear)
    route.CreatePointsAttr([Gf.Vec3f(x, y, 0.02) for (x, y) in AMR_ROUTE])
    route.CreateCurveVertexCountsAttr([len(AMR_ROUTE)])
    route.CreateWidthsAttr([0.02] * len(AMR_ROUTE))
    route.CreatePurposeAttr(UsdGeom.Tokens.guide)
    route.GetPrim().CreateAttribute("sdt:role", Sdf.ValueTypeNames.String, custom=True).Set(
        "R03 site route: storage dispatch dock S1 -> ST01 door -> lane -> Cell 01 AMR portal -> H2 approach (world xy)")
    st.GetRootLayer().Save()
    print(f"wrote {USD}/site_shell.usda: {n} triangles, {len(light_grid())} luminaires")


if __name__ == "__main__":
    build()
