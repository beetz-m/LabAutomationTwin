"""Evidence records for Cell 01 CRAM/SDT episodes run in the twin (NEEM-compatible, per the Cell 01 sdt/schemas).

Input: the raw log written by scripts/run_cell01_episode.py. Per designator it holds the bindings, interaction
frames, monitor observations (name, passed, observation, value) taken from the simulated devices, command
completion, timestamps, evidence outputs and, on failure, the route the executive chose.

Output: one record per designator following sdt/schemas/neem_record_schema.yaml. The critic vector is derived from
sdt/schemas/monitor_templates.yaml: a failed monitor clears the critic dimensions in its critic_effects and blocks
its failure_blocks paths. Missing monitors, missing evidence outputs or unresolved bindings make the record
incomplete. validate() checks every record against the NEEM, critic-vector and designator schemas and the
schema invariants.

Cell 01's own helpers (simulation/isaac_sim/biophysical_v2/physical_workflow.py: SDT grounding, schema loaders,
MonitorResult, build_h4_quarantine_request) are imported read-only, without writing bytecode into ResearchSpace.
No Isaac Sim dependency: python -m twin.episode_records test_reports/episodes/cell01_episodes_raw.json
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import yaml

CELL01_ROOT = Path(os.path.expanduser(
    "~/ResearchSpace/projects/robot-scientist/cell-01/AICOR_Cell01_Codex_Handoff"))
CRITICS = ("physical_success", "safety_ok", "quality_ok", "grounding_ok", "experimental_validity_ok",
           "measurement_adequacy_ok", "evidence_complete")
COMMIT_REQUIRES = ("physical_success", "grounding_ok", "safety_ok", "quality_ok", "experimental_validity_ok",
                   "evidence_complete")
COMMIT_ROUTE = "culture_sdt_commit"


def _load_physical_workflow(root: Path):
    spec = importlib.util.spec_from_file_location(
        "cell01_physical_workflow", root / "simulation/isaac_sim/biophysical_v2/physical_workflow.py")
    mod = importlib.util.module_from_spec(spec)
    dont = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # Cell 01 is read-only from here
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = dont
    return mod


class Schemas:
    def __init__(self, root: Path = CELL01_ROOT):
        self.root = root
        self.pw = _load_physical_workflow(root)
        s = root / "sdt/schemas"
        self.neem = yaml.safe_load((s / "neem_record_schema.yaml").read_text())
        self.critic = yaml.safe_load((s / "critic_vector_schema.yaml").read_text())
        self.designators = yaml.safe_load((s / "cram_designator_schemas.yaml").read_text())["designators"]
        self.templates = self.pw.load_monitor_templates(root)


def build_record(sch: Schemas, episode_id: str, d: dict) -> dict:
    """One NEEM-compatible record for a raw designator entry d."""
    pw = sch.pw
    action = d["action"]
    schema = sch.designators[action]
    g = pw.load_sdt_grounding(sch.root, d["component"])
    frames = {k: g.require_frame(v) for k, v in d["interaction_frames"].items()}
    monitors = [pw.MonitorResult(m["name"], bool(m["passed"]), m["observation"], m.get("value")) for m in d["monitors"]]
    obs = {m.name: m for m in monitors}
    required = list(schema["monitors"])
    missing = [n for n in required if n not in obs]
    failed = [n for n in required if n in obs and not obs[n].passed]
    designator = {"component_id": g.component_id, "component_prim": g.component_prim, **d["bindings"]}
    unresolved = [b for b in schema["required_bindings"] if designator.get(b) in (None, "", [])]
    evidence = {k: d["evidence"].get(k, designator.get(k)) for k in schema["evidence_outputs"]}
    missing_evidence = [k for k, v in evidence.items() if v in (None, "", [])]

    cv = {k: True for k in CRITICS}
    cv["measurement_adequacy_ok"] = None  # transfer / storage / containment actions produce no measurement evidence
    reasons = []
    for n in failed:
        for eff in sch.templates[n]["critic_effects"]:
            if cv.get(eff) is not None:
                cv[eff] = False
        reasons.append(f"failed monitor {n}: {obs[n].observation}")
    if not d["command_completed"]:
        cv["physical_success"] = False
        reasons.append("device command did not complete")
    if unresolved:
        cv["grounding_ok"] = False
        reasons.append("missing designator bindings: " + ", ".join(unresolved))
    if missing:
        cv["grounding_ok"] = cv["evidence_complete"] = False
        reasons.append("missing monitor evidence: " + ", ".join(missing))
    if missing_evidence:
        cv["evidence_complete"] = False
        reasons.append("missing evidence outputs: " + ", ".join(missing_evidence))
    commit = all(cv[k] for k in COMMIT_REQUIRES)
    blocked = sorted({b for n in failed for b in sch.templates[n]["failure_blocks"]}
                     | (set() if commit else {"semantic_event_commit"}))
    cv.update(commit_semantic_event=commit, failure_reasons=reasons, blocked_paths=blocked)

    route = COMMIT_ROUTE if commit else d.get("failure_route") or "human_escalation"
    target = "CultureSDT" if commit else d.get("failure_target") or "human"
    checks = {
        "grounded": not unresolved and not missing,
        "semantic_valid": not failed,
        "causally_admissible": d["command_completed"],
        "motion_feasible": d["command_completed"],
        "monitorable": not missing,
        "evidence_supported": not missing and not missing_evidence,
    }
    commitment = {"accepted": commit, "acceptance_checks": checks, "failure_reasons": reasons, "blocked_paths": blocked}
    lifecycle = {
        "open_designator": {"action": action, "requested_bindings": sorted(schema["required_bindings"]),
                            "unresolved_bindings": unresolved},
        "grounded_designator": {"component_id": g.component_id, "component_prim": g.component_prim,
                                "interaction_frames": frames, "grounded_bindings": designator},
        "commitment": commitment,
        "execution": {"command_completed": d["command_completed"], "physical_success": cv["physical_success"],
                      "timestamp_s": d["t_end"], "t_start_s": d["t_start"], "device_events": d.get("device_events", [])},
        "monitors": {"required": required, "observed": [m.__dict__ for m in monitors], "missing": missing,
                     "failed": failed},
        "failures": {"reasons": reasons, "blocked_paths": blocked},
        "repairs": {"attempted": d.get("repairs_attempted", []), "available_routes": list(schema["failure_routing"])},
        "verdict": {"critic_vector": cv, "semantic_event_eligible": commit, "evidence_complete": cv["evidence_complete"]},
        "routing": {"route": route, "target": target},
    }
    return {
        "episode_id": episode_id,
        "designator_id": d["id"],
        "event_type": f"{g.component_id}.{action}",
        "timestamp_s": d["t_end"],
        "lifecycle": lifecycle,
        "designator": designator,
        "monitors": [m.__dict__ for m in monitors],
        "critic_vector": cv,
        "commitment_acceptance": commitment,
        "semantic_event": {"eligible": commit, "target": d["semantic_target"], "effect": d.get("semantic_effect", "")},
        "routing": route,
        "evidence": evidence,
        "provenance": {"source": "LabAutomationTwin Isaac Sim twin (simulated devices)", **d.get("provenance", {})},
    }


def quarantine_request(sch: Schemas, record: dict, *, sample_id: str, reason: str, execution: dict) -> dict:
    """Cell 01's H4 request (physical_workflow.build_h4_quarantine_request), bound to the identity actually observed
    and carrying the outcome of its physical execution."""
    req = sch.pw.build_h4_quarantine_request({**record, "designator": {"plate_id": sample_id, **record["designator"]}},
                                             root=sch.root, reason=reason)
    req["sample_id"] = sample_id
    req["expected_sample_id"] = record["designator"].get("object_id")
    req["physical_execution"] = execution
    return req


def validate(sch: Schemas, rec: dict) -> list[str]:
    """Schema and invariant checks (cf. Cell 01 tools/validate_handoff.py for the L12/L17 demo records)."""
    err = []
    for f in sch.neem["required_top_level_fields"]:
        if f not in rec:
            err.append(f"missing NEEM field {f}")
    lc = rec.get("lifecycle", {})
    for sec in sch.neem["lifecycle"]["required_sections"]:
        if sec not in lc:
            err.append(f"lifecycle missing section {sec}")
            continue
        for f in sch.neem["section_contracts"][sec]["required_fields"]:
            if f not in lc[sec]:
                err.append(f"lifecycle {sec} missing field {f}")
    for f in sch.critic["required_fields"]:
        if f not in rec["critic_vector"]:
            err.append(f"critic vector missing {f}")
    if "quarantine_request" in rec:
        for f in sch.neem["section_contracts"]["quarantine_request"]["required_fields"]:
            if f not in rec["quarantine_request"]:
                err.append(f"quarantine_request missing {f}")
    action = lc.get("open_designator", {}).get("action")
    schema = sch.designators.get(action)
    if schema is None:
        return err + [f"unknown designator action {action!r}"]
    cv = rec["critic_vector"]
    # invariants (neem_record_schema.yaml, critic_vector_schema.yaml)
    if cv["commit_semantic_event"] and not all(cv[k] for k in COMMIT_REQUIRES):
        err.append("commit_semantic_event without grounding/safety/quality/validity/evidence")
    if not rec["semantic_event"]["eligible"] and rec["routing"] == COMMIT_ROUTE:
        err.append("ineligible semantic event routed to Culture SDT commit")
    for n in lc["monitors"]["failed"]:
        for where, reasons in (("failures.reasons", lc["failures"]["reasons"]),
                               ("commitment.failure_reasons", rec["commitment_acceptance"]["failure_reasons"])):
            if not any(n in r for r in reasons):
                err.append(f"failed monitor {n} absent from {where}")
    if cv["commit_semantic_event"]:
        for b in schema["required_bindings"]:
            if rec["designator"].get(b) in (None, "", []):
                err.append(f"committed record lacks binding {b}")
        for m in schema["monitors"]:
            if m not in {o["name"] for o in rec["monitors"]}:
                err.append(f"committed record lacks monitor {m}")
    gd = lc["grounded_designator"]
    if not gd.get("component_prim") or not gd.get("interaction_frames"):
        err.append("record lacks grounded component / interaction-frame provenance")
    if rec["commitment_acceptance"]["accepted"] != cv["commit_semantic_event"]:
        err.append("commitment acceptance disagrees with the critic vector")
    return err


def build_all(raw: dict, sch: Schemas | None = None) -> dict:
    """Records for every episode in a raw log, plus their validation results."""
    sch = sch or Schemas()
    out = {"run": raw["run"], "episodes": []}
    for ep in raw["episodes"]:
        recs = []
        for d in ep["designators"]:
            rec = build_record(sch, ep["episode_id"], d)
            q = d.get("quarantine")
            if q:
                rec["quarantine_request"] = quarantine_request(sch, rec, sample_id=q["sample_id"], reason=q["reason"],
                                                               execution=q["execution"])
            recs.append(rec)
        errors = {r["designator_id"]: validate(sch, r) for r in recs}
        out["episodes"].append({k: v for k, v in ep.items() if k != "designators"} | {
            "records": recs, "validation": {"errors": {k: v for k, v in errors.items() if v},
                                            "records_checked": len(recs),
                                            "pass": not any(errors.values())}})
    return out


def main(argv):
    raw_path = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[1] / \
        "test_reports/episodes/cell01_episodes_raw.json"
    out = build_all(json.loads(raw_path.read_text()))
    dst = raw_path.with_name(raw_path.name.replace("_raw", "_records"))
    dst.write_text(json.dumps(out, indent=2, default=str))
    for ep in out["episodes"]:
        print(f"{ep['episode_id']}: " + ", ".join(
            f"{r['event_type']}={'commit' if r['semantic_event']['eligible'] else r['routing']}" for r in ep["records"])
            + f"  validation {'PASS' if ep['validation']['pass'] else ep['validation']['errors']}")
    print(f"wrote {dst}")
    return 0 if all(ep["validation"]["pass"] for ep in out["episodes"]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
