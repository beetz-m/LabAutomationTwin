"""Render rsa/out/refinement_proof.json as docs/rsa/plan/proof.html (the styles are the culture page's).

    python3 -m rsa.proof_page
"""

from __future__ import annotations

import collections
import html
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "out")
PAGE = os.path.join(ROOT, "docs", "rsa", "plan", "proof.html")
e = html.escape

LEVELS = [  # (level, what it is, size, artefact)
    ("Culture plan", "what is done to the cultures and what becomes known", "12 actions, 3 cultures", "registry/lab/culture_plan.ldl"),
    ("Lab plan", "action designators over entity designators: requires, prevents, maintains, achieves, handles", "8 steps, 13 handlers", "registry/lab/challenge_rescue.ldl"),
    ("Step plan", "the kernel's expansion into grounded robot and device steps, plan_g050", "3 sessions, 151 steps", "out/plan_g050.json"),
    ("Motion plan", "giskardpy motion statecharts: goal frames, constraints, monitors, cancels", "111 motions, 25 goal frames", "rsa/out/challenge_rescue_giskard.py"),
]
OB_BETWEEN = {0: ["O1", "O2"], 1: ["O3"], 2: ["O4", "O5"], 3: ["O6", "O7"]}
OB_TEXT = {
    "O1": ("Culture plan well formed", "Every requirement is supported by an earlier effect or is establishable; the order is acyclic.", "rsa/culture_plan.py"),
    "O2": ("Abstraction", "The step level's proven doses, images and session times, mapped through the vessel map, entail every culture effect, the culture order and the culture-level prevents. z3 shows each negation UNSAT.", "z3 in rsa/refinement_proof.py"),
    "O3": ("Lab plan sound", "Causal links, threats resolved, instruments fill their roles, every handler's guarantee verified, culture order preserved in the lab order.", "rsa/ldl.py, rsa/ldl_trust.py"),
    "O4": ("Step plan valid", "Executability and preservation, safety S1 S2 S3 S6 S7, the 600 s window with durations within 20 %, realization of every dose and image, least cost.", "validate_plan_z3.py, re-run"),
    "O5": ("Cleanliness", "No tool coupled for plate handling is one that touches the culture; contamination freedom is a required constraint.", "z3 in rsa/refinement_proof.py"),
    "O6": ("Motion refinement", "Each of the 111 motions refines its step; its end monitor implies the step's postcondition under A3; tilt, collision and duration are hold-or-cancel.", "rsa/refinement_proof.py over giskard_motions.json"),
    "O7": ("Failure branch", "Every cancellation and every monitor-detected violation reaches a handler whose guarantee was verified in O3.", "rsa/refinement_proof.py"),
}
ASSUME = {  # how each assumption is covered
    "A1": ("library", "giskardpy's statechart semantics; the API used was verified against the source tree"),
    "A2": ("assumed", "sensor and monitor soundness; two device faults are only partly detected (below)"),
    "A3": ("illustrative", "nest capture of 2 mm is ILLUSTRATIVE; it needs the real nest drawings or a contact simulation"),
    "A4": ("monitored", "grasp_confirmed, lifted and seating are monitored at run time"),
    "A5": ("contract", "device contracts from the Cell 01 component records, watched by the process models' monitors"),
    "A6": ("checked", "25 of 25 goal frames reachable: R01 by its planner's IK, R02 by URDF-chain IK with the rail free"),
}
PILL = {"checked": "ok", "monitored": "ok", "contract": "know", "library": "know", "assumed": "cond", "illustrative": "cond"}


def ob_key(name):
    return name.split()[0]


def build():
    d = json.load(open(os.path.join(OUT, "refinement_proof.json")))
    ldl = json.load(open(os.path.join(OUT, "ldl_challenge_rescue.json")))
    O = {ob_key(k): (k, v) for k, v in d["obligations"].items()}
    ok = d["holds"]

    # ---- the chain
    chain = []
    for i, (lv, what, size, art) in enumerate(LEVELS):
        chain.append(f'<div class="lvl"><div><b>{e(lv)}</b><span>{e(what)}</span></div><div class="meta"><span class="num">{e(size)}</span><code>{e(art)}</code></div></div>')
        obs = "".join(f'<a class="ob" href="#{k}"><span class="pill {"ok" if O[k][1]["holds"] else "bad"}">{k}</span> {e(OB_TEXT[k][0])}</a>' for k in OB_BETWEEN[i])
        if i < len(LEVELS) - 1:
            chain.append(f'<div class="link"><span class="arrow">refined by</span>{obs}</div>')
        else:
            chain.append(f'<div class="link last">{obs}</div>')

    # ---- obligations
    cards = []
    for k in sorted(O):
        name, o = O[k]
        title, text, tool = OB_TEXT[k]
        body = ""
        if k == "O1":
            body = f'<p class="small">{o["links"]} causal links; establishable: <code>{e(o["establish"][0])}</code> (three interpretations).</p>'
        elif k == "O2":
            ev = o["events"]
            evs = "".join(f'<span>{e(x[0])} {e(x[1])}{" " + e(x[2]) + " " + str(x[3]/100) + " au" if x[2] else ""} @ {x[4]} h</span>' for x in ev)
            vm = " ".join(f'<code>{e(c)}</code>→<code>{e(w)}</code>' for c, w in o["vessel"].items())
            rows = "".join(f'<tr><td><span class="pill {"ok" if v else "bad"}">{"unsat" if v else "sat"}</span></td><td>{e(n)}</td></tr>' for n, v in o["obligations"].items())
            body = (f'<div class="small">Vessel map {vm}. Proven step-level events (V4):</div><div class="seq">{evs}</div>'
                    f'<div class="scroll"><table class="t"><thead><tr><th>¬ obligation</th><th>Culture-level obligation</th></tr></thead><tbody>{rows}</tbody></table></div>')
        elif k == "O3":
            body = f'<p class="small">Threats resolved {o["threats"]}; handler guarantees {o["guarantees"]}; negative controls {o["negative_controls"]}; culture order preserved: {o["order_preserved_culture_to_lab"]}.</p>'
        elif k == "O4":
            rows = "".join(f'<tr><td><span class="pill {"ok" if v else "bad"}">{"holds" if v else "fails"}</span></td><td>{e(n)}</td></tr>' for n, v in o["theorems"].items())
            body = f'<div class="scroll"><table class="t"><tbody>{rows}</tbody></table></div><p class="small">The validator\'s own negative controls: {o["negative_controls"]} mutated plans rejected.</p>'
        elif k == "O5":
            body = f'<p class="small">Tools coupled: <code>{", ".join(o["tools_used"])}</code>. Tools that touch the culture: <code>{", ".join(o["contacts_culture"])}</code> (only the liquid handler and the imager use them, inside the devices).</p>'
        elif k == "O6":
            g = collections.OrderedDict()
            for m in o["motions"]:
                g.setdefault(m["type"], []).append(m)
            rows = ""
            for t, ms in g.items():
                m = ms[0]
                canc = sorted({re.sub(r"[\d.]+ s", "1.2 × estimate", c) for x in ms for c in x["cancel"]})
                rows += (f'<tr><td><code>{e(t)}</code></td><td class="num">{len(ms)}</td><td><code>{e(m["step"])}</code><div class="small">{e(m["postcondition"])}</div></td>'
                         f'<td>{e(m["end_monitor"])}<div class="small">{e(m["why"])}</div></td><td>{"<br>".join(e(c) for c in canc)}</td>'
                         f'<td><span class="pill {"ok" if all(x["ok"] for x in ms) else "bad"}">{sum(x["ok"] for x in ms)}/{len(ms)}</span></td></tr>')
            per = "".join(f'<li>{e(m["session"])} {e(m["robot"])} {e(m["leg"])} <b>{e(m["type"])}</b> → {e(m["step"])}; timeout {m["timeout_s"]} s; cancel: {e("; ".join(m["cancel"]))}</li>' for m in o["motions"])
            code = " · ".join(f'{e(c)} <span class="pill {"ok" if v else "bad"}">{"present" if v else "missing"}</span>' for c, v in o["code"].items())
            body = (f'<div class="scroll"><table class="t"><thead><tr><th>Motion</th><th>n</th><th>Refines step · postcondition</th><th>End monitor · why it implies the postcondition</th><th>Hold or cancel</th><th>Checks</th></tr></thead><tbody>{rows}</tbody></table></div>'
                    f'<p class="small">Generated module: {code}. Goal frames reachable {o["goals_reachable"]}.</p>'
                    f'<details class="ev"><summary>All 111 motions</summary><ul>{per}</ul></details>')
        elif k == "O7":
            rows = "".join(f'<tr><td><code>{e(a)}</code></td><td>{e(b)}</td></tr>' for a, b in o["mapping"].items())
            gs = " ".join(f'<span>{e(n)}</span>' for n in o["guarantees"])
            body = f'<div class="scroll"><table class="t"><tbody>{rows}</tbody></table></div><div class="small">Failure types with a verified guarantee:</div><div class="seq">{gs}</div>'
        cards.append(f'<div class="panel" id="{k}"><div class="pad ob-h"><span class="pill {"ok" if o["holds"] else "bad"}">{k} {"holds" if o["holds"] else "fails"}</span><h3>{e(title)}</h3><span class="small">{e(tool)}</span></div>'
                     f'<div class="pad grid6"><p>{e(text)}</p>{body}</div></div>')

    # ---- assumptions
    arows = ""
    for a in d["assumptions"]:
        key, rest = a.split(" ", 1)
        kind, how = ASSUME[key]
        arows += f'<tr><td><b>{e(key)}</b></td><td>{e(rest)}</td><td><span class="pill {PILL[kind]}">{e(kind)}</span><div class="small">{e(how)}</div></td></tr>'
    part = sorted({(t["component"], f["fault"], f["monitor"]) for t in ldl["trust"] for f in t["faults"] if f["detected"] != "full"})
    nf = sum(len(t["faults"]) for t in ldl["trust"])
    npart = sum(1 for t in ldl["trust"] for f in t["faults"] if f["detected"] != "full")
    prow = "".join(f'<li><code>{e(c)}</code>: {e(f.replace("_", " "))}, detected by {e(m)}</li>' for c, f, m in part)

    # ---- negative controls
    nrows = "".join(f'<tr><td>{e(n)}</td><td><span class="pill {"ok" if v else "bad"}">{"caught" if v else "missed"}</span></td></tr>' for n, v in d["negative_controls"].items())

    css = open(os.path.join(ROOT, "docs", "rsa", "plan", "culture.html")).read().split("</style>")[0].split("<style>")[1]
    head = open(os.path.join(ROOT, "docs", "rsa", "plan", "culture.html")).read().split("<style>")[0]
    head = re.sub(r"<title>.*?</title>", "<title>Motion Plan Refinement Proof</title>", head)
    extra = """
.chainbox { display: grid; gap: 0 }
.lvl { background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 10px 14px; display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px 18px; min-width: 0 }
.lvl > div { display: grid; gap: 2px; min-width: 0 } .lvl b { font: 600 1.05rem var(--f-display) } .lvl span { font-size: .8rem; color: var(--muted) }
.lvl .meta { text-align: right } .lvl .num { font: 600 .85rem var(--f-mono); color: var(--ink) }
.link { margin-left: 26px; border-left: 2px solid var(--accent); padding: 8px 0 8px 16px; display: flex; flex-wrap: wrap; gap: 6px 14px; align-items: center }
.link.last { border-left-style: dashed }
.link .arrow { font: 600 .66rem var(--f-ui); letter-spacing: .08em; text-transform: uppercase; color: var(--accent) }
a.ob { color: var(--ink); text-decoration: none; font-size: .84rem; display: inline-flex; gap: 6px; align-items: center }
a.ob:hover span + *, a.ob:hover { text-decoration: underline } a.ob:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px }
.ob-h { display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: baseline; border-bottom: 1px solid var(--line) }
.grid6 { display: grid; gap: 8px; min-width: 0 }
td.num { font-variant-numeric: tabular-nums }
.thm { font: 1rem/1.6 var(--f-body); max-width: 80ch } .thm ol { margin: 6px 0 0; padding-left: 22px; display: grid; gap: 4px }
ul.gaps { margin: 0; padding-left: 20px; display: grid; gap: 6px; max-width: 86ch; font-size: .9rem }
"""
    page = f"""{head}<style>{css}{extra}</style>
<div class="wrap">
<header>
  <div class="eyebrow">Challenge-rescue · Cell 01 · refinement proof</div>
  <h1>Motion Plan Refinement Proof</h1>
  <p class="lead">Does the motion-level plan that Giskard executes carry out the culture-level plan, and satisfy every constraint stated on the way? It does, relative to six stated assumptions about the controller, the sensors and the devices. Seven proof obligations link the four levels. Each one is discharged by an SMT proof or a mechanical check that this page reports.</p>
  <div class="verdict{"" if ok else " warn"}"><div class="eyebrow">Result</div>
    <div class="thm">Under A1–A6, every execution of the 111-motion plan either
      <ol><li>realizes the culture plan: every physical and knowledge effect, in the derived order, at 0, 48 and 72 h of culture time, with the control culture untreated, while interlocks, L12 airspace, identity, environment before store, calibration before imaging, the 600 s window, contamination freedom, tool hygiene, plate level and collision distance all hold; <b>or</b></li>
      <li>is stopped by a monitor and ends in a failure handler whose guarantee holds (the goal, a safe state, or containment).</li></ol></div>
    <p class="small">{"Proved: 7 of 7 obligations hold; 8 of 8 negative controls are caught." if ok else "NOT PROVED: see the failing obligation."} Produced by <code>rsa/refinement_proof.py</code>, which writes <code>rsa/out/refinement_proof.json</code>.</p></div>
</header>

<section id="chain">
  <div class="eyebrow">1 · The refinement chain</div>
  <h2>Four levels, seven obligations between them</h2>
  <p class="note">Each level is refined into the one below it. The obligations on each link say what must hold for the refinement to be correct. Select an obligation to see its evidence.</p>
  <div class="chainbox">{"".join(chain)}</div>
</section>

<section id="obligations">
  <div class="eyebrow">2 · Proof obligations</div>
  <h2>What each obligation states and how it is discharged</h2>
  {"".join(cards)}
</section>

<section id="assumptions">
  <div class="eyebrow">3 · Assumptions</div>
  <h2>What the proof takes as given</h2>
  <p class="note">A motion statechart is a soft optimization problem. Its level-keeping and collision terms are weighted slacks, and convergence and contact are not modelled. The proof therefore makes every soft part <em>hold-or-cancel</em>: a monitor ends the motion when the property is violated. Whatever the proof cannot check itself is listed here, together with how it is covered.</p>
  <div class="panel scroll"><table class="t"><thead><tr><th></th><th>Assumption</th><th>Covered by</th></tr></thead><tbody>{arows}</tbody></table></div>
</section>

<section id="negative">
  <div class="eyebrow">4 · Negative controls</div>
  <h2>Each broken variant is rejected</h2>
  <p class="note">Each mutation must make an obligation fail. This shows that the checks are not vacuous.</p>
  <div class="panel scroll"><table class="t"><tbody>{nrows}</tbody></table></div>
</section>

<section id="limits">
  <div class="eyebrow">5 · Limits of the result</div>
  <h2>What is not proved</h2>
  <ul class="gaps">
    <li><b>Progress.</b> A1 says that a motion ends or is cancelled. It does not say that the motion reaches its goal. The proof gives correctness or a guaranteed safe failure, not that the experiment completes.</li>
    <li><b>Partly detected faults.</b> Branch (ii) covers only faults that a monitor detects. {npart} of the {nf} fault instances in the process models are detected only partly:<ul>{prow}</ul>An undetected misregistration or misseating falls outside the theorem. This is the main gap in trustworthiness.</li>
    <li><b>Physics.</b> Compliant insertion into the nests has no Giskard counterpart yet. The 2 mm capture of A3 and the 2° tilt bound are ILLUSTRATIVE.</li>
    <li><b>Execution.</b> The Giskard module was generated and its imports were verified, but it has not run: there is no Cell 01 semantic digital twin World yet. R02 collisions are not checked offline.</li>
    <li><b>Biology.</b> The culture-level goal is an expected information gain under the surrogate models M1–M3. The proof establishes that the plan does what the design says to the cultures. It makes no claim about what the cultures do.</li>
    <li><b>Level of formality.</b> O2, O4 and O5 are SMT proofs. O1, O3, O6 and O7 are exhaustive mechanical checks over finite plans; O6 compares tolerances against A3, it does not prove geometry. The checks of the generated module are syntactic.</li>
  </ul>
</section>
</div>
"""
    open(PAGE, "w").write(page)
    print(f"[proof_page] {PAGE} ({len(page)} bytes)")


if __name__ == "__main__":
    build()
