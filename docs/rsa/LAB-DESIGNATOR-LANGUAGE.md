# LDL: a lab designator language (v0.3)

Status: **v0.2**, 2026-10-17. v0.1 was the proposal below; v0.2 adds your seven decisions of the same day (section 10) and
is implemented in `rsa/ldl.py` with the experiment in `rsa/registry/lab/`. The illustrated report is
`docs/rsa/ldl_report.html`. Quantities that come from the twin
(600 s window, 5 % tolerance, dose units) are ILLUSTRATIVE (D016) and are marked as such where they appear.

## 0. In one paragraph

LDL is the language in which the lab states **what** an action must bring about, never **how**. An action is a
contract with four clauses over lab entities only:

| Clause | Meaning over the action's interval [t₀, t₁] | Operational reading |
|---|---|---|
| `requires` | holds (and is known to hold) at t₀ | acceptance check, or a reason to establish it first |
| `prevents` | no state or event matching it occurs in [t₀, t₁] | a monitor that must be able to detect it; abort or contain |
| `maintains` | holds throughout [t₀, t₁] | a regulated condition with recorded history |
| `achieves` | holds at t₁ and persists until changed | post-condition, including the evidence record |

Every term is an **entity description** in your entity-relation query form: `entity(X, δ)` with a partial description
δ (D6.2 §3.3.1; EQ1–EQ10 in `okf/aicor/.../entity-query-semantics-axioms.md`), written in the HADL surface
`(determiner sort slot*)` (`okf/cram/designator-language/00-language.md`). A condition is an entity description too:
once its variables are bound it is a ground query, i.e. a truth value (EQ6). No robot, gripper, tool, pose, frame,
prim, trajectory or device identity can be written. Those belong to the realization layer (kernel category cards,
coraplex, SDT). The language makes that boundary lintable (§6).

## 1. Sources and what is taken from each

| Idea | Source | Used as |
|---|---|---|
| `entity(X, δ)`, partial description, uppercase/`?` variables, `,` = join, `;` = union | euROBIN D6.2 §3.3; EQ1–EQ10 | term language and its answer-substitution semantics |
| determiners `a`/`an` (attributive), `the` (referential, tracked), `some` (stuff), `each` (universal) | HADL §2 | unchanged |
| capability-scoped sorts as restrictions | HADL §4 | instruments appear only as `(an instrument (function …) (qualified-for …))` |
| Π = ⟨Π_goal, Π_avoid, J⟩ | ISRR paper via `bws-relative-task-specification` | `achieves`/`maintains` ≈ Π_goal, `prevents` ≈ Π_avoid; J (quality) left out of v0.1 |
| intended effects, preserved conditions, safety constraints, evidence obligations | BWS-relative task specification | the four clauses; evidence is an `achieves` on a record |
| two-column verdict | uc_ccr critic, kernel concept 11 | `:column validity` annotation on a condition |
| event designator | kernel concept 1 | `prevents` ranges naturally over events (an excursion, a cross-transfer) |
| pre/eff derived per category, "unsatisfied pre drives expansion" | HADL §5 | `requires` may be established by the executive, unless marked `(known …)` only |

What is new here: the split of enforcement into `prevents` / `maintains` / `achieves`; conditions as ground entity
queries; the rule that instruments are only attributive; and the lint boundary.

## 2. Sorts and slots (lab entities only)

| Sort | Key slots | Notes |
|---|---|---|
| `plate` | `id`, `identity`, `contamination`, `in`, `contained` | the carrier; identity is tracked on it (barcode) |
| `well` | `of` (plate), `role`, `received`, `culture-time` | the culture lives in the well |
| `substance` | `type`, `lot`, `dose`, `identity` | with `some`: stuff, not an individual |
| `design` | `id`, `arm`, `requirement-bits` | the experiment design from e2m |
| `arm` | `role` (rescued, comparator, control), `wells` | design arm |
| `controlled-environment` | `profile` | a profile id; no invented setpoints (D016) |
| `excursion` | `of` (plate), `duration` | event: an interval outside a controlled environment |
| `transfer` | `of` (substance), `into` (well) | event: substance entering a well |
| `measurement` | `of` (well), `readout`, `binding`, `calibration`, `culture-time` | the information object, not the device |
| `record` | `of`, `states`, `attributable`, `original`, `hash-chained` | evidence; ALCOA fields |
| `instrument` | `function`, `qualified-for`, `calibration` | **attributive only** (`a`/`an`); never `the`, never an id |
| `person` | `role` (operator, reviewer) | for sign-off and personnel-safety clauses |
| `request` | `for`, `to` | e.g. a review request to a person |

Time is lab time: `(culture-time 48 h)` measured from the first intervention, not wall clock and not session.

## 3. Syntax

```
action      ::= "(" ("a"|"an"|"the") "action" var? "(type" action-type ")" role* clause* ")"
clause      ::= "(requires"  condition+ ")"
              | "(prevents"  condition+ ")"
              | "(maintains" condition+ ")"
              | "(achieves"  condition+ ")"
condition   ::= designator annotation*              ; holds iff it has an answer (EQ6)
              | "(not" condition ")" | "(and" condition+ ")" | "(or" condition+ ")"
              | "(known" condition ")"              ; believed with observed, fresh provenance (F2)
designator  ::= "(" determiner sort var? slot* ")"  ; = entity(var, δ)
determiner  ::= "a" | "an" | "the" | "some" | "each"
slot        ::= "(" slot-name value ")"
value       ::= atom | quantity | var | designator | "(" comparator quantity ")"
annotation  ::= ":column" ("realization" | "validity")       ; default realization
              | ":tolerance" quantity | ":source" id
;; ?self denotes the action itself (for records about it). A variable co-refers within one contract; it does not
;; make an attributive description referential.
workflow    ::= action
              | "(seq" workflow+ ")" | "(par" workflow+ ")"
              | "(at" "(culture-time" quantity ")" workflow ")"
              | "(each" var designator workflow ")"
action-type ::= experimenting | intervening | measuring | incubating | quarantining | qualifying
```

KQL list form, for the same well: `entity(W, [the, well, [of, P], [role, rescued]])` ≡
`(the well ?w (of ?p) (role rescued))`. The s-expression is the surface; the list form is what an euROBIN query
processor answers.

## 4. Semantics

Let τ be the execution trace (the twin's or the belief's state history) and [t₀, t₁] the action's interval.

- **Term.** ⟦(d s ?x δ)⟧ = ⟦entity(X, δ)⟧ (EQ1). `the` additionally requires exactly one tracked referent; `a`/`an`
  any satisfier.
- **Condition.** A condition φ is evaluated at a time point t: τ, t ⊨ φ iff the bound query has an answer in the state
  at t (EQ6). Event descriptions (`excursion`, `transfer`) hold at t if such an event is occurring at t.
- **Action.** τ ⊨ a iff
  τ, t₀ ⊨ requires ∧ ∀t ∈ [t₀, t₁]: τ, t ⊭ prevents ∧ ∀t ∈ [t₀, t₁]: τ, t ⊨ maintains ∧ τ, t₁ ⊨ achieves.
  `maintains φ` and `prevents (not φ)` are logically the same. They are kept apart because the operational
  obligation differs: a `prevents` item needs a **detector** and a reaction (abort, contain), a `maintains` item needs
  a **regulator** and a recorded history (excursion alarms).
- **Scope.** `prevents` and `maintains` of an enclosing action hold for every sub-action (inherited invariants).
  `achieves` is not inherited. `requires` of a sub-action may be satisfied by an earlier sibling's `achieves`.
- **Knowledge.** `(known φ)` holds iff the belief has φ with provenance *observed* and not *stale* (kernel F2). Plain
  φ in `requires` may be **established** by the executive (insert a qualifying action before measuring). `(known φ)`
  may only be **verified** (identity cannot be established, only read).
- **Two columns.** Realization = every `:column realization` item satisfied; validity = every `:column validity`
  item satisfied. NR3 = realization ∧ ¬validity. D009 commit rule: both.
- **Admissibility (understanding gate, B21 sharpened).** An action is accepted only if: every term resolves (or is
  attributive by design); every `prevents` item has a monitor that can detect it; every `maintains` item has a
  monitor or regulator; every `achieves` item has an evidence path; every `requires` item can be verified or
  established. A `prevents` clause that nothing can observe is not a constraint, so the action is refused.

## 5. The challenge–rescue experiment in LDL

Design c_d85_t48_n1 from e2m (requirement 0.5 bit, EIG 0.5439 bit), plate P17, wells A01 (rescued), A02 (comparator),
A05 (control); challenge 0.85 au at 0 h into A01 and A02, rescue 0.70 au at 48 h into A01, images of all three at 72 h.
All quantities are the twin's, ILLUSTRATIVE.

### 5.1 The experiment

```lisp
(the action ?E (type experimenting)
  (design (the design ?D (id c_d85_t48_n1)))
  (plate  (the plate ?P (id P17)))
  (requires
    (known (the plate ?P (contamination none)))
    (the design ?D (arm (an arm (role control)))) :column validity)  ; challenge_requires_controls
  (prevents
    (an excursion (of ?P) (duration (> 600 s)))              ; ILLUSTRATIVE window
    (a transfer (of (some substance)) (into (a well (of ?P) (role control))))
    (an event (type contamination-introduced) (of ?P)))
  (maintains
    (known (the plate ?P (identity verified))))              ; where it is and that it is P17
  (achieves
    (the plate ?P (in (a controlled-environment (profile culture-standard))))
    (each measurement (of (a well (of ?P))) (binding validated)) :column validity
    (a record (of ?E) (hash-chained true) (attributable true)))
  (workflow
    (seq
      (at (culture-time 0 h)
        (each well ?w (of ?P) (role (or rescued comparator))
          (an action (type intervening) (into ?w)
            (substance (some substance (type challenge))) (dose 0.85 au))))
      (at (culture-time 48 h)
        (each well ?w (of ?P) (role rescued)
          (an action (type intervening) (into ?w)
            (substance (some substance (type rescue))) (dose 0.70 au))))
      (at (culture-time 72 h)
        (each well ?w (of ?P)
          (an action (type measuring) (of ?w) (readout bright-field-image)))))))
```

Retrieve, transport, store, tool coupling and sessions do not appear. They are how the executive keeps
`(prevents (an excursion … (> 600 s)))` and achieves `(the plate ?P (in (a controlled-environment …)))` while bringing
the plate to something that can dispense or image. A *session* is a realization concept (one trip); the lab sees
culture-time points.

### 5.2 Category contracts (owned by the action type; the instance only binds roles)

```lisp
(an action (type intervening)
  (into (the well ?w (of ?p))) (substance (some substance ?s (type ?t))) (dose ?q)
  (requires
    (known (the plate ?p (identity verified)))                         ; identity_verified
    (known (some substance ?s (identity verified) (lot ?l)))          ; reagent_bound (lab part)
    (known (the plate ?p (contamination none)))                        ; contamination_free
    (the well ?w (role ?r)))                                           ; the well is bound to the design
  (prevents
    (a transfer (of (some substance (not ?s))) (into ?w))              ; wrong substance
    (a transfer (of ?s) (into (a well (of ?p) (not ?w))))              ; cross-dosing
    (an event (type contamination-introduced) (of ?p)))                ; tool_compatible derives from this
  (achieves
    (the well ?w (received (some substance ?s (dose ?q)))) :tolerance 5 % :column validity   ; ILLUSTRATIVE
    (a record (of ?self) (states (?w ?s ?l ?q culture-time delivered)) (original true))))

(an action (type measuring)
  (of (the well ?w (of ?p))) (readout ?r)
  (requires
    (known (the plate ?p (identity verified)))
    (an instrument (function imaging) (qualified-for ?r) (calibration current)))  ; establishable: qualifying
  (prevents
    (an event (type contamination-introduced) (of ?p)))
  (achieves
    (a measurement ?m (of ?w) (readout ?r) (calibration current) (culture-time ?ct)) :column validity
    (the measurement ?m (binding validated))                                         :column validity
    (a record (of ?m) (raw-data original) (hash-chained true))))

(an action (type qualifying)                                  ; QC; the lab-level name for calibration
  (instrument (an instrument ?i (function ?f)))               ; ?i co-refers inside the contract only
  (achieves (an instrument ?i (calibration current))))        ; the excursion bound is inherited (§4 scope)

(an action (type quarantining)
  (material (the plate ?x))
  (requires (or (known (the plate ?x (identity mismatched)))
                (known (the plate ?x (contamination suspected)))))
  (prevents
    (an event (type use) (of ?x) (in (an experiment)))
    (an event (type release) (of ?x) (without (a record (type sign-off) (by (a person (role reviewer)))))))
  (achieves
    (the plate ?x (contained true))
    (a request (for (a review (of ?x))) (to (a person (role reviewer))))))
```

The quarantine contract states the Part 11 question in the language itself: release requires a sign-off record by a
person. Whether such a record exists is now a condition the assistant can check and report, instead of a "not
covered" row.

## 6. The abstraction boundary

**Lint rule.** Forbidden in LDL: sorts `robot`, `gripper`, `tool`, `pose`, `frame`, `prim`, `trajectory`, `motion`;
any device identifier; `the instrument` (instruments only attributively); any location other than a
`controlled-environment` or containment state. The existing kernel lint (no device, robot, pose or plate in plan
code) becomes a lint over LDL documents. The plate *is* allowed here, because the experiment is about it.

**Where the kernel's constraints go** (my reading of `rsa/registry/constraints.yaml`; to be confirmed by the
implementation, §8):

| Kernel constraint | LDL clause | Layer |
|---|---|---|
| `identity_verified` | `requires (known … (identity verified))` | lab |
| `contamination_free` | `requires (known … (contamination none))` | lab |
| `reagent_bound` | `requires (known (some substance … (identity verified) (lot …)))`; the rack position is realization | lab |
| `challenge_requires_controls` | experiment `requires … (arm (role control))`, validity | lab |
| `window_kept` | `prevents (an excursion … (> 600 s))` | lab |
| `window_prospective` | the same clause, checked by projection; the 20 % margin is the executive's prudence, not a lab requirement | lab clause, realization margin |
| `environment_before_store` | experiment `achieves (… (in (a controlled-environment …)))` | lab |
| `calibration_before_imaging` | measuring `requires (an instrument … (calibration current))`, establishable | lab |
| `dispense_completed` | intervening `achieves (… (received … (dose ?q))) :tolerance` | lab |
| `measurement_binding_validated` | measuring `achieves (… (binding validated))`, validity | lab |
| `tool_compatible` | derived from `prevents (an event (type contamination-introduced))` | realization, traced to a lab clause |
| `interlocks_closed` | none: a cell norm (ISO 10218-2) | realization |
| `l12_airspace_clear` | none: a device-interference norm of the cell | realization |
| `projection_succeeds` | none: an executive acceptance rule, not a condition on the world | meta |

That is 10 of 14 runtime constraints at lab level, 3 realization-only (one of them derived from a lab clause), and 1
meta. Every realization constraint must name what it derives from: a lab clause or a cell norm. That link is what the
audit trail needs to answer "why did you do this?" across the boundary.

Cell 01's `cram_designator_schemas.yaml` splits the same way. For `dose`:

| Lab (LDL) | Realization |
|---|---|
| `plate_id`, `well_id`, `reagent_id`, `reagent_lot`, `intended_effect` | `component_id`, `component_prim`, `plate_frame`, `pipette_frame`, `tip_id` |
| `volume_uL`: the lab writes the dose; the volume is computed from the reagent's concentration (kernel F9) | `dispense_height_mm`, `dispense_rate_uL_s` |

## 7. Consequences for the kernel

1. **Device exchange becomes invisible at the lab level.** The imager swap no longer touches any lab text. What
   changes is whether `achieves (… (binding validated))` is *achievable*. Today (iteration 1), `imager_swapped`
   executes and ends NR3. With LDL the executive can see before execution that a validity effect is unachievable.
   **Decision for you:** refuse, or execute only if the experiment declares `(accepts (validity-gap …))`. I would
   refuse by default.
2. **Step substitution is means–ends over contracts.** Any realization whose effects entail the `achieves` and which
   preserves the inherited `prevents`/`maintains` is admissible. Inserting a calibration is establishing a `requires`.
   Recalibrating after a lapse is re-establishing it.
3. **Workflow change is editing §5.1 only.** Dropping the control arm violates the experiment's `requires` before
   anything moves, as today, but now as a lab clause instead of a coded check.
4. **The kernel's lab-task cards lose their constraint-id lists.** Their `pre`/`post` fields become references to the
   LDL contract. The constraint registry keeps only the realization and meta rows of §6.
5. **The competency questions get a lab-level family** answered from the contract alone, before any run. Examples:
   "What must never happen while you dose A01?" (`prevents`); "What does this experiment promise?" (`achieves`);
   "Which monitor watches each prevented condition?" (admissibility).
6. **Sessions leave the lab vocabulary.** `culture-time` is the lab's clock. A session is a trip, which is
   realization.

## 8. Next step (proposed, not started)

Iteration 3a, before coraplex arrives or alongside it:

1. `rsa/ldl.py`:
   - parser for §3;
   - evaluator of conditions over the kernel's `Belief` and over a trail;
   - admissibility check of §4.
2. Write §5 as `rsa/registry/lab/challenge_rescue.ldl` and the four contracts as `rsa/registry/lab/*.ldl`.
3. Generate the lab-level checks from the clauses and delete the corresponding coded checks.
4. **Acceptance test:**
   - The 12 symbolic scenarios give the same verdicts, dispositions and repairs as now. The one intended
     difference is `imager_swapped` under the refuse default; it would be disclosed beforehand.
   - The 52 competency-question answers stay correct.
5. The coraplex surface: an LDL contract becomes `ActionDescription.pre_condition` / `post_condition` as krrood EQL
   over lab annotations. `prevents` and `maintains` have no coraplex counterpart; they need a monitor
   attachment, which goes to the proposal list with the device-command executable (D-LAT-11).

## 9. Open questions for you

1. **Instruments in lab text.** Attributive only, as proposed? Or not at all, with all instrument conditions moved
   into the measurement (`(a measurement … (by (an instrument …)))`)?
2. **`prevents` vs `maintains`.** Keep both, for their different operational obligations? Or normalise to `prevents`
   only?
3. **Unachievable validity effects.** Refuse (proposed default) or execute with a declared gap (§7.1)?
4. **Epistemic modality.** Is `(known φ)` (observed and fresh) enough? Or does K10 need more grades
   (inferred, assumed)?
5. **Quality (J of the ISRR triple).** Should v0.2 have a `prefers` clause, for example a shorter excursion?
6. **Real values.** Where do the window, tolerance and dose units come from for a real lab? Today they are twin
   values (D016).

## 10. v0.2: the decisions of 2026-10-17

| # | Your decision | How it is in the language | Checked by `rsa/ldl.py` |
|---|---|---|---|
| 1 | Instruments are attributive, but they fill a role: a slot the plate is inserted into, and a process that, once started, performs the action (injecting a substance, taking an image). | Each contract has an `instrument` role: `(an instrument ?d (slot (a plate-slot (accepts ?p))) (process (a process (type substance-transfer) …)))`. Realization is machine tending: insert, start, await, remove. | The role is resolved against the knowledge: an automated device with a plate seat, plus the function and capability verb of the process. dose → L12 `plate_nest`, incubation → L10 `transfer_station`, imaging → L17 `plate_load_frame`, each with 5 rejected devices and the reason. N7: a process no device offers is caught. |
| 2 | Keep `prevents` and `maintains`; add the goal of each step. | `(goal …)` per contract and for the experiment: `(goal (a result (of ?D) (information-gain (>= 0.5 bit))))`. `achieves` keeps the further enforced effects (records, events). | Causal links use goal and achieves. 8/8 step goals serve the experiment through the links. The experiment goal is supported by the design's EIG of 0.5439 bit ≥ 0.5 bit, given the achieved measurements. N8: a measurement nothing uses is caught. |
| 3 | An unachievable effect signals a CRAM failure with a description (`fail`); the control program says how to handle it. | `(signals (a failure (type …)))` per contract. `(handles (on (a failure (type …) (cause …)) (do …) (then retry \| replan \| escalate) (else …)))` in the experiment. coraplex port: a `PlanFailure` subclass carrying the failure designator. | Every signalled failure needs a handler: 20/20 handled. N6: a handler removed is caught. The swapped imager's `validity-effect-unachievable` is escalated by the handler. |
| 4 | Rich epistemic grades, so that a meta model can say how problems are treated. | Grade = source (observed > reported > inferred > assumed > predicted > unknown) × freshness × corroboration. `(known φ)` = observed and fresh; `(believed φ (grade …))`; use annotated `:consequential`. Meta model in `registry/lab/epistemic.yaml`: shortfall → treatment (re-observe, verify-before-commit, contain-and-escalate, …). | Every requirement has a treatment for every shortfall (4/4 requirement kinds × 7 shortfalls). Consistent with the kernel: identity swap → contradicted → contain-and-escalate; the freshness rule F2 → re-observe. |
| 5 | State quality explicitly, with KPIs. | `(quality (a kpi (name …) (of <entity description>) (aggregate …) (target …) (direction …)) … (prefers (lexicographic …)))`. The hard limit stays in `prevents`, the soft target is a KPI. | KPIs measured from 7 audit trails (5 symbolic, 2 Isaac). Lexicographic ranking of completed runs: nominal > tip_lost > isaac_nominal > calibration_lapsed. Targets ILLUSTRATIVE. |
| 6 | Re-parent the well frames under the plate. | Overlay composer step 5: the SDT plate is a frame tree (root on the L12 nest, plate-relative SBS wells, SBS body, no collider, guide purpose). | Composed A01 frames equal the frame chain the report computes. `make check` PASS. |
| 7 | prevent/maintain as non-terminating processes bounded by a scope that fluents open and close (RPL). | `(scope (begins-when φ) (ends-when ψ) (prevents …) (maintains …))`. The default scope is the action. In coraplex this is a `monitor` around the realization. | The cross-dosing prevent is scoped to the portion drawn for the action. The v0.1 mutual exclusion between dosing A01 and A02 disappears (0 exclusions). |

Still the same: 153-leaf kernel run identical to the planner's; the planner's order is a linear extension; 8/8 negative controls; the
symbolic suite passes 52/52.

## 11. v0.3: device processes, guarantees, expressive meta model, KPIs (2026-10-17, second round)

| Your answer | In the language | Checked |
|---|---|---|
| The processes within the devices have to be modelled and reasoned about; this affects the trustworthiness of an experiment in a critical aspect. | `registry/lab/processes.ldl`: per lab process its phases, the irreversible phase, and its faults. Each fault has `signals`, `corrupts`, `detected-by` with coverage, `persistence`, `removed-by` and the record's recovery. The model also lists evidence and must-not-assume. Grounded in the Cell 01 component records (L12, L17, L10, H4). | Grounding: 11/11 record faults modelled, every monitor, evidence and must-not-assume name found. Trust per step: dosing has well_misregistration partly detected and only after the irreversible dispense; imaging has plate_misseated partly detected (the F17 lateral shift); incubation excursions are detected, but only during the irreversible hold. N10: an unknown fault name is caught. |
| Repairs should provide guarantees for the final effects. | Every handler states `(guarantees goal \| goal-or-safe-state \| safe-state \| contained)`. | **goal** needs: the fault detected, occurring before the irreversible phase, and transient or removed by what the handler re-establishes. **safe-state** needs: the final branch escalates or abstains, the plate is restorable, nothing is committed, evidence is kept. **contained** needs a quarantining action with a containment goal. 13/13 claims hold. N9: the F17 focus retry without re-seating is caught. N11: a goal claimed after the irreversible dispense is caught. Against the recorded runs, all 7 repair events kept their claim. In 2 (the Isaac focus case) the kernel did not repair as prescribed: it refocused instead of re-seating. |
| The meta model needs to be done thoroughly later; for now we need the expressive power. | `registry/lab/epistemic.ldl` replaces the yaml. A rule conditions on grade dimensions (with comparisons over the source order), the item as an entity description, its use, the action context and the provenance. A treatment is a plan with then/else and a cost. | 10 rules, 8 treatments. Every requirement in its context has a treatment for every shortfall. N12: removing the rules for weak consequential beliefs is caught. |
| Reliability, safety and auditability are high up; there might be costs associated with them. | KPIs `safety` (sessions with a violated prevents-item), `reliability` (first-attempt share of designed goals), `auditability` (share of achieved goals with hash-chained evidence, if the trail verifies), and `cost` (weighted consumables, instrument minutes, escalations), ranked first in `prefers`. | Measured on 7 trails. Ranking: nominal > isaac_nominal > tip_lost > calibration_lapsed > isaac_calibration_lapsed > identity_swap > tool_changer_slow. Targets and weights ILLUSTRATIVE, to be developed later. |

Negative controls 12/12; the kernel run from the LDL poset is still identical to the planner's (153 leaves).
