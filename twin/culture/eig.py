"""Expected information gain of candidate culture experiments over Cell 01's competing recovery models.

Cell 01 (biology/ontology/mathematical-models.md):
  §5  M1 graded recovery          P_rec = σ(β0 − β1 I − β2 Δt + β3 d_r)              (no point of no return)
      M2 threshold                rescue fails once the cumulative injury burden B(Δt) = ∫ I dτ ≥ B*
      M3 protective response      B*(t) = B0* + α P(t)  (the threshold moves with adaptive protection)
  §10 EIG(a) = E_{y∼p(y|a,D)} [ KL( p(M | D, y, a) ‖ p(M | D) ) ]   = I(M ; y | a, D)

Construction (ILLUSTRATIVE, D016 - no biomedical parameter is asserted):
  * latent dynamics: Cell 01's surrogate (twin/culture/model.py, coefficients verbatim) with the twin's per-well
    coefficient variability; the challenge acts from t = 0, the rescue (0.70 au) from Δt.
  * each model maps the latent state AT RESCUE TIME to a rescue efficacy e ∈ [ε, 1]; the rescued well's 72 h viability
    is V_none + e (V_full − V_none), where V_none / V_full are the surrogate's 72 h viability without / with a fully
    effective rescue at Δt.
  * parameter priors are CALIBRATED to the data already observed (D: rescue at 6 h raised 72 h viability at 0.25 ..
    0.85 au): every prior sample must give e(6 h, d) ≥ 0.9 at the observed doses (rejection). So M1-M3 agree on D and
    differ only where nothing has been measured yet - which is what makes the information gain non-trivial.
  * observations: 72 h organoid radius (Cell 01 mapping 180 + 90 V µm) of n rescued wells and n challenge-only
    comparator wells, with the twin's fitted measurement noise (observation_model_v1.json, σ ≈ 2.5 µm).
  * EIG: nested Monte Carlo; the class-conditional likelihood p(y | M, a) is a Gaussian fitted to simulated
    observation vectors of model M (moment matching), the outer expectation samples M ∼ p(M | D) and y ∼ p(y | M, a).
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass

import numpy as np

from twin.culture.model import CELL01_COEF, DT_H, HORIZON_H, INITIAL, RESCUE_DOSE, VARIABILITY

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OBS_MODEL = os.path.join(ROOT, "scenes", "culture", "observation_model_v1.json")
OBSERVED_DOSES = (0.25, 0.45, 0.65, 0.85)     # D: rescue at 6 h effective at these doses (nominal run, all claims p≈1)
OBSERVED_DELAY_H = 6.0
MODELS = ("M1_graded", "M2_threshold", "M3_protective")
EPS = 0.05                                    # residual efficacy past a point of no return (illustrative)


def _sigma_radius():
    try:
        return float(json.load(open(OBS_MODEL))["sigma"]["radius_um"])
    except Exception:
        return 2.5


def simulate(dose, delay_h, n, rng, rescue=True):
    """Vectorised Cell 01 surrogate for n wells with per-well coefficient factors.
    Returns state trajectories needed by the models: I and P at rescue time, cumulative injury B(Δt),
    and 72 h viability without rescue (V_none) and with a fully effective rescue at Δt (V_full)."""
    k = {kk: v * np.exp(rng.normal(0, VARIABILITY, n)) for kk, v in CELL01_COEF.items()}
    x0 = np.array([INITIAL["I"], INITIAL["P"], INITIAL["G"], INITIAL["V"]])
    steps = int(round(HORIZON_H / DT_H))
    out = {}
    for label, resc in (("none", False), ("full", True)):
        X = np.tile(x0, (n, 1)).astype(float)
        B = np.zeros(n)
        for s in range(steps):
            t = s * DT_H
            r = RESCUE_DOSE if (resc and t >= delay_h) else 0.0
            if label == "none" and t < delay_h:
                B += X[:, 0] * DT_H
            if label == "none" and abs(t - delay_h) < DT_H / 2:
                out["I_at"], out["P_at"] = X[:, 0].copy(), X[:, 1].copy()

            def f(X):
                I, P, G, V = X.T
                dI = k["k_inj"] * dose * (1 - I) - k["k_rel"] * I - k["k_prot"] * P * I - k["k_resc_i"] * r * I
                dP = k["k_act"] * I * (1 - P) - k["k_deg"] * P
                dG = k["k_syn"] * (1 - G) - k["k_cons"] * I * G + k["k_resc_g"] * r * (1 - G)
                dV = -k["k_death"] * I * V + k["k_resc_v"] * r * (1 - V)
                return np.stack([dI, dP, dG, dV], 1)
            k1 = f(X)
            k2 = f(X + 0.5 * DT_H * k1)
            k3 = f(X + 0.5 * DT_H * k2)
            k4 = f(X + DT_H * k3)
            X = np.clip(X + DT_H / 6 * (k1 + 2 * k2 + 2 * k3 + k4), 0, 1)
        out["V_" + label] = X[:, 3]
    out["B"] = B
    return out


@dataclass
class ModelPrior:
    name: str
    params: np.ndarray        # (S, p) accepted parameter samples


def efficacy(name, th, st, delay_h, dose):
    """Rescue efficacy e(state at rescue) under model `name` with parameters th (vectorised over wells)."""
    if name == "M1_graded":
        b0, b1, b2, b3 = th
        return 1.0 / (1.0 + np.exp(-(b0 - b1 * st["I_at"] - b2 * delay_h + b3 * RESCUE_DOSE)))
    if name == "M2_threshold":
        (bstar,) = th
        return np.where(st["B"] < bstar, 1.0, EPS)
    (b0star, alpha) = th
    return np.where(st["B"] < b0star + alpha * st["P_at"], 1.0, EPS)


def sample_prior(name, rng, n=400):
    """Parameter samples calibrated to D: e(6 h, d) ≥ 0.9 for every observed dose (mean over 32 simulated wells)."""
    ref = {d: simulate(d, OBSERVED_DELAY_H, 32, np.random.default_rng(1000 + int(d * 100))) for d in OBSERVED_DOSES}
    acc, tries = [], 0
    while len(acc) < n and tries < 60 * n:
        tries += 1
        if name == "M1_graded":
            th = (rng.uniform(2, 9), rng.uniform(0, 12), rng.uniform(0.0, 0.35), rng.uniform(0, 3))
        elif name == "M2_threshold":
            th = (rng.uniform(0.2, 12.0),)
        else:
            th = (rng.uniform(0.2, 12.0), rng.uniform(0.0, 20.0))
        if all(efficacy(name, th, ref[d], OBSERVED_DELAY_H, d).mean() >= 0.9 for d in OBSERVED_DOSES):
            acc.append(th)
    return ModelPrior(name, np.array(acc))


def predict(name, prior, dose, delay_h, n_rep, S, rng):
    """S simulated observation vectors y = (radii of n_rep rescued wells, radii of n_rep challenge-only wells)."""
    sig = _sigma_radius()
    st_r = simulate(dose, delay_h, S * n_rep, rng)
    st_c = simulate(dose, delay_h, S * n_rep, rng)
    th = prior.params[rng.integers(0, len(prior.params), S)]
    e = np.empty(S * n_rep)
    for s in range(S):
        sl = slice(s * n_rep, (s + 1) * n_rep)
        e[sl] = efficacy(name, th[s], {k: v[sl] for k, v in st_r.items()}, delay_h, dose)
    v_resc = st_r["V_none"] + e * (st_r["V_full"] - st_r["V_none"])
    y_r = (180 + 90 * v_resc + rng.normal(0, sig, S * n_rep)).reshape(S, n_rep)
    y_c = (180 + 90 * st_c["V_none"] + rng.normal(0, sig, S * n_rep)).reshape(S, n_rep)
    return np.concatenate([y_r, y_c], 1)


def eig(priors, pM, dose, delay_h, n_rep, S=600, seed=0):
    """I(M; y) in bits by nested Monte Carlo with moment-matched Gaussian class likelihoods."""
    rng = np.random.default_rng(seed)
    sims = {m: predict(m, priors[m], dose, delay_h, n_rep, S, rng) for m in MODELS}
    # summary statistic: mean rescued radius - mean comparator radius (sufficient for the rescue effect), and the mean
    stats = {m: np.stack([y[:, :n_rep].mean(1) - y[:, n_rep:].mean(1), y.mean(1)], 1) for m, y in sims.items()}
    gauss = {}
    for m, z in stats.items():
        mu = z.mean(0)
        cov = np.cov(z.T) + np.eye(2) * 1e-3
        gauss[m] = (mu, np.linalg.inv(cov), -0.5 * math.log(np.linalg.det(2 * math.pi * cov)))

    def loglik(z):
        return np.stack([g[2] - 0.5 * np.einsum("ij,jk,ik->i", z - g[0], g[1], z - g[0]) for g in
                         (gauss[m] for m in MODELS)], 1)
    total = 0.0
    p = np.array([pM[m] for m in MODELS])
    for i, m in enumerate(MODELS):
        ll = loglik(stats[m])
        lp = ll + np.log(p)
        post = np.exp(lp - lp.max(1, keepdims=True))
        post /= post.sum(1, keepdims=True)
        kl = np.sum(np.where(post > 0, post * np.log2(np.maximum(post, 1e-300) / p), 0.0), 1)
        total += p[i] * kl.mean()
    pred = {m: dict(effect_um=float(stats[m][:, 0].mean()), effect_sd_um=float(stats[m][:, 0].std())) for m in MODELS}
    return float(total), pred


def posterior_over_models(priors, pM, dose, delay_h, y_r, y_c, S=2000, seed=1):
    """p(M | D, y) for an executed experiment (Gaussian class likelihoods on the same summary statistic)."""
    rng = np.random.default_rng(seed)
    n = len(y_r)
    z = np.array([np.mean(y_r) - np.mean(y_c), np.mean(np.concatenate([y_r, y_c]))])
    lp = []
    for m in MODELS:
        y = predict(m, priors[m], dose, delay_h, n, S, rng)
        st = np.stack([y[:, :n].mean(1) - y[:, n:].mean(1), y.mean(1)], 1)
        mu, cov = st.mean(0), np.cov(st.T) + np.eye(2) * 1e-3
        d = z - mu
        lp.append(math.log(pM[m]) - 0.5 * d @ np.linalg.inv(cov) @ d - 0.5 * math.log(np.linalg.det(2 * math.pi * cov)))
    lp = np.array(lp)
    post = np.exp(lp - lp.max())
    post /= post.sum()
    return {m: float(p) for m, p in zip(MODELS, post)}
