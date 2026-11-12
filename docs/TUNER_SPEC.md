# Drift tuner: state of the project

Updated 2026-11-12. The tuner works for five cars and is pushed to GitHub. What it does and how to use it: [../README.md](../README.md). Every setting per car: [settings/](settings/). Notes for continuing in a new session: [HANDOVER.md](HANDOVER.md).

## 1. Summary

| Area | State |
|---|---|
| Goal | Change the driving settings of a car in a table page, install an own tuned copy, drive, close, repeat. No cosmetics. |
| Cars | **Five tested:** BMW M3 E46 CSL, Toyota GR86, Mazda RX-7 FD, Alfa Romeo Giulia GTAm, Porsche 992 GT3 R Rennsport (all extracted in the user's work folder). **All 71 game cars are listed** (from the game's `cars.table`, cached in `cars_index.json`), the 66 others shown as "not extracted" and untested; only cars the user picks are extracted. Six untested cars (Ferrari F40 LM, Audi Sport Quattro, Alpine A290 Beta (electric), Dallara EXP, MX-5 NA, 992 GT3 RS) extract, resolve defaults, build and pass the codec check without errors; whether they load or drive is unknown. For the electric car the combustion-engine settings are still shown. |
| First car | The BMW is installed as `BMW M3 E46 CSL_MY` with Hina's Drift Club drift setup recreated (90 settings changed against stock: differential, steering incl. rod ratio, soft springs/dampers/anti-roll bars, ride height, camber/toe/pressure, tyres, power curve, driver aids off) plus the user's own 29 L start fuel. The values were read from her package and checked value by value against it (136 of 137 settings match; the one mismatch is the five low-rpm points of the coast curve, which she left unscaled). The settings list is kept only in the user's local work folder, not in the repo. Not reproduced: her front strut hard points (version drift), her single "Drift" driving mode (we switch aids off in the stock modes), her narrow setup limit windows, the wear curve and some unnamed tyre fields. Untested in the game. |
| Tuner | **Built.** 143 settings in the catalogue, 136-142 applicable per tested car; local web page with car selector; Apply (update my car) and Save as new copy; backup on every install. |
| Verified against the real game files | **All five cars:** extracted from the game, defaults resolved, unchanged build equals stock apart from the id rename, edits change exactly the expected values in every copy, codec check has no failures, no stock id remains in the packages. |
| Verified in the game | BMW only so far (laptop): the car appears and loads, physics log identical to stock, the +20 hp display value shows in the selector. Effects of edits on driving are **not tested yet**; the other four cars have not been loaded in the game. |

## 2. What exists

| Part | File | Purpose |
|---|---|---|
| Package tool | `tools/kspkg.py` | list / extract (path prefix) / pack / verify `.kspkg`; long Windows paths |
| Schema extractor | `tools/extract_protos.py` | protobuf field names out of the SDK Editor exe into `schemas/` (kept local) |
| Codec | `tools/car_json.py` | lossless decode/encode of car files to JSON with real names; 31 file types (incl. `.tyre`) |
| Clone tool | `tools/clone_car.py` | copy a stock car under a same-length id, register it as a mod, names, pack, install with backup |
| Settings engine | `tools/tune.py`, `tuner/catalogue.json`, `tuner/cars.json` | car list, settings list, defaults from the game files, state, apply, reference generator |
| Web page | `tools/tuner_server.py`, `tuner/web/index.html`, `tuner/start_tuner.bat` | table with variable name, value, description, default; car selector |
| Reference | `docs/settings/<car id>.md` (generated), `Example mods (reference only)/decoded/` | all settings per car; driving data of six drift cars by Hina, text only |

## 3. Design decisions (made with the user)

- One HTML table is the only editing surface; columns Variable name, Value, Description, Default. Local server, Windows batch start.
- Apply installs only; the user starts and closes the game; refused while the game runs; a backup of the previous install every time.
- Each car gets its own copy under an id of the same length as the stock id: `ks_` replaced by `ax_` (`ks_bmw_m3_e46_csl` -> `ax_bmw_m3_e46_csl`). Name: the stock display name from the game's `system\cars.table` (not editable) plus a suffix the user chooses in a field next to it (setting `name_suffix`, default `_MY`, 1-30 characters; the default sorts the car next to the stock one in the game's list). The stock cars are never modified. "Save as new copy" installs further ids.
- Settings the car does not have are hidden (turbo values on naturally aspirated cars, gears beyond the real count, variant name when the car has none).
- Defaults are always read from the stock car in the game, never typed in. Descriptions in English; "unverified" where the meaning is guessed.
- Registration (brand, year, car classes) and the names in the car list come from the game's own data for that car.

## 4. How a build works

1. `init --car <id>` extracts that car (and its row from `cars.table`, and the shared stock localization once) from the game's `content.kspkg` into `%USERPROFILE%\ace_modded_cars_work\<car id>\base`.
2. Every Apply starts from that pristine copy: clone under the new id by same-length text replacement (no protobuf length changes), add the mod registration and localization, change the chosen settings in every copy of the value (standalone file and the inline copy in the car's `.car`), pack, back up the installed package, install.
3. The catalogue names files by role (`@engine`, `@gearbox`, `@drivetrain`, `@brakes`, `@setup`, `@limits`, `@car`, `@mech_preset`, `@turbo[N]`), resolved per car through its `.car` manifest, so one catalogue serves all cars. A setting is applicable when its required targets resolve; inline `.car` copies are optional targets.
4. An Apply with no changes equals a plain clone (tested on all five cars).
5. The work folder is outside OneDrive and outside AppData (the Claude desktop app redirects AppData writes into a private folder the user cannot see). Long paths (the Porsche's thumbnails exceed 260 characters) are handled with extended-length paths.

## 5. What was verified

- **Real game files, all five cars:** extraction, `defaults` (exit 0; applicable/hidden: BMW 77/5, GR86 77/5, RX-7 77/5, Giulia 81/1, Porsche 76/6), unchanged builds equal stock apart from the rename (all files identical, two added files: registration and localization), real edits (limiter, power curve scale, fuel) change exactly the expected values in all copies, `car_json.py check` no failures, no entry of any package contains the stock id, both copies written (for example the Giulia's turbo boost in the engine file, the `.turbo` file and the `.car`).
- **Web page:** car selector, per-car rows, hidden-settings line, "copies differ" badge, extract button for cars not yet extracted, edit/reset, apply and numbered copies (scratch folders, browser pane).
- **BMW in the game (laptop):** loads, physics identical to stock, display values show. The laptop renderer crashes for every car (Intel UHD 128 MB).

## 6. Open and unverified

- Do edits change the driving in the game (log line `POWER CLASS INDEX`, setup screen values, feel)? Not tested; needs the gaming PC.
- The four other cars have not been loaded in the game. Does each appear and load next to its stock car?
- Which copy does the game read when a value exists twice? Both are written. Some stock copies genuinely differ (RX-7: rev limiter cycles 11 vs 16, auto-shift 7500 vs 7000, max turbo boost 0.70 vs 0.69; shown with a badge).
- Do the setup limits act as ranges? Stock defaults exceed stock limits in places (BMW diff power 0.3 vs max 0.1).
- Does `diff_type` Spool (fully locked) take effect? Do numbered copies load?
- The RX-7 stock spring limits read 0 / 5 (looks like absent or unit-quirk data). The RX-7's real turbo cap seems to be the engine-level `max_turbo_boost`, not the per-turbo `max_boost`.
- About a third of the settings are marked unverified.
- Tyres: the build creates the car's own tyre files only for a changed axle and rewires the `.car` and the `compatibletyres` entry of the starting compound; the other compounds stay stock, and the game's choice between the `.car` and the preset entry is untested. The rear thermal curve of the recreated Hina setup is a near match of the supercar family.
- Not covered yet: aero, the performance-mode list itself (modes cannot be removed, only switched to aids off), TC/ABS/ESP tables, damper limits and curves, engine map values, further turbo settings (lag, wastegate, controllers), tyre fields without a setting (groove, brush, combined factor, speed sensitivity, wear curve), suspension hard points, `controls.steerRatio` and `ffMult` in the `.car`.

## 6b. Cars, variants and names (researched in the game files)

- In the game's car list each entry is a car with its own id; its title is the display name. The selection screen shows the car's **variants** (mechanical presets) and **trim levels** (visual presets). Example GR86: Standard, Trueno Edition, Hakone Edition; they differ in body parts and display values, all show 235 hp.
- A variant (`MechanicalCarPresetData`) carries display specs, tyre compound, rims, visual presets and lists of forced / compatible **parts**; it has **no physics of its own**. The physics files (engine, gearbox, setup, ...) belong to the whole car.
- The game's mechanism for variants with different physics is **tuning parts** (`TuningPart`: engine/gearbox/drivetrain/clutch/brakes/setup/limits files, a power multiplier, ...), attached through a variant's forced parts. Hina's AE86 uses it (engine 16v tuned / 20v blacktop / stock).
- Consequences: our tuned car must be its own mod car; adding a variant to a stock car would mean changing the stock car's own package. The user decided against building saved tunes as variants (tuning parts); several tunes stay separate copy cars ("Save as new copy").

## 7. Next steps

1. Test in the game on the gaming PC: load each of the five cars, drive, confirm that edits take effect, test Spool, the limits, numbered copies.
2. The gaps found by the analyses ([settings/coverage.md](settings/coverage.md), [drift-setup-comparison.md](drift-setup-comparison.md)) are closed for tyres, steering rod ratio, driver aids, hardware differential, ride height and bump stops, physical coilover / anti-roll values, caster, brake bias and clutch torque. Open: which layer wins (setup values or physical values), and the not-covered list in section 6. Then aero, more turbo settings, remaining tyre fields.
3. Polish: live build log in the page, job state per car, a guard against very long custom work paths; hide combustion settings for electric cars.
4. More tested cars: add an id to `tuner/cars.json`; run the per-car checks (defaults, unchanged build, edit test) before trusting it.
