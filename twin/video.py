"""Video of a running simulation: frames rendered from the live twin state (RTX real-time), a simple director, captions.

The physics run is unchanged: scripts wrap SimulationManager.step (install()) so the recorder gets control *between*
physics chunks - never inside a physics callback - and renders a frame every `every` steps while something moves
(5x real time at 30 fps with every=40 at 240 Hz) and every `idle_every` steps while everything waits (fast-forward).

Director: subjects report positions (robot TCPs, the AMR base) and stations report busy states; the most active one
gets the shot (priority AMR > R02 > R01 > station > establishing orbit), with a minimum shot length and smoothed
camera motion. Captions come from the run's own log lines (the episode's step reports), so the video shows what the
twin reports, not a separate script. Frames are JPEGs; encode() makes an H.264 MP4 (imageio-ffmpeg in env_cad).
"""

import math
import os
import subprocess
import sys

import numpy as np

HALL = (-9.4, 9.4, -6.8, 4.0)


class Subject:
    def __init__(self, name, label, pos_fn, shot_fn, priority, busy_fn=None):
        self.name, self.label, self.pos_fn, self.shot_fn, self.priority = name, label, pos_fn, shot_fn, priority
        self.busy_fn = busy_fn
        self.last = None
        self.activity = 0.0


class Recorder:
    def __init__(self, stage, out_dir, res=(1920, 1080), every=40, idle_every=480, hz=240, title="", fps=30):
        import carb
        import omni.replicator.core as rep
        from pxr import Gf, UsdGeom
        s = carb.settings.get_settings()
        s.set("/rtx/rendermode", "RaytracedLighting")
        s.set("/rtx/post/tonemap/op", 6)
        s.set("/rtx/post/histogram/enabled", True)
        s.set("/rtx/post/histogram/whiteScale", 9.0)
        s.set("/rtx/translucency/enabled", True)
        s.set("/rtx/translucency/maxRefractionBounces", 4)
        s.set("/rtx/reflections/enabled", True)
        s.set("/rtx/indirectDiffuse/enabled", True)
        s.set("/rtx/directLighting/sampledLighting/enabled", True)
        self.rep, self.res, self.every, self.idle_every, self.hz, self.fps = rep, res, every, idle_every, hz, fps
        self.out = out_dir
        os.makedirs(os.path.join(out_dir, "frames"), exist_ok=True)
        edit = stage.GetEditTarget()
        stage.SetEditTarget(stage.GetSessionLayer())
        cam = UsdGeom.Camera.Define(stage, "/World/RenderOnly/VideoCam")
        cam.CreateHorizontalApertureAttr(36.0)
        cam.CreateVerticalApertureAttr(36.0 * res[1] / res[0])
        cam.CreateClippingRangeAttr(Gf.Vec2f(0.02, 120))
        cam.CreateFocalLengthAttr(22.0)
        self.cam, self.op = cam, UsdGeom.Xformable(cam.GetPrim()).AddTransformOp()
        stage.SetEditTarget(edit)
        self.Gf = Gf
        self.rp = rep.create.render_product(str(cam.GetPath()), res)
        self.rgb = rep.AnnotatorRegistry.get_annotator("rgb")
        self.rgb.attach(self.rp)
        self.subjects = []
        self.steps = 0
        self.since = 0
        self.frame = 0
        self.t = 0.0
        self.caption = ""
        self.title = title
        self.shot = None
        self.shot_frames = 0
        self.eye = self.tgt = None
        self.focal = 22.0
        self.orbit = 0.0
        self.idle = False
        self.enabled = True
        self.log = []

    # ---------------------------------------------------------------- setup
    def add(self, *a, **kw):
        self.subjects.append(Subject(*a, **kw))

    def install(self):
        """Wrap SimulationManager.step: physics in chunks, a frame between chunks when due."""
        from isaacsim.core.simulation_manager import SimulationManager
        orig = SimulationManager.step
        rec = self

        def step(steps=1, callback=None, **kw):
            done = 0
            while done < steps:
                n = max(1, min(rec.due(), steps - done))
                if callback is None:
                    orig(steps=n, **kw)
                else:
                    orig(steps=n, callback=callback, **kw)
                done += n
                rec.advance(n)
        SimulationManager.step = step

    def hook_stdout(self, prefix="[episode]"):
        rec, real = self, sys.stdout

        class Tee:
            def write(self, s):
                for line in s.splitlines():
                    if line.startswith(prefix):
                        rec.on_log(line[len(prefix):].strip())
                return real.write(s)

            def flush(self):
                real.flush()

            def __getattr__(self, k):
                return getattr(real, k)
        sys.stdout = Tee()

    def on_log(self, line):
        if not line or line.startswith("robot contacts") or line.startswith("transit to") or line.startswith("frame "):
            return
        line = line.replace("===", "").strip()
        if len(line) > 120:
            line = line[:117] + "..."
        self.caption = line

    # ---------------------------------------------------------------- timing
    def due(self):
        return max(1, (self.idle_every if self.idle else self.every) - self.since)

    def advance(self, n):
        self.steps += n
        self.since += n
        self.t += n / self.hz
        if self.since >= (self.idle_every if self.idle else self.every):
            self.since = 0
            if self.enabled:
                self.capture()

    # ---------------------------------------------------------------- director
    def _activity(self, dt):
        best = None
        for s in self.subjects:
            p = s.pos_fn()
            speed = 0.0 if s.last is None or p is None else float(np.linalg.norm(np.asarray(p) - s.last)) / max(dt, 1e-6)
            s.last = None if p is None else np.asarray(p, float)
            busy = bool(s.busy_fn()) if s.busy_fn else False
            s.activity = 0.85 * s.activity + 0.15 * (1.0 if (speed > 0.015 or busy) else 0.0)
            if s.activity > 0.25 and (best is None or s.priority > best.priority):
                best = s
        return best

    def _orbit_shot(self):
        self.orbit += 0.004
        a = -1.2 + 0.9 * math.sin(self.orbit)
        eye = np.array([7.6 * math.cos(a), -0.8 + 5.2 * math.sin(a), 2.75])
        eye[0] = np.clip(eye[0], HALL[0], HALL[1])
        eye[1] = np.clip(eye[1], HALL[2], HALL[3])
        return eye, np.array([0.0, 0.3, 1.0]), 18.0, "Cell 01 in AICOR Lab 1"

    def capture(self):
        dt = (self.idle_every if self.idle else self.every) / self.hz
        s = self._activity(dt)
        want = s.name if s else "orbit"
        if want != self.shot and (self.shot_frames > 30 or self.shot is None or self.shot == "orbit"):
            self.shot, self.shot_frames, cut = want, 0, True
        else:
            cut = False
        self.shot_frames += 1
        self.idle = self.shot == "orbit"
        if self.shot == "orbit":
            eye, tgt, focal, label = self._orbit_shot()
        else:
            sub = next(x for x in self.subjects if x.name == self.shot)
            eye, tgt, focal = sub.shot_fn(sub.last if sub.last is not None else np.zeros(3))
            label = sub.label
        eye, tgt = np.asarray(eye, float), np.asarray(tgt, float)
        if cut or self.eye is None:
            self.eye, self.tgt, self.focal = eye, tgt, focal
        else:
            a = 0.18
            self.eye = self.eye + a * (eye - self.eye)
            self.tgt = self.tgt + 0.3 * (tgt - self.tgt)
            self.focal = self.focal + a * (focal - self.focal)
        Gf = self.Gf
        self.op.Set(Gf.Matrix4d().SetLookAt(Gf.Vec3d(*self.eye), Gf.Vec3d(*self.tgt), Gf.Vec3d(0, 0, 1)).GetInverse())
        self.cam.GetFocalLengthAttr().Set(float(self.focal))
        self.rep.orchestrator.step(rt_subframes=2, delta_time=0.0)
        img = np.asarray(self.rgb.get_data())[..., :3].astype(np.uint8)
        self._save(img, label)

    def _save(self, img, label):
        from PIL import Image, ImageDraw, ImageFont
        im = Image.fromarray(img)
        d = ImageDraw.Draw(im, "RGBA")
        W, H = im.size
        try:
            f1 = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", 30)
            f2 = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Regular.otf", 24)
            f3 = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Medium.otf", 20)
            fT = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", 56)
        except OSError:
            f1 = f2 = f3 = fT = ImageFont.load_default()
        d.rectangle([0, 0, W, 44], fill=(10, 18, 30, 170))
        d.text((20, 9), self.title, font=f3, fill=(225, 232, 242))
        speed = f"x{round(self.idle_every / self.every * 5) if self.idle else 5}"
        tt = f"sim t = {self.t:6.1f} s   {speed}{'  fast-forward' if self.idle else ''}"
        tw = d.textbbox((0, 0), tt, font=f3)[2]
        d.text((W - tw - 20, 9), tt, font=f3, fill=(225, 232, 242))
        d.rectangle([0, H - 96, W, H], fill=(10, 18, 30, 175))
        d.text((24, H - 88), label, font=f1, fill=(255, 255, 255))
        d.text((24, H - 46), self.caption, font=f2, fill=(190, 210, 235))
        if self.frame < 120:                           # title card for the first 4 s
            a = int(200 * min(1.0, (120 - self.frame) / 30))
            d.rectangle([0, H // 2 - 110, W, H // 2 + 90], fill=(10, 18, 30, a))
            lines = self.title.split("  |  ")
            d.text((80, H // 2 - 85), lines[0], font=fT, fill=(255, 255, 255, min(255, a + 55)))
            if len(lines) > 1:
                d.text((84, H // 2 + 5), "  |  ".join(lines[1:]), font=f2, fill=(200, 215, 235, min(255, a + 55)))
        im.save(os.path.join(self.out, "frames", f"{self.frame:06d}.jpg"), quality=92)
        self.log.append((self.frame, round(self.t, 2), self.shot, self.caption))
        self.frame += 1

    # ---------------------------------------------------------------- output
    def encode(self, name="video.mp4"):
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            exe = os.path.join(os.path.dirname(__file__), "..", "env_cad", "lib", "python3.12", "site-packages",
                               "imageio_ffmpeg", "binaries", "ffmpeg-linux-x86_64-v7.0.2")
        out = os.path.join(self.out, name)
        cmd = [exe, "-y", "-framerate", str(self.fps), "-i", os.path.join(self.out, "frames", "%06d.jpg"),
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium", out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        return out if r.returncode == 0 else r.stderr[-800:]
