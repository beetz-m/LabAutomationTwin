"""R01 robot rig: FR3 (URDF import) + proxy plate gripper, with the validated pick / place / move primitives.

Extracted from scripts/test_h4_robot.py (2026-10-15) so the H4 hand-off campaigns and the Cell 01 episodes
(scripts/run_cell01_episode.py) share one implementation:
  * damped-least-squares differential IK on the PhysX Jacobian, straight-line Cartesian moves that converge only
    with the tool point at rest;
  * GEP2006 emulation: ramped symmetric jaw targets, force-limited grip, and coupled jaws while holding;
  * compliant placement (FR3 Cartesian impedance emulated through softened joint drives, with a null-space
    posture term), or drop placement.
The reasons for each choice are recorded in assets/h4/README.md ("Lessons recorded in the test script").

Use (inside a SimulationApp, Isaac Sim 6.2):
    art_root = author_rig(stage, fr3_path, grip_path, mount_path, fr3_local)   # before play
    app_utils.play(commit=True)
    rig = R01Rig(art_root, grip_path, plates=[...], on_step=[ctrl.update, ...])
"""

from __future__ import annotations

import math
import os

import numpy as np
from isaacsim.core.experimental.prims import Articulation, RigidPrim
from isaacsim.core.simulation_manager import SimulationManager
from omni.physx import get_physx_simulation_interface
from pxr import Gf, PhysicsSchemaTools, PhysxSchema, Usd, UsdGeom, UsdPhysics

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FR3_USD = os.path.join(ROOT, "assets/fr3/usd/fr3_arm/fr3_arm.usda")
GRIPPER_USD = os.path.join(ROOT, "assets/gripper/plate_gripper.usda")
PLATE_USD = os.path.join(ROOT, "assets/labware/plate_sbs96.usda")

HZ = 240
DT = 1.0 / HZ
TCP_OFF = (0.0, 0.0, 0.171)           # plate_grasp_frame in the gripper body frame
GRIP_Z_ABOVE_BOTTOM = 0.006           # TCP sits 6 mm above the plate bottom when grasped
RELEASE_ABOVE_SEAT = 0.013            # drop mode: plate bottom 1 mm above the 12 mm guide tops
COMPLIANT_RELEASE = 0.002             # compliant mode: plate bottom 2 mm above the seat at release
COMPLIANCE = (0.03, 0.20)             # joint stiffness / damping scale while in impedance mode
STROKE = 0.006
APPROACH = 0.20                       # approach/transit height above a site; 0.10 m clipped H4's open door
                                      # top (~1.09 m) in the Cell 01 placement. A collision-aware planner
                                      # (cuMotion) is the production answer; straight lines suffice here.
PLATE_MASS = 0.07                     # kg, as authored in plate_sbs96.usda
READY = [0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785]
IMPEDANCE = np.array([800.0, 800.0, 1500.0, 10.0, 10.0, 10.0])  # N/m (x, y, z), N*m/rad (rx, ry, rz)
IMP_DAMPING = np.array([40.0, 40.0, 60.0])                     # N*s/m (x, y, z)
# null-space posture stiffness / damping (FR3 is redundant; franka_example_controllers' Cartesian impedance uses
# nullspace_stiffness 20 too). Without it the elbow's self-motion had zero stiffness while compliant.
NS_STIFFNESS, NS_DAMPING = 20.0, 2.0 * math.sqrt(20.0)        # N*m/rad, N*m*s/rad
GRIP_SQUEEZE = 0.0025  # coupled-jaw preload: 10 kN/m finger drive x 2.5 mm = 25 N per jaw (below the 30 N cap)


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


def frame_pose(stage, path):
    """World position and yaw (deg, of the frame's +X) of a prim."""
    m = UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(path))
    R = m.ExtractRotationMatrix()
    return np.array(m.ExtractTranslation()), math.degrees(math.atan2(R[0][1], R[0][0]))


# ------------------------------------------------------------------------------ authoring (before play)
def author_rig(stage, fr3_path, grip_path, mount_path, fr3_local: Gf.Matrix4d, contact_prims=()):
    """FR3 + plate gripper fixed to the flange; returns the articulation root path.

    fr3_local: the FR3 base pose in its parent's frame. contact_prims: extra rigid bodies (plates) whose contacts
    are reported together with the robot's and gripper's (contact reports are enabled only if this is given).
    """
    fr3 = UsdGeom.Xform.Define(stage, fr3_path)
    fr3.GetPrim().GetReferences().AddReference(FR3_USD)
    fr3.GetPrim().GetVariantSets().GetVariantSet("Physics").SetVariantSelection("physx")
    fr3.AddTransformOp().Set(fr3_local)
    art_root = next(str(p.GetPath()) for p in Usd.PrimRange(fr3.GetPrim()) if p.HasAPI(UsdPhysics.ArticulationRootAPI))
    link7 = next(str(p.GetPath()) for p in Usd.PrimRange(fr3.GetPrim()) if p.GetName() == "fr3_link7")

    # gripper on the flange: 107 mm along link7 z, rotated -45 deg (Franka EE convention)
    flange = Gf.Matrix4d(1.0).SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), -45.0)).SetTranslateOnly(Gf.Vec3d(0, 0, 0.107))
    link7_w = UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(link7))
    grip = UsdGeom.Xform.Define(stage, grip_path)
    grip.GetPrim().GetReferences().AddReference(GRIPPER_USD)
    grip.AddTransformOp().Set(flange * link7_w * UsdGeom.XformCache().GetParentToWorldTransform(grip.GetPrim()).GetInverse())
    mount = UsdPhysics.FixedJoint.Define(stage, os.path.dirname(grip_path) + "/GripperMount")
    mount.CreateBody0Rel().SetTargets([link7])
    mount.CreateBody1Rel().SetTargets([f"{grip_path}/GripperBody"])
    mount.CreateLocalPos0Attr(Gf.Vec3f(0, 0, 0.107))
    mount.CreateLocalRot0Attr(Gf.Quatf(math.cos(math.radians(-22.5)), 0, 0, math.sin(math.radians(-22.5))))
    mount.CreateLocalPos1Attr(Gf.Vec3f(0))
    mount.CreateLocalRot1Attr(Gf.Quatf(1, 0, 0, 0))
    robot_prims = list(Usd.PrimRange(fr3.GetPrim())) + list(Usd.PrimRange(grip.GetPrim()))
    for p in robot_prims:
        if p.HasAPI(UsdPhysics.RigidBodyAPI):  # emulate the FR3's gravity compensation
            PhysxSchema.PhysxRigidBodyAPI.Apply(p).CreateDisableGravityAttr(True)
    PhysxSchema.PhysxArticulationAPI.Apply(stage.GetPrimAtPath(art_root)).CreateSleepThresholdAttr(0.0)  # robot too
    # The FR3 base is bolted to its mount: without this filter fr3_link0's collider pressed into the pedestal (Cell 01)
    # or bench throughout every move (contact impulses up to ~80 N*s per step), fighting the base's root_joint, which
    # PhysX enforces as an external constraint because ArticulationRootAPI sits on the base link. In layout P1 this
    # coincided with intermittent 3-36 mm lateral jolts during compliant insertion (1/16 failed).
    UsdPhysics.FilteredPairsAPI.Apply(stage.GetPrimAtPath(art_root)).CreateFilteredPairsRel().AddTarget(mount_path)
    if contact_prims:
        for p in robot_prims + [stage.GetPrimAtPath(c) for c in contact_prims]:
            if p.HasAPI(UsdPhysics.RigidBodyAPI):
                PhysxSchema.PhysxContactReportAPI.Apply(p).CreateThresholdAttr().Set(0.0)
    return art_root


def add_plate(stage, path, position, yaw_deg=0.0, barcode=None):
    """An SBS 96-well plate (origin = bottom centre) with an optional barcode label (labware:barcode)."""
    from pxr import Sdf
    p = UsdGeom.Xform.Define(stage, path)
    p.GetPrim().GetReferences().AddReference(PLATE_USD)
    p.AddTranslateOp().Set(Gf.Vec3d(*map(float, position)))
    p.AddOrientOp().Set(Gf.Quatf(*map(float, qyaw(yaw_deg))))
    if barcode:
        p.GetPrim().CreateAttribute("labware:barcode", Sdf.ValueTypeNames.String, custom=True).Set(barcode)
    return p.GetPrim()


# ------------------------------------------------------------------------------ runtime (after play)
class R01Rig:
    def __init__(self, art_root, grip_path, plates, on_step=(), place_mode="compliant", contacts=False, log=print):
        self.place_mode = place_mode
        self.on_step = list(on_step)
        self.contacts_on = contacts
        self.log = log
        self.t = 0.0
        self.arm = Articulation(art_root)
        names = list(self.arm.dof_names)
        self.ARM = [names.index(f"fr3_joint{i}") for i in range(1, 8)]
        self.FA, self.FB = names.index("FingerAJoint"), names.index("FingerBJoint")
        links = list(self.arm.link_names)
        self.LIM_LO, self.LIM_HI = (np.asarray(v.numpy()[0][self.ARM], float) for v in self.arm.get_dof_limits())
        body_link = links.index("GripperBody")
        self.body_rp = RigidPrim(f"{grip_path}/GripperBody")
        self.plates = {p: RigidPrim(p) for p in plates}
        self.plate = plates[0] if plates else None  # the plate pick()/place() act on
        log(f"[rig] articulation {art_root}: dofs={names} links={len(links)} gripper link #{body_link}")
        # Jacobian layout: PhysX reports this imported FR3 as floating-base (the URDF root_joint is a separate
        # constraint), i.e. one row per link and 6 virtual base columns before the DOF columns. Verified by
        # perturbing each joint and comparing the measured TCP twist (scripts probe, 2026-10-15).
        J = self.arm.get_jacobian_matrices().numpy()
        if J.shape[1] == len(links) and J.shape[3] == len(names) + 6:
            self.J_ROW, self.J_COLS = body_link, [6 + a for a in self.ARM]
        else:
            self.J_ROW, self.J_COLS = body_link - 1, self.ARM
        log(f"[rig] jacobian {J.shape} -> row {self.J_ROW}, cols {self.J_COLS}")
        # PhysX reports the linear Jacobian rows at the link's centre of mass, not its frame origin; shifting
        # from the origin left a deterministic 2-4 mm path error in feed-forward (compliant) motion.
        self.COM_LOCAL = self.arm.get_link_coms()[0].numpy()[0, body_link].astype(float)
        log(f"[rig] gripper link COM (local) = {np.round(self.COM_LOCAL * 1e3, 1)} mm")
        self.arm.set_dof_positions(np.array([READY], dtype=np.float32), dof_indices=self.ARM)
        self.arm.set_dof_position_targets(np.array([READY], dtype=np.float32), dof_indices=self.ARM)
        self.held = {"on": False, "offset": None, "dropped": None}
        self.posture = np.array(READY)   # null-space posture bias of the Cartesian IK (joint 7 excluded)
        self.phase = None          # contact-log phase label (None: not logging)
        self.contact_log = {}      # phase -> {(collider0, collider1): [first t, steps, max impulse N*s]}

    # ---------------------------------------------------------------- stepping
    def _watch(self, i, k):
        self.t += DT
        for f in self.on_step:
            f(DT)
        if self.held["on"]:
            # GEP2006 jaws are mechanically coupled. With both jaws merely force-capped (targets beyond the stroke)
            # the gripper body had no stiffness relative to the plate along the jaw axis, and the compliant arm
            # could slide along it until one jaw reached its stroke end and the other shoved the arm 20-30 mm
            # sideways (layout P1 campaigns). Both jaws track the mean jaw position + a preload, so any asymmetry
            # is pushed back with 2 x 10 kN/m.
            qf = self.arm.get_dof_positions().numpy()[0]
            s_mean = (abs(qf[self.FA]) + abs(qf[self.FB])) / 2 + GRIP_SQUEEZE
            self.arm.set_dof_position_targets(np.array([[-s_mean, s_mean]], dtype=np.float32),
                                              dof_indices=[self.FA, self.FB])
        if self.held["on"] and self.held["dropped"] is None:
            p_tcp = self.tcp()[0]
            d = self.plate_pose()[0] - p_tcp
            if self.held["offset"] is None:
                self.held["offset"] = d
            elif np.linalg.norm(d - self.held["offset"]) > 0.005:
                q = self.arm.get_dof_positions().numpy()[0][self.ARM]
                self.held["dropped"] = {"t": round(self.t, 3), "tcp": np.round(p_tcp, 4).tolist(),
                                        "slip_mm": np.round((d - self.held["offset"]) * 1e3, 1).tolist(),
                                        "q_deg": np.round(np.degrees(q), 1).tolist()}
                self.log(f"[rig]   PLATE SLIPPED/DROPPED {self.held['dropped']}")
        if self.contacts_on and self.phase is not None:
            self._log_contacts(self.phase)

    def _log_contacts(self, phase):
        heads, data = get_physx_simulation_interface().get_contact_report()
        book = self.contact_log.setdefault(phase, {})
        for h in heads:
            imp = sum(np.linalg.norm(np.array(data[k].impulse)) for k in
                      range(h.contact_data_offset, h.contact_data_offset + h.num_contact_data))
            pair = tuple(sorted(str(PhysicsSchemaTools.intToSdfPath(c)) for c in (h.collider0, h.collider1)))
            c = book.setdefault(pair, [round(self.t, 3), 0, 0.0])
            c[1] += 1
            c[2] = max(c[2], float(imp))

    def step(self, n=1):
        SimulationManager.step(steps=n, callback=self._watch)

    def run_until(self, pred, timeout, chunk=0.25):
        t0 = self.t
        while self.t - t0 < timeout:
            self.step(int(chunk * HZ))
            if pred():
                return True
        return False

    # ---------------------------------------------------------------- state
    def tcp(self):
        """TCP position, gripper orientation, and the gripper link's COM (the Jacobian's reference point)."""
        p, q = self.body_rp.get_world_poses()
        p, q = p.numpy()[0].astype(float), q.numpy()[0].astype(float)
        R = qmat(q)
        return p + R @ np.array(TCP_OFF), q, p + R @ self.COM_LOCAL

    def plate_pose(self, path=None):
        p, q = self.plates[path or self.plate].get_world_poses()
        return p.numpy()[0].astype(float), q.numpy()[0].astype(float)

    def q_arm(self):
        return self.arm.get_dof_positions().numpy()[0][self.ARM].astype(float)

    # ---------------------------------------------------------------- motion
    def ik_step(self, target_p, target_q, gain=0.12, damping=0.02, max_dq=0.01):
        p_tcp, q_cur, p_ref = self.tcp()
        J = self.arm.get_jacobian_matrices().numpy()[0, self.J_ROW][:, self.J_COLS].astype(float)
        J[:3] -= skew(p_tcp - p_ref) @ J[3:]
        qe = qmul(target_q, qconj(q_cur))
        e = np.concatenate([target_p - p_tcp, 2 * np.sign(qe[0]) * qe[1:]])
        Jinv = J.T @ np.linalg.inv(J @ J.T + damping ** 2 * np.eye(6))
        dq = Jinv @ e
        # null-space posture bias toward self.posture (READY by default; joints 1-6, joint 7 is free for tool
        # yaw): keeps the redundant 7-DOF arm in one consistent configuration across trials / at a station
        bias = self.posture - self.q_arm()
        bias[6] = 0.0
        dq += (np.eye(7) - Jinv @ J) @ (0.02 * bias)
        dq = np.clip(gain * dq, -max_dq, max_dq)
        tgt = self.arm.get_dof_position_targets().numpy()[0][self.ARM] + dq
        self.arm.set_dof_position_targets(np.array([tgt], dtype=np.float32), dof_indices=self.ARM)
        return np.linalg.norm(e[:3]), math.degrees(np.linalg.norm(e[3:]))

    def move_to(self, goal_p, goal_q, speed=0.20, tol_mm=0.4, tol_deg=0.2, timeout=4.0):
        """Straight-line Cartesian move (linear position, normalised-lerp orientation), then converge."""
        p0, q0, _ = self.tcp()
        dist = np.linalg.norm(goal_p - p0)
        n = max(1, int(dist / speed * HZ))
        for i in range(1, n + 1):
            a = i / n
            q = q0 * (1 - a) + goal_q * a if np.dot(q0, goal_q) >= 0 else q0 * (1 - a) - goal_q * a
            self.ik_step(p0 + (goal_p - p0) * a, q / np.linalg.norm(q))
            self.step()
        settled = 0
        x_prev = self.tcp()[0]
        for k in range(int(timeout * HZ)):
            ep, er = self.ik_step(goal_p, goal_q)
            self.step()
            # converged = within tolerance AND the TCP at rest (< 2 mm/s) for 10 consecutive steps; a
            # tolerance-only check passed transiently mid-motion and the arm overshot the grasp by 4 mm.
            # (TCP speed, not joint speed: the null-space posture bias may keep reconfiguring the elbow.)
            x_now = self.tcp()[0]
            still = np.linalg.norm(x_now - x_prev) * HZ < 0.002
            x_prev = x_now
            settled = settled + 1 if (ep * 1e3 < tol_mm and er < tol_deg and still) else 0
            if settled >= 10:
                return True, ep * 1e3, er
        self.log(f"[rig]   move_to timeout: pos_err={ep * 1e3:.2f}mm rot_err={er:.2f}deg goal={np.round(goal_p, 4)} "
                 f"tcp={np.round(self.tcp()[0], 4)} q={np.round(np.degrees(self.q_arm()), 1)}")
        return False, ep * 1e3, er

    def move_joints(self, q_goal, speed_deg_s=45.0, tol_deg=0.3, timeout=6.0):
        """Joint-space move (linear in joint space, ramped targets), then wait for the arm to settle; used for
        planned transits between stations (twin/r01_planner.py)."""
        q_goal = np.asarray(q_goal, float)
        q0 = self.arm.get_dof_position_targets().numpy()[0][self.ARM].astype(float)
        n = max(1, int(math.degrees(np.abs(q_goal - q0).max()) / speed_deg_s * HZ))
        for i in range(1, n + 1):
            self.arm.set_dof_position_targets(np.array([q0 + (q_goal - q0) * i / n], dtype=np.float32),
                                              dof_indices=self.ARM)
            self.step()
        x_prev, settled = self.tcp()[0], 0
        for _ in range(int(timeout * HZ)):
            self.step()
            x_now = self.tcp()[0]
            still = np.linalg.norm(x_now - x_prev) * HZ < 0.002
            x_prev = x_now
            settled = settled + 1 if (math.degrees(np.abs(self.q_arm() - q_goal).max()) < tol_deg and still) else 0
            if settled >= 10:
                return True
        self.log(f"[rig]   move_joints timeout: err={np.round(np.degrees(self.q_arm() - q_goal), 2)} deg")
        return False

    def gripper(self, close, wait=0.5, ramp=0.4):
        """Emulates the GEP2006: mechanically coupled jaws (symmetric targets, ramped, so the first jaw to
        touch pushes the plate until it is centred) and force-limited gripping (targets beyond the
        stroke end, so the 30 N drive cap sets the grip force rather than the jaw position)."""
        q = self.arm.get_dof_positions().numpy()[0]
        s0 = (abs(q[self.FA]) + abs(q[self.FB])) / 2
        s1 = STROKE + 0.003 if close else 0.0
        n = max(1, int(ramp * HZ))
        for i in range(1, n + 1):
            s = s0 + (s1 - s0) * i / n
            self.arm.set_dof_position_targets(np.array([[-s, s]], dtype=np.float32), dof_indices=[self.FA, self.FB])
            self.step()
        self.step(int(wait * HZ))
        q = self.arm.get_dof_positions().numpy()[0]
        return abs(q[self.FA]) * 1e3, abs(q[self.FB]) * 1e3

    def pick(self, center_xy_z_bottom, yaw, label, plate=None):
        """Top-down long-side grasp of a plate whose bottom-centre is believed at center (world)."""
        if plate:
            self.plate = plate
        q = tool_down(yaw)
        above = center_xy_z_bottom + [0, 0, GRIP_Z_ABOVE_BOTTOM + APPROACH]
        grasp = center_xy_z_bottom + [0, 0, GRIP_Z_ABOVE_BOTTOM]
        ok1, *_ = self.move_to(above, q)
        ok2, *_ = self.move_to(grasp, q, speed=0.08)
        fa, fb = self.gripper(True)
        contact = fa < STROKE * 1e3 - 0.5 and fb < STROKE * 1e3 - 0.5
        z0 = self.plate_pose()[0][2]
        self.held.update(on=True, offset=None, dropped=None)
        p_grasp = self.tcp()[0]
        ok3, *_ = self.move_to(above, q, speed=0.10)
        lifted = self.plate_pose()[0][2] - z0 > 0.08
        # where the plate actually sits in the fingers, in the tool frame (nominal: bottom 6 mm below TCP)
        pt, qt, _ = self.tcp()
        rel = qmat(qt).T @ (self.plate_pose()[0] - pt)
        return {"phase": label, "reached": ok1 and ok2 and ok3, "contact": contact, "lifted": lifted,
                "finger_travel_mm": [round(fa, 2), round(fb, 2)],
                "tcp_err_at_grasp_mm": [round(v * 1e3, 2) for v in (p_grasp - grasp)],
                "plate_in_tool_mm": [round(v * 1e3, 2) for v in rel]}

    def release_and_watch(self, seat_z, wait=0.4):
        """Open the gripper and record the plate's release height and peak landing speed."""
        self.held["on"] = False
        h = self.plate_pose()[0][2] - seat_z
        vmax = 0.0
        q = self.arm.get_dof_positions().numpy()[0]
        s0 = (abs(q[self.FA]) + abs(q[self.FB])) / 2
        n = int(0.4 * HZ)
        for i in range(n + int(wait * HZ)):
            if i < n:
                s = s0 * (1 - (i + 1) / n)
                self.arm.set_dof_position_targets(np.array([[-s, s]], dtype=np.float32), dof_indices=[self.FA, self.FB])
            self.step()
            v = self.plates[self.plate].get_velocities()[0].numpy()[0]
            vmax = max(vmax, float(-v[2]))
        return {"release_height_mm": round(h * 1e3, 2), "landing_speed_mm_s": round(vmax * 1e3, 1)}

    def place(self, nest_bottom_center, yaw, seat_z=None, contacts_phase=None):
        """Place the held plate into a nest believed at nest_bottom_center (seat_z: the true seat height, for the
        release-height record; defaults to the believed one). contacts_phase: log contacts while inserting."""
        seat_z = nest_bottom_center[2] if seat_z is None else seat_z
        q = tool_down(yaw)
        above = nest_bottom_center + [0, 0, GRIP_Z_ABOVE_BOTTOM + APPROACH]
        entry = nest_bottom_center + [0, 0, GRIP_Z_ABOVE_BOTTOM + RELEASE_ABOVE_SEAT]
        ok1, *_ = self.move_to(above, q)
        ok2, ep, er = self.move_to(entry, q, speed=0.08)
        info = {}
        if self.place_mode == "drop":
            info.update(self.release_and_watch(seat_z))
        else:
            info.update(self._compliant_insert(q, contacts_phase))
            info.update(self.release_and_watch(seat_z))
            cur = self.arm.get_dof_positions().numpy()[0][self.ARM]
            self.arm.set_dof_position_targets(np.array([cur], dtype=np.float32), dof_indices=self.ARM)  # no jump
            self.arm.set_dof_gains(self._gains0[0], self._gains0[1], update_default_gains=False)          # re-stiffen
            self.step(int(0.1 * HZ))
        ok3, *_ = self.move_to(above, q, speed=0.10)
        self.step(int(0.5 * HZ))
        return ok1 and ok2 and ok3, info

    def _compliant_insert(self, q_goal, contacts_phase):
        # Cartesian impedance (as on the FR3): per step, joint torques tau = J^T (K e - D v) + payload
        # compensation, realised through softened joint drives as q_t = q + tau / k_joint.
        # Insertion practice: (A) ramp into the soft mode while holding the entry pose, (B) let it settle,
        # (C) descend slowly, (D) hold. Without A/B the gain switch left a ~4 mm lateral transient and 2/8
        # plates met a guide while still moving and jammed (15-37 mm excursions).
        arm, ARM = self.arm, self.ARM
        stiff0, damp0 = (g.numpy().copy() for g in arm.get_dof_gains())
        self._gains0 = (stiff0, damp0)
        p_tcp, _, _ = self.tcp()
        depth = RELEASE_ABOVE_SEAT - COMPLIANT_RELEASE
        state = {"x_prev": p_tcp.copy(), "margin": (np.inf, -1)}
        q_entry = self.q_arm()
        info = {"q_entry_deg": [round(math.degrees(v), 1) for v in q_entry]}
        lat_max, lat_trace = 0.0, []
        prev_phase = self.phase
        if contacts_phase and self.contacts_on:
            self.phase = contacts_phase

        def impedance_step(x_des, scale_k, scale_d):
            ks, kd = stiff0.copy(), damp0.copy()
            ks[0, ARM] *= scale_k
            kd[0, ARM] *= scale_d
            arm.set_dof_gains(ks, kd, update_default_gains=False)
            k_joint = ks[0, ARM].astype(float)
            x, q_cur, p_ref = self.tcp()
            v = (x - state["x_prev"]) * HZ
            state["x_prev"] = x
            J = arm.get_jacobian_matrices().numpy()[0, self.J_ROW][:, self.J_COLS].astype(float)
            J[:3] -= skew(x - p_ref) @ J[3:]
            qe = qmul(q_goal, qconj(q_cur))
            e = np.concatenate([x_des - x, 2 * np.sign(qe[0]) * qe[1:]])
            wrench = IMPEDANCE * e
            wrench[:3] -= IMP_DAMPING * v
            wrench[2] += PLATE_MASS * 9.81  # payload support
            q_now = self.q_arm()
            qd_now = arm.get_dof_velocities().numpy()[0][ARM].astype(float)
            # torque-level null-space projector N = I - J^T (J^T)^+ (kinematic pseudo-inverse)
            n_proj = np.eye(7) - J.T @ np.linalg.pinv(J.T, rcond=1e-4)
            tau_ns = n_proj @ (NS_STIFFNESS * (q_entry - q_now) - NS_DAMPING * qd_now)
            m = np.minimum(q_now - self.LIM_LO, self.LIM_HI - q_now)
            if m.min() < state["margin"][0]:
                state["margin"] = (float(m.min()), int(m.argmin()) + 1)
            arm.set_dof_position_targets(np.array([q_now + (J.T @ wrench + tau_ns) / k_joint], dtype=np.float32),
                                         dof_indices=ARM)
            self.step()
            return x - x_des

        n_ramp, n_settle, n_desc, n_hold = int(0.25 * HZ), int(0.3 * HZ), int(depth / 0.015 * HZ), int(0.3 * HZ)
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
        self.phase = prev_phase
        lateral = (self.tcp()[0] - (p_tcp + [0, 0, -depth]))[:2]
        info["guide_correction_mm"] = [round(v * 1e3, 2) for v in lateral]
        info["impedance_lateral_max_mm"] = round(lat_max * 1e3, 2)
        info["impedance_trace"] = lat_trace  # (t s, lateral err mm, vertical err mm)
        info["nullspace_drift_deg"] = round(float(np.degrees(np.abs(self.q_arm() - q_entry).max())), 2)
        info["joint_margin_min_deg"] = [round(math.degrees(state["margin"][0]), 1), f"joint{state['margin'][1]}"]
        return info

    def contacts(self, phase, short=True):
        """Logged contacts of a phase: 'a | b' -> [first t, steps in contact, max impulse N*s]."""
        def name(p):
            return p.split("/World/")[-1] if short else p
        return {" | ".join(name(p) for p in k): [v[0], v[1], round(v[2], 4)]
                for k, v in self.contact_log.get(phase, {}).items()}
