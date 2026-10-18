"""Simulated culture biology ("the world") for the Culture SDT: hidden per-well state driven by physical events.

ILLUSTRATIVE SURROGATE, NOT A BIOMEDICAL MODEL (Cell 01 D016; biological-model-registry M4 status
"illustrative-not-validated"). Every coefficient below is either copied from Cell 01 or marked as an illustrative
twin assumption:

  * Dynamics: Cell 01's executable surrogate, simulation/isaac_sim/biophysical_v2/isaac_sim_biological_runtime.py,
    step_biology(): states injury I, protective response P, glutathione-like reserve G, viability V (normalised
    [0, 1]); recovery probability R = sigma(3.2 (V - 0.5) + 1.1 P - 2.8 I + 0.7 G); uncertainty 0.04 + 0.08 I.
    Coefficients verbatim (CELL01_COEF). Integration: classical RK4 at the runtime's DT_H = 0.25 h.
  * Experiment design: the runtime's challenge/rescue design (CHALLENGE_WELLS with DOSE, RESCUE_WELLS with 0.70 au at
    6 h, CONTROL_WELLS), observations every 6 h to 72 h. Initial state: Plate_P17's well attributes in the Cell 01 USD.
  * Morphology: the runtime's update_visuals(): morphology radius = 180 + 90 V um.

Twin extensions (ILLUSTRATIVE assumptions, documented, all switchable):
  * physical coupling - the challenge / rescue input of a well is the dose actually delivered: design dose x
    (delivered uL / commanded uL), from L12's liquid model. Units: CONC_AU_PER_UL abstract units per uL.
  * well-to-well variability - each well's coefficients carry a fixed lognormal factor (sigma VARIABILITY) so wells
    differ like real cultures do; the SDT does not know these factors.
  * phototoxicity (Cell 01 process prim BiologicalProcesses/Phototoxicity) - each exposure adds
    K_PHOTO x light dose (LED level x exposure s) to the injury input.
  * necrotic core optical density 0.15 + 0.55 I and debris count 40 (1 - V) - the bright-field appearance of injury.
  * contamination (fault scenario only, Cell 01 mathematical-models section 7 form): dB = r_B B (1 - B/K_B);
    injury input + K_CONTAM B; medium turbidity = B.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

# --- Cell 01 (verbatim from isaac_sim_biological_runtime.py) -------------------------------------------------------
DT_H = 0.25
CELL01_COEF = dict(k_inj=0.18, k_rel=0.045, k_prot=0.10, k_resc_i=0.12, k_act=0.055, k_deg=0.020, k_syn=0.035,
                   k_cons=0.10, k_resc_g=0.055, k_death=0.060, k_resc_v=0.030)
CHALLENGE_WELLS = ["A03", "A04", "B03", "B04", "C03", "C04", "D03", "D04"]
RESCUE_WELLS = ["A04", "B04", "C04", "D04"]
CONTROL_WELLS = ["E03", "E04", "F03", "F04"]
DOSE = {"A03": 0.25, "A04": 0.25, "B03": 0.45, "B04": 0.45, "C03": 0.65, "C04": 0.65, "D03": 0.85, "D04": 0.85}
RESCUE_DOSE, RESCUE_AT_H, HORIZON_H, OBSERVE_EVERY_H = 0.70, 6.0, 72.0, 6.0
INITIAL = dict(I=0.05, P=0.05, G=0.95, V=0.98)          # Plate_P17 well attributes (bio:injury ... bio:viability)

# --- twin extensions (ILLUSTRATIVE) -----------------------------------------------------------------------------------
CONC_AU_PER_UL = 0.05            # abstract challenge / rescue units per uL dispensed (0.25 au = 5 uL ... 0.85 au = 17 uL)
VARIABILITY = 0.15               # lognormal sigma of per-well coefficient factors
K_PHOTO = 0.004                  # injury input per (LED level x exposure s)
CONTAM = dict(r_B=0.35, K_B=1.0, k=0.25, B0=0.02)


def sigmoid(z):
    return 1.0 / (1.0 + math.exp(-z))


def recovery_probability(I, P, G, V):
    return sigmoid(3.2 * (V - 0.5) + 1.1 * P - 2.8 * I + 0.7 * G)


def deriv(x, u, k):
    """Cell 01 surrogate right-hand side. x = (I, P, G, V); u = (challenge au, rescue au, extra injury input)."""
    I, P, G, V = x
    c, r, extra = u
    dI = k["k_inj"] * c * (1 - I) - k["k_rel"] * I - k["k_prot"] * P * I - k["k_resc_i"] * r * I + extra * (1 - I)
    dP = k["k_act"] * I * (1 - P) - k["k_deg"] * P
    dG = k["k_syn"] * (1 - G) - k["k_cons"] * I * G + k["k_resc_g"] * r * (1 - G)
    dV = -k["k_death"] * I * V + k["k_resc_v"] * r * (1 - V)
    return np.array([dI, dP, dG, dV])


def rk4(x, u, k, dt):
    k1 = deriv(x, u, k)
    k2 = deriv(x + 0.5 * dt * k1, u, k)
    k3 = deriv(x + 0.5 * dt * k2, u, k)
    k4 = deriv(x + dt * k3, u, k)
    return np.clip(x + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4), 0.0, 1.0)


def morphology(I, V):
    """Observable appearance from latent state: radius (Cell 01 mapping), necrotic core OD, debris (illustrative)."""
    return dict(radius_um=180.0 + 90.0 * V, core_od=0.15 + 0.55 * I, debris=int(round(40 * (1 - V))))


@dataclass
class WellTruth:
    well: str
    coef: dict
    x: np.ndarray
    challenge_au: float = 0.0
    rescue_au: float = 0.0
    challenge_t: float = -1.0
    rescue_t: float = -1.0
    photo_input: float = 0.0          # pending injury input from light, applied over the next step
    contam_B: float = 0.0
    history: list = field(default_factory=list)


class CultureWorld:
    """The hidden biological world of one plate. Only physical events reach it; nobody reads it but the simulators
    of physical observation (L17 image formation) and the audit tools."""

    def __init__(self, plate_id="Plate_P17", wells=None, seed=17, variability=VARIABILITY):
        rng = np.random.default_rng(seed)
        self.plate_id = plate_id
        self.t_h = 0.0
        self.wells = {}
        for w in wells or (CHALLENGE_WELLS + CONTROL_WELLS):
            f = {k: v * float(np.exp(rng.normal(0, variability))) for k, v in CELL01_COEF.items()}
            x0 = np.array([INITIAL["I"], INITIAL["P"], INITIAL["G"], INITIAL["V"]]) + rng.normal(0, 0.01, 4)
            self.wells[w] = WellTruth(w, f, np.clip(x0, 0, 1))
        self.events = []
        self._record()

    # ---------------------------------------------------------------- physical events (from the robot twin)
    def dispense(self, well, reagent_id, delivered_uL, t_h=None):
        """A physical dispense into a well (whatever the robot believes): challenge or rescue by reagent class."""
        t_h = self.t_h if t_h is None else t_h
        wt = self.wells.get(well)
        if wt is None:
            return
        au = CONC_AU_PER_UL * delivered_uL
        if "challenge" in reagent_id:
            wt.challenge_au += au
            wt.challenge_t = t_h if wt.challenge_t < 0 else wt.challenge_t
        elif "rescue" in reagent_id:
            wt.rescue_au += au
            wt.rescue_t = t_h if wt.rescue_t < 0 else wt.rescue_t
        else:                                       # vehicle: volume only, no surrogate input
            au = 0.0
        self.events.append(dict(t_h=t_h, kind="dispense", well=well, reagent=reagent_id, delivered_uL=delivered_uL,
                                au=round(au, 4)))

    def illuminate(self, well, led_level, exposure_s):
        wt = self.wells.get(well)
        if wt is not None:
            wt.photo_input += K_PHOTO * led_level * exposure_s

    def contaminate(self, well, t_h=None):
        wt = self.wells.get(well)
        if wt is not None and wt.contam_B == 0.0:
            wt.contam_B = CONTAM["B0"]
            self.events.append(dict(t_h=self.t_h if t_h is None else t_h, kind="contamination_introduced", well=well))

    # ---------------------------------------------------------------- time
    def advance(self, hours):
        n = int(round(hours / DT_H))
        for _ in range(n):
            for wt in self.wells.values():
                extra = wt.photo_input / DT_H
                wt.photo_input = 0.0
                if wt.contam_B > 0:
                    B = wt.contam_B
                    wt.contam_B = min(1.0, B + DT_H * CONTAM["r_B"] * B * (1 - B / CONTAM["K_B"]))
                    extra += CONTAM["k"] * wt.contam_B
                wt.x = rk4(wt.x, (wt.challenge_au, wt.rescue_au, extra), wt.coef, DT_H)
            self.t_h += DT_H
            self._record()

    def _record(self):
        for wt in self.wells.values():
            I, P, G, V = wt.x
            wt.history.append(dict(t_h=round(self.t_h, 3), I=float(I), P=float(P), G=float(G), V=float(V),
                                   R=recovery_probability(I, P, G, V), B=wt.contam_B, **morphology(I, V)))

    def appearance(self, well):
        """What a camera would see in this well now (for image formation / rendering only)."""
        wt = self.wells.get(well)
        if wt is None:
            return None
        I, P, G, V = wt.x
        return dict(**morphology(I, V), turbidity=wt.contam_B, viability=float(V), injury=float(I))
