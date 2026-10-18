"""3D representation of a culture run for rendering: what a camera sees (truth appearance) and what the SDT believes.

culture_render.usda  the physical plate on L12's plate nest (Cell 01: sdt:currentLocation of Plate_P17) with, per
                     experimental well, a procedural organoid (lobed body + necrotic core, OmniSurface with subsurface
                     scattering), loose debris and medium turbidity, all TIME-SAMPLED (time code = culture hours) from
                     the simulated culture: size from the Cell 01 morphology mapping, colour from viability / injury,
                     debris count and turbidity from the world. Appearance derives from state (Cell 01 USD rule 5).
                     Cell 01's semantic plate is aligned onto the physical plate (same wells, same place) and its
                     placeholder spheres / cylinders are hidden.
culture_viz.usda     the SDT visualisation layer (spec 18.3: analytical overlays belong to a separate layer): a disc
                     over each well coloured by the BELIEF viability (red -> green), a grey halo whose width grows
                     with the belief's 90 % interval, a purple ring once an anomaly is flagged, an orange ring for an
                     intervention whose record did not commit. Time-sampled from the SDT layer's belief.
lab_culture.usda     both, over scenes/lab_site.usda and the run's culture_sdt.usda (which carries Cell 01).
"""

from __future__ import annotations

import hashlib
import math
import os

import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

from twin.l17_optics import well_center

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PLATE_USD = os.path.join(ROOT, "assets", "labware", "plate_sbs96.usda")
WELL_BOTTOM_MM, PLATE_TOP_MM, MEDIUM_TOP_MM = 3.45, 14.35, 8.65
SEM = "/World/ExperimentalWorld/Plates/Plate_P17"
F, C3, B, A = Sdf.ValueTypeNames.Float, Sdf.ValueTypeNames.Color3f, Sdf.ValueTypeNames.Bool, Sdf.ValueTypeNames.Asset


def _shader(st, path, mdl):
    mat = UsdShade.Material.Define(st, path)
    sh = UsdShade.Shader.Define(st, f"{path}/Shader")
    sh.SetSourceAsset(Sdf.AssetPath(f"{mdl}.mdl"), "mdl")
    sh.SetSourceAssetSubIdentifier(mdl, "mdl")
    out = sh.CreateOutput("out", Sdf.ValueTypeNames.Token)
    for o in (mat.CreateSurfaceOutput("mdl"), mat.CreateVolumeOutput("mdl"), mat.CreateDisplacementOutput("mdl")):
        o.ConnectToSource(out)
    return mat, sh


def _mesh(st, path, P, N, T):
    m = UsdGeom.Mesh.Define(st, path)
    m.CreatePointsAttr(P.astype(np.float32))
    m.CreateNormalsAttr(N.astype(np.float32))
    m.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
    m.CreateFaceVertexCountsAttr(np.full(len(T), 3, np.int32))
    m.CreateFaceVertexIndicesAttr(T.astype(np.int32).ravel())
    m.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    m.CreateExtentAttr([Gf.Vec3f(*P.min(0)), Gf.Vec3f(*P.max(0))])
    return m


def lobed_sphere(seed, n_th=40, n_ph=24, lobes=0.06, flatten=0.85):
    """Unit organoid body: a sphere with low-order lobes and small buds (deterministic per well)."""
    rng = np.random.default_rng(seed)
    th = np.linspace(0, 2 * math.pi, n_th + 1)
    ph = np.linspace(0, math.pi, n_ph + 1)
    Th, Ph = np.meshgrid(th, ph, indexing="ij")
    r = np.ones_like(Th)
    for k in range(2, 7):
        r += rng.normal(0, lobes / k) * np.cos(k * Th + rng.random() * 6) * np.sin(Ph) ** 2
    for _ in range(5):                                       # buds
        bt, bp, bw = rng.random() * 2 * math.pi, rng.uniform(0.6, 2.2), rng.uniform(0.25, 0.4)
        ang = np.arccos(np.clip(np.sin(Ph) * np.sin(bp) * np.cos(Th - bt) + np.cos(Ph) * np.cos(bp), -1, 1))
        r += 0.12 * np.exp(-(ang / bw) ** 2)
    X = r * np.sin(Ph) * np.cos(Th)
    Y = r * np.sin(Ph) * np.sin(Th)
    Z = r * np.cos(Ph) * flatten
    P = np.stack([X, Y, Z], -1).reshape(-1, 3)
    m = n_ph + 1
    T = []
    for i in range(n_th):
        for j in range(n_ph):
            a, b, c, e = i * m + j, (i + 1) * m + j, (i + 1) * m + j + 1, i * m + j + 1
            T += [(a, b, c), (a, c, e)]
    T = np.array(T)
    N = np.zeros_like(P)
    fn = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    for k in range(3):
        np.add.at(N, T[:, k], fn)
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    if np.mean(np.sum(N * P, 1)) < 0:
        N, T = -N, T[:, [0, 2, 1]]
    return P, N, T


def unit_sphere(n=12):
    return lobed_sphere(0, n, n // 2, lobes=0.0, flatten=1.0)


def disc(r0, r1, seg=48):
    th = np.linspace(0, 2 * math.pi, seg + 1)[:-1]
    if r0 <= 0:
        P = np.concatenate([[[0, 0, 0]], np.stack([r1 * np.cos(th), r1 * np.sin(th), 0 * th], 1)])
        T = np.array([[0, 1 + i, 1 + (i + 1) % seg] for i in range(seg)])
    else:
        P = np.concatenate([np.stack([r1 * np.cos(th), r1 * np.sin(th), 0 * th], 1),
                            np.stack([r0 * np.cos(th), r0 * np.sin(th), 0 * th], 1)])
        T = np.array([t for i in range(seg) for t in ([i, (i + 1) % seg, seg + (i + 1) % seg],
                                                     [i, seg + (i + 1) % seg, seg + i])])
    return P, np.tile([0, 0, 1.0], (len(P), 1)), T


def organoid_color(V, I):
    healthy, injured = np.array([0.80, 0.70, 0.52]), np.array([0.36, 0.29, 0.24])
    w = float(np.clip(0.65 * (1 - V) + 0.35 * I, 0, 1))
    return (1 - w) * healthy + w * injured


def viability_color(v):
    v = float(np.clip(v, 0, 1))
    return np.array([min(1.0, 2 * (1 - v)), min(1.0, 2 * v), 0.12])


def plate_pose(cell01_scene):
    st = Usd.Stage.Open(cell01_scene)
    m = UsdGeom.XformCache().GetLocalToWorldTransform(st.GetPrimAtPath("/World/Cell01/Stations/L12_LiquidHandler/plate_nest"))
    p = np.array(m.ExtractTranslation())
    yaw = math.degrees(math.atan2(m.ExtractRotationMatrix()[0][1], m.ExtractRotationMatrix()[0][0]))
    sem_a01 = np.array(st.GetPrimAtPath(f"{SEM}/Wells/A01").GetAttribute("xformOp:translate").Get())
    return p + [0, 0, 0.0005], yaw, sem_a01


def _new(path, sublayers=()):
    if os.path.exists(path):
        os.remove(path)
    st = Usd.Stage.CreateNew(path)
    st.GetRootLayer().subLayerPaths = [os.path.relpath(p, os.path.dirname(path)) for p in sublayers]
    UsdGeom.SetStageUpAxis(st, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(st, 1.0)
    st.SetStartTimeCode(0)
    st.SetEndTimeCode(72)
    st.SetTimeCodesPerSecond(6)
    return st


def write_render_layers(out_dir, run, cell01_scene, lab_site):
    pos, yaw, sem_a01 = plate_pose(cell01_scene)
    mm = 1e-3
    # ---------------------------------------------------------------- appearance (truth)
    st = _new(os.path.join(out_dir, "culture_render.usda"))
    root = UsdGeom.Xform.Define(st, "/World/CultureRender")
    root.GetPrim().CreateAttribute("sdt:role", Sdf.ValueTypeNames.String, custom=True).Set(
        "appearance of the simulated culture (what a camera sees), time-sampled in culture hours")
    plate = UsdGeom.Xform.Define(st, "/World/CultureRender/Plate_P17")
    plate.AddTranslateOp().Set(Gf.Vec3d(*map(float, pos)))
    plate.AddRotateZOp().Set(float(yaw))
    vis = UsdGeom.Xform.Define(st, "/World/CultureRender/Plate_P17/Labware").GetPrim()
    vis.GetReferences().AddReference(os.path.relpath(PLATE_USD, out_dir))
    for sub in ("Collision", "PhysicsMaterials"):
        st.OverridePrim(f"/World/CultureRender/Plate_P17/Labware/{sub}").SetActive(False)
    # OmniGlass absorbs glass_color per `depth` (default 1 mm): 5 mm of medium rendered near-black. Phenol-red medium
    # in a 96-well column is light pink: absorption scale 20 mm (render appearance only)
    st.OverridePrim("/World/CultureRender/Plate_P17/Labware/Looks/CultureMedium/Shader").CreateAttribute(
        "inputs:depth", F, custom=False).Set(0.02)
    from pxr import UsdPhysics
    UsdPhysics.RigidBodyAPI.Apply(st.OverridePrim("/World/CultureRender/Plate_P17/Labware")).CreateRigidBodyEnabledAttr(False)
    sph_P, sph_N, sph_T = unit_sphere(10)
    for well, hist in run["truth"].items():
        u, v = well_center(well)
        seed = int.from_bytes(hashlib.sha256(f"Plate_P17/{well}/organoid".encode()).digest()[:8], "little")
        rng = np.random.default_rng(seed)
        off = rng.normal(0, 0.035, 2)
        base = f"/World/CultureRender/Plate_P17/Wells/{well}"
        w = UsdGeom.Xform.Define(st, base)
        w.AddTranslateOp().Set(Gf.Vec3d((u + off[0]) * mm, (v + off[1]) * mm, WELL_BOTTOM_MM * mm))
        org = UsdGeom.Xform.Define(st, f"{base}/Organoid")
        P, N, T = lobed_sphere(seed)
        _mesh(st, f"{base}/Organoid/Body", P, N, T)
        _mesh(st, f"{base}/Organoid/Core", sph_P * 0.42, sph_N, sph_T)
        sop = org.AddScaleOp()
        top = org.AddTranslateOp(opSuffix="lift")
        mat, sh = _shader(st, f"{base}/Looks/Organoid", "OmniSurface")
        sh.CreateInput("subsurface_weight", F).Set(0.55)
        sh.CreateInput("subsurface_scale", F).Set(0.0004)
        sh.CreateInput("specular_reflection_roughness", F).Set(0.32)
        col = sh.CreateInput("diffuse_reflection_color", C3)
        ssc = sh.CreateInput("subsurface_scattering_color", C3)
        UsdShade.MaterialBindingAPI.Apply(st.GetPrimAtPath(f"{base}/Organoid/Body")).Bind(mat)
        cmat, csh = _shader(st, f"{base}/Looks/Core", "OmniPBR")
        ccol = csh.CreateInput("diffuse_color_constant", C3)
        csh.CreateInput("reflection_roughness_constant", F).Set(0.6)
        UsdShade.MaterialBindingAPI.Apply(st.GetPrimAtPath(f"{base}/Organoid/Core")).Bind(cmat)
        deb = []
        for k in range(32):
            a, rr = rng.random() * 2 * math.pi, rng.uniform(1.1, 1.8)
            d = UsdGeom.Xform.Define(st, f"{base}/Debris/D{k:02d}")
            d.AddTranslateOp().Set(Gf.Vec3d(math.cos(a) * rr * 0.23 * mm, math.sin(a) * rr * 0.23 * mm, 0.008 * mm))
            d.AddScaleOp().Set(Gf.Vec3f(*(np.full(3, rng.uniform(0.008, 0.016) * mm))))
            _mesh(st, f"{base}/Debris/D{k:02d}/Geom", sph_P, sph_N, sph_T)
            UsdShade.MaterialBindingAPI.Apply(st.GetPrimAtPath(f"{base}/Debris/D{k:02d}/Geom")).Bind(cmat)
            deb.append(UsdGeom.Imageable(d.GetPrim()))
        turb = UsdGeom.Cylinder.Define(st, f"{base}/Turbidity")
        turb.CreateRadiusAttr(3.25 * mm)
        turb.CreateHeightAttr((MEDIUM_TOP_MM - WELL_BOTTOM_MM - 0.3) * mm)
        turb.CreateAxisAttr("Z")
        turb.AddTranslateOp().Set(Gf.Vec3d(-off[0] * mm, -off[1] * mm, (MEDIUM_TOP_MM - WELL_BOTTOM_MM) / 2 * mm))
        tmat, tsh = _shader(st, f"{base}/Looks/Turbid", "OmniGlass")
        tsh.CreateInput("glass_color", C3).Set(Gf.Vec3f(0.92, 0.86, 0.70))
        tsh.CreateInput("frosting_roughness", F).Set(0.6)
        UsdShade.MaterialBindingAPI.Apply(turb.GetPrim()).Bind(tmat)
        tvis = UsdGeom.Imageable(turb.GetPrim())
        for h in hist[::2]:
            t = h["t_h"]
            R = h["radius_um"] * mm * mm      # um -> m
            sop.Set(Gf.Vec3f(R, R, R), t)
            top.Set(Gf.Vec3d(0, 0, 0.82), t)                          # sits on the well bottom (local units)
            c = organoid_color(h["V"], h["I"])
            col.Set(Gf.Vec3f(*c), t)
            ssc.Set(Gf.Vec3f(*(0.6 * c + 0.4 * np.array([0.9, 0.55, 0.45]))), t)
            ccol.Set(Gf.Vec3f(*(np.array([0.30, 0.22, 0.16]) * (1.2 - h["core_od"]))), t)
            for k, dv in enumerate(deb):
                dv.CreateVisibilityAttr().Set("inherited" if k < h["debris"] * 0.8 else "invisible", t)
            tvis.CreateVisibilityAttr().Set("inherited" if h["B"] > 0.15 else "invisible", t)
    # Cell 01's semantic plate onto the physical one; hide its placeholder geometry
    phys_a01 = np.array(pos) + np.array([well_center("A01")[0] * mm, well_center("A01")[1] * mm, 0.0])
    sem = st.OverridePrim(SEM)
    sem_xf = UsdGeom.Xformable(sem)
    sem_xf.ClearXformOpOrder()
    sem_xf.AddTranslateOp().Set(Gf.Vec3d(*map(float, phys_a01 + [0, 0, WELL_BOTTOM_MM * mm] - sem_a01)))
    stg = Usd.Stage.Open(cell01_scene)
    for w in stg.GetPrimAtPath(f"{SEM}/Wells").GetChildren():
        UsdGeom.Imageable(st.OverridePrim(f"{w.GetPath()}/Physical")).CreateVisibilityAttr().Set("invisible")
    st.GetRootLayer().Save()

    # ---------------------------------------------------------------- SDT visualisation (belief)
    sv = _new(os.path.join(out_dir, "culture_viz.usda"))
    vroot = UsdGeom.Xform.Define(sv, "/World/SDTViz/Plate_P17")
    vroot.AddTranslateOp().Set(Gf.Vec3d(*map(float, pos + [0, 0, (PLATE_TOP_MM + 1.2) * mm])))
    vroot.AddRotateZOp().Set(float(yaw))
    vroot.GetPrim().CreateAttribute("sdt:role", Sdf.ValueTypeNames.String, custom=True).Set(
        "SDT visualisation layer: belief viability (disc colour), 90 % interval (halo), anomaly / unverified rings")
    Pd, Nd, Td = disc(0, 2.4 * mm)
    Ph, Nh, Th = disc(0, 1.0)
    Pr, Nr, Tr = disc(3.1 * mm, 3.6 * mm)
    for well, hist in run["belief"].items():
        u, v = well_center(well)
        base = f"/World/SDTViz/Plate_P17/{well}"
        g = UsdGeom.Xform.Define(sv, base)
        g.AddTranslateOp().Set(Gf.Vec3d(u * mm, v * mm, 0))
        halo = _mesh(sv, f"{base}/Halo", Ph, Nh, Th)
        hs = UsdGeom.Xformable(halo).AddScaleOp()
        _mesh(sv, f"{base}/Disc", Pd + [0, 0, 0.05 * mm], Nd, Td)
        dm, ds = _shader(sv, f"{base}/Looks/Disc", "OmniPBR")
        ds.CreateInput("enable_emission", B).Set(True)
        dcol = ds.CreateInput("emissive_color", C3)
        dcol2 = ds.CreateInput("diffuse_color_constant", C3)
        ds.CreateInput("emissive_intensity", F).Set(900.0)
        UsdShade.MaterialBindingAPI.Apply(sv.GetPrimAtPath(f"{base}/Disc")).Bind(dm)
        hm, hsh = _shader(sv, f"{base}/Looks/Halo", "OmniPBR")
        hsh.CreateInput("diffuse_color_constant", C3).Set(Gf.Vec3f(0.85, 0.87, 0.9))
        hsh.CreateInput("enable_emission", B).Set(True)
        hsh.CreateInput("emissive_color", C3).Set(Gf.Vec3f(0.85, 0.87, 0.9))
        hsh.CreateInput("emissive_intensity", F).Set(250.0)
        UsdShade.MaterialBindingAPI.Apply(halo.GetPrim()).Bind(hm)
        for h in hist:
            t = h["t_h"]
            r = (2.4 + 0.25 + 12.0 * (h["V"]["p95"] - h["V"]["p05"])) * mm
            hs.Set(Gf.Vec3f(r, r, 1.0), t)
            c = viability_color(h["V"]["mean"])
            dcol.Set(Gf.Vec3f(*c), t)
            dcol2.Set(Gf.Vec3f(*c), t)
        an = run["anomalies"].get(well)
        rej = [e for e in run["interventions"] if e["well"] == well and not e["committed"]]
        for name, cond_t, col_ in (("AnomalyRing", an["t_h"] if an else None, (0.65, 0.2, 0.9)),
                                   ("UnverifiedRing", rej[0]["t_h"] if rej else None, (1.0, 0.55, 0.05))):
            if cond_t is None:
                continue
            ring = _mesh(sv, f"{base}/{name}", Pr + [0, 0, 0.1 * mm], Nr, Tr)
            rm, rs = _shader(sv, f"{base}/Looks/{name}", "OmniPBR")
            rs.CreateInput("enable_emission", B).Set(True)
            rs.CreateInput("emissive_color", C3).Set(Gf.Vec3f(*col_))
            rs.CreateInput("diffuse_color_constant", C3).Set(Gf.Vec3f(*col_))
            rs.CreateInput("emissive_intensity", F).Set(1200.0)
            UsdShade.MaterialBindingAPI.Apply(ring.GetPrim()).Bind(rm)
            va = UsdGeom.Imageable(ring.GetPrim()).CreateVisibilityAttr()
            va.Set("invisible", 0.0)
            va.Set("inherited", float(cond_t))
    sv.GetRootLayer().Save()

    # ---------------------------------------------------------------- composed scene for rendering
    comp = _new(os.path.join(out_dir, "lab_culture.usda"),
                [os.path.join(out_dir, "culture_viz.usda"), os.path.join(out_dir, "culture_render.usda"), lab_site,
                 os.path.join(out_dir, "culture_sdt.usda")])
    comp.SetDefaultPrim(comp.OverridePrim("/World"))
    comp.GetRootLayer().comment = ("Lab + culture run: SDT viz layer, culture appearance layer, lab site layer, culture SDT "
                                   "layer (over Cell 01). Time code = culture hours.")
    comp.GetRootLayer().Save()
    return dict(plate_pos=pos.tolist(), yaw=yaw)
