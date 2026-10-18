"""Generalized plans of the kernel's action categories (KERNEL.md §2).

Plans name categories and requirements, never devices, robots or poses: those are bound at perform time by knowledge
base queries (``ctx.resolve``), against the current belief. The same code runs every scenario; only knowledge and the
world change (WP4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .checks import airspace_policy, window_policy
from .core import ActionDesignator, Command, Context, Designator, Failure, Motion, Plate, Recovery
from .kb import Answer

FUNCTION_OF = dict(dose=(["dispensing"], ["dose_well"]), image=(["imaging"], ["image_well"]))


def plate_location(ctx: Context, plate: Plate) -> str:
    at = ctx.belief.get(f"plate_at:{plate.id}")
    ctx.node.resolutions.append(Answer(f"plate_at({plate.id})", at, [f"belief plate_at:{plate.id} "
                                                                    f"({ctx.belief.source(f'plate_at:{plate.id}')})"]))
    return at


def device_here(ctx: Context, kind: str, plate: Plate) -> str:
    """A device capable of `kind` at which the plate currently is (resolution against knowledge and belief)."""
    fns, caps = FUNCTION_OF[kind]
    ans = ctx.kb.devices_for(fns, caps)
    at = str(plate_location(ctx, plate)).split(":")[-1]
    here = [d for d in (ans.value or []) if d == at]
    rej = ans.rejected + [(d, f"plate is at {at}") for d in (ans.value or []) if d != at]
    return ctx.resolve(Answer(ans.query + f" ∧ plate_at={at}", here[0] if here else None, ans.grounds, rej))


# ======================================================================================== scientific level
@dataclass(eq=False)
class Experiment(ActionDesignator):
    CATEGORY = "experiment"
    design: str = ""
    requirement_bits: float = 0.0
    eig_bits: float = 0.0
    plate: Optional[Plate] = None
    wells: Dict[str, List[str]] = field(default_factory=dict)
    sessions: List[Dict[str, Any]] = field(default_factory=list)

    def objects(self):
        return dict(design=self.design, plate=self.plate.id, wells=self.wells)

    def plan(self, ctx):
        out: List[Designator] = []
        t = 0.0
        for s in self.sessions:
            if s["t_h"] > t:
                out.append(Wait(until_h=s["t_h"], plate=self.plate))
                t = s["t_h"]
            out.append(RunSession(session=s["session"], trip=s["trip"], t_h=s["t_h"], plate=self.plate,
                                  material=[tuple(m) for m in s["material"]], roles=self.wells))
        return out


@dataclass(eq=False)
class Wait(ActionDesignator):
    CATEGORY = "wait"
    until_h: float = 0.0
    plate: Optional[Plate] = None

    def plan(self, ctx):
        home = ctx.resolve(ctx.kb.home())
        return [Command(command="incubate", device=home, args=(self.until_h,))]


@dataclass(eq=False)
class Intervene(ActionDesignator):
    CATEGORY = "intervene"
    plate: Optional[Plate] = None
    well: str = ""
    reagent: str = ""
    dose_au: float = 0.0
    role: str = ""

    def plan(self, ctx):
        conc = ctx.kb.registry["devices"]["reagents"][self.reagent]["conc_au_per_uL"]
        return [Dose(plate=self.plate, well=self.well, reagent=self.reagent, volume_uL=round(self.dose_au / conc, 3),
                     dose_au=self.dose_au)]


@dataclass(eq=False)
class Measure(ActionDesignator):
    CATEGORY = "measure"
    plate: Optional[Plate] = None
    well: str = ""
    role: str = ""

    def plan(self, ctx):
        return [Image(plate=self.plate, well=self.well)]


# ======================================================================================== lab-task level
@dataclass(eq=False)
class RunSession(ActionDesignator):
    CATEGORY = "run_session"
    session: str = ""
    trip: int = 1
    t_h: float = 0.0
    plate: Optional[Plate] = None
    material: List[tuple] = field(default_factory=list)
    roles: Dict[str, List[str]] = field(default_factory=dict)

    def _role(self, well):
        return next((r for r, ws in self.roles.items() if well.upper() in [w.upper() for w in ws]), "")

    def plan(self, ctx):
        kb = ctx.kb
        # F2 (iteration 1): robot/device state observed in an earlier session is stale -- the cell may have been used
        # in between (hours apart); it is re-established, not assumed (planner: tool symbolic at trip start).
        ctx.belief.stale(("tool:", "pose:", "shuttle:", "loaded:"), f"session {self.session} start")
        home = ctx.resolve(kb.home())
        kinds = sorted({m[0] for m in self.material})
        fns = sorted({f for k in kinds for f in FUNCTION_OF[k][0]})
        caps = sorted({c for k in kinds for c in FUNCTION_OF[k][1]})
        devs = ctx.resolve(kb.devices_for(fns, caps))
        dev = devs[0]
        ctx.node.bound_device = dev
        sci: List[Designator] = []
        for m in self.material:
            if m[0] == "dose":
                sci.append(Intervene(plate=self.plate, well=m[1].upper(), reagent=m[2], dose_au=m[3] / 100.0,
                                     role=self._role(m[1])))
            else:
                sci.append(Measure(plate=self.plate, well=m[1].upper(), role=self._role(m[1])))
        mon = ctx.resolve(kb.interlock_monitor())
        prep: List[Designator] = []
        if "image" in kinds and not ctx.belief.get(f"calibrated:{dev}"):
            # F11: the reference plate needs the imager's stage, so QC precedes the plate's release from home
            prep.append(Calibrate(target=dev))
        return [*prep, Command(command="check_interlocks", device=mon), Retrieve(plate=self.plate, source=home),
                TransportPlate(plate=self.plate, target=dev), *sci, TransportPlate(plate=self.plate, target=home),
                Store(plate=self.plate, location=home)]

    def policies(self, ctx):
        return [window_policy(ctx)]

    def recover(self, ctx, failure, child):
        """Unwind-protect for the sample: whatever failed, a plate that left its controlled environment is returned
        to it before the session reports failure (Cell 01 'abort ... if possible', sample integrity). A plate that
        was quarantined (escalated) or never left its slot is not moved."""
        if failure.code in ("escalated",):
            return None
        at = str(ctx.belief.get(f"plate_at:{self.plate.id}"))
        if at.startswith(("slot:", "contained:")) or at in ("unknown", "None"):
            return None
        home = ctx.kb.home().value
        why = ("window exceeded" if failure.code == "window_exceeded" else f"{failure.code} in {child.category}")
        return Recovery([TransportPlate(plate=self.plate, target=home), Store(plate=self.plate, location=home)],
                        then="fail", code="session_failed", suspend_policies=True,
                        why=f"safe return of the plate to its controlled environment ({why})")


@dataclass(eq=False)
class Retrieve(ActionDesignator):
    CATEGORY = "retrieve"
    plate: Optional[Plate] = None
    source: str = ""

    def plan(self, ctx):
        out: List[Designator] = [Command(command="verify_identity", device=self.source, expect=self.plate.id)]
        if ctx.belief.get(f"shuttle:{self.source}") != "presented":
            out.append(Command(command="present", device=self.source))
        return out

    def recover(self, ctx, failure, child):
        if failure.code == "identity_mismatch":
            seen = failure.observation["read"]
            return Recovery([Quarantine(plate=Plate(seen), reason=f"identity mismatch: read {seen}, "
                                                                  f"expected {self.plate.id}")],
                            then="fail", code="escalated",
                            why=f"quarantine {seen} (Cell 01 routing H4_quarantine_if_identity_unresolved); "
                                f"{self.plate.id} location unknown, human escalation")
        return None


@dataclass(eq=False)
class Store(ActionDesignator):
    CATEGORY = "store"
    plate: Optional[Plate] = None
    location: str = ""

    def plan(self, ctx):
        return [Command(command="wait_environment", device=self.location),
                Command(command="store", device=self.location)]


@dataclass(eq=False)
class TransportPlate(ActionDesignator):
    CATEGORY = "transport_lab"
    plate: Optional[Plate] = None
    target: str = ""

    def plan(self, ctx):
        src = str(plate_location(ctx, self.plate))
        if src.startswith("stage:"):          # on a device's internal stage: the device presents it (PickingUp)
            src = src.split(":")[1]
        if ":" in src:
            raise Failure("not_transportable", f"{self.plate.id} is at {src}")
        legs = ctx.resolve(ctx.kb.route(src, self.target))
        return [Transporting(plate=self.plate, robot=r, source=a, target=b) for r, a, b in legs]


@dataclass(eq=False)
class Dose(ActionDesignator):
    CATEGORY = "dose"
    plate: Optional[Plate] = None
    well: str = ""
    reagent: str = ""
    volume_uL: float = 0.0
    dose_au: float = 0.0

    def plan(self, ctx):
        kb = ctx.kb
        dev = device_here(ctx, "dose", self.plate)
        ctx.node.bound_device = dev
        rack = ctx.resolve(kb.frame("tip_rack", dev))
        waste = ctx.resolve(kb.frame("waste", dev))
        rpose = ctx.resolve(kb.reagent_pose(self.reagent))
        wpose = ctx.resolve(kb.well_pose(self.well, "pipette"))
        m = ("dose", self.well.lower(), self.reagent, int(round(self.dose_au * 100)))
        return [Command(command="tip_pick", device=dev, args=(rack,), material=m),
                Command(command="aspirate", device=dev, args=(rpose,), material=m),
                Command(command="dispense", device=dev, args=(wpose, m[3]), material=m),
                Command(command="tip_eject", device=dev, args=(waste,), material=m)]

    def policies(self, ctx):
        dev = getattr(ctx.node, "bound_device", None)
        if dev and ctx.kb.holds("airspace", dev):
            return [airspace_policy(ctx, dev, ctx.kb.seat(dev).value)]
        return []

    def recover(self, ctx, failure, child):
        if failure.code == "tip_missing":
            dev = ctx.node.bound_device
            rack = ctx.kb.frame("tip_rack", dev).value
            m = child.material
            return Recovery([Command(command="tip_pick", device=dev, args=(rack,), material=m)], then="retry",
                            why="replace tip and retry; aborted before aspiration, so no plate exposure")
        return None


@dataclass(eq=False)
class Image(ActionDesignator):
    CATEGORY = "image"
    plate: Optional[Plate] = None
    well: str = ""

    def plan(self, ctx):
        kb = ctx.kb
        fns, caps = FUNCTION_OF["image"]
        devs = ctx.resolve(kb.devices_for(fns, caps))
        at = str(plate_location(ctx, self.plate)).split(":")[-1]
        session_dev = next((getattr(a, "bound_device", None) for a in ctx.node.ancestors()
                            if a.designator.category == "run_session"), None)
        dev = at if at in devs else (session_dev if session_dev in devs else devs[0])
        ctx.node.bound_device = dev
        out: List[Designator] = []
        if at != dev:                     # e.g. after the plate was set aside for a recalibration
            out.append(TransportPlate(plate=self.plate, target=dev))
        if not ctx.belief.get(f"calibrated:{dev}"):
            out.append(Calibrate(target=dev))
        if ctx.belief.get(f"loaded:{dev}") != self.plate.id:
            out.append(Command(command="load", device=dev))
        wpose = ctx.resolve(kb.well_pose(self.well, "imaging"))
        out.append(Command(command="image_well", device=dev, args=(wpose,), material=("image", self.well.lower())))
        return out

    def recover(self, ctx, failure, child):
        dev = ctx.node.bound_device
        if failure.code == "calibration_invalid":
            aside = ctx.resolve(ctx.kb.staging_for(dev))
            return Recovery([TransportPlate(plate=self.plate, target=aside), Calibrate(target=dev)], then="replan",
                            why="calibration lapsed at imaging: set the plate aside, recalibrate the imager at its QC "
                                "station (needs the stage), re-plan the measurement (Cell 01 routing L21_qc)")
        if failure.code == "focus_invalid":
            return Recovery([Command(command="autofocus", device=dev, args=child.args, material=child.material)],
                            then="retry", why="out-of-focus acquisition retained; fresh autofocus and reacquire "
                                              "(Cell 01 routing reacquire_if_binding_recoverable)")
        return None


@dataclass(eq=False)
class Calibrate(ActionDesignator):
    CATEGORY = "calibrate"
    target: str = ""

    def plan(self, ctx):
        st = ctx.resolve(ctx.kb.qc_station_for(self.target))
        ctx.resolve(ctx.kb.devices_for(["calibration"], []))
        return [Command(command="validate", device=st, args=(self.target,))]


@dataclass(eq=False)
class Quarantine(ActionDesignator):
    CATEGORY = "quarantine"
    plate: Optional[Plate] = None
    reason: str = ""

    def plan(self, ctx):
        dev = ctx.resolve(ctx.kb.devices_for(["quarantine"], []))[0]
        out: List[Designator] = []
        at = str(plate_location(ctx, self.plate))
        if at.startswith("slot:"):
            out.append(Command(command="present", device=at.split(":")[1]))
        out += [TransportPlate(plate=self.plate, target=dev), Command(command="contain", device=dev,
                                                                       material=("quarantine", self.plate.id))]
        return out


# ======================================================================================== manipulation level
@dataclass(eq=False)
class Transporting(ActionDesignator):
    CATEGORY = "transporting"
    plate: Optional[Plate] = None
    robot: str = ""
    source: str = ""
    target: str = ""

    def plan(self, ctx):
        kb = ctx.kb
        s_seat = ctx.resolve(kb.seat(self.source))
        t_seat = ctx.resolve(kb.seat(self.target))
        out: List[Designator] = []
        tool = ctx.resolve(kb.tool_for(self.robot))
        held = ctx.belief.get(f"tool:{self.robot}")
        ctx.node.resolutions.append(Answer(f"belief tool:{self.robot}", held,
                                           [f"belief tool:{self.robot} ({ctx.belief.source(f'tool:{self.robot}')})"]))
        if tool != "none" and held != tool[0]:
            out.append(CouplingTool(robot=self.robot, tool=tool[0], dock=tool[1]))
        out.append(PickingUp(plate=self.plate, robot=self.robot, station=self.source, seat=s_seat))
        if kb.holds("has_shuttle", self.source):
            out.append(Command(command="stow", device=self.source))
        out.append(Motion(primitive="transit", robot=self.robot, args=(("appr", s_seat), ("appr", t_seat))))
        out.append(Placing(plate=self.plate, robot=self.robot, station=self.target, seat=t_seat))
        return out


@dataclass(eq=False)
class CouplingTool(ActionDesignator):
    CATEGORY = "coupling_tool"
    robot: str = ""
    tool: str = ""
    dock: str = ""

    def plan(self, ctx):
        return [Motion(primitive="tool_couple", robot=self.robot, args=(self.tool, self.dock))]


@dataclass(eq=False)
class PickingUp(ActionDesignator):
    CATEGORY = "picking_up"
    plate: Optional[Plate] = None
    robot: str = ""
    station: str = ""
    seat: str = ""

    def plan(self, ctx):
        out: List[Designator] = []
        if ctx.kb.holds("has_shuttle", self.station) and ctx.belief.get(f"shuttle:{self.station}") != "presented":
            out.append(Command(command="present", device=self.station))
        r = self.robot
        return out + [Motion(primitive="approach", robot=r, args=(("appr", self.seat),)),
                      Motion(primitive="insert", robot=r, args=(self.seat,)),
                      Motion(primitive="grasp", robot=r), Motion(primitive="lift", robot=r)]


@dataclass(eq=False)
class Placing(ActionDesignator):
    CATEGORY = "placing"
    plate: Optional[Plate] = None
    robot: str = ""
    station: str = ""
    seat: str = ""

    def plan(self, ctx):
        out: List[Designator] = []
        if ctx.kb.holds("has_shuttle", self.station) and ctx.belief.get(f"shuttle:{self.station}") != "presented":
            out.append(Command(command="present", device=self.station))
        r = self.robot
        return out + [Motion(primitive="approach", robot=r, args=(("appr", self.seat),)),
                      Motion(primitive="place", robot=r, args=(self.seat,)),
                      Motion(primitive="release", robot=r),
                      Motion(primitive="retract", robot=r, args=(("appr", self.seat),))]


def experiment_from_plan(plan: Dict[str, Any], plate_id: str, drop_roles=()) -> Experiment:
    """The scientific executive's output (derive_plan) as the root designator: design, roles and session materials
    only; none of the planner's 151 steps are passed on (the kernel re-derives them)."""
    wells = {k: v for k, v in plan["wells"].items() if k not in drop_roles}
    dropped = {w.lower() for k in drop_roles for w in plan["wells"].get(k, [])}
    sessions = []
    for s in plan["sessions"]:
        mat = [m for m in s["material"] if m[1] not in dropped]
        sessions.append(dict(session=s["session"], trip=s["trip"], t_h=s["t_h"], material=mat))
    sel = plan["selected"]
    return Experiment(design=sel["id"], requirement_bits=plan["requirement_bits"], eig_bits=sel["eig_bits"],
                      plate=Plate(plate_id), wells=wells, sessions=sessions)
