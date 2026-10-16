"""Passive SBS plate nest on a fixed pedestal: the validated shuttle-nest interface (sbs_shuttle.py) without a shuttle.

Used by the R01/R02 handover nest (assets/hn) and the L21 reference / QC nests (assets/l21). Geometry in mm in the
caller's frame; the nest is centred at (cx, cy) with its seat plane at seat_z above the pedestal base (z = cz).
8 corner guides with 34 deg lead-ins, A1 key at (-X,+Y), finger reliefs at the long sides, 4 flush seat sensors,
AprilTag plate and datum pin on the pedestal. Static colliders (no rigid body).
"""

from dataclasses import dataclass

import numpy as np

from .sbs_shuttle import ShuttleNest
from .twin_cad import add_box_collider, add_convex_collider, box

KEEP = ("NestBase", "SeatSensor", "Guide", "A1Key", "TagPlate", "DatumPin")


@dataclass
class StaticNest:
    seat_z: float
    tag_id: int
    cx: float = 0.0
    cy: float = 0.0
    prefix: str = ""
    cz: float = 0.0                 # pedestal base height in the caller's frame
    flip: bool = False              # nest turned 180 deg about Z (A1 key at the caller's (+X,-Y))

    def __post_init__(self):
        self.nest = ShuttleNest(z0=self.seat_z - 34.0, y_ret=0.0, travel=0.0, tag_id=self.tag_id, tray_hd=62.0)
        self.ped = dict(x=(-112.0, 112.0), y=(-62.0, 62.0), z=(0.0, self.nest.tray_z1))

    def _move(self, wp):
        if self.flip:
            wp = wp.rotate((0, 0, 0), (0, 0, 1), 180)
        return wp.translate((self.cx, self.cy, self.cz))

    def parts(self):
        """{name: (workplane, material)} in the caller's frame."""
        p = {f"{self.prefix}{name}": (self._move(wp), mat) for name, wp, mat in self.nest.parts() if name.startswith(KEEP)}
        P = self.ped
        ped = box(0, 0, sum(P["z"]) / 2, P["x"][1] - P["x"][0], P["y"][1] - P["y"][0], P["z"][1] - P["z"][0])
        p[f"{self.prefix}Pedestal"] = (self._move(ped.edges("|Z").fillet(6).edges(">Z").fillet(1.0)), "AnodizedGraphite")
        return p

    def add_colliders(self, stage, parent, cmat, origin=(0, 0, 0)):
        """Static box + convex colliders under `parent`; returns the number added."""
        o = np.array(origin, float) - np.array([self.cx, self.cy, self.cz])
        n = 0
        boxes = [b for b in self.nest.collision_boxes() if b[0].startswith(("Nest", "DatumPin"))]
        boxes.append(("Pedestal", self.ped["x"], self.ped["y"], self.ped["z"]))
        for name, xs, ys, zs in boxes:
            if self.flip:
                xs, ys = (-xs[1], -xs[0]), (-ys[1], -ys[0])
            add_box_collider(stage, parent, f"{self.prefix}{name}", xs, ys, zs, o,
                             cmat["Peek" if name.startswith("Nest") else "Steel"], offsets=(0.0005, 0.0))
            n += 1
        for name, solid in self.nest.convex_colliders():
            if self.flip:
                solid = solid.rotate((0, 0, 0), (0, 0, 1), 180)
            add_convex_collider(stage, f"{parent}/{self.prefix}{name}", solid, o, cmat["Peek"])
            n += 1
        return n

    def tag(self):
        """(x, y, z, half size) of the AprilTag surface, mm in the caller's frame."""
        k = -1.0 if self.flip else 1.0
        return self.cx + k * self.nest.tag_c[0], self.cy + k * self.nest.tag_c[1], self.cz + self.nest.tray_z1 + 0.62, 10.0

    def seat_sensors(self):
        k = -1.0 if self.flip else 1.0
        return [(self.cx + k * x, self.cy + k * y, self.cz + self.seat_z - 1.0) for x, y in self.nest.seat_sensors]

    def transfer_attributes(self):
        return self.nest.transfer_attributes()
