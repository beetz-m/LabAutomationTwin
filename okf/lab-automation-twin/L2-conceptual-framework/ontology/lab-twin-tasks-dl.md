---
type: dl-definition
title: "Lab task types and actions (DL definitions)"
derived_from: L1/lab-twin-tasks
maturity: L2
status: draft
timestamp: 2026-10-17
module: lab-automation-twin
---

# Lab task types and actions

Lab task types (concepts) and lab actions (events), with defined action classes.

Every class is positioned under an upstream AICOR / robot-scientist / VRB / normative-admissibility concept or an AICOR upper-level stand-in (`dul:` / `soma:`). Generated from `src/tbox.py` by `build_module.py`; edit the source, not this file.

## Manchester syntax

```
ObjectProperty: classifiesAction
    -- InverseOf: executesTaskType
    -- A task type classifies actions.

ObjectProperty: prescribesTaskType
    -- A workflow / protocol prescribes a task type as a step.

Class: LabTaskType
    SubClassOf: dul:Concept
    SubClassOf:
        classifiesAction only LabAction
    -- A type of lab work.

Class: PlateTransferTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some Labware
    DisjointWith: PlateStoringTask, PlateRetrievingTask, IncubatingTask, LiquidDispensingTask, ImagingTask, CalibratingTask, QuarantiningTask
    -- Move labware between seats. Every action of this type involves a Labware.

Class: PlateStoringTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some PlateStorageDevice
    DisjointWith: PlateRetrievingTask, IncubatingTask, LiquidDispensingTask, ImagingTask, CalibratingTask, QuarantiningTask
    -- Put a plate into a store. Every action of this type involves a PlateStorageDevice.

Class: PlateRetrievingTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some LabArtifact
    DisjointWith: IncubatingTask, LiquidDispensingTask, ImagingTask, CalibratingTask, QuarantiningTask
    -- Take a plate out of a device. Every action of this type involves a LabArtifact.

Class: IncubatingTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some IncubationDevice
    DisjointWith: LiquidDispensingTask, ImagingTask, CalibratingTask, QuarantiningTask
    -- Keep a plate in an incubator. Every action of this type involves a IncubationDevice.

Class: LiquidDispensingTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some DispensingDevice
    DisjointWith: ImagingTask, CalibratingTask, QuarantiningTask
    -- Dispense liquid into a well. Every action of this type involves a DispensingDevice.

Class: ChallengeDosingTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some DispensingDevice
    -- Dose the challenge reagent. Every action of this type involves a DispensingDevice.

Class: RescueDosingTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some DispensingDevice
    -- Dose the rescue reagent. Every action of this type involves a DispensingDevice.

Class: ImagingTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some ImagingDevice
    DisjointWith: CalibratingTask, QuarantiningTask
    -- Acquire an image. Every action of this type involves a ImagingDevice.

Class: CalibratingTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some QCCalibrationStation
    DisjointWith: QuarantiningTask
    -- Check / calibrate against a reference. Every action of this type involves a QCCalibrationStation.

Class: QuarantiningTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some QuarantineStation
    -- Contain a plate. Every action of this type involves a QuarantineStation.

Class: QuarantineReleaseTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some QuarantineStation
    -- Release a plate after authorisation. Every action of this type involves a QuarantineStation.

Class: IdentifyingTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some BarcodeReader
    -- Read a plate identity. Every action of this type involves a BarcodeReader.

Class: NavigationTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some SampleTransportAMR
    -- Drive between docks. Every action of this type involves a SampleTransportAMR.

Class: DockingTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some Dock
    -- Dock an AMR. Every action of this type involves a Dock.

Class: ToolExchangeTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some AutomaticToolChanger
    -- Couple / release a tool. Every action of this type involves a AutomaticToolChanger.

Class: TipHandlingTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some PipettingChannel
    -- Pick up / eject a tip. Every action of this type involves a PipettingChannel.

Class: ColdStoringTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some ColdStorageDevice
    -- Store material cold. Every action of this type involves a ColdStorageDevice.

Class: SterilizingTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some Autoclave
    -- Sterilise. Every action of this type involves a Autoclave.

Class: AsepticHandlingTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some BiosafetyCabinet
    -- Handle open cultures. Every action of this type involves a BiosafetyCabinet.

Class: TemperatureControllingTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some ManualLabEquipment
    -- Hold a temperature. Every action of this type involves a ManualLabEquipment.

Class: ConsumableStoringTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some StorageShelving
    -- Store consumables. Every action of this type involves a StorageShelving.

Class: CleaningTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some LabSinkUnit
    -- Wash. Every action of this type involves a LabSinkUnit.

Class: OperatorInteractionTask
    SubClassOf: LabTaskType
    SubClassOf:
        classifiesAction only hasParticipantEntity some LabArtifact
    -- A person operates equipment. Every action of this type involves a LabArtifact.

Class: LabAction
    SubClassOf: soma:Action
    SubClassOf:
        executesTaskType some LabTaskType
    -- An action of lab work.

Class: RobotAction
    SubClassOf: LabAction
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        LabAction,
        hasParticipantEntity some Robot
    -- Defined: a lab action a robot takes part in.

Class: TransferAction
    SubClassOf: LabAction
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        LabAction,
        executesTaskType some PlateTransferTask
    -- Defined: a lab action of type PlateTransferTask.

Class: StoreAction
    SubClassOf: LabAction
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        LabAction,
        executesTaskType some PlateStoringTask
    -- Defined: a lab action of type PlateStoringTask.

Class: RetrieveAction
    SubClassOf: LabAction
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        LabAction,
        executesTaskType some PlateRetrievingTask
    -- Defined: a lab action of type PlateRetrievingTask.

Class: IncubateAction
    SubClassOf: LabAction
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        LabAction,
        executesTaskType some IncubatingTask
    -- Defined: a lab action of type IncubatingTask.

Class: DoseAction
    SubClassOf: LabAction
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        LabAction,
        executesTaskType some LiquidDispensingTask
    -- Defined: a lab action of type LiquidDispensingTask.

Class: ImageAction
    SubClassOf: LabAction
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        LabAction,
        executesTaskType some ImagingTask
    -- Defined: a lab action of type ImagingTask.

Class: QCAction
    SubClassOf: LabAction
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        LabAction,
        executesTaskType some CalibratingTask
    -- Defined: a lab action of type CalibratingTask.

Class: QuarantineAction
    SubClassOf: LabAction
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        LabAction,
        executesTaskType some QuarantiningTask
    -- Defined: a lab action of type QuarantiningTask.

Class: AMRTransferAction
    SubClassOf: TransferAction
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        TransferAction,
        hasParticipantEntity some SampleTransportAMR
    -- Defined: a transfer by the sample AMR.

```

## Export notes

- Restrictions AICOR's exporter cannot read (negation, nested fillers, inverse roles): 23; they are kept in `build/lab-automation-twin.ofn`.
- Definitions (≡) are necessary conditions in the AICOR export (D-LAT-2).

