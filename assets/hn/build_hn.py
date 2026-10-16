"""Build the R01/R02 handover nest (HN): a passive SBS plate nest on the central bench, shared by R01 and R02.

Run with the CAD environment:  env_cad/bin/python assets/hn/build_hn.py

Layout P1 puts the handover site at (-1.05, 0.55) on the bench, reachable by R01 (FR3) and by R02 at the west end
of its rail. The nest is the validated robot interface of the station shuttles (assets/common/sbs_shuttle.py):
8 corner guides with 34 deg lead-ins, A1 key, finger reliefs at the long sides, 4 flush seat sensors, AprilTag
36h11 #21 and a datum pin, on a fixed pedestal. Seat plane 40 mm above the worktop (0.96 m in Cell 01). Static
colliders only; the seat sensors are read by twin/hn_monitor.py. Project-owned design.
"""

import os
import sys

import cadquery as cq
import numpy as np
from pxr import Gf, Kind, Sdf, Usd, UsdGeom

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from common import twin_cad as tc  # noqa: E402
from common.static_nest import StaticNest  # noqa: E402
from common.twin_cad import MM, bind, define_contact_materials, define_materials, write_mesh  # noqa: E402

NAME, TAG_ID = "HandoverNest_R01_R02", 21
ROOT = f"/{NAME}"
SEAT_Z = 40.0                                           # mm above the worktop
NEST = StaticNest(seat_z=SEAT_Z, tag_id=TAG_ID)


def parts():
    p = NEST.parts()
    text = cq.Workplane("XY").text("HN  R01 | R02", 6.0, 0.3, kind="bold", halign="center", valign="center")
    p["Label"] = (text.rotate((0, 0, 0), (1, 0, 0), 90).translate((0, NEST.ped["y"][0], 12.0)), "LabelWhite")
    return p


def build():
    os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
    tc.make_textures(os.path.join(HERE, "textures"), [TAG_ID])
    p = parts()
    asm = cq.Assembly(name=NAME)
    for name, (wp, _) in p.items():
        asm.add(wp, name=name)
    asm.export(os.path.join(HERE, "build", "hn.step"))
    st = tc.new_layer(os.path.join(HERE, "hn.usda"), NAME, "assets/hn/build_hn.py")
    root = UsdGeom.Xform.Define(st, ROOT)
    Usd.ModelAPI(root.GetPrim()).SetKind(Kind.Tokens.component)
    mats = define_materials(st, ROOT, sorted({m for _, m in p.values()} | {"AprilTag"}), tag_id=TAG_ID)
    UsdGeom.Xform.Define(st, f"{ROOT}/Visual")
    for name, (wp, mat) in p.items():
        m, _ = write_mesh(st, f"{ROOT}/Visual/{name}", wp)
        bind(m.GetPrim(), mats[mat])
    tx, ty, tz, hs = (v * MM for v in NEST.tag())
    tag = UsdGeom.Mesh.Define(st, f"{ROOT}/Visual/AprilTag")
    tag.CreatePointsAttr([Gf.Vec3f(tx - hs, ty - hs, tz), Gf.Vec3f(tx + hs, ty - hs, tz), Gf.Vec3f(tx + hs, ty + hs, tz),
                          Gf.Vec3f(tx - hs, ty + hs, tz)])
    tag.CreateFaceVertexCountsAttr([4])
    tag.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    tag.CreateNormalsAttr([Gf.Vec3f(0, 0, 1)] * 4)
    tag.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
    UsdGeom.PrimvarsAPI(tag).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex).Set(
        [Gf.Vec2f(0, 0), Gf.Vec2f(1, 0), Gf.Vec2f(1, 1), Gf.Vec2f(0, 1)])
    bind(tag.GetPrim(), mats["AprilTag"])
    cmat = define_contact_materials(st, ROOT)
    col = UsdGeom.Xform.Define(st, f"{ROOT}/Collision")
    col.CreatePurposeAttr(UsdGeom.Tokens.guide)
    n = NEST.add_colliders(st, col.GetPath(), cmat)
    S = Sdf.ValueTypeNames.String
    rp = root.GetPrim()
    for k, v in (("sdt:componentId", "HN"), ("sdt:canonicalName", "R01/R02 handover nest"),
                 ("sdt:bindingStatus", "passive_v1"),
                 ("sdt:designBasis", "project-owned passive SBS nest (validated shuttle-nest interface)")):
        rp.CreateAttribute(k, S, custom=True).Set(v)

    def frame(name, pos, role):
        f = UsdGeom.Xform.Define(st, f"{ROOT}/{name}")
        f.AddTranslateOp().Set(Gf.Vec3d(*(np.array(pos, float) * MM)))
        f.GetPrim().CreateAttribute("sdt:frameRole", S, custom=True).Set(role)
        return f

    hf = frame("handover_frame", (0, 0, SEAT_Z), "SBS plate seat: R01 and R02 place/pick target. +X along the plate "
                                                 "long axis, A1 corner at (-X,+Y), +Z up")
    for k, t, v in NEST.transfer_attributes():
        hf.GetPrim().CreateAttribute(k, {"string": S, "double": Sdf.ValueTypeNames.Double}[t], custom=True).Set(v)
    for i, xyz in enumerate(NEST.seat_sensors()):
        frame(f"seat_sensor_{i}", xyz, "flush seat sensor window, looks +Z")
    st.GetRootLayer().Save()
    print(f"HN: {len(p)} parts, {n} colliders; seat {SEAT_Z} mm above the worktop")


if __name__ == "__main__":
    build()
