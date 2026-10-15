"""Cell 01 reachability study: can R01 (FR3) and R02 (UR5e on the 2.6 m rail) serve the stations?

Kinematics: FR3 from assets/fr3/fr3_arm.urdf (the same model the simulation uses); UR5e from its
published DH parameters. Both carry the R01 plate gripper (TCP 171 mm beyond the flange, incl. tool
changer). A site counts as SERVICEABLE when a top-down grasp is IK-feasible at the site AND at its 0.20 m
approach point for at least 2 of 5 tool yaws (-90..90 deg about the radial direction), i.e. with some
orientation margin; stations can be oriented to suit the arm. Yaw coverage k/5 is reported.

Reach is (almost) rotationally symmetric for R01 about joint 1 and translation-invariant along the rail for
R02, so the study computes reachable distance bands (radial for R01, perpendicular-to-rail for R02) per
site height with numerical IK, then classifies every station interaction point in two layouts:
  usd   - the Cell 01 BioPhysical v2 USD (the twin)
  plan  - the 'Recommended Authoritative Engineering Layout v0.3' floor plan (positions read off the PNG)

Outputs: renders/cell01_reachability.png and test_reports/cell01_reachability.json.
Run: env_cad/bin/python tools/reachability_study.py
"""

import json
import math
import os
import xml.etree.ElementTree as ET

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
URDF = os.path.join(ROOT, "assets/fr3/fr3_arm.urdf")
TCP = 0.171            # plate gripper TCP beyond the robot flange
APPROACH = 0.20
R01_BASES = {"usd": np.array([-1.65, -0.10, 0.72]),     # Cell 01 USD R01_FR3/base_link (also the plan position)
             "plan": np.array([-1.65, -0.10, 0.72]),
             "proposal": np.array([-1.55, 0.35, 0.72])}  # P1: R01 moved onto the bench line
R01_BASE = R01_BASES["usd"]
RAIL = {"usd": dict(y=0.95, x0=0.60, x1=1.90, z=0.97),    # R02_RailSystem bbox (USD), base on the carriage
        "plan": dict(y=0.78, x0=-0.15, x1=2.45, z=0.97),  # floor plan v0.3: 2.6 m travel at y ~ 0.78
        "proposal": dict(y=0.78, x0=-0.85, x1=1.75, z=0.97)}  # P1: same 2.6 m (D004), shifted 0.7 m west


# ------------------------------------------------------------------------------ kinematics
def rpy_xyz(rpy, xyz):
    r, p, y = rpy
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    T = np.eye(4)
    T[:3, :3] = [[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                 [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                 [-sp, cp * sr, cp * cr]]
    T[:3, 3] = xyz
    return T


def rot_axis(axis, q):
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    T = np.eye(4)
    T[:3, :3] = np.eye(3) + math.sin(q) * K + (1 - math.cos(q)) * K @ K
    return T


class FR3:
    """FK from the URDF chain fr3_link0 -> fr3_link8, + gripper (-45 deg about flange z, TCP 171 mm)."""
    def __init__(self, urdf):
        joints = {j.find("parent").get("link"): j for j in ET.parse(urdf).getroot().findall("joint")
                  if j.find("parent") is not None and j.get("name").startswith("fr3_joint")}
        self.chain, link = [], "fr3_link0"
        while link in joints:
            j = joints[link]
            o = j.find("origin")
            T = rpy_xyz([float(v) for v in o.get("rpy", "0 0 0").split()], [float(v) for v in o.get("xyz").split()])
            lim = j.find("limit")
            self.chain.append((T, j.get("type"), [float(v) for v in j.find("axis").get("xyz").split()]
                               if j.find("axis") is not None else None,
                               (float(lim.get("lower")), float(lim.get("upper"))) if lim is not None else None))
            link = j.find("child").get("link")
        self.limits = np.array([c[3] for c in self.chain if c[1] == "revolute"])
        self.tool = rot_axis([0, 0, 1], -math.pi / 4) @ rpy_xyz([0, 0, 0], [0, 0, TCP])

    def fk(self, q):
        T, k = np.eye(4), 0
        for To, typ, axis, _ in self.chain:
            T = T @ To
            if typ == "revolute":
                T = T @ rot_axis(axis, q[k])
                k += 1
        return T @ self.tool


class UR5e:
    d = [0.1625, 0, 0, 0.1333, 0.0997, 0.0996]
    a = [0, -0.425, -0.3922, 0, 0, 0]
    alpha = [math.pi / 2, 0, 0, math.pi / 2, -math.pi / 2, 0]
    limits = np.array([[-2 * math.pi, 2 * math.pi]] * 6)
    limits[2] = [-math.pi, math.pi]
    tool = rpy_xyz([0, 0, 0], [0, 0, TCP])

    def fk(self, q):
        T = np.eye(4)
        for i in range(6):
            ct, st, ca, sa = math.cos(q[i]), math.sin(q[i]), math.cos(self.alpha[i]), math.sin(self.alpha[i])
            T = T @ np.array([[ct, -st * ca, st * sa, self.a[i] * ct], [st, ct * ca, -ct * sa, self.a[i] * st],
                              [0, sa, ca, self.d[i]], [0, 0, 0, 1]])
        return T @ self.tool


def ik(robot, p, yaw, rng, restarts=4, iters=90):
    """Top-down pose: tool z = -Z, tool x along yaw. Returns True if reachable within 1 mm / 0.5 deg."""
    return ik_solve(robot, p, yaw, rng, restarts, iters) is not None


def ik_solve(robot, p, yaw, rng, restarts=4, iters=90, q0=None):
    """As ik(), but returns the joint solution (or None). q0 seeds the first attempt."""
    c, s = math.cos(yaw), math.sin(yaw)
    Rt = np.array([[c, s, 0], [s, -c, 0], [0, 0, -1]])  # columns: x=(c,s,0), y=(s,-c,0), z=(0,0,-1)
    lo, hi = robot.limits[:, 0], robot.limits[:, 1]
    for attempt in range(restarts):
        q = np.array(q0, float) if (q0 is not None and attempt == 0) else rng.uniform(lo * 0.8, hi * 0.8)
        for _ in range(iters):
            T = robot.fk(q)
            e = np.concatenate([p - T[:3, 3], 0.5 * (np.cross(T[:3, 0], Rt[:, 0]) + np.cross(T[:3, 1], Rt[:, 1])
                                                     + np.cross(T[:3, 2], Rt[:, 2]))])
            if np.linalg.norm(e[:3]) < 1e-3 and np.linalg.norm(e[3:]) < math.radians(0.5):
                return q
            J = np.zeros((6, len(q)))
            for k in range(len(q)):
                dq = np.zeros(len(q))
                dq[k] = 1e-5
                T2 = robot.fk(q + dq)
                J[:3, k] = (T2[:3, 3] - T[:3, 3]) / 1e-5
                Rd = T2[:3, :3] @ T[:3, :3].T
                J[3:, k] = np.array([Rd[2, 1] - Rd[1, 2], Rd[0, 2] - Rd[2, 0], Rd[1, 0] - Rd[0, 1]]) / 2e-5
            q = np.clip(q + J.T @ np.linalg.solve(J @ J.T + 1e-4 * np.eye(6), e), lo, hi)
    return None


def serviceable(robot, base, target, rng, yaws=(-90, -45, 0, 45, 90)):
    """Top-down at target and at target+APPROACH, for every tool yaw relative to the radial direction."""
    d = target - base
    radial = math.atan2(d[1], d[0])
    ok = []
    for y in yaws:
        ok.append(all(ik(robot, d + [0, 0, dz], radial + math.radians(y), rng) for dz in (0.0, APPROACH)))
    return sum(ok) >= 2, sum(ok)


def band(robot, height_rel, rng, rmax=1.1, step=0.05):
    rs = np.arange(0.05, rmax, step)
    good = [r for r in rs if serviceable(robot, np.zeros(3), np.array([r, 0, height_rel]), rng)[0]]
    return (round(float(min(good)), 3), round(float(max(good)), 3)) if good else None


# ------------------------------------------------------------------------------ layouts
# interaction points (x, y, z): the frame a robot would place to / pick from. Placeholder frames in the USD
# sit at station origins, so for enclosed devices the point is taken at the device's robot-facing front.
LAYOUTS = {
    "usd": {
        "L09 plate hotel (transfer, front)": (-2.35, 1.40, 0.96),
        "L10 incubator (transfer, front)": (-1.55, 1.40, 0.96),
        "L12 liquid handler (plate nest)": (0.15, 0.10, 1.06),
        "L17 imager (plate load)": (1.65, 1.38, 1.00),
        "L21 QC (reference nest)": (2.48, 1.55, 0.97),
        "H4 quarantine (transfer_nest, overlay)": (-1.236, 0.186, 0.992),
        "R03 AMR dock (carrier)": (-1.80, -1.80, 0.30),
    },
    "plan": {
        "L09 plate hotel (transfer, front)": (-2.35, 1.25, 0.96),
        "L10 incubator (transfer, front)": (-1.50, 1.20, 0.96),
        "L12 liquid handler (deck front)": (0.05, 1.05, 0.98),
        "L17 imager (plate load)": (1.45, 1.28, 1.00),
        "L14 seal/inspect": (2.10, 0.87, 0.98),
        "L21 QC (reference nest)": (2.55, 1.45, 0.97),
        "H4 quarantine (plan corner)": (2.35, -1.35, 0.96),
        "R03 AMR dock (carrier)": (-1.80, -1.40, 0.30),
    },
    # P1 'R01 cluster': every R01 site 0.50-0.61 m from R01, transfer stations facing R01; a shared
    # R01<->R02 handover nest; AMR docks from the front lane with its carrier raised to bench height.
    "proposal": {
        "L10 incubator (transfer, faces R01)": (-2.05, 0.70, 0.96),
        "L09 plate hotel (transfer, faces R01)": (-1.30, 0.85, 0.96),
        "H4 quarantine (transfer_nest)": (-1.95, 0.00, 0.992),
        "R03 AMR dock (carrier, bench height)": (-1.25, -0.05, 0.96),
        "HN handover nest R01<->R02": (-1.05, 0.55, 0.96),
        "L12 liquid handler (deck front)": (0.05, 1.05, 0.98),
        "L17 imager (plate load)": (1.45, 1.28, 1.00),
        "L14 seal/inspect": (2.10, 0.87, 0.98),
        "L21 QC (moved: reference nest)": (2.25, 1.20, 0.97),
    },
}


def hclass(z):
    """Site-height classes for the band computation (keeps the IK sweep to a few minutes)."""
    return min((0.30, 0.97, 1.06), key=lambda c: abs(c - z))


def main():
    rng = np.random.default_rng(0)
    fr3, ur5e = FR3(URDF), UR5e()
    print("computing reach bands (numerical IK)...")
    heights = sorted({hclass(p[2]) for lay in LAYOUTS.values() for p in lay.values()})
    r01_bands = {h: band(fr3, h - R01_BASE[2], rng) for h in heights}  # all layouts: base at 0.72 m
    r02_bands = {h: band(ur5e, h - RAIL["usd"]["z"], rng) for h in heights}
    for h in heights:
        print(f"  z={h:.2f}: R01 radial band {r01_bands[h]}, R02 perpendicular band {r02_bands[h]}")

    result = {"assumptions": {"tcp_m": TCP, "approach_m": APPROACH, "R01_base": R01_BASE.tolist(), "rails": RAIL,
                              "criterion": "top-down IK at site and approach, tool yaw -90..90 deg about radial"},
              "bands": {"R01": {str(h): r01_bands[h] for h in heights}, "R02": {str(h): r02_bands[h] for h in heights}},
              "layouts": {}}
    for name, sites in LAYOUTS.items():
        rail = RAIL[name]
        base = R01_BASES[name]
        rows = {}
        for site, p in sites.items():
            p = np.array(p)
            r1 = float(np.hypot(*(p - base)[:2]))
            b1 = r01_bands[hclass(p[2])]
            ok1 = bool(b1 is not None and b1[0] <= r1 <= b1[1])
            xr = min(max(p[0], rail["x0"]), rail["x1"])  # carriage moves to the closest rail position
            r2 = float(np.hypot(p[0] - xr, p[1] - rail["y"]))
            b2 = r02_bands[hclass(p[2])]
            ok2 = bool(b2 is not None and b2[0] <= r2 <= b2[1])
            rows[site] = {"point": p.tolist(), "R01_dist_m": round(r1, 3), "R01": ok1, "R02_dist_m": round(r2, 3),
                          "R02": ok2}
            print(f"  [{name:4s}] {site:42s} R01 {r1:4.2f} m {'OK ' if ok1 else 'no '}  "
                  f"R02 {r2:4.2f} m {'OK' if ok2 else 'no'}")
        result["layouts"][name] = rows
    os.makedirs(os.path.join(ROOT, "test_reports"), exist_ok=True)
    with open(os.path.join(ROOT, "test_reports/cell01_reachability.json"), "w") as f:
        json.dump(result, f, indent=2)
    plot(result, r01_bands, r02_bands)


def plot(result, r01_bands, r02_bands):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle
    fig, axes = plt.subplots(1, 3, figsize=(24, 6.8))
    h = hclass(0.96)
    for ax, name in zip(axes, ("usd", "plan", "proposal")):
        R01_BASE = R01_BASES[name]
        ax.add_patch(Rectangle((-3, -2.25), 6, 4.5, fill=False, lw=2))
        b1 = r01_bands[h]
        if b1:
            ax.add_patch(Circle(R01_BASE[:2], b1[1], color="tab:blue", alpha=0.15, label=f"R01 top-down reach @ {h} m"))
            ax.add_patch(Circle(R01_BASE[:2], b1[0], color="white", alpha=1.0))
        rail = RAIL[name]
        b2 = r02_bands[h]
        if b2:
            ax.add_patch(Rectangle((rail["x0"] - b2[1], rail["y"] - b2[1]), rail["x1"] - rail["x0"] + 2 * b2[1],
                                   2 * b2[1], color="tab:orange", alpha=0.15, label=f"R02 (rail) reach @ {h} m"))
        ax.plot([rail["x0"], rail["x1"]], [rail["y"]] * 2, color="tab:orange", lw=4)
        ax.plot(*R01_BASE[:2], "o", color="tab:blue", ms=10)
        for site, row in result["layouts"][name].items():
            x, y, _ = row["point"]
            col = "tab:green" if (row["R01"] or row["R02"]) else "tab:red"
            ax.plot(x, y, "s", color=col, ms=8)
            ax.annotate(site.split(" (")[0], (x, y), textcoords="offset points", xytext=(5, 5), fontsize=8)
        ax.set_xlim(-3.2, 3.2)
        ax.set_ylim(-2.4, 2.4)
        ax.set_aspect("equal")
        ax.grid(alpha=0.3)
        ax.set_title({"usd": "Cell 01 USD (twin) layout", "plan": "Floor plan v0.3",
                      "proposal": "Proposal P1: R01 cluster + rail shifted west"}[name] +
                     "  -  green: serviceable, red: out of reach")
        ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    out = os.path.join(ROOT, "renders/cell01_reachability.png")
    fig.savefig(out, dpi=110)
    print("wrote", out)


if __name__ == "__main__":
    main()
