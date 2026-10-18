"""Grounding the culture plan in Cell 01: from abstract cultures to running programs, monitors and reactions.

  1. Instantiation: each abstract culture becomes a particular culture (the organoid in a particular well of a particular
     plate), each substance a particular reagent lot at a rack position, with the grounds and the rejected alternatives.
  2. Per trip, the grounded program as executed on the Isaac twin (trail_isaac_nominal.json), phase by phase:
       manipulation programs   the robots' pick / transit / place programs over seat frames, and tool coupling
       loading / unloading     the devices presenting, receiving, stowing and storing the plate
       device programs         dose_well (tip, aspirate, dispense with volume / height / rate), image_well (calibration,
                               autofocus, acquisition), incubation
       constraints             what was enforced at each step (window, L12 airspace, identity, interlocks)
       monitors                what was observed, with the observation itself
  3. The computations (interpret, analyse): their inputs (hashed image evidence, the calibration record) and outputs.
  4. Reactions: for each fault of each process, the detecting monitor, the handler and its checked guarantee; and the
     reactions the kernel actually performed in the recorded fault runs, step by step.

    env_cad/bin/python -m rsa.grounding        # rsa/out/grounding.json
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List

from .ldl import OUT

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MANIP = {"approach", "insert", "grasp", "lift", "transit", "place", "release", "retract", "tool_couple"}
LOAD = {"present", "stow", "load", "store_cmd", "release_plate"}
PROGRAM = {"tip_pick", "aspirate", "dispense", "tip_eject", "image_well", "incubate", "autofocus", "validate", "calibrate_cmd", "contain"}
CHECK = {"check_interlocks", "verify_identity", "wait_environment"}


def short(x):
    s = json.dumps(x) if not isinstance(x, str) else x
    s = re.sub(r"https___aicor_example_okf_sdt_lab1_world_experimentalworld_plates_plate_(\w+?)_wells_(\w+?)_interfaces_(\w+)",
               lambda m: f"{m.group(1).upper()}:{m.group(2).upper()}/{m.group(3)}", s)
    return s.replace("stations_", "").replace("fixtures_", "").replace("tooling_", "")


def tree(entries):
    nodes = {}
    for e in entries:
        d = e["designator"]
        n = nodes.setdefault(d, dict(id=d, parent=e["parent"], cat=e["category"], kind=e["kind"], entries=[]))
        n["entries"].append(e)
    kids = {}
    for n in nodes.values():
        kids.setdefault(n["parent"], []).append(n)
    first = {d: n["entries"][0]["seq"] for d, n in nodes.items()}
    for v in kids.values():
        v.sort(key=lambda n: first[n["id"]])
    return nodes, kids


def leaf_record(n):
    ex = next((e for e in reversed(n["entries"]) if e["transition"] in ("executed", "failed")), n["entries"][-1])
    ev = {x["kind"]: x["value"] for x in ex.get("evidence") or []}
    return dict(op=n["cat"], agent=ex.get("agent"), term=short(ex.get("term")), status=ex["transition"],
                t=round(ex["t_sim"] - (ex.get("duration_s") or 0), 2), duration_s=ex.get("duration_s"),
                realised_by=ev.pop("realised_by", None),
                monitors=[dict(name=m["name"], passed=m["passed"], observation=m.get("observation")) for m in ex.get("monitors") or []],
                constraints=[dict(id=c["id"], verdict=c["verdict"], observation=c.get("observation")) for c in ex.get("constraints") or []],
                evidence={k: short(v) for k, v in ev.items()},
                hashed=all(x.get("sha256") for x in ex.get("evidence") or []))


def leaves_of(n, kids):
    out = []
    for k in kids.get(n["id"], []):
        if k["kind"] == "action":
            out += leaves_of(k, kids)
        else:
            out.append(k)
    return out


def classify(op):
    return ("manipulation" if op in MANIP else "loading / unloading" if op in LOAD else
            "device program" if op in PROGRAM else "check" if op in CHECK else "other")


def trip_program(nodes, kids, session_node, step_of):
    """The run_session's lab tasks in order, each with its leaves grouped by kind."""
    t0 = session_node["entries"][0]["t_sim"]
    phases = []
    sess_constraints = {}
    for e in session_node["entries"]:
        for c in e.get("constraints") or []:
            sess_constraints[c["id"]] = dict(id=c["id"], verdict=c["verdict"], observation=c.get("observation"))
    for task in kids.get(session_node["id"], []):
        leafs = [leaf_record(l) for l in (leaves_of(task, kids) if task["kind"] == "action" else [task])]
        for l in leafs:
            l["t"] = round(l["t"] - t0, 1)
            l["kind"] = classify(l["op"])
        b = next((e.get("bindings") for e in task["entries"] if e["transition"] == "grounded" and e.get("bindings")), {}) or {}
        sub = [k["cat"] for k in kids.get(task["id"], []) if k["kind"] == "action"]
        robots = sorted({l["agent"] for l in leafs if l["kind"] == "manipulation"})
        phases.append(dict(task=task["cat"], ldl=step_of(task, nodes), bindings={k: b[k] for k in ("well", "reagent", "dose_au", "source", "target", "robot", "tool") if k in b},
                           sub=sub, robots=robots, leaves=leafs))
    return dict(t0=t0, phases=phases, session_constraints=list(sess_constraints.values()))


def reaction_episodes(name, max_steps=40):
    """What the kernel did after each failure in a recorded run: failure -> repair -> outcome, with monitors."""
    path = os.path.join(OUT, f"trail_{name}.json")
    if not os.path.exists(path):
        return []
    E = json.load(open(path))["entries"]
    out = []
    for i, e in enumerate(E):
        if e["transition"] != "repairing":
            continue
        fail = next((x for x in reversed(E[:i]) if x["transition"] == "failed" and x["kind"] != "action"), None)
        node = e["designator"]
        seq, outcome = [], None
        for x in E[i + 1:]:
            if x["kind"] != "action" and x["transition"] in ("executed", "failed"):
                seq.append(dict(op=x["category"], agent=x.get("agent"), status=x["transition"], term=short(x.get("term")),
                                monitors=[dict(name=m["name"], passed=m["passed"], observation=m.get("observation")) for m in x.get("monitors") or []]))
            if x["designator"] == node and x["transition"] in ("executed", "repaired", "escalated", "failed"):
                outcome = x["transition"]
                break
            if x["transition"] == "replanned" and x["designator"] == node:
                seq.append(dict(op="replanned", agent=None, status="replanned", term=None, monitors=[]))
            if len(seq) >= max_steps:
                break
        end = next((x["transition"] for x in reversed(E) if x["category"] == "experiment"), None)
        out.append(dict(run=name, at=e["category"], failure=e["repair"]["failure"], detail=e["repair"].get("detail") or "",
                        failed_leaf=dict(op=fail["category"], agent=fail.get("agent"), term=short(fail.get("term")),
                                         monitors=[dict(name=m["name"], passed=m["passed"], observation=m.get("observation")) for m in fail.get("monitors") or []]) if fail else None,
                        repair=e["repair"].get("repair_categories"), mode=e["repair"].get("then"), steps=seq, outcome=outcome, experiment_end=end))
    return out


def main(argv):
    cp = json.load(open(os.path.join(OUT, "culture_plan.json")))
    ldl = json.load(open(os.path.join(OUT, "ldl_challenge_rescue.json")))
    plan = json.load(open(os.path.join(ROOT, "okf", "lab-automation-twin", "L3-logical-axiomatization", "derivation", "out", "plan_g050.json")))
    devices = __import__("yaml").safe_load(open(os.path.join(HERE, "registry", "devices.yaml")))
    facts = open(os.path.join(ROOT, "okf", "lab-automation-twin", "build", "e2m", "facts_g050.lp")).read()
    free = sorted(re.findall(r"free\((\w+),\d+\)", facts), key=lambda w: (w[0], int(w[1:])))
    allw = [f"{r}{c:02d}".lower() for r in "abcdefgh" for c in range(1, 13)]
    used = [w.upper() for w in allw if w not in free]
    # ---- 1. instantiation
    inst = []
    for c, v in cp["mapping"]["vessels"].items():
        w = v["well"]
        inst.append(dict(abstract=c, role=v["role"], kind="culture",
                         particular=f"the organoid in {v['plate']}:{w}",
                         sdt=[f"…/Plate_{v['plate']}/Wells/{w}/Physical/Organoid (WellOrganoid)",
                              f"…/Plate_{v['plate']}/Wells/{w}/Biological/LatentState (WellBeliefEstimate)"],
                         grounds=[f"{v['plate']} is the experiment's culture plate (experiments ABox; SDT CulturePlate, barcode Plate_{v['plate']})",
                                  f"{w} is free: not used by Cell 01's own design (wells {', '.join(used[:6])}, … {len(used)} in all)",
                                  f"lowest free index for the {v['role']} arm; wells are interchangeable units, roles ordered rescued < comparator < control (experiment_to_motion.lp symmetry breaking)"],
                         rejected=[f"{u}: used by Cell 01's design" for u in used[:4]]))
    for key, typ in (("?ch", "challenge"), ("?rs", "rescue")):
        rg = devices["reagents"][typ]
        pose = re.search(rf"reagent_pose\({typ},(\w+)\)", facts).group(1)
        inst.append(dict(abstract=key, role=typ, kind="substance",
                         particular=f"reagent {rg['id']} (barcode {rg['barcode']}, lot {rg['lot']}) at {short(pose)}",
                         sdt=[short(pose)], grounds=[f"registry reagents.{typ}: stock {rg['conc_au_per_uL']} au/uL (ILLUSTRATIVE)", f"reagent_pose({typ},{short(pose)})"],
                         rejected=[]))
    inst.append(dict(abstract="(the plate ?p)", role="carrier", kind="plate", particular="Plate_P17 in L10 cassette slot 2",
                     sdt=["/World/ExperimentalWorld/Plates/Plate_P17 (SBSMicroplate, CulturePlate)", "runtime: /World/Episode/Plate_P17"],
                     grounds=["belief plate_at:P17 = slot:l10 (observed at the start of each trip by the barcode read)", "scripts/run_cell01_episode.py PLATES: P17 in L10 slot 2"],
                     rejected=["P30: arrives with the AMR, not a culture plate of this experiment", "RefPlate (L21): QC reference plate"]))
    for i in ldl["instruments"]:
        if i:
            for a in i["answers"]:
                pass
    # ---- 2. trips on the Isaac twin
    E = json.load(open(os.path.join(OUT, "trail_isaac_nominal.json")))["entries"]
    nodes, kids = tree(E)

    def step_of(task, nodes_):
        par = nodes_.get(task["parent"])
        for n in (task, par):
            if not n:
                continue
            b = next((e.get("bindings") for e in n["entries"] if e["transition"] == "grounded" and e.get("bindings")), {}) or {}
            if n["cat"] == "intervene":
                return "?x3" if b.get("reagent") == "rescue" else ("?x1" if b.get("well") == "A01" else "?x2")
            if n["cat"] == "measure":
                return {"A01": "?m1", "A02": "?m2", "A05": "?m3"}.get(b.get("well"))
        return None

    trips = []
    sessions = [n for n in nodes.values() if n["cat"] == "run_session"]
    sessions.sort(key=lambda n: n["entries"][0]["seq"])
    cult_of = {r["lab_step"]: r["culture_step"] for r in cp["mapping"]["rows"] if r["lab_step"]}
    for s in sessions:
        b = next(e["bindings"] for e in s["entries"] if e["transition"] == "grounded")
        prog = trip_program(nodes, kids, s, step_of)
        acts = [p["ldl"] for p in prog["phases"] if p["ldl"]]
        for p in prog["phases"]:
            if p["task"] in ("intervene", "measure"):
                # the lab action's own subtree: dose / image; expand to show the device program
                pass
        dur = round(s["entries"][-1]["t_sim"] - s["entries"][0]["t_sim"], 1)
        trips.append(dict(session=b["session"], t_h=b["t_h"], duration_s=dur, lab_steps=acts,
                          culture_steps=[cult_of.get(a) for a in acts], **prog))
    waits = [dict(lab_step="?w1" if (next(e.get("bindings") for e in n["entries"] if e["transition"] == "grounded") or {}).get("until_h") == 48 else "?w2",
                  culture_step=None, leaves=[leaf_record(l) for l in leaves_of(n, kids)]) for n in nodes.values() if n["cat"] == "wait"]
    for w in waits:
        w["culture_step"] = cult_of.get(w["lab_step"])
    # ---- 3. computations
    imgs = [e for e in E if e["category"] == "image_well" and e["transition"] == "executed"]
    comp = []
    for e in imgs:
        ev = {x["kind"]: x for x in e.get("evidence") or []}
        well = ev["well"]["value"]
        cal = next((m["observation"] for m in e.get("monitors") or [] if m["name"] == "calibration_state"), "")
        c = {"A01": "?cr", "A02": "?cc", "A05": "?ck"}[well]
        comp.append(dict(step={"?cr": "?i1", "?cc": "?i2", "?ck": "?i3"}[c], culture=c, input_image=short(ev["image"]["value"]["ref"]) if isinstance(ev["image"]["value"], dict) else short(ev["image"]["value"]),
                         image_sha256=ev["image"]["sha256"][:16], calibration=cal,
                         algorithm="twin/culture/optics.analyse: flat-field, threshold, largest component -> equivalent radius from the CALIBRATED pixel size",
                         output=f"radius estimate, sigma {cp['knowledge']['sigma_um']} um (observation_model_v1.json)",
                         note="the Isaac run images the twin's synthetic test sample, not organoids; the surrogate radii in section 2 come from the culture model (ILLUSTRATIVE)"))
    comp.append(dict(step="?a1", culture=None, input_image=None, image_sha256=None, calibration=None,
                     algorithm="twin/culture/eig.posterior_over_models on (rescued - comparator radius, mean radius)",
                     output=f"posterior {cp['knowledge']['posterior']}; {cp['knowledge']['information_gain_bit']} bit gained",
                     note="requires the control's estimate within its baseline (critic V4: controls present)"))
    # ---- 4. reactions
    react = []
    for t in ldl["trust"]:
        for f in t["faults"]:
            g = next((x for x in ldl["guarantees"] if x["cause"] == f["fault"]), None) or next(
                (x for x in ldl["guarantees"] if x["type"] == next(ff["signals"] for m in ldl["models"].values() for ff in m["faults"] if ff["name"] == f["fault"]) and x["cause"] is None), None)
            react.append(dict(step=t["step"], process=t["process"], fault=f["fault"], detected_by=f["monitor"], detection=f["detected"],
                              timing=f["timing"], handler=g["text"] if g else None, claims=g["claims"] if g else None, holds=g["ok"] if g else None))
    seen, react_u = set(), []
    for r_ in react:
        k = (r_["process"], r_["fault"])
        if k not in seen:
            seen.add(k)
            react_u.append(r_)
    episodes = []
    for run in ("calibration_lapsed", "tip_lost", "identity_swap", "tool_changer_slow", "isaac_identity_swap", "isaac_calibration_lapsed"):
        episodes += reaction_episodes(run)
    out = dict(instantiation=inst, trips=trips, waits=waits, computations=comp, reactions=react_u, episodes=episodes,
               source="rsa/out/trail_isaac_nominal.json (Isaac twin, 17 Oct 2026)")
    json.dump(out, open(os.path.join(OUT, "grounding.json"), "w"), indent=1, default=str)
    nleaf = sum(len(p["leaves"]) for t in trips for p in t["phases"])
    mons = sum(len(l["monitors"]) for t in trips for p in t["phases"] for l in p["leaves"])
    print(f"[grounding] {len(inst)} referents instantiated; {len(trips)} trips, {nleaf} grounded leaves, {mons} monitor observations; "
          f"{len(comp)} computations; {len(react_u)} fault reactions; {len(episodes)} recorded reaction episodes")
    for t in trips:
        print(f"[grounding] {t['session']} ({t['t_h']} h, {t['duration_s']} s): lab steps {t['lab_steps']} = culture steps {t['culture_steps']}; "
              f"phases {[p['task'] for p in t['phases']]}")
    for e in episodes:
        print(f"[grounding] reaction in {e['run']}: {e['failure']} at {e['at']} -> {e['repair']} ({len(e['steps'])} steps) -> {e['outcome']}; experiment {e['experiment_end']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
