"""Render a culture run from its USD layers (scenes/culture/<scenario>/lab_culture.usda): stills and a time-lapse.

Everything shown is read from the time-sampled USD (time code = culture hours): the organoids' appearance from the
culture appearance layer, the SDT discs / halos / rings from the SDT visualisation layer (spec 18.3: overlays in a
separate layer, switched on for the "SDT view"). No physics runs; the plate sits on L12's plate nest.

  --stills     path-traced: macro of a rescued / unrescued pair at 0, 24, 72 h (camera view: straight down into each
               well on a render-only transillumination pad, like a stereo microscope), the plate with the SDT
               layer at the same times, and the plate on L12 in context.
  --arms       path-traced: for a design run (scenes/culture/design_<name>), one unit per arm at 0, 24, 48, 72 h in the
               camera view, as a grid (arms x times), and the plate with the SDT layer at the same times.
  --timelapse  RTX real-time frames 0 -> 72 h (every 0.5 h): macro (camera view) + plate with SDT layer side by side,
               live belief-vs-time plots and captions, encoded to MP4.
Usage: python scripts/render_culture.py <scenario | design_<name>> (--stills | --arms | --timelapse [--pt]) [--quick]
"""

import json
import os
import sys

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
SCEN = next(a for a in sys.argv[1:] if not a.startswith("--"))
DIR = os.path.join(ROOT, "scenes", "culture", SCEN)
STILLS, TIMELAPSE, QUICK = "--stills" in sys.argv, "--timelapse" in sys.argv, "--quick" in sys.argv
ARMS = "--arms" in sys.argv
OUT = os.path.join(DIR, "renders")
RES = (1280, 720) if (QUICK or TIMELAPSE) else (1920, 1080)

from isaacsim import SimulationApp  # noqa: E402

PT = STILLS or ARMS or "--pt" in sys.argv          # --pt: path-traced time-lapse (needs the GPU alone)
app = SimulationApp({"headless": True, "renderer": "PathTracing" if PT else "RaytracedLighting",
                     "width": RES[0], "height": RES[1]})
import carb  # noqa: E402
import numpy as np  # noqa: E402
import omni.replicator.core as rep  # noqa: E402
import omni.timeline  # noqa: E402
import omni.usd  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from pxr import Gf, UsdGeom, UsdLux  # noqa: E402

from twin.l17_optics import well_center  # noqa: E402

s = carb.settings.get_settings()
s.set("/rtx/post/tonemap/op", 6)
s.set("/rtx/post/histogram/enabled", True)
s.set("/rtx/post/histogram/whiteScale", 9.0)
if PT:
    s.set("/rtx/rendermode", "PathTracing")
    s.set("/rtx/pathtracing/spp", 16)
    s.set("/rtx/pathtracing/totalSpp", 16 * (8 if (QUICK or TIMELAPSE) else 32))
    s.set("/rtx/pathtracing/maxBounces", 10)
    s.set("/rtx/pathtracing/optixDenoiser/enabled", True)
else:
    s.set("/rtx/rendermode", "RaytracedLighting")
    s.set("/rtx/translucency/enabled", True)
SUBFRAMES = (8 if (QUICK or TIMELAPSE) else 32) if PT else 3

omni.usd.get_context().open_stage(os.path.join(DIR, "lab_culture.usda"))
for _ in range(20):
    app.update()
stage = omni.usd.get_context().get_stage()
stage.SetEditTarget(stage.GetSessionLayer())
run = json.load(open(os.path.join(DIR, "run.json")))
TCPS = stage.GetTimeCodesPerSecond()
tl = omni.timeline.get_timeline_interface()
viz = UsdGeom.Imageable(stage.GetPrimAtPath("/World/SDTViz"))
plate_m = UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath("/World/CultureRender/Plate_P17"))
cam = UsdGeom.Camera.Define(stage, "/World/RenderOnly/CultureCam")
cam.CreateHorizontalApertureAttr(36.0)
cam.CreateVerticalApertureAttr(36.0 * RES[1] / RES[0])
cam.CreateClippingRangeAttr(Gf.Vec2f(0.002, 60))
op = UsdGeom.Xformable(cam.GetPrim()).AddTransformOp()
rp = rep.create.render_product(str(cam.GetPath()), RES)
rgb = rep.AnnotatorRegistry.get_annotator("rgb")
rgb.attach(rp)
os.makedirs(OUT, exist_ok=True)


def W(well, dz_mm=0.0, du=0.0, dv=0.0):
    u, v = well_center(well)
    return np.array(plate_m.Transform(Gf.Vec3d((u + du) * 1e-3, (v + dv) * 1e-3, dz_mm * 1e-3)))


PLATE_Y = np.array(plate_m.TransformDir(Gf.Vec3d(0, 1, 0)))
# transillumination pad (render only, like a stereo microscope's base): a diffuse light in the plate skirt under the
# wells, facing up; switched on for the macro views only
pad = UsdLux.RectLight.Define(stage, "/World/RenderOnly/TransilluminationPad")
pad.CreateWidthAttr(0.110)
pad.CreateHeightAttr(0.072)
pad.CreateIntensityAttr(1500.0)
pad.CreateColorTemperatureAttr(5600.0)
pad.CreateEnableColorTemperatureAttr(True)
pad_xf = UsdGeom.Xformable(pad.GetPrim())
pad_xf.AddTransformOp().Set(Gf.Matrix4d(Gf.Rotation(Gf.Vec3d(1, 0, 0), 180.0), Gf.Vec3d(0, 0, 0.0015)) * plate_m)
pad_vis = UsdGeom.Imageable(pad.GetPrim())


def shoot(eye, target, focal, t_h, show_viz, near=0.002, up=(0, 0, 1), backlight=False):
    viz.CreateVisibilityAttr().Set("inherited" if show_viz else "invisible")
    pad_vis.CreateVisibilityAttr().Set("inherited" if backlight else "invisible")
    cam.GetClippingRangeAttr().Set(Gf.Vec2f(near, 60))
    tl.set_current_time(float(t_h) / TCPS)
    op.Set(Gf.Matrix4d().SetLookAt(Gf.Vec3d(*map(float, eye)), Gf.Vec3d(*map(float, target)),
                                   Gf.Vec3d(*map(float, up))).GetInverse())
    cam.GetFocalLengthAttr().Set(float(focal))
    for _ in range(2):
        app.update()
    rep.orchestrator.step(rt_subframes=SUBFRAMES, delta_time=0.0)
    return Image.fromarray(np.asarray(rgb.get_data())[..., :3].astype(np.uint8))


def macro_pair(pair, t_h, size):
    """Stereo-microscope-like camera view: straight down into each well of the pair (camera 25 mm above the well
    bottom, ~4.4 mm horizontal field, centre half kept = 2.2 mm), transilluminated from below; side by side."""
    halves = []
    for w in pair:
        # near plane 16 mm: removes the SDT overlay (13.2 mm away) and the plate top (14.1 mm), keeps the medium surface
        # (19.8 mm) and the organoid (~25 mm); hiding the overlay prim alone did not reach the path tracer
        img = shoot(W(w, 25.0), W(w, 0.0), 205.0, t_h, False, near=0.016, up=PLATE_Y, backlight=True)
        x0 = img.width // 4
        half = img.crop((x0, 0, x0 + img.width // 2, img.height))
        d = ImageDraw.Draw(half, "RGBA")
        f = ImageFont.truetype(FONT, max(18, img.height // 30))
        d.rectangle([0, 0, half.width, img.height // 18], fill=(10, 18, 30, 150))
        d.text((12, 6), f"{w}  |  field 2.2 x 2.5 mm", font=f, fill=(235, 240, 248))
        halves.append(half)
    out = Image.new("RGB", (halves[0].width * 2, halves[0].height))
    out.paste(halves[0], (0, 0))
    out.paste(halves[1], (halves[0].width, 0))
    ImageDraw.Draw(out).line([(halves[0].width, 0), (halves[0].width, out.height)], fill=(12, 16, 22), width=4)
    return out.resize(size)


def plate_view():
    c = np.array(plate_m.Transform(Gf.Vec3d(-0.018, 0.010, 0.014)))
    return c + [0.02, -0.075, 0.105], c, 40.0


FONT = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"


def label(img, lines, size=26):
    d = ImageDraw.Draw(img, "RGBA")
    f = ImageFont.truetype(FONT, size)
    h = 14 + len(lines) * (size + 8)
    d.rectangle([0, img.height - h, img.width, img.height], fill=(10, 18, 30, 180))
    for i, ln in enumerate(lines):
        d.text((18, img.height - h + 8 + i * (size + 8)), ln, font=f, fill=(235, 240, 248))
    return img


if STILLS:
    pair = ("D03", "D04") if SCEN != "contamination" else ("C03", "C04")
    for t in (0.0, 24.0, 72.0):
        label(macro_pair(pair, t, RES), [f"{pair[0]} (challenge only)  |  {pair[1]} (challenge + rescue at 6 h)",
                                          f"culture time {t:.0f} h  -  camera view of the simulated culture "
                                          f"(illustrative surrogate, D016)"]).save(os.path.join(OUT, f"macro_{pair[0]}_{pair[1]}_{t:02.0f}h.png"))
        e, tg, f = plate_view()
        label(shoot(e, tg, f, t, True), [f"Plate_P17 on L12 - SDT layer at {t:.0f} h: disc = belief viability (red->green), "
                                         "halo = 90 % interval", "purple ring: anomaly flagged; orange ring: dose not verified"]
              ).save(os.path.join(OUT, f"plate_sdt_{t:02.0f}h.png"))
    e = np.array(plate_m.Transform(Gf.Vec3d(0, 0, 0))) + [0.35, -0.55, 0.42]
    label(shoot(e, np.array(plate_m.Transform(Gf.Vec3d(0, 0, 0.01))), 30.0, 72.0, True),
          ["Plate_P17 on L12 at 72 h with the SDT layer, in Cell 01"]).save(os.path.join(OUT, "context_l12_72h.png"))
    print(f"[render_culture] stills in {OUT}", flush=True)

if ARMS:
    D = run["design"]
    times = (0.0, 24.0, 48.0, 72.0)
    cell = 420
    names = list(D["arms"])
    grid = Image.new("RGB", (260 + cell * len(times), 70 + cell * len(names) + 60), (12, 16, 22))
    g = ImageDraw.Draw(grid)
    f1, f2, f3 = ImageFont.truetype(FONT, 26), ImageFont.truetype(FONT, 20), ImageFont.truetype(FONT, 16)
    g.text((20, 18), f"{D['name']} design, one unit per arm: camera view of the simulated culture (field 2.2 mm)",
           font=f1, fill=(235, 240, 248))
    for j, t in enumerate(times):
        g.text((260 + j * cell + cell // 2 - 25, 52), f"{t:.0f} h", font=f2, fill=(220, 226, 236))
    for i, arm in enumerate(names):
        w = D["arms"][arm][0]
        sched = ", ".join(f"{k} {au:g} au @ {tp:g} h" if k != "vehicle" else f"vehicle @ {tp:g} h"
                          for tp, ww, k, au in D["plan"] if ww == w) or "untreated"
        y = 80 + i * cell
        g.text((16, y + 20), arm.replace("_", " "), font=f2, fill=(235, 240, 248))
        g.text((16, y + 50), f"well {w}", font=f3, fill=(170, 182, 200))
        yy = y + 80
        for part in sched.split(", "):
            g.text((16, yy), part, font=f3, fill=(170, 182, 200))
            yy += 22
        for j, t in enumerate(times):
            img = shoot(W(w, 25.0), W(w, 0.0), 205.0, t, False, near=0.016, up=PLATE_Y, backlight=True)
            side = img.height
            x0 = (img.width - side) // 2
            grid.paste(img.crop((x0, 0, x0 + side, side)).resize((cell - 8, cell - 8)), (260 + j * cell, y))
        print(f"[render_culture] arm {arm} ({w}) done", flush=True)
    g.text((20, grid.height - 40), "Illustrative Cell 01 surrogate (D016): organoid body, necrotic core and debris are "
           "derived from the simulated state; not a biological finding.", font=f3, fill=(150, 165, 185))
    grid.save(os.path.join(OUT, "arms_camera_view.png"))
    for t in times:
        e, tg, f = plate_view()
        label(shoot(e, tg, f, t, True), [f"{D['name']} design on Plate_P17 (L12) at {t:.0f} h - disc = belief viability "
                                         "(red->green), halo = 90 % interval"]).save(os.path.join(OUT, f"plate_sdt_{t:02.0f}h.png"))
    print(f"[render_culture] arms in {OUT}", flush=True)

if TIMELAPSE:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fr = os.path.join(OUT, "timelapse_frames")
    os.makedirs(fr, exist_ok=True)
    pair = ("D03", "D04") if SCEN != "contamination" else ("C03", "C04")
    wells_plot = list(dict.fromkeys([pair[0], pair[1], "A03", "A04", "E03"]))
    bel = {w: run["belief"][w] for w in wells_plot}
    events = run["interventions"]
    for k, t in enumerate(np.arange(0.0, 72.01, 0.5)):
        a = macro_pair(pair, t, (960, 540))
        e, tg, f = plate_view()
        b = shoot(e, tg, f, t, True).resize((960, 540))
        fig, ax = plt.subplots(figsize=(19.2, 3.6), dpi=50)
        for i, w in enumerate(wells_plot):
            hs = [h for h in bel[w] if h["t_h"] <= t + 1e-6]
            col = plt.get_cmap("tab10")(i)
            if hs:
                ax.fill_between([h["t_h"] for h in hs], [h["V"]["p05"] for h in hs], [h["V"]["p95"] for h in hs],
                                color=col, alpha=0.2, lw=0)
                ax.plot([h["t_h"] for h in hs], [h["V"]["mean"] for h in hs], color=col, lw=3, label=f"{w} belief V")
        for ev in events:
            if ev["t_h"] <= t and ev["well"] in wells_plot:
                ax.axvline(ev["t_h"], color="tab:red" if ev["kind"] == "challenge" else "tab:green", alpha=0.3)
        ax.set_xlim(0, 72)
        ax.set_ylim(0, 1)
        ax.set_xlabel("culture time (h)", fontsize=16)
        ax.set_ylabel("viability (belief)", fontsize=16)
        ax.legend(loc="lower left", fontsize=13, ncol=5)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.canvas.draw()
        chart = Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[..., :3]).resize((1920, 360))
        plt.close(fig)
        frame = Image.new("RGB", (1920, 1080), (12, 16, 22))
        frame.paste(a, (0, 60))
        frame.paste(b, (960, 60))
        frame.paste(chart, (0, 690))
        d = ImageDraw.Draw(frame)
        f1, f2 = ImageFont.truetype(FONT, 30), ImageFont.truetype(FONT, 22)
        d.text((20, 14), f"Culture SDT time-lapse  |  Plate_P17  |  scenario '{SCEN}'  |  culture time {t:5.1f} h",
               font=f1, fill=(235, 240, 248))
        d.text((20, 604), f"camera view: {pair[0]} challenge only, {pair[1]} + rescue at 6 h (simulated culture)",
               font=f2, fill=(200, 212, 230))
        d.text((980, 604), "SDT layer: belief viability (disc), 90 % interval (halo), flags (rings)",
               font=f2, fill=(200, 212, 230))
        d.text((20, 640), "Illustrative Cell 01 surrogate (D016) - the SDT sees only robot records and 4x images",
               font=f2, fill=(150, 165, 185))
        frame.save(os.path.join(fr, f"{k:05d}.jpg"), quality=90)
        if k % 20 == 0:
            print(f"[render_culture] frame {k} t={t:.1f} h", flush=True)
    import subprocess
    ff = os.path.join(ROOT, "env_cad/lib/python3.12/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2")
    mp4 = os.path.join(OUT, f"culture_timelapse_{SCEN}.mp4")
    subprocess.run([ff, "-y", "-loglevel", "error", "-framerate", "12", "-i", os.path.join(fr, "%05d.jpg"), "-c:v",
                    "libx264", "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4],
                   check=True)
    print(f"[render_culture] {mp4}", flush=True)
rep.orchestrator.wait_until_complete()
sys.stdout.flush()
os._exit(0)
