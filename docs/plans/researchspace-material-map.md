# ResearchSpace material for the CRAM robot science assistant

Status: collected 2026-10-17 by a read-only sweep of `~/ResearchSpace`. Nothing in ResearchSpace was modified.
Companion to [cram-science-assistant-plan.md](cram-science-assistant-plan.md). Section 9 lists the plan changes
that follow from this material.

**Path prefixes**

| Prefix | Path |
|---|---|
| `RS` | `~/ResearchSpace` |
| `CR` | `RS/foundation/software/cram` (a CRAM monorepo checkout) |
| `UC` | `CR/experiments/aicorworks_reference_use_cases` |
| `OKF` | `RS/foundation/okf` |
| `C01` | `RS/projects/robot-scientist/cell-01/AICOR_Cell01_Codex_Handoff` |
| `RSV` | `RS/verticals/robot-scientist/okf` |
| `LA` | `RS/writing/aicor-lab-automation` |

**Maturity legend**

| Label | Meaning |
|---|---|
| idea | prose, slides, briefs |
| spec | schema, contract or plan with fields fixed |
| formal | DL/FOL, reasoner-consistent |
| proved | z3/HermiT/evaluator checks pass |
| impl | code exists |
| run | executed with recorded results |

Most items marked proved are checked over symbolic ABoxes or simulated traces by their own author. None has been run
on hardware.

**Method.** Six parallel read-only sweeps covered:
- the CRAM software and git history;
- the CRAM/designator OKF modules and kb;
- the AICOR/VRB/RIG and topic OKF modules;
- the robot-scientist project and the verticals;
- writing, the book and executive;
- studios, docs and tools.

I also checked the CRAM checkout directly (git branches, interpreter, imports).

---

## 1. Ten findings that change how we build it

1. **You already have a CRAM lab prototype: CRAM tryout `uc_ccr` (Culture–Challenge–Rescue).** It uses the same
   experiment family as our e2m work. It is written with **coraplex** (PyCRAM's new name since 2026-06) designators and
   includes:
   - a GAP with per-step constraints;
   - a SHA-256 hash-chained audit trail with a **two-column verdict** (realisation vs experimental validity);
   - an EIG scientific-executive loop;
   - an Experimental Critic;
   - "belief moves only on a valid finding";
   - an EQL competence spec that answers audit questions by inference.

   On the unmerged branch `robot-scientist-ur-perform`, the loop was *performed* on a UR10e + Robotiq in bullet,
   headless (retrieve → image → return; suite 25/25 per the commit message).
2. **The runtime target is coraplex on ROS 2 Jazzy, Python 3.12, with ROS optional.** It is not "PyCRAM on Noetic", as
   the first plan assumed.
   - `coraplex/doc/source/installation.rst`: "tested with ROS2 Jazzy / Ubuntu 24.04 / Python 3.12".
   - Classic process modules are gone. Execution is the giskardpy motion-statechart QP controller, ticked in-process on
     the semantic digital twin (simulated) or via `GiskardWrapper` over ROS 2 (real).
   - `ExecutionEnvironment(SIMULATED|REAL|NO_EXECUTION)` selects the mode.
3. **The checkout in ResearchSpace is a copy and does not run here (I checked this).** `CR` was copied on 2026-09-30
   from `~/WORK/cognitive_robot_abstract_machine`, which no longer exists on this machine.
   - Its `.venv` points to a missing uv-managed interpreter, and its editable `.pth` entries point into `~/WORK`.
   - With the system Python 3.12, `pybullet` and the `rclpy` shim import, but `coraplex`, `krrood`,
     `semantic_digital_twin` and `giskardpy` do not, and `mujoco` fails on a cffi mismatch.
   - The sources and the full git history are intact, including `robot-scientist-ur-perform` with
     `common/perform_labcell.py`, `semantic_digital_twin/robots/ur.py`, `run_labcell_campaign.py` and `cram_viz/web/cq.html`.
   - Reviving it means a fresh clone or worktree outside ResearchSpace plus `uv sync`.
4. **No lab action categories, lab process modules or lab semantic annotations exist anywhere.**
   - No dose, image, incubate, QC, quarantine or tool-change designators exist in coraplex.
   - `semantic_digital_twin` has no plate, well or incubator classes, no UR5e, and has FR3 only as part of GARMI.
   - The lab entities in `uc_ccr` are experiment dataclasses and JSON.
   - Our Isaac twin plus the Cell 01 contracts are the first lab-grade substrate.
5. **The Cell 01 contracts are detailed and binding.** The CRAM implementation must honour:
   - the 8 CRAM designator schemas;
   - the lifecycle;
   - the acceptance rule;
   - about 30 monitor templates with failure_blocks and recovery;
   - the 10-dimension critic vector;
   - the NEEM record schema;
   - the action frame plus SHACL understanding shape, with B21 (full frame) and B22 (abstain otherwise);
   - H4 authorisation;
   - D008–D016.

   See §4.
6. **Many ideas are formalised, but they are not reconciled with each other.** Your papers use at least five designator
   schemas, six category taxonomies, five warrant definitions, five status vocabularies, four names for the trace, and
   three different lab device sets. §5 lists the decisions the implementation must take. That is also a contribution in
   its own right.
7. **The audit trail exists in code: `UC/common/audit.py`.** It has `Constraint(cid, source, text, verdict, kind)`,
   `AuditTrail.record/verify`, a SHA-256 chain and 6 tests. VRB documents it as "the same machinery TraceBot built".
   The richest field specification is the Cell 01 `neem_record_schema.yaml` plus the RSV `evidence/evidence-schema.json`.
   Four audit formats coexist and need one canonical one.
8. **Competency questions answered by the robot about its own episode already have a working pattern:**
   `cram-viz-check <spec>`. It runs EQL competence queries headless against expectations and exits 0 or 1.
   - The CCR spec `RS/tools/research_os/instruments/cramviz/specs/ccr-two-column-competence.yaml` passes 5/5.
   - The KnowRob3 competence panel has about 144 queries.
   - What is missing is CQs answered from **runtime state and trace**. Today they are TBox, z3 or scene-only.
9. **Substitution and change are formalised and proved:**
   - the Σ algebra {σ_rule, σ_body, σ_instrument, σ_timing, σ_realize} and the change taxonomy Δ_R/Δ_N/Δ_G, both in VRB;
   - functional substitution by capacity, in improvised-tool-use;
   - σ_agent and qualified capability, in Siemens;
   - the measurement-binding lattice no_match ⊂ capability_match ⊂ provisional ⊂ validated, in RSV;
   - composition of σ generators, tested in `UC/warrant_composition.py`.

   One open contradiction: is a norm tightening a warrant-preserving σ_rule or a Δ_N that needs re-evaluation? See §5.
10. **"TraceBot" means two things in your corpus.** In the lab papers (LAYER2 §6.4, RRA §11) it is perception
    verification by imagination. In AICORworks it is trace and audit generation. The robot science assistant needs both:
    RoboKudo/NaivPhys4RP-style verification as **verifiers** that write into the audit trail (RobAuditor quadruple).

---

## 2. The CRAM tryouts: what was done, in order, and where it stands

127 commits by you in `CR`, 2026-08-04 → 2026-09-26, almost all written in Claude sessions. Branch names are in
parentheses.

| When | What | Commits | Status | Lab relevance |
|---|---|---|---|---|
| Aug 4 | Force-dynamic templates: action categories as hybrid automata (pour, cut), `coraplex/force_dynamic_templates` | `256d1df16` | 31 tests; verified only in isolation (not bound to SDT, segmind or ROS) | Category = causal template; anticipatory stop maps to dispensing |
| Aug 4 | Household normative core (`household-placement-norms`) | `54d5257fa` | 43 tests | Norm and consent-gate pattern for lab rules |
| Aug 5–7 | **AICORworks VRL cells.** UC1 environmental monitoring has GAP plus per-step regulatory constraints (GMP Annex 1, ISO 10218-2, Annex 11, AI Act), a hash-chained audit, UR10e/KUKA IK, and an Adapt panel with three levers (robot swap / device swap / rule 5 N→3 N). UC2 is HPLC with three SiLA-2 vendor profiles. UC3 is a 96-well microplate under timing windows. | `0c85ede82`, `5273589eb` | run; **motion synthesised from keyframes, not performed** | Highest: regulation-linked constraints, audit, swaps |
| Aug 8–10 | Household placement with real coraplex `TransportAction`s; guarded `--perform`; **perform in bullet without ROS** (flattened URDFs); placement rules as krrood EQL inference rules; designator resolution as an EQL query | `273b53501`, `9680059ae`, `4b42221fe`, `470f3c08d` | run | Proves the no-ROS perform path and EQL resolution |
| Aug 11–12 | Action designators as KR&R objects in cram_viz: frame ⟨κ,R,I,C,Φ,β,π⟩, resolution as unification, three-level warrant, per-phase monitors, `ActionEpisode`, re-designation, episodic NEEM memory, prospection, Ground & Emulate gate, `gate_discrimination` Phase 0 | `1826a9828`, `b41b5370a`, `43cafb984`, `ade06b6f9`, `0a628f776`, `4aa890d26`, `3c784bf58` | impl; gate harness partial (independent judge column null) | Designator calculus, gate, episodic memory |
| Aug 26–31 | Six household "faces"; headless `cram-viz-check`; live SDT bridge; σ_realize and σ_instrument warrant tests (the HPLC swap is warrant-invariant only inside the shared [0.1, 50] µL envelope) | `ef84c9ab8`, `ea6d4da8f`, `148cb00f8` | run/tests | CQ-as-regression; device-swap envelope |
| Sep 4 | σ_timing (UC3); **composition of σ generators**: the warrant survives on the intersection of regions, independent of order | `3857540bb`, `6c86dd9a0` | 7 tests | Substitution closure |
| Sep 5–8 | **`uc_ccr` Culture–Challenge–Rescue.** GAP + two-column audit (NR3: every realisation constraint enforced, negative control violated → invalid experiment); measurement-binding lever (swapping the imager flips validity #1005). P1 SE loop picks the next experiment by EIG; P2a perform stand-in on PR2/apartment; P3 Experimental Critic; P4 belief moves only on a valid finding; F1 fix (binomial k-of-12 readout); EQL `AuditConstraint`s | `1da28e22c`, `24d978074`, `46bd805e5`, `8205db7fe`, `a8b4511c6`, `a2094ec7b`, `159a6334a`, `119ec645e` | tests 8/8, 5/5, 4/4; ledger claims conferred | **Direct predecessor of our system** |
| Sep 7 (`robot-scientist-ur-perform`) | **CCR loop performed on UR10e + Robotiq** in bullet, headless: new `semantic_digital_twin.robots.ur.UR` (no motion mapping needed); `perform_labcell.py` (ParkArms + PickUp + Place, attachment grasp, < 2 mm); red-team fixes (NR3 verdict sensed from the episode); soundness sweep over all ground truths | `47e04011b`, `1bbcfd151`, `4b863d0bc` | run (suite 25/25 per commit message); **unmerged** | Proof that coraplex + a fixed-base UR works for lab legs. Dosing, tool change, rail and devices were not performed |
| Sep 18–26 | Real giskard-recording seam (σ_realize); Agilent G7129A vialsampler for Isaac with PhysX and RMPflow ("written, unrun"); ontology / ABox / **CQ explorers** (`cq.html`: CQ → theorem → proof); request-conditioned placement | `d9da533b5`, `7b7803b9b`, `56783b120`, `52e71e8d8`, `54a9c02a1`, `798fe2ae3` | impl, Isaac unrun | Isaac backend precedent; CQ UI |

**Write-ups of these tryouts**

| Path | Content |
|---|---|
| `RSV/scenarios/pillar4-ccr-simulation-SCOPE.md` | Plan and log of P1–P5, P2a/b; "motion mappings PR2/tiago/hsrb/stretch, not the CCR cell's UR" |
| `RSV/scenarios/pillar4-audit-2026-09-06.md` | Finding F1: the loop resolved onto the wrong model. Lesson: test every ground truth, not only the demo case |
| `RSV/scenarios/pillar4-usd-realization.md` | Isaac P2b-usd, blocked at the time (no GPU). We have a GPU and Isaac 6.2 |
| `RSV/scenarios/p2b_phys_step1_labcell_load.py` | Reproducer for the UR lab-cell load |
| `OKF/cram/action-designators/10-episode-demonstrations.md` (+ `out/episode-demonstrations.json`) | Live cram_viz runs of "fetch the milk": clean, belief repair, slip→regrasp, drop→abstain, rupture→abstain |
| `OKF/cram/artifacts/realization-map.html` | Theory → coraplex / SDT / giskardpy / segmind / krrood map with Done/Done*/open status |
| `OKF/manipulation-actions/DEFERRED-REGISTER.md` G1 | "Perform runtime unavailable": the dependency problem in the viewer venv |
| `OKF/vrb/L1…/concepts/lab-vrl-*.md` | The three VRL cells with reuse percentages (robot swap 91 %, rule swap 97 %, vendor swap 98–99 %) |
| `CR/cram_viz/docs/NEXT-SESSION-action-designators.md` | Phases A–D (represent / reason / execute / tool), largely executed |

**What was not tried:**
- coraplex on Isaac;
- coraplex on any Cell 01 component (FR3 plate arm, rail UR5e, tool changer, L12, L17, L10, L21, H4);
- dosing or tool change as performed actions;
- device (non-arm) actions as designators;
- an audit trail fed by real execution rather than by the plan.

---

## 3. Material by work package

Each WP lists: *basis* (adopt as is), *reuse code*, *theory* (formal), *ideas* (papers/notes), *open* (deferred
problems we will hit).

### WP1 CRAM runtime, world bridge, execution

**Basis**
- `C01/docs/Cell01_Realization_Plan.tex`
  - §5: six CRAM duties (interpret → open designators; ground; prospect; accept; execute with 8 monitor classes;
    diagnose/repair/abstain; NEEM + critic).
  - §6: seven roles with separate interfaces (Planner, Identity/Material, Manipulation Exec, Observation, Validity
    Critic, Provenance, Exception).
- D010 (CRAM = manipulation executive; the scientific executive sits above it).
- `C01/docs/SDT_ARCHITECTURE.md`: state ownership; query-driven fidelity.

**Reuse code**
- coraplex designator and plan API:
  - `CR/coraplex/src/coraplex/robot_plans/actions/base.py`: `ActionDescription`; pre/post conditions are krrood EQL
    expressions.
  - `core/`: PickUp, Place, Reach, Navigate, ParkArms, SetGripper, Open/Close, Detect, LookAt.
  - `composite/`: Transport, PickAndPlace, Pouring, Mixing.
- Plan language: `plans/factories.py` (`sequential`, `parallel`, `try_in_order`, `try_all`, `monitor`, `repeat`).
- Failures: `plans/failures.py`.
- Execution: `execution_environment.py`, `plans/executables.py` (`GiskardExecutable`).
- `robot_plans/motions/base.py` and the alternative motion mappings.
- UR robot class and lab-cell perform: branch `robot-scientist-ur-perform`.
- No-ROS shim: the `.venv` `ros_shim.py` and `coraplex/ros/__init__.py` fallback.
- Isaac precedent: the UC2 `isaac/` vialsampler backend (unrun).
- Cell 01 grounding:
  - `C01/sdt/grounding.py` (`SDTGroundingQuery`, `GroundedComponent`);
  - `C01/simulation/isaac_sim/biophysical_v2/usd_event_bridge.py` (`apply_verified_l12_to_usd`, which refuses invalid
    records).

**Theory**
- `OKF/cram/L2…/cram-capabilities-dl.md`: the executives as components.
- `OKF/cram/concurrent-reactive-plans`:
  - task-status DL and failure DL;
  - CP1–12 plan-language axioms, FD1–9 failure axioms, OP1–10 operations, PD1–10 designator semantics.
- `kb/dl-axioms/aicor/process-control-alignment-dl.md`: every process condition needs control, monitor, diagnosis,
  revision and evidence counterparts.
- AICOR `executive-specification.md`: Safe / Sound / Cognizant / Live / Complete / Faithful.

**Ideas**
- JAIR `07_cram_realization`: compile → infer → evaluate → commit → validate → record; preparation / commitment /
  activation kept separate.
- GARMI runtime contract: `fail` removes a candidate; `unknown` blocks commitment; commitment freezes the belief and
  norm versions; a world change invalidates before dispatch.
- RRA constitution: 16 statuses and the recovery loop.
- AAMAS: six agent roles as candidate modules.
- Book ch14: runtime-reasonable plans; monitors and traces as runtime structures.

**Open**
- R16: no projection of concurrent-process interference, but Cell 01 runs devices in parallel.
- No process-module concept in the DL; it appears only in reconstruction prose.
- No Isaac backend for coraplex.
- No FR3 plate-arm or rail-UR5e robot class.
- Device actions (L10/L12/L17/L21/H4/TCM) have no executable type.

### WP2 Action-designator taxonomy

**Basis**
- Cell 01 `sdt/schemas/cram_designator_schemas.yaml`: retrieve, store, transport, dose, incubate, image, qc,
  quarantine; lifecycle; required bindings; monitors; evidence outputs; failure routing.
- `C01/sdt/cell01_sdt_overview.yaml`: capability verbs per component.

**Theory**
- `kb/dl-axioms/cram/ontology/action-category-dl.md`:
  - effect partition: ObjectDisplacement, ConfigurationChange, SubstanceManipulation, SurfaceTreatment,
    ConnectingAction, InteractionAction, MaintenanceAction;
  - specialisation ⊑ vs partonomy ◁ as two orthogonal relations;
  - category = ⟨Int(C) roles + telos, Caus(C) force-dynamic automaton⟩.
- `OKF/cram/TASK-TAXONOMY.md`. Family **B, machine tending**, fits L10/L12/L17/L21. The rest map as:

  | Family | Cell 01 use |
  |---|---|
  | A | transport |
  | C | storage (hotel) |
  | D | purpose-constrained processing (dosing) |
  | E | process control (incubation) |
  | H | dispose |
  | K | inspect (QC, imaging) |

- `OKF/cram/plan-schemata/00-schemata.md`:
  - 7-part GAP schema (pre / body / eff / succ / monitor / repair);
  - `tend(M, load, config) = access · load-into · configure · start · monitor-until(done) · access · unload`.
- `OKF/manipulation-actions`:
  - C_cat = ⟨Name, D, IS, CS, Θ, M_template, π_template, Φ_phase, mastery_spec⟩;
  - A_inst;
  - phase structure (one control regime and termination predicate per phase);
  - intentional vs causal failure independence.
- Force-dynamic automata: `OKF/cram/action-ontology/L3…/pour-fd-automaton.md`, `cut-fd-automaton.md`,
  `open-close-articulated.md`, with z3 provers. The pour automaton's anticipatory stop maps to dispensing.
- `OKF/designator-inference`: event designators D_i = ⟨I_ref, AD, SD, MD, t, conf, prov, verdicts⟩. This is the audit-side
  counterpart of action designators.
- `OKF/knowrob3`:
  - seven-facet frame (category-owned ActionSchema separated from bindings, so subsumption is scene-free);
  - designator calculus (subsume, diff, project, check, invert, query).
- `RSV/L2…/scientific-action-designator-dl.md`: Measure, Replicate, Intervene, DiscriminateHypotheses, Perturb, Wait.
- `RSV/L2…/designator-refinement-dl.md`: Material → SceneGrounded → BodyMotion; REF-CQ-1..6 proved with z3.

**Ideas**
- `RS/writing/aicor-garmi-household-assistant/shared/THREE-MANIPULATION-CLASSES.md`. **Transport / Operation /
  Transformation** maps directly onto Cell 01:
  - plate moves → Transport;
  - incubator, imager and QC as stateful co-actors → Operation, with safe-to-start, safe-to-interrupt and safe-to-open
    critics;
  - liquid handling, irreversible at every step → Transformation.

  Composition uses `;` and coupling `⋈`.
- Siemens `verticals/siemens/okf/docs/action-designator-language.md`. The most mature slot grammar:
  - slots `:roles :goal{intended,prohibited} :frames :parameters :control-policy :preconditions :monitors
    :success-criteria :recovery-policies :evidence :output`;
  - goal kinds: achievement vs maintenance;
  - operators `;`, `A[B]`, `∥`.

  Also the 4-level taxonomy in `nacelle-manipulation-action-category.md`: task template / control mode / motion
  primitive / recovery action.
- `LA/shared/LAYER2-conceptual-framework.md` §6.1:
  - lab designator d = ⟨category, parameters, phases, goals, local constraints, interval constraints, evidence,
    warrant⟩;
  - verb list: grasp, place, open, close, transfer, aspirate, dispense, mix, wash, incubate, inspect, measure.
- `LA/RRA/sections/10-designator-calculus.tex`: bind → ground → compile → effect → classify.
- `C01/references/AICOR_CRAM_Based_Robot_Scientist_Assistant_Report.pdf`:
  - §9 scientific action vocabulary: observe, intervene, discriminate, replicate, control, wait, refine,
    terminate/quarantine;
  - §10.3 nine-phase CRAM realisation.
- `RSV/scenarios/hepatotoxicity-rescue-execution.md` §3: the 8-phase `AdministerAndImageTemplate`; designators with
  `expects`, `validity_conditions` and `freshness_key`.

**Open**
- MANIPULATION_ACTIONS-D1: no intentional-failure axis in AICOR ("clean but wrong for the protocol").
- Where does the task-category vs action-category boundary fall?
- Incubate and hold are maintenance goals and need their own category type.

### WP3 Explicit knowledge: capabilities, workflows, constraints, regulations

**Device capabilities**
- Basis:
  - `C01/sdt/components/*.yaml`: capabilities, action_contracts (e.g. L12 `dose_well`), limits.
  - `C01/simulation/.../06_semantics/asset_contracts.yaml`: required states per device.
  - Siemens `qualified-capability-dl.md`: physical vs *qualified* capability (calibration lapse).
  - VRB **CF2**: a capability match does not entail a valid measurement binding.
  - AICOR `competence-capability-taxonomy` (L1–L3), `embodiment-capability-grounding`, `self-knowledge-constraint`.
  - `OKF/tool-use`: a wielded tool extends the body, so the R02 tool changes R02's capability.
  - `OKF/vrb/L2…/lab-automation-device-dl.md`: device functions and SiLA2/LADS interfaces.
- Ideas:
  - `OKF/vrb/presentations/aicorworks-device-knowledge.html`: instrument → SDT.
  - EIC `capability-based-binding`: only the failed resource assignment is invalidated.

**Workflows**
- Theory:
  - AICOR `generalized-action-plan`, `runtime-reasonable-plan`.
  - `RSV/L2…/experimental-workflow-dl.md`.
  - `OKF/cram/L3 integrator-axioms` + `schedule_eval.py`: deadline-aware concurrent scheduling.
  - `operate-monitor-axioms` (program-load compatibility; unload gated on verified completion).
  - `process-control-axioms` (setpoint regulation, i.e. incubation).
  - `compositional-assessment`: margin ledger; assume/guarantee sub-episode contracts; time margins such as
    incubation windows.
- Reuse code: the `gap.py` GAPs of UC1/UC3/uc_ccr; VRB `traces/kinase-assay*.trace.json` (interval-fluent trace
  format).
- Ideas:
  - `LA/shared/REPRODUCIBLE-RUNNING-EXAMPLE.md`.
  - `C01/docs/SESSION_HANDOFF.md`: first slice is retrieve → verify identity → dose one well → validate → commit → NEEM.

**Constraints**
- Basis:
  - `OKF/vrb/L3…/axioms/lab-automation-constraints.md`: C-S/W/E/O/M/D in DL plus interval FOL; 9 z3 checks.
  - `RS/writing/autonomous-lab-report/latex/report.tex`: 25-constraint catalogue and its translation into motion
    constraints.
- Theory:
  - VRB `sdt-grounding-dl.md` (+ `motion-soundness-axioms.md`): the norm and the motion constraint are *one object at
    two altitudes* (EffortBound, KeepInRegion, Standoff); feasible ⇒ not forbidden.
  - `trajectory-space-dl.md` + `classify_trajectory.py`: a run is forbidden, successful or unsuccessful.
  - `OKF/cram/L3 r19-monitor-coupling`: monitor threshold = f(KPI).
  - `bounded-risk-detector` (PHAM DET).
- Reuse code: `UC/uc1_environmental_monitoring/gap.py`, `Constraint(id, standard, text, kind)` per step.
- Cell 01:
  - `sdt/schemas/monitor_templates.yaml`: 7 categories, about 30 templates, each with failure_blocks and recovery.
  - `biology/ontology/monitoring-rules.yaml`: challenge/rescue authorisation, contamination triggers, the 8-step
    diagnostic order, evidence promotion.
  - `contamination-and-asepsis.md`: "automatic tool change does not guarantee cleanliness".

**Regulations and norms**
- Basis:
  - `OKF/normative-admissibility` (Norm ⟂ causal admissibility; ask-permission threshold; norm provenance; conflicts;
    responsible refusal).
  - Siemens `regulatory-constraint-object.md`: clauses are first-class SDT objects; each postcondition links to its
    clause.
  - `OKF/vrb/L0…/demonstrator/aicorworks-vrl-cells.md`: standards encoded (Annex 1/11, ALCOA+, AI Act Art. 12,
    ISO 10218-2, SiLA2/LADS).
  - EIC `constraint-compilation`: executable constraints vs documentary or human-review obligations.
  - EIC `gmp-annex-11-15.md`: "selected requirements become runtime checks; others remain documentary controls".
  - `OKF/cram/L2 request-conditioned-placement-dl.md`: authority and scope of a request vs standing norms; this is
    the model for quarantine release.
  - `purpose-constrained-processing-dl.md`: Purpose + ForbiddenRegardless.
- Ideas: `OKF/vrb/presentations/aicorworks-constraint-extraction.html`: mining constraints from device docs and
  regulations.
- **Gaps:**
  - No GLP anywhere. 21 CFR Part 11 appears only in VRB pitch material.
  - No Cell 01 regulatory constraint objects (GMP, BSL-2).
  - Norm provenance and conflict calculus are open (normative CQ-4).

### WP4 Modularity: device exchange, step substitution, workflow change

**Basis**
- VRB `warrant-preserving-lab-program-FRAMING.md` and `-STATUS.md`: the Σ algebra, ≡_W, Σ-closure proved with z3.
- VRB `change-taxonomy-dl.md`: realisation / norm / account transitions → preserve, re-evaluate, or successor warrant.
- `UC/warrant_composition.py` (7 tests); σ_instrument envelope (UC2); σ_timing (UC3).

**Theory**
- `OKF/improvised-tool-use`: FunctionalRequirement + substitution by physical capacity rather than catalogue identity.
  This is the closest formal pattern for exchanging devices and steps.
- `OKF/cram/L2 resource-selection-dl.md`: stewarded instance selection, provisioning, restoration.
- Siemens `g7-agent-substitution-dl.md`: the warrant class is independent of the agent.
- `OKF/recompilation`: state-preserving splice of a running commitment, triggered by repair, a changed monitor or a
  revised assumption. This is the in-run workflow change; it is disjoint from replanning.
- `OKF/category-revision`: when a substitute device creates a new subtype; impact-scaled evidence threshold.
- `OKF/cram/concurrent-reactive-plans/structured-reactive-plan-dl.md` + `plan_transformation_eval.py`: plan as an
  object (R14/R15).
- RSV `scene/culture-challenge-rescue-binding.json`: the measurement-binding lever.

**Ideas**
- `LA/SLAS` §04: qualification matrix for change.
- `RS/writing/ral-competence-portability`: the program is fixed and transfer cost moves into the digital BWS plus
  bindings (results still `\todo`).
- `foundation-studio/problems/competence-portability/problem.yaml`.
- EIC `h4-rebinding`, with a named fallback.

**Open**
- When a splice exists vs a full replan (recompilation CQ-6).
- When an episodic fix becomes a category change (category-revision CQ-6).
- Substitution trust and requirement abstraction (improvised-tool-use).
- Cell 01 OPEN_TASKS P1: "re-specialization to alternative component bindings".

### WP5 Audit trail (TraceBot style) and NEEMs

**Basis**
- Cell 01 `sdt/schemas/neem_record_schema.yaml`: lifecycle sections open_designator → grounded → commitment →
  execution → monitors → failures → repairs → verdict → routing.
- `critic_vector_schema.yaml`: 10 dimensions with per-action overrides.
- `physical_workflow.py`: `build_l12/l17_neem_record`, `evaluate_commitment_acceptance`.
- `culture_ledger.py`: commit only validated records; keep rejection traces.
- SEC biconditional (RSV z3): Commit ⟺ Realized ∧ TargetVerified ∧ IdentityVerified ∧ DeviceValid ∧ MonitorPass.

**Reuse code**
- `UC/common/audit.py` (+ `test_audit.py`): hash chain with constraint verdicts.
- `CR/cram_viz/.../web/panels/audit`: in-browser chain verification.
- coraplex ORM: `krrood.ormatic ... to_dao(plan)`, queried with `get_dao_class(ActionDescription)`. Plan nodes carry
  status, start/end and reason.
- RSV `scene/culture-challenge-rescue-audit.json` + `evidence/evidence-schema.json`, with NR3 and malformed negative
  controls.
- Siemens `scene/episodes/*.yaml` + `run_episode.py`: `.neem.json` with expected verdicts under fault injection.

**Theory**
- AICOR:
  - `evidence-bearing-trace` ("a log is not automatically evidence; the regime fixes the schema");
  - `trace-schema`, `verdict-component`, `accountable-action-loop`, `faithful-report`;
  - DR1–8 diagnosis/repair routing.
- `OKF/cram/L2 cram-memory-dl.md`: NEEM = Intention / ActualCourse / Divergence.
- `L3 satisfies-reference-axioms` (`conformsTo`: right result, wrong procedure).
- `co-refers-with` (equating the request and executed designators).
- `OKF/critic-specification`: detection profile, blind spots, fault-injection adequacy, partial oracle.
- `OKF/designator-inference`: provenance and confidence per slot.
- VRB `warrant-preserving-lab-program-FRAMING.md`: the audit entry is ⟨grounds, constraints discharged, verdict,
  disposition⟩.

**TraceBot, RobAuditor, NEEMs**
- `OKF/vrb/L1…/concepts/{tracebot,lab-tracebot,semantic-execution-tracing,robauditor,neem}.md`:
  - three trace layers: RoboKudo perception, NaivPhys4RP imagination, RobAuditor verification;
  - verifier output (Ds, Cf, Ed, Er);
  - NEEMHub content hashing;
  - comparison by execution-tree isomorphism.
- `OKF/cram/deep-action-observer` slide 19: TraceBot canister pick-and-place.

**Ideas**
- Book ch07 `c7-9-10-cram2-evidence.tex`: one trace contribution per commitment field (task reading, belief, warrant,
  candidate, monitors, observations, residual, rejected alternatives, disposition), with an "evidential ceiling".
- JAIR: versioned designators with resolution certificates.
- SLAS: separate "command sent / physical event / semantic commitment satisfied", which prevents duplicate dispensing on
  retry.
- `LA/shared/REPRODUCIBLE-RUNNING-EXAMPLE.md` §8: replication package.

**Gaps**
- No e-signature or "who signed" model; the nearest is `authorization: human_review_required`.
- In-memory NEEM persistence debt (knowrob3).
- Live NEEM export is future work (Cell 01).
- Four coexisting audit formats.

### WP6 Understanding: competency questions about its own activity

**Basis**
- `C01/biology/ontology/robot-understanding-contract.md`: U(a), 13 items.
- `robot-action-frame.yaml`: required slots, 3-level recovery, authorisation.
- `aicor-biology-shapes.ttl`: SHACL `ExperimentActionUnderstandingShape`, a ready **machine-checkable understanding
  gate**.
- B21/B22 in `biological-domain-axioms.md`.
- `state-of-understanding.md`: 13 epistemic modes and grammatical rules ("I observed…", "Model M predicts…").
- `robot-understanding-and-communication.md`: communication acts, e.g. "Why are you not dosing well A03?".

**CQ sets to merge**
- `C01/biology/ontology/COMPETENCY-QUESTIONS-BIOLOGY.md`: 33 questions; Q28–33 are about robot understanding.
- CRAM report §19: 16 agent CQs.
- `RSV/L2…/competency-questions.yaml`: CQ-1..27; executable TBox/z3.
- REF-CQ-1..6.
- VRB `competency-questions.md`: 54 questions; CQ-21..29 devices/RSA, CQ-11..15 and 63/64 warrant.
- AICOR `COMPETENCY-QUESTIONS.md`: Bloom ladder.
- `kb/dl-axioms/aicor/competence-capability-taxonomy-dl.md`: CompetenceQuestion partitioned by Warrant / Commitment /
  Regulation / Evidence.
- KnowRob3 competence panel: about 144 queries in 9 dimensions, including "actions as knowledge objects" and
  "remembering and accounting".
- `studios/research-tools/ResearchProblemStudio/problems/competence-capability-taxonomy/dossier.md`: graded CQ
  taxonomy.

**Reuse code and tools**
- `cram-viz-check <spec>`.
- CCR spec `RS/tools/research_os/instruments/cramviz/specs/ccr-two-column-competence.yaml`.
- `make cramviz-run SPEC=`.
- `cram_viz/web/cq.html` (on branch `robot-scientist-ur-perform`).
- `kb/logical-axioms/aicor/manipulation-scenario-cq-axioms.md` + `okf_interval_cq.py`: 12/12 interval CQs by z3.

**Theory**
- Book ch10 *Understanding Executive*: understanding = self-model + competence awareness + calibration + explanation
  from within over a NEEM; distinct from the trace and from the critic verdict.
- `OKF/cram/action-ontology/06-narrative-intelligence.md`: understanding = telling the story of your activity; why /
  how / what-if over your own NEEM.
- AICOR `executive-specification`: a faithful report = sound + task-cognizant.
- `OKF/warrant-threshold`: act / gather / abstain at the start, continue, revise and verdict loci.

**Gap**
- No CQ anywhere is answered from **runtime state plus trace**.
- The biology and CRAM-report CQs are prose only.
- Two epistemic vocabularies need reconciling: 8 values in the SDT contract vs 13 in the biology ontology.

### WP7 Scientific executive integration

**Reuse code**
- `UC/uc_ccr_culture_challenge_rescue/se_loop.py`: `expected_information_gain`, `se_step`, `run_campaign`.
- `critic.py` `assess()` → `Verdict(realization, validity, promotable, nr3)`.
- `campaign.py` with the `perform_fn` seam.
- Compare with our e2m (clingo / z3 / Isaac).

**Theory**
- RSV `experimental-critic-dl`, `experimental-verdict-dl`, `experimental-authorization-envelope-dl`,
  `measurement-equivalence-contract-dl`, `semantic-event-commitment-dl`.
- VRB `multi-agent-warrant-dl.md`: six lab agent roles; local vs joint warrant.
- `warranted-inference-dl.md`: refuse / request-evidence / re-ground / re-plan.
- AICOR ledger claims `robot-scientist-*.md`: two-column verdict, NR3/ED2/CF2 separations.

**Ideas**
- `LA/RRA` §04: ScientificActionWarrant bounded by an authorisation envelope, fresh against the twin.
- `LA/shared/TOP-DOWN-FUNCTIONAL-STORY.md`: the 9-step spine.
- `LA/rra-architectural-constitution`: spine Q→(M,H)→P→W→D_s→D_g→D_m→E→T→K→V→(C,ΔM,Γ) and a 10-field interface
  contract κ.
- Siemens `reference-architecture/transformation-contracts.md`: TC-01..10.

### WP8 Verification, evaluation, regression

**Basis**
- Cell 01 OPEN_TASKS P1:
  - CCR scenario family;
  - injected identity / seating / timing / environment / tool / calibration faults;
  - invalid-commit rate with vs without contracts;
  - fault-vs-result diagnosis;
  - replay.
- `C01/simulation/.../07_tests/ACCEPTANCE_TESTS.md`: tool-ID and lock checks.
- `08_docs/P0_BUILD_SEQUENCE.md`: Gates 0–7.

**Ideas**
- `OKF/vrb/presentations/aicorworks-fault-injection-plan.md`: severity hierarchy, detection / false-stop matrix.
- `aicorworks-g1-benchmark-spec.md`: portability.
- `aicorworks-experiments-plan.md`: ablations.
- `C01/references/AICOR_Cell01_SDT_Research_Report.pdf` §13: baselines, metrics.
- `studios/research-tools/ResearchExperimentsDesignStudio/.../structured-action-representations-robotics/`:
  claim→evidence and ablation matrices.
- `RS/writing/knowrob3/table-8.1-experiment-scope.md`: verdict vs outcome, 540 rollouts planned and unrun.

**Lessons**
- F1 audit: test every ground truth.
- `gate_discrimination`: score the gate against an independent judge.
- KnowRob3 claim audit: CQ counts drift between documents, so generate counts from the files.

---

## 4. What the CRAM implementation must honour (Cell 01, binding)

1. **Invariants.**
   - `C01/AGENTS.md` 1–7 and I1–I7, all proved per `RSV/docs/cell01-invariant-crosswalk.md`.
   - Never silently invent designator values, device states, biomedical parameters or evidence (also D016).
2. **Lifecycle.** open → grounded → accepted → executing → executed / repaired / abstained / escalated.
   - The NEEM sections follow it.
   - Commit ⟺ Realized ∧ TargetVerified ∧ IdentityVerified ∧ DeviceValid ∧ MonitorPass.
3. **Acceptance.** Grounded ∧ SemanticValid ∧ CausallyAdmissible ∧ MotionFeasible ∧ Monitorable ∧ EvidenceSupported.
   Refusals carry explicit reasons and the blocked paths.
4. **Critic vector.** 10 dimensions, kept separate. Measurement adequacy is required for image and N/A for dose.
5. **Monitors.** Every `failure_blocks` entry and recovery ladder in `monitor_templates.yaml`.
6. **Authorisation and diagnosis.** Per `monitoring-rules.yaml`. The 8-step diagnostic order runs before anything
   counts as biology.
7. **H4.** A request stays `requested` until it is physically verified. Release happens only by authorisation. Invalid
   runs are kept, never promoted (B20).
8. **Grounding.** Bind to named USD Xforms and interaction frames under `/World/Cell01/...`. Component semantics stay
   stable under hardware substitution.
9. **Refinement.** Material → scene → body refinement preserves goals and evidence obligations. Forbidden refinements
   are not committable (DR1–5).
10. **Understanding.** Every consequential action fills the action frame and passes the SHACL shape (B21); otherwise
    the robot abstains (B22).
11. **Reuse.** A task-knowledge template must re-ground and re-check monitorability and validity. Contracts transfer;
    motions do not (A9).
12. **D008 / D009.** Physical success ≠ validity. A consequential event is committed only after validity.

---

## 5. Conflicts across the corpus and the decision the implementation must take

| # | Conflict | Where | Proposed resolution for the robot science assistant |
|---|---|---|---|
| K1 | Norm tightening (5 N → 3 N): warrant-preserving σ_rule, or Δ_N needing re-evaluation? | report.tex "substitution algebra" vs VRB change-taxonomy CT2, running example §7, constitution §6 | Treat it as Δ_N with mandatory re-evaluation. It is σ-preserving only when the re-evaluation is proved trivially satisfied (old envelope ⊆ new). The audit records both the change and the proof |
| K2 | Designator schema: LAYER2 8-tuple / KnowRob3 7 facets / JAIR versioned / NATIVE SD-AD-MD / Siemens slots / book designator kinds | §3 WP2 | One canonical **category card**: KnowRob3 frame (category-owned schema ⟂ bindings) + Siemens slots + LAYER2 interval constraints + JAIR version and certificate. Map the others in a crosswalk table |
| K3 | Category taxonomy: LAYER2 verbs / KnowRob3 lattice / GARMI Transport-Operation-Transformation / device functions / effect partition / TASK-TAXONOMY | §3 WP2 | Effect partition (AICOR) as the backbone. GARMI's three classes as a cross-cutting facet (reversibility and co-actor). TASK-TAXONOMY families as the lab-task level. Verbs as leaves |
| K4 | Warrant definitions (⟨G,D,B,C,R,W⟩, AAMAS 8-tuple, ScientificActionWarrant, plausible/justified/rational, pass/fail/unknown, book K_t) | LA/*, knowrob3, book ch07 | Commitment K_t reified as the audit unit (book R4). Warrant levels as a field of K_t; pass/fail/unknown as monitor results |
| K5 | Status vocabularies (3-cell partition, 5 validity grades, RPL 6 states vs 5 with `evaporated`, 16 constitution statuses, JAIR tags) | — | Keep three separate axes: plan task status (RPL), designator lifecycle (Cell 01), run classification + validity grade (two columns) |
| K6 | Trace / NEEM / audit / EvidenceBearingTrace naming; four audit formats | §3 WP5 | Recording → EvidenceBearingTrace (regime = GxP-aligned) → NEEM export. The hash-chained audit is a view of the evidence-bearing trace. One JSON schema extends `neem_record_schema` |
| K7 | Competence vs capability; "competence" vs "competency" questions | book, RAL, OKF | Device/robot **capability** (disposition, qualified or not). Scope-indexed **competence** claims. Questions are **competency questions** (OKF usage) |
| K8 | Three device sets (Cell 01 / CCR cleanroom UR10e / hepatotox Hamilton-Opera) | RSV scenarios | Cell 01 is canonical (D012/D014). The others are substitution test cases (WP4 X1/X2) |
| K9 | Runtime substrate (Lisp CRAM notation, coraplex, PyCRAM, cram_viz Python, "CRAM2") | JAIR, GARMI, RAL, book | coraplex for execution, HADL/Lisp notation as specification, cram_viz/krrood EQL for queries |
| K10 | Two epistemic vocabularies (8 SDT / 13 biology) | Cell 01 | Use the 13-mode biology vocabulary for communication and the 8 SDT values for state, with an explicit mapping |
| K11 | "TraceBot" = perception verification (lab papers) vs audit-trail generation (AICORworks) | LAYER2 §6.4 vs VRB | Both: verifiers (RoboKudo / imagination / RobAuditor) write into the audit trail |

---

## 6. Tooling and conventions to reuse

**Tools** (all in `RS/tools`, run from the RS root; we copy or invoke them, never edit them in place)

| Tool | What it does |
|---|---|
| `okf_turn_scaffold.py <domain> <root>` | New-module skeleton |
| `okf_reason.py` | HermiT with the frozen AICOR |
| `okf_reasoned_check.py` | Checks that axioms survived the exporter |
| `okf_cq.py` | TBox CQs from `competency-questions.yaml` |
| `gen_cq.py` | ABox-capable CQ theorems with an OWL-RL closure; hard-coded to GARMI, so parameterise before use |
| `gen_ontology_dl.py`, `gen_system_abox.py` | Explorer views (hard-coded paths) |
| `check_all.py` | Repository check matrix |
| `refarch/` | 37-check reference-architecture gate; fits WP1/WP7. LA/reference-architecture is still a stub |
| `research_os/okf_ingest.py`, `okf_review.py`, `okf_export.py` | Ingest, review and export bundles |
| `make cramviz-run SPEC=` | Runs a cram_viz competence spec |
| `l3_cq_check.py` (robot-scientist vertical) | z3 proof + `answered_by` |

**Conventions** (`RS/docs/research-os/okf-verification-interface.md`)
- Layout: L0 sources → L1 cards (frontmatter, modality tag ✅/🔧/❓) → L2 `*-dl.md` (Manchester syntax in a fence, one
  axiom per line, no one-line `Class: X SubClassOf: Y`) → L3 axioms with provers.
- `aicor-imports.yaml`: each concept is grounds, divergence or out-of-scope.
- DEFERRED-REGISTER entries `## <DU>-Dn`.
- Makefile targets print `<target>: PASS|SKIP|FAIL — <what>`.
- CQ `.md` lists answerable and not-answerable questions; the `.yaml` gives id/kind.
- The okf/lab-automation-twin module already follows this layout.

**coraplex gotchas** (from the commits)
- Clear `SymbolGraph()` per rule.
- A purely negative rule body needs a positive generator.
- Conjoin with chained `.where(A).where(B)`; Python `and` / `&` do not conjoin.
- Regenerate the ORM only via `scripts/regenerate_all_orm.py`.
- Robotiq knuckles have no mimic joints, so grasps are attachment-based.

**Repository rules in `CR`**
- `CLAUDE.local.md`: PRs are drafts only; never touch upstream `cram2`.
- `AGENTS.md` forbids `Co-Authored-By: Claude` trailers, but your commits carry them. Whoever commits there must decide
  which rule applies.

---

## 7. Research problems this work can provide evidence for

| Problem | Location | WP |
|---|---|---|
| assurance-constrained-transfer (third-party-reconstructable verdicts, refusal partition) | `RS/foundation-studio/problems/` | 5, 6 |
| competence-portability | `RS/foundation-studio/problems/` | 4 |
| model-relative-action-licensing | `RS/foundation-studio/problems/` | 6 |
| manipulation-outcome-admissibility | `RS/foundation-studio/problems/` | 4, 8 |
| competence-capability-taxonomy | ResearchProblemStudio | 6 |
| video-to-action-designator-inference | ResearchProblemStudio | 2, 5 |
| critic-oracle-specification, normative-admissibility, recompilation, warrant-threshold, compositional-episode-assessment | ResearchGapStudio | 3–8 |
| `llmreasoningforads` (epistemically qualified designator schema; designator-trajectory trace schema) | `studios/research-topics/topics/` | 2, 5 |
| `frompoliciestocognitivearchitectures` (CRAM-AICOR policy-realisation mapping; causal-admissibility trace template) | `studios/research-topics/topics/` | 1, 5, 7 |
| `evidence-grounded-action-category-revision` | `studios/research-topics/topics/` | 2, 4 |
| Open AICOR/CRAM register items the lab system will exercise | `OKF/cram/DEFERRED-REGISTER.md`, `FRONTIERS.md` | — |

The open register items are:
- R7 episode as referent;
- R8 `conformsTo`;
- R14/R15 plan as object;
- R16 concurrent interference;
- R19 monitor coupling;
- M1 deliberation scheduling;
- KR3-D1 pre-act verdict.

Papers whose evaluation sections this system could fill:
- `LA/TRO`, `LA/SLAS`, `LA/AAMAS`: all report "formal + simulation existence result" and no measured runs.
- `RS/writing/knowrob3` Table 8.1 (empty).
- `RS/writing/ral-competence-portability` results (`\todo`).
- JAIR experiments E1–E11 (prospective).

---

## 8. Inventory by location (condensed)

| Location | What is there | Use |
|---|---|---|
| `CR` (coraplex, semantic_digital_twin, giskardpy, krrood, robokudo, segmind, cram_viz, experiments) | CRAM runtime + your experiments; branches `robot-scientist-ur-perform`, `household-placement-norms`, `placement-competence-apartment` (checked out) | WP1, WP2, WP5, WP6, WP7 code |
| `CR/cram_viz/src/cram_viz/{designators.py,kb.py,competence_check.py}` | Designator interpretation, resolution, warrant, Ground & Emulate, episodic memory; EQL KB with `CATEGORY_LATTICE` and `AuditConstraint` | WP2, WP5, WP6 |
| `RS/foundation/software/cram-web-viz` | sunava's predecessor viewer (not your work) | — |
| `OKF/cram` | Rational reconstruction: 43 L1, 22 L2 (288 classes), about 25 L3 sets, 30/30 competences; HADL, TASK-TAXONOMY, plan schemata, CYCLE.md (S6 = pyCRAM/cram_viz) | WP1, WP2, WP5, WP8 theory |
| `OKF/{designator-inference,manipulation-actions,tool-use,improvised-tool-use,knowrob3}` | Event designators, category objects, tool embodiment, functional substitution, KnowRob3 frame/EQL/warrant/calculus | WP2, WP4, WP6 |
| `RS/foundation/kb` | Mirrors of the CRAM/AICOR L2/L3; AICOR process-control-alignment, scope-card, executive-spec, competence-capability taxonomy, EQL semantics, DR routing, hybrid automata; `hybrid-automata/`, `control-formalizations/` and `algorithms/` are **empty** | WP3, WP6, WP8 |
| `OKF/vrb` | Lab automation core: VRL cells, constraints, Σ algebra, SDT grounding, change taxonomy, multi-agent warrant, trajectory space, kinase-assay traces, 54 CQs, fault-injection and benchmark plans, `vrl-anatomy.html` (Cell 01 annotated) | WP3, WP4, WP5, WP8 |
| `OKF/aicor` | Hub: accountable action loop, proposal→commitment, trace/critic/verdict, capability taxonomy, executive spec; robot-scientist ledger claims; implementation status (critics/verdicts/competence claims "planned") | All |
| `OKF/{policy-realization,critic-specification,compositional-assessment,normative-admissibility,warrant-threshold,recompilation,regime-identification,category-revision,multi-agent}` | One L2 + CQs each, HermiT-checked, no L3 provers | WP3–WP8 theory |
| `OKF/rig` | Infrastructure governance; little lab content | WP8 framing |
| `C01` | Cell 01 contracts, schemas, components, biology ontology, realisation plan, reports, simulation packages | Binding spec (§4) |
| `RSV` | Robot-scientist OKF: about 95 L2 modules, CQ-1..27, 12 z3 rungs, scenarios (CCR, hepatotox, REUSE env monitoring), scene audit/binding JSON, evidence schema | WP2–WP8 |
| `RS/verticals/siemens` | Action-designator language, 4-level taxonomy, regulatory constraint objects, σ_agent, qualified capability, episode runner with fault injection, ROS `.action` generation, TC-01..10 | WP2, WP3, WP4, WP5 |
| `RS/verticals/{siemens-energy,eic}` | Cell manipulation executive, step monitoring/recovery, production NEEM; TraceBot/RobAuditor, capability-based binding, H4 rebinding, constraint compilation, Siemens→lab translation | WP4, WP5 ideas |
| `LA` | 10 lab papers + shared sources (TOP-DOWN, LAYER2, RUNNING-EXAMPLE, CLAIM-ARTIFACT-CROSSWALK), RRA constitution, reference-architecture stub | Ideas, WP7, WP8 |
| `RS/writing/{autonomous-lab-report,JAIR_Generative_Designators_Article,knowrob3,ral-competence-portability,aicor-garmi-household-assistant,native-aamas-source,aicor-research-mission}` | Technical report (25 constraints, 15 rungs); generative designators + CRAM realisation contract; KnowRob3; competence transfer; GARMI three classes + runtime contract; proposals→commitments; theory construction | WP1–WP6, WP8 |
| `RS/aicor-book` | ch07 Manipulation Executive (K_t), ch10 Understanding Executive, ch13 problem-class template (lab pouring), ch14 realising MEs (designators, plans, monitors); `aicor-scientist/` pass notes and registers | WP1, WP5, WP6 |
| `RS/executive` | Whitepaper v0.2 (quarantine station typed); research strategy `domains/lab-automation.md` (PASTEUR, two-column verdict, GMP Annex 11/15, TRL 6, AICORworks/TraceBot/euROBIN) | Framing |
| `RS/studios`, `RS/foundation-studio`, `RS/_archive` | Problem dossiers, topic dossiers, CQ tooling; archived structured-action-model schema and CRAM/KnowRob/NEEM field mappings (`_archive/old-data/topics/action-designators-foundation-models/task-cases/`) | WP2, WP5, WP6 ideas |
| `OKF/cram/{AD-STUFF,Stuff}` | LLM-generated, flagged unreliable ("specimens of the drift") | Do not use |
| `C01/../AICOR_Cell01_Codex_Context_Only` | Older stripped copy | Ignore |

---

## 9. Consequences for the plan (applied to cram-science-assistant-plan.md, revision 2)

- **WP1.1 runtime decision:**
  - The decision is coraplex, not PyCRAM vs Lisp.
  - The spike becomes: create a working coraplex environment outside ResearchSpace (fresh clone of your fork or a git
    worktree of `CR` at `robot-scientist-ur-perform`, then `uv sync`).
  - Reproduce `test_perform_labcell.py`.
  - Then add an Isaac execution backend next to giskardpy-on-SDT.
- **WP1.3 process modules:** coraplex has no process modules, so motion designators run as giskard motion statecharts.
  Cell 01 device actions (L10/L12/L17/L21/H4/TCM, door, shuttle) need a **device-command executable type**: new work
  and a proposal upstream. The FR3 plate arm, the rail UR5e and the R03 AMR need semantic robot classes (the UR class
  exists on the branch).
- **WP2:**
  - Start from Cell 01's 8 designators + TASK-TAXONOMY B "tend" + GARMI Transport/Operation/Transformation + the effect
    partition.
  - Card format per K2.
  - Implement as coraplex `ActionDescription` subclasses with EQL pre/post conditions.
- **WP3/WP4:**
  - Adopt the Σ algebra and change taxonomy rather than inventing SUB-D/SUB-S/SUB-W. Express those as Σ instances, with
    K1 settled.
  - Reuse `Constraint(id, standard, text, kind)` and the measurement-binding lattice.
- **WP5:**
  - Extend `UC/common/audit.py` and `neem_record_schema.yaml` into one canonical trail (K6).
  - Use coraplex ORM traces as the raw recording.
  - Feed RobAuditor-style verifiers from the twin's perception channels.
- **WP6:**
  - The CQ engine = EQL over the SDT + coraplex plan tree + ORM trace + audit, run headless via the `cram-viz-check`
    pattern.
  - The U(a) gate = the SHACL `ExperimentActionUnderstandingShape` + B21/B22.
  - Merge the CQ sets into one catalogue.
- **WP7:** reconcile our e2m (clingo / z3 / Isaac) with `uc_ccr` (`se_loop`, critic, campaign). Keep e2m's derivation
  and validation, and adopt the two-column critic and "belief moves only on a valid finding".
- **WP8:**
  - Cell 01 OPEN_TASKS P1 is the evaluation backlog.
  - Add the VRB fault-injection matrix and the F1 lesson (soundness over every ground truth).
