"""The motion level of the challenge-rescue plan: every robot leg's motion goals as frames, checked by kinematics.

For each transport leg the Isaac run executed (rsa/out/trail_isaac_nominal.json), the motion phases
(approach, insert, grasp, lift, transit, place, release, retract) get their goal frames in the composed Cell 01 scene:
  seat frames     L10 transfer_station, the R01/R02 handover_frame, L12 plate_nest, L17 plate_load_frame (pose + yaw)
  tool frames     R01: plate_grasp_frame, 171 mm beyond the FR3 flange (twin/r01_rig.TCP_OFF);
                  R02: T01's TCP, 155 mm beyond the coupling face, 16 mm beyond tool0 (assets/r02/build_tooling.py)
  offsets         grasp: TCP 6 mm above the plate bottom; approach: 0.20 m (R01) / 0.15 m (R02) above the grasp;
                  place entry 13 mm (R01) / 2 mm (R02) above the seat; tool pointing down, jaws on the plate's long sides
Each goal is checked offline with the twin's own kinematics (no simulator): R01 by the FR3 IK with the joint-margin and
conditioning thresholds of twin/r01_planner.py and its box collision model of the stations; R02 by the rail + UR5e
URDF IK (twin/kinematics.py) with the rail free and the joint-margin threshold of twin/r02_rig.solve.

    env_cad/bin/python -m rsa.motion_frames     # rsa/out/motion_frames.json
"""

from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
OUT = os.path.join(HERE, "out")

SEATS = {"l10": "/World/Cell01/Stations/L10_Incubator/transfer_station",
         "handovernest": "/World/Cell01/Fixtures/HandoverNest_R01_R02/handover_frame",
         "l12": "/World/Cell01/Stations/L12_LiquidHandler/plate_nest",
         "l17": "/World/Cell01/Stations/L17_BrightFieldImager/plate_load_frame"}
DOCK_T01 = "/World/Cell01/Tooling/AutomaticToolChanger/dock_T01"
ROBOT = {
    "r01": dict(tool_frame="plate_grasp_frame", tcp_beyond_flange_m=0.171, approach_m=0.20, grasp_above_bottom_m=0.006,
                place_entry_m=0.013, insert_speed=0.08, lift_speed=0.10, place_speed=0.08, root="fr3_link0",
                tip="plate_grasp_frame"),
    "r02": dict(tool_frame="t01_tcp", tcp_beyond_flange_m=0.016 + 0.155, approach_m=0.15, grasp_above_bottom_m=0.006,
                place_entry_m=0.002, insert_speed=0.05, lift_speed=0.08, place_speed=0.03, root="rail_base",
                tip="t01_tcp")}
GRIP_Z = 0.006


def seat_frames():
    from pxr import Usd, UsdGeom
    st = Usd.Stage.Open(os.path.join(ROOT, "scenes", "cell01_twin.usda"))
    xc = UsdGeom.XformCache()
    out = {}
    for k, p in list(SEATS.items()) + [("dock_t01", DOCK_T01)]:
        m = xc.GetLocalToWorldTransform(st.GetPrimAtPath(p))
        t = m.ExtractTranslation()
        R = m.ExtractRotationMatrix()
        yaw = math.degrees(math.atan2(R[0][1], R[0][0]))
        out[k] = dict(prim=p, p=[round(float(v), 4) for v in t], yaw_deg=round(yaw, 2))
    return out, st


def legs_from_trail():
    E = json.load(open(os.path.join(OUT, "trail_isaac_nominal.json")))["entries"]
    nodes = {}
    for e in E:
        n = nodes.setdefault(e["designator"], dict(id=e["designator"], parent=e["parent"], cat=e["category"], entries=[]))
        n["entries"].append(e)
    sess = {}
    legs = []
    for n in sorted(nodes.values(), key=lambda n: n["entries"][0]["seq"]):
        if n["cat"] == "run_session":
            cur = next(e["bindings"]["session"] for e in n["entries"] if e["transition"] == "grounded")
            sess[n["id"]] = cur
        if n["cat"] != "transporting":
            continue
        b = next((e.get("bindings") for e in n["entries"] if e["transition"] == "grounded" and e.get("bindings")), {}) or {}
        anc, sid = n, None
        while anc:
            if anc["id"] in sess:
                sid = sess[anc["id"]]
                break
            anc = nodes.get(anc["parent"])
        kids = [m for m in nodes.values() if m["parent"] == n["id"]]
        leaves = []
        for k in sorted(kids, key=lambda m: m["entries"][0]["seq"]):
            for m in sorted([x for x in nodes.values() if x["parent"] == k["id"]] or [k], key=lambda m: m["entries"][0]["seq"]):
                ex = next((e for e in m["entries"] if e["transition"] == "executed"), None)
                if ex and ex["kind"] == "motion":
                    leaves.append(dict(phase=m["cat"], term=ex.get("term"), duration_s=ex.get("duration_s"),
                                       realised_by=next((v["value"] for v in ex.get("evidence") or [] if v["kind"] == "realised_by"), None),
                                       monitors=[dict(name=x["name"], passed=x["passed"], observation=x.get("observation")) for x in ex.get("monitors") or []]))
        legs.append(dict(session=sid, robot=b.get("robot"), src=b.get("source"), dst=b.get("target"), leaves=leaves))
    return legs


def tool_down_R(yaw_deg):
    """Tool +Z down, jaws along the plate's long sides at the seat's yaw (both rigs' convention)."""
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    return np.array([[c, s, 0.0], [s, -c, 0.0], [0.0, 0.0, -1.0]])


def check_r01(goals, stage, layout):
    import reachability_study as rs
    from twin import r01_planner as rp
    obstacles = rp.obstacles_from_stage(stage, layout)
    base = np.array(layout["r01_base"])
    rng = np.random.default_rng(7)
    out = []
    q_prev = rp.READY
    for g in goals:
        p = np.array(g["p"]) - base
        best = None
        for k in range(12):
            q = rs.ik_solve(rp.FR3, p, math.radians(g["yaw_deg"] + 180.0), rng, restarts=2, iters=150, q0=q_prev if k == 0 else None)
            if q is None:
                continue
            sc = (rp.margin(q) >= rp.MARGIN_MIN, rp.sigma_min(q), -np.abs(q - q_prev).sum())
            if best is None or sc > best[0]:
                best = (sc, q)
        if best is None:
            out.append(dict(g, reachable=False))
            continue
        q = best[1]
        held = g["held"]
        coll = rp.collides(q, obstacles, held)
        out.append(dict(g, reachable=True, margin_deg=round(math.degrees(rp.margin(q)), 1),
                        sigma_min=round(float(rp.sigma_min(q)), 3), collision_free=not bool(coll),
                        margin_ok=bool(rp.margin(q) >= rp.MARGIN_MIN),
                        conditioning_ok=bool(rp.sigma_min(q) >= (rp.SIGMA_MIN_NEST if g["at_seat"] else rp.SIGMA_MIN_ABOVE)),
                        q_deg=[round(math.degrees(v), 1) for v in q]))
        q_prev = q
    return out


def check_r02(goals):
    from twin.kinematics import UrdfChain
    RAIL_SOFT = (0.02, 2.58)                     # twin/r02_rig.py (that module needs Isaac's physics schema)
    lay = json.load(open(os.path.join(ROOT, "scenes", "layout_p1.json")))["r02_rail"]
    kin = UrdfChain(os.path.join(ROOT, "assets", "r02", "r02.urdf"), "rail_base", "r02_tool0")
    base = np.array([lay["x0"], lay["y"], 0.0])  # twin/r02_rig.rail_origin()
    tool = np.eye(4)
    tool[2, 3] = ROBOT["r02"]["tcp_beyond_flange_m"]
    rng = np.random.default_rng(11)
    out = []
    for g in goals:
        R = tool_down_R(g["yaw_deg"]) if g["kind"] != "couple" else np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1.0]])
        rail = float(np.clip(g["p"][0] - base[0], *RAIL_SOFT))
        best = None
        for k in range(30):
            q0 = np.array([rail, rng.uniform(-math.pi, math.pi), rng.uniform(-2.0, -0.8), rng.uniform(0.8, 2.4),
                           rng.uniform(-2.5, -0.8), -math.pi / 2, rng.uniform(-math.pi, math.pi)])
            q = kin.ik(np.asarray(g["p"]) - base, R, q0, active=range(7), tool=tool, iters=250)
            if q is None or not (RAIL_SOFT[0] <= q[0] <= RAIL_SOFT[1]):
                continue
            m = kin.margin(q, range(1, 7))
            s = kin.sigma_min(q, range(1, 7), tool)
            sc = (m >= math.radians(15), s)
            if best is None or sc > best[0]:
                best = (sc, q, m, s)
        if best is None:
            out.append(dict(g, reachable=False))
            continue
        _, q, m, s = best
        out.append(dict(g, reachable=True, rail_m=round(float(q[0]), 3), margin_deg=round(math.degrees(m), 1),
                        sigma_min=round(float(s), 3), margin_ok=bool(m >= math.radians(15)), collision_free=None,
                        conditioning_ok=bool(s >= 0.05), q_deg=[round(float(q[0]), 3)] + [round(math.degrees(v), 1) for v in q[1:]]))
    return out


def goals_for_leg(leg, seats):
    r = ROBOT[leg["robot"]]
    s, d = seats[leg["src"]], seats[leg["dst"]]
    up = lambda f, h: [f["p"][0], f["p"][1], round(f["p"][2] + h, 4)]  # noqa: E731
    return [dict(leg=f"{leg['robot']} {leg['src']}->{leg['dst']}", phase="approach", seat=leg["src"], kind="above",
                 p=up(s, GRIP_Z + r["approach_m"]), yaw_deg=s["yaw_deg"], held=False, at_seat=False),
            dict(leg=f"{leg['robot']} {leg['src']}->{leg['dst']}", phase="insert", seat=leg["src"], kind="grasp",
                 p=up(s, GRIP_Z), yaw_deg=s["yaw_deg"], held=False, at_seat=True),
            dict(leg=f"{leg['robot']} {leg['src']}->{leg['dst']}", phase="transit", seat=leg["dst"], kind="above",
                 p=up(d, GRIP_Z + r["approach_m"]), yaw_deg=d["yaw_deg"], held=True, at_seat=False),
            dict(leg=f"{leg['robot']} {leg['src']}->{leg['dst']}", phase="place", seat=leg["dst"], kind="place",
                 p=up(d, GRIP_Z + r["place_entry_m"]), yaw_deg=d["yaw_deg"], held=True, at_seat=True)]


def main(argv):
    seats, stage = seat_frames()
    layout = json.load(open(os.path.join(ROOT, "scenes", "layout_p1.json")))
    legs = legs_from_trail()
    uniq = {}
    for l in legs:
        uniq.setdefault((l["robot"], l["src"], l["dst"]), l)
    goals = {k: goals_for_leg(l, seats) for k, l in uniq.items()}
    checks = []
    for (rob, a, b), gs in goals.items():
        checks += check_r01(gs, stage, layout) if rob == "r01" else check_r02(gs)
    dock = seats["dock_t01"]
    checks += check_r02([dict(leg="r02 tool couple", phase="tool_couple", seat="dock_t01", kind="couple",
                              p=[dock["p"][0], dock["p"][1], round(dock["p"][2] + 0.0, 4)], yaw_deg=0.0, held=False, at_seat=True)])
    out = dict(seats=seats, robots=ROBOT, legs=legs, goals=checks,
               r01_base=layout["r01_base"], r02_rail=layout["r02_rail"])
    json.dump(out, open(os.path.join(OUT, "motion_frames.json"), "w"), indent=1, default=str)
    for c in checks:
        print(f"[frames] {c['leg']:22} {c['phase']:11} {c['seat']:12} p={c['p']} yaw {c['yaw_deg']:7.2f}: "
              f"{'reachable' if c['reachable'] else 'NOT REACHABLE'} margin {c.get('margin_deg')} deg sigma {c.get('sigma_min')} "
              f"collision-free {c.get('collision_free')}")
    print(f"[frames] {len(legs)} legs ({len(uniq)} distinct), {len(checks)} goals, "
          f"{sum(c['reachable'] and c.get('margin_ok') for c in checks)} reachable with joint margin")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
