# Settings available in the game data but not in the tuner

Generated from the extracted stock data of the five tested cars (BMW M3 E46 CSL, Toyota GR86, Mazda RX-7 FD, Alfa Romeo Giulia GTAm, Porsche 992 GT3 R Rennsport) against `tuner/catalogue.json` (81 settings). Question answered: which physics values exist in the game files that the tuner does not offer yet. Facts and schema field names only; the "Likely effect" column is a guess from the field name and unverified.

Method. Every car's `.car` (CarData, with its inline copies of engine, gearbox, drivetrain, clutch, brakes, suspensions, electronics, aero, controls, general) and the standalone files it points to (engine, gearbox, drivetrain, clutch, brakes, stock setup, setup limits) plus every coilover, suspension, wing and turbo file in `data/` were decoded with `tools/car_json.py` (named schema fields). Alternate files in `parts/`, `unrestricted/` and `bak/`, the wet setup, AI data (`.aicardata`) and the mechanical presets are not counted. Each scalar leaf (int, float, bool, enum) is flattened to a path; strings, bytes and the point lists of curves are skipped, curves are counted once per reference. A leaf is COVERED when a catalogue target of any setting resolves to it (role file plus path, indices and `[key=VALUE]` selectors resolved, inline `@car` copies included, a covered object covers everything below it); a curve reference is covered when it is the `curve_from` of a setting or names the same file. Everything else is UNCOVERED. In the tables `[*]` stands for any list index; values are given per car in file order (front / rear, level 1 / 2 ...); `-` = the car does not have the field; `*` = the standalone file and the inline `.car` copy disagree (the inline value is shown in brackets).

Reading the numbers: most values exist twice (standalone file and inline copy in the `.car`), so leaf counts exceed the number of distinct physical values; the covered leaves are mostly setup defaults and limits (min / max). The setup limits file (`limits`) lists min / max / step / is_modifiable for each adjustable setup entry and so also shows which setup entries exist.

## Summary

| | BMW | GR86 | RX-7 | Giulia | Porsche |
|---|---|---|---|---|---|
| Files decoded | 17 | 15 | 17 | 18 | 14 |
| Scalar leaves | 860 | 827 | 808 | 971 | 1113 |
| Covered by a catalogue target | 126 | 122 | 106 | 123 | 121 |
| Uncovered | 734 | 705 | 702 | 848 | 992 |
| Uncovered share | 85% | 85% | 87% | 87% | 89% |
| Curve references (covered / total) | 4 / 28 | 4 / 26 | 4 / 34 | 4 / 36 | 4 / 26 |
| Unnamed wire fields kept in `_unknown` | 112 | 105 | 217 | 114 | 117 |

Distinct normalized paths over the five cars: 890, of which 819 have at least one uncovered leaf (the curated rows below stand for 389 of them, inline copies and hard points included; the rest is in the appendix).

Uncovered leaves / all leaves per section (Section = file role, `car/<name>` = section inside the `.car`; each cell is `uncovered/total`):

| Section | BMW | GR86 | RX-7 | Giulia | Porsche | Distinct uncovered paths |
|---|---|---|---|---|---|---|
| car/general | 11/12 | 12/13 | 12/13 | 12/13 | 12/13 | 14 |
| car/suspensions | 107/107 | 105/105 | 117/117 | 108/108 | 128/128 | 193 |
| car/drivetrain | 8/8 | 7/8 | 7/8 | 3/3 | 5/5 | 10 |
| car/engine | 21/29 | 6/13 | 24/30 | 30/38 | 13/18 | 40 |
| car/brakes | 2/4 | 2/4 | 2/4 | 15/17 | 41/43 | 46 |
| car/steeringSystem | - | - | 5/5 | - | - | 5 |
| car/electronics | 38/38 | 60/60 | 10/10 | 60/60 | 149/149 | 41 |
| car/controls | 4/5 | 4/5 | 4/5 | 4/5 | 3/4 | 4 |
| car/aero | 43/43 | 43/43 | 14/14 | 63/63 | 53/53 | 22 |
| car/gearbox | 11/22 | 10/20 | 9/18 | 13/26 | 11/22 | 15 |
| car/clutch | 5/5 | 4/4 | 4/4 | 5/5 | 5/5 | 5 |
| car/performance_modes | 5/5 | 6/6 | - | 11/11 | - | 4 |
| car/bodyMeshOffset | 6/6 | 5/5 | 5/5 | 5/5 | 5/5 | 6 |
| car/boxColliders | - | 5/5 | 10/10 | 5/5 | 10/10 | 5 |
| engine | 22/30 | 12/20 | 25/31 | 30/38 | 13/18 | 42 |
| gearbox | 11/22 | 10/20 | 9/18 | 13/26 | 12/23 | 15 |
| drivetrain | 8/8 | 7/8 | 7/8 | 3/3 | 5/5 | 10 |
| clutch | 5/5 | 4/4 | 4/4 | 5/5 | 5/5 | 5 |
| brakes | 2/4 | 2/4 | 2/4 | 15/17 | 41/43 | 46 |
| setup | 35/75 | 46/86 | 35/72 | 36/74 | 40/80 | 19 |
| limits | 208/250 | 221/260 | 270/301 | 242/277 | 298/341 | 126 |
| coilover | 40/40 | 42/42 | 52/52 | 40/40 | 42/42 | 27 |
| suspension | 86/86 | 51/51 | 53/53 | 56/56 | 74/74 | 99 |
| wing | 56/56 | 41/41 | 12/12 | 62/62 | 27/27 | 14 |
| turbo | - | - | 10/10 | 12/14 | - | 6 |

Wire-level unknowns (fields beyond the schema, mostly the legacy tail of `.drivetrain` and `.clutch`) are not named and not counted as leaves.

## Curated candidates

78 candidates (74 scalar rows, 4 curve rows). Path is the standalone-file path; "+car inline" means the same field also exists inside the `.car` (`suspensions.coilover_front/rear.*`, `suspensions.suspension_geometry_*`, `engine.*`, `brakes.*`, `aero.wings[*].*` ...). Combined rows list both fields in file order.

| Path | Section | Likely effect (unverified) | BMW | GR86 | RX-7 | Giulia | Porsche |
|---|---|---|---|---|---|---|---|
| `suspensions.longitudinal_cg_location` | car/suspensions | Longitudinal centre-of-gravity position (front weight share or CG distance as a wheelbase fraction), weight balance. | 0.517 | 0.55 | 0.51 | 0.54 | 0.369 |
| `suspensions.wheel_base` | car/suspensions | Wheelbase in metres; yaw response and weight transfer. | 2.729 | 2.575 | 2.425 | 2.82 | 2.507 |
| `suspensions.track_front / track_rear` | car/suspensions | Front and rear track width in metres; roll stiffness distribution and lateral weight transfer. | 1.518 ; 1.525 | 1.52 ; 1.55 | 1.46 ; 1.46 | 1.58 ; 1.654 | 1.722 ; 1.739 |
| `general.torsionalStiffness / torsionalDamping` | car/general | Chassis torsional stiffness and its damping (body flex between the axles). | 28000 ; 251 | 20000 ; 100 | 10000 ; 50 | 20000 ; 50 | 35000 ; 500 |
| `general.maxFuel` | car/general | Tank capacity in litres; with kgPerLiter it sets the fuel mass and its balance effect. | 63 | 50 | 76 | 58 | 117 |
| `suspensions.arbFront.stiffness / arbRear.stiffness` | car/suspensions | Physical anti-roll bar stiffness per axle; the setup arbs[] values probably scale it (absent on the BMW). unverified | - | 23000 ; 7000 | 21500 ; 9000 | 60000 ; 16000 | 20000 ; 80000 |
| `coilover.springRate` | coilover (+car inline) | Physical coilover spring rate per axle (front / rear file); relation to the setup wheel_rate is unknown, guess: base value the setup scales. | 55000 / 50000 | 45000 / 38000.1 | 40000 | 40000 / 53000 | 240000 / 260000 |
| `coilover.damper.slow.bump` | coilover (+car inline) | Damper force slope at low piston speed, bump direction (front / rear). | 5500 / 12000 | 3000 / 4200 | 2200 / 1200 | 5500 / 4500 | 13750 / 12000 |
| `coilover.damper.slow.rebound` | coilover (+car inline) | Damper force slope at low piston speed, rebound direction. | 7500 / 16000 | 7000 / 7500 | 10100 / 5370 | 7500 / 6500 | 11850 / 7150 |
| `coilover.damper.fast.bump` | coilover (+car inline) | Damper force slope above the fast threshold, bump direction. | 1500 / 250 | 1500 | 1434 / 1134 | 1500 / 2000 | 8000 / 7000 |
| `coilover.damper.fast.rebound` | coilover (+car inline) | Damper force slope above the fast threshold, rebound direction. | 4750 / 1000 | 3500 / 2300 | 8900 / 3220 | 4750 / 4250 | 6000 / 4000 |
| `coilover.damper.fastThresholdBump / fastThresholdRebound` | coilover (+car inline) | Piston speed where the damper switches from the slow to the fast slope. | 0.15 / 0.12 ; 0.15 / 0.12 | 0.15 ; 0.15 | 0.07 / 0.08 ; 0.12 | 0.15 ; 0.18 | 0.55 (inline: 0.03) * ; 0.55 (inline: 0.03) * |
| `coilover.bumpStopUp.Range / bumpStopDown.Range` | coilover (+car inline) | Travel at which the upper / lower bump stop engages. unverified | 0.0193681 / 0.0746095 ; 0.0556319 / 0.0153905 | 0.0674512 / 0.0353948 ; 0.0325488 / 0.0596052 | 0.11 ; 0.015 / 0.005 | 0.00930455 / 0.0523357 ; 0.0956955 / 0.0676643 | 0.000352632 / 0.0195387 ; 0.0346474 / 0.0254613 |
| `coilover.bumpStopUp.Force / bumpStopDown.Force` | coilover (+car inline) | Force scale of the bump stops. unverified | 80 / 500 ; 500 | 800 / 750 ; 600 | 1000 ; 750 / 900 | 400 / 500 ; 1000 | 800 ; 1000 |
| `setup.suspensions[*].bump_stop_up.rate / bump_stop_down.rate` | setup | Adjustable bump-stop rate in the setup (per corner); the limits file has min / max / step for it. | 100 / 500 ; 200 / 150 | 800 / 750 ; 600 | 1000 ; 750 | 500 / 400 ; 100 / 500 | 4000 ; 800 |
| `setup.suspensions[*].bump_stop_up.range / bump_stop_down.range` | setup | Adjustable bump-stop engagement range in the setup (per corner). | -0.00563 / 0.04461 ; 0.03563 / -0.00461 | 0.03745 / 0.02039 ; -0.01545 / -0.00039 | 0.02 / 0.035 ; 0.02 / 0.005 | 0.00930455 / 0.0523357 ; 0.0956955 / 0.0676643 | -0.005 / 0.02 ; 0.05 / 0.02 / 0.0254613 |
| `setup.suspensions[*].helper_rate / helper_range` | setup | Helper (third) spring rate and range in the setup (GR86). unverified | - | 5000 ; 0.06 | - | - | - |
| `setup.alignments[*].caster` | setup | Caster angle per front wheel (setup default; limits have min / step). | -0.068 | -0.06296 / -0.04296 | -0.01369 | -0.0488 | -0.02 / -0.1 |
| `setup.aero.front_target_height / rear_target_height` | setup | Target ride height front / rear in mm (ride height adjustment, drives the collar positions). | 116 ; 118 | 140 ; 130 | 175 ; 180 | 110 ; 155 | 60 ; 75 |
| `setup.aero.collar_positions_mm[*]` | setup | Spring collar position per corner in mm (result of the target heights). unverified | 68.1212 / 68.1221 / 25.9178 / 25.9174 | 109.379 / 109.376 / 95.9882 / 95.9904 | 147.326 / 147.327 / 144.276 / 144.274 | 79.9013 / 79.9009 / 59.8687 / 59.8687 | 24.5607 / 24.5591 / 12.78 / 12.78 |
| `setup.aero.rear_wing_angle` | setup | Adjustable rear wing angle (only cars with an adjustable wing). | - | - | 1 | - | 11.3 |
| `setup.mechanical_balance.brakes.torque_multiplier` | setup | Brake torque multiplier in percent (the BMW limits allow 100 only). | 100 | 100 | 100 | 100 | 100 |
| `setup.electronics.tc1` | setup | Traction control level selection (index into the electronics settings arrays). unverified | 1 | 1 | - | 1 | 5 |
| `setup.electronics.tc2` | setup | Second traction control level selection (cars with TC2). | - | 1 | - | 1 | 3 |
| `setup.electronics.abs` | setup | ABS level selection (index into ABS.settings[]). | 1 | 1 | 1 | 1 | 4 |
| `setup.electronics.engine_map` | setup | Engine map selection (index into engine.maps[]); Porsche only. | - | - | - | - | 2 |
| `suspension.basic_data.staticCamber` | suspension (+car inline) | Static camber of the geometry (front / rear file, degrees), basis of the setup camber. | -1.5 / -2 / -1.6 (inline: -1.5 / -1.6) * | -0.9 / -1.7 | -0.6 / 0.4 | -1.1 / -1.5 | -5.7 / -4.4 |
| `suspension.basic_data.toeOutLinear` | suspension (+car inline) | Toe change per metre of wheel travel (bump steer coefficient). unverified | 0.0005 / 0.0002 | 0.00065 / 0.0002 | -0.0002 / -0.001 | 0.00015 / -0.0005 | 0.00044 / -0.0011 |
| `suspension.basic_data.hubMass` | suspension (+car inline) | Unsprung hub mass per corner in kg. | 32 / 35 | 36 / 39 | 40 / 50 | 40 / 45 | 51 / 46 |
| `suspension.{strut|dW_data|dw_coil_data|multi_link_data|multi_link_new_data}.* (hard points x/y/z)` | suspension (+car inline) | Suspension hard points (arm and strut mounting coordinates): roll centre, camber gain, bump steer, Ackermann. Whole geometry, hard to tune by hand. unverified | F: strut; R: dW_data+multi_link_data | F: strut; R: dW_data | F: dW_data; R: dW_data | F: dW_data; R: dW_data | F: dw_coil_data; R: multi_link_new_data |
| `controls.steerRatio` | car/controls | Steering ratio of the car file (the setup steer_ratio is covered, this is the car-level value; GR86 has a negative sign). | 14.5 | -13.5 | 16 | 12 | 15 |
| `controls.linearSteerRodRatio` | car/controls | Steering rack / rod ratio (wheel angle per steering movement). unverified | 0.0017 | 0.001975 | 0.00215 | 0.002 | 0.0022 |
| `controls.steerAssist` | car/controls | Steering assist strength. unverified | 1 | 1 | 1 | 1 | - |
| `steeringSystem.fourWSControllers.stages[*].{combinatorMode ; downLimit ; filterGain ; inputVar ; upLimit}` | car/steeringSystem | Rear-wheel steering controller (combinator, limits, filter, input variable); RX-7 only. | - | - | Add ; -100 ; 0.99 ; LatG ; 100 | - | - |
| `brakes.frontBias` | brakes (+car inline) | Front brake bias of the brake file (Giulia as a fraction 0.75, the others in percent). | 68 | 72 | 67.5 | 0.75 | 65 |
| `brakes.biasStep` | brakes (+car inline) | Step size of the cockpit brake-bias adjustment. | 0.5 | 0.5 | 0.5 | 0.5 | 0.2 |
| `brakes.ebbFrontMultiplier` | brakes (+car inline) | Electronic brake-bias front multiplier (Giulia). | - | - | - | 1.1 | - |
| `brakes.controllerEbb.stages[*].upLimit / inputVar` | brakes (+car inline) | Electronic brake-bias controller: input variable and limits (Giulia). | - | - | - | 1 / 1.2 ; LoadSpreadLF / SlipAngleRearMAX / Brake | - |
| `brakes.frontBrakeCompounds[*].torqueK / rearBrakeCompounds[*].torqueK` | brakes (+car inline) | Brake torque coefficient of the brake compound per axle (Porsche). | - | - | - | - | 0.7 ; 0.85 (inline: 0.7) * |
| `drivetrain.differential_data.torque_bias_ratio_power` | drivetrain (+car inline) | Torque bias ratio under power of the physical diff model (besides the setup power / coast / preload). unverified | 2.3 | 4.1 | 4 | - | - |
| `drivetrain.differential_data.torque_bias_ratio_coast` | drivetrain (+car inline) | Torque bias ratio on coast. unverified | 0.5 | 4.1 | 4 | - | - |
| `drivetrain.differential_data.preload` | drivetrain (+car inline) | Differential preload torque in the drivetrain file (the setup preload default is covered). | 1 | 20 | - | 50 | 40 |
| `drivetrain.differential_data.power / coast` | drivetrain (+car inline) | Differential lock factors power / coast in the drivetrain file (setup defaults are covered). unverified | - | 0.03 ; 0.03 | - | 0.1 ; 0.25 | 0.3 ; 0.75 |
| `drivetrain.stiffness` | drivetrain (+car inline) | Driveline torsional stiffness (shock absorption, wheel hop, snap behaviour). | 400 | 800 | 400 | - | 600 |
| `drivetrain.damping_ratio` | drivetrain (+car inline) | Damping ratio of the driveline torsion model. | 0.4 | 0.8 | 0.3 | - | 10 |
| `drivetrain.max_torsion_deg` | drivetrain (+car inline) | Maximum driveline torsion angle in degrees. | 6 | - | 30 | - | - |
| `clutch.clutch_max_torque` | clutch (+car inline) | Maximum torque the clutch transmits before it slips (clutch kick, launch). | 1000 | 500 | 500 | 750 | 1000 |
| `clutch.autoclutch.min_rpms / max_rpms` | clutch (+car inline) | Engine speed band in which the auto clutch engages. | 1200 ; 2800 | 1300 ; 1800 | 1500 ; 2500 | 1600 ; 2000 | 2400 ; 3000 |
| `clutch.autoclutch.forcedOn` | clutch (+car inline) | Auto clutch forced on (cannot be switched off). unverified | true | - | - | true | true |
| `gearbox.gears[*].ratio (reverse)` | gearbox (+car inline) | Reverse gear ratio (forward gears 1-8 are covered). | -3.746 | -3.44 | -3.288 | -3.678 | -3.55 |
| `gearbox.autoshifter.gasCutoffTime` | gearbox (+car inline) | Throttle cut time during automatic shifts in seconds. | 0.26 | 0.08 | 0.3 | 0.26 | 0.05 |
| `gearbox.valid_shift_rpm_window` | gearbox (+car inline) | Engine speed window in which a shift is accepted. unverified | 1000 | 1200 | 800 | 6500 | 800 |
| `engine.maps[*].powerMult` | engine (+car inline) | Power multiplier of an engine map (map selection is a setup entry on the Porsche). | 1 | 1 | 0.98 (inline: 1) * | - | 0.87 |
| `engine.maps[*].throttling_factor` | engine (+car inline) | Throttle mapping factor of the engine map. unverified | 0.15 | - | 0.15 (inline: 0.05) * | - | 0.2 |
| `engine.maps[*].throttle_lag_up / throttle_lag_dn` | engine (+car inline) | Per-map throttle lag up / down (the engine-level lags are covered). | 0.98 ; 0.88 | - | - | - | - |
| `engine.startECUAssist.rpm_limiter` | engine (+car inline) | Engine speed held by the start (launch) assist. | 2850 | - | - | 5000 | - |
| `engine.turbos[*].lag_UP / lag_DN` | turbo / engine / car inline | Turbo spool-up / spool-down smoothing (turbo response). | - | 0.99 ; 0.996 | 0.995 / 0.988 (inline: 0.998 / 0.996) * ; 0.99 / 0.985 (inline: 0.996 / 0.994) * | 0.99 / 0.995 (inline: 0.99) * ; 0.99 | - |
| `engine.turbos[*].rpm_Ref` | turbo / engine / car inline | Engine speed at which the turbo reaches its reference boost. unverified | - | 1900 | 3000 / 5000 (inline: 1000 / 4500) * | 2250 | - |
| `engine.turbos[*].wastegate` | turbo / engine / car inline | Wastegate setting (Giulia; the GR86 engine file carries a turbo block although the car is naturally aspirated). unverified | - | 1.1 | - | 0.725 | - |
| `engine.turbos[*].gamma_Gas / gamma_Rpm` | turbo / engine / car inline | Boost response exponents versus throttle and rpm. unverified | - | 2 ; 2 | 0.7 (inline: 2) * ; 1 | 2.5 ; 2.5 | - |
| `electronics.TC.settings[*].maxSlipRatio / minSlipRatio` | car/electronics | Slip ratio window in which traction control intervenes (per TC level). | -1 / 0.305 ; -1 / 0.1 | 0.4 / 0.2 ; 0.15 / 0.1 | - | 0.6 / 0.4 ; 0.14 / 0.12 | 0.14..0.35 (6 distinct) ; 0.05..0.12 (9 distinct) |
| `electronics.TC.settings[*].oversteerGain` | car/electronics | Traction control reaction to oversteer per level. | 3 | 2 / 5 | - | 0.2 / 5.5 | 3.5..8 (9 distinct) |
| `electronics.TC.settings[*].slipAngleActivationDeg / refSlipAngleDeg` | car/electronics | Slip angle at which TC activates / reference slip angle (drift-relevant). | 10 ; 12 | 10 / 7 ; 15 / 12 | - | 10 / 7 ; 15 / 10 | 3.5..7.5 (8 distinct) ; 6.5..12 (8 distinct) |
| `electronics.TC.settings[*].engineCutLevel` | car/electronics | Engine torque cut applied by TC per level. | 3 | 1 | - | 2 / 0.25 | 1.5 / 1.25 / 1 / 0.75 |
| `electronics.ABS.settings[*].maxSlipRatio / minSlipRatio` | car/electronics | Slip ratio window in which ABS intervenes (per ABS level). | -1 / 0.12 ; -1 / 0.06 | -1 / 0.12 ; -1 / 0.06 | -1 / 0.112 ; -1 / 0.056 | -1 / 0.1 ; -1 / 0.0655 | -1..0.14 (10 distinct) ; -1..0.12 (11 distinct) |
| `electronics.ABS.settings[*].cutLevel` | car/electronics | Brake pressure cut applied by ABS per level. | 0.1 | 0.3 | 0.2 | 0.1 | 0.2 |
| `electronics.ESP.settings[*].oversteer_gain / understeer_gain` | car/electronics | Stability control correction gains (BMW, GR86, Giulia). | 1.5 ; 1.5 | 1 ; 3 / 1 | - | 0.5 / 1.5 ; 0.5 / 1.5 | - |
| `electronics.ESP.settings[*].max_slip_ratio` | car/electronics | Slip ratio limit of the stability control. | 0.1 | 0.11 / 0.3 / 0.8 | - | 0.19 / 0.1 | - |
| `electronics.EDL.maxspinpower / braketorquepower` | car/electronics | Electronic differential lock: allowed spin and brake torque under power (GR86, Giulia). | - | 0.8 ; 180 | - | 0.8 ; 200 | - |
| `performance_modes[*].electronics_settings.{abs ; esc ; tc1 ; tc2}` | car/performance_modes | Electronics levels of each performance mode (selectable driving-mode presets). | 1 ; 1 ; 1 ; - | 1 ; 1 ; 1 / 2 ; 1 | - | 1 ; 1 / 2 ; 1 / 2 ; - | - |
| `aero.wings[*].cl_gain` | wing (+car inline) | Lift (downforce) gain of each wing element. | -0.1 / -0.6 / 1.6 (inline: -0.1 / -0.6) * | 1 / -0.02 / -1.35 | 1 | 2 / 1 | 1 |
| `aero.wings[*].cd_gain` | wing (+car inline) | Drag gain of each wing element. | 1 | 1 | 1 | 1 | 1 |
| `aero.wings[*].span / chord` | wing (+car inline) | Wing element size (area). | 2.07 / 1.8 / 2.31 (inline: 2.07 / 1.8) * ; 1 / 0.5 | 1.8 / 1.99 ; 1.2 / 1 | 1.77 / 1 ; 1 | 2.31 ; 1 | 1 ; 1 |
| `aero.wings[*].angle` | wing (+car inline) | Wing angle of attack (looked up in the lutAOA curves). | 1 | 2 | - | 1 | - |
| `engine.throttleResponseCurve / maps[*].throttleResponseCurve (curve)` | engine (+car inline) | Throttle pedal to engine response curve (throttle feel). | bmw_m3_e46_coupe_throttle_response_1.curve | throttle.curve | throttle.curve | throttle.curve | throttle_2.curve (+2) |
| `clutch.autoclutch.upshiftProfile / downShiftProfile (curve)` | clutch (+car inline) | Auto-clutch engagement profiles for up and down shifts. | upShiftProfile.curve (+1) | upShiftProfile.curve (+1) | upShiftProfile.curve (+1) | - | - |
| `gearbox.autoblip.profile (curve)` | gearbox (+car inline) | Throttle blip profile on downshifts. | autoBlipProfile.curve | autoBlipProfile.curve | autoBlipProfile.curve | autoBlipProfile.curve | autoBlipProfile.curve |
| `wing lutAOA_CL / lutAOA_CD (curve)` | wing (+car inline) | Lift and drag versus angle of attack of each wing element. | wing_body_AOA_CL.curve (+7) | wing_body_AOA_CL.curve (+5) | wing_body_AOA_CL.curve (+4) | wing_body_AOA_CL.curve (+7) | wing_rear_front_AOA_CL.curve (+3) |

## Tyres

(Status after this analysis: the tuner now has a "Tyres" group with the main tyre values per axle and the thermal curve choice; the fields below without a setting are still not covered, and `.tyre` is mapped in `tools/car_json.py`.) Tyre physics lives in `.tyre` files (message `TyresCompoundData`, `schemas/TyresData.proto`). The decode below uses the schema with the relaxed wire walk of `decode_msg`; all four sample files decode and re-encode byte-exact (checked with `car_json.roundtrip`).

Which file the BMW uses. `data/ks_bmw_m3_e46_csl.car` names `frontTyreCompounds[0]` = `content\cars\common_phsx\tyres\road\road_235_35_19.tyre` and `rearTyreCompounds[0]` = `...\road\road_265_30_19.tyre`. `presets/tyres_e46csl.compatibletyres` offers two compounds: `TyreCompound_Supercar_Michelin_Cup_2` (`supercar_235_35_19.tyre` / `supercar_265_30_19.tyre`) and `TyreCompound_Road_Michelin` (the two road files). None of these files is in the extracted car folder (`base\content\cars\ks_bmw_m3_e46_csl` holds no `.tyre`, and no `common_phsx` folder exists next to it); they exist only in the game package `content.kspkg` under `content\cars\common_phsx\tyres\road|supercar\` (shared by all cars, 849 / 848 bytes each, extracted for this analysis). The other tested cars point to shared files too: GR86 `supercar_215_45_17`, RX-7 `road_235_45_17` / `road_255_40_17`, Giulia `supercar_265_30_20` / `supercar_285_30_20`, Porsche `racing_slicks\slick_325_680_18` / `slick_325_705_18`. A tyre file also names two curve files (`wear_*.curve`, `tcurve_*.curve`, one thermal performance curve per compound family) in the same shared folder.

Schema fields, all UNCOVERED (type `float` unless noted; the number after `/` is the field count):

- `TyresData` / 23: width, radius, rate, damping, angularInertia, rimRadius, radiusRaiseK, treadHeightMM, treadConsumptionK, mass, lateralFlexK, lateralFlexC, longitudinalFlexK, longitudinalFlexC, explosionTemperature, blanketTemperature, FlatSpotK, normalToFlexRatio, dampingMode (enum DampingMode), dampingThresholdSpeedMs, speedDampingFactor, deflectionDampingFactor, progressive_rate
- `TyresModelData` / 36: Dy0, Dx0, lsExpY, lsExpX, Fz0, friction_limit_angle, friction_limit_angle_load_gain, cfXmult, brakeDXMod, combinedFactor, gripSlipFactor, wearCurve (string), mzTweakMult, grainFactor, contactWearIMO, relaxationLengthY, relaxationLengthX, mzScale, mzTrailNdSlipReduction, mzTrailRemap, brushExponent, slip_ratio_limit, slip_ratio_limit_load_gain, use_sr_limit (bool), new_combined (bool), fx_shift_SA, fx_scale_SA, fy_shift_SR, fy_scale_SR, use_slip_falloff (bool), falloff_level, falloff_slope, falloff_shape, falloff_x_level, falloff_x_slope, falloff_x_shape
- `TyresCompoundData` / 13: name (string), shortName (string), tyreData (TyresData), modelData (TyresModelData), thermalData (TyresThermalPatchData), pressureData (TyresPressureData), camberData (TyresCamberData), speedSensitivity (TyresSpeedSensitivityData), rollingResistance (RollingResistanceData), grooveData (TyresGrooveData), pressure, init_data (TyreInitializerData), tyre_compound (enum PhysicsTyreCompound)
- `TyresThermalPatchData` / 25: verticalSpringK, verticalDampK, wearMult, grainGain, grainGamma, grainSlipAngleGain, grainSlipAngleGamma, grainSlipAngleThreshold, blisterGain, blisterGamma, practicalTempSource, brakeTransferFactor, thermalPerformanceCurve (string), contactIMO, TrefFrictionLimitAngle, frictionLimitAngleTSensitivity, density, specific_heat, surface_core_mass_ratio, cool_factor_rain, cool_factor, heat_partition_coeff, road_conduction, thermal_conductivity, rolling_factor
- `TyresCamberData` / 7: camberGain, camberVerticalKRangeDeg, camberVerticalKGain, dcamber0, dcamber1, dcamber0_x, dcamber1_x
- `TyresSpeedSensitivityData` / 15: ref_speed, muSpeedSensitivity, mu0T, muTSensitivity, TrefMuT, mu0T_x, ref_speed_x, muSpeedSensitivity_x, muTSensitivity_x, TrefMuT_x, use_master_curve (bool), t_glass, friction_master_curve (string), t_ref, t_shift_sens
- `TyresPressureData` / 10 (nested in `TyresCompoundData`): pressure_limit_angle_gain, rollingResistanceGain, rollingHeatGain, gainD, idealPressure, pressureReference, pressureSpringCurve (string), pressureSpringGain, curbPressureLossMult, curbPressureLossThreshold
- `RollingResistanceData` / 4 (nested in `TyresCompoundData`): rr0, rr1, rr_slip, rrWearMult
- `TyresGrooveData` / 3 (nested in `TyresCompoundData`): grooveFactor, grooveSAFactor, grooveSRFactor
- `TyreInitializerData` / 5 (nested in `TyresCompoundData`): width, aspect_ratio, diameter, load_index, pressure

Fields on the wire that the schema does not name (Road front 235/35R19, field number = value as float32; `speedSensitivity` #7 is a varint): tyreData ?19=9.60401, ?20=0.216261, ?21=15.1357, ?22=4, ?23=1, ?24=180, ?26=30; modelData ?11=0.96, ?12=0.96; thermalData ?4=0.05512, ?5=0.0503469, ?6=2.11121, ?7=0.02296, ?8=0.00321149, ?9=0.000336, ?10=0.002175, ?11=587.073, ?12=0.0005, ?13=0.0005, ?14=2, ?15=100, ?29=7, ?30=0.1; camberData ?6=15, ?7=8; speedSensitivity ?1=0.77, ?2=0.4, ?3=0.72, ?4=23, ?5=2.7, ?6=23, ?7=1. Their meaning is unknown.

Key values of the tyres the BMW can use (read from the game package; stock, front 235/35 R19 and rear 265/30 R19):

| Field | Road front | Road rear | Supercar front | Supercar rear |
|---|---|---|---|---|
| `tyreData.width` | 0.235 | 0.265 | 0.235 | 0.265 |
| `tyreData.radius` | 0.32355 | 0.3208 | 0.32355 | 0.3208 |
| `tyreData.rate` | 282100 | 322400 | 273000 | 312000 |
| `tyreData.damping` | 504.714 | 576.816 | 561.697 | 641.94 |
| `tyreData.mass` | 6 | 6 | 7 | 7 |
| `tyreData.treadHeightMM` | 8 | 8 | 7 | 7 |
| `tyreData.lateralFlexK` | 30000 | 30000 | 38000 | 38000 |
| `tyreData.longitudinalFlexK` | 18000 | 18000 | 20000 | 20000 |
| `tyreData.blanketTemperature` | 40 | 40 | 40 | 40 |
| `tyreData.explosionTemperature` | 450 | 450 | 450 | 450 |
| `modelData.Dy0` | 1.20783 | 1.22436 | 1.26635 | 1.28288 |
| `modelData.Dx0` | 1.25841 | 1.27407 | 1.31938 | 1.33495 |
| `modelData.Fz0` | 3930 | 4320 | 3930 | 4320 |
| `modelData.lsExpY` | 0.870015 | 0.875611 | 0.872016 | 0.877611 |
| `modelData.lsExpX` | 0.898015 | 0.903611 | 0.902015 | 0.907611 |
| `modelData.friction_limit_angle` | 8.11553 | 8.01075 | 8.02553 | 7.92075 |
| `modelData.friction_limit_angle_load_gain` | 0.0207 | 0.0207 | 0.0207 | 0.0207 |
| `modelData.combinedFactor` | 1.8 | 1.8 | 1.75 | 1.75 |
| `modelData.gripSlipFactor` | 0.78 | 0.78 | 0.77 | 0.77 |
| `modelData.brushExponent` | 2.9 | 2.9 | 2.85 | 2.85 |
| `modelData.relaxationLengthY` | 0.10051 | 0.10051 | 0.10051 | 0.10051 |
| `modelData.mzScale` | 0.12 | 0.12 | 0.12 | 0.12 |
| `camberData.camberGain` | 0.2 | 0.2 | 0.2 | 0.2 |
| `camberData.camberVerticalKRangeDeg` | 5 | 5 | 5 | 5 |
| `camberData.camberVerticalKGain` | -0.1 | -0.1 | -0.1 | -0.1 |
| `camberData.dcamber0` | 0.6 | 0.6 | 0.6 | 0.6 |
| `camberData.dcamber1` | -11 | -11 | -11 | -11 |
| `pressure` | 30 | 30 | 30 | 29 |
| `pressureData.idealPressure` | 31 | 31 | 30 | 30 |
| `pressureData.pressureReference` | 30 | 26 | 30 | 30 |
| `pressureData.pressureSpringGain` | 10010 | 11440 | 10010 | 11440 |
| `pressureData.rollingResistanceGain` | 1.2 | 1.2 | 1.2 | 1.2 |
| `speedSensitivity.mu0T` | 0.78 | 0.78 | 0.78 | 0.78 |
| `speedSensitivity.ref_speed` | 4.5 | 4.5 | 4.5 | 4.5 |
| `speedSensitivity.muSpeedSensitivity` | 0.78 | 0.78 | 0.78 | 0.78 |
| `speedSensitivity.muTSensitivity` | 0.025 | 0.025 | 0.025 | 0.025 |
| `speedSensitivity.TrefMuT` | 70 | 70 | 70 | 70 |
| `speedSensitivity.mu0T_x` | 0.68 | 0.68 | 0.7 | 0.7 |
| `speedSensitivity.muSpeedSensitivity_x` | 0.62 | 0.62 | 0.62 | 0.62 |
| `thermalData.verticalSpringK` | 40 | 40 | 40 | 40 |
| `thermalData.wearMult` | 0.2 | 0.2 | 0.2 | 0.2 |
| `thermalData.grainGain` | 0.27 | 0.27 | 0.47 | 0.47 |
| `thermalData.grainSlipAngleGain` | 0.265 | 0.265 | 0.565 | 0.565 |
| `thermalData.practicalTempSource` | 0.8 | 0.8 | 0.8 | 0.8 |
| `thermalData.cool_factor` | 1.4 | 1.4 | 1.4 | 1.4 |
| `thermalData.heat_partition_coeff` | 0.7 | 0.7 | 0.9 | 0.9 |
| `thermalData.thermal_conductivity` | 0.23 | 0.23 | 0.3 | 0.3 |
| `thermalData.TrefFrictionLimitAngle` | 75 | 75 | 75 | 75 |
| `thermalData.thermalPerformanceCurve` | tcurve_road.curve | tcurve_road.curve | tcurve_supercar.curve | tcurve_supercar.curve |
| `modelData.wearCurve` | wear_road.curve | wear_road.curve | wear_supercar.curve | wear_supercar.curve |
| `rollingResistance.rr0` | 18.9921 | 19.4366 | 18.9921 | 19.4366 |
| `rollingResistance.rr_slip` | 646 | 646 | 646 | 646 |
| `grooveData.grooveFactor` | 0.49 | 0.49 | 0.441 | 0.441 |
| `init_data.load_index` | 91 | 104 | 91 | 104 |
| `tyre_compound` | PhysicsTyreCompound_Road | PhysicsTyreCompound_Road | PhysicsTyreCompound_SuperCar | PhysicsTyreCompound_SuperCar |

Reading the names: `tyreData.width` is in metres (0.235 / 0.265), `init_data` holds the nominal size (width mm, aspect ratio, rim diameter inch, load index). By name only (unverified): Dy0 / Dx0 look like lateral / longitudinal peak friction coefficients, Fz0 like the reference load, `lsExp*` like load sensitivity exponents, `camberData` the camber response, `pressureData` and `pressure` the pressure model, `speedSensitivity` and `thermalData` the speed and temperature dependence of grip.

## Not curated (by section)

Uncovered scalar paths that are not in the table above, grouped by section. `{a,b}` = sibling leaves of the same parent, `{x,y,z}` = coordinates, `[*]` = any list index. Numbers in brackets = distinct uncovered paths in the section, of which not curated. Inline `.car` copies appear in their own `car/...` sections.

- **car/general** [14, 11 not curated]: general.{checkRules,efficiency,fuel,kgPerLiter,pickupFrontHeight,pickupRearHeight}; general.tankPosition.{y,z}; general.body_box_sizes.{x,y,z}
- **car/suspensions** [193, 40 not curated]: suspensions.{base_y_front,base_y_rear}; suspensions.coilover_front.bumpStopDown.{Gamma,Reference,damping,length}; suspensions.coilover_front.bumpStopUp.{Gamma,Reference,damping,length}; suspensions.coilover_front.collar_position; suspensions.coilover_front.damper.{cooling_surface,damper_lut_scale,heat_transfer_coef,max_stress_fatigue,min_stress_fatigue,nominal_force,thermal_capacity}; suspensions.coilover_rear.bumpStopDown.{Gamma,Reference,damping,length}; suspensions.coilover_rear.bumpStopUp.{Gamma,Reference,damping,length}; suspensions.coilover_rear.collar_position; suspensions.coilover_rear.damper.{cooling_surface,damper_lut_scale,heat_transfer_coef,max_stress_fatigue,min_stress_fatigue,nominal_force,thermal_capacity}; suspensions.damage.{debugLog,gain,maxDamage,minVelocity}; suspensions.suspension_geometry_front.basic_data.rimOffset; suspensions.suspension_geometry_rear.basic_data.rimOffset
- **car/drivetrain** [10, 2 not curated]: drivetrain.{non_linear_model,stiffness_mult}
- **car/engine** [40, 29 not curated]: engine.damage.{bovThreshold,rpmDamageK,turboBoostDamageK,turboBoostDamageThreshold}; engine.{fatigue_log10_a,ignitionTimeS,max_stress,min_stress,nominal_torque,overlapFreq,starterEngineTorque,turboBoostDamageK,turboBoostDamageThreshold}; engine.maps[*].{consumptionMult,throttleGainKRPM,throttleRefRPMMove,type}; engine.startECUAssist.{clutch_gain,gain,gas_gain,limiter_cycles,rpmRange,slip_ratio_target,speedRangeKHM,use_clutch}; engine.turboControllers[*].stages[*].{combinatorMode,filterGain,inputVar,upLimit}
- **car/brakes** [46, 39 not curated]: brakes.controllerEbb.stages[*].{combinatorMode,filterGain}; brakes.frontBrakeCompounds[*].{areaReductionMM,conductionThickness,coolSpeedFactor,coolTransfer,coreThermalCapacity,diskConsumptionRate,diskThickness,emissivity,gammaCorrectionMM,muReductionMM,padConsumptionRate,padThickness,perfDecreaseMM,rainCoolFactor,surface,tReferenceWear,thermalCapacity,thermalConductivity}; brakes.hasCockpitBias; brakes.rearBrakeCompounds[*].{areaReductionMM,conductionThickness,coolSpeedFactor,coolTransfer,coreThermalCapacity,diskConsumptionRate,diskThickness,emissivity,gammaCorrectionMM,muReductionMM,padConsumptionRate,padThickness,perfDecreaseMM,rainCoolFactor,surface,tReferenceWear,thermalCapacity,thermalConductivity}
- **car/steeringSystem** [5, 0 not curated]: all curated
- **car/electronics** [41, 27 not curated]: electronics.ABS.{channels,frequency,minSpeedKmh}; electronics.ABS.settings[*].{maxTorqueVariation,refSlipAngledeg}; electronics.EDL.{active,braketorquecoast,deadzonecoast,deadzonepower,maxspincoast}; electronics.ESP.{frequencyHz,minSpeedKmh}; electronics.ESP.settings[*].{brake_perc,brake_perc_activation,dead_zone,filter_gain,gain,min_steer_gain,steer_gain,steer_gain_max_speed}; electronics.TC.{frequencyHz,gearChangeTime,hasTC2,maxCutLevel,minCutLevel,minSpeedKmh}; electronics.TC.settings[*].angularACCgain
- **car/controls** [4, 1 not curated]: controls.ffMult
- **car/aero** [22, 17 not curated]: aero.downforces[*].{cd_gain,cl_gain,drag_per_cool_transfer}; aero.{slip_gain_mult,speed_factor_mult}; aero.wings[*].{damage_CD[*],damage_CL[*],yaw_gain}; aero.wings[*].position.{y,z}; aero.wings[*].wing_controllers[*].{combinator_mode,filter,input,up_limit}; aero.downforces[*].position.{x,y,z}
- **car/gearbox** [15, 12 not curated]: gearbox.autoblip.isElectronic; gearbox.autoshifter.slipThreshold; gearbox.{controls_window_gain,damageRpmWindow,gas_cut_off_level,gear_count,gearbox_inertia,has_dual_clutch,is_shifter_supported}; gearbox.downshift_protection.{isActive,lockN,overrev}
- **car/clutch** [5, 1 not curated]: clutch.clutch_inertia
- **car/performance_modes** [4, 0 not curated]: all curated
- **car/bodyMeshOffset** [6, 6 not curated]: bodyMeshOffset.position.{y,z}; bodyMeshOffset.rotation.x; bodyMeshOffset.scale.{x,y,z}
- **car/boxColliders** [5, 5 not curated]: boxColliders[*].center.{y,z}; boxColliders[*].size.{x,y,z}
- **engine** [42, 31 not curated]: {audio_throttle_limiter_tau_ms,bovThreshold,fatigue_log10_a,ignitionTimeS,max_stress,min_stress,nominal_torque,overlapFreq,starterEngineTorque,turboBoostDamageK,turboBoostDamageThreshold}; damage.{bovThreshold,rpmDamageK,turboBoostDamageK,turboBoostDamageThreshold}; maps[*].{consumptionMult,throttleGainKRPM,throttleRefRPMMove,type}; startECUAssist.{clutch_gain,gain,gas_gain,limiter_cycles,rpmRange,slip_ratio_target,speedRangeKHM,use_clutch}; turboControllers[*].stages[*].{combinatorMode,filterGain,inputVar,upLimit}
- **gearbox** [15, 12 not curated]: autoblip.isElectronic; autoshifter.slipThreshold; {controls_window_gain,damageRpmWindow,gas_cut_off_level,gear_count,gearbox_inertia,has_dual_clutch,is_shifter_supported}; downshift_protection.{isActive,lockN,overrev}
- **drivetrain** [10, 2 not curated]: {non_linear_model,stiffness_mult}
- **clutch** [5, 1 not curated]: clutch_inertia
- **brakes** [46, 39 not curated]: controllerEbb.stages[*].{combinatorMode,filterGain}; frontBrakeCompounds[*].{areaReductionMM,conductionThickness,coolSpeedFactor,coolTransfer,coreThermalCapacity,diskConsumptionRate,diskThickness,emissivity,gammaCorrectionMM,muReductionMM,padConsumptionRate,padThickness,perfDecreaseMM,rainCoolFactor,surface,tReferenceWear,thermalCapacity,thermalConductivity}; hasCockpitBias; rearBrakeCompounds[*].{areaReductionMM,conductionThickness,coolSpeedFactor,coolTransfer,coreThermalCapacity,diskConsumptionRate,diskThickness,emissivity,gammaCorrectionMM,muReductionMM,padConsumptionRate,padThickness,perfDecreaseMM,rainCoolFactor,surface,tReferenceWear,thermalCapacity,thermalConductivity}
- **setup** [19, 3 not curated]: alignments[*].{static_camber,toe_out_linear}; electronics.telemetry_laps_to_record
- **limits** [126, 126 not curated]: aero.collar_positions[*].{max,min,step}; aero.front_target_height.{fractional_digits,is_modifiable,max,min,step}; aero.rear_target_height.{fractional_digits,is_modifiable,max,min,step}; aero.rear_wing_angle.curve.points[*].{t,value}; aero.rear_wing_angle.{is_modifiable,max,min,step}; alignments[*].camber.{is_modifiable,step}; alignments[*].caster.{hide_value,is_modifiable,is_negative,max,min,step}; alignments[*].compound.{is_modifiable,max,step}; alignments[*].pressure.{is_modifiable,step}; alignments[*].static_camber.{max,min,step}; alignments[*].toe.{is_modifiable,step}; alignments[*].toe_out_linear.{max,min,step}; dampers[*].fast_bump.{max,min,step}; dampers[*].fast_rebound.{max,min,step}; dampers[*].slow_bump.{hide_value,is_modifiable,max,min,step}; dampers[*].slow_rebound.{hide_value,is_modifiable,max,min,step}; electronics.abs.{is_modifiable,max,min,step}; electronics.engine_map.{is_modifiable,max,min,step}; electronics.esc.{is_modifiable,max,step}; electronics.tc1.{is_modifiable,max,step}; electronics.tc2.{is_modifiable,max,step}; electronics.telemetry_laps_to_record.{is_modifiable,max,step}; fuel_strategy.fuel.{is_modifiable,max,min,step}; mechanical_balance.arbs[*].curve.points[*].{t,value}; mechanical_balance.arbs[*].{hide_value,is_modifiable,step}; mechanical_balance.brakes.front_bias.{is_modifiable,step}; mechanical_balance.brakes.torque_multiplier.{is_modifiable,max,min,step}; mechanical_balance.differential.coast.{min,step}; mechanical_balance.differential.power.{min,step}; mechanical_balance.differential.preload.{is_modifiable,min,step}; mechanical_balance.steer_ratio.{is_modifiable,step}; suspensions[*].bump_stop_down.range.{max,min,step}; suspensions[*].bump_stop_down.rate.{max,min,step}; suspensions[*].bump_stop_up.range.{hide_value,is_modifiable,max,min,step}; suspensions[*].bump_stop_up.rate.{is_modifiable,max,min,step}; suspensions[*].helper_range.{max,min,step}; suspensions[*].helper_rate.{max,min,step}; suspensions[*].wheel_rate.curve.points[*].{t,value}; suspensions[*].wheel_rate.{is_modifiable,step}; use_single_compound
- **coilover** [27, 16 not curated]: bumpStopDown.{Gamma,Reference,damping,length}; bumpStopUp.{Gamma,Reference,damping,length}; collar_position; damper.{cooling_surface,damper_lut_scale,heat_transfer_coef,max_stress_fatigue,min_stress_fatigue,nominal_force,thermal_capacity}
- **suspension** [99, 1 not curated]: basic_data.rimOffset
- **wing** [14, 9 not curated]: {damage_CD[*],damage_CL[*],yaw_gain}; position.{y,z}; wing_controllers[*].{combinator_mode,filter,input,up_limit}
- **turbo** [6, 0 not curated]: all curated

Curve references not curated (file names differ per car, so only the field is listed): brakes `controllerEbb.stages[*].lut` (Giulia 3); car/aero `aero.wings[*].wing_controllers[*].lut` (Giulia 1); car/brakes `brakes.controllerEbb.stages[*].lut` (Giulia 3); car/brakes `brakes.frontBrakeCompounds[*].perfCurve` (Porsche 1); car/brakes `brakes.rearBrakeCompounds[*].perfCurve` (Porsche 1); car/engine `engine.turboControllers[*].stages[*].lut` (RX-7 1, Giulia 2); car/steeringSystem `steeringSystem.fourWSControllers.stages[*].lut` (RX-7 1); engine `turboControllers[*].stages[*].lut` (RX-7 1, Giulia 2); limits `aero.rear_wing_angle.lut` (RX-7 1); limits `mechanical_balance.arbs[*].lut` (RX-7 2, Porsche 2); limits `suspensions[*].wheel_rate.lut` (RX-7 4); wing `wing_controllers[*].lut` (Giulia 1).

Covered curve references (power curve scale, coast curve scale): `engine.powerCurve` and `engine.coastCurve` in the engine file and in the inline `.car` copy.

