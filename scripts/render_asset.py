"""Quick look at any station asset: auto-framed RTX stills from a few angles (rest pose, no physics).

Usage: python scripts/render_asset.py <asset.usda> <out_prefix> [--hide <prim-subpath> ...] [--quick]
--hide makes prims invisible (e.g. Body/Visual/Housing) for cutaway views of internals.
"""

import math
import os
import sys

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
args = [a for a in sys.argv[1:]]
QUICK = "--quick" in args
hide = [args[i + 1] for i, a in enumerate(args) if a == "--hide"]
pos = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] != "--hide")]
ASSET, OUT = os.path.abspath(pos[0]), os.path.abspath(pos[1])
RES = (960, 640) if QUICK else (1600, 1066)

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True, "renderer": "RaytracedLighting", "width": RES[0], "height": RES[1]})

import numpy as np  # noqa: E402
import omni.replicator.core as rep  # noqa: E402
import omni.usd  # noqa: E402
from PIL import Image  # noqa: E402
from pxr import Gf, UsdGeom, UsdLux  # noqa: E402

omni.usd.get_context().new_stage()
app.update()
stage = omni.usd.get_context().get_stage()
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)
asset = UsdGeom.Xform.Define(stage, "/World/Asset")
asset.GetPrim().GetReferences().AddReference(ASSET)
floor = UsdGeom.Cube.Define(stage, "/World/Floor")
floor.CreateSizeAttr(1.0)
floor.AddTranslateOp().Set(Gf.Vec3d(0, 0, -0.005))
floor.AddScaleOp().Set(Gf.Vec3f(6, 6, 0.01))
floor.CreateDisplayColorAttr([Gf.Vec3f(0.35, 0.36, 0.37)])
for sub in hide:
    p = stage.GetPrimAtPath(f"/World/Asset/{sub}")
    print(f"[render_asset] hide {sub}: {'ok' if p else 'NOT FOUND'}")
    # group prims may be typeless (implicitly created): hide the imageable prims directly below them
    targets = [p] if p and p.IsA(UsdGeom.Imageable) else ([c for c in p.GetChildren()] if p else [])
    for t in targets:
        if t.IsA(UsdGeom.Imageable):
            UsdGeom.Imageable(t).MakeInvisible()
dome = UsdLux.DomeLight.Define(stage, "/World/Dome")
dome.CreateIntensityAttr(900)
key = UsdLux.DistantLight.Define(stage, "/World/Key")
key.CreateIntensityAttr(2500)
key.AddRotateXYZOp().Set(Gf.Vec3f(45, 0, 35))
for _ in range(10):
    app.update()

bb = UsdGeom.BBoxCache(0, ["default", "render"]).ComputeWorldBound(asset.GetPrim()).ComputeAlignedRange()
c = (np.array(bb.GetMin()) + np.array(bb.GetMax())) / 2
r = float(np.linalg.norm(np.array(bb.GetMax()) - np.array(bb.GetMin()))) / 2
cam = UsdGeom.Camera.Define(stage, "/World/Cam")
cam.CreateFocalLengthAttr(35.0)
cam.CreateHorizontalApertureAttr(36.0)
cam.CreateVerticalApertureAttr(36.0 * RES[1] / RES[0])
cam.CreateClippingRangeAttr(Gf.Vec2f(0.01, 100))
rp = rep.create.render_product(str(cam.GetPath()), RES)
rgb = rep.AnnotatorRegistry.get_annotator("rgb")
rgb.attach(rp)
dist = r / math.tan(math.radians(25)) * 1.05
for name, az, el in (("front_left", -125, 25), ("front_right", -55, 20)):
    eye = c + dist * np.array([math.cos(math.radians(el)) * math.cos(math.radians(az)),
                               math.cos(math.radians(el)) * math.sin(math.radians(az)), math.sin(math.radians(el))])
    m = Gf.Matrix4d().SetLookAt(Gf.Vec3d(*eye), Gf.Vec3d(*c), Gf.Vec3d(0, 0, 1)).GetInverse()
    xf = UsdGeom.Xformable(cam.GetPrim())
    xf.ClearXformOpOrder()
    xf.AddTransformOp().Set(m)
    rep.orchestrator.step(rt_subframes=8 if QUICK else 24)
    path = f"{OUT}_{name}.png"
    Image.fromarray(np.asarray(rgb.get_data())[..., :3].astype(np.uint8)).save(path)
    print("[render_asset]", path)
rep.orchestrator.wait_until_complete()
sys.stdout.flush()
os._exit(0)
