"""Shared CAD -> USD helpers for the LabAutomationTwin station assets (H4, L09, ...).

Moved verbatim from assets/h4/build_h4.py (2026-10-15); only the texture directory, AprilTag id and the
generator name became parameters. Conventions: CadQuery in millimetres, USD in metres (MM), Z up,
one vertex set per B-rep face (crisp edges, smooth fillets), MDL materials (OmniPBR / OmniGlass),
collision proxies as parent-translate / child-scaled Cubes or exact convex hulls.
"""

import os

import cadquery as cq
import numpy as np
from PIL import Image
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

MM = 0.001
SBS = (127.76, 85.48, 14.35)   # ANSI/SLAS footprint and height


def box(cx, cy, cz, sx, sy, sz):
    return cq.Workplane("XY").box(sx, sy, sz).translate((cx, cy, cz))


def cyl(r, h, base, axis):
    return cq.Workplane("XY").add(cq.Solid.makeCylinder(r, h, cq.Vector(*base), cq.Vector(*axis)))


def to_front(wp, x, z, y_face):
    """Map a part built in local XY (extruding +Z) onto a -Y-facing plane at y_face."""
    return wp.rotate((0, 0, 0), (1, 0, 0), 90).translate((x, y_face, z))


def to_side(wp, y, z, x_face):
    """Map a part built in local XY (extruding +Z) onto the +X-facing plane at x_face (local x -> +Y)."""
    return wp.rotate((0, 0, 0), (1, 0, 0), 90).rotate((0, 0, 0), (0, 0, 1), 90).translate((x_face, y, z))


def rrect(w, h, r, t):
    return cq.Workplane("XY").rect(w, h).extrude(t).edges("|Z").fillet(r)


def build_plate():
    w, d, h = SBS
    skirt = box(0, 0, 3.0, w, d, 6.0).edges("|Z").fillet(3)
    top = box(0, 0, h / 2, w - 2.5, d - 2.5, h).edges("|Z").fillet(2.5)
    plate = skirt.union(top)
    notch = cq.Workplane("XY").polyline([(-w / 2 - 1, d / 2 - 5), (-w / 2 - 1, d / 2 + 1), (-w / 2 + 5, d / 2 + 1)])
    plate = plate.cut(notch.close().extrude(h + 1))  # A1 corner chamfer
    pts = [(-w / 2 + 14.38 + 9 * c, d / 2 - 11.24 - 9 * r) for r in range(8) for c in range(12)]
    plate = plate.faces(">Z").workplane().pushPoints(pts).hole(6.9, 10.9)
    medium = cq.Workplane("XY")
    for x, y in pts:
        medium = medium.add(cq.Solid.makeCylinder(3.4, 5.2, cq.Vector(x, y, h - 10.9 + 0.05)))
    return plate, medium


def tessellate(wp, offset=(0.0, 0.0, 0.0), tol=0.04, ang=0.12):
    pts, nrm, uvs, idx = [], [], [], []
    for solid in wp.vals():
        for face in solid.Faces():
            vs, tris = face.tessellate(tol, ang)
            if not tris:
                continue
            P = np.array([v.toTuple() for v in vs])
            N = np.array([face.normalAt(v).toTuple() for v in vs])
            T = np.array(tris)
            # winding must agree with the B-rep normal
            e = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
            flip = (e * N[T[:, 0]]).sum(1) < 0
            T[flip] = T[flip][:, [0, 2, 1]]
            # box-projected UVs (metres, one tile = 0.18 m), axis chosen per face
            axis = int(np.argmax(np.abs(N.mean(0))))
            uv_axes = {0: (1, 2), 1: (0, 2), 2: (0, 1)}[axis]
            base = sum(len(a) for a in pts)
            pts.append(P)
            nrm.append(N)
            uvs.append(P[:, uv_axes] * MM / 0.18)
            idx.append(T + base)
    P = (np.concatenate(pts) - np.array(offset)) * MM
    return P, np.concatenate(nrm), np.concatenate(uvs), np.concatenate(idx)


def write_mesh(stage, path, wp, offset=(0, 0, 0)):
    P, N, UV, T = tessellate(wp, offset)
    m = UsdGeom.Mesh.Define(stage, path)
    m.CreatePointsAttr([Gf.Vec3f(*p) for p in P])
    m.CreateNormalsAttr([Gf.Vec3f(*n) for n in N])
    m.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
    m.CreateFaceVertexCountsAttr([3] * len(T))
    m.CreateFaceVertexIndicesAttr(T.flatten().tolist())
    m.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    m.CreateExtentAttr([Gf.Vec3f(*P.min(0)), Gf.Vec3f(*P.max(0))])
    st = UsdGeom.PrimvarsAPI(m).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex)
    st.Set([Gf.Vec2f(*uv) for uv in UV])
    return m, len(T)


def make_textures(tex_dir, tag_ids=()):
    os.makedirs(tex_dir, exist_ok=True)
    rng = np.random.default_rng(4)
    n = 1024
    # brushed streaks: white noise smeared along u
    noise = rng.normal(size=(n, n))
    k = np.ones(241) / 241
    streak = np.apply_along_axis(lambda r: np.convolve(np.tile(r, 3), k, "same")[n:2 * n], 1, noise)
    streak = (streak - streak.mean()) / streak.std()
    fine = rng.normal(size=(n, n)) * 0.15
    # low-frequency smudges (handling marks) lower roughness a little
    low = np.array(Image.fromarray(rng.random((8, 8)).astype(np.float32)).resize((n, n), Image.BICUBIC))
    smudge = np.clip((low - 0.55) * 3, 0, 1)
    rough = np.clip(0.27 + 0.025 * streak + 0.01 * fine - 0.04 * smudge, 0.05, 1)
    Image.fromarray((rough * 255).astype(np.uint8)).save(os.path.join(tex_dir, "steel_brushed_roughness.png"))
    alb = np.clip(0.62 * (1 + 0.012 * streak + 0.006 * fine), 0, 1)
    rgb = np.stack([alb, alb * 0.995, alb * 0.985], -1) ** (1 / 2.2)
    Image.fromarray((rgb * 255).astype(np.uint8)).save(os.path.join(tex_dir, "steel_brushed_albedo.png"))
    import cv2  # AprilTag 36h11 (black border included; the white quiet zone is the tag plate)
    for tag_id in tag_ids:
        tag = cv2.aruco.generateImageMarker(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11), tag_id, 400)
        Image.fromarray(tag).convert("RGB").save(os.path.join(tex_dir, f"apriltag36h11_{tag_id}.png"))


def _shader(stage, mat_path, mdl):
    mat = UsdShade.Material.Define(stage, mat_path)
    sh = UsdShade.Shader.Define(stage, f"{mat_path}/Shader")
    sh.SetSourceAsset(Sdf.AssetPath(f"{mdl}.mdl"), "mdl")
    sh.SetSourceAssetSubIdentifier(mdl, "mdl")
    out = sh.CreateOutput("out", Sdf.ValueTypeNames.Token)
    mat.CreateSurfaceOutput("mdl").ConnectToSource(out)
    mat.CreateVolumeOutput("mdl").ConnectToSource(out)
    mat.CreateDisplacementOutput("mdl").ConnectToSource(out)
    return mat, sh


def _set(sh, name, typ, val, raw=False):
    a = sh.CreateInput(name, typ)
    a.Set(val)
    if raw:
        a.GetAttr().SetMetadata("colorSpace", "raw")


F, C3, B, A = Sdf.ValueTypeNames.Float, Sdf.ValueTypeNames.Color3f, Sdf.ValueTypeNames.Bool, Sdf.ValueTypeNames.Asset

PBR = {  # name: (diffuse, roughness, metallic, extra)
    "SteelSatin": ((0.60, 0.60, 0.59), 0.22, 1.0, {}),
    "Aluminium": ((0.70, 0.71, 0.72), 0.35, 1.0, {}),
    "Brass": ((0.78, 0.60, 0.32), 0.28, 1.0, {}),
    "AnodizedGraphite": ((0.10, 0.105, 0.11), 0.38, 0.8, {}),
    "RubberBlack": ((0.025, 0.025, 0.025), 0.75, 0.0, {}),
    "PlasticBlack": ((0.03, 0.03, 0.032), 0.45, 0.0, {}),
    "PeekNatural": ((0.78, 0.72, 0.60), 0.5, 0.0, {}),
    "LabelYellow": ((0.95, 0.72, 0.05), 0.4, 0.0, {}),
    "LabelWhite": ((0.86, 0.86, 0.85), 0.55, 0.0, {}),
    "SensorWindow": ((0.02, 0.02, 0.025), 0.08, 0.0, {}),
    "SensorLens": ((0.5, 0.04, 0.03), 0.1, 0.0, {"emissive": ((1.0, 0.05, 0.02), 30.0)}),
    "LedDiffuser": ((0.9, 0.9, 0.9), 0.4, 0.0, {"emissive": ((1.0, 0.97, 0.92), 2500.0)}),
    "LensRed": ((0.55, 0.03, 0.03), 0.15, 0.0, {"emissive": ((1.0, 0.025, 0.012), 0.0)}),
    "LensGreen": ((0.03, 0.4, 0.08), 0.15, 0.0, {"emissive": ((0.1, 1.0, 0.25), 0.0)}),
    "ButtonLens": ((0.75, 0.82, 0.9), 0.25, 0.0, {"emissive": ((0.55, 0.75, 1.0), 0.0)}),
}
GLASS = {  # name: (color, ior, frosting)
    "Polycarbonate": ((0.93, 0.95, 0.97), 1.585, 0.0),
    "Polystyrene": ((0.97, 0.97, 0.98), 1.59, 0.0),
    "CultureMedium": ((0.98, 0.42, 0.52), 1.335, 0.0),
}
CONTACT = {  # physics material: (static mu, dynamic mu, restitution)
    "Steel": (0.5, 0.4, 0.1),
    "Peek": (0.35, 0.3, 0.05),
    "Polystyrene": (0.4, 0.3, 0.05),
}


def define_materials(stage, root, names, tag_id=None):
    looks = f"{root}/Looks"
    UsdGeom.Scope.Define(stage, looks)
    mats = {}
    for name in names:
        path = f"{looks}/{name}"
        if name == "AprilTag":
            mat, sh = _shader(stage, path, "OmniPBR")
            _set(sh, "diffuse_texture", A, Sdf.AssetPath(f"./textures/apriltag36h11_{tag_id}.png"))
            _set(sh, "reflection_roughness_constant", F, 0.6)
        elif name == "SteelBrushed":
            mat, sh = _shader(stage, path, "OmniPBR")
            _set(sh, "diffuse_texture", A, Sdf.AssetPath("./textures/steel_brushed_albedo.png"))
            _set(sh, "reflectionroughness_texture", A, Sdf.AssetPath("./textures/steel_brushed_roughness.png"), raw=True)
            _set(sh, "reflection_roughness_texture_influence", F, 1.0)
            _set(sh, "metallic_constant", F, 1.0)
            _set(sh, "texture_scale", Sdf.ValueTypeNames.Float2, Gf.Vec2f(1, 1))
        elif name in GLASS:
            color, ior, frost = GLASS[name]
            mat, sh = _shader(stage, path, "OmniGlass")
            _set(sh, "glass_color", C3, Gf.Vec3f(*color))
            _set(sh, "glass_ior", F, ior)
            _set(sh, "frosting_roughness", F, frost)
            _set(sh, "thin_walled", B, False)
        else:
            diff, rough, metal, extra = PBR[name]
            mat, sh = _shader(stage, path, "OmniPBR")
            _set(sh, "diffuse_color_constant", C3, Gf.Vec3f(*diff))
            _set(sh, "reflection_roughness_constant", F, rough)
            _set(sh, "metallic_constant", F, metal)
            if "emissive" in extra:
                col, inten = extra["emissive"]
                _set(sh, "enable_emission", B, True)
                _set(sh, "emissive_color", C3, Gf.Vec3f(*col))
                _set(sh, "emissive_intensity", F, inten)
        mats[name] = mat
    return mats


def define_contact_materials(stage, root):
    out = {}
    for name, (mus, mud, rest) in CONTACT.items():
        mat = UsdShade.Material.Define(stage, f"{root}/PhysicsMaterials/{name}")
        api = UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
        api.CreateStaticFrictionAttr(mus)
        api.CreateDynamicFrictionAttr(mud)
        api.CreateRestitutionAttr(rest)
        out[name] = mat
    return out


def bind(prim, mat, purpose=None):
    api = UsdShade.MaterialBindingAPI.Apply(prim)
    if purpose:
        api.Bind(mat, UsdShade.Tokens.weakerThanDescendants, purpose)
    else:
        api.Bind(mat)


def add_box_collider(stage, parent, name, xs, ys, zs, origin, contact_mat=None, offsets=None):
    """Static-safe box collider: parent Xform carries the translate, child Cube carries the scale."""
    c = np.array([(xs[0] + xs[1]) / 2, (ys[0] + ys[1]) / 2, (zs[0] + zs[1]) / 2]) - np.array(origin)
    size = (xs[1] - xs[0], ys[1] - ys[0], zs[1] - zs[0])
    xf = UsdGeom.Xform.Define(stage, f"{parent}/{name}")
    xf.AddTranslateOp().Set(Gf.Vec3d(*(c * MM)))
    cube = UsdGeom.Cube.Define(stage, f"{parent}/{name}/Box")
    cube.CreateSizeAttr(1.0)
    cube.AddScaleOp().Set(Gf.Vec3f(*(np.array(size) * MM)))
    cube.CreatePurposeAttr(UsdGeom.Tokens.guide)
    prim = cube.GetPrim()
    UsdPhysics.CollisionAPI.Apply(prim)
    if contact_mat is not None:
        bind(prim, contact_mat, "physics")
    if offsets:
        prim.AddAppliedSchema("PhysxCollisionAPI")
        prim.CreateAttribute("physxCollision:contactOffset", F).Set(offsets[0])
        prim.CreateAttribute("physxCollision:restOffset", F).Set(offsets[1])
    return prim


def add_convex_collider(stage, path, solid, origin, contact_mat=None):
    """Convex-hull collider from a convex CadQuery solid (exact for guides, key, plate prism)."""
    m, _ = write_mesh(stage, path, solid, origin)
    m.CreatePurposeAttr(UsdGeom.Tokens.guide)
    prim = m.GetPrim()
    UsdPhysics.CollisionAPI.Apply(prim)
    UsdPhysics.MeshCollisionAPI.Apply(prim).CreateApproximationAttr(UsdPhysics.Tokens.convexHull)
    if contact_mat is not None:
        bind(prim, contact_mat, "physics")
    prim.AddAppliedSchema("PhysxCollisionAPI")
    prim.CreateAttribute("physxCollision:contactOffset", F).Set(0.001)
    prim.CreateAttribute("physxCollision:restOffset", F).Set(0.0)
    return prim


def new_layer(path, default_prim, generator="assets/*/build_*.py"):
    if os.path.exists(path):
        os.remove(path)
    stage = Usd.Stage.CreateNew(path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    stage.SetMetadata("comment", f"Generated by {generator} - edit the script, not this file.")
    stage.SetDefaultPrim(stage.OverridePrim(f"/{default_prim}"))
    return stage


def mm3(v):
    return Gf.Vec3f(*(np.array(v, dtype=float) * MM))


def _joint(stage, cls, path, body0, body1, pos0, pos1, axis=None, limits=None, rot=None):
    j = cls.Define(stage, path)
    if body0:
        j.CreateBody0Rel().SetTargets([body0])
    j.CreateBody1Rel().SetTargets([body1])
    j.CreateLocalPos0Attr(pos0)
    j.CreateLocalPos1Attr(pos1)
    q = rot or Gf.Quatf(1, 0, 0, 0)
    j.CreateLocalRot0Attr(q)
    j.CreateLocalRot1Attr(q)
    if axis:
        j.CreateAxisAttr(axis)
    if limits:
        j.CreateLowerLimitAttr(limits[0])
        j.CreateUpperLimitAttr(limits[1])
    return j


def _drive(joint, kind, stiffness, damping, max_force, target):
    d = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), kind)
    d.CreateTypeAttr("force")
    d.CreateStiffnessAttr(stiffness)
    d.CreateDampingAttr(damping)
    d.CreateMaxForceAttr(max_force)
    d.CreateTargetPositionAttr(target)
