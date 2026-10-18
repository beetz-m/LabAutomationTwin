---
type: dl-definition
title: "Poses: coordinate and interaction frames of the twin (AICOR SpatialPose) (DL definitions)"
derived_from: L1/lab-twin-poses
maturity: L2
status: draft
timestamp: 2026-10-17
module: lab-automation-twin
---

# Poses: coordinate and interaction frames of the twin (AICOR SpatialPose)

Named poses of the twin (USD Xform frames) as AICOR SpatialPoses, typed by the task they afford.

Every class is positioned under an upstream AICOR / robot-scientist / VRB / normative-admissibility concept or an AICOR upper-level stand-in (`dul:` / `soma:`). Generated from `src/tbox.py` by `build_module.py`; edit the source, not this file.

## Manchester syntax

```
Class: TwinPose
    SubClassOf: SpatialPose
    SubClassOf:
        isPoseOf some dul:PhysicalObject
    -- A named pose on an object (USD Xform).

Class: KinematicPose
    SubClassOf: TwinPose
    SubClassOf:
        isPoseOf some LabArtifact
    -- Reference pose of a link or mechanism.

Class: InteractionPose
    SubClassOf: TwinPose
    SubClassOf:
        affordsTaskType some LabTaskType
    -- Pose where a task is performed.

Class: PlateSeatPose
    SubClassOf: InteractionPose
    SubClassOf:
        affordsTaskType some (PlateTransferTask or PlateStoringTask)
    DisjointWith: ApproachPose, DockPose, ToolCenterPose, ToolCouplingPose, PipettingTargetPose, ImagingTargetPose, RackPositionPose, WastePose, CalibrationPose
    -- SBS plate seat.

Class: ApproachPose
    SubClassOf: InteractionPose
    SubClassOf:
        affordsTaskType some (NavigationTask or PlateTransferTask)
    DisjointWith: DockPose, ToolCenterPose, ToolCouplingPose, PipettingTargetPose, ImagingTargetPose, RackPositionPose, WastePose, CalibrationPose
    -- Pose reached before an interaction.

Class: DockPose
    SubClassOf: InteractionPose
    SubClassOf:
        affordsTaskType some DockingTask
    DisjointWith: ToolCenterPose, ToolCouplingPose, PipettingTargetPose, ImagingTargetPose, RackPositionPose, WastePose, CalibrationPose
    -- Pose of a docked AMR.

Class: ToolCenterPose
    SubClassOf: InteractionPose
    SubClassOf:
        affordsTaskType some PlateTransferTask
    DisjointWith: ToolCouplingPose, PipettingTargetPose, ImagingTargetPose, RackPositionPose, WastePose, CalibrationPose
    -- Tool centre point.

Class: ToolCouplingPose
    SubClassOf: InteractionPose
    SubClassOf:
        affordsTaskType some ToolExchangeTask
    DisjointWith: PipettingTargetPose, ImagingTargetPose, RackPositionPose, WastePose, CalibrationPose
    -- Coupling face of a tool or changer.

Class: PipettingTargetPose
    SubClassOf: InteractionPose
    SubClassOf:
        affordsTaskType some LiquidDispensingTask
    DisjointWith: ImagingTargetPose, RackPositionPose, WastePose, CalibrationPose
    -- Where a channel doses into a well.

Class: ImagingTargetPose
    SubClassOf: InteractionPose
    SubClassOf:
        affordsTaskType some ImagingTask
    DisjointWith: RackPositionPose, WastePose, CalibrationPose
    -- Where a well is imaged.

Class: RackPositionPose
    SubClassOf: InteractionPose
    SubClassOf:
        affordsTaskType some (LiquidDispensingTask or TipHandlingTask)
    DisjointWith: WastePose, CalibrationPose
    -- Rack position.

Class: WastePose
    SubClassOf: InteractionPose
    SubClassOf:
        affordsTaskType some TipHandlingTask
    DisjointWith: CalibrationPose
    -- Tip ejection.

Class: CalibrationPose
    SubClassOf: InteractionPose
    SubClassOf:
        affordsTaskType some CalibratingTask
    -- Datum for QC / calibration.

Class: StorageLocationPose
    SubClassOf: InteractionPose
    SubClassOf:
        affordsTaskType some (ConsumableStoringTask or ColdStoringTask)
    -- Shelf location.

Class: ManipulationPointPose
    SubClassOf: InteractionPose
    SubClassOf:
        affordsTaskType some OperatorInteractionTask
    -- Handle, door, lid, sash, tap, button.

Class: OperatorPositionPose
    SubClassOf: InteractionPose
    SubClassOf:
        affordsTaskType some OperatorInteractionTask
    -- Where a person works.

Class: ItemAccessPose
    SubClassOf: InteractionPose
    SubClassOf:
        affordsTaskType some PlateTransferTask
    -- Where a person takes or puts an item.

Class: CleaningPointPose
    SubClassOf: InteractionPose
    SubClassOf:
        affordsTaskType some CleaningTask
    -- Sink basin, eyewash.

Class: OpticalPose
    SubClassOf: TwinPose
    SubClassOf:
        isPoseOf some (ImagingDevice or MechanismPart or CellRobot)
    -- Objective, camera or focal-point pose.

Class: IlluminationPose
    SubClassOf: OpticalPose
    SubClassOf:
        isPoseOf some ImagingDevice
    -- Illumination axis.

Class: ViewpointPose
    SubClassOf: TwinPose
    SubClassOf:
        isPoseOf some dul:PhysicalPlace
    -- Viewpoint of a virtual twin camera.

```

## Export notes

- Restrictions AICOR's exporter cannot read (negation, nested fillers, inverse roles): 0; they are kept in `build/lab-automation-twin.ofn`.
- Definitions (≡) are necessary conditions in the AICOR export (D-LAT-2).

