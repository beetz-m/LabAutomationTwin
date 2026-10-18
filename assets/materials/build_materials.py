"""Shared lab material library: procedural textures + MDL materials (OmniSurface / OmniPBR / OmniGlass).

Writes assets/materials/lab_materials.usda (/Looks/<Name>) and assets/materials/textures/*.png. Assets do not copy
these materials: an asset defines <root>/Looks as a reference to this layer's /Looks and binds to <root>/Looks/<Name>,
so there is one source of truth and texture paths resolve against this layer (assets/common/meshkit.py does it).

Material treatment follows the Cell 01 rendering specification (section 18.2): brushed stainless with anisotropic
highlights and roughness streaks, anodised aluminium, physically plausible glass, white/grey polymer housings, black
technical polymer/rubber, culture-plate polymer and decals. UVs are written in metres divided by each material's tile
size (TILE_M), so every texture keeps its real-world scale.

Run: env_cad/bin/python assets/materials/build_materials.py
"""

import os

import numpy as np
from PIL import Image, ImageFilter
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "textures")
OUT = os.path.join(HERE, "lab_materials.usda")
F, C3, B, A, F2 = (Sdf.ValueTypeNames.Float, Sdf.ValueTypeNames.Color3f, Sdf.ValueTypeNames.Bool,
                   Sdf.ValueTypeNames.Asset, Sdf.ValueTypeNames.Float2)

# metres covered by one texture repeat (used by meshkit when it writes UVs)
TILE_M = {"StainlessBrushed": 0.6, "StainlessWorktop": 1.2, "EpoxyFloor": 4.0, "WallPaint": 3.0, "CeilingTile": 1.2,
          "FloorTapeHatch": 0.4, "OakVeneer": 1.0, "Cardboard": 0.5, "Galvanized": 0.8, "AluAnodized": 0.5,
          "VinylSkirting": 1.0, "PhenolicDark": 1.5, "FabricGrey": 0.3, "Concrete": 4.0}


# ------------------------------------------------------------------------------------------------ textures
def _save(name, arr, mode=None):
    os.makedirs(TEX, exist_ok=True)
    a = np.clip(arr, 0, 1)
    img = Image.fromarray((a * 255).astype(np.uint8), mode)
    img.save(os.path.join(TEX, name))


def _blur_noise(rng, n, sigma_px):
    img = Image.fromarray((rng.random((n, n)) * 255).astype(np.uint8))
    a = np.asarray(img.filter(ImageFilter.GaussianBlur(sigma_px)), np.float32) / 255
    a = (a - a.mean()) / (a.std() + 1e-6)
    return a


def _tileable_lowfreq(rng, n, cells):
    """Smooth tileable noise: bicubic upsampling of a wrapped coarse grid."""
    g = rng.random((cells, cells)).astype(np.float32)
    g = np.pad(g, 2, mode="wrap")
    big = np.asarray(Image.fromarray(g).resize(((cells + 4) * n // cells,) * 2, Image.BICUBIC))
    o = 2 * n // cells
    a = big[o:o + n, o:o + n]
    return (a - a.mean()) / (a.std() + 1e-6)


def make_textures():
    rng = np.random.default_rng(11)
    n = 1024
    # brushed stainless: streaks along u (tileable: circular convolution)
    noise = rng.normal(size=(n, n))
    k = np.zeros(n)
    k[:181] = 1 / 181
    streak = np.real(np.fft.ifft(np.fft.fft(noise, axis=1) * np.fft.fft(k)[None, :], axis=1))
    streak = (streak - streak.mean()) / streak.std()
    low = _tileable_lowfreq(rng, n, 6)
    fine = rng.normal(size=(n, n))
    _save("steel_brushed_rough.png", 0.30 + 0.035 * streak + 0.012 * fine - 0.02 * np.clip(low, 0, None))
    alb = 0.64 * (1 + 0.018 * streak + 0.008 * fine + 0.01 * low)
    _save("steel_brushed_albedo.png", np.stack([alb, alb * 0.995, alb * 0.985], -1) ** (1 / 2.2))
    # stainless worktop: finer, lighter brushing + faint wipe marks
    k2 = np.zeros(n)
    k2[:301] = 1 / 301
    s2 = np.real(np.fft.ifft(np.fft.fft(rng.normal(size=(n, n)), axis=1) * np.fft.fft(k2)[None, :], axis=1))
    s2 = (s2 - s2.mean()) / s2.std()
    wipe = _tileable_lowfreq(rng, n, 4)
    _save("steel_worktop_rough.png", 0.24 + 0.03 * s2 + 0.03 * np.clip(wipe, -1, 1))
    # epoxy floor: light grey with fine flake speckle and soft trowel mottling
    base = 0.62 + 0.025 * _tileable_lowfreq(rng, n, 8) + 0.012 * _tileable_lowfreq(rng, n, 32)
    flakes = rng.random((n, n))
    sp = np.where(flakes > 0.985, -0.12, 0.0) + np.where(flakes < 0.006, 0.10, 0.0)
    sp = np.asarray(Image.fromarray(((sp + 0.5) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6)),
                    np.float32) / 255 - 0.5
    g = np.clip(base + sp, 0, 1)
    _save("epoxy_albedo.png", np.stack([g * 0.985, g, g * 1.01], -1) ** (1 / 2.2))
    _save("epoxy_rough.png", 0.30 + 0.06 * _tileable_lowfreq(rng, n, 10) + 0.02 * rng.normal(size=(n, n)))
    # wall paint: very subtle roller texture
    w = 0.86 + 0.006 * _tileable_lowfreq(rng, n, 24) + 0.004 * rng.normal(size=(n, n))
    _save("wall_albedo.png", np.stack([w, w * 0.995, w * 0.975], -1) ** (1 / 2.2))
    # ceiling: 600 mm tiles (2 x 2 per texture) with recessed joints and a fine perforation
    c = np.full((n, n), 0.90, np.float32)
    c += 0.008 * rng.normal(size=(n, n))
    for i in (0, n // 2):
        c[:, max(i - 3, 0):i + 3] = 0.55
        c[max(i - 3, 0):i + 3, :] = 0.55
    c[:, -3:] = 0.55
    c[-3:, :] = 0.55
    yy, xx = np.mgrid[0:n, 0:n]
    perf = ((xx % 12 < 2) & (yy % 12 < 2))
    c[perf] -= 0.08
    _save("ceiling_albedo.png", np.stack([c, c, c * 0.99], -1) ** (1 / 2.2))
    # floor tape: 45 degree yellow/black hatch (tile 0.4 m -> 8 stripes)
    m = 512
    yy, xx = np.mgrid[0:m, 0:m]
    stripe = ((xx + yy) // (m // 8)) % 2 == 0
    col = np.where(stripe[..., None], np.array([0.95, 0.72, 0.02]), np.array([0.03, 0.03, 0.03]))
    _save("tape_hatch.png", col ** (1 / 2.2))
    # oak veneer
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    grain = np.sin((yy / n * 60 + 3 * _tileable_lowfreq(rng, n, 5)) * 2 * np.pi) * 0.5 + 0.5
    v = 0.55 + 0.08 * grain + 0.03 * _tileable_lowfreq(rng, n, 40)
    _save("oak_albedo.png", np.stack([v, v * 0.78, v * 0.55], -1) ** (1 / 2.2) * 0.95)
    # cardboard
    cb = 0.52 + 0.03 * _tileable_lowfreq(rng, 512, 16) + 0.02 * rng.normal(size=(512, 512))
    _save("cardboard_albedo.png", np.stack([cb, cb * 0.80, cb * 0.58], -1) ** (1 / 2.2))
    # galvanised steel (cable trays): spangle
    sp = _tileable_lowfreq(rng, 512, 48)
    gv = 0.66 + 0.04 * np.sign(sp) * np.abs(sp) ** 0.5
    _save("galv_albedo.png", np.stack([gv, gv, gv * 1.01], -1) ** (1 / 2.2))
    _save("galv_rough.png", 0.32 + 0.08 * (sp > 0))
    # fabric (chairs)
    yy, xx = np.mgrid[0:256, 0:256]
    weave = ((xx % 4 < 2) ^ (yy % 4 < 2)) * 0.04
    fb = 0.16 + weave + 0.02 * rng.normal(size=(256, 256))
    _save("fabric_albedo.png", np.stack([fb, fb * 1.02, fb * 1.06], -1) ** (1 / 2.2))
    # concrete (exterior ground seen through the windows)
    cc = 0.50 + 0.05 * _tileable_lowfreq(rng, 512, 12) + 0.03 * rng.normal(size=(512, 512))
    _save("concrete_albedo.png", np.stack([cc, cc, cc * 0.98], -1) ** (1 / 2.2))


# ------------------------------------------------------------------------------------------------ materials
def _shader(stage, path, mdl):
    mat = UsdShade.Material.Define(stage, path)
    sh = UsdShade.Shader.Define(stage, f"{path}/Shader")
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


def tex(name):
    return Sdf.AssetPath(f"./textures/{name}")


# OmniPBR: (diffuse, roughness, metallic, extra)
PBR = {
    "AluAnodized": ((0.80, 0.81, 0.82), 0.30, 1.0, {}),
    "AluDark": ((0.05, 0.05, 0.055), 0.35, 0.9, {}),
    "Chrome": ((0.85, 0.85, 0.86), 0.06, 1.0, {}),
    "PowderGrey": ((0.70, 0.71, 0.70), 0.42, 0.0, {}),       # RAL 7035 light grey
    "PowderWhite": ((0.84, 0.85, 0.85), 0.38, 0.0, {}),      # equipment housings
    "PowderAnthracite": ((0.085, 0.09, 0.10), 0.45, 0.0, {}),  # RAL 7016
    "PowderBlue": ((0.06, 0.22, 0.48), 0.40, 0.0, {}),
    "PlasticWhite": ((0.86, 0.86, 0.85), 0.32, 0.0, {}),
    "PlasticGrey": ((0.42, 0.43, 0.44), 0.40, 0.0, {}),
    "PlasticBlack": ((0.025, 0.025, 0.027), 0.42, 0.0, {}),
    "RubberBlack": ((0.018, 0.018, 0.018), 0.80, 0.0, {}),
    "PlasticYellow": ((0.92, 0.66, 0.02), 0.35, 0.0, {}),
    "PlasticRed": ((0.62, 0.025, 0.02), 0.28, 0.0, {}),
    "PlasticBlue": ((0.04, 0.22, 0.55), 0.35, 0.0, {}),
    "PlasticGreen": ((0.05, 0.40, 0.12), 0.35, 0.0, {}),
    "PlasticOrange": ((0.85, 0.30, 0.03), 0.35, 0.0, {}),
    "PhenolicLight": ((0.72, 0.73, 0.72), 0.35, 0.0, {}),
    "DoorLaminate": ((0.80, 0.80, 0.78), 0.45, 0.0, {}),
    "VinylSkirting": ((0.22, 0.23, 0.24), 0.55, 0.0, {}),
    "PaperWhite": ((0.90, 0.90, 0.88), 0.85, 0.0, {}),
    "Soil": ((0.10, 0.07, 0.05), 0.9, 0.0, {}),
    "Leaf": ((0.06, 0.20, 0.05), 0.45, 0.0, {}),
    "MediumPink": ((0.85, 0.30, 0.38), 0.15, 0.0, {}),
    "HdpeNatural": ((0.88, 0.88, 0.84), 0.40, 0.0, {}),
    "ScreenOff": ((0.01, 0.01, 0.012), 0.08, 0.0, {}),
    # emissive
    "LedPanel": ((0.95, 0.95, 0.95), 0.5, 0.0, {"emissive": ((1.0, 0.98, 0.95), 4000.0)}),
    "LedStrip": ((0.95, 0.95, 0.95), 0.5, 0.0, {"emissive": ((0.85, 0.92, 1.0), 2500.0)}),
    "StackGreen": ((0.05, 0.45, 0.1), 0.2, 0.0, {"emissive": ((0.15, 1.0, 0.3), 1500.0)}),
    "StackAmber": ((0.6, 0.35, 0.02), 0.2, 0.0, {"emissive": ((1.0, 0.55, 0.05), 0.0)}),
    "StackRed": ((0.5, 0.03, 0.02), 0.2, 0.0, {"emissive": ((1.0, 0.05, 0.03), 0.0)}),
    "StackBlue": ((0.03, 0.12, 0.5), 0.2, 0.0, {"emissive": ((0.2, 0.45, 1.0), 800.0)}),
    "AmrGlow": ((0.1, 0.5, 0.2), 0.2, 0.0, {"emissive": ((0.2, 1.0, 0.45), 1200.0)}),
    "IndicatorGreen": ((0.05, 0.4, 0.1), 0.2, 0.0, {"emissive": ((0.2, 1.0, 0.3), 600.0)}),
    "IndicatorRed": ((0.5, 0.03, 0.02), 0.2, 0.0, {"emissive": ((1.0, 0.06, 0.03), 600.0)}),
    "ExitGreen": ((0.05, 0.5, 0.2), 0.3, 0.0, {"emissive": ((0.2, 1.0, 0.5), 300.0)}),
}
TEXTURED = {  # OmniPBR with textures: (albedo, rough tex or None, roughness, metallic)
    "Galvanized": ("galv_albedo.png", "galv_rough.png", 0.35, 1.0),
    "OakVeneer": ("oak_albedo.png", None, 0.45, 0.0),
    "Cardboard": ("cardboard_albedo.png", None, 0.85, 0.0),
    "WallPaint": ("wall_albedo.png", None, 0.82, 0.0),
    "CeilingTile": ("ceiling_albedo.png", None, 0.85, 0.0),
    "FloorTapeHatch": ("tape_hatch.png", None, 0.45, 0.0),
    "FabricGrey": ("fabric_albedo.png", None, 0.9, 0.0),
    "Concrete": ("concrete_albedo.png", None, 0.85, 0.0),
}
SOLID_TAPE = {"FloorTapeYellow": (0.92, 0.70, 0.03), "FloorTapeWhite": (0.88, 0.88, 0.86),
              "FloorTapeGreen": (0.08, 0.50, 0.20), "FloorTapeRed": (0.75, 0.05, 0.04), "FloorTapeBlue": (0.05, 0.28, 0.65)}
GLASS = {  # OmniGlass: (color, ior, frosting roughness)
    "SafetyGlass": ((0.93, 0.97, 0.96), 1.52, 0.0),     # laminated safety glass, faint green edge tint
    "Polycarbonate": ((0.95, 0.96, 0.97), 1.585, 0.0),
    "GlassFrosted": ((0.95, 0.96, 0.97), 1.52, 0.35),
    "GlassAmber": ((0.65, 0.33, 0.06), 1.52, 0.0),
    "GlassClear": ((0.97, 0.98, 0.98), 1.52, 0.0),
    "WindowGlass": ((0.90, 0.95, 0.95), 1.52, 0.0),
    "PolystyreneClear": ((0.97, 0.97, 0.98), 1.59, 0.0),
}


def define(stage):
    UsdGeom.Scope.Define(stage, "/Looks")
    names = []
    # brushed stainless: OmniSurface metal with anisotropic highlight along u and streaked roughness
    for name, rough_tex, aniso in (("StainlessBrushed", "steel_brushed_rough.png", 0.55),
                                   ("StainlessWorktop", "steel_worktop_rough.png", 0.35)):
        mat, sh = _shader(stage, f"/Looks/{name}", "OmniSurface")
        _set(sh, "diffuse_reflection_color", C3, Gf.Vec3f(0.62, 0.62, 0.61))
        _set(sh, "metalness", F, 1.0)
        _set(sh, "specular_reflection_roughness", F, 0.30)
        _set(sh, "specular_reflection_roughness_image", A, tex(rough_tex), raw=True)
        _set(sh, "specular_reflection_anisotropy", F, aniso)
        names.append(name)
    mat, sh = _shader(stage, "/Looks/StainlessSatin", "OmniSurface")  # bead-blasted / machined parts
    _set(sh, "diffuse_reflection_color", C3, Gf.Vec3f(0.60, 0.60, 0.59))
    _set(sh, "metalness", F, 1.0)
    _set(sh, "specular_reflection_roughness", F, 0.42)
    names.append("StainlessSatin")
    # epoxy floor: speckled grey base under a glossy clear coat (the reflective lab floor of the visual target)
    mat, sh = _shader(stage, "/Looks/EpoxyFloor", "OmniSurface")
    _set(sh, "diffuse_reflection_color_image", A, tex("epoxy_albedo.png"))
    _set(sh, "specular_reflection_roughness", F, 0.45)
    _set(sh, "specular_reflection_roughness_image", A, tex("epoxy_rough.png"), raw=True)
    _set(sh, "coat_weight", F, 0.85)
    _set(sh, "coat_roughness", F, 0.06)
    names.append("EpoxyFloor")
    # phenolic / epoxy-resin lab worktop (dark), slight coat
    mat, sh = _shader(stage, "/Looks/PhenolicDark", "OmniSurface")
    _set(sh, "diffuse_reflection_color", C3, Gf.Vec3f(0.055, 0.058, 0.062))
    _set(sh, "specular_reflection_roughness", F, 0.38)
    _set(sh, "coat_weight", F, 0.3)
    _set(sh, "coat_roughness", F, 0.15)
    names.append("PhenolicDark")
    for name, (diff, rough, metal, extra) in PBR.items():
        mat, sh = _shader(stage, f"/Looks/{name}", "OmniPBR")
        _set(sh, "diffuse_color_constant", C3, Gf.Vec3f(*diff))
        _set(sh, "reflection_roughness_constant", F, rough)
        _set(sh, "metallic_constant", F, metal)
        if "emissive" in extra:
            col, inten = extra["emissive"]
            _set(sh, "enable_emission", B, True)
            _set(sh, "emissive_color", C3, Gf.Vec3f(*col))
            _set(sh, "emissive_intensity", F, inten)
        names.append(name)
    for name, (alb, rtex, rough, metal) in TEXTURED.items():
        mat, sh = _shader(stage, f"/Looks/{name}", "OmniPBR")
        _set(sh, "diffuse_texture", A, tex(alb))
        _set(sh, "reflection_roughness_constant", F, rough)
        if rtex:
            _set(sh, "reflectionroughness_texture", A, tex(rtex), raw=True)
            _set(sh, "reflection_roughness_texture_influence", F, 1.0)
        _set(sh, "metallic_constant", F, metal)
        names.append(name)
    for name, col in SOLID_TAPE.items():
        mat, sh = _shader(stage, f"/Looks/{name}", "OmniPBR")
        _set(sh, "diffuse_color_constant", C3, Gf.Vec3f(*col))
        _set(sh, "reflection_roughness_constant", F, 0.45)
        names.append(name)
    for name, (col, ior, frost) in GLASS.items():
        mat, sh = _shader(stage, f"/Looks/{name}", "OmniGlass")
        _set(sh, "glass_color", C3, Gf.Vec3f(*col))
        _set(sh, "glass_ior", F, ior)
        _set(sh, "frosting_roughness", F, frost)
        _set(sh, "thin_walled", B, False)
        names.append(name)
    return names


def main():
    make_textures()
    if os.path.exists(OUT):
        os.remove(OUT)
    stage = Usd.Stage.CreateNew(OUT)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    stage.SetMetadata("comment", "Generated by assets/materials/build_materials.py - edit the script, not this file.")
    names = define(stage)
    stage.SetDefaultPrim(stage.GetPrimAtPath("/Looks"))
    stage.GetRootLayer().Save()
    print(f"wrote {OUT}: {len(names)} materials; textures in {TEX}")


if __name__ == "__main__":
    main()
