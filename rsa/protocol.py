"""The experimentation plan (protocol) and the audit certificate, generated from the pipeline's outputs.

  protocol.json / protocol.md   what is to be done, to which cultures, with which devices, under which constraints, with
                                which monitors and failure handlers, and what counts as success; derived, not written
  audit.json                    every audit trail: hash chain intact, tamper test, verdict, the registry it ran under,
                                and for the symbolic runs a re-execution in a temporary directory whose chain head must
                                equal the recorded one (the trail is reproducible, not only intact)

Both are stages of rsa/reproduce.py, so their content is covered by the manifest.

    env_cad/bin/python -m rsa.protocol          # rsa/out/repro/{protocol.json, protocol.md, audit.json}
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "out")
REPRO = os.path.join(OUT, "repro")
DERIV = os.path.join(ROOT, "okf", "lab-automation-twin", "L3-logical-axiomatization", "derivation")
J = lambda *p: json.load(open(os.path.join(*p)))  # noqa: E731


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def protocol():
    from .reproduce import INPUTS, tree_sha
    cp, plan, ldl = J(OUT, "culture_plan.json"), J(DERIV, "out", "plan_g050.json"), J(OUT, "ldl_challenge_rescue.json")
    gm, rp, rep = J(OUT, "giskard_motions.json"), J(OUT, "refinement_proof.json"), J(OUT, "report.json")
    inputs = {k: {os.path.relpath(p, ROOT): tree_sha(p) for p in v} for k, v in INPUTS.items()}
    input_digest = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    K, sel = cp["knowledge"], plan["selected"]
    order = cp["derived"]["hasse"]
    P = dict(
        id="challenge-rescue/c_d85_t48_n1",
        status="ILLUSTRATIVE (D016): the culture biology is Cell 01's surrogate; no biomedical parameter is asserted",
        question=cp["plan"]["question"], goal=cp["plan"]["goal"], entities=cp["plan"]["entities"],
        input_digest=input_digest, plan_sha256=sha(os.path.join(DERIV, "out", "plan_g050.json")),
        design=dict(selected=sel["id"], challenge_dose_au=sel["dose_au"], rescue_dose_au=sel["rescue_au"], rescue_delay_h=sel["delay_h"],
                    replicates=sel["reps"], expected_information_gain_bit=sel["eig_bits"], required_bit=plan["requirement_bits"],
                    prior=plan["prior_over_models"], predicted_effect_um={m: round(v["effect_um"], 1) for m, v in sel["predicted_effect_um"].items()},
                    alternatives=[dict(id=c, eig_bit=plan["candidate_eig_bits"][c], cost=plan["candidate_optima"].get(c))
                                  for c in plan["feasible_candidates"]], cost=plan["cost"]),
        culture_plan=[dict(var=s["var"], type=s["type"], text=s["text"]) for s in cp["plan"]["steps"]], culture_order=order,
        vessels=cp["mapping"]["vessels"],
        lab_plan=[dict(var=s["var"], type=s["type"], text=s["text"], time_h=s.get("time_h"), instrument=s.get("instrument"),
                       signals=s.get("signals")) for s in ldl["steps"]],
        refinement=[dict(culture=r["culture_step"], culture_type=r["type"], lab=r["lab_step"], lab_type=r["lab_type"],
                         process=r.get("process"), device=r.get("device") or r.get("realised_by")) for r in cp["mapping"]["rows"]],
        sessions=[dict(session=s["session"], t_h=s["t_h"], device=s["device"], material=s["material"], steps=len(s["steps"]),
                       duration_s=s["duration_s"], route_out=[f"{r['robot']} {r['src']}->{r['dst']}" for r in s["route_out"]])
                  for s in plan["sessions"]],
        window_s=plan["window_s"], start_state=plan["state"],
        constraints=[c for c in ldl["experiment"] if c["clause"] in ("prevents", "maintains", "requires")],
        handlers=ldl["handles"], kpis=ldl["quality"]["kpis"],
        motions=dict(n=sum(len(l["motions"]) for l in gm["legs"]), legs=len(gm["legs"])),
        acceptance=dict(realization="every designed intervention and measurement executed; no prevents-item violated",
                        validity=list(J(OUT, "run_nominal.json")["verdict"]["validity"]["checks"]),
                        competency_questions=f"{rep['cq']['correct']}/{rep['cq']['n']}",
                        refinement_proof=rp["holds"]),
        reproduce=["env_cad/bin/python -m rsa.reproduce", "env_cad/bin/python -m rsa.reproduce --verify"],
    )
    return P


def md(P, A):
    L = [f"# Experimentation plan: {P['id']}", "", f"_Status: {P['status']}._", "",
         f"- Input digest: `{P['input_digest']}`", f"- Plan (clingo) sha256: `{P['plan_sha256']}`", "",
         "## 1. Question and goal", "", f"```lisp\n{P['question']}\n```", "", "Goal: `" + "`; `".join(P["goal"]) + "`", "",
         "Entities:", ""] + [f"- `{v}` {t}" for v, t in P["entities"].items()]
    d = P["design"]
    L += ["", "## 2. Design", "",
          f"Selected `{d['selected']}`: challenge {d['challenge_dose_au']} au to the rescued and comparator cultures at 0 h; rescue "
          f"{d['rescue_dose_au']} au to the rescued culture after {d['rescue_delay_h']} h; {d['replicates']} replicate; images at 72 h. "
          f"Expected information gain {d['expected_information_gain_bit']} bit (required {d['required_bit']} bit) over a uniform prior on "
          f"{', '.join(d['prior'])}. Cost {d['cost']['value']} {d['cost']['unit']}.", "",
          "| Candidate meeting the requirement | EIG (bit) | Optimal plan cost |", "|---|---|---|"]
    L += [f"| `{a['id']}`{' (selected)' if a['id'] == d['selected'] else ''} | {a['eig_bit']} | {a['cost']} |" for a in d["alternatives"]]
    L += ["", "## 3. Culture plan", "", "| | Action |", "|---|---|"] + [f"| {s['var']} | `{s['text']}` |" for s in P["culture_plan"]]
    L += ["", f"Order (Hasse edges): {', '.join(f'{a} < {b}' for a, b in P['culture_order'])}", "",
          "## 4. Vessels", "", "| Culture | Role | Plate | Well |", "|---|---|---|---|"]
    L += [f"| `{c}` | {v['role']} | {v['plate']} | {v['well']} |" for c, v in P["vessels"].items()]
    L += ["", "## 5. Refinement into the laboratory", "", "| Culture action | Lab action | Process | Realized by |", "|---|---|---|---|"]
    L += [f"| {r['culture']} {r['culture_type']} | {r['lab'] or '-'} {r['lab_type'] or 'computation'} | {r['process'] or ''} | "
          f"{', '.join(r['device']) if isinstance(r['device'], list) else r['device']} |" for r in P["refinement"]]
    L += ["", "Lab action designators:", "", "```lisp"] + [s["text"] for s in P["lab_plan"]] + ["```", "",
          "## 6. Sessions", "", f"Start state: {P['start_state']}. Window outside the incubator per trip: {P['window_s']} s.", "",
          "| Session | Culture time | Device | Material | Steps | Duration | Route out |", "|---|---|---|---|---|---|---|"]
    L += [f"| {s['session']} | {s['t_h']} h | {s['device'].upper()} | {'; '.join(' '.join(map(str, m)) for m in s['material'])} | {s['steps']} | "
          f"{s['duration_s']} s | {'; '.join(s['route_out'])} |" for s in P["sessions"]]
    L += [f"", f"Robot motions: {P['motions']['n']} Giskard motion statecharts over {P['motions']['legs']} transport legs.", "",
          "## 7. Constraints", "", "| Clause | Condition | Status |", "|---|---|---|"]
    L += [f"| {c['clause']} | `{c['cond']}` | {c.get('status', '')} |" for c in P["constraints"]]
    L += ["", "## 8. Failure handling", ""] + [f"- `{h['text']}`" for h in P["handlers"]]
    L += ["", "## 9. Quality and acceptance", "", "| KPI | Of | Aggregate | Target |", "|---|---|---|---|"]
    L += [f"| {k['name']} | `{k['of']}` | {k['aggregate']} | {k['op']} {k['target']} {k['unit']} |" for k in P["kpis"]]
    a = P["acceptance"]
    L += ["", f"Realization: {a['realization']}. Validity checks: {', '.join(a['validity'])}. Competency questions answered: "
          f"{a['competency_questions']}. Refinement proof holds: {a['refinement_proof']}.", "",
          "## 10. Records", "",
          "Every designator lifecycle transition is one entry of a SHA-256 hash chain (prev hash + canonical JSON), written by the "
          "executor, never by the plan. Entries carry agent, software (kernel, KB, registry hash, backend), simulated time, "
          "bindings, resolutions, constraint verdicts (realization | validity), monitors and evidence with its own sha256.", "",
          "| Trail | Entries | Chain | Tamper detected | Re-executed | Head | End | Disposition |", "|---|---|---|---|---|---|---|---|"]
    L += [f"| {t['scenario']} | {t['n']} | {'intact' if t['chain_ok'] else 'BROKEN'} | {t['tamper_detected']} | "
          f"{'identical' if t['reexecuted_identical'] else ('n/a (physics run)' if t['reexecuted_identical'] is None else 'DIFFERS')} | "
          f"`{t['head'][:16]}` | {t['end']} | {t['disposition']} |" for t in A["trails"]]
    L += ["", "## 11. Reproduce", ""] + [f"    {c}" for c in P["reproduce"]] + [""]
    return "\n".join(L)


def audit():
    from . import run_example as RE
    from .audit import verify
    from .critic import assess
    scen = yaml.safe_load(open(os.path.join(HERE, "registry", "scenarios.yaml")))
    scen = scen.get("scenarios", scen)
    reg = RE.registry_sha()
    rows = []
    names = sorted(n[len("trail_"):-len(".json")] for n in os.listdir(OUT) if n.startswith("trail_") and n.endswith(".json"))
    for name in names:
        td = J(OUT, f"trail_{name}.json")
        v = verify(td)
        t2 = copy.deepcopy(td)
        victim = next((e for e in t2["entries"] if e.get("evidence")), t2["entries"][len(t2["entries"]) // 2])
        if victim.get("evidence"):
            victim["evidence"][0]["value"] = "TAMPERED"
        else:
            victim["transition"] = "TAMPERED"
        vt = verify(t2)
        same = None
        if name in scen:
            old = RE.OUT
            with tempfile.TemporaryDirectory() as tmp:
                RE.OUT = tmp
                try:
                    RE.run_scenario(name, scen[name])
                    same = J(tmp, f"trail_{name}.json") == td
                finally:
                    RE.OUT = old
        a = assess(td)
        end = next((e["transition"] for e in reversed(td["entries"]) if e["category"] == "experiment"), None)
        rows.append(dict(scenario=name, n=len(td["entries"]), chain_ok=v["ok"], attributable=v.get("attributable"),
                         evidence_hashed=v.get("evidence_hashed"), evidence=sum(len(e.get("evidence") or []) for e in td["entries"]),
                         tamper_detected=not vt["ok"], tamper_first_bad_seq=vt.get("first_bad_seq"), reexecuted_identical=same,
                         head=td["entries"][-1]["hash"], software=td["software"], registry_current=td["software"]["registry"] == reg,
                         end=end, realization=a["realization"]["ok"], validity=a["validity"]["ok"], disposition=a["disposition"]))
    rep = J(OUT, "report.json")
    return dict(registry_now=reg, trails=rows, competency_questions=dict(n=rep["cq"]["n"], correct=rep["cq"]["correct"],
                by_family=rep["cq"]["by_family"]),
                ok=all(r["chain_ok"] and r["tamper_detected"] and r["reexecuted_identical"] in (True, None) for r in rows))


def main(argv):
    os.makedirs(REPRO, exist_ok=True)
    P, A = protocol(), audit()
    json.dump(P, open(os.path.join(REPRO, "protocol.json"), "w"), indent=1, default=str)
    json.dump(A, open(os.path.join(REPRO, "audit.json"), "w"), indent=1, default=str)
    open(os.path.join(REPRO, "protocol.md"), "w").write(md(P, A))
    sym = [r for r in A["trails"] if r["reexecuted_identical"] is not None]
    print(f"[protocol] {P['id']}: {len(P['culture_plan'])} culture actions, {len(P['lab_plan'])} lab actions, {len(P['sessions'])} sessions, "
          f"{P['motions']['n']} motions; input digest {P['input_digest'][:16]}")
    print(f"[audit] {len(A['trails'])} trails: chains intact {sum(r['chain_ok'] for r in A['trails'])}, tamper detected "
          f"{sum(r['tamper_detected'] for r in A['trails'])}, re-executed identical {sum(bool(r['reexecuted_identical']) for r in sym)}/{len(sym)}, "
          f"under the current registry {sum(r['registry_current'] for r in A['trails'])}")
    return 0 if A["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
