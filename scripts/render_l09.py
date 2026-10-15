"""Path-traced stills of the L09 plate hotel in operation, posed by its own controller and physics.

Shots: presented nest with a plate; cutaway (housing hidden) with stored plates and the fork carrying a plate
mid-retrieve; service door open over the loaded cassette. Rendering uses delta_time=0 so the simulation
does not advance while samples accumulate. Nothing in assets/ is modified.
Usage: python scripts/render_l09.py [out_dir] [--quick]
"""

import math
import os
import sys
import time

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
L09 = os.path.join(ROOT, "assets/l09/l09.usda")
PLATE = os.path.join(ROOT, "assets/labware/plate_sbs96.usda")
QUICK = "--quick" in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = os.path.abspath(args[0] if args else os.path.join(ROOT, "renders/l09"))
RES = (960, 640) if QUICK else (1920, 1280)
SPP, SUBFRAMES = (8, 8) if QUICK else (16, 24)
BENCH_Z = 0.90
HZ = 240

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True, "renderer": "PathTracing", "width": RES[0], "height": RES[1]})

import carb  # noqa: E402
import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
import numpy as np  # noqa: E402
import omni.replicator.core as rep  # noqa: E402
import omni.usd  # noqa: E402
from isaacsim.core.experimental.prims import RigidPrim  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402
from PIL import Image  # noqa: E402
from pxr import Gf, PhysxSchema, Sdf, UsdGeom, UsdLux, UsdPhysics, UsdShade  # noqa: E402

from twin.l09_controller import L09Controller  # noqa: E402

s = carb.settings.get_settings()
s.set("/rtx/rendermode", "PathTracing")
s.set("/rtx/pathtracing/spp", SPP)
s.set("/rtx/pathtracing/totalSpp", SPP * SUBFRAMES)
s.set("/rtx/pathtracing/maxBounces", 8)
s.set("/rtx/pathtracing/optixDenoiser/enabled", True)

omni.usd.get_context().new_stage()
app.update()
stage = omni.usd.get_context().get_stage()
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)
UsdGeom.Xform.Define(stage, "/World")
scene = UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
scene.CreateGravityDirectionAttr(Gf.Vec3f(0, 0, -1))
scene.CreateGravityMagnitudeAttr(9.81)
PhysxSchema.PhysxSceneAPI.Apply(scene.GetPrim()).CreateTimeStepsPerSecondAttr(HZ)


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


def slab(path, center, size, mat=None, collide=False):
    xf = UsdGeom.Xform.Define(stage, path)
    xf.AddTranslateOp().Set(Gf.Vec3d(*center))
    c = UsdGeom.Cube.Define(stage, path + "/Box")
    c.CreateSizeAttr(1.0)
    c.AddScaleOp().Set(Gf.Vec3f(*size))
    if mat:
        UsdShade.MaterialBindingAPI.Apply(c.GetPrim()).Bind(mat)
    if collide:
        UsdPhysics.CollisionAPI.Apply(c.GetPrim())


slab("/World/Room/Floor", (0, 0, -0.01), (8, 8, 0.02), pbr("/World/Looks/Floor", (0.42, 0.44, 0.45), 0.35), True)
slab("/World/Room/Wall", (0, 1.0, 1.5), (8, 0.05, 3.0), pbr("/World/Looks/Wall", (0.80, 0.80, 0.78), 0.85))
slab("/World/Bench/Top", (0, 0.1, BENCH_Z - 0.015), (1.6, 0.9, 0.03), pbr("/World/Looks/Top", (0.035, 0.037, 0.04), 0.32), True)
slab("/World/Bench/Carcass", (0, 0.14, (BENCH_Z - 0.03) / 2 + 0.06), (1.56, 0.8, BENCH_Z - 0.15),
     pbr("/World/Looks/Carcass", (0.70, 0.72, 0.73), 0.5))

l09 = UsdGeom.Xform.Define(stage, "/World/L09_PlateHotel")
l09.GetPrim().GetReferences().AddReference(L09)
l09.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.1, BENCH_Z))
plates = {}
for i, pid in enumerate(["P-0101", "P-0102", "P-0103", "P-0104", "P-0105"]):
    p = UsdGeom.Xform.Define(stage, f"/World/Plate_{i}")
    p.GetPrim().GetReferences().AddReference(PLATE)
    p.AddTranslateOp().Set(Gf.Vec3d(2.5 + 0.2 * i, 2.5, 0.0))
    p.AddOrientOp().Set(Gf.Quatf(1, 0, 0, 0))
    p.GetPrim().CreateAttribute("labware:barcode", Sdf.ValueTypeNames.String, custom=True).Set(pid)
    plates[pid] = f"/World/Plate_{i}"

dome = UsdLux.DomeLight.Define(stage, "/World/Lights/Dome")
dome.CreateIntensityAttr(250)
for i, x in enumerate((-0.8, 0.8)):
    panel = UsdLux.RectLight.Define(stage, f"/World/Lights/Ceiling{i}")
    panel.CreateWidthAttr(1.2)
    panel.CreateHeightAttr(0.6)
    panel.CreateIntensityAttr(9000)
    panel.AddTranslateOp().Set(Gf.Vec3d(x, -0.4, 2.8))
key = UsdLux.RectLight.Define(stage, "/World/Lights/Key")
key.CreateWidthAttr(0.9)
key.CreateHeightAttr(0.9)
key.CreateIntensityAttr(6000)


def look_at(prim, eye, target):
    m = Gf.Matrix4d().SetLookAt(Gf.Vec3d(*eye), Gf.Vec3d(*target), Gf.Vec3d(0, 0, 1)).GetInverse()
    xf = UsdGeom.Xformable(prim)
    xf.ClearXformOpOrder()
    xf.AddTransformOp().Set(m)


look_at(key.GetPrim(), (-1.4, -1.5, 2.0), (0.0, 0.0, 1.2))
cam = UsdGeom.Camera.Define(stage, "/World/RenderCam")
cam.CreateHorizontalApertureAttr(36.0)
cam.CreateVerticalApertureAttr(36.0 * RES[1] / RES[0])
cam.CreateClippingRangeAttr(Gf.Vec2f(0.01, 100))
for _ in range(10):
    app.update()

app_utils.play(commit=True)
ctrl = L09Controller(stage, "/World/L09_PlateHotel")
rp = {pid: RigidPrim(path) for pid, path in plates.items()}
xc = UsdGeom.XformCache()
frame = lambda n: np.array(xc.GetLocalToWorldTransform(stage.GetPrimAtPath(f"/World/L09_PlateHotel/{n}"))  # noqa: E731
                           .ExtractTranslation())


def run(seconds):
    SimulationManager.step(steps=int(round(seconds * HZ)), callback=lambda i, n: ctrl.update(1.0 / HZ))


def run_until(pred, timeout):
    t0 = ctrl.t
    while ctrl.t - t0 < timeout and not pred():
        run(0.1)


def put(pid, pos):
    rp[pid].set_world_poses(positions=[list(pos)], orientations=[[1, 0, 0, 0]])
    rp[pid].set_velocities(linear_velocities=[[0, 0, 0]], angular_velocities=[[0, 0, 0]])


render_product = rep.create.render_product(str(cam.GetPath()), RES)
rgb = rep.AnnotatorRegistry.get_annotator("rgb")
rgb.attach(render_product)
os.makedirs(OUT, exist_ok=True)


def shot(name, eye, target, focal):
    t0 = time.time()
    look_at(cam.GetPrim(), eye, target)
    cam.GetFocalLengthAttr().Set(focal)
    rep.orchestrator.step(rt_subframes=SUBFRAMES, delta_time=0.0)
    img = np.asarray(rgb.get_data())[..., :3].astype(np.uint8)
    path = os.path.join(OUT, f"{name}.png")
    Image.fromarray(img).save(path)
    print(f"[render_l09] {path} ({time.time() - t0:.0f}s) mode={ctrl.mode} inventory={ctrl.inventory}")


def hide_housing(hidden):
    for sub in ("Body/Visual/Housing", "ServiceDoor"):
        im = UsdGeom.Imageable(stage.GetPrimAtPath(f"/World/L09_PlateHotel/{sub}"))
        im.MakeInvisible() if hidden else im.MakeVisible()


# stock the cassette through the real store path for one plate, directly for the rest (visual fill only)
run(0.5)
for pid, k in (("P-0102", 0), ("P-0103", 5), ("P-0104", 9)):
    put(pid, frame(f"slot_frames/slot_{k:02d}") + [0, 0, 0.001])
run(0.5)
ctrl.present_for_load()
run_until(lambda: ctrl.mode == "PRESENTED_EMPTY", 10)
put("P-0101", frame("transfer_nest") + [0, 0, 0.012])
run(1.0)
ctrl.store("P-0101", 3)
run_until(lambda: ctrl.mode in ("READY", "FAULT"), 60)
ctrl.present_for_load()
run_until(lambda: ctrl.mode == "PRESENTED_EMPTY", 10)
put("P-0105", frame("transfer_nest") + [0, 0, 0.012])
run(1.0)
shot("l09_presented_loaded", (0.75, -1.15, 1.45), (0.0, -0.15, 1.10), 40)

# mid-transfer: store P-0105 to slot 11 and freeze while the fork carries it up the channel
ctrl.store("P-0105", 11)
run_until(lambda: ctrl.q["lift"] > 0.20 and abs(ctrl.q["fork"]) < 0.002, 40)
hide_housing(True)
shot("l09_cutaway_handler", (-0.95, -0.80, 1.50), (0.0, -0.05, 1.18), 36)
hide_housing(False)
run_until(lambda: ctrl.mode in ("READY", "FAULT"), 60)

ctrl.art.set_dof_position_targets(np.array([[math.radians(95)]], dtype=np.float32), dof_indices=[ctrl.dof["door"]])
run(2.5)
shot("l09_service_door", (1.05, -0.35, 1.40), (0.10, 0.05, 1.25), 40)
rep.orchestrator.wait_until_complete()
sys.stdout.flush()
os._exit(0)
