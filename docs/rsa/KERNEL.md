# The robot science assistant kernel, v0.1

The consolidated core, scoped to one lab example, as the start of a rational reconstruction. It was written
2026-10-17, while coraplex/cram_viz are not yet installed here (they arrive Tue/Wed).

## 0. Purpose and method

The ResearchSpace material consists of try-outs: many good ideas in mutually inconsistent forms (see
[../plans/researchspace-material-map.md](../plans/researchspace-material-map.md) §5). The kernel does not try to unify
everything. It takes **one example** and keeps only what that example needs. For each concept it records which try-out
it comes from and what was changed. It then tests whether the result *flies*: does the example run end to end and leave
an audit trail that the assistant can answer competency questions about?

The example is the **challenge–rescue experiment derived for a required gain of 0.5 bits**: plan `plan_g050`, three
sessions, plate P17, wells A01 (rescued), A02 (comparator) and A05 (control). The same experiment family as your
`uc_ccr` try-out, but on Cell 01's real component set.

Iteration loop:

```
 example ─► kernel concepts (this file) ─► executable kernel (rsa/) ─► run nominal + fault scenarios
    ▲                                                                           │
    └──── revise concepts ◄── findings (ITERATIONS.md) ◄── audit trail + CQ answers + cross-checks
```

Executable form: package `rsa/` in LabAutomationTwin. Its API is shaped like coraplex: designators are dataclasses,
action designators build their plans, and plans are trees of sequential, try-in-order and monitor nodes with action,
motion and command leaves. The coraplex port should therefore be a mapping, not a rewrite (§6).

## 1. The twelve kernel concepts

| # | Concept | Kernel definition | Taken from | Changed / dropped |
|---|---|---|---|---|
| 1 | **Designator** | ⟨kind, category, determiner, bindings, constraints⟩. Kinds: action, object, location, motion, device-command, event | HADL d=⟨δ,s,Δ⟩; KnowRob3 frame; coraplex `Designator` | **device-command** is new: Cell 01 devices act themselves (L10 presents, L12 dispenses). The **event** designator is the audit-side record of what happened (designator-inference). Warrant is not a slot; see 9 |
| 2 | **Action category** | A card owned by the category, not by the instance: level, parent (⊑), effect class, facet, roles, required capability, pre/effects as constraint ids, sub-plan, monitors, failure→recovery, evidence obligations, OKF class, HADL form, sources | KnowRob3 (category-owned schema ⟂ bindings); Siemens slot grammar; C_cat (manipulation-actions); Cell 01 designator schemas | One card format replaces the 8-tuple, 7-facet and Siemens variants (K2) |
| 3 | **Category hierarchy** | Five levels: scientific → lab task → manipulation → motion; device-command beside motion. Manipulation categories are typed by AICOR effect class. The facet is transport / operation / transformation | RSV scientific actions; Cell 01 8 designators + TASK-TAXONOMY; AICOR effect partition; GARMI three classes | The facet is orthogonal to the effect class, not a competing taxonomy (K3) |
| 4 | **Generalized plan** | Python code of a category that builds the sub-plan from a bound designator *at perform time*, querying the KB | CRAM GAP; coraplex `_action_plan` | Plans name categories and requirements, never devices (lint) |
| 5 | **Resolution** | KB query → value + **grounds** (the fact atoms used) + rejected alternatives with the reason | KnowRob3 resolution climb (ClimbStep); JAIR certificates | One record type, written to the audit trail |
| 6 | **Knowledge base** | The **same facts** the clingo planner uses (`build/e2m/facts_<tag>.lp`, from the OKF ABoxes) + Cell 01 component records (capabilities, contracts, monitors, failure modes; read-only) + kernel registries (categories, constraints, norms) | e2m derivation; Cell 01 `sdt/components/*.yaml` | One source: planner, resolver, monitors and CQs read the same facts |
| 7 | **Capability** | Verb from the component record, **qualified** by state (calibrated, tool coupled, tips present, automated) and by measurement binding (no_match ⊂ capability_match ⊂ provisional ⊂ validated) | Cell 01 components; Siemens qualified capability; RSV binding lattice; VRB CF2 | — |
| 8 | **Constraint** | Registry entry ⟨id, column ∈ {realization, validity}, source, text, applies_to, check, asp_rule, z3_theorem⟩. Norm clauses point to the constraints that realise them, or are marked documentary | `uc_ccr` `Constraint(cid, source, text, verdict, kind)`; e2m S1–S9; VRB C-*; normative-admissibility | The two columns as in uc_ccr. Regulation clauses are cited by identifier only, and labelled illustrative |
| 9 | **Lifecycle** | open → grounded → accepted → executing → executed \| failed → repaired \| abstained \| escalated | Cell 01 `cram_designator_schemas.yaml` | Kept apart from plan-node status (RPL) and from the run verdict (K5) |
| 10 | **Commitment record** (audit unit) | One hash-chained entry per lifecycle transition: designator snapshot, bindings, resolution grounds, constraints with verdict, monitor results, evidence refs, disposition | `uc_ccr` `audit.py`; Cell 01 `neem_record_schema`; book K_t; VRB warrant entry ⟨grounds, discharged, verdict, disposition⟩ | One canonical trail; NEEM export later (K6) |
| 11 | **Two-column verdict** | Per episode: realization (did it run correctly and safely) ⟂ validity (is the result interpretable). Commit to the culture belief only if both hold (D009) | `uc_ccr` critic; Cell 01 critic vector; NR3 | Critic vector reduced to the dimensions the example exercises |
| 12 | **Understanding gate + CQs** | U(a) slots computed from card + bindings + registry. An incomplete frame is not accepted (B21/B22). CQs are formal queries over KB + plan tree + trail, with expected answers per scenario | Cell 01 understanding contract and SHACL shape; book ch10; cram-viz-check | CQs answered from **runtime trail**, not only TBox |

## 2. Categories used by the example

| Level | Category | Effect class / facet | Required capability | OKF class (alignment) |
|---|---|---|---|---|
| scientific | Intervene (challenge, rescue) | — | — | MaterialStepDesignator ⊐ Challenge/RescueDoseDesignator |
| scientific | Measure (image readout) | — | — | ImageWellDesignator |
| lab task | RunSession | — | — | ProtocolSession |
| lab task | Retrieve, Store | ObjectDisplacement / transport | plate_storage | RetrieveAction, StoreAction |
| lab task | TransportPlate | ObjectDisplacement / transport | — (route over servesStation) | TransferAction ⊐ PlateTransferDesignator |
| lab task | Dose | SubstanceManipulation / transformation | dispensing (dose_well) | DoseAction |
| lab task | Image | Perception / operation | imaging (image_well) | ImageAction |
| lab task | Calibrate (QC) | Maintenance / operation | calibration | QCAction |
| lab task | Quarantine | ObjectDisplacement / transport | quarantine | QuarantineAction |
| manipulation | PickUp, Place | ObjectDisplacement / transport | robot serves station | PlateTransferSkill |
| manipulation | PresentShuttle, StowShuttle | ConfigurationChange / operation | has_shuttle | DeviceCommandDesignator |
| manipulation | CoupleTool | ConnectingAction | requires_tool | ToolCoupleMotion |
| manipulation | PickTip, EjectTip | ConnectingAction / transformation | pick_tip, eject_tip | TipHandlingTask |
| manipulation | Aspirate, Dispense | SubstanceManipulation / transformation | aspirate, dispense | DeviceCommandDesignator |
| manipulation | LoadImager, ImageWell | Perception / operation | load_plate, image_well | DeviceCommandDesignator |
| manipulation | CheckInterlocks, VerifyIdentity, WaitEnvironment | Perception / Regulation | interlock_monitor, identification, incubation | SafetyStepDesignator |
| motion | Approach, Insert, Grasp, Lift, Transit, Place, Release, Retract | (phase of PickUp / Place: Reach–Lift–Transport–Release) | — | ApproachMotion … RetractMotion |

## 3. Decisions taken for the example (from the conflicts in the material map, §5)

- **K2 designator schema:** the category card (§1.2). Bindings live in the instance; everything else lives in the
  category.
- **K3 taxonomy:** the effect class is the backbone, the facet is orthogonal, the lab tasks come from Cell 01, and the
  motions come from e2m.
- **K5 vocabularies:** three separate axes:
  - plan-node status (`created / running / succeeded / failed`);
  - designator lifecycle (Cell 01);
  - episode verdict (two columns).
- **K6 trace:** one hash-chained trail of commitment records; the uc_ccr `audit.py` hash rule is kept, so its verifier
  logic carries over.
- **K7 terms:** "capability" (of devices and robots, qualified or not) vs "competence" (scope-indexed claims, not used
  yet) vs "competency question".
- **K8 devices:** Cell 01 is canonical. A swapped imager is a test case.
- **K11 TraceBot:** verifiers (identity, airspace, focus quality) write their results into the trail as monitor results.
- **Not decided yet:** K1 (σ_rule vs Δ_N), K4 (warrant definitions), K10 (epistemic vocabularies). The example
  exercises none of them yet; they are scheduled in ITERATIONS.md.

## 4. What "flies" means for iteration 1

1. **Cross-check:** expanding the nominal plan into designators reproduces the clingo plan's 151 leaf steps (same
   primitive, robot/device and pose, in the same order). Two independent derivations from the same facts must agree.
2. **Execution:** the nominal run and eleven further scenarios run on a symbolic backend. The backend is a world-state
   model with fault injection. It is not Isaac, and execution on the Isaac twin is iteration 2. Scenarios (see
   `rsa/registry/scenarios.yaml`):
   - calibration known missing or lapsed;
   - tip lost;
   - identity swap;
   - slow tool changer (window);
   - imager swapped or incapable;
   - rescue reagent unbound;
   - control dropped;
   - contamination;
   - incomplete category card.
3. **Audit:** each run leaves a verified hash-chained trail, and a tampered copy fails verification.
4. **Verdicts:** each scenario ends with the expected two-column verdict and disposition.
5. **CQs:** 27 competency questions in 13 families. Each has hand-written expected answers for selected scenarios (52
   checks), not derived from the trail. The engine must reproduce them, with grounds.
6. **Modularity:** the plan code does not change across scenarios. Only knowledge and world change.

Result of iteration 1: all six criteria met; see [ITERATIONS.md](ITERATIONS.md) (findings F1–F10 changed the kernel:
belief freshness, prospection at experiment and session level, understanding gate in projection, unwind-protect).

## 5. Out of scope for iteration 1

Isaac execution, coraplex, NEEM/OWL export of the trail, the DL module for the kernel concepts, real regulation texts,
natural-language CQ front end, concurrency (one plate, sequential sessions).

## 6. Mapping to coraplex (for the port on Tue/Wed)

| Kernel | coraplex | Gap |
|---|---|---|
| `rsa.designators.ActionDesignator` (dataclass fields = roles; `plan(ctx)`) | `ActionDescription` (`_action_plan`, `pre_condition`/`post_condition` as krrood EQL) | Our pre/post are registry constraint ids evaluated by python checks → EQL expressions |
| `rsa.plans.Sequential / TryInOrder / Monitor` | `plans.factories.sequential / try_in_order / monitor` | — |
| Motion leaf | `MotionNode` + giskard motion statechart | Twin controllers instead of giskard (Isaac backend) |
| Device-command leaf | **none** | New executable type (proposal to coraplex) |
| KB facts + query helpers with grounds | krrood EQL over semantic_digital_twin | Lab semantic annotations (plate, well, nest, device) missing in SDT |
| Audit trail | ORM (`to_dao(plan)`) + uc_ccr `audit.py` | Trail built from plan-node events; ORM is the raw recording |
| CQ engine | `cram-viz-check` specs | Specs over the trail as EQL entities (as `AuditConstraint`) |
