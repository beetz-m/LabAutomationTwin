---
type: dl-definition
title: "Laboratory devices, automated stations, mechanisms and device sensors (DL definitions)"
derived_from: L1/lab-twin-devices
maturity: L2
status: draft
timestamp: 2026-10-17
module: lab-automation-twin
---

# Laboratory devices, automated stations, mechanisms and device sensors

Automated stations as VRB LabAutomationDevices, the site's manual equipment, and the mechanisms and sensors of devices (not AICOR robot-body links or sensors: D-LAT-1).

Every class is positioned under an upstream AICOR / robot-scientist / VRB / normative-admissibility concept or an AICOR upper-level stand-in (`dul:` / `soma:`). Generated from `src/tbox.py` by `build_module.py`; edit the source, not this file.

## Manchester syntax

```
ObjectProperty: functionAffords
    -- A device function / robot skill affords a task type.

ObjectProperty: declaresSetpoint
    -- A device / manual declares an operating setpoint.

ObjectProperty: storesTool
    -- A magazine stores a tool.

Class: PlateStorageFunction
    SubClassOf: DeviceFunction
    SubClassOf:
        functionAffords some PlateStoringTask
    -- Store / buffer plates.

Class: QuarantineFunction
    SubClassOf: DeviceFunction
    SubClassOf:
        functionAffords some QuarantiningTask
    -- Contain suspect material.

Class: CalibrationFunction
    SubClassOf: DeviceFunction
    SubClassOf:
        functionAffords some CalibratingTask
    -- Validate a measurement chain.

Class: IdentificationFunction
    SubClassOf: DeviceFunction
    SubClassOf:
        functionAffords some IdentifyingTask
    -- Read labware identity.

Class: ColdStorageFunction
    SubClassOf: DeviceFunction
    SubClassOf:
        functionAffords some ColdStoringTask
    -- Keep material cold.

Class: SterilizationFunction
    SubClassOf: DeviceFunction
    SubClassOf:
        functionAffords some SterilizingTask
    -- Sterilise material.

Class: AsepticWorkFunction
    SubClassOf: DeviceFunction
    SubClassOf:
        functionAffords some AsepticHandlingTask
    -- Protect open cultures.

Class: TemperatureControlFunction
    SubClassOf: DeviceFunction
    SubClassOf:
        functionAffords some TemperatureControllingTask
    -- Hold a sample at temperature.

Class: PlateStorageDevice
    SubClassOf: LabAutomationDevice
    SubClassOf: LabArtifact
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        LabAutomationDevice,
        hasDirectComponent some PlateCassette
    DisjointWith: DispensingDevice, ImagingDevice, QCCalibrationStation, QuarantineStation
    -- Defined: an automated device that stores plates in a cassette.

Class: AutomatedPlateHotel
    SubClassOf: PlateStorageDevice
    SubClassOf:
        hasDeviceFunction some PlateStorageFunction,
        hasDirectComponent some PlateShuttle,
        hasDirectComponent some InternalPlateHandler,
        not (hasDirectComponent some IncubationChamber)
    DisjointWith: AutomatedCO2Incubator
    -- Ambient automated plate store (L09, LiCONiC LPE220 baseline).

Class: AutomatedCO2Incubator
    SubClassOf: IncubationDevice
    SubClassOf: PlateStorageDevice
    SubClassOf:
        hasDirectComponent some IncubationChamber,
        declaresSetpoint some OperatingSetpoint
    -- Robot-accessible CO2 incubator (L10, LiCONiC STX44-SA baseline).

Class: AutomatedLiquidHandler
    SubClassOf: DispensingDevice
    SubClassOf: LabArtifact
    SubClassOf:
        hasDirectComponent some GantryAxis,
        hasPhysicalPart some PipettingChannel
    -- Gantry liquid handler (L12, Hamilton ZEUS LT baseline).

Class: BrightFieldImager
    SubClassOf: ImagingDevice
    SubClassOf: LabArtifact
    SubClassOf:
        hasDirectComponent some MotorizedStage,
        hasDirectComponent some FocusDrive,
        hasPhysicalPart some ObjectiveTurret
    -- Bright-field imager (L17, OpenFlexure-derived).

Class: QCCalibrationStation
    SubClassOf: LabAutomationDevice
    SubClassOf: LabArtifact
    SubClassOf:
        hasDeviceFunction some CalibrationFunction,
        hasDirectComponent some LightBarrierSensor
    DisjointWith: QuarantineStation
    -- QC / calibration bench with reference artifacts (L21).

Class: QuarantineStation
    SubClassOf: LabAutomationDevice
    SubClassOf: LabArtifact
    SubClassOf:
        hasDeviceFunction some QuarantineFunction,
        hasDirectComponent some LockableDoor,
        hasDirectComponent some KeySwitch
    -- Lockable quarantine store (H4).

Class: Dock
    SubClassOf: LabArtifact
    SubClassOf:
        hasInteractionPose some DockPose
    -- A place an AMR docks at.

Class: DeterministicAMRDock
    SubClassOf: Dock
    SubClassOf:
        hasDirectComponent some DockSensor
    -- V-guide dock with pose sensors (H2).

Class: DispatchDock
    SubClassOf: Dock
    SubClassOf:
        locatedAt some StorageRoom
    -- Loading / charging dock in the storage room (S1).

Class: ToolMagazine
    SubClassOf: LabArtifact
    SubClassOf:
        hasDirectComponent some MagazineStand,
        storesTool some ExchangeableTool
    -- Automatic tool magazine (TCM01, Zimmer WMR2063 baseline).

Class: PassiveFixture
    SubClassOf: LabArtifact
    SubClassOf:
        not (hasDirectComponent some MechanismJoint)
    -- A fixture with no moving joints.

Class: HandoverNest
    SubClassOf: PassiveFixture
    SubClassOf:
        hasDirectComponent some SeatSensor,
        isServedByRobot min 2 Robot
    -- Passive nest where two robots hand a plate over (R01/R02).

Class: ManualLabEquipment
    SubClassOf: LabArtifact
    SubClassOf:
        not (LabAutomationDevice),
        hasEquipmentFunction some DeviceFunction
    -- Laboratory equipment operated by people, with no robot control interface.

Class: BiosafetyCabinet
    SubClassOf: ManualLabEquipment
    SubClassOf:
        hasEquipmentFunction some AsepticWorkFunction
    -- Class II BSC.

Class: ManualCO2Incubator
    SubClassOf: ManualLabEquipment
    SubClassOf:
        hasEquipmentFunction some IncubationFunction
    -- Benchtop.

Class: InvertedMicroscope
    SubClassOf: ManualLabEquipment
    SubClassOf:
        hasEquipmentFunction some ImagingFunction
    -- Manual scope.

Class: Centrifuge
    SubClassOf: ManualLabEquipment
    SubClassOf:
        hasEquipmentFunction some SeparationFunction
    -- Benchtop centrifuge.

Class: WaterBath
    SubClassOf: ManualLabEquipment
    SubClassOf:
        hasEquipmentFunction some TemperatureControlFunction
    -- Water bath.

Class: Autoclave
    SubClassOf: ManualLabEquipment
    SubClassOf:
        hasEquipmentFunction some SterilizationFunction
    -- Steam steriliser.

Class: ColdStorageDevice
    SubClassOf: ManualLabEquipment
    SubClassOf:
        hasEquipmentFunction some ColdStorageFunction
    -- Cold storage.

Class: LabRefrigerator
    SubClassOf: ColdStorageDevice
    SubClassOf:
        locatedAt some StorageRoom
    -- +4 °C refrigerator.

Class: LabFreezer
    SubClassOf: ColdStorageDevice
    SubClassOf:
        locatedAt some StorageRoom
    -- -20 °C freezer.

Class: ULTFreezer
    SubClassOf: ColdStorageDevice
    SubClassOf:
        locatedAt some StorageRoom
    -- -80 °C ultra-low freezer.

Class: CryogenicDewar
    SubClassOf: ColdStorageDevice
    SubClassOf:
        isMonitoredBy some O2DepletionMonitor
    -- LN2 dewar.

Class: GasCylinderCabinet
    SubClassOf: SafetyDevice
    SubClassOf:
        mitigatesHazard some AsphyxiationHazard
    -- Ventilated CO2 cabinet.

Class: MechanismPart
    SubClassOf: LabArtifact
    SubClassOf:
        isDirectComponentOf some LabArtifact
    -- A component of a lab device or fixture (not a robot-body link; D-LAT-1).

Class: MechanismJoint
    SubClassOf: MechanismPart
    SubClassOf:
        hasMechanismJointType exactly 1 JointType
    -- A kinematic joint of a device or tool mechanism (USD physics joint), typed by AICOR's JointType.

Class: DrivenMechanismJoint
    SubClassOf: MechanismJoint
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        MechanismJoint,
        isDrivenBy some Actuator
    -- Defined: a mechanism joint with an actuator (a USD joint with a drive).

Class: Actuator
    SubClassOf: MechanismPart
    SubClassOf:
        drivesJoint some MechanismJoint
    -- Motor or drive of a joint.

Class: StationHousing
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some LabAutomationDevice
    -- Body of a device.

Class: IncubationChamber
    SubClassOf: StationHousing
    SubClassOf:
        isDirectComponentOf some IncubationDevice
    -- Conditioned, insulated chamber.

Class: AccessGate
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some LabAutomationDevice
    -- Sliding load gate.

Class: ServiceDoor
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some LabAutomationDevice
    -- Hinged service door.

Class: LockableDoor
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some QuarantineStation,
        isMonitoredBy some DeviceSensor
    -- Door that a latch bolt locks (H4).

Class: LatchBolt
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some QuarantineStation
    -- Bolt that locks a door.

Class: OperatorControl
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some LabArtifact
    -- A physical control operated by a person.

Class: KeySwitch
    SubClassOf: OperatorControl
    SubClassOf:
        hasDirectComponent some KeyCylinder
    -- Key-operated selector (H4 release).

Class: KeyCylinder
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some KeySwitch
    -- Rotating cylinder of a key switch.

Class: PushButton
    SubClassOf: OperatorControl
    SubClassOf:
        hasDirectComponent some ButtonPlunger
    -- Momentary push button.

Class: ButtonPlunger
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some PushButton
    -- Moving plunger of a button.

Class: PlateShuttle
    SubClassOf: MechanismPart
    SubClassOf:
        hasDirectComponent some SeatSensor,
        hasInteractionPose some PlateSeatPose
    -- Sliding SBS nest that presents a plate outside the device.

Class: PlateCassette
    SubClassOf: MechanismPart
    SubClassOf:
        hasDirectComponent some PlateSlot
    -- Stack of plate slots.

Class: PlateSlot
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some PlateCassette,
        hasDirectComponent some SlotOccupancySensor,
        slotIndex some xsd:integer
    -- One plate position of a cassette.

Class: InternalPlateHandler
    SubClassOf: MechanismPart
    SubClassOf:
        hasDirectComponent some PlateFork
    -- Lift moving plates cassette <-> shuttle.

Class: PlateFork
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some InternalPlateHandler
    -- Fork tine lifting a plate.

Class: GantryAxis
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some (DispensingDevice or GantryAxis)
    -- Linear gantry axis.

Class: PipettingChannel
    SubClassOf: GantryAxis
    SubClassOf:
        hasInteractionPose some ToolCenterPose
    -- Z axis with a pipetting head.

Class: MotorizedStage
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some (ImagingDevice or MotorizedStage)
    -- XY stage axis (L17's stage is also the load drawer).

Class: FocusDrive
    SubClassOf: MechanismPart
    SubClassOf:
        hasDirectComponent some ObjectiveTurret
    -- Z focus drive.

Class: ObjectiveTurret
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some FocusDrive
    -- Objective changer.

Class: MagazineStand
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some ToolMagazine,
        hasDirectComponent some SlotOccupancySensor
    -- Stand carrying tool docks and their occupancy sensors.

Class: LinearRail
    SubClassOf: MechanismPart
    SubClassOf:
        hasDirectComponent some RailCarriage
    -- Linear axis carrying a robot (igus ZLW-1660).

Class: RailCarriage
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some LinearRail
    -- Moving rail carriage.

Class: DeviceSensor
    SubClassOf: MechanismPart
    SubClassOf:
        monitorsEntity some Entity
    -- A sensor of a device or fixture (not AICOR's robot-mounted Sensor; D-LAT-1).

Class: SeatSensor
    SubClassOf: DeviceSensor
    SubClassOf:
        monitorsEntity some PlateSeatPose
    -- Flush seat window (plate seated).

Class: SlotOccupancySensor
    SubClassOf: DeviceSensor
    SubClassOf:
        isDirectComponentOf some (PlateSlot or MagazineStand)
    -- Ray occupancy sensor.

Class: CarrierPresenceSensor
    SubClassOf: DeviceSensor
    SubClassOf:
        isDirectComponentOf some MobileRobotBase
    -- Carrier present in AMR cabinet.

Class: ThroughBeamSensor
    SubClassOf: DeviceSensor
    SubClassOf:
        isDirectComponentOf some LabAutomationDevice
    -- Emitter / receiver beam element.

Class: DockSensor
    SubClassOf: DeviceSensor
    SubClassOf:
        isDirectComponentOf some DeterministicAMRDock
    -- Ray measuring the docked AMR pose.

Class: BarcodeReader
    SubClassOf: DeviceSensor
    SubClassOf:
        monitorsEntity some Labware
    -- Reads plate barcodes.

Class: LightBarrierSensor
    SubClassOf: DeviceSensor
    SubClassOf:
        isDirectComponentOf some QCCalibrationStation
    -- Crossed barrier measuring a TCP.

Class: FiducialMarker
    SubClassOf: MechanismPart
    SubClassOf:
        affordsTaskType some CalibratingTask
    -- Marker used to register poses.

Class: AprilTagMarker
    SubClassOf: FiducialMarker
    SubClassOf:
        isDirectComponentOf some LabArtifact
    -- AprilTag 36h11.

Class: DatumPin
    SubClassOf: FiducialMarker
    SubClassOf:
        isDirectComponentOf some LabArtifact
    -- Conical registration pin.

```

## Export notes

- Restrictions AICOR's exporter cannot read (negation, nested fillers, inverse roles): 3; they are kept in `build/lab-automation-twin.ofn`.
- Definitions (≡) are necessary conditions in the AICOR export (D-LAT-2).

