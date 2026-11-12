# Hina's Drift Club 1.4 BMW M3 E46 versus the current stock BMW M3 E46 CSL

Compared by name with `tools/car_json.py` (named schema fields; unnamed wire fields compared as raw numbers). HDC side: `hdc_bmw_e46_01` from `hinas_drift_club_e46_v1.4.kspkg` (git history commit 52b2eea, extracted to scratch only, nothing copied into the repository). Stock side: the real game extraction `ks_bmw_m3_e46_csl` (current game version). Strings (names, paths, display text) and cosmetic fields are ignored except where a path decides what is used. Ratio = HDC / stock, delta = HDC - stock.

## The 60 most important differences

| # | Area | Item | Stock (game) | HDC | Delta / ratio |
|---|---|---|---|---|---|
| 1 | Engine | `_power_1` torque curve, all 22 points (peak Nm at 5000 rpm) | 360.0 | 377.9 | x1.0497 at every point (362 -> 380 PS peak) |
| 2 | Engine | coast curve point 1100 rpm | -10 | -8 | x0.8 |
| 3 | Engine | coast curve point 9000 rpm | -89 | -71.2 | x0.8 |
| 4 | Engine | `engine.damage.rpmDamageThreshold` | 7700 | 8400 | +700 (x1.091) |
| 5 | Gearbox | `final_ratio` | 3.62 | 3.91 | +0.29 (x1.08) |
| 6 | Gearbox | `gears[2].ratio` (gear 1) | 4.227 | 3.5 | -0.727 (x0.828) |
| 7 | Gearbox | `gears[3].ratio` (gear 2) | 2.528 | 2.1 | -0.428 (x0.8307) |
| 8 | Driveline | `drivetrain.differential_data.preload` | 1 | 10 | +9 (x10) |
| 9 | Driveline | `drivetrain.differential_data.torque_bias_ratio_coast` | 0.5 | 3 | +2.5 (x6) |
| 10 | Driveline | `drivetrain.differential_data.torque_bias_ratio_power` | 2.3 | 2.5 | +0.2 (x1.087) |
| 11 | Setup | diff power default | 0.3 | 0.85 | +0.55 (x2.833) |
| 12 | Setup | diff coast default | 0.1 | 0.7 | +0.6 (x7) |
| 13 | Limits | diff power / coast max (min absent in stock) | 0.1 / 0.1 | 1.0 / 0.85 | min 0.7 / 0.55 added |
| 14 | Setup | steer_ratio | 14.5 | 14 | -0.5 (x0.9655) (limits fix it at 14..14) |
| 15 | Setup | spring wheel_rate front | 80000 | 54000 | -26000 (x0.675) |
| 16 | Setup | spring wheel_rate rear | 65000 | 55000 | -10000 (x0.8462) |
| 17 | Dampers | front slow_bump (setup / coilover file) | 15000 / 5500 | 3400 / 3400 | setup x0.227, coilover x0.618 |
| 18 | Dampers | front fast_bump (setup / coilover file) | 3500 / 1500 | 1700 / 1700 | setup x0.486, coilover x1.133 |
| 19 | Dampers | front slow_rebound (setup / coilover file) | 18000 / 7500 | 9200 / 9200 | setup x0.511, coilover x1.227 |
| 20 | Dampers | front fast_rebound (setup / coilover file) | 5000 / 4750 | 4600 / 4600 | setup x0.920, coilover x0.968 |
| 21 | Dampers | rear slow_bump (setup / coilover file) | 14000 / 12000 | 4800 / 4800 | setup x0.343, coilover x0.400 |
| 22 | Dampers | rear fast_bump (setup / coilover file) | 3500 / 250 | 1300 / 1300 | setup x0.371, coilover x5.200 |
| 23 | Dampers | rear slow_rebound (setup / coilover file) | 17000 / 16000 | 5700 / 5700 | setup x0.335, coilover x0.356 |
| 24 | Dampers | rear fast_rebound (setup / coilover file) | 5000 / 1000 | 3900 / 3900 | setup x0.780, coilover x3.900 |
| 25 | Setup | arbs[0] front | 70000 | 36000 | -34000 (x0.5143) (`.car` arbFront.stiffness: absent -> 36000) |
| 26 | Setup | arbs[1] rear | 50000 | 6000 | -44000 (x0.12) (`.car` arbRear.stiffness: absent -> 6000) |
| 27 | Setup | camber front | -2 | -3.5 | -1.5 (x1.75) |
| 28 | Setup | camber rear | -1.5 | -0.5 | +1 (x0.3333) |
| 29 | Setup | toe front | -0.01 | (absent) | +0.01 (x0) [absent = 0] |
| 30 | Setup | toe rear | 0.15 | 0.1 | -0.05 (x0.6667) |
| 31 | Setup | tyre pressure front (setup) | 27 | 28 | +1 (x1.037) |
| 32 | Setup | tyre pressure rear (setup) | 27 | 23 | -4 (x0.8519) |
| 33 | Setup | ride height target front | 116 | 130 | +14 (x1.121) |
| 34 | Setup | ride height target rear | 118 | 135 | +17 (x1.144) |
| 35 | Coilover | springRate front (physical) | 55000 | 54000 | -1000 (x0.9818) |
| 36 | Coilover | springRate rear (physical) | 50000 | 55000 | +5000 (x1.1) |
| 37 | Setup | bump_stop_down.rate front / rear | 200 / 150 | 500 / 500 | x2.5 / x3.33 |
| 38 | Limits | camber window front / rear | -2.5..-1.0 / -2.5..-1.0 | -4..-3 / -1..0 | 1 degree wide |
| 39 | Limits | tyre pressure window front / rear | 20..40 / 20..40 | 25..31 / 21..27 | 6 psi wide |
| 40 | Limits | wheel_rate window front / rear | 5000..80000 / 5000..80000 | 48600..59400 / 49500..60500 | about +-10 percent of the default |
| 41 | Limits | steer_ratio window | 9..16 | 14..14 | fixed, not modifiable |
| 42 | Limits | damper window front slow_bump (others alike) | 1000..10000 | 2890..3910 | +-15 percent of the default (fast channels +-10) |
| 43 | Controls | `controls.steer_lock` | 540 | 450 | -90 (x0.8333) |
| 44 | Controls | `controls.linearSteerRodRatio` | 0.0017 | 0.0025 | +0.0008 (x1.471) (HDC `cardata.car`: 0.0026) |
| 45 | Electronics | performance mode tc1 / tc2 / esc | 1 / 0 / 0 (SPORT+) | 0 / 0 / 0 (HDC Drift) | TC off; stock mode NORMAL (esc 1) removed |
| 46 | Electronics | setup `electronics.tc1` | 1 | (absent) | absent = 0 |
| 47 | Geometry | front strut inline hard points in `.car` (carSteer.z / tyreSteer.x / tyreSteer.z) | 0.07571 / 0.13 / 0.08323 | 0.12571 / 0.035 / 0.13323 | probable version drift (see end) |
| 48 | Tyres | tyre compound and files | Road (road_235_35_19 / road_265_30_19) | SuperCar-based `hdc_*` files | see Tyres |
| 49 | Tyres | front modelData.Dy0 | 1.20783 | 1.35343 | +0.1456 (x1.121) |
| 50 | Tyres | front modelData.Dx0 | 1.25841 | 1.326 | +0.0675864 (x1.054) |
| 51 | Tyres | rear modelData.Dy0 | 1.22436 | 1.19931 | -0.0250519 (x0.9795) |
| 52 | Tyres | rear modelData.Dx0 | 1.27407 | 1.2659 | -0.0081686 (x0.9936) |
| 53 | Tyres | modelData.Fz0 front / rear | 3930 / 4320 | 3720 / 3720 | x0.947 / x0.861 |
| 54 | Tyres | modelData.friction_limit_angle front / rear | 8.1155 / 8.0108 | 8.4182 / 8.35 |  |
| 55 | Tyres | pressure (tyre file) front / rear | 30 / 30 | 28 / 24 |  |
| 56 | Tyres | tyreData.lateralFlexK / longitudinalFlexK (both axles) | 30000 / 18000 | 38000 / 20000 | x1.27 / x1.11 |
| 57 | Tyres | thermalData.grainGain = grainGamma / grainSlipAngleGain | 0.27 / 0.265 | 0.47 / 0.565 | x1.74 / x2.13 |
| 58 | Tyres | thermalData.heat_partition_coeff front / rear | 0.7 / 0.7 | 0.9 / 0.85 |  |
| 59 | Tyres | tyreData.rate front / rear | 282100 / 322400 | 273000 / 312000 | x0.968 |
| 60 | Tyres | thermal performance curve | tcurve_road (plateau 31.9-70 deg) | = supercar curve (plateau 60-95 deg); rear slightly higher above 98 deg |  |

## Files compared (matched by role through each `.car` manifest)

| Role | Stock (game) file | HDC file | Bytes identical | Leaves stock / HDC | Differing |
|---|---|---|---|---|---|
| car | `data/ks_bmw_m3_e46_csl.car` | `data/hdc_bmw_e46_01.car` | no | 304 / 309 | 36 |
| engine | `data/ks_bmw_m3_e46_engine_1.carengine` | `same name` | no | 31 / 31 | 1 |
| gearbox | `data/ks_bmw_m3_e46_1.gearbox` | `same name` | no | 23 / 23 | 3 |
| drivetrain | `data/ks_bmw_m3_e46_1.drivetrain` | `same name` | no | 22 / 25 | 6 |
| clutch | `data/ks_bmw_m3_e46_1.clutch` | `same name` | no | 5 / 5 | 0 |
| brakes | `data/ks_bmw_m3_e46_1.brakesystem` | `same name` | yes | 4 / 4 | 0 |
| setup | `data/setup/ks_bmw_m3_e46_stock_performance_pack.carsetup` | `data/setup/hdc_bmw_e46_01.carsetup` | no | 75 / 72 | 66 |
| limits | `data/setup/limits_m3_e46.carsetuplimits` | `same name` | no | 250 / 343 | 232 |
| coilover_front | `data/ks_bmw_m3_e46_front_1.coilover` | `same name` | no | 20 / 20 | 5 |
| coilover_rear | `data/ks_bmw_m3_e46_rear_1.coilover` | `same name` | no | 20 / 20 | 5 |
| suspension_front | `data/ks_bmw_m3_e46_front_sus_1.suspension` | `same name` | yes | 27 / 27 | 0 |
| suspension_rear | `data/ks_bmw_m3_e46_rear_sus_m2.suspension` | `same name` | yes | 35 / 35 | 0 |
| wing0 | `data/wings/ks_bmw_m3_e460.wing` | `same name` | no | 13 / 13 | 0 |
| wing1 | `data/wings/ks_bmw_m3_e461.wing` | `same name` | no | 14 / 14 | 0 |
| wing2 | `data/wings/ks_bmw_m3_e462.wing` | `same name` | no | 14 / 14 | 0 |
| wing3 | `data/wings/ks_bmw_m3_e463.wing` | `same name` | yes | 15 / 15 | 0 |

Other facts. (1) The HDC package has two `.car` files, `data/cardata.car` and `data/hdc_bmw_e46_01.car`; both decode as CarData, point to the same files, and differ in one field only: `controls.linearSteerRodRatio` 0.0026 in `cardata.car`, 0.0025 in `hdc_bmw_e46_01.car` (this report uses `hdc_bmw_e46_01.car`; which one the game reads is unknown). (2) All HDC paths point to its own folder `content\cars\hdc_bmw_e46_01\...` (same file names as the stock car, `ks_bmw_m3_e46_*`), the stock paths to `ks_bmw_m3_e46_csl`; car-id differences are ignored. (3) Compared numeric/bool/enum leaves over the 16 file pairs: 976 (identical 622, differing 244, present only in stock 6, present only in HDC 104). Curves: 23 curve files exist in both packages (21 identical, 2 differ: `bmw_m3_e46_coupe_engine_power_1.curve`, `ks_bmw_m3_e46_engine_coast_1.curve`).

## Engine / power curve

Curve files. Stock engine (`ks_bmw_m3_e46_engine_1.carengine`) uses `bmw_m3_e46_coupe_engine_power_1.curve`; HDC's engine file uses the same file name inside its own folder. The unreferenced `bmw_m3_e46_coupe_engine_power.curve` exists in both packages and is byte-identical there. Curve values are torque in Nm (point `t` = rpm); power derived as torque x rpm / 9549.3.

Three-way comparison of the power curve:

| | A: current stock `_power_1` (game) | B: HDC `_power.curve` (older Kunos file, identical to the game's `_power.curve`) | C: HDC `_power_1` (tuned, used by HDC) | C / A |
|---|---|---|---|---|
| Peak torque | 360.0 Nm at 5000 rpm | 368.0 Nm at 5000 rpm | 377.9 Nm at 5000 rpm | x1.0497 |
| Torque at 2000 rpm | 311.0 Nm | 232.0 Nm | 326.4 Nm | x1.0497 |
| Torque at 4000 rpm | 351.0 Nm | 351.0 Nm | 368.4 Nm | x1.0497 |
| Torque at 6000 rpm | 357.0 Nm | 358.0 Nm | 374.7 Nm | x1.0497 |
| Torque at 8000 rpm | 318.0 Nm | 314.0 Nm | 333.8 Nm | x1.0497 |
| Peak power (from curve) | 266.4 kW (362 PS) at 8000 rpm | 263.1 kW (358 PS) at 7500 rpm | 279.6 kW (380 PS) at 8000 rpm | x1.0497 |
| Points / last rpm | 22 / 8500 | 20 / 8500 | 22 / 8500 | |
| Game stock `_power.curve` vs B | identical (all 20 points) | | | |

Point by point, C versus A: the 22 points have identical rpm positions and the value ratio is 1.04966 at every point with a nonzero value (min 1.04966, max 1.04966), i.e. HDC's tuned curve is the current stock `_power_1` multiplied by a constant factor of about 1.0497 (all points, including the 0.128 value at rpm -1000).

| rpm | A: stock `_power_1` | C: HDC `_power_1` | C / A | B: HDC `_power.curve` |
|---|---|---|---|---|
| -1000 | 0.13 | 0.13 | x1.0497 | - |
| 500 | 0.00 | 0.00 | - | - |
| 1000 | 203.00 | 213.08 | x1.0497 | 155.0 |
| 1500 | 244.00 | 256.12 | x1.0497 | 206.0 |
| 1711.6 | 295.93 | 310.63 | x1.0497 | 217.0 |
| 2000 | 311.00 | 326.44 | x1.0497 | 232.0 |
| 2154.11 | 296.70 | 311.43 | x1.0497 | 243.7 |
| 2276.51 | 273.70 | 287.29 | x1.0497 | 252.9 |
| 2500 | 277.00 | 290.76 | x1.0497 | 269.0 |
| 2750 | 305.00 | 320.15 | x1.0497 | 286.0 |
| 3000 | 321.00 | 336.94 | x1.0497 | 302.0 |
| 3500 | 328.00 | 344.29 | x1.0497 | 329.0 |
| 4000 | 351.00 | 368.43 | x1.0497 | 351.0 |
| 4500 | 359.00 | 376.83 | x1.0497 | 365.0 |
| 5000 | 360.00 | 377.88 | x1.0497 | 368.0 |
| 5500 | 359.00 | 376.83 | x1.0497 | 361.0 |
| 6000 | 357.00 | 374.73 | x1.0497 | 358.0 |
| 6500 | 352.00 | 369.48 | x1.0497 | 355.0 |
| 7000 | 338.00 | 354.79 | x1.0497 | 349.0 |
| 7500 | 332.00 | 348.49 | x1.0497 | 335.0 |
| 8000 | 318.00 | 333.79 | x1.0497 | 314.0 |
| 8500 | 250.00 | 262.42 | x1.0497 | 250.0 |

Coast (engine braking) curve `ks_bmw_m3_e46_engine_coast_1.curve`: 7 points; differing points:

| rpm | Stock (game) | HDC | Delta / ratio |
|---|---|---|---|
| 1100 | -10.0 | -8.0 | +2 (x0.8) |
| 9000 | -89.0 | -71.2 | +17.8 (x0.8) |

Throttle response curves (`bmw_m3_e46_coupe_throttle_response.curve`, `_1.curve`): identical in both. Engine fields that differ:

| Path | Stock (game) | HDC | Delta / ratio |
|---|---|---|---|
| `damage.rpmDamageThreshold` | 7700 | 8400 | +700 (x1.091) |

The same difference appears in the inline copy `car: engine.damage.rpmDamageThreshold` (7700 vs 8400). All other engine fields are identical (see the identical list).

## Gearbox / final drive

| Path | Stock (game) | HDC | Delta / ratio |
|---|---|---|---|
| `final_ratio` | 3.62 | 3.91 | +0.29 (x1.08) |
| `gears[2].ratio (gear 1)` | 4.227 | 3.5 | -0.727 (x0.828) |
| `gears[3].ratio (gear 2)` | 2.528 | 2.1 | -0.428 (x0.8307) |

Same values in the inline copy `car: gearbox.final_ratio / gears[2] / gears[3]`. Gears 3-6 (1.669, 1.226, 1.0, 0.828), reverse -3.746, shift times and autoshifter fields are identical. Gear 1 / 2 ratio ratios: gear 1 x0.8280, gear 2 x0.8307; overall first-gear ratio (gear 1 x final): stock 15.302, HDC 13.685; gear 2: stock 9.151, HDC 8.211.

## Drivetrain / differential / clutch

| Path | Stock (game) | HDC | Delta / ratio |
|---|---|---|---|
| `differential_data.preload` | 1 | 10 | +9 (x10) |
| `differential_data.torque_bias_ratio_coast` | 0.5 | 3 | +2.5 (x6) |
| `differential_data.torque_bias_ratio_power` | 2.3 | 2.5 | +0.2 (x1.087) |
| `differential_data.coast` | (absent) | 0.7 | +0.7 [absent = 0] |
| `differential_data.power` | (absent) | 0.85 | +0.85 [absent = 0] |
| `differential_data.type` | (absent) | LSD | - |

`differential_data.type` is written explicitly as `LSD` in HDC and absent in stock; LSD is the enum default (0), so no change. `differential_data.power` / `coast` exist only in HDC (stock: absent = 0). Clutch file: no difference in any field (clutch_max_torque 1000, clutch_inertia 0.13, autoclutch 1200..2800 rpm unchanged). The same drivetrain differences appear in the inline copy of the `.car`.

## Brakes

No difference: `ks_bmw_m3_e46_1.brakesystem` is byte-identical (biasStep 0.5, frontBias 68, handBrakeTorque 1100, totalTorque 3700); the inline `.car` copy is identical too. HDC did not change the brake balance default either (setup front_bias 63, same as stock); only the setup limits restrict it (front_bias min 61 / max 65 instead of max 100, see Setup limits).

## Setup defaults (HDC `hdc_bmw_e46_01.carsetup` versus stock `ks_bmw_m3_e46_stock_performance_pack.carsetup`)

Index order in the lists: suspensions / dampers / alignments [0,1] = front left / right, [2,3] = rear left / right; arbs [0] front, [1] rear. `static_camber` and `toe_out_linear` in the setup are derived values stored with the camber / toe settings.

| Path | Stock (game) | HDC | Delta / ratio |
|---|---|---|---|
| `mechanical_balance.arbs[0]` | 70000 | 36000 | -34000 (x0.5143) |
| `mechanical_balance.arbs[1]` | 50000 | 6000 | -44000 (x0.12) |
| `mechanical_balance.differential.coast` | 0.1 | 0.7 | +0.6 (x7) |
| `mechanical_balance.differential.power` | 0.3 | 0.85 | +0.55 (x2.833) |
| `mechanical_balance.steer_ratio` | 14.5 | 14 | -0.5 (x0.9655) |
| `suspensions[0,1].bump_stop_down.range` | 0.03563 | 0.0556319 | +0.0200019 (x1.561) |
| `suspensions[0,1].bump_stop_down.rate` | 200 | 500 | +300 (x2.5) |
| `suspensions[0,1].bump_stop_up.range` | -0.00563 | 0.0193681 | +0.0249981 (x-3.44) |
| `suspensions[0,1].bump_stop_up.rate` | 100 | 80 | -20 (x0.8) |
| `suspensions[0,1].wheel_rate` | 80000 | 54000 | -26000 (x0.675) |
| `suspensions[2,3].bump_stop_down.range` | -0.00461 | 0.0153905 | +0.0200005 (x-3.339) |
| `suspensions[2,3].bump_stop_down.rate` | 150 | 500 | +350 (x3.333) |
| `suspensions[2,3].bump_stop_up.range` | 0.04461 | 0.0746095 | +0.0299995 (x1.672) |
| `suspensions[2,3].wheel_rate` | 65000 | 55000 | -10000 (x0.8462) |
| `dampers[0,1].fast_bump` | 3500 | 1700 | -1800 (x0.4857) |
| `dampers[0,1].fast_rebound` | 5000 | 4600 | -400 (x0.92) |
| `dampers[0,1].slow_bump` | 15000 | 3400 | -11600 (x0.2267) |
| `dampers[0,1].slow_rebound` | 18000 | 9200 | -8800 (x0.5111) |
| `dampers[2,3].fast_bump` | 3500 | 1300 | -2200 (x0.3714) |
| `dampers[2,3].fast_rebound` | 5000 | 3900 | -1100 (x0.78) |
| `dampers[2,3].slow_bump` | 14000 | 4800 | -9200 (x0.3429) |
| `dampers[2,3].slow_rebound` | 17000 | 5700 | -11300 (x0.3353) |
| `alignments[0,1].camber` | -2 | -3.5 | -1.5 (x1.75) |
| `alignments[0,1].pressure` | 27 | 28 | +1 (x1.037) |
| `alignments[0,1].toe` | -0.01 | (absent) | +0.01 (x0) [absent = 0] |
| `alignments[0].static_camber` | -2.50722 | -4.41646 | -1.90924 (x1.761) |
| `alignments[0].toe_out_linear` | -0.000186942 | -0.000336083 | -0.000149141 (x1.798) |
| `alignments[1].static_camber` | -2.50712 | -4.41613 | -1.90901 (x1.761) |
| `alignments[1].toe_out_linear` | -0.000185825 | -0.000337018 | -0.000151192 (x1.814) |
| `alignments[2,3].camber` | -1.5 | -0.5 | +1 (x0.3333) |
| `alignments[2,3].pressure` | 27 | 23 | -4 (x0.8519) |
| `alignments[2,3].toe` | 0.15 | 0.1 | -0.05 (x0.6667) |
| `alignments[2].static_camber` | -1.03327 | -0.39526 | +0.638014 (x0.3825) |
| `alignments[2].toe_out_linear` | -0.000518924 | -0.000297485 | +0.000221439 (x0.5733) |
| `alignments[3].static_camber` | -1.03359 | -0.395079 | +0.63851 (x0.3822) |
| `alignments[3].toe_out_linear` | -0.0005189 | -0.000297457 | +0.000221443 (x0.5732) |
| `aero.collar_positions_mm[0]` | 68.1212 | 108.779 | +40.658 (x1.597) |
| `aero.collar_positions_mm[1]` | 68.1221 | 108.777 | +40.6553 (x1.597) |
| `aero.collar_positions_mm[2]` | 25.9178 | 53.5709 | +27.6532 (x2.067) |
| `aero.collar_positions_mm[3]` | 25.9174 | 53.5709 | +27.6536 (x2.067) |
| `aero.front_target_height` | 116 | 130 | +14 (x1.121) |
| `aero.rear_target_height` | 118 | 135 | +17 (x1.144) |
| `electronics.tc1` | 1 | (absent) | -1 (x0) [absent = 0] |

The other stock setup in the game, `data/setup/bak/ks_bmw_m3_e46_stock_sport.carsetup`, is not referenced by the car (older Kunos setup); it differs from the stock performance pack too (arbs 42000 / 18000, wheel_rate 60000 / 55000, front bias 74, steer ratio 14.6, diff 0.09 / 0.04 / 1.0). HDC values do not match either stock setup except where listed as identical below.

## Setup limits (`limits_m3_e46.carsetuplimits`)

HDC narrows every adjustable range around its own defaults (springs about +-10 percent of the default, dampers +-10 to 15 percent, arbs +-20 percent, steer ratio fixed at 14.0, camber / toe / pressure windows of 1 degree / 0.1 / 6 psi) and switches several entries to not modifiable. Differences (numeric fields; `min` absent in stock means 0):

| Path | Stock (game) | HDC | Delta / ratio |
|---|---|---|---|
| `aero.front_target_height.is_modifiable` | (absent) | false | - |
| `aero.front_target_height.max` | 200 | 130 | -70 (x0.65) |
| `aero.front_target_height.min` | (absent) | 130 | +130 [absent = 0] |
| `aero.rear_target_height.is_modifiable` | (absent) | false | - |
| `aero.rear_target_height.max` | 200 | 135 | -65 (x0.675) |
| `aero.rear_target_height.min` | (absent) | 135 | +135 [absent = 0] |
| `alignments[0,1,2,3].camber.fractional_digits` | (absent) | 2 | +2 [absent = 0] |
| `alignments[0,1,2,3].compound.is_modifiable` | true | false | - |
| `alignments[0,1,2,3].compound.max` | 1 | 0 | -1 (x0) |
| `alignments[0,1,2,3].compound.min` | (absent) | 0 | +0 [absent = 0] |
| `alignments[0,1,2,3].toe.fractional_digits` | (absent) | 2 | +2 [absent = 0] |
| `alignments[0,1].camber.max` | -1 | -3 | -2 (x3) |
| `alignments[0,1].camber.min` | -2.5 | -4 | -1.5 (x1.6) |
| `alignments[0,1].caster.is_modifiable` | (absent) | false | - |
| `alignments[0,1].caster.max` | (absent) | -0.068 | -0.068 [absent = 0] |
| `alignments[0,1].caster.min` | -1.2 | -0.068 | +1.132 (x0.05667) |
| `alignments[0,1].pressure.max` | 40 | 31 | -9 (x0.775) |
| `alignments[0,1].pressure.min` | 20 | 25 | +5 (x1.25) |
| `alignments[0,1].toe.max` | 0.2 | 0.05 | -0.15 (x0.25) |
| `alignments[0,1].toe.min` | -0.2 | -0.05 | +0.15 (x0.25) |
| `alignments[2,3].camber.max` | -1 | 0 | +1 (x0) |
| `alignments[2,3].camber.min` | -2.5 | -1 | +1.5 (x0.4) |
| `alignments[2,3].pressure.max` | 40 | 27 | -13 (x0.675) |
| `alignments[2,3].pressure.min` | 20 | 21 | +1 (x1.05) |
| `alignments[2,3].toe.max` | 0.2 | 0.15 | -0.05 (x0.75) |
| `alignments[2,3].toe.min` | -0.2 | 0.05 | +0.25 (x-0.25) |
| `dampers[0,1,2,3].fast_bump.is_modifiable` | (absent) | true | - |
| `dampers[0,1,2,3].fast_rebound.is_modifiable` | (absent) | true | - |
| `dampers[0,1,2,3].slow_bump.is_modifiable` | (absent) | true | - |
| `dampers[0,1,2,3].slow_rebound.is_modifiable` | (absent) | true | - |
| `dampers[0,1].fast_bump.max` | 10000 | 1870 | -8130 (x0.187) |
| `dampers[0,1].fast_bump.min` | 500 | 1530 | +1030 (x3.06) |
| `dampers[0,1].fast_bump.step` | 100 | 85 | -15 (x0.85) |
| `dampers[0,1].fast_rebound.max` | 10000 | 5060 | -4940 (x0.506) |
| `dampers[0,1].fast_rebound.min` | 1000 | 4140 | +3140 (x4.14) |
| `dampers[0,1].fast_rebound.step` | 100 | 230 | +130 (x2.3) |
| `dampers[0,1].slow_bump.max` | 10000 | 3910 | -6090 (x0.391) |
| `dampers[0,1].slow_bump.min` | 1000 | 2890 | +1890 (x2.89) |
| `dampers[0,1].slow_bump.step` | 100 | 170 | +70 (x1.7) |
| `dampers[0,1].slow_rebound.max` | 12000 | 10580 | -1420 (x0.8817) |
| `dampers[0,1].slow_rebound.min` | 1000 | 7820 | +6820 (x7.82) |
| `dampers[0,1].slow_rebound.step` | 100 | 460 | +360 (x4.6) |
| `dampers[2,3].fast_bump.max` | 10000 | 1430 | -8570 (x0.143) |
| `dampers[2,3].fast_bump.min` | (absent) | 1170 | +1170 [absent = 0] |
| `dampers[2,3].fast_bump.step` | 100 | 65 | -35 (x0.65) |
| `dampers[2,3].fast_rebound.max` | 10000 | 4290 | -5710 (x0.429) |
| `dampers[2,3].fast_rebound.min` | (absent) | 3510 | +3510 [absent = 0] |
| `dampers[2,3].fast_rebound.step` | 100 | 195 | +95 (x1.95) |
| `dampers[2,3].slow_bump.max` | 10000 | 5520 | -4480 (x0.552) |
| `dampers[2,3].slow_bump.min` | (absent) | 4080 | +4080 [absent = 0] |
| `dampers[2,3].slow_bump.step` | 100 | 240 | +140 (x2.4) |
| `dampers[2,3].slow_rebound.max` | 10000 | 6555 | -3445 (x0.6555) |
| `dampers[2,3].slow_rebound.min` | (absent) | 4845 | +4845 [absent = 0] |
| `dampers[2,3].slow_rebound.step` | 100 | 285 | +185 (x2.85) |
| `electronics.abs.is_modifiable` | (absent) | true | - |
| `electronics.abs.min` | 1 | 0 | -1 (x0) |
| `electronics.esc.min` | (absent) | 0 | +0 [absent = 0] |
| `electronics.tc1.min` | (absent) | 0 | +0 [absent = 0] |
| `electronics.tc2.is_modifiable` | (absent) | false | - |
| `electronics.tc2.max` | (absent) | 0 | +0 [absent = 0] |
| `electronics.tc2.min` | (absent) | 0 | +0 [absent = 0] |
| `mechanical_balance.arbs[0,1].is_modifiable` | (absent) | true | - |
| `mechanical_balance.arbs[0].max` | 50000 | 43200 | -6800 (x0.864) |
| `mechanical_balance.arbs[0].min` | 5000 | 28800 | +23800 (x5.76) |
| `mechanical_balance.arbs[0].step` | 500 | 3600 | +3100 (x7.2) |
| `mechanical_balance.arbs[1].max` | 50000 | 7200 | -42800 (x0.144) |
| `mechanical_balance.arbs[1].min` | 5000 | 4800 | -200 (x0.96) |
| `mechanical_balance.arbs[1].step` | 500 | 600 | +100 (x1.2) |
| `mechanical_balance.brakes.front_bias.is_modifiable` | (absent) | true | - |
| `mechanical_balance.brakes.front_bias.max` | 100 | 65 | -35 (x0.65) |
| `mechanical_balance.brakes.front_bias.min` | (absent) | 61 | +61 [absent = 0] |
| `mechanical_balance.brakes.torque_multiplier.is_modifiable` | (absent) | true | - |
| `mechanical_balance.brakes.torque_multiplier.min` | 100 | 90 | -10 (x0.9) |
| `mechanical_balance.brakes.torque_multiplier.step` | 10 | 1 | -9 (x0.1) |
| `mechanical_balance.differential.coast.fractional_digits` | (absent) | 2 | +2 [absent = 0] |
| `mechanical_balance.differential.coast.is_modifiable` | (absent) | true | - |
| `mechanical_balance.differential.coast.max` | 0.1 | 0.85 | +0.75 (x8.5) |
| `mechanical_balance.differential.coast.min` | (absent) | 0.55 | +0.55 [absent = 0] |
| `mechanical_balance.differential.coast.step` | 0.001 | 0.05 | +0.049 (x50) |
| `mechanical_balance.differential.power.fractional_digits` | (absent) | 2 | +2 [absent = 0] |
| `mechanical_balance.differential.power.is_modifiable` | (absent) | true | - |
| `mechanical_balance.differential.power.max` | 0.1 | 1 | +0.9 (x10) |
| `mechanical_balance.differential.power.min` | (absent) | 0.7 | +0.7 [absent = 0] |
| `mechanical_balance.differential.power.step` | 0.01 | 0.05 | +0.04 (x5) |
| `mechanical_balance.differential.preload.fractional_digits` | (absent) | 0 | +0 [absent = 0] |
| `mechanical_balance.differential.preload.is_modifiable` | (absent) | true | - |
| `mechanical_balance.differential.preload.max` | 10 | 30 | +20 (x3) |
| `mechanical_balance.differential.preload.min` | (absent) | 5 | +5 [absent = 0] |
| `mechanical_balance.differential.preload.step` | 0.1 | 5 | +4.9 (x50) |
| `mechanical_balance.steer_ratio.is_modifiable` | (absent) | false | - |
| `mechanical_balance.steer_ratio.max` | 16 | 14 | -2 (x0.875) |
| `mechanical_balance.steer_ratio.min` | 9 | 14 | +5 (x1.556) |
| `mechanical_balance.steer_ratio.step` | 1 | 0.1 | -0.9 (x0.1) |
| `suspensions[0,1,2,3].bump_stop_down.range.is_modifiable` | (absent) | false | - |
| `suspensions[0,1,2,3].bump_stop_down.rate.is_modifiable` | (absent) | false | - |
| `suspensions[0,1,2,3].bump_stop_down.rate.max` | 3000 | 500 | -2500 (x0.1667) |
| `suspensions[0,1,2,3].bump_stop_down.rate.min` | (absent) | 500 | +500 [absent = 0] |
| `suspensions[0,1,2,3].bump_stop_down.rate.step` | 100 | 10 | -90 (x0.1) |
| `suspensions[0,1,2,3].bump_stop_up.range.is_modifiable` | (absent) | false | - |
| `suspensions[0,1,2,3].bump_stop_up.rate.is_modifiable` | (absent) | false | - |
| `suspensions[0,1,2,3].bump_stop_up.rate.step` | 100 | 10 | -90 (x0.1) |
| `suspensions[0,1,2,3].wheel_rate.is_modifiable` | (absent) | true | - |
| `suspensions[0,1].bump_stop_down.range.max` | 0.265632 | 0.0556319 | -0.21 (x0.2094) |
| `suspensions[0,1].bump_stop_down.range.min` | -0.134368 | 0.0556319 | +0.19 (x-0.414) |
| `suspensions[0,1].bump_stop_up.range.max` | 0.234368 | 0.0193681 | -0.215 (x0.08264) |
| `suspensions[0,1].bump_stop_up.range.min` | -0.0656319 | 0.0193681 | +0.085 (x-0.2951) |
| `suspensions[0,1].bump_stop_up.rate.max` | 1000 | 80 | -920 (x0.08) |
| `suspensions[0,1].bump_stop_up.rate.min` | (absent) | 80 | +80 [absent = 0] |
| `suspensions[0,1].wheel_rate.max` | 80000 | 59400 | -20600 (x0.7425) |
| `suspensions[0,1].wheel_rate.min` | 5000 | 48600 | +43600 (x9.72) |
| `suspensions[0,1].wheel_rate.step` | 500 | 2700 | +2200 (x5.4) |
| `suspensions[2,3].bump_stop_down.range.max` | 0.215391 | 0.0153905 | -0.2 (x0.07145) |
| `suspensions[2,3].bump_stop_down.range.min` | -0.184609 | 0.0153905 | +0.2 (x-0.08337) |
| `suspensions[2,3].bump_stop_up.range.max` | 0.284609 | 0.0746095 | -0.21 (x0.2621) |
| `suspensions[2,3].bump_stop_up.range.min` | -0.0153905 | 0.0746095 | +0.09 (x-4.848) |
| `suspensions[2,3].bump_stop_up.rate.max` | 1000 | 500 | -500 (x0.5) |
| `suspensions[2,3].bump_stop_up.rate.min` | (absent) | 500 | +500 [absent = 0] |
| `suspensions[2,3].wheel_rate.max` | 80000 | 60500 | -19500 (x0.7562) |
| `suspensions[2,3].wheel_rate.min` | 5000 | 49500 | +44500 (x9.9) |
| `suspensions[2,3].wheel_rate.step` | 500 | 2750 | +2250 (x5.5) |

## Suspension geometry / coilovers

Standalone geometry files `ks_bmw_m3_e46_front_sus_1.suspension`, `..._rear_sus_1.suspension`, `..._rear_sus_m2.suspension` are byte-identical (all hard points, camber, toe coefficients, hub mass). Coilover files (physical spring and dampers; the setup values above sit on top):

Front coilover (`ks_bmw_m3_e46_front_1.coilover`):

| Path | Stock (game) | HDC | Delta / ratio |
|---|---|---|---|
| `damper.fast.bump` | 1500 | 1700 | +200 (x1.133) |
| `damper.fast.rebound` | 4750 | 4600 | -150 (x0.9684) |
| `damper.slow.bump` | 5500 | 3400 | -2100 (x0.6182) |
| `damper.slow.rebound` | 7500 | 9200 | +1700 (x1.227) |
| `springRate` | 55000 | 54000 | -1000 (x0.9818) |

Rear coilover (`ks_bmw_m3_e46_rear_1.coilover`):

| Path | Stock (game) | HDC | Delta / ratio |
|---|---|---|---|
| `damper.fast.bump` | 250 | 1300 | +1050 (x5.2) |
| `damper.fast.rebound` | 1000 | 3900 | +2900 (x3.9) |
| `damper.slow.bump` | 12000 | 4800 | -7200 (x0.4) |
| `damper.slow.rebound` | 16000 | 5700 | -10300 (x0.3563) |
| `springRate` | 50000 | 55000 | +5000 (x1.1) |

Coilover fields that are identical: bump stop ranges, forces, gamma, reference, damping, length, collar_position, fastThresholdBump / Rebound (0.15 front, 0.12 rear).

Inline `.car` copies. The inline `suspensions.coilover_front/rear.*` values changed together with the files (same numbers). Inline suspension geometry in the `.car` (stock `.car` versus HDC `.car`):

| Path | Stock (game) | HDC | Delta / ratio |
|---|---|---|---|
| `suspensions.suspension_geometry_front.strut.carSteer.z` | 0.07571 | 0.12571 | +0.05 (x1.66) |
| `suspensions.suspension_geometry_front.strut.tyreSteer.x` | 0.13 | 0.035 | -0.095 (x0.2692) |
| `suspensions.suspension_geometry_front.strut.tyreSteer.z` | 0.08323 | 0.13323 | +0.05 (x1.601) |
| `suspensions.arbFront.stiffness` | (absent) | 36000 | +36000 [absent = 0] |
| `suspensions.arbRear.stiffness` | (absent) | 6000 | +6000 [absent = 0] |

The three geometry values differ only in the `.car` inline copy of the front strut: in HDC the inline copy equals the standalone file (which is byte-identical to the current game's standalone file), in the current stock `.car` the inline copy deviates from its own standalone file (see Version drift). The anti-roll bar stiffness fields do not exist in the stock BMW `.car` at all (absent = 0), HDC adds them (the setup arbs values 36000 / 6000 equal them).

## Aero

No difference in any aero value: the four wing files `ks_bmw_m3_e460..e463.wing` have identical leaves (`e460`-`e462` differ in the byte size only through the curve path strings), the `car: aero` section is identical, and all aero curves (`wing_*_aoa_cl/cd.curve`, controller speed curve) are byte-identical. Ride height (aero target heights) is a setup entry and appears under Setup defaults / Setup limits.

## Electronics

Inline `car: electronics` (ABS, ESP, TC settings tables) is identical in all leaves. What HDC changed are the performance mode and the setup entries:

| Path | Stock (game) | HDC | Delta / ratio |
|---|---|---|---|
| `performance_modes[0].electronics_settings.tc1` | 1 | 0 | -1 (x0) |
| `performance_modes[1].electronics_settings.abs (stock mode NORMAL, no equivalent in HDC)` | 1 | (absent) | -1 (x0) [absent = 0] |
| `performance_modes[1].electronics_settings.esc (stock mode NORMAL, no equivalent in HDC)` | 1 | (absent) | -1 (x0) [absent = 0] |
| `performance_modes[1].electronics_settings.tc1 (stock mode NORMAL, no equivalent in HDC)` | 1 | (absent) | -1 (x0) [absent = 0] |
| `performance_modes[0].electronics_settings.esc` | (absent) | 0 | +0 [absent = 0] |
| `performance_modes[0].electronics_settings.tc2` | (absent) | 0 | +0 [absent = 0] |
| `setup: electronics.tc1 (stock setup 1.0; absent in HDC setup = 0)` | 1 | (absent) | -1 (x0) [absent = 0] |
| `setup: electronics.abs` | 1 | 1 | +0 (x1) |

Stock has two performance modes: `SPORT+` (tc1 1, abs 1, no esc entry = 0) and `NORMAL` (tc1 1, abs 1, esc 1). HDC has one mode named `HDC Drift` with tc1 0, tc2 0, abs 1 (unchanged value), esc 0. The HDC setup omits `electronics.tc1` (stock setup: 1) and its limits fix tc1 / esc / tc2 at 0 and keep abs modifiable.

## Tyres

The current BMW references `common_phsx/tyres/road/road_235_35_19.tyre` and `road_265_30_19.tyre` (default compound `TyreCompound_Road_Michelin`) and offers `supercar_235_35_19` / `supercar_265_30_19` (Cup 2) as a second compound. HDC ships `data/tyres/hdc_235_35_19_front.tyre`, `hdc_265_30_19_rear.tyre` plus `hdc_temperature_front.curve`, `hdc_temperature_rear.curve`, `hdc_wear.curve`; its `compatibletyres` lists only one compound `TyreCompound_Supercar_Michelin_Cup_2` (both files above) and the `.car` and the mechanical preset use it. Decoded as `TyresCompoundData` (names from the schema; `?N` = unnamed wire field number N, float32). Comparison to the road tyre the stock car uses (front, then rear); the second block compares to the supercar tyre, which HDC's files resemble much more closely.

Front tyre 235/35 R19, HDC versus stock **road** tyre:

| Path | Stock (game) | HDC | Delta / ratio |
|---|---|---|---|
| `grooveData.grooveFactor` | 0.49 | 0.441 | -0.049 (x0.9) |
| `modelData.Dx0` | 1.25841 | 1.326 | +0.0675864 (x1.054) |
| `modelData.Dy0` | 1.20783 | 1.35343 | +0.1456 (x1.121) |
| `modelData.Fz0` | 3930 | 3720 | -210 (x0.9466) |
| `modelData.brushExponent` | 2.9 | 2.85 | -0.05 (x0.9828) |
| `modelData.combinedFactor` | 1.8 | 1.75 | -0.05 (x0.9722) |
| `modelData.friction_limit_angle` | 8.11553 | 8.41818 | +0.30265 (x1.037) |
| `modelData.gripSlipFactor` | 0.78 | 0.77 | -0.01 (x0.9872) |
| `modelData.lsExpX` | 0.898015 | 0.893332 | -0.00468364 (x0.9948) |
| `modelData.lsExpY` | 0.870015 | 0.863332 | -0.00668359 (x0.9923) |
| `modelData.wearCurve` | content\cars\common_phsx\tyres\road\wear_road.curve | content\cars\hdc_bmw_e46_01\data\tyres\hdc_wear.curve | - |
| `pressure` | 30 | 28 | -2 (x0.9333) |
| `pressureData.pressureReference` | 30 | 28 | -2 (x0.9333) |
| `speedSensitivity.?1[0]` | 0.77 | 0.74 | -0.03 (x0.961) |
| `speedSensitivity.?2[0]` | 0.4 | 0.3 | -0.1 (x0.75) |
| `speedSensitivity.?3[0]` | 0.72 | 0.7 | -0.02 (x0.9722) |
| `speedSensitivity.?4[0]` | 23 | 22 | -1 (x0.9565) |
| `speedSensitivity.?5[0]` | 2.7 | 3.1 | +0.4 (x1.148) |
| `speedSensitivity.?6[0]` | 23 | 22 | -1 (x0.9565) |
| `speedSensitivity.TrefMuT_x` | 70 | 80 | +10 (x1.143) |
| `speedSensitivity.mu0T_x` | 0.68 | 0.7 | +0.02 (x1.029) |
| `speedSensitivity.ref_speed_x` | 3.5 | 4 | +0.5 (x1.143) |
| `thermalData.?11[0]` | 587.073 | 547.073 | -40 (x0.9319) |
| `thermalData.?7[0]` | 0.02296 | 0.02396 | +0.001 (x1.044) |
| `thermalData.grainGain` | 0.27 | 0.47 | +0.2 (x1.741) |
| `thermalData.grainGamma` | 0.27 | 0.47 | +0.2 (x1.741) |
| `thermalData.grainSlipAngleGain` | 0.265 | 0.565 | +0.3 (x2.132) |
| `thermalData.grainSlipAngleGamma` | 0.345 | 0.845 | +0.5 (x2.449) |
| `thermalData.grainSlipAngleThreshold` | 10.8155 | 10.7255 | -0.09 (x0.9917) |
| `thermalData.heat_partition_coeff` | 0.7 | 0.9 | +0.2 (x1.286) |
| `thermalData.rolling_factor` | 0.7 | 0.8 | +0.1 (x1.143) |
| `thermalData.thermalPerformanceCurve` | content\cars\common_phsx\tyres\road\tcurve_road.curve | content\cars\hdc_bmw_e46_01\data\tyres\hdc_temperature_front.curve | - |
| `thermalData.thermal_conductivity` | 0.23 | 0.3 | +0.07 (x1.304) |
| `tyreData.?26[0]` | 30 | (absent) | -30 (x0) [absent = 0] |
| `tyreData.damping` | 504.714 | 561.697 | +56.9838 (x1.113) |
| `tyreData.lateralFlexK` | 30000 | 38000 | +8000 (x1.267) |
| `tyreData.longitudinalFlexK` | 18000 | 20000 | +2000 (x1.111) |
| `tyreData.mass` | 6 | 7 | +1 (x1.167) |
| `tyreData.rate` | 282100 | 273000 | -9100 (x0.9677) |
| `tyreData.treadHeightMM` | 8 | 7 | -1 (x0.875) |
| `tyre_compound` | PhysicsTyreCompound_Road | PhysicsTyreCompound_SuperCar | - |

Rear tyre 265/30 R19, HDC versus stock **road** tyre:

| Path | Stock (game) | HDC | Delta / ratio |
|---|---|---|---|
| `grooveData.grooveFactor` | 0.49 | 0.441 | -0.049 (x0.9) |
| `init_data.pressure` | 26 | 30 | +4 (x1.154) |
| `modelData.Dx0` | 1.27407 | 1.2659 | -0.0081686 (x0.9936) |
| `modelData.Dy0` | 1.22436 | 1.19931 | -0.0250519 (x0.9795) |
| `modelData.Fz0` | 4320 | 3720 | -600 (x0.8611) |
| `modelData.brushExponent` | 2.9 | 2.85 | -0.05 (x0.9828) |
| `modelData.combinedFactor` | 1.8 | 1.75 | -0.05 (x0.9722) |
| `modelData.friction_limit_angle` | 8.01075 | 8.35 | +0.339245 (x1.042) |
| `modelData.gripSlipFactor` | 0.78 | 0.77 | -0.01 (x0.9872) |
| `modelData.lsExpX` | 0.903611 | 0.9041 | +0.0004891 (x1.001) |
| `modelData.lsExpY` | 0.875611 | 0.863332 | -0.012279 (x0.986) |
| `modelData.wearCurve` | content\cars\common_phsx\tyres\road\wear_road.curve | content\cars\hdc_bmw_e46_01\data\tyres\hdc_wear.curve | - |
| `pressure` | 30 | 24 | -6 (x0.8) |
| `pressureData.idealPressure` | 31 | 30 | -1 (x0.9677) |
| `speedSensitivity.?1[0]` | 0.77 | 0.74 | -0.03 (x0.961) |
| `speedSensitivity.?2[0]` | 0.4 | 0.3 | -0.1 (x0.75) |
| `speedSensitivity.?3[0]` | 0.72 | 0.7 | -0.02 (x0.9722) |
| `speedSensitivity.?4[0]` | 23 | 22 | -1 (x0.9565) |
| `speedSensitivity.?5[0]` | 2.7 | 3.1 | +0.4 (x1.148) |
| `speedSensitivity.?6[0]` | 23 | 22 | -1 (x0.9565) |
| `speedSensitivity.TrefMuT_x` | 70 | 80 | +10 (x1.143) |
| `speedSensitivity.mu0T_x` | 0.68 | 0.7 | +0.02 (x1.029) |
| `speedSensitivity.ref_speed_x` | 3.5 | 4 | +0.5 (x1.143) |
| `thermalData.?7[0]` | 0.01867 | 0.02267 | +0.004 (x1.214) |
| `thermalData.grainGain` | 0.27 | 0.47 | +0.2 (x1.741) |
| `thermalData.grainGamma` | 0.27 | 0.47 | +0.2 (x1.741) |
| `thermalData.grainSlipAngleGain` | 0.265 | 0.565 | +0.3 (x2.132) |
| `thermalData.grainSlipAngleGamma` | 0.345 | 0.845 | +0.5 (x2.449) |
| `thermalData.grainSlipAngleThreshold` | 10.7108 | 10.6208 | -0.09 (x0.9916) |
| `thermalData.heat_partition_coeff` | 0.7 | 0.85 | +0.15 (x1.214) |
| `thermalData.rolling_factor` | 0.7 | 0.8 | +0.1 (x1.143) |
| `thermalData.thermalPerformanceCurve` | content\cars\common_phsx\tyres\road\tcurve_road.curve | content\cars\hdc_bmw_e46_01\data\tyres\hdc_temperature_rear.curve | - |
| `thermalData.thermal_conductivity` | 0.23 | 0.3 | +0.07 (x1.304) |
| `tyreData.?26[0]` | 30 | (absent) | -30 (x0) [absent = 0] |
| `tyreData.damping` | 576.816 | 641.94 | +65.1242 (x1.113) |
| `tyreData.lateralFlexK` | 30000 | 38000 | +8000 (x1.267) |
| `tyreData.longitudinalFlexK` | 18000 | 20000 | +2000 (x1.111) |
| `tyreData.mass` | 6 | 7 | +1 (x1.167) |
| `tyreData.rate` | 322400 | 312000 | -10400 (x0.9677) |
| `tyreData.treadHeightMM` | 8 | 7 | -1 (x0.875) |
| `tyre_compound` | PhysicsTyreCompound_Road | PhysicsTyreCompound_SuperCar | - |

Front tyre, HDC versus the stock **supercar** (Cup 2) tyre `supercar_235_35_19` (only the differences):

| Path | Stock (game) | HDC | Delta / ratio |
|---|---|---|---|
| `camberData.?7[0]` | (absent) | 8 | +8 [absent = 0] |
| `modelData.?11[0]` | (absent) | 0.96 | +0.96 [absent = 0] |
| `modelData.?12[0]` | (absent) | 0.96 | +0.96 [absent = 0] |
| `modelData.Dx0` | 1.31938 | 1.326 | +0.0066241 (x1.005) |
| `modelData.Dy0` | 1.26635 | 1.35343 | +0.0870884 (x1.069) |
| `modelData.Fz0` | 3930 | 3720 | -210 (x0.9466) |
| `modelData.friction_limit_angle` | 8.02553 | 8.41818 | +0.39265 (x1.049) |
| `modelData.lsExpX` | 0.902015 | 0.893332 | -0.00868365 (x0.9904) |
| `modelData.lsExpY` | 0.872016 | 0.863332 | -0.00868365 (x0.99) |
| `modelData.wearCurve` | content\cars\common_phsx\tyres\supercar\wear_supercar.curve | content\cars\hdc_bmw_e46_01\data\tyres\hdc_wear.curve | - |
| `pressure` | 30 | 28 | -2 (x0.9333) |
| `pressureData.idealPressure` | 30 | 31 | +1 (x1.033) |
| `pressureData.pressureReference` | 30 | 28 | -2 (x0.9333) |
| `thermalData.thermalPerformanceCurve` | content\cars\common_phsx\tyres\supercar\tcurve_supercar.curve | content\cars\hdc_bmw_e46_01\data\tyres\hdc_temperature_front.curve | - |

Rear tyre, HDC versus stock **supercar** tyre `supercar_265_30_19`:

| Path | Stock (game) | HDC | Delta / ratio |
|---|---|---|---|
| `camberData.?7[0]` | (absent) | 8 | +8 [absent = 0] |
| `modelData.?11[0]` | (absent) | 0.96 | +0.96 [absent = 0] |
| `modelData.?12[0]` | (absent) | 0.96 | +0.96 [absent = 0] |
| `modelData.Dx0` | 1.33495 | 1.2659 | -0.0690558 (x0.9483) |
| `modelData.Dy0` | 1.28288 | 1.19931 | -0.0835639 (x0.9349) |
| `modelData.Fz0` | 4320 | 3720 | -600 (x0.8611) |
| `modelData.friction_limit_angle` | 7.92075 | 8.35 | +0.429246 (x1.054) |
| `modelData.lsExpX` | 0.907611 | 0.9041 | -0.0035109 (x0.9961) |
| `modelData.lsExpY` | 0.877611 | 0.863332 | -0.014279 (x0.9837) |
| `modelData.wearCurve` | content\cars\common_phsx\tyres\supercar\wear_supercar.curve | content\cars\hdc_bmw_e46_01\data\tyres\hdc_wear.curve | - |
| `pressure` | 29 | 24 | -5 (x0.8276) |
| `pressureData.pressureReference` | 30 | 26 | -4 (x0.8667) |
| `thermalData.heat_partition_coeff` | 0.9 | 0.85 | -0.05 (x0.9444) |
| `thermalData.thermalPerformanceCurve` | content\cars\common_phsx\tyres\supercar\tcurve_supercar.curve | content\cars\hdc_bmw_e46_01\data\tyres\hdc_temperature_rear.curve | - |

Curves: `hdc_temperature_front.curve` (37 points, peak 1.0 from 60 to 95 deg) is identical to the game's `supercar/tcurve_supercar.curve`: yes. `hdc_temperature_rear.curve` has the same 37 points; values from 98 deg upward are slightly higher (for example 0.9986 vs 0.9982 at 98.4, 0.9843 vs 0.9790 at 116.2, 0.9529 vs 0.9392 at 204, 0.8306 vs 0.8261 at 235.2), the end point (250, 0.6) is unchanged. The road curve `tcurve_road.curve` has 21 points, plateau 31.9 to 70 deg, end at (350, 0.6). `hdc_wear.curve` (16 points) is identical to `supercar/wear_supercar.curve`: yes; `road/wear_road.curve` has 15 points (last point (8, 99.5) versus (7, 99.5)).

Reading of the numbers: HDC's tyres are tuned copies of the stock supercar compound (`tyre_compound` PhysicsTyreCompound_SuperCar, same flex, damping, speed sensitivity and thermal values as the supercar file) with a changed friction model block (Dy0, Dx0, Fz0, friction_limit_angle, load exponents) and pressure; the unnamed fields `camberData ?7`, `modelData ?11/?12` exist in HDC (8.0 / 0.96 / 0.96) but not in the current game's supercar file (the road file has them with 15 / 8.0 / 0.9).

## Other (controls, steering, display, mass)

| Path | Stock (game) | HDC | Delta / ratio |
|---|---|---|---|
| `controls.ffMult` | 1.75 | 1.5 | -0.25 (x0.8571) |
| `controls.linearSteerRodRatio` | 0.0017 | 0.0025 | +0.0008 (x1.471) |
| `controls.steerRatio` | 14.5 | 14 | -0.5 (x0.9655) |
| `controls.steer_lock` | 540 | 450 | -90 (x0.8333) |

Display values of the mechanical preset (spec sheet only, no physics): POWER 360 -> 375 (unit HORSEPOWER_US), TORQUE 370 -> 378 Nm; MAX_SPEED and ACCELERATION items removed in HDC; weight display 1460 unchanged. Mass (`general.totalMass` 1495), tank (63 L), kgPerLiter, body size and all other `general` leaves are identical. HDC car `screenName` is "Hina's Drift Club - BMW M3 CSL".

## Identical fields (not touched by Hina)

- **Engine** (30 leaves): audio_throttle_limiter_tau_ms=10, damage.bovThreshold=0.2, damage.rpmDamageK=1, damage.turboBoostDamageK=5, damage.turboBoostDamageThreshold=2, inertia=0.22, limiter=8100, limiterCycles=30, maps[*].?5[*]=5000, maps[*].consumptionMult=1, maps[*].powerMult=1, maps[*].throttle_lag_dn=0.88, maps[*].throttle_lag_up=0.98, maps[*].throttling_factor=0.15, maps[*].type=cervone, minimum=700, nominal_rpm=8100, overlapFreq=10, startECUAssist.clutch_gain=6.7, startECUAssist.gain=1, startECUAssist.gas_gain=1, startECUAssist.limiter_cycles=100, startECUAssist.rpmRange=4000, startECUAssist.rpm_limiter=2850, startECUAssist.slip_ratio_target=0.2, startECUAssist.speedRangeKHM=100, startECUAssist.use_clutch=true, starterEngineTorque=40, throttle_lag_dn=0.97, throttle_lag_up=0.98.
- **Gearbox** (16): auto_cut_off_time=250, autoblip.isElectronic=true, autoshifter.?2[*]=4500, autoshifter.gasCutoffTime=0.26, autoshifter.slipThreshold=0.95, autoshifter.up=7900, controls_window_gain=0.4, damageRpmWindow=100, downshift_protection.isActive=true, downshift_protection.lockN=true, gear_count=6, gear_dn_time=280, gear_up_time=200, gearbox_inertia=0.017, gears[*].ratio=-3.746/0.828/1/1.226/1.669, valid_shift_rpm_window=1000.
- **Drivetrain** (named): damping_ratio=0.4, max_torsion_deg=6, non_linear_model=true, stiffness=400, stiffness_mult=3.
- **Clutch**: all 5 leaves identical (named and unnamed).
- **Brakes**: all 4 leaves, file byte-identical.
- **Setup**: alignments[*].caster=-0.068, electronics.abs=1, fuel_strategy.fuel=30, mechanical_balance.brakes.front_bias=63, mechanical_balance.brakes.torque_multiplier=100, mechanical_balance.differential.preload=10, suspensions[*].bump_stop_up.rate=500.
- **Coilover front** (bump stops and thresholds): bumpStopDown.Force=500, bumpStopDown.Gamma=1.5, bumpStopDown.Range=0.0556319, bumpStopDown.Reference=0.03, bumpStopDown.damping=500, bumpStopDown.length=0.04, bumpStopUp.Force=80, bumpStopUp.Gamma=1.5, bumpStopUp.Range=0.0193681, bumpStopUp.Reference=0.04, bumpStopUp.damping=200, bumpStopUp.length=0.05, collar_position=0.0656319, damper.fastThresholdBump=0.15, damper.fastThresholdRebound=0.15.
- **Suspension geometry**: all hard points and basic_data of the three standalone files (byte-identical) and the rear inline copy.
- **Wings / aero**: all wing leaves, `car: aero`, `car: electronics`, all aero and gearbox / clutch profile curves (`autoblipprofile`, `upshiftprofile`, `downshiftprofile`), throttle response curves, `_power.curve`.
- **Car file**: `general` (mass, fuel, box sizes, torsional stiffness 28000 / damping 251), `brakes`, `aero`, `electronics`, the rest of `controls`, `gearbox` gears 3-6, `engine` except rpmDamageThreshold.

## Version drift versus Hina's tuning

Evidence available inside the HDC package (files that are still untouched Kunos files of HDC's base version):

1. **Power curve: no drift.** HDC's `_power.curve` (older Kunos file kept unused) is byte-identical to the current game's `_power.curve`, and HDC's tuned `_power_1.curve` equals the current stock `_power_1.curve` multiplied by 1.0497 at every one of the 22 points (21 with a nonzero value; same rpm positions). So the base curve did not change between HDC's base and the current game; the +4.97 percent is Hina's tuning. The coast curve differs only in the last two points (x0.8 at 1100 and 9000 rpm), Hina's tuning (the first five points are identical).
2. **Byte-identical files = neither tuned by Hina nor changed by Kunos since**: brakes, `aicardata`, all three suspension geometry files, wing curves, all aero curves, autoblip / upshift / downshift profiles, both throttle response curves, wing `e463`, `_power.curve`. If the game's base had changed in these, HDC would differ.
3. **Fields changed to round numbers in files that are otherwise stock** are Hina's tuning: final drive 3.62 -> 3.91, gears 1 / 2 (3.5, 2.1), steer lock 540 -> 450, diff preload 1 -> 10, rpmDamageThreshold 7700 -> 8400, tyre friction block, springs / dampers (HDC's setup, coilover and inline values agree with each other to the digit), ARB 36000 / 6000, ride height 130 / 135, camber -3.5 / -0.5.
4. **Probable drift (not proven)**: (a) the front strut hard points in the `.car` inline copy: HDC inline = standalone file (`carSteer.z` 0.12571, `tyreSteer.x` 0.035, `tyreSteer.z` 0.13323), current stock inline = 0.07571 / 0.13 / 0.08323 while the current stock standalone file still holds the HDC values; the standalone file did not change, so either Kunos changed only the inline copy after HDC's base or Hina copied the standalone values into the inline copy. (b) The current stock performance-pack setup and the older `bak/stock_sport` setup are Kunos files from two versions; HDC's setup values cannot be traced to either (so the setup baseline of HDC's base is unknown). (c) Tyres: the current game's supercar tyre lacks three unnamed fields (`camberData ?7`, `modelData ?11`, `?12`) that HDC's tyres have and the road tyre has; HDC's supercar-based values for `pressureData.idealPressure` (31 front) and `pressureReference` (28 front / 26 rear) are Hina's pressure tuning, the other supercar-model differences (Dx0, Dy0, Fz0, lsExp, friction_limit_angle) are listed above and are either tuning or a changed supercar file; with only this package they cannot be separated. (d) The stock `.car` has two performance modes (`SPORT+`, `NORMAL`), HDC only a custom one: Hina rewrote it, whether the base had one or two is unknown. (e) `drivetrain.differential_data.power/coast` and `arbFront/arbRear.stiffness` exist only in HDC's `.car`; the stock BMW has no such fields (absent), which could be an older schema (drift) or Hina's addition.

