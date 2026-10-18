"""Run the kernel on the challenge-rescue example: all scenarios, cross-check, critic, tamper test, competency questions.

    env_cad/bin/python -m rsa.run_example [scenario ...] [--no-cq]

Writes rsa/out/trail_<scenario>.json, rsa/out/run_<scenario>.json and rsa/out/report.json / report.md; exits 1 if
any expectation fails (cross-check, expected verdict, CQ answer, tamper detection).
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
from typing import Any, Dict

import yaml

from .audit import AuditTrail, verify
from .backend import SymbolicWorld
from .core import KERNEL_VERSION, Belief, Context, Failure, perform
from .critic import assess
from .kb import KB, PLAN_DIR, REGISTRY
from .library import experiment_from_plan

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

#: expected verdict per scenario (written from the scenario's specification, not from a run). `end` is the lifecycle
#: end of the root (experiment); repairs are recorded on the node that repaired (`repaired_at`). A session that fails
#: after a safe return reports `session_failed`, which the executor routes as escalation (human decision).
#: Corrected after the first run (ITERATIONS.md, iteration 1, E1/E2): the first table expected root-level 'repaired'
#: and 'failed' where the design (written before the run) records node-level repairs and escalation.
EXPECTED = dict(
    nominal=dict(end="executed", realization=True, validity=True, promotable=True, repaired_at=[]),
    uncalibrated_known=dict(end="executed", realization=True, validity=True, promotable=True, repaired_at=[]),
    calibration_lapsed=dict(end="executed", realization=True, validity=True, promotable=True, repaired_at=["image"]),
    tip_lost=dict(end="executed", realization=True, validity=True, promotable=True, repaired_at=["dose"]),
    identity_swap=dict(end="escalated", realization=False, validity=False, promotable=False, repaired_at=["retrieve"]),
    tool_changer_slow=dict(end="escalated", realization=False, validity=False, promotable=False,
                           repaired_at=["run_session"]),
    imager_swapped=dict(end="executed", realization=True, validity=False, promotable=False, nr3=True, repaired_at=[]),
    # F6 (iteration 1): with experiment-level projection these are refused before the first intervention
    imager_incapable=dict(end="abstained", realization=False, validity=False, promotable=False, repaired_at=[]),
    rescue_unbound=dict(end="abstained", realization=False, validity=False, promotable=False, repaired_at=[]),
    control_dropped=dict(end="abstained", realization=False, validity=False, promotable=False, repaired_at=[]),
    contamination=dict(end="abstained", realization=False, validity=False, promotable=False, repaired_at=[]),
    # F7: the understanding gate is knowledge-only and runs in projection, so this is refused before execution
    # Isaac (iteration 2): written before the runs; repairs left open where the twin's focus behaviour may add a
    # reacquisition (ITERATIONS, iteration 2)
    isaac_nominal=dict(end="executed", realization=True, validity=True, promotable=True),
    isaac_identity_swap=dict(end="escalated", realization=False, validity=False, promotable=False,
                             repaired_at=["retrieve"]),
    isaac_calibration_lapsed=dict(end="executed", realization=True, validity=True, promotable=True),
    card_incomplete=dict(end="abstained", realization=False, validity=False, promotable=False, repaired_at=[]),
)


def experiment_plate() -> str:
    """The plate the experiment is about, from the OKF experiments ABox (not hard-coded in plans)."""
    import re
    ofn = os.path.join(os.path.dirname(PLAN_DIR), "..", "..", "abox", "experiments.ofn")
    return sorted(set(re.findall(r"/Plates/Plate_(\w+?)/Wells/", open(ofn).read())))[0]


def lint_plans() -> list:
    """Plans name categories and requirements, never devices, robots, poses or plates (KERNEL.md concept 4)."""
    import re
    kb = KB.load("g050")
    names = {a[1] for a in kb.facts if a[0] in ("automated", "serves", "holds_plate", "home")} | \
            {a[2] for a in kb.facts if a[0] in ("serves", "seat", "tool_pose", "requires_tool")} | {experiment_plate()}
    bad = []
    for f in ("library.py", "checks.py"):
        for i, line in enumerate(open(os.path.join(HERE, f)), 1):
            for nm in names:
                if re.search(rf"[\"']{re.escape(str(nm))}[\"']", line):
                    bad.append(f"{f}:{i}: {nm}")
    return bad


def registry_sha() -> str:
    h = hashlib.sha256()
    for d, dirs, files in sorted(os.walk(REGISTRY)):     # includes registry/lab (LDL contracts and experiments)
        dirs.sort()
        for f in sorted(files):
            h.update(open(os.path.join(d, f), "rb").read())
    return h.hexdigest()[:12]


def scenario_kb(base: KB, sc: Dict[str, Any], name: str) -> KB:
    comps = {}
    alts = (base.registry.get("devices") or {}).get("alternative_components") or {}
    for dev, alt in (sc.get("components") or {}).items():
        rec = copy.deepcopy(alts[alt])
        rec["_twin"] = copy.deepcopy((base.components.get(dev) or {}).get("_twin") or {})
        comps[dev] = rec
    kb = base.derive(name, add=sc.get("add", ()), remove=sc.get("remove", ()), components=comps)
    if sc.get("card_patch"):
        reg = copy.deepcopy(kb.registry)
        for cat, patch in sc["card_patch"].items():
            for k in patch.get("drop", []):
                reg["categories"][cat].pop(k, None)
        kb.registry = reg
    return kb


def run_scenario(name: str, sc: Dict[str, Any]) -> Dict[str, Any]:
    tag = sc.get("plan", "g050")
    base = KB.load(tag)
    kb = scenario_kb(base, sc, f"facts_{tag}+{name}")
    plan = json.load(open(os.path.join(PLAN_DIR, f"plan_{tag}.json")))
    exp = experiment_from_plan(plan, experiment_plate(), drop_roles=tuple(sc.get("drop_roles", ())))
    world = SymbolicWorld(kb, faults=copy.deepcopy(sc.get("faults")))
    belief = Belief()
    world.initial_belief(belief, exp.plate.id)
    software = dict(kernel=KERNEL_VERSION, kb=kb.name, registry=registry_sha(), backend=world.name)
    trail = AuditTrail(f"challenge-rescue/{name}", software)
    ctx = Context(kb, world, trail, belief)
    try:
        perform(exp, ctx)
        err = None
    except Failure as f:
        err = f"{f.code}: {f.detail}"
    root = ctx.root
    td = trail.as_dict()
    os.makedirs(OUT, exist_ok=True)
    json.dump(td, open(os.path.join(OUT, f"trail_{name}.json"), "w"), indent=1, default=str)
    rec: Dict[str, Any] = dict(scenario=name, about=sc.get("about"), error=err, end=root.lifecycle[-1] if root.lifecycle
                               else root.status, n_entries=len(td["entries"]),
                               n_leaves=len(root.leaves()), clock_s=round(world.clock, 1))
    # ---- cross-check: the kernel's expansion vs the clingo plan, per session (same facts, independent derivations)
    if sc.get("crosscheck"):
        cc = []
        for n in root.walk():
            if n.designator.category == "run_session":
                s = next(s for s in plan["sessions"] if s["session"] == n.designator.session)
                mine = [x.designator.term() for x in n.leaves()]
                ref = [st["term"] for st in s["steps"]]
                cc.append(dict(session=n.designator.session, steps=len(mine), planner_steps=len(ref), same=mine == ref,
                               duration_s=round(n.t1 - n.t0, 2),
                               planner_duration_s=round(s["duration_s"] + s.get("prep_s", 0.0), 2),
                               projected_s=(getattr(n, "projection", None) or {}).get("duration_s")))
        rec["crosscheck"] = cc
    # ---- audit integrity + tamper test
    v = verify(td)
    t2 = copy.deepcopy(td)
    victim = next((e for e in t2["entries"] if e.get("evidence")), t2["entries"][len(t2["entries"]) // 2])
    if victim.get("evidence"):
        victim["evidence"][0]["value"] = "TAMPERED"
    else:
        victim["transition"] = "TAMPERED"
    vt = verify(t2)
    rec["audit"] = dict(verify=v, tampered_detected=not vt["ok"], tampered_first_bad_seq=vt.get("first_bad_seq"))
    # ---- critic
    rec["verdict"] = assess(td)
    exp_v = EXPECTED.get(name, {})
    got = dict(end=rec["end"], realization=rec["verdict"]["realization"]["ok"], validity=rec["verdict"]["validity"]["ok"],
               promotable=rec["verdict"]["promotable"], nr3=rec["verdict"]["nr3"])
    rec["repairs"] = [dict(r, category=n.designator.category, node=n.uid) for n in root.walk() for r in n.repairs]
    got["repaired_at"] = [r["category"] for r in rec["repairs"]]
    rec["expected"] = exp_v
    rec["got"] = got
    rec["expectation_ok"] = all(got[k] == v for k, v in exp_v.items())
    rec["plate"] = exp.plate.id
    rec["_ctx"] = ctx
    rec["_plan"] = plan
    json.dump({k: v for k, v in rec.items() if not k.startswith("_")}, open(os.path.join(OUT, f"run_{name}.json"), "w"),
              indent=1, default=str)
    return rec


def _short(x, n=150):
    t = json.dumps(x, default=list, ensure_ascii=False)
    return t if len(t) <= n else t[:n - 3] + "..."


def write_md(runs, cq_res, ok):
    L = ["# Robot science assistant kernel: challenge-rescue example (iteration 1)", "",
         f"Generated by `env_cad/bin/python -m rsa.run_example`; overall **{'PASS' if ok else 'FAIL'}**. Symbolic backend "
         "(world-state model with fault injection), not Isaac. ILLUSTRATIVE (D016).", "",
         "## Scenarios", "", "| scenario | what is changed | root ends | realization | validity | disposition | leaves |"
         " audit entries | repairs |", "|---|---|---|---|---|---|---|---|---|"]
    for n, r in runs.items():
        v = r["verdict"]
        L.append(f"| {n} | {r['about']} | {r['end']} | {'ok' if v['realization']['ok'] else 'x'} | "
                 f"{'ok' if v['validity']['ok'] else 'x'} | {v['disposition']} | {r['n_leaves']} | {r['n_entries']} | "
                 + ("; ".join(f"{x['failure']} at {x['category']} -> {', '.join(x['repair_categories'])}"
                              for x in r["repairs"]) or "-") + " |")
    L += ["", "## Cross-check: kernel expansion vs clingo plan (same facts, independent derivations)", "",
          "| scenario | session | kernel steps | planner steps | identical | kernel s | planner s | projected s |",
          "|---|---|---|---|---|---|---|---|"]
    for n, r in runs.items():
        for c in r.get("crosscheck") or []:
            L.append(f"| {n} | {c['session']} | {c['steps']} | {c['planner_steps']} | {c['same']} | {c['duration_s']} | "
                     f"{c['planner_duration_s']} | {c['projected_s']} |")
    if cq_res:
        L += ["", f"## Competency questions: {cq_res['correct']}/{cq_res['n']} correct, {cq_res['grounded']}/{cq_res['n']}"
              " grounded", ""]
        for x in cq_res["results"]:
            L.append(f"- **{x['id']} [{x['scenario']}]** {x['question']}  ")
            L.append(f"  {'✓' if x['ok'] else '✗'} `{_short(x['answer'], 220)}`  ")
            L.append(f"  grounds: {_short(x['grounds'], 200)}")
    open(os.path.join(OUT, "report.md"), "w").write("\n".join(L) + "\n")


def main(argv):
    scen = yaml.safe_load(open(os.path.join(REGISTRY, "scenarios.yaml")))
    names = [a for a in argv if not a.startswith("--")] or list(scen)
    runs = {n: run_scenario(n, scen[n]) for n in names}
    ok = True
    for n, r in runs.items():
        cc = r.get("crosscheck")
        ccs = (" crosscheck " + " ".join(f"{c['session']}:{c['steps']}/{c['planner_steps']}"
                                          f"{'=' if c['same'] else '!'}{c['duration_s']}s" for c in cc)) if cc else ""
        good = r["expectation_ok"] and r["audit"]["verify"]["ok"] and r["audit"]["tampered_detected"] and \
            all(c["same"] and abs(c["duration_s"] - c["planner_duration_s"]) < 0.05 for c in cc or [])
        ok &= good
        v = r["verdict"]
        print(f"[rsa] {n:20s} {'OK ' if good else 'BAD'} end={r['end']:9s} R={'ok' if v['realization']['ok'] else 'x '} "
              f"V={'ok' if v['validity']['ok'] else 'x '} -> {v['disposition']}; {r['n_leaves']} leaves, "
              f"{r['n_entries']} audit entries{ccs}" + (f"; error {r['error']}" if r["error"] else ""))
    lint = lint_plans()
    print(f"[rsa] lint: plan code names no device/robot/pose/plate" if not lint else f"[rsa] lint FAIL: {lint}")
    ok &= not lint
    cq_res = None
    if "--no-cq" not in argv:
        from .cq import run_cqs
        cq_res = run_cqs(runs)
        ok &= cq_res["ok"]
    report = dict(kernel=KERNEL_VERSION, lint=lint, scenarios={n: {k: v for k, v in r.items() if not k.startswith("_")}
                                                    for n, r in runs.items()}, cq=cq_res, ok=ok)
    json.dump(report, open(os.path.join(OUT, "report.json"), "w"), indent=1, default=str)
    write_md(runs, cq_res, ok)
    print(f"[rsa] {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
