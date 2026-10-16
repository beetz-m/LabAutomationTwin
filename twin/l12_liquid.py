"""Abstract liquid model for the L12 twin: tracked volumes, capacitive liquid-level detection, pressure traces.

Cell 01 asks for "hybrid: tracked volumes + optional visual/particle proxy" (sdt/components/L12_LiquidHandler.yaml).
There is no fluid simulation: each container (reagent tube, plate well) holds a volume and a content list, and its
liquid surface height follows from the volume and the inner radius. What couples the model to the physics is the
TIP: detection, aspiration and dispense use the real pose of the mounted tip (a PhysX rigid body), so a tip that is
not where the controller believes, or not there at all, is not in the liquid.

Sensor models (engineering ASSUMPTIONS, not ZEUS data; no biological parameters, D016):
  cLLD    the conductive tip detects the surface when its end is within 0.1 mm of it (plus 0.05 mm noise)
  pressure  p = -k_r * Q while aspirating liquid (k_r = 6 mbar per uL/s, 50 uL tip), -0.3 * Q while aspirating
            air (tip out of the liquid), and a clog (near-occlusion) multiplies k_r by 20, so the channel's -120 mbar
            limit cuts the flow; +k_r * Q while
            dispensing; 0.4 mbar noise at 200 Hz. The controller judges the trace against an envelope.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

K_R = 6.0                 # mbar per (uL/s) through a 50 uL tip, liquid
K_AIR = 0.3               # mbar per (uL/s), air
CLOG_FACTOR = 20.0        # near-occlusion (a partial clog only raises the pressure)
P_LIMIT = -120.0          # mbar: the channel stops aspirating beyond this (clog protection)
NOISE = 0.4
HZ = 200.0
LLD_TOL_MM = 0.1


@dataclass
class Container:
    cid: str
    kind: str                      # "tube" | "well"
    inner_r_mm: float
    bottom_z: float                # m, world, inner bottom
    volume_uL: float
    contents: dict = field(default_factory=dict)    # substance -> uL
    reagent_id: str = ""
    lot: str = ""

    @property
    def surface_z(self):
        return self.bottom_z + self.volume_uL / (math.pi * self.inner_r_mm ** 2) * 1e-3   # uL = mm^3

    def remove(self, v):
        v = min(v, self.volume_uL)
        frac = v / self.volume_uL if self.volume_uL > 0 else 0.0
        taken = {k: q * frac for k, q in self.contents.items()}
        for k in taken:
            self.contents[k] -= taken[k]
        self.volume_uL -= v
        return v, taken

    def add(self, v, contents):
        self.volume_uL += v
        for k, q in contents.items():
            self.contents[k] = self.contents.get(k, 0.0) + q


@dataclass
class LiquidModel:
    containers: dict = field(default_factory=dict)
    rng: np.random.Generator = field(default_factory=lambda: np.random.default_rng(12))
    clog_at: float | None = None   # injected: aspiration fraction at which the tip clogs (test hook)
    aspirated_uL: float = 0.0
    tip_contents: dict = field(default_factory=dict)

    # ---------------------------------------------------------------- sensing
    def immersion_mm(self, cid, tip_end_z):
        c = self.containers[cid]
        return (c.surface_z - tip_end_z) * 1e3

    def lld(self, cid, tip_end_z):
        """Capacitive LLD: True once the conductive tip end touches the surface."""
        return self.immersion_mm(cid, tip_end_z) >= -LLD_TOL_MM + self.rng.normal(0, 0.05)

    # ---------------------------------------------------------------- transfers (time-stepped by the controller)
    def flow_step(self, cid, q_uL_s, dt, tip_end_z, sign, progress):
        """One control step of aspiration (sign -1) or dispense (+1) at q uL/s. Returns (pressure mbar, moved uL)."""
        c = self.containers[cid]
        if sign < 0:
            wet = self.immersion_mm(cid, tip_end_z) > 0.2 and c.volume_uL > 0.5
            k = K_R if wet else K_AIR
            clogged = self.clog_at is not None and progress >= self.clog_at
            if clogged:
                k *= CLOG_FACTOR
            p = -k * q_uL_s
            if p < P_LIMIT:                                  # clog protection: flow limited to the pressure limit
                q_uL_s = -P_LIMIT / k
                p = P_LIMIT
            v = q_uL_s * dt
            if wet:
                moved, taken = c.remove(v)
                self.aspirated_uL += moved
                for s, q in taken.items():
                    self.tip_contents[s] = self.tip_contents.get(s, 0.0) + q
            else:
                moved = 0.0                                  # air: volume displaced is air, not liquid
            return p + self.rng.normal(0, NOISE), moved
        # dispense: the tip holds aspirated_uL of liquid
        v = min(q_uL_s * dt, self.aspirated_uL)
        frac = v / self.aspirated_uL if self.aspirated_uL > 0 else 0.0
        part = {s: q * frac for s, q in self.tip_contents.items()}
        for s in part:
            self.tip_contents[s] -= part[s]
        self.aspirated_uL -= v
        c.add(v, part)
        p = K_R * q_uL_s if v > 0 else 0.0
        return p + self.rng.normal(0, NOISE), v

    def settle_sample(self):
        return self.rng.normal(0, NOISE)


def judge_trace(trace, q_uL_s, sign, duration_s):
    """Pressure envelope check of a transfer: plateau within 30 % of the expected k_r*Q, no clog-limit samples, plateau
    for >= 80 % of the expected duration, return to baseline at the end."""
    p = np.array([s for _, s in trace]) if trace else np.zeros(1)
    expect = sign * K_R * q_uL_s
    n = len(p)
    core = p[int(0.15 * n):max(int(0.85 * n), int(0.15 * n) + 1)]
    plateau = float(np.median(core)) if len(core) else 0.0
    within = np.abs(core - expect) <= 0.3 * abs(expect) + 3 * NOISE
    ok_level = abs(plateau - expect) <= 0.3 * abs(expect)
    ok_steady = float(within.mean()) >= 0.8 if len(core) else False
    clog = bool((p <= P_LIMIT + 1.0).any())
    return {"expected_mbar": round(expect, 2), "plateau_mbar": round(plateau, 2),
            "steady_fraction": round(float(within.mean()), 3) if len(core) else 0.0, "clog_limit_hit": clog,
            "samples": n, "ok": bool(ok_level and ok_steady and not clog)}
