"""Isaac backend of the kernel: the same designators, executed by Cell 01's twin controllers (iteration 2).

Runs inside the Isaac process of ``scripts/run_cell01_episode.py --rsa <scenario>``, which builds the scene and hands
over its controllers and skills (``S``). The kernel, the plan library, the knowledge, the audit trail, the critic and the
competency questions are the ones used with the symbolic backend; only leaf execution changes.

Skill binding (the process-module layer, kernel concept "device-command leaf"; ITERATIONS F13):
  * the twin's skills are coarser than the leaves: R01/R02 pick = approach+insert+grasp+lift, place =
    approach+place+release(+retract clearing), L12 ``dose_well`` = tip_pick+aspirate+dispense+tip_eject. A group is
    executed at its FIRST leaf; the following leaves report the phase evidence of that execution (duration 0). Each
    leaf entry says ``realised_by``.
  * L17 images per well (``image_well``), L10 release reads identity (verify_identity) and presents (present).
Durations are the twin's physics time; culture waits advance a separate offset (no physics in between).
"""

from __future__ import annotations

import copy
import json
import os
from typing import Any, Dict

from .core import Command, Context, Failure, Motion
from .backend import SymbolicWorld, _sha

NEST = dict(l10="L10", handovernest="HN", l12="L12", l17="L17", h4="H4", l09="L09", l21="L21ref")


def tw(pid: str) -> str:
    return f"Plate_{pid}"


class IsaacBackend:
    name = "isaac-cell01-twin/0.1"

    def __init__(self, S, kb, faults=None):
        self.S, self.kb = S, kb
        self.faults = dict(faults or {})
        self.offset = 0.0                 # culture-time offset (s) added to the twin's physics clock
        self.t_h = 0.0
        self.grp: Dict[str, Dict[str, Any]] = {}
        self.release: Dict[str, Any] = {}
        self.dose: Dict[str, Any] = {}
        self.mismatch_reason = None

    @property
    def clock(self) -> float:
        return round(self.S.rig.t + self.offset, 3)

    def projection(self, belief=None):
        return SymbolicWorld.from_belief(self.kb, belief, self.clock, self.t_h)

    def initial_belief(self, belief, plate: str):
        SymbolicWorld(self.kb, plate=plate).initial_belief(belief, plate)

    # ---------------------------------------------------------------------------------------------- helpers
    def _session(self, ctx):
        for n in [ctx.node] + ctx.node.ancestors():
            if n.designator.category == "run_session":
                return n.designator.session
        return None

    def _station(self, seat):
        a = self.kb.one("seat", None, seat)
        return a[1] if a else seat

    def _plate_of(self, ctx):
        for n in [ctx.node] + ctx.node.ancestors():
            p = getattr(n.designator, "plate", None)
            if p is not None:
                return p.id
        return None

    def _seated(self, nest):
        S = self.S
        return bool({"HN": lambda: S.hn.seated, "L10": lambda: S.l10.seated, "L12": lambda: S.l12.seated,
                     "L17": lambda: S.l17.seated, "H4": lambda: S.h4.seated}.get(nest, lambda: True)())

    @staticmethod
    def _mon(obs, name, passed, observation):
        obs["monitors"].append(dict(name=name, passed=bool(passed), observation=observation))

    @staticmethod
    def _ev(obs, kind, value):
        obs["evidence"].append(dict(kind=kind, value=value, sha256=_sha([kind, value])))

    # ---------------------------------------------------------------------------------------------- execute
    def execute(self, d, ctx: Context) -> Dict[str, Any]:
        t0 = self.S.rig.t
        obs = dict(monitors=[], evidence=[], belief={}, realised_by=None)
        try:
            if isinstance(d, Motion):
                self._motion(d, ctx, obs)
            else:
                getattr(self, f"_c_{d.command}")(d, ctx, obs)
        except Failure as f:
            obs["duration_s"] = round(self.S.rig.t - t0, 2)
            f.obs = obs
            raise
        obs["duration_s"] = round(self.S.rig.t - t0, 2) if d.KIND == "motion" or d.command != "incubate" \
            else obs.get("duration_s", 0.0)
        if obs.get("realised_by"):
            self._ev(obs, "realised_by", obs.pop("realised_by"))
        return obs

    # ---------------------------------------------------------------------------------------------- motions
    def _motion(self, d: Motion, ctx, obs):
        S, r, prim = self.S, d.robot, d.primitive
        parent = ctx.node.parent.designator
        pid = self._plate_of(ctx)
        held = S.by_barcode.get(tw(pid)) if pid else None
        if prim == "tool_couple":
            ok, why = S.ensure_t01()
            self._mon(obs, "tool_frame_validity", ok, f"tool {(S.r02rig.tool or {}).get('id')} {why or ''}".strip())
            obs["realised_by"] = "R02 tool changer (TCM01) change_tool"
            if not ok:
                raise Failure("tool_change_failed", why)
            obs["belief"][f"tool:{r}"] = (d.args[0], "observed")
            return
        if prim == "transit":
            dst = NEST[self._station(d.args[1][1])]
            if r == "r01":
                ok, info = S.go_above(dst, held=True, phase="transit")
                self._mon(obs, "route_clear", ok, f"planned joint-space transit to {dst}")
                obs["realised_by"] = "R01 r01_planner transit"
                if not ok:
                    raise Failure("transit_failed", f"no transit to {dst}")
            else:
                obs["realised_by"] = "realised within R02's place skill (rail + arm path)"
            obs["belief"][f"pose:{r}"] = (list(d.args[1]), "observed")
            return
        cat = parent.category
        if cat == "picking_up":
            src = NEST[parent.station]
            if prim == "approach":
                if r == "r01":
                    ok_a, _ = S.go_above(src, held=False)
                    S.rig.phase = "pick"
                    g = S.rig.pick(*S.at(src), f"pick_{src}", plate=held)
                    S.rig.phase = None
                    res = dict(approach=bool(ok_a), insert=bool(ok_a), grasp=bool(g.get("contact")),
                               lift=bool(g.get("lifted")), evidence={k: bool(g.get(k)) for k in ("lifted", "contact")})
                    skill = "R01 go_above + rig.pick"
                else:
                    g = S.r02_pick(src, S.PLAN_R02_SIDE.get(src, 1.0), held)
                    res = dict(approach=bool(g["positioned"]), insert=bool(g["positioned"]), grasp=bool(g["converged"]),
                               lift=bool(g["lifted"]), evidence={k: g[k] for k in ("positioned", "converged",
                                                                                     "lifted_mm")})
                    skill = "R02 r02_pick"
                self.grp[r] = dict(res, skill=skill)
            res = self.grp[r]
            obs["realised_by"] = res["skill"] + ("" if prim == "approach" else f" (phase {prim})")
            if prim == "grasp":
                self._mon(obs, "grasp_confirmed", res["grasp"], json.dumps(res["evidence"]))
            if not res[prim]:
                raise Failure(f"{prim}_failed", f"{r} {prim} at {src}: {res['evidence']}")
            pose = ["appr", parent.seat] if prim in ("approach", "lift") else ["seat", parent.seat]
            obs["belief"][f"pose:{r}"] = (pose, "observed")
            if prim == "lift":
                obs["belief"][f"plate_at:{pid}"] = (f"robot:{r}", "observed")
            return
        if cat == "placing":
            dst = NEST[parent.station]
            if prim == "approach":
                if r == "r01":
                    S.rig.phase = "place"
                    placed, info = S.rig.place(*S.at(dst), contacts_phase="insert")
                    S.rig.phase = None
                    S.rig.step(int(0.5 * S.HZ))
                    seated = self._seated(dst)
                    res = dict(approach=True, place=bool(placed), release=bool(placed), seated=seated,
                               evidence={"placed": bool(placed), "seated": seated,
                                         **{k: info.get(k) for k in ("landing_speed_mm_s",) if k in info}})
                    skill = "R01 rig.place (compliant)"
                else:
                    g = S.r02_place(dst, S.PLAN_R02_SIDE.get(dst, 1.0), held)
                    seated = self._seated(dst)
                    res = dict(approach=bool(g["positioned"]), place=bool(g["converged"]), release=bool(g["converged"]),
                               seated=seated, evidence={"seated": seated, "offset_mm": g["offset_mm"],
                                                        "tilt_deg": g["tilt_deg"]})
                    skill = "R02 r02_place"
                self.grp[r] = dict(res, skill=skill)
            res = self.grp[r]
            obs["realised_by"] = res["skill"] + ("" if prim == "approach" else f" (phase {prim})")
            if prim == "release":
                self._mon(obs, "seating_confirmed", res["seated"], json.dumps(res["evidence"]))
                if not res["seated"]:
                    raise Failure("seating_failed", f"{pid} not seated at {dst}: {res['evidence']}")
                obs["belief"][f"plate_at:{pid}"] = (parent.station, "observed")
            if prim == "retract":
                if r == "r01":
                    clear = S.go_above("L09" if dst == "HN" else dst, held=False)[0]
                    obs["realised_by"] = f"R01 retract to {'L09 approach (clear of HN)' if dst == 'HN' else dst + ' approach'}"
                else:
                    clear = S.r02_clear() if dst == "L12" else S.r02_park() if dst == "HN" else True
                    obs["realised_by"] = f"R02 {'r02_clear' if dst == 'L12' else 'r02_park' if dst == 'HN' else 'stay'}"
                if dst == "L12":
                    self._mon(obs, "route_clear", S.l12.airspace_clear(), "L12 airspace clear after retract")
                if not clear:
                    raise Failure("retract_failed", f"{r} could not clear {dst}")
            elif not res.get(prim, True):
                raise Failure(f"{prim}_failed", f"{r} {prim} at {dst}: {res['evidence']}")
            pose = ["seat", parent.seat] if prim in ("place", "release") else ["appr", parent.seat]
            obs["belief"][f"pose:{r}"] = (pose, "observed")
            return
        raise Failure("no_skill", f"no twin skill for {prim} under {cat}")

    # ---------------------------------------------------------------------------------------------- commands
    def _c_check_interlocks(self, d, ctx, obs):
        S = self.S
        if S.LAB:
            closed = all(x.state() == "closed" for x in S.interlock.doors.values())
            self._mon(obs, "route_clear", closed, "LAB enclosure interlock state")
        else:
            closed = True
            self._mon(obs, "route_clear", True, "Cell 01 scene: no door model; the enclosure interlock is not "
                                                "simulated (assumed closed, epistemic: assumption)")
        if not closed:
            raise Failure("interlock_open", "enclosure interlock open")

    def _c_verify_identity(self, d, ctx, obs):
        S = self.S
        tr = S.rig.t
        r = S.l10.release_plate(tw(d.expect))
        ok = r.accepted and S.wait(lambda: S.l10.mode in ("PRESENTED_LOADED", "FAULT"), 120, "L10 release")
        seen = (S.events_since(S.l10, tr, "identity_read") or [{}])[-1].get("observed")
        seen_id = seen.replace("Plate_", "") if seen else None
        self.release = dict(accepted=bool(ok), mode=S.l10.mode, seen=seen_id)
        self._ev(obs, "barcode_read", dict(device=d.device, read=seen_id))
        obs["belief"]["identity_read"] = (seen_id, "observed")
        obs["realised_by"] = "L10 release_plate (barcode read at the transfer nest)"
        match = seen_id == d.expect
        self._mon(obs, "plate_identity", match, f"read {seen_id}, expected {d.expect}")
        if not match:
            obs["belief"][f"plate_at:{d.expect}"] = ("unknown", "observed")
            obs["belief"][f"plate_at:{seen_id}"] = (f"slot:{d.device}", "observed")
            self.mismatch_reason = f"identity mismatch at L10 release: expected {tw(d.expect)}, barcode read {seen!r}"
            raise Failure("identity_mismatch", f"{d.device} read {seen_id}, expected {d.expect}", dict(read=seen_id))

    def _c_present(self, d, ctx, obs):
        S, dev = self.S, d.device
        if dev == "l10":
            if self.release.get("mode") == "PRESENTED_LOADED" and self.release.get("accepted"):
                ok = S.l10.mode == "PRESENTED_LOADED"
                obs["realised_by"] = "L10 release_plate (presented with the identity read)"
                self.release = {}
                plate = self._plate_of(ctx)
                obs["belief"][f"plate_at:{plate}"] = ("l10", "observed")
            elif S.l10.mode == "FAULT":
                pid = self._plate_of(ctx)
                rp = S.l10.present_for_removal(self.mismatch_reason or "removal")
                ok = rp.accepted and S.wait(lambda: S.l10.mode == "PRESENTED_LOADED", 60, "L10 present for removal")
                obs["realised_by"] = "L10 present_for_removal"
                obs["belief"][f"plate_at:{pid}"] = ("l10", "observed")
            else:
                S.wait(S.l10_ready_for_transfer, 600, "L10 environment ready for a transfer")
                S.l10.present_for_load()
                ok = S.wait(lambda: S.l10.mode == "PRESENTED_EMPTY", 30, "L10 present for load")
                obs["realised_by"] = "L10 present_for_load"
        elif dev == "l17":
            unload = S.l17.mode == "LOADED"
            (S.l17.present_for_unload if unload else S.l17.present_for_load)()
            ok = S.wait(lambda: S.l17.mode != "BUSY", 30, f"L17 present for {'unload' if unload else 'load'}")
            obs["realised_by"] = f"L17 present_for_{'unload' if unload else 'load'}"
            if unload:
                obs["belief"][f"loaded:{dev}"] = (None, "observed")
                obs["belief"][f"plate_at:{self._plate_of(ctx)}"] = (dev, "observed")
        elif dev == "h4":
            S.h4.present_nest()
            ok = S.wait(lambda: S.h4.mode == "PRESENTED", 60, "H4 present nest")
            obs["realised_by"] = "H4 present_nest"
        else:
            raise Failure("no_skill", f"present {dev}")
        self._mon(obs, "source_release_state", ok, f"{dev} mode {getattr(getattr(S, dev), 'mode', '?')}")
        if not ok:
            raise Failure("present_failed", f"{dev}")
        obs["belief"][f"shuttle:{dev}"] = ("presented", "observed")

    def _c_stow(self, d, ctx, obs):
        S, dev = self.S, d.device
        x = getattr(S, dev)
        x.stow()
        ok = S.wait(lambda: x.mode not in ("BUSY", "PRESENTED_EMPTY", "PRESENTED"), 30, f"{dev} stow")
        obs["realised_by"] = f"{dev.upper()} stow"
        self._mon(obs, "source_release_state", ok, f"{dev} mode {x.mode}")
        if not ok:
            raise Failure("stow_failed", dev)
        obs["belief"][f"shuttle:{dev}"] = ("stowed", "observed")

    def _c_incubate(self, d, ctx, obs):
        until = float(d.args[0])
        dt = max(0.0, until - self.t_h) * 3600.0
        self.offset += dt
        self.t_h = until
        obs["duration_s"] = round(dt, 2)
        obs["realised_by"] = "culture time advanced (no physics simulated between sessions)"
        self._ev(obs, "culture_time_h", until)

    # L12: dose_well executes at tip_pick, the following leaves report its phases
    def _c_tip_pick(self, d, ctx, obs):
        S, m = self.S, d.material
        if self.dose.get("key") == (m, "retry"):
            pass
        _, well, reagent, au = m
        rec_r = self.kb.registry["devices"]["reagents"][reagent]
        pos = int(self.kb.reagent_pose(reagent).value.rsplit("_", 1)[-1])
        vol = round(au / 100.0 / rec_r["conc_au_per_uL"], 3)
        tw_ = self.kb.components[d.device]["_twin"]
        n_ev = len(S.l12.events)
        pid = self._plate_of(ctx)
        r = S.l12.dose_well(tw(pid), well.upper(), pos, rec_r["id"], rec_r["lot"], vol,
                            tw_["dispense_height_mm"]["value"], tw_["dispense_rate_uL_s"]["value"],
                            intended_effect=f"abstract_{reagent}")
        fin = r.accepted and S.wait(lambda: S.l12.mode != "BUSY", 240, f"L12 dose_well {well} {reagent} {au / 100} au")
        rec = S.l12.doses[-1] if fin and S.l12.doses else None
        evs = [e["event"] for e in S.l12.events[n_ev:]]
        self.dose = dict(rec=rec, evs=evs, vol=vol, accepted=r.accepted, reason=r.reason, lot=rec_r["lot"], rid=rec_r["id"],
                         barcode=rec_r["barcode"])
        obs["realised_by"] = "L12 dose_well (contract action; phases tip_pick, aspirate, dispense, tip_eject)"
        ok = "tip_pick" in evs
        self._mon(obs, "tip_state", ok, "tip_pick event in L12's log" if ok else f"no tip_pick ({r.reason})")
        if not r.accepted:
            raise Failure("dose_refused", str(r.reason))
        if not ok:
            raise Failure("tip_missing", "no tip_pick event")

    def _c_aspirate(self, d, ctx, obs):
        x = self.dose
        ok = "aspirate" in x["evs"] or bool(x["rec"])
        obs["realised_by"] = "L12 dose_well (phase aspirate)"
        self._mon(obs, "reagent_identity", ok, f"{x['barcode']} {x['rid']} lot {x['lot']}")
        self._ev(obs, "reagent", dict(id=x["rid"], lot=x["lot"], barcode=x["barcode"], volume_uL=x["vol"]))
        if not ok:
            raise Failure("aspirate_failed", "no aspiration in L12's log")

    def _c_dispense(self, d, ctx, obs):
        x, m = self.dose, d.material
        rec = x["rec"]
        ok = bool(rec and rec.get("valid") and not rec.get("aborted"))
        got = round(float(rec.get("volume_inferred_uL") or 0.0), 3) if rec else 0.0
        obs["realised_by"] = "L12 dose_well (phase dispense; volume inferred by L12's liquid model)"
        self._mon(obs, "dispense_completion", ok, f"{got} uL of {x['vol']} uL")
        self._mon(obs, "well_binding", bool(rec and rec.get("well_id") == m[1].upper()), f"{rec and rec.get('well_id')}")
        tw_ = self.kb.components[d.device]["_twin"]
        for k, v in (("plate", self._plate_of(ctx)), ("well", m[1].upper()), ("reagent", m[2]),
                     ("volume_commanded_uL", x["vol"]), ("volume_delivered_uL", got), ("dose_au", m[3] / 100.0),
                     ("culture_time_h", self.t_h), ("dispense_height_mm", tw_["dispense_height_mm"]["value"]),
                     ("dispense_rate_uL_s", tw_["dispense_rate_uL_s"]["value"]), ("tip_id", rec and rec.get("tip_id"))):
            self._ev(obs, k, v)
        if not ok:
            raise Failure("dispense_failed", f"L12 record {rec}")

    def _c_tip_eject(self, d, ctx, obs):
        evs = self.dose.get("evs", [])
        ok = "tip_eject" in evs and "tip_pick" in evs and evs.index("tip_pick") < evs.index("tip_eject")
        obs["realised_by"] = "L12 dose_well (phase tip_eject)"
        self._mon(obs, "tip_state", ok, "tip ejected to waste after the dispense" if ok else "no tip_eject")
        if not ok:
            raise Failure("tip_eject_failed", "")

    # L17
    def _c_load(self, d, ctx, obs):
        S = self.S
        pid = self._plate_of(ctx)
        r = S.l17.load_plate(tw(pid))
        ok = r.accepted and S.wait(lambda: S.l17.mode != "BUSY", 30, "L17 load_plate") and S.l17.mode == "LOADED"
        self._mon(obs, "plate_seating", ok, f"L17 mode {S.l17.mode}")
        obs["realised_by"] = "L17 load_plate"
        if not ok:
            raise Failure("load_failed", str(r.reason))
        obs["belief"][f"loaded:{d.device}"] = (pid, "observed")
        obs["belief"][f"shuttle:{d.device}"] = ("stowed", "observed")
        obs["belief"][f"plate_at:{pid}"] = (f"stage:{d.device}", "observed")

    def _c_image_well(self, d, ctx, obs):
        S = self.S
        f = self.faults.get("calibration_lapsed")
        if f and f.get("count", 1) > 0 and self._session(ctx) == f.get("session"):
            S.l17.invalidate_calibration("scenario: calibration lapsed (injected)", "QC-SCENARIO-LAPSE")
            f["count"] = 0
        pid = self._plate_of(ctx)
        well = d.material[1].upper()
        n0 = len(S.l17.acquisitions)
        cal_ok = S.l17.calibration_valid
        r = S.l17.image_well(tw(pid), well)
        if r.accepted:
            S.wait(lambda: S.l17.mode != "BUSY", 120, f"L17 image {well}")
        acq = next((a for a in reversed(S.l17.acquisitions[n0:]) if a.get("well_id") == well), None)
        failed = [m["name"] for m in (acq or {}).get("monitors", []) if not m["passed"]]
        cal_ok = cal_ok and S.l17.calibration_valid and "calibration_state" not in failed
        obs["realised_by"] = "L17 image_well (autofocus, capture, validity monitors)"
        self._mon(obs, "calibration_state", cal_ok, f"calibration {S.l17.calibration.get('calibration_id')} "
                                                     f"valid={S.l17.calibration_valid}" if r.accepted else str(r.reason))
        if acq:   # a refused command acquired nothing, so there is no focus observation to record
            self._mon(obs, "focus_quality", "focus_quality" not in failed, f"failed monitors {failed}")
        obs["belief"][f"calibrated:{d.device}"] = (cal_ok, "observed")
        if not r.accepted and not cal_ok:
            raise Failure("calibration_invalid", f"L17 refused imaging: {r.reason}")
        if not acq:
            raise Failure("image_failed", f"no acquisition for {well} ({r.reason})")
        if not cal_ok:
            raise Failure("calibration_invalid", f"L17 calibration invalid at {well}")
        if failed == ["focus_quality"]:
            raise Failure("focus_invalid", f"{well} out of focus; retained")
        if not acq.get("valid"):
            raise Failure("image_invalid", f"{well}: {failed}")
        self._mon(obs, "illumination_state", "illumination_state" not in failed, "nominal")
        self._ev(obs, "image", dict(ref=acq.get("raw_image_reference") or f"l17://{pid}/{well}/{acq.get('t')}", plate=pid,
                                    well=well, device=d.device, t_h=self.t_h, valid=acq.get("valid")))
        self._ev(obs, "well", well)

    def _c_autofocus(self, d, ctx, obs):
        S = self.S
        pid = self._plate_of(ctx)
        S.l17.focus_memory.pop((tw(pid), "10x"), None)
        obs["realised_by"] = "L17 focus memory cleared (fresh autofocus at the next image)"
        self._mon(obs, "focus_quality", True, "focus memory cleared")

    def _c_validate(self, d, ctx, obs):
        S = self.S
        okt, why = S.ensure_t01()
        S.l17.present_for_load()
        S.r02_pick("L21ref", 1.0, S.REF_PATH)
        S.r02_place("L17", 1.0, S.REF_PATH)
        S.wait(lambda: S.l17.mode != "BUSY", 30, "L17 present")
        S.l17.load_plate(S.REF_ID)
        S.wait(lambda: S.l17.mode != "BUSY", 30, "L17 load reference")
        r = S.l21.validate_imager(S.l17, S.REF_ID)
        if r.accepted:
            S.wait(lambda: S.l21.mode != "BUSY", 900, "L21 validate_imager")
        S.l17.present_for_unload()
        S.wait(lambda: S.l17.mode != "BUSY", 30, "L17 present for unload")
        S.r02_pick("L17", 1.0, S.REF_PATH)
        S.l17.stow()
        S.r02_place("L21ref", 1.0, S.REF_PATH)
        S.r02_clear()
        verdict = S.l21.qc_records[-1]["verdict"] if S.l21.qc_records else None
        ok = verdict == "pass" and S.l17.calibration_valid
        obs["realised_by"] = "L21 reference-plate procedure (R02 moves REF-L21-001 to L17 and back; validate_imager)"
        self._mon(obs, "calibration_state", ok, f"QC verdict {verdict}; L17 calibration valid={S.l17.calibration_valid}")
        self._mon(obs, "reference_identity", True, S.REF_ID)
        self._ev(obs, "qc_result", dict(target=d.args[0], station=d.device, result=verdict))
        obs["belief"][f"calibrated:{d.args[0]}"] = (ok, "observed")
        obs["belief"]["tool:r02"] = ((S.r02rig.tool or {}).get("id", "").lower() or None, "observed")
        obs["belief"][f"shuttle:{d.args[0]}"] = ("stowed", "observed")
        if not ok:
            raise Failure("qc_failed", f"verdict {verdict}")

    def _c_wait_environment(self, d, ctx, obs):
        S = self.S
        ok = S.wait(S.l10_ready_for_transfer, 600, "L10 environment ready") and S.l10.environment_valid
        obs["realised_by"] = "L10 environment control"
        self._mon(obs, "environment_accepted", ok, "L10 environment valid (ILLUSTRATIVE profile)")
        self._ev(obs, "environment_snapshot", {k: round(v, 3) for k, v in S.l10.env.items()})
        if not ok:
            raise Failure("environment_excursion", "L10")

    def _c_store(self, d, ctx, obs):
        S = self.S
        pid = self._plate_of(ctx)
        slot = next((p["slot"] for p in S.PLATES.values() if p["inventory"] == tw(pid)), None)
        tr = S.rig.t
        r = S.l10.incubate(tw(pid), slot)
        fin = r.accepted and S.wait(lambda: S.l10.mode in ("READY", "FAULT"), 120, "L10 incubate")
        seen = (S.events_since(S.l10, tr, "identity_read") or [{}])[-1].get("observed")
        ok = fin and S.l10.mode == "READY" and S.l10.inventory[slot] == tw(pid) and seen == tw(pid)
        obs["realised_by"] = "L10 incubate (identity read + slot store)"
        self._mon(obs, "seating_confirmed", ok, f"slot {slot}, read {seen}")
        self._ev(obs, "barcode_read", dict(device=d.device, read=(seen or "").replace("Plate_", "")))
        if not ok:
            raise Failure("store_failed", f"L10 mode {S.l10.mode}, read {seen}")
        obs["belief"][f"plate_at:{pid}"] = (f"slot:{d.device}", "observed")
        obs["belief"][f"shuttle:{d.device}"] = ("stowed", "observed")

    def _c_contain(self, d, ctx, obs):
        S = self.S
        pid = self._plate_of(ctx)
        r = S.h4.quarantine_sample(tw(pid), self.mismatch_reason or "unresolved", preceding_anomalies=["rsa retrieve"])
        ok = r.accepted and S.wait(lambda: S.h4.mode == "QUARANTINED", 20, "H4 quarantine")
        snap = S.h4.snapshot()
        r_un = S.h4.release("")
        blocked = not r_un.accepted and S.h4.mode == "QUARANTINED"
        obs["realised_by"] = "H4 quarantine_sample (door closed, bolt locked)"
        self._mon(obs, "containment_state", ok and snap["locked"], json.dumps({k: snap[k] for k in ("mode", "locked",
                                                                                                    "occupied")}))
        self._mon(obs, "reentry_prevented", blocked, f"unauthorised release refused: {r_un.reason!r}")
        self._ev(obs, "quarantine_request", dict(plate=pid, device=d.device, status="requested",
                                                 authorization="human_review_required"))
        if not ok:
            raise Failure("quarantine_failed", str(r.reason))
        obs["belief"][f"plate_at:{pid}"] = (f"contained:{d.device}", "observed")


# ================================================================================================== runner
def run_isaac(S, scenario: str) -> bool:
    import yaml
    from .audit import AuditTrail, verify
    from .core import KERNEL_VERSION, Belief, Context, perform
    from .critic import assess
    from .kb import KB, PLAN_DIR, REGISTRY
    from .library import experiment_from_plan
    from .run_example import OUT, scenario_kb, registry_sha, EXPECTED

    sc = yaml.safe_load(open(os.path.join(REGISTRY, "scenarios_isaac.yaml")))[scenario]
    tag = sc.get("plan", "g050")
    kb = scenario_kb(KB.load(tag), sc, f"facts_{tag}+{scenario}")
    plan = json.load(open(os.path.join(PLAN_DIR, f"plan_{tag}.json")))
    exp = experiment_from_plan(plan, sc["plate"])
    be = IsaacBackend(S, kb, faults=copy.deepcopy(sc.get("faults")))
    belief = Belief()
    be.initial_belief(belief, exp.plate.id)
    software = dict(kernel=KERNEL_VERSION, kb=kb.name, registry=registry_sha(), backend=be.name)
    trail = AuditTrail(f"challenge-rescue/{scenario}", software)
    ctx = Context(kb, be, trail, belief)
    t_wall = __import__("time").time()
    try:
        perform(exp, ctx)
        err = None
    except Failure as f:
        err = f"{f.code}: {f.detail}"
    except Exception as ex:          # a backend bug: keep the partial trail, report it as such
        import traceback
        traceback.print_exc()
        err = f"BACKEND EXCEPTION {type(ex).__name__}: {ex}"
    root = ctx.root
    td = trail.as_dict()
    os.makedirs(OUT, exist_ok=True)
    json.dump(td, open(os.path.join(OUT, f"trail_{scenario}.json"), "w"), indent=1, default=str)
    v = verify(td)
    t2 = copy.deepcopy(td)
    t2["entries"][len(t2["entries"]) // 2]["transition"] = "EDITED"
    verdict = assess(td)
    rec = dict(scenario=scenario, about=sc.get("about"), backend=be.name, error=err,
               end=root.lifecycle[-1] if root.lifecycle else root.status, n_entries=len(td["entries"]),
               n_leaves=len(root.leaves()), wall_s=round(__import__("time").time() - t_wall, 1),
               audit=dict(verify=v, tampered_detected=not verify(t2)["ok"]), verdict=verdict,
               repairs=[dict(r, category=n.designator.category, node=n.uid) for n in root.walk() for r in n.repairs],
               sessions=[dict(session=n.designator.session, kernel_s=round(n.t1 - n.t0, 2),
                              planner_s=next(s["duration_s"] + s.get("prep_s", 0) for s in plan["sessions"]
                                             if s["session"] == n.designator.session),
                              leaves=len(n.leaves()))
                         for n in root.walk() if n.designator.category == "run_session"])
    exp_v = EXPECTED.get(scenario, {})
    got = dict(end=rec["end"], realization=verdict["realization"]["ok"], validity=verdict["validity"]["ok"],
               promotable=verdict["promotable"], nr3=verdict["nr3"],
               repaired_at=[r["category"] for r in rec["repairs"]])
    rec.update(expected=exp_v, got=got, expectation_ok=all(got[k] == x for k, x in exp_v.items()), plate=exp.plate.id)
    from .cq import run_cqs
    cq = run_cqs({scenario: dict(rec, _ctx=ctx, _plan=plan)})
    rec["cq"] = dict(correct=cq["correct"], n=cq["n"], grounded=cq["grounded"], results=cq["results"])
    json.dump(rec, open(os.path.join(OUT, f"run_{scenario}.json"), "w"), indent=1, default=str)
    ok = not str(err).startswith("BACKEND") and rec["expectation_ok"] and v["ok"] and rec["audit"]["tampered_detected"] and cq["ok"]
    print(f"[rsa-isaac] {scenario}: end={rec['end']} R={verdict['realization']['ok']} V={verdict['validity']['ok']} -> "
          f"{verdict['disposition']}; {rec['n_leaves']} leaves, {rec['n_entries']} entries; sessions "
          + ", ".join(f"{s['session']} {s['kernel_s']} s (planner {s['planner_s']})" for s in rec["sessions"])
          + f"; repairs {[(r['failure'], r['category']) for r in rec['repairs']]}; CQ {cq['correct']}/{cq['n']}; "
          f"{'PASS' if ok else 'FAIL'}" + (f"; error {err}" if err else ""), flush=True)
    return ok
