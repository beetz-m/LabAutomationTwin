"""Path-traced stills from a running twin (Isaac Sim 6.2, SimulationApp created with renderer="PathTracing").

One camera and one render product, moved between views: several path-traced render products next to a running
simulation exhausted the 8 GB GPU (ERROR_DEVICE_LOST, scripts/render_cell01.py). Capturing does not advance physics
(delta_time 0), so a still shows the simulated state at that instant. Render-only additions (a ceiling panel light)
go to the session layer and are never saved.
"""

from __future__ import annotations

import os

import numpy as np


class StillCamera:
    def __init__(self, stage, res=(1920, 1200), spp=16, subframes=32):
        import carb
        import omni.replicator.core as rep
        from pxr import Gf, UsdGeom, UsdLux
        s = carb.settings.get_settings()
        s.set("/rtx/rendermode", "PathTracing")
        s.set("/rtx/pathtracing/spp", spp)
        s.set("/rtx/pathtracing/totalSpp", spp * subframes)
        s.set("/rtx/pathtracing/maxBounces", 8)
        s.set("/rtx/pathtracing/optixDenoiser/enabled", True)
        self.rep, self.res, self.subframes = rep, res, subframes
        edit = stage.GetEditTarget()
        stage.SetEditTarget(stage.GetSessionLayer())
        key = UsdLux.RectLight.Define(stage, "/World/RenderOnly/CeilingPanel")
        key.CreateWidthAttr(2.5)
        key.CreateHeightAttr(1.2)
        key.CreateIntensityAttr(4000)
        key.AddTranslateOp().Set(Gf.Vec3d(-1.0, 0.3, 2.45))
        cam = UsdGeom.Camera.Define(stage, "/World/RenderOnly/StillCam")
        cam.CreateHorizontalApertureAttr(36.0)
        cam.CreateVerticalApertureAttr(36.0 * res[1] / res[0])
        cam.CreateClippingRangeAttr(Gf.Vec2f(0.01, 100))
        self.cam, self.op = cam, UsdGeom.Xformable(cam.GetPrim()).AddTransformOp()
        stage.SetEditTarget(edit)
        self.rp = rep.create.render_product(str(cam.GetPath()), res)
        self.rgb = rep.AnnotatorRegistry.get_annotator("rgb")
        self.rgb.attach(self.rp)

    def capture(self, path, eye, target, focal=20.0):
        from PIL import Image
        from pxr import Gf
        self.op.Set(Gf.Matrix4d().SetLookAt(Gf.Vec3d(*eye), Gf.Vec3d(*target), Gf.Vec3d(0, 0, 1)).GetInverse())
        self.cam.GetFocalLengthAttr().Set(float(focal))
        self.rep.orchestrator.step(rt_subframes=self.subframes, delta_time=0.0)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        Image.fromarray(np.asarray(self.rgb.get_data())[..., :3].astype(np.uint8)).save(path)
        return path
