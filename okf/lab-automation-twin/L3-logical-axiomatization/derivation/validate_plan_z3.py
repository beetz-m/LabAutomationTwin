"""Independent SMT validation of a derived plan (z3): the [SMT] side of axioms E2M1-E2M9.

The answer-set program DERIVES a plan; this script CHECKS it with a separate encoding of what the steps mean. Each trip
is unrolled into z3 state variables (plate location, each robot's position and gripper, R02's tool, L10 / L17
shuttle-stage state, L12's tip and aspirated reagent, environment / QC / identity flags) with one transition per step.
A theorem holds when the negation of its claim is UNSAT under the transitions.

  V1 executability / preservation (E2M9 = DR1-DR3): every step's precondition holds and each trip ends with the plate
     stored in its home, grippers empty, no robot in a seat, for EVERY initial tool state and stage state (symbolic).
  V2 safety (E2M8): S1 no L12 operation while a robot is in the deck seat; S2 environment checked before store;
     S3 image only with valid calibration or a prior QC; S6 interlocks closed; S7 identity verified first.
  V3 time (S5): every trip fits the window for ALL step durations within +-20 % of the trace estimates.
  V4 realisation (E2M3/E2M4): the doses dispensed (well, reagent, au) and wells imaged are exactly those the selected
     experiment requires, in sessions at t0, t0 + delay, t0 + 72 h; arms disjoint, n / n / >=1 control (S9).
  V5 gain and least cost (E2M1): EIG(selected) >= g; no candidate meeting g has a lower optimum; ties broken by EIG.
Negative controls: ten mutated plans (each breaks one claim) must each be caught (SAT) with the expected theorem.

Run: env_cad/bin/python .../validate_plan_z3.py out/plan_g050.json      (writes out/proof_<tag>.json; exit 1 on failure)
"""

from __future__ import annotations

import copy
import json
import os
import sys

import clingo
import z3

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(os.path.dirname(HERE))
TOL = 0.20


def lab_facts(path):
    ctl = clingo.Control(["--warn=none"])
    ctl.load(path)
    ctl.ground([("base", [])])
    F = {}
    for a in ctl.symbolic_atoms:
        s = a.symbol
        F.setdefault(s.name, []).append(tuple(str(x) if x.type != clingo.SymbolType.Number else x.number
                                              for x in s.arguments))
    return F


class Trip:
    """Symbolic execution of one trip. Entities are interned as integers; the initial state is partly symbolic."""

    def __init__(self, lab, steps, window_s, tag):
        self.lab, self.steps, self.window, self.tag = lab, steps, window_s, tag
        self.ids = {}
        self.pre = []          # (label, step index, z3 condition)
        self.S = z3.Solver()

    def e(self, name):
        if name not in self.ids:
            self.ids[name] = len(self.ids) + 1
        return z3.IntVal(self.ids[name])

    def build(self, init_tool_free=True, init_stage_free=True):
        L, e, S = self.lab, self.e, self.S
        seat = {d: p for d, p in L["seat"]}
        seat_dev = {p: d for d, p in seat.items()}
        home = L["home"][0][0]
        shuttles = {d for (d,) in L.get("has_shuttle", [])}
        robots = sorted({r for r, _ in L["serves"]})
        req_tool = {r: t for r, t in L.get("requires_tool", [])}
        calibrated = {d for (d,) in L.get("calibrated", [])}
        airspace = {d for (d,) in L.get("airspace", [])}
        interlocks = bool(L.get("interlocks_closed"))
        appr = lambda p: e(f"appr:{p}")  # noqa: E731
        # initial state
        plate = e(f"inside:{home}")
        pos = {r: e(f"park:{r}") for r in robots}
        grip = {r: z3.BoolVal(False) for r in robots}
        tool = {}
        for r in robots:
            if r in req_tool:
                known = (r, req_tool[r]) in set(L.get("coupled", []))   # a stated assumption fixes the initial tool
                tool[r] = z3.Int(f"{self.tag}_tool0_{r}") if init_tool_free and not known else e(req_tool[r])
                S.add(z3.Or(tool[r] == e(req_tool[r]), tool[r] == e("none"), tool[r] == e("other")))
        presented = {d: (z3.Bool(f"{self.tag}_pres0_{d}") if init_stage_free and d != home else z3.BoolVal(False))
                     for d in shuttles}
        tip, loaded = z3.BoolVal(False), e("none")
        env_ok, ident, ilk = z3.BoolVal(False), z3.BoolVal(False), z3.BoolVal(False)
        qc = {d: z3.BoolVal(d in calibrated) for d, _ in L["seat"]}
        self.doses, self.images = [], []
        durs = []
        for i, st in enumerate(self.steps):
            t = st["term"]
            k = t[0]
            P = lambda lab, c: self.pre.append((lab, i, c))  # noqa: E731
            robot_in_seat = lambda d: z3.Or([pos[r] == e(seat[d]) for r in robots]) if d in seat else z3.BoolVal(False)  # noqa: E731
            if st.get("pos", 10000) >= 10000:      # preparation steps (< 10000) run before the plate leaves home
                durs.append(st["duration_s"])
            if k == "cmd":
                dev, c = t[1], t[2]
                cn = c[0] if isinstance(c, list) else c
                ca = c[1:] if isinstance(c, list) else []
                if dev in airspace and cn in ("tip_pick", "aspirate", "dispense", "tip_eject"):
                    P("S1 deck airspace clear", z3.Not(robot_in_seat(dev)))
                if cn == "check_interlocks":
                    P("S6 interlocks closed", z3.BoolVal(interlocks))
                    ilk = z3.BoolVal(True)
                elif cn == "verify_identity":
                    P("V1 identity read at home", plate == e(f"inside:{dev}"))
                    ident = z3.BoolVal(True)
                elif cn == "present":
                    P("V1 present: seat free", z3.Not(robot_in_seat(dev)))
                    P("S7 identity verified before release", ident)
                    P("S6 interlocks checked before motion", ilk)
                    plate = z3.If(plate == e(f"inside:{dev}"), e(seat[dev]), plate)
                    presented[dev] = z3.BoolVal(True)
                elif cn == "stow":
                    P("V1 stow: no robot in seat", z3.Not(robot_in_seat(dev)))
                    P("V1 stow: seat empty", plate != e(seat[dev]))
                    presented[dev] = z3.BoolVal(False)
                elif cn == "tip_pick":
                    P("V1 tip_pick: no tip", z3.Not(tip))
                    tip = z3.BoolVal(True)
                elif cn == "aspirate":
                    P("V1 aspirate: tip", tip)
                    P("V1 aspirate: plate on deck", plate == e(seat[dev]))
                    reag = next(r for r, p in L["reagent_pose"] if p == ca[0])
                    loaded = e(f"reagent:{reag}")
                elif cn == "dispense":
                    P("V1 dispense: plate on deck", plate == e(seat[dev]))
                    well = next(w for w, kind, p in L["well_pose"] if p == ca[0] and kind == "pipette")
                    reag = next(r for r, p in L["reagent_pose"] if self.steps[i - 1]["term"][2][1] == p)
                    P("V1 dispense: reagent aspirated", loaded == e(f"reagent:{reag}"))
                    self.doses.append((well, reag, ca[1]))
                    loaded = e("none")
                elif cn == "tip_eject":
                    P("V1 tip_eject: tip", tip)
                    tip = z3.BoolVal(False)
                elif cn == "load":
                    P("V1 load: plate presented on the stage", z3.And(plate == e(seat[dev]), presented[dev]))
                    P("V1 load: no robot in seat", z3.Not(robot_in_seat(dev)))
                    plate, presented[dev] = e(f"inside:{dev}"), z3.BoolVal(False)
                elif cn == "image_well":
                    P("V1 image: plate loaded", plate == e(f"inside:{dev}"))
                    P("S3 calibration valid", qc[dev])
                    self.images.append(next(w for w, kind, p in L["well_pose"] if p == ca[0] and kind == "imaging"))
                elif cn == "validate":
                    tgt = ca[0]
                    P("V1 validate: target imager free (the reference plate needs its stage)",
                      z3.And(plate != e(seat[tgt]), plate != e(f"inside:{tgt}"), z3.Not(robot_in_seat(tgt))))
                    qc[tgt] = z3.BoolVal(True)
                elif cn == "wait_environment":
                    env_ok = z3.BoolVal(True)
                elif cn == "store":
                    P("S2 environment valid before store", env_ok)
                    P("V1 store: plate on the presented shuttle", z3.And(plate == e(seat[dev]), presented[dev]))
                    P("V1 store: no robot in seat", z3.Not(robot_in_seat(dev)))
                    plate, presented[dev] = e(f"inside:{dev}"), z3.BoolVal(False)
                else:
                    P(f"V1 known command {cn}", z3.BoolVal(False))
                continue
            r = t[1]
            if r in req_tool and k != "tool_couple":
                P("V1 robot carries its required tool", tool[r] == e(req_tool[r]))
            if k in ("approach", "insert", "place", "retract", "transit") and r not in ("",):
                P("S6 interlocks checked before motion", ilk)
            if k == "tool_couple":
                P("V1 tool change with empty gripper", z3.Not(grip[r]))
                tool[r] = e(t[2])
            elif k == "approach":
                p = t[2][1]
                P("V1 approach from park or the same approach pose (long moves are transits)",
                  z3.Or(pos[r] == e(f"park:{r}"), pos[r] == appr(p)))
                pos[r] = appr(p)
            elif k == "insert":
                p = t[2]
                P("V1 insert from the seat's approach pose", pos[r] == appr(p))
                P("V1 insert: gripper empty", z3.Not(grip[r]))
                if seat_dev.get(p) in shuttles:
                    P("V1 insert: shuttle / stage presented", presented[seat_dev[p]])
                pos[r] = e(p)
            elif k == "grasp":
                P("V1 grasp: plate in the seat at the gripper", plate == pos[r])
                P("V1 grasp: gripper empty", z3.Not(grip[r]))
                grip[r], plate = z3.BoolVal(True), e(r)
            elif k == "lift":
                P("V1 lift: holding the plate", z3.And(grip[r], plate == e(r)))
                pos[r] = z3.If(z3.Or([pos[r] == e(s) for s in seat_dev]),
                               z3.Sum([z3.If(pos[r] == e(s), appr(s) - e(s), 0) for s in seat_dev]) + pos[r], pos[r])
            elif k == "transit":
                a, b = t[2][1], t[3][1]
                P("V1 transit starts at the source approach pose", pos[r] == appr(a))
                pos[r] = appr(b)
            elif k == "place":
                q = t[2]
                P("V1 place from the target approach pose", pos[r] == appr(q))
                P("V1 place: holding the plate", z3.And(grip[r], plate == e(r)))
                if seat_dev.get(q) in shuttles:
                    P("V1 place: shuttle / stage presented", presented[seat_dev[q]])
                pos[r], plate = e(q), e(q)
            elif k == "release":
                P("V1 release in a seat", z3.Or([pos[r] == e(s) for s in seat_dev]))
                grip[r] = z3.BoolVal(False)
            elif k == "retract":
                q = t[2][1]
                P("V1 retract from the seat", pos[r] == e(q))
                P("V1 retract with an empty gripper", z3.Not(grip[r]))
                pos[r] = appr(q)
            else:
                P(f"V1 known motion {k}", z3.BoolVal(False))
        n = len(self.steps)
        self.pre.append(("V1 trip ends with the plate stored at home", n, plate == e(f"inside:{home}")))
        self.pre.append(("V1 trip ends with empty grippers", n, z3.And([z3.Not(grip[r]) for r in robots])))
        self.pre.append(("V1 trip ends with no robot in a seat", n,
                         z3.And([pos[r] != e(s) for r in robots for s in seat_dev])))
        trip = [st for st in self.steps if st.get("pos", 10000) >= 10000]   # preparation steps (< 10000) excluded
        if trip:
            self.pre.append(("S6 the trip starts with the interlock check", 0,
                             z3.BoolVal(trip[0]["term"][2] == "check_interlocks")))
            self.pre.append(("S7 identity verified before any motion", 1,
                             z3.BoolVal(len(trip) > 1 and trip[1]["term"][2] == "verify_identity")))
        # V3 time: symbolic durations within +-TOL of the estimates (window-relevant steps only)
        n = len(durs)
        self.dv = [z3.Real(f"{self.tag}_d{i}") for i in range(n)]
        self.time_ok = z3.Sum(self.dv) <= self.window if n else z3.BoolVal(True)
        self.time_bounds = [z3.And(self.dv[i] >= (1 - TOL) * d, self.dv[i] <= (1 + TOL) * d) for i, d in enumerate(durs)]
        self.nominal_s = sum(durs)
        return self

    def check(self):
        """UNSAT of 'some precondition fails' = all hold for every symbolic initial state. Returns violations."""
        S = self.S
        S.push()
        S.add(z3.Or([z3.Not(c) for _, _, c in self.pre]))
        r = S.check()
        viol = []
        if r == z3.sat:
            m = S.model()
            viol = [(lab, i) for lab, i, c in self.pre if z3.is_false(m.eval(c, model_completion=True))]
        S.pop()
        S.push()
        S.add(self.time_bounds)
        S.add(z3.Not(self.time_ok))
        rt = S.check()
        S.pop()
        if rt == z3.sat:
            viol.append((f"S5 trip within the window for all durations within +-{int(TOL * 100)} %", -1))
        return viol, str(r), str(rt)


def theorems(plan, lab):
    """All claims of one plan; returns {theorem: {"holds": bool, "detail": ...}}."""
    T = {}
    trips = []
    for se in plan["sessions"]:
        tr = Trip(lab, se["steps"], plan["window_s"], se["id"]).build()
        viol, r, rt = tr.check()
        trips.append((se, tr, viol))
    groups = {"V1 executability / preservation": "V1", "V2 safety S1 S2 S3 S6 S7": ("S1", "S2", "S3", "S6", "S7"),
              "V3 time window (S5), durations +-20 %": "S5"}
    for name, pref in groups.items():
        bad = [(se["id"], lab_, i) for se, _, viol in trips for lab_, i in viol if lab_.startswith(pref)]
        T[name] = dict(holds=not bad, violations=bad[:6],
                       checked=sum(1 for _, tr, _ in trips for lab_, _, _ in tr.pre if lab_.startswith(pref))
                       if pref != "S5" else len(trips))
    # V4 realisation
    sel = plan["selected"]
    roles = {k: [w.lower() for w in v] for k, v in plan["wells"].items()}
    need = {"s0": sorted((w, "challenge", int(round(sel["dose_au"] * 100))) for w in roles.get("rescued", []) +
                         roles.get("comparator", [])),
            "s1": sorted((w, "rescue", int(round(sel["rescue_au"] * 100))) for w in roles.get("rescued", [])),
            "s2": []}
    imgs_need = sorted(w for v in roles.values() for w in v)
    got = {"s0": [], "s1": [], "s2": []}
    imgs = []
    for se, tr, _ in trips:
        got[se["session"]] += tr.doses
        imgs += tr.images if se["session"] == "s2" else []
    times = {se["session"]: se["t_h"] for se in plan["sessions"]}
    ok4 = all(sorted(got[s]) == need[s] for s in need) and sorted(imgs) == imgs_need and \
        times.get("s0") == 0 and times.get("s1") == sel["delay_h"] and times.get("s2") == 72
    free = {w for (w, _x) in lab["free"]}
    arms_ok = (len(roles.get("rescued", [])) == sel["reps"] == len(roles.get("comparator", []))
               and len(roles.get("control", [])) >= 1
               and len({w for v in roles.values() for w in v}) == sum(len(v) for v in roles.values())
               and all(w in free for v in roles.values() for w in v))
    T["V4 realisation (doses, images, session times)"] = dict(holds=ok4, doses=got, images=imgs, times=times)
    T["V4b arms E2M3 + control S9"] = dict(holds=arms_ok, wells=plan["wells"])
    # V5 gain and least cost, as an SMT problem over the candidate table
    g = plan["requirement_bits"]
    eig = plan["candidate_eig_bits"]
    opt = {c: v for c, v in plan["candidate_optima"].items() if v is not None}
    s = z3.Solver()
    x = z3.String("x")
    cost_sel, eig_sel = plan["cost"]["value"], eig[sel["id"]]
    # exists a better candidate: meets g, cheaper, or as cheap and more informative
    s.add(z3.Or([z3.And(x == z3.StringVal(c), z3.BoolVal(eig[c] >= g),
                        z3.Or(v < cost_sel, z3.And(v == cost_sel, eig[c] > eig_sel))) for c, v in opt.items()]
                + [z3.BoolVal(False)]))
    better = s.check()
    T["V5 gain met (EIG >= g)"] = dict(holds=eig_sel >= g, eig_bits=eig_sel, required_bits=g)
    T["V5b least cost, then max EIG, over all candidates meeting g"] = dict(
        holds=better == z3.unsat and set(opt) == {c for c in eig if eig[c] >= g}, smt=str(better),
        compared=len(opt))
    return T, trips


def mutate(plan, kind, lab):
    P = copy.deepcopy(plan)
    s0 = P["sessions"][0]["steps"]
    if kind == "N1 retract after the first L12 tip pick":
        i = next(j for j, st in enumerate(s0) if st["term"][0] == "retract" and "l12" in str(st["term"]))
        j = next(j for j, st in enumerate(s0) if st["term"][0] == "cmd" and st["term"][2][0] == "tip_pick")
        s0.insert(j, s0.pop(i))
    elif kind == "N2 environment wait removed":
        P["sessions"][0]["steps"] = [st for st in s0 if st["term"][0] != "cmd" or st["term"][2] != "wait_environment"]
    elif kind == "N3 L17 calibration expired, no QC step":
        lab = copy.deepcopy(lab)
        lab["calibrated"] = []
        for se in P["sessions"]:
            se["steps"] = [st for st in se["steps"] if not (st["term"][0] == "cmd" and isinstance(st["term"][2], list)
                                                          and st["term"][2][0] == "validate")]
    elif kind == "N4 identity check removed":
        P["sessions"][0]["steps"] = [st for st in s0 if st["term"][0] != "cmd" or st["term"][2] != "verify_identity"]
    elif kind == "N5 R02 transit to L12 removed":
        i = next(j for j, st in enumerate(s0) if st["term"][0] == "transit" and st["term"][1] == "r02")
        s0.pop(i)
    elif kind == "N6 tool change removed (initial tool unknown)":
        P["sessions"][0]["steps"] = [st for st in s0 if st["term"][0] != "tool_couple"]
        lab = copy.deepcopy(lab)
        lab["coupled"] = []
    elif kind == "N7 challenge dose changed (0.85 -> 0.65 au)":
        st = next(st for st in s0 if st["term"][0] == "cmd" and st["term"][2][0] == "dispense")
        st["term"][2][2] = 65
    elif kind == "N8 selected candidate below the requirement":
        low = min(P["candidate_eig_bits"], key=P["candidate_eig_bits"].get)
        P["selected"] = dict(P["selected"], id=low)
    elif kind == "N9 window shortened to 250 s":
        P["window_s"] = 250.0
    elif kind == "N10 control well not imaged":
        s2 = next(se for se in P["sessions"] if se["session"] == "s2")["steps"]
        ctrl = P["wells"]["control"][0].lower()
        s2[:] = [st for st in s2 if not (st["term"][0] == "cmd" and st["term"][2][0] == "image_well"
                                         and ctrl in st["term"][2][1])]
    return P, lab


NEG = {"N1 retract after the first L12 tip pick": "V2", "N2 environment wait removed": "V2",
       "N3 L17 calibration expired, no QC step": "V2", "N4 identity check removed": "V2",
       "N5 R02 transit to L12 removed": "V1", "N6 tool change removed (initial tool unknown)": "V1",
       "N7 challenge dose changed (0.85 -> 0.65 au)": "V4", "N8 selected candidate below the requirement": "V5",
       "N9 window shortened to 250 s": "V3", "N10 control well not imaged": "V4"}


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out", "plan_g050.json")
    plan = json.load(open(path))
    lab = lab_facts(os.path.join(MOD, plan["facts_file"]))
    T, trips = theorems(plan, lab)
    ok = all(v["holds"] for v in T.values())
    for k, v in T.items():
        print(f"[z3] {'PROVED' if v['holds'] else 'FAILED'}  {k}" +
              ("" if v["holds"] else f"  {v.get('violations') or ''}"))
    for se, tr, _ in trips:
        print(f"[z3]   {se['id']}: {len(tr.steps)} steps, {len(tr.pre)} preconditions, nominal {tr.nominal_s:.1f} s, "
              f"worst case {(1 + TOL) * tr.nominal_s:.1f} s <= {plan['window_s']:.0f} s")
    neg = {}
    if "--no-negative" not in sys.argv:
        for kind, expect in NEG.items():
            P, lab2 = mutate(plan, kind, lab)
            Tn, _ = theorems(P, lab2)
            failed = [k for k, v in Tn.items() if not v["holds"]]
            caught = any(k.startswith(expect) for k in failed)
            neg[kind] = dict(caught=caught, expected=expect, failed=failed,
                             first_violation=next((v.get("violations", [None])[0] for k, v in Tn.items()
                                                   if not v["holds"] and v.get("violations")), None))
            print(f"[z3] negative control {kind}: {'caught' if caught else 'MISSED'} by {failed}")
        ok = ok and all(v["caught"] for v in neg.values())
    out = dict(plan=os.path.basename(path), theorems=T, negative_controls=neg, all_passed=ok, z3=z3.get_version_string(),
               tolerance=TOL)
    dst = os.path.join(os.path.dirname(path), f"proof_{plan['tag']}.json")
    json.dump(out, open(dst, "w"), indent=1, default=str)
    print(f"[z3] {'ALL PROVED' if ok else 'FAILURES'}; negative controls caught "
          f"{sum(v['caught'] for v in neg.values())}/{len(neg)} -> {os.path.relpath(dst, MOD)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
