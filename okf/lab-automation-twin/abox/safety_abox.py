"""Safe-action knowledge -> ABox: lab safety rules, their sources, enforcement in the twin, verification, refusals.

Each rule (curated below from Cell 01's sources and the twin's implementation) becomes a LabSafetyRule (AICOR
IncapabilityAssertion) or an AuthorizationNorm (normative-admissibility Norm) with
  statementText, mitigatesHazard, prohibitsTaskType            the rule
  derivedFromSource -> source document individual (+ locator)  Cell 01 spec / contract / rule file
  enforcedBy -> mechanism (physical interlock / controller check / critic gate) realisedByDevice -> device referent
  verificationTest + RefusedCommand individuals                one per verifying test check, ONLY if the test report
                                                               records it as passed (read from test_reports/)
  enforcedInTwinBy on the manual preconditions it enforces    (TwinEnforcedPrecondition by definition)
Run: env_cad/bin/python okf/lab-automation-twin/abox/safety_abox.py   (after manuals_abox.py)
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(MOD))
sys.path.insert(0, os.path.join(MOD, "src"))
from dl import PREFIXES  # noqa: E402

SDT = "https://aicor.example/okf/sdt/lab1"
S = "https://aicor.example/okf/lab1/safety"
M = "https://aicor.example/okf/lab1/manuals"
HAZ = "https://aicor.example/okf/lab1/hazards"
TASKS = f"{SDT}/tasktypes"
C01 = "/World/Cell01"
H = "projects/robot-scientist/cell-01/AICOR_Cell01_Codex_Handoff"
SOURCES = {
    "spec": ("AICOR_Cell01_Complete_Design_and_Implementation_Specification.pdf", f"{H}/../simulation/isaac_sim/"
             "design_package/AICOR_Cell01_Complete_Design_and_Implementation_Specification.pdf"),
    "critic": ("Cell 01 critic vector schema", f"{H}/sdt/schemas/critic_vector_schema.yaml"),
    "monrules": ("Cell 01 biology monitoring rules", f"{H}/biology/ontology/monitoring-rules.yaml"),
    "asepsis": ("Cell 01 contamination and asepsis logic", f"{H}/biology/ontology/contamination-and-asepsis.md"),
    "site": ("Site layout proposal S1 (this project)", "LabAutomationTwin/proposals/site/README.md"),
}
for cid in ("L09", "L10", "L12", "L17", "L21", "H4", "R01", "R02", "R03_H2", "TCM01"):
    SOURCES[f"contract:{cid}"] = (f"Cell 01 component contract {cid}", f"{M}/{cid}")

# id, class, hazard, prohibited task, statement, [(source, locator)], [(mechanism class, device prim, how)],
# [(test script, check prefix, report json, refused device prim, refusal)], [(component, procedure, precondition#)]
RULES = [
    ("enclosure_door_interlock", "HumanSafetyRule", "HumanInjuryHazard", "PlateTransferTask",
     "No robot motion inside the enclosure while an enclosure door is open.",
     [("spec", "§4.1 safety enclosure: interlocked doors"), ("contract:R01", "constraints: no motion in interlocked "
                                                                             "human-access state")],
     [("PhysicalInterlockMechanism", f"{C01}/Architecture/Enclosure_E01/Doors/D1_Front",
       "twin/site_doors.py Interlock: door open -> safe motion withheld")],
     [("scripts/test_site_route.py", "F2 front door D1 opened", "site_route_report.json",
       f"{C01}/Architecture/Enclosure_E01", "safe motion withheld while D1_Front open")], []),
    ("portal_light_curtain", "HumanSafetyRule", "HumanInjuryHazard", "NavigationTask",
     "The AMR portal admits only the sample AMR (muted passage); any other object breaking the curtain latches a "
     "protective stop that cannot be reset while broken.",
     [("spec", "§4.1 AMR portal"), ("site", "light curtain, muting")],
     [("PhysicalInterlockMechanism", f"{C01}/Architecture/Enclosure_E01/amr_portal",
       "twin/site_doors.py LightCurtain: muting accepts only R03")],
     [("scripts/test_site_route.py", "F1 person proxy breaks the curtain", "site_route_report.json",
       f"{C01}/Architecture/Enclosure_E01/amr_portal", "protective stop latched; reset refused while broken")], []),
    ("emergency_stop", "HumanSafetyRule", "HumanInjuryHazard", "PlateTransferTask",
     "An actuated emergency stop halts all motion until reset.",
     [("spec", "§4.1 emergency stops")],
     [("PhysicalInterlockMechanism", f"{C01}/Architecture/Enclosure_E01/estop_front_left", "enclosure e-stops")],
     [], []),
    ("l12_deck_airspace", "MachineProtectionRule", "CollisionHazard", "LiquidDispensingTask",
     "L12 must not dose while a robot is in its deck airspace.",
     [("contract:L12", "constraints / risk controls")],
     [("ControllerInterlockMechanism", f"{C01}/Stations/L12_LiquidHandler",
       "L12 controller refuses dose: deck_airspace_occupied")],
     [("scripts/test_l12_robot.py", "R3b dose refused", "l12_robot_report.json", f"{C01}/Stations/L12_LiquidHandler",
       "deck_airspace_occupied")], []),
    ("amr_cabinet_closed", "SampleIntegrityRule", "ContaminationHazard", "NavigationTask",
     "The AMR moves only with its sample cabinet closed; the cabinet opens only when docked.",
     [("contract:R03_H2", "constraints: cabinet closed during transport")],
     [("ControllerInterlockMechanism", f"{C01}/Robots/R03_SampleAMR",
       "R03 controller: navigate refused with cabinet open; fault cabinet_open_in_transit")],
     [("scripts/test_r03.py", "F2 lid opened in transit", "r03_report.json", f"{C01}/Robots/R03_SampleAMR",
       "cabinet_open_in_transit: AMR stops")], []),
    ("l10_environment_valid", "SampleIntegrityRule", "SampleIntegrityHazard", "IncubatingTask",
     "No incubation while the incubator environment is outside its valid envelope.",
     [("contract:L10", "action_contracts.incubate.preconditions: environment valid")],
     [("ControllerInterlockMechanism", f"{C01}/Stations/L10_Incubator", "L10 controller refuses incubate")],
     [("scripts/test_l10_physics.py", "T6 incubate refused while environment invalid", "l10_physics_report.json",
       f"{C01}/Stations/L10_Incubator", "environment invalid")], [("L10", "incubate", 2)]),
    ("l09_transfer_nest_clear", "MachineProtectionRule", "CollisionHazard", "PlateRetrievingTask",
     "No plate is presented onto an occupied transfer nest.",
     [("contract:L09", "action_contracts.retrieve_plate.preconditions: transfer nest empty")],
     [("ControllerInterlockMechanism", f"{C01}/Stations/L09_PlateHotel", "L09 controller refuses retrieve")],
     [("scripts/test_l09_physics.py", "T8 retrieve refused", "l09_physics_report.json",
       f"{C01}/Stations/L09_PlateHotel", "transfer nest not clear")], [("L09", "retrieve_plate", 1)]),
    ("l09_slot_free", "MachineProtectionRule", "CollisionHazard", "PlateStoringTask",
     "No plate is stored into an occupied slot.",
     [("contract:L09", "action_contracts.store_plate.preconditions: slot reserved and empty")],
     [("ControllerInterlockMechanism", f"{C01}/Stations/L09_PlateHotel", "L09 controller refuses double occupancy")],
     [("scripts/test_l09_physics.py", "T6 double occupancy refused", "l09_physics_report.json",
       f"{C01}/Stations/L09_PlateHotel", "slot occupied")], [("L09", "store_plate", 1)]),
    ("l17_plate_seated", "MachineProtectionRule", "CollisionHazard", "ImagingTask",
     "L17 loads a plate only when it is seated in the stage nest.",
     [("contract:L17", "action_contracts.image_well.preconditions: plate verified and seated")],
     [("ControllerInterlockMechanism", f"{C01}/Stations/L17_BrightFieldImager", "L17 refuses load_plate")],
     [("scripts/test_l17_physics.py", "T3 misseated plate", "l17_physics_report.json",
       f"{C01}/Stations/L17_BrightFieldImager", "plate_misseated")], [("L17", "image_well", 0)]),
    ("l17_calibration_valid", "MeasurementValidityRule", "MeasurementValidityHazard", "ImagingTask",
     "No image is acquired as evidence with an expired or invalidated calibration.",
     [("contract:L17", "action_contracts.image_well.preconditions: calibration valid"),
      ("monrules", "evidence_promotion.requires: calibration_valid")],
     [("ControllerInterlockMechanism", f"{C01}/Stations/L17_BrightFieldImager", "L17 refuses image_well")],
     [("scripts/test_l17_physics.py", "T10 calibration expired", "l17_physics_report.json",
       f"{C01}/Stations/L17_BrightFieldImager", "calibration expired"),
      ("scripts/test_l21.py", "Q7 LED at 60 %", "l21_report.json", f"{C01}/Stations/L17_BrightFieldImager",
       "calibration_invalidated by QC: L17 blocked")], [("L17", "image_well", 2)]),
    ("l21_reference_valid", "MeasurementValidityRule", "MeasurementValidityHazard", "CalibratingTask",
     "No validation against a missing or expired reference artifact.",
     [("contract:L21", "action_contracts.validate_measurement_chain.preconditions: reference artifact valid")],
     [("ControllerInterlockMechanism", f"{C01}/Stations/L21_QC_Calibration", "L21 refuses validate_imager")],
     [("scripts/test_l21.py", "Q8 expired reference artifact", "l21_report.json",
       f"{C01}/Stations/L21_QC_Calibration", "reference artifact expired")],
     [("L21", "validate_measurement_chain", 0)]),
    ("r02_rail_homed", "MachineProtectionRule", "CollisionHazard", "PlateTransferTask",
     "The rail moves only after homing and within its soft limits.",
     [("contract:R02", "action_contracts.position_for_station.preconditions: rail homed")],
     [("ControllerInterlockMechanism", f"{C01}/Robots/R02_RailSystem", "R02 controller refuses rail commands")],
     [("scripts/test_r02.py", "R1 rail command refused before homing", "r02_report.json",
       f"{C01}/Robots/R02_RailSystem", "not homed")], [("R02", "position_for_station", 0)]),
    ("tool_contamination_compatible", "BiosafetyRule", "ContaminationHazard", "ToolExchangeTask",
     "A tool may contact a culture or reagent only if its contamination class is compatible; automatic tool change "
     "does not itself guarantee cleanliness.",
     [("asepsis", "Tool-state rule"), ("contract:TCM01", "action_contracts.change_tool.preconditions")],
     [("ControllerInterlockMechanism", f"{C01}/Tooling/AutomaticToolChanger", "tool changer refuses the tool")],
     [("scripts/test_r02.py", "T5 contamination-incompatible tool refused", "r02_report.json",
       f"{C01}/Tooling/AutomaticToolChanger", "contamination-incompatible tool")], [("TCM01", "change_tool", 0)]),
    ("contamination_suspected_blocks", "BiosafetyRule", "ContaminationHazard", "LiquidDispensingTask",
     "When contamination is suspected: block evidence promotion, quarantine affected material, compute the exposure "
     "graph, test, notify.",
     [("monrules", "contamination_suspected"), ("asepsis", "Suspected contamination response")],
     [("CriticGateMechanism", None, "culture SDT: haze flag -> contamination_suspected, claims withheld")],
     [], []),
    ("challenge_requires_controls", "SampleIntegrityRule", "SampleIntegrityHazard", "ChallengeDosingTask",
     "A challenge is authorised only with verified target and reagent identity, clean compatible tool, specified dose "
     "and timing, a control structure, monitoring and evidence plans, and valid containment.",
     [("monrules", "challenge_authorization")],
     [("CriticGateMechanism", None, "Cell 01 ledger commits a dose only with a valid L12 record")], [], []),
    ("commit_requires_safety", "SampleIntegrityRule", "SampleIntegrityHazard", "PlateTransferTask",
     "An action's semantic event commits only if grounding, safety, quality, experimental validity and evidence are "
     "all satisfied (safety_ok covers safety, sterility, contamination, identity, hazardous states).",
     [("critic", "invariants: commit_semantic_event requires ...")],
     [("CriticGateMechanism", None, "twin/episode_records.py critic vector -> routing")], [], []),
    ("identity_verified", "IdentityRule", "IdentityHazard", "PlateRetrievingTask",
     "A plate is released / incubated / dosed only with verified identity; a mismatch routes it to quarantine.",
     [("contract:L10", "release_plate.preconditions: identity consistent"),
      ("contract:L12", "dose_well.preconditions: plate ID verified")],
     [("ControllerInterlockMechanism", f"{C01}/Stations/L10_Incubator", "L10 barcode re-read at release")],
     [], [("L10", "incubate", 0), ("L10", "release_plate", 1)]),
    ("h4_door_vs_shuttle", "MachineProtectionRule", "CollisionHazard", "QuarantiningTask",
     "H4's door cannot close onto a presented shuttle.",
     [("contract:H4", "risk controls")],
     [("ControllerInterlockMechanism", f"{C01}/Stations/H4_Quarantine", "H4 controller")],
     [("scripts/test_h4_physics.py", "T4 door cannot close", "h4_physics_report.json",
       f"{C01}/Stations/H4_Quarantine", "shuttle presented")], []),
    ("h4_orientation_key", "IdentityRule", "IdentityHazard", "QuarantiningTask",
     "A rotated plate (A1 key not matched) is not quarantined as if correctly seated.",
     [("contract:H4", "quarantine_sample")],
     [("ControllerInterlockMechanism", f"{C01}/Stations/H4_Quarantine", "seat sensors + A1 key")],
     [("scripts/test_h4_physics.py", "T7 rotated plate", "h4_physics_report.json", f"{C01}/Stations/H4_Quarantine",
       "rotated plate")], []),
]
NORMS = [
    ("h4_release_authorization", "QuarantineReleaseTask",
     "A quarantined plate is released only with a QA authorisation token and the operator's key switch.",
     [("contract:H4", "release_by_authorization"), ("monrules", "block_and_escalate")],
     [("ControllerInterlockMechanism", f"{C01}/Stations/H4_Quarantine", "H4 controller: token + key")],
     [("scripts/test_h4_physics.py", "T11 release refused without token", "h4_physics_report.json",
       f"{C01}/Stations/H4_Quarantine", "no token / key")]),
    ("rescue_authorization", "RescueDosingTask",
     "A rescue is authorised only when linked to its preceding challenge, with verified identities, known elapsed "
     "time, a clean tool and defined success criteria.",
     [("monrules", "rescue_authorization")],
     [("CriticGateMechanism", None, "Cell 01 rules: block_and_escalate")], []),
]

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
    A.append(f'DataPropertyAssertion(:{p} <{a}> "{str(v).replace(chr(34), chr(39))}"^^{dt})')


def ref(path):
    return f"{SDT}{path}#entity"


def test_passed(report, check):
    """Pass status of the test whose name starts with `check`, from its report; None if absent."""
    p = os.path.join(REPO, "test_reports", report)
    if not os.path.exists(p):
        return None
    for r in json.load(open(p)).get("results", []):
        if str(r.get("test", "")).lower().startswith(check.lower()):
            return bool(r.get("pass"))
    return None


def source(key, loc, rule):
    name, path = SOURCES[key]
    if key.startswith("contract:"):
        si = path                                            # the manual individual itself
    else:
        si = f"{S}/source/{key}"
        Ty(si, "SafetySourceDocument")
        Dv("sourceDocument", si, path)
        Dv("canonicalName", si, name)
    R("derivedFromSource", rule, si)
    Dv("sourceLocator", rule, f"{key}: {loc}")


stats = {"rules": 0, "norms": 0, "mechanisms": 0, "verified_refusals": 0, "unverified_checks": 0,
         "enforced_preconditions": 0}
for hz in ("HumanInjuryHazard", "CollisionHazard", "ContaminationHazard", "SampleIntegrityHazard", "IdentityHazard",
           "MeasurementValidityHazard"):
    Ty(f"{HAZ}/{hz}", hz)
for t in {r[3] for r in RULES} | {n[1] for n in NORMS}:
    Ty(f"{TASKS}/{t}", t)


def mechanisms_and_tests(rid, rule, mechs, tests, is_norm=False):
    for k, (mcls, dev, how) in enumerate(mechs):
        mi = f"{rule}/mechanism/{k}"
        Ty(mi, mcls)
        Dv("statementText", mi, how)
        R("enforces", mi, rule)
        R("enforcedBy", rule, mi)
        if dev:
            R("realizedByDevice", mi, ref(dev))
        stats["mechanisms"] += 1
        for script, check, rep, rdev, why in tests:
            ti = f"{S}/test/{re.sub(r'[^A-Za-z0-9]+', '_', script + '_' + check.split()[0])}"
            ok = test_passed(rep, check)
            if ok:
                Ty(ti, "TwinVerificationTest")
                Dv("verificationTest", ti, f"{script} {check}")
                if mcls == "ControllerInterlockMechanism":
                    R("exercisedByTest", mi, ti)
    for script, check, rep, rdev, why in tests:
        ok = test_passed(rep, check)
        if not ok:
            stats["unverified_checks"] += 1
            continue
        ci = f"{rule}/refused/{re.sub(r'[^A-Za-z0-9]+', '_', check.split()[0])}"
        Ty(ci, "RefusedCommand")
        R("violatesRule", ci, rule)
        R("refusedByEntity", ci, ref(rdev))
        Dv("verificationTest", ci, f"{script} :: {check}")
        Dv("statementText", ci, why)
        stats["verified_refusals"] += 1


for rid, cls, hz, task, text, srcs, mechs, tests, pres in RULES:
    rule = f"{S}/rule/{rid}"
    Ty(rule, cls)
    Dv("statementText", rule, text)
    R("mitigatesHazard", rule, f"{HAZ}/{hz}")
    R("prohibitsTaskType", rule, f"{TASKS}/{task}")
    for key, loc in srcs:
        source(key, loc, rule)
    mechanisms_and_tests(rid, rule, mechs, tests)
    for cid, proc, k in pres:
        pc = f"{M}/{cid}/procedure/{proc}/pre/{k:02d}"
        for mi in [f"{rule}/mechanism/{j}" for j, m in enumerate(mechs) if m[0] == "ControllerInterlockMechanism"]:
            R("enforcedInTwinBy", pc, mi)
            stats["enforced_preconditions"] += 1
    stats["rules"] += 1
for rid, task, text, srcs, mechs, tests in NORMS:
    norm = f"{S}/norm/{rid}"
    Ty(norm, "AuthorizationNorm")
    Dv("statementText", norm, text)
    R("prohibitsTaskType", norm, f"{TASKS}/{task}")
    for key, loc in srcs:
        source(key, loc, norm)
    mechanisms_and_tests(rid, norm, mechs, tests, True)
    stats["norms"] += 1
hdr = [f"Prefix({k}:=<{v}>)" for k, v in PREFIXES.items()]
hdr += ["", "Ontology(<https://aicor.example/okf/sdt/lab1/abox/safety>",
        "Import(<http://aicor.knowledge/okf/lab-automation-twin>)",
        'Annotation(rdfs:comment "Lab safety rules and authorisation norms with sources, twin enforcement and '
        'verified refusals.")']
open(os.path.join(HERE, "safety.ofn"), "w").write("\n".join(hdr + A + [")"]) + "\n")
json.dump(stats, open(os.path.join(HERE, "safety_stats.json"), "w"), indent=1)
print("[safety-abox]", ", ".join(f"{k} {v}" for k, v in stats.items()))
