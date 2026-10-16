"""Build the L21 Quality-Control and Calibration Station asset: parametric CAD -> STEP + layered OpenUSD.

Run with the CAD environment:  env_cad/bin/python assets/l21/build_l21.py

Implements the physical side of sdt/components/L21_QC_Calibration.yaml (artifacts: reference plate, fiducial /
calibration target, tool datum). Project-owned design; no moving parts, static colliders only.

  * reference nest (reference_plate_frame) holding the certified reference plate REF-L21-001, whose wells carry a
    dot-grid target of certified pitch (its optical content is modelled in twin/l17_optics.py)
  * QC nest (qc_nest_frame): a second SBS nest for plates under check
  * tool datum (tool_calibration_frame): a light-barrier fork with two crossed horizontal beams; a robot moves a
    tool through the beams and L21 locates the tool's real TCP from the beam interruptions
  * camera calibration target (camera_calibration_frame): an AprilTag 36h11 grid board
  * status display with lamps
Both nests use the shared static SBS nest (assets/common/static_nest.py). The station stands on a provisional
0.90 m side table, so the nest seats are at 0.972 m like every transfer nest in layout P1.
"""

import os
import sys

import cadquery as cq
import numpy as np
from PIL import Image
from pxr import Gf, Kind, Sdf, Usd, UsdGeom

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from common import twin_cad as tc  # noqa: E402
from common.static_nest import StaticNest  # noqa: E402
from common.twin_cad import (MM, add_box_collider, bind, box, cyl, define_contact_materials, define_materials,  # noqa: E402
                             rrect, to_front, write_mesh)

NAME = "L21_QC_Calibration"
ROOT = f"/{NAME}"
GENERATOR = "assets/l21/build_l21.py"
SEAT_Z = 72.0                                    # nest seat above the table top (0.972 m on the 0.90 m table)
BASE = dict(x=(-250.0, 250.0), y=(-80.0, 270.0), z=(0.0, 10.0))
REF = StaticNest(seat_z=SEAT_Z, tag_id=22, cx=-125.0, cy=0.0, prefix="Ref")
QC = StaticNest(seat_z=SEAT_Z, tag_id=23, cx=125.0, cy=0.0, prefix="Qc")
DATUM = (-125.0, 170.0, 120.0)                   # beam crossing (tool_calibration_frame)
BEAM_HALF = 90.0                                 # emitter / receiver distance from the crossing
POST = 12.0
BOARD = dict(c=(125.0, 170.0), size=(140.0, 100.0), h=20.0)
TAG_GRID = (4, 3, 30, 26.0, 32.0)                # cols, rows, first id, tag size, pitch (mm)
DISPLAY_X = 125.0                                # status display behind the board: clear of the datum sweeps
EXTRA_PBR = {
    "PowderWhite": ((0.86, 0.87, 0.87), 0.42, 0.0, {}),
    "LensAmber": ((0.6, 0.35, 0.02), 0.15, 0.0, {"emissive": ((1.0, 0.55, 0.05), 0.0)}),
    "BeamRed": ((0.6, 0.02, 0.02), 0.2, 0.0, {"emissive": ((1.0, 0.03, 0.02), 40.0)}),
}


def beams():
    """{beam: (emitter, receiver)} in mm: A along +X, B along +Y, crossing at DATUM."""
    x, y, z = DATUM
    return {"A": ((x - BEAM_HALF, y, z), (x + BEAM_HALF, y, z)), "B": ((x, y - BEAM_HALF, z), (x, y + BEAM_HALF, z))}


def posts():
    out = {}
    for b, (e, r) in beams().items():
        for role, (x, y, _) in (("Emitter", e), ("Receiver", r)):
            out[f"Beam{b}{role}"] = (x, y)
    return out


def board_texture(path):
    import cv2
    cols, rows, first, size, pitch = TAG_GRID
    px = 8                                                     # px per mm
    W, Hh = int(BOARD["size"][0] * px), int(BOARD["size"][1] * px)
    img = np.full((Hh, W), 255, np.uint8)
    d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    for r in range(rows):
        for c in range(cols):
            t = cv2.aruco.generateImageMarker(d, first + r * cols + c, int(size * px))
            cx = W / 2 + (c - (cols - 1) / 2) * pitch * px
            cy = Hh / 2 + (r - (rows - 1) / 2) * pitch * px
            x0, y0 = int(cx - size * px / 2), int(cy - size * px / 2)
            img[y0:y0 + t.shape[0], x0:x0 + t.shape[1]] = t
    Image.fromarray(img).convert("RGB").save(path)


def build_cad():
    p = {}
    B = BASE
    p["BasePlate"] = (box(sum(B["x"]) / 2, sum(B["y"]) / 2, sum(B["z"]) / 2, B["x"][1] - B["x"][0], B["y"][1] - B["y"][0],
                          B["z"][1] - B["z"][0]).edges("|Z").fillet(8).edges(">Z").fillet(1.5), "AnodizedGraphite")
    for nest in (REF, QC):
        p.update(nest.parts())
    # light-barrier fork: four posts, emitter / receiver heads facing the crossing, a base frame
    x, y, z = DATUM
    for name, (px_, py_) in posts().items():
        p[f"{name}Post"] = (box(px_, py_, (B["z"][1] + z + 14) / 2, POST, POST, z + 14 - B["z"][1]).edges("|Z").fillet(2),
                            "Aluminium")
        dx, dy = np.sign(x - px_), np.sign(y - py_)
        hx, hy = px_ + dx * (POST / 2 + 5), py_ + dy * (POST / 2 + 5)
        p[f"{name}Head"] = (box(hx, hy, z, 10 if dx else 16, 10 if dy else 16, 16).edges().fillet(1.5), "PlasticBlack")
        p[f"{name}Lens"] = (box(hx + dx * 5.2, hy + dy * 5.2, z, 0.4 if dx else 6, 0.4 if dy else 6, 6), "BeamRed")
    ring = cq.Workplane("XY").rect(2 * BEAM_HALF + 30, 2 * BEAM_HALF + 30).rect(2 * BEAM_HALF - 30, 2 * BEAM_HALF - 30)
    p["DatumFrame"] = (ring.extrude(6).translate((x, y, B["z"][1])), "Aluminium")
    p["DatumLabel"] = (box(x, y - BEAM_HALF - 12, B["z"][1] + 0.4, 60, 10, 0.8), "LabelWhite")
    # camera calibration target board
    bx, by = BOARD["c"]
    sx, sy = BOARD["size"]
    p["TargetBoard"] = (box(bx, by, B["z"][1] + BOARD["h"] / 2, sx + 10, sy + 10, BOARD["h"]).edges("|Z").fillet(3),
                        "AnodizedGraphite")
    # status display at the back
    X = DISPLAY_X
    p["DisplayPost"] = (box(X, 255, (B["z"][1] + 150) / 2, 20, 12, 150 - B["z"][1]), "Aluminium")
    p["DisplayPanel"] = (to_front(rrect(150, 70, 6, 8), X, 170, 249), "PowderWhite")
    p["DisplayLabel"] = (to_front(rrect(110, 14, 2, 0.8), X - 10, 188, 248.5), "LabelWhite")
    text = cq.Workplane("XY").text("L21  QC / CALIBRATION", 6.0, 0.35, kind="bold", halign="center", valign="center")
    p["DisplayText"] = (to_front(text, X - 10, 188, 247.8), "PlasticBlack")
    for i, lens in enumerate(("LensGreen", "LensAmber", "LensRed")):
        p[f"StatusLamp{i}"] = (to_front(cyl(6, 3, (0, 0, 0), (0, 0, 1)), X - 35 + 35 * i, 155, 248.5), lens)
    return p


def collision_boxes():
    B = BASE
    x, y, z = DATUM
    out = [("BasePlate", B["x"], B["y"], B["z"])]
    for name, (px_, py_) in posts().items():
        out.append((f"{name}Post", (px_ - POST / 2, px_ + POST / 2), (py_ - POST / 2, py_ + POST / 2), (B["z"][1], z + 14)))
        dx, dy = np.sign(x - px_), np.sign(y - py_)
        hx, hy = px_ + dx * (POST / 2 + 5), py_ + dy * (POST / 2 + 5)
        w, d = (10, 16) if dx else (16, 10)
        out.append((f"{name}Head", (hx - w / 2, hx + w / 2), (hy - d / 2, hy + d / 2), (z - 8, z + 8)))
    bx, by = BOARD["c"]
    sx, sy = BOARD["size"]
    out.append(("TargetBoard", (bx - sx / 2 - 5, bx + sx / 2 + 5), (by - sy / 2 - 5, by + sy / 2 + 5),
                (B["z"][1], B["z"][1] + BOARD["h"])))
    out.append(("Display", (DISPLAY_X - 75, DISPLAY_X + 75), (249, 261), (B["z"][1], 205)))
    return out


def build():
    os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
    tex = os.path.join(HERE, "textures")
    tc.make_textures(tex, [22, 23])
    board_texture(os.path.join(tex, "target_board.png"))
    tc.PBR.update(EXTRA_PBR)
    parts = build_cad()
    asm = cq.Assembly(name=NAME)
    for name, (wp, _) in parts.items():
        asm.add(wp, name=name)
    asm.export(os.path.join(HERE, "build", "l21.step"))

    st = tc.new_layer(os.path.join(HERE, "l21.usda"), NAME, GENERATOR)
    root = UsdGeom.Xform.Define(st, ROOT)
    rp = root.GetPrim()
    Usd.ModelAPI(rp).SetKind(Kind.Tokens.component)
    mats = define_materials(st, ROOT, sorted({m for _, m in parts.values()} | {"AprilTag"}), tag_id=22)
    # board material: the generated tag-grid texture
    from common.twin_cad import _set, _shader, A, F
    bmat, bsh = _shader(st, f"{ROOT}/Looks/TargetBoardPrint", "OmniPBR")
    _set(bsh, "diffuse_texture", A, Sdf.AssetPath("./textures/target_board.png"))
    _set(bsh, "reflection_roughness_constant", F, 0.7)
    tag23, t23 = _shader(st, f"{ROOT}/Looks/AprilTag23", "OmniPBR")
    _set(t23, "diffuse_texture", A, Sdf.AssetPath("./textures/apriltag36h11_23.png"))
    _set(t23, "reflection_roughness_constant", F, 0.6)
    UsdGeom.Xform.Define(st, f"{ROOT}/Visual")
    tri = 0
    for name, (wp, mat) in parts.items():
        m, n = write_mesh(st, f"{ROOT}/Visual/{name}", wp)
        bind(m.GetPrim(), mats[mat])
        tri += n

    def quad(path, cx, cy, z, hx, hy, mat):
        q = UsdGeom.Mesh.Define(st, path)
        q.CreatePointsAttr([Gf.Vec3f((cx - hx) * MM, (cy - hy) * MM, z * MM), Gf.Vec3f((cx + hx) * MM, (cy - hy) * MM, z * MM),
                            Gf.Vec3f((cx + hx) * MM, (cy + hy) * MM, z * MM), Gf.Vec3f((cx - hx) * MM, (cy + hy) * MM, z * MM)])
        q.CreateFaceVertexCountsAttr([4])
        q.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
        q.CreateNormalsAttr([Gf.Vec3f(0, 0, 1)] * 4)
        q.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
        UsdGeom.PrimvarsAPI(q).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex).Set(
            [Gf.Vec2f(0, 0), Gf.Vec2f(1, 0), Gf.Vec2f(1, 1), Gf.Vec2f(0, 1)])
        bind(q.GetPrim(), mat)

    for nest, mat in ((REF, mats["AprilTag"]), (QC, tag23)):
        tx, ty, tz, hs = nest.tag()
        quad(f"{ROOT}/Visual/{nest.prefix}AprilTag", tx, ty, tz, hs, hs, mat)
    bx, by = BOARD["c"]
    quad(f"{ROOT}/Visual/TargetPrint", bx, by, BASE["z"][1] + BOARD["h"] + 0.05, BOARD["size"][0] / 2,
         BOARD["size"][1] / 2, bmat)

    cmat = define_contact_materials(st, ROOT)
    col = UsdGeom.Xform.Define(st, f"{ROOT}/Collision")
    col.CreatePurposeAttr(UsdGeom.Tokens.guide)
    n = REF.add_colliders(st, col.GetPath(), cmat) + QC.add_colliders(st, col.GetPath(), cmat)
    for name, xs, ys, zs in collision_boxes():
        add_box_collider(st, col.GetPath(), name, xs, ys, zs, (0, 0, 0), cmat["Steel"])
        n += 1

    S, Db, St = Sdf.ValueTypeNames.String, Sdf.ValueTypeNames.Double, Sdf.ValueTypeNames.StringArray
    for k, t, v in (
            ("sdt:componentId", S, "L21"), ("sdt:canonicalName", S, "L21 Quality-Control and Calibration Station"),
            ("sdt:contract", S, "sdt/components/L21_QC_Calibration.yaml"),
            ("sdt:capabilities", St, ["run_reference_measurement", "validate_imager", "validate_barcode",
                                      "validate_tool_frame"]),
            ("sdt:bindingStatus", S, "articulated_v1"),
            ("sdt:designBasis", S, "project-owned QC bench: reference + QC nests, light-barrier tool datum, AprilTag "
                                   "target board; not a product model"),
            ("state:reference_artifact", S, "available"), ("state:calibration_status", S, "valid"),
            ("state:last_check", S, ""), ("state:result", S, ""), ("state:fault", S, ""), ("state:mode", S, "READY")):
        rp.CreateAttribute(k, t, custom=True).Set(v)
    rp.CreateAttribute("qc:beamZ_mm", Db, custom=True).Set(DATUM[2])

    def frame(name, pos, role):
        f = UsdGeom.Xform.Define(st, f"{ROOT}/{name}")
        f.AddTranslateOp().Set(Gf.Vec3d(*(np.array(pos, float) * MM)))
        f.GetPrim().CreateAttribute("sdt:frameRole", S, custom=True).Set(role)
        return f

    for nest, fname, role in ((REF, "reference_plate_frame", "Reference nest seat: home of the reference plate "
                                                             "(R02 place/pick target). +X along the plate long axis, A1 "
                                                             "at (-X,+Y)"),
                              (QC, "qc_nest_frame", "QC nest seat: plates under check (R02 place/pick target)")):
        f = frame(fname, (nest.cx, nest.cy, SEAT_Z), role)
        for k, t, v in nest.transfer_attributes():
            f.GetPrim().CreateAttribute(k, {"string": S, "double": Db}[t], custom=True).Set(v)
        for i, xyz in enumerate(nest.seat_sensors()):
            frame(f"{fname}_seat_sensor_{i}", xyz, "flush seat sensor window, looks +Z")
    frame("tool_calibration_frame", DATUM, "Light-barrier datum: crossing of beam A (+X) and beam B (+Y), both "
                                           "horizontal. A tool's TCP is located from the beam interruptions")
    for b, (e, r) in beams().items():
        frame(f"beam_{b}_emitter", e, f"beam {b} emitter lens point")
        frame(f"beam_{b}_receiver", r, f"beam {b} receiver lens point")
    frame("camera_calibration_frame", (bx, by, BASE["z"][1] + BOARD["h"] + 0.05),
          f"AprilTag 36h11 grid board centre: {TAG_GRID[0]}x{TAG_GRID[1]} tags, ids {TAG_GRID[2]}.."
          f"{TAG_GRID[2] + TAG_GRID[0] * TAG_GRID[1] - 1}, {TAG_GRID[3]:g} mm tags at {TAG_GRID[4]:g} mm pitch, +X right, "
          "+Y up in the image of a top-down camera")
    st.GetRootLayer().Save()
    print(f"L21: {len(parts)} parts, {tri} triangles, {n} colliders; nest seats at {SEAT_Z} mm, datum {DATUM} mm")


if __name__ == "__main__":
    build()
