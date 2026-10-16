"""Build R03 (clean sample AMR) and H2 (deterministic AMR dock): parametric CAD -> STEP + OpenUSD.

Run with the CAD environment:  env_cad/bin/python assets/r03/build_r03.py

Cell 01 baseline (sdt/components/R03_AMR_H2_Dock.yaml): "MiR100-class simulation baseline with Cell01 sealed sample
cabinet". Project-owned proxies, not MiR models.

R03 (r03.usda, root = the map frame of the AMR, placed at the docked pose by the overlay):
  * planar base: PlanarX / PlanarY (prismatic) + Yaw (revolute) from a fixed anchor to BaseLink. The controller
    (twin/r03_controller.py) drives it with unicycle (differential-drive) kinematics; for docking it makes the
    lateral and yaw drives compliant so the dock's V-guides centre the AMR mechanically
  * BaseLink: 890 x 580 x 352 mm chassis (wheels visual), bumper with a central V-nose dock target, a sealed
    cabinet (shelves visual) with the carrier nest on top (shared static SBS nest, seat 960 mm above the floor)
  * Lid (prismatic, slides back 340 mm): a flat plate over a fixed shroud around the carrier nest; closed in transit
H2 (h2_dock.usda): a floor dock with two V-guide wedges (+-45 mm capture, 3 mm clearance when seated), a front stop
  with charging contacts and a notch for the AMR's V-nose, four dock sensor rays (two on the bumper face: depth +
  yaw; two on the V-nose: lateral), status lamps.
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
from common.twin_cad import (B, F, MM, _drive, _joint, add_box_collider, add_convex_collider, bind, box, cyl,  # noqa: E402
                             define_contact_materials, define_materials, write_mesh)

AMR, DOCK = "R03_SampleAMR", "H2_AMR_Dock"
L, Wd, CH_Z = 890.0, 580.0, (30.0, 352.0)            # chassis length (x), width (y), z range
CAB = dict(x=(-250.0, 150.0), y=(-190.0, 190.0), z=(352.0, 900.0))
# carrier nest 60 mm off the centreline toward the AMR's right (R01's side when docked heading west): at the centred
# site R01's planner found no approach with sigma_min >= 0.10 / 20 deg joint margin (full-cell run, 2026-10-16)
NEST = StaticNest(seat_z=60.0, tag_id=31, cx=35.0, cy=-60.0, prefix="Carrier", cz=900.0)   # seat 960 mm
# carrier enclosure: a FIXED shroud (walls) around the off-centre nest and a flat LID plate that slides back over it.
# (A sliding hood with walls swept through the carrier plate and jammed: full-cell run, 2026-10-16.)
LID = dict(x=(-85.0, 150.0), y=(-140.0, 20.0), z=(990.0, 996.0), t=4.0, travel=340.0)
SHROUD_Z = (900.0, 988.0)
NOSE = dict(x0=445.0, tip=470.0, half=25.0, z=(140.0, 240.0))
BUMPER = dict(x=(440.0, 452.0), y=(-250.0, 250.0), z=(60.0, 260.0))
X_RANGE, Y_RANGE = (-4000.0, 60.0), (-3500.0, 3500.0)
# dock (in the dock frame = the AMR map frame: +x is the AMR's forward direction when docked; origin = docked
# base_link). Stop face at the docked bumper face, nose notch, V-guides along the flanks.
STOP_X = BUMPER["x"][1] + 1.0
WEDGE = dict(len=250.0, open=45.0, clear=3.0, h=250.0, t=40.0)
DOCK_RAYS = {"depth_L": (STOP_X + 10.0, 150.0, 190.0), "depth_R": (STOP_X + 10.0, -150.0, 190.0),
             "nose_L": (NOSE["tip"] + 30.0, 15.0, 190.0), "nose_R": (NOSE["tip"] + 30.0, -15.0, 190.0)}
EXTRA_PBR = {
    "AmrGrey": ((0.20, 0.21, 0.22), 0.45, 0.2, {}),
    "AmrWhite": ((0.86, 0.87, 0.87), 0.42, 0.0, {}),
    "LensAmber": ((0.6, 0.35, 0.02), 0.15, 0.0, {"emissive": ((1.0, 0.55, 0.05), 0.0)}),
    "Copper": ((0.85, 0.50, 0.30), 0.3, 1.0, {}),
}


# ------------------------------------------------------------------ R03 CAD (base_link frame, mm)
def amr_parts():
    p = {}
    ch = box(0, 0, sum(CH_Z) / 2, L, Wd, CH_Z[1] - CH_Z[0]).edges("|Z").fillet(40).edges(">Z").fillet(8)
    p["Chassis"] = (ch, "AmrGrey", "BaseLink")
    p["TopDeck"] = (box(0, 0, CH_Z[1] - 2, L - 30, Wd - 30, 4).edges("|Z").fillet(30), "AmrWhite", "BaseLink")
    for i, (x, y, r, w) in enumerate([(0, 270, 100, 40), (0, -270, 100, 40), (330, 200, 40, 30), (330, -200, 40, 30),
                                      (-330, 200, 40, 30), (-330, -200, 40, 30)]):
        p[f"Wheel{i}"] = (cyl(r, w, (x, y - w / 2 * np.sign(y), r), (0, np.sign(y), 0)), "RubberBlack", "BaseLink")
    B_ = BUMPER
    p["Bumper"] = (box(sum(B_["x"]) / 2, 0, sum(B_["z"]) / 2, B_["x"][1] - B_["x"][0], B_["y"][1] - B_["y"][0],
                       B_["z"][1] - B_["z"][0]).edges("|X").fillet(4), "RubberBlack", "BaseLink")
    p["DockNose"] = (nose_solid(), "SteelSatin", "BaseLink")
    for s in (-1, 1):
        p[f"ChargeContact{'LR'[s > 0]}"] = (box(B_["x"][1] + 0.5, s * 100, 110, 1, 30, 20), "Copper", "BaseLink")
    C = CAB
    cab = box(sum(C["x"]) / 2, 0, sum(C["z"]) / 2, C["x"][1] - C["x"][0], C["y"][1] - C["y"][0], C["z"][1] - C["z"][0])
    p["Cabinet"] = (cab.edges("|Z").fillet(10).edges(">Z").fillet(3), "AmrWhite", "BaseLink")
    p["CabinetDoor"] = (box(C["x"][0] - 1.5, 0, (C["z"][0] + C["z"][1]) / 2, 3, C["y"][1] - C["y"][0] - 30,
                            C["z"][1] - C["z"][0] - 40).edges("|X").fillet(6), "AmrGrey", "BaseLink")
    p["CabinetHandle"] = (box(C["x"][0] - 6, 120, 640, 8, 12, 120).edges().fillet(2), "SteelSatin", "BaseLink")
    p["CabinetLabel"] = (box(C["x"][0] - 3.2, -40, 820, 0.6, 180, 30), "LabelWhite", "BaseLink")
    for i, lens in enumerate(("LensGreen", "LensAmber", "LensRed")):
        p[f"StatusLamp{i}"] = (cyl(6, 3, (C["x"][1], -60 + 30 * i, 860), (1, 0, 0)), lens, "BaseLink")
    for name, (wp, mat) in NEST.parts().items():
        p[name] = (wp, mat, "BaseLink")
    for name, xs, ys, zs in shroud_boxes():
        p[name] = (box(sum(xs) / 2, sum(ys) / 2, sum(zs) / 2, xs[1] - xs[0], ys[1] - ys[0], zs[1] - zs[0]), "AmrWhite",
                   "BaseLink")
    p["LidPlate"] = (lid_solid(), "AmrWhite", "Lid")
    p["LidHandle"] = (box(LID["x"][1] - 10, sum(LID["y"]) / 2, LID["z"][1] + 4, 12, 80, 8).edges().fillet(2),
                      "SteelSatin", "Lid")
    return p


def nose_solid():
    N = NOSE
    pts = [(N["x0"], -N["half"]), (N["tip"], 0.0), (N["x0"], N["half"])]
    return cq.Workplane("XY").polyline(pts).close().extrude(N["z"][1] - N["z"][0]).translate((0, 0, N["z"][0]))


def lid_solid():
    Ld = LID
    return box(sum(Ld["x"]) / 2, sum(Ld["y"]) / 2, sum(Ld["z"]) / 2, Ld["x"][1] - Ld["x"][0], Ld["y"][1] - Ld["y"][0],
               Ld["z"][1] - Ld["z"][0]).edges("|Z").fillet(3)


def shroud_boxes():
    Ld, t, z = LID, LID["t"], SHROUD_Z
    return [("ShroudN", Ld["x"], (Ld["y"][1] - t, Ld["y"][1]), z), ("ShroudS", Ld["x"], (Ld["y"][0], Ld["y"][0] + t), z),
            ("ShroudF", (Ld["x"][1] - t, Ld["x"][1]), Ld["y"], z), ("ShroudR", (Ld["x"][0], Ld["x"][0] + t), Ld["y"], z)]


def amr_colliders():
    C, B_, Ld = CAB, BUMPER, LID
    base = [("Chassis", (-L / 2, L / 2), (-Wd / 2, Wd / 2), CH_Z), ("Bumper", B_["x"], B_["y"], B_["z"]),
            ("Cabinet", C["x"], C["y"], C["z"])] + shroud_boxes()
    lid = [("Top", Ld["x"], Ld["y"], Ld["z"])]
    return base, lid


# ------------------------------------------------------------------ H2 CAD (dock frame, mm)
def wedge_solid(s):
    """V-guide along a flank: inner face from (STOP_X, s*(W/2+clear)) back to (STOP_X-len, s*(W/2+clear+open))."""
    W_ = WEDGE
    y_in0, y_in1 = s * (Wd / 2 + W_["clear"]), s * (Wd / 2 + W_["clear"] + W_["open"])
    x0, x1 = STOP_X, STOP_X - W_["len"]
    pts = [(x0, y_in0), (x1, y_in1), (x1, y_in1 + s * W_["t"]), (x0, y_in0 + s * W_["t"])]
    return cq.Workplane("XY").polyline(pts).close().extrude(W_["h"])


def dock_parts():
    p = {}
    p["BasePlate"] = (box(STOP_X - 120, 0, 5, 340, Wd + 2 * (WEDGE["clear"] + WEDGE["open"] + WEDGE["t"]) + 20, 10)
                      .edges("|Z").fillet(10), "AmrGrey")
    for s in (-1, 1):
        p[f"Wedge{'LR'[s > 0]}"] = (wedge_solid(s).edges("|Z").fillet(3), "LabelYellow")
        p[f"StopBlock{'LR'[s > 0]}"] = (box(STOP_X + 45, s * 150, 140, 90, 180, 260).edges("|Z").fillet(6), "AmrGrey")
        p[f"Contact{'LR'[s > 0]}"] = (box(STOP_X + 0.5, s * 100, 110, 1, 34, 24), "Copper")
    p["NoseNotch"] = (box(STOP_X + 70, 0, 200, 40, 120, 120).edges("|Z").fillet(4), "AmrGrey")
    p["Tower"] = (box(STOP_X + 70, 0, 400, 50, 60, 280).edges("|Z").fillet(6), "AmrWhite")
    for i, lens in enumerate(("LensGreen", "LensAmber", "LensRed")):
        p[f"StatusLamp{i}"] = (cyl(7, 3, (STOP_X + 45 - 3, -25 + 25 * i, 500), (-1, 0, 0)), lens)
    p["Label"] = (box(STOP_X + 44.6, 0, 440, 0.6, 50, 20), "LabelWhite")
    return p


def dock_colliders():
    out = []
    for s in (-1, 1):
        out.append((f"StopBlock{'LR'[s > 0]}", (STOP_X, STOP_X + 90), tuple(sorted((s * 60, s * 240))), (10, 270)))
    out.append(("NoseNotch", (NOSE["tip"] + 20, STOP_X + 90), (-60, 60), (140, 260)))
    out.append(("BasePlate", (STOP_X - 290, STOP_X + 50), (-Wd / 2 - 100, Wd / 2 + 100), (0, 10)))
    return out


# ------------------------------------------------------------------ USD
def new_layer(path, prim):
    return tc.new_layer(os.path.join(HERE, path), prim, "assets/r03/build_r03.py")


def build_amr():
    st = new_layer("r03.usda", AMR)
    R = f"/{AMR}"
    root = UsdGeom.Xform.Define(st, R)
    rp = root.GetPrim()
    Usd.ModelAPI(rp).SetKind(Kind.Tokens.component)
    parts = amr_parts()
    mats = define_materials(st, R, sorted({m for _, m, _ in parts.values()} | {"AprilTag"}), tag_id=31)
    links = {"Anchor": f"{R}/Anchor", "PlanarX": f"{R}/PlanarX", "PlanarY": f"{R}/PlanarX/PlanarY",
             "BaseLink": f"{R}/PlanarX/PlanarY/BaseLink", "Lid": f"{R}/PlanarX/PlanarY/BaseLink/Lid"}
    for name, path in links.items():
        UsdGeom.Xform.Define(st, path)
        UsdGeom.Xform.Define(st, f"{path}/Visual")
    tri = 0
    for name, (wp, mat, link) in parts.items():
        m, n = write_mesh(st, f"{links[link]}/Visual/{name}", wp)
        bind(m.GetPrim(), mats[mat])
        tri += n
    tx, ty, tz, hs = NEST.tag()
    q = UsdGeom.Mesh.Define(st, f"{links['BaseLink']}/Visual/CarrierAprilTag")
    q.CreatePointsAttr([Gf.Vec3f((tx - hs) * MM, (ty - hs) * MM, tz * MM), Gf.Vec3f((tx + hs) * MM, (ty - hs) * MM, tz * MM),
                        Gf.Vec3f((tx + hs) * MM, (ty + hs) * MM, tz * MM), Gf.Vec3f((tx - hs) * MM, (ty + hs) * MM, tz * MM)])
    q.CreateFaceVertexCountsAttr([4])
    q.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    q.CreateNormalsAttr([Gf.Vec3f(0, 0, 1)] * 4)
    q.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
    UsdGeom.PrimvarsAPI(q).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex).Set(
        [Gf.Vec2f(0, 0), Gf.Vec2f(1, 0), Gf.Vec2f(1, 1), Gf.Vec2f(0, 1)])
    bind(q.GetPrim(), mats["AprilTag"])
    # physics
    cmat = define_contact_materials(st, R)
    masses = {"Anchor": 1.0, "PlanarX": 1.0, "PlanarY": 1.0, "BaseLink": 95.0, "Lid": 1.5}
    base_cols, lid_cols = amr_colliders()
    for name, path in links.items():
        UsdPhysics.RigidBodyAPI.Apply(st.GetPrimAtPath(path))
        UsdPhysics.MassAPI.Apply(st.GetPrimAtPath(path)).CreateMassAttr(masses[name])
    n = 0
    for link, cols in (("BaseLink", base_cols), ("Lid", lid_cols)):
        col = UsdGeom.Xform.Define(st, f"{links[link]}/Collision")
        col.CreatePurposeAttr(UsdGeom.Tokens.guide)
        for name, xs, ys, zs in cols:
            add_box_collider(st, col.GetPath(), name, xs, ys, zs, (0, 0, 0), cmat["Steel"], offsets=(0.001, 0.0))
            n += 1
    colb = f"{links['BaseLink']}/Collision"
    add_convex_collider(st, f"{colb}/DockNose", nose_solid(), (0, 0, 0), cmat["Steel"])
    n += 1 + NEST.add_colliders(st, colb, cmat)
    # articulation: fixed anchor -> X -> Y -> yaw -> BaseLink; lid slides back along -X
    UsdPhysics.ArticulationRootAPI.Apply(rp)
    rp.AddAppliedSchema("PhysxArticulationAPI")
    rp.CreateAttribute("physxArticulation:enabledSelfCollisions", B).Set(False)
    rp.CreateAttribute("physxArticulation:solverPositionIterationCount", Sdf.ValueTypeNames.Int).Set(32)
    rp.CreateAttribute("physxArticulation:sleepThreshold", F).Set(0.0)
    J = f"{R}/Joints"
    UsdGeom.Scope.Define(st, J)
    _joint(st, UsdPhysics.FixedJoint, f"{J}/AnchorJoint", None, links["Anchor"], Gf.Vec3f(0), Gf.Vec3f(0))
    jx = _joint(st, UsdPhysics.PrismaticJoint, f"{J}/PlanarXJoint", links["Anchor"], links["PlanarX"], Gf.Vec3f(0),
                Gf.Vec3f(0), "X", (X_RANGE[0] * MM, X_RANGE[1] * MM))
    _drive(jx, "linear", stiffness=2.0e5, damping=2.0e4, max_force=5000.0, target=0.0)
    jy = _joint(st, UsdPhysics.PrismaticJoint, f"{J}/PlanarYJoint", links["PlanarX"], links["PlanarY"], Gf.Vec3f(0),
                Gf.Vec3f(0), "Y", (Y_RANGE[0] * MM, Y_RANGE[1] * MM))
    _drive(jy, "linear", stiffness=2.0e5, damping=2.0e4, max_force=5000.0, target=0.0)
    jr = _joint(st, UsdPhysics.RevoluteJoint, f"{J}/YawJoint", links["PlanarY"], links["BaseLink"], Gf.Vec3f(0),
                Gf.Vec3f(0), "Z", None)
    _drive(jr, "angular", stiffness=900.0, damping=25.0, max_force=5000.0, target=0.0)
    jl = _joint(st, UsdPhysics.PrismaticJoint, f"{J}/LidSlide", links["BaseLink"], links["Lid"], Gf.Vec3f(0),
                Gf.Vec3f(0), "X", (-LID["travel"] * MM, 0.0))
    _drive(jl, "linear", stiffness=20000.0, damping=400.0, max_force=200.0, target=0.0)
    # semantics + frames (Cell 01 binding: base_link, carrier_cabinet, dock_approach, dock_frame, handover_carrier_frame)
    S, Db, St = Sdf.ValueTypeNames.String, Sdf.ValueTypeNames.Double, Sdf.ValueTypeNames.StringArray
    for k, t, v in (("sdt:componentId", S, "R03/H2"), ("sdt:canonicalName", S, "R03 Clean Sample AMR with H2 Deterministic Dock"),
                    ("sdt:contract", S, "sdt/components/R03_AMR_H2_Dock.yaml"),
                    ("sdt:capabilities", St, ["navigate", "transport_clean_sample", "dock_precisely", "handover_carrier",
                                              "opportunity_charge"]),
                    ("sdt:bindingStatus", S, "articulated_v1"),
                    ("sdt:designBasis", S, "project-owned MiR100-class proxy with a sealed sample cabinet; not a MiR model"),
                    ("state:pose", S, ""), ("state:battery_percent", Db, 100.0), ("state:dock_state", S, "undocked"),
                    ("state:cabinet", S, "closed"), ("state:payload_inventory", St, []),
                    ("state:contamination_class", S, "clean_sample_only"), ("state:fault", S, ""), ("state:mode", S, "READY")):
        rp.CreateAttribute(k, t, custom=True).Set(v)
    for k, v in (("amr:lidTravel_mm", LID["travel"]), ("amr:noseTip_mm", NOSE["tip"]), ("amr:width_mm", Wd)):
        rp.CreateAttribute(k, Db, custom=True).Set(float(v))

    def frame(path, pos, role):
        f = UsdGeom.Xform.Define(st, path)
        f.AddTranslateOp().Set(Gf.Vec3d(*(np.array(pos, float) * MM)))
        f.GetPrim().CreateAttribute("sdt:frameRole", S, custom=True).Set(role)
        return f

    frame(f"{links['BaseLink']}/base_link_frame", (0, 0, 0), "AMR base_link (moving): floor centre, +X forward")
    frame(f"{R}/base_link", (0, 0, 0), "AMR base_link at the map origin of this prim (= dock_frame); the moving "
                                       "body is PlanarX/PlanarY/BaseLink")
    frame(f"{R}/carrier_cabinet", (sum(CAB["x"]) / 2, 0, sum(CAB["z"]) / 2), "sealed sample cabinet centre (docked pose)")
    frame(f"{R}/dock_frame", (0, 0, 0), "base_link pose when docked in H2 (map frame of this prim)")
    frame(f"{R}/dock_approach", (-1000.0, 0, 0), "approach pose 1.0 m before the dock, heading +X")
    hf = frame(f"{R}/handover_carrier_frame", (NEST.cx, NEST.cy, NEST.cz + NEST.seat_z),
               "carrier seat with the AMR docked and the lid open: R01 place/pick target; A1 at (-X,+Y)")
    for k, t, v in NEST.transfer_attributes():
        hf.GetPrim().CreateAttribute(k, {"string": S, "double": Db}[t], custom=True).Set(v)
    for i, xyz in enumerate(NEST.seat_sensors()):
        frame(f"{links['BaseLink']}/carrier_seat_sensor_{i}", xyz, "carrier presence sensor window, looks +Z")
    st.GetRootLayer().Save()
    return len(parts), tri, n


def build_dock():
    st = new_layer("h2_dock.usda", DOCK)
    R = f"/{DOCK}"
    root = UsdGeom.Xform.Define(st, R)
    rp = root.GetPrim()
    Usd.ModelAPI(rp).SetKind(Kind.Tokens.component)
    parts = dock_parts()
    mats = define_materials(st, R, sorted({m for _, m in parts.values()}))
    UsdGeom.Xform.Define(st, f"{R}/Visual")
    for name, (wp, mat) in parts.items():
        m, _ = write_mesh(st, f"{R}/Visual/{name}", wp)
        bind(m.GetPrim(), mats[mat])
    cmat = define_contact_materials(st, R)
    col = UsdGeom.Xform.Define(st, f"{R}/Collision")
    col.CreatePurposeAttr(UsdGeom.Tokens.guide)
    for s in (-1, 1):
        add_convex_collider(st, f"{col.GetPath()}/Wedge{'LR'[s > 0]}", wedge_solid(s), (0, 0, 0), cmat["Peek"])
    for name, xs, ys, zs in dock_colliders():
        add_box_collider(st, col.GetPath(), name, xs, ys, zs, (0, 0, 0), cmat["Steel"])
    S = Sdf.ValueTypeNames.String
    for k, v in (("sdt:componentId", "H2"), ("sdt:canonicalName", "H2 Deterministic AMR Dock"),
                 ("sdt:bindingStatus", "static_v1"), ("state:dock_state", "free"),
                 ("sdt:designBasis", "project-owned V-guide dock with a nose fiducial; not a MiR charging station")):
        rp.CreateAttribute(k, S, custom=True).Set(v)
    for name, (x, y, z) in DOCK_RAYS.items():
        f = UsdGeom.Xform.Define(st, f"{R}/sensor_{name}")
        f.AddTranslateOp().Set(Gf.Vec3d(x * MM, y * MM, z * MM))
        f.GetPrim().CreateAttribute("sdt:frameRole", S, custom=True).Set(
            f"dock sensor ray origin, looks -X toward the AMR ({'bumper face: depth/yaw' if 'depth' in name else 'V-nose: lateral'})")
    rp.CreateAttribute("dock:stopX_mm", Sdf.ValueTypeNames.Double, custom=True).Set(STOP_X)
    rp.CreateAttribute("dock:noseTip_mm", Sdf.ValueTypeNames.Double, custom=True).Set(NOSE["tip"])
    st.GetRootLayer().Save()
    return len(parts)


def build():
    os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
    tc.make_textures(os.path.join(HERE, "textures"), [31])
    tc.PBR.update(EXTRA_PBR)
    n_parts, tri, n_col = build_amr()
    nd = build_dock()
    asm = cq.Assembly(name="R03_H2")
    for name, (wp, _, _) in amr_parts().items():
        asm.add(wp, name=name)
    for name, (wp, _) in dock_parts().items():
        asm.add(wp, name=f"Dock_{name}")
    asm.export(os.path.join(HERE, "build", "r03_h2.step"))
    print(f"R03: {n_parts} parts, {tri} triangles, {n_col} colliders; carrier seat {NEST.cz + NEST.seat_z} mm; "
          f"H2: {nd} parts, stop face x {STOP_X} mm")


if __name__ == "__main__":
    build()
