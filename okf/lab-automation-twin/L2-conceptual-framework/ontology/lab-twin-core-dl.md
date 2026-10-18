---
type: dl-definition
title: "Properties, upper-level placements and the SDT node / referent split (DL definitions)"
derived_from: L1/lab-twin-core
maturity: L2
status: draft
timestamp: 2026-10-17
module: lab-automation-twin
---

# Properties, upper-level placements and the SDT node / referent split

Properties of the module (partonomy, location, containment, poses, SDT node -> referent) and the SDT node classes. AICOR's mereology properties are bare and frozen, so the module adds sub-properties with the characteristics it needs.

Every class is positioned under an upstream AICOR / robot-scientist / VRB / normative-admissibility concept or an AICOR upper-level stand-in (`dul:` / `soma:`). Generated from `src/tbox.py` by `build_module.py`; edit the source, not this file.

## Manchester syntax

```
ObjectProperty: hasPhysicalPart
    Characteristics: Transitive
    -- SubPropertyOf: hasPart   (full OWL export; not read by okf_owl.py)
    -- InverseOf: isPhysicalPartOf
    -- Physical parthood (transitive closure of direct components).

ObjectProperty: isPhysicalPartOf
    Characteristics: Transitive
    -- SubPropertyOf: partOf   (full OWL export; not read by okf_owl.py)
    -- Inverse of hasPhysicalPart.

ObjectProperty: hasDirectComponent
    -- SubPropertyOf: hasComponent   (full OWL export; not read by okf_owl.py)
    -- SubPropertyOf: hasPhysicalPart   (full OWL export; not read by okf_owl.py)
    -- InverseOf: isDirectComponentOf
    -- A designed artifact has a component directly (simple: may carry cardinalities, e.g. =96 wells).

ObjectProperty: isDirectComponentOf
    -- SubPropertyOf: componentOf   (full OWL export; not read by okf_owl.py)
    -- SubPropertyOf: isPhysicalPartOf   (full OWL export; not read by okf_owl.py)
    -- Inverse of hasDirectComponent.

ObjectProperty: hasSubPlace
    Characteristics: Transitive
    -- SubPropertyOf: hasPart   (full OWL export; not read by okf_owl.py)
    -- InverseOf: isSubPlaceOf
    -- A place has a sub-place (rooms, zones).

ObjectProperty: isSubPlaceOf
    Characteristics: Transitive
    -- SubPropertyOf: partOf   (full OWL export; not read by okf_owl.py)
    -- Inverse of hasSubPlace.

ObjectProperty: locatedAt
    -- InverseOf: hostsObject
    -- An object is located at a place (not parthood).

ObjectProperty: hostsObject
    -- Inverse of locatedAt.

ObjectProperty: containsMaterial
    -- InverseOf: isContainedIn
    -- A container holds a portion of material (not parthood).

ObjectProperty: isContainedIn
    -- Inverse of containsMaterial.

ObjectProperty: hasInteractionPose
    -- InverseOf: isPoseOf
    -- A physical object has a named pose (coordinate / interaction frame of the twin).

ObjectProperty: isPoseOf
    -- Inverse of hasInteractionPose.

ObjectProperty: affordsTaskType
    -- A pose / route is where a task of this type is performed.

ObjectProperty: representsEntity
    -- InverseOf: isRepresentedBy
    -- An SDT node represents the entity it is about.

ObjectProperty: isRepresentedBy
    -- Inverse of representsEntity.

ObjectProperty: hasChildNode
    -- InverseOf: hasParentNode
    -- Scene-graph hierarchy of SDT nodes (USD namespace parent -> child).

ObjectProperty: hasParentNode
    -- Inverse of hasChildNode.

ObjectProperty: servesStation
    -- InverseOf: isServedByRobot
    -- A robot is assigned to load and unload a station or fixture.

ObjectProperty: isServedByRobot
    -- Inverse of servesStation.

ObjectProperty: monitorsEntity
    -- InverseOf: isMonitoredBy
    -- A sensor or safety device observes the state of an entity.

ObjectProperty: isMonitoredBy
    -- Inverse of monitorsEntity.

ObjectProperty: couplesTool
    -- A tool changer can couple an exchangeable tool.

ObjectProperty: drivesJoint
    -- InverseOf: isDrivenBy
    -- An actuator drives a mechanism joint.

ObjectProperty: isDrivenBy
    -- Inverse of drivesJoint.

ObjectProperty: hasParentBody
    -- A mechanism joint's parent body (USD physics:body0).

ObjectProperty: hasChildBody
    -- A mechanism joint's child body (USD physics:body1).

ObjectProperty: hasMechanismJointType
    -- The kind of a mechanism joint (AICOR JointType: Revolute, Prismatic, Fixed ...).

ObjectProperty: hasRobotSkill
    -- A robot has a skill (a capability of the robot as a whole).

ObjectProperty: hasEquipmentFunction
    -- A manual (non-automated) equipment item has a function (VRB DeviceFunction kinds).

ObjectProperty: startsAt
    -- Origin dock of a route.

ObjectProperty: endsAt
    -- Destination dock of a route.

ObjectProperty: executesTaskType
    -- An action executes a task type (lab task concept).

ObjectProperty: hasParticipantEntity
    -- InverseOf: participatesIn
    -- An action involves a participant (robot, station, plate).

ObjectProperty: participatesIn
    -- Inverse of hasParticipantEntity.

DataProperty: usdPrimPath
    Characteristics: Functional
    Range: xsd:string
    -- USD prim path of an SDT node.

DataProperty: canonicalName
    Range: xsd:string
    -- Cell 01 canonical name.

DataProperty: componentId
    Range: xsd:string
    -- Cell 01 component identifier.

DataProperty: equipmentClassToken
    Range: xsd:string
    -- Site equipment class token (sdt:class).

DataProperty: wellId
    Characteristics: Functional
    Range: xsd:string
    -- Well designator, e.g. P17:B05.

DataProperty: slotIndex
    Characteristics: Functional
    Range: xsd:integer
    -- Index of a plate slot.

DataProperty: capabilityToken
    Range: xsd:string
    -- Cell 01 capability token.

DataProperty: statementText
    Range: xsd:string
    -- Natural-language statement of a manual / rule item (verbatim from its source).

DataProperty: sourceDocument
    Range: xsd:string
    -- Source document of a knowledge item (path).

DataProperty: sourceLocator
    Range: xsd:string
    -- Locator inside the source (YAML key, section).

DataProperty: verificationTest
    Range: xsd:string
    -- Twin test that exercises a rule / precondition.

DataProperty: startTime_s
    Range: xsd:double
    -- Simulation start time (s).

DataProperty: endTime_s
    Range: xsd:double
    -- Simulation end time (s).

DataProperty: monitorName
    Range: xsd:string
    -- Cell 01 monitor template name.

DataProperty: monitorPassed
    Characteristics: Functional
    Range: xsd:boolean
    -- Whether a monitor passed.

ObjectProperty: configures
    -- Settings configure a twin.

Class: dul:PhysicalPlace
    SubClassOf: dul:PhysicalObject
    SubClassOf:
        hasSubPlace some dul:PhysicalPlace
    -- (stand-in) a place with a physical extent; its sub-places are places (DUL: PhysicalPlace ⊑ PhysicalObject).

Class: LabArtifact
    SubClassOf: dul:PhysicalObject
    SubClassOf:
        isRepresentedBy some LabSDTNode
    -- A designed physical object of the lab that the twin represents.

Class: LabSDTNode
    SubClassOf: SceneNode
    SubClassOf:
        representsEntity some Entity,
        usdPrimPath some xsd:string
    -- A node of the lab's semantic digital twin (one USD prim): information that represents one entity.

Class: GroupingNode
    SubClassOf: LabSDTNode
    SubClassOf:
        hasChildNode some LabSDTNode
    -- A structural SDT node (USD scope / xform) that groups child nodes; it represents the grouping only.

Class: LabSemanticDigitalTwin
    SubClassOf: SemanticDigitalTwin
    SubClassOf:
        hasNodeStructure some LabSceneHierarchy
    -- The semantic digital twin of a laboratory site: the belief state about it, structured as a USD scene graph.

Class: LabSceneHierarchy
    SubClassOf: HierarchicalSceneStructure
    SubClassOf:
        hasNode some LabSDTNode
    -- The USD namespace hierarchy of the lab twin (lab_twin.usda + culture layer).

Class: SimulationSettings
    SubClassOf: dul:Description
    SubClassOf:
        configures some LabSemanticDigitalTwin
    -- Physics or rendering settings of the twin (physics scene, sky and sun lights).

Class: SimulationSettingsNode
    SubClassOf: LabSDTNode
    SubClassOf:
        representsEntity some SimulationSettings
    -- An SDT node holding settings.

Class: RenderRepresentationNode
    SubClassOf: SceneNode
    SubClassOf:
        not (LabSDTNode)
    -- A render-only USD prim (looks, materials, collision / visual geometry): representation, not SDT knowledge.

```

## Export notes

- Restrictions AICOR's exporter cannot read (negation, nested fillers, inverse roles): 1; they are kept in `build/lab-automation-twin.ofn`.
- Definitions (≡) are necessary conditions in the AICOR export (D-LAT-2).

