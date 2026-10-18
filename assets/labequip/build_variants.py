"""Numbered variants of library assets for the lab layout (tools/compose_lab.py).

shelving_rack_R1..R3: storage-room racks ST01-R1..R3, each with its own location codes (ST01-R<n>-S<k>) and its own
seeded consumable load, so every storage location in the twin is unique and addressable.
Run after assets/labequip/build_storage.py: env_cad/bin/python assets/labequip/build_variants.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_storage as bs  # noqa: E402

VARIANTS = {f"shelving_rack_R{n}": (bs.build_shelving_rack, {"seed": 10 + n, "bays": 1, "rack": n}) for n in (1, 2, 3)}


def main():
    for name, (fn, params) in VARIANTS.items():
        ntri, lo, hi, nf, nl = bs.write_asset(name, fn, params)
        print(f"{name:18s} tris {ntri:7d}  frames {nf}  locations {nl}")


if __name__ == "__main__":
    main()
