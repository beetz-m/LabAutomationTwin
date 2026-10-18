"""Build the technical report on representing biomedical experiments: the conceptual framework, its partonomy, the
LDL concept layer, the description-logic axiomatizations and the challenge-rescue case study.

Every number, axiom, listing and figure is read from the outputs of the generators it reports on:
  rsa/culture_plan.py, rsa/culture_to_cram.py, rsa/experiment_designator.py, rsa/experiment_concepts.py,
  rsa/experiment_dl.py, rsa/experiment_ontology.py, rsa/lab_affordance.py   (re-run first unless --no-regen)

    env_cad/bin/python report/experiments/build_experiments_report.py   # experiments_report.tex/.pdf, source zip

ILLUSTRATIVE (D016): the culture biology is Cell 01's surrogate; doses, criteria and the improved design are labelled,
not lab facts.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
PY = os.path.join(ROOT, "env_cad", "bin", "python")
OUT = os.path.join(ROOT, "rsa", "out")
XOUT = os.path.join(OUT, "experiment_ontology")
LAB = os.path.join(ROOT, "rsa", "registry", "lab")
FIG = os.path.join(HERE, "figures")
PLANF = os.path.join(ROOT, "okf", "lab-automation-twin", "L3-logical-axiomatization", "derivation", "out", "plan_g050.json")
GENERATORS = ["rsa.culture_plan", "rsa.culture_to_cram", "rsa.experiment_designator", "rsa.experiment_concepts",
              "rsa.experiment_dl", "rsa.experiment_ontology", "rsa.lab_affordance"]

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

INK, MUTED, LINE = "#263238", "#607d8b", "#b0bec5"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": INK, "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False})


def J(*p):
    return json.load(open(os.path.join(*p)))


# ================================================================================================= data
def load():
    global cp, xd, xc, xo, af, plan, XO, AF, spec1, spec2, B1, B2, V
    cp = J(OUT, "culture_plan.json")
    xd = J(OUT, "experiment_designator.json")
    xc = J(OUT, "experiment_concepts.json")
    xo = J(XOUT, "experiment_owl.json")
    af = J(XOUT, "lab_affordance.json")
    plan = J(PLANF)
    from rsa import experiment_ontology as _XO
    from rsa import lab_affordance as _AF
    XO, AF = _XO, _AF
    B1, spec1 = XO.current_design()
    eig3 = plan["candidate_eig_bits"].get("c_d85_t48_n3")
    B2, spec2 = XO.improved_design(eig3)
    K = cp["knowledge"]
    sel = plan["selected"]
    S = XO.tbox()
    n_ax = sum(len(s["axioms"]) for s in S)
    n_eq = sum(isinstance(a, XO.Eq) for s in S for a in s["axioms"])
    names = set()
    for s in S:
        for a in s["axioms"]:
            for side in ("l", "r"):
                x = getattr(a, side, None)
                if isinstance(x, XO.E):
                    names |= x.names()
            for c in getattr(a, "cs", []):
                names |= c.names()
    n_cls = len({n for n in names if not n.startswith("bio:")})
    d = xd["derived"]
    lv = {}
    for v, l in d["level"].items():
        lv.setdefault(l, []).append(v[1:])
    order = r" $<$ ".join("\\{" + ", ".join(sorted(vs)) + "\\}" if len(vs) > 1 else vs[0] for _, vs in sorted(lv.items()))
    links = d["links"]
    neg_v1 = xc["negative_controls"]
    V = dict(
        design=sel["id"].replace("_", r"\_"), dose="0.85", delay="48", eig=f"{sel['eig_bits']:.4f}",
        eig_n2=f"{plan['candidate_eig_bits']['c_d85_t48_n2']:.3f}", eig_n3=f"{eig3:.3f}",
        r_cr=f"{K['observed_radius_um']['cr']:.1f}", r_cc=f"{K['observed_radius_um']['cc']:.1f}",
        r_ck=f"{K['observed_radius_um']['ck']:.1f}", eff=f"{K['effect_um']:.1f}",
        eff_v=f"{K['observed_radius_um']['cc'] - K['observed_radius_um']['ck']:.1f}",
        p1=f"{K['posterior']['M1_graded']:.2f}", p2=f"{K['posterior']['M2_threshold']:.2f}", p3=f"{K['posterior']['M3_protective']:.2f}",
        ig=f"{K['information_gain_bit']:.3f}", h0=f"{K['entropy_before_bit']:.3f}", h1=f"{K['entropy_after_bit']:.3f}",
        sigma=f"{K['sigma_um']:.1f}",
        n_cp=str(len(cp["plan"]["steps"])), n_cp_links=str(len(cp["derived"]["links"])),
        n_cp_phys=str(sum(l["kind"] == "physical" for l in cp["derived"]["links"])),
        n_cp_know=str(sum(l["kind"] == "knowledge" for l in cp["derived"]["links"])),
        n_x=str(len(d["level"])), n_x_links=str(len(links)), order=order,
        n_x_phys=str(sum(l["kind"] == "physical" for l in links)), n_x_know=str(sum(l["kind"] == "knowledge" for l in links)),
        matched=str(len(xd["comparison"]["matched"])), n_v1_neg=str(len(neg_v1)),
        v1_parts=f"{sum(v[0] for v in xc['parts'].values())}/{sum(v[1] for v in xc['parts'].values())}",
        v1_constraints=str(sum(len(r) for r in xc["conformance"].values())),
        v1_concepts=str(len(xc["concepts"])), v1_roles=str(len(xc["roles"])),
        n_ax=str(n_ax), n_eq=str(n_eq), n_cls=str(n_cls), n_obj=str(len(XO.OBJ_PROPS)), n_data=str(len(XO.DATA_PROPS)),
        n_align=str(len(XO.ALIGN)), n_sec=str(len(S)),
        t_cur=str(xo["results"]["challenge_rescue"]["seconds"]), t_imp=str(xo["results"]["improved"]["seconds"]),
        t_bio=str(xo["with_bio"]["seconds"]), n_neg=str(len(xo["negative_controls"])),
        n_neg_ok=str(sum(xo["negative_controls"].values())), n_inf=str(len(xo["inferred_subsumptions"])),
        n_arm2=str(len(spec2["arms"])), n_units2=str(sum(a["units"] for a in spec2["arms"].values())),
        n_cmp2=str(len(spec2["comparisons"])), min_rep=str(XO.MIN_REPLICATES),
        t_aff=str(af["reasoner"]["seconds"]), n_dev=str(len(af["labs"]["cell01"]["devices"])),
        wps=str(af["labs"]["cell01"]["wells_per_session"]), window=f"{af['labs']['cell01']['window_s']:.0f}",
        overhead=f"{af['labs']['cell01']['overhead_s']:.0f}", dose_s=f"{af['labs']['cell01']['dose_s']:.1f}",
        n_aff=str(len(af["designs"])))
    for m, p in sel["predicted_effect_um"].items():
        V[f"pred_{m[:2]}"] = f"{p['effect_um']:.1f}"
        V[f"sd_{m[:2]}"] = f"{p['effect_sd_um']:.1f}"


def fill(s):
    for k, v in V.items():
        s = s.replace(f"@@{k}@@", v)
    left = re.findall(r"@@\w+@@", s)
    assert not left, left
    return s


# ================================================================================================= figures
def copy_figs():
    os.makedirs(FIG, exist_ok=True)
    for src, dst in ((os.path.join(XOUT, "framework.pdf"), "framework.pdf"),
                     (os.path.join(OUT, "experiment_partonomy.pdf"), "partonomy.pdf"),
                     (os.path.join(OUT, "experiment_concepts.pdf"), "concepts_v1.pdf"),
                     (os.path.join(ROOT, "report", "figures", "culture.pdf"), "culture.pdf"),
                     (os.path.join(ROOT, "report", "figures", "poset.pdf"), "poset12.pdf")):
        shutil.copy(src, os.path.join(FIG, dst))


def fig_order13():
    """The 13 culture actions derived from experiment.ldl, ordered by their causal links."""
    from rsa.culture_plan import load_plan
    P = load_plan(open(os.path.join(OUT, "experiment_culture_plan.ldl")).read())
    typ = {s["var"]: s["type"] for s in P["steps"]}
    col = {"intervention": "#ffebee", "growth": "#fff8e1", "observation": "#e3f2fd", "interpretation": "#ede7f6",
           "comparison:validity": "#e8f5e9", "comparison:primary": "#e8f5e9"}
    d = xd["derived"]
    dot = ["digraph O { rankdir=LR; nodesep=0.18; ranksep=0.42; node [shape=box, style=\"rounded,filled\", fontname=Helvetica, "
           "fontsize=10]; edge [fontname=Helvetica, fontsize=7, color=\"#546e7a\"];"]
    for v, t in typ.items():
        k = xd["kinds"][v]
        dot.append(f'"{v}" [label="{v[1:]}\\n{t}", fillcolor="{col.get(k, "#eeeeee")}"];')
    kinds = {(l["frm"], l["to"]): l["kind"] for l in d["links"]}
    for a, b in d["hasse"]:
        k = kinds.get((a, b), "")
        dot.append(f'"{a}" -> "{b}" [style={"solid" if k == "physical" else "dashed"}];')
    dot.append("}")
    subprocess.run(["dot", "-Tpdf", "-o", os.path.join(FIG, "order13.pdf")], input="\n".join(dot), text=True, check=True)


def fig_designs():
    """Arms on a time axis: administrations and imaging, for the current and the improved design."""
    mk = {"challenge": ("s", "#c62828"), "rescue": ("^", "#2e7d32"), "vehicle": ("o", "#90a4ae")}
    real = {n: xo["results"][n]["realization"] for n in ("challenge_rescue", "improved")}
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 3.5), gridspec_kw=dict(width_ratios=[1, 1.25]))
    for ax, (title, spec, name, pre) in zip(axes, (("current design (n = 1 per arm)", spec1, "challenge_rescue", ""),
                                                   ("improved design (ILLUSTRATIVE, n = 3 per arm)", spec2, "improved", "improved_"))):
        arms = list(spec["arms"])
        for i, a in enumerate(arms):
            y = len(arms) - 1 - i
            ax.plot([0, 72], [y, y], color=LINE, lw=1.0, zorder=0)
            for ag, dose, t in XO.schedule(spec, a):
                m, c = mk[ag]
                ax.scatter([t], [y], marker=m, s=70, color=c, zorder=3, edgecolor="white", linewidth=0.6)
            ax.scatter([72], [y], marker="D", s=40, color="#1565c0", zorder=3)
            cls = [t for t in real[name].get(f"{pre}arm_{a}", []) if t != "ReplicatedArm"]
            ax.text(-3, y + 0.2, a.replace("_", " "), ha="right", va="center", fontsize=8.5, color=INK)
            ax.text(-3, y - 0.22, ", ".join(cls), ha="right", va="center", fontsize=6.6, color=MUTED, style="italic")
            ax.text(75, y, f"n={spec['arms'][a]['units']}", va="center", fontsize=8, color=INK)
        ax.set_xlim(-2, 82)
        ax.set_ylim(-0.7, len(arms) - 0.3)
        ax.set_yticks([])
        ax.set_xticks([0, 6, 24, 48, 72])
        ax.set_xlabel("culture time (h)")
        ax.set_title(title, fontsize=9.5, color=INK)
        ax.spines["left"].set_visible(False)
    hs = [plt.Line2D([], [], marker=m, color=c, ls="", markersize=7, label=l) for l, (m, c) in mk.items()]
    hs.append(plt.Line2D([], [], marker="D", color="#1565c0", ls="", markersize=6, label="imaging (72 h)"))
    fig.legend(handles=hs, loc="lower center", ncol=4, frameon=False, fontsize=8.5, bbox_to_anchor=(0.6, -0.02))
    fig.subplots_adjust(left=0.2, right=0.98, wspace=0.62, bottom=0.25, top=0.9)
    fig.savefig(os.path.join(FIG, "designs.pdf"))
    plt.close(fig)


def fig_eig():
    """Expected information gain of the candidate designs (dose, delay, replicates)."""
    e = plan["candidate_eig_bits"]
    rows = []
    for k, v in e.items():
        m = re.match(r"c_d(\d+)_t(\d+)_n(\d+)", k)
        rows.append((int(m[1]) / 100, int(m[2]), int(m[3]), v))
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.0))
    for dose, c in zip(sorted({r[0] for r in rows}), ("#90a4ae", "#5c6bc0", "#c62828")):
        pts = sorted((r[1], r[3]) for r in rows if r[0] == dose and r[2] == 1)
        axes[0].plot(*zip(*pts), marker="o", color=c, label=f"dose {dose:.2f} au")
    for n, c in zip((1, 2, 3), ("#c62828", "#ef6c00", "#6d4c41")):
        pts = sorted((r[1], r[3]) for r in rows if r[0] == 0.85 and r[2] == n)
        axes[1].plot(*zip(*pts), marker="o", color=c, label=f"{n} per arm")
    for ax, t in zip(axes, ("one well per arm", "dose 0.85 au")):
        ax.axhline(0.5, color=MUTED, ls="--", lw=0.8)
        ax.text(12.3, 0.52, "required 0.5 bit", fontsize=7.5, color=MUTED)
        ax.set_xlabel("delay of the rescue (h)")
        ax.set_ylabel("expected information gain (bit)")
        ax.set_title(t, fontsize=9.5)
        ax.legend(frameon=False, fontsize=7.5)
    axes[0].scatter([48], [e["c_d85_t48_n1"]], s=120, facecolor="none", edgecolor=INK, zorder=4)
    axes[0].annotate("selected", (48, e["c_d85_t48_n1"]), xytext=(33, 0.62), fontsize=8, arrowprops=dict(arrowstyle="->", color=INK))
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "eig.pdf"))
    plt.close(fig)


def fig_inferred():
    """The inferred taxonomy (HermiT) in three panels, with the two designs' individuals realized under it."""
    w, onto, k, inds = XO.build([B1, B2])
    ok, _, _ = XO.reason(w, onto)
    assert ok
    groups = {"arms": ["ArmSpecification", "NegativeControlArm", "UntreatedArm", "VehicleControlArm", "ChallengeOnlyArm",
                       "RescueOnlyArm", "ChallengeRescueArm", "PositiveControlArm", "ReplicatedArm"],
              "comparisons": ["ComparisonSpecification", "InjuryValidityComparison", "RescueEffectComparison",
                              "AgentAloneComparison", "PositiveControlComparison", "RescueTimingComparison",
                              "SingleFactorComparison", "CoveredComparison"],
              "designs": ["StudyDesign", "ComparativeDesign", "ControlledDesign", "InjuryRescueDesign", "ValidatedInjuryRescueDesign",
                          "AgentControlledInjuryRescueDesign", "TherapeuticWindowDesign", "AdequatelyControlledInjuryRescueDesign",
                          "FactorialDesign", "WellContrastedDesign", "PreSpecifiedDesign", "PositiveControlledDesign",
                          "ReplicatedDesign", "HypothesisDiscriminatingDesign", "SufficientlyInformativeDesign"]}
    colors = {"challenge_rescue": "#e3f2fd", "improved": "#fff3e0"}
    for g, show in groups.items():
        dot = ["digraph H { rankdir=BT; nodesep=0.15; ranksep=0.3; node [shape=box, style=rounded, fontname=Helvetica, fontsize=9];"
               " edge [color=\"#555555\", arrowsize=0.6];"]
        for n in show:
            c = k.cls(n)
            sups = [s for s in c.ancestors() if s is not c and s.name in show]
            for s in [s for s in sups if not any(t is not s and issubclass(t, s) for t in sups)]:
                dot.append(f'"{n}" -> "{s.name}";')
            dot.append(f'"{n}";')
        for design, r in xo["results"].items():
            for ind, types in r["realization"].items():
                base = ind.split("improved_")[-1]
                keep = (g == "arms" and base.startswith("arm_")) or (g == "comparisons" and base.startswith("cmp_")) or \
                       (g == "designs" and ind.endswith("_design"))
                if not keep:
                    continue
                node = f"{design}:{ind}"
                dot.append(f'"{node}" [label="{ind}", shape=note, style=filled, fillcolor="{colors[design]}", fontsize=7];')
                for t in types:
                    if t in show:
                        dot.append(f'"{node}" -> "{t}" [style=dashed, color="#90a4ae", arrowsize=0.4];')
        dot.append("}")
        subprocess.run(["dot", "-Tpdf", "-o", os.path.join(FIG, f"inferred_{g}.pdf")], input="\n".join(dot), text=True, check=True)


def fig_affordance():
    """Left: capability classes of the two laboratories (HermiT). Right: each design's requirements and where they are met."""
    caps = ["TreatmentAndImagingModule", "DosingLab", "CultivationLab", "BrightfieldImagingLab", "ValidatedSizeReadoutLab",
            "QualityControlledLab", "ContainmentCapableLab", "ConnectedLab", "LuminescenceReadoutLab", "AbsorbanceReadoutLab",
            "ValidatedMetabolicReadoutLab", "MultiEnvironmentLab"]
    labs = list(af["labs"])
    reqs = ["RequiresCultivation", "RequiresDosing", "RequiresImaging", "RequiresLuminescence", "RequiresMultipleEnvironments",
            "reagents stocked"]
    D = af["designs"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.4, 4.0), gridspec_kw=dict(width_ratios=[0.8, 1.6]))
    for i, c in enumerate(caps):
        for j, l in enumerate(labs):
            has = c in af["labs"][l]["capability_classes"]
            a1.scatter(j, i, s=150, marker="s", color="#2e7d32" if has else "white", edgecolor="#2e7d32" if has else LINE)
    a1.set_xticks(range(len(labs)), ["Cell 01", "core reader\n(ILLUSTRATIVE)"])
    a1.set_yticks(range(len(caps)), caps, fontsize=7.5)
    a1.set_xlim(-0.6, len(labs) - 0.4)
    a1.invert_yaxis()
    a1.set_title("capability classes (HermiT)", fontsize=9.5)
    col = {"cell01": "#2e7d32", "core_reader": "#ef6c00", None: "#c62828"}
    names = {"current": "current", "improved": "improved", "improved_atp": "improved\n+ ATP endpoint", "oxygen": "challenge ×\noxygen"}
    for j, (n, m) in enumerate(D.items()):
        got = {r["requirement"]: r["allocated"] for r in m["checks"]}
        for i, r in enumerate(reqs):
            if r in m["requirements"] or r in got:
                a2.scatter(j, i, s=170, marker="o", color=col[got.get(r)], edgecolor="none")
                a2.text(j, i, {"cell01": "C1", "core_reader": "CR", None: "×"}[got.get(r)], ha="center", va="center",
                        fontsize=6.5, color="white", fontweight="bold")
            else:
                a2.scatter(j, i, s=30, marker=".", color=LINE)
        v = m["verdict"].replace("executable on site with transfers", "on site,\nwith transfers") \
            .replace("executable in cell01", "in Cell 01").replace("not executable as modelled", "not as\nmodelled")
        if m.get("if_stocked"):
            v += "\n(vehicle stocked:\n" + m["if_stocked"]["verdict"].replace("executable on site with transfers",
                                                                                   "with transfers").replace("executable in cell01", "Cell 01") + ")"
        a2.text(j, len(reqs) + 0.15, v, ha="center", va="top", fontsize=7, color=INK)
    a2.set_xticks(range(len(D)), [names[n] for n in D], fontsize=8)
    a2.xaxis.tick_top()
    a2.set_yticks(range(len(reqs)), reqs, fontsize=7.5)
    a2.set_ylim(len(reqs) + 1.6, -0.6)
    a2.set_xlim(-0.6, len(D) - 0.4)
    a2.set_title("requirements (HermiT), where they are met, verdict", fontsize=9.5, pad=26)
    for a in (a1, a2):
        a.tick_params(length=0)
        for sp in a.spines.values():
            sp.set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "affordance.pdf"))
    plt.close(fig)


# ================================================================================================= LaTeX helpers
def esc(s):
    return (str(s).replace("\\", r"\textbackslash{}").replace("_", r"\_").replace("&", r"\&").replace("%", r"\%")
            .replace("#", r"\#").replace("{", r"\{").replace("}", r"\}").replace("≥", r"$\geq$").replace("×", r"$\times$"))


def table(cols, head, rows, caption, label, size="small", long=False):
    spec = "@{}" + "".join(cols) + "@{}"
    body = "\n".join(" & ".join(r) + r" \\" for r in rows)
    if long:
        return (f"{{\\{size}\\begin{{xltabular}}{{\\linewidth}}{{{spec}}}\n\\caption{{{caption}}}\\label{{{label}}}\\\\\n"
                f"\\toprule {' & '.join(head)} \\\\ \\midrule\\endfirsthead\n\\toprule {' & '.join(head)} \\\\ \\midrule\\endhead\n"
                f"{body}\n\\bottomrule\n\\end{{xltabular}}}}\n")
    return (f"\\begin{{table}}[tbp]\\centering\\{size}\n\\caption{{{caption}}}\\label{{{label}}}\n"
            f"\\begin{{tabularx}}{{\\linewidth}}{{{spec}}}\\toprule {' & '.join(head)} \\\\ \\midrule\n{body}\n"
            f"\\bottomrule\\end{{tabularx}}\\end{{table}}\n")


def figure(f, caption, label, width=r"\linewidth"):
    return (f"\\begin{{figure}}[tbp]\\centering\\includegraphics[width={width},height=0.72\\textheight,keepaspectratio]{{figures/{f}}}\n"
            f"\\caption{{{caption}}}\\label{{{label}}}\\end{{figure}}\n")


def listing(text, caption, label, size="scriptsize"):
    return (f"\\begin{{Verbatim}}[fontsize=\\{size},breaklines,frame=lines,framesep=2mm]\n{text.rstrip()}\n\\end{{Verbatim}}\n"
            f"\\vspace{{-4pt}}\\captionof{{listing}}{{{caption}}}\\label{{{label}}}\\medskip\n")


def brk(x):
    for s in (" ⊓ ", " ⊔ "):
        x = x.replace(s, s.rstrip() + r"\allowbreak ")
    return x


def axioms(ax_list):
    return "\n".join(rf"\ax{{{brk(a.dl('tex'))}}}" for a in ax_list)


def find_ax(*names):
    """The axioms whose left-hand side is one of names, in TBox order."""
    out = []
    for s in XO.tbox():
        for a in s["axioms"]:
            if isinstance(getattr(a, "l", None), XO.A) and a.l.n in names:
                out.append(a)
    return out


def src(path, start=None, end=None):
    lines = open(path).read().splitlines()
    if start is not None:
        i = next(n for n, l in enumerate(lines) if start in l)
        j = next((n for n, l in enumerate(lines[i + 1:], i + 1) if end and end in l), len(lines) - 1) if end else len(lines) - 1
        lines = lines[i:j + 1]
    return "\n".join(lines)


def cw_cell(r):
    return r"\textit{info}" if r.get("info") else (r"\textcolor{green!45!black}{pass}" if r["ok"] else r"\textcolor{red!65!black}{fail}")


# ================================================================================================= the document
PREAMBLE = r"""\documentclass[10pt,a4paper]{article}
\usepackage[margin=2.3cm,headheight=14pt]{geometry}
\usepackage{fontspec,unicode-math}
\setmainfont{Libertinus Serif}
\setsansfont{IBM Plex Sans}
\setmonofont[Scale=0.86]{IBM Plex Mono}
\setmathfont{Libertinus Math}
\usepackage{microtype,graphicx,booktabs,tabularx,xltabular,xcolor,float,fvextra,caption,fancyhdr,titlesec,enumitem,multicol,array}
\usepackage{placeins}
\usepackage[numbers,sort&compress]{natbib}
\usepackage[colorlinks,hypertexnames=false,linkcolor=teal!70!black,citecolor=teal!70!black,urlcolor=teal!70!black]{hyperref}
\newfloat{listing}{tbp}{lol}\floatname{listing}{Listing}
\captionsetup{font=small,labelfont=bf}
\renewcommand{\tabularxcolumn}[1]{>{\raggedright\arraybackslash}p{#1}}
\setlength{\tabcolsep}{4pt}
\setlength{\LTpre}{6pt}\setlength{\LTpost}{6pt}
\setlength{\emergencystretch}{3em}
\setlist{itemsep=2pt,topsep=4pt}
\newcommand{\ax}[1]{\par{\raggedright\noindent\hangindent=2.2em\hangafter=1 $#1$\par}\smallskip}
\titleformat{\section}{\sffamily\Large\bfseries\color{teal!55!black}}{\thesection}{0.8em}{}
\titleformat{\subsection}{\sffamily\large\bfseries}{\thesubsection}{0.7em}{}
\titleformat{\subsubsection}{\sffamily\normalsize\bfseries}{\thesubsubsection}{0.6em}{}
\renewcommand{\floatpagefraction}{0.75}\renewcommand{\topfraction}{0.85}\renewcommand{\textfraction}{0.12}
\pagestyle{fancy}\fancyhf{}
\fancyhead[L]{\sffamily\footnotesize Representing biomedical experiments: technical report}
\fancyhead[R]{\sffamily\footnotesize\nouppercase{\leftmark}}
\fancyfoot[C]{\sffamily\footnotesize\thepage}
\renewcommand{\headrulewidth}{0.3pt}
\begin{document}
\begin{titlepage}
\sffamily
\vspace*{2.2cm}
\noindent{\color{teal!55!black}\rule{\linewidth}{1.2pt}}\par\vspace{0.6cm}
\noindent{\Huge\bfseries Representing Biomedical Experiments\par}\vspace{0.4cm}
{\Large A conceptual framework, its partonomy\\[2pt] and its description-logic axiomatization\par}\vspace{0.3cm}
{\large with the challenge--rescue experiment as a case study\par}\vspace{0.6cm}
\noindent{\color{teal!55!black}\rule{\linewidth}{1.2pt}}\par\vspace{1.0cm}
{\large Technical report on the experiment layer of the robot science assistant\\ on Cell 01 of the LabAutomationTwin\par}
\vspace{1.4cm}
{\normalsize [Authors and affiliations]\par}
\vfill
{\small\rmfamily
\begin{tabular}{@{}ll@{}}
Generated & 2026-10-17, from the generators' outputs \\
Case study & challenge--rescue experiment, design \texttt{@@design@@} \\
Ontology & @@n_cls@@ concepts, @@n_obj@@ object and @@n_data@@ data properties, @@n_ax@@ TBox axioms (OWL~2~DL), HermiT-checked \\
Status & research prototype; biology is a surrogate, quantities ILLUSTRATIVE (D016) \\
\end{tabular}\par}
\end{titlepage}
\pagenumbering{roman}
\tableofcontents
\clearpage
\pagenumbering{arabic}
"""


def affordance_section():
    """What Cell 01 affords: capability profiles, design requirements and their matching (rsa/lab_affordance.py)."""
    T = []
    c01, core = af["labs"]["cell01"], af["labs"]["core_reader"]
    caps_all = sorted(set(XO.REQUIREMENT_MET_BY.values()) | {"QualityControlledLab", "ContainmentCapableLab", "ConnectedLab",
                                                           "ValidatedSizeReadoutLab", "ValidatedMetabolicReadoutLab",
                                                           "TreatmentAndImagingModule"})
    M = lambda xs: ", ".join(rf"$\mathsf{{{x}}}$" for x in xs)
    RR = r">{\raggedright\arraybackslash}"
    T.append(r"""
\section{What our laboratory affords}\label{sec:afford}
Biomedical laboratories are not general-purpose. What experiments a laboratory affords is fixed by its equipment, the
environments it controls, its containment, the assays it has validated and the reagents it keeps; a cell-culture
laboratory, an imaging core, a plate-reader core and a hypoxia facility afford different experiments, and most
experiments of interest need more than one of them. Cell~01 is a \emph{treatment-and-imaging module}: it incubates,
doses, images, calibrates and quarantines plates, and a clean-sample robot connects it to the rest of the site. A
robot scientist that proposes designs therefore has to know, for each design, whether it can be run here, which of
its steps have to be performed elsewhere, and what is missing. This section adds capability profiles of laboratories
to the ontology, classifies designs by what they require, and matches the two (\texttt{rsa/lab\_affordance.py}).

\subsection{Capabilities as device functions}
Following BFO, a capability is modelled as a \emph{function}: a disposition that inheres in a device and is realized
only in processes of one kind. A liquid handler bears a dosing function, realized only in administrations; an imager
bears an imaging function, realized only in imaging assays. A laboratory has its devices as parts, and its capability
classes are \emph{defined} by the functions its devices bear, by the number of controlled environments it provides and
by its validated readout bindings (a binding is information about which quality a device's readout measures, and at
which validation level). The reasoner therefore classifies a laboratory from its devices, and nothing about what a
laboratory can do is asserted directly. Selected axioms:
""")
    T.append(axioms(find_ax("Laboratory", "DeviceFunction", "DosingFunction", "BrightfieldImagingFunction", "DosingLab",
                            "MultiEnvironmentLab", "ValidatedSizeReadoutLab", "TreatmentAndImagingModule")))
    T.append(r"""
Reagent stocks are located in a laboratory (\textit{stocks}), not parts of it, and an environment profile is a plan
specification that a laboratory realizes, so that two incubators running at the same setpoints count as one
environment. Because a function is realized only in processes of its kind, a function realized in the wrong kind of
process is a contradiction: an incubation function realized in an imaging assay is the eighth negative control of
Table~\ref{tab:neg2}.

\subsection{Design requirements}
What a design needs from a laboratory follows from its content, so requirement classes are defined as well: a design
with an administration requires dosing, one with an imaging readout requires imaging, one with an endpoint readout
(luminescence, absorbance) requires the corresponding reader and endpoint handling, and one with an environment factor
requires as many controlled environments as the factor has levels.
""")
    T.append(axioms(find_ax("RequiresDosing", "RequiresImaging", "RequiresLuminescence", "RequiresEndpointHandling",
                            "RequiresMultipleEnvironments")))
    rows = [[rf"$\mathsf{{{r}}}$", rf"$\mathsf{{{c}}}$"] for r, c in XO.REQUIREMENT_MET_BY.items()]
    T.append(r"""
Each requirement is met by one capability class (Table~\ref{tab:reqcap}). This correspondence is a table, not an
axiom: it relates classes of different categories (designs and laboratories), and stating it as a subsumption would
make every design a laboratory. The reasoner adds requirements no axiom states for a design class: every injury--rescue
design, validated or adequately controlled, requires dosing; every design that has an arm requires cultivation; and
luminescence and absorbance readouts require endpoint handling (Section~\ref{sec:results}).
""")
    T.append(table(["X", "X"], ["design requirement", "met by laboratory capability"], rows,
                   "Requirements and the capabilities that meet them.", "tab:reqcap", size="footnotesize"))
    rows = [[esc(d["name"]), esc(", ".join(d["capabilities"])),
             esc(", ".join(sorted({AF.VERB_FUNCTION[v] for v in d["capabilities"] if v in AF.VERB_FUNCTION})) or "---")]
            for d in c01["devices"].values()]
    env = c01["environments"]["standard"]
    T.append(r"""
\subsection{Cell~01's profile}
Cell~01's profile is not written by hand; it is read from three sources in the repository. The ten component records
list each device's capability verbs, which a table maps to device functions (Table~\ref{tab:c01dev}); the device
registry lists the reagent stocks and the readout bindings with their validation level; and the twin's measured
durations give the time a dosing session takes. Verbs without a function (aspirate, autofocus, press a button) are
steps of the functions' realizations, not capabilities of their own, and are not mapped.
""")
    T.append(table([RR + "p{4.0cm}", RR + "X", RR + "p{3.6cm}"], ["device (component record)", "capability verbs", "functions"], rows,
                   "Cell~01's devices, their capability verbs and the functions they are evidence of.", "tab:c01dev",
                   size="footnotesize"))
    T.append(rf"""
Cell~01 provides one controlled environment ({env['temperature_C']:g}\,\textdegree C, {env['CO2_percent']:g}\,\% CO$_2$,
{env['humidity_percent']:g}\,\% humidity, from the incubator's record), stocks the agents {esc(', '.join(c01['stocks']))},
and has one validated readout binding: the imaging station's organoid radius, a readout of organoid size. A plate may
be outside the incubator for at most @@window@@~s per excursion; a dosing session costs about @@overhead@@~s of
transfers (two legs of each robot arm, retrieval, storage, tool coupling) and @@dose_s@@~s per well, so at most
\textbf{{@@wps@@ wells}} can be dosed per session (these durations are the twin's, ILLUSTRATIVE).

HermiT classifies the laboratories in @@t_aff@@~s, with both laboratories and all four designs in one ontology
(Table~\ref{{tab:labcaps}}). Cell~01 is a treatment-and-imaging module; it is not an endpoint-reader, metabolic-readout
or multi-environment laboratory, because it has no endpoint reader, no validated metabolic readout and one
environment. A second laboratory, a site core facility with a multimode plate reader and a dock for the clean-sample
robot, is ILLUSTRATIVE (not modelled from records); it stands in for the facilities to which steps that Cell~01
cannot perform are allocated.

@@LABCAPS@@

\subsection{{Matching designs against laboratories}}
Whether a design is executable is a closed-world question over the individuals: it concerns the laboratories and
stocks the site has, not those it might have. For each design, the matcher (i) takes the requirement classes HermiT
infers for it and allocates each to a laboratory with the meeting capability, Cell~01 first; (ii) checks that every
agent the design administers is stocked where the dosing happens; (iii) checks that each readout has a validated
binding to the quality it is about in the allocated laboratory; (iv) counts the environments an environment factor
needs; (v) splits the doses due at each time point into sessions that fit the excursion window; (vi) checks the units
against the {AF.INTERIOR_WELLS} interior wells of one plate; (vii) checks that destructive endpoint readouts come
after every imaging; and (viii) checks that a transfer to every other allocated laboratory is possible (both
connected). The verdict is \emph{{executable in Cell~01}}, \emph{{executable on site with transfers}}, or \emph{{not
executable as modelled}} with what is missing; when only reagents are missing, the matcher also reports the verdict
with them stocked.
""")
    labcaps = table([RR + "p{3.2cm}", RR + "X", RR + "X"], ["laboratory", "is (HermiT)", "is not"],
                    [[esc(p["label"]), M(p["capability_classes"]), M(sorted(set(caps_all) - set(p["capability_classes"])))]
                     for p in (c01, core)], "Capability classes of the two laboratories (HermiT).", "tab:labcaps",
                    size="footnotesize")
    T[-1] = T[-1].replace("@@LABCAPS@@", labcaps)
    rows = []
    for n, m in af["designs"].items():
        C = lambda x: esc(x.replace("cell01", "Cell 01"))
        rows.append([esc(m["label"]), ", ".join(r.replace("Requires", "") for r in m["requirements"]), C(m["verdict"]),
                     C("; ".join(m["missing"]) or "---"),
                     C(m["if_stocked"]["verdict"]) if m.get("if_stocked") else "---"])
    T.append(table([RR + "p{3.6cm}", RR + "p{2.8cm}", RR + "p{2.0cm}", RR + "X", RR + "p{2.2cm}"],
                   ["design", "requires (HermiT)", "verdict", "missing", "with reagents stocked"], rows,
                   "What Cell~01 and the site afford: four designs (ILLUSTRATIVE).", "tab:afford", size="footnotesize"))
    T.append(figure("affordance.pdf", "Left: capability classes HermiT infers for the two laboratories. Right: the "
                    "requirements of the four designs and the laboratory each is allocated to (C1 Cell~01, CR core reader, "
                    "$\\times$ unmet), with the verdict below.", "fig:afford"))
    d = af["designs"]
    T.append(rf"""
\subsection{{Four designs}}
\paragraph{{The current design}} requires cultivation, dosing and imaging, all met by Cell~01, with both agents
stocked and a validated size readout; its three doses (two at 0~h, one at 48~h) take one session each. It is
\emph{{{esc(d['current']['verdict'].replace('cell01', 'Cell 01'))}}}.

\paragraph{{The improved design}} has the same requirements, but administers a vehicle that Cell~01 does not stock, so
it is \emph{{{esc(d['improved']['verdict'])}}}; with the vehicle stocked it would be
\emph{{{esc(d['improved']['if_stocked']['verdict'].replace('cell01', 'Cell 01'))}}}. Its @@n_units2@@ units receive 15
administrations at each of 0, 6 and 48~h, more than the @@wps@@ that fit one excursion, so each time point needs two
sessions and the last wells are dosed about ten minutes after the first. Against a rescue delay of 6 or 48~h this is
small, but it is systematic if the arms are dosed in a fixed order; the sessions should interleave the arms, which is
the same randomisation that the placement check asks for on the plate.

\paragraph{{The improved design with an ATP endpoint}} adds a luminescence readout of metabolic activity at 72~h,
after the imaging. HermiT classifies it as requiring luminescence and endpoint handling, which no device of Cell~01
offers; the step is allocated to the core reader, which has a validated binding for it, and the transfer is possible
because both laboratories are connected by the clean-sample robot. With the vehicle stocked it is \emph{{executable on
site with transfers}}. The time the plate spends outside the controlled environment on the way is not modelled; since
the ATP read is the last step and destructive, it does not affect the imaging readout.

\paragraph{{The challenge $\times$ oxygen design}} varies the environment (normoxia, hypoxia) as a factor. It requires
{len(d['oxygen']['requirements'])} capabilities, among them $\mathsf{{MultiEnvironmentLab}}$: two controlled
environments, of which Cell~01 provides one and the core facility none. It is \emph{{not executable as modelled}};
running it would need a second incubator at a different oxygen setpoint, or a hypoxia facility and transfers.

\subsection{{What the scope is, and what it is not}}
Within the modelled designs, Cell~01 affords in-vitro experiments on cultures in one plate, in one environment, with
treatments by the agents it stocks and imaging of organoid size as the readout: injury, rescue and agent-control
designs, therapeutic-window designs and their factorials, up to @@wps@@ administrations per session and
{AF.INTERIOR_WELLS} interior wells per plate. It affords designs with endpoint assays only together with a core
facility, and designs with environment factors not at all. For the adequately controlled design of
Section~\ref{{sec:results}} the only missing resource is a vehicle stock.

Three limitations bound this result. The map from capability verbs to functions is hand-written, and the general
manipulation verbs of the rail-mounted robot are not mapped, so capabilities that need a tool change are not
represented. The core facility, the vehicle and the durations are ILLUSTRATIVE, and transfer times between
laboratories are not modelled. And what can be dosed, imaged or read is classified, but whether an assay is suitable
for a question (sensitivity, dynamic range) is not: that is a property of a validated binding, which is recorded as a
level and not reasoned about.
""")
    return "\n".join(T)


def body():
    T = []
    T.append(r"""
\section{Executive summary}\label{sec:summary}
A robot scientist has to do more with an experiment than execute it. It has to know why each step is there, which
culture plays which part, what a measurement stands for, which comparison answers which question, and whether the
design can support the conclusion it is meant to support---ideally before anything is pipetted. This report describes
how the experiment layer of the robot science assistant (RSA) on Cell~01 of the LabAutomationTwin came to represent
experiments in that way, and what the resulting representation can and cannot check.

\paragraph{The case.} The running example is a \emph{challenge--rescue} experiment on organoid cultures
(Section~\ref{sec:case}): two cultures are injured with a challenge agent, one of them is given a rescue agent
@@delay@@~h later, an untreated culture serves as control, and organoid size is imaged at 72~h. The experiment
discriminates three recovery hypotheses---graded recovery, a threshold (``point of no return''), and a protective
response that moves the threshold. The design \texttt{@@design@@} was selected for its expected information gain of
@@eig@@~bit over the hypotheses. All biology is Cell~01's illustrative surrogate (D016).

\paragraph{From action lists to experiment logic.} The representation was developed in nine steps
(Section~\ref{sec:evolution}): from a culture-level plan of @@n_cp@@ actions ordered by causal links, through
CRAM/RPL plans and entity designators, to the observation that the experiment's \emph{logic} is three cultures,
each defined by its treatment, compared pairwise so that each comparison isolates one exposure. Written that way
(\texttt{experiment.ldl}), the experiment is short, has no variables, and the @@n_x@@ culture actions and their
order are \emph{derived} from it; the derivation reproduces all @@matched@@ actions of the hand-written plan and adds
the validity analysis that the hand-written plan only implied.

\paragraph{A conceptual framework.} Generalising from the case, Section~\ref{sec:framework} proposes a framework of
five layers---epistemic, design, protocol, execution and biological system---that keeps apart what is
\emph{planned}, what \emph{happens}, what is \emph{measured} and what is \emph{believed}. Its core concepts (units,
factors and levels, arms, controls defined by what they control for, replicates, readouts as proxies, comparisons,
interaction contrasts, analysis plans, hypotheses that \emph{posit} biology, belief and information gain,
deviations, conclusions) organise a multi-axial taxonomy of experiments. Validity criteria are assigned to the
mechanism that can enforce them: description logic for what experiments \emph{are}, closed-world queries for what a
design \emph{must contain}, run-time monitors for what an execution \emph{must keep}, and probabilistic models for
what it \emph{will tell us}. Three partonomies (process, material, plan) are separated from containment, membership,
participation and realization (Section~\ref{sec:partonomy}).

\paragraph{Axiomatization and reasoning.} The framework is axiomatized in OWL~2~DL (Section~\ref{sec:owl}):
@@n_ax@@ TBox axioms over @@n_cls@@ concepts in @@n_sec@@ groups, @@n_eq@@ of them definitions, so that the HermiT
reasoner \emph{classifies} arms, comparisons, designs and experiments from their content. Closure axioms in the ABox
make the definitions with negation decidable. The ontology is consistent alone, with both designs, and together with
Cell~01's biology ontology; all @@n_neg@@ negative controls are detected as inconsistencies; @@n_inf@@ subsumptions
between experiment classes are inferred rather than stated. What OWL~2 cannot express---single-factor contrasts,
replicate counts, plate-edge placement, factorial coverage, interaction estimability---is checked by closed-world
queries (Section~\ref{sec:closed}).

\paragraph{The main finding.} The reasoner classifies the current experiment as a \emph{validated injury--rescue}
experiment that is hypothesis-discriminating, sufficiently informative, pre-specified and well contrasted, but
\emph{not} as adequately controlled: it lacks a rescue-only arm (so the interaction of injury and rescue is not
estimable), a vehicle arm, a positive control and replicates, and its wells lie on the plate edge. An improved,
ILLUSTRATIVE design---a challenge $\times$ time-of-rescue factorial with @@n_arm2@@ arms, @@n_units2@@ units and
@@n_cmp2@@ comparisons including a therapeutic-window contrast---is classified as an
\emph{adequately controlled injury--rescue design}, and each variant that removes one ingredient loses exactly the
corresponding class (Section~\ref{sec:results}). The critique a biomedical reviewer would make is thus available as
a formal result before the experiment is run.

\paragraph{What our laboratory affords.} Laboratories are built for classes of experiments, so the ontology also
describes laboratories (Section~\ref{sec:afford}). Capability classes are defined by the functions a laboratory's
devices bear, its environments and its validated readouts; requirement classes are defined by a design's content.
HermiT classifies Cell~01, from its @@n_dev@@ component records, as a treatment-and-imaging module that is dosing,
cultivation, imaging, quality-controlled, containment-capable and connected, but not an endpoint-reader or
multi-environment laboratory. Matched against it, the current design is executable in Cell~01; the improved design
lacks only a vehicle stock and, with it, needs two dosing sessions per time point (at most @@wps@@ wells fit an
excursion); an ATP endpoint is executable on site with a transfer to an ILLUSTRATIVE core plate reader; and a design
with an oxygen factor is not executable, because no laboratory provides two environments.

\paragraph{Limits.} The CRAM plans are not executed (no Lisp CRAM is installed); the factors and analysis plan exist
in the OWL layer but not yet in the authored LDL; BFO and OBI are followed in style, not imported; the replication
minimum and the information target are illustrative criteria; in vivo and clinical experiments are outside the
current taxonomy (Section~\ref{sec:limits}).
""")

    T.append(r"""
\section{Motivation and scope}\label{sec:motivation}
Laboratory automation has made it routine for robots to \emph{perform} protocols. Robot scientists such as Adam and
Eve \citep{king2009,williams2015} went further and closed the loop from hypothesis to experiment to analysis, and
self-driving laboratories in chemistry and materials science \citep{burger2020,abolhasani2023} have shown how far
closed-loop experimentation can go when the experiment space is well parameterised. Biomedical experiments are
harder to parameterise: the system is alive, the quantities of interest are hidden and reached only through proxies,
and whether an experiment supports its conclusion depends on its \emph{logic}---which cultures are compared, what
they differ in, which controls exclude which alternative explanation---more than on any single step. Poor design is
one of the recognised causes of irreproducible biomedical results \citep{baker2016}, and reporting guidelines such
as ARRIVE \citep{kilkenny2010} and CONSORT \citep{schulz2010} exist largely to make that logic explicit after the
fact.

For a robot scientist the logic has to be explicit \emph{before} the fact, in a form a program can inspect. The RSA
already derives culture-level plans, refines them into lab actions and motions, and audits their execution (see the
companion report on the RSA kernel). What it lacked was a representation of the experiment \emph{as an experiment}:
of its question and hypotheses, its units and their roles, its treatments, its comparisons and their purpose, and
the standards against which a design is judged. This report fills that gap. Its contributions are:
\begin{enumerate}
\item a sequence of representations of one experiment, from an ordered list of actions to a variable-free entity
  designator organised by the experiment's logic, with the actions and their order derived and checked
  (Sections~\ref{sec:case}--\ref{sec:authored});
\item a conceptual framework for biomedical experiments in five layers, with core concepts, a multi-axial taxonomy,
  validity criteria assigned to enforcement mechanisms, and a lifecycle (Section~\ref{sec:framework});
\item a partonomy that separates process, material and plan parthood from containment, membership, participation and
  realization (Section~\ref{sec:partonomy});
\item two formalisations: an LDL concept hierarchy with a closed-world checker (Section~\ref{sec:ldlconcepts}) and an
  OWL~2~DL axiomatization with defined concepts, classified and checked by HermiT (Sections~\ref{sec:dlv1}--\ref{sec:results});
\item an evaluation on the case study and on an improved design, with negative controls at every level.
\end{enumerate}
The scope is the in-vitro injury--rescue family of experiments; the framework is written to extend beyond it, and
Section~\ref{sec:limits} lists what that extension still requires.
""")

    T.append(r"""
\section{Background}\label{sec:background}
\subsection{Experimental design}
The vocabulary of controlled experimentation goes back to Fisher \citep{fisher1935}: experimental units, treatments,
replication to estimate chance variation, randomisation to protect against systematic bias, and blocking to remove
known sources of variation. For laboratory biology, Lazic \citep{lazic2016} gives a modern account; it stresses that
the experimental unit is the entity \emph{independently} assigned to a treatment (a culture, not a measurement of it),
that technical and biological replicates answer different questions, and that controls are defined by what they rule
out. Factorial designs vary several factors at once and make their interactions estimable. Clinical trials use the
same notions under other names: arms, epochs and the cells of an arm-by-epoch grid, as formalised in the CDISC Study
Design Model \citep{cdisc_sdm}.

\subsection{Ontologies of experiments}
Ontologies of scientific experiments were proposed early: EXPO \citep{soldatova2006} describes experiments as
investigations with hypotheses, designs, objects and results; EXACT \citep{soldatova2008} describes protocols as
sequences of actions. The Ontology for Biomedical Investigations (OBI) \citep{brinkman2010,bandrowski2016}, part of
the OBO Foundry \citep{smith2007}, models investigations as planned processes that realize plans, assays with
specified inputs and outputs, study designs and their independent variables, and roles borne by material entities;
it is built on the Basic Formal Ontology (BFO) \citep{arp2015}, which separates continuants (material entities,
qualities, roles, dispositions) from occurrents (processes). The ISA framework \citep{sansone2012} carries
investigation, study and assay metadata for data deposition. The framework of this report follows BFO and OBI in
style---planned processes execute plans, roles and dispositions are borne, data are about qualities---without
importing them (Section~\ref{sec:limits}).

\subsection{Description logics and OWL}
Description logics \citep{baader2003} are decidable fragments of first-order logic built from concepts and roles.
$\mathcal{SROIQ}(\mathbf{D})$ \citep{horrocks2006} underlies OWL~2~DL \citep{owl2}: it adds role hierarchies,
transitivity, inverse roles, role chains, qualified number restrictions and datatypes. Number restrictions are
allowed only on \emph{simple} roles (roles that are neither transitive nor composite, and have no such sub-roles).
OWL reasons under the open-world assumption: what is not stated is unknown, not false. Checking that a design
\emph{contains} something is therefore a closed-world question, usually answered with constraint languages such as
SHACL \citep{shacl2017} or with integrity-constraint semantics \citep{motik2009}. Concrete domains with feature chains
\citep{baader1991} can compare data values reached by different paths, which OWL~2 cannot. HermiT \citep{glimm2014} is
a hypertableau reasoner for OWL~2; Owlready2 \citep{lamy2017} embeds ontologies and reasoners in Python.

\subsection{Plans and Bayesian design in the RSA}
The RSA represents plans in a lab designator language (LDL) and executes them as structured reactive controllers in
the style of RPL and CRAM \citep{mcdermott1991,beetz2001,beetz2010}; knowledge comes from a KnowRob-style ontology
\citep{tenorth2013}. Designs are chosen by expected information gain \citep{lindley1956,chaloner1995}: the mutual
information between the hypotheses and the outcome of a candidate design, estimated by nested Monte Carlo over Cell~01's
surrogate.
""")

    T.append(r"""
\section{The challenge--rescue experiment}\label{sec:case}
\subsection{System, question and hypotheses}
The units are organoid cultures in wells of a microplate, kept in an incubator under a standard culture environment.
Cell~01's surrogate describes each culture by hidden states---injury, an adaptive protective response, a
glutathione-like protective reserve, and viability---driven by two abstract agents: a \emph{challenge} that raises
injury and consumes the reserve, and a \emph{rescue} that restores the reserve and supports recovery. The structure
resembles classic toxicology paradigms in which an antidote's efficacy depends on how late it is given; the project
names no agent, doses are in arbitrary units (au), and every coefficient is a placeholder (D016). Organoid cultures
\citep{sato2009} are a natural target for such experiments because their morphology can be imaged without
destroying them.

Earlier (simulated) data showed that a rescue at 6~h is effective at every challenge dose tested. The open question is
what happens when the rescue comes much later. Table~\ref{tab:hyp} lists the competing hypotheses and the effect each
predicts for the selected design; the effect is the difference in organoid radius between the rescued and the
challenge-only culture at 72~h.
""")
    rows = [["M1 graded", "recovery declines smoothly with injury and delay; no point of no return", "@@pred_M1@@ $\\pm$ @@sd_M1@@"],
            ["M2 threshold", "once cumulative injury exceeds a threshold, the culture loses its capacity to recover", "@@pred_M2@@ $\\pm$ @@sd_M2@@"],
            ["M3 protective", "as M2, but the adaptive response raises the threshold", "@@pred_M3@@ $\\pm$ @@sd_M3@@"]]
    T.append(table(["p{2.4cm}", "X", "p{2.6cm}"], ["hypothesis", "claim", "predicted effect (µm)"], rows,
                   "The three recovery hypotheses and their predicted rescue effects for design \\texttt{@@design@@} "
                   "(surrogate, ILLUSTRATIVE).", "tab:hyp"))
    T.append(r"""
\subsection{The selected design}
The planner scored 45 candidate designs (three challenge doses, five rescue delays, one to three wells per arm) by
expected information gain and selected the cheapest design that reaches the required 0.5~bit
(Figure~\ref{fig:eig}). Expected gain grows with the delay, because the hypotheses agree at short delays (all were
calibrated to the effective 6~h rescue) and diverge only at long ones; at 48~h and the highest dose, one well per arm
already gives @@eig@@~bit, and two or three wells give @@eig_n2@@ and @@eig_n3@@~bit. The resulting design has three
cultures on plate P17: \emph{rescued} (challenge 0.85~au at 0~h, rescue 0.70~au at 48~h, well A01),
\emph{comparator} (challenge only, A02) and \emph{control} (untreated, A05), all imaged at 72~h.
""")
    T.append(figure("eig.pdf", "Expected information gain of the candidate designs over the three hypotheses. Left: one "
                    "well per arm, by dose and delay; the selected design is circled. Right: the selected dose with one to "
                    "three wells per arm. Surrogate, ILLUSTRATIVE.", "fig:eig"))
    T.append(r"""
\subsection{What a run shows}
Executed on the surrogate (Figure~\ref{fig:culture}), the challenge shrinks both challenged cultures; after the
rescue at 48~h the rescued culture partly recovers. At 72~h the radii are @@r_cr@@~µm (rescued), @@r_cc@@~µm
(comparator) and @@r_ck@@~µm (control). The validity comparison shows that the challenge injured the cultures
(@@eff_v@@~µm); the primary comparison gives a rescue effect of @@eff@@~µm. With a measurement noise of
$\sigma \approx$ @@sigma@@~µm, the posterior over the hypotheses moves from uniform to M1 @@p1@@, M2 @@p2@@, M3
@@p3@@: the entropy falls from @@h0@@ to @@h1@@~bit, a gain of @@ig@@~bit in this run against @@eig@@~bit expected.
In biological terms: no hard point of no return at 48~h, but a late rescue is clearly weaker than an early one. M2
and M3 predict nearly the same effect in this design; it separates graded from threshold-like recovery, not the two
threshold variants from each other.
""")
    T.append(figure("culture.pdf", "Surrogate run of the selected design: organoid radius of the three cultures over culture "
                    "time (left) and the belief over the hypotheses before and after the analysis (right). ILLUSTRATIVE.",
                    "fig:culture"))
    T.append(r"""
\subsection{How a biomedical reviewer would judge it}
As a real experiment the design would not stand. It has one culture per arm, so culture-to-culture variation cannot be
separated from the treatment effect. It has no rescue-only arm, so part of the rescue effect might be a general growth
effect of the rescue agent rather than rescue of injury. Its control receives nothing while the treated wells receive
liquid, so solvent and volume effects are confounded with the challenge. Its wells lie on the plate's edge row, where
evaporation and temperature effects are strongest. It has a single delay and a single readout, and organoid size is
only a proxy for viability. These are exactly the kinds of defects that a representation of the experiment
\emph{as an experiment} should make visible; Section~\ref{sec:results} shows that the final axiomatization does.
""")

    rows = [["1", "culture-level plan", "\\texttt{culture\\_plan.ldl}", "12 actions with physical and knowledge effects",
             "order from causal links (@@n_cp_links@@: @@n_cp_phys@@ physical, @@n_cp_know@@ knowledge)"],
            ["2", "CRAM/RPL controller", "\\texttt{culture\\_plan\\_src.lisp}", "control flow, policies, failure handling",
             "partial order = derived order; refinement into lab designators 8/8"],
            ["3", "experiment as an entity", "\\texttt{challenge\\_rescue\\_experiment.lisp}", "question, materials, rules, steps, insights",
             "one-line top-level plan: \\emph{conduct} the experiment"],
            ["4", "nested designators with roles", "(superseded)", "every participant fills a role; no variables",
             "references identify one step each; after-roles = derived order"],
            ["5", "organised by logic", "(superseded)", "cultures with treatments, shared conditions, comparisons",
             "single difference per comparison; 12/12 actions regenerated"],
            ["6", "authored experiment designator", "\\texttt{experiment.ldl}", "the logic; validity comparison explicit",
             "@@n_x@@ actions and order derived; vs.\\ the hand-written plan"],
            ["7", "LDL concept hierarchy", "\\texttt{experiment\\_concepts.ldl}", "5 experiment concepts, partonomy, procedure",
             "closed-world conformance, classification, @@n_v1_neg@@ negative controls"],
            ["8", "DL statement (v1)", "\\texttt{experiment\\_dl.pdf}", "the LDL concepts in $\\mathcal{SROIQ}(\\mathbf{D})$",
             "simple-role restriction; expressivity of each check"],
            ["9", "OWL~2~DL axiomatization (v2)", "\\texttt{experiment.ofn}", "BFO-style biomedical ontology, defined classes",
             "HermiT consistency, classification, realization; closed-world queries"]]
    T.append(r"""
\section{From action lists to experiment logic}\label{sec:evolution}
Table~\ref{tab:evolution} summarises the representations the experiment went through. Each step was prompted by
something the previous one made hard to see; each is generated from the one before it or from its source, and each
was checked mechanically.
""")
    T.append(table(["p{0.3cm}", "p{3.0cm}", "p{3.7cm}", "X", "X"], ["", "representation", "file", "explicit", "derived / checked"],
                   rows, "Nine representations of the challenge--rescue experiment.", "tab:evolution", size="footnotesize"))
    T.append(r"""
\subsection{The culture-level plan}
The first representation states only what is done to the cultures, how they are observed and how the observations
are interpreted and analysed; no plate, instrument or robot appears. Every action states a \emph{physical} effect (on
the cultures' state) and a \emph{knowledge} effect (records, images, estimates, the belief). The order is not written:
it is derived from causal links, a link holding when an effect of one action entails a requirement of another.
Listing~\ref{lst:cp} shows three of the @@n_cp@@ actions; Figure~\ref{fig:poset12} shows the derived order. The plan
is precise, but its logic is implicit: that the comparator exists to isolate the rescue, or that the control licenses
the comparison, can only be reconstructed from requirement lists.
""")
    cpl = src(os.path.join(LAB, "culture_plan.ldl"), "(an action ?c1", "(knowledge (a record (of ?c1)")
    cpa = src(os.path.join(LAB, "culture_plan.ldl"), "(an action ?a1", "(information-gain measured")
    T.append(listing(cpl + "\n    ...\n" + cpa, "Two of the twelve actions of the culture-level plan (\\texttt{culture\\_plan.ldl}).", "lst:cp"))
    T.append(figure("poset12.pdf", "Order of the twelve culture actions, derived from causal links over physical (solid) and "
                    "knowledge (dashed) effects.", "fig:poset12", width="0.85\\linewidth"))
    T.append(r"""
\subsection{The plan as a CRAM/RPL controller}
The culture plan was then generated as a top-level CRAM/RPL controller: one action plan per culture action type, each
waiting for its requirements, performing its refinement (a lab action designator, or a computation for interpreting
and analysing) and asserting its effects; a partial order of the twelve designators; and a top-level function that
binds the cultures, substances and belief, verifies the given state, runs the plan under the plan's own policies (the
control stays untreated, no contamination, standard environment) and restores the safe state on any exit. The
generator checks that the partial order equals the derived order and that the refinement templates reproduce the lab
designators of the lab-level plan for all eight lab-refined actions. The controller was correct but, as a
representation of the experiment, opaque: the experiment's purpose was dispersed over control structures.
""")
    T.append(r"""
\subsection{The experiment as an entity, and roles}
The third and fourth representations turned the experiment into one entity designator---question, hypotheses,
materials, rules, steps and insights---performed by a one-line top-level plan, \texttt{(perform (an action (type
conducting) (experiment \ldots)))}, whose generic action plan derives everything from the entity. Nesting entity
designators with roles removed all variables: every participant fills a named role, and every later mention is a
definite description that identifies one entity, such as \texttt{(the culture (role rescued))}; steps refer to the
steps they follow by the shortest identifying description. The generator checks that every reference identifies
exactly one step and that the \texttt{after} roles equal the derived order.
""")
    T.append(r"""
\subsection{Organised by the experiment's logic}
Organising the entity by steps still hid the logic. The experiment is three cultures, each defined by its treatment,
kept under shared conditions and observed the same way; comparisons between cultures that differ in exactly one
exposure determine the effects. Rescued and comparator differ only in the rescue, so their difference measures the
rescue's effect; comparator and control differ only in the challenge, so their difference shows that the challenge
injured the cultures---the precondition for there being anything to rescue. Written this way, the twelve actions
follow from the structure and were regenerated exactly, and the second comparison, which the culture plan expressed
only as a requirement of the analysis, became explicit.
""")

    T.append(r"""
\section{The authored experiment designator}\label{sec:authored}
The organised form became the authored source, \texttt{experiment.ldl} (Listing~\ref{lst:xldl}). It has no
variables and no lab entities. The generator \texttt{experiment\_designator.py} checks that every comparison isolates
exactly one exposure---the one whose effect it determines---and refuses to proceed otherwise; derives the culture
actions (an intervention per exposure, growth between the treatment times, an observation and an interpretation per
culture, an analysis per comparison, with a licensed comparison's analysis requiring the licensing one's finding);
writes them in the format of the culture plan; and derives their order with the same causal-link machinery.
""")
    T.append(listing(src(os.path.join(LAB, "experiment.ldl"), "(an experiment"), "The authored experiment designator "
                     "(\\texttt{rsa/registry/lab/experiment.ldl}).", "lst:xldl", size="tiny"))
    C = xd["comparison"]
    T.append(r"""
The derivation yields @@n_x@@ actions ordered by @@n_x_links@@ causal links (@@n_x_phys@@ physical, @@n_x_know@@
knowledge): @@order@@ (Figure~\ref{fig:order13}). Compared with the hand-written plan, all @@matched@@ of its actions
are reproduced and one is added, the validity analysis \texttt{v1}; the primary analysis now waits for v1's finding
that the challenge's effect is established, so the belief is not updated unless the challenge worked. The order
changes accordingly: the edges """ + ", ".join(f"{a[1:]}$\\to${b[1:]}" for a, b in C["edges_removed"]) +
             r""" are replaced by """ + ", ".join(f"{a[1:]}$\\to${b[1:]}" for a, b in C["edges_added"]) + r""". Two
effects that the hand-written plan states are not stated in the authored source (""" +
             "; ".join(esc(e[1].replace("?", "")) for e in C["effects_not_stated"]) + r"""); neither affects the order.
""")
    T.append(figure("order13.pdf", "The @@n_x@@ culture actions derived from \\texttt{experiment.ldl}: interventions (red), "
                    "growth (yellow), observations (blue), interpretations (violet), analyses (green); solid edges are "
                    "physical links, dashed edges knowledge links.", "fig:order13"))
    T.append(r"""
The top-level plan performing the designator is one \texttt{perform} of a \texttt{conducting} action whose
\texttt{experiment} role is filled by the entire designator, enriched with the placement chosen by the mapping to
Cell~01 (plate P17, wells A01, A02, A05), the models' predictions and the checked single differences
(Listing~\ref{lst:top}).
""")
    top = src(os.path.join(OUT, "challenge_rescue_designator.lisp"), "(def-top-level-cram-function", "(question (a question")
    T.append(listing(top + "\n                               ...", "The head of the top-level plan "
                     "(\\texttt{rsa/out/challenge\\_rescue\\_designator.lisp}).", "lst:top"))

    T.append(r"""
\section{A conceptual framework for biomedical experiments}\label{sec:framework}
\subsection{Core idea}
\emph{An experiment is a planned process that intervenes on and observes a biological system, executing a design, in
order to change a belief about hypotheses.} The framework keeps four things apart because most errors in practice
come from confusing them: what is \emph{planned} (design and protocol), what \emph{happens} (execution), what is
\emph{measured} (data) and what is \emph{believed} (hypotheses, belief, conclusions). The biology is the hidden state in
between, reached only through interventions and through readouts that are proxies for it. No biological fact or
parameter is asserted by the framework: hypotheses \emph{posit} biology, data are \emph{proxies} (D016).
""")
    T.append(figure("framework.pdf", "The five layers of the framework. Downward relations (black) connect the plan to "
                    "the system; upward relations (red) carry evidence back to the belief.", "fig:framework", width="0.95\\linewidth"))
    T.append(r"""
\subsection{Five layers}
The \textbf{epistemic layer} holds the question, the competing hypotheses, their predictions, the belief over them,
the objective (here: discriminate the hypotheses with at least a target information gain) and the conclusions. The
\textbf{design layer} holds the units, factors and levels, arms, controls, replication, allocation, readouts,
comparisons and the analysis plan---everything decided before anything is done to a culture. The \textbf{protocol
layer} details each kind of step (how to dose, incubate, image and analyse), device-independent and with tolerances.
The \textbf{execution layer} is the run: phases, steps, participants, times, deviations, the refinement into lab
actions and the audit trail. The \textbf{biological system} is the cultures, organoids, cells, medium, agents with
their roles and dispositions, their qualities, and the biological processes they undergo. Each layer is linked to the
next by one kind of relation (Figure~\ref{fig:framework}): the experiment \emph{executes} the design; steps
\emph{realize} parts of the plan; cultures \emph{participate} in steps; data are \emph{about} qualities and are
\emph{proxies for} hidden states; effect estimates \emph{update} the belief; conclusions are \emph{derived from}
evidence.
""")
    concepts = [
        ["experimental unit", "what is treated independently and measured: a culture in a well"],
        ["factor, level", "what is varied (agent, dose, time of rescue) and the values it takes"],
        ["treatment", "one combination of levels, given as a schedule of administrations"],
        ["arm", "a treatment and the units assigned to it; units are members of an arm, not its parts"],
        ["control", "an arm defined by what it controls for: negative (untreated, vehicle), positive (expected effect from "
                    "prior evidence), agent-alone (the agent's own effect), comparator (isolates one factor)"],
        ["replicate", "units under the same treatment; biological (independent units) vs.\\ technical (repeated measurement)"],
        ["allocation", "assignment and placement of units: randomisation, blocking, avoiding edge wells, blinding"],
        ["readout", "what is measured, when, by which assay, and what it is a proxy for (size for viability)"],
        ["comparison", "a pair of arms whose difference estimates the effect of exactly one factor"],
        ["interaction contrast", "a difference of comparisons: whether one factor's effect depends on another"],
        ["validity check", "a comparison that licenses another (the injury happened; the agent works)"],
        ["analysis plan", "one decision rule per comparison and a rule for deviations, fixed before the run"],
        ["hypothesis, prediction", "a model that posits processes, and its expected effect for a comparison"],
        ["belief, information gain", "a probability over hypotheses, and how much a design is expected to change it"],
        ["deviation", "a difference between execution and plan; it can invalidate comparisons"],
        ["conclusion (insight)", "a statement derived from effect estimates and the posterior, with provenance"]]
    T.append(table(["p{3.2cm}", "X"], ["concept", "meaning"], concepts, "Core concepts of the framework.", "tab:concepts"))
    T.append(r"""
\subsection{A multi-axial taxonomy}
Biomedical experiments are classified along independent axes, so the taxonomy is a polyhierarchy rather than a tree:
the \emph{system} (in silico, in vitro---cell line, primary cells, organoid---ex vivo, in vivo, clinical); the
\emph{purpose} (exploratory, confirmatory, hypothesis-discriminating, dose--response, time-course, screening); the
\emph{design structure} (comparative, controlled, factorial, within- or between-unit, randomised, blinded); the
\emph{intervention} (challenge, therapy or rescue, both); and \emph{adequacy} (validated, agent-controlled,
positive-controlled, replicated, pre-specified). Because classes are \emph{defined} rather than merely named, a
reasoner places an experiment under every class it satisfies; the challenge--rescue experiment is, at once, in vitro,
hypothesis-discriminating, a controlled injury--rescue experiment and validated---but not adequately controlled.
""")
    enf = [["internal", "single factor per comparison; negative, agent-alone and positive controls; randomisation; blinding",
            "defined classes (reasoner); closed-world checks"],
           ["statistical", "biological replicates; expected information or power", "closed-world counts; information-gain model"],
           ["construct", "readout states its proxy relation; manipulation checked by a validity comparison",
            "ontology; licensing order in the plan"],
           ["executional", "identity, contamination and environment kept; plan realized; deviations recorded",
            "run-time monitors (CRAM policies); audit trail"],
           ["external", "relevance of the system to the target biology", "stated as an assumption, never inferred"]]
    T.append(table(["p{1.9cm}", "X", "p{4.6cm}"], ["validity", "criteria", "enforced by"], enf,
                   "Validity criteria and the mechanism that enforces each.", "tab:enforce"))
    T.append(r"""
\subsection{Criteria and their enforcement}
Table~\ref{tab:enforce} assigns each kind of validity to the mechanism able to enforce it. The principle is a division
of labour: \emph{description logic for what experiments are; closed-world queries for what a design must contain;
run-time monitors for what an execution must keep; probabilistic models for what it will tell us}. A design's
adequacy is thus checked before the run, an execution's integrity during it, and the information it yields after it,
each by the formalism suited to the question.

\subsection{Lifecycle}
The framework is used along a lifecycle: question $\rightarrow$ hypotheses and predictions $\rightarrow$ candidate
designs $\rightarrow$ selection by information and cost $\rightarrow$ \textbf{adequacy check before the run}
$\rightarrow$ protocol $\rightarrow$ refinement into lab actions $\rightarrow$ monitored execution $\rightarrow$ data
$\rightarrow$ analysis by the pre-specified rules $\rightarrow$ belief update $\rightarrow$ conclusions $\rightarrow$ next
question. Each step reads and writes one layer, and the audit trail links them. In the RSA, selection is the
information-gain planner, the adequacy check is the reasoner of Section~\ref{sec:owl} together with the closed-world
queries of Section~\ref{sec:closed}, refinement and execution are the LDL and CRAM layers, and the belief update is
the posterior over the recovery models.

\subsection{Design principles}
Five principles recur. \emph{Plans are information.} A design is an information entity that a process executes;
the same design can be run many times, and each run is classified by its design. \emph{Membership is not
parthood.} A culture is assigned to an arm; it is not part of it, and a level is shared by the arms at that level.
\emph{Roles and dispositions are borne.} An agent is a challenge because it bears that role in this experiment, and a
toxicant because it bears a toxicity disposition; the role is given because of the disposition. \emph{Data are
proxies.} A size datum is about organoid size and is a proxy for viability, never viability itself. \emph{Hypotheses
posit.} A threshold hypothesis posits a loss of recovery capacity; nothing in the ontology asserts that it occurs.
""")

    rel = [["hasPart", "parthood", "transitive; kind-preserving", "—"],
           ["hasPhase, hasStep", "process parthood", "experiment $\\to$ phases $\\to$ steps", "cultivation phase has step x1"],
           ["hasWell, hasOrganoid, hasCell, hasMedium", "material parthood", "plate $\\to$ wells; culture $\\to$ organoids, medium",
            "P17 has well A01"],
           ["hasArm, hasFactor, hasLevel, hasAdministrationSpec, hasComparisonSpec, hasReadout, hasAnalysisPlan, hasDecisionRule",
            "plan parthood", "design $\\to$ arms, factors, comparisons, readout, analysis plan; arm $\\to$ administrations",
            "design has arm rescued"],
           ["contains / containedIn", "location", "well contains culture; chain containedIn $\\circ$ partOf $\\sqsubseteq$ locatedIn",
            "A01 contains the rescued culture"],
           ["assignedTo", "membership", "unit $\\to$ arm (functional)", "rescued culture assigned to arm rescued"],
           ["atLevel", "plan reference", "arm $\\to$ factor level (shared between arms)", "arm rescued at level rescue 0.7au\\_48h"],
           ["hasParticipant", "participation", "chain hasPart $\\circ$ hasParticipant $\\sqsubseteq$ hasParticipant", "x1 has input the rescued culture"],
           ["executes", "realization", "process $\\to$ plan part", "x1 executes the challenge administration"],
           ["bearerOf / inheresIn", "dependence", "continuant $\\to$ role, disposition, quality", "agent bears the challenge role"]]
    T.append(r"""
\section{Partonomy}\label{sec:partonomy}
Parthood is the backbone of any representation of experiments, and also its most common source of error: a culture is
not part of an arm, a well is not part of a treatment, an instrument is not part of an assay. The framework therefore
has one transitive parthood relation with three kinds of sub-relations, and keeps every other whole--part-like
relation separate (Table~\ref{tab:partonomy}). Parthood is \emph{kind-preserving}: processes have processes as parts,
material entities material entities, information entities information entities. The kinds of parthood are
\emph{simple} sub-roles of the transitive \emph{hasPart}, so they may be counted (exactly three phases, at most four
arms) without violating the OWL~2 restriction on number restrictions.
""")
    T.append(table(["p{3.9cm}", "p{2.2cm}", "X", "p{3.3cm}"], ["relation", "kind", "connects", "example"], rel,
                   "Parthood and the relations kept apart from it.", "tab:partonomy", size="footnotesize"))
    T.append(r"""
Figure~\ref{fig:partonomy} shows the three partonomies of the case study side by side. The process partonomy has the
experiment, its three phases and the @@n_x@@ steps; the material partonomy has the plate and its three wells, which
\emph{contain} (not have as parts) the three cultures; the plan partonomy has the treatments and their exposures.
Interventions \emph{realize} exposures---the dotted edges---which is how the execution is tied to the plan without
either being part of the other.
""")
    T.append(figure("partonomy.pdf", "The three partonomies of the case study: process (top), material and location "
                    "(bottom left), plan (bottom right); dotted edges are realization.", "fig:partonomy"))

    conf = xc["conformance"]
    rows = [[esc(c), str(len(rs)), str(sum(r["ok"] for r in rs))] for c, rs in conf.items()]
    negs = [[esc(n), esc(", ".join(v["fails_at"])), esc(", ".join(v["most_specific"]) or "---")] for n, v in xc["negative_controls"].items()]
    T.append(r"""
\section{The LDL concept layer}\label{sec:ldlconcepts}
Before the DL axiomatization, the experiment concepts were written in LDL itself
(\texttt{experiment\_concepts.ldl}): a specialization hierarchy of @@v1_concepts@@ concepts with @@v1_roles@@ roles,
each concept stating the roles its instances must fill (a pattern and a cardinality), the roles whose fillers are
restricted, and named checks. Five concepts form the experiment hierarchy: \emph{experiment}, then
\emph{comparative} and \emph{hypothesis-discriminating}, then \emph{controlled}, then \emph{challenge--rescue}, which
specializes both branches (Figure~\ref{fig:concepts_v1}). The procedure that derives the actions is attached to
\emph{comparative-experiment} and inherited by every specialization. Listing~\ref{lst:concepts} shows two concepts.
""")
    T.append(listing(src(os.path.join(LAB, "experiment_concepts.ldl"), "(a concept controlled-experiment", "(check rescue-after-challenge))"),
                     "Two concepts of the LDL concept layer (\\texttt{experiment\\_concepts.ldl}).", "lst:concepts"))
    T.append(r"""
The checker \texttt{experiment\_concepts.py} verifies the experiment \emph{as derived and placed}---with its phases and
steps from the procedure and its plate and wells from the mapping---against its concept and all ancestors, checks
every part against its own concept (@@v1_parts@@ parts conform), and classifies it independently. The declared concept
is confirmed as the most specific one; all @@v1_constraints@@ constraints hold (Table~\ref{tab:v1conf}). Each of the
@@n_v1_neg@@ negative controls---modified copies of the design or of its derived plan---fails exactly at the level
whose constraint it breaks and is reclassified under the more general concepts it still satisfies
(Table~\ref{tab:v1neg}).
""")
    T.append(table(["X", "p{2.4cm}", "p{2.2cm}"], ["concept", "constraints", "satisfied"], rows,
                   "Conformance of the experiment to the LDL concept hierarchy.", "tab:v1conf"))
    T.append(table(["p{4.8cm}", "X", "X"], ["modification", "fails at", "still an instance of"], negs,
                   "Negative controls of the LDL concept layer.", "tab:v1neg", size="footnotesize"))
    T.append(figure("concepts_v1.pdf", "The LDL concept hierarchy with each concept's own constraints, checked against the "
                    "experiment; the instance is declared \\texttt{instance-of} challenge-rescue-experiment.", "fig:concepts_v1",
                    width="0.9\\linewidth"))

    from rsa.experiment_dl import checks_dl, DL as DL1
    ch = checks_dl(DL1("txt"))
    rows = [[esc(k), esc(v[0])] for k, v in ch.items()]
    T.append(r"""
\section{A first description-logic statement}\label{sec:dlv1}
The first DL statement (\texttt{experiment\_dl.py}) was generated from the LDL concept file: each \texttt{has}
clause became a qualified number restriction, each \texttt{only} clause a value restriction, a pattern's slots nested
existentials, and \texttt{(role $x$)} the restriction $\exists \mathit{hasRole}.X\mathit{Role}$. Because it was
generated, it could not drift from what the checker checks. Its main value was diagnostic: stating each named check
in the logic it needs (Table~\ref{tab:v1expr}) showed which parts of the experiment concept OWL~2 can carry and which
it cannot. Single difference compares two individuals' sets of exposures and needs first-order logic with counting;
``rescue after challenge'' and the order of phases compare data values reached by different paths and need concrete
domains with feature chains \citep{baader1991}; ``all units on one plate'' is a role-value map, undecidable together
with the rest. The generator also verified that number restrictions are placed only on simple roles.

The first statement had three weaknesses that the second axiomatization removes: the design and the experiment were
one entity, so a plan and its execution could not be told apart; roles were values of a \emph{hasRole} slot rather
than realizable entities borne by participants; and the concepts were \emph{primitive}, so nothing was classified---the
hierarchy was only checked against what was declared.
""")
    T.append(table(["p{5.2cm}", "X"], ["constraint", "logic it needs"], rows,
                   "Expressivity of the named checks of the LDL concept layer.", "tab:v1expr", size="footnotesize"))

    S = XO.tbox()
    sec_rows = [[esc(s["title"]), str(len(s["axioms"])), str(sum(isinstance(a, XO.Eq) for a in s["axioms"]))] for s in S]
    T.append(r"""
\section{The OWL~2~DL axiomatization}\label{sec:owl}
The second axiomatization (\texttt{experiment\_ontology.py}) states the framework as a biomedical ontology in
$\mathcal{SROIQ}(\mathbf{D})$. It is written once, in a small DL syntax embedded in Python, and rendered three ways:
as DL notation (this report and Appendix~\ref{app:tbox}), as OWL functional syntax (\texttt{experiment.ofn}) and as
an Owlready2 ontology \citep{lamy2017} over which HermiT \citep{glimm2014} reasons. It has @@n_ax@@ TBox axioms over
@@n_cls@@ concepts, @@n_obj@@ object properties and @@n_data@@ data properties, in @@n_sec@@ groups
(Table~\ref{tab:tbox}); @@n_eq@@ axioms are definitions ($\equiv$), which is what lets the reasoner classify. The
namespace is \texttt{https://aicor.example/okf/experiment\#}. This section presents the axioms that carry the
framework; the full TBox is in Appendix~\ref{app:tbox}.
""")
    T.append(table(["X", "p{2.2cm}", "p{2.2cm}"], ["group", "axioms", "definitions"], sec_rows,
                   "The TBox by group.", "tab:tbox"))
    T.append(r"""
\subsection{Upper level and partonomy}
Continuants and occurrents are disjoint; material entities, specifically dependent continuants (qualities and
realizable entities) and information content entities are disjoint; roles and dispositions are disjoint realizable
entities; planned and biological processes are disjoint. Parthood is transitive and kind-preserving:
""")
    T.append(axioms([a for a in S[1]["axioms"] if isinstance(a, (XO.Trans,)) and not isinstance(a, (XO.Func, XO.FuncD))][:1]
                    + [a for a in S[1]["axioms"] if isinstance(a, XO.Sub) and isinstance(a.r, XO.All) and a.r.r == "hasPart"]
                    + [a for a in S[1]["axioms"] if isinstance(a, XO.Chain)]))
    T.append(r"""
The bearer relation ranges over specifically dependent continuants---qualities as well as roles and dispositions. An
earlier version restricted it to realizable entities, which made organoid size, every size datum and the executed
experiment's ABox unsatisfiable; HermiT found the error at the first run, and the negative controls were guarded so
that they count only against a consistent base.

\subsection{Biological material, agents and units}
""")
    T.append(axioms(find_ax("OrganoidCulture", "Organoid", "Well", "Toxicant", "ChallengeAgent", "ExperimentalUnit",
                            "RecoveryCapacity", "ToxicityDisposition")))
    T.append(r"""
An organoid culture is organoids in medium; a well holds at most one culture. Agents are chemical entities defined by
the roles they bear in the experiment; the challenge agent is a toxicant because its role is given for its toxicity
disposition. An experimental unit is an organoid culture bearing the experimental-unit role. Recovery capacity and
toxicity are dispositions realized only in recovery and injury processes, respectively.

\subsection{Arms, defined by their treatment}
An arm's class follows from what it administers. With the closure axioms of Section~\ref{sec:closed}, the reasoner
infers these classes from an arm's administration specifications alone:
""")
    T.append(axioms(find_ax("UntreatedArm", "VehicleControlArm", "NegativeControlArm", "ChallengeOnlyArm", "RescueOnlyArm",
                            "ChallengeRescueArm", "PositiveControlArm", "ReplicatedArm")))
    T.append(r"""
\subsection{Factors, levels and comparisons}
A factor has at least two levels; an arm is at one level of each factor; a comparison contrasts the factors in which
its arms differ. A comparison is classified by the arms it compares:
""")
    T.append(axioms(find_ax("Factor", "FactorLevel", "SingleFactorComparison", "InjuryValidityComparison",
                            "RescueEffectComparison", "AgentAloneComparison", "PositiveControlComparison",
                            "RescueTimingComparison", "InteractionContrast")))
    T.append(r"""
\subsection{Readouts and the analysis plan}
A readout measures a quality at a time and may be a proxy for another. The analysis plan has decision rules; a
comparison rule applies to exactly one comparison; a deviation rule applies to none. A design is pre-specified when it
has a readout, an analysis plan, and every comparison is covered by a rule:
""")
    T.append(axioms(find_ax("ReadoutSpecification", "SizeReadout", "ComparisonRule", "BayesianUpdateRule", "DeviationRule",
                            "CoveredComparison", "PreSpecifiedDesign")))
    T.append(r"""
\subsection{Design and experiment classes}
Design classes are defined by arms, comparisons, factors and the analysis plan. Adequate control---the reviewer's
standard---is the conjunction of agent control, a positive control, replication, single-factor comparisons and a
pre-specified analysis. Experiment classes mirror design classes: an investigation executes exactly one design and is
classified by it.
""")
    T.append(axioms(find_ax("ControlledDesign", "InjuryRescueDesign", "ValidatedInjuryRescueDesign",
                            "AgentControlledInjuryRescueDesign", "TherapeuticWindowDesign", "ReplicatedDesign",
                            "WellContrastedDesign", "AdequatelyControlledInjuryRescueDesign", "SufficientlyInformativeDesign",
                            "Investigation", "ValidatedInjuryRescueExperiment")))
    T.append(r"""
\subsection{Phases, steps, data and hypotheses}
A comparative experiment has exactly one cultivation, observation and analysis phase; each phase restricts its steps
(administrations and incubations; assays; data transformations). A size datum is about organoid size and a proxy for
viability. The recovery hypotheses are distinguished by what they posit:
""")
    T.append(axioms(find_ax("ComparativeExperiment", "CultivationPhase", "SizeDatum", "GradedRecoveryHypothesis",
                            "ThresholdRecoveryHypothesis", "ProtectiveResponseHypothesis")))
    T.append(r"""
\subsection{Alignment to Cell~01's biology ontology}
Where a concept means the same as one of Cell~01's biology ontology (\texttt{aicor-biology.ttl}, read only), it is
subsumed by it: @@n_align@@ axioms such as $\mathsf{Organoid} \sqsubseteq \mathsf{bio{:}Organoid}$,
$\mathsf{ChallengeAdministration} \sqsubseteq \mathsf{bio{:}ControlledToxicChallenge}$ and
$\mathsf{ImagingAssay} \sqsubseteq \mathsf{bio{:}ImagingProcess}$. Concepts whose meaning differs (the biology
ontology's models are scientific models, ours are hypotheses that posit processes) are not aligned. Reasoning over both
ontologies together is consistent with no unsatisfiable concept (HermiT @@t_bio@@~s).
""")

    T.append(r"""
\section{Closure and the closed world}\label{sec:closed}
\subsection{Closure axioms}
OWL reasons under the open world. That an arm has a challenge and \emph{no} rescue cannot be concluded from the absence
of a rescue assertion, and the definitions of Section~\ref{sec:owl} contain negations and universal restrictions. The
ABox therefore closes what the design states: every arm has at most as many administrations and assigned units as it
lists, the design at most as many arms and comparisons, and each comparison at most as many contrasted factors.
Together with distinctness assertions, these let HermiT conclude, for example, that the comparator arm---one
administration, which is a challenge specification, disjoint from rescue specifications---is a challenge-only arm, and
that a design all of whose (closed) arms are replicated satisfies $\forall \mathit{hasArm}.\mathsf{ReplicatedArm}$.
The closure of the design's arms had at first been stated over arm specifications only; under the open world another
kind of filler remained possible and the universal restriction could not be concluded, so the closure now ranges over
every filler.

\subsection{Closed-world checks}
What OWL~2 cannot state, or cannot conclude under the open world, is checked by queries over the design as given:
every arm has one level of each factor; each comparison contrasts exactly one factor; the administration schedules of
compared arms differ only at time points belonging to the contrasted factor (vehicle matching); whether the design is a
full factorial (information, not a requirement); whether some interaction is estimable (a complete $2\times2$
sub-table of two factors' levels); every comparison has a decision rule; a positive control licenses the primary
comparison; at least @@min_rep@@ replicates per arm (an ILLUSTRATIVE criterion); units off the plate edge; all units
on one plate; and, for an executed experiment, each administration specification executed exactly once. The
single-factor check replaces the earlier time-point check: the therapeutic-window comparison (late vs.\ early rescue)
differs at two time points but in one factor, the time of rescue.
""")

    # results
    R = xo["results"]

    def real_table(name, cap, label):
        rows = [[r"\texttt{" + esc(i) + "}", ", ".join(rf"$\mathsf{{{t}}}$" for t in ts) or "---"] for i, ts in R[name]["realization"].items()]
        return table(["p{5.0cm}", "X"], ["individual", "inferred most specific concepts"], rows, cap, label, size="footnotesize")
    T.append(r"""
\section{Reasoning results}\label{sec:results}
\subsection{Consistency}
HermiT finds the ontology consistent with the current experiment's ABox (@@t_cur@@~s), with the improved design's
(@@t_imp@@~s), with both together, and with Cell~01's biology ontology, with no unsatisfiable concept in any case.
\subsection{The current experiment}
Table~\ref{tab:real1} lists the most specific concepts the reasoner infers for the design, its arms and comparisons,
the experiment and some steps. Nothing in the table is asserted: the ABox states only administrations, assignments,
comparisons, levels, rules and closures.
""")
    T.append(real_table("challenge_rescue", "Realization of the current experiment (HermiT).", "tab:real1"))
    T.append(r"""
The design is a \emph{validated injury--rescue design}: it has a negative-control arm, a challenge--rescue and a
challenge-only arm, a rescue-effect and an injury-validity comparison. It is also factorial (two factors, challenge and
rescue), well contrasted (each comparison contrasts one factor), pre-specified (both comparisons have a rule: a
threshold rule for validity, a Bayesian update for the primary comparison), hypothesis-discriminating and sufficiently
informative. It is \emph{not} agent-controlled (no rescue-only arm, no vehicle arm), not positive-controlled and not
replicated, and therefore not adequately controlled. The experiment that executes it is classified accordingly.
""")
    T.append(figure("designs.pdf", "The two designs on a time axis: administrations of challenge, rescue and vehicle, and "
                    "imaging at 72~h; under each arm, the classes HermiT infers for it.", "fig:designs"))
    imp = spec2
    rows = [[esc(a.replace("_", " ")), esc(v["levels"]["challenge"]), esc(v["levels"]["rescue_time"]),
             esc("; ".join(f"{ag} {d:g} au at {t:g} h" for ag, d, t in XO.schedule(imp, a))), str(v["units"])]
            for a, v in imp["arms"].items()]
    T.append(r"""
\subsection{An improved design}
The improved design (ILLUSTRATIVE, not run) answers the reviewer: it is a factorial of \emph{challenge} (vehicle,
0.85~au at 0~h) and \emph{time of rescue} (none, 6~h, 48~h), every level vehicle-matched, with @@n_arm2@@ of the six
combinations as arms (Table~\ref{tab:imp}). The early-rescue arm is a positive control: its outcome is expected from
prior evidence (rescue at 6~h was effective at every dose tested), so that a null result at 48~h means that the late
rescue fails, not that the agent or the assay failed in this run. Each arm has three units in randomised interior
wells of one plate, and the analysis plan has a rule for each of the @@n_cmp2@@ comparisons and a deviation rule.
Its expected information gain for the primary contrast is @@eig_n3@@~bit; the surrogate does not model what the
control arms add.
""")
    T.append(table(["p{3.6cm}", "p{1.5cm}", "p{1.7cm}", "X", "p{0.6cm}"], ["arm", "challenge", "rescue time", "schedule", "n"],
                   rows, "Arms of the improved design (ILLUSTRATIVE).", "tab:imp", size="footnotesize"))
    rows = [[esc(c), esc(f"{a} vs {b}".replace("_", " ")), esc(", ".join(XO.contrasted(imp, a, b))),
             esc(" ".join(imp["rules"].get(c, ("—",))[:1])),
             esc(", ".join(f"{x}→{y}" for x, y in imp["licenses"] if y == c) or "—")] for c, (a, b) in imp["comparisons"].items()]
    T.append(table(["p{2.4cm}", "X", "p{2.0cm}", "p{1.6cm}", "p{3.4cm}"], ["comparison", "arms", "contrasts", "rule", "licensed by"],
                   rows, "Comparisons of the improved design.", "tab:impcmp", size="footnotesize"))
    T.append(real_table("improved", "Realization of the improved design (HermiT).", "tab:real2"))
    T.append(r"""
The reasoner classifies the improved design as an \emph{adequately controlled injury--rescue design}, a therapeutic-window
design (two challenge--rescue arms), interaction-aware and deviation-aware (Table~\ref{tab:real2}). The early-rescue
arm is both a challenge--rescue arm and a positive-control arm; the positive-control comparison is also a
rescue-effect comparison, which is correct; and the late-versus-early comparison is a rescue-timing comparison---the
contrast that asks directly whether the rescue's window closes.
""")
    T.append(figure("inferred_arms.pdf", "Inferred taxonomy of arms, with the arms of the current (blue) and improved "
                    "(orange) designs realized under it.", "fig:infarms", width="0.92\\linewidth"))
    T.append(figure("inferred_comparisons.pdf", "Inferred taxonomy of comparisons, with both designs' comparisons.",
                    "fig:infcmp", width="0.92\\linewidth"))
    T.append(figure("inferred_designs.pdf", "Inferred taxonomy of designs, with both designs. Solid edges are subsumptions "
                    "computed by HermiT; dashed edges are realizations.", "fig:infdes"))
    rows = []
    for c1, c2 in zip(R["challenge_rescue"]["closed_world"], R["improved"]["closed_world"] + [None] * 20):
        pass
    cur = {c["check"]: c for c in R["challenge_rescue"]["closed_world"]}
    imp_ = {c["check"]: c for c in R["improved"]["closed_world"]}
    keys = list(dict.fromkeys(list(cur) + list(imp_)))
    rows = [[esc(k), cw_cell(cur[k]) if k in cur else "---", cw_cell(imp_[k]) if k in imp_ else "---",
             esc((cur.get(k) or imp_.get(k))["detail"])] for k in keys]
    T.append(r"""
\subsection{Closed-world checks}
Table~\ref{tab:cw} lists the closed-world checks for both designs. The current design passes the single-factor,
schedule-matching, coverage-by-rules and placement-on-one-plate checks and the execution check, and fails on
interaction estimability (the rescue-only cell is missing), the positive control, replication and edge placement. The
improved design passes every required check; that it is not a full factorial (the vehicle--early-rescue cell is
absent) is reported as information, because no comparison needs that cell.
""")
    T.append(table(["p{4.4cm}", "p{1.2cm}", "p{1.2cm}", "X"], ["check", "current", "improved", "detail (current, else improved)"],
                   rows, "Closed-world checks.", "tab:cw", size="footnotesize"))
    rows = [[esc(v), ", ".join(rf"$\mathsf{{{t}}}$" for t in r["design"]), esc("; ".join(r["failed"]) or "---")]
            for v, r in xo["variants"].items()]
    T.append(r"""
\subsection{Variants}
To check that adequacy is not classified by accident, three variants of the improved design each remove one
ingredient. Each loses exactly the corresponding class and fails exactly the corresponding closed-world check
(Table~\ref{tab:variants}).
""")
    T.append(table(["p{3.8cm}", "X", "p{3.4cm}"], ["variant", "most specific design concepts", "closed-world failures"], rows,
                   "Variants of the improved design.", "tab:variants", size="footnotesize"))
    rows = [[esc(n), r"inconsistent, as required" if ok else r"\textbf{not detected}"] for n, ok in xo["negative_controls"].items()]
    T.append(r"""
\subsection{Negative controls and inferred subsumptions}
@@n_neg@@ modifications must each make the ontology inconsistent; all @@n_neg_ok@@ do (Table~\ref{tab:neg2}). They
exercise kind-preserving parthood, the functionality of assignment, arm closure, the disjointness of what hypotheses
posit, the disjointness of agents, the cardinality of comparison rules, the realization of device functions
(Section~\ref{sec:afford}) and the disjointness of plan parts.
""")
    T.append(table(["X", "p{4.0cm}"], ["modification", "HermiT"], rows, "Negative controls of the OWL axiomatization.",
                   "tab:neg2", size="footnotesize"))
    subs = xo["inferred_subsumptions"]
    T.append(r"""
The reasoner also derives subsumptions that no axiom states; the @@n_inf@@ found are
""" + "; ".join(rf"$\mathsf{{{a}}} \sqsubseteq \mathsf{{{b}}}$" for a, b in subs) + r""". In particular the whole chain
of experiment classes---adequately controlled, validated, injury--rescue, controlled, comparative---is inferred from
the definitions of the design classes they mirror, and the two negative-control arm classes are recognised as
specializations of their disjunction. The remaining subsumptions place design classes under the requirement classes
of Section~\ref{sec:afford}: whatever has an arm requires cultivation, and every injury--rescue design requires dosing.
""")

    T.append(affordance_section())

    std = [["ISA \\citep{sansone2012}", "investigation, study, assay; factors and factor values per sample",
            "design, data", "units, factors, assays", "no comparisons, controls by purpose, adequacy, reasoning"],
           ["OBI \\citep{bandrowski2016}", "planned processes, study designs, assays, roles; BFO", "all five",
            "the style of the upper level, roles, assays", "this work adds defined design classes and adequacy"],
           ["EXPO \\citep{soldatova2006}", "investigations, hypotheses, designs, results", "epistemic, design",
            "hypothesis--design--result link", "no defined control or comparison types"],
           ["CDISC SDM \\citep{cdisc_sdm}", "arms, epochs, cells, activities (clinical)", "design",
            "arms $\\times$ epochs = our arms $\\times$ phases", "clinical only; no logic"],
           ["EXACT \\citep{soldatova2008}, LabOP, Autoprotocol", "protocol steps, parameters, containers", "protocol, execution",
            "our lab designators and CRAM plans", "no design layer"],
           ["ARRIVE \\citep{kilkenny2010}, CONSORT \\citep{schulz2010}", "reporting checklists", "design (reported)",
            "replication, randomisation, blinding, controls", "checked by humans after the fact"]]
    T.append(r"""
\section{Relation to existing standards}\label{sec:related}
Table~\ref{tab:std} relates the framework to existing standards. None of them combines the three things the robot
scientist needs: a design layer with comparisons and controls defined by purpose, a reasoner that classifies designs
from their content, and a link to the plans the robot executes. OBI is the closest in spirit and would be the natural
upper ontology to import; the reporting guidelines list many of the criteria that the closed-world layer checks, but
for human authors and after the fact.
""")
    T.append(table(["p{3.0cm}", "X", "p{1.8cm}", "X", "X"], ["standard", "covers", "layers", "used here as", "gap"], std,
                   "Existing standards and the framework.", "tab:std", size="footnotesize"))

    T.append(r"""
\section{Discussion}\label{sec:discussion}
\paragraph{What the representation buys.} The final representation turns a reviewer's judgement into a computation
before the experiment is run. That the current design lacks agent and positive controls and replication is not a
comment in a report but the absence of a class in a realization; that the improved design has them is a derived fact
with a proof (the reasoner's), not an assertion. The same machinery explains a design: the classes an arm or a
comparison belongs to say what it is for. And because the actions and their order are derived from the design, a
change of design---a new arm, a new comparison---changes the plan the robot executes without hand editing.

\paragraph{Open and closed world.} The division of labour between OWL and the closed-world queries is not a
workaround but a consequence of the questions asked. ``What kind of design is this?'' is a question about what follows
from what is stated, which the open world answers soundly once the design's own extent is closed. ``Does this design
contain three replicates per arm?'' is a question about the design as given, which only the closed world answers.
Making the closure explicit in the ABox, rather than switching to closed-world semantics wholesale, keeps the
classification monotonic: adding an arm can only add classes.

\paragraph{Defined versus primitive concepts.} The LDL concept layer checked an experiment against the concept it
declared; the OWL layer \emph{finds} the concepts an experiment belongs to. The difference matters for a robot
scientist that generates designs: it should not need to know in advance what kind of experiment it has produced.

\paragraph{The proxy and the posit.} Two modelling decisions carry the D016 discipline into the ontology. Data are
proxies: the size datum is about organoid size and a proxy for viability; that viability is what the experiment is
about is visible, and so is the assumption. Hypotheses posit: the threshold hypothesis posits a loss of recovery
capacity; the graded one is defined by not positing it, and a graded hypothesis that posits it is inconsistent. The
ontology can thus represent competing biology without committing to any of it.

\paragraph{The case study as a test.} The case is small, but it exercises every layer: an epistemic objective with
an information target, a design with comparisons of different purposes, a protocol refined into lab actions, an
execution with an audit trail, and a hidden biological state reached through a proxy. The reviewer's critique of
Section~\ref{sec:case} served as an independent specification of what the representation should detect, and it does.
""")

    T.append(r"""
\section{Limitations}\label{sec:limits}
\begin{itemize}
\item \textbf{Not executed.} The CRAM/RPL plans are generated and checked but not executed; no Lisp CRAM is installed.
  The surrogate run is a simulation, and its numbers are ILLUSTRATIVE (D016).
\item \textbf{Two layers not yet joined.} Factors, levels, positive controls and the analysis plan exist in the OWL
  layer; the authored \texttt{experiment.ldl}, the LDL concept checker and the CRAM plans do not have them yet. The
  current design's factors are read off its schedules.
\item \textbf{Upper ontology in style only.} BFO and OBI are followed in style, in an own namespace, not imported;
  the alignment to Cell~01's biology ontology is by subsumption where the meaning is the same.
\item \textbf{Illustrative criteria.} The minimum of three replicates, the 0.5~bit information target and the
  validity criterion (an effect below zero by more than two standard deviations) are placeholders, not recommendations.
\item \textbf{Coverage.} The taxonomy covers in-vitro injury--rescue experiments. Positive controls are defined;
  randomisation is checked only as placement off the plate edge; blinding, blocking, technical versus biological
  replicates, dose--response and time-course designs, and the in vivo and clinical branches are not axiomatized.
\item \textbf{Information of control arms.} The information-gain model covers the primary contrast; it does not
  represent what control arms add (the confounds they exclude are outside the surrogate).
\item \textbf{Laboratory profiles.} Capability verbs are mapped to device functions by a hand-written table; the
  rail-mounted robot's general manipulation is not mapped; the core facility, the vehicle and the durations are
  ILLUSTRATIVE; transfer times between laboratories, assay suitability and costs are not modelled.
\item \textbf{Reproducibility pipeline.} The generators of this report are not yet stages of \texttt{rsa.reproduce};
  adding them would change the manifest hash quoted by the companion report and paper.
\item \textbf{References.} The references were compiled without database access and must be checked before
  publication.
\end{itemize}
""")
    T.append(r"""
\section{Roadmap}\label{sec:roadmap}
\begin{enumerate}
\item \textbf{One source.} Extend \texttt{experiment.ldl} with factors, levels, readouts and the analysis plan; generate
  the OWL ABox, the culture plan and the CRAM plans from it, so that every layer derives from one authored design.
\item \textbf{Adequacy in the loop.} Make the reasoner's classification a constraint of the design planner: among the
  designs that reach the information target, choose the cheapest \emph{adequately controlled} one, and report the
  classes a cheaper design would lose.
\item \textbf{Affordance in the loop.} Restrict the design planner to designs the site affords, and report for
  each rejected design what resource would make it executable (a stock, a reader, an environment).
\item \textbf{Information of controls.} Extend the surrogate and the information-gain model with the confounds the
  control arms exclude (agent effects, vehicle effects, plate position), so that their value is quantified.
\item \textbf{Import the upper ontology.} Replace the BFO-style upper level by BFO and OBI imports, and align the design
  classes with OBI's study-design terms.
\item \textbf{Broaden the taxonomy.} Add blinding, blocking, replicate kinds, dose--response and time-course designs,
  and the in vivo and clinical branches (arms $\times$ epochs).
\item \textbf{Shapes.} Express the closed-world checks as SHACL shapes over the reasoned ABox, so that they are
  portable beyond the RSA.
\item \textbf{Reproducibility.} Add the generators to \texttt{rsa.reproduce} and record the ontology, ABox and reasoner
  results in the manifest.
\end{enumerate}
""")
    return "\n".join(T)


def appendices():
    A = [r"\appendix", r"\section{The TBox in DL notation}\label{app:tbox}",
         r"The complete TBox as generated from \texttt{rsa/experiment\_ontology.py}. Concepts are set in $\mathsf{sans}$, "
         r"roles in $\mathit{italics}$."]
    for s in XO.tbox():
        A.append(rf"\subsection*{{{esc(s['title'])}}}{{\small {s['text']}}}")
        A.append(r"{\small\begin{multicols}{2}" if s["title"] in ("Upper level", "Relations and partonomy") else r"{\small")
        A.append(axioms(s["axioms"]))
        A.append(r"\end{multicols}}" if s["title"] in ("Upper level", "Relations and partonomy") else "}")
    A.append(r"\subsection*{Alignment to Cell~01's biology ontology}{\small\begin{multicols}{2}" + axioms(XO.ALIGN) + r"\end{multicols}}")
    A.append(r"\section{ABox of the current experiment (excerpt)}\label{app:abox}")
    A.append(r"The first assertions of the current experiment's ABox, as rendered from the same source as the OWL file.")
    lines = B1.lines("tex")
    A.append(r"{\scriptsize\begin{multicols}{2}" + "\n".join(rf"${x}$\par" for x in lines[:120]) + r"\end{multicols}}")
    A.append(r"\section{OWL functional syntax (excerpt)}\label{app:ofn}")
    ofn = open(os.path.join(XOUT, "experiment.ofn")).read().splitlines()
    pick = [l for l in ofn if l.startswith("EquivalentClasses(xp:ChallengeOnlyArm") or l.startswith("EquivalentClasses(xp:AdequatelyControlled")
            or l.startswith("EquivalentClasses(xp:SingleFactorComparison") or l.startswith("SubObjectPropertyOf(ObjectPropertyChain")
            or "xp:arm_comparator)" in l and l.startswith("ClassAssertion")]
    A.append(listing("\n".join(pick), "Selected axioms and closure assertions in OWL functional syntax "
                     "(\\texttt{rsa/out/experiment\\_ontology/experiment.ofn}).", "lst:ofn", size="tiny"))
    files = [["rsa/registry/lab/experiment.ldl", "the authored experiment designator"],
             ["rsa/registry/lab/experiment\\_concepts.ldl", "LDL concept hierarchy with partonomy"],
             ["rsa/experiment\\_designator.py", "logic check, action derivation, top-level designator"],
             ["rsa/experiment\\_concepts.py", "closed-world conformance, classification, partonomy figure"],
             ["rsa/experiment\\_dl.py", "first DL statement (v1)"],
             ["rsa/experiment\\_ontology.py", "OWL~2~DL axiomatization, HermiT reasoning, closed-world checks (v2)"],
             ["rsa/culture\\_plan.py, rsa/culture\\_to\\_cram.py", "culture-level plan; CRAM/RPL controller"],
             ["rsa/lab\\_affordance.py", "laboratory capability profiles, design requirements, matching"],
             ["rsa/out/experiment\\_ontology/", "experiment.ofn, experiment.owl, experiment\\_owl.pdf, lab\\_affordance.pdf, JSON results"],
             ["report/experiments/build\\_experiments\\_report.py", "this report"]]
    A.append(r"\section{Files and rebuilding}\label{app:files}")
    A.append(table(["p{6.6cm}", "X"], ["file", "content"], files, "Files of the experiment layer.", "tab:files", size="footnotesize"))
    A.append(r"""
To rebuild, run from the repository root:
\begin{itemize}
\item \texttt{env\_cad/bin/python -m rsa.experiment\_designator}
\item \texttt{env\_cad/bin/python -m rsa.experiment\_concepts}
\item \texttt{env\_cad/bin/python -m rsa.experiment\_ontology}
\item \texttt{env\_cad/bin/python -m rsa.lab\_affordance}
\item \texttt{env\_cad/bin/python report/experiments/build\_experiments\_report.py}
\end{itemize}
The report builder re-runs all generators first (\texttt{--no-regen} skips them).
""")
    return "\n".join(A)


# ================================================================================================= references
REFS_NEW = {
    "fisher1935": ("book", {"author": "Fisher, Ronald A.", "title": "The Design of Experiments", "publisher": "Oliver and Boyd",
                            "address": "Edinburgh", "year": "1935"}),
    "lazic2016": ("book", {"author": "Lazic, Stanley E.", "title": "Experimental Design for Laboratory Biologists: Maximising "
                           "Information and Improving Reproducibility", "publisher": "Cambridge University Press", "year": "2016"}),
    "arp2015": ("book", {"author": "Arp, Robert and Smith, Barry and Spear, Andrew D.", "title": "Building Ontologies with "
                         "Basic Formal Ontology", "publisher": "MIT Press", "year": "2015"}),
    "bandrowski2016": ("article", {"author": "Bandrowski, Anita and Brinkman, Ryan and Brochhausen, Mathias and others",
                                   "title": "The Ontology for Biomedical Investigations", "journal": "PLoS ONE", "volume": "11",
                                   "number": "4", "pages": "e0154556", "year": "2016"}),
    "brinkman2010": ("article", {"author": "Brinkman, Ryan R. and Courtot, M{\\'e}lanie and Derom, Dirk and others",
                                 "title": "Modeling Biomedical Experimental Processes with {OBI}", "journal": "Journal of "
                                 "Biomedical Semantics", "volume": "1", "number": "Suppl 1", "pages": "S7", "year": "2010"}),
    "smith2007": ("article", {"author": "Smith, Barry and Ashburner, Michael and Rosse, Cornelius and others",
                              "title": "The {OBO} Foundry: Coordinated Evolution of Ontologies to Support Biomedical Data "
                              "Integration", "journal": "Nature Biotechnology", "volume": "25", "number": "11",
                              "pages": "1251--1255", "year": "2007"}),
    "soldatova2006": ("article", {"author": "Soldatova, Larisa N. and King, Ross D.", "title": "An Ontology of Scientific "
                                  "Experiments", "journal": "Journal of the Royal Society Interface", "volume": "3",
                                  "number": "11", "pages": "795--803", "year": "2006"}),
    "soldatova2008": ("article", {"author": "Soldatova, Larisa N. and Aubrey, Wayne and King, Ross D. and Clare, Amanda",
                                  "title": "The {EXACT} Description of Biomedical Protocols", "journal": "Bioinformatics",
                                  "volume": "24", "number": "13", "pages": "i295--i303", "year": "2008"}),
    "sansone2012": ("article", {"author": "Sansone, Susanna-Assunta and Rocca-Serra, Philippe and Field, Dawn and others",
                                "title": "Toward Interoperable Bioscience Data", "journal": "Nature Genetics", "volume": "44",
                                "number": "2", "pages": "121--126", "year": "2012"}),
    "cdisc_sdm": ("misc", {"author": "{Clinical Data Interchange Standards Consortium}", "title": "{CDISC} Study Design Model "
                           "in {XML} ({SDM-XML})", "howpublished": "CDISC standard", "year": "2011"}),
    "baader2003": ("book", {"author": "Baader, Franz and Calvanese, Diego and McGuinness, Deborah L. and Nardi, Daniele and "
                            "Patel-Schneider, Peter F.", "title": "The Description Logic Handbook: Theory, Implementation and "
                            "Applications", "publisher": "Cambridge University Press", "year": "2003"}),
    "horrocks2006": ("inproceedings", {"author": "Horrocks, Ian and Kutz, Oliver and Sattler, Ulrike", "title": "The Even More "
                                       "Irresistible {SROIQ}", "booktitle": "Proceedings of the 10th International Conference on "
                                       "Principles of Knowledge Representation and Reasoning (KR)", "pages": "57--67", "year": "2006"}),
    "owl2": ("misc", {"author": "{W3C OWL Working Group}", "title": "{OWL} 2 Web Ontology Language Document Overview (Second "
                      "Edition)", "howpublished": "W3C Recommendation", "year": "2012"}),
    "glimm2014": ("article", {"author": "Glimm, Birte and Horrocks, Ian and Motik, Boris and Stoilos, Giorgos and Wang, Zhe",
                              "title": "{HermiT}: An {OWL} 2 Reasoner", "journal": "Journal of Automated Reasoning",
                              "volume": "53", "number": "3", "pages": "245--269", "year": "2014"}),
    "lamy2017": ("article", {"author": "Lamy, Jean-Baptiste", "title": "Owlready: Ontology-Oriented Programming in {Python} with "
                             "Automatic Classification and High Level Constructs for Biomedical Ontologies",
                             "journal": "Artificial Intelligence in Medicine", "volume": "80", "pages": "11--28", "year": "2017"}),
    "baader1991": ("inproceedings", {"author": "Baader, Franz and Hanschke, Philipp", "title": "A Scheme for Integrating "
                                     "Concrete Domains into Concept Languages", "booktitle": "Proceedings of the 12th "
                                     "International Joint Conference on Artificial Intelligence (IJCAI)", "pages": "452--457",
                                     "year": "1991"}),
    "shacl2017": ("misc", {"author": "Knublauch, Holger and Kontokostas, Dimitris", "title": "Shapes Constraint Language "
                           "({SHACL})", "howpublished": "W3C Recommendation", "year": "2017"}),
    "motik2009": ("article", {"author": "Motik, Boris and Horrocks, Ian and Sattler, Ulrike", "title": "Bridging the Gap "
                              "between {OWL} and Relational Databases", "journal": "Journal of Web Semantics", "volume": "7",
                              "number": "2", "pages": "74--89", "year": "2009"}),
    "kilkenny2010": ("article", {"author": "Kilkenny, Carol and Browne, William J. and Cuthill, Innes C. and Emerson, Michael "
                                 "and Altman, Douglas G.", "title": "Improving Bioscience Research Reporting: The {ARRIVE} "
                                 "Guidelines for Reporting Animal Research", "journal": "PLoS Biology", "volume": "8",
                                 "number": "6", "pages": "e1000412", "year": "2010"}),
    "schulz2010": ("article", {"author": "Schulz, Kenneth F. and Altman, Douglas G. and Moher, David", "title": "{CONSORT} 2010 "
                               "Statement: Updated Guidelines for Reporting Parallel Group Randomised Trials", "journal": "BMJ",
                               "volume": "340", "pages": "c332", "year": "2010"}),
    "sato2009": ("article", {"author": "Sato, Toshiro and Vries, Robert G. and Snippert, Hugo J. and others", "title": "Single "
                             "{Lgr5} Stem Cells Build Crypt--Villus Structures in vitro without a Mesenchymal Niche",
                             "journal": "Nature", "volume": "459", "pages": "262--265", "year": "2009"}),
}
REUSE = ["king2009", "williams2015", "burger2020", "abolhasani2023", "baker2016", "mcdermott1991", "beetz2001", "beetz2010",
         "tenorth2013", "lindley1956", "chaloner1995"]


def bibtex(text):
    import paper.build_paper as BP
    refs = {k: BP.REFS[k] for k in REUSE}
    refs.update(REFS_NEW)
    used = []
    for grp in re.findall(r"\\citep\{([^}]+)\}", text):
        used += [c.strip() for c in grp.split(",") if c.strip() not in used]
    missing = [c for c in used if c not in refs]
    assert not missing, missing
    out = []
    for k in used:
        typ, f = refs[k]
        out.append(f"@{typ}{{{k},\n" + ",\n".join(f"  {a} = {{{b}}}" for a, b in f.items()) + "\n}\n")
    return "\n".join(out)


# ================================================================================================= main
def main(argv):
    if "--no-regen" not in argv:
        for g in GENERATORS:
            r = subprocess.run([PY, "-m", g], cwd=ROOT, capture_output=True, text=True, timeout=1800)
            print(f"[regen] {g:28} exit {r.returncode}  {(r.stdout.strip().splitlines() or [''])[-1][:100]}")
    load()
    copy_figs()
    fig_order13()
    fig_designs()
    fig_eig()
    fig_inferred()
    fig_affordance()
    text = PREAMBLE + body() + "\n\\FloatBarrier\n\\bibliographystyle{unsrtnat}\n\\bibliography{refs}\n" + appendices() + "\n\\end{document}\n"
    text = fill(text).replace("\\_", "\\_\\allowbreak{}")
    open(os.path.join(HERE, "refs.bib"), "w").write(bibtex(text))
    open(os.path.join(HERE, "experiments_report.tex"), "w").write(text)
    r = subprocess.run(["latexmk", "-lualatex", "-interaction=nonstopmode", "-halt-on-error", "experiments_report.tex"], cwd=HERE,
                       capture_output=True, text=True, timeout=900)
    logp = os.path.join(HERE, "experiments_report.log")
    log = open(logp, errors="replace").read() if os.path.exists(logp) else ""
    pages = re.search(r"Output written on experiments_report\.pdf \((\d+) pages", log)
    warn = [l for l in log.splitlines() if re.search(r"undefined|Overfull \\hbox \((\d{2,})|Missing character", l)]
    print(f"[report] latexmk exit {r.returncode}; {pages.group(1) if pages else '?'} pages; warnings {len(warn)}")
    for w in warn[:25]:
        print("   ", w[:170])
    if r.returncode:
        print(r.stdout[-3000:])
        return r.returncode
    with zipfile.ZipFile(os.path.join(HERE, "experiments_report_source.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for f in ("experiments_report.tex", "refs.bib", "build_experiments_report.py"):
            z.write(os.path.join(HERE, f), f)
        for f in sorted(os.listdir(FIG)):
            z.write(os.path.join(FIG, f), os.path.join("figures", f))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
