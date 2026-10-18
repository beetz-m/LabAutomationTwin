"""Generate the OKF packaging of the lab-automation-twin module from src/tbox.py (AICOR federation conventions).

  L1-okf-knowledge-base/bundle/{index.md, log.md, concepts/<concept>.md}   one card per L2 concept (modality-tagged)
  aicor-imports.yaml        every L1 concept classified exactly once: grounds (upstream L2 classes it specialises,
                            AICOR / robot-scientist / VRB / normative-admissibility) | divergence (register tag) |
                            out-of-scope (named reason)
  DEFERRED-REGISTER.md      the divergences and tooling findings, with evidence
  L2-conceptual-framework/competency-questions.{yaml,md}   executable CQs for ResearchSpace tools/okf_cq.py
Run: env_cad/bin/python okf/lab-automation-twin/package_okf.py
"""

import collections
import json
import os
import re
import sys
from datetime import date

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))
import tbox  # noqa: E402

TODAY = date.today().isoformat()
BUNDLE = os.path.join(HERE, "L1-okf-knowledge-base", "bundle")
CONCEPTS = os.path.join(BUNDLE, "concepts")
UP = {l.strip() for l in open(os.path.join(HERE, "build", "upstream-names.txt")) if l.strip()}
OWN = {c["name"]: c for c in tbox.CLASSES}
H = "ResearchSpace/projects/robot-scientist/cell-01/AICOR_Cell01_Codex_Handoff"
MODULE_SOURCES = {
    "lab-twin-core": [f"{H}/sdt/ontology/cell01_components.ttl", "LabAutomationTwin/scenes/lab_twin.usda"],
    "lab-twin-site": ["LabAutomationTwin/proposals/site/README.md", "LabAutomationTwin/assets/cell01_fitout/README.md",
                      f"{H}/../simulation/isaac_sim/design_package/AICOR_Cell01_Complete_Design_and_Implementation_"
                      "Specification.pdf"],
    "lab-twin-devices": [f"{H}/sdt/components/", "LabAutomationTwin/assets/ (station builders)"],
    "lab-twin-robots": [f"{H}/sdt/components/R01_FR3_PlateArm.yaml", f"{H}/sdt/components/R02_RailMounted_UR5e.yaml",
                        f"{H}/sdt/components/R03_AMR_H2_Dock.yaml", f"{H}/sdt/components/ToolChanger_Magazine.yaml"],
    "lab-twin-labware": [f"{H}/biology/ontology/aicor-biology.ttl", "LabAutomationTwin/twin/culture/README.md"],
    "lab-twin-poses": [f"{H}/sdt/components/ (reference_frames)", "LabAutomationTwin/scenes/lab_twin.usda"],
    "lab-twin-tasks": [f"{H}/sdt/schemas/cram_designator_schemas.yaml"],
    "lab-twin-device-manuals": [f"{H}/sdt/components/*.yaml"],
    "lab-twin-safe-action": [f"{H}/sdt/schemas/critic_vector_schema.yaml", f"{H}/biology/ontology/monitoring-rules.yaml",
                             f"{H}/biology/ontology/contamination-and-asepsis.md",
                             "LabAutomationTwin/twin/site_doors.py", "LabAutomationTwin/scripts/test_*.py"],
    "lab-twin-culture-experiments": [f"{H}/biology/ontology/challenge-rescue.md",
                                     f"{H}/../simulation/isaac_sim/biophysical_v2/isaac_sim_biological_runtime.py",
                                     "LabAutomationTwin/twin/culture/"],
    "lab-twin-records": [f"{H}/sdt/schemas/neem_record_schema.yaml", "LabAutomationTwin/twin/episode_records.py"],
    "lab-twin-experiment-to-motion": [f"{H}/biology/ontology/mathematical-models.md",
                                      "verticals/robot-scientist/okf/L3-logical-axiomatization (experiment-design, "
                                      "designator-refinement)",
                                      "L3-logical-axiomatization/axioms/experiment-to-motion-axioms.md",
                                      "LabAutomationTwin/twin/culture/eig.py"],
    "lab-twin-rsa-kernel": ["LabAutomationTwin/rsa/registry/categories.yaml",
                            "LabAutomationTwin/rsa/registry/constraints.yaml", "LabAutomationTwin/docs/rsa/KERNEL.md",
                            f"{H}/sdt/schemas/cram_designator_schemas.yaml",
                            "foundation/kb/dl-axioms/cram/ontology/action-category-dl.md",
                            "foundation/software/cram/experiments/aicorworks_reference_use_cases/common/audit.py"],
}
DIVERGENCES = {   # concept -> register tag (AICOR is about this and lacks it)
    "MechanismPart": "D-LAT-1", "MechanismJoint": "D-LAT-1", "DrivenMechanismJoint": "D-LAT-1",
    "DeviceSensor": "D-LAT-1", "Actuator": "D-LAT-1",
    "LabPremises": "D-LAT-5", "LabRoom": "D-LAT-5", "LabZone": "D-LAT-5", "dul:PhysicalPlace": "D-LAT-5",
    "LabHazard": "D-LAT-6",
}
OUT_OF_SCOPE = {   # concept -> reason key
    "PottedPlant": "reason-furnishings", "Whiteboard": "reason-furnishings", "LabStool": "reason-furnishings",
    "LabCoatRack": "reason-furnishings", "GloveDispenser": "reason-furnishings", "PPEStation": "reason-furnishings",
    "HVACDiffuser": "reason-building-services", "CeilingLuminaire": "reason-building-services",
    "ServerRack": "reason-building-services", "BuildingServiceDevice": "reason-building-services",
    "SprinklerHead": "reason-building-services", "SmokeDetector": "reason-building-services",
    "FireExtinguisher": "reason-building-services", "FireSafetyDevice": "reason-building-services",
    "FirstAidBox": "reason-building-services",
}
REASONS = {
    "reason-furnishings": "Furnishings and decor of the lab twin: modelled so every SDT node has a referent; AICOR's "
                          "subject (embodied manipulation, its evidence and claims) does not lack them.",
    "reason-building-services": "Building services and fire safety: facility management, not manipulation; AICOR does "
                                "not lack them. Kept for the twin's completeness and the site checks.",
}


def kebab(n):
    n = n.replace("dul:", "dul-").replace("soma:", "soma-")
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "-", n).lower()


def upstream_grounds(c, seen=None):
    """Nearest upstream (non-module) superclasses of a module concept."""
    seen = seen or set()
    out = []
    for s in c["sup"]:
        if s in seen:
            continue
        seen.add(s)
        if s in OWN and ":" not in s:
            out += upstream_grounds(OWN[s], seen)
        elif s.startswith(("dul:", "soma:")):
            out.append(s.replace(":", "_"))          # AICOR's own upper-level stand-in class (dul_X / soma_X)
        elif s in UP:
            out.append(s)
    return list(dict.fromkeys(out))


def main():
    os.makedirs(CONCEPTS, exist_ok=True)
    for f in os.listdir(CONCEPTS):
        os.remove(os.path.join(CONCEPTS, f))
    grounds, divergence, oos = {}, {}, collections.defaultdict(list)
    index = collections.defaultdict(list)
    for c in tbox.CLASSES:
        name, (mkey, mtitle) = c["name"], c["module"]
        slug = kebab(name)
        g = upstream_grounds(c)
        real = [x for x in g if x in UP]
        tag = "✅" if c["src"] == "✅" else "🔧"
        if name in OUT_OF_SCOPE:
            oos[OUT_OF_SCOPE[name]].append(slug)
            gl = "out of AICOR's scope (" + OUT_OF_SCOPE[name] + ")"
        elif name in DIVERGENCES or not real:
            rtag = DIVERGENCES.get(name, "D-LAT-5" if "dul_PhysicalPlace" in g else "D-LAT-1")
            divergence[slug] = dict(register=rtag, why=f"AICOR lacks the concept; grounded only on "
                                                      f"{', '.join(g) or 'nothing'} (see {rtag})")
            gl = f"DIVERGENCE {divergence[slug]['register']} — grounded only on {', '.join(g) or 'nothing upstream'}"
        else:
            grounds[slug] = real
            gl = "specialises " + ", ".join(f"`{x}`" for x in real)
        src = MODULE_SOURCES.get(mkey, [])
        md = ["---", "type: concept", f'title: "{name}"', f"description: {json.dumps(c['doc'], ensure_ascii=False)}",
              "source:"] + [f'  - "{s}"' for s in src] + [
            "maturity: L1", "status: draft", f"timestamp: {TODAY}", f"l2: {mkey}-dl.md", "---", f"# {name}", "",
            f"{tag} {c['doc']}", "",
            f"🔧 **Grounding** — {gl}. Defined in L2 [`{mkey}-dl.md`](../../../L2-conceptual-framework/ontology/"
            f"{mkey}-dl.md) ({mtitle}).", ""]
        open(os.path.join(CONCEPTS, f"{slug}.md"), "w").write("\n".join(md) + "\n")
        index[mtitle].append((name, slug, tag))
    idx = ["---", "type: index", 'title: "lab-automation-twin L1 bundle"', "---",
           "# lab-automation-twin — L1 knowledge bundle", "",
           "One card per L2 concept of the module. Modality: ✅ the concept is stated in a cited source (Cell 01 "
           "package, the twin's implementation verified by a test), 🔧 engineering inference. Grounding into the "
           "frozen AICOR hub and the robot-scientist / VRB / normative-admissibility modules is declared in "
           "`../../aicor-imports.yaml`.", ""]
    for t, items in index.items():
        idx += [f"## {t}", ""] + [f"- {tag} [{n}](concepts/{s}.md)" for n, s, tag in items] + [""]
    open(os.path.join(BUNDLE, "index.md"), "w").write("\n".join(idx) + "\n")
    open(os.path.join(BUNDLE, "log.md"), "w").write(
        "---\ntype: log\ntitle: \"lab-automation-twin log\"\n---\n# Log\n\n"
        f"- {TODAY}: module created in LabAutomationTwin (ResearchSpace is read-only for this work): lab, cell, "
        "devices, robots, labware, poses, tasks, device manuals (Cell 01 component contracts), safe action, culture "
        "experiments, records; SDT nodes as instances. Reasoned with HermiT over the union with frozen AICOR + "
        "robot-scientist + VRB + normative-admissibility (okf_reason.py), and with Konclude over the full-semantics "
        "export with all ABoxes.\n")
    imports = {"aicor_repo": "auto (../aicor -> ResearchSpace foundation/okf/aicor, frozen)",
               "upstream_l2": ["foundation/okf/aicor (frozen hub)", "verticals/robot-scientist/okf (frozen)",
                               "foundation/okf/vrb (lab-automation-device, frozen)",
                               "foundation/okf/normative-admissibility (frozen)"],
               "note": "Grounding is declared at L2: each concept names the upstream L2 classes it specialises "
                       "(checked against the compiled upstream union), because two of the upstreams are verticals.",
               "grounds": grounds,
               "divergence": divergence,
               "out-of-scope": {k: dict(reason=REASONS[k], concepts=v) for k, v in oos.items()}}
    hdr = ("# aicor-imports.yaml — every OUTWARD edge from the lab-automation-twin module into the frozen upstream.\n"
           "# Three categories (VRB convention): grounds | divergence (register tag in DEFERRED-REGISTER.md) | "
           "out-of-scope (named reason).\n# Generated by package_okf.py from src/tbox.py; checked by "
           "tools/check_aicor_imports.py.\n\n")
    open(os.path.join(HERE, "aicor-imports.yaml"), "w").write(hdr + yaml.safe_dump(imports, sort_keys=False,
                                                                                    allow_unicode=True, width=110))
    cqs = [
        ("CQ-1", "Is Cell 01's automated incubator an AICOR lab-automation device and an incubation device?",
         dict(kind="classification", **{"class": "AutomatedCO2Incubator", "subclass_of": "IncubationDevice"})),
        ("CQ-2", "Is a device manual's operating procedure an AICOR / robot-scientist action contract?",
         dict(kind="classification", **{"class": "OperatingProcedure", "subclass_of": "ActionContract"})),
        ("CQ-3", "Is a device failure mode an AICOR failure signature, recovered by a repair?",
         dict(kind="restriction", **{"class": "DeviceFailureMode", "property": "hasRecoveryProcedure",
                                     "filler": "RecoveryProcedure"})),
        ("CQ-4", "Is a recovery procedure an AICOR Repair?",
         dict(kind="classification", **{"class": "RecoveryProcedure", "subclass_of": "Repair"})),
        ("CQ-5", "Is a lab safety rule a universal prohibition (AICOR IncapabilityAssertion, a BodyWorldConstraint)?",
         dict(kind="classification", **{"class": "LabSafetyRule", "subclass_of": "BodyWorldConstraint"})),
        ("CQ-6", "Is a biosafety rule a contamination-compatibility gate on interventions?",
         dict(kind="classification", **{"class": "BiosafetyRule", "subclass_of": "ContaminationCompatibility"})),
        ("CQ-7", "Is an authorisation rule a norm rather than a causal safety prohibition?",
         dict(kind="classification", **{"class": "AuthorizationNorm", "subclass_of": "Norm",
                                        "not_subclass_of": "IncapabilityAssertion"})),
        ("CQ-8", "Can an SDT node be the physical thing it represents?",
         dict(kind="disjoint", class_a="LabSDTNode", class_b="LabArtifact")),
        ("CQ-9", "Is a culture experiment run an AICOR manipulation episode?",
         dict(kind="classification", **{"class": "CultureExperimentRun", "subclass_of": "ManipulationEpisode"})),
        ("CQ-10", "Does the challenge-rescue design include a control arm?",
         dict(kind="restriction", **{"class": "ChallengeRescueStudyDesign", "property": "hasArm",
                                     "filler": "ControlArm"})),
        ("CQ-11", "Is a station mechanism part kept apart from AICOR's robot-body link?",
         dict(kind="classification", **{"class": "MechanismPart", "subclass_of": "dul_PhysicalObject",
                                        "not_subclass_of": "Link"})),
        ("CQ-12", "Is a well's medium a biological sample contained in the well (not a part)?",
         dict(kind="restriction", **{"class": "CultureMediumPortion", "property": "isContainedIn", "filler": "Well"})),
        ("CQ-13", "Is a derived robot motion step a robot-scientist body-motion designator (the lowest refinement "
                  "level)?",
         dict(kind="classification", **{"class": "PlaceMotion", "subclass_of": "BodyMotionDesignator"})),
        ("CQ-14", "Is the plan derived for an information-gain requirement an experimental protocol, organised in "
                  "protocol sessions?",
         dict(kind="restriction", **{"class": "ExperimentRealisationPlan", "property": "hasSession",
                                     "filler": "ProtocolSession"})),
        ("CQ-15", "Is a selected experiment a scientific proposal (selection is not warrant, RS ED2)?",
         dict(kind="classification", **{"class": "SelectedExperiment", "subclass_of": "ScientificProposal",
                                        "not_subclass_of": "ScientificConclusion"})),
        ("CQ-16", "Is the kernel's dispense a substance-manipulation designator at device-command level, not a body "
                  "motion (action categories aligned with the designator levels)?",
         dict(kind="classification", **{"class": "DispenseCommand", "subclass_of": "SubstanceManipulationDesignator",
                                        "not_subclass_of": "MotionStepDesignator"})),
        ("CQ-17", "Is the kernel's picking-up a plate-transfer (scene-step) designator of the transport facet, and not "
                  "a kind of the transporting it is a phase of (specialisation kept apart from partonomy)?",
         dict(kind="classification", **{"class": "PickingUpDesignator", "subclass_of": "TransportFacetDesignator",
                                        "not_subclass_of": "TransportingDesignator"})),
        ("CQ-18", "Does every kernel audit entry record one designator's lifecycle transition?",
         dict(kind="restriction", **{"class": "CommitmentAuditEntry", "property": "hasTransition",
                                     "filler": "DesignatorLifecycleState"})),
    ]
    yml = {"competency_questions": [dict(id=i, question=q, **d) for i, q, d in cqs]}
    open(os.path.join(HERE, "L2-conceptual-framework", "competency-questions.yaml"), "w").write(
        "# Executable competency questions (ResearchSpace tools/okf_cq.py over the HermiT-reasoned TTL).\n" +
        yaml.safe_dump(yml, sort_keys=False, allow_unicode=True, width=110))
    md = ["---", "type: competency-questions", 'title: "lab-automation-twin competency questions"', "---",
          "# Competency questions", "",
          "TBox questions are executable (`competency-questions.yaml`, `make cq`); ABox questions over the twin are "
          "answered by `check_module.py` into `../docs/competency_questions.md`.", "",
          "## Answered by the L2 (executable)", ""] + [f"**{i}** {q}\n" for i, q, _ in cqs] + [
          "", "## NOT answered by the L2 (by design)", "",
          "- Numeric operating limits of the vendor devices: no vendor manual is in the repository; the contracts "
          "carry none (D016: none are invented).", ""]
    open(os.path.join(HERE, "L2-conceptual-framework", "competency-questions.md"), "w").write("\n".join(md) + "\n")
    print(f"[package] {len(tbox.CLASSES)} L1 cards; grounds {len(grounds)}, divergence {len(divergence)}, "
          f"out-of-scope {sum(len(v) for v in oos.values())}; {len(cqs)} executable CQs")


if __name__ == "__main__":
    main()
