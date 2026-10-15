"""Physics + environment acceptance test for the articulated L10 Automated CO2 Incubator.

Scene: ground, L10 on the floor at an arbitrary pose, SBS plates with barcodes. PhysX 240 Hz, L10Controller in
the loop (handler physically simulated; environment model in the controller).

  S   structure: one articulation root, 6 joints, 6 links, 44 slots, binding frames present
  T1  rest: READY, environment at setpoint and valid, no alarm
  T2  incubate P-A into slot 0 (present, robot-style placement, store): plate on the slot-0 ledges
  T3  incubate P-B into the top slot 43 (full lift travel)
  T4  environment stayed in the envelope through both transfers (brief gate openings)
  T5  service door open 6 s: temperature and CO2 excursion alarms, environment invalid, red lamp,
      stored plates record time out of envelope
  T6  incubate refused while the environment is invalid
  T7  recovery: back inside the envelope after the door closes, alarms cleared
  T8  release_plate P-A: presented, seated, identity verified; release record carries the environment state and
      the plate's exposure history (incl. the excursion); time-outside clock runs
  T9  gate_stuck_open alarm when the gate stays open past the limit (limit shortened for the test)
  T10 state attributes mirror the controller (temperature, CO2, alarm, environment_valid, inventory)

Writes test_reports/l10_physics_report.json, l10_events.json, l10_environment.csv; exit 1 on any failure.
"""

import json
import math
import os
import sys
import time

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
L10_USD = os.path.join(ROOT, "assets/l10/l10.usda")
PLATE_USD = os.path.join(ROOT, "assets/labware/plate_sbs96.usda")
REPORT_DIR = os.path.join(ROOT, "test_reports")
HZ = 240
DT = 1.0 / HZ
POSE = (1.0, -0.6, 0.0, 20.0)
PLATES = {"P-A": (4.0, 4.0), "P-B": (4.3, 4.0)}
L = "/World/L10_Incubator"

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True})

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from isaacsim.core.experimental.prims import RigidPrim  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics  # noqa: E402

from twin.l10_controller import L10Controller  # noqa: E402

results = []


def check(name, ok, **values):
    fmt = lambda v: round(v, 4) if isinstance(v, float) else v  # noqa: E731
    vals = {k: fmt(v) for k, v in values.items()}
    results.append({"test": name, "pass": bool(ok), **vals})
    print(f"[test_l10] {'PASS' if ok else 'FAIL'}  {name}  {vals}", flush=True)


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
g = UsdGeom.Xform.Define(stage, "/World/Ground")
g.AddTranslateOp().Set(Gf.Vec3d(0, 0, -0.05))
c = UsdGeom.Cube.Define(stage, "/World/Ground/Box")
c.CreateSizeAttr(1.0)
c.AddScaleOp().Set(Gf.Vec3f(20, 20, 0.1))
UsdPhysics.CollisionAPI.Apply(c.GetPrim())
l10 = UsdGeom.Xform.Define(stage, L)
l10.GetPrim().GetReferences().AddReference(L10_USD)
l10.AddTranslateOp().Set(Gf.Vec3d(*POSE[:3]))
l10.AddRotateZOp().Set(POSE[3])
for pid, (x, y) in PLATES.items():
    p = UsdGeom.Xform.Define(stage, f"/World/Plate_{pid.replace('-', '_')}")
    p.GetPrim().GetReferences().AddReference(PLATE_USD)
    p.AddTranslateOp().Set(Gf.Vec3d(x, y, 0.0))
    p.AddOrientOp().Set(Gf.Quatf(1, 0, 0, 0))
    p.GetPrim().CreateAttribute("labware:barcode", Sdf.ValueTypeNames.String, custom=True).Set(pid)
for _ in range(5):
    app.update()

prims = list(Usd.PrimRange(l10.GetPrim()))
roots = [p for p in prims if p.HasAPI(UsdPhysics.ArticulationRootAPI)]
joints = sorted(p.GetName() for p in prims if p.IsA(UsdPhysics.Joint))
links = sorted(p.GetName() for p in prims if p.HasAPI(UsdPhysics.RigidBodyAPI))
binding = [n for n in ("transfer_station", "gate_frame", "cassette_slots", "service_door")
           if stage.GetPrimAtPath(f"{L}/{n}")]
nslots = len(stage.GetPrimAtPath(f"{L}/cassette_slots").GetChildren())
check("S structure + Cell 01 binding frames", len(roots) == 1 and len(joints) == 6 and len(links) == 6
      and len(binding) == 4 and nslots == 44, joints=joints, binding=binding, slots=nslots)

xc = UsdGeom.XformCache()
TRANSFER = np.array(xc.GetLocalToWorldTransform(stage.GetPrimAtPath(f"{L}/transfer_station")).ExtractTranslation())
SLOT = lambda k: np.array(xc.GetLocalToWorldTransform(  # noqa: E731
    stage.GetPrimAtPath(f"{L}/cassette_slots/slot_{k:02d}")).ExtractTranslation())
cs, sn = math.cos(math.radians(POSE[3])), math.sin(math.radians(POSE[3]))
R = np.array([[cs, -sn, 0], [sn, cs, 0], [0, 0, 1]])

app_utils.play(commit=True)
ctrl = L10Controller(stage, L)
rp = {pid: RigidPrim(f"/World/Plate_{pid.replace('-', '_')}") for pid in PLATES}


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


def place(pid, dx=1.0, dy=-1.0):
    rp[pid].set_world_poses(positions=[(TRANSFER + R @ np.array([dx * 1e-3, dy * 1e-3, 0.013])).tolist()],
                            orientations=[qyaw(POSE[3] + 0.5)])
    rp[pid].set_velocities(linear_velocities=[[0, 0, 0]], angular_velocities=[[0, 0, 0]])
    run(1.0)


def in_slot(pid, k):
    e = R.T @ (rp[pid].get_world_poses()[0].numpy()[0] - SLOT(k))
    return bool(np.all(np.abs(e[:2]) < 0.003) and abs(e[2]) < 0.0015), [round(float(v) * 1e3, 2) for v in e]


def env_range(t0):
    rows = [r for r in ctrl.series if r[0] >= t0]
    return (min(r[1] for r in rows), max(r[1] for r in rows), min(r[2] for r in rows), max(r[2] for r in rows))


t_start = time.time()
run(1.0)
check("T1 rest: READY, environment at setpoint, valid", ctrl.mode == "READY" and ctrl.environment_valid
      and not ctrl.alarms and abs(ctrl.env["T"] - 37) < 0.01, env={k: round(v, 3) for k, v in ctrl.env.items()})

t_transfers = ctrl.t
for pid, slot, label in (("P-A", 0, "T2 incubate P-A -> slot 0"), ("P-B", 43, "T3 incubate P-B -> top slot 43")):
    ctrl.present_for_load()
    run_until(lambda: ctrl.mode == "PRESENTED_EMPTY", 10)
    place(pid)
    r = ctrl.incubate(pid, slot)
    ok = run_until(lambda: ctrl.mode in ("READY", "FAULT"), 90)
    inslot, err = in_slot(pid, slot)
    check(label, r.accepted and ok and ctrl.mode == "READY" and inslot and ctrl.inventory[slot] == pid,
          err_mm=err, mode=ctrl.mode, fault=ctrl.fault)
tmin, tmax, cmin, cmax = env_range(t_transfers)
check("T4 environment within envelope through transfers", ctrl.environment_valid and tmin >= 36.5 and cmin >= 4.7
      and not any(e["event"] == "alarm_raised" for e in ctrl.events), T_min=tmin, CO2_min=cmin,
      gate_open_total_s=round(ctrl.door_open_total_s, 1))

door = ctrl.dof["door"]
ctrl.art.set_dof_position_targets(np.array([[math.radians(90)]], dtype=np.float32), dof_indices=[door])
run(6.0)
red = stage.GetPrimAtPath(f"{L}/Looks/LensRed/Shader").GetAttribute("inputs:emissive_intensity").Get()
exc = {"temperature_excursion", "CO2_excursion"} <= ctrl.alarms
hA = ctrl.environment_history("P-A")
check("T5 door open 6 s -> T/CO2 excursion alarms, plates exposed", exc and not ctrl.environment_valid and red > 0
      and hA["time_out_of_envelope_s"] > 0, alarms=sorted(ctrl.alarms), T=round(ctrl.env["T"], 2),
      CO2=round(ctrl.env["CO2"], 2), exposure_s=hA["time_out_of_envelope_s"])

r = ctrl.incubate("P-X", 5)
check("T6 incubate refused while environment invalid", not r.accepted and "environment not valid" in r.reason,
      reason=r.reason)

ctrl.art.set_dof_position_targets(np.array([[0.0]], dtype=np.float32), dof_indices=[door])
t_close = ctrl.t
ok = run_until(lambda: ctrl.environment_valid, 400)
check("T7 recovery into the envelope after closing", ok and not (ctrl.alarms - {"humidity_excursion"}),
      recovery_s=round(ctrl.t - t_close, 1), env={k: round(v, 2) for k, v in ctrl.env.items()},
      alarms=sorted(ctrl.alarms))

r = ctrl.release_plate("P-A")
ok = run_until(lambda: ctrl.mode in ("PRESENTED_LOADED", "FAULT"), 90)
run(2.0)
h = ctrl.environment_history("P-A")
e = R.T @ (rp["P-A"].get_world_poses()[0].numpy()[0] - TRANSFER)
check("T8 release_plate: presented, verified, environment record", r.accepted and ok and ctrl.seated
      and "release" in h and h["time_out_of_envelope_s"] > 0 and h["time_outside_controlled_environment_s"] >= 1.9
      and np.all(np.abs(e[:2]) < 0.002), err_mm=[round(float(v) * 1e3, 2) for v in e],
      release_env=h.get("release", {}).get("environment"), outside_s=h.get("time_outside_controlled_environment_s"),
      exposure_s=h.get("time_out_of_envelope_s"))

ctrl.gate_open_limit_s = 3.0  # shortened for the test (gate is open while the nest is presented)
run(4.0)
check("T9 gate_stuck_open alarm past the limit", "gate_stuck_open" in ctrl.alarms, alarms=sorted(ctrl.alarms))

attr = lambda n: l10.GetPrim().GetAttribute(n).Get()  # noqa: E731
check("T10 state attributes mirror the controller", abs(attr("state:temperature_C") - ctrl.env["T"]) < 0.01
      and abs(attr("state:CO2_percent") - ctrl.env["CO2"]) < 0.01 and "gate_stuck_open" in attr("state:alarm")
      and list(attr("state:inventory")) == ctrl.inventory,
      T=attr("state:temperature_C"), alarm=attr("state:alarm"), valid=attr("state:environment_valid"))

wall = time.time() - t_start
os.makedirs(REPORT_DIR, exist_ok=True)
with open(os.path.join(REPORT_DIR, "l10_physics_report.json"), "w") as f:
    json.dump({"asset": L10_USD, "physics_hz": HZ, "sim_time_s": round(ctrl.t, 1), "wall_time_s": round(wall, 1),
               "results": results, "plate_histories": {p: ctrl.environment_history(p) for p in PLATES}}, f, indent=2)
ctrl.save_events(os.path.join(REPORT_DIR, "l10_events.json"))
with open(os.path.join(REPORT_DIR, "l10_environment.csv"), "w") as f:
    f.write("t_s,temperature_C,CO2_percent,humidity_percent,gate_open_frac,door_open_frac\n")
    f.writelines(",".join(map(str, r)) + "\n" for r in ctrl.series)
failed = [r["test"] for r in results if not r["pass"]]
print(f"[test_l10] {len(results) - len(failed)}/{len(results)} passed; sim {ctrl.t:.0f}s in {wall:.0f}s wall", flush=True)
app_utils.stop()
sys.stdout.flush()
os._exit(1 if failed else 0)
