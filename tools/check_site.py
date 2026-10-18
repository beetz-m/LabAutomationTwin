"""Site layout S1 checks on the composed lab twin (scenes/lab_twin.usda) + plan drawing.

Measured from the composed USD (world bounding boxes of every placed asset), not from the placement table:
  * no two floor items overlap (benchtop items must sit on a worktop: z0 at the top of the item below, inside it);
  * every item stays inside its room: hall walls, storage-room partitions, and out of the Cell 01 envelope;
  * R03's route (shell curve AmrRoute_S1_to_H2, outside the cell) is clear: a 0.40 m half-width corridor along each
    segment and a 0.58 m turn-in-place circle at every corner (AMR half-diagonal 0.53 m + 0.05 m) against every item
    lower than the AMR's 1.05 m;
  * door swings clear: enclosure D1 (into the hall), D2/D3 (into the rear corridor), the storage sliding leaf path;
  * rear service corridor >= 1.0 m (Cell 01 spec), BSC operator zones (1.0 m) and the emergency-shower area clear.
Writes test_reports/site_layout_check.json and renders/site_plan_s1.png. Exit 1 on any failure.
Run: env_cad/bin/python tools/check_site.py
"""

import json
import math
import os
import sys

import numpy as np
from pxr import Usd, UsdGeom

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCENE = os.path.join(ROOT, "scenes", "lab_twin.usda")
LAYOUT = os.path.join(ROOT, "scenes", "site_layout_s1.json")
LAB = "/World/AICOR_Lab"
CELL = (-3.05, 3.05, -2.30, 2.30)
AMR_H, LANE_HALF, TURN_R = 1.05, 0.40, 0.58


def rect_overlap(a, b, eps=0.005):
    return min(a[1], b[1]) - max(a[0], b[0]) > eps and min(a[3], b[3]) - max(a[2], b[2]) > eps


def seg_rect_dist(p, q, r):
    """Distance from segment pq to axis-aligned rectangle r=(x0,x1,y0,y1) (0 if intersecting), sampled."""
    best = math.inf
    for t in np.linspace(0, 1, 60):
        x, y = p + (q - p) * t
        dx = max(r[0] - x, 0, x - r[1])
        dy = max(r[2] - y, 0, y - r[3])
        best = min(best, math.hypot(dx, dy))
    return best


def main():
    st = Usd.Stage.Open(SCENE)
    lay = json.load(open(LAYOUT))
    bc = UsdGeom.BBoxCache(0, ["default", "render"])
    items = {}
    for zone in st.GetPrimAtPath(LAB).GetChildren():
        if zone.GetName() in ("Building", "Zones", "Ceiling", "Sun", "Looks"):
            continue
        for p in zone.GetChildren():
            r = bc.ComputeWorldBound(p).ComputeAlignedRange()
            if r.IsEmpty():
                continue
            lo, hi = r.GetMin(), r.GetMax()
            items[p.GetName()] = dict(zone=zone.GetName(), r=(lo[0], hi[0], lo[1], hi[1]), z=(lo[2], hi[2]))
    problems, notes = [], []
    names = sorted(items)
    # 1 overlaps / support relations
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            A, B = items[a], items[b]
            if not rect_overlap(A["r"], B["r"]):
                continue
            if min(A["z"][1], B["z"][1]) - max(A["z"][0], B["z"][0]) <= 0.01:
                continue
            top, low = (A, B) if A["z"][0] > B["z"][0] else (B, A)
            tn, ln = (a, b) if top is A else (b, a)
            inside = (top["r"][0] >= low["r"][0] - 0.02 and top["r"][1] <= low["r"][1] + 0.02 and
                      top["r"][2] >= low["r"][2] - 0.02 and top["r"][3] <= low["r"][3] + 0.02)
            if top["z"][0] > 0.5 and inside and abs(top["z"][0] - 0.90) < 0.03:
                notes.append(f"{tn} stands on {ln}")
                continue
            if top["z"][0] > 0.5 and low["z"][1] - top["z"][0] < 0.12 and inside:
                notes.append(f"{tn} on {ln} (worktop z {low['z'][1]:.3f}, item z0 {top['z'][0]:.3f})")
                continue
            problems.append(f"overlap: {a} and {b}")
    # 2 rooms / walls / the cell
    hall, store = lay["hall"], lay["storage"]
    for n, it in items.items():
        x0, x1, y0, y1 = it["r"]
        if x0 < hall["x0"] - 0.01 or x1 > hall["x1"] + 0.01 or y0 < hall["y0"] - 0.01 or y1 > hall["y1"] + 0.01:
            problems.append(f"{n} outside the hall walls {np.round(it['r'], 3).tolist()}")
        in_store = it["zone"] == "StorageRoom" and n not in ("ST01_Access",)
        if in_store and (x1 > store["x1"] - 0.06 + 0.01 or y0 < store["y0"] + 0.06 - 0.01):
            problems.append(f"{n} crosses the storage-room partition {np.round(it['r'], 3).tolist()}")
        if not in_store and it["zone"] != "StorageRoom":
            if x0 < store["x1"] + 0.06 - 0.01 and y1 > store["y0"] - 0.06 + 0.01 and x1 > store["x0"]:
                problems.append(f"{n} intrudes on the storage room {np.round(it['r'], 3).tolist()}")
        if rect_overlap(it["r"], CELL):
            problems.append(f"{n} inside the Cell 01 envelope")
    # 3 AMR route (world), corridor + turning circles, items lower than the AMR
    route = [np.array(p, float) for p in lay["amr_route"]]
    outside = [p for p in route if not (CELL[0] < p[0] < CELL[1] and CELL[2] < p[1] < CELL[3])]
    worst = math.inf
    for n, it in items.items():
        if it["z"][0] > AMR_H or n == "S1_DispatchDock":     # the AMR's own dock at the route start
            continue
        for p, q in zip(outside[:-1], outside[1:]):
            d = seg_rect_dist(p, q, it["r"])
            worst = min(worst, d - LANE_HALF)
            if d < LANE_HALF:
                problems.append(f"{n} in the AMR corridor ({d:.2f} m from the route)")
        for c in outside[1:-1]:
            d = seg_rect_dist(c, c, it["r"])
            if d < TURN_R:
                problems.append(f"{n} in R03's turning circle at {c.tolist()} ({d:.2f} m)")
    sd = lay["storage_door"]
    if sd[1] - sd[0] < 0.58 + 2 * 0.25:
        problems.append("storage door narrower than the AMR + 2 x 0.25 m")
    # 4 door swings and sliding-leaf path
    swings = {"D1 (hall)": (-1.12, -0.08, -2.30 - 1.04, -2.30), "D2 (corridor)": (-2.62, -1.58, 2.30, 2.30 + 1.04),
              "D3 (corridor)": (1.08, 2.12, 2.30, 2.30 + 1.04),
              "ST01 sliding leaf": (sd[0] - 1.55, sd[1], store["y0"] - 0.15, store["y0"] - 0.06)}
    for name, r in swings.items():
        for n, it in items.items():
            if rect_overlap(r, it["r"]) and it["z"][0] < 2.0 and n != "ST01_Access":
                problems.append(f"{n} in the swing/slide zone of {name}")
    # 5 rear corridor width, BSC zones, emergency shower
    north = min([it["r"][2] for it in items.values() if it["r"][1] > CELL[0] and it["r"][0] < CELL[1]
                 and it["r"][2] > CELL[3]] + [hall["y1"] - 0.25])          # utility panels are 0.25 deep
    corridor = north - CELL[3]
    if corridor < 1.0:
        problems.append(f"rear service corridor only {corridor:.2f} m")
    for bsc in ("PR_BSC1", "PR_BSC2"):
        if bsc in items:
            b = items[bsc]["r"]
            zone = (b[0] - 1.0, b[0], b[2], b[3])
            for n, it in items.items():
                if n != bsc and not n.startswith("PR_Stool") and rect_overlap(zone, it["r"]):
                    problems.append(f"{n} in the operator zone of {bsc}")
    if "PR_Shower" in items:
        c = ((items["PR_Shower"]["r"][0] + items["PR_Shower"]["r"][1]) / 2, items["PR_Shower"]["r"][2])
        zone = (c[0] - 0.45, c[0] + 0.45, c[1] - 0.95, c[1] - 0.05)
        for n, it in items.items():
            if n != "PR_Shower" and rect_overlap(zone, it["r"]) and it["z"][0] < 2.0:
                problems.append(f"{n} in the emergency-shower area")
    out = dict(items={k: dict(zone=v["zone"], rect=np.round(v["r"], 3).tolist(), z=np.round(v["z"], 3).tolist())
                      for k, v in items.items()},
               notes=notes, problems=problems, rear_corridor_m=round(corridor, 3),
               amr_corridor_min_margin_m=round(worst, 3), status=lay["status"])
    json.dump(out, open(os.path.join(ROOT, "test_reports", "site_layout_check.json"), "w"), indent=1)
    plot(lay, items, route)
    print(f"{len(items)} items; {len(notes)} support relations; rear corridor {corridor:.2f} m; "
          f"AMR corridor min margin {worst:.2f} m")
    for p in problems:
        print("  PROBLEM:", p)
    print("OK" if not problems else f"{len(problems)} problems")
    return not problems


def plot(lay, items, route):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle
    fig, ax = plt.subplots(figsize=(16, 9.6))
    h, s = lay["hall"], lay["storage"]
    ax.add_patch(Rectangle((h["x0"], h["y0"]), h["x1"] - h["x0"], h["y1"] - h["y0"], fill=False, lw=3, ec="k"))
    ax.add_patch(Rectangle((s["x0"], s["y0"]), s["x1"] - s["x0"], s["y1"] - s["y0"], fill=False, lw=2, ec="k"))
    for name, z in lay["zones"].items():
        x0, x1, y0, y1 = z["extent_xy"]
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, alpha=0.06, color="tab:green" if name != "Cell01" else "tab:blue"))
        ax.text(x0 + 0.08, y1 - 0.25, name, fontsize=8, color="darkgreen" if name != "Cell01" else "navy")
    for n, it in items.items():
        x0, x1, y0, y1 = it["r"]
        bench_top = it["z"][0] > 0.5
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, alpha=0.35 if not bench_top else 0.6,
                               color="tab:gray" if not bench_top else "tab:orange", lw=0.5))
        if (x1 - x0) * (y1 - y0) > 0.15:
            ax.text((x0 + x1) / 2, (y0 + y1) / 2, n.replace("_", " "), fontsize=6, ha="center", va="center")
    ax.add_patch(Rectangle((CELL[0], CELL[2]), CELL[1] - CELL[0], CELL[3] - CELL[2], fill=False, lw=2, ec="tab:blue"))
    ax.text(0, 0, "Cell 01\n(layout P1)", ha="center", va="center", fontsize=12, color="navy")
    R = np.array(route)
    ax.plot(R[:, 0], R[:, 1], "-", color="tab:red", lw=2, label="R03 route S1 -> H2")
    for c in R[1:-1]:
        ax.add_patch(Circle(c, TURN_R, fill=False, ls=":", ec="tab:red"))
    sd = lay["storage_door"]
    ax.plot([sd[0], sd[1]], [s["y0"], s["y0"]], color="white", lw=4)
    ax.set_xlim(h["x0"] - 0.5, h["x1"] + 0.5)
    ax.set_ylim(h["y0"] - 0.5, h["y1"] + 0.5)
    ax.set_aspect("equal")
    ax.grid(alpha=0.2)
    ax.set_title("AICOR Lab 1 - site layout proposal S1 around Cell 01 (measured from the composed twin)")
    ax.legend(loc="lower right")
    os.makedirs(os.path.join(ROOT, "renders"), exist_ok=True)
    fig.savefig(os.path.join(ROOT, "renders", "site_plan_s1.png"), dpi=110, bbox_inches="tight")


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
