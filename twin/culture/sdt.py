"""Culture SDT: the robot's belief about the culture, built only from committed records and measurements.

Separation of worlds (Cell 01 biology ontology, evidence-hidden-state.md and the USD mapping rules):
  * twin/culture/model.py CultureWorld is the simulated biology. The SDT never reads it.
  * The SDT receives (1) L12 dose records - committed through Cell 01's own CultureSDTLedger (sdt/culture_ledger.py,
    imported read-only) - and (2) L17 bright-field images, analysed into morphology features with the calibrated
    pixel size (twin/culture/optics.py analyse()).
  * Its belief p(x_t | D_t) is a particle filter per well over the latent state x = (I, P, G, V) of the Cell 01
    surrogate (registry M4) AND the well's unknown coefficient factors (the SDT knows the model structure and the
    nominal Cell 01 coefficients, not the individual well). Mathematical-models.md sections 2 and 9.
  * Doses that physically happened but did not commit (a rejected or ambiguous record) are not ignored: each particle
    carries the hypothesis "applied" or "not applied" (50/50) and the measurements decide - fault vs finding.

Observation model (registry M6): fitted, not assumed - ObservationModel.fit() images known synthetic organoids
(a grid of latent states through the same optics + analysis chain, i.e. a measurement-chain characterisation on
reference samples) and regresses the measured features on the state. Its residual sigma is the measurement noise.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np

from twin.culture import model as M

RNG = np.random.default_rng(2026)


# ------------------------------------------------------------------------------------------- observation model
class ObservationModel:
    FEATURES = ("radius_um", "core_od")

    def __init__(self, coef=None, sigma=None, meta=None):
        self.coef, self.sigma, self.meta = coef or {}, sigma or {}, meta or {}

    @staticmethod
    def design(I, V):
        I, V = np.asarray(I, float), np.asarray(V, float)
        return np.stack([np.ones_like(I), I, V, I * V, I * I, V * V], -1)

    def predict(self, I, V):
        X = self.design(I, V)
        return {f: X @ np.array(self.coef[f]) for f in self.FEATURES}

    @classmethod
    def fit(cls, n_states=60, wells=("A01", "C05", "E09", "G12"), seed=5):
        import twin.l17_optics as op
        from twin.culture.optics import analyse, organoid_objects
        rng = np.random.default_rng(seed)
        rows = []
        for _ in range(n_states):
            I, V = rng.uniform(0.0, 0.85), rng.uniform(0.05, 1.0)
            for w in wells:
                look = dict(**M.morphology(I, V), turbidity=0.0, viability=V, injury=I)
                prev = op.SAMPLE_PROVIDER
                op.SAMPLE_PROVIDER = lambda b, ww, _w=w, _l=look: organoid_objects("CAL-REF", ww, _l) if ww == _w else None
                try:
                    img = image_well(w, rng)
                finally:
                    op.SAMPLE_PROVIDER = prev
                a = analyse(img, 1.12)
                if a["found"] and a["core_od"] is not None and not a["touches_edge"]:
                    rows.append((I, V, a["radius_um"], a["core_od"]))
        R = np.array(rows)
        X = cls.design(R[:, 0], R[:, 1])
        coef, sigma = {}, {}
        for j, f in enumerate(cls.FEATURES):
            y = R[:, 2 + j]
            c, *_ = np.linalg.lstsq(X, y, rcond=None)
            coef[f] = c.tolist()
            sigma[f] = float(np.std(y - X @ c) * 1.2 + (2.0 if f == "radius_um" else 0.01))
        meta = dict(samples=len(R), method="4x bright-field images of synthetic organoids of known latent state, "
                    "4 well positions (shape variation), analysed with twin/culture/optics.py analyse(); quadratic "
                    "regression on (I, V); sigma = 1.2 x residual std + floor", wells=list(wells))
        return cls(coef, sigma, meta)

    def save(self, path):
        json.dump(dict(coef=self.coef, sigma=self.sigma, meta=self.meta), open(path, "w"), indent=1)

    @classmethod
    def load(cls, path):
        d = json.load(open(path))
        return cls(d["coef"], d["sigma"], d["meta"])


def image_well(well, rng, pixel_um=1.12, na=0.10, defocus_um=0.0, led=1.0, exposure_ms=25.0, barcode="CAL-REF"):
    """A 4x bright-field image of a well with an ideally seated plate (abstract execution / calibration)."""
    import twin.l17_optics as op
    u, v = op.well_center(well)
    img, _ = op.form_image(plate_pos=np.zeros(3), plate_R=np.eye(3), well_bottom_mm=1.0, barcode=barcode,
                           focal_point=np.array([u * 1e-3, v * 1e-3, 1e-3 - defocus_um * 1e-6]),
                           axis=np.array([0, 0, 1.0]), ex=np.array([1.0, 0, 0]), ey=np.array([0, 1.0, 0]), na=na,
                           pixel_um=pixel_um, led_level=led, exposure_ms=exposure_ms, rng=rng)
    return img


# ------------------------------------------------------------------------------------------- particle filter
KEYS = list(M.CELL01_COEF)


class WellBelief:
    def __init__(self, well, n=800, prior_sigma=0.20, rng=RNG):
        self.well, self.n = well, n
        self.rng = rng
        x0 = np.array([M.INITIAL["I"], M.INITIAL["P"], M.INITIAL["G"], M.INITIAL["V"]])
        self.x = np.clip(x0 + rng.normal(0, 0.02, (n, 4)), 0, 1)
        self.f = {k: v * np.exp(rng.normal(0, prior_sigma, n)) for k, v in M.CELL01_COEF.items()}
        self.c = np.zeros(n)            # challenge au per particle (hypotheses for unconfirmed doses)
        self.r = np.zeros(n)
        self.photo = np.zeros(n)
        self.w = np.full(n, 1.0 / n)
        self.log_evidence = 0.0
        self.history = []
        self.events = []

    # inputs
    def dose(self, kind, au, committed=True, t_h=None):
        applied = np.ones(self.n, bool) if committed else self.rng.random(self.n) < 0.5
        if kind == "challenge":
            self.c = self.c + au * applied
        elif kind == "rescue":
            self.r = self.r + au * applied          # a vehicle has no input in the surrogate
        self.events.append(dict(t_h=t_h, kind=kind, au=au, committed=committed))

    def light(self, dose):
        self.photo = self.photo + M.K_PHOTO * dose

    # dynamics
    def predict(self, hours):
        steps = int(round(hours / M.DT_H))
        for _ in range(steps):
            extra = self.photo / M.DT_H
            self.photo = np.zeros(self.n)
            u = (self.c, self.r, extra)
            x = self.x
            k1 = _deriv(x, u, self.f)
            k2 = _deriv(x + 0.5 * M.DT_H * k1, u, self.f)
            k3 = _deriv(x + 0.5 * M.DT_H * k2, u, self.f)
            k4 = _deriv(x + M.DT_H * k3, u, self.f)
            x = x + M.DT_H / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
            x = x + self.rng.normal(0, 0.004, x.shape)                 # process noise
            self.x = np.clip(x, 0, 1)

    # measurement update
    def update(self, obs, om: ObservationModel):
        pred = om.predict(self.x[:, 0], self.x[:, 3])
        ll = np.zeros(self.n)
        for f in om.FEATURES:
            if obs.get(f) is None:
                continue
            s = om.sigma[f]
            ll += -0.5 * ((obs[f] - pred[f]) / s) ** 2 - math.log(s * math.sqrt(2 * math.pi))
        m = ll.max()
        lik = np.exp(ll - m)
        evid = float(np.sum(self.w * lik))
        self.log_evidence += math.log(max(evid, 1e-300)) + m
        self.w = self.w * lik
        self.w /= self.w.sum()
        ess = 1.0 / np.sum(self.w ** 2)
        if ess < self.n / 2:
            self._resample()
        return ess

    def _resample(self):
        n = self.n
        pos = (self.rng.random() + np.arange(n)) / n
        idx = np.searchsorted(np.cumsum(self.w), pos)
        idx = np.minimum(idx, n - 1)
        self.x = self.x[idx]
        self.c, self.r, self.photo = self.c[idx], self.r[idx], self.photo[idx]
        self.f = {k: v[idx] * np.exp(self.rng.normal(0, 0.02, n)) for k, v in self.f.items()}   # jitter
        self.w = np.full(n, 1.0 / n)

    # summaries
    def summary(self, t_h):
        I, P, G, V = self.x.T
        R = 1.0 / (1.0 + np.exp(-(3.2 * (V - 0.5) + 1.1 * P - 2.8 * I + 0.7 * G)))
        out = dict(t_h=round(t_h, 3), ess=round(float(1.0 / np.sum(self.w ** 2)), 1))
        for name, arr in (("I", I), ("P", P), ("G", G), ("V", V), ("R", R)):
            mean = float(np.sum(self.w * arr))
            lo, hi = _wquant(arr, self.w, 0.05), _wquant(arr, self.w, 0.95)
            out[name] = dict(mean=round(mean, 4), p05=round(lo, 4), p95=round(hi, 4))
        if self.events and any(not e["committed"] for e in self.events):
            out["p_unconfirmed_dose_applied"] = round(float(np.sum(self.w * (self.c > 0))), 3)
        self.history.append(out)
        return out


def _deriv(x, u, f):
    I, P, G, V = x[:, 0], x[:, 1], x[:, 2], x[:, 3]
    c, r, extra = u
    dI = f["k_inj"] * c * (1 - I) - f["k_rel"] * I - f["k_prot"] * P * I - f["k_resc_i"] * r * I + extra * (1 - I)
    dP = f["k_act"] * I * (1 - P) - f["k_deg"] * P
    dG = f["k_syn"] * (1 - G) - f["k_cons"] * I * G + f["k_resc_g"] * r * (1 - G)
    dV = -f["k_death"] * I * V + f["k_resc_v"] * r * (1 - V)
    return np.stack([dI, dP, dG, dV], 1)


def _wquant(a, w, q):
    o = np.argsort(a)
    cw = np.cumsum(w[o])
    return float(a[o][min(np.searchsorted(cw, q), len(a) - 1)])


# ------------------------------------------------------------------------------------------- Culture SDT
class CultureSDT:
    """Per-plate belief + ledger. Inputs: Cell 01 records (dose), image analyses; time advances in culture hours."""

    def __init__(self, plate_id, wells, om, ledger_module=None, n=800):
        self.plate_id, self.om = plate_id, om
        self.wells = {w: WellBelief(w, n) for w in wells}
        self.t_h = 0.0
        self.ledger = None
        if ledger_module is not None:
            st = ledger_module.CultureSDTState(plate_id=plate_id)
            self.ledger = ledger_module.CultureSDTLedger(st)
        self.commits, self.rejections, self.observations = [], [], []
        for b in self.wells.values():
            b.summary(0.0)

    def advance(self, hours):
        for b in self.wells.values():
            b.predict(hours)
        self.t_h += hours

    def dose_record(self, record):
        """An L12 dose record (Cell 01 format). Committed -> input; rejected -> unconfirmed hypothesis."""
        d = record["designator"]
        well = d["well_id"]
        if well not in self.wells:
            return None
        res = self.ledger.commit_l12_intervention(record) if self.ledger else None
        committed = bool(res.committed) if res else bool(record.get("semantic_event", {}).get("eligible"))
        vol = (record.get("evidence") or {}).get("volume_inferred_from_pressure_uL") or d["volume_uL"]
        kind = "challenge" if "challenge" in d["reagent_id"] else "vehicle" if "vehicle" in d["reagent_id"] else "rescue"
        au = 0.0 if kind == "vehicle" else M.CONC_AU_PER_UL * float(vol)
        self.wells[well].dose(kind, au, committed=committed, t_h=self.t_h)
        entry = dict(t_h=round(self.t_h, 3), well=well, kind=kind, au=round(au, 4), committed=committed,
                     record=record.get("designator_id") or record.get("episode_id"),
                     reasons=list(res.reasons) if res else [])
        (self.commits if committed else self.rejections).append(entry)
        return entry

    def image(self, well, features, light_dose, record_id=None, calibration_id=None):
        b = self.wells.get(well)
        if b is None:
            return None
        b.light(light_dose)
        if not features.get("found"):
            self.observations.append(dict(t_h=self.t_h, well=well, accepted=False, reason="no organoid found"))
            return None
        ess = b.update(features, self.om)
        s = b.summary(self.t_h)
        self.observations.append(dict(t_h=round(self.t_h, 3), well=well, accepted=True, features=features,
                                      record=record_id, calibration=calibration_id, ess=round(ess, 1)))
        return s

    def snapshot(self):
        return {w: b.summary(self.t_h) for w, b in self.wells.items()}


def save_json(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w"), indent=1, default=str)
