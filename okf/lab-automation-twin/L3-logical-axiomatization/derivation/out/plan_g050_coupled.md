# Derived plan: required information gain 0.5 bits

- **Selected experiment** `c_d85_t48_n1`: challenge 0.85 au, rescue 0.7 au after 48 h, 1 replicate(s) per arm; EIG 0.544 bits.
- **Wells** (free wells of Plate_P17): rescued: A01; comparator: A02; control: A05
- **Cost** 8738 (decisecond-equivalents (robot / device time + 60 s per well)); feasible candidates: 13
- **Solver** SAT, optimal True, 60643 ground rules, ground 0.05 s, solve 0.04 s

## Session s0 (t = 0 h), trip 1: l12, 257.3 s outside the incubator (window 600 s)

| # | Level | Primitive | Robot / device | Pose / argument | s | Discharges |
|---|---|---|---|---|---|---|
| 0 | safety_step | check_interlocks | cell01 |  | 0.5 | enclosure_door_interlock |
| 1 | safety_step | verify_identity | l10 |  | 0.0 | identity_verified |
| 2 | device_command | present | l10 |  | 26.01 |  |
| 3 | motion | approach | r01 | Stations/L10_Incubator/transfer_station | 1.89 |  |
| 4 | motion | insert | r01 | Stations/L10_Incubator/transfer_station | 1.26 |  |
| 5 | motion | grasp | r01 |  | 0.79 |  |
| 6 | motion | lift | r01 |  | 0.79 |  |
| 7 | device_command | stow | l10 |  | 3.0 |  |
| 8 | motion | transit | r01 | Stations/L10_Incubator/transfer_station, Fixtures/HandoverNest_R01_R02/handover_frame | 5.35 |  |
| 9 | motion | approach | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.89 |  |
| 10 | motion | place | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.57 |  |
| 11 | motion | release | r01 |  | 0.63 |  |
| 12 | motion | retract | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.57 |  |
| 13 | motion | approach | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 4.66 |  |
| 14 | motion | insert | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.11 |  |
| 15 | motion | grasp | r02 |  | 1.94 |  |
| 16 | motion | lift | r02 |  | 1.94 |  |
| 17 | motion | transit | r02 | Fixtures/HandoverNest_R01_R02/handover_frame, Stations/L12_LiquidHandler/plate_nest | 13.2 |  |
| 18 | motion | approach | r02 | Stations/L12_LiquidHandler/plate_nest | 4.66 |  |
| 19 | motion | place | r02 | Stations/L12_LiquidHandler/plate_nest | 3.88 |  |
| 20 | motion | release | r02 |  | 1.55 |  |
| 21 | motion | retract | r02 | Stations/L12_LiquidHandler/plate_nest | 3.88 |  |
| 22 | device_command | tip_pick | l12 | Stations/L12_LiquidHandler/tip_rack_frames/rack_1 | 7.12 |  |
| 23 | device_command | aspirate | l12 | Stations/L12_LiquidHandler/reagent_rack_frames/rack_1/pos_1 | 10.69 |  |
| 24 | device_command | dispense | l12 | Wells/A01/Interfaces/pipette_target_frame, 85 | 12.47 |  |
| 25 | device_command | tip_eject | l12 | Stations/L12_LiquidHandler/waste_frame | 5.34 |  |
| 26 | device_command | tip_pick | l12 | Stations/L12_LiquidHandler/tip_rack_frames/rack_1 | 7.12 |  |
| 27 | device_command | aspirate | l12 | Stations/L12_LiquidHandler/reagent_rack_frames/rack_1/pos_1 | 10.69 |  |
| 28 | device_command | dispense | l12 | Wells/A02/Interfaces/pipette_target_frame, 85 | 12.47 |  |
| 29 | device_command | tip_eject | l12 | Stations/L12_LiquidHandler/waste_frame | 5.34 |  |
| 30 | motion | approach | r02 | Stations/L12_LiquidHandler/plate_nest | 4.66 |  |
| 31 | motion | insert | r02 | Stations/L12_LiquidHandler/plate_nest | 3.11 |  |
| 32 | motion | grasp | r02 |  | 1.94 |  |
| 33 | motion | lift | r02 |  | 1.94 |  |
| 34 | motion | transit | r02 | Stations/L12_LiquidHandler/plate_nest, Fixtures/HandoverNest_R01_R02/handover_frame | 13.2 |  |
| 35 | motion | approach | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 4.66 |  |
| 36 | motion | place | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 37 | motion | release | r02 |  | 1.55 |  |
| 38 | motion | retract | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 39 | motion | approach | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.89 |  |
| 40 | motion | insert | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.26 |  |
| 41 | motion | grasp | r01 |  | 0.79 |  |
| 42 | motion | lift | r01 |  | 0.79 |  |
| 43 | motion | transit | r01 | Fixtures/HandoverNest_R01_R02/handover_frame, Stations/L10_Incubator/transfer_station | 5.35 |  |
| 44 | device_command | present | l10 |  | 26.01 |  |
| 45 | motion | approach | r01 | Stations/L10_Incubator/transfer_station | 1.89 |  |
| 46 | motion | place | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 47 | motion | release | r01 |  | 0.63 |  |
| 48 | motion | retract | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 49 | safety_step | wait_environment | l10 |  | 1.0 | l10_environment_valid |
| 50 | device_command | store | l10 |  | 20.25 |  |

## Session s1 (t = 48 h), trip 1: l12, 221.7 s outside the incubator (window 600 s)

| # | Level | Primitive | Robot / device | Pose / argument | s | Discharges |
|---|---|---|---|---|---|---|
| 0 | safety_step | check_interlocks | cell01 |  | 0.5 | enclosure_door_interlock |
| 1 | safety_step | verify_identity | l10 |  | 0.0 | identity_verified |
| 2 | device_command | present | l10 |  | 26.01 |  |
| 3 | motion | approach | r01 | Stations/L10_Incubator/transfer_station | 1.89 |  |
| 4 | motion | insert | r01 | Stations/L10_Incubator/transfer_station | 1.26 |  |
| 5 | motion | grasp | r01 |  | 0.79 |  |
| 6 | motion | lift | r01 |  | 0.79 |  |
| 7 | device_command | stow | l10 |  | 3.0 |  |
| 8 | motion | transit | r01 | Stations/L10_Incubator/transfer_station, Fixtures/HandoverNest_R01_R02/handover_frame | 5.35 |  |
| 9 | motion | approach | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.89 |  |
| 10 | motion | place | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.57 |  |
| 11 | motion | release | r01 |  | 0.63 |  |
| 12 | motion | retract | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.57 |  |
| 13 | motion | approach | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 4.66 |  |
| 14 | motion | insert | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.11 |  |
| 15 | motion | grasp | r02 |  | 1.94 |  |
| 16 | motion | lift | r02 |  | 1.94 |  |
| 17 | motion | transit | r02 | Fixtures/HandoverNest_R01_R02/handover_frame, Stations/L12_LiquidHandler/plate_nest | 13.2 |  |
| 18 | motion | approach | r02 | Stations/L12_LiquidHandler/plate_nest | 4.66 |  |
| 19 | motion | place | r02 | Stations/L12_LiquidHandler/plate_nest | 3.88 |  |
| 20 | motion | release | r02 |  | 1.55 |  |
| 21 | motion | retract | r02 | Stations/L12_LiquidHandler/plate_nest | 3.88 |  |
| 22 | device_command | tip_pick | l12 | Stations/L12_LiquidHandler/tip_rack_frames/rack_1 | 7.12 |  |
| 23 | device_command | aspirate | l12 | Stations/L12_LiquidHandler/reagent_rack_frames/rack_1/pos_2 | 10.69 |  |
| 24 | device_command | dispense | l12 | Wells/A01/Interfaces/pipette_target_frame, 70 | 12.47 |  |
| 25 | device_command | tip_eject | l12 | Stations/L12_LiquidHandler/waste_frame | 5.34 |  |
| 26 | motion | approach | r02 | Stations/L12_LiquidHandler/plate_nest | 4.66 |  |
| 27 | motion | insert | r02 | Stations/L12_LiquidHandler/plate_nest | 3.11 |  |
| 28 | motion | grasp | r02 |  | 1.94 |  |
| 29 | motion | lift | r02 |  | 1.94 |  |
| 30 | motion | transit | r02 | Stations/L12_LiquidHandler/plate_nest, Fixtures/HandoverNest_R01_R02/handover_frame | 13.2 |  |
| 31 | motion | approach | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 4.66 |  |
| 32 | motion | place | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 33 | motion | release | r02 |  | 1.55 |  |
| 34 | motion | retract | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 35 | motion | approach | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.89 |  |
| 36 | motion | insert | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.26 |  |
| 37 | motion | grasp | r01 |  | 0.79 |  |
| 38 | motion | lift | r01 |  | 0.79 |  |
| 39 | motion | transit | r01 | Fixtures/HandoverNest_R01_R02/handover_frame, Stations/L10_Incubator/transfer_station | 5.35 |  |
| 40 | device_command | present | l10 |  | 26.01 |  |
| 41 | motion | approach | r01 | Stations/L10_Incubator/transfer_station | 1.89 |  |
| 42 | motion | place | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 43 | motion | release | r01 |  | 0.63 |  |
| 44 | motion | retract | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 45 | safety_step | wait_environment | l10 |  | 1.0 | l10_environment_valid |
| 46 | device_command | store | l10 |  | 20.25 |  |

## Session s2 (t = 72 h), trip 1: l17, 214.8 s outside the incubator (window 600 s)

| # | Level | Primitive | Robot / device | Pose / argument | s | Discharges |
|---|---|---|---|---|---|---|
| 0 | safety_step | check_interlocks | cell01 |  | 0.5 | enclosure_door_interlock |
| 1 | safety_step | verify_identity | l10 |  | 0.0 | identity_verified |
| 2 | device_command | present | l10 |  | 26.01 |  |
| 3 | motion | approach | r01 | Stations/L10_Incubator/transfer_station | 1.89 |  |
| 4 | motion | insert | r01 | Stations/L10_Incubator/transfer_station | 1.26 |  |
| 5 | motion | grasp | r01 |  | 0.79 |  |
| 6 | motion | lift | r01 |  | 0.79 |  |
| 7 | device_command | stow | l10 |  | 3.0 |  |
| 8 | motion | transit | r01 | Stations/L10_Incubator/transfer_station, Fixtures/HandoverNest_R01_R02/handover_frame | 5.35 |  |
| 9 | motion | approach | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.89 |  |
| 10 | motion | place | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.57 |  |
| 11 | motion | release | r01 |  | 0.63 |  |
| 12 | motion | retract | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.57 |  |
| 13 | motion | approach | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 4.66 |  |
| 14 | motion | insert | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.11 |  |
| 15 | motion | grasp | r02 |  | 1.94 |  |
| 16 | motion | lift | r02 |  | 1.94 |  |
| 17 | motion | transit | r02 | Fixtures/HandoverNest_R01_R02/handover_frame, Stations/L17_BrightFieldImager/plate_load_frame | 13.2 |  |
| 18 | device_command | present | l17 |  | 5.0 |  |
| 19 | motion | approach | r02 | Stations/L17_BrightFieldImager/plate_load_frame | 4.66 |  |
| 20 | motion | place | r02 | Stations/L17_BrightFieldImager/plate_load_frame | 3.88 |  |
| 21 | motion | release | r02 |  | 1.55 |  |
| 22 | motion | retract | r02 | Stations/L17_BrightFieldImager/plate_load_frame | 3.88 |  |
| 23 | device_command | load | l17 |  | 7.41 |  |
| 24 | device_command | image_well | l17 | Wells/A01/Interfaces/imaging_target_frame | 2.11 |  |
| 25 | device_command | image_well | l17 | Wells/A02/Interfaces/imaging_target_frame | 2.11 |  |
| 26 | device_command | image_well | l17 | Wells/A05/Interfaces/imaging_target_frame | 2.11 |  |
| 27 | device_command | present | l17 |  | 5.0 |  |
| 28 | motion | approach | r02 | Stations/L17_BrightFieldImager/plate_load_frame | 4.66 |  |
| 29 | motion | insert | r02 | Stations/L17_BrightFieldImager/plate_load_frame | 3.11 |  |
| 30 | motion | grasp | r02 |  | 1.94 |  |
| 31 | motion | lift | r02 |  | 1.94 |  |
| 32 | device_command | stow | l17 |  | 5.0 |  |
| 33 | motion | transit | r02 | Stations/L17_BrightFieldImager/plate_load_frame, Fixtures/HandoverNest_R01_R02/handover_frame | 13.2 |  |
| 34 | motion | approach | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 4.66 |  |
| 35 | motion | place | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 36 | motion | release | r02 |  | 1.55 |  |
| 37 | motion | retract | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 38 | motion | approach | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.89 |  |
| 39 | motion | insert | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.26 |  |
| 40 | motion | grasp | r01 |  | 0.79 |  |
| 41 | motion | lift | r01 |  | 0.79 |  |
| 42 | motion | transit | r01 | Fixtures/HandoverNest_R01_R02/handover_frame, Stations/L10_Incubator/transfer_station | 5.35 |  |
| 43 | device_command | present | l10 |  | 26.01 |  |
| 44 | motion | approach | r01 | Stations/L10_Incubator/transfer_station | 1.89 |  |
| 45 | motion | place | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 46 | motion | release | r01 |  | 0.63 |  |
| 47 | motion | retract | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 48 | safety_step | wait_environment | l10 |  | 1.0 | l10_environment_valid |
| 49 | device_command | store | l10 |  | 20.25 |  |
