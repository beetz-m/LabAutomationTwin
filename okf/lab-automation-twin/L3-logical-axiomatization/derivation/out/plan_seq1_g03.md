# Derived plan: required information gain 0.3 bits

- **Selected experiment** `c_d85_t48_n1`: challenge 0.85 au, rescue 0.7 au after 48 h, 1 replicate(s) per arm; EIG 0.539 bits.
- **Wells** (free wells of Plate_P17): rescued: A01; comparator: A02; control: A05
- **Cost** 9986 (decisecond-equivalents (robot / device time + 60 s per well)); feasible candidates: 25
- **Solver** SAT, optimal True, 60750 ground rules, ground 0.06 s, solve 0.04 s

## Session s0 (t = 0 h), trip 1: l12, 298.9 s outside the incubator (window 600 s)

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
| 13 | tool | tool_couple | r02 | Tooling/AutomaticToolChanger/dock_T01 | 41.56 |  |
| 14 | motion | approach | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 4.66 |  |
| 15 | motion | insert | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.11 |  |
| 16 | motion | grasp | r02 |  | 1.94 |  |
| 17 | motion | lift | r02 |  | 1.94 |  |
| 18 | motion | transit | r02 | Fixtures/HandoverNest_R01_R02/handover_frame, Stations/L12_LiquidHandler/plate_nest | 13.2 |  |
| 19 | motion | approach | r02 | Stations/L12_LiquidHandler/plate_nest | 4.66 |  |
| 20 | motion | place | r02 | Stations/L12_LiquidHandler/plate_nest | 3.88 |  |
| 21 | motion | release | r02 |  | 1.55 |  |
| 22 | motion | retract | r02 | Stations/L12_LiquidHandler/plate_nest | 3.88 |  |
| 23 | device_command | tip_pick | l12 | Stations/L12_LiquidHandler/tip_rack_frames/rack_1 | 7.12 |  |
| 24 | device_command | aspirate | l12 | Stations/L12_LiquidHandler/reagent_rack_frames/rack_1/pos_1 | 10.69 |  |
| 25 | device_command | dispense | l12 | Wells/A01/Interfaces/pipette_target_frame, 85 | 12.47 |  |
| 26 | device_command | tip_eject | l12 | Stations/L12_LiquidHandler/waste_frame | 5.34 |  |
| 27 | device_command | tip_pick | l12 | Stations/L12_LiquidHandler/tip_rack_frames/rack_1 | 7.12 |  |
| 28 | device_command | aspirate | l12 | Stations/L12_LiquidHandler/reagent_rack_frames/rack_1/pos_1 | 10.69 |  |
| 29 | device_command | dispense | l12 | Wells/A02/Interfaces/pipette_target_frame, 85 | 12.47 |  |
| 30 | device_command | tip_eject | l12 | Stations/L12_LiquidHandler/waste_frame | 5.34 |  |
| 31 | motion | approach | r02 | Stations/L12_LiquidHandler/plate_nest | 4.66 |  |
| 32 | motion | insert | r02 | Stations/L12_LiquidHandler/plate_nest | 3.11 |  |
| 33 | motion | grasp | r02 |  | 1.94 |  |
| 34 | motion | lift | r02 |  | 1.94 |  |
| 35 | motion | transit | r02 | Stations/L12_LiquidHandler/plate_nest, Fixtures/HandoverNest_R01_R02/handover_frame | 13.2 |  |
| 36 | motion | approach | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 4.66 |  |
| 37 | motion | place | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 38 | motion | release | r02 |  | 1.55 |  |
| 39 | motion | retract | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 40 | motion | approach | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.89 |  |
| 41 | motion | insert | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.26 |  |
| 42 | motion | grasp | r01 |  | 0.79 |  |
| 43 | motion | lift | r01 |  | 0.79 |  |
| 44 | motion | transit | r01 | Fixtures/HandoverNest_R01_R02/handover_frame, Stations/L10_Incubator/transfer_station | 5.35 |  |
| 45 | device_command | present | l10 |  | 26.01 |  |
| 46 | motion | approach | r01 | Stations/L10_Incubator/transfer_station | 1.89 |  |
| 47 | motion | place | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 48 | motion | release | r01 |  | 0.63 |  |
| 49 | motion | retract | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 50 | safety_step | wait_environment | l10 |  | 1.0 | l10_environment_valid |
| 51 | device_command | store | l10 |  | 20.25 |  |

## Session s1 (t = 48 h), trip 1: l12, 263.3 s outside the incubator (window 600 s)

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
| 13 | tool | tool_couple | r02 | Tooling/AutomaticToolChanger/dock_T01 | 41.56 |  |
| 14 | motion | approach | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 4.66 |  |
| 15 | motion | insert | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.11 |  |
| 16 | motion | grasp | r02 |  | 1.94 |  |
| 17 | motion | lift | r02 |  | 1.94 |  |
| 18 | motion | transit | r02 | Fixtures/HandoverNest_R01_R02/handover_frame, Stations/L12_LiquidHandler/plate_nest | 13.2 |  |
| 19 | motion | approach | r02 | Stations/L12_LiquidHandler/plate_nest | 4.66 |  |
| 20 | motion | place | r02 | Stations/L12_LiquidHandler/plate_nest | 3.88 |  |
| 21 | motion | release | r02 |  | 1.55 |  |
| 22 | motion | retract | r02 | Stations/L12_LiquidHandler/plate_nest | 3.88 |  |
| 23 | device_command | tip_pick | l12 | Stations/L12_LiquidHandler/tip_rack_frames/rack_1 | 7.12 |  |
| 24 | device_command | aspirate | l12 | Stations/L12_LiquidHandler/reagent_rack_frames/rack_1/pos_2 | 10.69 |  |
| 25 | device_command | dispense | l12 | Wells/A01/Interfaces/pipette_target_frame, 70 | 12.47 |  |
| 26 | device_command | tip_eject | l12 | Stations/L12_LiquidHandler/waste_frame | 5.34 |  |
| 27 | motion | approach | r02 | Stations/L12_LiquidHandler/plate_nest | 4.66 |  |
| 28 | motion | insert | r02 | Stations/L12_LiquidHandler/plate_nest | 3.11 |  |
| 29 | motion | grasp | r02 |  | 1.94 |  |
| 30 | motion | lift | r02 |  | 1.94 |  |
| 31 | motion | transit | r02 | Stations/L12_LiquidHandler/plate_nest, Fixtures/HandoverNest_R01_R02/handover_frame | 13.2 |  |
| 32 | motion | approach | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 4.66 |  |
| 33 | motion | place | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 34 | motion | release | r02 |  | 1.55 |  |
| 35 | motion | retract | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 36 | motion | approach | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.89 |  |
| 37 | motion | insert | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.26 |  |
| 38 | motion | grasp | r01 |  | 0.79 |  |
| 39 | motion | lift | r01 |  | 0.79 |  |
| 40 | motion | transit | r01 | Fixtures/HandoverNest_R01_R02/handover_frame, Stations/L10_Incubator/transfer_station | 5.35 |  |
| 41 | device_command | present | l10 |  | 26.01 |  |
| 42 | motion | approach | r01 | Stations/L10_Incubator/transfer_station | 1.89 |  |
| 43 | motion | place | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 44 | motion | release | r01 |  | 0.63 |  |
| 45 | motion | retract | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 46 | safety_step | wait_environment | l10 |  | 1.0 | l10_environment_valid |
| 47 | device_command | store | l10 |  | 20.25 |  |

## Session s2 (t = 72 h), trip 1: l17, 256.4 s outside the incubator (window 600 s)

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
| 13 | tool | tool_couple | r02 | Tooling/AutomaticToolChanger/dock_T01 | 41.56 |  |
| 14 | motion | approach | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 4.66 |  |
| 15 | motion | insert | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.11 |  |
| 16 | motion | grasp | r02 |  | 1.94 |  |
| 17 | motion | lift | r02 |  | 1.94 |  |
| 18 | motion | transit | r02 | Fixtures/HandoverNest_R01_R02/handover_frame, Stations/L17_BrightFieldImager/plate_load_frame | 13.2 |  |
| 19 | device_command | present | l17 |  | 5.0 |  |
| 20 | motion | approach | r02 | Stations/L17_BrightFieldImager/plate_load_frame | 4.66 |  |
| 21 | motion | place | r02 | Stations/L17_BrightFieldImager/plate_load_frame | 3.88 |  |
| 22 | motion | release | r02 |  | 1.55 |  |
| 23 | motion | retract | r02 | Stations/L17_BrightFieldImager/plate_load_frame | 3.88 |  |
| 24 | device_command | load | l17 |  | 7.41 |  |
| 25 | device_command | image_well | l17 | Wells/A01/Interfaces/imaging_target_frame | 2.11 |  |
| 26 | device_command | image_well | l17 | Wells/A02/Interfaces/imaging_target_frame | 2.11 |  |
| 27 | device_command | image_well | l17 | Wells/A05/Interfaces/imaging_target_frame | 2.11 |  |
| 28 | device_command | present | l17 |  | 5.0 |  |
| 29 | motion | approach | r02 | Stations/L17_BrightFieldImager/plate_load_frame | 4.66 |  |
| 30 | motion | insert | r02 | Stations/L17_BrightFieldImager/plate_load_frame | 3.11 |  |
| 31 | motion | grasp | r02 |  | 1.94 |  |
| 32 | motion | lift | r02 |  | 1.94 |  |
| 33 | device_command | stow | l17 |  | 5.0 |  |
| 34 | motion | transit | r02 | Stations/L17_BrightFieldImager/plate_load_frame, Fixtures/HandoverNest_R01_R02/handover_frame | 13.2 |  |
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
