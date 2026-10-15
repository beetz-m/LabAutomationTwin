"""Parametric robot-grade SBS shuttle nest (the validated H4 hand-off interface, reusable by L09/L10).

Geometry (mm, station frame, nest stowed): rail on the chamber floor z0 -> carriage -> slide beam -> tray ->
nest base (seat plane `seat_z`). The nest has:
  * 8 corner guides: 0.5 mm locating band for 3 mm, then a 6 x 9 mm lead-in (34 deg): +-6.5 mm capture,
    or +-4 mm combined with +-2 deg yaw (validated in scripts/test_h4_physics.py T6)
  * finger reliefs (x +-25 mm, 5 mm deep) at the middle of both long sides for a long-side robot grip;
    with `tine_channel=True` (L09) the relief becomes a full-length, full-depth channel through the nest base
    and the tray gets a 12 mm slot (x 14..26) along its length, so an internal handler's fork tine can pass
    under a seated plate along Y while its post drops through the slot to an arm below the tray
  * A1 orientation key, 4 flush seat-sensor windows, AprilTag 36h11 + conical datum pin on the tray
Moved from assets/h4/build_h4.py (2026-10-15); H4 output is unchanged by the move.
"""

from dataclasses import dataclass, field

import cadquery as cq

from .twin_cad import SBS, box, cyl

GUIDE_CL, GUIDE_LEAD, GUIDE_H, GUIDE_W, GUIDE_L = 0.5, 6.0, 12.0, 10.0, 14.0
A1_KEY = 2.8                   # A1 orientation key leg (the plate's A1 chamfer leg is 4.0)
SEAT_SENSORS = [(-52.0, 32.0), (52.0, 32.0), (-52.0, -32.0), (52.0, -32.0)]  # rel. nest centre
RELIEF_HX, RELIEF_DEPTH = 25.0, 5.0
NEST_W, NEST_D = 160.0, 116.0
TAG_CODE, TAG_PLATE = 20.0, 24.0
TRAY_SLOT_X = (14.0, 26.0)     # tine_channel only: slot through the tray for the handler's fork post


@dataclass
class ShuttleNest:
    z0: float                       # chamber floor (rail base)
    y_ret: float                    # nest centre y with the shuttle stowed
    travel: float                   # shuttle stroke toward -Y
    tag_id: int
    tray_hw: float = 112.0
    tray_hd: float = 62.0
    slide_l: float = 100.0          # slide beam length behind the tray (stays on the rail when presented)
    tag_c: tuple = (97.0, 0.0)      # rel. nest centre
    datum_c: tuple = (-96.0, 40.0)
    tine_channel: bool = False
    rail_y0: float = None           # rail front end (defaults to the tray front when stowed)
    seat_sensors: list = field(default_factory=lambda: list(SEAT_SENSORS))

    def __post_init__(self):
        self.rail_z1 = self.z0 + 10.0
        self.carr_z1 = self.rail_z1 + 6.0
        self.beam_z1 = self.carr_z1 + 6.0
        self.tray_z1 = self.beam_z1 + 6.0
        self.seat_z = self.tray_z1 + 6.0
        self.y_ext = self.y_ret - self.travel
        if self.rail_y0 is None:
            self.rail_y0 = self.y_ret - self.tray_hd

    # ------------------------------------------------------------------ geometry
    def guide_solids(self):
        hx, hy = SBS[0] / 2, SBS[1] / 2
        cl, ld, h, w, L = GUIDE_CL, GUIDE_LEAD, GUIDE_H, GUIDE_W, GUIDE_L
        prof = [(cl, 0.0), (cl + w, 0.0), (cl + w, h), (cl + ld, h), (cl, 3.0)]
        out = []
        for i, (sx, sy) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]):
            pts = [(sx * (hx + u), self.seat_z + z) for u, z in prof]  # short side: faces +-X, near the corner
            g = cq.Workplane("XZ").polyline(pts).close().extrude(L / 2, both=True)
            out.append((f"Guide{i}X", g.translate((0, self.y_ret + sy * (hy - L / 2), 0))))
            pts = [(sy * (hy + u), self.seat_z + z) for u, z in prof]  # long side: faces +-Y, near the corner
            g = cq.Workplane("YZ").polyline(pts).close().extrude(L / 2, both=True)
            out.append((f"Guide{i}Y", g.translate((sx * (hx - L / 2), self.y_ret, 0))))
        return out

    def a1_key(self):
        hx, hy = SBS[0] / 2, SBS[1] / 2
        return (cq.Workplane("XY").polyline([(-hx, hy), (-hx + A1_KEY, hy), (-hx, hy - A1_KEY)]).close()
                .extrude(3.0).translate((0, self.y_ret, self.seat_z)))

    def parts(self):
        """(name, solid, material) in the stowed pose (mm, station frame)."""
        ny, hy = self.y_ret, SBS[1] / 2
        rear = ny + self.tray_hd
        out = [
            ("Carriage", box(0, rear + self.slide_l - 25, (self.rail_z1 + self.carr_z1) / 2, 30, 40,
                             self.carr_z1 - self.rail_z1).edges("|Z").fillet(2), "SteelSatin"),
            ("SlideBeam", box(0, (ny - 40 + rear + self.slide_l) / 2, (self.carr_z1 + self.beam_z1) / 2, 30,
                              rear + self.slide_l - ny + 40, self.beam_z1 - self.carr_z1).edges("|Y").fillet(1),
             "Aluminium"),
            ("Tray", self._tray(), "Aluminium"),
        ]
        base = box(0, ny, (self.tray_z1 + self.seat_z) / 2, NEST_W, NEST_D, self.seat_z - self.tray_z1).edges(
            "|Z").fillet(3)
        if self.tine_channel:  # full-length, full-depth channel: reliefs + tine/post path in one cut
            base = base.cut(box(0, ny, (self.tray_z1 + self.seat_z) / 2, 2 * RELIEF_HX, NEST_D + 4,
                                self.seat_z - self.tray_z1 + 2))
        else:
            y0, y1 = hy - 3, NEST_D / 2 + 2
            for sy in (-1, 1):  # finger reliefs at the middle of the long sides
                base = base.cut(box(0, ny + sy * (y0 + y1) / 2, self.seat_z - RELIEF_DEPTH / 2 + 0.5, 2 * RELIEF_HX,
                                    y1 - y0, RELIEF_DEPTH + 1))
        for x, y in self.seat_sensors:
            base = base.cut(cyl(2.6, 1.2, (x, ny + y, self.seat_z - 1.0), (0, 0, 1)))
        out.append(("NestBase", base, "PeekNatural"))
        for i, (x, y) in enumerate(self.seat_sensors):
            out.append((f"SeatSensor{i}", cyl(2.4, 0.3, (x, ny + y, self.seat_z - 1.0), (0, 0, 1)), "SensorWindow"))
        for name, g in self.guide_solids():
            out.append((name, g, "PeekNatural"))
        out.append(("A1Key", self.a1_key(), "PeekNatural"))
        tx, ty = self.tag_c
        out.append(("TagPlate", box(tx, ny + ty, self.tray_z1 + 0.3, TAG_PLATE, TAG_PLATE, 0.6), "LabelWhite"))
        dx, dy = self.datum_c
        pin = cyl(3.0, 5.0, (dx, ny + dy, self.tray_z1), (0, 0, 1)).union(
            cq.Workplane("XY").add(cq.Solid.makeCone(3.0, 0.6, 3.0, cq.Vector(dx, ny + dy, self.tray_z1 + 5.0))))
        out.append(("DatumPin", pin, "SteelSatin"))
        return out

    def _tray(self):
        t = box(0, self.y_ret, (self.beam_z1 + self.tray_z1) / 2, 2 * self.tray_hw, 2 * self.tray_hd,
                self.tray_z1 - self.beam_z1).edges("|Z").fillet(4).edges(">Z").fillet(0.8)
        if self.tine_channel:
            x0, x1 = TRAY_SLOT_X
            t = t.cut(box((x0 + x1) / 2, self.y_ret, (self.beam_z1 + self.tray_z1) / 2, x1 - x0, 2 * self.tray_hd + 2,
                          self.tray_z1 - self.beam_z1 + 2))
        return t

    def convex_colliders(self):
        return self.guide_solids() + [("A1Key", self.a1_key())]

    def collision_boxes(self):
        ny, hy, hw = self.y_ret, SBS[1] / 2 - 3, NEST_W / 2
        rear = ny + self.tray_hd
        tz, ty = (self.beam_z1, self.tray_z1), (ny - self.tray_hd, ny + self.tray_hd)
        if self.tine_channel:
            boxes = [("TrayL", (-self.tray_hw, TRAY_SLOT_X[0]), ty, tz), ("TrayR", (TRAY_SLOT_X[1], self.tray_hw), ty, tz)]
        else:
            boxes = [("Tray", (-self.tray_hw, self.tray_hw), ty, tz)]
        boxes += [
            ("SlideBeam", (-15, 15), (ny - 40, rear + self.slide_l), (self.carr_z1, self.beam_z1)),
            ("DatumPin", (self.datum_c[0] - 3, self.datum_c[0] + 3), (ny + self.datum_c[1] - 3, ny + self.datum_c[1] + 3),
             (self.tray_z1, self.tray_z1 + 8)),
        ]
        if self.tine_channel:
            ys = (ny - NEST_D / 2, ny + NEST_D / 2)
            boxes += [("NestCoreL", (-hw, -RELIEF_HX), ys, (self.tray_z1, self.seat_z)),
                      ("NestCoreR", (RELIEF_HX, hw), ys, (self.tray_z1, self.seat_z))]
        else:
            boxes.append(("NestCore", (-hw, hw), (ny - hy, ny + hy), (self.tray_z1, self.seat_z)))
            for sy, tag in ((-1, "Front"), (1, "Back")):  # long-side strips around the finger reliefs
                ys = tuple(sorted((ny + sy * hy, ny + sy * NEST_D / 2)))
                boxes += [(f"NestStrip{tag}L", (-hw, -RELIEF_HX), ys, (self.tray_z1, self.seat_z)),
                          (f"NestStrip{tag}R", (RELIEF_HX, hw), ys, (self.tray_z1, self.seat_z)),
                          (f"NestRelief{tag}", (-RELIEF_HX, RELIEF_HX), ys, (self.tray_z1, self.seat_z - RELIEF_DEPTH))]
        return boxes

    def rail_part(self, rear_limit):
        """Shuttle rail (station body), from the front to `rear_limit` (mm y)."""
        return box(0, (self.rail_y0 + rear_limit) / 2, (self.z0 + self.rail_z1) / 2, 16, rear_limit - self.rail_y0,
                   self.rail_z1 - self.z0).edges("|Y").fillet(1)

    def transfer_attributes(self):
        return [
            ("sdt:approach", "string", "top-down; gripper fingers on the plate LONG sides (pinch along +-Y), "
                                       "finger reliefs +-25 mm about x=0, 5 mm deep"),
            ("sdt:captureRange_mm", "double", GUIDE_CL + GUIDE_LEAD),
            ("sdt:seatClearance_mm", "double", GUIDE_CL),
            ("sdt:orientationKey", "string", "A1 key at (-X,+Y): a plate rotated 180 deg will not seat (seat sensors)"),
            ("sdt:registration", "string", f"Shuttle/registration_tag (AprilTag 36h11 #{self.tag_id}, {TAG_CODE:g} mm) "
                                           f"and Shuttle/registration_datum"),
        ]
