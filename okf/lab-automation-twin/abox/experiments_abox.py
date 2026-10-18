"""Culture experiments -> ABox: Cell 01's challenge-rescue study and the three executed runs of the culture SDT.

Design (twin/culture/model.py = Cell 01's isaac_sim_biological_runtime design, verbatim): challenge wells A03..D04 at
0.25 / 0.45 / 0.65 / 0.85 au, rescue A04 B04 C04 D04 at 6 h with 0.70 au, controls E03 E04 F03 F04, 4x imaging every
6 h to 72 h. Doses are abstract units (D016: illustrative surrogate).
  ChallengeRescueStudyDesign (RS StudyDesign) -> RescueHypothesis per dose (RS ScientificHypothesis), ExperimentalProtocol
  (RS) instantiated by the SDT's workflow, ObservationSchedule, ExperimentalArms with intervention specs. Arms carry
  closure axioms (only-these specs / no specs) so the reasoner classifies them as ChallengeOnly / ChallengeRescue /
  Control arms despite the open-world assumption.
  CultureExperimentRun (RS ExperimentalEpisode) per scenario (nominal / underdose / contamination) with its scenario
  condition (fault injection), interventions (Challenge / RescueIntervention, RS BiologicalIntervention) applied to
  wells, intervention records (committed or not), morphology readouts (RS CellViabilityReadout), the evidence trace,
  conclusions (RS ScientificConclusion) and withholding reasons.
Run: env_cad/bin/python okf/lab-automation-twin/abox/experiments_abox.py
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(MOD))
sys.path.insert(0, os.path.join(MOD, "src"))
sys.path.insert(0, REPO)
from dl import PREFIXES  # noqa: E402

SDT = "https://aicor.example/okf/sdt/lab1"
X = "https://aicor.example/okf/lab1/experiments"
HAZ = "https://aicor.example/okf/lab1/hazards"
WELLS = "/World/ExperimentalWorld/Plates/Plate_P17/Wells"
import importlib.util  # noqa: E402
spec = importlib.util.spec_from_file_location("culture_model", os.path.join(REPO, "twin", "culture", "model.py"))
cm = importlib.util.module_from_spec(spec)
sys.modules["culture_model"] = cm
spec.loader.exec_module(cm)

A, declared = [], set()


def decl(i):
    if i not in declared:
        declared.add(i)
        A.append(f"Declaration(NamedIndividual(<{i}>))")


def Ty(i, c):
    decl(i)
    A.append(f"ClassAssertion({c if c.startswith('Object') else ':' + c} <{i}>)")


def R(p, a, b):
    decl(a)
    decl(b)
    A.append(f"ObjectPropertyAssertion(:{p} <{a}> <{b}>)")


def Dv(p, a, v, dt="xsd:string"):
    if v is None or (isinstance(v, float) and v != v):
        return
    decl(a)
    if dt == "xsd:boolean":
        v = "true" if v else "false"
    A.append(f'DataPropertyAssertion(:{p} <{a}> "{str(v).replace(chr(34), chr(39))}"^^{dt})')


def well(w):
    return f"{SDT}{WELLS}/{w}#entity"


def organoid(w):
    return f"{SDT}{WELLS}/{w}/Physical/Organoid#entity"


# ---------------------------------------------------------------------------------------------- design
study = f"{X}/study/challenge_rescue_P17"
Ty(study, "ChallengeRescueStudyDesign")
Dv("sourceDocument", study, "Cell 01 biophysical_v2/isaac_sim_biological_runtime.py (design); twin/culture/model.py")
Dv("statementText", study, "Graded challenge A03..D04, rescue at 6 h in A04..D04, untreated controls E03..F04, 4x "
                           "bright-field imaging every 6 h to 72 h; doses in abstract units (illustrative, D016).")
proto = f"{X}/protocol/ccr_P17"
Ty(proto, "ExperimentalProtocol")
R("prescribesProtocol", study, proto)
R("instantiatedBy", proto, f"{SDT}/World/Experiment/Workflow#entity")
sched = f"{X}/schedule/every6h_72h"
Ty(sched, "ObservationSchedule")
Dv("interval_h", sched, cm.OBSERVE_EVERY_H, "xsd:double")
Dv("horizon_h", sched, cm.HORIZON_H, "xsd:double")
R("observedBySchedule", study, sched)
rescue_spec = f"{X}/spec/rescue_0.70au_6h"
Ty(rescue_spec, "RescueSpec")
Dv("doseAU", rescue_spec, cm.RESCUE_DOSE, "xsd:double")
Dv("time_h", rescue_spec, cm.RESCUE_AT_H, "xsd:double")
Ty(f"{SDT}/tasktypes/RescueDosingTask", "RescueDosingTask")
Ty(f"{SDT}/tasktypes/ChallengeDosingTask", "ChallengeDosingTask")
R("specifiesTask", rescue_spec, f"{SDT}/tasktypes/RescueDosingTask")
hyp, arms = {}, {}
for row in "ABCD":
    dose = cm.DOSE[f"{row}03"]
    cs = f"{X}/spec/challenge_{dose:.2f}au_0h"
    Ty(cs, "ChallengeSpec")
    Dv("doseAU", cs, dose, "xsd:double")
    Dv("time_h", cs, 0.0, "xsd:double")
    R("specifiesTask", cs, f"{SDT}/tasktypes/ChallengeDosingTask")
    h = f"{X}/hypothesis/rescue_raises_viability_{dose:.2f}au"
    Ty(h, "RescueHypothesis")
    Dv("statementText", h, f"rescue at 6 h raises 72 h viability at challenge {dose:.2f} au")
    R("testsHypothesis", study, h)
    hyp[dose] = h
    a1 = f"{X}/arm/challenge_only_{dose:.2f}au"
    Ty(a1, "ExperimentalArm")
    R("appliesIntervention", a1, cs)
    Ty(a1, "ObjectAllValuesFrom(:appliesIntervention :ChallengeSpec)")          # closure: challenge specs only
    R("assignsUnit", a1, well(f"{row}03"))
    a2 = f"{X}/arm/challenge_rescue_{dose:.2f}au"
    Ty(a2, "ExperimentalArm")
    R("appliesIntervention", a2, cs)
    R("appliesIntervention", a2, rescue_spec)
    R("assignsUnit", a2, well(f"{row}04"))
    for a in (a1, a2):
        R("hasArm", study, a)
    arms[row] = (a1, a2)
ctrl = f"{X}/arm/control"
Ty(ctrl, "ExperimentalArm")
Ty(ctrl, "ObjectMaxCardinality(0 :appliesIntervention)")                      # closure: no intervention at all
for w in cm.CONTROL_WELLS:
    R("assignsUnit", ctrl, well(w))
R("hasArm", study, ctrl)
for hz in ("SampleIntegrityHazard", "ContaminationHazard"):
    Ty(f"{HAZ}/{hz}", hz)

# ---------------------------------------------------------------------------------------------- runs
CONDITION = {"nominal": (None, "nominal: all 12 doses delivered"),
             "underdose": ("SampleIntegrityHazard", "D03's dispense clogs: 40 % delivered; pressure and completion "
                                                    "monitors fail; the dose record does not commit"),
             "contamination": ("ContaminationHazard", "C03 contaminated after the 24 h session (haze rises)")}
stats = {"runs": 0, "interventions": 0, "uncommitted": 0, "readouts": 0, "conclusions": 0, "withheld": 0}
for scen in ("nominal", "underdose", "contamination"):
    p = os.path.join(REPO, "scenes", "culture", scen, "run.json")
    if not os.path.exists(p):
        continue
    run = json.load(open(p))
    ri = f"{X}/run/{scen}"
    Ty(ri, "CultureExperimentRun")
    Dv("scenarioName", ri, scen)
    R("runOfStudy", ri, study)
    R("realizesProtocol", ri, proto)
    twin = f"{SDT}#culture_sdt" if scen == "contamination" else f"{X}/run/{scen}/culture_sdt"
    Ty(twin, "CultureSDT")
    R("updatesTwin", ri, twin)
    hz, text = CONDITION[scen]
    cond = f"{ri}/condition"
    Ty(cond, "FaultInjection" if hz else "ScenarioCondition")
    Dv("statementText", cond, text)
    if hz:
        R("injectsHazard", cond, f"{HAZ}/{hz}")
    R("hasScenarioCondition", ri, cond)
    trace = f"{ri}/evidence_trace"
    Ty(trace, "ExperimentalEvidenceTrace")
    R("recordsEpisode", trace, ri)
    R("hasEvidenceRecord", ri, trace)
    for k, ev in enumerate(run["interventions"]):
        e = f"{ri}/intervention/{k:02d}_{ev['kind']}_{ev['well']}"
        Ty(e, "ChallengeIntervention" if ev["kind"] == "challenge" else "RescueIntervention")
        R("appliedToWell", e, well(ev["well"]))
        rec = f"{e}/record"
        Ty(rec, "InterventionRecord")
        R("realizesIntervention", rec, e)
        Dv("isCommittedEvent", rec, bool(ev["committed"]), "xsd:boolean")
        Dv("doseAU", rec, ev["au"], "xsd:double")
        Dv("time_h", rec, ev["t_h"], "xsd:double")
        if ev["committed"]:
            R("recordsIntervention", twin, e)
        else:
            Dv("statementText", rec, "; ".join(ev.get("reasons", [])) or "not committed")
            stats["uncommitted"] += 1
        stats["interventions"] += 1
    for w, obs in run["observations"].items():
        for o in obs:
            f = o.get("features") or {}
            if not o.get("accepted") or not f:
                continue
            ro = f"{ri}/readout/{w}_{o['t_h']:04.1f}h".replace(".", "_")
            Ty(ro, "MorphologyViabilityReadout")
            R("observationOf", ro, organoid(w))
            R("concernsWell", ro, well(w))
            Dv("time_h", ro, o["t_h"], "xsd:double")
            Dv("radius_um", ro, f.get("radius_um"), "xsd:double")
            Dv("coreOpticalDensity", ro, f.get("core_od"), "xsd:double")
            stats["readouts"] += 1
    for k, c in enumerate(run["claims"]):
        ci = f"{ri}/conclusion/{k:02d}"
        Ty(ci, "RescueComparisonConclusion")
        Dv("statementText", ci, c["proposition"])
        Dv("claimStatus", ci, c["status"])
        Dv("claimProbability", ci, c["probability"], "xsd:double")
        R("drawnFrom", ci, trace)
        m = re.search(r"challenge ([0-9.]+) au", c["proposition"])
        if m:
            R("addressesHypothesis", ci, hyp[round(float(m.group(1)), 2)])
        for w in re.findall(r"\b([A-H]\d\d)\b", c["proposition"]):
            R("concernsWell", ci, well(w))
        if c["status"].startswith("withheld"):
            rs = f"{ci}/reason"
            Ty(rs, "ContaminationSuspectedReason" if "contamination" in c["status"] else "UnverifiedComparatorReason")
            Dv("statementText", rs, c["status"])
            R("withheldBecause", ci, rs)
            stats["withheld"] += 1
        stats["conclusions"] += 1
    if scen == "nominal":
        v = f"{ri}/verdict"
        Ty(v, "ExperimentalVerdict")
        R("assesses", v, ri)
        g = f"{ri}/verdict/grade"
        Ty(g, "ValidAndInterpretable")
        R("gradesValidity", v, g)
    stats["runs"] += 1

hdr = [f"Prefix({k}:=<{v}>)" for k, v in PREFIXES.items()]
hdr += ["", "Ontology(<https://aicor.example/okf/sdt/lab1/abox/experiments>",
        "Import(<http://aicor.knowledge/okf/lab-automation-twin>)",
        'Annotation(rdfs:comment "Cell 01 challenge-rescue study design and the three culture SDT runs.")']
open(os.path.join(HERE, "experiments.ofn"), "w").write("\n".join(hdr + A + [")"]) + "\n")
json.dump(stats, open(os.path.join(HERE, "experiments_stats.json"), "w"), indent=1)
print("[experiments-abox]", ", ".join(f"{k} {v}" for k, v in stats.items()))
