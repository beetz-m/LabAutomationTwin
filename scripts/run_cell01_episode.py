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

Writes test_reports/episodes/cell01_episodes_raw.json and, via twin/episode_records.py, the NEEM-compatible
records cell01_episodes_records.json (validated against the Cell 01 schemas). Exit 1 unless both episodes end as
expected and every record validates.
Usage: env_isaacsim/bin/python scripts/run_cell01_episode.py [--episodes nominal,identity_swap]
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
ap.add_argument("--episodes", default="nominal,identity_swap,quarantine_release")
ap.add_argument("--place-mode", choices=("compliant", "drop"), default="compliant")
ap.add_argument("--frames", default=None, help="directory for path-traced stills at the key moments (presentations)")
ap.add_argument("--quick", action="store_true", help="with --frames: 1280x800, fewer samples")
ap.add_argument("--frame-filter", default="", help="with --frames: only frames whose name contains this")
args = ap.parse_args()

OVERLAY = os.path.join(ROOT, "scenes/cell01_twin.usda")
OUT_DIR = os.path.join(ROOT, "test_reports/episodes")
H4 = "/World/Cell01/Stations/H4_Quarantine"
L09 = "/World/Cell01/Stations/L09_PlateHotel"
L10 = "/World/Cell01/Stations/L10_Incubator"
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
EPISODES = {"nominal": dict(plate_id="Plate_P17", store_slot=3),
            "identity_swap": dict(plate_id="Plate_P18", store_slot=4),
            "quarantine_release": dict(sample_id="Plate_P23", review=REVIEW)}

from isaacsim import SimulationApp  # noqa: E402

RES = (1280, 800) if args.quick else (1920, 1200)
app = SimulationApp({"headless": True, **({"renderer": "PathTracing", "width": RES[0], "height": RES[1]} if args.frames else {})})

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from pxr import PhysxSchema, UsdGeom  # noqa: E402

from twin.episode_records import build_all  # noqa: E402
from twin.h4_controller import H4Controller  # noqa: E402
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
fr3_local = UsdGeom.Xformable(stage.GetPrimAtPath(f"{R01}/base_link")).GetLocalTransformation()
ART_ROOT = author_rig(stage, FR3_PATH, GRIP_PATH, f"{R01}/Pedestal", fr3_local, contact_prims=list(plate_paths.values()))
for _ in range(5):
    app.update()
with open(os.path.join(ROOT, "scenes/layout_p1.json")) as f:
    LAYOUT = json.load(f)
OBSTACLES = r01_planner.obstacles_from_stage(stage, LAYOUT)
_base_w = UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(f"{R01}/base_link"))
BASE = np.array(_base_w.ExtractTranslation())
assert abs(_base_w.ExtractRotationMatrix()[0][0] - 1.0) < 1e-6, "planner assumes R01's base_link is not rotated"
NEST = {"L10": frame_pose(stage, f"{L10}/transfer_station"), "L09": frame_pose(stage, f"{L09}/transfer_nest"),
        "H4": frame_pose(stage, f"{H4}/transfer_nest")}

app_utils.play(commit=True)
h4 = H4Controller(stage, H4)
l09 = PlateStoreController(stage, L09)
l10 = L10Controller(stage, L10)
for p in PLATES.values():
    l10.inventory[p["slot"]] = p["inventory"]  # the SDT's belief at episode start (P18's entry is wrong)
rig = R01Rig(ART_ROOT, GRIP_PATH, plates=list(plate_paths.values()), on_step=[h4.update, l09.update, l10.update],
             place_mode=args.place_mode, contacts=True)
by_barcode = {p["barcode"]: plate_paths[n] for n, p in PLATES.items()}
VIEWS = {"cluster": ((-0.25, -1.35, 1.85), (-1.80, 0.50, 1.00), 20.0),
         "h4": ((-1.25, -0.65, 1.55), (-2.05, 0.10, 1.00), 24.0),
         "l10": ((-1.25, 0.05, 1.60), (-1.95, 0.85, 1.05), 22.0),
         "l10_side": ((-2.60, 0.30, 1.75), (-1.95, 0.80, 1.00), 22.0),   # from west of H4: R01 does not hide the tray
         "elevated": ((0.55, -2.05, 2.55), (-1.70, 0.50, 0.95), 20.0)}
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


t_wall = time.time()
episodes = []
for n, name in enumerate(args.episodes.split(",")):
    cfg = EPISODES[name]
    eid = f"cell01-ep-{n + 1:03d}-{name}"
    ds, esc, outcome = (run_release_episode(eid, **cfg) if name == "quarantine_release" else run_episode(eid, name, **cfg))
    episodes.append({"episode_id": eid, "scenario": name, "request": {**cfg, "protocol": PROTOCOL},
                     "designators": ds, "escalations": esc, "outcome": outcome})
    print(f"[episode] {eid} outcome {json.dumps(outcome, default=str)[:400]}")
raw = {"run": {"scene": "scenes/cell01_twin.usda (layout P1)", "physics_hz": HZ, "place_mode": args.place_mode,
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
os._exit(0 if ok else 1)
