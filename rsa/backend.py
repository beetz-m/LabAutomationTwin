"""Symbolic execution backend: a world-state model of Cell 01 with fault injection (iteration 1; Isaac is iteration 2).

It plays the role of coraplex's simulated execution: leaves (motion and device-command designators) are executed
against a world state that holds the *truth* (which plate is in the slot, whether the imager is really calibrated,
whether the tip is still on). The executor only sees what a leaf returns: durations, monitor results, evidence and
belief updates. Physical preconditions are checked (a grasp at an empty seat fails), so the backend also tests the
plan library. Durations are the planner's (``dur``/``ddur``/``leg_part`` facts), so a fault-free run must reproduce
the clingo plan's trip durations.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, Optional

from .core import Command, Context, Designator, Failure, Motion

#: leaf -> duration kind in the planner's facts
KIND = dict(check_interlocks="check", verify_identity="identity", present="present", stow="stow",
            wait_environment="wait_env", store="store", load="load", image_well="image", validate="qc",
            tip_pick="tip_pick", aspirate="aspirate", dispense="dispense", tip_eject="tip_eject", autofocus="image")


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


class SymbolicWorld:
    name = "symbolic-world/0.1"

    def __init__(self, kb, plate: str = "P17", faults: Optional[Dict[str, Any]] = None, projection: bool = False):
        self.kb = kb
        self.faults = {} if projection else dict(faults or {})
        self.projecting = projection
        self.clock = 0.0
        self.t_h = 0.0
        home = kb.home().value
        self.home = home
        self.slot = {home: plate}                       # what is physically in the storage slot
        self.plate_at = {plate: f"slot:{home}"}
        self.shuttle = {a[1]: "stowed" for a in kb.q("has_shuttle", None)}
        self.pose = {r: ["park"] for r in sorted({a[1] for a in kb.q("serves", None, None)})}
        self.holding = {r: None for r in self.pose}
        self.tool = {a[1]: a[2] for a in kb.q("coupled", None, None)}
        self.calibrated = {a[1]: True for a in kb.q("calibrated", None)}
        self.loaded: Dict[str, Optional[str]] = {}
        self.tip: Dict[str, Optional[str]] = {}
        self.aspirated: Dict[str, Optional[tuple]] = {}
        self.dispensed = []
        self.images = []
        self.contained = {}
        self.interlocks_closed = kb.holds("interlocks_closed")
        self.env_ok = True
        self._tips_used = 0

    # ---------------------------------------------------------------------------------------------- helpers
    def projection(self, belief=None) -> "SymbolicWorld":
        """A fault-free world to project in. Built from the assistant's BELIEF, not from this world's truth (F12):
        a prediction may only use what the assistant has reason to hold."""
        return SymbolicWorld.from_belief(self.kb, belief, self.clock, self.t_h) if belief is not None else \
            SymbolicWorld(self.kb, projection=True)

    @classmethod
    def from_belief(cls, kb, belief, clock: float = 0.0, t_h: float = 0.0) -> "SymbolicWorld":
        w = cls(kb, projection=True)
        w.clock, w.t_h = clock, t_h
        w.slot, w.plate_at = {}, {}
        for k, (v, src, _) in belief.items.items():
            kind, _, key = k.partition(":")
            if v is None or v == "unknown":
                continue
            if kind == "plate_at":
                w.plate_at[key] = v
                if str(v).startswith("slot:"):
                    w.slot[v.split(":")[1]] = key
            elif kind == "shuttle":
                w.shuttle[key] = v
            elif kind == "pose":
                w.pose[key] = list(v)
            elif kind == "tool":
                w.tool[key] = v
            elif kind == "calibrated":
                w.calibrated[key] = bool(v)
            elif kind == "loaded":
                w.loaded[key] = v
        return w

    def initial_belief(self, belief, plate: str):
        kb = self.kb
        belief.set(f"plate_at:{plate}", f"slot:{self.home}", "inferred", "home + experiment ABox (plate P17 in L10)")
        for d in self.shuttle:
            belief.set(f"shuttle:{d}", "stowed", "assumed", "devices start stowed")
        for r in self.pose:
            belief.set(f"pose:{r}", ["park"], "assumed", "robots start parked")
        for r, t in self.tool.items():
            belief.set(f"tool:{r}", t, "inferred", f"coupled({r},{t})")
        for a in kb.q("requires_tool", None, None):
            if a[1] not in self.tool:
                belief.set(f"tool:{a[1]}", None, "assumed", "no coupled fact")
        for a in kb.q("has_function", None, "imaging"):
            belief.set(f"calibrated:{a[1]}", kb.holds("calibrated", a[1]), "inferred",
                       f"{'calibrated' if kb.holds('calibrated', a[1]) else 'no calibrated'}({a[1]}) fact")

    def _session(self, ctx: Context) -> Optional[str]:
        for n in [ctx.node] + ctx.node.ancestors():
            if n.designator.category == "run_session":
                return n.designator.session
        return None

    def _fault(self, ctx: Context, name: str) -> Optional[dict]:
        f = self.faults.get(name)
        if f and f.get("session") in (None, self._session(ctx)) and f.get("count", 1) > 0:
            return f
        return None

    def _station_of_seat(self, seat: str) -> str:
        a = self.kb.one("seat", None, seat)
        return a[1] if a else seat

    def _duration(self, d: Designator, ctx: Context) -> float:
        kb = self.kb
        if isinstance(d, Motion):
            if d.primitive == "tool_couple":
                f = self._fault(ctx, "tool_changer_slow")
                return f["duration_s"] if f else kb.duration("tool_couple")
            return kb.duration(d.primitive, robot=d.robot)
        if d.command == "incubate":
            return 0.0
        return kb.duration(KIND.get(d.command, d.command), device=d.device)

    # ---------------------------------------------------------------------------------------------- execute
    def execute(self, d: Designator, ctx: Context) -> Dict[str, Any]:
        dur = self._duration(d, ctx)
        self.clock = round(self.clock + dur, 3)
        obs = dict(duration_s=round(dur, 2), monitors=[], evidence=[], belief={})
        fn = getattr(self, f"_{d.primitive}" if isinstance(d, Motion) else f"_c_{d.command}")
        try:
            fn(d, ctx, obs)
        except Failure as f:
            f.obs = obs                      # what was observed before the fault is evidence too
            raise
        return obs

    @staticmethod
    def _mon(obs, name, passed, observation):
        obs["monitors"].append(dict(name=name, passed=passed, observation=observation))

    @staticmethod
    def _ev(obs, kind, value):
        obs["evidence"].append(dict(kind=kind, value=value, sha256=_sha([kind, value])))

    # ---------------------------------------------------------------------------------------------- motions
    def _set_pose(self, r, p, obs):
        self.pose[r] = p
        obs["belief"][f"pose:{r}"] = (p, "observed")

    def _approach(self, d, ctx, obs):
        self._set_pose(d.robot, list(d.args[0]), obs)

    def _insert(self, d, ctx, obs):
        st = self._station_of_seat(d.args[0])
        if st in self.shuttle and self.shuttle[st] != "presented":
            raise Failure("collision_risk", f"{d.robot} inserting at {st} while its shuttle is {self.shuttle[st]}")
        self._set_pose(d.robot, ["seat", d.args[0]], obs)

    def _grasp(self, d, ctx, obs):
        seat = self.pose[d.robot][1] if self.pose[d.robot][0] == "seat" else None
        st = self._station_of_seat(seat) if seat else None
        plate = next((p for p, at in self.plate_at.items() if at == st), None)
        need = self.kb.tool_for(d.robot).value
        if need != "none" and self.tool.get(d.robot) != need[0]:
            raise Failure("tool_missing", f"{d.robot} has no {need[0]} coupled")
        if plate is None:
            self._mon(obs, "grasp_confirmed", False, f"no plate at {st}")
            raise Failure("grasp_failed", f"no plate at {st}")
        self.holding[d.robot] = plate
        self.plate_at[plate] = f"robot:{d.robot}"
        self._mon(obs, "grasp_confirmed", True, f"{plate} in gripper")
        obs["belief"][f"plate_at:{plate}"] = (f"robot:{d.robot}", "observed")

    def _lift(self, d, ctx, obs):
        p = self.pose[d.robot]
        self._set_pose(d.robot, ["appr", p[1]] if p[0] == "seat" else p, obs)

    def _transit(self, d, ctx, obs):
        self._set_pose(d.robot, list(d.args[1]), obs)

    def _place(self, d, ctx, obs):
        st = self._station_of_seat(d.args[0])
        if st in self.shuttle and self.shuttle[st] != "presented":
            raise Failure("collision_risk", f"{d.robot} placing at {st} while its shuttle is {self.shuttle[st]}")
        if self.holding[d.robot] is None:
            raise Failure("nothing_held", f"{d.robot} places without a plate")
        self._set_pose(d.robot, ["seat", d.args[0]], obs)

    def _release(self, d, ctx, obs):
        plate = self.holding[d.robot]
        st = self._station_of_seat(self.pose[d.robot][1])
        self.holding[d.robot] = None
        self.plate_at[plate] = st
        self._mon(obs, "seating_confirmed", True, f"{plate} seated at {st}")
        obs["belief"][f"plate_at:{plate}"] = (st, "observed")

    def _retract(self, d, ctx, obs):
        self._set_pose(d.robot, list(d.args[0]), obs)

    def _tool_couple(self, d, ctx, obs):
        f = self._fault(ctx, "tool_changer_slow")
        if f:
            f["count"] = f.get("count", 1) - 1
            self._mon(obs, "tool_frame_validity", True, f"coupled after {f['duration_s']} s (slow tool changer)")
        else:
            self._mon(obs, "tool_frame_validity", True, "tool frame valid")
        self.tool[d.robot] = d.args[0]
        obs["belief"][f"tool:{d.robot}"] = (d.args[0], "observed")

    # ---------------------------------------------------------------------------------------------- commands
    def _c_check_interlocks(self, d, ctx, obs):
        self._mon(obs, "route_clear", self.interlocks_closed, "interlocks closed" if self.interlocks_closed else "open")
        if not self.interlocks_closed:
            raise Failure("interlock_open", "enclosure interlock open")

    def _c_verify_identity(self, d, ctx, obs):
        f = self._fault(ctx, "identity_swap")
        if f:
            self.slot[d.device] = f["plate_in_slot"]
            self.plate_at = {k: v for k, v in self.plate_at.items() if v != f"slot:{d.device}"}
            self.plate_at[f["plate_in_slot"]] = f"slot:{d.device}"
            f["count"] = 0
        seen = self.slot.get(d.device)
        self._ev(obs, "barcode_read", dict(device=d.device, read=seen))
        obs["belief"]["identity_read"] = (seen, "observed")
        obs["belief"][f"plate_at:{seen}"] = (f"slot:{d.device}", "observed")
        ok = seen == d.expect
        self._mon(obs, "plate_identity", ok, f"read {seen}, expected {d.expect}")
        if not ok:
            obs["belief"][f"plate_at:{d.expect}"] = ("unknown", "observed")
            raise Failure("identity_mismatch", f"{d.device} read {seen}, expected {d.expect}", dict(read=seen))

    def _c_present(self, d, ctx, obs):
        self.shuttle[d.device] = "presented"
        obs["belief"][f"shuttle:{d.device}"] = ("presented", "observed")
        if d.device in self.slot and self.slot[d.device] is not None:
            p = self.slot.pop(d.device)
            self.plate_at[p] = d.device
            obs["belief"][f"plate_at:{p}"] = (d.device, "observed")
        if self.loaded.get(d.device):
            p = self.loaded.pop(d.device)
            self.plate_at[p] = d.device
            obs["belief"][f"loaded:{d.device}"] = (None, "observed")
            obs["belief"][f"plate_at:{p}"] = (d.device, "observed")

    def _c_stow(self, d, ctx, obs):
        self.shuttle[d.device] = "stowed"
        obs["belief"][f"shuttle:{d.device}"] = ("stowed", "observed")

    def _c_wait_environment(self, d, ctx, obs):
        self._mon(obs, "environment_accepted", self.env_ok, "environment within profile (ILLUSTRATIVE)")
        self._ev(obs, "environment_snapshot", dict(device=d.device, ok=self.env_ok))
        if not self.env_ok:
            raise Failure("environment_excursion", d.device)

    def _c_store(self, d, ctx, obs):
        plate = next((p for p, at in self.plate_at.items() if at == d.device), None)
        if plate is None:
            raise Failure("store_failed", f"no plate at {d.device}")
        self.slot[d.device] = plate
        self.plate_at[plate] = f"slot:{d.device}"
        self.shuttle[d.device] = "stowed"
        self._mon(obs, "seating_confirmed", True, f"{plate} in slot")
        obs["belief"][f"plate_at:{plate}"] = (f"slot:{d.device}", "observed")
        obs["belief"][f"shuttle:{d.device}"] = ("stowed", "observed")

    def _c_incubate(self, d, ctx, obs):
        until = float(d.args[0])
        dt = max(0.0, until - self.t_h)
        self.clock = round(self.clock + dt * 3600.0, 3)
        self.t_h = until
        obs["duration_s"] = round(dt * 3600.0, 2)
        self._ev(obs, "culture_time_h", until)

    def _c_tip_pick(self, d, ctx, obs):
        self._tips_used += 1
        self.tip[d.device] = f"TIP-{self._tips_used:03d}"
        self._mon(obs, "tip_state", True, f"{self.tip[d.device]} attached")
        self._ev(obs, "tip_id", self.tip[d.device])
        obs["belief"][f"tip:{d.device}"] = (self.tip[d.device], "observed")
        f = self._fault(ctx, "tip_lost")
        if f:
            f["count"] = f.get("count", 1) - 1
            self.tip[d.device] = None                 # the tip falls off after the pick confirmation

    def _c_aspirate(self, d, ctx, obs):
        if not self.tip.get(d.device):
            self._mon(obs, "tip_state", False, "no tip on the channel before aspiration")
            obs["belief"][f"tip:{d.device}"] = (None, "observed")
            raise Failure("tip_missing", "tip-presence sensor: no tip before aspiration (aborted before aspiration)")
        _, well, reagent, au = d.material
        rec = self.kb.registry["devices"]["reagents"][reagent]
        vol = round(au / 100.0 / rec["conc_au_per_uL"], 3)
        self.aspirated[d.device] = (reagent, vol)
        self._mon(obs, "tip_state", True, "tip present")
        self._mon(obs, "reagent_identity", True, f"{rec['barcode']} {rec['id']} lot {rec['lot']}")
        self._mon(obs, "liquid_level", True, "surface detected")
        self._mon(obs, "pressure_profile", True, "nominal (symbolic)")
        self._ev(obs, "reagent", dict(id=rec["id"], lot=rec["lot"], barcode=rec["barcode"], volume_uL=vol))

    def _c_dispense(self, d, ctx, obs):
        st = self._station_of_seat(self.kb.seat(d.device).value)
        plate = next((p for p, at in self.plate_at.items() if at == st), None)
        reagent, vol = self.aspirated.get(d.device) or (None, 0.0)
        if plate is None or reagent is None:
            raise Failure("dispense_failed", f"plate={plate}, aspirated={reagent}")
        _, well, _, au = d.material
        delivered = vol
        self.dispensed.append(dict(plate=plate, well=well.upper(), reagent=reagent, commanded_uL=vol,
                                   delivered_uL=delivered, t_h=self.t_h))
        self.aspirated[d.device] = None
        tw = self.kb.components[d.device]["_twin"]
        self._mon(obs, "well_binding", True, f"{plate}/{well.upper()}")
        self._mon(obs, "dispense_completion", True, f"{delivered} uL")
        for k, v in (("plate", plate), ("well", well.upper()), ("reagent", reagent), ("volume_commanded_uL", vol),
                     ("volume_delivered_uL", delivered), ("dose_au", au / 100.0), ("culture_time_h", self.t_h),
                     ("dispense_height_mm", tw["dispense_height_mm"]["value"]),
                     ("dispense_rate_uL_s", tw["dispense_rate_uL_s"]["value"]), ("tip_id", self.tip.get(d.device))):
            self._ev(obs, k, v)

    def _c_tip_eject(self, d, ctx, obs):
        self.tip[d.device] = None
        self._mon(obs, "tip_state", True, "tip ejected to waste")
        obs["belief"][f"tip:{d.device}"] = (None, "observed")

    def _c_load(self, d, ctx, obs):
        plate = next((p for p, at in self.plate_at.items() if at == d.device), None)
        if plate is None:
            raise Failure("load_failed", f"no plate at {d.device}")
        self.loaded[d.device] = plate
        self.plate_at[plate] = f"stage:{d.device}"
        self.shuttle[d.device] = "stowed"
        self._mon(obs, "plate_seating", True, f"{plate} on stage")
        obs["belief"][f"loaded:{d.device}"] = (plate, "observed")
        obs["belief"][f"shuttle:{d.device}"] = ("stowed", "observed")
        obs["belief"][f"plate_at:{plate}"] = (f"stage:{d.device}", "observed")

    def _c_image_well(self, d, ctx, obs):
        if d.device in self.faults.get("calibration_lapsed", {}).get("devices", []) and \
                self._fault(ctx, "calibration_lapsed"):
            self.calibrated[d.device] = False
            self.faults["calibration_lapsed"]["count"] = 0
        plate = self.loaded.get(d.device)
        if plate is None:
            raise Failure("image_failed", f"nothing loaded in {d.device}")
        ok = self.calibrated.get(d.device, False)
        self._mon(obs, "calibration_state", ok, "reference focus check " + ("passed" if ok else "failed: calibration lapsed"))
        self._mon(obs, "focus_quality", ok, "focus score 0.93" if ok else "focus score 0.41 (below acceptance)")
        obs["belief"][f"calibrated:{d.device}"] = (ok, "observed")
        if not ok:
            raise Failure("calibration_invalid", f"{d.device}: calibration check failed at imaging")
        well = d.material[1].upper()
        img = dict(plate=plate, well=well, device=d.device, t_h=self.t_h)
        self.images.append(img)
        self._mon(obs, "illumination_state", True, "nominal")
        self._ev(obs, "image", dict(ref=f"img://{plate}/{well}/{self.t_h:g}h", **img))
        self._ev(obs, "well", well)

    def _c_validate(self, d, ctx, obs):
        target = d.args[0]
        busy = [p for p, at in self.plate_at.items() if at in (target, f"stage:{target}")]
        if busy:
            self._mon(obs, "calibration_state", False, f"QC blocked: {busy} occupies {target}")
            raise Failure("qc_blocked", f"{target} holds {busy}; the reference plate needs the stage")
        self.calibrated[target] = True
        self._mon(obs, "calibration_state", True, f"{target} validated on the reference plate")
        self._mon(obs, "reference_identity", True, "reference plate REF-L21 (twin)")
        self._ev(obs, "qc_result", dict(target=target, station=d.device, result="pass"))
        obs["belief"][f"calibrated:{target}"] = (True, "observed")

    def _c_autofocus(self, d, ctx, obs):
        self._mon(obs, "focus_quality", True, "fresh autofocus (symbolic)")

    def _c_contain(self, d, ctx, obs):
        plate = next((p for p, at in self.plate_at.items() if at == d.device), None)
        self.contained[plate] = "requested"            # Cell 01: stays 'requested' until authorised release
        self.plate_at[plate] = f"contained:{d.device}"
        self._mon(obs, "containment_state", True, f"{plate} contained; release requires authorisation")
        self._ev(obs, "quarantine_request", dict(plate=plate, device=d.device, status="requested",
                                                 authorization="human_review_required"))
        obs["belief"][f"plate_at:{plate}"] = (f"contained:{d.device}", "observed")
