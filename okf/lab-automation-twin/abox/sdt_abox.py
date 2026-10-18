"""SDT -> ABox in AICOR terms: every SDT node (USD prim) is a LabSDTNode that representsEntity its referent.

Input   scenes/lab_site.usda + scenes/culture/<scenario>/culture_sdt.usda (which sublayers scenes/cell01_twin.usda),
        test_reports/episodes/cell01_episodes_records.json
Output  abox/sdt.ofn        nodes, referents, partonomy, location, containment, poses, joints, capabilities,
                            culture SDT (belief, observations, interventions, quality, conclusions), the twin itself
        abox/records.ofn    Cell 01 action records, actions, monitors, routing, episodes
        abox/sdt_mapping.json
        scenes/sdt_ontology.usda   ont:node, ont:referent, ont:types on every SDT node (inferred types added by the check)
Run: env_cad/bin/python okf/lab-automation-twin/abox/sdt_abox.py [--scenario contamination]
"""

import argparse
import collections
import json
import os
import re
import sys

from pxr import Sdf, Usd, UsdPhysics

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(MOD))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(MOD, "src"))
import classify_prims as cp  # noqa: E402
from dl import PREFIXES  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--scenario", default="contamination", choices=("nominal", "underdose", "contamination"))
args = ap.parse_args()

BASE, LAB, C01 = cp.BASE, cp.LAB, cp.C01
MANUALS = "https://aicor.example/okf/lab1/manuals"
T = {   # classifier names (first ontology version) -> AICOR module names
    "Laboratory": "AutomatedBiologyLab", "PlateHotel": "AutomatedPlateHotel", "AutomatedIncubator": "AutomatedCO2Incubator",
    "LiquidHandler": "AutomatedLiquidHandler", "AMRDock": "DeterministicAMRDock", "MechanicalLink": "VirtualPlanarLink",
    "MobileBase": "MobileRobotBase", "CryogenicStorage": "CryogenicDewar", "ManualIncubator": "ManualCO2Incubator",
    "Organoid": "WellOrganoid", "bio:Organoid": None, "bio:CultureMedium": None, "bio:CultureWell": None,
    "bio:CulturePlate": None, "bio:Reagent": None, "usd:Prim": None, "soma:Floor": None,
    "WellBiologyRecord": None, "WellBeliefRecord": "WellBeliefEstimate", "QualityAssessmentRecord": "WellQualityRecord",
    "ClaimNode": "RescueComparisonConclusion", "bio:ScientificModel": "ScientificModel",
    "bio:ObservationModel": "ScientificModel", "ExperimentWorkflow": "ExperimentalWorkflow", "DrivenJoint": None,
    "soma:FixedJoint": "MechanismJoint", "soma:PrismaticJoint": "MechanismJoint", "soma:RevoluteJoint": "MechanismJoint",
    "soma:MovableJoint": "MechanismJoint", "Reagent": "ReagentPortion", "WellInterfaceSet": None,
    **{k: k.replace("Frame", "Pose") for k in (
        "PlateSeatFrame", "ApproachFrame", "DockFrame", "ToolCenterPointFrame", "ToolCouplingFrame",
        "PipettingTargetFrame", "ImagingTargetFrame", "IlluminationFrame", "OpticalFrame", "CalibrationFrame",
        "WasteFrame", "RackPositionFrame", "KinematicFrame", "ViewpointFrame", "StorageLocationFrame",
        "ManipulationPointFrame", "OperatorPositionFrame", "ItemAccessFrame", "CleaningPointFrame")},
}
T["ToolCenterPointFrame"] = "ToolCenterPose"
JOINT_KIND = {"PhysicsFixedJoint": "Fixed", "PhysicsPrismaticJoint": "Prismatic", "PhysicsRevoluteJoint": "Revolute"}
STEP = {"PlateRetrieving": "PlateRetrievingTask", "Identifying": "IdentifyingTask", "PlateTransfer": "PlateTransferTask",
        "ChallengeDosing": "ChallengeDosingTask", "Incubating": "IncubatingTask", "RescueDosing": "RescueDosingTask",
        "Imaging": "ImagingTask", "Classifying": "CalibratingTask", "Logging": "CalibratingTask",
        "PlateStoring": "PlateStoringTask"}
CAPS = {"PlateStorageCapability": "PlateStorageFunction", "IdentificationCapability": "IdentificationFunction",
        "IncubationCapability": "IncubationFunction", "LiquidDispensingCapability": "DispensingFunction",
        "ImagingCapability": "ImagingFunction", "CalibrationCapability": "CalibrationFunction",
        "QuarantineCapability": "QuarantineFunction", "NavigationCapability": "NavigationSkill",
        "SampleTransportCapability": "SampleTransportSkill", "DockingCapability": "DockingSkill",
        "PlateTransferCapability": "PlateTransferSkill"}
ROBOTS = ("R01_FR3", "R02_RailSystem", "R03_SampleAMR")
T.update(STEP)

# ------------------------------------------------------------------------------------------------ compose the SDT
culture = os.path.join(REPO, "scenes", "culture", args.scenario, "culture_sdt.usda")
layer = Sdf.Layer.CreateAnonymous("sdt_composed.usda")
layer.subLayerPaths = [culture, os.path.join(REPO, "scenes", "lab_site.usda")]
stage = Usd.Stage.Open(layer)

nodes, n_render = {}, 0
for p in stage.Traverse():
    path = str(p.GetPath())
    if path in cp.REPRESENTATION_PATHS:
        n_render += 1
        continue
    c = cp.classify(p)
    mm = re.search(r"/Wells/[A-H]\d\d/Physical/(Medium|Organoid)$", path)
    if mm:                        # semantic material nodes that happen to be USD shapes (sdt:materialRole / renderRole)
        c = (["CultureMediumPortion"] if mm.group(1) == "Medium" else ["WellOrganoid"]), cp.ROLE_MATTER
    if c is None:
        if set(path.split("/")) & cp.REPRESENTATION or p.GetTypeName() in cp.GPRIMS:
            n_render += 1
            continue
        nodes[path] = dict(classes=[], role="group", prim=p)      # provisional: grouping or unmapped
        continue
    cls = [T.get(x, x) for x in c[0]]
    cls = [x for x in cls if x]
    role = c[1]
    if role == cp.ROLE_COLL or not cls:
        role, cls = "group", []
    nodes[path] = dict(classes=cls, role=role, prim=p)
nodes[LAB]["role"] = "site"          # the lab node is the site (a body-world system), not a place
# a provisional group node is a grouping node only if it has descendants that are SDT nodes; else it is unmapped
unmapped = []
for path, n in list(nodes.items()):
    if n["role"] == "group" and not any(q.startswith(path + "/") for q in nodes):
        if path.endswith("_frames") or path.startswith(("/World/Experiment/", "/World/Evidence/")) or \
                re.search(r"/Wells/[A-H]\d\d/(Biological/\w+|Physical)$", path):
            continue                       # Cell 01 schema groups, empty in this run: kept as grouping nodes
        unmapped.append(path)
        del nodes[path]
# cell floor slab and other geometry-only prims are representation
for path in list(nodes):
    if nodes[path]["prim"].GetTypeName() in cp.GPRIMS and nodes[path]["role"] != cp.ROLE_MATTER:
        del nodes[path]
        n_render += 1


def node(path):
    return f"{BASE}{path}"


def ref(path):
    return f"{BASE}{path}#entity"


A, types, facts = [], collections.defaultdict(list), collections.Counter()
declared = set()


def decl(i):
    if i not in declared:
        declared.add(i)
        A.append(f"Declaration(NamedIndividual(<{i}>))")


def cq(c):
    return c if ":" in c and not c.startswith(("dul:", "soma:")) else (f":{c.replace(':', '_')}")


def Ty(i, c):
    decl(i)
    A.append(f"ClassAssertion({cq(c)} <{i}>)")
    types[i].append(c)


def R(p, a, b):
    decl(a)
    decl(b)
    A.append(f"ObjectPropertyAssertion({cq(p)} <{a}> <{b}>)")
    facts[p] += 1


def Dv(p, a, v, dt):
    if v is None or (isinstance(v, float) and v != v):
        return
    decl(a)
    if dt == "xsd:boolean":
        v = "true" if v else "false"
    A.append(f'DataPropertyAssertion({cq(p)} <{a}> "{str(v).replace(chr(34), chr(39))}"^^{dt})')


def parent(path, skip=("group", cp.ROLE_LINK, cp.ROLE_FRAME, cp.ROLE_INFO, cp.ROLE_TASK)):
    q = path.rsplit("/", 1)[0]
    while q:
        if q in nodes and nodes[q]["role"] not in skip:
            return q
        q = q.rsplit("/", 1)[0]
    return None


def direct_parent_node(path):
    q = path.rsplit("/", 1)[0]
    while q and q not in nodes:
        q = q.rsplit("/", 1)[0]
    return q or None


SITE = LAB
PREMISES = f"{BASE}/premises"
Ty(PREMISES, "LabPremises")
for path, n in nodes.items():
    nd = node(path)
    Ty(nd, "GroupingNode" if n["role"] == "group" else ("SimulationSettingsNode" if "SimulationSettings" in n["classes"]
                                                        else "LabSDTNode"))
    Dv("usdPrimPath", nd, path, "xsd:string")
    dp = direct_parent_node(path)
    if dp:
        R("hasChildNode", node(dp), nd)
    if n["role"] == "group":
        continue
    r = ref(path)
    R("representsEntity", nd, r)
    for c in n["classes"]:
        Ty(r, c)
    a = n["prim"].GetAttribute
    for k, prop in (("sdt:canonicalName", "canonicalName"), ("sdt:componentId", "componentId"),
                    ("sdt:class", "equipmentClassToken")):
        if a(k) and a(k).HasAuthoredValue():
            Dv(prop, r, a(k).Get(), "xsd:string")

# ------------------------------------------------------------------------------------------------ referent relations
JK = {}
for kind in ("Fixed", "Prismatic", "Revolute"):
    JK[kind] = f"{BASE}/jointkind/{kind}"
    Ty(JK[kind], kind)
for path, n in nodes.items():
    role, cls = n["role"], n["classes"]
    if role == "group":
        continue
    r = ref(path)
    if path == SITE:
        R("locatedAt", r, PREMISES)
        continue
    par = parent(path)
    pr = nodes[par]["role"] if par else None
    if role == cp.ROLE_PLACE:
        R("isSubPlaceOf", r, ref(par) if pr == cp.ROLE_PLACE else PREMISES)
    elif role in (cp.ROLE_PHYS, cp.ROLE_LINK):
        if path == C01:
            R("comprisesCell", ref(SITE), r)
        elif pr == cp.ROLE_PLACE:
            R("locatedAt", r, ref(par))
        elif pr == cp.ROLE_PHYS or par == SITE:
            R("hasDirectComponent", ref(par), r)
    elif role == cp.ROLE_FRAME:
        host = parent(path, skip=("group", cp.ROLE_FRAME, cp.ROLE_INFO, cp.ROLE_TASK))
        if host:
            R("hasInteractionPose", ref(host), r)
    elif role == cp.ROLE_JOINT:
        if par:
            R("hasDirectComponent", ref(par), r)
        kind = JOINT_KIND.get(n["prim"].GetTypeName())
        if kind:
            R("hasMechanismJointType", r, JK[kind])
        j = UsdPhysics.Joint(n["prim"])
        if kind != "Fixed" and (n["prim"].HasAPI(UsdPhysics.DriveAPI, "linear") or
                                n["prim"].HasAPI(UsdPhysics.DriveAPI, "angular")):
            Ty(r, "DrivenMechanismJoint")
        for rel, prop in ((j.GetBody0Rel(), "hasParentBody"), (j.GetBody1Rel(), "hasChildBody")):
            tg = [str(t) for t in rel.GetTargets()] if rel else []
            tg = [t for t in tg if t in nodes and nodes[t]["role"] in (cp.ROLE_PHYS, cp.ROLE_LINK)]
            if tg:
                R(prop, r, ref(tg[0]))
    elif role == cp.ROLE_MATTER:
        if path.endswith("ChallengeReagent"):
            Ty(r, "ChallengeReagentPortion")
        elif path.endswith("RescueReagent"):
            Ty(r, "RescueReagentPortion")
        elif par and "CultureMediumPortion" in cls:
            R("containsMaterial", ref(par), r)
        elif par and "WellOrganoid" in cls:
            R("locatedAt", r, ref(par))
R("locatedAt", ref(C01), ref(f"{LAB}/Zones/Cell01"))
for path, n in nodes.items():
    if n["classes"][:1] and n["classes"][0] in ("SprinklerHead", "SmokeDetector", "HVACDiffuser", "CeilingLuminaire"):
        R("locatedAt", ref(path), ref(f"{LAB}/Ceiling"))
    if "ViewpointPose" in n["classes"]:
        R("hasInteractionPose", PREMISES, ref(path))
    if "O2DepletionMonitor" in n["classes"]:
        for q2, m in nodes.items():
            if "CryogenicDewar" in m["classes"]:
                R("monitorsEntity", ref(path), ref(q2))
    if "AccessControlReader" in n["classes"] and f"{LAB}/Building/store_door" in nodes:
        R("monitorsEntity", ref(path), ref(f"{LAB}/Building/store_door"))
route = f"{LAB}/Building/AmrRoute_S1_to_H2"
if route in nodes:
    R("startsAt", ref(route), ref(f"{LAB}/StorageRoom/S1_DispatchDock"))
    R("endsAt", ref(route), ref(f"{C01}/Stations/H2_AMR_Dock"))
byname = {p.rsplit("/", 1)[1]: p for p in nodes if p.startswith(C01) and p.count("/") == 4}
for r_, sts in cp.SERVES.items():
    for s in sts:
        if s in byname and r_ in byname:
            R("servesStation", ref(byname[r_]), ref(byname[s]))
for path in nodes:
    m = re.match(rf"{C01}/Furniture/(?:P1_Supports|FitOut)/(L09|L10|L17|L21|H4)_", path)
    if m:
        st = next((p for k, p in byname.items() if k.startswith(m.group(1) + "_")), None)
        if st:
            R("supportsObject", ref(path), ref(st))
n_same = 0
for a, b in cp.SAME_AS:
    if a in nodes and b in nodes and nodes[a]["role"] != "group" and nodes[b]["role"] != "group":
        A.append(f"SameIndividual(<{ref(a)}> <{ref(b)}>)")
        n_same += 1
# capabilities: device functions (VRB) and robot skills, from Cell 01 capability tokens
for path, n in nodes.items():
    a = n["prim"].GetAttribute("sdt:capabilities")
    if not (a and a.HasAuthoredValue()) or n["role"] == "group":
        continue
    by = collections.defaultdict(list)
    for tok in a.Get():
        if tok in cp.CAP_TOKENS and cp.CAP_TOKENS[tok] in CAPS:
            by[CAPS[cp.CAP_TOKENS[tok]]].append(tok)
    robot = path.rsplit("/", 1)[1] in ROBOTS
    for c, toks in by.items():
        fi = f"{ref(path)}/function/{c}"
        Ty(fi, c)
        R("hasRobotSkill" if robot else "hasDeviceFunction", ref(path), fi)
        for t in toks:
            Dv("capabilityToken", fi, t, "xsd:string")

# ------------------------------------------------------------------------------------------------ the twin itself
TWIN, HIER = f"{BASE}#twin", f"{BASE}#scene_hierarchy"
Ty(TWIN, "LabSemanticDigitalTwin")
Ty(HIER, "LabSceneHierarchy")
R("isAbout", TWIN, ref(SITE))
R("hasNodeStructure", TWIN, HIER)
for path in nodes:
    R("hasNode", HIER, node(path))
USG, ISS = f"{BASE}#usd_scene_graph", f"{BASE}#isaac_sim_scene"
Ty(USG, "UsdSceneGraph")
R("representsSite", USG, ref(SITE))
Ty(ISS, "IsaacSimScene")
R("realizesCell", ISS, ref(C01))
for path, n in nodes.items():
    if "SimulationSettings" in n["classes"]:
        R("configures", ref(path), TWIN)
STATION_CID = {"L09_PlateHotel": "L09", "L10_Incubator": "L10", "L12_LiquidHandler": "L12",
               "L17_BrightFieldImager": "L17", "L21_QC_Calibration": "L21", "H4_Quarantine": "H4"}
for st, cid in STATION_CID.items():
    if st in byname:
        cs = f"{node(byname[st])}#component_sdt"
        Ty(cs, "ComponentSDT")
        R("modeledInTwin", ref(byname[st]), cs)
        R("hasPart", TWIN, cs)
        manual = json.load(open(os.path.join(HERE, "manual_index.json"))).get(cid, []) if os.path.exists(
            os.path.join(HERE, "manual_index.json")) else []
        for proc in manual:
            R("hasActionContract", cs, proc)

# ------------------------------------------------------------------------------------------------ culture SDT
CSDT = f"{BASE}#culture_sdt"
Ty(CSDT, "CultureSDT")
R("hasPart", TWIN, CSDT)
wells = {path.split("/Wells/")[1]: path for path in nodes if re.search(r"/Wells/[A-H]\d\d$", path)}
for w, path in wells.items():
    Dv("wellId", ref(path), f"P17:{w}", "xsd:string")
reason_ix = 0
for path, n in nodes.items():
    p = n["prim"]
    m = re.search(r"/Wells/([A-H]\d\d)(/|$)", path)
    if m and path != wells[m.group(1)] and n["role"] == cp.ROLE_INFO:
        wr = ref(wells[m.group(1)])
        r = ref(path)
        cls = n["classes"]
        if "WellBeliefEstimate" in cls:
            R("concernsWell", r, wr)
            wp = stage.GetPrimAtPath(wells[m.group(1)])
            v = wp.GetAttribute("bio:viability")
            if v and v.GetNumTimeSamples():
                ts = v.GetTimeSamples()[-1]
                Dv("viabilityMean", r, v.Get(ts), "xsd:double")
                Dv("viabilityP05", r, wp.GetAttribute("bio:viability_p05").Get(ts), "xsd:double")
                Dv("viabilityP95", r, wp.GetAttribute("bio:viability_p95").Get(ts), "xsd:double")
                Dv("time_h", r, ts, "xsd:double")
        if "WellQualityRecord" in cls:
            R("concernsWell", r, wr)
            st = stage.GetPrimAtPath(wells[m.group(1)]).GetAttribute("bio:anomalyState")
            if st and st.Get() == "contamination_suspected":
                Ty(r, "ContaminationSuspectedFlag")
        if "WellObservationRecord" in cls:
            R("concernsWell", r, wr)
            for k, prop, dt in (("obs:time_h", "time_h", "xsd:double"), ("obs:radius_um", "radius_um", "xsd:double"),
                                ("obs:coreOpticalDensity", "coreOpticalDensity", "xsd:double"),
                                ("obs:debrisCount", "debrisCount", "xsd:integer"), ("obs:haze", "mediumHaze",
                                                                                     "xsd:double")):
                at = p.GetAttribute(k)
                if at and at.HasAuthoredValue():
                    Dv(prop, r, at.Get(), dt)
            R("observationOf", r, ref(f"{wells[m.group(1)]}/Physical/Organoid"))
        if "InterventionRecord" in cls:
            kind = p.GetAttribute("sdt:eventKind").Get()
            hist = f"{ref(wells[m.group(1)])}/intervention_history"
            Ty(hist, "InterventionHistory")
            R("historyOf", hist, CSDT)
            R("partOf", r, hist)
            ev = f"{r}/event"
            Ty(ev, "ChallengeIntervention" if kind == "challenge" else "RescueIntervention")
            R("realizesIntervention", r, ev)
            R("appliedToWell", ev, wr)
            R("logsIntervention", hist, ev)
            if p.GetAttribute("sdt:committed").Get():
                R("recordsIntervention", CSDT, ev)
            Dv("isCommittedEvent", r, bool(p.GetAttribute("sdt:committed").Get()), "xsd:boolean")
            Dv("doseAU", r, p.GetAttribute("sdt:abstractUnits").Get(), "xsd:double")
            Dv("time_h", r, p.GetAttribute("sdt:time_h").Get(), "xsd:double")
    if "RescueComparisonConclusion" in n["classes"]:
        r = ref(path)
        st = p.GetAttribute("claim:status").Get() or ""
        Dv("statementText", r, p.GetAttribute("claim:proposition").Get() or "", "xsd:string")
        Dv("claimStatus", r, st, "xsd:string")
        pv = p.GetAttribute("claim:probability").Get()
        Dv("claimProbability", r, pv, "xsd:double")
        for w in re.findall(r"\b([A-H]\d\d)\b", p.GetAttribute("claim:proposition").Get() or ""):
            if w in wells:
                R("concernsWell", r, ref(wells[w]))
        if st.startswith("withheld"):
            rs = f"{r}/withholding_reason"
            Ty(rs, "ContaminationSuspectedReason" if "contamination" in st else "UnverifiedComparatorReason")
            Dv("statementText", rs, st, "xsd:string")
            R("withheldBecause", r, rs)
    if n["role"] == cp.ROLE_TASK:
        R("prescribesTaskType", ref("/World/Experiment/Workflow"), ref(path))

# ------------------------------------------------------------------------------------------------ records
R_A = []
ACT = {"retrieve": "PlateRetrievingTask", "store": "PlateStoringTask", "incubate": "IncubatingTask",
       "quarantine": "QuarantiningTask", "dose_well": "LiquidDispensingTask", "image_well": "ImagingTask",
       "qc": "CalibratingTask", "transport": "PlateTransferTask"}
COMP = {"L09": "L09_PlateHotel", "L10": "L10_Incubator", "L12": "L12_LiquidHandler", "L17": "L17_BrightFieldImager",
        "L21": "L21_QC_Calibration", "H4": "H4_Quarantine", "R01": "R01_FR3", "R02": "R02_RailSystem",
        "R03/H2": "R03_SampleAMR", "H2": "H2_AMR_Dock"}
A_sdt = A
A = R_A
declared = set()
recs = json.load(open(os.path.join(REPO, "test_reports", "episodes", "cell01_episodes_records.json")))
task_ind = {}
for t in set(ACT.values()):
    task_ind[t] = f"{BASE}/tasktypes/{t}"
    Ty(task_ind[t], t)
n_rec = 0
for ep in recs["episodes"]:
    epi = f"{BASE}/episodes/{ep['episode_id']}"
    Ty(epi, "ManipulationEpisode")
    for r in ep["records"]:
        rid = r["designator_id"]
        ri, ai = f"{BASE}/records/{rid}", f"{BASE}/actions/{rid}"
        comp, verb = r["event_type"].rsplit(".", 1)
        Ty(ri, "CellActionRecord")
        Ty(ai, "LabAction")
        R("recordsAction", ri, ai)
        R("executesTaskType", ai, task_ind[ACT[verb]])
        R("includesAction", epi, ai)
        R("hasTrace", epi, ri)
        cid = COMP.get(comp)
        if cid and cid in byname:
            R("hasParticipantEntity", ai, ref(byname[cid]))
        obj = r["designator"].get("object_id")
        if obj:
            oi = ref("/World/ExperimentalWorld/Plates/Plate_P17") if obj == "Plate_P17" else f"{BASE}/labware/{obj}"
            if obj != "Plate_P17":
                Ty(oi, "SBSMicroplate96")
            R("hasParticipantEntity", ai, oi)
        ex = r["lifecycle"].get("execution", {})
        Dv("startTime_s", ai, ex.get("t_start_s"), "xsd:double")
        Dv("endTime_s", ai, ex.get("timestamp_s", r.get("timestamp_s")), "xsd:double")
        route = r["routing"] if isinstance(r["routing"], str) else r["routing"].get("route")
        decl(PREFIXES[""] + f"route_{route}")
        A.append(f"ObjectPropertyAssertion(:hasRouting <{ri}> :route_{route})")
        for k, mon in enumerate(r.get("monitors", [])):
            mi = f"{ri}/monitor/{k:02d}_{mon['name']}"
            Ty(mi, "MonitorResult")
            Dv("monitorName", mi, mon["name"], "xsd:string")
            Dv("monitorPassed", mi, bool(mon["passed"]), "xsd:boolean")
            R("hasMonitorResult", ri, mi)
        n_rec += 1


def write(path, axioms, comment):
    hdr = [f"Prefix({k}:=<{v}>)" for k, v in PREFIXES.items()]
    name = os.path.basename(path).replace(".ofn", "")
    hdr += ["", f"Ontology(<{BASE}/abox/{name}>", "Import(<http://aicor.knowledge/okf/lab-automation-twin>)",
            f'Annotation(rdfs:comment "{comment}")']
    open(path, "w").write("\n".join(hdr + axioms + [")"]) + "\n")


write(os.path.join(HERE, "sdt.ofn"), A_sdt,
      f"AICOR Lab 1 SDT (scenes/lab_site.usda + culture SDT {args.scenario}) as LabSDTNodes and their referents.")
write(os.path.join(HERE, "records.ofn"), R_A, "Cell 01 episode records (test_reports/episodes).")
counts = collections.Counter(c for i, t in types.items() for c in t)
json.dump({"scenario": args.scenario, "sdt_nodes": len(nodes),
           "grouping_nodes": sum(1 for n in nodes.values() if n["role"] == "group"),
           "referents": sum(1 for n in nodes.values() if n["role"] != "group"),
           "render_nodes_not_instantiated": n_render, "unmapped": unmapped, "same_as": n_same, "records": n_rec,
           "facts": dict(facts), "class_counts": dict(counts.most_common()),
           "nodes": {p: (n["classes"] or ["GroupingNode"]) for p, n in sorted(nodes.items())}},
          open(os.path.join(HERE, "sdt_mapping.json"), "w"), indent=1)

# USD typing layer
tl = os.path.join(REPO, "scenes", "sdt_ontology.usda")
if os.path.exists(tl):
    os.remove(tl)
lay = Sdf.Layer.CreateNew(tl)
lay.comment = ("Ontology typing of the SDT nodes (AICOR OKF module lab-automation-twin): ont:node = the node's "
               "individual (a LabSDTNode), ont:referent = the entity it represents, ont:types = the referent's asserted "
               "classes, ont:inferredTypes = entailed classes (okf/lab-automation-twin/check_module.py).")
st2 = Usd.Stage.Open(lay)
for path, n in nodes.items():
    pr = st2.OverridePrim(path)
    pr.CreateAttribute("ont:node", Sdf.ValueTypeNames.String, custom=True).Set(node(path))
    if n["role"] != "group":
        pr.CreateAttribute("ont:referent", Sdf.ValueTypeNames.String, custom=True).Set(ref(path))
        pr.CreateAttribute("ont:types", Sdf.ValueTypeNames.StringArray, custom=True).Set(list(n["classes"]))
    else:
        pr.CreateAttribute("ont:types", Sdf.ValueTypeNames.StringArray, custom=True).Set(["GroupingNode"])
lay.Save()
comp = os.path.join(REPO, "scenes", "lab_sdt_ontology.usda")
if os.path.exists(comp):
    os.remove(comp)
cl = Sdf.Layer.CreateNew(comp)
cl.subLayerPaths = ["sdt_ontology.usda", os.path.relpath(culture, os.path.dirname(comp)), "lab_site.usda"]
cl.Save()
print(f"[sdt-abox] {args.scenario}: {len(nodes)} SDT nodes ({sum(1 for n in nodes.values() if n['role'] != 'group')} "
      f"with referents), {n_render} render nodes not instantiated, {len(unmapped)} unmapped, {n_same} same-as, "
      f"{n_rec} records, {sum(facts.values())} relation assertions")
if unmapped:
    print("unmapped:", unmapped[:20])
