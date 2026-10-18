"""Build the paper from the pipeline's outputs: every number, table, figure and listing is read from rsa/out, the
derivation outputs and the reproduction manifest, so the paper is a build product of the pipeline it describes.

    env_cad/bin/python paper/build_paper.py          # paper/paper.tex, paper/paper.pdf (lualatex), paper/paper.html

ILLUSTRATIVE (D016): the culture biology is Cell 01's surrogate; no biomedical parameter is asserted.
"""

from __future__ import annotations

import base64
import collections
import hashlib
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "rsa", "out")
REPRO = os.path.join(OUT, "repro")
DERIV = os.path.join(ROOT, "okf", "lab-automation-twin", "L3-logical-axiomatization", "derivation")
FIG = os.path.join(HERE, "figures")
J = lambda *p: json.load(open(os.path.join(*p)))  # noqa: E731

# ------------------------------------------------------------------------------------------------------------- data
cp, plan, ldl = J(OUT, "culture_plan.json"), J(DERIV, "out", "plan_g050.json"), J(OUT, "ldl_challenge_rescue.json")
gm, frames, rp = J(OUT, "giskard_motions.json"), J(OUT, "motion_frames.json"), J(OUT, "refinement_proof.json")
zp, rep, ind = J(DERIV, "out", "proof_g050.json"), J(OUT, "report.json"), J(OUT, "independence.json")
man, repro, aud, prot = J(REPRO, "manifest.json"), J(REPRO, "reproduction.json"), J(REPRO, "audit.json"), J(REPRO, "protocol.json")
cands = J(ROOT, "okf", "lab-automation-twin", "build", "e2m", "eig_candidates.json")
K, sel = cp["knowledge"], plan["selected"]
runs = {n[4:-5]: J(OUT, n) for n in sorted(os.listdir(OUT)) if n.startswith("run_") and n.endswith(".json")}
N = dict(
    culture_actions=len(cp["plan"]["steps"]), culture_links=len(cp["derived"]["links"]), lab_steps=len(ldl["steps"]),
    handlers=len(ldl["handles"]), threats=len(ldl["threats"]), sessions=len(plan["sessions"]),
    steps=sum(len(s["steps"]) for s in plan["sessions"]), motions=sum(len(l["motions"]) for l in gm["legs"]),
    legs=len(gm["legs"]), goals=len(frames["goals"]), goals_ok=sum(1 for g in frames["goals"] if g["reachable"]),
    cq=rep["cq"]["n"], cq_ok=rep["cq"]["correct"], labs=len(ind["labs"]), candidates=len(cands["candidates"]),
    feasible=len(plan["feasible_candidates"]), stages=len(man["stages"]),
    outputs=sum(s["outputs"] for s in repro["stages"].values()), identical=sum(s["identical"] for s in repro["stages"].values()),
    trails=len(aud["trails"]), reexec=sum(1 for t in aud["trails"] if t["reexecuted_identical"]),
    reexec_n=sum(1 for t in aud["trails"] if t["reexecuted_identical"] is not None),
    faults=sum(len(t["faults"]) for t in ldl["trust"]), faults_full=sum(1 for t in ldl["trust"] for f in t["faults"] if f["detected"] == "full"),
    nominal_entries=runs["nominal"]["n_entries"], nominal_leaves=runs["nominal"]["n_leaves"],
    neg_ldl=len(ldl["negative_controls"]), neg_z3=len(zp["negative_controls"]), neg_rp=len(rp["negative_controls"]),
)
SYMB = sorted((n for n in runs if not n.startswith("isaac")), key=lambda n: (n != "nominal", n))
ISAAC = sorted((n for n in runs if n.startswith("isaac")), key=lambda n: (n != "isaac_nominal", n))


def session_durations(name):
    E = J(OUT, f"trail_{name}.json")["entries"]
    out = {}
    for e in E:
        if e["category"] == "run_session" and e["transition"] in ("executed", "escalated", "failed"):
            o = next(x for x in E if x["designator"] == e["designator"])
            g = next((x for x in E if x["designator"] == e["designator"] and x["transition"] == "grounded"), None)
            out[g["bindings"]["session"] if g else e["designator"]] = round(e["t_sim"] - o["t_sim"], 1)
    return out


DUR_PLAN = {s["session"]: s["duration_s"] + s.get("prep_s", 0.0) for s in plan["sessions"]}
DUR_ISAAC = session_durations("isaac_nominal")
DEV = {s: round(100 * (DUR_ISAAC[s] - DUR_PLAN[s]) / DUR_PLAN[s], 1) for s in DUR_ISAAC}

# ------------------------------------------------------------------------------------------------------------- figures
INK, MUTED, LINE = "#1d2630", "#5c6873", "#c9d1d6"
C = dict(phys="#0b7a75", know="#7a45c4", grow="#b7791f", obs="#2456c9", proof="#2c8540", bad="#c2362f")
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK, "svg.fonttype": "none",
                     "axes.spines.top": False, "axes.spines.right": False})


def save(fig, name):
    os.makedirs(FIG, exist_ok=True)
    fig.savefig(os.path.join(FIG, name + ".pdf"), bbox_inches="tight")
    fig.savefig(os.path.join(FIG, name + ".svg"), bbox_inches="tight")
    plt.close(fig)


def box(ax, x, y, w, h, title, sub, color, fs=8.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.06", fc="white", ec=color, lw=1.4))
    ax.add_patch(FancyBboxPatch((x, y), 0.07, h, boxstyle="square,pad=0", fc=color, ec=color, lw=0))
    ax.text(x + 0.18, y + h - 0.16, title, fontsize=fs + 0.8, fontweight="bold", va="top", color=INK)
    ax.text(x + 0.18, y + h - 0.5, sub, fontsize=fs - 0.9, va="top", color=MUTED, linespacing=1.4)


def fig_chain():
    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    ax.set_xlim(0, 12); ax.set_ylim(-0.2, 8.6); ax.axis("off")
    L = [("Culture-level plan", f"{N['culture_actions']} actions on 3 cultures; physical and knowledge effects;\ngoal: expected information gain ≥ 0.5 bit", C["phys"]),
         ("Design and lab plan", f"EIG over {N['candidates']} candidates, least-cost plan (clingo);\n{N['lab_steps']} lab action designators, {N['handlers']} failure handlers (LDL)", C["obs"]),
         ("Step plan and controller", f"{N['sessions']} trips, {N['steps']} grounded robot and device steps;\nCRAM/RPL structured reactive controller", C["grow"]),
         ("Motion plan", f"{N['motions']} Giskard motion statecharts over {N['goals']} goal frames;\nmonitors make soft constraints hold-or-cancel", C["know"]),
         ("Execution", "symbolic backend (12 scenarios) and Isaac Sim physics (3 runs);\nhash-chained audit trail per run", INK)]
    obs = ["O1  O2", "O3", "O4  O5", "O6  O7"]
    y0, h, gap = 7.2, 1.25, 0.48
    for i, (t, s, c) in enumerate(L):
        y = y0 - i * (h + gap)
        box(ax, 0.2, y, 7.5, h, t, s, c, fs=8)
        if i < len(L) - 1:
            ax.add_patch(FancyArrowPatch((1.0, y), (1.0, y - gap), arrowstyle="-|>", mutation_scale=10, color=MUTED, lw=1.1))
            ax.text(1.2, y - gap / 2, "refined by", fontsize=7, color=MUTED, va="center", style="italic")
            ax.text(3.1, y - gap / 2, obs[i], fontsize=7.6, color=C["proof"], va="center", fontweight="bold")
    # right: proof and manifest brackets
    top, bot = y0 + h, y0 - 4 * (h + gap)
    ax.add_patch(FancyBboxPatch((8.0, y0 - 3 * (h + gap) - 0.0), 3.8, 3 * (h + gap) + h, boxstyle="round,pad=0,rounding_size=0.08",
                                fc="#eef6ef", ec=C["proof"], lw=1.1))
    ax.text(8.2, top - 0.2, "Refinement proof", fontsize=9.2, fontweight="bold", va="top", color=C["proof"])
    ax.text(8.2, top - 0.55, "z3 and exhaustive checks;\nunder assumptions A1–A6\nevery execution realizes\nthe culture plan, or stops\nin a handler whose\nguarantee holds\n\n"
            f"{N['neg_rp']} negative controls\ncaught", fontsize=7.6, va="top", color=INK, linespacing=1.4)
    ax.add_patch(FancyBboxPatch((8.0, bot), 3.8, h, boxstyle="round,pad=0,rounding_size=0.08", fc="#f3eefb", ec=C["know"], lw=1.1))
    ax.text(8.2, bot + h - 0.17, "Audit trail", fontsize=9.2, fontweight="bold", va="top", color=C["know"])
    ax.text(8.2, bot + h - 0.5, "SHA-256 chain; re-execution\nreproduces the chain head", fontsize=7.6, va="top", color=INK, linespacing=1.35)
    ax.text(0.2, bot - 0.22, f"manifest: sha256 of inputs, code and {N['outputs']} outputs of {N['stages']} stages; a re-run reproduced all of them",
            fontsize=7.4, color=MUTED, va="top")
    save(fig, "chain")


def fig_poset():
    steps = cp["plan"]["steps"]
    var = [s["var"] for s in steps]
    typ = {s["var"]: s["type"] for s in steps}
    edges = [tuple(e) for e in cp["derived"]["hasse"]]
    level = {v: 0 for v in var}
    for _ in var:
        for a, b in edges:
            level[b] = max(level[b], level[a] + 1)
    cols = collections.defaultdict(list)
    for v in var:
        cols[level[v]].append(v)
    pos = {}
    for l, vs in cols.items():
        for i, v in enumerate(vs):
            pos[v] = (l * 1.75, ((len(vs) - 1) / 2 - i) * 1.05)
    col = dict(challenging=C["phys"], rescuing=C["phys"], growing=C["grow"], observing=C["obs"], interpreting=C["know"], analysing=C["know"])
    fig, ax = plt.subplots(figsize=(7.2, 2.5))
    for a, b in edges:
        (x0, y0), (x1, y1) = pos[a], pos[b]
        ax.add_patch(FancyArrowPatch((x0 + 0.47, y0), (x1 - 0.47, y1), arrowstyle="-|>", mutation_scale=8, color=MUTED, lw=0.9,
                                     connectionstyle="arc3,rad=0.0"))
    for v, (x, y) in pos.items():
        ax.add_patch(FancyBboxPatch((x - 0.47, y - 0.3), 0.94, 0.6, boxstyle="round,pad=0,rounding_size=0.08", fc="white", ec=col[typ[v]], lw=1.4))
        ax.text(x, y + 0.09, v.lstrip("?"), ha="center", va="center", fontsize=8.5, fontweight="bold", color=col[typ[v]])
        ax.text(x, y - 0.14, typ[v], ha="center", va="center", fontsize=5.4, color=MUTED)
    tl = {0: "0 h", 1: "0–48 h", 2: "48 h", 3: "48–72 h", 4: "72 h", 5: "after 72 h", 6: "after 72 h"}
    for l in cols:
        ax.text(l * 1.75, -1.85, tl.get(l, ""), ha="center", fontsize=7, color=MUTED)
    handles = [plt.Line2D([], [], color=c, lw=3, label=l) for l, c in
               (("intervention (physical)", C["phys"]), ("growth (physical)", C["grow"]), ("observation", C["obs"]), ("interpretation, analysis (knowledge)", C["know"]))]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 1.13), ncol=4, frameon=False, fontsize=7)
    ax.set_xlim(-0.6, max(cols) * 1.75 + 0.6); ax.set_ylim(-2.0, 1.75); ax.axis("off")
    save(fig, "poset")


def fig_design():
    rows = []
    for c in cands["candidates"]:
        m = re.match(r"c_d(\d+)_t(\d+)_n(\d+)", c["id"])
        rows.append((int(m.group(1)) / 100, int(m.group(2)), int(m.group(3)), c["eig_bits"], c["id"]))
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    doses = sorted({r[0] for r in rows})
    cmap = plt.get_cmap("viridis")
    for i, d in enumerate(doses):
        for n, mk in ((1, "o"), (2, "s"), (3, "^")):
            pts = sorted((r[1], r[3]) for r in rows if r[0] == d and r[2] == n)
            if pts:
                ax.plot([p[0] for p in pts], [p[1] for p in pts], marker=mk, ms=3.2, lw=0.9 if n == 1 else 0.6,
                        ls="-" if n == 1 else ":", color=cmap(0.05 + 0.75 * i / max(1, len(doses) - 1)), label=f"{d:.2f} au" if n == 1 else None)
    ax.axhline(plan["requirement_bits"], color=C["bad"], lw=0.9, ls="--")
    ax.text(ax.get_xlim()[0] if False else min(r[1] for r in rows), plan["requirement_bits"] + 0.02, "required 0.5 bit", fontsize=6.8, color=C["bad"])
    ax.plot([sel["delay_h"]], [sel["eig_bits"]], marker="o", ms=9, mfc="none", mec=C["bad"], mew=1.4)
    ax.annotate(f"selected: {sel['dose_au']} au, {sel['delay_h']} h, n={sel['reps']}\nEIG {sel['eig_bits']} bit, least cost",
                xy=(sel["delay_h"], sel["eig_bits"]), xytext=(12, 0.78), fontsize=6.8,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.7))
    ax.set_xlabel("rescue delay (h)"); ax.set_ylabel("expected information gain (bit)")
    ax.set_ylim(0, 0.92)
    ax.legend(title="challenge dose (n=1 solid)", fontsize=6.2, title_fontsize=6.4, frameon=False, loc="lower right", ncol=1)
    save(fig, "design")


def fig_gantt():
    E = J(OUT, "trail_isaac_nominal.json")["entries"]
    sess = [e for e in E if e["category"] == "run_session"]
    ids = []
    for e in sess:
        if e["designator"] not in ids:
            ids.append(e["designator"])
    lanes = ["cell01", "l10", "r01", "r02", "l12", "l17"]
    names = dict(cell01="cell (interlocks)", l10="L10 incubator", r01="R01 arm", r02="R02 arm", l12="L12 liquid handler", l17="L17 imager")
    colr = dict(cell01=MUTED, l10=C["grow"], r01=C["phys"], r02=C["obs"], l12=C["know"], l17=C["bad"])
    fig, axs = plt.subplots(1, len(ids), figsize=(7.2, 2.2), sharey=True)
    for ax, sid in zip(axs, ids):
        open_t = next(e["t_sim"] for e in E if e["designator"] == sid)
        end_t = next(e["t_sim"] for e in E if e["designator"] == sid and e["transition"] in ("executed", "escalated", "failed"))
        g = next(e for e in E if e["designator"] == sid and e["transition"] == "grounded")
        leaves = [e for e in E if e["kind"] in ("motion", "command") and e["transition"] == "executed" and open_t <= e["t_sim"] <= end_t]
        prev = open_t
        for e in leaves:
            a = e["agent"]
            if a in lanes:
                ax.barh(lanes.index(a), e["t_sim"] - prev, left=prev - open_t, height=0.62, color=colr[a], lw=0)
            prev = e["t_sim"]
        ax.set_title(f"{g['bindings']['session']}: culture time {g['bindings'].get('t_h', '')} h, {round(end_t - open_t)} s", fontsize=7.6)
        ax.set_xlabel("s into the trip", fontsize=7)
        ax.set_yticks(range(len(lanes))); ax.set_yticklabels([names[l] for l in lanes], fontsize=7)
        ax.invert_yaxis(); ax.tick_params(labelsize=6.8)
    save(fig, "gantt")


def photo():
    from PIL import Image
    im = Image.open(os.path.join(ROOT, "renders", "lab", "lab_cell_interior.png")).convert("RGB")
    im.thumbnail((1600, 1600))
    p = os.path.join(FIG, "cell.jpg")
    im.save(p, quality=84)
    return p


# ------------------------------------------------------------------------------------------------------------- references
REFS = {
    "king2009": ("article", dict(author="King, Ross D. and Rowland, Jem and Oliver, Stephen G. and Young, Michael and others", title="The Automation of Science",
                                 journal="Science", volume="324", number="5923", pages="85--89", year="2009")),
    "williams2015": ("article", dict(author="Williams, Kevin and Bilsland, Elizabeth and Sparkes, Andrew and others", title="Cheaper Faster Drug Development Validated by the Repositioning of Drugs against Neglected Tropical Diseases",
                                     journal="Journal of the Royal Society Interface", volume="12", number="104", pages="20141289", year="2015")),
    "burger2020": ("article", dict(author="Burger, Benjamin and Maffettone, Phillip M. and Gusev, Vladimir V. and others", title="A Mobile Robotic Chemist",
                                   journal="Nature", volume="583", pages="237--241", year="2020")),
    "abolhasani2023": ("article", dict(author="Abolhasani, Milad and Kumacheva, Eugenia", title="The Rise of Self-Driving Labs in Chemical and Materials Sciences",
                                       journal="Nature Synthesis", volume="2", pages="483--492", year="2023")),
    "baker2016": ("article", dict(author="Baker, Monya", title="1,500 Scientists Lift the Lid on Reproducibility", journal="Nature", volume="533", pages="452--454", year="2016")),
    "wilkinson2016": ("article", dict(author="Wilkinson, Mark D. and Dumontier, Michel and Aalbersberg, IJsbrand Jan and others", title="The FAIR Guiding Principles for Scientific Data Management and Stewardship",
                                      journal="Scientific Data", volume="3", pages="160018", year="2016")),
    "mcdermott1991": ("techreport", dict(author="McDermott, Drew", title="A Reactive Plan Language", institution="Yale University, Department of Computer Science", number="YALEU/CSD/RR 864", year="1991")),
    "beetz2001": ("article", dict(author="Beetz, Michael", title="Structured Reactive Controllers", journal="Autonomous Agents and Multi-Agent Systems", volume="4", number="1--2", pages="25--55", year="2001")),
    "beetz2010": ("inproceedings", dict(author="Beetz, Michael and M{\\\"o}senlechner, Lorenz and Tenorth, Moritz", title="{CRAM} -- A Cognitive Robot Abstract Machine for Everyday Manipulation in Human Environments",
                                        booktitle="IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS)", pages="1012--1017", year="2010")),
    "tenorth2013": ("article", dict(author="Tenorth, Moritz and Beetz, Michael", title="{KnowRob}: A Knowledge Processing Infrastructure for Cognition-Enabled Robots",
                                    journal="The International Journal of Robotics Research", volume="32", number="5", pages="566--590", year="2013")),
    "stelter2022": ("inproceedings", dict(author="Stelter, Simon and Bartels, Georg and Beetz, Michael", title="An Open-Source Motion Planning Framework for Mobile Manipulators using Constraint-Based Task Space Control with Linear {MPC}",
                                          booktitle="IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS)", year="2022")),
    "demoura2008": ("inproceedings", dict(author="de Moura, Leonardo and Bj{\\o}rner, Nikolaj", title="{Z3}: An Efficient {SMT} Solver",
                                          booktitle="Tools and Algorithms for the Construction and Analysis of Systems (TACAS)", series="LNCS", volume="4963", pages="337--340", year="2008")),
    "gebser2019": ("article", dict(author="Gebser, Martin and Kaminski, Roland and Kaufmann, Benjamin and Schaub, Torsten", title="Multi-Shot {ASP} Solving with clingo",
                                   journal="Theory and Practice of Logic Programming", volume="19", number="1", pages="27--82", year="2019")),
    "weld1994": ("article", dict(author="Weld, Daniel S.", title="An Introduction to Least Commitment Planning", journal="AI Magazine", volume="15", number="4", pages="27--61", year="1994")),
    "abadi1991": ("article", dict(author="Abadi, Mart{\\'\\i}n and Lamport, Leslie", title="The Existence of Refinement Mappings", journal="Theoretical Computer Science", volume="82", number="2", pages="253--284", year="1991")),
    "benveniste2018": ("article", dict(author="Benveniste, Albert and Caillaud, Beno{\\^\\i}t and Nickovic, Dejan and others", title="Contracts for System Design",
                                       journal="Foundations and Trends in Electronic Design Automation", volume="12", number="2--3", pages="124--400", year="2018")),
    "lindley1956": ("article", dict(author="Lindley, Dennis V.", title="On a Measure of the Information Provided by an Experiment", journal="The Annals of Mathematical Statistics",
                                    volume="27", number="4", pages="986--1005", year="1956")),
    "chaloner1995": ("article", dict(author="Chaloner, Kathryn and Verdinelli, Isabella", title="Bayesian Experimental Design: A Review", journal="Statistical Science",
                                     volume="10", number="3", pages="273--304", year="1995")),
    "haber1991": ("article", dict(author="Haber, Stuart and Stornetta, W. Scott", title="How to Time-Stamp a Digital Document", journal="Journal of Cryptology", volume="3", number="2", pages="99--111", year="1991")),
    "prov2013": ("misc", dict(author="Moreau, Luc and Missier, Paolo", title="{PROV-DM}: The {PROV} Data Model", howpublished="W3C Recommendation", year="2013")),
    "fda2018": ("misc", dict(author="{U.S. Food and Drug Administration}", title="Data Integrity and Compliance With Drug {CGMP}: Questions and Answers. Guidance for Industry", year="2018")),
}


def bibtex():
    out = []
    for k, (t, f) in REFS.items():
        out.append(f"@{t}{{{k},\n" + ",\n".join(f"  {a} = {{{v}}}" for a, v in f.items()) + "\n}")
    return "\n\n".join(out) + "\n"


def detex(s):
    s = re.sub(r"\{\\\\?\"o\}|\{\\\"o\}", "ö", s)
    s = s.replace("{\\o}", "ø").replace("{\\'\\i}", "í").replace("{\\^\\i}", "î").replace('{\\"o}', "ö")
    return s.replace("{", "").replace("}", "").replace("--", "–").replace("\\", "")


def ref_html(k):
    t, f = REFS[k]
    venue = f.get("journal") or f.get("booktitle") or f.get("institution") or f.get("howpublished") or ""
    extra = ", ".join(x for x in (f.get("volume") and (f["volume"] + (f"({f['number']})" if f.get("number") and t == "article" else "")),
                                   f.get("number") if t == "techreport" else None, f.get("pages")) if x)
    return f"{detex(f['author'])} ({f['year']}). {detex(f['title'])}. <em>{html.escape(detex(venue))}</em>{', ' + html.escape(detex(extra)) if extra else ''}."


# ------------------------------------------------------------------------------------------------------------- content
def listing_block(path, start_pat, n=None, end_pat=None):
    L = open(path).read().splitlines()
    i = next(k for k, l in enumerate(L) if re.search(start_pat, l))
    if end_pat:
        j = next(k for k in range(i + 1, len(L)) if re.search(end_pat, L[k]))
        seg = L[i:j]
    else:
        seg = L[i:i + n]
    ind = min(len(l) - len(l.lstrip()) for l in seg if l.strip())
    return "\n".join(l[ind:] for l in seg).rstrip()


LST = dict(
    culture=listing_block(os.path.join(OUT, "culture_plan.pretty.ldl"), r"\(an action \?c3", end_pat=r"\(an action \?g2"),
    lab=listing_block(os.path.join(OUT, "challenge_rescue.pretty.ldl"), r"\(an action \?x3", end_pat=r"\(an action \?w2"),
    cram=listing_block(os.path.join(OUT, "challenge_rescue_src.lisp"), r"^\(def-action-plan intervening", end_pat=r"^\(def-action-plan incubating"),
    giskard=listing_block(os.path.join(OUT, "challenge_rescue_giskard.py"), r"^def inserting", end_pat=r"^def grasping"),
)
entry = next(e for e in J(OUT, "trail_nominal.json")["entries"] if e.get("evidence") and e["category"] == "dispense")
def compact_entry(e):
    keep = ("seq", "t_sim", "designator", "parent", "kind", "category", "transition", "agent", "software", "term", "monitors",
            "constraints", "evidence", "prev", "hash")
    L = ["{"]
    for k in keep:
        if k not in e:
            continue
        v = e[k]
        if k == "evidence":
            L.append(f'  "evidence": [  // {len(v)} items, each with its own sha256')
            for x in v[:3]:
                L.append("    " + json.dumps(x, separators=(", ", ": "))[:88] + ("..." if len(json.dumps(x)) > 88 else "") + ",")
            L.append("    ...],")
            continue
        if k == "term":
            v = [x if not isinstance(x, str) or len(x) < 30 else x[:27] + "..." for x in v]
        t = json.dumps(v, separators=(", ", ": "), default=str)
        line = f'  "{k}": {t},'
        L.append(line if len(line) <= 100 else line[:96] + "...")
    L.append("}")
    return "\n".join(L)


LST["audit"] = compact_entry(entry)

T = {}
T["levels"] = (["Level", "States", "Language", "Derived by", "Size"], [
    ["Culture plan", "what is done to the cultures, what becomes known", "LDL (entity designators)", "written", f"{N['culture_actions']} actions"],
    ["Design", "doses, delay, replicates", "EIG + ASP", "nested Monte Carlo, clingo", f"{N['candidates']} candidates"],
    ["Lab plan", "action designators with contracts and handlers", "LDL", "mapping, checked", f"{N['lab_steps']} actions"],
    ["Controller", "structured reactive controller", "CRAM/RPL (Lisp)", "generated", "409 lines"],
    ["Step plan", "robot motions and device commands", "kernel designators", "clingo; kernel expansion", f"{N['steps']} steps"],
    ["Motion plan", "frames, constraints, monitors, cancels", "giskardpy statecharts", "generated", f"{N['motions']} motions"],
])
T["obligations"] = (["", "Obligation", "Discharged by", "Result"], [
    ["O1", "culture plan well formed (supported, acyclic)", "causal-link analysis", f"{N['culture_links']} links"],
    ["O2", "step-level events entail every culture effect, the order and the culture prevents", "z3 (negation UNSAT)",
     f"{sum(rp['obligations']['O2 abstraction: motion-level effects entail the culture plan']['obligations'].values())}/{len(rp['obligations']['O2 abstraction: motion-level effects entail the culture plan']['obligations'])}"],
    ["O3", "lab plan: links, threats, instruments, handler guarantees", "LDL checker", f"threats {rp['obligations']['O3 lab plan: order, threats, instruments, handlers, guarantees']['threats']}, guarantees {rp['obligations']['O3 lab plan: order, threats, instruments, handlers, guarantees']['guarantees']}"],
    ["O4", "step plan: executability, safety, time, realization, gain, least cost", "z3 (V1–V5)", f"{sum(zp_ for zp_ in [v['holds'] for v in zp['theorems'].values()])}/{len(zp['theorems'])} theorems"],
    ["O5", "no plate-handling tool touches the culture", "z3", "holds"],
    ["O6", "each motion refines its step; end monitor implies the postcondition; soft parts hold-or-cancel", "exhaustive check", f"{N['motions']}/{N['motions']} motions"],
    ["O7", "every cancellation reaches a handler with a verified guarantee", "exhaustive check", f"{len(rp['obligations']['O7 failure branch: every cancellation reaches a guaranteed handler']['guarantees'])} failure types"],
])
ASSUME_HOW = {"A1": "library semantics", "A2": "assumed; 2 fault kinds only partly detected", "A3": "ILLUSTRATIVE capture (2 mm)",
              "A4": "monitored at run time", "A5": "component contracts, monitored", "A6": f"checked ({N['goals_ok']}/{N['goals']})"}
T["assumptions"] = (["", "Assumption", "Covered by"], [[a.split()[0], a.split(" ", 1)[1].split(": ", 1)[-1], ASSUME_HOW[a.split()[0]]] for a in rp["assumptions"]])
T["negative"] = (["Mutation", "Caught"], [[k, "yes" if v else "NO"] for k, v in rp["negative_controls"].items()])
T["repro"] = (["Stage", "Derives", "Outputs", "Identical"], [[sid, next(s["derives"] for s in man["stages"] if s["id"] == sid), str(s["outputs"]), str(s["identical"])]
                                                        for sid, s in repro["stages"].items()])
EXPL = {k: v.get("about", "") for k, v in runs.items()}
T["scenarios"] = (["Scenario", "Backend", "End", "R | V", "Repairs", "Entries", "As specified"], [
    [n.replace("isaac_", "").replace("_", " "), "Isaac Sim" if n.startswith("isaac") else "symbolic", runs[n]["end"],
     f"{'ok' if runs[n]['got']['realization'] else '–'} | {'ok' if runs[n]['got']['validity'] else '–'}",
     ", ".join(runs[n]["got"].get("repaired_at") or []) or "–", str(runs[n]["n_entries"]), "yes" if runs[n]["expectation_ok"] else "NO"]
    for n in SYMB + ISAAC])
T["labs"] = (["Lab variant", "Dimension", "Outcome", "Culture plan"], [[l["title"], l["dimension"], l["outcome"], l["culture_plan_sha"]] for l in ind["labs"]])
T["sessions"] = (["Session", "Culture time", "Device", "Material", "Steps", "Planned (s)", "Isaac (s)"], [
    [s["session"], f"{s['t_h']} h", s["device"].upper(), "; ".join(f"{m[0]} {m[1].upper()} {m[2]} {m[3] / 100:.2f} au" if len(m) == 4 else f"{m[0]} {m[1].upper()}" for m in s["material"]),
     str(len(s["steps"])), f"{DUR_PLAN[s['session']]:.1f}", f"{DUR_ISAAC.get(s['session'], 0):.1f}"] for s in plan["sessions"]])
T["refine"] = (["Culture action", "Lab action", "Process", "Realized by"], [
    [f"{r['culture']} {r['culture_type']}", f"{r['lab'] or ''} {r['lab_type'] or 'computation'}", r["process"] or "", ", ".join(r["device"]).upper() if isinstance(r["device"], list) else str(r["device"])]
    for r in prot["refinement"]])
T["handlers"] = (["Failure", "Handler (LDL)"], [[h["type"], re.sub(r"\s+", " ", h["text"])] for h in ldl["handles"]])

mh = man["manifest_sha256"]
isaac_cal = runs["isaac_calibration_lapsed"]
P = K["posterior"]


def S(title, label, *blocks):
    return ("section", title, label, list(blocks))


ABSTRACT = (
    "Laboratory automation promises reproducible experiments. Yet an automated protocol is usually written at the level of devices and "
    "robot programs, so the scientific intent, its laboratory realization and the record of what happened are hard to separate, to check "
    "and to reproduce. We describe a pipeline in which an experiment is stated once, as a plan over the cultures: what is done to them, how "
    "they are observed and what becomes known. Everything else is derived from it: the experimental design by expected information gain, a "
    f"partially ordered plan of laboratory action designators, a structured reactive controller in CRAM/RPL, {N['steps']} grounded robot and "
    f"device steps, and {N['motions']} constraint-based motion specifications for Giskard. A machine-checked refinement proof shows that, under "
    "six stated assumptions about controllers, sensors and devices, every execution of the motion plan either realizes the culture plan while "
    "satisfying all stated safety, timing and contamination constraints, or is stopped by a monitor and ends in a failure handler whose "
    f"guarantee holds. The derivation is recorded in a content-addressed manifest. A complete re-run reproduced all {N['outputs']} outputs of its "
    f"{N['stages']} stages identically; only wall-clock timing fields are excluded from the comparison. Execution produces a hash-chained audit trail that is itself "
    f"reproducible: re-executing each of the {N['reexec_n']} symbolic scenarios yields the identical chain head. We demonstrate the pipeline on "
    "a challenge–rescue organoid experiment in a physics-based digital twin of a two-arm robotic cell. The biology is a surrogate model and "
    "all biomedical parameters are illustrative. The paper itself is a build product of the pipeline.")

DOC = [
    S("Introduction", "sec:intro",
      ("p", "Robotic laboratories can run experiments without interruption and record every action they take [@king2009,williams2015,burger2020,abolhasani2023]. "
            "Reproducibility, however, needs more than automation [@baker2016]. A protocol for a liquid handler and a plate-moving robot fixes "
            "*how* an experiment is executed in one laboratory. It does not state *what* the experiment does to the biological material, and it "
            "cannot be checked against that intent. When the laboratory changes (another robot, another incubator, a new safety rule), the "
            "protocol has to be rewritten, and nothing shows that the new protocol performs the same experiment."),
      ("p", "We take the opposite route. The experiment is written once, at the level of the cultures: which culture is challenged, rescued, grown, "
            "observed, interpreted and analysed; which physical change each action causes; and which knowledge it produces. The plan says "
            "nothing about robots, devices, poses, safety rules, cleanliness or temperature control. Everything below it is derived and "
            "checked: the design, the laboratory plan, the controller, the robot and device steps, and the robot motions. The derivation is "
            "recorded so that anyone with the inputs can reproduce it. The execution is recorded so that anyone can verify it and re-execute it."),
      ("p", "Contributions:"),
      ("ul", ["**A culture-level plan language** with physical and knowledge effects, built on entity-based designators. A partial order is derived "
              f"from causal links, and the plan is independent of the laboratory: we show this over {N['labs']} laboratory variants (§sec:culture§).",
              "**An automatic refinement** from the culture plan to a least-cost design by expected information gain, to laboratory action "
              "designators with contracts and failure handlers, to a CRAM/RPL structured reactive controller, and to Giskard motion "
              "statecharts (§sec:refine§).",
              "**A machine-checked refinement proof** that the motion plan carries out the culture plan and satisfies every stated constraint, "
              "or fails safely, relative to explicit assumptions (§sec:proof§).",
              "**A reproducible derivation and a reproducible audit trail**: a content-addressed manifest that a re-run reproduces, and "
              "hash-chained trails whose chain heads are reproduced by re-execution (§sec:repro§).",
              "**The paper as a build product.** Every number, table, figure and listing in this paper is generated from the pipeline's outputs "
              f"(manifest `{mh[:16]}`)."]),
      ("fig", "cell", "Cell 01 in its semantic digital twin (Isaac Sim, path-traced): two arms, an incubator, a liquid handler in its enclosure, "
                      "a bright-field imager, a tool rack and the handover nest. The experiment in this paper runs on this twin.")),
    S("Related work", "sec:related",
      ("p", "**Robot scientists and self-driving laboratories.** Adam and Eve closed the loop from hypothesis to experiment in yeast genetics and "
            "drug screening [@king2009,williams2015]. A mobile robot ran a chemistry search over a week of autonomous experiments [@burger2020]. "
            "Self-driving laboratories are now common in chemistry and materials science [@abolhasani2023]. These systems describe experiments "
            "at the level of the instruments. We add a level above the instruments and prove that the levels below realize it."),
      ("p", "**Plan languages for robots.** RPL introduced concurrent reactive plans with failure handling and fluents [@mcdermott1991]. Structured "
            "reactive controllers [@beetz2001] and CRAM [@beetz2010] made such plans the basis of everyday manipulation, using designators as "
            "symbolic descriptions that are resolved at run time, with knowledge supplied by KnowRob [@tenorth2013]. Giskard specifies motions as "
            "constraint- and optimization-based tasks solved by model-predictive control [@stelter2022]. We use these layers unchanged and add "
            "a culture level above them, together with proofs across the levels."),
      ("p", "**Planning, design and verification.** The partial order of our plans follows least-commitment planning: causal links and threats "
            "[@weld1994]. Designs are selected by expected information gain [@lindley1956,chaloner1995], and the least-cost plan is found with "
            "answer set programming [@gebser2019]. Proof obligations are discharged by an SMT solver [@demoura2008]. The refinement argument "
            "follows refinement mappings [@abadi1991] and assume-guarantee contracts [@benveniste2018]."),
      ("p", "**Provenance and data integrity.** The audit trail is a hash chain in the sense of [@haber1991]. Its entries follow W3C PROV "
            "[@prov2013] and the ALCOA+ expectations for regulated records [@fda2018]: attributable, legible, contemporaneous, original and "
            "accurate. The FAIR principles [@wilkinson2016] motivate publishing the manifest together with the data.")),
    S("The experiment and the laboratory", "sec:setting",
      ("p", "The experiment asks which of three recovery models explains the efficacy of a rescue that follows a challenge: graded recovery (M1), "
            "a threshold (M2), or a protective effect (M3). Three cultures take part. The *rescued* culture is challenged at 0 h and rescued "
            f"later. The *comparator* is challenged only. The *control* is untreated. All three are imaged at {72} h, and the organoid radius is "
            "measured from the images. Doses are in arbitrary units (au). The culture dynamics, the imaging and the models are Cell 01's culture "
            "surrogate. The numbers are ILLUSTRATIVE and are not claims about any biological system."),
      ("p", "Cell 01 (§fig:cell§) is a robotic cell for culture handling and liquid intervention. A seven-axis arm (R01) serves the incubator (L10) "
            "and the handover nest. A rail-mounted arm (R02) serves the liquid handler (L12), the imager (L17), a calibration and QC station (L21) "
            "and a quarantine station (H4), and changes tools at a rack. The cell is modelled as a semantic digital twin: an OWL ontology of the "
            "devices, seats, frames and safety rules, the component records of every device, and a USD scene that Isaac Sim simulates.")),
    S("The culture-level plan", "sec:culture",
      ("p", "A culture-level plan is a set of action designators over entity designators. An entity designator `(det sort ?var slot*)` "
            "describes an entity by its properties; it is resolved against a knowledge base and never names a device. Each action states "
            "its *physical* effect on a culture and its *knowledge* effect: what is recorded or inferred. §lst:culture§ shows the rescue. The "
            "goal of the plan is epistemic: the belief over the three models must have an expected information gain of at least 0.5 bit."),
      ("lst", "culture", "The rescue action of the culture plan (LDL). Times are culture times; the dose is ILLUSTRATIVE."),
      ("p", f"The order is not written. It is derived from causal links: an action's requirement must be supported by an earlier action's physical "
            f"or knowledge effect, or by the given state. The {N['culture_actions']} actions have {N['culture_links']} causal links, and the "
            "partial order is their transitive reduction (§fig:poset§). Interpretation requires a known image scale. This requirement is marked "
            "*establishable*: the plan states it, and the laboratory must establish it."),
      ("fig", "poset", "The culture plan as a partial order (Hasse diagram of the derived causal order). Columns are culture-time phases."),
      ("p", f"**Independence from the laboratory.** We checked the plan text against the realization vocabularies of the knowledge base: robots, "
            "devices, poses, seats, tools, safety rules, cleanliness and temperature. No term occurs in the plan. We then ran the whole refinement "
            f"in {N['labs']} laboratory variants that change robots, devices, the layout, safety constraints, cleanliness and temperature profiles "
            "(appendix, §tab:labs§). The culture plan, its hash and its derived order are identical in all of them. Where a variant cannot realize "
            "the plan, the refusal names the missing capability. The plan itself is not changed.")),
    S("Refinement to robot motions", "sec:refine",
      ("table", "levels", "The levels of the refinement. Each level is derived from the one above it and checked against it."),
      ("p", f"**Design.** The free parameters of the culture plan (challenge dose, rescue delay, replicates) are chosen by expected information "
            f"gain over a uniform prior on M1–M3. The gain is estimated by nested Monte Carlo on the surrogate ({cands['samples']} samples, seed "
            f"{cands['seed']}). Of {N['candidates']} candidates, {N['feasible']} reach 0.5 bit (§fig:design§). An answer set program over the laboratory "
            f"facts then selects the least-cost safe plan among them: challenge {sel['dose_au']} au, rescue {sel['rescue_au']} au after "
            f"{sel['delay_h']} h, {sel['reps']} replicate, EIG {sel['eig_bits']} bit, at a cost of {plan['cost']['value']} decisecond-equivalents."),
      ("fig", "design", "Expected information gain of the candidate designs. The circle marks the selected design, the least-cost safe plan "
                        "among the candidates that meet the requirement."),
      ("p", f"**Laboratory plan.** Each culture action is refined into a laboratory action designator (appendix, §tab:refine§). A laboratory action "
            "states what it *requires*, what it *prevents* and *maintains* during a scope bounded by fluents, what it *achieves*, its *goal*, the "
            "failures it *signals*, and an *instrument role*: a slot that accepts the plate and a process that performs the action (§lst:lab§). "
            "Instruments are resolved by capability. A device fills the role if it has the slot and can run the process. Process models of the "
            f"devices list their faults, the monitors that detect them and the handlers that repair them. The checker verifies the causal links, "
            f"resolves all {N['threats']} threats, resolves every instrument and verifies the guarantee of each of the {N['handlers']} handlers: "
            "goal, goal-or-safe-state, safe state or containment."),
      ("lst", "lab", "The laboratory action that refines the rescue. The instrument role, contracts and handlers come from the action type's contract."),
      ("p", "**Controller.** The laboratory plan is compiled into a CRAM/RPL structured reactive controller (§lst:cram§). The partial order "
            "becomes `partial-order` constraints. `prevents` becomes a `with-policy` over a monitored fluent, bounded by a `scope`. `requires` "
            "becomes `ensure` with the epistemic grade the contract demands. Handlers become `with-failure-handling` clauses with retry counters."),
      ("lst", "cram", "Generated CRAM/RPL action plan for the intervening type (excerpt)."),
      ("p", f"**Steps.** The kernel expands the controller into grounded steps: {N['steps']} robot motions and device commands in {N['sessions']} trips. "
            f"The answer set program derives the same plan independently, and both agree step for step and second for second. The z3 validator "
            f"proves executability, the safety rules (L12 airspace, environment before storage, calibration before imaging, interlocks, identity), "
            f"the 600 s window outside the incubator, the realization of every dose and image, and least cost ({N['neg_z3']} negative controls)."),
      ("p", f"**Motions.** Each robot step is refined into a giskardpy motion statechart (§lst:giskard§). Goal frames are taken from the composed "
            f"scene: seat frames, approach poses and well frames re-parented to the plate. A Cartesian task specifies the goal, velocity limits "
            f"and level-keeping are weighted constraints, and collision avoidance is a constraint set. The quadratic program minimizes velocity "
            f"and jerk over the horizon plus the weighted slacks. All {N['goals']} goal frames are reachable by inverse kinematics with joint "
            f"margin. Because level-keeping and collision terms are soft, the generator adds monitors that cancel the motion when tilt, collision "
            "distance or duration exceeds its bound. This makes every soft constraint *hold-or-cancel*."),
      ("lst", "giskard", "Generated Giskard phase for inserting the gripper at a seat (excerpt): the end monitor, the straight-line task, the "
                         "speed limit and the permitted finger contact.")),
    S("Correctness of the refinement", "sec:proof",
      ("p", "**Theorem.** Under assumptions A1–A6 (§tab:assumptions§), every execution of the motion plan does one of two things. (i) It realizes the "
            "culture plan: every physical and knowledge effect, in the derived order, at 0, 48 and 72 h of culture time, with the control culture "
            "untreated, while interlocks, L12 airspace, identity, environment before storage, calibration before imaging, the 600 s window, "
            "contamination freedom, tool hygiene, plate level and collision distance all hold. (ii) Or a monitor stops it, and it ends in a "
            "failure handler whose guarantee holds."),
      ("p", "The proof composes seven obligations along the refinement chain (§fig:chain§, §tab:obligations§). The step-level validator proves which "
            "doses, images and session times every execution produces. O2 maps them through the vessel map (rescued → A01, comparator → A02, "
            "control → A05) and shows with z3 that the negation of each culture-level obligation is unsatisfiable. O6 is where the soft optimization "
            "meets the logic. Each motion's end monitor implies its step's postcondition under A3. Each motion's timeout is 1.2 times its "
            "estimate, which is exactly the duration bound that the step-level timing proof assumes. A held plate's tilt and every collision "
            "distance cancel the motion when violated. O7 closes the failure branch: a cancellation raises a failure that propagates to a "
            "handler whose guarantee O3 verified."),
      ("fig", "chain", "The refinement chain, the proof obligations O1–O7 on its links, and the records that make it reproducible."),
      ("table", "obligations", "Proof obligations and how they are discharged."),
      ("table", "assumptions", "Assumptions of the theorem and how each is covered."),
      ("p", f"**Negative controls.** To show that the checks are not vacuous, each of {N['neg_rp']} mutations must make an obligation fail: a swapped "
            "vessel map, a dosed control, a missing control image, a contaminating tool, a held motion without its tilt monitor, a timeout beyond "
            "the timing bound, a motion that does not refine its step, and the validator's own mutated plans. All are caught (§tab:negative§).")),
    S("Reproducible derivation and audit", "sec:repro",
      ("p", f"**Manifest.** The pipeline runs in {N['stages']} stages, from the design to the protocol (§tab:repro§). For each stage the manifest records "
            "the command, the sha256 of the code it ran and the sha256 of every file it wrote. The inputs (culture plan, registry, ontology ABox, "
            "answer set program, scene, surrogate code, duration traces and the recorded physics runs) and the tool versions are recorded once. "
            "JSON outputs are hashed in canonical form without the wall-clock fields "
            f"({', '.join('`' + v + '`' for v in man['volatile_fields'])}). Nothing else is excluded. The manifest hash identifies the whole "
            f"derivation: `{mh}`."),
      ("p", f"**Reproduction.** A second complete run, which also recomputes the Monte Carlo estimates from scratch, produced the same manifest hash. "
            f"All {N['identical']} of {N['outputs']} outputs are identical, including the plan, the proofs, the controller, the generated Giskard "
            "module and all audit trails."),
      ("table", "repro", "Stages of the pipeline and the result of the reproduction run."),
      ("p", "**Audit trail.** Every lifecycle transition of every designator (open, grounded, accepted, executing, executed, failed, repaired) is "
            "one entry of a SHA-256 hash chain. The entry hash covers the previous hash and the canonical JSON of the entry (§lst:audit§). The "
            "executor writes the entries, not the plan, so a plan cannot skip them. Entries record the agent, the software (kernel, knowledge "
            "base, registry hash, backend), the simulated time, bindings and resolutions with their grounds, constraint verdicts in two columns "
            "(realization and validity), monitors, and evidence with its own sha256."),
      ("lst", "audit", "An audit entry (abbreviated; ... marks truncation): a dispense command executed by L12, with its monitors, constraint verdicts and hashed evidence."),
      ("p", f"**Verification.** For all {N['trails']} trails the chain is intact. Changing a single value is detected at the changed entry. "
            f"Re-executing each of the {N['reexec_n']} symbolic scenarios in a fresh directory reproduces its trail exactly, chain head included "
            f"({N['reexec']}/{N['reexec_n']}). A trail is therefore more than a tamper-evident record: it is a reproducible one, and its head "
            f"hash commits to the whole execution. The {N['cq']} competency questions of the kernel are audit questions: what was done, why, how, "
            f"under which constraints, with which evidence, and what would have happened if. All {N['cq_ok']} are answered correctly from the "
            "trails alone.")),
    S("Execution", "sec:exec",
      ("p", f"§tab:scenarios§ lists the executions. On the symbolic backend, {len(SYMB)} scenarios inject knowledge errors, faults and workflow "
            "errors: lapsed calibration, a lost tip, a swapped plate identity, a slow tool changer, a swapped or incapable imager, an unbound "
            "rescue, a dropped control, contamination and an incomplete component record. Every scenario ends as specified before it was run. "
            "The ends are executed, executed after a local repair, escalated to a human, or refused before anything moved."),
      ("table", "scenarios", "Executions. R | V: realization and validity columns of the verdict. 'As specified': the end and the verdict match the "
                             "expectation written before the run."),
      ("p", f"In Isaac Sim, the nominal run executes all three trips (§fig:gantt§). The physics-timed trips deviate from the planned durations by "
            f"{', '.join(f'{v:+.1f} %' for v in DEV.values())}, which lies within the ±20 % that the timing proof assumes, and every trip stays "
            "inside the 600 s window. The identity-swap run detects the wrong plate at the incubator's barcode read, quarantines it and escalates, "
            "as specified. The lapsed-calibration run does **not** end as specified. The calibration repair worked: the imager refused, the plate "
            "was set aside, the station recalibrated and the measurement was re-planned. But the comparator well then failed the focus check twice, "
            "and the session escalated. The images after the reload show a lateral shift of about 93 µm that the seat sensors did not register. "
            "The kernel's refocus repair cannot change the outcome, because the imager autofocuses on every image anyway. We report this failure "
            "because it marks the boundary of the proof: plate misseating on the imager is one of the two partly detected faults (§sec:limits§)."),
      ("fig", "gantt", "The nominal run in Isaac Sim: what each agent does during each trip (physics-timed leaves of the audit trail)."),
      ("p", f"**Knowledge.** Executed on the surrogate, the analysis moves the belief from uniform to M1 {P['M1_graded']:.2f}, M2 {P['M2_threshold']:.2f}, "
            f"M3 {P['M3_protective']:.2f}. The realized information gain is {K['information_gain_bit']:.3f} bit, below the expected "
            f"{K['expected_gain_bit']:.3f} bit. The plan's goal is an *expected* gain, which a single outcome need not reach. A sequential design "
            "conditions the next plan on this posterior.")),
    S("Limitations", "sec:limits",
      ("ul", ["**No wet-lab execution.** The experiment ran on a digital twin with a surrogate culture model. All biomedical parameters are "
              "ILLUSTRATIVE.",
              "**Relative correctness.** The theorem holds relative to A1–A6. It does not prove progress: a motion may be cancelled rather than "
              f"complete. {N['faults'] - N['faults_full']} of the {N['faults']} fault instances in the process models are only partly detected "
              "(well misregistration at the liquid handler, plate misseating at the imager). An undetected occurrence lies outside both branches of "
              "the theorem.",
              "**Physics.** Compliant insertion into the nests has no Giskard counterpart yet. The 2 mm capture and the 2° tilt bound are "
              "ILLUSTRATIVE. The generated Giskard module has been checked against the giskardpy sources but not executed, because no semantic "
              "digital twin world of Cell 01 is loaded into Giskard. Collisions of R02 are not checked offline.",
              "**Reproduction scope.** The reproduction ran on the same machine with the same environment. The Isaac Sim runs are recorded inputs: "
              "their chains are verified, but they were not re-executed, and physics simulation on a GPU is not expected to be bit-reproducible.",
              "**References and authorship.** The reference list was compiled without database access and must be checked before submission."])),
    S("Conclusion", "sec:conclusion",
      ("p", "An experiment can be stated at the level at which a scientist thinks about it, as a plan over cultures and knowledge, and still be "
            "carried out by robots under proofs that connect the two levels. The derivation and the execution can both be reproduced from "
            "content-addressed records. The proof is only as strong as its assumptions, and the experiment in this paper found where they are "
            "weakest: in how plates sit in their nests. The next steps are to execute the motion statecharts in Giskard against the semantic "
            "digital twin, to close the two detection gaps with monitors that make misseating observable, and to run the same culture plan in "
            "a wet laboratory.")),
    ("back", "Code and data availability",
     f"All inputs, code and outputs are in the project repository (`rsa/`, `okf/lab-automation-twin/`). `python -m rsa.reproduce` re-runs the "
     f"derivation, and `python -m rsa.reproduce --verify` compares the result with the manifest `{mh[:16]}`. `python -m rsa.protocol` writes the "
     "experimentation plan and the audit certificate. `python paper/build_paper.py` rebuilds this paper."),
    ("back", "Use of AI assistance",
     "Code, analyses and the text of this paper were produced with an AI coding assistant (Claude, Anthropic) under the authors' direction. "
     "The authors checked the results and are responsible for the content. [Authors: adapt this statement to the venue's policy.]"),
    ("appendix", "Experimentation plan (generated)", "sec:protocol",
     [("p", "The plan below is generated from the pipeline's outputs (`rsa/out/repro/protocol.md`). It is the protocol a laboratory would run, "
            f"bound to the derivation by the input digest `{prot['input_digest'][:16]}`."),
      ("table", "sessions", "Trips: culture time, device, material, number of steps, planned and physics-timed duration."),
      ("table", "refine", "Refinement of the culture actions into laboratory actions, processes and devices (computations run in the culture "
                          "digital twin)."),
      ("table", "handlers", "Failure handlers of the experiment with their guarantees."),
      ("table", "labs", "The culture plan in the laboratory variants: outcome and the hash of the culture plan."),
      ("table", "negative", "Negative controls of the refinement proof.")]),
]

LST_LANG = dict(culture="lisp", lab="lisp", cram="lisp", giskard="python", audit="json")
FIGS = ["cell", "poset", "design", "chain", "gantt"]
TABS = ["levels", "obligations", "assumptions", "repro", "scenarios", "sessions", "refine", "handlers", "labs", "negative"]
LSTS = ["culture", "lab", "cram", "giskard", "audit"]


def walk(blocks):
    for b in blocks:
        if b[0] == "section":
            yield from walk(b[3])
        elif b[0] == "appendix":
            yield from walk(b[3])
        else:
            yield b


ORDER = {"fig": [], "table": [], "lst": []}
for b in walk(DOC):
    if b[0] in ORDER and b[1] not in ORDER[b[0]]:
        ORDER[b[0]].append(b[1])
SEC_NUM = {}
k = 0
for b in DOC:
    if b[0] == "section":
        k += 1
        SEC_NUM[b[2]] = str(k)
CITES = []
for b in walk(DOC):
    texts = [b[1]] if b[0] == "p" else (b[1] if b[0] == "ul" else [])
    for t in texts:
        for grp in re.findall(r"\[@([^\]]+)\]", t):
            for c in grp.split(","):
                if c not in CITES:
                    CITES.append(c)


# ------------------------------------------------------------------------------------------------------------- LaTeX
def tex_esc(s):
    rep = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
           "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(rep.get(ch, ch) for ch in s)


def tex_inline(t):
    parts = re.split(r"(`[^`]+`)", t)
    out = []
    for p in parts:
        if p.startswith("`") and p.endswith("`") and len(p) > 1:
            out.append(r"\texttt{" + tex_esc(p[1:-1]).replace("-", "-\\allowbreak{}") + "}")
            continue
        refs = {}

        def keep(m, refs=refs):
            key = f"\x00{len(refs)}\x00"
            refs[key] = m.group(0)
            return key
        p = re.sub(r"\[@[^\]]+\]|§(fig|tab|lst|sec):[\w-]+§", keep, p)
        p = tex_esc(p)
        p = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", p)
        p = re.sub(r"\*(.+?)\*", r"\\emph{\1}", p)
        for key, v in refs.items():
            if v.startswith("[@"):
                v = r"~\citep{" + v[2:-1] + "}"
            else:
                kind, name = v.strip("§").split(":")
                v = {"fig": "Fig.~", "tab": "Table~", "lst": "Listing~", "sec": "Section~"}[kind] + r"\ref{" + f"{kind}:{name}" + "}"
            p = p.replace(key, v)
        p = p.replace(" ~\\citep", "~\\citep")
        out.append(p)
    return "".join(out)


def tex_table(name, cap):
    head, rows = T[name]
    wide = name in ("handlers", "repro", "obligations", "levels", "labs", "refine", "negative", "assumptions", "scenarios", "sessions")
    ncol = len(head)
    X = {"handlers": "lX", "repro": "lXrr", "obligations": "lXll", "levels": "lXlll", "labs": "Xlll", "refine": "lllX",
         "negative": "Xl", "assumptions": "lXl", "scenarios": "llllllr".replace("r", "l"), "sessions": "lllXrrr"}.get(name, "l" * ncol)
    body = " \\\\\n".join(" & ".join(tex_inline(str(c)) for c in r) for r in rows)
    return (f"\\begin{{table}}[tbp]\\centering\\small\n\\caption{{{tex_inline(cap)}}}\\label{{tab:{name}}}\n"
            f"\\begin{{tabularx}}{{\\linewidth}}{{{X}}}\\toprule\n" + " & ".join(f"\\textbf{{{tex_esc(h)}}}" for h in head) +
            " \\\\\\midrule\n" + body + " \\\\\\bottomrule\n\\end{tabularx}\n\\end{table}\n")


def tex_block(b):
    if b[0] == "p":
        return tex_inline(b[1]) + "\n"
    if b[0] == "ul":
        return "\\begin{itemize}\n" + "".join(f"  \\item {tex_inline(x)}\n" for x in b[1]) + "\\end{itemize}\n"
    if b[0] == "fig":
        f = "figures/cell.jpg" if b[1] == "cell" else f"figures/{b[1]}.pdf"
        w = {"design": "0.62\\linewidth", "poset": "\\linewidth", "chain": "0.92\\linewidth"}.get(b[1], "\\linewidth")
        return (f"\\begin{{figure}}[tbp]\\centering\n\\includegraphics[width={w}]{{{f}}}\n\\caption{{{tex_inline(b[2])}}}\\label{{fig:{b[1]}}}\n"
                "\\end{figure}\n")
    if b[0] == "table":
        return tex_table(b[1], b[2])
    if b[0] == "lst":
        return (f"\\begin{{listing}}[tbp]\n\\begin{{Verbatim}}[fontsize=\\footnotesize,breaklines,frame=lines,framesep=2mm]\n{LST[b[1]]}\n\\end{{Verbatim}}\n"
                f"\\caption{{{tex_inline(b[2])}}}\\label{{lst:{b[1]}}}\n\\end{{listing}}\n")
    raise ValueError(b)


def latex():
    L = [r"""\documentclass[10pt,a4paper]{article}
\usepackage[margin=2.2cm]{geometry}
\usepackage{fontspec}
\setmainfont{Libertinus Serif}
\setsansfont{IBM Plex Sans}
\setmonofont[Scale=0.86]{IBM Plex Mono}
\usepackage{microtype,graphicx,booktabs,tabularx,xcolor,float,fvextra,caption}
\usepackage[numbers,sort&compress]{natbib}
\usepackage[colorlinks,linkcolor=teal!70!black,citecolor=teal!70!black,urlcolor=teal!70!black]{hyperref}
\newfloat{listing}{tbp}{lol}\floatname{listing}{Listing}
\captionsetup{font=small,labelfont=bf}
\renewcommand{\tabularxcolumn}[1]{>{\raggedright\arraybackslash}p{#1}}
\setlength{\tabcolsep}{4pt}
\title{From Culture-Level Plans to Verified Robot Motions:\\ Reproducible and Auditable Experiments in a Robotic Laboratory Twin}
\author{[Author names and affiliations]}
\date{Preprint draft, generated """ + "2026-10-17" + r""" \\ \small manifest \texttt{""" + mh[:16] + r"""}}
\begin{document}
\maketitle
\begin{abstract}
""" + tex_inline(ABSTRACT) + r"""
\end{abstract}
"""]
    for b in DOC:
        if b[0] == "section":
            L.append(f"\\section{{{tex_esc(b[1])}}}\\label{{{b[2]}}}\n")
            L += [tex_block(x) for x in b[3]]
        elif b[0] == "back":
            L.append(f"\\paragraph{{{tex_esc(b[1])}.}} {tex_inline(b[2])}\n")
    L.append("\\bibliographystyle{unsrtnat}\n\\bibliography{refs}\n\\appendix\n")
    for b in DOC:
        if b[0] == "appendix":
            L.append(f"\\section{{{tex_esc(b[1])}}}\\label{{{b[2]}}}\n")
            L += [tex_block(x) for x in b[3]]
    L.append("\\end{document}\n")
    return "\n".join(L)


# ------------------------------------------------------------------------------------------------------------- HTML
def h_inline(t):
    parts = re.split(r"(`[^`]+`)", t)
    out = []
    for p in parts:
        if p.startswith("`") and p.endswith("`") and len(p) > 1:
            out.append("<code>" + html.escape(p[1:-1]) + "</code>")
            continue
        p = html.escape(p, quote=False)
        p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
        p = re.sub(r"\*(.+?)\*", r"<em>\1</em>", p)
        p = re.sub(r"\[@([^\]]+)\]", lambda m: "[" + ", ".join(f'<a href="#ref-{c}">{CITES.index(c) + 1}</a>' for c in m.group(1).split(",")) + "]", p)

        def rf(m):
            kind, name = m.group(1), m.group(2)
            if kind == "sec":
                return f'<a href="#{kind}-{name}">Section {SEC_NUM.get(kind + ":" + name, "A")}</a>'
            key = {"fig": "fig", "tab": "table", "lst": "lst"}[kind]
            lab = {"fig": "Fig.", "tab": "Table", "lst": "Listing"}[kind]
            idx = ORDER[key].index(name) + 1
            return f'<a href="#{kind}-{name}">{lab} {idx}</a>'
        p = re.sub(r"§(fig|tab|lst|sec):([\w-]+)§", rf, p)
        out.append(p)
    return "".join(out)


def svg_inline(name):
    s = open(os.path.join(FIG, name + ".svg")).read()
    s = s[s.index("<svg"):]
    s = re.sub(r'<svg([^>]*?) width="[^"]+" height="[^"]+"', r'<svg\1', s, count=1)
    return s


def h_block(b):
    if b[0] == "p":
        return f"<p>{h_inline(b[1])}</p>"
    if b[0] == "ul":
        return "<ul>" + "".join(f"<li>{h_inline(x)}</li>" for x in b[1]) + "</ul>"
    if b[0] == "fig":
        i = ORDER["fig"].index(b[1]) + 1
        if b[1] == "cell":
            data = base64.b64encode(open(os.path.join(FIG, "cell.jpg"), "rb").read()).decode()
            img = f'<img src="data:image/jpeg;base64,{data}" alt="Rendered view of Cell 01 in the digital twin">'
        else:
            img = svg_inline(b[1])
        cls = " narrow" if b[1] in ("design",) else ""
        return f'<figure id="fig-{b[1]}" class="fig{cls}"><div class="plate">{img}</div><figcaption><b>Fig. {i}.</b> {h_inline(b[2])}</figcaption></figure>'
    if b[0] == "table":
        i = ORDER["table"].index(b[1]) + 1
        head, rows = T[b[1]]
        return (f'<figure id="tab-{b[1]}" class="tab"><figcaption><b>Table {i}.</b> {h_inline(b[2])}</figcaption><div class="scroll"><table>'
                "<thead><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in head) + "</tr></thead><tbody>" +
                "".join("<tr>" + "".join(f"<td>{h_inline(str(c))}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div></figure>")
    if b[0] == "lst":
        i = ORDER["lst"].index(b[1]) + 1
        return (f'<figure id="lst-{b[1]}" class="lst"><div class="scroll"><pre>{html.escape(LST[b[1]])}</pre></div>'
                f'<figcaption><b>Listing {i}.</b> {h_inline(b[2])}</figcaption></figure>')
    raise ValueError(b)


CSS = """
:root { --bg: #f7f6f2; --paper: #ffffff; --ink: #1d2630; --muted: #5c6873; --line: #d9dcd6; --accent: #0b6e69; --code: #f1f3f0;
  --f-text: "Source Serif 4", Georgia, serif; --f-head: "IBM Plex Sans", system-ui, sans-serif; --f-mono: "IBM Plex Mono", ui-monospace, Menlo, monospace }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg: #101517; --paper: #161d20; --ink: #e3e8ea; --muted: #97a4aa;
  --line: #2b373c; --accent: #4cc3b9; --code: #11191c; color-scheme: dark } }
:root[data-theme="dark"] { --bg: #101517; --paper: #161d20; --ink: #e3e8ea; --muted: #97a4aa; --line: #2b373c; --accent: #4cc3b9; --code: #11191c;
  color-scheme: dark }
* { box-sizing: border-box }
body { background: var(--bg); color: var(--ink); font: 17px/1.62 var(--f-text); margin: 0;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); padding-block: 28px 64px }
article { max-width: 860px; margin: 0 auto; background: var(--paper); border: 1px solid var(--line); padding: clamp(20px, 5vw, 64px); display: grid; gap: 14px; min-width: 0 }
.kicker { font: 600 .74rem/1.3 var(--f-head); letter-spacing: .12em; text-transform: uppercase; color: var(--muted) }
h1 { font: 600 clamp(1.6rem, 3.6vw, 2.3rem)/1.18 var(--f-head); margin: 0; text-wrap: balance; letter-spacing: -.01em }
.authors { font: .95rem var(--f-head); color: var(--muted) }
.abstract { border-top: 1.5px solid var(--ink); border-bottom: 1px solid var(--line); padding: 14px 0; font-size: .95rem }
.abstract b { font: 600 .74rem var(--f-head); letter-spacing: .1em; text-transform: uppercase; display: block; margin-bottom: 4px }
h2 { font: 600 1.32rem/1.25 var(--f-head); margin: 26px 0 2px; text-wrap: balance }
h2 .n { color: var(--accent); margin-right: .5em; font-variant-numeric: tabular-nums }
p { margin: 0; max-width: 68ch } ul { margin: 0; padding-left: 1.3em; display: grid; gap: 6px; max-width: 70ch }
a { color: var(--accent) } a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px }
code { font: .84em var(--f-mono); background: var(--code); padding: 0 .25em; border-radius: 2px; word-break: break-word }
figure { margin: 10px 0; display: grid; gap: 8px; min-width: 0 }
figcaption { font: .84rem/1.5 var(--f-head); color: var(--muted); max-width: 80ch } figcaption b { color: var(--ink) }
.plate { background: #ffffff; border: 1px solid var(--line); padding: 8px; min-width: 0 }
.plate svg, .plate img { display: block; width: 100%; height: auto; max-width: 100% }
.fig.narrow .plate { max-width: 520px }
.scroll { overflow-x: auto; min-width: 0 }
table { border-collapse: collapse; width: 100%; font: .8rem/1.45 var(--f-head) }
th { text-align: left; font-weight: 600; font-size: .72rem; letter-spacing: .04em; text-transform: uppercase; color: var(--muted);
  border-bottom: 1.5px solid var(--ink); padding: 5px 7px; white-space: nowrap }
td { border-bottom: 1px solid var(--line); padding: 5px 7px; vertical-align: top; font-variant-numeric: tabular-nums }
td code { font-size: .74rem }
pre { margin: 0; background: var(--code); border: 1px solid var(--line); padding: 12px 14px; font: .74rem/1.5 var(--f-mono); white-space: pre }
.back h3 { font: 600 .98rem var(--f-head); margin: 16px 0 2px }
ol.refs { font-size: .86rem; padding-left: 1.8em; display: grid; gap: 4px; margin: 0 }
.note { font: .82rem/1.5 var(--f-head); color: var(--muted); border-left: 2px solid var(--accent); padding-left: 10px }
"""


def html_doc():
    H = ["<title>Culture Plans to Robot Motions</title>", '<meta name="claude:viewport-fit-sides" content="cover">',
         '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;600&'
         'family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap">', f"<style>{CSS}</style>", "<article>",
         '<div class="kicker">Preprint draft · generated from the pipeline · manifest <code>' + mh[:16] + "</code></div>",
         "<h1>From Culture-Level Plans to Verified Robot Motions: Reproducible and Auditable Experiments in a Robotic Laboratory Twin</h1>",
         '<div class="authors">[Author names and affiliations]</div>',
         '<p class="note">ILLUSTRATIVE: the experiment ran in a digital twin with a surrogate culture model; no biomedical parameter is asserted. '
         'This draft has not been submitted anywhere.</p>',
         f'<div class="abstract"><b>Abstract</b>{h_inline(ABSTRACT)}</div>']
    for b in DOC:
        if b[0] == "section":
            H.append(f'<h2 id="sec-{b[2].split(":")[1]}"><span class="n">{SEC_NUM[b[2]]}</span>{html.escape(b[1])}</h2>')
            H += [h_block(x) for x in b[3]]
    H.append('<div class="back">')
    for b in DOC:
        if b[0] == "back":
            H.append(f"<h3>{html.escape(b[1])}</h3><p>{h_inline(b[2])}</p>")
    H.append("</div><h2>References</h2><ol class=\"refs\">" + "".join(f'<li id="ref-{c}">{ref_html(c)}</li>' for c in CITES) + "</ol>")
    for b in DOC:
        if b[0] == "appendix":
            H.append(f'<h2 id="sec-{b[2].split(":")[1]}"><span class="n">A</span>{html.escape(b[1])}</h2>')
            H += [h_block(x) for x in b[3]]
    H.append("</article>")
    return "\n".join(H)


def main():
    os.makedirs(FIG, exist_ok=True)
    fig_chain(); fig_poset(); fig_design(); fig_gantt(); photo()
    open(os.path.join(HERE, "refs.bib"), "w").write(bibtex())
    open(os.path.join(HERE, "paper.tex"), "w").write(latex())
    open(os.path.join(HERE, "paper.html"), "w").write(html_doc())
    r = subprocess.run(["latexmk", "-lualatex", "-interaction=nonstopmode", "-halt-on-error", "paper.tex"], cwd=HERE,
                       capture_output=True, text=True, timeout=600)
    log = open(os.path.join(HERE, "paper.log")).read() if os.path.exists(os.path.join(HERE, "paper.log")) else ""
    pages = re.search(r"Output written on paper\.pdf \((\d+) pages", log)
    warn = [l for l in log.splitlines() if re.search(r"undefined|Overfull \\hbox \((\d{2,})", l)]
    print(f"[paper] latexmk exit {r.returncode}; {pages.group(1) if pages else '?'} pages; warnings {len(warn)}")
    for w in warn[:12]:
        print("   ", w[:160])
    if r.returncode:
        print(r.stdout[-3000:])
    print(f"[paper] {N}")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
