---
type: dl-definition
title: "Culture experiments: designs, arms, interventions, readouts, runs, conclusions (DL definitions)"
derived_from: L1/lab-twin-culture-experiments
maturity: L2
status: draft
timestamp: 2026-10-17
module: lab-automation-twin
---

# Culture experiments: designs, arms, interventions, readouts, runs, conclusions

Culture experiments: Cell 01's challenge-rescue design (RS StudyDesign) with arms, intervention specifications, observation schedule, interventions (RS BiologicalIntervention), morphology readouts (RS CellViabilityReadout), runs (RS ExperimentalEpisode), hypotheses and (withheld) conclusions.

Every class is positioned under an upstream AICOR / robot-scientist / VRB / normative-admissibility concept or an AICOR upper-level stand-in (`dul:` / `soma:`). Generated from `src/tbox.py` by `build_module.py`; edit the source, not this file.

## Manchester syntax

```
ObjectProperty: hasArm
    -- A study design has an arm.

ObjectProperty: assignsUnit
    -- An arm assigns an experimental unit (well).

ObjectProperty: appliesIntervention
    -- An arm applies an intervention specification.

ObjectProperty: observedBySchedule
    -- A design observes units on a schedule.

ObjectProperty: runOfStudy
    -- A run realises a study design.

ObjectProperty: concernsWell
    -- A record / conclusion concerns a well.

ObjectProperty: comparesArm
    -- A conclusion compares arms.

ObjectProperty: withheldBecause
    -- A conclusion is withheld for a reason.

ObjectProperty: hasScenarioCondition
    -- A run is conducted under a scenario condition (fault injection).

ObjectProperty: realizesIntervention
    -- A record is about an intervention event.

ObjectProperty: appliedToWell
    -- An intervention event is applied to a well.

DataProperty: doseAU
    Range: xsd:double
    -- Dose in abstract units (Cell 01 D016: illustrative).

DataProperty: time_h
    Range: xsd:double
    -- Culture time (h).

DataProperty: interval_h
    Range: xsd:double
    -- Observation interval (h).

DataProperty: horizon_h
    Range: xsd:double
    -- Observation horizon (h).

DataProperty: viabilityMean
    Range: xsd:double
    -- Posterior mean viability.

DataProperty: viabilityP05
    Range: xsd:double
    -- Posterior 5 % quantile.

DataProperty: viabilityP95
    Range: xsd:double
    -- Posterior 95 % quantile.

DataProperty: radius_um
    Range: xsd:double
    -- Measured organoid radius (µm).

DataProperty: coreOpticalDensity
    Range: xsd:double
    -- Measured core optical density.

DataProperty: debrisCount
    Range: xsd:integer
    -- Counted debris.

DataProperty: mediumHaze
    Range: xsd:double
    -- Measured haze.

DataProperty: claimProbability
    Range: xsd:double
    -- Posterior probability of a conclusion.

DataProperty: claimStatus
    Range: xsd:string
    -- Status (candidate / withheld ...).

DataProperty: isCommittedEvent
    Characteristics: Functional
    Range: xsd:boolean
    -- Whether the culture ledger committed the event.

DataProperty: scenarioName
    Range: xsd:string
    -- Scenario of a run.

ObjectProperty: specifiesTask
    -- A specification is realised by a task type.

ObjectProperty: injectsHazard
    -- A fault injection realises a hazard.

ObjectProperty: citesRule
    -- A reason cites a rule.

ObjectProperty: flagsHazard
    -- A record flags a hazard.

Class: ChallengeRescueStudyDesign
    SubClassOf: StudyDesign
    SubClassOf:
        hasArm some ChallengeOnlyArm,
        hasArm some ChallengeRescueArm,
        hasArm some ControlArm,
        observedBySchedule some ObservationSchedule
    -- Cell 01's challenge-rescue design: graded challenge doses, rescue at 6 h, untreated controls, 4x imaging every 6 h to 72 h.

Class: ExperimentalArm
    SubClassOf: dul:Description
    SubClassOf:
        assignsUnit some Well
    -- A group of units treated alike.

Class: InterventionSpec
    SubClassOf: dul:Description
    SubClassOf:
        doseAU some xsd:double,
        time_h some xsd:double
    -- A planned intervention (agent, dose, time).

Class: ChallengeSpec
    SubClassOf: InterventionSpec
    SubClassOf:
        specifiesTask some ChallengeDosingTask
    DisjointWith: RescueSpec
    -- Planned challenge dose.

Class: RescueSpec
    SubClassOf: InterventionSpec
    SubClassOf:
        specifiesTask some RescueDosingTask
    -- Planned rescue dose.

Class: ChallengeOnlyArm
    SubClassOf: ExperimentalArm
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        ExperimentalArm,
        appliesIntervention some ChallengeSpec,
        not (appliesIntervention some RescueSpec)
    DisjointWith: ChallengeRescueArm, ControlArm
    -- Defined: challenged, not rescued.

Class: ChallengeRescueArm
    SubClassOf: ExperimentalArm
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        ExperimentalArm,
        appliesIntervention some ChallengeSpec,
        appliesIntervention some RescueSpec
    DisjointWith: ControlArm
    -- Defined: challenged and rescued.

Class: ControlArm
    SubClassOf: ExperimentalArm
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        ExperimentalArm,
        not (appliesIntervention some InterventionSpec)
    -- Defined: no intervention.

Class: ObservationSchedule
    SubClassOf: dul:Description
    SubClassOf:
        interval_h some xsd:double,
        horizon_h some xsd:double
    -- When units are observed.

Class: ChallengeIntervention
    SubClassOf: BiologicalIntervention
    SubClassOf:
        realizedByAction some ScientificActionDesignator
    DisjointWith: RescueIntervention
    -- A dose of the challenge agent into a well (L12 dose).

Class: RescueIntervention
    SubClassOf: BiologicalIntervention
    SubClassOf:
        realizedByAction some ScientificActionDesignator
    -- A dose of the rescue agent into a well.

Class: MorphologyViabilityReadout
    SubClassOf: CellViabilityReadout
    SubClassOf:
        observationOf some WellOrganoid
    -- Viability inferred from bright-field morphology (radius, core OD, debris, haze) of a 4x image.

Class: RescueHypothesis
    SubClassOf: ScientificHypothesis
    SubClassOf:
        heldIn some CultureSDT
    -- 'Rescue at 6 h raises 72 h viability at challenge dose d.'

Class: CultureExperimentRun
    SubClassOf: ExperimentalEpisode
    SubClassOf:
        runOfStudy some ChallengeRescueStudyDesign,
        scenarioName some xsd:string
    -- One executed run of the study in the twin.

Class: ScenarioCondition
    SubClassOf: dul:Description
    SubClassOf:
        statementText some xsd:string
    -- A condition of a run (nominal, injected fault).

Class: FaultInjection
    SubClassOf: ScenarioCondition
    SubClassOf:
        injectsHazard some LabHazard
    -- A deliberately injected fault.

Class: RescueComparisonConclusion
    SubClassOf: ScientificConclusion
    SubClassOf:
        concernsWell min 2 Well,
        claimStatus some xsd:string
    -- Conclusion comparing a rescued with an unrescued well.

Class: WithholdingReason
    SubClassOf: dul:Description
    SubClassOf:
        statementText some xsd:string
    -- Why a conclusion is withheld.

Class: UnverifiedComparatorReason
    SubClassOf: WithholdingReason
    SubClassOf:
        citesRule some LabSafetyRule
    -- A compared well received an uncommitted (unverified) intervention.

Class: ContaminationSuspectedReason
    SubClassOf: WithholdingReason
    SubClassOf:
        citesRule some BiosafetyRule
    -- A compared well is flagged contamination_suspected.

Class: WithheldConclusion
    SubClassOf: RescueComparisonConclusion
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        RescueComparisonConclusion,
        withheldBecause some WithholdingReason
    -- Defined: a conclusion withheld for a stated reason.

Class: WellBeliefEstimate
    SubClassOf: StateEstimate
    SubClassOf:
        concernsWell some Well
    -- The culture SDT's posterior estimate of a well's latent state (epistemic status: inferred).

Class: WellObservationRecord
    SubClassOf: CellViabilityReadout
    SubClassOf:
        concernsWell some Well,
        radius_um some xsd:double
    -- Measured morphology of one well at one session, with image / calibration provenance.

Class: InterventionRecord
    SubClassOf: dul:InformationObject
    SubClassOf:
        partOf some InterventionHistory,
        realizesIntervention some BiologicalIntervention,
        isCommittedEvent some xsd:boolean
    -- A dose event in a well's intervention history.

Class: UnverifiedInterventionRecord
    SubClassOf: InterventionRecord
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        InterventionRecord,
        isCommittedEvent value false
    -- Defined: an intervention record the ledger did not commit.

Class: WellQualityRecord
    SubClassOf: dul:InformationObject
    SubClassOf:
        concernsWell some Well
    -- ESS and anomaly flags.

Class: ContaminationSuspectedFlag
    SubClassOf: WellQualityRecord
    SubClassOf:
        flagsHazard some ContaminationHazard
    -- Cell 01's contamination_suspected rule fired for a well.

```

## Export notes

- Restrictions AICOR's exporter cannot read (negation, nested fillers, inverse roles): 0; they are kept in `build/lab-automation-twin.ofn`.
- Definitions (≡) are necessary conditions in the AICOR export (D-LAT-2).

