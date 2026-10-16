"""Cell 01 layout proposal P1 ('R01 cluster'), adopted by the user on 2026-10-15: placements + checks.

Places each station so its presented transfer nest sits at a P1 site and faces R01, then checks, in plan view:
  * footprints, presented trays and service-door / hinged-door swing zones stay inside the cell walls, off the
    central bench, out of R01's pedestal + base clearance circle, out of the AMR front lane, and clear of each
    other;
  * R01 (FR3, real URDF kinematics) can serve every nest top-down at the nest and at its 0.20 m approach point
    (tools/reachability_study.py criterion).
Writes scenes/layout_p1.json (consumed by tools/compose_cell01_overlay.py) and renders/cell01_layout_p1.png.
Run: env_cad/bin/python tools/layout_p1.py
"""

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
import reachability_study as rs  # noqa: E402

R01 = np.array([-1.55, 0.35, 0.72])           # P1: R01 base_link (moved from (-1.65, -0.10))
PEDESTAL_R, ARM_CLEAR_R = 0.22, 0.28
CELL = (-3.0, 3.0, -2.25, 2.25)
BENCH = (-1.225, 1.425, -0.075, 0.675)         # central automation bench worktop (Cell 01 USD)
AMR_LANE_Y = -0.80                              # keep stations north of the front logistics lane
NEST_Z = 0.972                                  # transfer nest seat height for all R01 stations

# local geometry (m): body = plan bbox of the built asset, presented nest y, seat height above the device base, keep-out zones
DEVICES = {
    "H4": dict(prim="/World/Cell01/Stations/H4_Quarantine", body=(-0.15, 0.178, -0.169, 0.142), nest_y=-0.216, seat=0.072,
               zones={"tray": (-0.112, 0.112, -0.278, -0.13), "door_swing": (-0.20, -0.12, -0.40, -0.13)}),
    "L09": dict(prim="/World/Cell01/Stations/L09_PlateHotel", body=(-0.20, 0.218, -0.264, 0.26), nest_y=-0.35, seat=0.072,
                zones={"tray": (-0.112, 0.112, -0.412, -0.26), "service_door": (0.20, 0.36, -0.10, 0.05)}),
    "L10": dict(prim="/World/Cell01/Stations/L10_Incubator", body=(-0.37, 0.388, -0.432, 0.455), nest_y=-0.515, seat=0.200,
                zones={"tray": (-0.112, 0.112, -0.577, -0.425), "service_door": (0.37, 0.62, -0.27, -0.03)}),
}
# Robot approach direction in the device frame, measured from local -Y toward +X. H4 keeps the hand-off geometry
# validated by scripts/test_h4_robot.py on the bench and in the first Cell 01 placement (R01 at (0.30, -0.62) in
# the H4 frame, i.e. 36.6 deg toward the side away from the door hinge): head-on, the wrist grazed the open door's
# edge during compliant insertion (43 mm lateral transient, 2026-10-15 P1 smoke run).
APPROACH_DEG = {"H4": math.degrees(math.atan2(0.30, 0.62 - 0.216)), "L09": 0.0, "L10": 0.0}
# P1 sites (presented nest centres) and support kinds; tuned so every check below passes
SITES = {
    "L10": dict(nest=(-1.95, 0.80), support="plinth"),
    "L09": dict(nest=(-1.38, 0.90), support="side_table"),
    "H4": dict(nest=(-2.02, 0.05), support="side_table"),
}
# R02 and its tool magazine (amendment to P1, 2026-10-15: R02 built). The rail is part of P1 (D004 travel, shifted
# west); the magazine TCM01 (assets/r02/build_tooling.py) stands north of the rail, docks open toward it.
RAIL = dict(x0=-0.85, x1=1.75, y=0.78, top=0.965)
FIXTURES = {
    "TCM01": dict(prim="/World/Cell01/Tooling/AutomaticToolChanger", origin=(0.30, 1.20, 0.0), yaw_deg=0.0,
                  body=(-0.41, 0.41, -0.07, 0.24), dock_pitch=0.15, dock_z=1.12),
    # passive R01/R02 handover nest on the bench worktop (assets/hn/build_hn.py), seat at 0.96 m
    "HN": dict(prim="/World/Cell01/Fixtures/HandoverNest_R01_R02", origin=(-1.05, 0.55, 0.92), yaw_deg=0.0,
               body=(-0.112, 0.112, -0.062, 0.062), on_bench=True),
    # H2 dock + the docked R03 AMR (assets/r03): the AMR docks heading west along y = -0.28; its carrier nest sits 60 mm
    # off-centre toward R01, so the carrier seat is at (-1.45, -0.22), where R01's planner finds well-conditioned
    # approaches (at (-1.40, -0.28) sigma_min was 0.089). The low chassis passes under the bench edge (the cabinet
    # stays 15 mm south of it). Docking north (the first idea) put the dock into R01's pedestal and the cabinet into
    # the bench.
    "H2": dict(prim="/World/Cell01/Stations/H2_AMR_Dock", origin=(-1.415, -0.28, 0.0), yaw_deg=180.0,
               body=(-0.25, 0.15, -0.19, 0.19), on_bench=True,             # the docked AMR's tall cabinet
               low_zones={"chassis": (-0.445, 0.445, -0.29, 0.29),          # AMR chassis: below 0.36 m
                          "dock": (0.20, 0.545, -0.38, 0.38)}),             # V-guides, stop, tower: below 0.55 m
}
# Stations served by R02 (top-down with T01 from the rail). L17 keeps its Cell 01 location (1.65, 1.55), front toward
# the rail; its XY stage presents the plate 0.33 m in front of the station origin (assets/l17/build_l17.py).
R02_DEVICES = {
    "L17": dict(prim="/World/Cell01/Stations/L17_BrightFieldImager", origin=(1.65, 1.55), yaw_deg=0.0,
                body=(-0.22, 0.22, -0.25, 0.25), nest_y=-0.330, seat=0.200, support="plinth",
                zones={"stage": (-0.10, 0.18, -0.39, -0.25)}),
    # L12 liquid handler (assets/l12/build_l12.py) on the central bench at its Cell 01 location; plate nest at local
    # (0, 0.09), seat 52 mm above the worktop (0.972 m); the gantry parks at the west end, clear of R02's approach
    "L12": dict(prim="/World/Cell01/Stations/L12_LiquidHandler", origin=(0.15, 0.25), yaw_deg=0.0,
                body=(-0.46, 0.46, -0.23, 0.23), nest_y=0.09, seat=0.052, support="bench", on_bench=True, zones={},
                base_z=0.92),
    # L21 QC bench (assets/l21/build_l21.py), moved from (2.25, 1.20) to clear L17 and bring its nests and tool datum
    # within R02's comfortable reach; reference nest at local (-0.125, 0), QC nest (+0.125, 0), datum (-0.125, 0.17)
    "L21": dict(prim="/World/Cell01/Stations/L21_QC_Calibration", origin=(2.20, 1.07), yaw_deg=0.0,
                body=(-0.25, 0.25, -0.08, 0.27), nest_y=0.0, nest_x=-0.125, seat=0.072, support="side_table", zones={},
                extra_targets={"L21_qc_nest": (0.125, 0.0, 0.072), "L21_tool_datum": (-0.125, 0.17, 0.120 + 0.008)}),
}
EXTRA_SITES = {  # frames only for now (no device asset yet)
    "AMR_dock_carrier": (-1.45, -0.22),   # R03 carrier seat docked in H2 (from (-1.40, -0.12): see FIXTURES H2)
    "handover_nest_R01_R02": (-1.05, 0.55),
}


def yaw_facing_r01(nest_xy):
    u = np.array(nest_xy) - R01[:2]
    u /= np.linalg.norm(u)
    return math.degrees(math.atan2(-u[0], u[1]))    # device +Y points away from R01, robot side (-Y) faces R01


def to_world(local_xy, origin, yaw_deg):
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    x, y = local_xy
    return np.array([origin[0] + c * x - s * y, origin[1] + s * x + c * y])


def rect_poly(r, origin, yaw):
    x0, x1, y0, y1 = r
    return np.array([to_world(p, origin, yaw) for p in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))])


def sat_overlap(a, b, eps=0.005):
    """Separating-axis test for two convex polygons (plan view), with a small clearance."""
    for poly in (a, b):
        for i in range(len(poly)):
            e = poly[(i + 1) % len(poly)] - poly[i]
            n = np.array([-e[1], e[0]]) / np.linalg.norm(e)
            pa, pb = a @ n, b @ n
            if pa.max() < pb.min() + eps or pb.max() < pa.min() + eps:
                return False
    return True


def cross2(a, b):
    return a[0] * b[1] - a[1] * b[0]


def circle_hits(poly, c, r):
    if all(cross2(poly[(i + 1) % 4] - poly[i], c - poly[i]) >= 0 for i in range(4)) or \
       all(cross2(poly[(i + 1) % 4] - poly[i], c - poly[i]) <= 0 for i in range(4)):
        return True
    for i in range(4):
        a, b = poly[i], poly[(i + 1) % 4]
        t = np.clip(np.dot(c - a, b - a) / np.dot(b - a, b - a), 0, 1)
        if np.linalg.norm(a + t * (b - a) - c) < r:
            return True
    return False


def main():
    rng = np.random.default_rng(0)
    fr3 = rs.FR3(rs.URDF)
    place, shapes, problems = {}, [], []
    for name, site in SITES.items():
        d = DEVICES[name]
        yaw = yaw_facing_r01(site["nest"]) - APPROACH_DEG[name]
        origin = np.array(site["nest"]) + (to_world((0.0, -d["nest_y"]), (0, 0), yaw))
        base_z = NEST_Z - d["seat"]
        place[name] = dict(prim=d["prim"], origin=[round(float(origin[0]), 4), round(float(origin[1]), 4), round(base_z, 4)],
                           yaw_deg=round(yaw, 2), approach_deg=round(APPROACH_DEG[name], 2), support=site["support"], support_height=round(base_z, 4),
                           nest=[*site["nest"], NEST_Z], footprint=list(d["body"]))
        shapes.append((name, "body", rect_poly(d["body"], origin, yaw)))
        for zn, r in d["zones"].items():
            shapes.append((name, zn, rect_poly(r, origin, yaw)))
    for name, d in R02_DEVICES.items():
        nest = to_world((d.get("nest_x", 0.0), d["nest_y"]), d["origin"], d["yaw_deg"])
        base_z = d.get("base_z", NEST_Z - d["seat"])
        place[name] = dict(prim=d["prim"], origin=[*d["origin"], round(base_z, 4)], yaw_deg=d["yaw_deg"], approach_deg=0.0,
                           support=d["support"], support_height=round(base_z, 4),
                           nest=[round(float(nest[0]), 4), round(float(nest[1]), 4), NEST_Z], footprint=list(d["body"]),
                           served_by="R02")
        shapes.append((name, "body", rect_poly(d["body"], d["origin"], d["yaw_deg"])))
        for zn, r in d["zones"].items():
            shapes.append((name, zn, rect_poly(r, d["origin"], d["yaw_deg"])))
    for name, f in FIXTURES.items():
        shapes.append((name, "body", rect_poly(f["body"], f["origin"], f["yaw_deg"])))
        for zn, r in f.get("low_zones", {}).items():   # low parts (< 0.6 m): no conflict with R01's arm (>= 0.72 m)
            shapes.append((name, f"low_{zn}", rect_poly(r, f["origin"], f["yaw_deg"])))   # or with elevated swings
    rail = np.array([(RAIL["x0"] - 0.25, RAIL["y"] - 0.06), (RAIL["x1"] + 0.25, RAIL["y"] - 0.06),
                     (RAIL["x1"] + 0.25, RAIL["y"] + 0.06), (RAIL["x0"] - 0.25, RAIL["y"] + 0.06)])
    shapes.append(("R02", "rail", rail))
    x0, x1, y0, y1 = CELL
    bench = np.array([(BENCH[0], BENCH[2]), (BENCH[1], BENCH[2]), (BENCH[1], BENCH[3]), (BENCH[0], BENCH[3])])
    for name, part, poly in shapes:
        if poly[:, 0].min() < x0 + 0.03 or poly[:, 0].max() > x1 - 0.03 or poly[:, 1].min() < y0 + 0.03 or \
           poly[:, 1].max() > y1 - 0.03:
            problems.append(f"{name}/{part} outside the cell walls")
        on_bench = FIXTURES.get(name, {}).get("on_bench") or R02_DEVICES.get(name, {}).get("on_bench")
        if part in ("body", "service_door") and name != "R02" and not on_bench and sat_overlap(poly, bench):
            problems.append(f"{name}/{part} overlaps the central bench")
        if circle_hits(poly, R01[:2], ARM_CLEAR_R if part == "body" else PEDESTAL_R):
            problems.append(f"{name}/{part} intrudes on R01's pedestal/base clearance")
        if poly[:, 1].min() < AMR_LANE_Y:
            problems.append(f"{name}/{part} enters the AMR front lane")
    elevated = ("tray", "door_swing", "service_door", "stage")      # swing / presentation zones at >= 0.77 m
    for i, (na, pa, a) in enumerate(shapes):
        for nb, pb, b in shapes[i + 1:]:
            if (pa.startswith("low_") and pb in elevated) or (pb.startswith("low_") and pa in elevated):
                continue
            if na != nb and sat_overlap(a, b):
                problems.append(f"{na}/{pa} overlaps {nb}/{pb}")
    reach = {}
    for name, p in place.items():
        if p.get("served_by") == "R02":
            continue
        tgt = np.array(p["nest"])
        ok, k = rs.serviceable(fr3, R01, tgt, rng)
        reach[name] = dict(serviceable=bool(ok), yaw_coverage=f"{k}/5", dist=round(float(np.hypot(*(tgt - R01)[:2])), 3))
        if not ok:
            problems.append(f"{name} nest not serviceable by R01 ({k}/5 yaws)")
    reach.update(r02_dock_reach())
    problems += [f"TCM01 {d} not reachable by R02" for d, r in reach.items() if d.startswith("dock_") and not r["ok"]]
    for name, p in place.items():
        if p.get("served_by") == "R02":
            reach[name] = r02_plate_reach(np.array(p["nest"]))
            if not reach[name].get("ok"):
                problems.append(f"{name} nest not serviceable by R02 with T01")
            d = R02_DEVICES[name]
            for tname, (lx, ly, lz) in d.get("extra_targets", {}).items():
                xy = to_world((lx, ly), d["origin"], d["yaw_deg"])
                reach[tname] = r02_plate_reach(np.array([xy[0], xy[1], d.get("base_z", NEST_Z - d["seat"]) + lz]))
                if not reach[tname].get("ok"):
                    problems.append(f"{tname} not serviceable by R02 with T01")
    for name, xy in EXTRA_SITES.items():
        ok, k = rs.serviceable(fr3, R01, np.array([*xy, 0.96]), rng)
        reach[name] = dict(serviceable=bool(ok), yaw_coverage=f"{k}/5", dist=round(float(np.hypot(*(np.array(xy) - R01[:2]))), 3))
        if not ok:
            problems.append(f"{name} not serviceable by R01")
    fixtures = {n: dict(prim=f["prim"], origin=list(f["origin"]), yaw_deg=f["yaw_deg"], footprint=list(f["body"]))
                for n, f in FIXTURES.items()}
    out = dict(proposal="P1 R01 cluster", adopted="2026-10-15 (user)", r01_base=R01.tolist(), nest_z=NEST_Z,
               stations=place, fixtures=fixtures, r02_rail=RAIL, extra_frames={k: [*v, 0.96] for k, v in EXTRA_SITES.items()}, reach=reach,
               notes=["R02 rail shift (2.6 m travel, x -0.85..1.75 at y 0.78) is part of P1; R02 is built (assets/r02)",
                      "supports (side tables, L10 and L17 plinths) are provisional layout furniture",
                      "L17 keeps its Cell 01 location (1.65, 1.55), front toward R02's rail; served by R02 with T01",
                      "L21 moved from (2.25, 1.20) to (2.20, 1.07) on a 0.90 m side table; served by R02 with T01"],
               problems=problems)
    os.makedirs(os.path.join(ROOT, "scenes"), exist_ok=True)
    with open(os.path.join(ROOT, "scenes", "layout_p1.json"), "w") as f:
        json.dump(out, f, indent=2)
    for name, p in place.items():
        print(f"  {name:4s} origin {p['origin']} yaw {p['yaw_deg']:7.2f}  nest {p['nest']}  reach {reach[name]}")
    for name in EXTRA_SITES:
        print(f"  {name:22s} reach {reach[name]}")
    plot(shapes, place, out)
    print("PASS" if not problems else "FAIL:\n  " + "\n  ".join(problems))
    sys.exit(1 if problems else 0)


def r02_dock_reach():
    """R02 (rail + UR5e, assets/r02/r02.urdf) reaches each dock pose: coupler face on the docked coupling face,
    tool axis down; checked at the dock and 0.10 m above it (the lift-out), joint margin >= 15 deg."""
    sys.path.insert(0, os.path.join(ROOT))
    from twin.kinematics import UrdfChain
    urdf = os.path.join(ROOT, "assets/r02/r02.urdf")
    if not os.path.exists(urdf):
        return {}
    ch = UrdfChain(urdf, "rail_base", "tc_robot_half")
    tool = np.eye(4)
    tool[2, 3] = 0.016                                  # robot coupler face beyond tool0
    down = np.diag([1.0, -1.0, -1.0])                   # tool +Z down, tool X along world X
    f = FIXTURES["TCM01"]
    out = {}
    for k in range(5):
        p = np.array([f["origin"][0] + (k - 2) * f["dock_pitch"], f["origin"][1], f["dock_z"]])
        base = np.array([RAIL["x0"], RAIL["y"], 0.0])
        rail = float(np.clip(p[0] - base[0], 0.0, 2.6))
        q0 = np.array([rail, math.pi / 2, -1.2, 1.6, -1.97, -math.pi / 2, 0.0])
        ok, info = True, {}
        for lift in (0.10, 0.0):
            q = ch.ik(p - base + [0, 0, lift], down, q0, active=range(1, 7), tool=tool)
            good = q is not None and ch.margin(q, range(1, 7)) > math.radians(15)
            ok &= good
            if q is not None:
                q0 = q
                info = dict(rail_m=round(rail, 3), sigma_min=round(ch.sigma_min(q, range(1, 7), tool), 3),
                            margin_deg=round(math.degrees(ch.margin(q, range(1, 7))), 1))
        out[f"dock_T0{k + 1}"] = dict(ok=bool(ok), **info)
    return out


def r02_plate_reach(nest):
    """R02 with T01 serves a plate seat top-down (plate long axis along X, jaws along Y): grasp TCP 6 mm above the
    seat and the 0.15 m approach above it, joint margin >= 15 deg, best rail position."""
    sys.path.insert(0, os.path.join(ROOT))
    from twin.kinematics import UrdfChain
    urdf = os.path.join(ROOT, "assets/r02/r02.urdf")
    if not os.path.exists(urdf):
        return {}
    ch = UrdfChain(urdf, "rail_base", "tc_robot_half")
    tool = np.eye(4)
    tool[2, 3] = 0.016 + 0.155                          # coupler face + T01 TCP
    down = np.diag([1.0, -1.0, -1.0])
    base = np.array([RAIL["x0"], RAIL["y"], 0.0])
    best = dict(ok=False)
    for rail in np.clip(nest[0] - base[0] + np.array([0.0, -0.10, 0.10, -0.2, 0.2]), 0.02, 2.58):
        q0 = np.array([rail, math.pi / 2, -1.2, 1.6, -1.97, -math.pi / 2, 0.0])
        ok, info = True, {}
        for lift in (0.15, 0.006):
            q = ch.ik(nest - base + [0, 0, lift], down, q0, active=range(1, 7), tool=tool)
            good = q is not None and ch.margin(q, range(1, 7)) > math.radians(15)
            ok &= good
            if q is not None:
                q0 = q
                info = dict(rail_m=round(float(rail), 3), sigma_min=round(ch.sigma_min(q, range(1, 7), tool), 3),
                            margin_deg=round(math.degrees(ch.margin(q, range(1, 7))), 1))
        if ok and (not best["ok"] or info["sigma_min"] > best["sigma_min"]):
            best = dict(ok=True, **info)
    return best


def plot(shapes, place, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Polygon, Rectangle
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.add_patch(Rectangle((CELL[0], CELL[2]), 6, 4.5, fill=False, lw=2))
    ax.add_patch(Rectangle((BENCH[0], BENCH[2]), BENCH[1] - BENCH[0], BENCH[3] - BENCH[2], color="0.8", label="central bench"))
    ax.axhspan(-2.25, AMR_LANE_Y, color="tab:green", alpha=0.07, label="AMR front lane")
    ax.add_patch(Circle(R01[:2], 0.65, color="tab:blue", alpha=0.12, label="R01 top-down reach @ 0.97 m"))
    ax.add_patch(Circle(R01[:2], PEDESTAL_R, color="tab:blue", alpha=0.5))
    ax.plot([-0.85, 1.75], [0.78, 0.78], color="tab:orange", lw=4, label="R02 rail travel (P1)")
    col = {"body": "0.3", "low_dock": "tab:olive", "low_chassis": "tab:olive", "tray": "tab:purple", "stage": "tab:purple", "door_swing": "tab:red", "service_door": "tab:red",
           "rail": "tab:orange"}
    for name, part, poly in shapes:
        ax.add_patch(Polygon(poly, closed=True, fill=part == "body", alpha=0.35 if part == "body" else 0.9,
                             edgecolor=col[part], facecolor=col[part], lw=1.5, ls="-" if part == "body" else "--"))
    for name, f in out["fixtures"].items():
        ax.annotate(name, f["origin"][:2], ha="center", va="center", fontsize=9, color="white", weight="bold")
    for name, p in place.items():
        ax.plot(*p["nest"][:2], "s", color="tab:purple")
        ax.annotate(name, p["origin"][:2], ha="center", va="center", fontsize=11, color="white", weight="bold")
    for name, xyz in out["extra_frames"].items():
        ax.plot(*xyz[:2], "^", color="tab:green", ms=9)
        ax.annotate(name.replace("_", " "), xyz[:2], textcoords="offset points", xytext=(6, -12), fontsize=8)
    ax.set_xlim(-3.1, 2.6)
    ax.set_ylim(-1.3, 2.35)
    ax.set_aspect("equal")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right", fontsize=8)
    ax.set_title("Cell 01 layout P1 (adopted 2026-10-15): R01 cluster, R02 rail, tool magazine, L17  -  dashed: trays / "
                 "door swings")
    fig.tight_layout()
    fig.savefig(os.path.join(ROOT, "renders", "cell01_layout_p1.png"), dpi=110)


if __name__ == "__main__":
    main()
