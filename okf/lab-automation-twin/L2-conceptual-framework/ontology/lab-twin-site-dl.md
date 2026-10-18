---
type: dl-definition
title: "Laboratory site, premises, rooms, zones, building elements and fit-out (DL definitions)"
derived_from: L1/lab-twin-site
maturity: L2
status: draft
timestamp: 2026-10-17
module: lab-automation-twin
---

# Laboratory site, premises, rooms, zones, building elements and fit-out

The laboratory site (robot-scientist LaboratorySite / LaboratoryCell), its premises, rooms and zones (layout S1), building elements, the Cell 01 fit-out and the site's safety and service equipment.

Every class is positioned under an upstream AICOR / robot-scientist / VRB / normative-admissibility concept or an AICOR upper-level stand-in (`dul:` / `soma:`). Generated from `src/tbox.py` by `build_module.py`; edit the source, not this file.

## Manchester syntax

```
ObjectProperty: adjoinsZone
    Characteristics: Symmetric
    -- Two zones share a boundary.

ObjectProperty: supportsObject
    -- A support carries an object against gravity.

ObjectProperty: coversObject
    -- A cover encloses an object.

ObjectProperty: hostsSoftware
    -- A computer hosts a software / information artifact.

Class: AutomatedBiologyLab
    SubClassOf: LaboratorySite
    SubClassOf:
        comprisesCell some RobotExperimentCell,
        locatedAt some LabPremises
    -- A laboratory site that comprises at least one robot experiment cell (AICOR Lab 1).

Class: LabPremises
    SubClassOf: dul:PhysicalPlace
    SubClassOf:
        hasSubPlace some LabRoom
    -- The floor area of a laboratory site.

Class: LabRoom
    SubClassOf: dul:PhysicalPlace
    SubClassOf:
        isSubPlaceOf some LabPremises
    -- A room of the premises.

Class: LabHall
    SubClassOf: LabRoom
    SubClassOf:
        hostsObject some LaboratoryCell
    -- The hall in which automation cells stand.

Class: StorageRoom
    SubClassOf: LabRoom
    SubClassOf:
        hostsObject some (ColdStorageDevice or StorageShelving)
    -- A room for consumables, reagents and cold storage (ST01).

Class: LabZone
    SubClassOf: dul:PhysicalPlace
    SubClassOf:
        isSubPlaceOf some (LabRoom or LabPremises)
    -- A functional area (layout S1).

Class: EntranceZone
    SubClassOf: LabZone
    SubClassOf:
        hostsObject some PPEStation
    DisjointWith: OperatorArea, CulturePrepArea, WashWasteArea, CellZone, ServiceCorridor, LogisticsArea
    -- Entrance and gowning.

Class: OperatorArea
    SubClassOf: LabZone
    SubClassOf:
        hostsObject some OperatorWorkstation
    DisjointWith: CulturePrepArea, WashWasteArea, CellZone, ServiceCorridor, LogisticsArea
    -- Monitoring and engineering desks.

Class: CulturePrepArea
    SubClassOf: LabZone
    SubClassOf:
        hostsObject some BiosafetyCabinet
    DisjointWith: WashWasteArea, CellZone, ServiceCorridor, LogisticsArea
    -- Manual culture work upstream.

Class: WashWasteArea
    SubClassOf: LabZone
    SubClassOf:
        hostsObject some (Autoclave or WasteStation)
    DisjointWith: CellZone, ServiceCorridor, LogisticsArea
    -- Sterilisation and waste.

Class: CellZone
    SubClassOf: LabZone
    SubClassOf:
        hostsObject some LaboratoryCell
    DisjointWith: ServiceCorridor, LogisticsArea
    -- Floor envelope of an automation cell.

Class: ServiceCorridor
    SubClassOf: LabZone
    SubClassOf:
        adjoinsZone some CellZone
    DisjointWith: LogisticsArea
    -- Technician access to the rear instruments.

Class: LogisticsArea
    SubClassOf: LabZone
    SubClassOf:
        adjoinsZone some CellZone
    -- The AMR lane and walkway to the cell portal.

Class: LabCeiling
    SubClassOf: dul:PhysicalPlace
    SubClassOf:
        hostsObject some BuildingServiceDevice
    -- Ceiling with services.

Class: LabBuildingShell
    SubClassOf: LabArtifact
    SubClassOf:
        hasDirectComponent some LabDoor
    -- Walls, doors, windows and services.

Class: LabDoor
    SubClassOf: LabArtifact
    SubClassOf:
        hasDirectComponent some DoorLeaf
    -- A door with a moving leaf.

Class: HingedDoor
    SubClassOf: LabDoor
    SubClassOf:
        hasDirectComponent some hasMechanismJointType some Revolute
    DisjointWith: SlidingDoor
    -- Leaf swings on a hinge.

Class: SlidingDoor
    SubClassOf: LabDoor
    SubClassOf:
        hasDirectComponent some hasMechanismJointType some Prismatic
    -- Leaf slides.

Class: InterlockedDoor
    SubClassOf: LabDoor
    SubClassOf:
        isMonitoredBy some DoorInterlockSwitch
    -- A door whose open state gates safe robot motion.

Class: DoorLeaf
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some LabDoor
    -- The moving panel of a door.

Class: DoorFrame
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some LabDoor
    -- The fixed frame of a door.

Class: AMRRoute
    SubClassOf: SpatialPose
    SubClassOf:
        affordsTaskType some NavigationTask,
        startsAt some Dock,
        endsAt some Dock
    -- A navigation route of an AMR between docks (a USD curve).

Class: RobotExperimentCell
    SubClassOf: LaboratoryCell
    SubClassOf:
        hasDirectComponent some CellRobot,
        hasDirectComponent some LabAutomationDevice,
        hasDirectComponent some SafetyEnclosure
    -- An automation cell of robots and automated stations behind a safety enclosure (Cell 01).

Class: AutomationCell
    SubClassOf: LaboratoryCell
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        LaboratoryCell,
        hasDirectComponent some Robot,
        hasDirectComponent some LabAutomationDevice
    -- Defined: a laboratory cell with robots and automated devices as direct components.

Class: SafetyEnclosure
    SubClassOf: LabArtifact
    SubClassOf:
        hasDirectComponent some LabDoor,
        hasDirectComponent some EmergencyStop
    -- Guard enclosure bounding the robot envelope: glazed sides, interlocked doors, e-stops (spec §4.1).

Class: AMRPortal
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some SafetyEnclosure,
        isMonitoredBy some LightCurtain
    -- Opening in the enclosure for the sample AMR, guarded by a muted light curtain.

Class: HMIPanel
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some LabArtifact
    -- Operator touch panel.

Class: Worktop
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some (AutomationBench or LabBench)
    -- The working surface of a bench.

Class: AutomationBench
    SubClassOf: LabArtifact
    SubClassOf:
        hasDirectComponent some Worktop,
        supportsObject some LabAutomationDevice
    -- Machine bench carrying stations at transfer height (spec §4.2).

Class: StationSupport
    SubClassOf: LabArtifact
    SubClassOf:
        supportsObject some LabArtifact
    -- Plinth or side table carrying a station at its transfer height.

Class: VibrationIsolatedSupport
    SubClassOf: StationSupport
    SubClassOf:
        supportsObject some ImagingDevice
    -- Support decoupled from the bench (imaging sub-base).

Class: RailCover
    SubClassOf: MechanismPart
    SubClassOf:
        coversObject some LinearRail
    -- Cover over a robot rail.

Class: StationHood
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some LabAutomationDevice
    -- Glazed hood over a station deck.

Class: FitOutAssembly
    SubClassOf: LabArtifact
    SubClassOf:
        hasDirectComponent some (StationSupport or AutomationBench or RailCover)
    -- The cell's furniture and covers as installed.

Class: SafetyDevice
    SubClassOf: LabArtifact
    SubClassOf:
        mitigatesHazard some LabHazard
    -- Equipment whose function is safety.

Class: EmergencyStop
    SubClassOf: SafetyDevice
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some LabArtifact
    -- Latching e-stop button.

Class: LightCurtain
    SubClassOf: SafetyDevice
    SubClassOf: DeviceSensor
    SubClassOf:
        monitorsEntity some AMRPortal
    -- Optical safety curtain across the portal; muting admits the AMR only.

Class: DoorInterlockSwitch
    SubClassOf: SafetyDevice
    SubClassOf: DeviceSensor
    SubClassOf:
        monitorsEntity some LabDoor
    -- Door switch that withholds safe motion while the door is open.

Class: FireSafetyDevice
    SubClassOf: SafetyDevice
    SubClassOf:
        mitigatesHazard some FireHazard
    -- Fire detection or suppression.

Class: SprinklerHead
    SubClassOf: FireSafetyDevice
    SubClassOf:
        locatedAt some LabCeiling
    DisjointWith: SmokeDetector, FireExtinguisher
    -- Pendent sprinkler head.

Class: SmokeDetector
    SubClassOf: FireSafetyDevice
    SubClassOf: DeviceSensor
    SubClassOf:
        locatedAt some LabCeiling
    DisjointWith: FireExtinguisher
    -- Ceiling smoke detector.

Class: FireExtinguisher
    SubClassOf: FireSafetyDevice
    SubClassOf:
        locatedAt some dul:PhysicalPlace
    -- Portable extinguisher.

Class: FirstAidBox
    SubClassOf: SafetyDevice
    SubClassOf:
        locatedAt some dul:PhysicalPlace
    -- First-aid cabinet.

Class: EmergencyShower
    SubClassOf: SafetyDevice
    SubClassOf:
        mitigatesHazard some ChemicalExposureHazard
    -- Drench shower.

Class: O2DepletionMonitor
    SubClassOf: SafetyDevice
    SubClassOf: DeviceSensor
    SubClassOf:
        mitigatesHazard some AsphyxiationHazard
    -- Oxygen-depletion monitor guarding cryogen / gas storage.

Class: AccessControlReader
    SubClassOf: SafetyDevice
    SubClassOf:
        monitorsEntity some LabDoor
    -- Card reader releasing a door.

Class: BuildingServiceDevice
    SubClassOf: LabArtifact
    SubClassOf:
        locatedAt some dul:PhysicalPlace
    -- Technical building equipment.

Class: HVACDiffuser
    SubClassOf: BuildingServiceDevice
    SubClassOf:
        locatedAt some LabCeiling
    -- Supply-air diffuser.

Class: CeilingLuminaire
    SubClassOf: BuildingServiceDevice
    SubClassOf:
        locatedAt some LabCeiling
    -- LED ceiling panel.

Class: ServerRack
    SubClassOf: BuildingServiceDevice
    SubClassOf:
        hostsSoftware some LabSemanticDigitalTwin
    -- Rack hosting the twin's compute.

Class: GloveDispenser
    SubClassOf: LabArtifact
    SubClassOf:
        locatedAt some LabZone
    -- Glove box holder.

Class: LabCoatRack
    SubClassOf: LabArtifact
    SubClassOf:
        locatedAt some EntranceZone
    -- Coat hooks.

Class: PPEStation
    SubClassOf: LabArtifact
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        GloveDispenser,
        LabCoatRack
    -- Defined: a PPE station.

Class: PottedPlant
    SubClassOf: dul:PhysicalObject
    SubClassOf:
        hasPhysicalPart some BiologicalSpecimen,
        not (LabArtifact)
    -- Decor (a plant is not a designed artifact).

Class: Whiteboard
    SubClassOf: LabArtifact
    SubClassOf:
        locatedAt some LabZone
    -- Wall whiteboard.

Class: LabBench
    SubClassOf: LabArtifact
    SubClassOf:
        hasDirectComponent some Worktop
    -- Laboratory bench.

Class: AMRDispatchBench
    SubClassOf: LabBench
    SubClassOf:
        locatedAt some StorageRoom
    -- Bench where staff stage AMR carriers (S1).

Class: StorageShelving
    SubClassOf: LabArtifact
    SubClassOf:
        locatedAt some dul:PhysicalPlace
    -- Shelving with addressable locations.

Class: PipetteCarousel
    SubClassOf: LabArtifact
    SubClassOf:
        locatedAt some LabZone
    -- Manual pipette stand.

Class: LabSinkUnit
    SubClassOf: LabArtifact
    SubClassOf:
        hasEquipmentFunction some WashingFunction
    -- Sink with tap and eyewash.

Class: WasteStation
    SubClassOf: LabArtifact
    SubClassOf:
        locatedAt some WashWasteArea
    -- Segregated waste and sharps bins.

Class: OperatorWorkstation
    SubClassOf: LabArtifact
    SubClassOf:
        locatedAt some OperatorArea
    -- Desk with monitors.

Class: LabStool
    SubClassOf: LabArtifact
    SubClassOf:
        locatedAt some LabZone
    -- Lab stool.

```

## Export notes

- Restrictions AICOR's exporter cannot read (negation, nested fillers, inverse roles): 3; they are kept in `build/lab-automation-twin.ofn`.
- Definitions (≡) are necessary conditions in the AICOR export (D-LAT-2).

