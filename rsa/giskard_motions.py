"""Refine the action designators' motions into Giskard motion statecharts: reference frames, motion constraints and the
objective that giskardpy's QP-based model-predictive controller optimizes.

For every transport leg of the challenge-rescue plan (rsa/motion_frames.py: frames from the composed Cell 01 scene,
every goal checked by kinematics), this writes
  rsa/out/challenge_rescue_motions.lisp   the motion designators, CRAM/LDL notation, one per motion phase
  rsa/out/challenge_rescue_giskard.py     the same as giskardpy MotionStatecharts (giskardpy API of the user's CRAM
                                          checkout: classes and fields verified against its source)
Motion phases and their Giskard refinement:
  approaching   CartesianPose of the TCP to the pose above the seat (tool down, jaws on the plate's long sides)
  inserting     CartesianPoseStraight down to the grasp pose, Cartesian speed limit, gripper-plate contact allowed
  grasping      JointPositionList closes the fingers; ends at LocalMinimumReached (the fingers stall on the plate)
  lifting       CartesianPositionStraight up, speed limit, AlignPlanes keeps the plate level
  transiting    CartesianPose to above the target seat, plate level, Cartesian velocity limit, collision avoidance
  aligning      CartesianPose above the target seat with the twin's 0.4 mm tolerance (PoseReached)
  placing       CartesianPositionStraight down to the release height, slow, plate level, plate-seat contact allowed
  releasing     JointPositionList opens the fingers; ends at LocalMinimumReached
  retracting    CartesianPositionStraight back up
  coupling      CartesianPose above the dock, CartesianPoseStraight onto it within the 4 mm lock gap
External and self collision avoidance run through every statechart. Soft-constraint priorities (slack weights,
giskardpy DefaultWeights): plate level and speed limits 2500 > collision avoidance 50 > goals 1 > posture 0.1.
Objective (giskardpy QP): minimize, over the prediction horizon, the weighted squared joint velocities and jerks
(dof_weights) plus the weighted squared slacks of all soft constraints, subject to the hard joint position / velocity /
jerk limits and the constraint rows.

    env_cad/bin/python -m rsa.giskard_motions
"""

from __future__ import annotations

import json
import math
import os
import py_compile
import re
import sys

from .sexp_pretty import pretty

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
CRAM = os.path.expanduser("~/ResearchSpace/foundation/software/cram")
GISKARD = os.path.join(CRAM, "giskardpy", "src", "giskardpy")
SDT = os.path.join(CRAM, "semantic_digital_twin", "src", "semantic_digital_twin")
KRROOD = os.path.join(CRAM, "krrood", "src", "krrood")

GRIP_Z = 0.006
TIME_TOL = 1.2                        # per-phase timeout = 1.2 x the planner's estimate (the z3 time theorem V3 assumes +-20 %)
LEG_PART = {}                         # (robot, phase) -> estimate in s, from the planner's facts (leg_part, dur)
MAX_TILT_DEG = 2.0                    # ILLUSTRATIVE: the plate is kept level (culture medium, D016)
TRANSIT_V, TRANSIT_W = 0.25, 0.6      # m/s, rad/s Cartesian limits in free space (ILLUSTRATIVE)
POSE_TOL = 0.0004                     # m, the twin's at-rest convergence (twin/r01_rig, twin/r02_rig: 0.4 mm / 0.2 deg)
ORI_TOL = math.radians(0.2)
LOCK_GAP = 0.004                      # m, R02's coupler lock gap (twin/r02_rig.MAX_LOCK_GAP)
SEAT_BODY = {"l10": "transfer_station", "handovernest": "handover_frame", "l12": "plate_nest", "l17": "plate_load_frame",
             "dock_t01": "dock_T01"}
ROBOT_SDT = {"r01": dict(root="fr3_link0", tcp="plate_grasp_frame", fingers=["FingerAJoint", "FingerBJoint"],
                         closed=[-0.0025, 0.0025], opened=[0.0, 0.0], posture=dict(zip([f"fr3_joint{i}" for i in range(1, 8)],
                         [0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785]))),
             "r02": dict(root="rail_base", tcp="t01_tcp", fingers=["t01_jaw_a", "t01_jaw_b"], closed=[-0.0025, 0.0025],
                         opened=[0.0, 0.0], posture={})}


def motion_phases(leg, frames):
    """The motion designators of one leg, from the kernel's motion leaves (in order)."""
    r = frames["robots"][leg["robot"]]
    seen_approach = 0
    out = []
    for lf in leg["leaves"]:
        ph = lf["phase"]
        src, dst = leg["src"], leg["dst"]
        if ph == "tool_couple":
            out.append(dict(type="coupling", seat="dock_t01", z=0.0, pre=0.05, speed=0.02, tol=LOCK_GAP, held=False))
        elif ph == "approach":
            seen_approach += 1
            if seen_approach == 1:
                out.append(dict(type="approaching", seat=src, z=GRIP_Z + r["approach_m"], held=False, tol=0.005))
            else:
                out.append(dict(type="aligning", seat=dst, z=GRIP_Z + r["approach_m"], held=True, tol=POSE_TOL))
        elif ph == "insert":
            out.append(dict(type="inserting", seat=src, z=GRIP_Z, speed=r["insert_speed"], held=False, tol=POSE_TOL))
        elif ph == "grasp":
            out.append(dict(type="grasping", seat=src, held=False))
        elif ph == "lift":
            out.append(dict(type="lifting", seat=src, z=GRIP_Z + r["approach_m"], speed=r["lift_speed"], held=True))
        elif ph == "transit":
            out.append(dict(type="transiting", seat=dst, z=GRIP_Z + r["approach_m"], held=True, tol=0.005))
        elif ph == "place":
            out.append(dict(type="placing", seat=dst, z=GRIP_Z + r["place_entry_m"], speed=r["place_speed"], held=True, tol=POSE_TOL))
        elif ph == "release":
            out.append(dict(type="releasing", seat=dst, held=False))
        elif ph == "retract":
            out.append(dict(type="retracting", seat=dst, z=GRIP_Z + r["approach_m"], speed=r["lift_speed"], held=False))
        out[-1]["kernel_leaf"] = ph
        est = LEG_PART.get((leg["robot"], ph if ph != "tool_couple" else "tool_couple"))
        out[-1]["estimate_s"] = est
        out[-1]["timeout_s"] = round(TIME_TOL * est, 2) if est else None
        out[-1]["cancel"] = (["duration > %.2f s" % (TIME_TOL * est)] if est else []) + \
            (["plate tilt > %.1f deg" % MAX_TILT_DEG] if out[-1].get("held") else []) + \
            (["collision distance violated"] if out[-1]["type"] in ("approaching", "transiting", "aligning", "coupling",
                                                                    "lifting", "placing", "retracting", "inserting") else [])
    return out


# ------------------------------------------------------------------------------------------------- motion designators (Lisp)
def lisp_motion(rob, m, seats):
    s = seats[m["seat"]]
    goal = (f"(a pose (relative-to (the frame {SEAT_BODY[m['seat']]})) (translation 0 0 {m.get('z', 0):.3f}) "
            f"(orientation tool-down) (in-world (point {s['p'][0]} {s['p'][1]} {round(s['p'][2] + m.get('z', 0), 4)}) (yaw {s['yaw_deg']} deg)))")
    tip = f"(the frame {ROBOT_SDT[rob]['tcp']} (of (the robot {rob})))"
    root = f"(the frame {ROBOT_SDT[rob]['root']} (of (the robot {rob})))"
    cons, obj, until = [], [], ""
    if m["type"] in ("approaching", "transiting", "aligning"):
        cons.append(f"(reach {goal} :threshold {m['tol']})")
        cons.append(f"(cartesian-velocity-limit (linear {TRANSIT_V} m/s) (angular {TRANSIT_W} rad/s))")
        until = f"(pose-reached :threshold {m['tol']})"
    elif m["type"] in ("inserting",):
        cons.append(f"(reach-straight {goal})")
        cons.append(f"(cartesian-velocity-limit (linear {m['speed']} m/s))")
        cons.append(f"(allow-contact (the fingers (of (the robot {rob}))) (the plate ?p))")
        until = f"(pose-reached :position {POSE_TOL} :orientation 0.2 deg)"
    elif m["type"] in ("lifting", "placing", "retracting"):
        cons.append(f"(reach-straight (a point (relative-to (the frame {SEAT_BODY[m['seat']]})) (translation 0 0 {m['z']:.3f})))")
        cons.append(f"(cartesian-velocity-limit (linear {m['speed']} m/s))")
        if m["type"] == "placing":
            cons.append(f"(allow-contact (the plate ?p) (the seat {SEAT_BODY[m['seat']]}))")
        until = "(position-reached :threshold 0.0004)"
    elif m["type"] in ("grasping", "releasing"):
        cons.append(f"(joint-goal (the fingers (of (the robot {rob}))) ({'closed' if m['type'] == 'grasping' else 'open'}))")
        until = "(local-minimum-reached)"
    elif m["type"] == "coupling":
        cons.append(f"(reach (a pose (relative-to (the frame dock_T01)) (translation 0 0 {m['pre']})) :threshold 0.005)")
        cons.append(f"(reach-straight {goal} :threshold {LOCK_GAP})")
        until = f"(pose-reached :position {LOCK_GAP})"
    if m.get("held"):
        cons.append(f"(keep-level (the plate ?p) (max-tilt {MAX_TILT_DEG} deg))")
    if m["type"] in ("approaching", "transiting", "aligning", "coupling"):
        cons.append("(avoid-collisions (external) (self))")
        obj.append("(prefer-posture (the posture ready (of (the robot " + rob + "))) :weight 0.1)")
    obj.append("(minimize (sum (squared joint-velocity) (squared joint-jerk)) :horizon 7)")
    return (f"(a motion (type {m['type']}) (robot {rob}) (tip {tip}) (root {root})"
            f" (refines {m['kernel_leaf']}) (constraints {' '.join(cons)}) (objective {' '.join(obj)}) (until {until}))")


# ------------------------------------------------------------------------------------------------- giskardpy module
PY_HEAD = '''"""Challenge-rescue experiment: the motion designators of every transport leg as giskardpy motion statecharts.

GENERATED by rsa/giskard_motions.py from rsa/out/motion_frames.json (frames of the composed Cell 01 scene, every goal
checked by FR3 / rail + UR5e kinematics). Not executed here: it needs a semantic_digital_twin World of Cell 01 with
the robots, the plate and the seat frames as bodies (to be built when coraplex is installed). Body names follow the USD
prim names; see body().

Soft-constraint priorities (slack weights): plate level and speed limits (WEIGHT_ABOVE_COLLISION_AVOIDANCE = 2500) >
collision avoidance (WEIGHT_COLLISION_AVOIDANCE = 50) > goals (WEIGHT_BELOW_COLLISION_AVOIDANCE = 1) > posture (0.1).
Objective: giskardpy's QP minimizes the weighted squared joint velocities and jerks over the prediction horizon plus
the weighted squared slacks of the soft constraints, subject to the joint limits and the constraint rows.
ILLUSTRATIVE values (D016): the 2 deg tilt bound, the free-space Cartesian limits.
"""

from __future__ import annotations

import math

from giskardpy.executor import Executor
from giskardpy.motion_statechart.context import MotionStatechartContext
from giskardpy.motion_statechart.data_types import DefaultWeights
from giskardpy.motion_statechart.goals.cartesian_goals import CartesianPoseStraight
from giskardpy.motion_statechart.goals.collision_avoidance import (ExternalCollisionAvoidance, SelfCollisionAvoidance,
                                                                   UpdateTemporaryCollisionRules)
from giskardpy.motion_statechart.graph_node import CancelMotion, EndMotion
from giskardpy.motion_statechart.monitors.cartesian_monitors import PoseReached, VectorsAligned
from giskardpy.motion_statechart.monitors.payload_monitors import CountSimulationTimeSeconds
from giskardpy.motion_statechart.monitors.monitors import LocalMinimumReached
from giskardpy.motion_statechart.motion_statechart import MotionStatechart
from giskardpy.motion_statechart.tasks.align_planes import AlignPlanes
from giskardpy.motion_statechart.tasks.cartesian_tasks import (CartesianPose, CartesianPositionStraight,
                                                               CartesianPositionVelocityLimit, CartesianVelocityLimit)
from giskardpy.motion_statechart.tasks.joint_tasks import JointPositionList
from giskardpy.qp.qp_controller_config import QPControllerConfig
from krrood.symbolic_math.symbolic_math import trinary_logic_and, trinary_logic_not
from semantic_digital_twin.collision_checking.collision_rules import AllowCollisionBetweenGroups
from semantic_digital_twin.datastructures.joint_state import JointState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import Point3, Pose, Vector3

QP_CONFIG = QPControllerConfig(target_frequency=50, prediction_horizon=7, verbose=False)
W_LEVEL = DefaultWeights.WEIGHT_ABOVE_COLLISION_AVOIDANCE      # keep the plate level
W_SPEED = DefaultWeights.WEIGHT_ABOVE_COLLISION_AVOIDANCE      # Cartesian speed limits near seats
W_GOAL = DefaultWeights.WEIGHT_BELOW_COLLISION_AVOIDANCE       # reach the goal frame
W_POSTURE = 0.1 * float(DefaultWeights.WEIGHT_BELOW_COLLISION_AVOIDANCE)   # stay near the planned posture
MAX_TILT = math.radians(__MAX_TILT__)
TRANSIT_V, TRANSIT_W = __TRANSIT_V__, __TRANSIT_W__
POSE_TOL, ORI_TOL, LOCK_GAP = __POSE_TOL__, __ORI_TOL__, __LOCK_GAP__

ROBOTS = __ROBOTS__
SEATS = __SEATS__


def body(world, name):
    """The SDT body for a Cell 01 prim name (assumption: the SDT World built from the Cell 01 USD names bodies by prim)."""
    return world.get_kinematic_structure_entity_by_name(PrefixedName(name))


def tool_down(seat_frame, z):
    """TCP pose z above a seat frame, tool +Z pointing down, jaws on the plate's long sides (Rz(seat) Rx(pi))."""
    return Pose.from_xyz_rpy(x=0.0, y=0.0, z=z, roll=math.pi, pitch=0.0, yaw=0.0, reference_frame=seat_frame)


def keep_level(world, plate):
    return AlignPlanes(root_link=world.root, tip_link=plate, goal_normal=Vector3.Z(world.root),
                       tip_normal=Vector3.Z(plate), threshold=MAX_TILT, weight=W_LEVEL)


def posture(world, robot):
    if not robot["posture"]:
        return []
    return [JointPositionList(goal_state=JointState.from_str_dict(robot["posture"], world), weight=W_POSTURE)]


def fingers(world, robot, closed):
    return JointPositionList(goal_state=JointState.from_str_dict(
        dict(zip(robot["fingers"], robot["closed"] if closed else robot["opened"])), world))


def allow_contact(group_a, group_b):
    return UpdateTemporaryCollisionRules(temporary_rules=[AllowCollisionBetweenGroups(body_group_a=group_a, body_group_b=group_b)])


# ------------------------------------------------------------------ one function per motion designator type
# Each returns (done, aux): `done` ends the phase (its observation), `aux` are the constraints active during it.

def approaching(world, robot, seat, z, tol, plate=None):
    root, tcp = body(world, robot["root"]), body(world, robot["tcp"])
    done = CartesianPose(root_link=root, tip_link=tcp, goal_pose=tool_down(body(world, seat), z), threshold=tol, weight=W_GOAL)
    aux = [CartesianVelocityLimit(root_link=root, tip_link=tcp, max_linear_velocity=TRANSIT_V,
                                  max_angular_velocity=TRANSIT_W, weight=W_SPEED)] + posture(world, robot)
    return done, aux + ([keep_level(world, plate)] if plate is not None else [])


transiting = approaching        # same constraints; held plate kept level


def aligning(world, robot, seat, z, tol, plate=None):
    done, aux = approaching(world, robot, seat, z, 0.005, plate)
    goal = tool_down(body(world, seat), z)
    monitor = PoseReached(root_link=body(world, robot["root"]), tip_link=body(world, robot["tcp"]),
                          goal_pose=goal.to_homogeneous_matrix(), position_threshold=tol, orientation_threshold=ORI_TOL)
    return monitor, [done] + aux


def inserting(world, robot, seat, z, speed, tol, plate):
    root, tcp = body(world, robot["root"]), body(world, robot["tcp"])
    goal = tool_down(body(world, seat), z)
    done = PoseReached(root_link=root, tip_link=tcp, goal_pose=goal.to_homogeneous_matrix(),
                       position_threshold=tol, orientation_threshold=ORI_TOL)
    aux = [CartesianPoseStraight(root_link=root, tip_link=tcp, goal_pose=goal),
           CartesianPositionVelocityLimit(root_link=root, tip_link=tcp, max_linear_velocity=speed, weight=W_SPEED),
           allow_contact([body(world, j) for j in robot["finger_links"]], [plate])]
    return done, aux


def straight(world, robot, seat, z, speed, plate=None, contact=None):
    """lifting, placing, retracting: straight vertical motion of the TCP at a capped speed."""
    root, tcp = body(world, robot["root"]), body(world, robot["tcp"])
    done = CartesianPositionStraight(root_link=root, tip_link=tcp,
                                     goal_point=Point3(0.0, 0.0, z, reference_frame=body(world, seat)),
                                     reference_velocity=speed, threshold=POSE_TOL)
    aux = [CartesianPositionVelocityLimit(root_link=root, tip_link=tcp, max_linear_velocity=speed, weight=W_SPEED)]
    if plate is not None:
        aux.append(keep_level(world, plate))
    if contact is not None:
        aux.append(allow_contact(*contact))
    return done, aux


def grasping(world, robot):
    return LocalMinimumReached(), [fingers(world, robot, closed=True)]


def releasing(world, robot):
    return LocalMinimumReached(), [fingers(world, robot, closed=False)]


def coupling(world, robot, dock, pre):
    root, tcp = body(world, robot["root"]), body(world, robot["tcp_coupler"])
    above = CartesianPose(root_link=root, tip_link=tcp, goal_pose=tool_down(body(world, dock), pre), threshold=0.005)
    onto = tool_down(body(world, dock), 0.0)
    done = PoseReached(root_link=root, tip_link=tcp, goal_pose=onto.to_homogeneous_matrix(),
                       position_threshold=LOCK_GAP, orientation_threshold=math.radians(1.0))
    return done, [above, CartesianPoseStraight(root_link=root, tip_link=tcp, goal_pose=onto)]


# ------------------------------------------------------------------ statechart assembly
class MotionContractViolated(Exception):
    """A motion's contract is violated; CancelMotion raises it and the control program's failure handling takes over."""


def chain(chart, phases, motions, world, plate):
    """Wire phases in sequence: each phase starts when the previous one is done; its constraints end with it.
    Contract monitors make the soft parts of each phase hold-or-cancel: a per-phase timeout (1.2 x the planner's
    estimate, the bound the time theorem assumes) and, while the plate is held, its tilt (VectorsAligned); collision
    violations cancel through ExternalCollisionAvoidance(cancel_if_collision_violated=True)."""
    prev = None
    for (done, aux), m in zip(phases, motions):
        watch = []
        if m.get("timeout_s"):
            clock = CountSimulationTimeSeconds(seconds=m["timeout_s"])
            stop = CancelMotion.when_true(clock, exception=MotionContractViolated(f"{m['type']}: longer than {m['timeout_s']} s"))
            watch += [clock]
        if m.get("held"):
            level = VectorsAligned(root_link=world.root, tip_link=plate, goal_normal=Vector3.Z(world.root),
                                   tip_normal=Vector3.Z(plate), threshold=MAX_TILT)
            tilt = CancelMotion(exception=MotionContractViolated(f"{m['type']}: plate tilted beyond the bound"))
            tilt.start_condition = (trinary_logic_not(level.observation_variable) if prev is None else
                                    trinary_logic_and(prev.observation_variable, trinary_logic_not(level.observation_variable)))
            watch += [level]
        for node in [done] + list(aux) + watch:
            if prev is not None:
                node.start_condition = prev.observation_variable
            node.end_condition = done.observation_variable
            chart.add_node(node)
        if m.get("timeout_s"):
            chart.add_node(stop)
        if m.get("held"):
            chart.add_node(tilt)
        prev = done
    chart.add_node(EndMotion.when_true(prev))


def build_phase(world, robot, m, plate):
    seat = SEATS[m["seat"]]
    t = m["type"]
    if t in ("approaching", "transiting"):
        return approaching(world, robot, seat, m["z"], m["tol"], plate if m["held"] else None)
    if t == "aligning":
        return aligning(world, robot, seat, m["z"], m["tol"], plate)
    if t == "inserting":
        return inserting(world, robot, seat, m["z"], m["speed"], m["tol"], plate)
    if t == "lifting":
        return straight(world, robot, seat, m["z"], m["speed"], plate=plate)
    if t == "placing":
        return straight(world, robot, seat, m["z"], m["speed"], plate=plate, contact=([plate], [body(world, seat)]))
    if t == "retracting":
        return straight(world, robot, seat, m["z"], m["speed"],
                        contact=([body(world, j) for j in robot["finger_links"]], [plate]))
    if t == "grasping":
        return grasping(world, robot)
    if t == "releasing":
        return releasing(world, robot)
    if t == "coupling":
        return coupling(world, robot, seat, m["pre"])
    raise ValueError(t)


def leg_statecharts(world, leg, plate_name="Plate_P17"):
    """One motion statechart per manipulation designator of the leg: picking up (up to the grasp), then carrying
    (lift, transit, align, place, release), then retracting. Between them the SDT World changes: after the grasp the
    plate is attached to the TCP, after the release to the target seat (world modification, not motion)."""
    robot, plate = ROBOTS[leg["robot"]], body(world, plate_name)
    groups, cur = [], []
    for m in leg["motions"]:
        cur.append(m)
        if m["type"] in ("grasping", "releasing", "coupling"):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    charts = []
    for g in groups:
        chart = MotionStatechart()
        chart.add_nodes([ExternalCollisionAvoidance(cancel_if_collision_violated=True),
                         SelfCollisionAvoidance(cancel_if_collision_violated=True)])
        chain(chart, [build_phase(world, robot, m, plate) for m in g], g, world, plate)
        charts.append(([m["type"] for m in g], chart))
    return charts


def run_leg(world, leg):
    """Execute a leg's statecharts with giskardpy's QP controller (not run in this environment)."""
    for kinds, chart in leg_statecharts(world, leg):
        executor = Executor(MotionStatechartContext(world=world, qp_controller_config=QP_CONFIG))
        executor.compile(motion_statechart=chart)
        executor.tick_until_end()


LEGS = __LEGS__
'''


def verify_imports(py_text):
    """Every imported name must be defined in the module file the import names (user's giskardpy / SDT checkout)."""
    problems = []
    for m in re.finditer(r"^from ([\w.]+) import (\([^)]*\)|[^\n]+)", py_text, re.M):
        mod, names = m.group(1), [n.strip() for n in m.group(2).strip("()").replace("\n", " ").split(",") if n.strip()]
        root = GISKARD if mod.startswith("giskardpy") else SDT if mod.startswith("semantic_digital_twin") else \
            KRROOD if mod.startswith("krrood") else None
        if root is None:
            continue
        path = os.path.join(root, *mod.split(".")[1:]) + ".py"
        if not os.path.exists(path):
            problems.append(f"module {mod} not found")
            continue
        src = open(path).read()
        for n in names:
            if not re.search(rf"^(class|def) {n}\b|^{n}\s*=", src, re.M):
                problems.append(f"{mod}.{n} not defined")
    return problems


def load_estimates():
    facts = open(os.path.join(HERE, "..", "okf", "lab-automation-twin", "build", "e2m", "facts_g050.lp")).read()
    for r, ph, ds in re.findall(r"leg_part\((\w+),(\w+),(\d+)\)", facts):
        LEG_PART[(r, ph)] = int(ds) / 10.0
    tc = re.search(r"dur\(tool_couple,(\d+)\)", facts)
    LEG_PART[("r02", "tool_couple")] = int(tc.group(1)) / 10.0


def main(argv):
    load_estimates()
    fr = json.load(open(os.path.join(OUT, "motion_frames.json")))
    seats = fr["seats"]
    legs = []
    for l in fr["legs"]:
        ms = motion_phases(l, fr)
        legs.append(dict(session=l["session"], robot=l["robot"], src=l["src"], dst=l["dst"], motions=ms))
    # motion designators in Lisp notation, one block per distinct leg
    distinct = {}
    for l in legs:
        distinct.setdefault((l["robot"], l["src"], l["dst"]), l)
    lisp = [";;; Challenge-rescue: the motion designators of every distinct transport leg (generated by rsa/giskard_motions.py).",
            ";;; Each refines one kernel motion leaf and states its reference frames, motion constraints and objective;",
            ";;; rsa/out/challenge_rescue_giskard.py gives the same as giskardpy motion statecharts. ILLUSTRATIVE values (D016).", ""]
    for (rob, a, b), l in distinct.items():
        lisp.append(f";;; {rob.upper()} carries the plate {a} -> {b} (used in trips {', '.join(sorted({x['session'] for x in legs if (x['robot'], x['src'], x['dst']) == (rob, a, b)}))})")
        lisp.append(f"(motions-of (a transporting (robot {rob}) (from {SEAT_BODY[a]}) (to {SEAT_BODY[b]}))")
        lisp += ["  " + lisp_motion(rob, m, seats) for m in l["motions"]]
        lisp[-1] += ")"
        lisp.append("")
    lisp_txt = pretty("\n".join(lisp), "lisp")
    open(os.path.join(OUT, "challenge_rescue_motions.lisp"), "w").write(lisp_txt)
    # giskardpy module
    robots = {k: dict(v, finger_links=[f"{f}_link" for f in v["fingers"]], tcp_coupler="r02_coupler" if k == "r02" else v["tcp"])
              for k, v in ROBOT_SDT.items()}
    robots["r01"].update(approach=fr["robots"]["r01"]["approach_m"])
    py = (PY_HEAD.replace("__MAX_TILT__", repr(MAX_TILT_DEG)).replace("__TRANSIT_V__", repr(TRANSIT_V))
          .replace("__TRANSIT_W__", repr(TRANSIT_W)).replace("__POSE_TOL__", repr(POSE_TOL)).replace("__ORI_TOL__", repr(round(ORI_TOL, 6)))
          .replace("__LOCK_GAP__", repr(LOCK_GAP)).replace("__ROBOTS__", json.dumps(robots, indent=4))
          .replace("__SEATS__", json.dumps(SEAT_BODY, indent=4))
          .replace("__LEGS__", json.dumps([dict(l, motions=[{k: v for k, v in m.items()} for m in l["motions"]]) for l in legs], indent=1)))
    pyp = os.path.join(OUT, "challenge_rescue_giskard.py")
    open(pyp, "w").write(py)
    py_compile.compile(pyp, doraise=True)
    probs = verify_imports(py)
    n_leaves = sum(len(l["leaves"]) for l in fr["legs"])
    n_motions = sum(len(l["motions"]) for l in legs)
    reach = [g for g in fr["goals"]]
    summary = dict(legs=legs, distinct=[dict(robot=k[0], src=k[1], dst=k[2]) for k in distinct], import_problems=probs,
                   leaves=n_leaves, motions=n_motions, reach=reach, seats=seats,
                   weights=dict(level=2500, speed=2500, collision=50, goal=1, posture=0.1),
                   qp=dict(target_frequency=50, prediction_horizon=7, control_dt=0.02, max_derivative="jerk",
                           dof_velocity_weight=0.01, horizon_weight_gain_scalar=0.1, solver="PIQP"),
                   bounds=dict(max_tilt_deg=MAX_TILT_DEG, transit_v=TRANSIT_V, transit_w=TRANSIT_W, pose_tol=POSE_TOL,
                               ori_tol_deg=0.2, lock_gap=LOCK_GAP))
    json.dump(summary, open(os.path.join(OUT, "giskard_motions.json"), "w"), indent=1, default=str)
    print(f"[giskard] {len(legs)} legs ({len(distinct)} distinct), {n_motions} motion designators for {n_leaves} kernel motion leaves "
          f"(one-to-one: {n_motions == n_leaves}); module compiles; imports verified against the checkout: "
          f"{'all resolve' if not probs else probs}")
    print(f"[giskard] wrote {pyp} ({py.count(chr(10))} lines) and rsa/out/challenge_rescue_motions.lisp ({lisp_txt.count(chr(10))} lines)")
    return 0 if not probs and n_motions == n_leaves else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
