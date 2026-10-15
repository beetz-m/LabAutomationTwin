"""Parametric robot-loaded SBS plate store: the shared builder behind L09 (plate hotel) and L10 (incubator).

Generalised from assets/l09/build_l09.py (2026-10-15); with the defaults it reproduces L09. A device script
creates a StoreDesign (dimensions, slots, styling) and may override the hooks extra_parts / extra_colliders /
extra_semantics / extra_visual. See assets/l09/README.md for the design rationale (validated mechanism):

  * robot interface: the shared SBS shuttle nest (sbs_shuttle.py), presented through a motorised gate
  * one cassette column of addressable slots; plates rest on ledges under their short ends
  * internal handler: lift (Z) + fork (Y) whose 2 mm tine slides under a plate (between the ledges or through the
    nest's tine channel); a post at the tine's front end drops through the tray slot to an arm under the tray
  * barcode reader at the stowed nest, per-slot occupancy rays, nest seat sensors, service door with interlock

Geometry rules learned on L09 (keep them when changing parameters; tools/check_store_clearance.py sweeps them):
  * fork stroke (YC - YN) > tray depth + post width, so the post is in front of the tray at q_fork = 0 and behind
    it at full stroke; TINE_Y0 places the post 2 mm in front of the tray at q = 0
  * servo axes stiff enough that gravity sag stays well inside the controller's 0.4 mm move tolerance
  * pitch >= plate height + 9.65 mm (carry 4 mm above the ledge, tine 3 mm below it, 3 mm ledges)
"""

import os
from dataclasses import dataclass, field

import cadquery as cq
import numpy as np
from pxr import Gf, Kind, Sdf, Usd, UsdGeom, UsdLux, UsdPhysics

from . import twin_cad as tc
from .sbs_shuttle import ShuttleNest
from .twin_cad import (B, F, MM, SBS, _drive, _joint, add_box_collider, add_convex_collider, bind, box, cyl,
                       define_contact_materials, define_materials, mm3, rrect, to_front, write_mesh)

EXTRA_PBR = {
    "PowderWhite": ((0.86, 0.87, 0.87), 0.42, 0.0, {}),
    "LensAmber": ((0.6, 0.35, 0.02), 0.15, 0.0, {"emissive": ((1.0, 0.55, 0.05), 0.0)}),
}


@dataclass
class StoreDesign:
    name: str = "L09_PlateHotel"         # root prim
    file_prefix: str = "l09"
    here: str = ""                       # output directory
    generator: str = "assets/l09/build_l09.py"
    label: str = "L09  PLATE HOTEL"
    tag_id: int = 9
    # body (mm)
    z0: float = 8.0                      # foot height
    w: float = 400.0
    d: float = 520.0
    h: float = 700.0
    wall: float = 3.0
    base_h: float = 30.0                 # chamber floor (rail base) = z0 + base_h
    # nest / shuttle
    y_ret: float = -150.0
    travel: float = 200.0
    slide_l: float = 110.0
    rail_front_gap: float = 12.0         # rail starts this far inside the front face
    # cassette
    n_slots: int = 14
    pitch: float = 30.0
    ledge0: float = 150.0
    stroke: float = 140.0                # YC - YN
    park_tine_z: float = 125.0
    gate_z1: float = 112.0
    gate_travel: float = 90.0
    gate_x: float = 125.0
    door_y: tuple = (-95.0, 45.0)        # service door on the +X face
    door_z: tuple = (120.0, 600.0)
    door_window: bool = True
    shell_material: str = "PowderWhite"
    front_panel: tuple = (330.0, 300.0)  # (z centre, height) of the dark front panel; None to omit
    label_z: float = 520.0
    stack_light_xy: tuple = None         # default: (XS - 50, YB - 60)
    masses: dict = field(default_factory=lambda: {"Body": 30.0, "Gate": 0.4, "Shuttle": 0.9, "Lift": 1.2,
                                                  "Fork": 0.25, "ServiceDoor": 1.5})
    extra_attributes: list = field(default_factory=list)   # (name, sdf type, value) on the root prim
    capabilities: tuple = ("buffer_plate", "store_plate", "retrieve_plate", "report_inventory", "reserve_slot",
                           "verify_identity")
    component_id: str = "L09"
    canonical_name: str = "L09 Automated Plate Hotel"
    contract: str = "sdt/components/L09_PlateHotel.yaml"
    design_basis: str = "project-owned LPE220-class design (LiCONiC CAD to be requested); not a product model"
    # names of the Cell 01 binding frames (L09: transfer_nest/load_frame/slot_frames/service_door_frame)
    frame_names: dict = field(default_factory=lambda: {"transfer": "transfer_nest", "load": "load_frame",
                                                       "slots": "slot_frames", "door": "service_door_frame"})

    def __post_init__(self):
        self.YF, self.YB, self.XS = -self.d / 2, self.d / 2, self.w / 2
        self.XI = self.XS - self.wall                            # interior wall planes
        self.CZ0 = self.z0 + self.base_h
        self.NEST = ShuttleNest(z0=self.CZ0, y_ret=self.y_ret, travel=self.travel, tag_id=self.tag_id,
                                slide_l=self.slide_l, tine_channel=True, rail_y0=self.YF + self.rail_front_gap)
        self.YN = self.NEST.y_ret
        self.YC = self.YN + self.stroke
        self.SEAT_Z = self.NEST.seat_z
        self.TINE_HX, self.TINE_Y0, self.TINE_Y1, self.TINE_T = 20.0, -64.0, 55.0, 2.0
        self.POST_X = (16.0, 24.0)
        self.ARM_DZ = (-28.0, -20.0)
        self.TINE_REF_Z = self.SEAT_Z - 1.5
        self.FORK_TRAVEL = self.stroke
        self.LIFT_MAX = self.ledge0 + (self.n_slots - 1) * self.pitch + 12 - self.TINE_REF_Z
        self.PARK = (self.park_tine_z - self.TINE_REF_Z, 0.0)
        self.GATE = dict(x=self.gate_x, z0=self.CZ0, z1=self.gate_z1, y=self.YF + self.wall + 3, t=6.0,
                         travel=self.gate_travel)
        self.READER = (-102.0, self.YN, self.SEAT_Z + 10.0)
        self.SLOT_SENSE_Y = self.YC + 60.0
        self.LEDGE_X0, self.LEDGE_X1, self.LEDGE_T = 57.0, 72.0, 3.0
        self.CASS_Z = (self.ledge0 - 20, self.ledge0 + (self.n_slots - 1) * self.pitch + 40)
        self.ARM_X1 = self.XI - 57.0                             # arm end / slider (L09: 140)
        self.LINKS = {
            "Body": ("Body", (0, 0, 0), (0, 0, 0)),
            "Gate": ("Gate", (0, self.GATE["y"], 0), (0, self.GATE["y"], 0)),
            "Shuttle": ("Shuttle", (0, self.YN, 0), (0, self.YN, 0)),
            "Lift": ("Lift", (0, 0, self.TINE_REF_Z), (0, 0, self.TINE_REF_Z + self.PARK[0])),
            "Fork": ("Lift/Fork", (0, self.YN, self.TINE_REF_Z), (0, self.YN + self.PARK[1], 0)),
            "ServiceDoor": ("ServiceDoor", (self.XS, self.door_y[1], 0), (self.XS, self.door_y[1], 0)),
        }
        self.GROUP_LINK = {"Housing": "Body", "Interior": "Body", "Cassette": "Body", "StatusLight": "Body",
                           "Gate": "Gate", "Shuttle": "Shuttle", "Lift": "Lift", "Fork": "Fork",
                           "ServiceDoor": "ServiceDoor"}
        self.ROOT = f"/{self.name}"
        assert self.pitch >= SBS[2] + 9.65, "slot pitch too small for the fork clearances"
        assert self.stroke >= 2 * self.NEST.tray_hd + 14, "fork stroke must exceed tray depth + post width"

    # ------------------------------------------------------------------ helpers
    def ledge_top(self, k):
        return self.ledge0 + k * self.pitch

    def cassette_posts(self):
        hy = SBS[1] / 2
        return {"Front": (self.YC - hy - 15, self.YC - hy - 7), "Back": (self.YC + hy + 7, self.YC + hy + 15)}

    def link_path(self, name):
        return f"{self.ROOT}/{self.LINKS[name][0]}"

    def new_layer(self, path):
        return tc.new_layer(path, self.name, self.generator)

    # ------------------------------------------------------------------ hooks for device scripts
    def extra_parts(self, p):
        pass

    def extra_colliders(self, body):
        pass

    def extra_semantics(self, sem, frame):
        pass

    def extra_visual(self, vis, link_path):
        pass

    # ------------------------------------------------------------------ CAD
    def shell(self):
        G, YF, XS = self.GATE, self.YF, self.XS
        dy, dz = self.door_y, self.door_z
        outer = box(0, 0, self.z0 + self.h / 2, self.w, self.d, self.h).edges("|Z").fillet(10).edges(">Z").fillet(4)
        inner = box(0, 0, self.z0 + self.h / 2, self.w - 2 * self.wall, self.d - 2 * self.wall,
                    self.h - 2 * self.wall).edges("|Z").fillet(7)
        s = outer.cut(inner)
        s = s.cut(box(0, YF + self.wall / 2, (G["z0"] + G["z1"]) / 2, 2 * G["x"], self.wall + 20, G["z1"] - G["z0"]))
        s = s.cut(box(XS - self.wall / 2, (dy[0] + dy[1]) / 2, (dz[0] + dz[1]) / 2, self.wall + 20, dy[1] - dy[0],
                      dz[1] - dz[0]).edges("|X").fillet(6))
        return s

    def build_cad(self):
        p = {}
        G, YF, XS, XI, YN, YC = self.GATE, self.YF, self.XS, self.XI, self.YN, self.YC
        p["Housing"] = (self.shell(), self.shell_material, "Housing")
        p["BaseFrame"] = (box(0, 0, (self.z0 + self.CZ0) / 2, self.w - 2 * self.wall, self.d - 2 * self.wall,
                              self.CZ0 - self.z0), "AnodizedGraphite", "Housing")
        for i, (sx, sy) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]):
            p[f"Foot{i}"] = (cyl(14, self.z0, (sx * (self.w / 2 - 30), sy * (self.d / 2 - 30), 0), (0, 0, 1))
                             .faces("<Z").edges().fillet(1.5), "RubberBlack", "Housing")
        if self.front_panel:
            zc, hh = self.front_panel
            p["FrontPanel"] = (to_front(rrect(self.w - 40, hh, 6, 2), 0, zc, YF), "PlasticBlack", "Housing")
        p["Label"] = (to_front(rrect(150, 18, 2, 0.8), 0, self.label_z, YF - 2), "LabelWhite", "Housing")
        text = cq.Workplane("XY").text(self.label, 9.0, 0.35, kind="bold", halign="center", valign="center")
        p["LabelText"] = (to_front(text, 0, self.label_z, YF - 2.8), "PlasticBlack", "Housing")
        p["GateFrame"] = (to_front(cq.Workplane("XY").rect(2 * G["x"] + 24, G["z1"] - G["z0"] + 14)
                                   .rect(2 * G["x"], G["z1"] - G["z0"]).extrude(4), 0, (G["z0"] + G["z1"]) / 2, YF),
                          "AnodizedGraphite", "Housing")
        N = self.NEST
        p["ShuttleRail"] = (N.rail_part(YN + N.tray_hd + N.slide_l + 3), "SteelSatin", "Interior")
        for name, wp, mat in N.parts():
            p[name] = (wp, mat, "Shuttle")
        p["GatePanel"] = (box(0, G["y"], (G["z0"] + G["z1"]) / 2 + 2, 2 * G["x"] + 16, G["t"], G["z1"] - G["z0"] + 4)
                          .edges("|Y").fillet(2), "AnodizedGraphite", "Gate")
        hy = SBS[1] / 2
        top = self.ledge_top(self.n_slots - 1)
        for sx in (-1, 1):
            for tag, (y0, y1) in self.cassette_posts().items():
                p[f"CassettePost{'LR'[sx > 0]}{tag}"] = (
                    box(sx * (self.LEDGE_X1 + 4), (y0 + y1) / 2, (self.CASS_Z[0] + self.CASS_Z[1]) / 2, 8, y1 - y0,
                        self.CASS_Z[1] - self.CASS_Z[0]).edges("|Z").fillet(1), "Aluminium", "Cassette")
            for k in range(self.n_slots):
                p[f"Ledge{'LR'[sx > 0]}{k:02d}"] = (
                    box(sx * (self.LEDGE_X0 + self.LEDGE_X1) / 2, YC, self.ledge_top(k) - self.LEDGE_T / 2,
                        self.LEDGE_X1 - self.LEDGE_X0, 2 * hy + 14, self.LEDGE_T).edges("|Y").fillet(0.5),
                    "SteelSatin", "Cassette")
        p["CassetteBack"] = (box(0, YC + hy + 18, (self.ledge0 + top + 40) / 2, 2 * self.LEDGE_X1 + 16, 4,
                                 top - self.ledge0 + 60), "Aluminium", "Cassette")
        for k in range(self.n_slots):
            p[f"SlotSensor{k:02d}"] = (cyl(2.5, 1.0, (0, self.SLOT_SENSE_Y - 2, self.ledge_top(k) + 7), (0, -1, 0)),
                                       "SensorLens", "Cassette")
        p["LiftColumn"] = (box(XI - 17, YN - 15, (self.CZ0 + self.z0 + self.h) / 2 - 4, 20, 170,
                               self.h + self.z0 - self.CZ0 - 20 - 8).edges("|Z").fillet(2), "Aluminium", "Interior")
        p["LiftCarriage"] = (box(XI - 35, YN - 15, self.TINE_REF_Z - 10, 18, 190, 40).edges("|Z").fillet(2),
                             "AnodizedGraphite", "Lift")
        az0, az1 = self.TINE_REF_Z + self.ARM_DZ[0], self.TINE_REF_Z + self.ARM_DZ[1]
        ty0 = YN + self.TINE_Y0
        p["ForkSlider"] = (box(self.ARM_X1 + 10, ty0 - 5, (az0 + az1) / 2 + 4, 22, 30, 24).edges("|Z").fillet(2),
                           "SteelSatin", "Fork")
        p["ForkArm"] = (box((self.POST_X[0] + self.ARM_X1) / 2, ty0 - 5, (az0 + az1) / 2, self.ARM_X1 - self.POST_X[0],
                            10, az1 - az0), "SteelSatin", "Fork")
        p["ForkPost"] = (box(sum(self.POST_X) / 2, ty0 - 5, (az0 + self.TINE_REF_Z) / 2, self.POST_X[1] - self.POST_X[0],
                             10, self.TINE_REF_Z - az0), "SteelSatin", "Fork")
        p["ForkTine"] = (box(0, YN + (self.TINE_Y0 + self.TINE_Y1) / 2, self.TINE_REF_Z - self.TINE_T / 2,
                             2 * self.TINE_HX, self.TINE_Y1 - self.TINE_Y0, self.TINE_T).edges("|Z").fillet(3),
                         "SteelSatin", "Fork")
        rx, ry, rz = self.READER
        p["BarcodeReader"] = (box(rx - 9, ry, rz, 18, 34, 14).edges().fillet(1.5), "PlasticBlack", "Interior")
        p["BarcodeWindow"] = (box(rx + 0.25, ry, rz, 0.5, 20, 7), "SensorLens", "Interior")
        p["ReaderMount"] = (box((-XI + rx - 18) / 2, ry, rz, rx - 18 + XI, 16, 6), "Aluminium", "Interior")
        dy, dz = self.door_y, self.door_z
        door = rrect(dy[1] - dy[0] + 8, dz[1] - dz[0] + 8, 5, 4)
        if self.door_window:
            door = door.cut(rrect(dy[1] - dy[0] - 40, dz[1] - dz[0] - 60, 4, 4))
        place = lambda wp, dx: wp.rotate((0, 0, 0), (1, 0, 0), 90).rotate((0, 0, 0), (0, 0, 1), 90).translate(  # noqa: E731
            (XS + dx, (dy[0] + dy[1]) / 2, (dz[0] + dz[1]) / 2))
        p["DoorFrame"] = (place(door, 0), self.shell_material, "ServiceDoor")
        if self.door_window:
            p["DoorWindow"] = (place(rrect(dy[1] - dy[0] - 38, dz[1] - dz[0] - 58, 4, 2), 1), "Polycarbonate",
                               "ServiceDoor")
        p["DoorHandle"] = (box(XS + 14, dy[0] + 14, (dz[0] + dz[1]) / 2, 8, 10, 90).edges().fillet(2), "SteelSatin",
                           "ServiceDoor")
        sx, sy = self.stack_light_xy or (XS - 50, self.YB - 60)
        z = self.z0 + self.h
        for name, r, hh, mat in [("Base", 15, 12, "PlasticBlack"), ("Green", 14, 20, "LensGreen"),
                                 ("Amber", 14, 20, "LensAmber"), ("Red", 14, 20, "LensRed"), ("Cap", 15, 6, "PlasticBlack")]:
            part = cyl(r, hh, (sx, sy, z), (0, 0, 1))
            if name in ("Base", "Cap"):
                part = part.faces(">Z").edges().fillet(2 if name == "Cap" else 1)
            p[f"StackLight{name}"] = (part, mat, "StatusLight")
            z += hh
        self.extra_parts(p)
        return p

    def collision_boxes(self):
        t, G, YF, YB, XS, XI, YN, YC = self.wall, self.GATE, self.YF, self.YB, self.XS, self.XI, self.YN, self.YC
        top_z = self.z0 + self.h
        dy, dz = self.door_y, self.door_z
        body = [
            ("Floor", (-XS, XS), (YF, YB), (0, self.CZ0)),
            ("Roof", (-XS, XS), (YF, YB), (top_z - t, top_z)),
            ("WallBack", (-XS, XS), (YB - t, YB), (self.CZ0, top_z)),
            ("WallLeft", (-XS, -XS + t), (YF, YB), (self.CZ0, top_z)),
            ("WallRightRear", (XS - t, XS), (dy[1], YB), (self.CZ0, top_z)),
            ("WallRightFront", (XS - t, XS), (YF, dy[0]), (self.CZ0, top_z)),
            ("WallRightLow", (XS - t, XS), dy, (self.CZ0, dz[0])),
            ("WallRightHigh", (XS - t, XS), dy, (dz[1], top_z)),
            ("WallFrontUpper", (-XS, XS), (YF, YF + t), (G["z1"], top_z)),
            ("WallFrontLeft", (-XS, -G["x"]), (YF, YF + t), (self.CZ0, G["z1"])),
            ("WallFrontRight", (G["x"], XS), (YF, YF + t), (self.CZ0, G["z1"])),
            ("LiftColumn", (XI - 27, XI - 7), (YN - 100, YN + 70), (self.CZ0, top_z - 20)),
            ("BarcodeReader", (self.READER[0] - 18, self.READER[0]), (YN - 17, YN + 17),
             (self.READER[2] - 7, self.READER[2] + 7)),
            ("CassetteBack", (-self.LEDGE_X1 - 8, self.LEDGE_X1 + 8), (YC + SBS[1] / 2 + 16, YC + SBS[1] / 2 + 20),
             self.CASS_Z),
        ]
        hy = SBS[1] / 2
        for k in range(self.n_slots):
            z = self.ledge_top(k)
            for sx in (-1, 1):
                xs = tuple(sorted((sx * self.LEDGE_X0, sx * self.LEDGE_X1)))
                body.append((f"Ledge{'LR'[sx > 0]}{k:02d}", xs, (YC - hy - 7, YC + hy + 7), (z - self.LEDGE_T, z)))
        for sx in (-1, 1):
            xs = tuple(sorted((sx * self.LEDGE_X1, sx * (self.LEDGE_X1 + 8))))
            for tag, ys in self.cassette_posts().items():
                body.append((f"CassettePost{'LR'[sx > 0]}{tag}", xs, ys, self.CASS_Z))
        self.extra_colliders(body)
        gate = [("Panel", (-G["x"] - 8, G["x"] + 8), (G["y"] - G["t"] / 2, G["y"] + G["t"] / 2), (G["z0"], G["z1"] + 4))]
        az0, az1 = self.TINE_REF_Z + self.ARM_DZ[0], self.TINE_REF_Z + self.ARM_DZ[1]
        fy = (YN + self.TINE_Y0 - 10, YN + self.TINE_Y0)
        fork = [("Tine", (-self.TINE_HX, self.TINE_HX), (YN + self.TINE_Y0, YN + self.TINE_Y1),
                 (self.TINE_REF_Z - self.TINE_T, self.TINE_REF_Z)),
                ("Post", self.POST_X, fy, (az1, self.TINE_REF_Z)),
                ("Arm", (self.POST_X[0], self.ARM_X1), fy, (az0, az1))]
        lift = [("Carriage", (XI - 44, XI - 26), (YN - 110, YN + 80), (self.TINE_REF_Z - 30, self.TINE_REF_Z + 10))]
        door = [("Panel", (XS, XS + 4), (dy[0] - 4, dy[1] + 4), (dz[0] - 4, dz[1] + 4))]
        return {"Body": body, "Gate": gate, "Shuttle": self.NEST.collision_boxes(), "Fork": fork, "Lift": lift,
                "ServiceDoor": door}

    # ------------------------------------------------------------------ layers
    def write_visual(self, parts):
        tc.PBR.update(EXTRA_PBR)
        vis = self.new_layer(os.path.join(self.here, f"{self.file_prefix}_visual.usda"))
        UsdGeom.Xform.Define(vis, self.ROOT)
        mats = define_materials(vis, self.ROOT, sorted({m for _, m, _ in parts.values()} | {"AprilTag"}),
                                tag_id=self.tag_id)
        for name, (_, _, rest) in self.LINKS.items():
            xf = UsdGeom.Xform.Define(vis, self.link_path(name))
            xf.AddTranslateOp().Set(Gf.Vec3d(*(np.array(rest, dtype=float) * MM)))
            if name == "ServiceDoor":
                xf.AddRotateZOp(opSuffix="hinge").Set(0.0)
        fork_rest = np.array([0.0, self.YN + self.PARK[1], 0.0])
        UsdGeom.Xformable(vis.GetPrimAtPath(self.link_path("Fork"))).GetOrderedXformOps()[0].Set(
            Gf.Vec3d(*(fork_rest * MM)))
        tri = 0
        for link in self.LINKS:
            UsdGeom.Xform.Define(vis, f"{self.link_path(link)}/Visual")
        for group, link in self.GROUP_LINK.items():
            if link == "Body":
                UsdGeom.Xform.Define(vis, f"{self.link_path(link)}/Visual/{group}")
        for name, (wp, mat, group) in parts.items():
            link = self.GROUP_LINK[group]
            sub = f"/{group}" if link == "Body" else ""
            mesh, n = write_mesh(vis, f"{self.link_path(link)}/Visual{sub}/{name}", wp, self.LINKS[link][1])
            bind(mesh.GetPrim(), mats[mat])
            tri += n
        N = self.NEST
        tx, ty, tz, hs = N.tag_c[0] * MM, N.tag_c[1] * MM, (N.tray_z1 + 0.62) * MM, 10.0 * MM
        tagm = UsdGeom.Mesh.Define(vis, f"{self.link_path('Shuttle')}/Visual/AprilTag")
        tagm.CreatePointsAttr([Gf.Vec3f(tx - hs, ty - hs, tz), Gf.Vec3f(tx + hs, ty - hs, tz),
                               Gf.Vec3f(tx + hs, ty + hs, tz), Gf.Vec3f(tx - hs, ty + hs, tz)])
        tagm.CreateFaceVertexCountsAttr([4])
        tagm.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
        tagm.CreateNormalsAttr([Gf.Vec3f(0, 0, 1)] * 4)
        tagm.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
        tagm.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
        UsdGeom.PrimvarsAPI(tagm).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex).Set(
            [Gf.Vec2f(0, 0), Gf.Vec2f(1, 0), Gf.Vec2f(1, 1), Gf.Vec2f(0, 1)])
        bind(tagm.GetPrim(), mats["AprilTag"])
        led = UsdLux.RectLight.Define(vis, f"{self.link_path('Body')}/Visual/Interior/LedLight")
        led.CreateWidthAttr(0.24)
        led.CreateHeightAttr(0.30)
        led.CreateIntensityAttr(6000.0)
        led.CreateColorTemperatureAttr(5000.0)
        led.CreateEnableColorTemperatureAttr(True)
        led.AddTranslateOp().Set(Gf.Vec3d(0, (self.YN + self.YC) / 2 * MM, (self.z0 + self.h - self.wall - 5) * MM))
        self.extra_visual(vis, self.link_path)
        vis.GetRootLayer().Save()
        return tri

    def write_physics(self):
        phy = self.new_layer(os.path.join(self.here, f"{self.file_prefix}_physics.usda"))
        cmat = define_contact_materials(phy, self.ROOT)
        n = 0
        for link, boxes in self.collision_boxes().items():
            lp = phy.OverridePrim(self.link_path(link))
            UsdPhysics.RigidBodyAPI.Apply(lp)
            UsdPhysics.MassAPI.Apply(lp).CreateMassAttr(self.masses[link])
            col = UsdGeom.Xform.Define(phy, f"{self.link_path(link)}/Collision")
            col.CreatePurposeAttr(UsdGeom.Tokens.guide)
            origin = np.array(self.LINKS[link][1], dtype=float)
            for name, xs, ys, zs in boxes:
                mat = cmat["Peek"] if name.startswith(("Nest", "Tine")) else cmat["Steel"]
                add_box_collider(phy, col.GetPath(), name, xs, ys, zs, origin, mat,
                                 offsets=(0.0005, 0.0) if link != "Body" or name.startswith("Ledge") else None)
                n += 1
            if link == "Shuttle":
                for name, solid in self.NEST.convex_colliders():
                    add_convex_collider(phy, f"{col.GetPath()}/{name}", solid, origin, cmat["Peek"])
                    n += 1
        phy.GetRootLayer().Save()
        return n

    def write_articulation(self):
        art = self.new_layer(os.path.join(self.here, f"{self.file_prefix}_articulation.usda"))
        root = art.GetPrimAtPath(self.ROOT)
        UsdPhysics.ArticulationRootAPI.Apply(root)
        root.AddAppliedSchema("PhysxArticulationAPI")
        root.CreateAttribute("physxArticulation:enabledSelfCollisions", B).Set(True)
        root.CreateAttribute("physxArticulation:solverPositionIterationCount", Sdf.ValueTypeNames.Int).Set(32)
        root.CreateAttribute("physxArticulation:solverVelocityIterationCount", Sdf.ValueTypeNames.Int).Set(4)
        root.CreateAttribute("physxArticulation:sleepThreshold", F).Set(0.0)  # see H4: never sleep
        body, R = self.link_path("Body"), self.ROOT
        UsdGeom.Scope.Define(art, f"{R}/Joints")
        _joint(art, UsdPhysics.FixedJoint, f"{R}/Joints/RootJoint", None, body, Gf.Vec3f(0), Gf.Vec3f(0))
        g = _joint(art, UsdPhysics.PrismaticJoint, f"{R}/Joints/GateSlide", body, self.link_path("Gate"),
                   mm3((0, self.GATE["y"], 0)), Gf.Vec3f(0), "Z", (0.0, self.GATE["travel"] * MM))
        # servo axes: stiff enough that gravity sag stays well inside the controller's 0.4 mm move tolerance
        _drive(g, "linear", stiffness=50000.0, damping=400.0, max_force=100.0, target=0.0)
        s = _joint(art, UsdPhysics.PrismaticJoint, f"{R}/Joints/ShuttleSlide", body, self.link_path("Shuttle"),
                   mm3((0, self.YN, 0)), Gf.Vec3f(0), "Y", (0.0, self.NEST.travel * MM), Gf.Quatf(0, 0, 0, 1))
        _drive(s, "linear", stiffness=2000.0, damping=150.0, max_force=40.0, target=0.0)
        lf = _joint(art, UsdPhysics.PrismaticJoint, f"{R}/Joints/LiftSlide", body, self.link_path("Lift"),
                    mm3((0, 0, self.TINE_REF_Z)), Gf.Vec3f(0), "Z", (-1.0 * MM, self.LIFT_MAX * MM))
        _drive(lf, "linear", stiffness=200000.0, damping=1500.0, max_force=300.0, target=self.PARK[0] * MM)
        fk = _joint(art, UsdPhysics.PrismaticJoint, f"{R}/Joints/ForkSlide", self.link_path("Lift"),
                    self.link_path("Fork"), mm3((0, self.YN, 0)), mm3((0, 0, 0)), "Y", (0.0, self.FORK_TRAVEL * MM))
        _drive(fk, "linear", stiffness=50000.0, damping=400.0, max_force=100.0, target=self.PARK[1] * MM)
        dr = _joint(art, UsdPhysics.RevoluteJoint, f"{R}/Joints/ServiceDoorHinge", body, self.link_path("ServiceDoor"),
                    mm3((self.XS, self.door_y[1], 0)), Gf.Vec3f(0), "Z", (0.0, 100.0))
        _drive(dr, "angular", stiffness=0.2, damping=0.05, max_force=2.0, target=0.0)
        art.GetRootLayer().Save()

    def write_semantics(self):
        sem = self.new_layer(os.path.join(self.here, f"{self.file_prefix}_semantics.usda"))
        rp = sem.GetPrimAtPath(self.ROOT)
        Usd.ModelAPI(rp).SetKind(Kind.Tokens.component)
        S, St, Db, I = (Sdf.ValueTypeNames.String, Sdf.ValueTypeNames.StringArray, Sdf.ValueTypeNames.Double,
                        Sdf.ValueTypeNames.Int)
        attrs = [
            ("sdt:componentId", S, self.component_id),
            ("sdt:canonicalName", S, self.canonical_name),
            ("sdt:contract", S, self.contract),
            ("sdt:capabilities", St, list(self.capabilities)),
            ("sdt:bindingStatus", S, "articulated_v1"),
            ("sdt:designBasis", S, self.design_basis),
            ("sdt:slotCount", I, self.n_slots),
            ("state:inventory", St, [""] * self.n_slots),
            ("state:reserved_slots", Sdf.ValueTypeNames.IntArray, []),
            ("state:transfer_nest", S, "empty"),
            ("state:door", S, "closed"),
            ("state:gate", S, "closed"),
            ("state:mode", S, "READY"),
            ("state:fault", S, ""),
        ] + list(self.extra_attributes)
        for k, t, v in attrs:
            rp.CreateAttribute(k, t, custom=True).Set(v)

        def frame(name, pos, role):
            f = UsdGeom.Xform.Define(sem, f"{self.ROOT}/{name}")
            f.AddTranslateOp().Set(Gf.Vec3d(*(np.array(pos, dtype=float) * MM)))
            f.GetPrim().CreateAttribute("sdt:frameRole", S, custom=True).Set(role)
            return f

        fn, N = self.frame_names, self.NEST
        tn = frame(fn["transfer"], (0, N.y_ext, self.SEAT_Z),
                   "Presented SBS plate seat (gate open, shuttle extended): robot place/pick target. +X along the plate "
                   "long axis, A1 corner at (-X,+Y), +Z up")
        for k, t, v in N.transfer_attributes():
            tn.GetPrim().CreateAttribute(k, {"string": S, "double": Db}[t], custom=True).Set(v)
        if fn.get("load"):
            frame(fn["load"], (0, self.YN, self.SEAT_Z), "Stowed nest seat: where the internal handler loads/unloads")
        UsdGeom.Xform.Define(sem, f"{self.ROOT}/{fn['slots']}")
        for k in range(self.n_slots):
            f = frame(f"{fn['slots']}/slot_{k:02d}", (0, self.YC, self.ledge_top(k)), f"slot {k}: plate seat on the ledges")
            f.GetPrim().CreateAttribute("sdt:slotIndex", I, custom=True).Set(k)
            frame(f"{fn['slots']}/slot_{k:02d}/occupancy_sensor", (0, self.SLOT_SENSE_Y - self.YC, 7.0),
                  "occupancy ray origin, looks -Y over 40 mm")
        sd = frame(fn["door"], (self.XS, self.door_y[1], (self.door_z[0] + self.door_z[1]) / 2),
                   "Service door hinge axis at mid-height (+X face); joint ServiceDoorHinge, +angle opens outward")
        sd.GetPrim().CreateAttribute("sdt:interlock", S, custom=True).Set("door open -> internal handler halted")
        frame("barcode_reader", self.READER, "barcode reader lens point; reads the plate's -X short end along +X")
        frame("Shuttle/registration_tag", (N.tag_c[0], N.tag_c[1], N.tray_z1 + 0.62),
              "AprilTag 36h11 centre on the tag surface, axes = nest axes")
        frame("Shuttle/registration_datum", (N.datum_c[0], N.datum_c[1], N.tray_z1 + 8.0), "datum pin tip")
        for i, (x, y) in enumerate(N.seat_sensors):
            frame(f"Shuttle/seat_sensor_{i}", (x, y, self.SEAT_Z - 1.0), "flush seat sensor window, looks +Z")
        for k, v in (("handler:tineRefZ_mm", self.TINE_REF_Z), ("handler:forkTravel_mm", self.FORK_TRAVEL),
                     ("handler:liftMax_mm", self.LIFT_MAX), ("handler:ledge0_mm", self.ledge0),
                     ("handler:pitch_mm", self.pitch), ("handler:seatZ_mm", self.SEAT_Z),
                     ("handler:parkTineZ_mm", self.park_tine_z), ("handler:gateTravel_mm", self.GATE["travel"]),
                     ("handler:shuttleTravel_mm", self.NEST.travel)):
            rp.CreateAttribute(k, Db, custom=True).Set(float(v))
        rp.CreateAttribute("handler:frameNames", S, custom=True).Set(
            ";".join(f"{k}={v}" for k, v in fn.items() if v))
        self.extra_semantics(sem, frame)
        sem.GetRootLayer().Save()

    def build(self):
        os.makedirs(os.path.join(self.here, "build"), exist_ok=True)
        tc.make_textures(os.path.join(self.here, "textures"), [self.tag_id])
        parts = self.build_cad()
        asm = cq.Assembly(name=self.name)
        for name, (wp, _, _) in parts.items():
            asm.add(wp, name=name)
        asm.export(os.path.join(self.here, "build", f"{self.file_prefix}.step"))
        tri = self.write_visual(parts)
        n_col = self.write_physics()
        self.write_articulation()
        self.write_semantics()
        top = self.new_layer(os.path.join(self.here, f"{self.file_prefix}.usda"))
        top.GetRootLayer().subLayerPaths = [f"./{self.file_prefix}_{s}.usda" for s in
                                            ("semantics", "articulation", "physics", "visual")]
        top.GetRootLayer().Save()
        print(f"{self.component_id}: {len(parts)} parts, {tri} triangles, {n_col} colliders, {self.n_slots} slots; "
              f"seat z {self.SEAT_Z} mm, nest stowed y {self.YN}, presented y {self.NEST.y_ext}, slot column y {self.YC}")
        return parts
