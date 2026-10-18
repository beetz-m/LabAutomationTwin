"""Realised information gain of an executed plan (closes the loop: required gain -> plan -> twin -> culture -> belief).

The doses the twin's L12 actually delivered (volume inferred from its liquid model, per executed dispense step) enter
Cell 01's hidden culture world (twin/culture/model.py) at the plan's session times; the 72 h organoid radii of the
rescued and comparator wells are read with the twin's fitted measurement noise (observation_model_v1.json); the
posterior over the competing models M1-M3 (twin/culture/eig.py, same calibrated priors as the EIG) gives the realised
gain KL(p(M | D, y) || p(M | D)).

ILLUSTRATIVE (D016): the culture world is Cell 01's surrogate, not biology. One execution yields one draw of y; the
EIG is the expectation of this quantity over the prior predictive, so a single realised value may lie above or below.

Run: env_cad/bin/python .../realised_gain.py out/plan_g050.json ../../../../test_reports/e2m/plan_execution_g050.json
     [--abox]  (writes out/realised_<tag>.json and, with --abox, abox/plan_execution.ofn)
"""

from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(os.path.dirname(MOD))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(MOD, "src"))

from twin.culture import eig as E  # noqa: E402
from twin.culture.model import CultureWorld  # noqa: E402

E2M = "https://aicor.example/okf/lab1/e2m"


def main():
    plan_path, exe_path = sys.argv[1], sys.argv[2]
    plan, exe = json.load(open(plan_path)), json.load(open(exe_path))
    cands = json.load(open(os.path.join(MOD, "build", "e2m", "eig_candidates.json")))
    sel = plan["selected"]
    roles = {k: [w.upper() for w in v] for k, v in plan["wells"].items()}
    wells = sorted({w for v in roles.values() for w in v})
    # executed dispenses (twin): culture time from the plan's sessions, delivered volume from L12's liquid model
    disp = []
    for tr in exe["trips"]:
        for st in tr["executed"]:
            if st["primitive"] == "dispense" and st["ok"] and st.get("dose"):
                vol = st["dose"].get("volume_inferred_uL") or st["volume_uL"]
                disp.append(dict(t_h=tr["t_h"], well=st["well"], reagent=f"abstract_{st['reagent']}_reagent",
                                 commanded_uL=st["volume_uL"], delivered_uL=float(vol)))
    world = CultureWorld(wells=wells, seed=int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 17)
    for d in sorted(disp, key=lambda x: x["t_h"]):
        world.advance(d["t_h"] - world.t_h)
        world.dispense(d["well"], d["reagent"], d["delivered_uL"], t_h=d["t_h"])
    world.advance(72.0 - world.t_h)
    sig = E._sigma_radius()
    rng = np.random.default_rng(2026)
    obs = {w: dict(radius_true_um=round(world.appearance(w)["radius_um"], 3),
                   viability=round(world.appearance(w)["viability"], 4)) for w in wells}
    for w in wells:
        obs[w]["radius_obs_um"] = round(obs[w]["radius_true_um"] + float(rng.normal(0, sig)), 3)
    y_r = np.array([obs[w]["radius_obs_um"] for w in roles["rescued"]])
    y_c = np.array([obs[w]["radius_obs_um"] for w in roles["comparator"]])
    prng = np.random.default_rng(cands["seed"])
    priors = {m: E.sample_prior(m, prng, n=300) for m in E.MODELS}
    pM = plan.get("prior_over_models") or cands["prior_over_models"]
    post = E.posterior_over_models(priors, pM, sel["dose_au"], sel["delay_h"], y_r, y_c, S=4000, seed=11)
    kl = sum(p * math.log2(p / pM[m]) for m, p in post.items() if p > 0)
    out = dict(plan=plan["tag"], selected=sel, expected_gain_bits=sel["eig_bits"], realised_gain_bits=round(kl, 4),
               requirement_bits=plan["requirement_bits"], prior=pM, posterior={m: round(p, 4) for m, p in post.items()},
               map_model=max(post, key=post.get), dispenses=disp, observations=obs, sigma_radius_um=sig,
               effect_observed_um=round(float(y_r.mean() - y_c.mean()), 3),
               predicted_effect_um={m: round(v["effect_um"], 3) for m, v in sel["predicted_effect_um"].items()},
               executed_ok=exe["all_ok"],
               note="ILLUSTRATIVE (D016): Cell 01 surrogate culture world; one realisation of y; the EIG is its "
                    "expectation over the prior predictive.")
    # distribution over other culture realisations (per-well variability seeds, measurement noise) with the SAME
    # executed doses: how often does one execution of this plan realise the required gain?
    sweep = []
    for sd in range(100, 100 + int(os.environ.get("E2M_SWEEP", "40"))):
        w2 = CultureWorld(wells=wells, seed=sd)
        for d in sorted(disp, key=lambda x: x["t_h"]):
            w2.advance(d["t_h"] - w2.t_h)
            w2.dispense(d["well"], d["reagent"], d["delivered_uL"], t_h=d["t_h"])
        w2.advance(72.0 - w2.t_h)
        r2 = np.random.default_rng(sd)
        yr = np.array([w2.appearance(w)["radius_um"] + r2.normal(0, sig) for w in roles["rescued"]])
        yc = np.array([w2.appearance(w)["radius_um"] + r2.normal(0, sig) for w in roles["comparator"]])
        p2 = E.posterior_over_models(priors, pM, sel["dose_au"], sel["delay_h"], yr, yc, S=1500, seed=11)
        sweep.append(dict(seed=sd, realised_bits=round(sum(p * math.log2(p / pM[m]) for m, p in p2.items() if p > 0), 4),
                          map_model=max(p2, key=p2.get), effect_um=round(float(yr.mean() - yc.mean()), 3)))
    rb = np.array([x["realised_bits"] for x in sweep])
    out["sweep"] = dict(n=len(sweep), mean_bits=round(float(rb.mean()), 4), median_bits=round(float(np.median(rb)), 4),
                        p10_bits=round(float(np.percentile(rb, 10)), 4), p90_bits=round(float(np.percentile(rb, 90)), 4),
                        frac_meeting_requirement=round(float((rb >= plan["requirement_bits"]).mean()), 3),
                        map_model_counts={m: sum(1 for x in sweep if x["map_model"] == m) for m in E.MODELS},
                        runs=sweep,
                        note="Twin culture world = Cell 01's graded surrogate ODE, one fixed 'nature'; the EIG averages "
                             "over the prior predictive of M1-M3, so the sweep mean need not equal it.")
    print(f"[realised] sweep over {len(sweep)} culture realisations (same executed doses): mean {rb.mean():.3f} bits, "
          f"p10-p90 {np.percentile(rb, 10):.3f}-{np.percentile(rb, 90):.3f}, meets g in "
          f"{100 * (rb >= plan['requirement_bits']).mean():.0f} %; MAP model {out['sweep']['map_model_counts']}")
    dst = os.path.join(HERE, "out", f"realised_{plan['tag']}.json")
    json.dump(out, open(dst, "w"), indent=1)
    print(f"[realised] doses delivered: " + ", ".join(f"{d['well']} {d['reagent'].split('_')[1]} "
                                                       f"{d['delivered_uL']:.2f}/{d['commanded_uL']} uL @ {d['t_h']} h"
                                                       for d in disp))
    print(f"[realised] 72 h radii (obs): " + ", ".join(f"{w} {obs[w]['radius_obs_um']}" for w in wells))
    print(f"[realised] posterior " + ", ".join(f"{m} {p:.3f}" for m, p in post.items()) +
          f"; realised gain {kl:.3f} bits (expected {sel['eig_bits']:.3f}, required {plan['requirement_bits']})")
    if "--abox" in sys.argv:
        from dl import PREFIXES
        A = []
        ri, ep = f"{E2M}/realised_gain", f"{E2M}/execution/{plan['tag']}"
        for i in (ri, ep):
            A.append(f"Declaration(NamedIndividual(<{i}>))")
        A += [f"ClassAssertion(:RealisedInformationGain <{ri}>)",
              f'DataPropertyAssertion(:realisedGain_bits <{ri}> "{round(kl, 4)}"^^xsd:double)',
              f"ObjectPropertyAssertion(:about <{ri}> <{E2M}/plan>)",
              f"ClassAssertion(:ExperimentalEpisode <{ep}>)",
              f"ObjectPropertyAssertion(:executesPlan <{ep}> <{E2M}/plan>)",
              f'DataPropertyAssertion(:statementText <{ep}> "Twin execution of the derived plan '
              f'({sum(t["steps_ok"] for t in exe["trips"])}/{sum(t["steps_total"] for t in exe["trips"])} steps ok)."'
              f'^^xsd:string)']
        for m, p in post.items():
            A.append(f'DataPropertyAssertion(:statementText <{ri}> "posterior {m} = {p:.4f}"^^xsd:string)')
        hdr = [f"Prefix({k}:=<{v}>)" for k, v in PREFIXES.items()]
        hdr += ["", "Ontology(<https://aicor.example/okf/sdt/lab1/abox/plan_execution>",
                "Import(<http://aicor.knowledge/okf/lab-automation-twin>)"]
        open(os.path.join(MOD, "abox", "plan_execution.ofn"), "w").write("\n".join(hdr + A + [")"]) + "\n")
        print("[realised] abox/plan_execution.ofn")
    return 0


if __name__ == "__main__":
    sys.exit(main())
