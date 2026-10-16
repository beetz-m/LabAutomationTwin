"""R02 serves L12 in the Cell 01 overlay: plate onto the liquid handler's nest, a dose, plate back to the handover nest.

Scene: scenes/cell01_twin.usda (L12 on the central bench, TCM01, the R01/R02 handover nest HN), R02 added at runtime,
an SBS plate seated in HN; L12's tips and reagent tubes are loaded at runtime. PhysX 240 Hz; L12Controller runs on every physics step.

  R1  R02 homed, T01 coupled from the magazine (lock, ID, follow checks of the tool changer)
  R2  T01 picks the plate from HN (seated there first: HN seat sensors)
  R3  R02 places the plate top-down on L12's plate nest (gantry parked clear): seat sensors confirm seating, plate
      within 1 mm of plate_nest
  R3b dose refused while R02 is still over the nest (L12's deck airspace monitor)
  R4  R02 parks clear; dose_well B05 10 uL: all eight monitors pass; Cell 01's validate_l12_dose commits it
  R5  T01 picks the plate off the L12 nest and puts it back into HN, seated
  R6  T01 stored; L12 READY, parked

Writes test_reports/l12_robot_report.json; exit 1 on any failure.
"""

import json
import math
import os
import sys
import time

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
OVERLAY = os.path.join(ROOT, "scenes/cell01_twin.usda")
REPORT = os.path.join(ROOT, "test_reports/l12_robot_report.json")
L12 = "/World/Cell01/Stations/L12_LiquidHandler"

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True})

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402

for ext in ("isaacsim.robot.surface_gripper", "isaacsim.robot.schema"):
    app_utils.enable_extension(ext)
app.update()

import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from pxr import PhysxSchema, UsdGeom  # noqa: E402

from twin.episode_records import l12_dose_record  # noqa: E402
from twin.hn_monitor import HandoverNest  # noqa: E402
from twin.l12_controller import L12Controller, add_reagent_tube, add_tips, author_l12  # noqa: E402
from twin.r01_rig import add_plate  # noqa: E402
from twin.r02_controller import R02Controller, ToolChanger  # noqa: E402
from twin.r02_rig import HZ, R02Rig, author_r02  # noqa: E402

results = []


def check(name, ok, **vals):
    results.append({"test": name, "pass": bool(ok), **vals})
    print(f"[test_l12_robot] {'PASS' if ok else 'FAIL'}  {name}  {json.dumps(vals, default=str)[:700]}", flush=True)


def Rdown(yaw):
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return np.array([[c, s, 0], [s, -c, 0], [0, 0, -1]])


omni.usd.get_context().open_stage(OVERLAY)
for _ in range(10):
    app.update()
stage = omni.usd.get_context().get_stage()
px = PhysxSchema.PhysxSceneAPI.Apply(stage.GetPrimAtPath("/World/PhysicsScene"))
px.CreateTimeStepsPerSecondAttr(HZ)
px.CreateSolverTypeAttr("TGS")
with open(os.path.join(ROOT, "scenes/layout_p1.json")) as f:
    LAYOUT = json.load(f)
HN = np.array(LAYOUT["extra_frames"]["handover_nest_R01_R02"])
xc = UsdGeom.XformCache()
LOAD = np.array(xc.GetLocalToWorldTransform(stage.GetPrimAtPath(f"{L12}/plate_nest")).ExtractTranslation())

HN_PRIM = LAYOUT["fixtures"]["HN"]["prim"]
add_plate(stage, "/World/TestFixtures/Plate", HN + [0, 0, 0.0005], 0.0, barcode="Plate_L12_R1")
grip = author_l12(stage, L12)
tips = add_tips(stage, L12, [f"{r}{c:02d}" for c in (1, 2) for r in "ABCDEFGH"])
add_reagent_tube(stage, L12, 1, "RGT-0001", "abstract_challenge_reagent", "SIM-LOT-A", 1000.0)
PhysxSchema.PhysxRigidBodyAPI.Apply(stage.GetPrimAtPath("/World/TestFixtures/Plate")).CreateSleepThresholdAttr(0.0)
art_root, wrist, coupler = author_r02(stage)
for _ in range(5):
    app.update()

app_utils.play(commit=True)
l12 = L12Controller(stage, L12, grip, tips=dict(tips), reagent_inventory={
    1: dict(reagent_id="abstract_challenge_reagent", lot="SIM-LOT-A", volume_uL=1000.0)})
hn = HandoverNest(stage, HN_PRIM)
rig = R02Rig(art_root, wrist, coupler, on_step=[l12.update, hn.update], log=lambda m: print(m, flush=True))
r02 = R02Controller(stage, rig)
tcm = ToolChanger(stage, rig, r02)
from isaacsim.core.experimental.prims import RigidPrim  # noqa: E402
plate = RigidPrim("/World/TestFixtures/Plate")
rig.step(int(1.0 * HZ))
t_start = time.time()
R = Rdown(0)


def plate_pose():
    p, q = plate.get_world_poses()
    p, q = p.numpy()[0].astype(float), q.numpy()[0].astype(float)
    tilt = math.degrees(2 * math.asin(min(1.0, math.hypot(q[1], q[2]))))
    yaw = math.degrees(2 * math.atan2(q[3], q[0]))
    return p, tilt, yaw


def pick(at, station, side):
    grasp = at + [0, 0, 0.006]
    pos = r02.position_for_station(station, grasp + [0, 0, 0.15], R, side=side)
    rig.move_to(grasp, R, speed=0.05)
    fa, fb = rig.jaws(True)
    rig.holding = True
    z0 = plate_pose()[0][2]
    rig.move_to(grasp + [0, 0, 0.15], R, speed=0.08)
    return pos, [round(fa, 2), round(fb, 2)], round((plate_pose()[0][2] - z0) * 1e3, 1)


def place(at, station, side):
    target = at + [0, 0, 0.006 + 0.002]
    pos = r02.position_for_station(station, target + [0, 0, 0.15], R, side=side)
    rig.move_to(target, R, speed=0.03)
    rig.holding = False
    rig.jaws(False)
    rig.move_to(target + [0, 0, 0.15], R, speed=0.05)
    rig.step(int(0.5 * HZ))
    return pos


ok_h, _ = r02.home_rail()
ok_t, why = tcm.change_tool("T01")
check("R1 R02 homed, T01 coupled", ok_h and ok_t, reason=why, tool=(rig.tool or {}).get("id"))

seated0 = hn.seated
pos, fingers, lifted = pick(HN, "HN", side=-1.0)
check("R2 T01 picks the plate from the handover nest", seated0 and pos[0] and lifted > 100 and not hn.plate_on_nest,
      seated_before=seated0, finger_travel_mm=fingers, lifted_mm=lifted)

pos = place(LOAD, "L12", side=1.0)
rig.step(int(0.5 * HZ))
p, tilt, yaw = plate_pose()
off = np.round((p - LOAD) * 1e3, 2).tolist()
check("R3 R02 places the plate on L12's nest: seated", pos[0] and l12.seated and math.hypot(off[0], off[1]) < 1.0
      and abs(off[2]) < 0.5 and tilt < 0.5, offset_mm=off, tilt_deg=round(tilt, 3), seat_gaps_mm=[
          None if g is None else round(g * 1e3, 3) for g in l12.seat_gaps], rail_m=round(float(rig.q()[0]), 3))

# R02 is still over the nest: L12's airspace monitor must refuse to start
r_blocked = l12.dose_well("Plate_L12_R1", "B05", 1, "abstract_challenge_reagent", "SIM-LOT-A", 10.0, 1.2, 2.0)
check("R3b dose refused while R02 is in L12's airspace (deck_airspace_occupied)", not r_blocked.accepted
      and "deck_airspace_occupied" in r_blocked.reason, reason=r_blocked.reason)
# R02 must leave the deck airspace: L12's gantry arm and channel (up to 1.29 m) sweep over the nest
c = rig.carry(None, side=1.0)
rig.move_joints(np.r_[rig.q()[0], c[1:]])
rig.move_joints(np.r_[1.8, c[1:]])
r = l12.dose_well("Plate_L12_R1", "B05", 1, "abstract_challenge_reagent", "SIM-LOT-A", 10.0, 1.2, 2.0,
                  intended_effect="abstract_challenge")
rig.run_until(lambda: l12.mode != "BUSY", 240)
d = l12.doses[-1] if l12.doses else None
rec = l12_dose_record(d, "test-l12-robot", None) if d else None
check("R4 dose_well B05 10 uL on the cell bench: all monitors pass, Cell 01 commits", r.accepted and d and d["valid"]
      and rec["routing"] == "culture_sdt_commit", failed=[m["name"] for m in d["monitors"] if not m["passed"]] if d else None,
      aborted=d and d["aborted"], volume_inferred=d and d["volume_inferred_uL"],
      well_position=d and d["evidence"].get("well_position"))

pos_u, fingers, lifted = pick(LOAD, "L12", side=1.0)
place(HN, "HN", side=-1.0)
p, tilt, _ = plate_pose()
off_hn = np.round((p - HN) * 1e3, 2).tolist()
check("R5 T01 takes the plate off L12 and puts it back into HN, seated", pos_u[0] and lifted > 100 and hn.seated
      and math.hypot(off_hn[0], off_hn[1]) < 1.0 and tilt < 0.5, lifted_mm=lifted, hn_offset_mm=off_hn)

ok_s, why = tcm.store_tool()
check("R6 T01 stored; L12 READY and parked", ok_s and l12.mode == "READY" and not l12.fault
      and abs(l12.q["x"] - l12.park[0]) < 0.001, reason=why, l12_q_mm={k: round(v * 1e3, 2) for k, v in l12.q.items()})

report = {"results": results, "passed": sum(r["pass"] for r in results), "total": len(results),
          "wall_s": round(time.time() - t_start, 1), "l12_events": l12.events, "r02_events": r02.events,
          "tcm_events": tcm.events, "doses": l12.doses}
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
with open(REPORT, "w") as f:
    json.dump(report, f, indent=2, default=str)
print(f"[test_l12_robot] {report['passed']}/{report['total']} passed ({report['wall_s']} s)", flush=True)
app_utils.stop()
sys.stdout.flush()
os._exit(0 if report["passed"] == report["total"] else 1)
