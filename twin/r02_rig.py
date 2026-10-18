"""R02 runtime: the rail-mounted UR5e (assets/r02/r02.urdf import) with its automatic tool changer, in Isaac Sim 6.2.

  author_r02(stage)   before play: references R02 on /World/Cell01/Robots/R02_RailSystem/R02 (rail origin from
                      layout P1), stiffens the rail drive, emulates the UR's gravity compensation, adds the coupler
                      lock and the robot_coupler frame, and replaces the placeholder rail of the Cell 01 scene.
  R02Rig              after play: joint and Cartesian motion of the 7 joints (rail + 6) and the coupler and T01 jaws.

Coupler lock. Isaac Sim 6.2 ignores joints created or (re-)enabled while the simulation runs, so the lock uses the
Surface Gripper mechanism (isaacsim.robot.surface_gripper): one D6 attachment joint on r02_wrist_3_link with every
degree of freedom locked, whose second body the native gripper binds to the rigid body found along the coupler axis
within MAX_LOCK_GAP when it closes, and releases when it opens. Tools must never sleep (assets/r02/build_tooling.py):
a sleeping tool was not woken when the coupler released it and hung in the air.

Planning uses twin/kinematics.py on the same URDF; frames: the robot coupler face is 16 mm along the wrist_3 axis.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
R02_USD = os.path.join(ROOT, "assets/r02/usd/r02/r02.usda")
R02_URDF = os.path.join(ROOT, "assets/r02/r02.urdf")
R02 = "/World/Cell01/Robots/R02_RailSystem"
R02_PATH = f"{R02}/R02"
TCM = "/World/Cell01/Tooling/AutomaticToolChanger"
COUPLER_FACE = 0.016           # robot coupler face beyond tool0 (= r02_wrist_3_link frame), m
MAX_LOCK_GAP = 0.004           # m, coupler faces must be this close for the lock to engage
RAIL_STIFFNESS, RAIL_DAMPING = 2.0e5, 2.0e4  # N/m, N*s/m (the importer's 2000 N/m is for revolute joints)
RAIL_SOFT = (0.02, 2.58)       # m, soft travel limits inside the 0..2.6 m hard limits
INITIAL_RAIL = 1.30            # m, start position (carriage at x 0.45, mid-cell)
HZ = 240
DT = 1.0 / HZ


def layout():
    with open(os.path.join(ROOT, "scenes/layout_p1.json")) as f:
        return json.load(f)


def rail_origin():
    r = layout()["r02_rail"]
    return np.array([r["x0"], r["y"], 0.0])


def tool_prims(stage):
    tools = stage.GetPrimAtPath(f"{TCM}/Tools")
    return {c.GetName(): c for c in tools.GetChildren()} if tools else {}


# ------------------------------------------------------------------------------ authoring (before play)
def author_r02(stage, contact_prims=()):
    """Add R02 to the composed Cell 01 stage; returns (articulation root, wrist link, coupler gripper prim)."""
    from usd.schema.isaac import robot_schema
    stage.GetPrimAtPath(f"{R02}/LinearRail").SetActive(False)  # placeholder rail cube: the asset brings the real rail
    x = UsdGeom.Xform.Define(stage, R02_PATH)
    x.GetPrim().GetReferences().AddReference(R02_USD)
    x.GetPrim().GetVariantSets().GetVariantSet("Physics").SetVariantSelection("physx")
    x.AddTranslateOp().Set(Gf.Vec3d(*map(float, rail_origin())))
    prims = list(Usd.PrimRange(x.GetPrim()))
    art_root = next(str(p.GetPath()) for p in prims if p.HasAPI(UsdPhysics.ArticulationRootAPI))
    wrist = next(str(p.GetPath()) for p in prims if p.GetName() == "r02_wrist_3_link")
    rail = next(p for p in prims if p.GetName() == "rail_joint")
    UsdPhysics.DriveAPI(rail, "linear").CreateStiffnessAttr(RAIL_STIFFNESS)
    UsdPhysics.DriveAPI(rail, "linear").CreateDampingAttr(RAIL_DAMPING)
    for p in prims:
        if p.HasAPI(UsdPhysics.RigidBodyAPI):  # the UR controller compensates gravity; the rail carries the load
            PhysxSchema.PhysxRigidBodyAPI.Apply(p).CreateDisableGravityAttr(True)
    PhysxSchema.PhysxArticulationAPI.Apply(stage.GetPrimAtPath(art_root)).CreateSleepThresholdAttr(0.0)
    # initial state: carry posture mid-rail (all-zero joints stretch the arm 0.8 m west, into L09)
    q0 = R02Rig.carry(INITIAL_RAIL, side=-1.0)
    for p in prims:
        if p.IsA(UsdPhysics.RevoluteJoint) and p.GetName().startswith("r02_"):
            k = 1 + ["shoulder_pan", "shoulder_lift", "elbow", "wrist_1", "wrist_2", "wrist_3"].index(
                p.GetName()[4:-6])
            PhysxSchema.JointStateAPI.Apply(p, "angular").CreatePositionAttr(math.degrees(q0[k]))
            UsdPhysics.DriveAPI(p, "angular").CreateTargetPositionAttr(math.degrees(q0[k]))
    PhysxSchema.JointStateAPI.Apply(rail, "linear").CreatePositionAttr(INITIAL_RAIL)
    UsdPhysics.DriveAPI(rail, "linear").CreateTargetPositionAttr(INITIAL_RAIL)
    f = UsdGeom.Xform.Define(stage, f"{wrist}/robot_coupler")
    f.AddTranslateOp().Set(Gf.Vec3d(0, 0, COUPLER_FACE))
    f.GetPrim().CreateAttribute("sdt:frameRole", Sdf.ValueTypeNames.String, custom=True).Set(
        "R02 robot coupler face (TCM01 robot_coupler); +Z out of the flange")

    # coupler lock: a fully locked D6 attachment joint, bound by the surface gripper when it closes. Its body0 is a
    # collider-free coupler body fixed to the wrist (inside the articulation): with body0 = the wrist link, the
    # gripper's self-clearance logic measured the wrist's own coupler collider (17 mm) and settled the tool that far
    # into the robot (2026-10-15 diagnosis).
    cb = UsdGeom.Xform.Define(stage, f"{R02_PATH}/CouplerBody")
    UsdPhysics.RigidBodyAPI.Apply(cb.GetPrim())
    m = UsdPhysics.MassAPI.Apply(cb.GetPrim())
    m.CreateMassAttr(0.05)
    m.CreateDiagonalInertiaAttr(Gf.Vec3f(1e-5, 1e-5, 1e-5))
    PhysxSchema.PhysxRigidBodyAPI.Apply(cb.GetPrim()).CreateDisableGravityAttr(True)
    mount = UsdPhysics.FixedJoint.Define(stage, f"{R02_PATH}/CouplerMount")
    mount.CreateBody0Rel().SetTargets([wrist])
    mount.CreateBody1Rel().SetTargets([cb.GetPath()])
    mount.CreateLocalPos0Attr(Gf.Vec3f(0, 0, COUPLER_FACE))
    mount.CreateLocalPos1Attr(Gf.Vec3f(0))
    dummy = UsdGeom.Xform.Define(stage, f"{R02_PATH}/CouplerPark")
    dummy.AddTranslateOp().Set(Gf.Vec3d(0, 0, -0.5))
    UsdPhysics.RigidBodyAPI.Apply(dummy.GetPrim()).CreateKinematicEnabledAttr(True)
    j = UsdPhysics.Joint.Define(stage, f"{R02_PATH}/CouplerLock")
    jp = j.GetPrim()
    jp.AddAppliedSchema("IsaacAttachmentPointAPI")
    for ax in ("transX", "transY", "transZ", "rotX", "rotY", "rotZ"):
        lim = UsdPhysics.LimitAPI.Apply(jp, ax)
        lim.CreateLowAttr(1.0)
        lim.CreateHighAttr(-1.0)     # low > high: locked
    j.CreateBody0Rel().SetTargets([cb.GetPath()])
    j.CreateBody1Rel().SetTargets([dummy.GetPath()])
    j.CreateLocalPos0Attr(Gf.Vec3f(0))       # +Z (forward axis) points out of the flange, into the tool
    j.CreateLocalRot0Attr(Gf.Quatf(1, 0, 0, 0))
    j.CreateLocalPos1Attr(Gf.Vec3f(0))
    j.CreateLocalRot1Attr(Gf.Quatf(1, 0, 0, 0))
    j.CreateExcludeFromArticulationAttr(True)
    jp.CreateAttribute("isaac:forwardAxis", Sdf.ValueTypeNames.Token).Set("Z")
    jp.CreateAttribute("isaac:clearanceOffset", Sdf.ValueTypeNames.Float).Set(0.0)
    robot_schema.CreateSurfaceGripper(stage, f"{R02_PATH}/Coupler")
    gp = stage.GetPrimAtPath(f"{R02_PATH}/Coupler")
    gp.GetRelationship(robot_schema.Relations.ATTACHMENT_POINTS.name).SetTargets([jp.GetPath()])
    gp.GetAttribute(robot_schema.Attributes.MAX_GRIP_DISTANCE.name).Set(MAX_LOCK_GAP)
    gp.GetAttribute(robot_schema.Attributes.COAXIAL_FORCE_LIMIT.name).Set(1.0e5)   # mechanical lock: no slip-off
    gp.GetAttribute(robot_schema.Attributes.SHEAR_FORCE_LIMIT.name).Set(1.0e5)
    gp.GetAttribute(robot_schema.Attributes.RETRY_INTERVAL.name).Set(0.5)
    # coupler halves are in contact whenever locked: filter the wrist against every tool's bodies
    filt = UsdPhysics.FilteredPairsAPI.Apply(stage.GetPrimAtPath(wrist)).CreateFilteredPairsRel()
    for tool in tool_prims(stage).values():
        for p in Usd.PrimRange(tool):
            if p.HasAPI(UsdPhysics.RigidBodyAPI):
                filt.AddTarget(p.GetPath())
    for p in [stage.GetPrimAtPath(c) for c in contact_prims] + prims:
        if contact_prims and p.HasAPI(UsdPhysics.RigidBodyAPI):
            PhysxSchema.PhysxContactReportAPI.Apply(p).CreateThresholdAttr().Set(0.0)
    for name, target in (("rail_base", f"{art_root}"), ("rail_carriage", "rail_carriage"),
                         ("robot_base_link", "r02_shoulder_link"), ("tool0", "r02_wrist_3_link")):
        ph = stage.GetPrimAtPath(f"{R02}/{name}")
        if ph:
            ph.CreateAttribute("sdt:bindingStatus", Sdf.ValueTypeNames.String).Set("articulated_v1")
            ph.CreateAttribute("sdt:boundTo", Sdf.ValueTypeNames.String, custom=True).Set(
                target if target.startswith("/") else f"{R02_PATH} link {target}")
    return art_root, wrist, str(gp.GetPath())


# ------------------------------------------------------------------------------ runtime (after play)
class R02Rig:
    """Motion of R02's 7 joints (rail + UR5e), its coupler, and the T01 jaws when T01 is coupled."""

    def __init__(self, art_root, wrist, coupler, on_step=(), log=print):
        from isaacsim.core.experimental.prims import Articulation, RigidPrim
        from isaacsim.robot.surface_gripper import _surface_gripper as sgi
        from twin.kinematics import UrdfChain
        self.log, self.on_step, self.t = log, list(on_step), 0.0
        # optional joint trace for offline swept-volume checks (tools/fitout_clearance.py): R02_TRACE=<file>
        self._trace = open(os.environ["R02_TRACE"], "a", buffering=1) if os.environ.get("R02_TRACE") else None
        self._trace_k = 0
        self.arm = Articulation(art_root)
        names = list(self.arm.dof_names)
        self.RAIL = names.index("rail_joint")
        self.UR = [names.index(f"r02_{n}_joint") for n in ("shoulder_pan", "shoulder_lift", "elbow", "wrist_1",
                                                          "wrist_2", "wrist_3")]
        self.ALL = [self.RAIL] + self.UR
        links = list(self.arm.link_names)
        wl = links.index("r02_wrist_3_link")
        J = self.arm.get_jacobian_matrices().numpy()
        self.J_ROW, self.J_COLS = (wl, [6 + a for a in self.UR]) if J.shape[3] == len(names) + 6 else (wl - 1, self.UR)
        self.wrist = RigidPrim(wrist)
        self.COM = self.arm.get_link_coms()[0].numpy()[0, wl].astype(float)
        self.coupler, self.sg = coupler, sgi.acquire_surface_gripper_interface()
        self.kin = UrdfChain(R02_URDF, "rail_base", "r02_tool0")
        self.base = rail_origin()
        self.posture = None
        self.rng = np.random.default_rng(0)
        self.tool = None          # {"id", "path", "tcp" (m from the coupling face), "fingers" (T01 jaws)}
        self.holding = False
        log(f"[r02] articulation {art_root}: dofs={names}; jacobian {J.shape} -> row {self.J_ROW}")

    # ---------------------------------------------------------------- stepping / state
    def _watch(self, i, k):
        self.t += DT
        for f in self.on_step:
            f(DT)
        if self._trace is not None:
            self._trace_k += 1
            if self._trace_k % 12 == 0:      # 20 Hz
                tool = (self.tool or {}).get("id", "") if isinstance(self.tool, dict) else ""
                self._trace.write(" ".join(f"{v:.5f}" for v in self.q()) + f" {int(bool(self.holding))} {tool or '-'}\n")
        if self.holding and self.tool and self.tool.get("fingers"):
            qa, qb = self.jaw_q()                    # coupled jaws + preload while holding (R01 lesson)
            s = (abs(qa) + abs(qb)) / 2 + 0.0025
            self._jaw_set(-s, s)

    def step(self, n=1):
        from isaacsim.core.simulation_manager import SimulationManager
        SimulationManager.step(steps=n, callback=self._watch)

    def run_until(self, pred, timeout, chunk=0.25):
        t0 = self.t
        while self.t - t0 < timeout:
            self.step(int(chunk * HZ))
            if pred():
                return True
        return False

    def q(self):
        return self.arm.get_dof_positions().numpy()[0][self.ALL].astype(float)

    def coupler_pose(self):
        """World pose (p, R) of the robot coupler face, and the wrist link's COM (the Jacobian reference)."""
        p, q = self.wrist.get_world_poses()
        p, q = p.numpy()[0].astype(float), q.numpy()[0].astype(float)
        from twin.r01_rig import qmat
        R = qmat(q)
        return p + R @ np.array([0, 0, COUPLER_FACE]), R, p + R @ self.COM

    def tcp(self):
        """Tool centre point: the coupler face, or the coupled tool's TCP along the tool axis."""
        p, R, ref = self.coupler_pose()
        off = self.tool["tcp"] if self.tool else 0.0
        return p + R[:, 2] * off, R, ref

    # ---------------------------------------------------------------- planning (URDF kinematics)
    def solve(self, p_world, R, seed, rail=None, extra=0.0, tries=24):
        """IK for the TCP at p_world with orientation R, rail fixed at `rail` (m) if given; elbow-up UR solutions
        with >= 15 deg joint margin, best conditioned first among those near the seed. Returns q (7) or None."""
        tool = np.eye(4)
        tool[2, 3] = COUPLER_FACE + (self.tool["tcp"] if self.tool else 0.0) + extra
        rng = self.rng
        seed = np.array(seed, float)
        if rail is not None:
            seed[0] = rail
        act = range(1, 7) if rail is not None else range(7)
        best = None
        for k in range(tries):
            q0 = seed.copy()
            if k:
                q0[1:] = [rng.uniform(-math.pi, math.pi), rng.uniform(-2.0, -0.8), rng.uniform(0.8, 2.4),
                          rng.uniform(-2.5, -0.8), -math.pi / 2, rng.uniform(-math.pi, math.pi)]
            q = self.kin.ik(np.asarray(p_world) - self.base, R, q0, active=act, tool=tool, iters=250)
            if q is None or not (-math.pi <= q[2] <= 0 and 0 <= q[3] <= math.radians(170)) or \
                    self.kin.margin(q, range(1, 7)) < math.radians(15):
                continue
            score = self.kin.sigma_min(q, range(1, 7), tool) - 0.02 * np.abs(q[1:] - seed[1:]).sum()
            if best is None or score > best[0]:
                best = (score, q)
            if k >= 8 and best is not None:
                break
        return None if best is None else best[1]

    # ---------------------------------------------------------------- motion
    def move_joints(self, q_goal, speed_deg_s=45.0, rail_speed=0.4, tol=(0.3, 0.0005), timeout=8.0):
        q_goal = np.asarray(q_goal, float)
        q0 = self.arm.get_dof_position_targets().numpy()[0][self.ALL].astype(float)
        d = np.abs(q_goal - q0)
        n = max(1, int(max(math.degrees(d[1:].max()) / speed_deg_s, d[0] / rail_speed) * HZ))
        for i in range(1, n + 1):
            self.arm.set_dof_position_targets(np.array([q0 + (q_goal - q0) * i / n], dtype=np.float32),
                                              dof_indices=self.ALL)
            self.step()
        settled, x_prev = 0, self.tcp()[0]
        for _ in range(int(timeout * HZ)):
            self.step()
            x = self.tcp()[0]
            e = np.abs(self.q() - q_goal)
            still = np.linalg.norm(x - x_prev) * HZ < 0.002
            x_prev = x
            settled = settled + 1 if (math.degrees(e[1:].max()) < tol[0] and e[0] < tol[1] and still) else 0
            if settled >= 10:
                return True
        self.log(f"[r02]   move_joints timeout: err rail {e[0] * 1e3:.2f} mm, ur {np.round(np.degrees(e[1:]), 2)} deg")
        return False

    def ik_step(self, target_p, target_R, gain=0.12, damping=0.02, max_dq=0.01):
        from twin.r01_rig import skew
        p, R, ref = self.tcp()
        J = self.arm.get_jacobian_matrices().numpy()[0, self.J_ROW][:, self.J_COLS].astype(float)
        J[:3] -= skew(p - ref) @ J[3:]
        e = np.concatenate([target_p - p, 0.5 * sum(np.cross(R[:, i], target_R[:, i]) for i in range(3))])
        Jinv = J.T @ np.linalg.inv(J @ J.T + damping ** 2 * np.eye(6))
        dq = Jinv @ e
        if self.posture is not None:
            bias = self.posture[1:] - self.q()[1:]
            dq += (np.eye(6) - Jinv @ J) @ (0.02 * bias)
        dq = np.clip(gain * dq, -max_dq, max_dq)
        tgt = self.arm.get_dof_position_targets().numpy()[0][self.UR] + dq
        self.arm.set_dof_position_targets(np.array([tgt], dtype=np.float32), dof_indices=self.UR)
        return np.linalg.norm(e[:3]), math.degrees(np.linalg.norm(e[3:]))

    def move_to(self, goal_p, goal_R, speed=0.10, tol_mm=0.4, tol_deg=0.2, timeout=4.0):
        """Straight-line Cartesian move of the TCP (UR joints; rail held), then converge at rest."""
        p0, R0, _ = self.tcp()
        n = max(1, int(np.linalg.norm(goal_p - p0) / speed * HZ))
        for i in range(1, n + 1):
            self.ik_step(p0 + (goal_p - p0) * i / n, goal_R)
            self.step()
        settled, x_prev = 0, self.tcp()[0]
        for _ in range(int(timeout * HZ)):
            ep, er = self.ik_step(goal_p, goal_R)
            self.step()
            x = self.tcp()[0]
            still = np.linalg.norm(x - x_prev) * HZ < 0.002
            x_prev = x
            settled = settled + 1 if (ep * 1e3 < tol_mm and er < tol_deg and still) else 0
            if settled >= 10:
                return True, ep * 1e3, er
        self.log(f"[r02]   move_to timeout: pos_err={ep * 1e3:.2f}mm rot_err={er:.2f}deg goal={np.round(goal_p, 4)}")
        return False, ep * 1e3, er

    def go(self, p_world, R, rail=None, via_carry=True, side=None):
        """Planned move: carry posture, rail, approach configuration (IK), then a short Cartesian convergence."""
        p_world = np.asarray(p_world, float)
        rail = float(np.clip(p_world[0] - self.base[0] if rail is None else rail, *RAIL_SOFT))
        side = side if side is not None else (1.0 if p_world[1] > self.base[1] else -1.0)
        q_goal = self.solve(p_world, R, self.carry(rail, side=side), rail=rail)
        if q_goal is None:
            self.log(f"[r02]   no IK for {np.round(p_world, 3)} at rail {rail:.3f}")
            return False
        ok = True
        if via_carry:
            c = self.carry(None, side=side)
            ok &= self.move_joints(np.r_[self.q()[0], c[1:]])
            ok &= self.move_joints(np.r_[rail, c[1:]])
        ok &= self.move_joints(q_goal)
        self.posture = q_goal
        ok2, *_ = self.move_to(p_world, R)
        return bool(ok and ok2)

    @staticmethod
    def carry(rail, pan=None, side=-1.0):
        """Compact transport posture: tool down, wrist raised close to the base, facing the pan direction."""
        pan = (math.pi / 2 if side > 0 else -math.pi / 2) if pan is None else pan
        return np.array([0.0 if rail is None else rail, pan, -1.75, 1.95, -1.77, -math.pi / 2, 0.0])

    # ---------------------------------------------------------------- coupler and T01 jaws
    def coupler_close(self, wait=0.5):
        self.sg.close_gripper(self.coupler)
        self.step(int(wait * HZ))
        return str(self.sg.get_gripper_status(self.coupler)).split(".")[-1], list(self.sg.get_gripped_objects(self.coupler))

    def coupler_open(self, wait=0.3):
        self.sg.open_gripper(self.coupler)
        self.step(int(wait * HZ))
        return str(self.sg.get_gripper_status(self.coupler)).split(".")[-1]

    def jaw_q(self):
        """T01 jaw positions (m along the tool Y axis; A closes toward -, B toward +) from the body poses."""
        from twin.r01_rig import qmat
        f = self.tool["fingers"]
        pb, qb = f["body"].get_world_poses()
        Rb = qmat(qb.numpy()[0].astype(float))
        out = []
        for k in ("A", "B"):
            pf = f[k][0].get_world_poses()[0].numpy()[0].astype(float)
            out.append(float((Rb.T @ (pf - pb.numpy()[0].astype(float)))[1]))
        return out

    def _jaw_set(self, a, b):
        f = self.tool["fingers"]
        f["A"][1].GetTargetPositionAttr().Set(float(a))
        f["B"][1].GetTargetPositionAttr().Set(float(b))

    def jaws(self, close, ramp=0.4, wait=0.5):
        """T01 jaws (GEP2006 emulation as on R01): ramped symmetric targets, force-capped grip beyond the stroke."""
        qa, qb = self.jaw_q()
        s0, s1 = (abs(qa) + abs(qb)) / 2, (0.009 if close else 0.0)
        n = max(1, int(ramp * HZ))
        for i in range(1, n + 1):
            s = s0 + (s1 - s0) * i / n
            self._jaw_set(-s, s)
            self.step()
        self.step(int(wait * HZ))
        qa, qb = self.jaw_q()
        return abs(qa) * 1e3, abs(qb) * 1e3
