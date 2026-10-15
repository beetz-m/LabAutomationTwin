"""Generic URDF serial-chain kinematics (numpy): forward kinematics, numerical Jacobian and damped-least-squares IK.

Used for offline planning where the simulator is not running (R02: rail + UR5e). The FK follows the URDF exactly
(joint origins rpy = Rz(yaw) Ry(pitch) Rx(roll), then the joint motion about/along its axis), so it matches what
Isaac Sim's URDF importer builds from the same file.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET

import numpy as np


def rpy_xyz(rpy, xyz):
    r, p, y = rpy
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    T = np.eye(4)
    T[:3, :3] = np.array([[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                          [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                          [-sp, cp * sr, cp * cr]])
    T[:3, 3] = xyz
    return T


def rot_axis(axis, q):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    T = np.eye(4)
    T[:3, :3] = np.eye(3) + math.sin(q) * K + (1 - math.cos(q)) * K @ K
    return T


def trans_axis(axis, d):
    T = np.eye(4)
    T[:3, 3] = np.asarray(axis, float) * d
    return T


class UrdfChain:
    """The serial chain from `base` to `tip` link of a URDF; q holds the movable joints in chain order."""

    def __init__(self, urdf_path, base, tip):
        joints = {j.find("child").get("link"): j for j in ET.parse(urdf_path).getroot().findall("joint")}
        chain, link = [], tip
        while link != base:
            if link not in joints:
                raise ValueError(f"{tip} is not below {base}")
            chain.append(joints[link])
            link = joints[link].find("parent").get("link")
        self.chain = []
        for j in reversed(chain):
            o = j.find("origin")
            To = rpy_xyz([float(v) for v in (o.get("rpy") or "0 0 0").split()] if o is not None else [0, 0, 0],
                         [float(v) for v in (o.get("xyz") or "0 0 0").split()] if o is not None else [0, 0, 0])
            ax = j.find("axis")
            axis = [float(v) for v in ax.get("xyz").split()] if ax is not None else [1, 0, 0]
            lim = j.find("limit")
            typ = j.get("type")
            lims = (float(lim.get("lower")), float(lim.get("upper"))) if lim is not None and typ != "continuous" \
                else (-2 * math.pi, 2 * math.pi)
            self.chain.append((j.get("name"), typ, To, axis, lims))
        self.names = [c[0] for c in self.chain if c[1] != "fixed"]
        self.limits = np.array([c[4] for c in self.chain if c[1] != "fixed"])

    def frames(self, q):
        """Transforms of every joint's child frame (after its motion), and the tip."""
        T, k, out = np.eye(4), 0, []
        for name, typ, To, axis, _ in self.chain:
            T = T @ To
            if typ in ("revolute", "continuous"):
                T = T @ rot_axis(axis, q[k])
                k += 1
            elif typ == "prismatic":
                T = T @ trans_axis(axis, q[k])
                k += 1
            out.append((name, T.copy()))
        return out

    def fk(self, q, tool=None):
        T = self.frames(q)[-1][1]
        return T @ tool if tool is not None else T

    def jacobian(self, q, tool=None, eps=1e-6):
        T = self.fk(q, tool)
        J = np.zeros((6, len(q)))
        for k in range(len(q)):
            dq = np.zeros(len(q))
            dq[k] = eps
            T2 = self.fk(q + dq, tool)
            J[:3, k] = (T2[:3, 3] - T[:3, 3]) / eps
            Rd = T2[:3, :3] @ T[:3, :3].T
            J[3:, k] = np.array([Rd[2, 1] - Rd[1, 2], Rd[0, 2] - Rd[2, 0], Rd[1, 0] - Rd[0, 1]]) / (2 * eps)
        return J

    def margin(self, q, active=None):
        idx = range(len(q)) if active is None else active
        return float(min(min(q[i] - self.limits[i, 0], self.limits[i, 1] - q[i]) for i in idx))

    def ik(self, p, R, q0, active=None, tool=None, iters=200, damping=1e-3, tol=(1e-4, math.radians(0.05))):
        """DLS IK to position p and rotation R (3x3); `active` lists the joint indices allowed to move."""
        q = np.array(q0, float)
        act = list(range(len(q))) if active is None else list(active)
        lo, hi = self.limits[:, 0], self.limits[:, 1]
        for _ in range(iters):
            T = self.fk(q, tool)
            e = np.concatenate([p - T[:3, 3], 0.5 * sum(np.cross(T[:3, i], R[:, i]) for i in range(3))])
            if np.linalg.norm(e[:3]) < tol[0] and np.linalg.norm(e[3:]) < tol[1]:
                return q
            J = self.jacobian(q, tool)[:, act]
            dq = J.T @ np.linalg.solve(J @ J.T + damping * np.eye(6), e)
            q[act] = np.clip(q[act] + dq, lo[act], hi[act])
        return None

    def sigma_min(self, q, active=None, tool=None):
        J = self.jacobian(q, tool)
        if active is not None:
            J = J[:, list(active)]
        return float(np.linalg.svd(J, compute_uv=False)[-1])
