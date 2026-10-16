"""Build the L12 Automated Liquid-Handling Station asset: parametric CAD -> STEP + layered, articulated OpenUSD.

Run with the CAD environment:  env_cad/bin/python assets/l12/build_l12.py

Cell 01 baseline: "Hamilton ZEUS LT OEM module integrated in custom Cell01 station". This is a project-owned
station in that spirit, not a Hamilton model: one ZEUS-class pipetting channel on an X/Y gantry over a deck.

  * deck (0.92 x 0.46 m) on the central bench: plate nest (shared static SBS nest, seat 52 mm = 0.972 m, served
    top-down by R02), SBS tip rack position, reagent tube block (4 positions), tip waste bin
  * gantry: GantryX (carriage on the back rail), GantryY (carriage on the cantilevered arm), ChannelZ (the
    channel, q <= 0 lowers it). The tip-mount cone has no collider; tips are picked by a surface gripper on a
    collider-free TipMount body, added at runtime by twin/l12_rig.py (as R02's coupler)
  * sensors: plate barcode reader at the nest, a barcode reader per reagent position, nest seat sensors; the
    channel's tip-presence ray, pressure and liquid-level detection are modelled in twin/l12_liquid.py
  * tips: assets/l12/tip.usda, a 50 uL-class conductive tip as a free rigid body (collar collider), loaded into
    the rack at runtime (consumables)
"""

import os
import sys

import cadquery as cq
import numpy as np
from pxr import Gf, Kind, Sdf, Usd, UsdGeom, UsdPhysics

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from common import twin_cad as tc  # noqa: E402
from common.static_nest import StaticNest  # noqa: E402
from common.twin_cad import (B, F, MM, SBS, _drive, _joint, add_box_collider, bind, box, cyl, define_contact_materials,  # noqa: E402
                             define_materials, mm3, rrect, to_front, write_mesh)

NAME, PREFIX = "L12_LiquidHandler", "l12"
ROOT = f"/{NAME}"
GENERATOR = "assets/l12/build_l12.py"
DECK = dict(x=(-460.0, 460.0), y=(-230.0, 230.0), z=(0.0, 15.0))
NEST = StaticNest(seat_z=52.0, tag_id=12, cx=0.0, cy=90.0, prefix="Nest")
TIP_RACK = dict(c=(-250.0, 90.0), top=65.0)            # SBS-footprint rack block, tips rest on its top
REAGENT = dict(c=(250.0, 90.0), pitch=20.0, n=4, block_top=45.0, tube_bottom=17.0, tube_top=57.0, r_out=5.4,
               r_in=4.5)
WASTE = dict(c=(400.0, -120.0), size=(90.0, 120.0), top=120.0)
READER = (-SBS[0] / 2 - 30.0, NEST.cy, NEST.seat_z + 10.0)   # plate reader lens point, looks +X
CH_X = 32.0                                            # channel axis offset from the gantry X position
CONE_END_Z = 200.0                                     # tip-mount cone end with ChannelZ = 0
TIP = dict(length=50.0, collar_h=8.0, collar_r=3.6, cone_r0=2.8, cone_r1=0.45, insert=8.0)
X_RANGE, Y_RANGE, Z_RANGE = (-430.0, 400.0), (-150.0, 160.0), (-150.0, 0.0)
PARK = (-420.0, -100.0, 0.0)
LINKS = {
    "Body": ("Body", (0, 0, 0), (0, 0, 0)),
    "GantryX": ("GantryX", (0, 0, 0), (0, 0, 0)),
    "GantryY": ("GantryX/GantryY", (0, 0, 0), (0, 0, 0)),
    "ChannelZ": ("GantryX/GantryY/ChannelZ", (CH_X, 0, CONE_END_Z), (CH_X, 0, CONE_END_Z)),
}
MASSES = {"Body": 25.0, "GantryX": 3.0, "GantryY": 1.2, "ChannelZ": 0.8}
EXTRA_PBR = {
    "PowderWhite": ((0.86, 0.87, 0.87), 0.42, 0.0, {}),
    "LensAmber": ((0.6, 0.35, 0.02), 0.15, 0.0, {"emissive": ((1.0, 0.55, 0.05), 0.0)}),
    "ZeusBlue": ((0.10, 0.25, 0.55), 0.35, 0.2, {}),
    "TipPolypropylene": ((0.92, 0.92, 0.90), 0.35, 0.0, {}),
    "TipConductive": ((0.06, 0.06, 0.065), 0.4, 0.0, {}),
}


def link_path(name):
    return f"{ROOT}/{LINKS[name][0]}"


def tip_offsets():
    """SBS 96 positions relative to the rack centre (A1 at -X/+Y)."""
    return {f"{'ABCDEFGH'[r]}{c + 1:02d}": (-49.5 + 9 * c, 31.5 - 9 * r) for r in range(8) for c in range(12)}


def reagent_positions():
    cx, cy = REAGENT["c"]
    return {k + 1: (cx + (k - (REAGENT["n"] - 1) / 2) * REAGENT["pitch"], cy) for k in range(REAGENT["n"])}


def build_cad():
    p = {}
    D = DECK
    p["DeckPlate"] = (box(0, 0, sum(D["z"]) / 2, D["x"][1] - D["x"][0], D["y"][1] - D["y"][0], D["z"][1] - D["z"][0])
                      .edges("|Z").fillet(10).edges(">Z").fillet(1.5), "AnodizedGraphite", "Body")
    for name, (wp, mat) in NEST.parts().items():
        p[name] = (wp, mat, "Body")
    rx, ry = TIP_RACK["c"]
    rack = box(rx, ry, (D["z"][1] + TIP_RACK["top"]) / 2, SBS[0], SBS[1], TIP_RACK["top"] - D["z"][1]).edges("|Z").fillet(3)
    rack = rack.faces(">Z").workplane().pushPoints([(rx + u, ry + v) for u, v in tip_offsets().values()]).hole(5.8, 30)
    p["TipRack"] = (rack, "ZeusBlue", "Body")
    p["TipRackLabel"] = (to_front(rrect(60, 10, 2, 0.6), rx, D["z"][1] + 25, ry - SBS[1] / 2), "LabelWhite", "Body")
    cx, cy = REAGENT["c"]
    blk = box(cx, cy, (D["z"][1] + REAGENT["block_top"]) / 2, REAGENT["pitch"] * REAGENT["n"] + 20, 40,
              REAGENT["block_top"] - D["z"][1]).edges("|Z").fillet(3)
    for x, y in reagent_positions().values():
        blk = blk.cut(cyl(REAGENT["r_out"] + 0.3, 40, (x, y, REAGENT["tube_bottom"]), (0, 0, 1)))
    p["ReagentBlock"] = (blk, "Aluminium", "Body")
    for k, (x, y) in reagent_positions().items():
        p[f"ReagentReader{k}"] = (box(x, cy - 32, REAGENT["block_top"] + 2, 10, 12, 12).edges().fillet(1), "PlasticBlack",
                                  "Body")
        p[f"ReagentReaderWindow{k}"] = (box(x, cy - 25.8, REAGENT["block_top"] + 2, 6, 0.4, 4), "SensorLens", "Body")
    wx, wy = WASTE["c"]
    sx, sy = WASTE["size"]
    bin_ = box(wx, wy, (D["z"][1] + WASTE["top"]) / 2, sx, sy, WASTE["top"] - D["z"][1]).edges("|Z").fillet(4)
    bin_ = bin_.cut(box(wx, wy, (D["z"][1] + WASTE["top"]) / 2 + 3, sx - 6, sy - 6, WASTE["top"] - D["z"][1]))
    p["WasteBin"] = (bin_, "PlasticBlack", "Body")
    p["WasteLabel"] = (to_front(rrect(50, 10, 2, 0.6), wx, WASTE["top"] - 20, wy - sy / 2), "LabelYellow", "Body")
    rx_, ry_, rz_ = READER
    p["PlateReader"] = (box(rx_ - 9, ry_, rz_, 18, 30, 14).edges().fillet(1.5), "PlasticBlack", "Body")
    p["PlateReaderWindow"] = (box(rx_ + 0.25, ry_, rz_, 0.5, 18, 7), "SensorLens", "Body")
    p["PlateReaderPost"] = (box(rx_ - 9, ry_, (D["z"][1] + rz_ - 7) / 2, 10, 10, rz_ - 7 - D["z"][1]), "Aluminium", "Body")
    # gantry: back rail (body), X carriage + column + cantilever arm, Y carriage, ZEUS-class channel
    p["XRail"] = (box(0, -200, (D["z"][1] + 90) / 2, D["x"][1] - D["x"][0], 30, 90 - D["z"][1]).edges("|X").fillet(2),
                  "Aluminium", "Body")
    p["XRailCover"] = (box(0, -200, 92, D["x"][1] - D["x"][0] - 10, 34, 4), "PowderWhite", "Body")
    p["XCarriage"] = (box(0, -200, 107, 80, 44, 26).edges("|Z").fillet(3), "PowderWhite", "GantryX")
    p["Column"] = (box(0, -200, 182, 30, 30, 124).edges("|Z").fillet(2), "PowderWhite", "GantryX")
    p["YArm"] = (box(0, -10, 235, 24, 400, 20).edges("|Y").fillet(2), "Aluminium", "GantryX")
    p["YCarriage"] = (box(CH_X - 5, 0, 235, 34, 50, 34).edges("|Z").fillet(3), "PowderWhite", "GantryY")
    z0 = CONE_END_Z
    p["ChannelBody"] = (box(CH_X, 0, z0 + 10 + 80, 30, 40, 160).edges("|Z").fillet(4), "ZeusBlue", "ChannelZ")
    p["ChannelLabel"] = (to_front(rrect(22, 60, 2, 0.5), CH_X, z0 + 120, -20.2), "LabelWhite", "ChannelZ")
    p["ChannelNose"] = (cyl(6, 10, (CH_X, 0, z0 + 2), (0, 0, 1)), "SteelSatin", "ChannelZ")
    p["MountCone"] = (cq.Workplane("XY").add(cq.Solid.makeCone(2.2, 2.9, 4.0, cq.Vector(CH_X, 0, z0 - 2.0))),
                      "SteelSatin", "ChannelZ")
    for i, lens in enumerate(("LensGreen", "LensAmber", "LensRed")):
        p[f"StatusLamp{i}"] = (to_front(cyl(4, 2, (0, 0, 0), (0, 0, 1)), -440 + 14 * i, 60, -230), lens, "Body")
    return p


def tip_solid():
    """Tip in its own frame: z = 0 at the collar top (mount opening), cone downward; the mount cone enters 8 mm."""
    T = TIP
    collar = cyl(T["collar_r"], T["collar_h"], (0, 0, -T["collar_h"]), (0, 0, 1))
    cone = cq.Workplane("XY").add(cq.Solid.makeCone(T["cone_r1"], T["cone_r0"], T["length"] - T["collar_h"],
                                                    cq.Vector(0, 0, -T["length"])))
    return collar.union(cone).faces(">Z").shell(-0.4)


def collision_boxes():
    D = DECK
    rx, ry = TIP_RACK["c"]
    cx, cy = REAGENT["c"]
    wx, wy = WASTE["c"]
    sx, sy = WASTE["size"]
    body = [("DeckPlate", D["x"], D["y"], D["z"]),
            ("TipRack", (rx - SBS[0] / 2, rx + SBS[0] / 2), (ry - SBS[1] / 2, ry + SBS[1] / 2), (D["z"][1], TIP_RACK["top"])),
            ("ReagentBlock", (cx - 50, cx + 50), (cy - 20, cy + 20), (D["z"][1], REAGENT["block_top"])),
            ("WasteFloor", (wx - sx / 2, wx + sx / 2), (wy - sy / 2, wy + sy / 2), (D["z"][1], D["z"][1] + 3)),
            ("WasteWallW", (wx - sx / 2, wx - sx / 2 + 3), (wy - sy / 2, wy + sy / 2), (D["z"][1], WASTE["top"])),
            ("WasteWallE", (wx + sx / 2 - 3, wx + sx / 2), (wy - sy / 2, wy + sy / 2), (D["z"][1], WASTE["top"])),
            ("WasteWallS", (wx - sx / 2, wx + sx / 2), (wy - sy / 2, wy - sy / 2 + 3), (D["z"][1], WASTE["top"])),
            ("WasteWallN", (wx - sx / 2, wx + sx / 2), (wy + sy / 2 - 3, wy + sy / 2), (D["z"][1], WASTE["top"])),
            ("PlateReader", (READER[0] - 18, READER[0]), (READER[1] - 15, READER[1] + 15), (READER[2] - 7, READER[2] + 7)),
            ("XRail", D["x"], (-215, -185), (D["z"][1], 94))]
    for k, (x, y) in reagent_positions().items():
        body.append((f"ReagentReader{k}", (x - 5, x + 5), (cy - 38, cy - 26), (REAGENT["block_top"] - 4, REAGENT["block_top"] + 8)))
    gx = [("XCarriage", (-40, 40), (-222, -178), (94, 120)), ("Column", (-15, 15), (-215, -185), (120, 244)),
          ("YArm", (-12, 12), (-210, 190), (225, 245))]
    gy = [("YCarriage", (CH_X - 22, CH_X + 12), (-25, 25), (218, 252))]
    ch = [("ChannelBody", (CH_X - 15, CH_X + 15), (-20, 20), (CONE_END_Z + 10, CONE_END_Z + 170))]
    return {"Body": body, "GantryX": gx, "GantryY": gy, "ChannelZ": ch}


def new_layer(name):
    return tc.new_layer(os.path.join(HERE, f"{PREFIX}_{name}.usda" if name else f"{PREFIX}.usda"), NAME, GENERATOR)


def write_visual(parts):
    tc.PBR.update(EXTRA_PBR)
    vis = new_layer("visual")
    UsdGeom.Xform.Define(vis, ROOT)
    mats = define_materials(vis, ROOT, sorted({m for _, m, _ in parts.values()} | {"AprilTag"}), tag_id=12)
    for name, (_, _, rest) in LINKS.items():
        xf = UsdGeom.Xform.Define(vis, link_path(name))
        parent = {"GantryY": "GantryX", "ChannelZ": "GantryY"}.get(name)
        local = np.array(rest, float) - (np.array(LINKS[parent][2], float) if parent else 0)
        xf.AddTranslateOp().Set(Gf.Vec3d(*(local * MM)))
        UsdGeom.Xform.Define(vis, f"{link_path(name)}/Visual")
    tri = 0
    for name, (wp, mat, link) in parts.items():
        m, n = write_mesh(vis, f"{link_path(link)}/Visual/{name}", wp, LINKS[link][1])
        bind(m.GetPrim(), mats[mat])
        tri += n
    tx, ty, tz, hs = NEST.tag()
    q = UsdGeom.Mesh.Define(vis, f"{link_path('Body')}/Visual/NestAprilTag")
    q.CreatePointsAttr([Gf.Vec3f((tx - hs) * MM, (ty - hs) * MM, tz * MM), Gf.Vec3f((tx + hs) * MM, (ty - hs) * MM, tz * MM),
                        Gf.Vec3f((tx + hs) * MM, (ty + hs) * MM, tz * MM), Gf.Vec3f((tx - hs) * MM, (ty + hs) * MM, tz * MM)])
    q.CreateFaceVertexCountsAttr([4])
    q.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    q.CreateNormalsAttr([Gf.Vec3f(0, 0, 1)] * 4)
    q.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
    UsdGeom.PrimvarsAPI(q).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex).Set(
        [Gf.Vec2f(0, 0), Gf.Vec2f(1, 0), Gf.Vec2f(1, 1), Gf.Vec2f(0, 1)])
    bind(q.GetPrim(), mats["AprilTag"])
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
        origin = np.array(LINKS[link][1], float)
        for name, xs, ys, zs in boxes:
            add_box_collider(phy, col.GetPath(), name, xs, ys, zs, origin, cmat["Steel"],
                             offsets=(0.0005, 0.0) if link != "Body" else None)
            n += 1
        if link == "Body":
            n += NEST.add_colliders(phy, col.GetPath(), cmat)
    phy.GetRootLayer().Save()
    return n


def write_articulation():
    art = new_layer("articulation")
    root = art.GetPrimAtPath(ROOT)
    UsdPhysics.ArticulationRootAPI.Apply(root)
    root.AddAppliedSchema("PhysxArticulationAPI")
    root.CreateAttribute("physxArticulation:enabledSelfCollisions", B).Set(False)
    root.CreateAttribute("physxArticulation:solverPositionIterationCount", Sdf.ValueTypeNames.Int).Set(32)
    root.CreateAttribute("physxArticulation:solverVelocityIterationCount", Sdf.ValueTypeNames.Int).Set(4)
    root.CreateAttribute("physxArticulation:sleepThreshold", F).Set(0.0)
    J = f"{ROOT}/Joints"
    UsdGeom.Scope.Define(art, J)
    _joint(art, UsdPhysics.FixedJoint, f"{J}/RootJoint", None, link_path("Body"), Gf.Vec3f(0), Gf.Vec3f(0))
    jx = _joint(art, UsdPhysics.PrismaticJoint, f"{J}/GantryXSlide", link_path("Body"), link_path("GantryX"),
                Gf.Vec3f(0), Gf.Vec3f(0), "X", (X_RANGE[0] * MM, X_RANGE[1] * MM))
    _drive(jx, "linear", stiffness=200000.0, damping=2000.0, max_force=500.0, target=PARK[0] * MM)
    jy = _joint(art, UsdPhysics.PrismaticJoint, f"{J}/GantryYSlide", link_path("GantryX"), link_path("GantryY"),
                Gf.Vec3f(0), Gf.Vec3f(0), "Y", (Y_RANGE[0] * MM, Y_RANGE[1] * MM))
    _drive(jy, "linear", stiffness=200000.0, damping=1200.0, max_force=300.0, target=PARK[1] * MM)
    jz = _joint(art, UsdPhysics.PrismaticJoint, f"{J}/ChannelZSlide", link_path("GantryY"), link_path("ChannelZ"),
                mm3((CH_X, 0, CONE_END_Z)), Gf.Vec3f(0), "Z", (Z_RANGE[0] * MM, Z_RANGE[1] * MM))
    _drive(jz, "linear", stiffness=500000.0, damping=2000.0, max_force=300.0, target=0.0)
    for jn, val in (("GantryXSlide", PARK[0] * MM), ("GantryYSlide", PARK[1] * MM)):   # start parked (raw joint
        jp = art.GetPrimAtPath(f"{J}/{jn}")                                            # state: no PhysxSchema here)
        jp.AddAppliedSchema("PhysicsJointStateAPI:linear")
        jp.CreateAttribute("state:linear:physics:position", F).Set(val)
    art.GetRootLayer().Save()


def write_semantics():
    sem = new_layer("semantics")
    rp = sem.GetPrimAtPath(ROOT)
    Usd.ModelAPI(rp).SetKind(Kind.Tokens.component)
    S, St, Db, Bo = (Sdf.ValueTypeNames.String, Sdf.ValueTypeNames.StringArray, Sdf.ValueTypeNames.Double,
                     Sdf.ValueTypeNames.Bool)
    for k, t, v in (
            ("sdt:componentId", S, "L12"), ("sdt:canonicalName", S, "L12 Automated Liquid-Handling Station"),
            ("sdt:contract", S, "sdt/components/L12_LiquidHandler.yaml"),
            ("sdt:capabilities", St, ["pick_tip", "detect_liquid_surface", "aspirate", "dispense", "mix", "dose_well",
                                      "eject_tip"]),
            ("sdt:bindingStatus", S, "articulated_v1"),
            ("sdt:designBasis", S, "project-owned single-channel gantry liquid handler in the spirit of the Cell 01 "
                                   "baseline (ZEUS LT OEM module); not a Hamilton model"),
            ("state:tip_present", Bo, False), ("state:tip_id", S, ""), ("state:aspirated_volume_uL", Db, 0.0),
            ("state:reagent_id", S, ""), ("state:plate_id", S, ""), ("state:target_well", S, ""),
            ("state:fault", S, ""), ("state:mode", S, "READY")):
        rp.CreateAttribute(k, t, custom=True).Set(v)
    geo = {"chX_mm": CH_X, "coneEndZ_mm": CONE_END_Z, "tipLength_mm": TIP["length"], "tipInsert_mm": TIP["insert"],
           "parkX_mm": PARK[0], "parkY_mm": PARK[1], "reagentInnerR_mm": REAGENT["r_in"],
           "reagentBottomZ_mm": REAGENT["tube_bottom"] + 1.0, "wellBottom_mm": NEST.seat_z + SBS[2] - 10.9}
    for k, v in geo.items():
        rp.CreateAttribute(f"lh:{k}", Db, custom=True).Set(float(v))

    def frame(name, pos, role):
        f = UsdGeom.Xform.Define(sem, f"{ROOT}/{name}")
        f.AddTranslateOp().Set(Gf.Vec3d(*(np.array(pos, float) * MM)))
        f.GetPrim().CreateAttribute("sdt:frameRole", S, custom=True).Set(role)
        return f

    frame("deck_frame", (0, 0, DECK["z"][1]), "deck top centre; +X along the deck, +Y toward R02's rail")
    pn = frame("plate_nest", (NEST.cx, NEST.cy, NEST.seat_z), "SBS plate seat (R02 place/pick target); A1 at (-X,+Y)")
    for k, t, v in NEST.transfer_attributes():
        pn.GetPrim().CreateAttribute(k, {"string": S, "double": Db}[t], custom=True).Set(v)
    for i, xyz in enumerate(NEST.seat_sensors()):
        frame(f"plate_nest_seat_sensor_{i}", xyz, "flush seat sensor window, looks +Z")
    frame("plate_reader", READER, "plate barcode reader lens point; reads the plate's -X short end along +X")
    UsdGeom.Xform.Define(sem, f"{ROOT}/tip_rack_frames")
    rx, ry = TIP_RACK["c"]
    frame("tip_rack_frames/rack_1", (rx, ry, TIP_RACK["top"]), "SBS 96 tip rack top surface centre; tip collars rest "
                                                              "here; positions A01..H12 at 9 mm pitch, A01 at (-X,+Y)")
    UsdGeom.Xform.Define(sem, f"{ROOT}/reagent_rack_frames")
    frame("reagent_rack_frames/rack_1", (*REAGENT["c"], REAGENT["block_top"]), "reagent tube block, 4 positions")
    for k, (x, y) in reagent_positions().items():
        frame(f"reagent_rack_frames/rack_1/pos_{k}", (x - REAGENT["c"][0], y - REAGENT["c"][1],
                                                      REAGENT["tube_bottom"] - REAGENT["block_top"]),
              f"reagent position {k}: tube bottom (outside) centre")
        frame(f"reagent_reader_{k}", (x, REAGENT["c"][1] - 26.0, REAGENT["block_top"] + 2.0),
              f"barcode reader of reagent position {k}; looks +Y at the tube")
    frame("waste_frame", (*WASTE["c"], WASTE["top"] + 30.0), "tip eject point above the waste bin")
    pt = UsdGeom.Xform.Define(sem, f"{link_path('ChannelZ')}/pipette_tip_frame")
    pt.AddTranslateOp().Set(Gf.Vec3d(0, 0, 0))
    pt.GetPrim().CreateAttribute("sdt:frameRole", S, custom=True).Set(
        "tip-mount cone end on the channel (moving); a mounted tip's end is 42 mm below it along -Z")
    frame("pipette_tip_frame", (CH_X, 0, CONE_END_Z), "channel cone end with the gantry at X = Y = 0, Z = 0 (live: "
                                                      "GantryX/GantryY/ChannelZ/pipette_tip_frame)")
    sem.GetRootLayer().Save()


def write_tip():
    st = tc.new_layer(os.path.join(HERE, "tip.usda"), "Tip", GENERATOR)
    root = UsdGeom.Xform.Define(st, "/Tip")
    mats = define_materials(st, "/Tip", ["TipConductive"])
    m, _ = write_mesh(st, "/Tip/Visual", tip_solid())
    bind(m.GetPrim(), mats["TipConductive"])
    rp = root.GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(rp)
    mass = UsdPhysics.MassAPI.Apply(rp)
    mass.CreateMassAttr(0.004)                                # heavier than real (0.5 g) for solver stability
    mass.CreateDiagonalInertiaAttr(Gf.Vec3f(2e-7, 2e-7, 5e-8))
    rp.AddAppliedSchema("PhysxRigidBodyAPI")
    rp.CreateAttribute("physxRigidBody:sleepThreshold", F).Set(0.0)
    cmat = define_contact_materials(st, "/Tip")
    c = UsdGeom.Xform.Define(st, "/Tip/Collision")
    c.CreatePurposeAttr(UsdGeom.Tokens.guide)
    T = TIP
    add_box_collider(st, c.GetPath(), "Collar", (-T["collar_r"], T["collar_r"]), (-T["collar_r"], T["collar_r"]),
                     (-T["collar_h"], 0.0), (0, 0, 0), cmat["Polystyrene"], offsets=(0.0005, 0.0))
    # collar only: the cone hangs in the rack hole, and the rack is one solid collider block (a cone collider would be
    # pushed out of it at the first step; found on the first test run, 2026-10-16)
    rp.CreateAttribute("labware:kind", Sdf.ValueTypeNames.String, custom=True).Set("pipette_tip_50uL_conductive")
    st.GetRootLayer().Save()


def build():
    os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
    tc.make_textures(os.path.join(HERE, "textures"), [12])
    tc.PBR.update(EXTRA_PBR)
    parts = build_cad()
    asm = cq.Assembly(name=NAME)
    for name, (wp, _, _) in parts.items():
        asm.add(wp, name=name)
    asm.export(os.path.join(HERE, "build", f"{PREFIX}.step"))
    tri = write_visual(parts)
    n = write_physics()
    write_articulation()
    write_semantics()
    write_tip()
    top = new_layer("")
    top.GetRootLayer().subLayerPaths = [f"./{PREFIX}_{s}.usda" for s in ("semantics", "articulation", "physics",
                                                                         "visual")]
    top.GetRootLayer().Save()
    print(f"L12: {len(parts)} parts, {tri} triangles, {n} colliders; nest seat {NEST.seat_z} mm, cone end "
          f"{CONE_END_Z} mm at Z = 0")


if __name__ == "__main__":
    build()
