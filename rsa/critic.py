"""The experimental critic: a two-column verdict computed from the audit trail alone (KERNEL.md concept 11).

Realization (did it run correctly and safely) and validity (is the result interpretable) are judged separately; a
result may update the culture belief only if both hold (D009); realization without validity is NR3 (uc_ccr).
The critic reads the serialised trail, not the executor's state -- an auditor can recompute it (RobAuditor-style
verifier: decision, confidence, explanation).
"""

from __future__ import annotations

from typing import Any, Dict, List


def _entries(trail, **kw):
    return [e for e in trail["entries"] if all(e.get(k) == v for k, v in kw.items())]


def _ev(e, kind):
    return next((x["value"] for x in e.get("evidence") or [] if x["kind"] == kind), None)


def assess(trail: Dict[str, Any], tolerance_pct: float = 5.0) -> Dict[str, Any]:
    root_open = next(e for e in trail["entries"] if e["category"] == "experiment" and e["transition"] == "grounded") \
        if any(e["category"] == "experiment" and e["transition"] == "grounded" for e in trail["entries"]) else None
    exp_open = next((e for e in trail["entries"] if e["category"] == "experiment" and e["transition"] == "open"), None)
    final = [e for e in trail["entries"] if e["category"] == "experiment"][-1]
    design = (root_open or {}).get("bindings") or {}
    plate = design.get("plate", "P17")
    roles = design.get("wells", {})
    sessions = design.get("sessions", [])

    # ------------------------------------------------------------------ realization column
    viol = sorted({c["id"] for e in trail["entries"] for c in e.get("constraints") or []
                   if c.get("verdict") == "VIOLATED" and c.get("column") == "realization"})
    ended = final["transition"]
    realization = dict(ok=not viol and ended in ("executed", "repaired"), violated=viol, run_ended=ended)

    # ------------------------------------------------------------------ validity column
    reads = [_ev(e, "barcode_read") for e in _entries(trail, category="verify_identity")]
    v = {}
    idr = [r["read"] for r in reads if r]
    mism = [e for e in trail["entries"] if e["category"] == "verify_identity" and any(
        m["name"] == "plate_identity" and not m["passed"] for m in e.get("monitors") or [])]
    v["V1_identity_continuity"] = (not mism and all(r == plate for r in idr),
                                   f"identity reads {idr}" + (f"; mismatch at seq {[e['seq'] for e in mism]}" if mism else ""))
    imgs = [e for e in _entries(trail, category="image_well", transition="executed")]
    cal_ok = all(any(m["name"] == "calibration_state" and m["passed"] for m in e.get("monitors") or []) for e in imgs)
    v["V2_calibration_at_measurement"] = (bool(imgs) and cal_ok, f"{len(imgs)} readouts, calibration observed valid "
                                          f"for {'all' if cal_ok else 'not all'}")
    binds = [c for e in trail["entries"] for c in e.get("constraints") or [] if c["id"] == "measurement_binding_validated"]
    v["V3_binding_validated"] = (bool(binds) and all(c["verdict"] == "ENFORCED" for c in binds),
                                 "; ".join(sorted({c["observation"] for c in binds})) or "no readout")
    imaged = sorted({_ev(e, "well") for e in imgs})
    ctrl = [w.upper() for w in roles.get("control", [])]
    v["V4_controls_present"] = (bool(ctrl) and set(ctrl) <= set(imaged), f"control {ctrl}, imaged {imaged}")
    disp = []
    for e in _entries(trail, category="dispense", transition="executed"):
        disp.append(dict(well=_ev(e, "well"), reagent=_ev(e, "reagent"), t_h=_ev(e, "culture_time_h"),
                         cmd=_ev(e, "volume_commanded_uL"), got=_ev(e, "volume_delivered_uL")))
    designed_doses = [(m[1].upper(), m[2], s["t_h"]) for s in sessions for m in s["material"] if m[0] == "dose"]
    designed_imgs = [(m[1].upper(), s["t_h"]) for s in sessions for m in s["material"] if m[0] == "image"]
    tol_ok = all(d["cmd"] and abs(d["got"] - d["cmd"]) <= tolerance_pct / 100 * d["cmd"] for d in disp)
    v["V5_dose_delivered"] = (bool(disp) and tol_ok, f"{len(disp)} dispenses within {tolerance_pct} %: {tol_ok}")
    win = [c for e in trail["entries"] for c in e.get("constraints") or [] if c["id"] == "window_kept" and
           c["verdict"] == "VIOLATED"]
    v["V6_sample_integrity"] = (not win, "window kept on every trip" if not win else f"window violated: {win[0]['observation']}")
    done_d = {(d["well"], d["reagent"], d["t_h"]) for d in disp}
    img_t = {(_ev(e, "well"), (_ev(e, "image") or {}).get("t_h")) for e in imgs}
    miss = [x for x in designed_doses if x not in done_d] + [x for x in designed_imgs if x not in img_t]
    v["V7_design_realised"] = (not miss, "all designed interventions and measurements executed" if not miss
                               else f"missing {miss}")
    acc = [c for e in trail["entries"] for c in e.get("constraints") or []
           if c.get("column") == "validity" and c.get("verdict") == "VIOLATED" and c["id"] not in
           ("measurement_binding_validated",)]
    validity_ok = all(ok for ok, _ in v.values()) and not acc
    validity = dict(ok=validity_ok, checks={k: dict(ok=ok, observation=o) for k, (ok, o) in v.items()},
                    refused_by=sorted({c["id"] for c in acc}))
    promotable = realization["ok"] and validity_ok
    nr3 = realization["ok"] and not validity_ok
    if promotable:
        disposition = "commit: result may update the culture belief"
    elif ended == "abstained":
        disposition = "refused before execution"
    elif any(e["transition"] == "escalated" for e in trail["entries"]):
        disposition = "escalated: human decision required; nothing committed"
    elif nr3:
        disposition = "NR3: physically realised but not valid evidence; nothing committed"
    else:
        disposition = "failed: nothing committed"
    return dict(realization=realization, validity=validity, promotable=promotable, nr3=nr3, disposition=disposition,
                design=dict(id=design.get("design"), requirement_bits=design.get("requirement_bits"),
                            eig_bits=design.get("eig_bits")))
