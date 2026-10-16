# L17: bright-field imaging station

L17 implements Cell 01's `sdt/components/L17_BrightFieldImager.yaml` and binds to
`/World/Cell01/Stations/L17_BrightFieldImager`, with the five required frames: `plate_load_frame`, `plate_stage`,
`objective_frame`, `camera_frame` and `illumination_frame`.

**Design basis.** Cell 01's baseline is an "OpenFlexure-derived operational mechanism in a Cell01 photorealistic
enclosure". This is a project-owned inverted bright-field plate imager in that spirit, not an OpenFlexure part
model. All dimensions and optical figures are parameters of `build_l17.py`.

Everything in this folder except `README.md` is generated. Edit the script, not the outputs.

## Build and test

```bash
env_cad/bin/python assets/l17/build_l17.py         # CAD -> STEP + layered USD; checks collider clearance over the joint ranges
env_isaacsim/bin/python scripts/test_l17_physics.py # mechanism + imaging, 15 checks
env_isaacsim/bin/python scripts/test_l17_robot.py   # R02 loads, L17 images, R02 unloads (Cell 01 overlay), 6 checks
```

## Structure

| Link / joint | What |
|---|---|
| **Body** | 440 × 500 × 430 mm enclosure on a 0.772 m plinth, so the seat is at 0.972 m like the other transfer nests. It holds the stage rail, the focus column, the barcode reader, the LED condenser and the front status lamps. |
| **Gate** (`GateSlide`, Z, 95 mm) | Motorised front gate over the 264 × 92 mm load opening. |
| **StageY** (`StageY`, Y, −290…+36 mm) | The load drawer and the row axis. At −290 mm the nest is presented 80 mm in front of the housing (`plate_load_frame`); between −31.5 and +31.5 mm it positions rows A–H over the optical axis. It runs on a side rail at x +150 mm, clear of the optics. |
| **StageX** (`StageX`, X, ±55 mm) | The column axis, on a guide behind the plate. It carries the open frame nest: 5 mm lips under the plate rim, the shared SBS corner guides with 34° lead-ins, the A1 key, finger reliefs on the long sides, 4 seat sensors in the short-side lips, and AprilTag #17 on the carriage. |
| **Focus** (`FocusZ`, Z, ±2.5 mm) | The whole optics module moves, as in OpenFlexure: fold mirror, tube lens, camera, and the turret pivot. The drive is lead-screw stiff (1·10⁷ N/m, about 2 µm of sag). |
| **Turret** (`TurretRotate`, 0 / 180°) | Two parfocal objectives (45 mm): 10x/0.25 with WD 12 mm, and 4x/0.10 with WD 17 mm. They carry the standard yellow and red rings. |

**Clearance by design.** Nothing on the stage passes under the wells except the 4 mm frame. Every stage part that
crosses the objective zone stays at least 2 mm above the highest objective tip, even at focus +2.5 mm.
Self-collisions are off because the rails and carriages touch by design. Instead, `build_l17.py` sweeps the
collider boxes of all links over the joint ranges and fails the build on any overlap; the smallest gap is
0.5 mm, at the sliding rails. The sweep applies the controller's interlocks:
- the stage leaves the chamber only with the gate open;
- StageX is centred before StageY leaves the imaging range.

## Image formation (`twin/l17_optics.py`)

The camera image is formed from the simulated state. The controller (`twin/l17_controller.py`) decides only from
the image and its own encoders.

**Inputs from the simulation:**
- the plate's PhysX pose, so a shifted or tilted plate is imaged where it really is;
- the focal point (FocusZ);
- the indexed objective (TurretRotate within 1°);
- the LED level (the light prim);
- the exposure;
- whether the gate is open (stray light).

**The sample** is a **synthetic optical test sample** of absorbing Gaussian objects per (barcode, well). It gives
the images structure for the focus and registration checks. It is not a model of cells or morphology (D016).

**Optics and sensor:**
- **PSF:** Gaussian, combining the diffraction limit, geometric defocus (|dz|·NA) and the pixel footprint.
- **Field:** 820 × 616 px at 0.45 µm/px (10x) or 1.12 µm/px (4x), so 0.37 × 0.28 mm or 0.92 × 0.69 mm.
- **Sensor:** Poisson shot noise, 3 e⁻ read noise, 10 000 e⁻ full well, 12-bit ADC, 12 % vignetting. At LED
  1.0 and 25 ms the background sits near 57 % of full scale.
- **Status:** these are optical and sensor engineering assumptions, documented in the module.

**Focus score:** a normalised Brenner gradient on a 2 × 2-binned image, minus the noise term predicted by the
calibrated sensor model. A blank field scores about 0. At 10x the in-focus score is about 0.07–0.10 and falls to
half at about 20 µm of defocus.

## Controller (`twin/l17_controller.py`)

**Capabilities (contract names):**
- `load_plate`, as `present_for_load` followed by `load_plate`: the barcode is read at the stage home position;
- `autofocus`: a coarse sweep, a fine sweep, then a least-squares parabola over the top of the focus curve. A
  seed from the previous well cuts it from 34 to 20 frames;
- `image_well`, `image_plate_region` (e.g. `"B04:B06"`), `compute_focus_quality` and `export_raw_image`;
- `present_for_unload`, `present_for_removal` (to H4 after an identity mismatch) and `stow`.

**Monitors per image.** These are the five that Cell 01's `validate_l17_image` requires:

| Monitor | Passes when |
|---|---|
| `plate_identity` | The barcode read at load matches. |
| `plate_seating` | All 4 seat sensors read under 0.4 mm. |
| `focus_quality` | The score is at or above the calibrated floor, and at least 0.85 × the autofocus best. |
| `illumination_state` | The LED reads back as commanded, the gate is closed, and the histogram mean is 0.25–0.85 of full scale with at most 0.1 % saturated. |
| `calibration_state` | The calibration record is current. |

Cell 01 has no separate exposure monitor, so the histogram is part of `illumination_state`.

**Evidence.**
- **Raw images:** each image is saved as a 16-bit PNG with a JSON sidecar holding the settings, focus score,
  histogram, monitors, calibration id, stage coordinates, autofocus summary, imaging history and SHA-256.
  Rejected images are kept.
- **Imaging history:** every exposure is counted per plate and well, autofocus frames included, as a relative
  light dose (LED level × ms). The contract requires this phototoxicity history.
- **Calibration:** the record `L17-CAL-2026-10-16-SIM` is simulated input, because the L21 QC station is not
  built yet.

**Records.** `twin/episode_records.py: l17_image_record` builds them with Cell 01's own `validate_l17_image` and
`build_l17_neem_record`. Valid images are routed to `evidence_admission`; blocked ones go to
`L21_qc_or_human_escalation`.

## Verified (2026-10-16)

**`scripts/test_l17_physics.py`: 15/15.**

| Check | Result |
|---|---|
| Interlocks | Held during every presentation; the presented nest is at `plate_load_frame` to 0.0 mm. |
| Misseated plate (8 mm off) | `load_plate` refused (`plate_misseated`). |
| B03, 10x autofocus | Valid; true defocus −0.16 µm (half the depth of field is 4.4 µm). |
| Registration | The field is in B03, 0.47 mm from the well centre. The plate has 0.5 mm clearance per side in the nest. |
| Region B04:B06 | All valid, defocus within 0.06 µm. |
| 4x at E07 | Valid, defocus 0.14 µm; parfocal within 0.1 µm. |
| Out of focus (+60 µm) | Retained; `focus_quality` fails; blocked. |
| Overexposure (60 ms, 99.5 % saturated) | `illumination_state` fails; blocked. |
| Expired calibration | `image_well` refused. |
| Identity mismatch | Plate held, then presented for removal. |

The contact sheet is `test_reports/l17_contact_sheet.png`.

**`scripts/test_l17_robot.py`, in the Cell 01 overlay: 6/6.**
- R02 coupled T01 and picked the plate from the handover nest.
- It placed the plate on the presented nest at rail 2.5 m: offset 0.01 / 0.23 mm, seated on all 4 sensors.
- L17 loaded the plate and imaged B03 validly, with true defocus −0.52 µm.
- L17 presented the plate for unload. R02 took it back to the handover nest, where it seated 0.42 / 0.20 mm off.
  L17 stowed; R02 stored T01.

## Limits

- **Optical model:**
  - the image is synthesised (`twin/l17_optics.py`), not ray traced through the optics;
  - the sample is a synthetic test target;
  - there is no plate-bottom refraction, no phase contrast and no flat-field correction.
- **Registration:** the plate's position in the nest (±0.5 mm) is not corrected by image-based well finding. The
  imaged field can be up to about 0.7 mm from the well centre, still well inside the 6.9 mm well.
- **Calibration:** the record is simulated until L21 exists.
- **Contact sensing:** L17 has no contact sensing of its own. The design-time sweep guarantees mechanism clearance.
