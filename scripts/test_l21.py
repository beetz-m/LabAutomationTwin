"""L21 QC / calibration acceptance test in the Cell 01 overlay: tool-frame check, imager validation, fault handling.

Scene: scenes/cell01_twin.usda with L17, L21 and TCM01; R02 added at runtime; the reference plate REF-L21-001 in
L21's reference nest. PhysX 240 Hz; L17Controller and L21Controller run on every physics step. Faults are injected
as PHYSICAL changes the controllers cannot see (a wrong tool TCP belief, a magnification drift, a dim LED).

  Q1  structure: L21 binding frames, artifacts valid, reference plate seated in its nest
  Q2  validate_tool_frame T01 right after coupling (light barrier, 3 sweeps): the real TCP is located; if it is out of
      tolerance (the coupler lock holds the faces at their residual gap) L21's correction is applied; as left: pass
  Q3  T01 TCP belief off by 2 mm along the tool axis: out_of_tolerance, error found; correction applied; re-check pass
  Q4  R02 carries the reference plate to L17; L17 reads REF-L21-001 at load (validate_barcode)
  Q5  validate_imager: pass; a calibration record is issued by L21 and applied to L17 (measured pixel sizes)
  Q6  a measurement image bound to that calibration; then a 4 % magnification drift at 10x: as found
      out_of_tolerance -> calibration invalidated, the dependent image flagged; recalibrated record issued; as-left
      validation passes
  Q7  LED at 60 % output: out_of_tolerance (brightness), not recalibratable: L17 blocked (image_well refused);
      after repair the validation passes
  Q8  expired reference artifact: validate_imager refused
  Q9  QC records: Cell 01 `qc` designator records validate against the schemas; passing ones commit to the evidence
      layer, failing ones route to invalidate_dependent_measurements
  Q10 the reference plate goes back into its L21 nest (seated); T01 stored

Writes test_reports/l21_report.json (+ l21_qc_records.json); exit 1 on any failure.
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
REPORT = os.path.join(ROOT, "test_reports/l21_report.json")
L17 = "/World/Cell01/Stations/L17_BrightFieldImager"
L21 = "/World/Cell01/Stations/L21_QC_Calibration"
REF = "REF-L21-001"

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True})

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402

for ext in ("isaacsim.robot.surface_gripper", "isaacsim.robot.schema"):
    app_utils.enable_extension(ext)
app.update()

import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from pxr import PhysxSchema, UsdGeom  # noqa: E402

from twin.episode_records import Schemas, build_record, validate  # noqa: E402
from twin.l17_controller import L17Controller  # noqa: E402
from twin.l21_controller import L21Controller, qc_designator  # noqa: E402
from twin.r01_rig import add_plate  # noqa: E402
from twin.r02_controller import R02Controller, ToolChanger  # noqa: E402
from twin.r02_rig import HZ, R02Rig, author_r02  # noqa: E402

results = []


def check(name, ok, **vals):
    results.append({"test": name, "pass": bool(ok), **vals})
    print(f"[test_l21] {'PASS' if ok else 'FAIL'}  {name}  {json.dumps(vals, default=str)[:900]}", flush=True)


def Rdown(yaw=0.0):
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return np.array([[c, s, 0], [s, -c, 0], [0, 0, -1]])


omni.usd.get_context().open_stage(OVERLAY)
for _ in range(10):
    app.update()
stage = omni.usd.get_context().get_stage()
px = PhysxSchema.PhysxSceneAPI.Apply(stage.GetPrimAtPath("/World/PhysicsScene"))
px.CreateTimeStepsPerSecondAttr(HZ)
px.CreateSolverTypeAttr("TGS")
xc = UsdGeom.XformCache()
W = lambda p: np.array(xc.GetLocalToWorldTransform(stage.GetPrimAtPath(p)).ExtractTranslation())  # noqa: E731
REF_NEST, LOAD = W(f"{L21}/reference_plate_frame"), W(f"{L17}/plate_load_frame")
add_plate(stage, "/World/TestFixtures/RefPlate", REF_NEST + [0, 0, 0.0005], 0.0, barcode=REF)
PhysxSchema.PhysxRigidBodyAPI.Apply(stage.GetPrimAtPath("/World/TestFixtures/RefPlate")).CreateSleepThresholdAttr(0.0)
art_root, wrist, coupler = author_r02(stage)
for _ in range(5):
    app.update()

app_utils.play(commit=True)
l17 = L17Controller(stage, L17, image_dir=os.path.join(ROOT, "test_reports/l17_images_l21"))
l21 = L21Controller(stage, L21)
rig = R02Rig(art_root, wrist, coupler, on_step=[l17.update, l21.update], log=lambda m: print(m, flush=True))
r02 = R02Controller(stage, rig)
tcm = ToolChanger(stage, rig, r02)
from isaacsim.core.experimental.prims import RigidPrim  # noqa: E402
plate = RigidPrim("/World/TestFixtures/RefPlate")
rig.step(int(1.0 * HZ))
t_start = time.time()
R = Rdown()
sch = Schemas()
qc_recs = []


def plate_pose():
    p, q = plate.get_world_poses()
    p, q = p.numpy()[0].astype(float), q.numpy()[0].astype(float)
    return p, math.degrees(2 * math.asin(min(1.0, math.hypot(q[1], q[2]))))


def idle(ctrl, timeout):
    return rig.run_until(lambda: ctrl.mode != "BUSY", timeout)


def pick(at, station, side):
    grasp = at + [0, 0, 0.006]
    pos = r02.position_for_station(station, grasp + [0, 0, 0.15], R, side=side)
    rig.move_to(grasp, R, speed=0.05)
    rig.jaws(True)
    rig.holding = True
    z0 = plate_pose()[0][2]
    rig.move_to(grasp + [0, 0, 0.15], R, speed=0.08)
    return pos[0] and plate_pose()[0][2] - z0 > 0.1


def place(at, station, side):
    target = at + [0, 0, 0.008]
    pos = r02.position_for_station(station, target + [0, 0, 0.15], R, side=side)
    rig.move_to(target, R, speed=0.03)
    rig.holding = False
    rig.jaws(False)
    rig.move_to(target + [0, 0, 0.15], R, speed=0.05)
    rig.step(int(0.5 * HZ))
    return pos[0]


def tool_check(tool_id="T01"):
    """Three light-barrier sweeps with T01 (jaws open): z with finger A over beam A, y across beam A, x across
    beam B. L21 samples the beams and the robot's believed TCP on every physics step."""
    D = l21.frames["tool_calibration_frame"]
    tip = 0.008                                  # T01 fingertips 8 mm beyond the TCP along the tool axis
    half = 0.05024                               # finger centre offset from the TCP (open)
    l21.begin_tool_check(tool_id, lambda: rig.tcp()[0], tip)

    def at(x, y, z, phase=None, speed=0.02):
        l21.mark_phase(phase)
        return rig.move_to(np.array([x, y, z]), R, speed=speed, tol_mm=0.2, timeout=8.0)[0]

    hi = D[2] + tip + 0.030
    ok = r02.position_for_station("L21_datum", np.array([D[0] + 0.040, D[1] + half, hi + 0.10]), R, side=1.0)[0]
    ok &= at(D[0] + 0.040, D[1] + half, D[2] + tip + 0.010)
    ok &= at(D[0] + 0.040, D[1] + half, D[2] + tip - 0.006, "z", 0.003)
    l21.mark_phase(None)
    ok &= at(D[0] + 0.040, D[1] + half, hi)
    ok &= at(D[0] + 0.040, D[1] - 0.075, hi)
    ok &= at(D[0] + 0.040, D[1] - 0.075, D[2] + tip - 0.005)
    ok &= at(D[0] + 0.040, D[1] + 0.075, D[2] + tip - 0.005, "y", 0.004)
    l21.mark_phase(None)
    ok &= at(D[0] + 0.040, D[1] + 0.075, hi)
    ok &= at(D[0] - 0.050, D[1] + 0.020, hi)
    ok &= at(D[0] - 0.050, D[1] + 0.020, D[2] + tip - 0.005)
    ok &= at(D[0] + 0.050, D[1] + 0.020, D[2] + tip - 0.005, "x", 0.004)
    l21.mark_phase(None)
    ok &= at(D[0] + 0.050, D[1] + 0.020, hi + 0.10)
    rec = l21.finish_tool_check()
    rec["moves_converged"] = bool(ok)
    qc_recs.append(qc_designator(rec, "test-l21", tool_frame_ok=rec["verdict"] == "pass"))
    return rec


def validate_imager():
    n = len(l21.qc_records)
    r = l21.validate_imager(l17, REF)
    if r.accepted:
        idle(l21, 600)
    rec = l21.qc_records[-1] if len(l21.qc_records) > n else None
    if rec:
        qc_recs.append(qc_designator(rec, "test-l21", tool_frame_ok=l21.tool_frame_valid("T01")))
    return r, rec


def summary(rec):
    return None if rec is None else {"verdict": rec["verdict"], "issued": rec["calibration_issued"],
                                     "invalidated": rec["invalidated_acquisitions"],
                                     **{m: {k: p.get(k) for k in ("pixel_um_measured", "pixel_scale_error",
                                                                   "autofocus_repeatability_um")} | {
                                         "failed": [k for k, v in p["checks"].items() if not v],
                                         "brightness": [x.get("brightness_fs") for x in p["measurements"]]}
                                        for m, p in rec["per_objective"].items()}}


# ---------------------------------------------------------------- Q1 structure
frames = [n for n in ("reference_plate_frame", "camera_calibration_frame", "tool_calibration_frame", "qc_nest_frame")
          if stage.GetPrimAtPath(f"{L21}/{n}")]
ns = l21.nest_state("reference_plate_frame")
check("Q1 L21 frames, artifacts valid, reference plate seated in its nest", len(frames) == 4
      and l21.artifact_valid(REF) and l21.artifact_valid("DATUM-L21-LB1") and ns["seated"],
      frames=frames, ref_nest=ns, beams={b: l21.beam_blocked(b) for b in "AB"})

# ---------------------------------------------------------------- Q2 / Q3 tool frame
r02.home_rail()
ok_t, why = tcm.change_tool("T01")
rec = tool_check()                              # as found, right after coupling
as_found = rec["result"]
if rec["verdict"] != "pass" and rec["result"].get("ok"):
    rig.tool["tcp"] += rec["result"]["error_mm"][2] * 1e-3   # apply L21's correction to the tool record
    rec = tool_check()                          # as left
check("Q2 validate_tool_frame T01 after coupling: located; corrected if needed; as left pass", ok_t
      and as_found.get("ok") and rec["verdict"] == "pass" and rec["moves_converged"]
      and max(abs(e) for e in rec["result"]["error_mm"]) < 0.3, as_found=as_found, as_left=rec["result"],
      tcp_mm=round(rig.tool["tcp"] * 1e3, 3), samples=rec["samples"])

tcp0 = rig.tool["tcp"]
rig.tool["tcp"] = tcp0 + 0.002                  # injected: the robot believes the TCP 2 mm further along the tool
rec = tool_check()
err = rec["result"].get("error_mm", [0, 0, 0])
found = rec["verdict"] == "out_of_tolerance" and abs(err[2] + 2.0) < 0.3 and abs(err[0]) < 0.3 and abs(err[1]) < 0.3
rig.tool["tcp"] += err[2] * 1e-3               # apply L21's correction to the tool record (believed - real along z)
rec2 = tool_check()
check("Q3 TCP belief off by 2 mm: out_of_tolerance, error located, corrected, re-check pass", found
      and rec2["verdict"] == "pass" and abs(rig.tool["tcp"] - tcp0) < 0.0003, as_found=rec["result"],
      correction_mm=rec["correction_mm"], as_left=rec2["result"], tcp_mm=round(rig.tool["tcp"] * 1e3, 3))

# ---------------------------------------------------------------- Q4 reference plate to L17
l17.present_for_load()
ok_p = pick(REF_NEST, "L21_ref", side=1.0)
ok_pl = place(LOAD, "L17", side=1.0)
idle(l17, 20)
r = l17.load_plate(REF)
idle(l17, 30)
read = [e for e in l17.events if e["event"] == "identity_read"][-1]
check("Q4 reference plate L21 -> L17; L17 reads REF-L21-001 at load", ok_p and ok_pl and r.accepted
      and l17.mode == "LOADED" and read["observed"] == REF, identity=read, seated=l17.seated)

# ---------------------------------------------------------------- Q5 validation pass -> calibration issued
cal0 = l17.calibration["calibration_id"]
r, rec = validate_imager()
s5 = summary(rec)
check("Q5 validate_imager: pass, L21 issues and L17 applies a calibration", r.accepted and rec and rec["verdict"] == "pass"
      and l17.calibration["calibration_id"] == rec["calibration_issued"] != cal0 and l17.calibration_valid
      and abs(l17.calibration["objectives"]["10x"]["pixel_um"] / 0.45 - 1) < 0.002, summary=s5,
      calibration=l17.calibration["calibration_id"])

# ---------------------------------------------------------------- Q6 magnification drift
r = l17.image_well(REF, "B03")                 # a measurement bound to the current calibration
idle(l17, 60)
dep = len(l17.acquisitions) - 1
l17.camera.pixel_scale["10x"] = 1.04           # injected: tube-lens / magnification drift at 10x
r, rec_f = validate_imager()
s_f = summary(rec_f)
blocked = not l17.image_well(REF, "B03", purpose="measurement").accepted if not l17.calibration_valid else False
r, rec_l = validate_imager()                   # as-left confirmation of the recalibrated record
s_l = summary(rec_l)
check("Q6 magnification drift 4 %: as found out_of_tolerance, dependent image flagged, recalibrated, as-left pass",
      rec_f and rec_f["verdict"] == "out_of_tolerance_recalibrated" and dep in rec_f["invalidated_acquisitions"]
      and l17.acquisitions[dep].get("invalidated_by") == rec_f["qc_id"] and rec_l and rec_l["verdict"] == "pass"
      and abs(l17.calibration["objectives"]["10x"]["pixel_um"] / 0.468 - 1) < 0.003 and l17.calibration_valid,
      as_found=s_f, as_left=s_l, dependent=dep, calibration=l17.calibration["calibration_id"], blocked_between=blocked)

# ---------------------------------------------------------------- Q7 dim LED
l17.camera.led_efficiency = 0.6                # injected: LED output at 60 %
r, rec_d = validate_imager()
r_img = l17.image_well(REF, "B03")
l17.camera.led_efficiency = 1.0                # repair: LED replaced
r, rec_r = validate_imager()
check("Q7 LED at 60 %: out_of_tolerance (brightness), L17 blocked; after repair pass", rec_d
      and rec_d["verdict"] == "out_of_tolerance" and not r_img.accepted and "calibration_invalidated" in r_img.reason
      and rec_r and rec_r["verdict"] == "pass" and l17.calibration_valid, as_found=summary(rec_d),
      refused=r_img.reason, after_repair=summary(rec_r))

# ---------------------------------------------------------------- Q8 expired reference
l21.today = "2027-05-01"
r, _ = validate_imager()
l21.today = "2026-10-16"
check("Q8 expired reference artifact: validate_imager refused", not r.accepted and "expired" in r.reason, reason=r.reason)

# ---------------------------------------------------------------- Q9 QC records
recs = []
for d in qc_recs:
    rr = build_record(sch, "test-l21", d)
    recs.append({"id": d["id"], "verdict": d["qc_record"]["verdict"], "routing": rr["routing"],
                 "eligible": rr["semantic_event"]["eligible"], "errors": validate(sch, rr), "record": rr})
ok9 = all(not x["errors"] for x in recs) and all(
    (x["routing"] == "evidence_layer_commit") == (x["verdict"] == "pass") for x in recs)
check("Q9 QC records: schema-valid; pass -> evidence layer, out of tolerance -> invalidate_dependent_measurements",
      ok9 and len(recs) >= 8, records=[{k: x[k] for k in ("id", "verdict", "routing", "errors")} for x in recs])

# ---------------------------------------------------------------- Q10 reference plate home
l17.present_for_unload()
idle(l17, 30)
ok_p = pick(LOAD, "L17", side=1.0)
l17.stow()
ok_pl = place(REF_NEST, "L21_ref", side=1.0)
idle(l17, 20)
ns = l21.nest_state("reference_plate_frame")
ok_s, _ = tcm.store_tool()
check("Q10 reference plate back in its L21 nest (seated); T01 stored; L17 READY", ok_p and ok_pl and ns["seated"]
      and ok_s and l17.mode == "READY", ref_nest=ns)

report = {"results": results, "passed": sum(r["pass"] for r in results), "total": len(results),
          "wall_s": round(time.time() - t_start, 1), "qc_records": l21.qc_records, "calibrations": l21.calibrations,
          "tool_frames": l21.tool_frames, "l21_events": l21.events, "l17_events": l17.events}
with open(REPORT, "w") as f:
    json.dump(report, f, indent=2, default=str)
with open(os.path.join(ROOT, "test_reports/l21_qc_records.json"), "w") as f:
    json.dump([x["record"] for x in recs], f, indent=2, default=str)
print(f"[test_l21] {report['passed']}/{report['total']} passed ({report['wall_s']} s)", flush=True)
app_utils.stop()
sys.stdout.flush()
os._exit(0 if report["passed"] == report["total"] else 1)
