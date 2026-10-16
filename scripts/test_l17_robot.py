"""R02 loads and unloads L17 in the Cell 01 overlay: robot-level acceptance for the imager's load interface.

Scene: scenes/cell01_twin.usda (L17 on its plinth at its Cell 01 location, TCM01, the R01/R02 handover nest HN),
R02 added at runtime, an SBS plate seated in HN. PhysX 240 Hz; L17Controller runs on every physics step.

  R1  R02 homed, T01 coupled from the magazine (lock, ID, follow checks of the tool changer)
  R2  T01 picks the plate from HN (seated there first: HN seat sensors)
  R3  L17 presents its stage while R02 travels; R02 places the plate top-down on the presented nest: the four seat
      sensors confirm seating, plate within 1 mm and 0.5 deg of plate_load_frame
  R4  load_plate (identity read at stage home) + image_well B03 10x with autofocus: valid; true defocus within half
      the depth of field (optics ground truth, for the test only)
  R5  present_for_unload; T01 picks the plate off the L17 nest; stow; the plate goes back into HN, seated
  R6  T01 stored; no L17 fault; L17 READY and empty

Writes test_reports/l17_robot_report.json; exit 1 on any failure.
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
REPORT = os.path.join(ROOT, "test_reports/l17_robot_report.json")
L17 = "/World/Cell01/Stations/L17_BrightFieldImager"

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True})

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402

for ext in ("isaacsim.robot.surface_gripper", "isaacsim.robot.schema"):
    app_utils.enable_extension(ext)
app.update()

import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from pxr import PhysxSchema, UsdGeom  # noqa: E402

from twin.hn_monitor import HandoverNest  # noqa: E402
from twin.l17_controller import L17Controller  # noqa: E402
from twin.r01_rig import add_plate  # noqa: E402
from twin.r02_controller import R02Controller, ToolChanger  # noqa: E402
from twin.r02_rig import HZ, R02Rig, author_r02  # noqa: E402

results = []


def check(name, ok, **vals):
    results.append({"test": name, "pass": bool(ok), **vals})
    print(f"[test_l17_robot] {'PASS' if ok else 'FAIL'}  {name}  {json.dumps(vals, default=str)[:700]}", flush=True)


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
LOAD = np.array(xc.GetLocalToWorldTransform(stage.GetPrimAtPath(f"{L17}/plate_load_frame")).ExtractTranslation())

HN_PRIM = LAYOUT["fixtures"]["HN"]["prim"]
add_plate(stage, "/World/TestFixtures/Plate", HN + [0, 0, 0.0005], 0.0, barcode="Plate_L17_R1")
PhysxSchema.PhysxRigidBodyAPI.Apply(stage.GetPrimAtPath("/World/TestFixtures/Plate")).CreateSleepThresholdAttr(0.0)
art_root, wrist, coupler = author_r02(stage)
for _ in range(5):
    app.update()

app_utils.play(commit=True)
l17 = L17Controller(stage, L17, image_dir=os.path.join(ROOT, "test_reports/l17_images_robot"))
hn = HandoverNest(stage, HN_PRIM)
rig = R02Rig(art_root, wrist, coupler, on_step=[l17.update, hn.update], log=lambda m: print(m, flush=True))
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

r = l17.present_for_load()
pos = place(LOAD, "L17", side=1.0)
rig.run_until(lambda: l17.mode != "BUSY", 20)
p, tilt, yaw = plate_pose()
off = np.round((p - LOAD) * 1e3, 2).tolist()
check("R3 R02 places the plate on L17's presented nest: seated", r.accepted and pos[0] and l17.mode == "PRESENTED_EMPTY"
      and l17.seated and math.hypot(off[0], off[1]) < 1.0 and abs(off[2]) < 0.5 and tilt < 0.5,
      offset_mm=off, tilt_deg=round(tilt, 3), yaw_deg=round(yaw, 3), seat_gaps_mm=l17._gaps_mm(),
      rail_m=round(float(rig.q()[0]), 3), position=[e for e in r02.events if e["event"].startswith("position_for_station")][-1])

r1 = l17.load_plate("Plate_L17_R1")
rig.run_until(lambda: l17.mode != "BUSY", 30)
r2 = l17.image_well("Plate_L17_R1", "B03")
rig.run_until(lambda: l17.mode != "BUSY", 90)
a = l17.acquisitions[-1] if l17.acquisitions else {}
tr = l17.truth[-1] if l17.truth else {}
check("R4 load_plate + image_well B03 10x: valid, in focus (truth)", r1.accepted and r2.accepted
      and l17.mode == "LOADED" and a.get("valid") and abs(tr.get("defocus_um", 99)) <= 4.4 and tr.get("well") == "B03",
      focus_score=a.get("focus_score"), truth=tr, monitors={m["name"]: m["passed"] for m in a.get("monitors", [])})

r = l17.present_for_unload()
rig.run_until(lambda: l17.mode != "BUSY", 30)
pres = np.round((plate_pose()[0] - LOAD) * 1e3, 2).tolist()
pos_u, fingers, lifted = pick(LOAD, "L17", side=1.0)
r_st = l17.stow()
place(HN, "HN", side=-1.0)
rig.run_until(lambda: l17.mode != "BUSY", 20)
p, tilt, _ = plate_pose()
off_hn = np.round((p - HN) * 1e3, 2).tolist()
check("R5 unload: presented, T01 picks it off the nest, L17 stows, plate seated back in HN", r.accepted and pos_u[0]
      and lifted > 100 and r_st.accepted and hn.seated and math.hypot(off_hn[0], off_hn[1]) < 1.0 and tilt < 0.5,
      presented_offset_mm=pres, lifted_mm=lifted, hn_offset_mm=off_hn, hn_seat_gaps_mm=hn.gaps_mm(),
      tilt_deg=round(tilt, 3))

ok_s, why = tcm.store_tool()
check("R6 T01 stored; L17 READY, empty, no fault", ok_s and l17.mode == "READY" and not l17.fault
      and not l17.plate_on_nest and l17.plate_id == "", reason=why, l17=l17.snapshot())

report = {"results": results, "passed": sum(r["pass"] for r in results), "total": len(results),
          "wall_s": round(time.time() - t_start, 1), "l17_events": l17.events, "r02_events": r02.events,
          "tcm_events": tcm.events, "acquisitions": l17.acquisitions, "truth": l17.truth}
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
with open(REPORT, "w") as f:
    json.dump(report, f, indent=2, default=str)
print(f"[test_l17_robot] {report['passed']}/{report['total']} passed ({report['wall_s']} s)", flush=True)
app_utils.stop()
sys.stdout.flush()
os._exit(0 if report["passed"] == report["total"] else 1)
