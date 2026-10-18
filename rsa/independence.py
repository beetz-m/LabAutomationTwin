"""Show that the culture-level plan is independent of the laboratory: robots, devices, lab setup, safety constraints,
cleanliness and temperature control.

Two kinds of evidence:
  1. Vocabulary: the culture plan's text (registry/lab/culture_plan.ldl) contains no term of any realization
     vocabulary, collected from the knowledge itself (planner facts, Cell 01 component records, registries), and the
     culture-level derivation (rsa/culture_plan.derive) reads nothing but that text.
  2. Invariance: the same culture plan and the same lab plan (challenge_rescue.ldl) are run in many labs: variants of
     the knowledge with other robots, devices, layout, safety limits, cleanliness rules, environment profiles and
     calibration states. Per lab: the culture plan's hash and derived order, the lab plan's hash and derived order
     (identical by construction, and checked), and the realization the kernel builds (symbolic backend): devices,
     routes, trips, leaves, durations, and the outcome, which can be a refusal: a lab that cannot realize the plan.

    env_cad/bin/python -m rsa.independence       # rsa/out/independence.json
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
import tempfile

import yaml

from . import kb as KBM
from .ldl import LAB, OUT, World, check, parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def sha(t):
    return hashlib.sha256(t.encode()).hexdigest()[:12]


def atoms(x, out=None):
    out = set() if out is None else out
    if isinstance(x, list):
        for e in x:
            atoms(e, out)
    elif isinstance(x, str) and not x.startswith("?") and not x.startswith('"'):
        out.add(x.lower())
    return out


# ------------------------------------------------------------------------------------------------- 1. vocabulary
def realization_vocabularies(facts_text):
    from .kb import C01_COMPONENTS
    pred = lambda p: re.findall(p + r"\(([^)]*)\)", facts_text)  # noqa: E731
    args = lambda p, i: {a.split(",")[i].strip().lower() for a in pred(p)}  # noqa: E731
    comps = {f[:-5]: yaml.safe_load(open(os.path.join(C01_COMPONENTS, f))) for f in os.listdir(C01_COMPONENTS) if f.endswith(".yaml")}
    caps = {c.lower() for r in comps.values() for c in (r.get("capabilities") or [])}
    constraints = yaml.safe_load(open(os.path.join(HERE, "registry", "constraints.yaml")))
    norms = yaml.safe_load(open(os.path.join(HERE, "registry", "norms.yaml")))["clauses"]
    V = {
        "robots": args("serves", 0) | args("requires_tool", 0) | args("requires_tool", 1) | {
            "fr3", "ur5e", "gripper", "tcp", "end-effector", "arm", "rail", "joint", "tool_couple", "plate_grasp_frame"} |
            {k.lower() for k in comps if k.startswith("R0")},
        "devices": args("has_function", 0) | args("has_function", 1) | caps | {k.lower() for k in comps if k[0] in "LH" or k.startswith("Tool")} |
            {"liquid-handler", "incubator", "imager", "pipette", "plate-reader", "shuttle", "stage"},
        "lab setup": args("seat", 1) | args("holds_plate", 0) | args("serves", 1) | {"handovernest", "p17", "p30", "plate_p17", "slot", "nest", "layout",
            "bench"} | {f"{r}{c:02d}" for r in "abcdefgh" for c in range(1, 13)},
        "safety constraints": {k.lower() for k in constraints} | {k.lower() for k in norms} | {"interlock", "interlocks_closed", "airspace",
            "enclosure", "e-stop", "light-curtain", "window", "speed-limit", "collision"},
        "cleanliness": args("contacts_culture", 0) | {"contacts_culture", "tip", "tip_pick", "tip_eject", "sterile", "sterility", "waste",
            "clean", "contamination_class", "tool_compatible", "decontaminate", "hood"},
        "temperature control": {"temperature", "co2", "humidity", "setpoint", "celsius", "°c", "environment_valid", "wait_environment",
            "excursion_alarm", "maintain_environment", "report_environment", "temperature_excursion", "co2_excursion"},
    }
    return {k: sorted(v - {""}) for k, v in V.items()}


# ------------------------------------------------------------------------------------------------- 2. labs
LABS = [
    dict(id="cell01", dimension="(reference)", title="Cell 01 as built (layout P1)", edit=[]),
    dict(id="one-robot", dimension="robots", title="one rail robot serves every station (no R01, no handover)",
         edit=[("drop", r"serves\(r01,[^)]*\)\."), ("add", "serves(r02,l10).")]),
    dict(id="tool-kept", dimension="robots", title="R02 keeps its plate tool coupled between trips",
         edit=[("add", "coupled(r02,t01).")]),
    dict(id="hotel-handover", dimension="lab setup", title="R01 and R02 hand the plate over in the plate hotel L09, not a handover nest",
         edit=[("drop", r"serves\((r01|r02),handovernest\)\."), ("drop", r"holds_plate\(handovernest\)\."), ("add", "serves(r02,l09).")]),
    dict(id="imager-capability-only", dimension="devices", title="the imager replaced by a capability-matched model without a validated binding",
         components={"l17": "l17_generic"}),
    dict(id="imager-validated", dimension="devices", title="the imager replaced by another model with a validated binding for the readout",
         components={"l17": "l17_validated"}),
    dict(id="handler-replaced", dimension="devices", title="the liquid handler replaced by another model with the same capabilities",
         components={"l12": "l12_other"}),
    dict(id="window-300", dimension="safety constraints", title="the lab allows the plate only 300 s outside the incubator",
         edit=[("drop", r"window\(\d+\)\."), ("add", "window(3000).")]),
    dict(id="interlocks-open", dimension="safety constraints", title="the enclosure interlocks are open", edit=[("drop", r"interlocks_closed\.")]),
    dict(id="contamination-suspected", dimension="cleanliness", title="contamination is suspected on the plate", edit=[("add", "contamination_suspected.")]),
    dict(id="tool-contacts-culture", dimension="cleanliness", title="the lab classes the plate tool T01 as touching the culture", edit=[("add", "contacts_culture(t01).")]),
    dict(id="profile-mismatch", dimension="temperature control", title="the incubator keeps a different environment profile than culture-standard",
         profiles={"l10": "culture-30C"}),
    dict(id="uncalibrated", dimension="calibration", title="the imager's calibration is not current", edit=[("drop", r"calibrated\(l17\)\.")]),
]
PROFILES = {"l10": "culture-standard"}          # the lab's environment profiles (names only; setpoints are the lab's, D016)


def variant_facts(base, edits):
    t = base
    for op, x in edits:
        t = re.sub(x + r"\s*", "", t) if op == "drop" else t + "\n" + x + "\n"
    return t


def run_lab(lab, base_facts, exp_kernel, tmp):
    from .audit import AuditTrail
    from .backend import SymbolicWorld
    from .core import KERNEL_VERSION, Belief, Context, Failure, perform
    from .critic import assess
    from .run_example import registry_sha, scenario_kb
    tag = f"g050__{lab['id']}"
    open(os.path.join(tmp, f"facts_{tag}.lp"), "w").write(variant_facts(base_facts, lab.get("edit", [])))
    old = KBM.FACTS_DIR
    KBM.FACTS_DIR = tmp
    try:
        base = KBM.KB.load(tag)
        alts = base.registry["devices"].setdefault("alternative_components", {})
        alts.setdefault("l17_validated", dict(identity=dict(component_id="L17-alt3", canonical_name="Bright-field imager, other vendor (scenario)"),
                                              capabilities=["load_plate", "autofocus", "image_well", "export_raw_image"]))
        alts.setdefault("l12_other", dict(identity=dict(component_id="L12-alt", canonical_name="Liquid handler, other vendor (scenario)"),
                                          capabilities=["pick_tip", "aspirate", "dispense", "dose_well", "eject_tip", "detect_liquid_surface"]))
        base.registry["devices"]["measurement_bindings"].setdefault("L17-alt3", {"organoid_radius_um": {"level": "validated", "source": "scenario"}})
        kb = scenario_kb(base, {"components": lab.get("components", {})}, tag)
        if lab.get("components", {}).get("l12") == "l12_other":
            kb.components["l12"].setdefault("action_contracts", copy.deepcopy(base.components["l12"].get("action_contracts", [])))
        # environment profile: a controlled-environment designator needs an incubation device keeping the profile
        prof = dict(PROFILES, **lab.get("profiles", {}))
        env = [d for d in sorted({a[1] for a in kb.q("has_function", None, "incubation")}) if prof.get(d) == "culture-standard"]
        if not env:
            return dict(outcome="refused at mapping", refused_by=["(a controlled-environment (profile culture-standard)) resolves to nothing: "
                                                                   + ", ".join(f"{d.upper()} keeps {p}" for d, p in prof.items())],
                        devices={}, routes=[], trips=[], leaves=0, realization=None, validity=None, environment=None)
        world = SymbolicWorld(kb, faults=None)
        belief = Belief()
        world.initial_belief(belief, exp_kernel.plate.id)
        trail = AuditTrail(f"challenge-rescue/{lab['id']}", dict(kernel=KERNEL_VERSION, kb=kb.name, registry=registry_sha(), backend=world.name))
        ctx = Context(kb, world, trail, belief)
        err = None
        try:
            perform(copy.deepcopy(exp_kernel), ctx)
        except Failure as f:
            err = f"{f.code}: {f.detail}"
        td = trail.as_dict()
        E = td["entries"]
        v = assess(td)
        end = next((e["transition"] for e in reversed(E) if e["category"] == "experiment"), None)
        refused = sorted({f"{c['id']}: {c.get('observation') or ''}".strip(": ") for e in E for c in (e.get("constraints") or [])
                          if c["verdict"] in ("VIOLATED", "NOT_EVALUATED")})
        leaves = [e for e in E if e["kind"] in ("motion", "command") and e["transition"] == "executed"]
        devs = {}
        for e in leaves:
            devs[e["agent"]] = devs.get(e["agent"], 0) + 1
        routes = sorted({json.dumps(r["value"]) for e in E for r in (e.get("resolutions") or []) if r["query"].startswith("route(") and r.get("value")})
        trips = []
        for e in E:
            if e["category"] == "run_session" and e["transition"] in ("executed", "escalated", "failed", "abstained"):
                g = next((x for x in E if x["designator"] == e["designator"] and x["transition"] == "grounded"), None)
                o = next((x for x in E if x["designator"] == e["designator"]), None)
                trips.append(dict(session=g["bindings"]["session"] if g else None, end=e["transition"],
                                  duration_s=round(e["t_sim"] - o["t_sim"], 1) if o else None))
        cats = {}
        for e in leaves:
            cats[e["category"]] = cats.get(e["category"], 0) + 1
        outcome = {"executed": "realized", "abstained": "refused before anything moved", "escalated": "escalated", "failed": "failed"}.get(end, end)
        if end != "executed" and not leaves:
            outcome = "refused before anything moved"
        if end == "executed" and not v["validity"]["ok"]:
            outcome = "realized, result not valid evidence (NR3)"
        models = {d: ((kb.components.get(d) or {}).get("identity") or {}).get("component_id", d) for d in ("l10", "l12", "l17")}
        return dict(outcome=outcome, end=end, error=err, refused_by=refused, devices=devs, models=models, routes=[json.loads(r) for r in routes],
                    trips=trips, leaves=len(leaves), categories=cats, realization=v["realization"]["ok"], validity=v["validity"]["ok"],
                    environment=env)
    finally:
        KBM.FACTS_DIR = old


def main(argv):
    from .culture_plan import derive, load_plan
    cp_text = open(os.path.join(LAB, "culture_plan.ldl")).read()
    lab_text = open(os.path.join(LAB, "challenge_rescue.ldl")).read()
    con_text = open(os.path.join(LAB, "contracts.ldl")).read()
    base_facts = open(os.path.join(KBM.FACTS_DIR, "facts_g050.lp")).read()
    # 1. vocabulary
    P = load_plan(cp_text)
    D = derive(P)
    cp_atoms = atoms(parse(cp_text))
    V = realization_vocabularies(base_facts)
    hits = {k: sorted(cp_atoms & set(v)) for k, v in V.items()}
    culture_terms = sorted(cp_atoms)
    # 2. labs
    world = World("g050")
    nominal = check(lab_text, con_text, world)
    kexp, _ = nominal["E"].to_kernel(nominal["E"].linear_extension(nominal["before"]))
    culture_order = sorted(map(tuple, D["hasse"]))
    lab_order = sorted(map(tuple, nominal["hasse"]))
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for lab in LABS:
            # the plans are re-read and re-derived for every lab: they must come out identical
            Pc = load_plan(open(os.path.join(LAB, "culture_plan.ldl")).read())
            Dc = derive(Pc)
            r = run_lab(lab, base_facts, kexp, tmp)
            rows.append(dict(lab, culture_plan_sha=sha(cp_text), culture_order_same=sorted(map(tuple, Dc["hasse"])) == culture_order,
                             lab_plan_sha=sha(lab_text), lab_order_same=True, **r))
    ref = rows[0]
    for r in rows:
        r["differs"] = [k for k in ("models", "devices", "routes", "trips", "leaves", "outcome") if json.dumps(r.get(k), sort_keys=True) != json.dumps(ref.get(k), sort_keys=True)]
    out = dict(culture_plan=dict(sha=sha(cp_text), terms=culture_terms, order=culture_order, inputs=["registry/lab/culture_plan.ldl"]),
               lab_plan=dict(sha=sha(lab_text), order=lab_order), vocabularies={k: dict(size=len(v), sample=v[:14], hits=hits[k]) for k, v in V.items()},
               labs=rows)
    json.dump(out, open(os.path.join(OUT, "independence.json"), "w"), indent=1, default=str)
    print(f"[independence] culture plan {sha(cp_text)}: {len(culture_terms)} terms; realization vocabulary hits: "
          + ", ".join(f"{k} {len(h)}" for k, h in hits.items()))
    for r in rows:
        print(f"[independence] {r['id']:24} {r['dimension']:20} culture plan {r['culture_plan_sha']} order same {r['culture_order_same']}; "
              f"lab plan {r['lab_plan_sha']}; -> {r['outcome']}{' refused by ' + str(r['refused_by']) if r['refused_by'] and r['outcome'] != 'realized' else ''}; "
              f"devices {r['devices']}; trips {[(t['session'], t['duration_s']) for t in r['trips']]}; differs in {r['differs']}")
    ok = not any(hits.values()) and all(r["culture_order_same"] for r in rows)
    print(f"[independence] {'PASS' if ok else 'FAIL'}: no realization term in the culture plan, and its derived order is the same in all {len(rows)} labs")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
