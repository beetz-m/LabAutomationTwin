# Plan: a CRAM-based robot science assistant for Cell 01

Status: plan, revision 2, 2026-10-17. Nothing in this document is implemented yet.

Revision 2 follows the ResearchSpace sweep in [researchspace-material-map.md](researchspace-material-map.md). The
runtime is **coraplex**, which is PyCRAM renamed; it runs on ROS 2 Jazzy and Python 3.12, and ROS is optional. Your
`uc_ccr` CRAM tryout is the direct predecessor of this system. The changes are listed in §9 of the map. Where this text
and that section differ, §9 wins.

Aim: re-implement the Cell 01 robot science assistant as a CRAM system. Plans are written as `perform`s of action
designators. The action designator categories align with the categories of robot and manipulation actions. Devices,
steps and workflows can be exchanged. Every execution leaves a TraceBot-style audit trail. Workflows, constraints,
regulations and device capabilities are explicit knowledge, and the assistant shows that it understands what it is
doing by answering competency questions about its past, present and possible activity.

---

## 0. Starting point and principles

### 0.1 What exists already (LabAutomationTwin, uncommitted since d831ac1)

| Asset | Where | Role in the new system |
|---|---|---|
| Isaac twin of Cell 01 (R01 FR3, R02 UR5e + rail + TCM, R03 AMR, L09, L10, L12, L17, L21, H4, HN) | `twin/*.py`, `assets/`, `scenes/` | Backends of the process modules (WP1.3) |
| Episode runner (≈1700 lines of imperative Python) | `scripts/run_cell01_episode.py` | **Replaced** by CRAM plans. Its episodes become regression oracles |
| Experiment-to-motion derivation (EIG → clingo → z3 → Isaac) | `okf/.../L3-logical-axiomatization/derivation/` | Scientific executive. It emits action designators (WP7) |
| AICOR OKF module, 12 sub-modules, 359 concepts | `okf/lab-automation-twin/` | Knowledge base that designator resolution queries (WP3) |
| Safety rules S1–S9, device manual ABox, culture SDT | `abox/*.ofn`, `twin/culture/` | Constraints and belief state |
| Records via Cell 01 `build_*_neem_record` | `twin/episode_records.py` | Seed of the audit trail (WP5) |

### 0.2 What ResearchSpace provides (read-only; reused by reference, never edited)

- **CRAM language and theory**
  - `foundation/okf/cram`: GLOSSARY, `designator-language/00-language.md` (HADL), and
    `concurrent-reactive-plans/CRAM-PLAN-LANGUAGE-COMPREHENSIVE.md` (perform, failure handling, SEQ/PAR/PURSUE/
    TRY-IN-ORDER/WITH-POLICY).
  - The DL ontologies in `foundation/kb/dl-axioms/cram/ontology/` (designators, plans, architecture, memory,
    action tokens).
  - The designator lifecycle axioms (WellFormed ⊐ Resolved ⊐ Executable) in
    `foundation/kb/logical-axioms/cram/axioms/designator-competence-axioms.md`.
- **Action categories**
  - `foundation/kb/dl-axioms/cram/ontology/action-category-dl.md`, effect partition: ObjectDisplacement,
    ConfigurationChange, SubstanceManipulation, SurfaceTreatment, ConnectingAction, InteractionAction,
    MaintenanceAction.
  - `foundation/okf/manipulation-actions` (phase structure, intentional and causal structure, failure classes).
  - `foundation/okf/tool-use`.
  - The Siemens action-designator schema (roles, goal/prohibited effects, control policy, monitors, success
    criteria). It is a good template.
- **Cell 01 contracts**
  - `sdt/schemas/cram_designator_schemas.yaml`: 8 designators (retrieve, store, transport, dose, incubate, image,
    qc, quarantine) and the lifecycle open → grounded → accepted → executing → executed / repaired / abstained /
    escalated.
  - `neem_record_schema.yaml`.
  - Component capabilities in `sdt/components/*.yaml`.
  - Decisions D008 (physical success ≠ validity), D009 (commit only after validity), D010 (CRAM is the manipulation
    executive; the scientific executive sits above it) and D011 (NEEMs are the evidence trace).
- **Understanding**
  - `biology/ontology/robot-understanding-contract.md` U(a) = ⟨What, Target, Purpose, Mechanism, Preconditions,
    Realization, ExpectedEffects, Risks, Controls, Monitors, Recovery, Evidence, EpistemicState⟩.
  - `robot-understanding-and-communication.md` (ExplainAction, ExplainWhyAbstaining, ...).
  - `foundation/okf/cram/action-ontology/06-narrative-intelligence.md` ("understanding = telling the story of your
    activity").
- **Audit and regulation**
  - TraceBot / semantic execution tracing / RobAuditor / NEEM cards in
    `foundation/okf/vrb/L1-okf-knowledge-base/bundle/concepts/`.
  - The VRB lab constraints `foundation/okf/vrb/L3-logical-axiomatization/axioms/lab-automation-constraints.md`
    (C-S/W/E/O/M/D, including C-D1 append-only tamper-evident audit and C-D2 method version bound to result).
  - The warrant framing ⟨grounds, constraints discharged, verdict, disposition⟩ as the audit entry.
  - `foundation/okf/normative-admissibility` (Norm ≠ causal admissibility).

### 0.3 Gaps this plan closes

1. **No working CRAM runtime on this machine.** The CRAM monorepo (coraplex, semantic_digital_twin, giskardpy, krrood,
   cram_viz) is checked out at `~/ResearchSpace/foundation/software/cram`, including the branch with the UR lab-cell
   perform.
   - It is a copy of `~/WORK/...`, which no longer exists.
   - Its `.venv` points to a missing interpreter and to `~/WORK`, so coraplex does not import (checked 2026-10-17).
   - ROS 2 Jazzy is installed.
2. **No lab action categories.** The CRAM foundation has no categories for pipetting, dispensing, imaging, device
   tending or tool coupling ("pipett" has 0 hits in foundation/okf/cram).
3. **Procedural knowledge sits in code.** The episode runner hard-codes device names, poses and step orders.
   Clingo/z3 hold the *plan* explicitly, but not its execution.
4. **Records are not an audit trail.** They have no hash chain, no actor, software or KB versions, no resolution
   provenance and no human authorisation records. Their timestamps are simulated time only.
5. **The competency questions are TBox questions** ("is X a Y?"). None asks the robot about its own activity: why,
   how, what-if, evidence.
6. **Regulations are absent from Cell 01.** The VRB constraints cite GMP Annex 1/11 and ALCOA+. GLP and 21 CFR Part 11
   are not represented anywhere.

### 0.4 Design principles

- **P1 One knowledge base, many uses.** The same explicit representation drives selection (clingo), validation (z3),
  designator resolution, execution monitoring, audit and question answering. Nothing is duplicated in code.
- **P2 Plans name categories and requirements, never devices or poses.** Devices, poses and motion parameters are
  bound at resolution time by querying knowledge. This is what makes exchange possible.
- **P3 The designator lifecycle is the audit unit.** Each transition (open, grounded, accepted, executing, executed,
  failed, repaired, abstained, escalated) is one audit entry.
- **P4 Understanding is a contract, not a feature.** A designator whose U(a) is incomplete is not executable (Cell 01
  rule). Competency questions are the test that U(a) is really computed.
- **P5 Every claim of compliance is a mapped check.** Each regulation clause is either a runtime check with a
  verifier, or a documentary control that a named human signs off. Nothing in between. D016 applies: we cite clause
  identifiers and do not paraphrase regulatory text as fact without the source.
- **P6 The twin is a backend, not the system.** Process modules have a twin backend now and a device backend later.
  Plans do not change.

---

## 1. Target architecture

```
 ┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ L6  Understanding & dialogue    CQ engine · U(a) contract check · explanation acts · (opt.) NL   │
 ├──────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ L5  Scientific executive        EIG / model discrimination · experiment selection (existing e2m) │
 │                                  emits SCIENTIFIC action designators (Measure, Intervene, Wait)  │
 ├──────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ L4  Workflow layer              workflow = versioned graph of task designators + temporal and    │
 │                                  normative constraints; validated (clingo/z3) before release     │
 ├──────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ L3  CRAM plan layer             generalized action plans per action category; perform;          │
 │                                  with-failure-handling; with-policy monitors; try-in-order       │
 ├──────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ L2  Resolution layer            action → (sub-actions | motion | object | location designators)  │
 │                                  by queries to the KB: capabilities, poses, constraints, costs   │
 ├──────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ L1  Process modules             Arm · RailArm · ToolChanger · Gripper · LiquidHandling · Imaging │
 │                                  · Storage · Environment · Calibration · Navigation · Identity   │
 │                                  backends: Isaac twin (now) · SiLA 2 / LADS / ROS 2 (later)      │
 ├──────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ L0  World                       Isaac Sim Cell 01 twin · culture SDT · belief state             │
 └──────────────────────────────────────────────────────────────────────────────────────────────────┘
   Cross-cutting:  Knowledge base (OKF/OWL + ABoxes + ASP + z3)   ·   Audit trail / NEEM store + verifiers
```

Data flow for one step: the scientific executive asks to *Intervene(challenge, well A01, 0.85 au)*. The workflow layer
instantiates the task designator `dosing`. The CRAM plan for `dosing` performs `transporting(plate → L12)`, then
`dispensing(...)`, then `transporting(plate → L10)`. Resolution binds the transporting designators to R01, the HN and
R02 with T01, and expands them into `picking-up / placing` and then motion designators. The process modules execute on
the twin. The monitors, as policies, watch airspace, identity, environment and window. Every lifecycle transition is
written to the hash-chained audit trail together with its grounds and evidence. The CQ engine can answer, at any
moment, "what are you doing, why, how do you know it worked".

---

## 2. Work breakdown (hierarchical)

Sizes are relative: S ≈ days, M ≈ 1–2 weeks, L ≈ 3–6 weeks of focused work.

### WP1 CRAM runtime foundation

**1.1 Runtime decision and spike (S). Decision point D-C1.**

> Revision 2: decided by the material. Use **coraplex** (PyCRAM renamed; ROS 2 Jazzy / Python 3.12; ROS optional via
> its `no_ros` fallback). The spike is:
> 1. Create a working environment *outside* ResearchSpace, from a clone of your fork or a worktree of the RS checkout
>    at `robot-scientist-ur-perform`, then `uv sync`.
> 2. Reproduce `test_perform_labcell.py` (UR10e in bullet, headless).
> 3. Add an Isaac execution backend next to giskardpy-on-SDT.
>
> coraplex has no process modules. Motions run as giskard motion statecharts. Cell 01 *device* actions therefore need a
> new device-command executable type (WP1.3).
>
> Options A and B below are kept for the record.
- **1.1.1 Option A: PyCRAM** (Python, the CRAM team's re-implementation). It sits in the same process as Isaac's
  Python and the existing controllers, and RS names it as the operational target (`foundation/okf/cram/CYCLE.md` S6).
  - Risk: the documented setup is ROS Noetic. The new API uses `semantic_digital_twin` as the belief world.
- **1.1.2 Option B: Lisp CRAM** (cram_core on SBCL). This is the canonical language with the full plan language
  (PURSUE, policies, plan transformation).
  - Risk: it is ROS 1 only. It would need a bridge to Isaac (ROS 2 / sockets).
- **1.1.3 Spike.** Install the candidate in a separate venv (`env_cram`). Run one `perform(PickUpAction)` on a toy
  world. Then run it against Isaac via an in-process backend with no ROS.
  - Exit criterion: one plate pick on the Cell 01 twin, triggered by a designator.
- **1.1.4 Recommendation:** Option A, keeping HADL / Lisp-style notation as the *specification* language. Every
  PyCRAM class carries its HADL form, so a later Lisp port stays mechanical.

**1.2 World and belief bridge (M).**
- 1.2.1 Load the Cell 01 USD and URDFs into the CRAM belief world: the static scene plus articulated devices as
  semantic objects (plate, nest, slot, door, shuttle, tool, tip).
- 1.2.2 Synchronise the belief world from the twin's perception channels: barcode reads, seat sensors, HN monitor,
  L17 images. Ground truth stays hidden from the belief (as with the twin's own L17 optics).
- 1.2.3 Semantic labels: every belief object is linked to its KB individual (SDT node IRI). This implements the
  node ≠ referent rule (CQ-8).

**1.3 Process modules over the existing controllers (L).**
- 1.3.1 Define the process module interface: `execute(motion_or_command_designator) → result + evidence`, plus
  typed failures (from the SOMA failure taxonomy and the Cell 01 failure routing).
- 1.3.2 Implement one module per capability family, wrapping the existing code:

  | Process module | Wraps | Accepts |
  |---|---|---|
  | `ArmPM[R01]` | `r01_rig`, `r01_planner` | reaching, approaching, grasping, lifting, transiting, lowering, releasing, retracting (compliant variants) |
  | `RailArmPM[R02]` | `r02_rig`, `r02_controller` | the same plus rail moves |
  | `ToolChangerPM` | TCM in `r02_controller` | tool-coupling, tool-uncoupling |
  | `LiquidHandlingPM[L12]` | `l12_controller`, `l12_liquid` | tip pick-up, aspirate, dispense, eject; airspace interlock |
  | `ImagingPM[L17]` | `l17_controller`, `l17_optics` | present / load, autofocus, image region |
  | `StoragePM[L09, L10, H4]` | the three controllers | present, stow, store / retrieve, environment |
  | `CalibrationPM[L21]` | `l21_controller` | reference-plate procedure |
  | `NavigationPM[R03]` | `r03_controller` | navigate, dock |
  | `IdentityPM` | barcode / AprilTag reads | identify plate |
  | `GuardPM` | interlocks, doors, light curtain | check, close |

- 1.3.3 Backend abstraction: `backend = twin | device`. Only the twin backend exists for now. The device backend
  defines the SiLA 2 / LADS / ROS 2 action mapping per capability (spec only).

**1.4 First vertical slice (M).** Port the `nominal` episode (L10 → R01 → L09 store) to
`perform(an action (type storing) (object (the plate P17)) (location (a location (in plate-hotel))))`.
- Acceptance: the same monitors and the same routing as the current runner. The regression oracle is
  `test_reports/episodes/cell01_episodes_records.json`.

### WP2 Action designator taxonomy aligned with robot and manipulation action categories

**2.1 Category ontology (M).** A new OKF sub-module, `lab-twin-action-categories`. It imports the CRAM designator and
action-category DL modules and the Cell 01 designator schemas by IRI.

Five levels. Each class is an action-designator *category*, i.e. a GeneralizedActionPlan type in CRAM terms:

```
 SCIENTIFIC (RS scientific-action-designator)   Measure · Intervene · Wait · Replicate · Perturb · DiscriminateHypotheses
 └─ LAB TASK  (schema heads; composite)         Storing · Retrieving · Transporting(plate) · Incubating · Dosing ·
    │                                            Imaging · QualityControl · Quarantining · QuarantineReleasing ·
    │                                            Restocking · WasteDisposing · Docking/Delivering
    └─ MANIPULATION ACTION (by effect, AICOR action-category-dl partition)
       ├─ ObjectDisplacement      PickingUp · Placing · Transporting · HandingOver · Inserting/Seating · Presenting
       ├─ ConfigurationChange     OpeningDoor · ClosingDoor · ExtendingShuttle · RetractingShuttle · PressingButton ·
       │                          TurningSelector
       ├─ SubstanceManipulation   Aspirating · Dispensing · Mixing · (Pouring) · LiquidLevelDetecting
       ├─ ConnectingAction        ToolCoupling · ToolUncoupling · TipPickingUp · TipEjecting · Docking · Lidding/Delidding
       ├─ PerceptionAction        Identifying(barcode/tag) · Inspecting(seating, airspace) · Imaging · Autofocusing ·
       │                          LocalisingByFiducial
       ├─ MaintenanceAction       Calibrating · Cleaning · Sterilising · Restocking
       └─ RegulationAction        Incubating(hold env.) · Waiting · Monitoring
          └─ MOTION (CRAM motion designators; phase structure Reach–Lift–Transport–Release)
               Reaching · Approaching · Grasping · Lifting · Transiting · Lowering(compliant) · Releasing ·
               Retracting · MovingRail · MovingGantry · MovingStage · Focusing · ...
          └─ DEVICE COMMAND (for actions an automated device performs internally; SiLA-like call)
```

- Disjointness: the manipulation categories are disjoint by effect. The Motion and DeviceCommand levels are disjoint
  (negative control 5 already enforces this).
- Every existing class is placed:
  - `LabTaskType` subclasses → LAB TASK;
  - the e2m `MaterialStep / TransferScene / MotionStep` → L5 / L4 / MOTION;
  - Cell 01's 8 designators → LAB TASK.

**2.2 Category specifications (L).** One card per category, following the Siemens schema plus the Cell 01 contract and
U(a):
- roles (agent, patient, instrument, source, destination, substance, tool);
- typed parameters with units and admissible ranges, taken from device capability records, not invented (D016);
- preconditions and effects, both goal and prohibited effects;
- phase structure, and the control mode per phase (free-space → guarded → compliant → seated verification);
- monitors (Cell 01 `monitor_templates.yaml`) and their policies;
- failure types → recovery (allowed and forbidden recoveries);
- evidence obligations (what the audit entry must carry);
- the applicable constraints and norms (link to WP3.4 / 3.5).

The cards are written as L1 concept cards and compiled to DL (L2) and to ASP and z3 facts (L3). There is one source.

**2.3 Object and location designators (M).**
- Object designators: plate (with identity), well, tip, tube/reagent (lot), tool, door, shuttle. Use referential
  "the" for identified plates and attributive "a" for consumables (HADL determiners).
- Location designators: nest, slot, well pose, approach pose, park, airspace region. They resolve against frames in
  the KB pose module (`lab-twin-poses`) and are refined to ARPlaces for the robot.

**2.4 Generalized action plans (L).** One plan per manipulation category and lab task. Each is a PyCRAM
`ActionDescription` with its HADL form in the docstring.
- Generated from, or checked against, the category card. A unit test fails if the code's roles or pre/effects differ
  from the card.
- Failure handling follows CRAM idiom: `with_failure_handling(GraspSlipped → reperceive; retry ≤ n)` and
  `IdentityMismatch → escalate(H4_quarantine)`. Retry = re-resolution.
- Policies: `with_policy(airspace_clear(L12))` and `with_policy(outside_incubator_window ≤ W)`, where the window
  policy turns the static S5 check into a live fluent.

**2.5 Alignment proofs (S).**
- Every executable designator class is under exactly one manipulation category.
- Every motion step refines exactly one manipulation action.
- Every lab task covers the Cell 01 designator schema's `required_bindings`.
- These go in the OKF check as TBox CQs plus negative controls.

### WP3 Explicit knowledge: capabilities, workflows, constraints, regulations

**3.1 Device capability model (M).**
- 3.1.1 Lift `sdt/components/*.yaml` (capabilities, action_contracts, limits, interfaces) into a capability ABox. A
  `Capability` is a disposition of a device to realise an action category, under parameter ranges and preconditions.
  It extends `lab-twin-devices` and `lab-twin-device-manuals`.
- 3.1.2 State-dependent capability: calibrated, coupled tool, tips available, door state. These are fluents in the
  belief, so "L17 can image now" is a query, not a constant.
- 3.1.3 Robot capabilities: reach sets per site (from `tools/reachability_study.py`), payload, compliance, and
  grippers/tools as instruments (tool-use ontology: WieldedTool, effective embodiment).

**3.2 Labware and material model (S).** SBS plate formats, well geometry, tips, reagents with lot, expiry and
concentration (illustrative). Contamination state as a fluent.

**3.3 Workflow representation (M).**
- 3.3.1 A workflow is a versioned graph of task designators:
  - nodes are categories with partial bindings;
  - edges are precedence, with Allen relations and min/max delays (e.g. rescue 48 h after challenge);
  - each workflow is annotated with purpose (the scientific goal), required evidence and the applicable norms.
- 3.3.2 Serialisation: OWL ABox (for reasoning and CQs) plus a compact YAML/HADL authoring form, compiled into
  both. Workflows become data, not Python.
- 3.3.3 The workflows to model first:
  - the 5 existing episodes;
  - the e2m challenge–rescue experiment;
  - QC/calibration;
  - quarantine and release.

**3.4 Constraint representation (M).** Unify the constraint sets in one constraint registry. Each constraint has:
- a formal statement (DL where expressible, ASP for planning, z3 for verification, a runtime monitor for
  execution);
- the kind (causal safety, machine protection, biosafety, sample integrity, identity, measurement validity,
  temporal, normative);
- its source.

The sets to unify are:
- safety S1–S9;
- the 600 s / 20 % window;
- the Cell 01 acceptance checks;
- the VRB lab constraints (C-S, C-W, C-E, C-O, C-M, C-D).

Generate the clingo constraints, the z3 theorems and the runtime monitors from the registry, so the three cannot
drift apart.

**3.5 Regulations and norms (M). Decision point D-C3: scope.**
- 3.5.1 A clause registry: regulation, clause identifier, short own-words gloss, and source pointer. The candidate
  scope is listed below. Cell 01 is a research cell, not a GMP site, so the honest framing is "GxP-aligned audit and
  data integrity". QA or the user confirms the scope.
  - EU GMP Annex 11 (computerised systems, audit trail);
  - 21 CFR Part 11 (electronic records and signatures);
  - ALCOA+ (data integrity);
  - OECD GLP principles;
  - GMP Annex 1 (aseptic handling);
  - ISO 10218-1/-2 and ISO/TS 15066 (robot safety);
  - biosafety level rules.
- 3.5.2 Each clause → `Norm` (normative-admissibility: obligation, permission or prohibition) → realised by one or
  more of:
  - a runtime check (registry constraint plus verifier);
  - an audit-trail obligation (WP5 field);
  - a documentary control (human sign-off record).

  A clause with no realisation is reported as an uncovered requirement.
- 3.5.3 Keep norms apart from causal safety. CQ-7 already does this, and it is extended to the full registry.

**3.6 Resolution queries (M).**
- A resolution query interface that the CRAM resolvers call:
  - `devices_capable(category, params, now)`
  - `pose(location_designator)`
  - `constraints_applicable(designator)`
  - `route(src, dst)`
  - `cost(designator)`
- Implementation: OWL reasoning offline (classification is cached), plus fast runtime lookups over the compiled
  ABox, plus clingo for combinatorial choices (as e2m does).
- Every answer returns its **grounds**: the axioms and facts used. The audit entry needs them (WP5) and the
  "why this device?" CQ needs them (WP6).

### WP4 Modularity: exchange devices, substitute steps, change workflows

**4.1 Capability-based binding (M).**
- Remove every device and pose name from the plans. A lint fails CI if a plan module mentions a device IRI or prim
  path.
- Bindings come only from the resolution queries (WP3.6).

**4.2 Substitution theory (M).** New L3 axiom set `substitution-axioms.md`, proved with z3 over finite frames like
`designator_z3_prove.py`:
- **SUB-D (device substitution):** D′ may replace D for category C in workflow W iff:
  - caps(D′) ⊇ required(C, params);
  - D′ satisfies the same applicable constraints;
  - D′ meets the evidence obligations;
  - D′'s qualification state is valid (calibrated, released);
  - the routes exist (reach).
- **SUB-S (step substitution):** realisation R′ may replace R for designator d iff:
  - goal effects(R′) ⊇ goal effects(d);
  - prohibited effects(R′) ∩ forbidden(d) = ∅;
  - pre(R′) holds in the expected belief;
  - the monitors remain sufficient;
  - the evidence is preserved (the refinement rule of the RS designator-refinement module).
- **SUB-W (workflow change):** W′ refines W if it preserves purpose, required evidence and norms. Otherwise it is a
  *change*, which triggers change control (4.4).

**4.3 Method library and selection (M).**
- Several realisations per category, for example:
  - transport direct vs via the handover nest;
  - dosing by L12 vs a pipette tool on R02, if modelled;
  - imaging at 10× vs 20×.
- They are tried in order of cost and risk, with CRAM `try_in_order` semantics. Re-resolution happens on failure.

**4.4 Change control (S).**
- Workflows, category cards, capability records and the constraint registry are versioned (git hash plus a semantic
  version).
- An impact analysis query answers which validations, qualified states and previous results a change invalidates
  (C-D2 "method version bound to result").
- An audit entry records the change and its approval.

**4.5 Exchange demonstrators (M). Each is an acceptance test.**
- **X1 Device swap:** replace L17 with a second imager twin model (different stage, objectives and API) by changing
  only its capability record and process-module binding. The plans are unchanged. The audit shows the new binding.
- **X2 Robot swap:** do the R01 FR3 plate transfers with a different arm model, or with R02 where reach allows.
  Reach and route constraints decide feasibility, or a refusal names the blocking constraint.
- **X3 Step substitution:** direct transfer vs handover nest, and a tip-wash vs a fresh tip (only if modelled).
  SUB-S is proved before execution.
- **X4 Workflow change:**
  - add a priming intervention to separate M2 from M3 (the e2m finding);
  - insert an extra QC step;
  - change the rescue delay.

  Re-validated by clingo/z3, with change control recorded.

### WP5 TraceBot-style audit trail

**5.1 Audit event model (M).** Extend Cell 01 `neem_record_schema.yaml`. One entry per designator lifecycle
transition, with these fields:
- **What:** the designator (full HADL form, category, bindings) and its parent chain up to the scientific goal.
- **Who:**
  - agent (robot or device id);
  - software versions (plan library, KB, twin, controller);
  - human actor for authorisations.
- **When:** wall-clock and sim time, with monotonic sequence numbers.
- **Why / grounds:**
  - the resolution provenance (queries, axioms and facts used, alternatives rejected and the rule that rejected
    them);
  - the belief snapshot hash.
- **Constraints discharged:** ids from the registry, each with its verdict (the warrant ⟨grounds, constraints
  discharged, verdict, disposition⟩).
- **Evidence:** monitor results, raw evidence references (images, force traces, seat sensors, barcode reads, USD
  state snapshots), each content-hashed.
- **Outcome and disposition:** commit / route / repair / abstain / escalate. D009: consequential events are committed
  only after validity.

**5.2 Instrumentation (M).** Hooks in `perform`, the resolvers, the process modules, the monitors and the failure
handlers. Nothing in the plans themselves: the trail is written by the runtime, so a plan cannot skip it (C-D1).

**5.3 Evidence store (S).**
- Content-addressed blobs (sha256) under `audit/evidence/`.
- Raw images from L17, force/torque from the twin, and USD layer snapshots at key events.

**5.4 Integrity (S).**
- An append-only, SHA-256 hash-chained log, with a verifier CLI that re-computes the chain and checks every evidence
  hash.
- A tamper test: a mutated entry or blob must be detected. This is the negative control.

**5.5 Human authorisation and sign-off (S).**
- Records for quarantine release, workflow changes and documentary controls: who, role, meaning of the signature,
  time, and the entry hash signed.
- Signing in the twin is simulated and labelled as such. It is not a Part 11 claim.

**5.6 NEEM export and replay (M).**
- Export episodes as SOMA-typed ABox (OWL) plus a JSON document per episode (MongoDB-compatible layout).
- Replay an episode in Isaac from the trail, and compare runs by execution-tree isomorphism.

**5.7 Verifiers, RobAuditor-style (M).**
- A pipeline of verifiers, each returning ⟨decision, confidence, explanation, recovery⟩. Examples:
  - identity continuity;
  - dose delivered vs commanded;
  - window kept;
  - every step has its constraints discharged;
  - an ALCOA+ checklist evaluation.
- Online (during execution, feeding failure handling) and offline (an audit review report).

### WP6 Understanding: the assistant answers competency questions about what it does

**6.1 CQ catalogue (M).** About 60 questions in 10 families. Each has an NL form, a formal query, the expected answer
in a reference episode, and the source of truth used to check it.

| Family | Examples |
|---|---|
| What / now | What are you doing? Which plate, which well, which device? Which phase of picking-up? |
| Why / purpose | Why are you dosing A01? → goal chain: rescue arm → experiment c_d85_t48_n1 → discriminate M1–M3 → required 0.5 bits |
| How / realisation | How will you get the plate to L12? Which motions, which tool, how long? |
| Preconditions / constraints | What must hold before you dispense? Which rule forbids entering L12 now? |
| Capabilities | Which devices can image this plate now? Can R02 replace R01 for L10 → HN? Why not? |
| What-if (counterfactual / prospective) | What happens if L17 is uncalibrated? If identity fails at L10? If the window would be exceeded? |
| Evidence | How do you know A01 received 17 µL? Show the evidence and its hash |
| Retrospective (over the trail) | What went wrong in trip s2? Why did you re-image A01? Which steps were repaired? |
| Normative | Is this action permitted? Who authorised the release? Which clauses does this run cover / not cover? |
| Self-assessment / epistemic | How confident are you that the dose was delivered? What do you not know? Which result is invalidated if L17's calibration is revoked? |

**6.2 Query engine (L).**
- One interface over four sources:
  - the KB (OWL reasoner / SPARQL over the compiled ABox);
  - the belief state (fluents);
  - the plan (the current task tree, e.g. CRAM's task tree);
  - the audit trail / NEEMs.
- Counterfactual and prospective questions are answered by projection: clingo re-planning with the changed fact, z3
  for "would this violate", or Isaac/CRAM simulation of the plan (CRAM-style projection).

**6.3 Understanding contract gate (S).**
- Before `accepted`, compute U(a) for the designator from the category card, bindings, constraints, monitors and
  recovery.
- If any of items 1–12 is missing, the designator stays `grounded` and is not executed (Cell 01 rule). The gate
  decision is an audit entry.

**6.4 Explanation acts (M).**
- ExplainAction, ExplainWhyAbstaining, RequestAuthorization, ReportDeviation, ReportEvidenceStatus.
- Generated from query results with their grounds, as templated text. Every sentence links back to an axiom, fact or
  trail entry.

**6.5 Evaluation (M).**
- The CQ suite runs in `make check` against reference episodes (nominal, identity swap, uncalibrated imager,
  contamination refusal, plan_g050), with exact expected answers.
- A perturbation set (injected failures) checks that retrospective answers follow the actual course, not the
  intention (RS "intention vs actual course vs divergence").
- Score: answered, correct, grounded (has grounds), consistent with the trail.

**6.6 Natural-language front end (optional, M).**
- An LLM translates questions into the formal CQ queries and verbalises answers.
- The answer content comes only from the query engine. Unanswerable questions are reported as such.

### WP7 Integration with the scientific executive and end-to-end demonstrators

**7.1 (M)** e2m emits scientific and lab-task designators, not interpreter steps. Clingo keeps the selection, the
allocation and the S1–S9 checks. Motion refinement moves to CRAM resolution, and z3 validates the resolved plan.

**7.2 (M)** Retire `run_plan_episode`. The same plan executes via CRAM, and the results match within tolerance
(steps, durations ±20 %, doses, identity).

**7.3 Demonstrators.** Each produces a trail, a verifier report and a CQ session.

| Id | Demonstrator | Shows |
|---|---|---|
| D1 | Required 0.5 bits → experiment → CRAM execution → realised gain | The full stack |
| D2 | X1 device swap (imager) mid-campaign | Modularity and change control |
| D3 | X3 step substitution after a handover-nest fault | Failure handling and re-resolution |
| D4 | X4 priming step to separate M2 / M3 | Workflow change driven by science |
| D5 | Identity swap → quarantine → human release | Audit trail and authorisation |
| D6 | Interrogation: 30 CQs asked during and after D1 / D5 | Understanding |

Video in the lab scene for D1 and D5 (existing `twin/video.py`).

### WP8 Verification and regression infrastructure (continuous)

- `make check` grows:
  - category alignment (2.5);
  - substitution proofs (4.2);
  - generated-constraint equivalence between ASP, z3 and the monitors (3.4);
  - trail integrity, including the tamper test (5.4);
  - the CQ suite (6.5).
- Isaac regressions: the 5 legacy episodes as oracles until WP7 retires the runner, then the CRAM versions of the
  same.
- Every new module follows the OKF layout (L1 cards → L2 DL → L3 axioms + provers) and adds negative controls.

---

## 3. Sequencing and milestones

```
 WP1.1 spike ──► WP1.2/1.3 ──► WP1.4 slice ──┬─► WP2.4 plans ──► WP4.1/4.3 ──► WP4.5 X1–X4
                                              │
 WP2.1/2.2 taxonomy+cards ────────────────────┤
 WP3.1–3.4 capabilities/workflows/constraints ┴─► WP3.6 resolution ──► WP7.1/7.2 e2m via CRAM
 WP5.1/5.2 audit model+hooks (start with WP1.4) ──► 5.3–5.5 ──► 5.6/5.7
 WP6.1 CQ catalogue (early, drives WP3 content) ──► 6.2/6.3 ──► 6.4/6.5 ──► D6
 WP3.5 norms (after D-C3) ──► 5.7 ALCOA+ verifier, normative CQs
```

| Milestone | Content | Acceptance |
|---|---|---|
| **M1 Runtime** | D-C1 decided; first pick by designator on the twin | One `perform(picking-up)` on Cell 01 |
| **M2 Vertical slice** | `nominal` + `identity_swap` as CRAM plans, with trail entries from day one | Same routing and monitors as the legacy runner; trail verifies |
| **M3 Taxonomy & knowledge** | Category ontology + cards; capability ABox; workflow and constraint registries | OKF `make check` passes; alignment proofs; ASP / z3 / monitors generated from one registry |
| **M4 All episodes in CRAM** | 5 legacy episodes + plan_g050 via CRAM; device names gone from plans | Regression matches; lint clean |
| **M5 Modularity** | X1–X4 | Each swap runs or is refused with a named constraint; substitution proofs in CI |
| **M6 Audit** | Hash chain, evidence store, sign-offs, NEEM export, verifiers | Tamper test caught; replay reproduces the execution tree |
| **M7 Understanding** | CQ engine + U(a) gate + explanations | ≥ 90 % of the CQ suite correct and grounded on reference episodes; 100 % of answers carry grounds |
| **M8 Demonstrators** | D1–D6, videos | Each with trail, verifier report and CQ transcript |

---

## 4. Decisions needed (with recommendations)

| Id | Decision | Recommendation |
|---|---|---|
| D-C1 | CRAM runtime | **coraplex** (revision 2), with HADL as the specification language. Revive your checkout outside ResearchSpace |
| D-C2 | ROS 2 in the loop for the twin? | Not at first: coraplex `no_ros` plus an in-process Isaac backend. ROS 2 Jazzy (GiskardWrapper / actions) for real devices later |
| D-C7 | Where the coraplex fork lives, and its commit rules | Your fork `beetz-m/cognitive_robot_abstract_machine`, new branch from `robot-scientist-ur-perform`. Its AGENTS.md forbids Claude co-author trailers, which conflicts with your other repos. Needs your call |
| D-C8 | Corpus conflicts K1–K11 (map §5) | Resolutions as proposed in the map, settled in WP2/WP4/WP5 cards |
| D-C3 | Regulatory scope | "GxP-aligned audit and data integrity": Annex 11, ALCOA+, Part 11 *as design target*, GLP for study records, ISO 10218 / TS 15066 for robot safety. No compliance claim |
| D-C4 | Trail store | Append-only JSONL + content-addressed blobs now; MongoDB / NEEMHub-compatible export later |
| D-C5 | Where shared artefacts go | New OKF sub-modules in LabAutomationTwin. RS gets proposals only (`proposals/`), as before |
| D-C6 | NL front end | Optional, after M7. The answer content always comes from the query engine |

---

## 5. Risks

| Risk | Mitigation |
|---|---|
| PyCRAM / ROS version mismatch on Ubuntu 24.04 / Python 3.12 | The 1.1 spike first, in an isolated venv. The fallback is a thin CRAM-semantics layer (designators, perform, failure handling, policies) of our own, keeping the HADL spec |
| Isaac and CRAM in one process (event loop, stepping) | Process modules own the stepping. CRAM tasks are cooperative coroutines driven by the sim clock |
| Resolution latency of OWL reasoning at runtime | Classify offline, compile to lookup tables and ASP facts; reason at runtime only on changed fluents |
| Taxonomy over-engineering | Categories are admitted only if a workflow uses them or a CQ asks about them (the CQ catalogue drives the content) |
| Regulatory over-claiming | Clause registry with explicit realisation type; uncovered clauses reported; twin signatures labelled simulated |
| Constraint drift between planner, verifier and monitors | Generated from one registry; an equivalence check in CI |
| Loss of the current twin behaviour during the port | Legacy episodes as oracles until M4 |

---

## 6. First concrete steps (in order)

1. Revive coraplex in `env_cram` from your `robot-scientist-ur-perform` branch, outside ResearchSpace, and reproduce
   the UR lab-cell perform (WP1.1, revision 2).
2. Draft the category ontology skeleton and 6 category cards: PickingUp, Placing, Transporting, Dispensing, Imaging,
   ToolCoupling (WP2.1/2.2).
3. Draft the first 20 CQs (WP6.1) for the `nominal` and `identity_swap` episodes. They fix what WP3 must represent.
4. Define the process-module interface and wrap R01 + L10 + L09 (WP1.3) → milestone M2 with audit entries (WP5.1/5.2).
