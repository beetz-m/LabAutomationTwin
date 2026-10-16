"""Build the L17 Bright-Field Imaging Station asset: parametric CAD -> STEP + layered, articulated OpenUSD.

Run with the CAD environment:  env_cad/bin/python assets/l17/build_l17.py

Cell 01 baseline (sdt/components/L17_BrightFieldImager.yaml): "OpenFlexure-derived operational mechanism in a
Cell01 photorealistic enclosure". This is a project-owned design in that spirit, not an OpenFlexure part model:
an inverted bright-field microscope for SBS plates whose XY stage is also the robot load drawer.

  * Robot interface: the plate sits on an OPEN frame nest (5 mm lips under the plate rim, the shared SBS corner
    guides and A1 key of assets/common/sbs_shuttle.py, finger reliefs at the long sides, 4 seat sensors in the
    short-side lips). The stage carries it out through a motorised front gate to the presented position
    (plate_load_frame) for top-down loading by R02 with T01.
  * XY stage: StageY (load stroke + row positioning) on a side rail, StageX (column positioning) on a guide
    behind the plate; nothing of the stage passes under the wells except the 4 mm frame, so the objectives
    image every well from below.
  * Optics module on FocusZ (the whole module moves, as in OpenFlexure): a 2-position objective turret
    (TurretRotate: 10x/0.25 and 4x/0.10, parfocal 45 mm), fold mirror, tube lens and camera.
  * Transmitted illumination: LED condenser above the plate on the optical axis (UsdLux DiskLight).
  * Barcode reader at the stage home position (reads the plate's -X end), front status lamps.

Every stage part that crosses the objectives' zone stays above the highest objective tip (focus +2.5 mm); the
build checks the collider boxes of all links for overlaps across the joint ranges (self-collisions are off).
"""

import itertools
import os
import sys

import cadquery as cq
import numpy as np
from pxr import Gf, Kind, Sdf, Usd, UsdGeom, UsdLux, UsdPhysics

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from common import twin_cad as tc  # noqa: E402
from common.sbs_shuttle import GUIDE_CL, GUIDE_W, ShuttleNest  # noqa: E402
from common.twin_cad import (B, F, MM, SBS, _drive, _joint, add_box_collider, add_convex_collider, bind, box, cyl,  # noqa: E402
                             define_contact_materials, define_materials, mm3, rrect, to_front, write_mesh)

NAME, PREFIX, TAG_ID = "L17_BrightFieldImager", "l17", 17
ROOT = f"/{NAME}"
GENERATOR = "assets/l17/build_l17.py"

# ------------------------------------------------------------------ geometry (mm, station frame, all joints at 0)
W, D, H, Z0, WALL = 440.0, 500.0, 430.0, 8.0, 3.0
XS, YF, YB, TOP = W / 2, -D / 2, D / 2, Z0 + H
SEAT_Z = 200.0                         # nest seat plane above the feet: 0.972 m on the 0.772 m plinth
X_OPT, Y_OPT = 0.0, -40.0              # optical axis
WELL_BOTTOM = SBS[2] - 10.9            # 3.45 mm: well-bottom surface above the plate's underside (plate model)
Z_FOCAL0 = SEAT_Z + WELL_BOTTOM        # focal plane at FocusZ = 0 for a seated plate
PARFOCAL = 45.0
OBJECTIVES = {  # optical engineering assumptions (plan achromats), not product data
    "10x": dict(na=0.25, wd=12.0, pixel_um=0.45, color="LabelYellow", angle=180.0),
    "4x": dict(na=0.10, wd=17.0, pixel_um=1.12, color="LensRedRing", angle=0.0),
}
TURRET_C, TURRET_R, TURRET_RO = (32.0, Y_OPT), 32.0, 48.0      # pivot, objective radius, disk radius
TURRET_Z = (146.0, Z_FOCAL0 - PARFOCAL)                         # disk under the objective shoulders
FOCUS_RANGE = (-2.5, 2.5)
X_RANGE = (-55.0, 55.0)
Y_LOAD = 290.0                         # StageY = -Y_LOAD presents the nest at y = Y_OPT - Y_LOAD
Y_RANGE = (-Y_LOAD, 36.0)
GATE = dict(x0=-92.0, x1=172.0, z0=150.0, z1=242.0, y=YF + WALL + 6.0, t=6.0, travel=95.0)
HX, HY = SBS[0] / 2, SBS[1] / 2        # plate half extents
LIP = 5.0                              # support lip under the plate rim
FX, FY = HX + GUIDE_CL + GUIDE_W, HY + GUIDE_CL + GUIDE_W       # frame outer half extents (74.38, 53.24)
FRAME_Z = (SEAT_Z - 4.0, SEAT_Z)
RELIEF_HX = 25.0
SEAT_SENSORS = [(-HX + LIP / 2, 25.0), (HX - LIP / 2, 25.0), (-HX + LIP / 2, -25.0), (HX - LIP / 2, -25.0)]
XGUIDE = dict(x=(-88.0, 162.0), y=(72.0, 84.0), z=(SEAT_Z - 3.5, SEAT_Z + 4.5))   # y rel. nest centre
XCARR = dict(x=(-24.0, 24.0), y=(70.0, 86.0), z=(SEAT_Z + 5.0, SEAT_Z + 14.0))
BEAM = dict(x=(138.0, 162.0), y=(-20.0, 240.0), z=(170.5, SEAT_Z - 3.5))           # y rel. nest centre
RAIL = dict(x=(140.0, 160.0), y=(-236.0, 236.0), z=(Z0 + 12.0, 170.0))
READER = (-142.0, Y_OPT, SEAT_Z + 8.0)                                           # lens point, looks +X
COND = dict(r=22.0, z=(242.0, 292.0))
CAM_X = -97.0                                                                     # sensor plane (faces +X)
TAG_C = (0.0, 78.0, XCARR["z"][1])                                                 # on the X carriage, rel. nest
ZF = Z_FOCAL0
assert max(Z_FOCAL0 - o["wd"] for o in OBJECTIVES.values()) + FOCUS_RANGE[1] < min(FRAME_Z[0], XGUIDE["z"][0]) - 2.0

LINKS = {  # link: (prim path, CAD origin, rest translate) - CAD is authored in station coordinates at q = 0
    "Body": ("Body", (0, 0, 0), (0, 0, 0)),
    "Gate": ("Gate", (0, GATE["y"], 0), (0, GATE["y"], 0)),
    "StageY": ("StageY", (0, Y_OPT, SEAT_Z), (0, Y_OPT, SEAT_Z)),
    "StageX": ("StageY/StageX", (0, Y_OPT, SEAT_Z), (0, 0, 0)),
    "Focus": ("Focus", (0, Y_OPT, 0), (0, Y_OPT, 0)),
    "Turret": ("Focus/Turret", (TURRET_C[0], TURRET_C[1], 0), (TURRET_C[0], 0, 0)),
}
MASSES = {"Body": 22.0, "Gate": 0.3, "StageY": 1.2, "StageX": 0.6, "Focus": 1.5, "Turret": 0.4}
EXTRA_PBR = {
    "PowderWhite": ((0.86, 0.87, 0.87), 0.42, 0.0, {}),
    "LensAmber": ((0.6, 0.35, 0.02), 0.15, 0.0, {"emissive": ((1.0, 0.55, 0.05), 0.0)}),
    "LensRedRing": ((0.70, 0.06, 0.05), 0.35, 0.0, {}),
    "IllumLed": ((0.92, 0.92, 0.92), 0.3, 0.0, {"emissive": ((1.0, 0.97, 0.92), 0.0)}),
    "OpticalGlass": ((0.05, 0.07, 0.09), 0.02, 0.0, {}),
}


def link_path(name):
    return f"{ROOT}/{LINKS[name][0]}"


def nest():
    """The shared SBS guide geometry, seated at SEAT_Z around the nest centre (0, Y_OPT)."""
    return ShuttleNest(z0=SEAT_Z - 34.0, y_ret=Y_OPT, travel=0.0, tag_id=TAG_ID)


# ------------------------------------------------------------------ CAD
def objective(name, o):
    """Objective at the optical axis position of the turret (station coords, FocusZ = 0, active)."""
    tip = Z_FOCAL0 - o["wd"]
    sh = Z_FOCAL0 - PARFOCAL
    x, y = X_OPT, Y_OPT
    nose_r = 6.5 if name == "10x" else 7.5
    taper0 = tip - (8.5 if name == "10x" else 10.5)
    body = cyl(10.5, taper0 - 4.0 - sh, (x, y, sh), (0, 0, 1))
    cone = cq.Workplane("XY").add(cq.Solid.makeCone(10.5, nose_r, 4.0, cq.Vector(x, y, taper0 - 4.0)))
    nose = cyl(nose_r, tip - taper0, (x, y, taper0), (0, 0, 1)).faces(">Z").edges().fillet(1.0)
    barrel = body.union(cone).union(nose)
    ring = cyl(10.7, 3.0, (x, y, taper0 - 12.0), (0, 0, 1))
    lens = cyl(2.6, 0.2, (x, y, tip - 0.05), (0, 0, 1))
    thread = cyl(9.0, 4.0, (x, y, sh - 4.0), (0, 0, 1))
    return barrel, ring, lens, thread


def rotate_about_pivot(wp, deg):
    cx, cy = TURRET_C
    return wp.rotate((cx, cy, 0), (cx, cy, 1), deg)


def build_cad():
    p = {}
    G = GATE
    # ---- housing
    outer = box(0, 0, Z0 + H / 2, W, D, H).edges("|Z").fillet(12).edges(">Z").fillet(5)
    inner = box(0, 0, Z0 + H / 2, W - 2 * WALL, D - 2 * WALL, H - 2 * WALL).edges("|Z").fillet(9)
    shell = outer.cut(inner).cut(box((G["x0"] + G["x1"]) / 2, YF + WALL / 2, (G["z0"] + G["z1"]) / 2,
                                     G["x1"] - G["x0"], WALL + 20, G["z1"] - G["z0"]))
    p["Housing"] = (shell, "PowderWhite", "Body")
    p["BaseFrame"] = (box(0, 0, (Z0 + Z0 + 12) / 2, W - 2 * WALL, D - 2 * WALL, 12), "AnodizedGraphite", "Body")
    for i, (sx, sy) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]):
        p[f"Foot{i}"] = (cyl(14, Z0, (sx * (W / 2 - 30), sy * (D / 2 - 30), 0), (0, 0, 1)).faces("<Z").edges()
                         .fillet(1.5), "RubberBlack", "Body")
    p["FrontPanel"] = (to_front(rrect(W - 40, 120, 6, 2), 0, 330, YF), "PlasticBlack", "Body")
    p["Label"] = (to_front(rrect(190, 18, 2, 0.8), -70, 360, YF - 2), "LabelWhite", "Body")
    text = cq.Workplane("XY").text("L17  BRIGHT-FIELD IMAGER", 8.0, 0.35, kind="bold", halign="center",
                                   valign="center")
    p["LabelText"] = (to_front(text, -70, 360, YF - 2.8), "PlasticBlack", "Body")
    p["GateFrame"] = (to_front(cq.Workplane("XY").rect(G["x1"] - G["x0"] + 24, G["z1"] - G["z0"] + 14)
                               .rect(G["x1"] - G["x0"], G["z1"] - G["z0"]).extrude(4),
                               (G["x0"] + G["x1"]) / 2, (G["z0"] + G["z1"]) / 2, YF), "AnodizedGraphite", "Body")
    for i, lens in enumerate(("LensGreen", "LensAmber", "LensRed")):
        p[f"StatusLamp{i}"] = (to_front(cyl(6, 3, (0, 0, 0), (0, 0, 1)), 120 + 20 * i, 360, YF - 2), lens, "Body")
    # ---- stage rail, focus column, reader, illumination (static)
    p["StageRail"] = (box(sum(RAIL["x"]) / 2, sum(RAIL["y"]) / 2, sum(RAIL["z"]) / 2, RAIL["x"][1] - RAIL["x"][0],
                          RAIL["y"][1] - RAIL["y"][0], RAIL["z"][1] - RAIL["z"][0]).edges("|Y").fillet(1),
                      "Aluminium", "Body")
    p["FocusColumn"] = (box(-168.5, Y_OPT, 80, 13, 80, 120).edges("|Z").fillet(1), "Aluminium", "Body")
    rx, ry, rz = READER
    p["BarcodeReader"] = (box(rx - 9, ry, rz, 18, 34, 14).edges().fillet(1.5), "PlasticBlack", "Body")
    p["BarcodeWindow"] = (box(rx + 0.25, ry, rz, 0.5, 20, 7), "SensorLens", "Body")
    p["ReaderPost"] = (box(rx - 9, ry, (Z0 + 12 + rz - 7) / 2, 10, 10, rz - 7 - Z0 - 12), "Aluminium", "Body")
    cz0, cz1 = COND["z"]
    p["Condenser"] = (cyl(COND["r"], cz1 - cz0 - 2, (X_OPT, Y_OPT, cz0 + 2), (0, 0, 1)).faces("<Z").edges()
                      .fillet(2), "AnodizedGraphite", "Body")
    p["CondenserLed"] = (cyl(15, 2, (X_OPT, Y_OPT, cz0), (0, 0, 1)), "IllumLed", "Body")
    p["IllumArm"] = (box(0, (Y_OPT + YB - WALL) / 2, cz1 - 8, 24, YB - WALL - Y_OPT, 16), "Aluminium", "Body")
    p["Electronics"] = (box(-60, 190, 90, 200, 80, 140).edges("|Z").fillet(3), "AnodizedGraphite", "Body")
    # ---- gate
    p["GatePanel"] = (box((G["x0"] + G["x1"]) / 2, G["y"], (G["z0"] + G["z1"]) / 2 + 2, G["x1"] - G["x0"] + 16,
                          G["t"], G["z1"] - G["z0"] + 4).edges("|Y").fillet(2), "AnodizedGraphite", "Gate")
    # ---- StageY: beam on the side rail + X guide behind the nest
    yn = Y_OPT
    p["StageBeam"] = (box(sum(BEAM["x"]) / 2, yn + sum(BEAM["y"]) / 2, sum(BEAM["z"]) / 2, BEAM["x"][1] - BEAM["x"][0],
                          BEAM["y"][1] - BEAM["y"][0], BEAM["z"][1] - BEAM["z"][0]).edges("|Y").fillet(1.5),
                      "AnodizedGraphite", "StageY")
    p["XGuide"] = (box(sum(XGUIDE["x"]) / 2, yn + sum(XGUIDE["y"]) / 2, sum(XGUIDE["z"]) / 2,
                       XGUIDE["x"][1] - XGUIDE["x"][0], XGUIDE["y"][1] - XGUIDE["y"][0],
                       XGUIDE["z"][1] - XGUIDE["z"][0]).edges("|X").fillet(1), "SteelSatin", "StageY")
    # ---- StageX: open frame nest, guides, A1 key, seat sensors, bracket, carriage, registration tag
    frame = box(0, yn, sum(FRAME_Z) / 2, 2 * FX, 2 * FY, FRAME_Z[1] - FRAME_Z[0]).edges("|Z").fillet(3)
    frame = frame.cut(box(0, yn, sum(FRAME_Z) / 2, 2 * (HX - LIP), 2 * (HY - LIP), 10).edges("|Z").fillet(4))
    for sy in (-1, 1):  # finger reliefs outside the plate rim at the middle of the long sides
        frame = frame.cut(box(0, yn + sy * (HY + 0.5 + 10), sum(FRAME_Z) / 2, 2 * RELIEF_HX, 20, 10))
    for x, y in SEAT_SENSORS:
        frame = frame.cut(cyl(2.6, 1.2, (x, yn + y, SEAT_Z - 1.0), (0, 0, 1)))
    p["NestFrame"] = (frame, "PeekNatural", "StageX")
    for i, (x, y) in enumerate(SEAT_SENSORS):
        p[f"SeatSensor{i}"] = (cyl(2.4, 0.3, (x, yn + y, SEAT_Z - 1.0), (0, 0, 1)), "SensorWindow", "StageX")
    N = nest()
    for name, g in N.guide_solids():
        p[name] = (g, "PeekNatural", "StageX")
    p["A1Key"] = (N.a1_key(), "PeekNatural", "StageX")
    p["Bracket"] = (box(0, yn + (FY + 72.0) / 2, sum(FRAME_Z) / 2, 36, 72.0 - FY + 1, FRAME_Z[1] - FRAME_Z[0]),
                    "Aluminium", "StageX")
    p["Riser"] = (box(0, yn + 69.0, (FRAME_Z[0] + XCARR["z"][1]) / 2, 36, 6, XCARR["z"][1] - FRAME_Z[0]),
                  "Aluminium", "StageX")
    p["XCarriage"] = (box(0, yn + sum(XCARR["y"]) / 2, sum(XCARR["z"]) / 2, XCARR["x"][1] - XCARR["x"][0],
                          XCARR["y"][1] - XCARR["y"][0], XCARR["z"][1] - XCARR["z"][0]).edges("|Z").fillet(2),
                      "SteelSatin", "StageX")
    p["TagPlate"] = (box(TAG_C[0], yn + TAG_C[1], TAG_C[2] + 0.3, 15, 15, 0.6), "LabelWhite", "StageX")
    # ---- Focus: optics bench, carriage, fold mirror, tube lens, camera, turret pivot
    p["OpticsBench"] = (box(-30, Y_OPT, 90, 240, 120, 10).edges("|Z").fillet(3), "AnodizedGraphite", "Focus")
    p["FocusCarriage"] = (box(-155.75, Y_OPT, 100, 11.5, 70, 60), "SteelSatin", "Focus")
    p["MirrorCube"] = (box(X_OPT, Y_OPT, 117, 34, 34, 34).edges().fillet(2), "AnodizedGraphite", "Focus")
    p["TubeLens"] = (cyl(15, 78, (-17, Y_OPT, 117), (-1, 0, 0)), "Aluminium", "Focus")
    p["Camera"] = (box(-115, Y_OPT, 117, 40, 44, 44).edges("|X").fillet(3), "PlasticBlack", "Focus")
    p["CameraMount"] = (cyl(16, 3, (-95, Y_OPT, 117), (-1, 0, 0)), "SteelSatin", "Focus")
    p["TurretPost"] = (cyl(8, TURRET_Z[0] - 95, (TURRET_C[0], TURRET_C[1], 95), (0, 0, 1)), "SteelSatin", "Focus")
    # ---- Turret: disk + objectives (10x on the axis at q = 0, 4x opposite)
    disk = cyl(TURRET_RO, TURRET_Z[1] - TURRET_Z[0], (TURRET_C[0], TURRET_C[1], TURRET_Z[0]), (0, 0, 1))
    p["TurretDisk"] = (disk.edges().fillet(1.5), "SteelSatin", "Turret")
    for name, o in OBJECTIVES.items():
        rot = o["angle"] - 180.0            # parts are built on the axis (angle 180 about the pivot)
        solids = objective(name, o)
        for part, solid, mat in zip(("Barrel", "Ring", "FrontLens", "Thread"), solids,
                                    ("SteelSatin", o["color"], "OpticalGlass", "Brass")):
            p[f"Objective{name}{part}"] = (rotate_about_pivot(solid, rot), mat, "Turret")
    return p


# ------------------------------------------------------------------ colliders (station coords at q = 0)
def collision_boxes():
    G, t = GATE, WALL
    body = [
        ("Floor", (-XS, XS), (YF, YB), (0, Z0 + 12)),
        ("Roof", (-XS, XS), (YF, YB), (TOP - t, TOP)),
        ("WallBack", (-XS, XS), (YB - t, YB), (Z0, TOP)),
        ("WallLeft", (-XS, -XS + t), (YF, YB), (Z0, TOP)),
        ("WallRight", (XS - t, XS), (YF, YB), (Z0, TOP)),
        ("WallFrontLow", (-XS, XS), (YF, YF + t), (Z0, G["z0"])),
        ("WallFrontHigh", (-XS, XS), (YF, YF + t), (G["z1"], TOP)),
        ("WallFrontLeft", (-XS, G["x0"]), (YF, YF + t), (G["z0"], G["z1"])),
        ("WallFrontRight", (G["x1"], XS), (YF, YF + t), (G["z0"], G["z1"])),
        ("StageRail", RAIL["x"], RAIL["y"], RAIL["z"]),
        ("FocusColumn", (-175, -162), (Y_OPT - 40, Y_OPT + 40), (Z0 + 12, 140)),
        ("BarcodeReader", (READER[0] - 18, READER[0]), (Y_OPT - 17, Y_OPT + 17), (READER[2] - 7, READER[2] + 7)),
        ("Condenser", (-COND["r"], COND["r"]), (Y_OPT - COND["r"], Y_OPT + COND["r"]), COND["z"]),
        ("IllumArm", (-12, 12), (Y_OPT, YB - t), (COND["z"][1] - 16, COND["z"][1])),
        ("Electronics", (-160, 40), (150, 230), (20, 160)),
    ]
    gate = [("Panel", (G["x0"] - 8, G["x1"] + 8), (G["y"] - G["t"] / 2, G["y"] + G["t"] / 2), (G["z0"], G["z1"] + 4))]
    yn = Y_OPT
    stage_y = [("Beam", BEAM["x"], tuple(yn + v for v in BEAM["y"]), BEAM["z"]),
               ("XGuide", XGUIDE["x"], tuple(yn + v for v in XGUIDE["y"]), XGUIDE["z"])]
    fz = FRAME_Z
    stage_x = [("FrameShortL", (-FX, -(HX - LIP)), (yn - FY, yn + FY), fz),
               ("FrameShortR", (HX - LIP, FX), (yn - FY, yn + FY), fz)]
    for sy, tag in ((-1, "Front"), (1, "Back")):
        lip = tuple(sorted((yn + sy * (HY - LIP), yn + sy * HY)))
        band = tuple(sorted((yn + sy * HY, yn + sy * FY)))
        stage_x += [(f"Lip{tag}", (-(HX - LIP), HX - LIP), lip, fz),
                    (f"Band{tag}L", (-(HX - LIP), -RELIEF_HX), band, fz),
                    (f"Band{tag}R", (RELIEF_HX, HX - LIP), band, fz)]
    stage_x += [("Bracket", (-18, 18), (yn + FY, yn + 72.0), fz),
                ("Riser", (-18, 18), (yn + 66.0, yn + 72.0), (fz[0], XCARR["z"][1])),
                ("XCarriage", XCARR["x"], tuple(yn + v for v in XCARR["y"]), XCARR["z"])]
    focus = [("Bench", (-150, 90), (Y_OPT - 60, Y_OPT + 60), (85, 95)),
             ("Carriage", (-161.5, -150), (Y_OPT - 35, Y_OPT + 35), (70, 130)),
             ("MirrorCube", (-17, 17), (Y_OPT - 17, Y_OPT + 17), (100, 134)),
             ("TubeLens", (-95, -17), (Y_OPT - 15, Y_OPT + 15), (102, 132)),
             ("Camera", (-135, -95), (Y_OPT - 22, Y_OPT + 22), (95, 139)),
             ("TurretPost", (TURRET_C[0] - 8, TURRET_C[0] + 8), (Y_OPT - 8, Y_OPT + 8), (95, TURRET_Z[0]))]
    cx, cy = TURRET_C
    turret = [("Disk", (cx - TURRET_RO, cx + TURRET_RO), (cy - TURRET_RO, cy + TURRET_RO), TURRET_Z)]
    for name, o in OBJECTIVES.items():
        a = np.radians(o["angle"])
        ox, oy = cx + TURRET_R * np.cos(a), cy + TURRET_R * np.sin(a)
        turret.append((f"Objective{name}", (ox - 10.5, ox + 10.5), (oy - 10.5, oy + 10.5),
                       (TURRET_Z[1], Z_FOCAL0 - o["wd"])))
    return {"Body": body, "Gate": gate, "StageY": stage_y, "StageX": stage_x, "Focus": focus, "Turret": turret}


def check_clearance(min_gap=0.3):
    """Sweep the joint ranges and check that no two links' collider boxes overlap (AABB, mm)."""
    boxes = collision_boxes()

    def placed(link, q):
        gate, sy, sx, fz, tr = q
        out = []
        for name, xs, ys, zs in boxes[link]:
            lo, hi = np.array([xs[0], ys[0], zs[0]], float), np.array([xs[1], ys[1], zs[1]], float)
            if link == "Turret":                        # rotate the box corners about the pivot, take the AABB
                c = np.array([[x, y] for x in (lo[0], hi[0]) for y in (lo[1], hi[1])]) - TURRET_C
                ca, sa = np.cos(np.radians(tr)), np.sin(np.radians(tr))
                c = c @ np.array([[ca, sa], [-sa, ca]]) + TURRET_C
                lo[:2], hi[:2] = c.min(0), c.max(0)
            d = {"Gate": (0, 0, gate), "StageY": (0, sy, 0), "StageX": (sx, sy, 0), "Focus": (0, 0, fz),
                 "Turret": (0, 0, fz)}.get(link, (0, 0, 0))
            out.append((name, lo + d, hi + d))
        return out

    grid = itertools.product((0.0, GATE["travel"]), np.linspace(*Y_RANGE, 34), np.linspace(*X_RANGE, 5),
                             FOCUS_RANGE, (0.0, 45.0, 90.0, 135.0, 180.0))
    worst, hits = 1e9, set()
    for q in grid:
        gate, sy = q[0], q[1]
        if sy < -5.0 and gate < GATE["travel"]:   # interlock: the stage leaves home only with the gate open
            continue
        if sy < -100.0 and abs(q[2]) > 1.0:        # sequencing: StageX is centred before StageY leaves the chamber
            continue
        pl = {k: placed(k, q) for k in boxes}
        for a, b in itertools.combinations(pl, 2):
            if {a, b} in ({"StageX", "StageY"}, {"Focus", "Turret"}):   # parent/child: mounted together
                continue
            for na, la, ha in pl[a]:
                for nb, lb, hb in pl[b]:
                    gap = np.max(np.maximum(lb - ha, la - hb))
                    worst = min(worst, gap)
                    if gap < min_gap:
                        hits.add((a, na, b, nb, tuple(np.round(q, 1))))
    allowed = {("Body", "StageRail", "StageY", "Beam")}            # beam rides 0.5 mm above its rail
    real = sorted(h for h in hits if (h[0], h[1], h[2], h[3]) not in allowed)
    assert not real, f"collider overlaps: {real[:6]} (+{len(real) - 6 if len(real) > 6 else 0})"
    return worst


# ------------------------------------------------------------------ layers
def new_layer(name):
    return tc.new_layer(os.path.join(HERE, f"{PREFIX}_{name}.usda" if name else f"{PREFIX}.usda"), NAME, GENERATOR)


def write_visual(parts):
    tc.PBR.update(EXTRA_PBR)
    vis = new_layer("visual")
    UsdGeom.Xform.Define(vis, ROOT)
    mats = define_materials(vis, ROOT, sorted({m for _, m, _ in parts.values()} | {"AprilTag"}), tag_id=TAG_ID)
    for name, (_, _, rest) in LINKS.items():
        xf = UsdGeom.Xform.Define(vis, link_path(name))
        xf.AddTranslateOp().Set(Gf.Vec3d(*(np.array(rest, dtype=float) * MM)))
        if name == "Turret":
            xf.AddRotateZOp().Set(0.0)
        UsdGeom.Xform.Define(vis, f"{link_path(name)}/Visual")
    tri = 0
    for name, (wp, mat, link) in parts.items():
        mesh, n = write_mesh(vis, f"{link_path(link)}/Visual/{name}", wp, LINKS[link][1])
        bind(mesh.GetPrim(), mats[mat])
        tri += n
    # registration tag on the X carriage (visible from above with the stage presented)
    o = np.array(LINKS["StageX"][1], float)
    tx, ty, tz, hs = (TAG_C[0] - o[0]) * MM, (Y_OPT + TAG_C[1] - o[1]) * MM, (TAG_C[2] + 0.62 - o[2]) * MM, 6.0 * MM
    tagm = UsdGeom.Mesh.Define(vis, f"{link_path('StageX')}/Visual/AprilTag")
    tagm.CreatePointsAttr([Gf.Vec3f(tx - hs, ty - hs, tz), Gf.Vec3f(tx + hs, ty - hs, tz),
                           Gf.Vec3f(tx + hs, ty + hs, tz), Gf.Vec3f(tx - hs, ty + hs, tz)])
    tagm.CreateFaceVertexCountsAttr([4])
    tagm.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    tagm.CreateNormalsAttr([Gf.Vec3f(0, 0, 1)] * 4)
    tagm.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
    tagm.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    UsdGeom.PrimvarsAPI(tagm).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex).Set(
        [Gf.Vec2f(0, 0), Gf.Vec2f(1, 0), Gf.Vec2f(1, 1), Gf.Vec2f(0, 1)])
    bind(tagm.GetPrim(), mats["AprilTag"])
    # transmitted illumination (intensity driven by the controller) and a dim interior service light
    led = UsdLux.DiskLight.Define(vis, f"{link_path('Body')}/Visual/IlluminationLed")
    led.CreateRadiusAttr(0.012)
    led.CreateIntensityAttr(0.0)
    led.CreateColorTemperatureAttr(5600.0)
    led.CreateEnableColorTemperatureAttr(True)
    led.AddTranslateOp().Set(Gf.Vec3d(X_OPT * MM, Y_OPT * MM, (COND["z"][0] - 0.5) * MM))
    vis.GetRootLayer().Save()
    return tri


def write_physics():
    phy = new_layer("physics")
    cmat = define_contact_materials(phy, ROOT)
    n = 0
    for link, boxes in collision_boxes().items():
        lp = phy.OverridePrim(link_path(link))
        UsdPhysics.RigidBodyAPI.Apply(lp)
        UsdPhysics.MassAPI.Apply(lp).CreateMassAttr(MASSES[link])
        col = UsdGeom.Xform.Define(phy, f"{link_path(link)}/Collision")
        col.CreatePurposeAttr(UsdGeom.Tokens.guide)
        origin = np.array(LINKS[link][1], dtype=float)
        for name, xs, ys, zs in boxes:
            mat = cmat["Peek"] if link == "StageX" else cmat["Steel"]
            add_box_collider(phy, col.GetPath(), name, xs, ys, zs, origin, mat,
                             offsets=(0.0005, 0.0) if link != "Body" else None)
            n += 1
        if link == "StageX":
            N = nest()
            for name, solid in N.convex_colliders():
                add_convex_collider(phy, f"{col.GetPath()}/{name}", solid, origin, cmat["Peek"])
                n += 1
    phy.GetRootLayer().Save()
    return n


def write_articulation():
    art = new_layer("articulation")
    root = art.GetPrimAtPath(ROOT)
    UsdPhysics.ArticulationRootAPI.Apply(root)
    root.AddAppliedSchema("PhysxArticulationAPI")
    # self-collisions off: rails and carriages touch by design; check_clearance() verifies the rest at build time
    root.CreateAttribute("physxArticulation:enabledSelfCollisions", B).Set(False)
    root.CreateAttribute("physxArticulation:solverPositionIterationCount", Sdf.ValueTypeNames.Int).Set(32)
    root.CreateAttribute("physxArticulation:solverVelocityIterationCount", Sdf.ValueTypeNames.Int).Set(4)
    root.CreateAttribute("physxArticulation:sleepThreshold", F).Set(0.0)
    body = link_path("Body")
    UsdGeom.Scope.Define(art, f"{ROOT}/Joints")
    J = f"{ROOT}/Joints"
    _joint(art, UsdPhysics.FixedJoint, f"{J}/RootJoint", None, body, Gf.Vec3f(0), Gf.Vec3f(0))
    g = _joint(art, UsdPhysics.PrismaticJoint, f"{J}/GateSlide", body, link_path("Gate"), mm3((0, GATE["y"], 0)),
               Gf.Vec3f(0), "Z", (0.0, GATE["travel"] * MM))
    _drive(g, "linear", stiffness=50000.0, damping=400.0, max_force=100.0, target=0.0)
    sy = _joint(art, UsdPhysics.PrismaticJoint, f"{J}/StageY", body, link_path("StageY"), mm3((0, Y_OPT, SEAT_Z)),
                Gf.Vec3f(0), "Y", (Y_RANGE[0] * MM, Y_RANGE[1] * MM))
    _drive(sy, "linear", stiffness=200000.0, damping=1200.0, max_force=200.0, target=0.0)
    sx = _joint(art, UsdPhysics.PrismaticJoint, f"{J}/StageX", link_path("StageY"), link_path("StageX"),
                Gf.Vec3f(0), Gf.Vec3f(0), "X", (X_RANGE[0] * MM, X_RANGE[1] * MM))
    _drive(sx, "linear", stiffness=200000.0, damping=800.0, max_force=200.0, target=0.0)
    fz = _joint(art, UsdPhysics.PrismaticJoint, f"{J}/FocusZ", body, link_path("Focus"), mm3((0, Y_OPT, 0)),
                Gf.Vec3f(0), "Z", (FOCUS_RANGE[0] * MM, FOCUS_RANGE[1] * MM))
    _drive(fz, "linear", stiffness=1.0e7, damping=8000.0, max_force=2000.0, target=0.0)   # lead screw: ~1 um sag
    tr = _joint(art, UsdPhysics.RevoluteJoint, f"{J}/TurretRotate", link_path("Focus"), link_path("Turret"),
                mm3((TURRET_C[0], 0, 0)), Gf.Vec3f(0), "Z", (-2.0, 182.0))
    _drive(tr, "angular", stiffness=5.0, damping=0.05, max_force=10.0, target=0.0)
    art.GetRootLayer().Save()


def write_semantics():
    sem = new_layer("semantics")
    rp = sem.GetPrimAtPath(ROOT)
    Usd.ModelAPI(rp).SetKind(Kind.Tokens.component)
    S, St, Db, Bo = (Sdf.ValueTypeNames.String, Sdf.ValueTypeNames.StringArray, Sdf.ValueTypeNames.Double,
                     Sdf.ValueTypeNames.Bool)
    attrs = [
        ("sdt:componentId", S, "L17"),
        ("sdt:canonicalName", S, "L17 Bright-Field Imaging Station"),
        ("sdt:contract", S, "sdt/components/L17_BrightFieldImager.yaml"),
        ("sdt:capabilities", St, ["load_plate", "autofocus", "image_well", "image_plate_region",
                                  "compute_focus_quality", "export_raw_image"]),
        ("sdt:bindingStatus", S, "articulated_v1"),
        ("sdt:designBasis", S, "project-owned inverted bright-field plate imager in the spirit of the Cell 01 "
                               "baseline (OpenFlexure-derived mechanism); not an OpenFlexure part model"),
        ("state:plate_id", S, ""),
        ("state:door", S, "closed"),
        ("state:stage_pose", S, "home"),
        ("state:focus_score", Db, -1.0),
        ("state:exposure_ms", Db, 0.0),
        ("state:magnification", S, "10x"),
        ("state:illumination", S, "off"),
        ("state:calibration_valid", Bo, True),
        ("state:mode", S, "READY"),
        ("state:fault", S, ""),
    ]
    for k, t, v in attrs:
        rp.CreateAttribute(k, t, custom=True).Set(v)
    geo = {"seatZ_mm": SEAT_Z, "wellBottom_mm": WELL_BOTTOM, "focalZ0_mm": Z_FOCAL0, "yLoad_mm": Y_LOAD,
           "gateTravel_mm": GATE["travel"], "xMin_mm": X_RANGE[0], "xMax_mm": X_RANGE[1], "yMax_mm": Y_RANGE[1],
           "focusMin_mm": FOCUS_RANGE[0], "focusMax_mm": FOCUS_RANGE[1]}
    for k, v in geo.items():
        rp.CreateAttribute(f"imager:{k}", Db, custom=True).Set(float(v))
    for name, o in OBJECTIVES.items():
        for k in ("na", "wd", "pixel_um", "angle"):
            rp.CreateAttribute(f"optics:objective_{name}:{k}", Db, custom=True).Set(float(o[k]))
    rp.CreateAttribute("optics:objectives", St, custom=True).Set(list(OBJECTIVES))
    rp.CreateAttribute("optics:note", S, custom=True).Set(
        "objective NA/WD/pixel size are optical engineering assumptions (plan achromats, parfocal 45 mm); "
        "image formation: twin/l17_optics.py")

    def frame(name, pos, role, parent=None):
        # a link Xform sits at its CAD origin at rest, so link-attached frames are authored relative to it
        path = f"{ROOT}/{name}" if parent is None else f"{link_path(parent)}/{name}"
        origin = np.zeros(3) if parent is None else np.array(LINKS[parent][1], float)
        f = UsdGeom.Xform.Define(sem, path)
        f.AddTranslateOp().Set(Gf.Vec3d(*((np.array(pos, dtype=float) - origin) * MM)))
        f.GetPrim().CreateAttribute("sdt:frameRole", S, custom=True).Set(role)
        return f

    N = nest()
    lf = frame("plate_load_frame", (0, Y_OPT - Y_LOAD, SEAT_Z),
               "Presented SBS plate seat (gate open, StageY = -yLoad, StageX = 0): robot place/pick target. +X along "
               "the plate long axis, A1 corner at (-X,+Y), +Z up")
    for k, t, v in N.transfer_attributes():
        if k == "sdt:registration":
            v = f"StageY/StageX/registration_tag (AprilTag 36h11 #{TAG_ID}, 12 mm, on the X carriage behind the nest)"
        lf.GetPrim().CreateAttribute(k, {"string": S, "double": Db}[t], custom=True).Set(v)
    frame("plate_stage", (0, Y_OPT, SEAT_Z),
          "Stage home: plate seat centre with StageX = StageY = 0 (plate centre on the optical axis). Live pose = "
          "this + (StageX, StageY); the moving frame is StageY/StageX/plate_seat")
    frame("objective_frame", (X_OPT, Y_OPT, Z_FOCAL0),
          "Optical axis at the focal plane with FocusZ = 0 (+Z toward the sample). The focal plane moves with FocusZ "
          "(live: Focus/focal_point); the active objective is the one indexed by TurretRotate")
    frame("camera_frame", (CAM_X, Y_OPT, 117.0),
          "Camera sensor plane centre (FocusZ = 0); optical axis folded by the mirror cube, sensor looks +X. Image "
          "axes: +u = station +X, +v = station +Y at the sample")
    frame("illumination_frame", (X_OPT, Y_OPT, COND["z"][0]),
          "LED condenser exit on the optical axis, emits -Z (transmitted illumination); light prim "
          "Body/Visual/IlluminationLed")
    frame("barcode_reader", READER, "barcode reader lens point; reads the plate's -X short end along +X at stage home")
    frame("gate_frame", (0, GATE["y"], GATE["z0"]), "Load gate plane at the opening sill; joint GateSlide, +q opens (up)")
    frame("plate_seat", (0, Y_OPT, SEAT_Z), "plate seat centre on the moving stage", parent="StageX")
    frame("registration_tag", (TAG_C[0], Y_OPT + TAG_C[1], TAG_C[2] + 0.62), "AprilTag 36h11 centre", parent="StageX")
    for i, (x, y) in enumerate(SEAT_SENSORS):
        frame(f"seat_sensor_{i}", (x, Y_OPT + y, SEAT_Z - 1.0), "flush seat sensor window in the lip, looks +Z",
              parent="StageX")
    frame("focal_point", (X_OPT, Y_OPT, Z_FOCAL0), "live focal point of the indexed objective", parent="Focus")
    sem.GetRootLayer().Save()


def build():
    os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
    tc.make_textures(os.path.join(HERE, "textures"), [TAG_ID])
    worst = check_clearance()
    parts = build_cad()
    asm = cq.Assembly(name=NAME)
    for name, (wp, _, _) in parts.items():
        asm.add(wp, name=name)
    asm.export(os.path.join(HERE, "build", f"{PREFIX}.step"))
    tri = write_visual(parts)
    n_col = write_physics()
    write_articulation()
    write_semantics()
    top = new_layer("")
    top.GetRootLayer().subLayerPaths = [f"./{PREFIX}_{s}.usda" for s in ("semantics", "articulation", "physics",
                                                                         "visual")]
    top.GetRootLayer().Save()
    print(f"L17: {len(parts)} parts, {tri} triangles, {n_col} colliders; seat z {SEAT_Z} mm, focal plane z {Z_FOCAL0} "
          f"mm, load nest y {Y_OPT - Y_LOAD} mm; smallest collider gap over the joint sweep {worst:.2f} mm")


if __name__ == "__main__":
    build()
