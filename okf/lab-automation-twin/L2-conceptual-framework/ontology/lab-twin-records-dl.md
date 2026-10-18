---
type: dl-definition
title: "Action records, monitor results and routing (Cell 01 NEEM records) (DL definitions)"
derived_from: L1/lab-twin-records
maturity: L2
status: draft
timestamp: 2026-10-17
module: lab-automation-twin
---

# Action records, monitor results and routing (Cell 01 NEEM records)

Cell 01's NEEM-style action records (RS LabExecutionTrace), monitor results and routing (commit / quarantine / escalation / invalidation).

Every class is positioned under an upstream AICOR / robot-scientist / VRB / normative-admissibility concept or an AICOR upper-level stand-in (`dul:` / `soma:`). Generated from `src/tbox.py` by `build_module.py`; edit the source, not this file.

## Manchester syntax

```
ObjectProperty: recordsAction
    -- A record is about an action.

ObjectProperty: hasMonitorResult
    -- A record contains a monitor result.

ObjectProperty: hasRouting
    Characteristics: Functional
    -- The routing Cell 01's validator assigned to a record.

ObjectProperty: routesTo
    -- Where a routing sends the record or object.

ObjectProperty: includesAction
    -- An episode includes an action.

ObjectProperty: classifiesRecord
    -- A routing classifies records.

Class: CellActionRecord
    SubClassOf: LabExecutionTrace
    SubClassOf:
        recordsAction some LabAction,
        hasRouting some RecordRouting
    -- A Cell 01 NEEM-style record of one action (critic vector, monitors, routing).

Class: MonitorResult
    SubClassOf: dul:InformationObject
    SubClassOf:
        monitorPassed some xsd:boolean,
        monitorName some xsd:string
    -- Result of one Cell 01 monitor on an action.

Class: FailedMonitorResult
    SubClassOf: MonitorResult
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        MonitorResult,
        monitorPassed value false
    -- Defined: a monitor that did not pass.

Class: BlockedActionRecord
    SubClassOf: CellActionRecord
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        CellActionRecord,
        hasMonitorResult some FailedMonitorResult
    -- Defined: a record with a failed monitor; its semantic event cannot commit.

Class: RecordRouting
    SubClassOf: dul:Concept
    SubClassOf:
        classifiesRecord only CellActionRecord
    -- A routing outcome.

Class: CommitRouting
    SubClassOf: RecordRouting
    SubClassOf:
        routesTo some LabSemanticDigitalTwin
    DisjointWith: QuarantineRouting, EscalationRouting, InvalidationRouting
    -- Commit (culture SDT / evidence layer / admission).

Class: QuarantineRouting
    SubClassOf: RecordRouting
    SubClassOf:
        routesTo some QuarantineStation
    DisjointWith: EscalationRouting, InvalidationRouting
    -- Object to H4 (a Repair).

Class: EscalationRouting
    SubClassOf: RecordRouting
    SubClassOf:
        routesTo some dul:Agent
    DisjointWith: InvalidationRouting
    -- To a human (an AICOR HelpRequest).

Class: InvalidationRouting
    SubClassOf: RecordRouting
    SubClassOf:
        routesTo some LabSemanticDigitalTwin
    -- Invalidate dependent measurements.

Individual: route_culture_sdt_commit
    Types: CommitRouting

Individual: route_evidence_layer_commit
    Types: CommitRouting

Individual: route_evidence_admission
    Types: CommitRouting

Individual: route_H4_quarantine
    Types: QuarantineRouting

Individual: route_human_escalation
    Types: EscalationRouting

Individual: route_invalidate_dependent_measurements
    Types: InvalidationRouting

```

## Export notes

- Restrictions AICOR's exporter cannot read (negation, nested fillers, inverse roles): 0; they are kept in `build/lab-automation-twin.ofn`.
- Definitions (≡) are necessary conditions in the AICOR export (D-LAT-2).

