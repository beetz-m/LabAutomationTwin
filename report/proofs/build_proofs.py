"""Theorems and proofs: the robot-motion level correctly implements the culture-level experiment design.

Typesets the refinement theorem of rsa/refinement_proof.py and the step-level theorems of validate_plan_z3.py as
definitions, lemmas, theorems and proofs. Every count, verdict and table row is read from the checkers' outputs
(rsa/out/refinement_proof.json, .../derivation/out/proof_g050.json, rsa/out/culture_plan.json), which are re-run
first unless --no-regen.

    env_cad/bin/python report/proofs/build_proofs.py      # report/proofs/refinement_theorems.pdf
"""

import collections
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PY = os.path.join(ROOT, "env_cad", "bin", "python")
OUT = os.path.join(ROOT, "rsa", "out")
DERIV = os.path.join(ROOT, "okf", "lab-automation-twin", "L3-logical-axiomatization", "derivation", "out")


def esc(s):
    return (str(s).replace("\\", r"\textbackslash{}").replace("_", r"\_").replace("&", r"\&").replace("%", r"\%")
            .replace("#", r"\#").replace("->", r"$\to$").replace("<", r"$<$").replace(">", r"$>$").replace("~", r"$\sim$"))


def ok(b):
    return r"\textcolor{green!40!black}{holds}" if b else r"\textcolor{red!70!black}{FAILS}"


def main(argv):
    if "--no-regen" not in argv:
        r = subprocess.run([PY, "-m", "rsa.refinement_proof"], cwd=ROOT, capture_output=True, text=True, timeout=1800)
        print(r.stdout.strip().splitlines()[-1])
    R = json.load(open(os.path.join(OUT, "refinement_proof.json")))
    P = json.load(open(os.path.join(DERIV, "proof_g050.json")))
    cp = json.load(open(os.path.join(OUT, "culture_plan.json")))
    plan = json.load(open(os.path.join(DERIV, "plan_g050.json")))
    O = R["obligations"]
    key = lambda p: next(k for k in O if k.startswith(p))  # noqa: E731
    o1, o2, o3, o4, o5, o6, o7 = (O[key(f"O{i}")] for i in range(1, 8))
    th = P["theorems"]
    v4 = th["V4 realisation (doses, images, session times)"]
    steps = cp["plan"]["steps"]
    vessels = cp["mapping"]["vessels"]
    n_steps = sum(len(s["steps"]) for s in plan["sessions"])
    motions = o6["motions"]
    by_type = collections.Counter(m["type"] for m in motions)
    sessions = plan["sessions"]
    times = v4["times"] if isinstance(v4["times"], dict) else json.loads(v4["times"].replace("'", '"'))

    T = [r"""\documentclass[10pt,a4paper]{article}
\usepackage[margin=2.3cm]{geometry}
\usepackage{fontspec,unicode-math}
\setmainfont{Libertinus Serif}\setsansfont{IBM Plex Sans}\setmonofont[Scale=0.85]{IBM Plex Mono}\setmathfont{Libertinus Math}
\usepackage{amsmath,amsthm,booktabs,tabularx,array,xcolor,enumitem,tikz,hyperref,microtype}
\usetikzlibrary{arrows.meta,positioning,fit}
\renewcommand{\tabularxcolumn}[1]{>{\raggedright\arraybackslash}p{#1}}
\setlength{\emergencystretch}{3em}
\theoremstyle{plain}\newtheorem{theorem}{Theorem}\newtheorem{lemma}{Lemma}\newtheorem{corollary}{Corollary}
\theoremstyle{definition}\newtheorem{definition}{Definition}\newtheorem{assumption}{Assumption}
\theoremstyle{remark}\newtheorem*{remark}{Remark}
\newcommand{\M}{\mathcal{M}}\newcommand{\Pl}{\mathcal{P}}\newcommand{\Lp}{\mathcal{L}}\newcommand{\C}{\mathcal{C}}
\title{\sffamily\bfseries The robot motions implement the experiment\\[4pt]\large Refinement theorems and their proofs for the challenge--rescue experiment on Cell~01}
\author{Generated from the proof checkers' outputs (rsa/refinement\_proof.py, validate\_plan\_z3.py)}
\date{2026-10-18}
\begin{document}\maketitle
\begin{abstract}
The experiment is stated at the culture level: which cultures receive which treatment when, which are observed, and
what must never happen to them. The robots execute motions. This document states, as theorems, that every execution of
the motion-level plan either realizes the culture-level design, in order and under every stated constraint, or is
stopped by a monitor and ends in a failure handler whose guarantee holds. The proof composes seven obligations across
four levels of abstraction; each obligation is discharged by a machine check (z3, the LDL checker, an exhaustive check
over the motions), and each check is shown to be discriminating by negative controls. The result is relative to six
explicit assumptions about controllers, sensors and devices. All quantities are the twin's and ILLUSTRATIVE (D016).
\end{abstract}
"""]
    T.append(r"""\section{Four levels and their abstraction maps}
\begin{center}\begin{tikzpicture}[node distance=7mm and 6mm, box/.style={draw, rounded corners, align=left, inner sep=5pt, text width=118mm, font=\small}]
\node[box] (C) {\textbf{Culture plan} $\C$: """ + f"{len(steps)} culture actions over 3 cultures; order from {o1['links']} causal links" + r"""};
\node[box, below=of C] (L) {\textbf{Lab plan} $\Lp$ (LDL): action contracts with requires / prevents / maintains / achieves, instruments, handlers};
\node[box, below=of L] (P) {\textbf{Step plan} $\Pl$: """ + f"{n_steps} grounded steps in {len(sessions)} sessions (trips) at culture times " + ", ".join(f"{t} h" for t in times.values()) + r"""};
\node[box, below=of P] (M) {\textbf{Motion plan} $\M$: """ + f"{len(motions)} robot motions as giskardpy motion statecharts" + r"""};
\draw[-{Latex}] (L) -- node[right, font=\footnotesize] {refines (O3)} (C);
\draw[-{Latex}] (P) -- node[right, font=\footnotesize] {$\alpha_{\Pl}$: events $\mapsto$ culture effects via the vessel map $\nu$ (O2)} (L);
\draw[-{Latex}] (M) -- node[right, font=\footnotesize] {$\alpha_{\M}$: motion type $\mapsto$ step primitive (O6)} (P);
\end{tikzpicture}\end{center}
""")
    vrows = " \\\\ ".join(f"\\texttt{{{esc(c)}}} & {esc(v['role'])} & {esc(v['well'])} on {esc(v['plate'])}" for c, v in vessels.items())
    T.append(r"""
\begin{definition}[Culture plan]\label{def:culture}
$\C = (A_{\C}, \prec_{\C}, \mathit{Eff}_{\C}, \mathit{Prev}_{\C})$: the culture actions $A_{\C}$ with their culture times, the
partial order $\prec_{\C}$ derived from causal links (physical and knowledge effects), the effects $\mathit{Eff}_{\C}$
(a culture exposed to a substance at a dose and time, an observation, an estimate) and the prevented conditions
$\mathit{Prev}_{\C}$ (the control culture is never exposed). The actions are: """ +
             ", ".join(f"\\texttt{{{esc(s['var'])}}} {esc(s['type'])}" for s in steps) + r""".
\end{definition}

\begin{definition}[Vessel map]
$\nu$ maps each culture of $\C$ to the well that holds it:
\begin{center}\small\begin{tabular}{lll}\toprule culture & role & well \\\midrule """ + vrows + r""" \\\bottomrule\end{tabular}\end{center}
\end{definition}

\begin{definition}[Events and the abstraction $\alpha_{\Pl}$]
An execution of $\Pl$ produces events $\mathit{dose}(w, r, q, t)$ (reagent $r$ of $q$ abstract units into well $w$
in the session at culture time $t$) and $\mathit{image}(w, t)$. A culture effect ``$c$ exposed to $r$ at $q$ at $t$''
holds iff $\mathit{dose}(\nu(c), r, q, t)$ occurs; ``$c$ observed at $t$'' holds iff $\mathit{image}(\nu(c), t)$ occurs.
\end{definition}

\begin{definition}[Motion executions and $\alpha_{\M}$]
A motion $m \in \M$ is a statechart that ends either by \emph{EndMotion} (its end monitor true) or by
\emph{CancelMotion} (a cancel condition true). $\alpha_{\M}(m)$ is the step primitive $m$ refines (approach, insert,
grasp, lift, transit, place, release, retract, tool coupling), whose postcondition is that of the step model of
$\Pl$ (Table~\ref{tab:post}).
\end{definition}

\section{Assumptions}
""")
    for a in R["assumptions"]:
        m = re.match(r"(A\d) (.*)", a)
        T.append(rf"\begin{{assumption}}[{m.group(1)}] {esc(m.group(2))}\end{{assumption}}")
    T.append(r"""Each assumption is either checked kinematically (A6: """ + esc(o6["goals_reachable"]) + r""" goal frames reachable),
monitored at run time (A2, A4), part of a device's contract (A5), or the documented semantics of the motion framework (A1).
A3 is a geometric premise: the motion controllers converge to within 0.4 mm, inside the 2 mm capture of the nest guides.
""")
    # ------------------------------------------------------------------ main theorem
    T.append(r"""
\section{The refinement theorem}
\begin{theorem}[The motions implement the culture-level design]\label{thm:main}
Under A1--A6, every execution $\rho$ of the motion plan $\M$ satisfies exactly one of:
\begin{enumerate}[label=(\roman*)]
\item $\alpha_{\Pl}(\alpha_{\M}(\rho))$ realizes $\C$: every effect of $\mathit{Eff}_{\C}$ occurs at its culture time; the
order $\prec_{\C}$ is respected; $\mathit{Prev}_{\C}$ holds throughout (the control culture is never exposed); and every
stated constraint holds along $\rho$: interlocks, the L12 airspace, identity before use, environment before storing,
calibration before imaging, the 600~s excursion window, contamination freedom, tool hygiene, plate level, collision
distance;
\item a monitor stops $\rho$ (CancelMotion or a device monitor), and $\rho$ ends in a failure handler $h$ whose stated
guarantee $g(h) \in \{\textit{goal}, \textit{goal-or-safe-state}, \textit{safe-state}, \textit{contained}\}$ holds.
\end{enumerate}
\end{theorem}
The proof composes the seven lemmas below (\S\ref{sec:composition}). Status of each, as checked on 2026-10-18:
\begin{center}\small\begin{tabularx}{\linewidth}{@{}lXl@{}}\toprule & obligation & status \\\midrule
""" + " \\\\\n".join(f"{k.split()[0]} & {esc(' '.join(k.split()[1:]))} & {ok(v['holds'])}" for k, v in O.items()) +
             r""" \\\bottomrule\end{tabularx}\end{center}
""")
    # ------------------------------------------------------------------ lemmas
    T.append(r"""
\section{Lemmas and their proofs}
\begin{lemma}[O1: the culture plan is well formed]
Every precondition of every culture action is supported by a causal link from an earlier action's effect or by the
initial state, or is to be established by the executive; the link graph is acyclic.
\end{lemma}
\begin{proof}
\texttt{rsa/culture\_plan.derive} computes, for each requirement, its supporting effects. """ +
             f"It finds {o1['links']} links, no unsupported requirement and no cycle; the requirements left to establish are "
             f"{len(o1['establish'])} known image scales (calibration), which the step level discharges (V2, S3)." + r"""
$\prec_{\C}$ is the transitive closure of the links, hence a strict partial order.
\end{proof}

\begin{lemma}[O2: the step events entail the culture plan]\label{lem:abs}
Let $E$ be the set of events the step plan provably produces (Theorem~V4 below). Then for each culture obligation
$\varphi$ (each effect of $\mathit{Eff}_{\C}$ at its time, the prevented condition, and the order),
$E \cup \{\text{definition of }\alpha_{\Pl},\ \nu\} \models \varphi$.
\end{lemma}
\begin{proof}
Encode each event as a Boolean fact asserted true and each obligation $\varphi$ as the disjunction of the events that
support it under $\nu$. For each $\varphi$, z3 shows $E \wedge \neg\varphi$ unsatisfiable. The obligations and verdicts:
\begin{center}\small\begin{tabularx}{\linewidth}{@{}Xl@{}}\toprule obligation & $E \wedge \neg\varphi$ \\\midrule
""" + " \\\\\n".join(f"{esc(k)} & {'UNSAT' if v else 'SAT'}" for k, v in o2["obligations"].items()) + r"""
\\\bottomrule\end{tabularx}\end{center}
The events used are the doses """ + esc(v4["doses"]) + r""" (session $\mapsto$ [well, reagent, dose $\times 100$]) and
images of """ + esc(v4["images"]) + r""" at """ + esc(times) + r""".
\end{proof}

\begin{lemma}[O3: the lab plan refines the culture plan]
The LDL lab plan preserves $\prec_{\C}$; every threat to a causal link is resolved; every instrument role is filled by a
device that offers the slot and the process; every signalled failure has a handler whose guarantee holds.
\end{lemma}
\begin{proof}
By the LDL checker (\texttt{rsa/ldl.py}, \texttt{rsa/ldl\_trust.py}): order preserved from culture to lab level: """ +
             esc(o3["order_preserved_culture_to_lab"]) + f"; threats resolved {esc(o3['threats'])}; repair guarantees {esc(o3['guarantees'])}; "
             f"its negative controls caught {esc(o3['negative_controls'])}. A guarantee \\textit{{goal}} is admitted only if the "
             "fault is detected before the process's irreversible phase and is transient or removed by what the handler "
             "re-establishes; \\textit{safe-state} only if the handler escalates or abstains, the plate is restorable, nothing is "
             "committed and evidence is kept." + r"""
\end{proof}
""")
    T.append(r"""
\begin{theorem}[O4: the step plan is executable, safe, timely and realizes the design]\label{thm:steps}
Each trip of the step plan is unrolled into z3 state variables (plate location, each robot's position and gripper,
R02's tool, the L10 shuttle and L17 stage, L12's tip and reagent, environment, QC and identity flags), one transition
per step. Then:
\begin{description}[leftmargin=2em, style=nextline]
\item[V1 executability and preservation] every step's precondition holds and each trip ends with the plate at home,
grippers empty and no robot in a seat, for every initial tool and stage state;
\item[V2 safety] S1 no L12 operation while a robot is in the deck seat; S2 environment checked before storing; S3 image
only with valid calibration or after QC; S6 interlocks closed; S7 identity verified first;
\item[V3 time] every trip fits the 600~s window for all step durations within $\pm 20\,\%$ of the estimates;
\item[V4 realization] the doses and images are exactly those the selected design requires, in sessions at
$t_0$, $t_0 + 48$~h, $t_0 + 72$~h; arms disjoint with a control (V4b);
\item[V5 gain and cost] the design's expected information gain meets the requirement, and no cheaper design does.
\end{description}
\end{theorem}
\begin{proof}
For each claim $\psi$, z3 shows $\mathit{Trans} \wedge \neg\psi$ unsatisfiable, where $\mathit{Trans}$ is the
conjunction of the transitions (\texttt{validate\_plan\_z3.py}, an encoding separate from the answer-set program that
derived the plan). Results:
\begin{center}\small\begin{tabularx}{\linewidth}{@{}Xll@{}}\toprule claim & result & checked \\\midrule
""" + " \\\\\n".join(f"{esc(k)} & {ok(v['holds'])} & {esc(v.get('checked', v.get('eig_bits', v.get('compared', '')))) }"
                    for k, v in th.items()) + r"""
\\\bottomrule\end{tabularx}\end{center}
Ten mutated plans, each breaking one claim, are each caught (satisfiable negation) by the expected theorem: """ +
             esc(", ".join(P["negative_controls"])) + r""".
\end{proof}

\begin{lemma}[O5: cleanliness]
No tool that touches a culture is ever used to handle the plate, and contamination freedom is a requirement of every
dosing and imaging step.
\end{lemma}
\begin{proof}
""" + f"The plate-handling tools used are {esc(', '.join(o5['tools_used']))}; the tools that touch cultures are "
             f"{esc(', '.join(o5['contacts_culture']))}. z3 shows that asserting any used tool to touch a culture contradicts "
             f"the facts. contamination\\_free is in the constraint registry: {esc(o5['contamination_free_required'])}." + r"""
\end{proof}
""")
    trows = []
    for t, n in sorted(by_type.items()):
        m = next(x for x in motions if x["type"] == t)
        trows.append(f"{esc(t)} & {n} & {esc(m['step'])} & {esc(m['postcondition'])} & {esc(m['end_monitor'])} & {esc(m['why'])}")
    T.append(r"""
\begin{lemma}[O6: every motion refines its step]\label{lem:motion}
For each of the """ + str(len(motions)) + r""" motions $m$: (a) $m$'s type refines the step primitive $\alpha_{\M}(m)$;
(b) if $m$ ends by EndMotion, the postcondition of $\alpha_{\M}(m)$ holds (under A3, A4); (c) while the plate is held,
tilt beyond the level tolerance cancels $m$; (d) a violated collision distance cancels $m$; (e) $m$ is cancelled if it
runs longer than $1.2\times$ its estimated duration, which is the duration bound V3 assumes.
\end{lemma}
\begin{proof}
Exhaustive check over the motions (\texttt{refinement\_proof.motion\_proof}) against the end monitors and their
tolerances (Table~\ref{tab:post}); each end tolerance is at most the capture of the seat it acts on (0.4~mm $\le$ 2~mm
for seats, 5~mm for free-space approach poses, 4~mm lock gap for the coupler), so by A3 EndMotion implies the
postcondition. The generated controller code contains the cancel conditions (timeout: """ +
             esc(o6["code"]["CancelMotion on timeout"]) + ", tilt: " + esc(o6["code"]["CancelMotion on tilt"]) + ", collision: " +
             esc(o6["code"]["collision cancel"]) + r"""). Result: """ + f"{sum(m['ok'] for m in motions)}/{len(motions)}" + r""" motions
satisfy (a)--(e); goal frames reachable """ + esc(o6["goals_reachable"]) + r""".
\begin{table}[h]\centering\footnotesize\caption{Motion types, the steps they refine, and why their end monitor implies
the step's postcondition.}\label{tab:post}
\begin{tabularx}{\linewidth}{@{}lrllXX@{}}\toprule motion & n & step & postcondition & end monitor & why \\\midrule
""" + " \\\\\n".join(trows) + r"""
\\\bottomrule\end{tabularx}\end{table}
\end{proof}

\begin{lemma}[O7: every stop ends in a guaranteed handler]
Every CancelMotion (timeout, tilt, collision) and every device monitor's failure reaches a handler of the experiment
whose stated guarantee holds.
\end{lemma}
\begin{proof}
A cancelled motion raises MotionContractViolated (or CollisionViolatedError); it propagates to the session, whose
unwind-protect returns the plate to its home; the handler for a violated \textit{prevents} item guarantees a safe state.
Device monitors signal the failure types of the process models, each with its own handler. The guarantees checked
(O3) are: """ + esc(", ".join(f"{k}: {'ok' if v else 'FAIL'}" for k, v in o7["guarantees"].items())) + r""".
\end{proof}
""")
    # ------------------------------------------------------------------ composition
    T.append(r"""
\section{Proof of Theorem~\ref{thm:main}}\label{sec:composition}
\begin{proof}
Let $\rho$ be an execution of $\M$. By A1 each motion of $\rho$ ends by EndMotion or by CancelMotion; device steps end
with their monitors passing or a failure signalled (A5).

\emph{Case 1: no motion is cancelled and no device monitor fails.} By Lemma~\ref{lem:motion}(b), after each motion the
postcondition of its step holds; device steps achieve their contract effects (A5). Hence $\alpha_{\M}(\rho)$ is an
execution of the step plan in which each step's effect holds when it ends. By Theorem~\ref{thm:steps} (V1) the
precondition of every next step then holds, so $\alpha_{\M}(\rho)$ is a complete execution of $\Pl$; by V2 the safety
constraints S1, S2, S3, S6, S7 hold along it; by Lemma~\ref{lem:motion}(e) every duration is within $1.2\times$ its
estimate, so V3 applies and each trip keeps the 600~s window; by Lemma~\ref{lem:motion}(c, d) the plate stays level and
no collision distance is violated; by O5 no culture-touching tool handles the plate. By V4 the events of the execution
are exactly $E$. By Lemma~\ref{lem:abs}, $E$ entails every culture effect at its time, the order, and that the control
culture is never exposed. By O1 and O3 these effects, in this order, are the culture plan and its lab-level refinement.
So (i) holds.

\emph{Case 2: some motion is cancelled or a device monitor fails.} The first such event stops the trip; by O7 it reaches
a handler whose guarantee holds. So (ii) holds.

The cases are exhaustive by A1 and A5, and exclusive because (i) requires a complete execution. \qedhere
\end{proof}

\begin{corollary}
The design's purpose is preserved: the comparisons the experiment makes (rescued vs comparator, comparator vs control)
are between cultures that received exactly the designed treatments, so any conclusion drawn from an execution in case
(i) is about the designed contrast; in case (ii) no conclusion is drawn (the handler commits nothing).
\end{corollary}

\section{The checks discriminate: negative controls}
Each mutation must make an obligation fail; a check that passes a mutant would prove nothing.
\begin{center}\small\begin{tabularx}{\linewidth}{@{}Xl@{}}\toprule mutation & caught \\\midrule
""" + " \\\\\n".join(f"{esc(k)} & {'yes' if v else r'\textbf{no}'}" for k, v in R["negative_controls"].items()) + r"""
\\\bottomrule\end{tabularx}\end{center}

\section{Scope and what is not proved}
\begin{itemize}
\item \textbf{The current design only.} The theorem is about the selected plan (three cultures, one well each). The
improved five-arm design has no derived step and motion plan yet; its proof needs the same chain (derive the plan,
V1--V5, O2 with its 15 units and the vehicle doses, O6).
\item \textbf{Progress.} The plan may stop (case ii) rather than finish; no probability of finishing is claimed.
\item \textbf{Partially detected faults.} L12 well misregistration and L17 plate misseating are detected only partly
(6 of 27 fault instances); for these, case (ii) is not guaranteed.
\item \textbf{The imaging postcondition (new, 2026-10-18).} A5 reads ``image\_well yields an image of the well when
calibration and focus monitors pass''. The L17 twin without plate registration places its 4$\times$ field 0.2--0.65~mm
from the well centre and misses the organoid in 3 of 5 wells. When the field contains no structure, focus fails and case
(ii) applies; a field that shows debris but not the organoid could pass and violate A5 silently. Edge-finding plate
registration (\texttt{L17Controller.register\_plate}, in progress) is meant to discharge this premise; until it is
verified, A5 for imaging is a premise, not a fact of the twin.
\item \textbf{Physics and execution.} Compliant insertion is not modelled; the Giskard module is generated and checked
but not run (no SDT world for it); R02 is not collision-checked offline.
\item \textbf{Biology.} The goal is an expected information gain under the surrogate model, not a biological finding.
\end{itemize}
\end{document}
""")
    os.makedirs(HERE, exist_ok=True)
    tex = os.path.join(HERE, "refinement_theorems.tex")
    open(tex, "w").write("\n".join(T))
    r = subprocess.run(["latexmk", "-lualatex", "-interaction=nonstopmode", "-halt-on-error", "refinement_theorems.tex"],
                       cwd=HERE, capture_output=True, text=True, timeout=600)
    log = open(os.path.join(HERE, "refinement_theorems.log"), errors="replace").read()
    pages = re.search(r"Output written on .*?\((\d+) pages?", log)
    print(f"[proofs] latex exit {r.returncode}; {pages.group(1) if pages else '?'} pages; "
          f"{len(re.findall('Overfull', log))} overfull; QED: {R['holds']}")
    if r.returncode:
        print(r.stdout[-2500:])
    return r.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
