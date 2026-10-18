"""Verify the lab-automation-twin module with its ABoxes, answer the competency questions, write inferences back to USD.

1. ROBOT merges the upstream union (AICOR + robot-scientist + VRB + normative-admissibility, compiled by AICOR's own
   exporter) with the module's full-semantics TBox and the ABoxes (sdt, records, manuals, safety, experiments).
   Guard: the merged file must exist and carry the expected number of class assertions (a missing input must never
   read as "consistent").
2. Konclude: consistency, classification (unsatisfiable concepts), realisation (every entailed type).
3. Negative controls (robot-scientist convention): four injected contradictions must each make the KB INCONSISTENT.
4. Entailed types -> scenes/sdt_ontology.usda (ont:inferredTypes); competency questions -> docs/competency_questions.md;
   instance partonomy -> docs/partonomy_lab1.md + docs/partonomy_cell01.png; report -> out/check-report.json.
Exit 1 on inconsistency, an unsatisfiable module concept, or a negative control that stays consistent.
Run: env_cad/bin/python okf/lab-automation-twin/check_module.py
"""

import collections
import json
import os
import re
import subprocess
import sys
import time

from pxr import Sdf, Usd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(HERE, "src"))
import tbox  # noqa: E402
from dl import AICOR_NS  # noqa: E402

TOOLS = os.path.join(HERE, "tools")
KONCLUDE = os.path.join(TOOLS, "konclude", "Binaries", "Konclude")
ROBOT = os.path.join(TOOLS, "robot.jar")
BUILD, ABOX, DOCS = (os.path.join(HERE, d) for d in ("build", "abox", "docs"))
OUT = os.path.join(HERE, "L2-conceptual-framework", "out")
SDT = "https://aicor.example/okf/sdt/lab1"
W = SDT + "/World"
ABOXES = ["sdt", "records", "manuals", "safety", "experiments"]
# the experiment-to-motion derivation's plan (derive_plan.py --abox) and its twin execution (realised_gain.py --abox)
ABOXES += [a for a in ("plan", "plan_execution", "rsa_trail") if os.path.exists(os.path.join(HERE, "abox", f"{a}.ofn"))]
OWN = {c["name"] for c in tbox.CLASSES if ":" not in c["name"]}
C01 = os.path.expanduser("~/ResearchSpace/projects/robot-scientist/cell-01/AICOR_Cell01_Codex_Handoff")
BRIDGE = [os.path.join(HERE, "bridge", "cell01-bridge.ofn"), os.path.join(C01, "biology/ontology/aicor-biology.ttl"),
          os.path.join(C01, "sdt/ontology/cell01_components.ttl")]
BRIDGE = [b for b in BRIDGE if os.path.exists(b)]


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def merge(extra=None, out="all_merged.owx"):
    path = os.path.join(BUILD, out)
    if os.path.exists(path):
        os.remove(path)
    inputs = ["--input", os.path.join(BUILD, "upstream-aicor-ontology.ttl")]
    for a in ABOXES:
        inputs += ["--input", os.path.join(ABOX, f"{a}.ofn")]
    for b in BRIDGE:                     # D-LAT-8: Cell 01's own ontologies (read-only) + the bridge
        inputs += ["--input", b]
    if extra:
        inputs += ["--input", extra]
    r = run(["java", "-Xmx8g", "-jar", ROBOT, "merge", "--catalog", os.path.join(BUILD, "catalog-v001.xml")] + inputs +
            ["--output", path])
    if r.returncode != 0 or not os.path.exists(path):
        sys.exit(f"[check] merge failed: {r.stderr[-800:]}")
    return path


def konclude(cmd, inp, out=None):
    t = time.time()
    r = run([KONCLUDE, cmd, "-w", "AUTO", "-i", inp] + (["-o", out] if out else []))
    return r.stdout + r.stderr, time.time() - t


def verdict(log):
    if "is inconsistent" in log:
        return False
    if "is consistent" in log:
        return True
    sys.exit(f"[check] Konclude gave no verdict:\n{log[-600:]}")


# ---------------------------------------------------------------------------------------------- 1-2 reasoning
merged = merge()
n_ca = open(merged).read().count("<ClassAssertion>")
expected = len({l.strip() for a in ABOXES for l in open(os.path.join(ABOX, f"{a}.ofn")) if l.startswith("ClassAssertion(")})
if n_ca < expected:
    sys.exit(f"[check] merged KB has {n_ca} class assertions, expected >= {expected}: input lost")
log_c, t_c = konclude("consistency", merged)
consistent = verdict(log_c)
print(f"[check] Konclude: TBox + {len(ABOXES)} ABoxes + upstream union + Cell 01 bridge ({len(BRIDGE)} files) "
      f"({n_ca} class assertions): "
      f"{'consistent' if consistent else 'INCONSISTENT'} ({t_c:.1f} s)")
if not consistent:
    sys.exit(1)
cls_out, real_out = os.path.join(BUILD, "classification.owx"), os.path.join(BUILD, "realization.owx")
_, t_k = konclude("classification", merged, cls_out)
_, t_r = konclude("realization", merged, real_out)
ct, rt = open(cls_out).read(), open(real_out).read()
unsat = []
sup = collections.defaultdict(set)
for m in re.finditer(r"<EquivalentClasses>(.*?)</EquivalentClasses>", ct, re.S):
    iris = re.findall(r'IRI="([^"]+)"', m.group(1))
    if any(i.endswith("owl#Nothing") for i in iris):
        unsat += [i for i in iris if not i.endswith("owl#Nothing")]
    for a in iris:
        sup[a] |= set(iris) - {a}
for m in re.finditer(r'<SubClassOf>\s*<Class IRI="([^"]+)"/>\s*<Class IRI="([^"]+)"/>', ct):
    sup[m.group(1)].add(m.group(2))
anc_cache = {}


def ancestors(c):
    if c not in anc_cache:
        seen, stack = set(), [c]
        while stack:
            for s in sup.get(stack.pop(), ()):
                if s not in seen:
                    seen.add(s)
                    stack.append(s)
        anc_cache[c] = seen
    return anc_cache[c]


types = collections.defaultdict(set)
for m in re.finditer(r'<ClassAssertion>\s*<Class IRI="([^"]+)"/>\s*<NamedIndividual IRI="([^"]+)"/>', rt):
    types[m.group(2)].add(m.group(1))
inferred = {}
for i, cs in types.items():
    allc = set(cs)
    for c in cs:
        allc |= ancestors(c)
    inferred[i] = {c[len(AICOR_NS):] for c in allc if c.startswith(AICOR_NS)}
unsat_own = [u for u in unsat if u.startswith(AICOR_NS) and u[len(AICOR_NS):] in OWN]
print(f"[check] classification {t_k:.1f} s, realisation {t_r:.1f} s; unsatisfiable: {len(unsat)} "
      f"(module concepts: {len(unsat_own)})")

# ---------------------------------------------------------------------------------------------- 3 negative controls
NEG = [("SDT node typed as a physical artifact (node vs referent: AICOR physical/abstract cut)",
        f"ClassAssertion(:LabArtifact <{W}/Cell01/Stations/L10_Incubator>)"),
       ("an intervention typed as both challenge and rescue (disjoint)",
        "ClassAssertion(:RescueIntervention <https://aicor.example/okf/lab1/experiments/run/nominal/intervention/"
        "00_challenge_A03>)"),
       ("the control arm given an intervention (closure: max 0)",
        "ObjectPropertyAssertion(:appliesIntervention <https://aicor.example/okf/lab1/experiments/arm/control> "
        "<https://aicor.example/okf/lab1/experiments/spec/rescue_0.70au_6h>)"),
       ("a well typed as culture medium (disjoint)",
        f"ClassAssertion(:CultureMediumPortion <{W}/ExperimentalWorld/Plates/Plate_P17/Wells/C03#entity>)")]
if "plan" in ABOXES:
    NEG.append(("a derived motion step typed as a device command (designator levels are disjoint)",
                "ClassAssertion(:DeviceCommandDesignator <https://aicor.example/okf/lab1/e2m/session/s0_trip1/step/"
                "003_approach>)"))
if "rsa_trail" in ABOXES:
    _m = re.search(r"ClassAssertion\(:ApproachMotion (<[^>]+>)\)", open(os.path.join(ABOX, "rsa_trail.ofn")).read())
    NEG.append(("a kernel motion designator also typed as a manipulation-level designator (kernel levels are disjoint)",
                f"ClassAssertion(:KernelManipulationDesignator {_m.group(1)})"))
neg_results = []
for k, (what, ax) in enumerate(NEG):
    p = os.path.join(BUILD, f"negative_control_{k}.ofn")
    open(p, "w").write(f"Prefix(:=<{AICOR_NS}>)\nOntology(<{SDT}/negative/{k}>\n{ax}\n)\n")
    log, _ = konclude("consistency", merge(p, f"negative_{k}.owx"))
    ok = verdict(log) is False
    neg_results.append(dict(control=what, inconsistent_as_required=ok))
    print(f"[check] negative control {k + 1}: {what}: {'INCONSISTENT as required' if ok else 'STILL CONSISTENT (FAIL)'}")

# ---------------------------------------------------------------------------------------------- asserted facts
facts = collections.defaultdict(list)
data = collections.defaultdict(dict)
same = collections.defaultdict(set)
asserted = collections.defaultdict(set)
for a in ABOXES:
    for c_, x in re.findall(r"ClassAssertion\(:(\w+) <([^>]+)>\)", open(os.path.join(ABOX, f"{a}.ofn")).read()):
        asserted[x].add(c_)
for a in ABOXES:
    txt = open(os.path.join(ABOX, f"{a}.ofn")).read()
    for p_, x, y in re.findall(r"ObjectPropertyAssertion\(:(\w+) <([^>]+)> <([^>]+)>\)", txt):
        facts[p_].append((x, y))
    for p_, x, v in re.findall(r'DataPropertyAssertion\(:(\w+) <([^>]+)> "([^"]*)"', txt):
        data[x].setdefault(p_, v)
    for x, y in re.findall(r"SameIndividual\(<([^>]+)> <([^>]+)>\)", txt):
        same[x].add(y)
        same[y].add(x)


def leaf(i):
    return i.split("#")[0].rstrip("/").rsplit("/", 1)[-1] if "#entity" in i else i.rsplit("/", 1)[-1]


def inst(c):
    return sorted(i for i, t in inferred.items() if c in t)


def txt(i):
    return data[i].get("statementText", leaf(i))


# ---------------------------------------------------------------------------------------------- 4a USD write-back
lay = Sdf.Layer.FindOrOpen(os.path.join(REPO, "scenes", "sdt_ontology.usda"))
st = Usd.Stage.Open(lay)
n_usd = 0
for p in st.TraverseAll():
    a = p.GetAttribute("ont:referent")
    if a and a.Get() in inferred:
        p.CreateAttribute("ont:inferredTypes", Sdf.ValueTypeNames.StringArray, custom=True).Set(
            sorted(inferred[a.Get()]))
        n_usd += 1
lay.Save()

# ---------------------------------------------------------------------------------------------- 4b competency questions
CQ = []


def Q(q, lines, how):
    CQ.append((q, lines, how))


serves = collections.defaultdict(list)
for r_, s_ in facts["servesStation"]:
    serves[s_].append(leaf(r_))
Q("Which Cell 01 stations are lab-automation devices, of which (entailed) kinds, and which robot serves each?",
  [f"{leaf(s)}: {', '.join(sorted(inferred[s] & {'PlateStorageDevice', 'IncubationDevice', 'ImagingDevice', 'DispensingDevice', 'AutomatedPlateHotel', 'AutomatedCO2Incubator', 'QCCalibrationStation', 'QuarantineStation'}))}"
   f" — served by {', '.join(sorted(serves[s])) or '-'}" for s in inst("LabAutomationDevice")],
  "VRB LabAutomationDevice; PlateStorageDevice ≡ LabAutomationDevice ⊓ ∃hasDirectComponent.PlateCassette")
l10m = "https://aicor.example/okf/lab1/manuals/L10"
Q("What does L10's manual (Cell 01 component contract) specify?",
  [f"baseline: {data[l10m].get('manufacturerBaseline')}",
   "setpoints: " + "; ".join(txt(sp) for x, sp in facts["declaresSetpoint"] if x == l10m),
   "procedures: " + "; ".join(txt(p) for x, p in facts["documentsProcedure"] if x == l10m)],
  "DeviceManual, OperatingProcedure ⊑ RS ActionContract, OperatingSetpoint")
Q("Which manual preconditions does the twin enforce (entailed TwinEnforcedPrecondition), and how?",
  [f"{p.split('/manuals/')[1].split('/pre/')[0].replace('/procedure/', '.')}: \"{txt(p)}\" — "
   + "; ".join(txt(m) for x, m in facts["enforcedInTwinBy"] if x == p) for p in inst("TwinEnforcedPrecondition")],
  "TwinEnforcedPrecondition ≡ Precondition ⊓ ∃enforcedInTwinBy.TwinControllerCheck")
by_haz = collections.defaultdict(list)
for f_, h in facts["hasFailureConsequence"]:
    by_haz[leaf(h)].append(f_)
Q("Which device failure modes lead to which hazard (with recovery)? (counts and examples)",
  [f"{h}: {len(fs)} failure modes, e.g. {fs[0].split('/manuals/')[1].split('/')[0]}: \"{txt(fs[0])}\" → recovery "
   f"\"{txt(next(r for x, r in facts['hasRecoveryProcedure'] if x == fs[0]))}\"" for h, fs in sorted(by_haz.items())],
  "DeviceFailureMode ⊑ AICOR FailureSignature ⊓ ∃hasFailureConsequence.LabHazard ⊓ ∃hasRecoveryProcedure.(Repair)")
rules = inst("LabSafetyRule") + inst("AuthorizationNorm")
Q("Which safety rules and norms apply, which hazard do they mitigate, and are they verified in the twin?",
  [f"{leaf(r)} [{', '.join(sorted(inferred[r] & {'HumanSafetyRule', 'MachineProtectionRule', 'BiosafetyRule', 'SampleIntegrityRule', 'IdentityRule', 'MeasurementValidityRule', 'AuthorizationNorm'}))}]: "
   f"{txt(r)} — refusals verified: {sum(1 for c, x in facts['violatesRule'] if x == r)}" for r in rules],
  "LabSafetyRule ⊑ AICOR IncapabilityAssertion; AuthorizationNorm ⊑ normative-admissibility Norm")
Q("Which candidate actions are unsafe or unauthorised (entailed), who refused them, and which test shows it?",
  [f"{'UNAUTHORISED' if c in inst('UnauthorizedCandidateAction') else 'UNSAFE'}: {txt(c)} — refused by "
   f"{', '.join(leaf(d) for x, d in facts['refusedByEntity'] if x == c)} ({data[c].get('verificationTest')})"
   for c in sorted(set(inst("UnsafeCandidateAction")) | set(inst("UnauthorizedCandidateAction")))],
  "UnsafeCandidateAction ≡ CandidateAction ⊓ ∃violatesRule.LabSafetyRule; Unauthorized… ∃violatesRule.AuthorizationNorm")
arms = [(a, k) for k in ("ChallengeOnlyArm", "ChallengeRescueArm", "ControlArm") for a in inst(k)]
Q("What are the arms of the challenge-rescue study (entailed from closure axioms) and their units?",
  [f"{k}: {leaf(a)} — wells {', '.join(sorted(leaf(w) for x, w in facts['assignsUnit'] if x == a))}" for a, k in arms],
  "ChallengeOnlyArm ≡ Arm ⊓ ∃applies.ChallengeSpec ⊓ ¬∃applies.RescueSpec; ControlArm ≡ Arm ⊓ ¬∃applies.InterventionSpec")
Q("Which conclusions were withheld in which run, and why?",
  [f"{c.split('/run/')[1].split('/')[0] if '/run/' in c else 'SDT claim node ' + leaf(c)}: \"{txt(c)}\" — "
   f"{data[c].get('claimStatus')}" for c in inst("WithheldConclusion")],
  "WithheldConclusion ≡ RescueComparisonConclusion ⊓ ∃withheldBecause.WithholdingReason")
Q("Which interventions were not verified (entailed UnverifiedInterventionRecord)?",
  [f"{r.split('/run/')[1].split('/')[0] if '/run/' in r else 'SDT'}: {leaf(r.rsplit('/record', 1)[0])} "
   f"({data[r].get('doseAU')} au at {data[r].get('time_h')} h)" for r in inst("UnverifiedInterventionRecord")],
  "UnverifiedInterventionRecord ≡ InterventionRecord ⊓ ∃isCommittedEvent.{false}")
Q("Which actions were sample-AMR transfers, and which records are blocked by failed monitors?",
  [f"AMR transfer: {a.split('/actions/')[1]}" for a in inst("AMRTransferAction")] +
  [f"blocked: {r.split('/records/')[1]} — " + ", ".join(data[m].get("monitorName", "?") for x, m in
                                                         facts["hasMonitorResult"] if x == r and
                                                         data[m].get("monitorPassed") == "false")
   for r in inst("BlockedActionRecord")],
  "AMRTransferAction ≡ TransferAction ⊓ ∃hasParticipantEntity.SampleTransportAMR; BlockedActionRecord ≡ …")
down = collections.defaultdict(set)
for p_ in ("hasDirectComponent", "hasPhysicalPart", "hasSubPlace"):
    for x, y in facts[p_]:
        down[x].add(y)
for p_ in ("isDirectComponentOf", "isPhysicalPartOf", "isSubPlaceOf"):
    for x, y in facts[p_]:
        down[y].add(x)


def closure(x):
    seen, stack = {x}, [x]
    while stack:
        y = stack.pop()
        for z in list(down[y]) + list(same[y]):
            for v in [z] + list(same[z]):
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
    return seen - {x}


l10 = closure(f"{W}/Cell01/Stations/L10_Incubator#entity")
Q("What are the physical parts of L10 (hasPhysicalPart: transitive closure of hasDirectComponent)?",
  [f"{len(l10)} parts: " + ", ".join(sorted({leaf(p) for p in l10})[:18]) + " ..."],
  "hasDirectComponent ⊑ hasPhysicalPart (transitive) ⊑ AICOR hasPart")
nodes = inst("LabSDTNode")
Q("How are the SDT's nodes typed (node vs referent), and what does the reasoner add?",
  [f"{len(nodes)} SDT nodes (AICOR SceneNode / LabSDTNode); {sum(1 for x, y in facts['representsEntity'])} represent a "
   f"referent; referents with entailed (unasserted) module types: "
   f"{sum(1 for x, y in facts['representsEntity'] if (inferred.get(y, set()) & OWN) - asserted[y] - {'LabArtifact'})} "
   f"(beyond LabArtifact); entailed module-type assertions on referents: "
   f"{sum(len((inferred.get(y, set()) & OWN) - asserted[y]) for x, y in facts['representsEntity'])}"],
  "LabSDTNode ⊑ SceneNode ⊓ ∃representsEntity.Entity; nodes are information, referents physical / abstract")

if "rsa_trail" in ABOXES:
    RSA_N = "https://aicor.example/okf/lab1/rsa/run/"
    import yaml as _yaml
    _cards = _yaml.safe_load(open(os.path.join(HERE, "..", "..", "rsa", "registry", "categories.yaml")))
    _cls = {"".join(w[:1].upper() + w[1:] for w in c.split("_")) + ("Command" if v["level"] == "command" else
            "Designator"): c for c, v in _cards.items() if v["level"] != "motion"}
    _des = {x for x, cs in inferred.items() if x.startswith(RSA_N) and "/designator/" in x}
    _by = collections.Counter(_cls[c] for x in _des for c in inferred.get(x, set()) & set(_cls))
    _eff = collections.Counter(c for x in _des for c in inferred.get(x, set()) if c.endswith("Designator") and c[:-10] in
                               ("ObjectDisplacement", "ConfigurationChange", "SubstanceManipulation", "ConnectingAction",
                                "Perception", "MaintenanceAction", "RegulationAction"))
    _ents = {x for x, cs in inferred.items() if x.startswith(RSA_N) and "CommitmentAuditEntry" in cs}
    _viol = {x for x, cs in inferred.items() if x.startswith(RSA_N) and "ViolationAuditEntry" in cs}
    _unclassified = sorted(x.rsplit("/", 1)[-1] for x in _des if not (inferred.get(x, set()) & (set(_cls) | {
        "ApproachMotion", "InsertMotion", "GraspMotion", "LiftMotion", "TransitMotion", "PlaceMotion",
        "ReleaseMotion", "RetractMotion", "ToolCoupleMotion"})))
    Q("Into which action-designator categories and effect classes does the reasoner classify the designators of the "
      "kernel's audit trail, and does the trail record any constraint violation?",
      [f"{len(_des)} designators, {len(_ents)} audit entries, {len(_viol)} violation entries (entailed "
       f"ViolationAuditEntry); unclassified: {_unclassified or 'none'}",
       "categories (entailed from level + kernelCategory): " + ", ".join(f"{k} {n}" for k, n in sorted(_by.items())),
       "effect classes (entailed via the categories): " + ", ".join(f"{k[:-10]} {n}" for k, n in sorted(_eff.items()))],
      "XCategory ≡ Level ⊓ ∃kernelCategory.{x} (generated from rsa/registry/categories.yaml); "
      "ViolationAuditEntry ≡ CommitmentAuditEntry ⊓ ∃violatesConstraint.KernelConstraint")

if "plan" in ABOXES:
    E2M = "https://aicor.example/okf/lab1/e2m"
    sel = inst("SelectedExperiment")
    req = f"{E2M}/requirement"
    Q("Which experiment is selected for the required information gain (entailed SelectedExperiment), with which "
      "expected gain and cost, among how many candidates?",
      [f"requirement {data[req].get('requiredGain_bits')} bits; {len(inst('ExperimentCandidate'))} candidates; "
       f"selected (entailed): " + ", ".join(
           f"{leaf(c)} — dose {data[c].get('doseAU')} au, rescue delay {data[c].get('rescueDelay_h')} h, "
           f"{data[c].get('replicateCount')} replicate(s), EIG {data[c].get('expectedGain_bits')} bits, "
           f"cost {data[c].get('planCost')}" for c in sel)],
      "SelectedExperiment ≡ ExperimentCandidate ⊓ ∃selectedUnder.InformationGainRequirement (E2M1 in derive_plan.py)")
    by_sess = collections.defaultdict(collections.Counter)
    for x, d in facts["hasStep"]:
        for c in sorted(inferred.get(d, set()) & {"ApproachMotion", "InsertMotion", "GraspMotion", "LiftMotion",
                                                  "TransitMotion", "PlaceMotion", "ReleaseMotion", "RetractMotion",
                                                  "ToolCoupleMotion", "SafetyStepDesignator", "ChallengeDoseDesignator",
                                                  "RescueDoseDesignator", "ImageWellDesignator"}):
            by_sess[leaf(x)][c] += 1
        if "DeviceCommandDesignator" in inferred.get(d, set()) and "SafetyStepDesignator" not in inferred.get(d, set()):
            by_sess[leaf(x)]["DeviceCommandDesignator"] += 1
    robots = collections.defaultdict(set)
    for d, r in facts["performedByRobot"]:
        robots[d.split("/step/")[0].split("/transfer/")[0].rsplit("/", 1)[-1]].add(leaf(r))
    Q("Which material, motion and device-command designators realise the selected experiment, per session, and "
      "which robots perform them?",
      [f"{s_} at {data[f'{E2M}/session/{s_}'].get('scheduledAt_h')} h: " + ", ".join(f"{n} {c}" for c, n in
                                                                                     sorted(cnt.items()))
       + f" — robots {', '.join(sorted(robots[s_]))}" for s_, cnt in sorted(by_sess.items())],
      "MotionStepDesignator ⊑ RS BodyMotionDesignator; PlateTransferDesignator ⊑ ∃performedByRobot.CellRobot")
    dis = collections.Counter(leaf(r) for d, r in facts["dischargesRule"])
    rg = inst("RealisedInformationGain")
    Q("Which safety rules do the derived steps discharge, and what gain did the executed plan realise?",
      [f"{r}: discharged by {n} step(s) — {txt(f'https://aicor.example/okf/lab1/safety/rule/{r}')}"
       for r, n in sorted(dis.items())]
      + [f"realised gain {data[g].get('realisedGain_bits')} bits (KL posterior ‖ prior over M1-M3) in the twin's "
         f"execution" for g in rg],
      "SafetyStepDesignator ⊑ ∃dischargesRule.LabSafetyRule; RealisedInformationGain ⊑ ∃about.ExperimentRealisationPlan")

md = ["# Competency questions, answered from the reasoned module + SDT", "",
      f"Generated by `check_module.py`: Konclude over TBox + ABoxes ({', '.join(ABOXES)}) + upstream union; "
      f"consistent; unsatisfiable module concepts: {len(unsat_own)}; negative controls: "
      f"{sum(n['inconsistent_as_required'] for n in neg_results)}/{len(neg_results)} inconsistent as required.", ""]
for q, lines, how in CQ:
    md += [f"## {q}", "", f"*{how}*", ""] + [f"- {x}" for x in lines] + [""]
os.makedirs(DOCS, exist_ok=True)
open(os.path.join(DOCS, "competency_questions.md"), "w").write("\n".join(md) + "\n")

# ---------------------------------------------------------------------------------------------- 4c instance partonomy
children = collections.defaultdict(list)
for x, y in facts["isSubPlaceOf"]:
    children[y].append(("⊂ sub-place", x))
for x, y in facts["locatedAt"]:
    children[y].append(("@ located", x))
for x, y in facts["comprisesCell"]:
    children[x].append(("◆ cell", y))
for x, y in facts["hasDirectComponent"]:
    children[x].append(("◆ component", y))
for x, y in facts["containsMaterial"]:
    children[x].append(("◇ contains", y))
poses = collections.Counter(x for x, y in facts["hasInteractionPose"])
lines, seen = [], set()


def tname(i):
    """The most specific asserted type (asserted types are the mapping's most specific choice), else an inferred one."""
    a = sorted(asserted.get(i, set()) - {"LabArtifact"})
    if a:
        return a[0]
    t = [c for c in sorted(inferred.get(i, ())) if c in OWN]
    return t[-1] if t else "?"


def walk(i, d, how):
    tag = f"{how} " if how else ""
    if i in seen:
        lines.append("    " * d + f"{tag}{leaf(i)} (see above)")
        return
    seen.add(i)
    pz = f"  [{poses[i]} poses]" if poses[i] else ""
    lines.append("    " * d + f"{tag}{leaf(i)} :{tname(i)}{pz}")
    order = {"⊂ sub-place": 0, "@ located": 1, "◆ cell": 2, "◆ component": 3, "◇ contains": 4}
    for h, c in sorted(children[i], key=lambda x: (order[x[0]], leaf(x[1]))):
        walk(c, d + 1, h)


walk(f"{SDT}/premises", 0, "")
walk(f"{W}/AICOR_Lab#entity", 0, "")
open(os.path.join(DOCS, "partonomy_lab1.md"), "w").write(
    "# Partonomy of AICOR Lab 1 (instances: the SDT's referents)\n\nGenerated by `check_module.py`. `⊂` sub-place "
    "(`hasSubPlace`), `@` location (`locatedAt`, not parthood), `◆` component (`hasDirectComponent` ⊑ "
    "`hasPhysicalPart` ⊑ AICOR `hasPart`; `comprisesCell` from the robot-scientist vertical), `◇` containment "
    "(`containsMaterial`, not parthood); `[n poses]` = interaction poses of the node.\n\n```text\n" +
    "\n".join(lines) + "\n```\n")
cell = f"{W}/Cell01#entity"
dot = ["digraph cell01 {", 'rankdir=LR; nodesep=0.1; ranksep=0.45; node [shape=box, style="rounded,filled", '
       'fontname="Helvetica", fontsize=9, fillcolor="#eef3fb", color="#4a6fa5"]; edge [color="#2b6cb0", arrowsize=0.5];']
q_, done = [(cell, 0)], set()
while q_:
    i, d = q_.pop(0)
    if i in done or d > 3:
        continue
    done.add(i)
    t = tname(i)
    fill = "#fde2e2" if "Robot" in t or "Manipulator" in t or "AMR" in t else ("#e6f4ea" if "Sensor" in t else "#eef3fb")
    dot.append(f'"{i}" [label="{leaf(i)}\\n:{t}", fillcolor="{fill}"];')
    for h, c in children[i]:
        if "MechanismJoint" in inferred.get(c, set()):
            continue
        dot.append(f'"{i}" -> "{c}";')
        dot.append(f'"{c}" [label="{leaf(c)}\\n:{tname(c)}"];')
        q_.append((c, d + 1))
dot.append("}")
dp = os.path.join(DOCS, "partonomy_cell01.dot")
open(dp, "w").write("\n".join(dot) + "\n")
for fmt in ("svg", "png"):
    run(["dot", f"-T{fmt}", "-Gdpi=90", dp, "-o", dp.replace(".dot", f".{fmt}")])

# ---------------------------------------------------------------------------------------------- report
os.makedirs(OUT, exist_ok=True)
own_inferred = collections.Counter(c for i, t in inferred.items() for c in t if c in OWN)
report = {"reasoner": "Konclude v0.7.0-1138 (SROIQV(D))", "consistent": consistent, "class_assertions": n_ca,
          "timing_s": {"consistency": round(t_c, 2), "classification": round(t_k, 2), "realisation": round(t_r, 2)},
          "unsatisfiable_total": len(unsat), "unsatisfiable_module_concepts": [u.split("#")[-1] for u in unsat_own],
          "negative_controls": neg_results, "individuals_realised": len(inferred), "sdt_nodes": len(nodes),
          "usd_nodes_with_inferred_types": n_usd, "competency_questions": len(CQ),
          "module_concept_instances": dict(own_inferred.most_common())}
json.dump(report, open(os.path.join(OUT, "check-report.json"), "w"), indent=1)
ok = consistent and not unsat_own and all(n["inconsistent_as_required"] for n in neg_results)
print(f"[check] {len(inferred)} individuals realised; inferred types on {n_usd} USD nodes; {len(CQ)} competency "
      f"questions -> docs/competency_questions.md; partonomy {len(seen)} nodes -> {'PASS' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
