"""Export an audit trail as an OWL ABox of the OKF module (abox/rsa_trail.ofn), so the reasoner classifies the
designators into the kernel's categories (defined by level + kernelCategory) and the trail can be queried as
knowledge (WP5 NEEM-like export; ITERATIONS iteration 2).

    env_cad/bin/python -m rsa.okf_export [rsa/out/trail_<scenario>.json]
"""

from __future__ import annotations

import json
import os
import sys

from .kb import PLAN_DIR, REGISTRY

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(os.path.dirname(HERE), "okf", "lab-automation-twin")
RSA = "https://aicor.example/okf/lab1/rsa"
LEVEL = dict(scientific="KernelScientificDesignator", lab_task="KernelLabTaskDesignator",
             manipulation="KernelManipulationDesignator", motion="MotionStepDesignator",
             command="DeviceCommandDesignator")
MOTION = dict(approach="ApproachMotion", insert="InsertMotion", grasp="GraspMotion", lift="LiftMotion",
              transit="TransitMotion", place="PlaceMotion", release="ReleaseMotion", retract="RetractMotion",
              tool_couple="ToolCoupleMotion")


def export(trail_path: str, out_path: str) -> dict:
    import yaml
    sys.path.insert(0, os.path.join(MOD, "src"))
    from dl import PREFIXES
    cards = yaml.safe_load(open(os.path.join(REGISTRY, "categories.yaml")))
    names = json.load(open(os.path.join(PLAN_DIR, "plan_g050.json")))["names"]
    t = json.load(open(trail_path))
    run = t["run"].split("/")[-1]
    base = f"{RSA}/run/{run}"
    A, seen, n_ev = [], {}, 0
    decl = set()

    def ind(i):
        if i not in decl:
            decl.add(i)
            A.append(f"Declaration(NamedIndividual(<{i}>))")
        return f"<{i}>"
    lit = lambda v, dt: f'"{v}"^^xsd:{dt}'  # noqa: E731
    missing = set()
    prev = None
    for e in t["entries"]:
        d = f"{base}/designator/{e['designator']}"
        if e["designator"] not in seen:
            seen[e["designator"]] = e["category"]
            card = cards.get(e["category"])
            if card is None:
                missing.add(e["category"])
            elif card["level"] == "motion":
                A.append(f"ClassAssertion(:{MOTION.get(e['category'], 'MotionStepDesignator')} {ind(d)})")
            else:
                A.append(f"ClassAssertion(:{LEVEL[card['level']]} {ind(d)})")
                A.append(f"DataPropertyAssertion(:kernelCategory {ind(d)} {lit(e['category'], 'string')})")
            if e.get("parent"):
                A.append(f"ObjectPropertyAssertion(:refinesInto {ind(f'{base}/designator/{e['parent']}')} {ind(d)})")
            who = e.get("agent")
            if e["kind"] == "motion" and who in names:
                A.append(f"ObjectPropertyAssertion(:performedByRobot {ind(d)} <{names[who]}>)")
            if e["kind"] == "command" and who in names:
                A.append(f"ObjectPropertyAssertion(:commandsDevice {ind(d)} <{names[who]}>)")
        x = f"{base}/entry/{e['seq']:05d}"
        A += [f"ClassAssertion(:CommitmentAuditEntry {ind(x)})",
              f"DataPropertyAssertion(:recordSeq {ind(x)} {lit(e['seq'], 'integer')})",
              f"DataPropertyAssertion(:chainHash {ind(x)} {lit(e['hash'], 'string')})",
              f"DataPropertyAssertion(:simTime_s {ind(x)} {lit(float(e['t_sim']), 'double')})",
              f"ObjectPropertyAssertion(:recordsDesignator {ind(x)} {ind(d)})",
              f"ObjectPropertyAssertion(:hasTransition {ind(x)} :lifecycle_{e['transition']})"]
        if prev:
            A.append(f"ObjectPropertyAssertion(:chainedAfter {ind(x)} {ind(prev)})")
        prev = x
        for c in e.get("constraints") or []:
            prop = "violatesConstraint" if c["verdict"] == "VIOLATED" else "checksConstraint"
            A.append(f"ObjectPropertyAssertion(:{prop} {ind(x)} :constraint_{c['id']})")
        for k, ev in enumerate(e.get("evidence") or []):
            v = f"{x}/evidence/{k}"
            n_ev += 1
            A += [f"ClassAssertion(:EvidenceItem {ind(v)})",
                  f"DataPropertyAssertion(:evidenceSha256 {ind(v)} {lit(ev['sha256'], 'string')})",
                  f"DataPropertyAssertion(:statementText {ind(v)} {lit(ev['kind'], 'string')})",
                  f"ObjectPropertyAssertion(:carriesEvidence {ind(x)} {ind(v)})"]
    if missing:
        raise SystemExit(f"categories without a card: {sorted(missing)}")
    hdr = [f"Prefix({k}:=<{v}>)" for k, v in PREFIXES.items()]
    hdr += ["", f"Ontology(<https://aicor.example/okf/sdt/lab1/abox/rsa_trail>",
            "Import(<http://aicor.knowledge/okf/lab-automation-twin>)"]
    open(out_path, "w").write("\n".join(hdr + A + [")"]) + "\n")
    return dict(run=run, designators=len(seen), entries=len(t["entries"]), evidence=n_ev, axioms=len(A))


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out", "trail_nominal.json")
    r = export(src, os.path.join(MOD, "abox", "rsa_trail.ofn"))
    print(f"[rsa-okf] {os.path.relpath(src)} -> abox/rsa_trail.ofn: {r}")
