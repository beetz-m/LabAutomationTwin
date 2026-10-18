"""Constraint checks, policies and the understanding gate (KERNEL.md concepts 8, 12).

Every check reads the knowledge base and the assistant's *belief* (observations with provenance), never the backend's
ground truth: what the assistant may claim is what it has evidence for.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .core import Context, Designator, Node, Policy

FAILURE_CODE = dict(window_kept="window_exceeded", l12_airspace_clear="airspace_occupied")


def registry(ctx: Context) -> Dict[str, Dict[str, Any]]:
    return ctx.kb.registry.get("constraints") or {}


def column(ctx: Context, cid: str) -> str:
    return registry(ctx).get(cid, {}).get("column", "realization")


def failure_code(ctx: Context, cid: str) -> str:
    return FAILURE_CODE.get(cid, "constraint_violated")


def applicable(ctx: Context, category: str, phase: str) -> List[str]:
    return [cid for cid, c in registry(ctx).items() if c.get("phase") == phase and category in (c.get("applies_to") or [])]


# ----------------------------------------------------------------------------------------------------- checks
def _ok(b: bool, obs: Any) -> Tuple[str, Any]:
    return ("ENFORCED" if b else "VIOLATED"), obs


def c_interlocks_closed(ctx, node):
    return _ok(ctx.kb.holds("interlocks_closed"), "fact interlocks_closed" if ctx.kb.holds("interlocks_closed")
               else "no interlocks_closed fact")


def _projection(ctx, node):
    if getattr(node, "projection", None) is None:
        import copy
        pr = ctx.project(copy.copy(node.designator))
        node.projection = dict(duration_s=pr["duration_s"], ok=pr["ok"], reason=pr["reason"])
    return node.projection


def c_projection_succeeds(ctx, node):
    if ctx.projecting:
        return "NOT_EVALUATED", "inside projection"
    pr = _projection(ctx, node)
    return _ok(pr["ok"], f"projected to completion in {pr['duration_s']} s" if pr["ok"]
               else f"projection failed after {pr['duration_s']} s: {pr['reason']}")


def c_window_prospective(ctx, node):
    if ctx.projecting:
        return "NOT_EVALUATED", "inside projection"
    pr = _projection(ctx, node)
    if not pr["ok"]:
        return "NOT_EVALUATED", "no complete projection (see projection_succeeds)"
    w, m = ctx.kb.window_s()
    need = round(pr["duration_s"] * (100 + m) / 100.0, 2)
    return _ok(need <= w, f"projected {pr['duration_s']} s x {(100 + m) / 100:.2f} = {need} s "
                          f"{'<=' if need <= w else '>'} window {w} s")


def c_contamination_free(ctx, node):
    sus = ctx.kb.holds("contamination_suspected")
    return _ok(not sus, "contamination_suspected" if sus else "no contamination_suspected fact")


def c_reagent_bound(ctx, node):
    d = node.designator
    rec = ((ctx.kb.registry.get("devices") or {}).get("reagents") or {}).get(d.reagent)
    pose = ctx.kb.reagent_pose(d.reagent)
    return _ok(bool(rec and pose.ok), f"{d.reagent}: lot {rec['lot'] if rec else None} at {pose.value}")


def c_calibration_before_imaging(ctx, node):
    dev = getattr(node, "bound_device", None)
    believed = ctx.belief.get(f"calibrated:{dev}")
    planned = "calibrate" in (getattr(node, "planned", []) or [])
    return _ok(bool(believed) or planned, f"belief calibrated({dev})={believed} ({ctx.belief.source(f'calibrated:{dev}')})"
               + ("; calibrate planned first" if planned else ""))


def c_tool_compatible(ctx, node):
    t = node.designator.tool
    bad = ctx.kb.holds("contacts_culture", t) and not ctx.kb.holds("compatible", t)
    return _ok(not bad, f"tool {t}: contacts_culture={ctx.kb.holds('contacts_culture', t)}")


def c_challenge_requires_controls(ctx, node):
    roles = node.designator.wells
    challenge = any(m[0] == "dose" and m[2] == "challenge" for s in node.designator.sessions for m in s["material"])
    return _ok(not challenge or bool(roles.get("control")), f"challenge={challenge}, control wells={roles.get('control')}")


def c_identity_verified(ctx, node):
    seen = ctx.belief.get("identity_read")
    return _ok(seen == node.designator.plate.id, f"read {seen}, expected {node.designator.plate.id} "
                                                 f"({ctx.belief.source('identity_read')})")


def c_environment_before_store(ctx, node):
    ok = any(c.designator.category == "wait_environment" and c.status == "succeeded" for c in node.children)
    return _ok(ok, "wait_environment executed before store" if ok else "no accepted environment before store")


def c_dispense_completed(ctx, node):
    disp = [c for c in node.children if c.designator.category == "dispense" and c.status == "succeeded"]
    if not disp:
        return _ok(False, "no dispense executed")
    ev = {e["kind"]: e["value"] for e in disp[-1].observation.get("evidence", [])}
    dev = getattr(node, "bound_device", None)
    tol = ((ctx.kb.components.get(dev) or {}).get("_twin") or {}).get("volume_tolerance_pct", {}).get("value", 5)
    cmd, got = ev.get("volume_commanded_uL"), ev.get("volume_delivered_uL")
    ok = cmd is not None and got is not None and abs(got - cmd) <= tol / 100.0 * cmd
    return _ok(ok, f"delivered {got} uL of {cmd} uL (tolerance {tol} %)")


def c_measurement_binding_validated(ctx, node):
    dev = getattr(node, "bound_device", None)
    readout = ((ctx.kb.components.get(dev) or {}).get("_twin") or {}).get("readout", "organoid_radius_um")
    b = ctx.kb.measurement_binding(dev, readout)
    node.resolutions.append(b)
    return _ok(b.value == "validated", f"binding({dev},{readout}) = {b.value}")


CHECKS = {k[2:]: v for k, v in globals().items() if k.startswith("c_")}


def evaluate(ctx: Context, node: Node, phase: str) -> List[Dict[str, Any]]:
    out = []
    for cid in applicable(ctx, node.designator.category, phase):
        fn = CHECKS.get(cid)
        verdict, obs = fn(ctx, node) if fn else ("NOT_EVALUATED", "no check implemented")
        c = registry(ctx)[cid]
        out.append(dict(id=cid, column=c.get("column"), verdict=verdict, observation=obs, source=c.get("source")))
    return out


# ----------------------------------------------------------------------------------------------------- policies
def window_policy(ctx: Context) -> Policy:
    w, _ = ctx.kb.window_s()

    def check(c: Context, d: Optional[Designator], when: str):
        if when != "after" or c.projecting:      # in projection the window is predicted (window_prospective), F8
            return None, None
        owner = next(p.owner for p in c.policies if p.name == "window")
        # the window runs from the trip start (interlock check, as in the planner), preparation excluded (F11)
        ret = next((n for n in owner.children if n.designator.category != "calibrate"), None)
        if ret is None:
            return None, None
        el = round(c.clock - ret.t0, 2)
        return el <= w, f"{el} s outside the incubator (window {w} s)"
    return Policy("window", "window_kept", check)


def airspace_policy(ctx: Context, device: str, seat: str) -> Policy:
    def check(c: Context, d: Optional[Designator], when: str):
        if when != "before" or getattr(d, "device", None) != device:
            return None, None
        inside = [k.split(":")[1] for k, (v, _, _) in c.belief.items.items() if k.startswith("pose:") and v == ["seat", seat]]
        return not inside, (f"robots in {device} airspace: {inside}" if inside else f"{device} airspace clear")
    return Policy(f"{device}_airspace", "l12_airspace_clear", check)


# ----------------------------------------------------------------------------------------------------- understanding
SLOTS = ["what", "target", "purpose", "mechanism", "preconditions", "realization", "expected_effects", "risks",
         "controls", "monitors", "recovery", "evidence"]


def understanding(ctx: Context, node: Node) -> Dict[str, Any]:
    """U(a) for a consequential designator (Cell 01 robot-understanding contract, B21/B22).

    Slots come from the category card (declared, possibly empty = 'none required'), the bindings, the resolutions and
    the purpose chain up to the experiment's requirement. A slot that is *undeclared* blocks acceptance.
    """
    d = node.designator
    card = ctx.card(d.category)
    if not card.get("consequential"):
        return dict(missing=[], slots={})
    chain = [d.category] + [a.designator.category for a in node.ancestors()]
    purposes = [ctx.card(a.designator.category).get("purpose") for a in [node] + node.ancestors()]
    realization = sorted({str(a.value) for a in node.resolutions if a.ok and a.query.startswith(("devices_for", "route"))})
    slots = dict(
        what=card.get("label"),
        target=d.objects() or None,
        purpose=[p for p in purposes if p] or None,
        mechanism=card.get("effect_class") or card.get("level"),
        preconditions=card.get("pre") if "pre" in card else None,
        realization=realization or [r.query for r in node.resolutions] or ["no device binding required"],
        expected_effects=card.get("effects"),
        risks=card.get("hazards") if "hazards" in card else None,
        controls=applicable(ctx, d.category, "accept") + applicable(ctx, d.category, "post")
        + applicable(ctx, d.category, "policy"),
        monitors=card.get("monitors") if "monitors" in card else None,
        recovery=card.get("recovery") if "recovery" in card else None,
        evidence=card.get("evidence"),
    )
    epistemic = {}
    pid = d.plate.id if getattr(d, "plate", None) is not None else None
    dev = getattr(node, "bound_device", None)
    for k in (f"plate_at:{pid}", f"calibrated:{dev}", "identity_read"):
        if k in ctx.belief.items:
            epistemic[k] = ctx.belief.source(k)
    slots["epistemic_state"] = epistemic
    missing = [s for s in SLOTS if slots.get(s) is None]
    return dict(missing=missing, slots=slots, chain=chain)
