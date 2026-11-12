# HANDOVER: continuing the work in a new session (local or cloud)

Read this first in a new session, then [TUNER_SPEC.md](TUNER_SPEC.md) (state of the project). User-facing usage is in [../README.md](../README.md), every setting per car in [settings/](settings/). Owner: Alex (GitHub AlexanderHultsch). Last updated 2026-11-12.

## 1. The project in short

A local table page to tune Assetto Corsa EVO cars for drifting: read a car's data with real field names, change values, build an own copy of the car under an `ax_` id (shown as the stock name plus a user-chosen suffix, default `_MY`, setting `name_suffix`; the page header shows the stock name with the suffix field next to it; the page title is `ACE - Simple Car Tuner`), install it in the game's mods folder, drive, repeat. Driving settings only, no cosmetics. Five cars: BMW M3 E46 CSL, Toyota GR86, Mazda RX-7 FD, Alfa Romeo Giulia GTAm, Porsche 992 GT3 R Rennsport (list in `tuner/cars.json`). The tuner is built and verified against the real game files for all five (143 settings in the catalogue, 136-142 applicable per tested car; last code commit `f960ef7`). The user's first car is installed: `BMW M3 E46 CSL_MY` = Hina's Drift Club drift setup recreated (90 settings against stock) plus the user's own 29 L start fuel; it matched her package on 136 of 137 settings. In the game only the BMW has been loaded so far (laptop, display values; the laptop renderer crashes for every car). **Nothing has been driven yet.** Open: do edits take effect and how do they drive; which layer the game reads; do the other four cars load.

## 2. Where you are working: local or cloud

| | Local session (Alex's Windows PC) | Cloud session |
|---|---|---|
| Repo | the working folder | a fresh checkout of GitHub `main` |
| Game, SDK, mods folder, logs | available (Steam folder, `Saved Games\ACE`) | **not available** |
| Can do | everything: extract cars, build, install, read game logs, run the tuner page | code and docs work that needs only the repo; analysis of text files |
| Cannot do | | extract from the game, create `schemas/` (git-ignored, regenerated locally), install, any test with real game files |

State that lives only on the local PC and is not in git: `schemas/` (from the SDK Editor exe), the work folder `%USERPROFILE%\ace_modded_cars_work` (per car: `<car id>\base`, `build`, `tune_state.json`, `stock_info.json`; shared `backups\`, `stock_loc\` and `cars_index.json`; the five tested cars are extracted), the installed packages in `Saved Games\ACE\mods\` (currently `ax_bmw_m3_e46_csl.kspkg` = `BMW M3 E46 CSL_MY` with the recreated Hina drift setup and 29 L fuel; the previous +20 hp test package is in `backups\`), and game logs. The BMW's `tune_state.json` holds the 90-entry Hina recreation (the earlier state is saved next to it as `tune_state.before_hina.json`); that state file contains her values and is therefore never committed. Scratch copies of it, of the extracted Hina package and of the comparison scripts live in `%LOCALAPPDATA%\Temp\q24` / `q23` (may be gone; the work folder state is the source of truth). The user's tuner window (old single-car version) may still be running on port 8765: it must be closed and restarted (`tuner\start_tuner.bat`) to get the current multi-car version with the new settings; the work folder layout migrated already (nothing was deleted). To hand over to the cloud: commit and push first. To come back to the local PC: pull; re-run `tools\extract_protos.py` only if `schemas/` is missing.

Local setup: Python 3.12 (not on PATH): `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`, run tools with `-I`. Git for Windows installed; commits use the GitHub noreply address. In PowerShell 5.1 pass multi-line commit messages through a file (`git commit -F`): quotes inside here-strings break the argument list. **Gotcha:** the Claude desktop app writes under `AppData\Local` into a private redirected folder that the user's own terminal cannot see; keep work data outside AppData (and outside OneDrive).

## 3. Working rules

- Process: Claude plans and reviews; subagents write all code under the user's "executor contract" (stock general-purpose subagent, model haiku for mechanical one or two file jobs, sonnet where judgment is needed; the contract text is copied verbatim into every delegation). One step at a time; the parent runs the verification itself and reads the diff; never accept a green run reached by weakening a test. Show a plan and wait for the user's OK before building, unless the user asks to run uninterrupted.
- Vendor data stays out of git: `schemas/`, the work folder, `*.kspkg`, game and SDK files. Third-party mods are not kept in the repo.
- Test with scratch folders (`--work <short dir>`, `--mods <dir>`); never touch the real work folder's state, the real mods folder, the game folder, the SDK folder or the stock cars while testing. The game may be running: the tuner refuses to install then. Always back up before replacing a package (the tools do).
- Edit car data only through `tools/car_json.py` (lossless). A setting changes every copy of a value.
- Do not use `Nenkai/ACEvo.Package` (its AGENTS.md prohibits use by AI tools).
- Do not publish tuned derivatives of Kunos' or Hina's cars. Hina's actual setting values (the recreation's state file, her extracted package) stay local and are not committed; the repo only holds the by-name comparison in `docs/drift-setup-comparison.md`. Credits: Hina's Drift Club 1.4 (Hina, OverTake.gg), Kunos Simulazioni (game and data). The repo holds tools, the settings catalogue, generated settings references with default values and text dumps of driving data; no game assets or packages.
- The development laptop (Intel UHD 128 MB) crashes in the renderer for every car; there, judge only by the game log.

## 4. Repo layout

```
README.md                    user guide
docs/TUNER_SPEC.md           state of the project
docs/HANDOVER.md             this file
docs/settings/<car id>.md    generated by `python tools/tune.py doc --all`: every setting, default, description
docs/settings/coverage.md    analysis: which game settings the tuner covers and which not
docs/drift-setup-comparison.md   stock BMW versus Hina's drift E46, what changed and why it matters
tools/                       kspkg, extract_protos, car_json, clone_car, tune, tuner_server, pb_raw, dump_car
tuner/                       cars.json (tested cars), catalogue.json (settings), web/index.html, start_tuner.bat
Example mods (reference only)/decoded/<car>/   driving data of six drift cars by Hina, text dumps, research only
Example mods (reference only)/hdc_e46_vs_stock.md   60 largest differences, stock versus HDC E46 (numbers)
.gitignore, .gitattributes   vendor data (schemas/, *.kspkg, work/) and line endings
```

## 5. Key knowledge

- **Loading mod cars:** one `.kspkg` directly in `%USERPROFILE%\Saved Games\ACE\mods\`. A mod car needs `content\cars\<id>\<id>.moddedcarcontent` (ModdedCarContentData: display name, brand, year, property_1/2/3 = classes) and its names in `content\cars\<id>\uiresources\localization\en.cars.loc` (CRLF, UTF-8, no BOM; copied from the game's stock `en.cars.loc` lines of that car with the new id); without it the selection screen shows raw keys. Cars need no patching of the game's own package. Single player only.
- **Stock registration data:** the game's `system\cars.table` (TableData -> preset.lines[].car_content, CarContentData) has name, display_name, brand, year, properties for each of the 71 cars; the tool stores them in `stock_info.json` per car. A missing property means the enum default (Road / Modern / ICE).
- **All cars listed:** the selector shows all 71 game cars (names from `cars.table`, cached in `<work>\cars_index.json`); `tuner/cars.json` is only the list of TESTED cars (five). Untested cars (six tried: F40 LM, Audi Sport Quattro, Alpine A290 (electric), Dallara EXP, MX-5 NA, 992 GT3 RS) extract, resolve and build without errors; loading and driving unknown; the electric car still shows combustion settings.
- **Variants vs cars (researched):** a game car has variants (mechanical presets: body parts and display specs, no physics) and trim levels (visual presets). Physics belongs to the whole car; the game's way to give variants different physics is tuning parts (`TuningPart`, referenced by a variant's forced parts; Hina's AE86 uses it). So the tuned car is its own mod car (stock car's package must not change). The user decided against saving tunes as variants; tunes stay separate copy cars.
- **Clone trick:** the id is replaced everywhere by a same-length id (`ks_` -> `ax_`), so no protobuf length prefix changes. The id appears inside `.mesh`, `.actor`, `.car` and others. All 71 game car ids start with `ks_`.
- **Car manifest:** each car's `.car` (CarData; file name varies: `<id>.car`, `cardata.car`, `<id>_car.car`) has `engine_path`, `drivetrain_path`, `gearbox_path`, `clutch_path`, `brakes_path`, `stock_setup`, `setupLimits` (mixed-case paths) and embeds inline copies of engine, gearbox, drivetrain, brakes. The catalogue uses these as roles (`@engine`, `@gearbox`, `@setup`, `@limits`, `@car`, `@mech_preset`, `@turbo[N]`). Which copy the game reads is unknown; the tuner writes both. Some stock copies differ (RX-7).
- **`.kspkg`:** 64 MiB file table at the end, XOR key `c135117da921979f`, 256-byte entries (path, flags 1 = directory / 0x100 = data XOR'd, FNV-1a 64 hash of the lower-case path as UTF-16LE, size, offset); the game's `content.kspkg` (66 GB) uses the same format, all files XOR-flagged; our `pack` variant (flags 0, lower-case paths) is accepted by the game. Windows paths over 260 characters occur (Porsche thumbnails): kspkg/clone/tune use extended-length paths.
- **Schemas:** the SDK Editor exe (and the game exe) embed the protobuf descriptors; `tools/extract_protos.py` writes them to `schemas/`. Real game files also contain "legacy tail" fields beyond the schema (second gear set in `.drivetrain`, foreign car names): preserved in `_unknown`. Unmapped `car_json` types: `.actor`, `.cardisplaysystem`, `.carwipersystem`, `.tyremesh`. `.tyre` (TyresCompoundData) is mapped; tyre files are shared under `content\cars\common_phsx` and are extracted into `<base>\content\cars\common_phsx` by `init` / lazily; a changed tyre becomes the car's own file under `data\tyres\`.
- **Catalogue mechanics** (`tuner/catalogue.json`, see `tune.py` docstring): targets name a role and a dotted JSON path (`[n]` index, `[key=VALUE]` selector); `optional` targets (inline `.car` copies) are written only when present; `needs` guards applicability; `hide_if_absent`; `default_template` for the variant name (`{stock_variant_name}`); `[*]` wildcard in paths (all elements), `create_missing` (absent intermediate objects are created on write), kind `flag` (bool that writes a fixed value, e.g. `driver_aids_off`), `choice_values` (enum choice name to written text, e.g. thermal curve families), roles `@clutch`, `@coilover_front/@coilover_rear`, `@tyre_front/@tyre_rear`; a setting is applicable when its required targets resolve; unknown ids in a saved state are ignored with a warning.
- **Verify power/mass without driving:** the newest `Saved Games\ACE\Logs\log-*.txt` has `Creating car: <id>` and `POWER CLASS INDEX: ... (357.18982 HP) W:1517.65` at session start. Unchanged clone and stock match exactly (BMW).
- **Driving data reference:** `Example mods (reference only)/decoded/<car>/` has only physics and setup dumps with field numbers (made before the schemas); use `car_json.py` on real files for names.

- **Tyres:** `.tyre` files (TyresCompoundData) are shared; a changed axle gets the car's own `data\tyres\<new id>_front/_rear.tyre`, and the `.car` (`frontTyreCompounds/rearTyreCompounds`) plus the `compatibletyres` entry of the stock-default compound are rewired to it. Only the starting compound changes; the garage's other compounds stay stock. Thermal curve is a choice setting (curve families, e.g. supercar). 24 tyre settings in total, 12 per axle.
- **Hina recreation, known differences:** coast curve scale also moves 5 low-rpm points she left unscaled; rear thermal curve near match (identical to 95 °C, up to 0.014 higher above); not reproduced: front strut hard points (version drift), her single "Drift" performance mode (we switch driver aids off in the stock modes via `driver_aids_off`), her narrow setup limit windows (we widen the stock windows only where her values fall outside: diff power/coast max 1.0, front camber min -4, rear camber max 0), wear curve, some unnamed tyre fields, `controls.steerRatio`/`ffMult` in the `.car`.
- **Check an install without driving:** after `tune.py apply` compare installed vs built hash, run `car_json.py check`, confirm the registration display name and that no package path contains the stock id (done for the BMW before the first install).

## 6. Open questions

- Do edits take effect and change the feel (log line, setup screen, driving)? Does the Hina recreation drive like her car? Do the four other cars load next to their stock cars?
- Which layer wins where setup values and physical values both exist (setup springs/dampers/ARB vs coilover and ARB stiffness in the car files; setup ride height vs physical)? The tuner writes both. Does the game read the car's own tyre file at all?
- Which copy of duplicated data does the game read; does it enforce the setup limits as ranges (stock defaults exceed some stock limits); does `diff_type` Spool apply; do numbered copies load?
- RX-7: is the engine-level `max_turbo_boost` the real boost cap (the per-turbo `max_boost` is absent)? Its stock spring limits read 0 / 5.
- Which unnamed legacy fields matter?

## 7. Next steps

1. Test on the gaming PC: load `BMW M3 E46 CSL_MY` (selector shows 380 PS, log `POWER CLASS INDEX` about 380 HP), drive it, compare with Hina's mod if wanted; then load the other four cars, check that edits take effect, test Spool, limits, numbered copies, and find out which layer wins. 2. Closed already: tyres, steering rod ratio, driver aids, hardware differential, ride height and bump stops, physical coilover/ARB values, caster, brake bias, clutch torque. Still not covered: aero, the performance-mode list, TC/ABS/ESP tables, damper limits and curves, engine maps, further turbo settings, remaining tyre fields, hard points, `controls.steerRatio`/`ffMult` (see `docs/settings/coverage.md`). 3. Polish: live build log, job state per car, long-path guard for custom work paths. 4. More cars: add to `tuner/cars.json` and run the per-car checks (defaults, unchanged build equals stock, edit test).
