"""Swept-volume clearance of R02 (rail + UR5e + tool + held plate) against the Cell 01 fit-out colliders.

Input: joint traces recorded by twin/r02_rig.py with R02_TRACE=<file> (20 Hz rows: rail q1..q6 holding tool). The arm
is modelled as conservative capsules between the URDF joint origins (radii above the UR5e link radii), the tool as a
capsule from the coupler face to its TCP, a held plate as a flat capsule (plate footprint) at the TCP. Every collider of the fit-out assets
(assets/cell01_fitout/usd/*.usda, placed as in scenes/cell01_twin.usda) is a box; the report gives the minimum
clearance per fit-out part and the trace samples that come closest.

Run: env_cad/bin/python tools/fitout_clearance.py <trace> [<trace> ...]
"""

import math
import os
import sys

import numpy as np
from pxr import Usd, UsdGeom, UsdPhysics

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from twin.kinematics import UrdfChain  # noqa: E402

SCENE = os.environ.get("CELL01_OVERLAY_OUT", os.path.join(ROOT, "scenes", "cell01_twin.usda"))
RAIL_ORIGIN = np.array([-0.85, 0.78, 0.0])
TOOL_TCP = {"T01": 0.155, "T02": 0.130, "T03": 0.150, "T04": 0.120, "T05": 0.110, "-": 0.0}
# capsule radii between consecutive frames (UR5e link radii + margin)
RADII = {"r02_shoulder_pan_joint": 0.08, "r02_shoulder_lift_joint": 0.08, "r02_elbow_joint": 0.065,
         "r02_wrist_1_joint": 0.055, "r02_wrist_2_joint": 0.05, "r02_wrist_3_joint": 0.05}
PARTS = ("/World/Cell01/Architecture/Enclosure_E01", "/World/Cell01/Stations/L12_LiquidHandler/Enclosure",
         "/World/Cell01/Furniture/P1_Supports")


def fitout_boxes(stage):
    out = []
    xc = UsdGeom.XformCache()
    for root in PARTS:
        prim = stage.GetPrimAtPath(root)
        if not prim:
            continue
        for p in Usd.PrimRange(prim):
            if p.IsA(UsdGeom.Cube) and p.HasAPI(UsdPhysics.CollisionAPI):
                M = xc.GetLocalToWorldTransform(p)
                A = np.array(M).T     # column-vector convention
                size = p.GetAttribute("size").Get() or 1.0
                axes = A[:3, :3] * size
                half = np.linalg.norm(axes, axis=0) / 2
                R = axes / (2 * half)
                out.append((str(p.GetPath()), A[:3, 3], R, half))
    return out


def seg_box_dist(a, b, c, R, half, n=12):
    ts = np.linspace(0, 1, n)[:, None]
    pts = a + (b - a) * ts
    local = (pts - c) @ R
    d = np.maximum(np.abs(local) - half, 0)
    return np.linalg.norm(d, axis=1).min()


def main(paths):
    chain = UrdfChain(os.path.join(ROOT, "assets/r02/r02.urdf"), "rail_base", "r02_tool0")
    stage = Usd.Stage.Open(SCENE)
    boxes = fitout_boxes(stage)
    print(f"{len(boxes)} fit-out collider boxes")
    best = {}
    for path in paths:
        rows = [ln.split() for ln in open(path) if ln.strip()]
        for i, r in enumerate(rows):
            q = np.array(list(map(float, r[:7])))
            hold, tool = r[7] == "1", r[8]
            fr = chain.frames(q)
            pts = {name: T[:3, 3] + RAIL_ORIGIN for name, T in fr}
            names = [n for n, _ in fr]
            caps = []
            for a, b in zip(names[:-1], names[1:]):
                if a in RADII and np.linalg.norm(pts[b] - pts[a]) > 1e-4:
                    caps.append((pts[a], pts[b], RADII[a]))
            T0 = fr[-1][1]
            z = T0[:3, 2]
            tip = pts[names[-1]] + z * (0.016 + TOOL_TCP.get(tool, 0.15))
            caps.append((pts[names[-1]], tip, 0.05 if tool != "-" else 0.04))
            if hold:   # SBS plate under the TCP: flat capsule along the tool x-axis (127.8 x 85.5 x 14.4 mm)
                xa = T0[:3, 0]
                c = tip + z * 0.006
                caps.append((c - xa * 0.0213, c + xa * 0.0213, 0.043))
            for bp, c, R, half in boxes:
                part = bp.split("/Collision/")[0] if "/Collision/" in bp else bp
                d = min(seg_box_dist(a, b, c, R, half) - rad for a, b, rad in caps)
                if part not in best or d < best[part][0]:
                    best[part] = (d, os.path.basename(path), i, bp.split("/")[-2], np.round(tip, 3).tolist(), tool, hold)
    print(f"{'fit-out part':60s} {'min clearance':>13s}  sample")
    worst = math.inf
    for part, (d, f, i, box, tip, tool, hold) in sorted(best.items(), key=lambda kv: kv[1][0]):
        worst = min(worst, d)
        print(f"{part.replace('/World/Cell01/', ''):60s} {d * 1000:10.0f} mm  {f}#{i} {box} tool {tool} "
              f"{'holding' if hold else ''} tip {tip}")
    return worst


if __name__ == "__main__":
    w = main(sys.argv[1:])
    print(f"worst clearance {w * 1000:.0f} mm")
