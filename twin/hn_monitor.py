"""Seat sensing for the passive R01/R02 handover nest (assets/hn/hn.usda): 4 flush seat sensors, PhysX raycasts.

The nest has no actuators and no barcode reader: identity across the handover is carried by custody (the robot that
placed the plate) and re-read by the next station with a reader.
"""

from __future__ import annotations

import carb
import numpy as np
from omni.physx import get_physx_scene_query_interface
from pxr import Gf, Usd, UsdGeom

SEAT_GAP_OK = 0.0004


class HandoverNest:
    def __init__(self, stage, root):
        self.stage, self.root = stage, root
        xc = UsdGeom.XformCache(Usd.TimeCode.Default())
        tf = xc.GetLocalToWorldTransform(stage.GetPrimAtPath(root))
        self.up = np.array(tf.TransformDir(Gf.Vec3d(0, 0, 1)))
        self.sensors = [np.array(xc.GetLocalToWorldTransform(stage.GetPrimAtPath(f"{root}/seat_sensor_{i}"))
                                 .ExtractTranslation()) for i in range(4)]
        f = xc.GetLocalToWorldTransform(stage.GetPrimAtPath(f"{root}/handover_frame"))
        self.frame = np.array(f.ExtractTranslation())
        self.sq = get_physx_scene_query_interface()
        self.update()

    def _gap(self, origin):
        hits = []

        def report(h):
            if not h.collision.startswith(self.root + "/"):
                hits.append(h.distance)
            return True

        self.sq.raycast_all(carb.Float3(*map(float, origin)), carb.Float3(*map(float, self.up)), 0.015, report)
        return min(hits) - 0.001 if hits else None

    def update(self, dt=None):
        self.gaps = [self._gap(s) for s in self.sensors]
        self.plate_on_nest = any(g is not None for g in self.gaps)
        self.seated = all(g is not None and g < SEAT_GAP_OK for g in self.gaps)

    def gaps_mm(self):
        return [None if g is None else round(g * 1e3, 3) for g in self.gaps]
