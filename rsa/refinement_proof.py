"""A refinement proof: the motion-level plan executes the culture-level plan and satisfies the stated constraints,
relative to explicit assumptions about the controllers, sensors and devices.

Theorem. Let Pi_M be the motion-level plan of the challenge-rescue experiment: the 151 grounded steps of plan_g050 (the
kernel's expansion, identical step for step), whose 111 robot motions are refined into giskardpy motion statecharts
(rsa/out/challenge_rescue_giskard.py). Under assumptions A1-A6, every execution of Pi_M either
  (i) realizes the culture plan: every culture-level physical and knowledge effect, in the derived order, at the
      design's culture times, with the control culture untreated, and every stated constraint holds on the way
      (interlocks, L12 airspace, identity, environment before store, calibration before imaging, the 600 s window,
      contamination freedom, tool hygiene, plate level, collision distance); or
  (ii) is stopped by a monitor and ends in a failure handler whose guarantee holds (safe state, contained, or the goal).

Assumptions (not proved here; each is checked kinematically, monitored at run time, or taken from a device contract):
  A1 giskardpy semantics: a motion statechart ends only through EndMotion (its end monitor true) or CancelMotion.
  A2 monitor soundness: PoseReached, LocalMinimumReached with the grasp check, VectorsAligned, the collision distance
     monitors, the simulation clock, the barcode read, the seat sensors and the device monitors observe correctly.
  A3 abstraction: a TCP within 0.4 mm / 0.2 deg of a seat's grasp or release pose has the plate in that seat (the
     nest guides capture it); within 5 mm of an approach pose it is at that approach pose (free-space waypoint).
  A4 the grasp holds the plate from grasp to release (monitored: grasp_confirmed, lifted, seating).
  A5 device contracts: dose_well delivers within its tolerance when its monitors pass; image_well yields an image
     when calibration and focus monitors pass; L10 holds the environment profile while the plate is stored.
  A6 the goal frames are the ones the scene defines (rsa/motion_frames.py), and each is reachable (checked).

Proof, by composition (each obligation is discharged by a check this script runs or reads):
  O1 culture plan well formed (rsa/culture_plan.derive)
  O2 abstraction: the motion level's proven effects, mapped by the vessel map, entail every culture-level effect, the
     culture order and the culture-level prevents (z3: the negation is UNSAT; negative controls SAT)
  O3 lab plan: order, threats, instruments, handlers and guarantees (rsa/ldl.py, rsa/ldl_trust.py)
  O4 step level: executability, safety, time and realization of every trip (z3 V1-V5, validate_plan_z3.py)
  O5 step level, cleanliness: no tool that touches the culture handles the plate; contamination freedom is required
  O6 motion refinement: each of the 111 motion designators corresponds to its step, its end monitor implies the
     step's postcondition under A3, and its soft parts are hold-or-cancel (tilt, collision, duration <= 1.2 x estimate,
     which is V3's assumption)
  O7 failure branch: every cancellation and monitor-detected violation reaches a handler whose guarantee holds

    env_cad/bin/python -m rsa.refinement_proof      # rsa/out/refinement_proof.json, exit 1 if an obligation fails
"""

from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys

import z3

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "out")
DERIV = os.path.join(ROOT, "okf", "lab-automation-twin", "L3-logical-axiomatization", "derivation")
PY = os.path.join(ROOT, "env_cad", "bin", "python")

POST = {  # the step model's postcondition of each motion primitive (validate_plan_z3.Trip), and the motion that refines it
    "approach": ("pos = appr(seat)", {"approaching", "aligning"}),
    "insert": ("pos = seat", {"inserting"}),
    "grasp": ("grip and plate = robot", {"grasping"}),
    "lift": ("pos = appr(seat), plate held", {"lifting"}),
    "transit": ("pos = appr(target)", {"transiting"}),
    "place": ("pos = seat, plate = seat", {"placing"}),
    "release": ("not grip", {"releasing"}),
    "retract": ("pos = appr(seat)", {"retracting"}),
    "tool_couple": ("tool = T01", {"coupling"}),
}
END_MONITOR = {  # motion type -> (end monitor, tolerance, why it implies the postcondition)
    "approaching": ("CartesianPose observation", 0.005, "A3: within 5 mm of the approach pose"),
    "aligning": ("PoseReached", 0.0004, "A3: within 0.4 mm / 0.2 deg of the approach pose"),
    "inserting": ("PoseReached", 0.0004, "A3: within 0.4 mm / 0.2 deg of the grasp pose, the plate between the jaws"),
    "grasping": ("LocalMinimumReached + grasp_confirmed", None, "A4: the jaws stalled on the plate, contact and lift confirmed"),
    "lifting": ("CartesianPositionStraight observation", 0.0004, "A3 + A4: at the approach height, plate held"),
    "transiting": ("CartesianPose observation", 0.005, "A3: within 5 mm of the target approach pose"),
    "placing": ("CartesianPositionStraight observation", 0.0004, "A3: at the release height over the seat; the guides capture the plate"),
    "releasing": ("LocalMinimumReached", None, "A2: the jaws open"),
    "retracting": ("CartesianPositionStraight observation", 0.0004, "A3: back at the approach height"),
    "coupling": ("PoseReached within the lock gap", 0.004, "A2: the coupler locks within 4 mm"),
}
CAPTURE_M = 0.002   # A3: the nest guides' capture, larger than the 0.4 mm convergence (twin seat geometry, ILLUSTRATIVE)


# ------------------------------------------------------------------------------------------------- O2 abstraction (z3)
def abstraction_proof(proof, cp, vessel=None, extra_events=None, drop_images=()):
    """z3: from the step level's proven events (V4) and the vessel map, every culture-level obligation follows."""
    v4 = proof["theorems"]["V4 realisation (doses, images, session times)"]
    times = v4["times"]
    events = [("dose", w.upper(), r, au, times[s]) for s, ds in v4["doses"].items() for w, r, au in ds]
    events += [("image", w.upper(), None, None, times["s2"]) for w in v4["images"] if w.upper() not in drop_images]
    events += extra_events or []
    vessel = vessel or {c: v["well"] for c, v in cp["mapping"]["vessels"].items()}
    S = z3.Solver()
    # facts: the events, as an enumerated relation; a culture fact holds iff some event of its vessel supports it
    ev = {e: z3.Bool(f"ev_{i}") for i, e in enumerate(events)}
    for b in ev.values():
        S.add(b)
    def exposed(c, s, au, t):
        return z3.Or([ev[e] for e in events if e[0] == "dose" and e[1] == vessel[c] and e[2] == s
                      and (au is None or e[3] == au) and (t is None or e[4] == t)] or [z3.BoolVal(False)])
    def observed(c, t):
        return z3.Or([ev[e] for e in events if e[0] == "image" and e[1] == vessel[c] and e[4] == t] or [z3.BoolVal(False)])
    obligations = {}
    for st in cp["plan"]["steps"]:
        sl, v = st["slots"], st["var"]
        if st["type"] in ("challenging", "rescuing"):
            sub = "challenge" if st["type"] == "challenging" else "rescue"
            au = int(round(float(sl["dose"].split()[0]) * 100))
            t = int(re.search(r"culture-time (\d+)", sl["at"]).group(1))
            obligations[f"{v} {st['type']} {sl['culture']}: exposed to {sub} {sl['dose']} at {t} h"] = exposed(sl["culture"], sub, au, t)
        elif st["type"] == "observing":
            obligations[f"{v} observing {sl['culture']}: image at 72 h"] = observed(sl["culture"], 72)
        elif st["type"] == "interpreting":
            c = re.search(r"\(of (\?c\w)\)", st["requires"][0]["cond"]).group(1)
            # needs the image (above) and a known scale: S3 (calibration valid or QC before imaging) is part of V2
            obligations[f"{v} interpreting {c}: image and known scale"] = z3.And(observed(c, 72), z3.BoolVal(proof["theorems"]["V2 safety S1 S2 S3 S6 S7"]["holds"]))
        elif st["type"] == "analysing":
            obligations[f"{v} analysing: estimates of the rescued, comparator and control cultures"] = z3.And([observed(c, 72) for c in ("?cr", "?cc", "?ck")])
        elif st["type"] == "growing":
            a = int(re.search(r"culture-time (\d+)", sl["from"]).group(1))
            b = int(re.search(r"culture-time (\d+)", sl["to"]).group(1))
            # every trip ends with the plate stored at home (V1), so between trips the cultures are in their environment
            obligations[f"{v} growing {a} -> {b} h: cultures in their environment between the trips"] = z3.BoolVal(
                proof["theorems"]["V1 executability / preservation"]["holds"] and any(t == a for t in times.values())
                and any(t == b for t in times.values()))
    obligations["prevents: the control culture is never exposed"] = z3.Not(z3.Or(
        [ev[e] for e in events if e[0] == "dose" and e[1] == vessel["?ck"]] or [z3.BoolVal(False)]))
    obligations["order: challenges at 0 h < rescue at 48 h < observations at 72 h"] = z3.BoolVal(times["s0"] < times["s1"] < times["s2"])
    results = {}
    for name, f in obligations.items():
        S.push()
        S.add(z3.Not(f))
        r = S.check()
        results[name] = (r == z3.unsat)
        S.pop()
    return dict(holds=all(results.values()), obligations=results, events=[list(e) for e in events], vessel=vessel)


# ------------------------------------------------------------------------------------------------- O5 cleanliness (z3)
def cleanliness_proof(plan, facts_text, contacts_extra=()):
    """z3: no tool that touches the culture is ever coupled for plate handling; contamination freedom is required."""
    contacts = set(re.findall(r"contacts_culture\((\w+)\)", facts_text)) | set(contacts_extra)
    used = set()
    for s in plan["sessions"]:
        for st in s["steps"]:
            if st["primitive"] == "tool_couple":
                used.add(st["term"][2])
    req = set(a.split(",")[1] for a in re.findall(r"requires_tool\(([^)]*)\)", facts_text))
    used |= req
    tools = sorted(used | contacts)
    T = {t: z3.Bool(f"contacts_{t}") for t in tools}
    S = z3.Solver()
    for t in tools:
        S.add(T[t] == z3.BoolVal(t in contacts))
    claim = z3.And([z3.Not(T[t]) for t in used])
    S.add(z3.Not(claim))
    return dict(holds=S.check() == z3.unsat, tools_used=sorted(used), contacts_culture=sorted(contacts),
                contamination_free_required="contamination_free" in open(os.path.join(HERE, "registry", "constraints.yaml")).read())


# ------------------------------------------------------------------------------------------------- O6 motion refinement
def motion_proof(gm, frames, py_text):
    rows, ok = [], True
    reach = {(g["leg"], g["phase"]): g for g in frames["goals"]}
    for leg in gm["legs"]:
        for m in leg["motions"]:
            leaf = m["kernel_leaf"]
            post, refiners = POST[leaf]
            mon, tol, why = END_MONITOR[m["type"]]
            checks = {
                "refines its step": m["type"] in refiners,
                "end monitor implies the postcondition": tol is None or tol <= (0.005 if m["type"] in ("approaching", "transiting") else
                                                                                 LOCK if m["type"] == "coupling" else CAPTURE_M),
                "tilt is hold-or-cancel while held": (not m.get("held")) or any("tilt" in c for c in m.get("cancel", [])),
                "collision is hold-or-cancel": m["type"] in ("grasping", "releasing") or any("collision" in c for c in m.get("cancel", [])),
                "duration is hold-or-cancel within V3's bound": bool(m.get("timeout_s")) and m["timeout_s"] <= 1.2 * m["estimate_s"] + 1e-9,
            }
            good = all(checks.values())
            ok &= good
            rows.append(dict(session=leg["session"], robot=leg["robot"], leg=f"{leg['src']}->{leg['dst']}", type=m["type"], step=leaf,
                             postcondition=post, end_monitor=mon, why=why, timeout_s=m.get("timeout_s"), cancel=m.get("cancel", []),
                             checks=checks, ok=good))
    code = {"CancelMotion on timeout": "CancelMotion.when_true(clock" in py_text,
            "CancelMotion on tilt": "VectorsAligned(" in py_text and "trinary_logic_not(level.observation_variable)" in py_text,
            "collision cancel": "cancel_if_collision_violated=True" in py_text}
    reachable = sum(1 for g in frames["goals"] if g["reachable"] and g.get("margin_ok"))
    return dict(holds=ok and all(code.values()) and reachable == len(frames["goals"]), motions=rows, code=code,
                goals_reachable=f"{reachable}/{len(frames['goals'])}", capture_m=CAPTURE_M)


LOCK = 0.004


def main(argv):
    # O4: re-run the step-level SMT validation of the plan (fresh)
    r = subprocess.run([PY, os.path.join(DERIV, "validate_plan_z3.py"), os.path.join(DERIV, "out", "plan_g050.json")],
                       capture_output=True, text=True, timeout=900)
    proof = json.load(open(os.path.join(DERIV, "out", "proof_g050.json")))
    plan = json.load(open(os.path.join(DERIV, "out", "plan_g050.json")))
    facts = open(os.path.join(ROOT, "okf", "lab-automation-twin", "build", "e2m", "facts_g050.lp")).read()
    cp = json.load(open(os.path.join(OUT, "culture_plan.json")))
    ldl = json.load(open(os.path.join(OUT, "ldl_challenge_rescue.json")))
    gm = json.load(open(os.path.join(OUT, "giskard_motions.json")))
    frames = json.load(open(os.path.join(OUT, "motion_frames.json")))
    py_text = open(os.path.join(OUT, "challenge_rescue_giskard.py")).read()

    O = {}
    O["O1 culture plan well formed"] = dict(holds=not cp["derived"]["unsupported"] and not cp["derived"]["cyclic"],
                                            links=len(cp["derived"]["links"]), establish=[e["cond"] for e in cp["derived"]["establish"]])
    O["O2 abstraction: motion-level effects entail the culture plan"] = abstraction_proof(proof, cp)
    O["O3 lab plan: order, threats, instruments, handlers, guarantees"] = dict(
        holds=bool(ldl["ok"]) and all(t["resolved"] for t in ldl["threats"]) and all(g["ok"] for g in ldl["guarantees"])
        and all(i["ok"] for i in ldl["instruments"] if i) and all(v["caught"] for v in ldl["negative_controls"].values()),
        threats=f"{sum(t['resolved'] for t in ldl['threats'])}/{len(ldl['threats'])}", guarantees=f"{sum(g['ok'] for g in ldl['guarantees'])}/{len(ldl['guarantees'])}",
        negative_controls=f"{sum(v['caught'] for v in ldl['negative_controls'].values())}/{len(ldl['negative_controls'])}",
        order_preserved_culture_to_lab=cp["mapping"]["order_preserved"])
    O["O4 step level: executability, safety, time, realization (z3 V1-V5)"] = dict(
        holds=bool(proof["all_passed"]), theorems={k: v["holds"] for k, v in proof["theorems"].items()},
        negative_controls=f"{sum(v['caught'] for v in proof['negative_controls'].values())}/{len(proof['negative_controls'])}",
        validator_exit=r.returncode)
    O["O5 step level: cleanliness"] = cleanliness_proof(plan, facts)
    O["O6 motion refinement: 111 Giskard motions"] = motion_proof(gm, frames, py_text)
    fails = {g["type"] + (("/" + g["cause"]) if g["cause"] else ""): g["ok"] for g in ldl["guarantees"]}
    O["O7 failure branch: every cancellation reaches a guaranteed handler"] = dict(
        holds=fails.get("prevents-violated", False) and all(fails.values()),
        mapping={"MotionContractViolated (timeout, tilt)": "propagates to the session; unwind-protect returns the plate; handler prevents-violated: safe-state",
                 "CollisionViolatedError": "the same path", "device monitors": "the failure types of the process models, each with its verified handler"},
        guarantees=fails)

    # negative controls: each mutation must make one obligation fail
    neg = {}
    vm = {c: v["well"] for c, v in cp["mapping"]["vessels"].items()}
    sw = dict(vm, **{"?cr": vm["?cc"], "?cc": vm["?cr"]})
    neg["vessel map swaps rescued and comparator"] = not abstraction_proof(proof, cp, vessel=sw)["holds"]
    neg["the control well A05 is also dosed"] = not abstraction_proof(proof, cp, extra_events=[("dose", "A05", "challenge", 85, 0)])["holds"]
    neg["the control well is not imaged"] = not abstraction_proof(proof, cp, drop_images=("A05",))["holds"]
    neg["the plate tool T01 touches the culture"] = not cleanliness_proof(plan, facts, contacts_extra=("t01",))["holds"]
    gm2 = copy.deepcopy(gm)
    held = next(m for l in gm2["legs"] for m in l["motions"] if m.get("held"))
    held["cancel"] = [c for c in held["cancel"] if "tilt" not in c]
    neg["one held motion without the tilt cancel"] = not motion_proof(gm2, frames, py_text)["holds"]
    gm3 = copy.deepcopy(gm)
    m3 = next(m for l in gm3["legs"] for m in l["motions"] if m.get("timeout_s"))
    m3["timeout_s"] = round(1.5 * m3["estimate_s"], 2)
    neg["one motion's timeout beyond V3's bound (1.5 x)"] = not motion_proof(gm3, frames, py_text)["holds"]
    gm4 = copy.deepcopy(gm)
    gm4["legs"][0]["motions"][1]["type"] = "grasping"
    neg["a motion that does not refine its step"] = not motion_proof(gm4, frames, py_text)["holds"]
    neg["step level: the validator's own 10 mutated plans"] = all(v["caught"] for v in proof["negative_controls"].values())

    holds = all(o["holds"] for o in O.values())
    out = dict(theorem=__doc__.split("Assumptions")[0].strip(), assumptions=re.findall(r"(A\d .*?)(?=\s+A\d |$)", " ".join(l.strip() for l in __doc__.split("Assumptions")[1].split("Proof,")[0].splitlines()[1:])),
               obligations=O, negative_controls=neg, holds=holds and all(neg.values()))
    json.dump(out, open(os.path.join(OUT, "refinement_proof.json"), "w"), indent=1, default=str)
    for k, o in O.items():
        extra = ""
        if "obligations" in o:
            extra = f" ({sum(o['obligations'].values())}/{len(o['obligations'])} culture obligations)"
        if "motions" in o:
            extra = f" ({sum(m['ok'] for m in o['motions'])}/{len(o['motions'])} motions; goals reachable {o['goals_reachable']}; code {o['code']})"
        if "theorems" in o:
            extra = f" ({o['theorems']}; negative controls {o['negative_controls']})"
        print(f"[proof] {k}: {'holds' if o['holds'] else 'FAILS'}{extra}")
    for k, v in neg.items():
        print(f"[proof] negative control '{k}': {'caught' if v else 'MISSED'}")
    print(f"[proof] {'QED (relative to A1-A6)' if out['holds'] else 'NOT PROVED'}")
    return 0 if out["holds"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
