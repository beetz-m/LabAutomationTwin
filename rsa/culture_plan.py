"""From the culture plan to Cell 01: the abstract plan over the cultures, its physical and knowledge change, its mapping
to the laboratory, and the feasibility of the object transports and the machine tending it needs.

  1. The culture plan (registry/lab/culture_plan.ldl) says only what is done to the cultures, how they are observed,
     interpreted and analysed. Every action states a physical and a knowledge effect; the order is derived from causal
     links over both.
  2. Executing it on Cell 01's culture surrogate (twin/culture, ILLUSTRATIVE, D016) gives the physical trajectories of
     the cultures and the knowledge change: the belief over M1-M3 before and after the analysis, and the information
     actually gained against the 0.5 bit required.
  3. The mapping refines culture actions into lab action designators (challenge_rescue.ldl) and those into instrument
     roles and devices (rsa/ldl.py); the lab order must be the projection of the culture order.
  4. Feasibility of the transports and the machine tending, per trip, with the evidence for each verdict: knowledge
     (facts, component records, layout reach), plan (clingo), proof (z3), projection (kernel), simulation (symbolic run)
     and physics (Isaac run). What none of these covers is listed as open.

    env_cad/bin/python -m rsa.culture_plan      # rsa/out/culture_plan.json
"""

from __future__ import annotations

import itertools
import json
import math
import os
import sys
from typing import Any, Dict, List

import numpy as np
import yaml

from .ldl import LAB, OUT, World, check, dslots, dvar, fmt, is_desig, items, parse, slot, slot_l

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EFFECTS = ("physical", "knowledge")


# ------------------------------------------------------------------------------------------------- the culture plan
def sub(a, r) -> bool:
    """Does description a entail r? (variables compared by name: one plan, no instantiation)."""
    if isinstance(r, str):
        return a == r
    if is_desig(r):
        if not (is_desig(a) and a[1] == r[1]):
            return False
        if dvar(r) and dvar(a) != dvar(r):
            return False
        return all(any(as_[0] == rs[0] and all(any(sub(av, rv) for av in as_[1:]) for rv in rs[1:]) for as_ in dslots(a))
                   for rs in dslots(r))
    return isinstance(a, list) and a[:1] == r[:1] and all(any(sub(av, rv) for av in a[1:]) for rv in r[1:])


def load_plan(text):
    root = parse(text)[0]
    get = lambda n: slot_l(root[2:], n) or [n]  # noqa: E731
    steps = []
    for s in get("steps")[1:]:
        if not (isinstance(s, list) and s and s[0] in ("a", "an")):
            continue
        st = dict(var=dvar(s), type=slot(s, "type")[1], text=fmt(s),
                  slots={x[0]: " ".join(fmt(v) for v in x[1:]) for x in dslots(s) if x[0] not in ("type", "requires") + EFFECTS})
        for c in ("requires",) + EFFECTS:
            st[c] = items(slot(s, c) or [c])
        steps.append(st)
    return dict(root=root, question=fmt(get("question")[1]) if len(get("question")) > 1 else None,
                entities={dvar(e): fmt(e) for e in get("entities")[1:]}, goal=items(get("goal")),
                given=items(get("given")), prevents=items(get("prevents")), maintains=items(get("maintains")), steps=steps)


def derive(P):
    links, unsupported, establish = [], [], []
    for s in P["steps"]:
        for it in s["requires"]:
            r = it["cond"]
            prod = [("start", "given") for g in P["given"] if sub(g["cond"], r)]
            prod += [(p["var"], kind) for p in P["steps"] if p is not s for kind in EFFECTS
                     if any(sub(a["cond"], r) for a in p[kind])]
            if prod:
                links += [dict(frm=f, to=s["var"], kind=k, cond=fmt(r)) for f, k in dict.fromkeys(prod)]
            elif it["ann"].get(":establishable"):
                establish.append(dict(step=s["var"], cond=fmt(r)))
            else:
                unsupported.append(dict(step=s["var"], cond=fmt(r)))
    V = [s["var"] for s in P["steps"]]
    before = {v: set() for v in V}
    for l in links:
        if l["frm"] != "start":
            before[l["to"]].add(l["frm"])
    for _ in V:
        for v in V:
            for u in list(before[v]):
                before[v] |= before[u]
    lt = lambda a, b: a in before[b]  # noqa: E731
    hasse = sorted({(l["frm"], l["to"]) for l in links if l["frm"] != "start"
                    and not any(lt(l["frm"], m) and lt(m, l["to"]) for m in V)})
    level = {}
    for v in V:                         # longest path from the start
        level[v] = max([level.get(u, 0) + 1 for u in before[v]], default=0) if all(u in level for u in before[v]) else None
    for _ in V:
        for v in V:
            if level[v] is None and all(level.get(u) is not None for u in before[v]):
                level[v] = max([level[u] + 1 for u in before[v]], default=0)
    exts = sum(1 for p in itertools.permutations(V) if all(not lt(p[j], p[i]) for i in range(len(p)) for j in range(i + 1, len(p)))) \
        if len(V) <= 10 else None
    return dict(links=links, unsupported=unsupported, establish=establish, hasse=hasse, level=level,
                cyclic=[v for v in V if v in before[v]], before={k: sorted(v) for k, v in before.items()}, extensions=exts)


# ------------------------------------------------------------------------------------------------- physical and knowledge change
def execute_on_surrogate(plan_json):
    """Run the culture plan on Cell 01's surrogate; observe, interpret, analyse. ILLUSTRATIVE (D016)."""
    sys.path.insert(0, ROOT)
    from twin.culture import eig as EIG
    from twin.culture.model import CultureWorld, morphology
    sel = plan_json["selected"]
    W = CultureWorld(wells=["cr", "cc", "ck"], seed=17)
    uL = lambda au: au / 0.05  # noqa: E731   (stock concentration 0.05 au/uL, registry reagents; ILLUSTRATIVE)
    W.dispense("cr", "challenge", uL(sel["dose_au"]), 0.0)
    W.dispense("cc", "challenge", uL(sel["dose_au"]), 0.0)
    W.advance(sel["delay_h"])
    W.dispense("cr", "rescue", uL(sel["rescue_au"]))
    W.advance(72 - sel["delay_h"])
    traj = {k: [dict(t_h=h["t_h"], I=round(h["I"], 4), P=round(h["P"], 4), V=round(h["V"], 4),
                     radius_um=round(h["radius_um"], 2)) for h in W.wells[k].history[::4]] for k in ("cr", "cc", "ck")}
    sig = EIG._sigma_radius()
    rng = np.random.default_rng(72)
    truth = {k: morphology(*W.wells[k].x[[0, 3]])["radius_um"] for k in ("cr", "cc", "ck")}
    y = {k: float(truth[k] + rng.normal(0, sig)) for k in truth}
    pri = {m: EIG.sample_prior(m, np.random.default_rng(i), n=400) for i, m in enumerate(EIG.MODELS)}
    pM = {m: 1 / 3 for m in EIG.MODELS}
    post = EIG.posterior_over_models(pri, pM, sel["dose_au"], sel["delay_h"], [y["cr"]], [y["cc"]])
    H = lambda p: -sum(v * math.log2(v) for v in p.values() if v > 0)  # noqa: E731
    ig = sum(v * math.log2(v / pM[m]) for m, v in post.items() if v > 0)
    return dict(trajectories=traj, sigma_um=sig, true_radius_um={k: round(v, 2) for k, v in truth.items()},
                observed_radius_um={k: round(v, 2) for k, v in y.items()},
                effect_um=round(y["cr"] - y["cc"], 2), predicted=sel["predicted_effect_um"],
                prior=pM, posterior={m: round(v, 4) for m, v in post.items()},
                entropy_before_bit=round(H(pM), 4), entropy_after_bit=round(H(post), 4),
                information_gain_bit=round(ig, 4), expected_gain_bit=sel["eig_bits"], required_bit=plan_json["requirement_bits"],
                control_baseline_um=round(180 + 90 * float(W.wells["ck"].history[0]["V"]), 2))


# ------------------------------------------------------------------------------------------------- mapping to the lab
REFINES = {"challenging": "intervening", "rescuing": "intervening", "growing": "incubating", "observing": "measuring",
           "interpreting": None, "analysing": None}
COMPUTATION = {"interpreting": "culture SDT image analysis (twin/culture/optics.analyse): radius from the calibrated pixel size",
               "analysing": "posterior over M1-M3 (twin/culture/eig.posterior_over_models) on the rescued - comparator radius"}


def mapping(P, D, lab):
    E = lab["E"]
    role_of = {v: slot(parse(t)[0], "role")[1] for v, t in P["entities"].items() if "culture" in t}
    well_var = {}
    for v, d in E.decls.items():
        if d[1] == "well":
            well_var[slot(d, "role")[1]] = v
    vessel = {c: dict(role=r, lab_var=well_var[r], well=E.ref[well_var[r]].split(":")[1], plate=E.ref["?p"].split(":")[1])
              for c, r in role_of.items()}
    rows, ref = [], {}
    for s in P["steps"]:
        lt = REFINES[s["type"]]
        if lt is None:
            rows.append(dict(culture_step=s["var"], type=s["type"], lab_step=None, lab_type=None,
                             realised_by=COMPUTATION[s["type"]], device=None))
            continue
        cand = []
        for t in E.steps:
            if t["type"] != lt:
                continue
            if lt == "intervening":
                ok = (E.ref[t["slots"]["into"]] == E.ref[vessel[s["slots"]["culture"]]["lab_var"]]
                      and t["slots"]["substance"] in ("?ch" if s["type"] == "challenging" else "?rs",)
                      and t["slots"]["at"] == s["slots"]["at"])
            elif lt == "incubating":
                ok = t["slots"]["from"] == s["slots"]["from"] and t["slots"]["to"] == s["slots"]["to"]
            else:
                ok = E.ref[t["slots"]["of"]] == E.ref[vessel[s["slots"]["culture"]]["lab_var"]]
            if ok:
                cand.append(t)
        t = cand[0] if len(cand) == 1 else None
        ins = next((i for i in lab["instruments"] if i and t and i["step"] == t["var"]), None)
        ref[s["var"]] = t["var"] if t else None
        rows.append(dict(culture_step=s["var"], type=s["type"], lab_step=t["var"] if t else None, lab_type=lt,
                         lab_text=t["text"] if t else None, ambiguous=len(cand) != 1,
                         process=ins["process"] if ins else None,
                         device=[a["device"] for a in ins["answers"]] if ins else None,
                         slot=[a["slot"] for a in ins["answers"]] if ins else None))
    # order preservation: the lab order is the projection of the culture order onto the refined steps
    proj = sorted({(ref[a], ref[b]) for a, b in D["hasse"] if ref.get(a) and ref.get(b)})
    lab_hasse = sorted(tuple(e) for e in lab["hasse"])
    # transitive projection (a culture edge may pass through a computation step; none does here)
    return dict(vessels=vessel, rows=rows, projected_order=proj, lab_order=lab_hasse, order_preserved=proj == lab_hasse)


# ------------------------------------------------------------------------------------------------- feasibility
def feasibility(world, lab, plan_json):
    from .kb import C01_COMPONENTS, KB
    kb: KB = world.kb
    lay = json.load(open(os.path.join(ROOT, "scenes", "layout_p1.json")))
    reach = lay["reach"]
    sdt = world.sdt
    comps = {d: yaml.safe_load(open(os.path.join(C01_COMPONENTS, f + ".yaml")))
             for d, f in (("l10", "L10_Incubator"), ("l12", "L12_LiquidHandler"), ("l17", "L17_BrightFieldImager"))}
    trails = {n: json.load(open(os.path.join(OUT, f"trail_{n}.json")))["entries"] for n in ("nominal", "isaac_nominal")
              if os.path.exists(os.path.join(OUT, f"trail_{n}.json"))}
    window = plan_json["window_s"]
    sessions = []
    seat_class = lambda path: "PlateSeatPose" if f"lab1{path}#entity>)" in sdt and "PlateSeatPose" in "".join(  # noqa: E731
        l for l in sdt.split("\n") if f"lab1{path}#entity>)" in l and "ClassAssertion" in l) else None
    SEAT_PATH = dict(l10="/World/Cell01/Stations/L10_Incubator/transfer_station", l12="/World/Cell01/Stations/L12_LiquidHandler/plate_nest",
                     l17="/World/Cell01/Stations/L17_BrightFieldImager/plate_load_frame", handovernest="/World/Cell01/Fixtures/HandoverNest_R01_R02/handover_frame")
    REACH = dict(r01={"l10": reach["L10"], "handovernest": reach["handover_nest_R01_R02"]},
                 r02={"l12": reach["L12"], "l17": reach["L17"], "handovernest": {"ok": True, "note": "rail-side handover (layout P1)"},
                      "t01": reach["dock_T01"]})
    durations = {}
    for name, E_ in trails.items():
        durations[name] = {}
        for e in E_:
            if e["category"] == "run_session" and e["transition"] == "grounded":
                durations[name].setdefault(e["bindings"]["session"], {})["t0"] = e["t_sim"]
            if e["category"] == "run_session" and e["transition"] == "executed":
                s_ = next(k for k, v in durations[name].items() if "t1" not in v)
                durations[name][s_]["t1"] = e["t_sim"]
    for s in plan_json["sessions"]:
        dev = s["device"]
        legs_out = [(l["robot"], l["src"], l["dst"]) for l in s["route_out"]]
        back = kb.route(dev, "l10")
        legs = legs_out + [tuple(x) for x in back.value]
        tending = {}
        for st in s["steps"]:
            if st.get("level") in ("motion",) or "robot" in st and st["primitive"] in ("tool_couple",):
                continue
            d = st.get("device")
            if d and d != "cell01":
                tending.setdefault(d, [])
                if not tending[d] or tending[d][-1] != st["primitive"]:
                    tending[d].append(st["primitive"])
        checks = []
        # transport
        for r, a, b in legs:
            g = [f"serves({r},{a})", f"serves({r},{b})", f"holds_plate({a})", f"holds_plate({b})"]
            ok = all(kb.holds("serves", r, x) for x in (a, b)) and all(kb.holds("holds_plate", x) for x in (a, b))
            reach_ok = all((REACH.get(r, {}).get(x) or {}).get("serviceable", (REACH.get(r, {}).get(x) or {}).get("ok", False)) for x in (a, b))
            seats = all(seat_class(SEAT_PATH[x]) for x in (a, b))
            checks.append(dict(kind="transport", what=f"{r.upper()} carries the plate {a.upper()} → {b.upper()}",
                               ok=ok and reach_ok and seats,
                               evidence=["knowledge: " + ", ".join(g),
                                         "layout reach: " + "; ".join(f"{x.upper()} " + json.dumps(REACH.get(r, {}).get(x)) for x in (a, b)),
                                         "SDT: both seats are PlateSeatPose (SBS plate)" if seats else "SDT: seat class missing"]))
        if any(r == "r02" for r, _, _ in legs):
            checks.append(dict(kind="transport", what="R02 couples tool T01 for the plate (each trip; freshness rule F2)",
                               ok=kb.holds("requires_tool", "r02", "t01") and reach["dock_T01"]["ok"],
                               evidence=["knowledge: requires_tool(r02,t01), tool_pose(t01,tooling_automatictoolchanger_dock_t01)",
                                         f"layout reach: dock_T01 {json.dumps(reach['dock_T01'])}",
                                         "tool_compatible: T01 does not contact the culture (contacts_culture: t03, t04 only)"]))
        # machine tending
        CONTRACT = dict(l10="incubate", l12="dose_well", l17="image_well")
        HOW = {"plate identity verified": "verify_identity at L10 in the same trip (barcode, observed)",
               "plate ID verified": "verify_identity at L10 in the same trip (barcode, observed)",
               "plate verified and seated": "verify_identity at L10; L17 seat sensors (partial: no lateral shift, F17)",
               "well bound": "well_pose(<well>,pipette, …/Interfaces/pipette_target_frame) (SDT)",
               "well coordinate bound": "well_pose(<well>,imaging, …/Interfaces/imaging_target_frame) (SDT)",
               "reagent lot verified": "registry reagents (lot SIM-LOT-A/B) + reagent_pose(…, rack_1_pos_1/2)",
               "tip attached and compatible": "tip_pick from tip_rack(l12, rack_1) before aspirate",
               "device calibrated": "ASSUMED: no L12 calibration record in the twin",
               "calibration valid": "calibrated(l17) observed; else a QC calibration on L21 is inserted (establishable)",
               "device healthy": "ASSUMED: no health monitor beyond the device's own monitors",
               "incubator available": "L10 transfer station free (single plate)",
               "environment valid": "wait_environment at L10 before store (monitored: temperature, CO2, humidity, gate)",
               "slot reserved": "L10 slot 2 (inventory), held across the experiment"}
        for d, seq in tending.items():
            con = next((c for c in comps.get(d, {}).get("action_contracts") or [] if c["name"] == CONTRACT.get(d)), None)
            caps = kb.capabilities(d)
            pre = [dict(pre=p, how=HOW.get(p, "not mapped")) for p in (con or {}).get("preconditions", [])]
            assumed = [p["pre"] for p in pre if p["how"].startswith("ASSUMED") or p["how"] == "not mapped"]
            checks.append(dict(kind="tending", what=f"{d.upper()}: {' → '.join(seq)}",
                               ok=bool(con) and not [p for p in pre if p["how"] == "not mapped"],
                               conditional=assumed,
                               evidence=[f"capabilities({d}): {', '.join(caps)}",
                                         f"contract {CONTRACT.get(d)}: " + "; ".join(f"{p['pre']} ← {p['how']}" for p in pre)]))
        # time
        sym = durations.get("nominal", {}).get(s["session"], {})
        isa = durations.get("isaac_nominal", {}).get(s["session"], {})
        tsym = round(sym["t1"] - sym["t0"], 1) if "t1" in sym else None
        tisa = round(isa["t1"] - isa["t0"], 1) if "t1" in isa else None
        planned = s["duration_s"] + s.get("prep_s", 0)
        checks.append(dict(kind="time", what=f"trip outside the incubator ≤ {window:.0f} s (planner margin 20 %: ≤ {window / 1.2:.0f} s)",
                           ok=planned * 1.2 <= window and (tisa is None or tisa <= window),
                           evidence=[f"plan (clingo, z3-validated): {planned:.1f} s", f"simulation (symbolic run): {tsym} s",
                                     f"physics (Isaac twin): {tisa} s"]))
        sessions.append(dict(session=s["session"], t_h=s["t_h"], device=dev, material=s["material"],
                             legs=[list(l) for l in legs], tending=tending, checks=checks,
                             ok=all(c["ok"] for c in checks)))
    # culture-time precision: when within the trip each culture action happens
    prec = []
    if "nominal" in trails:
        E_ = trails["nominal"]
        sess_t0 = {}
        for e in E_:
            if e["category"] == "run_session" and e["transition"] == "grounded":
                cur = e["bindings"]["session"]
                sess_t0[cur] = (e["t_sim"], e["bindings"]["t_h"])
            if e["category"] in ("dispense", "image_well") and e["transition"] == "executed":
                t0, th = sess_t0[cur]
                prec.append(dict(session=cur, what=e["category"], well=next((x["value"] for x in e.get("evidence") or [] if x["kind"] == "well"), None),
                                 offset_s=round(e["t_sim"] - t0, 1), culture_time_h=th))
    open_items = [
        "reagent stock and tip inventory: no inventory model in the twin (3 tips and 51 uL challenge / 14 uL rescue are needed; ILLUSTRATIVE)",
        "L12 calibration: no calibration record; the dose_well precondition 'device calibrated' is assumed",
        "L12 well registration is only partly detected (seating, not dispense position): the dose's trust gap (process model)",
        "L17 lateral seating is only partly detected (F17); the prescribed re-seat repair is not yet in the kernel",
        "real device timing: the durations are the twin's controllers', not vendor data (no manufacturer CAD or specs acquired)",
        "humidity and CO2 are monitored by L10's contract but not simulated by the twin's incubator model",
    ]
    return dict(sessions=sessions, precision=prec, open=open_items,
                plan_validation=dict(planner="clingo optimal plan plan_g050 (151 steps)", z3="make e2m: 7 plans z3-validated, PASS",
                                     kernel="projection succeeded before each trip (projection_succeeds ENFORCED)",
                                     simulation="symbolic run executed, R/V ok", physics="Isaac run executed, R/V ok, 10/10 CQ"),
                ok=all(s["ok"] for s in sessions))


def main(argv):
    world = World("g050")
    P = load_plan(open(os.path.join(LAB, "culture_plan.ldl")).read())
    D = derive(P)
    lab = check(open(os.path.join(LAB, "challenge_rescue.ldl")).read(), open(os.path.join(LAB, "contracts.ldl")).read(), world)
    plan_json = world.plan
    K = execute_on_surrogate(plan_json)
    Mp = mapping(P, D, lab)
    F = feasibility(world, lab, plan_json)
    print(f"[culture] {len(P['steps'])} culture actions, {len(D['links'])} causal links "
          f"({sum(l['kind'] == 'physical' for l in D['links'])} physical, {sum(l['kind'] == 'knowledge' for l in D['links'])} knowledge, "
          f"{sum(l['kind'] == 'given' for l in D['links'])} from the given state); order {D['hasse']}; "
          f"unsupported {D['unsupported']}; to establish {[e['cond'] for e in D['establish']][:1]}; linear extensions {D['extensions']}")
    print(f"[culture] surrogate: observed radius {K['observed_radius_um']} um, effect {K['effect_um']} um "
          f"(predicted M1 {K['predicted']['M1_graded']['effect_um']:.1f}, M2 {K['predicted']['M2_threshold']['effect_um']:.1f}, "
          f"M3 {K['predicted']['M3_protective']['effect_um']:.1f}); posterior {K['posterior']}; entropy {K['entropy_before_bit']} -> "
          f"{K['entropy_after_bit']} bit; information gained {K['information_gain_bit']} bit (expected {K['expected_gain_bit']}, required {K['required_bit']})")
    for r in Mp["rows"]:
        print(f"[map] {r['culture_step']:4} {r['type']:12} -> {r['lab_step'] or '-':4} {r['lab_type'] or 'computation':11} "
              f"{(r.get('process') or '') + ' ' + str(r.get('device') or r.get('realised_by'))}")
    print(f"[map] vessels {{{', '.join(f'{c}: {v['plate']}/{v['well']}' for c, v in Mp['vessels'].items())}}}; "
          f"lab order = projection of the culture order: {Mp['order_preserved']}")
    for s in F["sessions"]:
        print(f"[feasible] {s['session']} ({s['t_h']} h, {s['device'].upper()}): {'OK' if s['ok'] else 'NOT OK'}; legs "
              f"{[f'{r.upper()} {a}->{b}' for r, a, b in s['legs']]}; conditional {sorted({c for x in s['checks'] for c in x.get('conditional', [])})}")
    out = dict(plan=dict(question=P["question"], entities=P["entities"], goal=[fmt(g["cond"]) for g in P["goal"]],
                         steps=[{k: (v if k not in ("requires",) + EFFECTS else [dict(cond=fmt(i["cond"]), ann=i["ann"]) for i in v])
                                 for k, v in s.items()} for s in P["steps"]]),
               derived=D, knowledge=K, mapping=Mp, feasibility=F,
               lab_steps=[dict(var=s["var"], type=s["type"], text=s["text"]) for s in lab["E"].steps])
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, "culture_plan.json"), "w"), indent=1, default=str)
    ok = not D["unsupported"] and not D["cyclic"] and Mp["order_preserved"] and F["ok"]
    print(f"[culture] {'PASS' if ok else 'FAIL'}: plan well-formed {not D['unsupported'] and not D['cyclic']}, "
          f"order preserved by the mapping {Mp['order_preserved']}, transports and tending feasible {F['ok']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
