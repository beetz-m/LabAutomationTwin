# Deferred register: lab-automation-twin

The AICOR hub is frozen, and this module never edits it. Where the module needs something upstream does not have, or
finds a defect upstream, the entry is recorded here. Each entry has its evidence and a proposal; adoption is for the
upstream owners.

| Tag | Kind | Finding |
|---|---|---|
| D-LAT-1 | divergence | No vocabulary for non-robot mechanisms and sensors |
| D-LAT-2 | tooling | `okf_owl.py` reads `EquivalentTo:` as necessary conditions only |
| D-LAT-3 | upstream modelling | RS `MeasurementInstrument ⊑ Sensor` (robot-body) |
| D-LAT-4 | upstream modelling | Mereology properties carry no characteristics |
| D-LAT-5 | divergence | No places, rooms or zones |
| D-LAT-6 | divergence | No hazard concept |
| D-LAT-7 | tooling | Large qualified cardinality makes HermiT intractable over the AICOR export |
| D-LAT-8 | reconciliation | Cell 01's namespaces are disconnected from AICOR |
| D-LAT-9 | upstream defect (SOMA) | Three SOMA classes are unsatisfiable |

## D-LAT-1: no vocabulary for non-robot mechanisms and sensors (divergence)

**What AICOR has.** AICOR's articulated-body vocabulary is about robot bodies:
- `Link ⊑ partOf some RobotBody`
- `Joint ⊑ connects exactly 2 Link, actuatedBy some Motor`
- `Sensor ⊑ partOf some RobotBody, mountedOn some Link`

**Why that doesn't fit.** An automation cell's stations also have articulations, actuators and sensors: the L10 gate
slide and shuttle, L12's gantry axes, H4's latch bolt, plate seat sensors, slot occupancy rays, the AMR dock sensors.
Typing these as AICOR `Joint`, `Link` or `Sensor` would entail that each belongs to some robot body. VRB recognises
the device side (`LabAutomationDevice ⟂ RobotBody`) but has no parts vocabulary.

**What this module does.** It adds `MechanismPart`, `MechanismJoint` (typed by AICOR's `JointType`),
`DrivenMechanismJoint`, `Actuator` and `DeviceSensor`, all under `dul:PhysicalObject`.

**Proposal.** Generalise AICOR's link, joint and sensor concepts to articulated artifacts, with `RobotBody` as one
case.

## D-LAT-2: `okf_owl.py` reads `EquivalentTo:` as necessary conditions only (tooling)

**Evidence.** In `okf_owl.py`, `_consume` handles `EquivalentTo:` items exactly like `SubClassOf:` items
(`frame.is_a.append`). Only closed enumerations become `equivalent_to`.

**Consequence.** Definitions such as the following lose their sufficient half in the AICOR export, so HermiT cannot
classify by them:
- `AutomationCell`
- `PlateStorageDevice`
- `CultureWell`
- `ChallengeOnlyArm`
- `WithheldConclusion`
- `UnsafeCandidateAction`
- `TwinEnforcedPrecondition`

**Workaround.** The module also exports full-semantics OWL (`build/lab-automation-twin.ofn`), and `check_module.py`
realises the SDT with it. The AICOR export keeps the necessary conditions.

**Proposal.** Emit `X ≡ (conjunction of the listed items)` when an `EquivalentTo:` block lists class expressions.

## D-LAT-3: RS `MeasurementInstrument ⊑ Sensor` (robot-body) (upstream modelling)

**Evidence.** In the robot-scientist vertical, `MeasurementInstrument ⊑ Sensor`, and AICOR's `Sensor ⊑ partOf some
RobotBody`. An imager typed `MeasurementInstrument` would therefore be entailed to be part of a robot body.

**What this module does.** It grounds L17 in VRB's `ImagingDevice` instead.

**Proposal.** Ground `MeasurementInstrument` in VRB `LabAutomationDevice` (or a generalised sensor; see D-LAT-1).

## D-LAT-4: mereology properties carry no characteristics (upstream modelling)

**What AICOR has.** `hasPart`, `hasProperPart`, `partOf`, `hasComponent` and `componentOf` are declared without
characteristics. Their comments in `robot-dl.md` explain why they are domain/range-free.

**Consequence.** A partonomy needs transitivity, but the properties are frozen.

**What this module does.** It adds sub-properties with characteristics:
- `hasPhysicalPart`: transitive, under `hasPart`;
- `hasDirectComponent`: simple, under both `hasComponent` and `hasPhysicalPart`;
- `hasSubPlace`: transitive.

**Proposal.** Consider a transitive `hasPart` in the hub, leaving `hasComponent` non-transitive.

## D-LAT-5: no places, rooms or zones (divergence)

**What AICOR and RS have.** Neither has a place concept. RS `LaboratorySite` and `LaboratoryCell` are
`BodyWorldSystem`s, i.e. physical systems, not places.

**What this module adds.** `dul:PhysicalPlace` placed under `dul:PhysicalObject` (the DUL reading), and under it
`LabPremises`, `LabRoom` and `LabZone`, with `locatedAt` and `hasSubPlace`.

## D-LAT-6: no hazard concept (divergence)

**What exists upstream.** AICOR has safety claims, checks and standards, and prohibitions (`IncapabilityAssertion`).
Cell 01's biology ontology has `Hazard`, in its own disconnected namespace.

**What's missing.** A hazard concept in the AICOR namespace that rules, failure modes and devices can point to.

**What this module adds.** `LabHazard` and nine kinds of lab hazard.

## D-LAT-7: large qualified cardinality makes HermiT intractable over the AICOR export (tooling)

**Evidence** (2026-10-16). `SBSMicroplate96 ⊑ hasDirectComponent exactly 96 Well`, in the union with AICOR, RS, VRB
and normative-admissibility:
- HermiT (owlready2) classification ran longer than 25 minutes without finishing.
- With `some` instead, it took 7 s.
- Konclude handles the full export, `=96` included, in under 5 s.

**What this module does.** The AICOR export writes `some`, with the exact count in a comment, and the full OWL
export keeps `=96`.

## D-LAT-8: Cell 01's namespaces are disconnected from AICOR (reconciliation)

**Evidence.** Cell 01's handoff ontologies use their own namespaces and are not connected to AICOR's
`http://aicor.knowledge/l2-ontology.owl#`:
- `aicor-biology.ttl`: `https://aicor.example/okf/biology#`, and it refers to `https://aicor.example/okf/lab#`;
- `cell01_components.ttl`: `https://aicor.example.org/ontology/{sdt,cell01}#`.

**Proposal.** Bridge axioms. Examples:
- `c01lab:CulturePlate ≡ CulturePlate`, `c01lab:CultureWell ≡ CultureWell`, `c01lab:Organoid ⊑ WellOrganoid`;
- `bio:ControlledToxicChallenge ⊑ ChallengeIntervention`, `bio:RescueIntervention ⊑ RescueIntervention`;
- `sdtc:RobotAgent ⊑ CellRobot`, `sdtc:LaboratoryDevice ⊑ LabAutomationDevice`;
- `cell01:L10 ≡` the L10 referent.

These are to be adopted by the Cell 01 owner, together with an explicit `owl:imports`.

## D-LAT-9: SOMA (master, commit `5d27187`) has three unsatisfiable classes (upstream defect, SOMA)

**Evidence.** HermiT and Konclude both find these unsatisfiable:
- **`SOMA:Color`:** an extrinsic physical quality whose colour region may only be a region for physical objects, while
  DUL keeps qualities and objects disjoint.
- **`SOMA:PreferenceOrder` and `SOMA:PreferenceRegion`:** each is a DUL Object that is also an Abstract or a Quality.

**Impact.** This doesn't affect AICOR's export, which uses stand-ins. It matters for anyone loading SOMA itself.

## D-LAT-10: two deferred rungs of the robot-scientist experiment-design axioms are discharged here (proposal, RS)

**Evidence.** The RS L3 experiment-design axioms (ED1 EIG-optimal selection under feasibility, ED2 selection is not
warrant) defer two rungs:
- "EIG computed from model-predictive distributions";
- "Feasible / Admissible grounded in run traces".

This module discharges both for Cell 01:
- `twin/culture/eig.py` computes EIG by nested Monte Carlo over the calibrated competing models M1–M3.
- `L3-logical-axiomatization/derivation/` decides `Feasible(c)` constructively. It derives a complete motion-level
  plan from the lab ABox and the twin's run-trace durations, under the safe-action rules, and z3 checks it
  independently.

**Proposal.** RS can reference `experiment-to-motion-axioms.md` (E2M1–E2M9) as the domain instantiation of ED1. The
designator levels used here (`MaterialStepDesignator ⊑ MaterialScientificDesignator`, `SceneStepDesignator ⊑
SceneGroundedDesignator`, `MotionStepDesignator ⊑ BodyMotionDesignator`) are RS's own, so no divergence is introduced.

**Open.** Two items remain:
- The cost model is a module choice: robot and device time plus 60 s per well, with no culture-time term.
- The candidate frame is finite: 3 doses × 5 delays × 1–3 replicates.

## D-LAT-11: the kernel's audit entry is not AICOR's CommitmentRecord; device commands have no CRAM counterpart

**Evidence.** The robot science assistant kernel (`LabAutomationTwin/rsa/`, module `lab-twin-rsa-kernel`) records one
hash-chained entry per designator lifecycle transition. AICOR defines `CommitmentRecord ⊑ dul:Description ⊓ contains
some ActionToken ⊓ contains some ManipulationEpisode` (manipulation-episode-dl): an episode-level nesting structure,
not a per-transition audit entry. The kernel therefore names its unit `CommitmentAuditEntry ⊑ LabExecutionTrace`.
The kernel also needs a fourth leaf kind beside body motions: commands that Cell 01's devices execute themselves
(present, dose_well phases, image, validate, store). CRAM's designator family (action / object / location / motion)
and coraplex's executables (giskard motion statecharts) have no counterpart.

**Proposal.**
- AICOR: relate a run's trail to `CommitmentRecord`, e.g. `CommitmentRecord ⊑ ∃hasAuditEntry.CommitmentAuditEntry`, or
  state that they are distinct.
- CRAM/coraplex: a device-command designator and executable type (kernel concept 1, `rsa/core.py` Command).

**Reuse.** The validity column of the kernel's constraints is robot-scientist's `ValidityConstraint`
(experimental-authorization-envelope-dl), reused, not redefined.

## D-LAT-12: the module's design concepts and the experiment ontology are bridged; dose datatypes diverge (reconciliation)

**Status (2026-10-18):** the culture-experiments design concepts are bridged to the experiment ontology
(`rsa/experiment_ontology.py`, namespace `xp:`) by `bridge/experiment-bridge.ofn`. Only primitive correspondences are
asserted (arm and administration specifications, challenge and rescue specs, `hasArm`, `appliesIntervention`,
`assignsUnit`, design, intervention, hypothesis, conclusion, run, well and organoid). `make experiment-merge`
(Konclude over module ∪ upstream ∪ experiment ontology ∪ bridge) finds the union consistent with no unsatisfiable
class, and infers ChallengeOnlyArm ≡ xp:ChallengeOnlyArm, ChallengeRescueArm ≡ xp:ChallengeRescueArm and
ControlArm ≡ xp:UntreatedArm; the module's study designs are classified under the experiment ontology's requirement
classes (RequiresDosing, RequiresCultivation). Report: `L2-conceptual-framework/out/experiment-merge-report.md`.

**Divergence:** `doseAU` (here, range `xsd:double`) and `xp:dose_au` (`xsd:decimal`) are not equated. OWL 2 value
spaces of double and decimal are disjoint, so the equivalence makes every asserted dose contradictory (HermiT found
this on the first merge). **Proposal:** use `xsd:decimal` for abstract doses here (doses are exact decimal quantities),
then add the data-property equivalence.

**Not yet merged:** the module still states its own (simpler) definitions; the bridge makes them provably the same
classes rather than removing them. Removing them in favour of imports is the next step once the experiment ontology is
packaged as an OKF module.
