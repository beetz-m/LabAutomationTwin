"""LDL v0.3: reasoning about the instruments' processes, the guarantees of repairs, the epistemic meta model and the
experiment's quality, for rsa/ldl.py.

User decisions of 2026-10-17 (docs/rsa/LAB-DESIGNATOR-LANGUAGE.md section 11):
  * the processes within the devices are modelled and reasoned about; they decide the trustworthiness of an
    experiment (registry/lab/processes.ldl, grounded in the read-only Cell 01 component records);
  * repairs must provide guarantees for the final effects: every failure handler states what it guarantees, and the
    claim is checked against the contracts and the process models, and against what the recorded runs did;
  * the meta model needs expressive power now (registry/lab/epistemic.ldl), its rules are refined later;
  * safety, reliability and auditability rank high among the KPIs, with costs attached.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

import yaml

from .ldl import (LAB, OUT, dslots, fmt, is_desig, is_var, parse, slot, slot_l, unq)

HERE = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------------------------------------- pattern matching
def pmatch(a, r) -> bool:
    """Does the description `a` entail the pattern `r`? Variables in either match anything (pattern level)."""
    if is_var(r) or is_var(a):
        return True
    if isinstance(r, str) or isinstance(a, str):
        return unq(a) == unq(r)
    if is_desig(r):
        if not (is_desig(a) and a[1] == r[1]):
            return False
        for rs in dslots(r):
            if rs[0] == "not":
                continue
            if not any(len(as_) >= len(rs) and all(pmatch(x, y) for x, y in zip(as_[1:], rs[1:]))
                       for as_ in dslots(a) if as_[0] == rs[0]):
                return False
        return True
    return isinstance(a, list) and len(a) == len(r) and all(pmatch(x, y) for x, y in zip(a, r))


# ------------------------------------------------------------------------------------------------- process models
class Fault:
    def __init__(self, d):
        g = lambda n: slot(d, n)  # noqa: E731
        self.name = g("name")[1]
        self.signals = g("signals")[1]
        self.at = g("at")[1]
        self.corrupts = g("corrupts")[1]
        det = g("detected-by")[1]
        self.monitor = None if det == "none" else (slot(det, "observation") or slot(det, "control"))
        self.monitor_kind = None if self.monitor is None else self.monitor[0]
        self.monitor = None if self.monitor is None else unq(self.monitor[1])
        self.coverage = (g("coverage") or [None, "none" if self.monitor is None else "full"])[1]
        self.persistence = g("persistence")[1]
        self.removed_by = (g("removed-by") or [None, None])[1]
        self.record_recovery = unq((g("record-recovery") or [None, '""'])[1])
        self.twin = unq((g("twin") or [None, '""'])[1])


class ProcessModel:
    def __init__(self, d):
        get = lambda n: slot_l(d, n)  # noqa: E731
        self.type = d[1]
        self.component = get("component")[1]
        self.contract = (get("contract") or [None, None])[1]
        self.function = slot(get("realised-by")[1], "function")[1]
        self.phases = get("phases")[1:]
        self.irreversible = get("irreversible-at")[1]
        self.produces = get("produces")[1]
        self.faults = [Fault(f) for f in get("faults")[1:]]
        self.evidence = [unq(x) for x in get("evidence")[1:]]
        self.must_not_assume = [unq(x) for x in get("must-not-assume")[1:]]

    def phase_index(self, p):
        return self.phases.index(p) if p in self.phases else None

    def after_irreversible(self, f: Fault) -> bool:
        if self.irreversible == "none":
            return False
        return self.phase_index(f.at) >= self.phase_index(self.irreversible)


def load_models(text) -> Dict[str, ProcessModel]:
    return {m[1]: ProcessModel(m) for m in parse(text) if m and m[0] == "process-model"}


def ground(models: Dict[str, ProcessModel]) -> List[Dict[str, Any]]:
    """Every name a process model uses must be in the device's Cell 01 component record (read-only)."""
    from .kb import C01_COMPONENTS
    out = []
    for m in models.values():
        rec = yaml.safe_load(open(os.path.join(C01_COMPONENTS, m.component + ".yaml")))
        faults = {f["fault"]: f for f in rec.get("failure_modes") or []}
        obs = {x["observation"] for x in rec.get("monitoring") or []}
        ctrls = set(rec.get("risk_controls") or [])
        con = next((c for c in rec.get("action_contracts") or [] if c["name"] == m.contract), None)
        mna = set((rec.get("epistemic_state") or {}).get("must_not_assume") or [])
        problems = []
        if m.contract and con is None:
            problems.append(f"no action contract {m.contract}")
        for f in m.faults:
            if f.name not in faults:
                problems.append(f"fault {f.name} not in the record's failure_modes")
            elif f.record_recovery and f.record_recovery != faults[f.name]["recovery"]:
                problems.append(f"fault {f.name}: recovery differs from the record")
            if f.monitor and f.monitor_kind == "observation" and f.monitor not in obs:
                problems.append(f"monitor '{f.monitor}' not in the record's monitoring")
            if f.monitor and f.monitor_kind == "control" and f.monitor not in ctrls:
                problems.append(f"control '{f.monitor}' not in the record's risk_controls")
        for e in m.evidence:
            if con is not None and e not in (con.get("evidence_outputs") or []):
                problems.append(f"evidence '{e}' not in {m.contract}.evidence_outputs")
        for a in m.must_not_assume:
            if a not in mna:
                problems.append(f"must-not-assume '{a}' not in the record")
        unmodelled = sorted(set(faults) - {f.name for f in m.faults})
        out.append(dict(process=m.type, component=m.component, contract=m.contract, faults=len(m.faults),
                        record_faults=len(faults), unmodelled=unmodelled, problems=problems, ok=not problems and not unmodelled))
    return out


# ------------------------------------------------------------------------------------------------- trust per step
def step_process(st) -> Optional[str]:
    d = st.get("instrument")
    return slot(slot(d, "process")[1], "type")[1] if d else None


def handlers(E) -> List[Dict[str, Any]]:
    out = []
    for h in E.handles:
        f = h[1]
        br = lambda n: [x[1] for x in h[2:] if isinstance(x, list) and x[0] == n]  # noqa: E731
        g = next((x[1:] for x in h[2:] if isinstance(x, list) and x[0] == "guarantees"), [])
        then = br("then")
        out.append(dict(type=slot(f, "type")[1], cause=(slot(f, "cause") or [None, None])[1], do=br("do"),
                        then=[t if isinstance(t, str) else t[0] for t in then], then_raw=[fmt(t) for t in then],
                        orelse=[fmt(x) for x in br("else")], claims=g, text=fmt(h)))
    return out


def handler_for(hs, typ, cause):
    exact = [h for h in hs if h["type"] == typ and h["cause"] == cause]
    return exact[0] if exact else next((h for h in hs if h["type"] == typ and h["cause"] is None), None)


def trust(E, models, hs) -> List[Dict[str, Any]]:
    rows = []
    for st in E.steps:
        pt = step_process(st)
        m = models.get(pt)
        if m is None:
            continue
        effects = [i["cond"] for i in st["goal"] + st["maintains"] + st["achieves"]]
        faults = []
        for f in m.faults:
            if not any(pmatch(e, f.corrupts) for e in effects):
                continue
            h = handler_for(hs, f.signals, f.name)
            faults.append(dict(fault=f.name, at=f.at, detected=f.coverage if f.monitor else "none", monitor=f.monitor,
                               timing="after the irreversible phase" if m.after_irreversible(f) else "before the irreversible phase"
                               if m.irreversible != "none" else "non-destructive process",
                               persistence=f.persistence, handled=bool(h), handler=h["text"] if h else None,
                               silent=f.coverage != "full", irreparable=m.after_irreversible(f)))
        rows.append(dict(step=st["var"], process=pt, component=m.component, faults=faults,
                         silent=[x["fault"] for x in faults if x["silent"]],
                         irreparable=[x["fault"] for x in faults if x["irreparable"]],
                         unhandled=[x["fault"] for x in faults if not x["handled"]],
                         must_not_assume=m.must_not_assume, evidence=m.evidence))
    return rows


# ------------------------------------------------------------------------------------------------- guarantees of repairs
def guarantees(E, models, hs) -> List[Dict[str, Any]]:
    from .ldl import ldl_contract_goal
    out = []
    plate_home = any(it["ann"].get(":establishable") and slot(it["cond"], "in") for it in E.clauses["achieves"])
    for h in hs:
        steps = [s for s in E.steps if h["type"] in s["signals"]] or ([] if h["type"] != "prevents-violated" else [None])
        procs = {step_process(s) for s in steps if s}
        faults = [f for p in procs if p in models for f in models[p].faults
                  if f.signals == h["type"] and (h["cause"] in (None, f.name))]
        res: Dict[str, Any] = dict(type=h["type"], cause=h["cause"], claims=h["claims"], text=h["text"], steps=[s["var"] for s in steps if s])
        checks = {}
        # goal: the failed step's goal is achieved after all
        if any(c in ("goal", "goal-or-safe-state") for c in h["claims"]):
            why, conds = [], ["no second fault occurs", "the excursion limit (600 s) is not reached; the window policy enforces it, else escalate"]
            if not any(t in ("retry", "replan") for t in h["then"]):
                why.append("no retry or replan follows the repair")
            if not faults:
                why.append(f"no modelled fault for {h['type']}" + (f"/{h['cause']}" if h["cause"] else ""))
            for f in faults:
                m = next(models[p] for p in procs if p in models and f in models[p].faults)
                if f.monitor is None:
                    why.append(f"{f.name} is not detected, so nothing triggers the repair")
                elif f.coverage == "partial":
                    conds.append(f"{f.name} is detected (coverage partial: '{f.monitor}')")
                if m.after_irreversible(f):
                    why.append(f"{f.name} occurs at {f.at}, at or after the irreversible phase {m.irreversible}; the goal cannot be re-achieved")
                if f.persistence == "persistent":
                    rem = [d for d in h["do"] if isinstance(d, list) and d[0] == "re-establish" and pmatch(d[1], f.removed_by)]
                    if not rem:
                        why.append(f"{f.name} is persistent and the handler does not re-establish {fmt(f.removed_by)}: a retry meets the same cause"
                                   + (f" ({f.twin})" if f.twin else ""))
                    else:
                        conds.append(f"re-establishing {fmt(rem[0][1])} removes {f.name} (process model)")
                else:
                    conds.append(f"{f.name} is transient; a repeat meets a fresh cause")
            checks["goal"] = dict(ok=not why, why=why, conditions=conds if not why else [])
        # safe state: plate back in its controlled environment, nothing committed, evidence retained
        if any(c in ("safe-state", "goal-or-safe-state") for c in h["claims"]):
            last = h["orelse"] if "goal-or-safe-state" in h["claims"] else h["then"]
            why = []
            if not any(x in ("escalate", "abstain") for x in last):
                why.append(f"the final branch ({last}) does not end in escalate or abstain")
            if not plate_home:
                why.append("the experiment does not make (the plate (in ?env)) establishable, so nothing restores it")
            recs = all(any(slot(i["cond"], "of") and i["cond"][1] == "record" for i in s["achieves"]) for s in steps if s)
            if not recs:
                why.append("a failing step's contract records no evidence")
            checks["safe-state"] = dict(ok=not why, why=why, conditions=[] if why else [
                "plate restored to its controlled environment (experiment achieves, :establishable; kernel unwind-protect F10)",
                "nothing committed (escalation; commit needs both columns, D009)",
                "evidence of the failed attempt retained (contract record; kernel logs failed leaves, F4)"])
        # containment: a quarantining action whose contract guarantees containment
        if "contained" in h["claims"]:
            q = [d for d in h["do"] if is_desig(d) and slot(d, "type") and slot(d, "type")[1] == "quarantining"]
            g = ldl_contract_goal(E, "quarantining")
            ok = bool(q) and g is not None and slot(g, "contained") is not None
            checks["contained"] = dict(ok=ok, why=[] if ok else ["no quarantining action with a containment goal"],
                                       conditions=["quarantining achieves (the plate ?x (contained true)); H4 fills its instrument role"] if ok else [])
        res["checks"] = checks
        res["ok"] = bool(checks) and all(c["ok"] for c in checks.values())
        out.append(res)
    return out


def fault_coverage(E, models, hs) -> List[Dict[str, Any]]:
    """Every fault a step's process can have must reach a handler (its own or one for its failure type)."""
    out = []
    for st in E.steps:
        m = models.get(step_process(st))
        for f in (m.faults if m else []):
            h = handler_for(hs, f.signals, f.name)
            out.append(dict(step=st["var"], fault=f.name, signals=f.signals, handled=bool(h)))
    return out


# ------------------------------------------------------------------------------------------------- guarantees vs runs
KERNEL_FAILURE = {"calibration_invalid": ("measurement-invalid", "calibration_expired"),
                  "focus_invalid": ("measurement-invalid", "out_of_focus"),
                  "tip_missing": ("dose-not-delivered", "tip_missing_or_dropped"),
                  "identity_mismatch": ("identity-mismatch", None),
                  "window_exceeded": ("prevents-violated", None)}
#: what a prescribed repair is called in the kernel's repair records (rsa/library.py recover methods)
PRESCRIBED = {"calibration current": "calibrate", "seated true": "reseat", "quarantining": "quarantine",
              "restore": "store", "identity verified": "verify_reagent"}


def empirical(hs, runs) -> List[Dict[str, Any]]:
    out = []
    for name in runs:
        path = os.path.join(OUT, f"trail_{name}.json")
        if not os.path.exists(path):
            continue
        E_ = json.load(open(path))["entries"]
        end = next((e["transition"] for e in reversed(E_) if e["category"] == "experiment"), None)
        for i, e in enumerate(E_):
            if e["transition"] != "repairing":
                continue
            code = e["repair"]["failure"]
            typ, cause = KERNEL_FAILURE.get(code, (code, None))
            h = handler_for(hs, typ, cause)
            node = e["designator"]
            later = E_[i + 1:]
            goal = any(x["designator"] == node and x["transition"] in ("executed", "repaired") for x in later)
            restored = any(x["category"] in ("store", "quarantine", "contain") and x["transition"] == "executed" for x in later)
            outcome = "goal achieved after the repair" if goal else (
                "safe state: escalated, plate restored or contained" if end == "escalated" and restored else
                "escalated" if end == "escalated" else "other")
            claim = h["claims"] if h else None
            held = (goal and claim and any(c.startswith("goal") for c in claim)) or (
                not goal and claim and any("safe-state" in c for c in claim) and restored)
            done = e["repair"].get("repair_categories") or []
            prescribed = [fmt(d) for d in (h["do"] if h else [])]
            as_prescribed = all(any(k in " ".join(prescribed) and v in done for k, v in PRESCRIBED.items() if k in p_)
                                for p_ in prescribed) if prescribed else True
            out.append(dict(run=name, failure=code, at=e["category"], handler=(f"{typ}/{cause}" if cause else typ) if h else None,
                            claims=claim, repair=done, prescribed=prescribed, as_prescribed=as_prescribed,
                            outcome=outcome, held=bool(held)))
    return out


# ------------------------------------------------------------------------------------------------- epistemic meta model
class Meta:
    def __init__(self, text):
        root = next(x for x in parse(text) if x and x[0] == "meta-model")
        self.order = slot_l(root, "order")[1][1:]
        self.rules = [dict(name=r[1], when=slot_l(r, "when")[1:], treat=slot_l(r, "treat")[1],
                           because=unq(slot_l(r, "because")[1])) for r in root[2:] if r[0] == "rule"]
        self.treatments = {t[1]: dict(text=fmt(t), do=[fmt(x[1]) for x in t[2:] if x[0] == "do"],
                                      then=[fmt(x[1]) for x in t[2:] if x[0] == "then"],
                                      orelse=[fmt(x[1]) for x in t[2:] if x[0] == "else"],
                                      cost=[fmt(x[1:]) for x in t[2:] if x[0] == "cost"],
                                      kernel=unq((slot_l(t, "kernel") or [None, '""'])[1]))
                           for t in root[2:] if t[0] == "treatment"}

    def _src_ok(self, have, want):
        if isinstance(want, list):                     # (<= assumed): at most as strong as `assumed`
            op, lvl = want[0], want[1]
            a, b = self.order.index(have), self.order.index(lvl)
            return a >= b if op == "<=" else a > b if op == "<" else a <= b if op == ">=" else a < b
        return have == want

    def match(self, rule, item, grade, consequential, context, provenance=None) -> bool:
        for c in rule["when"]:
            if c[0] in ("a", "an") and c[1] == "belief":
                of = slot(c, "of")
                if of and not pmatch(item, of[1]):
                    return False
                g = slot(c, "grade")
                if g:
                    for dim in g[1:]:
                        k, v = dim[0], dim[1]
                        if k == "source" and not self._src_ok(grade["source"], v):
                            return False
                        if k in ("freshness", "corroboration") and grade.get(k) != v:
                            return False
                fr = slot(c, "from")
                if fr and not (provenance and pmatch(provenance, fr[1])):
                    return False
            elif c[0] == "use":
                if (c[1] == "consequential") != consequential:
                    return False
            elif c[0] == "in":
                if not (context and slot(c[1], "type") and slot(c[1], "type")[1] == context):
                    return False
        return True

    def treat(self, item, grade, consequential, context, provenance=None):
        r = next((r for r in self.rules if self.match(r, item, grade, consequential, context, provenance)), None)
        return (r["treat"], r["name"]) if r else ("UNTREATED", None)


SHORTFALLS = {"stale": dict(source="observed", freshness="stale", corroboration="single"),
              "contradicted": dict(source="observed", freshness="fresh", corroboration="contradicted"),
              "reported": dict(source="reported", freshness="fresh", corroboration="single"),
              "inferred": dict(source="inferred", freshness="fresh", corroboration="single"),
              "assumed": dict(source="assumed", freshness="fresh", corroboration="single"),
              "predicted": dict(source="predicted", freshness="fresh", corroboration="single"),
              "unknown": dict(source="unknown", freshness="fresh", corroboration="single")}


def epistemic(E, meta: Meta) -> List[Dict[str, Any]]:
    rows, seen = [], set()
    for s in E.steps + [dict(var=E.var, type="experimenting", requires=E.clauses["requires"], maintains=E.clauses["maintains"])]:
        for it in s.get("requires", []) + s.get("maintains", []):
            if not it.get("known"):
                continue
            req, cons, ctx = it["grade"], bool(it["ann"].get(":consequential")), s.get("type")
            key = (re.sub(r"\?[\w.]+", "?", fmt(it["cond"])), req["source"], cons, ctx)
            if key in seen:
                continue
            seen.add(key)
            treat = {}
            for label, g in SHORTFALLS.items():
                short = (meta.order.index(g["source"]) > meta.order.index(req["source"]) or g["freshness"] == "stale"
                         or g["corroboration"] == "contradicted")
                if short:
                    t, rule = meta.treat(it["cond"], g, cons, ctx)
                    treat[label] = dict(treat=t, rule=rule)
            rows.append(dict(item=fmt(it["cond"]), context=ctx, needs=req, consequential=cons, treatments=treat,
                             ok=all(v["treat"] != "UNTREATED" for v in treat.values()), where=s["var"]))
    return rows


# ------------------------------------------------------------------------------------------------- KPIs
KPI_RUNS = ["nominal", "calibration_lapsed", "tip_lost", "tool_changer_slow", "identity_swap", "isaac_nominal",
            "isaac_calibration_lapsed"]


def kpi_values(name, kb, weights, n_goals) -> Optional[Dict[str, Any]]:
    from .audit import verify
    from .cq import T, q_time_outside
    path = os.path.join(OUT, f"trail_{name}.json")
    if not os.path.exists(path):
        return None
    td = json.load(open(path))
    t = T(td)
    exc, _ = q_time_outside(dict(T=t, kb=kb), {})
    exc = {k: v for k, v in exc.items() if re.fullmatch(r"s\d+", str(k))}
    ev = lambda e, k: next((x["value"] for x in e.get("evidence") or [] if x["kind"] == k), None)  # noqa: E731
    dev = [abs(ev(e, "volume_delivered_uL") - ev(e, "volume_commanded_uL")) / ev(e, "volume_commanded_uL") * 100
           for e in t.all(category="dispense", transition="executed")
           if ev(e, "volume_delivered_uL") is not None and ev(e, "volume_commanded_uL")]
    doses, imgs = t.all(category="dispense", transition="executed"), t.all(category="image_well", transition="executed")
    end = next((e["transition"] for e in reversed(t.E) if e["category"] == "experiment"), None)
    # goals: interventions and measurements of the design; first attempt = no failure or repair below it
    goals = [e for e in t.E if e["category"] in ("intervene", "measure") and e["transition"] == "executed"]
    def clean(uid):
        return not any(x["transition"] in ("failed", "repairing") and uid in t.chain(x["designator"]) for x in t.E)
    first = [g for g in goals if clean(g["designator"])]
    evidenced = [g for g in goals if any(x.get("evidence") and all(v.get("sha256") for v in x["evidence"])
                                         and g["designator"] in t.chain(x["designator"]) and x["category"] in ("dispense", "image_well")
                                         for x in t.E)]
    v = verify(td)
    cmd_s = sum(e.get("duration_s") or 0 for e in t.E if e.get("kind") == "command" and e["transition"] == "executed"
                and e["category"] != "incubate")        # instrument time of the operations; culture waits are the design's
    tips = len(t.all(category="tip_pick", transition="executed"))
    esc = 1 if end == "escalated" else 0
    cost = tips * weights.get("consumable", 0) + cmd_s / 60 * weights.get("instrument-minute", 0) + esc * weights.get("escalation", 0)
    violated = {t.session_of(e["designator"]) for e in t.all(transition="policy_violation")}
    violated |= {k for k, x in exc.items() if x > kb.window_s()[0]}
    safety = len(violated)                              # sessions in which a prevents-item was violated
    return dict(run=name, end=end, sessions=exc,
                **{"safety": safety,
                   "reliability": round(len(first) / n_goals, 3),
                   "auditability": round(len(evidenced) / len(goals), 3) if goals and v["ok"] and v["attributable"] and v["evidence_hashed"] else 0.0,
                   "excursion-time": max(exc.values()) if exc else None,
                   "cost": round(cost, 2),
                   "dose-deviation": round(max(dev), 3) if dev else None,
                   "time-to-result": round((imgs[-1]["t_sim"] - doses[0]["t_sim"]) / 3600, 3) if doses and imgs else None},
                cost_parts=dict(consumables=tips, instrument_minutes=round(cmd_s / 60, 2), escalations=esc))


def kpi_table(E) -> Dict[str, Any]:
    kpis, prefers, weights = [], [], {}
    for q in E.quality:
        if q[0] == "prefers":
            prefers = q[1][1:]
            continue
        tgt = slot(q, "target")[1]
        w = slot(q, "weights")
        if w:
            weights = {x[0]: float(x[1]) for x in w[1:]}
        kpis.append(dict(name=slot(q, "name")[1], of=fmt(slot(q, "of")[1]), aggregate=slot(q, "aggregate")[1],
                         unit=(slot(q, "unit") or [None, ""])[1], op=tgt[0], target=float(tgt[1]),
                         direction=slot(q, "direction")[1], weights=fmt(w) if w else None))
    n_goals = sum(1 for s in E.steps if s["type"] in ("intervening", "measuring"))
    runs = [r for r in (kpi_values(n, E.world.kb, weights, n_goals) for n in KPI_RUNS) if r]
    for r in runs:
        r["met"] = {k["name"]: (None if r[k["name"]] is None else
                                (r[k["name"]] <= k["target"] if k["op"] == "<=" else r[k["name"]] >= k["target"]))
                    for k in kpis}
    sign = {k["name"]: (1 if k["direction"] == "minimize" else -1) for k in kpis}
    rank = sorted(runs, key=lambda r: tuple((sign[k] * r[k]) if r[k] is not None else float("inf") for k in prefers))
    return dict(kpis=kpis, prefers=prefers, weights=weights, goals=n_goals, runs=runs, ranking=[r["run"] for r in rank])
