"""Bright-field image formation for the L17 twin: simulated state in, raw camera image out (pure numpy).

The L17 controller sees only the image this returns and its own encoders; the ground truth (defocus, the plate
coordinates actually imaged) is returned separately for tests and evidence audits, never to the controller.

Inputs, all from the running simulation (twin/l17_controller.py: L17Camera):
  * the plate's pose (PhysX rigid body), so a mis-seated or tilted plate is imaged where it really is;
  * the focal point and optical axis of the indexed objective (FocusZ joint position, TurretRotate index);
  * the LED level (the illumination light prim) and the exposure time.

Model (optical and sensor engineering ASSUMPTIONS, documented here; no biological parameters, D016):
  * Sample: a SYNTHETIC OPTICAL TEST SAMPLE per (plate barcode, well): absorbing Gaussian objects (a body and a
    denser core) scattered over the well bottom, seeded from the barcode and well id. It exists to give images
    structure for focus and registration checks. It is not a model of cells, morphology or a culture.
  * Reference plates (barcode REF-...): a dot grid of known pitch in every well (L21's reference artifact).
  * Well: transmission drops to 0.3 outside the 6.9 mm well bottom (the wall region), so a field of view that is
    off the well shows the edge.
  * PSF: Gaussian, sigma^2 = diffraction (0.21 lambda / NA)^2 + geometric defocus (|dz| NA / (2 sqrt(1 - NA^2)))^2
    + pixel footprint. Gaussian objects blurred by a Gaussian stay Gaussian, so blurring is exact and cheap.
  * Illumination: LED level x exposure -> photoelectrons with 12 % radial vignetting; Poisson shot noise, 3 e-
    read noise, 10 000 e- full well, 12-bit ADC. At LED 1.0 and 25 ms the clear background sits near 60 % of
    full scale.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np

SENSOR = (820, 616)                # px (w, h): a 4x4-binned 3280 x 2464 sensor
LAMBDA_UM = 0.55
FULL_WELL_E, READ_E, ADC_MAX = 10000.0, 3.0, 4095
E_PER_MS = 240.0                   # e- per ms per pixel at LED level 1.0, clear background, centre of field
VIGNETTE = 0.12
WELL_PITCH, WELL_R = 9.0, 3.45     # mm (SBS 96)
A1 = (-49.5, 31.5)                 # well A1 centre, plate frame (mm, origin = plate centre, A1 at -X/+Y)
ROWS = "ABCDEFGH"
OUTSIDE_T = 0.3
OBJECTS_PER_MM2 = 150.0            # synthetic test-sample density (arbitrary: about 15-20 objects per 10x field)
# Reference plates (barcode "REF-..."): every well carries a dot-grid target, the L21 reference artifact. The pitch
# here is the TRUE pitch of the physical artifact; L21 holds its certified value (twin/l21_controller.py).
REFERENCE_GRID = {"pitch_um": 50.0, "dot_sigma_um": 2.0, "absorption": 0.55}


def well_center(well_id: str) -> tuple[float, float]:
    r, c = ROWS.index(well_id[0].upper()), int(well_id[1:]) - 1
    if not (0 <= r < 8 and 0 <= c < 12):
        raise ValueError(well_id)
    return A1[0] + WELL_PITCH * c, A1[1] - WELL_PITCH * r


def well_ids():
    return [f"{r}{c:02d}" for r in ROWS for c in range(1, 13)]


def parse_well(well_id: str) -> str | None:
    """Canonical well id (A01..H12) or None if it is not a 96-well coordinate."""
    try:
        r, c = well_id[0].upper(), int(well_id[1:])
    except (ValueError, IndexError):
        return None
    return f"{r}{c:02d}" if r in ROWS and 1 <= c <= 12 else None


def nearest_well(u_mm: float, v_mm: float):
    c = int(round((u_mm - A1[0]) / WELL_PITCH))
    r = int(round((A1[1] - v_mm) / WELL_PITCH))
    if not (0 <= r < 8 and 0 <= c < 12):
        return None, None
    wid = f"{ROWS[r]}{c + 1:02d}"
    cx, cy = well_center(wid)
    return wid, math.hypot(u_mm - cx, v_mm - cy)


_SAMPLES: dict = {}
# Optional plug (twin/culture/optics.py CultureSampleProvider): objects of a live, changing sample (a simulated
# culture). Called first and never cached; returns None for wells it does not own.
SAMPLE_PROVIDER = None


def sample_objects(barcode: str, well_id: str):
    """Synthetic optical test objects in one well: (x_mm, y_mm, sigma_um, absorption), cores included."""
    if SAMPLE_PROVIDER is not None:
        live = SAMPLE_PROVIDER(barcode, well_id)
        if live is not None:
            return live
    key = (barcode, well_id)
    if key not in _SAMPLES and barcode.startswith("REF-"):
        g = REFERENCE_GRID
        cx, cy = well_center(well_id)
        k = int((WELL_R - 0.15) * 1e3 / g["pitch_um"])
        i, j = np.meshgrid(np.arange(-k, k + 1), np.arange(-k, k + 1))
        x, y = cx + i.ravel() * g["pitch_um"] * 1e-3, cy + j.ravel() * g["pitch_um"] * 1e-3
        keep = np.hypot(x - cx, y - cy) < WELL_R - 0.15
        n = int(keep.sum())
        _SAMPLES[key] = np.column_stack([x[keep], y[keep], np.full(n, g["dot_sigma_um"]), np.full(n, g["absorption"])])
    if key not in _SAMPLES:
        seed = int.from_bytes(hashlib.sha256(f"{barcode}/{well_id}".encode()).digest()[:8], "little")
        rng = np.random.default_rng(seed)
        cx, cy = well_center(well_id)
        n = int(OBJECTS_PER_MM2 * math.pi * (WELL_R - 0.15) ** 2)
        r = (WELL_R - 0.15) * np.sqrt(rng.random(n))
        a = rng.random(n) * 2 * math.pi
        x, y = cx + r * np.cos(a), cy + r * np.sin(a)
        size = rng.uniform(4.0, 9.0, n)                      # body sigma, um
        absorb = rng.uniform(0.12, 0.30, n)
        off = rng.normal(0.0, 0.25, (n, 2)) * size[:, None] * 1e-3
        body = np.column_stack([x, y, size, absorb])
        core = np.column_stack([x + off[:, 0], y + off[:, 1], 0.35 * size, rng.uniform(0.15, 0.30, n)])
        _SAMPLES[key] = np.vstack([body, core])
    return _SAMPLES[key]


def psf_sigma_um(na: float, defocus_um: float, pixel_um: float) -> float:
    diff = 0.21 * LAMBDA_UM / na
    geo = abs(defocus_um) * na / (2.0 * math.sqrt(1.0 - na * na))
    return math.sqrt(diff ** 2 + geo ** 2 + (0.5 * pixel_um) ** 2)


def form_image(*, plate_pos, plate_R, well_bottom_mm, barcode, focal_point, axis, ex, ey, na, pixel_um,
               led_level, exposure_ms, stray_e_per_ms=0.0, rng=None):
    """Raw 12-bit image (uint16, h x w) and the ground truth of what was imaged.

    plate_pos (m, world) and plate_R (3x3, world from plate) give the plate pose; the well-bottom plane is
    well_bottom_mm above the plate's underside. focal_point (m) and axis (unit, toward the sample) describe the
    indexed objective; ex / ey (unit, world) are the object-space directions of the image's +u / +v axes.
    """
    rng = rng or np.random.default_rng()
    w, h = SENSOR
    if plate_pos is None:                                # nothing above the objective: flat field
        return _expose(np.ones((h, w)), led_level, exposure_ms, stray_e_per_ms, rng), {
            "defocus_um": None, "imaged_uv_mm": None, "well": None, "offset_from_well_centre_mm": None,
            "psf_sigma_um": None}
    plate_pos, plate_R = np.asarray(plate_pos, float), np.asarray(plate_R, float)
    f, a = np.asarray(focal_point, float), np.asarray(axis, float)
    n = plate_R[:, 2]
    p0 = plate_pos + n * well_bottom_mm * 1e-3
    s = float(np.dot(p0 - f, n) / np.dot(a, n))        # along the axis from the focal point to the sample plane
    hit = f + s * a
    uv = plate_R.T @ (hit - plate_pos) * 1e3             # mm, plate frame
    defocus_um = s * 1e6                                 # + : sample above the focal plane
    # pixel grid in plate coordinates (mm)
    du, dv = (plate_R.T @ np.asarray(ex, float))[:2], (plate_R.T @ np.asarray(ey, float))[:2]
    pj = (np.arange(w) - w / 2 + 0.5) * pixel_um * 1e-3
    pi = (h / 2 - np.arange(h) - 0.5) * pixel_um * 1e-3
    U = uv[0] + pj[None, :] * du[0] + pi[:, None] * dv[0]
    V = uv[1] + pj[None, :] * du[1] + pi[:, None] * dv[1]
    sig = psf_sigma_um(na, defocus_um, pixel_um)
    T = np.ones((h, w))
    well, dist = nearest_well(uv[0], uv[1])
    if well is not None:
        objs = sample_objects(barcode or "", well)
        half = max(w, h) * pixel_um * 1e-3 * 0.75 + 0.06
        sel = objs[(np.abs(objs[:, 0] - uv[0]) < half) & (np.abs(objs[:, 1] - uv[1]) < half)]
        for x, y, sz, ab in sel:
            s2 = sz * sz + sig * sig
            amp = ab * sz * sz / s2
            rad = 4.0 * math.sqrt(s2) * 1e-3
            j0, j1, i0, i1 = _window(U, V, x, y, rad)
            if j1 <= j0 or i1 <= i0:
                continue
            d2 = ((U[i0:i1, j0:j1] - x) ** 2 + (V[i0:i1, j0:j1] - y) ** 2) * 1e6
            T[i0:i1, j0:j1] -= amp * np.exp(-d2 / (2 * s2))
        T = np.clip(T, 0.03, None)
        if dist + half > WELL_R - 4 * sig * 1e-3:        # the field reaches the well edge
            cx, cy = well_center(well)
            r = np.hypot(U - cx, V - cy)
            edge = 0.5 * (1 + _erf((WELL_R - r) * 1e3 / (math.sqrt(2) * max(sig, 1.0))))
            T = T * (OUTSIDE_T + (1 - OUTSIDE_T) * edge)
    else:
        T *= OUTSIDE_T
    adu = _expose(T, led_level, exposure_ms, stray_e_per_ms, rng)
    truth = {"defocus_um": round(defocus_um, 2), "imaged_uv_mm": [round(float(uv[0]), 4), round(float(uv[1]), 4)],
             "well": well, "offset_from_well_centre_mm": None if dist is None else round(dist, 4),
             "psf_sigma_um": round(sig, 3)}
    return adu, truth


def _expose(T, led_level, exposure_ms, stray_e_per_ms, rng):
    h, w = T.shape
    rr = ((np.arange(w)[None, :] - w / 2) ** 2 + (np.arange(h)[:, None] - h / 2) ** 2) / ((w / 2) ** 2 + (h / 2) ** 2)
    electrons = E_PER_MS * exposure_ms * led_level * T * (1 - VIGNETTE * rr) + stray_e_per_ms * exposure_ms
    electrons = rng.poisson(np.clip(electrons, 0, None)).astype(float) + rng.normal(0, READ_E, electrons.shape)
    return np.clip(np.round(electrons * ADC_MAX / FULL_WELL_E), 0, ADC_MAX).astype(np.uint16)


def _window(U, V, x, y, rad):
    """Index window of the pixel grid within rad of (x, y); U varies along columns, V along rows (axis-aligned)."""
    cols = np.nonzero(np.abs(U[0] - x) < rad)[0] if abs(U[0, -1] - U[0, 0]) > abs(U[-1, 0] - U[0, 0]) else None
    if cols is None:                                     # rotated more than 45 deg: no cheap window, use all
        return 0, U.shape[1], 0, U.shape[0]
    rows = np.nonzero(np.abs(V[:, 0] - y) < rad)[0]
    if len(cols) == 0 or len(rows) == 0:
        return 0, 0, 0, 0
    return cols[0], cols[-1] + 1, rows[0], rows[-1] + 1


def _erf(x):
    """Abramowitz & Stegun 7.1.26 (|error| < 1.5e-7), vectorised."""
    x = np.asarray(x, float)
    s, x = np.sign(x), np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * x)
    y = 1.0 - ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * np.exp(-x * x)
    return s * y


# ------------------------------------------------------------------ image metrics (what the controller computes)
def focus_score(img, gain_e_per_adu=FULL_WELL_E / ADC_MAX, read_noise_e=READ_E) -> float:
    """Normalised Brenner gradient on a 2x2-binned image, minus the sensor's expected noise contribution.

    The noise term comes from the calibrated sensor model (shot noise at the image mean + read noise), so a
    featureless or fully blurred field scores about 0 and structure in focus scores high. x1000 for readability.
    """
    a = np.asarray(img, float)
    h, w = a.shape[0] // 2 * 2, a.shape[1] // 2 * 2
    b = a[:h, :w].reshape(h // 2, 2, w // 2, 2).mean((1, 3))
    m = b.mean()
    if m <= 0:
        return 0.0
    g = ((b[:, 2:] - b[:, :-2]) ** 2).mean()
    noise = (m / gain_e_per_adu + (read_noise_e / gain_e_per_adu) ** 2) / 2.0   # E[(b_i - b_j)^2] for white noise
    return float((g - noise) / (m * m) * 1e3)


def histogram_stats(img) -> dict:
    a = np.asarray(img, float)
    return {"mean_fs": round(float(a.mean() / ADC_MAX), 4), "p01_fs": round(float(np.percentile(a, 1) / ADC_MAX), 4),
            "p999_fs": round(float(np.percentile(a, 99.9) / ADC_MAX), 4),
            "saturated_fraction": round(float((a >= ADC_MAX).mean()), 6)}
