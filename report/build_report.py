"""Build the technical report on the robot science assistant (RSA) from the pipeline's outputs.

The report is the long companion of paper/build_paper.py: it reuses the paper's data loading, figures, tables, listings
and LaTeX renderer, and adds the kernel, the knowledge, the lab designator language, the process models, the execution
scenarios, the audit and competency questions, the findings log and the roadmap. Every number is read from rsa/out,
the derivation outputs and the reproduction manifest.

    env_cad/bin/python report/build_report.py        # report/rsa_report.tex, report/rsa_report.pdf (lualatex)

ILLUSTRATIVE (D016): the culture biology is Cell 01's surrogate; twin parameters are labelled, not lab facts.
"""

from __future__ import annotations

import collections
import json
import os
import re
import shutil
import subprocess
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import paper.build_paper as BP  # noqa: E402  (loads the outputs, figures and renderer)

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch  # noqa: E402

FIG = os.path.join(HERE, "figures")
BP.FIG = FIG                       # the paper's figure functions save here
OUT, REG = BP.OUT, os.path.join(ROOT, "rsa", "registry")
J, N, C, INK, MUTED, LINE = BP.J, BP.N, BP.C, BP.INK, BP.MUTED, BP.LINE
cp, plan, ldl, gm, frames, rp, zp, rep, ind = BP.cp, BP.plan, BP.ldl, BP.gm, BP.frames, BP.rp, BP.zp, BP.rep, BP.ind
man, repro, aud, prot, cands, runs, K = BP.man, BP.repro, BP.aud, BP.prot, BP.cands, BP.runs, BP.K
grd = J(OUT, "grounding.json")
CATS = yaml.safe_load(open(os.path.join(REG, "categories.yaml")))
CONS = yaml.safe_load(open(os.path.join(REG, "constraints.yaml")))
NORMS = yaml.safe_load(open(os.path.join(REG, "norms.yaml")))["clauses"]
CQS = yaml.safe_load(open(os.path.join(REG, "cq.yaml")))
CATS = CATS.get("categories", CATS)
CQS = CQS.get("questions", CQS) if isinstance(CQS, dict) else CQS
trail = J(OUT, "trail_nominal.json")["entries"]
mh = man["manifest_sha256"]
SRC_LINES = {f: sum(1 for _ in open(os.path.join(ROOT, "rsa", f))) for f in os.listdir(os.path.join(ROOT, "rsa")) if f.endswith(".py")}
LISP_LINES = sum(1 for _ in open(os.path.join(OUT, "challenge_rescue_src.lisp")))
GISK_LINES = sum(1 for _ in open(os.path.join(OUT, "challenge_rescue_giskard.py")))
q = K
QR = [r for r in ldl["quality"]["runs"]]


# ------------------------------------------------------------------------------------------------------------- figures
def save(fig, name):
    BP.save(fig, name)


def fig_arch():
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    ax.set_xlim(0, 10); ax.set_ylim(0, 6.2); ax.axis("off")
    B = dict(
        kb=(0.2, 3.9, 2.6, 1.9, "Knowledge base", "planner facts (ABox → ASP)\nCell 01 component records\nregistries: categories,\nconstraints, norms, devices", C["know"]),
        lib=(3.7, 3.9, 2.6, 1.9, "Plan library", "generalized plans per\ncategory; build sub-plans\nat perform time; no device\nnames (linted)", C["phys"]),
        ldl=(7.2, 3.9, 2.6, 1.9, "Lab designator language", "culture plan, lab plan,\ncontracts, process models,\nepistemic meta model, KPIs", C["grow"]),
        ex=(3.7, 1.75, 2.6, 1.75, "Executive", "lifecycle, projection,\nunderstanding gate,\npolicies, failure handling", C["obs"]),
        be=(0.2, 1.75, 2.6, 1.75, "Backends", "symbolic Cell 01 world\n(fault injection);\nIsaac Sim twin controllers", C["phys"]),
        au=(7.2, 1.75, 2.6, 1.75, "Audit trail", "one hash-chained entry\nper lifecycle transition,\nevidence hashed", C["proof"]),
        cr=(3.7, 0.1, 2.6, 1.15, "Critic", "realization vs validity", C["bad"]),
        cq=(7.2, 0.1, 2.6, 1.15, "Competency questions", "answers with grounds", C["know"]),
        mo=(0.2, 0.1, 2.6, 1.15, "Motion level", "Giskard statecharts", C["obs"]),
    )
    for k, (x, y, w, h, t, s, col) in B.items():
        BP.box(ax, x, y, w, h, t, s, col, fs=8)

    def arrow(a, b, txt="", dx=0, dy=0):
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=10, color=MUTED, lw=1.0))
        if txt:
            ax.text((a[0] + b[0]) / 2 + dx, (a[1] + b[1]) / 2 + dy, txt, fontsize=6.8, color=MUTED, ha="center")
    arrow((2.8, 4.85), (3.7, 4.85), "queries\n+ grounds", dy=0.12)
    arrow((7.2, 4.85), (6.3, 4.85), "contracts", dy=0.12)
    arrow((5.0, 3.9), (5.0, 3.5), "")
    arrow((3.7, 2.6), (2.8, 2.6), "leaves", dy=0.1)
    arrow((6.3, 2.6), (7.2, 2.6), "entries", dy=0.1)
    arrow((8.5, 1.75), (8.5, 1.25), "")
    arrow((7.2, 2.1), (6.3, 0.9), "")
    arrow((1.5, 1.75), (1.5, 1.25), "")
    save(fig, "arch")


def fig_lifecycle():
    fig, ax = plt.subplots(figsize=(7.2, 1.9))
    ax.set_xlim(0, 10.6); ax.set_ylim(0, 2.2); ax.axis("off")
    S = [("open", 0.5, 1.4), ("grounded", 2.1, 1.4), ("accepted", 3.8, 1.4), ("executing", 5.5, 1.4), ("executed", 7.3, 1.9),
         ("failed", 7.3, 0.9), ("repaired", 9.3, 1.9), ("abstained", 9.3, 1.15), ("escalated", 9.3, 0.4)]
    P = {}
    for n, x, y in S:
        col = C["proof"] if n in ("executed", "repaired") else (C["bad"] if n in ("failed", "escalated") else (C["grow"] if n == "abstained" else C["obs"]))
        ax.text(x, y, n, ha="center", va="center", fontsize=8, color=INK,
                bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=col, lw=1.3))
        P[n] = (x, y)
    for a, b in [("open", "grounded"), ("grounded", "accepted"), ("accepted", "executing"), ("executing", "executed"), ("executing", "failed"),
                 ("failed", "repaired"), ("failed", "abstained"), ("failed", "escalated")]:
        (x1, y1), (x2, y2) = P[a], P[b]
        ax.add_patch(FancyArrowPatch((x1 + 0.62, y1), (x2 - 0.68, y2), arrowstyle="-|>", mutation_scale=9, color=MUTED, lw=0.9))
    ax.text(2.95, 0.55, "resolution writes grounds;  acceptance checks constraints + understanding gate;\n"
                        "each transition is one hash-chained audit entry", fontsize=7, color=MUTED, ha="center")
    save(fig, "lifecycle")


def fig_culture():
    T = K["trajectories"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.4, 2.7), gridspec_kw=dict(width_ratios=[1.6, 1]))
    lab = dict(cr=("rescued (A01)", C["phys"]), cc=("comparator (A02)", C["bad"]), ck=("control (A05)", C["obs"]))
    for k, (n, col) in lab.items():
        if k in T:
            a.plot([p["t_h"] for p in T[k]], [p["radius_um"] for p in T[k]], color=col, lw=1.6, label=n)
    for t, s in ((0, "challenge"), (48, "rescue"), (72, "image")):
        a.axvline(t, color=LINE, lw=0.9, ls="--"); a.text(t + 0.8, a.get_ylim()[1] if False else 272, s, fontsize=7, color=MUTED, va="top")
    a.set_xlabel("culture time (h)"); a.set_ylabel("organoid radius (µm, surrogate)"); a.legend(frameon=False, fontsize=7, loc="lower left")
    m = list(K["prior"])
    x = range(len(m))
    b.bar([i - 0.18 for i in x], [K["prior"][k] for k in m], width=0.36, color=LINE, label="prior")
    b.bar([i + 0.18 for i in x], [K["posterior"][k] for k in m], width=0.36, color=C["know"], label="posterior")
    b.set_xticks(list(x)); b.set_xticklabels([k.split("_")[1] for k in m], fontsize=7.5); b.set_ylabel("P(model)")
    b.legend(frameon=False, fontsize=7); b.set_title(f"gain {K['information_gain_bit']:.3f} bit (expected {K['expected_gain_bit']:.3f})", fontsize=7.5, color=MUTED)
    fig.tight_layout()
    save(fig, "culture")


def fig_trust():
    rows = [(t["step"], t["process"], f) for t in ldl["trust"] for f in t["faults"]]
    steps = list(dict.fromkeys(r[0] for r in rows))
    faults = list(dict.fromkeys(r[2]["fault"] for r in rows))
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    for r in rows:
        x, y = steps.index(r[0]), faults.index(r[2]["fault"])
        f = r[2]
        col = C["proof"] if f["detected"] == "full" else C["bad"]
        mk = "o" if "before" in f["timing"] or "non-destructive" in f["timing"] else "s"
        ax.scatter(x, y, s=150, marker=mk, c="white" if f["persistence"] == "transient" else col, edgecolors=col, linewidths=1.6, zorder=3)
    PN = {"substance-transfer": "transfer", "incubation": "incubation", "imaging": "imaging"}
    ax.set_xticks(range(len(steps))); ax.set_xticklabels([f"{s}\n{PN.get(next(r[1] for r in rows if r[0] == s), '')}" for s in steps], fontsize=6.8)
    ax.set_yticks(range(len(faults))); ax.set_yticklabels(faults, fontsize=7)
    ax.set_xlim(-0.6, len(steps) - 0.4); ax.set_ylim(-0.6, len(faults) - 0.4); ax.grid(color=LINE, lw=0.5, zorder=0)
    ax.text(1.0, 1.02, "green: fully detected · red: partly detected (silent case possible)\n"
                       "circle: before the irreversible phase / non-destructive · square: after it · hollow: transient",
            transform=ax.transAxes, fontsize=6.6, color=MUTED, ha="right", va="bottom")
    save(fig, "trust")


def fig_kpi():
    R = [r for r in QR]
    names = [r["run"].replace("isaac_", "I:").replace("_", " ") for r in R]
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.4, 2.6))
    ex = [r["excursion-time"] for r in R]
    a.barh(names, ex, color=[C["bad"] if v > 600 else (C["grow"] if v > 300 else C["phys"]) for v in ex])
    a.axvline(600, color=C["bad"], lw=1, ls="--"); a.axvline(300, color=MUTED, lw=0.8, ls=":")
    a.text(600, -0.9, "window 600 s", fontsize=6.5, color=C["bad"], ha="center"); a.text(300, -0.9, "target", fontsize=6.5, color=MUTED, ha="center")
    a.set_xlabel("longest excursion (s)"); a.invert_yaxis(); a.tick_params(axis="y", labelsize=7)
    b.barh(names, [r["reliability"] for r in R], color=C["obs"]); b.set_xlim(0, 1.32); b.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    b.set_xlabel("reliability (first-attempt goals)")
    b.set_yticklabels([]); b.invert_yaxis()
    for i, r in enumerate(R):
        b.text(1.04, i, f"cost {r['cost']:.1f}", fontsize=6.6, color=MUTED, va="center", ha="left")
    fig.tight_layout()
    save(fig, "kpi")


def fig_reach():
    G = frames["goals"]
    fig, ax = plt.subplots(figsize=(5.6, 2.6))
    for rob, col in (("r01", C["phys"]), ("r02", C["obs"])):
        g = [x for x in G if x["leg"].startswith(rob)]
        ax.scatter([x["margin_deg"] for x in g], [x["sigma_min"] for x in g], s=26, color=col, label=f"{rob.upper()} ({len(g)} goals)", alpha=0.85)
    ax.set_xlabel("smallest joint-limit margin (deg)"); ax.set_ylabel("smallest singular value"); ax.legend(frameon=False, fontsize=7)
    save(fig, "reach")


def fig_trail():
    tr = collections.Counter(e["transition"] for e in trail)
    ag = collections.Counter(e["agent"] for e in trail if e["kind"] in ("motion", "command") and e["transition"] == "executed")
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 2.2))
    keys = ["open", "grounded", "accepted", "executing", "executed"]
    a.bar(keys, [tr[k] for k in keys], color=C["proof"]); a.set_title(f"{len(trail)} entries by transition", fontsize=8, color=MUTED)
    a.tick_params(axis="x", labelsize=7)
    ks = [k for k, _ in ag.most_common()]
    b.bar([k.upper() for k in ks], [ag[k] for k in ks], color=C["obs"]); b.set_title(f"{sum(ag.values())} executed leaves by agent", fontsize=8, color=MUTED)
    fig.tight_layout()
    save(fig, "trail")


def photo(src, name):
    from PIL import Image
    im = Image.open(os.path.join(ROOT, "renders", "lab", src)).convert("RGB")
    im.thumbnail((1500, 1500))
    im.save(os.path.join(FIG, name + ".jpg"), quality=82)


# ------------------------------------------------------------------------------------------------------------- tables
T = dict(BP.T)
short = lambda s, n=110: (s if len(s) <= n else s[:n - 1] + "…")  # noqa: E731

T["concepts"] = (["#", "Concept", "Kernel definition", "Taken from"], [
    ["1", "Designator", "kind, category, determiner, bindings, constraints; kinds action, object, location, motion, device-command, event", "HADL; KnowRob; coraplex"],
    ["2", "Action category", "a card owned by the category: level, parent, effect class, facet, roles, capability, pre/effects, sub-plan, monitors, recovery, evidence", "KnowRob; Cell 01 schemas"],
    ["3", "Category hierarchy", "scientific → lab task → manipulation → motion, device-command beside motion; typed by effect class and facet", "AICOR effect partition; Cell 01"],
    ["4", "Generalized plan", "code of a category that builds the sub-plan from a bound designator at perform time, querying the knowledge base", "CRAM; coraplex"],
    ["5", "Resolution", "a query returns value, grounds (fact atoms used) and rejected alternatives with reasons", "KnowRob resolution; certificates"],
    ["6", "Knowledge base", "the planner's facts, the Cell 01 component records and the kernel registries; one source for all consumers", "e2m derivation; Cell 01 SDT"],
    ["7", "Capability", "a verb qualified by state and by measurement binding (no match ⊂ capability match ⊂ provisional ⊂ validated)", "Cell 01; RSV binding lattice"],
    ["8", "Constraint", "registry entry: id, column (realization or validity), source, text, applies-to, check, ASP rule, z3 theorem", "uc_ccr; e2m S1–S9"],
    ["9", "Lifecycle", "open → grounded → accepted → executing → executed | failed → repaired | abstained | escalated", "Cell 01 schemas"],
    ["10", "Commitment record", "one hash-chained entry per lifecycle transition, with bindings, grounds, verdicts, monitors and evidence", "uc_ccr audit; NEEM schema"],
    ["11", "Two-column verdict", "realization (ran correctly and safely) ⟂ validity (result interpretable); commit only if both hold", "uc_ccr critic"],
    ["12", "Understanding gate + CQs", "an incomplete understanding frame is not accepted; competency questions answered from the runtime trail", "Cell 01 understanding contract"],
])

levels = collections.OrderedDict()
for name, card in CATS.items():
    levels.setdefault(card.get("level"), []).append(name)
LEVEL_NAMES = dict(scientific="scientific", lab_task="lab task", manipulation="manipulation", command="device command", motion="motion")
T["categories"] = (["Level", "#", "Categories"], [[LEVEL_NAMES.get(l, l), str(len(v)), ", ".join(f"`{x}`" for x in v)] for l, v in levels.items()])

T["constraints"] = (["Constraint", "Column", "Applies to", "Statement", "Source"], [
    [f"`{k}`", v.get("column", ""), ", ".join(v.get("applies_to") or ["episode"]), v.get("text", ""), short(v.get("source", ""), 70)] for k, v in CONS.items()])

T["norms"] = (["Clause (ILLUSTRATIVE mapping)", "Topic", "Realised by"], [
    [k, v["topic"], "; ".join(f"{kind}: {', '.join(x)}" for kind, x in v["realised_by"].items())] for k, v in NORMS.items()])

T["ldl_clauses"] = (["Clause", "Meaning over the action's interval", "Operational obligation"], [
    ["`requires`", "holds (and is known to hold) at the start", "acceptance check, or a reason to establish it first"],
    ["`prevents`", "no matching state or event occurs during the action", "a detector and a reaction (abort, contain)"],
    ["`maintains`", "holds throughout the action", "a regulator with a recorded history"],
    ["`achieves`", "holds at the end and persists until changed", "post-condition with an evidence record"],
    ["`goal`", "the effect the action is for; links steps causally", "justified by the experiment's goal"],
    ["`signals`", "the failures the action may raise", "every failure needs a handler in the control program"],
    ["`scope`", "a non-terminating prevents/maintains opened and closed by fluents", "a monitor around the realization"],
])

T["instruments"] = (["Step", "Process", "Function / capability", "Device and slot", "Rejected"], [
    [i["step"], i["process"], f"{i['function']} / `{i['capability']}`", "; ".join(f"{a['device'].upper()} `{a['slot']}`" for a in i["answers"]), str(len(i["rejected"]))]
    for i in ldl["instruments"]])

T["models"] = (["Process", "Component", "Phases", "Irreversible", "Faults", "Must not assume"], [
    [p, m["component"], " → ".join(m["phases"]), m["irreversible"], ", ".join(f["name"] for f in m["faults"]), "; ".join(m["must_not_assume"])]
    for p, m in ldl["models"].items()])

T["trust"] = (["Fault", "Process", "Detected by", "Coverage", "Timing", "Persistence", "Handled"], [])
seen = set()
for t in ldl["trust"]:
    for f in t["faults"]:
        key = (t["process"], f["fault"])
        if key in seen:
            continue
        seen.add(key)
        T["trust"][1].append([f"`{f['fault']}`", t["process"], f["monitor"], f["detected"], f["timing"], f["persistence"], "yes" if f["handled"] else "NO"])

T["guarantees"] = (["Failure", "Cause", "Claims", "Steps", "Holds"], [
    [g["type"], g["cause"] or "any", ", ".join(g["claims"]), str(len(g["steps"])), "yes" if all(c["ok"] for c in g["checks"].values()) else "NO"] for g in ldl["guarantees"]])

T["empirical"] = (["Run", "Failure", "Handler", "Repair", "As prescribed", "Claim held"], [
    [e["run"].replace("_", " "), e["failure"], e["handler"], ", ".join(e["repair"]) or "–", "yes" if e["as_prescribed"] else "NO", "yes" if e["held"] else "NO"]
    for e in ldl["empirical"]])

T["meta"] = (["Rule", "When", "Treatment", "Because"], [
    [f"`{r['name']}`", "; ".join(r["when"]), r["treat"], r["because"]] for r in ldl["meta"]["rules"]])

ep0 = ldl["epistemic"][0]
T["treat"] = (["Shortfall of the belief", "Treatment", "Rule"], [[k, v["treat"], f"`{v['rule']}`"] for k, v in ep0["treatments"].items()])

T["kpis"] = (["KPI", "Of", "Aggregate", "Target", "Direction"], [
    [k["name"], k["of"], k["aggregate"], f"{k['op']} {k['target']:g}{(' ' + k['unit']) if k['unit'] else ''}", k["direction"]] for k in ldl["quality"]["kpis"]])
T["kpiruns"] = (["Run", "End", "Safety", "Reliability", "Auditability", "Max excursion (s)", "Cost"], [
    [r["run"].replace("_", " "), r["end"], str(r["safety"]), f"{r['reliability']:.3f}", f"{r['auditability']:.2f}", f"{r['excursion-time']:.1f}", f"{r['cost']:.2f}"]
    for r in QR])

T["ldlneg"] = (["Negative control (mutation)", "Caught by"], [[k, short("; ".join(v["by"]), 120)] for k, v in ldl["negative_controls"].items()])

T["culture_steps"] = (["Step", "Type", "Physical effect", "Knowledge effect"], [
    [s["var"], s["type"], "; ".join(f"`{p['cond']}`" for p in s["physical"]) or "–", "; ".join(f"`{p['cond']}`" for p in s["knowledge"]) or "–"]
    for s in cp["plan"]["steps"]])

T["links"] = (["From", "To", "Kind", "Condition"], [[l["frm"], l["to"], l["kind"], f"`{l['cond']}`"] for l in cp["derived"]["links"]])

T["knowledge"] = (["Quantity", "Value"], [
    ["observed radius A01 / A02 / A05 (µm)", " / ".join(f"{K['observed_radius_um'][k]:.1f}" for k in ("cr", "cc", "ck"))],
    ["measurement noise σ (µm)", f"{K['sigma_um']:.2f}"],
    ["observed rescue effect (µm)", f"{K['effect_um']:.2f}"],
    ["predicted effect M1 / M2 / M3 (µm)", " / ".join(f"{v['effect_um']:.1f} ± {v['effect_sd_um']:.1f}" for v in K["predicted"].values())],
    ["posterior M1 / M2 / M3", " / ".join(f"{v:.3f}" for v in K["posterior"].values())],
    ["entropy before / after (bit)", f"{K['entropy_before_bit']:.3f} / {K['entropy_after_bit']:.3f}"],
    ["information gained (bit)", f"{K['information_gain_bit']:.3f}"],
    ["expected gain of the design / required (bit)", f"{K['expected_gain_bit']:.4f} / {K['required_bit']}"],
])

T["instantiation"] = (["Abstract entity", "Role", "Particular in Cell 01"], [[f"`{i['abstract']}`", i.get("role") or i.get("kind", ""), i["particular"]] for i in grd["instantiation"]])

T["feas"] = (["Session", "Culture time", "Device", "Transport legs", "Checks", "All pass"], [
    [s["session"], f"{s['t_h']} h", s["device"].upper(), "; ".join(f"{r.upper()} {a.upper()}→{b.upper()}" for r, a, b in s["legs"]), str(len(s["checks"])),
     "yes" if all(c["ok"] for c in s["checks"]) else "NO"] for s in cp["feasibility"]["sessions"]])

T["z3"] = (["Theorem", "Holds", "Detail"], [
    [k, "yes" if v["holds"] else "NO", short(", ".join(f"{a}={json.dumps(b) if not isinstance(b, (int, float, str)) else b}" for a, b in v.items() if a not in ("holds", "violations", "doses", "images", "times", "wells")), 70) or "–"]
    for k, v in zp["theorems"].items()])

sel = plan["selected"]
T["design"] = (["Item", "Value"], [
    ["question", "which recovery model (M1 graded, M2 threshold, M3 protective) explains the rescue efficacy after a delay"],
    ["candidates evaluated", f"{N['candidates']} (dose × delay × replicates); {N['feasible']} meet the 0.5-bit requirement"],
    ["EIG estimator", f"nested Monte Carlo, {cands['samples']} samples, seed {cands['seed']}, uniform prior over 3 models (max {cands['max_bits']} bit)"],
    ["selected design", f"`{sel['id']}`: challenge {sel['dose_au']} au, rescue {sel['rescue_au']} au after {sel['delay_h']} h, {sel['reps']} replicate"],
    ["expected information gain", f"{sel['eig_bits']} bit ≥ {plan['requirement_bits']} bit"],
    ["wells", ", ".join(f"{k} {v[0]}" for k, v in plan["wells"].items())],
    ["cost (least, then max EIG)", f"{plan['cost']['value']} {plan['cost']['unit']}"],
    ["clingo", f"{plan['solver']['atoms']} atoms, {plan['solver']['rules']} rules, optimal"],
])

T["scen_cat"] = (["Scenario", "Fault or change injected", "Outcome"], [
    [n.replace("_", " "), runs[n].get("about", ""), short((runs[n]["end"] + (": " + runs[n]["error"] if runs[n].get("error") else "")), 140)] for n in BP.SYMB + BP.ISAAC])

cqres = collections.defaultdict(list)
for r in rep["cq"]["results"]:
    cqres[r["id"]].append(r)
T["cqfam"] = (["Family", "Checks", "Correct"], [[f, str(v[0]), str(v[1])] for f, v in rep["cq"]["by_family"].items()])
T["cqlist"] = (["CQ", "Family", "Question", "Scenarios checked"], [
    [x["id"], x["family"], x["question"], ", ".join(r["scenario"].replace("_", " ") for r in cqres.get(x["id"], []))] for x in CQS])

T["audit_cert"] = (["Trail", "Entries", "Evidence", "Chain", "Tamper caught", "Re-executed", "End", "Disposition"], [
    [t["scenario"].replace("_", " "), str(t["n"]), str(t.get("evidence", "")), "intact" if t["chain_ok"] else "BROKEN", "yes" if t["tamper_detected"] else "NO",
     {True: "identical", False: "DIFFERS", None: "not re-run"}[t["reexecuted_identical"]], t["end"], short(t.get("disposition", ""), 44)] for t in aud["trails"]])

T["giskard"] = (["Parameter", "Value", "Meaning"], [
    ["control frequency", f"{gm['qp']['target_frequency']} Hz (dt {gm['qp']['control_dt']} s)", "QP-based MPC rate"],
    ["prediction horizon", str(gm["qp"]["prediction_horizon"]), f"steps; highest derivative {gm['qp']['max_derivative']}; solver {gm['qp']['solver']}"],
    ["weights", ", ".join(f"{k} {v}" for k, v in gm["weights"].items()), "level and speed dominate; goal tracking is soft"],
    ["plate tilt", f"≤ {gm['bounds']['max_tilt_deg']}°", "kept level while held (cancel if violated)"],
    ["transit speed", f"≤ {gm['bounds']['transit_v']} m/s, {gm['bounds']['transit_w']} rad/s", "Cartesian limits while carrying"],
    ["pose tolerance", f"{gm['bounds']['pose_tol'] * 1000:.1f} mm, {gm['bounds']['ori_tol_deg']}°", "end monitor at grasp / release (A3)"],
    ["lock gap", f"{gm['bounds']['lock_gap'] * 1000:.0f} mm", "nest capture before release"],
    ["timeout", "1.2 × estimate", "the ±20 % duration bound of z3 theorem V3"],
])
T["legs"] = (["Robot", "Leg", "Motions", "Sequence"], [
    [d["robot"].upper(), f"{d['src'].upper()} → {d['dst'].upper()}", str(len(next(l["motions"] for l in gm["legs"] if l["robot"] == d["robot"] and l["src"] == d["src"] and l["dst"] == d["dst"]))),
     " → ".join(m["type"] for m in next(l["motions"] for l in gm["legs"] if l["robot"] == d["robot"] and l["src"] == d["src"] and l["dst"] == d["dst"]))]
    for d in gm["distinct"]])

O2 = rp["obligations"]["O2 abstraction: motion-level effects entail the culture plan"]["obligations"]
T["o2"] = (["O2 obligation (culture-level effect entailed by step-level events)", "Proved"], [[k, "yes" if v else "NO"] for k, v in O2.items()])
T["env"] = (["Tool", "Version"], [[k, str(v)] for k, v in man["environment"].items()])
T["inputs"] = (["Input group", "Files", "Digest (first 12)"], [[k, ", ".join(os.path.basename(p) for p in v), ", ".join(h[:12] for h in v.values())] for k, v in man["inputs"].items()])

T["findings"] = (["#", "Finding", "Change"], [
    ["F1", "The knowledge base was incomplete: plate seats came from a hard-coded name list; H4, L09, L21 had no seat facts, so a quarantine could not be grounded.", "Seats from the ABox type `PlateSeatPose`, shuttles from part types; plans unchanged."],
    ["F2", "Kernel and planner disagreed at s1: the kernel believed the tool still coupled 48 h later.", "Freshness: observations of shared cell state go stale at a session boundary."],
    ["F3", "The understanding gate caught incomplete category cards written by the assistant itself.", "Cards completed; an undeclared slot blocks, a slot declared empty does not."],
    ["F4", "A failing barcode read wrote no audit entry; the evidence for the escalation was lost.", "Failing leaves log what they observed."],
    ["F5", "The refusal for an unbound reagent was blamed on the time window.", "Projection is its own constraint (`projection_succeeds`)."],
    ["F6", "Missing capabilities failed only after the challenge was dosed, wasting the culture.", "The whole experiment is projected at acceptance."],
    ["F7", "An incomplete card moved the plate before the gate refused the dose.", "The gate is knowledge-only and also runs during projection."],
    ["F8", "A predicted window violation was reported as \"not groundable\".", "In projection, policies predict instead of abort."],
    ["F9", "The lint found device names in plan code (concentration, tolerance).", "Concentration is a reagent property; tolerance comes from the bound device."],
    ["F10", "A failure after leaving the incubator stranded the plate at the device.", "Unwind-protect at session level returns the plate first."],
    ["F11", "A planning error in both derivations: QC calibration placed after the plate occupied the imager stage.", "QC is a preparation step; z3 precondition \"imager free\"; the old plan is refuted at step 24."],
    ["F12", "Projection copied the backend's ground truth.", "Projection starts from the assistant's belief."],
    ["F13", "The twin's devices act at contract granularity (e.g. `dose_well`).", "A process-module layer binds groups of leaves to one skill; each leaf says what realised it."],
    ["F14", "HermiT found 6 unsatisfiable categories: `parent` conflated specialisation, partonomy and realisation.", "Cards separate `parent` (specialisation) from `parts` (refinement)."],
    ["F15", "The trail export needed cards for `incubate` and `contain`.", "Cards added; all 222 nominal designators classified."],
    ["F16", "Upstream reuse: RS `ValidityConstraint` is the validity column; AICOR's commitment record is episode-level.", "Unit `CommitmentAuditEntry`; divergence registered (D-LAT-11)."],
    ["F17", "Isaac `calibration_lapsed` did not end as specified: after the reload the plate sat about 93 µm off; A02 failed the focus floor twice; A05 was never imaged.", "Not fixed. The focus repair (refocus) cannot change the outcome; a re-seat is prescribed and its absence is caught by the language (N9)."],
])

T["files"] = (["Module", "Lines", "Role"], [[f"`rsa/{f}`", str(SRC_LINES[f]), r] for f, r in [
    ("kb.py", "knowledge base: planner facts, component records, registries; queries return grounds"),
    ("core.py", "designators, plan nodes, belief with provenance and freshness, executor"),
    ("library.py", "generalized plans of the categories; no device names (linted)"),
    ("checks.py", "constraint checks, policies (window, airspace), understanding frame"),
    ("backend.py", "symbolic Cell 01 world with fault injection"),
    ("isaac.py", "Isaac Sim backend: leaves bound to the twin's controllers"),
    ("audit.py", "hash-chained commitment records and verifier"),
    ("critic.py", "two-column verdict from the trail alone"),
    ("cq.py", "competency questions answered from trail, knowledge and dry runs"),
    ("ldl.py", "LDL parser, checker: order, threats, instruments, handlers, trust, KPIs"),
    ("ldl_trust.py", "process models, guarantees, epistemic meta model"),
    ("ldl_to_cram.py", "CRAM/RPL controller generation"),
    ("culture_plan.py", "culture plan: order, surrogate execution, mapping, feasibility"),
    ("grounding.py", "instantiation, trips, waits, computations, reactions"),
    ("motion_frames.py", "goal frames from the scene; inverse kinematics reachability"),
    ("giskard_motions.py", "Giskard motion statecharts"),
    ("refinement_proof.py", "refinement proof O1–O7 and negative controls"),
    ("independence.py", "culture plan in 13 lab variants"),
    ("reproduce.py", "content-addressed manifest; verify by re-run"),
    ("protocol.py", "experimentation plan and audit certificate"),
] if f in SRC_LINES])

T["glossary"] = (["Term", "Meaning in this report"], [
    ["action designator", "a symbolic description of an action, resolved against knowledge at run time (CRAM)"],
    ["entity designator", "a partial description of a lab entity: (determiner sort slot*), answered by a knowledge query"],
    ["culture plan", "the experiment over the cultures only: actions with physical and knowledge effects"],
    ["lab plan", "LDL action designators with contracts, instruments, handlers and KPIs"],
    ["step plan", "the grounded robot and device steps, derived by clingo and expanded by the kernel"],
    ["session / trip", "one excursion of the plate from the incubator, a realization concept"],
    ["realization / validity", "the two columns of the verdict: ran correctly and safely / result interpretable"],
    ["NR3", "realised but not valid; nothing may be committed"],
    ["EIG", "expected information gain of a design over the competing models (bits)"],
    ["grounds", "the fact atoms a resolution or answer used"],
    ["ILLUSTRATIVE", "a twin value or mapping, labelled; not a lab or biomedical fact (D016)"],
    ["Cell 01", "the two-arm robotic cell of the laboratory twin (Isaac Sim, OpenUSD)"],
])


# ------------------------------------------------------------------------------------------------------------- listings
def lst(path, start, end=None, n=None):
    return BP.listing_block(path, start, n=n, end_pat=end)


LDLDIR = os.path.join(REG, "lab")
DERIV = BP.DERIV
LST = dict(BP.LST)
LST["contract"] = lst(os.path.join(LDLDIR, "contracts.ldl"), r"^\(contract intervening", r"^\(contract incubating")
LST["process"] = lst(os.path.join(LDLDIR, "processes.ldl"), r"^\(process-model substance-transfer", r"^\(process-model imaging")
LST["epistemic"] = lst(os.path.join(LDLDIR, "epistemic.ldl"), r"^\(meta-model epistemic", r"\(rule reported-by")
LST["cplan"] = lst(os.path.join(LDLDIR, "culture_plan.ldl"), r"^\(the experiment \?E", r"what is done to the cultures")
LST["asp"] = lst(os.path.join(DERIV, "experiment_to_motion.lp"), r"E2M1 selection", r"E2M5 allocation")
LST["handlers"] = lst(os.path.join(LDLDIR, "challenge_rescue.ldl"), r"\(handles", n=22)
LST["motions"] = lst(os.path.join(OUT, "challenge_rescue_motions.lisp"), r"\(a motion", n=18) if "(a motion" in open(os.path.join(OUT, "challenge_rescue_motions.lisp")).read() else \
    "\n".join(open(os.path.join(OUT, "challenge_rescue_motions.lisp")).read().splitlines()[:18])
cq_ex = next(r for r in rep["cq"]["results"] if r["id"] == "CQ-03" and r["scenario"] == "nominal")
LST["cq"] = json.dumps({k: cq_ex[k] for k in ("id", "scenario", "question", "answer", "grounds")}, indent=1, ensure_ascii=False)[:2400]
LST_LANG = dict(BP.LST_LANG, contract="lisp", process="lisp", epistemic="lisp", cplan="lisp", asp="prolog", handlers="lisp", motions="lisp", cq="json")


# ------------------------------------------------------------------------------------------------------------- text
def S(title, label, *blocks):
    return ("section", title, label, list(blocks))


def SS(title, label=None):
    return ("sub", title, label)


nom = runs["nominal"]
isaac_cal = runs["isaac_calibration_lapsed"]
nsym, nisaac = len(BP.SYMB), len(BP.ISAAC)
ok_sym = sum(1 for n in BP.SYMB if runs[n]["expectation_ok"])
ok_isaac = sum(1 for n in BP.ISAAC if runs[n]["expectation_ok"])
nneg = len(ldl["negative_controls"])
ncats = len(CATS)
ncons = sum(1 for v in CONS.values() if v.get("applies_to"))
nvcrit = sum(1 for k in CONS if re.match(r"V\d", k))

SUMMARY = (
    "This report documents the robot science assistant (RSA): a kernel that lets a robotic laboratory carry out an experiment stated "
    "at the level of the cultures, explain what it does, prove that its robot motions realize the stated experiment, and leave a record "
    "that anyone can verify and re-execute. The assistant is developed on Cell 01, a two-arm robotic cell of a physics-based laboratory "
    "twin, with one example: a challenge–rescue organoid experiment derived for an information gain of 0.5 bit. The report describes "
    "the concepts, the languages, the knowledge, the execution system, the verification and the reproducibility machinery, and reports "
    "every result with its source file. All biological quantities come from the twin's surrogate culture model and are ILLUSTRATIVE.")

KEY = (["Result", "Value", "Section"], [
    ["Culture plan → lab plan → steps → motions", f"{N['culture_actions']} → {N['lab_steps']} → {N['steps']} → {N['motions']}", "§sec:culture§, §sec:motion§"],
    ["Expected / realized information gain", f"{sel['eig_bits']} / {K['information_gain_bit']:.3f} bit (required 0.5)", "§sec:design§, §sec:culture§"],
    ["Kernel run vs planner (nominal)", f"{nom['n_leaves']} leaves, identical step for step; {nom['n_entries']} audit entries", "§sec:exec§"],
    ["Symbolic scenarios ending as specified", f"{ok_sym}/{nsym}", "§sec:exec§"],
    ["Isaac Sim runs ending as specified", f"{ok_isaac}/{nisaac} (calibration lapsed fails: F17)", "§sec:isaac§"],
    ["Competency-question checks", f"{N['cq_ok']}/{N['cq']} correct, all grounded", "§sec:audit§"],
    ["LDL negative controls caught", f"{sum(1 for v in ldl['negative_controls'].values() if v['caught'])}/{nneg}", "§sec:ldl§"],
    ["Handler guarantees verified", f"{sum(1 for g in ldl['guarantees'] if all(c['ok'] for c in g['checks'].values()))}/{len(ldl['guarantees'])}", "§sec:trust§"],
    ["Refinement proof", "QED relative to A1–A6; O1–O7 hold", "§sec:proof§"],
    ["Lab variants with identical culture plan", f"{N['labs']}/{N['labs']}", "§sec:indep§"],
    ["Reproduction of the derivation", f"{N['identical']}/{N['outputs']} outputs identical; manifest `{mh[:16]}`", "§sec:repro§"],
    ["Audit trails", f"{N['trails']} intact, {N['trails']} tamper tests caught, {N['reexec']}/{N['reexec_n']} re-executions identical", "§sec:repro§"],
])
T["key"] = KEY

DOC = [
    S("Executive summary", "sec:summary",
      ("p", SUMMARY),
      ("p", "**What the assistant is.** The RSA is a plan-based controller for a robotic laboratory, built in the tradition of CRAM and "
            "structured reactive controllers [@mcdermott1991,beetz2001,beetz2010]. An experiment is written once as a plan over the cultures. The "
            "assistant derives everything below it: a design chosen by expected information gain, a partially ordered plan of laboratory "
            "action designators with contracts and failure handlers, a CRAM/RPL controller, the robot and device steps, and constraint-based "
            "motion specifications for Giskard [@stelter2022]. While it executes, it keeps beliefs with provenance and freshness, checks "
            "constraints before and during every action, repairs or escalates failures, and writes a hash-chained audit entry for every "
            "lifecycle transition of every designator. After the run, a critic judges realization and validity separately, and the assistant "
            "answers competency questions about what it did and why, with the grounds of each answer."),
      ("p", "**What was shown.** The table below collects the main results. Each row is computed from the outputs of the pipeline at the "
            f"manifest `{mh[:16]}`; the section given in the last column explains how."),
      ("table", "key", "Main results of the RSA on the challenge–rescue example."),
      ("p", "**What was not shown.** The assistant has not run in a wet laboratory. The culture is a surrogate model of the twin. Reproduction "
            "was checked on one machine. The Isaac Sim runs are recorded, not re-executed, and one of them does not end as specified; the "
            "cause (plate seating on the imager stage) is diagnosed but not repaired. The refinement proof is relative to six assumptions, two "
            "of which cover faults that the cell can detect only partly. The coraplex framework, the intended execution platform, was not yet installed; "
            "the kernel is shaped so that the port is a mapping, not a rewrite (§sec:roadmap§)."),
      ("p", "**How to read the report.** §sec:background§ sets the scope and §sec:arch§ the architecture. §sec:kb§–§sec:trust§ describe the "
            "knowledge, the design, the lab designator language and the process models. §sec:culture§–§sec:motion§ follow the experiment "
            "from the culture plan to robot motions and executions. §sec:proof§–§sec:repro§ cover proof, independence and reproducibility. "
            "§sec:findings§–§sec:roadmap§ list what the iterations taught, the limits and the next steps.")),

    S("Background, scope and method", "sec:background",
      ("p", "Robotic laboratories can run experiments around the clock and record everything they do [@king2009,williams2015,burger2020,abolhasani2023]. "
            "They are usually programmed at the level of devices: a liquid-handler method, a robot program, a scheduler script. Such a program "
            "fixes *how* an experiment is executed in one laboratory but does not state *what* it does to the material, so it cannot be checked "
            "against the scientific intent, and it must be rewritten when the laboratory changes. Reproducibility suffers in both directions "
            "[@baker2016]: the intent is not recorded in a checkable form, and the record of what happened is not tied to the intent."),
      ("p", "The RSA addresses this with three commitments. First, the experiment is stated at the level of the cultures, independent of the "
            "laboratory. Second, every level below is derived and checked against the level above, so that the robot's motions provably "
            "realize the stated experiment, or fail safely. Third, the derivation and the execution are both recorded so that they can be "
            "verified and reproduced by someone else, in the spirit of FAIR data and data-integrity guidance [@wilkinson2016,fda2018]."),
      SS("A rational reconstruction", "sec:recon"),
      ("p", "The kernel is a *rational reconstruction* of earlier try-outs in the ResearchSpace material: many good ideas in mutually "
            "inconsistent forms (designator schemas, taxonomies, audit formats, verdict vocabularies). The kernel does not try to unify "
            "everything. It takes one example and keeps only what that example needs. For each concept it records where it comes from and "
            "what was changed (§tab:concepts§). It then tests whether the result *flies*: does the example run end to end, leave an audit "
            "trail, and answer competency questions correctly? Each iteration ends with findings that change the kernel or the knowledge; "
            "the findings log is in §sec:findings§."),
      SS("Cell 01 and the laboratory twin", "sec:cell"),
      ("p", "Cell 01 is a robotic cell of a laboratory twin built on Isaac Sim with an OpenUSD scene and a semantic digital twin (SDT) in OWL. "
            "Two robots serve it: R01, a Franka FR3 that moves plates between the incubator (L10) and a handover nest, and R02, a UR5e on a "
            "rail that carries plates between the handover nest, the liquid handler (L12) in its enclosure, and the bright-field imager (L17), "
            "and couples a plate tool (T01) from an automatic tool changer. Further stations are a quarantine nest (H4), a plate hotel (L09) "
            "and a QC reference station (L21). The devices act themselves: L10 presents a plate on a shuttle, L12 doses a well, L17 loads and "
            "images. Cell 01 changes are made only through an overlay composer, so the as-built scene is never edited."),
      ("fig", "cell", "Cell 01 in the laboratory twin (Isaac Sim, path-traced): two arms, the incubator, the liquid handler in its enclosure, "
                      "the bright-field imager, the tool rack and the handover nest."),
      SS("The example experiment", "sec:example"),
      ("p", "The example is a challenge–rescue experiment on organoid cultures. Three competing recovery models (M1 graded, M2 threshold, "
            "M3 protective) predict different effects of a rescue given after a delay. The experiment challenges two cultures, rescues one "
            "of them after the delay, keeps a third culture untreated as control, images all three, and updates the belief over the models. "
            f"The design is chosen to reach an expected information gain of at least {plan['requirement_bits']} bit at least cost "
            f"(§sec:design§). The selected design is `{sel['id']}`: challenge {sel['dose_au']} au at 0 h into the rescued and the comparator "
            f"culture, rescue {sel['rescue_au']} au at {sel['delay_h']} h, images at 72 h. It runs in three sessions on plate P17, wells A01 "
            "(rescued), A02 (comparator) and A05 (control)."),
      ("p", "**ILLUSTRATIVE values (D016).** The culture is the twin's surrogate model; doses are in arbitrary units (au); the 600 s window "
            "outside the incubator, the 5 % dose tolerance, KPI targets and the regulation mapping are twin values. They are labelled where they "
            "appear and are not asserted as laboratory or biomedical facts."),
      SS("Method: iterate on one example", "sec:method"),
      ("ul", ["**Iteration 1** built the kernel and ran the example on a symbolic backend with fault injection: 12 scenarios, audit, critic, "
              "27 competency questions (52 checks).",
              "**Iteration 2** added the Isaac Sim backend (same plan code) and expressed the kernel's categories as an OWL module checked by "
              "HermiT and Konclude.",
              "**Iteration 3a** introduced the lab designator language (LDL) in three versions (v0.1–v0.3), each after a round of design "
              "decisions, then the culture-level plan, its grounding in Cell 01, the Giskard motion level, the independence check, the "
              "refinement proof, and the reproducibility machinery.",
              "**Iteration 3 (pending)** ports the kernel to coraplex."])),

    S("Architecture", "sec:arch",
      ("p", "The assistant is organised in levels (§tab:levels§). Each level states something different, in its own language, and is "
            "derived from the level above. The culture plan is written; everything else is generated and checked."),
      ("table", "levels", "The levels of the RSA, from the culture plan to robot motions."),
      ("p", "Inside the kernel, seven components cooperate (§fig:arch§). The knowledge base answers resolution queries with their grounds. The "
            "plan library builds sub-plans of each action category at perform time. The executive drives designators through their "
            "lifecycle, projects plans before anything moves, applies the understanding gate and the policies, and handles failures. A "
            "backend executes leaves: a symbolic world with fault injection, or the Isaac Sim twin. Every transition goes into the audit "
            "trail, from which the critic and the competency-question engine work."),
      ("fig", "arch", "Kernel components and their data flow. The plan code never names a device; devices enter only through resolution "
                      "against the knowledge base."),
      SS("Twelve kernel concepts", "sec:concepts"),
      ("p", "§tab:concepts§ lists the twelve concepts the example needs, each with its kernel definition and origin. Three of them are new "
            "relative to the sources. The *device-command designator* is a fourth leaf kind beside motions, because Cell 01's devices are "
            "co-actors. The *event designator* is the audit-side record of what happened. And *freshness* is part of belief, not only provenance "
            "(finding F2)."),
      ("table", "concepts", "The twelve kernel concepts, their definitions and where they come from."),
      SS("Code map", "sec:files"),
      ("p", f"The kernel is a Python package (`rsa/`) of about {sum(SRC_LINES.values()):,} lines. Its API is shaped like coraplex: designators "
            "are dataclasses, action designators build their plans, and plans are trees of sequential, try-in-order and monitor nodes with "
            "action, motion and command leaves."),
      ("table", "files", "Modules of the RSA kernel and pipeline.")),

    S("Knowledge, designators and constraints", "sec:kb",
      ("p", "**One source of knowledge.** The planner, the resolver, the monitors and the competency questions read the same facts. They are "
            "generated from the OKF ontology ABoxes of the lab (SDT, safety, experiments) into ASP facts (`build/e2m/facts_<tag>.lp`), "
            "complemented by the Cell 01 component records (capabilities, contracts, monitors, failure modes; read-only) and the kernel "
            "registries (categories, constraints, norms, devices, scenarios, competency questions). Two derivations from the same facts, "
            "the clingo plan and the kernel's expansion, must agree; they do, step for step (§sec:exec§)."),
      ("p", "**Resolution with grounds.** A resolution query returns a value, the fact atoms it used, and the alternatives it rejected with "
            "the reason. For the dosing step, the instrument resolves to L12's plate nest with grounds `has_function(l12,dispensing)`, "
            "`dose_well` among L12's capabilities and `seat(l12, …)`; five other devices are rejected, each with the missing function or "
            "capability. These records go into the audit trail, so the assistant can later answer why it chose a device."),
      ("p", "**Designator lifecycle.** Each designator moves through the lifecycle of §fig:lifecycle§. Plan-node status (created, running, "
            "succeeded, failed), designator lifecycle and episode verdict are three separate vocabularies (decision K5); conflating them was "
            "a source of inconsistency in the earlier material."),
      ("fig", "lifecycle", "Designator lifecycle. Every transition is one audit entry; repairs are recorded on the node that repaired."),
      SS("Action categories", "sec:categories"),
      ("p", f"The category registry has {ncats} cards on five levels (§tab:categories§). A card belongs to the category, not to the instance: "
            "level, specialisation parent, refinement parts, effect class (the AICOR partition: object displacement, substance manipulation, "
            "perception, connecting, configuration change, regulation, maintenance), facet (transport, operation, transformation), roles, "
            "required capability, pre- and post-conditions as constraint ids, sub-plan, monitors, recovery and evidence obligations. The "
            "instance only binds roles. Expressed as an OWL module, the cards first produced six unsatisfiable classes, because `parent` "
            "mixed specialisation, partonomy and realisation (F14); separating `parent` from `parts` made the module consistent."),
      ("table", "categories", "Action categories by level (kernel registry)."),
      SS("Constraints and norms", "sec:constraints"),
      ("p", f"Constraints are registry entries with a column. {ncons} runtime constraints guard the transitions of the categories they apply to; "
            f"{nvcrit} validity checks (V1–V7) are evaluated by the critic over the whole episode (§tab:constraints§). Every constraint names its "
            "source: an ontology axiom, a Cell 01 monitor, an e2m axiom or a kernel finding."),
      ("table", "constraints", "Constraint registry: runtime constraints and the critic's validity checks."),
      ("p", "Regulation clauses are cited by identifier only and mapped to what realises them in the kernel: an audit field, a runtime constraint, "
            "or a documentary obligation the kernel cannot discharge (§tab:norms§). The mapping is ILLUSTRATIVE. Its point is that the "
            "assistant can say which clauses a run covers and which it does not (competency question CQ-19)."),
      ("table", "norms", "Regulation clauses and what realises them (ILLUSTRATIVE mapping)."),
      SS("Capabilities and measurement bindings", "sec:capability"),
      ("p", "A capability is a verb from a component record, qualified by state (calibrated, tool coupled, tips present, automated) and by a "
            "measurement binding on a lattice: no match ⊂ capability match ⊂ provisional ⊂ validated. The distinction matters for validity. "
            "An imager that *can* image a well but whose binding for the readout is not validated produces an image that does not count as "
            "evidence. This is how the `imager_swapped` scenario ends realised but not valid (NR3), while `imager_incapable` is refused before "
            "anything moves.")),

    S("Experimental design", "sec:design",
      ("p", "The design answers: which dose, delay and number of replicates separate the three recovery models best, at least cost? The "
            "assistant uses Bayesian experimental design [@lindley1956,chaloner1995]: the expected information gain (EIG) of a design is the "
            "expected reduction of entropy of the belief over the models, estimated by nested Monte Carlo over the twin's calibrated surrogate. "
            "The planner then selects, among candidates meeting the required gain, the least-cost one that can be executed safely in Cell 01."),
      ("table", "design", "The design problem and its solution."),
      ("fig", "design", "Expected information gain of the candidate designs by delay and dose. The selected design is circled."),
      SS("From design to steps in ASP", "sec:asp"),
      ("p", "The derivation from the selected design to the grounded steps is an answer-set program [@gebser2019] that executes the "
            "experiment-to-motion axioms E2M1–E2M8. The stable model *is* the plan: the selected experiment, the wells, the sessions, the "
            "trips, the routes and the ordered robot and device steps of every trip. Facts such as seats, shuttles, tools and durations come "
            "from the ontology; durations are apportioned from the twin's run traces. The excerpt in §lst:asp§ shows design selection, arm "
            "assignment with symmetry breaking, and the material of each session."),
      ("lst", "asp", "Excerpt of the experiment-to-motion axioms in ASP (selection, arms, sessions)."),
      ("table", "sessions", "The three sessions of the derived plan, with planned and Isaac Sim durations."),
      SS("SMT validation of the plan", "sec:z3"),
      ("p", "An independent validator encodes the plan in z3 [@demoura2008] and proves the theorems V1–V5: executability and preservation of "
            "preconditions over all steps, safety rules, the time window with a ±20 % duration tolerance, realization of the design (doses, "
            "images, session times), the arms with a control, the information gain, and least cost over all candidates meeting the "
            f"requirement. {len(zp['negative_controls'])} negative controls (mutated plans) are refuted. Finding F11 came from this layer: "
            "a QC calibration placed after the plate occupied the imager stage was physically infeasible in both derivations; the validator "
            "now refutes the old plan at step 24."),
      ("table", "z3", "SMT theorems over the derived plan (`validate_plan_z3.py`).")),

    S("The lab designator language", "sec:ldl",
      ("p", "The lab designator language (LDL) states *what* a laboratory action must bring about, never *how*. Every term is an entity "
            "description `(determiner sort slot*)` over lab entities only: plates, wells, substances, designs, arms, environments, "
            "excursions, transfers, measurements, records, instruments, persons and requests. A condition is an entity description too: once "
            "its variables are bound it is a ground query with a truth value. No robot, gripper, tool, pose, frame, trajectory or device "
            "identity can be written; a lint makes the boundary checkable."),
      ("table", "ldl_clauses", "LDL clauses and their operational obligations."),
      ("p", "**Semantics.** An execution trace satisfies an action iff its `requires` hold at the start, nothing its `prevents` describes "
            "occurs during the action, its `maintains` hold throughout, and its `achieves` hold at the end. `prevents` and `maintains` of an "
            "enclosing action are inherited by every sub-action; `achieves` is not. A condition φ marked `known` holds iff φ is believed with observed, fresh "
            "provenance; a plain `requires` may be established by the executive (insert a calibration), a `known` one may only be verified "
            "(identity cannot be established, only read). **Admissibility** sharpens the understanding gate: an action is accepted only if "
            "every term resolves, every `prevents` item has a monitor that can detect it, every `maintains` item a monitor or regulator, every "
            "`achieves` item an evidence path, and every `requires` item can be verified or established. A `prevents` clause that nothing can "
            "observe is not a constraint, so the action is refused."),
      ("lst", "contract", "The contract of the action type `intervening` (`registry/lab/contracts.ldl`)."),
      SS("Instruments as roles", "sec:instruments"),
      ("p", "Instruments appear only attributively, but they fill a role: a slot the plate is inserted into and a process that, once started, "
            "performs the action. Realization is machine tending: insert, start, await, remove. The checker resolves every role against the "
            "knowledge (§tab:instruments§): an automated device with a plate seat, with the function and capability verb of the process."),
      ("table", "instruments", "Instrument roles of the lab plan and how they resolve in Cell 01."),
      SS("Order, goals and threats", "sec:order"),
      ("p", f"The order of the lab plan is derived, not written. From goals and `achieves` the checker builds {len(ldl['links'])} causal links; "
            f"{len(ldl['threats'])} threats on culture time are all resolved by promotion, leaving {len(ldl['hasse'])} Hasse edges and "
            f"{ldl['linear_extensions']} linear extensions, in the manner of least-commitment planning [@weld1994]. Every step goal is justified "
            "by the experiment's goal through the links. A `scope` bounds a non-terminating prevents-item by fluents: the cross-dosing "
            "prevents-item holds only while the portion drawn for the action is in the tip, which removed a spurious mutual exclusion between "
            "dosing A01 and A02 that v0.1 produced."),
      ("lst", "lab", "A lab action designator of the generated plan (the rescue dose)."),
      SS("Failures and handlers", "sec:handlers"),
      ("p", f"Each contract lists the failures it may signal. The experiment's control program handles them: `(on (a failure …) (do …) (then "
            f"retry | replan | escalate) (else …) (guarantees …))`. All {len(ldl['failures'])} signalled failures of the plan have a handler. "
            "§lst:handlers§ shows the handlers; §tab:handlers§ in the appendix lists them all."),
      ("lst", "handlers", "Handlers of the experiment's control program (excerpt of `challenge_rescue.ldl`)."),
      SS("Negative controls", "sec:ldlneg"),
      ("p", f"A checker that accepts everything proves nothing. Each of the {nneg} mutations in §tab:ldlneg§ breaks one property, and the "
            "checker must refuse it with the right reason."),
      ("table", "ldlneg", "Negative controls of the LDL checker; each mutation must be caught.")),

    S("Process models, trust, guarantees and quality", "sec:trust",
      ("p", "The trustworthiness of an experiment depends on what happens *inside* the devices. LDL v0.3 therefore models each laboratory "
            "process: its phases, the phase after which it cannot be undone, and its faults. Each fault states the failure it signals, the "
            "goal it corrupts, the monitor that detects it and with what coverage, whether a repeat meets the same cause (persistence), and "
            "which re-established condition removes it. The models are grounded in the Cell 01 component records: every fault must be one of "
            "the record's failure modes, every monitor one of its observations."),
      ("lst", "process", "Process model of substance transfer (L12), `registry/lab/processes.ldl`."),
      ("table", "models", "Process models and their grounding in the Cell 01 components."),
      SS("Trust per step", "sec:truststep"),
      ("p", f"Reasoning over the models gives the trust profile of each step (§fig:trust§, §tab:trust§). {N['faults_full']} of {N['faults']} "
            "fault occurrences are fully detected. Two fault kinds are only partly detected: well misregistration at L12, which occurs at the "
            "irreversible dispense, and plate misseating at L17, the lateral shift behind finding F17. They are the two trust gaps of the "
            "current cell and appear as assumption A2 of the refinement proof."),
      ("fig", "trust", "Trust profile of the lab plan: fault × step, by detection coverage, timing relative to the irreversible phase, and persistence."),
      ("table", "trust", "Faults of the process models: detection, timing, persistence and handling."),
      SS("Repair guarantees", "sec:guarantees"),
      ("p", "Every handler states what it guarantees, and the checker verifies the claim. *goal* needs the fault to be detected before the "
            "irreversible phase and either transient or removed by what the handler re-establishes. *safe-state* needs the final branch to "
            "escalate or abstain, the plate to be restorable, nothing committed and the evidence kept. *contained* needs a quarantining action "
            "with a containment goal. The checker rejects a focus retry that does not re-seat the plate (N9) and a goal claimed after the "
            "irreversible dispense (N11)."),
      ("table", "guarantees", "Handler guarantees and their verification."),
      ("p", "Against the recorded runs, every repair event kept its claim (§tab:empirical§). In the Isaac focus case the kernel did not "
            "repair as prescribed: it refocused instead of re-seating."),
      ("table", "empirical", "Repairs in the recorded runs against the handlers' claims."),
      SS("Epistemic meta model", "sec:epistemic"),
      ("p", "Beliefs carry a grade: source (observed > reported > inferred > assumed > predicted > unknown) × freshness × corroboration. A meta "
            "model, itself written in LDL, says how each shortfall is treated depending on the item, its use (consequential or routine) and the "
            "action context. A treatment is a plan with a cost: re-observe, verify before commit, contain and escalate, sense or abstain, "
            f"plan only. The {len(ldl['meta']['rules'])} rules give every requirement a treatment for every shortfall."),
      ("lst", "epistemic", "The first rules of the epistemic meta model (`registry/lab/epistemic.ldl`)."),
      ("table", "treat", "Treatments for the plate-identity requirement of a dose, by shortfall of the belief."),
      ("table", "meta", "All rules of the epistemic meta model."),
      SS("Quality: KPIs and preference", "sec:kpi"),
      ("p", "Hard limits stay in `prevents`; soft targets are KPIs, each an aggregate over an entity description, ranked lexicographically. "
            "Safety, reliability and auditability lead, then excursion time, cost, dose deviation and time to result. Targets and cost weights "
            "are ILLUSTRATIVE."),
      ("table", "kpis", "KPIs of the experiment (`quality` clause)."),
      ("fig", "kpi", "KPIs measured from the recorded trails: longest excursion outside the incubator and reliability; cost in the label."),
      ("table", "kpiruns", "KPIs per recorded run, in the order of the lexicographic ranking.")),

    S("The culture-level plan", "sec:culture",
      ("p", "The culture plan states the experiment over the cultures only. It names the question, the entities (three cultures by role, two "
            "substances, a belief over the three models), the goal, what is given, what must never happen (the control is never exposed; no "
            "contamination) and what must hold throughout (the cultures' environment). Its steps are what is done to the cultures and what "
            "becomes known: challenge, grow, rescue, observe, interpret and analyse. Each step has a physical and a knowledge effect."),
      ("lst", "cplan", "Head of the culture plan (`registry/lab/culture_plan.ldl`)."),
      ("lst", "culture", "A culture-level action: the rescue."),
      ("table", "culture_steps", "Steps of the culture plan with their physical and knowledge effects."),
      SS("Derived order", "sec:corder"),
      ("p", f"The order is derived from {N['culture_links']} causal links, 7 physical and 6 knowledge links (§tab:links§); §fig:poset§ shows the "
            "partial order. One link needs an establishable requirement: interpretation needs a known image scale. It first required "
            "\"a calibration of the pixel size\", which the independence check rejected because calibration is a device function (§sec:indep§)."),
      ("fig", "poset", "The culture plan as a partial order (Hasse layers). Colour shows the kind of step."),
      ("table", "links", "Causal links of the culture plan."),
      SS("Execution on the surrogate and what became known", "sec:knowledge"),
      ("p", "Run on Cell 01's surrogate, the rescued culture recovers partly and the comparator does not (§fig:culture§). The observed effect "
            f"of {K['effect_um']:.1f} µm lies between the predictions of M1 and of M2/M3, so the belief moves towards M1 but gains only "
            f"{K['information_gain_bit']:.3f} bit, against {K['required_bit']} bit required and {K['expected_gain_bit']:.4f} bit expected. The "
            "design meets the requirement only in expectation; the goal therefore says `expected-information-gain`. A priming design that "
            "separates M2 from M3 is on the roadmap."),
      ("fig", "culture", "Surrogate organoid radii of the three cultures over culture time (left) and the belief over the recovery models before "
                         "and after the experiment (right). ILLUSTRATIVE."),
      ("table", "knowledge", "What the experiment made known (surrogate, ILLUSTRATIVE)."),
      SS("Mapping to the laboratory", "sec:mapping"),
      ("p", "The cultures map to wells A01, A02 and A05 of plate P17; the eight physical culture actions map to lab action designators and, "
            "through their instrument roles, to L12, L10 and L17. The four computations (interpretation and analysis) map to the twin's image "
            "analysis and posterior computation. The lab order is exactly the projection of the culture order."),
      ("table", "refine", "Refinement of the culture actions to lab actions, processes and devices."),
      ("table", "instantiation", "Instantiation of the abstract entities in Cell 01."),
      ("p", "**Feasibility.** For each session the assistant checks every transport leg (both seats served by the robot, reach from the layout, "
            "seats typed in the SDT), the tool coupling, the machine tending of L10, L12 and L17, and the trip time against the window. "
            "All checks pass, with evidence from facts and from the Isaac run. They are conditional on two assumed device preconditions (L12 "
            "calibrated, L17 healthy), and inventory (tips, reagent stock) is not modelled."),
      ("table", "feas", "Feasibility checks per session.")),

    S("Execution", "sec:exec",
      ("p", "The executive turns one linear extension of the lab plan, grouped by culture time into sessions, into a plan tree. The generalized "
            "plan of each category builds its sub-plan at perform time, querying the knowledge base; the leaves are motions and device "
            "commands. Before anything moves, the whole experiment is projected from the assistant's belief (F6, F12): every designator must "
            "be groundable, the understanding gate must accept every card, and the window policies predict instead of abort (F8). At each "
            "session start, observations of shared cell state go stale and are re-established (F2). If a session fails after the plate left "
            "the incubator, an unwind-protect returns it before the failure propagates, unless it was quarantined (F10)."),
      ("p", f"The executive is also emitted as a CRAM/RPL structured reactive controller ({LISP_LINES} lines of Lisp): one `def-action-plan` "
            "per lab action type, with the contract's requires as checks, the scoped prevents as monitors, and the handlers as failure "
            "handling. §lst:cram§ shows the plan for `intervening`."),
      ("lst", "cram", "The generated CRAM/RPL plan for the lab action type `intervening`."),
      SS("Cross-check with the planner", "sec:crosscheck"),
      ("p", f"Expanding the nominal plan into designators reproduces the clingo plan's leaf steps term for term ({nom['n_leaves']} leaves, "
            "same primitive, agent and pose, in the same order), and the durations match the planner's exactly "
            f"({', '.join(str(c['duration_s']) for c in nom['crosscheck'])} s). Two independent derivations from the same facts agree. Since "
            "the symbolic backend takes durations from the planner's facts, this shows consistency, not independent physics; the Isaac runs "
            "supply the latter."),
      ("fig", "trail", "The nominal audit trail: entries by lifecycle transition and executed leaves by agent."),
      SS("Scenarios", "sec:scenarios"),
      ("p", f"Twelve symbolic scenarios exercise the kernel with the *same plan code*; only knowledge and world change (§tab:scen_cat§). "
            "Expectations, including the two-column verdict and the disposition, were written before the runs. They cover device exchange, "
            "step substitution by knowledge and by repair, workflow change, safety and identity, and knowledge gaps."),
      ("table", "scen_cat", "Scenario catalogue: what is injected and how each run ends."),
      ("table", "scenarios", "Outcome per scenario: end state, realization (R) and validity (V), repairs, trail size, and whether it ended as specified."),
      ("ul", ["**Device exchange.** `imager_swapped` executes unchanged and ends NR3: physically realised, invalid evidence, nothing committed. "
              "`imager_incapable` is refused before the first intervention, naming the missing capability.",
              "**Step substitution.** `uncalibrated_known` inserts a QC calibration as a preparation step. `calibration_lapsed` detects the lapse "
              "at imaging, sets the plate aside at a passive station, recalibrates and re-plans the measurement. `tip_lost` replaces the tip "
              "before aspiration.",
              "**Workflow change.** `control_dropped` is refused by `challenge_requires_controls` before anything moves.",
              "**Safety and identity.** `identity_swap` quarantines the wrong plate, escalates, and records that it does not know where P17 is. "
              "`tool_changer_slow` exceeds the window and returns the plate before reporting failure.",
              "**Knowledge gaps.** `rescue_unbound`, `contamination` and `card_incomplete` are refused before any motion."]),
      SS("Isaac Sim execution", "sec:isaac"),
      ("p", "The Isaac backend runs the same plan code, knowledge, audit, critic and competency questions; only leaf execution changes. The "
            "twin's skills are coarser than the leaves (F13): a robot pick is approach, insert, grasp and lift; L12's `dose_well` is tip pick, "
            "aspirate, dispense and tip eject. A group of leaves is executed at its first leaf, and the following leaves report the phases of "
            "that execution; every leaf entry records what realised it. Durations are physics time; culture waits advance a separate clock."),
      ("fig", "gantt", "The nominal run in Isaac Sim: leaves per agent over each session."),
      ("p", f"The twin's session durations deviate from the planner's by {', '.join(f'{v:+.1f} %' for v in BP.DEV.values())} and stay within "
            "the window. `isaac_identity_swap` ends as specified: L10 read the wrong barcode, the plate was quarantined at H4 and the run escalated."),
      ("p", "**Finding F17: `isaac_calibration_lapsed` does not end as specified.** The calibration repair worked: L17 refused, the plate was set "
            "aside, L21 recalibrated and the measurement was re-planned; A01 was then imaged validly. A02 then failed the focus floor twice "
            "(scores 0.035 and 0.030, floor 0.04); the session returned the plate and escalated, so control A05 was never imaged. After the "
            "reload, the A01 field is shifted by about 93 µm against the nominal run with the same commanded stage position and seat sensors "
            "at zero gap; two A02 images of the same load differ by about 35 µm. The plate seems to move in the nest, which the seat sensors "
            "do not see. The kernel's repair `focus_invalid → autofocus, retry` cannot change the outcome, because L17 autofocuses before "
            "every image; the process model prescribes a re-seat, and the LDL checker catches the refocus-only handler (N9). The disposition "
            "was correct for what happened; the expected outcome was not reached, and the expectation was not changed.")),

    S("Audit trail, critic and competency questions", "sec:audit",
      ("p", "Every lifecycle transition of every designator writes one commitment record: sequence number, simulated time, designator and "
            "parent, kind and category, transition, agent and software versions, the HADL term, bindings, resolution grounds, constraint "
            "verdicts, monitor results and evidence references, each with its own SHA-256. Each entry carries the hash of its predecessor and "
            "its own hash over the canonical JSON, forming a chain [@haber1991]. A verifier recomputes the chain; editing any value breaks it "
            "at that entry. §lst:audit§ shows a dispense entry."),
      ("lst", "audit", "An audit entry of the nominal trail (a dispense), abbreviated."),
      ("p", "**Critic.** The critic judges each episode from the trail alone, in two columns. Realization: the run ended executed and no "
            "runtime constraint was violated. Validity: V1–V7 (identity continuity, calibration at measurement, validated binding, controls "
            "measured, dose delivered, sample integrity, design realised). The result may update the culture belief only if both hold (D009)."),
      SS("Competency questions", "sec:cq"),
      ("p", f"{len(CQS)} competency questions in {len(rep['cq']['by_family'])} families ask what the assistant is doing, why, how, under which "
            "constraints, with which capability, what would happen if, with what evidence, what went wrong, which norms are covered, whether "
            "the result is valid, what it does not know, what kind of action something is, and what a device exchange would change. They "
            "are answered from the trail, the knowledge base and dry runs, with grounds. Expected answers were written by hand for selected "
            f"scenarios before the runs: {N['cq']} checks, {N['cq_ok']} correct and all grounded."),
      ("table", "cqfam", "Competency-question checks by family."),
      ("lst", "cq", "An answer with grounds: why L12 was chosen for dosing and which devices were rejected (CQ-03, nominal)."),
      SS("The kernel in the ontology", "sec:okf"),
      ("p", "The kernel's categories and the trail are exported to an OKF module. Each category is a class defined by its level and kernel "
            "name, so trail individuals are classified by the reasoner; effect classes and facets are disjoint superclasses aligned with the "
            "e2m designator classes. HermiT finds no unsatisfiable class after F14; Konclude realises 6244 individuals, and all 222 designators "
            "and 498 audit entries of the nominal trail are classified with none left over. 18 TBox competency questions and 6 negative controls "
            "pass.")),

    S("Motion level", "sec:motion",
      ("p", f"Every motion leaf of the executed plan is refined into a Giskard motion designator: {N['motions']} leaves become {N['motions']} "
            f"designators over {N['legs']} legs, {len(gm['distinct'])} of them distinct. Each designator has reference frames (robot root and tip, "
            "and a goal pose in a seat frame of the composed scene), motion constraints (Cartesian goal or straight line, speed limits, plate "
            "kept level, collision avoidance, allowed contacts), an ending monitor and cancel conditions, and the objective of giskardpy's "
            f"QP-based model-predictive controller. The output is a Lisp description and a giskardpy module of {GISK_LINES} lines whose API "
            "use was checked against a CRAM checkout."),
      ("table", "legs", "Distinct transport legs and their motion sequences."),
      ("table", "giskard", "Controller parameters and motion bounds."),
      ("lst", "giskard", "The generated giskardpy statechart for inserting into a seat."),
      ("p", f"All {N['goals']} goal frames are reachable with the FR3 and the rail-mounted UR5e kinematics within joint-margin and conditioning "
            "thresholds (§fig:reach§). R01's goals are collision-free; R02's collisions are not checked offline. Compliant insertion is open: "
            "giskardpy has no impedance control, and a force monitor needs ROS."),
      ("fig", "reach", "Reachability of the goal frames: joint-limit margin and smallest singular value of the Jacobian per goal.")),

    S("Refinement proof", "sec:proof",
      ("p", "The refinement proof shows that the motion-level plan executes the culture-level plan and satisfies the stated constraints, "
            "relative to explicit assumptions about controllers, sensors and devices. It is an assume-guarantee argument in the sense of "
            "refinement mappings and contract-based design [@abadi1991,benveniste2018]."),
      ("p", f"**Theorem.** Let Π_M be the motion-level plan of the experiment: the {N['steps']} grounded steps whose {N['motions']} robot motions "
            "are refined into Giskard statecharts. Under A1–A6, every execution of Π_M either (i) realizes the culture plan: every physical and "
            "knowledge effect in the derived order at the design's culture times, with the control untreated, while every stated constraint "
            "holds on the way (interlocks, L12 airspace, identity, environment before store, calibration before imaging, the window, "
            "contamination freedom, tool hygiene, plate level, collision distance); or (ii) is stopped by a monitor and ends in a failure "
            "handler whose guarantee holds (safe state, contained, or the goal)."),
      ("table", "assumptions", "Assumptions of the refinement proof."),
      ("fig", "chain", "The proof chain: levels, the obligation discharged between each pair, and the audit."),
      ("table", "obligations", "Proof obligations and how they are discharged."),
      ("table", "o2", "Obligation O2: every culture-level effect is entailed by step-level events (z3)."),
      ("p", "Motion constraints are hold-or-cancel: a statechart ends only through its end monitor or a cancel, and every cancel (timeout at "
            "1.2 × the estimate, tilt, collision distance) reaches a handler with a verified guarantee (O7). The proof does not cover progress "
            "(that a motion terminates), the two partly detected faults, contact physics, or Giskard's execution itself."),
      ("table", "negative", "Negative controls of the refinement proof.")),

    S("Independence of the culture plan", "sec:indep",
      ("p", "The culture plan must not depend on the laboratory. Two checks establish this. **Vocabulary:** no term of six realization "
            "vocabularies (robots, devices, lab setup, safety constraints, cleanliness, temperature control), collected from the facts, the "
            "component records and the registries, occurs in the culture plan. The check found one leak, a requirement for \"a calibration of "
            "the pixel size\"; it now requires a known image scale. **Invariance:** in "
            f"{N['labs']} laboratory variants the culture plan, its order and the lab plan are identical; only the realization differs, "
            "and some laboratories refuse before anything moves (§tab:labs§)."),
      ("table", "labs", "The culture plan in 13 laboratory variants. The culture-plan hash is the same in all.")),

    S("Reproducible derivation, plan and audit", "sec:repro",
      ("p", f"The derivation runs in {N['stages']} stages, from the EIG design to the protocol. A manifest records the hash of every input, "
            "the code each stage ran, every output and the tool versions; the manifest's own hash identifies the whole derivation. JSON outputs "
            "are hashed in canonical form without wall-clock fields; nothing else is excluded. `--verify` re-runs every stage, including a "
            f"fresh EIG Monte Carlo, and compares: all {N['outputs']} outputs were identical and the manifest hash `{mh[:16]}` was reproduced."),
      ("table", "repro", "Stages of the reproducible derivation and their reproduction."),
      ("table", "inputs", "Recorded inputs of the derivation."),
      ("table", "env", "Tool versions recorded in the manifest."),
      ("p", "**Experimentation plan.** `rsa/out/repro/protocol.md` is generated from the outputs: question and design with alternatives, culture "
            "plan and order, culture-to-well mapping, refinement into lab actions and devices, trips, constraints, handlers, KPIs, acceptance "
            "criteria and the records, bound to the derivation by an input digest. Appendix §sec:appendix-plan§ reproduces its tables."),
      ("p", f"**Audit certificate.** For all {N['trails']} trails, the chain is intact and a single changed value is detected. Each of the "
            f"{N['reexec_n']} symbolic scenarios was re-executed in a temporary directory and produced the identical trail, chain head included "
            "(§tab:audit_cert§). The Isaac trails are verified but not re-executed; GPU physics is not expected to be bit-reproducible, and they "
            "were recorded under older registry hashes."),
      ("table", "audit_cert", "Audit certificate: chain, tamper test and re-execution per trail.")),

    S("Findings log", "sec:findings",
      ("p", "Each iteration ended with findings that changed the kernel, the knowledge or the language. The table keeps the ones that changed "
            "concepts; the expectation tables were not changed after the runs, except two disclosed corrections in iteration 1 (repairs are "
            "recorded on the node that repaired; `session_failed` routes as escalation)."),
      ("table", "findings", "Findings F1–F17 and the changes they caused."),
      ("p", "**What the reconstruction learned.** A device-command designator is needed beside motions. Prospection operates at two levels "
            "(experiment and session) and must predict policies, not enforce them. Belief needs freshness. The understanding gate is cheap and "
            "belongs in prospection. Physical success and validity separate naturally once the measurement binding is a knowledge item. And "
            "repairs must be justified by the device's process model: a repair that repeats the same deterministic action cannot help.")),

    S("Limitations and open questions", "sec:limits",
      ("ul", ["**No wet laboratory.** The culture is a surrogate; all biological quantities are ILLUSTRATIVE. Twin parameters (window, "
              "tolerance, dose units, KPI targets) have no laboratory source yet.",
              "**Symbolic durations.** On the symbolic backend durations are the planner's facts; only the Isaac runs give independent timing.",
              "**Concurrency.** One plate, sequential sessions; several plates under concurrency are not handled.",
              "**Trust gaps.** Well misregistration at L12 and lateral plate seating at L17 are only partly detected; F17 is unresolved and needs "
              "a decision on what counts as the same measurement (another field in the well, another magnification).",
              "**Proof scope.** Relative to A1–A6; no progress guarantee; contact physics and Giskard execution are not covered; R02's "
              "goal collisions are not checked offline.",
              "**Reproduction scope.** One machine and environment; no clean clone or container yet. Isaac runs are recorded inputs.",
              "**Competency questions.** Hand-written query functions over the trail, not yet EQL or OWL queries; no natural-language front end.",
              "**Norms.** The regulation mapping is illustrative; signature and study-plan approval are documentary only (Part 11 not covered).",
              "**Pending decisions.** K1 (rule vs norm set), K4 (warrant definitions), K10 (epistemic vocabularies); calibration freshness; "
              "whether a human sign-off model is needed."])),

    S("Roadmap", "sec:roadmap",
      ("ul", ["**coraplex port.** `ActionDesignator` → `ActionDescription`, leaves → `MotionNode`; a device-command executable is proposed; "
              "resolution queries → krrood EQL over the semantic digital twin (lab annotations for plate, well, nest, device); CQs → "
              "`cram-viz-check` specifications. LDL contracts become pre- and post-conditions; `prevents` and `maintains` need a monitor "
              "attachment (D-LAT-11).",
              "**Re-seat repair and Isaac re-run.** Implement the prescribed re-seat for misseated plates at L17, confirm the plate movement from "
              "the physics state, re-run `isaac_calibration_lapsed`.",
              "**Close the trust gaps.** A dispense-position observation at L12; a lateral seating observation at L17.",
              "**Clean-room reproduction.** Container image and a clean clone; re-run `--verify` there.",
              "**Science.** A priming design to separate M2 from M3; several plates under concurrency.",
              "**Giskard execution.** A Cell 01 SDT world so the motion module runs; attach and detach the plate between statecharts; compliant insertion."])),
]

APPX = [
    ("appendix", "Experimentation plan tables", "sec:appendix-plan", [
        ("table", "handlers", "Failure handlers of the experiment's control program (LDL)."),
    ]),
    ("appendix", "Competency questions", "sec:appendix-cq", [
        ("table", "cqlist", "The competency questions and the scenarios for which an expected answer was checked."),
    ]),
    ("appendix", "Glossary", "sec:glossary", [("table", "glossary", "Terms used in this report.")]),
    ("appendix", "Rebuilding this report", "sec:rebuild", [
        ("p", "All commands run from the repository root with the project's Python environment:"),
        ("ul", ["`env_cad/bin/python -m rsa.reproduce --verify` re-runs the 12-stage derivation and compares manifests;",
                "`env_cad/bin/python paper/build_paper.py` builds the paper;",
                "`env_cad/bin/python report/build_report.py` builds this report: `report/rsa_report.tex` and, with LuaLaTeX, "
                "`report/rsa_report.pdf`."]),
        ("p", f"This build read the outputs at manifest `{mh[:16]}` (full hash on the title page). The report's TeX source needs "
              "`refs.bib` and the `figures/` directory beside it; fonts are Libertinus Serif, IBM Plex Sans and IBM Plex Mono."),
    ]),
]


# ------------------------------------------------------------------------------------------------------------- LaTeX
tex_inline, tex_esc = BP.tex_inline, BP.tex_esc
COLS = dict(levels="lXlll", obligations="lXll", assumptions="lXl", negative="Xl", repro="lXrr", scenarios="lllllrl", labs="Xlll",
            sessions="lllXrrr", refine="lllX", handlers="lX", concepts="lp{2.6cm}Xp{3.1cm}", categories="lrX", constraints="p{3.2cm}lp{1.9cm}Xp{3.0cm}",
            norms="p{3.4cm}Xp{4.6cm}", ldl_clauses="lXX", instruments="llp{3.2cm}Xr", models="lp{2.4cm}XlXX", trust="p{3.2cm}lXllll",
            guarantees="lllrl", empirical="XllXll", meta="p{3.0cm}XlX", treat="Xll", kpis="lXlll", kpiruns="Xlrrrrr", ldlneg="p{5cm}X",
            culture_steps="llXX", links="lllX", knowledge="Xl", instantiation="llX", feas="lllXrl", z3="XlX", design="p{3.6cm}X",
            scen_cat="lXX", cqfam="Xrr", cqlist="llXp{3.6cm}", audit_cert="Xrrllllp{3.2cm}", giskard="p{2.6cm}XX", legs="llrX", o2="Xl",
            env="lX", inputs="XXp{3.6cm}", findings="lXX", files="p{3.6cm}rX", glossary="p{3.4cm}X", key="XXp{3.2cm}")
SMALL = {"constraints", "trust", "models", "audit_cert", "meta", "culture_steps", "scen_cat", "cqlist", "inputs", "instruments", "findings", "labs", "ldlneg", "scenarios", "handlers"}


LONG = {"handlers", "cqlist", "glossary"}   # appendix tables stay where their section is


def tex_table(name, cap):
    head, rows = T[name]
    size = "\\footnotesize" if name in SMALL else "\\small"
    spec = COLS.get(name, "l" * (len(head) - 1) + "X")
    body = " \\\\\n".join(" & ".join(tex_inline(str(c)) for c in r) for r in rows)
    lines = sum(max(1.0, len(" ".join(map(str, r))) / 115) for r in rows)
    if lines <= 24 and name not in LONG:   # short tables float; only long ones break across pages
        return (f"\\begin{{table}}[tbp]\\centering{size}\n\\caption{{{tex_inline(cap)}}}\\label{{tab:{name}}}\n"
                f"\\begin{{tabularx}}{{\\linewidth}}{{{spec}}}\\toprule\n" + " & ".join(f"\\textbf{{{tex_esc(h)}}}" for h in head) +
                " \\\\\\midrule\n" + body + " \\\\\\bottomrule\n\\end{tabularx}\n\\end{table}\n")
    return (f"{{{size}\n\\begin{{xltabular}}{{\\linewidth}}{{{spec}}}\n\\caption{{{tex_inline(cap)}}}\\label{{tab:{name}}}\\\\\n\\toprule\n"
            + " & ".join(f"\\textbf{{{tex_esc(h)}}}" for h in head) + " \\\\\\midrule\n\\endfirsthead\n\\toprule\n"
            + " & ".join(f"\\textbf{{{tex_esc(h)}}}" for h in head) + " \\\\\\midrule\n\\endhead\n\\bottomrule\n\\endlastfoot\n"
            + body + " \\\\\n\\end{xltabular}}\n")


FIGW = dict(design="0.62\\linewidth", poset="\\linewidth", chain="0.9\\linewidth", lifecycle="\\linewidth", reach="0.72\\linewidth",
            arch="0.95\\linewidth")


def tex_block(b):
    if b[0] == "p":
        return tex_inline(b[1]) + "\n"
    if b[0] == "ul":
        return "\\begin{itemize}\n" + "".join(f"  \\item {tex_inline(x)}\n" for x in b[1]) + "\\end{itemize}\n"
    if b[0] == "sub":
        return f"\\subsection{{{tex_esc(b[1])}}}" + (f"\\label{{{b[2]}}}" if b[2] else "") + "\n"
    if b[0] == "fig":
        f = f"figures/{b[1]}.jpg" if b[1] in ("cell", "overview") else f"figures/{b[1]}.pdf"
        return (f"\\begin{{figure}}[tbp]\\centering\n\\includegraphics[width={FIGW.get(b[1], chr(92) + 'linewidth')}]{{{f}}}\n"
                f"\\caption{{{tex_inline(b[2])}}}\\label{{fig:{b[1]}}}\n\\end{{figure}}\n")
    if b[0] == "table":
        return tex_table(b[1], b[2])
    if b[0] == "lst":
        return (f"\\begin{{listing}}[tbp]\n\\begin{{Verbatim}}[fontsize=\\footnotesize,breaklines,frame=lines,framesep=2mm]\n{LST[b[1]].replace('φ', 'phi').replace('∋', ' in ')}\n\\end{{Verbatim}}\n"
                f"\\caption{{{tex_inline(b[2])}}}\\label{{lst:{b[1]}}}\n\\end{{listing}}\n")
    raise ValueError(b)


def latex():
    L = [r"""\documentclass[10pt,a4paper]{article}
\usepackage[margin=2.3cm,headheight=14pt]{geometry}
\usepackage{fontspec}
\setmainfont{Libertinus Serif}
\setsansfont{IBM Plex Sans}
\setmonofont[Scale=0.86]{IBM Plex Mono}
\usepackage{microtype,graphicx,booktabs,xltabular,xcolor,float,fvextra,caption,fancyhdr,titlesec,enumitem}
\usepackage{placeins}
\usepackage[numbers,sort&compress]{natbib}
\usepackage[colorlinks,linkcolor=teal!70!black,citecolor=teal!70!black,urlcolor=teal!70!black]{hyperref}
\newfloat{listing}{tbp}{lol}\floatname{listing}{Listing}
\captionsetup{font=small,labelfont=bf}
\renewcommand{\tabularxcolumn}[1]{>{\raggedright\arraybackslash}p{#1}}
\setlength{\tabcolsep}{4pt}
\setlength{\LTpre}{6pt}\setlength{\LTpost}{6pt}
\setlist{itemsep=2pt,topsep=4pt}
\titleformat{\section}{\sffamily\Large\bfseries\color{teal!55!black}}{\thesection}{0.8em}{}
\titleformat{\subsection}{\sffamily\large\bfseries}{\thesubsection}{0.7em}{}
\renewcommand{\floatpagefraction}{0.75}\renewcommand{\topfraction}{0.85}\renewcommand{\textfraction}{0.12}
\pagestyle{fancy}\fancyhf{}
\fancyhead[L]{\sffamily\footnotesize The Robot Science Assistant: technical report}
\fancyhead[R]{\sffamily\footnotesize\nouppercase{\leftmark}}
\fancyfoot[C]{\sffamily\footnotesize\thepage}
\renewcommand{\headrulewidth}{0.3pt}
\begin{document}
\begin{titlepage}
\sffamily
\vspace*{2.2cm}
\noindent{\color{teal!55!black}\rule{\linewidth}{1.2pt}}\par\vspace{0.6cm}
\noindent{\Huge\bfseries The Robot Science Assistant\par}\vspace{0.4cm}
{\Large From culture-level plans to verified robot motions,\\ reproducible derivations and auditable executions\par}\vspace{0.6cm}
\noindent{\color{teal!55!black}\rule{\linewidth}{1.2pt}}\par\vspace{1.0cm}
{\large Technical report on the RSA kernel, its languages and its evaluation\\ on Cell 01 of the LabAutomationTwin\par}
\vspace{1.4cm}
{\normalsize [Authors and affiliations]\par}
\vfill
{\small\rmfamily
\begin{tabular}{@{}ll@{}}
Generated & 2026-10-17, from the pipeline's outputs \\
Manifest & \texttt{""" + mh[:32] + r"""} \\
         & \texttt{""" + mh[32:] + r"""} \\
Example & challenge--rescue experiment, design \texttt{""" + tex_esc(sel["id"]) + r"""} \\
Status & research prototype; biology is a surrogate, quantities ILLUSTRATIVE (D016) \\
\end{tabular}\par}
\end{titlepage}
\pagenumbering{roman}
\tableofcontents
\clearpage
\pagenumbering{arabic}
"""]
    for b in DOC:
        L.append(f"\\section{{{tex_esc(b[1])}}}\\label{{{b[2]}}}\n")
        L += [tex_block(x) for x in b[3]]
    L.append("\\FloatBarrier\n\\bibliographystyle{unsrtnat}\n\\bibliography{refs}\n\\appendix\n")
    for b in APPX:
        L.append(f"\\section{{{tex_esc(b[1])}}}\\label{{{b[2]}}}\n")
        L += [tex_block(x) for x in b[3]]
    L.append("\\end{document}\n")
    return "\n".join(L).replace("\\_", "\\_\\allowbreak{}")


def bibtex():
    used = []
    for b in DOC:
        for x in b[3]:
            texts = [x[1]] if x[0] == "p" else (x[1] if x[0] == "ul" else [])
            for t in texts:
                for grp in re.findall(r"\[@([^\]]+)\]", t):
                    used += [c for c in grp.split(",") if c not in used]
    missing = [c for c in used if c not in BP.REFS]
    assert not missing, missing
    return BP.bibtex()


def main():
    os.makedirs(FIG, exist_ok=True)
    BP.fig_chain(); BP.fig_poset(); BP.fig_design(); BP.fig_gantt()
    BP.photo()
    fig_arch(); fig_lifecycle(); fig_culture(); fig_trust(); fig_kpi(); fig_reach(); fig_trail()
    open(os.path.join(HERE, "refs.bib"), "w").write(bibtex())
    open(os.path.join(HERE, "rsa_report.tex"), "w").write(latex())
    r = subprocess.run(["latexmk", "-lualatex", "-interaction=nonstopmode", "-halt-on-error", "rsa_report.tex"], cwd=HERE,
                       capture_output=True, text=True, timeout=900)
    logp = os.path.join(HERE, "rsa_report.log")
    log = open(logp, errors="replace").read() if os.path.exists(logp) else ""
    pages = re.search(r"Output written on rsa_report\.pdf \((\d+) pages", log)
    warn = [l for l in log.splitlines() if re.search(r"undefined|Overfull \\hbox \((\d{2,})|Missing character", l)]
    print(f"[report] latexmk exit {r.returncode}; {pages.group(1) if pages else '?'} pages; warnings {len(warn)}")
    for w in warn[:20]:
        print("   ", w[:170])
    if r.returncode:
        print(r.stdout[-3000:])
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
