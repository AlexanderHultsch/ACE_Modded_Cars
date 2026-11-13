# Drift tuner: state of the project

Updated 2026-11-13. The tuner works for five cars and is pushed to GitHub. What it does and how to use it: [../README.md](../README.md). Every setting per car: [settings/](settings/). Notes for continuing in a new session: [HANDOVER.md](HANDOVER.md).

## 1. Summary

| Area | State |
|---|---|
| Goal | Change the driving settings of a car in a table page, install an own tuned copy, drive, close, repeat. No cosmetics. |
| Cars | **Five tested:** BMW M3 E46 CSL, Toyota GR86, Mazda RX-7 FD, Alfa Romeo Giulia GTAm, Porsche 992 GT3 R Rennsport (the generated references use the game's own display names, for example "Mazda RX-7 FD Spirit R") (all extracted in the user's work folder). **All 71 game cars are listed** (from the game's `cars.table`, cached in `cars_index.json`), the 66 others are untested and listed under "Other Cars" until their game files are pulled; a car is pulled only when the user picks it or uses the install buttons. Six untested cars (Ferrari F40 LM, Audi Sport Quattro, Alpine A290 Beta (electric), Dallara EXP, MX-5 NA, 992 GT3 RS) extract, resolve defaults, build and pass the codec check without errors; whether they load or drive is unknown. For the electric car the combustion-engine settings are still shown. |
| First car | The BMW is installed as `BMW M3 E46 CSL_MY` with the user's first drift tune (90 settings changed against stock: differential, steering incl. rod ratio, soft springs/dampers/anti-roll bars, ride height, camber/toe/pressure, tyres, power curve, driver aids off) plus the user's own 29 L start fuel. The settings list is kept only in the user's local work folder, not in the repo. Untested in the game. |
| Tuner | **Built.** 143 settings in the catalogue in 18 groups with descriptions, 136-142 applicable per tested car; local web page (dark theme, two tabs Car Tuner and Tyre Creator, collapsible setting categories that show their description when open, a box "show advanced settings") with car selector (Installed Cars, Other Cars, Modded Cars) and install buttons; Create modded car…, Apply (update this car) and Duplicate…; several modded cars per stock car; backup on every install. |
| Own tyres | **Built, cloud-tested only:** a tyre library (Tyre Creator tab) and a garage tyre selection per modded car (Apply writes it into the package), section 4d. Tested with synthetic files only; not run on the real game files, not tried in the game. |
| Verified against the real game files | **All five cars:** extracted from the game, defaults resolved, unchanged build equals stock apart from the id rename, edits change exactly the expected values in every copy, codec check has no failures, no stock id remains in the packages. |
| Tests | 1652 tests in `tests/` (stdlib `unittest`, `python -m unittest discover -s tests`), run in the cloud without game data; they cover the tools, the settings engine, the catalogue, the server and the page on synthetic car trees. The review of 2026-11-12 is fixed except the items listed in [review/FIXES.md](review/FIXES.md). |
| Verified in the game | BMW only so far (laptop): the car appears and loads, physics log identical to stock, the +20 hp display value shows in the selector. Effects of edits on driving are **not tested yet**; the other four cars have not been loaded in the game. |

## 2. What exists

| Part | File | Purpose |
|---|---|---|
| Package tool | `tools/kspkg.py` | list / extract (path prefix) / pack / verify `.kspkg`; long Windows paths |
| Schema extractor | `tools/extract_protos.py` | protobuf field names out of the SDK Editor exe into `schemas/` (kept local) |
| Codec | `tools/car_json.py` | lossless decode/encode of car files to JSON with real names; 31 file types (incl. `.tyre`) |
| Clone tool | `tools/clone_car.py` | copy a stock car under a same-length id, register it as a mod, names, pack, install with backup |
| Raw dump | `tools/pb_raw.py`, `tools/dump_car.py` | schema-less protobuf text dump (used before the schemas existed) |
| Reference check | `tools/refgraph.py` | lists which file of an extracted car references which `content\` path (ok / MISSING / external) |
| Settings engine | `tools/tune.py`, `tuner/catalogue.json`, `tuner/cars.json` | car list, setting groups and settings list, defaults from the game files, state, apply, reference generator, tyre library and garage selection |
| Web page | `tools/tuner_server.py`, `tuner/web/index.html`, `tuner/start_tuner.bat` | Car Tuner tab: table with variable name, value, description, default, car selector, install buttons, garage tyres; Tyre Creator tab |
| Tests | `tests/` | unit and integration tests on synthetic data, no game files needed; review reports and fix list in `docs/review/` |
| Reference | `docs/settings/<car id>.md` (generated) | all settings per car |

## 3. Design decisions (made with the user)

- One HTML table is the only editing surface; columns Variable name, Value, Default, Description. Local server, Windows batch start.
- Apply installs only; the user starts and closes the game; refused while the game runs; a backup of the previous install every time.
- Each car gets its own copy under an id of the same length as the stock id: `ks_` replaced by `ax_` (`ks_bmw_m3_e46_csl` -> `ax_bmw_m3_e46_csl`). Name: the stock display name from the game's `system\cars.table` (not editable) plus a suffix the user chooses in a field next to it (setting `name_suffix`, default `_MY`, 1-30 characters; the default sorts the car next to the stock one in the game's list). The stock cars are never modified. Further modded cars of the same stock car get their own ids and suffixes (section 4c).
- Settings the car does not have are hidden (turbo values on naturally aspirated cars, gears beyond the real count, variant name when the car has none).
- Defaults are always read from the stock car in the game, never typed in. Descriptions in English; "unverified" where the meaning is guessed. Texts marked "Kunos documentation:" repeat facts from the official physics documentation of the game (section 6c); they do not change the unverified flag, which stays until the setting is tested in the game.
- Registration (brand, year, car classes) and the names in the car list come from the game's own data for that car.

## 4. How a build works

1. `init --car <id>` extracts that car (and its row from `cars.table`, and the shared stock localization once) from the game's `content.kspkg` into `%USERPROFILE%\ace_modded_cars_work\<car id>\base`.
2. Every Apply starts from that pristine copy: clone under the new id by same-length text replacement (no protobuf length changes), add the mod registration and localization, change the chosen settings in every copy of the value (standalone file and the inline copy in the car's `.car`), write the garage tyre selection when the state has one (section 4d), pack, back up the installed package, install.
3. The catalogue names files by role (`@engine`, `@gearbox`, `@drivetrain`, `@brakes`, `@setup`, `@limits`, `@car`, `@mech_preset`, `@turbo[N]`, `@clutch`, `@coilover_front`, `@coilover_rear`, `@tyre_front`, `@tyre_rear`), resolved per car through its `.car` manifest, so one catalogue serves all cars. A setting is applicable when its required targets resolve; inline `.car` copies are optional targets.
4. An Apply with no changes equals a plain clone (tested on all five cars).
5. The catalogue file has the top-level parts `groups` and `settings`. `groups` is the list of the setting groups in display order, each `{name, description}` (description 1 to 360 characters, no control characters, names unique); `load_catalogue` refuses a catalogue in which a setting's group is not listed or a listed group has no setting. Today 18 groups: Meta, Display, Engine, Turbo, Gearbox & clutch (incl. the clutch torque), Differential, Differential (hardware), Steering, Brakes, Vehicle (hardware), Springs & anti-roll, Ride height & bump stops, Dampers, Suspension (physical), Alignment & tyres (incl. caster), Tyres, Fuel, Electronics. A setting may carry the optional flag `advanced` (true or false): the page hides it unless the box "show advanced settings" is ticked or its value is changed; apply ignores the flag. Only `collar_front` and `collar_rear` have it (Kunos: the editor's Auto Setup computes the collar positions, section 6c). Setting ids and saved values did not change with the regrouping.
6. The work folder is outside OneDrive and outside AppData (the Claude desktop app redirects AppData writes into a private folder the user cannot see). Long paths (the Porsche's thumbnails exceed 260 characters) are handled with extended-length paths.

## 4b. Server

`python tools\tuner_server.py [--port N] [--work <dir>] [--mods <dir>] [--game <content.kspkg>]` serves `tuner/web/index.html` on 127.0.0.1 only (default port 8765, `--port` 1024 to 65535; `--game` is the game's `content.kspkg`). It accepts only the Host headers `127.0.0.1:<port>` and `localhost:<port>`; every POST needs the header `X-Tuner: 1` and Content-Type `application/json`. Every answer carries `X-Frame-Options: DENY` and `Content-Security-Policy: frame-ancestors 'none'`.

| Route | Purpose |
|---|---|
| `GET /` | the page |
| `GET /api/state` | work folder, car, game running, installed package, background job, all cars, number of applicable and hidden settings |
| `GET /api/settings` | applicable settings with default, value, changed flag |
| `GET /api/groups` | the setting groups of the catalogue in display order (`groups`: name, description); static, the same for every car and tune, needs no base car |
| `POST /api/set`, `/api/unset`, `/api/reset_all` | change, remove or clear values |
| `POST /api/init` | pull the car's game files (the page calls it "Install car (pull game files)"; background job, 202) |
| `POST /api/install_tested` | `init` for every tested car of `tuner/cars.json`, one after the other (background job, 202); a car that fails does not stop the others, the job then ends in state error and names the failed ids |
| `POST /api/duplicate` | copy a modded car or the draft to a new modded car; body `{car, tune, new_id?, suffix?}`, answer `{id, stock, name_suffix}` |
| `POST /api/apply` | build and install (background job, 202); body `{car, tune, new_id?, suffix?}` |
| `GET /api/tyres` | the tyre library (`tyres`) and the tyre pairs the installed cars offer (`sources`) |
| `GET /api/tyre?id=<tyre id>` | one library tyre (`tyre`) and its settings (`rows`); 400 for an unknown id |
| `POST /api/tyre_new`, `/api/tyre_rename`, `/api/tyre_source`, `/api/tyre_set`, `/api/tyre_unset`, `/api/tyre_reset`, `/api/tyre_delete` | create, rename, change the source of, set a value of, unset a value of, reset, delete a library tyre; bodies `{name, source}`, `{id, name}`, `{id, source}`, `{id, setting, value}`, `{id, setting}`, `{id}`, `{id}` |
| `GET /api/garage` | the garage of the car and tune: `choices` (key, kind, label, ticked, start), `custom`, `missing`, `car`, `tune`; needs the base car |
| `POST /api/garage_set`, `/api/garage_reset` | tick exactly the given keys (`{keys}`, at least one) or remove the selection; both answer the new garage |

All routes take an optional car id (`?car=<id>` on GET, the body field `car` on POST). All car-bound routes also take the `tune` parameter (`?tune=<x>` on GET, the field `tune` on POST): `"draft"` is the draft of the base car, a modded car id selects that modded car, absent is the default modded car `ax_<stock>`. `/api/apply` with `"tune": "draft"` creates a new modded car (`new_id` and `suffix` optional, automatic when left out) and empties the draft after a successful build; with a modded car id it updates exactly that car (`new_id` and `suffix` ignored). The old `mode` field ("new copy") is gone. `/api/state` adds `modded` (the modded cars of all stock cars), `modded_error`, `default_tune_taken`, `proposed_new_id`, `proposed_suffix` and `tune`. The tyre library routes are shared by all cars: they ignore the car and the tune and need no base car, and so does `/api/groups`; the garage routes take car and tune like the settings routes. Errors are JSON `{"error": text}` with 400 (bad input, unknown car or tyre, a tyre or garage rule broken), 403 (wrong Host, missing `X-Tuner`), 404, 405, 409 (base car missing, another job running, game running, `/api/tyre_delete` while a modded car or the draft has the tyre ticked), 413 (body over 64 KiB), 415 (not JSON) or 500. Edits, including tyre library and garage edits, are refused with 409 while a job runs; there is one job at a time for all cars, and Ctrl+C waits for a running job (a second Ctrl+C aborts it). Details: the docstring of `tools/tuner_server.py`.

## 4c. Modded cars

A modded car is a stock car plus its own tuned-car id, its own saved values and its own name suffix.

- **Id:** same length as the stock id. The first modded car takes `ax_<stock>` (for the BMW `ax_bmw_m3_e46_csl`, the "default tune"); further ones get a counter id such as `ax_bmw_m3_e46_c01`. The id can be edited in the Create and Duplicate panels.
- **Name:** stock display name plus the suffix, unique per stock car; automatic proposals are `_MY`, `_MY2`, `_MY3`. In the game's car list the entry keeps the stock brand and sits next to the stock car. Every modded car is its own mod package `<id>.kspkg` in the mods folder.
- **Files in the work folder:** `<work>\<stock id>\draft_state.json` (the values of the base car page, starts from stock defaults; emptied after a successful Create), `<work>\<stock id>\tunes\<id>\{tune_state.json, meta.json}` for each further modded car. The default modded car `ax_<stock>` keeps its legacy files `<work>\<stock id>\tune_state.json` and `build\<id>`, so the tuned car that existed before (the BMW `BMW M3 E46 CSL_MY` with the first drift tune) appears as the first entry under Modded Cars with its values unchanged.
- **Page:** dark theme only; two tabs, "Car Tuner" and "Tyre Creator" (section 4d). The selector of the Car Tuner tab has the groups "Installed Cars" (every car whose game files were pulled, tested or not), "Other Cars" (not pulled yet) and "Modded Cars" (entry text `<label> - installed` or `- not installed`); car names carry no brackets or tags. A car is pulled with the button "Install car (pull game files)" (about 20 s per car: the car's data and its shared tyre files are copied out of the game into the work folder). The header button "Install the N tested cars" (N = number of tested cars in `tuner/cars.json`, 5 today) pulls all tested cars in one background job; a car that fails does not stop the others and the job then reports which failed; the button is off while a job runs and when all tested cars are installed. The settings are in collapsible categories (Meta, Display, Engine, ...), all collapsed on load, with the buttons "Expand all" and "Collapse all"; search and "changed only" open the matching categories for as long as they are set; changed rows are highlighted blue. The page reads `GET /api/groups` once (again with the next table load only if that read failed), orders the category headers by it and shows each category's description under its header while the category is open (also when search or "changed only" opened it); if the call fails it keeps the order of the settings list and shows no descriptions. The toolbar box "show advanced settings" (off at the start, kept while the page is open) lists the settings flagged `advanced`; a changed advanced setting is listed even with the box off, and the box text counts the hidden ones. An installed car works on its draft. **Create modded car…** opens a panel with editable id and suffix and builds a NEW modded car (never overwrites). Selecting a modded car loads its values; **Apply (update this car)** updates exactly that car. **Duplicate…** copies a modded car to a new one (panel with editable id and suffix, automatic when left empty).
- **CLI:** `tune.py cars --modded`, `tune.py duplicate [--car] [--tune SRC | --draft] [--new-id] [--suffix]`, and `--tune <id>` for show / set / unset / defaults / apply.
- **No deletion in the page:** to remove a modded car delete its folder `<work>\<stock id>\tunes\<id>` and its `<id>.kspkg` in the mods folder by hand (the default one: `<work>\<stock id>\tune_state.json` and `build\<id>`).
- **Status:** tested on synthetic data only (cloud). The checks on the real work folder and in the game are open ([HANDOVER.md](HANDOVER.md) section 0, rows 16-19).

## 4d. Tyre library and garage

Own tyres in two parts: a library of tyres shared by all cars (Tyre Creator tab) and a per-car garage selection (panel "Garage tyres" in the Car Tuner tab) that decides which tyres a modded car offers in the game.

**Library tyre.** A name, a source and the changed values of the tyre settings relative to the source.
- **Format:** `<work>\tyres\<id>.json` = `{"version": 1, "name", "source": {"front", "rear"}, "values": {setting id: value}}`; only changed values are stored. `front` and `rear` are game paths of shared tyre files (below `content\cars\common_phsx`). The id is made from the name (lower case, every run of other characters one `_`, 1 to 24 characters of a-z, 0-9, `_`; a taken id gets 2, 3, ... appended); the name is 1 to 40 characters without control characters and unique ignoring case. A damaged file is listed with its error and is not offered in the garage.
- **Source:** a front/rear pair of game tyre files taken from the physic compounds of the `presets/*.compatibletyres` of an installed car (only pairs whose two files are shared game files present in that car's pulled files). The list of sources (key `<front>|<rear>`, label, cars) is built from the installed cars and needs no game access. If no installed car offers the source any more, the editor and Apply report it and ask to install a car or pick another source.
- **Settings:** the 24 tyre settings of the catalogue (targets `@tyre_front` / `@tyre_rear`: 12 front, 12 rear). The default shown is read from the source tyre file of that axle; a setting whose default cannot be read is listed as not applicable with the reason. Values are checked like the car settings (type, range warning).
- **Tab:** create (name and source), rename, change the source (values are kept), edit values, reset one value or all, delete. Delete is refused (409 in the server) while a saved state of a modded car, the default modded car included, or a draft has the tyre ticked in its garage. The values are applied per tyre file: a tyre edit takes effect on a car at its next Apply or Create.

**Garage selection.**
- **State:** the reserved key `_tyres` in the car's state (`tune_state.json` of a modded car, `draft_state.json` of the draft): an ordered list of `own:<tyre id>` (library tyre) and `stock:<front>|<rear>` (stock compound of the car, read from the presets of the car's pulled files). It is not a setting: never reported as unknown, not in `show`, not counted as applied. Duplicate and Create copy it with the rest of the state; "Reset all" of the page clears the whole state, so it drops the selection too (a modded car other than the default one keeps only its name suffix); "Reset to stock tyres" removes only the selection.
- **Order and start tyre:** own tyres first (by name, then id), then the stock compounds in the order of the car's presets. The first ticked entry is the starting tyre. At least one entry stays ticked (the CLI and the server refuse an empty selection, the page keeps the last tick).
- **Default:** no `_tyres` entry means all stock compounds ticked and the car is not touched at all (Apply as before). Ticking exactly all stock compounds and no own tyre removes the entry again. The per-car tyre settings of the table work as before.
- **Apply / Create with a selection:** the selection is checked before anything is built (a tyre that is gone, a source no installed car offers, an empty selection, a preset file that would be left without a compound are errors). The package gets `data/tyres/own_<id>_front.tyre` and `data/tyres/own_<id>_rear.tyre` for every ticked own tyre (the source files with the changed values written in; float values as 32 bit, thermal curve families as their text). The car's `frontTyreCompounds` / `rearTyreCompounds` and the `physic_compounds` of every `presets/*.compatibletyres` are rewired to the ticked tyres in order: unticked stock compounds are dropped, a stock compound keeps its entry, an own tyre is added as a copy of a template compound entry (the compound of its source pair in that file, else the first one) with its own front and rear paths; entries that no stock pair names stay at the end. All other fields of the template entry are copied unchanged.
- **With the per-car tyre settings of the table:** they still work when the car's stock default compound stays ticked (they change that compound's copy); otherwise Apply refuses with "tyre settings are changed but the stock starting tyre of the car is not ticked in the garage, tick it or reset the tyre values".
- **CLI and server:** `tune.py tyres | tyre-sources | tyre-new | tyre-show | tyre-set | tyre-unset | tyre-delete | garage | garage-set | garage-reset` (usage block of `tools/tune.py`); routes in section 4b.

**Verified in the cloud (synthetic files only):** `tests/test_tyre_library.py` and `tests/test_garage.py` (library, sources, state key, garage rules, the rewired `.car` and preset files, errors), the server routes in `tests/test_tuner_server.py`, the Tyre Creator and the garage panel in `tests/test_page.py` (headless page with a mocked API).

**Not verified (needs the PC and the game, [HANDOVER.md](HANDOVER.md) section 0, rows 20-29):** the fields of a real physic compound besides the two paths (copied unchanged from the template entry); `rear_tyre_data_paths` as list or plain string in the real files; the encoder with the changed list lengths on real files (`car_json.py check`, `_order` handling); defaults of a library tyre against the real tyre files; whether the game accepts added or removed compounds, starts on the first one, and shows distinct readable names; whether a car with a garage selection loads and drives.

## 5. What was verified

- **Real game files, all five cars:** extraction, `defaults` (exit 0; applicable/hidden with the 143-setting catalogue: BMW 137/6, GR86 138/5, RX-7 136/7, Giulia 142/1, Porsche 137/6), unchanged builds equal stock apart from the rename (all files identical, two added files: registration and localization), real edits (limiter, power curve scale, fuel) change exactly the expected values in all copies, `car_json.py check` no failures, no entry of any package contains the stock id, both copies written (for example the Giulia's turbo boost in the engine file, the `.turbo` file and the `.car`).
- **Web page** (before the dark theme, tabs and tyre work of November 2026): car selector, per-car rows, hidden-settings line, "copies differ" badge, install button for cars not yet pulled, edit/reset, apply and numbered copies (scratch folders, browser pane). The newer page parts were tested in the cloud only.
- **BMW in the game (laptop):** loads, physics identical to stock, display values show. The laptop renderer crashes for every car (Intel UHD 128 MB).
- **Cloud test suite:** `python -m unittest discover -s tests` (1652 tests) checks the tools, the settings engine and catalogue, the server routes and the page, and that the three documents agree with the catalogue (setting counts). It cannot cover the game files (extraction from `content.kspkg`, defaults and builds of the real cars), Windows behaviour (long paths, game detection, the start file, console handling) or timings; those, and everything about the game itself, need the PC (see [HANDOVER.md](HANDOVER.md) section 7 and [review/FIXES.md](review/FIXES.md)).

## 6. Open and unverified

- Do edits change the driving in the game (log line `POWER CLASS INDEX`, setup screen values, feel)? Not tested; needs the gaming PC.
- The four other cars have not been loaded in the game. Does each appear and load next to its stock car?
- Which copy does the game read when a value exists twice? Both are written. Some stock copies genuinely differ (RX-7: rev limiter cycles 11 vs 16, auto-shift 7500 vs 7000, max turbo boost 0.70 vs 0.69; shown with a badge).
- Do the setup limits act as ranges? Stock defaults exceed stock limits in places (BMW diff power 0.3 vs max 0.1).
- Does `diff_type` Spool (fully locked) take effect? Do numbered copies load?
- The RX-7 stock spring limits read 0 / 5 (looks like absent or unit-quirk data). The RX-7's real turbo cap seems to be the engine-level `max_turbo_boost`, not the per-turbo `max_boost`.
- About a third of the settings are marked unverified.
- Tyres: the per-car tyre settings of the table create the car's own tyre files only for a changed axle and rewire the `.car` and the `compatibletyres` entry of the starting compound; the other compounds stay stock as long as the car has no garage selection (with one, the garage tyres decide, section 4d). The game's choice between the `.car` and the preset entry is untested, and so is everything about library tyres and the garage selection in the game. The Tyre Creator tab shows a warning that Kunos advises against editing the tyre model values (section 6c); the settings stay available.
- Not covered yet: aero, the performance-mode list itself (modes cannot be removed, only switched to aids off), TC/ABS/ESP tables, damper limits and curves, engine map values, further turbo settings (lag, wastegate, controllers), tyre fields without a setting (groove, brush, combined factor, speed sensitivity, wear curve), suspension hard points, `controls.steerRatio` and `ffMult` in the `.car`.

## 6b. Cars, variants and names (researched in the game files)

- In the game's car list each entry is a car with its own id; its title is the display name. The selection screen shows the car's **variants** (mechanical presets) and **trim levels** (visual presets). Example GR86: Standard, Trueno Edition, Hakone Edition; they differ in body parts and display values, all show 235 hp.
- A variant (`MechanicalCarPresetData`) carries display specs, tyre compound, rims, visual presets and lists of forced / compatible **parts**; it has **no physics of its own**. The physics files (engine, gearbox, setup, ...) belong to the whole car.
- The game's mechanism for variants with different physics is **tuning parts** (`TuningPart`: engine/gearbox/drivetrain/clutch/brakes/setup/limits files, a power multiplier, ...), attached through a variant's forced parts.
- Consequences: our tuned car must be its own mod car; adding a variant to a stock car would mean changing the stock car's own package. The user decided against building saved tunes as variants (tuning parts); several tunes stay separate modded cars (own id, own package; "Create modded car…" and "Duplicate…", section 4c).

## 6c. From the Kunos physics documentation

Source: the official vendor documentation "AC EVO - Car Modding Pipeline: Physics", V1, 3 June 2026 (https://docs.assetto.cn/en/evo/car/physics/). It describes the Car Editor, not this tuner; what applies here is below. Setting texts that use it start the sentence with "Kunos documentation:". None of it is tested in the game by us ([HANDOVER.md](HANDOVER.md) section 0, rows 30-35).

- **Layers:** the `.carsetup` overrides the values of the other car files; the `.carsetuplimits` bound it. A setup value outside its limits is forced to the limit by the game and can make the car dysfunctional, even for options a player cannot adjust. The default Performance Mode can override `.carsetup` values (Kunos calls it a bug and wants to fix it; example: the 992 GT3 RS dampers), although the same page says Performance Mode settings should be dominant over other definitions.
- **Dampers:** with active dampers defined in the `.car` the damper values of the setup and the damper properties of the `.coilover` are ignored. Racing damper tables (`.dampercurves`) use a click number (a range such as 1 to 50 for 50 curves) instead of force values. Whether our five cars use force values or click numbers is open (HANDOVER, row 31).
- **Ride height and collars:** the collar positions are computed by the editor's Auto Setup from the ride height and should not be adjusted by hand; ride height is to become a result of other settings. Kunos advises converging the setup again after any change of centre of gravity, fuel tank position or mass (even 100 g). This tuner does not run Auto Setup.
- **Driver aids:** TC, ABS and ESC levels count from 0 (index 0 is "Setting 1"). For an aid to be switchable off, Setting 1 must be defined as no intervention.
- **Tyres:** the tyre editor lets you change any model value, but the code connecting them is not under user control; Kunos strongly recommends keeping the tyre as is (ideally only select the compound and initialise the dimensions). Known model issues: tyres need too much slip to grip (slow response), the slip ratio curve is too dynamic in combined grip (nervous throttle pickup), the grip effect of pressure and camber is too simple. The `.tyre` file's model parameters are listed as "not adjustable" in the file overview.
- **Crashes:** a car has about 500 data points; an error in one of them or in a link can crash the game. A field created under a dropdown and left empty becomes NaN. Very high or very low values are the main cause of crashes. Watch the game log.
- **Units:** SI base units (metres, kilograms, seconds, newtons) unless stated otherwise.
- **`max_turbo_boost`** has no physical effect (reference for gameplay and audio); the boost of each turbo is the real cap.

File overview as Kunos lists it (names as on that page; the codec in `tools/car_json.py` knows the extensions in its `TYPES`, for example `carengine` for the engine file):

| File | Role |
|---|---|
| `.car` | main file, links all other car parts |
| `.coilover` | front and rear dampers: bump stop data, damper speed thresholds, progressive spring rate |
| `.suspension` | suspension geometry |
| `.drivetrain` | drive axle and differential data |
| `.gearbox` | gearbox type, ratios, behaviour, shift assists |
| `.clutch` | clutch |
| `.engine` | type, power and coast curves, engine maps, throttle shapes, turbo and controllers, Push2Pass, launch control, battery |
| `.turbo` | turbo definitions |
| `.brakesystem` | brake capacity, electronic bias controllers, brake steer |
| `.brake` | brake pad and disc properties |
| `.tyre` | dimensions, initialisation, model parameters |
| `.wing` | aero components |
| `.surface3d` | ride-height based aero map |
| `.carsetuplimits` | allowed ranges of the setup variables |
| `.carsetup` | values of all adjustable and non-adjustable components |
| `.curve` | multi-purpose lookup table |
| `.dampercurves` | wrapper around several `.curve` files (damper speed to force) |

## 7. Next steps

0. PC verification of the page, the tyre library and the garage selection: [HANDOVER.md](HANDOVER.md) section 0a and section 0, rows 20-35.
1. Test in the game on the gaming PC: load each of the five cars, drive, confirm that edits take effect, test Spool, the limits, numbered copies.
2. The gaps found by the analysis ([settings/coverage.md](settings/coverage.md)) are closed for tyres, steering rod ratio, driver aids, hardware differential, ride height and bump stops, physical coilover / anti-roll values, caster, brake bias and clutch torque. Open: which layer wins (setup values or physical values; Kunos' statement is in section 6c), and the not-covered list in section 6. Then aero, more turbo settings, remaining tyre fields. Settings the Kunos page lists that the catalogue lacks are collected in [HANDOVER.md](HANDOVER.md) section 0a.
3. Polish: live build log in the page, job state per car, a guard against very long custom work paths; hide combustion settings for electric cars.
4. More tested cars: add an id to `tuner/cars.json`; run the per-car checks (defaults, unchanged build, edit test) before trusting it.
