"""Joint-space transits for R01 between station approach poses, checked against the Cell 01 layout.

The straight-line Cartesian moves of twin/r01_rig.py are fine for approach, insertion and lift, but not for moving
between stations. Through the region above R01's base the IK branch is arbitrary, and a top-down tool yaw that
suits one station can put joint 7 at its limit at the next. This planner picks, for each approach pose, inverse
kinematics solutions with large joint margins (FR3 URDF kinematics, the same as tools/reachability_study.py), and
connects them by straight joint-space segments. Each segment is checked by forward kinematics against the
station bodies, the bench, the supports and the walls:
  * the plate (when held) and the gripper as boxes in the tool frame;
  * the arm as spheres on links 3-8.
When no direct segment is free, a via configuration (tool raised above R01, part of the way round) is inserted.

Pure numpy; obstacles come from scenes/layout_p1.json and the station parts on the composed stage.
Tool convention: the sim's tool_down(psi) is this FK's top-down frame at yaw psi + 180 deg.
"""

from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import reachability_study as rs  # noqa: E402

FR3 = rs.FR3(rs.URDF)
LO, HI = FR3.limits[:, 0], FR3.limits[:, 1]
READY = np.array([0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785])
MARGIN_MIN = math.radians(20.0)   # joint-limit margin required of a planned configuration
# Smallest singular value of the 6x7 Jacobian (m, rad mixed; READY 0.22, the validated H4 entry pose 0.18). The rig's
# damped-least-squares IK (damping 0.02) left 1-2 mm steady errors and failed its at-rest convergence at 0.06-0.08
# (first episode run, 2026-10-15). The best solutions in layout P1 reach 0.12-0.14 at the approach poses and
# 0.17-0.19 at the nests (the READY-like family: q1 ~ azimuth, q3 ~ q5 ~ 0); candidates are ranked by it.
SIGMA_MIN_ABOVE, SIGMA_MIN_NEST = 0.10, 0.15
CLEAR = 0.02                      # m, clearance added to every obstacle for plate / gripper points
LINK_R = 0.075                    # m, sphere radius for arm links
PLATE = (0.0639, 0.0427, -0.0085, 0.006)    # half length, half width, top / bottom z in the tool frame (z down)
GRIPPER = (0.035, 0.055, -0.171, -0.01)     # half x, half y, z range (flange .. near the TCP) in the tool frame


def frames(q):
    """World-free FK: origins of the revolute joints' child frames, the flange, and the tool pose (base frame)."""
    T, k, pts = np.eye(4), 0, []
    for To, typ, axis, _ in FR3.chain:
        T = T @ To
        if typ == "revolute":
            T = T @ rs.rot_axis(axis, q[k])
            k += 1
        pts.append(T[:3, 3].copy())
    return pts, T @ FR3.tool


def margin(q):
    return float(np.minimum(q - LO, HI - q).min())


def sigma_min(q):
    """Smallest singular value of the tool Jacobian (numerical, base frame)."""
    T = FR3.fk(q)
    J = np.zeros((6, 7))
    for k in range(7):
        dq = np.zeros(7)
        dq[k] = 1e-6
        T2 = FR3.fk(q + dq)
        J[:3, k] = (T2[:3, 3] - T[:3, 3]) / 1e-6
        Rd = T2[:3, :3] @ T[:3, :3].T
        J[3:, k] = np.array([Rd[2, 1] - Rd[1, 2], Rd[0, 2] - Rd[2, 0], Rd[1, 0] - Rd[0, 1]]) / 2e-6
    return float(np.linalg.svd(J, compute_uv=False)[-1])


class Box:
    """Obstacle: plan-view rectangle (centre, half sizes, yaw) between z0 and z1."""
    def __init__(self, name, cx, cy, hx, hy, yaw_deg, z0, z1):
        self.name, self.c, self.h, self.z = name, np.array([cx, cy]), np.array([hx, hy]), (z0, z1)
        c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
        self.Rt = np.array([[c, s], [-s, c]])

    def hits(self, p, r):
        d = np.abs(self.Rt @ (p[:, :2] - self.c).T).T
        return np.any(np.all(d <= self.h + r, axis=1) & (p[:, 2] >= self.z[0] - r) & (p[:, 2] <= self.z[1] + r))


def obstacles_from_stage(stage, layout):
    """Boxes in the robot base frame, from the composed stage:
      * each station's housing (the Body link's geometry without its stack light) and its stack light, as boxes
        in the station frame, from the floor up (the supports are covered by the housing footprint + CLEAR);
      * H4's open-door swing zone (tools/layout_p1.py) up to the housing top;
      * the central bench and the west / north walls;
      * the docked R03 AMR's cabinet (H2 fixture body + the lid's open travel), whether or not the AMR is docked.
    Presented trays are not obstacles: they are the targets."""
    from pxr import Gf, Usd, UsdGeom
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render"])
    base = np.array(layout["r01_base"])
    out = []

    def add(name, origin, yaw, r, z0, z1):
        x0, x1, y0, y1 = r
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        lx, ly = (x0 + x1) / 2, (y0 + y1) / 2
        out.append(Box(name, origin[0] + c * lx - s * ly - base[0], origin[1] + s * lx + c * ly - base[1],
                       (x1 - x0) / 2, (y1 - y0) / 2, yaw, z0 - base[2], z1 - base[2]))

    for n, st in layout["stations"].items():
        root = stage.GetPrimAtPath(st["prim"])
        parts = {"housing": Gf.Range3d(), "light": Gf.Range3d()}
        for p in Usd.PrimRange(stage.GetPrimAtPath(st["prim"] + "/Body")):
            if p.IsA(UsdGeom.Gprim):
                key = "light" if "StatusLight" in p.GetPath().pathString or "StackLight" in p.GetName() else "housing"
                parts[key].UnionWith(bc.ComputeRelativeBound(p, root).ComputeAlignedRange())
        for key, r in parts.items():
            if r.IsEmpty():
                continue
            lo, hi = r.GetMin(), r.GetMax()
            z0 = st["origin"][2] if key == "light" else 0.0
            add(f"{n}_{key}", st["origin"], st["yaw_deg"], (lo[0], hi[0], lo[1], hi[1]), z0, st["origin"][2] + hi[2])
        if n == "H4":
            top = st["origin"][2] + parts["housing"].GetMax()[2]
            add("H4_open_door", st["origin"], st["yaw_deg"], (-0.20, -0.12, -0.40, -0.13), st["origin"][2], top)
    out.append(Box("bench", 0.10 - base[0], 0.30 - base[1], 1.325, 0.375, 0.0, -base[2], 0.92 - base[2]))
    h2 = layout.get("fixtures", {}).get("H2")
    if h2:   # the docked R03's sealed cabinet (up to 1.0 m; its lid slides back over the rear): kept as an obstacle
        x0, x1, y0, y1 = h2["footprint"]     # whether or not the AMR is docked (conservative)
        add("R03_cabinet_docked", h2["origin"], h2["yaw_deg"], (x0 - 0.35, x1, y0, y1), 0.0, 1.0)
    for n, (x0, x1, y0, y1) in {"wall_W": (-3.3, -3.0, -2.5, 2.5), "wall_N": (-3.3, 3.3, 2.25, 2.5)}.items():
        out.append(Box(n, (x0 + x1) / 2 - base[0], (y0 + y1) / 2 - base[1], (x1 - x0) / 2, (y1 - y0) / 2, 0.0,
                       -base[2], 3.0))
    return out


def _box_pts(T, b):
    hx, hy, z0, z1 = b
    loc = np.array([[sx * hx, sy * hy, z] for sx in (-1, 1) for sy in (-1, 1) for z in (z0, (z0 + z1) / 2, z1)])
    return (T[:3, :3] @ loc.T).T + T[:3, 3]


def collides(q, obstacles, held):
    pts, T = frames(q)
    links = [pts[k] for k in range(3, len(pts))]
    links += [(a + b) / 2 for a, b in zip(links[:-1], links[1:])]
    links = np.array(links)
    tool = _box_pts(T, GRIPPER)
    if held:
        tool = np.vstack([tool, _box_pts(T, PLATE)])
    for ob in obstacles:
        if ob.hits(links, LINK_R) or ob.hits(tool, CLEAR):
            return ob.name
    return None


def describe(obstacles):
    return {o.name: {"centre": np.round(o.c, 3).tolist(), "half": np.round(o.h, 3).tolist(),
                     "z": [round(v, 3) for v in o.z]} for o in obstacles}


def segment_free(qa, qb, obstacles, held, step_deg=1.0):
    n = max(2, int(math.degrees(np.abs(qb - qa).max()) / step_deg) + 1)
    for a in np.linspace(0, 1, n):
        hit = collides(qa + (qb - qa) * a, obstacles, held)
        if hit:
            return False, hit
    return True, None


def ik_candidates(p_base, psi_deg, seeds, rng, n=60, p_low=None):
    """IK solutions for a top-down tool at p_base (base frame) with sim tool yaw psi_deg, with joint margin and
    conditioning; with p_low (the nest pose below), the solution continued down to p_low must qualify too."""
    sols = []
    for k in range(n):
        q0 = seeds[k] if k < len(seeds) else None
        q = rs.ik_solve(FR3, np.asarray(p_base, float), math.radians(psi_deg + 180.0), rng, restarts=1, iters=150, q0=q0)
        if q is None or margin(q) < MARGIN_MIN or sigma_min(q) < SIGMA_MIN_ABOVE or \
                any(np.abs(q - s).max() <= math.radians(5) for s in sols):
            continue
        if p_low is not None:
            ql = rs.ik_solve(FR3, np.asarray(p_low, float), math.radians(psi_deg + 180.0), rng, restarts=1, iters=150,
                             q0=q)
            if ql is None or np.abs(ql - q).max() > math.radians(60) or margin(ql) < math.radians(15) or \
                    sigma_min(ql) < SIGMA_MIN_NEST:
                continue
        sols.append(q)
    sols.sort(key=lambda q: -sigma_min(q))
    return sols


def plan(q_start, p_goal, psi_goal, obstacles, held=True, seed=0, posture=None, p_low=None):
    """Joint waypoints from q_start to a configuration at p_goal (base frame) with tool yaw psi_goal.

    Prefers the best-conditioned goal configuration that a free direct segment reaches.
    Returns (waypoints, info)."""
    rng = np.random.default_rng(seed)
    q_start = np.asarray(q_start, float)
    ref = q_start if posture is None else np.asarray(posture, float)
    goals = ik_candidates(p_goal, psi_goal, [q_start, ref, READY], rng, p_low=p_low)  # best conditioned first
    goals = [q for q in goals if not collides(q, obstacles, held)]
    tried = []
    for qg in goals[:12]:
        ok, hit = segment_free(q_start, qg, obstacles, held)
        if ok:
            return [q_start, qg], {"via": None, "goal_margin_deg": round(math.degrees(margin(qg)), 1),
                                   "goal_sigma_min": round(sigma_min(qg), 3)}
        tried.append(hit)
    # via: tool raised 0.15 m above the start/goal mean height, on the way round, at a smaller radius
    _, Ts = frames(q_start)
    ps = Ts[:3, 3]
    az0, az1 = math.atan2(ps[1], ps[0]), math.atan2(p_goal[1], p_goal[0])
    for frac in (0.5, 0.33, 0.67):
        for rad in (0.42, 0.50, 0.35):
            az = az0 + (az1 - az0) * frac
            pv = np.array([rad * math.cos(az), rad * math.sin(az), max(ps[2], p_goal[2]) + 0.15])
            for qv in ik_candidates(pv, psi_goal, [q_start], rng, n=12):
                if collides(qv, obstacles, held) or not segment_free(q_start, qv, obstacles, held)[0]:
                    continue
                for qg in goals[:12]:
                    if segment_free(qv, qg, obstacles, held)[0]:
                        return [q_start, qv, qg], {"via": np.round(pv, 3).tolist(),
                                                    "goal_margin_deg": round(math.degrees(margin(qg)), 1),
                                                    "goal_sigma_min": round(sigma_min(qg), 3)}
    return None, {"blocked_by": tried, "goals": len(goals)}


if __name__ == "__main__":  # offline check of the episode transits (env_cad has no Isaac; uses usd-core)
    from pxr import Usd
    lay = json.load(open(os.path.join(ROOT, "scenes/layout_p1.json")))
    stage = Usd.Stage.Open(os.path.join(ROOT, "scenes/cell01_twin.usda"))
    obs = obstacles_from_stage(stage, lay)
    for k, v in describe(obs).items():
        print(f"  {k:14s} {v}")
    base = np.array(lay["r01_base"])
    above = {n: (np.array(s["nest"]) - base + [0, 0, 0.206], s["yaw_deg"]) for n, s in lay["stations"].items()}
    q = READY.copy()
    for a, b, held in (("READY", "L10", False), ("L10", "L09", True), ("L09", "L10", False), ("L10", "H4", True)):
        wps, info = plan(q, *above[b], obs, held=held, p_low=above[b][0] - [0, 0, 0.20])
        print(f"{a:5s} -> {b:3s} held={held}: {'OK' if wps else 'NO PATH'} {info}")
        if wps:
            print("      " + " | ".join(str(np.round(np.degrees(w), 1).tolist()) for w in wps[1:]))
            q = wps[-1]
