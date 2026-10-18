"""Bright-field appearance of the simulated culture for L17's image formation, and the SDT's image analysis.

Appearance (simulator side, reads the hidden CultureWorld): an organoid in a well is rendered for twin/l17_optics.py
as absorbing Gaussian objects (the optics module blurs Gaussians exactly): a body filling the projected disc with
thickness-weighted absorption, a refractive dark rim, a brighter lumen when healthy, a dark necrotic core with optical
density from injury, loose debris around a dying organoid, and a faint haze when the medium is contaminated.
ILLUSTRATIVE appearance model (twin assumption, D016): it encodes Cell 01's morphology mapping (radius 180 + 90 V um)
and the twin's illustrative core-OD / debris mappings (twin/culture/model.py), nothing else.

Analysis (SDT side, sees only the raw image and L17's *applied calibration record*): flat-field normalisation,
smoothing, threshold, largest component -> equivalent radius (um, from the calibrated pixel size, so a wrong
calibration biases the measurement exactly as it would in a real lab), core optical density, debris count, haze.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np

from twin.l17_optics import well_center


def organoid_objects(barcode: str, well_id: str, look: dict, t_key: float = 0.0):
    """Gaussian objects (x_mm, y_mm, sigma_um, absorption) for one well's organoid at its current state."""
    seed = int.from_bytes(hashlib.sha256(f"{barcode}/{well_id}/organoid".encode()).digest()[:8], "little")
    rng = np.random.default_rng(seed)                       # stable shape per well; state changes its parameters
    cx, cy = well_center(well_id)
    off = rng.normal(0, 0.035, 2)                           # organoid not exactly centred (mm)
    cx, cy = cx + off[0], cy + off[1]
    R = look["radius_um"]
    V = look["viability"]
    objs = []
    # body: hex-ish fill, thickness-weighted (chord length of a sphere), slightly lobed outline
    sig = 16.0
    step = 1.25 * sig
    lobes = rng.normal(0, 0.035, 6)
    for ix in np.arange(-R, R + step, step):
        for iy in np.arange(-R, R + step, step):
            r = math.hypot(ix, iy)
            a = math.atan2(iy, ix)
            Rl = R * (1 + sum(lobes[k] * math.cos((k + 2) * a + k) for k in range(6)) / 2)
            if r > Rl:
                continue
            chord = math.sqrt(max(0.0, 1 - (r / Rl) ** 2))
            lumen = (0.55 * V) * math.exp(-(r / (0.55 * Rl)) ** 2)    # healthy cystic organoids: brighter centre
            amp = 0.055 * (0.35 + 0.65 * chord) * (1 - lumen)
            jitter = rng.normal(0, 3.0, 2)
            objs.append((cx + (ix + jitter[0]) * 1e-3, cy + (iy + jitter[1]) * 1e-3, sig, amp))
    # dark refractive rim
    n_rim = int(2 * math.pi * R / 10)
    for k in range(n_rim):
        a = 2 * math.pi * k / n_rim
        Rl = R * (1 + sum(lobes[j] * math.cos((j + 2) * a + j) for j in range(6)) / 2)
        objs.append((cx + 0.97 * Rl * math.cos(a) * 1e-3, cy + 0.97 * Rl * math.sin(a) * 1e-3, 7.0, 0.16))
    # necrotic core: OD -> absorption of a cluster of Gaussians in the inner 40 %
    od = look["core_od"]
    n_core = 40
    for _ in range(n_core):
        r = 0.38 * R * math.sqrt(rng.random())
        a = rng.random() * 2 * math.pi
        objs.append((cx + r * math.cos(a) * 1e-3, cy + r * math.sin(a) * 1e-3, 22.0, 0.10 * od))
    # debris around a dying organoid
    for _ in range(look["debris"]):
        r = R * (1.05 + 0.6 * rng.random())
        a = rng.random() * 2 * math.pi
        objs.append((cx + r * math.cos(a) * 1e-3, cy + r * math.sin(a) * 1e-3, rng.uniform(3.0, 7.0),
                     rng.uniform(0.25, 0.5)))
    # contamination haze: many faint small particles over the well bottom
    # (a turbid, growing population of small particles; only those near the imaged field are rendered by the optics)
    nh = int(40000 * look.get("turbidity", 0.0))
    if nh:
        hr = np.random.default_rng(seed + 1)
        rr = 3.2 * np.sqrt(hr.random(nh))
        aa = hr.random(nh) * 2 * math.pi
        hz = np.column_stack([cx - off[0] + rr * np.cos(aa), cy - off[1] + rr * np.sin(aa), np.full(nh, 1.6),
                              hr.uniform(0.15, 0.35, nh)])
        return np.vstack([np.array(objs, float), hz])
    return np.array(objs, float)


class CultureSampleProvider:
    """Plug for twin.l17_optics.SAMPLE_PROVIDER: returns the culture's objects for wells of the culture plate."""

    def __init__(self, world, barcodes):
        self.world, self.barcodes = world, set(barcodes)

    def __call__(self, barcode, well_id):
        if barcode not in self.barcodes or well_id not in self.world.wells:
            return None
        return organoid_objects(barcode, well_id, self.world.appearance(well_id))


# ------------------------------------------------------------------------------------------- SDT image analysis
def analyse(img, pixel_um, well_id=None):
    """Morphology features from a raw bright-field image and the CALIBRATED pixel size (um/px)."""
    from scipy import ndimage as ndi
    a = img.astype(float)
    bg = np.percentile(a, 97)                                # clear medium (flat field ~ the brightest pixels)
    T = ndi.gaussian_filter(a / max(bg, 1.0), 2.0)
    mask = T < 0.88
    mask = ndi.binary_opening(mask, iterations=2)
    lab, n = ndi.label(mask)
    if n == 0:
        return dict(found=False, radius_um=None, core_od=None, debris=0, haze=float(np.std(T)))
    sizes = ndi.sum(mask, lab, range(1, n + 1))
    k = int(np.argmax(sizes)) + 1
    body = ndi.binary_fill_holes(lab == k)
    area_px = float(body.sum())
    radius = math.sqrt(area_px / math.pi) * pixel_um
    cy, cx = ndi.center_of_mass(body)
    yy, xx = np.indices(T.shape)
    rr = np.hypot(yy - cy, xx - cx) * pixel_um
    core = body & (rr < 0.30 * radius)
    core_od = float(-np.log10(np.clip(np.median(T[core]), 1e-3, None))) if core.any() else None
    # debris: small dark blobs outside the body
    small = (ndi.gaussian_filter(a / max(bg, 1.0), 1.0) < 0.80) & ~ndi.binary_dilation(body, iterations=6)
    dl, dn = ndi.label(small)
    ds = ndi.sum(small, dl, range(1, dn + 1)) if dn else np.array([])
    debris = int(np.sum((ds >= 6) & (ds <= 120)))
    edge = bool(body[0].any() or body[-1].any() or body[:, 0].any() or body[:, -1].any())
    hp = a / max(bg, 1.0) - ndi.gaussian_filter(a / max(bg, 1.0), 6.0)      # fine texture (vignetting removed)
    clear = hp[~ndi.binary_dilation(body | small, iterations=25)]
    return dict(found=True, radius_um=round(radius, 2), core_od=None if core_od is None else round(core_od, 4),
                debris=debris, haze=round(float(np.std(clear)), 5), touches_edge=edge,
                centre_px=[round(cx, 1), round(cy, 1)], area_px=int(area_px))
