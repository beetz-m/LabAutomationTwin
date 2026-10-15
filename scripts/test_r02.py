"""R02 (rail + UR5e + automatic tool changer) acceptance in the Cell 01 overlay (layout P1, tool magazine TCM01).

  S  structure: 7 joints (rail + 6), coupler lock, 5 registered tools, every dock reads occupied, binding frames
  R1 rail commands refused before homing (rail_not_homed); R2 homing, rail move residual, soft-limit refusal
  R3 reach plan (URDF IK, elbow-up, joint margin) for the service frames: R01/R02 handover nest, L12 plate frame,
     L17 plate load frame, L21 reference plate frame (top-down with T01)
  T1 change_tool T05: alignment, lock verified, ID read through the coupler, tool follows, dock reads empty
  T2 store_tool T05: tool at rest in its dock, dock occupied
  T3 misaligned approach (2.5 mm belief error): refused before locking (partial_lock), T04 undisturbed
  T4 swapped tools (T03 sits in dock T02): change_tool T02 refused as wrong_tool after the ID read, T03 left docked
  T5 contamination: T03 (liquid_contact) refused for a clean task
  P1 plate transfer with T01: pick at the handover nest, carry along the whole rail, place on L21's deck, store T01

Writes test_reports/r02_report.json; exit 1 on any failure.
Usage: env_isaacsim/bin/python scripts/test_r02.py
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
REPORT = os.path.join(ROOT, "test_reports/r02_report.json")

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True})

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402

for ext in ("isaacsim.robot.surface_gripper", "isaacsim.robot.schema"):
    app_utils.enable_extension(ext)
app.update()

import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from pxr import Gf, PhysxSchema, UsdGeom, UsdPhysics  # noqa: E402

from twin.r01_rig import add_plate  # noqa: E402
from twin.r02_controller import R02Controller, ToolChanger  # noqa: E402
from twin.r02_rig import HZ, R02, TCM, R02Rig, author_r02  # noqa: E402

results = []


def check(name, ok, **vals):
    results.append({"test": name, "pass": bool(ok), **vals})
    print(f"[test_r02] {'PASS' if ok else 'FAIL'}  {name}  {json.dumps(vals, default=str)[:600]}", flush=True)


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
HN = np.array(LAYOUT["extra_frames"]["handover_nest_R01_R02"])           # (-1.05, 0.55, 0.96)
L21_DECK = np.array([2.25, 1.20, 0.97])                                    # L21 reference plate frame, on the deck top

# test fixtures: plate on a stand at the handover nest; tools T02 and T03 swapped in their docks (T4)
stand = UsdGeom.Xform.Define(stage, "/World/TestFixtures/HNStand")
stand.AddTranslateOp().Set(Gf.Vec3d(HN[0], HN[1], (HN[2] + 0.92) / 2))
c = UsdGeom.Cube.Define(stage, "/World/TestFixtures/HNStand/Box")
c.CreateSizeAttr(1.0)
c.AddScaleOp().Set(Gf.Vec3f(0.14, 0.07, float(HN[2] - 0.92)))
UsdPhysics.CollisionAPI.Apply(c.GetPrim())
add_plate(stage, "/World/TestFixtures/Plate", HN + [0, 0, 0.0005], 0.0, barcode="Plate_R02_T1")
PhysxSchema.PhysxRigidBodyAPI.Apply(stage.GetPrimAtPath("/World/TestFixtures/Plate")).CreateSleepThresholdAttr(0.0)
for a, b in (("T02", "T03"), ("T03", "T02")):
    op = UsdGeom.Xformable(stage.GetPrimAtPath(f"{TCM}/Tools/{a}")).GetOrderedXformOps()[0]
    dock = UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(f"{TCM}/dock_{b}")).ExtractTranslation()
    parent = UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(f"{TCM}/Tools")).GetInverse()
    op.Set(Gf.Vec3d(parent.Transform(dock)))
art_root, wrist, coupler = author_r02(stage)
for _ in range(5):
    app.update()

app_utils.play(commit=True)
rig = R02Rig(art_root, wrist, coupler, log=lambda m: print(m, flush=True))
r02 = R02Controller(stage, rig)
tcm = ToolChanger(stage, rig, r02)
from isaacsim.core.experimental.prims import RigidPrim  # noqa: E402
plate = RigidPrim("/World/TestFixtures/Plate")
rig.step(int(1.0 * HZ))
t_start = time.time()

# ---------------------------------------------------------------- structure
frames = [n for n in ("rail_base", "rail_carriage", "robot_base_link", "tool0", "magazine_approach", "station_approach_frames")
          if stage.GetPrimAtPath(f"{R02}/{n}")]
docks = {d: tcm.dock_occupied(d) for d in tcm.tools}
check("S structure: 7 joints, coupler, 5 tools, docks occupied, binding frames", len(rig.ALL) == 7 and
      rig.sg.get_gripper_status(coupler) is not None and len(tcm.tools) == 5 and all(docks.values()) and len(frames) == 6,
      dofs=list(rig.arm.dof_names), docks=docks, frames=frames, rail_m=round(float(rig.q()[0]), 4))

# ---------------------------------------------------------------- rail
ok, why = r02.move_rail(1.0)
check("R1 rail command refused before homing", not ok and r02.fault == "rail_not_homed", reason=why)
r02.fault = ""
ok_h, _ = r02.home_rail()
ok_m, _ = r02.move_rail(1.0)
ok_l, why_l = r02.move_rail(2.7)
check("R2 homing, rail move residual, soft-limit refusal", ok_h and ok_m and not ok_l,
      move=r02.events[-2], refused=why_l)

# ---------------------------------------------------------------- reach plan
plans = {}
for name, p in (("HN handover nest", HN + [0, 0, 0.006]),
                ("L12 experiment_plate_frame", np.array([0.15, 0.10, 1.06 + 0.006])),
                ("L17 plate_load_frame", np.array([1.65, 1.55, 0.94 + 0.006])),
                ("L21 reference plate (deck top)", L21_DECK + [0, 0, 0.006])):
    side = 1.0 if p[1] > rig.base[1] else -1.0
    rail = float(np.clip(p[0] - rig.base[0], 0.02, 2.58))
    q = rig.solve(p, Rdown(0), rig.carry(rail, side=side), rail=rail, extra=0.155)
    plans[name] = None if q is None else {"rail_m": round(rail, 3), "q_deg": np.round(np.degrees(q[1:]), 0).tolist(),
                                          "margin_deg": round(math.degrees(rig.kin.margin(q, range(1, 7))), 1)}
check("R3 reach plan with T01 for HN, L12, L17, L21", all(plans.values()), plans=plans)

# ---------------------------------------------------------------- tool changer
ok, why = tcm.change_tool("T05")
ev = tcm.events[-1]
check("T1 change_tool T05: aligned, locked, ID read, follows, dock empty", ok and not tcm.dock_occupied("T05"),
      reason=why, evidence={k: ev.get(k) for k in ("lock", "id_read", "alignment", "follow_after_lift", "utilities")})
ok, why = tcm.store_tool()
check("T2 store_tool T05: at rest in its dock", ok and tcm.dock_occupied("T05"), reason=why, evidence=tcm.events[-1])

t04_before = tcm.tool_face("T04")[0]
ok, why = tcm.change_tool("T04", belief_offset=(0.0025, 0.0, 0.0))
moved = float(np.linalg.norm(tcm.tool_face("T04")[0] - t04_before))
check("T3 misaligned approach refused before locking (partial_lock)", not ok and tcm.fault == "partial_lock"
      and rig.tool is None and moved < 0.0005, reason=why, t04_moved_mm=round(moved * 1e3, 3))
tcm.fault = ""

ok, why = tcm.change_tool("T02")
check("T4 swapped tool: wrong_tool after the ID read, T03 left in dock T02", not ok and tcm.fault == "wrong_tool"
      and rig.tool is None and tcm.dock_occupied("T02") and str(rig.sg.get_gripper_status(coupler)).endswith("Open"),
      reason=why, id_read=[e for e in tcm.events if e["event"] == "tool_id_read"][-1])
tcm.fault = ""

ok, why = tcm.change_tool("T03", task_contamination="clean")
check("T5 contamination-incompatible tool refused", not ok and tcm.fault == "contamination_incompatible_tool", reason=why)
tcm.fault = ""

# ---------------------------------------------------------------- plate transfer with T01
info = {}
ok_t, why = tcm.change_tool("T01")
info["change_tool"] = why or "ok"
if ok_t:
    R = Rdown(0)
    grasp = HN + [0, 0, 0.006]
    info["to_HN"] = r02.position_for_station("HN", grasp + [0, 0, 0.15], R, side=-1.0)
    rig.move_to(grasp, R, speed=0.05)
    fa, fb = rig.jaws(True)
    rig.holding = True
    z0 = plate.get_world_poses()[0].numpy()[0][2]
    rig.move_to(grasp + [0, 0, 0.15], R, speed=0.08)
    info["grasp"] = {"finger_travel_mm": [round(fa, 2), round(fb, 2)],
                     "lifted_mm": round(float(plate.get_world_poses()[0].numpy()[0][2] - z0) * 1e3, 1)}
    place = L21_DECK + [0, 0, 0.006 + 0.002]
    info["to_L21"] = r02.position_for_station("L21", place + [0, 0, 0.15], R, side=1.0)
    rig.move_to(place, R, speed=0.03)
    rig.holding = False
    rig.jaws(False)
    rig.move_to(place + [0, 0, 0.15], R, speed=0.05)
    rig.step(int(0.5 * HZ))
    p, q = plate.get_world_poses()
    p, q = p.numpy()[0].astype(float), q.numpy()[0].astype(float)
    tilt = math.degrees(2 * math.asin(min(1.0, math.hypot(q[1], q[2]))))
    info["plate_on_L21"] = {"offset_mm": np.round((p - L21_DECK) * 1e3, 2).tolist(), "tilt_deg": round(tilt, 2),
                            "rail_m": round(float(rig.q()[0]), 3)}
    info["store_T01"] = tcm.store_tool()
off = info.get("plate_on_L21", {}).get("offset_mm", [99, 99, 99])
check("P1 T01 plate transfer HN -> rail -> L21 deck, T01 stored", ok_t and info["grasp"]["lifted_mm"] > 100
      and math.hypot(off[0], off[1]) < 5.0 and abs(off[2]) < 1.5 and info["plate_on_L21"]["tilt_deg"] < 1.0
      and info["store_T01"][0], **info)

report = {"results": results, "passed": sum(r["pass"] for r in results), "total": len(results),
          "wall_s": round(time.time() - t_start, 1), "r02_events": r02.events, "tcm_events": tcm.events}
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
with open(REPORT, "w") as f:
    json.dump(report, f, indent=2, default=str)
print(f"[test_r02] {report['passed']}/{report['total']} passed ({report['wall_s']} s)", flush=True)
app_utils.stop()
sys.stdout.flush()
os._exit(0 if report["passed"] == report["total"] else 1)
