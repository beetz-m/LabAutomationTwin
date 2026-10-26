"""Bridge between the module's culture-experiments design concepts (AICOR namespace) and the experiment ontology
(rsa/experiment_ontology.py, namespace xp:), so that the two experiment models are one: the module keeps runs,
records, readouts and conclusions; the experiment ontology is the source of what a design, an arm, a comparison and
a control are.

Only primitive correspondences are asserted. The defined classes (challenge-only, challenge-rescue and control arms,
the design classes) are left to the reasoner: tools/check_experiment_merge.py merges module + upstream + experiment
ontology + this bridge, reasons with HermiT and reports what is inferred across the two.

    env_cad/bin/python okf/lab-automation-twin/bridge/build_experiment_bridge.py   # -> bridge/experiment-bridge.ofn
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
XP = "https://aicor.example/okf/experiment#"

CLASS_EQ = [("ExperimentalArm", "ArmSpecification", "a group of units treated alike = an arm specification"),
            ("InterventionSpec", "AdministrationSpecification", "a planned intervention (agent, dose, time)"),
            ("ChallengeSpec", "ChallengeSpec", "a planned dose of the challenge agent"),
            ("RescueSpec", "RescueSpec", "a planned dose of the rescue agent")]
CLASS_SUB = [("StudyDesign", "StudyDesign"), ("ObservationSchedule", "PlanSpecification"),
             ("ChallengeIntervention", "ChallengeAdministration"), ("RescueIntervention", "RescueAdministration"),
             ("ScientificHypothesis", "Hypothesis"), ("ScientificConclusion", "Conclusion"),
             ("CultureExperimentRun", "Investigation"), ("Well", "Well"), ("WellOrganoid", "Organoid")]
OBJ_EQ = [("hasArm", "hasArm"), ("appliesIntervention", "hasAdministrationSpec"), ("assignsUnit", "hasAssignedUnit")]
OBJ_SUB = [("runOfStudy", "executes")]
DATA_EQ = []     # doseAU (xsd:double) vs dose_au (xsd:decimal): disjoint value spaces in OWL 2, equating them makes
                 # every dose contradictory (found by HermiT, 2026-10-18); see DIVERGENCES
DIVERGENCES = ["doseAU (lab, xsd:double) and dose_au (experiment ontology, xsd:decimal) cannot be equated: OWL 2 "
               "value spaces of double and decimal are disjoint; align the datatype in the next revision of one side"]


def main():
    L = ["Prefix(:=<http://aicor.knowledge/l2-ontology.owl#>)", f"Prefix(xp:=<{XP}>)",
         "Prefix(owl:=<http://www.w3.org/2002/07/owl#>)", "Prefix(rdfs:=<http://www.w3.org/2000/01/rdf-schema#>)", "",
         "Ontology(<https://aicor.example/okf/lab-automation-twin/experiment-bridge>",
         'Annotation(rdfs:comment "Primitive correspondences between lab-twin-culture-experiments and the experiment '
         'ontology (rsa/experiment_ontology.py); defined classes are inferred, not asserted.")']
    for a, b, why in CLASS_EQ:
        L.append(f'EquivalentClasses(Annotation(rdfs:comment "{why}") :{a} xp:{b})')
    L += [f"SubClassOf(:{a} xp:{b})" for a, b in CLASS_SUB]
    L += [f"EquivalentObjectProperties(:{a} xp:{b})" for a, b in OBJ_EQ]
    L += [f"SubObjectPropertyOf(:{a} xp:{b})" for a, b in OBJ_SUB]
    L += [f"EquivalentDataProperties(:{a} xp:{b})" for a, b in DATA_EQ]
    L.append(")")
    out = os.path.join(HERE, "experiment-bridge.ofn")
    open(out, "w").write("\n".join(L) + "\n")
    print(f"[bridge] {len(CLASS_EQ)} class equivalences, {len(CLASS_SUB)} subsumptions, {len(OBJ_EQ) + len(OBJ_SUB)} object "
          f"and {len(DATA_EQ)} data property axioms; divergences: {DIVERGENCES} -> {out}")


if __name__ == "__main__":
    main()
