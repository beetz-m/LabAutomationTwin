"""Fast procedural mesh kit for furniture, enclosures, building parts and lab equipment (numpy, metres, Z up).

CadQuery (assets/common/twin_cad.py) stays the tool for mechanisms and precision parts; this kit builds the many
simple-but-detailed parts of the lab (rounded boxes with real edge radii, cylinders, lathed parts, swept tubes,
extruded profiles, decal quads) quickly. Geometry accumulates per material; Kit.write() emits one Mesh per material
under <root>/Visual, a <root>/Looks reference to the shared library (assets/materials/lab_materials.usda), decal /
screen materials for generated textures, and static box colliders (guide purpose) under <root>/Collision.

Frames: Kit.at(...) pushes a local frame (translate + yaw / full rotation). Equipment convention: origin on the floor
at the footprint centre, front (operator / robot side) toward -Y.
"""

import math
import os
from collections import defaultdict
from contextlib import contextmanager

import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MATLIB = os.path.join(ROOT, "assets", "materials", "lab_materials.usda")
import sys  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "assets", "materials"))
from build_materials import TILE_M  # noqa: E402


def rot_z(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def rot_x(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[1.0, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, 0, s], [0, 1.0, 0], [-s, 0, c]])


def frame_from_axis(axis):
    """Rotation whose +Z is `axis` (unit)."""
    w = np.asarray(axis, float)
    w = w / np.linalg.norm(w)
    a = np.array([1.0, 0, 0]) if abs(w[0]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(a, w)
    u /= np.linalg.norm(u)
    v = np.cross(w, u)
    return np.stack([u, v, w], 1)


def earclip(poly):
    """Triangulate a simple CCW polygon (list of 2D points) -> index triples."""
    P = np.asarray(poly, float)
    idx = list(range(len(P)))
    area = 0.5 * sum(P[i, 0] * P[(i + 1) % len(P), 1] - P[(i + 1) % len(P), 0] * P[i, 1] for i in range(len(P)))
    if area < 0:
        idx.reverse()
    tris = []
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        n = len(idx)
        for k in range(n):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % n]
            a, b, c = P[i0], P[i1], P[i2]
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) <= 1e-12:
                continue
            inside = False
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                p = P[j]
                d1 = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
                d2 = (c[0] - b[0]) * (p[1] - b[1]) - (c[1] - b[1]) * (p[0] - b[0])
                d3 = (a[0] - c[0]) * (p[1] - c[1]) - (a[1] - c[1]) * (p[0] - c[0])
                if d1 >= 0 and d2 >= 0 and d3 >= 0:
                    inside = True
                    break
            if inside:
                continue
            tris.append((i0, i1, i2))
            idx.pop(k)
            break
    if len(idx) == 3:
        tris.append(tuple(idx))
    return tris


class Kit:
    def __init__(self):
        self.parts = defaultdict(list)     # material key -> [(P, N, UV or None, T)]
        self.stack = [np.eye(4)]
        self.colliders = []                # (name, centre(3), size(3), yaw_deg)
        self.frames = {}                   # name -> 4x4 (local to asset root)
        self.ncoll = 0

    # ---------------------------------------------------------------- frames
    @contextmanager
    def at(self, pos=(0, 0, 0), yaw=0.0, R=None):
        M = np.eye(4)
        M[:3, :3] = rot_z(yaw) if R is None else np.asarray(R, float)
        M[:3, 3] = pos
        self.stack.append(self.stack[-1] @ M)
        try:
            yield self
        finally:
            self.stack.pop()

    @property
    def M(self):
        return self.stack[-1]

    def frame(self, name, pos=(0, 0, 0), yaw=0.0):
        M = np.eye(4)
        M[:3, :3] = rot_z(yaw)
        M[:3, 3] = pos
        self.frames[name] = self.M @ M

    # ---------------------------------------------------------------- core
    def add(self, mat, P, N, T, UV=None):
        M = self.M
        P = P @ M[:3, :3].T + M[:3, 3]
        N = N @ M[:3, :3].T
        self.parts[mat].append((P, N, UV, np.asarray(T, np.int64)))

    def collide(self, center, size, yaw=0.0, name=None):
        """Static box collider in the current frame (frame yaw is composed)."""
        M = self.M
        c = M[:3, :3] @ np.asarray(center, float) + M[:3, 3]
        fyaw = math.degrees(math.atan2(M[1, 0], M[0, 0]))
        self.ncoll += 1
        self.colliders.append((name or f"Box{self.ncoll:03d}", c, np.asarray(size, float), fyaw + yaw))

    # ---------------------------------------------------------------- primitives
    def rbox(self, mat, center, size, r=0.002, seg=2, faces=None):
        """Box with rounded edges/corners (radius r, seg segments per 45 deg). faces: subset of '+x-x+y-y+z-z'."""
        h = np.asarray(size, float) / 2
        r = float(min(r, *(h * 0.999))) if r > 0 else 0.0
        inner = h - r
        c0 = np.asarray(center, float)
        if r > 0:
            phis = np.linspace(0, math.pi / 4, seg + 1)
        Ps, Ns, Ts = [], [], []
        base = 0
        for a in range(3):
            for s in (-1, 1):
                key = f"{'+' if s > 0 else '-'}{'xyz'[a]}"
                if faces is not None and key not in faces:
                    continue
                b, c = [k for k in range(3) if k != a]
                def samples(k):
                    if r == 0:
                        return np.array([-h[k], h[k]])
                    t = inner[k] + r * np.tan(phis)
                    return np.concatenate([-t[::-1], t if inner[k] > 1e-9 else t[1:]])
                sb, sc = samples(b), samples(c)
                B, C = np.meshgrid(sb, sc, indexing="ij")
                p = np.zeros(B.shape + (3,))
                p[..., a] = s * h[a]
                p[..., b] = B
                p[..., c] = C
                cl = np.clip(p, -inner, inner)
                d = p - cl
                ln = np.linalg.norm(d, axis=-1, keepdims=True)
                n = np.where(ln > 1e-12, d / np.maximum(ln, 1e-12), 0)
                if r == 0:
                    n = np.zeros_like(p)
                    n[..., a] = s
                    q = p
                else:
                    q = cl + r * n
                nb, nc = len(sb), len(sc)
                ii, jj = np.meshgrid(np.arange(nb - 1), np.arange(nc - 1), indexing="ij")
                v0 = (ii * nc + jj).ravel()
                t1 = np.stack([v0, v0 + nc, v0 + nc + 1], 1)
                t2 = np.stack([v0, v0 + nc + 1, v0 + 1], 1)
                T = np.concatenate([t1, t2])
                Q = q.reshape(-1, 3)
                Nn = n.reshape(-1, 3)
                e = np.cross(Q[T[:, 1]] - Q[T[:, 0]], Q[T[:, 2]] - Q[T[:, 0]])
                ref = Nn[T[:, 0]] + Nn[T[:, 1]] + Nn[T[:, 2]]
                flip = (e * ref).sum(1) < 0
                T[flip] = T[flip][:, [0, 2, 1]]
                Ps.append(Q + c0)
                Ns.append(Nn)
                Ts.append(T + base)
                base += len(Q)
        self.add(mat, np.concatenate(Ps), np.concatenate(Ns), np.concatenate(Ts))

    def box(self, mat, center, size, faces=None):
        self.rbox(mat, center, size, r=0.0, faces=faces)

    def box_between(self, mat, lo, hi, r=0.0, seg=2):
        lo, hi = np.asarray(lo, float), np.asarray(hi, float)
        self.rbox(mat, (lo + hi) / 2, hi - lo, r=r, seg=seg)

    def lathe(self, mat, profile, base=(0, 0, 0), axis=(0, 0, 1), seg=32, smooth=True):
        """Surface of revolution of profile [(radius, z)] (ordered bottom->top) about axis through base."""
        pr = np.asarray(profile, float)
        R = frame_from_axis(axis)
        th = np.linspace(0, 2 * math.pi, seg + 1)
        Ps, Ns, Ts = [], [], []
        base_i = 0
        # profile normals (2D): perpendicular to tangent, pointing outward (+r side)
        tang = np.gradient(pr, axis=0) if smooth else None
        for k in range(len(pr) - 1):
            r0, z0 = pr[k]
            r1, z1 = pr[k + 1]
            if smooth:
                t0, t1 = tang[k], tang[k + 1]
            else:
                t0 = t1 = pr[k + 1] - pr[k]
            n0 = np.array([t0[1], -t0[0]])
            n1 = np.array([t1[1], -t1[0]])
            n0 /= np.linalg.norm(n0) + 1e-12
            n1 /= np.linalg.norm(n1) + 1e-12
            if not smooth:
                pass
            ct, st = np.cos(th), np.sin(th)
            P0 = np.stack([r0 * ct, r0 * st, np.full_like(th, z0)], 1)
            P1 = np.stack([r1 * ct, r1 * st, np.full_like(th, z1)], 1)
            N0 = np.stack([n0[0] * ct, n0[0] * st, np.full_like(th, n0[1])], 1)
            N1 = np.stack([n1[0] * ct, n1[0] * st, np.full_like(th, n1[1])], 1)
            P = np.concatenate([P0, P1])
            N = np.concatenate([N0, N1])
            m = seg + 1
            i = np.arange(seg)
            T = np.concatenate([np.stack([i, i + 1, m + i + 1], 1), np.stack([i, m + i + 1, m + i], 1)])
            e = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
            ref = N[T[:, 0]] + N[T[:, 1]] + N[T[:, 2]]
            flip = (e * ref).sum(1) < 0
            T[flip] = T[flip][:, [0, 2, 1]]
            Ps.append(P)
            Ns.append(N)
            Ts.append(T + base_i)
            base_i += len(P)
        P = np.concatenate(Ps) @ R.T + np.asarray(base, float)
        N = np.concatenate(Ns) @ R.T
        self.add(mat, P, N, np.concatenate(Ts))

    def disk(self, mat, center, radius, normal=(0, 0, 1), seg=32, r_in=0.0):
        R = frame_from_axis(normal)
        th = np.linspace(0, 2 * math.pi, seg + 1)[:-1]
        if r_in <= 0:
            P = np.concatenate([[[0, 0, 0]], np.stack([radius * np.cos(th), radius * np.sin(th), 0 * th], 1)])
            T = np.array([[0, 1 + i, 1 + (i + 1) % seg] for i in range(seg)])
        else:
            outer = np.stack([radius * np.cos(th), radius * np.sin(th), 0 * th], 1)
            inner = np.stack([r_in * np.cos(th), r_in * np.sin(th), 0 * th], 1)
            P = np.concatenate([outer, inner])
            T = np.array([t for i in range(seg) for t in ([i, (i + 1) % seg, seg + (i + 1) % seg],
                                                         [i, seg + (i + 1) % seg, seg + i])])
        P = P @ R.T + np.asarray(center, float)
        N = np.tile(R[:, 2], (len(P), 1))
        self.add(mat, P, N, T)

    def cyl(self, mat, p0, p1, radius, seg=32, caps=True, r_edge=0.0):
        p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
        L = np.linalg.norm(p1 - p0)
        ax = (p1 - p0) / L
        if r_edge > 0:
            re = min(r_edge, radius * 0.5, L * 0.5)
            prof = [(0.0, 0.0)] if caps else []
            prof += [(radius - re + re * math.sin(a), re - re * math.cos(a)) for a in np.linspace(0, math.pi / 2, 4)]
            prof += [(radius - re + re * math.cos(a), L - re + re * math.sin(a)) for a in np.linspace(0, math.pi / 2, 4)]
            if caps:
                prof += [(0.0, L)]
            self.lathe(mat, prof, p0, ax, seg, smooth=False)
            return
        self.lathe(mat, [(radius, 0.0), (radius, L)], p0, ax, seg, smooth=False)
        if caps:
            self.disk(mat, p0, radius, -ax, seg)
            self.disk(mat, p1, radius, ax, seg)

    def sphere(self, mat, c, r, seg=24):
        prof = [(r * math.sin(a), -r * math.cos(a)) for a in np.linspace(0, math.pi, seg // 2 + 1)]
        self.lathe(mat, prof, c, (0, 0, 1), seg)

    def tube(self, mat, pts, radius, seg=12, caps=False):
        """Swept circular tube along a polyline (parallel-transport frames). Use bend() for rounded corners."""
        pts = np.asarray(pts, float)
        tang = np.gradient(pts, axis=0)
        tang /= np.linalg.norm(tang, axis=1, keepdims=True)
        R0 = frame_from_axis(tang[0])
        u = R0[:, 0]
        rings, norms = [], []
        th = np.linspace(0, 2 * math.pi, seg + 1)
        for i, p in enumerate(pts):
            t = tang[i]
            u = u - t * (u @ t)
            u /= np.linalg.norm(u)
            v = np.cross(t, u)
            n = np.outer(np.cos(th), u) + np.outer(np.sin(th), v)
            rings.append(p + radius * n)
            norms.append(n)
        P = np.concatenate(rings)
        N = np.concatenate(norms)
        m = seg + 1
        T = []
        for k in range(len(pts) - 1):
            i = np.arange(seg) + k * m
            T.append(np.stack([i, i + m, i + m + 1], 1))
            T.append(np.stack([i, i + m + 1, i + 1], 1))
        T = np.concatenate(T)
        e = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
        flip = (e * N[T[:, 0]]).sum(1) < 0
        T[flip] = T[flip][:, [0, 2, 1]]
        self.add(mat, P, N, T)
        if caps:
            self.disk(mat, pts[0], radius, -tang[0], seg)
            self.disk(mat, pts[-1], radius, tang[-1], seg)

    def extrude(self, mat, profile, p0, p1, up=(0, 0, 1), caps=True, smooth_deg=35.0):
        """Prism of a 2D CCW profile (u, v) swept from p0 to p1. u = up x axis, v = up projected (profile 'y')."""
        p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
        w = (p1 - p0) / np.linalg.norm(p1 - p0)
        vv = np.asarray(up, float) - w * (np.asarray(up, float) @ w)
        if np.linalg.norm(vv) < 1e-6:
            vv = frame_from_axis(w)[:, 1]
        vv /= np.linalg.norm(vv)
        uu = np.cross(vv, w)
        pr = np.asarray(profile, float)
        n = len(pr)
        Ps, Ns, Ts = [], [], []
        base = 0
        # edge normals (outward for CCW profile in (u, v))
        en = []
        for i in range(n):
            d = pr[(i + 1) % n] - pr[i]
            nn = np.array([d[1], -d[0]])
            en.append(nn / (np.linalg.norm(nn) + 1e-12))
        en = np.array(en)
        cosmax = math.cos(math.radians(smooth_deg))
        for i in range(n):
            j = (i + 1) % n
            ni = en[i]
            # smooth with neighbours when the turn is small (rounded corners)
            na, nb = ni.copy(), ni.copy()
            if en[i - 1] @ ni > cosmax:
                na = (en[i - 1] + ni) / np.linalg.norm(en[i - 1] + ni)
            if en[j] @ ni > cosmax:
                nb = (en[j] + ni) / np.linalg.norm(en[j] + ni)
            q = [pr[i], pr[j]]
            P = np.array([p0 + q[0][0] * uu + q[0][1] * vv, p0 + q[1][0] * uu + q[1][1] * vv,
                          p1 + q[1][0] * uu + q[1][1] * vv, p1 + q[0][0] * uu + q[0][1] * vv])
            N3 = [na[0] * uu + na[1] * vv, nb[0] * uu + nb[1] * vv]
            N = np.array([N3[0], N3[1], N3[1], N3[0]])
            T = np.array([[0, 1, 2], [0, 2, 3]])
            e = np.cross(P[1] - P[0], P[2] - P[0])
            if e @ (N3[0] + N3[1]) < 0:
                T = T[:, [0, 2, 1]]
            Ps.append(P)
            Ns.append(N)
            Ts.append(T + base)
            base += 4
        if caps:
            tri = np.array(earclip(pr))
            for end, sgn in ((p0, -1), (p1, 1)):
                P = np.array([end + q[0] * uu + q[1] * vv for q in pr])
                N = np.tile(sgn * w, (n, 1))
                T = tri.copy()
                e = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
                flip = (e @ (sgn * w)) < 0
                T[flip] = T[flip][:, [0, 2, 1]]
                Ps.append(P)
                Ns.append(N)
                Ts.append(T + base)
                base += n
        self.add(mat, np.concatenate(Ps), np.concatenate(Ns), np.concatenate(Ts))

    def quad(self, mat, center, normal, up, w, h, uv=(0, 0, 1, 1)):
        """Flat rectangle facing `normal` with explicit UVs (decals, screens, labels)."""
        n = np.asarray(normal, float)
        n /= np.linalg.norm(n)
        upv = np.asarray(up, float) - n * (np.asarray(up, float) @ n)
        upv /= np.linalg.norm(upv)
        right = np.cross(upv, n)
        c = np.asarray(center, float)
        P = np.array([c - right * w / 2 - upv * h / 2, c + right * w / 2 - upv * h / 2,
                      c + right * w / 2 + upv * h / 2, c - right * w / 2 + upv * h / 2])
        UV = np.array([[uv[0], uv[1]], [uv[2], uv[1]], [uv[2], uv[3]], [uv[0], uv[3]]])
        T = np.array([[0, 1, 2], [0, 2, 3]])
        self.add(mat, P, np.tile(n, (4, 1)), T, UV)

    def decal(self, png, center, normal, up, w, h, emissive=0.0):
        """Textured label/sign/screen quad. png: path of a generated texture (absolute)."""
        key = ("screen:" if emissive > 0 else "decal:") + os.path.abspath(png) + (f"@{emissive}" if emissive else "")
        self.quad(key, center, normal, up, w, h)

    # ---------------------------------------------------------------- composites
    def profile_item(self, p0, p1, size=0.04, mat="AluAnodized", up=(0, 0, 1)):
        """item Line 8-style square aluminium profile with a groove in every side and chamfered corners (visual)."""
        a = size / 2
        sw, sd, ch = 0.008 * size / 0.04, 0.004 * size / 0.04, 0.0015
        corners = [np.array(c, float) for c in ((a, -a), (a, a), (-a, a), (-a, -a))]
        pts = []
        for k in range(4):
            c0, c1 = corners[k - 1], corners[k]
            d = (c1 - c0) / np.linalg.norm(c1 - c0)
            nrm = np.array([d[1], -d[0]])
            m = (c0 + c1) / 2
            pts.append(c0 + d * ch)
            for (s_, dep) in ((-sw / 2, 0), (-sw / 2, sd), (sw / 2, sd), (sw / 2, 0)):
                pts.append(m + d * s_ - nrm * dep)
            pts.append(c1 - d * ch)
        self.extrude(mat, _ccw(pts), p0, p1, up=up)

    def handle_bar(self, mat, center, length, axis=(0, 0, 1), standoff=0.03, r=0.006, normal=(0, -1, 0)):
        """Tubular cabinet/door handle: bar + two stand-offs, bar parallel to axis, offset along normal."""
        c = np.asarray(center, float)
        ax = np.asarray(axis, float) / np.linalg.norm(axis)
        nm = np.asarray(normal, float) / np.linalg.norm(normal)
        a, b = c - ax * length / 2 + nm * standoff, c + ax * length / 2 + nm * standoff
        self.cyl(mat, a, b, r, seg=16)
        for e in (a, b):
            self.cyl(mat, e - nm * standoff, e, r * 0.85, seg=12)

    # ---------------------------------------------------------------- output
    def write(self, stage, root, semantics=None, tex_rel_to=None):
        """Emit meshes/materials/colliders/frames under root (an existing or new Xform)."""
        if not stage.GetPrimAtPath(root):
            UsdGeom.Xform.Define(stage, root)
        layer_dir = os.path.dirname(stage.GetRootLayer().realPath)
        looks = UsdGeom.Scope.Define(stage, f"{root}/Looks").GetPrim()
        looks.GetReferences().AddReference(os.path.relpath(MATLIB, layer_dir), "/Looks")
        UsdGeom.Scope.Define(stage, f"{root}/Visual")
        ntri = 0
        dec = 0
        for key, plist in self.parts.items():
            P = np.concatenate([p[0] for p in plist])
            N = np.concatenate([p[1] for p in plist])
            Ts, UVs, off = [], [], 0
            for (p, n, uv, t) in plist:
                Ts.append(t + off)
                off += len(p)
                if uv is None:
                    UVs.append(_box_uv(p, n))
                else:
                    UVs.append(np.asarray(uv, float))
            T = np.concatenate(Ts)
            UV = np.concatenate(UVs)
            if key.startswith(("decal:", "screen:")):
                dec += 1
                name = f"Decal{dec:03d}"
            else:
                name = key
                UV = UV / TILE_M.get(key, 1.0)
            m = UsdGeom.Mesh.Define(stage, f"{root}/Visual/{name}")
            m.CreatePointsAttr(P.astype(np.float32))
            m.CreateNormalsAttr(N.astype(np.float32))
            m.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
            m.CreateFaceVertexCountsAttr(np.full(len(T), 3, np.int32))
            m.CreateFaceVertexIndicesAttr(T.astype(np.int32).ravel())
            m.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
            m.CreateExtentAttr([Gf.Vec3f(*P.min(0)), Gf.Vec3f(*P.max(0))])
            st = UsdGeom.PrimvarsAPI(m).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex)
            st.Set(UV.astype(np.float32))
            ntri += len(T)
            if key.startswith(("decal:", "screen:")):
                mat = _decal_material(stage, f"{root}/Looks/{name}Mat", key, layer_dir)
            else:
                mat = UsdShade.Material(stage.GetPrimAtPath(f"{root}/Looks/{key}"))
                if not mat:
                    raise KeyError(f"material {key} not in {MATLIB}")
            UsdShade.MaterialBindingAPI.Apply(m.GetPrim()).Bind(mat)
        if self.colliders:
            UsdGeom.Scope.Define(stage, f"{root}/Collision")
            for name, c, size, yaw in self.colliders:
                xf = UsdGeom.Xform.Define(stage, f"{root}/Collision/{name}")
                xf.AddTranslateOp().Set(Gf.Vec3d(*map(float, c)))
                if abs(yaw) > 1e-9:
                    xf.AddRotateZOp().Set(float(yaw))
                cube = UsdGeom.Cube.Define(stage, f"{root}/Collision/{name}/Box")
                cube.CreateSizeAttr(1.0)
                cube.AddScaleOp().Set(Gf.Vec3f(*map(float, size)))
                cube.CreatePurposeAttr(UsdGeom.Tokens.guide)
                UsdPhysics.CollisionAPI.Apply(cube.GetPrim())
        for name, M in self.frames.items():
            f = UsdGeom.Xform.Define(stage, f"{root}/{name}")
            f.AddTransformOp().Set(Gf.Matrix4d(*M.T.ravel().tolist()))
        if semantics:
            prim = stage.GetPrimAtPath(root)
            for k, v in semantics.items():
                typ = (Sdf.ValueTypeNames.StringArray if isinstance(v, (list, tuple)) else
                       Sdf.ValueTypeNames.Double if isinstance(v, float) else
                       Sdf.ValueTypeNames.Int if isinstance(v, int) and not isinstance(v, bool) else
                       Sdf.ValueTypeNames.Bool if isinstance(v, bool) else Sdf.ValueTypeNames.String)
                prim.CreateAttribute(k, typ, custom=True).Set(v)
        return ntri


def _ccw(pts):
    P = np.asarray(pts, float)
    # drop consecutive duplicates
    keep = [0] + [i for i in range(1, len(P)) if np.linalg.norm(P[i] - P[i - 1]) > 1e-7]
    P = P[keep]
    if np.linalg.norm(P[0] - P[-1]) < 1e-7:
        P = P[:-1]
    area = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    return P if area > 0 else P[::-1]


def _box_uv(P, N):
    """Box-projected UVs in metres; u runs horizontally on walls (brushing direction)."""
    ax = np.argmax(np.abs(N), axis=1)
    UV = np.empty((len(P), 2))
    m0, m1, m2 = ax == 0, ax == 1, ax == 2
    UV[m0] = P[m0][:, [1, 2]]
    UV[m1] = P[m1][:, [0, 2]]
    UV[m2] = P[m2][:, [0, 1]]
    return UV


def _decal_material(stage, path, key, layer_dir):
    kind, rest = key.split(":", 1)
    png, _, em = rest.partition("@")
    mat = UsdShade.Material.Define(stage, path)
    sh = UsdShade.Shader.Define(stage, f"{path}/Shader")
    sh.SetSourceAsset(Sdf.AssetPath("OmniPBR.mdl"), "mdl")
    sh.SetSourceAssetSubIdentifier("OmniPBR", "mdl")
    out = sh.CreateOutput("out", Sdf.ValueTypeNames.Token)
    mat.CreateSurfaceOutput("mdl").ConnectToSource(out)
    mat.CreateVolumeOutput("mdl").ConnectToSource(out)
    mat.CreateDisplacementOutput("mdl").ConnectToSource(out)
    rel = Sdf.AssetPath(os.path.relpath(png, layer_dir))
    sh.CreateInput("diffuse_texture", Sdf.ValueTypeNames.Asset).Set(rel)
    if kind == "screen":
        sh.CreateInput("reflection_roughness_constant", Sdf.ValueTypeNames.Float).Set(0.08)
        sh.CreateInput("enable_emission", Sdf.ValueTypeNames.Bool).Set(True)
        sh.CreateInput("emissive_color_texture", Sdf.ValueTypeNames.Asset).Set(rel)
        sh.CreateInput("emissive_color", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1, 1, 1))
        sh.CreateInput("emissive_intensity", Sdf.ValueTypeNames.Float).Set(float(em))
    else:
        sh.CreateInput("reflection_roughness_constant", Sdf.ValueTypeNames.Float).Set(0.45)
    return mat


def new_asset(path, root="Asset", comment=""):
    if os.path.exists(path):
        os.remove(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    st = Usd.Stage.CreateNew(path)
    UsdGeom.SetStageUpAxis(st, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(st, 1.0)
    st.SetMetadata("comment", comment or "Generated - edit the build script, not this file.")
    xf = UsdGeom.Xform.Define(st, f"/{root}")
    st.SetDefaultPrim(xf.GetPrim())
    return st, f"/{root}"
