"""Expand the official franka_description FR3 xacro (arm only, no Franka Hand) into a plain URDF.

Source: Cell 01 kit, franka_description @ 7aeeddc (frankarobotics/franka_description, Apache-2.0),
acquired 2026-09-09 (see the kit's 01_acquisition/OPEN_SOURCE_ACQUISITION.json). The source tree
is read in place and not modified; package:// and $(find ...) are resolved to its absolute path.

Run with the CAD venv (has xacro):  env_cad/bin/python tools/make_fr3_urdf.py
Output: assets/fr3/fr3_arm.urdf
"""

import os

import xacro
import xacro.substitution_args as sa

FR_DESC = os.path.expanduser(
    "~/ResearchSpace/projects/robot-scientist/cell-01/AICOR_Cell01_Codex_Handoff/simulation/isaac_sim/"
    "manufacturer_grounded/02_source_assets/open_source/franka_description")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fr3", "fr3_arm.urdf")

_orig = sa._eval_find


def _eval_find(pkg):
    return FR_DESC if pkg == "franka_description" else _orig(pkg)


sa._eval_find = _eval_find
doc = xacro.process_file(os.path.join(FR_DESC, "robots/fr3/fr3.urdf.xacro"),
                         mappings={"robot_type": "fr3", "hand": "false", "with_sc": "false"})
xml = doc.toprettyxml(indent="  ").replace("package://franka_description", FR_DESC)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    f.write(xml)
print("wrote", os.path.abspath(OUT))
