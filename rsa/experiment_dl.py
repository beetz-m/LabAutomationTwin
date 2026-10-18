"""The experiment concepts in description logic: RBox (role hierarchy, partonomy), TBox (kinds, entities, phases,
experiments) and an ABox of the challenge-rescue experiment as derived and placed.

Everything is generated from registry/lab/experiment_concepts.ldl and the instance rsa/experiment_concepts.py checks,
so the DL statement and the checked concepts cannot drift apart. Constraints that SROIQ(D) (OWL 2 DL) cannot state are
given in the more expressive logic they need, with what OWL 2 can state of them. The RBox is checked for the OWL 2
restriction that number restrictions use simple roles only.

    env_cad/bin/python -m rsa.experiment_dl    # rsa/out/experiment_dl.{tex,pdf,txt}
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

from .experiment_concepts import (TBox, ancestors, derived_and_placed, ex_key, exposures, load_concepts, role_of,
                                  steps_of, units)
from .ldl import LAB, OUT, dslots, fmt, is_desig, parse, slot

INSTANCE = os.path.join(LAB, "experiment.ldl")
TOP, BOT = "⊤", "⊥"


def camel(s, cap=True):
    parts = re.split(r"[-_]", s)
    out = "".join(p[:1].upper() + p[1:] for p in parts)
    return out if cap else out[:1].lower() + out[1:]


ROLE = {  # LDL slot -> DL role name
    "role": "hasRole", "question": "hasQuestion", "goal": "hasGoal", "insight": "hasInsight", "candidate": "hasCandidate",
    "belief": "hasBelief", "over": "over", "prior": "hasPrior", "form": "hasForm", "unit": "hasUnit",
    "treatment": "hasTreatment", "shared-conditions": "hasSharedConditions", "from": "fromTime", "at": "atTime",
    "observation": "hasObservation", "interpreted-as": "interpretedAs", "comparison": "hasComparison",
    "between": "between", "determines": "determines", "phase": "hasPhase", "site": "hasSite", "prevents": "prevents",
    "maintains": "maintains", "of": "of", "exposure": "hasExposure", "licenses": "licenses", "updates": "updates",
    "substance": "hasSubstance", "step": "hasStep", "well": "hasWell", "contains": "contains", "culture": "hasCulture",
    "expected-information-gain": "expectedInformationGain", "dose": "dose", "has-part": "hasPart", "part-of": "partOf",
    "has-component": "hasComponent", "contained-in": "containedIn", "located-in": "locatedIn",
    "has-participant": "hasParticipant", "has-output": "hasOutput", "specifies": "specifies", "realizes": "realizes",
}


def rname(slot_name, cls=None):
    if slot_name == "to":
        return "exposedTo" if cls == "exposure" else "toTime"
    return ROLE.get(slot_name, camel(slot_name, cap=False))


class DL:
    """Renders descriptions as DL concept expressions, plain (txt) or LaTeX (tex)."""

    def __init__(self, mode):
        self.mode = mode
        self.defs = {}

    def C(self, n):
        return n if self.mode == "txt" else rf"\mathsf{{{n}}}"

    def R(self, n):
        return n if self.mode == "txt" else rf"\mathit{{{n}}}"

    def T(self, t):
        return t if self.mode == "txt" else rf"\text{{{t}}}"

    def inv(self, n):
        return self.R(n) + ("⁻" if self.mode == "txt" else "^{-}")

    def concept(self, c):
        return self.C(camel(c))

    def wrap(self, x):
        return f"({x})" if (" ⊓ " in x or " ⊔ " in x) else x

    def tr(self, p):
        if p == "any":
            return TOP
        if isinstance(p, list) and p and p[0] == "or":
            return " ⊔ ".join(self.tr(q) for q in p[1:])
        if isinstance(p, list) and p and p[0] == "no":
            name = "Empty" + camel(p[1])
            self.defs[name] = f"{self.C(name)} ≡ {self.C(camel(p[1]))} ⊓ ¬∃{self.R('hasExposure')}.{TOP}"
            return self.C(name)
        if not is_desig(p):
            return self.C(camel(str(p)))
        cls = p[1]
        conj = [] if cls == "entity" else [self.concept(cls)]
        for s in dslots(p):
            if s[0] == "role":
                conj.append(f"∃{self.R('hasRole')}.{self.C(camel(s[1]) + 'Role')}")
            elif s[0] == "kind":
                conj = [self.C(camel(s[1]) + "Action")]
            elif len(s) == 1:
                conj.append(f"∃{self.R(rname(s[0], cls))}.{TOP}")
            else:
                conj += [f"∃{self.R(rname(s[0], cls))}.{self.wrap(self.tr(v))}" for v in s[1:]]
        return " ⊓ ".join(conj) if conj else TOP

    def number(self, card, role, filler):
        op, n = card[0], int(card[1])
        if op == "at-least" and n == 1:
            return f"∃{self.R(role)}.{self.wrap(filler)}"
        sym = {"exactly": "=", "at-least": "≥", "at-most": "≤"}[op]
        return f"({sym}{n} {self.R(role)}.{self.wrap(filler)})"

    def has(self, h):
        path = h["path"]
        inner = self.number(h["card"], rname(path[-1]), self.tr(h["pattern"]))
        for r in reversed(path[:-1]):
            inner = f"∃{self.R(rname(r))}.{inner}"
        return inner

    def only(self, o):
        return f"∀{self.R(rname(o['path'][0]))}.{self.wrap(self.tr(o['pattern']))}"


# ------------------------------------------------------------------------------------------------- constraints beyond the TBox axioms
def checks_dl(d):
    C, R, inv = d.C, d.R, d.inv
    M = (lambda x: f"${x}$") if d.mode == "tex" else (lambda x: x)  # noqa: E731
    return {
        "parthood-preserves-kind": ("OWL 2 DL", [f"{C(k)} ⊑ ∀{R('hasPart')}.{C(k)}" for k in
                                                ("Process", "MaterialEntity", "PlanSpecification", "InformationEntity")],
                                    "stated in the kinds section; parthood never crosses kinds"),
        "answer-from-a-comparison-that-updates-the-belief": (
            "OWL 2 DL", [f"{C('Insight')} ⊓ ∃{R('hasRole')}.{C('AnswerRole')} ⊑ ∃{R('from')}.({C('Comparison')} ⊓ ∃{R('updates')}.{C('Belief')})"],
            "that the comparison is one of the same experiment needs variable sharing (FOL)"),
        "comparisons-between-units": (
            "SROIQ role inclusion", [f"{R('hasComparison')} ∘ {R('between')} ⊑ {R('hasUnit')}"],
            "read as an integrity constraint: under the open world an OWL reasoner would infer the unit, not report it"),
        "an-effect-insight-per-comparison": (
            "FOL", [f"∀e,c. {R('hasComparison')}(e,c) → ∃i. {R('hasInsight')}(e,i) ∧ {R('from')}(i,c) ∧ "
                    f"∀s. ({R('determines')}∘{R('of')})(c,s) → {R('of')}(i,s)"],
            "OWL 2 states only " + M(f"{C('Comparison')} ⊑ ∃{inv('from')}.({C('Insight')} ⊓ ∃{R('hasRole')}.{C('EffectRole')})")),
        "parts-conform-to-their-concepts": ("DL semantics", ["(every TBox axiom holds of every individual)"],
                                            "the closed-world checker evaluates each part against its own concept"),
        "each-step-in-one-phase": ("OWL 2 DL", [f"{C('Action')} ⊑ (=1 {inv('hasStep')}.{C('Phase')})"], ""),
        "each-exposure-realized-once": (
            "OWL 2 DL + rule", [f"{C('Exposure')} ⊑ (=1 {inv('realizes')}.{C('InterventionAction')})",
                                f"realizes(a,x) ← {R('hasCulture')}(a,u) ∧ {R('hasTreatment')}(u,t) ∧ {R('hasExposure')}(t,x) ∧ "
                                + d.T(" same substance, dose and time")],
            "the rule that computes realizes compares data values of two individuals (SWRL)"),
        "each-unit-observed-once": (
            "FOL", [f"∀e,u. {R('hasUnit')}(e,u) → {'∃=1' if d.mode == 'txt' else '∃^{=1}'} s. {R('hasPart')}(e,s) ∧ {C('ObservationAction')}(s) ∧ {R('hasCulture')}(s,u)"],
            "OWL 2 states only " + M(f"{C('Culture')} ⊑ (=1 {inv('hasCulture')}.{C('ObservationAction')})") + ", not 'within the same experiment'"),
        "each-comparison-realized-once": (
            "OWL 2 DL + rule", [f"{C('Comparison')} ⊑ (=1 {inv('realizes')}.{C('AnalysisAction')})"],
            "realizes is computed from the analysis's statistic (the pair of units it compares)"),
        "units-in-distinct-wells-of-the-site": (
            "FOL (path agreement)", [f"{C('Culture')} ⊑ (=1 {R('containedIn')}.{C('Well')}),   {C('Well')} ⊑ (≤1 {R('contains')}.{TOP})",
                                     f"∀e,u,v. {R('hasUnit')}(e,u) ∧ {R('hasUnit')}(e,v) → "
                                     f"({R('containedIn')}∘{R('partOf')})(u) = ({R('containedIn')}∘{R('partOf')})(v)"],
            "the first line is OWL 2 DL; 'one plate for all units' is a role-value map, undecidable with the rest"),
        "phases-in-time-order": (
            "ALC(D) feature chains", [f"{C('ComparativeExperiment')} ⊑ ∃({R('cultivation')}∘{R('toTime')}, {R('observationPhase')}∘{R('atTime')}).≤"],
            "compares two data values reached by different paths: a concrete-domain predicate, not available in OWL 2"),
        "single-difference": (
            "FOL with counting", [f"∀c,u,v. {R('between')}(c,u) ∧ {R('between')}(c,v) ∧ u≠v → |X(u) △ X(v)| = 1 ∧ "
                                  f"∀x ∈ X(u) △ X(v). {R('exposedTo')}(x) = ({R('determines')}∘{R('of')})(c)",
                                  "(X(u): the exposures of the treatment of u, as substance, dose and time)"],
            "beyond SROIQ: compares two individuals' sets of exposures (rule with aggregation, SPARQL, or the checker)"),
        "rescue-after-challenge": (
            "ALC(D) feature chains", [f"∃{R('hasRole')}.{C('RescuedRole')} ⊑ ∃({R('rescueExposure')}∘{R('atTime')}, "
                                      f"{R('challengeExposure')}∘{R('atTime')}).>"],
            "with rescueExposure, challengeExposure functional subroles of hasTreatment∘hasExposure; not OWL 2"),
    }


# ------------------------------------------------------------------------------------------------- RBox
def rbox(roles, d):
    lines = []
    for r, v in roles.items():
        if v["parent"]:
            lines.append(f"{d.R(rname(r))} ⊑ {d.R(rname(v['parent']))}")
    for r, v in roles.items():
        if v["transitive"]:
            lines.append(f"Trans({d.R(rname(r))})")
        if v["inverse"]:
            lines.append(f"{d.R(rname(v['inverse']))} ≡ {d.inv(rname(r))}")
        if v["chain"]:
            lines.append(f"{' ∘ '.join(d.R(rname(c)) for c in v['chain'])} ⊑ {d.R(rname(r))}")
    return lines


def non_simple(roles):
    """OWL 2: a role is non-simple if it is transitive, the head of a chain, or has a non-simple subrole."""
    ns = {r for r, v in roles.items() if v["transitive"] or v["chain"]}
    ns |= {v["inverse"] for r, v in roles.items() if r in ns and v["inverse"]}
    changed = True
    while changed:
        changed = False
        for r, v in roles.items():
            if v["parent"] and r in ns and v["parent"] not in ns:
                ns.add(v["parent"])
                changed = True
    return ns


def numbered_roles(concepts):
    out = set()
    for c in concepts.values():
        for h in c["has"]:
            if h["card"][0] != "at-least" or int(h["card"][1]) > 1:
                out.add(h["path"][-1])
    return out


# ------------------------------------------------------------------------------------------------- ABox
def abox(T, E, d):
    """Assertions for the experiment as derived and placed (individual names from roles and ids)."""
    I = lambda n: n if d.mode == "txt" else rf"\mathtt{{{n.replace('_', chr(92) + '_')}}}"  # noqa: E731
    out = []
    a = lambda c, i: out.append(f"{d.C(c)}({I(i)})")  # noqa: E731
    r = lambda p, x, y: out.append(f"{d.R(p)}({I(x)}, {I(y)})")  # noqa: E731
    a(camel(slot(E, "instance-of")[1]), "e")
    q = slot(E, "question")[1]
    r("hasQuestion", "e", "q")
    for c in dslots(q):
        if c[0] == "candidate":
            m = slot(c[1], "name")[1]
            a("RecoveryModel", m)
            r("hasCandidate", "q", m)
    a("Belief", "b")
    r("hasBelief", "e", "b")
    for role in [slot(s[1], "role")[1] for s in dslots(E) if s[0] == "substance"]:
        a("Substance", f"s_{role}")
        r("hasRole", f"s_{role}", f"{role}Role")
        r("hasSubstance", "e", f"s_{role}")
    for role, u in units(T, E).items():
        a("Culture", role)
        r("hasCulture", "e", role)
        r("hasRole", role, f"{role}Role")
        ex = exposures(u)
        if ex:
            a("Treatment", f"t_{role}")
            r("hasTreatment", role, f"t_{role}")
            for e in ex:
                k = ex_key(e)
                n = f"x_{role}_{k[0]}"
                a("Exposure", n)
                r("hasExposure", f"t_{role}", n)
                r("exposedTo", n, f"s_{k[0]}")
        else:
            a("EmptyTreatment", f"t_{role}")
            r("hasTreatment", role, f"t_{role}")
    for c in T.fillers(E, ["comparison"]):
        cr = role_of(c)
        a("Comparison", f"c_{cr}")
        r("hasComparison", "e", f"c_{cr}")
        for b in slot(c, "between")[1:]:
            r("between", f"c_{cr}", role_of(b))
        if slot(c, "licenses"):
            r("licenses", f"c_{cr}", f"c_{role_of(slot(c, 'licenses')[1])}")
    for i in T.fillers(E, ["insight"]):
        ir = role_of(i)
        n = f"ins_{ir}" + (f"_{role_of(slot(i, 'of')[1])}" if slot(i, "of") else "")
        a("Insight", n)
        r("hasInsight", "e", n)
        r("from", n, f"c_{role_of(slot(i, 'from')[1])}")
    for p in T.fillers(E, ["phase"]):
        pn = p[1].replace("-phase", "")
        a(camel(p[1]), pn)
        r("hasPhase", "e", pn)
        for s in T.fillers(p, ["step"]):
            sn = slot(s, "name")[1]
            a(camel(slot(s, "kind")[1]) + "Action", sn)
            r("hasStep", pn, sn)
    for s in steps_of(T, E, "intervention"):
        u, sub = role_of(slot(s, "culture")[1]), role_of(slot(s, "substance")[1])
        r("realizes", slot(s, "name")[1], f"x_{u}_{sub}")
    for s in steps_of(T, E, "analysis"):
        pair = [role_of(x[1]) for x in slot(s, "statistic")[1][1:]]
        c = next(role_of(c) for c in T.fillers(E, ["comparison"]) if [role_of(b) for b in slot(c, "between")[1:]] == pair)
        r("realizes", slot(s, "name")[1], f"c_{c}")
    for site in T.fillers(E, ["site"]):
        pid = slot(site, "id")[1]
        a("Plate", pid)
        r("hasSite", "e", pid)
        for w in T.fillers(site, ["well"]):
            wid = slot(w, "id")[1]
            a("Well", wid)
            r("hasWell", pid, wid)
            for c in T.fillers(w, ["contains"]):
                r("contains", wid, role_of(c))
    return out


# ------------------------------------------------------------------------------------------------- the document
def axioms(T, d):
    concepts = T.concepts
    groups = {"kinds": [], "entities": [], "phases": [], "experiments": []}
    for c, v in concepts.items():
        lhs = d.concept(c)
        ax = [f"{lhs} ⊑ {' ⊓ '.join(d.concept(p) for p in v['parents'])}"] if v["parents"] else []
        ax += [f"{lhs} ⊑ {d.has(h)}" for h in v["has"]] + [f"{lhs} ⊑ {d.only(o)}" for o in v["only"]]
        g = ("kinds" if v["kind"] else "experiments" if c in T.experiments else
             "phases" if "phase" in ancestors(c, concepts) else "entities")
        groups[g].append(dict(name=c, doc=v["doc"], axioms=ax, checks=v["checks"], procedure=v["procedure"]))
    kinds = [d.concept(c) for c, v in concepts.items() if v["kind"]]
    disj = [f"{a} ⊓ {b} ⊑ {BOT}" for i, a in enumerate(kinds) for b in kinds[i + 1:]]
    kp = [f"{k} ⊑ ∀{d.R('hasPart')}.{k}" for k in kinds]
    acts = [f"{d.C(k + 'Action')} ⊑ {d.C('Action')}" for k in ("Intervention", "Growth", "Observation", "Interpretation", "Analysis")]
    return groups, disj, kp, acts


def tt(s):
    """Monospace text that may break after hyphens."""
    return s.replace("-", r"-\allowbreak{}")


def tex_escape(s):
    return s.replace("_", r"\_").replace("&", r"\&").replace("%", r"\%").replace("#", r"\#")


def brk(x):
    return x.replace(" ⊓ ", r" ⊓\allowbreak ").replace(" ⊔ ", r" ⊔\allowbreak ").replace(" ∧ ", r" ∧\allowbreak ")


def build_tex(T, E, res, ns, used, bad):
    d = DL("tex")
    groups, disj, kp, acts = axioms(T, d)
    CH = checks_dl(d)
    rb = rbox(T.roles, d)
    ab = abox(T, E, d)
    m = lambda x: f"${x}$"  # noqa: E731
    out = [r"""\documentclass[10pt,a4paper]{article}
\usepackage[margin=2.2cm]{geometry}
\usepackage{fontspec,unicode-math}
\setmainfont{Libertinus Serif}\setsansfont{IBM Plex Sans}[Scale=0.9]\setmonofont{IBM Plex Mono}[Scale=0.85]
\setmathfont{Libertinus Math}
\usepackage{graphicx,booktabs,tabularx,multicol,xcolor,hyperref,enumitem}
\hypersetup{colorlinks,linkcolor=black,urlcolor=blue!50!black}
\newcommand{\ax}[1]{\par{\raggedright\noindent\hangindent=2.5em\hangafter=1 $#1$\par}\smallskip}
\setlength{\parindent}{0pt}\setlength{\parskip}{3pt}\setlength{\emergencystretch}{3em}
\newcommand{\tth}[1]{\texttt{#1}}
\title{Experiment concepts in description logic\\[2pt]\large with a partonomy, and the challenge-rescue experiment as an instance}
\author{Generated from \texttt{experiment\_concepts.ldl} by \texttt{rsa/experiment\_dl.py}}
\date{}
\begin{document}\maketitle
\section*{Conventions}
The concepts are stated in $\mathcal{SROIQ}(\mathbf{D})$, the logic of OWL~2~DL. Concept names are set in
$\mathsf{sans}$, role names in $\mathit{italics}$, individuals in $\mathtt{mono}$. A filler restriction
$(=\!n\;r.C)$ means exactly $n$ $r$-successors in $C$; $\exists r.C$ at least one; $\forall r.C$ only $C$.
Each LDL clause \texttt{(has \emph{role pattern cardinality})} becomes one number restriction,
\texttt{(only \emph{role pattern})} one value restriction, a pattern's slots nested existentials, and
\texttt{(role $x$)} the restriction $\exists\mathit{hasRole}.\mathsf{X\,Role}$.

Conformance of an experiment is checked under the \emph{closed-world} reading: the axioms are integrity
constraints over the instance as given, derived and placed (\texttt{rsa/experiment\_concepts.py}). An OWL reasoner
reads the same axioms under the open world: it would infer a missing culture rather than report it. Constraints that
$\mathcal{SROIQ}(\mathbf{D})$ cannot express are stated in Section~\ref{sec:beyond} in the logic they need.

\section{Roles and partonomy (RBox)}
Parthood ($\mathit{hasPart}$) is transitive and has four kinds: temporal parts of processes ($\mathit{hasPhase}$,
$\mathit{hasStep}$), material parts ($\mathit{hasWell}$) and components of plans and information entities
($\mathit{hasComponent}$: $\mathit{hasExposure}$, $\mathit{hasObservation}$, $\mathit{hasCandidate}$). Three relations
are deliberately \emph{not} parthood: a culture is \emph{contained in} a well (location), an action \emph{realizes} a
part of the plan, and a culture \emph{participates} in the actions it undergoes.
"""]
    out += [r"\begin{multicols}{2}"] + [rf"\ax{{{brk(x)}}}" for x in rb] + [r"\end{multicols}"]
    out.append(rf"OWL~2 allows number restrictions only on simple roles. Non-simple here: "
               rf"{', '.join(m(d.R(rname(r))) for r in sorted(ns))}. Roles in number restrictions: "
               rf"{', '.join(m(d.R(rname(r))) for r in sorted(used))}. "
               + (r"All are simple." if not bad else rf"\textbf{{Not simple: {', '.join(bad)}.}}"))
    out.append(r"\section{Kinds and their partonomy}")
    out.append("Four disjoint kinds. Parthood never crosses kinds: a process has processes as parts, a plate has wells, "
               "a treatment has exposures, a question has candidate hypotheses.")
    out += [r"\begin{multicols}{2}"] + [rf"\ax{{{brk(x)}}}" for x in disj + kp] + [r"\end{multicols}"]
    out.append(r"\section{Entities}")
    out += [r"\begin{multicols}{2}"] + [rf"\ax{{{brk(x)}}}" for g in groups["entities"] for x in g["axioms"]] \
        + [rf"\ax{{{brk(x)}}}" for x in acts] + [rf"\ax{{{brk(x)}}}" for x in d.defs.values()] + [r"\end{multicols}"]
    out.append(r"\section{Phases: the process partonomy of an experiment}")
    for g in groups["phases"]:
        out.append(rf"\textbf{{{camel(g['name'])}}} --- {tex_escape(g['doc'])}.")
        out += [rf"\ax{{{brk(x)}}}" for x in g["axioms"]]
    out.append(r"\section{Experiments}")
    out.append(r"\begin{center}\includegraphics[width=\linewidth]{experiment_concepts.pdf}\end{center}")
    for g in groups["experiments"]:
        out.append(rf"\subsection*{{{camel(g['name'])}}}{tex_escape(g['doc'])}.")
        out += [rf"\ax{{{brk(x)}}}" for x in g["axioms"]]
        if g["checks"]:
            out.append(r"Further constraints (Section~\ref{sec:beyond}): " + ", ".join(rf"\tth{{{tt(c)}}}" for c in g["checks"]) + ".")
        if g["procedure"]:
            out.append(r"Procedure (rules that derive the actions; not DL axioms):\begin{itemize}[nosep,leftmargin=1.5em]"
                       + "".join(rf"\item {{\small\tth{{{tt(tex_escape(p))}}}}}" for p in g["procedure"]) + r"\end{itemize}")
    out.append(r"\section{Constraints beyond the TBox axioms}\label{sec:beyond}")
    out.append(r"\begin{tabularx}{\linewidth}{@{}p{3.6cm}>{\raggedright\arraybackslash}p{2.4cm}>{\raggedright\arraybackslash}X@{}}\toprule constraint & logic & statement \\ \midrule")
    for k, (logic, fs, note) in CH.items():
        body = r" \newline ".join(f"${brk(f)}$" if not f.startswith("(") else tex_escape(f) for f in fs)
        if note:
            body += rf" \newline {{\footnotesize\itshape {note if '$' in note else tex_escape(note)}}}"
        out.append(rf"\tth{{{tt(k)}}} & {logic} & {body} \\[3pt]")
    out.append(r"\bottomrule\end{tabularx}")
    out.append(r"\section{The challenge-rescue experiment as an instance}")
    out.append(r"The ABox below is the experiment of \texttt{experiment.ldl} as derived (phases and steps from the "
               r"procedure) and placed (plate and wells from the mapping to Cell~01). Doses and times are omitted.")
    out.append(r"\begin{center}\includegraphics[width=\linewidth]{experiment_partonomy.pdf}\end{center}")
    out.append(r"{\small\begin{multicols}{2}")
    out += [rf"${x}$\par" for x in ab]
    out.append(r"\end{multicols}}")
    conf = res["conformance"]
    out.append(r"\subsection*{Conformance and classification (closed world)}")
    out.append(r"\begin{tabular}{@{}lrr@{}}\toprule concept & constraints & satisfied \\ \midrule")
    for c, rs in conf.items():
        out.append(rf"{camel(c)} & {len(rs)} & {sum(r['ok'] for r in rs)} \\")
    out.append(r"\bottomrule\end{tabular}")
    out.append(rf"\par Most specific concept: $\mathsf{{{camel(res['most_specific'][0])}}}$ (declared: "
               rf"$\mathsf{{{camel(res['declared'])}}}$). Every part satisfies its own concept "
               rf"({sum(v[0] for v in res['parts'].values())}/{sum(v[1] for v in res['parts'].values())}).")
    out.append(r"\subsection*{Negative controls}")
    out.append(r"\begin{tabularx}{\linewidth}{@{}>{\raggedright\arraybackslash}p{4.6cm}>{\raggedright\arraybackslash}X>{\raggedright\arraybackslash}X@{}}\toprule modification & fails at & still an instance of \\ \midrule")
    for n, v in res["negative_controls"].items():
        out.append(rf"{tex_escape(n)} & {', '.join(camel(c) for c in v['fails_at'])} & "
                   rf"{', '.join(camel(c) for c in v['most_specific']) or '---'} \\")
    out.append(r"\bottomrule\end{tabularx}")
    out.append(r"\end{document}")
    return "\n".join(out)


def build_txt(T, E, ns, used):
    d = DL("txt")
    groups, disj, kp, acts = axioms(T, d)
    out = ["EXPERIMENT CONCEPTS IN DESCRIPTION LOGIC (SROIQ(D) = OWL 2 DL), generated from experiment_concepts.ldl", "",
           "RBOX (role hierarchy, partonomy)"] + ["  " + x for x in rbox(T.roles, d)]
    out += [f"  non-simple roles: {sorted(rname(r) for r in ns)}; roles in number restrictions: {sorted(rname(r) for r in used)}", "",
            "KINDS (disjoint; parthood never crosses kinds)"] + ["  " + x for x in disj + kp]
    out += ["", "ENTITIES"] + ["  " + x for g in groups["entities"] for x in g["axioms"]] + ["  " + x for x in acts] \
        + ["  " + x for x in d.defs.values()]
    for name in ("phases", "experiments"):
        out += ["", name.upper()]
        for g in groups[name]:
            out += [f"  -- {camel(g['name'])}: {g['doc']}"] + ["  " + x for x in g["axioms"]]
            if g["checks"]:
                out.append(f"     further constraints: {', '.join(g['checks'])}")
    out += ["", "CONSTRAINTS BEYOND THE TBOX AXIOMS"]
    for k, (logic, fs, note) in checks_dl(d).items():
        out += [f"  {k} [{logic}]"] + [f"      {f}" for f in fs] + ([f"      ({note})"] if note else [])
    out += ["", "ABOX (the experiment as derived and placed)"] + ["  " + x for x in abox(T, E, d)]
    return "\n".join(out) + "\n"


def main(argv):
    r = subprocess.run([sys.executable, "-m", "rsa.experiment_concepts"], capture_output=True, text=True,
                       cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-2000:])
        return 1
    res = json.load(open(os.path.join(OUT, "experiment_concepts.json")))
    roles, concepts = load_concepts()
    T = TBox(roles, concepts)
    E, _ = derived_and_placed(parse(open(INSTANCE).read())[0])
    ns, used = non_simple(roles), numbered_roles(concepts)
    bad = sorted(used & ns)
    open(os.path.join(OUT, "experiment_dl.txt"), "w").write(build_txt(T, E, ns, used))
    build = os.path.join(OUT, "experiment_dl")
    os.makedirs(build, exist_ok=True)
    for f in ("experiment_concepts", "experiment_partonomy"):
        shutil.copy(os.path.join(OUT, f + ".pdf"), os.path.join(build, f + ".pdf"))
    tex = build_tex(T, E, res, ns, used, bad)
    open(os.path.join(build, "experiment_dl.tex"), "w").write(tex)
    p = subprocess.run(["latexmk", "-lualatex", "-interaction=nonstopmode", "-halt-on-error", "experiment_dl.tex"],
                       cwd=build, capture_output=True, text=True)
    log = open(os.path.join(build, "experiment_dl.log"), errors="replace").read() if os.path.exists(os.path.join(build, "experiment_dl.log")) else ""
    pages = re.search(r"Output written on .*?\((\d+) pages?", log)
    warn = len(re.findall(r"(Overfull|Underfull) \\hbox", log)) + len(re.findall(r"Missing character", log))
    if p.returncode == 0:
        shutil.copy(os.path.join(build, "experiment_dl.pdf"), os.path.join(OUT, "experiment_dl.pdf"))
        shutil.copy(os.path.join(build, "experiment_dl.tex"), os.path.join(OUT, "experiment_dl.tex"))
    print(f"[dl] {len(concepts)} concepts, {len(roles)} roles; number restrictions on simple roles only: {not bad}"
          f"{'' if not bad else ' (not simple: ' + str(bad) + ')'}; latex exit {p.returncode}, "
          f"{pages.group(1) if pages else '?'} pages, {warn} box/glyph warnings -> rsa/out/experiment_dl.pdf, .tex, .txt")
    if p.returncode:
        print(p.stdout[-3000:])
    return 0 if p.returncode == 0 and not bad else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
