"""Runtime controller for robot-loaded plate stores: L09 Automated Plate Hotel (this class), base of L10.

PlateStoreController reads its geometry (park height, travels, frame names) from the asset's handler:*
attributes, so any assets/common/plate_store.py device can use it; twin/l10_controller.py extends it.

Implements sdt/components/L09_PlateHotel.yaml on top of assets/l09/l09.usda:

  actions        present_for_load, store(plate_id, slot), retrieve(plate_id), stow, reserve(slot, plate_id),
                 present_for_removal(reason): after an identity fault, present the plate for removal to H4
  constraints    one plate per slot; SDT plate ID must agree with the identity READ at transfer; transfer nest
                 clear before robot placement; door/interlock must permit access
  monitors       barcode at the stowed nest, per-slot occupancy rays, nest seat sensors, gate/door/shuttle
  faults         slot_identity_mismatch (stop, keep pre-fault inventory, recommend quarantine),
                 double_occupancy_or_jam (stop, require service), transfer_nest_not_clear (block placement),
                 service door open (handler halted until closed)

The internal handler is physically simulated: ramped joint trajectories for gate, shuttle, lift and fork; a
plate is moved only by the fork tine under it. Each internal sequence is a generator advanced once per
physics step by update(); while the service door is open the generator is not advanced and the axes hold.
Sensing uses simulated state only: joint positions (tensor API) and PhysX raycasts; identity comes from the
plate prim that the barcode ray actually hits (attribute labware:barcode), never from the slot address.
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

MM = 0.001
JOINTS = {"gate": "GateSlide", "shuttle": "ShuttleSlide", "lift": "LiftSlide", "fork": "ForkSlide",
          "door": "ServiceDoorHinge"}
SPEED = {"gate": 0.10, "shuttle": 0.12, "lift": 0.08, "fork": 0.06}   # m/s, ramped targets (plate on tine: gentle)
TOL = 0.0004
MOVE_TIMEOUT_S = 6.0
SEAT_GAP_OK = 0.0004
LIGHT_ON = 3000.0


@dataclass
class Result:
    accepted: bool
    reason: str = ""


@dataclass
class PlateStoreController:
    stage: Usd.Stage
    root: str
    dt: float = 1.0 / 240
    t: float = 0.0
    mode: str = "READY"   # READY | PRESENTED_EMPTY | PRESENTED_LOADED | BUSY | FAULT
    fault: str = ""
    events: list = field(default_factory=list)

    def __post_init__(self):
        self.prim = self.stage.GetPrimAtPath(self.root)
        g = lambda k: float(self.prim.GetAttribute(k).Get())  # noqa: E731
        self.n_slots = int(self.prim.GetAttribute("sdt:slotCount").Get())
        self.tine_ref, self.fork_travel = g("handler:tineRefZ_mm") * MM, g("handler:forkTravel_mm") * MM
        self.ledge0, self.pitch, self.seat_z = g("handler:ledge0_mm") * MM, g("handler:pitch_mm") * MM, g("handler:seatZ_mm") * MM
        self.park_z = g("handler:parkTineZ_mm") * MM
        fn = dict(kv.split("=") for kv in self.prim.GetAttribute("handler:frameNames").Get().split(";"))
        self.slots_frame = fn["slots"]
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

        self.seat_local = [local(f"Shuttle/seat_sensor_{i}") for i in range(4)]
        self.reader = local("barcode_reader")
        self.slot_sensors = [local(f"{self.slots_frame}/slot_{k:02d}/occupancy_sensor") for k in range(self.n_slots)]
        self.ex = self._dir((1, 0, 0))
        self.ey = self._dir((0, 1, 0))
        self.ez = self._dir((0, 0, 1))
        q = self.art.get_dof_positions().numpy()[0]
        self.tgt = {k: float(q[i]) for k, i in self.dof.items()}
        self.travel = {"gate": g("handler:gateTravel_mm") * MM, "shuttle": g("handler:shuttleTravel_mm") * MM}
        self.inventory = [""] * self.n_slots
        self.reserved = {}
        self.identity_fault = None   # {slot, expected, observed} of the last slot_identity_mismatch
        self.unaccounted = {}        # plate_id -> record: the inventory placed it here, but it was not found
        self._job = None
        self._door_halt = False
        self._written = {}
        self.read_sensors()

    # ------------------------------------------------------------------ geometry helpers
    def _dir(self, v):
        d = np.array(self.to_world.TransformDir(Gf.Vec3d(*v)))
        return d / np.linalg.norm(d)

    def _world(self, p):
        return np.array(self.to_world.Transform(Gf.Vec3d(*map(float, p))))

    def ledge(self, k):
        return self.ledge0 + k * self.pitch

    def lift_q(self, tine_top_z):
        return tine_top_z - self.tine_ref

    def _ray(self, origin_local, direction, dist):
        """Closest hit that is not part of L09 itself -> (distance, plate root prim) or (None, None)."""
        hits = []

        def report(h):
            if not h.collision.startswith(self.root + "/"):
                hits.append((h.distance, h.collision))
            return True

        self.sq.raycast_all(carb.Float3(*self._world(origin_local)), carb.Float3(*direction), dist, report)
        if not hits:
            return None, None
        d, path = min(hits)
        p = self.stage.GetPrimAtPath(path)
        while p and p.GetPath() != p.GetPath().GetParentPath() and not p.GetAttribute("labware:barcode"):
            p = p.GetParent()
        return d, (p if p and p.GetAttribute("labware:barcode") else None)

    # ------------------------------------------------------------------ sensing
    def read_sensors(self):
        q = self.art.get_dof_positions().numpy()[0]
        self.q = {k: float(q[i]) for k, i in self.dof.items()}
        self.door_open = math.degrees(self.q["door"]) > 2.0
        shift = np.array([0.0, -self.q["shuttle"], 0.0])
        gaps = []
        for s in self.seat_local:
            d, _ = self._ray(s + shift - [0, 0, 0], self.ez, 0.015)
            gaps.append(None if d is None else d - 0.001)
        self.seat_gaps = gaps
        self.plate_on_nest = any(g is not None for g in gaps)
        self.seated = all(g is not None and g < SEAT_GAP_OK for g in gaps)
        self.slot_occupied = [self._ray(s, -self.ey, 0.04)[0] is not None for s in self.slot_sensors]

    def read_barcode(self):
        """Identity actually observed at the stowed nest: the barcode of the plate the reader's ray hits."""
        if self.q["shuttle"] > 0.001:
            return None
        _, plate = self._ray(self.reader, self.ex, 0.06)
        return plate.GetAttribute("labware:barcode").Get() if plate else None

    # ------------------------------------------------------------------ executive-facing commands
    def present_for_load(self) -> Result:
        if self.mode != "READY":
            return self._refuse("present_for_load", f"mode {self.mode}")
        if self.plate_on_nest:
            return self._refuse("present_for_load", "transfer_nest_not_clear", fault="transfer_nest_not_clear")
        return self._start("present_for_load", self._seq_present("PRESENTED_EMPTY"))

    def reserve(self, slot: int, plate_id: str) -> Result:
        if not 0 <= slot < self.n_slots:
            return self._refuse("reserve", f"no slot {slot}")
        if self.inventory[slot] or self.slot_occupied[slot]:
            return self._refuse("reserve", f"slot {slot} occupied")
        if self.reserved.get(slot, plate_id) != plate_id:
            return self._refuse("reserve", f"slot {slot} reserved for {self.reserved[slot]}")
        self.reserved[slot] = plate_id
        return self._ok("reserve", slot=slot, plate_id=plate_id)

    def store(self, plate_id: str, slot: int) -> Result:
        """store_plate: identity verified at transfer, slot reserved/empty, transfer interface ready."""
        if self.mode not in ("PRESENTED_EMPTY", "READY"):
            return self._refuse("store", f"mode {self.mode}")
        if not self.seated:
            return self._refuse("store", "plate not seated on the transfer nest")
        if not 0 <= slot < self.n_slots:
            return self._refuse("store", f"no slot {slot}")
        if self.inventory[slot] or self.slot_occupied[slot]:
            return self._refuse("store", f"slot {slot} occupied", event="double_occupancy_prevented")
        if self.reserved.get(slot, plate_id) != plate_id:
            return self._refuse("store", f"slot {slot} reserved for {self.reserved[slot]}")
        if plate_id in self.inventory:
            return self._refuse("store", f"{plate_id} already stored in slot {self.inventory.index(plate_id)}")
        return self._start("store", self._seq_store(plate_id, slot), plate_id=plate_id, slot=slot)

    def retrieve(self, plate_id: str) -> Result:
        """retrieve_plate: inventory confirms location, transfer nest empty, device healthy."""
        if self.mode != "READY":
            return self._refuse("retrieve", f"mode {self.mode}")
        if plate_id not in self.inventory:
            return self._refuse("retrieve", f"{plate_id} not in inventory")
        if self.plate_on_nest:
            return self._refuse("retrieve", "transfer_nest_not_clear", fault="transfer_nest_not_clear")
        slot = self.inventory.index(plate_id)
        if not self.slot_occupied[slot]:
            return self._refuse("retrieve", f"slot {slot} reads empty but inventory holds {plate_id}",
                                fault="inventory_inconsistent")
        return self._start("retrieve", self._seq_retrieve(plate_id, slot), plate_id=plate_id, slot=slot)

    def stow(self) -> Result:
        if self.mode not in ("PRESENTED_EMPTY", "PRESENTED_LOADED"):
            return self._refuse("stow", f"mode {self.mode}")
        if self.plate_on_nest:
            return self._refuse("stow", "plate on nest: store it or remove it")
        return self._start("stow", self._seq_stow("READY"))

    def present_for_removal(self, reason: str) -> Result:
        """Identity-fault recovery (retrieve/store failure routing: H4 quarantine if identity unresolved).

        After slot_identity_mismatch the plate is held on the stowed nest with the handler parked. This presents it
        so the robot can take it to H4. On a retrieve mismatch the slot is physically empty now: its inventory entry
        is cleared and the plate the inventory expected there is recorded as unaccounted for (location unknown).
        """
        f = self.identity_fault
        if self.mode != "FAULT" or self.fault != "slot_identity_mismatch" or f is None:
            return self._refuse("present_for_removal", f"mode {self.mode}, fault {self.fault!r}")
        if not (self.plate_on_nest and self.seated):
            return self._refuse("present_for_removal", "no seated plate on the stowed nest")
        if not self.parked():
            return self._refuse("present_for_removal", "handler not parked: service required")
        if f["slot"] is not None and self.inventory[f["slot"]] == f["expected"] and not self.slot_occupied[f["slot"]]:
            self.unaccounted[f["expected"]] = {"t": round(self.t, 2), "last_inventory_slot": f["slot"],
                                               "found_instead": f["observed"]}
            self.inventory[f["slot"]] = ""
            self._log("inventory_reconciled", slot=f["slot"], expected=f["expected"], observed=f["observed"],
                      expected_plate_location="unknown")
        self._log("fault_handled", fault=self.fault, route="present_for_removal", reason=reason)
        self.fault, self.identity_fault = "", None
        return self._start("present_for_removal", self._seq_present("PRESENTED_LOADED"), observed=f["observed"])

    def reset_fault(self, by: str) -> Result:
        """Operator reset: re-home the handler to park, unless the tine may be under a plate on the nest."""
        if self.mode != "FAULT":
            return self._refuse("reset_fault", "no fault")
        if abs(self.q["fork"]) < 0.01 and self.q["lift"] < self.lift_q(self.seat_z + 0.016) and self.plate_on_nest:
            return self._refuse("reset_fault", "tine may be under the nest plate: service required")
        self._log("fault_reset", by=by, fault=self.fault)
        self.fault = ""
        return self._start("rehome", self._seq_rehome())

    # ------------------------------------------------------------------ sequences (generators)
    def _move(self, joint, target):
        speed = SPEED[joint]
        start = self.tgt[joint]
        n = max(1, int(abs(target - start) / speed / self.dt))
        for i in range(1, n + 1):
            self._set(joint, start + (target - start) * i / n)
            yield
        t0 = self.t
        while abs(self.q[joint] - target) > TOL:
            if self.t - t0 > MOVE_TIMEOUT_S:
                raise RuntimeError(f"{joint} did not reach {target * 1e3:.1f} mm (at {self.q[joint] * 1e3:.1f} mm)")
            yield

    def _wait(self, seconds):
        t0 = self.t
        while self.t - t0 < seconds:
            yield

    def parked(self):
        return abs(self.q["lift"] - self.lift_q(self.park_z)) < 0.001 and abs(self.q["fork"]) < 0.001

    def _seq_rehome(self):
        yield from self._to_park()
        self.mode = "READY" if self.q["shuttle"] < 0.001 else "PRESENTED_EMPTY"

    def _seq_present(self, end_mode):
        if not self.parked():
            yield from self._to_park()
        yield from self._move("gate", self.travel["gate"])
        yield from self._move("shuttle", self.travel["shuttle"])
        self.mode = end_mode

    def _seq_stow(self, end_mode):
        if not self.parked():
            yield from self._to_park()
        yield from self._move("shuttle", 0.0)
        yield from self._move("gate", 0.0)
        self.mode = end_mode

    def _to_park(self):
        yield from self._move("lift", self.lift_q(self.park_z))
        yield from self._move("fork", 0.0)

    def _seq_store(self, plate_id, slot):
        if self.q["shuttle"] > 0.001:
            yield from self._seq_stow("BUSY")
        yield from self._wait(0.3)
        seen = self.read_barcode()
        self._log("identity_read", where="transfer_nest", expected=plate_id, observed=seen)
        if seen != plate_id:
            self._set_fault("slot_identity_mismatch",
                            f"expected {plate_id}, read {seen!r}; plate held on the stowed nest; quarantine recommended")
            self.identity_fault = {"slot": None, "expected": plate_id, "observed": seen}
            return
        L = self.ledge(slot)
        yield from self._move("fork", self.fork_travel)            # tine to the slot side, above the nest plate
        yield from self._move("lift", self.lift_q(self.tine_ref))  # down to nest level, behind the nest
        yield from self._move("fork", 0.0)                         # slide under the plate (nest channel)
        yield from self._move("lift", self.lift_q(L + 0.004))      # lift it out of the nest, up the channel
        yield from self._move("fork", self.fork_travel)            # into the slot, 4 mm above the ledges
        yield from self._move("lift", self.lift_q(L - 0.003))      # set it down on the ledges
        yield from self._move("fork", 0.0)                         # withdraw the tine
        yield from self._to_park()
        yield from self._wait(0.3)
        if not self.slot_occupied[slot]:
            self._set_fault("double_occupancy_or_jam", f"slot {slot} reads empty after store")
            return
        self.inventory[slot] = plate_id
        self.reserved.pop(slot, None)
        self._log("stored", plate_id=plate_id, slot=slot)
        self.mode = "READY"

    def _seq_retrieve(self, plate_id, slot):
        L = self.ledge(slot)
        yield from self._move("lift", self.lift_q(L - 0.003))      # tine below the plate, in the channel
        yield from self._move("fork", self.fork_travel)            # under the plate
        yield from self._move("lift", self.lift_q(L + 0.004))      # lift it off the ledges
        yield from self._move("fork", 0.0)                         # out into the channel
        yield from self._move("lift", self.lift_q(self.tine_ref))  # lower it onto the nest
        yield from self._move("fork", self.fork_travel)            # slide the tine out behind the nest
        yield from self._move("lift", self.lift_q(self.park_z))
        yield from self._move("fork", 0.0)                         # park (over the plate, in the channel)
        yield from self._wait(0.3)
        seen = self.read_barcode()
        self._log("identity_read", where="transfer_nest", expected=plate_id, observed=seen)
        if seen != plate_id:
            self._set_fault("slot_identity_mismatch",
                            f"slot {slot} held {seen!r}, inventory said {plate_id}; inventory kept as pre-fault")
            self.identity_fault = {"slot": slot, "expected": plate_id, "observed": seen}
            return
        if not self.seated:
            self._set_fault("double_occupancy_or_jam", f"retrieved plate not seated on the nest: {self.seat_gaps}")
            return
        self.inventory[slot] = ""
        self._log("retrieved", plate_id=plate_id, slot=slot)
        yield from self._seq_present("PRESENTED_LOADED")

    # ------------------------------------------------------------------ loop
    def update(self, dt=None):
        self.dt = dt or self.dt
        self.t += self.dt
        self.read_sensors()
        if self._job is not None:
            if self.door_open:
                if not self._door_halt:
                    self._door_halt = True
                    for k in ("gate", "shuttle", "lift", "fork"):
                        self._set(k, self.q[k])
                    self._log("handler_halted", reason="service door open")
            else:
                if self._door_halt:
                    self._door_halt = False
                    self._log("handler_resumed")
                try:
                    next(self._job)
                except StopIteration:
                    self._job = None
                except RuntimeError as exc:
                    self._job = None
                    self._set_fault("double_occupancy_or_jam", str(exc))
        self._outputs()

    # ------------------------------------------------------------------ outputs / provenance
    def _set(self, joint, value):
        self.tgt[joint] = value
        self.art.set_dof_position_targets(np.array([[value]], dtype=np.float32), dof_indices=[self.dof[joint]])

    def _start(self, cmd, gen, **details):
        self.mode = "BUSY"
        self._job = gen
        self._log(f"{cmd}_accepted", **details)
        return Result(True)

    def _outputs(self):
        self._write("state:inventory", list(self.inventory))
        self._write("state:reserved_slots", sorted(self.reserved))
        self._write("state:transfer_nest", "occupied" if self.plate_on_nest else "empty")
        self._write("state:door", "open" if self.door_open else "closed")
        gate_state = "open" if self.q["gate"] > self.travel["gate"] - 0.01 else ("closed" if self.q["gate"] < 0.001 else "moving")
        self._write("state:gate", gate_state)
        self._write("state:mode", self.mode)
        self._write("state:fault", self.fault)
        for lens, on in (("LensGreen", self.mode in ("READY", "PRESENTED_EMPTY", "PRESENTED_LOADED")),
                         ("LensAmber", self.mode == "BUSY"),
                         ("LensRed", self.mode == "FAULT" or self.door_open or self._extra_red())):
            self._write("inputs:emissive_intensity", LIGHT_ON if on else 0.0, f"{self.root}/Looks/{lens}/Shader")

    def _extra_red(self) -> bool:
        """Subclass hook: additional conditions that light the red lamp (e.g. L10 environment alarms)."""
        return False

    def _write(self, attr, value, path=None):
        key = (path or self.root, attr)
        if self._written.get(key) == value:
            return
        prim = self.stage.GetPrimAtPath(path) if path else self.prim
        a = prim.GetAttribute(attr)
        if a:
            a.Set(value)
            self._written[key] = value

    def _log(self, event, **details):
        self.events.append({"t": round(self.t, 4), "event": event, "mode": self.mode, **details})

    def _ok(self, cmd, **details):
        self._log(f"{cmd}_accepted", **details)
        return Result(True)

    def _refuse(self, cmd, reason, event=None, fault=None):
        self._log(event or f"{cmd}_refused", reason=reason)
        if fault:
            self._log("fault_signal", fault=fault)
        return Result(False, reason)

    def _set_fault(self, fault, detail):
        self.fault, self.mode = fault, "FAULT"
        self._job = None
        for k in ("gate", "shuttle", "lift", "fork"):
            self._set(k, self.q[k])
        self._log("fault", fault=fault, detail=detail)

    def snapshot(self):
        return {"mode": self.mode, "fault": self.fault, "inventory": list(self.inventory),
                "slot_occupied": [k for k, o in enumerate(self.slot_occupied) if o], "plate_on_nest": self.plate_on_nest,
                "seated": self.seated, "q_mm": {k: round(v * 1e3, 2) for k, v in self.q.items() if k != "door"},
                "door_deg": round(math.degrees(self.q["door"]), 1)}

    def save_events(self, path):
        with open(path, "w") as f:
            json.dump({"component": "L09", "prim": self.root, "events": self.events}, f, indent=2)


L09Controller = PlateStoreController  # the plate hotel is the plain plate store
