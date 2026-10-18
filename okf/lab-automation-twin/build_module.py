"""Build the lab-automation-twin OKF module from src/tbox.py.

  L2-conceptual-framework/ontology/<module>-dl.md   AICOR-style DL modules (Manchester), read by AICOR's exporter
                                                    (okf_owl.py via ResearchSpace tools/okf_reason.py)
  build/lab-automation-twin.ofn                     full-semantics OWL 2 (definitions, negation, property axioms)
  docs/axioms.md, docs/axioms.tex                   every concept with its DL axioms
  docs/partonomy_classes.{md,dot,svg,png}           class-level partonomy
Checks (exit 1): every referenced name is local or upstream (AICOR + robot-scientist + VRB + normative-admissibility,
from build/upstream-names.txt), no local name collides with an upstream one, every concept has >= 1 axiom and a doc.
Run: env_cad/bin/python okf/lab-automation-twin/build_module.py
"""

import collections
import os
import re
import subprocess
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))
import tbox  # noqa: E402
from dl import AICOR_NS, PREFIXES, And, E, Exact, Min, Or, Some, q  # noqa: E402

ONTO_DIR = os.path.join(HERE, "L2-conceptual-framework", "ontology")
BUILD = os.path.join(HERE, "build")
DOCS = os.path.join(HERE, "docs")
MODULE_IRI = "http://aicor.knowledge/okf/lab-automation-twin"
TODAY = date.today().isoformat()
INTRO = {
    "lab-twin-core": "Properties of the module (partonomy, location, containment, poses, SDT node -> referent) and "
                     "the SDT node classes. AICOR's mereology properties are bare and frozen, so the module adds "
                     "sub-properties with the characteristics it needs.",
    "lab-twin-site": "The laboratory site (robot-scientist LaboratorySite / LaboratoryCell), its premises, rooms and "
                     "zones (layout S1), building elements, the Cell 01 fit-out and the site's safety and service "
                     "equipment.",
    "lab-twin-devices": "Automated stations as VRB LabAutomationDevices, the site's manual equipment, and the "
                        "mechanisms and sensors of devices (not AICOR robot-body links or sensors: D-LAT-1).",
    "lab-twin-robots": "Cell robots (AICOR Robot), robot bodies, exchangeable tools and robot skills.",
    "lab-twin-labware": "Labware, wells, culture medium and organoids, reagent portions.",
    "lab-twin-poses": "Named poses of the twin (USD Xform frames) as AICOR SpatialPoses, typed by the task they "
                      "afford.",
    "lab-twin-tasks": "Lab task types (concepts) and lab actions (events), with defined action classes.",
    "lab-twin-device-manuals": "Device manual knowledge: Cell 01's SDT component contracts as manuals, with "
                               "operating procedures (RS ActionContract), preconditions, effects, setpoints, "
                               "constraints, monitors (AICOR ProcessMonitor), failure modes (AICOR "
                               "FailureSignature), recovery (AICOR Repair), risk controls and device process "
                               "microtheories (AICOR BodyWorldProcessMicrotheory).",
    "lab-twin-safe-action": "Safe action: lab hazards, safety rules as AICOR IncapabilityAssertions, biosafety as RS "
                            "ContaminationCompatibility, authorisation as normative-admissibility Norms, their "
                            "enforcement (interlocks, controller checks, critic gates) and the classification of "
                            "candidate actions as unsafe / unauthorised.",
    "lab-twin-culture-experiments": "Culture experiments: Cell 01's challenge-rescue design (RS StudyDesign) with "
                                    "arms, intervention specifications, observation schedule, interventions (RS "
                                    "BiologicalIntervention), morphology readouts (RS CellViabilityReadout), runs (RS "
                                    "ExperimentalEpisode), hypotheses and (withheld) conclusions.",
    "lab-twin-records": "Cell 01's NEEM-style action records (RS LabExecutionTrace), monitor results and routing "
                        "(commit / quarantine / escalation / invalidation).",
}


def upstream_names():
    p = os.path.join(BUILD, "upstream-names.txt")
    if not os.path.exists(p):
        sys.exit("build/upstream-names.txt missing: run `make upstream` first")
    return {l.strip() for l in open(p) if l.strip()}


def check():
    up = upstream_names()
    errs = []
    local_c = [c["name"] for c in tbox.CLASSES]
    local_p = [p["name"] for p in tbox.PROPS]
    local_i = [i["name"] for i in tbox.INDIVIDUALS]
    own = {n for n in local_c + local_p + local_i if ":" not in n}
    for n in sorted(own & up):
        errs.append(f"collision: {n} already exists upstream (reuse it, do not redefine)")
    for n, k in collections.Counter(local_c + local_p).items():
        if k > 1:
            errs.append(f"duplicate definition: {n}")
    refs_c, refs_p = set(), set()
    for c in tbox.CLASSES:
        for e in [E(s) for s in c["sup"]] + c["ax"] + ([E(c["eq"])] if c["eq"] is not None else []):
            refs_c |= e.names()
            refs_p |= e.props()
        if not c["ax"] and c["eq"] is None:
            errs.append(f"{c['name']}: no axiom beyond its named superclasses")
        if not c["doc"]:
            errs.append(f"{c['name']}: no documentation")
    for p in tbox.PROPS:
        refs_p |= set(p["sup"]) | ({p["inv"]} if p["inv"] else set())
    for i in tbox.INDIVIDUALS:
        refs_c.add(i["cls"])
    known = up | own
    for n in sorted(refs_c | refs_p):
        if n.split(":")[0] in ("dul", "soma"):
            continue                      # upper-level stand-ins (dul_X / soma_X), AICOR convention
        if n not in known:
            errs.append(f"unknown name: {n}")
    return errs, own & {c for c in local_c}, up


# ------------------------------------------------------------------------------------------------- Manchester
def man_frame(c, disj):
    L = [f"Class: {c['name']}"]
    for s in c["sup"]:
        L.append(f"    SubClassOf: {s}")
    if c["ax"]:
        L.append("    SubClassOf:")
        L += [f"        {a.man()}," for a in c["ax"]]
        L[-1] = L[-1].rstrip(",")
    if c["eq"] is not None:
        eq = E(c["eq"])
        parts = eq.xs if isinstance(eq, And) else [eq]
        L.append("    -- definition (≡): the intersection of the items below. AICOR's exporter reads them as")
        L.append("    -- necessary conditions only (D-LAT-2); the full OWL export keeps the definition.")
        L.append("    EquivalentTo:")
        L += [f"        {x.man()}," for x in parts]
        L[-1] = L[-1].rstrip(",")
    for others in disj.get(c["name"], []):
        L.append(f"    DisjointWith: {', '.join(others)}")
    L.append(f"    -- {c['doc']}")
    return L


def man_prop(p):
    kind = "ObjectProperty" if p["kind"] == "object" else "DataProperty"
    L = [f"{kind}: {p['name']}"]
    if p["chars"]:
        L.append(f"    Characteristics: {', '.join(p['chars'])}")
    if p["kind"] == "data" and p["range"]:
        L.append(f"    Range: {p['range']}")
    for s in p["sup"]:
        L.append(f"    -- SubPropertyOf: {s}   (full OWL export; not read by okf_owl.py)")
    if p["inv"]:
        L.append(f"    -- InverseOf: {p['inv']}")
    L.append(f"    -- {p['doc']}")
    return L


def write_dl_md():
    os.makedirs(ONTO_DIR, exist_ok=True)
    for f in os.listdir(ONTO_DIR):
        if f.endswith("-dl.md"):
            os.remove(os.path.join(ONTO_DIR, f))
    mods = collections.OrderedDict()
    for kind, items in (("C", tbox.CLASSES), ("P", tbox.PROPS), ("D", tbox.DISJOINT), ("I", tbox.INDIVIDUALS)):
        for x in items:
            mods.setdefault(x["module"], collections.defaultdict(list))[kind].append(x)
    for (key, title), m in mods.items():
        disj = collections.defaultdict(list)
        for d in m["D"]:
            ns = d["names"]
            for i, a in enumerate(ns):
                if ns[i + 1:]:
                    disj[a].append(ns[i + 1:])
        body = []
        for p in m["P"]:
            body += man_prop(p) + [""]
        for c in m["C"]:
            body += man_frame(c, disj) + [""]
        for i in m["I"]:
            body += [f"Individual: {i['name']}", f"    Types: {i['cls']}", ""]
        n_skip = sum(1 for c in m["C"] for a in c["ax"] if not a.simple())
        md = ["---", "type: dl-definition", f"title: \"{title} (DL definitions)\"", f"derived_from: L1/{key}",
              "maturity: L2", "status: draft", f"timestamp: {TODAY}", "module: lab-automation-twin", "---", "",
              f"# {title}", "", INTRO.get(key, ""), "",
              "Every class is positioned under an upstream AICOR / robot-scientist / VRB / normative-admissibility "
              "concept or an AICOR upper-level stand-in (`dul:` / `soma:`). Generated from `src/tbox.py` by "
              "`build_module.py`; edit the source, not this file.", "",
              "## Manchester syntax", "", "```"] + body + ["```", "",
              "## Export notes", "",
              f"- Restrictions AICOR's exporter cannot read (negation, nested fillers, inverse roles): {n_skip}; "
              "they are kept in `build/lab-automation-twin.ofn`.",
              "- Definitions (≡) are necessary conditions in the AICOR export (D-LAT-2).", ""]
        open(os.path.join(ONTO_DIR, f"{key}-dl.md"), "w").write("\n".join(md) + "\n")
    return len(mods)


# ------------------------------------------------------------------------------------------------- full OWL
def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def write_ofn():
    L = [f"Prefix({k}:=<{v}>)" for k, v in PREFIXES.items()]
    L += ["", f"Ontology(<{MODULE_IRI}>",
          'Annotation(rdfs:label "lab-automation-twin OKF module (full semantics)"@en)',
          'Annotation(rdfs:comment "AICOR L2 extension for an automated biology lab and its semantic digital twin. '
          'Generated by okf/lab-automation-twin/build_module.py. Merge with the upstream union '
          '(AICOR + robot-scientist + VRB + normative-admissibility) to reason."@en)']
    for c in tbox.CLASSES:
        n = q(c["name"])
        L.append(f"Declaration(Class({n}))")
        L.append(f'AnnotationAssertion(rdfs:label {n} "{c["name"]}")')
        L.append(f'AnnotationAssertion(rdfs:comment {n} "{esc(c["doc"])}"@en)')
        for s in c["sup"]:
            L.append(f"SubClassOf({n} {E(s).ofn()})")
        for a in c["ax"]:
            L.append(f"SubClassOf({n} {a.ofn()})")
        if c["eq"] is not None:
            L.append(f"EquivalentClasses({n} {E(c['eq']).ofn()})")
    for d in tbox.DISJOINT:
        L.append(f"DisjointClasses({' '.join(q(x) for x in d['names'])})")
    for p in tbox.PROPS:
        n, obj = q(p["name"]), p["kind"] == "object"
        kind = "ObjectProperty" if obj else "DataProperty"
        L.append(f"Declaration({kind}({n}))")
        L.append(f'AnnotationAssertion(rdfs:label {n} "{p["name"]}")')
        L.append(f'AnnotationAssertion(rdfs:comment {n} "{esc(p["doc"])}"@en)')
        for s in p["sup"]:
            L.append(f"Sub{kind}Of({n} {q(s)})")
        if p["inv"]:
            L.append(f"InverseObjectProperties({n} {q(p['inv'])})")
        if not obj and p["range"]:
            L.append(f"DataPropertyRange({n} {p['range']})")
        for ch in p["chars"]:
            L.append(f"{ch}{kind}({n})")
    for i in tbox.INDIVIDUALS:
        L.append(f"Declaration(NamedIndividual({q(i['name'])}))")
        L.append(f"ClassAssertion({q(i['cls'])} {q(i['name'])})")
    L.append(")")
    os.makedirs(BUILD, exist_ok=True)
    open(os.path.join(BUILD, "lab-automation-twin.ofn"), "w").write("\n".join(L) + "\n")
    return len(L)


# ------------------------------------------------------------------------------------------------- docs
TEX = [("⊑", r"\sqsubseteq "), ("≡", r"\equiv "), ("⊓", r"\sqcap "), ("⊔", r"\sqcup "), ("∃", r"\exists "),
       ("∀", r"\forall "), ("¬", r"\neg "), ("≥", r"\geq "), ("≤", r"\leq "), ("⊤", r"\top "), ("⊥", r"\bot "),
       ("⁻", r"^{-}")]
_ROLE = re.compile(r"(∃|∀|[≥≤=]\d+ )((?:[a-z]+:)?[A-Za-z_][A-Za-z0-9_]*)(⁻?)(?=\.)")
_NAME = re.compile(r"(?<![A-Za-z0-9_:{\\@])((?:[a-z]+:)?[A-Za-z_][A-Za-z0-9_]*)")


def tex(s):
    roles = []

    def keep(m):
        roles.append(m.group(2))
        return f"{m.group(1)}@R{len(roles) - 1}@{m.group(3)}"
    s = _ROLE.sub(keep, s)
    s = re.sub(r"([≥≤=])(\d+) (?=@R)", lambda m: ("{=}" if m.group(1) == "=" else m.group(1)) + m.group(2) + r"\, ", s)
    s = _NAME.sub(lambda m: m.group(1) if re.fullmatch(r"R\d+", m.group(1)) else
                  r"\mathsf{" + m.group(1).replace(":", "{:}").replace("_", r"\_") + "}", s)
    for i, r_ in enumerate(roles):
        s = s.replace(f"@R{i}@", r"\mathit{" + r_.replace(":", "{:}").replace("_", r"\_") + "}")
    for a, b in TEX:
        s = s.replace(a, b)
    return s


def dl_lines(c, disj):
    n = c["name"]
    out = [f"{n} ⊑ {E(s).dl()}" for s in c["sup"]] + [f"{n} ⊑ {a.dl()}" for a in c["ax"]]
    if c["eq"] is not None:
        out.append(f"{n} ≡ {E(c['eq']).dl()}")
    out += [f"{n} ⊓ {o} ⊑ ⊥" for o in disj.get(n, [])]
    return out


def texsafe(t):
    for a, b in (("\\", r"\textbackslash{}"), ("%", r"\%"), ("&", r"\&"), ("_", r"\_"), ("#", r"\#"),
                 ("°", r"$^\circ$"), ("µ", r"$\mu$"), ("≥", r"$\geq$"), ("→", r"$\to$"), ("⊑", r"$\sqsubseteq$"),
                 ("≡", r"$\equiv$"), ("×", r"$\times$")):
        t = t.replace(a, b)
    return t


def write_docs():
    os.makedirs(DOCS, exist_ok=True)
    disj = collections.defaultdict(list)
    for d in tbox.DISJOINT:
        for x in d["names"]:
            disj[x] += [y for y in d["names"] if y != x][:1]
    mods = collections.OrderedDict()
    for c in tbox.CLASSES:
        mods.setdefault(c["module"], []).append(c)
    n_local = sum(1 for c in tbox.CLASSES if ":" not in c["name"])
    md = ["# lab-automation-twin: concepts and their description-logic axioms", "",
          f"An AICOR OKF module ({TODAY}). Names are AICOR L2 names (one namespace, `{AICOR_NS}`); `dul:` / `soma:` "
          "are AICOR's upper-level stand-ins. Superclasses that are not defined here come from the frozen AICOR core, "
          "the robot-scientist vertical, VRB or normative-admissibility. ⊑ necessary condition, ≡ definition, "
          "⁻ inverse role. Modality of each concept's basis: ✅ stated in a cited source / verified in the twin, "
          "🔧 engineering inference.", "",
          f"{n_local} concepts, {len(tbox.PROPS)} properties, {len(tbox.DISJOINT)} disjointness axioms, "
          f"{len(mods)} modules.", "", "## Modules", ""]
    md += [f"- [{t}](#{re.sub(r'[^a-z0-9 -]', '', t.lower()).replace(' ', '-')}) (`{k}`)" for k, t in mods]
    md.append("")
    tx = [r"\documentclass[10pt]{article}", r"\usepackage[a4paper,margin=17mm]{geometry}",
          r"\usepackage{amsmath,amssymb}", r"\setlength{\parindent}{0pt}",
          r"\title{lab-automation-twin (AICOR OKF module): description-logic axioms}", r"\date{" + TODAY + "}",
          r"\begin{document}", r"\maketitle", r"\small",
          r"Names are AICOR L2 names; \textsf{dul:}/\textsf{soma:} are AICOR's upper-level stand-ins; superclasses "
          r"not defined here are upstream (AICOR core, robot-scientist, VRB, normative-admissibility).", ""]
    for (k, t), cs in mods.items():
        md += [f"## {t}", "", f"`{k}-dl.md` — {INTRO.get(k, '')}", ""]
        tx.append(r"\section*{" + texsafe(t) + "}")
        for c in cs:
            lines = dl_lines(c, disj)
            md += [f"### {c['name']} {c['src']}", "", c["doc"], "", "```text"] + lines + ["```", ""]
            tx.append(r"\paragraph{" + texsafe(c["name"]) + "} " + texsafe(c["doc"]))
            tx += [r"\[\begin{array}{l}"] + [tex(x) + r" \\" for x in lines] + [r"\end{array}\]"]
    md += ["## Properties", "", "| Property | Kind | Super-properties | Characteristics | Description |",
           "|---|---|---|---|---|"]
    for p in tbox.PROPS:
        md.append(f"| `{p['name']}` | {p['kind']} | {', '.join(p['sup']) or '-'}"
                  f"{' (inverse ' + p['inv'] + ')' if p['inv'] else ''} | {', '.join(p['chars']) or '-'} | {p['doc']} |")
    tx.append(r"\end{document}")
    open(os.path.join(DOCS, "axioms.md"), "w").write("\n".join(md) + "\n")
    open(os.path.join(DOCS, "axioms.tex"), "w").write("\n".join(tx) + "\n")


PART = {"hasDirectComponent": "component", "hasPhysicalPart": "part", "hasSubPlace": "subplace",
        "isDirectComponentOf": "~component", "isPhysicalPartOf": "~part", "isSubPlaceOf": "~subplace",
        "containsMaterial": "contains", "isContainedIn": "~contains", "hasProperPart": "part"}


def write_partonomy():
    edges = {}

    def walk(owner, e):
        if isinstance(e, (Some, Exact, Min)) and isinstance(e.p, str) and e.p in PART:
            fill = e.c
            ts = [x.n for x in fill.xs if hasattr(x, "n")] if isinstance(fill, (And, Or)) else \
                ([fill.n] if hasattr(fill, "n") else [])
            qn = "∃" if isinstance(e, Some) else (f"={e.n}" if isinstance(e, Exact) else f"≥{e.n}")
            rel = PART[e.p]
            for t in ts:
                if rel.startswith("~"):
                    edges.setdefault((t, owner, rel[1:]), "")
                else:
                    edges[(owner, t, rel)] = qn
        if isinstance(e, (And, Or)):
            for x in e.xs:
                walk(owner, x)
    for c in tbox.CLASSES:
        for a in c["ax"]:
            walk(c["name"], a)
        if c["eq"] is not None:
            walk(c["name"], E(c["eq"]))
    col = {"component": "#2b6cb0", "part": "#2f855a", "subplace": "#805ad5", "contains": "#b7791f"}
    md = ["# Class-level partonomy (derived from the axioms)", "",
          "`hasDirectComponent` (simple, ⊑ AICOR hasComponent) under `hasPhysicalPart` (transitive, ⊑ AICOR hasPart); "
          "places: `hasSubPlace`; containment (`containsMaterial`) is listed separately - it is not parthood.", ""]
    for rel in col:
        md += [f"## {rel}", "", "| Whole | Part | Axiom |", "|---|---|---|"]
        md += [f"| {w} | {p} | {qn or 'inverse'} |" for (w, p, r), qn in sorted(edges.items()) if r == rel] + [""]
    open(os.path.join(DOCS, "partonomy_classes.md"), "w").write("\n".join(md) + "\n")
    dot = ["digraph partonomy {", 'rankdir=LR; node [shape=box, fontname="Helvetica", fontsize=10, style="rounded,'
           'filled", fillcolor="#eef3fb", color="#4a6fa5"]; edge [fontname="Helvetica", fontsize=8];']
    for (w, p, r), qn in sorted(edges.items()):
        if not p.startswith(("dul:", "soma:")) and p not in ("Entity", "LabArtifact"):
            dot.append(f'"{w}" -> "{p}" [color="{col[r]}", label="{qn}"];')
    dot.append("}")
    dp = os.path.join(DOCS, "partonomy_classes.dot")
    open(dp, "w").write("\n".join(dot) + "\n")
    for fmt in ("svg", "png"):
        subprocess.run(["dot", f"-T{fmt}", "-Gdpi=100", dp, "-o", dp.replace(".dot", f".{fmt}")], check=False)
    return len(edges)


def main():
    errs, own_classes, up = check()
    if errs:
        print("\n".join(errs))
        sys.exit(1)
    n_mod = write_dl_md()
    n_ofn = write_ofn()
    write_docs()
    n_part = write_partonomy()
    print(f"[build] {len(own_classes)} concepts ({sum(1 for c in tbox.CLASSES if c['src'] == '✅')} ✅ sourced), "
          f"{len(tbox.PROPS)} properties, {len(tbox.DISJOINT)} disjointness axioms, {n_part} partonomy axioms; "
          f"{n_mod} AICOR -dl.md modules; full OWL {n_ofn} lines; upstream names checked against {len(up)}")


if __name__ == "__main__":
    main()
