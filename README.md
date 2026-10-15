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
| `twin/` | Runtime controllers: `h4_controller.py`, `l09_controller.py` (`PlateStoreController`), `l10_controller.py`. |
| `scripts/` | Isaac Sim tests (`test_*_physics.py`, `test_h4_robot.py`), renders, FR3 import. |
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
env_isaacsim/bin/python scripts/render_cell01.py [--quick]
```

Every test exits non-zero on failure and writes a JSON report to `test_reports/`.

## Cell 01 layout P1

Adopted by the user on 2026-10-15: R01 moves to (−1.55, 0.35) at the west end of the central bench, and H4, L09,
L10, the AMR carrier dock and the R01/R02 handover nest sit around it at 0.49–0.60 m. `tools/layout_p1.py`
computes the placements and checks footprints, door swings and presented trays against the walls, the bench, R01's
pedestal and the AMR lane, plus FR3 reach; `tools/compose_cell01_overlay.py` writes the overlay.
Plan view: `renders/cell01_layout_p1.png`.

## Design basis and limits

- All station designs are project-owned parametric designs, not manufacturer models. Manufacturer CAD (LiCONiC,
  Zimmer) has not been acquired; the dimensions are parameters to replace when it is.
- L10's environment model parameters are illustrative engineering assumptions, not validated incubator data
  (Cell 01 rule D016: no invented biological parameters).
- The robot campaigns are functional checks (16 trials), not reliability estimates.
