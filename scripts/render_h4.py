"""Path-traced stills of the H4 Quarantine Station on a lab bench.

Builds a throwaway render stage (floor, wall, bench, lights, camera), references
assets/h4/h4.usda and the SBS plate prop, then renders a list of states. Each state is
reached through the twin's own physics (joint drive targets + stepping), so the images
show simulated poses. Nothing in assets/ is modified.

Usage: python scripts/render_h4.py [out_dir] [--quick]
"""

import math
import os
import sys
import time

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
H4 = os.path.join(ROOT, "assets/h4/h4.usda")
PLATE = os.path.join(ROOT, "assets/labware/plate_sbs96.usda")
QUICK = "--quick" in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = os.path.abspath(args[0] if args else os.path.join(ROOT, "renders"))
RES = (960, 600) if QUICK else (1920, 1200)
SPP, SUBFRAMES = (8, 8) if QUICK else (16, 24)
BENCH_Z = 0.90

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True, "renderer": "PathTracing", "width": RES[0], "height": RES[1]})

import carb  # noqa: E402
import numpy as np  # noqa: E402
import omni.replicator.core as rep  # noqa: E402
import omni.usd  # noqa: E402
from PIL import Image  # noqa: E402
import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
from isaacsim.core.experimental.prims import Articulation, RigidPrim  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402
from pxr import Gf, PhysxSchema, Sdf, UsdGeom, UsdLux, UsdPhysics, UsdShade  # noqa: E402

s = carb.settings.get_settings()
s.set("/rtx/rendermode", "PathTracing")
s.set("/rtx/pathtracing/spp", SPP)
s.set("/rtx/pathtracing/totalSpp", SPP * SUBFRAMES)
s.set("/rtx/pathtracing/maxBounces", 8)
s.set("/rtx/pathtracing/maxSpecularAndTransmissionBounces", 10)
s.set("/rtx/pathtracing/optixDenoiser/enabled", True)

omni.usd.get_context().new_stage()
for _ in range(5):
    app.update()
stage = omni.usd.get_context().get_stage()
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)
UsdGeom.Xform.Define(stage, "/World")


def look_at_xform(prim, eye, target):
    m = Gf.Matrix4d().SetLookAt(Gf.Vec3d(*eye), Gf.Vec3d(*target), Gf.Vec3d(0, 0, 1)).GetInverse()
    xf = UsdGeom.Xformable(prim)
    xf.ClearXformOpOrder()
    xf.AddTransformOp().Set(m)


def pbr(path, diffuse, rough, metal=0.0):
    mat = UsdShade.Material.Define(stage, path)
    sh = UsdShade.Shader.Define(stage, path + "/Shader")
    sh.SetSourceAsset(Sdf.AssetPath("OmniPBR.mdl"), "mdl")
    sh.SetSourceAssetSubIdentifier("OmniPBR", "mdl")
    sh.CreateInput("diffuse_color_constant", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*diffuse))
    sh.CreateInput("reflection_roughness_constant", Sdf.ValueTypeNames.Float).Set(rough)
    sh.CreateInput("metallic_constant", Sdf.ValueTypeNames.Float).Set(metal)
    out = sh.CreateOutput("out", Sdf.ValueTypeNames.Token)
    for o in (mat.CreateSurfaceOutput("mdl"), mat.CreateVolumeOutput("mdl"), mat.CreateDisplacementOutput("mdl")):
        o.ConnectToSource(out)
    return mat


def slab(path, center, size, mat):
    c = UsdGeom.Cube.Define(stage, path)
    c.CreateSizeAttr(1.0)
    c.AddTranslateOp().Set(Gf.Vec3d(*center))
    c.AddScaleOp().Set(Gf.Vec3f(*size))
    UsdShade.MaterialBindingAPI.Apply(c.GetPrim()).Bind(mat)


def collider(path, center, size):
    xf = UsdGeom.Xform.Define(stage, path)
    xf.AddTranslateOp().Set(Gf.Vec3d(*center))
    c = UsdGeom.Cube.Define(stage, path + "/Box")
    c.CreateSizeAttr(1.0)
    c.AddScaleOp().Set(Gf.Vec3f(*size))
    c.CreatePurposeAttr(UsdGeom.Tokens.guide)
    UsdPhysics.CollisionAPI.Apply(c.GetPrim())


scene = UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
scene.CreateGravityDirectionAttr(Gf.Vec3f(0, 0, -1))
scene.CreateGravityMagnitudeAttr(9.81)
PhysxSchema.PhysxSceneAPI.Apply(scene.GetPrim()).CreateTimeStepsPerSecondAttr(240)
collider("/World/Colliders/Floor", (0, 0, -0.01), (8, 8, 0.02))
collider("/World/Colliders/BenchTop", (0, 0.05, BENCH_Z - 0.015), (1.8, 0.75, 0.03))

# --- room and bench --------------------------------------------------------------------------
floor = pbr("/World/Looks/EpoxyFloor", (0.42, 0.44, 0.45), 0.35)
wall = pbr("/World/Looks/WallPaint", (0.80, 0.80, 0.78), 0.85)
top = pbr("/World/Looks/PhenolicTop", (0.035, 0.037, 0.04), 0.32)
carcass = pbr("/World/Looks/PowderCoat", (0.70, 0.72, 0.73), 0.5)
trim = pbr("/World/Looks/Aluminium", (0.75, 0.75, 0.76), 0.3, 1.0)
slab("/World/Room/Floor", (0, 0, -0.01), (8, 8, 0.02), floor)
slab("/World/Room/BackWall", (0, 0.75, 1.5), (8, 0.05, 3.0), wall)
slab("/World/Bench/Top", (0, 0.05, BENCH_Z - 0.015), (1.8, 0.75, 0.03), top)
slab("/World/Bench/Carcass", (0, 0.09, (BENCH_Z - 0.03) / 2 + 0.06), (1.76, 0.66, BENCH_Z - 0.15), carcass)
slab("/World/Bench/Plinth", (0, 0.12, 0.03), (1.74, 0.6, 0.06), top)
for i, x in enumerate((-0.44, 0.44)):
    slab(f"/World/Bench/DrawerGap{i}", (x, -0.241, 0.62), (0.84, 0.004, 0.004), top)
    slab(f"/World/Bench/Handle{i}", (x, -0.255, 0.70), (0.25, 0.012, 0.012), trim)
slab("/World/Bench/DoorGap", (0, -0.241, 0.38), (0.004, 0.004, 0.58), top)

# --- assets ---------------------------------------------------------------------------------
h4 = UsdGeom.Xform.Define(stage, "/World/H4_Quarantine")
h4.GetPrim().GetReferences().AddReference(H4)
h4.AddTranslateOp().Set(Gf.Vec3d(0.05, 0.0, BENCH_Z))
h4.AddRotateZOp().Set(0.0)
plate = UsdGeom.Xform.Define(stage, "/World/Plate")
plate.GetPrim().GetReferences().AddReference(PLATE)
plate.AddTranslateOp().Set(Gf.Vec3d(3.0, 3.0, 0.0))  # parked off-camera on the floor
plate.AddOrientOp().Set(Gf.Quatf(1, 0, 0, 0))
PARK = [3.0, 3.0, 0.0]

# --- lights ---------------------------------------------------------------------------------
dome = UsdLux.DomeLight.Define(stage, "/World/Lights/Dome")
dome.CreateIntensityAttr(220)
dome.CreateColorAttr(Gf.Vec3f(0.92, 0.95, 1.0))
for i, x in enumerate((-0.9, 0.9)):
    panel = UsdLux.RectLight.Define(stage, f"/World/Lights/Ceiling{i}")
    panel.CreateWidthAttr(1.2)
    panel.CreateHeightAttr(0.6)
    panel.CreateIntensityAttr(9000)
    panel.CreateColorTemperatureAttr(4300)
    panel.CreateEnableColorTemperatureAttr(True)
    panel.AddTranslateOp().Set(Gf.Vec3d(x, -0.4, 2.8))
key = UsdLux.RectLight.Define(stage, "/World/Lights/Key")
key.CreateWidthAttr(0.9)
key.CreateHeightAttr(0.9)
key.CreateIntensityAttr(5000)
key.CreateColorTemperatureAttr(5200)
key.CreateEnableColorTemperatureAttr(True)
look_at_xform(key.GetPrim(), (-1.4, -1.3, 1.9), (0.05, 0.0, 1.0))
rim = UsdLux.RectLight.Define(stage, "/World/Lights/Rim")
rim.CreateWidthAttr(0.5)
rim.CreateHeightAttr(0.5)
rim.CreateIntensityAttr(7000)
look_at_xform(rim.GetPrim(), (1.2, 0.6, 1.6), (0.05, 0.0, 1.0))

cam = UsdGeom.Camera.Define(stage, "/World/RenderCam")
cam.CreateHorizontalApertureAttr(36.0)
cam.CreateVerticalApertureAttr(36.0 * RES[1] / RES[0])
cam.CreateFStopAttr(0.0)  # DOF off: Kit lens scale with metersPerUnit=1 makes any f-stop wildly blurry
cam.CreateClippingRangeAttr(Gf.Vec2f(0.01, 100))


def set_state(door_deg, presented, locked, occupied, red, green):
    p = stage.GetPrimAtPath
    # drive the twin into the state through its joints, in the controller's interlock order:
    # bolt out -> shuttle in -> door -> shuttle out -> bolt in
    if not locked:
        drive_joint("LatchSlide", 0.0065)
        SimulationManager.step(steps=120)
    if not presented:
        drive_joint("ShuttleSlide", 0.0)
        SimulationManager.step(steps=480)
    drive_joint("DoorHinge", math.radians(door_deg))
    SimulationManager.step(steps=720)
    if presented:
        drive_joint("ShuttleSlide", 0.150)
        SimulationManager.step(steps=480)
    if locked:
        drive_joint("LatchSlide", 0.0)
        SimulationManager.step(steps=120)
    p("/World/H4_Quarantine/Looks/ButtonLens/Shader").GetAttribute("inputs:emissive_intensity").Set(
        400.0 if green else 0.0)
    for lens, on in (("LensRed", red), ("LensGreen", green)):
        sh = p(f"/World/H4_Quarantine/Looks/{lens}/Shader")
        sh.GetAttribute("inputs:emissive_intensity").Set(3000.0 if on else 0.0)
    # plate is dropped onto the (presented or stowed) nest when occupied, otherwise parked out of view
    frame = "transfer_nest" if presented else "quarantine_nest"
    nest = UsdGeom.Xformable(p(f"/World/H4_Quarantine/{frame}")).ComputeLocalToWorldTransform(0)
    pos = (np.array(nest.ExtractTranslation()) + [0, 0, 0.002]).tolist() if occupied else PARK
    plate_rp.set_world_poses(positions=[pos], orientations=[[1, 0, 0, 0]])
    plate_rp.set_velocities(linear_velocities=[[0, 0, 0]], angular_velocities=[[0, 0, 0]])
    SimulationManager.step(steps=240)
    q = art.get_dof_positions().numpy()[0]
    print(f"[render_h4] state door={math.degrees(q[DOF['DoorHinge']]):.1f}deg "
          f"shuttle={q[DOF['ShuttleSlide']] * 1e3:.1f}mm bolt={q[DOF['LatchSlide']] * 1e3:.2f}mm occupied={occupied}")


def set_camera(eye, target, focal):
    look_at_xform(cam.GetPrim(), eye, target)
    cam.GetFocalLengthAttr().Set(focal)
    cam.GetFocusDistanceAttr().Set((Gf.Vec3d(*eye) - Gf.Vec3d(*target)).GetLength())


SHOTS = [
    # name, (door, presented, locked, occupied, red, green), eye, target, focal
    ("h4_presented_loaded", (100, True, False, True, False, True), (0.60, -1.00, 1.36), (0.03, -0.17, 0.97), 50),
    ("h4_quarantined_closed", (0, False, True, True, True, False), (-0.62, -1.05, 1.32), (0.05, -0.08, 0.99), 55),
    ("h4_nest_detail", (100, True, False, False, False, True), (0.30, -0.52, 1.20), (0.05, -0.216, 0.972), 60),
    ("h4_control_panel", (0, False, False, False, False, True), (0.62, -0.52, 1.10), (0.20, -0.075, 1.0), 70),
]

app_utils.play(commit=True)
art = Articulation("/World/H4_Quarantine")
DOF = {n: i for i, n in enumerate(art.dof_names)}
plate_rp = RigidPrim("/World/Plate")


def drive_joint(joint, value):
    art.set_dof_position_targets(np.array([[value]], dtype=np.float32), dof_indices=[DOF[joint]])


rp = rep.create.render_product(str(cam.GetPath()), RES)
rgb = rep.AnnotatorRegistry.get_annotator("rgb")
rgb.attach(rp)
os.makedirs(OUT, exist_ok=True)
for _ in range(10):
    app.update()

for name, state, eye, target, focal in SHOTS:
    t0 = time.time()
    set_state(*state)
    set_camera(eye, target, focal)
    rep.orchestrator.step(rt_subframes=SUBFRAMES)
    img = np.asarray(rgb.get_data())[..., :3].astype(np.uint8)
    path = os.path.join(OUT, f"{name}.png")
    Image.fromarray(img).save(path)
    print(f"[render_h4] {path}  ({time.time() - t0:.0f}s, mean={img.mean():.0f})")

rep.orchestrator.wait_until_complete()
app.close()
