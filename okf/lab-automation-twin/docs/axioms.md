# lab-automation-twin: concepts and their description-logic axioms

An AICOR OKF module (2026-10-17). Names are AICOR L2 names (one namespace, `http://aicor.knowledge/l2-ontology.owl#`); `dul:` / `soma:` are AICOR's upper-level stand-ins. Superclasses that are not defined here come from the frozen AICOR core, the robot-scientist vertical, VRB or normative-admissibility. ⊑ necessary condition, ≡ definition, ⁻ inverse role. Modality of each concept's basis: ✅ stated in a cited source / verified in the twin, 🔧 engineering inference.

412 concepts, 176 properties, 22 disjointness axioms, 13 modules.

## Modules

- [Properties, upper-level placements and the SDT node / referent split](#properties-upper-level-placements-and-the-sdt-node--referent-split) (`lab-twin-core`)
- [Laboratory site, premises, rooms, zones, building elements and fit-out](#laboratory-site-premises-rooms-zones-building-elements-and-fit-out) (`lab-twin-site`)
- [Laboratory devices, automated stations, mechanisms and device sensors](#laboratory-devices-automated-stations-mechanisms-and-device-sensors) (`lab-twin-devices`)
- [Cell robots, robot bodies, tools and robot skills](#cell-robots-robot-bodies-tools-and-robot-skills) (`lab-twin-robots`)
- [Labware, wells and material portions](#labware-wells-and-material-portions) (`lab-twin-labware`)
- [Poses: coordinate and interaction frames of the twin (AICOR SpatialPose)](#poses-coordinate-and-interaction-frames-of-the-twin-aicor-spatialpose) (`lab-twin-poses`)
- [Lab task types and actions](#lab-task-types-and-actions) (`lab-twin-tasks`)
- [Device manual knowledge (Cell 01 component contracts) and device process knowledge](#device-manual-knowledge-cell-01-component-contracts-and-device-process-knowledge) (`lab-twin-device-manuals`)
- [Safe action: hazards, safety rules, enforcement, admissibility of candidate actions](#safe-action-hazards-safety-rules-enforcement-admissibility-of-candidate-actions) (`lab-twin-safe-action`)
- [Culture experiments: designs, arms, interventions, readouts, runs, conclusions](#culture-experiments-designs-arms-interventions-readouts-runs-conclusions) (`lab-twin-culture-experiments`)
- [Action records, monitor results and routing (Cell 01 NEEM records)](#action-records-monitor-results-and-routing-cell-01-neem-records) (`lab-twin-records`)
- [From a required information gain to the robot's physical actions and motions (derivation layer)](#from-a-required-information-gain-to-the-robots-physical-actions-and-motions-derivation-layer) (`lab-twin-experiment-to-motion`)
- [The robot science assistant kernel: action-designator categories, lifecycle and audit entries](#the-robot-science-assistant-kernel-action-designator-categories-lifecycle-and-audit-entries) (`lab-twin-rsa-kernel`)

## Properties, upper-level placements and the SDT node / referent split

`lab-twin-core-dl.md` — Properties of the module (partonomy, location, containment, poses, SDT node -> referent) and the SDT node classes. AICOR's mereology properties are bare and frozen, so the module adds sub-properties with the characteristics it needs.

### dul:PhysicalPlace 🔧

(stand-in) a place with a physical extent; its sub-places are places (DUL: PhysicalPlace ⊑ PhysicalObject).

```text
dul:PhysicalPlace ⊑ dul:PhysicalObject
dul:PhysicalPlace ⊑ ∃hasSubPlace.dul:PhysicalPlace
```

### LabArtifact ✅

A designed physical object of the lab that the twin represents.

```text
LabArtifact ⊑ dul:PhysicalObject
LabArtifact ⊑ ∃isRepresentedBy.LabSDTNode
```

### LabSDTNode ✅

A node of the lab's semantic digital twin (one USD prim): information that represents one entity.

```text
LabSDTNode ⊑ SceneNode
LabSDTNode ⊑ ∃representsEntity.Entity
LabSDTNode ⊑ ∃usdPrimPath.xsd:string
```

### GroupingNode 🔧

A structural SDT node (USD scope / xform) that groups child nodes; it represents the grouping only.

```text
GroupingNode ⊑ LabSDTNode
GroupingNode ⊑ ∃hasChildNode.LabSDTNode
```

### LabSemanticDigitalTwin ✅

The semantic digital twin of a laboratory site: the belief state about it, structured as a USD scene graph.

```text
LabSemanticDigitalTwin ⊑ SemanticDigitalTwin
LabSemanticDigitalTwin ⊑ ∃hasNodeStructure.LabSceneHierarchy
```

### LabSceneHierarchy ✅

The USD namespace hierarchy of the lab twin (lab_twin.usda + culture layer).

```text
LabSceneHierarchy ⊑ HierarchicalSceneStructure
LabSceneHierarchy ⊑ ∃hasNode.LabSDTNode
```

### SimulationSettings ✅

Physics or rendering settings of the twin (physics scene, sky and sun lights).

```text
SimulationSettings ⊑ dul:Description
SimulationSettings ⊑ ∃configures.LabSemanticDigitalTwin
```

### SimulationSettingsNode ✅

An SDT node holding settings.

```text
SimulationSettingsNode ⊑ LabSDTNode
SimulationSettingsNode ⊑ ∃representsEntity.SimulationSettings
```

### RenderRepresentationNode 🔧

A render-only USD prim (looks, materials, collision / visual geometry): representation, not SDT knowledge.

```text
RenderRepresentationNode ⊑ SceneNode
RenderRepresentationNode ⊑ ¬LabSDTNode
```

## Laboratory site, premises, rooms, zones, building elements and fit-out

`lab-twin-site-dl.md` — The laboratory site (robot-scientist LaboratorySite / LaboratoryCell), its premises, rooms and zones (layout S1), building elements, the Cell 01 fit-out and the site's safety and service equipment.

### AutomatedBiologyLab ✅

A laboratory site that comprises at least one robot experiment cell (AICOR Lab 1).

```text
AutomatedBiologyLab ⊑ LaboratorySite
AutomatedBiologyLab ⊑ ∃comprisesCell.RobotExperimentCell
AutomatedBiologyLab ⊑ ∃locatedAt.LabPremises
```

### LabPremises 🔧

The floor area of a laboratory site.

```text
LabPremises ⊑ dul:PhysicalPlace
LabPremises ⊑ ∃hasSubPlace.LabRoom
```

### LabRoom 🔧

A room of the premises.

```text
LabRoom ⊑ dul:PhysicalPlace
LabRoom ⊑ ∃isSubPlaceOf.LabPremises
```

### LabHall 🔧

The hall in which automation cells stand.

```text
LabHall ⊑ LabRoom
LabHall ⊑ ∃hostsObject.LaboratoryCell
```

### StorageRoom 🔧

A room for consumables, reagents and cold storage (ST01).

```text
StorageRoom ⊑ LabRoom
StorageRoom ⊑ ∃hostsObject.(ColdStorageDevice ⊔ StorageShelving)
```

### LabZone 🔧

A functional area (layout S1).

```text
LabZone ⊑ dul:PhysicalPlace
LabZone ⊑ ∃isSubPlaceOf.(LabRoom ⊔ LabPremises)
```

### EntranceZone 🔧

Entrance and gowning.

```text
EntranceZone ⊑ LabZone
EntranceZone ⊑ ∃hostsObject.PPEStation
EntranceZone ⊓ OperatorArea ⊑ ⊥
```

### OperatorArea 🔧

Monitoring and engineering desks.

```text
OperatorArea ⊑ LabZone
OperatorArea ⊑ ∃hostsObject.OperatorWorkstation
OperatorArea ⊓ EntranceZone ⊑ ⊥
```

### CulturePrepArea 🔧

Manual culture work upstream.

```text
CulturePrepArea ⊑ LabZone
CulturePrepArea ⊑ ∃hostsObject.BiosafetyCabinet
CulturePrepArea ⊓ EntranceZone ⊑ ⊥
```

### WashWasteArea 🔧

Sterilisation and waste.

```text
WashWasteArea ⊑ LabZone
WashWasteArea ⊑ ∃hostsObject.(Autoclave ⊔ WasteStation)
WashWasteArea ⊓ EntranceZone ⊑ ⊥
```

### CellZone 🔧

Floor envelope of an automation cell.

```text
CellZone ⊑ LabZone
CellZone ⊑ ∃hostsObject.LaboratoryCell
CellZone ⊓ EntranceZone ⊑ ⊥
```

### ServiceCorridor 🔧

Technician access to the rear instruments.

```text
ServiceCorridor ⊑ LabZone
ServiceCorridor ⊑ ∃adjoinsZone.CellZone
ServiceCorridor ⊓ EntranceZone ⊑ ⊥
```

### LogisticsArea 🔧

The AMR lane and walkway to the cell portal.

```text
LogisticsArea ⊑ LabZone
LogisticsArea ⊑ ∃adjoinsZone.CellZone
LogisticsArea ⊓ EntranceZone ⊑ ⊥
```

### LabCeiling 🔧

Ceiling with services.

```text
LabCeiling ⊑ dul:PhysicalPlace
LabCeiling ⊑ ∃hostsObject.BuildingServiceDevice
```

### LabBuildingShell 🔧

Walls, doors, windows and services.

```text
LabBuildingShell ⊑ LabArtifact
LabBuildingShell ⊑ ∃hasDirectComponent.LabDoor
```

### LabDoor 🔧

A door with a moving leaf.

```text
LabDoor ⊑ LabArtifact
LabDoor ⊑ ∃hasDirectComponent.DoorLeaf
```

### HingedDoor 🔧

Leaf swings on a hinge.

```text
HingedDoor ⊑ LabDoor
HingedDoor ⊑ ∃hasDirectComponent.∃hasMechanismJointType.Revolute
HingedDoor ⊓ SlidingDoor ⊑ ⊥
```

### SlidingDoor 🔧

Leaf slides.

```text
SlidingDoor ⊑ LabDoor
SlidingDoor ⊑ ∃hasDirectComponent.∃hasMechanismJointType.Prismatic
SlidingDoor ⊓ HingedDoor ⊑ ⊥
```

### InterlockedDoor ✅

A door whose open state gates safe robot motion.

```text
InterlockedDoor ⊑ LabDoor
InterlockedDoor ⊑ ∃isMonitoredBy.DoorInterlockSwitch
```

### DoorLeaf 🔧

The moving panel of a door.

```text
DoorLeaf ⊑ MechanismPart
DoorLeaf ⊑ ∃isDirectComponentOf.LabDoor
```

### DoorFrame 🔧

The fixed frame of a door.

```text
DoorFrame ⊑ MechanismPart
DoorFrame ⊑ ∃isDirectComponentOf.LabDoor
```

### AMRRoute ✅

A navigation route of an AMR between docks (a USD curve).

```text
AMRRoute ⊑ SpatialPose
AMRRoute ⊑ ∃affordsTaskType.NavigationTask
AMRRoute ⊑ ∃startsAt.Dock
AMRRoute ⊑ ∃endsAt.Dock
```

### RobotExperimentCell ✅

An automation cell of robots and automated stations behind a safety enclosure (Cell 01).

```text
RobotExperimentCell ⊑ LaboratoryCell
RobotExperimentCell ⊑ ∃hasDirectComponent.CellRobot
RobotExperimentCell ⊑ ∃hasDirectComponent.LabAutomationDevice
RobotExperimentCell ⊑ ∃hasDirectComponent.SafetyEnclosure
```

### AutomationCell 🔧

Defined: a laboratory cell with robots and automated devices as direct components.

```text
AutomationCell ⊑ LaboratoryCell
AutomationCell ≡ LaboratoryCell ⊓ ∃hasDirectComponent.Robot ⊓ ∃hasDirectComponent.LabAutomationDevice
```

### SafetyEnclosure ✅

Guard enclosure bounding the robot envelope: glazed sides, interlocked doors, e-stops (spec §4.1).

```text
SafetyEnclosure ⊑ LabArtifact
SafetyEnclosure ⊑ ∃hasDirectComponent.LabDoor
SafetyEnclosure ⊑ ∃hasDirectComponent.EmergencyStop
```

### AMRPortal ✅

Opening in the enclosure for the sample AMR, guarded by a muted light curtain.

```text
AMRPortal ⊑ MechanismPart
AMRPortal ⊑ ∃isDirectComponentOf.SafetyEnclosure
AMRPortal ⊑ ∃isMonitoredBy.LightCurtain
```

### HMIPanel 🔧

Operator touch panel.

```text
HMIPanel ⊑ MechanismPart
HMIPanel ⊑ ∃isDirectComponentOf.LabArtifact
```

### Worktop 🔧

The working surface of a bench.

```text
Worktop ⊑ MechanismPart
Worktop ⊑ ∃isDirectComponentOf.(AutomationBench ⊔ LabBench)
```

### AutomationBench ✅

Machine bench carrying stations at transfer height (spec §4.2).

```text
AutomationBench ⊑ LabArtifact
AutomationBench ⊑ ∃hasDirectComponent.Worktop
AutomationBench ⊑ ∃supportsObject.LabAutomationDevice
```

### StationSupport 🔧

Plinth or side table carrying a station at its transfer height.

```text
StationSupport ⊑ LabArtifact
StationSupport ⊑ ∃supportsObject.LabArtifact
```

### VibrationIsolatedSupport ✅

Support decoupled from the bench (imaging sub-base).

```text
VibrationIsolatedSupport ⊑ StationSupport
VibrationIsolatedSupport ⊑ ∃supportsObject.ImagingDevice
```

### RailCover 🔧

Cover over a robot rail.

```text
RailCover ⊑ MechanismPart
RailCover ⊑ ∃coversObject.LinearRail
```

### StationHood 🔧

Glazed hood over a station deck.

```text
StationHood ⊑ MechanismPart
StationHood ⊑ ∃isDirectComponentOf.LabAutomationDevice
```

### FitOutAssembly 🔧

The cell's furniture and covers as installed.

```text
FitOutAssembly ⊑ LabArtifact
FitOutAssembly ⊑ ∃hasDirectComponent.(StationSupport ⊔ AutomationBench ⊔ RailCover)
```

### SafetyDevice 🔧

Equipment whose function is safety.

```text
SafetyDevice ⊑ LabArtifact
SafetyDevice ⊑ ∃mitigatesHazard.LabHazard
```

### EmergencyStop ✅

Latching e-stop button.

```text
EmergencyStop ⊑ SafetyDevice
EmergencyStop ⊑ MechanismPart
EmergencyStop ⊑ ∃isDirectComponentOf.LabArtifact
```

### LightCurtain ✅

Optical safety curtain across the portal; muting admits the AMR only.

```text
LightCurtain ⊑ SafetyDevice
LightCurtain ⊑ DeviceSensor
LightCurtain ⊑ ∃monitorsEntity.AMRPortal
```

### DoorInterlockSwitch ✅

Door switch that withholds safe motion while the door is open.

```text
DoorInterlockSwitch ⊑ SafetyDevice
DoorInterlockSwitch ⊑ DeviceSensor
DoorInterlockSwitch ⊑ ∃monitorsEntity.LabDoor
```

### FireSafetyDevice 🔧

Fire detection or suppression.

```text
FireSafetyDevice ⊑ SafetyDevice
FireSafetyDevice ⊑ ∃mitigatesHazard.FireHazard
```

### SprinklerHead 🔧

Pendent sprinkler head.

```text
SprinklerHead ⊑ FireSafetyDevice
SprinklerHead ⊑ ∃locatedAt.LabCeiling
SprinklerHead ⊓ SmokeDetector ⊑ ⊥
```

### SmokeDetector 🔧

Ceiling smoke detector.

```text
SmokeDetector ⊑ FireSafetyDevice
SmokeDetector ⊑ DeviceSensor
SmokeDetector ⊑ ∃locatedAt.LabCeiling
SmokeDetector ⊓ SprinklerHead ⊑ ⊥
```

### FireExtinguisher 🔧

Portable extinguisher.

```text
FireExtinguisher ⊑ FireSafetyDevice
FireExtinguisher ⊑ ∃locatedAt.dul:PhysicalPlace
FireExtinguisher ⊓ SprinklerHead ⊑ ⊥
```

### FirstAidBox 🔧

First-aid cabinet.

```text
FirstAidBox ⊑ SafetyDevice
FirstAidBox ⊑ ∃locatedAt.dul:PhysicalPlace
```

### EmergencyShower 🔧

Drench shower.

```text
EmergencyShower ⊑ SafetyDevice
EmergencyShower ⊑ ∃mitigatesHazard.ChemicalExposureHazard
```

### O2DepletionMonitor 🔧

Oxygen-depletion monitor guarding cryogen / gas storage.

```text
O2DepletionMonitor ⊑ SafetyDevice
O2DepletionMonitor ⊑ DeviceSensor
O2DepletionMonitor ⊑ ∃mitigatesHazard.AsphyxiationHazard
```

### AccessControlReader 🔧

Card reader releasing a door.

```text
AccessControlReader ⊑ SafetyDevice
AccessControlReader ⊑ ∃monitorsEntity.LabDoor
```

### BuildingServiceDevice 🔧

Technical building equipment.

```text
BuildingServiceDevice ⊑ LabArtifact
BuildingServiceDevice ⊑ ∃locatedAt.dul:PhysicalPlace
```

### HVACDiffuser 🔧

Supply-air diffuser.

```text
HVACDiffuser ⊑ BuildingServiceDevice
HVACDiffuser ⊑ ∃locatedAt.LabCeiling
```

### CeilingLuminaire 🔧

LED ceiling panel.

```text
CeilingLuminaire ⊑ BuildingServiceDevice
CeilingLuminaire ⊑ ∃locatedAt.LabCeiling
```

### ServerRack 🔧

Rack hosting the twin's compute.

```text
ServerRack ⊑ BuildingServiceDevice
ServerRack ⊑ ∃hostsSoftware.LabSemanticDigitalTwin
```

### GloveDispenser 🔧

Glove box holder.

```text
GloveDispenser ⊑ LabArtifact
GloveDispenser ⊑ ∃locatedAt.LabZone
```

### LabCoatRack 🔧

Coat hooks.

```text
LabCoatRack ⊑ LabArtifact
LabCoatRack ⊑ ∃locatedAt.EntranceZone
```

### PPEStation 🔧

Defined: a PPE station.

```text
PPEStation ⊑ LabArtifact
PPEStation ≡ GloveDispenser ⊔ LabCoatRack
```

### PottedPlant 🔧

Decor (a plant is not a designed artifact).

```text
PottedPlant ⊑ dul:PhysicalObject
PottedPlant ⊑ ∃hasPhysicalPart.BiologicalSpecimen
PottedPlant ⊑ ¬LabArtifact
```

### Whiteboard 🔧

Wall whiteboard.

```text
Whiteboard ⊑ LabArtifact
Whiteboard ⊑ ∃locatedAt.LabZone
```

### LabBench 🔧

Laboratory bench.

```text
LabBench ⊑ LabArtifact
LabBench ⊑ ∃hasDirectComponent.Worktop
```

### AMRDispatchBench 🔧

Bench where staff stage AMR carriers (S1).

```text
AMRDispatchBench ⊑ LabBench
AMRDispatchBench ⊑ ∃locatedAt.StorageRoom
```

### StorageShelving 🔧

Shelving with addressable locations.

```text
StorageShelving ⊑ LabArtifact
StorageShelving ⊑ ∃locatedAt.dul:PhysicalPlace
```

### PipetteCarousel 🔧

Manual pipette stand.

```text
PipetteCarousel ⊑ LabArtifact
PipetteCarousel ⊑ ∃locatedAt.LabZone
```

### LabSinkUnit 🔧

Sink with tap and eyewash.

```text
LabSinkUnit ⊑ LabArtifact
LabSinkUnit ⊑ ∃hasEquipmentFunction.WashingFunction
```

### WasteStation 🔧

Segregated waste and sharps bins.

```text
WasteStation ⊑ LabArtifact
WasteStation ⊑ ∃locatedAt.WashWasteArea
```

### OperatorWorkstation 🔧

Desk with monitors.

```text
OperatorWorkstation ⊑ LabArtifact
OperatorWorkstation ⊑ ∃locatedAt.OperatorArea
```

### LabStool 🔧

Lab stool.

```text
LabStool ⊑ LabArtifact
LabStool ⊑ ∃locatedAt.LabZone
```

## Laboratory devices, automated stations, mechanisms and device sensors

`lab-twin-devices-dl.md` — Automated stations as VRB LabAutomationDevices, the site's manual equipment, and the mechanisms and sensors of devices (not AICOR robot-body links or sensors: D-LAT-1).

### PlateStorageFunction ✅

Store / buffer plates.

```text
PlateStorageFunction ⊑ DeviceFunction
PlateStorageFunction ⊑ ∃functionAffords.PlateStoringTask
```

### QuarantineFunction ✅

Contain suspect material.

```text
QuarantineFunction ⊑ DeviceFunction
QuarantineFunction ⊑ ∃functionAffords.QuarantiningTask
```

### CalibrationFunction ✅

Validate a measurement chain.

```text
CalibrationFunction ⊑ DeviceFunction
CalibrationFunction ⊑ ∃functionAffords.CalibratingTask
```

### IdentificationFunction ✅

Read labware identity.

```text
IdentificationFunction ⊑ DeviceFunction
IdentificationFunction ⊑ ∃functionAffords.IdentifyingTask
```

### ColdStorageFunction 🔧

Keep material cold.

```text
ColdStorageFunction ⊑ DeviceFunction
ColdStorageFunction ⊑ ∃functionAffords.ColdStoringTask
```

### SterilizationFunction 🔧

Sterilise material.

```text
SterilizationFunction ⊑ DeviceFunction
SterilizationFunction ⊑ ∃functionAffords.SterilizingTask
```

### AsepticWorkFunction 🔧

Protect open cultures.

```text
AsepticWorkFunction ⊑ DeviceFunction
AsepticWorkFunction ⊑ ∃functionAffords.AsepticHandlingTask
```

### TemperatureControlFunction 🔧

Hold a sample at temperature.

```text
TemperatureControlFunction ⊑ DeviceFunction
TemperatureControlFunction ⊑ ∃functionAffords.TemperatureControllingTask
```

### PlateStorageDevice 🔧

Defined: an automated device that stores plates in a cassette.

```text
PlateStorageDevice ⊑ LabAutomationDevice
PlateStorageDevice ⊑ LabArtifact
PlateStorageDevice ≡ LabAutomationDevice ⊓ ∃hasDirectComponent.PlateCassette
PlateStorageDevice ⊓ DispensingDevice ⊑ ⊥
```

### AutomatedPlateHotel ✅

Ambient automated plate store (L09, LiCONiC LPE220 baseline).

```text
AutomatedPlateHotel ⊑ PlateStorageDevice
AutomatedPlateHotel ⊑ ∃hasDeviceFunction.PlateStorageFunction
AutomatedPlateHotel ⊑ ∃hasDirectComponent.PlateShuttle
AutomatedPlateHotel ⊑ ∃hasDirectComponent.InternalPlateHandler
AutomatedPlateHotel ⊑ ¬∃hasDirectComponent.IncubationChamber
AutomatedPlateHotel ⊓ AutomatedCO2Incubator ⊑ ⊥
```

### AutomatedCO2Incubator ✅

Robot-accessible CO2 incubator (L10, LiCONiC STX44-SA baseline).

```text
AutomatedCO2Incubator ⊑ IncubationDevice
AutomatedCO2Incubator ⊑ PlateStorageDevice
AutomatedCO2Incubator ⊑ ∃hasDirectComponent.IncubationChamber
AutomatedCO2Incubator ⊑ ∃declaresSetpoint.OperatingSetpoint
AutomatedCO2Incubator ⊓ AutomatedPlateHotel ⊑ ⊥
```

### AutomatedLiquidHandler ✅

Gantry liquid handler (L12, Hamilton ZEUS LT baseline).

```text
AutomatedLiquidHandler ⊑ DispensingDevice
AutomatedLiquidHandler ⊑ LabArtifact
AutomatedLiquidHandler ⊑ ∃hasDirectComponent.GantryAxis
AutomatedLiquidHandler ⊑ ∃hasPhysicalPart.PipettingChannel
```

### BrightFieldImager ✅

Bright-field imager (L17, OpenFlexure-derived).

```text
BrightFieldImager ⊑ ImagingDevice
BrightFieldImager ⊑ LabArtifact
BrightFieldImager ⊑ ∃hasDirectComponent.MotorizedStage
BrightFieldImager ⊑ ∃hasDirectComponent.FocusDrive
BrightFieldImager ⊑ ∃hasPhysicalPart.ObjectiveTurret
```

### QCCalibrationStation ✅

QC / calibration bench with reference artifacts (L21).

```text
QCCalibrationStation ⊑ LabAutomationDevice
QCCalibrationStation ⊑ LabArtifact
QCCalibrationStation ⊑ ∃hasDeviceFunction.CalibrationFunction
QCCalibrationStation ⊑ ∃hasDirectComponent.LightBarrierSensor
QCCalibrationStation ⊓ PlateStorageDevice ⊑ ⊥
```

### QuarantineStation ✅

Lockable quarantine store (H4).

```text
QuarantineStation ⊑ LabAutomationDevice
QuarantineStation ⊑ LabArtifact
QuarantineStation ⊑ ∃hasDeviceFunction.QuarantineFunction
QuarantineStation ⊑ ∃hasDirectComponent.LockableDoor
QuarantineStation ⊑ ∃hasDirectComponent.KeySwitch
QuarantineStation ⊓ PlateStorageDevice ⊑ ⊥
```

### Dock 🔧

A place an AMR docks at.

```text
Dock ⊑ LabArtifact
Dock ⊑ ∃hasInteractionPose.DockPose
```

### DeterministicAMRDock ✅

V-guide dock with pose sensors (H2).

```text
DeterministicAMRDock ⊑ Dock
DeterministicAMRDock ⊑ ∃hasDirectComponent.DockSensor
```

### DispatchDock ✅

Loading / charging dock in the storage room (S1).

```text
DispatchDock ⊑ Dock
DispatchDock ⊑ ∃locatedAt.StorageRoom
```

### ToolMagazine ✅

Automatic tool magazine (TCM01, Zimmer WMR2063 baseline).

```text
ToolMagazine ⊑ LabArtifact
ToolMagazine ⊑ ∃hasDirectComponent.MagazineStand
ToolMagazine ⊑ ∃storesTool.ExchangeableTool
```

### PassiveFixture 🔧

A fixture with no moving joints.

```text
PassiveFixture ⊑ LabArtifact
PassiveFixture ⊑ ¬∃hasDirectComponent.MechanismJoint
```

### HandoverNest ✅

Passive nest where two robots hand a plate over (R01/R02).

```text
HandoverNest ⊑ PassiveFixture
HandoverNest ⊑ ∃hasDirectComponent.SeatSensor
HandoverNest ⊑ ≥2 isServedByRobot.Robot
```

### ManualLabEquipment 🔧

Laboratory equipment operated by people, with no robot control interface.

```text
ManualLabEquipment ⊑ LabArtifact
ManualLabEquipment ⊑ ¬LabAutomationDevice
ManualLabEquipment ⊑ ∃hasEquipmentFunction.DeviceFunction
```

### BiosafetyCabinet 🔧

Class II BSC.

```text
BiosafetyCabinet ⊑ ManualLabEquipment
BiosafetyCabinet ⊑ ∃hasEquipmentFunction.AsepticWorkFunction
```

### ManualCO2Incubator 🔧

Benchtop.

```text
ManualCO2Incubator ⊑ ManualLabEquipment
ManualCO2Incubator ⊑ ∃hasEquipmentFunction.IncubationFunction
```

### InvertedMicroscope 🔧

Manual scope.

```text
InvertedMicroscope ⊑ ManualLabEquipment
InvertedMicroscope ⊑ ∃hasEquipmentFunction.ImagingFunction
```

### Centrifuge 🔧

Benchtop centrifuge.

```text
Centrifuge ⊑ ManualLabEquipment
Centrifuge ⊑ ∃hasEquipmentFunction.SeparationFunction
```

### WaterBath 🔧

Water bath.

```text
WaterBath ⊑ ManualLabEquipment
WaterBath ⊑ ∃hasEquipmentFunction.TemperatureControlFunction
```

### Autoclave 🔧

Steam steriliser.

```text
Autoclave ⊑ ManualLabEquipment
Autoclave ⊑ ∃hasEquipmentFunction.SterilizationFunction
```

### ColdStorageDevice 🔧

Cold storage.

```text
ColdStorageDevice ⊑ ManualLabEquipment
ColdStorageDevice ⊑ ∃hasEquipmentFunction.ColdStorageFunction
```

### LabRefrigerator 🔧

+4 °C refrigerator.

```text
LabRefrigerator ⊑ ColdStorageDevice
LabRefrigerator ⊑ ∃locatedAt.StorageRoom
```

### LabFreezer 🔧

-20 °C freezer.

```text
LabFreezer ⊑ ColdStorageDevice
LabFreezer ⊑ ∃locatedAt.StorageRoom
```

### ULTFreezer 🔧

-80 °C ultra-low freezer.

```text
ULTFreezer ⊑ ColdStorageDevice
ULTFreezer ⊑ ∃locatedAt.StorageRoom
```

### CryogenicDewar 🔧

LN2 dewar.

```text
CryogenicDewar ⊑ ColdStorageDevice
CryogenicDewar ⊑ ∃isMonitoredBy.O2DepletionMonitor
```

### GasCylinderCabinet 🔧

Ventilated CO2 cabinet.

```text
GasCylinderCabinet ⊑ SafetyDevice
GasCylinderCabinet ⊑ ∃mitigatesHazard.AsphyxiationHazard
```

### MechanismPart 🔧

A component of a lab device or fixture (not a robot-body link; D-LAT-1).

```text
MechanismPart ⊑ LabArtifact
MechanismPart ⊑ ∃isDirectComponentOf.LabArtifact
```

### MechanismJoint ✅

A kinematic joint of a device or tool mechanism (USD physics joint), typed by AICOR's JointType.

```text
MechanismJoint ⊑ MechanismPart
MechanismJoint ⊑ =1 hasMechanismJointType.JointType
```

### DrivenMechanismJoint 🔧

Defined: a mechanism joint with an actuator (a USD joint with a drive).

```text
DrivenMechanismJoint ⊑ MechanismJoint
DrivenMechanismJoint ≡ MechanismJoint ⊓ ∃isDrivenBy.Actuator
```

### Actuator 🔧

Motor or drive of a joint.

```text
Actuator ⊑ MechanismPart
Actuator ⊑ ∃drivesJoint.MechanismJoint
```

### StationHousing 🔧

Body of a device.

```text
StationHousing ⊑ MechanismPart
StationHousing ⊑ ∃isDirectComponentOf.LabAutomationDevice
```

### IncubationChamber ✅

Conditioned, insulated chamber.

```text
IncubationChamber ⊑ StationHousing
IncubationChamber ⊑ ∃isDirectComponentOf.IncubationDevice
```

### AccessGate ✅

Sliding load gate.

```text
AccessGate ⊑ MechanismPart
AccessGate ⊑ ∃isDirectComponentOf.LabAutomationDevice
```

### ServiceDoor ✅

Hinged service door.

```text
ServiceDoor ⊑ MechanismPart
ServiceDoor ⊑ ∃isDirectComponentOf.LabAutomationDevice
```

### LockableDoor ✅

Door that a latch bolt locks (H4).

```text
LockableDoor ⊑ MechanismPart
LockableDoor ⊑ ∃isDirectComponentOf.QuarantineStation
LockableDoor ⊑ ∃isMonitoredBy.DeviceSensor
```

### LatchBolt ✅

Bolt that locks a door.

```text
LatchBolt ⊑ MechanismPart
LatchBolt ⊑ ∃isDirectComponentOf.QuarantineStation
```

### OperatorControl 🔧

A physical control operated by a person.

```text
OperatorControl ⊑ MechanismPart
OperatorControl ⊑ ∃isDirectComponentOf.LabArtifact
```

### KeySwitch ✅

Key-operated selector (H4 release).

```text
KeySwitch ⊑ OperatorControl
KeySwitch ⊑ ∃hasDirectComponent.KeyCylinder
```

### KeyCylinder 🔧

Rotating cylinder of a key switch.

```text
KeyCylinder ⊑ MechanismPart
KeyCylinder ⊑ ∃isDirectComponentOf.KeySwitch
```

### PushButton 🔧

Momentary push button.

```text
PushButton ⊑ OperatorControl
PushButton ⊑ ∃hasDirectComponent.ButtonPlunger
```

### ButtonPlunger 🔧

Moving plunger of a button.

```text
ButtonPlunger ⊑ MechanismPart
ButtonPlunger ⊑ ∃isDirectComponentOf.PushButton
```

### PlateShuttle ✅

Sliding SBS nest that presents a plate outside the device.

```text
PlateShuttle ⊑ MechanismPart
PlateShuttle ⊑ ∃hasDirectComponent.SeatSensor
PlateShuttle ⊑ ∃hasInteractionPose.PlateSeatPose
```

### PlateCassette ✅

Stack of plate slots.

```text
PlateCassette ⊑ MechanismPart
PlateCassette ⊑ ∃hasDirectComponent.PlateSlot
```

### PlateSlot ✅

One plate position of a cassette.

```text
PlateSlot ⊑ MechanismPart
PlateSlot ⊑ ∃isDirectComponentOf.PlateCassette
PlateSlot ⊑ ∃hasDirectComponent.SlotOccupancySensor
PlateSlot ⊑ ∃slotIndex.xsd:integer
```

### InternalPlateHandler 🔧

Lift moving plates cassette <-> shuttle.

```text
InternalPlateHandler ⊑ MechanismPart
InternalPlateHandler ⊑ ∃hasDirectComponent.PlateFork
```

### PlateFork 🔧

Fork tine lifting a plate.

```text
PlateFork ⊑ MechanismPart
PlateFork ⊑ ∃isDirectComponentOf.InternalPlateHandler
```

### GantryAxis ✅

Linear gantry axis.

```text
GantryAxis ⊑ MechanismPart
GantryAxis ⊑ ∃isDirectComponentOf.(DispensingDevice ⊔ GantryAxis)
```

### PipettingChannel ✅

Z axis with a pipetting head.

```text
PipettingChannel ⊑ GantryAxis
PipettingChannel ⊑ ∃hasInteractionPose.ToolCenterPose
```

### MotorizedStage ✅

XY stage axis (L17's stage is also the load drawer).

```text
MotorizedStage ⊑ MechanismPart
MotorizedStage ⊑ ∃isDirectComponentOf.(ImagingDevice ⊔ MotorizedStage)
```

### FocusDrive ✅

Z focus drive.

```text
FocusDrive ⊑ MechanismPart
FocusDrive ⊑ ∃hasDirectComponent.ObjectiveTurret
```

### ObjectiveTurret ✅

Objective changer.

```text
ObjectiveTurret ⊑ MechanismPart
ObjectiveTurret ⊑ ∃isDirectComponentOf.FocusDrive
```

### MagazineStand ✅

Stand carrying tool docks and their occupancy sensors.

```text
MagazineStand ⊑ MechanismPart
MagazineStand ⊑ ∃isDirectComponentOf.ToolMagazine
MagazineStand ⊑ ∃hasDirectComponent.SlotOccupancySensor
```

### LinearRail ✅

Linear axis carrying a robot (igus ZLW-1660).

```text
LinearRail ⊑ MechanismPart
LinearRail ⊑ ∃hasDirectComponent.RailCarriage
```

### RailCarriage 🔧

Moving rail carriage.

```text
RailCarriage ⊑ MechanismPart
RailCarriage ⊑ ∃isDirectComponentOf.LinearRail
```

### DeviceSensor ✅

A sensor of a device or fixture (not AICOR's robot-mounted Sensor; D-LAT-1).

```text
DeviceSensor ⊑ MechanismPart
DeviceSensor ⊑ ∃monitorsEntity.Entity
```

### SeatSensor ✅

Flush seat window (plate seated).

```text
SeatSensor ⊑ DeviceSensor
SeatSensor ⊑ ∃monitorsEntity.PlateSeatPose
```

### SlotOccupancySensor ✅

Ray occupancy sensor.

```text
SlotOccupancySensor ⊑ DeviceSensor
SlotOccupancySensor ⊑ ∃isDirectComponentOf.(PlateSlot ⊔ MagazineStand)
```

### CarrierPresenceSensor ✅

Carrier present in AMR cabinet.

```text
CarrierPresenceSensor ⊑ DeviceSensor
CarrierPresenceSensor ⊑ ∃isDirectComponentOf.MobileRobotBase
```

### ThroughBeamSensor 🔧

Emitter / receiver beam element.

```text
ThroughBeamSensor ⊑ DeviceSensor
ThroughBeamSensor ⊑ ∃isDirectComponentOf.LabAutomationDevice
```

### DockSensor ✅

Ray measuring the docked AMR pose.

```text
DockSensor ⊑ DeviceSensor
DockSensor ⊑ ∃isDirectComponentOf.DeterministicAMRDock
```

### BarcodeReader ✅

Reads plate barcodes.

```text
BarcodeReader ⊑ DeviceSensor
BarcodeReader ⊑ ∃monitorsEntity.Labware
```

### LightBarrierSensor ✅

Crossed barrier measuring a TCP.

```text
LightBarrierSensor ⊑ DeviceSensor
LightBarrierSensor ⊑ ∃isDirectComponentOf.QCCalibrationStation
```

### FiducialMarker 🔧

Marker used to register poses.

```text
FiducialMarker ⊑ MechanismPart
FiducialMarker ⊑ ∃affordsTaskType.CalibratingTask
```

### AprilTagMarker ✅

AprilTag 36h11.

```text
AprilTagMarker ⊑ FiducialMarker
AprilTagMarker ⊑ ∃isDirectComponentOf.LabArtifact
```

### DatumPin ✅

Conical registration pin.

```text
DatumPin ⊑ FiducialMarker
DatumPin ⊑ ∃isDirectComponentOf.LabArtifact
```

## Cell robots, robot bodies, tools and robot skills

`lab-twin-robots-dl.md` — Cell robots (AICOR Robot), robot bodies, exchangeable tools and robot skills.

### CellRobot ✅

A robot of an automation cell, assigned to stations (layout P1).

```text
CellRobot ⊑ Robot
CellRobot ⊑ LabArtifact
CellRobot ⊑ ∃servesStation.LabArtifact
CellRobot ⊑ ∃hasRobotSkill.RobotSkill
```

### FixedBaseManipulator ✅

Arm on a fixed pedestal (R01 FR3).

```text
FixedBaseManipulator ⊑ CellRobot
FixedBaseManipulator ⊑ ∃hasProperPart.ArmRobotBody
FixedBaseManipulator ⊑ ¬∃hasDirectComponent.(LinearRail ⊔ MobileRobotBase)
```

### RailMountedManipulator ✅

Arm on a linear rail with a tool changer (R02 UR5e).

```text
RailMountedManipulator ⊑ CellRobot
RailMountedManipulator ⊑ ∃hasDirectComponent.LinearRail
RailMountedManipulator ⊑ ∃hasProperPart.ArmRobotBody
```

### SampleTransportAMR ✅

Clean-sample AMR with a sealed cabinet (R03, MiR100 class).

```text
SampleTransportAMR ⊑ CellRobot
SampleTransportAMR ⊑ ∃hasProperPart.MobileRobotBase
SampleTransportAMR ⊑ ∃hasRobotSkill.SampleTransportSkill
```

### ArmRobotBody 🔧

Serial arm body (FR3, UR5e).

```text
ArmRobotBody ⊑ RobotBody
ArmRobotBody ⊑ ∃hasEndEffectorMount.EndEffector
```

### MobileRobotBase ✅

AMR base with the sample cabinet (R03).

```text
MobileRobotBase ⊑ RobotBody
MobileRobotBase ⊑ ∃hasDirectComponent.CabinetLid
```

### CabinetLid ✅

Flat lid over the carrier nest.

```text
CabinetLid ⊑ MechanismPart
CabinetLid ⊑ ∃isDirectComponentOf.MobileRobotBase
```

### VirtualPlanarLink ✅

A simulation link of the AMR's planar base joints (twin artefact).

```text
VirtualPlanarLink ⊑ Link
VirtualPlanarLink ⊑ ∃partOf.MobileRobotBase
```

### AutomaticToolChanger ✅

Robot-side tool coupler.

```text
AutomaticToolChanger ⊑ MechanismPart
AutomaticToolChanger ⊑ ∃couplesTool.ExchangeableTool
```

### ExchangeableTool ✅

End effector exchanged by a tool changer (stored in a magazine, not a robot-body link).

```text
ExchangeableTool ⊑ LabArtifact
ExchangeableTool ⊑ ∃hasDirectComponent.ToolBody
ExchangeableTool ⊑ ∃hasInteractionPose.ToolCouplingPose
```

### ToolBody 🔧

Housing of a tool.

```text
ToolBody ⊑ MechanismPart
ToolBody ⊑ ∃isDirectComponentOf.ExchangeableTool
```

### GripperJaw 🔧

Jaw of a gripper tool.

```text
GripperJaw ⊑ MechanismPart
GripperJaw ⊑ ∃isDirectComponentOf.ExchangeableTool
```

### PlateGripperTool ✅

Two-jaw SBS plate gripper (T01).

```text
PlateGripperTool ⊑ ExchangeableTool
PlateGripperTool ⊑ =2 hasDirectComponent.GripperJaw
PlateGripperTool ⊑ ∃affordsRobotSkill.PlateTransferSkill
PlateGripperTool ⊓ TubeGripperTool ⊑ ⊥
```

### TubeGripperTool ✅

T02.

```text
TubeGripperTool ⊑ ExchangeableTool
TubeGripperTool ⊑ ∃affordsRobotSkill.TubeHandlingSkill
TubeGripperTool ⊓ PlateGripperTool ⊑ ⊥
```

### PipettingTool ✅

T03.

```text
PipettingTool ⊑ ExchangeableTool
PipettingTool ⊑ ∃affordsRobotSkill.LiquidTransferSkill
PipettingTool ⊓ PlateGripperTool ⊑ ⊥
```

### SuctionPickupTool ✅

T04.

```text
SuctionPickupTool ⊑ ExchangeableTool
SuctionPickupTool ⊑ ∃affordsRobotSkill.PlateTransferSkill
SuctionPickupTool ⊓ PlateGripperTool ⊑ ⊥
```

### CameraInspectionTool ✅

T05.

```text
CameraInspectionTool ⊑ ExchangeableTool
CameraInspectionTool ⊑ ∃affordsRobotSkill.InspectionSkill
CameraInspectionTool ⊓ PlateGripperTool ⊑ ⊥
```

### RobotSkill 🔧

A capability of a robot.

```text
RobotSkill ⊑ dul:Quality
RobotSkill ⊑ ∃functionAffords.LabTaskType
```

### PlateTransferSkill ✅

Pick, carry, place SBS plates.

```text
PlateTransferSkill ⊑ RobotSkill
PlateTransferSkill ⊑ ∃functionAffords.PlateTransferTask
```

### SampleTransportSkill ✅

Carry samples in a closed cabinet.

```text
SampleTransportSkill ⊑ RobotSkill
SampleTransportSkill ⊑ ∃functionAffords.PlateTransferTask
```

### NavigationSkill ✅

Navigate between docks.

```text
NavigationSkill ⊑ RobotSkill
NavigationSkill ⊑ ∃functionAffords.NavigationTask
```

### DockingSkill ✅

Dock deterministically.

```text
DockingSkill ⊑ RobotSkill
DockingSkill ⊑ ∃functionAffords.DockingTask
```

### ToolExchangeSkill ✅

Exchange end effectors.

```text
ToolExchangeSkill ⊑ RobotSkill
ToolExchangeSkill ⊑ ∃functionAffords.ToolExchangeTask
```

### TubeHandlingSkill ✅

Handle tubes.

```text
TubeHandlingSkill ⊑ RobotSkill
TubeHandlingSkill ⊑ ∃functionAffords.PlateTransferTask
```

### LiquidTransferSkill ✅

Pipette.

```text
LiquidTransferSkill ⊑ RobotSkill
LiquidTransferSkill ⊑ ∃functionAffords.LiquidDispensingTask
```

### InspectionSkill ✅

Inspect with a camera.

```text
InspectionSkill ⊑ RobotSkill
InspectionSkill ⊑ ∃functionAffords.ImagingTask
```

## Labware, wells and material portions

`lab-twin-labware-dl.md` — Labware, wells, culture medium and organoids, reagent portions.

### Labware 🔧

Containers handled in experiments.

```text
Labware ⊑ LabArtifact
Labware ⊑ ∃handledIn.PlateTransferTask
```

### Microplate 🔧

Defined: labware with wells.

```text
Microplate ⊑ Labware
Microplate ≡ Labware ⊓ ∃hasDirectComponent.Well
```

### SBSMicroplate96 ✅

SBS / ANSI 96-well plate.

```text
SBSMicroplate96 ⊑ Microplate
SBSMicroplate96 ⊑ =96 hasDirectComponent.Well
```

### CulturePlate ✅

Plate holding cultures (Plate_P17).

```text
CulturePlate ⊑ Microplate
CulturePlate ⊑ ∃hasDirectComponent.CultureWell
```

### ReferencePlate ✅

L21 calibration reference plate.

```text
ReferencePlate ⊑ Microplate
ReferencePlate ⊑ ∃affordsTaskType.CalibratingTask
```

### Well ✅

A well of a plate.

```text
Well ⊑ MechanismPart
Well ⊑ ∃isDirectComponentOf.Microplate
Well ⊑ ∃wellId.xsd:string
Well ⊓ CultureMediumPortion ⊑ ⊥
```

### CultureWell 🔧

Defined: a well that contains culture medium.

```text
CultureWell ⊑ Well
CultureWell ≡ Well ⊓ ∃containsMaterial.CultureMediumPortion
```

### CultureMediumPortion ✅

The medium in one well: a material portion, contained, not a part.

```text
CultureMediumPortion ⊑ BiologicalSample
CultureMediumPortion ⊑ ∃isContainedIn.Well
CultureMediumPortion ⊓ Well ⊑ ⊥
```

### WellOrganoid ✅

The organoid cultured in one well (Cell 01: hepatotoxicity model; RS reading: a liver organoid).

```text
WellOrganoid ⊑ BiologicalSpecimen
WellOrganoid ⊑ ∃locatedAt.Well
```

### ReagentPortion 🔧

A reagent portion in a container.

```text
ReagentPortion ⊑ Sample
ReagentPortion ⊑ ∃isContainedIn.Labware
```

### ChallengeReagentPortion ✅

Abstract challenge reagent.

```text
ChallengeReagentPortion ⊑ ReagentPortion
ChallengeReagentPortion ⊑ ∃affordsTaskType.ChallengeDosingTask
ChallengeReagentPortion ⊓ RescueReagentPortion ⊑ ⊥
```

### RescueReagentPortion ✅

Abstract rescue reagent.

```text
RescueReagentPortion ⊑ ReagentPortion
RescueReagentPortion ⊑ ∃affordsTaskType.RescueDosingTask
RescueReagentPortion ⊓ ChallengeReagentPortion ⊑ ⊥
```

## Poses: coordinate and interaction frames of the twin (AICOR SpatialPose)

`lab-twin-poses-dl.md` — Named poses of the twin (USD Xform frames) as AICOR SpatialPoses, typed by the task they afford.

### TwinPose ✅

A named pose on an object (USD Xform).

```text
TwinPose ⊑ SpatialPose
TwinPose ⊑ ∃isPoseOf.dul:PhysicalObject
```

### KinematicPose 🔧

Reference pose of a link or mechanism.

```text
KinematicPose ⊑ TwinPose
KinematicPose ⊑ ∃isPoseOf.LabArtifact
```

### InteractionPose 🔧

Pose where a task is performed.

```text
InteractionPose ⊑ TwinPose
InteractionPose ⊑ ∃affordsTaskType.LabTaskType
```

### PlateSeatPose ✅

SBS plate seat.

```text
PlateSeatPose ⊑ InteractionPose
PlateSeatPose ⊑ ∃affordsTaskType.(PlateTransferTask ⊔ PlateStoringTask)
PlateSeatPose ⊓ ApproachPose ⊑ ⊥
```

### ApproachPose ✅

Pose reached before an interaction.

```text
ApproachPose ⊑ InteractionPose
ApproachPose ⊑ ∃affordsTaskType.(NavigationTask ⊔ PlateTransferTask)
ApproachPose ⊓ PlateSeatPose ⊑ ⊥
```

### DockPose ✅

Pose of a docked AMR.

```text
DockPose ⊑ InteractionPose
DockPose ⊑ ∃affordsTaskType.DockingTask
DockPose ⊓ PlateSeatPose ⊑ ⊥
```

### ToolCenterPose ✅

Tool centre point.

```text
ToolCenterPose ⊑ InteractionPose
ToolCenterPose ⊑ ∃affordsTaskType.PlateTransferTask
ToolCenterPose ⊓ PlateSeatPose ⊑ ⊥
```

### ToolCouplingPose ✅

Coupling face of a tool or changer.

```text
ToolCouplingPose ⊑ InteractionPose
ToolCouplingPose ⊑ ∃affordsTaskType.ToolExchangeTask
ToolCouplingPose ⊓ PlateSeatPose ⊑ ⊥
```

### PipettingTargetPose ✅

Where a channel doses into a well.

```text
PipettingTargetPose ⊑ InteractionPose
PipettingTargetPose ⊑ ∃affordsTaskType.LiquidDispensingTask
PipettingTargetPose ⊓ PlateSeatPose ⊑ ⊥
```

### ImagingTargetPose ✅

Where a well is imaged.

```text
ImagingTargetPose ⊑ InteractionPose
ImagingTargetPose ⊑ ∃affordsTaskType.ImagingTask
ImagingTargetPose ⊓ PlateSeatPose ⊑ ⊥
```

### RackPositionPose ✅

Rack position.

```text
RackPositionPose ⊑ InteractionPose
RackPositionPose ⊑ ∃affordsTaskType.(LiquidDispensingTask ⊔ TipHandlingTask)
RackPositionPose ⊓ PlateSeatPose ⊑ ⊥
```

### WastePose ✅

Tip ejection.

```text
WastePose ⊑ InteractionPose
WastePose ⊑ ∃affordsTaskType.TipHandlingTask
WastePose ⊓ PlateSeatPose ⊑ ⊥
```

### CalibrationPose ✅

Datum for QC / calibration.

```text
CalibrationPose ⊑ InteractionPose
CalibrationPose ⊑ ∃affordsTaskType.CalibratingTask
CalibrationPose ⊓ PlateSeatPose ⊑ ⊥
```

### StorageLocationPose ✅

Shelf location.

```text
StorageLocationPose ⊑ InteractionPose
StorageLocationPose ⊑ ∃affordsTaskType.(ConsumableStoringTask ⊔ ColdStoringTask)
```

### ManipulationPointPose ✅

Handle, door, lid, sash, tap, button.

```text
ManipulationPointPose ⊑ InteractionPose
ManipulationPointPose ⊑ ∃affordsTaskType.OperatorInteractionTask
```

### OperatorPositionPose ✅

Where a person works.

```text
OperatorPositionPose ⊑ InteractionPose
OperatorPositionPose ⊑ ∃affordsTaskType.OperatorInteractionTask
```

### ItemAccessPose ✅

Where a person takes or puts an item.

```text
ItemAccessPose ⊑ InteractionPose
ItemAccessPose ⊑ ∃affordsTaskType.PlateTransferTask
```

### CleaningPointPose ✅

Sink basin, eyewash.

```text
CleaningPointPose ⊑ InteractionPose
CleaningPointPose ⊑ ∃affordsTaskType.CleaningTask
```

### OpticalPose 🔧

Objective, camera or focal-point pose.

```text
OpticalPose ⊑ TwinPose
OpticalPose ⊑ ∃isPoseOf.(ImagingDevice ⊔ MechanismPart ⊔ CellRobot)
```

### IlluminationPose 🔧

Illumination axis.

```text
IlluminationPose ⊑ OpticalPose
IlluminationPose ⊑ ∃isPoseOf.ImagingDevice
```

### ViewpointPose 🔧

Viewpoint of a virtual twin camera.

```text
ViewpointPose ⊑ TwinPose
ViewpointPose ⊑ ∃isPoseOf.dul:PhysicalPlace
```

## Lab task types and actions

`lab-twin-tasks-dl.md` — Lab task types (concepts) and lab actions (events), with defined action classes.

### LabTaskType 🔧

A type of lab work.

```text
LabTaskType ⊑ dul:Concept
LabTaskType ⊑ ∀classifiesAction.LabAction
```

### PlateTransferTask ✅

Move labware between seats. Every action of this type involves a Labware.

```text
PlateTransferTask ⊑ LabTaskType
PlateTransferTask ⊑ ∀classifiesAction.∃hasParticipantEntity.Labware
PlateTransferTask ⊓ PlateStoringTask ⊑ ⊥
```

### PlateStoringTask ✅

Put a plate into a store. Every action of this type involves a PlateStorageDevice.

```text
PlateStoringTask ⊑ LabTaskType
PlateStoringTask ⊑ ∀classifiesAction.∃hasParticipantEntity.PlateStorageDevice
PlateStoringTask ⊓ PlateTransferTask ⊑ ⊥
```

### PlateRetrievingTask ✅

Take a plate out of a device. Every action of this type involves a LabArtifact.

```text
PlateRetrievingTask ⊑ LabTaskType
PlateRetrievingTask ⊑ ∀classifiesAction.∃hasParticipantEntity.LabArtifact
PlateRetrievingTask ⊓ PlateTransferTask ⊑ ⊥
```

### IncubatingTask ✅

Keep a plate in an incubator. Every action of this type involves a IncubationDevice.

```text
IncubatingTask ⊑ LabTaskType
IncubatingTask ⊑ ∀classifiesAction.∃hasParticipantEntity.IncubationDevice
IncubatingTask ⊓ PlateTransferTask ⊑ ⊥
```

### LiquidDispensingTask ✅

Dispense liquid into a well. Every action of this type involves a DispensingDevice.

```text
LiquidDispensingTask ⊑ LabTaskType
LiquidDispensingTask ⊑ ∀classifiesAction.∃hasParticipantEntity.DispensingDevice
LiquidDispensingTask ⊓ PlateTransferTask ⊑ ⊥
```

### ChallengeDosingTask ✅

Dose the challenge reagent. Every action of this type involves a DispensingDevice.

```text
ChallengeDosingTask ⊑ LabTaskType
ChallengeDosingTask ⊑ ∀classifiesAction.∃hasParticipantEntity.DispensingDevice
```

### RescueDosingTask ✅

Dose the rescue reagent. Every action of this type involves a DispensingDevice.

```text
RescueDosingTask ⊑ LabTaskType
RescueDosingTask ⊑ ∀classifiesAction.∃hasParticipantEntity.DispensingDevice
```

### ImagingTask ✅

Acquire an image. Every action of this type involves a ImagingDevice.

```text
ImagingTask ⊑ LabTaskType
ImagingTask ⊑ ∀classifiesAction.∃hasParticipantEntity.ImagingDevice
ImagingTask ⊓ PlateTransferTask ⊑ ⊥
```

### CalibratingTask ✅

Check / calibrate against a reference. Every action of this type involves a QCCalibrationStation.

```text
CalibratingTask ⊑ LabTaskType
CalibratingTask ⊑ ∀classifiesAction.∃hasParticipantEntity.QCCalibrationStation
CalibratingTask ⊓ PlateTransferTask ⊑ ⊥
```

### QuarantiningTask ✅

Contain a plate. Every action of this type involves a QuarantineStation.

```text
QuarantiningTask ⊑ LabTaskType
QuarantiningTask ⊑ ∀classifiesAction.∃hasParticipantEntity.QuarantineStation
QuarantiningTask ⊓ PlateTransferTask ⊑ ⊥
```

### QuarantineReleaseTask ✅

Release a plate after authorisation. Every action of this type involves a QuarantineStation.

```text
QuarantineReleaseTask ⊑ LabTaskType
QuarantineReleaseTask ⊑ ∀classifiesAction.∃hasParticipantEntity.QuarantineStation
```

### IdentifyingTask ✅

Read a plate identity. Every action of this type involves a BarcodeReader.

```text
IdentifyingTask ⊑ LabTaskType
IdentifyingTask ⊑ ∀classifiesAction.∃hasParticipantEntity.BarcodeReader
```

### NavigationTask ✅

Drive between docks. Every action of this type involves a SampleTransportAMR.

```text
NavigationTask ⊑ LabTaskType
NavigationTask ⊑ ∀classifiesAction.∃hasParticipantEntity.SampleTransportAMR
```

### DockingTask ✅

Dock an AMR. Every action of this type involves a Dock.

```text
DockingTask ⊑ LabTaskType
DockingTask ⊑ ∀classifiesAction.∃hasParticipantEntity.Dock
```

### ToolExchangeTask ✅

Couple / release a tool. Every action of this type involves a AutomaticToolChanger.

```text
ToolExchangeTask ⊑ LabTaskType
ToolExchangeTask ⊑ ∀classifiesAction.∃hasParticipantEntity.AutomaticToolChanger
```

### TipHandlingTask ✅

Pick up / eject a tip. Every action of this type involves a PipettingChannel.

```text
TipHandlingTask ⊑ LabTaskType
TipHandlingTask ⊑ ∀classifiesAction.∃hasParticipantEntity.PipettingChannel
```

### ColdStoringTask ✅

Store material cold. Every action of this type involves a ColdStorageDevice.

```text
ColdStoringTask ⊑ LabTaskType
ColdStoringTask ⊑ ∀classifiesAction.∃hasParticipantEntity.ColdStorageDevice
```

### SterilizingTask ✅

Sterilise. Every action of this type involves a Autoclave.

```text
SterilizingTask ⊑ LabTaskType
SterilizingTask ⊑ ∀classifiesAction.∃hasParticipantEntity.Autoclave
```

### AsepticHandlingTask ✅

Handle open cultures. Every action of this type involves a BiosafetyCabinet.

```text
AsepticHandlingTask ⊑ LabTaskType
AsepticHandlingTask ⊑ ∀classifiesAction.∃hasParticipantEntity.BiosafetyCabinet
```

### TemperatureControllingTask ✅

Hold a temperature. Every action of this type involves a ManualLabEquipment.

```text
TemperatureControllingTask ⊑ LabTaskType
TemperatureControllingTask ⊑ ∀classifiesAction.∃hasParticipantEntity.ManualLabEquipment
```

### ConsumableStoringTask ✅

Store consumables. Every action of this type involves a StorageShelving.

```text
ConsumableStoringTask ⊑ LabTaskType
ConsumableStoringTask ⊑ ∀classifiesAction.∃hasParticipantEntity.StorageShelving
```

### CleaningTask ✅

Wash. Every action of this type involves a LabSinkUnit.

```text
CleaningTask ⊑ LabTaskType
CleaningTask ⊑ ∀classifiesAction.∃hasParticipantEntity.LabSinkUnit
```

### OperatorInteractionTask ✅

A person operates equipment. Every action of this type involves a LabArtifact.

```text
OperatorInteractionTask ⊑ LabTaskType
OperatorInteractionTask ⊑ ∀classifiesAction.∃hasParticipantEntity.LabArtifact
```

### LabAction 🔧

An action of lab work.

```text
LabAction ⊑ soma:Action
LabAction ⊑ ∃executesTaskType.LabTaskType
```

### RobotAction 🔧

Defined: a lab action a robot takes part in.

```text
RobotAction ⊑ LabAction
RobotAction ≡ LabAction ⊓ ∃hasParticipantEntity.Robot
```

### TransferAction 🔧

Defined: a lab action of type PlateTransferTask.

```text
TransferAction ⊑ LabAction
TransferAction ≡ LabAction ⊓ ∃executesTaskType.PlateTransferTask
```

### StoreAction 🔧

Defined: a lab action of type PlateStoringTask.

```text
StoreAction ⊑ LabAction
StoreAction ≡ LabAction ⊓ ∃executesTaskType.PlateStoringTask
```

### RetrieveAction 🔧

Defined: a lab action of type PlateRetrievingTask.

```text
RetrieveAction ⊑ LabAction
RetrieveAction ≡ LabAction ⊓ ∃executesTaskType.PlateRetrievingTask
```

### IncubateAction 🔧

Defined: a lab action of type IncubatingTask.

```text
IncubateAction ⊑ LabAction
IncubateAction ≡ LabAction ⊓ ∃executesTaskType.IncubatingTask
```

### DoseAction 🔧

Defined: a lab action of type LiquidDispensingTask.

```text
DoseAction ⊑ LabAction
DoseAction ≡ LabAction ⊓ ∃executesTaskType.LiquidDispensingTask
```

### ImageAction 🔧

Defined: a lab action of type ImagingTask.

```text
ImageAction ⊑ LabAction
ImageAction ≡ LabAction ⊓ ∃executesTaskType.ImagingTask
```

### QCAction 🔧

Defined: a lab action of type CalibratingTask.

```text
QCAction ⊑ LabAction
QCAction ≡ LabAction ⊓ ∃executesTaskType.CalibratingTask
```

### QuarantineAction 🔧

Defined: a lab action of type QuarantiningTask.

```text
QuarantineAction ⊑ LabAction
QuarantineAction ≡ LabAction ⊓ ∃executesTaskType.QuarantiningTask
```

### AMRTransferAction 🔧

Defined: a transfer by the sample AMR.

```text
AMRTransferAction ⊑ TransferAction
AMRTransferAction ≡ TransferAction ⊓ ∃hasParticipantEntity.SampleTransportAMR
```

## Device manual knowledge (Cell 01 component contracts) and device process knowledge

`lab-twin-device-manuals-dl.md` — Device manual knowledge: Cell 01's SDT component contracts as manuals, with operating procedures (RS ActionContract), preconditions, effects, setpoints, constraints, monitors (AICOR ProcessMonitor), failure modes (AICOR FailureSignature), recovery (AICOR Repair), risk controls and device process microtheories (AICOR BodyWorldProcessMicrotheory).

### DeviceManual ✅

Operating knowledge of a device or robot: identity, procedures, setpoints, constraints, monitors, failure modes, recovery and risk controls.

```text
DeviceManual ⊑ dul:InformationObject
DeviceManual ⊑ ∃manualFor.LabArtifact
DeviceManual ⊑ ∃documentsProcedure.OperatingProcedure
DeviceManual ⊑ ∃sourceDocument.xsd:string
```

### CellComponentContract ✅

A Cell 01 SDT component contract (sdt/components/*.yaml): the project's manual-equivalent; no vendor manual is in the repository (restricted source folders are empty).

```text
CellComponentContract ⊑ DeviceManual
CellComponentContract ⊑ ∃manufacturerBaseline.xsd:string
```

### OperatingProcedure ✅

A documented device operation with preconditions, parameters, effects, monitors, recovery and evidence outputs (Cell 01 action_contracts).

```text
OperatingProcedure ⊑ ActionContract
OperatingProcedure ⊑ ∃requiresPrecondition.Precondition
OperatingProcedure ⊑ ∃hasExpectedEffect.ExpectedEffect
OperatingProcedure ⊑ ∃hasRecoveryProcedure.RecoveryProcedure
```

### ManualItem ✅

One item of a manual, verbatim.

```text
ManualItem ⊑ dul:Description
ManualItem ⊑ ∃statementText.xsd:string
```

### Precondition ✅

Must hold before a procedure.

```text
Precondition ⊑ ManualItem
Precondition ⊑ ∃isRequiredBy.OperatingProcedure
```

### IdentityPrecondition ✅

Plate / reagent / target identity verified or consistent.

```text
IdentityPrecondition ⊑ Precondition
IdentityPrecondition ⊑ ∃isRequiredBy.OperatingProcedure
IdentityPrecondition ⊓ AvailabilityPrecondition ⊑ ⊥
```

### AvailabilityPrecondition ✅

Device / slot / station available, reserved or clear.

```text
AvailabilityPrecondition ⊑ Precondition
AvailabilityPrecondition ⊑ ∃isRequiredBy.OperatingProcedure
AvailabilityPrecondition ⊓ IdentityPrecondition ⊑ ⊥
```

### EnvironmentPrecondition ✅

Environment within its valid envelope.

```text
EnvironmentPrecondition ⊑ Precondition
EnvironmentPrecondition ⊑ ∃isRequiredBy.OperatingProcedure
EnvironmentPrecondition ⊓ IdentityPrecondition ⊑ ⊥
```

### CalibrationPrecondition ✅

Calibration / tool frame valid.

```text
CalibrationPrecondition ⊑ Precondition
CalibrationPrecondition ⊑ ∃isRequiredBy.OperatingProcedure
CalibrationPrecondition ⊓ IdentityPrecondition ⊑ ⊥
```

### SafetyPrecondition ✅

A safety or containment state holds (interlocks ready, airspace clear).

```text
SafetyPrecondition ⊑ Precondition
SafetyPrecondition ⊑ ∃isRequiredBy.OperatingProcedure
SafetyPrecondition ⊓ IdentityPrecondition ⊑ ⊥
```

### AuthorizationPrecondition ✅

An authorisation is present (quarantine release, QA decision).

```text
AuthorizationPrecondition ⊑ Precondition
AuthorizationPrecondition ⊑ ∃isRequiredBy.OperatingProcedure
AuthorizationPrecondition ⊓ IdentityPrecondition ⊑ ⊥
```

### PlacementPrecondition ✅

An object is seated / present / positioned.

```text
PlacementPrecondition ⊑ Precondition
PlacementPrecondition ⊑ ∃isRequiredBy.OperatingProcedure
PlacementPrecondition ⊓ IdentityPrecondition ⊑ ⊥
```

### ExpectedEffect ✅

State after a procedure.

```text
ExpectedEffect ⊑ ManualItem
ExpectedEffect ⊑ ∃isEffectOf.OperatingProcedure
```

### EvidenceOutput ✅

Evidence a procedure records.

```text
EvidenceOutput ⊑ ManualItem
EvidenceOutput ⊑ ∃isEvidenceOf.OperatingProcedure
```

### OperatingSetpoint ✅

Nominal operating state value of a device (e.g. 37 °C).

```text
OperatingSetpoint ⊑ ManualItem
OperatingSetpoint ⊑ ∃quantityName.xsd:string
```

### OperatingConstraint ✅

A constraint a manual places on operation.

```text
OperatingConstraint ⊑ ManualItem
OperatingConstraint ⊑ LabConstraint
OperatingConstraint ⊑ ∃constrainsDevice.LabArtifact
```

### DeviceMonitor ✅

A monitored expectation of a device (expectation + observation channel).

```text
DeviceMonitor ⊑ ProcessMonitor
DeviceMonitor ⊑ ∃statementText.xsd:string
```

### DeviceFailureMode ✅

A fault of a device, with its consequence and recovery (Cell 01 failure_modes).

```text
DeviceFailureMode ⊑ FailureSignature
DeviceFailureMode ⊑ ∃hasRecoveryProcedure.RecoveryProcedure
DeviceFailureMode ⊑ ∃hasFailureConsequence.LabHazard
DeviceFailureMode ⊑ ∃statementText.xsd:string
```

### RecoveryProcedure ✅

What to do when a fault occurs.

```text
RecoveryProcedure ⊑ Repair
RecoveryProcedure ⊑ ∃statementText.xsd:string
```

### RiskControl ✅

A control measure a manual names (alarms, timing limits, interlocks, identity tracking).

```text
RiskControl ⊑ ManualItem
RiskControl ⊑ SafetyConstraint
RiskControl ⊑ ∃mitigatesHazard.LabHazard
```

### DeviceProcessMicrotheory ✅

Scoped process knowledge of a device: state variables, articulations, environment model.

```text
DeviceProcessMicrotheory ⊑ BodyWorldProcessMicrotheory
DeviceProcessMicrotheory ⊑ ∃microtheoryOf.LabArtifact
```

### TwinControllerCheck ✅

A precondition / rule check implemented in a twin device controller (refuses the command when violated).

```text
TwinControllerCheck ⊑ dul:Description
TwinControllerCheck ⊑ ∃exercisedByTest.TwinVerificationTest
```

### TwinVerificationTest ✅

A twin regression test (scripts/test_*.py) with its pass record.

```text
TwinVerificationTest ⊑ dul:InformationObject
TwinVerificationTest ⊑ ∃verificationTest.xsd:string
```

### TwinEnforcedPrecondition 🔧

Defined: a manual precondition the twin enforces.

```text
TwinEnforcedPrecondition ⊑ Precondition
TwinEnforcedPrecondition ≡ Precondition ⊓ ∃enforcedInTwinBy.TwinControllerCheck
```

## Safe action: hazards, safety rules, enforcement, admissibility of candidate actions

`lab-twin-safe-action-dl.md` — Safe action: lab hazards, safety rules as AICOR IncapabilityAssertions, biosafety as RS ContaminationCompatibility, authorisation as normative-admissibility Norms, their enforcement (interlocks, controller checks, critic gates) and the classification of candidate actions as unsafe / unauthorised.

### LabHazard ✅

A potential source of harm in the lab.

```text
LabHazard ⊑ dul:Description
LabHazard ⊑ ∃hazardTo.Entity
```

### HumanInjuryHazard ✅

Robot motion or pinch points near a person.

```text
HumanInjuryHazard ⊑ LabHazard
HumanInjuryHazard ⊑ ∃hazardTo.Entity
```

### CollisionHazard ✅

Robot / device / labware collision.

```text
CollisionHazard ⊑ LabHazard
CollisionHazard ⊑ ∃hazardTo.Entity
```

### ContaminationHazard ✅

Transfer of contaminants to cultures or reagents.

```text
ContaminationHazard ⊑ LabHazard
ContaminationHazard ⊑ ∃hazardTo.Entity
```

### SampleIntegrityHazard ✅

Loss of environment, time window or physical integrity.

```text
SampleIntegrityHazard ⊑ LabHazard
SampleIntegrityHazard ⊑ ∃hazardTo.Entity
```

### IdentityHazard ✅

Swap or loss of sample identity.

```text
IdentityHazard ⊑ LabHazard
IdentityHazard ⊑ ∃hazardTo.Entity
```

### MeasurementValidityHazard ✅

Measurements made with an invalid measurement chain.

```text
MeasurementValidityHazard ⊑ LabHazard
MeasurementValidityHazard ⊑ ∃hazardTo.Entity
```

### AsphyxiationHazard 🔧

Oxygen depletion from LN2 / CO2.

```text
AsphyxiationHazard ⊑ LabHazard
AsphyxiationHazard ⊑ ∃hazardTo.Entity
```

### FireHazard 🔧

Fire.

```text
FireHazard ⊑ LabHazard
FireHazard ⊑ ∃hazardTo.Entity
```

### ChemicalExposureHazard 🔧

Splash / exposure of a person.

```text
ChemicalExposureHazard ⊑ LabHazard
ChemicalExposureHazard ⊑ ∃hazardTo.Entity
```

### LabSafetyRule ✅

A universal prohibition on lab actions in a situation (AICOR IncapabilityAssertion: removes trajectories).

```text
LabSafetyRule ⊑ IncapabilityAssertion
LabSafetyRule ⊑ ∃mitigatesHazard.LabHazard
LabSafetyRule ⊑ ∃prohibitsTaskType.LabTaskType
LabSafetyRule ⊑ ∃derivedFromSource.dul:InformationObject
LabSafetyRule ⊑ ∃statementText.xsd:string
```

### HumanSafetyRule ✅

Protects people (enclosure, door interlocks, light curtain, e-stop).

```text
HumanSafetyRule ⊑ LabSafetyRule
HumanSafetyRule ⊑ ∃mitigatesHazard.HumanInjuryHazard
HumanSafetyRule ⊑ ∃enforcedBy.SafetyDevice
HumanSafetyRule ⊓ MachineProtectionRule ⊑ ⊥
```

### MachineProtectionRule ✅

Protects equipment and labware (airspace interlock, gate state, cabinet closed in transit).

```text
MachineProtectionRule ⊑ LabSafetyRule
MachineProtectionRule ⊑ ∃mitigatesHazard.CollisionHazard
MachineProtectionRule ⊓ HumanSafetyRule ⊑ ⊥
```

### BiosafetyRule ✅

Asepsis / contamination rules; gates intervention admissibility (RS ContaminationCompatibility).

```text
BiosafetyRule ⊑ LabSafetyRule
BiosafetyRule ⊑ ContaminationCompatibility
BiosafetyRule ⊑ ∃mitigatesHazard.ContaminationHazard
BiosafetyRule ⊓ HumanSafetyRule ⊑ ⊥
```

### SampleIntegrityRule ✅

Environment envelope, time outside the incubator, seating.

```text
SampleIntegrityRule ⊑ LabSafetyRule
SampleIntegrityRule ⊑ ∃mitigatesHazard.SampleIntegrityHazard
SampleIntegrityRule ⊓ HumanSafetyRule ⊑ ⊥
```

### IdentityRule ✅

Identity must be verified.

```text
IdentityRule ⊑ LabSafetyRule
IdentityRule ⊑ ∃mitigatesHazard.IdentityHazard
IdentityRule ⊓ HumanSafetyRule ⊑ ⊥
```

### MeasurementValidityRule ✅

No measurement with an invalid calibration / tool frame.

```text
MeasurementValidityRule ⊑ LabSafetyRule
MeasurementValidityRule ⊑ ∃mitigatesHazard.MeasurementValidityHazard
MeasurementValidityRule ⊓ HumanSafetyRule ⊑ ⊥
```

### AuthorizationNorm ✅

A normative rule: an action is permitted only with an authorisation (normative, not causal, admissibility).

```text
AuthorizationNorm ⊑ Norm
AuthorizationNorm ⊑ ∃prohibitsTaskType.LabTaskType
AuthorizationNorm ⊑ ∃statementText.xsd:string
```

### SafetySourceDocument ✅

A document safety knowledge is derived from (Cell 01 specification, rule files, site proposal).

```text
SafetySourceDocument ⊑ dul:InformationObject
SafetySourceDocument ⊑ ∃sourceDocument.xsd:string
```

### SafetyEnforcementMechanism 🔧

How a rule is enforced in the twin.

```text
SafetyEnforcementMechanism ⊑ dul:Description
SafetyEnforcementMechanism ⊑ ∃enforces.LabSafetyRule
```

### PhysicalInterlockMechanism ✅

Enforcement by a safety device (door switch, light curtain, e-stop).

```text
PhysicalInterlockMechanism ⊑ SafetyEnforcementMechanism
PhysicalInterlockMechanism ⊑ ∃realizedByDevice.SafetyDevice
```

### ControllerInterlockMechanism ✅

Enforcement by a device controller refusing a command (L12 airspace, L10 environment, H4 token).

```text
ControllerInterlockMechanism ⊑ SafetyEnforcementMechanism
ControllerInterlockMechanism ⊑ TwinControllerCheck
ControllerInterlockMechanism ⊑ ∃realizedByDevice.LabArtifact
```

### CriticGateMechanism ✅

Enforcement by Cell 01's critic vector: an event commits only if safety_ok (AICOR commitment checking).

```text
CriticGateMechanism ⊑ SafetyEnforcementMechanism
CriticGateMechanism ⊑ SafetyCheck
CriticGateMechanism ⊑ ∃testsCriterion.CommitmentCriterion
```

### UnsafeCandidateAction 🔧

Defined: a candidate action that violates a lab safety rule (inadmissible).

```text
UnsafeCandidateAction ⊑ CandidateAction
UnsafeCandidateAction ≡ CandidateAction ⊓ ∃violatesRule.LabSafetyRule
```

### UnauthorizedCandidateAction 🔧

Defined: a candidate action that violates an authorisation norm (normatively inadmissible).

```text
UnauthorizedCandidateAction ⊑ CandidateAction
UnauthorizedCandidateAction ≡ CandidateAction ⊓ ∃violatesRule.AuthorizationNorm
```

### RefusedCommand ✅

A command the twin refused, observed in a verification test.

```text
RefusedCommand ⊑ CandidateAction
RefusedCommand ⊑ ∃violatesRule.(LabSafetyRule ⊔ AuthorizationNorm)
RefusedCommand ⊑ ∃refusedByEntity.Entity
RefusedCommand ⊑ ∃verificationTest.xsd:string
```

### ProtectiveStopEvent ✅

A latched protective stop (e.g. light curtain broken without muting).

```text
ProtectiveStopEvent ⊑ dul:Event
ProtectiveStopEvent ⊑ ∃triggeredByDevice.SafetyDevice
```

## Culture experiments: designs, arms, interventions, readouts, runs, conclusions

`lab-twin-culture-experiments-dl.md` — Culture experiments: Cell 01's challenge-rescue design (RS StudyDesign) with arms, intervention specifications, observation schedule, interventions (RS BiologicalIntervention), morphology readouts (RS CellViabilityReadout), runs (RS ExperimentalEpisode), hypotheses and (withheld) conclusions.

### ChallengeRescueStudyDesign ✅

Cell 01's challenge-rescue design: graded challenge doses, rescue at 6 h, untreated controls, 4x imaging every 6 h to 72 h.

```text
ChallengeRescueStudyDesign ⊑ StudyDesign
ChallengeRescueStudyDesign ⊑ ∃hasArm.ChallengeOnlyArm
ChallengeRescueStudyDesign ⊑ ∃hasArm.ChallengeRescueArm
ChallengeRescueStudyDesign ⊑ ∃hasArm.ControlArm
ChallengeRescueStudyDesign ⊑ ∃observedBySchedule.ObservationSchedule
```

### ExperimentalArm ✅

A group of units treated alike.

```text
ExperimentalArm ⊑ dul:Description
ExperimentalArm ⊑ ∃assignsUnit.Well
```

### InterventionSpec ✅

A planned intervention (agent, dose, time).

```text
InterventionSpec ⊑ dul:Description
InterventionSpec ⊑ ∃doseAU.xsd:double
InterventionSpec ⊑ ∃time_h.xsd:double
```

### ChallengeSpec ✅

Planned challenge dose.

```text
ChallengeSpec ⊑ InterventionSpec
ChallengeSpec ⊑ ∃specifiesTask.ChallengeDosingTask
ChallengeSpec ⊓ RescueSpec ⊑ ⊥
```

### RescueSpec ✅

Planned rescue dose.

```text
RescueSpec ⊑ InterventionSpec
RescueSpec ⊑ ∃specifiesTask.RescueDosingTask
RescueSpec ⊓ ChallengeSpec ⊑ ⊥
```

### ChallengeOnlyArm 🔧

Defined: challenged, not rescued.

```text
ChallengeOnlyArm ⊑ ExperimentalArm
ChallengeOnlyArm ≡ ExperimentalArm ⊓ ∃appliesIntervention.ChallengeSpec ⊓ ¬∃appliesIntervention.RescueSpec
ChallengeOnlyArm ⊓ ChallengeRescueArm ⊑ ⊥
```

### ChallengeRescueArm 🔧

Defined: challenged and rescued.

```text
ChallengeRescueArm ⊑ ExperimentalArm
ChallengeRescueArm ≡ ExperimentalArm ⊓ ∃appliesIntervention.ChallengeSpec ⊓ ∃appliesIntervention.RescueSpec
ChallengeRescueArm ⊓ ChallengeOnlyArm ⊑ ⊥
```

### ControlArm 🔧

Defined: no intervention.

```text
ControlArm ⊑ ExperimentalArm
ControlArm ≡ ExperimentalArm ⊓ ¬∃appliesIntervention.InterventionSpec
ControlArm ⊓ ChallengeOnlyArm ⊑ ⊥
```

### ObservationSchedule ✅

When units are observed.

```text
ObservationSchedule ⊑ dul:Description
ObservationSchedule ⊑ ∃interval_h.xsd:double
ObservationSchedule ⊑ ∃horizon_h.xsd:double
```

### ChallengeIntervention ✅

A dose of the challenge agent into a well (L12 dose).

```text
ChallengeIntervention ⊑ BiologicalIntervention
ChallengeIntervention ⊑ ∃realizedByAction.ScientificActionDesignator
ChallengeIntervention ⊓ RescueIntervention ⊑ ⊥
```

### RescueIntervention ✅

A dose of the rescue agent into a well.

```text
RescueIntervention ⊑ BiologicalIntervention
RescueIntervention ⊑ ∃realizedByAction.ScientificActionDesignator
RescueIntervention ⊓ ChallengeIntervention ⊑ ⊥
```

### MorphologyViabilityReadout ✅

Viability inferred from bright-field morphology (radius, core OD, debris, haze) of a 4x image.

```text
MorphologyViabilityReadout ⊑ CellViabilityReadout
MorphologyViabilityReadout ⊑ ∃observationOf.WellOrganoid
```

### RescueHypothesis ✅

'Rescue at 6 h raises 72 h viability at challenge dose d.'

```text
RescueHypothesis ⊑ ScientificHypothesis
RescueHypothesis ⊑ ∃heldIn.CultureSDT
```

### CultureExperimentRun ✅

One executed run of the study in the twin.

```text
CultureExperimentRun ⊑ ExperimentalEpisode
CultureExperimentRun ⊑ ∃runOfStudy.ChallengeRescueStudyDesign
CultureExperimentRun ⊑ ∃scenarioName.xsd:string
```

### ScenarioCondition ✅

A condition of a run (nominal, injected fault).

```text
ScenarioCondition ⊑ dul:Description
ScenarioCondition ⊑ ∃statementText.xsd:string
```

### FaultInjection ✅

A deliberately injected fault.

```text
FaultInjection ⊑ ScenarioCondition
FaultInjection ⊑ ∃injectsHazard.LabHazard
```

### RescueComparisonConclusion ✅

Conclusion comparing a rescued with an unrescued well.

```text
RescueComparisonConclusion ⊑ ScientificConclusion
RescueComparisonConclusion ⊑ ≥2 concernsWell.Well
RescueComparisonConclusion ⊑ ∃claimStatus.xsd:string
```

### WithholdingReason ✅

Why a conclusion is withheld.

```text
WithholdingReason ⊑ dul:Description
WithholdingReason ⊑ ∃statementText.xsd:string
```

### UnverifiedComparatorReason ✅

A compared well received an uncommitted (unverified) intervention.

```text
UnverifiedComparatorReason ⊑ WithholdingReason
UnverifiedComparatorReason ⊑ ∃citesRule.LabSafetyRule
```

### ContaminationSuspectedReason ✅

A compared well is flagged contamination_suspected.

```text
ContaminationSuspectedReason ⊑ WithholdingReason
ContaminationSuspectedReason ⊑ ∃citesRule.BiosafetyRule
```

### WithheldConclusion 🔧

Defined: a conclusion withheld for a stated reason.

```text
WithheldConclusion ⊑ RescueComparisonConclusion
WithheldConclusion ≡ RescueComparisonConclusion ⊓ ∃withheldBecause.WithholdingReason
```

### WellBeliefEstimate ✅

The culture SDT's posterior estimate of a well's latent state (epistemic status: inferred).

```text
WellBeliefEstimate ⊑ StateEstimate
WellBeliefEstimate ⊑ ∃concernsWell.Well
```

### WellObservationRecord ✅

Measured morphology of one well at one session, with image / calibration provenance.

```text
WellObservationRecord ⊑ CellViabilityReadout
WellObservationRecord ⊑ ∃concernsWell.Well
WellObservationRecord ⊑ ∃radius_um.xsd:double
```

### InterventionRecord ✅

A dose event in a well's intervention history.

```text
InterventionRecord ⊑ dul:InformationObject
InterventionRecord ⊑ ∃partOf.InterventionHistory
InterventionRecord ⊑ ∃realizesIntervention.BiologicalIntervention
InterventionRecord ⊑ ∃isCommittedEvent.xsd:boolean
```

### UnverifiedInterventionRecord 🔧

Defined: an intervention record the ledger did not commit.

```text
UnverifiedInterventionRecord ⊑ InterventionRecord
UnverifiedInterventionRecord ≡ InterventionRecord ⊓ ∃isCommittedEvent.{false}
```

### WellQualityRecord ✅

ESS and anomaly flags.

```text
WellQualityRecord ⊑ dul:InformationObject
WellQualityRecord ⊑ ∃concernsWell.Well
```

### ContaminationSuspectedFlag ✅

Cell 01's contamination_suspected rule fired for a well.

```text
ContaminationSuspectedFlag ⊑ WellQualityRecord
ContaminationSuspectedFlag ⊑ ∃flagsHazard.ContaminationHazard
```

## Action records, monitor results and routing (Cell 01 NEEM records)

`lab-twin-records-dl.md` — Cell 01's NEEM-style action records (RS LabExecutionTrace), monitor results and routing (commit / quarantine / escalation / invalidation).

### CellActionRecord ✅

A Cell 01 NEEM-style record of one action (critic vector, monitors, routing).

```text
CellActionRecord ⊑ LabExecutionTrace
CellActionRecord ⊑ ∃recordsAction.LabAction
CellActionRecord ⊑ ∃hasRouting.RecordRouting
```

### MonitorResult ✅

Result of one Cell 01 monitor on an action.

```text
MonitorResult ⊑ dul:InformationObject
MonitorResult ⊑ ∃monitorPassed.xsd:boolean
MonitorResult ⊑ ∃monitorName.xsd:string
```

### FailedMonitorResult 🔧

Defined: a monitor that did not pass.

```text
FailedMonitorResult ⊑ MonitorResult
FailedMonitorResult ≡ MonitorResult ⊓ ∃monitorPassed.{false}
```

### BlockedActionRecord 🔧

Defined: a record with a failed monitor; its semantic event cannot commit.

```text
BlockedActionRecord ⊑ CellActionRecord
BlockedActionRecord ≡ CellActionRecord ⊓ ∃hasMonitorResult.FailedMonitorResult
```

### RecordRouting ✅

A routing outcome.

```text
RecordRouting ⊑ dul:Concept
RecordRouting ⊑ ∀classifiesRecord.CellActionRecord
```

### CommitRouting ✅

Commit (culture SDT / evidence layer / admission).

```text
CommitRouting ⊑ RecordRouting
CommitRouting ⊑ ∃routesTo.LabSemanticDigitalTwin
CommitRouting ⊓ QuarantineRouting ⊑ ⊥
```

### QuarantineRouting ✅

Object to H4 (a Repair).

```text
QuarantineRouting ⊑ RecordRouting
QuarantineRouting ⊑ ∃routesTo.QuarantineStation
QuarantineRouting ⊓ CommitRouting ⊑ ⊥
```

### EscalationRouting ✅

To a human (an AICOR HelpRequest).

```text
EscalationRouting ⊑ RecordRouting
EscalationRouting ⊑ ∃routesTo.dul:Agent
EscalationRouting ⊓ CommitRouting ⊑ ⊥
```

### InvalidationRouting ✅

Invalidate dependent measurements.

```text
InvalidationRouting ⊑ RecordRouting
InvalidationRouting ⊑ ∃routesTo.LabSemanticDigitalTwin
InvalidationRouting ⊓ CommitRouting ⊑ ⊥
```

## From a required information gain to the robot's physical actions and motions (derivation layer)

`lab-twin-experiment-to-motion-dl.md` — 

### CompetingRecoveryModel ✅

One of Cell 01's competing recovery models (mathematical-models.md §5), calibrated to the observed data.

```text
CompetingRecoveryModel ⊑ ScientificModel
CompetingRecoveryModel ⊑ ∃predictsReadout.MorphologyViabilityReadout
```

### GradedRecoveryModel ✅

M1: P_rec = σ(β0 − β1 I − β2 Δt + β3 d_r); no point of no return.

```text
GradedRecoveryModel ⊑ CompetingRecoveryModel
GradedRecoveryModel ⊑ ∃statementText.xsd:string
GradedRecoveryModel ⊓ ThresholdRecoveryModel ⊑ ⊥
```

### ThresholdRecoveryModel ✅

M2: rescue fails once the cumulative injury burden B(Δt) ≥ B*.

```text
ThresholdRecoveryModel ⊑ CompetingRecoveryModel
ThresholdRecoveryModel ⊑ ∃statementText.xsd:string
ThresholdRecoveryModel ⊓ GradedRecoveryModel ⊑ ⊥
```

### ProtectiveThresholdModel ✅

M3: B*(t) = B0* + α P(t): the threshold moves with adaptive protection.

```text
ProtectiveThresholdModel ⊑ CompetingRecoveryModel
ProtectiveThresholdModel ⊑ ∃statementText.xsd:string
ProtectiveThresholdModel ⊓ GradedRecoveryModel ⊑ ⊥
```

### InformationGainRequirement 🔧

What an experiment must teach: a minimum expected information gain over the competing models.

```text
InformationGainRequirement ⊑ dul:Description
InformationGainRequirement ⊑ ∃requiredGain_bits.xsd:double
```

### ExperimentCandidate ✅

A candidate delayed-rescue experiment (dose, rescue delay, replicates) with its EIG and cost.

```text
ExperimentCandidate ⊑ ScientificProposal
ExperimentCandidate ⊑ ≥2 discriminatesModel.CompetingRecoveryModel
ExperimentCandidate ⊑ ∃expectedGain_bits.xsd:double
ExperimentCandidate ⊑ ∃rescueDelay_h.xsd:double
ExperimentCandidate ⊑ ∃doseAU.xsd:double
ExperimentCandidate ⊑ ∃replicateCount.xsd:integer
ExperimentCandidate ⊑ ∃planCost.xsd:integer
```

### InformationGainEstimate ✅

EIG(a) = E_y KL(p(M|D,y,a) ‖ p(M|D)) (Cell 01 §10), by nested Monte Carlo over the calibrated models.

```text
InformationGainEstimate ⊑ dul:InformationObject
InformationGainEstimate ⊑ ∃estimatesGainOf.ExperimentCandidate
InformationGainEstimate ⊑ ∃conditionedOnBelief.CultureSDT
InformationGainEstimate ⊑ ∃expectedGain_bits.xsd:double
```

### SelectedExperiment 🔧

Defined: the candidate chosen under a gain requirement (least cost among those meeting it).

```text
SelectedExperiment ⊑ ExperimentCandidate
SelectedExperiment ≡ ExperimentCandidate ⊓ ∃selectedUnder.InformationGainRequirement
```

### DelayedRescueStudyDesign ✅

A study design with a chosen rescue delay, comparator and untreated control.

```text
DelayedRescueStudyDesign ⊑ StudyDesign
DelayedRescueStudyDesign ⊑ ∃hasArm.ChallengeRescueArm
DelayedRescueStudyDesign ⊑ ∃hasArm.ChallengeOnlyArm
DelayedRescueStudyDesign ⊑ ∃hasArm.ControlArm
DelayedRescueStudyDesign ⊑ ∃rescueDelay_h.xsd:double
```

### ExperimentRealisationPlan ✅

The derived protocol that realises a selected experiment in the lab: sessions of material, scene and motion designators.

```text
ExperimentRealisationPlan ⊑ ExperimentalProtocol
ExperimentRealisationPlan ⊑ ∃realisesProposal.SelectedExperiment
ExperimentRealisationPlan ⊑ ∃hasSession.ProtocolSession
```

### ProtocolSession ✅

One trip of the plate out of the incubator at a scheduled culture time.

```text
ProtocolSession ⊑ dul:Description
ProtocolSession ⊑ ∃scheduledAt_h.xsd:double
ProtocolSession ⊑ ∃hasStep.LabActionDesignator
```

### LabActionDesignator ✅

A designator of the realisation plan (RS ScientificActionDesignator).

```text
LabActionDesignator ⊑ ScientificActionDesignator
LabActionDesignator ⊑ ∃stepIndex.xsd:integer
```

### MaterialStepDesignator ✅

What happens to the material: dose well w, image well w.

```text
MaterialStepDesignator ⊑ LabActionDesignator
MaterialStepDesignator ⊑ MaterialScientificDesignator
MaterialStepDesignator ⊑ ∃refinesInto.SceneStepDesignator
MaterialStepDesignator ⊓ SceneStepDesignator ⊑ ⊥
```

### ChallengeDoseDesignator ✅

Dose challenge.

```text
ChallengeDoseDesignator ⊑ MaterialStepDesignator
ChallengeDoseDesignator ⊑ ∃doseAU.xsd:double
```

### RescueDoseDesignator ✅

Dose rescue.

```text
RescueDoseDesignator ⊑ MaterialStepDesignator
RescueDoseDesignator ⊑ ∃doseAU.xsd:double
```

### ImageWellDesignator ✅

Image a well.

```text
ImageWellDesignator ⊑ MaterialStepDesignator
ImageWellDesignator ⊑ ∃concernsWell.Well
```

### SceneStepDesignator ✅

Bound to the scene: device, robot, poses.

```text
SceneStepDesignator ⊑ LabActionDesignator
SceneStepDesignator ⊑ SceneGroundedDesignator
SceneStepDesignator ⊑ ∃boundToDevice.LabArtifact
SceneStepDesignator ⊓ MaterialStepDesignator ⊑ ⊥
```

### PlateTransferDesignator ✅

Move the plate between two seat poses with one robot (one leg of a route).

```text
PlateTransferDesignator ⊑ SceneStepDesignator
PlateTransferDesignator ⊑ ∃performedByRobot.CellRobot
PlateTransferDesignator ⊑ ∃boundToPose.PlateSeatPose
PlateTransferDesignator ⊑ ∃refinesInto.MotionStepDesignator
```

### DeviceOperationDesignator ✅

A device operation (dose, image, present, store).

```text
DeviceOperationDesignator ⊑ SceneStepDesignator
DeviceOperationDesignator ⊑ ∃boundToDevice.LabAutomationDevice
DeviceOperationDesignator ⊑ ∃refinesInto.DeviceCommandDesignator
```

### MotionStepDesignator ✅

A robot body-motion primitive (RS BodyMotionDesignator) bound to a pose.

```text
MotionStepDesignator ⊑ LabActionDesignator
MotionStepDesignator ⊑ BodyMotionDesignator
MotionStepDesignator ⊑ ∃performedByRobot.CellRobot
MotionStepDesignator ⊑ ∃primitiveName.xsd:string
MotionStepDesignator ⊑ ∃estimatedDuration_s.xsd:double
MotionStepDesignator ⊓ MaterialStepDesignator ⊑ ⊥
MotionStepDesignator ⊓ KernelScientificDesignator ⊑ ⊥
```

### ApproachMotion ✅

Move to the approach pose above a seat.

```text
ApproachMotion ⊑ MotionStepDesignator
ApproachMotion ⊑ ∃boundToPose.TwinPose
```

### InsertMotion ✅

Descend to the seat pose (compliant).

```text
InsertMotion ⊑ MotionStepDesignator
InsertMotion ⊑ ∃boundToPose.TwinPose
```

### GraspMotion ✅

Close the gripper on the plate.

```text
GraspMotion ⊑ MotionStepDesignator
GraspMotion ⊑ ∃boundToPose.TwinPose
```

### LiftMotion ✅

Lift the plate off the seat.

```text
LiftMotion ⊑ MotionStepDesignator
LiftMotion ⊑ ∃boundToPose.TwinPose
```

### TransitMotion ✅

Planned joint-space / rail transit between approach poses.

```text
TransitMotion ⊑ MotionStepDesignator
TransitMotion ⊑ ∃boundToPose.TwinPose
```

### PlaceMotion ✅

Compliant placement into the target seat.

```text
PlaceMotion ⊑ MotionStepDesignator
PlaceMotion ⊑ ∃boundToPose.TwinPose
```

### ReleaseMotion ✅

Open the gripper.

```text
ReleaseMotion ⊑ MotionStepDesignator
ReleaseMotion ⊑ ∃boundToPose.TwinPose
```

### RetractMotion ✅

Retract to the approach pose (leaves device airspace).

```text
RetractMotion ⊑ MotionStepDesignator
RetractMotion ⊑ ∃boundToPose.TwinPose
```

### ToolCoupleMotion ✅

Couple an exchangeable tool at the magazine.

```text
ToolCoupleMotion ⊑ MotionStepDesignator
ToolCoupleMotion ⊑ ∃boundToPose.TwinPose
```

### DeviceCommandDesignator ✅

A device-level command (present, stow, tip pick, aspirate, dispense, eject, load, image, store, QC).

```text
DeviceCommandDesignator ⊑ LabActionDesignator
DeviceCommandDesignator ⊑ ScientificActionDesignator
DeviceCommandDesignator ⊑ ∃commandsDevice.LabAutomationDevice
DeviceCommandDesignator ⊑ ∃primitiveName.xsd:string
DeviceCommandDesignator ⊓ MaterialStepDesignator ⊑ ⊥
DeviceCommandDesignator ⊓ KernelScientificDesignator ⊑ ⊥
```

### SafetyStepDesignator ✅

A step inserted to discharge a safety rule (environment wait, QC calibration, interlock check).

```text
SafetyStepDesignator ⊑ DeviceCommandDesignator
SafetyStepDesignator ⊑ ∃dischargesRule.LabSafetyRule
```

### PlanDerivation ✅

One run of the derivation (answer-set program over the ontology's ABox and the EIG candidates).

```text
PlanDerivation ⊑ dul:Description
PlanDerivation ⊑ ∃derivesPlan.ExperimentRealisationPlan
PlanDerivation ⊑ ∃appliesAxiomSet.DerivationAxiomSet
```

### DerivationAxiomSet ✅

The L3 axioms E2M1-E2M8 (L3-logical-axiomatization/axioms/experiment-to-motion-axioms.md).

```text
DerivationAxiomSet ⊑ dul:InformationObject
DerivationAxiomSet ⊑ ∃sourceDocument.xsd:string
```

### RealisedInformationGain ✅

KL(p(M|D,y) ‖ p(M|D)) after executing the plan.

```text
RealisedInformationGain ⊑ dul:InformationObject
RealisedInformationGain ⊑ ∃realisedGain_bits.xsd:double
RealisedInformationGain ⊑ ∃about.ExperimentRealisationPlan
```

## The robot science assistant kernel: action-designator categories, lifecycle and audit entries

`lab-twin-rsa-kernel-dl.md` — 

### KernelScientificDesignator ✅

Scientific-level designator of the kernel (experiment, wait, intervene, measure; RS scientific actions); realised by lower-level designators.

```text
KernelScientificDesignator ⊑ LabActionDesignator
KernelScientificDesignator ⊑ ∃refinesInto.LabActionDesignator
KernelScientificDesignator ⊓ KernelLabTaskDesignator ⊑ ⊥
```

### KernelLabTaskDesignator ✅

Lab-task designator (Cell 01 CRAM designator schemas: retrieve, store, transport, dose, image, qc, quarantine).

```text
KernelLabTaskDesignator ⊑ LabActionDesignator
KernelLabTaskDesignator ⊑ ∃refinesInto.LabActionDesignator
KernelLabTaskDesignator ⊓ KernelScientificDesignator ⊑ ⊥
```

### KernelManipulationDesignator ✅

Manipulation-action designator (CRAM action categories: picking-up, placing, transporting, coupling, presenting, stowing).

```text
KernelManipulationDesignator ⊑ LabActionDesignator
KernelManipulationDesignator ⊑ ∃refinesInto.LabActionDesignator
KernelManipulationDesignator ⊓ KernelScientificDesignator ⊑ ⊥
```

### ObjectDisplacementDesignator ✅

Designators of actions whose effect class is ObjectDisplacement (AICOR action-category partition, CRAM action-category-dl).

```text
ObjectDisplacementDesignator ⊑ LabActionDesignator
ObjectDisplacementDesignator ⊑ ∃designatesAction.LabAction
ObjectDisplacementDesignator ⊓ ConfigurationChangeDesignator ⊑ ⊥
```

### ConfigurationChangeDesignator ✅

Designators of actions whose effect class is ConfigurationChange (AICOR action-category partition, CRAM action-category-dl).

```text
ConfigurationChangeDesignator ⊑ LabActionDesignator
ConfigurationChangeDesignator ⊑ ∃designatesAction.LabAction
ConfigurationChangeDesignator ⊓ ObjectDisplacementDesignator ⊑ ⊥
```

### SubstanceManipulationDesignator ✅

Designators of actions whose effect class is SubstanceManipulation (AICOR action-category partition, CRAM action-category-dl).

```text
SubstanceManipulationDesignator ⊑ LabActionDesignator
SubstanceManipulationDesignator ⊑ ∃designatesAction.LabAction
SubstanceManipulationDesignator ⊓ ObjectDisplacementDesignator ⊑ ⊥
```

### ConnectingActionDesignator ✅

Designators of actions whose effect class is ConnectingAction (AICOR action-category partition, CRAM action-category-dl).

```text
ConnectingActionDesignator ⊑ LabActionDesignator
ConnectingActionDesignator ⊑ ∃designatesAction.LabAction
ConnectingActionDesignator ⊓ ObjectDisplacementDesignator ⊑ ⊥
```

### PerceptionDesignator ✅

Designators of actions whose effect class is Perception (AICOR action-category partition, CRAM action-category-dl).

```text
PerceptionDesignator ⊑ LabActionDesignator
PerceptionDesignator ⊑ ∃designatesAction.LabAction
PerceptionDesignator ⊓ ObjectDisplacementDesignator ⊑ ⊥
```

### MaintenanceActionDesignator ✅

Designators of actions whose effect class is MaintenanceAction (AICOR action-category partition, CRAM action-category-dl).

```text
MaintenanceActionDesignator ⊑ LabActionDesignator
MaintenanceActionDesignator ⊑ ∃designatesAction.LabAction
MaintenanceActionDesignator ⊓ ObjectDisplacementDesignator ⊑ ⊥
```

### RegulationActionDesignator ✅

Designators of actions whose effect class is RegulationAction (AICOR action-category partition, CRAM action-category-dl).

```text
RegulationActionDesignator ⊑ LabActionDesignator
RegulationActionDesignator ⊑ ∃designatesAction.LabAction
RegulationActionDesignator ⊓ ObjectDisplacementDesignator ⊑ ⊥
```

### TransportFacetDesignator 🔧

Designators of transport actions (GARMI three manipulation classes; orthogonal to the effect class).

```text
TransportFacetDesignator ⊑ LabActionDesignator
TransportFacetDesignator ⊑ ∃designatesAction.LabAction
TransportFacetDesignator ⊓ OperationFacetDesignator ⊑ ⊥
```

### OperationFacetDesignator 🔧

Designators of operation actions (GARMI three manipulation classes; orthogonal to the effect class).

```text
OperationFacetDesignator ⊑ LabActionDesignator
OperationFacetDesignator ⊑ ∃designatesAction.LabAction
OperationFacetDesignator ⊓ TransportFacetDesignator ⊑ ⊥
```

### TransformationFacetDesignator 🔧

Designators of transformation actions (GARMI three manipulation classes; orthogonal to the effect class).

```text
TransformationFacetDesignator ⊑ LabActionDesignator
TransformationFacetDesignator ⊑ ∃designatesAction.LabAction
TransformationFacetDesignator ⊓ TransportFacetDesignator ⊑ ⊥
```

### ExperimentDesignator ✅

Kernel category 'experiment': run the selected experiment. HADL: (an action (type experiment) (design ?d) (requirement (eig >= ?g))). Sources: e2m derive_plan selection, RSV experimental-workflow-dl, uc_ccr se_loop.

```text
ExperimentDesignator ⊑ KernelScientificDesignator
ExperimentDesignator ⊑ LabActionDesignator
ExperimentDesignator ≡ KernelScientificDesignator ⊓ ∃kernelCategory.{experiment}
```

### WaitDesignator ✅

Kernel category 'wait': wait for culture time. HADL: (an action (type wait) (until (culture-time ?t))). Sources: RSV scientific-action-designator-dl Wait.

```text
WaitDesignator ⊑ KernelScientificDesignator
WaitDesignator ⊑ LabActionDesignator
WaitDesignator ≡ KernelScientificDesignator ⊓ ∃kernelCategory.{wait}
```

### InterveneDesignator ✅

Kernel category 'intervene': intervene on a culture well. HADL: (an action (type intervene) (reagent ?r) (dose ?au) (well (the well ?w))). Sources: RSV scientific-action-designator-dl Intervene, C01 report §9.

```text
InterveneDesignator ⊑ KernelScientificDesignator
InterveneDesignator ⊑ MaterialStepDesignator
InterveneDesignator ⊑ ∃refinesInto.DoseDesignator
InterveneDesignator ≡ KernelScientificDesignator ⊓ ∃kernelCategory.{intervene}
```

### MeasureDesignator ✅

Kernel category 'measure': measure a culture well. HADL: (an action (type measure) (readout organoid-radius) (well (the well ?w))). Sources: RSV scientific-action-designator-dl Measure.

```text
MeasureDesignator ⊑ KernelScientificDesignator
MeasureDesignator ⊑ ImageWellDesignator
MeasureDesignator ⊑ ∃refinesInto.ImageDesignator
MeasureDesignator ≡ KernelScientificDesignator ⊓ ∃kernelCategory.{measure}
```

### RunSessionDesignator ✅

Kernel category 'run_session': run one session trip. HADL: (an action (type run-session) (plate (the plate ?p)) (materials ?m)). Sources: e2m E2M4 sessions, C01 SESSION_HANDOFF first slice.

```text
RunSessionDesignator ⊑ KernelLabTaskDesignator
RunSessionDesignator ⊑ LabActionDesignator
RunSessionDesignator ≡ KernelLabTaskDesignator ⊓ ∃kernelCategory.{run_session}
```

### RetrieveDesignator ✅

Kernel category 'retrieve': retrieve the plate from storage. HADL: (an action (type retrieve) (object (the plate ?p)) (source (the location home))). Sources: C01 cram_designator_schemas retrieve, e2m S7.

```text
RetrieveDesignator ⊑ KernelLabTaskDesignator
RetrieveDesignator ⊑ ObjectDisplacementDesignator
RetrieveDesignator ⊑ TransportFacetDesignator
RetrieveDesignator ⊑ ∃designatesAction.RetrieveAction
RetrieveDesignator ≡ KernelLabTaskDesignator ⊓ ∃kernelCategory.{retrieve}
```

### StoreDesignator ✅

Kernel category 'store': store the plate in the incubator. HADL: (an action (type store) (object (the plate ?p)) (location (the location home))). Sources: C01 cram_designator_schemas store, e2m S2.

```text
StoreDesignator ⊑ KernelLabTaskDesignator
StoreDesignator ⊑ ObjectDisplacementDesignator
StoreDesignator ⊑ TransportFacetDesignator
StoreDesignator ⊑ ∃designatesAction.StoreAction
StoreDesignator ≡ KernelLabTaskDesignator ⊓ ∃kernelCategory.{store}
```

### TransportLabDesignator ✅

Kernel category 'transport_lab': transport the plate between stations. HADL: (an action (type transport) (object (the plate ?p)) (target (a location (serves ?function)))). Sources: C01 cram_designator_schemas transport, e2m E2M6 routes, coraplex TransportAction.

```text
TransportLabDesignator ⊑ KernelLabTaskDesignator
TransportLabDesignator ⊑ ObjectDisplacementDesignator
TransportLabDesignator ⊑ TransportFacetDesignator
TransportLabDesignator ⊑ ∃designatesAction.TransferAction
TransportLabDesignator ⊑ ∃refinesInto.TransportingDesignator
TransportLabDesignator ≡ KernelLabTaskDesignator ⊓ ∃kernelCategory.{transport_lab}
```

### DoseDesignator ✅

Kernel category 'dose': dose a culture well. HADL: (an action (type dose) (device (a device (capable dose_well))) (well (the well ?w)) (reagent (the reagent ?r)) (volume ?v)). Sources: C01 cram_designator_schemas dose, C01 L12 action_contracts dose_well, e2m E2M5.

```text
DoseDesignator ⊑ KernelLabTaskDesignator
DoseDesignator ⊑ SubstanceManipulationDesignator
DoseDesignator ⊑ TransformationFacetDesignator
DoseDesignator ⊑ ∃designatesAction.DoseAction
DoseDesignator ≡ KernelLabTaskDesignator ⊓ ∃kernelCategory.{dose}
```

### ImageDesignator ✅

Kernel category 'image': image a culture well. HADL: (an action (type image) (device (a device (capable image_well))) (well (the well ?w))). Sources: C01 cram_designator_schemas image, C01 L17 record, RSV measurement-binding lever.

```text
ImageDesignator ⊑ KernelLabTaskDesignator
ImageDesignator ⊑ PerceptionDesignator
ImageDesignator ⊑ OperationFacetDesignator
ImageDesignator ⊑ ∃designatesAction.ImageAction
ImageDesignator ≡ KernelLabTaskDesignator ⊓ ∃kernelCategory.{image}
```

### CalibrateDesignator ✅

Kernel category 'calibrate': calibrate a measurement device at its QC station. HADL: (an action (type calibrate) (target (the device ?d)) (station (a device (qc-station-for ?d)))). Sources: C01 cram_designator_schemas qc, e2m S3.

```text
CalibrateDesignator ⊑ KernelLabTaskDesignator
CalibrateDesignator ⊑ MaintenanceActionDesignator
CalibrateDesignator ⊑ OperationFacetDesignator
CalibrateDesignator ⊑ ∃designatesAction.QCAction
CalibrateDesignator ≡ KernelLabTaskDesignator ⊓ ∃kernelCategory.{calibrate}
```

### QuarantineDesignator ✅

Kernel category 'quarantine': quarantine a plate. HADL: (an action (type quarantine) (object (the plate ?p)) (reason ?why)). Sources: C01 cram_designator_schemas quarantine, C01 H4 record.

```text
QuarantineDesignator ⊑ KernelLabTaskDesignator
QuarantineDesignator ⊑ ObjectDisplacementDesignator
QuarantineDesignator ⊑ TransportFacetDesignator
QuarantineDesignator ⊑ ∃designatesAction.QuarantineAction
QuarantineDesignator ≡ KernelLabTaskDesignator ⊓ ∃kernelCategory.{quarantine}
```

### TransportingDesignator ✅

Kernel category 'transporting': transport by one robot (one leg). HADL: (an action (type transporting) (agent (a robot (serves ?src ?dst))) (object (the plate ?p)) (from ?src) (to ?dst)). Sources: coraplex TransportAction, CRAM TASK-TAXONOMY A.

```text
TransportingDesignator ⊑ KernelManipulationDesignator
TransportingDesignator ⊑ ObjectDisplacementDesignator
TransportingDesignator ⊑ TransportFacetDesignator
TransportingDesignator ⊑ PlateTransferDesignator
TransportingDesignator ⊑ ∃refinesInto.PickingUpDesignator
TransportingDesignator ⊑ ∃refinesInto.PlacingDesignator
TransportingDesignator ≡ KernelManipulationDesignator ⊓ ∃kernelCategory.{transporting}
```

### PickingUpDesignator ✅

Kernel category 'picking_up': pick up the plate. HADL: (an action (type picking-up) (object (the plate ?p)) (location (the seat ?s))). Sources: coraplex PickUpAction, Flanagan reach-lift.

```text
PickingUpDesignator ⊑ KernelManipulationDesignator
PickingUpDesignator ⊑ ObjectDisplacementDesignator
PickingUpDesignator ⊑ TransportFacetDesignator
PickingUpDesignator ⊑ PlateTransferDesignator
PickingUpDesignator ≡ KernelManipulationDesignator ⊓ ∃kernelCategory.{picking_up}
```

### PlacingDesignator ✅

Kernel category 'placing': place the plate. HADL: (an action (type placing) (object (the plate ?p)) (location (the seat ?s))). Sources: coraplex PlaceAction.

```text
PlacingDesignator ⊑ KernelManipulationDesignator
PlacingDesignator ⊑ ObjectDisplacementDesignator
PlacingDesignator ⊑ TransportFacetDesignator
PlacingDesignator ⊑ PlateTransferDesignator
PlacingDesignator ≡ KernelManipulationDesignator ⊓ ∃kernelCategory.{placing}
```

### CouplingToolDesignator ✅

Kernel category 'coupling_tool': couple the plate gripper tool. HADL: (an action (type coupling-tool) (agent ?r) (tool (the tool ?t))). Sources: OKF tool-use (tool extends body), e2m S4.

```text
CouplingToolDesignator ⊑ KernelManipulationDesignator
CouplingToolDesignator ⊑ ConnectingActionDesignator
CouplingToolDesignator ⊑ TransportFacetDesignator
CouplingToolDesignator ⊑ SceneStepDesignator
CouplingToolDesignator ⊑ ∃refinesInto.ToolCoupleMotion
CouplingToolDesignator ≡ KernelManipulationDesignator ⊓ ∃kernelCategory.{coupling_tool}
```

### PresentingDesignator ✅

Kernel category 'presenting': present the device's plate shuttle. HADL: (an action (type presenting) (device ?d)). Sources: CRAM TASK-TAXONOMY B tend (access), H4 v2 shuttle.

```text
PresentingDesignator ⊑ KernelManipulationDesignator
PresentingDesignator ⊑ ConfigurationChangeDesignator
PresentingDesignator ⊑ OperationFacetDesignator
PresentingDesignator ⊑ DeviceOperationDesignator
PresentingDesignator ⊑ ∃refinesInto.PresentCommand
PresentingDesignator ≡ KernelManipulationDesignator ⊓ ∃kernelCategory.{presenting}
```

### StowingDesignator ✅

Kernel category 'stowing': stow the device's plate shuttle. HADL: (an action (type stowing) (device ?d)). Sources: CRAM TASK-TAXONOMY B tend (access).

```text
StowingDesignator ⊑ KernelManipulationDesignator
StowingDesignator ⊑ ConfigurationChangeDesignator
StowingDesignator ⊑ OperationFacetDesignator
StowingDesignator ⊑ DeviceOperationDesignator
StowingDesignator ⊑ ∃refinesInto.StowCommand
StowingDesignator ≡ KernelManipulationDesignator ⊓ ∃kernelCategory.{stowing}
```

### CheckInterlocksCommand 🔧

Kernel category 'check_interlocks': check enclosure interlocks. HADL: -. Sources: kernel registry.

```text
CheckInterlocksCommand ⊑ DeviceCommandDesignator
CheckInterlocksCommand ⊑ PerceptionDesignator
CheckInterlocksCommand ⊑ SafetyStepDesignator
CheckInterlocksCommand ≡ DeviceCommandDesignator ⊓ ∃kernelCategory.{check_interlocks}
```

### VerifyIdentityCommand 🔧

Kernel category 'verify_identity': read plate identity. HADL: -. Sources: kernel registry.

```text
VerifyIdentityCommand ⊑ DeviceCommandDesignator
VerifyIdentityCommand ⊑ PerceptionDesignator
VerifyIdentityCommand ⊑ SafetyStepDesignator
VerifyIdentityCommand ≡ DeviceCommandDesignator ⊓ ∃kernelCategory.{verify_identity}
```

### PresentCommand 🔧

Kernel category 'present': present shuttle. HADL: -. Sources: kernel registry.

```text
PresentCommand ⊑ DeviceCommandDesignator
PresentCommand ⊑ ConfigurationChangeDesignator
PresentCommand ≡ DeviceCommandDesignator ⊓ ∃kernelCategory.{present}
```

### StowCommand 🔧

Kernel category 'stow': stow shuttle. HADL: -. Sources: kernel registry.

```text
StowCommand ⊑ DeviceCommandDesignator
StowCommand ⊑ ConfigurationChangeDesignator
StowCommand ≡ DeviceCommandDesignator ⊓ ∃kernelCategory.{stow}
```

### WaitEnvironmentCommand 🔧

Kernel category 'wait_environment': wait for environment. HADL: -. Sources: kernel registry.

```text
WaitEnvironmentCommand ⊑ DeviceCommandDesignator
WaitEnvironmentCommand ⊑ RegulationActionDesignator
WaitEnvironmentCommand ⊑ SafetyStepDesignator
WaitEnvironmentCommand ≡ DeviceCommandDesignator ⊓ ∃kernelCategory.{wait_environment}
```

### StoreCmdCommand 🔧

Kernel category 'store_cmd': store plate in slot. HADL: -. Sources: kernel registry.

```text
StoreCmdCommand ⊑ DeviceCommandDesignator
StoreCmdCommand ⊑ ObjectDisplacementDesignator
StoreCmdCommand ≡ DeviceCommandDesignator ⊓ ∃kernelCategory.{store_cmd}
```

### TipPickCommand 🔧

Kernel category 'tip_pick': pick a tip. HADL: -. Sources: kernel registry.

```text
TipPickCommand ⊑ DeviceCommandDesignator
TipPickCommand ⊑ ConnectingActionDesignator
TipPickCommand ⊑ TransformationFacetDesignator
TipPickCommand ≡ DeviceCommandDesignator ⊓ ∃kernelCategory.{tip_pick}
```

### AspirateCommand 🔧

Kernel category 'aspirate': aspirate reagent. HADL: -. Sources: kernel registry.

```text
AspirateCommand ⊑ DeviceCommandDesignator
AspirateCommand ⊑ SubstanceManipulationDesignator
AspirateCommand ⊑ TransformationFacetDesignator
AspirateCommand ≡ DeviceCommandDesignator ⊓ ∃kernelCategory.{aspirate}
```

### DispenseCommand 🔧

Kernel category 'dispense': dispense into well. HADL: -. Sources: kernel registry.

```text
DispenseCommand ⊑ DeviceCommandDesignator
DispenseCommand ⊑ SubstanceManipulationDesignator
DispenseCommand ⊑ TransformationFacetDesignator
DispenseCommand ≡ DeviceCommandDesignator ⊓ ∃kernelCategory.{dispense}
```

### TipEjectCommand 🔧

Kernel category 'tip_eject': eject tip to waste. HADL: -. Sources: kernel registry.

```text
TipEjectCommand ⊑ DeviceCommandDesignator
TipEjectCommand ⊑ ConnectingActionDesignator
TipEjectCommand ⊑ TransformationFacetDesignator
TipEjectCommand ≡ DeviceCommandDesignator ⊓ ∃kernelCategory.{tip_eject}
```

### LoadCommand 🔧

Kernel category 'load': load plate onto stage. HADL: -. Sources: kernel registry.

```text
LoadCommand ⊑ DeviceCommandDesignator
LoadCommand ⊑ ObjectDisplacementDesignator
LoadCommand ⊑ OperationFacetDesignator
LoadCommand ≡ DeviceCommandDesignator ⊓ ∃kernelCategory.{load}
```

### ImageWellCommand 🔧

Kernel category 'image_well': image a well. HADL: -. Sources: kernel registry.

```text
ImageWellCommand ⊑ DeviceCommandDesignator
ImageWellCommand ⊑ PerceptionDesignator
ImageWellCommand ⊑ OperationFacetDesignator
ImageWellCommand ≡ DeviceCommandDesignator ⊓ ∃kernelCategory.{image_well}
```

### AutofocusCommand 🔧

Kernel category 'autofocus': fresh autofocus on a well. HADL: -. Sources: kernel registry.

```text
AutofocusCommand ⊑ DeviceCommandDesignator
AutofocusCommand ⊑ PerceptionDesignator
AutofocusCommand ⊑ OperationFacetDesignator
AutofocusCommand ≡ DeviceCommandDesignator ⊓ ∃kernelCategory.{autofocus}
```

### IncubateCommand 🔧

Kernel category 'incubate': hold the plate in the incubator until a culture time. HADL: -. Sources: kernel registry.

```text
IncubateCommand ⊑ DeviceCommandDesignator
IncubateCommand ⊑ RegulationActionDesignator
IncubateCommand ⊑ OperationFacetDesignator
IncubateCommand ≡ DeviceCommandDesignator ⊓ ∃kernelCategory.{incubate}
```

### ContainCommand 🔧

Kernel category 'contain': contain a plate in quarantine. HADL: -. Sources: kernel registry.

```text
ContainCommand ⊑ DeviceCommandDesignator
ContainCommand ⊑ ConfigurationChangeDesignator
ContainCommand ⊑ OperationFacetDesignator
ContainCommand ≡ DeviceCommandDesignator ⊓ ∃kernelCategory.{contain}
```

### ValidateCommand 🔧

Kernel category 'validate': run reference-plate validation. HADL: -. Sources: kernel registry.

```text
ValidateCommand ⊑ DeviceCommandDesignator
ValidateCommand ⊑ MaintenanceActionDesignator
ValidateCommand ⊑ SafetyStepDesignator
ValidateCommand ≡ DeviceCommandDesignator ⊓ ∃kernelCategory.{validate}
```

### DesignatorLifecycleState ✅

Cell 01 designator lifecycle: open, grounded, accepted, executing, executed, failed, repaired, abstained, escalated (+ repairing, replanned, policy_violation as executor events).

```text
DesignatorLifecycleState ⊑ dul:Concept
DesignatorLifecycleState ⊑ ∃statementText.xsd:string
```

### KernelConstraint ✅

A constraint of the kernel registry, checked at acceptance, after execution, as a policy, or by the experimental critic.

```text
KernelConstraint ⊑ dul:Description
KernelConstraint ⊑ ∃sourceDocument.xsd:string
KernelConstraint ⊑ ∃constrainsDesignator.LabActionDesignator
```

### RealizationConstraint ✅

Did it run correctly and safely (uc_ccr realization column).

```text
RealizationConstraint ⊑ KernelConstraint
RealizationConstraint ⊑ ∃constrainsDesignator.LabActionDesignator
RealizationConstraint ⊓ ValidityConstraint ⊑ ⊥
```

### EvidenceItem ✅

An observation, reading or record attached to an audit entry, content-hashed.

```text
EvidenceItem ⊑ dul:InformationObject
EvidenceItem ⊑ ∃evidenceSha256.xsd:string
```

### CommitmentAuditEntry ✅

One hash-chained audit entry per designator lifecycle transition (uc_ccr audit.py + Cell 01 NEEM record sections + VRB warrant entry ⟨grounds, constraints discharged, verdict, disposition⟩). Not AICOR's CommitmentRecord (an episode-level Description containing action tokens and episodes; D-LAT-11).

```text
CommitmentAuditEntry ⊑ LabExecutionTrace
CommitmentAuditEntry ⊑ ∃recordsDesignator.LabActionDesignator
CommitmentAuditEntry ⊑ ∃hasTransition.DesignatorLifecycleState
CommitmentAuditEntry ⊑ ∃recordSeq.xsd:integer
CommitmentAuditEntry ⊑ ∃chainHash.xsd:string
```

### ViolationAuditEntry ✅

Defined: an audit entry that records a violated constraint.

```text
ViolationAuditEntry ⊑ CommitmentAuditEntry
ViolationAuditEntry ≡ CommitmentAuditEntry ⊓ ∃violatesConstraint.KernelConstraint
```

## Properties

| Property | Kind | Super-properties | Characteristics | Description |
|---|---|---|---|---|
| `hasPhysicalPart` | object | hasPart (inverse isPhysicalPartOf) | Transitive | Physical parthood (transitive closure of direct components). |
| `isPhysicalPartOf` | object | partOf | Transitive | Inverse of hasPhysicalPart. |
| `hasDirectComponent` | object | hasComponent, hasPhysicalPart (inverse isDirectComponentOf) | - | A designed artifact has a component directly (simple: may carry cardinalities, e.g. =96 wells). |
| `isDirectComponentOf` | object | componentOf, isPhysicalPartOf | - | Inverse of hasDirectComponent. |
| `hasSubPlace` | object | hasPart (inverse isSubPlaceOf) | Transitive | A place has a sub-place (rooms, zones). |
| `isSubPlaceOf` | object | partOf | Transitive | Inverse of hasSubPlace. |
| `locatedAt` | object | - (inverse hostsObject) | - | An object is located at a place (not parthood). |
| `hostsObject` | object | - | - | Inverse of locatedAt. |
| `containsMaterial` | object | - (inverse isContainedIn) | - | A container holds a portion of material (not parthood). |
| `isContainedIn` | object | - | - | Inverse of containsMaterial. |
| `hasInteractionPose` | object | - (inverse isPoseOf) | - | A physical object has a named pose (coordinate / interaction frame of the twin). |
| `isPoseOf` | object | - | - | Inverse of hasInteractionPose. |
| `affordsTaskType` | object | - | - | A pose / route is where a task of this type is performed. |
| `representsEntity` | object | - (inverse isRepresentedBy) | - | An SDT node represents the entity it is about. |
| `isRepresentedBy` | object | - | - | Inverse of representsEntity. |
| `hasChildNode` | object | - (inverse hasParentNode) | - | Scene-graph hierarchy of SDT nodes (USD namespace parent -> child). |
| `hasParentNode` | object | - | - | Inverse of hasChildNode. |
| `servesStation` | object | - (inverse isServedByRobot) | - | A robot is assigned to load and unload a station or fixture. |
| `isServedByRobot` | object | - | - | Inverse of servesStation. |
| `monitorsEntity` | object | - (inverse isMonitoredBy) | - | A sensor or safety device observes the state of an entity. |
| `isMonitoredBy` | object | - | - | Inverse of monitorsEntity. |
| `couplesTool` | object | - | - | A tool changer can couple an exchangeable tool. |
| `drivesJoint` | object | - (inverse isDrivenBy) | - | An actuator drives a mechanism joint. |
| `isDrivenBy` | object | - | - | Inverse of drivesJoint. |
| `hasParentBody` | object | - | - | A mechanism joint's parent body (USD physics:body0). |
| `hasChildBody` | object | - | - | A mechanism joint's child body (USD physics:body1). |
| `hasMechanismJointType` | object | - | - | The kind of a mechanism joint (AICOR JointType: Revolute, Prismatic, Fixed ...). |
| `hasRobotSkill` | object | - | - | A robot has a skill (a capability of the robot as a whole). |
| `hasEquipmentFunction` | object | - | - | A manual (non-automated) equipment item has a function (VRB DeviceFunction kinds). |
| `startsAt` | object | - | - | Origin dock of a route. |
| `endsAt` | object | - | - | Destination dock of a route. |
| `executesTaskType` | object | - | - | An action executes a task type (lab task concept). |
| `hasParticipantEntity` | object | - (inverse participatesIn) | - | An action involves a participant (robot, station, plate). |
| `participatesIn` | object | - | - | Inverse of hasParticipantEntity. |
| `usdPrimPath` | data | - | Functional | USD prim path of an SDT node. |
| `canonicalName` | data | - | - | Cell 01 canonical name. |
| `componentId` | data | - | - | Cell 01 component identifier. |
| `equipmentClassToken` | data | - | - | Site equipment class token (sdt:class). |
| `wellId` | data | - | Functional | Well designator, e.g. P17:B05. |
| `slotIndex` | data | - | Functional | Index of a plate slot. |
| `capabilityToken` | data | - | - | Cell 01 capability token. |
| `statementText` | data | - | - | Natural-language statement of a manual / rule item (verbatim from its source). |
| `sourceDocument` | data | - | - | Source document of a knowledge item (path). |
| `sourceLocator` | data | - | - | Locator inside the source (YAML key, section). |
| `verificationTest` | data | - | - | Twin test that exercises a rule / precondition. |
| `startTime_s` | data | - | - | Simulation start time (s). |
| `endTime_s` | data | - | - | Simulation end time (s). |
| `monitorName` | data | - | - | Cell 01 monitor template name. |
| `monitorPassed` | data | - | Functional | Whether a monitor passed. |
| `configures` | object | - | - | Settings configure a twin. |
| `adjoinsZone` | object | - | Symmetric | Two zones share a boundary. |
| `supportsObject` | object | - | - | A support carries an object against gravity. |
| `coversObject` | object | - | - | A cover encloses an object. |
| `hostsSoftware` | object | - | - | A computer hosts a software / information artifact. |
| `functionAffords` | object | - | - | A device function / robot skill affords a task type. |
| `declaresSetpoint` | object | - | - | A device / manual declares an operating setpoint. |
| `storesTool` | object | - | - | A magazine stores a tool. |
| `hasEndEffectorMount` | object | - | - | A robot body offers an end-effector mount. |
| `affordsRobotSkill` | object | - | - | A tool affords a robot skill when coupled. |
| `handledIn` | object | - | - | Labware is handled in tasks of a type. |
| `classifiesAction` | object | - (inverse executesTaskType) | - | A task type classifies actions. |
| `prescribesTaskType` | object | - | - | A workflow / protocol prescribes a task type as a step. |
| `manualFor` | object | - | - | A manual is about a device or robot (model / component). |
| `documentsProcedure` | object | - | - | A manual documents an operating procedure. |
| `requiresPrecondition` | object | - | - | A procedure requires a precondition. |
| `hasExpectedEffect` | object | - | - | A procedure has an expected effect. |
| `usesProcedureMonitor` | object | - | - | A procedure is monitored by a monitor. |
| `hasRecoveryProcedure` | object | - | - | A procedure / failure mode is recovered by a procedure. |
| `producesEvidenceOutput` | object | - | - | A procedure produces an evidence output. |
| `declaresFailureMode` | object | - | - | A manual declares a failure mode. |
| `declaresRiskControl` | object | - | - | A manual declares a risk control. |
| `declaresOperatingConstraint` | object | - | - | A manual declares an operating constraint. |
| `declaresMonitor` | object | - | - | A manual declares a device monitor. |
| `hasFailureConsequence` | object | - | - | A failure mode has a consequence (hazard / validity loss). |
| `hasProcessMicrotheory` | object | - | - | A device's process knowledge. |
| `enforcedInTwinBy` | object | - | - | A precondition / rule is enforced by a twin controller check. |
| `setpointValue` | data | - | - | Numeric value of a setpoint. |
| `quantityName` | data | - | - | Quantity a setpoint / variable refers to. |
| `manufacturerBaseline` | data | - | - | Manufacturer / model family a contract is based on. |
| `isRequiredBy` | object | - | - | Inverse of requiresPrecondition. |
| `isEffectOf` | object | - | - | Inverse of hasExpectedEffect. |
| `isEvidenceOf` | object | - | - | Inverse of producesEvidenceOutput. |
| `constrainsDevice` | object | - | - | A constraint applies to a device. |
| `microtheoryOf` | object | - | - | A microtheory describes a device's processes. |
| `exercisedByTest` | object | - | - | A twin check is exercised by a test. |
| `mitigatesHazard` | object | - | - | A device / rule / control mitigates a hazard. |
| `prohibitsTaskType` | object | - | - | A rule prohibits a task type (in its situation). |
| `appliesInSituation` | object | - | - | A rule applies in a situation type. |
| `enforcedBy` | object | - | - | A rule is enforced by a mechanism (interlock, controller check, critic). |
| `derivedFromSource` | object | - | - | A rule is derived from a source (manual, standard, Cell 01 rule file). |
| `violatesRule` | object | - | - | A candidate action / command violates a rule. |
| `refusedByEntity` | object | - | - | A command was refused by a device / interlock / critic. |
| `hazardTo` | object | - | - | Whom / what a hazard can harm. |
| `enforces` | object | - (inverse enforcedBy) | - | A mechanism enforces a rule. |
| `realizedByDevice` | object | - | - | A mechanism is realised by a device. |
| `testsCriterion` | object | - | - | A gate tests a commitment criterion. |
| `triggeredByDevice` | object | - | - | An event is triggered by a device. |
| `hasArm` | object | - | - | A study design has an arm. |
| `assignsUnit` | object | - | - | An arm assigns an experimental unit (well). |
| `appliesIntervention` | object | - | - | An arm applies an intervention specification. |
| `observedBySchedule` | object | - | - | A design observes units on a schedule. |
| `runOfStudy` | object | - | - | A run realises a study design. |
| `concernsWell` | object | - | - | A record / conclusion concerns a well. |
| `comparesArm` | object | - | - | A conclusion compares arms. |
| `withheldBecause` | object | - | - | A conclusion is withheld for a reason. |
| `hasScenarioCondition` | object | - | - | A run is conducted under a scenario condition (fault injection). |
| `realizesIntervention` | object | - | - | A record is about an intervention event. |
| `appliedToWell` | object | - | - | An intervention event is applied to a well. |
| `doseAU` | data | - | - | Dose in abstract units (Cell 01 D016: illustrative). |
| `time_h` | data | - | - | Culture time (h). |
| `interval_h` | data | - | - | Observation interval (h). |
| `horizon_h` | data | - | - | Observation horizon (h). |
| `viabilityMean` | data | - | - | Posterior mean viability. |
| `viabilityP05` | data | - | - | Posterior 5 % quantile. |
| `viabilityP95` | data | - | - | Posterior 95 % quantile. |
| `radius_um` | data | - | - | Measured organoid radius (µm). |
| `coreOpticalDensity` | data | - | - | Measured core optical density. |
| `debrisCount` | data | - | - | Counted debris. |
| `mediumHaze` | data | - | - | Measured haze. |
| `claimProbability` | data | - | - | Posterior probability of a conclusion. |
| `claimStatus` | data | - | - | Status (candidate / withheld ...). |
| `isCommittedEvent` | data | - | Functional | Whether the culture ledger committed the event. |
| `scenarioName` | data | - | - | Scenario of a run. |
| `specifiesTask` | object | - | - | A specification is realised by a task type. |
| `injectsHazard` | object | - | - | A fault injection realises a hazard. |
| `citesRule` | object | - | - | A reason cites a rule. |
| `flagsHazard` | object | - | - | A record flags a hazard. |
| `recordsAction` | object | - | - | A record is about an action. |
| `hasMonitorResult` | object | - | - | A record contains a monitor result. |
| `hasRouting` | object | - | Functional | The routing Cell 01's validator assigned to a record. |
| `routesTo` | object | - | - | Where a routing sends the record or object. |
| `includesAction` | object | - | - | An episode includes an action. |
| `classifiesRecord` | object | - | - | A routing classifies records. |
| `discriminatesModel` | object | - | - | A candidate experiment's outcome distribution differs between competing models. |
| `selectedUnder` | object | - | - | A candidate was selected under an information-gain requirement. |
| `realisesProposal` | object | - | - | A realisation plan realises a selected experiment proposal. |
| `hasSession` | object | - | - | A plan has a protocol session. |
| `hasStep` | object | - | - | A session / designator has an ordered step. |
| `refinesInto` | object | - | - | A designator is refined into a lower-level designator (inverse reading of RS refines). |
| `boundToDevice` | object | - | - | A designator is bound to a device that performs it. |
| `boundToPose` | object | - | - | A designator is bound to a pose of the twin. |
| `performedByRobot` | object | - | - | A motion designator is performed by a robot. |
| `commandsDevice` | object | - | - | A device-command designator commands a device. |
| `usesToolDesignator` | object | - | - | A motion uses an exchangeable tool. |
| `derivesPlan` | object | - | - | A derivation derives a realisation plan. |
| `appliesAxiomSet` | object | - | - | A derivation applies an L3 axiom set. |
| `conditionedOnBelief` | object | - | - | An information-gain estimate is conditioned on a culture SDT belief. |
| `estimatesGainOf` | object | - | - | An estimate is about a candidate experiment. |
| `executesPlan` | object | - | - | An executed episode executes a realisation plan. |
| `routeVia` | object | - | - | A plate transfer route passes a station or fixture. |
| `requiredGain_bits` | data | - | - | Required expected information gain (bits). |
| `expectedGain_bits` | data | - | Functional | Expected information gain I(M; y | a, D) (bits). |
| `realisedGain_bits` | data | - | - | Realised information gain KL(p(M|D,y) ‖ p(M|D)) (bits). |
| `rescueDelay_h` | data | - | - | Challenge-to-rescue delay (h). |
| `replicateCount` | data | - | - | Replicates per arm. |
| `planCost` | data | - | - | Cost of a realisation (robot operations + wells). |
| `scheduledAt_h` | data | - | - | Scheduled culture time of a session (h). |
| `stepIndex` | data | - | Functional | Position of a step in its sequence. |
| `estimatedDuration_s` | data | - | - | Duration estimate from twin run traces (s). |
| `primitiveName` | data | - | - | Name of a motion / command primitive. |
| `predictsReadout` | object | - | - | A model predicts a readout. |
| `dischargesRule` | object | - | - | A step discharges (satisfies) a rule's precondition. |
| `about` | object | - | - | An information object is about an entity (module-local, domain-free). |
| `designatesAction` | object | - | - | A designator designates an action of a type (CRAM: an action designator references an action event type). |
| `kernelCategory` | data | - | - | A kernel category (registry card id) of a designator (not functional: a specialised category's designators also carry the general one). |
| `constrainsDesignator` | object | - | - | A kernel constraint applies to designators of a category. |
| `recordsDesignator` | object | - | - | An audit entry is about one designator (one lifecycle transition of it). |
| `hasTransition` | object | - | - | An audit entry records a lifecycle transition. |
| `checksConstraint` | object | - | - | An audit entry carries a verdict on a registry constraint. |
| `violatesConstraint` | object | checksConstraint | - | An audit entry records a VIOLATED verdict on a constraint. |
| `chainedAfter` | object | - | Functional | An audit entry is hash-chained after its predecessor. |
| `carriesEvidence` | object | - | - | An audit entry carries a content-hashed evidence item. |
| `recordSeq` | data | - | Functional | Position of the entry in the trail. |
| `chainHash` | data | - | Functional | SHA-256 over the previous hash and the entry's canonical JSON. |
| `simTime_s` | data | - | Functional | Simulated time of the entry (s). |
| `evidenceSha256` | data | - | Functional | Content hash of an evidence item. |
