"""Build the R01 SBS plate gripper (proxy) as an articulated USD asset.

Cell 01 baseline: Zimmer WMR2063 tool changer + GEP2006 parallel gripper with custom SBS plate fingers.
The Zimmer CAD is restricted (not in the kit), so the changer and gripper body are dimensioned
PROXIES; the fingers are project-owned and designed against the H4 nest interface:

  * long-side grip: fingers pinch the plate's long sides (jaw axis = gripper +-Y), 30 mm wide,
    so they fit the nest's +-25 mm finger reliefs with 10 mm margin per side
  * 6 mm stroke per jaw: open 90.5 mm (2.5 mm clearance per side on the 85.48 mm plate),
    closed limit 78.5 mm, so the grip sits mid-stroke
  * rubber pads 26 x 10 mm; TCP (plate_grasp_frame) at the pad centre, 171 mm from the flange;
    with a seated plate the finger tips reach 2 mm below the seat, into the 5 mm reliefs

Frame: origin on the robot flange face, +Z along the tool (away from the robot), jaws along +-Y.
Links: GripperBody (attach to the robot flange with a FixedJoint in the scene), FingerA (+Y side),
FingerB (-Y side). No articulation root: the gripper joins the robot's articulation.

Run: env_cad/bin/python assets/gripper/build_plate_gripper.py  ->  assets/gripper/plate_gripper.usda
"""

import os
import sys

import cadquery as cq
from pxr import Gf, UsdGeom, UsdPhysics

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from common import twin_cad as b  # noqa: E402  (shared tessellation, materials and collider helpers)

MM = b.MM
ROOT = "/PlateGripper"
CHANGER_H, ADAPTER_H, BODY_H, JAW_H = 28.0, 8.0, 62.0, 10.0
Z_BODY0 = CHANGER_H + ADAPTER_H
Z_JAW0 = Z_BODY0 + BODY_H
SBS_W = b.SBS[1]                       # 85.48 mm: the dimension the fingers span
CLEAR, STROKE = 2.5, 6.0
PAD_IN_OPEN = SBS_W / 2 + CLEAR        # pad inner face |y| when open
PAD_T, PAD_W, PAD_H = 2.0, 26.0, 10.0
FINGER_T, FINGER_W = 6.0, 30.0
TCP_Z = 171.0
FINGER_TIP_Z = TCP_Z + 8.0


def parts():
    p = {}
    changer = b.cyl(31.5, CHANGER_H, (0, 0, 0), (0, 0, 1)).edges().chamfer(1.0)
    p["ToolChanger"] = (changer, "Aluminium", "GripperBody")
    p["Adapter"] = (b.box(0, 0, CHANGER_H + ADAPTER_H / 2, 50, 70, ADAPTER_H).edges("|Z").fillet(4), "AnodizedGraphite",
                    "GripperBody")
    p["Body"] = (b.box(0, 0, Z_BODY0 + BODY_H / 2, 50, 80, BODY_H).edges("|Z").fillet(3).edges(">Z or <Z").fillet(1),
                 "PlasticBlack", "GripperBody")
    for side, link in ((1, "FingerA"), (-1, "FingerB")):
        y_pad = side * (PAD_IN_OPEN + PAD_T / 2)
        y_fin = side * (PAD_IN_OPEN + PAD_T + FINGER_T / 2)
        jaw = b.box(0, side * (PAD_IN_OPEN + PAD_T + FINGER_T - 7), Z_JAW0 + JAW_H / 2, 20, 14, JAW_H)
        finger = b.box(0, y_fin, (Z_JAW0 + FINGER_TIP_Z) / 2, FINGER_W, FINGER_T, FINGER_TIP_Z - Z_JAW0)
        finger = finger.faces(">Z").edges("|X").chamfer(1.5)
        p[f"{link}Jaw"] = (jaw.edges("|Z").fillet(1), "SteelSatin", link)
        p[f"{link}Plate"] = (finger, "Aluminium", link)
        p[f"{link}Pad"] = (b.box(0, y_pad, TCP_Z, PAD_W, PAD_T, PAD_H).edges("|Y").fillet(1), "RubberBlack", link)
    return p


def colliders():
    out = {"GripperBody": [("Changer", (-31.5, 31.5), (-31.5, 31.5), (0, Z_BODY0)),
                           ("Body", (-25, 25), (-40, 40), (Z_BODY0, Z_JAW0))]}
    for side, link in ((1, "FingerA"), (-1, "FingerB")):
        def ys(a, c):
            return tuple(sorted((side * a, side * c)))
        out[link] = [
            ("Plate", (-FINGER_W / 2, FINGER_W / 2), ys(PAD_IN_OPEN + PAD_T, PAD_IN_OPEN + PAD_T + FINGER_T),
             (Z_JAW0, FINGER_TIP_Z)),
            ("Pad", (-PAD_W / 2, PAD_W / 2), ys(PAD_IN_OPEN, PAD_IN_OPEN + PAD_T), (TCP_Z - PAD_H / 2, TCP_Z + PAD_H / 2)),
        ]
    return out


def main():
    pp = parts()
    stage = b.new_layer(os.path.join(HERE, "plate_gripper.usda"), "PlateGripper")
    UsdGeom.Xform.Define(stage, ROOT)
    mats = b.define_materials(stage, ROOT, sorted({m for _, m, _ in pp.values()}))
    cm = b.define_contact_materials(stage, ROOT)
    rubber = b.UsdShade.Material.Define(stage, f"{ROOT}/PhysicsMaterials/Rubber")
    api = UsdPhysics.MaterialAPI.Apply(rubber.GetPrim())
    api.CreateStaticFrictionAttr(1.0)
    api.CreateDynamicFrictionAttr(0.9)
    api.CreateRestitutionAttr(0.05)
    for link in ("GripperBody", "FingerA", "FingerB"):
        UsdGeom.Xform.Define(stage, f"{ROOT}/{link}")
    for name, (wp, mat, link) in pp.items():
        mesh, _ = b.write_mesh(stage, f"{ROOT}/{link}/Visual/{name}", wp)
        b.bind(mesh.GetPrim(), mats[mat])
    mass = {"GripperBody": 0.95, "FingerA": 0.05, "FingerB": 0.05}
    for link, boxes in colliders().items():
        prim = stage.GetPrimAtPath(f"{ROOT}/{link}")
        UsdPhysics.RigidBodyAPI.Apply(prim)
        UsdPhysics.MassAPI.Apply(prim).CreateMassAttr(mass[link])
        col = UsdGeom.Xform.Define(stage, f"{ROOT}/{link}/Collision")
        col.CreatePurposeAttr(UsdGeom.Tokens.guide)
        for name, xs, ys, zs in boxes:
            b.add_box_collider(stage, str(col.GetPath()), name, xs, ys, zs, (0, 0, 0),
                               rubber if name == "Pad" else cm["Steel"], offsets=(0.001, 0.0))
    for side, link in ((1, "FingerA"), (-1, "FingerB")):
        lim = (-STROKE * MM, 0.0) if side > 0 else (0.0, STROKE * MM)  # closing = toward the centre
        j = b._joint(stage, UsdPhysics.PrismaticJoint, f"{ROOT}/Joints/{link}Joint", f"{ROOT}/GripperBody",
                     f"{ROOT}/{link}", Gf.Vec3f(0), Gf.Vec3f(0), "Y", lim)
        b._drive(j, "linear", stiffness=10000.0, damping=100.0, max_force=30.0, target=0.0)  # 30 N grip per jaw
    tcp = UsdGeom.Xform.Define(stage, f"{ROOT}/GripperBody/plate_grasp_frame")
    tcp.AddTranslateOp().Set(Gf.Vec3d(0, 0, TCP_Z * MM))
    tcp.GetPrim().CreateAttribute("sdt:frameRole", b.Sdf.ValueTypeNames.String, custom=True).Set(
        "TCP: plate footprint centre at pad mid-height when grasped (plate bottom = TCP z - 6 mm); jaws along +-Y")
    root = stage.GetPrimAtPath(ROOT)
    for k, v in (("sdt:designBasis", "proxy for Zimmer WMR2063 + GEP2006 (restricted CAD); fingers project-owned"),
                 ("sdt:gripMode", "SBS long-side pinch, 30 N per jaw, open 90.5 mm, stroke 6 mm per jaw")):
        root.CreateAttribute(k, b.Sdf.ValueTypeNames.String, custom=True).Set(v)
    stage.GetRootLayer().Save()
    print(f"wrote {os.path.join(HERE, 'plate_gripper.usda')}: {len(pp)} parts")


if __name__ == "__main__":
    main()
