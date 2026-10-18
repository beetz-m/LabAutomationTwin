"""Which experiments a laboratory affords: capability profiles, design requirements and their matching.

Cell 01's profile is read from its component records (capability verbs -> device functions), the device registry
(reagent stocks, validated readout bindings) and the twin's measured durations (wells that can be dosed within the
plate's excursion window). A second laboratory, a site core facility with a luminescence/absorbance plate reader, is
ILLUSTRATIVE (not modelled from records): it shows how steps a module cannot perform are allocated elsewhere.

  1. HermiT classifies the laboratories (capability classes, from the functions their devices bear) and the designs
     (requirement classes, from their content) in one ontology (rsa/experiment_ontology.py).
  2. Closed-world matching per design: every requirement met by a capability of some laboratory (the home module
     first); every reagent the design administers stocked where it is dosed; a validated readout binding for each
     readout; enough environments for an environment factor; wells per dosing session within the excursion window;
     units within the plate's interior wells; endpoint readouts after every imaging; transfers between laboratories
     possible (both connected).
  3. Verdict: executable in the home module, executable on site with transfers, or not executable as modelled (with
     what is missing).

Four designs: the current challenge-rescue design, the improved design, the improved design with an ATP luminescence
endpoint, and a challenge x oxygen design with an environment factor. All ILLUSTRATIVE (D016).

    env_cad/bin/python -m rsa.lab_affordance      # rsa/out/experiment_ontology/lab_affordance.{json,txt,pdf}
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys

import yaml

from . import experiment_ontology as XO
from .experiment_ontology import ABox, Max
from .kb import C01_COMPONENTS, COMPONENT_FILES

HERE = os.path.dirname(os.path.abspath(__file__))
DST = XO.DST
DEVICES = os.path.join(HERE, "registry", "devices.yaml")

VERB_FUNCTION = {  # capability verb of a component record -> the device function it is evidence of
    "dose_well": "DosingFunction", "incubate_plate": "IncubationFunction", "image_well": "BrightfieldImagingFunction",
    "run_reference_measurement": "CalibrationFunction", "isolate_sample": "QuarantineFunction",
    "transport_clean_sample": "TransportFunction", "pick_sbs_plate": "PlateHandlingFunction", "store_plate": "StorageFunction",
    "read_absorbance": "AbsorbanceReadingFunction", "read_luminescence": "LuminescenceReadingFunction",
    "receive_carrier": "TransportFunction"}
QUALITY = {"organoid_radius_um": "OrganoidSize", "atp_luminescence": "MetabolicActivity"}
INTERIOR_WELLS = 60          # rows B-G x columns 2-11 of a 96-well plate


# ================================================================================================= laboratories
def cell01_profile():
    reg = yaml.safe_load(open(DEVICES))
    plan = json.load(open(XO.PLAN))
    dev = {}
    for a, f in COMPONENT_FILES.items():
        rec = yaml.safe_load(open(os.path.join(C01_COMPONENTS, f + ".yaml")))
        dev[a] = dict(name=rec["identity"]["canonical_name"], capabilities=rec.get("capabilities") or [])
    env = {}
    rec = yaml.safe_load(open(os.path.join(C01_COMPONENTS, COMPONENT_FILES["l10"] + ".yaml")))
    st = rec.get("operational_state") or {}
    env["standard"] = {k: st.get(k) for k in ("temperature_C", "CO2_percent", "humidity_percent")}
    bindings = [dict(device=d, readout=r, level=v["level"]) for d, rs in reg["measurement_bindings"].items() for r, v in rs.items()]
    du = plan["durations_s"]
    overhead = 2 * du["r01_leg"] + 2 * du["r02_leg"] + du["l10_retrieve"] + du["l10_store"] + du["tool_couple"]
    window = float(plan["window_s"])
    return dict(name="cell01", label="Cell 01 (automated treatment-and-imaging module)", devices=dev, environments=env,
                stocks=sorted(reg["reagents"]), bindings=bindings, source="component records, devices.yaml, twin durations",
                window_s=window, overhead_s=round(overhead, 1), dose_s=du["dose_well"],
                wells_per_session=int((window - overhead) // du["dose_well"]))


def core_profile():
    """ILLUSTRATIVE: a site core facility with a multimode plate reader and a dock for the clean-sample AMR."""
    return dict(name="core_reader", label="Core facility: multimode plate reader (ILLUSTRATIVE)",
                devices={"reader": dict(name="Multimode plate reader", capabilities=["read_luminescence", "read_absorbance",
                                                                                     "pick_sbs_plate"]),
                         "dock": dict(name="AMR reception dock", capabilities=["receive_carrier"])},
                environments={}, stocks=["atp_assay_reagent"],
                bindings=[dict(device="reader", readout="atp_luminescence", level="validated")],
                source="ILLUSTRATIVE (not from records)")


def lab_abox(lab):
    B = ABox(lab["name"], lab["label"])
    L = f"lab_{lab['name']}"
    B.t(L, "Laboratory")
    for d, rec in lab["devices"].items():
        dn = f"dev_{lab['name']}_{d}"
        B.t(dn, "Device")
        B.r("hasDevice", L, dn)
        for fn in sorted({VERB_FUNCTION[v] for v in rec["capabilities"] if v in VERB_FUNCTION}):
            f = f"fn_{lab['name']}_{d}_{fn}"
            B.t(f, fn)
            B.r("bearerOf", dn, f)
    for e in lab["environments"]:
        B.t(f"env_{lab['name']}_{e}", "EnvironmentProfile")
        B.r("providesEnvironment", L, f"env_{lab['name']}_{e}")
    B.t(L, Max(len(lab["environments"]), "providesEnvironment"))          # closure: the environments it provides
    if len(lab["environments"]) > 1:
        B.different(*[f"env_{lab['name']}_{e}" for e in lab["environments"]])
    for s in lab["stocks"]:
        B.r("stocks", L, f"agent_{s}")
    for b in lab["bindings"]:
        n = f"binding_{lab['name']}_{b['readout']}"
        B.t(n, "ValidatedReadoutBinding" if b["level"] == "validated" else "ReadoutBinding")
        q = f"quality_{lab['name']}_{b['readout']}"
        B.t(q, QUALITY[b["readout"]])
        B.r("isAbout", n, q)
        B.r("hasReadoutBinding", L, n)
    return B


# ================================================================================================= designs
def designs():
    plan = json.load(open(XO.PLAN))
    eig3 = plan["candidate_eig_bits"].get("c_d85_t48_n3")
    _, cur = XO.current_design()
    imp = XO.improved_spec(eig3)
    lum = dict(XO.improved_spec(eig3), readouts=[("imaging", 72), ("luminescence", 72)])
    env = dict(factors={"challenge": {"none": [], "c085": [("challenge", 0.85, 0)]},
                        "oxygen": {"normoxia": [], "hypoxia": []}},
               factor_kinds={"oxygen": "EnvironmentFactor"},
               arms={"normoxia_control": dict(units=3, levels=dict(challenge="none", oxygen="normoxia")),
                     "hypoxia_control": dict(units=3, levels=dict(challenge="none", oxygen="hypoxia")),
                     "normoxia_challenge": dict(units=3, levels=dict(challenge="c085", oxygen="normoxia")),
                     "hypoxia_challenge": dict(units=3, levels=dict(challenge="c085", oxygen="hypoxia"))},
               comparisons={"challenge": ("normoxia_challenge", "normoxia_control"),
                            "hypoxia": ("hypoxia_control", "normoxia_control"),
                            "challenge_in_hypoxia": ("hypoxia_challenge", "hypoxia_control")},
               licenses=[], rules={"challenge": ("threshold", 2.0), "hypoxia": ("estimate",), "challenge_in_hypoxia": ("estimate",)},
               interaction=[("challenge_in_hypoxia", "challenge")], eig=None, readout=dict(at_h=72), deviation_rule=True,
               placement=None)
    return {"current": ("the current challenge-rescue design", cur),
            "improved": ("the improved design (vehicle, rescue-only, early rescue, 3 replicates)", imp),
            "improved_atp": ("the improved design with an ATP luminescence endpoint at 72 h", lum),
            "oxygen": ("a challenge x oxygen design (environment factor)", env)}


def agents_used(spec):
    return sorted({ag for a in spec["arms"] for ag, *_ in XO.schedule(spec, a)})


def doses_by_time(spec):
    out = {}
    for a, v in spec["arms"].items():
        for ag, d, t in XO.schedule(spec, a):
            out[t] = out.get(t, 0) + v["units"]
    return dict(sorted(out.items()))


# ================================================================================================= matching
def all_types(ind, k):
    return {c.name for c in ind.INDIRECT_is_a if hasattr(c, "name") and getattr(c, "namespace", None) is not None
            and c.namespace.base_iri == XO.XP}


def match(name, spec, req, labs, lab_types, home="cell01"):
    """Closed-world matching of one design's requirements and resources against the laboratories' profiles."""
    rows, alloc, missing, notes = [], {}, [], []
    for r in sorted(req):
        cap = XO.REQUIREMENT_MET_BY.get(r)
        if not cap:
            continue
        cands = [l for l in labs if cap in lab_types[l]]
        where = home if home in cands else (cands[0] if cands else None)
        alloc[r] = where
        rows.append(dict(requirement=r, capability=cap, labs=cands, allocated=where))
        if where is None:
            missing.append(f"{r}: no laboratory is a {cap}")
    # reagents where the dosing happens
    dl = alloc.get("RequiresDosing")
    if dl:
        lack = [a for a in agents_used(spec) if a not in labs[dl]["stocks"]]
        rows.append(dict(requirement="reagents stocked", capability=", ".join(agents_used(spec)), labs=[dl],
                         allocated=dl if not lack else None))
        if lack:
            missing.append(f"reagent not stocked in {dl}: {', '.join(lack)}")
    # validated readout bindings
    for kind, at_h in spec.get("readouts") or [("imaging", spec["readout"]["at_h"])]:
        r = {"imaging": "RequiresImaging", "luminescence": "RequiresLuminescence", "absorbance": "RequiresAbsorbance"}[kind]
        lab = alloc.get(r)
        q = "OrganoidSize" if kind == "imaging" else "MetabolicActivity"
        ok = bool(lab) and any(b["level"] == "validated" and QUALITY[b["readout"]] == q for b in labs[lab]["bindings"])
        rows.append(dict(requirement=f"validated binding: {kind} readout", capability=q, labs=[lab] if lab else [],
                         allocated=lab if ok else None))
        if lab and not ok:
            missing.append(f"no validated {q} readout in {lab}")
    # environments
    for f, kind in spec.get("factor_kinds", {}).items():
        if kind == "EnvironmentFactor":
            need = len(spec["factors"][f])
            have = {l: len(p["environments"]) for l, p in labs.items()}
            notes.append(f"environment factor '{f}' needs {need} controlled environments; provided: "
                         + ", ".join(f"{l} {n}" for l, n in have.items()))
    # dosing sessions within the excursion window (home module timings)
    if dl == home:
        per = labs[home]["wells_per_session"]
        sess = {t: math.ceil(n / per) for t, n in doses_by_time(spec).items()}
        split = {t: s for t, s in sess.items() if s > 1}
        notes.append(f"doses per time point {doses_by_time(spec)}; at most {per} wells per session "
                     f"({labs[home]['window_s']:.0f} s window, {labs[home]['overhead_s']:.0f} s transfer overhead, "
                     f"{labs[home]['dose_s']:.1f} s per well)" + (f"; split into several sessions at {', '.join(f'{t:g} h ({s})' for t, s in split.items())}"
                                                                      if split else "; one session per time point")
                     + (f"; the last session of a time point starts about {(max(split.values()) - 1) * labs[home]['window_s'] / 60:.0f} min "
                        f"after the first" if split else ""))
    units = sum(a["units"] for a in spec["arms"].values())
    rows.append(dict(requirement="units within the plate's interior wells", capability=f"{units} of {INTERIOR_WELLS}",
                     labs=[home], allocated=home if units <= INTERIOR_WELLS else None))
    if units > INTERIOR_WELLS:
        missing.append(f"{units} units exceed {INTERIOR_WELLS} interior wells of one plate")
    # endpoint readouts after every imaging; transfers
    ro = spec.get("readouts") or [("imaging", spec["readout"]["at_h"])]
    t_img = max([t for k, t in ro if k == "imaging"] or [0])
    for k, t in ro:
        if k != "imaging" and t < t_img:
            missing.append(f"{k} endpoint at {t} h precedes imaging at {t_img} h (destructive)")
    away = sorted({l for l in alloc.values() if l and l != home})
    for l in away:
        ok = "ConnectedLab" in lab_types[home] and "ConnectedLab" in lab_types[l]
        notes.append(f"transfer {home} -> {l}: {'possible (clean-sample transport at both ends)' if ok else 'NOT possible'}; "
                     f"the plate leaves the controlled environment for an unmodelled time")
        if not ok:
            missing.append(f"no transfer to {l}")
    verdict = ("not executable as modelled" if missing else
               "executable on site with transfers" if away else f"executable in {home}")
    return dict(design=name, requirements=sorted(req), checks=rows, allocation=alloc, missing=missing, notes=notes,
                verdict=verdict, units=units)


def main(argv):
    os.makedirs(DST, exist_ok=True)
    labs = {"cell01": cell01_profile(), "core_reader": core_profile()}
    D = designs()
    boxes = [lab_abox(l) for l in labs.values()]
    dboxes = {n: XO.design_abox(f"aff_{n}", spec, label) for n, (label, spec) in D.items()}
    w, onto, k, inds = XO.build(boxes + list(dboxes.values()))
    ok, secs, unsat = XO.reason(w, onto)
    print(f"[afford] HermiT {'consistent' if ok else 'INCONSISTENT'} in {secs} s, unsatisfiable {unsat}")
    if not ok:
        return 1
    caps = set(XO.REQUIREMENT_MET_BY.values()) | {"QualityControlledLab", "ContainmentCapableLab", "ConnectedLab",
                                                    "ValidatedSizeReadoutLab", "ValidatedMetabolicReadoutLab",
                                                    "TreatmentAndImagingModule"}
    lab_types = {n: all_types(inds[f"lab_{n}"], k) for n in labs}
    for n, p in labs.items():
        fs = sorted({VERB_FUNCTION[v] for d in p["devices"].values() for v in d["capabilities"] if v in VERB_FUNCTION})
        print(f"[lab] {n:12} functions {fs}")
        print(f"      capability classes (HermiT): {sorted(lab_types[n] & caps)}")
        print(f"      not: {sorted(caps - lab_types[n])}")
    res = {}
    for n, (label, spec) in D.items():
        req = {t for t in all_types(inds[f"aff_{n}_design"], k) if t.startswith("Requires")}
        m = match(n, spec, req, labs, lab_types)
        m["label"] = label
        m["design_classes"] = XO.most_specific(inds[f"aff_{n}_design"], k)
        lack = [x.split(": ")[1] for x in m["missing"] if x.startswith("reagent not stocked")]
        if lack and len(lack) == len(m["missing"]):          # what if the missing reagents were stocked
            import copy
            labs2 = copy.deepcopy(labs)
            for x in lack:
                labs2["cell01"]["stocks"] += [a.strip() for a in x.split(",")]
            m["if_stocked"] = dict(reagents=lack, verdict=match(n, spec, req, labs2, lab_types)["verdict"])
        res[n] = m
        print(f"[design] {n:13} requires {sorted(req)}")
        print(f"         -> {m['verdict'].upper()}" + (f"; missing: {m['missing']}" if m["missing"] else "")
              + (f"; with {m['if_stocked']['reagents']} stocked: {m['if_stocked']['verdict']}" if m.get("if_stocked") else ""))
        for r in m["checks"]:
            print(f"           {'ok ' if r['allocated'] else 'NO '} {r['requirement']:42} {r['capability']:36} {r['labs']}")
        for x in m["notes"]:
            print(f"           note: {x}")
    out = dict(labs={n: dict(p, capability_classes=sorted(lab_types[n] & caps)) for n, p in labs.items()},
               designs=res, reasoner=dict(consistent=ok, seconds=secs))
    json.dump(out, open(os.path.join(DST, "lab_affordance.json"), "w"), indent=1, default=str)
    write_pdf(out)
    return 0


# ================================================================================================= document
def tex(s):
    return (str(s).replace("_", r"\_").replace("&", r"\&").replace("%", r"\%").replace("#", r"\#").replace("≥", r"$\geq$")
            .replace("×", r"$\times$").replace("->", r"$\rightarrow$"))


def write_pdf(out):
    L = [r"""\documentclass[10pt,a4paper]{article}
\usepackage[margin=2.1cm]{geometry}
\usepackage{fontspec,unicode-math}
\setmainfont{Libertinus Serif}\setsansfont{IBM Plex Sans}[Scale=0.9]\setmonofont{IBM Plex Mono}[Scale=0.82]
\setmathfont{Libertinus Math}
\usepackage{booktabs,tabularx,array,xcolor,enumitem,hyperref}
\renewcommand{\tabularxcolumn}[1]{>{\raggedright\arraybackslash}p{#1}}
\newcommand{\ax}[1]{\par{\raggedright\noindent\hangindent=2.5em\hangafter=1 $#1$\par}\smallskip}
\setlength{\parindent}{0pt}\setlength{\parskip}{3pt}\setlength{\emergencystretch}{3em}\raggedright
\title{What our laboratory affords\\[2pt]\large capability profiles, design requirements and their matching}
\author{Generated by \texttt{rsa/lab\_affordance.py}; ILLUSTRATIVE (D016)}\date{}
\begin{document}\maketitle
\section*{Approach}
A laboratory has devices; a device bears \emph{functions}, dispositions realized only in processes of one kind. A
laboratory's capability classes are defined by those functions, by the environments it provides and by its validated
readout bindings, so HermiT classifies laboratories from their devices. A design's requirement classes are defined by
its content (administrations, readouts, environment factors), so HermiT classifies designs by their needs. Matching a
design's requirements, reagents, readout bindings and timing against the laboratories of a site is a closed-world
question over the individuals. Cell~01's profile is read from its ten component records, the device registry and the
twin's durations; the core plate-reader facility is ILLUSTRATIVE.
\section*{Axioms}"""]
    S = {s["title"]: s for s in XO.tbox()}
    for t in ("Laboratories, devices and capabilities", "Design requirements"):
        L.append(rf"\subsection*{{{t}}}")
        L += [rf"\ax{{{XO.brk(a.dl('tex'))}}}" for a in S[t]["axioms"]]
    L.append(r"\section*{Laboratories}")
    for n, p in out["labs"].items():
        L.append(rf"\subsection*{{{tex(p['label'])}}}")
        rows = [rf"{tex(d['name'])} & {tex(', '.join(d['capabilities']))} & "
                rf"{tex(', '.join(sorted({VERB_FUNCTION[v] for v in d['capabilities'] if v in VERB_FUNCTION})) or '---')} \\"
                for d in p["devices"].values()]
        L.append(r"\par\noindent{\footnotesize\begin{tabularx}{\linewidth}{@{}p{4.4cm}XX@{}}\toprule device & capability verbs (component record) & "
                 r"functions \\ \midrule" + "\n" + "\n".join(rows) + "\n" + r"\bottomrule\end{tabularx}}")
        L.append(rf"\par Environments: {tex(', '.join(f'{e} {v}' for e, v in p['environments'].items()) or 'none')}. "
                 rf"Reagent stocks: {tex(', '.join(p['stocks']))}. Validated readouts: "
                 rf"{tex(', '.join(b['readout'] for b in p['bindings'] if b['level'] == 'validated'))}. "
                 + (rf"Dosing within the {p['window_s']:.0f}~s excursion window: at most {p['wells_per_session']} wells per session. "
                    if "wells_per_session" in p else "")
                 + rf"\textbf{{Capability classes (HermiT):}} {', '.join(rf'$\mathsf{{{c}}}$' for c in p['capability_classes'])}.")
    L.append(r"\section*{Designs}")
    for n, m in out["designs"].items():
        col = "green!45!black" if m["verdict"].startswith("executable in") else "orange!80!black" if "transfers" in m["verdict"] else "red!65!black"
        L.append(rf"\subsection*{{{tex(m['label'][0].upper() + m['label'][1:])}}}")
        L.append(rf"Design classes: {', '.join(rf'$\mathsf{{{c}}}$' for c in m['design_classes'] if not c.startswith('Requires'))}. "
                 rf"Requirements (HermiT): {', '.join(rf'$\mathsf{{{c}}}$' for c in m['requirements'])}. "
                 rf"\textbf{{Verdict: \textcolor{{{col}}}{{{tex(m['verdict'])}}}}}.")
        rows = [rf"{tex(r['requirement'])} & {tex(r['capability'])} & {tex(', '.join(x for x in r['labs'] if x) or '---')} & "
                rf"{tex(r['allocated']) if r['allocated'] else r'\textcolor{red!65!black}{unmet}'} \\" for r in m["checks"]]
        L.append(r"\par\noindent{\footnotesize\begin{tabularx}{\linewidth}{@{}p{4.6cm}Xp{2.6cm}p{2.0cm}@{}}\toprule requirement & needs & "
                 r"offered by & allocated \\ \midrule" + "\n" + "\n".join(rows) + "\n" + r"\bottomrule\end{tabularx}}")
        if m["missing"]:
            L.append(r"Missing:\begin{itemize}[nosep]" + "".join(rf"\item {tex(x)}" for x in m["missing"]) + r"\end{itemize}")
        if m.get("if_stocked"):
            L.append(rf"With {tex(', '.join(m['if_stocked']['reagents']))} stocked in Cell~01 the verdict would be: "
                     rf"\textbf{{{tex(m['if_stocked']['verdict'])}}}.")
        if m["notes"]:
            L.append(r"Notes:\begin{itemize}[nosep]" + "".join(rf"\item {tex(x)}" for x in m["notes"]) + r"\end{itemize}")
    L.append(r"\end{document}")
    p = os.path.join(DST, "lab_affordance.tex")
    open(p, "w").write("\n".join(L))
    r = subprocess.run(["latexmk", "-lualatex", "-interaction=nonstopmode", "-halt-on-error", "lab_affordance.tex"], cwd=DST,
                       capture_output=True, text=True)
    log = open(os.path.join(DST, "lab_affordance.log"), errors="replace").read()
    pages = re.search(r"Output written on .*?\((\d+) pages?", log)
    print(f"[afford] latex exit {r.returncode}, {pages.group(1) if pages else '?'} pages, "
          f"{len(re.findall('Overfull', log))} overfull -> rsa/out/experiment_ontology/lab_affordance.pdf")
    if r.returncode:
        print(r.stdout[-2000:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
