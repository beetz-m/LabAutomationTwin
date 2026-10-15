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
| `twin/` | Runtime controllers: `h4_controller.py`, `l09_controller.py` (`PlateStoreController`), `l10_controller.py`. R01: `r01_rig.py` (FR3 + gripper, IK, pick/place), `r01_planner.py` (checked joint-space transits). R02: `r02_rig.py`, `r02_controller.py` (rail + tool-changer contracts), `kinematics.py` (URDF FK/IK). Evidence: `episode_records.py`. |
| `scripts/` | Isaac Sim tests (`test_*_physics.py`, `test_h4_robot.py`), the end-to-end episodes (`run_cell01_episode.py`), renders, FR3 import. |
| `tools/` | Layout and reach (`reachability_study.py`, `layout_p1.py`), overlay composer, clearance sweeps, `build_all.sh`. |
| `scenes/` | `layout_p1.json` (placements) and the generated overlay `cell01_twin.usda`. |
| `proposals/cell01/` | Cell 01 fixes and the D017 decision text, ready to merge when the owner chooses. |
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
env_isaacsim/bin/python scripts/run_cell01_episode.py   # end-to-end episodes, records in test_reports/episodes/
env_isaacsim/bin/python scripts/render_cell01.py [--quick]
```

Every test exits non-zero on failure and writes a JSON report to `test_reports/`.

## Cell 01 layout P1

Adopted by the user on 2026-10-15: R01 moves to (−1.55, 0.35) at the west end of the central bench, and H4, L09,
L10, the AMR carrier dock and the R01/R02 handover nest sit around it at 0.49–0.60 m. `tools/layout_p1.py`
computes the placements and checks footprints, door swings and presented trays against the walls, the bench, R01's
pedestal and the AMR lane, plus FR3 reach; `tools/compose_cell01_overlay.py` writes the overlay.
Plan view: `renders/cell01_layout_p1.png`.

## End-to-end episodes

`scripts/run_cell01_episode.py` runs Cell 01 workflows as CRAM designators with every station controller and R01
in the loop. Monitors read the simulated devices: barcode rays, seat sensors, slot rays, joint states, PhysX contact
reports and the L10 environment model. The two episodes, verified 2026-10-15:

| Episode | What happens | Records |
|---|---|---|
| `nominal` | L10 releases Plate_P17. R01 picks it, transits and places it on L09. L09 reads the barcode again and stores it in slot 3. | retrieve, transport, store: all eligible to commit |
| `identity_swap` | L10's inventory says slot 5 holds Plate_P18, but the plate there is Plate_P23. L10's reader catches it at release, and L10 presents the plate for removal. R01 carries it to H4, which quarantines and locks it and refuses an unauthorised release. | retrieve: blocked (`plate_identity`), routed to H4, quarantine request executed; transport, quarantine: eligible; escalations: Plate_P18 unaccounted for, quarantine review |

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

## Design basis and limits

- All station designs are project-owned parametric designs, not manufacturer models. Manufacturer CAD (LiCONiC,
  Zimmer) has not been acquired; the dimensions are parameters to replace when it is.
- L10's environment model parameters are illustrative engineering assumptions, not validated incubator data
  (Cell 01 rule D016: no invented biological parameters).
- The robot campaigns are functional checks (16 trials), not reliability estimates.
- The episodes are single functional runs. The transit planner checks simplified boxes and link spheres; it is not a
  collision-aware motion planner (cuMotion would be the production choice).
