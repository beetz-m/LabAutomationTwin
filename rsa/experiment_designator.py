"""The challenge-rescue experiment as one entity designator: from the authored source to the culture actions and the
top-level plan.

The source (registry/lab/experiment.ldl) is organised by the experiment's logic: three cultures, each defined by its
treatment, kept under shared conditions and observed the same way; comparisons between cultures that differ in exactly
one exposure determine the effects, and the primary comparison updates the belief over the recovery models. It has no
variables and no lab entities.

  1. Check the logic: every comparison is between two cultures whose treatments differ in exactly one exposure, and
     that exposure is the one whose effect the comparison determines.
  2. Derive the culture actions: an intervention per exposure, growth between the treatment times, an observation and
     an interpretation per culture, an analysis per comparison (the validity analysis licenses the primary one).
     The result is a culture plan in the format of culture_plan.ldl, and its order is derived from causal links by
     rsa/culture_plan.py (nothing is ordered by hand).
  3. Compare it with registry/lab/culture_plan.ldl: which actions are the same, which are new, how the order changes,
     which effects the hand-written plan states that the experiment does not.
  4. Write the experiment designator performed by the top-level plan, with the placement the mapping to Cell 01 chose
     (plate, wells), the models' predictions, the checked single differences and the insights still to be filled in.

    env_cad/bin/python -m rsa.experiment_designator
      -> rsa/out/challenge_rescue_designator.lisp   (the top-level plan performing the experiment designator)
      -> rsa/out/experiment_culture_plan.ldl        (the derived culture actions)
"""

from __future__ import annotations

import json
import os
import re
import sys

from .culture_plan import derive, load_plan
from .ldl import LAB, OUT, dslots, fmt, is_desig, parse, slot
from .sexp_pretty import pretty

SRC = os.path.join(LAB, "experiment.ldl")


# ------------------------------------------------------------------------------------------------- reading the source
def slots_all(d, name):
    return [s for s in dslots(d) if s[0] == name]


def hours(t):
    """(culture-time 48 h) -> 48.0"""
    return float(t[1])


def load(path=SRC, root=None):
    root = root if root is not None else parse(open(path).read())[0]
    one = lambda n: (slot(root, n) or [n, None])[1]  # noqa: E731
    X = dict(root=root, question=one("question"), goal=one("goal"), belief=one("belief"),
             prevents=slot(root, "prevents")[1:], maintains=slot(root, "maintains")[1:],
             shared=one("shared-conditions"), insights=[s[1] for s in slots_all(root, "insight")])
    X["substances"] = {slot(s[1], "role")[1]: s[1] for s in slots_all(root, "substance")}
    X["cultures"] = {}
    for s in slots_all(root, "culture"):
        d = s[1]
        X["cultures"][slot(d, "role")[1]] = dict(desig=d, exposures=[
            dict(substance=slot(slot(e, "to")[1], "role")[1], dose=slot(e, "dose")[1:], at=slot(e, "at")[1])
            for e in (sl[1] for sl in slots_all(slot(d, "treatment")[1], "exposure"))])
    X["comparisons"] = {}
    for s in slots_all(root, "comparison"):
        d = s[1]
        a, b = (slot(c, "role")[1] for c in slot(d, "between")[1:])
        of = slot(slot(d, "determines")[1], "of")[1]
        X["comparisons"][slot(d, "role")[1]] = dict(desig=d, a=a, b=b, determines=slot(of, "role")[1])
    X["observation"] = slot(X["shared"], "observation")[1]
    X["models"] = (slot(X["belief"], "over")[1] if X["belief"] else
                   [slot(c[1], "name")[1] for c in dslots(X["question"]) if c[0] == "candidate"])
    return X


def check_logic(X):
    """Every comparison isolates one exposure: the two cultures' treatments differ in exactly that exposure."""
    out = []
    for role, c in X["comparisons"].items():
        key = lambda r: {(e["substance"], fmt(e["dose"]), fmt(e["at"])) for e in X["cultures"][r]["exposures"]}  # noqa: E731
        diff = sorted(key(c["a"]) ^ key(c["b"]))
        ok = len(diff) == 1 and diff[0][0] == c["determines"]
        out.append(dict(comparison=role, between=(c["a"], c["b"]), differ_in=diff, determines=c["determines"], ok=ok))
    return out


# ------------------------------------------------------------------------------------------------- deriving the culture actions
def V(role):
    return "?" + role


def to_vars(x):
    """Identifying descriptions -> variables of the culture plan: (the culture (role rescued)) -> ?rescued."""
    if isinstance(x, list) and is_desig(x) and x[0] in ("the", "each") and x[1] in ("culture", "substance", "belief", "experiment"):
        rest = [to_vars(s) for s in dslots(x) if s[0] != "role"]
        r = slot(x, "role")
        var = {"belief": "?B", "experiment": "?E"}.get(x[1]) or (V(r[1]) if r else None)
        if var:
            return ["the", x[1], var] + rest if rest else var
    if isinstance(x, list):
        return [to_vars(e) for e in x]
    return x


def derive_actions(X):
    cul = list(X["cultures"])
    sh, ob = X["shared"], X["observation"]
    t0, t1, tobs = slot(sh, "from")[1], slot(sh, "to")[1], slot(ob, "at")[1]
    env = slot(sh, "environment")[1]
    ents = [f"(the culture {V(c)} (role {c}))" for c in cul]
    ents += [f"(some substance {V(s)} (type {s}))" for s in X["substances"]]
    if X["belief"]:
        ents.append(f"(the belief ?B (over {fmt(X['models'])}) (prior {slot(X['belief'], 'prior')[1]}))")
    given = [f"(the culture {V(c)} {fmt(slot(X['cultures'][c]['desig'], 'state'))})" for c in cul]
    given += ([f"(the belief ?B {fmt(slot(X['belief'], 'entropy'))})"] if X["belief"] else []) + [f"(the experiment ?E {fmt(t0)})"]
    prevents = [fmt(to_vars(p)) for p in X["prevents"]]
    maintains = []
    for m in X["maintains"]:
        if m[0] == "each":
            maintains += [f"(the culture {V(c)} {fmt(m[2])})" for c in cul]
        else:
            maintains.append(fmt(to_vars(m)))
    steps, kind = [], {}

    def add(var, text, k, when=(float("inf"), 9)):
        steps.append((when, len(steps), text))
        kind[var] = k

    # an intervention per exposure; steps are listed in time order (interventions at t before growth from t)
    exps = sorted(((hours(e["at"]), i, c, e) for i, c in enumerate(cul) for e in X["cultures"][c]["exposures"]),
                  key=lambda x: (x[0], x[1]))
    for n, (h, _, c, e) in enumerate(exps, 1):
        v, s = f"?x{n}", e["substance"]
        typ = (s[:-1] if s.endswith("e") else s) + "ing"
        dose, at = " ".join(e["dose"]), fmt(e["at"])
        req = f" (requires (the experiment ?E {at}))" if h > hours(t0) else ""
        causes = slot(X["substances"][s], "causes")
        phys = f"(the culture {V(c)} (exposed-to {V(s)} {dose}))" + (f" (the culture {V(c)} {fmt(causes[1])})" if causes else "")
        add(v, f"(an action {v} (type {typ}) (culture {V(c)}) (substance {V(s)}) (dose {dose}) (at {at}){req} "
               f"(physical {phys}) (knowledge (a record (of {v}) (states {V(c)} {V(s)} {dose} {e['at'][1]} {e['at'][2]}))))",
            "intervention", (h, 0))
    # growth between the treatment times, for all cultures under the shared conditions
    times = sorted({hours(t0), hours(t1)} | {h for h, *_ in exps})
    unit = t0[2]
    ct = lambda h: f"(culture-time {h:g} {unit})"  # noqa: E731
    for n, (a, b) in enumerate(zip(times, times[1:]), 1):
        v = f"?g{n}"
        at_a = [(c, e) for h, _, c, e in exps if h == a]
        req = (" ".join(f"(the culture {V(c)} (exposed-to {V(e['substance'])}))" for c, e in at_a) if at_a
               else (f"(the experiment ?E {ct(a)})" if a > hours(t0) else ""))
        add(v, f"(an action {v} (type growing) (cultures {' '.join(V(c) for c in cul)}) (from {ct(a)}) (to {ct(b)})"
               + (f" (requires {req})" if req else "")
               + f" (physical (the experiment ?E {ct(b)})) (knowledge (a record (of {v}) (environment-history {env}))))",
            "growth", (a, 1))
    # an observation and an interpretation per culture
    side = slot(ob, "side-effect")
    est = slot(ob, "interpreted-as")[1]
    needs = slot(ob, "needs")[1]
    q = slot(est, "quantity")[1]
    for n, c in enumerate(cul, 1):
        v = f"?o{n}"
        add(v, f"(an action {v} (type observing) (culture {V(c)}) {fmt(slot(ob, 'readout'))} (at {fmt(tobs)}) "
               f"(requires (the experiment ?E {fmt(tobs)}))"
               + (f" (physical (the culture {V(c)} {fmt(side[1])}))" if side else "")
               + f" (knowledge (an image ?y{n} (of {V(c)}) {fmt(tobs)} (raw true))))", "observation")
    for n, c in enumerate(cul, 1):
        v = f"?i{n}"
        add(v, f"(an action {v} (type interpreting) (image ?y{n}) (into {q}) "
               f"(requires (an image (of {V(c)}) (raw true)) {fmt(needs)} :establishable) "
               f"(knowledge (an estimate (of {V(c)}) ({q}) {fmt(slot(est, 'sigma'))})))", "interpretation")
    # an analysis per comparison; a comparison licensed by another requires its finding
    licensed_by = {slot(slot(c["desig"], "licenses")[1], "role")[1]: r for r, c in X["comparisons"].items()
                   if slot(c["desig"], "licenses")}
    for r, c in X["comparisons"].items():
        upd = slot(c["desig"], "updates")
        v = "?a1" if upd else "?v1"
        stat = f"(statistic (difference (radius {V(c['a'])}) (radius {V(c['b'])})))"
        crit = slot(c["desig"], "established-when")
        req = [f"(an estimate (of {V(c['a'])}) ({q}))", f"(an estimate (of {V(c['b'])}) ({q}))"]
        if r in licensed_by:
            req.append(f"(a finding (of (the effect (of {V(X['comparisons'][licensed_by[r]]['determines'])}))) (established true))")
        if upd:
            know = ["(the belief ?B (posterior updated))", "(the belief ?B (information-gain measured))",
                    f"(a finding (of (the effect (of {V(c['determines'])}))) (measured true))"]
        else:
            know = [f"(a finding (of (the effect (of {V(c['determines'])}))) (established true))"]
        add(v, f"(an action {v} (type analysing)" + (" (belief ?B)" if upd else "")
               + f" {stat}" + (f" (criterion {fmt(crit[1])})" if crit else "")
               + f" (requires {' '.join(req)}) (knowledge {' '.join(know)}))", f"comparison:{r}")
    expl = fmt(slot(X["question"], "explains"))
    text = (f"(the experiment ?E\n  (question (which (a recovery-model (in {fmt(X['models'])})) {expl}))\n"
            f"  (entities {' '.join(ents)})\n  (goal {fmt(to_vars(X['goal']))})\n  (given {' '.join(given)})\n"
            f"  (prevents {' '.join(prevents)})\n  (maintains {' '.join(maintains)})\n  (steps {' '.join(t for *_, t in sorted(steps))}))")
    return text, kind


# ------------------------------------------------------------------------------------------------- comparing with culture_plan.ldl
def compare(P_new, D_new, P_old, D_old):
    ren = {}
    for v, t in P_old["entities"].items():
        d = parse(t)[0]
        r = slot(d, "role") or slot(d, "type") or [None, None]
        ren[v] = "?B" if d[1] == "belief" else V(r[1])
    rn = lambda s: re.sub(r"\?\w+", lambda m: ren.get(m.group(0), m.group(0)), s)  # noqa: E731
    key = lambda st, f: (st["type"], tuple(sorted((k, f(v)) for k, v in st["slots"].items() if k != "image")))  # noqa: E731
    new_by = {key(s, str): s for s in P_new["steps"]}
    match, missing = {}, []
    for s in P_old["steps"]:
        if s["type"] == "interpreting":       # identified by the culture of its estimate, not by its image variable
            of = rn(fmt(slot(s["knowledge"][0]["cond"], "of")[1]))
            m = next((n for n in P_new["steps"] if n["type"] == "interpreting"
                      and fmt(slot(n["knowledge"][0]["cond"], "of")[1]) == of), None)
        else:
            m = new_by.get(key(s, rn))
        if m:
            match[s["var"]] = m["var"]
        else:
            missing.append(s["var"])
    added = [s["var"] for s in P_new["steps"] if s["var"] not in match.values()]
    old_edges = {(match.get(a, a), match.get(b, b)) for a, b in D_old["hasse"]}
    new_edges = {tuple(e) for e in D_new["hasse"]}
    eff = []
    by_new = {s["var"]: s for s in P_new["steps"]}
    for s in P_old["steps"]:
        if s["var"] in match:
            have = {fmt(i["cond"]) for i in by_new[match[s["var"]]]["physical"]}
            eff += [(s["var"], rn(fmt(i["cond"]))) for i in s["physical"] if rn(fmt(i["cond"])) not in have]
    return dict(matched=match, missing=missing, added=added, edges_kept=sorted(old_edges & new_edges),
                edges_removed=sorted(old_edges - new_edges), edges_added=sorted(new_edges - old_edges), effects_not_stated=eff)


# ------------------------------------------------------------------------------------------------- the experiment designator
def designator(X, logic, K, Mp):
    vessels = {v["role"]: v for v in Mp["vessels"].values()}
    plate = next(iter(vessels.values()))["plate"]
    lg = {l["comparison"]: l for l in logic}

    def culture(d):
        r = slot(d, "role")[1]
        place = ["in", ["a", "well", ["id", vessels[r]["well"]], ["part-of", ["the", "plate", ["id", plate]]]]]
        rest = [s for s in dslots(d) if s[0] != "role"]
        return d[:2] + [["role", r], place] + rest

    def question(d):
        out = d[:2]
        for s in dslots(d):
            if s[0] == "candidate":
                p = K["predicted"][slot(s[1], "name")[1]]
                s = ["candidate", s[1] + [["predicts", ["an", "effect", ["of", ["the", "substance", ["role", "rescue"]]],
                                                       ["mean", f"{p['effect_um']:.1f}", "um"], ["sd", f"{p['effect_sd_um']:.1f}", "um"]]]]]
            out.append(s)
        return out

    def comparison(d):
        r = slot(d, "role")[1]
        c = X["comparisons"][r]
        s = lg[r]["differ_in"][0][0]
        extra = [["differ-only-in", ["the", "exposure", ["to", ["the", "substance", ["role", s]]]]],
                 ["statistic", ["difference", ["radius", ["the", "culture", ["role", c["a"]]]],
                                ["radius", ["the", "culture", ["role", c["b"]]]]]]]
        sl = dslots(d)
        return d[:2] + sl[:2] + extra + sl[2:]

    def insight(d):
        out = d + ([["expected-information-gain", str(K["expected_gain_bit"]), "bit"]] if slot(d, "role")[1] == "answer" else [])
        return out + [["value", "unknown"]]

    def shared(d):
        p = ["plate", ["a", "plate", ["id", plate], ["located-in", ["a", "controlled-environment",
                                                                      ["profile", slot(d, "environment")[1]]]]]]
        return d[:2] + [p] + dslots(d)

    f = {"culture": culture, "question": question, "comparison": comparison, "insight": insight, "shared-conditions": shared}
    return X["root"][:2] + [[s[0], f[s[0]](s[1])] if s[0] in f else s for s in X["root"][2:]]


def main(argv):
    X = load()
    logic = check_logic(X)
    text, kind = derive_actions(X)
    P_new = load_plan(text)
    D_new = derive(P_new)
    P_old = load_plan(open(os.path.join(LAB, "culture_plan.ldl")).read())
    D_old = derive(P_old)
    C = compare(P_new, D_new, P_old, D_old)
    cp = json.load(open(os.path.join(OUT, "culture_plan.json")))
    K, Mp = cp["knowledge"], cp["mapping"]

    plan_hdr = (";; The culture actions derived from rsa/registry/lab/experiment.ldl by rsa/experiment_designator.py (LDL v0.3,\n"
                ";; culture level, the format of culture_plan.ldl). Generated; do not edit. The order is derived from the\n"
                ";; causal links by rsa/culture_plan.py. ILLUSTRATIVE (D016).\n\n")
    open(os.path.join(OUT, "experiment_culture_plan.ldl"), "w").write(plan_hdr + pretty(text, "ldl"))

    E = designator(X, logic, K, Mp)
    top = ["def-top-level-cram-function", "challenge-rescue", [],
           ["perform", ["an", "action", ["type", "conducting"], ["experiment", E]]]]
    lv = {}
    for v, l in D_new["level"].items():
        lv.setdefault(l, []).append(v[1:])
    order = " < ".join("{" + " ".join(sorted(vs)) + "}" if len(vs) > 1 else vs[0] for _, vs in sorted(lv.items()))
    logic_txt = "; ".join(f"{l['comparison']}: {l['between'][0]} vs {l['between'][1]} differ only in "
                          f"{l['differ_in'][0][0] if l['ok'] else l['differ_in']}" for l in logic)
    header = f""";;; -*- Mode: Lisp -*-
;;; The challenge-rescue experiment as one entity designator, performed by the top-level plan.
;;; Source: rsa/registry/lab/experiment.ldl (authored); placement (plate, wells) from the mapping to Cell 01, the models'
;;; predictions from the design. Generated by rsa/experiment_designator.py.
;;; Checked: {logic_txt}.
;;; Conducting it performs {len(P_new['steps'])} culture actions (rsa/out/experiment_culture_plan.ldl), ordered by
;;; {len(D_new['links'])} causal links: {order}.
;;; Not executed: no Lisp CRAM here. ILLUSTRATIVE (D016).

(in-package :culture-src)
"""
    lisp = header + "\n" + pretty(fmt(top), "lisp", width=112)
    path = os.path.join(OUT, "challenge_rescue_designator.lisp")
    open(path, "w").write(lisp)
    stale = os.path.join(OUT, "challenge_rescue_by_culture.lisp")       # superseded by the file above
    if os.path.exists(stale):
        os.remove(stale)
    code = re.sub(r";[^\n]*", "", lisp)
    balanced = code.count("(") == code.count(")")
    no_vars = not re.search(r"\?[a-z]", code)
    ok_logic = all(l["ok"] for l in logic)
    wellformed = not D_new["unsupported"] and not D_new["cyclic"]
    print(f"[experiment] logic: {logic_txt}: {'OK' if ok_logic else 'VIOLATED'}")
    print(f"[experiment] derived {len(P_new['steps'])} culture actions, {len(D_new['links'])} causal links, order {order}; "
          f"unsupported {D_new['unsupported']}, cyclic {D_new['cyclic']}")
    print(f"[experiment] vs culture_plan.ldl: {len(C['matched'])}/{len(P_old['steps'])} actions the same "
          f"(missing {C['missing']}), added {C['added']}; order edges kept {len(C['edges_kept'])}, "
          f"removed {C['edges_removed']}, added {C['edges_added']}")
    print(f"[experiment] effects culture_plan.ldl states that experiment.ldl does not: {C['effects_not_stated']}")
    print(f"[experiment] wrote {os.path.relpath(path)} ({lisp.count(chr(10))} lines; parentheses balanced {balanced}; "
          f"variables {'none' if no_vars else 'PRESENT'}) and rsa/out/experiment_culture_plan.ldl")
    json.dump(dict(logic=logic, derived=D_new, comparison=C, kinds=kind), open(os.path.join(OUT, "experiment_designator.json"), "w"),
              indent=1, default=list)
    return 0 if ok_logic and wellformed and balanced and no_vars and not C["missing"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
