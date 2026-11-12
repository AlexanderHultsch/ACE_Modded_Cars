# What Hina changed for the drift setup (BMW M3 E46): stock versus Hina's Drift Club 1.4

Source: the E46 of Hina's Drift Club 1.4 (author Hina, OverTake.gg; all rights with the author, used here for research and comparison only) against the current stock BMW M3 E46 CSL from the game, both decoded by name with `tools/car_json.py`. Full number tables: [../Example mods (reference only)/hdc_e46_vs_stock.md](../Example%20mods%20%28reference%20only%29/hdc_e46_vs_stock.md). The driving effects below are the usual simulator reading of these numbers and are **not tested in the game**.

Version drift: nothing in the power curve, gearbox, drivetrain, brakes, clutch, suspension hard points or aero changed between Hina's base and the current game (her unused original curve is byte-identical to the game's). The only probable drift is a front strut hard-point copy inside the `.car`. So essentially everything below is Hina's tuning.

## Summary by area

| Area | Stock (game) | Hina | What it does for driving |
|---|---|---|---|
| Engine power | peak 360 Nm, 362 PS | x1.05 at every rpm: 378 Nm, 380 PS | A mild power gain (about +18 PS), the same as our +20 hp test edit. |
| Engine braking | coast curve -10 .. -89 Nm | x0.8 at both ends (-8 .. -71) | Less engine braking when you lift: calmer weight transfer and less rear lock-up on lift-off. |
| Rev damage limit | 7700 rpm | 8400 rpm | Lets the engine live closer to the 8100 limiter. |
| Final drive | 3.62 | 3.91 (+8 %) | Shorter overall gearing. |
| Gears 1 and 2 | 4.227 / 2.528 | 3.5 / 2.1 | Overall ratios: 1st -10 %, 2nd -10 %, gears 3-6 +8 %. Taller first two gears (less wheelspin), shorter upper gears: stronger pull at drift speeds in 3rd-6th, about 7 % lower top speed, closer 2nd-3rd gap (the rpm drop on the shift shrinks). Gears 3-6 untouched. |
| Differential (setup) | power 0.3, coast 0.1, preload 10 Nm | power 0.85, coast 0.70, preload 10 Nm | The central drift change: the rear wheels are forced to turn together on throttle and on lift. The slide stays predictable and the inside wheel does not spin. Not a full spool (1.0 / 1.0). |
| Differential (hardware) | preload 1, torque bias 2.3 power / 0.5 coast | preload 10, bias 2.5 / 3.0 | The physical diff model is also much more locked, mostly on coast. |
| Diff limits | power and coast max 0.1 | power 0.7-1.0, coast 0.55-0.85 | Stock lets you choose only almost-open settings; Hina's ranges keep you in the locked band. |
| Steering | steer ratio 14.5, lock 540 deg, rod ratio 0.0017 | ratio 14 (fixed), lock 450 deg, rod ratio 0.0025 (+47 %) | Quicker steering and, above all, far more front wheel angle for the same hand movement: the most important change for holding big drift angles. |
| Springs (wheel rate) | front 80000, rear 65000 N/m | 54000 / 55000 (-32 % / -15 %) | Softer car, more roll and weight transfer, quicker transitions, more compliance on bumps. |
| Dampers | e.g. front slow bump 15000, rear 14000 | 3400 / 4800 (about -75 % / -65 %), others -20 to -66 % | Slow, soft body movements: weight shifts to the front and back are big and easy to trigger. |
| Anti-roll bars | front 70000, rear 50000 | 36000 / 6000 | The rear bar nearly removed: the rear axle works almost independently and keeps traction under power. |
| Ride height | 116 / 118 mm | 130 / 135 mm | Higher car (more travel, kerbs), bump stops 2.5x stiffer. |
| Camber | front -2.0, rear -1.5 | front -3.5, rear -0.5 | More front grip while the wheels are turned and the body rolls; rear contact patch at its largest for traction, less peak side grip. |
| Toe | front -0.01, rear 0.15 | front 0, rear 0.10 | Less rear toe-in: less straight-line stability, more willingness to rotate. |
| Tyre pressure | 27 / 27 psi | 28 / 23 | Softer, larger rear patch. |
| Tyres | Road compound | tuned copy of the Supercar compound | Front lateral grip +12 %, front longitudinal +5 %, rear -2 % / -1 %: the front out-grips the rear so steering has authority and the rear can slide. Grip falls off later at higher slip angles (progressive slides), much hotter working window (60-95 deg instead of 32-70 deg: drifting heats the tyres), stiffer sidewalls. |
| Electronics | SPORT+: traction control 1, ESC 0 (NORMAL mode with ESC) | one mode "Drift": TC 0, ESC 0 | All driver aids off, no interference. |
| Setup limits generally | broad windows (for example steer ratio 9-16, camber -2.5..-1) | narrow windows around her values (steer ratio fixed 14, camber front -4..-3 / rear -1..0, springs and dampers +-10-15 %) | The mod keeps you inside its drift setup. |

## What she did not touch

Brakes, clutch, mass (1495 kg), fuel (63 L), rev limiter 8100, nominal rpm, idle, gears 3-6 and reverse, shift times, brake bias 63, suspension hard points, wings and aero, the electronics tables, caster, the throttle response curves.

## How this relates to our tuner

Covered today: power curve and coast curve scale, damage rpm, final drive and gears, differential defaults and limits (setup layer), steer ratio, steer lock, springs, dampers, anti-roll bars (setup layer), camber, toe, tyre pressure, fuel.

Not covered yet and important for a drift tune, in order of value (see [settings/coverage.md](settings/coverage.md)): **tyres** (grip, load sensitivity, thermal window), **steering rod ratio** (`controls.linearSteerRodRatio`, the big angle change), **electronics** (TC / ESC levels and the performance modes), **hardware differential** (preload and torque bias in the drivetrain file), **ride height** (`setup.aero` target heights) and bump stops, **the physical coilover spring and damper values and the anti-roll bar stiffness** (Hina changed these consistently with the setup layer; which layer the game uses is still open), caster, brake bias in the brake file, clutch maximum torque.
