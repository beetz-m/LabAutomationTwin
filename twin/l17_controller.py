"""Runtime controller for the L17 Bright-Field Imaging Station twin (sdt/components/L17_BrightFieldImager.yaml).

Asset: assets/l17/l17.usda (gate, XY stage = load drawer, focus drive, 2-objective turret, LED condenser, camera).

  capabilities  load_plate (present_for_load + load_plate), autofocus, image_well, image_plate_region,
                compute_focus_quality, export_raw_image; plus present_for_unload / present_for_removal / stow
  constraints   plate identity (barcode READ at the stage home position) and the well coordinate are bound to each
                image; calibration and focus validity are required before an image can support a claim; every
                exposure (autofocus frames included) is added to the plate's imaging history
  monitors      plate_identity, plate_seating (4 seat sensors), focus_quality (image focus score), illumination_state
                (LED read back, gate closed, image histogram in the usable range), calibration_state
  faults        plate_misseated (load refused: reseat), plate_identity_mismatch (plate held, present for removal),
                out_of_focus (autofocus found no focus: image retained, blocked), calibration_expired (image_well
                refused), device faults (axis did not reach its target)

The mechanism is physically simulated (ramped joint targets, PhysX). The camera (L17Camera) forms the image from
the simulated state with twin/l17_optics.py; the controller decides from that image and its own encoders only.
Ground truth from the optics model is kept apart in `truth` for tests and audits and is never used for decisions.
Sequences are generators advanced once per physics step by update(), as in the plate stores.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
from dataclasses import dataclass, field

import carb
import numpy as np
from isaacsim.core.experimental.prims import Articulation, RigidPrim
from omni.physx import get_physx_scene_query_interface
from pxr import Gf, Usd, UsdGeom

from . import l17_optics as optics

MM = 0.001
JOINTS = {"gate": "GateSlide", "y": "StageY", "x": "StageX", "focus": "FocusZ", "turret": "TurretRotate"}
SPEED = {"gate": 0.10, "y": 0.10, "x": 0.05, "focus": 0.001, "turret": math.radians(120.0)}   # per s
TOL = {"gate": 0.0004, "y": 0.00002, "x": 0.00002, "focus": 0.000005, "turret": math.radians(0.3)}
MOVE_TIMEOUT_S = 6.0
SEAT_GAP_OK = 0.0004
LIGHT_ON = 3000.0
LED_FULL = 30000.0            # light prim intensity at LED level 1.0 (render units)
LED_EMISSIVE = 6000.0
STRAY_E_PER_MS = 150.0        # ambient light reaching the sensor with the gate open (assumption)
HIST_OK = {"mean_fs": (0.25, 0.85), "saturated_max": 0.001}
AF_REL = 0.85                 # focus_quality with autofocus: score >= AF_REL x the sweep's best score

# Twin calibration record (simulated; the L21 QC station is not built yet). Values match the optics model.
CALIBRATION_DEMO = {
    "calibration_id": "L17-CAL-2026-10-16-SIM",
    "source": "twin calibration record (simulated input; L21 QC not yet built)",
    "issued": "2026-10-16", "valid_until": "2026-11-15",
    "objectives": {"10x": {"pixel_um": 0.45, "focus_floor": 0.04}, "4x": {"pixel_um": 1.12, "focus_floor": 0.15}},
    "sensor": {"gain_e_per_adu": optics.FULL_WELL_E / optics.ADC_MAX, "read_noise_e": optics.READ_E},
    "stage_offset_mm": [0.0, 0.0],
}


@dataclass
class Result:
    accepted: bool
    reason: str = ""


class L17Camera:
    """The simulated camera: image formed from the plate pose, focus, objective index, LED and exposure."""

    def __init__(self, ctrl, seed=0):
        self.c = ctrl
        self.rng = np.random.default_rng(seed)
        self._plates = {}
        # physical state of the optics that the controller cannot see (test hooks for injected faults):
        # true object-space pixel size factor per objective (magnification drift), LED output efficiency
        self.pixel_scale = {}
        self.led_efficiency = 1.0

    def objective_on_axis(self):
        q = math.degrees(self.c.q["turret"])
        for mag in self.c.objectives:
            if abs(q - self.c.index_deg[mag]) < 1.0:
                return mag
        return None

    def _plate_above(self, focal):
        hit = self.c.ray_hit(focal - self.c.ez * 0.02, self.c.ez, 0.06)
        return hit[1] if hit else None

    def capture(self, exposure_ms):
        c = self.c
        mag = self.objective_on_axis()
        focal = c.world_mm((c.x_opt, c.y_opt, c.focal0 + c.q["focus"] / MM))
        led = c.led_level_readback() * self.led_efficiency
        stray = STRAY_E_PER_MS if c.q["gate"] > 0.002 else 0.0
        if mag is None:   # no objective in the beam path: the sensor sees stray light only
            img = optics._expose(np.zeros(optics.SENSOR[::-1]), 0.0, exposure_ms, stray, self.rng)
            return img, {"objective": None}
        o = c.objectives[mag]
        plate = self._plate_above(focal)
        kw = dict(plate_pos=None, plate_R=None, barcode=None)
        if plate is not None:
            path = str(plate.GetPath())
            if path not in self._plates:
                self._plates[path] = RigidPrim(path)
            p, qwxyz = self._plates[path].get_world_poses()
            p, qwxyz = p.numpy()[0].astype(float), qwxyz.numpy()[0].astype(float)
            R = np.array(Gf.Matrix3d(Gf.Rotation(Gf.Quatd(*qwxyz))).GetTranspose())   # row-major -> columns = axes
            kw = dict(plate_pos=p, plate_R=R, barcode=plate.GetAttribute("labware:barcode").Get())
        img, truth = optics.form_image(well_bottom_mm=c.well_bottom, focal_point=focal, axis=c.ez, ex=c.ex, ey=c.ey,
                                       na=o["na"], pixel_um=o["pixel_um"] * self.pixel_scale.get(mag, 1.0),
                                       led_level=led, exposure_ms=exposure_ms,
                                       stray_e_per_ms=stray, rng=self.rng, **kw)
        truth["objective"] = mag
        return img, truth


@dataclass
class L17Controller:
    stage: Usd.Stage
    root: str
    calibration: dict = field(default_factory=lambda: json.loads(json.dumps(CALIBRATION_DEMO)))
    today: str = "2026-10-16"
    image_dir: str = ""
    dt: float = 1.0 / 240
    t: float = 0.0
    mode: str = "READY"   # READY | PRESENTED_EMPTY | PRESENTED_LOADED | LOADED | BUSY | FAULT
    fault: str = ""
    events: list = field(default_factory=list)

    def __post_init__(self):
        self.prim = self.stage.GetPrimAtPath(self.root)
        g = lambda k: float(self.prim.GetAttribute(k).Get())  # noqa: E731
        self.seat_z, self.well_bottom = g("imager:seatZ_mm") * MM, g("imager:wellBottom_mm")
        self.focal0, self.y_load = g("imager:focalZ0_mm"), g("imager:yLoad_mm") * MM
        self.gate_travel = g("imager:gateTravel_mm") * MM
        self.x_lim = (g("imager:xMin_mm") * MM, g("imager:xMax_mm") * MM)
        self.y_max = g("imager:yMax_mm") * MM
        self.focus_lim = (g("imager:focusMin_mm") * MM, g("imager:focusMax_mm") * MM)
        self.objectives = {m: {k: g(f"optics:objective_{m}:{k}") for k in ("na", "wd", "pixel_um", "angle")}
                           for m in self.prim.GetAttribute("optics:objectives").Get()}
        self.index_deg = {m: 180.0 - o["angle"] for m, o in self.objectives.items()}   # turret q putting m on axis
        self.art = Articulation(self.root)
        names = list(self.art.dof_names)
        self.dof = {k: names.index(v) for k, v in JOINTS.items()}
        self.sq = get_physx_scene_query_interface()
        xc = UsdGeom.XformCache(Usd.TimeCode.Default())
        self.to_world = xc.GetLocalToWorldTransform(self.prim)
        w2l = self.to_world.GetInverse()

        def local(path):
            return np.array(w2l.Transform(xc.GetLocalToWorldTransform(self.stage.GetPrimAtPath(f"{self.root}/{path}"))
                                          .ExtractTranslation()))

        self.seat_local = [local(f"StageY/StageX/seat_sensor_{i}") for i in range(4)]
        self.reader = local("barcode_reader")
        obj = local("objective_frame") / MM
        self.x_opt, self.y_opt = obj[0], obj[1]
        self.ex, self.ey, self.ez = self._dir((1, 0, 0)), self._dir((0, 1, 0)), self._dir((0, 0, 1))
        self.led = self.stage.GetPrimAtPath(f"{self.root}/Body/Visual/IlluminationLed").GetAttribute("inputs:intensity")
        q = self.art.get_dof_positions().numpy()[0]
        self.tgt = {k: float(q[i]) for k, i in self.dof.items()}
        self.camera = L17Camera(self)
        self.plate_id = ""            # identity verified by the barcode read at load
        self.identity_fault = None
        self.focus_memory = {}        # (plate_id, magnification) -> FocusZ (m) of the last good focus
        self.history = {}             # plate_id -> well -> {"exposures", "light_dose_rel_ms"} (imaging history)
        self.acquisitions = []        # one record per image_well acquisition (valid or rejected)
        self.autofocus_runs = []
        self.truth = []               # optics ground truth per acquisition (tests/audit only)
        self.images = {}              # acquisition index -> raw image array (recent ones; L21 analyses QC images)
        self._cal_since = 0
        self._job = None
        self._written = {}
        self._led_level = 0.0
        self.read_sensors()

    # ------------------------------------------------------------------ geometry / sensing
    def _dir(self, v):
        d = np.array(self.to_world.TransformDir(Gf.Vec3d(*v)))
        return d / np.linalg.norm(d)

    def world_mm(self, p_mm):
        return np.array(self.to_world.Transform(Gf.Vec3d(*(float(v) * MM for v in p_mm))))

    def _world(self, p):
        return np.array(self.to_world.Transform(Gf.Vec3d(*map(float, p))))

    def ray_hit(self, origin_world, direction, dist):
        """Closest hit outside L17 -> (distance, plate root prim or None), or None."""
        hits = []

        def report(h):
            if not h.collision.startswith(self.root + "/"):
                hits.append((h.distance, h.collision))
            return True

        self.sq.raycast_all(carb.Float3(*map(float, origin_world)), carb.Float3(*map(float, direction)), dist, report)
        if not hits:
            return None
        d, path = min(hits)
        p = self.stage.GetPrimAtPath(path)
        while p and p.GetPath() != p.GetPath().GetParentPath() and not p.GetAttribute("labware:barcode"):
            p = p.GetParent()
        return d, (p if p and p.GetAttribute("labware:barcode") else None)

    def read_sensors(self):
        q = self.art.get_dof_positions().numpy()[0]
        self.q = {k: float(q[i]) for k, i in self.dof.items()}
        shift = np.array([self.q["x"], self.q["y"], 0.0])
        gaps = []
        for s in self.seat_local:
            h = self.ray_hit(self._world(s + shift), self.ez, 0.015)
            gaps.append(None if h is None else h[0] - 0.001)
        self.seat_gaps = gaps
        self.plate_on_nest = any(v is not None for v in gaps)
        self.seated = all(v is not None and v < SEAT_GAP_OK for v in gaps)

    def read_barcode(self):
        """Identity actually observed: the barcode of the plate hit by the reader's ray (stage at home only)."""
        if abs(self.q["y"]) > 0.001 or abs(self.q["x"]) > 0.001:
            return None
        h = self.ray_hit(self._world(self.reader), self.ex, 0.09)
        return h[1].GetAttribute("labware:barcode").Get() if h and h[1] else None

    def led_level_readback(self):
        return float(self.led.Get() or 0.0) / LED_FULL

    @property
    def calibration_valid(self):
        return self.calibration.get("status", "valid") == "valid" and \
            datetime.date.fromisoformat(self.today) <= datetime.date.fromisoformat(self.calibration["valid_until"])

    def apply_calibration(self, record: dict, by: str) -> Result:
        """Install a calibration record issued by L21 (validate_imager); measurements from now on bind to it."""
        if record.get("status") != "valid":
            return self._refuse("apply_calibration", f"record {record.get('calibration_id')} is not valid")
        self.calibration = json.loads(json.dumps(record))
        self._cal_since = len(self.acquisitions)
        self._log("calibration_applied", calibration_id=record["calibration_id"], by=by)
        return Result(True)

    def invalidate_calibration(self, reason: str, qc_record: str, magnifications=None) -> list:
        """L21 found the measurement chain out of tolerance: block measurements and flag every acquisition that was
        bound to this calibration (dependent measurements). Returns the flagged acquisition indices."""
        cal = self.calibration["calibration_id"]
        self.calibration["status"] = "invalidated"
        self.calibration["invalidated_by"] = qc_record
        flagged = [i for i, a in enumerate(self.acquisitions)
                   if a.get("calibration_id") == cal and a.get("purpose", "measurement") == "measurement"
                   and (magnifications is None or a["magnification"] in magnifications)]
        for i in flagged:
            self.acquisitions[i]["invalidated_by"] = qc_record
        self._log("calibration_invalidated", calibration_id=cal, reason=reason, qc_record=qc_record,
                  dependent_acquisitions=flagged)
        return flagged

    def stage_pose(self):
        if abs(self.q["y"] + self.y_load) < 0.001 and abs(self.q["x"]) < 0.001:
            return "presented"
        if abs(self.q["y"]) < 0.001 and abs(self.q["x"]) < 0.001:
            return "home"
        if self.y_max >= self.q["y"] >= -0.040:
            wid, d = optics.nearest_well(-self.q["x"] / MM, -self.q["y"] / MM)
            if wid and d < 0.05:
                return f"well {wid}"
        return "moving"

    # ------------------------------------------------------------------ executive-facing commands
    def present_for_load(self) -> Result:
        if self.mode != "READY":
            return self._refuse("present_for_load", f"mode {self.mode}")
        if self.plate_on_nest:
            return self._refuse("present_for_load", "stage nest not clear")
        return self._start("present_for_load", self._seq_present("PRESENTED_EMPTY"))

    def load_plate(self, plate_id: str) -> Result:
        """load_plate: plate seated on the presented nest -> retract, close, read the barcode at home."""
        if self.mode != "PRESENTED_EMPTY":
            return self._refuse("load_plate", f"mode {self.mode}")
        if not self.plate_on_nest:
            return self._refuse("load_plate", "no plate on the presented nest")
        if not self.seated:
            return self._refuse("load_plate", f"plate_misseated: seat gaps {self._gaps_mm()} mm; reseat",
                                fault_signal="plate_misseated")
        return self._start("load_plate", self._seq_load(plate_id), plate_id=plate_id)

    def present_for_unload(self) -> Result:
        if self.mode != "LOADED":
            return self._refuse("present_for_unload", f"mode {self.mode}")
        return self._start("present_for_unload", self._seq_present("PRESENTED_LOADED"), plate_id=self.plate_id)

    def present_for_removal(self, reason: str) -> Result:
        """After plate_identity_mismatch: present the held plate so a robot can take it to H4."""
        if self.mode != "FAULT" or self.fault != "plate_identity_mismatch":
            return self._refuse("present_for_removal", f"mode {self.mode}, fault {self.fault!r}")
        self._log("fault_handled", fault=self.fault, route="present_for_removal", reason=reason)
        self.fault = ""
        return self._start("present_for_removal", self._seq_present("PRESENTED_LOADED"))

    def stow(self) -> Result:
        if self.mode not in ("PRESENTED_EMPTY", "PRESENTED_LOADED"):
            return self._refuse("stow", f"mode {self.mode}")
        if self.plate_on_nest:
            return self._refuse("stow", "plate on the presented nest: load it or remove it")
        return self._start("stow", self._seq_stow())

    def image_well(self, plate_id, well_id, exposure_ms=25.0, magnification="10x", focus_policy="autofocus",
                   led_level=1.0, measurement_binding_id="brightfield-morphology-v1", purpose="measurement") -> Result:
        return self.image_plate_region(plate_id, [well_id], exposure_ms, magnification, focus_policy, led_level,
                                       measurement_binding_id, purpose=purpose, _cmd="image_well")

    def image_plate_region(self, plate_id, wells, exposure_ms=25.0, magnification="10x", focus_policy="autofocus",
                           led_level=1.0, measurement_binding_id="brightfield-morphology-v1", purpose="measurement",
                           _cmd="image_plate_region"):
        """Preconditions: plate verified and seated, wells bound, calibration valid, device healthy.

        purpose="qc" (L21 reference measurements only): allowed while the calibration is invalid or expired, because
        that is how it is restored; such images are labelled QC and are never measurement evidence."""
        if isinstance(wells, str):
            wells = region_wells(wells)
        bound = [optics.parse_well(w) for w in wells]
        if self.mode != "LOADED":
            return self._refuse(_cmd, f"mode {self.mode}")
        if plate_id != self.plate_id:
            return self._refuse(_cmd, f"plate {plate_id!r} is not the verified plate {self.plate_id!r}")
        if not self.seated:
            return self._refuse(_cmd, f"plate_misseated: seat gaps {self._gaps_mm()} mm", fault_signal="plate_misseated")
        if not wells or None in bound:
            return self._refuse(_cmd, f"well coordinate not bound: {wells}")
        if purpose == "qc" and not str(plate_id).startswith("REF-"):
            return self._refuse(_cmd, "QC acquisitions are only for reference artifacts")
        if not self.calibration_valid and purpose != "qc":
            cal = self.calibration
            if cal.get("status", "valid") != "valid":
                return self._refuse(_cmd, f"calibration_invalidated: {cal['calibration_id']} invalidated by "
                                          f"{cal.get('invalidated_by')}; repair/recalibrate via L21 first",
                                    fault_signal="calibration_invalidated")
            return self._refuse(_cmd, f"calibration_expired: {cal['calibration_id']} valid until "
                                      f"{cal['valid_until']}, today {self.today}; run L21 QC first",
                                fault_signal="calibration_expired")
        if magnification not in self.objectives or (purpose != "qc" and magnification not in self.calibration["objectives"]):
            return self._refuse(_cmd, f"no calibrated objective {magnification!r}")
        if not 0.0 < exposure_ms <= 1000.0 or not 0.0 < led_level <= 1.0:
            return self._refuse(_cmd, f"acquisition parameters out of range: {exposure_ms} ms, LED {led_level}")
        return self._start(_cmd, self._seq_image(plate_id, bound, exposure_ms, magnification, focus_policy, led_level,
                                                 measurement_binding_id, purpose),
                           plate_id=plate_id, wells=bound, exposure_ms=exposure_ms, magnification=magnification,
                           focus_policy=str(focus_policy))

    def autofocus(self, plate_id, well_id, magnification="10x", exposure_ms=25.0, fresh=False) -> Result:
        """Stand-alone autofocus at a well (capability `autofocus`); the result goes to autofocus_runs.
        fresh=True forgets the stored focus first (full-range search; L21 uses it for repeatability)."""
        if self.mode != "LOADED" or plate_id != self.plate_id or optics.parse_well(well_id) is None:
            return self._refuse("autofocus", f"mode {self.mode}, plate {plate_id!r}, well {well_id!r}")
        if fresh:
            self.focus_memory.pop((plate_id, magnification), None)

        def seq():
            yield from self._index(magnification)
            yield from self._goto_well(optics.parse_well(well_id))
            yield from self._autofocus(plate_id, optics.parse_well(well_id), magnification, exposure_ms, 1.0)
            self.mode = "LOADED"

        return self._start("autofocus", seq(), well=well_id, magnification=magnification)

    def compute_focus_quality(self, image, magnification="10x") -> dict:
        s = self.calibration["sensor"]
        score = optics.focus_score(image, s["gain_e_per_adu"], s["read_noise_e"])
        floor = self.calibration["objectives"][magnification]["focus_floor"]
        return {"focus_score": round(score, 4), "threshold": floor, "passed": score >= floor}

    def reset_fault(self, by: str) -> Result:
        if self.mode != "FAULT" or self.fault == "plate_identity_mismatch":
            return self._refuse("reset_fault", f"mode {self.mode}, fault {self.fault!r}")
        self._log("fault_reset", by=by, fault=self.fault)
        self.fault = ""
        self.mode = "LOADED" if self.plate_id else "READY"
        return Result(True)

    # ------------------------------------------------------------------ sequences
    def _move(self, joint, target):
        start = self.tgt[joint]
        n = max(1, int(abs(target - start) / SPEED[joint] / self.dt))
        for i in range(1, n + 1):
            self._set(joint, start + (target - start) * i / n)
            yield
        t0 = self.t
        while abs(self.q[joint] - target) > TOL[joint]:
            if self.t - t0 > MOVE_TIMEOUT_S:
                raise RuntimeError(f"{joint} did not reach {target:.6f} (at {self.q[joint]:.6f})")
            yield

    def _wait(self, seconds):
        t0 = self.t
        while self.t - t0 < seconds - 1e-9:
            yield

    def _seq_present(self, end_mode):
        yield from self._move("gate", self.gate_travel)
        yield from self._move("x", 0.0)                 # centred before the stage leaves the chamber
        yield from self._move("y", -self.y_load)
        self.mode = end_mode

    def _seq_stow(self):
        yield from self._move("y", 0.0)
        yield from self._move("gate", 0.0)
        if self.plate_id:
            self._log("plate_removed", plate_id=self.plate_id)
        self.plate_id = ""
        self.mode = "READY"

    def _seq_load(self, plate_id):
        yield from self._move("y", 0.0)
        yield from self._move("gate", 0.0)
        yield from self._wait(0.3)
        seen = self.read_barcode()
        self._log("identity_read", where="stage_home", expected=plate_id, observed=seen)
        if seen != plate_id:
            self.identity_fault = {"expected": plate_id, "observed": seen}
            self._set_fault("plate_identity_mismatch", f"expected {plate_id}, read {seen!r}; plate held in the chamber; "
                                                       "quarantine recommended")
            return
        if not self.seated:
            self._set_fault("plate_misseated", f"plate not seated after retract: {self._gaps_mm()} mm")
            return
        self.plate_id = plate_id
        self.history.setdefault(plate_id, {})
        self._log("plate_loaded", plate_id=plate_id)
        self.mode = "LOADED"

    def _index(self, mag):
        target = math.radians(self.index_deg[mag])
        if abs(self.q["turret"] - target) > TOL["turret"]:
            yield from self._move("turret", target)
            yield from self._wait(0.1)
        if self.camera.objective_on_axis() != mag:
            raise RuntimeError(f"objective {mag} not indexed (turret at {math.degrees(self.q['turret']):.2f} deg)")

    def well_target(self, well):
        wx, wy = optics.well_center(well)
        ox, oy = self.calibration.get("stage_offset_mm", [0.0, 0.0])
        return -(wx + ox) * MM, -(wy + oy) * MM

    def _goto_well(self, well):
        tx, ty = self.well_target(well)
        if not (self.x_lim[0] <= tx <= self.x_lim[1] and -0.040 <= ty <= self.y_max):
            raise RuntimeError(f"well {well} outside the stage range")
        yield from self._move("y", ty)
        yield from self._move("x", tx)
        yield from self._wait(0.05)

    def _expose(self, plate_id, well, exposure_ms, led_level, purpose):
        """Switch the LED on, integrate for exposure_ms of simulated time, read out, LED off."""
        self._led(led_level)
        yield from self._wait(0.02)
        yield from self._wait(exposure_ms / 1000.0)
        img, truth = self.camera.capture(exposure_ms)
        led_rb = self.led_level_readback()
        self._led(0.0)
        h = self.history.setdefault(plate_id, {}).setdefault(well, {"exposures": 0, "light_dose_rel_ms": 0.0,
                                                                    "autofocus_frames": 0})
        h["exposures"] += 1
        h["light_dose_rel_ms"] = round(h["light_dose_rel_ms"] + led_level * exposure_ms, 3)
        if purpose == "autofocus":
            h["autofocus_frames"] += 1
        self._frame = (img, truth, led_rb)

    def _score(self, img):
        s = self.calibration["sensor"]
        return optics.focus_score(img, s["gain_e_per_adu"], s["read_noise_e"])

    def _autofocus(self, plate_id, well, mag, exposure_ms, led_level):
        """Image-based autofocus: coarse sweep, fine sweep, parabolic peak. Uses images and encoders only."""
        seed = self.focus_memory.get((plate_id, mag))
        step = 30e-6 if mag == "10x" else 60e-6
        half = 3 * step if seed is not None else 300e-6
        centre = seed if seed is not None else 0.0
        curve, audit = [], []

        def sweep(zs):
            for z in zs:
                z = float(np.clip(z, *self.focus_lim))
                yield from self._move("focus", z)
                yield from self._wait(0.02)
                yield from self._expose(plate_id, well, exposure_ms, led_level, "autofocus")
                curve.append((self.q["focus"], self._score(self._frame[0])))
                audit.append(self._frame[1].get("defocus_um"))   # optics ground truth, audit only

        yield from sweep(centre + np.arange(-half, half + 1e-9, step))
        zbest, sbest = max(curve, key=lambda c: c[1])
        floor = self.calibration["objectives"][mag]["focus_floor"]
        run = {"t": round(self.t, 3), "plate_id": plate_id, "well": well, "magnification": mag,
               "seeded": seed is not None}
        if sbest < 0.5 * floor:   # nothing to focus on: report and keep the sweep for the audit trail
            run.update(ok=False, reason="no focus found (no structure above the noise in the sweep range)",
                       curve=[(round(z / MM, 4), round(s, 4)) for z, s in curve])
            self.autofocus_runs.append(run)
            self._log("autofocus_failed", well=well, best_score=round(sbest, 4))
            return None
        fine = step / 6
        yield from sweep(zbest + np.arange(-step, step + 1e-9, fine))
        pts = sorted(c for c in curve if abs(c[0] - zbest) <= step + 1e-9)
        z = np.array([c[0] for c in pts])
        s = np.array([c[1] for c in pts])
        zf = float(z[int(np.argmax(s))])
        top = s >= 0.6 * s.max()
        if top.sum() >= 4:                              # least-squares parabola over the top of the focus curve
            a, b, _ = np.polyfit((z[top] - zf) / fine, s[top], 2)
            if a < 0:
                zf = float(np.clip(zf - b / (2 * a) * fine, z[top].min(), z[top].max()))
        yield from self._move("focus", float(zf))
        yield from self._wait(0.03)
        self.focus_memory[(plate_id, mag)] = float(zf)
        run.update(ok=True, focus_mm=round(zf / MM, 5), best_score=round(float(s.max()), 4), frames=len(curve),
                   curve=[(round(zz / MM, 4), round(ss, 4)) for zz, ss in curve],
                   truth_defocus_um_audit=audit)
        self.autofocus_runs.append(run)
        self._log("autofocus_done", well=well, magnification=mag, focus_mm=run["focus_mm"], frames=len(curve))
        return run

    def _seq_image(self, plate_id, wells, exposure_ms, mag, policy, led_level, binding_id, purpose="measurement"):
        yield from self._index(mag)
        for well in wells:
            yield from self._goto_well(well)
            af = None
            if policy == "autofocus" or (policy == "stored" and (plate_id, mag) not in self.focus_memory):
                af = yield from self._autofocus(plate_id, well, mag, exposure_ms, led_level)
            elif policy == "stored":
                yield from self._move("focus", self.focus_memory[(plate_id, mag)])
            elif isinstance(policy, (tuple, list)) and policy[0] == "fixed":
                yield from self._move("focus", float(np.clip(policy[1] * MM, *self.focus_lim)))
            yield from self._expose(plate_id, well, exposure_ms, led_level, "acquisition")
            img, truth, led_rb = self._frame
            self._record(plate_id, well, img, truth, led_rb, exposure_ms, mag, policy, led_level, af, binding_id, purpose)
        self.mode = "LOADED"

    # ------------------------------------------------------------------ evidence
    def _record(self, plate_id, well, img, truth, led_rb, exposure_ms, mag, policy, led_level, af, binding_id,
                purpose="measurement"):
        cal = self.calibration
        score = self._score(img)
        floor = cal["objectives"].get(mag, CALIBRATION_DEMO["objectives"][mag])["focus_floor"]
        hist = optics.histogram_stats(img)
        focus_ok = score >= floor and (af is None or (af["ok"] and score >= AF_REL * af["best_score"]))
        if af is not None and not af["ok"]:
            focus_ok = False
        hist_ok = HIST_OK["mean_fs"][0] <= hist["mean_fs"] <= HIST_OK["mean_fs"][1] and \
            hist["saturated_fraction"] <= HIST_OK["saturated_max"]
        gate_closed = self.q["gate"] < 0.001
        led_ok = abs(led_rb - led_level) < 0.01
        tx, ty = self.well_target(well)
        stage_err = math.hypot(self.q["x"] - tx, self.q["y"] - ty) / MM
        monitors = [
            dict(name="plate_identity", passed=plate_id == self.plate_id,
                 observation="barcode read at the stage home position matched the SDT plate id at load"
                 if plate_id == self.plate_id else "plate id differs from the verified plate", value=self.plate_id),
            dict(name="plate_seating", passed=self.seated,
                 observation="4 nest seat sensors " + ("confirm seating" if self.seated else "do not confirm seating"),
                 value=self._gaps_mm()),
            dict(name="focus_quality", passed=bool(focus_ok),
                 observation=("focus score passed threshold" if focus_ok else "focus score below validity threshold")
                 + f" (floor {floor}" + (f", >= {AF_REL} x autofocus best {af['best_score']}" if af and af.get("ok")
                                         else "") + ")", value=round(score, 4)),
            dict(name="illumination_state", passed=bool(led_ok and gate_closed and hist_ok),
                 observation=f"LED {led_rb:.2f} of commanded {led_level:.2f}; gate {'closed' if gate_closed else 'OPEN'};"
                             f" histogram mean {hist['mean_fs']} FS, saturated {hist['saturated_fraction']}"
                             + ("" if hist_ok else " (outside the usable range)"), value=hist),
            dict(name="calibration_state", passed=self.calibration_valid,
                 observation=f"{cal['calibration_id']} {cal.get('status', 'valid')}, valid until {cal['valid_until']} "
                             f"({cal['source']})",
                 value=cal["calibration_id"]),
        ]
        n = len(self.acquisitions)
        stem = f"L17_{plate_id}_{well}_{mag}_{n:03d}" + ("_qc" if purpose == "qc" else "")
        ref = self._export(stem, img, {
            "plate_id": plate_id, "well_id": well, "timestamp_s": round(self.t, 3),
            "settings": {"exposure_ms": exposure_ms, "magnification": mag, "na": self.objectives[mag]["na"],
                         "pixel_um": cal["objectives"].get(mag, {}).get("pixel_um"), "led_level": led_level,
                         "focus_policy": str(policy), "focus_z_mm": round(self.q["focus"] / MM, 5),
                         "stage_xy_mm": [round(self.q["x"] / MM, 4), round(self.q["y"] / MM, 4)],
                         "stage_error_um": round(stage_err * 1e3, 1)},
            "purpose": purpose, "focus_score": round(score, 4), "histogram": hist, "calibration_id": cal["calibration_id"],
            "monitors": monitors, "analysis_version": "l17_optics focus/histogram v1",
            "imaging_history": dict(self.history[plate_id][well]),
            "autofocus": None if af is None else {k: af[k] for k in af if k != "curve"}})
        rec = {"t": round(self.t, 3), "plate_id": plate_id, "well_id": well, "magnification": mag,
               "exposure_ms": exposure_ms, "led_level": led_level, "focus_policy": str(policy),
               "measurement_binding_id": binding_id, "focus_score": round(score, 4), "histogram": hist,
               "monitors": monitors, "raw_image_reference": ref, "command_completed": True,
               "imaging_history": dict(self.history[plate_id][well]), "purpose": purpose,
               "calibration_id": cal["calibration_id"],
               "valid": purpose == "measurement" and all(m["passed"] for m in monitors)}
        self.acquisitions.append(rec)
        self.images[n] = img
        for k in [k for k in self.images if k < n - 40]:      # keep the recent raw arrays in memory (files hold all)
            del self.images[k]
        self.truth.append({"acquisition": n, **truth})
        self._write("state:focus_score", round(score, 4))
        self._write("state:exposure_ms", float(exposure_ms))
        self._log("image_acquired", well=well, magnification=mag, focus_score=round(score, 4), valid=rec["valid"],
                  raw_image_reference=ref)

    def _export(self, stem, img, meta):
        """export_raw_image: 16-bit PNG + JSON sidecar; rejected images are kept (audit trail)."""
        sha = hashlib.sha256(np.ascontiguousarray(img).tobytes()).hexdigest()
        if not self.image_dir:
            return f"evidence://l17/{stem}.raw#sha256={sha[:16]}"
        from PIL import Image
        os.makedirs(self.image_dir, exist_ok=True)
        path = os.path.join(self.image_dir, f"{stem}.png")
        Image.fromarray(img.astype(np.uint16)).save(path)
        # 8-bit preview for viewing: the 12-bit ADC range mapped linearly to 0-255 (the raw file is the evidence;
        # a 16-bit PNG of 12-bit values looks nearly black in ordinary viewers)
        Image.fromarray(np.clip(img.astype(float) * (255.0 / 4095.0), 0, 255).astype(np.uint8)).save(
            os.path.join(self.image_dir, f"{stem}_view.png"))
        with open(os.path.join(self.image_dir, f"{stem}.json"), "w") as f:
            json.dump({**meta, "raw_image_sha256": sha, "format": "PNG 16-bit, 12-bit ADC values",
                       "preview": f"{stem}_view.png (8-bit, linear 0-4095)"}, f, indent=2, default=str)
        return f"evidence://l17/{stem}.png#sha256={sha[:16]}"

    # ------------------------------------------------------------------ loop / outputs
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
                self._led(0.0)
                self._set_fault("device_fault", str(exc))
        self._outputs()

    def _set(self, joint, value):
        self.tgt[joint] = value
        self.art.set_dof_position_targets(np.array([[value]], dtype=np.float32), dof_indices=[self.dof[joint]])

    def _led(self, level):
        self._led_level = level
        self.led.Set(float(level * LED_FULL))
        self._write("inputs:emissive_intensity", LED_EMISSIVE * level, f"{self.root}/Looks/IllumLed/Shader")

    def _gaps_mm(self):
        return [None if g is None else round(g * 1e3, 3) for g in self.seat_gaps]

    def _outputs(self):
        g = self.q["gate"]
        self._write("state:plate_id", self.plate_id)
        self._write("state:door", "open" if g > self.gate_travel - 0.002 else ("closed" if g < 0.001 else "moving"))
        self._write("state:stage_pose", self.stage_pose())
        self._write("state:magnification", self.camera.objective_on_axis() or "none")
        self._write("state:illumination", "on" if self._led_level > 0 else "off")
        self._write("state:calibration_valid", self.calibration_valid)
        self._write("state:mode", self.mode)
        self._write("state:fault", self.fault)
        for lens, on in (("LensGreen", self.mode in ("READY", "PRESENTED_EMPTY", "PRESENTED_LOADED", "LOADED")),
                         ("LensAmber", self.mode == "BUSY"), ("LensRed", self.mode == "FAULT")):
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

    def _log(self, event, **details):
        self.events.append({"t": round(self.t, 4), "event": event, "mode": self.mode, **details})

    def _start(self, cmd, gen, **details):
        self.mode = "BUSY"
        self._job = gen
        self._log(f"{cmd}_accepted", **details)
        return Result(True)

    def _refuse(self, cmd, reason, fault_signal=None):
        self._log(f"{cmd}_refused", reason=reason)
        if fault_signal:
            self._log("fault_signal", fault=fault_signal)
        return Result(False, reason)

    def _set_fault(self, fault, detail):
        self.fault, self.mode = fault, "FAULT"
        self._job = None
        for k in JOINTS:
            self._set(k, self.q[k])
        self._log("fault", fault=fault, detail=detail)

    def busy(self):
        return self.mode == "BUSY"

    def snapshot(self):
        return {"mode": self.mode, "fault": self.fault, "plate_id": self.plate_id, "plate_on_nest": self.plate_on_nest,
                "seated": self.seated, "stage_pose": self.stage_pose(),
                "q_mm": {k: round(v / MM, 4) for k, v in self.q.items() if k != "turret"},
                "turret_deg": round(math.degrees(self.q["turret"]), 2), "objective": self.camera.objective_on_axis()}

    def save_events(self, path):
        with open(path, "w") as f:
            json.dump({"component": "L17", "prim": self.root, "events": self.events,
                       "autofocus_runs": self.autofocus_runs, "imaging_history": self.history}, f, indent=2,
                      default=str)


def region_wells(region: str):
    """'B02:B04' or 'B2:C3' -> wells in the rectangle, row-major."""
    a, b = (optics.parse_well(x) for x in region.split(":"))
    if a is None or b is None:
        return [None]
    rows = optics.ROWS[min(optics.ROWS.index(a[0]), optics.ROWS.index(b[0])):
                       max(optics.ROWS.index(a[0]), optics.ROWS.index(b[0])) + 1]
    c0, c1 = sorted((int(a[1:]), int(b[1:])))
    return [f"{r}{c:02d}" for r in rows for c in range(c0, c1 + 1)]
