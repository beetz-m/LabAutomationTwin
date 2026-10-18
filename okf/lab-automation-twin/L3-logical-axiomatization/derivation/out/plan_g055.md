# Derived plan: required information gain 0.55 bits

- **Selected experiment** `c_d85_t48_n2`: challenge 0.85 au, rescue 0.7 au after 48 h, 2 replicate(s) per arm; EIG 0.601 bits.
- **Wells** (free wells of Plate_P17): rescued: A01, A02; comparator: A05, A06; control: A07
- **Cost** 12296 (decisecond-equivalents (robot / device time + 60 s per well)); feasible candidates: 6
- **Solver** SAT, optimal True, 60703 ground rules, ground 0.05 s, solve 0.03 s

## Session s0 (t = 0 h), trip 1: l12, 370.1 s outside the incubator (window 600 s)

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
| 31 | device_command | tip_pick | l12 | Stations/L12_LiquidHandler/tip_rack_frames/rack_1 | 7.12 |  |
| 32 | device_command | aspirate | l12 | Stations/L12_LiquidHandler/reagent_rack_frames/rack_1/pos_1 | 10.69 |  |
| 33 | device_command | dispense | l12 | Wells/A05/Interfaces/pipette_target_frame, 85 | 12.47 |  |
| 34 | device_command | tip_eject | l12 | Stations/L12_LiquidHandler/waste_frame | 5.34 |  |
| 35 | device_command | tip_pick | l12 | Stations/L12_LiquidHandler/tip_rack_frames/rack_1 | 7.12 |  |
| 36 | device_command | aspirate | l12 | Stations/L12_LiquidHandler/reagent_rack_frames/rack_1/pos_1 | 10.69 |  |
| 37 | device_command | dispense | l12 | Wells/A06/Interfaces/pipette_target_frame, 85 | 12.47 |  |
| 38 | device_command | tip_eject | l12 | Stations/L12_LiquidHandler/waste_frame | 5.34 |  |
| 39 | motion | approach | r02 | Stations/L12_LiquidHandler/plate_nest | 4.66 |  |
| 40 | motion | insert | r02 | Stations/L12_LiquidHandler/plate_nest | 3.11 |  |
| 41 | motion | grasp | r02 |  | 1.94 |  |
| 42 | motion | lift | r02 |  | 1.94 |  |
| 43 | motion | transit | r02 | Stations/L12_LiquidHandler/plate_nest, Fixtures/HandoverNest_R01_R02/handover_frame | 13.2 |  |
| 44 | motion | approach | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 4.66 |  |
| 45 | motion | place | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 46 | motion | release | r02 |  | 1.55 |  |
| 47 | motion | retract | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 48 | motion | approach | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.89 |  |
| 49 | motion | insert | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.26 |  |
| 50 | motion | grasp | r01 |  | 0.79 |  |
| 51 | motion | lift | r01 |  | 0.79 |  |
| 52 | motion | transit | r01 | Fixtures/HandoverNest_R01_R02/handover_frame, Stations/L10_Incubator/transfer_station | 5.35 |  |
| 53 | device_command | present | l10 |  | 26.01 |  |
| 54 | motion | approach | r01 | Stations/L10_Incubator/transfer_station | 1.89 |  |
| 55 | motion | place | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 56 | motion | release | r01 |  | 0.63 |  |
| 57 | motion | retract | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 58 | safety_step | wait_environment | l10 |  | 1.0 | l10_environment_valid |
| 59 | device_command | store | l10 |  | 20.25 |  |

## Session s1 (t = 48 h), trip 1: l12, 298.9 s outside the incubator (window 600 s)

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
| 27 | device_command | tip_pick | l12 | Stations/L12_LiquidHandler/tip_rack_frames/rack_1 | 7.12 |  |
| 28 | device_command | aspirate | l12 | Stations/L12_LiquidHandler/reagent_rack_frames/rack_1/pos_2 | 10.69 |  |
| 29 | device_command | dispense | l12 | Wells/A02/Interfaces/pipette_target_frame, 70 | 12.47 |  |
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

## Session s2 (t = 72 h), trip 1: l17, 260.6 s outside the incubator (window 600 s)

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
| 28 | device_command | image_well | l17 | Wells/A06/Interfaces/imaging_target_frame | 2.11 |  |
| 29 | device_command | image_well | l17 | Wells/A07/Interfaces/imaging_target_frame | 2.11 |  |
| 30 | device_command | present | l17 |  | 5.0 |  |
| 31 | motion | approach | r02 | Stations/L17_BrightFieldImager/plate_load_frame | 4.66 |  |
| 32 | motion | insert | r02 | Stations/L17_BrightFieldImager/plate_load_frame | 3.11 |  |
| 33 | motion | grasp | r02 |  | 1.94 |  |
| 34 | motion | lift | r02 |  | 1.94 |  |
| 35 | device_command | stow | l17 |  | 5.0 |  |
| 36 | motion | transit | r02 | Stations/L17_BrightFieldImager/plate_load_frame, Fixtures/HandoverNest_R01_R02/handover_frame | 13.2 |  |
| 37 | motion | approach | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 4.66 |  |
| 38 | motion | place | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 39 | motion | release | r02 |  | 1.55 |  |
| 40 | motion | retract | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 41 | motion | approach | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.89 |  |
| 42 | motion | insert | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.26 |  |
| 43 | motion | grasp | r01 |  | 0.79 |  |
| 44 | motion | lift | r01 |  | 0.79 |  |
| 45 | motion | transit | r01 | Fixtures/HandoverNest_R01_R02/handover_frame, Stations/L10_Incubator/transfer_station | 5.35 |  |
| 46 | device_command | present | l10 |  | 26.01 |  |
| 47 | motion | approach | r01 | Stations/L10_Incubator/transfer_station | 1.89 |  |
| 48 | motion | place | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 49 | motion | release | r01 |  | 0.63 |  |
| 50 | motion | retract | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 51 | safety_step | wait_environment | l10 |  | 1.0 | l10_environment_valid |
| 52 | device_command | store | l10 |  | 20.25 |  |
