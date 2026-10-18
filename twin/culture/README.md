# Culture SDT: simulated biology, the robot's belief about it, and its representation and rendering in USD

This package implements Cell 01's biological layer as a working loop:

**biological process → robot action → measurement → state estimate → evidence/claim**

It follows the four coupled layers of Cell 01's `biophysical_v2/README.md`:
- **physical:** the robots and stations in Isaac Sim;
- **biological:** the simulated culture;
- **observation:** L17 bright-field images;
- **evidence:** records, belief and claims.

It also implements that README's "next implementation step": committing a biological event only after its physical
realization passes the execution-validity checks.

> **ILLUSTRATIVE SURROGATE, NOT A BIOMEDICAL MODEL** (Cell 01 D016; model registry M4 status
> `illustrative-not-validated`).
> - **From Cell 01 (verbatim):** the dynamics, their coefficients, the experiment design, the initial state, and the
>   morphology mapping.
> - **Twin extensions:** listed and marked in `model.py`.

## Two worlds, kept apart

| | Simulated world (`model.py` `CultureWorld`) | Culture SDT (`sdt.py` `CultureSDT`) |
|---|---|---|
| **What it is** | The hidden biology of Plate_P17's wells. | The robot's belief about it. |
| **State** | Cell 01 surrogate: injury I, protective response P, glutathione-like reserve G, viability V (`isaac_sim_biological_runtime.py`, coefficients verbatim), with a fixed per-well coefficient variability. | A particle filter per well over (I, P, G, V) **and** the well's unknown coefficient factors. Posterior mean, 90 % interval, ESS. |
| **Inputs** | What physically happened: the **delivered** volume (L12's liquid model), the light dose of every exposure (phototoxicity), and contamination (fault scenario). | Only Cell 01 records. L12 dose records are committed by **Cell 01's own** `sdt/culture_ledger.py`. A record that does not commit stays as a 50/50 "applied / not applied" hypothesis for the measurements to settle. |
| **Observations** | Its appearance feeds L17's image formation (`optics.py` → `twin/l17_optics.py SAMPLE_PROVIDER`): the organoid body, rim, lumen, necrotic core, debris and turbidity. | Morphology features from the 4× images (radius from the **calibrated** pixel size, core optical density, debris, haze). The observation model is fitted from a measurement-chain characterisation of known synthetic samples (`observation_model_v1.json`). |
| **Who reads it** | Only the observation simulators, the render layer, and the audit. | Everyone: the USD SDT layer and claims. |

**Cell 01 rules applied:**
- **`contamination_suspected`:** when haze rises above the well's own baseline, the image's evidence is blocked, the
  rule's actions are attached (quarantine, exposure graph, confirmatory tests, notify), and the well's claims are
  withheld.
- **No unverified comparator:** a claim whose comparator well had an uncommitted intervention is withheld.

## Experiment

`scripts/run_culture_experiment.py [--scenario nominal|underdose|contamination]` runs the CPU-only abstract execution
in about 25 s. It uses Cell 01's design:
- **Challenge:** A03…D04 at 0.25–0.85 au (au = abstract dose units).
- **Rescue:** A04, B04, C04 and D04 at 6 h, 0.70 au.
- **Controls:** E03, E04, F03 and F04.
- **Imaging:** a 4× image of every well every 6 h, to 72 h.

The robot operations produce the twin's real artefacts:
- **L12 doses:** Cell 01 L12 NEEM records, built by Cell 01's builders and validator through
  `episode_records.l12_dose_record`.
- **L17 images:** formed by the L17 optics model.

| Scenario | What happens | What the SDT does |
|---|---|---|
| `nominal` | All 12 doses delivered. | 12 commits; belief tracks the culture; all 4 "rescue raises 72 h viability" claims p ≈ 1 (candidate). |
| `underdose` | D03's dispense clogs: 40 % delivered, and the pressure and completion monitors fail. | The record does not commit; the images establish D03's real (milder) course; the 0.85 au claim is **withheld** (comparator not verified). |
| `contamination` | C03 is contaminated after the 24 h session. | Haze flagged at 36 h → `contamination_suspected`, evidence blocked; the 0.65 au claim **withheld**. |

**Audit (simulator side, never seen by the SDT):** in all three runs, 100 % of the belief's 90 % intervals contain the
hidden viability (±0.02).

## USD representation (time code = culture hours, 0–72)

| Layer | Contents |
|---|---|
| `culture_sdt.usda` (over `cell01_twin.usda`) | See [The SDT layer](#the-sdt-layer) below. |
| `culture_truth.usda` | `/World/SimulatedBiology/Plate_P17/<w>` `truth:*`. Simulator ground truth, outside the SDT. |
| `culture_render.usda` | The physical plate on L12's nest. Per well: a procedural organoid (lobed body with buds, necrotic core, OmniSurface subsurface), debris and medium turbidity, time-sampled from the simulated culture. The appearance derives from the state (Cell 01 USD rule 5). Cell 01's semantic plate is aligned onto it, and its placeholder spheres are hidden. |
| `culture_viz.usda` | The SDT visualisation layer (spec 18.3). Per well: a disc coloured by belief viability, a halo as wide as the 90 % interval, a purple anomaly ring and an orange unverified-dose ring. |
| `lab_culture.usda` | viz + render + `scenes/lab_site.usda` + the SDT layer: the whole lab with the culture. |

### The SDT layer

`culture_sdt.usda` writes onto Cell 01's semantic wells `/World/ExperimentalWorld/Plates/Plate_P17/Wells/<w>`:
- **Belief:** `bio:*` time samples of the belief means and `_p05`/`_p95`; `bio:uncertainty`;
  `bio:epistemicStatus = Inferred`.
- **Interventions:** committed doses as `bio:challenge*`/`bio:rescue*`; `InterventionHistory/E_*` holds every dose
  event (committed or not), plus Cell 01's `usd_event_bridge` stamps for the committed ones.
- **Observations:** `ObservationState/t_*h`, the measured features with their image and calibration provenance.
- **Quality:** `QualityAndUncertainty`, the ESS and anomaly actions.
- **Evidence:** `/World/Evidence/Culture/<run>`, the claims with probability, model, scope and status.

## Rendering

`scripts/render_culture.py <scenario> --stills | --timelapse`:
- **Stills:** path-traced macros of a challenged / rescued pair at 0, 24 and 72 h; the plate with the SDT layer;
  and the plate in context on L12.
- **Time-lapse:** RTX, 0 → 72 h, showing the camera view next to the SDT view, with live belief plots, as an MP4.

Other outputs per run: `dashboard.png` (belief bands against the dashed truth), `plate_maps.png` (orange ring: dose not verified), and
`contact_sheet.png` (every 4× image).

## Limits

- **Biology:** the surrogate is illustrative.
- **Assumed mappings:** the twin extensions (dose units, variability, phototoxicity, core OD / debris mapping,
  contamination growth) are assumptions.
- **Unmodelled processes:** there is no growth beyond Cell 01's morphology mapping, and no medium chemistry (pH,
  nutrients).
- **Execution:** the experiment runs with abstract robot execution. The physical episodes produce the same records,
  but a 72 h protocol is not run in physics; incubation intervals are fast-forwarded.
- **Model comparison:** M1–M3 (graded / threshold / protective-response) are not yet compared on the data. The claims
  use M4 only.
