"""Path-traced view of Cell 01 with the stations built so far, posed by their controllers and physics.

Opens scenes/cell01_twin.usda (Cell 01 + collider fixes + layout P1 with the H4, L09 and L10 twins around R01, and
R02's tool magazine, L12, L17, L21, the handover nest and R03 + H2) and adds, in this session only: R02 (rail + UR5e)
reaching over the magazine, L12 tips + reagent tubes, plates on L12 and L21, R03 docked with its cabinet open, the FR3 + plate
gripper on R01's base_link (hovering over H4's presented nest)
and plates on the presented transfer nests of H4, L09, L10 and L17 (stage presented) and in the R01/R02 handover
nest. Nothing is saved.
Usage: python scripts/render_cell01.py [out_dir] [--quick] [--rt] [--views=name1,name2]
"""

import math
import os
import sys
import time

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
OVERLAY = os.path.join(ROOT, "scenes/cell01_twin.usda")
FR3_USD = os.path.join(ROOT, "assets/fr3/usd/fr3_arm/fr3_arm.usda")
GRIPPER_USD = os.path.join(ROOT, "assets/gripper/plate_gripper.usda")
PLATE_USD = os.path.join(ROOT, "assets/labware/plate_sbs96.usda")
QUICK = "--quick" in sys.argv
RT = "--rt" in sys.argv          # real-time ray tracing: far less GPU memory (preview next to running simulations)
ONLY = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--views=")), None)
args = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = os.path.abspath(args[0] if args else os.path.join(ROOT, "renders/cell01"))
RES = (1280, 800) if QUICK else (1920, 1200)
SPP, SUBFRAMES = (8, 8) if QUICK else (16, 32)
HZ = 240
H4 = "/World/Cell01/Stations/H4_Quarantine"
L09 = "/World/Cell01/Stations/L09_PlateHotel"
L10 = "/World/Cell01/Stations/L10_Incubator"
L17 = "/World/Cell01/Stations/L17_BrightFieldImager"
HN = "/World/Cell01/Fixtures/HandoverNest_R01_R02"
R01 = "/World/Cell01/Robots/R01_FR3"

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True, "renderer": "RaytracedLighting" if RT else "PathTracing", "width": RES[0],
                     "height": RES[1]})

import carb  # noqa: E402
import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402

for _ext in ("isaacsim.robot.surface_gripper", "isaacsim.robot.schema"):  # R02's coupler lock
    app_utils.enable_extension(_ext)
app.update()
import numpy as np  # noqa: E402
import omni.replicator.core as rep  # noqa: E402
import omni.usd  # noqa: E402
from isaacsim.core.experimental.prims import Articulation, RigidPrim  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402
from PIL import Image  # noqa: E402
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdLux, UsdPhysics  # noqa: E402

from twin.h4_controller import H4Controller  # noqa: E402
from twin.l09_controller import L09Controller  # noqa: E402
from twin.l10_controller import L10Controller  # noqa: E402
from twin.l17_controller import L17Controller  # noqa: E402
from twin.r02_rig import author_r02, rail_origin  # noqa: E402

s = carb.settings.get_settings()
s.set("/rtx/rendermode", "RaytracedLighting" if RT else "PathTracing")
s.set("/rtx/pathtracing/spp", SPP)
s.set("/rtx/pathtracing/totalSpp", SPP * SUBFRAMES)
s.set("/rtx/pathtracing/maxBounces", 8)
s.set("/rtx/pathtracing/optixDenoiser/enabled", True)

omni.usd.get_context().open_stage(OVERLAY)
for _ in range(10):
    app.update()
stage = omni.usd.get_context().get_stage()
stage.SetEditTarget(stage.GetSessionLayer())  # session-only edits: nothing is written to disk
PhysxSchema.PhysxSceneAPI.Apply(stage.GetPrimAtPath("/World/PhysicsScene")).CreateTimeStepsPerSecondAttr(HZ)

# FR3 + gripper on R01's base_link
fr3 = UsdGeom.Xform.Define(stage, f"{R01}/FR3")
fr3.GetPrim().GetReferences().AddReference(FR3_USD)
fr3.GetPrim().GetVariantSets().GetVariantSet("Physics").SetVariantSelection("physx")
fr3.AddTransformOp().Set(UsdGeom.Xformable(stage.GetPrimAtPath(f"{R01}/base_link")).GetLocalTransformation())
app.update()
art_root = next(str(p.GetPath()) for p in Usd.PrimRange(fr3.GetPrim()) if p.HasAPI(UsdPhysics.ArticulationRootAPI))
link7 = next(str(p.GetPath()) for p in Usd.PrimRange(fr3.GetPrim()) if p.GetName() == "fr3_link7")
flange = Gf.Matrix4d(1.0).SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), -45.0)).SetTranslateOnly(Gf.Vec3d(0, 0, 0.107))
grip = UsdGeom.Xform.Define(stage, f"{R01}/PlateGripper")
grip.GetPrim().GetReferences().AddReference(GRIPPER_USD)
xc = UsdGeom.XformCache()
grip.AddTransformOp().Set(flange * xc.GetLocalToWorldTransform(stage.GetPrimAtPath(link7))
                          * xc.GetParentToWorldTransform(grip.GetPrim()).GetInverse())
mount = UsdPhysics.FixedJoint.Define(stage, f"{R01}/GripperMount")
mount.CreateBody0Rel().SetTargets([link7])
mount.CreateBody1Rel().SetTargets([f"{R01}/PlateGripper/GripperBody"])
mount.CreateLocalPos0Attr(Gf.Vec3f(0, 0, 0.107))
mount.CreateLocalRot0Attr(Gf.Quatf(math.cos(math.radians(-22.5)), 0, 0, math.sin(math.radians(-22.5))))
mount.CreateLocalPos1Attr(Gf.Vec3f(0))
mount.CreateLocalRot1Attr(Gf.Quatf(1, 0, 0, 0))
for p in list(Usd.PrimRange(fr3.GetPrim())) + list(Usd.PrimRange(grip.GetPrim())):
    if p.HasAPI(UsdPhysics.RigidBodyAPI):
        PhysxSchema.PhysxRigidBodyAPI.Apply(p).CreateDisableGravityAttr(True)
PhysxSchema.PhysxArticulationAPI.Apply(stage.GetPrimAtPath(art_root)).CreateSleepThresholdAttr(0.0)

plates = {}
for i, pid in enumerate(("P-H4-01", "P-L09-01", "P-L10-01", "P-L17-01", "P-HN-01")):
    p = UsdGeom.Xform.Define(stage, f"/World/RenderOnly/Plate_{i}")
    p.GetPrim().GetReferences().AddReference(PLATE_USD)
    p.AddTranslateOp().Set(Gf.Vec3d(2.5, -1.5 + 0.2 * i, 0.02))
    p.AddOrientOp().Set(Gf.Quatf(1, 0, 0, 0))
    p.GetPrim().CreateAttribute("labware:barcode", Sdf.ValueTypeNames.String, custom=True).Set(pid)
    plates[pid] = str(p.GetPath())

# R02 (rail + UR5e + coupler) next to its tool magazine (the magazine and tools come with the overlay)
r02_root, _, _ = author_r02(stage)
# L12 consumables (tips, a reagent tube), L21's reference plate, R03 docked with a carrier plate (opened after play)
from twin.l12_controller import add_reagent_tube, add_tips  # noqa: E402
from twin.r03_controller import R03Controller, carrier_seat_world  # noqa: E402
L12 = "/World/Cell01/Stations/L12_LiquidHandler"
L21 = "/World/Cell01/Stations/L21_QC_Calibration"
R03 = "/World/Cell01/Robots/R03_SampleAMR"
add_tips(stage, L12, [f"{r}{c:02d}" for c in (1, 2, 3, 4) for r in "ABCDEFGH"])
add_reagent_tube(stage, L12, 1, "RGT-0001", "abstract_challenge_reagent", "SIM-LOT-A", 1000.0)
add_reagent_tube(stage, L12, 2, "RGT-0002", "abstract_rescue_reagent", "SIM-LOT-B", 800.0)
for pid, prim in (("REF-L21-001", f"{L21}/reference_plate_frame"), ("P-L12-01", f"{L12}/plate_nest")):
    _p = UsdGeom.Xform.Define(stage, f"/World/RenderOnly/Plate_{pid.replace('-', '_')}")
    _p.GetPrim().GetReferences().AddReference(PLATE_USD)
    _p.AddTranslateOp().Set(UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(prim)).ExtractTranslation()
                            + Gf.Vec3d(0, 0, 0.0005))
_pc, _yc = carrier_seat_world(stage, R03, (0.0, 0.0, 0.0))
_p = UsdGeom.Xform.Define(stage, "/World/RenderOnly/Plate_P30")
_p.GetPrim().GetReferences().AddReference(PLATE_USD)
_p.AddTranslateOp().Set(Gf.Vec3d(*map(float, _pc + [0, 0, 0.0005])))
_p.AddRotateZOp().Set(float(_yc))

# a little more light than the scene's dome alone (render-only)
key = UsdLux.RectLight.Define(stage, "/World/RenderOnly/CeilingPanel")
key.CreateWidthAttr(2.5)
key.CreateHeightAttr(1.2)
key.CreateIntensityAttr(4000)
key.AddTranslateOp().Set(Gf.Vec3d(-1.0, 0.3, 2.45))
for _ in range(10):
    app.update()

app_utils.play(commit=True)
h4c = H4Controller(stage, H4)
l9c = L09Controller(stage, L09)
l10c = L10Controller(stage, L10)
l17c = L17Controller(stage, L17)
amr = R03Controller(stage, R03, "/World/Cell01/Stations/H2_AMR_Dock")
amr.mode = "DOCKED"
amr.open_cabinet()
arm = Articulation(art_root)
names = list(arm.dof_names)
ARM = [names.index(f"fr3_joint{i}") for i in range(1, 8)]


def frame(path):
    m = UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(path))
    r = m.ExtractRotationMatrix()
    return np.array(m.ExtractTranslation()), math.degrees(math.atan2(r[0][1], r[0][0]))  # origin, yaw of +X


nest, h4_yaw = frame(f"{H4}/transfer_nest")
base = np.array(UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(f"{R01}/base_link"))
                .ExtractTranslation())
# hover pose from FR3 IK (same URDF kinematics as the sim): TCP 0.20 m above H4's transfer_nest (the approach
# point), tool down, jaws across the plate; a hand-picked pose put the gripper in the shuttle's path
sys.path.insert(0, os.path.join(ROOT, "tools"))
import reachability_study as rs  # noqa: E402
fr3_kin, rng = rs.FR3(rs.FR3_URDF if hasattr(rs, "FR3_URDF") else rs.URDF), np.random.default_rng(1)
READY = [0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785]
target = nest - base + [0, 0, 0.006 + 0.20]
pose = None
for yaw in (h4_yaw + 180.0, h4_yaw, h4_yaw + 135.0, h4_yaw - 45.0):
    pose = rs.ik_solve(fr3_kin, target, math.radians(yaw), rng, restarts=8, iters=150, q0=READY)
    if pose is not None:
        break
assert pose is not None, "no IK solution for the hover pose"
pose = [float(v) for v in pose]
print(f"[render_cell01] FR3 hover pose (deg): {[round(math.degrees(v), 1) for v in pose]}")
arm.set_dof_positions(np.array([pose], dtype=np.float32), dof_indices=ARM)
arm.set_dof_position_targets(np.array([pose], dtype=np.float32), dof_indices=ARM)

# R02 at the magazine: coupler 0.10 m above dock T03 (URDF IK, elbow-up), as when it is about to pick a tool
from twin.kinematics import UrdfChain  # noqa: E402
_r02k = UrdfChain(os.path.join(ROOT, "assets/r02/r02.urdf"), "rail_base", "r02_tool0")
_dock = np.array(UsdGeom.XformCache().GetLocalToWorldTransform(
    stage.GetPrimAtPath("/World/Cell01/Tooling/AutomaticToolChanger/dock_T03")).ExtractTranslation())
_tool = np.eye(4)
_tool[2, 3] = 0.016
_rail = float(_dock[0] - rail_origin()[0])
q_r02 = _r02k.ik(_dock + [0, 0, 0.10] - rail_origin(), np.diag([1.0, -1.0, -1.0]),
                 [_rail, math.pi / 2, -1.75, 1.95, -1.77, -math.pi / 2, 0.0], active=range(1, 7), tool=_tool)
assert q_r02 is not None, "no R02 IK for the magazine pose"
r02_arm = Articulation(r02_root)
r02_arm.set_dof_positions(np.array([q_r02], dtype=np.float32))
r02_arm.set_dof_position_targets(np.array([q_r02], dtype=np.float32))
print(f"[render_cell01] R02 at the magazine: rail {q_r02[0]:.3f} m, q {np.round(np.degrees(q_r02[1:]), 1).tolist()}")


def run(seconds):
    def cb(i, n):
        h4c.update(1.0 / HZ)
        l17c.update(1.0 / HZ)
        amr.update(1.0 / HZ)
        l9c.update(1.0 / HZ)
        l10c.update(1.0 / HZ)
    SimulationManager.step(steps=int(round(seconds * HZ)), callback=cb)


plate_views = {pid: RigidPrim(path) for pid, path in plates.items()}  # create once (see note in put)


def put(pid, pos, yaw_deg):
    # a RigidPrim view created on the fly right before its first pose write dropped that write silently
    a = math.radians(yaw_deg) / 2
    rp = plate_views[pid]
    rp.set_world_poses(positions=[list(pos)], orientations=[[math.cos(a), 0, 0, math.sin(a)]])
    rp.set_velocities(linear_velocities=[[0, 0, 0]], angular_velocities=[[0, 0, 0]])


run(0.5)
h4c.present_nest()
l9c.present_for_load()
l10c.present_for_load()
l17c.present_for_load()
for _ in range(80):  # wait for every station to finish presenting before plates go on the nests
    run(0.25)
    if h4c.mode == "PRESENTED" and l9c.mode == "PRESENTED_EMPTY" and l10c.mode == "PRESENTED_EMPTY" \
            and l17c.mode == "PRESENTED_EMPTY":
        break
run(0.5)
put("P-H4-01", nest + [0, 0, 0.004], h4_yaw)
for pid, prim in (("P-L09-01", f"{L09}/transfer_nest"), ("P-L10-01", f"{L10}/transfer_station"),
                  ("P-L17-01", f"{L17}/plate_load_frame"), ("P-HN-01", f"{HN}/handover_frame")):
    p_, y_ = frame(prim)
    put(pid, p_ + [0, 0, 0.004], y_)
run(1.0)
print(f"[render_cell01] H4 {h4c.mode} seated={h4c.seated} | L09 {l9c.mode} on_nest={l9c.plate_on_nest} | "
      f"L10 {l10c.mode} on_nest={l10c.plate_on_nest}")
_pp = plate_views["P-H4-01"].get_world_poses()[0].numpy()[0]
print(f"[render_cell01] H4 plate at {np.round(_pp, 4)} nest {np.round(nest, 4)} diff_mm {np.round((_pp - nest) * 1e3, 1)} "
      f"gaps {h4c.snapshot()['seat_gaps_mm']} shuttle_mm {h4c.shuttle_m * 1e3:.1f}")

# one camera + one render product, moved between views (three path-traced products at once exhausted the
# 8 GB GPU next to a running simulation: ERROR_DEVICE_LOST)
ov = UsdGeom.Camera(stage.GetPrimAtPath("/World/Sensors/OverviewCamera"))
cam = UsdGeom.Camera.Define(stage, "/World/RenderOnly/RenderCam")
cam.CreateHorizontalApertureAttr(36.0)
cam.CreateVerticalApertureAttr(36.0 * RES[1] / RES[0])
cam.CreateClippingRangeAttr(Gf.Vec2f(0.01, 100))
cam_op = UsdGeom.Xformable(cam.GetPrim()).AddTransformOp()
rp_ = rep.create.render_product(str(cam.GetPath()), RES)
rgb = rep.AnnotatorRegistry.get_annotator("rgb")
rgb.attach(rp_)
os.makedirs(OUT, exist_ok=True)
views = [("cell01_overview", UsdGeom.XformCache().GetLocalToWorldTransform(ov.GetPrim()), ov.GetFocalLengthAttr().Get()),
         ("cell01_elevated", ((0.55, -2.05, 2.55), (-1.70, 0.50, 0.95)), 20.0),
         ("cell01_r01_cluster", ((-0.25, -1.35, 1.85), (-1.80, 0.50, 1.00)), 20.0),
         ("cell01_r01_service", ((-1.60, -0.75, 2.60), (-1.75, 0.55, 0.95)), 16.0),
         ("cell01_r02_magazine", ((1.45, -0.85, 2.00), (0.25, 1.00, 1.05)), 20.0),
         ("cell01_l17", ((0.80, 0.15, 1.75), (1.62, 1.30, 1.00)), 22.0),
         ("cell01_l17_close", ((1.20, 0.72, 1.32), (1.65, 1.27, 1.00)), 30.0),
         ("cell01_handover_nest", ((-0.55, -0.20, 1.40), (-1.05, 0.55, 0.96)), 30.0),
         ("cell01_l12", ((0.15, -0.85, 1.65), (0.15, 0.25, 0.98)), 24.0),
         ("cell01_l21", ((1.55, 0.25, 1.55), (2.15, 1.12, 0.98)), 26.0),
         ("cell01_amr_docked", ((-0.35, -1.35, 1.55), (-1.45, -0.28, 0.65)), 22.0),
         ("cell01_east", ((2.70, -1.90, 2.40), (0.80, 0.70, 0.95)), 20.0)]
if os.environ.get("CELL01_DEBUG"):
    sys.stdout.flush()
    os._exit(0)
for name, pose, focal in [v for v in views if ONLY is None or v[0] in ONLY]:
    t0 = time.time()
    m = pose if isinstance(pose, Gf.Matrix4d) else Gf.Matrix4d().SetLookAt(
        Gf.Vec3d(*pose[0]), Gf.Vec3d(*pose[1]), Gf.Vec3d(0, 0, 1)).GetInverse()
    cam_op.Set(m)
    cam.GetFocalLengthAttr().Set(float(focal))
    rep.orchestrator.step(rt_subframes=SUBFRAMES, delta_time=0.0)
    path = os.path.join(OUT, f"{name}.png")
    Image.fromarray(np.asarray(rgb.get_data())[..., :3].astype(np.uint8)).save(path)
    print(f"[render_cell01] {path} ({time.time() - t0:.0f}s)")
rep.orchestrator.wait_until_complete()
sys.stdout.flush()
os._exit(0)
