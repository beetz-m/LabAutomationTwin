"""Physics acceptance test for the articulated H4 Quarantine Station (shuttle version).

Builds a scratch stage (ground, bench, H4 at an arbitrary pose, SBS plate), runs PhysX at 240 Hz
with the H4Controller in the loop, and checks the contract and robot hand-off end to end:

  S   structure: one articulation root, 6 joints, 6 rigid links, box + convex colliders
  T1  fixed base holds at a rotated/offset placement
  T2  rest: stowed, closed, unlocked, READY, green
  T3  DOOR pushbutton presents the nest (door opens first, then the shuttle extends)
  T4  interlock: forcing the door motor closed onto the presented shuttle is blocked by contact
  T5  quarantine refused while the nest is empty
  T6  placement capture: plates released 1 mm above the guides with XY/yaw errors seat inside the
      design envelope (+-6 mm translation, or +-4 mm combined with +-2 deg yaw) and are reported
      seated; beyond it they are reported unseated (the seat sensors never claim a false seat)
  T7  a plate rotated 180 deg (A1 key) is detected as unseated and quarantine is refused (reseat)
  T8  quarantine_sample on a seated plate: stow, close, lock, red; chamber beam confirms
  T9  forcing the door open while locked: the bolt blocks it
  T10 DOOR pushbutton while locked is refused and logged
  T11 release refused without token, and with token but key in LOCK
  T12 key to RELEASE + token: unlock, open, present with the plate on the nest, green
  T13 plate removed -> sample binding cleared; stow -> READY

The robot is not in this test: plates are released by teleporting them to a pose (see
scripts/test_h4_robot.py for FR3 pick-and-place). Writes test_reports/h4_physics_report.json and
h4_events.json; exit status 1 on any failure.
"""

import json
import math
import os
import sys
import time

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
H4_USD = os.path.join(ROOT, "assets/h4/h4.usda")
PLATE_USD = os.path.join(ROOT, "assets/labware/plate_sbs96.usda")
REPORT_DIR = os.path.join(ROOT, "test_reports")
HZ = 240
DT = 1.0 / HZ
POSE = (1.0, -0.5, 0.9, 30.0)  # x, y, z, yaw deg: deliberately not the asset origin
PARK = [4.0, 4.0, 0.02]
GUIDE_TOP_ABOVE_SEAT = 0.012

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True})

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from isaacsim.core.experimental.prims import RigidPrim  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402
from pxr import Gf, PhysxSchema, Usd, UsdGeom, UsdPhysics  # noqa: E402

from twin.h4_controller import H4Controller  # noqa: E402

results = []


def check(name, ok, **values):
    def fmt(v):
        return round(v, 4) if isinstance(v, float) else v
    results.append({"test": name, "pass": bool(ok), **{k: fmt(v) for k, v in values.items()}})
    print(f"[test_h4] {'PASS' if ok else 'FAIL'}  {name}  { {k: fmt(v) for k, v in values.items()} }")


# ------------------------------------------------------------------------------ scene
omni.usd.get_context().new_stage()
app.update()
stage = omni.usd.get_context().get_stage()
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)
UsdGeom.Xform.Define(stage, "/World")
scene = UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
scene.CreateGravityDirectionAttr(Gf.Vec3f(0, 0, -1))
scene.CreateGravityMagnitudeAttr(9.81)
px = PhysxSchema.PhysxSceneAPI.Apply(scene.GetPrim())
px.CreateTimeStepsPerSecondAttr(HZ)
px.CreateSolverTypeAttr("TGS")
px.CreateEnableCCDAttr(True)


def static_box(path, center, size):
    xf = UsdGeom.Xform.Define(stage, path)
    xf.AddTranslateOp().Set(Gf.Vec3d(*center))
    c = UsdGeom.Cube.Define(stage, path + "/Box")
    c.CreateSizeAttr(1.0)
    c.AddScaleOp().Set(Gf.Vec3f(*size))
    UsdPhysics.CollisionAPI.Apply(c.GetPrim())


static_box("/World/Ground", (0, 0, -0.05), (20, 20, 0.1))
static_box("/World/Bench", (POSE[0], POSE[1], POSE[2] / 2), (0.6, 0.5, POSE[2]))  # H4 footprint only

h4 = UsdGeom.Xform.Define(stage, "/World/H4_Quarantine")
h4.GetPrim().GetReferences().AddReference(H4_USD)
h4.AddTranslateOp().Set(Gf.Vec3d(*POSE[:3]))
h4.AddRotateZOp().Set(POSE[3])
plate = UsdGeom.Xform.Define(stage, "/World/Plate")
plate.GetPrim().GetReferences().AddReference(PLATE_USD)
plate.AddTranslateOp().Set(Gf.Vec3d(*PARK))
plate.AddOrientOp().Set(Gf.Quatf(1, 0, 0, 0))
for _ in range(5):
    app.update()

# ------------------------------------------------------------------------------ S: structure
prims = list(Usd.PrimRange(h4.GetPrim()))
roots = [p for p in prims if p.HasAPI(UsdPhysics.ArticulationRootAPI)]
joints = sorted(p.GetName() for p in prims if p.IsA(UsdPhysics.Joint))
links = sorted(p.GetName() for p in prims if p.HasAPI(UsdPhysics.RigidBodyAPI))
colliders = [p for p in prims if p.HasAPI(UsdPhysics.CollisionAPI)]
convex = [p for p in colliders if p.HasAPI(UsdPhysics.MeshCollisionAPI)]
check("S structure", len(roots) == 1 and len(joints) == 6 and len(links) == 6 and len(convex) == 9,
      joints=joints, links=links, colliders=len(colliders), convex=len(convex))

xc = UsdGeom.XformCache()
TRANSFER = np.array(xc.GetLocalToWorldTransform(
    stage.GetPrimAtPath("/World/H4_Quarantine/transfer_nest")).ExtractTranslation())

# ------------------------------------------------------------------------------ run
app_utils.play(commit=True)
ctrl = H4Controller(stage, "/World/H4_Quarantine")
plate_rp = RigidPrim("/World/Plate")


def run(seconds):
    SimulationManager.step(steps=int(round(seconds * HZ)), callback=lambda i, n: ctrl.update(DT))


def lens(name):
    return stage.GetPrimAtPath(f"/World/H4_Quarantine/Looks/{name}/Shader").GetAttribute(
        "inputs:emissive_intensity").Get()


def press_button(hold=0.25):
    ctrl._target("button", -0.003)
    run(hold)
    ctrl._target("button", 0.0)
    run(0.25)


def quat_yaw(deg):
    a = math.radians(deg) / 2
    return [math.cos(a), 0.0, 0.0, math.sin(a)]  # w, x, y, z


YAW = POSE[3]
c, s = math.cos(math.radians(YAW)), math.sin(math.radians(YAW))
R_H4 = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])  # H4 frame -> world


def place_plate(dx_mm=0.0, dy_mm=0.0, dyaw_deg=0.0, z_above_seat=GUIDE_TOP_ABOVE_SEAT + 0.001, settle=1.0):
    pos = TRANSFER + R_H4 @ np.array([dx_mm * 1e-3, dy_mm * 1e-3, z_above_seat])
    plate_rp.set_world_poses(positions=[pos.tolist()], orientations=[quat_yaw(YAW + dyaw_deg)])
    plate_rp.set_velocities(linear_velocities=[[0, 0, 0]], angular_velocities=[[0, 0, 0]])
    run(settle)
    p, q = plate_rp.get_world_poses()
    p, q = p.numpy()[0], q.numpy()[0]
    err = R_H4.T @ (p - TRANSFER)
    yaw_err = math.degrees(2 * math.atan2(q[3], q[0])) - YAW
    return err, yaw_err


def park_plate():
    plate_rp.set_world_poses(positions=[PARK], orientations=[[1, 0, 0, 0]])
    plate_rp.set_velocities(linear_velocities=[[0, 0, 0]], angular_velocities=[[0, 0, 0]])
    run(0.3)


t_start = time.time()
run(1.0)
pos, quat = ctrl.art.get_world_poses()
drift = float(np.linalg.norm(pos.numpy()[0] - np.array(POSE[:3])))
qerr = float(1 - abs(np.dot(quat.numpy()[0], quat_yaw(YAW))))
check("T1 fixed base at offset+rotated pose", drift < 1e-3 and qerr < 1e-5, drift_m=drift, quat_err=qerr)

s0 = ctrl.snapshot()
check("T2 rest: stowed, closed, unlocked, READY, green", ctrl.stowed and ctrl.door_closed and not ctrl.locked
      and s0["mode"] == "READY" and lens("LensGreen") > 0 and lens("LensRed") == 0,
      door_deg=s0["door_deg"], shuttle_mm=s0["shuttle_m"] * 1e3, mode=s0["mode"])

press_button()
run(4.0)
check("T3 DOOR button presents the nest", ctrl.mode == "PRESENTED" and ctrl.presented and ctrl.door_open,
      mode=ctrl.mode, door_deg=ctrl.door_deg, shuttle_mm=ctrl.shuttle_m * 1e3)

ctrl._target("door", 0.0)  # bypass the controller: motor tries to close the door onto the shuttle
run(2.0)
blocked_at = ctrl.door_deg
ctrl._target("door", math.radians(100))
run(2.0)
check("T4 door cannot close onto presented shuttle", blocked_at > 20 and ctrl.door_open and ctrl.presented,
      door_deg_when_forced=blocked_at)

r = ctrl.quarantine_sample("P-0001", "identity_mismatch")
check("T5 quarantine refused with empty nest", not r.accepted and "no sample" in r.reason, reason=r.reason)

trials = []
cases = [  # dx mm, dy mm, dyaw deg, inside design envelope?
    (0, 0, 0, True), (2, 0, 0, True), (0, 2, 0, True), (-3, 2, 1.5, True), (3.5, -3.5, -2, True),
    (4, 4, 2, True), (-4, -4, -2, True), (6, 0, 0, True), (0, -6, 0, True),
    (9, 0, 0, False), (0, 9, 0, False)]
for dx, dy, dyaw, expected in cases:
    err, yaw_err = place_plate(dx, dy, dyaw)
    snap = ctrl.snapshot()
    trials.append({"offset_mm": [dx, dy], "yaw_deg": dyaw, "in_envelope": expected, "seated_sensor": snap["seated"],
                   "final_err_mm": [round(float(v) * 1e3, 2) for v in err], "final_yaw_err_deg": round(yaw_err, 2),
                   "seat_gaps_mm": snap["seat_gaps_mm"]})
    park_plate()
inside = [t for t in trials if t["in_envelope"]]
outside = [t for t in trials if not t["in_envelope"]]
true_seat = lambda t: max(abs(v) for v in t["final_err_mm"][:2]) < 0.6 and abs(t["final_err_mm"][2]) < 0.4
check("T6 placement capture in design envelope and honest seat sensing",
      all(t["seated_sensor"] and true_seat(t) for t in inside)
      and all(t["seated_sensor"] == true_seat(t) for t in trials),
      captured=f"{sum(t['seated_sensor'] for t in inside)}/{len(inside)} inside envelope",
      beyond=f"{sum(not t['seated_sensor'] for t in outside)}/{len(outside)} correctly reported unseated")

err, _ = place_plate(0, 0, 180.0)
snap = ctrl.snapshot()
r = ctrl.quarantine_sample("P-0001", "identity_mismatch")
check("T7 rotated plate (A1 key) detected, quarantine refused", not snap["seated"] and not r.accepted
      and "not seated" in r.reason, seat_gaps_mm=snap["seat_gaps_mm"], reason=r.reason)
park_plate()

place_plate(1.5, -1.0, 0.5)
r = ctrl.quarantine_sample("P-0001", "identity_mismatch", preceding_anomalies=["barcode_read_mismatch@L17"])
run(6.0)
st = h4.GetPrim()
check("T8 quarantine: stow, close, lock, red, beam confirms", r.accepted and ctrl.mode == "QUARANTINED"
      and ctrl.locked and ctrl.stowed and ctrl.beam_blocked and ctrl.seated and not ctrl.fault
      and lens("LensRed") > 0 and lens("LensGreen") == 0 and st.GetAttribute("state:sample_id").Get() == "P-0001",
      mode=ctrl.mode, door_deg=ctrl.door_deg, bolt_mm=ctrl.bolt_m * 1e3, shuttle_mm=ctrl.shuttle_m * 1e3,
      fault=ctrl.fault)

ctrl._target("door", math.radians(100))  # bypass: motor tries to open a locked door
run(2.0)
forced = ctrl.door_deg
ctrl._target("door", 0.0)
run(1.0)
check("T9 latch bolt blocks forced opening", forced < 3.0 and ctrl.locked and not ctrl.fault,
      door_deg_under_force=forced)

n_before = len(ctrl.events)
press_button()
run(0.5)
refused = [e for e in ctrl.events[n_before:] if e["event"] == "door_request_refused"]
check("T10 DOOR button refused while locked", bool(refused) and ctrl.locked, refused_events=len(refused))

r1 = ctrl.release("")
r2 = ctrl.release("QA-2026-10-15-017")
run(0.5)
check("T11 release refused without token / key", not r1.accepted and not r2.accepted and ctrl.locked,
      no_token=r1.reason, token_key_lock=r2.reason)

ctrl._target("key", math.radians(90))  # operator turns the key to RELEASE
run(1.0)
r3 = ctrl.release("QA-2026-10-15-017")
run(6.0)
check("T12 authorised release: unlock, open, present plate, green", r3.accepted and ctrl.mode == "PRESENTED"
      and not ctrl.locked and ctrl.presented and ctrl.seated and lens("LensGreen") > 0 and lens("LensRed") == 0,
      mode=ctrl.mode, door_deg=ctrl.door_deg, shuttle_mm=ctrl.shuttle_m * 1e3, seated=ctrl.seated)

park_plate()
r4 = ctrl.stow()
run(5.0)
check("T13 plate removed clears binding; stow -> READY", ctrl.sample_id == "" and r4.accepted
      and ctrl.mode == "READY" and ctrl.stowed and ctrl.door_closed
      and any(e["event"] == "sample_removed" for e in ctrl.events), mode=ctrl.mode)

wall = time.time() - t_start
os.makedirs(REPORT_DIR, exist_ok=True)
with open(os.path.join(REPORT_DIR, "h4_physics_report.json"), "w") as f:
    json.dump({"asset": H4_USD, "physics_hz": HZ, "sim_time_s": round(ctrl.t, 3), "wall_time_s": round(wall, 2),
               "results": results, "placement_trials": trials}, f, indent=2)
ctrl.save_events(os.path.join(REPORT_DIR, "h4_events.json"))
for t in trials:
    print("[test_h4]   trial", t)
failed = [r["test"] for r in results if not r["pass"]]
print(f"[test_h4] {len(results) - len(failed)}/{len(results)} passed; sim {ctrl.t:.1f}s in {wall:.1f}s wall")
app_utils.stop()
sys.stdout.flush()
os._exit(1 if failed else 0)  # SimulationApp.close() would end the process with status 0
