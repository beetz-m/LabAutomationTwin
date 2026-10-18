# Iterations of the robot science assistant kernel

## Iteration 1 (2026-10-17): does the consolidated kernel fly on the challenge–rescue example?

**Result: yes, on the symbolic backend.** Command: `env_cad/bin/python -m rsa.run_example`. Report:
`rsa/out/report.md`. Trails: `rsa/out/trail_<scenario>.json`.

| Criterion (KERNEL.md §4) | Result |
|---|---|
| Cross-check vs the clingo plan | Expanding the designators in the nominal and `uncalibrated_known` runs reproduces the planner's leaf steps term for term: 151/151 and 152/152. The durations also match exactly: 298.9 / 263.3 / 256.4 s and 376.4 s. Two independent derivations from the same facts agree. |
| 12 scenarios, same plan code | All end with the expected two-column verdict, disposition and repairs. |
| Audit | Every trail verifies (attributable, evidence hashed). A tampered copy is detected in every scenario. |
| Competency questions | 27 questions × scenarios = 52 checks. 52/52 correct, 52/52 grounded. Expected answers were written from the specification. |
| Modularity lint | The plan code names no device, robot, pose or plate. |
| OKF module after the KB fix (F1) | `make check` PASS: e2m 7 plans re-derived and z3-validated, the g050 plan identical step for step. |

What the scenarios show:
- **Device exchange.**
  - `imager_swapped` executes unchanged and ends NR3 (physically realised, invalid evidence; nothing committed).
  - `imager_incapable` is refused before the first intervention, naming the missing capability.
- **Step substitution by knowledge.** `uncalibrated_known` inserts the QC calibration.
- **Step substitution by repair.** `calibration_lapsed` recalibrates and re-images. `tip_lost` replaces the tip before
  aspiration.
- **Workflow change.** `control_dropped` is refused by `challenge_requires_controls`.
- **Safety and identity.**
  - `identity_swap` quarantines P18, escalates, and knows that it does not know where P17 is.
  - `tool_changer_slow` returns the plate to the incubator before reporting failure.
- **Knowledge gaps.** `rescue_unbound` and `card_incomplete` are refused before anything moves.

### Findings (each changed the kernel or the knowledge)

| # | Finding | Change |
|---|---|---|
| F1 | **The knowledge base was incomplete.** derive_plan chose plate seats by a hard-coded name list and hard-coded the shuttles (l10, l17). H4 (`transfer_nest`), L09 and L21 had no seat facts, so a quarantine could never have been grounded. | Seats now come from the ABox type `PlateSeatPose`, shuttles from `PlateShuttle`/`MotorizedStage` parts (`derive_plan.py`). The plans are unchanged and the OKF check passes. |
| F2 | **The kernel and the planner disagreed at s1.** The kernel kept believing R02's tool was still coupled 48 h later; the planner re-couples every trip. | Freshness rule: observations of shared cell state (tool, poses, shuttles, stage) go *stale* at session start and are re-established, not assumed. This is the `freshness_key` idea of the hepatotox scenario. **Open:** should calibration also go stale? That needs a QC validity policy, which Cell 01 does not define. |
| F3 | **The understanding gate caught incomplete category cards** that I wrote myself (`calibrate`, `quarantine`: no declared preconditions or risks). | Cards completed. Semantics made explicit: an *undeclared* slot blocks, a slot *declared empty* ("none required") does not. **Question for the RS contract:** is that the intended reading of B21? |
| F4 | A failing leaf (the barcode read in the identity swap) wrote no audit entry, so the evidence for the escalation was lost. | Failing leaves log what they observed (Cell 01: retain invalid runs). |
| F5 | The refusal for `rescue_unbound` was blamed on the time window. | Prospection is its own constraint: `projection_succeeds` (CRAM projection / Ground & Emulate gate). |
| F6 | `imager_incapable` and `rescue_unbound` failed only after the challenge had been dosed, wasting the culture. | The whole experiment is projected at acceptance, so it is refused before the first intervention. |
| F7 | `card_incomplete` moved the plate to L12 before the understanding gate refused the dose. | The understanding gate is knowledge-only, so it also runs during projection. Refused before any motion. |
| F8 | A predicted window violation was reported as "not groundable" because the window policy aborted the projection. | In projection, policies predict instead of abort. The window is judged by `window_prospective`. |
| F9 | The lint found device names in plan code: L12 as the source of the reagent concentration and of the volume tolerance. | Stock concentration is a property of the reagent (registry `reagents`). Tolerance comes from the *bound* device. The plate comes from the experiments ABox. |
| F10 | Any failure after the plate left the incubator stranded it at the device. | Unwind-protect at session level: the plate is returned before the failure propagates, except when it was quarantined. |

**Corrections to my own expectation table (disclosed).** The first table expected the root to end `repaired` in
`calibration_lapsed` and `tip_lost`. The design, written before the run, records repairs on the node that repaired;
the root ends `executed`. The table also expected `failed` where the executor routes `session_failed` as escalation.
I corrected both entries (E1, E2) after the first run. All other expectations, and all 52 competency-question answers,
were written before the runs and were not changed.

### Conflicts settled in this iteration (material map §5)

- **K2 designator schema:** category card.
- **K3 taxonomy:** effect class as backbone, transport/operation/transformation as facet, Cell 01 lab tasks,
  e2m motions.
- **K5 vocabularies:** three separate axes.
- **K6 trace:** one hash-chained trail; the uc_ccr hash rule is kept.
- **K7 terms:** capability vs competence.
- **K8 devices:** Cell 01 canonical, alternatives as scenarios.
- **K11 TraceBot:** verifier results go into the trail as monitors.

Not exercised yet: K1 (σ_rule vs Δ_N), K4 (warrant definitions), K10 (epistemic vocabularies).

### What the reconstruction learned about the concepts

- The **device-command designator** is needed as a fourth leaf kind beside motions. Cell 01 devices are co-actors, and
  coraplex has no counterpart.
- **Prospection operates at two levels:** experiment before the first intervention, session before the plate moves.
  It must *predict* policies, not enforce them.
- **Belief needs freshness**, not only provenance: observed → stale across sessions.
- The **understanding gate** is cheap (knowledge-only). It belongs in prospection, where it blocks badly specified
  actions before anything moves.
- **Physical success ≠ validity** shows up naturally once the measurement binding is a knowledge item. Swapping the
  imager leaves the plan identical and the experiment invalid (NR3).

### Limits of iteration 1

- **Symbolic backend.** Durations are the planner's facts, so the duration cross-check shows consistency, not
  independent physics.
- No concurrency (one plate, sequential sessions).
- The competency questions are hand-written query functions over the trail, not yet EQL.
- The critic covers only what the example exercises.
- The regulation mapping is illustrative.
- No natural-language front end.
- The kernel's own concepts are not yet an OKF/DL module.

## Iteration 2 (2026-10-17): Isaac backend and the kernel in the ontology

### Findings

| # | Finding | Change |
|---|---|---|
| F11 | **A planning error present in both derivations.** For an uncalibrated imager, the QC validation was placed after the experiment plate had been set on L17. The reference plate needs L17's stage, so the step is physically infeasible. It surfaced when mapping the kernel's `validate` leaf onto the twin's L21 procedure. | Planner: QC is a *preparation* step (ASP position 5000), before the plate leaves L10, excluded from the window (S5). z3: new precondition "target imager free". The *old* `plan_g050_uncal` is now refuted at step 24. All 7 plans were re-derived and z3-validated. Kernel: `RunSession` calibrates first. A lapse detected *during* imaging is repaired by setting the plate aside at a passive station (`staging_for`: handover nest), recalibrating, and **re-planning** the measurement (new recovery mode `replan`: CRAM retry = re-resolution). |
| F12 | Projection copied the backend's ground truth. | Projection starts from the assistant's **belief** (`SymbolicWorld.from_belief`). A prediction may only use what the assistant has reason to hold. |
| F13 | **The twin's devices act at contract granularity.** L12 offers `dose_well`; there are no separate tip, aspirate and dispense calls. Robot skills are whole picks and places. | The process-module layer binds *groups* of leaves to one skill. The group runs at its first leaf, and the following leaves report the phases of that execution. Every leaf entry names what `realised_by` it. **Open question:** should a device-command leaf be at contract granularity (`dose_well`) with phases as events, or at the planner's granularity (4 commands)? The kernel keeps the planner's granularity for now. |
| F14 | **HermiT found 6 unsatisfiable kernel categories:** picking-up, placing, transporting, retrieve, present, stow. The cards' `parent` conflated specialisation (⊑) with partonomy (◁, phases) and realisation (command realises manipulation). | Cards now separate `parent` (⊑, same level) from `parts` (refinement). This is the ⊑/◁ distinction of CRAM's action-category DL, enforced by the reasoner. The module is consistent with 0 unsatisfiable classes. |
| F15 | The trail export needed category cards for `incubate` (culture wait) and `contain` (quarantine). The reasoner left them unclassified until the cards existed. | Cards added. All 222 designators of the nominal trail are classified by the reasoner. |
| F16 | **Upstream reuse.** RS `ValidityConstraint` (authorization envelope) is the kernel's validity column. AICOR's `CommitmentRecord` is an episode-level structure, not a per-transition entry. | Reused `ValidityConstraint`. The kernel's unit is `CommitmentAuditEntry`. Divergence registered as D-LAT-11, together with the missing device-command designator in CRAM/coraplex. |

### OKF module `lab-twin-rsa-kernel` (generated from `rsa/registry/`)

- Each category is a class *defined* by its level plus its kernel category name, so trail individuals are classified by
  the reasoner.
- Effect classes (AICOR partition) and facets are disjoint superclasses. Alignment with the e2m designator classes is
  by subclass or `designatesAction`.
- Audit entries are `CommitmentAuditEntry`. `ViolationAuditEntry` is defined.
- `make check`: PASS.
  - HermiT: 0 unsatisfiable.
  - 18/18 TBox competency questions, including CQ-16..18 on the kernel.
  - Konclude realises 6244 individuals. 222 trail designators are classified with none left over, plus 498 audit
    entries.
  - 6/6 negative controls, including "a kernel motion also typed manipulation-level".

### Isaac backend (`rsa/isaac.py`, `scripts/run_cell01_episode.py --rsa <scenario>`)

Same plan code, knowledge, audit, critic and competency questions; the twin's controllers execute the leaves.
- The first run executed sessions s0 and s1 on the twin, then stopped in s2 on a backend bug: a property was called as
  a method. That Kit run exited 0 even so. Both are fixed: partial trails are kept, and a backend exception now fails
  the run.
- Results (unchanged plan code; expectations written before the runs):

  | Scenario | End | R / V | Trail | Sessions on the twin (planner) | CQ |
  |---|---|---|---|---|---|
  | `isaac_nominal` | executed, commit | ok / ok | 498 entries, 153 leaves, same counts as the symbolic trail | s0 305.7 s (298.9), s1 230.1 s (263.3), s2 207.3 s (256.4) | 10/10 correct, grounded |
  | `isaac_identity_swap` | escalated | x / x | 56 entries; L10 read P23 for P18; P23 quarantined at H4; P18 unknown | s0 55.3 s (298.9) before the stop | 6/6 |
  | `isaac_calibration_lapsed` | **escalated (expected: executed)** | x / x | 562 entries, 178 leaves | s0 305.7, s1 230.1, s2 414.6 s (256.4) | 2/3 (CQ-21 fails) |

  The twin's durations are now physics, not the planner's facts. They lie between −19 % and +2 % of the planner's
  durations, and every trip stays inside the 600 s window (ILLUSTRATIVE).

- **F17: `isaac_calibration_lapsed` does not fly (expectation not changed).**
  - The calibration repair worked as designed: L17 refused, the plate was set aside, L21 recalibrated, and the
    measurement was re-planned. A01 was then imaged validly.
  - A02 then failed `focus_quality` twice (score 0.035 and 0.030, floor 0.04). The session returned the plate to L10
    and escalated, so control A05 was never imaged (V4, V7). The disposition is correct for what happened; the
    expected outcome was not reached.
  - Evidence:
    - After the reload, the A01 field is shifted by about 93 µm against the nominal run (image cross-correlation),
      with the same commanded stage position, zero stage error and seat sensors at zero gap.
    - The two A02 images of the same load differ by about 35 µm. The plate seems to move in the nest, which the
      seat sensors do not see. **Not yet confirmed** from the physics state.
    - The twin's test sample is sparse (about 15–20 objects per 10x field), so a shifted A02 field holds too little
      structure for the focus floor.
  - **Knowledge error in the kernel:** the `focus_invalid → autofocus, retry` repair cannot change the outcome. L17
    autofocuses on every image, so the repair repeats the same action on the same field. A repair should be admitted
    only if the device contract says it changes something.
  - **Backend bug, fixed, not yet re-run:** a refused image recorded a failed focus monitor although nothing was
    acquired.
  - **Open, needs your call:** the lateral seating of the plate on the L17 stage (twin physics, Cell 01 overlay), and
    what a valid focus repair is (another field in the same well? 4x?). Each changes what counts as the same
    measurement.

- **Refinement proof (motion plan → culture plan): `rsa/refinement_proof.py`, `docs/rsa/REFINEMENT-PROOF.md`,
  `docs/rsa/plan/proof.html`.**
  - Seven obligations hold relative to A1–A6:
    - O2 and O5 by z3;
    - O4 by re-running `validate_plan_z3.py`;
    - O6 over 111/111 motions;
    - O7 over 13/13 guarantees.
  - Eight negative controls are caught.
  - The theorem is "realizes the culture plan, or a monitor stops it and a verified handler's guarantee holds". It
    does not cover progress, the two partly detected faults (L12 misregistration, L17 misseating), contact physics,
    or Giskard execution.

- **Reproducible plan, audit trail and paper: `rsa/reproduce.py`, `rsa/protocol.py`, `paper/build_paper.py`,
  `docs/rsa/REPRODUCIBILITY.md`.**
  - The derivation runs in 12 stages, from the EIG design to the protocol, and is recorded in a content-addressed
    manifest. Only the wall-clock fields `solve_s`, `ground_s` and `wall_s` are excluded from the hashes.
  - `--verify` re-ran everything, including a fresh EIG Monte Carlo, and produced the same manifest hash.
  - The protocol (`rsa/out/repro/protocol.md`) and the audit certificate (`audit.json`) are generated from the outputs.
  - Audit trails: all 15 chains are intact and the tamper test is detected in all 15. Each of the 12 symbolic
    scenarios was re-executed in a temporary directory and gave an identical trail. The Isaac trails are verified but
    not re-executed, and they were recorded under older registry hashes.
  - The paper is generated from the outputs (LuaLaTeX PDF plus HTML). Authors and the AI statement are placeholders;
    the references must be checked.

## Next iterations

1. **Iteration 2, Isaac (before coraplex arrives).**
   - Bind the leaves to the twin's controllers by factoring the skills out of `scripts/run_cell01_episode.py` into
     `twin/cell01_skills.py`, used both by the legacy runner and by an `IsaacBackend`.
   - Run nominal, `calibration_lapsed` and `identity_swap` in Isaac.
   - Compare the trails with the symbolic ones: same designator tree, real durations, real evidence (images, barcode
     reads, L12 liquid volumes).
2. **Iteration 2, OKF.**
   - Module `lab-twin-rsa-kernel`: category cards → DL (taxonomy alignment proved by HermiT).
   - Commitment records → ABox (trail export as NEEM-like individuals).
   - The CQs also answered by OWL query.
3. **Iteration 3a, lab designator language.** Proposal: [LAB-DESIGNATOR-LANGUAGE.md](LAB-DESIGNATOR-LANGUAGE.md).
   Lab actions as contracts with `requires` / `prevents` / `maintains` / `achieves` over lab entities only.
   Acceptance test: the 12 scenarios and 52 CQ answers are unchanged when the lab-level checks are generated from
   the clauses.
   **First step done (2026-10-17):** the whole experiment as a partially ordered set of action designators over entity
   designators (`rsa/registry/lab/challenge_rescue.ldl`, contracts in `contracts.ldl`, checker `env_cad/bin/python -m rsa.ldl`).
   - 8 entity designators resolve against the planner's facts, the derived plan and the SDT ABox.
   - The order is derived, not written: 13 causal links, 7 Hasse edges, 12 linear extensions. All 9 threats on culture
     time are resolved by the order.
   - One mutual exclusion: dosing A01 and A02 may not overlap. That comes from reading the cross-dosing prevents-item
     over the interval; open question in the report.
   - Negative controls 5/5 caught:
     - design anchors removed: open threats;
     - control well dosed: experiment prevents violated;
     - no control arm;
     - device named in lab text: lint;
     - rescue at a culture time that nothing achieves.
   - One linear extension, grouped by culture time into sessions, drives the kernel. The symbolic run gives the
     **identical** 153-leaf sequence and 498 entries as the run built from the planner's plan. The planner's executed
     order is a linear extension of the LDL order.
   - The symbolic suite still passes (52/52 CQ). `registry_sha` now hashes `registry/lab/` too.
   - Not yet: lab-level checks generated from the clauses (they are still coded checks), and contract monitors for the
     admissibility rule.
   **v0.2 (same day, after the user's seven decisions; LAB-DESIGNATOR-LANGUAGE.md section 10).**
   - New in the language: instrument roles (slot and process), goals, signalled failures with control-program
     handlers, rich epistemic grades with a meta model (`registry/lab/epistemic.yaml`), KPIs with a lexicographic
     preference, and fluent-bounded scopes.
   - The checker resolves every instrument role (L12, L10, L17 by slot and process) and justifies 8/8 goals.
   - 20/20 failures are handled, and every epistemic shortfall has a treatment.
   - KPIs are measured from 7 trails. The scoped prevent removes the A01/A02 exclusion.
   - Negative controls: 8/8.
   - The well frames are re-parented in the overlay (`compose_cell01_overlay.semantic_plate`); `make check` PASS.
   **v0.3 (second round of decisions; LAB-DESIGNATOR-LANGUAGE.md section 11).**
   - Device process models, grounded in the component records (`registry/lab/processes.ldl`), and trust per step.
   - Checked repair guarantees (13/13 hold, and they hold in the recorded runs).
   - The meta model in LDL (`epistemic.ldl`).
   - Safety, reliability, auditability and cost as the leading KPIs.
   - Negative controls: 12/12.
   - Found: the kernel's focus repair (refocus) differs from the prescribed re-seat. Two trust gaps remain: well
     misregistration at L12, and lateral plate seating at L17.
4. **Culture plan → Cell 01 (2026-10-17).**
   - The experiment stated over the cultures only (`registry/lab/culture_plan.ldl`): 12 actions (challenge, grow,
     rescue, observe, interpret, analyse), each with a physical and a knowledge effect. Order derived from 13 links
     (7 physical, 6 knowledge).
   - Run on Cell 01's surrogate:
     - observed effect 14.8 um;
     - belief M1 0.68 / M2 0.15 / M3 0.17;
     - **0.357 bit gained against 0.5 required**, while the design's expected gain is 0.5439 bit.
     The design meets the requirement only in expectation, so the goal now says `expected-information-gain`.
   - Mapping:
     - cultures to P17 A01/A02/A05;
     - 8 culture actions to lab action designators and devices (L12, L10, L17);
     - 4 computations (interpretation and analysis), which need an established pixel-size calibration.
     The lab order is exactly the projection of the culture order.
   - Feasibility (`rsa/culture_plan.py`): every transport leg, the tool coupling, the machine tending of L10, L12 and
     L17, and the trip time pass, with evidence from facts and reach up to the Isaac run.
   - Conditional on two assumed device preconditions (L12 calibrated, L17 healthy). Open: inventory, the two trust
     gaps, vendor timing.
5. **Motion level in Giskard (2026-10-17).**
   - Every motion leaf of the executed plan is refined into a motion designator. 111 leaves become 111 designators,
     over 12 legs, 6 of them distinct. Each designator has:
     - reference frames: robot root and tip, and a goal pose in a seat frame of the composed scene;
     - motion constraints: Cartesian goal or straight line, speed limits, plate kept level, collision avoidance,
       allowed contacts;
     - an ending monitor;
     - the objective of giskardpy's QP-based model-predictive controller.
   - Output: `rsa/out/challenge_rescue_motions.lisp` and `rsa/out/challenge_rescue_giskard.py`. The giskardpy API is
     verified against the user's CRAM checkout (imports, constructor fields); the module compiles.
   - All 25 goal frames are reachable with FR3 and rail + UR5e kinematics within the joint-margin thresholds. R01's
     goals are collision-free; R02's collisions are not checked offline.
   - Open:
     - compliant insertion, for which giskardpy has no impedance (ForceImpactMonitor needs ROS);
     - attaching and detaching the plate in the SDT World between statecharts;
     - a Cell 01 SDT World, so the module can run.
6. **Independence of the culture plan (2026-10-17; `rsa/independence.py`).**
   - Vocabulary: no term of six realization vocabularies occurs in `culture_plan.ldl`. The vocabularies cover
     robots, devices, lab setup, safety constraints, cleanliness and temperature control, and are collected from the
     facts, component records and registries.
   - Found and fixed: the interpretation step required "a calibration of the pixel size", and `calibration` is L21's
     function. It now requires `(a scale (of (an image)) (known true))`.
   - Invariance over 13 labs (knowledge variants, symbolic backend): the culture plan, its derived order and the lab
     plan are identical in every lab. The realization differs:
     - **same:** tool kept coupled;
     - **different:** one rail robot, hand-over in the plate hotel, other device models, uncalibrated imager (QC
       inserted);
     - **realized but not valid evidence:** capability-only imager;
     - **refused before anything moves:** 300 s window, interlocks open, contamination suspected, tool counted as
       culture-contacting, incubator profile mismatch.
7. **Iteration 3, coraplex (Tue/Wed).**
   - Map `ActionDesignator` → `ActionDescription` and leaves → `MotionNode`; propose a device-command executable.
   - Resolution queries → krrood EQL over semantic_digital_twin (lab annotations: plate, well, nest, device).
   - CQs → `cram-viz-check` specs.
   - Revive your `robot-scientist-ur-perform` branch as the UR reference.
8. **Science.** A priming design to separate M2 from M3 (the realised-gain finding); several plates under concurrency
   (R16).
9. **Decisions pending:**
   - K1, K4, K10;
   - calibration freshness;
   - whether a human sign-off model is needed (Part 11 is currently "not covered").
