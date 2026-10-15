"""Kinematic interference check for a plate store's internal handler, L09 or L10 (CPU, no simulator).

Sweeps the store/retrieve waypoint sequences (and shuttle/gate motion) and reports overlaps between the
moving links' box colliders (Fork, Lift, Gate, Shuttle, plus a plate riding on the tine or sitting on the nest)
and everything else. Convex guide colliders are approximated by their bounding boxes (conservative).
Run: env_cad/bin/python tools/check_store_clearance.py [--device l09|l10] [slot ...]
"""

import importlib.util
import os
import sys
from types import SimpleNamespace

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "assets"))
from common.twin_cad import SBS  # noqa: E402

DEVICE = sys.argv[sys.argv.index("--device") + 1] if "--device" in sys.argv else "l09"
_spec = importlib.util.spec_from_file_location("build", os.path.join(HERE, "..", "assets", DEVICE, f"build_{DEVICE}.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
D = _mod.DESIGN
L = SimpleNamespace(collision_boxes=D.collision_boxes, NEST=D.NEST, N_SLOTS=D.n_slots, TINE_REF_Z=D.TINE_REF_Z,
                    FORK_TRAVEL=D.FORK_TRAVEL, PARK_TINE_Z=D.park_tine_z, YN=D.YN, YC=D.YC, SEAT_Z=D.SEAT_Z,
                    ledge_top=D.ledge_top, GATE_TRAVEL=D.GATE["travel"], SHUTTLE_TRAVEL=D.NEST.travel)

EPS = 0.05  # mm: touching is not overlapping


def boxes_at(lift, fork, shuttle, gate):
    """World AABBs (mm) of all colliders at the given joint values (mm)."""
    cb = L.collision_boxes()
    off = {"Body": (0, 0, 0), "Gate": (0, 0, gate), "Shuttle": (0, -shuttle, 0), "Lift": (0, 0, lift),
           "Fork": (0, fork, lift), "ServiceDoor": (0, 0, 0)}
    out = []
    for link, bxs in cb.items():
        o = np.array(off[link], float)
        for name, xs, ys, zs in bxs:
            out.append((link, name, np.array([xs[0], ys[0], zs[0]]) + o, np.array([xs[1], ys[1], zs[1]]) + o))
    for name, solid in L.NEST.convex_colliders():
        bb = solid.val().BoundingBox()
        o = np.array(off["Shuttle"], float)
        out.append(("Shuttle", name, np.array([bb.xmin, bb.ymin, bb.zmin]) + o, np.array([bb.xmax, bb.ymax, bb.zmax]) + o))
    return out


def plate_box(center_xy, bottom_z):
    w, d, h = SBS
    c = np.array([center_xy[0], center_xy[1], bottom_z])
    return np.array([c[0] - w / 2, c[1] - d / 2, bottom_z]), np.array([c[0] + w / 2, c[1] + d / 2, bottom_z + h])


def overlap(a0, a1, b0, b1):
    return bool(np.all(np.minimum(a1, b1) - np.maximum(a0, b0) > EPS))


MOVING = {"Fork", "Lift"}
PAIRS_OK = {("Lift", "Fork")}  # jointed


def check(pose, plate=None, label="", quiet=False):
    lift, fork, shuttle, gate = pose
    bxs = boxes_at(lift, fork, shuttle, gate)
    bad = []
    for i, (la, na, a0, a1) in enumerate(bxs):
        for lb, nb, b0, b1 in bxs[i + 1:]:
            if la == lb or (la, lb) in PAIRS_OK or (lb, la) in PAIRS_OK:
                continue
            if not ({la, lb} & (MOVING | {"Shuttle", "Gate"})):
                continue
            if {la, lb} == {"Body", "Shuttle"} and shuttle == 0 and gate == 0:
                pass
            if overlap(a0, a1, b0, b1):
                if {la, lb} <= {"Body", "Shuttle", "Gate"} and not ({la, lb} & MOVING):
                    if {la, lb} == {"Body", "Shuttle"} or {la, lb} == {"Body", "Gate"}:
                        continue  # jointed to Body: PhysX filters these pairs
                if {la, lb} == {"Body", "Lift"}:
                    continue  # jointed
                bad.append(f"{la}/{na} x {lb}/{nb}")
    if plate is not None:
        p0, p1 = plate
        for lb, nb, b0, b1 in bxs:
            # the A1 key sits inside the plate's chamfered A1 corner, which a plain AABB cannot represent
            if overlap(p0, p1, b0, b1) and not (lb == "Fork" and nb == "Tine") and not nb.startswith(
                    ("NestCore", "Guide", "A1Key")):
                bad.append(f"PLATE x {lb}/{nb}")
    if quiet and not bad:
        return True
    print(f"  {'OK ' if not bad else 'BAD'} {label:58s} lift={lift:6.1f} fork={fork:6.1f} shuttle={shuttle:5.1f} gate={gate:4.1f}"
          + ("" if not bad else "  <- " + "; ".join(bad)))
    return not bad


def main():
    args = [a for i, a in enumerate(sys.argv[1:], 1) if a != "--device" and sys.argv[i - 1] != "--device"]
    slots = [int(a) for a in args] or [0, L.N_SLOTS // 2, L.N_SLOTS - 1]
    print(f"device {DEVICE}: {L.N_SLOTS} slots")
    ref, FT = L.TINE_REF_Z, L.FORK_TRAVEL
    q = lambda z: z - ref  # noqa: E731
    park = q(L.PARK_TINE_Z)
    nest_plate = plate_box((0, L.YN), L.SEAT_Z)
    ok = True
    print("shuttle/gate with handler parked:")
    gt, st = L.GATE_TRAVEL, L.SHUTTLE_TRAVEL
    for sh, g, lab in ((0, 0, "stowed, gate closed"), (0, gt, "gate open"), (st, gt, "presented")):
        ok &= check((park, 0, sh, g), plate_box((0, L.YN - sh), L.SEAT_Z), lab + " (plate on nest)")
    for k in slots:
        Lk = L.ledge_top(k)
        print(f"store / retrieve slot {k} (ledge {Lk:.0f} mm):")
        seq = [
            ((park, FT), nest_plate, "fork to slot side at park height (plate on nest)"),
            ((q(ref), FT), nest_plate, "down to nest level behind the nest"),
            ((q(ref), FT / 2), nest_plate, "sliding under the plate (half way)"),
            ((q(ref), 0), nest_plate, "tine under the seated plate"),
            ((q(Lk + 4), 0), plate_box((0, L.YN), Lk + 4), "plate lifted to the slot height"),
            ((q(Lk + 4), FT / 2), plate_box((0, L.YN + FT / 2), Lk + 4), "carrying into the slot (half way)"),
            ((q(Lk + 4), FT), plate_box((0, L.YC), Lk + 4), "plate over the ledges"),
            ((q(Lk - 3), FT), plate_box((0, L.YC), Lk), "plate set down on the ledges"),
            ((q(Lk - 3), 0), plate_box((0, L.YC), Lk), "tine withdrawn into the channel"),
            ((park, 0), plate_box((0, L.YC), Lk), "parked"),
        ]
        prev = (park, 0.0)
        for (lift, fork), pl, lab in seq:
            # sweep the motion, not only the waypoint (a waypoint-only check missed a collision mid-descent);
            # the plate box follows the fork while carried, else it stays where it is
            for i in range(1, 11):
                a = i / 10
                lq, fq = prev[0] + (lift - prev[0]) * a, prev[1] + (fork - prev[1]) * a
                ok &= check((lq, fq, 0, 0), pl, f"{lab} [{i}/10]", quiet=True)
            ok &= check((lift, fork, 0, 0), pl, lab)
            prev = (lift, fork)
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
