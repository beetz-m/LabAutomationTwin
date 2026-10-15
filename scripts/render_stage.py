"""Render PNGs of a USD stage headlessly with Isaac Sim (RTX).

Renders the stage's own OverviewCamera plus an extra camera aimed at a target
point (default: H4's location). The stage is opened read-only; nothing is saved.

Usage: python scripts/render_stage.py [stage.usda] [out_dir]
"""

import os
import sys

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")

DEFAULT_STAGE = os.path.expanduser(
    "~/ResearchSpace/projects/robot-scientist/cell-01/AICOR_Cell01_Codex_Handoff/"
    "simulation/isaac_sim/biophysical_v2/AICOR_BioPhysical_Cell01_v2.usda"
)
RES = (1600, 1000)
WARMUP_STEPS = 32  # RTX path needs a few frames to converge

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True, "renderer": "RaytracedLighting", "width": RES[0], "height": RES[1]})

import numpy as np  # noqa: E402
import omni.replicator.core as rep  # noqa: E402
import omni.usd  # noqa: E402
from PIL import Image  # noqa: E402
from pxr import Gf, Usd, UsdGeom  # noqa: E402

stage_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_STAGE
out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), "..", "renders")
os.makedirs(out_dir, exist_ok=True)

ctx = omni.usd.get_context()
ctx.open_stage(stage_path)
for _ in range(20):
    app.update()
stage = ctx.get_stage()

h4 = stage.GetPrimAtPath("/World/Cell01/Stations/H4_Quarantine")
target = Gf.Vec3d(0, 0, 0)
if h4:
    target = UsdGeom.XformCache(Usd.TimeCode.Default()).GetLocalToWorldTransform(h4).ExtractTranslation()
print(f"[render] H4 world position: {tuple(round(v, 3) for v in target)}")

views = {}
if stage.GetPrimAtPath("/World/Sensors/OverviewCamera"):
    views["cell01_overview"] = "/World/Sensors/OverviewCamera"
views["h4_location"] = rep.create.camera(
    position=(target[0] - 2.2, target[1] - 2.6, target[2] + 2.0),
    look_at=(target[0], target[1], target[2] + 0.4),
    focal_length=24,
)

annotators = {}
for name, cam in views.items():
    rp = rep.create.render_product(cam, RES)
    ann = rep.AnnotatorRegistry.get_annotator("rgb")
    ann.attach(rp)
    annotators[name] = ann

for _ in range(WARMUP_STEPS):
    rep.orchestrator.step(rt_subframes=4)

for name, ann in annotators.items():
    rgba = np.asarray(ann.get_data())
    path = os.path.abspath(os.path.join(out_dir, f"{name}.png"))
    Image.fromarray(rgba[..., :3].astype(np.uint8)).save(path)
    print(f"[render] wrote {path}")

rep.orchestrator.wait_until_complete()
app.close()
