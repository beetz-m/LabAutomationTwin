---
type: dl-definition
title: "Cell robots, robot bodies, tools and robot skills (DL definitions)"
derived_from: L1/lab-twin-robots
maturity: L2
status: draft
timestamp: 2026-10-17
module: lab-automation-twin
---

# Cell robots, robot bodies, tools and robot skills

Cell robots (AICOR Robot), robot bodies, exchangeable tools and robot skills.

Every class is positioned under an upstream AICOR / robot-scientist / VRB / normative-admissibility concept or an AICOR upper-level stand-in (`dul:` / `soma:`). Generated from `src/tbox.py` by `build_module.py`; edit the source, not this file.

## Manchester syntax

```
ObjectProperty: hasEndEffectorMount
    -- A robot body offers an end-effector mount.

ObjectProperty: affordsRobotSkill
    -- A tool affords a robot skill when coupled.

Class: CellRobot
    SubClassOf: Robot
    SubClassOf: LabArtifact
    SubClassOf:
        servesStation some LabArtifact,
        hasRobotSkill some RobotSkill
    -- A robot of an automation cell, assigned to stations (layout P1).

Class: FixedBaseManipulator
    SubClassOf: CellRobot
    SubClassOf:
        hasProperPart some ArmRobotBody,
        not (hasDirectComponent some (LinearRail or MobileRobotBase))
    -- Arm on a fixed pedestal (R01 FR3).

Class: RailMountedManipulator
    SubClassOf: CellRobot
    SubClassOf:
        hasDirectComponent some LinearRail,
        hasProperPart some ArmRobotBody
    -- Arm on a linear rail with a tool changer (R02 UR5e).

Class: SampleTransportAMR
    SubClassOf: CellRobot
    SubClassOf:
        hasProperPart some MobileRobotBase,
        hasRobotSkill some SampleTransportSkill
    -- Clean-sample AMR with a sealed cabinet (R03, MiR100 class).

Class: ArmRobotBody
    SubClassOf: RobotBody
    SubClassOf:
        hasEndEffectorMount some EndEffector
    -- Serial arm body (FR3, UR5e).

Class: MobileRobotBase
    SubClassOf: RobotBody
    SubClassOf:
        hasDirectComponent some CabinetLid
    -- AMR base with the sample cabinet (R03).

Class: CabinetLid
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some MobileRobotBase
    -- Flat lid over the carrier nest.

Class: VirtualPlanarLink
    SubClassOf: Link
    SubClassOf:
        partOf some MobileRobotBase
    -- A simulation link of the AMR's planar base joints (twin artefact).

Class: AutomaticToolChanger
    SubClassOf: MechanismPart
    SubClassOf:
        couplesTool some ExchangeableTool
    -- Robot-side tool coupler.

Class: ExchangeableTool
    SubClassOf: LabArtifact
    SubClassOf:
        hasDirectComponent some ToolBody,
        hasInteractionPose some ToolCouplingPose
    -- End effector exchanged by a tool changer (stored in a magazine, not a robot-body link).

Class: ToolBody
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some ExchangeableTool
    -- Housing of a tool.

Class: GripperJaw
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some ExchangeableTool
    -- Jaw of a gripper tool.

Class: PlateGripperTool
    SubClassOf: ExchangeableTool
    SubClassOf:
        hasDirectComponent exactly 2 GripperJaw,
        affordsRobotSkill some PlateTransferSkill
    DisjointWith: TubeGripperTool, PipettingTool, SuctionPickupTool, CameraInspectionTool
    -- Two-jaw SBS plate gripper (T01).

Class: TubeGripperTool
    SubClassOf: ExchangeableTool
    SubClassOf:
        affordsRobotSkill some TubeHandlingSkill
    DisjointWith: PipettingTool, SuctionPickupTool, CameraInspectionTool
    -- T02.

Class: PipettingTool
    SubClassOf: ExchangeableTool
    SubClassOf:
        affordsRobotSkill some LiquidTransferSkill
    DisjointWith: SuctionPickupTool, CameraInspectionTool
    -- T03.

Class: SuctionPickupTool
    SubClassOf: ExchangeableTool
    SubClassOf:
        affordsRobotSkill some PlateTransferSkill
    DisjointWith: CameraInspectionTool
    -- T04.

Class: CameraInspectionTool
    SubClassOf: ExchangeableTool
    SubClassOf:
        affordsRobotSkill some InspectionSkill
    -- T05.

Class: RobotSkill
    SubClassOf: dul:Quality
    SubClassOf:
        functionAffords some LabTaskType
    -- A capability of a robot.

Class: PlateTransferSkill
    SubClassOf: RobotSkill
    SubClassOf:
        functionAffords some PlateTransferTask
    -- Pick, carry, place SBS plates.

Class: SampleTransportSkill
    SubClassOf: RobotSkill
    SubClassOf:
        functionAffords some PlateTransferTask
    -- Carry samples in a closed cabinet.

Class: NavigationSkill
    SubClassOf: RobotSkill
    SubClassOf:
        functionAffords some NavigationTask
    -- Navigate between docks.

Class: DockingSkill
    SubClassOf: RobotSkill
    SubClassOf:
        functionAffords some DockingTask
    -- Dock deterministically.

Class: ToolExchangeSkill
    SubClassOf: RobotSkill
    SubClassOf:
        functionAffords some ToolExchangeTask
    -- Exchange end effectors.

Class: TubeHandlingSkill
    SubClassOf: RobotSkill
    SubClassOf:
        functionAffords some PlateTransferTask
    -- Handle tubes.

Class: LiquidTransferSkill
    SubClassOf: RobotSkill
    SubClassOf:
        functionAffords some LiquidDispensingTask
    -- Pipette.

Class: InspectionSkill
    SubClassOf: RobotSkill
    SubClassOf:
        functionAffords some ImagingTask
    -- Inspect with a camera.

```

## Export notes

- Restrictions AICOR's exporter cannot read (negation, nested fillers, inverse roles): 1; they are kept in `build/lab-automation-twin.ofn`.
- Definitions (≡) are necessary conditions in the AICOR export (D-LAT-2).

