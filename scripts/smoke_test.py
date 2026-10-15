"""Headless Isaac Sim smoke test.

1. Start Isaac Sim headless (EULA accepted by the user on 2026-10-15).
2. Open the Cell 01 BioPhysical USD read-only and list the station prims.
3. Play the timeline for a few hundred frames to check physics runs.

Usage: python scripts/smoke_test.py [path/to/stage.usda]
"""

import os
import sys
import time

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")

DEFAULT_STAGE = os.path.expanduser(
    "~/ResearchSpace/projects/robot-scientist/cell-01/AICOR_Cell01_Codex_Handoff/"
    "simulation/isaac_sim/biophysical_v2/AICOR_BioPhysical_Cell01_v2.usda"
)
STATIONS = ("L09", "L10", "L12", "L17", "L21", "H4", "R01", "R02", "R03")

t0 = time.time()
from isaacsim import SimulationApp  # noqa: E402  (must come before omni imports)

app = SimulationApp({"headless": True})
print(f"[smoke] SimulationApp up in {time.time() - t0:.1f}s")

import omni.timeline  # noqa: E402
import omni.usd  # noqa: E402
from pxr import UsdPhysics  # noqa: E402

stage_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_STAGE
ctx = omni.usd.get_context()
ok = ctx.open_stage(stage_path)
for _ in range(20):
    app.update()
stage = ctx.get_stage()
if not ok or stage is None:
    print(f"[smoke] FAIL could not open {stage_path}")
    app.close()
    sys.exit(1)

prims = list(stage.Traverse())
colliders = [p for p in prims if p.HasAPI(UsdPhysics.CollisionAPI)]
rigid = [p for p in prims if p.HasAPI(UsdPhysics.RigidBodyAPI)]
joints = [p for p in prims if p.IsA(UsdPhysics.Joint)]
scenes = [p for p in prims if p.IsA(UsdPhysics.Scene)]
print(f"[smoke] stage: {stage_path}")
print(f"[smoke] prims={len(prims)} colliders={len(colliders)} rigid={len(rigid)} "
      f"joints={len(joints)} physicsScenes={len(scenes)}")
for p in prims:
    name = p.GetName()
    if any(name.startswith(s + "_") for s in STATIONS):
        print(f"[smoke]   station {p.GetPath()}")

timeline = omni.timeline.get_timeline_interface()
timeline.play()
t1 = time.time()
frames = 300
for _ in range(frames):
    app.update()
dt = time.time() - t1
timeline.stop()
print(f"[smoke] stepped {frames} frames in {dt:.1f}s ({frames / dt:.0f} fps)")
print("[smoke] PASS")
app.close()
