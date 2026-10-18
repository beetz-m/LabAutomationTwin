"""Illustration of LDL, the lab designator language (docs/rsa/LAB-DESIGNATOR-LANGUAGE.md, rsa/ldl.py).

Top: the anatomy of an action contract over the action's interval [t0, t1] (requires, prevents, maintains, achieves,
goal; the instrument role; signalled failures and their handlers). Bottom: the LDL documents of the lab
(rsa/registry/lab/*.ldl) above the abstraction boundary, and what realizes them below it. Contract, process-model and
rule names are read from the registry files. Writes renders/ontology/ldl_overview.{png,pdf,svg}.

    env_cad/bin/python tools/ldl_illustration.py
"""

import glob
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REG = os.path.join(ROOT, "rsa", "registry", "lab")
OUT = os.path.join(ROOT, "renders", "ontology")


def names(file, head):
    return re.findall(rf"^\s*\({head} ([\w-]+)", open(os.path.join(REG, file)).read(), re.M)


contracts = names("contracts.ldl", "contract")
processes = names("processes.ldl", "process-model")
rules = names("epistemic.ldl", "rule")
treatments = names("epistemic.ldl", "treatment")
files = sorted(os.path.basename(f) for f in glob.glob(os.path.join(REG, "*.ldl")))
lines = {f: sum(1 for _ in open(os.path.join(REG, f))) for f in files}

INK, MUTED = "#1f2a33", "#5b6b78"
C = dict(requires="#2f6f9f", prevents="#b03a2e", maintains="#a8611c", achieves="#2f7d4f", goal="#6d4a9a",
         inst="#4f8f8f", fail="#7a5510")
plt.rcParams["font.family"] = "DejaVu Sans"
fig = plt.figure(figsize=(17, 13.2))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 17)
ax.set_ylim(0, 13.2)
ax.axis("off")


def box(x, y, w, h, fc, ec, lw=1.2, r=0.1):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw))


def txt(x, y, s, size=9, col=INK, weight="normal", ha="left", va="top", family=None):
    ax.text(x, y, s, fontsize=size, color=col, weight=weight, ha=ha, va=va, family=family)


def arrow(p, q, col="#6f7d89", ls="-", lw=1.3, style="-|>"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=12, lw=lw, color=col, linestyle=ls,
                                 shrinkA=1, shrinkB=1))


txt(0.3, 12.95, "LDL: the lab designator language", 18, INK, "bold")
txt(0.3, 12.48, "states what a lab action must bring about - never how; every term is an entity description over lab "
    "entities, never a robot, tool, pose or device", 10.5, MUTED)

# ---------------------------------------------------------------- A. anatomy of an action contract
box(0.3, 6.15, 16.4, 6.0, "white", "#8e9aa5", 1.4)
txt(0.5, 11.95, "A  An action is a contract over its interval", 12.5, INK, "bold")
txt(0.5, 11.62, "(the action ?a (type intervening) (into (the well ?w (of ?p))) (substance ?s) (dose ?q) ...)   "
    "- roles are bound by the step; the contract is owned by the action type", 8.8, MUTED, family="DejaVu Sans Mono")
X0, X1, Y = 2.4, 13.6, 7.8
ax.plot([X0 - 1.0, X1 + 1.2], [Y, Y], color="#9aa6b0", lw=1.2)
for x, lab in ((X0, "t0: action starts"), (X1, "t1: action ends")):
    ax.plot([x, x], [Y - 0.12, 11.1], color="#c3cbd2", lw=1, ls=":")
    txt(x, Y - 0.2, lab, 9, MUTED, ha="center")
txt(X1 + 1.25, Y + 0.05, "time", 9, MUTED, va="center")
rows = [("requires", "holds, and is known to hold, at t0", "check it, or establish it first (e.g. qualify the "
         "instrument); (known ...) can only be verified", (X0 - 0.12, X0 + 0.12)),
        ("prevents", "never occurs in [t0, t1]", "needs a detector and a reaction (abort, contain); e.g. cross-dosing, "
         "contamination, an excursion > 600 s", (X0, X1)),
        ("maintains", "holds throughout [t0, t1]", "needs a regulator and a recorded history; e.g. the plate stays in "
         "its controlled environment", (X0, X1)),
        ("achieves", "holds at t1 and persists", "enforced effects, including the evidence record (hash-chained, "
         "original)", (X1 - 0.12, X1 + 0.12)),
        ("goal", "what the step is for", "e.g. (the well ?w (received ?s ?q)) :tolerance 5 % :column validity; causal "
         "links connect goals", (X1 - 0.12, X1 + 0.12))]
for k, (name, sem, op, (a, b)) in enumerate(rows):
    y = 11.0 - k * 0.6
    col = C[name]
    txt(0.5, y + 0.12, name, 10.5, col, "bold", family="DejaVu Sans Mono")
    if b - a > 1:
        ax.add_patch(Rectangle((a, y - 0.12), b - a, 0.24, fc=col, alpha=0.18, ec=col, lw=1))
    else:
        ax.add_patch(Rectangle((a, y - 0.16), b - a, 0.32, fc=col, alpha=0.85, ec=col))
    left = b - a > 1 or a < X0 + 1
    tx = X0 + 0.25 if left else a - 0.25
    txt(tx, y + 0.08, sem, 9, col, "bold", ha="left" if left else "right")
    txt(tx, y - 0.17, op, 8, INK, ha="left" if left else "right")
txt(X0 + 0.25, 8.22, "scope: prevents / maintains may run inside a scope opened and closed by fluents, e.g. only while "
    "the drawn portion is not yet delivered (RPL monitor)", 8.2, MUTED)
# instrument role and failures
box(0.5, 6.3, 7.9, 0.95, "#eef6f6", C["inst"])
txt(0.65, 7.15, "instrument role (attributive only)", 9.6, C["inst"], "bold")
txt(0.65, 6.88, "(an instrument ?d (slot (a plate-slot (accepts ?p))) (process (a process (type substance-transfer) ...)))",
    7.6, INK, family="DejaVu Sans Mono")
txt(0.65, 6.6, "resolved by the realization to a device that has the slot and offers the process: dosing -> L12, "
    "imaging -> L17, incubation -> L10", 8, MUTED)
box(8.6, 6.3, 7.9, 0.95, "#fbf3e3", C["fail"])
txt(8.75, 7.15, "signals and handles", 9.6, C["fail"], "bold")
txt(8.75, 6.88, "(signals (a failure (type dose-not-delivered)))  ->  (handles (on ...) (do ...) (then retry|replan|escalate))",
    7.3, INK, family="DejaVu Sans Mono")
txt(8.75, 6.6, "every handler states its guarantee: goal | goal-or-safe-state | safe-state | contained", 8, MUTED)

# ---------------------------------------------------------------- B. documents and the abstraction boundary
box(0.3, 0.3, 16.4, 5.6, "white", "#8e9aa5", 1.4)
txt(0.5, 5.7, "B  The lab's LDL documents, and what realizes them", 12.5, INK, "bold")
docs = [("experiment.ldl", "the experiment as an entity: cultures defined by treatments, comparisons, "
         "goal (>= 0.5 bit), insights", C["goal"]),
        ("challenge_rescue.ldl", "the experiment's action designator: workflow at culture times, handlers with "
         "guarantees", C["goal"]),
        ("culture_plan.ldl", "culture-level plan: steps with physical and knowledge effects; order derived from "
         "causal links", C["achieves"]),
        ("contracts.ldl", f"category contracts: {', '.join(contracts)}", C["requires"]),
        ("processes.ldl", f"device processes: {', '.join(processes)}; phases, irreversible phase, faults",
         C["prevents"]),
        ("epistemic.ldl", f"meta model: {len(rules)} rules, {len(treatments)} treatments for beliefs that fall short "
         "(observed > reported > inferred > ...)", C["maintains"]),
        ("experiment_concepts.ldl", "concept hierarchy of experiments with partonomy and closed-world checks", MUTED)]
order = ["experiment.ldl", "challenge_rescue.ldl", "culture_plan.ldl", "contracts.ldl", "processes.ldl", "epistemic.ldl",
         "experiment_concepts.ldl"]
docs = sorted(docs, key=lambda d: order.index(d[0]))
for k, (f, what, col) in enumerate(docs):
    y = 5.15 - k * 0.56
    box(0.5, y - 0.42, 9.2, 0.48, "white", col, 1.1, 0.06)
    txt(0.62, y - 0.06, f, 9.2, col, "bold", family="DejaVu Sans Mono")
    txt(0.62, y - 0.26, f"{lines.get(f, 0)} lines", 7.4, MUTED)
    txt(2.95, y - 0.18, what, 8.0, INK, va="center")
# boundary
ax.plot([9.95, 9.95], [0.8, 5.35], color="#b03a2e", lw=1.6, ls=(0, (5, 3)))
txt(10.05, 5.55, "abstraction boundary (linted)", 9.6, "#b03a2e", "bold")
txt(10.05, 5.27, "no robot, gripper, tool, pose, frame, prim, trajectory or device id;", 8, MUTED)
txt(10.05, 5.05, "instruments only attributively (a/an), never 'the'", 8, MUTED)
real = [("rsa/ldl.py", "parser, evaluator over belief and trail, admissibility: monitors for every\n"
         "prevents, a handler for every failure, every guarantee checked"),
        ("rsa/ldl_to_cram.py, culture_to_cram.py", "CRAM/RPL plans: partial order, with-policy monitors, "
         "unwind-protect, failure handling"),
        ("kernel + robots (R01, R02, R03)", "transport, tool coupling, sessions within the excursion window - the "
         "realization of one lab step"),
        ("devices (L09, L10, L12, L17, L21, H4)", "fill the instrument role through their slot and process; their "
         "records ground the process models"),
        ("semantic digital twin (USD)", "the referents: plates, wells, frames; records and belief")]
for k, (t, what) in enumerate(real):
    y = 4.6 - k * 0.83
    box(10.1, y - 0.65, 6.4, 0.72, "#f6f7f8", "#9aa6b0", 1, 0.06)
    txt(10.22, y - 0.05, t, 9, INK, "bold")
    txt(10.22, y - 0.3, what, 7.9, MUTED)
arrow((9.75, 2.55), (10.1, 2.55))
txt(9.92, 2.75, "realized\nby", 7.6, MUTED, ha="center", va="bottom")
txt(0.5, 0.45, "Checks (rsa/ldl.py, v0.3): 20/20 signalled failures handled, 13/13 repair guarantees hold, 11/11 record "
    "faults grounded, 12/12 negative controls caught. Quantities ILLUSTRATIVE (D016).", 8.0, MUTED, ha="left",
    va="bottom")
os.makedirs(OUT, exist_ok=True)
for ext in ("png", "pdf", "svg"):
    fig.savefig(os.path.join(OUT, f"ldl_overview.{ext}"), dpi=170 if ext == "png" else None)
print(f"[ldl] contracts {contracts}; processes {processes}; {len(rules)} rules, {len(treatments)} treatments; "
      f"{len(files)} files -> {OUT}/ldl_overview.png")
