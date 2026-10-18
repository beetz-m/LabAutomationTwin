---
type: dl-definition
title: "Labware, wells and material portions (DL definitions)"
derived_from: L1/lab-twin-labware
maturity: L2
status: draft
timestamp: 2026-10-17
module: lab-automation-twin
---

# Labware, wells and material portions

Labware, wells, culture medium and organoids, reagent portions.

Every class is positioned under an upstream AICOR / robot-scientist / VRB / normative-admissibility concept or an AICOR upper-level stand-in (`dul:` / `soma:`). Generated from `src/tbox.py` by `build_module.py`; edit the source, not this file.

## Manchester syntax

```
ObjectProperty: handledIn
    -- Labware is handled in tasks of a type.

Class: Labware
    SubClassOf: LabArtifact
    SubClassOf:
        handledIn some PlateTransferTask
    -- Containers handled in experiments.

Class: Microplate
    SubClassOf: Labware
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        Labware,
        hasDirectComponent some Well
    -- Defined: labware with wells.

Class: SBSMicroplate96
    SubClassOf: Microplate
    SubClassOf:
        hasDirectComponent some Well   -- exactly 96 in the full OWL export
    -- SBS / ANSI 96-well plate.

Class: CulturePlate
    SubClassOf: Microplate
    SubClassOf:
        hasDirectComponent some CultureWell
    -- Plate holding cultures (Plate_P17).

Class: ReferencePlate
    SubClassOf: Microplate
    SubClassOf:
        affordsTaskType some CalibratingTask
    -- L21 calibration reference plate.

Class: Well
    SubClassOf: MechanismPart
    SubClassOf:
        isDirectComponentOf some Microplate,
        wellId some xsd:string
    DisjointWith: CultureMediumPortion
    -- A well of a plate.

Class: CultureWell
    SubClassOf: Well
    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as
    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.
    EquivalentTo:
        Well,
        containsMaterial some CultureMediumPortion
    -- Defined: a well that contains culture medium.

Class: CultureMediumPortion
    SubClassOf: BiologicalSample
    SubClassOf:
        isContainedIn some Well
    -- The medium in one well: a material portion, contained, not a part.

Class: WellOrganoid
    SubClassOf: BiologicalSpecimen
    SubClassOf:
        locatedAt some Well
    -- The organoid cultured in one well (Cell 01: hepatotoxicity model; RS reading: a liver organoid).

Class: ReagentPortion
    SubClassOf: Sample
    SubClassOf:
        isContainedIn some Labware
    -- A reagent portion in a container.

Class: ChallengeReagentPortion
    SubClassOf: ReagentPortion
    SubClassOf:
        affordsTaskType some ChallengeDosingTask
    DisjointWith: RescueReagentPortion
    -- Abstract challenge reagent.

Class: RescueReagentPortion
    SubClassOf: ReagentPortion
    SubClassOf:
        affordsTaskType some RescueDosingTask
    -- Abstract rescue reagent.

```

## Export notes

- Restrictions AICOR's exporter cannot read (negation, nested fillers, inverse roles): 0; they are kept in `build/lab-automation-twin.ofn`.
- Definitions (≡) are necessary conditions in the AICOR export (D-LAT-2).

