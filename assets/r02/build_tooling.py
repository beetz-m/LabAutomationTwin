"""Build the R02 tool magazine TCM01 with tools T01-T05 (Cell 01 sdt/components/ToolChanger_Magazine.yaml).

Project-owned proxies (Zimmer WMR2063 CAD is restricted; Cell 01 option A). Coupler: the robot half is part of
R02 (tools/make_r02_urdf.py, 16 mm); each tool carries the 12 mm tool half (Ø63) and a 90 x 70 x 8 mm adapter
flange, by which it hangs in a fork-type dock.

Tool frame: origin on the coupling face, +Z along the tool (away from the robot), as for the R01 gripper. Docked, a
tool's +Z points down and its coupling face is at the dock frame dock_Txx (the pose the robot coupler must reach).

  T01 plate_gripper     GEP2006-class gripper with the R01 SBS long-side fingers (2 jaws on driven prismatic joints;
                        not an articulation: the coupler lock, a surface-gripper attachment, cannot hold articulation links),
                        TCP 155 mm from the coupling face (= 171 mm from the robot flange, as on R01)
  T02 tube_gripper      rigid proxy, TCP 130 mm
  T03 pipetting_tool    rigid proxy, TCP 150 mm, contamination class liquid_contact
  T04 suction_tool      rigid proxy, TCP 120 mm, needs vacuum
  T05 inspection_camera rigid proxy, TCP (camera frame) 110 mm

Each tool: tool:id (the ID the coupler's electrical contact reads; never inferred from the dock), tool:type,
tool:contaminationClass, tool:utilities, tool:tcp_mm, tool_coupler and tcp frames; never-sleeping rigid bodies
(a sleeping tool is not woken when the coupler releases it). Docks: frames dock_T01..dock_T05 and an occupancy
ray origin per dock. Magazine frame: origin on the floor below the middle dock, docks along +X, open to -Y.

Run: env_cad/bin/python assets/r02/build_tooling.py  ->  assets/r02/tooling.usda
"""

import os
import sys

from pxr import Gf, Sdf, UsdGeom, UsdPhysics

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from common import twin_cad as b  # noqa: E402

MM = b.MM
ROOT = "/AutomaticToolChanger"
PITCH = 150.0
Z_DOCK = 1120.0                    # coupling face height of a docked tool (mm above the floor)
TOOL_HALF, ADAPTER = 12.0, 8.0
Z_TINE = Z_DOCK - TOOL_HALF - ADAPTER
GAP, TINE_W, TINE_H = 62.0, 15.0, 15.0
TINE_Y = (-60.0, 70.0)
# back beam behind every tool's footprint: T01's rear jaw reaches 53 mm behind the dock axis (a beam at 40 mm caught
# its tip when the tool was lowered back in, 2026-10-15)
BEAM = dict(y=(70.0, 110.0), z=(Z_TINE - 45.0, Z_TINE))
LEG_X = 2 * PITCH + 70.0
TOOLS = {
    "T01": dict(type="plate_gripper", tcp=155.0, mass=1.0, contamination="clean", utilities="electrical"),
    "T02": dict(type="tube_gripper", tcp=130.0, mass=0.5, contamination="clean", utilities="electrical"),
    "T03": dict(type="pipetting_tool", tcp=150.0, mass=0.6, contamination="liquid_contact", utilities="electrical"),
    "T04": dict(type="suction_tool", tcp=120.0, mass=0.4, contamination="clean", utilities="electrical,vacuum"),
    "T05": dict(type="inspection_camera", tcp=110.0, mass=0.5, contamination="clean", utilities="electrical"),
}
# T01 jaw geometry from assets/gripper/build_plate_gripper.py, re-based on the 12 mm tool half (-16 mm)
SBS_W = b.SBS[1]
CLEAR, STROKE = 2.5, 6.0
PAD_IN_OPEN = SBS_W / 2 + CLEAR
PAD_T, PAD_W, PAD_H = 2.0, 26.0, 10.0
FINGER_T, FINGER_W = 6.0, 30.0
BODY0, BODY_H, JAW_H = TOOL_HALF + ADAPTER, 62.0, 10.0
JAW0 = BODY0 + BODY_H
TCP01 = TOOLS["T01"]["tcp"]
TIP01 = TCP01 + 8.0


def dock_x(k):
    return (k - 2) * PITCH


def coupler_parts():
    half = b.cyl(31.5, TOOL_HALF, (0, 0, 0), (0, 0, 1)).edges().chamfer(1.0)
    adapter = b.box(0, 0, TOOL_HALF + ADAPTER / 2, 90, 70, ADAPTER).edges("|Z").fillet(5)
    tag = b.box(0, -35.2, TOOL_HALF + ADAPTER / 2, 30, 0.6, 5)
    return {"ToolHalf": (half, "Aluminium"), "Adapter": (adapter, "AnodizedGraphite"), "IdTag": (tag, "LabelYellow")}


def coupler_colliders():
    return [("ToolHalf", (-31.5, 31.5), (-31.5, 31.5), (0, TOOL_HALF)),
            ("Adapter", (-45, 45), (-35, 35), (TOOL_HALF, BODY0))]


def tool_parts(tid):
    """{link: {name: (solid, material)}}, {link: [box colliders]} in the tool frame (mm)."""
    vis, col = {"Body": coupler_parts()}, {"Body": coupler_colliders()}
    v, c = vis["Body"], col["Body"]
    if tid == "T01":
        v["GripperBody"] = (b.box(0, 0, BODY0 + BODY_H / 2, 50, 80, BODY_H).edges("|Z").fillet(3), "PlasticBlack")
        c.append(("GripperBody", (-25, 25), (-40, 40), (BODY0, JAW0)))
        for side, link in ((1, "FingerA"), (-1, "FingerB")):
            y_pad = side * (PAD_IN_OPEN + PAD_T / 2)
            y_fin = side * (PAD_IN_OPEN + PAD_T + FINGER_T / 2)
            jaw = b.box(0, side * (PAD_IN_OPEN + PAD_T + FINGER_T - 7), JAW0 + JAW_H / 2, 20, 14, JAW_H)
            finger = b.box(0, y_fin, (JAW0 + TIP01) / 2, FINGER_W, FINGER_T, TIP01 - JAW0).faces(">Z").edges("|X").chamfer(1.5)
            vis[link] = {"Jaw": (jaw.edges("|Z").fillet(1), "SteelSatin"), "Plate": (finger, "Aluminium"),
                         "Pad": (b.box(0, y_pad, TCP01, PAD_W, PAD_T, PAD_H).edges("|Y").fillet(1), "RubberBlack")}

            def ys(a, e, s=side):
                return tuple(sorted((s * a, s * e)))
            col[link] = [("Plate", (-FINGER_W / 2, FINGER_W / 2), ys(PAD_IN_OPEN + PAD_T, PAD_IN_OPEN + PAD_T + FINGER_T),
                          (JAW0, TIP01)),
                         ("Pad", (-PAD_W / 2, PAD_W / 2), ys(PAD_IN_OPEN, PAD_IN_OPEN + PAD_T), (TCP01 - PAD_H / 2, TCP01 + PAD_H / 2))]
    elif tid == "T02":
        v["Housing"] = (b.box(0, 0, BODY0 + 25, 40, 60, 50).edges("|Z").fillet(3), "PlasticBlack")
        for s in (1, -1):
            v[f"Finger{'A' if s > 0 else 'B'}"] = (b.box(0, s * 10, BODY0 + 50 + 35, 10, 4, 70), "SteelSatin")
        c += [("Housing", (-20, 20), (-30, 30), (BODY0, BODY0 + 50)), ("Fingers", (-5, 5), (-12, 12), (BODY0 + 50, 140))]
    elif tid == "T03":
        v["Barrel"] = (b.cyl(22, 90, (0, 0, BODY0), (0, 0, 1)).edges().fillet(2), "LabelWhite")
        v["Nozzle"] = (b.cyl(8, 40, (0, 0, BODY0 + 90), (0, 0, 1)), "SteelSatin")
        c += [("Barrel", (-22, 22), (-22, 22), (BODY0, BODY0 + 90)), ("Nozzle", (-8, 8), (-8, 8), (BODY0 + 90, 150))]
    elif tid == "T04":
        v["Valve"] = (b.box(0, 0, BODY0 + 20, 40, 40, 40).edges("|Z").fillet(3), "AnodizedGraphite")
        v["Stem"] = (b.cyl(6, 50, (0, 0, BODY0 + 40), (0, 0, 1)), "SteelSatin")
        v["Cup"] = (b.cyl(15, 10, (0, 0, 110), (0, 0, 1)), "RubberBlack")
        c += [("Valve", (-20, 20), (-20, 20), (BODY0, BODY0 + 40)), ("Stem", (-6, 6), (-6, 6), (BODY0 + 40, 110)),
              ("Cup", (-15, 15), (-15, 15), (110, 120))]
    elif tid == "T05":
        v["Camera"] = (b.box(0, 0, BODY0 + 35, 50, 50, 70).edges("|Z").fillet(4), "PlasticBlack")
        v["Lens"] = (b.cyl(14, 20, (0, 0, BODY0 + 70), (0, 0, 1)), "SensorWindow")
        c += [("Camera", (-25, 25), (-25, 25), (BODY0, BODY0 + 70)), ("Lens", (-14, 14), (-14, 14), (BODY0 + 70, 110))]
    return vis, col


def stand_parts():
    p = {"Beam": (b.box(0, sum(BEAM["y"]) / 2, sum(BEAM["z"]) / 2, 2 * LEG_X + 40, BEAM["y"][1] - BEAM["y"][0],
                        BEAM["z"][1] - BEAM["z"][0]), "Aluminium")}
    for s in (-1, 1):
        p[f"Leg{'R' if s > 0 else 'L'}"] = (b.box(s * LEG_X, 90, BEAM["z"][0] / 2, 40, 40, BEAM["z"][0]), "Aluminium")
        p[f"Foot{'R' if s > 0 else 'L'}"] = (b.box(s * LEG_X, 90, 5, 80, 300, 10), "AnodizedGraphite")
    for k in range(5):
        for s in (-1, 1):
            x = dock_x(k) + s * (GAP / 2 + TINE_W / 2)
            p[f"Tine{k}{'R' if s > 0 else 'L'}"] = (b.box(x, sum(TINE_Y) / 2, Z_TINE - TINE_H / 2, TINE_W,
                                                         TINE_Y[1] - TINE_Y[0], TINE_H).edges("|Y").fillet(2), "PeekNatural")
        p[f"Label{k}"] = (b.box(dock_x(k), BEAM["y"][0] - 0.3, Z_TINE - 25, 40, 0.6, 14), "LabelWhite")
    return p


def main():
    path = os.path.join(HERE, "tooling.usda")
    stage = b.new_layer(path, "AutomaticToolChanger", generator="assets/r02/build_tooling.py")
    UsdGeom.Xform.Define(stage, ROOT)
    names = {"Aluminium", "AnodizedGraphite", "LabelYellow", "PlasticBlack", "SteelSatin", "RubberBlack", "LabelWhite",
             "SensorWindow", "PeekNatural"}
    mats = b.define_materials(stage, ROOT, sorted(names))
    cm = b.define_contact_materials(stage, ROOT)
    rubber = b.UsdShade.Material.Define(stage, f"{ROOT}/PhysicsMaterials/Rubber")
    api = UsdPhysics.MaterialAPI.Apply(rubber.GetPrim())
    api.CreateStaticFrictionAttr(1.0)
    api.CreateDynamicFrictionAttr(0.9)
    api.CreateRestitutionAttr(0.05)

    # stand (static)
    UsdGeom.Xform.Define(stage, f"{ROOT}/Stand")
    for name, (wp, mat) in stand_parts().items():
        mesh, _ = b.write_mesh(stage, f"{ROOT}/Stand/Visual/{name}", wp)
        b.bind(mesh.GetPrim(), mats[mat])
    scol = UsdGeom.Xform.Define(stage, f"{ROOT}/Stand/Collision")
    scol.CreatePurposeAttr(UsdGeom.Tokens.guide)
    b.add_box_collider(stage, str(scol.GetPath()), "Beam", (-LEG_X - 20, LEG_X + 20), BEAM["y"], BEAM["z"], (0, 0, 0),
                       cm["Steel"])
    for s in (-1, 1):
        b.add_box_collider(stage, str(scol.GetPath()), f"Leg{'R' if s > 0 else 'L'}", (s * LEG_X - 20, s * LEG_X + 20),
                           (70, 110), (0, BEAM["z"][0]), (0, 0, 0), cm["Steel"])
    for k in range(5):
        for s in (-1, 1):
            x = dock_x(k) + s * (GAP / 2 + TINE_W / 2)
            b.add_box_collider(stage, str(scol.GetPath()), f"Tine{k}{'R' if s > 0 else 'L'}", (x - TINE_W / 2, x + TINE_W / 2),
                               TINE_Y, (Z_TINE - TINE_H, Z_TINE), (0, 0, 0), cm["Peek"], offsets=(0.001, 0.0))

    # docks: frames at the docked coupling face (tool +Z down = rotated 180 deg about X), occupancy ray origins
    for k, tid in enumerate(TOOLS):
        d = UsdGeom.Xform.Define(stage, f"{ROOT}/dock_{tid}")
        d.AddTranslateOp().Set(Gf.Vec3d(dock_x(k) * MM, 0, Z_DOCK * MM))
        d.AddRotateXOp().Set(180.0)
        d.GetPrim().CreateAttribute("sdt:frameRole", Sdf.ValueTypeNames.String, custom=True).Set(
            f"dock {tid}: coupling face of the docked tool; tool +Z down; the robot coupler must reach this pose")
        d.GetPrim().CreateAttribute("dock:expectedToolId", Sdf.ValueTypeNames.String, custom=True).Set(tid)
        s = UsdGeom.Xform.Define(stage, f"{ROOT}/Stand/occupancy_{tid}")
        s.AddTranslateOp().Set(Gf.Vec3d(dock_x(k) * MM, BEAM["y"][0] * MM - 0.001, (Z_TINE + 4) * MM))
        s.GetPrim().CreateAttribute("sdt:frameRole", Sdf.ValueTypeNames.String, custom=True).Set(
            f"occupancy ray origin for dock {tid}; ray along -Y, 60 mm: hits a docked tool's adapter flange")
    for name, note in (("tool_coupler", "tool-side coupling faces are Tools/Txx/Body/tool_coupler"),
                       ("robot_coupler", "robot-side coupling face is on R02: .../r02_wrist_3_link/robot_coupler")):
        f = UsdGeom.Xform.Define(stage, f"{ROOT}/{name}")
        f.GetPrim().CreateAttribute("sdt:frameRole", Sdf.ValueTypeNames.String, custom=True).Set(note)

    # tools: rigid bodies resting in their docks (T01 also an articulation with two driven jaws)
    UsdGeom.Scope.Define(stage, f"{ROOT}/Tools")
    for k, (tid, t) in enumerate(TOOLS.items()):
        troot = f"{ROOT}/Tools/{tid}"
        x = UsdGeom.Xform.Define(stage, troot)
        x.AddTranslateOp().Set(Gf.Vec3d(dock_x(k) * MM, 0, Z_DOCK * MM))
        x.AddRotateXOp().Set(180.0)
        vis, col = tool_parts(tid)
        masses = {"Body": t["mass"] - (0.1 if tid == "T01" else 0.0), "FingerA": 0.05, "FingerB": 0.05}
        for link, parts in vis.items():
            UsdGeom.Xform.Define(stage, f"{troot}/{link}")
            for name, (wp, mat) in parts.items():
                mesh, _ = b.write_mesh(stage, f"{troot}/{link}/Visual/{name}", wp)
                b.bind(mesh.GetPrim(), mats[mat])
            prim = stage.GetPrimAtPath(f"{troot}/{link}")
            UsdPhysics.RigidBodyAPI.Apply(prim)
            UsdPhysics.MassAPI.Apply(prim).CreateMassAttr(masses[link])
            prim.AddAppliedSchema("PhysxRigidBodyAPI")
            prim.CreateAttribute("physxRigidBody:sleepThreshold", Sdf.ValueTypeNames.Float).Set(0.0)
            cx = UsdGeom.Xform.Define(stage, f"{troot}/{link}/Collision")
            cx.CreatePurposeAttr(UsdGeom.Tokens.guide)
            for name, xs, ys, zs in col[link]:
                b.add_box_collider(stage, str(cx.GetPath()), name, xs, ys, zs, (0, 0, 0),
                                   rubber if name == "Pad" else cm["Steel"], offsets=(0.001, 0.0))
        body = stage.GetPrimAtPath(f"{troot}/Body")
        for key, val in (("tool:id", tid), ("tool:type", t["type"]), ("tool:contaminationClass", t["contamination"]),
                         ("tool:utilities", t["utilities"])):
            body.CreateAttribute(key, Sdf.ValueTypeNames.String, custom=True).Set(val)
        body.CreateAttribute("tool:tcp_mm", Sdf.ValueTypeNames.Float, custom=True).Set(t["tcp"])
        body.CreateAttribute("tool:length_mm", Sdf.ValueTypeNames.Float, custom=True).Set(   # lift-out clearance
            max(zs[1] for boxes in col.values() for _, _, _, zs in boxes))
        UsdGeom.Xform.Define(stage, f"{troot}/Body/tool_coupler")
        tcp = UsdGeom.Xform.Define(stage, f"{troot}/Body/tcp")
        tcp.AddTranslateOp().Set(Gf.Vec3d(0, 0, t["tcp"] * MM))
        if tid == "T01":   # plain driven joints, no articulation: the coupler lock cannot attach articulation links
            for side, link in ((1, "FingerA"), (-1, "FingerB")):
                lim = (-STROKE * MM, 0.0) if side > 0 else (0.0, STROKE * MM)
                j = b._joint(stage, UsdPhysics.PrismaticJoint, f"{troot}/Joints/{link}Joint", f"{troot}/Body",
                             f"{troot}/{link}", Gf.Vec3f(0), Gf.Vec3f(0), "Y", lim)
                b._drive(j, "linear", stiffness=10000.0, damping=100.0, max_force=30.0, target=0.0)
            tcp.GetPrim().CreateAttribute("sdt:frameRole", Sdf.ValueTypeNames.String, custom=True).Set(
                "plate_grasp_frame: plate bottom = TCP z + 6 mm along the tool; jaws along +-Y (as on R01)")
    root = stage.GetPrimAtPath(ROOT)
    for key, val in (("sdt:componentId", "TCM01"),
                     ("sdt:designBasis", "project-owned proxy: Zimmer WMR2063-class coupler, fork docks; tool bodies "
                                         "dimensioned proxies (restricted CAD not acquired)")):
        root.CreateAttribute(key, Sdf.ValueTypeNames.String, custom=True).Set(val)
    root.CreateAttribute("magazine:dockPitch_mm", Sdf.ValueTypeNames.Float, custom=True).Set(PITCH)
    root.CreateAttribute("magazine:dockHeight_mm", Sdf.ValueTypeNames.Float, custom=True).Set(Z_DOCK)
    stage.GetRootLayer().Save()
    print(f"wrote {path}: {len(TOOLS)} tools, docks at x = {[dock_x(k) for k in range(5)]} mm, z {Z_DOCK} mm")


if __name__ == "__main__":
    main()
