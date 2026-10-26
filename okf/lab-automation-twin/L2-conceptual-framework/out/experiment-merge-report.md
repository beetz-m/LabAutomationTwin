# Experiment models merged: lab module + experiment ontology

Konclude (SROIQV(D)) over okf/lab-automation-twin/build/upstream-aicor-ontology.ttl, okf/lab-automation-twin/build/lab-automation-twin.ofn, rsa/out/experiment_ontology/experiment.owl, okf/lab-automation-twin/bridge/experiment-bridge.ofn: **consistent**, 0 unsatisfiable, 1.4 s.

## Inferred equivalences (not asserted)

- lab:ChallengeOnlyArm ≡ xp:ChallengeOnlyArm
- lab:ChallengeRescueArm ≡ xp:ChallengeRescueArm
- lab:ControlArm ≡ xp:UntreatedArm

## Divergences (not bridged)

- doseAU (lab, xsd:double) and dose_au (experiment ontology, xsd:decimal) cannot be equated: OWL 2 value spaces of double and decimal are disjoint; align the datatype in the next revision of one side

## Inferred subsumptions across the two (not asserted)

- lab:ChallengeRescueStudyDesign ⊑ xp:RequiresDosing
- lab:ControlArm ⊑ xp:NegativeControlArm
- lab:DelayedRescueStudyDesign ⊑ xp:RequiresDosing
- lab:ExperimentalArm ⊑ xp:PlanSpecification
- lab:InterventionSpec ⊑ xp:PlanSpecification
- xp:ChallengeRescueArm ⊑ lab:ExperimentalArm
- xp:ChallengeSpec ⊑ lab:InterventionSpec
- xp:NegativeControlArm ⊑ lab:ExperimentalArm
- xp:PositiveControlArm ⊑ lab:ExperimentalArm
- xp:ReplicatedArm ⊑ lab:ExperimentalArm
- xp:RescueOnlyArm ⊑ lab:ExperimentalArm
- xp:VehicleSpec ⊑ lab:InterventionSpec
