"""Runtime controller for the L12 Automated Liquid-Handling Station twin (sdt/components/L12_LiquidHandler.yaml).

Asset: assets/l12/l12.usda (deck, plate nest, tip rack, reagent block, waste, X/Y/Z gantry with one channel).
Runtime additions (before play): author_l12() adds the collider-free TipMount body and the tip surface gripper on
the channel (the R02 coupler pattern: runtime-created joints are ignored in Isaac Sim 6.2, a surface gripper
attachment works); add_tips() loads tips into the rack, add_reagent_tube() places reagent tubes. Both are
consumables with identities (labware:tipId, labware:barcode + reagent:id / reagent:lot / reagent:volume_uL).

  dose_well(plate_id, well_id, reagent_pos, reagent_id, reagent_lot, volume_uL, dispense_height_mm,
            dispense_rate_uL_s)   the contract's action, as one sequence:
      verify plate (barcode at the nest) and seating -> verify reagent (barcode reader of that position) ->
      pick_tip (gripper attach, tip-presence ray) -> detect_liquid_surface (cLLD on the REAL tip end) ->
      aspirate with liquid following (pressure trace) -> dispense at the well (pressure trace, well position
      check from the real tip pose) -> eject_tip into the waste (tip seen leaving)
  Aborts BEFORE aspiration on a wrong reagent, a missing tip, an unseated / unverified plate or a liquid level
  that disagrees with the inventory; a clog or air in the trace makes the dose uncertain (not committed).
  Every dose produces a record with the eight monitors of the Cell 01 `dose` designator.

The controller knows commanded joint targets, encoders, the barcode/seat/tip-presence rays and the pressure trace.
The liquid model (twin/l12_liquid.py) is the world: it uses the real tip pose. Executed volume is reported as the
volume inferred from the pressure trace, never the commanded one ("commanded volume equals delivered volume" is in
the contract's must_not_assume).
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field

import carb
import numpy as np
from isaacsim.core.experimental.prims import Articulation, RigidPrim
from omni.physx import get_physx_scene_query_interface
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

from . import l12_liquid as lq
from .l17_optics import parse_well, well_center

MM = 0.001
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TIP_USD = os.path.join(ROOT_DIR, "assets/l12/tip.usda")
JOINTS = {"x": "GantryXSlide", "y": "GantryYSlide", "z": "ChannelZSlide"}
SPEED = {"x": 0.25, "y": 0.20, "z": 0.08}
TOL = {"x": 0.0002, "y": 0.0002, "z": 0.00005}
MOVE_TIMEOUT_S = 6.0
SEAT_GAP_OK = 0.0004
TIP_GAP = 1.0                 # mm: the cone end stops this far above the tip collar before the gripper closes
TIP_LEN = 50.0                # mm, collar top to tip end
LLD_SPEED = 0.002             # m/s
SUBMERGE_MM = 2.0
LEVEL_TOL_MM = 1.5
LIGHT_ON = 3000.0
WELL_R = 3.45
# deck airspace monitor (area sensor / light curtain): horizontal beams along X across the deck above the gantry's
# working height; L12's own parts are ignored, anything else (a robot tool, a hand) blocks a beam. Added after the
# first R02 test drove the gantry into R02's gripper hovering over the plate nest (2026-10-16).
AIRSPACE = {"x": (-470.0, 470.0), "y": (-110.0, 0.0, 90.0, 180.0), "z": (260.0, 330.0)}


@dataclass
class Result:
    accepted: bool
    reason: str = ""


# ------------------------------------------------------------------ authoring (before play)
def author_l12(stage, root):
    """TipMount (collider-free body fixed to the channel at the cone end) + a surface gripper looking down."""
    from usd.schema.isaac import robot_schema
    from pxr import PhysxSchema
    ch = f"{root}/GantryX/GantryY/ChannelZ"
    tm = UsdGeom.Xform.Define(stage, f"{root}/TipMount")
    UsdPhysics.RigidBodyAPI.Apply(tm.GetPrim())
    m = UsdPhysics.MassAPI.Apply(tm.GetPrim())
    m.CreateMassAttr(0.02)
    m.CreateDiagonalInertiaAttr(Gf.Vec3f(1e-6, 1e-6, 1e-6))
    PhysxSchema.PhysxRigidBodyAPI.Apply(tm.GetPrim()).CreateDisableGravityAttr(True)
    xc = UsdGeom.XformCache()
    tm.AddTransformOp().Set(xc.GetLocalToWorldTransform(stage.GetPrimAtPath(ch)) *
                            xc.GetParentToWorldTransform(tm.GetPrim()).GetInverse())
    mount = UsdPhysics.FixedJoint.Define(stage, f"{root}/TipMountJoint")
    mount.CreateBody0Rel().SetTargets([ch])
    mount.CreateBody1Rel().SetTargets([tm.GetPath()])
    mount.CreateLocalPos0Attr(Gf.Vec3f(0))
    mount.CreateLocalPos1Attr(Gf.Vec3f(0))
    park = UsdGeom.Xform.Define(stage, f"{root}/TipLockPark")
    park.AddTranslateOp().Set(Gf.Vec3d(0, 0, -0.5))
    UsdPhysics.RigidBodyAPI.Apply(park.GetPrim()).CreateKinematicEnabledAttr(True)
    j = UsdPhysics.Joint.Define(stage, f"{root}/TipLock")
    jp = j.GetPrim()
    jp.AddAppliedSchema("IsaacAttachmentPointAPI")
    for ax in ("transX", "transY", "transZ", "rotX", "rotY", "rotZ"):
        lim = UsdPhysics.LimitAPI.Apply(jp, ax)
        lim.CreateLowAttr(1.0)
        lim.CreateHighAttr(-1.0)
    j.CreateBody0Rel().SetTargets([tm.GetPath()])
    j.CreateBody1Rel().SetTargets([park.GetPath()])
    j.CreateLocalPos0Attr(Gf.Vec3f(0))
    j.CreateLocalRot0Attr(Gf.Quatf(0, 1, 0, 0))          # +Z of the attachment frame points down, out of the cone
    j.CreateLocalPos1Attr(Gf.Vec3f(0))
    j.CreateLocalRot1Attr(Gf.Quatf(1, 0, 0, 0))
    j.CreateExcludeFromArticulationAttr(True)
    jp.CreateAttribute("isaac:forwardAxis", Sdf.ValueTypeNames.Token).Set("Z")
    jp.CreateAttribute("isaac:clearanceOffset", Sdf.ValueTypeNames.Float).Set(0.0)
    robot_schema.CreateSurfaceGripper(stage, f"{root}/TipGripper")
    gp = stage.GetPrimAtPath(f"{root}/TipGripper")
    gp.GetRelationship(robot_schema.Relations.ATTACHMENT_POINTS.name).SetTargets([jp.GetPath()])
    gp.GetAttribute(robot_schema.Attributes.MAX_GRIP_DISTANCE.name).Set(0.003)
    gp.GetAttribute(robot_schema.Attributes.COAXIAL_FORCE_LIMIT.name).Set(1.0e4)
    gp.GetAttribute(robot_schema.Attributes.SHEAR_FORCE_LIMIT.name).Set(1.0e4)
    gp.GetAttribute(robot_schema.Attributes.RETRY_INTERVAL.name).Set(0.3)
    return str(gp.GetPath())


def _station_tf(stage, root):
    return UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(root))


def add_tips(stage, root, positions, rack="rack_1", parent="/World/L12Consumables/Tips"):
    """Tips into the rack (rigid bodies resting on their collars). Returns {position: prim path}."""
    tf = _station_tf(stage, root)
    top = UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(f"{root}/tip_rack_frames/{rack}"))
    rack_c = tf.GetInverse().Transform(top.ExtractTranslation())
    out = {}
    for pos in positions:
        u, v = well_center(pos)
        local = Gf.Vec3d(rack_c[0] + u * MM, rack_c[1] + v * MM, rack_c[2] + 0.008 + 0.0002)
        path = f"{parent}/Tip_{rack}_{pos}"
        x = UsdGeom.Xform.Define(stage, path)
        x.GetPrim().GetReferences().AddReference(TIP_USD)
        x.AddTranslateOp().Set(tf.Transform(local))
        x.AddOrientOp().Set(Gf.Quatf(tf.ExtractRotationQuat()))
        x.GetPrim().CreateAttribute("labware:tipId", Sdf.ValueTypeNames.String, custom=True).Set(
            f"TIP-{rack.upper().replace('_', '')}-{pos}")
        out[pos] = path
    return out


def add_reagent_tube(stage, root, pos, barcode, reagent_id, lot, volume_uL, parent="/World/L12Consumables/Reagents"):
    """A 2 mL reagent tube (static collider, labelled) in reagent position pos; the volume is its PHYSICAL content."""
    tf = _station_tf(stage, root)
    p = stage.GetPrimAtPath(f"{root}/reagent_rack_frames/rack_1/pos_{pos}")
    base = UsdGeom.XformCache().GetLocalToWorldTransform(p).ExtractTranslation()
    path = f"{parent}/Tube_{pos}"
    x = UsdGeom.Xform.Define(stage, path)
    x.AddTranslateOp().Set(base)
    x.AddOrientOp().Set(Gf.Quatf(tf.ExtractRotationQuat()))
    body = UsdGeom.Cylinder.Define(stage, f"{path}/Body")
    body.CreateRadiusAttr(0.0054)
    body.CreateHeightAttr(0.040)
    body.AddTranslateOp().Set(Gf.Vec3d(0, 0, 0.020))
    body.CreateDisplayColorAttr([Gf.Vec3f(0.93, 0.93, 0.95)])
    body.CreateDisplayOpacityAttr([0.35])
    UsdPhysics.CollisionAPI.Apply(body.GetPrim())
    h = volume_uL / (math.pi * 4.5 ** 2) * MM
    liq = UsdGeom.Cylinder.Define(stage, f"{path}/Liquid")
    liq.CreateRadiusAttr(0.0045)
    liq.CreateHeightAttr(max(h, 1e-4))
    liq.AddTranslateOp().Set(Gf.Vec3d(0, 0, 0.001 + h / 2))
    liq.CreateDisplayColorAttr([Gf.Vec3f(0.55, 0.75, 0.95)])
    cap = UsdGeom.Cylinder.Define(stage, f"{path}/Label")
    cap.CreateRadiusAttr(0.0056)
    cap.CreateHeightAttr(0.012)
    cap.AddTranslateOp().Set(Gf.Vec3d(0, 0, 0.026))
    cap.CreateDisplayColorAttr([Gf.Vec3f(0.95, 0.95, 0.9)])
    pr = x.GetPrim()
    S = Sdf.ValueTypeNames.String
    for k, v in (("labware:barcode", barcode), ("reagent:id", reagent_id), ("reagent:lot", lot)):
        pr.CreateAttribute(k, S, custom=True).Set(v)
    pr.CreateAttribute("reagent:volume_uL", Sdf.ValueTypeNames.Double, custom=True).Set(float(volume_uL))
    return path


# ------------------------------------------------------------------ controller
@dataclass
class L12Controller:
    stage: Usd.Stage
    root: str
    gripper: str
    tips: dict                                  # rack position -> tip prim (what the inventory believes is loaded)
    reagent_inventory: dict                     # position -> {"reagent_id", "lot", "volume_uL"} (SDT belief)
    well_volume_uL: float = 100.0               # demo initial volume per well of a plate on the nest (D016)
    dt: float = 1.0 / 240
    t: float = 0.0
    mode: str = "READY"
    fault: str = ""
    events: list = field(default_factory=list)

    def __post_init__(self):
        from isaacsim.robot.surface_gripper import _surface_gripper as sgi
        self.prim = self.stage.GetPrimAtPath(self.root)
        g = lambda k: float(self.prim.GetAttribute(k).Get())  # noqa: E731
        self.ch_x, self.cone_z0 = g("lh:chX_mm"), g("lh:coneEndZ_mm")
        self.park = (g("lh:parkX_mm") * MM, g("lh:parkY_mm") * MM)
        self.well_bottom = g("lh:wellBottom_mm")
        self.art = Articulation(self.root)
        names = list(self.art.dof_names)
        self.dof = {k: names.index(v) for k, v in JOINTS.items()}
        self.sg = sgi.acquire_surface_gripper_interface()
        self.sq = get_physx_scene_query_interface()
        xc = UsdGeom.XformCache(Usd.TimeCode.Default())
        self.to_world = xc.GetLocalToWorldTransform(self.prim)
        self.w2l = self.to_world.GetInverse()
        L = lambda n: np.array(self.w2l.Transform(xc.GetLocalToWorldTransform(  # noqa: E731
            self.stage.GetPrimAtPath(f"{self.root}/{n}")).ExtractTranslation())) / MM
        self.nest = L("plate_nest")
        self.seat = [L(f"plate_nest_seat_sensor_{i}") for i in range(4)]
        self.plate_reader = L("plate_reader")
        self.rack_top = L("tip_rack_frames/rack_1")
        self.reagent_pos = {k: L(f"reagent_rack_frames/rack_1/pos_{k}") for k in range(1, 5)}
        self.reagent_reader = {k: L(f"reagent_reader_{k}") for k in range(1, 5)}
        self.waste = L("waste_frame")
        self.ex, self.ey, self.ez = (self._dir(v) for v in ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        q = self.art.get_dof_positions().numpy()[0]
        self.tgt = {k: float(q[i]) for k, i in self.dof.items()}
        self.liquid = lq.LiquidModel()
        self.used_tips = set()
        self.tip = None                         # {"id", "path", "pos"} while a tip is mounted
        self.doses = []
        self.plate_id = ""
        self._tip_views = {}
        self._job = None
        self._paused = False
        self._written = {}
        self.read_sensors()

    # ---------------------------------------------------------------- geometry
    def _dir(self, v):
        d = np.array(self.to_world.TransformDir(Gf.Vec3d(*v)))
        return d / np.linalg.norm(d)

    def W(self, p_mm):
        return np.array(self.to_world.Transform(Gf.Vec3d(*(float(v) * MM for v in p_mm))))

    def cone_end_mm(self):
        return np.array([self.q["x"] / MM + self.ch_x, self.q["y"] / MM, self.cone_z0 + self.q["z"] / MM])

    def joints_for(self, x_mm, y_mm):
        return (x_mm - self.ch_x) * MM, y_mm * MM

    # ---------------------------------------------------------------- sensing
    def _hits(self, origin, direction, dist):
        hits = []

        def report(h):
            if not h.collision.startswith(self.root + "/"):
                hits.append((h.distance, h.collision))
            return True

        self.sq.raycast_all(carb.Float3(*map(float, origin)), carb.Float3(*map(float, direction)), float(dist), report)
        return sorted(hits)

    def _owner(self, path, attr):
        p = self.stage.GetPrimAtPath(path)
        while p and p.GetPath() != Sdf.Path.absoluteRootPath and not p.GetAttribute(attr):
            p = p.GetParent()
        return p if p and p.GetAttribute(attr) else None

    def read_sensors(self):
        q = self.art.get_dof_positions().numpy()[0]
        self.q = {k: float(q[i]) for k, i in self.dof.items()}
        gaps = []
        for s in self.seat:
            h = self._hits(self.W(s), self.ez, 0.015)
            gaps.append(None if not h else h[0][0] - 0.001)
        self.seat_gaps = gaps
        self.plate_on_nest = any(v is not None for v in gaps)
        self.seated = all(v is not None and v < SEAT_GAP_OK for v in gaps)

    def read_plate_barcode(self):
        for d, path in self._hits(self.W(self.plate_reader), self.ex, 0.06):
            p = self._owner(path, "labware:barcode")
            if p:
                return p.GetAttribute("labware:barcode").Get(), p
        return None, None

    def read_reagent(self, pos):
        for d, path in self._hits(self.W(self.reagent_reader[pos]), self.ey, 0.03):
            p = self._owner(path, "reagent:id")
            if p:
                return {"barcode": p.GetAttribute("labware:barcode").Get(), "reagent_id": p.GetAttribute("reagent:id").Get(),
                        "lot": p.GetAttribute("reagent:lot").Get(), "path": str(p.GetPath())}
        return None

    def tip_present(self):
        """Horizontal light barrier across the tip collar just below the cone end."""
        c = self.cone_end_mm()
        origin = self.W(c + [-10.0, 0.0, -TIP_GAP - 4.0])
        for _, path in self._hits(origin, self.ex, 0.020):
            p = self._owner(path, "labware:tipId")
            if p:
                return p.GetAttribute("labware:tipId").Get(), str(p.GetPath())
        return None, None

    def tip_end_world(self):
        """REAL tip end (from the tip rigid body), or None without a mounted tip."""
        if not self.tip:
            return None
        v = self._tip_views.setdefault(self.tip["path"], RigidPrim(self.tip["path"]))
        p, q = v.get_world_poses()
        p, q = p.numpy()[0].astype(float), q.numpy()[0].astype(float)
        R = np.array(Gf.Matrix3d(Gf.Rotation(Gf.Quatd(*q))).GetTranspose())
        return p - R[:, 2] * TIP_LEN * MM

    # ---------------------------------------------------------------- liquid world (from the physical consumables)
    def tube_container(self, pos):
        info = self.read_reagent(pos)
        if not info:
            return None
        cid = f"tube:{info['path']}"
        if cid not in self.liquid.containers:
            pr = self.stage.GetPrimAtPath(info["path"])
            base = self.W(self.reagent_pos[pos])
            self.liquid.containers[cid] = lq.Container(cid, "tube", 4.5, base[2] + 0.001,
                                                       float(pr.GetAttribute("reagent:volume_uL").Get()),
                                                       {info["reagent_id"]: float(pr.GetAttribute("reagent:volume_uL").Get())},
                                                       info["reagent_id"], info["lot"])
        return cid

    def well_container(self, plate_id, well):
        cid = f"well:{plate_id}:{well}"
        if cid not in self.liquid.containers:
            u, v = well_center(well)
            bottom = self.W(self.nest + [u, v, self.well_bottom - self.nest[2]])
            self.liquid.containers[cid] = lq.Container(cid, "well", WELL_R, bottom[2], self.well_volume_uL,
                                                       {"medium": self.well_volume_uL})
        return cid

    # ---------------------------------------------------------------- command
    def airspace_clear(self):
        x0, x1 = AIRSPACE["x"]
        for y in AIRSPACE["y"]:
            for z in AIRSPACE["z"]:
                if self._hits(self.W([x0, y, z]), self.ex, (x1 - x0) * MM):
                    return False
        return True

    def dose_well(self, plate_id, well_id, reagent_pos, reagent_id, reagent_lot, volume_uL, dispense_height_mm=1.2,
                  dispense_rate_uL_s=0.5, aspirate_rate_uL_s=2.0, intended_effect="abstract_intervention") -> Result:
        if self.mode != "READY":
            return self._refuse("dose_well", f"mode {self.mode}")
        if not self.airspace_clear():
            return self._refuse("dose_well", "deck_airspace_occupied: a foreign object is in the gantry's airspace")
        if not 0.5 <= volume_uL <= 45.0:
            return self._refuse("dose_well", f"volume {volume_uL} uL outside the 50 uL tip's working range")
        self._start("dose_well", self._seq_dose(dict(
            plate_id=plate_id, well_id=well_id, reagent_pos=reagent_pos, reagent_id=reagent_id, reagent_lot=reagent_lot,
            volume_uL=volume_uL, dispense_height_mm=dispense_height_mm, dispense_rate_uL_s=dispense_rate_uL_s,
            aspirate_rate_uL_s=aspirate_rate_uL_s, intended_effect=intended_effect)), plate_id=plate_id, well=well_id)
        return Result(True)

    def park_head(self) -> Result:
        if self.mode != "READY":
            return self._refuse("park", f"mode {self.mode}")
        self._start("park", self._seq_park())
        return Result(True)

    # ---------------------------------------------------------------- sequences
    def _move(self, joint, target):
        start = self.tgt[joint]
        n = max(1, int(abs(target - start) / SPEED[joint] / self.dt))
        for i in range(1, n + 1):
            while not self.airspace_clear():               # pause (hold) until the airspace is clear again
                if not self._paused:
                    self._paused = True
                    for k in JOINTS:
                        self._set(k, self.q[k])
                    self._log("motion_paused", reason="deck_airspace_occupied")
                yield
            if self._paused:
                self._paused = False
                self._log("motion_resumed")
            self._set(joint, start + (target - start) * i / n)
            yield
        t0 = self.t
        while abs(self.q[joint] - target) > TOL[joint]:
            if self.t - t0 > MOVE_TIMEOUT_S:
                raise RuntimeError(f"{joint} did not reach {target:.5f} (at {self.q[joint]:.5f})")
            yield

    def _wait(self, s):
        t0 = self.t
        while self.t - t0 < s - 1e-9:
            yield

    def _travel(self, x_mm, y_mm):
        """Safe travel: channel up, then X/Y."""
        yield from self._move("z", 0.0)
        qx, qy = self.joints_for(x_mm, y_mm)
        yield from self._move("y", qy)
        yield from self._move("x", qx)

    def _seq_park(self):
        yield from self._move("z", 0.0)
        yield from self._move("y", self.park[1])
        yield from self._move("x", self.park[0])
        self.mode = "READY"

    def _z_for_cone(self, cone_z_mm):
        """ChannelZ joint target that puts the cone end at cone_z_mm (STATION-local mm)."""
        return (cone_z_mm - self.cone_z0) * MM

    def _local_z_mm(self, z_world):
        """World height (m) -> station-local height (mm); the station stands level. (The first bench run fed world
        heights to _z_for_cone: fine on the floor-standing test station, +0.81 m on the 0.92 m bench, 2026-10-16.)"""
        return (z_world - float(self.to_world.ExtractTranslation()[2])) / MM

    def _seq_pick_tip(self, ev):
        free = [p for p in self.tips if p not in self.used_tips]
        if not free:
            ev["tip"] = {"ok": False, "reason": "no tip left in the inventory"}
            return
        pos = free[0]
        self.used_tips.add(pos)
        u, v = well_center(pos)
        x, y = self.rack_top[0] + u, self.rack_top[1] + v
        yield from self._travel(x, y)
        collar_top = self.rack_top[2] + 8.0
        yield from self._move("z", self._z_for_cone(collar_top + 10.0))
        yield from self._move("z", self._z_for_cone(collar_top + TIP_GAP))
        yield from self._wait(0.1)
        self.sg.close_gripper(self.gripper)
        yield from self._wait(0.4)
        yield from self._move("z", 0.0)
        yield from self._wait(0.2)
        tid, path = self.tip_present()
        gripped = list(self.sg.get_gripped_objects(self.gripper))
        expected = f"TIP-RACK1-{pos}"
        ok = tid is not None and tid == expected
        if ok:
            self.tip = {"id": tid, "path": path, "pos": pos}
        else:
            self.sg.open_gripper(self.gripper)
        ev["tip"] = {"ok": ok, "rack_position": pos, "expected": expected, "observed": tid, "gripped": gripped}
        self._log("tip_pick", **ev["tip"])

    def _seq_eject(self, ev):
        x, y, z = self.waste
        yield from self._travel(x, y)
        yield from self._move("z", self._z_for_cone(z + TIP_LEN))
        path = self.tip["path"] if self.tip else None
        self.sg.open_gripper(self.gripper)
        yield from self._wait(0.8)
        tid, _ = self.tip_present()
        fell = None
        if path:
            p = self._tip_views.setdefault(path, RigidPrim(path)).get_world_poses()[0].numpy()[0]
            fell = float(np.array(self.w2l.Transform(Gf.Vec3d(*map(float, p))))[2] / MM)
        ev["eject"] = {"ok": tid is None, "tip_id": (self.tip or {}).get("id"), "tip_z_after_mm": fell}
        self._log("tip_eject", **ev["eject"])
        self.tip = None
        yield from self._move("z", 0.0)

    def _seq_lld(self, cid, x, y, expected_surface_z, bottom_z, ev, key):
        """Descend at LLD speed from 5 mm above the expected surface until the conductive tip touches liquid."""
        yield from self._travel(x, y)
        tip_off = TIP_GAP + TIP_LEN                         # nominal cone end to tip end (controller belief)
        yield from self._move("z", self._z_for_cone(self._local_z_mm(expected_surface_z) + 5.0 + tip_off))
        start = self.tgt["z"]
        stop = self._z_for_cone(self._local_z_mm(bottom_z) + 0.5 + tip_off)
        n = max(1, int((start - stop) / LLD_SPEED / self.dt))
        hit = None
        for i in range(1, n + 1):
            self._set("z", start + (stop - start) * i / n)
            yield
            te = self.tip_end_world()
            if te is not None and self.liquid.lld(cid, te[2]):
                hit = float(self.W(self.cone_end_mm() - [0.0, 0.0, tip_off])[2])
                self._set("z", self.q["z"])
                break
        ev[key] = {"detected": hit is not None, "surface_z_m": None if hit is None else round(hit, 5),
                   "expected_surface_z_m": round(expected_surface_z, 5),
                   "deviation_mm": None if hit is None else round((hit - expected_surface_z) * 1e3, 3)}
        return hit

    def _seq_transfer(self, cid, q_uL_s, volume, sign, follow_area_mm2, ev, key):
        """Aspirate (sign -1, with liquid following) or dispense (+1) volume at q; record the pressure trace (one
        sample per physics step) and judge it against the envelope."""
        flow, settle, moved, t = [], [], 0.0, 0.0
        duration = volume / q_uL_s
        while t < duration - 1e-9:
            yield
            t += self.dt
            te = self.tip_end_world()
            p, m = self.liquid.flow_step(cid, q_uL_s, self.dt, te[2], sign, t / duration)
            moved += m
            if sign < 0 and follow_area_mm2:               # liquid following: track the falling surface
                self._set("z", self.tgt["z"] - q_uL_s * self.dt / follow_area_mm2 * MM)
            flow.append((round(t, 4), round(p, 2)))
        t_end = t
        while t < t_end + 0.3:                             # settle: pressure back to baseline
            yield
            t += self.dt
            settle.append((round(t, 4), round(self.liquid.settle_sample(), 2)))
        verdict = lq.judge_trace(flow, q_uL_s, sign, duration)
        inferred = float(sum(abs(p) / lq.K_R for _, p in flow) * self.dt)
        trace = flow + settle
        ev[key] = {**verdict, "commanded_uL": round(volume, 3), "inferred_from_pressure_uL": round(inferred, 3),
                   "returned_to_baseline": bool(abs(np.mean([p for _, p in settle[-24:]])) < 2.0),
                   "trace": trace[:: max(1, len(trace) // 200)]}
        return moved

    def _seq_dose(self, a):
        ev = {"request": dict(a), "t_start": round(self.t, 3)}
        mons = {}
        abort = None
        # plate identity + seating + well binding
        seen, _ = self.read_plate_barcode()
        self.plate_id = seen or ""
        mons["plate_identity"] = (seen == a["plate_id"], f"L12 plate reader: expected {a['plate_id']}, read {seen!r}", seen)
        mons["plate_seating"] = (self.seated, "4 nest seat sensors " + ("confirm seating" if self.seated else "do not confirm seating"),
                                 [None if g is None else round(g * 1e3, 3) for g in self.seat_gaps])
        well = parse_well(a["well_id"])
        if not (mons["plate_identity"][0] and mons["plate_seating"][0]) or well is None:
            abort = "plate not verified / not seated / well not bound"
        # reagent identity (barcode reader of the position)
        info = self.read_reagent(a["reagent_pos"])
        rid_ok = bool(info) and info["reagent_id"] == a["reagent_id"] and info["lot"] == a["reagent_lot"]
        mons["reagent_identity"] = (rid_ok, f"reagent reader pos {a['reagent_pos']}: requested {a['reagent_id']} lot "
                                            f"{a['reagent_lot']}, read {info and (info['reagent_id'], info['lot'])}", info)
        if abort is None and not rid_ok:
            abort = "wrong_reagent: abort before aspiration"
        # tip
        if abort is None:
            yield from self._seq_pick_tip(ev)
            if not ev["tip"]["ok"]:
                abort = f"tip_missing_or_dropped: {ev['tip']}"
        # liquid level at the reagent
        cid = self.tube_container(a["reagent_pos"]) if abort is None else None
        if abort is None:
            inv = self.reagent_inventory[a["reagent_pos"]]
            base = self.W(self.reagent_pos[a["reagent_pos"]])[2] + 0.001
            expected = base + inv["volume_uL"] / (math.pi * 4.5 ** 2) * 1e-3
            x, y = self.reagent_pos[a["reagent_pos"]][:2]
            hit = yield from self._seq_lld(cid, x, y, expected, base, ev, "lld")
            if hit is None or abs(ev["lld"]["deviation_mm"]) > LEVEL_TOL_MM:
                abort = "liquid level disagrees with the inventory: abort before aspiration"
        mons["liquid_level"] = (abort is None and "lld" in ev and ev["lld"]["detected"],
                                f"cLLD: {ev.get('lld')}", ev.get("lld"))
        # aspirate (2 mm submerged, following)
        if abort is None:
            yield from self._move("z", self.tgt["z"] - SUBMERGE_MM * MM)
            yield from self._seq_transfer(cid, a["aspirate_rate_uL_s"], a["volume_uL"], -1, math.pi * 4.5 ** 2, ev,
                                          "aspirate")
            ev["aspirated_uL_model"] = round(self.liquid.aspirated_uL, 3)
        # dispense into the well at the requested height
        if abort is None:
            u, v = well_center(well)
            wx, wy = self.nest[0] + u, self.nest[1] + v
            yield from self._travel(wx, wy)
            tip_off = TIP_GAP + TIP_LEN
            yield from self._move("z", self._z_for_cone(self.well_bottom + a["dispense_height_mm"] + tip_off))
            yield from self._wait(0.1)
            te = self.tip_end_world()
            target = self.W([wx, wy, self.well_bottom + a["dispense_height_mm"]])
            off = (te - target) * 1e3
            ev["well_position"] = {"tip_end_offset_mm": np.round(off, 3).tolist(),
                                   "lateral_mm": round(float(math.hypot(off[0], off[1])), 3)}
            wcid = self.well_container(a["plate_id"], well)
            yield from self._seq_transfer(wcid, a["dispense_rate_uL_s"], max(self.liquid.aspirated_uL, 0.01), +1, 0.0, ev,
                                          "dispense")
            ev["well_volume_after_uL"] = round(self.liquid.containers[wcid].volume_uL, 3)
            ev["well_contents_after"] = {k: round(v, 3) for k, v in self.liquid.containers[wcid].contents.items()}
        tip_ok_dispense = abort is None and self.tip is not None and self.tip_present()[0] == (self.tip or {}).get("id")
        if self.tip:
            yield from self._seq_eject(ev)
        yield from self._seq_park()
        # remaining monitors
        lat = ev.get("well_position", {}).get("lateral_mm")
        mons["well_binding"] = (well is not None and lat is not None and lat <= 1.0,
                                f"well {well} frame from the nest; real tip end {lat} mm from the well centre at dispense",
                                well)
        tip_ok = bool(ev.get("tip", {}).get("ok")) and tip_ok_dispense and bool(ev.get("eject", {}).get("ok"))
        mons["tip_state"] = (tip_ok, f"fresh tip {ev.get('tip', {}).get('observed')} attached (presence ray) through the "
                                     f"dispense, ejected to waste", ev.get("tip", {}).get("observed"))
        asp, dsp = ev.get("aspirate", {}), ev.get("dispense", {})
        mons["pressure_profile"] = (bool(asp.get("ok")) and bool(dsp.get("ok")),
                                    f"aspirate {asp and {k: asp[k] for k in ('plateau_mbar', 'expected_mbar', 'steady_fraction', 'clog_limit_hit')}}; "
                                    f"dispense {dsp and {k: dsp[k] for k in ('plateau_mbar', 'expected_mbar', 'steady_fraction')}}",
                                    {"aspirate": asp.get("ok"), "dispense": dsp.get("ok")})
        inferred = dsp.get("inferred_from_pressure_uL")
        done = bool(dsp) and dsp.get("returned_to_baseline") and inferred is not None and \
            abs(inferred - a["volume_uL"]) <= 0.05 * a["volume_uL"] + 0.1
        mons["dispense_completion"] = (bool(done), f"pressure back to baseline; volume inferred from the trace {inferred} "
                                                   f"uL of {a['volume_uL']} uL commanded", inferred)
        order = ("plate_identity", "well_binding", "reagent_identity", "tip_state", "plate_seating", "liquid_level",
                 "pressure_profile", "dispense_completion")
        rec = {"t": round(self.t, 3), **{k: a[k] for k in ("plate_id", "reagent_id", "reagent_lot", "volume_uL",
                                                           "dispense_height_mm", "dispense_rate_uL_s", "intended_effect")},
               "well_id": well or a["well_id"], "tip_id": ev.get("tip", {}).get("observed") or "",
               "monitors": [dict(name=k, passed=bool(mons[k][0]), observation=mons[k][1], value=mons[k][2]) for k in order],
               "command_completed": abort is None and bool(dsp), "aborted": abort, "evidence": ev,
               "volume_inferred_uL": inferred}
        rec["valid"] = all(m["passed"] for m in rec["monitors"]) and rec["command_completed"]
        self.doses.append(rec)
        self._log("dose_done", well=rec["well_id"], valid=rec["valid"], aborted=abort)
        self.mode = "READY"

    # ---------------------------------------------------------------- loop / outputs
    def update(self, dt=None):
        self.dt = dt or self.dt
        self.t += self.dt
        self.read_sensors()
        if self._job is not None:
            try:
                next(self._job)
            except StopIteration:
                self._job = None
            except RuntimeError as exc:
                self._job = None
                self.fault, self.mode = "device_fault", "FAULT"
                for k in JOINTS:
                    self._set(k, self.q[k])
                self._log("fault", fault=self.fault, detail=str(exc))
        self._outputs()

    def _set(self, joint, value):
        self.tgt[joint] = value
        self.art.set_dof_position_targets(np.array([[value]], dtype=np.float32), dof_indices=[self.dof[joint]])

    def _outputs(self):
        self._write("state:tip_present", self.tip is not None)
        self._write("state:tip_id", (self.tip or {}).get("id", ""))
        self._write("state:aspirated_volume_uL", round(self.liquid.aspirated_uL, 3))
        self._write("state:plate_id", self.plate_id)
        self._write("state:mode", self.mode)
        self._write("state:fault", self.fault)
        for lens, on in (("LensGreen", self.mode == "READY"), ("LensAmber", self.mode == "BUSY"),
                         ("LensRed", self.mode == "FAULT")):
            self._write("inputs:emissive_intensity", LIGHT_ON if on else 0.0, f"{self.root}/Looks/{lens}/Shader")

    def _write(self, attr, value, path=None):
        key = (path or self.root, attr)
        if self._written.get(key) == value:
            return
        prim = self.stage.GetPrimAtPath(path) if path else self.prim
        a = prim.GetAttribute(attr) if prim else None
        if a:
            a.Set(value)
            self._written[key] = value

    def _log(self, event, **d):
        self.events.append({"t": round(self.t, 4), "event": event, "mode": self.mode, **d})

    def _start(self, cmd, gen, **d):
        self.mode = "BUSY"
        self._job = gen
        self._log(f"{cmd}_accepted", **d)

    def _refuse(self, cmd, reason):
        self._log(f"{cmd}_refused", reason=reason)
        return Result(False, reason)

    def save_events(self, path):
        with open(path, "w") as f:
            json.dump({"component": "L12", "events": self.events, "doses": self.doses}, f, indent=2, default=str)
