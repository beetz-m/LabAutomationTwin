"""FR3 pick-and-place trials into the H4 shuttle nest (robot hand-off acceptance).

Scene: bench, H4 (controller in the loop), FR3 arm (URDF import) + proxy plate gripper (fixed to the
flange), a source stand with an SBS plate. Per trial the robot:
  1. picks the plate from the source stand (plate pose noise +-1.5 mm / +-1 deg),
  2. places it top-down into H4's presented transfer_nest, releasing 1 mm above the guide tops,
  3. H4 checks seating with its seat sensors (and trial 0 runs a full quarantine/lock/release cycle),
  4. picks the plate back out of the nest (retrieval), lifts it, and the plate is reset to the source.

The robot targets its BELIEF of the nest pose = true pose + an injected error:
  registered    (AprilTag/datum registration residual): N(0, 0.5 mm) xy, N(0, 0.3 deg) yaw
  unregistered  (station calibration error only):        U(+-3 mm) xy,  U(+-1 deg) yaw

Contact-only grasp (30 N per jaw, rubber pads); no attachment joints, no pose writes while handled.
FR3 link gravity is disabled to emulate the FR3's internal gravity compensation; the plate has gravity.
Control: damped-least-squares differential IK on the PhysX Jacobian, straight-line Cartesian moves; the robot rig
and its primitives live in twin/r01_rig.py (shared with scripts/run_cell01_episode.py).

Writes test_reports/h4_robot_report_<scene>_<place-mode>.json; exit 1 unless every registered trial seats and is
retrieved and the quarantine cycle passes.
Usage: env_isaacsim/bin/python scripts/test_h4_robot.py [--scene bench|cell01] [--place-mode compliant|drop]
       [--trials N] [--seed S]
"""

import argparse
import json
import math
import os
import sys
import time

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
ap = argparse.ArgumentParser()
ap.add_argument("--trials", type=int, default=16)
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--stop-after", type=int, default=None, help="debug: stop after this many trials (same RNG draws)")
ap.add_argument("--scene", choices=("bench", "cell01"), default="bench",
                help="bench: standalone rig; cell01: scenes/cell01_twin.usda overlay (layout P1), FR3 on R01's base_link")
ap.add_argument("--place-mode", choices=("compliant", "drop"), default="compliant",
                help="compliant: lower the plate into the guides under low arm stiffness and release 2 mm "
                     "above the seat; drop: release 1 mm above the guide tops (~13 mm free fall)")
args = ap.parse_args()

H4_USD = os.path.join(ROOT, "assets/h4/h4.usda")
CELL01_OVERLAY = os.path.join(ROOT, "scenes/cell01_twin.usda")
REPORT_DIR = os.path.join(ROOT, "test_reports")
BENCH_Z = 0.90
FR3_BASE = (0.30, -0.62, BENCH_Z, 90.0)

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True})

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from pxr import Gf, PhysxSchema, UsdGeom, UsdPhysics  # noqa: E402

from twin.h4_controller import H4Controller  # noqa: E402
from twin.r01_rig import HZ, R01Rig, add_plate, author_rig, frame_pose, qyaw, tool_down, yaw_of  # noqa: E402

if args.scene == "bench":
    SOURCE = np.array([0.55, -0.27, BENCH_Z + 0.04])
    H4_PATH, FR3_PATH, GRIP_PATH = "/World/H4_Quarantine", "/World/FR3", "/World/Gripper"
else:  # layout P1 (scenes/layout_p1.json): the source plate sits on a test stand at the R01/R02 handover nest
    with open(os.path.join(ROOT, "scenes/layout_p1.json")) as f:
        LAYOUT = json.load(f)
    SOURCE = np.array(LAYOUT["extra_frames"]["handover_nest_R01_R02"])
    WORKTOP_Z = 0.92  # central bench top (Cell 01)
    H4_PATH = "/World/Cell01/Stations/H4_Quarantine"
    FR3_PATH, GRIP_PATH = "/World/Cell01/Robots/R01_FR3/FR3", "/World/Cell01/Robots/R01_FR3/PlateGripper"
    H4_YAW_CELL01 = LAYOUT["stations"]["H4"]["yaw_deg"]  # as placed by the overlay (checked against the stage below)
rng = np.random.default_rng(args.seed)


# ------------------------------------------------------------------------------ scene
if args.scene == "bench":
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
else:
    omni.usd.get_context().open_stage(CELL01_OVERLAY)
    for _ in range(10):
        app.update()
    stage = omni.usd.get_context().get_stage()
    px = PhysxSchema.PhysxSceneAPI.Apply(stage.GetPrimAtPath("/World/PhysicsScene"))
px.CreateTimeStepsPerSecondAttr(HZ)
px.CreateSolverTypeAttr("TGS")


def static_box(path, center, size, yaw_deg=0.0):
    xf = UsdGeom.Xform.Define(stage, path)
    xf.AddTranslateOp().Set(Gf.Vec3d(*map(float, center)))
    xf.AddRotateZOp().Set(float(yaw_deg))
    c = UsdGeom.Cube.Define(stage, path + "/Box")
    c.CreateSizeAttr(1.0)
    c.AddScaleOp().Set(Gf.Vec3f(*size))
    UsdPhysics.CollisionAPI.Apply(c.GetPrim())


# source pedestal narrower than the plate's 85.5 mm width so the long-side fingers pass beside it
if args.scene == "bench":
    static_box("/World/Ground", (0, 0, -0.05), (20, 20, 0.1))
    static_box("/World/Bench", (0.15, -0.25, BENCH_Z / 2), (1.4, 1.1, BENCH_Z))
    static_box("/World/SourceStand", SOURCE - [0, 0, 0.02], (0.14, 0.07, 0.04))
    h4 = UsdGeom.Xform.Define(stage, H4_PATH)
    h4.GetPrim().GetReferences().AddReference(H4_USD)
    h4.AddTranslateOp().Set(Gf.Vec3d(0, 0, BENCH_Z))
    fr3_local = Gf.Matrix4d(1.0).SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), FR3_BASE[3])).SetTranslateOnly(
        Gf.Vec3d(*FR3_BASE[:3]))
    MOUNT = "/World/Bench/Box"
else:  # Cell 01: H4 placed by the overlay; FR3 mounted on R01's base_link frame
    static_box("/World/TestFixtures/SourceStand", [SOURCE[0], SOURCE[1], (SOURCE[2] + WORKTOP_Z) / 2],
               (0.14, 0.07, SOURCE[2] - WORKTOP_Z), yaw_deg=H4_YAW_CELL01)  # on the bench, oriented like the plate
    fr3_local = UsdGeom.Xformable(stage.GetPrimAtPath("/World/Cell01/Robots/R01_FR3/base_link")).GetLocalTransformation()
    MOUNT = "/World/Cell01/Robots/R01_FR3/Pedestal"

add_plate(stage, "/World/Plate", SOURCE)
app.update()
CONTACTS = bool(os.environ.get("H4_CONTACTS"))  # diagnostic: log contacts of robot, gripper and plate while placing
ART_ROOT = author_rig(stage, FR3_PATH, GRIP_PATH, MOUNT, fr3_local, contact_prims=["/World/Plate"] if CONTACTS else ())
for _ in range(5):
    app.update()

NEST_TRUE, NEST_YAW = frame_pose(stage, f"{H4_PATH}/transfer_nest")  # nest +X (plate long axis) in world
if args.scene == "cell01":
    assert abs((NEST_YAW - H4_YAW_CELL01 + 180) % 360 - 180) < 0.5, (NEST_YAW, H4_YAW_CELL01)

# ------------------------------------------------------------------------------ runtime handles
app_utils.play(commit=True)
ctrl = H4Controller(stage, H4_PATH)
rig = R01Rig(ART_ROOT, GRIP_PATH, plates=["/World/Plate"], on_step=[ctrl.update], place_mode=args.place_mode,
             contacts=CONTACTS, log=lambda m: print(m.replace("[rig]", "[robot]")))
step, tcp, move_to, gripper, plate_pose = rig.step, rig.tcp, rig.move_to, rig.gripper, rig.plate_pose
HELD = rig.held


def reset_plate():
    d = np.array([rng.uniform(-1.5, 1.5), rng.uniform(-1.5, 1.5), 0]) * 1e-3
    yaw = NEST_YAW + rng.uniform(-1, 1)  # source presented in the nest's orientation (no big wrist roll)
    rp = rig.plates["/World/Plate"]
    rp.set_world_poses(positions=[(SOURCE + d + [0, 0, 0.0005]).tolist()], orientations=[qyaw(yaw).tolist()])
    rp.set_velocities(linear_velocities=[[0, 0, 0]], angular_velocities=[[0, 0, 0]])
    step(int(0.4 * HZ))


def pick(center, yaw, label):
    return rig.pick(center, yaw, label)


def place(nest_bottom_center, yaw):
    ok, info = rig.place(nest_bottom_center, yaw, seat_z=NEST_TRUE[2], contacts_phase="insert")
    if CONTACTS:  # pair -> [first t, steps in contact, max impulse N*s]
        info["contacts"] = rig.contacts("insert")
        rig.contact_log.pop("insert", None)
    return ok, info


# ------------------------------------------------------------------------------ trials
step(int(0.5 * HZ))
p0, q0, _ = tcp()
print(f"[robot] READY tcp={np.round(p0, 4)} quat={np.round(q0, 3)} yaw={yaw_of(q0):.1f}")
ctrl.present_nest()
step(int(4.0 * HZ))
assert ctrl.mode == "PRESENTED", ctrl.snapshot()
reset_plate()
trials = []
t_start = time.time()
for i in range(args.trials):
    if args.stop_after is not None and i >= args.stop_after:
        break
    t0_trial = ctrl.t
    mode = "registered" if i < args.trials // 2 else "unregistered"
    if mode == "registered":
        err = np.array([rng.normal(0, 0.5), rng.normal(0, 0.5), 0.0]) * 1e-3
        yaw_err = rng.normal(0, 0.3)
    else:
        err = np.array([rng.uniform(-3, 3), rng.uniform(-3, 3), 0.0]) * 1e-3
        yaw_err = rng.uniform(-1, 1)
    belief = NEST_TRUE + err
    if os.environ.get("H4_FREE_AIR"):  # diagnostic: same placement 50 mm above the nest (no guide contact)
        belief = belief + [0, 0, 0.05]
    rec = {"_t0": t0_trial, "trial": i, "mode": mode, "belief_err_mm": [round(v, 2) for v in err[:2] * 1e3],
           "belief_yaw_err_deg": round(yaw_err, 2)}

    sp, sq = plate_pose()
    src_bottom = sp.copy()  # plate origin is its bottom centre
    rec["pick_source"] = pick(src_bottom, yaw_of(sq), "pick_source")
    if not rec["pick_source"]["lifted"]:
        rec["result"] = "FAIL pick_source"
        trials.append(rec)
        reset_plate()
        continue
    reached, place_info = place(belief, NEST_YAW + yaw_err)
    pp, pq = plate_pose()
    e_nest = pp - NEST_TRUE
    rec.update({"place_reached": reached, **place_info, "seated": ctrl.seated, "in_transit_slip": HELD["dropped"],
                "seat_gaps_mm": ctrl.snapshot()["seat_gaps_mm"],
                "plate_err_mm": [round(v, 2) for v in e_nest * 1e3],
                "plate_yaw_err_deg": round(yaw_of(pq) - NEST_YAW, 2)})

    if i == 0 and ctrl.seated:  # full quarantine / lock / authorised release cycle once
        r = ctrl.quarantine_sample("P-TRIAL-0", "robot_handoff_test")
        step(int(6.0 * HZ))
        locked = ctrl.mode == "QUARANTINED" and ctrl.locked
        ctrl._target("key", math.radians(90))
        step(int(1.0 * HZ))
        r2 = ctrl.release("QA-ROBOT-TRIAL")
        step(int(6.0 * HZ))
        ctrl._target("key", 0.0)
        step(int(0.5 * HZ))
        rec["quarantine_cycle"] = {"accepted": r.accepted, "locked": locked, "released": r2.accepted,
                                   "presented_again": ctrl.mode == "PRESENTED", "seated_after": ctrl.seated}

    if ctrl.seated:
        rec["pick_nest"] = pick(belief, NEST_YAW + yaw_err, "pick_nest")
        ok = rec["pick_nest"]["lifted"]
        rec["result"] = "PASS" if ok else "FAIL retrieve"
    else:
        rec["result"] = "FAIL not seated"
    HELD["on"] = False
    gripper(False, wait=0.3)
    reset_plate()
    move_to(SOURCE + [0, 0, 0.15], tool_down(NEST_YAW))
    rec["h4_events"] = [e for e in ctrl.events if e["t"] >= rec.setdefault("_t0", 0)]
    trials.append(rec)
    print(f"[robot] trial {i:2d} {mode:12s} err={rec['belief_err_mm']}mm/{rec['belief_yaw_err_deg']}deg "
          f"seated={rec.get('seated')} plate_err={rec.get('plate_err_mm')} release={rec.get('release_height_mm')}mm "
          f"v_land={rec.get('landing_speed_mm_s')}mm/s corr={rec.get('guide_correction_mm')} -> {rec['result']}")

wall = time.time() - t_start
summary = {}
for mode in ("registered", "unregistered"):
    ts = [t for t in trials if t["mode"] == mode]
    summary[mode] = {"trials": len(ts), "seated": sum(bool(t.get("seated")) for t in ts),
                     "retrieved": sum(t["result"] == "PASS" for t in ts),
                     "max_landing_speed_mm_s": max((t.get("landing_speed_mm_s", 0) for t in ts), default=None),
                     "max_release_height_mm": max((t.get("release_height_mm", 0) for t in ts), default=None)}
cycle = next((t.get("quarantine_cycle") for t in trials if "quarantine_cycle" in t), None)
ok = (summary["registered"]["retrieved"] == summary["registered"]["trials"] and cycle is not None
      and all(cycle.values()))
os.makedirs(REPORT_DIR, exist_ok=True)
with open(os.path.join(REPORT_DIR, f"h4_robot_report_{args.scene}_{args.place_mode}.json"), "w") as f:
    json.dump({"scene": args.scene, "place_mode": args.place_mode, "summary": summary, "quarantine_cycle": cycle, "trials": trials, "physics_hz": HZ,
               "wall_time_s": round(wall, 1), "seed": args.seed}, f, indent=2, default=str)
print(f"[robot] summary {summary} quarantine_cycle={cycle} wall={wall:.0f}s -> {'PASS' if ok else 'FAIL'}")
app_utils.stop()
sys.stdout.flush()
os._exit(0 if ok else 1)
