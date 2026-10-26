"""The robot's own images of a design's cultures: the articulated L17 imager (PhysX, L17Controller in the loop) images
one unit per arm of a culture design run at several culture times.

The culture is the run's simulated culture (scenes/culture/<run>/run.json, hidden truth) seen through L17's image
formation (twin/l17_optics.py with twin/culture/optics.CultureSampleProvider): the controller moves the stage, indexes
the turret, autofocuses, exposes and checks its monitors exactly as in an episode; only the sample comes from the
culture. The plate stays loaded and is re-imaged at each time (in a run it would go back to L10 in between).

Outputs in scenes/culture/<run>/l17_robot/: the controller's raw 16-bit images (12-bit ADC values) with JSON sidecars
and an 8-bit preview of each (*_view.png), and robot_images.png (arms x times). ILLUSTRATIVE surrogate (D016).
--no-register: image without the plate registration (output in l17_robot*_unregistered/).
--place dx,dy,yaw: where the plate is released over the nest (mm, mm, deg; default 0,0,0). 1,-1,0.5 is the L17
acceptance test's placement: the nest's guides seat it, but without plate registration the residual shift and
rotation move the field off the organoid at 4x (output then in l17_robot_placement_error/).
Usage: env_isaacsim/bin/python scripts/image_culture_l17.py design_improved [--mag 4x] [--times 0,24,48,72] [--place dx,dy,yaw]
"""

import json
import math
import os
import shutil
import sys

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
args = sys.argv[1:]
RUN = args[0]
MAG = args[args.index("--mag") + 1] if "--mag" in args else "4x"
PLACE = [float(x) for x in (args[args.index("--place") + 1] if "--place" in args else "0,0,0").split(",")]  # dx mm, dy mm, yaw deg
TIMES = [float(x) for x in (args[args.index("--times") + 1] if "--times" in args else "0,24,48,72").split(",")]
DIR = os.path.join(ROOT, "scenes", "culture", RUN)
REGISTER = "--no-register" not in args
OUT = os.path.join(DIR, "l17_robot" + ("" if PLACE == [0, 0, 0] else "_placement_error") + ("" if REGISTER else "_unregistered"))
L17_USD = os.path.join(ROOT, "assets/l17/l17.usda")
PLATE_USD = os.path.join(ROOT, "assets/labware/plate_sbs96.usda")
PLATE = "Plate_P17"
HZ = 240
DT = 1.0 / HZ
POSE = (1.0, -0.6, 0.0, 20.0)
L = "/World/L17_BrightFieldImager"

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True})

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from isaacsim.core.experimental.prims import RigidPrim  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from pxr import Gf, PhysxSchema, Sdf, UsdGeom, UsdPhysics  # noqa: E402

import twin.l17_optics as op  # noqa: E402
from twin.culture import model as M  # noqa: E402
from twin.culture.optics import CultureSampleProvider  # noqa: E402
from twin.l17_controller import L17Controller  # noqa: E402

run = json.load(open(os.path.join(DIR, "run.json")))
ARMS = run["design"]["arms"]


class RunCulture:
    """The run's hidden culture replayed at a chosen culture time (for image formation only)."""

    def __init__(self, truth):
        self.truth, self.t_h = truth, 0.0
        self.wells = {w: None for w in truth}

    def appearance(self, well):
        h = min(self.truth[well], key=lambda x: abs(x["t_h"] - self.t_h))
        return dict(**M.morphology(h["I"], h["V"]), turbidity=h["B"], viability=h["V"], injury=h["I"])


culture = RunCulture(run["truth"])
op.SAMPLE_PROVIDER = CultureSampleProvider(culture, [PLATE])

omni.usd.get_context().new_stage()
app.update()
stage = omni.usd.get_context().get_stage()
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)
UsdGeom.Xform.Define(stage, "/World")
scene = UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
scene.CreateGravityDirectionAttr(Gf.Vec3f(0, 0, -1))
scene.CreateGravityMagnitudeAttr(9.81)
px = PhysxSchema.PhysxSceneAPI.Apply(scene.GetPrim())
px.CreateTimeStepsPerSecondAttr(HZ)
px.CreateSolverTypeAttr("TGS")
g = UsdGeom.Xform.Define(stage, "/World/Ground")
g.AddTranslateOp().Set(Gf.Vec3d(0, 0, -0.05))
c = UsdGeom.Cube.Define(stage, "/World/Ground/Box")
c.CreateSizeAttr(1.0)
c.AddScaleOp().Set(Gf.Vec3f(20, 20, 0.1))
UsdPhysics.CollisionAPI.Apply(c.GetPrim())
l17 = UsdGeom.Xform.Define(stage, L)
l17.GetPrim().GetReferences().AddReference(L17_USD)
l17.AddTranslateOp().Set(Gf.Vec3d(*POSE[:3]))
l17.AddRotateZOp().Set(POSE[3])
p = UsdGeom.Xform.Define(stage, "/World/Plate")
p.GetPrim().GetReferences().AddReference(PLATE_USD)
p.AddTranslateOp().Set(Gf.Vec3d(4.0, 4.0, 0.0))
p.AddOrientOp().Set(Gf.Quatf(1, 0, 0, 0))
p.GetPrim().CreateAttribute("labware:barcode", Sdf.ValueTypeNames.String, custom=True).Set(PLATE)
PhysxSchema.PhysxRigidBodyAPI.Apply(p.GetPrim()).CreateSleepThresholdAttr(0.0)
for _ in range(5):
    app.update()
xc = UsdGeom.XformCache()
LOAD = np.array(xc.GetLocalToWorldTransform(stage.GetPrimAtPath(f"{L}/plate_load_frame")).ExtractTranslation())
cs, sn = math.cos(math.radians(POSE[3])), math.sin(math.radians(POSE[3]))
R = np.array([[cs, -sn, 0], [sn, cs, 0], [0, 0, 1]])

app_utils.play(commit=True)
if os.path.isdir(OUT):
    shutil.rmtree(OUT)
ctrl = L17Controller(stage, L, image_dir=OUT)
plate = RigidPrim("/World/Plate")


def run_s(seconds):
    SimulationManager.step(steps=int(round(seconds * HZ)), callback=lambda i, n: ctrl.update(DT))


def wait_idle(timeout=120):
    t0 = ctrl.t
    while ctrl.t - t0 < timeout:
        run_s(0.25)
        if ctrl.mode != "BUSY":
            return True
    return False


run_s(1.0)
ctrl.present_for_load()
wait_idle(20)
a = math.radians(POSE[3] + PLACE[2]) / 2
plate.set_world_poses(positions=[(LOAD + R @ np.array([PLACE[0] * 1e-3, PLACE[1] * 1e-3, 0.013])).tolist()],
                      orientations=[[math.cos(a), 0.0, 0.0, math.sin(a)]])
plate.set_velocities(linear_velocities=[[0, 0, 0]], angular_velocities=[[0, 0, 0]])
run_s(1.0)
r = ctrl.load_plate(PLATE)
wait_idle(30)
print(f"[l17_culture] load_plate: {r.accepted} {r.reason} mode={ctrl.mode}", flush=True)
reg = None
if REGISTER:                                       # edge-finding plate registration before any imaging
    r = ctrl.register_plate(PLATE)
    wait_idle(600)
    reg = ctrl.registration.get(PLATE)
    print(f"[l17_culture] register_plate: accepted={r.accepted} -> "
          + (f"shift ({reg['dx_mm']:+.3f}, {reg['dy_mm']:+.3f}) mm, rotation {math.degrees(reg['theta_rad']):+.3f} deg, "
             f"well diameters {[w['diameter_mm'] for w in reg['wells'].values()]} mm" if reg else "FAILED"), flush=True)

shots = {}
for t in TIMES:
    culture.t_h = t
    for arm, wells in ARMS.items():
        w = wells[0]
        n0 = len(ctrl.acquisitions)
        r = ctrl.image_well(PLATE, w, magnification=MAG)
        wait_idle(90)
        acq = ctrl.acquisitions[n0:]
        last = acq[-1] if acq else None
        ref = last["raw_image_reference"].split("/")[-1].split("#")[0] if last else None
        tr = ctrl.truth[-1] if ctrl.truth else {}
        shots[(arm, t)] = dict(well=w, file=ref, valid=bool(last and last["valid"]), accepted=r.accepted,
                               focus=last["focus_score"] if last else None,
                               field_offset_from_well_centre_mm=tr.get("offset_from_well_centre_mm"))
        print(f"[l17_culture] t={t:4.0f} h {arm:24} {w}: accepted={r.accepted} valid={shots[(arm, t)]['valid']} "
              f"focus={shots[(arm, t)]['focus']} offset={shots[(arm, t)]['field_offset_from_well_centre_mm']} mm {ref}", flush=True)

# arms x times sheet of the robot's previews
cell = 300
names = list(ARMS)
sheet = Image.new("RGB", (250 + cell * len(TIMES), 70 + cell * len(names) + 40), (14, 16, 20))
d = ImageDraw.Draw(sheet)
F = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
f1, f2, f3 = ImageFont.truetype(F, 22), ImageFont.truetype(F, 18), ImageFont.truetype(F, 14)
d.text((16, 14), f"L17 robot images ({MAG}, autofocus, {'with' if reg else 'without'} plate registration) of the "
       f"{run['design']['name']} design's cultures, one unit per arm",
       font=f1, fill=(235, 240, 248))
for j, t in enumerate(TIMES):
    d.text((250 + j * cell + cell // 2 - 22, 46), f"{t:.0f} h", font=f2, fill=(220, 226, 236))
for i, arm in enumerate(names):
    y = 70 + i * cell
    d.text((14, y + cell // 2 - 30), arm.replace("_", " "), font=f2, fill=(235, 240, 248))
    d.text((14, y + cell // 2 - 4), f"well {ARMS[arm][0]}", font=f3, fill=(170, 182, 200))
    for j, t in enumerate(TIMES):
        s = shots.get((arm, t))
        if s and s["file"]:
            v = os.path.join(OUT, s["file"][:-4] + "_view.png")
            im = Image.open(v).convert("RGB")
            side = min(im.size)
            im = im.crop(((im.width - side) // 2, (im.height - side) // 2, (im.width + side) // 2, (im.height + side) // 2))
            sheet.paste(im.resize((cell - 6, cell - 6)), (250 + j * cell, y))
            if not s["valid"]:
                d.text((250 + j * cell + 8, y + 8), "invalid", font=f3, fill=(255, 120, 120))
d.text((16, sheet.height - 30), "Raw 12-bit images shown linearly (0-4095 -> 0-255), centre square. Simulated culture, "
       "illustrative surrogate (D016).", font=f3, fill=(150, 165, 185))
sheet.save(os.path.join(OUT, "robot_images.png"))
json.dump(dict(registration=reg, place=PLACE, shots={f"{a}@{t:g}h": s for (a, t), s in shots.items()}),
          open(os.path.join(OUT, "robot_images.json"), "w"), indent=1)
valid = sum(s["valid"] for s in shots.values())
offs = [s["field_offset_from_well_centre_mm"] for s in shots.values() if s["field_offset_from_well_centre_mm"] is not None]
print(f"[l17_culture] valid {valid}/{len(shots)}; field offset from the well centre: max {max(offs):.3f} mm, "
      f"mean {sum(offs) / len(offs):.3f} mm", flush=True)
print(f"[l17_culture] wrote {OUT}/robot_images.png", flush=True)
app.close()
