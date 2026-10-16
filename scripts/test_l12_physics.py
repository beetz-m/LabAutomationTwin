"""Physics + liquid-handling acceptance test for the articulated L12 Automated Liquid-Handling Station.

Scene: ground, L12 at an arbitrary pose, an SBS plate placed robot-style on the plate nest, 24 tips in the rack,
four reagent tubes. PhysX 240 Hz; L12Controller in the loop. Tips are rigid bodies picked by the channel's surface
gripper and ejected into the waste bin; the liquid model uses the real tip pose. Each dose is turned into a Cell 01
NEEM record by Cell 01's own L12 helpers (validate_l12_dose, build_l12_neem_record).

  S   structure: one articulation root, gantry joints, TipMount + tip gripper, Cell 01 binding frames
  D1  park: READY, gantry parked clear of the plate nest
  D2  dose_well A03, 10 uL from the challenge reagent: all 8 monitors pass, record commits; tube -10 uL, well +10 uL,
      pressure-inferred volume within 5 %, the tip is in the waste bin
  D3  wrong reagent (position holds a different reagent): aborted before any tip or aspiration; routed H4 / human
  D4  tip missing (the next rack position is empty, the inventory says loaded): no tip attached, aborted
  D5  low reagent (60 uL in the tube, inventory says 1000 uL): cLLD finds the surface ~15 mm low, aborted before
      aspiration
  D6  clog during aspiration: pressure hits the clog limit, less volume delivered, dose uncertain: not committed
  D7  plate not seated (removed): plate_identity / plate_seating fail, aborted
  D8  every record validates against the Cell 01 schemas; only D2 commits
  D9  state attributes mirror the controller

Writes test_reports/l12_physics_report.json and l12_events.json; exit 1 on any failure.
"""

import json
import os
import sys
import time

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
L12_USD = os.path.join(ROOT, "assets/l12/l12.usda")
REPORT_DIR = os.path.join(ROOT, "test_reports")
HZ = 240
DT = 1.0 / HZ
POSE = (1.0, -0.6, 0.0, 20.0)
L = "/World/L12_LiquidHandler"

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True})

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402

for ext in ("isaacsim.robot.surface_gripper", "isaacsim.robot.schema"):
    app_utils.enable_extension(ext)
app.update()

import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from isaacsim.core.experimental.prims import RigidPrim  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402
from pxr import Gf, PhysxSchema, Usd, UsdGeom, UsdPhysics  # noqa: E402

from twin.episode_records import Schemas, l12_dose_record, validate  # noqa: E402
from twin.l12_controller import L12Controller, add_reagent_tube, add_tips, author_l12  # noqa: E402
from twin.r01_rig import add_plate  # noqa: E402

results = []


def check(name, ok, **values):
    results.append({"test": name, "pass": bool(ok), **values})
    print(f"[test_l12] {'PASS' if ok else 'FAIL'}  {name}  {json.dumps(values, default=str)[:900]}", flush=True)


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
l12 = UsdGeom.Xform.Define(stage, L)
l12.GetPrim().GetReferences().AddReference(L12_USD)
l12.AddTranslateOp().Set(Gf.Vec3d(*POSE[:3]))
l12.AddRotateZOp().Set(POSE[3])
for _ in range(3):
    app.update()
grip = author_l12(stage, L)
order = [f"{r}{c:02d}" for c in (1, 2, 3) for r in "ABCDEFGH"]
tips = add_tips(stage, L, order)
REAGENTS = {1: ("RGT-0001", "abstract_challenge_reagent", "SIM-LOT-A", 1000.0),
            2: ("RGT-0002", "abstract_rescue_reagent", "SIM-LOT-B", 1000.0),
            3: ("RGT-0003", "abstract_rescue_reagent", "SIM-LOT-B", 1000.0),
            4: ("RGT-0004", "abstract_challenge_reagent", "SIM-LOT-A", 60.0)}
for pos, (bc, rid, lot, vol) in REAGENTS.items():
    add_reagent_tube(stage, L, pos, bc, rid, lot, vol)
INVENTORY = {1: dict(reagent_id="abstract_challenge_reagent", lot="SIM-LOT-A", volume_uL=1000.0),
             2: dict(reagent_id="abstract_rescue_reagent", lot="SIM-LOT-B", volume_uL=1000.0),
             3: dict(reagent_id="abstract_challenge_reagent", lot="SIM-LOT-A", volume_uL=1000.0),   # belief is wrong
             4: dict(reagent_id="abstract_challenge_reagent", lot="SIM-LOT-A", volume_uL=1000.0)}   # belief is wrong
xc = UsdGeom.XformCache()
NEST = np.array(xc.GetLocalToWorldTransform(stage.GetPrimAtPath(f"{L}/plate_nest")).ExtractTranslation())
add_plate(stage, "/World/Plate", NEST + [0, 0, 0.004], POSE[3], barcode="Plate_L12_T1")
PhysxSchema.PhysxRigidBodyAPI.Apply(stage.GetPrimAtPath("/World/Plate")).CreateSleepThresholdAttr(0.0)
for _ in range(5):
    app.update()

prims = list(Usd.PrimRange(l12.GetPrim()))
roots = [p for p in prims if p.HasAPI(UsdPhysics.ArticulationRootAPI)]
joints = sorted(p.GetName() for p in prims if p.IsA(UsdPhysics.Joint))
frames = [n for n in ("deck_frame", "tip_rack_frames", "reagent_rack_frames", "plate_nest", "pipette_tip_frame")
          if stage.GetPrimAtPath(f"{L}/{n}")]

app_utils.play(commit=True)
ctrl = L12Controller(stage, L, grip, tips=dict(tips), reagent_inventory=INVENTORY)
plate = RigidPrim("/World/Plate")
missing_tip = RigidPrim(tips[order[1]])      # created early: a view made right before its first write can drop it
sch = Schemas()


def run(seconds):
    SimulationManager.step(steps=int(round(seconds * HZ)), callback=lambda i, n: ctrl.update(DT))


def run_until(pred, timeout):
    t0 = ctrl.t
    while ctrl.t - t0 < timeout:
        run(0.25)
        if pred():
            return True
    return False


def dose(**kw):
    n = len(ctrl.doses)
    base = dict(plate_id="Plate_L12_T1", well_id="A03", reagent_pos=1, reagent_id="abstract_challenge_reagent",
                reagent_lot="SIM-LOT-A", volume_uL=10.0, dispense_height_mm=1.2, dispense_rate_uL_s=2.0,
                intended_effect="abstract_challenge")
    base.update(kw)
    r = ctrl.dose_well(**base)
    ok = r.accepted and run_until(lambda: ctrl.mode != "BUSY", 180)
    d = ctrl.doses[-1] if len(ctrl.doses) > n else None
    rec = l12_dose_record(d, f"test-l12-{len(ctrl.doses):02d}", sch) if d else None
    return ok, d, rec


def failed(d):
    return [m["name"] for m in d["monitors"] if not m["passed"]]


t_start = time.time()
run(1.0)
check("S structure + binding frames + tip gripper", len(roots) == 1 and {"GantryXSlide", "GantryYSlide",
      "ChannelZSlide", "TipLock", "TipMountJoint"} <= set(joints) and len(frames) == 5 and ctrl.seated,
      joints=joints, frames=frames, seated=ctrl.seated)

check("D1 parked, READY", ctrl.mode == "READY" and abs(ctrl.q["x"] - ctrl.park[0]) < 0.001, q_mm={k: round(v * 1e3, 2)
      for k, v in ctrl.q.items()})

tube1 = None
ok, d, rec = dose()
ev = d["evidence"]
tube1 = ctrl.liquid.containers.get(next((k for k in ctrl.liquid.containers if k.endswith("Tube_1")), ""), None)
tip_z = ev.get("eject", {}).get("tip_z_after_mm")
check("D2 dose A03 10 uL: all monitors pass, commit, volumes, tip in waste", ok and d["valid"]
      and rec["routing"] == "culture_sdt_commit" and abs(ev.get("well_volume_after_uL", 0) - 110.0) < 0.3
      and tube1 is not None and abs(tube1.volume_uL - 990.0) < 0.3 and abs((d["volume_inferred_uL"] or 0) - 10.0) < 0.5
      and tip_z is not None and tip_z < 120.0 and d["volume_inferred_uL"] is not None,
      failed=failed(d), aborted=d["aborted"], lld=ev.get("lld"),
      aspirate={k: ev.get("aspirate", {}).get(k) for k in ("plateau_mbar", "expected_mbar", "ok")},
      dispense={k: ev.get("dispense", {}).get(k) for k in ("plateau_mbar", "inferred_from_pressure_uL", "ok")},
      well=ev.get("well_volume_after_uL"), tube=round(tube1.volume_uL, 2) if tube1 else None,
      well_position=ev.get("well_position"), tip=ev.get("tip"), eject=ev.get("eject"))

used0 = set(ctrl.used_tips)
ok, d, rec = dose(well_id="A04", reagent_pos=3)
check("D3 wrong reagent: aborted before tip pick / aspiration, routed H4 / human", ok and not d["valid"]
      and "wrong_reagent" in (d["aborted"] or "") and set(ctrl.used_tips) == used0
      and rec["routing"] == "H4_or_human_escalation", failed=failed(d), aborted=d["aborted"])

nxt = [p for p in ctrl.tips if p not in ctrl.used_tips][0]
assert tips[nxt] == tips[order[1]], nxt
missing_tip.set_world_poses(positions=[[POSE[0] + 3.0, POSE[1], 0.01]])           # someone took that tip
run(0.3)
ok, d, rec = dose(well_id="A05")
check("D4 tip missing at the next rack position: no tip, aborted, nothing aspirated", ok and not d["valid"]
      and "tip_missing" in (d["aborted"] or "") and ctrl.liquid.aspirated_uL == 0.0, failed=failed(d),
      tip=d["evidence"].get("tip"))

ok, d, rec = dose(well_id="A06", reagent_pos=4)
check("D5 low reagent (60 uL vs 1000 uL believed): cLLD deviation, aborted before aspiration", ok and not d["valid"]
      and "liquid level" in (d["aborted"] or "") and (d["evidence"]["lld"]["deviation_mm"] or 0) < -10.0
      and ctrl.liquid.aspirated_uL == 0.0, failed=failed(d), lld=d["evidence"].get("lld"))

ctrl.liquid.clog_at = 0.4
ok, d, rec = dose(well_id="A07")
ctrl.liquid.clog_at = None
asp = d["evidence"].get("aspirate", {})
check("D6 clog: pressure at the clog limit, less volume, dose uncertain (not committed)", ok and not d["valid"]
      and asp.get("clog_limit_hit") and "pressure_profile" in failed(d) and "dispense_completion" in failed(d)
      and rec["routing"] == "H4_or_human_escalation", failed=failed(d),
      aspirate={k: asp.get(k) for k in ("plateau_mbar", "expected_mbar", "clog_limit_hit")},
      inferred=d["volume_inferred_uL"], well=d["evidence"].get("well_volume_after_uL"))

plate.set_world_poses(positions=[[POSE[0] + 3.0, POSE[1] + 1.0, 0.01]])
run(0.5)
ok, d, rec = dose(well_id="A08")
check("D7 plate removed: identity / seating fail, aborted", ok and not d["valid"]
      and {"plate_identity", "plate_seating"} <= set(failed(d)) and d["aborted"], failed=failed(d), aborted=d["aborted"])

recs = [l12_dose_record(x, f"test-l12-{i:02d}", sch) for i, x in enumerate(ctrl.doses)]
for i, r in enumerate(recs):
    r["designator_id"] = f"test/{i}"
errs = {i: validate(sch, r) for i, r in enumerate(recs)}
commits = [r["semantic_event"]["eligible"] for r in recs]
check("D8 Cell 01 records validate; only the nominal dose commits", not any(errs.values())
      and commits == [True, False, False, False, False, False], commits=commits, errors=errs)

attr = lambda n: l12.GetPrim().GetAttribute(n).Get()  # noqa: E731
check("D9 state attributes mirror the controller", attr("state:mode") == ctrl.mode and attr("state:tip_present") is False
      and attr("state:tip_id") == "", mode=attr("state:mode"), tip=attr("state:tip_present"),
      aspirated=attr("state:aspirated_volume_uL"))

wall = time.time() - t_start
with open(os.path.join(REPORT_DIR, "l12_physics_report.json"), "w") as f:
    json.dump({"asset": L12_USD, "physics_hz": HZ, "sim_time_s": round(ctrl.t, 1), "wall_time_s": round(wall, 1),
               "results": results, "doses": ctrl.doses, "records": recs,
               "containers": {k: {"volume_uL": round(v.volume_uL, 3), "contents": {s: round(q, 3) for s, q in v.contents.items()}}
                              for k, v in ctrl.liquid.containers.items()}}, f, indent=2, default=str)
ctrl.save_events(os.path.join(REPORT_DIR, "l12_events.json"))
failed_tests = [r["test"] for r in results if not r["pass"]]
print(f"[test_l12] {len(results) - len(failed_tests)}/{len(results)} passed; sim {ctrl.t:.0f}s in {wall:.0f}s wall",
      flush=True)
app_utils.stop()
sys.stdout.flush()
os._exit(1 if failed_tests else 0)
