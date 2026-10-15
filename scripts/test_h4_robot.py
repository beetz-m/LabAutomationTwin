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
Control: damped-least-squares differential IK on the PhysX Jacobian, straight-line Cartesian moves.

Writes test_reports/h4_robot_report.json; exit 1 unless every registered trial seats and is retrieved.
Usage: env_isaacsim/bin/python scripts/test_h4_robot.py [--trials N] [--seed S]
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
                help="bench: standalone rig; cell01: scenes/cell01_h4.usda overlay, FR3 on R01's base_link")
ap.add_argument("--place-mode", choices=("compliant", "drop"), default="compliant",
                help="compliant: lower the plate into the guides under low arm stiffness and release 2 mm "
                     "above the seat; drop: release 1 mm above the guide tops (~13 mm free fall)")
args = ap.parse_args()

H4_USD = os.path.join(ROOT, "assets/h4/h4.usda")
PLATE_USD = os.path.join(ROOT, "assets/labware/plate_sbs96.usda")
FR3_USD = os.path.join(ROOT, "assets/fr3/usd/fr3_arm/fr3_arm.usda")
GRIPPER_USD = os.path.join(ROOT, "assets/gripper/plate_gripper.usda")
CELL01_OVERLAY = os.path.join(ROOT, "scenes/cell01_h4.usda")
REPORT_DIR = os.path.join(ROOT, "test_reports")
HZ = 240
DT = 1.0 / HZ
BENCH_Z = 0.90
FR3_BASE = (0.30, -0.62, BENCH_Z, 90.0)
TCP_OFF = (0.0, 0.0, 0.171)           # plate_grasp_frame in the gripper body frame
GRIP_Z_ABOVE_BOTTOM = 0.006           # TCP sits 6 mm above the plate bottom when grasped
RELEASE_ABOVE_SEAT = 0.013            # drop mode: plate bottom 1 mm above the 12 mm guide tops
COMPLIANT_RELEASE = 0.002             # compliant mode: plate bottom 2 mm above the seat at release
COMPLIANCE = (0.03, 0.20)             # joint stiffness / damping scale while in impedance mode
IMPEDANCE = None                      # Cartesian stiffness diag, set below (needs numpy)
STROKE = 0.006
APPROACH = 0.20                       # approach/transit height above a site; 0.10 m clipped H4's open door
                                      # top (~1.09 m) in the Cell 01 placement. A collision-aware planner
                                      # (cuMotion) is the production answer; straight lines suffice here.
PLATE_MASS = 0.07                     # kg, as authored in plate_sbs96.usda
READY = [0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785]

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True})

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from isaacsim.core.experimental.prims import Articulation, RigidPrim  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402
from pxr import Gf, PhysxSchema, Usd, UsdGeom, UsdPhysics  # noqa: E402

from twin.h4_controller import H4Controller  # noqa: E402

if args.scene == "bench":
    SOURCE = np.array([0.55, -0.27, BENCH_Z + 0.04])
    H4_PATH, FR3_PATH, GRIP_PATH = "/World/H4_Quarantine", "/World/FR3", "/World/Gripper"
else:  # test-only handover stand within R01 reach (not part of Cell 01)
    SOURCE = np.array([-1.60, 0.45, 0.96])
    H4_PATH = "/World/Cell01/Stations/H4_Quarantine"
    FR3_PATH, GRIP_PATH = "/World/Cell01/Robots/R01_FR3/FR3", "/World/Cell01/Robots/R01_FR3/PlateGripper"
    H4_YAW_CELL01 = -92.0  # as placed by tools/compose_cell01_overlay.py (checked against the stage below)
IMPEDANCE = np.array([800.0, 800.0, 1500.0, 10.0, 10.0, 10.0])  # N/m (x, y, z), N*m/rad (rx, ry, rz)
IMP_DAMPING = np.array([40.0, 40.0, 60.0])                     # N*s/m (x, y, z)
rng = np.random.default_rng(args.seed)


# ------------------------------------------------------------------------------ math
def qmul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return np.array([aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw])


def qconj(q):
    return q * np.array([1, -1, -1, -1])


def qmat(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                     [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                     [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def qyaw(deg):
    a = math.radians(deg) / 2
    return np.array([math.cos(a), 0, 0, math.sin(a)])


def skew(v):
    return np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])


def tool_down(yaw_deg):
    """Tool +Z pointing down, jaws (+Y) along world Y rotated by yaw: grips the plate's long sides."""
    return qmul(qyaw(yaw_deg), np.array([0.0, 0.0, 1.0, 0.0]))  # yaw * (180 deg about Y)


def yaw_of(q):
    R = qmat(q)
    return math.degrees(math.atan2(R[1, 0], R[0, 0]))


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
else:  # Cell 01: H4 placed by the overlay; FR3 mounted on R01's base_link frame
    static_box("/World/TestFixtures/SourceStand", [SOURCE[0], SOURCE[1], SOURCE[2] / 2], (0.14, 0.07, SOURCE[2]),
               yaw_deg=H4_YAW_CELL01)  # oriented like the plate it presents
    h4 = UsdGeom.Xform(stage.GetPrimAtPath(H4_PATH))

fr3 = UsdGeom.Xform.Define(stage, FR3_PATH)
fr3.GetPrim().GetReferences().AddReference(FR3_USD)
fr3.GetPrim().GetVariantSets().GetVariantSet("Physics").SetVariantSelection("physx")
if args.scene == "bench":
    fr3.AddTranslateOp().Set(Gf.Vec3d(*FR3_BASE[:3]))
    fr3.AddRotateZOp().Set(FR3_BASE[3])
else:
    base_link = UsdGeom.Xformable(stage.GetPrimAtPath("/World/Cell01/Robots/R01_FR3/base_link"))
    fr3.AddTransformOp().Set(base_link.GetLocalTransformation())  # parent is R01_FR3, like base_link

plate = UsdGeom.Xform.Define(stage, "/World/Plate")
plate.GetPrim().GetReferences().AddReference(PLATE_USD)
plate.AddTranslateOp().Set(Gf.Vec3d(*map(float, SOURCE)))
plate.AddOrientOp().Set(Gf.Quatf(1, 0, 0, 0))
app.update()

ART_ROOT = next(str(p.GetPath()) for p in Usd.PrimRange(fr3.GetPrim())
                if p.HasAPI(UsdPhysics.ArticulationRootAPI))
LINK7 = next(str(p.GetPath()) for p in Usd.PrimRange(fr3.GetPrim()) if p.GetName() == "fr3_link7")

# gripper on the flange: 107 mm along link7 z, rotated -45 deg (Franka EE convention)
flange = Gf.Matrix4d(1.0).SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), -45.0)).SetTranslateOnly(Gf.Vec3d(0, 0, 0.107))
link7_w = UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(LINK7))
grip = UsdGeom.Xform.Define(stage, GRIP_PATH)
grip.GetPrim().GetReferences().AddReference(GRIPPER_USD)
grip.AddTransformOp().Set(flange * link7_w * UsdGeom.XformCache().GetParentToWorldTransform(grip.GetPrim()).GetInverse())
mount = UsdPhysics.FixedJoint.Define(stage, "/World/GripperMount")
mount.CreateBody0Rel().SetTargets([LINK7])
mount.CreateBody1Rel().SetTargets([f"{GRIP_PATH}/GripperBody"])
mount.CreateLocalPos0Attr(Gf.Vec3f(0, 0, 0.107))
mount.CreateLocalRot0Attr(Gf.Quatf(math.cos(math.radians(-22.5)), 0, 0, math.sin(math.radians(-22.5))))
mount.CreateLocalPos1Attr(Gf.Vec3f(0))
mount.CreateLocalRot1Attr(Gf.Quatf(1, 0, 0, 0))
for p in list(Usd.PrimRange(fr3.GetPrim())) + list(Usd.PrimRange(grip.GetPrim())):
    if p.HasAPI(UsdPhysics.RigidBodyAPI):  # emulate the FR3's gravity compensation
        PhysxSchema.PhysxRigidBodyAPI.Apply(p).CreateDisableGravityAttr(True)
PhysxSchema.PhysxArticulationAPI.Apply(stage.GetPrimAtPath(ART_ROOT)).CreateSleepThresholdAttr(0.0)  # robot too
for _ in range(5):
    app.update()

xc = UsdGeom.XformCache()
_nest_w = xc.GetLocalToWorldTransform(stage.GetPrimAtPath(f"{H4_PATH}/transfer_nest"))
NEST_TRUE = np.array(_nest_w.ExtractTranslation())
_R = _nest_w.ExtractRotationMatrix()
NEST_YAW = math.degrees(math.atan2(_R[0][1], _R[0][0]))  # nest +X (plate long axis) in world
if args.scene == "cell01":
    assert abs(NEST_YAW - H4_YAW_CELL01) < 0.5, (NEST_YAW, H4_YAW_CELL01)

# ------------------------------------------------------------------------------ runtime handles
app_utils.play(commit=True)
ctrl = H4Controller(stage, H4_PATH)
arm = Articulation(ART_ROOT)
names = list(arm.dof_names)
ARM = [names.index(f"fr3_joint{i}") for i in range(1, 8)]
FA, FB = names.index("FingerAJoint"), names.index("FingerBJoint")
links = list(arm.link_names)
BODY_LINK = links.index("GripperBody")
body_rp = RigidPrim(f"{GRIP_PATH}/GripperBody")
plate_rp = RigidPrim("/World/Plate")
print(f"[robot] articulation {ART_ROOT}: dofs={names} links={len(links)} gripper link #{BODY_LINK}")

# Jacobian layout: PhysX reports this imported FR3 as floating-base (the URDF root_joint is a separate
# constraint), i.e. one row per link and 6 virtual base columns before the DOF columns. Verified by
# perturbing each joint and comparing the measured TCP twist (scripts probe, 2026-10-15).
_J = arm.get_jacobian_matrices().numpy()
if _J.shape[1] == len(links) and _J.shape[3] == len(names) + 6:
    J_ROW, J_COLS = BODY_LINK, [6 + a for a in ARM]
else:
    J_ROW, J_COLS = BODY_LINK - 1, ARM
print(f"[robot] jacobian {_J.shape} -> row {J_ROW}, cols {J_COLS}")
# PhysX reports the linear Jacobian rows at the link's centre of mass, not its frame origin; shifting
# from the origin left a deterministic 2-4 mm path error in feed-forward (compliant) motion.
COM_LOCAL = np.zeros(3)
COM_LOCAL = arm.get_link_coms()[0].numpy()[0, BODY_LINK].astype(float)
print(f"[robot] gripper link COM (local) = {np.round(COM_LOCAL * 1e3, 1)} mm")
arm.set_dof_positions(np.array([READY], dtype=np.float32), dof_indices=ARM)
arm.set_dof_position_targets(np.array([READY], dtype=np.float32), dof_indices=ARM)


HELD = {"on": False, "offset": None, "dropped": None}


def _watch(i, k):
    ctrl.update(DT)
    if HELD["on"] and HELD["dropped"] is None:
        p_tcp = tcp()[0]
        d = plate_pose()[0] - p_tcp
        if HELD["offset"] is None:
            HELD["offset"] = d
        elif np.linalg.norm(d - HELD["offset"]) > 0.005:
            q = arm.get_dof_positions().numpy()[0][ARM]
            HELD["dropped"] = {"t": round(ctrl.t, 3), "tcp": np.round(p_tcp, 4).tolist(),
                               "slip_mm": np.round((d - HELD["offset"]) * 1e3, 1).tolist(),
                               "q_deg": np.round(np.degrees(q), 1).tolist()}
            print(f"[robot]   PLATE SLIPPED/DROPPED {HELD['dropped']}")


def step(n=1):
    SimulationManager.step(steps=n, callback=_watch)


def tcp():
    """TCP position, gripper orientation, and the gripper link's COM (the Jacobian's reference point)."""
    p, q = body_rp.get_world_poses()
    p, q = p.numpy()[0].astype(float), q.numpy()[0].astype(float)
    R = qmat(q)
    return p + R @ np.array(TCP_OFF), q, p + R @ COM_LOCAL


def ik_step(target_p, target_q, gain=0.12, damping=0.02, max_dq=0.01):
    p_tcp, q_cur, p_ref = tcp()
    J = arm.get_jacobian_matrices().numpy()[0, J_ROW][:, J_COLS].astype(float)
    J[:3] -= skew(p_tcp - p_ref) @ J[3:]
    qe = qmul(target_q, qconj(q_cur))
    e = np.concatenate([target_p - p_tcp, 2 * np.sign(qe[0]) * qe[1:]])
    Jinv = J.T @ np.linalg.inv(J @ J.T + damping ** 2 * np.eye(6))
    dq = Jinv @ e
    # null-space posture bias toward READY (joints 1-6; joint 7 is free for tool yaw): keeps the
    # redundant 7-DOF arm in one consistent elbow-up configuration across trials
    q_now = arm.get_dof_positions().numpy()[0][ARM].astype(float)
    bias = np.array(READY) - q_now
    bias[6] = 0.0
    dq += (np.eye(7) - Jinv @ J) @ (0.02 * bias)
    dq = np.clip(gain * dq, -max_dq, max_dq)
    tgt = arm.get_dof_position_targets().numpy()[0][ARM] + dq
    arm.set_dof_position_targets(np.array([tgt], dtype=np.float32), dof_indices=ARM)
    return np.linalg.norm(e[:3]), math.degrees(np.linalg.norm(e[3:]))


def move_to(goal_p, goal_q, speed=0.20, tol_mm=0.4, tol_deg=0.2, timeout=4.0):
    """Straight-line Cartesian move (linear position, slerp-free yaw blend), then converge."""
    p0, q0, _ = tcp()
    dist = np.linalg.norm(goal_p - p0)
    n = max(1, int(dist / speed * HZ))
    for i in range(1, n + 1):
        a = i / n
        q = q0 * (1 - a) + goal_q * a if np.dot(q0, goal_q) >= 0 else q0 * (1 - a) - goal_q * a
        ik_step(p0 + (goal_p - p0) * a, q / np.linalg.norm(q))
        step()
    settled = 0
    x_prev = tcp()[0]
    for k in range(int(timeout * HZ)):
        ep, er = ik_step(goal_p, goal_q)
        step()
        # converged = within tolerance AND the TCP at rest (< 2 mm/s) for 10 consecutive steps; a
        # tolerance-only check passed transiently mid-motion and the arm overshot the grasp by 4 mm.
        # (TCP speed, not joint speed: the null-space posture bias may keep reconfiguring the elbow.)
        x_now = tcp()[0]
        still = np.linalg.norm(x_now - x_prev) * HZ < 0.002
        x_prev = x_now
        settled = settled + 1 if (ep * 1e3 < tol_mm and er < tol_deg and still) else 0
        if settled >= 10:
            return True, ep * 1e3, er
    q = arm.get_dof_positions().numpy()[0][ARM]
    print(f"[robot]   move_to timeout: pos_err={ep * 1e3:.2f}mm rot_err={er:.2f}deg goal={np.round(goal_p, 4)} "
          f"tcp={np.round(tcp()[0], 4)} q={np.round(np.degrees(q), 1)}")
    return False, ep * 1e3, er


def gripper(close, wait=0.5, ramp=0.4):
    """Emulates the GEP2006: mechanically coupled jaws (symmetric targets, ramped, so the first jaw to
    touch pushes the plate until it is centred) and force-limited gripping (targets beyond the
    stroke end, so the 30 N drive cap sets the grip force rather than the jaw position)."""
    q = arm.get_dof_positions().numpy()[0]
    s0 = (abs(q[FA]) + abs(q[FB])) / 2
    s1 = STROKE + 0.003 if close else 0.0
    n = max(1, int(ramp * HZ))
    for i in range(1, n + 1):
        s = s0 + (s1 - s0) * i / n
        arm.set_dof_position_targets(np.array([[-s, s]], dtype=np.float32), dof_indices=[FA, FB])
        step()
    step(int(wait * HZ))
    q = arm.get_dof_positions().numpy()[0]
    return abs(q[FA]) * 1e3, abs(q[FB]) * 1e3


def plate_pose():
    p, q = plate_rp.get_world_poses()
    return p.numpy()[0].astype(float), q.numpy()[0].astype(float)


def reset_plate():
    d = np.array([rng.uniform(-1.5, 1.5), rng.uniform(-1.5, 1.5), 0]) * 1e-3
    yaw = NEST_YAW + rng.uniform(-1, 1)  # source presented in the nest's orientation (no big wrist roll)
    plate_rp.set_world_poses(positions=[(SOURCE + d + [0, 0, 0.0005]).tolist()], orientations=[qyaw(yaw).tolist()])
    plate_rp.set_velocities(linear_velocities=[[0, 0, 0]], angular_velocities=[[0, 0, 0]])
    step(int(0.4 * HZ))


def pick(center_xy_z_bottom, yaw, label):
    """Top-down long-side grasp of a plate whose bottom-centre is believed at center (world)."""
    q = tool_down(yaw)
    above = center_xy_z_bottom + [0, 0, GRIP_Z_ABOVE_BOTTOM + APPROACH]
    grasp = center_xy_z_bottom + [0, 0, GRIP_Z_ABOVE_BOTTOM]
    ok1, *_ = move_to(above, q)
    ok2, *_ = move_to(grasp, q, speed=0.08)
    fa, fb = gripper(True)
    contact = fa < STROKE * 1e3 - 0.5 and fb < STROKE * 1e3 - 0.5
    z0 = plate_pose()[0][2]
    HELD.update(on=True, offset=None, dropped=None)
    p_grasp = tcp()[0]
    ok3, *_ = move_to(above, q, speed=0.10)
    lifted = plate_pose()[0][2] - z0 > 0.08
    # where the plate actually sits in the fingers, in the tool frame (nominal: bottom 6 mm below TCP)
    pt, qt, _ = tcp()
    rel = qmat(qt).T @ (plate_pose()[0] - pt)
    return {"phase": label, "reached": ok1 and ok2 and ok3, "contact": contact, "lifted": lifted,
            "finger_travel_mm": [round(fa, 2), round(fb, 2)],
            "tcp_err_at_grasp_mm": [round(v * 1e3, 2) for v in (p_grasp - grasp)],
            "plate_in_tool_mm": [round(v * 1e3, 2) for v in rel]}


def release_and_watch(wait=0.4):
    """Open the gripper and record the plate's release height and peak landing speed."""
    HELD["on"] = False
    seat_z = NEST_TRUE[2]
    h = plate_pose()[0][2] - seat_z
    vmax = 0.0
    q = arm.get_dof_positions().numpy()[0]
    s0 = (abs(q[FA]) + abs(q[FB])) / 2
    n = int(0.4 * HZ)
    for i in range(n + int(wait * HZ)):
        if i < n:
            s = s0 * (1 - (i + 1) / n)
            arm.set_dof_position_targets(np.array([[-s, s]], dtype=np.float32), dof_indices=[FA, FB])
        step()
        v = plate_rp.get_velocities()[0].numpy()[0]
        vmax = max(vmax, float(-v[2]))
    return {"release_height_mm": round(h * 1e3, 2), "landing_speed_mm_s": round(vmax * 1e3, 1)}


def place(nest_bottom_center, yaw):
    q = tool_down(yaw)
    above = nest_bottom_center + [0, 0, GRIP_Z_ABOVE_BOTTOM + APPROACH]
    entry = nest_bottom_center + [0, 0, GRIP_Z_ABOVE_BOTTOM + RELEASE_ABOVE_SEAT]
    ok1, *_ = move_to(above, q)
    ok2, ep, er = move_to(entry, q, speed=0.08)
    info = {}
    if args.place_mode == "drop":
        info.update(release_and_watch())
    else:
        # Cartesian impedance (as on the FR3): per step, joint torques tau = J^T (K e - D v) + payload
        # compensation, realised through softened joint drives as q_t = q + tau / k_joint.
        # Insertion practice: (A) ramp into the soft mode while holding the entry pose, (B) let it settle,
        # (C) descend slowly, (D) hold. Without A/B the gain switch left a ~4 mm lateral transient and 2/8
        # plates met a guide while still moving and jammed (15-37 mm excursions).
        stiff0, damp0 = (g.numpy().copy() for g in arm.get_dof_gains())
        p_tcp, _, _ = tcp()
        q_goal = q
        depth = RELEASE_ABOVE_SEAT - COMPLIANT_RELEASE
        state = {"x_prev": p_tcp.copy(), "k": stiff0[0, ARM].astype(float)}
        lat_max, lat_trace = 0.0, []

        def impedance_step(x_des, scale_k, scale_d):
            ks, kd = stiff0.copy(), damp0.copy()
            ks[0, ARM] *= scale_k
            kd[0, ARM] *= scale_d
            arm.set_dof_gains(ks, kd, update_default_gains=False)
            k_joint = ks[0, ARM].astype(float)
            x, q_cur, p_ref = tcp()
            v = (x - state["x_prev"]) * HZ
            state["x_prev"] = x
            J = arm.get_jacobian_matrices().numpy()[0, J_ROW][:, J_COLS].astype(float)
            J[:3] -= skew(x - p_ref) @ J[3:]
            qe = qmul(q_goal, qconj(q_cur))
            e = np.concatenate([x_des - x, 2 * np.sign(qe[0]) * qe[1:]])
            wrench = IMPEDANCE * e
            wrench[:3] -= IMP_DAMPING * v
            wrench[2] += PLATE_MASS * 9.81  # payload support
            q_now = arm.get_dof_positions().numpy()[0][ARM].astype(float)
            arm.set_dof_position_targets(np.array([q_now + (J.T @ wrench) / k_joint], dtype=np.float32),
                                         dof_indices=ARM)
            step()
            return x - x_des

        n_ramp, n_settle, n_desc, n_hold = int(0.25 * HZ), int(0.3 * HZ), int(depth / 0.015 * HZ), int(0.3 * HZ)
        t = 0
        for i in range(n_ramp + n_settle + n_desc + n_hold):
            a = min(1.0, (i + 1) / n_ramp)  # gain ramp, log-linear from stiff to soft
            sk = COMPLIANCE[0] ** a
            sd = COMPLIANCE[1] ** a
            dz = depth * min(max(i - n_ramp - n_settle + 1, 0), n_desc) / n_desc
            err = impedance_step(p_tcp + [0.0, 0.0, -dz], sk, sd)
            lat = float(np.linalg.norm(err[:2]))
            if i >= n_ramp + n_settle:
                lat_max = max(lat_max, lat)
            if i % 24 == 0:
                lat_trace.append((round(i / HZ, 2), round(lat * 1e3, 2), round(float(err[2]) * 1e3, 2)))
        lateral = (tcp()[0] - (p_tcp + [0, 0, -depth]))[:2]
        info["guide_correction_mm"] = [round(v * 1e3, 2) for v in lateral]
        info["impedance_lateral_max_mm"] = round(lat_max * 1e3, 2)
        info["impedance_trace"] = lat_trace  # (t s, lateral err mm, vertical err mm)
        info.update(release_and_watch())
        cur = arm.get_dof_positions().numpy()[0][ARM]
        arm.set_dof_position_targets(np.array([cur], dtype=np.float32), dof_indices=ARM)  # no jump on re-stiffening
        arm.set_dof_gains(stiff0, damp0, update_default_gains=False)
        step(int(0.1 * HZ))
    ok3, *_ = move_to(above, q, speed=0.10)
    step(int(0.5 * HZ))
    return ok1 and ok2 and ok3, info


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
