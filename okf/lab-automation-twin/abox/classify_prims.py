"""Prim classification for the SDT -> ABox mapping (shared by sdt_abox.py). Originally:
SDT -> ABox: every semantic node of the semantic digital twin becomes an individual of the AICOR lab ontology.

Input  the composed SDT: scenes/lab_site.usda (lab) + scenes/culture/<scenario>/culture_sdt.usda (culture SDT layer,
       which sublayers scenes/cell01_twin.usda), and the Cell 01 episode records (test_reports/episodes/).
Output ontology/abox/lab1_sdt.ofn       ABox (imports the TBox), one individual per SDT node (IRI = prim path)
       ontology/abox/mapping_report.json  per-class counts, every node's classes, unmapped / representation nodes
       scenes/sdt_ontology.usda           USD layer typing the SDT nodes in place: ont:iri, ont:types (and, after
                                          reasoning, ont:inferredTypes - written by check_ontology.py)
Node kinds: physical artifacts / agents / places / portions of matter are the twin's individuals for those things
(SOMA USD ontology: a usd:Prim is a dul:Object); frames are soma:Feature; grouping nodes are dul:Collection; the
culture SDT's belief / observation / intervention / claim nodes are information objects ABOUT the culture.
Render-only nodes (Looks, materials, shaders, collision and visual geometry) are representation, not SDT knowledge:
they are counted, not instantiated.
Run: env_cad/bin/python ontology/sdt_to_abox.py [--scenario contamination]
"""

import argparse
import collections
import json
import os
import re
import sys

from pxr import Sdf, Usd, UsdPhysics

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


BASE = "https://aicor.example/okf/sdt/lab1"
LAB = "/World/AICOR_Lab"
C01 = "/World/Cell01"
REPRESENTATION = {"Looks", "Visual", "Collision", "Collisions", "PhysicsMaterials", "Materials", "Render", "Meshes",
                  "Geom", "Textures"}
REPRESENTATION_PATHS = {"/World/ExperimentalWorld/Plates/Plate_P17/Physical"}    # geometry-only grouping nodes
GPRIMS = {"Mesh", "Cube", "Cylinder", "Sphere", "Capsule", "Cone", "Plane", "Points", "GeomSubset", "Shader",
          "Material", "NodeGraph"}

SITE_CLASS = {
    "sprinkler_head": "SprinklerHead", "hvac_swirl_diffuser": "HVACDiffuser", "smoke_detector": "SmokeDetector",
    "lab_stool": "LabStool", "storage_shelving": "StorageShelving", "fire_extinguisher": "FireExtinguisher",
    "lab_refrigerator": "LabRefrigerator", "glove_dispenser": "GloveDispenser", "lab_sink_unit": "LabSinkUnit",
    "first_aid_box": "FirstAidBox", "potted_plant": "PottedPlant", "operator_desk": "OperatorWorkstation",
    "biosafety_cabinet_class_II": "BiosafetyCabinet", "ult_freezer": "ULTFreezer", "lab_freezer": "LabFreezer",
    "gas_cylinder_cabinet": "GasCylinderCabinet", "ln2_dewar": "CryogenicStorage", "amr_dispatch_bench":
    "AMRDispatchBench", "o2_depletion_monitor": "O2DepletionMonitor", "access_control_reader": "AccessControlReader",
    "lab_coat_rack": "LabCoatRack", "server_rack": "ServerRack", "co2_incubator_stack": "ManualIncubator",
    "lab_bench_island": "LabBench", "lab_bench_wall": "LabBench", "inverted_microscope": "InvertedMicroscope",
    "benchtop_centrifuge": "Centrifuge", "water_bath": "WaterBath", "pipette_carousel": "PipetteCarousel",
    "emergency_shower": "EmergencyShower", "whiteboard": "Whiteboard", "laboratory_autoclave": "Autoclave",
    "waste_station": "WasteStation"}
CAP_TOKENS = {
    "navigate": "NavigationCapability", "transport_clean_sample": "SampleTransportCapability",
    "dock_precisely": "DockingCapability", "handover_carrier": "PlateTransferCapability",
    "buffer_plate": "PlateStorageCapability", "store_plate": "PlateStorageCapability",
    "retrieve_plate": "PlateStorageCapability", "report_inventory": "PlateStorageCapability",
    "reserve_slot": "PlateStorageCapability", "release_plate": "PlateStorageCapability",
    "verify_identity": "IdentificationCapability", "incubate_plate": "IncubationCapability",
    "maintain_environment": "IncubationCapability", "report_environment": "IncubationCapability",
    "raise_excursion_alarm": "IncubationCapability", "pick_tip": "LiquidDispensingCapability",
    "eject_tip": "LiquidDispensingCapability", "detect_liquid_surface": "LiquidDispensingCapability",
    "aspirate": "LiquidDispensingCapability", "dispense": "LiquidDispensingCapability",
    "mix": "LiquidDispensingCapability", "dose_well": "LiquidDispensingCapability", "load_plate": "ImagingCapability",
    "autofocus": "ImagingCapability", "image_well": "ImagingCapability", "image_plate_region": "ImagingCapability",
    "compute_focus_quality": "ImagingCapability", "export_raw_image": "ImagingCapability",
    "run_reference_measurement": "CalibrationCapability", "validate_imager": "CalibrationCapability",
    "validate_barcode": "CalibrationCapability", "validate_tool_frame": "CalibrationCapability",
    "isolate_sample": "QuarantineCapability", "retain_invalid_run": "QuarantineCapability",
    "prevent_reentry": "QuarantineCapability", "release_by_authorization": "QuarantineCapability"}
STEP_TASK = {"Retrieve": "PlateRetrieving", "Identify": "Identifying", "Transport": "PlateTransfer",
             "Challenge": "ChallengeDosing", "Incubate": "Incubating", "Rescue": "RescueDosing", "Image": "Imaging",
             "Classify": "Classifying", "Log": "Logging", "Return": "PlateStoring"}
TOOLS = {"T01": "PlateGripperTool", "T02": "TubeGripperTool", "T03": "PipettingTool", "T04": "SuctionPickupTool",
         "T05": "CameraInspectionTool"}
STATIONS = {"L09_PlateHotel": "PlateHotel", "L10_Incubator": "AutomatedIncubator", "L12_LiquidHandler": "LiquidHandler",
            "L17_BrightFieldImager": "BrightFieldImager", "L21_QC_Calibration": "QCCalibrationStation",
            "H4_Quarantine": "QuarantineStation", "H2_AMR_Dock": "AMRDock"}
# robot <-> station assignments of layout P1 (D017, proposals/cell01/README.md)
SERVES = {"R01_FR3": ["H4_Quarantine", "L09_PlateHotel", "L10_Incubator", "H2_AMR_Dock", "HandoverNest_R01_R02"],
          "R02_RailSystem": ["HandoverNest_R01_R02", "L12_LiquidHandler", "L17_BrightFieldImager",
                             "L21_QC_Calibration", "AutomaticToolChanger"]}
# two SDT nodes for one physical thing: Cell 01's semantic node and the fit-out / asset node
SAME_AS = [(f"{C01}/Furniture/AutomationBench", f"{C01}/Furniture/FitOut/F01_Bench"),
           (f"{C01}/Robots/ToolMagazine", f"{C01}/Tooling/AutomaticToolChanger")] + \
          [(f"{C01}/Furniture/P1_Supports/{a}", f"{C01}/Furniture/FitOut/{b}") for a, b in (
              ("L10_plinth", "L10_support"), ("L09_side_table", "L09_support"), ("H4_side_table", "H4_support"),
              ("L17_plinth", "L17_support"), ("L21_side_table", "L21_support"))] + \
          [(f"{C01}/Architecture/SafetyEnclosure", f"{C01}/Architecture/Enclosure_E01")] + \
          [(f"{LAB}/Zones/{a}", f"{LAB}/{b}") for a, b in (
              ("StorageRoom_ST01", "StorageRoom"), ("EntranceGowning", "Entrance"), ("OperatorArea", "OperatorArea"),
              ("CulturePrep", "CulturePrep"), ("WashWaste", "WashWaste"))] + \
          [(f"{C01}/Robots/ToolMagazine/{a}", f"{C01}/Tooling/AutomaticToolChanger/Tools/{a[:3]}") for a in (
              "T01_PlateGripper", "T02_TubeGripper", "T03_PipettingTool", "T04_SuctionPickup", "T05_CameraInspect")]

ROLE_PHYS, ROLE_PLACE, ROLE_FRAME, ROLE_JOINT, ROLE_COLL, ROLE_INFO, ROLE_TASK, ROLE_LINK, ROLE_MATTER = (
    "physical", "place", "frame", "joint", "collection", "info", "task", "link", "matter")


def frame_class(name, role_txt):
    n = name.lower()
    t = (role_txt or "").lower()
    if "approach" in n:
        return "ApproachFrame"
    if n in ("dock_frame",):
        return "DockFrame"
    if "coupl" in n or n.startswith("dock_t"):
        return "ToolCouplingFrame"
    if n in ("tcp", "tool0", "flange", "plate_grasp_frame", "pipette_tip_frame"):
        return "ToolCenterPointFrame"
    if "pipette_target" in n:
        return "PipettingTargetFrame"
    if "imaging_target" in n:
        return "ImagingTargetFrame"
    if "illumination" in n:
        return "IlluminationFrame"
    if "calibration" in n:
        return "CalibrationFrame"
    if any(k in n for k in ("camera", "objective", "focal")):
        return "OpticalFrame"
    if n == "carrier_cabinet":
        return "KinematicFrame"
    if "waste" in n:
        return "WasteFrame"
    if n.startswith(("rack_", "pos_")) or "rack_frame" in n:
        return "RackPositionFrame"
    if any(k in n for k in ("seat", "nest", "handover", "transfer", "load_frame", "plate_stage", "plate_load",
                            "experiment_plate", "reference_plate_frame", "carrier")) or "plate seat" in t:
        return "PlateSeatFrame"
    return "KinematicFrame"


def sensor_class(name, path):
    n = name.lower()
    if "carrier_seat_sensor" in n:
        return "CarrierPresenceSensor"
    if "seat_sensor" in n:
        return "SeatSensor"
    if "occupancy" in n:
        return "SlotOccupancySensor"
    if n.startswith("sensor_") and "H2_AMR_Dock" in path:
        return "DockSensor"
    if "reader" in n:
        return "BarcodeReader"
    if n.startswith("beam_") and "L21" in path:
        return "LightBarrierSensor"
    if n.startswith("beam"):
        return "ThroughBeamSensor"
    return None


def classify(p):
    """-> (classes, role) or None (not an SDT knowledge node)."""
    path, name, typ = str(p.GetPath()), p.GetName(), p.GetTypeName()
    parts = path.split("/")
    attr = lambda k: p.GetAttribute(k).Get() if p.GetAttribute(k) and p.GetAttribute(k).HasAuthoredValue() else None  # noqa
    fr = attr("sdt:frameRole")
    if set(parts) & REPRESENTATION or typ in GPRIMS:
        return None
    if typ.startswith("Physics") and typ.endswith("Joint"):
        k = {"PhysicsFixedJoint": "soma:FixedJoint", "PhysicsPrismaticJoint": "soma:PrismaticJoint",
             "PhysicsRevoluteJoint": "soma:RevoluteJoint"}.get(typ, "soma:MovableJoint")
        cls = [k]
        if k != "soma:FixedJoint" and (p.HasAPI(UsdPhysics.DriveAPI, "linear") or p.HasAPI(UsdPhysics.DriveAPI, "angular")):
            cls.append("DrivenJoint")
        return cls, ROLE_JOINT
    if path in REPRESENTATION_PATHS:
        return None
    if path == "/World/Experiment/Events":
        return ["SDTCollection"], ROLE_COLL
    if path == f"{C01}/Architecture/SafetyEnclosure":
        return ["SafetyEnclosure"], ROLE_PHYS
    if typ in ("PhysicsScene", "DomeLight", "DistantLight"):
        return ["SimulationSettings"], ROLE_INFO
    if typ == "RectLight" and "/Lights/" in path:
        return ["CeilingLuminaire"], ROLE_PHYS
    if typ == "Camera":
        return ["ViewpointFrame"], ROLE_FRAME
    if typ == "BasisCurves":
        return (["AMRRoute"], ROLE_FRAME) if "AmrRoute" in name else None
    # ---- culture SDT (information about the culture)
    if "/Wells/" in path:
        rel = path.split("/Wells/")[1].split("/")
        if len(rel) == 1:
            return ["Well", "bio:CultureWell"], ROLE_PHYS
        if rel[1] == "Physical":
            if len(rel) == 2:
                return ["SDTCollection"], ROLE_COLL
            return (["CultureMediumPortion", "bio:CultureMedium"], ROLE_MATTER) if rel[2] == "Medium" else \
                (["Organoid", "bio:Organoid"], ROLE_MATTER) if rel[2] == "Organoid" else None
        if rel[1] == "Interfaces":
            return (["WellInterfaceSet"], ROLE_COLL) if len(rel) == 2 else ([frame_class(rel[2], fr)], ROLE_FRAME)
        if rel[1] == "Biological":
            if len(rel) == 2:
                return ["WellBiologyRecord"], ROLE_INFO
            if rel[2] == "LatentState":
                return ["WellBeliefRecord"], ROLE_INFO
            if rel[2] == "QualityAndUncertainty":
                return ["QualityAssessmentRecord"], ROLE_INFO
            if rel[2] in ("InterventionHistory", "ObservationState"):
                return (["SDTCollection"], ROLE_COLL) if len(rel) == 3 else (
                    (["InterventionRecord"], ROLE_INFO) if rel[2] == "InterventionHistory" else
                    (["WellObservationRecord"], ROLE_INFO))
        return None
    if re.match(r".*/Evidence/Culture/[^/]+/Claim_\d+$", path):
        return ["ClaimNode"], ROLE_INFO
    if path.startswith("/World/ProcessModels/") and len(parts) == 5:
        return (["bio:ObservationModel"] if "ObservationModels" in path else ["bio:ScientificModel"]), ROLE_INFO
    if path.startswith("/World/ProcessModels"):
        return ["ProcessModelCollection"], ROLE_COLL
    if path.startswith("/World/Experiment/Workflow/Step"):
        return [STEP_TASK[name.split("_", 1)[1]]], ROLE_TASK
    if path == "/World/Experiment/Workflow":
        return ["ExperimentWorkflow"], ROLE_INFO
    if path.startswith("/World/Evidence"):
        return (["CultureSDTLedger"] if name == "Culture" else ["EvidenceLayer"]), ROLE_COLL
    if path.startswith("/World/ExperimentalWorld/Reagents/"):
        return ["Reagent", "bio:Reagent"], ROLE_MATTER
    if re.match(r"/World/ExperimentalWorld/Plates/Plate_\w+$", path):
        return ["SBSMicroplate96", "CulturePlate", "bio:CulturePlate"], ROLE_PHYS
    # ---- lab site
    if path == LAB:
        return ["Laboratory"], ROLE_PLACE
    if path == f"{LAB}/Building":
        return ["LabBuildingShell"], ROLE_PHYS
    zones = {"StorageRoom": "StorageRoom", "Entrance": "EntranceZone", "OperatorArea": "OperatorArea",
             "CulturePrep": "CulturePrepArea", "WashWaste": "WashWasteArea", "Ceiling": "LabCeiling"}
    if len(parts) == 4 and path.startswith(LAB) and name in zones:
        return [zones[name]], ROLE_PLACE
    zone_nodes = {"Cell01": "CellZone", "RearServiceCorridor": "ServiceCorridor", "FrontLogistics": "LogisticsArea",
                  "StorageRoom_ST01": "StorageRoom", "EntranceGowning": "EntranceZone", "OperatorArea": "OperatorArea",
                  "CulturePrep": "CulturePrepArea", "WashWaste": "WashWasteArea"}
    if path.startswith(f"{LAB}/Zones/") and name in zone_nodes:
        return [zone_nodes[name]], ROLE_PLACE
    if path.startswith(LAB) and len(parts) == 6 and parts[3] not in ("Building", "Zones"):     # equipment frames
        nm = re.sub(r"\d+", "#", name)
        for keys, c in ((("loc_",), "StorageLocationFrame"),
                        (("handle", "door", "lid", "sash", "button", "tap"), "ManipulationPointFrame"),
                        (("operator_position", "seat", "work_", "keyboard", "screens", "eyepieces", "display"),
                         "OperatorPositionFrame"),
                        (("hook_", "glove_", "pick", "marker_tray", "shelf", "top", "drop_point", "sharps"),
                         "ItemAccessFrame"),
                        (("sink", "eyewash"), "CleaningPointFrame"),
                        (("staging_nest", "stage"), "PlateSeatFrame")):
            if nm.startswith(keys):
                return [c], ROLE_FRAME
    if attr("sdt:class") in SITE_CLASS:
        return [SITE_CLASS[attr("sdt:class")]], ROLE_PHYS
    if name == "S1_DispatchDock":
        return ["DispatchDock"], ROLE_PHYS
    if path.startswith(f"{LAB}/Building/") and len(parts) == 5 and name.endswith(("door", "entrance")):
        return (["SlidingDoor"] if name == "store_door" else ["HingedDoor"]), ROLE_PHYS
    # ---- cell
    if path == C01:
        return ["RobotExperimentCell"], ROLE_PHYS
    if path == f"{C01}/Architecture/Floor":
        return ["soma:Floor"], ROLE_PHYS
    if path == f"{C01}/Architecture/Enclosure_E01":
        return ["SafetyEnclosure"], ROLE_PHYS
    if re.match(rf"{C01}/Architecture/Enclosure_E01/Doors/D\d_\w+$", path):
        return ["HingedDoor", "InterlockedDoor"], ROLE_PHYS
    if name == "Leaf":
        return ["DoorLeaf"], ROLE_PHYS
    if name == "Frame" and "/Doors/" in path:
        return ["DoorFrame"], ROLE_PHYS
    if name.startswith("estop"):
        return ["EmergencyStop"], ROLE_PHYS
    if name == "hmi":
        return ["HMIPanel"], ROLE_PHYS
    if name == "amr_portal":
        return ["AMRPortal"], ROLE_PHYS
    if path in (f"{C01}/Furniture/AutomationBench", f"{C01}/Furniture/FitOut/F01_Bench"):
        return ["AutomationBench"], ROLE_PHYS
    if path == f"{C01}/Furniture/FitOut":
        return ["FitOutAssembly"], ROLE_PHYS
    if re.match(rf"{C01}/Furniture/(P1_Supports|FitOut)/\w+_(plinth|side_table|support)$", path):
        return (["VibrationIsolatedSupport"] if "L17" in name else ["StationSupport"]), ROLE_PHYS
    if name == "R02_RailCover":
        return ["RailCover"], ROLE_PHYS
    if path == f"{C01}/Robots/R01_FR3":
        return ["FixedBaseManipulator"], ROLE_PHYS
    if path == f"{C01}/Robots/R02_RailSystem":
        return ["RailMountedManipulator"], ROLE_PHYS
    if path == f"{C01}/Robots/R03_SampleAMR":
        return ["SampleTransportAMR"], ROLE_PHYS
    if name == "LinearRail":
        return ["LinearRail"], ROLE_PHYS
    if name == "RailCarriage":
        return ["RailCarriage"], ROLE_PHYS
    if name == "AutomaticToolChanger" and "R02" in path:
        return ["AutomaticToolChanger"], ROLE_PHYS
    if path in (f"{C01}/Tooling/AutomaticToolChanger", f"{C01}/Robots/ToolMagazine"):
        return ["ToolMagazine"], ROLE_PHYS
    if name == "Stand" and "Tooling" in path:
        return ["MagazineStand"], ROLE_PHYS
    m = re.match(r"(T0\d)(_\w+)?$", name)
    if m and ("/Tools/" in path or "/ToolMagazine/" in path):
        return [TOOLS[m.group(1)]], ROLE_PHYS
    if name == "Body" and "/Tools/" in path:
        return ["ToolBody"], ROLE_PHYS
    if name.startswith("Finger"):
        return ["GripperJaw"], ROLE_PHYS
    if name in ("Anchor", "PlanarX", "PlanarY"):
        return ["MechanicalLink"], ROLE_LINK
    if name == "BaseLink":
        return ["MobileBase"], ROLE_PHYS
    if name == "Lid" and "R03" in path:
        return ["CabinetLid"], ROLE_PHYS
    if len(parts) == 5 and parts[3] == "Stations" and name in STATIONS:
        return [STATIONS[name]], ROLE_PHYS
    if name == "HandoverNest_R01_R02":
        return ["HandoverNest"], ROLE_PHYS
    if path.startswith(f"{C01}/Stations/") or path.startswith(f"{C01}/Fixtures/"):
        st = parts[4] if len(parts) > 4 else ""
        if name == "Body":
            return (["IncubationChamber"] if st == "L10_Incubator" else ["StationHousing"]), ROLE_PHYS
        simple = {"Gate": "AccessGate", "Shuttle": "PlateShuttle", "Lift": "InternalPlateHandler", "Fork": "PlateFork",
                  "ServiceDoor": "ServiceDoor", "GantryX": "GantryAxis", "GantryY": "GantryAxis",
                  "ChannelZ": "PipettingChannel", "StageY": "MotorizedStage", "StageX": "MotorizedStage",
                  "Focus": "FocusDrive", "Turret": "ObjectiveTurret", "Door": "LockableDoor", "LatchBolt": "LatchBolt",
                  "DoorButton": "PushButton", "Plunger": "ButtonPlunger", "KeySwitch": "KeySwitch",
                  "KeyCylinder": "KeyCylinder", "Enclosure": "StationHood", "registration_tag": "AprilTagMarker",
                  "registration_datum": "DatumPin", "slot_frames": "PlateCassette", "cassette_slots": "PlateCassette"}
        if name in simple and "/Joints/" not in path:
            return [simple[name]], ROLE_PHYS
        if re.match(r"slot_\d+$", name):
            return ["PlateSlot"], ROLE_PHYS
    sc = sensor_class(name, path)
    if sc and (fr or "sensor" in name or "reader" in name or name.startswith("beam")):
        return [sc], ROLE_PHYS
    if fr is not None or name.endswith(("_frame", "_link", "_approach")) or name in (
            "tool0", "flange", "tcp", "base_link", "rail_base", "rail_carriage", "magazine_approach", "focal_point",
            "plate_seat", "plate_stage", "transfer_nest", "transfer_station", "quarantine_nest", "nest_seat",
            "dock_approach", "carrier_cabinet", "load_frame", "plate_nest", "barcode_reader", "AMR_dock_carrier",
            "handover_nest_R01_R02", "tool_coupler", "robot_coupler") or re.match(r"(rack|pos)_\d+$", name):
        return [frame_class(name, fr)], ROLE_FRAME
    return None


def iri(path):
    return f"{BASE}{path}"


