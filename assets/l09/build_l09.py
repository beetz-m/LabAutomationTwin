"""Build the L09 Automated Plate Hotel asset: parametric CAD -> STEP + layered, articulated OpenUSD.

Run with the CAD environment:  env_cad/bin/python assets/l09/build_l09.py

Project-owned, LPE220-class automated plate hotel (Cell 01 baseline: LiCONiC LiCotel LPE220 family; the LiCONiC
CAD has to be requested, so this is a dimensioned design, not a product model). The mechanism (shuttle nest,
gate, lift + fork handler, cassette, sensors, service door) is the shared plate-store builder
assets/common/plate_store.py, whose defaults are this device; see assets/l09/README.md.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from common.plate_store import StoreDesign  # noqa: E402

DESIGN = StoreDesign(here=HERE)   # L09 = the plate-store defaults

if __name__ == "__main__":
    DESIGN.build()
