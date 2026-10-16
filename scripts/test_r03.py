"""R03 (clean sample AMR) + H2 (deterministic dock) acceptance test in the Cell 01 overlay.

Scene: scenes/cell01_twin.usda (R03 referenced on its Cell 01 prim, its map frame = the docked pose in H2), an SBS
plate as the carrier in the AMR's cabinet nest. PhysX 240 Hz; R03Controller runs on every physics step. The AMR
starts outside the cell (front, east) and enters along the logistics lane. Faults are injected as physical or
sensor states the controller must notice (a localization bias, an opened lid, lost localization).

  S   structure: planar base + lid joints, Cell 01 binding frames, H2 dock sensor frames
  N1  carrier loaded (clean); navigate in: arrives at dock_approach (estimate within 1 cm / 1 deg); cabinet closed
      and carrier present over the whole route; open_cabinet refused while undocked (dock interlock)
  D1  dock (compliant): the V-guides centre the AMR; dock sensors confirm depth, yaw and lateral; latched
  C1  open cabinet when docked: carrier seated at handover_carrier_frame within 1 mm (deterministic handover pose)
  C2  close cabinet, undock: back at the approach pose; H2 free
  F1  localization bias 30 mm lateral + stiff drives: dock fails (not seated), backs out; relocalize; compliant
      retry docks
  F2  lid opened in transit (fault): AMR stops, cabinet_open_in_transit; close + reset
  F3  localization lost in transit: stop; relocalize; continue to the outside
  R1  the inbound transport as a Cell 01 `transport` record (R03): validates and commits

Writes test_reports/r03_report.json; exit 1 on any failure.
"""

import json
import math
import os
import sys

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
OVERLAY = os.path.join(ROOT, "scenes/cell01_twin.usda")
REPORT = os.path.join(ROOT, "test_reports/r03_report.json")
R03 = "/World/Cell01/Robots/R03_SampleAMR"
H2 = "/World/Cell01/Stations/H2_AMR_Dock"
HZ = 240
DT = 1.0 / HZ

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True})

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from isaacsim.core.experimental.prims import RigidPrim  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402
from pxr import Gf, PhysxSchema, UsdGeom  # noqa: E402

from twin.episode_records import Schemas, build_record, validate  # noqa: E402
from twin.r01_rig import add_plate  # noqa: E402
from twin.r03_controller import R03Controller, author_r03_start, carrier_seat_world  # noqa: E402

results = []


def check(name, ok, **vals):
    results.append({"test": name, "pass": bool(ok), **vals})
    print(f"[test_r03] {'PASS' if ok else 'FAIL'}  {name}  {json.dumps(vals, default=str)[:900]}", flush=True)


omni.usd.get_context().open_stage(OVERLAY)
for _ in range(10):
    app.update()
stage = omni.usd.get_context().get_stage()
px = PhysxSchema.PhysxSceneAPI.Apply(stage.GetPrimAtPath("/World/PhysicsScene"))
px.CreateTimeStepsPerSecondAttr(HZ)
px.CreateSolverTypeAttr("TGS")
xc = UsdGeom.XformCache()
MAP = xc.GetLocalToWorldTransform(stage.GetPrimAtPath(R03))
HANDOVER = np.array(xc.GetLocalToWorldTransform(stage.GetPrimAtPath(f"{R03}/handover_carrier_frame")).ExtractTranslation())
START = (-2.565, 2.72, -math.pi / 2)            # map pose: world (1.2, -3.0), heading north, outside the cell front
ROUTE_IN = [START[:2], (-2.565, 0.72), (-2.165, 0.0), (-1.0, 0.0)]
ROUTE_OUT = [(-1.0, 0.0), (-2.165, 0.0), (-2.565, 0.72), (-2.565, 2.72)]
author_r03_start(stage, R03, START)
_pc, _yc = carrier_seat_world(stage, R03, START)
add_plate(stage, "/World/TestFixtures/Carrier", _pc + [0, 0, 0.0005], _yc, barcode="Plate_P30")
PhysxSchema.PhysxRigidBodyAPI.Apply(stage.GetPrimAtPath("/World/TestFixtures/Carrier")).CreateSleepThresholdAttr(0.0)
frames = [n for n in ("base_link", "carrier_cabinet", "dock_approach", "dock_frame", "handover_carrier_frame")
          if stage.GetPrimAtPath(f"{R03}/{n}")]
for _ in range(5):
    app.update()

app_utils.play(commit=True)
amr = R03Controller(stage, R03, H2)
carrier = RigidPrim("/World/TestFixtures/Carrier")
d = amr.dof
amr._command_est(np.array(START))
sch = Schemas()


def run(seconds):
    SimulationManager.step(steps=int(round(seconds * HZ)), callback=lambda i, n: amr.update(DT))


def run_until(pred, timeout):
    t0 = amr.t
    while amr.t - t0 < timeout:
        run(0.25)
        if pred():
            return True
    return False


def idle(timeout=120):
    return run_until(lambda: not amr.busy(), timeout)


def to_world(p_map):
    return np.array(MAP.Transform(Gf.Vec3d(*map(float, p_map))))


run(1.5)
check("S structure: planar base + lid, Cell 01 frames, dock sensors, carrier seated at the start",
      set(amr.dof) == {"x", "y", "yaw", "lid"} and len(frames) == 5 and len(amr.rays) == 4 and amr.carrier_seated,
      frames=frames, carrier_gaps=amr.carrier_gaps, start_true=np.round(amr.pose_true(), 3).tolist())

# ---------------------------------------------------------------- N1 inbound
t_in = amr.t
amr.load_carrier("Plate_P30")
r = amr.navigate(ROUTE_IN)
ok = r.accepted and idle(120)
tr = [x for x in amr.trace if x[0] >= t_in]
e = amr.pose_est()
r_open = amr.open_cabinet()
check("N1 navigate in: at dock_approach, cabinet closed and carrier present all the way; cabinet locked undocked",
      ok and amr.mode == "READY" and np.hypot(e[0] + 1.0, e[1]) < 0.01 and abs(amr._wrap(e[2])) < math.radians(1)
      and all(x[4] == "closed" and x[5] for x in tr) and not r_open.accepted and amr.battery < 100.0,
      estimate=np.round(e, 4).tolist(), samples=len(tr), refused=r_open.reason, battery=round(amr.battery, 2),
      duration_s=round(amr.t - t_in, 1))
t_arrive = amr.t

# ---------------------------------------------------------------- D1 dock
r = amr.dock(compliant=True)
ok = r.accepted and idle(60)
check("D1 dock (compliant): V-guides centre it; depth, yaw, lateral in tolerance; latched", ok and amr.mode == "DOCKED"
      and amr.last_dock["ok"] and abs(amr.pose_true()[1]) < 0.003, residual=amr.last_dock,
      true_mm_deg=[round(amr.pose_true()[0] * 1e3, 2), round(amr.pose_true()[1] * 1e3, 2),
                   round(math.degrees(amr.pose_true()[2]), 3)])
dock_rec = dict(amr.last_dock)
t_docked = amr.t

# ---------------------------------------------------------------- C1 / C2 cabinet + undock
amr.open_cabinet()
idle(10)
pc = carrier.get_world_poses()[0].numpy()[0]
off = np.round((pc - HANDOVER) * 1e3, 2).tolist()
check("C1 cabinet opens when docked; carrier seated at handover_carrier_frame (within 1 mm)", amr.cabinet == "open"
      and amr.carrier_seated and math.hypot(off[0], off[1]) < 1.0 and abs(off[2]) < 0.5, offset_mm=off,
      gaps=amr.carrier_gaps)
amr.close_cabinet()
idle(10)
r = amr.undock()
ok = r.accepted and idle(60)
h2_state = stage.GetPrimAtPath(H2).GetAttribute("state:dock_state").Get()
check("C2 close + undock: back at the approach pose, H2 free", ok and amr.cabinet == "closed" and amr.mode == "READY"
      and abs(amr.pose_est()[0] + 1.0) < 0.005 and h2_state == "free", estimate=np.round(amr.pose_est(), 4).tolist(),
      h2=h2_state)

# ---------------------------------------------------------------- F1 dock misalignment
amr.bias = np.array([0.0, 0.030, 0.0])           # the AMR believes it is 30 mm to the left of where it is
amr._command_est(amr.pose_est())
run(1.0)
r = amr.dock(compliant=False)
idle(60)
failed_dock = dict(amr.last_dock)
backed = amr.mode == "READY" and abs(amr.pose_est()[0] + 1.0) < 0.005
amr.relocalize("dock fiducial")
amr._command_est(np.array([-1.0, 0.0, 0.0]))
run(2.0)
r2 = amr.dock(compliant=True)
idle(60)
check("F1 30 mm localization bias + stiff drives: dock fails and backs out; relocalize; compliant retry docks",
      r.accepted and not failed_dock["ok"] and backed and r2.accepted and amr.mode == "DOCKED" and amr.last_dock["ok"],
      failed=failed_dock, retry=amr.last_dock)
amr.undock()
idle(60)

# ---------------------------------------------------------------- F2 cabinet open in transit
r = amr.navigate(ROUTE_OUT, reverse=True)
run(4.0)
amr.art.set_dof_position_targets(np.array([[-0.10]], dtype=np.float32), dof_indices=[d["lid"]])   # latch fails
idle(30)
f2 = amr.fault
amr.close_cabinet()
idle(10)
r_reset = amr.reset_fault("operator: lid closed; carrier sample validity to be evaluated")
check("F2 lid opened in transit: AMR stops (cabinet_open_in_transit); closed; reset", r.accepted
      and f2 == "cabinet_open_in_transit" and r_reset.accepted and amr.cabinet == "closed", fault=f2,
      events=[x["event"] for x in amr.events[-5:]])

# ---------------------------------------------------------------- F3 localization lost
e = amr.pose_est()
r = amr.navigate([tuple(e[:2]), ROUTE_OUT[-1]], reverse=True)
run(2.0)
amr.localization_ok = False                      # localization lost (sensor state)
idle(30)
f3 = amr.fault
amr.relocalize("site marker")
e = amr.pose_est()
r = amr.navigate([tuple(e[:2]), ROUTE_OUT[-1]], reverse=True)
ok = r.accepted and idle(120)
check("F3 localization lost: stop; relocalize; continue out of the cell", f3 == "localization_lost" and ok
      and np.hypot(*(amr.pose_est()[:2] - np.array(ROUTE_OUT[-1]))) < 0.02, fault=f3,
      final=np.round(amr.pose_est(), 3).tolist())

# ---------------------------------------------------------------- R1 record
tr = [x for x in amr.trace if t_in <= x[0] <= t_docked]
des = {
    "id": "test-r03/transport_in", "action": "transport", "component": "R03_AMR_H2_Dock",
    "interaction_frames": {"source_frame": "dock_approach", "target_frame": "handover_carrier_frame"},
    "bindings": {"object_id": "Plate_P30", "source_frame": "site entry (outside Cell 01)",
                 "target_frame": "H2/handover_carrier_frame", "route": "logistics lane -> dock_approach -> H2",
                 "contamination_state": "clean_sample_only (carrier class clean)"},
    "monitors": [
        dict(name="route_clear", passed=all(x[7] for x in tr), observation="localization healthy along the route; "
             "arrived at dock_approach within 1 cm", value={"samples": len(tr)}),
        dict(name="object_identity", passed="Plate_P30" in amr.inventory, observation="carrier id bound at loading, "
             "carried in the closed cabinet (transport history)", value=list(amr.inventory)),
        dict(name="object_pose_or_grasp", passed=all(x[5] for x in tr), observation="carrier presence sensors: present "
             "for the whole transport; seated at the docked handover pose", value=dock_rec),
        dict(name="contamination_compatibility", passed=amr.contamination_class == "clean_sample_only",
             observation="clean carrier on the clean-sample AMR; cabinet closed in transit", value="clean"),
        dict(name="elapsed_time", passed=True, observation=f"transport took {t_docked - t_in:.1f} s",
             value=round(t_docked - t_in, 2)),
    ],
    "command_completed": True, "t_start": round(t_in, 3), "t_end": round(t_docked, 3),
    "semantic_target": "CultureSDT.custody_event", "semantic_effect": "Plate_P30 delivered to H2 by R03",
    "failure_route": "human_escalation", "failure_target": "human",
    "evidence": {"route": ROUTE_IN, "timestamps": {"start": round(t_in, 3), "docked": round(t_docked, 3)},
                 "dock_result": dock_rec},
}
rec = build_record(sch, "test-r03", des)
errs = validate(sch, rec)
check("R1 inbound transport as a Cell 01 transport record: valid, commits", not errs and rec["semantic_event"]["eligible"],
      errors=errs, routing=rec["routing"])

report = {"results": results, "passed": sum(r["pass"] for r in results), "total": len(results),
          "events": amr.events, "trace": amr.trace[::4], "record": rec}
with open(REPORT, "w") as f:
    json.dump(report, f, indent=2, default=str)
print(f"[test_r03] {report['passed']}/{report['total']} passed", flush=True)
app_utils.stop()
sys.stdout.flush()
os._exit(0 if report["passed"] == report["total"] else 1)
