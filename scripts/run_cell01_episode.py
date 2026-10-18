"""First end-to-end Cell 01 episodes: L10 release -> R01 -> L09 store, or H4 quarantine on an identity fault.

Scene: scenes/cell01_twin.usda (layout P1) with the H4, L09 and L10 twins and their controllers in the loop, the FR3
+ plate gripper on R01 (twin/r01_rig.py), and plates with barcodes preloaded in L10 cassette slots.

One generic executive runs each episode as CRAM designators (Cell 01 sdt/schemas/cram_designator_schemas.yaml):
  retrieve   L10 release_plate(plate_id): handler brings the plate to the stowed nest, its barcode reader checks
             identity, the shuttle presents it; R01 picks it; L10 stows (gate closed).
  transport  R01 carries it at transit height to the target nest and places it (compliant insertion).
  store      L09 store(plate_id, slot): L09 reads the barcode again, stores, confirms the slot.
  quarantine on an identity fault (failure routing H4_quarantine_if_identity_or_contamination_unresolved):
             H4 presents, L10 presents the faulted plate for removal (present_for_removal), R01 carries it to H4,
             H4 quarantine_sample(observed identity) closes and locks; an unauthorised release must be refused.
Monitor values come from the simulated devices (barcode rays, seat sensors, slot rays, joint states, contact
reports, the L10 environment model), never from the plan.

Episodes:
  nominal        Plate_P17 in L10 slot 2 (inventory agrees) -> L09 slot 3.
  identity_swap  L10's inventory says slot 5 holds Plate_P18, but the plate there carries Plate_P23 (a swap at
                 manual loading). Expected: caught at L10's reader, routed to H4; Plate_P18 unaccounted for.
  quarantine_release  (continues identity_swap) a human review resolves Plate_P23 and authorises its release: the
                 operator turns H4's key to RELEASE and the token is given; H4 presents the plate; R01 returns it to
                 L10, which re-reads its barcode and incubates it (incubate designator with environment monitors).
                 Plate_P18 stays escalated.
  imaging        Plate_P17 (stored in L09 by `nominal`) is imaged by L17 and returned: L09 retrieve -> R01 -> the
                 R01/R02 handover nest -> R02 with T01 (tool change from TCM01) -> L17 (identity read at load,
                 autofocus, wells B02..B04 at 10x) -> R02 -> handover nest -> R01 -> L09 store. Each image gets an
                 L17 record from Cell 01's own validity and record builder (physical_workflow.build_l17_neem_record).
                 An image that fails focus_quality is retained (routed to L21 QC / human) and the well is refocused
                 from scratch and reacquired once (the contract's out_of_focus recovery).

Writes test_reports/episodes/cell01_episodes_raw.json and, via twin/episode_records.py, the NEEM-compatible
records cell01_episodes_records.json (validated against the Cell 01 schemas). Exit 1 unless both episodes end as
expected and every record validates.
Usage: env_isaacsim/bin/python scripts/run_cell01_episode.py [--episodes nominal,identity_swap,quarantine_release,imaging]
"""

import argparse
import json
import math
import os
import sys
import time

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
ap = argparse.ArgumentParser()
ap.add_argument("--episodes", default="nominal,identity_swap,quarantine_release,imaging")
ap.add_argument("--place-mode", choices=("compliant", "drop"), default="compliant")
ap.add_argument("--frames", default=None, help="directory for path-traced stills at the key moments (presentations)")
ap.add_argument("--quick", action="store_true", help="with --frames: 1280x800, fewer samples")
ap.add_argument("--frame-filter", default="", help="with --frames: only frames whose name contains this")
ap.add_argument("--scene", choices=("cell01", "lab"), default="cell01",
                help="lab: the whole AICOR Lab 1 (scenes/lab_twin.usda); R03 starts in the storage room's S1 dock and "
                     "comes in through the storage door, the AMR lane and the Cell 01 portal")
ap.add_argument("--video", default=None, help="directory for a video of the run (RTX real-time frames + MP4)")
ap.add_argument("--rsa", default=None, help="run the rsa kernel (action designators) on the twin: a scenario of "
                "rsa/registry/scenarios_isaac.yaml (rsa/isaac.py)")
ap.add_argument("--plan", default=None, help="execute a derived plan (okf/.../derivation/out/plan_<tag>.json): every "
                "trip of every session, step by step, on the twin's controllers; writes test_reports/e2m/")
args = ap.parse_args()

LAB = args.scene == "lab"
OVERLAY = os.path.join(ROOT, "scenes/lab_twin.usda" if LAB else "scenes/cell01_twin.usda")
OUT_DIR = os.path.join(args.video, "records") if args.video else os.path.join(ROOT, "test_reports/episodes")
if args.plan:
    OUT_DIR = os.path.join(args.video, "records") if args.video else os.path.join(ROOT, "test_reports/e2m")
    args.episodes = "plan"
H4 = "/World/Cell01/Stations/H4_Quarantine"
L09 = "/World/Cell01/Stations/L09_PlateHotel"
L10 = "/World/Cell01/Stations/L10_Incubator"
L17 = "/World/Cell01/Stations/L17_BrightFieldImager"
L12 = "/World/Cell01/Stations/L12_LiquidHandler"
L21 = "/World/Cell01/Stations/L21_QC_Calibration"
R03 = "/World/Cell01/Robots/R03_SampleAMR"
H2 = "/World/Cell01/Stations/H2_AMR_Dock"
REF_ID = "REF-L21-001"
AMR_START = (-2.565, 2.72, -math.pi / 2)        # R03 map pose: world (1.2, -3.0), heading north, outside the cell
AMR_IN = [AMR_START[:2], (-2.565, 0.72), (-2.165, 0.0), (-1.0, 0.0)]
AMR_OUT = [(-1.0, 0.0), (-2.165, 0.0), (-2.565, 0.72), (-2.565, 2.72)]
if LAB:   # R03 starts docked in the storage room's S1 dock (world (-6.4, 0.6), heading north); site route legs
    S1_WORLD = (-6.4, 0.6, 90.0)
    AMR_START = (-(S1_WORLD[0] + 1.415), -(S1_WORLD[1] + 0.28), math.radians(S1_WORLD[2] - 180.0))
    _w2m = lambda pts: [(-(x + 1.415), -(y + 0.28)) for (x, y) in pts]   # noqa: E731
    AMR_STORE_OUT = _w2m([(-6.4, 0.6), (-6.4, -2.4)])
    AMR_LEGS = [_w2m(leg) for leg in ([(-6.4, -2.4), (-6.4, -3.3)], [(-6.4, -3.3), (1.15, -3.3)],
                                      [(1.15, -3.3), (1.15, -1.0), (0.75, -0.28), (-0.415, -0.28)])]
    AMR_IN = AMR_STORE_OUT + [p for leg in AMR_LEGS for p in leg[1:]]
R01 = "/World/Cell01/Robots/R01_FR3"
FR3_PATH, GRIP_PATH = f"{R01}/FR3", f"{R01}/PlateGripper"
# Episode request parameters. These belong to the requesting protocol, not to the twin; the values are DEMO
# parameters chosen for this functional test, not biological or validated values (Cell 01 rule D016).
PROTOCOL = {"protocol_window_s": 600.0, "intended_incubation": "PT24H",
            "storage_environment": "ambient_accepted_by_request",
            "note": "demo request parameters for the twin episode; not biological or validated values (D016)"}
# initial physical state (plate prim, barcode on the plate, L10 slot) and the SDT inventory belief of L10
PLATES = {"P17": dict(barcode="Plate_P17", slot=2, inventory="Plate_P17"),
          "P23": dict(barcode="Plate_P23", slot=5, inventory="Plate_P18")}
# quarantine review: a HUMAN decision, supplied here as simulated input and recorded as such in the evidence
REVIEW = {"reviewer": "QA reviewer (simulated human input)", "decision": "release_to_L10",
          "authorization": "QA-2026-10-16-001", "return_slot": 5,
          "resolution": "Plate_P23 confirmed by its label and sample record; it had been loaded into L10 slot 5 in "
                        "place of Plate_P18 (inventory swap at manual loading). Return it to L10 slot 5. Plate_P18 "
                        "remains unaccounted for (separate escalation)."}
# imaging request (demo parameters: exposure / magnification are acquisition settings; the window is a request
# parameter for this functional test, not a biological value, D016)
IMAGING = dict(plate_id="Plate_P17", wells="B02:B04", magnification="10x", exposure_ms=25.0,
               measurement_binding_id="brightfield-morphology-v1", return_slot=3,
               request={"imaging_window_s": 1800.0, "note": "demo request parameters for the twin episode (D016)"})
EPISODES = {"nominal": dict(plate_id="Plate_P17", store_slot=3),  # "full_cell" filled in below (FULL)
            "identity_swap": dict(plate_id="Plate_P18", store_slot=4),
            "quarantine_release": dict(sample_id="Plate_P23", review=REVIEW),
            "imaging": IMAGING, "full_cell": None}

from isaacsim import SimulationApp  # noqa: E402

RES = (1280, 800) if args.quick else (1920, 1200)
if args.video:
    RES = (1920, 1080)
app = SimulationApp({"headless": True, **({"renderer": "PathTracing", "width": RES[0], "height": RES[1]} if args.frames
                                          else {"renderer": "RaytracedLighting", "width": RES[0], "height": RES[1]}
                                          if args.video else {})})

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402

for ext in ("isaacsim.robot.surface_gripper", "isaacsim.robot.schema"):   # R02's tool coupler
    app_utils.enable_extension(ext)
app.update()

import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from pxr import PhysxSchema, UsdGeom  # noqa: E402

from twin.episode_records import build_all  # noqa: E402
from twin.h4_controller import H4Controller  # noqa: E402
from twin.hn_monitor import HandoverNest  # noqa: E402
from twin.l12_controller import L12Controller, add_reagent_tube, add_tips, author_l12  # noqa: E402
from twin.l17_controller import L17Controller  # noqa: E402
from twin.l21_controller import L21Controller, qc_designator  # noqa: E402
from twin.r03_controller import R03Controller, author_r03_start, carrier_seat_world  # noqa: E402
from twin.r02_controller import R02Controller, ToolChanger  # noqa: E402
from twin.r02_rig import R02Rig, author_r02  # noqa: E402
from twin.l09_controller import PlateStoreController  # noqa: E402
from twin.l10_controller import L10Controller  # noqa: E402
from twin import r01_planner  # noqa: E402
from twin.render import StillCamera  # noqa: E402
from twin.r01_rig import APPROACH, GRIP_Z_ABOVE_BOTTOM, HZ, R01Rig, add_plate, author_rig, frame_pose, tool_down  # noqa: E402

omni.usd.get_context().open_stage(OVERLAY)
for _ in range(10):
    app.update()
stage = omni.usd.get_context().get_stage()
px = PhysxSchema.PhysxSceneAPI.Apply(stage.GetPrimAtPath("/World/PhysicsScene"))
px.CreateTimeStepsPerSecondAttr(HZ)
px.CreateSolverTypeAttr("TGS")

plate_paths = {}
for name, p in PLATES.items():
    pos, yaw = frame_pose(stage, f"{L10}/cassette_slots/slot_{p['slot']:02d}")
    plate_paths[name] = f"/World/Episode/Plate_{name}"
    add_plate(stage, plate_paths[name], pos + [0, 0, 0.0005], yaw, barcode=p["barcode"])
plate_paths["P30"] = "/World/Episode/Plate_P30"    # arrives with the AMR: in its carrier nest, AMR outside the cell
author_r03_start(stage, R03, AMR_START)
_p30, _y30 = carrier_seat_world(stage, R03, AMR_START)
add_plate(stage, plate_paths["P30"], _p30 + [0, 0, 0.0005], _y30, barcode="Plate_P30")
REF_PATH = "/World/Episode/RefPlate"
add_plate(stage, REF_PATH, np.array(UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(
    f"{L21}/reference_plate_frame")).ExtractTranslation()) + [0, 0, 0.0005], 0.0, barcode=REF_ID)
for _pp in (plate_paths["P30"], REF_PATH):
    PhysxSchema.PhysxRigidBodyAPI.Apply(stage.GetPrimAtPath(_pp)).CreateSleepThresholdAttr(0.0)
GRIP12 = author_l12(stage, L12)
TIPS12 = add_tips(stage, L12, [f"{r}{c:02d}" for c in (1, 2) for r in "ABCDEFGH"])
add_reagent_tube(stage, L12, 1, "RGT-0001", "abstract_challenge_reagent", "SIM-LOT-A", 1000.0)
if args.plan or args.rsa:   # the derived plan's rescue reagent (E2M7: reagent(rescue) = reagent rack position 2)
    add_reagent_tube(stage, L12, 2, "RGT-0002", "abstract_rescue_reagent", "SIM-LOT-B", 1000.0)
fr3_local = UsdGeom.Xformable(stage.GetPrimAtPath(f"{R01}/base_link")).GetLocalTransformation()
ART_ROOT = author_rig(stage, FR3_PATH, GRIP_PATH, f"{R01}/Pedestal", fr3_local, contact_prims=list(plate_paths.values()))
R02_ART, R02_WRIST, R02_COUPLER = author_r02(stage)
for _ in range(5):
    app.update()
with open(os.path.join(ROOT, "scenes/layout_p1.json")) as f:
    LAYOUT = json.load(f)
HN_PRIM = LAYOUT["fixtures"]["HN"]["prim"]
OBSTACLES = r01_planner.obstacles_from_stage(stage, LAYOUT)
_base_w = UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(f"{R01}/base_link"))
BASE = np.array(_base_w.ExtractTranslation())
assert abs(_base_w.ExtractRotationMatrix()[0][0] - 1.0) < 1e-6, "planner assumes R01's base_link is not rotated"
NEST = {"L10": frame_pose(stage, f"{L10}/transfer_station"), "L09": frame_pose(stage, f"{L09}/transfer_nest"),
        "H4": frame_pose(stage, f"{H4}/transfer_nest"), "HN": frame_pose(stage, f"{HN_PRIM}/handover_frame"),
        "L17": frame_pose(stage, f"{L17}/plate_load_frame"), "L12": frame_pose(stage, f"{L12}/plate_nest"),
        "L21ref": frame_pose(stage, f"{L21}/reference_plate_frame"), "R03": frame_pose(stage, f"{R03}/handover_carrier_frame")}

app_utils.play(commit=True)
h4 = H4Controller(stage, H4)
l09 = PlateStoreController(stage, L09)
l10 = L10Controller(stage, L10)
for p in PLATES.values():
    l10.inventory[p["slot"]] = p["inventory"]  # the SDT's belief at episode start (P18's entry is wrong)
l17 = L17Controller(stage, L17, image_dir=os.path.join(OUT_DIR, "l17_images"))
hn = HandoverNest(stage, HN_PRIM)
l12 = L12Controller(stage, L12, GRIP12, tips=dict(TIPS12), reagent_inventory={
    1: dict(reagent_id="abstract_challenge_reagent", lot="SIM-LOT-A", volume_uL=1000.0),
    **({2: dict(reagent_id="abstract_rescue_reagent", lot="SIM-LOT-B", volume_uL=1000.0)} if args.plan or args.rsa
       else {})})
l21 = L21Controller(stage, L21)
amr = R03Controller(stage, R03, H2)
amr._command_est(np.array(AMR_START))
STATIONS = [h4.update, l09.update, l10.update, l17.update, hn.update, l12.update, l21.update, amr.update]
if LAB:   # storage sliding door, Cell 01 door interlock + AMR-portal light curtain (twin/site_doors.py)
    from twin.site_doors import Door, Interlock, LightCurtain  # noqa: E402
    store_door = Door(stage, "/World/AICOR_Lab/Building/Doors/ST01_Sliding")
    curtain = LightCurtain(stage, R03)
    interlock = Interlock(stage, curtain)

    def _site(dt):
        interlock.update(dt)
        store_door.update(interlock.t)
    STATIONS.append(_site)
r02rig = None   # R01 and R02 step the same simulation; each rig's step advances the other's clock


def _r02_clock(dt):
    if r02rig is not None:
        r02rig.t += dt


def _r01_clock(dt):
    rig.t += dt


rig = R01Rig(ART_ROOT, GRIP_PATH, plates=list(plate_paths.values()), on_step=STATIONS + [_r02_clock],
             place_mode=args.place_mode, contacts=True)
r02rig = R02Rig(R02_ART, R02_WRIST, R02_COUPLER, on_step=STATIONS + [_r01_clock], log=lambda m: print(m, flush=True))
r02rig.t = rig.t
r02 = R02Controller(stage, r02rig)
tcm = ToolChanger(stage, r02rig, r02)
by_barcode = {p["barcode"]: plate_paths[n] for n, p in PLATES.items()} | {"Plate_P30": plate_paths["P30"]}
VIEWS = {"cluster": ((-0.25, -1.35, 1.85), (-1.80, 0.50, 1.00), 20.0),
         "h4": ((-1.25, -0.65, 1.55), (-2.05, 0.10, 1.00), 24.0),
         "l10": ((-1.25, 0.05, 1.60), (-1.95, 0.85, 1.05), 22.0),
         "l10_side": ((-2.60, 0.30, 1.75), (-1.95, 0.80, 1.00), 22.0),   # from west of H4: R01 does not hide the tray
         "elevated": ((0.55, -2.05, 2.55), (-1.70, 0.50, 0.95), 20.0),
         "hn": ((-0.35, -0.75, 1.75), (-1.05, 0.55, 1.00), 22.0),
         "l17": ((0.75, 0.05, 1.75), (1.62, 1.30, 1.00), 22.0),
         "l21": ((1.30, 0.20, 1.70), (2.10, 1.15, 1.00), 24.0),
         "l12": ((-0.45, -0.75, 1.75), (0.15, 0.30, 0.98), 22.0),
         "amr": ((-0.55, -1.45, 1.60), (-1.45, -0.28, 0.70), 24.0)}
cam = StillCamera(stage, RES, *((8, 8) if args.quick else (16, 32))) if args.frames else None


def still(name, view):
    """Path-traced still of the current simulated state (only with --frames)."""
    if cam and args.frame_filter in name:
        t0 = time.time()
        print(f"[episode]   frame {cam.capture(os.path.join(args.frames, name + '.png'), *VIEWS[view])} "
              f"({time.time() - t0:.0f}s)", flush=True)
rig.step(int(1.0 * HZ))
initial = {"L10_inventory": {k: v for k, v in enumerate(l10.inventory) if v},
           "L10_slots_occupied": [k for k, o in enumerate(l10.slot_occupied) if o],
           "L10_environment": {k: round(v, 3) for k, v in l10.env.items()}, "L09": l09.snapshot()["mode"],
           "H4": h4.mode}
initial["R03_carrier_seated"] = bool(amr.carrier_seated)
print(f"[episode] initial {initial}")
assert all(l10.slot_occupied[p["slot"]] for p in PLATES.values()), initial


# ------------------------------------------------------------------------------ helpers
def mon(name, passed, observation, value=None):
    return {"name": name, "passed": bool(passed), "observation": observation, "value": value}


def events_since(ctrl, t0, *names):
    return [e for e in ctrl.events if e["t"] >= t0 and (not names or e["event"] in names)]


def wait(pred, timeout, what):
    ok = rig.run_until(pred, timeout)
    print(f"[episode]   {what}: {'ok' if ok else 'TIMEOUT'} (t={rig.t:.1f}s)")
    return ok


IMPULSE_CONTACT = 1e-4  # N*s; pairs reported with less are within PhysX's contact offset but not touching


def robot_contacts(phase, held):
    """Contacts of the robot / gripper / held plate with anything else in a phase, split into real contacts
    (impulse > 0) and proximity reports (inside the contact offset, no force); robot-internal pairs, the fingers on
    the held plate, and plates resting in stations are excluded."""
    real, near = {}, {}
    for pair, v in rig.contact_log.get(phase, {}).items():
        robotish = [p.startswith(R01 + "/") for p in pair]
        on_held = [bool(held) and (p == held or p.startswith(held + "/")) for p in pair]
        if all(robotish) or (any(on_held) and any(p.startswith(GRIP_PATH + "/") for p in pair)):
            continue
        if not any(robotish) and not any(on_held):
            continue
        (real if v[2] > IMPULSE_CONTACT else near)[" | ".join(p.split("/World/")[-1] for p in pair)] = \
            [v[0], v[1], round(v[2], 4)]
    return real, near


def at(nest):
    p, yaw = NEST[nest]
    return p.copy(), yaw


def go_above(nest, held, phase=None):
    """Planned joint-space transit to the approach pose above a nest (twin/r01_planner.py), then a short Cartesian
    convergence; the null-space posture is pinned to the planned configuration for the station work."""
    p, yaw = at(nest)
    above = p + [0, 0, GRIP_Z_ABOVE_BOTTOM + APPROACH]
    wps, info = r01_planner.plan(rig.q_arm(), above - BASE, yaw, OBSTACLES, held=held,
                                 p_low=p - BASE + [0, 0, GRIP_Z_ABOVE_BOTTOM])
    if wps is None:
        print(f"[episode]   NO TRANSIT PLAN to {nest}: {info}")
        return False, info
    rig.phase = phase
    ok = all(rig.move_joints(q) for q in wps[1:])
    rig.posture = np.array(wps[-1])
    ok2, ep, er = rig.move_to(above, tool_down(yaw))
    rig.phase = None
    info.update(waypoints_deg=[np.round(np.degrees(q), 1).tolist() for q in wps[1:]], converged=bool(ok and ok2),
                residual_mm=round(ep, 2))
    print(f"[episode]   transit to {nest} (held={held}): {info}")
    return ok and ok2, info


# ------------------------------------------------------------------------------ executive
def run_episode(episode_id, scenario, plate_id, store_slot):
    print(f"[episode] === {episode_id} ({scenario}): retrieve {plate_id} from L10")
    t_ep = rig.t
    ds, escalations = [], []
    l10_slot = l10.inventory.index(plate_id) if plate_id in l10.inventory else None

    # ---- retrieve (L10 release + R01 pick)
    t0 = rig.t
    r = l10.release_plate(plate_id)
    released = r.accepted and wait(lambda: l10.mode in ("PRESENTED_LOADED", "FAULT"), 120, "L10 release")
    reads = events_since(l10, t0, "identity_read")
    observed = reads[-1]["observed"] if reads else None
    identity_ok = released and l10.mode == "PRESENTED_LOADED" and observed == plate_id
    route = "store" if identity_ok else "quarantine"
    if not identity_ok and l10.mode == "FAULT" and l10.fault == "slot_identity_mismatch":
        reason = f"identity mismatch at L10 release: expected {plate_id}, barcode read {observed!r}"
        rp = l10.present_for_removal(reason)
        h4.present_nest()
        released = rp.accepted and wait(lambda: l10.mode == "PRESENTED_LOADED" and h4.mode == "PRESENTED", 60,
                                        "L10 present for removal + H4 present")
    elif identity_ok:
        l09.present_for_load()
    held = by_barcode.get(observed)
    release_rec = l10.released.get(plate_id) or {"t": next((e["t"] for e in events_since(l10, t0, "present_for_removal_accepted")), None),
                                                 "environment": {k: round(v, 3) for k, v in l10.env.items()},
                                                 "environment_valid": l10.environment_valid}
    p_src, yaw_src = at("L10")
    if released and held:
        go_above("L10", held=False)
        if route == "quarantine":
            still(f"{scenario}_1_identity_fault_at_L10", "l10_side")
    rig.phase = "pick"
    grasp = rig.pick(p_src, yaw_src, "pick_L10", plate=held) if (released and held) else {"lifted": False}
    rig.phase = None
    grasp["robot_contacts"], grasp["robot_proximity"] = robot_contacts("pick", held)
    l10.stow()
    stowed = wait(lambda: l10.mode == "READY", 30, "L10 stow (gate closed)")
    exposure = rig.t - release_rec["t"] if release_rec.get("t") is not None else None
    ds.append({
        "id": f"{episode_id}/retrieve", "action": "retrieve", "component": "L10_Incubator",
        "interaction_frames": {"source_frame": "transfer_station"},
        "bindings": {"object_id": plate_id, "source_component_id": "L10", "source_frame": "transfer_station",
                     "target_frame": "L09/transfer_nest" if route == "store" else "H4/transfer_nest",
                     "identity_binding": "barcode read at the L10 stowed transfer nest (labware:barcode)",
                     "source_slot": l10_slot},
        "monitors": [
            mon("plate_identity", identity_ok, f"L10 barcode reader: expected {plate_id}, read {observed!r}",
                {"expected": plate_id, "observed": observed}),
            mon("grasp_confirmed", grasp.get("lifted") and grasp.get("contact"),
                "R01 jaws closed on the plate and lifted it", grasp),
            mon("source_release_state", stowed and release_rec.get("t") is not None,
                "L10 release observed; gate closed after the pick", {"release": release_rec, "L10_mode": l10.mode}),
            mon("time_outside_environment", exposure is not None and exposure <= PROTOCOL["protocol_window_s"],
                f"{exposure:.1f} s outside L10 after the pick (protocol window {PROTOCOL['protocol_window_s']:.0f} s)"
                if exposure is not None else "release time unknown", round(exposure or -1, 2)),
        ],
        "command_completed": bool(released and grasp.get("lifted")), "t_start": round(t0, 3), "t_end": round(rig.t, 3),
        "semantic_target": "CultureSDT.custody_event", "semantic_effect": f"{plate_id} left L10",
        "failure_route": "H4_quarantine", "failure_target": "H4",
        "evidence": {"identity_observation": observed, "timestamps": {"release": release_rec.get("t"), "picked": round(rig.t, 3)}},
        "device_events": events_since(l10, t0),
    })
    if not grasp.get("lifted"):
        return ds, escalations, {"route": route, "aborted": "retrieve"}

    # ---- transport (R01) to the target nest
    target = "L09" if route == "store" else "H4"
    t0 = rig.t
    p_tgt, yaw_tgt = at(target)
    ok_transit, transit_info = go_above(target, held=True, phase="transit")
    still(f"{scenario}_2_carrying_to_{target}", "h4" if target == "H4" else "cluster")
    rig.phase = "place"
    placed, info = rig.place(p_tgt, yaw_tgt, contacts_phase="insert")
    rig.phase = None
    tgt_ctrl = l09 if target == "L09" else h4
    rig.step(int(0.5 * HZ))
    seated = bool(tgt_ctrl.seated)
    transit_bad, transit_near = robot_contacts("transit", held)
    place_bad, place_near = robot_contacts("place", held)
    for ph, (c, n) in {"pick": (grasp["robot_contacts"], grasp["robot_proximity"]), "transit": (transit_bad, transit_near),
                       "place": (place_bad, place_near)}.items():
        print(f"[episode]   robot contacts {ph}: real {c or '-'}; proximity {list(n) or '-'}")
    slip = rig.held["dropped"]
    ds.append({
        "id": f"{episode_id}/transport", "action": "transport", "component": "R01_FR3_PlateArm",
        "interaction_frames": {"grasp_frame": "plate_grasp_frame", "tool_frame": "tool0"},
        "bindings": {"object_id": observed, "source_frame": "L10/transfer_station", "target_frame": f"{target}/transfer_nest",
                     "route": f"planned joint-space transit between the {APPROACH:.2f} m approach poses (twin/r01_planner.py)",
                     "contamination_state": "not modelled (assumption: lidded plate, closed route)"},
        "monitors": [
            mon("route_clear", ok_transit and not transit_bad, "contact report during transit: no contacts besides "
                "the fingers on the plate" if not transit_bad else "unexpected contacts during transit",
                {"contacts": transit_bad, "proximity_within_contact_offset": transit_near}),
            mon("object_identity", observed is not None, f"carrying the plate read as {observed!r} at the source",
                observed),
            mon("object_pose_or_grasp", slip is None and placed and seated,
                "no slip > 5 mm in the fingers; plate seated at the target (seat sensors)" if slip is None
                else f"plate slipped: {slip}", {"slip": slip, "seated": seated, **{k: info.get(k) for k in (
                    "release_height_mm", "landing_speed_mm_s", "impedance_lateral_max_mm")}}),
            mon("contamination_compatibility", True, "ASSUMPTION: no contamination model in the twin; lidded plate "
                "on a closed route assumed (epistemic_status: assumption)", "assumption"),
            mon("elapsed_time", rig.t - t0 <= PROTOCOL["protocol_window_s"],
                f"transport took {rig.t - t0:.1f} s (protocol window {PROTOCOL['protocol_window_s']:.0f} s)",
                round(rig.t - t0, 2)),
        ],
        "command_completed": bool(placed and seated), "t_start": round(t0, 3), "t_end": round(rig.t, 3),
        "semantic_target": "CultureSDT.custody_event", "semantic_effect": f"{observed} moved L10 -> {target}",
        "failure_route": "H4_quarantine", "failure_target": "H4",
        "evidence": {"route": {"path": f"L10/transfer_station -> {target}/transfer_nest", "plan": transit_info},
                     "timestamps": {"start": round(t0, 3), "placed": round(rig.t, 3)}, "place": info,
                     "insert_contacts": rig.contacts("insert"),
                     "approach_contacts": {"contacts": place_bad, "proximity_within_contact_offset": place_near}},
    })
    rig.contact_log.clear()

    if target == "L09":
        # ---- store (L09)
        t0 = rig.t
        slot_free_before = not l09.slot_occupied[store_slot] and not l09.inventory[store_slot]
        r = l09.store(plate_id, store_slot)
        done = r.accepted and wait(lambda: l09.mode in ("READY", "FAULT"), 120, "L09 store")
        read = events_since(l09, t0, "identity_read")
        seen = read[-1]["observed"] if read else None
        stored = done and l09.mode == "READY" and l09.inventory[store_slot] == plate_id and l09.slot_occupied[store_slot]
        hist = l10.environment_history(plate_id)
        outside = hist.get("time_outside_controlled_environment_s")
        ds.append({
            "id": f"{episode_id}/store", "action": "store", "component": "L09_PlateHotel",
            "interaction_frames": {"storage_slot_or_frame": "slot_frames[]", "transfer_frame": "transfer_nest"},
            "bindings": {"object_id": plate_id, "storage_component_id": "L09", "storage_slot_or_frame": f"slot_{store_slot:02d}",
                         "environmental_state_binding": PROTOCOL["storage_environment"]},
            "monitors": [
                mon("identity_preserved", seen == plate_id, f"L09 barcode reader: expected {plate_id}, read {seen!r}",
                    {"expected": plate_id, "observed": seen}),
                mon("slot_available", slot_free_before and r.accepted, f"slot {store_slot} empty (ray + inventory) "
                    "and accepted", {"slot": store_slot, "accepted": r.accepted, "reason": r.reason}),
                mon("seating_confirmed", seated and stored, "seated on the L09 nest before the store; slot ray "
                    "occupied after", {"nest_seated": seated, "slot_occupied_after": bool(l09.slot_occupied[store_slot])}),
                mon("environment_accepted", outside is not None and outside <= PROTOCOL["protocol_window_s"],
                    f"ambient storage accepted by the request; {outside} s outside a controlled environment "
                    f"(protocol window {PROTOCOL['protocol_window_s']:.0f} s)", {"time_outside_s": outside,
                                                                                 "binding": PROTOCOL["storage_environment"]}),
            ],
            "command_completed": bool(stored), "t_start": round(t0, 3), "t_end": round(rig.t, 3),
            "semantic_target": "CultureSDT.custody_event", "semantic_effect": f"{plate_id} stored in L09 slot {store_slot}",
            "failure_route": "H4_quarantine", "failure_target": "H4",
            "evidence": {"timestamps": {"start": round(t0, 3), "stored": round(rig.t, 3)},
                         "environment_snapshot": {"L10_environment_history": hist, "L09": "ambient (unconditioned)"}},
            "device_events": events_since(l09, t0),
        })
        l09_after = l09.snapshot()
        outcome = {"route": "store", "stored": stored, "L09_inventory": {k: v for k, v in enumerate(l09.inventory) if v},
                   "L09": l09_after["mode"]}
    else:
        # ---- quarantine (H4)
        t0 = rig.t
        reason = f"identity mismatch at L10 release: expected {plate_id}, barcode read {observed!r}"
        r = h4.quarantine_sample(observed, reason, preceding_anomalies=[f"{episode_id}/retrieve: plate_identity failed"])
        done = r.accepted and wait(lambda: h4.mode == "QUARANTINED", 20, "H4 quarantine")
        snap = h4.snapshot()
        contained = done and snap["locked"] and snap["occupied"] and snap["door_deg"] < 1.0
        r_unauth = h4.release("")   # re-entry must be refused without authorisation (and key)
        rig.step(int(0.5 * HZ))
        reentry_blocked = not r_unauth.accepted and h4.mode == "QUARANTINED"
        still(f"{scenario}_3_quarantined_locked", "h4")
        unacc = l10.unaccounted.get(plate_id)
        if unacc:
            escalations.append({"kind": "plate_unaccounted", "plate_id": plate_id, **unacc,
                                "action": "human search / inventory audit; Culture SDT location of "
                                          f"{plate_id} set to unknown"})
        escalations.append({"kind": "quarantine_review", "sample_id": observed,
                            "action": "human review; release needs an authorisation token AND the H4 key in RELEASE"})
        ds.append({
            "id": f"{episode_id}/quarantine", "action": "quarantine", "component": "H4_Quarantine",
            "interaction_frames": {"quarantine_frame": "quarantine_nest", "door_frame": "door_frame"},
            "bindings": {"object_id": observed, "quarantine_component_id": "H4", "quarantine_frame": "quarantine_nest",
                         "quarantine_reason": reason, "release_authorization_policy": "token AND key switch in RELEASE"},
            "monitors": [
                mon("object_identity_or_uncertainty", observed is not None,
                    f"identity resolved by barcode as {observed!r}; the expected {plate_id} is recorded as unaccounted",
                    {"observed": observed, "expected": plate_id, "expected_unaccounted": unacc}),
                mon("containment_state", contained, "H4 QUARANTINED: plate in the chamber (beam), door closed, bolt "
                    "locked", snap),
                mon("reentry_prevented", reentry_blocked, f"unauthorised release refused: {r_unauth.reason!r}",
                    {"refused": not r_unauth.accepted, "reason": r_unauth.reason}),
            ],
            "command_completed": bool(done), "t_start": round(t0, 3), "t_end": round(rig.t, 3),
            "semantic_target": "CultureSDT.quarantine_event",
            "semantic_effect": f"{observed} contained in H4; scientific evidence from it blocked until authorised release",
            "failure_route": "human_escalation", "failure_target": "human",
            "evidence": {"containment_state": "QUARANTINED" if contained else snap["mode"],
                         "timestamps": {"start": round(t0, 3), "contained": round(rig.t, 3)}},
            "device_events": events_since(h4, t0),
        })
        ds[0]["quarantine"] = {"sample_id": observed, "reason": reason, "execution": {
            "status": "executed" if contained else "failed", "command_completed": bool(done),
            "evidence": [f"{episode_id}/transport", f"{episode_id}/quarantine"]}}
        outcome = {"route": "quarantine", "contained": contained, "reentry_blocked": reentry_blocked,
                   "H4": snap, "L10_unaccounted": dict(l10.unaccounted)}
    outcome["duration_s"] = round(rig.t - t_ep, 1)
    return ds, escalations, outcome


def l10_ready_for_transfer():
    """L10's environment at least halfway from the envelope bound to the setpoint, so a gate opening does not push it
    out. First release episode run: three transfers in two minutes left L10 out of its envelope and it refused the
    incubation."""
    from twin.l10_controller import SETPOINT
    ok = True
    for k, (lo, hi) in l10.envelope.items():
        sp = SETPOINT[k]
        ok &= (lo + sp) / 2 <= l10.env[k] <= (hi + sp) / 2
    return ok and l10.environment_valid


def run_release_episode(episode_id, sample_id, review):
    """Quarantine release: review -> key + token -> H4 presents -> R01 -> L10 incubate (identity re-read at L10)."""
    print(f"[episode] === {episode_id}: release {sample_id} from H4 ({review['decision']})")
    t_ep, ds, esc = rig.t, [], []
    if h4.mode != "QUARANTINED" or h4.sample_id != sample_id:
        return ds, esc, {"aborted": f"{sample_id} is not quarantined in H4 (mode {h4.mode})"}
    q_ev = [e for e in h4.events if e["event"] == "quarantine_sample_accepted" and e.get("sample_id") == sample_id]
    t_q = q_ev[-1]["t"] if q_ev else 0.0
    chain_ok = not any(e["event"] in ("release_accepted",) for e in h4.events if e["t"] > t_q)
    t_out = next((e["t"] for e in reversed(l10.events) if e["event"] == "present_for_removal_accepted"), None)
    t_wait = rig.t
    recovered = wait(l10_ready_for_transfer, 600, "L10 environment recovered for a transfer")
    env_wait = {"waited_s": round(rig.t - t_wait, 1), "recovered": recovered,
                "environment": {k: round(v, 3) for k, v in l10.env.items()}}

    # ---- retrieve from H4 (authorised release)
    t0 = rig.t
    h4._target("key", math.radians(90))                     # HUMAN: operator turns the key to RELEASE
    rig.step(int(1.0 * HZ))
    quarantined_id = h4.sample_id                             # cleared by H4 on release
    r_no_token = h4.release("")                               # still refused without the token
    r = h4.release(review["authorization"])                   # HUMAN: authorisation token from the review
    released = r.accepted and wait(lambda: h4.mode == "PRESENTED" and h4.seated, 15, "H4 authorised release")
    still("quarantine_release_1_authorised_release", "h4")
    h4._target("key", 0.0)                                    # HUMAN: key back to LOCK
    held = by_barcode[sample_id]
    p_h4, yaw_h4 = at("H4")
    if released:
        go_above("H4", held=False)
    rig.phase = "pick"
    grasp = rig.pick(p_h4, yaw_h4, "pick_H4", plate=held) if released else {"lifted": False}
    rig.phase = None
    grasp["robot_contacts"], grasp["robot_proximity"] = robot_contacts("pick", held)
    h4.stow()
    stowed = wait(lambda: h4.mode == "READY", 20, "H4 stow (door closed)")
    exposure = rig.t - t_out if t_out is not None else None
    ds.append({
        "id": f"{episode_id}/retrieve", "action": "retrieve", "component": "H4_Quarantine",
        "interaction_frames": {"source_frame": "quarantine_nest"},
        "bindings": {"object_id": sample_id, "source_component_id": "H4", "source_frame": "quarantine_nest",
                     "target_frame": "L10/transfer_station",
                     "identity_binding": "H4 containment chain (sample_id bound at quarantine, locked until the "
                                         "authorised release); H4 has no reader: re-read by L10 at incubation",
                     "release_authorization": review["authorization"]},
        "monitors": [
            mon("plate_identity", chain_ok and quarantined_id == sample_id,
                f"containment chain intact: {sample_id} quarantined at t={t_q:.1f} s, no release before the "
                "authorised one", {"sample_id": quarantined_id, "quarantined_t": t_q}),
            mon("grasp_confirmed", grasp.get("lifted") and grasp.get("contact"), "R01 jaws closed on the plate and "
                "lifted it from the H4 nest", grasp),
            mon("source_release_state", released and stowed and not r_no_token.accepted,
                "release needed token AND key (refused without the token); H4 presented, then stowed after the pick",
                {"refused_without_token": r_no_token.reason, "release": r.accepted, "H4_mode": h4.mode,
                 "events": [e["event"] for e in events_since(h4, t0)]}),
            mon("time_outside_environment", exposure is not None and exposure <= PROTOCOL["protocol_window_s"],
                f"{exposure:.1f} s outside L10 since its removal for quarantine (protocol window "
                f"{PROTOCOL['protocol_window_s']:.0f} s)" if exposure is not None else "removal time unknown",
                round(exposure or -1, 2)),
        ],
        "command_completed": bool(released and grasp.get("lifted")), "t_start": round(t0, 3), "t_end": round(rig.t, 3),
        "semantic_target": "CultureSDT.release_from_quarantine",
        "semantic_effect": f"{sample_id} released from H4 by authorised review ({review['authorization']})",
        "failure_route": "human_escalation", "failure_target": "human",
        "evidence": {"identity_observation": f"H4 containment record: {quarantined_id}",
                     "timestamps": {"key_release": round(t0, 3), "released": round(rig.t, 3)}, "review": review,
                     "L10_environment_wait": env_wait},
        "device_events": events_since(h4, t0),
    })
    if not grasp.get("lifted"):
        return ds, esc, {"aborted": "retrieve from H4"}

    # ---- transport to L10: open L10 just in time (the gate opens only once the plate is in the gripper)
    t0 = rig.t
    l10.present_for_load()
    ok_transit, transit_info = go_above("L10", held=True, phase="transit")
    wait(lambda: l10.mode == "PRESENTED_EMPTY", 30, "L10 present for load")
    still("quarantine_release_2_return_to_L10", "l10")
    p_l10, yaw_l10 = at("L10")
    rig.phase = "place"
    placed, info = rig.place(p_l10, yaw_l10, contacts_phase="insert")
    rig.phase = None
    rig.step(int(0.5 * HZ))
    seated = bool(l10.seated)
    transit_bad, transit_near = robot_contacts("transit", held)
    slip = rig.held["dropped"]
    ds.append({
        "id": f"{episode_id}/transport", "action": "transport", "component": "R01_FR3_PlateArm",
        "interaction_frames": {"grasp_frame": "plate_grasp_frame", "tool_frame": "tool0"},
        "bindings": {"object_id": sample_id, "source_frame": "H4/transfer_nest", "target_frame": "L10/transfer_station",
                     "route": f"planned joint-space transit between the {APPROACH:.2f} m approach poses (twin/r01_planner.py)",
                     "contamination_state": "not modelled (assumption: lidded plate, closed route)"},
        "monitors": [
            mon("route_clear", ok_transit and not transit_bad, "contact report during transit" + (
                ": no contacts besides the fingers on the plate" if not transit_bad else ": unexpected contacts"),
                {"contacts": transit_bad, "proximity_within_contact_offset": transit_near}),
            mon("object_identity", True, f"carrying {sample_id} (H4 containment chain)", sample_id),
            mon("object_pose_or_grasp", slip is None and placed and seated, "no slip > 5 mm; seated on the L10 nest"
                if slip is None else f"plate slipped: {slip}", {"slip": slip, "seated": seated, **{k: info.get(k) for k in (
                    "release_height_mm", "landing_speed_mm_s", "impedance_lateral_max_mm")}}),
            mon("contamination_compatibility", True, "ASSUMPTION: no contamination model in the twin; lidded plate "
                "on a closed route assumed (epistemic_status: assumption)", "assumption"),
            mon("elapsed_time", rig.t - t0 <= PROTOCOL["protocol_window_s"], f"transport took {rig.t - t0:.1f} s",
                round(rig.t - t0, 2)),
        ],
        "command_completed": bool(placed and seated), "t_start": round(t0, 3), "t_end": round(rig.t, 3),
        "semantic_target": "CultureSDT.custody_event", "semantic_effect": f"{sample_id} moved H4 -> L10",
        "failure_route": "H4_quarantine", "failure_target": "H4",
        "evidence": {"route": {"path": "H4/transfer_nest -> L10/transfer_station", "plan": transit_info},
                     "timestamps": {"start": round(t0, 3), "placed": round(rig.t, 3)}, "place": info},
    })
    rig.contact_log.clear()

    # ---- incubate in L10 (identity re-read at L10's reader)
    t0 = rig.t
    slot = review["return_slot"]
    r = l10.incubate(sample_id, slot)
    done = r.accepted and wait(lambda: l10.mode in ("READY", "FAULT"), 120, "L10 incubate")
    read = events_since(l10, t0, "identity_read")
    seen = read[-1]["observed"] if read else None
    incubated = done and l10.mode == "READY" and l10.inventory[slot] == sample_id and l10.slot_occupied[slot]
    rig.step(int(2.0 * HZ))
    env = {k: round(v, 3) for k, v in l10.env.items()}
    lo_hi = l10.envelope
    alarms = [e for e in events_since(l10, t_ep, "alarm_raised")]
    ds.append({
        "id": f"{episode_id}/incubate", "action": "incubate", "component": "L10_Incubator",
        "interaction_frames": {"storage_slot_or_frame": "cassette_slots[]", "transfer_frame": "transfer_station"},
        "bindings": {"plate_id": sample_id, "incubator_component_id": "L10", "storage_slot_or_frame": f"slot_{slot:02d}",
                     "intended_duration": PROTOCOL["intended_incubation"],
                     "environment_profile_id": "L10_setpoint_T37_CO2_5_RH90 (illustrative engineering setpoints, D016)"},
        "monitors": [
            mon("plate_identity", seen == sample_id, f"L10 barcode reader: expected {sample_id}, read {seen!r}",
                {"expected": sample_id, "observed": seen}),
            mon("seating_confirmed", seated and incubated, "seated on the L10 nest; slot ray occupied after the store",
                {"nest_seated": seated, "slot": slot, "slot_occupied": bool(l10.slot_occupied[slot])}),
            mon("temperature_state", lo_hi["T"][0] <= env["T"] <= lo_hi["T"][1], f"T {env['T']} C, envelope {lo_hi['T']}",
                env["T"]),
            mon("co2_state", lo_hi["CO2"][0] <= env["CO2"] <= lo_hi["CO2"][1], f"CO2 {env['CO2']} %, envelope "
                f"{lo_hi['CO2']}", env["CO2"]),
            mon("humidity_state", lo_hi["RH"][0] <= env["RH"] <= lo_hi["RH"][1], f"RH {env['RH']} %, envelope "
                f"{lo_hi['RH']}", env["RH"]),
            mon("excursion_alarm_state", not alarms and l10.environment_valid, "no environment alarm during the "
                "episode" if not alarms else f"alarms: {alarms}", sorted(l10.alarms)),
        ],
        "command_completed": bool(incubated), "t_start": round(t0, 3), "t_end": round(rig.t, 3),
        "semantic_target": "CultureSDT.incubation_event", "semantic_effect": f"{sample_id} incubated in L10 slot {slot}",
        "failure_route": "H4_quarantine", "failure_target": "H4",
        "evidence": {"slot_or_frame": f"slot_{slot:02d}", "environment_history": l10.environment_history(sample_id),
                     "timestamps": {"start": round(t0, 3), "incubated": round(rig.t, 3)},
                     "time_outside_controlled_environment_s": round(exposure, 2) if exposure is not None else None},
        "device_events": events_since(l10, t0),
    })
    still("quarantine_release_3_incubated", "elevated")
    esc.append({"kind": "quarantine_review", "sample_id": sample_id, "resolved": True, **review})
    if any(v for v in l10.unaccounted):
        esc.append({"kind": "plate_unaccounted", "plate_id": next(iter(l10.unaccounted)), "resolved": False,
                    **l10.unaccounted[next(iter(l10.unaccounted))]})
    outcome = {"route": "release_to_L10", "incubated": incubated, "L10_inventory": {k: v for k, v in enumerate(l10.inventory) if v},
               "H4": h4.mode, "H4_empty": not h4.plate_on_nest and not h4.occupied, "duration_s": round(rig.t - t_ep, 1)}
    return ds, esc, outcome

# ------------------------------------------------------------------------------ imaging episode (R01 + R02 + L17)
def r02_down(yaw_deg=0.0):
    c, sn = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    return np.array([[c, sn, 0], [sn, -c, 0], [0, 0, -1]])


def plate_pose(path):
    from isaacsim.core.experimental.prims import RigidPrim
    p, q = RigidPrim(path).get_world_poses()
    p, q = p.numpy()[0].astype(float), q.numpy()[0].astype(float)
    return p, math.degrees(2 * math.asin(min(1.0, math.hypot(q[1], q[2]))))


def r02_pick(nest, side, held):
    """T01 top-down pick from a nest (plate long axis along X, jaws along Y); returns evidence."""
    p, _ = at(nest)
    grasp = p + [0, 0, 0.006]
    ok_pos, why = r02.position_for_station(nest, grasp + [0, 0, 0.15], r02_down(), side=side)
    ok_in = r02rig.move_to(grasp, r02_down(), speed=0.05)[0]
    fa, fb = r02rig.jaws(True)
    r02rig.holding = True
    z0 = plate_pose(held)[0][2]
    ok_up = r02rig.move_to(grasp + [0, 0, 0.15], r02_down(), speed=0.08)[0]
    lifted = (plate_pose(held)[0][2] - z0) * 1e3
    return {"positioned": ok_pos, "reason": why, "converged": bool(ok_in and ok_up), "lifted_mm": round(lifted, 1),
            "finger_travel_mm": [round(fa, 2), round(fb, 2)], "lifted": lifted > 100}


def r02_place(nest, side, held):
    p, _ = at(nest)
    target = p + [0, 0, 0.006 + 0.002]
    ok_pos, why = r02.position_for_station(nest, target + [0, 0, 0.15], r02_down(), side=side)
    ok_in = r02rig.move_to(target, r02_down(), speed=0.03)[0]
    r02rig.holding = False
    r02rig.jaws(False)
    ok_up = r02rig.move_to(target + [0, 0, 0.15], r02_down(), speed=0.05)[0]
    r02rig.step(int(0.5 * HZ))
    pos, tilt = plate_pose(held)
    off = (pos - p) * 1e3
    return {"positioned": ok_pos, "reason": why, "converged": bool(ok_in and ok_up),
            "offset_mm": np.round(off, 2).tolist(), "tilt_deg": round(tilt, 3)}


def r02_park():
    """Carry posture mid-rail, clear of the handover site and of R01."""
    q = r02rig.q()
    c = r02rig.carry(None, side=-1.0)
    return r02rig.move_joints(np.r_[q[0], c[1:]]) and r02rig.move_joints(np.r_[1.30, c[1:]])


def r02_transport(episode_id, tag, plate_id, src, dst, t0, pick, place, seated, custody):
    ok_motion = pick["positioned"] and pick["converged"] and place["positioned"] and place["converged"]
    return {
        "id": f"{episode_id}/{tag}", "action": "transport", "component": "R02_RailMounted_UR5e",
        "interaction_frames": {"tool_frame": "tool0", "approach_frames": "station_approach_frames"},
        "bindings": {"object_id": plate_id, "source_frame": src, "target_frame": dst,
                     "route": "rail transit in R02's carry posture between station approach poses (twin/r02_rig.py)",
                     "contamination_state": "not modelled (assumption: lidded plate, closed route)", "tool": "T01"},
        "monitors": [
            mon("route_clear", ok_motion, "every positioning and Cartesian move converged; clearance by the carry "
                "posture design (the R02 twin has no contact sensing: epistemic_status posture_design)",
                {"pick": pick, "place": place}),
            mon("object_identity", True, custody, plate_id),
            mon("object_pose_or_grasp", pick["lifted"] and seated, f"lifted {pick['lifted_mm']} mm in T01; seated at "
                f"{dst} (seat sensors), offset {place['offset_mm']} mm, tilt {place['tilt_deg']} deg",
                {"lifted_mm": pick["lifted_mm"], "seated": seated, "offset_mm": place["offset_mm"]}),
            mon("contamination_compatibility", True, "ASSUMPTION: no contamination model in the twin; T01 is a clean "
                "tool (contamination class checked by the tool changer); lidded plate assumed", "assumption"),
            mon("elapsed_time", rig.t - t0 <= IMAGING["request"]["imaging_window_s"],
                f"transport took {rig.t - t0:.1f} s", round(rig.t - t0, 2)),
        ],
        "command_completed": bool(ok_motion and seated), "t_start": round(t0, 3), "t_end": round(rig.t, 3),
        "semantic_target": "CultureSDT.custody_event", "semantic_effect": f"{plate_id} moved {src} -> {dst} by R02",
        "failure_route": "H4_quarantine", "failure_target": "H4",
        "evidence": {"route": {"path": f"{src} -> {dst}", "rail_m": round(float(r02rig.q()[0]), 3)},
                     "timestamps": {"start": round(t0, 3), "placed": round(rig.t, 3)}},
        "device_events": [e for e in r02.events + tcm.events if e["t"] >= t0 - 1e-6],
    }


def r01_transport(episode_id, tag, plate_id, src, dst, t0, ok_transit, transit_info, placed, info, seated, held):
    transit_bad, transit_near = robot_contacts("transit", held)
    slip = rig.held["dropped"]
    d = {
        "id": f"{episode_id}/{tag}", "action": "transport", "component": "R01_FR3_PlateArm",
        "interaction_frames": {"grasp_frame": "plate_grasp_frame", "tool_frame": "tool0"},
        "bindings": {"object_id": plate_id, "source_frame": src, "target_frame": dst,
                     "route": f"planned joint-space transit between the {APPROACH:.2f} m approach poses (twin/r01_planner.py)",
                     "contamination_state": "not modelled (assumption: lidded plate, closed route)"},
        "monitors": [
            mon("route_clear", ok_transit and not transit_bad, "contact report during transit" + (
                ": no contacts besides the fingers on the plate" if not transit_bad else ": unexpected contacts"),
                {"contacts": transit_bad, "proximity_within_contact_offset": transit_near}),
            mon("object_identity", True, f"carrying {plate_id} (custody since the last barcode read)", plate_id),
            mon("object_pose_or_grasp", slip is None and placed and seated, f"no slip > 5 mm; seated at {dst}"
                if slip is None else f"plate slipped: {slip}", {"slip": slip, "seated": seated, **{k: info.get(k) for k in (
                    "release_height_mm", "landing_speed_mm_s", "impedance_lateral_max_mm")}}),
            mon("contamination_compatibility", True, "ASSUMPTION: no contamination model in the twin; lidded plate "
                "on a closed route assumed (epistemic_status: assumption)", "assumption"),
            mon("elapsed_time", rig.t - t0 <= IMAGING["request"]["imaging_window_s"], f"transport took {rig.t - t0:.1f} s",
                round(rig.t - t0, 2)),
        ],
        "command_completed": bool(placed and seated), "t_start": round(t0, 3), "t_end": round(rig.t, 3),
        "semantic_target": "CultureSDT.custody_event", "semantic_effect": f"{plate_id} moved {src} -> {dst} by R01",
        "failure_route": "H4_quarantine", "failure_target": "H4",
        "evidence": {"route": {"path": f"{src} -> {dst}", "plan": transit_info},
                     "timestamps": {"start": round(t0, 3), "placed": round(rig.t, 3)}, "place": info},
    }
    rig.contact_log.clear()
    return d


def run_imaging_episode(episode_id, plate_id, wells, magnification, exposure_ms, measurement_binding_id, return_slot,
                        request):
    print(f"[episode] === {episode_id}: image {plate_id} {wells} {magnification} on L17 (R01 -> HN -> R02 -> L17)")
    t_ep, ds, esc = rig.t, [], []
    if plate_id not in l09.inventory:
        return ds, esc, {"aborted": f"{plate_id} is not in L09 (run the nominal episode first)"}
    held = by_barcode[plate_id]
    window = request["imaging_window_s"]

    # ---- retrieve from L09 (barcode read at L09's transfer nest)
    t0 = rig.t
    slot = l09.inventory.index(plate_id)
    r = l09.retrieve(plate_id)
    released = r.accepted and wait(lambda: l09.mode in ("PRESENTED_LOADED", "FAULT"), 120, "L09 retrieve")
    reads = events_since(l09, t0, "identity_read")
    observed = reads[-1]["observed"] if reads else None
    identity_ok = released and l09.mode == "PRESENTED_LOADED" and observed == plate_id
    if identity_ok:
        go_above("L09", held=False)
        rig.phase = "pick"
        grasp = rig.pick(*at("L09"), "pick_L09", plate=held)
        rig.phase = None
    else:
        grasp = {"lifted": False}
    grasp["robot_contacts"], grasp["robot_proximity"] = robot_contacts("pick", held)
    l09.stow()
    stowed = wait(lambda: l09.mode == "READY", 30, "L09 stow")
    outside = l10.environment_history(plate_id).get("time_outside_controlled_environment_s")
    ds.append({
        "id": f"{episode_id}/retrieve", "action": "retrieve", "component": "L09_PlateHotel",
        "interaction_frames": {"source_frame": "transfer_nest"},
        "bindings": {"object_id": plate_id, "source_component_id": "L09", "source_frame": "transfer_nest",
                     "target_frame": "L17/plate_load_frame (via the R01/R02 handover nest)",
                     "identity_binding": "barcode read at the L09 stowed transfer nest (labware:barcode)",
                     "source_slot": slot},
        "monitors": [
            mon("plate_identity", identity_ok, f"L09 barcode reader: expected {plate_id}, read {observed!r}",
                {"expected": plate_id, "observed": observed}),
            mon("grasp_confirmed", grasp.get("lifted") and grasp.get("contact"), "R01 jaws closed on the plate and "
                "lifted it", grasp),
            mon("source_release_state", released and stowed, "L09 presented the plate; gate closed after the pick",
                {"L09_mode": l09.mode}),
            mon("time_outside_environment", outside is not None and outside <= window,
                f"{outside} s outside a controlled environment since its L10 release (ambient storage accepted by "
                f"the request; imaging window {window:.0f} s)", outside),
        ],
        "command_completed": bool(released and grasp.get("lifted")), "t_start": round(t0, 3), "t_end": round(rig.t, 3),
        "semantic_target": "CultureSDT.custody_event", "semantic_effect": f"{plate_id} left L09 for imaging",
        "failure_route": "H4_quarantine", "failure_target": "H4",
        "evidence": {"identity_observation": observed, "timestamps": {"start": round(t0, 3), "picked": round(rig.t, 3)}},
        "device_events": events_since(l09, t0),
    })
    if not grasp.get("lifted"):
        return ds, esc, {"aborted": "retrieve from L09"}

    # ---- R01: L09 -> handover nest, then R01 parks above L09 (clear of R02's approach)
    t0 = rig.t
    ok_transit, transit_info = go_above("HN", held=True, phase="transit")
    rig.phase = "place"
    placed, info = rig.place(*at("HN"), contacts_phase="insert")
    rig.phase = None
    rig.step(int(0.5 * HZ))
    seated = bool(hn.seated)
    ds.append(r01_transport(episode_id, "transport_R01", plate_id, "L09/transfer_nest", "HN/handover_frame", t0,
                            ok_transit, transit_info, placed, info, seated, held))
    go_above("L09", held=False)
    still("imaging_1_handover_nest", "hn")

    # ---- R02 (T01): handover nest -> L17; L17 presents its stage while R02 travels
    t0 = rig.t
    if not r02.rail_homed:
        r02.home_rail()
    tool_ok, why = (True, "") if (r02rig.tool or {}).get("id") == "T01" else tcm.change_tool("T01")
    if not tool_ok:
        return ds, esc, {"aborted": f"T01 tool change: {why}"}
    pick = r02_pick("HN", -1.0, held)
    l17.present_for_load()
    place = r02_place("L17", 1.0, held)
    wait(lambda: l17.mode != "BUSY", 30, "L17 present for load")
    seated = bool(l17.seated)
    ds.append(r02_transport(episode_id, "transport_R02", plate_id, "HN/handover_frame", "L17/plate_load_frame", t0,
                            pick, place, seated, "custody: placed in HN by R01 after the L09 barcode read; L17 re-reads "
                                                  "the barcode at load"))
    still("imaging_2_R02_loaded_L17", "l17")

    # ---- L17: load (identity read at stage home) and image the region
    t0 = rig.t
    r = l17.load_plate(plate_id)
    loaded = r.accepted and wait(lambda: l17.mode != "BUSY", 30, "L17 load_plate") and l17.mode == "LOADED"
    n0 = len(l17.acquisitions)
    if loaded:
        r = l17.image_plate_region(plate_id, wells, exposure_ms, magnification, "autofocus", 1.0, measurement_binding_id)
        wait(lambda: l17.mode != "BUSY", 300, f"L17 image {wells}")
    # contract recovery for out_of_focus: retain the rejected image, refocus from scratch, reacquire (once per well)
    for acq in list(l17.acquisitions[n0:]):
        failed = [m["name"] for m in acq["monitors"] if not m["passed"]]
        if loaded and failed == ["focus_quality"]:
            print(f"[episode]   {acq['well_id']}: focus_quality failed (score {acq['focus_score']}); refocus + reacquire")
            l17.focus_memory.pop((plate_id, magnification), None)
            r = l17.image_well(plate_id, acq["well_id"], exposure_ms, magnification, "autofocus", 1.0, measurement_binding_id)
            wait(lambda: l17.mode != "BUSY", 120, f"L17 reacquire {acq['well_id']}")
    seen = set()
    for i, acq in enumerate(l17.acquisitions[n0:]):
        tag = f"image_{acq['well_id']}" + ("_reacquired" if acq["well_id"] in seen else "")
        seen.add(acq["well_id"])
        ds.append({"id": f"{episode_id}/{tag}", "action": "image", "component": "L17_BrightFieldImager",
                   "acquisition": acq, "truth_for_audit": l17.truth[n0 + i],
                   "t_start": round(t0, 3), "t_end": acq["t"], "command_completed": acq["command_completed"]})
    if not loaded:
        esc.append({"kind": "L17_load_failed", "fault": l17.fault, "identity": l17.identity_fault})
        return ds, esc, {"aborted": f"L17 load: {l17.mode} {l17.fault}"}

    # ---- unload: L17 presents, R02 takes the plate back to the handover nest, L17 stows, R02 parks
    t0 = rig.t
    l17.present_for_unload()
    wait(lambda: l17.mode != "BUSY", 30, "L17 present for unload")
    pick = r02_pick("L17", 1.0, held)
    l17.stow()
    place = r02_place("HN", -1.0, held)
    wait(lambda: l17.mode == "READY", 20, "L17 stow")
    seated = bool(hn.seated)
    ds.append(r02_transport(episode_id, "transport_R02_back", plate_id, "L17/plate_load_frame", "HN/handover_frame", t0,
                            pick, place, seated, "custody: identity read by L17 at load; held in L17 until unload"))
    tool_back = tcm.store_tool()
    parked = r02_park()

    # ---- R01: handover nest -> L09, store (identity re-read by L09)
    t0 = rig.t
    go_above("HN", held=False)
    rig.phase = "pick"
    grasp = rig.pick(*at("HN"), "pick_HN", plate=held)
    rig.phase = None
    l09.present_for_load()
    ok_transit, transit_info = go_above("L09", held=True, phase="transit")
    wait(lambda: l09.mode == "PRESENTED_EMPTY", 30, "L09 present for load")
    rig.phase = "place"
    placed, info = rig.place(*at("L09"), contacts_phase="insert")
    rig.phase = None
    rig.step(int(0.5 * HZ))
    seated_l09 = bool(l09.seated)
    ds.append(r01_transport(episode_id, "transport_R01_back", plate_id, "HN/handover_frame", "L09/transfer_nest", t0,
                            ok_transit and grasp.get("lifted"), transit_info, placed, info, seated_l09, held))
    t0 = rig.t
    r = l09.store(plate_id, return_slot)
    done = r.accepted and wait(lambda: l09.mode in ("READY", "FAULT"), 120, "L09 store")
    read = events_since(l09, t0, "identity_read")
    seen = read[-1]["observed"] if read else None
    stored = done and l09.mode == "READY" and l09.inventory[return_slot] == plate_id
    outside = l10.environment_history(plate_id).get("time_outside_controlled_environment_s")
    ds.append({
        "id": f"{episode_id}/store", "action": "store", "component": "L09_PlateHotel",
        "interaction_frames": {"storage_slot_or_frame": "slot_frames[]", "transfer_frame": "transfer_nest"},
        "bindings": {"object_id": plate_id, "storage_component_id": "L09", "storage_slot_or_frame": f"slot_{return_slot:02d}",
                     "environmental_state_binding": PROTOCOL["storage_environment"]},
        "monitors": [
            mon("identity_preserved", seen == plate_id, f"L09 barcode reader: expected {plate_id}, read {seen!r}",
                {"expected": plate_id, "observed": seen}),
            mon("slot_available", r.accepted, f"slot {return_slot} empty (ray + inventory) and accepted",
                {"slot": return_slot, "accepted": r.accepted, "reason": r.reason}),
            mon("seating_confirmed", seated_l09 and stored, "seated on the L09 nest before the store; slot ray occupied "
                "after", {"nest_seated": seated_l09, "slot_occupied_after": bool(l09.slot_occupied[return_slot])}),
            mon("environment_accepted", outside is not None and outside <= window,
                f"ambient storage accepted by the request; {outside} s outside a controlled environment (imaging "
                f"window {window:.0f} s)", {"time_outside_s": outside, "binding": PROTOCOL["storage_environment"]}),
        ],
        "command_completed": bool(stored), "t_start": round(t0, 3), "t_end": round(rig.t, 3),
        "semantic_target": "CultureSDT.custody_event", "semantic_effect": f"{plate_id} returned to L09 slot {return_slot}",
        "failure_route": "H4_quarantine", "failure_target": "H4",
        "evidence": {"timestamps": {"start": round(t0, 3), "stored": round(rig.t, 3)},
                     "environment_snapshot": {"L10_environment_history": l10.environment_history(plate_id),
                                              "L09": "ambient (unconditioned)"}},
        "device_events": events_since(l09, t0),
    })
    still("imaging_3_returned_to_L09", "cluster")
    acqs = l17.acquisitions[n0:]
    outcome = {"route": "imaging", "images": len(acqs), "images_valid": sum(a["valid"] for a in acqs),
               "reacquired": [a["well_id"] for a in acqs if not a["valid"]],
               "autofocus_runs": [r for r in l17.autofocus_runs if r["t"] >= t0],
               "wells": [a["well_id"] for a in acqs], "stored": stored, "L17": l17.mode, "T01_stored": tool_back[0],
               "R02_parked": bool(parked), "imaging_history": l17.history.get(plate_id),
               "truth_defocus_um": [t["defocus_um"] for t in l17.truth[n0:]],
               "duration_s": round(rig.t - t_ep, 1)}
    return ds, esc, outcome

# ------------------------------------------------------------------------------ full-cell episode (all stations)
FULL = dict(plate_id="Plate_P30", incubate_slot=8, dose=dict(well="B05", reagent_pos=1,
            reagent_id="abstract_challenge_reagent", reagent_lot="SIM-LOT-A", volume_uL=10.0, dispense_height_mm=1.2,
            dispense_rate_uL_s=2.0, intended_effect="abstract_challenge"), image_wells=["B05", "B06"],
            request={"window_s": 3600.0, "note": "demo request parameters for the twin episode (D016)"})


def r02_clear(rail=1.8):
    """R02 in the carry posture at a rail position clear of L12's deck and the handover site."""
    c = r02rig.carry(None, side=1.0)
    return r02rig.move_joints(np.r_[r02rig.q()[0], c[1:]]) and r02rig.move_joints(np.r_[rail, c[1:]])


def ensure_t01():
    if not r02.rail_homed:
        r02.home_rail()
    if (r02rig.tool or {}).get("id") == "T01":
        return True, ""
    return tcm.change_tool("T01")


def t01_tool_check():
    """L21 light-barrier sweeps with T01 (jaws open): z over beam A, y across beam A, x across beam B."""
    D = l21.frames["tool_calibration_frame"]
    tip, half, R = 0.008, 0.05024, r02_down()
    l21.begin_tool_check("T01", lambda: r02rig.tcp()[0], tip)

    def at_(x, y, z, phase=None, speed=0.02):
        l21.mark_phase(phase)
        return r02rig.move_to(np.array([x, y, z]), R, speed=speed, tol_mm=0.2, timeout=8.0)[0]

    hi = D[2] + tip + 0.030
    r02.position_for_station("L21_datum", np.array([D[0] + 0.040, D[1] + half, hi + 0.10]), R, side=1.0)
    for args_ in ((D[0] + 0.040, D[1] + half, D[2] + tip + 0.010), (D[0] + 0.040, D[1] + half, D[2] + tip - 0.006, "z", 0.003),
                  (D[0] + 0.040, D[1] + half, hi), (D[0] + 0.040, D[1] - 0.075, hi),
                  (D[0] + 0.040, D[1] - 0.075, D[2] + tip - 0.005), (D[0] + 0.040, D[1] + 0.075, D[2] + tip - 0.005, "y", 0.004),
                  (D[0] + 0.040, D[1] + 0.075, hi), (D[0] - 0.050, D[1] + 0.020, hi),
                  (D[0] - 0.050, D[1] + 0.020, D[2] + tip - 0.005), (D[0] + 0.050, D[1] + 0.020, D[2] + tip - 0.005, "x", 0.004),
                  (D[0] + 0.050, D[1] + 0.020, hi + 0.10)):
        at_(*args_)
        l21.mark_phase(None)
    return l21.finish_tool_check()


def amr_transport_designator(episode_id, tag, plate_id, t0, t1, route, dock_res, inbound=True):
    tr = [x for x in amr.trace if t0 <= x[0] <= t1]
    return {
        "id": f"{episode_id}/{tag}", "action": "transport", "component": "R03_AMR_H2_Dock",
        "interaction_frames": {"source_frame": "dock_approach", "target_frame": "handover_carrier_frame"},
        "bindings": {"object_id": plate_id, "source_frame": "site entry (outside Cell 01)" if inbound else "H2",
                     "target_frame": "H2/handover_carrier_frame" if inbound else "site exit",
                     "route": "logistics lane -> dock_approach -> H2" if inbound else "H2 -> lane -> site exit",
                     "contamination_state": "clean_sample_only (carrier class clean)"},
        "monitors": [
            mon("route_clear", all(x[7] for x in tr), "localization healthy along the route", {"samples": len(tr)}),
            mon("object_identity", plate_id in amr.inventory or not inbound,
                "carrier id bound at loading and carried in the closed cabinet (transport history)", list(amr.inventory)),
            mon("object_pose_or_grasp", all(x[5] for x in tr) if inbound else True,
                "carrier presence sensors: present for the whole transport; docked handover pose" if inbound
                else "cabinet empty", dock_res),
            mon("contamination_compatibility", amr.contamination_class == "clean_sample_only",
                "clean carrier on the clean-sample AMR; cabinet closed in transit", "clean"),
            mon("elapsed_time", t1 - t0 <= FULL["request"]["window_s"], f"transport took {t1 - t0:.1f} s",
                round(t1 - t0, 2)),
        ],
        "command_completed": bool(dock_res.get("ok", True)), "t_start": round(t0, 3), "t_end": round(t1, 3),
        "semantic_target": "CultureSDT.custody_event",
        "semantic_effect": f"{plate_id} delivered to H2 by R03" if inbound else "R03 left the cell",
        "failure_route": "human_escalation", "failure_target": "human",
        "evidence": {"route": route, "timestamps": {"start": round(t0, 3), "end": round(t1, 3)}, "dock_result": dock_res},
    }


def r01_to_l10_incubate(episode_id, tag, plate_id, src, slot, held):
    """R01 carries the plate from NEST[src] to L10 (gate opened just in time) and L10 incubates it (barcode re-read)."""
    out = []
    t0 = rig.t
    wait(l10_ready_for_transfer, 600, "L10 environment ready for a transfer")
    l10.present_for_load()
    ok_transit, transit_info = go_above("L10", held=True, phase="transit")
    wait(lambda: l10.mode == "PRESENTED_EMPTY", 30, "L10 present for load")
    rig.phase = "place"
    placed, info = rig.place(*at("L10"), contacts_phase="insert")
    rig.phase = None
    rig.step(int(0.5 * HZ))
    seated = bool(l10.seated)
    out.append(r01_transport(episode_id, f"transport_R01_{tag}", plate_id, src, "L10/transfer_station", t0, ok_transit,
                             transit_info, placed, info, seated, held))
    t0 = rig.t
    r = l10.incubate(plate_id, slot)
    done = r.accepted and wait(lambda: l10.mode in ("READY", "FAULT"), 120, "L10 incubate")
    read = events_since(l10, t0, "identity_read")
    seen = read[-1]["observed"] if read else None
    incubated = done and l10.mode == "READY" and l10.inventory[slot] == plate_id and l10.slot_occupied[slot]
    env = {k: round(v, 3) for k, v in l10.env.items()}
    lo_hi = l10.envelope
    out.append({
        "id": f"{episode_id}/incubate_{tag}", "action": "incubate", "component": "L10_Incubator",
        "interaction_frames": {"storage_slot_or_frame": "cassette_slots[]", "transfer_frame": "transfer_station"},
        "bindings": {"plate_id": plate_id, "incubator_component_id": "L10", "storage_slot_or_frame": f"slot_{slot:02d}",
                     "intended_duration": PROTOCOL["intended_incubation"],
                     "environment_profile_id": "L10_setpoint_T37_CO2_5_RH90 (illustrative engineering setpoints, D016)"},
        "monitors": [
            mon("plate_identity", seen == plate_id, f"L10 barcode reader: expected {plate_id}, read {seen!r}",
                {"expected": plate_id, "observed": seen}),
            mon("seating_confirmed", seated and incubated, "seated on the L10 nest; slot ray occupied after the store",
                {"nest_seated": seated, "slot": slot}),
            mon("temperature_state", lo_hi["T"][0] <= env["T"] <= lo_hi["T"][1], f"T {env['T']} C", env["T"]),
            mon("co2_state", lo_hi["CO2"][0] <= env["CO2"] <= lo_hi["CO2"][1], f"CO2 {env['CO2']} %", env["CO2"]),
            mon("humidity_state", lo_hi["RH"][0] <= env["RH"] <= lo_hi["RH"][1], f"RH {env['RH']} %", env["RH"]),
            mon("excursion_alarm_state", l10.environment_valid, "no environment alarm at incubation", sorted(l10.alarms)),
        ],
        "command_completed": bool(incubated), "t_start": round(t0, 3), "t_end": round(rig.t, 3),
        "semantic_target": "CultureSDT.incubation_event", "semantic_effect": f"{plate_id} incubated in L10 slot {slot}",
        "failure_route": "H4_quarantine", "failure_target": "H4",
        "evidence": {"slot_or_frame": f"slot_{slot:02d}", "environment_history": l10.environment_history(plate_id),
                     "timestamps": {"start": round(t0, 3), "incubated": round(rig.t, 3)}},
        "device_events": events_since(l10, t0),
    })
    return out, incubated


def run_full_cell_episode(episode_id, plate_id, incubate_slot, dose, image_wells, request):
    print(f"[episode] === {episode_id}: start-of-day QC, AMR intake of {plate_id}, incubate, dose, image, incubate")
    t_ep, ds, esc = rig.t, [], []
    held = by_barcode[plate_id]

    # ---- A. start-of-day QC: T01 tool frame (L21 light barrier), then L17 against the reference plate
    ok, why = ensure_t01()
    if not ok:
        return ds, esc, {"aborted": f"T01: {why}"}
    rec = t01_tool_check()
    ds.append(qc_designator(rec, episode_id, tool_frame_ok=rec["verdict"] == "pass"))
    if rec["verdict"] != "pass" and rec["result"].get("ok"):
        r02rig.tool["tcp"] += rec["result"]["error_mm"][2] * 1e-3      # apply L21's correction to the tool record
        rec = t01_tool_check()
        ds.append(qc_designator(rec, episode_id, tool_frame_ok=rec["verdict"] == "pass"))
    still("full_cell_1_tool_frame_check", "l21")
    l17.present_for_load()
    r02_pick("L21ref", 1.0, REF_PATH)
    r02_place("L17", 1.0, REF_PATH)
    wait(lambda: l17.mode != "BUSY", 30, "L17 present")
    l17.load_plate(REF_ID)
    wait(lambda: l17.mode != "BUSY", 30, "L17 load reference")
    r = l21.validate_imager(l17, REF_ID)
    if r.accepted:
        wait(lambda: l21.mode != "BUSY", 900, "L21 validate_imager")
    qrec = l21.qc_records[-1]
    ds.append(qc_designator(qrec, episode_id, tool_frame_ok=l21.tool_frame_valid("T01")))
    l17.present_for_unload()
    wait(lambda: l17.mode != "BUSY", 30, "L17 present for unload")
    r02_pick("L17", 1.0, REF_PATH)
    l17.stow()
    r02_place("L21ref", 1.0, REF_PATH)
    r02_clear()

    # ---- B. AMR intake: navigate in, dock, open; R01 takes the carrier to L10
    t0 = rig.t
    amr.load_carrier(plate_id)
    if LAB:   # from the storage room: door open, back out of S1, door closed, lane legs, portal
        store_door.open()
        wait(lambda: store_door.state() == "open", 15, "ST01 storage door open")
        amr.navigate(AMR_STORE_OUT, reverse=True)
        wait(lambda: not amr.busy(), 120, "R03 leaves the storage dock S1")
        store_door.close()
        for i, leg in enumerate(AMR_LEGS):
            amr.navigate(leg)
            wait(lambda: not amr.busy(), 180, ["R03 to the AMR lane", "R03 along the lane to Cell 01",
                                               "R03 through the Cell 01 portal to dock_approach"][i])
    else:
        amr.navigate(AMR_IN)
        wait(lambda: not amr.busy(), 180, "R03 navigate to dock_approach")
    amr.dock(compliant=True)
    wait(lambda: not amr.busy(), 90, "R03 dock")
    dock_res = dict(getattr(amr, "last_dock", {"ok": False}))
    ds.append(amr_transport_designator(episode_id, "transport_R03_in", plate_id, t0, rig.t, AMR_IN, dock_res))
    amr.open_cabinet()
    wait(lambda: not amr.busy(), 20, "R03 open cabinet")
    still("full_cell_2_amr_docked", "amr")
    t0 = rig.t
    go_above("R03", held=False)
    rig.phase = "pick"
    grasp = rig.pick(*at("R03"), "pick_R03", plate=held)
    rig.phase = None
    grasp["robot_contacts"], grasp["robot_proximity"] = robot_contacts("pick", held)
    amr.close_cabinet()
    closed = wait(lambda: not amr.busy(), 20, "R03 close cabinet") and amr.cabinet == "closed"
    ds.append({
        "id": f"{episode_id}/retrieve_R03", "action": "retrieve", "component": "R03_AMR_H2_Dock",
        "interaction_frames": {"source_frame": "handover_carrier_frame"},
        "bindings": {"object_id": plate_id, "source_component_id": "R03/H2", "source_frame": "handover_carrier_frame",
                     "target_frame": "L10/transfer_station",
                     "identity_binding": "carrier id bound in R03's transport history; re-read by L10's reader",
                     "dock": "H2"},
        "monitors": [
            mon("plate_identity", plate_id in amr.inventory, "carrier id from R03's transport history (no reader on "
                "the AMR; L10 re-reads it at incubation)", plate_id),
            mon("grasp_confirmed", grasp.get("lifted") and grasp.get("contact"), "R01 jaws closed on the plate and "
                "lifted it from the AMR carrier nest", grasp),
            mon("source_release_state", dock_res.get("ok") and closed, "AMR docked (dock sensors) before the cabinet "
                "opened; cabinet closed after the pick", {"dock": dock_res, "cabinet": amr.cabinet}),
            mon("time_outside_environment", True, "arrived from the site store in R03's closed cabinet (no exposure "
                "model for the site leg)", None),
        ],
        "command_completed": bool(grasp.get("lifted")), "t_start": round(t0, 3), "t_end": round(rig.t, 3),
        "semantic_target": "CultureSDT.custody_event", "semantic_effect": f"{plate_id} taken over from R03 by R01",
        "failure_route": "H4_quarantine", "failure_target": "H4",
        "evidence": {"identity_observation": f"R03 transport history: {plate_id}", "timestamps": {"start": round(t0, 3)}},
        "device_events": [e for e in amr.events if e["t"] >= t0 - 1e-6],
    })
    amr.inventory.remove(plate_id)
    t_leave = rig.t
    amr.undock()
    wait(lambda: not amr.busy(), 60, "R03 undock")
    out, inc1 = r01_to_l10_incubate(episode_id, "intake", plate_id, "R03/handover_carrier_frame", incubate_slot, held)
    ds += out
    amr.navigate(AMR_OUT, reverse=True)
    wait(lambda: not amr.busy(), 180, "R03 leaves the cell")
    ds.append(amr_transport_designator(episode_id, "transport_R03_out", plate_id, t_leave, rig.t, AMR_OUT, {"ok": True},
                                       inbound=False))
    if not inc1:
        return ds, esc, {"aborted": "intake incubation"}

    # ---- C. dose on L12, image on L17, back to L10
    t0 = rig.t
    wait(l10_ready_for_transfer, 600, "L10 environment ready for a transfer")
    r = l10.release_plate(plate_id)
    released = r.accepted and wait(lambda: l10.mode in ("PRESENTED_LOADED", "FAULT"), 120, "L10 release")
    seen = (events_since(l10, t0, "identity_read") or [{}])[-1].get("observed")
    go_above("L10", held=False)
    rig.phase = "pick"
    grasp = rig.pick(*at("L10"), "pick_L10", plate=held)
    rig.phase = None
    grasp["robot_contacts"], grasp["robot_proximity"] = robot_contacts("pick", held)
    l10.stow()
    stowed = wait(lambda: l10.mode == "READY", 30, "L10 stow")
    rel = l10.released.get(plate_id) or {}
    ds.append({
        "id": f"{episode_id}/retrieve_L10", "action": "retrieve", "component": "L10_Incubator",
        "interaction_frames": {"source_frame": "transfer_station"},
        "bindings": {"object_id": plate_id, "source_component_id": "L10", "source_frame": "transfer_station",
                     "target_frame": "L12/plate_nest (via the handover nest)",
                     "identity_binding": "barcode read at the L10 stowed transfer nest", "source_slot": incubate_slot},
        "monitors": [
            mon("plate_identity", released and seen == plate_id, f"L10 barcode reader: expected {plate_id}, read {seen!r}",
                {"expected": plate_id, "observed": seen}),
            mon("grasp_confirmed", grasp.get("lifted") and grasp.get("contact"), "R01 jaws closed and lifted", grasp),
            mon("source_release_state", released and stowed, "L10 release observed; gate closed after the pick", rel),
            mon("time_outside_environment", True, f"leaves L10 at t={rig.t:.1f} s for dosing and imaging (window "
                f"{request['window_s']:.0f} s)", None),
        ],
        "command_completed": bool(released and grasp.get("lifted")), "t_start": round(t0, 3), "t_end": round(rig.t, 3),
        "semantic_target": "CultureSDT.custody_event", "semantic_effect": f"{plate_id} left L10 for dosing",
        "failure_route": "H4_quarantine", "failure_target": "H4",
        "evidence": {"identity_observation": seen, "timestamps": {"start": round(t0, 3), "picked": round(rig.t, 3)}},
        "device_events": events_since(l10, t0),
    })
    t0 = rig.t
    ok_transit, transit_info = go_above("HN", held=True, phase="transit")
    rig.phase = "place"
    placed, info = rig.place(*at("HN"), contacts_phase="insert")
    rig.phase = None
    rig.step(int(0.5 * HZ))
    ds.append(r01_transport(episode_id, "transport_R01_to_HN", plate_id, "L10/transfer_station", "HN/handover_frame",
                            t0, ok_transit, transit_info, placed, info, bool(hn.seated), held))
    go_above("L09", held=False)
    t0 = rig.t
    pick = r02_pick("HN", -1.0, held)
    place = r02_place("L12", 1.0, held)
    seated12 = bool(l12.seated)
    ds.append(r02_transport(episode_id, "transport_R02_to_L12", plate_id, "HN/handover_frame", "L12/plate_nest", t0,
                            pick, place, seated12, "custody: L10 barcode read at release, R01 -> HN -> R02"))
    r02_clear()
    t0 = rig.t
    d_ = dose
    r = l12.dose_well(plate_id, d_["well"], d_["reagent_pos"], d_["reagent_id"], d_["reagent_lot"], d_["volume_uL"],
                      d_["dispense_height_mm"], d_["dispense_rate_uL_s"], intended_effect=d_["intended_effect"])
    if r.accepted:
        wait(lambda: l12.mode != "BUSY", 240, "L12 dose_well")
    dose_rec = l12.doses[-1] if l12.doses and r.accepted else None
    if dose_rec:
        ds.append({"id": f"{episode_id}/dose_{d_['well']}", "action": "dose", "component": "L12_LiquidHandler",
                   "dose": dose_rec, "t_start": round(t0, 3), "t_end": dose_rec["t"],
                   "command_completed": dose_rec["command_completed"]})
    still("full_cell_3_dosed_on_L12", "l12")
    t0 = rig.t
    l17.present_for_load()
    pick = r02_pick("L12", 1.0, held)
    place = r02_place("L17", 1.0, held)
    wait(lambda: l17.mode != "BUSY", 30, "L17 present for load")
    ds.append(r02_transport(episode_id, "transport_R02_to_L17", plate_id, "L12/plate_nest", "L17/plate_load_frame", t0,
                            pick, place, bool(l17.seated), "custody: dosed on L12 (plate reader at L12)"))
    t0 = rig.t
    r = l17.load_plate(plate_id)
    loaded = r.accepted and wait(lambda: l17.mode != "BUSY", 30, "L17 load_plate") and l17.mode == "LOADED"
    n0 = len(l17.acquisitions)
    if loaded:
        l17.image_plate_region(plate_id, image_wells, 25.0, "10x", "autofocus", 1.0, "brightfield-morphology-v1")
        wait(lambda: l17.mode != "BUSY", 300, f"L17 image {image_wells}")
        for acq in list(l17.acquisitions[n0:]):
            if [m["name"] for m in acq["monitors"] if not m["passed"]] == ["focus_quality"]:
                l17.focus_memory.pop((plate_id, "10x"), None)
                l17.image_well(plate_id, acq["well_id"])
                wait(lambda: l17.mode != "BUSY", 120, f"L17 reacquire {acq['well_id']}")
    seen_w = set()
    for i, acq in enumerate(l17.acquisitions[n0:]):
        tag = f"image_{acq['well_id']}" + ("_reacquired" if acq["well_id"] in seen_w else "")
        seen_w.add(acq["well_id"])
        ds.append({"id": f"{episode_id}/{tag}", "action": "image", "component": "L17_BrightFieldImager",
                   "acquisition": acq, "truth_for_audit": l17.truth[n0 + i], "t_start": round(t0, 3), "t_end": acq["t"],
                   "command_completed": acq["command_completed"]})
    still("full_cell_4_imaging_on_L17", "l17")
    t0 = rig.t
    l17.present_for_unload()
    wait(lambda: l17.mode != "BUSY", 30, "L17 present for unload")
    pick = r02_pick("L17", 1.0, held)
    l17.stow()
    place = r02_place("HN", -1.0, held)
    ds.append(r02_transport(episode_id, "transport_R02_back", plate_id, "L17/plate_load_frame", "HN/handover_frame", t0,
                            pick, place, bool(hn.seated), "custody: identity read by L17 at load"))
    r02_park()
    go_above("HN", held=False)
    rig.phase = "pick"
    rig.pick(*at("HN"), "pick_HN", plate=held)
    rig.phase = None
    out, inc2 = r01_to_l10_incubate(episode_id, "return", plate_id, "HN/handover_frame", incubate_slot, held)
    ds += out
    still("full_cell_5_back_in_L10", "elevated")
    acqs = l17.acquisitions[n0:]
    outcome = {"route": "full_cell", "qc": [x["qc_record"]["verdict"] for x in ds if x["action"] == "qc"],
               "calibration": l17.calibration["calibration_id"], "dock": dock_res,
               "dose": dose_rec and {k: dose_rec[k] for k in ("valid", "volume_inferred_uL", "aborted")},
               "images_valid": sum(a["valid"] for a in acqs), "images": len(acqs), "incubated": bool(inc2),
               "L10_inventory": {k: v for k, v in enumerate(l10.inventory) if v}, "AMR": amr.mode,
               "duration_s": round(rig.t - t_ep, 1)}
    return ds, esc, outcome



# ------------------------------------------------------------------------------ derived-plan execution (E2M)
# The plan (okf/lab-automation-twin/L3-logical-axiomatization/derivation) is a sequence of motion, device-command and
# safety designators per trip. The interpreter executes them in order on the twin's controllers. A robot's
# approach/insert/grasp/lift at a seat is one pick of that robot's controller (executed at its `lift`), its
# transit/approach/place/release/retract one place (executed at its `retract`); L12's tip_pick/aspirate/dispense/
# tip_eject for one well are one dose_well (executed at `dispense`, the tip / aspirate / eject events are checked in
# L12's own log). Every step gets the twin time at which it completed and the evidence of its controller.
PLAN_NEST = {"l10": "L10", "hn": "HN", "l12": "L12", "l17": "L17"}
PLAN_R02_SIDE = {"HN": -1.0}


def run_plan_episode(episode_id, plan_path):
    from twin.culture.model import CONC_AU_PER_UL
    plan = json.load(open(plan_path))
    plate_id = "Plate_P17"
    held = by_barcode[plate_id]
    slot = PLATES["P17"]["slot"]
    seat_keys = {"L10_Incubator/transfer_station": "l10", "HandoverNest_R01_R02/handover_frame": "hn",
                 "L12_LiquidHandler/plate_nest": "l12", "L17_BrightFieldImager/plate_load_frame": "l17"}
    seat_dev = {k: d for k, v in plan["names"].items() for frag, d in seat_keys.items() if v.endswith(frag + "#entity")}
    trips, ok_all = [], True
    print(f"[plan] executing {os.path.relpath(plan_path, ROOT)}: {plan['selected']['id']} "
          f"(EIG {plan['selected']['eig_bits']} bits >= {plan['requirement_bits']})")
    for se in plan["sessions"]:
        t0, ex, ok_trip = rig.t, [], True
        print(f"[plan] === session {se['session']} trip {se['trip']} (culture t = {se['t_h']} h): {len(se['steps'])} steps")
        pending = {}
        acq_n0 = None

        def done(st, ok, **ev):
            nonlocal ok_trip
            ok_trip &= bool(ok)
            ex.append({"index": st["index"], "primitive": st["primitive"], "level": st["level"],
                       "who": st.get("robot") or st.get("device"), "t": round(rig.t - t0, 3), "ok": bool(ok),
                       "predicted_s": st["duration_s"], **ev})
            if not ok:
                print(f"[plan]   step {st['index']} {st['primitive']} FAILED {ev}")

        for st in se["steps"]:
            t = st["term"]
            k = t[0]
            if k == "cmd":
                dev, c = t[1], t[2]
                cn = c[0] if isinstance(c, list) else c
                if cn == "check_interlocks":
                    closed = all(d_.state() == "closed" for d_ in interlock.doors.values()) if LAB else True
                    done(st, closed, evidence="LAB interlock state" if LAB else
                         "Cell 01 scene: no door model; the enclosure interlock is not simulated (assumed closed)")
                elif cn == "verify_identity":
                    pending["identity"] = st          # read by L10's barcode reader during release (next step)
                elif cn == "present" and dev == "l10" and l10.inventory[slot] == plate_id and not pending.get("out"):
                    tr = rig.t
                    r = l10.release_plate(plate_id)
                    rel = r.accepted and wait(lambda: l10.mode in ("PRESENTED_LOADED", "FAULT"), 120, "L10 release")
                    seen = (events_since(l10, tr, "identity_read") or [{}])[-1].get("observed")
                    done(pending.pop("identity"), seen == plate_id, observed=seen)
                    done(st, rel and l10.mode == "PRESENTED_LOADED", mode=l10.mode)
                    pending["out"] = True
                elif cn == "present" and dev == "l10":
                    wait(l10_ready_for_transfer, 600, "L10 environment ready for a transfer")
                    l10.present_for_load()
                    done(st, wait(lambda: l10.mode == "PRESENTED_EMPTY", 30, "L10 present for load"), mode=l10.mode)
                elif cn == "present" and dev == "l17":
                    unload = l17.mode == "LOADED"
                    (l17.present_for_unload if unload else l17.present_for_load)()
                    done(st, wait(lambda: l17.mode != "BUSY", 30, f"L17 present for {'unload' if unload else 'load'}"),
                         mode=l17.mode)
                elif cn == "stow":
                    d = {"l10": l10, "l17": l17}[dev]
                    d.stow()
                    done(st, wait(lambda: d.mode not in ("BUSY",) and d.mode != "PRESENTED_EMPTY", 30, f"{dev} stow"),
                         mode=d.mode)
                elif cn == "tip_eject" and "dose_evs" in pending:   # follows its dispense: checked in L12's log
                    evs = pending.pop("dose_evs")
                    done(st, "tip_eject" in evs and evs.index("tip_pick") < evs.index("tip_eject"), l12_event=True)
                elif cn in ("tip_pick", "aspirate", "tip_eject"):
                    pending.setdefault("dose", []).append(st)
                elif cn == "dispense":
                    m = st["material"]
                    well, reagent, au = m[1].upper(), m[2], m[3] / 100.0
                    asp = next(x for x in pending["dose"] if x["primitive"] == "aspirate")
                    pos = int(asp["term"][2][1].rsplit("_", 1)[-1])
                    vol = round(au / CONC_AU_PER_UL, 3)
                    td = rig.t
                    n_ev = len(l12.events)
                    r = l12.dose_well(plate_id, well, pos, f"abstract_{reagent}_reagent",
                                      "SIM-LOT-A" if pos == 1 else "SIM-LOT-B", vol, 1.2, 2.0,
                                      intended_effect=f"abstract_{reagent}")
                    fin = r.accepted and wait(lambda: l12.mode != "BUSY", 240, f"L12 dose_well {well} {reagent} {au} au")
                    rec = l12.doses[-1] if fin and l12.doses else None
                    evs = [e["event"] for e in l12.events[n_ev:]]
                    order_ok = evs.index("tip_pick") < evs.index("tip_eject") if {"tip_pick", "tip_eject"} <= set(evs) \
                        else False
                    for x in pending.pop("dose"):
                        done(x, order_ok, l12_event=x["primitive"] in evs or x["primitive"] == "aspirate")
                    done(st, bool(rec and rec["valid"] and not rec["aborted"]), well=well, reagent=reagent, au=au,
                         volume_uL=vol, refused=None if r.accepted else r.reason,
                         dose=rec and {k_: rec[k_] for k_ in ("valid", "volume_inferred_uL", "aborted", "well_id")},
                         duration_s=round(rig.t - td, 2))
                    pending.setdefault("doses", []).append(rec)
                    pending["dose_evs"] = evs
                elif cn == "load":
                    r = l17.load_plate(plate_id)
                    done(st, r.accepted and wait(lambda: l17.mode != "BUSY", 30, "L17 load_plate") and l17.mode == "LOADED",
                         mode=l17.mode)
                    acq_n0 = len(l17.acquisitions)
                elif cn == "image_well":
                    pending.setdefault("images", []).append(st)
                    nxt = se["steps"][st["index"] + 1] if st["index"] + 1 < len(se["steps"]) else None
                    if not (nxt and nxt["term"][0] == "cmd" and isinstance(nxt["term"][2], list)
                            and nxt["term"][2][0] == "image_well"):
                        wells = [x["material"][1].upper() for x in pending["images"]]
                        l17.image_plate_region(plate_id, wells, 25.0, "10x", "autofocus", 1.0, "brightfield-morphology-v1")
                        wait(lambda: l17.mode != "BUSY", 300, f"L17 image {wells}")
                        for acq in list(l17.acquisitions[acq_n0:]):
                            if [m_["name"] for m_ in acq["monitors"] if not m_["passed"]] == ["focus_quality"]:
                                l17.focus_memory.pop((plate_id, "10x"), None)
                                l17.image_well(plate_id, acq["well_id"])
                                wait(lambda: l17.mode != "BUSY", 120, f"L17 reacquire {acq['well_id']}")
                        acqs = {a_["well_id"]: a_ for a_ in l17.acquisitions[acq_n0:]}
                        for x in pending.pop("images"):
                            w = x["material"][1].upper()
                            a_ = acqs.get(w)
                            done(x, bool(a_ and a_["valid"]), well=w,
                                 acquisition=a_ and {k_: a_.get(k_) for k_ in ("well_id", "valid", "t")},
                                 calibration=l17.calibration.get("calibration_id"))
                elif cn == "validate":
                    l17.present_for_load()
                    r02_pick("L21ref", 1.0, REF_PATH)
                    r02_place("L17", 1.0, REF_PATH)
                    wait(lambda: l17.mode != "BUSY", 30, "L17 present")
                    l17.load_plate(REF_ID)
                    wait(lambda: l17.mode != "BUSY", 30, "L17 load reference")
                    r = l21.validate_imager(l17, REF_ID)
                    if r.accepted:
                        wait(lambda: l21.mode != "BUSY", 900, "L21 validate_imager")
                    l17.present_for_unload()
                    wait(lambda: l17.mode != "BUSY", 30, "L17 present for unload")
                    r02_pick("L17", 1.0, REF_PATH)
                    l17.stow()
                    r02_place("L21ref", 1.0, REF_PATH)
                    r02_clear()
                    done(st, l21.qc_records and l21.qc_records[-1]["verdict"] == "pass",
                         qc=l21.qc_records and l21.qc_records[-1]["verdict"])
                elif cn == "wait_environment":
                    done(st, wait(l10_ready_for_transfer, 600, "L10 environment ready") and l10.environment_valid,
                         environment={k_: round(v, 3) for k_, v in l10.env.items()})
                elif cn == "store":
                    tr = rig.t
                    r = l10.incubate(plate_id, slot)
                    fin = r.accepted and wait(lambda: l10.mode in ("READY", "FAULT"), 120, "L10 incubate")
                    seen = (events_since(l10, tr, "identity_read") or [{}])[-1].get("observed")
                    done(st, fin and l10.mode == "READY" and l10.inventory[slot] == plate_id and seen == plate_id,
                         slot=slot, observed=seen)
                else:
                    done(st, False, error=f"no executor for command {cn}")
                continue
            r = t[1]
            if k == "tool_couple":
                okt, why = ensure_t01()
                done(st, okt, tool=(r02rig.tool or {}).get("id"), reason=why)
            elif k in ("approach", "insert", "grasp", "transit", "place", "release"):
                pending.setdefault(("leg", r), []).append(st)
            elif k == "lift":
                legs = pending.pop(("leg", r), [])
                src = PLAN_NEST[seat_dev[legs[0]["term"][2][1]]]
                if r == "r01":
                    go_above(src, held=False)
                    rig.phase = "pick"
                    g = rig.pick(*at(src), f"pick_{src}", plate=held)
                    rig.phase = None
                    okp = bool(g.get("lifted") and g.get("contact"))
                    ev = {"lifted": bool(g.get("lifted")), "contact": bool(g.get("contact"))}
                else:
                    g = r02_pick(src, PLAN_R02_SIDE.get(src, 1.0), held)
                    okp = bool(g["positioned"] and g["converged"] and g["lifted"])
                    ev = {k_: g[k_] for k_ in ("positioned", "converged", "lifted_mm")}
                for x in legs:
                    done(x, okp, pick_at=src)
                done(st, okp, pick_at=src, **ev)
            elif k == "retract":
                legs = pending.pop(("leg", r), [])
                dst_atom = t[2][1]
                dst = PLAN_NEST[seat_dev[dst_atom]]
                if r == "r01":
                    tr_ok, _ = go_above(dst, held=True, phase="transit")
                    rig.phase = "place"
                    placed, info = rig.place(*at(dst), contacts_phase="insert")
                    rig.phase = None
                    rig.step(int(0.5 * HZ))
                    seated = {"HN": lambda: bool(hn.seated), "L10": lambda: bool(l10.seated)}[dst]()
                    okp = bool(tr_ok and placed and seated)
                    clear = go_above("L09" if dst == "HN" else dst, held=False)[0]   # leave the seat for the next robot
                    ev = {"seated": seated, "retract_to": "L09 approach (clear of HN)" if dst == "HN" else f"{dst} approach"}
                else:
                    g = r02_place(dst, PLAN_R02_SIDE.get(dst, 1.0), held)
                    seated = {"HN": lambda: bool(hn.seated), "L12": lambda: bool(l12.seated),
                              "L17": lambda: bool(l17.seated)}[dst]()
                    okp = bool(g["positioned"] and g["converged"] and seated)
                    clear = (r02_clear() if dst == "L12" else r02_park() if dst == "HN" else True)
                    ev = {"seated": seated, "offset_mm": g["offset_mm"], "tilt_deg": g["tilt_deg"],
                          "l12_airspace_clear": bool(l12.airspace_clear()) if dst == "L12" else None}
                for x in legs:
                    done(x, okp, place_at=dst)
                done(st, okp and bool(clear), place_at=dst, **ev)
            else:
                done(st, False, error=f"no executor for motion {k}")
        dur = rig.t - t0
        within = dur <= plan["window_s"]
        complete = {x["index"] for x in ex} == set(range(len(se["steps"])))   # every step executed and checked
        ok_trip &= within and complete
        n_ok = sum(x["ok"] for x in ex)
        print(f"[plan] --- {se['id']}: {n_ok}/{len(se['steps'])} steps ok, {dur:.1f} s outside L10 "
              f"(predicted {se['duration_s']:.1f} s, window {plan['window_s']:.0f} s) -> {'OK' if ok_trip else 'FAIL'}")
        trips.append({"id": se["id"], "session": se["session"], "t_h": se["t_h"], "device": se["device"],
                      "steps_total": len(se["steps"]), "steps_ok": n_ok, "executed": ex, "duration_s": round(dur, 2),
                      "predicted_s": se["duration_s"], "within_window": within, "ok": ok_trip,
                      "doses": [d for d in pending.get("doses", []) if d]})
        ok_all &= ok_trip
        if not ok_trip:
            break
    acq = [a_ for a_ in l17.acquisitions]
    return [], [], {"route": "derived_plan", "plan": os.path.relpath(plan_path, ROOT), "selected": plan["selected"],
                    "trips": trips, "all_ok": ok_all, "L10_inventory": {k: v for k, v in enumerate(l10.inventory) if v},
                    "acquisitions": [{k_: a_.get(k_) for k_ in ("well_id", "valid", "t")} for a_ in acq]}

VIDEO = None
if args.video:   # live video of the run (twin/video.py): director follows the moving robot, captions from this log
    from pxr import Gf as _Gf  # noqa: E402

    from twin.video import Recorder  # noqa: E402
    VIDEO = Recorder(stage, args.video, title="AICOR Lab 1  |  Cell 01 full-cell experiment  |  semantic digital twin "
                     "(Isaac Sim, simulated)" if LAB else "Cell 01  |  semantic digital twin (Isaac Sim, simulated)")

    def _amr_world():
        x, y, _ = amr.pose_true()
        return np.array(amr.map_to_world.Transform(_Gf.Vec3d(float(x), float(y), 0.0)))

    def _amr_shot(p):
        if p[0] < -5.2 and p[1] > -1.2:                                    # in the storage room
            return (-5.55, -0.95, 2.05), p + [0, 0, 0.5], 18.0
        if abs(p[0]) < 3.0 and abs(p[1]) < 2.25:                           # inside Cell 01
            return (0.9, -2.0, 1.75), p + [0, 0, 0.55], 20.0
        eye = np.clip(p + [2.6, -2.5, 0], [-9.3, -6.7, 0], [9.3, 3.9, 0]) + [0, 0, 2.3]
        return eye, p + [0, 0, 0.5], 20.0

    VIDEO.add("R03", "R03 clean-sample AMR", _amr_world, _amr_shot, 5)
    VIDEO.add("R02", "R02 rail-mounted arm", lambda: r02rig.tcp()[0],
              lambda p: ((float(np.clip(p[0] + 0.5, -1.5, 2.6)), -1.25, 1.95), p, 22.0), 4)
    VIDEO.add("R01", "R01 fixed plate arm", lambda: rig.tcp()[0], lambda p: ((-0.35, -1.45, 1.85), p, 22.0), 3)
    VIDEO.add("L17", "L17 bright-field imager", lambda: None,
              lambda p: ((0.95, 0.55, 1.55), (1.65, 1.40, 1.02), 26.0), 2, busy_fn=lambda: l17.mode == "BUSY")
    VIDEO.add("L12", "L12 liquid handler", lambda: None,
              lambda p: ((0.95, -1.25, 1.60), (0.15, 0.25, 1.08), 26.0), 2, busy_fn=lambda: l12.mode == "BUSY")
    VIDEO.add("L21", "L21 QC / calibration", lambda: None,
              lambda p: ((1.55, 0.25, 1.55), (2.15, 1.12, 0.98), 26.0), 2, busy_fn=lambda: l21.mode == "BUSY")
    VIDEO.install()
    VIDEO.hook_stdout()

if args.rsa:   # the rsa kernel drives the twin through its action designators (rsa/isaac.py)
    from types import SimpleNamespace  # noqa: E402

    from rsa.isaac import run_isaac  # noqa: E402
    S_ = SimpleNamespace(rig=rig, r02rig=r02rig, l10=l10, l12=l12, l17=l17, l21=l21, h4=h4, hn=hn, LAB=LAB, HZ=HZ,
                         interlock=interlock if LAB else None, by_barcode=by_barcode, wait=wait,
                         events_since=events_since, go_above=go_above, at=at, r02_pick=r02_pick, r02_place=r02_place,
                         r02_clear=r02_clear, r02_park=r02_park, ensure_t01=ensure_t01,
                         l10_ready_for_transfer=l10_ready_for_transfer, REF_PATH=REF_PATH, REF_ID=REF_ID,
                         PLAN_R02_SIDE=PLAN_R02_SIDE, PLATES=PLATES)
    try:
        ok_rsa = run_isaac(S_, args.rsa)
    except Exception:  # noqa: BLE001 -- report and fail the process (Kit would otherwise exit 0)
        import traceback  # noqa: E402
        traceback.print_exc()
        ok_rsa = False
    app_utils.stop()
    sys.stdout.flush()
    os._exit(0 if ok_rsa else 1)

t_wall = time.time()
episodes = []
EPISODES["full_cell"] = FULL
if args.plan:
    EPISODES["plan"] = dict(plan_path=os.path.abspath(args.plan))
for n, name in enumerate(args.episodes.split(",")):
    cfg = EPISODES[name]
    eid = f"cell01-ep-{n + 1:03d}-{name}"
    runner = {"quarantine_release": run_release_episode, "imaging": run_imaging_episode,
              "full_cell": run_full_cell_episode, "plan": run_plan_episode}.get(name)
    ds, esc, outcome = runner(eid, **cfg) if runner else run_episode(eid, name, **cfg)
    if name == "plan":
        os.makedirs(OUT_DIR, exist_ok=True)
        tag = json.load(open(cfg["plan_path"]))["tag"]
        dst = os.path.join(OUT_DIR, f"plan_execution_{tag}.json")
        json.dump({"episode_id": eid, "scene": "lab" if LAB else "cell01", "place_mode": args.place_mode, **outcome,
                   "wall_time_s": round(time.time() - t_wall, 1)}, open(dst, "w"), indent=1, default=str)
        print(f"[plan] wrote {os.path.relpath(dst, ROOT)}; {'PASS' if outcome['all_ok'] else 'FAIL'}", flush=True)
        app_utils.stop()
        if VIDEO is not None:
            with open(os.path.join(args.video, "video_log.json"), "w") as f:
                json.dump(VIDEO.log, f)
            print(f"[episode] video: {VIDEO.frame} frames -> {VIDEO.encode('cell01_derived_plan.mp4')}", flush=True)
        sys.stdout.flush()
        os._exit(0 if outcome["all_ok"] else 1)
    episodes.append({"episode_id": eid, "scenario": name, "request": {**cfg, "protocol": PROTOCOL},
                     "designators": ds, "escalations": esc, "outcome": outcome})
    print(f"[episode] {eid} outcome {json.dumps(outcome, default=str)[:400]}")
raw = {"run": {"scene": "scenes/lab_twin.usda (AICOR Lab 1, layout P1)" if LAB else "scenes/cell01_twin.usda (layout P1)", "physics_hz": HZ, "place_mode": args.place_mode,
               "l17_calibration": l17.calibration,
               "initial_state": initial, "plates": PLATES, "wall_time_s": round(time.time() - t_wall, 1),
               "L10_environment_series_1Hz": l10.series[-400:]},
       "episodes": episodes}
os.makedirs(OUT_DIR, exist_ok=True)
raw_path = os.path.join(OUT_DIR, "cell01_episodes_raw.json")
with open(raw_path, "w") as f:
    json.dump(raw, f, indent=2, default=str)
records = build_all(json.loads(json.dumps(raw, default=str)))
with open(os.path.join(OUT_DIR, "cell01_episodes_records.json"), "w") as f:
    json.dump(records, f, indent=2, default=str)

ok = True
for ep in records["episodes"]:
    recs = {r["designator_id"].split("/")[-1]: r for r in ep["records"]}
    summary = ", ".join(f"{k}: {'commit' if r['semantic_event']['eligible'] else 'route ' + r['routing']}"
                        for k, r in recs.items())
    if ep["scenario"] == "nominal":
        exp = (set(recs) == {"retrieve", "transport", "store"} and all(r["semantic_event"]["eligible"] for r in recs.values())
               and ep["outcome"].get("stored"))
    elif ep["scenario"] == "imaging":
        imgs = [k for k in recs if k.startswith("image_")]
        wells = {k.split("_")[1] for k in imgs}
        admitted = {k.split("_")[1] for k in imgs if recs[k]["routing"] == "evidence_admission"}
        # a blocked image is acceptable only as an out-of-focus image that was retained and then reacquired validly
        blocked_ok = all(recs[k]["routing"] == "evidence_admission" or (
            recs[k]["lifecycle"]["monitors"]["failed"] == ["focus_quality"]
            and recs[k]["routing"] == "L21_qc_or_human_escalation") for k in imgs)
        exp = (set(recs) - set(imgs) == {"retrieve", "transport_R01", "transport_R02", "transport_R02_back",
                                         "transport_R01_back", "store"} and len(wells) == 3 and admitted == wells
               and blocked_ok and all(r["semantic_event"]["eligible"] for k, r in recs.items() if k not in imgs)
               and ep["outcome"].get("stored"))
    elif ep["scenario"] == "full_cell":
        imgs = [k for k in recs if k.startswith("image_")]
        wells = {k.split("_")[1] for k in imgs}
        admitted = {k.split("_")[1] for k in imgs if recs[k]["routing"] == "evidence_admission"}
        qcs = [k for k in recs if k.startswith("qc_")]
        last_tcp = [k for k in qcs if "tcp" in k][-1:] if qcs else []
        exp = (len(wells) == 2 and admitted == wells and any(k.startswith("dose_") for k in recs)
               and all(recs[k]["semantic_event"]["eligible"] for k in recs if not k.startswith(("image_", "qc_")))
               and all(recs[k]["semantic_event"]["eligible"] for k in last_tcp + [k for k in qcs if "img" in k])
               and ep["outcome"].get("incubated"))
    elif ep["scenario"] == "quarantine_release":
        exp = (set(recs) == {"retrieve", "transport", "incubate"} and all(r["semantic_event"]["eligible"] for r in recs.values())
               and ep["outcome"].get("incubated") and ep["outcome"].get("H4") == "READY" and ep["outcome"].get("H4_empty")
               and any(e["kind"] == "plate_unaccounted" and not e["resolved"] for e in ep["escalations"]))
    else:
        exp = (set(recs) == {"retrieve", "transport", "quarantine"} and not recs["retrieve"]["semantic_event"]["eligible"]
               and recs["retrieve"]["routing"] == "H4_quarantine" and recs["quarantine"]["semantic_event"]["eligible"]
               and ep["outcome"].get("contained") and ep["outcome"].get("reentry_blocked")
               and recs["retrieve"]["quarantine_request"]["physical_execution"]["status"] == "executed"
               and any(e["kind"] == "plate_unaccounted" for e in ep["escalations"]))
    ok &= bool(exp) and ep["validation"]["pass"]
    print(f"[episode] {ep['episode_id']}: {summary}; schema {'PASS' if ep['validation']['pass'] else ep['validation']['errors']}"
          f" -> {'AS EXPECTED' if exp else 'UNEXPECTED'}")
print(f"[episode] wrote {raw_path} and cell01_episodes_records.json; {'PASS' if ok else 'FAIL'}")
app_utils.stop()
sys.stdout.flush()
if VIDEO is not None:
    with open(os.path.join(args.video, "video_log.json"), "w") as f:
        json.dump(VIDEO.log, f)
    print(f"[episode] video: {VIDEO.frame} frames -> {VIDEO.encode('cell01_full_cell.mp4')}", flush=True)
sys.stdout.flush()
os._exit(0 if ok else 1)
