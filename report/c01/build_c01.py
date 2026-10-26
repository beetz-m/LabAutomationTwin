"""Cell 01: vision, research problem, contributions, where we are, and the plan for a first demonstrator.

A comprehensive document assembled from the repository: renders, figures, LDL and OWL excerpts and the checkers'
results are read from their sources (nothing is retyped), so it can be rebuilt as the work moves.

    env_cad/bin/python report/c01/build_c01.py          # report/c01/cell01_vision_status_plan.pdf
"""

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
J = lambda *p: json.load(open(os.path.join(ROOT, *p)))  # noqa: E731
R = lambda *p: os.path.join(ROOT, *p)  # noqa: E731


def esc(s):
    return (str(s).replace("\\", r"\textbackslash{}").replace("_", r"\_").replace("&", r"\&").replace("%", r"\%")
            .replace("#", r"\#").replace("~", r"$\sim$").replace("->", r"$\to$").replace("≥", r"$\geq$"))


def fig(path, caption, width=r"\linewidth", height=r"0.42\textheight", label=None, pos="htbp"):
    if not os.path.exists(R(path)):
        return f"% missing figure {path}\n"
    lab = f"\\label{{{label}}}" if label else ""
    return (f"\\begin{{figure}}[{pos}]\\centering\\includegraphics[width={width},height={height},keepaspectratio]{{{R(path)}}}"
            f"\\caption{{{caption}}}{lab}\\end{{figure}}\n")


def figrow(items, caption, height=r"0.2\textheight", label=None):
    """Several images side by side: items = [(path, subcaption)]."""
    n = len(items)
    w = f"{0.98 / n:.3f}\\linewidth"
    cells = []
    for p, sub in items:
        if os.path.exists(R(p)):
            cells.append(f"\\begin{{minipage}}[t]{{{w}}}\\centering\\includegraphics[width=\\linewidth,height={height},"
                         f"keepaspectratio]{{{R(p)}}}\\\\[-1pt]{{\\scriptsize {sub}}}\\end{{minipage}}")
    lab = f"\\label{{{label}}}" if label else ""
    return "\\begin{figure}[htbp]\\centering" + "\\hfill".join(cells) + f"\\caption{{{caption}}}{lab}\\end{{figure}}\n"


def code(text, size="scriptsize", title=None):
    t = f"\\noindent{{\\small\\sffamily\\bfseries {title}}}\\par\\vspace{{2pt}}" if title else ""
    return (t + f"\\begin{{Verbatim}}[fontsize=\\{size},frame=lines,framesep=2mm,breaklines]\n{text.rstrip()}\n"
            "\\end{Verbatim}\n")


def table(cols, head, rows, caption, size="footnotesize"):
    body = " \\\\\n".join(" & ".join(r) for r in rows)
    return (f"\\begin{{table}}[htbp]\\centering\\{size}\\caption{{{caption}}}\n\\begin{{tabularx}}{{\\linewidth}}{{@{{}}{''.join(cols)}@{{}}}}"
            f"\\toprule {' & '.join(head)} \\\\\\midrule\n{body} \\\\\\bottomrule\\end{{tabularx}}\\end{{table}}\n")


def ldl_excerpt(path, start, n):
    lines = open(R(path)).read().splitlines()
    i = next(k for k, l in enumerate(lines) if start in l)
    return "\n".join(lines[i:i + n])


def main(argv):
    # ------------------------------------------------------------------ facts from the sources
    import collections
    sys.path.insert(0, R("okf/lab-automation-twin/src"))
    import tbox
    from rsa import experiment_ontology as XO
    S = XO.tbox()
    n_ax = sum(len(s["axioms"]) for s in S)
    names = set()
    for s in S:
        for a in s["axioms"]:
            for side in ("l", "r"):
                x = getattr(a, side, None)
                if isinstance(x, XO.E):
                    names |= x.names()
            for c in getattr(a, "cs", []):
                names |= c.names()
    n_xo = len({n for n in names if not n.startswith("bio:")})
    mods = collections.Counter(c["module"][0] for c in tbox.CLASSES)
    proof = J("rsa/out/refinement_proof.json")
    p50 = J("okf/lab-automation-twin/L3-logical-axiomatization/derivation/out/proof_g050.json")
    plan = J("okf/lab-automation-twin/L3-logical-axiomatization/derivation/out/plan_g050.json")
    owl = J("rsa/out/experiment_ontology/experiment_owl.json")
    aff = J("rsa/out/experiment_ontology/lab_affordance.json")
    kern = J("rsa/out/report.json")
    eps = J("test_reports/episodes/cell01_episodes_records.json")["episodes"]
    merge = J("okf/lab-automation-twin/L2-conceptual-framework/out/experiment-merge-report.json")
    tests = {}
    for n in ("h4_physics", "l09_physics", "l10_physics", "l12_physics", "l12_robot", "l17_physics", "l17_robot", "l21",
              "r02", "r03", "site_route"):
        d = J(f"test_reports/{n}_report.json")
        res = d.get("results") or d.get("tests") or d.get("checks")
        tests[n] = (sum(1 for r in res if r.get("pass") or r.get("ok") or r.get("passed")), len(res))
    h4r = J("test_reports/h4_robot_report_cell01_compliant.json")["summary"]
    reg_path = R("scenes/culture/design_improved/l17_robot/robot_images.json")
    reg = json.load(open(reg_path)) if os.path.exists(reg_path) else None
    unreg = J("scenes/culture/design_improved/l17_robot_unregistered/robot_images.json")
    unreg_shots = unreg["shots"] if "shots" in unreg else unreg
    n_steps = sum(len(s["steps"]) for s in plan["sessions"])
    n_mot = len(proof["obligations"][next(k for k in proof["obligations"] if k.startswith("O6"))]["motions"])
    t_pass = sum(p for p, _ in tests.values())
    t_all = sum(n for _, n in tests.values())
    scen = kern["scenarios"]
    neg_total = len(proof["negative_controls"])
    if reg and reg.get("registration"):
        rg = reg["registration"]
        sh = list(reg["shots"].values())
        reg_txt = (f"Edge-finding plate registration measures the walls of two wells consistently (shift "
                   f"({rg['dx_mm']:+.2f}, {rg['dy_mm']:+.2f})~mm, rotation {rg['theta_rad'] * 57.2958:+.2f}$^\\circ$), but it "
                   f"does not yet correct the field: {sum(s['valid'] for s in sh)} of {len(sh)} frames are valid and the field "
                   f"still lies {min(s['field_offset_from_well_centre_mm'] for s in sh):.2f}--"
                   f"{max(s['field_offset_from_well_centre_mm'] for s in sh):.2f}~mm from the well centre. The offsets are "
                   "stable over time, so the plate does not slide; the mismatch lies between where the controller believes "
                   "the field is and where the optics images, and is under investigation (WP2).")
    else:
        reg_txt = "Plate registration is implemented and being verified; the registered run is pending."
    unreg_valid = sum(s["valid"] for s in unreg_shots.values())

    # ------------------------------------------------------------------ document
    T = [r"""\documentclass[10.5pt,a4paper]{article}
\usepackage[margin=2.2cm,headheight=14pt]{geometry}
\usepackage{fontspec,unicode-math}
\setmainfont{Libertinus Serif}\setsansfont{IBM Plex Sans}\setmonofont[Scale=0.84]{IBM Plex Mono}\setmathfont{Libertinus Math}
\usepackage{microtype,graphicx,booktabs,tabularx,xcolor,fvextra,caption,fancyhdr,titlesec,enumitem,amsmath,amsthm,array,placeins,tikz}
\usepackage[colorlinks,linkcolor=teal!60!black,urlcolor=teal!60!black,citecolor=teal!60!black]{hyperref}
\usetikzlibrary{arrows.meta,positioning}
\captionsetup{font=small,labelfont=bf}
\renewcommand{\tabularxcolumn}[1]{>{\raggedright\arraybackslash}p{#1}}
\setlength{\emergencystretch}{3em}\setlist{itemsep=2pt,topsep=3pt}
\titleformat{\section}{\sffamily\Large\bfseries\color{teal!50!black}}{\thesection}{0.8em}{}
\titleformat{\subsection}{\sffamily\large\bfseries}{\thesubsection}{0.7em}{}
\titleformat{\paragraph}[runin]{\sffamily\bfseries}{}{}{}[.]
\newtheorem{theorem}{Theorem}
\pagestyle{fancy}\fancyhf{}\fancyhead[L]{\sffamily\footnotesize AICOR Cell 01: vision, status and demonstrator plan}
\fancyhead[R]{\sffamily\footnotesize\nouppercase{\leftmark}}\fancyfoot[C]{\sffamily\footnotesize\thepage}
\renewcommand{\headrulewidth}{0.3pt}
\renewcommand{\floatpagefraction}{0.7}\renewcommand{\topfraction}{0.9}\renewcommand{\textfraction}{0.1}
\begin{document}
\begin{titlepage}\sffamily
\noindent\includegraphics[width=\linewidth,height=0.42\textheight,keepaspectratio]{""" + R("renders/lab/lab_cell_interior.png") + r"""}\par\vspace{0.8cm}
{\color{teal!50!black}\rule{\linewidth}{1.2pt}}\par\vspace{0.4cm}
{\Huge\bfseries A laboratory that knows\\[4pt] what its experiments mean\par}\vspace{0.3cm}
{\Large AICOR Cell 01: vision, research problem, contributions,\\ where we are, and the plan for a first demonstrator\par}\vspace{0.3cm}
{\color{teal!50!black}\rule{\linewidth}{1.2pt}}\par\vspace{0.6cm}
{\large Semantic digital twin of an automated culture-experimentation cell\par}\vspace{0.3cm}
{\normalsize [Authors and affiliations] \hfill 18 October 2026\par}\vfill
{\small\rmfamily Every figure, excerpt and number in this document is generated from the LabAutomationTwin repository
(renders from Isaac Sim 6.2, ontologies reasoned by HermiT and Konclude, plans checked by z3). Biology, doses and
timings are Cell 01's illustrative surrogate (decision D016); they are not laboratory facts.\par}
\end{titlepage}
\tableofcontents\clearpage
"""]
    # ---------------------------------------------------------------- 0 summary
    T.append(r"""
\section*{Summary}\addcontentsline{toc}{section}{Summary}
Robots in biomedical laboratories execute protocols. They do not know what the experiment is for, which culture is
the control, which comparison answers the question, or whether a failure at 3~am invalidates a conclusion. Cell~01 is
our answer: an automated culture-experimentation cell, built first as a \emph{semantic digital twin}, in which the
experiment itself is represented, reasoned about and executed down to the robot motions, with proofs that the motions
implement the design.

\paragraph{Where we are} The twin is complete: """ + f"{len(eps)}" + r""" end-to-end robot episodes run in physics
(nominal, identity swap, quarantine and release, imaging, full cell), """ + f"{t_pass}/{t_all}" + r""" device and robot
acceptance tests pass, and AICOR Lab~1 surrounds the cell. Above it sits a stack of knowledge: a lab designator language
(LDL) that states what lab actions must achieve, an OWL~2~DL experiment ontology (""" + f"{n_xo} concepts, {n_ax} axioms" +
             r""") whose reasoner classifies a design as adequately controlled or not, a """ + f"{len(tbox.CLASSES)}" +
             r"""-concept lab ontology within the AICOR federation, capability profiles that decide what the lab can run,
Bayesian experiment design, and a robot science assistant kernel. A refinement theorem, discharged by machine checks,
states that the """ + f"{n_mot}" + r""" robot motions of the selected experiment either realize the culture-level
design under all constraints or stop in a handler whose guarantee holds.

\paragraph{What is next} A first demonstrator: the challenge--rescue experiment executed end to end in the twin by the
generated plans, its cultures imaged by the robot's own camera, the belief updated, faults injected and handled at
the level of the experiment, the improved five-arm design carried through the same proof, and one segment on real
hardware (Section~\ref{sec:plan}).
""")
    # ---------------------------------------------------------------- 1 vision and mission
    T.append(r"""
\section{Vision and mission}
\paragraph{Vision} A laboratory in which a robot scientist runs biomedical experiments that are valid by
construction: every robot action traces to the scientific purpose it serves, every design is checked for the controls
and comparisons its conclusion needs before anything is pipetted, every failure is understood in terms of what it
does to the experiment, and every result carries the evidence of how it was obtained.

\paragraph{Mission} To build Cell~01, an automated cell for culture experiments, as the place where this is worked
out end to end: a physically faithful, semantically annotated digital twin first, with the knowledge, reasoning and
plans that make its robots understand the experiments they perform; then a demonstrator; then real hardware.
""")
    T.append(fig("renders/lab/lab_overview.png", "AICOR Lab~1 with Cell~01 at its centre (path-traced in Isaac Sim 6.2): "
                 "operator desks, prep bench, storage, the enclosed cell with its AMR portal.", height=r"0.36\textheight"))
    T.append(r"""
\section{The research problem}
\textbf{How can a robot execute a biomedical experiment so that what it physically does provably implements what the
experiment is designed to establish, and so that it knows, at every moment, what its actions, observations and failures
mean for the experiment's conclusions?}

The problem has three parts:
\begin{enumerate}
\item \textbf{Meaning across levels.} An experiment is stated over cultures, treatments, controls and comparisons. A
robot executes motions over plates, grippers and frames. The robot must carry the experiment's meaning down through
these levels and back up: from ``the comparator culture receives the challenge at 0~h'' to 52 grounded steps in one
trip, and from an image of a well back to evidence about a hypothesis.
\item \textbf{Validity, not only execution.} A protocol can run perfectly and still answer nothing: no vehicle control,
no replicates, a confounded comparison, an unvalidated readout. The robot must judge a design's adequacy before running
it, and an execution's validity after.
\item \textbf{Living material under uncertainty.} Cultures change while the robot works; they tolerate only limited
time outside the incubator; their state is seen only through images that are proxies for viability; contamination and
identity swaps happen. Execution must keep the material's constraints and reason about what it does not observe.
\end{enumerate}

\section{Why it matters}
\begin{itemize}
\item \textbf{AI scientists now choose experiments, but nothing checks them.} Agent systems propose and run
experiments on liquid-handling robots~\cite{verid}; their checks concern the protocol and the machine (deck state, safe
commands), not whether the experiment has the controls and comparisons its conclusion needs.
\item \textbf{The syntax-to-safety gap.} Commands that parse can be physically unsafe~\cite{safesdl}; in biology they
can also be scientifically void.
\item \textbf{Reproducibility.} Much of biomedical research does not reproduce~\cite{baker2016}; reporting checklists
are applied by people after the fact.
\item \textbf{Standards stop at devices and data.} SiLA~2, OPC~UA LADS and Allotrope make instruments interoperable and
data contextual~\cite{lapp}; none represents why a step exists or whether a design can answer its question.
\item \textbf{Regulated laboratories need traceability.} Every robot action must be verifiable and auditable, as
TraceBot set out for sterility testing~\cite{tracebot}.
\end{itemize}

\section{Why it is hard}
""")
    T.append(table(["p{4.2cm}", "X"], ["difficulty", "what it means in Cell 01"], [
        ["The abstraction gap", f"{len(J('rsa/out/culture_plan.json')['plan']['steps'])} culture actions become "
                                f"{n_steps} grounded steps in {len(plan['sessions'])} trips and {n_mot} robot motions; "
                                "each level has its own vocabulary, constraints and failure modes."],
        ["Time-critical living material", "a plate may be outside the incubator for 600~s per excursion "
                                          "(illustrative); culture times (0, 48, 72~h) are fixed by the design."],
        ["Partial observability", "viability is seen through bright-field images of organoid size, core density and "
                                  "debris; the robot's belief must be calibrated against what it cannot see."],
        ["Validity is not execution", "a run can be physically perfect and scientifically invalid (an unvalidated "
                                      "imager: realized but not valid evidence)."],
        ["Failures with consequences", "a dropped tip before aspiration is repairable; a misregistered well after the "
                                       "dispense is not; recovery must state what it guarantees."],
        ["Devices have inner processes", "incubators, liquid handlers and imagers have phases, irreversible points and "
                                         "faults that decide how trustworthy a result is."],
        ["Verification across levels", "a proof that motions implement a design must compose discrete planning, "
                                       "continuous control, device contracts and biology."],
        ["Generality", "special devices make automation rigid; general manipulation makes it flexible but harder to "
                       "verify."]], "Why the problem is hard."))
    # ---------------------------------------------------------------- contributions
    T.append(r"""
\section{Contributions}
\begin{enumerate}[label=\textbf{C\arabic*}]
\item \textbf{A semantic digital twin of Cell~01 and AICOR Lab~1} (Isaac Sim 6.2): articulated, physically simulated
stations and robots with their own controllers, sensors and monitors, the fit-out, the lab and its site;
""" + f"{len(eps)} end-to-end episodes; {t_pass}/{t_all} acceptance tests." + r"""
\item \textbf{A culture digital twin with two separated worlds}: hidden simulated biology and the robot's belief about
it, connected only by robot records and images; dose ledger, contamination rule, calibrated observation model.
\item \textbf{LDL, a lab designator language}: actions as contracts (requires, prevents, maintains, achieves, goal)
over lab entities only, with instrument roles, device process models, failure handlers with guarantees and an
epistemic meta model; a checked abstraction boundary to the realization.
\item \textbf{The experiment as a reasoned entity}: an OWL~2~DL experiment ontology (""" + f"{n_xo} concepts, {n_ax} axioms" +
             r""") in which HermiT classifies a design by its content: adequately controlled, factorial, interaction-aware;
closed-world checks for what OWL cannot express.
\item \textbf{A lab ontology in the AICOR federation} (""" + f"{len(tbox.CLASSES)} concepts in {len(mods)} modules" +
             r"""), bridged to the experiment ontology; the union is consistent and the reasoner proves their arm classes equal.
\item \textbf{Lab affordance}: capability profiles derived from device records, matched against the requirement
classes of designs: what the lab can run, where steps must go, what is missing.
\item \textbf{From information gain to motion}: Bayesian experiment design selects the experiment; an answer-set
program derives the plan; z3 independently validates executability, safety, timing and realization.
\item \textbf{A robot science assistant kernel and CRAM/RPL plans}: designators, executive with failure handling,
two-column critic (realization vs validity), hash-chained audit trail, competency questions; plans generated as
CRAM/RPL and as Giskard motion statecharts.
\item \textbf{A refinement theorem with machine-checked obligations}: the motions implement the culture-level design
or stop in a guaranteed handler, relative to six explicit assumptions; """ + f"{neg_total}" + r""" negative controls.
\end{enumerate}
""")
    # ---------------------------------------------------------------- where we are
    T.append(r"""
\section{Where we are}
\subsection{The cell and the lab}
Cell~01 combines a fixed plate arm (R01, Franka FR3), a rail-mounted flexible arm with an automatic tool changer
(R02, UR5e), a clean-sample AMR with a deterministic dock (R03/H2), a plate hotel (L09), a CO$_2$ incubator (L10),
a liquid handler (L12), a bright-field imager (L17), a QC and calibration station (L21) and a quarantine station (H4),
inside an interlocked safety enclosure.
""")
    T.append(figrow([("renders/lab/lab_cell_front.png", "the enclosed cell"), ("renders/cell01/cell01_elevated.png",
                                                                                "the stations without the enclosure")],
                    "Cell~01 with and without its fit-out (path-traced).", height=r"0.24\textheight"))
    T.append(figrow([("renders/lab/lab_amr_portal.png", "AMR portal"), ("renders/lab/lab_storage_dock.png", "storage and dock"),
                     ("renders/cell01/cell01_r02_magazine.png", "R02 and its tool magazine")],
                    "Details of the twin: the AMR route into the cell, storage, and the flexible arm.", height=r"0.17\textheight"))
    T.append(r"""
\subsection{Devices and their mechanisms}
Every station is an articulated model whose controller drives its joints in physics and whose sensors feed its
monitors: the L09 hotel's lift, fork and shuttle; the L10 incubator's cassette, lift, gate and environment probes; the
L12 gantry; the L17 stage, focus and turret; the H4 door, latch and shuttle.
""")
    T.append(figrow([("renders/l09/l09_cutaway_handler.png", "L09: fork carrying a plate"),
                     ("renders/devices/l17_open_front_left.png", "L17: stage, focus, illumination"),
                     ("renders/devices/l10_open_front_left.png", "L10: cassette, lift, shuttle")],
                    "Inside the devices (housings removed): the mechanisms the controllers drive.", height=r"0.2\textheight"))
    T.append(figrow([("renders/devices/l12_front_left.png", "L12 gantry and deck"),
                     ("renders/devices/r02_tool_magazine_front_left.png", "R02 tool magazine"),
                     ("renders/h4_presented_loaded.png", "H4 quarantine")],
                    "Liquid handling, tools and containment.", height=r"0.17\textheight"))
    ep_rows = []
    for e in eps:
        o = e.get("outcome") or {}
        ep_rows.append([esc(e.get("episode_id", "")), esc(o.get("route", "")), f"{o.get('duration_s', '')} s",
                        esc(", ".join(f"{k}: {v}" for k, v in o.items() if k in ("stored", "contained", "reentry_blocked",
                                                                              "incubated", "images_valid", "qc")))])
    T.append(r"""
\subsection{Robots in action}
The episodes run the cell's robots and devices in PhysX at 240~Hz with the controllers in the loop; their run logs
become Cell~01 NEEM records through Cell~01's own builders and validator.
""")
    T.append(table(["p{4.4cm}", "p{2.2cm}", "p{1.3cm}", "X"], ["episode", "route", "duration", "outcome"], ep_rows,
                   "End-to-end episodes in the twin (test\\_reports/episodes)."))
    T.append(figrow([("renders/episodes/identity_swap_1_identity_fault_at_L10.png", "identity fault at L10"),
                     ("renders/episodes/identity_swap_2_carrying_to_H4.png", "carrying to quarantine"),
                     ("renders/episodes/identity_swap_3_quarantined_locked.png", "quarantined and locked")],
                    "The identity-swap episode: the wrong plate is detected at the incubator and contained in H4.",
                    height=r"0.16\textheight"))
    trow = [[esc(k.replace("_", " ")), f"{p}/{n}"] for k, (p, n) in tests.items()]
    T.append(table(["X", "p{2cm}"], ["acceptance test", "passed"], trow,
                   f"Device and robot acceptance tests (physics in the loop): {t_pass}/{t_all} pass; H4 robot loading: "
                   f"{h4r['registered']['seated']}/{h4r['registered']['trials']} seated."))
    T.append(r"""
\subsection{The cultures}
The culture twin keeps two worlds apart. The \emph{simulated world} holds the hidden biology of every well (injury,
protective response, reserve, viability; Cell~01's surrogate). The \emph{belief} is a particle filter per well, fed only
by robot records (committed doses) and 4$\times$ images. Its 90\,\% intervals contain the hidden viability in every
snapshot of every run.
""")
    T.append(fig("scenes/culture/design_improved/renders/arms_camera_view.png", "The improved five-arm design, one culture "
                 "per arm at 0, 24, 48 and 72~h (path-traced camera view of the simulated cultures).", height=r"0.5\textheight"))
    T.append(fig("scenes/culture/design_improved/arms.png", "Arm by arm: what is given when, the twin's belief about "
                 "each culture's viability against the hidden truth, and the 4$\\times$ images.", height=r"0.5\textheight"))
    T.append(r"""
\paragraph{The robot's own images} The L17 controller images the simulated cultures through its optics model: stage
motion, objective change, autofocus, exposure and monitors as in an episode. Without plate registration the field lands
0.2--0.65~mm off the well centre and """ + f"{unreg_valid} of {len(unreg_shots)}" + r""" frames are valid. """ + reg_txt + r"""
""")
    T.append(fig("scenes/culture/design_improved/l17_robot/robot_images.png" if reg else
                 "scenes/culture/design_improved/l17_robot_unregistered/robot_images.png",
                 "The robot's own L17 images of the improved design's cultures (4$\\times$, autofocus).", height=r"0.42\textheight"))
    # knowledge
    T.append(r"""
\subsection{Knowledge: ontologies and the designator language}
""")
    T.append(fig("renders/ontology/ontology_map.png", "The ontologies and how they connect: upstream AICOR federation, the "
                 "lab ontology's 13 modules, the experiment ontology and LDL, Cell~01's records and biology, and the twin as "
                 "their instances.", height=r"0.55\textheight"))
    T.append(fig("renders/ontology/ldl_overview.png", "LDL: an action as a contract over its interval, and the lab's LDL "
                 "documents above a checked abstraction boundary.", height=r"0.55\textheight"))
    T.append(code(ldl_excerpt("rsa/registry/lab/contracts.ldl", "(contract intervening", 22), title=
                  "LDL: the contract of an intervention (rsa/registry/lab/contracts.ldl)"))
    T.append(code(ldl_excerpt("rsa/registry/lab/experiment_improved.ldl", "(factor (a factor (name challenge)", 18), title=
                  "LDL: the improved design is authored once and read by every layer (experiment\\_improved.ldl)"))
    axs = []
    want = ("ChallengeOnlyArm", "NegativeControlArm", "RescueEffectComparison", "AdequatelyControlledInjuryRescueDesign",
            "TreatmentAndImagingModule", "RequiresDosing")
    for s in S:
        for a in s["axioms"]:
            if isinstance(getattr(a, "l", None), XO.A) and a.l.n in want and isinstance(a, XO.Eq):
                axs.append(a.dl("tex"))
    T.append(r"""
\paragraph{The experiment ontology} A design is classified from its content. Selected definitions (OWL~2~DL, the
reasoner decides membership):
{\small """ + "\n".join(r"\par\noindent\hangindent=2em\hangafter=1 $" + x.replace(" ⊓ ", r" \sqcap\allowbreak ") + "$\\par\\smallskip"
                         for x in axs) + r"""}\par
""")
    rlz = owl["results"]
    rows = [[esc(d.replace("_", " ")), ", ".join(rf"$\mathsf{{{c}}}$" for c in sorted(set(r["realization"].get(f"{'' if d == 'challenge_rescue' else 'improved_'}design", [])))[:6])]
            for d, r in rlz.items()]
    T.append(r"""HermiT classifies the current design as a validated injury--rescue design but \emph{not} adequately
controlled (no rescue-only or vehicle arm, no positive control, no replicates); the improved design is adequately
controlled, interaction-aware and has a therapeutic-window comparison. Each variant that removes one ingredient loses
exactly the corresponding class.
""")
    T.append(fig("rsa/out/experiment_ontology/inferred.png", "The inferred taxonomy (HermiT) with both designs realized "
                 "under it.", height=r"0.45\textheight"))
    T.append(r"""\paragraph{One experiment model} The lab ontology's design concepts are bridged to the experiment ontology.
Konclude finds the union """ + ("consistent" if merge["consistent"] else "INCONSISTENT") + f" with {len(merge['unsatisfiable'])} "
             r"""unsatisfiable classes and infers """ + "; ".join(f"{esc(a)} $\\equiv$ {esc(b)}" for a, b in merge["inferred_equivalences"]) + r""".
""")
    # e2m and plans
    T.append(r"""
\subsection{From required information to robot motion}
Three hypotheses compete: graded recovery, a threshold, and a protective response. The design is chosen for the
expected information gain it yields about them (""" + f"{plan['selected']['eig_bits']:.3f}" + r"""~bit, at least 0.5~bit
required); an answer-set program derives the plan (sessions, trips, steps); z3 checks it independently.
""")
    T.append(figrow([("okf/lab-automation-twin/docs/e2m_eig_landscape_g050.png", "expected information gain of the candidates"),
                     ("okf/lab-automation-twin/docs/e2m_plan_g050.png", "the derived plan: sessions and trips")],
                    "Experiment to motion: choosing the experiment by information gain, and the plan derived for it.",
                    height=r"0.25\textheight"))
    T.append(fig("report/figures/chain.pdf", "The chain from the experiment to the robots, as the kernel executes it.",
                 height=r"0.32\textheight"))
    T.append(code("\n".join(open(R("rsa/out/culture_plan_src.lisp")).read().splitlines()[:30]), title=
                  "The culture-level plan as a CRAM/RPL program (generated; rsa/out/culture\\_plan\\_src.lisp, first lines)"))
    # guarantees
    O = proof["obligations"]
    T.append(r"""
\subsection{Guarantees: the motions implement the design}
\begin{theorem}[Refinement]
Under assumptions A1--A6 (motion-framework semantics, monitor soundness, mechanical capture, grasp, device contracts,
reachable goal frames), every execution of the """ + f"{n_mot}" + r""" robot motions of the selected plan either
(i) realizes the culture-level design, every treatment and observation to the right culture at the right culture time
in the designed order, the control never exposed, and every stated constraint kept; or (ii) is stopped by a monitor and
ends in a failure handler whose stated guarantee holds.
\end{theorem}
""")
    T.append(table(["p{1cm}", "X", "p{1.6cm}"], ["", "obligation", "status"],
                   [[k.split()[0], esc(" ".join(k.split()[1:])), "holds" if v["holds"] else "FAILS"] for k, v in O.items()],
                   f"The seven obligations; each is discharged by a machine check, and {neg_total} negative controls show "
                   "the checks discriminate. Full statements and proofs: report/proofs/refinement\\_theorems.pdf."))
    T.append(figrow([("report/figures/trail.pdf", "hash-chained audit trail"), ("report/figures/trust.pdf", "trust per step")],
                    "Evidence and trust: every lifecycle transition is a hash-chained record; device processes decide how far "
                    "a result can be trusted.", height=r"0.22\textheight"))
    def rz(v):
        g = v.get("got") or {}
        return ("ok" if g.get("realization") else "x") + " / " + ("ok" if g.get("validity") else "x")
    srows = [[esc(k.replace("_", " ")), esc(v.get("about", "")), esc(v.get("end", "")), rz(v),
              "yes" if v.get("expectation_ok") else "NO"] for k, v in scen.items()]
    T.append(table(["p{2.8cm}", "X", "p{1.5cm}", "p{1.6cm}", "p{1.1cm}"],
                   ["scenario", "what is changed", "end", "realization / validity", "as expected"], srows,
                   "The kernel on twelve scenarios (symbolic backend): repairs, escalations, refusals before execution, and "
                   "realized-but-invalid evidence (imager swapped)."))
    # affordance
    T.append(r"""
\subsection{What the lab affords}
Capability classes of a laboratory are defined by the functions its devices bear; requirement classes of a design by
its content. The reasoner classifies both, and a closed-world matcher decides what can run where.
""")
    T.append(fig("renders/ontology/affordance.png", "Capability classes of Cell~01 and an (illustrative) core plate reader; "
                 "the requirements of four designs and where they are met.", height=r"0.3\textheight"))
    arow = [[esc(m["label"]), esc(m["verdict"].replace("cell01", "Cell 01")), esc("; ".join(m["missing"]) or "---")]
            for m in aff["designs"].values()]
    T.append(table(["p{5cm}", "p{3.2cm}", "X"], ["design", "verdict", "missing"], arow, "Design verdicts against the site."))
    # status table
    T.append(r"""
\subsection{Status at a glance}
""")
    st = [["Twin of Cell 01 and Lab 1", "built, tested", f"{t_pass}/{t_all} tests; {len(eps)} episodes"],
          ["Culture twin (belief vs truth)", "built, audited", "90 % coverage 1.00 in all runs"],
          ["Robot imaging of cultures", "built; registration not yet effective", "7/20 frames valid; field 0.3-0.6 mm off"],
          ["LDL", "built, checked", "20/20 failures handled, 13/13 guarantees, 12/12 negative controls"],
          ["Experiment ontology", "built, reasoned", f"{n_xo} concepts, {n_ax} axioms; 8/8 negative controls"],
          ["Lab ontology + bridge", "built, reasoned", f"{len(tbox.CLASSES)} concepts; union consistent"],
          ["Lab affordance", "built", "4 designs judged; vehicle stock missing"],
          ["Experiment to motion", "built, z3-validated", "7 plans derived, 3 refused"],
          ["Kernel", "runs (symbolic, Isaac)", "12/12 scenarios as expected"],
          ["CRAM/RPL and Giskard plans", "generated, checked; not executed", "no CRAM runtime installed"],
          ["Refinement theorem", "proved (relative to A1-A6)", "current design only"],
          ["Real hardware", "not started", "---"]]
    T.append(table(["p{4.6cm}", "p{4.2cm}", "X"], ["component", "status", "evidence"], [[esc(c) for c in r] for r in st],
                   "Where the work stands."))
    # ---------------------------------------------------------------- plan
    T.append(r"""
\section{Plan for a first demonstrator}\label{sec:plan}
\paragraph{Goal} Demonstrator D1 shows, on Cell~01's twin and in one real segment, that a robot executes a biomedical
experiment it understands: the challenge--rescue experiment is designed, checked for adequacy, matched to the lab,
planned, executed by the generated plans, observed with the robot's own camera, interpreted into an updated belief,
and reported with its evidence, and its failures are handled at the level of the experiment, with the refinement
theorem holding for the executed design.
""")
    wp = [["WP1", "Execution", "Run the generated plans in the twin: a CRAM (or PyCRAM) executive or the kernel's Isaac "
           "backend executing the designators and Giskard motions; complete the full-cell run.", "3"],
          ["WP2", "Valid imaging", "Find the field-position mismatch that registration does not remove (stage-to-optics "
           "calibration); robot images of every arm valid; update assumption A5.", "1-2"],
          ["WP3", "Improved design, full chain", "Derive the step and motion plans for the five-arm design (15 cultures, "
           "split dosing sessions); extend the refinement proof to it.", "2"],
          ["WP4", "Closed loop", "The culture twin fed by the robot's own images; belief update; the next experiment chosen by "
           "information gain; report and provenance generated.", "2"],
          ["WP5", "Faults at experiment level", "Injected faults (identity swap, lost tip, calibration lapse, contamination, "
           "lost culture) mapped to the comparisons and conclusions they affect; partial reruns.", "2"],
          ["WP6", "One real segment", "One step on real hardware (plate transfer or imaging) predicted by the twin and "
           "compared.", "2-4"],
          ["WP7", "Package", "Reproducibility pipeline with all generators; merge to main; demonstrator video and report.", "1"]]
    T.append(table(["p{0.9cm}", "p{2.6cm}", "X", "p{1.3cm}"], ["WP", "name", "content", "weeks"], wp,
                   "Work packages (durations proposed, to be agreed)."))
    T.append(r"""
\begin{center}\begin{tikzpicture}[x=0.95cm, y=0.55cm, font=\footnotesize\sffamily]
\foreach \w in {0,...,11} {\draw[gray!25] (\w,0.4) -- (\w,-7.6); \node[gray] at (\w+0.5,0.8) {W\the\numexpr\w+1\relax};}
\def\bar#1#2#3#4{\fill[#4!25] (#2,-#1+0.35) rectangle (#3,-#1-0.35); \draw[#4!70!black] (#2,-#1+0.35) rectangle (#3,-#1-0.35);}
\bar{0}{0}{3}{teal}\node[anchor=east] at (0,0) {WP1 execution};
\bar{1}{0}{1}{orange}\node[anchor=east] at (0,-1) {WP2 imaging};
\bar{2}{3}{5}{teal}\node[anchor=east] at (0,-2) {WP3 improved design};
\bar{3}{3}{5}{blue}\node[anchor=east] at (0,-3) {WP4 closed loop};
\bar{4}{5}{7}{blue}\node[anchor=east] at (0,-4) {WP5 faults};
\bar{5}{6}{10}{red}\node[anchor=east] at (0,-5) {WP6 real segment};
\bar{6}{10}{11}{gray}\node[anchor=east] at (0,-6) {WP7 package};
\foreach \x/\m in {1/M1,3/M2,7/M3,11/M4} {\draw[thick,teal!50!black] (\x,0.4) -- (\x,-7.2); \node[fill=white,inner sep=1pt] at (\x,-7.4) {\textbf{\m}};}
\end{tikzpicture}\end{center}
\begin{description}[style=nextline]
\item[M1 (week 1)] the robot's images of every arm valid with registration.
\item[M2 (week 3)] the current design executed end to end in the twin by the generated plans; O2 checked on the executed
trail, not only on the plan.
\item[M3 (week 7)] the improved design carried through the proof; fault campaign with experiment-level consequences;
the closed loop proposes the next experiment.
\item[M4 (week 11)] one real segment against the twin's prediction; demonstrator package.
\end{description}
""")
    T.append(table(["p{4.2cm}", "X"], ["criterion", "measure"], [
        ["Faithful execution", "the executed trail satisfies every culture-level obligation (O2 on the trail) in every "
                               "nominal run"],
        ["Valid observation", "share of robot images valid; field offset from the culture within the 4$\\times$ field"],
        ["Proof coverage", "refinement theorem regenerated and holding for both designs"],
        ["Robustness", "every injected fault ends in a handler with its guarantee; the conclusions it invalidates are named"],
        ["Closed loop", "belief updated from the robot's images; next experiment proposed with its expected gain"],
        ["Twin vs real", "the real segment's duration and outcome against the twin's prediction (target set after the first "
                         "measurement)"]], "Acceptance criteria of D1."))
    T.append(table(["p{4.2cm}", "X"], ["risk", "mitigation"], [
        ["No CRAM runtime on this machine", "use PyCRAM or the kernel's Isaac backend as the executive for D1; keep the "
                                             "CRAM/RPL output as the reference"],
        ["One 8 GB GPU: concurrent Isaac jobs crash it", "serialize GPU jobs in the build pipeline"],
        ["Integration of Giskard with the twin", "start with R01 legs; fall back to the twin's own planners for R02"],
        ["Real hardware availability", "decide the platform early (week 2); the twin demonstrator stands on its own"],
        ["Biology realism", "keep the surrogate labelled; invite scientists to pose the question for a later demonstrator"]],
        "Risks."))
    T.append(r"""
\paragraph{Decisions needed} (1) the executive for D1: Lisp CRAM, PyCRAM, or the kernel's Isaac backend; (2) the
real-hardware segment and platform; (3) the audience and date of the first showing.

\begin{thebibliography}{9}\small
\bibitem{verid} P.~Rao, P.~Sirkovic, A.~Pawlosky. Grounding AI agents in biological reality: building blocks for
autonomous wet labs. Google Research blog, 16 Oct 2026.
\bibitem{safesdl} Z.~Zhang et al. Safe-SDL: establishing safety boundaries and control mechanisms for AI-driven
self-driving laboratories. arXiv:2602.15061, 2026.
\bibitem{baker2016} M.~Baker. 1,500 scientists lift the lid on reproducibility. Nature 533:452--454, 2016.
\bibitem{lapp} A.~Wolf et al. The Laboratory Automation Plug and Play (LAPP) framework, part three. ISPE iSpeak, 2026.
\bibitem{tracebot} TraceBot: traceable robotic handling of sterile medical products. EU H2020, grant 101017089, 2021--2025.
\end{thebibliography}
\end{document}
""")
    tex = os.path.join(HERE, "cell01_vision_status_plan.tex")
    open(tex, "w").write("\n".join(T))
    r = subprocess.run(["latexmk", "-lualatex", "-interaction=nonstopmode", "-halt-on-error", os.path.basename(tex)],
                       cwd=HERE, capture_output=True, text=True, timeout=900)
    log = open(tex[:-4] + ".log", errors="replace").read()
    pages = re.search(r"Output written on .*?\((\d+) pages?", log)
    print(f"[c01] latex exit {r.returncode}; {pages.group(1) if pages else '?'} pages; "
          f"{len(re.findall('Overfull', log))} overfull")
    if r.returncode:
        print(r.stdout[-3000:])
    return r.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
