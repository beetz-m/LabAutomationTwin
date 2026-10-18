# LabAutomationTwin

Isaac Sim digital twin of the AICOR robot-scientist **Cell 01**: articulated, physics-simulated station twins,
their runtime controllers, an FR3 robot rig, and a working overlay of the Cell 01 scene.

The authoritative Cell 01 package lives in `~/ResearchSpace/projects/robot-scientist/cell-01/` and is
**never modified** from here. Cell 01 changes land as a non-destructive USD overlay (`scenes/cell01_twin.usda`);
merge-ready proposals for the Cell 01 package are in `proposals/cell01/`.

## Contents

| Path | What |
|---|---|
| `assets/h4/` | H4 Quarantine station (door, latch, presenting shuttle, key switch, button). See its README. |
| `assets/l09/` | L09 plate hotel (shuttle nest, gate, cassette, lift + fork handler). See its README. |
| `assets/l10/` | L10 CO2 incubator, STX44-class (L09 mechanism + insulated chamber, environment state). |
| `assets/common/` | Shared CAD → USD helpers, the SBS shuttle nest, and the parametric plate store (L09, L10). |
| `assets/gripper/`, `assets/labware/` | Plate gripper proxy for R01, SBS 96-well plate. |
| `assets/r02/` | R02: rail + UR5e (official ur_description) + automatic tool changer, tool magazine TCM01 with tools T01-T05. See its README. |
| `assets/l17/` | L17 bright-field imager: load gate, XY stage that doubles as the load drawer, focus drive, 2-objective turret, LED condenser, camera. See its README. |
| `assets/l12/` | L12 liquid handler: deck, plate nest, tip rack, reagent tubes, waste, X/Y/Z gantry with one ZEUS-class channel (tips = rigid bodies picked by a surface gripper). See its README. |
| `assets/r03/` | R03 clean sample AMR (planar base, sealed cabinet, lid, carrier nest) and the H2 deterministic dock. See its README. |
| `assets/l21/` | L21 QC / calibration bench: reference plate nest, QC nest, light-barrier tool datum, AprilTag target board. See its README. |
| `assets/hn/` | The passive R01/R02 handover nest on the bench (shared SBS nest interface, seat sensors). |
| `assets/materials/` | The MDL material library (`lab_materials.usda`: brushed stainless, epoxy floor, glass, ...) and procedural textures. |
| `assets/cell01_fitout/` | Cell 01 fit-out: enclosure E01 (profiles, glass, articulated doors D1-D3, AMR portal with light curtain), bench F01, rail cover, station supports, the L12 hood. See its README. |
| `assets/labequip/`, `assets/site/` | Lab equipment (storage, prep, safety, 36 assets) and the lab hall shell (site layout S1: storage room ST01, entrance, windows, lighting, AMR lane). |
| `twin/` | Runtime controllers: `h4_controller.py`, `l09_controller.py` (`PlateStoreController`), `l10_controller.py`. R01: `r01_rig.py` (FR3 + gripper, IK, pick/place), `r01_planner.py` (checked joint-space transits). R02: `r02_rig.py`, `r02_controller.py` (rail + tool-changer contracts), `kinematics.py` (URDF FK/IK). L17: `l17_controller.py`, `l17_optics.py` (image formation from the simulated state). L21: `l21_controller.py`, `l21_analysis.py` (grid and light-barrier analysis). L12: `l12_controller.py`, `l12_liquid.py` (tracked volumes, cLLD, pressure). R03/H2: `r03_controller.py`. `hn_monitor.py` (handover nest seat sensors). Evidence: `episode_records.py`. Site: `site_doors.py` (doors, interlock, light curtain). Video: `video.py`. Culture SDT: `culture/` (see its README). |
| `scripts/` | Isaac Sim tests (`test_*_physics.py`, `test_h4_robot.py`), the end-to-end episodes (`run_cell01_episode.py`), renders, FR3 import. |
| `tools/` | Layout and reach (`reachability_study.py`, `layout_p1.py`), overlay composer, clearance sweeps, `build_all.sh`. |
| `scenes/` | `layout_p1.json` (placements), the generated overlay `cell01_twin.usda`, the lab `lab_site.usda` / `lab_twin.usda` (`tools/compose_lab.py`), and the culture runs in `culture/`. |
| `proposals/cell01/` | Cell 01 fixes and the D017 decision text, ready to merge when the owner chooses. |
| `proposals/site/` | Site layout proposal S1 for the lab around Cell 01. |
| `okf/lab-automation-twin/` | AICOR OKF module: the lab's ontology on the AICOR hub + robot-scientist + VRB, with device-manual, safe-action and culture-experiment knowledge; SDT nodes as instances. See its README. |
| `test_reports/`, `renders/` | Evidence from the latest runs. |

## Setup

Two Python 3.12 virtual environments (not in git):
- `env_isaacsim/`: Isaac Sim 6.2.0.0 (pip) with torch 2.11 cu130.
- `env_cad/`: CadQuery 2.8, usd-core, opencv, xacro, matplotlib, pyyaml, pyflakes.

The Isaac Sim scripts set `OMNI_KIT_ACCEPT_EULA=YES`; the user accepted the NVIDIA Omniverse EULA on 2026-10-15.
Tested on an RTX 3070 (8 GB): use one path-traced render product at a time.

## Build and test

Generated files (USD layers, STEP, textures, the FR3 import, the overlay) are not committed. Regenerate them all:

```bash
tools/build_all.sh
```

Then:

```bash
export OMNI_KIT_ACCEPT_EULA=YES
env_isaacsim/bin/python scripts/test_h4_physics.py      # 14 station checks
env_isaacsim/bin/python scripts/test_l09_physics.py     # 11 checks
env_isaacsim/bin/python scripts/test_l10_physics.py     # 11 checks
env_isaacsim/bin/python scripts/test_h4_robot.py --scene cell01 [--place-mode compliant|drop]   # 16 FR3 trials
env_isaacsim/bin/python scripts/test_r02.py              # R02 rail, reach, tool changer, plate transfer (10)
env_isaacsim/bin/python scripts/test_l17_physics.py      # L17 mechanism + imaging (15)
env_isaacsim/bin/python scripts/test_l17_robot.py        # R02 loads L17, L17 images, R02 unloads (6)
env_isaacsim/bin/python scripts/test_l21.py              # L21 tool-frame check, imager validation, fault handling (10)
env_isaacsim/bin/python scripts/test_l12_physics.py      # L12 dosing, liquid model, faults (10)
env_isaacsim/bin/python scripts/test_l12_robot.py        # R02 serves L12, airspace interlock, dose (7)
env_isaacsim/bin/python scripts/test_r03.py              # R03 AMR navigation, H2 docking, cabinet, faults (9)
env_isaacsim/bin/python scripts/test_site_route.py       # lab: storage door, lane, portal light curtain, H2 dock (7)
env_isaacsim/bin/python scripts/run_cell01_episode.py   # end-to-end episodes, records in test_reports/episodes/
env_isaacsim/bin/python scripts/run_cell01_episode.py --scene lab --episodes full_cell --video renders/video/full_cell_lab
env_isaacsim/bin/python scripts/render_cell01.py [--quick] [--lab]
env_cad/bin/python scripts/run_culture_experiment.py --scenario nominal|underdose|contamination   # culture SDT, CPU
env_isaacsim/bin/python scripts/render_culture.py nominal --stills | --timelapse [--pt]
env_cad/bin/python tools/check_site.py                  # lab layout S1 checks
env_cad/bin/python tools/fitout_clearance.py            # R02 swept volume against the fit-out
```

Every test exits non-zero on failure and writes a JSON report to `test_reports/`.

## Cell 01 layout P1

Adopted by the user on 2026-10-15: R01 moves to (−1.55, 0.35) at the west end of the central bench, and H4, L09,
L10, the AMR carrier dock and the R01/R02 handover nest sit around it at 0.49–0.60 m. `tools/layout_p1.py`
computes the placements and checks footprints, door swings and presented trays against the walls, the bench, R01's
pedestal and the AMR lane, plus FR3 reach; `tools/compose_cell01_overlay.py` writes the overlay.
Plan view: `renders/cell01_layout_p1.png`.

## End-to-end episodes

`scripts/run_cell01_episode.py` runs Cell 01 workflows as CRAM designators with every station controller, R01, R02 and
R03 in the loop. Monitors read the simulated devices: barcode rays, seat sensors, slot rays, joint states, PhysX
contact reports, the L10 environment model, L17 images, L12 pressure traces, L21 reference measurements and the H2
dock sensors. The five episodes run in sequence in one simulation (2026-10-16):

| Episode | What happens | Records |
|---|---|---|
| `nominal` | L10 releases Plate_P17. R01 picks it, transits and places it on L09. L09 reads the barcode again and stores it in slot 3. | retrieve, transport, store: all eligible to commit |
| `identity_swap` | L10's inventory says slot 5 holds Plate_P18, but the plate there is Plate_P23. L10's reader catches it at release, and L10 presents the plate for removal. R01 carries it to H4, which quarantines and locks it and refuses an unauthorised release. | retrieve: blocked (`plate_identity`), routed to H4, quarantine request executed; transport, quarantine: eligible; escalations: Plate_P18 unaccounted for, quarantine review |
| `quarantine_release` | Continues the swap. A human review (simulated input, recorded as such) confirms Plate_P23 and authorises its release. The operator turns H4's key to RELEASE; the release is still refused without the token and accepted with it. H4 presents the plate. R01 returns it to L10, which re-reads the barcode and incubates it in slot 5. | retrieve from H4 (identity carried by the containment chain; H4 has no reader), transport, incubate (barcode re-read, seating, T / CO2 / RH and alarm monitors): all eligible; quarantine review resolved; Plate_P18 still unaccounted for |
| `imaging` | Plate_P17 (stored in L09 by `nominal`) goes L09 → R01 → handover nest → R02 with T01 → L17. L17 reads its barcode at load and images B02–B04 at 10x with autofocus. The plate then returns the same way and L09 stores it again. A well that fails `focus_quality` is kept as a blocked image, then refocused from scratch and reacquired. | retrieve, 4 transports, 3 L17 image records (Cell 01's own L17 builder; admitted), store: all eligible |
| `full_cell` | Start-of-day QC: L21 checks T01's TCP on the light barrier (as found 0.76 mm off, corrected), then validates L17 on the reference plate, which issues a calibration. R03 brings Plate_P30 in its closed cabinet, docks in H2 and opens the cabinet; R01 takes the plate to L10, which incubates it, and R03 leaves. L10 releases it for an intervention: R01 → handover nest → R02 → L12, which doses 10 µL into B05 after an airspace check. R02 takes it to L17, which images B05 and B06, and the plate returns to L10. | 3 QC (the as-found TCP check routes to `invalidate_dependent_measurements`), 2 AMR transports, retrieves, transports, L12 dose (Cell 01's L12 builder), 2 L17 images, 2 incubations: all others eligible |

**Scheduling finding from the twin.** In the first `quarantine_release` run the executive opened L10's gate for loading
before R01 had even fetched the plate, just after two earlier transfers. L10's chamber left its envelope, and L10
correctly refused the incubation, leaving the plate on the open tray. The executive now waits until L10's environment
is at least halfway from each bound back to its setpoint, and opens the gate only once the plate is in the gripper.
The environment numbers come from the illustrative model (D016); the scheduling logic is the point.

**Findings from the full-cell integration (2026-10-16).**
- **AMR carrier site:** R01's planner could not reach the first AMR carrier site, although the layout check passed
  it. The site moved toward R01.
- **AMR lid:** the AMR's sliding hood jammed on the carrier plate. It is now a fixed shroud with a flat lid.
- **L12 heights:** the liquid-level descent of L12 mixed world and station heights. It worked only with the station
  on the floor.
- **L12 airspace:** a robot hovering over L12 blocked its gantry. L12 now has a deck airspace interlock.
- **Plate placement:** a runtime pose write to a just-created physics view was dropped silently, so the AMR's plate
  is now authored before play.

**Records.** `twin/episode_records.py` turns the run log into records that follow Cell 01's
`neem_record_schema.yaml`:
- The critic vector comes from `monitor_templates.yaml`.
- Grounding and the H4 request come from Cell 01's `physical_workflow.py`, which is imported read-only.
- Every record is validated against the schemas and their invariants.
- `python -m twin.episode_records` rebuilds the records without Isaac Sim.

**Request parameters.** The protocol window (600 s) and the acceptance of ambient storage in L09 are labelled demo
request parameters, not biological values (D016). Contamination compatibility is recorded as an assumption, because
the twin has no contamination model.

**R01 motion.**
- Between stations, R01 moves in joint space along paths from `twin/r01_planner.py`. It uses the FR3 URDF
  kinematics and checks the plate, the gripper and the arm links against the station housings, stack lights,
  H4's open door, the bench and the walls.
- Approach configurations must have joint margins of at least 20° and a well-conditioned Jacobian:
  - The first run's planner chose configurations with σ_min 0.06–0.08.
  - The damped IK then left 1–2 mm errors that never settled.
  - The READY-like configurations reach 0.12–0.14.
- Approach, insertion and lift stay Cartesian (`twin/r01_rig.py`).
- No arm contact occurred in either transit.

## AICOR Lab 1 around Cell 01 (site layout proposal S1)

`scenes/lab_twin.usda` puts the fitted Cell 01 into a whole lab hall (19.2 × 11.2 m). The hall has:
- a storage room ST01 (cold storage, CO2 cabinet, shelving, LN2, and the S1 dispatch dock where R03 is loaded);
- an entrance and gowning area;
- an operator area;
- a culture prep area (BSCs, incubators, benches, sink, emergency shower);
- a wash / waste area.

The fit-out (`assets/cell01_fitout/`) adds the safety enclosure, with interlocked doors and an AMR portal with a
muted light curtain, plus the machine bench, station supports and the L12 hood. The site layout is a proposal; see
`proposals/site/README.md`. All lab and equipment assets are project-owned proxies.

**Checks:**
- `tools/check_site.py`: 45 items; rear corridor 1.65 m; AMR corridor margin 0.46 m.
- `tools/fitout_clearance.py`: R02's recorded joint traces from the episodes and robot tests, replayed against the
  fit-out colliders. The worst case is 27 mm, at the existing L21 side table; the L12 hood is at 51 mm.
- `scripts/test_site_route.py` (7/7): storage door; AMR lane; portal light curtain (a muted AMR passage, and a person
  proxy that latches a protective stop); door interlock; H2 dock; and a valid Cell 01 transport record.

**Lab-level findings:**
- **L12 hood:** a full hood around L12 cut 50 mm into R02's swept volume. It is now open on the robot side.
- **R03 joint limits:** in the hall, R03 hit Cell 01's ±3.5 m planar joint limit 0.48 m south of the lane. The lab
  scene widens the limits.
- **R03 leg alignment:** R03 now turns in place onto each leg before driving it.

**Renders and video:**
- `renders/lab/` holds 12 path-traced lab views (`render_cell01.py --lab`).
- `run_cell01_episode.py --scene lab --video DIR` records the full-cell episode in the lab as an MP4 (`twin/video.py`).
  The episode starts with R03 at the storage dock.

## Culture SDT

`twin/culture/` simulates the biology of Plate_P17 (Cell 01's illustrative surrogate, D016) and keeps it apart from
the SDT's belief:
- The SDT is a particle filter that sees only robot records and L17 4× images.
- Doses commit through Cell 01's own culture ledger.
- Contamination and unverified doses withhold claims.

The results are written as USD layers (belief, truth, appearance, SDT visualisation) and rendered in the lab. See
`twin/culture/README.md`.

## Ontology: the AICOR OKF module `okf/lab-automation-twin`

The lab's ontology is an **AICOR OKF module**. It extends:
- the frozen AICOR hub (`http://aicor.knowledge/l2-ontology.owl#`);
- the robot-scientist vertical;
- VRB's lab-automation-device module;
- normative-admissibility.

All four are referenced read-only in ResearchSpace. It has 359 concepts, each axiomatised in description logic
(`okf/lab-automation-twin/docs/axioms.pdf`), with a partonomy, and four knowledge modules:
- **device manuals:** Cell 01's ten component contracts;
- **safe action:** 19 rules and 2 norms, with enforcement and verified refusals;
- **culture experiments:** the challenge-rescue study and its three runs;
- **experiment to motion:** from a required information gain, L3 axioms derive the experiment and every robot motion
  and device command that realises it. The derivation is clingo; z3 validates each plan; the twin executes it:
  `scripts/run_cell01_episode.py --plan okf/lab-automation-twin/L3-logical-axiomatization/derivation/out/plan_g050.json`.

Every SDT node is a `LabSDTNode` representing a typed referent (`scenes/sdt_ontology.usda`, with inferred types).
`make -C okf/lab-automation-twin check` runs:
- HermiT through AICOR's own pipeline;
- the imports guard;
- the executable competency questions;
- Konclude over TBox + ABoxes, with negative controls.

Divergences and upstream findings are in its `DEFERRED-REGISTER.md`. See `okf/lab-automation-twin/README.md`.

## Renders

All renders are path traced. `renders/cell01/` holds the cell: `scripts/render_cell01.py` shows every station
presenting a plate, R01 over H4, R02 reaching over its tool magazine, L12 with tips and reagents, L21 with its
reference plate, L17's presented stage, the handover nest and R03 docked with its cabinet open (`cell01_east`,
`cell01_l12`, `cell01_l21`, `cell01_l17`, `cell01_amr_docked`, ...). `--rt --quick` gives a real-time preview that can
share the GPU with a running simulation (path tracing next to two simulations crashed the 8 GB GPU).

`renders/episodes/` holds stills of the simulated state at the key moments of the episodes, from
`scripts/run_cell01_episode.py --frames renders/episodes`:

| Frame | Moment |
|---|---|
| `nominal_2_carrying_to_L09` | R01 above L09 with Plate_P17 |
| `identity_swap_1_identity_fault_at_L10` | The swapped plate presented for removal after L10's barcode mismatch |
| `identity_swap_2_carrying_to_H4` | R01 above H4's open door with the plate |
| `identity_swap_3_quarantined_locked` | The plate contained in H4, door closed and locked |
| `quarantine_release_1_authorised_release` | H4 presents the plate after the key and token |
| `quarantine_release_2_return_to_L10` | R01 above L10's tray with the released plate |
| `quarantine_release_3_incubated` | The cell after the plate is back in L10 |

## Design basis and limits

- All station designs are project-owned parametric designs, not manufacturer models. Manufacturer CAD (LiCONiC,
  Zimmer) has not been acquired; the dimensions are parameters to replace when it is.
- L10's environment model parameters are illustrative engineering assumptions, not validated incubator data
  (Cell 01 rule D016: no invented biological parameters).
- The robot campaigns are functional checks (16 trials), not reliability estimates.
- The episodes are single functional runs. The transit planner checks simplified boxes and link spheres; it is not a
  collision-aware motion planner (cuMotion would be the production choice).
