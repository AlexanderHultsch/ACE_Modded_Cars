# BMW E46 drift tuner: state of the project

Updated 2026-11-12. Version 1 is built and pushed. What it does and how to use it: [../README.md](../README.md). Every setting with its default: [BMW_SETTINGS.md](BMW_SETTINGS.md). Notes for continuing in a new session: [HANDOVER.md](HANDOVER.md).

## 1. Summary

| Area | State |
|---|---|
| Goal | Change the driving settings of the BMW M3 E46 CSL in a table page, install an own tuned copy, drive, close, repeat. No cosmetics. |
| Tuner v1 | **Built and tested in scratch folders.** 71 settings in 12 groups, local web page, Apply (update my BMW) and Save as new copy, backups on every install. |
| Car loads in the game | **Confirmed** (laptop): the tuned car (named "Alex E46 Drift" at that time, now `MY_BMW M3 E46 CSL` by default) appears next to the stock E46, a session starts, the physics log line is identical to the stock car. |
| Edits reach the game | **Not confirmed yet.** A +20 hp edit (power scale 1.056, display 380 PS) is installed; the game log should report about 377 HP instead of 357.19. |
| Driving feel | **Untested.** The development laptop crashes in the renderer for every car (Intel UHD, 128 MB). Needs the gaming PC. |

## 2. What exists

| Part | File | Purpose |
|---|---|---|
| Package tool | `tools/kspkg.py` | list / extract (optional path prefix) / pack / verify `.kspkg` |
| Schema extractor | `tools/extract_protos.py` | protobuf field names out of the SDK Editor exe into `schemas/` (kept local) |
| Codec | `tools/car_json.py` | lossless decode/encode of car files to JSON with real names; 29 file types |
| Clone tool | `tools/clone_car.py` | copy the stock car under a same-length id, register it as a mod, names, pack, install with backup |
| Settings engine | `tools/tune.py`, `tuner/catalogue.json` | the settings list, defaults from the game files, state, apply, reference generator |
| Web page | `tools/tuner_server.py`, `tuner/web/index.html`, `tuner/start_tuner.bat` | table with variable name, value, description, default |
| Reference dumps | `Example mods (reference only)/decoded/` | driving data of six drift cars by Hina, as text, research only |

## 3. Design decisions (made with the user)

- One HTML table is the only editing surface; columns Variable name, Value, Description, Default (for the BMW). Local server, Windows batch start.
- 71 settings first (engine, gearing, differential, brakes/steering, springs, dampers, alignment, fuel, display/meta); more groups later.
- Apply installs only; the user starts and closes the game. Apply is refused while the game runs. A backup of the previous install is made every time.
- Own car id `ax_bmw_m3_e46_csl` (same length as the stock `ks_bmw_m3_e46_csl`); the stock car is never modified. "Save as new copy" installs further 17-character ids.
- Descriptions in English; "unverified" where the meaning is guessed from names and values.
- Defaults are read from the stock car in the game, never typed in.

## 4. How a build works

1. `init` extracts the stock BMW from the game's `content.kspkg` into the work folder (once).
2. Every Apply starts from that pristine copy, clones it under the new id by same-length text replacement (no protobuf length changes), adds the mod registration and localization, changes the chosen settings in every copy of the value (standalone file and the inline copy in `data/<id>.car`), packs, backs up the installed package and installs the new one.
3. An Apply with no changes is byte-identical to a plain clone (tested).
4. Work folder: `%USERPROFILE%\ace_modded_cars_work` (outside OneDrive and outside AppData; the Claude desktop app redirects AppData writes into a private folder the user cannot see).

## 5. What was verified

- Catalogue: every target resolves in the real E46, all copies agree (floats within 1e-5), defaults come from the files.
- Clone: the old id appears nowhere; reversing the replacement reproduces all 312 stock files byte for byte.
- Edits in scratch builds change exactly the expected values in all copies, e.g. +20 hp changes only the power curve and the display preset; `car_json.py check` has no failures.
- Server: API and input validation, Host and cross-site checks, refusal while the game runs, two copies side by side, backups.
- Game (laptop): clone appears and loads; physics log line identical to stock (357.18982 HP, 1517.65 kg, power class index 175.50609).

## 6. Open and unverified

- Do the edits reach the game? (log line for +20 hp, about 377 HP)
- Which copy does the game read when a value exists twice (standalone file or inline copy in `.car`)? Both are written, so edits work either way; the question is for understanding.
- Do the setup limits act as ranges? Stock defaults exceed stock limits in places (diff power 0.3 vs max 0.1, front anti-roll 70000 vs max 50000); the cause is unknown.
- Does `diff_type` Spool (fully locked) take effect? Do numbered copies (other ids) load?
- 32 settings are marked unverified (meaning guessed from names and values).
- Not covered yet: tyres (shared game files, a new compound would need its own file), aero, TC/ABS, bump stops, caster, damper limits, engine map values.

## 7. Next steps

1. Confirm the edits in the game (log line, or a visible value such as the starting fuel in the setup screen).
2. On the gaming PC: drive, test the Spool differential, the limits, the numbered copies, which copy is read.
3. Several cars (section 8).
4. Extend the table: tyres first (most important for drifting), then aero and electronics.
5. Polish: live build log in the page, guard against very long work paths.

## 8. Roadmap: several cars

The game has 71 cars with a data file (all ids start with `ks_`). Only the cars the user picks are ever extracted (about 0.3 GB each, never the whole 66 GB package); a shortlist file `tuner/cars.json` limits the page to supported cars.

Steps, in order:
1. **Car picker and per-car folders.** `<work>\<car_id>\base|build|tune_state.json`, backups per car, `tune.py cars` lists the available cars (id and display name from the game's `system\cars.table`), `init --car <id>` extracts one car, the page gets a car selector.
2. **Car-independent catalogue.** Targets become logical names (engine, gearbox, drivetrain, brakes, stock setup, setup limits, mechanical preset) resolved for each car through its `.car` manifest, with applicability rules: settings whose fields do not exist are hidden (turbo values on naturally aspirated cars, all-wheel-drive differentials), and the gear list follows the real gear count.
3. **Automatic id, name and registration.** Id: same length as the stock id, `ks_` replaced by `ax_` (unique per car, no clash with the BMW). Name: `MY_` plus the stock display name from `cars.table` (user can change it). Brand and year from the game data; localization lines copied from the stock `en.cars.loc` for that car with the new id (today the four lines are BMW-specific).
4. **Per-car defaults and reference.** `doc --car <id>`; the "unverified" flags and descriptions are per setting, not per car.
5. **Harden on three different cars** before widening: a rear-wheel-drive naturally aspirated one, a turbo one and an all-wheel-drive one. For each: the unchanged clone loads, its log line `POWER CLASS INDEX` equals the stock car's, an unchanged build is byte-identical to a plain clone.
6. **Shared data.** Tyres and other shared files stay referenced by path from the clone; this is also the basis for the tyre settings.

**Shortlist chosen by the user (2026-11-12):** BMW M3 E46 CSL (done), Toyota GR86 (`ks_toyota_gr86`), Mazda RX-7 FD (`ks_mazda_rx7_fd`, turbo), Alfa Romeo Giulia GTAm (`ks_alfa_romeo_giulia_gtam`), Porsche 992 GT3 R Rennsport (`ks_porsche_992_gt3_r_rennsport`, race car: expect aero, ABS/TC, sequential gearbox differences). A good spread for step 5: naturally aspirated front-engine, turbo, and a rear-engine race car.

Risks: car data layouts differ between cars (legacy fields, different file names, split engines); each new car may need small catalogue or codec additions, found by the per-car checks in step 5.
