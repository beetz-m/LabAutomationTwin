"""Runtime controller for the L21 Quality-Control and Calibration Station twin (sdt/components/L21_QC_Calibration.yaml).

Asset: assets/l21/l21.usda (reference nest + QC nest with seat sensors, light-barrier tool datum, AprilTag board).

  validate_imager(l17, reference_id)   validate_measurement_chain for L17: the reference plate must be loaded in L17
        (its identity read by L17's own barcode reader = validate_barcode). L21 runs, per objective: three fresh
        autofocus runs (repeatability) and reference images of the dot grid at two wells (QC acquisitions), and
        measures pixel scale, isotropy, orientation and brightness against the versioned acceptance criterion.
        Verdict:
          * pass                 -> a new L17 calibration record (measured pixel sizes, 30 days) is issued;
          * scale out of tolerance only, inside the recalibration band -> the old record is invalidated
                                    (dependent measurements flagged), a recalibrated record is issued and must be
                                    confirmed by a second validation (as-found / as-left);
          * anything else out of tolerance -> the record is invalidated, L17 stays blocked: repair + human.
  validate_tool_frame(tool_id)  begin_tool_check / mark_phase / finish_tool_check: while the robot sweeps the tool
        through the crossed beams, L21 samples both beams every physics step together with the robot's believed
        TCP; twin/l21_analysis.py recovers the real TCP. Out of tolerance -> the tool frame is invalid and a
        correction is offered (the robot's tool record must be updated and re-checked).
  Reference artifacts carry identity, lot, certified values and validity; an expired artifact refuses every check.
  Every result is a QC record (twin/episode_records.py builds the Cell 01 `qc` designator record from it).

Thresholds are versioned acceptance criteria (L21-ACC-IMG-v1, L21-ACC-TCP-v1); the certified values belong to the
simulated reference artifact. Engineering values, no biological parameters (D016).
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field

import carb
import numpy as np
from omni.physx import get_physx_scene_query_interface
from pxr import Gf, Usd, UsdGeom

from . import l21_analysis as qa

ARTIFACTS = {
    "REF-L21-001": {"kind": "SBS reference plate, dot-grid target in every well", "lot": "SIM-LOT-2026-001",
                    "certified": {"pitch_um": 50.0, "pitch_u_um": 0.05}, "valid_until": "2027-04-30",
                    "certificate": "simulated certificate (twin)", "home": "reference_plate_frame"},
    "DATUM-L21-LB1": {"kind": "light-barrier tool datum (2 crossed beams)", "lot": "SIM-LB-2026-001",
                      "certified": {"beam_position_u_mm": 0.02}, "valid_until": "2027-04-30",
                      "certificate": "simulated certificate (twin)", "home": "tool_calibration_frame"},
}
ACC_IMG = {"id": "L21-ACC-IMG-v1", "wells": ["D06", "E07"], "objectives": ["10x", "4x"], "af_repeats": 3,
           "pixel_scale_tol": 0.01, "recal_band": 0.10, "isotropy_tol": 0.005, "orientation_tol_deg": 1.0,
           "brightness_nominal_fs": 0.60, "brightness_tol": 0.10, "af_repeat_um": {"10x": 2.2, "4x": 14.0},
           "focus_floor": {"10x": 0.04, "4x": 0.15}, "validity_days": 30}
ACC_TCP = {"id": "L21-ACC-TCP-v1", "tol_mm": 0.5, "validity_days": 7}
LIGHT_ON = 3000.0


@dataclass
class Result:
    accepted: bool
    reason: str = ""


@dataclass
class L21Controller:
    stage: Usd.Stage
    root: str
    today: str = "2026-10-16"
    dt: float = 1.0 / 240
    t: float = 0.0
    mode: str = "READY"     # READY | BUSY | FAULT
    events: list = field(default_factory=list)
    _written: dict = field(default_factory=dict)

    def __post_init__(self):
        self.prim = self.stage.GetPrimAtPath(self.root)
        xc = UsdGeom.XformCache(Usd.TimeCode.Default())
        W = lambda n: np.array(xc.GetLocalToWorldTransform(self.stage.GetPrimAtPath(f"{self.root}/{n}"))  # noqa: E731
                               .ExtractTranslation())
        self.frames = {n: W(n) for n in ("reference_plate_frame", "qc_nest_frame", "tool_calibration_frame",
                                         "camera_calibration_frame")}
        self.beams = {b: (W(f"beam_{b}_emitter"), W(f"beam_{b}_receiver")) for b in ("A", "B")}
        self.seat = {n: [W(f"{n}_seat_sensor_{i}") for i in range(4)] for n in ("reference_plate_frame", "qc_nest_frame")}
        self.up = np.array(xc.GetLocalToWorldTransform(self.prim).TransformDir(Gf.Vec3d(0, 0, 1)))
        self.sq = get_physx_scene_query_interface()
        self.artifacts = json.loads(json.dumps(ARTIFACTS))
        self.tool_frames = {}        # tool_id -> last tool-frame record
        self.calibrations = []       # calibration records issued
        self.qc_records = []         # QC results (one per validation)
        self._check = None
        self._job = None
        self._n = 0
        self.update(0.0)

    # ------------------------------------------------------------------ sensing
    def _hits(self, origin, direction, dist):
        hits = []

        def report(h):
            if not h.collision.startswith(self.root + "/"):
                hits.append((h.distance, h.collision))
            return True

        self.sq.raycast_all(carb.Float3(*map(float, origin)), carb.Float3(*map(float, direction)), float(dist), report)
        return sorted(hits)

    def beam_blocked(self, b):
        e, r = self.beams[b]
        d = r - e
        return bool(self._hits(e, d / np.linalg.norm(d), np.linalg.norm(d)))

    def nest_state(self, name):
        gaps = []
        for s in self.seat[name]:
            h = self._hits(s, self.up, 0.015)
            gaps.append(None if not h else h[0][0] - 0.001)
        return {"plate_on_nest": any(g is not None for g in gaps),
                "seated": all(g is not None and g < 0.0004 for g in gaps),
                "gaps_mm": [None if g is None else round(g * 1e3, 3) for g in gaps]}

    def artifact_valid(self, ref_id):
        a = self.artifacts.get(ref_id)
        return a is not None and datetime.date.fromisoformat(self.today) <= datetime.date.fromisoformat(a["valid_until"])

    # ------------------------------------------------------------------ tool frame (light barrier)
    def begin_tool_check(self, tool_id, believed_tcp, tip_below_tcp, datum_id="DATUM-L21-LB1") -> Result:
        """Start sampling the beams; believed_tcp() returns the robot's believed TCP position (world, m)."""
        if self.mode != "READY":
            return self._refuse("validate_tool_frame", f"mode {self.mode}")
        if not self.artifact_valid(datum_id):
            return self._refuse("validate_tool_frame", f"datum artifact {datum_id} not valid", fault="reference_expired")
        self._check = {"tool_id": tool_id, "tcp": believed_tcp, "tip": tip_below_tcp, "phase": None,
                       "samples": {"z": [], "y": [], "x": []}, "t0": self.t, "datum_id": datum_id}
        self.mode = "BUSY"
        self._log("validate_tool_frame_accepted", tool_id=tool_id)
        return Result(True)

    def mark_phase(self, phase):
        if self._check:
            self._check["phase"] = phase

    def finish_tool_check(self) -> dict:
        c, self._check = self._check, None
        self.mode = "READY"
        d = self.frames["tool_calibration_frame"]
        res = qa.tcp_from_sweeps(c["samples"]["z"], c["samples"]["y"], c["samples"]["x"], d, c["tip"])
        ok = bool(res.get("ok")) and all(abs(e) <= ACC_TCP["tol_mm"] for e in res["error_mm"])
        rec = {"qc_id": self._qc_id("TCP"), "kind": "tool_frame", "target": c["tool_id"], "t": round(self.t, 3),
               "reference_artifact_id": c["datum_id"], "acceptance_criterion_id": ACC_TCP["id"], "result": res,
               "verdict": "pass" if ok else "out_of_tolerance", "tolerance_mm": ACC_TCP["tol_mm"],
               "correction_mm": [-e for e in res.get("error_mm", [0, 0, 0])] if res.get("ok") else None,
               "samples": {k: len(v) for k, v in c["samples"].items()}, "date": self.today}
        self.tool_frames[c["tool_id"]] = {"qc_id": rec["qc_id"], "valid": ok, "date": self.today, "t": rec["t"],
                                          "error_mm": res.get("error_mm")}
        self.qc_records.append(rec)
        self._log("tool_frame_checked", tool_id=c["tool_id"], verdict=rec["verdict"], error_mm=res.get("error_mm"))
        self._write("state:last_check", f"{rec['qc_id']} {c['tool_id']} {rec['verdict']}")
        self._write("state:result", rec["verdict"])
        return rec

    def tool_frame_valid(self, tool_id):
        f = self.tool_frames.get(tool_id)
        if not f or not f["valid"]:
            return False
        age = (datetime.date.fromisoformat(self.today) - datetime.date.fromisoformat(f["date"])).days
        return age <= ACC_TCP["validity_days"]

    # ------------------------------------------------------------------ imager (validate_measurement_chain for L17)
    def validate_imager(self, l17, ref_id, objectives=None) -> Result:
        if self.mode != "READY":
            return self._refuse("validate_imager", f"mode {self.mode}")
        if not self.artifact_valid(ref_id):
            return self._refuse("validate_imager", f"reference artifact {ref_id} missing or expired "
                                                   f"(valid until {self.artifacts.get(ref_id, {}).get('valid_until')})",
                                fault="reference_expired")
        if l17.mode != "LOADED" or l17.plate_id != ref_id:
            return self._refuse("validate_imager", f"L17 must hold the verified reference {ref_id} (L17 mode "
                                                   f"{l17.mode}, plate {l17.plate_id!r})")
        self.mode = "BUSY"
        self._job = self._seq_validate_imager(l17, ref_id, objectives or ACC_IMG["objectives"])
        self._log("validate_imager_accepted", device="L17", reference=ref_id)
        return Result(True)

    def _wait_l17(self, l17, timeout=120.0):
        t0 = self.t
        while l17.mode == "BUSY":
            if self.t - t0 > timeout:
                raise RuntimeError("L17 did not finish")
            yield

    def _seq_validate_imager(self, l17, ref_id, objectives):
        cert = self.artifacts[ref_id]["certified"]
        identity = {"read_by_L17_at_load": l17.plate_id, "expected": ref_id,
                    "events": [e for e in l17.events if e["event"] == "identity_read"][-1:]}
        per = {}
        old = dict(l17.calibration)
        for mag in objectives:
            af = []
            for _ in range(ACC_IMG["af_repeats"]):
                l17.autofocus(ref_id, ACC_IMG["wells"][0], mag, fresh=True)
                yield from self._wait_l17(l17)
                run = l17.autofocus_runs[-1]
                af.append(run.get("focus_mm") if run.get("ok") else None)
            meas = []
            for well in ACC_IMG["wells"]:
                n0 = len(l17.acquisitions)
                r = l17.image_well(ref_id, well, 25.0, mag, "autofocus", 1.0, "qc-reference", purpose="qc")
                if not r.accepted:
                    raise RuntimeError(f"L17 refused the QC acquisition: {r.reason}")
                yield from self._wait_l17(l17)
                if len(l17.acquisitions) == n0:
                    raise RuntimeError("no QC acquisition recorded")
                a = qa.analyse_grid(l17.images[n0], cert["pitch_um"])
                a.update(well=well, acquisition=n0, raw_image_reference=l17.acquisitions[n0]["raw_image_reference"])
                meas.append(a)
            per[mag] = self._judge(mag, af, meas, old)
        rec = self._imager_verdict(l17, ref_id, identity, per, old)
        self.mode = "READY"
        return rec

    def _judge(self, mag, af, meas, old):
        A = ACC_IMG
        ok_meas = [m for m in meas if m.get("ok")]
        claimed = old["objectives"].get(mag, {}).get("pixel_um")
        if len(ok_meas) != len(meas) or None in af or claimed is None:
            return {"magnification": mag, "measurements": meas, "autofocus_mm": af, "ok": False,
                    "checks": {"analysis": False}, "recalibratable": False}
        px = float(np.mean([m["pixel_um"] for m in ok_meas]))
        scale = px / claimed - 1.0
        rep = float(np.std(np.array(af) * 1e3))
        checks = {
            "pixel_scale": abs(scale) <= A["pixel_scale_tol"],
            "isotropy": all(abs(m["isotropy"]) <= A["isotropy_tol"] for m in ok_meas),
            "orientation": all(abs(m["orientation_deg"]) <= A["orientation_tol_deg"] for m in ok_meas),
            "brightness": all(abs(m["brightness_fs"] / A["brightness_nominal_fs"] - 1) <= A["brightness_tol"]
                              for m in ok_meas),
            "autofocus_repeatability": rep <= A["af_repeat_um"][mag],
        }
        recal = (not checks["pixel_scale"]) and abs(scale) <= A["recal_band"] and \
            all(v for k, v in checks.items() if k != "pixel_scale")
        return {"magnification": mag, "measurements": meas, "autofocus_mm": af, "pixel_um_measured": round(px, 5),
                "pixel_um_claimed": claimed, "pixel_scale_error": round(scale, 5),
                "autofocus_repeatability_um": round(rep, 3), "checks": checks, "ok": all(checks.values()),
                "recalibratable": recal}

    def _imager_verdict(self, l17, ref_id, identity, per, old):
        qc_id = self._qc_id("IMG")
        ok = all(p["ok"] for p in per.values())
        recal = not ok and all(p["ok"] or p["recalibratable"] for p in per.values())
        verdict = "pass" if ok else ("out_of_tolerance_recalibrated" if recal else "out_of_tolerance")
        rec = {"qc_id": qc_id, "kind": "imager", "target": "L17", "t": round(self.t, 3), "date": self.today,
               "reference_artifact_id": ref_id, "reference": self.artifacts[ref_id],
               "acceptance_criterion_id": ACC_IMG["id"], "acceptance": ACC_IMG, "identity": identity,
               "device_configuration": {"calibration_as_found": old["calibration_id"],
                                        "objectives": {m: dict(o) for m, o in l17.objectives.items()}},
                                        "per_objective": per, "verdict": verdict, "calibration_issued": None,
               "invalidated_acquisitions": []}
        if not ok:
            bad = [m for m, p in per.items() if not p["ok"]]
            rec["invalidated_acquisitions"] = l17.invalidate_calibration(
                f"{qc_id}: {verdict} ({', '.join(f'{m}: ' + ','.join(k for k, v in per[m]['checks'].items() if not v) for m in bad)})",
                qc_id, magnifications=bad)
        if ok or recal:
            cal = self._issue_calibration(qc_id, ref_id, per, old, provisional=recal)
            rec["calibration_issued"] = cal["calibration_id"]
            l17.apply_calibration(cal, by=f"L21 {qc_id}")
        self.qc_records.append(rec)
        self._log("imager_validated", qc_id=qc_id, verdict=verdict, calibration_issued=rec["calibration_issued"])
        self._write("state:last_check", f"{qc_id} L17 {verdict}")
        self._write("state:result", verdict)
        self._write("state:calibration_status", "valid" if ok else ("recalibrated" if recal else "invalid"))
        return rec

    def _issue_calibration(self, qc_id, ref_id, per, old, provisional):
        today = datetime.date.fromisoformat(self.today)
        k = len(self.calibrations) + 1
        cal = {"calibration_id": f"L17-CAL-{self.today}-L21-{k:02d}",
               "source": f"L21 validate_imager {qc_id} (reference {ref_id}, {ACC_IMG['id']})",
               "issued": self.today, "status": "valid",
               "valid_until": (today + datetime.timedelta(days=ACC_IMG["validity_days"])).isoformat(),
               "objectives": {m: {"pixel_um": p["pixel_um_measured"], "focus_floor": ACC_IMG["focus_floor"][m]}
                              for m, p in per.items()},
               "sensor": old["sensor"], "stage_offset_mm": old.get("stage_offset_mm", [0.0, 0.0]),
               "qc_record": qc_id, "recalibrated": provisional,
               "note": "recalibrated scale: confirm with a second validate_imager (as-left)" if provisional else ""}
        self.calibrations.append(cal)
        return cal

    # ------------------------------------------------------------------ loop / outputs
    def update(self, dt=None):
        self.t += self.dt if dt is None else dt
        if dt:
            self.dt = dt
        if self._check and self._check["phase"]:
            c = self._check
            p = np.asarray(c["tcp"](), float)
            axis = {"z": 2, "y": 1, "x": 0}[c["phase"]]
            beam = "B" if c["phase"] == "x" else "A"
            c["samples"][c["phase"]].append((float(p[axis]), self.beam_blocked(beam)))
        if self._job is not None:
            try:
                next(self._job)
            except StopIteration:
                self._job = None
            except RuntimeError as exc:
                self._job = None
                self.mode = "FAULT"
                self._log("fault", fault="qc_sequence_failed", detail=str(exc))
        self._outputs()

    def _outputs(self):
        self._write("state:mode", self.mode)
        self._write("state:reference_artifact", "available" if self.nest_state("reference_plate_frame")["plate_on_nest"]
                    else "in use / not in its nest")
        for lens, on in (("LensGreen", self.mode == "READY"), ("LensAmber", self.mode == "BUSY"),
                         ("LensRed", self.mode == "FAULT")):
            a = self.stage.GetPrimAtPath(f"{self.root}/Looks/{lens}/Shader")
            if a:
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

    def _qc_id(self, kind):
        self._n += 1
        return f"QC-L21-{self.today}-{kind}-{self._n:03d}"

    def _log(self, event, **d):
        self.events.append({"t": round(self.t, 4), "event": event, "mode": self.mode, **d})

    def _refuse(self, cmd, reason, fault=None):
        self._log(f"{cmd}_refused", reason=reason)
        if fault:
            self._log("fault_signal", fault=fault)
        return Result(False, reason)

    def save(self, path):
        with open(path, "w") as f:
            json.dump({"component": "L21", "events": self.events, "qc_records": self.qc_records,
                       "calibrations": self.calibrations, "tool_frames": self.tool_frames}, f, indent=2, default=str)


def qc_designator(rec, episode_id, tool_frame_ok, tool_id="T01"):
    """Raw `qc` designator for twin/episode_records.py from an L21 QC record."""
    if rec["kind"] == "imager":
        per = rec["per_objective"]
        ident_ok = rec["identity"]["read_by_L17_at_load"] == rec["reference_artifact_id"]
        rep = {m: p.get("autofocus_repeatability_um") for m, p in per.items()}
        rep_ok = all(p["checks"].get("autofocus_repeatability", False) for p in per.values())
        cal_ok = rec["verdict"] == "pass"
        mons = [
            dict(name="reference_identity", passed=ident_ok, observation=f"L17 barcode read {rec['identity']['read_by_L17_at_load']!r}; "
                 f"artifact {rec['reference_artifact_id']} lot {rec['reference']['lot']} valid until "
                 f"{rec['reference']['valid_until']}", value=rec["reference_artifact_id"]),
            dict(name="calibration_state", passed=cal_ok, observation=f"L17 as found ({rec['device_configuration']['calibration_as_found']}) "
                 f"{rec['verdict']}: " + "; ".join(f"{m} scale error {p.get('pixel_scale_error')}, checks "
                                                    f"{ {k: v for k, v in p['checks'].items()} }" for m, p in per.items()),
                 value={m: p.get("pixel_scale_error") for m, p in per.items()}),
            dict(name="measurement_repeatability", passed=rep_ok, observation=f"autofocus repeatability (std, um) {rep} "
                 f"vs {ACC_IMG['af_repeat_um']}", value=rep),
            dict(name="tool_frame_validity", passed=tool_frame_ok, observation=f"{tool_id} (moved the reference plate) "
                 "frame validated on the L21 light barrier" if tool_frame_ok else f"{tool_id} frame not validated",
                 value=tool_id),
        ]
        target = "L17 (10x, 4x imaging chain)"
        frame = "reference_plate_frame"
    else:
        ok = rec["verdict"] == "pass"
        mons = [
            dict(name="reference_identity", passed=True, observation=f"datum {rec['reference_artifact_id']} (L21 fixture)",
                 value=rec["reference_artifact_id"]),
            dict(name="calibration_state", passed=ok, observation=f"TCP error {rec['result'].get('error_mm')} mm vs "
                 f"tolerance {rec['tolerance_mm']} mm", value=rec["result"].get("error_mm")),
            dict(name="measurement_repeatability", passed=rec["result"].get("ok", False),
                 observation=f"beam runs z/y/x {rec['result'].get('z_runs')}/{rec['result'].get('y_runs')}/"
                             f"{rec['result'].get('x_runs')} (expected >=1/2/1)", value=rec["samples"]),
            dict(name="tool_frame_validity", passed=ok, observation=f"{rec['target']} frame "
                 f"{'valid' if ok else 'INVALID: correction ' + str(rec['correction_mm']) + ' mm'}", value=rec["target"]),
        ]
        target = rec["target"]
        frame = "tool_calibration_frame"
    return {
        "id": f"{episode_id}/qc_{rec['qc_id'].split('-')[-2].lower()}_{rec['qc_id'].split('-')[-1]}", "action": "qc",
        "component": "L21_QC_Calibration", "interaction_frames": {"reference_frame": frame},
        "bindings": {"qc_target_id": target, "qc_component_id": "L21", "reference_artifact_id": rec["reference_artifact_id"],
                     "acceptance_criterion_id": rec["acceptance_criterion_id"]},
        "monitors": mons, "command_completed": True, "t_start": rec["t"], "t_end": rec["t"],
        "semantic_target": "EvidenceLayer.measurement_binding_validity",
        "semantic_effect": f"{target}: {rec['verdict']}" + (f"; calibration {rec.get('calibration_issued')} issued"
                                                            if rec.get("calibration_issued") else ""),
        "failure_route": "invalidate_dependent_measurements", "failure_target": "EvidenceLayer",
        "commit_route": "evidence_layer_commit", "commit_target": "EvidenceLayer",
        "evidence": {"qc_target_id": target, "reference_artifact_id": rec["reference_artifact_id"],
                     "verdict": rec["verdict"], "timestamps": {"checked": rec["t"]}},
        "qc_record": rec,
    }
