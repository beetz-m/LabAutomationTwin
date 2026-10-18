# Class-level partonomy (derived from the axioms)

`hasDirectComponent` (simple, ⊑ AICOR hasComponent) under `hasPhysicalPart` (transitive, ⊑ AICOR hasPart); places: `hasSubPlace`; containment (`containsMaterial`) is listed separately - it is not parthood.

## component

| Whole | Part | Axiom |
|---|---|---|
| AutomatedCO2Incubator | IncubationChamber | ∃ |
| AutomatedLiquidHandler | GantryAxis | ∃ |
| AutomatedPlateHotel | InternalPlateHandler | ∃ |
| AutomatedPlateHotel | PlateShuttle | ∃ |
| AutomationBench | Worktop | ∃ |
| AutomationCell | LabAutomationDevice | ∃ |
| AutomationCell | Robot | ∃ |
| BrightFieldImager | FocusDrive | ∃ |
| BrightFieldImager | MotorizedStage | ∃ |
| CulturePlate | CultureWell | ∃ |
| DeterministicAMRDock | DockSensor | ∃ |
| DispensingDevice | GantryAxis | inverse |
| ExchangeableTool | GripperJaw | inverse |
| ExchangeableTool | ToolBody | ∃ |
| FitOutAssembly | AutomationBench | ∃ |
| FitOutAssembly | RailCover | ∃ |
| FitOutAssembly | StationSupport | ∃ |
| FocusDrive | ObjectiveTurret | ∃ |
| GantryAxis | GantryAxis | inverse |
| HandoverNest | SeatSensor | ∃ |
| ImagingDevice | MotorizedStage | inverse |
| IncubationDevice | IncubationChamber | inverse |
| InternalPlateHandler | PlateFork | ∃ |
| KeySwitch | KeyCylinder | ∃ |
| LabArtifact | AprilTagMarker | inverse |
| LabArtifact | DatumPin | inverse |
| LabArtifact | EmergencyStop | inverse |
| LabArtifact | HMIPanel | inverse |
| LabArtifact | MechanismPart | inverse |
| LabArtifact | OperatorControl | inverse |
| LabAutomationDevice | AccessGate | inverse |
| LabAutomationDevice | ServiceDoor | inverse |
| LabAutomationDevice | StationHood | inverse |
| LabAutomationDevice | StationHousing | inverse |
| LabAutomationDevice | ThroughBeamSensor | inverse |
| LabBench | Worktop | ∃ |
| LabBuildingShell | LabDoor | ∃ |
| LabDoor | DoorFrame | inverse |
| LabDoor | DoorLeaf | ∃ |
| LinearRail | RailCarriage | ∃ |
| MagazineStand | SlotOccupancySensor | ∃ |
| Microplate | Well | ∃ |
| MobileRobotBase | CabinetLid | ∃ |
| MobileRobotBase | CarrierPresenceSensor | inverse |
| MotorizedStage | MotorizedStage | inverse |
| PlateCassette | PlateSlot | ∃ |
| PlateGripperTool | GripperJaw | =2 |
| PlateShuttle | SeatSensor | ∃ |
| PlateSlot | SlotOccupancySensor | ∃ |
| PlateStorageDevice | PlateCassette | ∃ |
| PushButton | ButtonPlunger | ∃ |
| QCCalibrationStation | LightBarrierSensor | ∃ |
| QuarantineStation | KeySwitch | ∃ |
| QuarantineStation | LatchBolt | inverse |
| QuarantineStation | LockableDoor | ∃ |
| RailMountedManipulator | LinearRail | ∃ |
| RobotExperimentCell | CellRobot | ∃ |
| RobotExperimentCell | LabAutomationDevice | ∃ |
| RobotExperimentCell | SafetyEnclosure | ∃ |
| SBSMicroplate96 | Well | =96 |
| SafetyEnclosure | AMRPortal | inverse |
| SafetyEnclosure | EmergencyStop | ∃ |
| SafetyEnclosure | LabDoor | ∃ |
| ToolMagazine | MagazineStand | ∃ |

## part

| Whole | Part | Axiom |
|---|---|---|
| AutomatedLiquidHandler | PipettingChannel | ∃ |
| BrightFieldImager | ObjectiveTurret | ∃ |
| FixedBaseManipulator | ArmRobotBody | ∃ |
| PottedPlant | BiologicalSpecimen | ∃ |
| RailMountedManipulator | ArmRobotBody | ∃ |
| SampleTransportAMR | MobileRobotBase | ∃ |

## subplace

| Whole | Part | Axiom |
|---|---|---|
| LabPremises | LabRoom | ∃ |
| LabPremises | LabZone | inverse |
| LabRoom | LabZone | inverse |
| dul:PhysicalPlace | dul:PhysicalPlace | ∃ |

## contains

| Whole | Part | Axiom |
|---|---|---|
| CultureWell | CultureMediumPortion | ∃ |
| Labware | ReagentPortion | inverse |
| Well | CultureMediumPortion | inverse |

