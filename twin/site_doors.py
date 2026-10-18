"""Doors, the Cell 01 door interlock and the AMR-portal light curtain of the lab twin (runs on physics steps).

  Door          an articulated door (assets/cell01_fitout enclosure doors: fixed frame -> revolute hinge -> leaf;
                assets/site storage sliding door: fixed frame -> prismatic -> leaf). open()/close() set the drive
                target; state() is measured from the joint (closed within 1 deg / 3 mm), never from the command.
  Interlock     Cell 01 safe-motion permission: every enclosure door closed and no unmuted light-curtain break
                (spec 4.1: doors linked to interlock state). Robots may move only while ok().
  LightCurtain  beams between the two columns of the AMR portal; muting sensors in front of and behind the curtain.
                A break while a muting sensor sees R03 is a muted passage (logged); any other break latches a
                protective stop until reset() with the curtain clear.

The muting accepts only R03's own colliders (identity-aware muting: the twin knows what broke the beam; a physical
muting arrangement would use sensor timing). Twin-level model; no safety rating is implied.
"""

import math

import carb
import numpy as np
from isaacsim.core.experimental.prims import Articulation
from omni.physx import get_physx_scene_query_interface
from pxr import Sdf, UsdPhysics

ENC = "/World/Cell01/Architecture/Enclosure_E01"
CELL_DOORS = ("D1_Front", "D2_RearWest", "D3_RearEast")
PORTAL = dict(x0=0.58 + 0.045 + 0.02, x1=1.72 - 0.045 - 0.02, y=-2.275, z=(0.20, 0.45, 0.70, 0.95, 1.20),
              mute_dy=(-0.22, 0.22), mute_z=0.30)


class Door:
    def __init__(self, stage, path):
        self.stage, self.path = stage, path
        self.prim = stage.GetPrimAtPath(path)
        self.art = Articulation(path)
        joint = next(p for p in _descendants(self.prim)
                     if p.IsA(UsdPhysics.RevoluteJoint) or p.IsA(UsdPhysics.PrismaticJoint))
        self.revolute = joint.IsA(UsdPhysics.RevoluteJoint)
        lo = joint.GetAttribute("physics:lowerLimit").Get()
        hi = joint.GetAttribute("physics:upperLimit").Get()
        far = lo if abs(lo) > abs(hi) else hi
        self.open_target = (math.radians(far) * 0.9) if self.revolute else far * 0.98
        self.tol = math.radians(1.0) if self.revolute else 0.003
        self.id = self.prim.GetAttribute("sdt:doorId").Get() or path.split("/")[-1]
        self.events = []
        self._last = None

    def position(self):
        return float(self.art.get_dof_positions().numpy()[0][0])

    def open(self):
        self.art.set_dof_position_targets(np.array([[self.open_target]], dtype=np.float32))

    def close(self):
        self.art.set_dof_position_targets(np.array([[0.0]], dtype=np.float32))

    def state(self):
        q = self.position()
        if abs(q) < self.tol:
            return "closed"
        if abs(q - self.open_target) < 5 * self.tol:
            return "open"
        return "moving"

    def update(self, t):
        s = self.state()
        if s != self._last:
            self.events.append((round(t, 3), self.id, s))
            self.prim.GetAttribute("sdt:doorState").Set("closed_locked" if s == "closed" and self.revolute else s)
            self._last = s
        return s


def _descendants(prim):
    stack = list(prim.GetChildren())
    while stack:
        p = stack.pop()
        yield p
        stack.extend(p.GetChildren())


class LightCurtain:
    def __init__(self, stage, amr_root, portal=PORTAL):
        self.stage, self.amr_root, self.p = stage, amr_root, portal
        self.sq = get_physx_scene_query_interface()
        self.broken = False
        self.muted = False
        self.protective_stop = False
        self.passages = []          # (t_start, t_end) muted AMR passages
        self.events = []
        self._pass_t0 = None

    def _hits(self, origin, direction, dist):
        hits = []

        def report(h):
            hits.append(h.collision)
            return True

        self.sq.raycast_all(carb.Float3(*map(float, origin)), carb.Float3(*map(float, direction)), float(dist), report)
        return hits

    def update(self, t):
        p = self.p
        L = p["x1"] - p["x0"]
        beam = [h for z in p["z"] for h in self._hits((p["x0"], p["y"], z), (1, 0, 0), L)]
        mute = [h for dy in p["mute_dy"] for h in self._hits((p["x0"], p["y"] + dy, p["mute_z"]), (1, 0, 0), L)]
        self.broken = bool(beam)
        amr_mute = any(h.startswith(self.amr_root + "/") for h in mute)
        only_amr = all(h.startswith(self.amr_root + "/") for h in beam)
        if self.broken and amr_mute and only_amr:
            if not self.muted:
                self.events.append((round(t, 3), "muted_passage_start"))
                self._pass_t0 = t
            self.muted = True
        elif self.broken:
            if not self.protective_stop:
                self.events.append((round(t, 3), "protective_stop", sorted(set(beam))[:3]))
            self.protective_stop = True
        else:
            if self.muted:
                self.events.append((round(t, 3), "muted_passage_end"))
                self.passages.append((round(self._pass_t0, 3), round(t, 3)))
            self.muted = False
        return self.protective_stop

    def reset(self, t):
        if self.broken:
            return False
        self.protective_stop = False
        self.events.append((round(t, 3), "reset"))
        return True


class Interlock:
    def __init__(self, stage, curtain=None, enclosure=ENC):
        self.doors = {d: Door(stage, f"{enclosure}/Doors/{d}") for d in CELL_DOORS}
        self.curtain = curtain
        self.prim = stage.GetPrimAtPath(enclosure)
        if not self.prim.GetAttribute("state:safe_motion"):
            self.prim.CreateAttribute("state:safe_motion", Sdf.ValueTypeNames.Bool, custom=True)
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        for d in self.doors.values():
            d.update(self.t)
        if self.curtain is not None:
            self.curtain.update(self.t)
        self.prim.GetAttribute("state:safe_motion").Set(self.ok())

    def ok(self):
        doors_closed = all(d.state() == "closed" for d in self.doors.values())
        return doors_closed and not (self.curtain is not None and self.curtain.protective_stop)

    def why_not(self):
        out = [f"door {k} {d.state()}" for k, d in self.doors.items() if d.state() != "closed"]
        if self.curtain is not None and self.curtain.protective_stop:
            out.append("light curtain protective stop")
        return out


def amr_map_from_world(x, y, yaw_deg, map_origin=(-1.415, -0.28)):
    """R03 map frame (= H2 docked pose, yaw 180 in the world) from world x, y, heading (deg)."""
    return (-(x - map_origin[0]), -(y - map_origin[1]), math.radians(yaw_deg - 180.0))


def world_path_to_map(pts):
    return [amr_map_from_world(x, y, 0.0)[:2] for (x, y) in pts]

