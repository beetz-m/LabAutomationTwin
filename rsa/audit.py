"""The audit trail: one hash-chained commitment record per designator lifecycle transition (KERNEL.md concept 10).

Consolidates
  * uc_ccr ``common/audit.py`` (CRAM tryout): SHA-256 over prev-hash + canonical JSON, GENESIS, verify(); the
    two-column constraint verdicts (``column`` realization | validity) -- the hash rule is kept unchanged;
  * Cell 01 ``neem_record_schema.yaml``: lifecycle sections (open, grounded, commitment/accepted, execution,
    monitors, failures, repairs, verdict, routing) become ``transition`` values of entries;
  * VRB warrant entry ⟨grounds, constraints discharged, verdict, disposition⟩: ``resolutions`` (grounds),
    ``constraints``, ``monitors``/``evidence``, ``reason``/``repair``;
  * ALCOA+ attributable/contemporaneous/original as audit fields: ``agent``, ``software``, ``t_sim``,
    evidence ``sha256``.
Written by the runtime (executor hooks), never by plans, so a plan cannot skip it (VRB C-D1).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

GENESIS = "0" * 64
EPOCH = "2026-10-17T08:00:00"


def _hash(prev: str, content: Dict[str, Any]) -> str:
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256((prev + canonical).encode("utf-8")).hexdigest()


def _iso(sim_s: float) -> str:
    date, clock = EPOCH.split("T")
    h, m, s = (int(p) for p in clock.split(":"))
    total = h * 3600 + m * 60 + s + sim_s
    days, rem = divmod(int(total), 86400)
    hh, rem = divmod(rem, 3600)
    mm, ss = divmod(rem, 60)
    return f"{date}+{days}d T{hh:02d}:{mm:02d}:{ss:02d}" if days else f"{date}T{hh:02d}:{mm:02d}:{ss:02d}"


class AuditTrail:
    def __init__(self, run: str, software: Dict[str, str]):
        self.run, self.software = run, software
        self.entries: List[Dict[str, Any]] = []
        self.hashes: List[str] = []

    def record(self, ctx, node, transition: str, **kw) -> Dict[str, Any]:
        d = node.designator
        agent = getattr(d, "robot", None) or getattr(d, "device", None) or "rsa-kernel (manipulation executive)"
        content = dict(seq=len(self.entries), t_sim=round(ctx.clock, 2), t=_iso(ctx.clock), designator=node.uid,
                       parent=node.parent.uid if node.parent else None, kind=d.KIND, category=d.category,
                       transition=transition, agent=agent, software=self.software)
        if transition == "open" or d.KIND != "action":
            content["hadl"] = d.hadl()
        if transition == "grounded":
            content["bindings"] = d.bindings()
            content["resolutions"] = [a.as_dict() for a in node.resolutions]
            if getattr(node, "bound_device", None):
                content["bound_device"] = node.bound_device
        if d.KIND != "action":
            content["term"] = d.term()
        for k, v in kw.items():
            if v is not None:
                content[k] = v
        prev = self.hashes[-1] if self.hashes else GENESIS
        h = _hash(prev, content)
        self.entries.append(content)
        self.hashes.append(h)
        return content

    def as_dict(self) -> Dict[str, Any]:
        return dict(run=self.run, genesis=GENESIS, software=self.software, n=len(self.entries),
                    entries=[{**e, "prev": (self.hashes[i - 1] if i else GENESIS), "hash": h}
                             for i, (e, h) in enumerate(zip(self.entries, self.hashes))])


def verify(trail: Dict[str, Any]) -> Dict[str, Any]:
    """Recompute the chain from a serialised trail; report the first broken entry (tamper evidence)."""
    prev = trail.get("genesis", GENESIS)
    for e in trail["entries"]:
        content = {k: v for k, v in e.items() if k not in ("prev", "hash")}
        if e.get("prev") != prev or _hash(prev, content) != e.get("hash"):
            return dict(ok=False, first_bad_seq=e.get("seq"))
        prev = e["hash"]
    fields_ok = all(e.get("agent") and e.get("software") and "t_sim" in e for e in trail["entries"])
    ev_ok = all(ev.get("sha256") for e in trail["entries"] for ev in e.get("evidence", []) or [])
    return dict(ok=True, n=len(trail["entries"]), attributable=fields_ok, evidence_hashed=ev_ok)
