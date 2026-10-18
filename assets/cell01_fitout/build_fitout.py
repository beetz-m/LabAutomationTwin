"""Cell 01 fit-out: safety enclosure, central machine bench, rail cover, instrument supports and the L12 hood.

Implements the architectural part of the Cell 01 specification (Complete Design and Implementation Specification
v0.3, section 4 and 18) on layout P1, as project-owned designs (the item Line 8 frame, Labconco cabinets and
Schneider/Pilz controls of the CAD acquisition register are not acquired; these are proxies of those classes):

  enclosure.usda   6.0 x 4.5 x 2.5 m modular frame (45 mm aluminium profiles, floor anchors), laminated safety glass on
                   the robot-facing sides, sheet panels and the AICOR Cell 01 panel on the rear (service) side, an
                   interlocked human-access door (front), two rear service doors, the AMR portal at x 0.60..1.70 with a
                   muted light curtain (the R03 route enters there), E-stop stations front-left / front-right / rear,
                   the HMI on a swivel arm, three stack lights, two overview-camera housings, cable trunking. The doors
                   are articulations (fixed frame -> revolute hinge -> leaf) with an interlock attribute, driven closed.
  bench_f01.usda   the central automation bench as a machine base: stainless worktop on exactly the Cell 01 worktop
                   extents (the Cell 01 worktop cube stays the collider), base cabinets set back to y 0.10 so the docked
                   AMR chassis (y <= 0.01, z < 0.36) keeps clear, recessed kick plinth, levelling feet.
  rail_cover.usda  stainless plinth around R02's rail legs (visual only: nothing else ever goes there).
  support_*.usda   instrument cabinets / the isolated L17 sub-base on the P1 support envelopes (the P1 box colliders stay).
  l12_hood.usda    L12 enclosure: glazed front/sides and a partial roof; the robot side (+Y, toward R02's rail) and the
                   roof over the plate nest stay open for R02 (light-curtain guarded). Sized from R02's recorded swept
                   volume (tools/fitout_clearance.py).

Run: env_cad/bin/python assets/cell01_fitout/build_fitout.py   (after tools/layout_p1.py)
"""

import json
import math
import os
import sys

import numpy as np
from pxr import Gf, Sdf, UsdGeom, UsdPhysics

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
from assets.common import decals  # noqa: E402
from assets.common.meshkit import Kit, new_asset  # noqa: E402

USD = os.path.join(HERE, "usd")
TEX = os.path.join(HERE, "textures")
LAYOUT = os.path.join(ROOT, "scenes", "layout_p1.json")
PROXY = "project-owned proxy (item Line 8-class frame / Labconco-class cabinets / Harmony XB4- and PITestop-class " \
        "controls); manufacturer CAD not acquired"

# enclosure geometry (cell frame, metres): profile centre lines just outside the 6.0 x 4.5 m interior
XW, YW = 3.025, 2.275
P = 0.045                      # profile size
Z_BOT, Z_TOP = 0.10, 2.4775    # rail centre heights; top of the frame = 2.50
FRONT_POSTS = [-XW, -2.10, -1.12, -0.08, 0.58, 1.72, 2.40, XW]
REAR_POSTS = [-XW, -2.62, -1.58, -0.50, 0.55, 1.08, 2.12, XW]
SIDE_POSTS = [-YW, -1.10, 0.0, 1.10, YW]
DOORS = {  # name: wall, hinge x, latch x, opens to (+1 outward = away from the cell), role
    "D1_Front": dict(wall="front", x0=-1.12, x1=-0.08, role="human access door (interlocked)"),
    "D2_RearWest": dict(wall="rear", x0=-2.62, x1=-1.58, role="rear service door (L09/L10/H4 side)"),
    "D3_RearEast": dict(wall="rear", x0=1.08, x1=2.12, role="rear service door (L17/L21 side)"),
}
PORTAL = (0.58, 1.72, 1.40)    # AMR portal between these posts, glazed header above z 1.40
BRAND_SPAN = (-0.50, 1.08)     # rear wall section carrying the AICOR Cell 01 panel (between posts)


def tex(name):
    return os.path.join(TEX, name)


# ------------------------------------------------------------------------------------------- small parts
def anchor_plate(k, x, y):
    k.rbox("StainlessSatin", (x, y, 0.005), (0.12, 0.12, 0.010), r=0.003)
    for dx in (-0.04, 0.04):
        for dy in (-0.04, 0.04):
            k.cyl("Chrome", (x + dx, y + dy, 0.010), (x + dx, y + dy, 0.016), 0.007, seg=6)


def post(k, x, y, top=2.50):
    k.profile_item((x, y, 0.010), (x, y, top - 0.006), P)
    k.rbox("PlasticBlack", (x, y, top - 0.003), (P, P, 0.006), r=0.002)
    anchor_plate(k, x, y)


def rail(k, a, b, z):
    a, b = np.array([a[0], a[1], z]), np.array([b[0], b[1], z])
    d = (b - a) / np.linalg.norm(b - a)
    k.profile_item(a + d * P / 2, b - d * P / 2, P, up=(0, 0, 1))


def panel(k, a, b, z0, z1, mat="SafetyGlass", t=0.008):
    """Infill panel between two posts (glass or sheet), in the wall plane."""
    a, b = np.array(a, float), np.array(b, float)
    d = (b - a) / np.linalg.norm(b - a)
    lo, hi = a + d * (P / 2 - 0.006), b - d * (P / 2 - 0.006)
    c = (lo + hi) / 2
    L = np.linalg.norm(hi - lo)
    yaw = math.degrees(math.atan2(d[1], d[0]))
    with k.at((c[0], c[1], 0), yaw=yaw):
        k.box(mat, (0, 0, (z0 + z1) / 2), (L, t, z1 - z0))


def wall_collider(k, a, b, z0=0.0, z1=2.5, t=0.05):
    a, b = np.array(a, float), np.array(b, float)
    c = (a + b) / 2
    L = np.linalg.norm(b - a)
    yaw = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    k.collide((c[0], c[1], (z0 + z1) / 2), (L, t, z1 - z0), yaw=yaw)


def estop_box(k, pos, normal_yaw, label_png=None):
    """Yellow E-stop housing with a red mushroom button; front faces the yaw direction (+X local -> world yaw)."""
    with k.at(pos, yaw=normal_yaw):
        k.rbox("PlasticYellow", (0.035, 0, 0), (0.07, 0.075, 0.095), r=0.006, seg=2)
        k.cyl("PlasticYellow", (0.07, 0, 0), (0.078, 0, 0), 0.026, seg=24)
        k.lathe("PlasticRed", [(0.0, 0.0), (0.012, 0.0), (0.012, 0.010), (0.020, 0.012), (0.021, 0.018),
                               (0.015, 0.024), (0.0, 0.026)], base=(0.078, 0, 0), axis=(1, 0, 0), seg=28)
        if label_png:
            k.decal(label_png, (0.0705, 0, -0.038), (1, 0, 0), (0, 0, 1), 0.06, 0.016)


def stack_light(k, x, y, z, lit="green"):
    k.cyl("AluAnodized", (x, y, z), (x, y, z + 0.10), 0.010, seg=12)
    k.cyl("PlasticBlack", (x, y, z + 0.10), (x, y, z + 0.13), 0.028, seg=24, r_edge=0.004)
    zz = z + 0.13
    for col in ("green", "amber", "red"):
        mat = {"green": "StackGreen", "amber": "StackAmber", "red": "StackRed"}[col]
        if col != lit:
            mat = {"green": "PlasticGreen", "amber": "PlasticOrange", "red": "PlasticRed"}[col]
        k.cyl(mat, (x, y, zz + 0.002), (x, y, zz + 0.058), 0.026, seg=24)
        k.cyl("PlasticGrey", (x, y, zz + 0.058), (x, y, zz + 0.062), 0.027, seg=24)
        zz += 0.062
    k.cyl("PlasticBlack", (x, y, zz), (x, y, zz + 0.012), 0.027, seg=24, r_edge=0.004)


def camera_housing(k, pos, yaw, pitch=-35):
    with k.at(pos, yaw=yaw):
        k.rbox("PowderWhite", (0, 0, -0.02), (0.05, 0.05, 0.04), r=0.006)
        k.cyl("AluAnodized", (0, 0, -0.04), (0, 0, -0.06), 0.008, seg=12)
        R = np.array([[math.cos(math.radians(pitch)), 0, -math.sin(math.radians(pitch))], [0, 1, 0],
                      [math.sin(math.radians(pitch)), 0, math.cos(math.radians(pitch))]])
        with k.at((0, 0, -0.085), R=R):
            k.rbox("PowderWhite", (0.04, 0, 0), (0.13, 0.065, 0.06), r=0.012, seg=2)
            k.cyl("PlasticBlack", (0.105, 0, 0), (0.112, 0, 0), 0.024, seg=24)
            k.disk("ScreenOff", (0.1125, 0, 0), 0.016, normal=(1, 0, 0), seg=24)


def door_leaf(k, w, h, z0=0.125, frame=0.03, handle_side=1.0, outward=-1.0, sign_png=None):
    """Glazed door leaf in local frame: hinge edge at x=0, leaf along +x, wall plane y=0."""
    k.profile_item((0.005 + frame / 2, 0, z0), (0.005 + frame / 2, 0, z0 + h), frame)
    k.profile_item((w - 0.005 - frame / 2, 0, z0), (w - 0.005 - frame / 2, 0, z0 + h), frame)
    for z in (z0 + frame / 2, z0 + h - frame / 2, z0 + 0.95):
        k.profile_item((0.005 + frame, 0, z), (w - 0.005 - frame, 0, z), frame, up=(0, 0, 1))
    k.box("SafetyGlass", (w / 2, 0, z0 + (0.95 + h) / 2), (w - 2 * frame - 0.01, 0.008, h - 0.95 - frame))
    k.box("PowderGrey", (w / 2, 0, z0 + 0.95 / 2), (w - 2 * frame - 0.01, 0.003, 0.95 - frame))
    # lever handle + safety interlock actuator on the latch side, both faces
    for side in (-1, 1):
        hx = w - 0.07
        k.rbox("StainlessSatin", (hx, side * 0.020, 1.05), (0.03, 0.012, 0.16), r=0.004)
        k.cyl("StainlessSatin", (hx, side * 0.026, 1.08), (hx, side * 0.075, 1.08), 0.010, seg=16)
        k.cyl("StainlessSatin", (hx, side * 0.075, 1.08), (hx - 0.13, side * 0.075, 1.08), 0.010, seg=16)
    k.rbox("PlasticRed", (w - 0.012, outward * 0.03, 1.35), (0.02, 0.025, 0.06), r=0.003)
    if sign_png:
        k.decal(sign_png, (w / 2, outward * 0.0055, 1.55), (0, outward, 0), (0, 0, 1), 0.20, 0.28)


# ------------------------------------------------------------------------------------------- enclosure
def build_enclosure():
    os.makedirs(TEX, exist_ok=True)
    k = Kit()
    walls = {
        "front": [(x, -YW) for x in FRONT_POSTS],
        "rear": [(x, YW) for x in REAR_POSTS],
        "west": [(-XW, y) for y in SIDE_POSTS],
        "east": [(XW, y) for y in SIDE_POSTS],
    }
    posts = {tuple(np.round(p, 4)) for pts in walls.values() for p in pts}
    for (x, y) in posts:
        post(k, x, y)
    door_spans = {(DOORS[d]["wall"], DOORS[d]["x0"]) for d in DOORS}
    for name, pts in walls.items():
        for a, b in zip(pts[:-1], pts[1:]):
            is_door = name in ("front", "rear") and (name, a[0]) in door_spans
            is_portal = name == "front" and abs(a[0] - PORTAL[0]) < 1e-6
            rail(k, a, b, Z_TOP)
            if is_door:
                rail(k, a, b, 2.20)                                         # door header
                panel(k, a, b, 2.22, 2.455)
                continue
            if is_portal:
                rail(k, a, b, PORTAL[2])
                panel(k, a, b, PORTAL[2] + 0.022, 2.455)
                wall_collider(k, a, b, PORTAL[2], 2.5)
                continue
            rail(k, a, b, Z_BOT)
            if name == "rear":
                rail(k, a, b, 1.00)
                brand = abs(a[0] - BRAND_SPAN[0]) < 1e-6 or abs(a[0] - 0.55) < 1e-6
                panel(k, a, b, 0.122, 0.978, "PowderGrey", t=0.003)
                panel(k, a, b, 1.022, 2.455, "PowderWhite" if brand else "SafetyGlass", t=0.004 if brand else 0.008)
            else:
                panel(k, a, b, 0.122, 2.455)
            wall_collider(k, a, b)
    # rear brand panel graphic, facing into the cell (and through the front glass toward the hall)
    png = decals.brand_panel(tex("brand_panel.png"))
    k.decal(png, (0.29, YW - 0.004, 1.74), (0, -1, 0), (0, 0, 1), 1.40, 0.583)
    # door headers' colliders above the doors
    for d in DOORS.values():
        y = -YW if d["wall"] == "front" else YW
        wall_collider(k, (d["x0"], y), (d["x1"], y), 2.20, 2.5)

    # E-stops: front-left (post -2.10), front-right (HMI pedestal at post 2.40), rear service (post -0.50)
    es_png = decals.plain_sign(tex("estop_label.png"), ["EMERGENCY STOP"], w=600, h=160, bg=(250, 205, 0),
                               fg=(20, 20, 20), sizes=[90])
    estop_box(k, (-2.10, -YW - P / 2 - 0.001, 1.10), -90, es_png)
    estop_box(k, (-0.50, YW + P / 2 + 0.001, 1.10), 90, es_png)
    # HMI on a swivel arm from the front-right post (outside, toward the operator)
    hx, hy = 2.40, -YW - P / 2
    k.cyl("AluAnodized", (hx, hy - 0.02, 1.62), (hx, hy - 0.30, 1.62), 0.018, seg=16)
    k.cyl("AluAnodized", (hx, hy - 0.30, 1.50), (hx, hy - 0.30, 1.66), 0.022, seg=16)
    with k.at((hx, hy - 0.33, 1.45), R=np.array([[1, 0, 0], [0, math.cos(0.17), -math.sin(0.17)],
                                                  [0, math.sin(0.17), math.cos(0.17)]])):
        k.rbox("PlasticGrey", (0, 0, 0), (0.42, 0.06, 0.32), r=0.012, seg=2)
        k.rbox("PlasticBlack", (0, -0.0305, 0.0), (0.36, 0.002, 0.25), r=0.004)
        stations = [("L09", "Plate hotel", "READY", True), ("L10", "CO2 incubator", "READY", True),
                    ("L12", "Liquid handler", "READY", True), ("L17", "Imager", "READY", True),
                    ("L21", "QC / calibration", "VALID", True), ("H4", "Quarantine", "1 plate held", False),
                    ("R01", "Plate arm", "IDLE", True), ("R02", "Rail arm  T01", "IDLE", True),
                    ("R03", "Sample AMR", "DOCKED  H2", True), ("TCM01", "Tool magazine", "4/5 tools", True),
                    ("HN", "Handover nest", "empty", True), ("SDT", "Culture SDT", "in sync", True)]
        hmi = decals.screen_hmi(tex("hmi_cell01.png"), stations)
        k.decal(hmi, (0, -0.032, 0.0), (0, -1, 0), (0, 0, 1), 0.34, 0.2125, emissive=350.0)
    # control box under the HMI: E-stop, start, stop, reset, key switch
    with k.at((hx, hy - 0.06, 1.12)):
        k.rbox("PowderGrey", (0, -0.03, 0), (0.22, 0.06, 0.16), r=0.008)
        estop_box(k, (0.0, -0.06, 0.02), -90)
        for i, (mat, dx) in enumerate((("PlasticGreen", -0.07), ("PlasticRed", 0.07), ("PlasticBlue", 0.045))):
            k.cyl(mat, (dx, -0.06, -0.045), (dx, -0.068, -0.045), 0.011, seg=20)
        k.cyl("Chrome", (-0.045, -0.06, -0.045), (-0.045, -0.068, -0.045), 0.010, seg=20)
        k.decal(es_png, (0.0, -0.0605, 0.065), (0, -1, 0), (0, 0, 1), 0.09, 0.024)
    # stack lights on the top rail corners
    stack_light(k, -XW, -YW, 2.50)
    stack_light(k, XW, -YW, 2.50)
    stack_light(k, -XW, YW, 2.50)
    # overview camera housings (top corners, looking into the cell)
    camera_housing(k, (-XW + 0.06, -YW + 0.06, 2.50), 38)
    camera_housing(k, (XW - 0.06, YW - 0.06, 2.50), 218)
    # cable trunking along the rear top rail + vertical drop at the rear centre
    k.rbox("PowderGrey", (0.0, YW, 2.50 + 0.03), (6.0, 0.10, 0.06), r=0.004)
    k.rbox("PowderGrey", (0.0, YW + 0.07, 2.20), (0.10, 0.06, 0.60), r=0.004)
    # AMR portal: light-curtain columns (emitter/receiver facing each other), muting arms + lamp, floor sill
    for x, face in ((PORTAL[0] + 0.045, 1.0), (PORTAL[1] - 0.045, -1.0)):
        k.rbox("PlasticYellow", (x, -YW, 0.75), (0.035, 0.045, 1.20), r=0.004)
        k.box("PlasticBlack", (x + face * 0.0181, -YW, 0.75), (0.0015, 0.03, 1.12))
        k.rbox("PlasticBlack", (x, -YW, 0.12), (0.06, 0.08, 0.04), r=0.004)
        for dy in (-0.22, 0.22):    # muting sensors in front of / behind the curtain
            k.cyl("AluAnodized", (x, -YW, 0.30), (x, -YW + dy, 0.30), 0.008, seg=10)
            k.rbox("PlasticBlack", (x + face * 0.01, -YW + dy, 0.30), (0.03, 0.025, 0.035), r=0.004)
        k.cyl("PlasticWhite", (x, -YW, 1.35), (x, -YW, 1.40), 0.018, seg=20)
    k.box("FloorTapeHatch", (sum(PORTAL[:2]) / 2, -YW, 0.0008), (PORTAL[1] - PORTAL[0] - P, 0.10, 0.0016))
    # signs
    warn = decals.warning_sign(tex("warn_robot.png"), "robot", ["Robot cell", "automatic operation", "authorised staff only"])
    portal_png = decals.plain_sign(tex("portal_sign.png"), ["AMR portal", "muted light curtain - keep clear"],
                                   w=1000, h=300, accent=(240, 180, 0))
    k.decal(portal_png, (sum(PORTAL[:2]) / 2, -YW - 0.0065, 1.90), (0, -1, 0), (0, 0, 1), 0.60, 0.18)
    cell_png = decals.station_plate(tex("cell01_plate.png"), "Cell 01", "Culture handling & liquid intervention",
                                    sub="AICOR Lab  |  enclosure E01  |  door D1 interlocked")
    k.decal(cell_png, (-1.60, -YW - 0.0065, 1.55), (0, -1, 0), (0, 0, 1), 0.60, 0.21)
    k.decal(warn, (-2.55, -YW - 0.0065, 1.45), (0, -1, 0), (0, 0, 1), 0.24, 0.336)
    k.decal(warn, (2.95 - 0.40, YW + 0.0065, 1.45), (0, 1, 0), (0, 0, 1), 0.24, 0.336)
    svc = decals.plain_sign(tex("service_sign.png"), ["Service access", "rear maintenance corridor"], w=1000, h=300,
                            accent=(18, 62, 118))
    for d in ("D2_RearWest", "D3_RearEast"):
        x = (DOORS[d]["x0"] + DOORS[d]["x1"]) / 2
        k.decal(svc, (x, YW + 0.0065, 2.32), (0, 1, 0), (0, 0, 1), 0.40, 0.12)

    st, root = new_asset(os.path.join(USD, "enclosure.usda"), "Enclosure",
                         "Generated by assets/cell01_fitout/build_fitout.py - edit the script, not this file.")
    sem = {"sdt:componentId": "E01", "sdt:canonicalName": "Cell 01 safety enclosure",
           "sdt:role": "Bounds the robot work envelope; glazed robot-facing sides, interlocked access, E-stops, stack lights",
           "sdt:designBasis": PROXY, "sdt:bindingStatus": "static_v1 + articulated doors",
           "sdt:interiorEnvelope_m": "6.0 x 4.5 x 2.5 (Cell 01 v0.3 authoritative)",
           "sdt:amrPortal": "x 0.60..1.70 on the front wall (y -2.25), light curtain with muting",
           "sdt:emergencyStops": ["front-left post x -2.10", "front-right HMI pedestal x 2.40", "rear post x -0.50"]}
    n = k.write(st, root, sem)
    for name, d in DOORS.items():
        n += add_door(st, root, name, d)
    for fname, pos in (("estop_front_left", (-2.10, -YW - 0.10, 1.10)), ("estop_front_right", (2.40, -YW - 0.15, 1.10)),
                       ("estop_rear", (-0.50, YW + 0.10, 1.10)), ("hmi", (2.40, -YW - 0.36, 1.45)),
                       ("amr_portal", ((PORTAL[0] + PORTAL[1]) / 2, -YW, 0.0))):
        f = UsdGeom.Xform.Define(st, f"{root}/{fname}")
        f.AddTranslateOp().Set(Gf.Vec3d(*pos))
    st.GetRootLayer().Save()
    return n


def add_door(st, root, name, d):
    """Articulated door: Frame (fixed to world) -> Hinge (revolute, driven closed) -> Leaf (rigid, collider)."""
    y = -YW if d["wall"] == "front" else YW
    outward = -1.0 if d["wall"] == "front" else 1.0
    w = d["x1"] - d["x0"] - P - 0.010
    hx = d["x0"] + P / 2 + 0.005
    base = f"{root}/Doors/{name}"
    UsdGeom.Xform.Define(st, f"{root}/Doors")
    door = UsdGeom.Xform.Define(st, base)
    door.AddTranslateOp().Set(Gf.Vec3d(hx, y, 0.0))
    dp = door.GetPrim()
    frame = UsdGeom.Xform.Define(st, f"{base}/Frame")
    leaf = UsdGeom.Xform.Define(st, f"{base}/Leaf")
    for p, mass in ((frame.GetPrim(), 1.0), (leaf.GetPrim(), 22.0)):
        UsdPhysics.RigidBodyAPI.Apply(p)
        m = UsdPhysics.MassAPI.Apply(p)
        m.CreateMassAttr(mass)
    k = Kit()
    sign = decals.warning_sign(tex("warn_robot.png"), "robot", ["Robot cell", "automatic operation", "authorised staff only"]) \
        if d["wall"] == "front" else None
    door_leaf(k, w, 2.05, outward=outward, sign_png=sign)
    k.collide((w / 2, 0, 0.125 + 1.025), (w - 0.01, 0.03, 2.04))
    n = k.write(st, f"{base}/Leaf")
    dp.AddAppliedSchema("PhysxArticulationAPI")
    UsdPhysics.ArticulationRootAPI.Apply(dp)
    dp.CreateAttribute("physxArticulation:enabledSelfCollisions", Sdf.ValueTypeNames.Bool).Set(False)
    dp.CreateAttribute("physxArticulation:sleepThreshold", Sdf.ValueTypeNames.Float).Set(0.0)
    fj = UsdPhysics.FixedJoint.Define(st, f"{base}/Joints/FrameJoint")
    fj.CreateBody1Rel().SetTargets([frame.GetPath()])
    fj.CreateLocalPos0Attr(Gf.Vec3f(0))
    fj.CreateLocalPos1Attr(Gf.Vec3f(0))
    hj = UsdPhysics.RevoluteJoint.Define(st, f"{base}/Joints/Hinge")
    hj.CreateBody0Rel().SetTargets([frame.GetPath()])
    hj.CreateBody1Rel().SetTargets([leaf.GetPath()])
    hj.CreateLocalPos0Attr(Gf.Vec3f(0))
    hj.CreateLocalPos1Attr(Gf.Vec3f(0))
    hj.CreateLocalRot0Attr(Gf.Quatf(1, 0, 0, 0))
    hj.CreateLocalRot1Attr(Gf.Quatf(1, 0, 0, 0))
    hj.CreateAxisAttr("Z")
    # outward opening: front door swings toward -Y (negative angle), rear doors toward +Y (positive)
    lo, hi = (-100.0, 0.0) if outward < 0 else (0.0, 100.0)
    hj.CreateLowerLimitAttr(lo)
    hj.CreateUpperLimitAttr(hi)
    dr = UsdPhysics.DriveAPI.Apply(hj.GetPrim(), "angular")
    dr.CreateTypeAttr("force")
    dr.CreateStiffnessAttr(200.0)
    dr.CreateDampingAttr(60.0)
    dr.CreateMaxForceAttr(400.0)
    dr.CreateTargetPositionAttr(0.0)
    for kk, t, v in (("sdt:doorId", Sdf.ValueTypeNames.String, name), ("sdt:role", Sdf.ValueTypeNames.String, d["role"]),
                     ("sdt:interlock", Sdf.ValueTypeNames.String, "safety switch with tongue actuator; robots run only "
                      "while every door reads closed (twin/site_doors.py)"),
                     ("sdt:openingDirection", Sdf.ValueTypeNames.String, "outward, away from the robot cell"),
                     ("sdt:doorState", Sdf.ValueTypeNames.String, "closed_locked")):
        dp.CreateAttribute(kk, t, custom=True).Set(v)
    return n


# ------------------------------------------------------------------------------------------- bench
BENCH = dict(x0=-1.225, x1=1.425, y0=-0.075, y1=0.675, top=0.92)
BASE_Y0 = 0.10       # base cabinet front: the docked AMR chassis reaches y 0.01 below 0.36 m


def cabinet_front(k, x0, x1, z0, z1, y, kind, handle="Chrome"):
    """One base-cabinet module front (doors / drawers / vented panel) at face plane y (facing -Y)."""
    g = 0.003
    w = x1 - x0
    if kind == "doors":
        for (a, b, hx) in ((x0, x0 + w / 2, x0 + w / 2 - 0.05), (x0 + w / 2, x1, x0 + w / 2 + 0.05)):
            k.rbox("StainlessBrushed", ((a + b) / 2, y - 0.009, (z0 + z1) / 2), (b - a - 2 * g, 0.018, z1 - z0 - 2 * g),
                   r=0.002)
            k.handle_bar(handle, (hx, y - 0.018, z1 - 0.16), 0.16, axis=(0, 0, 1), standoff=0.028, r=0.0055)
    elif kind == "drawers":
        hs = [0.14, 0.17, 0.20, (z1 - z0) - 0.51]
        z = z1
        for h in hs:
            k.rbox("StainlessBrushed", ((x0 + x1) / 2, y - 0.009, z - h / 2), (w - 2 * g, 0.018, h - 2 * g), r=0.002)
            k.handle_bar(handle, ((x0 + x1) / 2, y - 0.018, z - 0.045), 0.20, axis=(1, 0, 0), standoff=0.026, r=0.0055)
            z -= h
    elif kind == "vented":
        k.rbox("StainlessBrushed", ((x0 + x1) / 2, y - 0.009, (z0 + z1) / 2), (w - 2 * g, 0.018, z1 - z0 - 2 * g),
               r=0.002)
        for i in range(14):
            zz = z0 + 0.10 + i * 0.025
            k.box("PlasticBlack", ((x0 + x1) / 2, y - 0.0185, zz), (w - 0.16, 0.002, 0.008))
        k.rbox("PlasticGrey", ((x0 + x1) / 2, y - 0.020, z1 - 0.12), (0.22, 0.006, 0.09), r=0.004)
        for i, mat in enumerate(("IndicatorGreen", "IndicatorGreen", "StackAmber")):
            k.cyl(mat, ((x0 + x1) / 2 - 0.07 + i * 0.03, y - 0.023, z1 - 0.10),
                  ((x0 + x1) / 2 - 0.07 + i * 0.03, y - 0.027, z1 - 0.10), 0.005, seg=12)
        png = decals.plain_sign(tex("bench_io.png"), ["F01  I/O + power", "robot / station supplies"], w=800, h=240,
                                accent=(18, 62, 118))
        k.decal(png, ((x0 + x1) / 2 + 0.04, y - 0.0235, z1 - 0.135), (0, -1, 0), (0, 0, 1), 0.11, 0.033)
        # key-locked door handle
        k.cyl("Chrome", (x1 - 0.05, y - 0.018, z1 - 0.2), (x1 - 0.05, y - 0.030, z1 - 0.2), 0.012, seg=16)


def build_bench():
    k = Kit()
    b = BENCH
    zt0 = b["top"] - 0.04
    k.rbox("StainlessWorktop", ((b["x0"] + b["x1"]) / 2, (b["y0"] + b["y1"]) / 2, zt0 + 0.02),
           (b["x1"] - b["x0"], b["y1"] - b["y0"], 0.04), r=0.003, seg=2)
    k.rbox("StainlessWorktop", ((b["x0"] + b["x1"]) / 2, b["y0"] + 0.005, zt0 - 0.010),
           (b["x1"] - b["x0"], 0.010, 0.02), r=0.002)                               # turned-down front edge
    # carcass
    x0, x1, y0, y1 = b["x0"] + 0.025, b["x1"] - 0.025, BASE_Y0, b["y1"] - 0.015
    zc0, zc1 = 0.10, zt0 - 0.02
    k.rbox("StainlessBrushed", ((x0 + x1) / 2, (y0 + y1) / 2 + 0.01, (zc0 + zc1) / 2),
           (x1 - x0, y1 - y0 - 0.02, zc1 - zc0), r=0.002)
    for x in (x0, x1):                                                               # end panels
        k.rbox("StainlessBrushed", (x, (y0 + y1) / 2, (0.0 + zc1) / 2 + 0.005), (0.02, y1 - y0, zc1 - 0.01), r=0.003)
    k.rbox("PowderAnthracite", ((x0 + x1) / 2, (y0 + y1) / 2 + 0.03, 0.05), (x1 - x0 - 0.04, y1 - y0 - 0.06, 0.10),
           r=0.002)                                                                  # recessed kick plinth
    for x in np.linspace(x0 + 0.06, x1 - 0.06, 5):                                   # levelling feet (visible)
        for y in (y0 + 0.06, y1 - 0.05):
            k.cyl("Chrome", (x, y, 0.012), (x, y, 0.10), 0.010, seg=12)
            k.cyl("RubberBlack", (x, y, 0.0), (x, y, 0.012), 0.025, seg=20, r_edge=0.003)
    mods = ["doors", "drawers", "vented", "doors"]
    xs = np.linspace(x0 + 0.01, x1 - 0.01, len(mods) + 1)
    for kind, a, c in zip(mods, xs[:-1], xs[1:]):
        cabinet_front(k, a, c, zc0 + 0.005, zc1, y0, kind)
    png = decals.station_plate(tex("f01_plate.png"), "F01", "Central automation bench", sub="AICOR Cell 01  |  machine base")
    k.decal(png, (b["x0"] + 0.40, b["y0"] - 0.0006, 0.885), (0, -1, 0), (0, 0, 1), 0.143, 0.05)
    r01 = decals.station_plate(tex("r01_plate.png"), "R01", "Fixed precision plate arm", sub="AICOR Cell 01  |  FR3 + plate gripper")
    k.decal(r01, (b["x0"] + 0.025 - 0.0106, 0.38, 0.70), (-1, 0, 0), (0, 0, 1), 0.24, 0.084)
    st, root = new_asset(os.path.join(USD, "bench_f01.usda"), "Bench",
                         "Generated by assets/cell01_fitout/build_fitout.py - edit the script, not this file.")
    n = k.write(st, root, {"sdt:componentId": "F01", "sdt:canonicalName": "Central automation bench (machine base)",
                           "sdt:role": "Carries the stations on its worktop (0.92 m); the Cell 01 worktop cube is its collider",
                           "sdt:designBasis": PROXY, "sdt:bindingStatus": "visual_v1"})
    st.GetRootLayer().Save()
    return n


def build_rail_cover():
    k = Kit()
    x0, x1, y0, y1, h = -1.12, 2.02, 0.70, 0.86, 0.860
    k.rbox("StainlessBrushed", ((x0 + x1) / 2, (y0 + y1) / 2, h / 2 + 0.05), (x1 - x0, y1 - y0, h - 0.10), r=0.004)
    k.rbox("PowderAnthracite", ((x0 + x1) / 2, (y0 + y1) / 2, 0.05), (x1 - x0 - 0.04, y1 - y0 - 0.04, 0.10), r=0.002)
    # access panels with screws on the south face
    for i in range(4):
        a = x0 + 0.05 + i * (x1 - x0 - 0.10) / 4
        c = a + (x1 - x0 - 0.10) / 4 - 0.02
        k.rbox("StainlessBrushed", ((a + c) / 2, y0 - 0.002, 0.48), (c - a, 0.004, 0.62), r=0.002)
        for xx in (a + 0.02, c - 0.02):
            for zz in (0.19, 0.77):
                k.cyl("Chrome", (xx, y0 - 0.004, zz), (xx, y0 - 0.007, zz), 0.0045, seg=10)
    k.rbox("StainlessWorktop", ((x0 + x1) / 2, 0.6875, 0.885), (x1 - x0 - 0.20, 0.025, 0.012), r=0.002)  # gap strip
    png = decals.station_plate(tex("r02_plate.png"), "R02", "Rail-mounted flexible arm", sub="AICOR Cell 01  |  2.6 m linear axis")
    k.decal(png, (-0.40, y0 - 0.0046, 0.70), (0, -1, 0), (0, 0, 1), 0.24, 0.084)
    pinch = decals.warning_sign(tex("warn_pinch.png"), "general", ["Moving axis", "pinch hazard"])
    k.decal(pinch, (0.30, y0 - 0.0046, 0.70), (0, -1, 0), (0, 0, 1), 0.08, 0.112)
    st, root = new_asset(os.path.join(USD, "rail_cover.usda"), "RailCover",
                         "Generated by assets/cell01_fitout/build_fitout.py - edit the script, not this file.")
    n = k.write(st, root, {"sdt:componentId": "R02-RC", "sdt:canonicalName": "R02 rail plinth cover",
                           "sdt:role": "Encloses the rail legs and cable routing (visual; R02's rail asset keeps its colliders)",
                           "sdt:designBasis": PROXY, "sdt:bindingStatus": "visual_v1"})
    st.GetRootLayer().Save()
    return n


# ------------------------------------------------------------------------------------------- supports
SUPPORT_NAMES = {"L09": ("L09", "Plate hotel"), "L10": ("L10", "CO2 incubator"), "H4": ("H4", "Quarantine"),
                 "L17": ("L17", "Bright-field imager"), "L21": ("L21", "QC / calibration")}


def build_support(name, kind, W, D, H, yaw):
    """Support cabinet in its own frame (centre of the footprint on the floor, local -Y = robot side)."""
    k = Kit()
    code, title = SUPPORT_NAMES[name]
    if name == "L17":       # isolated sub-base: steel frame, isolation mounts, granite-type slab
        slab = 0.06
        for sx in (-1, 1):
            for sy in (-1, 1):
                x, y = sx * (W / 2 - 0.05), sy * (D / 2 - 0.05)
                k.rbox("PowderAnthracite", (x, y, (H - slab - 0.04) / 2), (0.06, 0.06, H - slab - 0.04), r=0.004)
                k.cyl("RubberBlack", (x, y, H - slab - 0.04), (x, y, H - slab), 0.035, seg=20)
                k.cyl("Chrome", (x, y, 0.0), (x, y, 0.03), 0.02, seg=16)
        for z in (0.15, H - slab - 0.07):
            for sy in (-1, 1):
                k.rbox("PowderAnthracite", (0, sy * (D / 2 - 0.05), z), (W - 0.10, 0.05, 0.05), r=0.004)
            for sx in (-1, 1):
                k.rbox("PowderAnthracite", (sx * (W / 2 - 0.05), 0, z), (0.05, D - 0.10, 0.05), r=0.004)
        k.rbox("PhenolicDark", (0, 0, H - slab / 2), (W, D, slab), r=0.006, seg=2)
        tag_z = 0.45
    else:                   # stainless cabinet with recessed plinth, door(s), worktop lip
        k.rbox("StainlessWorktop", (0, 0, H - 0.015), (W, D, 0.03), r=0.003)
        k.rbox("StainlessBrushed", (0, 0, (H - 0.03 + 0.10) / 2), (W - 0.04, D - 0.04, H - 0.03 - 0.10), r=0.003)
        k.rbox("PowderAnthracite", (0, 0, 0.05), (W - 0.10, D - 0.10, 0.10), r=0.002)
        # door fronts on every side that is not against something: all four (rotated cabinets are seen from all sides)
        for face_yaw in (0, 90, 180, 270):
            with k.at((0, 0, 0), yaw=face_yaw):
                L = W if face_yaw in (0, 180) else D
                Dd = D if face_yaw in (0, 180) else W
                kind_f = "doors" if L > 0.5 else "single"
                y = -Dd / 2 + 0.02 - 0.0
                if kind_f == "doors":
                    cabinet_front(k, -L / 2 + 0.03, L / 2 - 0.03, 0.105, H - 0.035, y + 0.0, "doors")
                else:
                    k.rbox("StainlessBrushed", (0, y - 0.009, (0.105 + H - 0.035) / 2), (L - 0.06, 0.018, H - 0.146),
                           r=0.002)
                    k.handle_bar("Chrome", (L / 2 - 0.08, y - 0.018, H - 0.18), 0.14, standoff=0.026, r=0.0055)
        tag_z = H - 0.09
    k.collide((0, 0, H / 2), (W, D, H))   # informational: the composer keeps the P1 box as the live collider
    # station plate on the face that points most toward the front of the cell (world -Y)
    best = max((0, 90, 180, 270), key=lambda f: math.cos(math.radians(yaw + f)))   # face toward world -Y
    png = decals.station_plate(tex(f"{code.lower()}_plate.png"), code, title)
    with k.at((0, 0, 0), yaw=best):
        Dd = D if best in (0, 180) else W
        if name == "L17":
            k.decal(png, (0, -Dd / 2 - 0.0006, H - 0.03), (0, -1, 0), (0, 0, 1), 0.14, 0.049)
        else:   # below the handles, on the left leaf
            L = W if best in (0, 180) else D
            k.decal(png, (-L / 4 if L > 0.5 else 0.0, -Dd / 2 + 0.0014, 0.30), (0, -1, 0), (0, 0, 1), 0.17, 0.06)
    st, root = new_asset(os.path.join(USD, f"support_{name}.usda"), "Support",
                         "Generated by assets/cell01_fitout/build_fitout.py - edit the script, not this file.")
    n = k.write(st, root, {"sdt:componentId": f"{code}-SUP", "sdt:canonicalName": f"{code} {kind.replace('_', ' ')}",
                           "sdt:role": ("vibration-isolated imaging sub-base (spec 4.2)" if name == "L17"
                                        else "instrument cabinet putting the transfer nest at 0.972 m (layout P1)"),
                           "sdt:designBasis": PROXY, "sdt:bindingStatus": "visual_v1"})
    # drop the informational collider: the live collider is the composer's P1 box (identical envelope)
    st.RemovePrim(f"{root}/Collision")
    st.GetRootLayer().Save()
    return n


# ------------------------------------------------------------------------------------------- L12 hood
HOOD = dict(x=(-0.495, 0.495), y0=-0.270, y1=-0.030, h=0.52, roof_y1=-0.030)


def build_l12_hood(h=None, roof_y1=None):
    """L12 enclosure in the L12 station frame (origin on the worktop at the station origin)."""
    h = HOOD["h"] if h is None else h
    roof_y1 = HOOD["roof_y1"] if roof_y1 is None else roof_y1
    k = Kit()
    xa, xb = HOOD["x"]
    y0, y1 = HOOD["y0"], HOOD["y1"]
    s = 0.030
    for x in (xa, xb):
        for y in (y0, y1):
            k.profile_item((x, y, 0.0), (x, y, h), s)
        k.profile_item((x, y0 + s / 2, h - s / 2), (x, y1 - s / 2, h - s / 2), s, up=(0, 0, 1))
        k.profile_item((x, y0 + s / 2, s / 2), (x, y1 - s / 2, s / 2), s, up=(0, 0, 1))
        k.box("Polycarbonate", (x, (y0 + y1) / 2, h / 2), (0.006, y1 - y0 - s, h - 2 * s))        # side glazing
        k.collide((x, (y0 + y1) / 2, h / 2), (0.03, y1 - y0 + s, h))
    for y in (y0,):
        k.profile_item((xa + s / 2, y, h - s / 2), (xb - s / 2, y, h - s / 2), s, up=(0, 0, 1))
        k.profile_item((xa + s / 2, y, s / 2), (xb - s / 2, y, s / 2), s, up=(0, 0, 1))
    # front: lift-up glazed service door (hinged at the top), handle, interlock
    k.box("Polycarbonate", (0, y0, h / 2), (xb - xa - s, 0.006, h - 2 * s))
    k.handle_bar("AluAnodized", (0, y0 - 0.004, 0.20), 0.30, axis=(1, 0, 0), standoff=0.03, r=0.007, normal=(0, -1, 0))
    k.rbox("PlasticRed", (xb - 0.04, y0 - 0.02, h - 0.06), (0.03, 0.02, 0.05), r=0.003)
    k.collide((0, y0, h / 2), (xb - xa + s, 0.03, h))
    # partial roof over the front half (status light bar + LED strip); the robot half stays open
    k.profile_item((xa + s / 2, roof_y1, h - s / 2), (xb - s / 2, roof_y1, h - s / 2), s, up=(0, 0, 1))
    k.box("Polycarbonate", (0, (y0 + roof_y1) / 2, h - 0.003), (xb - xa - s, roof_y1 - y0 - s, 0.006))
    k.rbox("PlasticWhite", (0, (y0 + roof_y1) / 2, h - 0.03), (xb - xa - 0.12, 0.05, 0.02), r=0.004)
    k.box("LedStrip", (0, (y0 + roof_y1) / 2, h - 0.0405), (xb - xa - 0.16, 0.035, 0.001))
    k.collide((0, (y0 + roof_y1) / 2, h - 0.01), (xb - xa + s, roof_y1 - y0 + s, 0.02))
    # light-curtain columns at the open edge: the robot half of the deck (R02's approach and carry corridor,
    # tools/fitout_clearance.py) stays open and guarded
    for x, face in ((xa + 0.035, 1), (xb - 0.035, -1)):
        k.rbox("PlasticYellow", (x, y1, h / 2 + 0.03), (0.03, 0.035, h - 0.10), r=0.003)
        k.box("PlasticBlack", (x + face * 0.0155, y1, h / 2 + 0.03), (0.0012, 0.025, h - 0.14))
        k.collide((x, y1, h / 2 + 0.03), (0.03, 0.035, h - 0.10))
    png = decals.station_plate(tex("l12_plate.png"), "L12", "Liquid handler", sub="AICOR Cell 01  |  ZEUS-class channel")
    k.decal(png, (-0.30, y0 - 0.0035, 0.37), (0, -1, 0), (0, 0, 1), 0.20, 0.07)
    st, root = new_asset(os.path.join(USD, "l12_hood.usda"), "Hood",
                         "Generated by assets/cell01_fitout/build_fitout.py - edit the script, not this file.")
    n = k.write(st, root, {"sdt:componentId": "L12-ENC", "sdt:canonicalName": "L12 enclosure",
                           "sdt:role": "Glazed hood over the L12 deck; robot side and the roof over the plate nest open "
                                       "for R02 (light-curtain guarded)", "sdt:designBasis": PROXY,
                           "sdt:bindingStatus": "static_v1", "sdt:roofOpenFrom_localY": float(roof_y1),
                           "sdt:height_m": float(h)})
    st.GetRootLayer().Save()
    return n


def main():
    lay = json.load(open(LAYOUT))
    out = {"enclosure": build_enclosure(), "bench_f01": build_bench(), "rail_cover": build_rail_cover(),
           "l12_hood": build_l12_hood()}
    for name, s in lay["stations"].items():
        if s["support"] == "bench":
            continue
        x0, x1, y0, y1 = s["footprint"]
        out[f"support_{name}"] = build_support(name, s["support"], x1 - x0 + 0.04, y1 - y0 + 0.04, s["support_height"],
                                               s["yaw_deg"])
    for k_, v in out.items():
        print(f"  {k_:18s} {v:8d} triangles")


if __name__ == "__main__":
    main()
