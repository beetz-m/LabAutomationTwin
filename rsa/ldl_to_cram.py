"""Generate the structured reactive controller (CRAM/RPL, Lisp notation) for an LDL experiment.

The controller is generated from the checked LDL experiment (rsa/ldl.py), so the partial order, the policies, the
failure handling and the guarantees are the ones the checker verified; nothing is written by hand. It follows the CRAM
structure: an action designator is performed by the plan of its action type, so

  1. the experiment plan is only the partial order of action designators (the order derived from causal links);
  2. each action type has one action plan that carries its contract's reactive envelope (requires as ensure /
     achieve / wait-for, prevents and maintains as policies, step-level repairs, the goal check), and performs the
     action by tending its instrument (insert the plate into the instrument's slot, start the process, remove it);
  3. the top-level controller binds the entity designators and the process modules, runs the experiment's own
     policies, the experiment-level repairs and the safe state around the experiment plan.

Mapping of LDL to RPL/CRAM:
  condition (ground query)    (holds <description>): a fluent pulsed by the belief state (EQ6)
  requires known / believed   (ensure ... :grade ... :consequential ...)   shortfalls are treated by the meta model
  requires establishable      (achieve ...)                                 RPL ACHIEVE
  requires by a causal link   (wait-for (holds ...))                        supplied by a predecessor in the order
  prevents / maintains        WHENEVER monitors under WITH-POLICY: non-terminating, they evaporate with what they constrain
  scope                       (scope (begin end) ...): WAIT-FOR begin, then PURSUE until end
  handler retry / replan      WITH-FAILURE-HANDLING + WITH-RETRY-COUNTERS / DO-RETRY / RETRY in the action plan
  handler escalate            WITH-FAILURE-HANDLING in the top-level controller; the failure propagates after the repair
  safe state                  UNWIND-PROTECT that achieves (the plate ?p (in ?env))

Notation: RPL control structures (McDermott; Beetz, Concurrent Reactive Plans) in CRAM Lisp syntax. Not executed: no
Lisp CRAM is installed in this environment. Output is pretty-printed by rsa/sexp_pretty.py.

    env_cad/bin/python -m rsa.ldl_to_cram       # rsa/out/challenge_rescue_src.lisp (+ sections as JSON for the page)
"""

from __future__ import annotations

import json
import os
import re
import sys

from .ldl import LAB, OUT, World, check, fmt, items, parse, slot, slot_l
from .sexp_pretty import pretty

GOAL_FAILURE = {"intervening": "dose-not-delivered", "measuring": "measurement-invalid",
                "incubating": "environment-excursion", "quarantining": "containment-breach"}


def failure_for(cond: str, typ: str) -> str:
    if "contamination" in cond:
        return "contamination-suspected"
    if typ == "incubating":
        return "environment-excursion"
    if typ == "quarantining":
        return "containment-breach"
    return "prevents-violated"


def grade(g):
    return "(" + " ".join(f"{k} {v}" for k, v in sorted(g.items())) + ")"


def macros() -> str:
    return """;;; LDL clauses as RPL. These macros are the only vocabulary the plans below add to RPL/CRAM.

(defmacro holds (description)
  "A ground entity description as a fluent: true while the belief state answers the query (EQ6).
The belief state is updated by the process modules' monitors and the sensors."
  `(belief-fluent ',description))

(defmacro prevent (fluent failure)
  "LDL prevents: a monitor that never finishes by itself and evaporates with the control structure
it constrains (RPL WITH-POLICY)."
  `(whenever ,fluent (fail ',failure :description ',fluent)))

(defmacro maintain (fluent failure)
  "LDL maintains: the same monitor on the negated condition."
  `(whenever (fl-not ,fluent) (fail ',failure :description '(not ,fluent))))

(defmacro scope ((begin end) &body monitors)
  "LDL scope: the monitors run from the moment BEGIN holds until END holds."
  `(seq (wait-for ,begin) (pursue (wait-for ,end) (par ,@monitors))))

(defmacro ensure (belief &key grade consequential)
  "A requires-item the realization verifies; a shortfall below GRADE is treated by the epistemic
meta model (re-observe, verify, contain-and-escalate, ...)."
  `(treat-shortfall ',belief ',grade ,consequential *epistemic-meta-model*))

(defmacro check-goal (description failure)
  "The goal of an action: checked after the action; if it does not hold, the action fails."
  `(unless (fluent-value (holds ,description)) (fail ',failure :description ',description)))

(defmacro def-action-plan (type (&rest roles) &body body)
  "The plan that PERFORM uses for action designators of TYPE. ROLES are (slot ?variable) pairs
bound from the designator's slots when it is performed."
  `(register-action-plan ',type ',roles (lambda (?self ,@(mapcar #'second roles)) ,@body)))
"""


def failures_section(r) -> str:
    out = [";;; Failures: what an action can signal, and the device faults behind each (process models)", "",
           "(define-condition lab-failure (plan-failure)",
           "  ((designator :initarg :description :reader failure-designator)",
           "   (cause :initarg :cause :initform nil :reader failure-cause))",
           "  (:documentation \"A failure designator, e.g. (a failure (type measurement-invalid) (cause out_of_focus)).\"))", ""]
    for t in sorted({f["failure"] for f in r["failures"]}):
        fs = [(m.component.split("_")[0], f.name) for m in r["models"].values() for f in m.faults if f.signals == t]
        doc = f"  (:documentation \"{fs[0][0]} faults: {', '.join(n for _, n in fs)}\")" if fs else None
        out.append(f"(define-condition {t} (lab-failure) ()" + (f"\n{doc})" if doc else ")"))
    return "\n".join(out) + "\n"


def data_section(E, r) -> str:
    out = [";;; Quality (for the critic over the audit trail) and the epistemic meta model (for ENSURE)", "",
           "(defparameter *quality*", "  ;; targets and weights ILLUSTRATIVE; to be set with the lab later",
           "  '(" + "\n    ".join(fmt(q) for q in E.quality) + "))", "",
           "(defparameter *epistemic-meta-model*", "  ;; registry/lab/epistemic.ldl; the first matching rule applies",
           "  '(" + "\n    ".join(f"(rule {x['name']} (when {' '.join(fmt(c) for c in x['when'])}) (treat {x['treat']}))"
                              for x in r["meta"].rules) + "))"]
    return "\n".join(out) + "\n"


def action_plan(typ: str, contract: list, hs, guar, used_by) -> str:
    """The plan for one action type, from its LDL contract (not instantiated) and the experiment's retry handlers."""
    get = lambda n: slot_l(contract, n)  # noqa: E731
    roles = get("roles")[1:]
    params, bind = [], []
    for role in roles:
        pat = role[1]
        if isinstance(pat, list) and pat and pat[0] in ("a", "an", "the") and len(pat) > 2:
            params.append(f"({role[0]} {pat[2]})")
            of = slot(pat, "of")
            if of:
                bind.append(f"({of[1]} (plate-of {pat[2]}))")
        elif isinstance(pat, list):            # (at (culture-time ?t))
            params.append(f"({role[0]} {pat[1]})")
        else:
            params.append(f"({role[0]} {pat})")
    inst = get("instrument")
    goal = items(get("goal") or ["goal"])
    goal_txt = fmt(goal[0]["cond"]) if goal else None
    lines = [f"(def-action-plan {typ} ({' '.join(params)})",
             f"  \"Goal: {goal_txt}." + (f" Performed in: {', '.join(used_by)}." if used_by else "") + "\""]
    if inst:
        d = inst[1]
        bind.append(f"(?instrument {fmt([x for k, x in enumerate(d) if k != 2])})")
    body = []
    for it in items(get("requires") or ["requires"]):
        c = fmt(it["cond"])
        if it["ann"].get(":establishable"):
            body.append(f"(achieve {c})")
        elif it["known"]:
            body.append(f"(ensure {c} :grade {grade(it['grade'])} :consequential {'t' if it['ann'].get(':consequential') else 'nil'})")
        else:
            body.append(f"\n;; supplied by a predecessor in the partial order\n(wait-for (holds {c}))")
    pols = [f"(prevent (holds {fmt(it['cond'])}) {failure_for(fmt(it['cond']), typ)})" for it in items(get("prevents") or ["p"])]
    for sc in (e for e in contract if e[0] == "scope"):
        b, e_ = slot_l(sc, "begins-when")[1], slot_l(sc, "ends-when")[1]
        inner = " ".join(f"(prevent (holds {fmt(it['cond'])}) {failure_for(fmt(it['cond']), typ)})"
                         for x in sc[1:] if x[0] == "prevents" for it in items(x))
        pols.append(f"(scope ((holds {fmt(b)}) (holds {fmt(e_)})) {inner})")
    pols += [f"(maintain (holds {fmt(it['cond'])}) {failure_for(fmt(it['cond']), typ)})" for it in items(get("maintains") or ["m"])]
    obj = "?x" if typ == "quarantining" else "?p"
    act = f"(perform (an action (type tending) (instrument ?instrument) (object {obj})))"
    body.append(f"(with-policy (par {' '.join(pols)})\n  {act})" if pols else act)
    if goal_txt:
        body.append(f"(check-goal {goal_txt} {GOAL_FAILURE.get(typ, 'prevents-violated')})")
    core = "(seq " + " ".join(body) + ")"
    # step-level repairs: the experiment's handlers that retry or replan, for failures this action signals
    signals = [slot(f, "type")[1] for f in (get("signals") or ["s"])[1:]]
    rh = [h for h in hs if h["type"] in signals and any(t in ("retry", "replan") for t in h["then"])]
    if rh:
        counters, cl = [], {}
        for h in rh:
            cnt = f"{h['cause'].replace('_', '-')}-repairs"
            counters.append(f"({cnt} 1)")
            ach = " ".join(f"(achieve {fmt(d[1])})" for d in h["do"] if isinstance(d, list) and d[0] == "re-establish")
            g = guar.get((h["type"], h["cause"]))
            how = "re-resolve and perform again" if "replan" in h["then"] else "perform again"
            cl.setdefault(h["type"], []).append(
                f"\n;; {how}; guarantees {', '.join(h['claims'])}: {'holds' if g and g['ok'] else 'NOT VERIFIED'}\n"
                f"({h['cause']} (do-retry {cnt} {ach + ' ' if ach else ''}(retry)))")
        clauses = " ".join(f"({t} (f) (case (failure-cause f) {' '.join(cs)}))" for t, cs in cl.items())
        core = f"(with-retry-counters ({' '.join(counters)}) (with-failure-handling ({clauses}) {core}))"
    lines.append(f"  (let* ((?self (current-action-designator)) {' '.join(bind)})")
    lines.append("    " + core + "))")
    return "\n".join(lines) + "\n"


def experiment_plan(E, r) -> str:
    pos = {st["var"]: i for i, st in enumerate(E.steps)}
    params = " ".join(v for v in E.decls if v != "?D")
    out = [f"(def-cram-function challenge-rescue-plan ({params})",
           "  \"The lab plan: 8 action designators. The order is derived from causal links (rsa/ldl.py);",
           "steps without an order between them may run in any order or concurrently.\"",
           "  (partial-order", "      ("]
    for st in E.steps:
        slots = " ".join(f"({k} {val})" for k, val in st["slots"].items() if k != "requires")
        when = (f"{st['slots']['from'][1:-1].replace('culture-time ', '')} -> {st['slots']['to'][1:-1].replace('culture-time ', '')}"
                if st["type"] == "incubating" else f"culture-time {int(st['time_h'])} h")
        out.append(f"       (:tag {st['var'][1:]}  ; {st['type']}, {when}\n        (perform (an action (type {st['type']}) {slots})))")
    out[-1] += ")"
    for a, b in sorted(r["hasse"], key=lambda e: (pos[e[0]], pos[e[1]])):
        conds = sorted({l["cond"] for l in r["links"] if l["frm"] == a and l["to"] == b})
        out.append(f"    (:order {a[1:]} {b[1:]})  ; {'; '.join(conds)}")
    out[-1] = out[-1].replace(")  ;", ")))  ;", 1)
    return "\n".join(out) + "\n"


def top_level(E, r, world, hs, guar) -> str:
    ins = sorted({f"{i['process']} -> {', '.join(a['device'].upper() for a in i['answers'])}" for i in r["instruments"] if i})
    goal = " ".join(fmt(i["cond"]) for i in E.clauses["goal"])
    lets = " ".join(f"({v} {fmt([x for k, x in enumerate(d) if k != 2])})" for v, d in E.decls.items())
    clauses = []
    for typ in sorted({f["failure"] for f in r["failures"]}):
        spec = [h for h in hs if h["type"] == typ and not any(t in ("retry", "replan") for t in h["then"])]

        def body(h):
            b = [f"(perform {fmt(d)})" if isinstance(d, list) and d[0] in ("a", "an") else f"({fmt(d)[1:-1]})" for d in h["do"]]
            return " ".join(b + ["(escalate f)"])

        def note(h):
            g = guar.get((h["type"], h["cause"]))
            return f"\n;; guarantees {', '.join(h['claims'])}: {'holds' if g and g['ok'] else 'NOT VERIFIED'}\n"
        if not spec:
            clauses.append(f"({typ} (f)\n;; after the action plan's repairs ran out\n(escalate f))")
        elif len(spec) == 1 and spec[0]["cause"] is None:
            clauses.append(f"({typ} (f) {note(spec[0])} {body(spec[0])})")
        else:
            cs = " ".join(f"{note(h)}({h['cause']} {body(h)})" for h in spec if h["cause"])
            clauses.append(f"({typ} (f) (case (failure-cause f) {cs}\n;; otherwise, and after the action plan's repairs ran out\n(t (escalate f))))")
    pols = [f"(prevent (holds {fmt(it['cond'])}) {failure_for(fmt(it['cond']), 'experimenting')})" for it in E.clauses["prevents"]]
    pols += [f"(maintain (holds {fmt(it['cond'])}) {'identity-mismatch' if 'identity' in fmt(it['cond']) else 'prevents-violated'})"
             for it in E.clauses["maintains"]]
    reqs = []
    for it in E.clauses["requires"]:
        c = fmt(it["cond"])
        reqs.append(f"(ensure {c} :grade {grade(it['grade'])} :consequential t)" if it["known"] else f"(ensure-design {c})")
    home = next(fmt(i["cond"]) for i in E.clauses["achieves"] if i["ann"].get(":establishable"))
    args = " ".join(v for v in E.decls if v != "?D")
    return f"""(def-top-level-cram-function challenge-rescue ()
  "Goal: {goal}. Design c_d85_t48_n1, EIG {world.plan['selected']['eig_bits']} bit."
  ;; the process modules fill the instrument roles;
  ;; rsa/ldl.py resolves them to {'; '.join(ins)}
  (with-process-modules-running (resolve-process-modules)
    (let* ({lets})
      ;; experiment-level repairs: they end in escalation, the failure then propagates
      (with-failure-handling ({' '.join(clauses)})
        (unwind-protect
            (seq {' '.join(reqs)}
                 (with-policy (par {' '.join(pols)})
                   (challenge-rescue-plan {args})))
          ;; the safe state on any exit: the plate back in its controlled environment
          (achieve {home}))))))
"""


def generate():
    world = World("g050")
    text = open(os.path.join(LAB, "challenge_rescue.ldl")).read()
    contracts_text = open(os.path.join(LAB, "contracts.ldl")).read()
    r = check(text, contracts_text, world)
    assert r["ok"], "the LDL experiment must pass rsa/ldl.py before a controller is generated"
    E = r["E"]
    hs = r["handlers_"]
    guar = {(g["type"], g["cause"]): g for g in r["guarantees"]}
    contracts = {c[1]: c[2:] for c in parse(contracts_text)}
    used = {}
    for st in E.steps:
        used.setdefault(st["type"], []).append(st["var"][1:])
    header = f""";;; -*- Mode: Lisp -*-
;;; Challenge-rescue experiment (design c_d85_t48_n1, required gain 0.5 bit): the structured reactive controller.
;;; Generated by rsa/ldl_to_cram.py from rsa/registry/lab/challenge_rescue.ldl (LDL v0.3), after rsa/ldl.py checked it:
;;; {len(E.steps)} action designators, {len(r['links'])} causal links, {len(r['hasse'])} order constraints,
;;; {sum(t['resolved'] for t in r['threats'])}/{len(r['threats'])} threats resolved, {sum(g['ok'] for g in r['guarantees'])}/{len(r['guarantees'])} repair guarantees hold.
;;; Notation: RPL control structures in CRAM Lisp syntax. No device, robot, pose or volume appears: they come
;;; from resolving the instrument roles at run time. Not executed: no Lisp CRAM here. ILLUSTRATIVE values (D016).

(in-package :lab-src)
"""
    sections = dict(
        header=header,
        macros=macros(),
        failures=failures_section(r),
        data=data_section(E, r),
        action_plans="\n".join(action_plan(t, contracts[t], hs, guar, used.get(t, [])) for t in
                               ("intervening", "incubating", "measuring", "quarantining")),
        experiment_plan=experiment_plan(E, r),
        top_level=top_level(E, r, world, hs, guar))
    pp = {k: (v if k in ("header", "macros") else pretty(v, "lisp")) for k, v in sections.items()}
    pp["description"] = pretty(text, "ldl")
    return pp, r


ORDER = ("header", "macros", "failures", "data", "action_plans", "experiment_plan", "top_level")


def main(argv):
    pp, r = generate()
    os.makedirs(OUT, exist_ok=True)
    lisp = "\n".join(pp[k].rstrip() + "\n" for k in ORDER)
    path = os.path.join(OUT, "challenge_rescue_src.lisp")
    open(path, "w").write(lisp)
    open(os.path.join(OUT, "challenge_rescue.pretty.ldl"), "w").write(pp["description"])
    json.dump(pp, open(os.path.join(OUT, "challenge_rescue_src_sections.json"), "w"), indent=1)
    code = re.sub(r";[^\n]*", "", re.sub(r'"(?:[^"\\]|\\.)*"', '""', lisp))
    depth, ok = 0, True
    for ch in code:
        depth += ch == "("
        depth -= ch == ")"
        ok &= depth >= 0
    orders = re.findall(r"\(:order (\w+) (\w+)\)", lisp)
    hasse = [(a[1:], b[1:]) for a, b in r["hasse"]]
    devs = [d for d in ("l10", "l12", "l17", "l21", "h4", "r01", "r02") if re.search(rf"\b{d}\b", code.lower())]
    long_ = [l for l in lisp.split("\n") if len(l) > 110 and not l.lstrip().startswith(";")]
    print(f"[ldl->cram] wrote {path}: {lisp.count(chr(10))} lines; parentheses balanced {ok and depth == 0}; "
          f"{len(orders)} :order constraints = derived Hasse edges {sorted(orders) == sorted(hasse)}; "
          f"device or robot names in code {devs or 'none'}; code lines over 110 chars {len(long_)}")
    return 0 if ok and depth == 0 and sorted(orders) == sorted(hasse) and not devs else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
