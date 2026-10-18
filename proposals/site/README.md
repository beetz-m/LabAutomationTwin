# Site layout proposal S1: AICOR Lab 1 around Cell 01 (not part of the Cell 01 baseline)

## Why this is a proposal

The Cell 01 specification (v0.3, §2) treats Cell 01 as "one bounded automation cell inside the larger
laboratory". Upstream systems prepare reagents and cultures; downstream cells take over imaging, assays and waste.
It fixes the cell's own interior: 6.0 × 4.5 × 2.5 m, the rear service access (≥ 1.0 m outside the cell) and the
front logistics lane. It does **not** define the surrounding lab.

S1 is that missing site level, drawn so the twin can show and test the cell in context. Its dimensions, rooms and
equipment classes are engineering choices made by the twin project; they need a decision before anyone builds to
them.

Implementation:
- `assets/site/build_site.py`: the building shell.
- `assets/labequip/`: the equipment.
- `tools/compose_lab.py`: placements, zones and the S1 dock; it writes `scenes/lab_twin.usda` and
  `scenes/site_layout_s1.json`.
- `tools/check_site.py`: the layout checks and `renders/site_plan_s1.png`.

## Layout (Cell 01 frame: origin at the cell floor centre, +Y toward the rear instrument wall)

| Zone | Extent (m) | Contents |
|---|---|---|
| Cell 01 | x ±3.05, y ±2.30 | Layout P1 and the fit-out (`assets/cell01_fitout/`). |
| Rear service corridor | y 2.30…4.2 | Technician access to the rear instruments (measured 1.65 m; the spec asks for ≥ 1.0 m). Utility panels on the north wall: electrical distribution, network/BMS, gas manifold. The main cable tray, with a drop into the cell trunking. |
| Front logistics | y −4.2…−2.30 | The AMR lane (y −3.3, floor-marked, 1.3 m wide) to the Cell 01 portal (x 1.15), plus a pedestrian walkway. |
| Storage room ST01 | x −9.6…−5.2, y −1.2…4.2 | See [Storage room ST01](#storage-room-st01) below. |
| Entrance / gowning | x −9.6…−5.2, y −7.0…−1.2 | Double door to the building corridor, lab coats, gloves, hand-wash sink, extinguisher, first aid, signage. |
| Operator area | x −5.2…3.3, y −7.0…−4.2 | A monitoring desk and an engineering desk facing the cell; the twin compute rack. |
| Culture prep | x 3.3…9.6, y −4.2…4.2 | Manual work upstream of Cell 01: two class II BSCs (with 1.0 m operator zones), a CO2 incubator stack, an island bench with a reagent shelf, a wall bench (microscope, centrifuge, water bath), a sink with eyewash, and an emergency shower. |
| Wash / waste | x 5.5…9.6, y −7.0…−4.2 | Autoclave and a waste station: the waste handover point the spec asks Cell 01 to expose. |

### Storage room ST01

- **Cold storage** along the north wall: a −80 °C ULT freezer, two +4 °C fridges and a −20 °C freezer.
- **CO2 cylinder cabinet** in the north-east corner. Its CO2 line runs along the ceiling and drops into the cell
  to L10.
- **Shelving racks** ST01-R1…R3, with addressable locations ST01-R*n*-S*k*.
- **LN2 cryostorage** with an O2-depletion monitor.
- **AMR dispatch** bench and dock S1.
- **Automatic sliding door**, 1.4 m clear.

### Building

- **Hall:** 19.2 × 11.2 m, with a 3.2 m suspended ceiling.
- **Lighting:** 40 LED panels, 600 × 600 mm, on a 2.4 m grid.
- **South windows:** four bays with blinds, and radiators below.
- **Doors:** the entrance on the west wall and a door to Lab 2 on the east wall.

## R03 site route

The route is: S1 dock (−6.4, 0.6), heading north → reverse out through the storage door → turn on the AMR lane at
(−6.4, −3.3) → east to (1.15, −3.3) → north through the Cell 01 portal (muted light curtain) → H2 approach
(−0.415, −0.28) → compliant docking at H2.

R03's map frame stays the H2 docked pose. The lab scene widens its planar X travel so it can reach S1; the Cell 01
scene keeps its own limits.

## Checks (`tools/check_site.py`, measured from the composed USD)

The checker confirms:
- No overlapping items; benchtop items stand on worktops.
- Every item is inside its room and out of the Cell 01 envelope.
- The AMR corridor (0.40 m half-width) and the turn-in-place circles (0.58 m) are clear.
- Door swings and the sliding-leaf path are clear.
- The rear corridor is ≥ 1.0 m.
- The BSC operator zones and the emergency-shower area are clear.

The latest results are in `test_reports/site_layout_check.json`.

## What a decision would need

- **Real room:** the actual room geometry: walls, columns, doors, windows and building services.
- **Room assignments:** which neighbouring rooms hold the storage, prep and waste functions; S1 assumes all of them
  sit in one hall.
- **Biosafety:** the biosafety level, and the room classification that goes with it (air changes, pressure cascade,
  gowning). S1 draws a gowning zone but does not model air handling.
- **Storage capacity:** cold-storage and cryostorage capacities, and the CO2 supply (cylinders or a central line).
- **Equipment:** vendors and models for the equipment classes. All of them are generic project-owned proxies.
