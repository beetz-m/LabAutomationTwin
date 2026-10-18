---
type: dl-definition
title: "Device manual knowledge (Cell 01 component contracts) and device process knowledge (DL definitions)"
derived_from: L1/lab-twin-device-manuals
maturity: L2
status: draft
timestamp: 2026-10-17
module: lab-automation-twin
---

# Device manual knowledge (Cell 01 component contracts) and device process knowledge

Device manual knowledge: Cell 01's SDT component contracts as manuals, with operating procedures (RS ActionContract), preconditions, effects, setpoints, constraints, monitors (AICOR ProcessMonitor), failure modes (AICOR FailureSignature), recovery (AICOR Repair), risk controls and device process microtheories (AICOR BodyWorldProcessMicrotheory).

Every class is positioned under an upstream AICOR / robot-scientist / VRB / normative-admissibility concept or an AICOR upper-level stand-in (`dul:` / `soma:`). Generated from `src/tbox.py` by `build_module.py`; edit the source, not this file.

## Manchester syntax

```
ObjectProperty: manualFor
    -- A manual is about a device or robot (model / component).

ObjectProperty: documentsProcedure
    -- A manual documents an operating procedure.

ObjectProperty: requiresPrecondition
    -- A procedure requires a precondition.

ObjectProperty: hasExpectedEffect
    -- A procedure has an expected effect.

ObjectProperty: usesProcedureMonitor
    -- A procedure is monitored by a monitor.

ObjectProperty: hasRecoveryProcedure
    -- A procedure / failure mode is recovered by a procedure.

ObjectProperty: producesEvidenceOutput
    -- A procedure produces an evidence output.

ObjectProperty: declaresFailureMode
    -- A manual declares a failure mode.

ObjectProperty: declaresRiskControl
    -- A manual declares a risk control.

ObjectProperty: declaresOperatingConstraint
    -- A manual declares an operating constraint.

ObjectProperty: declaresMonitor
    -- A manual declares a device monitor.

ObjectProperty: hasFailureConsequence
    -- A failure mode has a consequence (hazard / validity loss).

ObjectProperty: hasProcessMicrotheory
    -- A device's process knowledge.

ObjectProperty: enforcedInTwinBy
    -- A precondition / rule is enforced by a twin controller check.

DataProperty: setpointValue
    Range: xsd:double
    -- Numeric value of a setpoint.

DataProperty: quantityName
    Range: xsd:string
    -- Quantity a setpoint / variable refers to.

DataProperty: manufacturerBaseline
    Range: xsd:string
    -- Manufacturer / model family a contract is based on.

ObjectProperty: isRequiredBy
    -- Inverse of requiresPrecondition.

ObjectProperty: isEffectOf
    -- Inverse of hasExpectedEffect.

ObjectProperty: isEvidenceOf
    -- Inverse of producesEvidenceOutput.

ObjectProperty: constrainsDevice
    -- A constraint applies to a device.

ObjectProperty: microtheoryOf
    -- A microtheory describes a device's processes.

ObjectProperty: exercisedByTest
    -- A twin check is exercised by a test.

Class: DeviceManual
    SubClassOf: dul:InformationObject
    SubClassOf:
        manualFor some LabArtifact,
        documentsProcedure some OperatingProcedure,
        sourceDocument some xsd:string
    -- Operating knowledge of a device or robot: identity, procedures, setpoints, constraints, monitors, failure modes, recovery and risk controls.

Class: CellComponentContract
    SubClassOf: DeviceManual
    SubClassOf:
        manufacturerBaseline some xsd:string
    -- A Cell 01 SDT component contract (sdt/components/*.yaml): the project's manual-equivalent; no vendor manual is in the repository (restricted source folders are empty).

Class: OperatingProcedure
    SubClassOf: ActionContract
    SubClassOf:
        requiresPrecondition some Precondition,
        hasExpectedEffect some ExpectedEffect,
        hasRecoveryProcedure some RecoveryProcedure
    -- A documented device operation with preconditions, parameters, effects, monitors, recovery and evidence outputs (Cell 01 action_contracts).

Class: ManualItem
    SubClassOf: dul:Description
    SubClassOf:
        statementText some xsd:string
    -- One item of a manual, verbatim.

Class: Precondition
    SubClassOf: ManualItem
    SubClassOf:
        isRequiredBy some OperatingProcedure
    -- Must hold before a procedure.

Class: IdentityPrecondition
    SubClassOf: Precondition
    SubClassOf:
        isRequiredBy some OperatingProcedure
    DisjointWith: AvailabilityPrecondition, EnvironmentPrecondition, CalibrationPrecondition, SafetyPrecondition, AuthorizationPrecondition, PlacementPrecondition
    -- Plate / reagent / target identity verified or consistent.

Class: AvailabilityPrecondition
    SubClassOf: Precondition
    SubClassOf:
        isRequiredBy some OperatingProcedure
    DisjointWith: EnvironmentPrecondition, CalibrationPrecondition, SafetyPrecondition, AuthorizationPrecondition, PlacementPrecondition
    -- Device / slot / station available, reserved or clear.

Class: EnvironmentPrecondition
    SubClassOf: Precondition
    SubClassOf:
        isRequiredBy some OperatingProcedure
    DisjointWith: CalibrationPrecondition, SafetyPrecondition, AuthorizationPrecondition, PlacementPrecondition
    -- Environment within its valid envelope.

Class: CalibrationPrecondition
    SubClassOf: Precondition
    SubClassOf:
        isRequiredBy some OperatingProcedure
    DisjointWith: SafetyPrecondition, AuthorizationPrecondition, PlacementPrecondition
    -- Calibration / tool frame valid.

Class: SafetyPrecondition
    SubClassOf: Precondition
    SubClassOf:
        isRequiredBy some OperatingProcedure
    DisjointWith: AuthorizationPrecondition, PlacementPrecondition
    -- A safety or containment state holds (interlocks ready, airspace clear).

Class: AuthorizationPrecondition
    SubClassOf: Precondition
    SubClassOf:
        isRequiredBy some OperatingProcedure
    DisjointWith: PlacementPrecondition
    -- An authorisation is present (quarantine release, QA decision).

Class: PlacementPrecondition
    SubClassOf: Precondition
    SubClassOf:
        isRequiredBy some OperatingProcedure
    -- An object is seated / present / positioned.

Class: ExpectedEffect
    SubClassOf: ManualItem
    SubClassOf:
        isEffectOf some OperatingProcedure
    -- State after a procedure.

Class: EvidenceOutput
    SubClassOf: ManualItem
    SubClassOf:
        isEvidenceOf some OperatingProcedure
    -- Evidence a procedure records.

Class: OperatingSetpoint
    SubClassOf: ManualItem
    SubClassOf:
        quantityName some xsd:string
    -- Nominal operating state value of a device (e.g. 37 °C).

Class: OperatingConstraint
    SubClassOf: ManualItem
    SubClassOf: LabConstraint
    SubClassOf:
        constrainsDevice some LabArtifact
    -- A constraint a manual places on operation.

Class: DeviceMonitor
    SubClassOf: ProcessMonitor
    SubClassOf:
        statementText some xsd:string
    -- A monitored expectation of a device (expectation + observation channel).

Class: DeviceFailureMode
    SubClassOf: FailureSignature
    SubClassOf:
        hasRecoveryProcedure some RecoveryProcedure,
        hasFailureConsequence some LabHazard,
        statementText some xsd:string
    -- A fault of a device, with its consequence and recovery (Cell 01 failure_modes).

Class: RecoveryProcedure
    SubClassOf: Repair
    SubClassOf:
        statementText some xsd:string
    -- What to do when a fault occurs.

Class: RiskControl
    SubClassOf: ManualItem
    SubClassOf: SafetyConstraint
    SubClassOf:
        mitigatesHazard some LabHazard
    -- A control measure a manual names (alarms, timing limits, interlocks, identity tracking).

Class: DeviceProcessMicrotheory
    SubClassOf: BodyWorldProcessMicrotheory
    SubClassOf:
        microtheoryOf some LabArtifact
    -- Scoped process knowledge of a device: state variables, articulations, environment model.

Class: TwinControllerCheck
    SubClassOf: dul:Description
    SubClassOf:
        exercisedByTest some TwinVerificationTest
    -- A precondition / rule check implemented in a twin device controller (refuses the command when violated).

Class: TwinVerificationTest
    SubClassOf: dul:InformationObject
    SubClassOf:
        verificationTest some xsd:string
    -- A twin regression test (scripts/test_*.py) with its pass record.

Class: TwinEnforcedPrecondition
    SubClassOf: Precondition
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        Precondition,
        enforcedInTwinBy some TwinControllerCheck
    -- Defined: a manual precondition the twin enforces.

```

## Export notes

- Restrictions AICOR's exporter cannot read (negation, nested fillers, inverse roles): 0; they are kept in `build/lab-automation-twin.ofn`.
- Definitions (≡) are necessary conditions in the AICOR export (D-LAT-2).

