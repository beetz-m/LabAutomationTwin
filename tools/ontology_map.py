"""Overview illustration of the ontologies of the LabAutomationTwin and how they connect.

Counts are read from the sources: the lab ontology (okf/lab-automation-twin/src/tbox.py), the experiment ontology
(rsa/experiment_ontology.py) and Cell 01's biology ontology (rsa/out/experiment_ontology/aicor-biology.rdf).
Writes renders/ontology/ontology_map.{svg,png,pdf}.

    env_cad/bin/python tools/ontology_map.py
"""

import collections
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "okf/lab-automation-twin/src"))
import tbox  # noqa: E402
from rsa import experiment_ontology as XO  # noqa: E402

OUT = os.path.join(ROOT, "renders", "ontology")

# --------------------------------------------------------------------------------------------- counts from sources
mods = collections.OrderedDict()
for c in tbox.CLASSES:
    mods.setdefault(c["module"][0], dict(title=c["module"][1], classes=[], props=0))["classes"].append(c["name"])
for p in tbox.PROPS:
    if p["module"][0] in mods:
        mods[p["module"][0]]["props"] += 1
S = XO.tbox()
names = set()
for s in S:
    for a in s["axioms"]:
        for side in ("l", "r"):
            x = getattr(a, side, None)
            if isinstance(x, XO.E):
                names |= x.names()
        for c in getattr(a, "cs", []):
            names |= c.names()
n_xo_cls = len({n for n in names if not n.startswith("bio:")})
n_xo_ax = sum(len(s["axioms"]) for s in S)
bio = open(os.path.join(ROOT, "rsa/out/experiment_ontology/aicor-biology.rdf")).read().count('owl#Class"')

# --------------------------------------------------------------------------------------------- drawing (hand-placed)
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

INK, MUTED = "#1f2a33", "#5b6b78"


def short(m):
    return m.replace("lab-twin-", "")


GROUPS = [("Why, and with what evidence", "#f3edf8", "#6d4a9a", ["lab-twin-culture-experiments", "lab-twin-records",
                                                                 "lab-twin-experiment-to-motion"]),
          ("How, and safely", "#fbf1e6", "#a8611c", ["lab-twin-tasks", "lab-twin-device-manuals", "lab-twin-safe-action",
                                                     "lab-twin-rsa-kernel"]),
          ("What", "#eaf5ee", "#2f7d4f", ["lab-twin-devices", "lab-twin-robots", "lab-twin-labware"]),
          ("Where", "#e8f1f8", "#2f6f9f", ["lab-twin-site", "lab-twin-core", "lab-twin-poses"])]
fig = plt.figure(figsize=(17, 13.7))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 17)
ax.set_ylim(0, 13.7)
ax.axis("off")
plt.rcParams["font.family"] = "DejaVu Sans"


def panel(x, y, w, h, fill, edge, title=None, tcol=INK, size=11.5, lw=1.2, sub=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.12", fc=fill, ec=edge, lw=lw))
    if title:
        ax.text(x + 0.15, y + h - 0.2, title, fontsize=size, color=tcol, weight="bold", va="top")
    if sub:
        ax.text(x + 0.15, y + h - 0.47, sub, fontsize=8.6, color=MUTED, va="top")


def card(x, y, w, h, title, sub, lines, col, edge=None, wrap=None):
    if wrap:
        import textwrap
        lines = [ln for l0 in lines for ln in textwrap.wrap(l0, wrap, subsequent_indent="  ")]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.08", fc="white",
                                ec=edge or col, lw=1.1))
    ax.text(x + 0.12, y + h - 0.13, title, fontsize=9.6, color=col, weight="bold", va="top")
    ax.text(x + 0.12, y + h - 0.36, sub, fontsize=7.6, color=MUTED, va="top")
    for k, ln in enumerate(lines):
        ax.text(x + 0.12, y + h - 0.58 - 0.17 * k, ln, fontsize=7.6, color=INK, va="top")


def arrow(p, q, label="", ls="-", both=False, lx=0.0, ly=0.0, ha="left", rad=0.0):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="<|-|>" if both else "-|>", mutation_scale=12, lw=1.3,
                                 color="#6f7d89", linestyle=ls, connectionstyle=f"arc3,rad={rad}",
                                 shrinkA=2, shrinkB=2, zorder=5))
    if label:
        mx, my = (p[0] + q[0]) / 2 + lx, (p[1] + q[1]) / 2 + ly
        ax.text(mx, my, label, fontsize=8.4, color="#3f4d58", ha=ha, va="center", zorder=6,
                bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="none", alpha=0.9))


ax.text(0.3, 13.4, "Ontologies of the LabAutomationTwin", fontsize=18, weight="bold", color=INK, va="top")
ax.text(0.3, 12.92, "what the lab is, what it can and safely may do, what an experiment is, what the evidence says - and how "
        "they connect", fontsize=10.5, color=MUTED, va="top")
# upstream band
panel(0.3, 11.0, 16.4, 1.35, "#f4f5f6", "#b8c0c7", "Upstream ontologies (AICOR federation, read-only)", "#33414c", 11)
UP = (("AICOR L2 ontology", "the hub: scene graph, robots, poses, monitors"),
      ("Robot-scientist vertical", "study designs, interventions, readouts"),
      ("VRB lab-automation-device", "devices and device functions"),
      ("Normative admissibility", "norms, admissible actions"),
      ("DUL / SOMA", "places, concepts, actions"))
for k, (t, sub) in enumerate(UP):
    x = 0.5 + k * 3.24
    ax.add_patch(FancyBboxPatch((x, 11.13), 3.0, 0.72, boxstyle="round,pad=0,rounding_size=0.08", fc="white",
                                ec="#b8c0c7", lw=1))
    ax.text(x + 0.12, 11.75, t, fontsize=9.4, weight="bold", color="#33414c", va="top")
    ax.text(x + 0.12, 11.48, sub, fontsize=7.8, color=MUTED, va="top")
# lab ontology panel
LX, LY, LW, LH = 0.3, 4.55, 16.4, 6.2
panel(LX, LY, LW, LH, "white", "#8e9aa5", "Lab ontology", INK, 12.5, 1.4,
      sub=f"OKF module lab-automation-twin (okf/lab-automation-twin): {len(tbox.CLASSES)} concepts, {len(tbox.PROPS)} "
          f"properties, {len(mods)} modules, HermiT-consistent; extends the upstream ontologies")
gx = {}
cw = 3.9
for k, (g, fill, col, ms) in enumerate(GROUPS):
    x0 = 0.5 + k * 4.05
    panel(x0, LY + 0.15, cw, LH - 0.85, fill, col, g, col, 10.2)
    gx[g] = x0
    ch, gap = 1.12, 0.1
    for j, m in enumerate(ms):
        d = mods[m]
        ex = [x for x in d["classes"] if ":" not in x][:3]
        yy = LY + LH - 1.25 - (j + 1) * (ch + gap) + gap
        card(x0 + 0.12, yy, cw - 0.24, ch, short(m), f"{len(d['classes'])} concepts, {d['props']} propert{'y' if d['props'] == 1 else 'ies'}", ex, col)
        gx[m] = (x0 + 0.12, yy, cw - 0.24, ch)
# bottom row
sec = [s_["title"] for s_ in S]
half = (len(sec) + 1) // 2
panel(0.3, 0.3, 8.0, 3.75, "#fdf6e9", "#b7862a", "Experiment ontology", "#7a5510", 12.5, 1.4,
      sub=f"rsa/experiment_ontology.py: {n_xo_cls} concepts, {n_xo_ax} axioms, OWL 2 DL, HermiT")
card(0.5, 0.75, 2.3, 2.5, "LDL", "lab designator language", ["experiment, challenge_rescue", "culture_plan", "contracts (4 action types)",
                                                              "processes (4 device", "  processes)", "epistemic meta model",
                                                              "experiment_concepts", "-> CRAM/RPL plans"], "#7a5510", "#b7862a")
card(2.95, 0.75, 2.6, 2.5, "Experiments and biology", f"sections 1-{half}", sec[:half], "#7a5510", "#b7862a", wrap=30)
card(5.65, 0.75, 2.35, 2.5, "Designs, evidence, labs", f"sections {half + 1}-{len(sec)}", sec[half:], "#7a5510", "#b7862a", wrap=27)
arrow((2.8, 1.85), (2.95, 1.85))
panel(8.55, 0.3, 4.6, 3.75, "#eef6f6", "#4f8f8f", "Cell 01 package (read-only)", "#2f6666", 12)
card(8.75, 0.75, 2.0, 2.5, "Component records", "10 SDT contracts", ["capabilities", "monitors", "failure modes", "recovery",
                                                                   "NEEM record", "schemas"], "#2f6666")
card(10.95, 0.75, 2.0, 2.5, "Biology ontology", f"{bio} classes", ["cultures, organoids", "biological processes", "toxic challenge",
                                                                 "rescue intervention", "hypotheses,", "predictions"], "#2f6666")
panel(13.4, 0.3, 3.3, 3.75, "white", INK, "Semantic digital twin", INK, 12, 1.8, sub="USD: the instances of all of these")
for k, ln in enumerate(["AICOR Lab 1 and Cell 01 prims", "devices, robots, plates, wells", "culture SDT layer: belief,",
                        "  interventions, observations", "robot episodes, records,", "  images, claims"]):
    ax.text(13.55, 3.25 - 0.27 * k, ln, fontsize=8.6, color=INK, va="top")
# connections
arrow((8.5, 11.0), (8.5, 10.75), "grounded in: 325 concepts placed under 51 upstream classes", lx=0.12)
arrow((2.4, 4.05), (2.4, 4.7), "overlaps culture-experiments: not yet merged", ls="--", both=True, lx=0.12)
arrow((9.75, 4.05), (6.6, 4.7), "cell01-bridge.ofn (device manuals)", lx=-0.15, ly=-0.08, ha="right")
arrow((11.95, 4.05), (11.95, 4.7), "bridge (labware, biology)", lx=0.12)
arrow((14.9, 4.05), (14.9, 4.7), "prims are instances (ABox)", lx=0.12)
ax.plot([4.25, 4.25, 11.95], [0.75, 0.55, 0.55], color="#6f7d89", lw=1.3, zorder=5)
ax.add_patch(FancyArrowPatch((11.95, 0.55), (11.95, 0.76), arrowstyle="-|>", mutation_scale=12, lw=1.3, color="#6f7d89",
                             shrinkA=0, shrinkB=0, zorder=5))
ax.text(8.1, 0.4, f"{len(XO.ALIGN)} alignment subsumptions to Cell 01 biology", fontsize=8.4, color="#3f4d58", ha="center",
        va="center", zorder=6, bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="none", alpha=0.9))
arrow((8.75, 2.3), (8.0, 2.3))
ax.text(8.375, 2.58, "capability\nprofiles", fontsize=7.8, color="#3f4d58", ha="center", va="center")
fig.savefig(os.path.join(OUT, "ontology_map.png"), dpi=170)
fig.savefig(os.path.join(OUT, "ontology_map.pdf"))
fig.savefig(os.path.join(OUT, "ontology_map.svg"))
print(f"[ontology_map] lab {len(tbox.CLASSES)} concepts / {len(mods)} modules; experiment {n_xo_cls} concepts, "
      f"{n_xo_ax} axioms; biology {bio} classes -> {OUT}/ontology_map.png")
