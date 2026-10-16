"""Runtime controller for the L10 Automated CO2 Incubator twin: plate store + controlled environment.

Extends PlateStoreController (twin/l09_controller.py: present/stow, store/retrieve via the simulated handler,
identity at transfer, interlocks) with sdt/components/L10_Incubator.yaml:

  actions     incubate(plate_id, slot)  = store, refused while the environment is invalid
              release_plate(plate_id)   = retrieve; records the environment at release and starts the plate's
                                          time-outside-controlled-environment clock
  state       temperature_C, CO2_percent, humidity_percent, door_open_duration_s, alarm, environment_valid
  monitors    T / CO2 / RH within the experiment envelope, gate closes after transfer (gate_stuck_open)
  evidence    environment time series (1 Hz), door/gate events, alarms, per-plate exposure history

Environment model (ILLUSTRATIVE engineering assumptions, not validated incubator data; D016: no biological
parameters): each variable X exchanges with ambient through openings and is driven back to setpoint by a
rate-limited PI controller,
    dX/dt = -(k_closed + k_gate * f_gate + k_door * f_door) (X - X_amb) + u,
    u = clip((X_set - X) / tau + I, -r_max, r_max),   dI/dt = (X_set - X) / (tau * T_I)  (frozen while u saturates)
with f_gate / f_door the open fractions read from the simulated joints. I starts at the closed-chamber equilibrium
k_closed (X_set - X_amb). (A proportional-only controller settled below setpoint, e.g. T 36.75 C, RH 86.5 %, and an
episode waited 600 s for a recovery that could not happen, 2026-10-16.) The recorded values are the simulated
sensor readings ("nominal setpoint must not be assumed to equal culture exposure").
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .l09_controller import PlateStoreController, Result

AMBIENT = {"T": 22.0, "CO2": 0.04, "RH": 45.0}
SETPOINT = {"T": 37.0, "CO2": 5.0, "RH": 90.0}
# k in 1/s; tau in s; r_max in unit/s (assumptions)
MODEL = {
    "T":   dict(k_closed=1 / 7200, k_gate=1 / 1200, k_door=1 / 40, tau=120.0, r_max=0.02),
    "CO2": dict(k_closed=1 / 3600, k_gate=1 / 600, k_door=1 / 25, tau=120.0, r_max=0.03),
    "RH":  dict(k_closed=1 / 7200, k_gate=1 / 1500, k_door=1 / 60, tau=600.0, r_max=0.02),
}
T_I = 300.0  # s, integral time (assumption)
ENVELOPE = {"T": (36.5, 37.5), "CO2": (4.7, 5.3), "RH": (85.0, 100.0)}
ALARM_NAME = {"T": "temperature_excursion", "CO2": "CO2_excursion", "RH": "humidity_excursion"}


@dataclass
class L10Controller(PlateStoreController):
    gate_open_limit_s: float = 60.0
    env: dict = field(default_factory=lambda: dict(SETPOINT))
    envelope: dict = field(default_factory=lambda: dict(ENVELOPE))

    def __post_init__(self):
        super().__post_init__()
        self._integ = {k: m["k_closed"] * (SETPOINT[k] - AMBIENT[k]) for k, m in MODEL.items()}  # equilibrium
        self.alarms = set()
        self.door_open_total_s = 0.0
        self._gate_open_s = 0.0
        self.series = []
        self._next_sample = 0.0
        self.plates = {}      # plate_id -> exposure history while incubated
        self.released = {}    # plate_id -> release record (clock of time outside the controlled environment)
        self._inv_prev = list(self.inventory)

    # ------------------------------------------------------------------ contract actions
    def incubate(self, plate_id: str, slot: int, target_environment: dict | None = None) -> Result:
        if not self.environment_valid:
            return self._refuse("incubate", f"environment not valid ({sorted(self.alarms)})")
        if target_environment and any(abs(target_environment[k] - SETPOINT[k]) > 1e-6 for k in target_environment):
            return self._refuse("incubate", "target_environment differs from the running setpoint")
        return self.store(plate_id, slot)

    def release_plate(self, plate_id: str) -> Result:
        return self.retrieve(plate_id)

    @property
    def environment_valid(self) -> bool:
        return not (self.alarms & set(ALARM_NAME.values()))

    def environment_history(self, plate_id: str) -> dict:
        h = dict(self.plates.get(plate_id, {}))
        if plate_id in self.released:
            r = self.released[plate_id]
            h["release"] = r
            h["time_outside_controlled_environment_s"] = round(self.t - r["t"], 2)
        return h

    # ------------------------------------------------------------------ loop
    def update(self, dt=None):
        super().update(dt)
        dt = self.dt
        f_gate = min(1.0, max(0.0, self.q["gate"] / self.travel["gate"]))
        f_door = min(1.0, max(0.0, math.degrees(self.q["door"]) / 90.0))
        for k, m in MODEL.items():
            x = self.env[k]
            loss = (m["k_closed"] + m["k_gate"] * f_gate + m["k_door"] * f_door) * (x - AMBIENT[k])
            e = SETPOINT[k] - x
            u = e / m["tau"] + self._integ[k]
            ctrl = float(np.clip(u, -m["r_max"], m["r_max"]))
            if ctrl == u:                                   # anti-windup: integrate only when not saturated
                self._integ[k] += e / (m["tau"] * T_I) * dt
            self.env[k] = x + (ctrl - loss) * dt
        if f_door > 0.02 or f_gate > 0.02:
            self.door_open_total_s += dt
        self._gate_open_s = self._gate_open_s + dt if f_gate > 0.02 else 0.0
        self._alarm("gate_stuck_open", self._gate_open_s > self.gate_open_limit_s,
                    open_s=round(self._gate_open_s, 1))
        for k, (lo, hi) in self.envelope.items():
            self._alarm(ALARM_NAME[k], not (lo <= self.env[k] <= hi), value=round(self.env[k], 3))
        self._track_plates(dt)
        if self.t >= self._next_sample:
            self._next_sample += 1.0
            self.series.append((round(self.t, 2), round(self.env["T"], 3), round(self.env["CO2"], 3),
                                round(self.env["RH"], 2), round(f_gate, 2), round(f_door, 2)))
        self._env_outputs()

    def _alarm(self, name, active, **detail):
        if active and name not in self.alarms:
            self.alarms.add(name)
            self._log("alarm_raised", alarm=name, **detail)
        elif not active and name in self.alarms:
            self.alarms.discard(name)
            self._log("alarm_cleared", alarm=name, **detail)

    def _track_plates(self, dt):
        inv = list(self.inventory)
        for slot, (old, new) in enumerate(zip(self._inv_prev, inv)):
            if new and new != old:   # incubated
                self.released.pop(new, None)
                self.plates[new] = {"slot": slot, "incubated_at": round(self.t, 2), "time_stored_s": 0.0,
                                    "time_out_of_envelope_s": 0.0, "T_min": self.env["T"], "T_max": self.env["T"],
                                    "CO2_min": self.env["CO2"], "CO2_max": self.env["CO2"], "excursions": []}
            if old and old != new and old in self.unaccounted:   # inventory reconciled: it was never here
                self.plates.get(old, {})["unaccounted"] = self.unaccounted[old]
                self._log("plate_unaccounted", plate_id=old, **self.unaccounted[old])
            elif old and old != new:   # released
                rec = {"t": round(self.t, 2), "slot": slot, "environment": {k: round(v, 3) for k, v in self.env.items()},
                       "environment_valid": self.environment_valid}
                self.released[old] = rec
                self._log("release_record", plate_id=old, **rec)
        self._inv_prev = inv
        for pid, h in self.plates.items():
            if pid not in self.inventory:
                continue
            h["time_stored_s"] = round(h["time_stored_s"] + dt, 4)
            h["T_min"], h["T_max"] = min(h["T_min"], self.env["T"]), max(h["T_max"], self.env["T"])
            h["CO2_min"], h["CO2_max"] = min(h["CO2_min"], self.env["CO2"]), max(h["CO2_max"], self.env["CO2"])
            if not self.environment_valid:
                h["time_out_of_envelope_s"] = round(h["time_out_of_envelope_s"] + dt, 4)
                tags = sorted(self.alarms & set(ALARM_NAME.values()))
                if not h["excursions"] or h["excursions"][-1] != tags:
                    h["excursions"].append(tags)

    def _env_outputs(self):
        r = lambda v, n: round(v, n)  # noqa: E731
        self._write("state:temperature_C", r(self.env["T"], 2))
        self._write("state:CO2_percent", r(self.env["CO2"], 2))
        self._write("state:humidity_percent", r(self.env["RH"], 1))
        self._write("state:door_open_duration_s", r(self.door_open_total_s, 1))
        self._write("state:alarm", ",".join(sorted(self.alarms)) or "none")
        self._write("state:environment_valid", self.environment_valid)

    def _extra_red(self) -> bool:
        return bool(getattr(self, "alarms", None))
