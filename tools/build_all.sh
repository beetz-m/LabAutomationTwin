#!/usr/bin/env bash
# Regenerate every generated asset (USD layers, STEP, textures, FR3 import, Cell 01 overlay).
set -euo pipefail
cd "$(dirname "$0")/.."
CAD=env_cad/bin/python
ISAAC=env_isaacsim/bin/python
$CAD assets/h4/build_h4.py                # H4 + labware/plate_sbs96.usda
$CAD assets/gripper/build_plate_gripper.py
$CAD assets/l09/build_l09.py
$CAD assets/l10/build_l10.py
$CAD tools/make_fr3_urdf.py               # reads the Cell 01 kit's franka_description in place
OMNI_KIT_ACCEPT_EULA=YES $ISAAC scripts/import_fr3.py
$CAD tools/compose_cell01_overlay.py      # scenes/cell01_h4.usda (Cell 01 is referenced, never modified)
