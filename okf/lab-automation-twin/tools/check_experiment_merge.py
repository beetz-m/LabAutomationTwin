"""Merge the lab module (with its upstream union) and the experiment ontology through bridge/experiment-bridge.ofn,
reason (Konclude over the full union, as the module's own check-full does; HermiT took > 20 min) and report: consistency, unsatisfiable classes, and the subsumptions and equivalences
between the two namespaces that the reasoner infers (not asserted in the bridge). Writes
L2-conceptual-framework/out/experiment-merge-report.{md,json}; exit 1 if inconsistent or a class is unsatisfiable.

    env_cad/bin/python okf/lab-automation-twin/tools/check_experiment_merge.py
"""

import json
import os
import re
import subprocess
import sys
import time

MOD = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOT = os.path.abspath(os.path.join(MOD, "..", ".."))
BUILD = os.path.join(MOD, "build")
ROBOT = os.path.join(MOD, "tools", "robot.jar")
KONCLUDE = os.path.join(MOD, "tools", "konclude", "Binaries", "Konclude")
XO_OFN = os.path.join(ROOT, "rsa", "out", "experiment_ontology", "experiment.owl")   # RDF/XML (owlready2 export)
BRIDGE = os.path.join(MOD, "bridge", "experiment-bridge.ofn")
OUT = os.path.join(MOD, "L2-conceptual-framework", "out")
LAB, XP = "http://aicor.knowledge/l2-ontology.owl#", "https://aicor.example/okf/experiment#"


def robot(*args):
    r = subprocess.run(["java", "-Xmx8g", "-jar", ROBOT, *args], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"[merge] ROBOT {args[0]} failed: {(r.stdout + r.stderr)[-1500:]}")
    return r.stdout + r.stderr


def iri_axioms(path):
    """Asserted SubClassOf / EquivalentClasses pairs between named classes in an OFN file (full IRIs)."""
    txt = open(path).read()
    pre = dict(re.findall(r"Prefix\((\w*):=<([^>]+)>\)", txt))
    full = lambda t: pre[t.split(":")[0]] + t.split(":", 1)[1] if not t.startswith("<") else t[1:-1]  # noqa: E731
    name = r"(<[^>]+>|\w*:[\w-]+)"
    sub = {(full(a), full(b)) for a, b in re.findall(rf"^SubClassOf\({name} {name}\)", txt, re.M)}
    eq = set()
    for body in re.findall(r'^EquivalentClasses\((?:Annotation\(rdfs:comment "[^"]*"\) )?(.+)\)$', txt, re.M):
        toks = re.findall(name, body)
        if len(toks) == 2 and "(" not in body.replace(toks[0], "").replace(toks[1], ""):
            eq.add(frozenset(full(t) for t in toks))
    return sub, eq


def owx_classification(path):
    """Direct subsumptions and equivalences between named classes from Konclude's OWL/XML classification."""
    txt = open(path).read()
    sub, eq, unsat = set(), set(), []
    for a, b in re.findall(r'<SubClassOf>\s*<Class IRI="([^"]+)"/>\s*<Class IRI="([^"]+)"/>\s*</SubClassOf>', txt):
        sub.add((a, b))
    for body in re.findall(r"<EquivalentClasses>(.*?)</EquivalentClasses>", txt, re.S):
        names = re.findall(r'<Class IRI="([^"]+)"/>', body)
        if "http://www.w3.org/2002/07/owl#Nothing" in names:
            unsat += [n for n in names if not n.endswith("#Nothing")]
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                eq.add(frozenset((names[i], names[j])))
    return sub, eq, unsat


def main():
    t0 = time.time()
    merged, reasoned = os.path.join(BUILD, "experiment_merged.owx"), os.path.join(BUILD, "experiment_merged_reasoned.ofn")
    inputs = [os.path.join(BUILD, "upstream-aicor-ontology.ttl"), os.path.join(BUILD, "lab-automation-twin.ofn"), XO_OFN, BRIDGE]
    robot("merge", "--catalog", os.path.join(BUILD, "catalog-v001.xml"), *sum((["--input", i] for i in inputs), []),
          "--output", merged)
    reasoned = os.path.join(BUILD, "experiment_merged_classification.owx")
    k1 = subprocess.run([KONCLUDE, "consistency", "-w", "AUTO", "-i", merged], capture_output=True, text=True)
    log = k1.stdout + k1.stderr
    consistent = "is consistent" in log and "inconsistent" not in log
    if not consistent:
        sys.exit(f"[merge] Konclude: INCONSISTENT\n{log[-1500:]}")
    k2 = subprocess.run([KONCLUDE, "classification", "-w", "AUTO", "-i", merged, "-o", reasoned], capture_output=True, text=True)
    sub, eq, unsat = owx_classification(reasoned)
    asub, aeq = set(), set()
    for f in inputs[1:]:
        s, e = iri_axioms(f)
        asub |= s
        aeq |= e
    cross = lambda a, b: (a.startswith(LAB) and b.startswith(XP)) or (a.startswith(XP) and b.startswith(LAB))  # noqa: E731
    short = lambda i: ("lab:" + i[len(LAB):]) if i.startswith(LAB) else ("xp:" + i[len(XP):])  # noqa: E731
    inf_eq = sorted(sorted(short(x) for x in p) for p in eq if len(p) == 2 and cross(*p) and p not in aeq)
    inf_sub = sorted((short(a), short(b)) for a, b in sub if cross(a, b) and (a, b) not in asub
                     and frozenset((a, b)) not in aeq and frozenset((a, b)) not in eq)
    rep = dict(consistent=consistent, reasoner="Konclude (SROIQV(D))", unsatisfiable=unsat,
               inferred_equivalences=inf_eq, inferred_subsumptions=inf_sub, seconds=round(time.time() - t0, 1),
               inputs=[os.path.relpath(i, ROOT) for i in inputs])
    os.makedirs(OUT, exist_ok=True)
    json.dump(rep, open(os.path.join(OUT, "experiment-merge-report.json"), "w"), indent=1)
    md = ["# Experiment models merged: lab module + experiment ontology", "",
          f"{rep['reasoner']} over {', '.join(rep['inputs'])}: **{'consistent' if rep['consistent'] else 'INCONSISTENT'}**, "
          f"{len(unsat)} unsatisfiable, {rep['seconds']} s.", "", "## Inferred equivalences (not asserted)", ""]
    md += [f"- {a} ≡ {b}" for a, b in inf_eq] or ["- none"]
    sys.path.insert(0, os.path.join(MOD, "bridge"))
    import build_experiment_bridge as BB
    md += ["", "## Divergences (not bridged)", ""] + [f"- {d}" for d in BB.DIVERGENCES]
    md += ["", "## Inferred subsumptions across the two (not asserted)", ""]
    md += [f"- {a} ⊑ {b}" for a, b in inf_sub] or ["- none"]
    open(os.path.join(OUT, "experiment-merge-report.md"), "w").write("\n".join(md) + "\n")
    print(f"[merge] {'consistent' if rep['consistent'] else 'INCONSISTENT'}, {len(unsat)} unsatisfiable; inferred "
          f"{len(inf_eq)} equivalences, {len(inf_sub)} subsumptions across the namespaces ({rep['seconds']} s)")
    for a, b in inf_eq:
        print(f"   {a} ≡ {b}")
    for a, b in inf_sub:
        print(f"   {a} ⊑ {b}")
    return 0 if rep["consistent"] and not unsat else 1


if __name__ == "__main__":
    sys.exit(main())
