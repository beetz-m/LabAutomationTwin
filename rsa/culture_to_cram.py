"""Generate the top-level CRAM/RPL plan for the culture-level description of the experiment.

The culture plan (registry/lab/culture_plan.ldl) names only cultures, substances, observations and a belief. This
generator turns it into the top of the controller hierarchy:

  1. the top-level controller binds the culture, substance and belief designators, verifies the given state and the
     design's guarantee, runs the culture plan under the plan's own policies (the control stays untreated, no
     contamination, standard environment) and leaves the cultures in their environment on any exit;
  2. the culture plan is the partial order of the 12 culture action designators; the order is the one rsa/culture_plan.py
     derives from causal links over physical and knowledge effects (nothing is written by hand);
  3. each culture action type has one action plan. It waits for the requires-items its predecessors supply, performs
     the refinement (a lab action designator, or a computation for interpreting and analysing), then adds the action's
     physical effects to the belief state as projected and its knowledge effects as known;
  4. the lab action designators are performed by the lab action plans of rsa/out/challenge_rescue_src.lisp, which
     carry the instruments, policies and repairs. Neither level names a device, robot or pose.

The refinement templates are checked: instantiated with the vessels the mapping chose, each must give exactly the lab
designator rsa/culture_plan.py mapped the culture step to.

Notation: RPL control structures in CRAM Lisp syntax; not executed (no Lisp CRAM in this environment). ILLUSTRATIVE
values (D016).

    env_cad/bin/python -m rsa.culture_to_cram      # rsa/out/culture_plan_src.lisp
"""

from __future__ import annotations

import json
import os
import re
import sys

from .culture_plan import EFFECTS, derive, load_plan, mapping
from .ldl import LAB, OUT, World, check, dslots, dvar, fmt, parse, slot
from .sexp_pretty import pretty


# ------------------------------------------------------------------------------------------------- refinement
class Symbolic:
    """Resolve vessels as run-time functions (for the generated plan)."""
    vessel = staticmethod(lambda c: f"(vessel {c})")
    plate = staticmethod(lambda cs: f"(plate-of {cs})")
    env = staticmethod(lambda cs: f"(environment-of {cs})")


class Resolved:
    """Resolve vessels with the mapping's choice (for checking the templates against the lab plan)."""
    def __init__(self, vessels):
        self.v = vessels

    def vessel(self, c):
        return self.v[c]["lab_var"]

    plate = staticmethod(lambda cs: "?p")
    env = staticmethod(lambda cs: "?env")


def _intervening(P, R):
    return (f"(an action (type intervening) (into {R.vessel(P['culture'])}) (substance {P['substance']}) "
            f"(dose {P['dose']}) (at {P['at']}))")


REFINE = {  # culture action type -> (what performs it, template over the designator's slots)
    "challenging": ("lab", _intervening),
    "rescuing": ("lab", _intervening),
    "growing": ("lab", lambda P, R: f"(an action (type incubating) (plate {R.plate(P['cultures'])}) "
                                    f"(in {R.env(P['cultures'])}) (from {P['from']}) (to {P['to']}))"),
    "observing": ("lab", lambda P, R: f"(an action (type measuring) (of {R.vessel(P['culture'])}) "
                                      f"(readout organoid-radius) (at {P['at']}))"),
    "interpreting": ("computation", lambda P, R: f"(a computation (type image-analysis) (image {P['image']}) "
                                                 f"(into {P['into']}))"),
    "analysing": ("computation", lambda P, R: f"(a computation (type model-posterior) (belief {P['belief']}) "
                                              f"(statistic {P['statistic']}))"),
}
DOC = {
    "challenging": "Expose a culture to the challenge. Refined into one lab intervening action (a substance transfer).",
    "rescuing": "Expose a challenged culture to the rescue. Refined into one lab intervening action.",
    "growing": "Let the cultures grow over a culture-time interval. Refined into one lab incubating action of their plate.",
    "observing": "Image a culture. Refined into one lab measuring action; its readout carries the raw image.",
    "interpreting": "Turn an image into an organoid-radius estimate. A computation of the culture SDT; no lab action.",
    "analysing": "Update the belief over the recovery models from the radius difference. A computation; no lab action.",
}
FAILURE = {"exposure": "control-exposed", "contamination": "contamination-suspected", "environment": "environment-excursion"}


def failure_for(cond):
    return next((f for k, f in FAILURE.items() if k in cond), "prevents-violated")


def strip_lab(text):
    """A lab step's designator without its variable and requires slot, as the refinement template writes it."""
    d = parse(text)[0]
    return fmt(d[:2] + [x for x in dslots(d) if x[0] != "requires"])


# ------------------------------------------------------------------------------------------------- sections
def macros():
    return """;;; The culture level adds this vocabulary to RPL/CRAM and to the lab level (package :lab-src):
;;; HOLDS, PREVENT, MAINTAIN, ENSURE, DEF-ACTION-PLAN and the lab action plans come from there.

(defmacro with-culture-contract ((self) &body refinement)
  "The clauses a culture action designator carries: wait for each requires-item a causal link
supplies, achieve the :establishable ones, perform the REFINEMENT, then add the PHYSICAL effects
to the belief state as projected (graded by the culture model until an observation bears on
them) and assert the KNOWLEDGE effects (records, images, estimates, the belief update) as known."
  `(seq (dolist (r (desig-prop-values ,self :requires))
          (if (establishable-p r) (achieve r) (wait-for (holds r))))
        ,@refinement
        (project-effects (desig-prop-values ,self :physical) :grade '(source projected))
        (assert-effects (desig-prop-values ,self :knowledge) :grade '(source recorded))))

(defmacro ensure-given (description)
  "A given-item: verified before the culture plan starts; a shortfall is treated by the
epistemic meta model like any ENSURE."
  `(ensure ,description :grade (source verified) :consequential t))

(defun vessel (culture)
  "The well that holds CULTURE, as chosen by the mapping to the laboratory (rsa/culture_plan.py)."
  (desig-prop-value (resolve-mapping culture) :vessel))
"""


def failures_section():
    return """;;; Culture-level failures: violations of the culture plan's own policies. Lab failures (lab-failure
;;; and its subtypes) come from the lab action plans after their repairs ran out.

(define-condition culture-failure (plan-failure)
  ((designator :initarg :description :reader failure-designator))
  (:documentation "A violated prevents- or maintains-item of the culture plan."))
(define-condition control-exposed (culture-failure)
  ()
  (:documentation "The control culture received a substance: the comparison is no longer licensed."))
"""


def mapping_section(Mp):
    rows = []
    for r in Mp["rows"]:
        how = (f"{r['lab_type']} {r['lab_step'][1:]}" if r["lab_step"] else "computation")
        rows.append(f"({r['culture_step'][1:]} {r['type']} -> {how})")
    vs = " ".join(f"({c} {v['role']} {v['lab_var']})" for c, v in Mp["vessels"].items())
    where = "; ".join(f"{c} {v['plate']}/{v['well']}" for c, v in Mp["vessels"].items())
    return f"""(defparameter *culture-to-lab*
  ;; the refinement rsa/culture_plan.py resolved; the vessels are {where}
  '((vessels {vs})
    (steps {' '.join(rows)})))
"""


def action_plan(typ, steps):
    roles = list(dict.fromkeys(k for s in steps for k in s["slots"]))
    P = {k: f"?{k}" for k in roles}
    kind, tpl = REFINE[typ]
    body = f"(perform {tpl(P, Symbolic)})"
    return (f"(def-action-plan {typ} ({' '.join(f'({k} ?{k})' for k in roles)})\n"
            f"  \"{DOC[typ]}\nPerformed in: {', '.join(s['var'][1:] for s in steps)}.\"\n"
            f"  (with-culture-contract (?self)\n    {body}))\n")


def designator(s, images):
    """The step's culture action designator as performed: its slots, requires and effects; its own variable becomes
    its tag, the images it produces become the designators bound in the plan."""
    d = parse(s["text"])[0]
    tag = s["var"][1:]
    txt = fmt(d[:2] + dslots(d))
    txt = re.sub(rf"\?{tag}\b", tag, txt)
    for v in images:
        txt = txt.replace(f"(an image {v} ", "(an image ")
    return txt


def culture_plan(P, D):
    pos = {s["var"]: i for i, s in enumerate(P["steps"])}
    images = {}
    for s in P["steps"]:
        for it in s["knowledge"]:
            c = it["cond"]
            if isinstance(c, list) and c[:2] == ["an", "image"] or (isinstance(c, list) and len(c) > 2 and c[1] == "image"):
                v = dvar(c)
                if v:
                    images[v] = fmt([c[0], c[1]] + [x for x in dslots(c) if x[0] in ("of", "culture-time")])
    params = " ".join(v for v in P["entities"]) + " ?E"
    lets = " ".join(f"({v} {d})" for v, d in images.items())
    out = [f"(def-cram-function challenge-rescue-culture-plan ({params})",
           f"  \"The culture plan: {len(P['steps'])} culture action designators. The order is derived from "
           f"{len(D['links'])} causal links\nover physical and knowledge effects (rsa/culture_plan.py); steps without "
           "an order between them\nmay run in any order or concurrently.\"",
           "  ;; the images are knowledge: designators the observations make effective",
           f"  (let* ({lets})", "    (partial-order", "        ("]
    for s in P["steps"]:
        sl = s["slots"]
        when = (f"culture-time {sl['from'][14:-1]} -> {sl['to'][14:-1]}" if "from" in sl else
                f"culture-time {sl['at'][14:-1]}" if "at" in sl else "after its inputs")
        out.append(f"         (:tag {s['var'][1:]}  ; {s['type']}, {when}\n          (perform {designator(s, images)}))")
    out[-1] += ")"
    for a, b in sorted(D["hasse"], key=lambda e: (pos[e[0]], pos[e[1]])):
        ls = [l for l in D["links"] if l["frm"] == a and l["to"] == b]
        out.append(f"      (:order {a[1:]} {b[1:]})  ; {ls[0]['kind']}: {'; '.join(sorted({l['cond'] for l in ls}))}")
    out[-1] = out[-1].replace(")  ;", "))))  ;", 1)
    return "\n".join(out) + "\n"


def top_level(P, K):
    lets = " ".join(f"({v} {d.replace(f' {v} ', ' ', 1)})" for v, d in P["entities"].items())
    goal = fmt(P["goal"][0]["cond"])
    given = " ".join(f"(ensure-given {fmt(g['cond'])})" for g in P["given"])
    pols = [f"(prevent (holds {fmt(it['cond'])}) {failure_for(fmt(it['cond']))})" for it in P["prevents"]]
    pols += [f"(maintain (holds {fmt(it['cond'])}) {failure_for(fmt(it['cond']))})" for it in P["maintains"]]
    safe = " ".join(f"(achieve {fmt(it['cond'])})" for it in P["maintains"])
    args = " ".join(P["entities"]) + " ?E"
    return f"""(def-top-level-cram-function challenge-rescue-culture-level ()
  "Question:
{P['question']}.
Goal: {goal}:
guaranteed in expectation by the design ({K['expected_gain_bit']} bit); one run measures its gain."
  ;; the process modules: the lab instruments (through the lab action plans) and the culture SDT for computations
  (with-process-modules-running (resolve-process-modules)
    (let* ((?E (current-experiment)) {lets})
      (with-failure-handling
          ((control-exposed (f)
             ;; the analysis would compare against an exposed control: do not update the belief
             (assert-effects '((the belief ?B (posterior withheld))) :grade '(source recorded))
             (escalate f))
           (lab-failure (f)
             ;; the lab action plans' repairs ran out; the culture plan cannot continue as derived
             (escalate f)))
        (unwind-protect
            (seq {given}
                 (ensure-design {goal})
                 (with-policy (par {' '.join(pols)})
                   (challenge-rescue-culture-plan {args})))
          ;; the safe state on any exit, at the culture level: every culture in its environment
          {safe})))))
"""


def generate():
    world = World("g050")
    text = open(os.path.join(LAB, "culture_plan.ldl")).read()
    P = load_plan(text)
    D = derive(P)
    assert not D["unsupported"] and not D["cyclic"], "the culture plan must be well-formed before a controller is generated"
    lab = check(open(os.path.join(LAB, "challenge_rescue.ldl")).read(), open(os.path.join(LAB, "contracts.ldl")).read(), world)
    Mp = mapping(P, D, lab)
    K = json.load(open(os.path.join(OUT, "culture_plan.json")))["knowledge"]
    # the refinement templates, instantiated with the mapping's vessels, must give the mapped lab designators
    R = Resolved(Mp["vessels"])
    by = {s["var"]: s for s in P["steps"]}
    tpl_check = []
    for r in Mp["rows"]:
        if r["lab_step"]:
            got = fmt(parse(REFINE[r["type"]][1](by[r["culture_step"]]["slots"], R))[0])
            tpl_check.append((r["culture_step"], got == strip_lab(r["lab_text"]), got, strip_lab(r["lab_text"])))
    types = list(dict.fromkeys(s["type"] for s in P["steps"]))
    header = f""";;; -*- Mode: Lisp -*-
;;; Challenge-rescue experiment at the culture level: the top-level CRAM/RPL plan.
;;; Generated by rsa/culture_to_cram.py from rsa/registry/lab/culture_plan.ldl (LDL v0.3, culture level):
;;; {len(P['steps'])} culture action designators, {len(D['links'])} causal links ({sum(l['kind'] == 'physical' for l in D['links'])} physical, {sum(l['kind'] == 'knowledge' for l in D['links'])} knowledge),
;;; {len(D['hasse'])} order constraints, {len(types)} action types. Below it: the lab level (rsa/out/challenge_rescue_src.lisp),
;;; whose action plans perform the lab action designators the culture actions are refined into.
;;; No plate, well, instrument or robot appears in code: vessels come from the mapping at run time.
;;; Notation: RPL control structures in CRAM Lisp syntax. Not executed: no Lisp CRAM here. ILLUSTRATIVE (D016).

(in-package :culture-src)   ; uses :lab-src
"""
    sections = dict(header=header, macros=macros(), failures=failures_section(), mapping=mapping_section(Mp),
                    action_plans="\n".join(action_plan(t, [s for s in P["steps"] if s["type"] == t]) for t in types),
                    culture_plan=culture_plan(P, D), top_level=top_level(P, K))
    pp = {k: (v if k in ("header", "macros") else pretty(v, "lisp")) for k, v in sections.items()}
    return pp, P, D, Mp, tpl_check, K


# ------------------------------------------------------------------------------------------------- the experiment as an entity
def _after(D):
    pre = {}
    for a, b in D["hasse"]:
        pre.setdefault(b, []).append(a[1:])
    return pre


def experiment_entity(P, D, Mp, K):
    """The experiment as one entity designator: question, hypotheses, materials and their roles, rules, steps and
    insights. The steps carry their order as (after ...) slots, the derived Hasse edges; nothing is written by hand."""
    ent = {v: parse(t)[0] for v, t in P["entities"].items()}
    role = lambda v: slot(ent[v], "role") or slot(ent[v], "type")  # noqa: E731
    plate = next(iter(Mp["vessels"].values()))["plate"]
    models = slot(ent["?B"], "over")[1]
    hyp = " ".join(f"(a recovery-model {m} (predicts (effect {K['predicted'][m]['effect_um']:.1f} um "
                   f"(sd {K['predicted'][m]['effect_sd_um']:.1f} um))))" for m in models)
    cultures = " ".join(f"(the culture {c} (role {v['role']}) (in (the well (id {v['well']}) (of ?p))) (state baseline))"
                        for c, v in Mp["vessels"].items())
    substances = " ".join(f"(some substance {v} (role {role(v)[1]}))" for v in P["entities"] if fmt(ent[v]).startswith("(some substance"))
    treat = {c: [] for c in Mp["vessels"]}
    for s in P["steps"]:
        if s["type"] in ("challenging", "rescuing"):
            sl = s["slots"]
            treat[sl["culture"]].append(f"({s['type'][:-3] + 'e' if s['type'] == 'challenging' else 'rescue'} {sl['substance']} "
                                        f"{sl['dose']} {sl['at']})")
    treatments = " ".join(f"({c} {' '.join(t) if t else 'untreated'})" for c, t in treat.items())
    rules = " ".join([f"(never {fmt(i['cond'])})" for i in P["prevents"]] + [f"(always {fmt(i['cond'])})" for i in P["maintains"]])
    after = _after(D)
    steps = []
    for s in P["steps"]:
        d = parse(s["text"])[0]
        keep = [x for x in dslots(d) if x[0] not in ("requires",) + EFFECTS]
        est = [i for i in s["requires"] if i["ann"].get(":establishable")]
        txt = fmt(["a", "step", s["var"]] + keep)[:-1]
        txt += f" (after {' '.join('?' + a for a in after.get(s['var'], []))})" if after.get(s["var"]) else " (after start)"
        if est:
            txt += " (needs " + " ".join(fmt(i["cond"]) for i in est) + ")"
        for k in EFFECTS:
            if s[k]:
                txt += f" ({k} " + " ".join(fmt(i["cond"]) for i in s[k]) + ")"
        steps.append(txt + ")")
    est_steps = [s for s in P["steps"] if any(isinstance(i["cond"], list) and len(i["cond"]) > 1 and i["cond"][1] == "estimate"
                                              for i in s["knowledge"])]
    ans = next(s for s in P["steps"] if s["type"] == "analysing")
    ins = [f"(the insight ?answer (answers (the question (of ?E))) (form (a belief ?B (over ({' '.join(models)})))) "
           f"(prior uniform) (entropy {K['entropy_before_bit']} bit) (expected-information-gain {K['expected_gain_bit']} bit) "
           f"(required (>= {K['required_bit']} bit)) (from {ans['var']}) (value unknown))"]
    for s in est_steps:
        c = s["knowledge"][0]["cond"]
        ins.append(f"(an insight (of {slot(c, 'of')[1]}) (quantity organoid-radius) (sigma {slot(c, 'sigma')[1]} um) "
                   f"(from {s['var']}) (value unknown))")
    q = fmt(parse(P["question"])[0]) if P["question"] else ""
    entity = f"""(defparameter *challenge-rescue*
  '(an experiment ?E
     (question {q})
     (hypotheses {hyp})
     (materials
       (the plate ?p (id {plate}) (in (a controlled-environment (profile culture-standard))))
       {cultures}
       {substances})
     (treatments {treatments})
     (rules {rules})
     (steps {' '.join(steps)})
     (insights {' '.join(ins)}))
  "The challenge-rescue experiment as one entity: what it asks, with what, under which rules, in which steps,
and which insights it produces. Generated from culture_plan.ldl and the mapping (plate and wells). The insights'
values are unknown until the experiment is conducted.")
"""
    # the insights after a run of the culture surrogate (ILLUSTRATIVE, D016)
    post = " ".join(f"({m} {K['posterior'][m]:.3f})" for m in models)
    best = max(K["posterior"], key=K["posterior"].get)
    obs = K["observed_radius_um"]
    filled = [f"(the insight ?answer (posterior {post}) (best-supported {best}) (entropy {K['entropy_after_bit']} bit) "
              f"(information-gain {K['information_gain_bit']} bit) (expected-information-gain {K['expected_gain_bit']} bit) "
              f"(evidence (effect (difference (radius ?cr) (radius ?cc)) {K['effect_um']} um)) (from {ans['var']}))"]
    for s in est_steps:
        c = slot(s["knowledge"][0]["cond"], "of")[1]
        filled.append(f"(an insight (of {c}) (quantity organoid-radius) (sigma {K['sigma_um']:.1f} um) (from {s['var']}) "
                      f"(value {obs[c[1:]]} um))")
    after_run = f"""(defparameter *challenge-rescue-insights-after-surrogate-run*
  ;; ILLUSTRATIVE (D016): Cell 01's culture surrogate, not biology (rsa/out/culture_plan.json)
  '(insights {' '.join(filled)})
  "What conducting *challenge-rescue* on the culture surrogate filled in: one run measures its gain;
the design guarantees the gain only in expectation.")
"""
    conducting = """(def-action-plan conducting ((experiment ?E))
  "Conduct an experiment given as an entity: bind its materials, keep its rules while its steps run,
perform every step after the steps its (after ...) slot names (steps with no order between them may
run concurrently), leave its cultures in their environment on any exit, and fill in its insights."
  (let* ((?bindings (resolve-materials ?E)))
    (unwind-protect
        (seq (ensure-given (initial-state-of ?E))
             (ensure-design (insight-expectation-of ?E))
             (with-policy (rules-as-monitors ?E)
               (perform-steps-in-order (steps-of ?E) ?bindings)))
      (achieve (safe-state-of ?E)))
    (fill-insights ?E)))
"""
    top = """(def-top-level-cram-function challenge-rescue ()
  "The whole experiment: conduct it."
  (with-process-modules-running (resolve-process-modules)
    (perform (an action (type conducting) (experiment *challenge-rescue*)))))
"""
    header = f""";;; -*- Mode: Lisp -*-
;;; The challenge-rescue experiment as an entity, and the top-level plan that conducts it.
;;; Generated by rsa/culture_to_cram.py from rsa/registry/lab/culture_plan.ldl, the mapping to Cell 01 and the culture
;;; surrogate run (rsa/out/culture_plan.json). Each step is performed by the action plan of its type in
;;; rsa/out/culture_plan_src.lisp, which refines it into lab actions (rsa/out/challenge_rescue_src.lisp).
;;; Notation: CRAM designators and RPL. Not executed: no Lisp CRAM here. ILLUSTRATIVE (D016).

(in-package :culture-src)
"""
    return dict(header=header, entity=entity, conducting=conducting, top=top, after_run=after_run)


ORDER = ("header", "macros", "failures", "mapping", "action_plans", "culture_plan", "top_level")


def main(argv):
    pp, P, D, Mp, tpl, K = generate()
    lisp = "\n".join(pp[k].rstrip() + "\n" for k in ORDER)
    path = os.path.join(OUT, "culture_plan_src.lisp")
    open(path, "w").write(lisp)
    json.dump(pp, open(os.path.join(OUT, "culture_plan_src_sections.json"), "w"), indent=1)
    code = re.sub(r";[^\n]*", "", re.sub(r'"(?:[^"\\]|\\.)*"', '""', lisp))
    depth, ok = 0, True
    for ch in code:
        depth += ch == "("
        depth -= ch == ")"
        ok &= depth >= 0
    orders = sorted(re.findall(r"\(:order (\w+) (\w+)\)", lisp))
    hasse = sorted((a[1:], b[1:]) for a, b in D["hasse"])
    devs = [d for d in ("l10", "l12", "l17", "l21", "h4", "r01", "r02", "p17", "a01", "a02", "a05")
            if re.search(rf"\b{d}\b", code.lower())]
    plans = set(re.findall(r"\(def-action-plan (\w+)", lisp))
    long_ = [l for l in lisp.split("\n") if len(l) > 110 and not l.lstrip().startswith(";")]
    for v, good, got, want in tpl:
        if not good:
            print(f"[culture->cram] refinement of {v} differs:\n  got  {got}\n  want {want}")
    print(f"[culture->cram] wrote {os.path.relpath(path)}: {lisp.count(chr(10))} lines; parentheses balanced {ok and depth == 0}; "
          f"{len(orders)} :order constraints = derived Hasse edges {orders == hasse}; action plans for every culture type "
          f"{plans == {s['type'] for s in P['steps']}}; refinement templates reproduce the mapped lab designators "
          f"{sum(g for _, g, _, _ in tpl)}/{len(tpl)}; lab order = projection of the culture order {Mp['order_preserved']}; "
          f"lab names in code {devs or 'none'}; code lines over 110 chars {len(long_)}")
    ex = experiment_entity(P, D, Mp, K)
    xl = "\n".join((v if k == "header" else pretty(v, "lisp")).rstrip() + "\n"
                    for k, v in ex.items())
    xpath = os.path.join(OUT, "challenge_rescue_experiment.lisp")
    open(xpath, "w").write(xl)
    xc = re.sub(r";[^\n]*", "", re.sub(r'"(?:[^"\\]|\\.)*"', '""', xl))
    ok &= xc.count("(") == xc.count(")")
    print(f"[culture->cram] wrote {os.path.relpath(xpath)}: {xl.count(chr(10))} lines")
    good = ok and depth == 0 and orders == hasse and all(g for _, g, _, _ in tpl) and not devs and Mp["order_preserved"]
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
