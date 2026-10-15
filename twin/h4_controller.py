"""Runtime controller for the H4 Quarantine Station twin (Isaac Sim 6.x, PhysX), shuttle version.

Implements the SDT contract in sdt/components/H4_Quarantine.yaml on top of assets/h4/h4.usda:

  capabilities   isolate_sample, retain_invalid_run, prevent_reentry, release_by_authorization
  risk controls  mechanical lock (latch bolt in the door slot), software reservation,
                 authorization gate (software token AND key switch in RELEASE),
                 distinct visual status (red = quarantined, green = available)
  monitors       seat sensors (4 flush windows: plate flat and A1-oriented), chamber through-beam
                 (diverse occupancy check after stowing), lock state, door angle, shuttle position

Robot hand-off (R01 place_plate / retrieve_plate): the robot asks H4 to present_nest(); H4 opens
the door and extends the shuttle to transfer_nest; the robot places top-down (long-side grip);
quarantine_sample() checks seating, stows, closes and locks. A badly seated plate is refused so
the robot can reseat (R01 contract: "reseat; if still invalid, quarantine").

Interlocks (enforced here and, for door vs. shuttle, also by contact in the physics model):
shuttle extends only with the door open; door closes only with the shuttle stowed; the bolt
extends only with the door closed, settled and aligned.

Sensors are read from simulated state only: joint positions (PhysX articulation tensor API) and
PhysX scene-query raycasts. Outputs: joint drive targets, state:* / control:* attributes, the
status-light emission, and an append-only event list (the provenance sidecar).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

import carb
import numpy as np
from isaacsim.core.experimental.prims import Articulation
from omni.physx import get_physx_scene_query_interface
from pxr import Gf, Usd, UsdGeom

DOOR_OPEN_DEG = 100.0
DOOR_OPEN_MIN_DEG = 95.0       # shuttle may extend beyond this
DOOR_CLOSED_TOL_DEG = 1.0
DOOR_LATCH_TOL_DEG = 0.1       # slot clearance 0.6 mm at ~257 mm from the hinge ~ 0.13 deg
DOOR_SETTLE_S = 0.25
BOLT_TRAVEL_M = 0.0065
BOLT_TOL_M = 0.0005
SHUTTLE_TRAVEL_M = 0.150
SHUTTLE_TOL_M = 0.001
SEAT_GAP_OK_M = 0.0004         # all four windows must see the plate underside within 0.4 mm
SEAT_RANGE_M = 0.015
SEAT_WINDOW_DEPTH_M = 0.001    # sensor windows sit 1 mm below the seating plane
BUTTON_THRESHOLD_M = 0.002
KEY_RELEASE_DEG = 80.0
SEQUENCE_TIMEOUT_S = 8.0
LIGHT_ON = 3000.0

JOINTS = {"door": "DoorHinge", "bolt": "LatchSlide", "shuttle": "ShuttleSlide", "button": "button_joint",
          "key": "key_joint"}
AVAILABLE = ("READY", "PRESENTING", "PRESENTED", "STOWING")


@dataclass
class Result:
    accepted: bool
    reason: str = ""


@dataclass
class H4Controller:
    stage: Usd.Stage
    root: str
    t: float = 0.0
    mode: str = "READY"  # READY | PRESENTING | PRESENTED | STOWING | SECURING | QUARANTINED | RELEASING
    fault: str = ""
    events: list = field(default_factory=list)

    def __post_init__(self):
        self.prim = self.stage.GetPrimAtPath(self.root)
        self.art = Articulation(self.root)
        names = list(self.art.dof_names)
        missing = [j for j in JOINTS.values() if j not in names]
        if missing:
            raise RuntimeError(f"H4 articulation lacks joints {missing}; has {names}")
        self.dof = {k: names.index(v) for k, v in JOINTS.items()}
        self.sq = get_physx_scene_query_interface()
        # The Body is a fixed base, so authored poses of Body-fixed frames equal simulated ones.
        xc = UsdGeom.XformCache(Usd.TimeCode.Default())
        self.h4_to_world = xc.GetLocalToWorldTransform(self.prim)
        world_to_h4 = self.h4_to_world.GetInverse()

        def local(path):  # frame position in the H4 frame (shuttle frames: at the stowed rest pose)
            return np.array(world_to_h4.Transform(xc.GetLocalToWorldTransform(
                self.stage.GetPrimAtPath(f"{self.root}/{path}")).ExtractTranslation()))

        p0, p1 = self._world(local("beam_emitter")), self._world(local("beam_receiver"))
        d = p1 - p0
        self.beam = (carb.Float3(*p0), carb.Float3(*(d / np.linalg.norm(d))), float(np.linalg.norm(d)))
        self.seat_local = [local(f"Shuttle/seat_sensor_{i}") for i in range(4)]
        self.up = np.array(self.h4_to_world.TransformDir(Gf.Vec3d(0, 0, 1)))
        self.up /= np.linalg.norm(self.up)
        self.sample_id = self.reason = self.authorization = ""
        self._seq_started = 0.0
        self._aligned_since = None
        self._button_was_pressed = False
        self._written = {}
        self.read_sensors()
        self._apply_outputs()

    def _world(self, p_h4):
        return np.array(self.h4_to_world.Transform(Gf.Vec3d(*map(float, p_h4))))

    # ------------------------------------------------------------------ sensing
    def read_sensors(self):
        q = self.art.get_dof_positions().numpy()[0]
        self.door_deg = math.degrees(q[self.dof["door"]])
        self.bolt_m = float(q[self.dof["bolt"]])        # 0 = extended (locked), +6.5 mm = retracted
        self.shuttle_m = float(q[self.dof["shuttle"]])  # 0 = stowed, +150 mm = presented
        self.button_m = float(q[self.dof["button"]])    # 0 = rest, negative = pressed
        self.key_deg = math.degrees(q[self.dof["key"]])

        hit = self.sq.raycast_closest(*self.beam)
        self.beam_blocked = bool(hit.get("hit", False))
        self.seat_gaps = [self._seat_gap(p) for p in self.seat_local]
        gaps = [g for g in self.seat_gaps if g is not None]
        self.plate_on_nest = bool(gaps)
        self.seated = len(gaps) == 4 and max(gaps) < SEAT_GAP_OK_M

        self.door_closed = abs(self.door_deg) < DOOR_CLOSED_TOL_DEG
        self.door_open = self.door_deg > DOOR_OPEN_MIN_DEG
        self.stowed = self.shuttle_m < SHUTTLE_TOL_M
        self.presented = self.shuttle_m > SHUTTLE_TRAVEL_M - SHUTTLE_TOL_M
        self.bolt_extended = self.bolt_m < BOLT_TOL_M
        self.bolt_retracted = self.bolt_m > BOLT_TRAVEL_M - BOLT_TOL_M
        self.locked = self.bolt_extended and abs(self.door_deg) < 0.5  # bolt seated in the door slot
        self.key_position = "RELEASE" if self.key_deg > KEY_RELEASE_DEG else "LOCK"
        self.button_pressed = -self.button_m > BUTTON_THRESHOLD_M
        self.occupied = self.plate_on_nest or (self.stowed and self.beam_blocked)

    def _seat_gap(self, p_rest):
        """Distance from the seating plane to the plate underside above one window (None = no plate)."""
        origin = self._world(p_rest - np.array([0.0, self.shuttle_m, 0.0]))
        best = []

        def report(hit):
            if not hit.collision.startswith(self.root + "/"):  # ignore H4's own colliders
                best.append(hit.distance)
            return True

        self.sq.raycast_all(carb.Float3(*origin), carb.Float3(*self.up), SEAT_RANGE_M, report)
        return (min(best) - SEAT_WINDOW_DEPTH_M) if best else None

    # ------------------------------------------------------------------ commands (executive-facing)
    def present_nest(self) -> Result:
        """Open the door and extend the shuttle to transfer_nest for a robot place/pick."""
        if self.mode != "READY":
            return self._refuse("present_nest", f"mode {self.mode}")
        self._start("PRESENTING")
        self._target("door", math.radians(DOOR_OPEN_DEG))
        return self._ok("present_nest")

    def stow(self) -> Result:
        """Retract the shuttle and close the door without quarantining (e.g. after a pick)."""
        if self.mode != "PRESENTED":
            return self._refuse("stow", f"mode {self.mode}")
        if self.plate_on_nest:
            return self._refuse("stow", "plate on nest: use quarantine_sample or remove it")
        self._start("STOWING")
        self._target("shuttle", 0.0)
        return self._ok("stow")

    def quarantine_sample(self, sample_id: str, reason: str, preceding_anomalies: list | None = None) -> Result:
        """Contract action quarantine_sample: isolate an identified, correctly seated sample."""
        if self.mode != "PRESENTED":
            return self._refuse("quarantine_sample", f"nest not presented / capacity unavailable (mode {self.mode})")
        if not sample_id:
            return self._refuse("quarantine_sample", "sample identity or traceable surrogate unknown")
        if not reason:
            return self._refuse("quarantine_sample", "quarantine reason required")
        if not self.plate_on_nest:
            return self._refuse("quarantine_sample", "no sample detected on nest")
        if not self.seated:
            gaps = ["--" if g is None else f"{g * 1e3:.2f}" for g in self.seat_gaps]
            return self._refuse("quarantine_sample", f"plate not seated (seat gaps mm: {gaps}); reseat")
        self.sample_id, self.reason = sample_id, reason
        self._start("SECURING")
        self._target("shuttle", 0.0)
        return self._ok("quarantine_sample", sample_id=sample_id, reason=reason,
                        preceding_anomalies=preceding_anomalies or [])

    def release(self, authorization: str) -> Result:
        """Contract capability release_by_authorization: token AND physical key in RELEASE."""
        if self.mode != "QUARANTINED":
            return self._refuse("release", f"nothing to release (mode {self.mode})")
        if not authorization:
            return self._refuse("release", "authorization token missing", event="release_refused")
        if self.key_position != "RELEASE":
            return self._refuse("release", "key switch not in RELEASE", event="release_refused")
        self.authorization = authorization
        self._start("RELEASING")
        self._target("bolt", BOLT_TRAVEL_M)
        return self._ok("release", authorization=authorization, sample_id=self.sample_id)

    # ------------------------------------------------------------------ loop
    def update(self, dt: float):
        self.t += dt
        self.read_sensors()

        if self.button_pressed and not self._button_was_pressed:
            if self.mode == "READY":
                self.present_nest()
            elif self.mode == "PRESENTED" and not self.plate_on_nest:
                self.stow()
            else:
                self._log("door_request_refused", reason=f"mode {self.mode}", source="DOOR pushbutton")
        self._button_was_pressed = self.button_pressed

        m = self.mode
        if m in ("PRESENTING", "RELEASING"):
            if m == "RELEASING" and self.bolt_retracted and not self.door_open:
                self._target("door", math.radians(DOOR_OPEN_DEG))
            if self.door_open and (m == "PRESENTING" or self.bolt_retracted):
                self._target("shuttle", SHUTTLE_TRAVEL_M)  # interlock: only with the door open
            if self.presented:
                if m == "RELEASING":
                    self._log("released", sample_id=self.sample_id, authorization=self.authorization)
                self._set_mode("PRESENTED")
        elif m in ("STOWING", "SECURING"):
            if self.stowed:
                self._target("door", 0.0)  # interlock: door closes only with the shuttle stowed
            if m == "STOWING" and self.stowed and self.door_closed:
                self._set_mode("READY")
            if m == "SECURING":
                # extend the bolt only once the door has settled with its slot aligned; extending
                # while the door is still swinging jams the bolt against the door edge
                if self.stowed and abs(self.door_deg) < DOOR_LATCH_TOL_DEG:
                    self._aligned_since = self.t if self._aligned_since is None else self._aligned_since
                    if self.t - self._aligned_since >= DOOR_SETTLE_S:
                        self._target("bolt", 0.0)
                else:
                    self._aligned_since = None
                if self.locked:
                    if not self.beam_blocked:
                        self._set_fault("isolation_check: chamber beam clear after stowing a seated plate")
                    self._set_mode("QUARANTINED")
                    self._log("quarantined", sample_id=self.sample_id, reason=self.reason,
                              beam_confirms=self.beam_blocked)
        elif m == "QUARANTINED":
            if not self.locked:
                self._set_fault("isolation_breach: lock lost while quarantined")
            elif not self.beam_blocked or not self.plate_on_nest:
                self._set_fault("isolation_breach: sample not detected while quarantined")
        elif m == "PRESENTED" and self.sample_id and not self.plate_on_nest:
            self._log("sample_removed", sample_id=self.sample_id)
            self.sample_id = self.reason = self.authorization = ""

        if m in ("PRESENTING", "STOWING", "SECURING", "RELEASING") and self.t - self._seq_started > SEQUENCE_TIMEOUT_S:
            self._set_fault(f"sequence_timeout in {m}")
        self._apply_outputs()

    # ------------------------------------------------------------------ outputs
    def _target(self, joint: str, value: float):
        self.art.set_dof_position_targets(np.array([[value]], dtype=np.float32), dof_indices=[self.dof[joint]])

    def _start(self, mode):
        self._seq_started = self.t
        self._aligned_since = None
        self.mode = mode

    def _set_mode(self, mode):
        if mode != self.mode:
            self.mode = mode
            self._log("mode", to=mode)

    def _apply_outputs(self):
        quarantined = self.mode in ("SECURING", "QUARANTINED")
        self._write("state:mode", self.mode)
        self._write("state:fault", self.fault)
        self._write("state:occupied", self.occupied)
        self._write("state:locked", self.locked)
        self._write("state:sample_id", self.sample_id)
        self._write("state:reason", self.reason)
        self._write("state:release_authorization", self.authorization)
        self._write("state:door_angle_deg", round(self.door_deg, 1))
        self._write("control:pressed", self.button_pressed, f"{self.root}/Controls/DoorButton")
        self._write("control:position", self.key_position, f"{self.root}/Controls/KeySwitch")
        self._write("inputs:emissive_intensity", LIGHT_ON if quarantined or self.fault else 0.0,
                    f"{self.root}/Looks/LensRed/Shader")
        self._write("inputs:emissive_intensity", LIGHT_ON if self.mode in AVAILABLE and not self.fault else 0.0,
                    f"{self.root}/Looks/LensGreen/Shader")
        self._write("inputs:emissive_intensity", 400.0 if self.mode in ("READY", "PRESENTED") else 0.0,
                    f"{self.root}/Looks/ButtonLens/Shader")

    def _write(self, attr, value, path=None):
        key = (path or self.root, attr)
        if self._written.get(key) == value:
            return
        prim = self.stage.GetPrimAtPath(path) if path else self.prim
        a = prim.GetAttribute(attr)
        if a:
            a.Set(value)
            self._written[key] = value

    # ------------------------------------------------------------------ provenance
    def _log(self, event, **details):
        self.events.append({"t": round(self.t, 4), "event": event, "mode": self.mode, **details})

    def _ok(self, command, **details):
        self._log(f"{command}_accepted", **details)
        return Result(True)

    def _refuse(self, command, reason, event=None):
        self._log(event or f"{command}_refused", reason=reason)
        return Result(False, reason)

    def _set_fault(self, fault):
        if fault != self.fault:
            self.fault = fault
            self._log("fault", fault=fault)

    def snapshot(self) -> dict:
        keys = ("mode", "fault", "occupied", "plate_on_nest", "seated", "beam_blocked", "locked", "door_deg",
                "bolt_m", "shuttle_m", "key_position", "sample_id", "reason")
        out = {k: getattr(self, k) for k in keys}
        out["seat_gaps_mm"] = [None if g is None else round(g * 1e3, 3) for g in self.seat_gaps]
        return out

    def save_events(self, path):
        with open(path, "w") as f:
            json.dump({"component": "H4", "prim": self.root, "events": self.events}, f, indent=2)
