"""Runtime controller for R03 (clean sample AMR) and the H2 dock (sdt/components/R03_AMR_H2_Dock.yaml).

Asset: assets/r03/r03.usda (planar base PlanarX / PlanarY / Yaw -> BaseLink, cabinet lid) and h2_dock.usda.
Both prims share one map frame: the R03 prim is placed at the docked base_link pose, so dock_frame is the map
origin and +X the docking direction.

  navigate(route)         pure pursuit on the ESTIMATED pose (encoders + localization; a bias can be injected),
                          unicycle (differential-drive) kinematics: v <= 0.4 m/s, |w| <= 0.8 rad/s, turn in place
                          above 60 deg heading error. Cabinet must stay closed (stop + fault if it opens in transit).
  dock()                  from dock_approach: compliant lateral / yaw drives, forward at 0.05 m/s until the dock's
                          depth rays read the bumper at the stop; the V-guides centre the AMR mechanically. Accepted
                          when depth, yaw (two bumper rays) and lateral (two rays on the V-nose) are in tolerance;
                          then the drives are latched stiff at the reached pose ("arrival near H2 != docked").
                          Otherwise dock_misalignment: back out to the approach pose; the caller may relocalize and
                          retry.
  open_cabinet / close_cabinet   dock interlock: the lid opens only when docked
  undock()                close (interlock), back out to the approach pose
  carrier presence        4 seat-sensor rays in the carrier nest (shelf presence sensor)
The contract's transport monitors (localization, cabinet state, carrier presence, battery) are logged as the AMR
moves; twin/episode_records.py turns a transport into a Cell 01 `transport` record.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

import carb
import numpy as np
from isaacsim.core.experimental.prims import Articulation
from omni.physx import get_physx_scene_query_interface
from pxr import Gf, Usd, UsdGeom

MM = 0.001
JOINTS = {"x": "PlanarXJoint", "y": "PlanarYJoint", "yaw": "YawJoint", "lid": "LidSlide"}
STIFF = {"x": 2.0e5, "y": 2.0e5, "yaw": 5.0e4}         # N/m, N/m, N m/rad
DAMP = {"x": 2.0e4, "y": 2.0e4, "yaw": 1.4e3}
SOFT = {"y": 300.0, "yaw": 40.0}                        # compliant docking (the V-guides centre the AMR)
SOFT_DAMP = {"y": 800.0, "yaw": 20.0}
V_MAX, W_MAX, V_DOCK = 0.40, 0.8, 0.05
LOOKAHEAD = 0.35
DOCK_TOL = {"depth_mm": 1.5, "lateral_mm": 2.0, "yaw_deg": 0.3}
DEPTH_NOMINAL_MM = 11.0                                  # ray origin 10 mm behind the stop, bumper 1 mm in front
BATTERY_DRAIN = {"moving": 0.02, "idle": 0.002}          # %/s (assumption)
LIGHT_ON = 3000.0


CARRIER_SEAT_LOCAL = (0.035, -0.060, 0.960)          # carrier seat in the AMR base frame (m), see assets/r03


def author_r03_start(stage, root, pose):
    """Before play: start the AMR at map pose (x, y, yaw) (joint state + drive targets authored in USD)."""
    from pxr import PhysxSchema, UsdPhysics
    for name, val, kind in (("PlanarXJoint", pose[0], "linear"), ("PlanarYJoint", pose[1], "linear"),
                            ("YawJoint", math.degrees(pose[2]), "angular")):
        j = stage.GetPrimAtPath(f"{root}/Joints/{name}")
        PhysxSchema.JointStateAPI.Apply(j, kind).CreatePositionAttr(float(val))
        UsdPhysics.DriveAPI(j, kind).CreateTargetPositionAttr(float(val))


def carrier_seat_world(stage, root, pose):
    """World position and yaw (deg) of the carrier seat with the AMR at map pose (x, y, yaw)."""
    tf = UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(root))
    x, y, a = pose
    lx, ly, lz = CARRIER_SEAT_LOCAL
    m = Gf.Vec3d(x + math.cos(a) * lx - math.sin(a) * ly, y + math.sin(a) * lx + math.cos(a) * ly, lz)
    yaw_map = math.degrees(math.atan2(tf.TransformDir(Gf.Vec3d(1, 0, 0))[1], tf.TransformDir(Gf.Vec3d(1, 0, 0))[0]))
    return np.array(tf.Transform(m)), yaw_map + math.degrees(a)


@dataclass
class Result:
    accepted: bool
    reason: str = ""


@dataclass
class R03Controller:
    stage: Usd.Stage
    root: str
    dock_root: str
    dt: float = 1.0 / 240
    t: float = 0.0
    mode: str = "READY"          # READY | MOVING | DOCKING | DOCKED | FAULT
    fault: str = ""
    events: list = field(default_factory=list)

    def __post_init__(self):
        self.prim = self.stage.GetPrimAtPath(self.root)
        self.art = Articulation(self.root)
        names = list(self.art.dof_names)
        self.dof = {k: names.index(v) for k, v in JOINTS.items()}
        self.sq = get_physx_scene_query_interface()
        xc = UsdGeom.XformCache(Usd.TimeCode.Default())
        self.map_to_world = xc.GetLocalToWorldTransform(self.prim)
        self.lid_travel = float(self.prim.GetAttribute("amr:lidTravel_mm").Get()) * MM
        base = f"{self.root}/PlanarX/PlanarY/BaseLink"
        b0 = xc.GetLocalToWorldTransform(self.stage.GetPrimAtPath(base)).GetInverse()
        self.seat_local = [np.array(b0.Transform(xc.GetLocalToWorldTransform(self.stage.GetPrimAtPath(
            f"{base}/carrier_seat_sensor_{i}")).ExtractTranslation())) for i in range(4)]
        dock = self.stage.GetPrimAtPath(self.dock_root)
        self.dock_tf = xc.GetLocalToWorldTransform(dock)
        self.rays = {n: np.array(xc.GetLocalToWorldTransform(self.stage.GetPrimAtPath(f"{self.dock_root}/sensor_{n}"))
                                 .ExtractTranslation()) for n in ("depth_L", "depth_R", "nose_L", "nose_R")}
        self.ray_dir = np.array(self.dock_tf.TransformDir(Gf.Vec3d(-1, 0, 0)))
        self.approach = (-1.0, 0.0, 0.0)
        q = self.art.get_dof_positions().numpy()[0]
        self.tgt = {k: float(q[i]) for k, i in self.dof.items()}
        self.bias = np.zeros(3)              # localization error (injected): estimate = true + bias
        self.localization_ok = True
        self.battery = 100.0
        self.inventory = []                  # carrier ids believed on board
        self.contamination_class = "clean_sample_only"
        self.trace = []                      # (t, est x, y, yaw, cabinet, carrier, battery) at 2 Hz
        self.transit = None                  # running transport record
        self._next_trace = 0.0
        self._job = None
        self._written = {}
        self.read_sensors()

    # ---------------------------------------------------------------- sensing
    def _hits(self, origin, direction, dist, own):
        hits = []

        def report(h):
            if not h.collision.startswith(own + "/"):
                hits.append((h.distance, h.collision))
            return True

        self.sq.raycast_all(carb.Float3(*map(float, origin)), carb.Float3(*map(float, direction)), float(dist), report)
        return sorted(hits)

    def pose_true(self):
        return np.array([self.q["x"], self.q["y"], self.q["yaw"]])

    def pose_est(self):
        return self.pose_true() + self.bias

    def base_world(self, p_local):
        x, y, a = self.pose_true()
        c, s = math.cos(a), math.sin(a)
        m = np.array([x + c * p_local[0] - s * p_local[1], y + s * p_local[0] + c * p_local[1], p_local[2]])
        return np.array(self.map_to_world.Transform(Gf.Vec3d(*map(float, m))))

    def read_sensors(self):
        q = self.art.get_dof_positions().numpy()[0]
        self.q = {k: float(q[i]) for k, i in self.dof.items()}
        self.cabinet = "open" if self.q["lid"] < -0.002 else "closed"
        up = np.array(self.map_to_world.TransformDir(Gf.Vec3d(0, 0, 1)))
        gaps = []
        for s in self.seat_local:
            h = self._hits(self.base_world(s), up, 0.015, self.root)
            gaps.append(None if not h else h[0][0] - 0.001)
        self.carrier_present = any(g is not None for g in gaps)
        self.carrier_seated = all(g is not None and g < 0.0004 for g in gaps)
        self.carrier_gaps = gaps

    def dock_sensors(self):
        d = {}
        for n, o in self.rays.items():
            h = self._hits(o, self.ray_dir, 0.08, self.dock_root)
            d[n] = None if not h else h[0][0] * 1e3
        out = {"rays_mm": {k: None if v is None else round(v, 3) for k, v in d.items()}}
        if None not in (d["depth_L"], d["depth_R"]):
            out["depth_mm"] = round((d["depth_L"] + d["depth_R"]) / 2 - DEPTH_NOMINAL_MM, 3)
            out["yaw_deg"] = round(math.degrees(math.atan2(d["depth_R"] - d["depth_L"], 300.0)), 4)
        if None not in (d["nose_L"], d["nose_R"]):
            out["lateral_mm"] = round((d["nose_R"] - d["nose_L"]) / 2, 3)
        out["ok"] = all(k in out for k in ("depth_mm", "yaw_deg", "lateral_mm")) and \
            abs(out["depth_mm"]) <= DOCK_TOL["depth_mm"] and abs(out["lateral_mm"]) <= DOCK_TOL["lateral_mm"] and \
            abs(out["yaw_deg"]) <= DOCK_TOL["yaw_deg"]
        return out

    # ---------------------------------------------------------------- commands
    def load_carrier(self, carrier_id, carrier_class="clean"):
        """Inventory: a carrier was put into the cabinet at the source (identity bound to the transport history)."""
        if carrier_class != "clean":
            return self._refuse("load_carrier", f"carrier class {carrier_class!r} not allowed on the clean-sample AMR")
        self.inventory.append(carrier_id)
        self._log("carrier_loaded", carrier_id=carrier_id)
        return Result(True)

    def navigate(self, route, speed=V_MAX, reverse=False) -> Result:
        """reverse=True drives backwards along the route (e.g. backing out of the dock zone without turning in place)."""
        if self.mode not in ("READY",):
            return self._refuse("navigate", f"mode {self.mode}")
        if self.cabinet != "closed":
            return self._refuse("navigate", "cabinet open: close it before moving")
        self._start("navigate", self._seq_route([np.array(p[:2], float) for p in route], speed, reverse),
                    route=[list(p) for p in route], reverse=reverse)
        return Result(True)

    def dock(self, compliant=True) -> Result:
        if self.mode != "READY":
            return self._refuse("dock", f"mode {self.mode}")
        e = self.pose_est()
        if np.hypot(e[0] - self.approach[0], e[1] - self.approach[1]) > 0.05 or abs(self._wrap(e[2])) > math.radians(5):
            return self._refuse("dock", f"not at dock_approach (estimate {np.round(e, 3).tolist()})")
        if not self.localization_ok:
            return self._refuse("dock", "localization_lost")
        self._start("dock", self._seq_dock(compliant))
        return Result(True)

    def undock(self) -> Result:
        if self.mode != "DOCKED":
            return self._refuse("undock", f"mode {self.mode}")
        self._start("undock", self._seq_undock())
        return Result(True)

    def open_cabinet(self) -> Result:
        if self.mode != "DOCKED":
            return self._refuse("open_cabinet", "dock interlock: cabinet opens only when docked")
        self._start("open_cabinet", self._seq_lid(-self.lid_travel, "DOCKED"))
        return Result(True)

    def close_cabinet(self) -> Result:
        if self.mode not in ("DOCKED", "FAULT"):
            return self._refuse("close_cabinet", f"mode {self.mode}")
        self._start("close_cabinet", self._seq_lid(0.0, self.mode))
        return Result(True)

    def relocalize(self, by="dock fiducial") -> Result:
        """Relocalization (e.g. on the dock fiducial / a site marker): the estimate snaps back to the true pose."""
        self._log("relocalized", by=by, bias_cleared_mm=np.round(self.bias[:2] * 1e3, 1).tolist(),
                  bias_cleared_deg=round(math.degrees(self.bias[2]), 2))
        self.bias = np.zeros(3)
        self.localization_ok = True
        if self.fault in ("localization_lost",):
            self.fault, self.mode = "", "READY"
        return Result(True)

    def reset_fault(self, by) -> Result:
        if self.mode != "FAULT":
            return self._refuse("reset_fault", "no fault")
        if self.cabinet != "closed":
            return self._refuse("reset_fault", "cabinet open")
        self._log("fault_reset", by=by, fault=self.fault)
        self.fault, self.mode = "", "READY"
        return Result(True)

    # ---------------------------------------------------------------- motion
    @staticmethod
    def _wrap(a):
        return (a + math.pi) % (2 * math.pi) - math.pi

    def _set(self, k, v):
        self.tgt[k] = v
        self.art.set_dof_position_targets(np.array([[v]], dtype=np.float32), dof_indices=[self.dof[k]])

    def _command_est(self, est):
        """Drive the physical base so that the ESTIMATED pose becomes est (targets = est - bias)."""
        true = np.array(est) - self.bias
        self._set("x", float(true[0]))
        self._set("y", float(true[1]))
        self._set("yaw", float(true[2]))

    def _gains(self, soft):
        idx = [self.dof["y"], self.dof["yaw"]]
        if soft:
            self.art.set_dof_gains(np.array([[SOFT["y"], SOFT["yaw"]]]), np.array([[SOFT_DAMP["y"], SOFT_DAMP["yaw"]]]),
                                   dof_indices=idx)
        else:
            self.art.set_dof_gains(np.array([[STIFF["y"], STIFF["yaw"]]]), np.array([[DAMP["y"], DAMP["yaw"]]]),
                                   dof_indices=idx)

    def _seq_route(self, pts, speed, reverse=False):
        """Pure pursuit along the polyline; the commanded estimate integrates the unicycle model. Reverse driving is
        pursuit for a virtual robot facing backwards (heading + pi) with the velocity negated."""
        flip = math.pi if reverse else 0.0
        sgn = -1.0 if reverse else 1.0
        est = self.pose_est()
        cmd = est.copy()
        k = 0
        # align first: turn in place toward the first lookahead point (starting a long leg misaligned and steering
        # onto it by pursuit swings the AMR ~0.5 m off the lane - found by the site route test)
        while k < len(pts) - 1 and np.linalg.norm(pts[k] - cmd[:2]) < LOOKAHEAD:
            k += 1
        d = pts[k] - cmd[:2]
        if np.linalg.norm(d) > 0.05:
            h0 = math.atan2(d[1], d[0]) - flip
            while abs(self._wrap(h0 - cmd[2])) > math.radians(1.0):
                cmd[2] += float(np.clip(self._wrap(h0 - cmd[2]), -W_MAX * self.dt, W_MAX * self.dt))
                self._command_est(cmd)
                yield
        moving = True
        while moving:
            if not self.localization_ok:
                self._command_est(self.pose_est())
                self._set_fault("localization_lost", "localization lost in transit: stopped; relocalize")
                return
            if self.cabinet != "closed":
                self._command_est(self.pose_est())
                self._set_fault("cabinet_open_in_transit", "cabinet opened in transit: stopped; close it and evaluate "
                                                           "sample validity")
                return
            p = cmd[:2]
            while k < len(pts) - 1 and np.linalg.norm(pts[k] - p) < LOOKAHEAD:
                k += 1
            goal = pts[k]
            d = goal - p
            dist = float(np.linalg.norm(d))
            last = k == len(pts) - 1
            if last and dist < 0.002:
                break
            alpha = self._wrap(math.atan2(d[1], d[0]) - cmd[2] - flip)
            if abs(alpha) > math.radians(60) or (last and dist < 0.05 and abs(alpha) > math.radians(5)):
                v, w = 0.0, float(np.clip(2.0 * alpha, -W_MAX, W_MAX))     # turn in place
            else:
                v = min(speed, dist / 0.5 + 0.02) if last else speed
                w = float(np.clip(2 * v * math.sin(alpha) / max(LOOKAHEAD, dist), -W_MAX, W_MAX))
            cmd = cmd + np.array([sgn * v * math.cos(cmd[2]), sgn * v * math.sin(cmd[2]), w]) * self.dt
            self._command_est(cmd)
            self.battery -= BATTERY_DRAIN["moving"] * self.dt
            yield
        # final heading: the last segment's direction (the dock approach heads +X); reversed: facing back along it
        h = (math.atan2(*(pts[-1] - pts[-2])[::-1]) + flip) if len(pts) > 1 else cmd[2]
        while abs(self._wrap(h - cmd[2])) > 1e-3:
            cmd[2] += float(np.clip(self._wrap(h - cmd[2]), -W_MAX * self.dt, W_MAX * self.dt))
            self._command_est(cmd)
            yield
        for _ in range(int(0.5 / self.dt)):
            yield
        self.mode = "READY"
        self._log("arrived", estimate=np.round(self.pose_est(), 4).tolist(), true=np.round(self.pose_true(), 4).tolist())

    def _seq_dock(self, compliant):
        self.mode = "DOCKING"
        if compliant:
            self._gains(True)
        est = self.pose_est()
        cmd = est.copy()
        t0 = self.t
        res = None
        while self.t - t0 < 40.0:
            cmd[0] = min(cmd[0] + V_DOCK * self.dt, 0.004)          # press 4 mm beyond the stop
            cmd[1], cmd[2] = 0.0, 0.0
            self._command_est(cmd)
            yield
            res = self.dock_sensors()
            if cmd[0] >= 0.004 and self.t - t0 > 2.0:
                for _ in range(int(1.0 / self.dt)):                  # settle against the stop
                    yield
                res = self.dock_sensors()
                break
        if res and res["ok"]:
            # latch: hold the reached physical pose, drives stiff again
            q = self.pose_true()
            self._set("x", float(q[0]))
            self._set("y", float(q[1]))
            self._set("yaw", float(q[2]))
            self._gains(False)
            for _ in range(int(0.3 / self.dt)):
                yield
            res = self.dock_sensors()
            self.mode = "DOCKED"
            self._write("state:dock_state", "occupied", self.dock_root)
            self._log("docked", residual=res, true_pose=np.round(self.pose_true() * [1e3, 1e3, 57.2958], 2).tolist())
            self.last_dock = {"ok": True, **res}
            return
        self._gains(False)
        self.last_dock = {"ok": False, **(res or {})}
        self._log("dock_misalignment", residual=res)
        # recovery: back out to the approach pose (estimated frame)
        cmd = self.pose_est()
        while cmd[0] > self.approach[0] + 1e-4:
            cmd[0] = max(cmd[0] - V_DOCK * 2 * self.dt, self.approach[0])
            self._command_est(cmd)
            yield
        for _ in range(int(0.5 / self.dt)):
            yield
        self.mode = "READY"                                          # backed out: relocalize and retry
        self._log("backed_out", estimate=np.round(self.pose_est(), 4).tolist())

    def _seq_undock(self):
        if self.cabinet != "closed":
            yield from self._seq_lid(0.0, "DOCKED")
        self.mode = "MOVING"
        self._write("state:dock_state", "free", self.dock_root)
        cmd = self.pose_est()
        cmd[1:] = 0.0
        while cmd[0] > self.approach[0] + 1e-4:
            cmd[0] = max(cmd[0] - V_DOCK * 2 * self.dt, self.approach[0])
            self._command_est(cmd)
            yield
        for _ in range(int(0.5 / self.dt)):
            yield
        self.mode = "READY"
        self._log("undocked")

    def _seq_lid(self, target, end_mode):
        start = self.tgt["lid"]
        n = max(1, int(abs(target - start) / 0.15 / self.dt))
        for i in range(1, n + 1):
            self._set("lid", start + (target - start) * i / n)
            yield
        while abs(self.q["lid"] - target) > 0.0005:
            yield
        self.mode = end_mode
        self._log("cabinet", state=self.cabinet)

    # ---------------------------------------------------------------- loop / outputs
    def update(self, dt=None):
        self.dt = dt or self.dt
        self.t += self.dt
        self.read_sensors()
        if self._job is not None:
            try:
                next(self._job)
            except StopIteration:
                self._job = None
        else:
            self.battery -= BATTERY_DRAIN["idle"] * self.dt
        if self.t >= self._next_trace:
            self._next_trace += 0.5
            e = self.pose_est()
            self.trace.append((round(self.t, 2), round(float(e[0]), 4), round(float(e[1]), 4), round(float(e[2]), 4),
                               self.cabinet, bool(self.carrier_present), round(self.battery, 2), self.localization_ok))
        self._outputs()

    def _outputs(self):
        e = self.pose_est()
        self._write("state:pose", f"map ({e[0]:.3f}, {e[1]:.3f}, {math.degrees(e[2]):.1f} deg)")
        self._write("state:battery_percent", round(self.battery, 1))
        self._write("state:dock_state", "docked" if self.mode == "DOCKED" else ("docking" if self.mode == "DOCKING"
                                                                                else "undocked"))
        self._write("state:cabinet", self.cabinet)
        self._write("state:payload_inventory", list(self.inventory))
        self._write("state:mode", self.mode)
        self._write("state:fault", self.fault)
        for lens, on in (("LensGreen", self.mode in ("READY", "DOCKED")), ("LensAmber", self.mode in ("MOVING", "DOCKING")),
                         ("LensRed", self.mode == "FAULT")):
            self._write("inputs:emissive_intensity", LIGHT_ON if on else 0.0, f"{self.root}/Looks/{lens}/Shader")

    def _write(self, attr, value, path=None):
        key = (path or self.root, attr)
        if self._written.get(key) == value:
            return
        prim = self.stage.GetPrimAtPath(path) if path else self.prim
        a = prim.GetAttribute(attr) if prim else None
        if a:
            a.Set(value)
            self._written[key] = value

    def _log(self, event, **d):
        self.events.append({"t": round(self.t, 3), "event": event, "mode": self.mode, **d})

    def _start(self, cmd, gen, **d):
        self.mode = "MOVING" if cmd in ("navigate", "undock") else ("DOCKING" if cmd == "dock" else self.mode)
        self._job = gen
        self._log(f"{cmd}_accepted", **d)

    def _refuse(self, cmd, reason):
        self._log(f"{cmd}_refused", reason=reason)
        return Result(False, reason)

    def _set_fault(self, fault, detail):
        self.fault, self.mode = fault, "FAULT"
        self._job = None
        self._log("fault", fault=fault, detail=detail)

    def busy(self):
        return self._job is not None

    def save(self, path):
        with open(path, "w") as f:
            json.dump({"component": "R03/H2", "events": self.events, "trace": self.trace}, f, indent=2, default=str)
