---
type: fol-axioms
title: "Experiment-to-motion: deriving the robot's physical actions and motions from a required information gain"
derived_from: [L2/lab-twin-experiment-to-motion, L2/lab-twin-device-manuals, L2/lab-twin-safe-action, L2/lab-twin-devices, L2/lab-twin-poses]
inherits_from: [RS L3/experiment-design (ED1, ED2), RS L3/designator-refinement (DR1-DR5), AICOR L3/interval-temporal-logic]
maturity: L3
status: draft
timestamp: 2026-10-16
executable: L3-logical-axiomatization/derivation/experiment_to_motion.lp      # clingo (answer-set programming)
driver: L3-logical-axiomatization/derivation/derive_plan.py                   # ABox + EIG + twin traces -> facts -> plan
solver: L3-logical-axiomatization/derivation/validate_plan_z3.py              # independent z3 check of every plan
closure: L3-logical-axiomatization/derivation/realised_gain.py                # executed plan -> culture -> realised gain
---

# Experiment-to-motion: axioms

**The question.** Which physical actions and motions of the lab's robots and devices implement an experiment that
yields a required expected information gain *g* about Cell 01's competing recovery models?

**The answer.** These axioms answer it by a chain of refinements. They extend two calculi from the robot-scientist
vertical:
- the **experiment-design** rung (ED1: an EIG-optimal feasible selection; ED2: selection is not warrant);
- the **designator-refinement** calculus (DR1–DR5: refinement preserves goals and evidence; the
  material → scene → body-motion chain composes).

They add what those calculi leave to the domain: the axioms that **construct** each refinement from the lab's
ontology. The ontology supplies the device functions, the robot–station assignments, the seat and target poses, the
tools, the manual preconditions and the safety rules.

**How the axioms are used.** They are executable twice over:
- as an answer-set program, `derivation/experiment_to_motion.lp` (clingo), whose stable model **is** the derived
  plan;
- as properties that `derivation/validate_plan_z3.py` decides with z3 over the derived plan, using its own encoding of
  what each step means (a symbolic execution of plate, grippers, tool, shuttles, tips, airspace and flags). It runs
  with ten negative controls (mutated plans), so the checker is independent of the program that derived the plan.

**Conventions** (AICOR `axiom-conventions.md`): sorted first-order logic over AICOR's reified interval temporal logic
(`holds` / `occurs`). Every axiom declares its side:
- **[DL]:** a DL shadow in `lab-twin-experiment-to-motion-dl.md`, checked by HermiT;
- **[FOL]:** order, quantified structure;
- **[SMT]:** arithmetic, discharged by z3.

`:=` marks definitional axioms; all others are substantive.

## Signature

**Sorts:**

| Variable | Sort |
|---|---|
| `c` | candidate experiment |
| `m` | competing model (M1 graded, M2 threshold, M3 protective) |
| `w` | well |
| `s` | protocol session |
| `k` | trip |
| `v` | station / fixture referent |
| `r` | robot |
| `p` | pose (TwinPose) |
| `T` | tool |
| `d` | designator |
| `t` | culture time (h) |
| `i`, `j` | step positions |

**Functions:**
- **Candidate properties:** `eig(c)` (bits, I(M; y | c, D)), `cost(c)`, `dose(c)`, `delay(c)`, `reps(c)`.
- **Durations:** `dur(d)` (s, from the twin's run traces).
- **Poses:** `seat(v)` (the plate-transfer seat pose of `v`), `appr(p)` (the approach pose above `p`),
  `target(w, f)` (the pipetting / imaging target pose of well `w`).

**Predicates:**
- **Ontology facts (from the ABox, see the table below):** `Serves(r, v)`, `HasFunction(v, f)`, `Automated(v)`,
  `HoldsPlate(v)`, `Home(v)`, `RequiresTool(r, T)`, `Coupled(r, T)`, `Compatible(T)`, `Calibrated(v)`,
  `InterlocksClosed`, `Free(w)`.
- **Derived:** `Selected(c)`, `Role(w, ρ)` with `ρ ∈ {rescued, comparator, control}`, `Material(d)`, `Scene(d)`,
  `Motion(d)`, `refines(d′, d)`, `In(d, s, k)`, `pos(d) ∈ ℕ`.

`Occurs(d, t)` is AICOR's `occurs` of `d`'s occurrence over interval `t`; `Before(d1, d2) := pos(d1) < pos(d2)`
within a trip.

## Axioms

### Selection: what must be learned decides what is done

**(E2M1) Gain-constrained least-cost selection** [SMT] (refines ED1)

```
Selected(c) ↔ Feasible(c) ∧ eig(c) ≥ g ∧ ¬∃c′ (Feasible(c′) ∧ eig(c′) ≥ g ∧ cost(c′) < cost(c))
```

- Ties are broken by higher `eig`.
- **Variant `g = max`:** `Selected = argmax_{Feasible} eig` (ED1).
- **What it says:** the experiment run is the cheapest one that teaches at least `g`. Unlike ED1, `Feasible`
  includes the *derived* plan's feasibility (E2M8). Selection stays separate from warrant (ED2): a selected candidate
  is executed only inside the authorisation envelope.

**(E2M2) Information gain** := (Cell 01 `mathematical-models.md` §10)

```
eig(c) := Σ_m p(m | D) · E_{y ∼ p(y | m, c)} KL( p(M | D, y, c) ‖ p(M | D) )
```

This is computed, not reasoned. It enters the theory as a frame constant per candidate (`twin/culture/eig.py`,
nested Monte Carlo).
- The models' parameter priors are **calibrated to D**: each sample reproduces the observed 6 h rescue effect.
- So `eig(c) ≈ 0` for any `c` that repeats what D already shows: the derived consequence D1 below.

### Expansion: experiment → material designators

**(E2M3) Arms and units** [DL + FOL]

```
Selected(c) → |{w : Role(w, rescued)}| = reps(c) ∧ |{w : Role(w, comparator)}| = reps(c)
            ∧ |{w : Role(w, control)}| ≥ 1 ∧ ∀w ∀ρ ≠ ρ′ ¬(Role(w, ρ) ∧ Role(w, ρ′)) ∧ (Role(w, ρ) → Free(w))
```

- **DL shadow:** `DelayedRescueStudyDesign ⊑ ∃hasArm.ChallengeRescueArm ⊓ ∃hasArm.ChallengeOnlyArm ⊓
  ∃hasArm.ControlArm`.
- **Why the control:** a comparator and an untreated control are required. That is the "control structure present"
  precondition of Cell 01's `challenge_authorization`.

**(E2M4) Sessions and material designators** [FOL, interval logic]

There are three sessions: `s₀` (challenge), `s₁` (rescue) and `s₂` (readout). They satisfy:

```
Occurs(s₀, t₀) ∧ Occurs(s₁, t₁) ∧ Occurs(s₂, t₂)
  ∧ t₁ − t₀ = delay(c) ∧ t₂ − t₀ = 72 h ∧ Before(s₀, s₁) ∧ Before(s₁, s₂)        (Allen: s₀ < s₁ < s₂)
```

Each session carries these material designators:

| Session | Material designators |
|---|---|
| `s₀` | `Dose(w, challenge, dose(c))` for each `w` with `Role(w, rescued) ∨ Role(w, comparator)` |
| `s₁` | `Dose(w, rescue, 0.70 au)` for each `w` with `Role(w, rescued)` |
| `s₂` | `Image(w)` for each `w` with any role |

- **DL shadow:** `ChallengeDoseDesignator`, `RescueDoseDesignator` and `ImageWellDesignator ⊑ MaterialStepDesignator`.

### Allocation and routing: material → scene designators

**(E2M5) Device allocation** [FOL]

```
Material(d) ∧ kind(d) = κ → ∃v (Automated(v) ∧ HasFunction(v, f(κ)) ∧ Scene(d′) ∧ refines(d′, d) ∧ boundTo(d′, v))
```

- **Function per kind:** `f(Dose) = dispensing` and `f(Image) = imaging`.
- **Home:** `Home(v) ↔ Automated(v) ∧ HasFunction(v, incubation)`. The plate rests at its home between sessions.

**(E2M6) Transfer routes** [FOL]

- **Transfer edges:** `Edge(r, a, b) := Serves(r, a) ∧ Serves(r, b) ∧ a ≠ b ∧ HoldsPlate(a) ∧ HoldsPlate(b)`.
- **Outbound:** a trip to device `v` is a shortest edge path from `Home` to `v`. Each edge `(r, a, b)` is one
  `PlateTransfer(r, seat(a), seat(b))` scene designator.
- **Return:** the reverse path. **Between devices:** the shortest path from the previous device.
- **DL shadow:** `PlateTransferDesignator ⊑ ∃performedByRobot.CellRobot ⊓ ∃boundToPose.PlateSeatPose`.
- **Why a handover:** R01 serves L10 and the handover nest; R02 serves the nest, L12, L17 and L21. So L10 → L12
  routes `L10 –R01→ HN –R02→ L12`. No robot reaches both L10 and L12: the reachability study behind layout P1.

### Refinement: scene → motion and command designators

**(E2M7) Motion refinement** [FOL]

```
PlateTransfer(r, p, q) refines into the Meets-ordered sequence
  ⟨ Approach(r, appr(p)), Insert(r, p), Grasp(r), Lift(r), Transit(r, appr(p), appr(q)),
    Approach(r, appr(q)), Place(r, q), Release(r), Retract(r, appr(q)) ⟩

RequiresTool(r, T) ∧ ¬Coupled(r, T) → ∃d (ToolCouple(r, T) ∧ Before(d, first motion of r in the trip))

DeviceOp(v, Dose(w, ρ, a)) refines into ⟨ TipPick(v, rack), Aspirate(v, reagent(ρ)), Dispense(v, target(w, pipette)),
                                         TipEject(v, waste) ⟩
DeviceOp(v, Image(w))      refines into ⟨ ImageWell(v, target(w, imaging)) ⟩   (after one Load(v) per trip)
Present(v) before the pick from v; Stow(v) after the place into v (when v has a shuttle / gate)
```

- **What it is:** the body-motion level of the RS chain (`MotionStepDesignator ⊑ BodyMotionDesignator`). Every
  motion is bound to a pose of the twin and a robot.
- **Device commands** (`DeviceCommandDesignator`) are the corresponding level for a station's own mechanisms.

### Safety: the safe-action module as constraints on every derived sequence

**(E2M8) Safety and manual preconditions** [FOL + SMT]

For every trip `k` with steps ordered by `pos`, the following must hold. Each constraint is a rule of
`lab-twin-safe-action` or a precondition of a Cell 01 contract.

| | Constraint | Formula | Source |
|---|---|---|---|
| (S1) | Deck airspace | `Place(r, seat(v)) ∧ DeviceOp(v, ·) ∧ Before(place, op) → ∃ Retract(r, appr(seat(v))) between them` | rule `l12_deck_airspace` |
| (S2) | Environment | `Store(Home) → ∃ WaitEnvironment(Home) before it in the trip` | rule `l10_environment_valid`; L10 contract `incubate` "environment valid" |
| (S3) | Calibration | `Image at position i → Calibrated(L17) ∨ ∃ QC(L21, L17) at j < i` | rule `l17_calibration_valid`; L17 contract "calibration valid" |
| (S4) | Tool compatibility | `ToolCouple(r, T) ∧ ContactsCulture(T) → Compatible(T)` | rule `tool_contamination_compatible` |
| (S5) | Time outside the incubator | `(1 + μ) · Σ_{d ∈ trip k} dur(d) ≤ window`, margin μ = 0.2 over the trace estimates | Cell 01 protocol request (D016 demo value) |
| (S6) | Interlocks | `InterlocksClosed` holds at every trip start | rule `enclosure_door_interlock` |
| (S7) | Identity | each trip begins with `VerifyIdentity(Home)` | rule `identity_verified`; L10 `release_plate` "identity consistent" |
| (S8) | Contamination | `ContaminationSuspected(plate) → ¬∃ Dose(·, ·, ·)` in the plan | rule `contamination_suspected_blocks` |
| (S9) | Control structure | `Dose(·, challenge, ·) → ∃w Role(w, control)` | rule `challenge_requires_controls` |

**Feasibility.** `Feasible(c)` holds iff a plan exists that satisfies E2M3–E2M8. When (S5) cannot hold for one trip,
the derivation splits the session into more trips, which costs more (E2M1's `cost`).

**Why the margin μ.** The first version used the nominal durations. z3 then showed that a 300 s window, packed to
298.9 s per trip, is violated as soon as the twin runs a fifth slower than its traces (V3). (S5) now carries the same
margin that z3 checks.

**Refusals carry their reason.** When no plan exists, `derive_plan.py` re-solves with one constraint relaxed at a
time (`relax(sN)`, never asserted in a derivation) and reports which rule blocks. Examples: S8 for a plate under
suspected contamination, S6 for an open door, S5 for a window too short for even one dose.

### Preservation (inherited)

**(E2M9) Refinement preserves goals and evidence** [FOL, = DR1–DR3]

```
refines(d′, d) → goals(d′) = goals(d) ∧ ev(d′) = ev(d)
```

The material → scene → motion chain composes. A motion designator therefore carries the material designator's goal,
for example "challenge well B06 with 0.85 au", and the evidence it must produce (dose record, image record).

## Derived consequences

- **(D1) Repeating the known experiment teaches nothing:** `delay(c) = 6 h → eig(c) < ε`, from E2M2 and the
  calibration to D, decided numerically. EIG is ≈ 0.01 bits at 6 h, against 0.54–0.64 bits at 48 h.
- **(D2) Information has a price:** `g > max_c eig(c) → ¬∃c Selected(c)` [SMT]. No plan exists, and the derivation
  reports unsatisfiable rather than running a weaker experiment.
- **(D3) Uncalibrated imager:** `¬Calibrated(L17) → every derived plan has a QC step before the readout trip's first
  image` [FOL], from E2M8 (S3).
- **(D4) Airspace:** no derived plan commands an L12 dose while the robot that placed the plate is still in L12's
  airspace [FOL], from E2M7 + E2M8 (S1).
- **(D5) Least cost:** a selected plan meets `g` at least cost, i.e. no feasible candidate with `eig ≥ g` costs less
  [SMT], from E2M1.
- **(D6) Every material designator is realised:** each one is refined to ≥ 1 scene designator and each of those to
  ≥ 1 motion / command designator (completeness), from E2M5–E2M7.

## Counterexample (what the axioms rule out)

Here is a plan that picks the most informative candidate for g = 0.5 bits (0.85 au, 48 h, 3 replicates) and doses as
soon as R02 has placed the plate on L12:
- It violates E2M1: one replicate already meets g, and a single replicate costs 9,986 against 14,606.
- It violates (S1): the dose happens with R02 in the deck airspace.
- If L17's calibration lapsed during the 72 h, it also violates (S3): it images without QC.

`validate_plan_z3.py` exhibits each of these as a satisfiable violation of the mutated plan (negative controls N1,
N3 and N8). For the derived plan, the same queries are unsatisfiable.

## Honest scope

- **The selection is bounded.** E2M1 is decided over a finite candidate frame: 3 doses × 5 delays × 3 replicate
  counts.
- **EIG is approximate.** E2M2 is a Monte-Carlo estimate (≈ ±0.02 bits), and the models' parameters are illustrative
  (D016).
- **Cost does not see the delay.** Cost counts robot and device time plus wells, which do not depend on the
  rescue delay. Among candidates of equal cost the tie-break (max EIG) therefore always picks the longest delay in the
  frame (48 h). A cost on culture time or incubator occupancy would change that; it is a modelling choice, not
  a derived fact.
- **Durations are apportioned.** Leg and dose durations are medians of the twin's run traces. Their split over motion
  primitives is a fixed illustrative ratio (`LEG_SPLIT`, `DOSE_SPLIT` in `derive_plan.py`). The QC step's 120 s is
  an estimate, and the L10 present time is derived from the retrieve trace (an overestimate on the return leg).
- **QC is one command here.** In the twin, `validate(L17)` is L21's reference-plate procedure (R02 carries the
  reference plate). The derivation treats it as one device command with a duration.
- **Motions are symbolic.** The derivation targets poses; continuous trajectories come from the twin's planners
  (`twin/r01_planner.py`, the R02 rail and IK). Execution in Isaac then checks that the derived motions are physically
  realisable.

## Executable form and results (2026-10-17)

**Pipeline.**
1. `derive_plan.py` turns the ontology ABox into clingo facts:
   - automated devices and their functions, `servesStation`, plate seats, well and rack poses, tools, free wells;
   - the safety rules;
   - durations from the twin's run traces;
   - the 45 EIG candidates.
2. `experiment_to_motion.lp` (E2M1, E2M3–E2M8) finds the optimal stable model, which is the plan: material,
   scene, motion and command designators per trip.
3. `validate_plan_z3.py` checks the plan with an **independent** encoding: a symbolic execution of plate, grippers,
   tool, shuttles, tips, airspace and flags, for every unknown initial tool and stage state.
4. `run_cell01_episode.py --plan` executes the plan in Isaac.
5. `realised_gain.py` feeds the executed doses into the culture world and computes the posterior and the realised
   gain.

| Required gain | Lab state | Derived experiment | Trips (s outside L10) | z3 |
|---|---|---|---|---|
| 0.25 / 0.50 bits | nominal | 0.85 au, rescue 48 h, n = 1 (EIG 0.544) | 299 · 263 · 256 | 7/7 theorems, 10/10 negatives |
| 0.55 bits | nominal | 0.85 au, 48 h, n = 2 (0.601) | 370 · 299 · 261 | idem |
| 0.62 bits | nominal | 0.85 au, 48 h, n = 3 (0.641) | 441 · 335 · 265 | idem |
| 0.62 bits | window 400 s | idem; challenge split 3 trips, rescue 2 | 6 trips ≤ 299 | idem |
| 0.50 bits | L17 calibration expired | n = 1 + QC step before imaging | readout 376 | idem |
| 0.50 bits | T01 known coupled | n = 1 without tool changes | 257 · 222 · 215 | idem |
| 0.70 bits | nominal | **refused:** no candidate reaches it (max 0.641) | — | — |
| 0.50 bits | contamination suspected | **refused:** blocked by S8 | — | — |
| 0.50 bits | enclosure door open | **refused:** blocked by S6 | — | — |

Solving is fast: ground ≈ 0.05 s, optimality proven in ≈ 0.04 s.

**Twin execution of the 0.5-bit plan** (Cell 01 scene, PhysX, `test_reports/e2m/plan_execution_g050.json`).

| Trip | Steps OK | Twin time | Predicted | Window |
|---|---|---|---|---|
| s0 challenge | 52/52 | 305.7 s | 298.9 s | 600 s |
| s1 rescue at 48 h | 48/48 | 230.2 s | 263.3 s | 600 s |
| s2 readout at 72 h | 51/51 | 212.3 s | 256.4 s | 600 s |

- **Doses:** L12 inferred 17.00 / 17.02 µL (challenge) and 14.01 µL (rescue) against 17 / 14 µL commanded.
- **L12 airspace:** clear before every dose (S1, observed by L12's own interlock).
- **Identity:** the L10 barcode read `Plate_P17` at every release and store.
- **Imaging:** A01's first image was out of focus and was reacquired, as the contract's recovery requires.

**Realised gain** (Cell 01 surrogate culture world, D016):
- **This realisation:** the posterior moved from uniform to M1 0.61 / M2 0.19 / M3 0.20. Realised gain 0.227 bits
  against an expected 0.544.
- **Over 40 culture realisations with the same executed doses:** mean 0.21 bits, p10–p90 0.02–0.34. The MAP model was
  M2 or M3 in 39 of 40.

**Reading.** The twin's culture behaves like M2/M3 at 48 h:
- The observed effect is 24 ± 6 µm, against predicted means of 25 µm for M2/M3 and 8.5 µm for M1.
- In that world one replicate mostly moves mass off M1, and M2 and M3 stay inseparable. So the realised gain is
  bounded by log₂3 − 1 = 0.585 bits, and in practice it is much lower.
- The requirement is on the **expected** gain (E2M1). The EIG averages over worlds where M1 holds, and there the
  gain is larger.

**Sequential design** (`derive_plan.py --prior-from out/realised_g050.json`):
- The derivation conditions on the posterior and excludes the consumed wells.
- It re-derives the same design on fresh wells A06/A07/A08 (EIG 0.539 bits), and z3 proves it.
- Separating M2 from M3 needs an intervention outside this frame, for example priming the protective response.

**Findings from the checks.**
- (i) z3 rejected the first encoding's nominal-duration window check: the robustness margin of S5 came from it.
- (ii) z3 caught one negative control only after the approach semantics were tightened, so a "teleporting"
  approach is now a violation.
- (iii) The twin interpreter first left the trailing tip ejection unchecked. It now requires every step executed and
  checked.
