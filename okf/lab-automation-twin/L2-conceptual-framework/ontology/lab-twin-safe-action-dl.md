---
type: dl-definition
title: "Safe action: hazards, safety rules, enforcement, admissibility of candidate actions (DL definitions)"
derived_from: L1/lab-twin-safe-action
maturity: L2
status: draft
timestamp: 2026-10-17
module: lab-automation-twin
---

# Safe action: hazards, safety rules, enforcement, admissibility of candidate actions

Safe action: lab hazards, safety rules as AICOR IncapabilityAssertions, biosafety as RS ContaminationCompatibility, authorisation as normative-admissibility Norms, their enforcement (interlocks, controller checks, critic gates) and the classification of candidate actions as unsafe / unauthorised.

Every class is positioned under an upstream AICOR / robot-scientist / VRB / normative-admissibility concept or an AICOR upper-level stand-in (`dul:` / `soma:`). Generated from `src/tbox.py` by `build_module.py`; edit the source, not this file.

## Manchester syntax

```
ObjectProperty: mitigatesHazard
    -- A device / rule / control mitigates a hazard.

ObjectProperty: prohibitsTaskType
    -- A rule prohibits a task type (in its situation).

ObjectProperty: appliesInSituation
    -- A rule applies in a situation type.

ObjectProperty: enforcedBy
    -- A rule is enforced by a mechanism (interlock, controller check, critic).

ObjectProperty: derivedFromSource
    -- A rule is derived from a source (manual, standard, Cell 01 rule file).

ObjectProperty: violatesRule
    -- A candidate action / command violates a rule.

ObjectProperty: refusedByEntity
    -- A command was refused by a device / interlock / critic.

ObjectProperty: hazardTo
    -- Whom / what a hazard can harm.

ObjectProperty: enforces
    -- InverseOf: enforcedBy
    -- A mechanism enforces a rule.

ObjectProperty: realizedByDevice
    -- A mechanism is realised by a device.

ObjectProperty: testsCriterion
    -- A gate tests a commitment criterion.

ObjectProperty: triggeredByDevice
    -- An event is triggered by a device.

Class: LabHazard
    SubClassOf: dul:Description
    SubClassOf:
        hazardTo some Entity
    -- A potential source of harm in the lab.

Class: HumanInjuryHazard
    SubClassOf: LabHazard
    SubClassOf:
        hazardTo some Entity
    -- Robot motion or pinch points near a person.

Class: CollisionHazard
    SubClassOf: LabHazard
    SubClassOf:
        hazardTo some Entity
    -- Robot / device / labware collision.

Class: ContaminationHazard
    SubClassOf: LabHazard
    SubClassOf:
        hazardTo some Entity
    -- Transfer of contaminants to cultures or reagents.

Class: SampleIntegrityHazard
    SubClassOf: LabHazard
    SubClassOf:
        hazardTo some Entity
    -- Loss of environment, time window or physical integrity.

Class: IdentityHazard
    SubClassOf: LabHazard
    SubClassOf:
        hazardTo some Entity
    -- Swap or loss of sample identity.

Class: MeasurementValidityHazard
    SubClassOf: LabHazard
    SubClassOf:
        hazardTo some Entity
    -- Measurements made with an invalid measurement chain.

Class: AsphyxiationHazard
    SubClassOf: LabHazard
    SubClassOf:
        hazardTo some Entity
    -- Oxygen depletion from LN2 / CO2.

Class: FireHazard
    SubClassOf: LabHazard
    SubClassOf:
        hazardTo some Entity
    -- Fire.

Class: ChemicalExposureHazard
    SubClassOf: LabHazard
    SubClassOf:
        hazardTo some Entity
    -- Splash / exposure of a person.

Class: LabSafetyRule
    SubClassOf: IncapabilityAssertion
    SubClassOf:
        mitigatesHazard some LabHazard,
        prohibitsTaskType some LabTaskType,
        derivedFromSource some dul:InformationObject,
        statementText some xsd:string
    -- A universal prohibition on lab actions in a situation (AICOR IncapabilityAssertion: removes trajectories).

Class: HumanSafetyRule
    SubClassOf: LabSafetyRule
    SubClassOf:
        mitigatesHazard some HumanInjuryHazard,
        enforcedBy some SafetyDevice
    DisjointWith: MachineProtectionRule, BiosafetyRule, SampleIntegrityRule, IdentityRule, MeasurementValidityRule
    -- Protects people (enclosure, door interlocks, light curtain, e-stop).

Class: MachineProtectionRule
    SubClassOf: LabSafetyRule
    SubClassOf:
        mitigatesHazard some CollisionHazard
    DisjointWith: BiosafetyRule, SampleIntegrityRule, IdentityRule, MeasurementValidityRule
    -- Protects equipment and labware (airspace interlock, gate state, cabinet closed in transit).

Class: BiosafetyRule
    SubClassOf: LabSafetyRule
    SubClassOf: ContaminationCompatibility
    SubClassOf:
        mitigatesHazard some ContaminationHazard
    DisjointWith: SampleIntegrityRule, IdentityRule, MeasurementValidityRule
    -- Asepsis / contamination rules; gates intervention admissibility (RS ContaminationCompatibility).

Class: SampleIntegrityRule
    SubClassOf: LabSafetyRule
    SubClassOf:
        mitigatesHazard some SampleIntegrityHazard
    DisjointWith: IdentityRule, MeasurementValidityRule
    -- Environment envelope, time outside the incubator, seating.

Class: IdentityRule
    SubClassOf: LabSafetyRule
    SubClassOf:
        mitigatesHazard some IdentityHazard
    DisjointWith: MeasurementValidityRule
    -- Identity must be verified.

Class: MeasurementValidityRule
    SubClassOf: LabSafetyRule
    SubClassOf:
        mitigatesHazard some MeasurementValidityHazard
    -- No measurement with an invalid calibration / tool frame.

Class: AuthorizationNorm
    SubClassOf: Norm
    SubClassOf:
        prohibitsTaskType some LabTaskType,
        statementText some xsd:string
    -- A normative rule: an action is permitted only with an authorisation (normative, not causal, admissibility).

Class: SafetySourceDocument
    SubClassOf: dul:InformationObject
    SubClassOf:
        sourceDocument some xsd:string
    -- A document safety knowledge is derived from (Cell 01 specification, rule files, site proposal).

Class: SafetyEnforcementMechanism
    SubClassOf: dul:Description
    SubClassOf:
        enforces some LabSafetyRule
    -- How a rule is enforced in the twin.

Class: PhysicalInterlockMechanism
    SubClassOf: SafetyEnforcementMechanism
    SubClassOf:
        realizedByDevice some SafetyDevice
    -- Enforcement by a safety device (door switch, light curtain, e-stop).

Class: ControllerInterlockMechanism
    SubClassOf: SafetyEnforcementMechanism
    SubClassOf: TwinControllerCheck
    SubClassOf:
        realizedByDevice some LabArtifact
    -- Enforcement by a device controller refusing a command (L12 airspace, L10 environment, H4 token).

Class: CriticGateMechanism
    SubClassOf: SafetyEnforcementMechanism
    SubClassOf: SafetyCheck
    SubClassOf:
        testsCriterion some CommitmentCriterion
    -- Enforcement by Cell 01's critic vector: an event commits only if safety_ok (AICOR commitment checking).

Class: UnsafeCandidateAction
    SubClassOf: CandidateAction
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        CandidateAction,
        violatesRule some LabSafetyRule
    -- Defined: a candidate action that violates a lab safety rule (inadmissible).

Class: UnauthorizedCandidateAction
    SubClassOf: CandidateAction
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        CandidateAction,
        violatesRule some AuthorizationNorm
    -- Defined: a candidate action that violates an authorisation norm (normatively inadmissible).

Class: RefusedCommand
    SubClassOf: CandidateAction
    SubClassOf:
        violatesRule some (LabSafetyRule or AuthorizationNorm),
        refusedByEntity some Entity,
        verificationTest some xsd:string
    -- A command the twin refused, observed in a verification test.

Class: ProtectiveStopEvent
    SubClassOf: dul:Event
    SubClassOf:
        triggeredByDevice some SafetyDevice
    -- A latched protective stop (e.g. light curtain broken without muting).

```

## Export notes

- Restrictions AICOR's exporter cannot read (negation, nested fillers, inverse roles): 0; they are kept in `build/lab-automation-twin.ofn`.
- Definitions (≡) are necessary conditions in the AICOR export (D-LAT-2).

