"""An experiment as an instance of a concept in a specialization hierarchy of experiment concepts, with a partonomy.

The concepts (registry/lab/experiment_concepts.ldl) state, per level, the roles an instance must fill (pattern and
cardinality), the roles whose fillers are restricted (only) and the checks it must pass; a concept inherits all of this
from the concepts it specializes. Roles form a hierarchy (a culture is a unit, a unit a participant; a phase, a step,
a well and an exposure are kinds of parthood). Kinds (process, material entity, plan specification, information
entity) are disjoint, and parthood never crosses them. The experiment (registry/lab/experiment.ldl) declares its
concept with instance-of.

The experiment is checked as derived and placed: its procedure (rsa/experiment_designator.py) yields its phases and
steps (process partonomy), the mapping to Cell 01 its plate and wells (material partonomy); its treatments have
exposures as components (plan partonomy). Steps realize exposures, observations and comparisons; cultures are
contained in wells, not parts of them.

  1. Conformance: the experiment against its concept and every ancestor, constraint by constraint; every part
     (phase, plate, well, treatment, ...) against its own concept.
  2. Classification: every experiment concept the experiment satisfies; the most specific must include the declared one.
  3. Negative controls: modified copies must fail exactly at the levels whose constraints they break.

    env_cad/bin/python -m rsa.experiment_concepts
      -> rsa/out/experiment_concepts.json, experiment_concepts.{svg,png} (hierarchy),
         experiment_partonomy.{svg,png} (the instance's partonomy)
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys

from .culture_plan import load_plan
from .experiment_designator import derive_actions, load as load_experiment
from .ldl import LAB, OUT, dslots, fmt, is_desig, parse, slot

CONCEPTS = os.path.join(LAB, "experiment_concepts.ldl")
INSTANCE = os.path.join(LAB, "experiment.ldl")


# ------------------------------------------------------------------------------------------------- the TBox
def load_concepts(path=CONCEPTS):
    roles, concepts = {}, {}
    for f in parse(open(path).read()):
        name = f[2]
        doc = slot(f, "documentation")
        doc = doc[1].strip('"') if doc else ""
        if f[1] == "role":
            sp, inv, ch = slot(f, "specializes"), slot(f, "inverse"), slot(f, "chain")
            roles[name] = dict(parent=sp[1] if sp else None, transitive=bool(slot(f, "transitive")),
                               inverse=inv[1] if inv else None, chain=ch[1:] if ch else None, doc=doc)
        elif f[1] == "concept":
            concepts[name] = dict(
                name=name, parents=(slot(f, "specializes") or ["s"])[1:], doc=doc, kind=bool(slot(f, "kind")),
                has=[dict(path=h[1] if isinstance(h[1], list) else [h[1]], pattern=h[2], card=h[3])
                     for h in dslots(f) if h[0] == "has"],
                only=[dict(path=[o[1]], pattern=o[2]) for o in dslots(f) if o[0] == "only"],
                checks=[c[1] for c in dslots(f) if c[0] == "check"],
                procedure=[fmt(r) for r in (slot(f, "procedure") or ["p"])[1:]])
    return roles, concepts


def ancestors(c, concepts):
    """The concept and all concepts it specializes, most general first."""
    out = []

    def visit(n):
        for p in concepts[n]["parents"]:
            visit(p)
        if n not in out:
            out.append(n)
    visit(c)
    return out


def kind_of(c, concepts):
    return next((a for a in ancestors(c, concepts) if concepts[a]["kind"]), None) if c in concepts else None


def role_chain(r, roles):
    while r is not None:
        yield r
        r = roles.get(r, {}).get("parent")


def subroles(role, roles):
    return {r for r in roles if role in role_chain(r, roles)} | {role}


class TBox:
    def __init__(self, roles, concepts):
        self.roles, self.concepts = roles, concepts
        self.experiments = [c for c in concepts if "experiment" in ancestors(c, concepts)]

    # matching ------------------------------------------------------------------------------------
    def fillers(self, x, path):
        cur = [x]
        for role in path:
            names = subroles(role, self.roles)
            cur = [v for c in cur if isinstance(c, list) for s in dslots(c) if s[0] in names for v in s[1:]]
        return cur

    def isa(self, cls, pat_cls):
        return pat_cls == "entity" or cls == pat_cls or (cls in self.concepts and pat_cls in ancestors(cls, self.concepts))

    def match(self, x, pat):
        if pat == "any":
            return True
        if isinstance(pat, str):
            return x == pat
        if pat and pat[0] == "or":
            return any(self.match(x, p) for p in pat[1:])
        if is_desig(pat):
            if not (is_desig(x) and self.isa(x[1], pat[1])):
                return False
            return all(any(s[0] == ps[0] and all(any(self.match(v, pv) for v in s[1:]) for pv in ps[1:]) for s in dslots(x))
                       for ps in dslots(pat))
        return isinstance(x, list) and x[:1] == pat[:1] and all(any(self.match(v, pv) for v in x[1:]) for pv in pat[1:])

    # constraints -----------------------------------------------------------------------------------
    def own(self, x, c, E):
        res = []
        for h in self.concepts[c]["has"]:
            n = sum(self.match(f, h["pattern"]) for f in self.fillers(x, h["path"]))
            k = int(h["card"][1])
            ok = {"exactly": n == k, "at-least": n >= k, "at-most": n <= k}[h["card"][0]]
            pr = slot(h["pattern"], "role") if is_desig(h["pattern"]) else None
            if not pr and is_desig(h["pattern"]) and h["pattern"][1] not in ("entity", h["path"][-1]):
                pr = ["role", h["pattern"][1]]
            card = {"exactly": "=", "at-least": "≥", "at-most": "≤"}[h["card"][0]] + h["card"][1]
            res.append(dict(kind="role", what=f"{' '.join(h['path'])}: {fmt(h['pattern'])[:90]}",
                            short=" ".join(h["path"]) + (f" [{pr[1]}]" if pr else ""), card=card, found=n, ok=ok))
        for o in self.concepts[c]["only"]:
            bad = [f for f in self.fillers(x, o["path"]) if not self.match(f, o["pattern"])]
            res.append(dict(kind="only", what=f"only {o['path'][0]}: {fmt(o['pattern'])[:90]}", short=f"only {o['path'][0]}",
                            card="", found=len(bad), ok=not bad))
        for k in self.concepts[c]["checks"]:
            ok, what = CHECKS[k](self, E)
            res.append(dict(kind="check", what=f"{k}: {what}", short=k, ok=ok))
        return res

    def conforms(self, x, c, E):
        return all(r["ok"] for a in ancestors(c, self.concepts) for r in self.own(x, a, E))

    def parts(self, x):
        """Every designator inside x with an indefinite determiner (an entity, not a reference to one)."""
        out = []

        def walk(y, top):
            if isinstance(y, list):
                if is_desig(y) and y[0] in ("a", "an") and not top:
                    out.append(y)
                for e in y:
                    walk(e, False)
        walk(x, True)
        return out


# ------------------------------------------------------------------------------------------------- the instance as derived and placed
def describe(v, X):
    """Culture-plan variables -> identifying descriptions."""
    if v in ("?B",):
        return ["the", "belief"]
    if v == "?E":
        return ["the", "experiment"]
    r = v[1:]
    if r in X["cultures"]:
        return ["the", "culture", ["role", r]]
    if r in X["substances"]:
        return ["the", "substance", ["role", r]]
    return v


def to_desc(x, X):
    if isinstance(x, str):
        return describe(x, X) if x.startswith("?") else x
    return [to_desc(e, X) for e in x]


def derived_and_placed(E):
    """The experiment with its derived phases and steps and its placement (plate, wells) from the mapping."""
    X = load_experiment(root=copy.deepcopy(E))
    text, kind = derive_actions(X)
    P = load_plan(text)
    steps = {}
    for s in P["steps"]:
        k = kind[s["var"]]
        d = ["an", "action", ["name", s["var"][1:]], ["kind", "analysis" if k.startswith("comparison") else k], ["type", s["type"]]]
        for key, val in s["slots"].items():
            if key in ("culture",):
                d.append(["culture", describe(val, X)])
            elif key == "cultures":
                d += [["culture", describe(v, X)] for v in val.split()]
            elif key == "substance":
                d.append(["substance", describe(val, X)])
            elif key == "image":
                d.append(["about", describe(slot(s["knowledge"][0]["cond"], "of")[1], X)])
            elif key == "belief":
                d.append(["updates", describe(val, X)])
            else:
                d.append([key] + [to_desc(e, X) for e in parse(f"({val})")[0]])
        steps[s["var"][1:]] = (d, k)
    sh = X["shared"]
    t0, t1, tobs = slot(sh, "from")[1], slot(sh, "to")[1], slot(X["observation"], "at")[1]
    by = lambda *ks: [["step", d] for d, k in steps.values() if k.split(":")[0] in ks]  # noqa: E731
    phases = [["phase", ["a", "cultivation-phase", ["from", t0], ["to", t1]] + by("intervention", "growth")],
              ["phase", ["an", "observation-phase", ["at", tobs]] + by("observation")],
              ["phase", ["an", "analysis-phase", ["begins-after", ["the", "observation-phase"]]] + by("interpretation", "comparison")]]
    Mp = json.load(open(os.path.join(OUT, "culture_plan.json")))["mapping"]
    vs = list(Mp["vessels"].values())
    site = ["site", ["a", "plate", ["id", vs[0]["plate"]],
                     ["located-in", ["a", "controlled-environment", ["profile", slot(sh, "environment")[1]]]]]
            + [["well", ["a", "well", ["id", v["well"]], ["contains", ["the", "culture", ["role", v["role"]]]]]] for v in vs]]
    return copy.deepcopy(E) + phases + [site], len(steps)


# ------------------------------------------------------------------------------------------------- checks over several roles
def units(T, E):
    return {slot(u, "role")[1]: u for u in T.fillers(E, ["unit"])}


def exposures(u):
    tr = slot(u, "treatment")[1] if slot(u, "treatment") else None
    return [s[1] for s in dslots(tr) if s[0] == "exposure" and is_desig(s[1]) and s[1][1] == "exposure"] if is_desig(tr) else []


def ex_key(e):
    return (slot(slot(e, "to")[1], "role")[1], fmt(slot(e, "dose")[1:]), fmt(slot(e, "at")[1]))


def steps_of(T, E, kind=None):
    return [s for p in T.fillers(E, ["phase"]) for s in T.fillers(p, ["step"]) if kind is None or T.match(s, ["an", "action", ["kind", kind]])]


def role_of(desc):
    r = slot(desc, "role") if is_desig(desc) else None
    return r[1] if r else None


def c_between(T, E):
    U = units(T, E)
    bad = [role_of(c) for c in T.fillers(E, ["comparison"])
           if not all(sum(T.match(u, b) for u in U.values()) == 1 for b in slot(c, "between")[1:])]
    return not bad, "every comparison is between two units of the experiment" + (f"; not: {bad}" if bad else "")


def c_effect_insight(T, E):
    ins = T.fillers(E, ["insight"])
    miss = [role_of(c) for c in T.fillers(E, ["comparison"])
            if not any(T.match(i, ["an", "insight", ["role", "effect"], ["of", slot(slot(c, "determines")[1], "of")[1]]])
                       and T.match(c, slot(i, "from")[1]) for i in ins)]
    return not miss, "an effect insight from each comparison" + (f"; missing for {miss}" if miss else "")


def c_single_difference(T, E):
    U = units(T, E)
    out = []
    for c in T.fillers(E, ["comparison"]):
        a, b = (next((u for u in U.values() if T.match(u, r)), None) for r in slot(c, "between")[1:])
        if a is None or b is None:
            out.append(f"{role_of(c)}: a unit is missing")
            continue
        diff = sorted({ex_key(e) for e in exposures(a)} ^ {ex_key(e) for e in exposures(b)})
        det = role_of(slot(slot(c, "determines")[1], "of")[1])
        if not (len(diff) == 1 and diff[0][0] == det):
            out.append(f"{role_of(c)} differs in {len(diff)} exposures")
    return not out, "every comparison isolates exactly the exposure whose effect it determines" + (f"; {'; '.join(out)}" if out else "")


def c_rescue_after(T, E):
    u = units(T, E).get("rescued")
    t = {ex_key(e)[0]: float(slot(e, "at")[1][1]) for e in exposures(u)} if u else {}
    ok = "challenge" in t and "rescue" in t and t["rescue"] > t["challenge"]
    return ok, f"the rescue is given after the challenge ({t.get('challenge')} h, {t.get('rescue')} h)"


def c_answer(T, E):
    ans = [i for i in T.fillers(E, ["insight"]) if T.match(i, ["an", "insight", ["role", "answer"]])]
    ok = len(ans) == 1 and any(T.match(c, slot(ans[0], "from")[1]) and slot(c, "updates") for c in T.fillers(E, ["comparison"]))
    return ok, "the answer comes from a comparison that updates the belief"


def c_kind(T, E):
    bad = []
    names = subroles("has-part", T.roles)
    for x in [E] + T.parts(E):
        kx = kind_of(x[1], T.concepts)
        for s in dslots(x):
            if s[0] in names:
                for v in s[1:]:
                    if is_desig(v) and kind_of(v[1], T.concepts) != kx:
                        bad.append(f"{x[1]} -{s[0]}-> {v[1]}")
    return not bad, "parthood never crosses kinds (process, material entity, plan, information)" + (f"; {bad[:3]}" if bad else "")


def c_parts(T, E):
    bad = [f"{p[1]}{' ' + slot(p, 'name')[1] if slot(p, 'name') else ''}" for p in T.parts(E)
           if p[1] in T.concepts and not T.conforms(p, p[1], E)]
    return not bad, "every part satisfies its own concept" + (f"; not: {bad}" if bad else "")


def c_step_once(T, E):
    names = [slot(s, "name")[1] for s in steps_of(T, E)]
    dup = sorted({n for n in names if names.count(n) > 1})
    return not dup, f"each of the {len(set(names))} steps is part of exactly one phase" + (f"; in several: {dup}" if dup else "")


def c_exposure_realized(T, E):
    acts = steps_of(T, E, "intervention")
    bad = []
    for r, u in units(T, E).items():
        for e in exposures(u):
            n = sum(role_of(slot(a, "culture")[1]) == r and role_of(slot(a, "substance")[1]) == ex_key(e)[0]
                    and fmt(slot(a, "dose")[1:]) == ex_key(e)[1] and fmt(slot(a, "at")[1]) == ex_key(e)[2] for a in acts)
            if n != 1:
                bad.append(f"{r}/{ex_key(e)[0]}: {n}")
    n_exp = sum(len(exposures(u)) for u in units(T, E).values())
    extra = len(acts) - n_exp
    return not bad and extra == 0, (f"each exposure is realized by exactly one intervention ({n_exp} exposures, {len(acts)} interventions)"
                                    + (f"; {bad}" if bad else ""))


def c_observed(T, E):
    obs = steps_of(T, E, "observation")
    bad = [r for r in units(T, E) if sum(role_of(slot(o, "culture")[1]) == r for o in obs) != 1]
    return not bad, "each unit is observed exactly once" + (f"; not: {bad}" if bad else "")


def c_comparison_realized(T, E):
    an = steps_of(T, E, "analysis")
    bad = []
    for c in T.fillers(E, ["comparison"]):
        pair = [role_of(b) for b in slot(c, "between")[1:]]
        n = sum([role_of(x[1]) for x in slot(a, "statistic")[1][1:]] == pair for a in an)
        if n != 1:
            bad.append(f"{role_of(c)}: {n}")
    return not bad, "each comparison is realized by exactly one analysis" + (f"; {bad}" if bad else "")


def c_wells(T, E):
    sites = T.fillers(E, ["site"])
    U = units(T, E)
    wells = [(slot(s, "id")[1], w) for s in sites for w in T.fillers(s, ["well"])]
    bad = []
    for r in U:
        n = [(p, slot(w, "id")[1]) for p, w in wells if any(role_of(v) == r for v in T.fillers(w, ["contains"]))]
        if len(n) != 1:
            bad.append(f"{r}: {len(n)} wells")
    plates = {p for p, w in wells if T.fillers(w, ["contains"])}
    return not bad and len(plates) == 1, (f"every unit is in exactly one well, all wells part of one plate ({sorted(plates)})"
                                          + (f"; {bad}" if bad else ""))


def c_time(T, E):
    ph = {p[1]: p for p in T.fillers(E, ["phase"])}
    cul, obs = ph.get("cultivation-phase"), ph.get("observation-phase")
    if not (cul and obs):
        return False, "phases missing"
    t0, t1, to = (float(slot(cul, "from")[1][1]), float(slot(cul, "to")[1][1]), float(slot(obs, "at")[1][1]))
    bad = []
    for s in T.fillers(cul, ["step"]):
        times = [float(slot(s, k)[1][1]) for k in ("at", "from", "to") if slot(s, k)]
        if not all(t0 <= t <= t1 for t in times):
            bad.append(slot(s, "name")[1])
    ok = t1 <= to and not bad and bool(slot(ph.get("analysis-phase", ["a", "x"]), "begins-after"))
    return ok, f"cultivation {t0:g}-{t1:g} h, then observation at {to:g} h, then analysis" + (f"; outside: {bad}" if bad else "")


CHECKS = {"comparisons-between-units": c_between, "an-effect-insight-per-comparison": c_effect_insight,
          "single-difference": c_single_difference, "rescue-after-challenge": c_rescue_after,
          "answer-from-a-comparison-that-updates-the-belief": c_answer, "parthood-preserves-kind": c_kind,
          "parts-conform-to-their-concepts": c_parts, "each-step-in-one-phase": c_step_once,
          "each-exposure-realized-once": c_exposure_realized, "each-unit-observed-once": c_observed,
          "each-comparison-realized-once": c_comparison_realized, "units-in-distinct-wells-of-the-site": c_wells,
          "phases-in-time-order": c_time}


# ------------------------------------------------------------------------------------------------- conformance and classification
def evaluate(T, E):
    own = {c: T.own(E, c, E) for c in T.experiments}
    sat = {c: all(r["ok"] for a in ancestors(c, T.concepts) if a in own for r in own[a]) for c in T.experiments}
    most = [c for c in T.experiments if sat[c] and not any(sat[d] and d != c and c in ancestors(d, T.concepts) for d in T.experiments)]
    return own, sat, most


def variants(E0, E):
    """Negative controls. Design edits change experiment.ldl and derive and place it again; plan edits change the
    derived phases or the placement of the unchanged design."""
    def design(f):
        x = copy.deepcopy(E0)
        f(x)
        return derived_and_placed(x)[0]

    def edit(f):
        x = copy.deepcopy(E)
        f(x)
        return x

    def unit(x, role):
        return next(s[1] for s in dslots(x) if s[0] == "culture" and slot(s[1], "role")[1] == role)

    def phase(x, name):
        return next(s[1] for s in dslots(x) if s[0] == "phase" and s[1][1] == name)

    def dose(x):
        slot(exposures(unit(x, "comparator"))[0], "dose")[1] = "0.60"

    def no_control(x):
        x.remove(next(s for s in dslots(x) if s[0] == "culture" and slot(s[1], "role")[1] == "control"))

    def rescue_early(x):
        e = next(e for e in exposures(unit(x, "rescued")) if ex_key(e)[0] == "rescue")
        slot(e, "at")[1][1] = "0"

    def no_belief(x):
        for s in [s for s in dslots(x) if s[0] == "belief" or (s[0] == "insight" and slot(s[1], "role")[1] == "answer")]:
            x.remove(s)

    def drop_rescue_step(x):
        p = phase(x, "cultivation-phase")
        p.remove(next(s for s in dslots(p) if s[0] == "step" and slot(s[1], "type")[1] == "rescuing"))

    def other_plate(x):
        site = next(s[1] for s in dslots(x) if s[0] == "site")
        w = next(s for s in dslots(site) if s[0] == "well" and role_of(slot(s[1], "contains")[1]) == "comparator")
        site.remove(w)
        x.append(["site", ["a", "plate", ["id", "P18"], w]])

    def observe_in_analysis(x):
        o, a = phase(x, "observation-phase"), phase(x, "analysis-phase")
        s = next(s for s in dslots(o) if s[0] == "step")
        a.append(s)

    def twin_step(x):
        phase(x, "analysis-phase").append(copy.deepcopy(next(s for s in dslots(phase(x, "observation-phase")) if s[0] == "step")))

    def well_in_treatment(x):
        tr = slot(unit(x, "rescued"), "treatment")[1]
        tr.append(["exposure", ["a", "well", ["id", "B01"]]])
    return {"comparator dose 0.60 au": (design(dose), "controlled-experiment"),
            "control culture removed": (design(no_control), "comparative-experiment"),
            "rescue given with the challenge (0 h)": (design(rescue_early), "challenge-rescue-experiment"),
            "belief and answer removed": (design(no_belief), "hypothesis-discriminating-experiment"),
            "rescue intervention missing from the plan": (edit(drop_rescue_step), "comparative-experiment"),
            "comparator on another plate": (edit(other_plate), "comparative-experiment"),
            "an observation step in two phases": (edit(twin_step), "comparative-experiment"),
            "a well as part of a treatment": (edit(well_in_treatment), "experiment")}


# ------------------------------------------------------------------------------------------------- figures
def fig_hierarchy(T, own, sat, declared, path):
    def lbl(c, rows_):
        rows = [f'<tr><td align="left"><b>{c}</b></td></tr>']
        for r in rows_:
            t = f"{r['short']} {r['card']}" if r["kind"] == "role" else r["short"]
            mark = ("&#10003; " if r["ok"] else "&#10007; ") if r.get("ok") is not None else ""
            rows.append(f'<tr><td align="left"><font point-size="9">{mark}{t}</font></td></tr>')
        return "<<table border='0' cellspacing='0'>" + "".join(rows) + "</table>>"
    dot = ["digraph G { rankdir=BT; nodesep=0.25; ranksep=0.35; node [shape=box, style=rounded, fontname=Helvetica, fontsize=11];"
           " edge [fontname=Helvetica, fontsize=8, color=\"#555555\"];"]
    show = set(T.experiments) | {"process", "phase", "cultivation-phase", "observation-phase", "analysis-phase"}
    for c in T.concepts:
        if c not in show:
            continue
        if c in own:
            dot.append(f'"{c}" [label={lbl(c, own[c])}, color="{"#2e7d32" if sat[c] else "#c62828"}"];')
        else:
            spec = [dict(kind="role", short=" ".join(h["path"]), card=("=" if h["card"][0] == "exactly" else "≥") + h["card"][1])
                    for h in T.concepts[c]["has"]] + [dict(kind="only", short=f"only {o['path'][0]}: "
                                                           + " | ".join(fmt(p)[16:-1] for p in (o["pattern"][1:] if o["pattern"][0] == "or" else [o["pattern"]])))
                                                      for o in T.concepts[c]["only"]]
            style = 'style="rounded,filled", fillcolor="#f3f3f3"' if T.concepts[c]["kind"] else ""
            dot.append(f'"{c}" [label={lbl(c, spec)} {style}];')
        for p in T.concepts[c]["parents"]:
            dot.append(f'"{c}" -> "{p}";')
    for ph in ("cultivation-phase", "observation-phase", "analysis-phase"):
        dot.append(f'"comparative-experiment" -> "{ph}" [dir=back, arrowtail=diamond, style=dashed, constraint=false, '
                   f'color="#1565c0", fontcolor="#1565c0", label="{"has-part (phase) =1" if ph == "observation-phase" else ""}"];')
    dot.append('"challenge-rescue (experiment.ldl)" [shape=note, fillcolor="#e3f2fd", style=filled];')
    dot.append(f'"challenge-rescue (experiment.ldl)" -> "{declared}" [style=dashed, label="instance-of"];}}')
    for fmt_, p in (("svg", path), ("png", path.replace(".svg", ".png")), ("pdf", path.replace(".svg", ".pdf"))):
        subprocess.run(["dot", f"-T{fmt_}", "-Gdpi=130", "-o", p], input="\n".join(dot), text=True, check=True)


def fig_partonomy(T, E, path):
    dot = ["digraph P { rankdir=LR; nodesep=0.12; ranksep=0.5; node [shape=box, style=rounded, fontname=Helvetica, fontsize=10];"
           " edge [fontname=Helvetica, fontsize=8];"]
    part = 'arrowtail=diamond, dir=back, color="#333333"'
    dot.append('subgraph cluster_p { label="process partonomy (has-part: phase, step)"; fontname=Helvetica; fontsize=10; color="#90a4ae";')
    dot.append('E [label="challenge-rescue\\nexperiment", style="rounded,filled", fillcolor="#e3f2fd"];')
    for p in T.fillers(E, ["phase"]):
        pid = p[1]
        dot.append(f'"{pid}" [label="{pid}"];')
        dot.append(f'E -> "{pid}" [{part}];')
        for s in T.fillers(p, ["step"]):
            n = slot(s, "name")[1]
            dot.append(f'"s_{n}" [label="{n}: {slot(s, "type")[1]}", fontsize=9];')
            dot.append(f'"{pid}" -> "s_{n}" [{part}];')
    dot.append("}")
    dot.append('subgraph cluster_m { label="material partonomy (has-part: well) and location (contains)"; fontname=Helvetica; fontsize=10; color="#a5d6a7";')
    for s in T.fillers(E, ["site"]):
        pid = slot(s, "id")[1]
        dot.append(f'"m_{pid}" [label="plate {pid}"];')
        for w in T.fillers(s, ["well"]):
            wid = slot(w, "id")[1]
            dot.append(f'"w_{wid}" [label="well {wid}"]; "m_{pid}" -> "w_{wid}" [{part}];')
            for c in T.fillers(w, ["contains"]):
                dot.append(f'"w_{wid}" -> "u_{role_of(c)}" [style=dashed, label="contains"];')
    for r in units(T, E):
        dot.append(f'"u_{r}" [label="culture\\n({r})", style="rounded,filled", fillcolor="#e8f5e9"];')
    dot.append("}")
    dot.append('subgraph cluster_t { label="plan partonomy (has-component: exposure)"; fontname=Helvetica; fontsize=10; color="#ffcc80";')
    for r, u in units(T, E).items():
        dot.append(f'"t_{r}" [label="treatment\\n({r})"]; "u_{r}" -> "t_{r}" [label="treatment", style=dotted];')
        for e in exposures(u):
            k = ex_key(e)
            eid = f"e_{r}_{k[0]}"
            dot.append(f'"{eid}" [label="exposure: {k[0]}\\n{k[1][1:-1]}, {k[2][14:-1]}", fontsize=9]; "t_{r}" -> "{eid}" [{part}];')
            for a in steps_of(T, E, "intervention"):
                if role_of(slot(a, "culture")[1]) == r and role_of(slot(a, "substance")[1]) == k[0] and fmt(slot(a, "at")[1]) == k[2]:
                    dot.append(f'"s_{slot(a, "name")[1]}" -> "{eid}" [style=dotted, color="#e65100", label="realizes", constraint=false];')
    dot.append("}}")
    for fmt_, p in (("svg", path), ("png", path.replace(".svg", ".png")), ("pdf", path.replace(".svg", ".pdf"))):
        subprocess.run(["dot", f"-T{fmt_}", "-Gdpi=120", "-o", p], input="\n".join(dot), text=True, check=True)


def main(argv):
    roles, concepts = load_concepts()
    T = TBox(roles, concepts)
    E0 = parse(open(INSTANCE).read())[0]
    declared = slot(E0, "instance-of")[1]
    E, n_steps = derived_and_placed(E0)
    own, sat, most = evaluate(T, E)
    line = " < ".join(a for a in ancestors(declared, concepts))
    print(f"[concepts] {len(concepts)} concepts ({len(T.experiments)} of experiments), {len(roles)} roles; {declared}: {line}")
    print(f"[instance] derived and placed: {len(T.fillers(E, ['phase']))} phases, {n_steps} steps, "
          f"{len(T.fillers(E, ['site']))} plate, {sum(len(T.fillers(s, ['well'])) for s in T.fillers(E, ['site']))} wells")
    for c in [a for a in ancestors(declared, concepts) if a in own]:
        print(f"[conform] {c:38} {'OK ' if all(r['ok'] for r in own[c]) else 'NOT'} ({sum(r['ok'] for r in own[c])}/{len(own[c])})")
        for r in own[c]:
            print(f"            {'✓' if r['ok'] else '✗'} {r['what']}" + (f"  [{r['found']} found, {r['card']}]" if r['kind'] == 'role' else ''))
    parts = {}
    for p in T.parts(E):
        if p[1] in concepts:
            parts.setdefault(p[1], []).append(T.conforms(p, p[1], E))
    print(f"[parts] {', '.join(f'{c} {sum(v)}/{len(v)}' for c, v in sorted(parts.items()))}")
    print(f"[classify] satisfies {[c for c in T.experiments if sat[c]]}; most specific {most}; declared {declared} "
          f"{'confirmed' if declared in most else 'NOT confirmed'}")
    neg = {}
    for name, (V, expect) in variants(E0, E).items():
        o, s, m = evaluate(T, V)
        failing = [c for c in T.experiments if not all(r["ok"] for r in o[c])]
        ok = expect in failing and not s[declared]
        neg[name] = dict(fails_at=failing, most_specific=m, expected_to_fail_at=expect, ok=ok,
                         broken=[r["what"] for c in failing for r in o[c] if not r["ok"]])
        print(f"[negative] {name:42} fails at {failing}; classified as {m}: {'as expected' if ok else 'UNEXPECTED'}")
    fig_hierarchy(T, own, sat, declared, os.path.join(OUT, "experiment_concepts.svg"))
    fig_partonomy(T, E, os.path.join(OUT, "experiment_partonomy.svg"))
    json.dump(dict(roles=roles, concepts=concepts, declared=declared, instance=fmt(E),
                   conformance={c: own[c] for c in ancestors(declared, concepts) if c in own},
                   parts={c: [sum(v), len(v)] for c, v in parts.items()}, satisfied=sat, most_specific=most,
                   negative_controls=neg), open(os.path.join(OUT, "experiment_concepts.json"), "w"), indent=1, default=str)
    good = declared in most and all(n["ok"] for n in neg.values()) and all(all(v) for v in parts.values())
    print(f"[concepts] {'PASS' if good else 'FAIL'}: rsa/out/experiment_concepts.json, experiment_concepts.png, experiment_partonomy.png")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
