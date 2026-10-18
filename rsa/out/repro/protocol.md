# Experimentation plan: challenge-rescue/c_d85_t48_n1

_Status: ILLUSTRATIVE (D016): the culture biology is Cell 01's surrogate; no biomedical parameter is asserted._

- Input digest: `d514d47b1ad1b07549cdee66c5db8b0b00ac277c76790f3746471ba2e515057e`
- Plan (clingo) sha256: `2b8dcf3efc1a3bfeef60b9859bf3db39f0cd3038afcb96cd7634270b18111247`

## 1. Question and goal

```lisp
(which (a recovery-model (in (M1_graded M2_threshold M3_protective))) (explains (the rescue-efficacy (after (a delay (of 48 h))))))
```

Goal: `(the belief ?B (expected-information-gain (>= 0.5 bit)))`

Entities:

- `?cr` (the culture ?cr (role rescued))
- `?cc` (the culture ?cc (role comparator))
- `?ck` (the culture ?ck (role control))
- `?ch` (some substance ?ch (type challenge))
- `?rs` (some substance ?rs (type rescue))
- `?B` (the belief ?B (over (M1_graded M2_threshold M3_protective)) (prior uniform))

## 2. Design

Selected `c_d85_t48_n1`: challenge 0.85 au to the rescued and comparator cultures at 0 h; rescue 0.7 au to the rescued culture after 48 h; 1 replicate; images at 72 h. Expected information gain 0.5439 bit (required 0.5 bit) over a uniform prior on M1_graded, M2_threshold, M3_protective. Cost 9986 decisecond-equivalents (robot / device time + 60 s per well).

| Candidate meeting the requirement | EIG (bit) | Optimal plan cost |
|---|---|---|
| `c_d45_t36_n3` | 0.5072 | 14606 |
| `c_d45_t48_n2` | 0.5474 | 12296 |
| `c_d45_t48_n3` | 0.5883 | 14606 |
| `c_d65_t36_n2` | 0.5042 | 12296 |
| `c_d65_t36_n3` | 0.5458 | 14606 |
| `c_d65_t48_n1` | 0.5205 | 9986 |
| `c_d65_t48_n2` | 0.5787 | 12296 |
| `c_d65_t48_n3` | 0.6205 | 14606 |
| `c_d85_t36_n2` | 0.528 | 12296 |
| `c_d85_t36_n3` | 0.5717 | 14606 |
| `c_d85_t48_n1` (selected) | 0.5439 | 9986 |
| `c_d85_t48_n2` | 0.6013 | 12296 |
| `c_d85_t48_n3` | 0.6415 | 14606 |

## 3. Culture plan

| | Action |
|---|---|
| ?c1 | `(an action ?c1 (type challenging) (culture ?cr) (substance ?ch) (dose 0.85 au) (at (culture-time 0 h)) (physical (the culture ?cr (exposed-to ?ch 0.85 au)) (the culture ?cr (injury rising))) (knowledge (a record (of ?c1) (states ?cr ?ch 0.85 au 0 h))))` |
| ?c2 | `(an action ?c2 (type challenging) (culture ?cc) (substance ?ch) (dose 0.85 au) (at (culture-time 0 h)) (physical (the culture ?cc (exposed-to ?ch 0.85 au)) (the culture ?cc (injury rising))) (knowledge (a record (of ?c2) (states ?cc ?ch 0.85 au 0 h))))` |
| ?g1 | `(an action ?g1 (type growing) (cultures ?cr ?cc ?ck) (from (culture-time 0 h)) (to (culture-time 48 h)) (requires (the culture ?cr (exposed-to ?ch)) (the culture ?cc (exposed-to ?ch))) (physical (the experiment ?E (culture-time 48 h)) (the culture ?cr (injury-burden accumulated))) (knowledge (a record (of ?g1) (environment-history culture-standard))))` |
| ?c3 | `(an action ?c3 (type rescuing) (culture ?cr) (substance ?rs) (dose 0.70 au) (at (culture-time 48 h)) (requires (the experiment ?E (culture-time 48 h))) (physical (the culture ?cr (exposed-to ?rs 0.70 au)) (the culture ?cr (recovery possible))) (knowledge (a record (of ?c3) (states ?cr ?rs 0.70 au 48 h))))` |
| ?g2 | `(an action ?g2 (type growing) (cultures ?cr ?cc ?ck) (from (culture-time 48 h)) (to (culture-time 72 h)) (requires (the culture ?cr (exposed-to ?rs))) (physical (the experiment ?E (culture-time 72 h)) (the culture ?cr (viability settled))) (knowledge (a record (of ?g2) (environment-history culture-standard))))` |
| ?o1 | `(an action ?o1 (type observing) (culture ?cr) (readout morphology) (at (culture-time 72 h)) (requires (the experiment ?E (culture-time 72 h))) (physical (the culture ?cr (light-dose increased))) (knowledge (an image ?y1 (of ?cr) (culture-time 72 h) (raw true))))` |
| ?o2 | `(an action ?o2 (type observing) (culture ?cc) (readout morphology) (at (culture-time 72 h)) (requires (the experiment ?E (culture-time 72 h))) (physical (the culture ?cc (light-dose increased))) (knowledge (an image ?y2 (of ?cc) (culture-time 72 h) (raw true))))` |
| ?o3 | `(an action ?o3 (type observing) (culture ?ck) (readout morphology) (at (culture-time 72 h)) (requires (the experiment ?E (culture-time 72 h))) (physical (the culture ?ck (light-dose increased))) (knowledge (an image ?y3 (of ?ck) (culture-time 72 h) (raw true))))` |
| ?i1 | `(an action ?i1 (type interpreting) (image ?y1) (into organoid-radius) (requires (an image (of ?cr) (raw true)) (a scale (of (an image)) (known true)) :establishable) (knowledge (an estimate (of ?cr) (organoid-radius) (sigma 2.5 um))))` |
| ?i2 | `(an action ?i2 (type interpreting) (image ?y2) (into organoid-radius) (requires (an image (of ?cc) (raw true)) (a scale (of (an image)) (known true)) :establishable) (knowledge (an estimate (of ?cc) (organoid-radius) (sigma 2.5 um))))` |
| ?i3 | `(an action ?i3 (type interpreting) (image ?y3) (into organoid-radius) (requires (an image (of ?ck) (raw true)) (a scale (of (an image)) (known true)) :establishable) (knowledge (an estimate (of ?ck) (organoid-radius) (sigma 2.5 um))))` |
| ?a1 | `(an action ?a1 (type analysing) (belief ?B) (statistic (difference (radius ?cr) (radius ?cc))) (requires (an estimate (of ?cr) (organoid-radius)) (an estimate (of ?cc) (organoid-radius)) (an estimate (of ?ck) (organoid-radius))) (knowledge (the belief ?B (posterior updated)) (the belief ?B (information-gain measured))))` |

Order (Hasse edges): ?c1 < ?g1, ?c2 < ?g1, ?c3 < ?g2, ?g1 < ?c3, ?g2 < ?o1, ?g2 < ?o2, ?g2 < ?o3, ?i1 < ?a1, ?i2 < ?a1, ?i3 < ?a1, ?o1 < ?i1, ?o2 < ?i2, ?o3 < ?i3

## 4. Vessels

| Culture | Role | Plate | Well |
|---|---|---|---|
| `?cr` | rescued | P17 | A01 |
| `?cc` | comparator | P17 | A02 |
| `?ck` | control | P17 | A05 |

## 5. Refinement into the laboratory

| Culture action | Lab action | Process | Realized by |
|---|---|---|---|
| ?c1 challenging | ?x1 intervening | substance-transfer | l12 |
| ?c2 challenging | ?x2 intervening | substance-transfer | l12 |
| ?g1 growing | ?w1 incubating | incubation | l10 |
| ?c3 rescuing | ?x3 intervening | substance-transfer | l12 |
| ?g2 growing | ?w2 incubating | incubation | l10 |
| ?o1 observing | ?m1 measuring | imaging | l17 |
| ?o2 observing | ?m2 measuring | imaging | l17 |
| ?o3 observing | ?m3 measuring | imaging | l17 |
| ?i1 interpreting | - computation |  | culture SDT image analysis (twin/culture/optics.analyse): radius from the calibrated pixel size |
| ?i2 interpreting | - computation |  | culture SDT image analysis (twin/culture/optics.analyse): radius from the calibrated pixel size |
| ?i3 interpreting | - computation |  | culture SDT image analysis (twin/culture/optics.analyse): radius from the calibrated pixel size |
| ?a1 analysing | - computation |  | posterior over M1-M3 (twin/culture/eig.posterior_over_models) on the rescued - comparator radius |

Lab action designators:

```lisp
(an action ?x1 (type intervening) (into ?r) (substance ?ch) (dose 0.85 au) (at (culture-time 0 h)))
(an action ?x2 (type intervening) (into ?c) (substance ?ch) (dose 0.85 au) (at (culture-time 0 h)))
(an action ?w1 (type incubating) (plate ?p) (in ?env) (from (culture-time 0 h)) (to (culture-time 48 h)) (requires (the well ?r (received ?ch)) (the well ?c (received ?ch))))
(an action ?x3 (type intervening) (into ?r) (substance ?rs) (dose 0.70 au) (at (culture-time 48 h)))
(an action ?w2 (type incubating) (plate ?p) (in ?env) (from (culture-time 48 h)) (to (culture-time 72 h)) (requires (the well ?r (received ?rs))))
(an action ?m1 (type measuring) (of ?r) (readout organoid-radius) (at (culture-time 72 h)))
(an action ?m2 (type measuring) (of ?c) (readout organoid-radius) (at (culture-time 72 h)))
(an action ?m3 (type measuring) (of ?k) (readout organoid-radius) (at (culture-time 72 h)))
```

## 6. Sessions

Start state: {'calibrated': True, 'coupled': False, 'interlocks': True, 'contaminated': False}. Window outside the incubator per trip: 600.0 s.

| Session | Culture time | Device | Material | Steps | Duration | Route out |
|---|---|---|---|---|---|---|
| s0 | 0 h | L12 | dose a01 challenge 85; dose a02 challenge 85 | 52 | 298.9 s | r01 l10->handovernest; r02 handovernest->l12 |
| s1 | 48 h | L12 | dose a01 rescue 70 | 48 | 263.3 s | r01 l10->handovernest; r02 handovernest->l12 |
| s2 | 72 h | L17 | image a01; image a02; image a05 | 51 | 256.4 s | r01 l10->handovernest; r02 handovernest->l17 |

Robot motions: 111 Giskard motion statecharts over 12 transport legs.

## 7. Constraints

| Clause | Condition | Status |
|---|---|---|
| requires | `(the plate ?p (contamination none))` | verified by the realization |
| requires | `(the design ?D (arm (role control)))` | holds in the design |
| prevents | `(an excursion (of ?p) (duration (> 600 s)))` | no step achieves it (statically) |
| prevents | `(a transfer (of (some substance)) (into ?k))` | no step achieves it (statically) |
| prevents | `(an event (type contamination-introduced) (of ?p))` | no step achieves it (statically) |

## 8. Failure handling

- `(on (a failure (type identity-mismatch)) (do (an action (type quarantining) (material (the plate (identity mismatched))))) (then escalate) (guarantees safe-state contained))`
- `(on (a failure (type measurement-invalid) (cause calibration_expired)) (do (re-establish (an instrument (function imaging) (calibration current)))) (then replan) (else escalate) (guarantees goal-or-safe-state))`
- `(on (a failure (type measurement-invalid) (cause out_of_focus)) (do (re-establish (the plate ?p (seated true)))) (then (retry (max 1))) (else escalate) (guarantees goal-or-safe-state))`
- `(on (a failure (type measurement-invalid) (cause plate_misseated)) (do (re-establish (the plate ?p (seated true)))) (then (retry (max 1))) (else escalate) (guarantees goal-or-safe-state))`
- `(on (a failure (type validity-effect-unachievable)) (then escalate) (guarantees safe-state))`
- `(on (a failure (type dose-not-delivered) (cause wrong_reagent)) (do (re-establish (some substance ?s (identity verified)))) (then (retry (max 1))) (else escalate) (guarantees goal-or-safe-state))`
- `(on (a failure (type dose-not-delivered) (cause tip_missing_or_dropped)) (then (retry (max 1))) (else escalate) (guarantees goal-or-safe-state))`
- `(on (a failure (type dose-not-delivered) (cause clog_or_air_aspiration)) (then escalate) (guarantees safe-state))`
- `(on (a failure (type dose-not-delivered) (cause well_misregistration)) (do (an action (type quarantining) (material ?p))) (then escalate) (guarantees safe-state contained))`
- `(on (a failure (type contamination-suspected)) (do (an action (type quarantining) (material ?p))) (then escalate) (guarantees safe-state contained))`
- `(on (a failure (type environment-excursion)) (do (restore (the plate ?p (in ?env)))) (then escalate) (guarantees safe-state))`
- `(on (a failure (type containment-breach)) (then escalate) (guarantees safe-state))`
- `(on (a failure (type prevents-violated)) (do (restore (the plate ?p (in ?env)))) (then escalate) (guarantees safe-state))`

## 9. Quality and acceptance

| KPI | Of | Aggregate | Target |
|---|---|---|---|
| safety | `(each violation (of (a prevents-item (in ?E))))` | count | <= 0.0  |
| reliability | `(each goal (of (an action (in ?E))))` | first-attempt-fraction | >= 1.0  |
| auditability | `(each goal (of (an action (in ?E))))` | evidenced-fraction | >= 1.0  |
| excursion-time | `(each excursion (of ?p))` | max | <= 300.0 s |
| cost | `(each resource (used-by ?E))` | weighted-sum | <= 10.0 cost-units |
| dose-deviation | `(each transfer (into (a well (of ?p))))` | max | <= 2.0 % |
| time-to-result | `?E` | span | <= 72.5 h |

Realization: every designed intervention and measurement executed; no prevents-item violated. Validity checks: V1_identity_continuity, V2_calibration_at_measurement, V3_binding_validated, V4_controls_present, V5_dose_delivered, V6_sample_integrity, V7_design_realised. Competency questions answered: 52/52. Refinement proof holds: True.

## 10. Records

Every designator lifecycle transition is one entry of a SHA-256 hash chain (prev hash + canonical JSON), written by the executor, never by the plan. Entries carry agent, software (kernel, KB, registry hash, backend), simulated time, bindings, resolutions, constraint verdicts (realization | validity), monitors and evidence with its own sha256.

| Trail | Entries | Chain | Tamper detected | Re-executed | Head | End | Disposition |
|---|---|---|---|---|---|---|---|
| calibration_lapsed | 569 | intact | True | identical | `e71f6e131dfa3c98` | executed | commit: result may update the culture belief |
| card_incomplete | 3 | intact | True | identical | `d75e11ff5b379e9b` | abstained | refused before execution |
| contamination | 3 | intact | True | identical | `c060395b5c2dfde5` | abstained | refused before execution |
| control_dropped | 3 | intact | True | identical | `703458117a2aca69` | abstained | refused before execution |
| identity_swap | 224 | intact | True | identical | `d55ba8ba256e9a11` | escalated | escalated: human decision required; nothing committed |
| imager_incapable | 3 | intact | True | identical | `abf299839f520dff` | abstained | refused before execution |
| imager_swapped | 498 | intact | True | identical | `f863454d7bb6bced` | executed | NR3: physically realised but not valid evidence; nothing committed |
| isaac_calibration_lapsed | 562 | intact | True | n/a (physics run) | `3305922c8bf7df49` | escalated | escalated: human decision required; nothing committed |
| isaac_identity_swap | 56 | intact | True | n/a (physics run) | `57705bd4e6e4b5f7` | escalated | escalated: human decision required; nothing committed |
| isaac_nominal | 498 | intact | True | n/a (physics run) | `c4b3059613d605cf` | executed | commit: result may update the culture belief |
| nominal | 498 | intact | True | identical | `3f92c88e4e25011f` | executed | commit: result may update the culture belief |
| rescue_unbound | 3 | intact | True | identical | `cfac4baec9177f6c` | abstained | refused before execution |
| tip_lost | 501 | intact | True | identical | `84b02ae69e46d4c7` | executed | commit: result may update the culture belief |
| tool_changer_slow | 266 | intact | True | identical | `bae2c3c0aae7a77b` | escalated | escalated: human decision required; nothing committed |
| uncalibrated_known | 504 | intact | True | identical | `8b8b4b0343ff2fea` | executed | commit: result may update the culture belief |

## 11. Reproduce

    env_cad/bin/python -m rsa.reproduce
    env_cad/bin/python -m rsa.reproduce --verify
