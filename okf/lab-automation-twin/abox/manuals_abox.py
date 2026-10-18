"""Device manual knowledge -> ABox: the ten Cell 01 SDT component contracts (sdt/components/*.yaml, read-only).

Each contract becomes a CellComponentContract (a DeviceManual) about its device's referent, with
  OperatingProcedure (RS ActionContract)  per action_contract: Preconditions (typed by kind), ExpectedEffects,
                                          DeviceMonitors, a RecoveryProcedure (AICOR Repair), EvidenceOutputs
  OperatingSetpoint                       per operational_state value
  OperatingConstraint (VRB LabConstraint) per constraint
  DeviceMonitor (AICOR ProcessMonitor)    per monitoring entry (expectation | observation)
  DeviceFailureMode (AICOR FailureSignature) per failure mode, with its consequence hazard and RecoveryProcedure
  RiskControl (VRB SafetyConstraint)      per risk control, with the hazard it mitigates
  DeviceProcessMicrotheory (AICOR BodyWorldProcessMicrotheory) from physical_model
Item texts are verbatim (statementText) with sourceDocument / sourceLocator. Kinds and hazards are assigned by the
keyword rules below (recorded per item as `classifiedBy`); no numeric vendor limit is invented (D016): the contracts
carry none, and no vendor manual is in the repository.
Run: env_cad/bin/python okf/lab-automation-twin/abox/manuals_abox.py
"""

import glob
import json
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
from dl import PREFIXES  # noqa: E402

RS_ROOT = os.path.expanduser("~/ResearchSpace")
SRC = os.path.join(RS_ROOT, "projects/robot-scientist/cell-01/AICOR_Cell01_Codex_Handoff/sdt/components")
SDT = "https://aicor.example/okf/sdt/lab1"
M = "https://aicor.example/okf/lab1/manuals"
HAZ = "https://aicor.example/okf/lab1/hazards"

PRE_RULES = [("AuthorizationPrecondition", r"authori[sz]|token|approv|review decision|qa "),
             ("CalibrationPrecondition", r"calibrat|tool frame|tcp|focus|reference valid"),
             ("EnvironmentPrecondition", r"environment|temperature|co2|humidity|envelope"),
             ("SafetyPrecondition", r"interlock|safe|airspace|collision|clear of|human|contamin|clean|steril|"
                                    r"compatib|containment|enclosure"),
             ("IdentityPrecondition", r"identit|barcode|verified|plate id|consistent"),
             ("PlacementPrecondition", r"present|seated|position|docked|loaded|at (the )?transfer|mounted|coupled"),
             ("AvailabilityPrecondition", r"availab|reserved|free|ready|empty|idle|clear")]
HAZ_RULES = [("ContaminationHazard", r"contamin|steril|asep|carryover|clean"),
             ("IdentityHazard", r"identit|swap|barcode|mislabel|inventory"),
             ("MeasurementValidityHazard", r"calibrat|focus|measurement|image|illumination|blur|drift|frame invalid"),
             ("CollisionHazard", r"collision|crash|drop|jam|stuck|slip|misplace|misalign|tilt|seat"),
             ("HumanInjuryHazard", r"human|person|operator|injur|e-?stop"),
             ("SampleIntegrityHazard", r"environment|temperature|co2|humidity|excursion|exposure|time|volume|"
                                       r"dose|evaporat|condition|confound")]

A, declared = [], set()


def decl(i):
    if i not in declared:
        declared.add(i)
        A.append(f"Declaration(NamedIndividual(<{i}>))")


def Ty(i, c):
    decl(i)
    A.append(f"ClassAssertion(:{c} <{i}>)")


def R(p, a, b):
    decl(a)
    decl(b)
    A.append(f"ObjectPropertyAssertion(:{p} <{a}> <{b}>)")


def Dv(p, a, v, dt="xsd:string"):
    decl(a)
    v = str(v).replace("\\", "\\\\").replace('"', "'")
    A.append(f'DataPropertyAssertion(:{p} <{a}> "{v}"^^{dt})')


def slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", str(s)).strip("_")[:60] or "item"


def classify(text, rules):
    t = text.lower()
    return [c for c, rx in rules if re.search(rx, t)]


for hz in ("ContaminationHazard", "IdentityHazard", "MeasurementValidityHazard", "CollisionHazard",
           "HumanInjuryHazard", "SampleIntegrityHazard"):
    Ty(f"{HAZ}/{hz}", hz)

index, stats = {}, {"manuals": 0, "procedures": 0, "preconditions": 0, "setpoints": 0, "constraints": 0,
                    "monitors": 0, "failure_modes": 0, "risk_controls": 0, "typed_by_rule": 0}
for f in sorted(glob.glob(os.path.join(SRC, "*.yaml"))):
    d = yaml.safe_load(open(f))
    rel = os.path.relpath(f, RS_ROOT)
    ident, cid = d["identity"], d["identity"]["component_id"]
    dev = f"{SDT}{d['grounding']['usd_path']}#entity"
    man = f"{M}/{slug(cid)}"
    Ty(man, "CellComponentContract")
    R("manualFor", man, dev)
    Dv("sourceDocument", man, "ResearchSpace/" + rel)
    Dv("canonicalName", man, ident.get("canonical_name", cid))
    Dv("manufacturerBaseline", man, ident.get("manufacturer_baseline", "n/a"))
    Dv("statementText", man, ident.get("role", ""))
    stats["manuals"] += 1
    # process knowledge
    pm = d.get("physical_model", {})
    mt = f"{man}/process_microtheory"
    Ty(mt, "DeviceProcessMicrotheory")
    R("microtheoryOf", mt, dev)
    R("hasPart", man, mt)
    Dv("statementText", mt, "; ".join(f"{k}: {', '.join(map(str, v)) if isinstance(v, list) else v}"
                                     for k, v in pm.items()))
    Dv("sourceLocator", mt, "physical_model")
    # setpoints
    for k, v in (d.get("operational_state") or {}).items():
        sp = f"{man}/setpoint/{slug(k)}"
        Ty(sp, "OperatingSetpoint")
        R("declaresSetpoint", man, sp)
        R("declaresSetpoint", dev, sp)
        Dv("quantityName", sp, k)
        Dv("statementText", sp, f"{k} = {v}")
        Dv("sourceLocator", sp, f"operational_state.{k}")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            Dv("setpointValue", sp, float(v), "xsd:double")
        stats["setpoints"] += 1
    # constraints
    for k, c in enumerate(d.get("constraints") or []):
        ci = f"{man}/constraint/{k:02d}"
        Ty(ci, "OperatingConstraint")
        R("declaresOperatingConstraint", man, ci)
        R("constrainsDevice", ci, dev)
        Dv("statementText", ci, c)
        Dv("sourceLocator", ci, f"constraints[{k}]")
        stats["constraints"] += 1
    # monitors
    mon_by_text = {}
    for k, mo in enumerate(d.get("monitoring") or []):
        mi = f"{man}/monitor/{k:02d}"
        Ty(mi, "DeviceMonitor")
        R("declaresMonitor", man, mi)
        txt = f"{mo.get('expectation', '')} | observed by: {mo.get('observation', '')}" if isinstance(mo, dict) else mo
        Dv("statementText", mi, txt)
        Dv("sourceLocator", mi, f"monitoring[{k}]")
        mon_by_text[str(mo.get("expectation", "") if isinstance(mo, dict) else mo).lower()] = mi
        stats["monitors"] += 1
    # failure modes
    for k, fm in enumerate(d.get("failure_modes") or []):
        fi = f"{man}/failure/{slug(fm.get('fault', k))}"
        Ty(fi, "DeviceFailureMode")
        R("declaresFailureMode", man, fi)
        Dv("statementText", fi, f"{fm.get('fault')}: {fm.get('consequence')}")
        Dv("sourceLocator", fi, f"failure_modes[{k}]")
        rec = f"{fi}/recovery"
        Ty(rec, "RecoveryProcedure")
        Dv("statementText", rec, fm.get("recovery", ""))
        R("hasRecoveryProcedure", fi, rec)
        R("respondsTo", rec, fi)
        for hz in classify(f"{fm.get('fault')} {fm.get('consequence')}", HAZ_RULES)[:2]:
            R("hasFailureConsequence", fi, f"{HAZ}/{hz}")
            stats["typed_by_rule"] += 1
        stats["failure_modes"] += 1
    # risk controls
    for k, rc in enumerate(d.get("risk_controls") or []):
        ri = f"{man}/risk_control/{k:02d}"
        Ty(ri, "RiskControl")
        R("declaresRiskControl", man, ri)
        Dv("statementText", ri, rc)
        Dv("sourceLocator", ri, f"risk_controls[{k}]")
        for hz in classify(rc, HAZ_RULES)[:2]:
            R("mitigatesHazard", ri, f"{HAZ}/{hz}")
            stats["typed_by_rule"] += 1
        stats["risk_controls"] += 1
    # operating procedures (action contracts)
    index[cid] = []
    for ac in d.get("action_contracts") or []:
        pi = f"{man}/procedure/{slug(ac['name'])}"
        index[cid].append(pi)
        Ty(pi, "OperatingProcedure")
        R("documentsProcedure", man, pi)
        Dv("statementText", pi, f"{ac['name']}: {ac.get('purpose', '')}")
        Dv("sourceLocator", pi, f"action_contracts.{ac['name']}")
        for k, pre in enumerate(ac.get("preconditions") or []):
            pc = f"{pi}/pre/{k:02d}"
            kinds = classify(pre, PRE_RULES)
            Ty(pc, kinds[0] if kinds else "Precondition")
            if kinds:
                stats["typed_by_rule"] += 1
            R("requiresPrecondition", pi, pc)
            R("isRequiredBy", pc, pi)
            Dv("statementText", pc, pre)
            stats["preconditions"] += 1
        for k, eff in enumerate(ac.get("expected_effects") or []):
            ei = f"{pi}/effect/{k:02d}"
            Ty(ei, "ExpectedEffect")
            R("hasExpectedEffect", pi, ei)
            R("isEffectOf", ei, pi)
            Dv("statementText", ei, eff)
        for k, mo in enumerate(ac.get("monitors") or []):
            mi = f"{pi}/monitor/{k:02d}"
            Ty(mi, "DeviceMonitor")
            R("usesProcedureMonitor", pi, mi)
            Dv("statementText", mi, mo)
        if ac.get("abort_or_recovery"):
            rc = f"{pi}/recovery"
            Ty(rc, "RecoveryProcedure")
            R("hasRecoveryProcedure", pi, rc)
            Dv("statementText", rc, ac["abort_or_recovery"])
        for k, ev in enumerate(ac.get("evidence_outputs") or []):
            ei = f"{pi}/evidence/{k:02d}"
            Ty(ei, "EvidenceOutput")
            R("producesEvidenceOutput", pi, ei)
            R("isEvidenceOf", ei, pi)
            Dv("statementText", ei, ev)
        stats["procedures"] += 1

hdr = [f"Prefix({k}:=<{v}>)" for k, v in PREFIXES.items()]
hdr += ["", "Ontology(<https://aicor.example/okf/sdt/lab1/abox/manuals>",
        "Import(<http://aicor.knowledge/okf/lab-automation-twin>)",
        'Annotation(rdfs:comment "Device manual knowledge from the ten Cell 01 SDT component contracts.")']
open(os.path.join(HERE, "manuals.ofn"), "w").write("\n".join(hdr + A + [")"]) + "\n")
json.dump(index, open(os.path.join(HERE, "manual_index.json"), "w"), indent=1)
json.dump(stats, open(os.path.join(HERE, "manuals_stats.json"), "w"), indent=1)
print("[manuals-abox]", ", ".join(f"{k} {v}" for k, v in stats.items()))
