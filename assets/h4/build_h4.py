"""Build the H4 Quarantine Station asset: parametric CAD -> STEP + layered, articulated OpenUSD.

Run with the CAD environment (CadQuery + usd-core), not the Isaac Sim one:
    env_cad/bin/python assets/h4/build_h4.py

Design (option A, project-owned; no manufacturer CAD):
  * brushed stainless cabinet, 300 x 260 x 198 mm incl. feet, one SBS plate position
  * motorised side-hinged front door with polycarbonate window, rubber gasket, manual handle
  * solenoid latch: the bolt engages a slot in the door edge, so a locked door is physically blocked
  * motorised transfer SHUTTLE: the nest rides out through the door opening so the robot loads it
    top-down outside the cabinet (unlimited headroom), then retracts into the chamber before closing
  * robot-grade SBS nest: 34 deg lead-in corner guides (+-6.5 mm capture), finger reliefs for a
    long-side grip, A1 orientation key, 4 flush seat sensors (flat + correctly oriented)
  * registration: AprilTag 36h11 #4 and a conical datum pin on the shuttle tray
  * through-beam plate-presence sensor in the chamber (diverse cross-check), interior LED strip
  * red/green stack light ("distinct visual status" risk control in the SDT)
  * side control panel: illuminated DOOR pushbutton + RELEASE key switch (authorised release)

Local frame (Cell 01 conventions, D003/D005): metres, Z up, origin at the centre of the
footprint on the bench plane, door on the -Y face, hinge on -X, control panel on +X.

Prim hierarchy (one rigid link per moving part; D006 layer separation):
  /H4_Quarantine                       ArticulationRoot, SDT identity + state:*
    Body/{Visual,Collision}            fixed base link (RootJoint to world)
    Door/{Visual,Collision}            DoorHinge   revolute  0..105 deg, position drive (motor)
    LatchBolt/{Visual,Collision}       LatchSlide  prismatic 0 = extended (locked) .. 6.5 mm retracted
    Shuttle/{Visual,Collision}         ShuttleSlide prismatic 0 = stowed .. 150 mm presented (toward -Y)
    Controls/DoorButton/Plunger        button_joint prismatic -3..0 mm, spring return (Cell 01 pushbutton convention)
    Controls/KeySwitch/KeyCylinder     key_joint   revolute 0 (LOCK) .. 90 deg (RELEASE)
    Joints/                            RootJoint, DoorHinge, LatchSlide
    quarantine_nest, door_frame        frames required by sdt/usd_bindings (stowed seat, hinge)
    transfer_nest                      presented seat: the robot's place/pick target (Cell 01 L09 naming)
    Shuttle/registration_tag|_datum    registration features that move with the nest
    Looks/

Layers (h4.usda sublayers, strongest first):
  h4_semantics.usda     SDT attributes, state, frames
  h4_articulation.usda  articulation root, joints, limits, drives, control attributes
  h4_physics.usda       rigid bodies, masses, collision proxies, contact materials
  h4_visual.usda        render meshes, MDL materials, link transforms
Plus build/h4.step, build/plate_sbs96.step, ../labware/plate_sbs96.usda (rigid-body plate prop), textures/.
"""

import os
import sys

import cadquery as cq
import numpy as np
from pxr import Gf, Kind, Sdf, Usd, UsdGeom, UsdLux, UsdPhysics

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common import twin_cad as tc  # noqa: E402
from common.sbs_shuttle import GUIDE_CL, GUIDE_LEAD, TAG_CODE, ShuttleNest  # noqa: E402
from common.twin_cad import (B, F, MM, SBS, _drive, _joint, add_box_collider, add_convex_collider, bind,  # noqa: E402
                             box, build_plate, cyl, define_contact_materials, define_materials, mm3, rrect,
                             to_front, to_side, write_mesh)

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
TEX = os.path.join(HERE, "textures")
LABWARE = os.path.join(HERE, "..", "labware")
ROOT = "/H4_Quarantine"

# ----------------------------------------------------------------------------------------------
# Dimensions (mm)
# ----------------------------------------------------------------------------------------------
Z0 = 8.0                       # foot height
W, D, H = 300.0, 260.0, 190.0  # cabinet body
YF = -D / 2                    # front face plane
XS = W / 2                     # right side face plane (control panel)
CW, CH, CD = 236.0, 126.0, 230.0  # chamber opening width/height, depth
CZ0 = Z0 + 30.0                # chamber floor
DOOR_W, DOOR_H, DOOR_T = 252.0, 142.0, 14.0
DOOR_ZC = CZ0 + CH / 2         # door / opening centre height
GASKET_T = 3.0
DOOR_BACK = YF - GASKET_T      # door back face plane
HINGE = (-131.0, YF - 10.0)    # hinge axis (x, y)
BOLT_X, BOLT_Y, BOLT_R, BOLT_L = 129.0, DOOR_BACK - DOOR_T / 2, 3.0, 8.0  # bolt base (tip at BOLT_X - BOLT_L)
BOLT_TRAVEL = 6.5
SLOT_X = 119.0                 # door edge slot that receives the bolt: x in [SLOT_X, door edge]
# shuttle: the validated robot hand-off interface (assets/common/sbs_shuttle.py)
NEST = ShuttleNest(z0=CZ0, y_ret=-66.0, travel=150.0, tag_id=4, rail_y0=YF + 4)
RAIL_Z1, CARR_Z1, BEAM_Z1, TRAY_Z1, SEAT_Z = NEST.rail_z1, NEST.carr_z1, NEST.beam_z1, NEST.tray_z1, NEST.seat_z
NEST_Y_RET, SHUTTLE_TRAVEL, NEST_Y_EXT = NEST.y_ret, NEST.travel, NEST.y_ext
TRAY_HD, SLIDE_L = NEST.tray_hd, NEST.slide_l
TAG_ID, TAG_C, DATUM_C, SEAT_SENSORS = NEST.tag_id, NEST.tag_c, NEST.datum_c, NEST.seat_sensors
NEST_C = (0.0, NEST_Y_RET)     # stowed plate seat (x, y) = quarantine_nest
NEST_TOP = SEAT_Z
BEAM_Y, BEAM_Z = NEST_Y_RET, SEAT_Z + 7
PANEL_C = (-75.0, Z0 + H / 2)  # (y, z) on the +X face
BTN = (XS + 2, -75.0, 128.0)   # button axis point on the panel surface
KEY = (XS + 2, -75.0, 80.0)
BTN_TRAVEL = 3.0
DOOR_OPEN_MAX_DEG = 105.0

LINKS = {  # name: (prim path under ROOT, joint-zero origin for mesh offsets (mm), rest translate (mm))
    "Body": ("Body", (0, 0, 0), (0, 0, 0)),
    "Door": ("Door", (HINGE[0], HINGE[1], 0), (HINGE[0], HINGE[1], 0)),
    "LatchBolt": ("LatchBolt", (BOLT_X, BOLT_Y, DOOR_ZC), (BOLT_X + BOLT_TRAVEL, BOLT_Y, DOOR_ZC)),  # rest = unlocked
    "Plunger": ("Controls/DoorButton/Plunger", BTN, BTN),
    "KeyCylinder": ("Controls/KeySwitch/KeyCylinder", KEY, KEY),
    "Shuttle": ("Shuttle", (0, NEST_Y_RET, 0), (0, NEST_Y_RET, 0)),
}
GROUP_LINK = {"Housing": "Body", "Interior": "Body", "StatusLight": "Body", "Panel": "Body",
              "Door": "Door", "LatchBolt": "LatchBolt", "Plunger": "Plunger", "KeyCylinder": "KeyCylinder",
              "Shuttle": "Shuttle"}


# ----------------------------------------------------------------------------------------------
# CAD
# ----------------------------------------------------------------------------------------------
def build_cad():
    p = {}  # name -> (workplane, material, group)

    # cabinet body with a filleted chamber cut in from the front
    body = box(0, 0, Z0 + H / 2, W, D, H).edges("|Z").fillet(8).edges(">Z or <Z").fillet(2.5)
    chamber = box(0, YF + CD / 2 - 2, CZ0 + CH / 2, CW, CD + 4, CH).edges("|Y").fillet(5)
    p["Cabinet"] = (body.cut(chamber), "SteelBrushed", "Housing")

    for i, (sx, sy) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]):
        foot = cyl(11, Z0, (sx * 118, sy * 98, 0), (0, 0, 1)).faces("<Z").edges().fillet(1.5)
        p[f"Foot{i}"] = (foot, "RubberBlack", "Housing")

    gasket = cq.Workplane("XY").rect(CW + 12, CH + 12).rect(CW + 2, CH + 2).extrude(GASKET_T)
    p["Gasket"] = (to_front(gasket, 0, DOOR_ZC, YF), "RubberBlack", "Housing")

    for i, (sx, z) in enumerate([(-1, Z0 + 14), (1, Z0 + 14), (-1, Z0 + H - 12), (1, Z0 + H - 12)]):
        head = (cq.Workplane("XY").circle(3.6).extrude(1.8).faces(">Z").edges().fillet(0.9)
                .faces(">Z").workplane().polygon(6, 2.9).cutBlind(-1.2))
        p[f"Screw{i}"] = (to_front(head, sx * 136, z, YF), "SteelSatin", "Housing")

    label = to_front(rrect(124, 15, 1.5, 0.8), 0, Z0 + H - 12, YF)
    p["Label"] = (label, "LabelYellow", "Housing")
    text = cq.Workplane("XY").text("QUARANTINE   H4", 8.0, 0.35, kind="bold", halign="center", valign="center")
    p["LabelText"] = (to_front(text, 0, Z0 + H - 12, YF - 0.8), "PlasticBlack", "Housing")

    # hinges: barrels + housing leaves are static; door leaves move with the door
    hx, hy = HINGE
    for i, zc in enumerate([DOOR_ZC - 48, DOOR_ZC + 48]):
        p[f"HingeBarrel{i}"] = (cyl(4.5, 30, (hx, hy, zc - 15), (0, 0, 1)), "SteelSatin", "Housing")
        p[f"HingeLeaf{i}"] = (box(hx - 6, YF - 3, zc, 12, 6, 30).edges("|Y").fillet(1), "SteelSatin", "Housing")

    # solenoid latch on the right of the door; the bolt is its own link
    p["LatchBody"] = (box(135, YF - 11, DOOR_ZC, 13, 22, 44).edges().fillet(1.5), "AnodizedGraphite", "Housing")
    p["LatchBoltPin"] = (cyl(BOLT_R, BOLT_L, (BOLT_X, BOLT_Y, DOOR_ZC), (-1, 0, 0)).faces("<X").edges().fillet(0.8),
                         "SteelSatin", "LatchBolt")

    # chamber interior: shuttle rail + drive, through-beam sensor, LED strip; shuttle parts are their own link
    p["Rail"] = (NEST.rail_part(NEST_Y_RET + TRAY_HD + SLIDE_L), "SteelSatin", "Interior")
    p["DriveUnit"] = (box(65, 79, CZ0 + 16, 50, 38, 32).edges().fillet(2), "AnodizedGraphite", "Interior")
    for name, wp, mat in NEST.parts():
        p[name] = (wp, mat, "Shuttle")
    for side, name in [(-1, "Emitter"), (1, "Receiver")]:
        p[f"Sensor{name}"] = (box(side * (CW / 2 - 4), BEAM_Y, BEAM_Z, 8, 16, 14).edges().fillet(1),
                              "PlasticBlack", "Interior")
        p[f"Sensor{name}Lens"] = (cyl(3.0, 0.8, (side * (CW / 2 - 8), BEAM_Y, BEAM_Z), (-side, 0, 0)),
                                  "SensorLens", "Interior")
    p["LedStrip"] = (box(0, YF + 30, CZ0 + CH - 1, 180, 8, 2), "LedDiffuser", "Interior")

    # stack light: base, green, ring, red, cap
    sx, sy, z = 105.0, 85.0, Z0 + H
    for name, r, h, mat in [("Base", 15, 12, "PlasticBlack"), ("Green", 14, 24, "LensGreen"),
                            ("Ring", 15, 2, "PlasticBlack"), ("Red", 14, 24, "LensRed"),
                            ("Cap", 15, 6, "PlasticBlack")]:
        part = cyl(r, h, (sx, sy, z), (0, 0, 1))
        if name in ("Base", "Cap"):
            part = part.faces(">Z").edges().fillet(2 if name == "Cap" else 1)
        p[f"StackLight{name}"] = (part, mat, "StatusLight")
        z += h

    # cable gland at the back
    p["CableGland"] = (cyl(7, 12, (80, D / 2, Z0 + 40), (0, 1, 0)).faces(">Y").edges().fillet(1.5),
                       "PlasticBlack", "Housing")

    # side control panel: plate, bezels, labels (Body) + plunger and key cylinder (own links)
    py, pz = PANEL_C
    p["PanelPlate"] = (to_side(rrect(70, 112, 4, 2).edges(">Z").fillet(0.6), py, pz, XS), "Aluminium", "Panel")
    for name, (_, y, z) in (("Button", BTN), ("Key", KEY)):
        bezel = cq.Workplane("XY").circle(14).circle(10.9).extrude(4).faces(">Z").edges().fillet(1.0)
        p[f"{name}Bezel"] = (to_side(bezel, y, z, XS + 2), "SteelSatin", "Panel")
    for txt, z in (("DOOR", BTN[2] + 21), ("RELEASE", KEY[2] - 21), ("0", KEY[2] + 18)):
        t = cq.Workplane("XY").text(txt, 5.0, 0.3, kind="bold", halign="center", valign="center")
        p[f"PanelText_{txt}"] = (to_side(t, py, z, XS + 2), "PlasticBlack", "Panel")
    t = cq.Workplane("XY").text("I", 5.0, 0.3, kind="bold", halign="center", valign="center")
    p["PanelText_I"] = (to_side(t, py + 18, KEY[2], XS + 2), "PlasticBlack", "Panel")

    cap = cq.Workplane("XY").circle(10.4).extrude(6).faces(">Z").edges().fillet(1.5)
    p["ButtonCap"] = (to_side(cap, BTN[1], BTN[2], BTN[0] + 1), "ButtonLens", "Plunger")
    face = (cq.Workplane("XY").circle(10).extrude(5).faces(">Z").edges().fillet(0.8)
            .faces(">Z").workplane().rect(1.6, 9).cutBlind(-2))
    p["KeyFace"] = (to_side(face, KEY[1], KEY[2], KEY[0]), "SteelSatin", "KeyCylinder")
    # key in LOCK: head plate vertical (in the X-Z plane), pulled out along +X
    blade = box(KEY[0] + 6, KEY[1], KEY[2], 4, 1.4, 8)
    head = box(KEY[0] + 17, KEY[1], KEY[2], 18, 3, 20).edges("|Y").fillet(4).cut(
        cyl(2.6, 10, (KEY[0] + 21, KEY[1] - 5, KEY[2]), (0, 1, 0)))
    p["KeyBlade"] = (blade, "Brass", "KeyCylinder")
    p["KeyHead"] = (head, "Brass", "KeyCylinder")

    # door (built in local XY then placed on the front); the edge slot receives the latch bolt
    door = rrect(DOOR_W, DOOR_H, 6, DOOR_T).faces(">Z").edges().fillet(2)
    window = rrect(172, 82, 5, DOOR_T)
    door = door.cut(window.translate((0, 6, 0)))
    pane = rrect(171.6, 81.6, 4.8, 6).translate((0, 6, 4))
    handle = box(100, 0, DOOR_T + 18, 12, 100, 8).edges().fillet(2)
    for yy in (-35, 35):
        handle = handle.union(box(100, yy, DOOR_T + 7.5, 10, 10, 15).edges("|Z").fillet(1.5))
    door_parts = {
        "DoorPanel": (door, "SteelBrushed"),
        "DoorWindow": (pane, "Polycarbonate"),
        "DoorHandle": (handle, "SteelSatin"),
    }
    for name, (wp, mat) in door_parts.items():
        p[name] = (to_front(wp, 0, DOOR_ZC, DOOR_BACK), mat, "Door")
    slot = box((SLOT_X + DOOR_W / 2 + 1) / 2, BOLT_Y, DOOR_ZC, DOOR_W / 2 + 1 - SLOT_X, 2 * BOLT_R + 1.2, 8)
    p["DoorPanel"] = (p["DoorPanel"][0].cut(slot), "SteelBrushed", "Door")
    for i, zc in enumerate([DOOR_ZC - 48, DOOR_ZC + 48]):
        leaf = box(hx + 10, DOOR_BACK - DOOR_T - 1.5, zc, 20, 3, 30).edges("|Y").fillet(1)
        p[f"DoorHingeLeaf{i}"] = (leaf, "SteelSatin", "Door")
    return p


def convex_colliders():
    """Exact convex colliders (CadQuery solids) per link."""
    return {"Shuttle": NEST.convex_colliders()}


def collision_boxes():
    """Collision proxies per link as (name, (x0, x1), (y0, y1), (z0, z1)) in mm, rest-free pose."""
    yb = YF + CD  # chamber back wall plane
    body = [
        ("Floor", (-W / 2, W / 2), (YF, D / 2), (0, CZ0)),
        ("Roof", (-W / 2, W / 2), (YF, D / 2), (CZ0 + CH, Z0 + H)),
        ("WallL", (-W / 2, -CW / 2), (YF, D / 2), (CZ0, CZ0 + CH)),
        ("WallR", (CW / 2, W / 2), (YF, D / 2), (CZ0, CZ0 + CH)),
        ("WallBack", (-CW / 2, CW / 2), (yb, D / 2), (CZ0, CZ0 + CH)),
        ("DriveUnit", (40, 90), (60, 98), (CZ0, CZ0 + 32)),
        ("LatchBody", (128.5, 141.5), (YF - 22, YF), (DOOR_ZC - 22, DOOR_ZC + 22)),
        ("StackLight", (90, 120), (70, 100), (Z0 + H, Z0 + H + 68)),
        ("SensorEmitter", (-CW / 2, -CW / 2 + 8), (BEAM_Y - 8, BEAM_Y + 8), (BEAM_Z - 7, BEAM_Z + 7)),
        ("SensorReceiver", (CW / 2 - 8, CW / 2), (BEAM_Y - 8, BEAM_Y + 8), (BEAM_Z - 7, BEAM_Z + 7)),
    ]
    dz0, dz1 = DOOR_ZC - DOOR_H / 2, DOOR_ZC + DOOR_H / 2
    dy = (DOOR_BACK - DOOR_T, DOOR_BACK)
    edge = DOOR_W / 2
    gap = 0.6
    door = [
        ("Panel", (-edge, SLOT_X), dy, (dz0, dz1)),
        ("EdgeUpper", (SLOT_X, edge), dy, (DOOR_ZC + 4, dz1)),
        ("EdgeLower", (SLOT_X, edge), dy, (dz0, DOOR_ZC - 4)),
        ("SlotLipFront", (SLOT_X, edge), (dy[0], BOLT_Y - BOLT_R - gap), (DOOR_ZC - 4, DOOR_ZC + 4)),
        ("SlotLipBack", (SLOT_X, edge), (BOLT_Y + BOLT_R + gap, dy[1]), (DOOR_ZC - 4, DOOR_ZC + 4)),
        ("Handle", (94, 106), (DOOR_BACK - DOOR_T - 22, DOOR_BACK - DOOR_T), (DOOR_ZC - 50, DOOR_ZC + 50)),
    ]
    bolt = [("Pin", (BOLT_X - BOLT_L, BOLT_X), (BOLT_Y - BOLT_R, BOLT_Y + BOLT_R), (DOOR_ZC - BOLT_R, DOOR_ZC + BOLT_R))]
    plunger = [("Cap", (BTN[0] + 1, BTN[0] + 7), (BTN[1] - 10.4, BTN[1] + 10.4), (BTN[2] - 10.4, BTN[2] + 10.4))]
    key = [("Cylinder", (KEY[0], KEY[0] + 5), (KEY[1] - 10, KEY[1] + 10), (KEY[2] - 10, KEY[2] + 10))]
    shuttle = NEST.collision_boxes()
    return {"Body": body, "Door": door, "LatchBolt": bolt, "Plunger": plunger, "KeyCylinder": key,
            "Shuttle": shuttle}


def new_layer(path, default_prim):
    return tc.new_layer(path, default_prim, "assets/h4/build_h4.py")


def link_path(name):
    return f"{ROOT}/{LINKS[name][0]}"


# ----------------------------------------------------------------------------------------------
# Layers
# ----------------------------------------------------------------------------------------------
def write_visual(parts):
    vis = new_layer(os.path.join(HERE, "h4_visual.usda"), "H4_Quarantine")
    UsdGeom.Xform.Define(vis, ROOT)
    mats = define_materials(vis, ROOT, sorted({m for _, m, _ in parts.values()} | {"AprilTag"}), tag_id=TAG_ID)
    UsdGeom.Scope.Define(vis, f"{ROOT}/Controls")
    UsdGeom.Xform.Define(vis, f"{ROOT}/Controls/DoorButton")
    UsdGeom.Xform.Define(vis, f"{ROOT}/Controls/KeySwitch")
    for name, (_, _, rest) in LINKS.items():
        xf = UsdGeom.Xform.Define(vis, link_path(name))
        xf.AddTranslateOp().Set(Gf.Vec3d(*(np.array(rest, dtype=float) * MM)))
        if name == "Door":
            xf.AddRotateZOp(opSuffix="hinge").Set(0.0)  # static/visual posing only; PhysX drives the joint
        if name == "KeyCylinder":
            xf.AddRotateXOp(opSuffix="key").Set(0.0)
    tri_total = 0
    for name, (wp, mat, group) in parts.items():
        link = GROUP_LINK[group]
        sub = f"/{group}" if link == "Body" else ""
        mesh, ntri = write_mesh(vis, f"{link_path(link)}/Visual{sub}/{name}", wp, LINKS[link][1])
        bind(mesh.GetPrim(), mats[mat])
        tri_total += ntri
    # AprilTag quad (UV-mapped, image top toward +Y) on the tag plate, in Shuttle link coordinates
    tx, ty, tz, hs = TAG_C[0] * MM, TAG_C[1] * MM, (TRAY_Z1 + 0.62) * MM, TAG_CODE / 2 * MM  # link origin z = 0
    tagm = UsdGeom.Mesh.Define(vis, f"{link_path('Shuttle')}/Visual/AprilTag")
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
    # the LED strip is a real area light so the chamber (and the plate behind the window) is lit
    led = UsdLux.RectLight.Define(vis, f"{link_path('Body')}/Visual/Interior/LedLight")
    led.CreateWidthAttr(0.176)
    led.CreateHeightAttr(0.006)
    led.CreateIntensityAttr(40000.0)
    led.CreateColorTemperatureAttr(5000.0)
    led.CreateEnableColorTemperatureAttr(True)
    led.AddTranslateOp().Set(Gf.Vec3d(0, (YF + 30) * MM, (CZ0 + CH - 2.2) * MM))  # emits along -Z (down)
    vis.GetRootLayer().Save()
    return tri_total


MASS_KG = {"Body": 18.0, "Door": 1.4, "LatchBolt": 0.02, "Plunger": 0.02, "KeyCylinder": 0.03, "Shuttle": 0.9}


def write_physics():
    phy = new_layer(os.path.join(HERE, "h4_physics.usda"), "H4_Quarantine")
    cmat = define_contact_materials(phy, ROOT)
    n = 0
    for link, boxes in collision_boxes().items():
        lp = phy.OverridePrim(link_path(link))
        UsdPhysics.RigidBodyAPI.Apply(lp)
        UsdPhysics.MassAPI.Apply(lp).CreateMassAttr(MASS_KG[link])
        col = UsdGeom.Xform.Define(phy, f"{link_path(link)}/Collision")
        col.CreatePurposeAttr(UsdGeom.Tokens.guide)
        small = link in ("Door", "LatchBolt", "Plunger", "KeyCylinder", "Shuttle")
        for name, xs, ys, zs in boxes:
            mat = cmat["Peek"] if name.startswith("Nest") else cmat["Steel"]
            add_box_collider(phy, col.GetPath(), name, xs, ys, zs, LINKS[link][1], mat,
                             offsets=(0.001, 0.0) if small else None)
            n += 1
        for name, solid in convex_colliders().get(link, []):
            add_convex_collider(phy, f"{col.GetPath()}/{name}", solid, LINKS[link][1], cmat["Peek"])
            n += 1
    phy.GetRootLayer().Save()
    return n


def write_articulation():
    art = new_layer(os.path.join(HERE, "h4_articulation.usda"), "H4_Quarantine")
    root = art.GetPrimAtPath(ROOT)
    UsdPhysics.ArticulationRootAPI.Apply(root)
    root.AddAppliedSchema("PhysxArticulationAPI")
    root.CreateAttribute("physxArticulation:enabledSelfCollisions", B).Set(True)  # door vs bolt must collide
    root.CreateAttribute("physxArticulation:solverPositionIterationCount", Sdf.ValueTypeNames.Int).Set(32)
    root.CreateAttribute("physxArticulation:solverVelocityIterationCount", Sdf.ValueTypeNames.Int).Set(4)
    # never sleep: when an idle H4 was woken by a plate contact, PhysX restored stale initial joint
    # state (door/shuttle snapped to the authored pose; found in test_h4_robot.py, 2026-10-15)
    root.CreateAttribute("physxArticulation:sleepThreshold", F).Set(0.0)
    body = link_path("Body")
    UsdGeom.Scope.Define(art, f"{ROOT}/Joints")
    _joint(art, UsdPhysics.FixedJoint, f"{ROOT}/Joints/RootJoint", None, body, Gf.Vec3f(0), Gf.Vec3f(0))

    # door: joint frames flipped 180 deg about X so +angle = opening (rotation toward -Y)
    flip = Gf.Quatf(0, 1, 0, 0)
    hinge = _joint(art, UsdPhysics.RevoluteJoint, f"{ROOT}/Joints/DoorHinge", body, link_path("Door"),
                   mm3((HINGE[0], HINGE[1], DOOR_ZC)), mm3((0, 0, DOOR_ZC)), "Z", (0.0, DOOR_OPEN_MAX_DEG), flip)
    _drive(hinge, "angular", stiffness=0.5, damping=0.05, max_force=3.0, target=0.0)  # N*m/deg, N*m*s/deg, N*m

    latch = _joint(art, UsdPhysics.PrismaticJoint, f"{ROOT}/Joints/LatchSlide", body, link_path("LatchBolt"),
                   mm3((BOLT_X, BOLT_Y, DOOR_ZC)), Gf.Vec3f(0), "X", (0.0, BOLT_TRAVEL * MM))
    _drive(latch, "linear", stiffness=2000.0, damping=20.0, max_force=20.0, target=BOLT_TRAVEL * MM)  # rest: retracted

    # Cell 01 pushbutton convention (author_pushbutton.py): joint next to the plunger, owner carries control:*
    btn = _joint(art, UsdPhysics.PrismaticJoint, f"{ROOT}/Controls/DoorButton/button_joint", body,
                 link_path("Plunger"), mm3(BTN), Gf.Vec3f(0), "X", (-BTN_TRAVEL * MM, 0.0))
    _drive(btn, "linear", stiffness=1800.0, damping=8.0, max_force=50.0, target=0.0)
    owner = art.OverridePrim(f"{ROOT}/Controls/DoorButton")
    owner.CreateAttribute("control:pressed", B, custom=True).Set(False)
    owner.CreateAttribute("control:actuationThreshold_m", Sdf.ValueTypeNames.Double, custom=True).Set(0.002)
    owner.CreateAttribute("control:function", Sdf.ValueTypeNames.String, custom=True).Set(
        "door open/close request; ignored and logged while locked")

    # shuttle: frames flipped 180 deg about Z so +q presents the nest (moves toward -Y)
    shuttle = _joint(art, UsdPhysics.PrismaticJoint, f"{ROOT}/Joints/ShuttleSlide", body, link_path("Shuttle"),
                     mm3((0, NEST_Y_RET, 0)), Gf.Vec3f(0), "Y", (0.0, SHUTTLE_TRAVEL * MM), Gf.Quatf(0, 0, 0, 1))
    _drive(shuttle, "linear", stiffness=2000.0, damping=150.0, max_force=40.0, target=0.0)

    key = _joint(art, UsdPhysics.RevoluteJoint, f"{ROOT}/Controls/KeySwitch/key_joint", body,
                 link_path("KeyCylinder"), mm3(KEY), Gf.Vec3f(0), "X", (0.0, 90.0))
    _drive(key, "angular", stiffness=0.005, damping=0.0005, max_force=0.5, target=0.0)
    owner = art.OverridePrim(f"{ROOT}/Controls/KeySwitch")
    owner.CreateAttribute("control:position", Sdf.ValueTypeNames.String, custom=True).Set("LOCK")
    owner.CreateAttribute("control:releaseAngle_deg", Sdf.ValueTypeNames.Double, custom=True).Set(80.0)
    owner.CreateAttribute("control:function", Sdf.ValueTypeNames.String, custom=True).Set(
        "physical half of authorised release: RELEASE position required together with a software authorisation")
    art.GetRootLayer().Save()


def write_semantics():
    sem = new_layer(os.path.join(HERE, "h4_semantics.usda"), "H4_Quarantine")
    rp = sem.GetPrimAtPath(ROOT)
    Usd.ModelAPI(rp).SetKind(Kind.Tokens.component)
    S, Bo, St, Db = (Sdf.ValueTypeNames.String, Sdf.ValueTypeNames.Bool, Sdf.ValueTypeNames.StringArray,
                     Sdf.ValueTypeNames.Double)
    for k, t, v in [
        ("sdt:componentId", S, "H4"),
        ("sdt:canonicalName", S, "H4 Quarantine Station"),
        ("sdt:contract", S, "sdt/components/H4_Quarantine.yaml"),
        ("sdt:capabilities", St, ["isolate_sample", "retain_invalid_run", "prevent_reentry", "release_by_authorization"]),
        ("sdt:bindingStatus", S, "articulated_v1"),
        ("sdt:designBasis", S, "project-owned parametric design (option A); not a manufacturer asset"),
        ("state:occupied", Bo, False),
        ("state:locked", Bo, False),
        ("state:sample_id", S, ""),
        ("state:reason", S, ""),
        ("state:release_authorization", S, ""),
        ("state:mode", S, "READY"),
        ("state:fault", S, ""),
        ("state:door_angle_deg", Db, 0.0),
    ]:
        rp.CreateAttribute(k, t, custom=True).Set(v)

    def frame(name, pos, role):
        f = UsdGeom.Xform.Define(sem, f"{ROOT}/{name}")
        f.AddTranslateOp().Set(Gf.Vec3d(*(np.array(pos, dtype=float) * MM)))
        f.GetPrim().CreateAttribute("sdt:frameRole", S, custom=True).Set(role)
        return f

    frame("quarantine_nest", (NEST_C[0], NEST_C[1], NEST_TOP),
          "Stowed SBS plate seat (shuttle retracted, isolation position): footprint centre on the seating "
          "plane, +X along plate long axis, A1 corner at (-X,+Y), +Z up")
    tn = frame("transfer_nest", (0, NEST_Y_EXT, SEAT_Z),
               "Presented SBS plate seat (shuttle extended, door open): robot place/pick target. "
               "Same axes as quarantine_nest.")
    for k, t, v in [
        ("sdt:approach", S, "top-down; gripper fingers on the plate LONG sides (pinch along +-Y), "
                            "finger reliefs +-25 mm about x=0, 5 mm deep"),
        ("sdt:captureRange_mm", Db, GUIDE_CL + GUIDE_LEAD),
        ("sdt:seatClearance_mm", Db, GUIDE_CL),
        ("sdt:orientationKey", S, "A1 key at (-X,+Y): a plate rotated 180 deg will not seat (seat sensors)"),
        ("sdt:registration", S, "Shuttle/registration_tag (AprilTag 36h11 #%d, %g mm) and Shuttle/registration_datum"
                                % (TAG_ID, TAG_CODE)),
    ]:
        tn.GetPrim().CreateAttribute(k, t, custom=True).Set(v)

    tag = frame("Shuttle/registration_tag", (TAG_C[0], TAG_C[1], TRAY_Z1 + 0.62),
                "AprilTag 36h11 centre on the tag surface, axes = nest axes (tag image +Y = nest +Y)")
    tag.GetPrim().CreateAttribute("sdt:tagFamily", S, custom=True).Set("tag36h11")
    tag.GetPrim().CreateAttribute("sdt:tagId", Sdf.ValueTypeNames.Int, custom=True).Set(TAG_ID)
    tag.GetPrim().CreateAttribute("sdt:tagSize_mm", Db, custom=True).Set(TAG_CODE)
    frame("Shuttle/registration_datum", (DATUM_C[0], DATUM_C[1], TRAY_Z1 + 8.0), "datum pin tip (touch-off point)")
    frame("Shuttle/nest_seat", (0, 0, SEAT_Z), "live nest seat (moves with the shuttle)")
    for i, (x, y) in enumerate(SEAT_SENSORS):
        frame(f"Shuttle/seat_sensor_{i}", (x, y, SEAT_Z - 1.0), "flush seat sensor window, looks +Z")
    df = frame("door_frame", (HINGE[0], HINGE[1], DOOR_ZC),
               "Door hinge axis at door mid-height; joint DoorHinge, +angle opens toward -Y")
    df.GetPrim().CreateAttribute("sdt:doorOpenMaxDeg", Db, custom=True).Set(DOOR_OPEN_MAX_DEG)
    frame("door_button_frame", (BTN[0] + 7, BTN[1], BTN[2]), "DOOR pushbutton face centre; press along -X")
    frame("key_switch_frame", (KEY[0] + 5, KEY[1], KEY[2]), "RELEASE key switch face centre; turn about +X, 0=LOCK 90=RELEASE")
    for name in ("beam_emitter", "beam_receiver"):
        side = -1 if name == "beam_emitter" else 1
        frame(name, (side * (CW / 2 - 8.8), BEAM_Y, BEAM_Z), "plate-presence through-beam end point (lens face)")
    sem.GetRootLayer().Save()


def write_plate(plate, medium):
    os.makedirs(LABWARE, exist_ok=True)
    pst = new_layer(os.path.join(LABWARE, "plate_sbs96.usda"), "Plate_SBS96")
    UsdGeom.Xform.Define(pst, "/Plate_SBS96")
    pm = define_materials(pst, "/Plate_SBS96", ["Polystyrene", "CultureMedium"])
    m1, n1 = write_mesh(pst, "/Plate_SBS96/Visual/Body", plate)
    m2, n2 = write_mesh(pst, "/Plate_SBS96/Visual/Medium", medium)
    bind(m1.GetPrim(), pm["Polystyrene"])
    bind(m2.GetPrim(), pm["CultureMedium"])
    root = pst.GetPrimAtPath("/Plate_SBS96")
    root.CreateAttribute("sdt:labwareClass", Sdf.ValueTypeNames.String, custom=True).Set("SBS96WellPlate")
    UsdPhysics.RigidBodyAPI.Apply(root)
    UsdPhysics.MassAPI.Apply(root).CreateMassAttr(0.07)
    cm = define_contact_materials(pst, "/Plate_SBS96")["Polystyrene"]
    col = UsdGeom.Xform.Define(pst, "/Plate_SBS96/Collision")
    col.CreatePurposeAttr(UsdGeom.Tokens.guide)
    w, d, h = SBS
    c = 4.0  # A1 corner chamfer leg, so the A1 key in the nest is physically effective
    prism = (cq.Workplane("XY").polyline([(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2 + c, d / 2),
                                          (-w / 2, d / 2 - c)]).close().extrude(h))
    add_convex_collider(pst, "/Plate_SBS96/Collision/Prism", prism, (0, 0, 0), cm)
    pst.GetRootLayer().Save()
    return n1 + n2


def main():
    os.makedirs(BUILD, exist_ok=True)
    tc.make_textures(TEX, [TAG_ID])
    parts = build_cad()

    asm = cq.Assembly(name="H4_Quarantine")
    for name, (wp, _, _) in parts.items():
        asm.add(wp, name=name)
    asm.export(os.path.join(BUILD, "h4.step"))

    tri_total = write_visual(parts)
    n_col = write_physics()
    write_articulation()
    write_semantics()
    asmb = new_layer(os.path.join(HERE, "h4.usda"), "H4_Quarantine")
    asmb.GetRootLayer().subLayerPaths = ["./h4_semantics.usda", "./h4_articulation.usda",
                                         "./h4_physics.usda", "./h4_visual.usda"]
    asmb.GetRootLayer().Save()

    plate, medium = build_plate()
    cq.Assembly(name="Plate").add(plate, name="Body").add(medium, name="Medium").export(
        os.path.join(BUILD, "plate_sbs96.step"))
    n_plate = write_plate(plate, medium)

    print(f"H4: {len(parts)} parts, {tri_total} triangles, {n_col} collision boxes; plate: {n_plate} triangles")
    print("wrote", ", ".join(f for f in sorted(os.listdir(HERE)) if f.endswith(".usda")), "+ build/*.step")


if __name__ == "__main__":
    main()
