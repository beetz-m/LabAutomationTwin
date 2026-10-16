"""L21 reference-measurement analysis (pure numpy/scipy, no Isaac Sim): dot-grid images and light-barrier sweeps.

Dot grid (validate_imager): dots are found as dark blobs (smoothed image below 85 % of the local background),
centroided, and fitted with a lattice c = c0 + i a + j b by least squares after an initial nearest-neighbour
estimate. With the certified pitch p: pixel size = p / mean(|a|, |b|), isotropy = |a| / |b| - 1, orientation =
angle of a. Brightness = median background level in the central field (fraction of full scale).

Light barrier (validate_tool_frame): from the beam-interruption events logged while a robot swept a tool through
the beams, recover where the tool's real reference features were relative to the robot's believed TCP.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import ndimage

ADC_MAX = 4095


def find_dots(img, min_px=6):
    a = np.asarray(img, float)
    bg = ndimage.median_filter(a[::4, ::4], size=15)
    bg = ndimage.zoom(bg, (a.shape[0] / bg.shape[0], a.shape[1] / bg.shape[1]), order=1)[:a.shape[0], :a.shape[1]]
    sm = ndimage.gaussian_filter(a, 1.0)
    mask = sm < 0.85 * bg
    lab, n = ndimage.label(mask)
    if n == 0:
        return np.zeros((0, 2)), float(np.median(a))
    idx = np.arange(1, n + 1)
    size = ndimage.sum(mask, lab, idx)
    w = np.clip(bg - sm, 0, None)
    cen = np.array(ndimage.center_of_mass(w, lab, idx))            # (row, col)
    border = 3
    ok = (size >= min_px) & (cen[:, 0] > border) & (cen[:, 1] > border) & \
        (cen[:, 0] < a.shape[0] - border) & (cen[:, 1] < a.shape[1] - border)
    background = float(np.median(a[~ndimage.binary_dilation(mask, iterations=4)]))
    return cen[ok][:, ::-1], background                             # (x = col, y = row)


def fit_lattice(pts):
    """Least-squares lattice through dot centres -> (a, b) basis vectors in px, residual rms px, n used."""
    if len(pts) < 6:
        return None
    from scipy.spatial import cKDTree
    tree = cKDTree(pts)
    d, k = tree.query(pts, k=5)
    vec = (pts[k[:, 1:]] - pts[:, None, :]).reshape(-1, 2)
    nn = np.median(d[:, 1])
    vec = vec[np.abs(np.linalg.norm(vec, axis=1) - nn) < 0.25 * nn]
    ang = np.mod(np.arctan2(vec[:, 1], vec[:, 0]), np.pi / 2)        # fold to one quadrant
    th = np.angle(np.mean(np.exp(4j * ang))) / 4                     # circular mean with 90 deg symmetry
    a0 = nn * np.array([math.cos(th), math.sin(th)])
    b0 = nn * np.array([-math.sin(th), math.cos(th)])
    origin = pts[np.argmin(np.linalg.norm(pts - pts.mean(0), axis=1))]
    ij = np.round(np.linalg.solve(np.column_stack([a0, b0]), (pts - origin).T).T)
    A = np.column_stack([np.ones(len(pts)), ij])
    sol, *_ = np.linalg.lstsq(A, pts, rcond=None)
    res = pts - A @ sol
    rms = float(np.sqrt((res ** 2).sum(1).mean()))
    keep = np.linalg.norm(res, axis=1) < max(3 * rms, 0.5)           # drop mis-indexed dots, refit
    sol, *_ = np.linalg.lstsq(A[keep], pts[keep], rcond=None)
    res = pts[keep] - A[keep] @ sol
    return sol[1], sol[2], float(np.sqrt((res ** 2).sum(1).mean())), int(keep.sum())


def analyse_grid(img, pitch_um):
    pts, background = find_dots(img)
    h, w = np.asarray(img).shape
    yy, xx = np.mgrid[0:h:8, 0:w:8]
    centre = np.hypot(xx - w / 2, yy - h / 2) < 0.25 * min(w, h)
    sub = np.asarray(img, float)[::8, ::8][centre]
    bright = float(np.percentile(sub, 75) / ADC_MAX)                  # clear background dominates the field
    fit = fit_lattice(pts)
    if fit is None:
        return {"dots": int(len(pts)), "ok": False, "reason": "too few dots", "brightness_fs": round(bright, 4)}
    a, b, rms, n = fit
    la, lb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    orient = math.degrees(math.atan2(a[1], a[0]))
    orient = (orient + 45.0) % 90.0 - 45.0
    return {"ok": True, "dots": int(len(pts)), "dots_fitted": n, "pitch_px": [round(la, 4), round(lb, 4)],
            "pixel_um": round(pitch_um / ((la + lb) / 2), 5), "isotropy": round(la / lb - 1.0, 5),
            "orthogonality_deg": round(math.degrees(math.acos(abs(np.dot(a, b)) / (la * lb))) - 90.0, 4),
            "orientation_deg": round(orient, 4), "fit_rms_px": round(rms, 4), "brightness_fs": round(bright, 4),
            "background_fs": round(background / ADC_MAX, 4)}


# ------------------------------------------------------------------ light barrier
def intervals(samples):
    """[(coordinate, blocked)] in sweep order -> list of (enter, exit) coordinates of blocked runs."""
    out, start = [], None
    prev_c, prev_b = None, False
    for c, b in samples:
        if b and not prev_b:
            start = c if prev_c is None else (c + prev_c) / 2
        if prev_b and not b and start is not None:
            out.append((start, (c + prev_c) / 2))
            start = None
        prev_c, prev_b = c, b
    return out


def first_entry(samples):
    """[(coordinate, blocked)] -> [(entry,)] for the first unblocked -> blocked edge (the z sweep ends inside the
    beam, so its run never closes)."""
    for (c0, b0), (c1, b1) in zip(samples, samples[1:]):
        if b1 and not b0:
            return [((c0 + c1) / 2,)]
    return []


def tcp_from_sweeps(z_samples, y_samples, x_samples, datum, tip_below_tcp):
    """Believed-TCP error (believed - real) along x, y, z (m) from the three sweeps.

    z: descending with one finger over beam A: the first interruption is the fingertip at the beam height.
    y: sweeping across beam A: two blocked runs (the two fingers); their common centre is the real TCP y.
    x: sweeping across beam B: one blocked run (both fingers, same x extent); its centre is the real TCP x.
    """
    zi = first_entry(z_samples)
    yi = intervals(y_samples)
    xi = intervals(x_samples)
    out = {"z_runs": len(zi), "y_runs": len(yi), "x_runs": len(xi)}
    if not zi or len(yi) != 2 or len(xi) != 1:
        out["ok"] = False
        return out
    # z samples are ordered from high to low: the run starts where the tip reaches the beam
    ez = zi[0][0] - (datum[2] + tip_below_tcp)
    ey = float(np.mean([v for run in yi for v in run])) - datum[1]
    ex = float(np.mean(xi[0])) - datum[0]
    out.update(ok=True, error_mm=[round(ex * 1e3, 3), round(ey * 1e3, 3), round(ez * 1e3, 3)],
               finger_runs_y_mm=[[round((v - datum[1]) * 1e3, 2) for v in run] for run in yi],
               run_x_mm=[round((v - datum[0]) * 1e3, 2) for v in xi[0]])
    return out
