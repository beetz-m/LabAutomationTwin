"""Derive the robot's physical actions and motions that realise an experiment with a required information gain.

Pipeline (axioms/experiment-to-motion-axioms.md):
  1. EIG candidates (E2M2): delayed-rescue experiments (challenge dose x rescue delay x replicates) with their expected
     information gain over Cell 01's competing recovery models M1-M3 (twin/culture/eig.py), cached.
  2. Lab facts from the ontology ABox (abox/sdt.ofn, safety.ofn, experiments.ofn): automated devices and their functions,
     which robot serves which station, plate seat / well / rack poses, tools, free wells, safety rules; durations from
     the twin's run traces (test_reports/episodes/cell01_episodes_raw.json); device state (calibration, interlocks,
     tool, contamination) from the command line.
  3. clingo over experiment_to_motion.lp (E2M1, E2M3-E2M8): the optimal stable model is the plan.
  4. Writes out/plan_<tag>.json (the plan), abox/plan.ofn (the plan as designator individuals of the ontology, only for
     the default derivation) and out/plan_<tag>.md (readable).

Run: env_cad/bin/python okf/lab-automation-twin/L3-logical-axiomatization/derivation/derive_plan.py --gain-bits 0.5
Exit 0 with a plan, 2 when no candidate in the frame meets the requirement or no safe plan exists (reported, with the
reason), 1 on errors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
import time

import clingo

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(os.path.dirname(MOD))
ABOX = os.path.join(MOD, "abox")
OUT = os.path.join(HERE, "out")
BUILD = os.path.join(MOD, "build", "e2m")
LP = os.path.join(HERE, "experiment_to_motion.lp")
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(MOD, "src"))

SDT = "https://aicor.example/okf/sdt/lab1"
CELL = f"{SDT}/World/Cell01"
PLATE = "/World/ExperimentalWorld/Plates/Plate_P17"
SAFE = "https://aicor.example/okf/lab1/safety/rule"
E2M = "https://aicor.example/okf/lab1/e2m"
TRACE = os.path.join(REPO, "test_reports", "episodes", "cell01_episodes_raw.json")

# candidate frame (Honest scope in the axioms): doses already in the study, delays beyond the observed 6 h, 1-3 reps
DOSES = (0.45, 0.65, 0.85)
DELAYS = (12, 18, 24, 36, 48)
REPS = (1, 2, 3)
RESCUE_AU = 0.70
MARGIN_PCT = 20          # S5 is derived for durations up to 20 % above the trace estimates (validate_plan_z3 TOL)
# seat-pose priority per device (the frame a plate rests in when a robot hands it over)
SEAT_NAMES = ("transfer_station", "transfer_nest", "plate_nest", "plate_load_frame", "handover_frame")
# how a transfer leg's measured duration is apportioned over its motion primitives (illustrative split; sums to 1)
LEG_SPLIT = dict(approach=0.12, insert=0.08, grasp=0.05, lift=0.05, transit=0.34, place=0.10, release=0.04, retract=0.10)
DOSE_SPLIT = dict(tip_pick=0.20, aspirate=0.30, dispense=0.35, tip_eject=0.15)
# rules that a derived step discharges (lab-twin-safe-action individuals)
DISCHARGES = {"check_interlocks": "enclosure_door_interlock", "verify_identity": "identity_verified",
              "wait_environment": "l10_environment_valid", "validate": "l17_calibration_valid"}


def atom(s):
    return re.sub(r"[^a-z0-9_]", "_", s.lower()).strip("_")


# ------------------------------------------------------------------------------------------------- 1. EIG candidates
def eig_candidates(samples, seed, refresh=False, prior=None):
    os.makedirs(BUILD, exist_ok=True)
    src = open(os.path.join(REPO, "twin", "culture", "eig.py"), "rb").read()
    key = hashlib.sha1(src + repr((DOSES, DELAYS, REPS, samples, seed, prior)).encode()).hexdigest()[:12]
    cache = os.path.join(BUILD, "eig_candidates.json" if prior is None else f"eig_candidates_{key}.json")
    if not refresh and os.path.exists(cache):
        c = json.load(open(cache))
        if c.get("key") == key:
            return c
    import numpy as np
    from twin.culture import eig as E
    t0 = time.time()
    rng = np.random.default_rng(seed)
    priors = {m: E.sample_prior(m, rng, n=300) for m in E.MODELS}
    pM = prior or {m: 1 / 3 for m in E.MODELS}
    rows = []
    for d in DOSES:
        for dt in DELAYS:
            for n in REPS:
                g, pred = E.eig(priors, pM, d, dt, n, S=samples, seed=seed + 1)
                rows.append(dict(id=f"c_d{int(round(d * 100))}_t{dt}_n{n}", dose_au=d, delay_h=dt, reps=n,
                                 eig_bits=round(g, 4), predicted_effect_um=pred))
    c = dict(key=key, models=list(E.MODELS), prior_over_models=pM, samples=samples, seed=seed,
             max_bits=round(float(np.log2(len(E.MODELS))), 4), wall_s=round(time.time() - t0, 1), candidates=rows,
             note="EIG by nested Monte Carlo over Cell 01's calibrated surrogate (twin/culture/eig.py); ILLUSTRATIVE, "
                  "D016: no biomedical parameter is asserted.")
    json.dump(c, open(cache, "w"), indent=1)
    return c


# --------------------------------------------------------------------------------------------------- 2. ABox facts
def read_abox():
    sdt = open(os.path.join(ABOX, "sdt.ofn")).read()
    exp = open(os.path.join(ABOX, "experiments.ofn")).read()
    saf = open(os.path.join(ABOX, "safety.ofn")).read()
    ab = dict(types={}, fn={}, serves=[], poses={})
    for c, i in re.findall(r"ClassAssertion\(:(\w+) <([^>]+)>\)", sdt):
        ab["types"].setdefault(i, set()).add(c)
    for a, b in re.findall(r"hasDeviceFunction <([^>]+)> <[^>]+/function/(\w+)>", sdt):
        ab["fn"].setdefault(a, set()).add(b)
    ab["serves"] = re.findall(r"ObjectPropertyAssertion\(:servesStation <([^>]+)> <([^>]+)>\)", sdt)
    for a, b in re.findall(r"ObjectPropertyAssertion\(:hasInteractionPose <([^>]+)> <([^>]+)>\)", sdt):
        ab["poses"].setdefault(a, []).append(b)
    ab["used_wells"] = sorted(set(re.findall(r"appliedToWell <[^>]+> <[^>]*/Plate_P17/Wells/([A-H]\d\d)#entity>", exp)))
    ab["arm_wells"] = sorted(set(re.findall(r"assignsUnit <[^>]+> <[^>]*/Plate_P17/Wells/([A-H]\d\d)#entity>", exp)))
    ab["rules"] = set(re.findall(rf"<{SAFE}/(\w+)>", saf))
    return ab


def short(iri):
    return iri.replace(CELL + "/", "").replace("#entity", "")


def trace_durations():
    """Durations (s) of Cell 01 operations, medians over the twin's recorded episodes."""
    raw = json.load(open(TRACE))
    ds = [x for e in raw["episodes"] for x in e.get("designators", []) if "t_start" in x and "t_end" in x]
    dur = lambda x: x["t_end"] - x["t_start"]  # noqa: E731
    tid = lambda x: x["id"].split("/")[-1]  # noqa: E731
    r01 = [dur(x) for x in ds if x["action"] == "transport" and ("R01" in tid(x) or tid(x) == "transport")
           and "back" not in tid(x)]
    r02 = [dur(x) for x in ds if x["action"] == "transport" and "R02" in tid(x)]
    ret = [dur(x) for x in ds if x["action"] == "retrieve" and x.get("component") == "L10_Incubator"]
    inc = [dur(x) for x in ds if x["action"] in ("incubate", "store")]
    dose = [dur(x) for x in ds if x["action"] == "dose"]
    per_ep = {}
    for e in raw["episodes"]:
        im = sorted(x["t_end"] - x["t_start"] for x in e.get("designators", []) if x["action"] == "image")
        if len(im) > 1:
            per_ep[e.get("episode_id")] = im
    per_well = statistics.median([b - a for im in per_ep.values() for a, b in zip(im, im[1:])])
    first = statistics.median([im[0] for im in per_ep.values()])
    l17 = json.load(open(os.path.join(REPO, "test_reports", "l17_events.json")))["events"]
    t_ev = lambda n: next(x["t"] for x in l17 if x["event"] == n)  # noqa: E731
    tcm = json.load(open(os.path.join(REPO, "test_reports", "r02_report.json")))["tcm_events"]
    tc = [b["t"] - a["t"] for a, b in zip(tcm, tcm[1:]) if a["event"] == "change_tool_ok"
          and b["event"] == "store_tool_ok"]
    d = dict(r01_leg=statistics.median(r01), r02_leg=statistics.median(r02), l10_retrieve=statistics.median(ret),
             l10_store=statistics.median(inc), dose_well=statistics.median(dose), image_well=per_well,
             l17_present=t_ev("present_for_load_accepted") and 5.0, l17_load=first - per_well,
             tool_couple=statistics.median(tc) if tc else 13.0)
    d["l17_present"] = round(min(x["t"] for x in l17 if x["event"] in ("load_plate_refused", "load_plate_accepted"))
                             - t_ev("present_for_load_accepted"), 2)
    d["n"] = dict(r01=len(r01), r02=len(r02), retrieve=len(ret), store=len(inc), dose=len(dose))
    return d


def facts(ab, cands, req_bits, window_s, state, consumed=()):
    F, names = [], {}

    def name(iri, kind):
        a = atom(short(iri).split("/")[-1] if kind != "pose" else short(iri).replace("/", "_"))
        if kind == "dev":
            a = atom(re.match(r"(?:Stations|Robots|Fixtures|Tooling)/([A-Za-z0-9]+?)(?:_|$)", short(iri)).group(1))
        names[a] = iri
        return a

    fnmap = dict(DispensingFunction="dispensing", ImagingFunction="imaging", IncubationFunction="incubation",
                 CalibrationFunction="calibration", PlateStorageFunction="plate_storage",
                 QuarantineFunction="quarantine", IdentificationFunction="identification")
    robots = {r for r, _ in ab["serves"]}
    served = {}
    for r, v in ab["serves"]:
        served.setdefault(v, set()).add(r)
    # automated device := has a device function and is served by a robot (the ABox's own facts)
    devs = {v for v in ab["fn"] if v in served}
    seat = {}
    # the plate seat is the station's PlateSeatPose (ABox type); SEAT_NAMES only orders stations with several.
    # (rsa kernel iteration 1 found H4's transfer_nest missing when seats were selected by name alone.)
    rank = lambda p: next((i for i, nm in enumerate(SEAT_NAMES) if p.endswith(f"/{nm}#entity")), len(SEAT_NAMES))  # noqa: E731
    for v in served:
        cands_ = sorted((p for p in ab["poses"].get(v, []) if "PlateSeatPose" in ab["types"].get(p, ())), key=rank)
        if cands_:
            seat[v] = cands_[0]
    for v in sorted(devs):
        dv = name(v, "dev")
        F.append(f"automated({dv}).")
        for f in sorted(ab["fn"][v]):
            F.append(f"has_function({dv},{fnmap[f]}).")
            if f == "IncubationFunction":
                F.append(f"home({dv}).")
    for v, p in seat.items():
        dv = name(v, "dev")
        F += [f"holds_plate({dv}).", f"seat({dv},{name(p, 'pose')})."]
    for r, v in ab["serves"]:
        F.append(f"serves({name(r, 'dev')},{name(v, 'dev')}).")
    # mechanisms: a station whose plate seat is on a shuttle / stage it presents (the ABox's joint facts)
    for v in seat:
        dv = name(v, "dev")
        base = v.replace("#entity", "/")
        if any(i.startswith(base) and c & {"PlateShuttle", "MotorizedStage"} for i, c in ab["types"].items()):
            F.append(f"has_shuttle({dv}).")
    # airspace: the device constrained by the l12_deck_airspace rule
    if "l12_deck_airspace" in ab["rules"]:
        F.append("airspace(l12).")
    # tools: a robot that serves a tool magazine needs the magazine's plate gripper for plate transfers
    for r, v in ab["serves"]:
        if "ToolMagazine" in ab["types"].get(v, ()):
            tools = [i for i, c in ab["types"].items() if i.startswith(v.replace("#entity", "/Tools/"))
                     and "PlateGripperTool" in c]
            for t in tools:
                tn = name(t, "tool")
                dock = next(p for p in ab["poses"][v] if p.endswith(f"/dock_{tn.upper()}#entity"))
                F += [f"requires_tool({name(r, 'dev')},{tn}).", f"tool_pose({tn},{name(dock, 'pose')})."]
                if state["coupled"]:
                    F.append(f"coupled({name(r, 'dev')},{tn}).")
            for i, c in ab["types"].items():
                if i.startswith(v.replace("#entity", "/Tools/")) and ("PipettingTool" in c or "SuctionPickupTool" in c):
                    F.append(f"contacts_culture({name(i, 'tool')}).")
    # QC: a calibration station validates the imaging devices
    for v in devs:
        if "CalibrationFunction" in ab["fn"][v]:
            for w in devs:
                if "ImagingFunction" in ab["fn"][w]:
                    F.append(f"qc_station({name(v, 'dev')},{name(w, 'dev')}).")
    for v in devs:
        if "ImagingFunction" in ab["fn"][v] and state["calibrated"]:
            F.append(f"calibrated({name(v, 'dev')}).")
    if state["interlocks"]:
        F.append("interlocks_closed.")
    if state["contaminated"]:
        F.append("contamination_suspected.")
    F.append("interlock_monitor(cell01).")
    names["cell01"] = f"{SDT}/World/Cell01#entity"
    # L12 deck: tip rack, waste, reagent positions (challenge reagent in pos 1, rescue reagent in pos 2: the twin's deck)
    l12 = next(v for v in devs if "DispensingFunction" in ab["fn"][v])
    P = ab["poses"][l12]
    pick = lambda suffix: next(p for p in P if p.endswith(suffix))  # noqa: E731
    F += [f"tip_rack(l12,{name(pick('/tip_rack_frames/rack_1#entity'), 'pose')}).",
          f"waste(l12,{name(pick('/waste_frame#entity'), 'pose')}).",
          f"reagent_pose(challenge,{name(pick('/reagent_rack_frames/rack_1/pos_1#entity'), 'pose')}).",
          f"reagent_pose(rescue,{name(pick('/reagent_rack_frames/rack_1/pos_2#entity'), 'pose')})."]
    # wells: free = not used by the study's existing interventions or arms; targets from the well's own interfaces
    used = set(ab["used_wells"]) | set(ab["arm_wells"]) | set(consumed)     # + wells of executed plans
    idx = 0
    for r in "ABCDEFGH":
        for c in range(1, 13):
            idx += 1
            w = f"{r}{c:02d}"
            if w in used:
                continue
            wi = f"{SDT}{PLATE}/Wells/{w}#entity"
            wa = atom(w)
            names[wa] = wi
            F.append(f"free({wa},{idx}).")
            for kind, fr in (("pipette", "pipette_target_frame"), ("imaging", "imaging_target_frame")):
                F.append(f"well_pose({wa},{kind},{name(f'{SDT}{PLATE}/Wells/{w}/Interfaces/{fr}#entity', 'pose')}).")
    # durations (deciseconds) from the twin's traces
    td = trace_durations()
    ds = lambda s: int(round(10 * s))  # noqa: E731
    for r, leg in (("r01", td["r01_leg"]), ("r02", td["r02_leg"])):
        for k, f in LEG_SPLIT.items():
            F.append(f"leg_part({r},{k},{ds(f * leg)}).")
    pick_part = sum(LEG_SPLIT[k] for k in ("approach", "insert", "grasp", "lift")) * td["r01_leg"]
    stow = 3.0
    D = dict(check=0.5, identity=0.0, present=5.0, stow=stow, wait_env=1.0, store=td["l10_store"],
             load=td["l17_load"], image=td["image_well"], qc=120.0, tool_couple=td["tool_couple"],
             **{k: f * td["dose_well"] for k, f in DOSE_SPLIT.items()})
    for k, v in D.items():
        F.append(f"dur({k},{ds(v)}).")
    F += [f"ddur(l10,present,{ds(td['l10_retrieve'] - pick_part - stow)}).", f"ddur(l17,present,{ds(td['l17_present'])}).",
          f"ddur(l17,stow,{ds(td['l17_present'])})."]
    # requirement, window, candidates
    F += [f"req({int(round(req_bits * 1000))}).", f"window({ds(window_s)}).", f"margin_pct({MARGIN_PCT}).", f"rescue_au({int(round(RESCUE_AU * 100))})."]
    for c in cands["candidates"]:
        F.append(f"cand({c['id']},{int(round(c['dose_au'] * 100))},{c['delay_h']},{c['reps']},"
                 f"{int(round(c['eig_bits'] * 1000))}).")
    return F, names, td, D


# ------------------------------------------------------------------------------------------------------ 3. solve
def solve(F, timeout_s=120):
    ctl = clingo.Control(["--opt-mode=opt", "--parallel-mode=4", "--warn=none"])
    ctl.load(LP)
    ctl.add("base", [], "\n".join(F))
    t0 = time.time()
    ctl.ground([("base", [])])
    tg = time.time() - t0
    best = {}

    def on_model(m):
        best["atoms"] = [str(a) for a in m.symbols(shown=True)]
        best["syms"] = list(m.symbols(shown=True))
        best["cost"] = list(m.cost)
        best["optimal"] = m.optimality_proven

    with ctl.solve(on_model=on_model, async_=True) as h:
        h.wait(timeout_s)
        h.cancel()
        res = h.get()
    st = ctl.statistics
    return dict(result=str(res), optimal=bool(res.exhausted) and bool(best), ground_s=round(tg, 2),
                solve_s=round(time.time() - t0 - tg, 2), atoms=len(best.get("atoms", [])),
                rules=int(st["problem"]["lp"]["rules"]), **({"model": best} if best else {}))


SAFETY = {"s1": "l12_deck_airspace", "s2": "l10_environment_valid", "s3": "l17_calibration_valid",
          "s4": "tool_contamination_compatible", "s5": "protocol window", "s6": "enclosure_door_interlock",
          "s7": "identity_verified", "s8": "contamination_suspected_blocks", "s9": "challenge_requires_controls"}


def diagnose(F, timeout_s):
    """Which single safety constraint, when relaxed, makes the requirement realisable (the refusal's reason)."""
    out = []
    for s in SAFETY:
        if "model" in solve(F + [f"relax({s})."], timeout_s):
            out.append(s)
    return out


# ---------------------------------------------------------------------------------------------- 4. plan assembly
def sym2py(s):
    if s.type == clingo.SymbolType.Number:
        return s.number
    if s.type == clingo.SymbolType.String:
        return s.string
    if s.arguments:
        return [s.name] + [sym2py(a) for a in s.arguments]
    return s.name


def gkey(x):
    """A flat readable key of a step group: legref_1, op_dose_a01_challenge_85, safety_l17_calibration_valid, start."""
    if isinstance(x, list):
        return "_".join(gkey(y) for y in x)
    return str(x)


def assemble(sol, names, cands, req_bits, window_s, td, D, state):
    sy = sol["model"]["syms"]
    get = lambda n: [[sym2py(a) for a in s.arguments] for s in sy if s.name == n]  # noqa: E731
    cid = get("selected")[0][0]
    cand = next(c for c in cands["candidates"] if c["id"] == cid)
    roles = {}
    for w, r in get("role"):
        roles.setdefault(r, []).append(w.upper())
    for r in roles:
        roles[r].sort()
    sess = {s: t for s, t in get("session")}
    trips = {}
    for s, pos, kp, act, grp in [(a[0], a[2], a[1], a[3], a[4]) for a in get("step")]:
        trips.setdefault((s, kp), []).append((pos, act, grp))
    tdur, pdur = {}, {}
    for s, k, _p, du in get("sdur"):      # window-relevant: from the trip start (10000); preparation (< 10000) apart
        d_ = tdur if _p >= 10000 else pdur
        d_[(s, k)] = d_.get((s, k), 0) + du
    mats = {}
    for s, m, k in get("in_trip"):
        mats.setdefault((s, k), []).append(m)
    legs = {}
    for t, i, r, a, b in get("leg"):
        legs.setdefault(t, []).append(dict(index=i, robot=r, src=a, dst=b))
    for v in legs.values():
        v.sort(key=lambda x: x["index"])

    def describe(act, grp):
        prim = act[0] if isinstance(act, list) else act
        st = dict(primitive=prim)
        if prim == "cmd":
            dev, c = act[1], act[2]
            cname = c[0] if isinstance(c, list) else c
            st = dict(level="device_command", primitive=cname, device=dev, device_iri=names.get(dev))
            if isinstance(c, list):
                args = c[1:]
                st["args"] = [names.get(a, a) if isinstance(a, str) else a for a in args]
                if cname == "dispense":
                    st["dose_au"] = args[1] / 100.0
            if cname in DISCHARGES:
                st["discharges_rule"] = DISCHARGES[cname]
                st["level"] = "safety_step"
        else:
            st["level"] = "tool" if prim == "tool_couple" else "motion"
            st["robot"] = act[1]
            st["robot_iri"] = names.get(act[1])
            poses = [a[1] if isinstance(a, list) else a for a in act[2:] if not isinstance(a, int)]
            st["poses"] = [names.get(p, p) for p in poses if isinstance(p, str)]
            st["approach_of"] = [isinstance(a, list) and a[0] == "appr" for a in act[2:]]
            if prim == "tool_couple":
                st["tool"] = act[2]
                st["tool_iri"] = names.get(act[2])
                st["poses"] = [names.get(act[3])]
        st["term"] = act
        st["group"] = gkey(grp)
        if isinstance(grp, list) and grp[0] == "op":
            m = grp[1]
            st["material"] = m
        if isinstance(grp, list) and grp[0] == "safety":
            st["discharges_rule"] = grp[1]
            st["level"] = "safety_step"
        return st

    durs = dict((k, v) for k, v in D.items())
    sessions = []
    for (s, k), steps in sorted(trips.items(), key=lambda x: (sess[x[0][0]], x[0][1])):
        steps.sort()
        out = []
        for j, (pos, act, grp) in enumerate(steps):
            d = describe(act, grp)
            d["index"] = j
            d["pos"] = pos
            out.append(d)
        dev = next((x["device"] for x in out if x["level"] == "device_command" and x["group"].startswith("op")), None)
        sessions.append(dict(id=f"{s}_trip{k}", session=s, trip=k, t_h=sess[s], device=dev,
                             material=[m for m in mats.get((s, k), [])], duration_s=tdur[(s, k)] / 10.0,
                             prep_s=pdur.get((s, k), 0) / 10.0,
                             route_out=legs.get(dev, []), steps=out))
    # annotate step durations (s) the way the program summed them
    lp = {r: {k: f * (td["r01_leg"] if r == "r01" else td["r02_leg"]) for k, f in LEG_SPLIT.items()} for r in ("r01", "r02")}
    for se in sessions:
        for st in se["steps"]:
            p = st["primitive"]
            if st["level"] in ("motion",):
                st["duration_s"] = round(lp[st["robot"]].get(p, 0.0), 2)
            elif p == "tool_couple":
                st["duration_s"] = round(D["tool_couple"], 2)
            else:
                key = dict(check_interlocks="check", verify_identity="identity", wait_environment="wait_env",
                           image_well="image", validate="qc").get(p, p)
                if st.get("device") == "l10" and p == "present":
                    st["duration_s"] = round(td["l10_retrieve"] - sum(LEG_SPLIT[k] for k in ("approach", "insert", "grasp", "lift")) * td["r01_leg"] - 3.0, 2)
                elif st.get("device") == "l17" and p in ("present", "stow"):
                    st["duration_s"] = round(td["l17_present"], 2)
                else:
                    st["duration_s"] = round(durs.get(key, 0.0), 2)
    cost = sol["model"]["cost"][0]
    return dict(
        requirement_bits=req_bits, window_s=window_s, state=state,
        selected=dict(**{k: cand[k] for k in ("id", "dose_au", "delay_h", "reps", "eig_bits", "predicted_effect_um")},
                      rescue_au=RESCUE_AU),
        cost=dict(value=cost, unit="decisecond-equivalents (robot / device time + 60 s per well)"),
        wells=roles, sessions=sessions,
        feasible_candidates=sorted([c["id"] for c in cands["candidates"] if c["eig_bits"] >= req_bits]),
        solver=dict(**{k: v for k, v in sol.items() if k != "model"}, cost_vector=sol["model"]["cost"]),
        durations_s={k: round(v, 3) for k, v in td.items() if k != "n"}, trace_counts=td["n"],
        names={k: v for k, v in names.items()})


# ------------------------------------------------------------------------------------------------------ outputs
def write_md(plan, path):
    s = plan["selected"]
    L = [f"# Derived plan: required information gain {plan['requirement_bits']} bits",
         "",
         f"- **Selected experiment** `{s['id']}`: challenge {s['dose_au']} au, rescue {s['rescue_au']} au after "
         f"{s['delay_h']} h, {s['reps']} replicate(s) per arm; EIG {s['eig_bits']:.3f} bits.",
         f"- **Wells** (free wells of Plate_P17): " + "; ".join(f"{k}: {', '.join(v)}" for k, v in plan["wells"].items()),
         f"- **Cost** {plan['cost']['value']} ({plan['cost']['unit']}); feasible candidates: "
         f"{len(plan['feasible_candidates'])}",
         f"- **Solver** {plan['solver']['result']}, optimal {plan['solver']['optimal']}, "
         f"{plan['solver']['rules']} ground rules, ground {plan['solver']['ground_s']} s, solve {plan['solver']['solve_s']} s",
         ""]
    for se in plan["sessions"]:
        L += [f"## Session {se['session']} (t = {se['t_h']} h), trip {se['trip']}: {se['device']}, "
              f"{se['duration_s']:.1f} s outside the incubator (window {plan['window_s']:.0f} s)", "",
              "| # | Level | Primitive | Robot / device | Pose / argument | s | Discharges |", "|---|---|---|---|---|---|---|"]
        for st in se["steps"]:
            who = st.get("robot") or st.get("device")
            arg = ", ".join(short(p).replace(SDT + PLATE + "/", "") for p in st.get("poses", []) or [])
            if st.get("args"):
                arg = ", ".join(short(a).replace(f"{SDT}{PLATE}/", "") if isinstance(a, str) else str(a)
                                for a in st["args"])
            L.append(f"| {st['index']} | {st['level']} | {st['primitive']} | {who} | {arg} | {st['duration_s']} | "
                     f"{st.get('discharges_rule', '')} |")
        L.append("")
    open(path, "w").write("\n".join(L))


def write_abox(plan, cands, path):
    sys.path.insert(0, os.path.join(MOD, "src"))
    from dl import PREFIXES
    A, declared = [], set()

    def decl(i):
        if i not in declared:
            declared.add(i)
            A.append(f"Declaration(NamedIndividual(<{i}>))")

    def Ty(i, c):
        decl(i)
        A.append(f"ClassAssertion(:{c} <{i}>)")

    def R(p, a, b):
        decl(a)
        decl(b)
        A.append(f"ObjectPropertyAssertion(:{p} <{a}> <{b}>)")

    def Dv(p, a, v, dt="xsd:string"):
        decl(a)
        A.append(f'DataPropertyAssertion(:{p} <{a}> "{v}"^^{dt})')

    req = f"{E2M}/requirement"
    Ty(req, "InformationGainRequirement")
    Dv("requiredGain_bits", req, plan["requirement_bits"], "xsd:double")
    models = {}
    for m, c in (("M1_graded", "GradedRecoveryModel"), ("M2_threshold", "ThresholdRecoveryModel"),
                 ("M3_protective", "ProtectiveThresholdModel")):
        models[m] = f"{E2M}/model/{m}"
        Ty(models[m], c)
        Dv("statementText", models[m], {"M1_graded": "graded recovery", "M2_threshold": "threshold (point of no return)",
                                        "M3_protective": "protective, moving threshold"}[m])
    belief = f"{SDT}#culture_sdt"
    for c in cands["candidates"]:
        ci = f"{E2M}/candidate/{c['id']}"
        Ty(ci, "ExperimentCandidate")
        for k, p, dt in (("eig_bits", "expectedGain_bits", "xsd:double"), ("delay_h", "rescueDelay_h", "xsd:double"),
                         ("dose_au", "doseAU", "xsd:double"), ("reps", "replicateCount", "xsd:integer")):
            Dv(p, ci, c[k], dt)
        if c["id"] in plan.get("candidate_optima", {}) and plan["candidate_optima"][c["id"]] is not None:
            Dv("planCost", ci, plan["candidate_optima"][c["id"]], "xsd:integer")
        for m in models.values():
            R("discriminatesModel", ci, m)
        e = f"{ci}/eig"
        Ty(e, "InformationGainEstimate")
        R("estimatesGainOf", e, ci)
        R("conditionedOnBelief", e, belief)
        Dv("expectedGain_bits", e, c["eig_bits"], "xsd:double")
    sel = f"{E2M}/candidate/{plan['selected']['id']}"
    R("selectedUnder", sel, req)
    plan_i = f"{E2M}/plan"
    Ty(plan_i, "ExperimentRealisationPlan")
    R("realisesProposal", plan_i, sel)
    der = f"{E2M}/derivation"
    Ty(der, "PlanDerivation")
    R("derivesPlan", der, plan_i)
    ax = f"{E2M}/axioms"
    Ty(ax, "DerivationAxiomSet")
    Dv("sourceDocument", ax, "L3-logical-axiomatization/axioms/experiment-to-motion-axioms.md")
    R("appliesAxiomSet", der, ax)
    design = f"{E2M}/design"
    Ty(design, "DelayedRescueStudyDesign")
    Dv("rescueDelay_h", design, plan["selected"]["delay_h"], "xsd:double")
    for role, cls in (("rescued", "ChallengeRescueArm"), ("comparator", "ChallengeOnlyArm"), ("control", "ControlArm")):
        a = f"{design}/arm/{role}"
        Ty(a, cls)
        R("hasArm", design, a)
    n_mot = n_cmd = n_scene = n_mat = 0
    for se in plan["sessions"]:
        si = f"{E2M}/session/{se['id']}"
        Ty(si, "ProtocolSession")
        R("hasSession", plan_i, si)
        Dv("scheduledAt_h", si, se["t_h"], "xsd:double")
        scene = {}
        # scene designators: one transfer per leg (out and back), one device operation per material / trip block
        for st in se["steps"]:
            g = st["group"]
            if g.startswith("legref"):
                key = g
                if key not in scene:
                    scene[key] = f"{si}/transfer/leg{g.split('_')[-1]}"
                    Ty(scene[key], "PlateTransferDesignator")
                    Dv("stepIndex", scene[key], st["index"], "xsd:integer")
                    n_scene += 1
                parent = scene[key]
            else:
                key = g
                if key not in scene:
                    scene[key] = f"{si}/operation/{key}"
                    Ty(scene[key], "DeviceOperationDesignator")
                    Dv("stepIndex", scene[key], st["index"], "xsd:integer")
                    n_scene += 1
                parent = scene[key]
            di = f"{si}/step/{st['index']:03d}_{st['primitive']}"
            if st["level"] in ("motion", "tool"):
                cls = {"approach": "ApproachMotion", "insert": "InsertMotion", "grasp": "GraspMotion",
                       "lift": "LiftMotion", "transit": "TransitMotion", "place": "PlaceMotion",
                       "release": "ReleaseMotion", "retract": "RetractMotion", "tool_couple": "ToolCoupleMotion"}[
                    st["primitive"]]
                Ty(di, cls)
                R("performedByRobot", di, st["robot_iri"])
                if parent.split("/")[-2] == "transfer":
                    R("performedByRobot", parent, st["robot_iri"])
                for p in st.get("poses") or []:
                    R("boundToPose", di, p)
                    if st["primitive"] in ("insert", "place"):
                        R("boundToPose", parent, p)
                if st.get("tool_iri"):
                    R("usesToolDesignator", di, st["tool_iri"])
                n_mot += 1
            else:
                Ty(di, "SafetyStepDesignator" if st["level"] == "safety_step" else "DeviceCommandDesignator")
                R("commandsDevice", di, st["device_iri"])
                R("boundToDevice", parent, st["device_iri"])
                if st.get("discharges_rule"):
                    R("dischargesRule", di, f"{SAFE}/{st['discharges_rule']}")
                n_cmd += 1
            Dv("primitiveName", di, st["primitive"])
            Dv("stepIndex", di, st["index"], "xsd:integer")
            Dv("estimatedDuration_s", di, st["duration_s"], "xsd:double")
            R("hasStep", si, di)
            R("refinesInto", parent, di)
        # material designators refine into the trip's transfers (the route) and their own device operation
        transfers = [sc for key, sc in scene.items() if key.startswith("legref")]
        for sc in transfers:
            for leg in se["route_out"]:
                R("routeVia", sc, plan["names"][leg["src"]])
                R("routeVia", sc, plan["names"][leg["dst"]])
        for m in se["material"]:
            kind, w = m[0], m[1]
            mi = f"{si}/material/{gkey(m)}"
            if kind == "dose":
                Ty(mi, "ChallengeDoseDesignator" if m[2] == "challenge" else "RescueDoseDesignator")
                Dv("doseAU", mi, m[3] / 100.0, "xsd:double")
            else:
                Ty(mi, "ImageWellDesignator")
            R("concernsWell", mi, plan["names"][w])
            Dv("stepIndex", mi, n_mat, "xsd:integer")
            R("hasStep", si, mi)
            n_mat += 1
            for sc in transfers + [scene[k] for k in (f"op_{gkey(m)}",) if k in scene]:
                R("refinesInto", mi, sc)
    hdr = [f"Prefix({k}:=<{v}>)" for k, v in PREFIXES.items()]
    hdr += ["", "Ontology(<https://aicor.example/okf/sdt/lab1/abox/plan>",
            "Import(<http://aicor.knowledge/okf/lab-automation-twin>)",
            f'Annotation(rdfs:comment "Plan derived for a required information gain of {plan["requirement_bits"]} '
            f'bits (derive_plan.py; E2M1-E2M8).")']
    open(path, "w").write("\n".join(hdr + A + [")"]) + "\n")
    return dict(material=n_mat, scene=n_scene, motion=n_mot, command=n_cmd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gain-bits", type=float, default=0.5, help="required expected information gain (bits)")
    ap.add_argument("--window-s", type=float, default=600.0, help="protocol window outside the incubator per trip")
    ap.add_argument("--uncalibrated", action="store_true", help="L17's calibration is not valid at the start")
    ap.add_argument("--coupled", action="store_true", help="R02 is known to carry T01 at every trip start")
    ap.add_argument("--interlocks-open", action="store_true")
    ap.add_argument("--contaminated", action="store_true", help="the culture SDT suspects contamination of the plate")
    ap.add_argument("--samples", type=int, default=800)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--refresh", action="store_true", help="recompute the EIG candidates")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--prior-from", default=None, help="out/realised_<tag>.json: condition on an executed plan's "
                    "posterior over M1-M3 (sequential design)")
    ap.add_argument("--abox", action="store_true", help="also write abox/plan.ofn (the module's plan ABox)")
    ap.add_argument("--timeout", type=float, default=120.0)
    a = ap.parse_args()
    state = dict(calibrated=not a.uncalibrated, coupled=a.coupled, interlocks=not a.interlocks_open,
                 contaminated=a.contaminated)
    tag = a.tag or f"g{int(round(a.gain_bits * 100)):03d}"
    os.makedirs(OUT, exist_ok=True)
    prior = None
    if a.prior_from:
        prior = {m: max(float(p), 1e-6) for m, p in json.load(open(a.prior_from))["posterior"].items()}
        print("[e2m] prior over models from " + os.path.basename(a.prior_from) + ": " +
              ", ".join(f"{m} {p:.3f}" for m, p in prior.items()))
    cands = eig_candidates(a.samples, a.seed, a.refresh, prior)
    print(f"[e2m] {len(cands['candidates'])} candidates; EIG range "
          f"{min(c['eig_bits'] for c in cands['candidates']):.3f}..{max(c['eig_bits'] for c in cands['candidates']):.3f} "
          f"bits (max log2 3 = {cands['max_bits']})")
    ab = read_abox()
    consumed = sorted(json.load(open(a.prior_from))["observations"]) if a.prior_from else []
    if consumed:
        print(f"[e2m] wells consumed by the executed plan (not free): {', '.join(consumed)}")
    F, names, td, D = facts(ab, cands, a.gain_bits, a.window_s, state, consumed)
    open(os.path.join(BUILD, f"facts_{tag}.lp"), "w").write("\n".join(F) + "\n")
    print(f"[e2m] {len(F)} facts from the ABox, the twin traces and the candidates -> build/e2m/facts_{tag}.lp")
    sol = solve(F, a.timeout)
    rep = dict(tag=tag, requirement_bits=a.gain_bits, window_s=a.window_s, state=state,
               solver={k: v for k, v in sol.items() if k != "model"})
    if "model" not in sol:
        feas = [c["id"] for c in cands["candidates"] if c["eig_bits"] >= a.gain_bits]
        why = ("no candidate in the frame reaches the required gain" if not feas else
               "no plan satisfies the safety / feasibility constraints for any candidate meeting the requirement")
        blocking = diagnose(F, a.timeout) if feas else []
        if blocking:
            why += "; blocked by " + ", ".join(f"{s} ({SAFETY[s]})" for s in blocking)
        rep.update(plan=None, reason=why, feasible_candidates=feas, blocking_constraints=blocking)
        json.dump(rep, open(os.path.join(OUT, f"plan_{tag}.json"), "w"), indent=1)
        print(f"[e2m] NO PLAN ({sol['result']}): {why}")
        return 2
    plan = assemble(sol, names, cands, a.gain_bits, a.window_s, td, D, state)
    plan["tag"] = tag
    plan["prior_over_models"] = cands["prior_over_models"]
    plan["prior_from"] = os.path.basename(a.prior_from) if a.prior_from else None
    # the optimum of every candidate that meets the requirement (E2M1's least-cost claim is checked against these)
    plan["candidate_optima"] = {}
    for cid in plan["feasible_candidates"]:
        r = solve(F + [f":- not selected({cid})."], a.timeout)
        plan["candidate_optima"][cid] = r["model"]["cost"][0] if "model" in r else None
    plan["candidate_eig_bits"] = {c["id"]: c["eig_bits"] for c in cands["candidates"]}
    plan["facts_file"] = os.path.relpath(os.path.join(BUILD, f"facts_{tag}.lp"), MOD)
    json.dump(plan, open(os.path.join(OUT, f"plan_{tag}.json"), "w"), indent=1)
    write_md(plan, os.path.join(OUT, f"plan_{tag}.md"))
    s = plan["selected"]
    print(f"[e2m] selected {s['id']}: dose {s['dose_au']} au, delay {s['delay_h']} h, {s['reps']} reps, EIG "
          f"{s['eig_bits']:.3f} bits; cost {plan['cost']['value']}; optimal {sol['optimal']} "
          f"(ground {sol['ground_s']} s, solve {sol['solve_s']} s)")
    for se in plan["sessions"]:
        print(f"[e2m]   {se['id']:12s} t={se['t_h']:>4} h  {se['device']}  {len(se['steps'])} steps  "
              f"{se['duration_s']:.1f} s")
    if a.abox:
        n = write_abox(plan, cands, os.path.join(ABOX, "plan.ofn"))
        print(f"[e2m] abox/plan.ofn: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
