"""The reproducible pipeline: from the culture-level plan to the executed experiment, its audit trail and its proofs.

Every stage is a command over versioned inputs. The manifest records, per stage, the command, the code it ran (sha256),
the files it wrote (sha256 of the canonical content) and its exit status; the inputs (registry, ontology ABox, ASP
program, scene, culture surrogate code) and the tool versions are recorded once. The manifest's own hash identifies
the experiment's whole derivation. `--verify` re-runs every stage and compares the canonical output hashes with a
recorded manifest: a reproduction is a run whose manifest hash is the same.

Canonical content: JSON outputs without wall-clock fields (VOLATILE), other files as bytes. Nothing else is excluded.

    env_cad/bin/python -m rsa.reproduce                       # run, write rsa/out/repro/manifest.json
    env_cad/bin/python -m rsa.reproduce --verify              # run again, compare with the recorded manifest
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MOD = os.path.join(ROOT, "okf", "lab-automation-twin")
DERIV = os.path.join(MOD, "L3-logical-axiomatization", "derivation")
PY = os.path.join(ROOT, "env_cad", "bin", "python")
REPRO = os.path.join(HERE, "out", "repro")
WATCH = [os.path.join(HERE, "out"), os.path.join(DERIV, "out"), os.path.join(MOD, "build", "e2m")]
VOLATILE = {"solve_s", "ground_s", "wall_s", "validator_wall_s"}   # wall-clock measurements, not content
SYMBOLIC = ["nominal", "uncalibrated_known", "calibration_lapsed", "tip_lost", "identity_swap", "tool_changer_slow",
            "imager_swapped", "imager_incapable", "rescue_unbound", "control_dropped", "contamination", "card_incomplete"]

INPUTS = {  # what the derivation reads, grouped by what it is
    "culture plan and lab designators (LDL)": [os.path.join(HERE, "registry", "lab")],
    "kernel registry (categories, constraints, devices, norms, scenarios, competency questions)": [
        os.path.join(HERE, "registry", f) for f in ("categories.yaml", "constraints.yaml", "devices.yaml", "norms.yaml",
                                                    "scenarios.yaml", "cq.yaml")],
    "lab ontology ABox (semantic digital twin, safety, experiments)": [
        os.path.join(MOD, "abox", f) for f in ("sdt.ofn", "safety.ofn", "experiments.ofn")],
    "experiment-to-motion axioms (ASP)": [os.path.join(DERIV, "experiment_to_motion.lp")],
    "Cell 01 scene (composed overlay)": [os.path.join(ROOT, "scenes", "cell01_twin.usda")],
    "culture surrogate (ILLUSTRATIVE, D016)": [os.path.join(ROOT, "twin", "culture")],
    "twin duration traces": [os.path.join(ROOT, "test_reports", "episodes", "cell01_episodes_raw.json")],
    "recorded Isaac Sim runs (physics; read, not re-executed, by this pipeline)": [
        os.path.join(HERE, "out", f"trail_isaac_{s}.json") for s in ("nominal", "identity_swap", "calibration_lapsed")],
}

STAGES = [  # (id, what it derives, argv, code)
    ("design", "EIG over the competing recovery models; least-cost safe plan meeting 0.5 bit (clingo)",
     [os.path.join(DERIV, "derive_plan.py"), "--gain-bits", "0.5", "--refresh"], [os.path.join(DERIV, "derive_plan.py")]),
    ("step-proof", "SMT validation of the plan: executability, safety, time, realization, gain, least cost (z3)",
     [os.path.join(DERIV, "validate_plan_z3.py"), os.path.join(DERIV, "out", "plan_g050.json")],
     [os.path.join(DERIV, "validate_plan_z3.py")]),
    ("culture", "culture plan: causal order, surrogate execution, mapping to the lab, transport and tending feasibility",
     ["-m", "rsa.culture_plan"], ["culture_plan.py", "ldl.py"]),
    ("lab-plan", "lab action designators: order, threats, instruments, process models, handlers, guarantees, KPIs",
     ["-m", "rsa.ldl"], ["ldl.py", "ldl_trust.py"]),
    ("controller", "CRAM/RPL structured reactive controller (Lisp)", ["-m", "rsa.ldl_to_cram"], ["ldl_to_cram.py", "sexp_pretty.py"]),
    ("execution", "kernel execution on the symbolic backend: 12 scenarios, audit trails, critic, tamper test, competency questions",
     ["-m", "rsa.run_example"] + SYMBOLIC, ["run_example.py", "core.py", "library.py", "backend.py", "audit.py", "critic.py",
                                             "kb.py", "cq.py", "checks.py"]),
    ("grounding", "cultures on plates, trips, device programs, monitors, reactions", ["-m", "rsa.grounding"], ["grounding.py"]),
    ("frames", "goal frames from the scene; reachability (IK) of every goal", ["-m", "rsa.motion_frames"], ["motion_frames.py"]),
    ("motions", "Giskard motion statecharts: frames, constraints, monitors, cancels", ["-m", "rsa.giskard_motions"],
     ["giskard_motions.py"]),
    ("independence", "the culture plan in 13 lab variants", ["-m", "rsa.independence"], ["independence.py"]),
    ("refinement-proof", "motion plan refines the culture plan (O1-O7, negative controls)", ["-m", "rsa.refinement_proof"],
     ["refinement_proof.py"]),
    ("protocol", "experimentation plan (protocol) and audit certificate: chains, tamper test, re-execution of every symbolic trail",
     ["-m", "rsa.protocol"], ["protocol.py"]),
]


def canon(x):
    if isinstance(x, dict):
        return {k: canon(v) for k, v in x.items() if k not in VOLATILE}
    if isinstance(x, list):
        return [canon(v) for v in x]
    return x


def file_sha(path):
    if path.endswith(".json"):
        try:
            data = json.load(open(path))
            return hashlib.sha256(json.dumps(canon(data), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        except ValueError:
            pass
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def tree_sha(path):
    if os.path.isfile(path):
        return file_sha(path)
    h = hashlib.sha256()
    for d, dirs, files in sorted(os.walk(path)):
        dirs[:] = sorted(x for x in dirs if x != "__pycache__")
        for f in sorted(files):
            if f.endswith(".pyc"):
                continue
            p = os.path.join(d, f)
            h.update(os.path.relpath(p, path).encode() + b"\0" + open(p, "rb").read())
    return h.hexdigest()


def snapshot():
    s = {}
    for w in WATCH:
        for d, dirs, files in os.walk(w):
            dirs[:] = [x for x in dirs if x != "__pycache__"]
            for f in files:
                if f in ("manifest.json", "manifest_rerun.json", "reproduction.json"):
                    continue
                p = os.path.join(d, f)
                s[p] = os.stat(p).st_mtime_ns
    return s


def rel(p):
    return os.path.relpath(p, ROOT)


def environment():
    r = subprocess.run([PY, "-c", "import clingo, z3, numpy, sys; print(clingo.__version__, z3.get_version_string(), numpy.__version__, "
                        "sys.version.split()[0])"], capture_output=True, text=True)
    c, z, n, p = r.stdout.split()
    try:
        from pxr import Usd  # noqa: F401
        usd = "pxr"
    except Exception:
        usd = None
    return dict(python=p, clingo=c, z3=z, numpy=n, platform=platform.platform(), usd=usd)


def run():
    stages = []
    for sid, what, argv, code in STAGES:
        before = snapshot()
        t0 = time.time()
        r = subprocess.run([PY] + argv, cwd=ROOT, capture_output=True, text=True, timeout=3600)
        wall = round(time.time() - t0, 1)
        after = snapshot()
        written = sorted(p for p, m in after.items() if before.get(p) != m)
        code_paths = [c if os.path.isabs(c) else os.path.join(HERE, c) for c in code]
        stages.append(dict(id=sid, derives=what, command=" ".join(["python"] + [rel(a) if os.path.isabs(a) else a for a in argv]),
                           code={rel(c): file_sha(c) for c in code_paths}, exit=r.returncode,
                           outputs={rel(p): file_sha(p) for p in written}, wall_s=wall,
                           log_tail=[l for l in r.stdout.strip().splitlines() if l.strip()][-3:]))
        print(f"[repro] {sid:17} exit {r.returncode}  {len(written):3} files  {wall:6.1f} s  {(stages[-1]['log_tail'] or [''])[-1][:110]}")
        if r.returncode != 0:
            print(r.stdout[-2000:], r.stderr[-2000:])
    inputs = {k: {rel(p): tree_sha(p) for p in v} for k, v in INPUTS.items()}
    body = dict(experiment="challenge-rescue", culture_plan=rel(os.path.join(HERE, "registry", "lab", "culture_plan.ldl")),
                inputs=inputs, environment=environment(), volatile_fields=sorted(VOLATILE),
                stages=[{k: v for k, v in s.items() if k not in ("wall_s", "log_tail")} for s in stages])
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return dict(body, manifest_sha256=digest, timings={s["id"]: s["wall_s"] for s in stages},
                logs={s["id"]: s["log_tail"] for s in stages}, ok=all(s["exit"] == 0 for s in stages))


def compare(a, b):
    diffs = []
    for k in ("inputs", "environment"):
        if a[k] != b[k]:
            diffs.append(dict(where=k, recorded=a[k], now=b[k]))
    sa, sb = {s["id"]: s for s in a["stages"]}, {s["id"]: s for s in b["stages"]}
    per = {}
    for sid in sa:
        x, y = sa[sid], sb.get(sid, {})
        files = sorted(set(x["outputs"]) | set(y.get("outputs", {})))
        bad = [f for f in files if x["outputs"].get(f) != y.get("outputs", {}).get(f)]
        per[sid] = dict(outputs=len(files), identical=len(files) - len(bad), differing=bad,
                        code_same=x["code"] == y.get("code"), exit_same=x["exit"] == y.get("exit"))
    return dict(reproduced=a["manifest_sha256"] == b["manifest_sha256"], manifest_recorded=a["manifest_sha256"],
                manifest_now=b["manifest_sha256"], stages=per, other=diffs)


def main(argv):
    os.makedirs(REPRO, exist_ok=True)
    path = os.path.join(REPRO, "manifest.json")
    if "--verify" in argv:
        recorded = json.load(open(path))
        now = run()
        json.dump(now, open(os.path.join(REPRO, "manifest_rerun.json"), "w"), indent=1)
        c = compare(recorded, now)
        c["timings_recorded"], c["timings_now"] = recorded["timings"], now["timings"]
        json.dump(c, open(os.path.join(REPRO, "reproduction.json"), "w"), indent=1)
        for sid, s in c["stages"].items():
            print(f"[verify] {sid:17} {s['identical']}/{s['outputs']} outputs identical" + (f"; differ: {s['differing'][:4]}" if s["differing"] else ""))
        print(f"[verify] manifest {c['manifest_recorded'][:16]} vs {c['manifest_now'][:16]}: "
              f"{'REPRODUCED' if c['reproduced'] else 'NOT REPRODUCED'}")
        return 0 if c["reproduced"] and now["ok"] else 1
    m = run()
    json.dump(m, open(path, "w"), indent=1)
    print(f"[repro] manifest {m['manifest_sha256']} ({'all stages exit 0' if m['ok'] else 'A STAGE FAILED'}) -> {rel(path)}")
    return 0 if m["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
