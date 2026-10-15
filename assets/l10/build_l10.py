"""Build the L10 Automated CO2 Incubator asset: parametric CAD -> STEP + layered, articulated OpenUSD.

Run with the CAD environment:  env_cad/bin/python assets/l10/build_l10.py

Project-owned STX44-class design (Cell 01 baseline: LiCONiC STX44-SA family). Overall figures follow a
public reseller listing and are UNVERIFIED: 740 W x 850 D x 1470 H mm, 88 kg, 44 plates, transfer height
200 mm (other listings disagree; LiCONiC's own CAD, offered publicly without stated terms, was not
downloaded). Every dimension is a parameter: replace them when the product CAD is acquired.

Mechanism: the shared plate store (assets/common/plate_store.py; validated on L09): shuttle nest presented
through a motorised gate, one 44-slot cassette (24 mm pitch, the minimum the fork clearances allow), lift +
fork handler, barcode reader, slot occupancy rays. L10 adds an insulated chamber (60 mm walls), a solid
insulated service door with an inner glass door, environment probes (T, CO2, RH), a circulation fan, a water
pan, a front display, and the environment state of sdt/components/L10_Incubator.yaml. The environment
dynamics (door/gate losses, recovery) live in twin/l10_controller.py and are illustrative assumptions.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from common.plate_store import StoreDesign  # noqa: E402
from common.twin_cad import SBS, box, cyl, rrect, to_front  # noqa: E402
from pxr import Sdf  # noqa: E402

S, Db, Bo = Sdf.ValueTypeNames.String, Sdf.ValueTypeNames.Double, Sdf.ValueTypeNames.Bool
PROBES = {"temperature": (-170.0, 260.0, 900.0), "co2": (-170.0, 260.0, 840.0), "humidity": (-170.0, 260.0, 780.0)}


class L10Design(StoreDesign):
    def extra_parts(self, p):
        XI, YB = self.XI, self.YB
        # front touchscreen (environment readout) and a CO2 inlet port at the back
        p["Display"] = (to_front(rrect(220, 130, 8, 6), -170, 1150, self.YF), "PlasticBlack", "Housing")
        p["DisplayGlass"] = (to_front(rrect(196, 110, 6, 1), -170, 1150, self.YF - 6), "DisplayLit", "Housing")
        p["CO2Inlet"] = (cyl(9, 30, (220, YB, 1200), (0, 1, 0)).faces(">Y").edges().fillet(2), "SteelSatin", "Housing")
        # interior: circulation fan on the back wall, water pan on the floor, environment probes
        p["FanHousing"] = (box(-150, YB - self.wall - 25, 1100, 180, 50, 180).edges("|Y").fillet(8), "SteelSatin",
                           "Interior")
        p["FanGrille"] = (cyl(70, 4, (-150, YB - self.wall - 52, 1100), (0, -1, 0)), "PlasticBlack", "Interior")
        p["WaterPan"] = (box(-150, YB - self.wall - 140, self.CZ0 + 25, 260, 220, 50).faces(">Z").shell(-2),
                         "SteelSatin", "Interior")
        for name, (x, y, z) in PROBES.items():
            p[f"Probe_{name}"] = (cyl(6, 70, (x, y + 70, z), (0, -1, 0)), "SteelSatin", "Interior")
        # inner glass door behind the service door (static), over the cassette opening
        dy, dz = self.door_y, self.door_z
        glass = rrect(dy[1] - dy[0] - 6, dz[1] - dz[0] - 6, 4, 4).rotate((0, 0, 0), (1, 0, 0), 90).rotate(
            (0, 0, 0), (0, 0, 1), 90).translate((XI + 2, (dy[0] + dy[1]) / 2, (dz[0] + dz[1]) / 2))
        p["InnerGlassDoor"] = (glass, "Polycarbonate", "Housing")

    def extra_colliders(self, body):
        body.append(("FanHousing", (-240, -60), (self.YB - self.wall - 50, self.YB - self.wall), (1010, 1190)))
        body.append(("WaterPan", (-280, -20), (self.YB - self.wall - 250, self.YB - self.wall - 30),
                     (self.CZ0, self.CZ0 + 50)))

    def extra_semantics(self, sem, frame):
        frame("gate_frame", (0, self.GATE["y"], self.GATE["z0"]),
              "Transfer gate plane at the opening sill; joint GateSlide, +q opens (up)")
        for name, pos in PROBES.items():
            frame(f"sensors/{name}", pos, f"{name} probe tip (chamber air)")


DESIGN = L10Design(
    name="L10_Incubator", file_prefix="l10", here=HERE, generator="assets/l10/build_l10.py",
    label="L10  CO2 INCUBATOR", tag_id=10,
    z0=10.0, w=740.0, d=850.0, h=1470.0, wall=60.0, base_h=156.0,     # seat = 200 mm (listed transfer height)
    # nest stowed far enough behind the gate that the fork post (y_ret - 74) clears the gate inside the 60 mm wall
    # (y_ret = -290 overlapped it; found by tools/check_store_clearance.py); stroke keeps the tray clear when presented
    y_ret=-270.0, travel=245.0, slide_l=150.0, rail_front_gap=70.0,
    n_slots=44, pitch=24.0, ledge0=280.0, stroke=140.0, park_tine_z=245.0,
    gate_z1=240.0, gate_travel=90.0, gate_x=125.0,
    door_y=(-265.0, -35.0), door_z=(240.0, 1380.0), door_window=False,
    front_panel=None, label_z=1320.0, stack_light_xy=(300.0, 330.0),
    masses={"Body": 88.0, "Gate": 0.4, "Shuttle": 0.9, "Lift": 1.5, "Fork": 0.35, "ServiceDoor": 6.0},
    component_id="L10", canonical_name="L10 Automated CO2 Incubator", contract="sdt/components/L10_Incubator.yaml",
    capabilities=("incubate_plate", "maintain_environment", "store_plate", "release_plate", "report_environment",
                  "raise_excursion_alarm"),
    design_basis="project-owned STX44-class design; overall figures from an unverified reseller listing "
                 "(740x850x1470 mm, 88 kg, 44 plates, 200 mm transfer height); not a product model",
    frame_names={"transfer": "transfer_station", "load": "load_frame", "slots": "cassette_slots",
                 "door": "service_door"},
    extra_attributes=[
        ("state:temperature_C", Db, 37.0), ("state:CO2_percent", Db, 5.0), ("state:humidity_percent", Db, 90.0),
        ("state:door_open_duration_s", Db, 0.0), ("state:alarm", S, "none"), ("state:environment_valid", Bo, True),
        ("env:setpoint", Sdf.ValueTypeNames.DoubleArray, [37.0, 5.0, 90.0]),
        ("env:envelope", S, "T 37+-0.5 C; CO2 5+-0.3 %; RH >= 85 % (experiment-specific default, configurable)"),
        ("env:model", S, "lumped first-order exchange with ambient through gate/door + rate-limited recovery; "
                         "parameters are illustrative engineering assumptions, not validated incubator data"),
    ],
)
assert DESIGN.SEAT_Z == 200.0, DESIGN.SEAT_Z
assert DESIGN.pitch >= SBS[2] + 9.65

if __name__ == "__main__":
    from common import twin_cad as tc
    tc.PBR["DisplayLit"] = ((0.05, 0.12, 0.10), 0.2, 0.0, {"emissive": ((0.35, 0.9, 0.7), 250.0)})
    DESIGN.build()
