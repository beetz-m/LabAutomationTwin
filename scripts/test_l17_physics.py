"""Physics + imaging acceptance test for the articulated L17 Bright-Field Imaging Station.

Scene: ground, L17 on the floor at an arbitrary pose, SBS plates with barcodes. PhysX 240 Hz, L17Controller in the
loop (mechanism physically simulated; images formed from the simulated state by twin/l17_optics.py). Plates are
placed robot-style (set above the presented nest, released). The ground truth of each image (defocus, position
imaged) comes from the optics model and is used here only to judge the controller, never by the controller.

  S   structure: one articulation root, 6 joints, 6 links, the five Cell 01 binding frames
  T1  rest: READY, stage home, gate closed, 10x indexed, calibration valid
  T2  present_for_load: gate opened before the stage left, stage centred in X before leaving the chamber; the stage
      nest (encoders) at plate_load_frame
  T3  misseated plate (placed 8 mm off, beyond the 6.5 mm capture range): load_plate refused (plate_misseated)
  T4  reseat + load_plate P-A: seated, retracted, gate closed, identity read at home
  T5  image_well P-A B03 10x, autofocus: valid; true defocus within half the 10x depth of field; the field imaged
      is in B03, within 0.75 mm of its centre (the plate has 0.5 mm clearance per side in the nest); Cell 01's
      validate_l17_image admits it; raw image + sidecar written
  T6  image_plate_region B04:B06 (seeded autofocus): all valid, fewer autofocus frames than T5
  T7  4x at E07 after a turret change: indexed, valid, true defocus within the 4x depth of field, parfocal
  T8  out of focus (fixed focus +60 um): image acquired and retained, focus_quality fails, evidence blocked
  T9  overexposure (60 ms): histogram saturated, illumination_state fails, evidence blocked
  T10 calibration expired: image_well refused (calibration_expired), state:calibration_valid false
  T11 imaging history: exposures (autofocus frames included) and relative light dose per well
  T12 present_for_unload, plate removed, stow: READY, plate id cleared
  T13 identity mismatch: load_plate('P-X') with P-B on the nest -> plate_identity_mismatch, held; present_for_removal
  T14 state attributes mirror the controller

Writes test_reports/l17_physics_report.json, l17_events.json, l17_images/ (16-bit PNG + JSON sidecars; gitignored)
and l17_contact_sheet.png; exit 1 on any failure.
"""

import json
import math
import os
import shutil
import sys
import time

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
L17_USD = os.path.join(ROOT, "assets/l17/l17.usda")
PLATE_USD = os.path.join(ROOT, "assets/labware/plate_sbs96.usda")
REPORT_DIR = os.path.join(ROOT, "test_reports")
IMG_DIR = os.path.join(REPORT_DIR, "l17_images")
HZ = 240
DT = 1.0 / HZ
POSE = (1.0, -0.6, 0.0, 20.0)
PLATES = {"P-A": (4.0, 4.0), "P-B": (4.3, 4.0)}
L = "/World/L17_BrightFieldImager"

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True})

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from isaacsim.core.experimental.prims import RigidPrim  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics  # noqa: E402

from twin.episode_records import l17_image_record  # noqa: E402
from twin.l17_controller import L17Controller  # noqa: E402

results = []


def check(name, ok, **values):
    fmt = lambda v: round(v, 4) if isinstance(v, float) else v  # noqa: E731
    vals = {k: fmt(v) for k, v in values.items()}
    results.append({"test": name, "pass": bool(ok), **vals})
    print(f"[test_l17] {'PASS' if ok else 'FAIL'}  {name}  {json.dumps(vals, default=str)[:700]}", flush=True)


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
l17 = UsdGeom.Xform.Define(stage, L)
l17.GetPrim().GetReferences().AddReference(L17_USD)
l17.AddTranslateOp().Set(Gf.Vec3d(*POSE[:3]))
l17.AddRotateZOp().Set(POSE[3])
for pid, (x, y) in PLATES.items():
    p = UsdGeom.Xform.Define(stage, f"/World/Plate_{pid.replace('-', '_')}")
    p.GetPrim().GetReferences().AddReference(PLATE_USD)
    p.AddTranslateOp().Set(Gf.Vec3d(x, y, 0.0))
    p.AddOrientOp().Set(Gf.Quatf(1, 0, 0, 0))
    p.GetPrim().CreateAttribute("labware:barcode", Sdf.ValueTypeNames.String, custom=True).Set(pid)
    PhysxSchema.PhysxRigidBodyAPI.Apply(p.GetPrim()).CreateSleepThresholdAttr(0.0)
for _ in range(5):
    app.update()

prims = list(Usd.PrimRange(l17.GetPrim()))
roots = [p for p in prims if p.HasAPI(UsdPhysics.ArticulationRootAPI)]
joints = sorted(p.GetName() for p in prims if p.IsA(UsdPhysics.Joint))
links = sorted(p.GetName() for p in prims if p.HasAPI(UsdPhysics.RigidBodyAPI))
FRAMES = ("plate_load_frame", "plate_stage", "objective_frame", "camera_frame", "illumination_frame")
binding = [n for n in FRAMES if stage.GetPrimAtPath(f"{L}/{n}")]
check("S structure + Cell 01 binding frames", len(roots) == 1 and len(joints) == 6 and len(links) == 6
      and len(binding) == 5, joints=joints, links=links, binding=binding)

xc = UsdGeom.XformCache()
W = lambda n: np.array(xc.GetLocalToWorldTransform(stage.GetPrimAtPath(f"{L}/{n}")).ExtractTranslation())  # noqa: E731
LOAD, HOME = W("plate_load_frame"), W("plate_stage")
cs, sn = math.cos(math.radians(POSE[3])), math.sin(math.radians(POSE[3]))
R = np.array([[cs, -sn, 0], [sn, cs, 0], [0, 0, 1]])

app_utils.play(commit=True)
if os.path.isdir(IMG_DIR):
    shutil.rmtree(IMG_DIR)
ctrl = L17Controller(stage, L, image_dir=IMG_DIR)
rp = {pid: RigidPrim(f"/World/Plate_{pid.replace('-', '_')}") for pid in PLATES}
violations = []


def watch():
    q = ctrl.q
    if q["y"] < -0.100 and q["gate"] < ctrl.gate_travel - 0.002:     # beyond the imaging range: leaving the chamber
        violations.append(("stage leaving the chamber with the gate not open", round(ctrl.t, 3)))
    if q["y"] < -0.100 and abs(q["x"]) > 0.001:
        violations.append(("stage out of the chamber with X not centred", round(ctrl.t, 3)))


def step_cb(i, n):
    ctrl.update(DT)
    watch()


def run(seconds):
    SimulationManager.step(steps=int(round(seconds * HZ)), callback=step_cb)


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


def place(pid, dx=1.0, dy=-1.0, yaw=0.5):
    rp[pid].set_world_poses(positions=[(LOAD + R @ np.array([dx * 1e-3, dy * 1e-3, 0.013])).tolist()],
                            orientations=[qyaw(POSE[3] + yaw)])
    rp[pid].set_velocities(linear_velocities=[[0, 0, 0]], angular_velocities=[[0, 0, 0]])
    run(1.0)


def remove(pid, x, y):
    rp[pid].set_world_poses(positions=[[x, y, 0.0]], orientations=[[1, 0, 0, 0]])
    rp[pid].set_velocities(linear_velocities=[[0, 0, 0]], angular_velocities=[[0, 0, 0]])
    run(0.5)


def plate_err(pid, ref):
    return [round(float(v) * 1e3, 2) for v in R.T @ (rp[pid].get_world_poses()[0].numpy()[0] - ref)]


def wait_idle(timeout=120):
    return run_until(lambda: ctrl.mode != "BUSY", timeout)


def record(i):
    return l17_image_record(ctrl.acquisitions[i], f"test-l17-{i:03d}")


t_start = time.time()
run(1.0)
check("T1 rest: READY, home, gate closed, 10x indexed, calibration valid", ctrl.mode == "READY"
      and ctrl.stage_pose() == "home" and ctrl.q["gate"] < 0.001 and ctrl.camera.objective_on_axis() == "10x"
      and ctrl.calibration_valid, snapshot=ctrl.snapshot())

r = ctrl.present_for_load()
ok = wait_idle(20)
nest = HOME + R @ np.array([ctrl.q["x"], ctrl.q["y"], 0.0])
check("T2 present_for_load: interlocks held, stage nest at plate_load_frame", r.accepted and ok
      and ctrl.mode == "PRESENTED_EMPTY" and not violations and np.linalg.norm(nest - LOAD) < 0.0005,
      nest_err_mm=round(float(np.linalg.norm(nest - LOAD)) * 1e3, 3), violations=violations[:3])

place("P-A", dx=8.0, dy=0.0)
r = ctrl.load_plate("P-A")
check("T3 misseated plate (8 mm off): load_plate refused, plate_misseated", not r.accepted
      and "plate_misseated" in r.reason and ctrl.mode == "PRESENTED_EMPTY", reason=r.reason)

place("P-A")
seat = list(ctrl._gaps_mm())
r = ctrl.load_plate("P-A")
ok = wait_idle(20)
check("T4 reseat + load_plate P-A: seated, home, gate closed, identity read", r.accepted and ok
      and ctrl.mode == "LOADED" and ctrl.plate_id == "P-A" and ctrl.stage_pose() == "home" and ctrl.q["gate"] < 0.001
      and ctrl.seated, seat_gaps_mm=seat, plate_vs_home_mm=plate_err("P-A", HOME),
      identity=[e for e in ctrl.events if e["event"] == "identity_read"][-1])

r = ctrl.image_well("P-A", "B03", exposure_ms=25.0, magnification="10x")
ok = wait_idle(60)
a, tr, rec = ctrl.acquisitions[-1], ctrl.truth[-1], record(len(ctrl.acquisitions) - 1)
af5 = ctrl.autofocus_runs[-1]
png = os.path.join(IMG_DIR, a["raw_image_reference"].split("/")[-1].split("#")[0])
check("T5 image_well B03 10x autofocus: valid, in focus (truth), right well, admitted by Cell 01's validator",
      r.accepted and ok and a["valid"] and abs(tr["defocus_um"]) <= 4.4 and tr["well"] == "B03"
      and tr["offset_from_well_centre_mm"] < 0.75 and rec["routing"] == "evidence_admission"
      and rec["semantic_event"]["eligible"] and os.path.exists(png) and os.path.exists(png[:-4] + ".json"),
      focus_score=a["focus_score"], truth=tr, autofocus={k: af5[k] for k in ("focus_mm", "best_score", "frames")},
      routing=rec["routing"], ref=a["raw_image_reference"])

n0 = len(ctrl.acquisitions)
r = ctrl.image_plate_region("P-A", "B04:B06")
ok = wait_idle(90)
new = ctrl.acquisitions[n0:]
trs = ctrl.truth[n0:]
af6 = ctrl.autofocus_runs[-3:]
check("T6 image_plate_region B04:B06: all valid and in focus, seeded autofocus uses fewer frames", r.accepted and ok
      and len(new) == 3 and all(x["valid"] for x in new) and all(abs(t["defocus_um"]) <= 4.4 for t in trs)
      and [t["well"] for t in trs] == ["B04", "B05", "B06"] and all(f["frames"] < af5["frames"] for f in af6),
      wells=[t["well"] for t in trs], defocus_um=[t["defocus_um"] for t in trs], frames=[f["frames"] for f in af6],
      scores=[x["focus_score"] for x in new])

z10 = ctrl.focus_memory[("P-A", "10x")]
r = ctrl.image_well("P-A", "E07", magnification="4x")
ok = wait_idle(60)
a, tr = ctrl.acquisitions[-1], ctrl.truth[-1]
z4 = ctrl.focus_memory.get(("P-A", "4x"), 99)
check("T7 4x at E07 after a turret change: indexed, valid, in focus, parfocal", r.accepted and ok and a["valid"]
      and ctrl.camera.objective_on_axis() == "4x" and abs(tr["defocus_um"]) <= 27.5 and tr["well"] == "E07"
      and abs(z4 - z10) < 30e-6, defocus_um=tr["defocus_um"], focus_10x_mm=round(z10 * 1e3, 4),
      focus_4x_mm=round(z4 * 1e3, 4), turret_deg=round(math.degrees(ctrl.q["turret"]), 2))

r = ctrl.image_well("P-A", "B03", magnification="10x", focus_policy=("fixed", z10 * 1e3 + 0.060))
ok = wait_idle(60)
i8 = len(ctrl.acquisitions) - 1
a, tr, rec = ctrl.acquisitions[i8], ctrl.truth[i8], record(i8)
foc = next(m for m in a["monitors"] if m["name"] == "focus_quality")
check("T8 out of focus (+60 um, fixed): retained, focus_quality failed, evidence blocked", r.accepted and ok
      and not foc["passed"] and not a["valid"] and rec["routing"] == "L21_qc_or_human_escalation"
      and not rec["semantic_event"]["eligible"] and os.path.exists(os.path.join(IMG_DIR, a["raw_image_reference"]
                                                                                .split("/")[-1].split("#")[0])),
      focus_score=a["focus_score"], truth_defocus_um=tr["defocus_um"], reasons=rec["critic_vector"]["failure_reasons"])

r = ctrl.image_well("P-A", "B03", exposure_ms=60.0, focus_policy="stored")
ok = wait_idle(60)
i9 = len(ctrl.acquisitions) - 1
a, rec = ctrl.acquisitions[i9], record(i9)
ill = next(m for m in a["monitors"] if m["name"] == "illumination_state")
check("T9 overexposure (60 ms): histogram saturated, illumination_state failed, blocked", r.accepted and ok
      and not ill["passed"] and not rec["semantic_event"]["eligible"], histogram=a["histogram"],
      observation=ill["observation"])

ctrl.today = "2026-12-01"
r = ctrl.image_well("P-A", "B03")
run(0.1)
cal_attr = l17.GetPrim().GetAttribute("state:calibration_valid").Get()
check("T10 calibration expired: image_well refused, state:calibration_valid false", not r.accepted
      and "calibration_expired" in r.reason and cal_attr is False, reason=r.reason)
ctrl.today = "2026-10-16"
run(0.1)

h = ctrl.history["P-A"]
b3 = h["B03"]
exp_b3 = [x for x in ctrl.acquisitions if x["well_id"] == "B03"]
dose = sum(x["led_level"] * x["exposure_ms"] for x in exp_b3) + 25.0 * b3["autofocus_frames"]
check("T11 imaging history: every exposure counted, autofocus frames included", b3["exposures"] ==
      len(exp_b3) + b3["autofocus_frames"] and abs(b3["light_dose_rel_ms"] - dose) < 1e-6 and set(h) ==
      {"B03", "B04", "B05", "B06", "E07"}, B03=b3, wells=sorted(h))

r = ctrl.present_for_unload()
ok = wait_idle(30)
err = plate_err("P-A", LOAD)
remove("P-A", *PLATES["P-A"])
r2 = ctrl.stow()
ok2 = wait_idle(20)
check("T12 present_for_unload, removal, stow: READY, plate id cleared", r.accepted and ok and r2.accepted and ok2
      and ctrl.mode == "READY" and ctrl.plate_id == "" and abs(err[0]) < 1.0 and abs(err[1]) < 1.0
      and not violations, presented_err_mm=err, violations=violations[:3])

ctrl.present_for_load()
wait_idle(20)
place("P-B")
r = ctrl.load_plate("P-X")
wait_idle(20)
held = ctrl.mode == "FAULT" and ctrl.fault == "plate_identity_mismatch" and ctrl.plate_id == ""
r2 = ctrl.present_for_removal("identity unresolved: route to H4")
ok = wait_idle(20)
check("T13 identity mismatch: held, present_for_removal presents it", r.accepted and held and r2.accepted and ok
      and ctrl.mode == "PRESENTED_LOADED" and ctrl.plate_on_nest, identity=ctrl.identity_fault,
      events=[e["event"] for e in ctrl.events[-6:]])

attr = lambda n: l17.GetPrim().GetAttribute(n).Get()  # noqa: E731
check("T14 state attributes mirror the controller", attr("state:mode") == ctrl.mode and attr("state:door") == "open"
      and attr("state:stage_pose") == "presented" and attr("state:magnification") == ctrl.camera.objective_on_axis()
      and abs(attr("state:focus_score") - ctrl.acquisitions[-1]["focus_score"]) < 1e-6,
      mode=attr("state:mode"), door=attr("state:door"), stage_pose=attr("state:stage_pose"),
      magnification=attr("state:magnification"), focus_score=attr("state:focus_score"))

# contact sheet of the acquisitions (8-bit previews of the 12-bit raw images)
from PIL import Image, ImageDraw  # noqa: E402

tiles = []
for i, x in enumerate(ctrl.acquisitions):
    im = np.array(Image.open(os.path.join(IMG_DIR, x["raw_image_reference"].split("/")[-1].split("#")[0])))
    t = Image.fromarray(np.clip(im / 16, 0, 255).astype(np.uint8)).convert("RGB").resize((410, 308))
    d = ImageDraw.Draw(t)
    d.rectangle([0, 0, 409, 20], fill=(0, 0, 0))
    d.text((6, 4), f"{x['well_id']} {x['magnification']} {x['exposure_ms']:g} ms  focus {x['focus_score']:.3f}  "
                   f"{'VALID' if x['valid'] else 'BLOCKED'}", fill=(120, 255, 120) if x["valid"] else (255, 110, 110))
    tiles.append(t)
cols = 4
sheet = Image.new("RGB", (cols * 414, ((len(tiles) + cols - 1) // cols) * 312), (255, 255, 255))
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % cols) * 414, (i // cols) * 312))
sheet.save(os.path.join(REPORT_DIR, "l17_contact_sheet.png"))

wall = time.time() - t_start
with open(os.path.join(REPORT_DIR, "l17_physics_report.json"), "w") as f:
    json.dump({"asset": L17_USD, "physics_hz": HZ, "sim_time_s": round(ctrl.t, 1), "wall_time_s": round(wall, 1),
               "results": results, "acquisitions": ctrl.acquisitions, "truth": ctrl.truth,
               "autofocus_runs": [{k: v for k, v in r.items() if k != "curve"} for r in ctrl.autofocus_runs],
               "autofocus_curve_T5": af5["curve"], "imaging_history": ctrl.history}, f, indent=2, default=str)
ctrl.save_events(os.path.join(REPORT_DIR, "l17_events.json"))
failed = [r["test"] for r in results if not r["pass"]]
print(f"[test_l17] {len(results) - len(failed)}/{len(results)} passed; sim {ctrl.t:.0f}s in {wall:.0f}s wall", flush=True)
app_utils.stop()
sys.stdout.flush()
os._exit(1 if failed else 0)
