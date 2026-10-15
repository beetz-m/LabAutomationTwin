"""Physics acceptance test for the articulated L09 Automated Plate Hotel.

Scene: ground, bench, L09 at an arbitrary pose, SBS plates with barcodes (labware:barcode). PhysX 240 Hz with
the L09Controller in the loop. Plates are put on the presented nest the way a robot would (released 1 mm above
the guides with small errors); every internal move is done by the simulated lift/fork.

  S   structure: one articulation root, 6 joints, 6 links
  T1  rest: READY, gate closed, shuttle stowed, handler parked, all slots empty
  T2  present_for_load: gate opens, then the shuttle presents the nest
  T3  store P-A into slot 3: stow, barcode read, handler moves it; plate on the slot-3 ledges, inventory bound
  T4  store P-B into the top slot (13)
  T5  identity mismatch: store("P-X") with plate P-C on the nest -> slot_identity_mismatch, inventory unchanged,
      plate held on the stowed nest; after reset, store("P-C", 0) succeeds
  T6  double occupancy: storing into occupied slot 3 is refused (plate removed afterwards)
  T7  retrieve P-A: plate delivered to the presented nest, seated, identity verified, slot 3 freed
  T8  transfer nest not clear: retrieve refused while a plate sits on the stowed nest
  T9  service-door interlock: opening the door mid-retrieve halts the handler; closing resumes; P-B delivered
  T10 state attributes mirror the controller (inventory, mode, gate)

Writes test_reports/l09_physics_report.json and l09_events.json; exit 1 on any failure.
"""

import json
import math
import os
import sys
import time

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
L09_USD = os.path.join(ROOT, "assets/l09/l09.usda")
PLATE_USD = os.path.join(ROOT, "assets/labware/plate_sbs96.usda")
REPORT_DIR = os.path.join(ROOT, "test_reports")
HZ = 240
DT = 1.0 / HZ
POSE = (0.8, -0.4, 0.9, 25.0)
PLATES = {"P-A": (3.0, 3.0), "P-B": (3.3, 3.0), "P-C": (3.6, 3.0), "P-D": (3.9, 3.0)}

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True})

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from isaacsim.core.experimental.prims import RigidPrim  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics  # noqa: E402

from twin.l09_controller import L09Controller  # noqa: E402

results = []


def check(name, ok, **values):
    fmt = lambda v: round(v, 4) if isinstance(v, float) else v  # noqa: E731
    vals = {k: fmt(v) for k, v in values.items()}
    results.append({"test": name, "pass": bool(ok), **vals})
    print(f"[test_l09] {'PASS' if ok else 'FAIL'}  {name}  {vals}")


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


def static_box(path, center, size):
    xf = UsdGeom.Xform.Define(stage, path)
    xf.AddTranslateOp().Set(Gf.Vec3d(*center))
    c = UsdGeom.Cube.Define(stage, path + "/Box")
    c.CreateSizeAttr(1.0)
    c.AddScaleOp().Set(Gf.Vec3f(*size))
    UsdPhysics.CollisionAPI.Apply(c.GetPrim())


static_box("/World/Ground", (0, 0, -0.05), (20, 20, 0.1))
static_box("/World/Bench", (POSE[0], POSE[1], POSE[2] / 2), (0.6, 0.7, POSE[2]))
l09 = UsdGeom.Xform.Define(stage, "/World/L09_PlateHotel")
l09.GetPrim().GetReferences().AddReference(L09_USD)
l09.AddTranslateOp().Set(Gf.Vec3d(*POSE[:3]))
l09.AddRotateZOp().Set(POSE[3])
for pid, (x, y) in PLATES.items():
    p = UsdGeom.Xform.Define(stage, f"/World/Plate_{pid.replace('-', '_')}")
    p.GetPrim().GetReferences().AddReference(PLATE_USD)
    p.AddTranslateOp().Set(Gf.Vec3d(x, y, 0.0))
    p.AddOrientOp().Set(Gf.Quatf(1, 0, 0, 0))
    p.GetPrim().CreateAttribute("labware:barcode", Sdf.ValueTypeNames.String, custom=True).Set(pid)
for _ in range(5):
    app.update()

prims = list(Usd.PrimRange(l09.GetPrim()))
roots = [p for p in prims if p.HasAPI(UsdPhysics.ArticulationRootAPI)]
joints = sorted(p.GetName() for p in prims if p.IsA(UsdPhysics.Joint))
links = sorted(p.GetName() for p in prims if p.HasAPI(UsdPhysics.RigidBodyAPI))
check("S structure", len(roots) == 1 and len(joints) == 6 and len(links) == 6, joints=joints, links=links)

xc = UsdGeom.XformCache()
TRANSFER = np.array(xc.GetLocalToWorldTransform(stage.GetPrimAtPath("/World/L09_PlateHotel/transfer_nest"))
                    .ExtractTranslation())
SLOTS = [np.array(xc.GetLocalToWorldTransform(stage.GetPrimAtPath(f"/World/L09_PlateHotel/slot_frames/slot_{k:02d}"))
                  .ExtractTranslation()) for k in range(14)]
c, s = math.cos(math.radians(POSE[3])), math.sin(math.radians(POSE[3]))
R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])

app_utils.play(commit=True)
ctrl = L09Controller(stage, "/World/L09_PlateHotel")
plate_rp = {pid: RigidPrim(f"/World/Plate_{pid.replace('-', '_')}") for pid in PLATES}


def run(seconds):
    SimulationManager.step(steps=int(round(seconds * HZ)), callback=lambda i, n: ctrl.update(DT))


def run_until(pred, timeout):
    t0 = ctrl.t
    while ctrl.t - t0 < timeout:
        run(0.25)
        if pred():
            return True
    return False


def qyaw(deg):
    a = math.radians(deg) / 2
    return [math.cos(a), 0.0, 0.0, math.sin(a)]


def put_on_presented_nest(pid, dx=1.0, dy=-1.0, dyaw=0.5):
    pos = TRANSFER + R @ np.array([dx * 1e-3, dy * 1e-3, 0.013])
    plate_rp[pid].set_world_poses(positions=[pos.tolist()], orientations=[qyaw(POSE[3] + dyaw)])
    plate_rp[pid].set_velocities(linear_velocities=[[0, 0, 0]], angular_velocities=[[0, 0, 0]])
    run(1.0)


def remove(pid):
    plate_rp[pid].set_world_poses(positions=[[*PLATES[pid], 0.02]], orientations=[[1, 0, 0, 0]])
    plate_rp[pid].set_velocities(linear_velocities=[[0, 0, 0]], angular_velocities=[[0, 0, 0]])
    run(0.4)


def plate_pos(pid):
    return plate_rp[pid].get_world_poses()[0].numpy()[0].astype(float)


def in_slot(pid, k):
    e = R.T @ (plate_pos(pid) - SLOTS[k])
    return bool(np.all(np.abs(e[:2]) < 0.003) and abs(e[2]) < 0.0015), [round(v * 1e3, 2) for v in e]


t_start = time.time()
run(1.0)
sn = ctrl.snapshot()
check("T1 rest: READY, closed, stowed, parked, empty", sn["mode"] == "READY" and abs(sn["q_mm"]["gate"]) < 0.5
      and abs(sn["q_mm"]["shuttle"]) < 0.5 and not sn["slot_occupied"] and not ctrl.plate_on_nest, **sn["q_mm"])

r = ctrl.present_for_load()
ok = run_until(lambda: ctrl.mode == "PRESENTED_EMPTY", 8)
check("T2 present_for_load: gate open, nest presented", r.accepted and ok, **ctrl.snapshot()["q_mm"])

put_on_presented_nest("P-A")
r = ctrl.store("P-A", 3)
ok = run_until(lambda: ctrl.mode in ("READY", "FAULT"), 60)
inslot, err = in_slot("P-A", 3)
check("T3 store P-A -> slot 3", r.accepted and ok and ctrl.mode == "READY" and inslot and ctrl.inventory[3] == "P-A"
      and ctrl.slot_occupied[3] and abs(ctrl.q["gate"]) < 0.001, err_mm=err, mode=ctrl.mode, fault=ctrl.fault)

ctrl.present_for_load()
run_until(lambda: ctrl.mode == "PRESENTED_EMPTY", 8)
put_on_presented_nest("P-B", dx=-1.5, dy=2.0, dyaw=-1.0)
r = ctrl.store("P-B", 13)
ok = run_until(lambda: ctrl.mode in ("READY", "FAULT"), 60)
inslot, err = in_slot("P-B", 13)
check("T4 store P-B -> top slot 13", r.accepted and ok and ctrl.mode == "READY" and inslot and ctrl.inventory[13] == "P-B",
      err_mm=err, mode=ctrl.mode, fault=ctrl.fault)

ctrl.present_for_load()
run_until(lambda: ctrl.mode == "PRESENTED_EMPTY", 8)
put_on_presented_nest("P-C")
inv_before = list(ctrl.inventory)
r = ctrl.store("P-X", 0)
run_until(lambda: ctrl.mode in ("READY", "FAULT"), 30)
mismatch = ctrl.mode == "FAULT" and ctrl.fault == "slot_identity_mismatch" and ctrl.inventory == inv_before \
    and ctrl.plate_on_nest and abs(ctrl.q["shuttle"]) < 0.001
ctrl.reset_fault("test-operator")
run_until(lambda: ctrl.mode in ("READY", "FAULT"), 15)
r2 = ctrl.store("P-C", 0)
run_until(lambda: ctrl.mode in ("READY", "FAULT"), 60)
inslot, err = in_slot("P-C", 0)
check("T5 identity mismatch stops + keeps inventory; then stored", r.accepted and mismatch and r2.accepted and inslot
      and ctrl.inventory[0] == "P-C", mismatch_detected=mismatch, err_mm=err, fault=ctrl.fault)

ctrl.present_for_load()
run_until(lambda: ctrl.mode == "PRESENTED_EMPTY", 8)
put_on_presented_nest("P-D")
r = ctrl.store("P-D", 3)
check("T6 double occupancy refused", not r.accepted and "occupied" in r.reason, reason=r.reason)
remove("P-D")
ctrl.stow()
run_until(lambda: ctrl.mode == "READY", 8)

r = ctrl.retrieve("P-A")
ok = run_until(lambda: ctrl.mode in ("PRESENTED_LOADED", "FAULT"), 60)
e = R.T @ (plate_pos("P-A") - TRANSFER)
check("T7 retrieve P-A -> presented, seated, verified", r.accepted and ok and ctrl.mode == "PRESENTED_LOADED"
      and ctrl.seated and ctrl.inventory[3] == "" and np.all(np.abs(e[:2]) < 0.002)
      and any(ev["event"] == "identity_read" and ev["observed"] == "P-A" for ev in ctrl.events),
      err_mm=[round(v * 1e3, 2) for v in e], mode=ctrl.mode, fault=ctrl.fault)
remove("P-A")
ctrl.stow()
run_until(lambda: ctrl.mode == "READY", 8)

stowed_seat = np.array(xc.GetLocalToWorldTransform(stage.GetPrimAtPath("/World/L09_PlateHotel/load_frame"))
                       .ExtractTranslation())
plate_rp["P-D"].set_world_poses(positions=[(stowed_seat + [0, 0, 0.002]).tolist()], orientations=[qyaw(POSE[3])])
run(0.8)
r = ctrl.retrieve("P-B")
check("T8 retrieve refused: transfer nest not clear", not r.accepted and "not_clear" in r.reason, reason=r.reason)
remove("P-D")

r = ctrl.retrieve("P-B")
run(2.0)
door_target = math.radians(60)
ctrl.art.set_dof_position_targets(np.array([[door_target]], dtype=np.float32), dof_indices=[ctrl.dof["door"]])
run(2.0)
q_halt1 = dict(ctrl.q)
run(1.0)
held = all(abs(ctrl.q[k] - q_halt1[k]) < 0.0015 for k in ("lift", "fork")) and ctrl.door_open
ctrl.art.set_dof_position_targets(np.array([[0.0]], dtype=np.float32), dof_indices=[ctrl.dof["door"]])
ok = run_until(lambda: ctrl.mode in ("PRESENTED_LOADED", "FAULT"), 60)
ev = [e["event"] for e in ctrl.events]
check("T9 service-door interlock halts and resumes", r.accepted and held and ok and ctrl.mode == "PRESENTED_LOADED"
      and "handler_halted" in ev and "handler_resumed" in ev and ctrl.inventory[13] == "",
      held=held, mode=ctrl.mode, fault=ctrl.fault)

attr = lambda n: l09.GetPrim().GetAttribute(n).Get()  # noqa: E731
check("T10 state attributes mirror the controller", list(attr("state:inventory")) == ctrl.inventory
      and attr("state:mode") == ctrl.mode and attr("state:gate") == "open",
      inventory=list(attr("state:inventory")), mode=attr("state:mode"))

wall = time.time() - t_start
os.makedirs(REPORT_DIR, exist_ok=True)
with open(os.path.join(REPORT_DIR, "l09_physics_report.json"), "w") as f:
    json.dump({"asset": L09_USD, "physics_hz": HZ, "sim_time_s": round(ctrl.t, 2), "wall_time_s": round(wall, 1),
               "results": results}, f, indent=2)
ctrl.save_events(os.path.join(REPORT_DIR, "l09_events.json"))
failed = [r["test"] for r in results if not r["pass"]]
print(f"[test_l09] {len(results) - len(failed)}/{len(results)} passed; sim {ctrl.t:.0f}s in {wall:.0f}s wall")
app_utils.stop()
sys.stdout.flush()
os._exit(1 if failed else 0)
