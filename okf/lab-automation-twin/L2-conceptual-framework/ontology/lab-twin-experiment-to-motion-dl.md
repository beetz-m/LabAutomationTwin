---
type: dl-definition
title: "From a required information gain to the robot's physical actions and motions (derivation layer) (DL definitions)"
derived_from: L1/lab-twin-experiment-to-motion
maturity: L2
status: draft
timestamp: 2026-10-17
module: lab-automation-twin
---

# From a required information gain to the robot's physical actions and motions (derivation layer)



Every class is positioned under an upstream AICOR / robot-scientist / VRB / normative-admissibility concept or an AICOR upper-level stand-in (`dul:` / `soma:`). Generated from `src/tbox.py` by `build_module.py`; edit the source, not this file.

## Manchester syntax

```
ObjectProperty: discriminatesModel
    -- A candidate experiment's outcome distribution differs between competing models.

ObjectProperty: selectedUnder
    -- A candidate was selected under an information-gain requirement.

ObjectProperty: realisesProposal
    -- A realisation plan realises a selected experiment proposal.

ObjectProperty: hasSession
    -- A plan has a protocol session.

ObjectProperty: hasStep
    -- A session / designator has an ordered step.

ObjectProperty: refinesInto
    -- A designator is refined into a lower-level designator (inverse reading of RS refines).

ObjectProperty: boundToDevice
    -- A designator is bound to a device that performs it.

ObjectProperty: boundToPose
    -- A designator is bound to a pose of the twin.

ObjectProperty: performedByRobot
    -- A motion designator is performed by a robot.

ObjectProperty: commandsDevice
    -- A device-command designator commands a device.

ObjectProperty: usesToolDesignator
    -- A motion uses an exchangeable tool.

ObjectProperty: derivesPlan
    -- A derivation derives a realisation plan.

ObjectProperty: appliesAxiomSet
    -- A derivation applies an L3 axiom set.

ObjectProperty: conditionedOnBelief
    -- An information-gain estimate is conditioned on a culture SDT belief.

ObjectProperty: estimatesGainOf
    -- An estimate is about a candidate experiment.

ObjectProperty: executesPlan
    -- An executed episode executes a realisation plan.

ObjectProperty: routeVia
    -- A plate transfer route passes a station or fixture.

DataProperty: requiredGain_bits
    Range: xsd:double
    -- Required expected information gain (bits).

DataProperty: expectedGain_bits
    Characteristics: Functional
    Range: xsd:double
    -- Expected information gain I(M; y | a, D) (bits).

DataProperty: realisedGain_bits
    Range: xsd:double
    -- Realised information gain KL(p(M|D,y) ‖ p(M|D)) (bits).

DataProperty: rescueDelay_h
    Range: xsd:double
    -- Challenge-to-rescue delay (h).

DataProperty: replicateCount
    Range: xsd:integer
    -- Replicates per arm.

DataProperty: planCost
    Range: xsd:integer
    -- Cost of a realisation (robot operations + wells).

DataProperty: scheduledAt_h
    Range: xsd:double
    -- Scheduled culture time of a session (h).

DataProperty: stepIndex
    Characteristics: Functional
    Range: xsd:integer
    -- Position of a step in its sequence.

DataProperty: estimatedDuration_s
    Range: xsd:double
    -- Duration estimate from twin run traces (s).

DataProperty: primitiveName
    Range: xsd:string
    -- Name of a motion / command primitive.

ObjectProperty: predictsReadout
    -- A model predicts a readout.

ObjectProperty: dischargesRule
    -- A step discharges (satisfies) a rule's precondition.

ObjectProperty: about
    -- An information object is about an entity (module-local, domain-free).

Class: CompetingRecoveryModel
    SubClassOf: ScientificModel
    SubClassOf:
        predictsReadout some MorphologyViabilityReadout
    -- One of Cell 01's competing recovery models (mathematical-models.md §5), calibrated to the observed data.

Class: GradedRecoveryModel
    SubClassOf: CompetingRecoveryModel
    SubClassOf:
        statementText some xsd:string
    DisjointWith: ThresholdRecoveryModel, ProtectiveThresholdModel
    -- M1: P_rec = σ(β0 − β1 I − β2 Δt + β3 d_r); no point of no return.

Class: ThresholdRecoveryModel
    SubClassOf: CompetingRecoveryModel
    SubClassOf:
        statementText some xsd:string
    DisjointWith: ProtectiveThresholdModel
    -- M2: rescue fails once the cumulative injury burden B(Δt) ≥ B*.

Class: ProtectiveThresholdModel
    SubClassOf: CompetingRecoveryModel
    SubClassOf:
        statementText some xsd:string
    -- M3: B*(t) = B0* + α P(t): the threshold moves with adaptive protection.

Class: InformationGainRequirement
    SubClassOf: dul:Description
    SubClassOf:
        requiredGain_bits some xsd:double
    -- What an experiment must teach: a minimum expected information gain over the competing models.

Class: ExperimentCandidate
    SubClassOf: ScientificProposal
    SubClassOf:
        discriminatesModel min 2 CompetingRecoveryModel,
        expectedGain_bits some xsd:double,
        rescueDelay_h some xsd:double,
        doseAU some xsd:double,
        replicateCount some xsd:integer,
        planCost some xsd:integer
    -- A candidate delayed-rescue experiment (dose, rescue delay, replicates) with its EIG and cost.

Class: InformationGainEstimate
    SubClassOf: dul:InformationObject
    SubClassOf:
        estimatesGainOf some ExperimentCandidate,
        conditionedOnBelief some CultureSDT,
        expectedGain_bits some xsd:double
    -- EIG(a) = E_y KL(p(M|D,y,a) ‖ p(M|D)) (Cell 01 §10), by nested Monte Carlo over the calibrated models.

Class: SelectedExperiment
    SubClassOf: ExperimentCandidate
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        ExperimentCandidate,
        selectedUnder some InformationGainRequirement
    -- Defined: the candidate chosen under a gain requirement (least cost among those meeting it).

Class: DelayedRescueStudyDesign
    SubClassOf: StudyDesign
    SubClassOf:
        hasArm some ChallengeRescueArm,
        hasArm some ChallengeOnlyArm,
        hasArm some ControlArm,
        rescueDelay_h some xsd:double
    -- A study design with a chosen rescue delay, comparator and untreated control.

Class: ExperimentRealisationPlan
    SubClassOf: ExperimentalProtocol
    SubClassOf:
        realisesProposal some SelectedExperiment,
        hasSession some ProtocolSession
    -- The derived protocol that realises a selected experiment in the lab: sessions of material, scene and motion designators.

Class: ProtocolSession
    SubClassOf: dul:Description
    SubClassOf:
        scheduledAt_h some xsd:double,
        hasStep some LabActionDesignator
    -- One trip of the plate out of the incubator at a scheduled culture time.

Class: LabActionDesignator
    SubClassOf: ScientificActionDesignator
    SubClassOf:
        stepIndex some xsd:integer
    -- A designator of the realisation plan (RS ScientificActionDesignator).

Class: MaterialStepDesignator
    SubClassOf: LabActionDesignator
    SubClassOf: MaterialScientificDesignator
    SubClassOf:
        refinesInto some SceneStepDesignator
    DisjointWith: SceneStepDesignator, MotionStepDesignator, DeviceCommandDesignator
    -- What happens to the material: dose well w, image well w.

Class: ChallengeDoseDesignator
    SubClassOf: MaterialStepDesignator
    SubClassOf:
        doseAU some xsd:double
    -- Dose challenge.

Class: RescueDoseDesignator
    SubClassOf: MaterialStepDesignator
    SubClassOf:
        doseAU some xsd:double
    -- Dose rescue.

Class: ImageWellDesignator
    SubClassOf: MaterialStepDesignator
    SubClassOf:
        concernsWell some Well
    -- Image a well.

Class: SceneStepDesignator
    SubClassOf: LabActionDesignator
    SubClassOf: SceneGroundedDesignator
    SubClassOf:
        boundToDevice some LabArtifact
    DisjointWith: MotionStepDesignator, DeviceCommandDesignator
    -- Bound to the scene: device, robot, poses.

Class: PlateTransferDesignator
    SubClassOf: SceneStepDesignator
    SubClassOf:
        performedByRobot some CellRobot,
        boundToPose some PlateSeatPose,
        refinesInto some MotionStepDesignator
    -- Move the plate between two seat poses with one robot (one leg of a route).

Class: DeviceOperationDesignator
    SubClassOf: SceneStepDesignator
    SubClassOf:
        boundToDevice some LabAutomationDevice,
        refinesInto some DeviceCommandDesignator
    -- A device operation (dose, image, present, store).

Class: MotionStepDesignator
    SubClassOf: LabActionDesignator
    SubClassOf: BodyMotionDesignator
    SubClassOf:
        performedByRobot some CellRobot,
        primitiveName some xsd:string,
        estimatedDuration_s some xsd:double
    DisjointWith: DeviceCommandDesignator
    -- A robot body-motion primitive (RS BodyMotionDesignator) bound to a pose.

Class: ApproachMotion
    SubClassOf: MotionStepDesignator
    SubClassOf:
        boundToPose some TwinPose
    -- Move to the approach pose above a seat.

Class: InsertMotion
    SubClassOf: MotionStepDesignator
    SubClassOf:
        boundToPose some TwinPose
    -- Descend to the seat pose (compliant).

Class: GraspMotion
    SubClassOf: MotionStepDesignator
    SubClassOf:
        boundToPose some TwinPose
    -- Close the gripper on the plate.

Class: LiftMotion
    SubClassOf: MotionStepDesignator
    SubClassOf:
        boundToPose some TwinPose
    -- Lift the plate off the seat.

Class: TransitMotion
    SubClassOf: MotionStepDesignator
    SubClassOf:
        boundToPose some TwinPose
    -- Planned joint-space / rail transit between approach poses.

Class: PlaceMotion
    SubClassOf: MotionStepDesignator
    SubClassOf:
        boundToPose some TwinPose
    -- Compliant placement into the target seat.

Class: ReleaseMotion
    SubClassOf: MotionStepDesignator
    SubClassOf:
        boundToPose some TwinPose
    -- Open the gripper.

Class: RetractMotion
    SubClassOf: MotionStepDesignator
    SubClassOf:
        boundToPose some TwinPose
    -- Retract to the approach pose (leaves device airspace).

Class: ToolCoupleMotion
    SubClassOf: MotionStepDesignator
    SubClassOf:
        boundToPose some TwinPose
    -- Couple an exchangeable tool at the magazine.

Class: DeviceCommandDesignator
    SubClassOf: LabActionDesignator
    SubClassOf: ScientificActionDesignator
    SubClassOf:
        commandsDevice some LabAutomationDevice,
        primitiveName some xsd:string
    -- A device-level command (present, stow, tip pick, aspirate, dispense, eject, load, image, store, QC).

Class: SafetyStepDesignator
    SubClassOf: DeviceCommandDesignator
    SubClassOf:
        dischargesRule some LabSafetyRule
    -- A step inserted to discharge a safety rule (environment wait, QC calibration, interlock check).

Class: PlanDerivation
    SubClassOf: dul:Description
    SubClassOf:
        derivesPlan some ExperimentRealisationPlan,
        appliesAxiomSet some DerivationAxiomSet
    -- One run of the derivation (answer-set program over the ontology's ABox and the EIG candidates).

Class: DerivationAxiomSet
    SubClassOf: dul:InformationObject
    SubClassOf:
        sourceDocument some xsd:string
    -- The L3 axioms E2M1-E2M8 (L3-logical-axiomatization/axioms/experiment-to-motion-axioms.md).

Class: RealisedInformationGain
    SubClassOf: dul:InformationObject
    SubClassOf:
        realisedGain_bits some xsd:double,
        about some ExperimentRealisationPlan
    -- KL(p(M|D,y) ‖ p(M|D)) after executing the plan.

```

## Export notes

- Restrictions AICOR's exporter cannot read (negation, nested fillers, inverse roles): 0; they are kept in `build/lab-automation-twin.ofn`.
- Definitions (≡) are necessary conditions in the AICOR export (D-LAT-2).

