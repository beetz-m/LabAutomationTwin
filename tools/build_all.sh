#!/usr/bin/env bash
# Regenerate every generated asset (USD layers, STEP, textures, FR3 and R02 imports, Cell 01 overlay).
set -euo pipefail
cd "$(dirname "$0")/.."
CAD=env_cad/bin/python
ISAAC=env_isaacsim/bin/python
$CAD assets/materials/build_materials.py  # shared lab material library + textures (fit-out, site, equipment)
$CAD assets/h4/build_h4.py                # H4 + labware/plate_sbs96.usda
$CAD assets/gripper/build_plate_gripper.py
$CAD assets/l09/build_l09.py
$CAD assets/l10/build_l10.py
$CAD assets/hn/build_hn.py                 # R01/R02 handover nest (passive SBS nest)
$CAD assets/l12/build_l12.py               # L12 liquid handler + tip
$CAD assets/r03/build_r03.py               # R03 AMR + H2 dock
$CAD assets/l21/build_l21.py               # L21 QC bench (reference + QC nests, light-barrier tool datum)
$CAD assets/l17/build_l17.py               # L17 bright-field imager (load stage, focus, turret, camera)
$CAD tools/make_fr3_urdf.py               # reads the Cell 01 kit's franka_description in place
OMNI_KIT_ACCEPT_EULA=YES $ISAAC scripts/import_fr3.py
$CAD tools/make_r02_urdf.py               # R02 = rail + UR5e (Cell 01 kit's ur_description, read in place) + coupler
OMNI_KIT_ACCEPT_EULA=YES $ISAAC scripts/import_r02.py
$CAD assets/r02/build_tooling.py          # tool magazine TCM01 + tools T01-T05
$CAD tools/layout_p1.py                  # layout P1 placements + checks -> scenes/layout_p1.json
$CAD assets/cell01_fitout/build_fitout.py # enclosure E01, bench F01, rail cover, supports, L12 hood (reads layout P1)
$CAD tools/compose_cell01_overlay.py      # scenes/cell01_twin.usda (Cell 01 is referenced, never modified)
$CAD assets/site/build_site.py            # AICOR Lab 1 shell (site layout proposal S1)
$CAD assets/labequip/build_storage.py     # storage room + building-service equipment
$CAD assets/labequip/build_prep.py        # culture prep, wash/waste, operator equipment
$CAD assets/labequip/build_variants.py    # numbered shelving racks R1-R3
$CAD tools/compose_lab.py                 # scenes/lab_twin.usda (Cell 01 overlay + lab) + scenes/site_layout_s1.json
