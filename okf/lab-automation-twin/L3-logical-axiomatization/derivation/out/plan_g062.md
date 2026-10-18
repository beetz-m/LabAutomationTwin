# Derived plan: required information gain 0.62 bits

- **Selected experiment** `c_d85_t48_n3`: challenge 0.85 au, rescue 0.7 au after 48 h, 3 replicate(s) per arm; EIG 0.641 bits.
- **Wells** (free wells of Plate_P17): rescued: A01, A02, A05; comparator: A06, A07, A08; control: A09
- **Cost** 14606 (decisecond-equivalents (robot / device time + 60 s per well)); feasible candidates: 2
- **Solver** SAT, optimal True, 52774 ground rules, ground 0.04 s, solve 0.02 s

## Session s0 (t = 0 h), trip 1: l12, 441.3 s outside the incubator (window 600 s)

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
| 39 | device_command | tip_pick | l12 | Stations/L12_LiquidHandler/tip_rack_frames/rack_1 | 7.12 |  |
| 40 | device_command | aspirate | l12 | Stations/L12_LiquidHandler/reagent_rack_frames/rack_1/pos_1 | 10.69 |  |
| 41 | device_command | dispense | l12 | Wells/A07/Interfaces/pipette_target_frame, 85 | 12.47 |  |
| 42 | device_command | tip_eject | l12 | Stations/L12_LiquidHandler/waste_frame | 5.34 |  |
| 43 | device_command | tip_pick | l12 | Stations/L12_LiquidHandler/tip_rack_frames/rack_1 | 7.12 |  |
| 44 | device_command | aspirate | l12 | Stations/L12_LiquidHandler/reagent_rack_frames/rack_1/pos_1 | 10.69 |  |
| 45 | device_command | dispense | l12 | Wells/A08/Interfaces/pipette_target_frame, 85 | 12.47 |  |
| 46 | device_command | tip_eject | l12 | Stations/L12_LiquidHandler/waste_frame | 5.34 |  |
| 47 | motion | approach | r02 | Stations/L12_LiquidHandler/plate_nest | 4.66 |  |
| 48 | motion | insert | r02 | Stations/L12_LiquidHandler/plate_nest | 3.11 |  |
| 49 | motion | grasp | r02 |  | 1.94 |  |
| 50 | motion | lift | r02 |  | 1.94 |  |
| 51 | motion | transit | r02 | Stations/L12_LiquidHandler/plate_nest, Fixtures/HandoverNest_R01_R02/handover_frame | 13.2 |  |
| 52 | motion | approach | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 4.66 |  |
| 53 | motion | place | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 54 | motion | release | r02 |  | 1.55 |  |
| 55 | motion | retract | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 56 | motion | approach | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.89 |  |
| 57 | motion | insert | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.26 |  |
| 58 | motion | grasp | r01 |  | 0.79 |  |
| 59 | motion | lift | r01 |  | 0.79 |  |
| 60 | motion | transit | r01 | Fixtures/HandoverNest_R01_R02/handover_frame, Stations/L10_Incubator/transfer_station | 5.35 |  |
| 61 | device_command | present | l10 |  | 26.01 |  |
| 62 | motion | approach | r01 | Stations/L10_Incubator/transfer_station | 1.89 |  |
| 63 | motion | place | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 64 | motion | release | r01 |  | 0.63 |  |
| 65 | motion | retract | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 66 | safety_step | wait_environment | l10 |  | 1.0 | l10_environment_valid |
| 67 | device_command | store | l10 |  | 20.25 |  |

## Session s1 (t = 48 h), trip 1: l12, 334.5 s outside the incubator (window 600 s)

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
| 31 | device_command | tip_pick | l12 | Stations/L12_LiquidHandler/tip_rack_frames/rack_1 | 7.12 |  |
| 32 | device_command | aspirate | l12 | Stations/L12_LiquidHandler/reagent_rack_frames/rack_1/pos_2 | 10.69 |  |
| 33 | device_command | dispense | l12 | Wells/A05/Interfaces/pipette_target_frame, 70 | 12.47 |  |
| 34 | device_command | tip_eject | l12 | Stations/L12_LiquidHandler/waste_frame | 5.34 |  |
| 35 | motion | approach | r02 | Stations/L12_LiquidHandler/plate_nest | 4.66 |  |
| 36 | motion | insert | r02 | Stations/L12_LiquidHandler/plate_nest | 3.11 |  |
| 37 | motion | grasp | r02 |  | 1.94 |  |
| 38 | motion | lift | r02 |  | 1.94 |  |
| 39 | motion | transit | r02 | Stations/L12_LiquidHandler/plate_nest, Fixtures/HandoverNest_R01_R02/handover_frame | 13.2 |  |
| 40 | motion | approach | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 4.66 |  |
| 41 | motion | place | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 42 | motion | release | r02 |  | 1.55 |  |
| 43 | motion | retract | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 44 | motion | approach | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.89 |  |
| 45 | motion | insert | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.26 |  |
| 46 | motion | grasp | r01 |  | 0.79 |  |
| 47 | motion | lift | r01 |  | 0.79 |  |
| 48 | motion | transit | r01 | Fixtures/HandoverNest_R01_R02/handover_frame, Stations/L10_Incubator/transfer_station | 5.35 |  |
| 49 | device_command | present | l10 |  | 26.01 |  |
| 50 | motion | approach | r01 | Stations/L10_Incubator/transfer_station | 1.89 |  |
| 51 | motion | place | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 52 | motion | release | r01 |  | 0.63 |  |
| 53 | motion | retract | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 54 | safety_step | wait_environment | l10 |  | 1.0 | l10_environment_valid |
| 55 | device_command | store | l10 |  | 20.25 |  |

## Session s2 (t = 72 h), trip 1: l17, 264.8 s outside the incubator (window 600 s)

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
| 30 | device_command | image_well | l17 | Wells/A08/Interfaces/imaging_target_frame | 2.11 |  |
| 31 | device_command | image_well | l17 | Wells/A09/Interfaces/imaging_target_frame | 2.11 |  |
| 32 | device_command | present | l17 |  | 5.0 |  |
| 33 | motion | approach | r02 | Stations/L17_BrightFieldImager/plate_load_frame | 4.66 |  |
| 34 | motion | insert | r02 | Stations/L17_BrightFieldImager/plate_load_frame | 3.11 |  |
| 35 | motion | grasp | r02 |  | 1.94 |  |
| 36 | motion | lift | r02 |  | 1.94 |  |
| 37 | device_command | stow | l17 |  | 5.0 |  |
| 38 | motion | transit | r02 | Stations/L17_BrightFieldImager/plate_load_frame, Fixtures/HandoverNest_R01_R02/handover_frame | 13.2 |  |
| 39 | motion | approach | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 4.66 |  |
| 40 | motion | place | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 41 | motion | release | r02 |  | 1.55 |  |
| 42 | motion | retract | r02 | Fixtures/HandoverNest_R01_R02/handover_frame | 3.88 |  |
| 43 | motion | approach | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.89 |  |
| 44 | motion | insert | r01 | Fixtures/HandoverNest_R01_R02/handover_frame | 1.26 |  |
| 45 | motion | grasp | r01 |  | 0.79 |  |
| 46 | motion | lift | r01 |  | 0.79 |  |
| 47 | motion | transit | r01 | Fixtures/HandoverNest_R01_R02/handover_frame, Stations/L10_Incubator/transfer_station | 5.35 |  |
| 48 | device_command | present | l10 |  | 26.01 |  |
| 49 | motion | approach | r01 | Stations/L10_Incubator/transfer_station | 1.89 |  |
| 50 | motion | place | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 51 | motion | release | r01 |  | 0.63 |  |
| 52 | motion | retract | r01 | Stations/L10_Incubator/transfer_station | 1.57 |  |
| 53 | safety_step | wait_environment | l10 |  | 1.0 | l10_environment_valid |
| 54 | device_command | store | l10 |  | 20.25 |  |
