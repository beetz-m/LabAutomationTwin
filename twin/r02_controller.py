"""Contract-level controllers for R02 and its tool changer (Cell 01 sdt/components/R02_RailMounted_UR5e.yaml and
ToolChanger_Magazine.yaml), on top of twin/r02_rig.py.

R02Controller
  home_rail()                          rail homed before any task (fault rail_not_homed otherwise)
  position_for_station(station, p, R)  rail + arm configuration servicing a station frame: soft limits, reach (IK),
                                       execution; evidence: station binding, rail pose, robot pose
ToolChanger (TCM01)
  change_tool(tool_id, task_contamination)   dock occupied (ray) -> approach -> coupler alignment within tolerance ->
                                       lock -> lock verified (attachment) -> tool ID read through the coupler ->
                                       utilities -> lift-out with the tool following -> dock reads empty
  store_tool()                         dock empty -> lower into the dock -> unlock -> tool at rest in the dock
  faults: wrong_tool (ID read != requested: unlock, leave it, do not execute), partial_lock (alignment out of
  tolerance or lock not verified: abort before leaving the magazine), contamination_incompatible_tool.
  must_not_assume: a tool stored in the expected dock is the expected tool; reaching a pose means it locked.

Sensing is simulated state only: physics poses of the wrist and tool bodies, the surface-gripper (coupler) state,
PhysX raycasts for dock occupancy, and the tool body's tool:id attribute read only once the coupler holds it.
"""

from __future__ import annotations

import json
import math

import numpy as np
from pxr import UsdGeom

from twin.r02_rig import COUPLER_FACE, MAX_LOCK_GAP, R02, RAIL_SOFT, TCM, tool_prims

ALIGN_LATERAL_MM, ALIGN_ANGLE_DEG = 1.0, 1.0     # coupler self-centring range assumed for the WMR2063-class proxy
FOLLOW_MM = 1.0                                  # tool must follow the coupler within this after lift-out
LIFT_MARGIN = 0.04                               # m above the dock tines for the tool's lowest point
COMPATIBLE = {"clean": {"clean"}, "liquid_contact": {"clean", "liquid_contact"}}   # task class -> allowed tool classes


def _world(stage, path):
    m = UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(path))
    R = np.array(m.ExtractRotationMatrix()).T          # Gf rows are basis vectors; columns here
    return np.array(m.ExtractTranslation()), R


class _Events:
    def _log(self, event, **d):
        self.events.append({"t": round(self.rig.t, 3), "event": event, **d})

    def _ok(self, cmd, **d):
        self._log(f"{cmd}_ok", **d)
        return True, ""

    def _refuse(self, cmd, reason, fault=None, **d):
        self._log(f"{cmd}_refused", reason=reason, **d)
        if fault:
            self.fault = fault
            self._log("fault", fault=fault, detail=reason)
        return False, reason


class R02Controller(_Events):
    def __init__(self, stage, rig):
        self.stage, self.rig, self.events = stage, rig, []
        self.rail_homed, self.fault = False, ""
        self.prim = stage.GetPrimAtPath(R02)

    def home_rail(self):
        r = self.rig
        q = r.q()
        ok = r.move_joints(np.r_[q[0], r.carry(None, side=-1.0)[1:]]) and r.move_joints(np.r_[0.0, r.carry(None, side=-1.0)[1:]])
        if not ok or abs(r.q()[0]) > 0.0005:
            return self._refuse("home_rail", f"rail did not reach home ({r.q()[0] * 1e3:.2f} mm)", fault="rail_not_homed")
        self.rail_homed = True
        self._write()
        return self._ok("home_rail", rail_m=round(float(r.q()[0]), 5))

    def move_rail(self, x):
        if not self.rail_homed:
            return self._refuse("move_rail", "rail not homed", fault="rail_not_homed")
        if not RAIL_SOFT[0] <= x <= RAIL_SOFT[1]:
            return self._refuse("move_rail", f"{x:.3f} m outside soft limits {RAIL_SOFT}")
        q = self.rig.q()
        ok = self.rig.move_joints(np.r_[x, q[1:]])
        res = abs(self.rig.q()[0] - x)
        self._write()
        if not ok or res > 0.0005:
            return self._refuse("move_rail", f"encoder residual {res * 1e3:.2f} mm")
        return self._ok("move_rail", rail_m=round(x, 4), residual_mm=round(res * 1e3, 3))

    def position_for_station(self, station, p, R, rail=None, side=None):
        if not self.rail_homed:
            return self._refuse("position_for_station", "rail not homed", fault="rail_not_homed", station=station)
        t0 = self.rig.t
        ok = self.rig.go(p, R, rail=rail, side=side)
        tcp, Rt, _ = self.rig.tcp()
        res = float(np.linalg.norm(tcp - p))
        self._write()
        ev = dict(station=station, rail_m=round(float(self.rig.q()[0]), 4), q_deg=np.round(np.degrees(self.rig.q()[1:]), 1).tolist(),
                  tcp_residual_mm=round(res * 1e3, 2), duration_s=round(self.rig.t - t0, 2))
        if not ok or res > 0.001:
            return self._refuse("position_for_station", "not converged", **ev)
        return self._ok("position_for_station", **ev)

    def _write(self):
        for k, v in (("state:rail_position_m", float(self.rig.q()[0])), ("state:rail_homed", self.rail_homed),
                     ("state:active_tool", (self.rig.tool or {}).get("id", "none")), ("state:fault", self.fault)):
            a = self.prim.GetAttribute(k)
            if not a:
                from pxr import Sdf
                a = self.prim.CreateAttribute(k, Sdf.ValueTypeNames.Float if isinstance(v, float) else
                                              Sdf.ValueTypeNames.Bool if isinstance(v, bool) else Sdf.ValueTypeNames.String,
                                              custom=True)
            a.Set(v)


class ToolChanger(_Events):
    def __init__(self, stage, rig, r02):
        from isaacsim.core.experimental.prims import RigidPrim
        from pxr import UsdPhysics
        from omni.physx import get_physx_scene_query_interface
        self.stage, self.rig, self.r02, self.events, self.fault = stage, rig, r02, [], ""
        self.sq = get_physx_scene_query_interface()
        self.tools = {}
        for tid, prim in tool_prims(stage).items():
            body = prim.GetChild("Body")
            self.tools[tid] = {a: body.GetAttribute(f"tool:{a}").Get() for a in ("type", "contaminationClass", "utilities")}
            self.tools[tid].update(path=str(body.GetPath()), tcp=body.GetAttribute("tool:tcp_mm").Get() / 1000.0,
                                   lift=max(0.10, body.GetAttribute("tool:length_mm").Get() / 1000.0 + LIFT_MARGIN),
                                   rp=RigidPrim(str(body.GetPath())), fingers=None)
            if prim.GetChild("FingerA"):
                self.tools[tid]["fingers"] = {"body": self.tools[tid]["rp"], **{
                    k: (RigidPrim(str(prim.GetChild(f"Finger{k}").GetPath())),
                        UsdPhysics.DriveAPI(stage.GetPrimAtPath(f"{prim.GetPath()}/Joints/Finger{k}Joint"), "linear"))
                    for k in ("A", "B")}}
        self.docks = {tid: _world(stage, f"{TCM}/dock_{tid}") for tid in self.tools}
        self.sensors = {tid: _world(stage, f"{TCM}/Stand/occupancy_{tid}") for tid in self.tools}
        self.home = {}   # tool id -> dock it belongs to (dock_Txx)

    # ---------------------------------------------------------------- sensing
    def dock_occupied(self, dock):
        """Ray from the dock's occupancy sensor along the magazine -Y: hits a docked tool's adapter flange."""
        o, R = self.sensors[dock]
        hit = self.sq.raycast_closest(tuple(map(float, o)), tuple(map(float, -R[:, 1])), 0.06)
        return bool(hit and hit.get("hit") and "/Tools/" in hit.get("collision", ""))

    def tool_face(self, tid):
        """Measured coupling-face pose of a tool (its Body frame)."""
        p, q = self.tools[tid]["rp"].get_world_poses()
        from twin.r01_rig import qmat
        return p.numpy()[0].astype(float), qmat(q.numpy()[0].astype(float))

    def _residual(self, p_t, R_t):
        p_c, R_c, _ = self.rig.coupler_pose()
        d = R_c.T @ (p_t - p_c)
        ang = math.degrees(math.acos(np.clip((np.trace(R_c.T @ R_t) - 1) / 2, -1, 1)))
        return {"lateral_mm": round(float(np.hypot(d[0], d[1])) * 1e3, 3), "gap_mm": round(float(d[2]) * 1e3, 3),
                "angle_deg": round(ang, 3)}

    # ---------------------------------------------------------------- contract actions
    def change_tool(self, tool_id, task_contamination="clean", dock=None, belief_offset=(0.0, 0.0, 0.0)):
        """Acquire tool_id from its dock. belief_offset: injected error of the robot's dock pose belief (tests)."""
        dock = dock or tool_id
        cmd = "change_tool"
        if self.rig.tool is not None:
            return self._refuse(cmd, f"tool {self.rig.tool['id']} still coupled: store it first", tool_id=tool_id)
        if tool_id not in self.tools:
            return self._refuse(cmd, f"unknown tool {tool_id}")
        cls = self.tools[tool_id]["contaminationClass"]
        if cls not in COMPATIBLE.get(task_contamination, set()):
            return self._refuse(cmd, f"{tool_id} is {cls}, task requires {task_contamination}",
                                fault="contamination_incompatible_tool", tool_id=tool_id)
        if not self.dock_occupied(dock):
            return self._refuse(cmd, f"dock {dock} reads empty", tool_id=tool_id)
        p_d, R_d = self.docks[dock]
        p_b = p_d + np.asarray(belief_offset)
        if not self.r02.position_for_station(f"TCM01/dock_{dock}/approach", p_b + [0, 0, 0.10], R_d, side=1.0)[0]:
            return self._refuse(cmd, "dock approach not reached", tool_id=tool_id)
        self.rig.move_to(p_b + [0, 0, 0.0005], R_d, speed=0.02)
        res = self._residual(*self.tool_face(self._tool_in(dock)))
        self._log("coupler_alignment", dock=dock, **res)
        if res["lateral_mm"] > ALIGN_LATERAL_MM or res["angle_deg"] > ALIGN_ANGLE_DEG or res["gap_mm"] > MAX_LOCK_GAP * 1e3:
            self.rig.move_to(p_b + [0, 0, 0.10], R_d, speed=0.05)
            return self._refuse(cmd, f"coupler alignment out of tolerance {res}; lock not attempted",
                                fault="partial_lock", tool_id=tool_id)
        status, gripped = self.rig.coupler_close()
        body = gripped[0] if gripped else None
        if status != "Closed" or body is None:
            self.rig.coupler_open()
            self.rig.move_to(p_b + [0, 0, 0.10], R_d, speed=0.05)
            return self._refuse(cmd, f"lock not verified (coupler {status}, attached {gripped})", fault="partial_lock")
        read_id = self.stage.GetPrimAtPath(body).GetAttribute("tool:id").Get()   # electrical ID via the coupler
        self._log("tool_id_read", expected=tool_id, read=read_id, body=body)
        if read_id != tool_id:
            self.rig.coupler_open()
            self.rig.move_to(p_b + [0, 0, 0.10], R_d, speed=0.05)
            return self._refuse(cmd, f"wrong tool: dock {dock} held {read_id}, expected {tool_id}; unlocked and left "
                                     "in the dock", fault="wrong_tool", tool_id=tool_id, read=read_id)
        t = self.tools[tool_id]
        self.rig.tool = {"id": tool_id, "path": body, "tcp": t["tcp"], "fingers": t["fingers"]}
        p_t, R_t, _ = self.rig.tcp()                                 # TCP now includes the tool
        self.rig.move_to(p_t + [0, 0, t["lift"]], R_t, speed=0.05)  # whole tool clear of the dock tines
        follow = self._residual(*self.tool_face(tool_id))
        utilities = {u: ("connected" if u == "electrical" else "assumed_available") for u in t["utilities"].split(",")}
        if follow["lateral_mm"] > FOLLOW_MM or abs(follow["gap_mm"]) > FOLLOW_MM or self.dock_occupied(dock):
            return self._refuse(cmd, f"tool did not follow the coupler {follow}", fault="partial_lock")
        self.home[tool_id] = dock
        self.r02._write()
        return self._ok(cmd, tool_id=tool_id, dock=dock, lock="verified", id_read=read_id, alignment=res,
                        follow_after_lift=follow, utilities=utilities)

    def store_tool(self):
        cmd = "store_tool"
        if self.rig.tool is None:
            return self._refuse(cmd, "no tool coupled")
        tid = self.rig.tool["id"]
        dock = self.home.get(tid, tid)
        if self.dock_occupied(dock):
            return self._refuse(cmd, f"dock {dock} occupied", tool_id=tid)
        p_d, R_d = self.docks[dock]
        tcp_off = self.rig.tool["tcp"]
        # TCP-based planning: put the coupling face (TCP - tool length along the tool axis) on the dock frame
        p_tcp = p_d + R_d[:, 2] * tcp_off
        lift = self.tools[tid]["lift"]
        if not self.r02.position_for_station(f"TCM01/dock_{dock}/approach", p_tcp + [0, 0, lift], R_d, side=1.0)[0]:
            return self._refuse(cmd, "dock approach not reached", tool_id=tid)
        self.rig.move_to(p_tcp + [0, 0, 0.001], R_d, speed=0.02)
        status = self.rig.coupler_open(wait=0.5)
        self.rig.tool = None
        p_c, R_c, _ = self.rig.coupler_pose()
        self.rig.move_to(p_c + [0, 0, 0.10], R_c, speed=0.05)
        self.rig.step(int(0.5 * 240))
        p_t, R_t = self.tool_face(tid)
        seated = {"offset_mm": np.round((p_t - p_d) * 1e3, 2).tolist(),
                  "angle_deg": round(math.degrees(math.acos(np.clip((np.trace(R_d.T @ R_t) - 1) / 2, -1, 1))), 3)}
        occupied = self.dock_occupied(dock)
        self.r02._write()
        if status != "Open" or not occupied or np.linalg.norm(p_t - p_d) > 0.003:
            return self._refuse(cmd, f"tool not at rest in its dock (coupler {status}, occupied {occupied}, {seated})",
                                tool_id=tid)
        return self._ok(cmd, tool_id=tid, dock=dock, rest=seated)

    def _tool_in(self, dock):
        """Which tool body is physically nearest the dock (for the alignment measurement only, not identity)."""
        p_d, _ = self.docks[dock]
        return min(self.tools, key=lambda t: np.linalg.norm(self.tool_face(t)[0] - p_d))

    def save_events(self, path):
        with open(path, "w") as f:
            json.dump({"component": "TCM01", "events": self.events}, f, indent=2, default=str)


__all__ = ["R02Controller", "ToolChanger", "COUPLER_FACE"]
