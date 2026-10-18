"""Knowledge base of the robot science assistant kernel (KERNEL.md concept 6).

One source: the facts the clingo planner reads (``okf/lab-automation-twin/build/e2m/facts_<tag>.lp``, generated from
the OKF ABoxes by ``derive_plan.facts``), Cell 01's component records (capabilities, action contracts, monitors,
failure modes; read-only from ResearchSpace) and the kernel registries (``rsa/registry/*.yaml``).

Every resolution query returns an :class:`Answer` carrying its **grounds** (the fact atoms and record fields used) and
the alternatives it rejected, so the audit trail and the competency questions can say *why* a value was chosen.
"""

from __future__ import annotations

import copy
import os
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FACTS_DIR = os.path.join(REPO, "okf", "lab-automation-twin", "build", "e2m")
PLAN_DIR = os.path.join(REPO, "okf", "lab-automation-twin", "L3-logical-axiomatization", "derivation", "out")
C01_COMPONENTS = os.path.expanduser(
    "~/ResearchSpace/projects/robot-scientist/cell-01/AICOR_Cell01_Codex_Handoff/sdt/components")
REGISTRY = os.path.join(HERE, "registry")

#: kernel atom -> Cell 01 component record (the canonical component ids, D012/D014)
COMPONENT_FILES = dict(h4="H4_Quarantine", l09="L09_PlateHotel", l10="L10_Incubator", l12="L12_LiquidHandler",
                       l17="L17_BrightFieldImager", l21="L21_QC_Calibration", r01="R01_FR3_PlateArm",
                       r02="R02_RailMounted_UR5e", r03="R03_AMR_H2_Dock", automatictoolchanger="ToolChanger_Magazine")

Atom = Tuple[Any, ...]


def parse_facts(text: str) -> set:
    out = set()
    for line in text.splitlines():
        line = line.split("%")[0].strip()
        if not line:
            continue
        for stmt in re.findall(r"([a-z_][a-z0-9_]*(?:\([^)]*\))?)\.", line):
            m = re.match(r"([a-z_][a-z0-9_]*)(?:\((.*)\))?$", stmt)
            args = tuple(int(a) if re.fullmatch(r"-?\d+", a) else a for a in (m.group(2).split(",") if m.group(2) else []))
            out.add((m.group(1),) + args)
    return out


def fmt(a: Atom) -> str:
    return a[0] + ("(" + ",".join(str(x) for x in a[1:]) + ")" if len(a) > 1 else "")


@dataclass
class Answer:
    """A resolution result with its grounds (KnowRob3 ClimbStep / JAIR resolution certificate, kernel concept 5)."""
    query: str
    value: Any
    grounds: List[str] = field(default_factory=list)
    rejected: List[Tuple[Any, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.value is not None and self.value != []

    def as_dict(self) -> Dict[str, Any]:
        return dict(query=self.query, value=self.value, grounds=list(self.grounds),
                    rejected=[[str(a), r] for a, r in self.rejected])


class Unresolved(Exception):
    def __init__(self, answer: Answer):
        super().__init__(f"unresolved: {answer.query}")
        self.answer = answer


class KB:
    def __init__(self, facts: set, components: Dict[str, dict], registry: Dict[str, Any], name: str):
        self.facts, self.components, self.registry, self.name = facts, components, registry, name

    # ------------------------------------------------------------------------------------------------ loading
    @classmethod
    def load(cls, tag: str = "g050") -> "KB":
        facts = parse_facts(open(os.path.join(FACTS_DIR, f"facts_{tag}.lp")).read())
        comps = {}
        for a, f in COMPONENT_FILES.items():
            p = os.path.join(C01_COMPONENTS, f + ".yaml")
            if os.path.exists(p):
                comps[a] = yaml.safe_load(open(p))
        reg = {}
        for f in sorted(os.listdir(REGISTRY)):
            if f.endswith(".yaml"):
                reg[f[:-5]] = yaml.safe_load(open(os.path.join(REGISTRY, f)))
        # twin-side extensions of component records (ILLUSTRATIVE, labelled in the registry)
        for dev, ext in (reg.get("devices") or {}).get("extensions", {}).items():
            comps.setdefault(dev, {}).setdefault("_twin", {}).update(ext)
        return cls(facts, comps, reg, f"facts_{tag}")

    def derive(self, name: str, add: Iterable[str] = (), remove: Iterable[str] = (),
               components: Optional[Dict[str, dict]] = None) -> "KB":
        """A scenario variant: knowledge changes, plan code does not (WP4)."""
        f = set(self.facts)
        f -= parse_facts("".join(r if r.endswith(".") else r + "." for r in remove))
        f |= parse_facts("".join(a if a.endswith(".") else a + "." for a in add))
        comps = copy.deepcopy(self.components)
        for dev, rec in (components or {}).items():
            comps[dev] = rec
        return KB(f, comps, self.registry, name)

    # ------------------------------------------------------------------------------------------------ queries
    def q(self, pred: str, *pat) -> List[Atom]:
        return sorted((a for a in self.facts if a[0] == pred and len(a) == len(pat) + 1
                       and all(p is None or p == x for p, x in zip(pat, a[1:]))), key=str)

    def holds(self, pred: str, *args) -> bool:
        return (pred,) + tuple(args) in self.facts

    def one(self, pred: str, *pat) -> Optional[Atom]:
        r = self.q(pred, *pat)
        return r[0] if r else None

    def capabilities(self, dev: str) -> List[str]:
        rec = self.components.get(dev) or {}
        return list(rec.get("capabilities") or []) + list((rec.get("_twin") or {}).get("capabilities", []))

    def contract(self, dev: str, name: str) -> Optional[dict]:
        return next((c for c in (self.components.get(dev) or {}).get("action_contracts") or [] if c["name"] == name), None)

    # ------------------------------------------------------------------------------------------------ resolution
    def devices_for(self, functions: List[str], capabilities: List[str]) -> Answer:
        """Automated devices that have every required function and capability verb."""
        q = f"devices_for(functions={functions}, capabilities={capabilities})"
        ok, grounds, rejected = [], [], []
        devs = sorted({a[1] for a in self.q("automated", None)})
        for d in devs:
            miss_f = [f for f in functions if not self.holds("has_function", d, f)]
            caps = self.capabilities(d)
            miss_c = [c for c in capabilities if c not in caps]
            if miss_f or miss_c:
                if any(self.holds("has_function", d, f) for f in functions):
                    rejected.append((d, f"lacks function {miss_f}" if miss_f else
                                     f"component record lacks capability {miss_c}"))
                continue
            ok.append(d)
            grounds += [f"automated({d})"] + [f"has_function({d},{f})" for f in functions] + \
                       [f"component:{COMPONENT_FILES.get(d, d)}.capabilities∋{c}" for c in capabilities]
        return Answer(q, ok, grounds, rejected)

    def seat(self, station: str) -> Answer:
        a = self.one("seat", station, None)
        return Answer(f"seat({station})", a[2] if a else None, [fmt(a)] if a else [])

    def route(self, src: str, dst: str) -> Answer:
        """Shortest station-to-station route; each leg by one robot that serves both plate-holding stations."""
        q = f"route({src},{dst})"
        if src == dst:
            return Answer(q, [], [])
        holders = {a[1] for a in self.q("holds_plate", None)}
        serves = {}
        for _, r, v in self.q("serves", None, None):
            serves.setdefault(r, set()).add(v)
        prev, seen, dq = {}, {src}, deque([src])
        while dq:
            u = dq.popleft()
            for r in sorted(serves):
                if u not in serves[r]:
                    continue
                for v in sorted(serves[r] & holders):
                    if v not in seen:
                        seen.add(v)
                        prev[v] = (u, r)
                        dq.append(v)
        if dst not in prev:
            return Answer(q, None, [], [(dst, "no robot chain over servesStation reaches it")])
        legs, v = [], dst
        while v != src:
            u, r = prev[v]
            legs.append((r, u, v))
            v = u
        legs.reverse()
        grounds = []
        for r, u, v in legs:
            grounds += [f"serves({r},{u})", f"serves({r},{v})", f"holds_plate({u})", f"holds_plate({v})"]
        return Answer(q, legs, grounds)

    def tool_for(self, robot: str) -> Answer:
        a = self.one("requires_tool", robot, None)
        if not a:
            return Answer(f"tool_for({robot})", "none", [f"not requires_tool({robot},_)"])
        p = self.one("tool_pose", a[2], None)
        return Answer(f"tool_for({robot})", (a[2], p[2] if p else None), [fmt(a)] + ([fmt(p)] if p else []))

    def well_pose(self, well: str, purpose: str) -> Answer:
        a = self.one("well_pose", well.lower(), purpose, None)
        return Answer(f"well_pose({well},{purpose})", a[3] if a else None, [fmt(a)] if a else [])

    def reagent_pose(self, reagent: str) -> Answer:
        a = self.one("reagent_pose", reagent, None)
        return Answer(f"reagent_pose({reagent})", a[2] if a else None, [fmt(a)] if a else [],
                      [] if a else [(reagent, "no reagent_pose fact: reagent not bound to a rack position")])

    def frame(self, pred: str, dev: str) -> Answer:
        a = self.one(pred, dev, None)
        return Answer(f"{pred}({dev})", a[2] if a else None, [fmt(a)] if a else [])

    def staging_for(self, dev: str) -> Answer:
        """A passive plate-holding station where a plate can wait while `dev` is busy: holds_plate, not automated,
        reachable by a robot that serves `dev`."""
        q = f"staging_for({dev})"
        for a in self.q("holds_plate", None):
            x = a[1]
            if x == dev or self.holds("automated", x):
                continue
            r = next((b[1] for b in self.q("serves", None, x) if self.holds("serves", b[1], dev)), None)
            if r:
                return Answer(q, x, [fmt(a), f"not automated({x})", f"serves({r},{x})", f"serves({r},{dev})"])
        return Answer(q, None, [], [(dev, "no passive plate station shared with a robot serving it")])

    def qc_station_for(self, dev: str) -> Answer:
        a = self.one("qc_station", None, dev)
        return Answer(f"qc_station_for({dev})", a[1] if a else None, [fmt(a)] if a else [])

    def home(self) -> Answer:
        a = self.one("home", None)
        return Answer("home", a[1] if a else None, [fmt(a)] if a else [])

    def interlock_monitor(self) -> Answer:
        a = self.one("interlock_monitor", None)
        return Answer("interlock_monitor", a[1] if a else None, [fmt(a)] if a else [])

    def measurement_binding(self, dev: str, readout: str) -> Answer:
        """Binding lattice no_match ⊂ capability_match ⊂ provisional ⊂ validated (RSV scene binding)."""
        model = ((self.components.get(dev) or {}).get("identity") or {}).get("component_id", dev)
        b = ((self.registry.get("devices") or {}).get("measurement_bindings") or {}).get(model, {}).get(readout)
        caps = self.capabilities(dev)
        if b is None:
            lvl = "capability_match" if "image_well" in caps else "no_match"
            return Answer(f"measurement_binding({dev},{readout})", lvl,
                          [f"component {model}: capabilities∋image_well, no validated binding for {readout}"
                           if lvl != "no_match" else f"component {model}: no capability for {readout}"])
        return Answer(f"measurement_binding({dev},{readout})", b["level"], [f"registry:devices.measurement_bindings."
                                                                         f"{model}.{readout} ({b.get('source', '')})"])

    # ------------------------------------------------------------------------------------------------ durations (s)
    def duration(self, kind: str, device: Optional[str] = None, robot: Optional[str] = None) -> float:
        if robot is not None:
            a = self.one("leg_part", robot, kind, None)
            if a:
                return a[3] / 10.0
        if device is not None:
            a = self.one("ddur", device, kind, None)
            if a:
                return a[3] / 10.0
        a = self.one("dur", kind, None)
        return a[2] / 10.0 if a else 0.0

    def window_s(self) -> Tuple[float, int]:
        w, m = self.one("window", None), self.one("margin_pct", None)
        return (w[1] / 10.0 if w else 600.0), (m[1] if m else 20)
