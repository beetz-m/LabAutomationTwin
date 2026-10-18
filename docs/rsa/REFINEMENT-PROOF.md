# Refinement proof: motion plan → culture plan

`env_cad/bin/python -m rsa.refinement_proof` writes `rsa/out/refinement_proof.json` and exits 1 if any obligation fails.
`python3 -m rsa.proof_page` renders `docs/rsa/plan/proof.html`.

## Theorem

Under assumptions A1–A6, every execution of the motion-level plan (the 151 steps of plan_g050, whose 111 robot motions are giskardpy motion statecharts) does one of two things:

1. It realizes the culture plan:
   - every physical and knowledge effect, in the derived order, at 0/48/72 h;
   - the control culture stays untreated;
   - all stated constraints hold: interlocks, L12 airspace, identity, environment before store, calibration before imaging, the 600 s window, contamination freedom, tool hygiene, plate level, and collision distance.
2. Or a monitor stops it, and it ends in a failure handler whose guarantee holds.

## Obligations

| | Link | Discharged by |
|---|---|---|
| O1 | culture plan well formed | `culture_plan.derive` |
| O2 | the step-level events (V4) plus the vessel map entail the culture effects, the order and the prevents | z3; 14 obligations; each negation UNSAT |
| O3 | lab plan: links, threats 9/9, instruments, guarantees 13/13 | `ldl.py`, `ldl_trust.py` |
| O4 | step plan: V1–V5 | `validate_plan_z3.py`, re-run; 10/10 of its own negative controls |
| O5 | no plate-handling tool touches the culture | z3 |
| O6 | 111/111 motions: each refines its step, its end monitor implies the postcondition (under A3), and tilt, collision and duration are hold-or-cancel (timeout ≤ 1.2 × estimate, which is V3's assumption) | `refinement_proof.motion_proof` |
| O7 | every cancellation reaches a handler with a verified guarantee | `refinement_proof.py` |

Eight negative controls (swapped vessel map, dosed control, missing control image, contaminating tool, missing tilt cancel, 1.5× timeout, wrong motion type, the validator's 10 mutants): all caught.

## Assumptions

- **A1** giskardpy statechart semantics: a motion ends either by `EndMotion` or by `CancelMotion`.
- **A2** monitor and sensor soundness.
- **A3** pose tolerance lies within mechanical capture: 0.4 mm convergence, 2 mm capture (ILLUSTRATIVE).
- **A4** grasp holds (monitored).
- **A5** device contracts.
- **A6** goal frames reachable (checked, 25/25).

## Not proved

- **Progress:** the plan may cancel rather than finish.
- **Partially detected faults:** L12 well misregistration and L17 plate misseating (6/27 fault instances) lie outside branch 2.
- **Physics:** compliant insertion is not modelled.
- **Execution of the Giskard module:** it is not run, because there is no SDT World.
- **R02 offline collision checking.**
- **Biology:** the goal is expected information gain under the surrogate model.
