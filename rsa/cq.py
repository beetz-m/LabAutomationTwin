"""Competency questions: the assistant answers questions about its own activity (KERNEL.md concept 12, WP6).

Answers are computed from the audit trail (what happened, why, with which evidence), the knowledge base (what holds,
what is possible) and dry runs (what would happen). Every answer carries its grounds (trail entries / KB atoms).
Expected answers are written per scenario in registry/cq.yaml from the scenario specification, not from runs.
"""

from __future__ import annotations

import copy
import json
import os
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .audit import verify
from .core import Belief, Context, Failure, NullAudit, perform
from .critic import assess
from .kb import KB, REGISTRY

Ans = Tuple[Any, List[str]]


# ----------------------------------------------------------------------------------------------------- trail access
class T:
    def __init__(self, trail: Dict[str, Any]):
        self.d = trail
        self.E = trail["entries"]
        self.parent = {e["designator"]: e["parent"] for e in self.E}
        self.cat = {e["designator"]: e["category"] for e in self.E}

    def first(self, **kw) -> Optional[Dict[str, Any]]:
        return next((e for e in self.E if all(e.get(k) == v for k, v in kw.items())), None)

    def all(self, **kw) -> List[Dict[str, Any]]:
        return [e for e in self.E if all(e.get(k) == v for k, v in kw.items())]

    def chain(self, uid: str) -> List[str]:
        out = []
        while uid:
            out.append(uid)
            uid = self.parent.get(uid)
        return out

    def session_of(self, uid: str) -> Optional[str]:
        for u in self.chain(uid):
            if self.cat.get(u) == "run_session":
                g = self.first(designator=u, transition="grounded")
                return g["bindings"]["session"] if g else None
        return None

    def in_session(self, session: str) -> List[Dict[str, Any]]:
        return [e for e in self.E if self.session_of(e["designator"]) == session]

    def experiment(self) -> Dict[str, Any]:
        g = self.first(category="experiment", transition="grounded")
        return (g or {}).get("bindings") or {}


def ev(e, kind):
    return next((x["value"] for x in (e or {}).get("evidence") or [] if x["kind"] == kind), None)


def g(e) -> str:
    return f"trail#{e['seq']}:{e['category']}/{e['transition']}"


def dry_run(kb: KB, designator, plate: str = "P17"):
    """What would happen: execute with full acceptance logic on a fault-free copy of the world, without audit."""
    from .backend import SymbolicWorld
    w = SymbolicWorld(kb, projection=True)
    b = Belief()
    w.initial_belief(b, plate)
    ctx = Context(kb, w, NullAudit(), b)
    try:
        perform(designator, ctx)
        return ctx.root, None, w
    except Failure as f:
        return ctx.root, f, w


def refusals(node) -> List[str]:
    return sorted({c["id"] for n in node.walk() for c in n.constraints if c["verdict"] == "VIOLATED"})


# ----------------------------------------------------------------------------------------------------- answers
def q_what(run, a) -> Ans:
    t = run["T"]
    e = t.first(category=a["category"], transition="executed")
    if not e:
        return None, []
    return dict(category=e["category"], device=e["agent"], plate=ev(e, "plate"), well=ev(e, "well"),
                reagent=ev(e, "reagent"), volume_uL=ev(e, "volume_delivered_uL"),
                culture_time_h=ev(e, "culture_time_h")), [g(e)]


def q_why_chain(run, a) -> Ans:
    t = run["T"]
    e = t.first(category=a["category"], transition="executed")
    chain = [t.cat[u] for u in t.chain(e["designator"])]
    x = t.experiment()
    well = ev(e, "well")
    role = next((r for r, ws in x.get("wells", {}).items() if well in ws), None)
    return dict(chain=chain, design=x.get("design"), requirement_bits=x.get("requirement_bits"),
                eig_bits=x.get("eig_bits"), role=role, session=t.session_of(e["designator"])), \
        [g(e)] + [g(t.first(designator=u, transition="grounded")) for u in t.chain(e["designator"])[1:]
                  if t.first(designator=u, transition="grounded")]


def q_why_device(run, a) -> Ans:
    t = run["T"]
    e = t.first(category=a["category"], transition="grounded")
    r = next(r for r in e["resolutions"] if r["query"].startswith("devices_for"))
    return dict(device=r["value"], grounds=r["grounds"], rejected=r["rejected"]), [g(e)] + r["grounds"]


def q_why_route(run, a) -> Ans:
    t = run["T"]
    e = t.first(category="transport_lab", transition="grounded")
    r = next(r for r in e["resolutions"] if r["query"].startswith("route"))
    kb = run["kb"]
    src, dst = r["value"][0][1], r["value"][-1][2]
    s1 = sorted(x[1] for x in kb.q("serves", None, src))
    s2 = sorted(x[1] for x in kb.q("serves", None, dst))
    return dict(legs=[list(l) for l in r["value"]], serves_source=s1, serves_target=s2), [g(e)] + r["grounds"]


def q_why_tool(run, a) -> Ans:
    t = run["T"]
    out, gr, before = {}, [], {}
    for e in t.all(category="coupling_tool", transition="open"):
        s = t.session_of(e["designator"])
        out[s] = out.get(s, 0) + 1
        pe = t.first(designator=e["parent"], transition="grounded")
        r = next(r for r in pe["resolutions"] if r["query"].startswith("tool_for"))
        b = next(r for r in pe["resolutions"] if r["query"].startswith("belief tool:"))
        before[s] = b["grounds"][0].split("(")[-1].rstrip(")")
        gr += [g(pe)] + r["grounds"]
    return dict(couplings=out, grounds=sorted(set(x for x in gr if not x.startswith("trail"))), belief_before=before), gr


def q_time_outside(run, a) -> Ans:
    t = run["T"]
    out, gr = {}, []
    for e in t.all(category="run_session", transition="open"):
        s = t.session_of(e["designator"])
        end = [x for x in t.all(designator=e["designator"]) if x["transition"] in ("executed", "repaired", "failed",
                                                                                   "escalated")]
        ret = next((x for x in t.E if x["parent"] == e["designator"] and x["category"] != "calibrate"
                    and x["transition"] in ("open", "executed")), None)
        if ret is not None and ret["kind"] != "action":      # a leaf: its entry is written at its end
            ret = dict(ret, t_sim=ret["t_sim"] - (ret.get("duration_s") or 0))
        if end and ret:          # from the trip start (first non-preparation step), as in the planner (F11)
            out[s] = round(end[-1]["t_sim"] - ret["t_sim"], 2)
            gr += [g(ret), g(end[-1])]
    w, m = run["kb"].window_s()
    out.update(window_s=w, margin_pct=m)
    return out, gr


def q_constraints_in_session(run, a) -> Ans:
    t = run["T"]
    out: Dict[str, set] = {}
    gr = []
    for e in t.in_session(a["session"]):
        for c in e.get("constraints") or []:
            out.setdefault(c["id"], set()).add(c["verdict"])
            gr.append(g(e))
    return {k: sorted(v) for k, v in out.items()}, sorted(set(gr))[:5] + [f"... {len(set(gr))} entries"]


def q_must_hold(run, a) -> Ans:
    from .checks import applicable
    kb = run["kb"]
    ctx = run["ctx"]
    cat = a["category"]
    ids = applicable(ctx, cat, "accept") + applicable(ctx, cat, "post") + applicable(ctx, cat, "policy")
    contract = kb.contract("l12", "dose_well") or {}
    return dict(kernel=ids, cell01_contract=contract.get("preconditions", [])), \
        [f"registry:constraints.{i}" for i in ids] + ["component:L12_LiquidHandler.action_contracts.dose_well"]


def q_devices_now(run, a) -> Ans:
    kb = run["kb"]
    d = kb.devices_for(["imaging"], ["image_well"])
    out = {x: kb.measurement_binding(x, "organoid_radius_um").value for x in d.value or []}
    return out, d.grounds + [kb.measurement_binding(x, "organoid_radius_um").grounds[0] for x in d.value or []] + \
        [f"rejected {x}: {r}" for x, r in d.rejected] + ([] if d.value else ["no automated device with imaging + image_well"])


def q_can_robot(run, a) -> Ans:
    kb = run["kb"]
    r, s, d = a["robot"], a["source"], a["target"]
    miss = [f"serves({r},{x})" for x in (s, d) if not kb.holds("serves", r, x)]
    return dict(possible=not miss, missing=miss), [f"serves({r},{x})" for x in (s, d) if kb.holds("serves", r, x)] \
        + [f"not {m}" for m in miss]


def _session_designator(run, session: str):
    from .core import Plate
    from .library import RunSession
    plan = run["plan"]
    s = next(s for s in plan["sessions"] if s["session"] == session)
    return RunSession(session=s["session"], trip=s["trip"], t_h=s["t_h"], plate=Plate(run["plate"]),
                      material=[tuple(m) for m in s["material"]], roles=plan["wells"])


def q_whatif(run, a) -> Ans:
    from .library import experiment_from_plan
    base = run["kb"]
    kb = base.derive(base.name + "+whatif", add=a.get("add", ()), remove=a.get("remove", ()))
    if a.get("components"):
        alts = (base.registry.get("devices") or {}).get("alternative_components") or {}
        comps = {}
        for dev, alt in a["components"].items():
            rec = copy.deepcopy(alts[alt])
            rec["_twin"] = copy.deepcopy((base.components.get(dev) or {}).get("_twin") or {})
            comps[dev] = rec
        kb = kb.derive(kb.name, components=comps)
    pid = run["plate"]
    d = _session_designator(run, a["session"]) if a.get("session") else experiment_from_plan(run["plan"], pid)
    root, err, _ = dry_run(kb, d, pid)
    ref_root, _, _ = dry_run(base, _session_designator(run, a["session"]) if a.get("session")
                             else experiment_from_plan(run["plan"], pid), pid)
    mine = [n.designator.term() for n in root.leaves()]
    ref = [n.designator.term() for n in ref_root.leaves()]
    inserted = sorted({n.designator.category for n in root.walk() if n.designator.KIND == "action"} -
                      {n.designator.category for n in ref_root.walk() if n.designator.KIND == "action"})
    out = dict(outcome="refused" if err and err.code == "refused" else ("failed" if err else "completes"),
               refused_by=refusals(root) if err else [], inserted=inserted, plan_changed=mine != ref,
               duration_s=round(root.t1 - root.t0, 2))
    if a.get("session"):
        w, m = kb.window_s()
        out["within_window"] = round(out["duration_s"] * (100 + m) / 100, 2) <= w
    viol = sorted({c["id"] for n in root.walk() for c in n.constraints if c["verdict"] == "VIOLATED"
                   and c["column"] == "validity"})
    out["validity_violations"] = viol
    qc = [n.designator.device for n in root.walk() if n.designator.category == "validate"]
    if qc:
        out["qc_station"] = qc[0]
    return out, [f"dry run on {kb.name} ({len(mine)} leaves vs {len(ref)})"] + [f"{x}" for x in a.get("add", [])] + \
        [f"not {x}" for x in a.get("remove", [])]


def q_evidence_dose(run, a) -> Ans:
    t = run["T"]
    e = next(e for e in t.all(category="dispense", transition="executed")
             if ev(e, "well") == a["well"] and ev(e, "reagent") == a["reagent"])
    sib = [x for x in t.all(parent=e["parent"], category="aspirate", transition="executed")]
    rg = ev(sib[-1], "reagent") if sib else {}
    s = t.session_of(e["designator"])
    idr = [ev(x, "barcode_read")["read"] for x in t.in_session(s) if x["category"] == "verify_identity"
           and ev(x, "barcode_read")]
    entry = next(x for x in t.d["entries"] if x["seq"] == e["seq"])
    return dict(well=ev(e, "well"), reagent=ev(e, "reagent"), lot=rg.get("lot"), delivered_uL=ev(e, "volume_delivered_uL"),
                commanded_uL=ev(e, "volume_commanded_uL"), tip_id=ev(e, "tip_id"), identity_read_in_session=idr[-1]
                if idr else None, culture_time_h=ev(e, "culture_time_h"), hash_chained=bool(entry.get("hash"))), \
        [g(e)] + ([g(sib[-1])] if sib else [])


def q_integrity(run, a) -> Ans:
    v = verify(run["trail"])
    t2 = copy.deepcopy(run["trail"])
    t2["entries"][len(t2["entries"]) // 2]["transition"] = "EDITED"
    return dict(intact=v["ok"], tamper_detected=not verify(t2)["ok"]), [f"verify over {v.get('n')} entries"]


def q_repairs(run, a) -> Ans:
    t = run["T"]
    out = []
    for e in t.all(transition="repairing"):
        out.append(dict(failure=e["repair"]["failure"], at=e["category"], repair=e["repair"]["repair_categories"]))
    return out, [g(e) for e in t.all(transition="repairing")] or [f"no repairing entry among {len(t.E)} trail entries"]


def q_rescue(run, a) -> Ans:
    t = run["T"]
    d = [e for e in t.all(category="dispense", transition="executed") if ev(e, "reagent") == "rescue"]
    if d:
        return dict(rescue_given=True, wells=sorted({ev(e, "well") for e in d}),
                    culture_time_h=ev(d[0], "culture_time_h")), [g(e) for e in d]
    reasons = []
    for e in t.E:
        if e["transition"] in ("abstained", "escalated", "failed", "policy_violation") and e["kind"] != "command" or \
                e["transition"] == "failed" and e["category"] == "verify_identity":
            r = e.get("reason") or "; ".join(f"{c['id']}: {c.get('observation')}" for c in e.get("constraints") or []
                                             if c["verdict"] == "VIOLATED")
            if r:
                reasons.append((e, r))
    e, r = reasons[0] if reasons else (None, "not in this run's design")
    viol = [f"{c['id']}: {c.get('observation')}" for c in (e or {}).get("constraints") or [] if c["verdict"] == "VIOLATED"]
    return dict(rescue_given=False, reason=r + ("; " + "; ".join(viol) if viol else "")), [g(e)] if e else []


def q_where(run, a) -> Ans:
    b = run["ctx"].belief
    pid = a.get("plate") or run["plate"]
    k = f"plate_at:{pid}"
    return dict(plate=pid, at=b.get(k), source=b.source(k)), [f"belief {k} ({b.items.get(k, (None, None, None))[2]})"]


def q_regulation(run, a) -> Ans:
    norms = run["kb"].registry["norms"]["clauses"]
    t = run["T"]
    v = verify(run["trail"])
    seen = {}
    for e in t.E:
        for c in e.get("constraints") or []:
            seen.setdefault(c["id"], set()).add(c["verdict"])
    cov, notc, viol = [], [], []
    for cid, c in norms.items():
        rb = c["realised_by"]
        if "audit_field" in rb:
            ok = v["ok"] and v.get("attributable") and v.get("evidence_hashed")
            (cov if ok else notc).append(cid)
        elif "runtime" in rb:
            vs = set().union(*[seen.get(x, set()) for x in rb["runtime"]])
            (viol if "VIOLATED" in vs else cov if "ENFORCED" in vs else notc).append(cid)
        else:
            notc.append(cid)
    return dict(covered=cov, not_covered=notc, violated=viol), ["registry:norms", f"verify ok={v['ok']}"]


def q_quarantine(run, a) -> Ans:
    t = run["T"]
    out = []
    for e in t.all(category="contain", transition="executed"):
        q = ev(e, "quarantine_request")
        out.append(dict(plate=q["plate"], status=q["status"], authorization=q["authorization"]))
    return dict(quarantined=out), [g(e) for e in t.all(category="contain")] or \
        [f"no contain entry among {len(t.E)} trail entries"]


def q_verdict(run, a) -> Ans:
    v = run["verdict"]
    failed = sorted(k for k, c in v["validity"]["checks"].items() if not c["ok"])
    return dict(realization=v["realization"]["ok"], validity=v["validity"]["ok"], nr3=v["nr3"], failed_checks=failed), \
        ["critic over trail"]


def q_promotable(run, a) -> Ans:
    v = run["verdict"]
    return dict(promotable=v["promotable"], reason=v["disposition"]), ["critic over trail", "D009"]


def q_unknowns(run, a) -> Ans:
    b = run["ctx"].belief
    out = [f"{k} = {v}" for k, (v, src, _) in sorted(b.items.items()) if src in ("stale", "assumed") or v == "unknown"]
    kb = run["kb"]
    for dev in ("l12",):
        for c in (kb.components.get(dev) or {}).get("constraints") or []:
            if "not equivalent" in c:
                out.append(f"L12: {c}")
    return out, ["belief provenance", "component:L12_LiquidHandler.constraints"]


def q_robot_did(run, a) -> Ans:
    t = run["T"]
    out: Dict[str, int] = {}
    for e in t.in_session(a["session"]):
        if e["kind"] == "motion" and e["agent"] == a["robot"] and e["transition"] == "executed":
            out[e["category"]] = out.get(e["category"], 0) + 1
    return out, [f"trail motion entries of {a['robot']} in {a['session']}"]


def q_category(run, a) -> Ans:
    reg = run["kb"].registry["categories"]
    c = reg[a["category"]]
    t = run["T"]
    e = t.first(category=a["category"], transition="executed")
    realises = [t.cat[u] for u in t.chain(e["designator"])[1:] if reg.get(t.cat[u], {}).get("level") in
                ("lab_task", "scientific")][:2] if e else []
    return dict(level=c.get("level"), effect_class=c.get("effect_class"), facet=c.get("facet"),
                okf_class=c.get("okf_class"), realises=realises), [f"registry:categories.{a['category']}"] + \
        ([g(e)] if e else [])


FN = {k: v for k, v in globals().items() if k.startswith("q_")}


# ----------------------------------------------------------------------------------------------------- matching
def match(expected, got) -> bool:
    if isinstance(expected, str) and expected.startswith("~"):
        return isinstance(got, str) and expected[1:] in got
    if isinstance(expected, dict):
        if expected.get("$set") is not None:
            return isinstance(got, list) and sorted(map(json.dumps, expected["$set"])) == sorted(map(json.dumps, got))
        if expected.get("$contains") is not None:
            return isinstance(got, list) and all(any(match(x, y) for y in got) for x in expected["$contains"])
        return isinstance(got, dict) and all(k in got and match(v, got[k]) for k, v in expected.items())
    if isinstance(expected, float) or isinstance(got, float):
        try:
            return abs(float(expected) - float(got)) < 0.051
        except (TypeError, ValueError):
            return False
    if isinstance(expected, list):
        return isinstance(got, list) and len(expected) == len(got) and all(match(x, y) for x, y in zip(expected, got))
    return expected == got


def run_cqs(runs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    cat = yaml.safe_load(open(os.path.join(REGISTRY, "cq.yaml")))
    results, ok, n, n_ok, n_grounded = [], True, 0, 0, 0
    for cq in cat["questions"]:
        for sc, exp in (cq.get("expect") or {}).items():
            if sc not in runs:
                continue
            r = runs[sc]
            ctx = r["_ctx"]
            run = dict(T=T(ctx.audit.as_dict()), trail=ctx.audit.as_dict(), kb=ctx.kb, ctx=ctx, plan=r["_plan"],
                       verdict=r["verdict"], plate=r["plate"])
            try:
                ans, grounds = FN[cq["fn"]](run, cq.get("args") or {})
                err = None
            except Exception as ex:  # an unanswerable question is a failed CQ, reported
                ans, grounds, err = None, [], f"{type(ex).__name__}: {ex}"
            good = err is None and match(exp, json.loads(json.dumps(ans, default=list)))
            n += 1
            n_ok += good
            n_grounded += bool(grounds)
            ok &= good and bool(grounds)
            results.append(dict(id=cq["id"], family=cq["family"], scenario=sc, question=cq["question"], ok=good,
                                answer=ans, expected=exp, grounds=grounds[:8], error=err))
    for x in results:
        if not x["ok"]:
            print(f"[cq] FAIL {x['id']} [{x['scenario']}] {x['question']}\n      expected {json.dumps(x['expected'])}"
                  f"\n      got      {json.dumps(x['answer'], default=list)}" + (f"\n      {x['error']}" if x["error"] else ""))
    fam = {}
    for x in results:
        f = fam.setdefault(x["family"], [0, 0])
        f[0] += x["ok"]
        f[1] += 1
    print(f"[cq] {n_ok}/{n} answers correct, {n_grounded}/{n} grounded, over {len({x['id'] for x in results})} questions "
          f"x scenarios; by family: " + ", ".join(f"{k} {a}/{b}" for k, (a, b) in fam.items()))
    return dict(ok=ok and n_ok == n, n=n, correct=n_ok, grounded=n_grounded, by_family=fam, results=results)
