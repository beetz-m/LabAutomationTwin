# lab-automation-twin: an AICOR OKF module for an automated biology lab and its semantic digital twin

This module extends the **AICOR ontology** (`http://aicor.knowledge/l2-ontology.owl#`, the frozen hub in
`ResearchSpace/foundation/okf/aicor`) and the modules built on it:
- the **robot-scientist vertical** (`verticals/robot-scientist/okf`);
- **VRB's lab-automation-device** module;
- **normative-admissibility**.

It covers four kinds of knowledge:
- **device manuals:** Cell 01's ten SDT component contracts;
- **safe action:** hazards, rules, enforcement and refused commands;
- **culture experiments:** the challenge-rescue study and its three runs;
- **experiment to motion:** an axiomatisation that derives, from a required expected information gain, the
  experiment to run and every robot motion and device command that realises it (see below).

The **SDT's nodes** (USD prims of AICOR Lab 1 and the culture SDT) are instances of its concepts.

ResearchSpace is read-only for this work. The module therefore lives in LabAutomationTwin, in the federation's layout,
as a proposal for `foundation/okf/lab-automation-twin`. It references the upstream and never edits it.

```bash
cd okf/lab-automation-twin
make all       # upstream snapshot, TBox build, ABoxes, packaging, check, PDF
make check     # validate · reason (HermiT, AICOR pipeline) · imports · cq · e2m (clingo + z3) · check-full (Konclude)
make e2m       # derive plans for required gains / lab states and validate each with z3
```

## Layout

| Path | What |
|---|---|
| `src/tbox.py`, `src/dl.py` | **Source of truth:** 359 concepts, 163 properties and 18 disjointness axioms, with description-logic axioms, in a small DSL that renders OWL, Manchester and DL notation |
| `L2-conceptual-framework/ontology/lab-twin-*-dl.md` | The 12 modules in AICOR's `-dl.md` format (Manchester), read by AICOR's exporter `okf_owl.py` |
| `L3-logical-axiomatization/axioms/experiment-to-motion-axioms.md` | E2M1–E2M9: from a required information gain to motions (sorted FOL over interval logic, [DL]/[FOL]/[SMT] sides) |
| `L3-logical-axiomatization/derivation/` | The axioms executable: `experiment_to_motion.lp` (clingo), `derive_plan.py` (ABox + EIG + twin traces → plan), `validate_plan_z3.py` (independent z3 check), `realised_gain.py` (twin execution → culture → realised gain); `out/` plans, proofs |
| `L2-conceptual-framework/out/` | HermiT reasoned TTL of the union, the reasoner report, the CQ report and `check-report.json` |
| `L1-okf-knowledge-base/bundle/` | 360 L1 concept cards (modality-tagged), `index.md`, `log.md` |
| `aicor-imports.yaml` | Every concept classified once: 325 grounded in 51 upstream classes, 20 divergences, 15 out of scope |
| `DEFERRED-REGISTER.md` | D-LAT-1 … D-LAT-9: divergences from AICOR, tooling findings, reconciliation proposals |
| `abox/` | SDT → ABox (`sdt_abox.py`), device manuals, safety, experiments, records; `plan.ofn` (the derived plan as designators), `plan_execution.ofn` (its twin execution and realised gain) |
| `bridge/cell01-bridge.ofn` | Reconciles Cell 01's own namespaces (biology, components) with AICOR (D-LAT-8) |
| `build_module.py`, `package_okf.py`, `check_module.py` | Build, OKF packaging, and the full check |
| `docs/` | `axioms.pdf` / `.md` (every concept with its DL axioms), class and instance partonomy, competency answers |

## Modules

| Module | Grounded in (upstream) | Content |
|---|---|---|
| `lab-twin-core` | AICOR `SceneNode`, `SemanticDigitalTwin`, `HierarchicalSceneStructure`; mereology `hasPart` / `hasComponent` | Partonomy properties; the SDT node / referent split |
| `lab-twin-site` | RS `LaboratorySite`, `LaboratoryCell` | Premises, rooms, zones, building, fit-out, site safety and services |
| `lab-twin-devices` | VRB `LabAutomationDevice`, `IncubationDevice`, `ImagingDevice`, `DispensingDevice`, `DeviceFunction` | Cell 01 stations, manual equipment, mechanisms, device sensors |
| `lab-twin-robots` | AICOR `Robot`, `RobotBody`, `Link` | Cell robots, bodies, exchangeable tools, robot skills |
| `lab-twin-labware` | RS `Sample`, `BiologicalSample`, `BiologicalSpecimen` | Plates, wells, medium, organoids, reagents |
| `lab-twin-poses` | AICOR `SpatialPose` | Interaction / coordinate frames of the twin |
| `lab-twin-tasks` | `dul:Concept`, `soma:Action` | Lab task types and defined action classes |
| `lab-twin-device-manuals` | RS `ActionContract`; AICOR `ProcessMonitor`, `FailureSignature`, `Repair`, `BodyWorldProcessMicrotheory`; VRB `LabConstraint`, `SafetyConstraint` | Manuals, procedures, preconditions, effects, setpoints, constraints, monitors, failure modes, recovery, risk controls |
| `lab-twin-safe-action` | AICOR `IncapabilityAssertion`, `CandidateAction`, `SafetyCheck`; RS `ContaminationCompatibility`; NA `Norm` | Hazards, safety rules, authorisation norms, enforcement, unsafe / unauthorised actions |
| `lab-twin-culture-experiments` | RS `StudyDesign`, `ExperimentalEpisode`, `BiologicalIntervention`, `CellViabilityReadout`, `ScientificHypothesis`, `ScientificConclusion`, `InterventionHistory`, `CultureSDT` | Design, arms, specifications, runs, readouts, (withheld) conclusions |
| `lab-twin-records` | RS `LabExecutionTrace` | Cell 01 NEEM records, monitor results, routing |
| `lab-twin-experiment-to-motion` | RS `ScientificModel`, `ScientificProposal`, `ExperimentalProtocol`, `ScientificActionDesignator`, `MaterialScientificDesignator`, `SceneGroundedDesignator`, `BodyMotionDesignator`, `StudyDesign` | Competing models M1–M3, gain requirement, candidates and EIG estimates, selected experiment, realisation plan, sessions, material → scene → motion / command designators, safety steps, realised gain |

## Modelling commitments

- **SDT node ≠ referent.** Every USD prim is a `LabSDTNode`, an AICOR `SceneNode` and therefore information, which
  `representsEntity` the thing it is about: an artifact, place, pose, record, estimate or claim. AICOR's
  `PhysicalEntity ⟂ AbstractEntity` makes this mandatory, and negative control 1 checks it. `owl:sameAs` relates
  referents (one bench, two SDT nodes), never nodes.
- **Partonomy:**
  - `hasDirectComponent` is simple, sits under AICOR `hasComponent`, and carries `=96` wells.
  - `hasPhysicalPart` is transitive and sits under AICOR `hasPart`; `hasSubPlace` does the same for places.
  - Containment (`containsMaterial`), location (`locatedAt`) and poses (`hasInteractionPose`) are not parthood.
- **Device manuals.** Cell 01's component contracts serve as the manuals. No vendor manual is in the repository: the
  restricted source folders hold only `.keep` files. Every item is verbatim, with source and locator. No numeric
  vendor limit is invented (D016).
- **Safe action** is three separate gates:
  - **causal / physical:** `LabSafetyRule ⊑ IncapabilityAssertion`;
  - **biosafety:** `BiosafetyRule ⊑ ContaminationCompatibility`;
  - **normative:** `AuthorizationNorm ⊑ Norm`.

  Each rule names its source, its enforcing mechanism in the twin, and the test whose *passed* result shows the
  refusal. The reasoner classifies the refused commands as `UnsafeCandidateAction` or `UnauthorizedCandidateAction`.
- **Culture experiments.** Arms carry closure axioms (only-these specs, or none), so the reasoner classifies them as
  challenge-only, challenge-rescue or control under OWL's open-world semantics.

## Verification (`make check`)

| Gate | Result |
|---|---|
| `validate` | 326 cards: frontmatter, modality tags, links |
| `reason` | HermiT, through AICOR's exporter, over the module ∪ AICOR + RS + VRB + NA (1,197 classes): **consistent, 0 unsatisfiable**, physical/abstract cut respected (about 5 s) |
| `imports` | Every grounding is an upstream class; every concept is classified once; divergences are registered; upstream unchanged |
| `cq` | 15 executable TBox competency questions **answered by inference** (`okf_cq.py`), in step with the prose |
| `e2m` | 7 plans derived (clingo, proven optimal) and validated by z3 (7 theorems each, 10/10 negative controls); 3 requirements refused with the blocking rule named |
| `check-full` | Konclude over the full-semantics TBox + 7 ABoxes (incl. plan, plan_execution) + the Cell 01 bridge + the upstream union: **consistent**, 0 unsatisfiable; **5/5 negative controls inconsistent as required**; 5,441 individuals realised (incl. the plan's designators); inferred types written to 1,567 USD nodes; 15 ABox competency questions answered (`docs/competency_questions.md`) |

**Why two reasoners.** AICOR's exporter reads definitions (≡) as necessary conditions only (D-LAT-2). Large
cardinalities also make its HermiT run intractable: `=96` took more than 25 minutes against 7 s without it (D-LAT-7).
The full-semantics export with Konclude keeps both and still finishes in seconds.

## From a required information gain to the robot's motions

`L3-logical-axiomatization/` answers the question "which physical actions and motions of the lab implement an
experiment that yields a required expected information gain g?".

- **Axioms:** `axioms/experiment-to-motion-axioms.md` (E2M1–E2M9):
  - gain-constrained least-cost selection;
  - EIG over Cell 01's competing recovery models M1–M3;
  - arms and units, sessions, device allocation by function, transfer routes over `servesStation`;
  - motion refinement, the safe-action rules as constraints, preservation.
- **Executable:** `derivation/` runs `make e2m` as clingo derivation → independent z3 validation, then twin
  execution and the realised gain. The results, including the refused requirements, are in the axioms document.

| Figure | What |
|---|---|
| `docs/e2m_eig_landscape_g050.png` | EIG over dose × delay × replicates; the requirement and the selected candidate |
| `docs/e2m_plan_g050.png` | The derived plan as a timeline per robot and device, with the twin's completion times |

**For g = 0.5 bits** the derivation selects a 0.85 au challenge, a 0.70 au rescue at 48 h, and one replicate per
arm (EIG 0.544 bits). It derives 151 steps in three trips. The Isaac twin executes all 151, in 306 / 230 / 212 s
against a 600 s window.

**Realised gain.** In the twin's culture world the realised gain is 0.23 bits (0.21 mean over 40 realisations). That
world behaves like M2/M3, which this frame cannot separate. The requirement is on the expected gain.

## Limits

- **No vendor operating limits.** The manual knowledge comes from Cell 01's contracts, which are procedural.
  Vendor-specific limits await acquired manuals (❓).
- **Keyword-based typing.** Precondition kinds and failure-mode hazards are assigned by documented keyword rules
  (`abox/manuals_abox.py`), not by expert curation.
- **Untested rules.** Six rules and norms have no refusal test in the twin and are reported with 0 verified
  refusals: the e-stop, challenge and rescue authorisation, the commit gate, the contamination response and the
  identity rule. The contamination response and the identity rule are exercised by the culture SDT and by the
  identity-swap episode, not by a refusal test.
- **Surrogate biology.** The culture experiments are the illustrative Cell 01 surrogate (D016), not a biological
  claim.
