"""Challenge-rescue culture experiment on the Culture SDT (abstract execution of the robot operations; CPU only).

The experiment design is Cell 01's (simulation/isaac_sim/biophysical_v2/isaac_sim_biological_runtime.py): challenge
wells A03..D04 at 0.25..0.85 au, rescue of A04/B04/C04/D04 at 6 h (0.70 au), controls E03/E04/F03/F04, an observation
every 6 h to 72 h. Each robot operation is executed abstractly but produces the same artefacts as the physical twin:
  * L12 dose -> the dose dict L12Controller produces -> Cell 01 L12 NEEM record (twin/episode_records.l12_dose_record,
    Cell 01's own builders and validator) -> Culture SDT ledger (Cell 01 sdt/culture_ledger.py);
  * L17 4x bright-field image of each well, formed by twin/l17_optics.py from the hidden culture (CultureSampleProvider)
    -> SDT image analysis with the calibrated pixel size -> belief update.
The hidden world (twin/culture/model.py) receives what physically happened (delivered volume, light dose,
contamination); the SDT receives records and images only.

Designs (--design): cell01 (default, the dose series above) | current | improved: the challenge-rescue designs of the
experiment ontology (rsa/experiment_ontology.py current_design / improved_spec): arms, their schedules (challenge,
rescue, vehicle), units and well placement are read from the design; claims are its comparisons. Output for a design
goes to scenes/culture/design_<name>/ and adds arms.png (per arm: schedule, belief vs hidden truth, 4x images).

Scenarios: nominal | underdose (D03's challenge dispense partly clogs: 40 % delivered, L12's pressure / completion
monitors fail, the record does not commit) | contamination (C03 contaminated after the 24 h session; the image haze
must trigger Cell 01's contamination_suspected rule before the belief uses it).

Outputs in scenes/culture/<scenario>/: run.json, culture_sdt.usda (belief, on Cell 01's semantic plate), culture_truth.usda
(simulator truth), images/ (4x well images per session), dashboard.png, plate_maps.png, contact_sheet.png.
Run: env_cad/bin/python scripts/run_culture_experiment.py [--scenario nominal|underdose|contamination]
"""

import argparse
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
import twin.l17_optics as op  # noqa: E402
from twin.culture import model as M  # noqa: E402
from twin.culture.cell01 import culture_ledger, usd_event_bridge  # noqa: E402
from twin.culture.optics import CultureSampleProvider, analyse  # noqa: E402
from twin.culture.sdt import CultureSDT, ObservationModel, image_well, save_json  # noqa: E402
from twin.culture.usd_layers import write_sdt_layer, write_truth_layer  # noqa: E402
from twin.episode_records import Schemas, l12_dose_record  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--scenario", choices=("nominal", "underdose", "contamination"), default="nominal")
ap.add_argument("--particles", type=int, default=800)
ap.add_argument("--design", choices=("cell01", "current", "improved"), default="cell01")
ap.add_argument("--out", default=None)
args = ap.parse_args()
OUT = args.out or os.path.join(ROOT, "scenes", "culture", args.scenario if args.design == "cell01" else f"design_{args.design}")
os.makedirs(os.path.join(OUT, "images"), exist_ok=True)
PLATE = "Plate_P17"      # the plate the twin renders; a design's own plate id is kept in run.json


def design_plan(name):
    """(wells, plan [(t_h, well, kind, au)], arms {arm: [wells]}, comparisons {name: (arm, arm)}, labels, meta)."""
    if name == "cell01":
        plan = [(0.0, w, "challenge", M.DOSE[w]) for w in M.CHALLENGE_WELLS] + \
               [(M.RESCUE_AT_H, w, "rescue", M.RESCUE_DOSE) for w in M.RESCUE_WELLS]
        return M.CHALLENGE_WELLS + M.CONTROL_WELLS, plan, None, None, None, \
            dict(source="Cell 01 isaac_sim_biological_runtime.py")
    from rsa import experiment_ontology as XO
    import json as _j
    if name == "current":
        _, spec = XO.current_design()
    else:
        pl = _j.load(open(XO.PLAN))
        spec = XO.improved_spec(pl["candidate_eig_bits"].get("c_d85_t48_n3"))
    place = spec["placement"]["wells"]
    arms, plan, labels = {}, [], {}
    for arm, a in spec["arms"].items():
        ws = [place[k] for k in sorted(place) if k.rsplit("_", 1)[0].endswith("unit_" + arm)]
        arms[arm] = ws
        for i, w in enumerate(ws):
            labels[w] = f"{arm.replace('_', ' ')} {i + 1}"
            for agent, au, t in XO.schedule(spec, arm):
                plan.append((float(t), w, agent, float(au)))
    wells = [w for ws in arms.values() for w in ws]
    return wells, sorted(plan), arms, dict(spec["comparisons"]), labels, dict(
        source=f"rsa/experiment_ontology.py ({name} design, ILLUSTRATIVE)", design_plate=spec["placement"]["plate"])


WELLS, PLAN, ARMS, COMPARISONS, LABELS, META = design_plan(args.design)
VEHICLE_UL = {}                                   # a vehicle matches the volume of the agent it stands in for
for t, w, kind, au in PLAN:
    if kind != "vehicle":
        VEHICLE_UL.setdefault(t, round(au / M.CONC_AU_PER_UL, 2))
LED, EXPOSURE_MS, PIXEL_CAL = 1.0, 25.0, 1.12        # L17 4x; pixel size from L17's applied calibration record
CAL_ID = "L17-CAL-abstract-4x"
HAZE_FACTOR = 1.12                                    # haze above the well's own 0 h baseline (+12 %)

world = M.CultureWorld(PLATE, WELLS)
op.SAMPLE_PROVIDER = CultureSampleProvider(world, [PLATE])
om = ObservationModel.load(os.path.join(ROOT, "scenes", "culture", "observation_model_v1.json"))
sdt = CultureSDT(PLATE, WELLS, om, ledger_module=culture_ledger(), n=args.particles)
schemas = Schemas()
MON = schemas.pw.load_designator_schema(schemas.root, "dose")["monitors"]
rng = np.random.default_rng(11)
records, committed_records, anomalies, haze0 = [], [], {}, {}
tips = iter(f"TIP-RACK1-{r}{c:02d}" for c in range(1, 13) for r in "ABCDEFGH")


def dose(well, kind, t_h, au, fault=None):
    vol = round(au / M.CONC_AU_PER_UL, 2) if kind != "vehicle" else VEHICLE_UL.get(t_h, 14.0)
    reagent = f"abstract_{kind}_reagent"
    lot = {"challenge": "SIM-LOT-A", "rescue": "SIM-LOT-B"}.get(kind, "SIM-LOT-V")
    delivered = vol * (0.4 if fault == "clog" else 1.0)
    world.dispense(well, reagent, delivered, t_h)                     # what physically happened
    ok = fault is None
    mons = []
    for m in MON:
        bad = (not ok) and m in ("pressure_profile", "dispense_completion")
        obs = {"pressure_profile": "plateau within 30 % of expected" if not bad else "clog limit reached; flow cut",
               "dispense_completion": "volume inferred from pressure matches command" if not bad else
               f"inferred {delivered:.1f} of {vol:.1f} uL"}.get(m, f"{m} ok (abstract execution)")
        mons.append(dict(name=m, passed=not bad, observation=obs, value=None))
    d = dict(plate_id=PLATE, well_id=well, reagent_id=reagent, reagent_lot=lot, tip_id=next(tips), volume_uL=vol,
             dispense_height_mm=1.2, dispense_rate_uL_s=2.0, intended_effect=f"abstract_{kind}", monitors=mons,
             command_completed=ok, t=t_h * 3600.0, volume_inferred_uL=delivered if not ok else vol,
             evidence={"t_start": t_h * 3600.0 - 30})
    rec = l12_dose_record(d, f"culture-{args.scenario}-{kind}-{well}-{t_h:.0f}h", schemas)
    rec["designator_id"] = f"culture-{args.scenario}/{kind}_{well}_{t_h:.0f}h"
    entry = sdt.dose_record(rec)
    records.append(dict(record=rec["designator_id"], routing=rec["routing"], eligible=rec["semantic_event"]["eligible"],
                        sdt=entry))
    if entry["committed"]:
        committed_records.append(rec)


def session(t_h):
    for well in WELLS:
        img = image_well(well, rng, barcode=PLATE, led=LED, exposure_ms=EXPOSURE_MS)
        world.illuminate(well, LED, EXPOSURE_MS / 1000.0)
        f = analyse(img, PIXEL_CAL)
        _thumb(img, well, t_h)
        rid = f"L17-IMG-{args.scenario}-{well}-{t_h:04.1f}h"
        if t_h == 0.0:
            haze0[well] = f["haze"]
        if well in anomalies:                                       # quarantined: evidence blocked
            sdt.observations.append(dict(t_h=t_h, well=well, accepted=False, features=f, record=rid,
                                         reason="contamination_suspected: evidence promotion blocked"))
            sdt.wells[well].light(LED * EXPOSURE_MS / 1000.0)
            continue
        if f["found"] and f["haze"] > max(HAZE_FACTOR * haze0.get(well, f["haze"]), haze0.get(well, 0) + 0.001):
            anomalies[well] = dict(state="contamination_suspected", t_h=t_h, haze=f["haze"],
                                   actions=["block_evidence_promotion", "quarantine_affected_material",
                                            "compute_exposure_graph", "acquire_confirmatory_tests",
                                            "inspect_downstream_tools_and_stations", "notify_scientist"])
            sdt.observations.append(dict(t_h=t_h, well=well, accepted=False, features=f, record=rid,
                                         reason="contamination_suspected (Cell 01 monitoring rule): haze "
                                                f"{f['haze']:.4f} vs baseline {haze0.get(well):.4f}"))
            sdt.wells[well].light(LED * EXPOSURE_MS / 1000.0)
            continue
        sdt.image(well, f, LED * EXPOSURE_MS / 1000.0, record_id=rid, calibration_id=CAL_ID)


def _thumb(img, well, t_h):
    from PIL import Image
    a = (img.astype(float) / 4095 * 255).clip(0, 255).astype(np.uint8)
    h, w = a.shape
    Image.fromarray(a[h // 2 - 300:h // 2 + 300, w // 2 - 300:w // 2 + 300]).resize((200, 200)).save(
        os.path.join(OUT, "images", f"{well}_{t_h:04.1f}h.png"))


times = np.arange(0.0, M.HORIZON_H + 1e-9, M.OBSERVE_EVERY_H)
for t in times:
    while sdt.t_h < t - 1e-9:                                        # hourly predictions between sessions
        world.advance(1.0)
        sdt.advance(1.0)
        for b in sdt.wells.values():
            b.summary(sdt.t_h)
    session(t)                                                       # observe before intervening
    for tp, w, kind, au in PLAN:
        if abs(tp - t) < 1e-9:
            dose(w, kind, t, au, fault="clog" if (args.scenario == "underdose" and w == "D03" and kind == "challenge") else None)
    if args.scenario == "contamination" and abs(t - 24.0) < 1e-9:
        world.contaminate("C03", t)
    print(f"[culture] t={t:4.1f} h  " + "  ".join(
        f"{w}:V {sdt.wells[w].history[-1]['V']['mean']:.2f}/{world.wells[w].x[3]:.2f}" for w in WELLS[:4]),
        flush=True)


# ---- claims (model-based, scoped) and an audit of the belief against the hidden truth
def p_greater(a, b, n=4000):
    ia = rng.choice(len(a.w), n, p=a.w)
    ib = rng.choice(len(b.w), n, p=b.w)
    return float(np.mean(a.x[ia, 3] > b.x[ib, 3]))


def p_arm_greater(wa, wb, n=4000):
    """P(mean 72 h viability of arm a's units > arm b's), from the wells' posterior particles."""
    def draw(ws):
        tot = 0.0
        for w in ws:
            b = sdt.wells[w]
            tot = tot + b.x[rng.choice(len(b.w), n, p=b.w), 3]
        return tot / len(ws)
    return float(np.mean(draw(wa) > draw(wb)))


claims = []
for cname, (aa, ab) in (COMPARISONS or {}).items():
    wa, wb = ARMS[aa], ARMS[ab]
    prop = f"{cname}: mean 72 h viability of '{aa}' ({', '.join(wa)}) exceeds '{ab}' ({', '.join(wb)})"
    bad = [w for w in wa + wb if w in anomalies or any(e["well"] == w and not e["committed"] for e in sdt.rejections)]
    if bad:
        claims.append(dict(proposition=prop, probability=float("nan"), model="M4 surrogate + M6", scope=OUT,
                           status=f"withheld: {', '.join(bad)} anomalous or with an unverified intervention"))
        continue
    p = p_arm_greater(wa, wb)
    claims.append(dict(proposition=prop, probability=round(p, 3),
                       model="M4 Cell 01 surrogate (illustrative) + M6 fitted observation model",
                       scope=f"simulated run of the {args.design} design; illustrative model, not a biological finding (D016)",
                       status="candidate" if p > 0.95 or p < 0.05 else "unresolved"))
for lvl, (wn, wr) in ({} if ARMS else {"0.25 au": ("A03", "A04"), "0.45 au": ("B03", "B04"), "0.65 au": ("C03", "C04"),
                      "0.85 au": ("D03", "D04")}).items():
    unverified = [w for w in (wn, wr) if any(e["well"] == w and not e["committed"] for e in sdt.rejections)]
    if unverified:
        claims.append(dict(proposition=f"rescue at 6 h raises 72 h viability at challenge {lvl} ({wr} vs {wn})",
                           probability=float("nan"), model="M4 surrogate + M6", scope="Plate_P17 run " + args.scenario,
                           status=f"withheld: intervention in {', '.join(unverified)} not verified (record not committed)"))
        continue
    if wn in anomalies or wr in anomalies:
        claims.append(dict(proposition=f"rescue at 6 h raises 72 h viability at challenge {lvl} ({wr} vs {wn})",
                           probability=float("nan"), model="M4 surrogate + M6", scope="Plate_P17 run " + args.scenario,
                           status="withheld: contamination_suspected in a compared well"))
        continue
    p = p_greater(sdt.wells[wr], sdt.wells[wn])
    claims.append(dict(proposition=f"rescue at 6 h raises 72 h viability at challenge {lvl} ({wr} vs {wn})",
                       probability=round(p, 3), model="M4 Cell 01 surrogate (illustrative) + M6 fitted observation model",
                       scope=f"Plate_P17, single wells, simulated run '{args.scenario}'; illustrative model, not a "
                             "biological finding (D016)", status="candidate" if p > 0.95 else "unresolved"))
cover, n_cover = 0, 0
for w in WELLS:
    th = {round(h["t_h"], 3): h for h in world.wells[w].history}
    for b in sdt.wells[w].history:
        tr = th.get(round(b["t_h"], 3))
        if tr is None or w in anomalies:
            continue
        n_cover += 1
        cover += b["V"]["p05"] - 0.02 <= tr["V"] <= b["V"]["p95"] + 0.02
audit = dict(coverage_V_90=round(cover / max(n_cover, 1), 3), n=n_cover,
             note="fraction of belief snapshots whose 90 % interval (+-0.02) contains the hidden viability; the SDT "
                  "never sees this audit")

run = dict(run_id=f"culture_{args.scenario}" + ("" if args.design == "cell01" else f"_{args.design}"),
           scenario=args.scenario if args.design == "cell01" else f"{args.design} design ({args.scenario})", design=dict(
    challenge=M.DOSE, rescue_wells=M.RESCUE_WELLS, rescue_au=M.RESCUE_DOSE, rescue_at_h=M.RESCUE_AT_H,
    controls=M.CONTROL_WELLS, observe_every_h=M.OBSERVE_EVERY_H, **META) if ARMS is None else dict(
    name=args.design, arms=ARMS, plan=PLAN, comparisons=COMPARISONS, labels=LABELS, observe_every_h=M.OBSERVE_EVERY_H,
    **META),
    truth={w: wt.history for w, wt in world.wells.items()},
    belief={w: list({h["t_h"]: h for h in b.history}.values()) for w, b in sdt.wells.items()},
    interventions=sdt.commits + sdt.rejections, records=records,
    observations={w: [o for o in sdt.observations if o["well"] == w] for w in WELLS},
    anomalies=anomalies, claims=claims, audit=audit, world_events=world.events,
    committed_records=committed_records)
save_json({k: v for k, v in run.items() if k != "committed_records"}, os.path.join(OUT, "run.json"))
applied = write_sdt_layer(os.path.join(OUT, "culture_sdt.usda"), os.path.join(ROOT, "scenes", "cell01_twin.usda"), run,
                          bridge=usd_event_bridge())
write_truth_layer(os.path.join(OUT, "culture_truth.usda"), run)
from twin.culture.render_layer import write_render_layers  # noqa: E402
write_render_layers(OUT, run, os.path.join(ROOT, "scenes", "cell01_twin.usda"), os.path.join(ROOT, "scenes", "lab_site.usda"))
from twin.culture.plots import contact_sheet, dashboard, plate_maps  # noqa: E402
dashboard(run, os.path.join(OUT, "dashboard.png"))
plate_maps(run, os.path.join(OUT, "plate_maps.png"))
contact_sheet(os.path.join(OUT, "images"), WELLS, times, os.path.join(OUT, "contact_sheet.png"),
              labels=LABELS)
if ARMS:
    from twin.culture.plots import arm_panel  # noqa: E402
    arm_panel(run, os.path.join(OUT, "images"), os.path.join(OUT, "arms.png"))
print(f"[culture] commits {len(sdt.commits)}, rejections {len(sdt.rejections)}, anomalies {list(anomalies)}; "
      f"bridge applied {sum(a['applied'] for a in applied)}/{len(applied)}; audit {audit}")
for c in claims:
    print(f"[culture] claim p={c['probability']}: {c['proposition']} [{c['status']}]")
print(f"[culture] wrote {OUT}")
