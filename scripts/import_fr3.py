"""Import the FR3 arm (assets/fr3/fr3_arm.urdf, from tools/make_fr3_urdf.py) to USD with Isaac Sim's URDFImporter.

Fixed base, position-driven joints, URDF collision meshes as convex hulls. Output: assets/fr3/usd/...
Usage: env_isaacsim/bin/python scripts/import_fr3.py
"""

import os
import sys

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
URDF = os.path.join(ROOT, "assets/fr3/fr3_arm.urdf")
OUT = os.path.join(ROOT, "assets/fr3/usd")

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True})

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402

for ext in ("isaacsim.asset.importer.urdf", "isaacsim.robot.schema"):
    app_utils.enable_extension(ext)
app.update()

from isaacsim.asset.importer.urdf import URDFImporter, URDFImporterConfig  # noqa: E402

config = URDFImporterConfig(
    urdf_path=URDF,
    usd_path=OUT,
    merge_fixed_joints=True,
    fix_base=True,
    collision_from_visuals=False,
    collision_type="Convex Hull",
    joint_drive_type="force",
    joint_target_type="position",
    override_joint_stiffness=2000.0,
    override_joint_damping=150.0,
    robot_type="Manipulator",
)
out = URDFImporter(config).import_urdf()
print("[import_fr3] wrote", out)
sys.stdout.flush()
os._exit(0 if out else 1)
