"""lab-automation-twin OKF module (TBox): an automated biology lab and its semantic digital twin, in AICOR terms.

Upstream (frozen, referenced, never edited):
  AICOR L2 core            foundation/okf/aicor            Robot, RobotBody, SemanticDigitalTwin, SDTNode, SceneNode,
                                                           CandidateAction, CommitmentChecking, IncapabilityAssertion,
                                                           FailureSignature, Repair, ProcessMonitor, HelpRequest, ...
  robot-scientist vertical verticals/robot-scientist/okf   LaboratorySite, LaboratoryCell, ComponentSDT, CultureSDT,
                                                           UsdSceneGraph, IsaacSimScene, ActionContract, StudyDesign,
                                                           ExperimentalProtocol, ExperimentalEpisode, BiologicalIntervention,
                                                           CellViabilityReadout, ScientificHypothesis, ScientificConclusion,
                                                           ContaminationCompatibility, ...
  VRB lab-automation-device foundation/okf/vrb             LabAutomationDevice, IncubationDevice, ImagingDevice,
                                                           DispensingDevice, SeparationDevice, DeviceFunction, LabConstraint,
                                                           SafetyConstraint, SterilityConstraint, ...
  normative-admissibility  foundation/okf/normative-adm.   Norm
Names are bare (one AICOR namespace); dul:/soma: tokens are AICOR's upper-level stand-ins.

Commitments
  * SDT node ≠ referent: every USD prim is a LabSDTNode (an AICOR SceneNode, information) that representsEntity the
    thing it is about (artifact, place, pose, record, estimate, claim). AICOR's physical/abstract cut makes this
    mandatory; owl:sameAs relates referents (one bench, two SDT nodes), never nodes.
  * partonomy: hasDirectComponent (simple, ⊑ AICOR hasComponent, ⊑ hasPhysicalPart) and hasPhysicalPart
    (transitive, ⊑ AICOR hasPart); places: hasSubPlace (transitive, ⊑ hasPart). AICOR's mereology properties are
    bare (no characteristics) and frozen, so the module adds sub-properties rather than characteristics.
  * containment (containsMaterial), location (locatedAt), poses (hasInteractionPose) are not parthood.
  * station mechanisms and sensors are NOT AICOR Link / Joint / Sensor (those are robot-body concepts: partOf some
    RobotBody) - DIVERGENCE D-LAT-1, see DEFERRED-REGISTER.md.
"""

from dl import All, And, DSome, DValue, Exact, Inv, Min, Not, Or, Some

CLASSES, PROPS, DISJOINT, INDIVIDUALS = [], [], [], []
_mod = [""]
DC, PP, SP = "hasDirectComponent", "hasPhysicalPart", "hasSubPlace"
IDC, IPP, ISP = "isDirectComponentOf", "isPhysicalPartOf", "isSubPlaceOf"
LOC, POSE, CAP, FN = "locatedAt", "hasInteractionPose", "hasRobotSkill", "hasDeviceFunction"
AFF, REP = "affordsTaskType", "representsEntity"


def module(key, title):
    _mod[0] = (key, title)


def C(name, sup, *axioms, eq=None, doc="", src="🔧"):
    """A concept. `src`: modality of its basis - ✅ stated in a cited source (Cell 01 package, twin verified by a
    test), 🔧 engineering inference, ❓ open."""
    CLASSES.append(dict(name=name, sup=[sup] if isinstance(sup, str) else list(sup), ax=list(axioms), eq=eq,
                        doc=doc, module=_mod[0], src=src))


def P(name, kind="object", sup=(), inv=None, domain=None, range_=None, chars=(), doc=""):
    PROPS.append(dict(name=name, kind=kind, sup=list(sup), inv=inv, domain=domain, range=range_, chars=list(chars),
                      doc=doc, module=_mod[0]))


def D(*names):
    DISJOINT.append(dict(names=list(names), module=_mod[0]))


def I(name, cls, doc=""):
    INDIVIDUALS.append(dict(name=name, cls=cls, doc=doc, module=_mod[0]))


# =====================================================================================================================
module("lab-twin-core", "Properties, upper-level placements and the SDT node / referent split")
# =====================================================================================================================
P(PP, sup=["hasPart"], inv=IPP, chars=["Transitive"],
  doc="Physical parthood (transitive closure of direct components).")
P(IPP, sup=["partOf"], chars=["Transitive"], doc="Inverse of hasPhysicalPart.")
P(DC, sup=["hasComponent", PP], inv=IDC, doc="A designed artifact has a component directly (simple: may carry "
                                              "cardinalities, e.g. =96 wells).")
P(IDC, sup=["componentOf", IPP], doc="Inverse of hasDirectComponent.")
P(SP, sup=["hasPart"], inv=ISP, chars=["Transitive"], doc="A place has a sub-place (rooms, zones).")
P(ISP, sup=["partOf"], chars=["Transitive"], doc="Inverse of hasSubPlace.")
P(LOC, inv="hostsObject", doc="An object is located at a place (not parthood).")
P("hostsObject", doc="Inverse of locatedAt.")
P("containsMaterial", inv="isContainedIn", doc="A container holds a portion of material (not parthood).")
P("isContainedIn", doc="Inverse of containsMaterial.")
P(POSE, inv="isPoseOf", doc="A physical object has a named pose (coordinate / interaction frame of the twin).")
P("isPoseOf", doc="Inverse of hasInteractionPose.")
P(AFF, doc="A pose / route is where a task of this type is performed.")
P(REP, inv="isRepresentedBy", doc="An SDT node represents the entity it is about.")
P("isRepresentedBy", doc="Inverse of representsEntity.")
P("hasChildNode", inv="hasParentNode", doc="Scene-graph hierarchy of SDT nodes (USD namespace parent -> child).")
P("hasParentNode", doc="Inverse of hasChildNode.")
P("servesStation", inv="isServedByRobot", doc="A robot is assigned to load and unload a station or fixture.")
P("isServedByRobot", doc="Inverse of servesStation.")
P("monitorsEntity", inv="isMonitoredBy", doc="A sensor or safety device observes the state of an entity.")
P("isMonitoredBy", doc="Inverse of monitorsEntity.")
P("couplesTool", doc="A tool changer can couple an exchangeable tool.")
P("drivesJoint", inv="isDrivenBy", doc="An actuator drives a mechanism joint.")
P("isDrivenBy", doc="Inverse of drivesJoint.")
P("hasParentBody", doc="A mechanism joint's parent body (USD physics:body0).")
P("hasChildBody", doc="A mechanism joint's child body (USD physics:body1).")
P("hasMechanismJointType", doc="The kind of a mechanism joint (AICOR JointType: Revolute, Prismatic, Fixed ...).")
P(CAP, doc="A robot has a skill (a capability of the robot as a whole).")
P("hasEquipmentFunction", doc="A manual (non-automated) equipment item has a function (VRB DeviceFunction kinds).")
P("startsAt", doc="Origin dock of a route.")
P("endsAt", doc="Destination dock of a route.")
P("executesTaskType", doc="An action executes a task type (lab task concept).")
P("hasParticipantEntity", inv="participatesIn", doc="An action involves a participant (robot, station, plate).")
P("participatesIn", doc="Inverse of hasParticipantEntity.")
for n, rng, doc in (("usdPrimPath", "xsd:string", "USD prim path of an SDT node."),
                    ("canonicalName", "xsd:string", "Cell 01 canonical name."),
                    ("componentId", "xsd:string", "Cell 01 component identifier."),
                    ("equipmentClassToken", "xsd:string", "Site equipment class token (sdt:class)."),
                    ("wellId", "xsd:string", "Well designator, e.g. P17:B05."),
                    ("slotIndex", "xsd:integer", "Index of a plate slot."),
                    ("capabilityToken", "xsd:string", "Cell 01 capability token."),
                    ("statementText", "xsd:string", "Natural-language statement of a manual / rule item (verbatim "
                                                    "from its source)."),
                    ("sourceDocument", "xsd:string", "Source document of a knowledge item (path)."),
                    ("sourceLocator", "xsd:string", "Locator inside the source (YAML key, section)."),
                    ("verificationTest", "xsd:string", "Twin test that exercises a rule / precondition."),
                    ("startTime_s", "xsd:double", "Simulation start time (s)."),
                    ("endTime_s", "xsd:double", "Simulation end time (s)."),
                    ("monitorName", "xsd:string", "Cell 01 monitor template name."),
                    ("monitorPassed", "xsd:boolean", "Whether a monitor passed.")):
    P(n, kind="data", range_=rng, chars=["Functional"] if n in ("usdPrimPath", "wellId", "slotIndex",
                                                                "monitorPassed") else [], doc=doc)

# upper-level stand-ins this module relies on, placed on AICOR's cut (DUL reading)
C("dul:PhysicalPlace", "dul:PhysicalObject", Some(SP, "dul:PhysicalPlace"),
  doc="(stand-in) a place with a physical extent; its sub-places are places (DUL: PhysicalPlace ⊑ PhysicalObject).")
C("LabArtifact", "dul:PhysicalObject", Some("isRepresentedBy", "LabSDTNode"),
  doc="A designed physical object of the lab that the twin represents.", src="✅")
C("LabSDTNode", "SceneNode", Some(REP, "Entity"), DSome("usdPrimPath", "xsd:string"),
  doc="A node of the lab's semantic digital twin (one USD prim): information that represents one entity.", src="✅")
C("GroupingNode", "LabSDTNode", Some("hasChildNode", "LabSDTNode"),
  doc="A structural SDT node (USD scope / xform) that groups child nodes; it represents the grouping only.")
C("LabSemanticDigitalTwin", "SemanticDigitalTwin", Some("hasNodeStructure", "LabSceneHierarchy"),
  doc="The semantic digital twin of a laboratory site: the belief state about it, structured as a USD scene graph.",
  src="✅")
C("LabSceneHierarchy", "HierarchicalSceneStructure", Some("hasNode", "LabSDTNode"),
  doc="The USD namespace hierarchy of the lab twin (lab_twin.usda + culture layer).", src="✅")
P("configures", doc="Settings configure a twin.")
C("SimulationSettings", "dul:Description", Some("configures", "LabSemanticDigitalTwin"),
  doc="Physics or rendering settings of the twin (physics scene, sky and sun lights).", src="✅")
C("SimulationSettingsNode", "LabSDTNode", Some(REP, "SimulationSettings"), doc="An SDT node holding settings.",
  src="✅")
C("RenderRepresentationNode", "SceneNode", Not("LabSDTNode"),
  doc="A render-only USD prim (looks, materials, collision / visual geometry): representation, not SDT knowledge.")

# =====================================================================================================================
module("lab-twin-site", "Laboratory site, premises, rooms, zones, building elements and fit-out")
# =====================================================================================================================
C("AutomatedBiologyLab", "LaboratorySite", Some("comprisesCell", "RobotExperimentCell"), Some(LOC, "LabPremises"),
  doc="A laboratory site that comprises at least one robot experiment cell (AICOR Lab 1).", src="✅")
C("LabPremises", "dul:PhysicalPlace", Some(SP, "LabRoom"), doc="The floor area of a laboratory site.")
C("LabRoom", "dul:PhysicalPlace", Some(ISP, "LabPremises"), doc="A room of the premises.")
C("LabHall", "LabRoom", Some("hostsObject", "LaboratoryCell"), doc="The hall in which automation cells stand.")
C("StorageRoom", "LabRoom", Some("hostsObject", Or("ColdStorageDevice", "StorageShelving")),
  doc="A room for consumables, reagents and cold storage (ST01).")
C("LabZone", "dul:PhysicalPlace", Some(ISP, Or("LabRoom", "LabPremises")), doc="A functional area (layout S1).")
C("EntranceZone", "LabZone", Some("hostsObject", "PPEStation"), doc="Entrance and gowning.")
C("OperatorArea", "LabZone", Some("hostsObject", "OperatorWorkstation"), doc="Monitoring and engineering desks.")
C("CulturePrepArea", "LabZone", Some("hostsObject", "BiosafetyCabinet"), doc="Manual culture work upstream.")
C("WashWasteArea", "LabZone", Some("hostsObject", Or("Autoclave", "WasteStation")), doc="Sterilisation and waste.")
C("CellZone", "LabZone", Some("hostsObject", "LaboratoryCell"), doc="Floor envelope of an automation cell.")
C("ServiceCorridor", "LabZone", Some("adjoinsZone", "CellZone"), doc="Technician access to the rear instruments.")
C("LogisticsArea", "LabZone", Some("adjoinsZone", "CellZone"), doc="The AMR lane and walkway to the cell portal.")
C("LabCeiling", "dul:PhysicalPlace", Some("hostsObject", "BuildingServiceDevice"), doc="Ceiling with services.")
P("adjoinsZone", chars=["Symmetric"], doc="Two zones share a boundary.")
D("EntranceZone", "OperatorArea", "CulturePrepArea", "WashWasteArea", "CellZone", "ServiceCorridor", "LogisticsArea")
C("LabBuildingShell", "LabArtifact", Some(DC, "LabDoor"), doc="Walls, doors, windows and services.")
C("LabDoor", "LabArtifact", Some(DC, "DoorLeaf"), doc="A door with a moving leaf.")
C("HingedDoor", "LabDoor", Some(DC, Some("hasMechanismJointType", "Revolute")), doc="Leaf swings on a hinge.")
C("SlidingDoor", "LabDoor", Some(DC, Some("hasMechanismJointType", "Prismatic")), doc="Leaf slides.")
C("InterlockedDoor", "LabDoor", Some("isMonitoredBy", "DoorInterlockSwitch"),
  doc="A door whose open state gates safe robot motion.", src="✅")
C("DoorLeaf", "MechanismPart", Some(IDC, "LabDoor"), doc="The moving panel of a door.")
C("DoorFrame", "MechanismPart", Some(IDC, "LabDoor"), doc="The fixed frame of a door.")
C("AMRRoute", "SpatialPose", Some(AFF, "NavigationTask"), Some("startsAt", "Dock"), Some("endsAt", "Dock"),
  doc="A navigation route of an AMR between docks (a USD curve).", src="✅")
D("HingedDoor", "SlidingDoor")
# cell fit-out
C("RobotExperimentCell", "LaboratoryCell", Some(DC, "CellRobot"), Some(DC, "LabAutomationDevice"),
  Some(DC, "SafetyEnclosure"), doc="An automation cell of robots and automated stations behind a safety enclosure "
                                   "(Cell 01).", src="✅")
C("AutomationCell", "LaboratoryCell", eq=And("LaboratoryCell", Some(DC, "Robot"), Some(DC, "LabAutomationDevice")),
  doc="Defined: a laboratory cell with robots and automated devices as direct components.")
C("SafetyEnclosure", "LabArtifact", Some(DC, "LabDoor"), Some(DC, "EmergencyStop"),
  doc="Guard enclosure bounding the robot envelope: glazed sides, interlocked doors, e-stops (spec §4.1).", src="✅")
C("AMRPortal", "MechanismPart", Some(IDC, "SafetyEnclosure"), Some("isMonitoredBy", "LightCurtain"),
  doc="Opening in the enclosure for the sample AMR, guarded by a muted light curtain.", src="✅")
C("HMIPanel", "MechanismPart", Some(IDC, "LabArtifact"), doc="Operator touch panel.")
C("Worktop", "MechanismPart", Some(IDC, Or("AutomationBench", "LabBench")), doc="The working surface of a bench.")
C("AutomationBench", "LabArtifact", Some(DC, "Worktop"), Some("supportsObject", "LabAutomationDevice"),
  doc="Machine bench carrying stations at transfer height (spec §4.2).", src="✅")
P("supportsObject", doc="A support carries an object against gravity.")
C("StationSupport", "LabArtifact", Some("supportsObject", "LabArtifact"),
  doc="Plinth or side table carrying a station at its transfer height.")
C("VibrationIsolatedSupport", "StationSupport", Some("supportsObject", "ImagingDevice"),
  doc="Support decoupled from the bench (imaging sub-base).", src="✅")
C("RailCover", "MechanismPart", Some("coversObject", "LinearRail"), doc="Cover over a robot rail.")
P("coversObject", doc="A cover encloses an object.")
C("StationHood", "MechanismPart", Some(IDC, "LabAutomationDevice"), doc="Glazed hood over a station deck.")
C("FitOutAssembly", "LabArtifact", Some(DC, Or("StationSupport", "AutomationBench", "RailCover")),
  doc="The cell's furniture and covers as installed.")
# site safety, services, furniture
C("SafetyDevice", "LabArtifact", Some("mitigatesHazard", "LabHazard"), doc="Equipment whose function is safety.")
C("EmergencyStop", ["SafetyDevice", "MechanismPart"], Some(IDC, "LabArtifact"), doc="Latching e-stop button.", src="✅")
C("LightCurtain", ["SafetyDevice", "DeviceSensor"], Some("monitorsEntity", "AMRPortal"),
  doc="Optical safety curtain across the portal; muting admits the AMR only.", src="✅")
C("DoorInterlockSwitch", ["SafetyDevice", "DeviceSensor"], Some("monitorsEntity", "LabDoor"),
  doc="Door switch that withholds safe motion while the door is open.", src="✅")
C("FireSafetyDevice", "SafetyDevice", Some("mitigatesHazard", "FireHazard"), doc="Fire detection or suppression.")
C("SprinklerHead", "FireSafetyDevice", Some(LOC, "LabCeiling"), doc="Pendent sprinkler head.")
C("SmokeDetector", ["FireSafetyDevice", "DeviceSensor"], Some(LOC, "LabCeiling"), doc="Ceiling smoke detector.")
C("FireExtinguisher", "FireSafetyDevice", Some(LOC, "dul:PhysicalPlace"), doc="Portable extinguisher.")
C("FirstAidBox", "SafetyDevice", Some(LOC, "dul:PhysicalPlace"), doc="First-aid cabinet.")
C("EmergencyShower", "SafetyDevice", Some("mitigatesHazard", "ChemicalExposureHazard"), doc="Drench shower.")
C("O2DepletionMonitor", ["SafetyDevice", "DeviceSensor"], Some("mitigatesHazard", "AsphyxiationHazard"),
  doc="Oxygen-depletion monitor guarding cryogen / gas storage.")
C("AccessControlReader", "SafetyDevice", Some("monitorsEntity", "LabDoor"), doc="Card reader releasing a door.")
C("BuildingServiceDevice", "LabArtifact", Some(LOC, "dul:PhysicalPlace"), doc="Technical building equipment.")
C("HVACDiffuser", "BuildingServiceDevice", Some(LOC, "LabCeiling"), doc="Supply-air diffuser.")
C("CeilingLuminaire", "BuildingServiceDevice", Some(LOC, "LabCeiling"), doc="LED ceiling panel.")
C("ServerRack", "BuildingServiceDevice", Some("hostsSoftware", "LabSemanticDigitalTwin"),
  doc="Rack hosting the twin's compute.")
P("hostsSoftware", doc="A computer hosts a software / information artifact.")
C("GloveDispenser", "LabArtifact", Some(LOC, "LabZone"), doc="Glove box holder.")
C("LabCoatRack", "LabArtifact", Some(LOC, "EntranceZone"), doc="Coat hooks.")
C("PPEStation", "LabArtifact", eq=Or("GloveDispenser", "LabCoatRack"), doc="Defined: a PPE station.")
C("PottedPlant", "dul:PhysicalObject", Some(PP, "BiologicalSpecimen"), Not("LabArtifact"),
  doc="Decor (a plant is not a designed artifact).")
C("Whiteboard", "LabArtifact", Some(LOC, "LabZone"), doc="Wall whiteboard.")
C("LabBench", "LabArtifact", Some(DC, "Worktop"), doc="Laboratory bench.")
C("AMRDispatchBench", "LabBench", Some(LOC, "StorageRoom"), doc="Bench where staff stage AMR carriers (S1).")
C("StorageShelving", "LabArtifact", Some(LOC, "dul:PhysicalPlace"), doc="Shelving with addressable locations.")
C("PipetteCarousel", "LabArtifact", Some(LOC, "LabZone"), doc="Manual pipette stand.")
C("LabSinkUnit", "LabArtifact", Some("hasEquipmentFunction", "WashingFunction"), doc="Sink with tap and eyewash.")
C("WasteStation", "LabArtifact", Some(LOC, "WashWasteArea"), doc="Segregated waste and sharps bins.")
C("OperatorWorkstation", "LabArtifact", Some(LOC, "OperatorArea"), doc="Desk with monitors.")
C("LabStool", "LabArtifact", Some(LOC, "LabZone"), doc="Lab stool.")
D("SprinklerHead", "SmokeDetector", "FireExtinguisher")

# =====================================================================================================================
module("lab-twin-devices", "Laboratory devices, automated stations, mechanisms and device sensors")
# =====================================================================================================================
C("PlateStorageFunction", "DeviceFunction", Some("functionAffords", "PlateStoringTask"), doc="Store / buffer plates.",
  src="✅")
P("functionAffords", doc="A device function / robot skill affords a task type.")
C("QuarantineFunction", "DeviceFunction", Some("functionAffords", "QuarantiningTask"), doc="Contain suspect material.",
  src="✅")
C("CalibrationFunction", "DeviceFunction", Some("functionAffords", "CalibratingTask"), doc="Validate a measurement "
                                                                                         "chain.", src="✅")
C("IdentificationFunction", "DeviceFunction", Some("functionAffords", "IdentifyingTask"), doc="Read labware identity.",
  src="✅")
C("ColdStorageFunction", "DeviceFunction", Some("functionAffords", "ColdStoringTask"), doc="Keep material cold.")
C("SterilizationFunction", "DeviceFunction", Some("functionAffords", "SterilizingTask"), doc="Sterilise material.")
C("AsepticWorkFunction", "DeviceFunction", Some("functionAffords", "AsepticHandlingTask"), doc="Protect open cultures.")
C("TemperatureControlFunction", "DeviceFunction", Some("functionAffords", "TemperatureControllingTask"),
  doc="Hold a sample at temperature.")
# automated stations of Cell 01
C("PlateStorageDevice", ["LabAutomationDevice", "LabArtifact"], eq=And("LabAutomationDevice", Some(DC, "PlateCassette")),
  doc="Defined: an automated device that stores plates in a cassette.")
C("AutomatedPlateHotel", "PlateStorageDevice", Some(FN, "PlateStorageFunction"), Some(DC, "PlateShuttle"),
  Some(DC, "InternalPlateHandler"), Not(Some(DC, "IncubationChamber")),
  doc="Ambient automated plate store (L09, LiCONiC LPE220 baseline).", src="✅")
C("AutomatedCO2Incubator", ["IncubationDevice", "PlateStorageDevice"], Some(DC, "IncubationChamber"),
  Some("declaresSetpoint", "OperatingSetpoint"),
  doc="Robot-accessible CO2 incubator (L10, LiCONiC STX44-SA baseline).", src="✅")
P("declaresSetpoint", doc="A device / manual declares an operating setpoint.")
C("AutomatedLiquidHandler", ["DispensingDevice", "LabArtifact"], Some(DC, "GantryAxis"), Some(PP, "PipettingChannel"),
  doc="Gantry liquid handler (L12, Hamilton ZEUS LT baseline).", src="✅")
C("BrightFieldImager", ["ImagingDevice", "LabArtifact"], Some(DC, "MotorizedStage"), Some(DC, "FocusDrive"), Some(PP, "ObjectiveTurret"),
  doc="Bright-field imager (L17, OpenFlexure-derived).", src="✅")
C("QCCalibrationStation", ["LabAutomationDevice", "LabArtifact"], Some(FN, "CalibrationFunction"), Some(DC, "LightBarrierSensor"),
  doc="QC / calibration bench with reference artifacts (L21).", src="✅")
C("QuarantineStation", ["LabAutomationDevice", "LabArtifact"], Some(FN, "QuarantineFunction"), Some(DC, "LockableDoor"),
  Some(DC, "KeySwitch"), doc="Lockable quarantine store (H4).", src="✅")
C("Dock", "LabArtifact", Some(POSE, "DockPose"), doc="A place an AMR docks at.")
C("DeterministicAMRDock", "Dock", Some(DC, "DockSensor"), doc="V-guide dock with pose sensors (H2).", src="✅")
C("DispatchDock", "Dock", Some(LOC, "StorageRoom"), doc="Loading / charging dock in the storage room (S1).", src="✅")
C("ToolMagazine", "LabArtifact", Some(DC, "MagazineStand"), Some("storesTool", "ExchangeableTool"),
  doc="Automatic tool magazine (TCM01, Zimmer WMR2063 baseline).", src="✅")
P("storesTool", doc="A magazine stores a tool.")
C("PassiveFixture", "LabArtifact", Not(Some(DC, "MechanismJoint")), doc="A fixture with no moving joints.")
C("HandoverNest", "PassiveFixture", Some(DC, "SeatSensor"), Min(2, "isServedByRobot", "Robot"),
  doc="Passive nest where two robots hand a plate over (R01/R02).", src="✅")
D("AutomatedPlateHotel", "AutomatedCO2Incubator")
D("PlateStorageDevice", "DispensingDevice", "ImagingDevice", "QCCalibrationStation", "QuarantineStation")
# manual equipment of the site (not lab-automation devices)
C("ManualLabEquipment", "LabArtifact", Not("LabAutomationDevice"), Some("hasEquipmentFunction", "DeviceFunction"),
  doc="Laboratory equipment operated by people, with no robot control interface.")
C("BiosafetyCabinet", "ManualLabEquipment", Some("hasEquipmentFunction", "AsepticWorkFunction"), doc="Class II BSC.")
C("ManualCO2Incubator", "ManualLabEquipment", Some("hasEquipmentFunction", "IncubationFunction"), doc="Benchtop.")
C("InvertedMicroscope", "ManualLabEquipment", Some("hasEquipmentFunction", "ImagingFunction"), doc="Manual scope.")
C("Centrifuge", "ManualLabEquipment", Some("hasEquipmentFunction", "SeparationFunction"), doc="Benchtop centrifuge.")
C("WaterBath", "ManualLabEquipment", Some("hasEquipmentFunction", "TemperatureControlFunction"), doc="Water bath.")
C("Autoclave", "ManualLabEquipment", Some("hasEquipmentFunction", "SterilizationFunction"), doc="Steam steriliser.")
C("ColdStorageDevice", "ManualLabEquipment", Some("hasEquipmentFunction", "ColdStorageFunction"), doc="Cold storage.")
C("LabRefrigerator", "ColdStorageDevice", Some(LOC, "StorageRoom"), doc="+4 °C refrigerator.")
C("LabFreezer", "ColdStorageDevice", Some(LOC, "StorageRoom"), doc="-20 °C freezer.")
C("ULTFreezer", "ColdStorageDevice", Some(LOC, "StorageRoom"), doc="-80 °C ultra-low freezer.")
C("CryogenicDewar", "ColdStorageDevice", Some("isMonitoredBy", "O2DepletionMonitor"), doc="LN2 dewar.")
C("GasCylinderCabinet", "SafetyDevice", Some("mitigatesHazard", "AsphyxiationHazard"), doc="Ventilated CO2 cabinet.")
# mechanisms (D-LAT-1: not AICOR Link / Joint)
C("MechanismPart", "LabArtifact", Some(IDC, "LabArtifact"),
  doc="A component of a lab device or fixture (not a robot-body link; D-LAT-1).")
C("MechanismJoint", "MechanismPart", Exact(1, "hasMechanismJointType", "JointType"),
  doc="A kinematic joint of a device or tool mechanism (USD physics joint), typed by AICOR's JointType.", src="✅")
C("DrivenMechanismJoint", "MechanismJoint", eq=And("MechanismJoint", Some("isDrivenBy", "Actuator")),
  doc="Defined: a mechanism joint with an actuator (a USD joint with a drive).")
C("Actuator", "MechanismPart", Some("drivesJoint", "MechanismJoint"), doc="Motor or drive of a joint.")
C("StationHousing", "MechanismPart", Some(IDC, "LabAutomationDevice"), doc="Body of a device.")
C("IncubationChamber", "StationHousing", Some(IDC, "IncubationDevice"), doc="Conditioned, insulated chamber.", src="✅")
C("AccessGate", "MechanismPart", Some(IDC, "LabAutomationDevice"), doc="Sliding load gate.", src="✅")
C("ServiceDoor", "MechanismPart", Some(IDC, "LabAutomationDevice"), doc="Hinged service door.", src="✅")
C("LockableDoor", "MechanismPart", Some(IDC, "QuarantineStation"), Some("isMonitoredBy", "DeviceSensor"),
  doc="Door that a latch bolt locks (H4).", src="✅")
C("LatchBolt", "MechanismPart", Some(IDC, "QuarantineStation"), doc="Bolt that locks a door.", src="✅")
C("OperatorControl", "MechanismPart", Some(IDC, "LabArtifact"), doc="A physical control operated by a person.")
C("KeySwitch", "OperatorControl", Some(DC, "KeyCylinder"), doc="Key-operated selector (H4 release).", src="✅")
C("KeyCylinder", "MechanismPart", Some(IDC, "KeySwitch"), doc="Rotating cylinder of a key switch.")
C("PushButton", "OperatorControl", Some(DC, "ButtonPlunger"), doc="Momentary push button.")
C("ButtonPlunger", "MechanismPart", Some(IDC, "PushButton"), doc="Moving plunger of a button.")
C("PlateShuttle", "MechanismPart", Some(DC, "SeatSensor"), Some(POSE, "PlateSeatPose"),
  doc="Sliding SBS nest that presents a plate outside the device.", src="✅")
C("PlateCassette", "MechanismPart", Some(DC, "PlateSlot"), doc="Stack of plate slots.", src="✅")
C("PlateSlot", "MechanismPart", Some(IDC, "PlateCassette"), Some(DC, "SlotOccupancySensor"), DSome("slotIndex",
                                                                                                    "xsd:integer"),
  doc="One plate position of a cassette.", src="✅")
C("InternalPlateHandler", "MechanismPart", Some(DC, "PlateFork"), doc="Lift moving plates cassette <-> shuttle.")
C("PlateFork", "MechanismPart", Some(IDC, "InternalPlateHandler"), doc="Fork tine lifting a plate.")
C("GantryAxis", "MechanismPart", Some(IDC, Or("DispensingDevice", "GantryAxis")), doc="Linear gantry axis.", src="✅")
C("PipettingChannel", "GantryAxis", Some(POSE, "ToolCenterPose"), doc="Z axis with a pipetting head.", src="✅")
C("MotorizedStage", "MechanismPart", Some(IDC, Or("ImagingDevice", "MotorizedStage")),
  doc="XY stage axis (L17's stage is also the load drawer).", src="✅")
C("FocusDrive", "MechanismPart", Some(DC, "ObjectiveTurret"), doc="Z focus drive.", src="✅")
C("ObjectiveTurret", "MechanismPart", Some(IDC, "FocusDrive"), doc="Objective changer.", src="✅")
C("MagazineStand", "MechanismPart", Some(IDC, "ToolMagazine"), Some(DC, "SlotOccupancySensor"),
  doc="Stand carrying tool docks and their occupancy sensors.", src="✅")
C("LinearRail", "MechanismPart", Some(DC, "RailCarriage"), doc="Linear axis carrying a robot (igus ZLW-1660).",
  src="✅")
C("RailCarriage", "MechanismPart", Some(IDC, "LinearRail"), doc="Moving rail carriage.")
C("DeviceSensor", "MechanismPart", Some("monitorsEntity", "Entity"),
  doc="A sensor of a device or fixture (not AICOR's robot-mounted Sensor; D-LAT-1).", src="✅")
C("SeatSensor", "DeviceSensor", Some("monitorsEntity", "PlateSeatPose"), doc="Flush seat window (plate seated).",
  src="✅")
C("SlotOccupancySensor", "DeviceSensor", Some(IDC, Or("PlateSlot", "MagazineStand")), doc="Ray occupancy sensor.",
  src="✅")
C("CarrierPresenceSensor", "DeviceSensor", Some(IDC, "MobileRobotBase"), doc="Carrier present in AMR cabinet.",
  src="✅")
C("ThroughBeamSensor", "DeviceSensor", Some(IDC, "LabAutomationDevice"), doc="Emitter / receiver beam element.")
C("DockSensor", "DeviceSensor", Some(IDC, "DeterministicAMRDock"), doc="Ray measuring the docked AMR pose.", src="✅")
C("BarcodeReader", "DeviceSensor", Some("monitorsEntity", "Labware"), doc="Reads plate barcodes.", src="✅")
C("LightBarrierSensor", "DeviceSensor", Some(IDC, "QCCalibrationStation"), doc="Crossed barrier measuring a TCP.",
  src="✅")
C("FiducialMarker", "MechanismPart", Some(AFF, "CalibratingTask"), doc="Marker used to register poses.")
C("AprilTagMarker", "FiducialMarker", Some(IDC, "LabArtifact"), doc="AprilTag 36h11.", src="✅")
C("DatumPin", "FiducialMarker", Some(IDC, "LabArtifact"), doc="Conical registration pin.", src="✅")

# =====================================================================================================================
module("lab-twin-robots", "Cell robots, robot bodies, tools and robot skills")
# =====================================================================================================================
C("CellRobot", ["Robot", "LabArtifact"], Some("servesStation", "LabArtifact"), Some(CAP, "RobotSkill"),
  doc="A robot of an automation cell, assigned to stations (layout P1).", src="✅")
C("FixedBaseManipulator", "CellRobot", Some("hasProperPart", "ArmRobotBody"),
  Not(Some(DC, Or("LinearRail", "MobileRobotBase"))), doc="Arm on a fixed pedestal (R01 FR3).", src="✅")
C("RailMountedManipulator", "CellRobot", Some(DC, "LinearRail"), Some("hasProperPart", "ArmRobotBody"),
  doc="Arm on a linear rail with a tool changer (R02 UR5e).", src="✅")
C("SampleTransportAMR", "CellRobot", Some("hasProperPart", "MobileRobotBase"), Some(CAP, "SampleTransportSkill"),
  doc="Clean-sample AMR with a sealed cabinet (R03, MiR100 class).", src="✅")
C("ArmRobotBody", "RobotBody", Some("hasEndEffectorMount", "EndEffector"), doc="Serial arm body (FR3, UR5e).")
P("hasEndEffectorMount", doc="A robot body offers an end-effector mount.")
C("MobileRobotBase", "RobotBody", Some(DC, "CabinetLid"), doc="AMR base with the sample cabinet (R03).", src="✅")
C("CabinetLid", "MechanismPart", Some(IDC, "MobileRobotBase"), doc="Flat lid over the carrier nest.", src="✅")
C("VirtualPlanarLink", "Link", Some("partOf", "MobileRobotBase"),
  doc="A simulation link of the AMR's planar base joints (twin artefact).", src="✅")
C("AutomaticToolChanger", "MechanismPart", Some("couplesTool", "ExchangeableTool"),
  doc="Robot-side tool coupler.", src="✅")
C("ExchangeableTool", "LabArtifact", Some(DC, "ToolBody"), Some(POSE, "ToolCouplingPose"),
  doc="End effector exchanged by a tool changer (stored in a magazine, not a robot-body link).", src="✅")
C("ToolBody", "MechanismPart", Some(IDC, "ExchangeableTool"), doc="Housing of a tool.")
C("GripperJaw", "MechanismPart", Some(IDC, "ExchangeableTool"), doc="Jaw of a gripper tool.")
C("PlateGripperTool", "ExchangeableTool", Exact(2, DC, "GripperJaw"), Some("affordsRobotSkill", "PlateTransferSkill"),
  doc="Two-jaw SBS plate gripper (T01).", src="✅")
P("affordsRobotSkill", doc="A tool affords a robot skill when coupled.")
C("TubeGripperTool", "ExchangeableTool", Some("affordsRobotSkill", "TubeHandlingSkill"), doc="T02.", src="✅")
C("PipettingTool", "ExchangeableTool", Some("affordsRobotSkill", "LiquidTransferSkill"), doc="T03.", src="✅")
C("SuctionPickupTool", "ExchangeableTool", Some("affordsRobotSkill", "PlateTransferSkill"), doc="T04.", src="✅")
C("CameraInspectionTool", "ExchangeableTool", Some("affordsRobotSkill", "InspectionSkill"), doc="T05.", src="✅")
D("PlateGripperTool", "TubeGripperTool", "PipettingTool", "SuctionPickupTool", "CameraInspectionTool")
C("RobotSkill", "dul:Quality", Some("functionAffords", "LabTaskType"), doc="A capability of a robot.")
for sk, task, doc in (("PlateTransferSkill", "PlateTransferTask", "Pick, carry, place SBS plates."),
                      ("SampleTransportSkill", "PlateTransferTask", "Carry samples in a closed cabinet."),
                      ("NavigationSkill", "NavigationTask", "Navigate between docks."),
                      ("DockingSkill", "DockingTask", "Dock deterministically."),
                      ("ToolExchangeSkill", "ToolExchangeTask", "Exchange end effectors."),
                      ("TubeHandlingSkill", "PlateTransferTask", "Handle tubes."),
                      ("LiquidTransferSkill", "LiquidDispensingTask", "Pipette."),
                      ("InspectionSkill", "ImagingTask", "Inspect with a camera.")):
    C(sk, "RobotSkill", Some("functionAffords", task), doc=doc, src="✅")

# =====================================================================================================================
module("lab-twin-labware", "Labware, wells and material portions")
# =====================================================================================================================
P("handledIn", doc="Labware is handled in tasks of a type.")
C("Labware", "LabArtifact", Some("handledIn", "PlateTransferTask"), doc="Containers handled in experiments.")
C("Microplate", "Labware", eq=And("Labware", Some(DC, "Well")), doc="Defined: labware with wells.")
C("SBSMicroplate96", "Microplate", Exact(96, DC, "Well"), doc="SBS / ANSI 96-well plate.", src="✅")
C("CulturePlate", "Microplate", Some(DC, "CultureWell"), doc="Plate holding cultures (Plate_P17).", src="✅")
C("ReferencePlate", "Microplate", Some(AFF, "CalibratingTask"), doc="L21 calibration reference plate.", src="✅")
C("Well", "MechanismPart", Some(IDC, "Microplate"), DSome("wellId", "xsd:string"), doc="A well of a plate.", src="✅")
C("CultureWell", "Well", eq=And("Well", Some("containsMaterial", "CultureMediumPortion")),
  doc="Defined: a well that contains culture medium.")
C("CultureMediumPortion", "BiologicalSample", Some("isContainedIn", "Well"),
  doc="The medium in one well: a material portion, contained, not a part.", src="✅")
C("WellOrganoid", "BiologicalSpecimen", Some(LOC, "Well"),
  doc="The organoid cultured in one well (Cell 01: hepatotoxicity model; RS reading: a liver organoid).", src="✅")
C("ReagentPortion", "Sample", Some("isContainedIn", "Labware"), doc="A reagent portion in a container.")
C("ChallengeReagentPortion", "ReagentPortion", Some(AFF, "ChallengeDosingTask"), doc="Abstract challenge reagent.",
  src="✅")
C("RescueReagentPortion", "ReagentPortion", Some(AFF, "RescueDosingTask"), doc="Abstract rescue reagent.", src="✅")
D("Well", "CultureMediumPortion")
D("ChallengeReagentPortion", "RescueReagentPortion")

# =====================================================================================================================
module("lab-twin-poses", "Poses: coordinate and interaction frames of the twin (AICOR SpatialPose)")
# =====================================================================================================================
C("TwinPose", "SpatialPose", Some("isPoseOf", "dul:PhysicalObject"), doc="A named pose on an object (USD Xform).",
  src="✅")
C("KinematicPose", "TwinPose", Some("isPoseOf", "LabArtifact"), doc="Reference pose of a link or mechanism.")
C("InteractionPose", "TwinPose", Some(AFF, "LabTaskType"), doc="Pose where a task is performed.")
for pz, task, doc in (("PlateSeatPose", Or("PlateTransferTask", "PlateStoringTask"), "SBS plate seat."),
                      ("ApproachPose", Or("NavigationTask", "PlateTransferTask"), "Pose reached before an interaction."),
                      ("DockPose", "DockingTask", "Pose of a docked AMR."),
                      ("ToolCenterPose", "PlateTransferTask", "Tool centre point."),
                      ("ToolCouplingPose", "ToolExchangeTask", "Coupling face of a tool or changer."),
                      ("PipettingTargetPose", "LiquidDispensingTask", "Where a channel doses into a well."),
                      ("ImagingTargetPose", "ImagingTask", "Where a well is imaged."),
                      ("RackPositionPose", Or("LiquidDispensingTask", "TipHandlingTask"), "Rack position."),
                      ("WastePose", "TipHandlingTask", "Tip ejection."),
                      ("CalibrationPose", "CalibratingTask", "Datum for QC / calibration."),
                      ("StorageLocationPose", Or("ConsumableStoringTask", "ColdStoringTask"), "Shelf location."),
                      ("ManipulationPointPose", "OperatorInteractionTask", "Handle, door, lid, sash, tap, button."),
                      ("OperatorPositionPose", "OperatorInteractionTask", "Where a person works."),
                      ("ItemAccessPose", "PlateTransferTask", "Where a person takes or puts an item."),
                      ("CleaningPointPose", "CleaningTask", "Sink basin, eyewash.")):
    C(pz, "InteractionPose", Some(AFF, task), doc=doc, src="✅")
C("OpticalPose", "TwinPose", Some("isPoseOf", Or("ImagingDevice", "MechanismPart", "CellRobot")),
  doc="Objective, camera or focal-point pose.")
C("IlluminationPose", "OpticalPose", Some("isPoseOf", "ImagingDevice"), doc="Illumination axis.")
C("ViewpointPose", "TwinPose", Some("isPoseOf", "dul:PhysicalPlace"), doc="Viewpoint of a virtual twin camera.")
D("PlateSeatPose", "ApproachPose", "DockPose", "ToolCenterPose", "ToolCouplingPose", "PipettingTargetPose",
  "ImagingTargetPose", "RackPositionPose", "WastePose", "CalibrationPose")

# =====================================================================================================================
module("lab-twin-tasks", "Lab task types and actions")
# =====================================================================================================================
C("LabTaskType", "dul:Concept", All("classifiesAction", "LabAction"), doc="A type of lab work.")
P("classifiesAction", inv="executesTaskType", doc="A task type classifies actions.")
for t, part, doc in (("PlateTransferTask", "Labware", "Move labware between seats."),
                     ("PlateStoringTask", "PlateStorageDevice", "Put a plate into a store."),
                     ("PlateRetrievingTask", "LabArtifact", "Take a plate out of a device."),
                     ("IncubatingTask", "IncubationDevice", "Keep a plate in an incubator."),
                     ("LiquidDispensingTask", "DispensingDevice", "Dispense liquid into a well."),
                     ("ChallengeDosingTask", "DispensingDevice", "Dose the challenge reagent."),
                     ("RescueDosingTask", "DispensingDevice", "Dose the rescue reagent."),
                     ("ImagingTask", "ImagingDevice", "Acquire an image."),
                     ("CalibratingTask", "QCCalibrationStation", "Check / calibrate against a reference."),
                     ("QuarantiningTask", "QuarantineStation", "Contain a plate."),
                     ("QuarantineReleaseTask", "QuarantineStation", "Release a plate after authorisation."),
                     ("IdentifyingTask", "BarcodeReader", "Read a plate identity."),
                     ("NavigationTask", "SampleTransportAMR", "Drive between docks."),
                     ("DockingTask", "Dock", "Dock an AMR."),
                     ("ToolExchangeTask", "AutomaticToolChanger", "Couple / release a tool."),
                     ("TipHandlingTask", "PipettingChannel", "Pick up / eject a tip."),
                     ("ColdStoringTask", "ColdStorageDevice", "Store material cold."),
                     ("SterilizingTask", "Autoclave", "Sterilise."),
                     ("AsepticHandlingTask", "BiosafetyCabinet", "Handle open cultures."),
                     ("TemperatureControllingTask", "ManualLabEquipment", "Hold a temperature."),
                     ("ConsumableStoringTask", "StorageShelving", "Store consumables."),
                     ("CleaningTask", "LabSinkUnit", "Wash."),
                     ("OperatorInteractionTask", "LabArtifact", "A person operates equipment.")):
    C(t, "LabTaskType", All("classifiesAction", Some("hasParticipantEntity", part)),
      doc=f"{doc} Every action of this type involves a {part}.", src="✅")
P("prescribesTaskType", doc="A workflow / protocol prescribes a task type as a step.")
C("LabAction", "soma:Action", Some("executesTaskType", "LabTaskType"), doc="An action of lab work.")
C("RobotAction", "LabAction", eq=And("LabAction", Some("hasParticipantEntity", "Robot")),
  doc="Defined: a lab action a robot takes part in.")
for a, t in (("TransferAction", "PlateTransferTask"), ("StoreAction", "PlateStoringTask"),
             ("RetrieveAction", "PlateRetrievingTask"), ("IncubateAction", "IncubatingTask"),
             ("DoseAction", "LiquidDispensingTask"), ("ImageAction", "ImagingTask"), ("QCAction", "CalibratingTask"),
             ("QuarantineAction", "QuarantiningTask")):
    C(a, "LabAction", eq=And("LabAction", Some("executesTaskType", t)), doc=f"Defined: a lab action of type {t}.")
C("AMRTransferAction", "TransferAction", eq=And("TransferAction", Some("hasParticipantEntity", "SampleTransportAMR")),
  doc="Defined: a transfer by the sample AMR.")
D("PlateTransferTask", "PlateStoringTask", "PlateRetrievingTask", "IncubatingTask", "LiquidDispensingTask",
  "ImagingTask", "CalibratingTask", "QuarantiningTask")

# =====================================================================================================================
module("lab-twin-device-manuals", "Device manual knowledge (Cell 01 component contracts) and device process knowledge")
# =====================================================================================================================
P("manualFor", doc="A manual is about a device or robot (model / component).")
P("documentsProcedure", doc="A manual documents an operating procedure.")
P("requiresPrecondition", doc="A procedure requires a precondition.")
P("hasExpectedEffect", doc="A procedure has an expected effect.")
P("usesProcedureMonitor", doc="A procedure is monitored by a monitor.")
P("hasRecoveryProcedure", doc="A procedure / failure mode is recovered by a procedure.")
P("producesEvidenceOutput", doc="A procedure produces an evidence output.")
P("declaresFailureMode", doc="A manual declares a failure mode.")
P("declaresRiskControl", doc="A manual declares a risk control.")
P("declaresOperatingConstraint", doc="A manual declares an operating constraint.")
P("declaresMonitor", doc="A manual declares a device monitor.")
P("hasFailureConsequence", doc="A failure mode has a consequence (hazard / validity loss).")
P("hasProcessMicrotheory", doc="A device's process knowledge.")
P("enforcedInTwinBy", doc="A precondition / rule is enforced by a twin controller check.")
for n, rng, doc in (("setpointValue", "xsd:double", "Numeric value of a setpoint."),
                    ("quantityName", "xsd:string", "Quantity a setpoint / variable refers to."),
                    ("manufacturerBaseline", "xsd:string", "Manufacturer / model family a contract is based on.")):
    P(n, kind="data", range_=rng, doc=doc)
C("DeviceManual", "dul:InformationObject", Some("manualFor", "LabArtifact"), Some("documentsProcedure",
                                                                                   "OperatingProcedure"),
  DSome("sourceDocument", "xsd:string"),
  doc="Operating knowledge of a device or robot: identity, procedures, setpoints, constraints, monitors, failure "
      "modes, recovery and risk controls.", src="✅")
C("CellComponentContract", "DeviceManual", DSome("manufacturerBaseline", "xsd:string"),
  doc="A Cell 01 SDT component contract (sdt/components/*.yaml): the project's manual-equivalent; no vendor manual is "
      "in the repository (restricted source folders are empty).", src="✅")
C("OperatingProcedure", "ActionContract", Some("requiresPrecondition", "Precondition"),
  Some("hasExpectedEffect", "ExpectedEffect"), Some("hasRecoveryProcedure", "RecoveryProcedure"),
  doc="A documented device operation with preconditions, parameters, effects, monitors, recovery and evidence outputs "
      "(Cell 01 action_contracts).", src="✅")
C("ManualItem", "dul:Description", DSome("statementText", "xsd:string"), doc="One item of a manual, verbatim.",
  src="✅")
C("Precondition", "ManualItem", Some("isRequiredBy", "OperatingProcedure"), doc="Must hold before a procedure.",
  src="✅")
P("isRequiredBy", doc="Inverse of requiresPrecondition.")
for pc, doc in (("IdentityPrecondition", "Plate / reagent / target identity verified or consistent."),
                ("AvailabilityPrecondition", "Device / slot / station available, reserved or clear."),
                ("EnvironmentPrecondition", "Environment within its valid envelope."),
                ("CalibrationPrecondition", "Calibration / tool frame valid."),
                ("SafetyPrecondition", "A safety or containment state holds (interlocks ready, airspace clear)."),
                ("AuthorizationPrecondition", "An authorisation is present (quarantine release, QA decision)."),
                ("PlacementPrecondition", "An object is seated / present / positioned.")):
    C(pc, "Precondition", Some("isRequiredBy", "OperatingProcedure"), doc=doc, src="✅")
C("ExpectedEffect", "ManualItem", Some("isEffectOf", "OperatingProcedure"), doc="State after a procedure.", src="✅")
P("isEffectOf", doc="Inverse of hasExpectedEffect.")
C("EvidenceOutput", "ManualItem", Some("isEvidenceOf", "OperatingProcedure"), doc="Evidence a procedure records.",
  src="✅")
P("isEvidenceOf", doc="Inverse of producesEvidenceOutput.")
C("OperatingSetpoint", "ManualItem", DSome("quantityName", "xsd:string"),
  doc="Nominal operating state value of a device (e.g. 37 °C).", src="✅")
C("OperatingConstraint", ["ManualItem", "LabConstraint"], Some("constrainsDevice", "LabArtifact"),
  doc="A constraint a manual places on operation.", src="✅")
P("constrainsDevice", doc="A constraint applies to a device.")
C("DeviceMonitor", "ProcessMonitor", DSome("statementText", "xsd:string"),
  doc="A monitored expectation of a device (expectation + observation channel).", src="✅")
C("DeviceFailureMode", "FailureSignature", Some("hasRecoveryProcedure", "RecoveryProcedure"),
  Some("hasFailureConsequence", "LabHazard"), DSome("statementText", "xsd:string"),
  doc="A fault of a device, with its consequence and recovery (Cell 01 failure_modes).", src="✅")
C("RecoveryProcedure", "Repair", DSome("statementText", "xsd:string"), doc="What to do when a fault occurs.",
  src="✅")
C("RiskControl", ["ManualItem", "SafetyConstraint"], Some("mitigatesHazard", "LabHazard"),
  doc="A control measure a manual names (alarms, timing limits, interlocks, identity tracking).", src="✅")
C("DeviceProcessMicrotheory", "BodyWorldProcessMicrotheory", Some("microtheoryOf", "LabArtifact"),
  doc="Scoped process knowledge of a device: state variables, articulations, environment model.", src="✅")
P("microtheoryOf", doc="A microtheory describes a device's processes.")
C("TwinControllerCheck", "dul:Description", Some("exercisedByTest", "TwinVerificationTest"),
  doc="A precondition / rule check implemented in a twin device controller (refuses the command when violated).",
  src="✅")
P("exercisedByTest", doc="A twin check is exercised by a test.")
C("TwinVerificationTest", "dul:InformationObject", DSome("verificationTest", "xsd:string"),
  doc="A twin regression test (scripts/test_*.py) with its pass record.", src="✅")
C("TwinEnforcedPrecondition", "Precondition", eq=And("Precondition", Some("enforcedInTwinBy", "TwinControllerCheck")),
  doc="Defined: a manual precondition the twin enforces.")
D("IdentityPrecondition", "AvailabilityPrecondition", "EnvironmentPrecondition", "CalibrationPrecondition",
  "SafetyPrecondition", "AuthorizationPrecondition", "PlacementPrecondition")

# =====================================================================================================================
module("lab-twin-safe-action", "Safe action: hazards, safety rules, enforcement, admissibility of candidate actions")
# =====================================================================================================================
P("mitigatesHazard", doc="A device / rule / control mitigates a hazard.")
P("prohibitsTaskType", doc="A rule prohibits a task type (in its situation).")
P("appliesInSituation", doc="A rule applies in a situation type.")
P("enforcedBy", doc="A rule is enforced by a mechanism (interlock, controller check, critic).")
P("derivedFromSource", doc="A rule is derived from a source (manual, standard, Cell 01 rule file).")
P("violatesRule", doc="A candidate action / command violates a rule.")
P("refusedByEntity", doc="A command was refused by a device / interlock / critic.")
C("LabHazard", "dul:Description", Some("hazardTo", "Entity"), doc="A potential source of harm in the lab.", src="✅")
P("hazardTo", doc="Whom / what a hazard can harm.")
for hz, doc, s in (("HumanInjuryHazard", "Robot motion or pinch points near a person.", "✅"),
                   ("CollisionHazard", "Robot / device / labware collision.", "✅"),
                   ("ContaminationHazard", "Transfer of contaminants to cultures or reagents.", "✅"),
                   ("SampleIntegrityHazard", "Loss of environment, time window or physical integrity.", "✅"),
                   ("IdentityHazard", "Swap or loss of sample identity.", "✅"),
                   ("MeasurementValidityHazard", "Measurements made with an invalid measurement chain.", "✅"),
                   ("AsphyxiationHazard", "Oxygen depletion from LN2 / CO2.", "🔧"),
                   ("FireHazard", "Fire.", "🔧"),
                   ("ChemicalExposureHazard", "Splash / exposure of a person.", "🔧")):
    C(hz, "LabHazard", Some("hazardTo", "Entity"), doc=doc, src=s)
C("LabSafetyRule", "IncapabilityAssertion", Some("mitigatesHazard", "LabHazard"),
  Some("prohibitsTaskType", "LabTaskType"), Some("derivedFromSource", "dul:InformationObject"),
  DSome("statementText", "xsd:string"),
  doc="A universal prohibition on lab actions in a situation (AICOR IncapabilityAssertion: removes trajectories).",
  src="✅")
C("HumanSafetyRule", "LabSafetyRule", Some("mitigatesHazard", "HumanInjuryHazard"), Some("enforcedBy",
                                                                                         "SafetyDevice"),
  doc="Protects people (enclosure, door interlocks, light curtain, e-stop).", src="✅")
C("MachineProtectionRule", "LabSafetyRule", Some("mitigatesHazard", "CollisionHazard"),
  doc="Protects equipment and labware (airspace interlock, gate state, cabinet closed in transit).", src="✅")
C("BiosafetyRule", ["LabSafetyRule", "ContaminationCompatibility"], Some("mitigatesHazard", "ContaminationHazard"),
  doc="Asepsis / contamination rules; gates intervention admissibility (RS ContaminationCompatibility).", src="✅")
C("SampleIntegrityRule", "LabSafetyRule", Some("mitigatesHazard", "SampleIntegrityHazard"),
  doc="Environment envelope, time outside the incubator, seating.", src="✅")
C("IdentityRule", "LabSafetyRule", Some("mitigatesHazard", "IdentityHazard"), doc="Identity must be verified.",
  src="✅")
C("MeasurementValidityRule", "LabSafetyRule", Some("mitigatesHazard", "MeasurementValidityHazard"),
  doc="No measurement with an invalid calibration / tool frame.", src="✅")
C("AuthorizationNorm", "Norm", Some("prohibitsTaskType", "LabTaskType"), DSome("statementText", "xsd:string"),
  doc="A normative rule: an action is permitted only with an authorisation (normative, not causal, admissibility).",
  src="✅")
C("SafetySourceDocument", "dul:InformationObject", DSome("sourceDocument", "xsd:string"),
  doc="A document safety knowledge is derived from (Cell 01 specification, rule files, site proposal).", src="✅")
C("SafetyEnforcementMechanism", "dul:Description", Some("enforces", "LabSafetyRule"),
  doc="How a rule is enforced in the twin.")
P("enforces", inv="enforcedBy", doc="A mechanism enforces a rule.")
C("PhysicalInterlockMechanism", "SafetyEnforcementMechanism", Some("realizedByDevice", "SafetyDevice"),
  doc="Enforcement by a safety device (door switch, light curtain, e-stop).", src="✅")
P("realizedByDevice", doc="A mechanism is realised by a device.")
C("ControllerInterlockMechanism", ["SafetyEnforcementMechanism", "TwinControllerCheck"],
  Some("realizedByDevice", "LabArtifact"),
  doc="Enforcement by a device controller refusing a command (L12 airspace, L10 environment, H4 token).", src="✅")
C("CriticGateMechanism", ["SafetyEnforcementMechanism", "SafetyCheck"],
  Some("testsCriterion", "CommitmentCriterion"),
  doc="Enforcement by Cell 01's critic vector: an event commits only if safety_ok (AICOR commitment checking).",
  src="✅")
P("testsCriterion", doc="A gate tests a commitment criterion.")
C("UnsafeCandidateAction", "CandidateAction", eq=And("CandidateAction", Some("violatesRule", "LabSafetyRule")),
  doc="Defined: a candidate action that violates a lab safety rule (inadmissible).")
C("UnauthorizedCandidateAction", "CandidateAction", eq=And("CandidateAction", Some("violatesRule",
                                                                                  "AuthorizationNorm")),
  doc="Defined: a candidate action that violates an authorisation norm (normatively inadmissible).")
C("RefusedCommand", "CandidateAction", Some("violatesRule", Or("LabSafetyRule", "AuthorizationNorm")),
  Some("refusedByEntity", "Entity"), DSome("verificationTest", "xsd:string"),
  doc="A command the twin refused, observed in a verification test.", src="✅")
C("ProtectiveStopEvent", "dul:Event", Some("triggeredByDevice", "SafetyDevice"),
  doc="A latched protective stop (e.g. light curtain broken without muting).", src="✅")
P("triggeredByDevice", doc="An event is triggered by a device.")
D("HumanSafetyRule", "MachineProtectionRule", "BiosafetyRule", "SampleIntegrityRule", "IdentityRule",
  "MeasurementValidityRule")

# =====================================================================================================================
module("lab-twin-culture-experiments", "Culture experiments: designs, arms, interventions, readouts, runs, conclusions")
# =====================================================================================================================
P("hasArm", doc="A study design has an arm.")
P("assignsUnit", doc="An arm assigns an experimental unit (well).")
P("appliesIntervention", doc="An arm applies an intervention specification.")
P("observedBySchedule", doc="A design observes units on a schedule.")
P("runOfStudy", doc="A run realises a study design.")
P("concernsWell", doc="A record / conclusion concerns a well.")
P("comparesArm", doc="A conclusion compares arms.")
P("withheldBecause", doc="A conclusion is withheld for a reason.")
P("hasScenarioCondition", doc="A run is conducted under a scenario condition (fault injection).")
P("realizesIntervention", doc="A record is about an intervention event.")
P("appliedToWell", doc="An intervention event is applied to a well.")
for n, rng, doc in (("doseAU", "xsd:double", "Dose in abstract units (Cell 01 D016: illustrative)."),
                    ("time_h", "xsd:double", "Culture time (h)."),
                    ("interval_h", "xsd:double", "Observation interval (h)."),
                    ("horizon_h", "xsd:double", "Observation horizon (h)."),
                    ("viabilityMean", "xsd:double", "Posterior mean viability."),
                    ("viabilityP05", "xsd:double", "Posterior 5 % quantile."),
                    ("viabilityP95", "xsd:double", "Posterior 95 % quantile."),
                    ("radius_um", "xsd:double", "Measured organoid radius (µm)."),
                    ("coreOpticalDensity", "xsd:double", "Measured core optical density."),
                    ("debrisCount", "xsd:integer", "Counted debris."),
                    ("mediumHaze", "xsd:double", "Measured haze."),
                    ("claimProbability", "xsd:double", "Posterior probability of a conclusion."),
                    ("claimStatus", "xsd:string", "Status (candidate / withheld ...)."),
                    ("isCommittedEvent", "xsd:boolean", "Whether the culture ledger committed the event."),
                    ("scenarioName", "xsd:string", "Scenario of a run.")):
    P(n, kind="data", range_=rng, chars=["Functional"] if n == "isCommittedEvent" else [], doc=doc)
C("ChallengeRescueStudyDesign", "StudyDesign", Some("hasArm", "ChallengeOnlyArm"), Some("hasArm",
                                                                                      "ChallengeRescueArm"),
  Some("hasArm", "ControlArm"), Some("observedBySchedule", "ObservationSchedule"),
  doc="Cell 01's challenge-rescue design: graded challenge doses, rescue at 6 h, untreated controls, 4x imaging "
      "every 6 h to 72 h.", src="✅")
C("ExperimentalArm", "dul:Description", Some("assignsUnit", "Well"), doc="A group of units treated alike.", src="✅")
C("InterventionSpec", "dul:Description", DSome("doseAU", "xsd:double"), DSome("time_h", "xsd:double"),
  doc="A planned intervention (agent, dose, time).", src="✅")
C("ChallengeSpec", "InterventionSpec", Some("specifiesTask", "ChallengeDosingTask"), doc="Planned challenge dose.",
  src="✅")
C("RescueSpec", "InterventionSpec", Some("specifiesTask", "RescueDosingTask"), doc="Planned rescue dose.", src="✅")
P("specifiesTask", doc="A specification is realised by a task type.")
C("ChallengeOnlyArm", "ExperimentalArm", eq=And("ExperimentalArm", Some("appliesIntervention", "ChallengeSpec"),
                                                 Not(Some("appliesIntervention", "RescueSpec"))),
  doc="Defined: challenged, not rescued.")
C("ChallengeRescueArm", "ExperimentalArm", eq=And("ExperimentalArm", Some("appliesIntervention", "ChallengeSpec"),
                                                   Some("appliesIntervention", "RescueSpec")),
  doc="Defined: challenged and rescued.")
C("ControlArm", "ExperimentalArm", eq=And("ExperimentalArm", Not(Some("appliesIntervention", "InterventionSpec"))),
  doc="Defined: no intervention.")
C("ObservationSchedule", "dul:Description", DSome("interval_h", "xsd:double"), DSome("horizon_h", "xsd:double"),
  doc="When units are observed.", src="✅")
C("ChallengeIntervention", "BiologicalIntervention", Some("realizedByAction", "ScientificActionDesignator"),
  doc="A dose of the challenge agent into a well (L12 dose).", src="✅")
C("RescueIntervention", "BiologicalIntervention", Some("realizedByAction", "ScientificActionDesignator"),
  doc="A dose of the rescue agent into a well.", src="✅")
C("MorphologyViabilityReadout", "CellViabilityReadout", Some("observationOf", "WellOrganoid"),
  doc="Viability inferred from bright-field morphology (radius, core OD, debris, haze) of a 4x image.", src="✅")
C("RescueHypothesis", "ScientificHypothesis", Some("heldIn", "CultureSDT"),
  doc="'Rescue at 6 h raises 72 h viability at challenge dose d.'", src="✅")
C("CultureExperimentRun", "ExperimentalEpisode", Some("runOfStudy", "ChallengeRescueStudyDesign"),
  DSome("scenarioName", "xsd:string"), doc="One executed run of the study in the twin.", src="✅")
C("ScenarioCondition", "dul:Description", DSome("statementText", "xsd:string"),
  doc="A condition of a run (nominal, injected fault).", src="✅")
C("FaultInjection", "ScenarioCondition", Some("injectsHazard", "LabHazard"), doc="A deliberately injected fault.",
  src="✅")
P("injectsHazard", doc="A fault injection realises a hazard.")
C("RescueComparisonConclusion", "ScientificConclusion", Min(2, "concernsWell", "Well"),
  DSome("claimStatus", "xsd:string"), doc="Conclusion comparing a rescued with an unrescued well.", src="✅")
C("WithholdingReason", "dul:Description", DSome("statementText", "xsd:string"), doc="Why a conclusion is withheld.",
  src="✅")
C("UnverifiedComparatorReason", "WithholdingReason", Some("citesRule", "LabSafetyRule"),
  doc="A compared well received an uncommitted (unverified) intervention.", src="✅")
C("ContaminationSuspectedReason", "WithholdingReason", Some("citesRule", "BiosafetyRule"),
  doc="A compared well is flagged contamination_suspected.", src="✅")
P("citesRule", doc="A reason cites a rule.")
C("WithheldConclusion", "RescueComparisonConclusion",
  eq=And("RescueComparisonConclusion", Some("withheldBecause", "WithholdingReason")),
  doc="Defined: a conclusion withheld for a stated reason.")
C("WellBeliefEstimate", "StateEstimate", Some("concernsWell", "Well"),
  doc="The culture SDT's posterior estimate of a well's latent state (epistemic status: inferred).", src="✅")
C("WellObservationRecord", "CellViabilityReadout", Some("concernsWell", "Well"), DSome("radius_um", "xsd:double"),
  doc="Measured morphology of one well at one session, with image / calibration provenance.", src="✅")
C("InterventionRecord", "dul:InformationObject", Some("partOf", "InterventionHistory"),
  Some("realizesIntervention", "BiologicalIntervention"),
  DSome("isCommittedEvent", "xsd:boolean"), doc="A dose event in a well's intervention history.", src="✅")
C("UnverifiedInterventionRecord", "InterventionRecord",
  eq=And("InterventionRecord", DValue("isCommittedEvent", "false", "xsd:boolean")),
  doc="Defined: an intervention record the ledger did not commit.")
C("WellQualityRecord", "dul:InformationObject", Some("concernsWell", "Well"), doc="ESS and anomaly flags.", src="✅")
C("ContaminationSuspectedFlag", "WellQualityRecord", Some("flagsHazard", "ContaminationHazard"),
  doc="Cell 01's contamination_suspected rule fired for a well.", src="✅")
P("flagsHazard", doc="A record flags a hazard.")
D("ChallengeOnlyArm", "ChallengeRescueArm", "ControlArm")
D("ChallengeIntervention", "RescueIntervention")
D("ChallengeSpec", "RescueSpec")

# =====================================================================================================================
module("lab-twin-records", "Action records, monitor results and routing (Cell 01 NEEM records)")
# =====================================================================================================================
P("recordsAction", doc="A record is about an action.")
P("hasMonitorResult", doc="A record contains a monitor result.")
P("hasRouting", chars=["Functional"], doc="The routing Cell 01's validator assigned to a record.")
P("routesTo", doc="Where a routing sends the record or object.")
P("includesAction", doc="An episode includes an action.")
C("CellActionRecord", "LabExecutionTrace", Some("recordsAction", "LabAction"), Some("hasRouting", "RecordRouting"),
  doc="A Cell 01 NEEM-style record of one action (critic vector, monitors, routing).", src="✅")
C("MonitorResult", "dul:InformationObject", DSome("monitorPassed", "xsd:boolean"), DSome("monitorName", "xsd:string"),
  doc="Result of one Cell 01 monitor on an action.", src="✅")
C("FailedMonitorResult", "MonitorResult", eq=And("MonitorResult", DValue("monitorPassed", "false", "xsd:boolean")),
  doc="Defined: a monitor that did not pass.")
C("BlockedActionRecord", "CellActionRecord", eq=And("CellActionRecord", Some("hasMonitorResult",
                                                                             "FailedMonitorResult")),
  doc="Defined: a record with a failed monitor; its semantic event cannot commit.")
C("RecordRouting", "dul:Concept", All("classifiesRecord", "CellActionRecord"), doc="A routing outcome.", src="✅")
P("classifiesRecord", doc="A routing classifies records.")
C("CommitRouting", "RecordRouting", Some("routesTo", "LabSemanticDigitalTwin"), doc="Commit (culture SDT / evidence "
                                                                                   "layer / admission).", src="✅")
C("QuarantineRouting", "RecordRouting", Some("routesTo", "QuarantineStation"), doc="Object to H4 (a Repair).",
  src="✅")
C("EscalationRouting", "RecordRouting", Some("routesTo", "dul:Agent"), doc="To a human (an AICOR HelpRequest).",
  src="✅")
C("InvalidationRouting", "RecordRouting", Some("routesTo", "LabSemanticDigitalTwin"),
  doc="Invalidate dependent measurements.", src="✅")
D("CommitRouting", "QuarantineRouting", "EscalationRouting", "InvalidationRouting")
for ind, cls in (("route_culture_sdt_commit", "CommitRouting"), ("route_evidence_layer_commit", "CommitRouting"),
                 ("route_evidence_admission", "CommitRouting"), ("route_H4_quarantine", "QuarantineRouting"),
                 ("route_human_escalation", "EscalationRouting"),
                 ("route_invalidate_dependent_measurements", "InvalidationRouting")):
    I(ind, cls)

# =====================================================================================================================
module("lab-twin-experiment-to-motion",
       "From a required information gain to the robot's physical actions and motions (derivation layer)")
# =====================================================================================================================
P("discriminatesModel", doc="A candidate experiment's outcome distribution differs between competing models.")
P("selectedUnder", doc="A candidate was selected under an information-gain requirement.")
P("realisesProposal", doc="A realisation plan realises a selected experiment proposal.")
P("hasSession", doc="A plan has a protocol session.")
P("hasStep", doc="A session / designator has an ordered step.")
P("refinesInto", doc="A designator is refined into a lower-level designator (inverse reading of RS refines).")
P("boundToDevice", doc="A designator is bound to a device that performs it.")
P("boundToPose", doc="A designator is bound to a pose of the twin.")
P("performedByRobot", doc="A motion designator is performed by a robot.")
P("commandsDevice", doc="A device-command designator commands a device.")
P("usesToolDesignator", doc="A motion uses an exchangeable tool.")
P("derivesPlan", doc="A derivation derives a realisation plan.")
P("appliesAxiomSet", doc="A derivation applies an L3 axiom set.")
P("conditionedOnBelief", doc="An information-gain estimate is conditioned on a culture SDT belief.")
P("estimatesGainOf", doc="An estimate is about a candidate experiment.")
P("executesPlan", doc="An executed episode executes a realisation plan.")
P("routeVia", doc="A plate transfer route passes a station or fixture.")
for n, rng, doc in (("requiredGain_bits", "xsd:double", "Required expected information gain (bits)."),
                    ("expectedGain_bits", "xsd:double", "Expected information gain I(M; y | a, D) (bits)."),
                    ("realisedGain_bits", "xsd:double", "Realised information gain KL(p(M|D,y) ‖ p(M|D)) (bits)."),
                    ("rescueDelay_h", "xsd:double", "Challenge-to-rescue delay (h)."),
                    ("replicateCount", "xsd:integer", "Replicates per arm."),
                    ("planCost", "xsd:integer", "Cost of a realisation (robot operations + wells)."),
                    ("scheduledAt_h", "xsd:double", "Scheduled culture time of a session (h)."),
                    ("stepIndex", "xsd:integer", "Position of a step in its sequence."),
                    ("estimatedDuration_s", "xsd:double", "Duration estimate from twin run traces (s)."),
                    ("primitiveName", "xsd:string", "Name of a motion / command primitive.")):
    P(n, kind="data", range_=rng, chars=["Functional"] if n in ("expectedGain_bits", "stepIndex") else [], doc=doc)

C("CompetingRecoveryModel", "ScientificModel", Some("predictsReadout", "MorphologyViabilityReadout"),
  doc="One of Cell 01's competing recovery models (mathematical-models.md §5), calibrated to the observed data.",
  src="✅")
P("predictsReadout", doc="A model predicts a readout.")
C("GradedRecoveryModel", "CompetingRecoveryModel", DSome("statementText", "xsd:string"),
  doc="M1: P_rec = σ(β0 − β1 I − β2 Δt + β3 d_r); no point of no return.", src="✅")
C("ThresholdRecoveryModel", "CompetingRecoveryModel", DSome("statementText", "xsd:string"),
  doc="M2: rescue fails once the cumulative injury burden B(Δt) ≥ B*.", src="✅")
C("ProtectiveThresholdModel", "CompetingRecoveryModel", DSome("statementText", "xsd:string"),
  doc="M3: B*(t) = B0* + α P(t): the threshold moves with adaptive protection.", src="✅")
D("GradedRecoveryModel", "ThresholdRecoveryModel", "ProtectiveThresholdModel")
C("InformationGainRequirement", "dul:Description", DSome("requiredGain_bits", "xsd:double"),
  doc="What an experiment must teach: a minimum expected information gain over the competing models.")
C("ExperimentCandidate", "ScientificProposal", Min(2, "discriminatesModel", "CompetingRecoveryModel"),
  DSome("expectedGain_bits", "xsd:double"), DSome("rescueDelay_h", "xsd:double"), DSome("doseAU", "xsd:double"),
  DSome("replicateCount", "xsd:integer"), DSome("planCost", "xsd:integer"),
  doc="A candidate delayed-rescue experiment (dose, rescue delay, replicates) with its EIG and cost.", src="✅")
C("InformationGainEstimate", "dul:InformationObject", Some("estimatesGainOf", "ExperimentCandidate"),
  Some("conditionedOnBelief", "CultureSDT"), DSome("expectedGain_bits", "xsd:double"),
  doc="EIG(a) = E_y KL(p(M|D,y,a) ‖ p(M|D)) (Cell 01 §10), by nested Monte Carlo over the calibrated models.",
  src="✅")
C("SelectedExperiment", "ExperimentCandidate", eq=And("ExperimentCandidate",
                                                      Some("selectedUnder", "InformationGainRequirement")),
  doc="Defined: the candidate chosen under a gain requirement (least cost among those meeting it).")
C("DelayedRescueStudyDesign", "StudyDesign", Some("hasArm", "ChallengeRescueArm"), Some("hasArm", "ChallengeOnlyArm"),
  Some("hasArm", "ControlArm"), DSome("rescueDelay_h", "xsd:double"),
  doc="A study design with a chosen rescue delay, comparator and untreated control.", src="✅")
C("ExperimentRealisationPlan", "ExperimentalProtocol", Some("realisesProposal", "SelectedExperiment"),
  Some("hasSession", "ProtocolSession"),
  doc="The derived protocol that realises a selected experiment in the lab: sessions of material, scene and "
      "motion designators.", src="✅")
C("ProtocolSession", "dul:Description", DSome("scheduledAt_h", "xsd:double"), Some("hasStep", "LabActionDesignator"),
  doc="One trip of the plate out of the incubator at a scheduled culture time.", src="✅")
C("LabActionDesignator", "ScientificActionDesignator", DSome("stepIndex", "xsd:integer"),
  doc="A designator of the realisation plan (RS ScientificActionDesignator).", src="✅")
C("MaterialStepDesignator", ["LabActionDesignator", "MaterialScientificDesignator"],
  Some("refinesInto", "SceneStepDesignator"), doc="What happens to the material: dose well w, image well w.",
  src="✅")
C("ChallengeDoseDesignator", "MaterialStepDesignator", DSome("doseAU", "xsd:double"), doc="Dose challenge.",
  src="✅")
C("RescueDoseDesignator", "MaterialStepDesignator", DSome("doseAU", "xsd:double"), doc="Dose rescue.", src="✅")
C("ImageWellDesignator", "MaterialStepDesignator", Some("concernsWell", "Well"), doc="Image a well.", src="✅")
C("SceneStepDesignator", ["LabActionDesignator", "SceneGroundedDesignator"], Some("boundToDevice", "LabArtifact"),
  doc="Bound to the scene: device, robot, poses.", src="✅")
C("PlateTransferDesignator", "SceneStepDesignator", Some("performedByRobot", "CellRobot"),
  Some("boundToPose", "PlateSeatPose"), Some("refinesInto", "MotionStepDesignator"),
  doc="Move the plate between two seat poses with one robot (one leg of a route).", src="✅")
C("DeviceOperationDesignator", "SceneStepDesignator", Some("boundToDevice", "LabAutomationDevice"),
  Some("refinesInto", "DeviceCommandDesignator"), doc="A device operation (dose, image, present, store).",
  src="✅")
C("MotionStepDesignator", ["LabActionDesignator", "BodyMotionDesignator"], Some("performedByRobot", "CellRobot"),
  DSome("primitiveName", "xsd:string"), DSome("estimatedDuration_s", "xsd:double"),
  doc="A robot body-motion primitive (RS BodyMotionDesignator) bound to a pose.", src="✅")
for mp, doc in (("ApproachMotion", "Move to the approach pose above a seat."),
                ("InsertMotion", "Descend to the seat pose (compliant)."),
                ("GraspMotion", "Close the gripper on the plate."),
                ("LiftMotion", "Lift the plate off the seat."),
                ("TransitMotion", "Planned joint-space / rail transit between approach poses."),
                ("PlaceMotion", "Compliant placement into the target seat."),
                ("ReleaseMotion", "Open the gripper."),
                ("RetractMotion", "Retract to the approach pose (leaves device airspace)."),
                ("ToolCoupleMotion", "Couple an exchangeable tool at the magazine.")):
    C(mp, "MotionStepDesignator", Some("boundToPose", "TwinPose"), doc=doc, src="✅")
C("DeviceCommandDesignator", ["LabActionDesignator", "ScientificActionDesignator"],
  Some("commandsDevice", "LabAutomationDevice"), DSome("primitiveName", "xsd:string"),
  doc="A device-level command (present, stow, tip pick, aspirate, dispense, eject, load, image, store, QC).",
  src="✅")
C("SafetyStepDesignator", "DeviceCommandDesignator", Some("dischargesRule", "LabSafetyRule"),
  doc="A step inserted to discharge a safety rule (environment wait, QC calibration, interlock check).", src="✅")
P("dischargesRule", doc="A step discharges (satisfies) a rule's precondition.")
C("PlanDerivation", "dul:Description", Some("derivesPlan", "ExperimentRealisationPlan"),
  Some("appliesAxiomSet", "DerivationAxiomSet"), doc="One run of the derivation (answer-set program over the "
                                                    "ontology's ABox and the EIG candidates).", src="✅")
C("DerivationAxiomSet", "dul:InformationObject", DSome("sourceDocument", "xsd:string"),
  doc="The L3 axioms E2M1-E2M8 (L3-logical-axiomatization/axioms/experiment-to-motion-axioms.md).", src="✅")
C("RealisedInformationGain", "dul:InformationObject", DSome("realisedGain_bits", "xsd:double"),
  Some("about", "ExperimentRealisationPlan"), doc="KL(p(M|D,y) ‖ p(M|D)) after executing the plan.", src="✅")
P("about", doc="An information object is about an entity (module-local, domain-free).")
D("MaterialStepDesignator", "SceneStepDesignator", "MotionStepDesignator", "DeviceCommandDesignator")

# =====================================================================================================================
module("lab-twin-rsa-kernel",
       "The robot science assistant kernel: action-designator categories, lifecycle and audit entries")
# =====================================================================================================================
# GENERATED from the kernel's own registry (LabAutomationTwin/rsa/registry/categories.yaml, constraints.yaml): one
# source for the executable kernel (rsa/) and its ontology. A category card becomes a designator class DEFINED by its
# level and its kernel category name (necessary and sufficient), so trail individuals are classified by the reasoner;
# its effect class (AICOR action-category partition) and facet (transport / operation / transformation) become
# superclasses; its okf_class aligns it with this module's designator classes (subclass) or LabAction classes
# (designatesAction). HermiT checks that the alignment is satisfiable under the level / effect / facet disjointness.
import os as _os  # noqa: E402

import yaml as _yaml  # noqa: E402

_REG = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", "rsa", "registry")
_CARDS = _yaml.safe_load(open(_os.path.join(_REG, "categories.yaml")))
_CONS = _yaml.safe_load(open(_os.path.join(_REG, "constraints.yaml")))


def _camel(s):
    return "".join(w[:1].upper() + w[1:] for w in s.replace("-", "_").split("_"))


P("designatesAction", doc="A designator designates an action of a type (CRAM: an action designator references an "
                          "action event type).")
P("kernelCategory", kind="data", range_="xsd:string",
  doc="A kernel category (registry card id) of a designator (not functional: a specialised category's designators "
      "also carry the general one).")
P("constrainsDesignator", doc="A kernel constraint applies to designators of a category.")
C("KernelScientificDesignator", "LabActionDesignator", Some("refinesInto", "LabActionDesignator"),
  doc="Scientific-level designator of the kernel (experiment, wait, intervene, measure; RS scientific actions); "
      "realised by lower-level designators.", src="✅")
C("KernelLabTaskDesignator", "LabActionDesignator", Some("refinesInto", "LabActionDesignator"),
  doc="Lab-task designator (Cell 01 CRAM designator schemas: retrieve, store, transport, dose, image, qc, "
      "quarantine).", src="✅")
C("KernelManipulationDesignator", "LabActionDesignator", Some("refinesInto", "LabActionDesignator"),
  doc="Manipulation-action designator (CRAM action categories: picking-up, placing, transporting, coupling, "
      "presenting, stowing).", src="✅")
D("KernelScientificDesignator", "KernelLabTaskDesignator", "KernelManipulationDesignator", "MotionStepDesignator",
  "DeviceCommandDesignator")
_EFFECTS = ["ObjectDisplacement", "ConfigurationChange", "SubstanceManipulation", "ConnectingAction", "Perception",
            "MaintenanceAction", "RegulationAction"]
for _e in _EFFECTS:
    C(f"{_e}Designator", "LabActionDesignator", Some("designatesAction", "LabAction"),
      doc=f"Designators of actions whose effect class is {_e} (AICOR action-category partition, CRAM "
          f"action-category-dl).", src="✅")
D(*[f"{_e}Designator" for _e in _EFFECTS])
_FACETS = dict(transport="TransportFacetDesignator", operation="OperationFacetDesignator",
               transformation="TransformationFacetDesignator")
for _f, _n in _FACETS.items():
    C(_n, "LabActionDesignator", Some("designatesAction", "LabAction"),
      doc=f"Designators of {_f} actions (GARMI three manipulation classes; orthogonal to the effect class).",
      src="🔧")
D(*_FACETS.values())
_LEVEL = dict(scientific="KernelScientificDesignator", lab_task="KernelLabTaskDesignator",
              manipulation="KernelManipulationDesignator", motion="MotionStepDesignator",
              command="DeviceCommandDesignator")
_DESIGNATOR_CLASSES = {"LabActionDesignator", "MaterialStepDesignator", "ChallengeDoseDesignator", "RescueDoseDesignator",
                       "ImageWellDesignator", "SceneStepDesignator", "PlateTransferDesignator",
                       "DeviceOperationDesignator", "MotionStepDesignator", "DeviceCommandDesignator",
                       "SafetyStepDesignator", "ApproachMotion", "InsertMotion", "GraspMotion", "LiftMotion",
                       "TransitMotion", "PlaceMotion", "ReleaseMotion", "RetractMotion", "ToolCoupleMotion"}
_EXISTING_MOTIONS = {"ApproachMotion", "InsertMotion", "GraspMotion", "LiftMotion", "TransitMotion", "PlaceMotion",
                     "ReleaseMotion", "RetractMotion", "ToolCoupleMotion"}
RSA_CLASS = {}
for _cid, _c in _CARDS.items():
    _ok = _c.get("okf_class")
    RSA_CLASS[_cid] = _ok if (_c["level"] == "motion" and _ok in _EXISTING_MOTIONS) else \
        _camel(_cid) + ("Command" if _c["level"] == "command" else "Motion" if _c["level"] == "motion" else "Designator")
for _cid, _c in _CARDS.items():
    _n = RSA_CLASS[_cid]
    _lvl = _LEVEL[_c["level"]]
    if _n in _EXISTING_MOTIONS:
        continue
    _sup = [_lvl]
    if _c.get("parent") and _c["parent"] in RSA_CLASS:      # specialisation (⊑) within the kernel
        _sup.append(RSA_CLASS[_c["parent"]])
    if _c.get("effect_class"):
        _sup.append(f"{_c['effect_class']}Designator")
    if _c.get("facet"):
        _sup.append(_FACETS[_c["facet"]])
    _ax = []
    _ok = _c.get("okf_class")
    if _ok in _DESIGNATOR_CLASSES:
        _sup.append(_ok)
    elif _ok:
        _ax.append(Some("designatesAction", _ok))
    if _c.get("realised_by"):
        _ax.append(Some("refinesInto", RSA_CLASS[_c["realised_by"]]))
    for _part in _c.get("parts", []) or []:                  # partonomy (◁): realised through its phases
        _ax.append(Some("refinesInto", RSA_CLASS[_part]))
    C(_n, list(dict.fromkeys(_sup)), *_ax, eq=And(_lvl, DValue("kernelCategory", _cid, "xsd:string")),
      doc=f"Kernel category '{_cid}': {_c.get('label', '')}. HADL: {_c.get('hadl', '-')}. Sources: "
          f"{', '.join(_c.get('sources', []) or ['kernel registry'])}.", src="✅" if _c.get("sources") else "🔧")

# ---- lifecycle and audit entries (the audit trail as knowledge)
P("recordsDesignator", doc="An audit entry is about one designator (one lifecycle transition of it).")
P("hasTransition", doc="An audit entry records a lifecycle transition.")
P("checksConstraint", doc="An audit entry carries a verdict on a registry constraint.")
P("violatesConstraint", sup=["checksConstraint"], doc="An audit entry records a VIOLATED verdict on a constraint.")
P("chainedAfter", chars=["Functional"], doc="An audit entry is hash-chained after its predecessor.")
P("carriesEvidence", doc="An audit entry carries a content-hashed evidence item.")
for _n_, _rng, _doc in (("recordSeq", "xsd:integer", "Position of the entry in the trail."),
                        ("chainHash", "xsd:string", "SHA-256 over the previous hash and the entry's canonical JSON."),
                        ("simTime_s", "xsd:double", "Simulated time of the entry (s)."),
                        ("evidenceSha256", "xsd:string", "Content hash of an evidence item.")):
    P(_n_, kind="data", range_=_rng, chars=["Functional"], doc=_doc)
C("DesignatorLifecycleState", "dul:Concept", DSome("statementText", "xsd:string"),
  doc="Cell 01 designator lifecycle: open, grounded, accepted, executing, executed, failed, repaired, abstained, "
      "escalated (+ repairing, replanned, policy_violation as executor events).", src="✅")
for _s in ("open", "grounded", "accepted", "executing", "executed", "failed", "repaired", "abstained", "escalated",
           "repairing", "replanned", "policy_violation"):
    I(f"lifecycle_{_s}", "DesignatorLifecycleState")
C("KernelConstraint", "dul:Description", DSome("sourceDocument", "xsd:string"),
  Some("constrainsDesignator", "LabActionDesignator"),
  doc="A constraint of the kernel registry, checked at acceptance, after execution, as a policy, or by the "
      "experimental critic.", src="✅")
C("RealizationConstraint", "KernelConstraint", Some("constrainsDesignator", "LabActionDesignator"),
  doc="Did it run correctly and safely (uc_ccr realization column).", src="✅")
D("RealizationConstraint", "ValidityConstraint")
for _k, _c in _CONS.items():
    I(f"constraint_{_k}", "RealizationConstraint" if _c.get("column") == "realization" else "ValidityConstraint")
C("EvidenceItem", "dul:InformationObject", DSome("evidenceSha256", "xsd:string"),
  doc="An observation, reading or record attached to an audit entry, content-hashed.", src="✅")
C("CommitmentAuditEntry", "LabExecutionTrace", Some("recordsDesignator", "LabActionDesignator"),
  Some("hasTransition", "DesignatorLifecycleState"), DSome("recordSeq", "xsd:integer"), DSome("chainHash", "xsd:string"),
  doc="One hash-chained audit entry per designator lifecycle transition (uc_ccr audit.py + Cell 01 NEEM record "
      "sections + VRB warrant entry ⟨grounds, constraints discharged, verdict, disposition⟩). Not AICOR's "
      "CommitmentRecord (an episode-level Description containing action tokens and episodes; D-LAT-11).", src="✅")
C("ViolationAuditEntry", "CommitmentAuditEntry", eq=And("CommitmentAuditEntry", Some("violatesConstraint",
                                                                                     "KernelConstraint")),
  doc="Defined: an audit entry that records a violated constraint.", src="✅")
