"""LDL, the lab designator language (v0.2): parser, lint, entity resolution and the partial order of an experiment.

An experiment is a set of lab action designators over entity designators (docs/rsa/LAB-DESIGNATOR-LANGUAGE.md). The
order is not written; it is derived:

  * every step instantiates its category contract (registry/lab/contracts.ldl) by unifying the contract's role
    patterns with the step's slots and, through a variable, with the experiment's entity declaration;
  * a requires-item of a step is supported by a *causal link* from the step (or the given state) whose achieves-item
    entails it. Entailment is subsumption of partial descriptions: the more specific description entails the less
    specific one, entity variables are compared by their resolved referent (EQ6/EQ7);
  * `known` items are verified by the realization and `:establishable` items may be established by it; neither
    orders lab steps;
  * a link carrying a functional state (culture-time, in, contained) is *threatened* by a step that achieves another
    value of it; the threat must be resolved by the derived order (classical partial-order planning);
  * prevents-items of a step that another, unordered step would achieve make the two mutually exclusive in time.

One linear extension, grouped by culture-time, is the kernel's Experiment; the symbolic run is compared with the run
built from the planner's plan.

    env_cad/bin/python -m rsa.ldl            # check challenge_rescue.ldl, negative controls, kernel bridge
"""

from __future__ import annotations

import copy
import itertools
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.join(HERE, "registry", "lab")
OUT = os.path.join(HERE, "out")

DET = {"a", "an", "the", "some", "each"}
FUNCTIONAL = {"culture-time", "in", "contained"}
ANN_ARITY = {":column": 1, ":tolerance": 2, ":establishable": 0, ":consequential": 0}
#: lab process type -> (device function, capability verb) the instrument must offer (Cell 01 component records)
PROCESS = {"substance-transfer": ("dispensing", "dose_well"), "imaging": ("imaging", "image_well"),
           "incubation": ("incubation", "incubate_plate"), "containment": ("quarantine", "isolate_sample"),
           "qualification": ("calibration", "validate_imager")}
#: lab readout -> the device readout channel its measurement binding is recorded under (registry devices.yaml)
READOUT = {"organoid-radius": "organoid_radius_um"}
CLAUSES = ("requires", "prevents", "maintains", "achieves")
FORBIDDEN_SORTS = {"robot", "gripper", "tool", "pose", "frame", "prim", "trajectory", "motion"}
DEVICE_IDS = {"l09", "l10", "l12", "l17", "l21", "h2", "h4", "hn", "handovernest", "r01", "r02", "r03", "t01", "t02",
              "t03", "t04", "t05", "tcm01", "cell01"}


# ------------------------------------------------------------------------------------------------- reading
class Splice(list):
    """A variable bound to the rest of a slot (`(dose 0.85 au)` binds ?q to 0.85 au); spliced on substitution."""


def parse(text: str) -> List[Any]:
    """S-expressions; `;` starts a comment outside a string; "quoted strings" stay one token (with their quotes)."""
    toks, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch == ";":
            while i < n and text[i] != "\n":
                i += 1
        elif ch == '"':
            j = text.index('"', i + 1)
            toks.append(text[i:j + 1])
            i = j + 1
        elif ch in "()":
            toks.append(ch)
            i += 1
        elif ch.isspace():
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '();"':
                j += 1
            toks.append(text[i:j])
            i = j
    out: List[Any] = []
    stack = [out]
    for t in toks:
        if t == "(":
            stack[-1].append([])
            stack.append(stack[-1][-1])
        elif t == ")":
            stack.pop()
        else:
            stack[-1].append(t)
    return out


def unq(x: str) -> str:
    return x[1:-1] if isinstance(x, str) and x.startswith('"') else x


def is_var(x) -> bool:
    return isinstance(x, str) and x.startswith("?")


def is_desig(x) -> bool:
    return isinstance(x, list) and len(x) >= 2 and isinstance(x[0], str) and x[0] in DET and isinstance(x[1], str)


def dvar(d) -> Optional[str]:
    return d[2] if len(d) > 2 and is_var(d[2]) else None


def dslots(d) -> List[list]:
    return [s for s in d[2:] if isinstance(s, list)]


def slot(d, name):
    return next((s for s in dslots(d) if s and s[0] == name), None)


def slot_l(lst, name):
    return next((e for e in lst if isinstance(e, list) and e and e[0] == name), None)


def _localize(x, prefix):
    """Contract variables still unbound after instantiation (e.g. a portion ?u, the instrument ?d) become step-local."""
    if isinstance(x, str) and x.startswith("?_"):
        return prefix + x[2:]
    if isinstance(x, list):
        return [_localize(e, prefix) for e in x]
    return x


def fmt(x) -> str:
    if isinstance(x, list):
        return "(" + " ".join(fmt(e) for e in x) + ")"
    return str(x)


def items(clause: list) -> List[Dict[str, Any]]:
    """Clause body -> [{cond, known, ann}] (annotations follow the item they qualify)."""
    out: List[Dict[str, Any]] = []
    i = 1
    while i < len(clause):
        e = clause[i]
        if isinstance(e, str) and e in ANN_ARITY:
            n = ANN_ARITY[e]
            out[-1]["ann"][e] = " ".join(clause[i + 1:i + 1 + n]) if n else True
            i += 1 + n
            continue
        head = e[0] if isinstance(e, list) and e else None
        if head == "known":
            out.append(dict(cond=e[1], known=True, grade=dict(source="observed", freshness="fresh"), ann={}))
        elif head == "believed":
            g = {x[0]: x[1] for x in e[2][1:]} if len(e) > 2 else {}
            out.append(dict(cond=e[1], known=True, grade=dict(dict(freshness="fresh"), **g), ann={}))
        else:
            out.append(dict(cond=e, known=False, grade=None, ann={}))
        i += 1
    return out


def subst(x, th):
    if is_var(x):
        return th.get(x, x)
    if isinstance(x, list):
        out = []
        for e in x:
            s = subst(e, th)
            out.extend(s) if isinstance(s, Splice) else out.append(s)
        return out
    return x


def rename(x, prefix="?_"):
    if is_var(x):
        return prefix + x[1:]
    if isinstance(x, list):
        return [rename(e, prefix) for e in x]
    return x


# ------------------------------------------------------------------------------------------------- knowledge
class World:
    """What the lab text is resolved against: the planner's facts, the derived plan (design), the SDT ABox and the
    kernel registry (all read-only)."""

    def __init__(self, tag="g050"):
        from .kb import FACTS_DIR, PLAN_DIR
        self.facts = open(os.path.join(FACTS_DIR, f"facts_{tag}.lp")).read()
        self.plan = json.load(open(os.path.join(PLAN_DIR, f"plan_{tag}.json")))
        self.devices = yaml.safe_load(open(os.path.join(HERE, "registry", "devices.yaml")))
        sdt = os.path.join(HERE, "..", "okf", "lab-automation-twin", "abox", "sdt.ofn")
        self.sdt = open(sdt).read()
        from .run_example import experiment_plate
        self.plate_id = experiment_plate()
        self.tag = tag
        from .kb import KB
        self.kb = KB.load(tag)

    def fact(self, pred):
        return re.findall(pred + r"\(([^)]*)\)", self.facts)

    def sdt_node(self, path):
        return f"lab1{path}#entity>" in self.sdt


def resolve(decls: Dict[str, list], world: World, drop_roles=()) -> Dict[str, Dict[str, Any]]:
    """Each entity declaration -> referent with grounds (answer substitution over the knowledge) or an error."""
    out: Dict[str, Dict[str, Any]] = {}
    wells = {k: v for k, v in world.plan["wells"].items() if k not in drop_roles}
    for var, d in decls.items():
        sort, r = d[1], dict(decl=fmt(d), det=d[0])
        if sort == "design":
            did = slot(d, "id")[1]
            ok = world.plan["selected"]["id"] == did
            r.update(ref=f"design:{did}" if ok else None, roles=wells,
                     grounds=[f"plan_{world.tag}.selected.id = {world.plan['selected']['id']}",
                              f"requirement {world.plan['requirement_bits']} bit, EIG {world.plan['selected']['eig_bits']} bit"])
        elif sort == "plate":
            pid = slot(d, "id")[1]
            node = f"/World/ExperimentalWorld/Plates/Plate_{pid}"
            ok = pid == world.plate_id and world.sdt_node(node)
            r.update(ref=f"plate:{pid}" if ok else None, sdt=node + "#entity",
                     grounds=[f"experiments.ofn plate {world.plate_id}", f"sdt.ofn {node}#entity (SBSMicroplate, CulturePlate)"])
        elif sort == "well":
            role = slot(d, "role")[1]
            cand = wells.get(role, [])
            plate = out.get(slot(d, "of")[1], {}).get("ref", "plate:?").split(":")[1]
            node = f"/World/ExperimentalWorld/Plates/Plate_{plate}/Wells/{cand[0]}" if cand else None
            ok = len(cand) == 1 and world.sdt_node(node)
            r.update(ref=f"well:{cand[0]}" if ok else None, sdt=(node + "#entity") if node else None,
                     grounds=[f"design arm {role} = {cand}", f"hasDirectComponent(Plate_{plate}, Wells/{cand[0]})"
                              if cand else "no well with this role"])
        elif sort == "substance":
            typ = slot(d, "type")[1]
            rg = (world.devices.get("reagents") or {}).get(typ)
            pose = [p for p in world.fact("reagent_pose") if p.startswith(typ + ",")]
            r.update(ref=f"substance:{typ}" if rg else None,
                     grounds=[f"registry reagents.{typ} lot {rg['lot']}" if rg else "no reagent", *[f"reagent_pose({p})" for p in pose]])
        elif sort == "controlled-environment":
            cand = sorted(x.split(",")[0] for x in world.fact("has_function") if x.endswith(",incubation"))
            rej = sorted({x.split(",")[0] for x in world.fact("holds_plate")} - set(cand))
            r.update(ref=f"environment:{cand[0]}" if len(cand) == 1 else None, answers=cand, rejected=rej,
                     grounds=[f"has_function({c},incubation)" for c in cand],
                     note="profile not modelled in the knowledge (unchecked)")
        else:
            r.update(ref=None, grounds=[f"no resolver for sort {sort}"])
        out[var] = r
    return out


# ------------------------------------------------------------------------------------------------- the experiment
class Experiment:
    def __init__(self, text: str, contracts_text: str, world: World, drop_roles=()):
        root = parse(text)[0]
        self.root = root
        self.var = dvar(root)
        get = lambda name: next((s for s in dslots(root) if s[0] == name), [name])
        self.decls = {dvar(d): d for d in get("entities")[1:]}
        self.res = resolve(self.decls, world, drop_roles)
        self.ref = {v: r.get("ref") for v, r in self.res.items()}
        self.given = items(get("given"))
        self.clauses = {c: items(get(c)) for c in CLAUSES + ("goal",)}
        self.quality = get("quality")[1:]
        self.handles = get("handles")[1:]
        self.contracts_root = parse(contracts_text)
        self.contracts = {c[1]: rename(c[2:]) for c in self.contracts_root}
        self.steps = [self._instantiate(s) for s in get("steps")[1:]]
        self.by = {s["var"]: s for s in self.steps}
        self.world = world

    # -- instantiation
    def _deref(self, v):
        return self.decls.get(v) if is_var(v) else None

    def _unify(self, pat, val, th) -> bool:
        if is_var(pat):
            th[pat] = val
            return True
        if isinstance(pat, str):
            return pat == val
        if is_desig(pat):
            d = self._deref(val) if is_var(val) else val if is_desig(val) else None
            if d is None or d[1] != pat[1]:
                return False
            if dvar(pat):
                th[dvar(pat)] = val if is_var(val) else (dvar(d) or val)
            for ps in dslots(pat):
                ds = slot(d, ps[0])
                if ds is None or not self._unify(ps[1], ds[1] if len(ds) == 2 else Splice(ds[1:]), th):
                    return False
            return True
        if isinstance(pat, list) and isinstance(val, list) and pat and val and pat[0] == val[0]:
            if len(pat) == 2 and is_var(pat[1]):
                th[pat[1]] = val[1] if len(val) == 2 else Splice(val[1:])
                return True
            return len(pat) == len(val) and all(self._unify(p, v, th) for p, v in zip(pat[1:], val[1:]))
        return False

    def _instantiate(self, s) -> Dict[str, Any]:
        typ = slot(s, "type")[1]
        k = self.contracts[typ]
        kget = lambda n: next((e for e in k if e[0] == n), [n])  # noqa: E731
        th: Dict[str, Any] = {"?_self": dvar(s)}
        unbound = []
        for role in kget("roles")[1:]:
            sv = slot(s, role[0])
            val = None if sv is None else (sv[1] if len(sv) == 2 else Splice(sv[1:]))
            if val is None or not self._unify(role[1], val, th):
                unbound.append(role[0])
        local = "?" + dvar(s)[1:] + "."
        loc = lambda x: _localize(subst(x, th), local)  # noqa: E731
        st = dict(var=dvar(s), type=typ, text=fmt(s), unbound=unbound,
                  slots={x[0]: fmt(x[1]) if len(x) == 2 else " ".join(map(fmt, x[1:])) for x in dslots(s) if x[0] != "type"})
        for c in CLAUSES + ("goal",):
            st[c] = [dict(it, cond=loc(it["cond"]), source="contract", scope=None) for it in items(kget(c))]
            st[c] += [dict(it, source="step", scope=None) for it in items(slot(s, c) or [c])]
        for sc in (e for e in k if e[0] == "scope"):
            beg, end = loc(slot_l(sc, "begins-when")[1]), loc(slot_l(sc, "ends-when")[1])
            for inner in sc[1:]:
                if inner[0] in ("prevents", "maintains"):
                    st[inner[0]] += [dict(it, cond=loc(it["cond"]), source="contract", scope=(fmt(beg), fmt(end)))
                                     for it in items(inner)]
        ins = kget("instrument")
        st["instrument"] = loc(ins[1]) if len(ins) > 1 else None
        st["signals"] = [slot(loc(f), "type")[1] for f in kget("signals")[1:]]
        at = slot(s, "at") or slot(s, "to")
        st["time_h"] = float(at[1][1]) if at else None
        return st

    # -- entailment (subsumption of partial descriptions, referents compared after resolution)
    def _same(self, a, b) -> bool:
        if a == b:
            return True
        ra, rb = self.ref.get(a) if is_var(a) else None, self.ref.get(b) if is_var(b) else None
        return ra is not None and ra == rb

    def _match(self, av, rv) -> bool:
        if is_var(rv):
            return self._same(av, rv)
        if isinstance(rv, str):
            return av == rv
        if is_desig(rv):
            ad = self._deref(av) if is_var(av) else av
            return is_desig(ad) and self.entails(ad, rv, avar=av if is_var(av) else None)
        if isinstance(av, list) and av and av[0] == rv[0]:
            return all(any(self._match(a, r) for a in av[1:]) for r in rv[1:])
        return False

    def entails(self, a, r, avar=None) -> bool:
        if not (is_desig(a) and is_desig(r)) or a[1] != r[1]:
            return False
        aref = avar or dvar(a)
        if dvar(r) and not (aref and self._same(aref, dvar(r))):
            return False
        for rs in dslots(r):
            if rs[0] == "not":
                if any(aref and self._same(aref, x) for x in rs[1:]):
                    return False
                continue
            if not any(all(any(self._match(av, rv) for av in as_[1:]) for rv in rs[1:])
                       for as_ in dslots(a) if as_[0] == rs[0]):
                return False
        return True

    # -- the order
    def links(self):
        links, unsupported, verified, established = [], [], [], []
        for s in self.steps:
            for it in s["requires"]:
                c = it["cond"]
                if it["known"]:
                    verified.append((s["var"], fmt(c)))
                    continue
                prod = ["start"] if any(self.entails(g["cond"], c) for g in self.given) else []
                prod += [p["var"] for p in self.steps if p is not s
                         and any(self.entails(a["cond"], c) for a in p["goal"] + p["achieves"])]
                if prod:
                    links += [dict(frm=p, to=s["var"], cond=fmt(c), cond_l=c) for p in prod]
                elif it["ann"].get(":establishable"):
                    established.append((s["var"], fmt(c)))
                else:
                    unsupported.append((s["var"], fmt(c)))
        return links, unsupported, verified, established

    def order(self, links):
        V = [s["var"] for s in self.steps]
        before = {v: set() for v in V}           # before[b] = steps that must precede b
        for l in links:
            if l["frm"] != "start":
                before[l["to"]].add(l["frm"])
        changed = True
        while changed:
            changed = False
            for v in V:
                new = set().union(*(before[u] for u in before[v])) if before[v] else set()
                if not new <= before[v]:
                    before[v] |= new
                    changed = True
        cyclic = [v for v in V if v in before[v]]
        lt = lambda a, b: (a == "start" and b != "start") or (b in before and a in before[b])
        hasse = sorted({(l["frm"], l["to"]) for l in links if l["frm"] != "start"
                        and not any(lt(l["frm"], m) and lt(m, l["to"]) for m in V)})
        return before, lt, hasse, cyclic

    def threats(self, links, lt):
        out = []
        for l in links:
            c = l["cond_l"]
            subj = dvar(c)
            for fs in dslots(c):
                if fs[0] not in FUNCTIONAL:
                    continue
                for t in self.steps:
                    if t["var"] in (l["frm"], l["to"]):
                        continue
                    for a in t["goal"] + t["achieves"]:
                        ad = a["cond"]
                        if not (is_desig(ad) and ad[1] == c[1] and dvar(ad) and self._same(dvar(ad), subj)):
                            continue
                        other = slot(ad, fs[0])
                        if other is None or other[1:] == fs[1:]:
                            continue
                        ok = (l["frm"] != "start" and lt(t["var"], l["frm"])) or lt(l["to"], t["var"])
                        out.append(dict(link=f"{l['frm']} -> {l['to']}", cond=l["cond"], by=t["var"],
                                        achieves=fmt(ad), resolved=ok,
                                        how=("demoted" if lt(t["var"], l["frm"]) else "promoted") if ok else None))
        return out

    def exclusions(self, lt):
        out = []
        for s, t in itertools.permutations(self.steps, 2):
            if lt(s["var"], t["var"]) or lt(t["var"], s["var"]):
                continue
            for p in s["prevents"]:
                for a in t["goal"] + t["achieves"]:
                    if self.entails(a["cond"], p["cond"]):
                        out.append(dict(pair=sorted([s["var"], t["var"]]), prevented_by=s["var"], cond=fmt(p["cond"]),
                                        would_occur=fmt(a["cond"]), scope=p.get("scope")))
        uniq = {tuple(x["pair"]): x for x in out}
        return list(uniq.values())

    def experiment_checks(self):
        out = []
        for it in self.clauses["requires"]:
            c = it["cond"]
            if it["known"]:
                out.append(dict(clause="requires", cond=fmt(c), status="verified by the realization"))
            elif c[1] == "design":
                arm = slot(c, "arm")
                role = arm[1][1] if arm and isinstance(arm[1], list) and arm[1][0] == "role" else None
                ok = role in self.res[dvar(c)].get("roles", {})
                out.append(dict(clause="requires", cond=fmt(c), status="holds in the design" if ok else "VIOLATED",
                                ok=ok, column=it["ann"].get(":column", "realization")))
        for it in self.clauses["prevents"]:
            hits = [s["var"] for s in self.steps for a in s["goal"] + s["achieves"] if self.entails(a["cond"], it["cond"])]
            out.append(dict(clause="prevents", cond=fmt(it["cond"]), ok=not hits,
                            status=f"VIOLATED by {hits}" if hits else "no step achieves it (statically)"))
        for it in self.clauses["achieves"]:
            prod = [s["var"] for s in self.steps if any(self.entails(a["cond"], it["cond"]) for a in s["goal"] + s["achieves"])]
            est = it["ann"].get(":establishable")
            out.append(dict(clause="achieves", cond=fmt(it["cond"]), ok=bool(prod or est),
                            status=f"achieved by {prod}" if prod else "established by the realization" if est else "UNSUPPORTED",
                            column=it["ann"].get(":column", "realization")))
        for it in self.clauses["goal"]:
            ig = slot(it["cond"], "information-gain")
            need = float(ig[1][1]) if ig else None
            eig, req = self.world.plan["selected"]["eig_bits"], self.world.plan["requirement_bits"]
            ok = need is not None and eig >= need and all(c.get("ok", True) for c in out if c["clause"] == "achieves")
            out.append(dict(clause="goal", cond=fmt(it["cond"]), ok=ok,
                            status=f"supported: the design's EIG {eig} bit >= {need} bit (requirement {req} bit), given "
                                   f"the achieved measurements" if ok else "UNSUPPORTED"))
        return out

    # -- v0.2: instruments, goals, failures, epistemic grades
    def instrument(self, st) -> Optional[Dict[str, Any]]:
        d = st.get("instrument")
        if not d:
            return None
        ptype = slot(slot(d, "process")[1], "type")[1]
        f, verb = PROCESS.get(ptype, (None, None))
        seats = dict(x.split(",", 1) for x in self.world.fact("seat"))
        funcs = set(self.world.fact("has_function"))
        q = slot(d, "qualified-for")
        answers, rejected = [], []
        for dev in sorted(set(self.world.fact("automated"))):
            why = []
            if f is None:
                why.append(f"no device function realises process {ptype}")
            elif f"{dev},{f}" not in funcs:
                why.append(f"no function {f}")
            if verb and verb not in self.world.kb.capabilities(dev):
                why.append(f"no capability {verb}")
            if dev not in seats:
                why.append("no plate slot")
            if q and not why:
                b = self.world.kb.measurement_binding(dev, READOUT.get(q[1], q[1]))
                if b.value != "validated":
                    why.append(f"binding {b.value} for {q[1]}")
            if why:
                rejected.append([dev, "; ".join(why)])
            else:
                answers.append(dict(device=dev, slot=seats[dev], grounds=[f"has_function({dev},{f})",
                               f"capabilities({dev})∋{verb}", f"seat({dev},{seats[dev]})"]
                               + ([f"measurement_binding({dev},{READOUT.get(q[1], q[1])}) = validated"] if q else [])))
        return dict(step=st["var"], process=ptype, function=f, capability=verb, description=fmt(d),
                    answers=answers, rejected=rejected, ok=bool(answers))

    def justification(self, links) -> Dict[str, bool]:
        just = {s["var"] for s in self.steps
                if any(self.entails(a["cond"], it["cond"]) for it in self.clauses["achieves"] for a in s["goal"] + s["achieves"])}
        changed = True
        while changed:
            changed = False
            for l in links:
                if l["to"] in just and l["frm"] != "start" and l["frm"] not in just:
                    just.add(l["frm"])
                    changed = True
        return {s["var"]: s["var"] in just for s in self.steps}

    def failures(self) -> List[Dict[str, Any]]:
        hs = []
        for h in self.handles:
            f = h[1]
            hs.append(dict(type=slot(f, "type")[1], cause=(slot(f, "cause") or [None, None])[1],
                           do=[fmt(x[1]) for x in h[2:] if x[0] == "do"], then=[fmt(x[1]) for x in h[2:] if x[0] == "then"],
                           orelse=[fmt(x[1]) for x in h[2:] if x[0] == "else"]))
        out = []
        for s_ in self.steps:
            for typ in s_["signals"]:
                m = [h for h in hs if h["type"] == typ]
                out.append(dict(step=s_["var"], failure=typ, handled=bool(m), handlers=m))
        return out

    def lint(self) -> List[str]:
        bad = []

        def walk(x, parent=None):
            if isinstance(x, list):
                if is_desig(x) and x[1] in FORBIDDEN_SORTS:
                    bad.append(f"sort '{x[1]}' in {fmt(x)}")
                if is_desig(x) and x[1] == "instrument" and x[0] == "the":
                    bad.append(f"referential instrument {fmt(x)}")
                for e in x:
                    walk(e, x)
            elif isinstance(x, str) and x.lower() in DEVICE_IDS:
                bad.append(f"device or robot id '{x}' in {fmt(parent)}")
            elif isinstance(x, str) and x in ("uL", "µL", "mL"):
                bad.append(f"volume in {fmt(parent)}")
        walk(self.root)
        walk(self.contracts_root)
        return bad

    # -- realization bridge
    def linear_extension(self, before):
        order, done = [], set()
        while len(order) < len(self.steps):
            nxt = next(s for s in self.steps if s["var"] not in done and before[s["var"]] <= done)
            order.append(nxt)
            done.add(nxt["var"])
        return order

    def to_kernel(self, order):
        from .core import Plate
        from .library import Experiment as KExperiment
        well = lambda v: self.ref[v].split(":")[1]
        sessions: List[Dict[str, Any]] = []
        for s in order:
            if s["type"] == "incubating":
                continue
            t = s["time_h"]
            if not sessions or sessions[-1]["t_h"] != t:
                sessions.append(dict(session=f"s{len(sessions)}", trip=1, t_h=int(t), material=[]))
            if s["type"] == "intervening":
                into, sub = slot_raw(s, "into"), slot_raw(s, "substance")
                dose = float(s["slots"]["dose"].split()[0])
                sessions[-1]["material"].append(["dose", well(into).lower(), self.ref[sub].split(":")[1], int(round(dose * 100))])
            elif s["type"] == "measuring":
                sessions[-1]["material"].append(["image", well(slot_raw(s, "of")).lower()])
        des = next(v for v, r in self.res.items() if r.get("ref", "") and r["ref"].startswith("design:"))
        roles = {self.res[v]["decl"].split("(role ")[1].rstrip(")"): [self.ref[v].split(":")[1]]
                 for v in self.decls if self.decls[v][1] == "well"}
        plate = next(r["ref"].split(":")[1] for r in self.res.values() if (r.get("ref") or "").startswith("plate:"))
        sel = self.world.plan["selected"]
        return KExperiment(design=self.res[des]["ref"].split(":", 1)[1], requirement_bits=self.world.plan["requirement_bits"],
                           eig_bits=sel["eig_bits"], plate=Plate(plate), wells=roles, sessions=sessions), sessions


def slot_raw(st, name):
    m = re.search(r"\(" + name + r" (\?\w+)\)", st["text"])
    return m.group(1) if m else None


# ------------------------------------------------------------------------------------------------- kernel runs
def run_kernel(exp, name):
    from .audit import AuditTrail
    from .backend import SymbolicWorld
    from .core import KERNEL_VERSION, Belief, Context, perform
    from .critic import assess
    from .kb import KB
    from .run_example import registry_sha, scenario_kb
    kb = scenario_kb(KB.load("g050"), {}, f"facts_g050+{name}")
    world = SymbolicWorld(kb, faults=None)
    belief = Belief()
    world.initial_belief(belief, exp.plate.id)
    trail = AuditTrail(f"challenge-rescue/{name}", dict(kernel=KERNEL_VERSION, kb=kb.name, registry=registry_sha(),
                                                         backend=world.name))
    ctx = Context(kb, world, trail, belief)
    perform(exp, ctx)
    root = ctx.root
    lab = []
    for n in root.walk():
        d = n.designator
        if d.category in ("intervene", "measure", "wait"):
            lab.append((d.category, getattr(d, "well", ""), getattr(d, "reagent", ""), getattr(d, "until_h", None)))
    td = trail.as_dict()
    v = assess(td)
    return dict(leaves=[list(map(str, n.designator.term())) for n in root.leaves()], entries=len(td["entries"]),
                end=root.lifecycle[-1], clock_s=round(world.clock, 1), lab=lab,
                realization=v["realization"]["ok"], validity=v["validity"]["ok"])


def ldl_contract_goal(E, typ):
    k = E.contracts.get(typ)
    g = next((e for e in k if e[0] == "goal"), None) if k else None
    return items(g)[0]["cond"] if g and len(g) > 1 else None


# ------------------------------------------------------------------------------------------------- report
def check(text, contracts, world, drop_roles=(), processes=None, meta_text=None) -> Dict[str, Any]:
    E = Experiment(text, contracts, world, drop_roles)
    links, unsupported, verified, established = E.links()
    before, lt, hasse, cyclic = E.order(links)
    thr = E.threats(links, lt)
    exc = E.exclusions(lt)
    expc = E.experiment_checks()
    lint = E.lint()
    unresolved_refs = [v for v, r in E.ref.items() if r is None]
    ins = [E.instrument(s) for s in E.steps]
    just = E.justification(links)
    fails = E.failures()
    from . import ldl_trust as LT
    models = LT.load_models(processes if processes is not None else open(os.path.join(LAB, "processes.ldl")).read())
    meta = LT.Meta(meta_text if meta_text is not None else open(os.path.join(LAB, "epistemic.ldl")).read())
    hs = LT.handlers(E)
    if E.clauses["prevents"]:
        fails.append(dict(step=E.var, failure="prevents-violated", handled=any(h["type"] == "prevents-violated" for h in hs), handlers=[]))
    grounding = LT.ground(models)
    trust = LT.trust(E, models, hs)
    guar = LT.guarantees(E, models, hs)
    fcov = LT.fault_coverage(E, models, hs)
    epi = LT.epistemic(E, meta)
    ok = not (unsupported or cyclic or lint or unresolved_refs or any(not t["resolved"] for t in thr)
              or any(c.get("ok") is False for c in expc) or any(s["unbound"] for s in E.steps)
              or any(i and not i["ok"] for i in ins) or not all(just.values()) or any(not f["handled"] for f in fails)
              or any(not e["ok"] for e in epi) or any(not g["ok"] for g in grounding) or any(not g["ok"] for g in guar)
              or any(not f["handled"] for f in fcov))
    return dict(ok=ok, E=E, links=links, unsupported=unsupported, verified=verified, established=established,
                before=before, lt=lt, hasse=hasse, cyclic=cyclic, threats=thr, exclusions=exc, experiment=expc,
                lint=lint, unresolved_refs=unresolved_refs, instruments=ins, justified=just, failures=fails, epistemic=epi,
                grounding=grounding, trust=trust, guarantees=guar, fault_coverage=fcov, handlers_=hs, models=models, meta=meta)


def main(argv):
    world = World("g050")
    text = open(os.path.join(LAB, "challenge_rescue.ldl")).read()
    contracts = open(os.path.join(LAB, "contracts.ldl")).read()
    r = check(text, contracts, world)
    E = r["E"]
    V = [s["var"] for s in E.steps]
    n_ext = sum(1 for p in itertools.permutations(V)
                if all(not r["lt"](p[j], p[i]) for i in range(len(p)) for j in range(i + 1, len(p))))
    print(f"[ldl] {len(E.decls)} entity designators, {len(E.steps)} action designators, {len(r['links'])} causal links")
    for v, x in E.res.items():
        print(f"[ldl]   {v:4} {x['decl']:60} -> {x.get('ref')}")
    print(f"[ldl] order (Hasse): {', '.join(f'{a} < {b}' for a, b in r['hasse'])}; {n_ext} linear extensions")
    print(f"[ldl] threats {len(r['threats'])}, unresolved {sum(not t['resolved'] for t in r['threats'])}; "
          f"mutual exclusions {[x['pair'] for x in r['exclusions']]}; unsupported {r['unsupported']}; lint {r['lint']}")

    for i in r["instruments"]:
        print(f"[ldl] instrument of {i['step']}: process {i['process']} -> {[a['device'] + ' @' + a['slot'] for a in i['answers']]}"
              f" (rejected {len(i['rejected'])})")
    print(f"[ldl] goals justified: {sum(r['justified'].values())}/{len(r['justified'])}; failures handled "
          f"{sum(f['handled'] for f in r['failures'])}/{len(r['failures'])}; epistemic requirements with a treatment for "
          f"every shortfall {sum(e['ok'] for e in r['epistemic'])}/{len(r['epistemic'])}")
    from . import ldl_trust as LT
    for g in r["grounding"]:
        print(f"[ldl] process model {g['process']:18} grounded in {g['component']}: {g['faults']}/{g['record_faults']} record faults "
              f"modelled{'; PROBLEMS ' + str(g['problems']) if g['problems'] else ''}{'; unmodelled ' + str(g['unmodelled']) if g['unmodelled'] else ''}")
    for t in r["trust"]:
        print(f"[ldl] trust {t['step']} ({t['process']}): {len(t['faults'])} faults can corrupt its effects; partly or not detected "
              f"{t['silent'] or 'none'}; detected only after the irreversible phase {t['irreparable'] or 'none'}; "
              f"unhandled {t['unhandled'] or 'none'}")
    for g in r["guarantees"]:
        print(f"[ldl] guarantee {g['type']}{'/' + g['cause'] if g['cause'] else ''}: claims {g['claims']} -> "
              f"{'holds' if g['ok'] else 'FAILS ' + str([w for c in g['checks'].values() for w in c['why']])}")
    emp = LT.empirical(r["handlers_"], LT.KPI_RUNS)
    for x in emp:
        print(f"[ldl] in run {x['run']:24} {x['failure']:18} at {x['at']:12} -> {x['outcome']}; claim {x['claims']} held: {x['held']}"
              f"{'' if x['as_prescribed'] else '; the kernel repaired by ' + str(x['repair']) + ', the handler prescribes ' + str(x['prescribed'])}")
    kt = LT.kpi_table(E)
    for run in kt["runs"]:
        print(f"[ldl] KPI {run['run']:26} end={run['end']:9} " + " ".join(
            f"{k['name']}={run[k['name']]}{'' if run['met'][k['name']] in (None, True) else '!'}" for k in kt["kpis"]))
    print(f"[ldl] quality ranking (lexicographic {kt['prefers']}): {kt['ranking']}")

    # negative controls: each must be caught
    neg = {}
    t1 = re.sub(r"\n\s+\(requires \(the well \?r \(received \?ch\)\) \(the well \?c \(received \?ch\)\)\)\)", ")", text)
    t1 = re.sub(r"\n\s+\(requires \(the well \?r \(received \?rs\)\)\)\)", ")", t1)
    a = check(t1, contracts, world)
    neg["N1 design anchors removed"] = dict(caught=any(not t["resolved"] for t in a["threats"]),
                                            by=[f"{t['by']} threatens {t['link']} ({t['cond']})" for t in a["threats"] if not t["resolved"]][:4])
    t2 = text.replace("(an action ?m3", "(an action ?x9 (type intervening) (into ?k) (substance ?ch) (dose 0.85 au) "
                                        "(at (culture-time 0 h)))\n    (an action ?m3")
    b = check(t2, contracts, world)
    neg["N2 control well dosed"] = dict(caught=any(c.get("ok") is False and c["clause"] == "prevents" for c in b["experiment"]),
                                        by=[c["status"] for c in b["experiment"] if c.get("ok") is False])
    c = check(text, contracts, world, drop_roles=("control",))
    neg["N3 design without a control arm"] = dict(caught=not c["ok"], by=[*c["unresolved_refs"],
                                                  *[x["status"] for x in c["experiment"] if x.get("ok") is False]][:3])
    t4 = text.replace("(readout organoid-radius) (at (culture-time 72 h)))\n    (an action ?m2",
                      "(readout organoid-radius) (at (culture-time 72 h)) (on l17))\n    (an action ?m2")
    d = check(t4, contracts, world)
    neg["N4 device named in lab text"] = dict(caught=bool(d["lint"]), by=d["lint"][:2])
    t5 = text.replace("(an action ?x3 (type intervening) (into ?r) (substance ?rs) (dose 0.70 au) (at (culture-time 48 h)))",
                      "(an action ?x3 (type intervening) (into ?r) (substance ?rs) (dose 0.70 au) (at (culture-time 36 h)))")
    e = check(t5, contracts, world)
    neg["N5 rescue at a culture time nothing achieves"] = dict(caught=bool(e["unsupported"]), by=[f"{s}: {c}" for s, c in e["unsupported"]][:2])
    t6 = re.sub(r"\n    \(on \(a failure \(type identity-mismatch\)\)\n.*\n.*\n.*\(guarantees safe-state contained\)\)", "", text)
    f6 = check(t6, contracts, world)
    neg["N6 identity-mismatch handler removed"] = dict(caught=any(not f["handled"] for f in f6["failures"]),
                                                      by=sorted({f"{f['step']}: {f['failure']} unhandled" for f in f6["failures"] if not f["handled"]})[:2])
    c7 = contracts.replace("(process (a process (type imaging)", "(process (a process (type sequencing)")
    g7 = check(text, c7, world)
    neg["N7 instrument process no device offers"] = dict(caught=any(i and not i["ok"] for i in g7["instruments"]),
                                                        by=[f"{i['step']}: {i['rejected'][0]}" for i in g7["instruments"] if i and not i["ok"]][:2])
    t8 = text.replace("(an action ?m3 (type measuring) (of ?k)", "(an action ?m9 (type measuring) (of ?r) "
                      "(readout organoid-count) (at (culture-time 72 h)))\n    (an action ?m3 (type measuring) (of ?k)")
    h8 = check(t8, contracts, world)
    neg["N8 a step whose goal serves nothing"] = dict(caught=not all(h8["justified"].values()),
                                                     by=[f"{k} unjustified" for k, v in h8["justified"].items() if not v][:2])
    t9 = text.replace("(on (a failure (type measurement-invalid) (cause out_of_focus))\n        (do (re-establish (the plate ?p (seated true))))",
                      "(on (a failure (type measurement-invalid) (cause out_of_focus))")
    i9 = check(t9, contracts, world)
    neg["N9 focus retry without re-seating (F17)"] = dict(caught=any(not g["ok"] for g in i9["guarantees"]),
        by=[w for g in i9["guarantees"] for c in g["checks"].values() for w in c["why"]][:1])
    p10 = open(os.path.join(LAB, "processes.ldl")).read().replace("(name well_misregistration)", "(name pipette_crash)")
    j10 = check(text, contracts, world, processes=p10)
    neg["N10 process fault not in the component record"] = dict(caught=any(not g["ok"] for g in j10["grounding"]),
        by=[f"{g['component']}: {g['problems'][:1]} unmodelled {g['unmodelled']}" for g in j10["grounding"] if not g["ok"]][:1])
    t11 = text.replace("(on (a failure (type dose-not-delivered) (cause well_misregistration))\n"
                       "        (do (an action (type quarantining) (material ?p)))\n        (then escalate)\n"
                       "        (guarantees safe-state contained))",
                       "(on (a failure (type dose-not-delivered) (cause well_misregistration))\n"
                       "        (do (re-establish (the plate ?p (seated true))))\n        (then (retry (max 1))) (else escalate)\n"
                       "        (guarantees goal-or-safe-state))")
    k11 = check(t11, contracts, world)
    neg["N11 repair claims the goal after the irreversible phase"] = dict(caught=t11 != text and any(not g["ok"] for g in k11["guarantees"]),
        by=[w for g in k11["guarantees"] for c in g["checks"].values() for w in c["why"]][:1])
    m12 = open(os.path.join(LAB, "epistemic.ldl")).read()
    m12 = re.sub(r"\n  \(rule inferred-consequential\n(.*\n){3}", "\n", m12)
    m12 = re.sub(r"\n  \(rule assumed-consequential\n(.*\n){3}", "\n", m12)
    l12 = check(text, contracts, world, meta_text=m12)
    neg["N12 meta model without rules for weak consequential beliefs"] = dict(caught=any(not e["ok"] for e in l12["epistemic"]),
        by=[f"{e['item']}: {[k for k, v in e['treatments'].items() if v['treat'] == 'UNTREATED']} untreated" for e in l12["epistemic"] if not e["ok"]][:1])
    for k, v in neg.items():
        print(f"[ldl] negative control {k}: {'caught' if v['caught'] else 'MISSED'} {v['by'][:2]}")

    # kernel bridge: one linear extension of the poset vs the planner's plan
    order = E.linear_extension(r["before"])
    kexp, sessions = E.to_kernel(order)
    from .library import experiment_from_plan
    from .run_example import experiment_plate
    a_run = run_kernel(kexp, "ldl")
    b_run = run_kernel(experiment_from_plan(world.plan, experiment_plate()), "plan")
    same = a_run["leaves"] == b_run["leaves"]
    plan_lab = [x for x in b_run["lab"]]
    pos = {}
    for st in E.steps:
        key = ("intervene" if st["type"] == "intervening" else "measure" if st["type"] == "measuring" else "wait")
        pos[st["var"]] = key
    # the planner's executed lab-level order mapped to LDL steps, checked against the derived order
    seq = []
    pool = list(E.steps)
    for cat, wellid, reagent, until in plan_lab:
        for st in pool:
            if cat == "wait" and st["type"] == "incubating" and st["time_h"] == until:
                seq.append(st["var"]); pool.remove(st); break
            if cat == "intervene" and st["type"] == "intervening" and E.ref[slot_raw(st, "into")] == f"well:{wellid}" \
                    and E.ref[slot_raw(st, "substance")] == f"substance:{reagent}":
                seq.append(st["var"]); pool.remove(st); break
            if cat == "measure" and st["type"] == "measuring" and E.ref[slot_raw(st, "of")] == f"well:{wellid}":
                seq.append(st["var"]); pool.remove(st); break
    consistent = len(seq) == len(E.steps) and all(not r["lt"](seq[j], seq[i]) for i in range(len(seq)) for j in range(i + 1, len(seq)))
    print(f"[ldl] kernel from the LDL poset: {len(a_run['leaves'])} leaves, {a_run['entries']} entries, end {a_run['end']}, "
          f"R={a_run['realization']} V={a_run['validity']}; from the planner's plan: {len(b_run['leaves'])} leaves, "
          f"{b_run['entries']} entries; leaf sequences identical: {same}")
    print(f"[ldl] the planner's executed order {seq} is a linear extension of the LDL order: {consistent}")

    rep = dict(
        entities=[dict(var=v, **{k: x[k] for k in x if k in ("decl", "det", "ref", "sdt", "grounds", "answers", "rejected", "note")})
                  for v, x in E.res.items()],
        steps=[dict(var=s["var"], type=s["type"], text=s["text"], time_h=s["time_h"], slots=s["slots"],
                    instrument=fmt(s["instrument"]) if s["instrument"] else None, signals=s["signals"],
                    **{c: [dict(cond=fmt(i["cond"]), known=i["known"], grade=i.get("grade"), ann=i["ann"], source=i["source"],
                                scope=i.get("scope")) for i in s[c]] for c in CLAUSES + ("goal",)})
               for s in E.steps],
        links=[{k: l[k] for k in ("frm", "to", "cond")} for l in r["links"]], hasse=r["hasse"], linear_extensions=n_ext,
        verified=r["verified"], established=r["established"], unsupported=r["unsupported"], threats=r["threats"],
        exclusions=r["exclusions"], experiment=r["experiment"], lint=r["lint"], ok=r["ok"], negative_controls=neg,
        instruments=r["instruments"], justified=r["justified"], failures=[dict(f, handlers=[dict(h) for h in f["handlers"]])
                                                                           for f in r["failures"]],
        epistemic=r["epistemic"], quality=kt, grounding=r["grounding"], trust=r["trust"], guarantees=r["guarantees"],
        fault_coverage=r["fault_coverage"], empirical=emp,
        models={m.type: dict(component=m.component, contract=m.contract, function=m.function, phases=m.phases,
                             irreversible=m.irreversible, produces=fmt(m.produces), evidence=m.evidence,
                             must_not_assume=m.must_not_assume,
                             faults=[dict(name=f.name, signals=f.signals, at=f.at, corrupts=fmt(f.corrupts), monitor=f.monitor,
                                          coverage=f.coverage, persistence=f.persistence,
                                          removed_by=fmt(f.removed_by) if f.removed_by else None, record_recovery=f.record_recovery,
                                          twin=f.twin) for f in m.faults]) for m in r["models"].values()},
        meta=dict(order=r["meta"].order, rules=[dict(r_, when=[fmt(c) for c in r_["when"]]) for r_ in r["meta"].rules],
                  treatments=r["meta"].treatments),
        experiment_goal=[fmt(i["cond"]) for i in E.clauses["goal"]],
        handles=[dict(type=slot(h[1], "type")[1], text=fmt(h)) for h in E.handles],
        kernel=dict(sessions=sessions, ldl=dict((k, a_run[k]) for k in ("entries", "end", "clock_s", "realization", "validity")),
                    plan=dict((k, b_run[k]) for k in ("entries", "end", "clock_s", "realization", "validity")),
                    leaves=len(a_run["leaves"]), identical=same, planner_order=seq, planner_order_consistent=consistent))
    os.makedirs(OUT, exist_ok=True)
    json.dump(rep, open(os.path.join(OUT, "ldl_challenge_rescue.json"), "w"), indent=1, default=str)
    allneg = all(v["caught"] for v in neg.values())
    rep["ok"] = r["ok"]
    print(f"[ldl] {'PASS' if r['ok'] and allneg and same and consistent else 'FAIL'}: well-formed={r['ok']}, "
          f"negative controls {sum(v['caught'] for v in neg.values())}/{len(neg)}, kernel identical={same}")
    return 0 if r["ok"] and allneg and same and consistent else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
