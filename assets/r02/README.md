# R02: rail-mounted UR5e with automatic tool changer (TCM01)

R02 implements Cell 01's `sdt/components/R02_RailMounted_UR5e.yaml` and `ToolChanger_Magazine.yaml`, and binds to
`/World/Cell01/Robots/R02_RailSystem` and `/World/Cell01/Tooling/AutomaticToolChanger`.

**Design basis.**
- The UR5e is the official `ur_description` (BSD-3-Clause), read in place from the Cell 01 kit.
- The rail, carriage, coupler, magazine and tools are project-owned parametric proxies. Neither the igus nor the
  Zimmer CAD has been acquired.

Everything in this folder except `README.md` is generated. Edit the scripts, not the outputs.

## Build and test

```bash
env_cad/bin/python tools/make_r02_urdf.py            # assets/r02/r02.urdf: rail + UR5e + coupler robot half
env_isaacsim/bin/python scripts/import_r02.py         # assets/r02/usd/ (wipes the old import first)
env_cad/bin/python assets/r02/build_tooling.py        # assets/r02/tooling.usda: magazine TCM01 + tools T01-T05
env_cad/bin/python tools/layout_p1.py && env_cad/bin/python tools/compose_cell01_overlay.py
env_isaacsim/bin/python scripts/test_r02.py           # 10 checks, test_reports/r02_report.json
```

## Structure

| Part | What |
|---|---|
| **Rail** | Prismatic `rail_joint`, travel 0–2.6 m (D004), soft limits 0.02–2.58 m, drive 2·10⁵ N/m. Placed at x −0.85…1.75, y 0.78 (layout P1). The beam top is at 0.965 m. |
| **UR5e** | Six revolute joints with the manufacturer's effort limits (150/28 N·m). The base sits on a 30 mm carriage at about 0.995 m. Link gravity is off, emulating the UR controller's compensation. |
| **Coupler** | WMR2063-class proxy: a 16 mm robot half on `tool0` and a 12 mm tool half on each tool. The lock is a surface-gripper attachment (see Lessons). |
| **TCM01** | Fork-type magazine north of the rail at (0.30, 1.20). Five docks at 150 mm pitch; coupling faces at 1.12 m. Each dock has an occupancy ray. |
| **Tools** | T01 plate gripper (the R01 GEP2006 fingers, TCP 171 mm from the flange as on R01), T02 tube gripper, T03 pipetting tool (contamination class `liquid_contact`), T04 suction tool (needs vacuum), T05 inspection camera. |

**Joint count.** The contract says "8-DOF" but lists a 1-DOF rail and a 6-DOF robot. The twin has those 7 joints
(the coupler lock is not a joint DOF).

## Runtime

**Authoring.** `twin/r02_rig.py: author_r02(stage)` adds R02 before play, as `twin/r01_rig.py` does for R01:
- it replaces the placeholder rail;
- it authors the initial joint state: mid-rail, in the carry posture. At all-zero joints the arm reaches 0.8 m
  west, into L09.

**Motion (`R02Rig`).**
- IK runs on the URDF (`twin/kinematics.py`): elbow-up solutions with at least 15° joint margins, best conditioned
  first.
- Moves between stations go through the compact carry posture.
- Approach, insertion and lift are Cartesian and run on the PhysX Jacobian.
- T01's jaws use the R01 coupled-jaw emulation.

**`twin/r02_controller.py`.**
- `R02Controller`: `home_rail`, `move_rail` (soft limits, encoder residual), and `position_for_station` with evidence.
- `ToolChanger.change_tool` / `store_tool` implement the contract's checks:
  - contamination compatibility;
  - dock occupancy, read from the ray, not the inventory;
  - coupler alignment within 1 mm and 1°, else `partial_lock` with no lock attempted;
  - lock verified;
  - tool ID read through the coupler (the tool's `tool:id`), else `wrong_tool`, and the tool is left in the dock;
  - utilities;
  - the tool must follow within 1 mm after lift-out;
  - lift-out height = tool length + 40 mm.

## Verified (2026-10-16, `scripts/test_r02.py`, 10/10)

**Rail.** Commands are refused before homing. Positioning residual is 0.14 mm, and a command at 2.7 m is refused.

**Reach plans with T01.**

| Frame | Rail position | Joint margin |
|---|---|---|
| R01/R02 handover nest | 0.02 m | 29° |
| L12 plate frame | 1.0 m | 93° |
| L17 plate load frame | 2.5 m | 108° |
| L21 reference plate | 2.58 m | 87° |

**Tool change and refusals.**
- **Tool change (T05):**
  - alignment before locking: 0.04 mm lateral, 0.36 mm gap;
  - lock verified and ID read;
  - after lift-out the tool follows within 0.73 mm;
  - stored back within 0.13 mm.
- **Misaligned (2.5 mm):** refused before locking; T04 untouched.
- **Swapped T02 and T03:** `wrong_tool` after the ID read; T03 left in its dock.
- **T03 for a clean task:** refused.

**Plate transfer with T01.**
- The plate is picked at the R01/R02 handover nest and carried 2.56 m along the rail.
- It is placed on L21's deck 0.4 / 0.6 mm from the target, flat.
- T01 is stored back.

## Lessons (Isaac Sim 6.2)

- **Runtime joints:** joints created, or toggled with `physics:jointEnabled`, while the simulation runs are ignored.
  Runtime attach and detach therefore uses the surface gripper. Drive targets on plain joints do follow USD edits.
- **Articulations:** the surface gripper does not attach articulation links. T01's jaws are plain driven prismatic
  joints, not an articulation.
- **The lock's own body:** the lock's body0 is a collider-free coupler body fixed to the wrist. The gripper's
  self-clearance is computed from body0's own colliders; when the robot coupler half overlapped the probe origin,
  the gripper pulled the tool into the robot by that clearance. The robot-half collider also ends 1 mm short of
  the coupling face.
- **Stale imports:** the URDF importer does not overwrite an existing output. A stale 32 mm coupler collider caused
  the 17 mm snap above, so `import_r02.py` wipes the output first.
- **Sleep:** tools must never sleep (`physxRigidBody:sleepThreshold = 0`). A sleeping tool was not woken when the
  coupler released it.

## Limits

- **Physical simplifications:**
  - The lock is ideal and rigid.
  - Utilities other than the electrical contact are assumed available.
  - There is no cable-chain model.
- **Collision checking:** R02's transits avoid stations by posture design (the carry posture), not by a
  collision-aware planner.
- **Placeholders:** L12, L17 and L21 are still Cell 01 placeholders. The L21 deck got a collider in the overlay;
  in Cell 01 it has none.
