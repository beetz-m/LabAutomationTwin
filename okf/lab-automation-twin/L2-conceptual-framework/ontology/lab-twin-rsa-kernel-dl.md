---
type: dl-definition
title: "The robot science assistant kernel: action-designator categories, lifecycle and audit entries (DL definitions)"
derived_from: L1/lab-twin-rsa-kernel
maturity: L2
status: draft
timestamp: 2026-10-17
module: lab-automation-twin
---

# The robot science assistant kernel: action-designator categories, lifecycle and audit entries



Every class is positioned under an upstream AICOR / robot-scientist / VRB / normative-admissibility concept or an AICOR upper-level stand-in (`dul:` / `soma:`). Generated from `src/tbox.py` by `build_module.py`; edit the source, not this file.

## Manchester syntax

```
ObjectProperty: designatesAction
    -- A designator designates an action of a type (CRAM: an action designator references an action event type).

DataProperty: kernelCategory
    Range: xsd:string
    -- A kernel category (registry card id) of a designator (not functional: a specialised category's designators also carry the general one).

ObjectProperty: constrainsDesignator
    -- A kernel constraint applies to designators of a category.

ObjectProperty: recordsDesignator
    -- An audit entry is about one designator (one lifecycle transition of it).

ObjectProperty: hasTransition
    -- An audit entry records a lifecycle transition.

ObjectProperty: checksConstraint
    -- An audit entry carries a verdict on a registry constraint.

ObjectProperty: violatesConstraint
    -- SubPropertyOf: checksConstraint   (full OWL export; not read by okf_owl.py)
    -- An audit entry records a VIOLATED verdict on a constraint.

ObjectProperty: chainedAfter
    Characteristics: Functional
    -- An audit entry is hash-chained after its predecessor.

ObjectProperty: carriesEvidence
    -- An audit entry carries a content-hashed evidence item.

DataProperty: recordSeq
    Characteristics: Functional
    Range: xsd:integer
    -- Position of the entry in the trail.

DataProperty: chainHash
    Characteristics: Functional
    Range: xsd:string
    -- SHA-256 over the previous hash and the entry's canonical JSON.

DataProperty: simTime_s
    Characteristics: Functional
    Range: xsd:double
    -- Simulated time of the entry (s).

DataProperty: evidenceSha256
    Characteristics: Functional
    Range: xsd:string
    -- Content hash of an evidence item.

Class: KernelScientificDesignator
    SubClassOf: LabActionDesignator
    SubClassOf:
        refinesInto some LabActionDesignator
    DisjointWith: KernelLabTaskDesignator, KernelManipulationDesignator, MotionStepDesignator, DeviceCommandDesignator
    -- Scientific-level designator of the kernel (experiment, wait, intervene, measure; RS scientific actions); realised by lower-level designators.

Class: KernelLabTaskDesignator
    SubClassOf: LabActionDesignator
    SubClassOf:
        refinesInto some LabActionDesignator
    DisjointWith: KernelManipulationDesignator, MotionStepDesignator, DeviceCommandDesignator
    -- Lab-task designator (Cell 01 CRAM designator schemas: retrieve, store, transport, dose, image, qc, quarantine).

Class: KernelManipulationDesignator
    SubClassOf: LabActionDesignator
    SubClassOf:
        refinesInto some LabActionDesignator
    DisjointWith: MotionStepDesignator, DeviceCommandDesignator
    -- Manipulation-action designator (CRAM action categories: picking-up, placing, transporting, coupling, presenting, stowing).

Class: ObjectDisplacementDesignator
    SubClassOf: LabActionDesignator
    SubClassOf:
        designatesAction some LabAction
    DisjointWith: ConfigurationChangeDesignator, SubstanceManipulationDesignator, ConnectingActionDesignator, PerceptionDesignator, MaintenanceActionDesignator, RegulationActionDesignator
    -- Designators of actions whose effect class is ObjectDisplacement (AICOR action-category partition, CRAM action-category-dl).

Class: ConfigurationChangeDesignator
    SubClassOf: LabActionDesignator
    SubClassOf:
        designatesAction some LabAction
    DisjointWith: SubstanceManipulationDesignator, ConnectingActionDesignator, PerceptionDesignator, MaintenanceActionDesignator, RegulationActionDesignator
    -- Designators of actions whose effect class is ConfigurationChange (AICOR action-category partition, CRAM action-category-dl).

Class: SubstanceManipulationDesignator
    SubClassOf: LabActionDesignator
    SubClassOf:
        designatesAction some LabAction
    DisjointWith: ConnectingActionDesignator, PerceptionDesignator, MaintenanceActionDesignator, RegulationActionDesignator
    -- Designators of actions whose effect class is SubstanceManipulation (AICOR action-category partition, CRAM action-category-dl).

Class: ConnectingActionDesignator
    SubClassOf: LabActionDesignator
    SubClassOf:
        designatesAction some LabAction
    DisjointWith: PerceptionDesignator, MaintenanceActionDesignator, RegulationActionDesignator
    -- Designators of actions whose effect class is ConnectingAction (AICOR action-category partition, CRAM action-category-dl).

Class: PerceptionDesignator
    SubClassOf: LabActionDesignator
    SubClassOf:
        designatesAction some LabAction
    DisjointWith: MaintenanceActionDesignator, RegulationActionDesignator
    -- Designators of actions whose effect class is Perception (AICOR action-category partition, CRAM action-category-dl).

Class: MaintenanceActionDesignator
    SubClassOf: LabActionDesignator
    SubClassOf:
        designatesAction some LabAction
    DisjointWith: RegulationActionDesignator
    -- Designators of actions whose effect class is MaintenanceAction (AICOR action-category partition, CRAM action-category-dl).

Class: RegulationActionDesignator
    SubClassOf: LabActionDesignator
    SubClassOf:
        designatesAction some LabAction
    -- Designators of actions whose effect class is RegulationAction (AICOR action-category partition, CRAM action-category-dl).

Class: TransportFacetDesignator
    SubClassOf: LabActionDesignator
    SubClassOf:
        designatesAction some LabAction
    DisjointWith: OperationFacetDesignator, TransformationFacetDesignator
    -- Designators of transport actions (GARMI three manipulation classes; orthogonal to the effect class).

Class: OperationFacetDesignator
    SubClassOf: LabActionDesignator
    SubClassOf:
        designatesAction some LabAction
    DisjointWith: TransformationFacetDesignator
    -- Designators of operation actions (GARMI three manipulation classes; orthogonal to the effect class).

Class: TransformationFacetDesignator
    SubClassOf: LabActionDesignator
    SubClassOf:
        designatesAction some LabAction
    -- Designators of transformation actions (GARMI three manipulation classes; orthogonal to the effect class).

Class: ExperimentDesignator
    SubClassOf: KernelScientificDesignator
    SubClassOf: LabActionDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        KernelScientificDesignator,
        kernelCategory value "experiment"
    -- Kernel category 'experiment': run the selected experiment. HADL: (an action (type experiment) (design ?d) (requirement (eig >= ?g))). Sources: e2m derive_plan selection, RSV experimental-workflow-dl, uc_ccr se_loop.

Class: WaitDesignator
    SubClassOf: KernelScientificDesignator
    SubClassOf: LabActionDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        KernelScientificDesignator,
        kernelCategory value "wait"
    -- Kernel category 'wait': wait for culture time. HADL: (an action (type wait) (until (culture-time ?t))). Sources: RSV scientific-action-designator-dl Wait.

Class: InterveneDesignator
    SubClassOf: KernelScientificDesignator
    SubClassOf: MaterialStepDesignator
    SubClassOf:
        refinesInto some DoseDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        KernelScientificDesignator,
        kernelCategory value "intervene"
    -- Kernel category 'intervene': intervene on a culture well. HADL: (an action (type intervene) (reagent ?r) (dose ?au) (well (the well ?w))). Sources: RSV scientific-action-designator-dl Intervene, C01 report §9.

Class: MeasureDesignator
    SubClassOf: KernelScientificDesignator
    SubClassOf: ImageWellDesignator
    SubClassOf:
        refinesInto some ImageDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        KernelScientificDesignator,
        kernelCategory value "measure"
    -- Kernel category 'measure': measure a culture well. HADL: (an action (type measure) (readout organoid-radius) (well (the well ?w))). Sources: RSV scientific-action-designator-dl Measure.

Class: RunSessionDesignator
    SubClassOf: KernelLabTaskDesignator
    SubClassOf: LabActionDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        KernelLabTaskDesignator,
        kernelCategory value "run_session"
    -- Kernel category 'run_session': run one session trip. HADL: (an action (type run-session) (plate (the plate ?p)) (materials ?m)). Sources: e2m E2M4 sessions, C01 SESSION_HANDOFF first slice.

Class: RetrieveDesignator
    SubClassOf: KernelLabTaskDesignator
    SubClassOf: ObjectDisplacementDesignator
    SubClassOf: TransportFacetDesignator
    SubClassOf:
        designatesAction some RetrieveAction
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        KernelLabTaskDesignator,
        kernelCategory value "retrieve"
    -- Kernel category 'retrieve': retrieve the plate from storage. HADL: (an action (type retrieve) (object (the plate ?p)) (source (the location home))). Sources: C01 cram_designator_schemas retrieve, e2m S7.

Class: StoreDesignator
    SubClassOf: KernelLabTaskDesignator
    SubClassOf: ObjectDisplacementDesignator
    SubClassOf: TransportFacetDesignator
    SubClassOf:
        designatesAction some StoreAction
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        KernelLabTaskDesignator,
        kernelCategory value "store"
    -- Kernel category 'store': store the plate in the incubator. HADL: (an action (type store) (object (the plate ?p)) (location (the location home))). Sources: C01 cram_designator_schemas store, e2m S2.

Class: TransportLabDesignator
    SubClassOf: KernelLabTaskDesignator
    SubClassOf: ObjectDisplacementDesignator
    SubClassOf: TransportFacetDesignator
    SubClassOf:
        designatesAction some TransferAction,
        refinesInto some TransportingDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        KernelLabTaskDesignator,
        kernelCategory value "transport_lab"
    -- Kernel category 'transport_lab': transport the plate between stations. HADL: (an action (type transport) (object (the plate ?p)) (target (a location (serves ?function)))). Sources: C01 cram_designator_schemas transport, e2m E2M6 routes, coraplex TransportAction.

Class: DoseDesignator
    SubClassOf: KernelLabTaskDesignator
    SubClassOf: SubstanceManipulationDesignator
    SubClassOf: TransformationFacetDesignator
    SubClassOf:
        designatesAction some DoseAction
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        KernelLabTaskDesignator,
        kernelCategory value "dose"
    -- Kernel category 'dose': dose a culture well. HADL: (an action (type dose) (device (a device (capable dose_well))) (well (the well ?w)) (reagent (the reagent ?r)) (volume ?v)). Sources: C01 cram_designator_schemas dose, C01 L12 action_contracts dose_well, e2m E2M5.

Class: ImageDesignator
    SubClassOf: KernelLabTaskDesignator
    SubClassOf: PerceptionDesignator
    SubClassOf: OperationFacetDesignator
    SubClassOf:
        designatesAction some ImageAction
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        KernelLabTaskDesignator,
        kernelCategory value "image"
    -- Kernel category 'image': image a culture well. HADL: (an action (type image) (device (a device (capable image_well))) (well (the well ?w))). Sources: C01 cram_designator_schemas image, C01 L17 record, RSV measurement-binding lever.

Class: CalibrateDesignator
    SubClassOf: KernelLabTaskDesignator
    SubClassOf: MaintenanceActionDesignator
    SubClassOf: OperationFacetDesignator
    SubClassOf:
        designatesAction some QCAction
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        KernelLabTaskDesignator,
        kernelCategory value "calibrate"
    -- Kernel category 'calibrate': calibrate a measurement device at its QC station. HADL: (an action (type calibrate) (target (the device ?d)) (station (a device (qc-station-for ?d)))). Sources: C01 cram_designator_schemas qc, e2m S3.

Class: QuarantineDesignator
    SubClassOf: KernelLabTaskDesignator
    SubClassOf: ObjectDisplacementDesignator
    SubClassOf: TransportFacetDesignator
    SubClassOf:
        designatesAction some QuarantineAction
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        KernelLabTaskDesignator,
        kernelCategory value "quarantine"
    -- Kernel category 'quarantine': quarantine a plate. HADL: (an action (type quarantine) (object (the plate ?p)) (reason ?why)). Sources: C01 cram_designator_schemas quarantine, C01 H4 record.

Class: TransportingDesignator
    SubClassOf: KernelManipulationDesignator
    SubClassOf: ObjectDisplacementDesignator
    SubClassOf: TransportFacetDesignator
    SubClassOf: PlateTransferDesignator
    SubClassOf:
        refinesInto some PickingUpDesignator,
        refinesInto some PlacingDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        KernelManipulationDesignator,
        kernelCategory value "transporting"
    -- Kernel category 'transporting': transport by one robot (one leg). HADL: (an action (type transporting) (agent (a robot (serves ?src ?dst))) (object (the plate ?p)) (from ?src) (to ?dst)). Sources: coraplex TransportAction, CRAM TASK-TAXONOMY A.

Class: PickingUpDesignator
    SubClassOf: KernelManipulationDesignator
    SubClassOf: ObjectDisplacementDesignator
    SubClassOf: TransportFacetDesignator
    SubClassOf: PlateTransferDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        KernelManipulationDesignator,
        kernelCategory value "picking_up"
    -- Kernel category 'picking_up': pick up the plate. HADL: (an action (type picking-up) (object (the plate ?p)) (location (the seat ?s))). Sources: coraplex PickUpAction, Flanagan reach-lift.

Class: PlacingDesignator
    SubClassOf: KernelManipulationDesignator
    SubClassOf: ObjectDisplacementDesignator
    SubClassOf: TransportFacetDesignator
    SubClassOf: PlateTransferDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        KernelManipulationDesignator,
        kernelCategory value "placing"
    -- Kernel category 'placing': place the plate. HADL: (an action (type placing) (object (the plate ?p)) (location (the seat ?s))). Sources: coraplex PlaceAction.

Class: CouplingToolDesignator
    SubClassOf: KernelManipulationDesignator
    SubClassOf: ConnectingActionDesignator
    SubClassOf: TransportFacetDesignator
    SubClassOf: SceneStepDesignator
    SubClassOf:
        refinesInto some ToolCoupleMotion
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        KernelManipulationDesignator,
        kernelCategory value "coupling_tool"
    -- Kernel category 'coupling_tool': couple the plate gripper tool. HADL: (an action (type coupling-tool) (agent ?r) (tool (the tool ?t))). Sources: OKF tool-use (tool extends body), e2m S4.

Class: PresentingDesignator
    SubClassOf: KernelManipulationDesignator
    SubClassOf: ConfigurationChangeDesignator
    SubClassOf: OperationFacetDesignator
    SubClassOf: DeviceOperationDesignator
    SubClassOf:
        refinesInto some PresentCommand
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        KernelManipulationDesignator,
        kernelCategory value "presenting"
    -- Kernel category 'presenting': present the device's plate shuttle. HADL: (an action (type presenting) (device ?d)). Sources: CRAM TASK-TAXONOMY B tend (access), H4 v2 shuttle.

Class: StowingDesignator
    SubClassOf: KernelManipulationDesignator
    SubClassOf: ConfigurationChangeDesignator
    SubClassOf: OperationFacetDesignator
    SubClassOf: DeviceOperationDesignator
    SubClassOf:
        refinesInto some StowCommand
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        KernelManipulationDesignator,
        kernelCategory value "stowing"
    -- Kernel category 'stowing': stow the device's plate shuttle. HADL: (an action (type stowing) (device ?d)). Sources: CRAM TASK-TAXONOMY B tend (access).

Class: CheckInterlocksCommand
    SubClassOf: DeviceCommandDesignator
    SubClassOf: PerceptionDesignator
    SubClassOf: SafetyStepDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        DeviceCommandDesignator,
        kernelCategory value "check_interlocks"
    -- Kernel category 'check_interlocks': check enclosure interlocks. HADL: -. Sources: kernel registry.

Class: VerifyIdentityCommand
    SubClassOf: DeviceCommandDesignator
    SubClassOf: PerceptionDesignator
    SubClassOf: SafetyStepDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        DeviceCommandDesignator,
        kernelCategory value "verify_identity"
    -- Kernel category 'verify_identity': read plate identity. HADL: -. Sources: kernel registry.

Class: PresentCommand
    SubClassOf: DeviceCommandDesignator
    SubClassOf: ConfigurationChangeDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        DeviceCommandDesignator,
        kernelCategory value "present"
    -- Kernel category 'present': present shuttle. HADL: -. Sources: kernel registry.

Class: StowCommand
    SubClassOf: DeviceCommandDesignator
    SubClassOf: ConfigurationChangeDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        DeviceCommandDesignator,
        kernelCategory value "stow"
    -- Kernel category 'stow': stow shuttle. HADL: -. Sources: kernel registry.

Class: WaitEnvironmentCommand
    SubClassOf: DeviceCommandDesignator
    SubClassOf: RegulationActionDesignator
    SubClassOf: SafetyStepDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        DeviceCommandDesignator,
        kernelCategory value "wait_environment"
    -- Kernel category 'wait_environment': wait for environment. HADL: -. Sources: kernel registry.

Class: StoreCmdCommand
    SubClassOf: DeviceCommandDesignator
    SubClassOf: ObjectDisplacementDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        DeviceCommandDesignator,
        kernelCategory value "store_cmd"
    -- Kernel category 'store_cmd': store plate in slot. HADL: -. Sources: kernel registry.

Class: TipPickCommand
    SubClassOf: DeviceCommandDesignator
    SubClassOf: ConnectingActionDesignator
    SubClassOf: TransformationFacetDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        DeviceCommandDesignator,
        kernelCategory value "tip_pick"
    -- Kernel category 'tip_pick': pick a tip. HADL: -. Sources: kernel registry.

Class: AspirateCommand
    SubClassOf: DeviceCommandDesignator
    SubClassOf: SubstanceManipulationDesignator
    SubClassOf: TransformationFacetDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        DeviceCommandDesignator,
        kernelCategory value "aspirate"
    -- Kernel category 'aspirate': aspirate reagent. HADL: -. Sources: kernel registry.

Class: DispenseCommand
    SubClassOf: DeviceCommandDesignator
    SubClassOf: SubstanceManipulationDesignator
    SubClassOf: TransformationFacetDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        DeviceCommandDesignator,
        kernelCategory value "dispense"
    -- Kernel category 'dispense': dispense into well. HADL: -. Sources: kernel registry.

Class: TipEjectCommand
    SubClassOf: DeviceCommandDesignator
    SubClassOf: ConnectingActionDesignator
    SubClassOf: TransformationFacetDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        DeviceCommandDesignator,
        kernelCategory value "tip_eject"
    -- Kernel category 'tip_eject': eject tip to waste. HADL: -. Sources: kernel registry.

Class: LoadCommand
    SubClassOf: DeviceCommandDesignator
    SubClassOf: ObjectDisplacementDesignator
    SubClassOf: OperationFacetDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        DeviceCommandDesignator,
        kernelCategory value "load"
    -- Kernel category 'load': load plate onto stage. HADL: -. Sources: kernel registry.

Class: ImageWellCommand
    SubClassOf: DeviceCommandDesignator
    SubClassOf: PerceptionDesignator
    SubClassOf: OperationFacetDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        DeviceCommandDesignator,
        kernelCategory value "image_well"
    -- Kernel category 'image_well': image a well. HADL: -. Sources: kernel registry.

Class: AutofocusCommand
    SubClassOf: DeviceCommandDesignator
    SubClassOf: PerceptionDesignator
    SubClassOf: OperationFacetDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        DeviceCommandDesignator,
        kernelCategory value "autofocus"
    -- Kernel category 'autofocus': fresh autofocus on a well. HADL: -. Sources: kernel registry.

Class: IncubateCommand
    SubClassOf: DeviceCommandDesignator
    SubClassOf: RegulationActionDesignator
    SubClassOf: OperationFacetDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        DeviceCommandDesignator,
        kernelCategory value "incubate"
    -- Kernel category 'incubate': hold the plate in the incubator until a culture time. HADL: -. Sources: kernel registry.

Class: ContainCommand
    SubClassOf: DeviceCommandDesignator
    SubClassOf: ConfigurationChangeDesignator
    SubClassOf: OperationFacetDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        DeviceCommandDesignator,
        kernelCategory value "contain"
    -- Kernel category 'contain': contain a plate in quarantine. HADL: -. Sources: kernel registry.

Class: ValidateCommand
    SubClassOf: DeviceCommandDesignator
    SubClassOf: MaintenanceActionDesignator
    SubClassOf: SafetyStepDesignator
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        DeviceCommandDesignator,
        kernelCategory value "validate"
    -- Kernel category 'validate': run reference-plate validation. HADL: -. Sources: kernel registry.

Class: DesignatorLifecycleState
    SubClassOf: dul:Concept
    SubClassOf:
        statementText some xsd:string
    -- Cell 01 designator lifecycle: open, grounded, accepted, executing, executed, failed, repaired, abstained, escalated (+ repairing, replanned, policy_violation as executor events).

Class: KernelConstraint
    SubClassOf: dul:Description
    SubClassOf:
        sourceDocument some xsd:string,
        constrainsDesignator some LabActionDesignator
    -- A constraint of the kernel registry, checked at acceptance, after execution, as a policy, or by the experimental critic.

Class: RealizationConstraint
    SubClassOf: KernelConstraint
    SubClassOf:
        constrainsDesignator some LabActionDesignator
    DisjointWith: ValidityConstraint
    -- Did it run correctly and safely (uc_ccr realization column).

Class: EvidenceItem
    SubClassOf: dul:InformationObject
    SubClassOf:
        evidenceSha256 some xsd:string
    -- An observation, reading or record attached to an audit entry, content-hashed.

Class: CommitmentAuditEntry
    SubClassOf: LabExecutionTrace
    SubClassOf:
        recordsDesignator some LabActionDesignator,
        hasTransition some DesignatorLifecycleState,
        recordSeq some xsd:integer,
        chainHash some xsd:string
    -- One hash-chained audit entry per designator lifecycle transition (uc_ccr audit.py + Cell 01 NEEM record sections + VRB warrant entry ⟨grounds, constraints discharged, verdict, disposition⟩). Not AICOR's CommitmentRecord (an episode-level Description containing action tokens and episodes; D-LAT-11).

Class: ViolationAuditEntry
    SubClassOf: CommitmentAuditEntry
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        CommitmentAuditEntry,
        violatesConstraint some KernelConstraint
    -- Defined: an audit entry that records a violated constraint.

Individual: lifecycle_open
    Types: DesignatorLifecycleState

Individual: lifecycle_grounded
    Types: DesignatorLifecycleState

Individual: lifecycle_accepted
    Types: DesignatorLifecycleState

Individual: lifecycle_executing
    Types: DesignatorLifecycleState

Individual: lifecycle_executed
    Types: DesignatorLifecycleState

Individual: lifecycle_failed
    Types: DesignatorLifecycleState

Individual: lifecycle_repaired
    Types: DesignatorLifecycleState

Individual: lifecycle_abstained
    Types: DesignatorLifecycleState

Individual: lifecycle_escalated
    Types: DesignatorLifecycleState

Individual: lifecycle_repairing
    Types: DesignatorLifecycleState

Individual: lifecycle_replanned
    Types: DesignatorLifecycleState

Individual: lifecycle_policy_violation
    Types: DesignatorLifecycleState

Individual: constraint_interlocks_closed
    Types: RealizationConstraint

Individual: constraint_projection_succeeds
    Types: RealizationConstraint

Individual: constraint_window_prospective
    Types: RealizationConstraint

Individual: constraint_window_kept
    Types: RealizationConstraint

Individual: constraint_identity_verified
    Types: RealizationConstraint

Individual: constraint_environment_before_store
    Types: RealizationConstraint

Individual: constraint_l12_airspace_clear
    Types: RealizationConstraint

Individual: constraint_calibration_before_imaging
    Types: RealizationConstraint

Individual: constraint_tool_compatible
    Types: RealizationConstraint

Individual: constraint_contamination_free
    Types: RealizationConstraint

Individual: constraint_reagent_bound
    Types: RealizationConstraint

Individual: constraint_dispense_completed
    Types: RealizationConstraint

Individual: constraint_challenge_requires_controls
    Types: ValidityConstraint

Individual: constraint_measurement_binding_validated
    Types: ValidityConstraint

Individual: constraint_V1_identity_continuity
    Types: ValidityConstraint

Individual: constraint_V2_calibration_at_measurement
    Types: ValidityConstraint

Individual: constraint_V3_binding_validated
    Types: ValidityConstraint

Individual: constraint_V4_controls_present
    Types: ValidityConstraint

Individual: constraint_V5_dose_delivered
    Types: ValidityConstraint

Individual: constraint_V6_sample_integrity
    Types: ValidityConstraint

Individual: constraint_V7_design_realised
    Types: ValidityConstraint

```

## Export notes

- Restrictions AICOR's exporter cannot read (negation, nested fillers, inverse roles): 0; they are kept in `build/lab-automation-twin.ofn`.
- Definitions (≡) are necessary conditions in the AICOR export (D-LAT-2).

