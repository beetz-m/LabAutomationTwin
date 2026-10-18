"""Designators, plan nodes and the executor of the kernel (KERNEL.md concepts 1, 4, 5, 9, 12).

Shaped like coraplex so the port is a mapping: designators are dataclasses whose fields are their roles; an action
designator builds its sub-plan at perform time (coraplex ``_action_plan``) by querying the knowledge base; leaves are
motion designators (coraplex ``MotionNode``) and device-command designators (no coraplex counterpart yet).

The executor runs the Cell 01 designator lifecycle for every action designator
    open -> grounded -> accepted -> executing -> executed | failed  (-> repaired | abstained | escalated)
and writes one audit entry per transition. Failures propagate upward until a category's recovery handles them (CRAM
with-failure-handling; retry = re-perform after repair, at most once per node and failure code).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, fields
from typing import Any, Callable, ClassVar, Dict, List, Optional, Tuple

from .kb import KB, Answer, Unresolved

KERNEL_VERSION = "rsa-kernel/0.1"


# ----------------------------------------------------------------------------------------------------- failures
class Failure(Exception):
    """A typed plan failure (Cell 01 failure modes / SOMA failure taxonomy, kernel subset)."""

    def __init__(self, code: str, detail: str = "", observation: Any = None, constraint: Optional[str] = None):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.observation, self.constraint = code, detail, observation, constraint


@dataclass
class Recovery:
    repairs: List["Designator"]
    then: str = "retry"            # retry the failed child | continue with the next child | fail (re-raise as `code`)
    code: Optional[str] = None
    suspend_policies: bool = False
    why: str = ""


# ----------------------------------------------------------------------------------------------------- objects
@dataclass(frozen=True)
class Plate:
    id: str

    def __str__(self):
        return f"(the plate {self.id})"


def _ser(v):
    if isinstance(v, Plate):
        return v.id
    if isinstance(v, (list, tuple)):
        return [_ser(x) for x in v]
    return v


# ----------------------------------------------------------------------------------------------------- designators
@dataclass(eq=False)
class Designator:
    CATEGORY: ClassVar[str] = ""
    KIND: ClassVar[str] = "action"

    @property
    def category(self) -> str:
        return self.CATEGORY

    def bindings(self) -> Dict[str, Any]:
        return {f.name: _ser(getattr(self, f.name)) for f in fields(self) if not f.name.startswith("_")}

    def hadl(self) -> str:
        roles = " ".join(f"({k} {v})" for k, v in self.bindings().items() if v not in (None, [], ()))
        art = "an" if self.KIND[0] in "aeiou" else "a"
        return f"({art} {self.KIND} (type {self.category.replace('_', '-')}) {roles})".replace(" )", ")")


@dataclass(eq=False)
class ActionDesignator(Designator):
    KIND: ClassVar[str] = "action"

    def plan(self, ctx: "Context") -> List[Designator]:
        raise NotImplementedError

    def recover(self, ctx: "Context", failure: Failure, child: Designator) -> Optional[Recovery]:
        return None

    def policies(self, ctx: "Context") -> List["Policy"]:
        return []

    def objects(self) -> Dict[str, Any]:
        """Roles that name the things acted on (understanding slot 'target')."""
        return {k: v for k, v in self.bindings().items() if k in ("plate", "well", "wells", "target", "device", "design")}


@dataclass(eq=False)
class Motion(Designator):
    """A body-motion designator: one phase of picking-up / placing, executed by the robot's controller."""
    KIND: ClassVar[str] = "motion"
    primitive: str = ""
    robot: str = ""
    args: Tuple = ()

    @property
    def category(self) -> str:
        return self.primitive

    def term(self) -> list:
        return [self.primitive, self.robot, *[list(a) if isinstance(a, tuple) else a for a in self.args]]


@dataclass(eq=False)
class Command(Designator):
    """A device-command designator: an operation the device performs itself (Cell 01 devices are co-actors)."""
    KIND: ClassVar[str] = "command"
    command: str = ""
    device: str = ""
    args: Tuple = ()
    material: Optional[Tuple] = None
    expect: Optional[str] = None

    @property
    def category(self) -> str:
        return "store_cmd" if self.command == "store" else self.command

    def term(self) -> list:
        return ["cmd", self.device, [self.command, *self.args] if self.args else self.command]


# ----------------------------------------------------------------------------------------------------- plan nodes
@dataclass(eq=False)
class Node:
    designator: Designator
    parent: Optional["Node"]
    uid: str
    children: List["Node"] = field(default_factory=list)
    status: str = "created"            # plan-node status (RPL axis), kept apart from the lifecycle (K5)
    lifecycle: List[str] = field(default_factory=list)
    t0: float = 0.0
    t1: float = 0.0
    reason: str = ""
    resolutions: List[Answer] = field(default_factory=list)
    constraints: List[Dict[str, Any]] = field(default_factory=list)
    repairs: List[Dict[str, Any]] = field(default_factory=list)
    understanding: Optional[Dict[str, Any]] = None
    observation: Optional[Dict[str, Any]] = None

    def ancestors(self) -> List["Node"]:
        out, n = [], self.parent
        while n is not None:
            out.append(n)
            n = n.parent
        return out

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def leaves(self):
        return [n for n in self.walk() if n.designator.KIND in ("motion", "command")]


@dataclass
class Policy:
    """A monitor active while a sub-plan executes (CRAM with-policy); `check` returns (ok, observation)."""
    name: str
    constraint: str
    check: Callable[["Context", Optional[Designator], str], Tuple[bool, Any]]
    owner: Optional[Node] = None


# ----------------------------------------------------------------------------------------------------- belief
class Belief:
    """The assistant's belief with provenance per item: observed | inferred (from KB facts) | assumed."""

    def __init__(self):
        self.items: Dict[str, Tuple[Any, str, Any]] = {}

    def set(self, key: str, value: Any, source: str, ref: Any = None):
        self.items[key] = (value, source, ref)

    def get(self, key: str, default=None):
        return self.items[key][0] if key in self.items else default

    def source(self, key: str) -> Optional[str]:
        return self.items[key][1] if key in self.items else None

    def stale(self, prefixes, why: str):
        """Freshness: observations of shared cell state do not outlive the session they were made in."""
        for k, (v, src, ref) in list(self.items.items()):
            if k.startswith(tuple(prefixes)) and src in ("observed", "inferred"):
                self.items[k] = (None, "stale", why)

    def copy(self) -> "Belief":
        b = Belief()
        b.items = dict(self.items)
        return b


# ----------------------------------------------------------------------------------------------------- context
class Context:
    def __init__(self, kb: KB, backend, audit, belief: Belief, projecting: bool = False):
        self.kb, self.backend, self.audit, self.belief = kb, backend, audit, belief
        self.projecting = projecting
        self.stack: List[Node] = []
        self.policies: List[Policy] = []
        self.retries: Dict[Tuple[str, str], int] = {}
        self._uid = 0
        self.root: Optional[Node] = None

    @property
    def clock(self) -> float:
        return self.backend.clock

    @property
    def node(self) -> Node:
        return self.stack[-1]

    def new_uid(self, d: Designator) -> str:
        self._uid += 1
        return f"d{self._uid:04d}-{d.category}"

    def resolve(self, ans: Answer, required: bool = True):
        """Record a resolution on the current node; unresolvable required values make the designator ungroundable."""
        if self.stack:
            self.node.resolutions.append(ans)
        if required and not ans.ok:
            raise Unresolved(ans)
        return ans.value

    def card(self, category: str) -> Dict[str, Any]:
        return (self.kb.registry.get("categories") or {}).get(category, {})

    def project(self, d: ActionDesignator) -> Dict[str, Any]:
        """CRAM projection: perform `d` on a copy of the world without faults and without audit."""
        pctx = Context(self.kb, self.backend.projection(self.belief), NullAudit(), self.belief.copy(), projecting=True)
        t0 = pctx.clock
        try:
            node = perform(d, pctx)
            ok, reason = node.status == "succeeded", node.reason
        except Failure as f:
            ok, reason, node = False, f"{f.code}: {f.detail}", pctx.root
        return dict(ok=ok, reason=reason, duration_s=round(pctx.clock - t0, 2), node=node)


class NullAudit:
    def record(self, *a, **k):
        return None


# ----------------------------------------------------------------------------------------------------- executor
def perform(d: Designator, ctx: Context, parent: Optional[Node] = None) -> Node:
    from . import checks

    node = Node(d, parent, ctx.new_uid(d))
    if parent is not None:
        parent.children.append(node)
    else:
        ctx.root = node
    node.t0 = ctx.clock
    ctx.stack.append(node)
    try:
        if d.KIND in ("motion", "command"):
            _perform_leaf(node, ctx, checks)
        else:
            _perform_action(node, ctx, checks)
        node.status = "succeeded"
        return node
    except Failure as f:
        node.status = "failed"
        node.reason = node.reason or f"{f.code}: {f.detail}"
        raise
    finally:
        node.t1 = ctx.clock
        ctx.stack.pop()


def _check_policies(node: Node, ctx: Context, checks, when: str, defer: bool = False) -> List[Dict[str, Any]]:
    passed = []
    for p in list(ctx.policies):
        ok, obs = p.check(ctx, node.designator, when)
        if ok is None:
            continue
        v = dict(id=p.constraint, column=checks.column(ctx, p.constraint), verdict="ENFORCED" if ok else "VIOLATED",
                 observation=obs, policy=p.name, when=when)
        if not ok and defer:
            passed.append(v)
            continue
        if not ok:
            ctx.audit.record(ctx, node, "policy_violation", constraints=[v])
            raise Failure(checks.failure_code(ctx, p.constraint), f"policy {p.name}: {obs}", obs, p.constraint)
        passed.append(v)
    return passed


def _perform_leaf(node: Node, ctx: Context, checks):
    before = _check_policies(node, ctx, checks, "before")
    try:
        obs = ctx.backend.execute(node.designator, ctx)      # raises Failure on a physical / monitored fault
    except Failure as f:
        obs = getattr(f, "obs", None) or {}
        node.observation = obs
        for k, (v, src) in (obs.get("belief") or {}).items():
            ctx.belief.set(k, v, src, node.uid)
        ctx.audit.record(ctx, node, "failed", monitors=obs.get("monitors"), evidence=obs.get("evidence"),
                         belief={k: v for k, (v, _) in (obs.get("belief") or {}).items()} or None,
                         constraints=before or None, duration_s=obs.get("duration_s"), reason=f"{f.code}: {f.detail}")
        raise
    node.observation = obs
    for k, (v, src) in (obs.get("belief") or {}).items():
        ctx.belief.set(k, v, src, node.uid)
    after = _check_policies(node, ctx, checks, "after", defer=True)
    node.constraints += before + after
    ctx.audit.record(ctx, node, "executed", monitors=obs.get("monitors"), evidence=obs.get("evidence"),
                     belief={k: v for k, (v, _) in (obs.get("belief") or {}).items()} or None,
                     constraints=(before + after) or None, duration_s=obs.get("duration_s"))
    bad = [v for v in after if v["verdict"] == "VIOLATED"]
    if bad:
        ctx.audit.record(ctx, node, "policy_violation", constraints=bad)
        raise Failure(checks.failure_code(ctx, bad[0]["id"]), f"policy {bad[0]['policy']}: {bad[0]['observation']}",
                      bad[0]["observation"], bad[0]["id"])


def _perform_action(node: Node, ctx: Context, checks):
    d: ActionDesignator = node.designator  # type: ignore[assignment]
    node.lifecycle.append("open")
    ctx.audit.record(ctx, node, "open")
    # ---- ground: build the sub-plan from knowledge (resolution records its grounds on the node)
    try:
        children = d.plan(ctx)
    except Unresolved as u:
        node.lifecycle.append("abstained")
        node.reason = f"unresolved {u.answer.query}"
        ctx.audit.record(ctx, node, "abstained", reason=node.reason)
        raise Failure("unresolved", f"{u.answer.query}; " + "; ".join(r for _, r in u.answer.rejected), u.answer)
    node.lifecycle.append("grounded")
    node.planned = [c.category for c in children]
    ctx.audit.record(ctx, node, "grounded", plan=[c.hadl() for c in children])
    # ---- accept: constraints (phase accept) and the understanding gate
    verdicts = checks.evaluate(ctx, node, "accept")
    node.constraints += verdicts
    refused = [v for v in verdicts if v["verdict"] == "VIOLATED"]
    if not refused:                       # knowledge-only, so it also runs in projection (F7)
        u = checks.understanding(ctx, node)
        node.understanding = u
        if u["missing"]:
            node.lifecycle.append("abstained")
            node.reason = "understanding incomplete: " + ", ".join(u["missing"])
            ctx.audit.record(ctx, node, "abstained", constraints=verdicts, understanding=u, reason=node.reason)
            raise Failure("understanding_incomplete", node.reason)
    if refused:
        node.lifecycle.append("abstained")
        node.reason = "refused by " + ", ".join(v["id"] for v in refused)
        ctx.audit.record(ctx, node, "abstained", constraints=verdicts, reason=node.reason)
        raise Failure("refused", node.reason, refused, refused[0]["id"])
    node.lifecycle.append("accepted")
    ctx.audit.record(ctx, node, "accepted", constraints=verdicts, understanding=node.understanding)
    # ---- execute
    node.lifecycle.append("executing")
    ctx.audit.record(ctx, node, "executing")
    own = d.policies(ctx)
    for p in own:
        p.owner = node
    ctx.policies += own
    try:
        _run_children(node, ctx, checks, children)
    except Failure as f:
        node.lifecycle.append("escalated" if f.code in ("escalated", "session_failed") else "failed")
        ctx.audit.record(ctx, node, node.lifecycle[-1], reason=f"{f.code}: {f.detail}")
        raise
    finally:
        ctx.policies = [p for p in ctx.policies if p.owner is not node]
    post = checks.evaluate(ctx, node, "post")
    node.constraints += post
    bad = [v for v in post if v["verdict"] == "VIOLATED" and v["column"] == "realization"]
    if bad:
        node.lifecycle.append("failed")
        ctx.audit.record(ctx, node, "failed", constraints=post, reason="post-condition violated")
        raise Failure("post_violated", ", ".join(v["id"] for v in bad), bad, bad[0]["id"])
    node.lifecycle.append("repaired" if node.repairs else "executed")
    ctx.audit.record(ctx, node, node.lifecycle[-1], constraints=post)


def _run_children(node: Node, ctx: Context, checks, children: List[Designator]):
    d: ActionDesignator = node.designator  # type: ignore[assignment]
    i = 0
    while i < len(children):
        child = children[i]
        try:
            perform(child, ctx, node)
            i += 1
        except Failure as f:
            key = (node.uid, f.code)
            rec = None if ctx.projecting or ctx.retries.get(key, 0) >= 1 else d.recover(ctx, f, child)
            if rec is None:
                raise
            ctx.retries[key] = ctx.retries.get(key, 0) + 1
            node.repairs.append(dict(failure=f.code, detail=f.detail, at=node.children[-1].uid if node.children else None,
                                     repairs=[r.hadl() for r in rec.repairs],
                                     repair_categories=[r.category for r in rec.repairs], then=rec.then, why=rec.why))
            ctx.audit.record(ctx, node, "repairing", reason=f"{f.code}: {f.detail}", repair=node.repairs[-1])
            saved = ctx.policies
            if rec.suspend_policies:
                ctx.policies = [p for p in ctx.policies if p.owner is not node]
            try:
                for r in rec.repairs:
                    perform(r, ctx, node)
            finally:
                ctx.policies = saved
            if rec.then == "fail":
                raise Failure(rec.code or f.code, f"{f.detail} (after {rec.why})", f.observation, f.constraint)
            if rec.then == "continue":
                i += 1
            if rec.then == "replan":          # CRAM: retry = re-resolution against the repaired belief
                children = d.plan(ctx)
                node.planned = [c.category for c in children]
                ctx.audit.record(ctx, node, "replanned", plan=[c.hadl() for c in children],
                                 resolutions=[a.as_dict() for a in node.resolutions[-6:]])
                i = 0
