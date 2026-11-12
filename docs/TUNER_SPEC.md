# Specification: BMW E46 drift tuner

Status: v1 built and committed (2026-11-12). Settings reference: [BMW_SETTINGS.md](BMW_SETTINGS.md) (generated). Still open: in-game confirmation of what the game reads (section 7).
Process rule: Claude plans and reviews, subagents write all code under the executor contract; one verified step at a time.

## 1. Goal and loop

Understand and quickly change the settings of one car, the BMW M3 E46 CSL, without touching the stock car:

1. Start the tuner (`tuner\start_tuner.bat`), change values in the table, press Apply.
2. The tool builds the tuned BMW from the pristine stock files and installs it into `%USERPROFILE%\Saved Games\ACE\mods\`.
3. The user closes the game if it runs, starts it, drives a lap, closes it, and repeats.

Out of scope for v1: other cars, online play, tracks, 3D/visual changes, starting or closing the game.

## 2. Decisions

| Topic | Decision |
|---|---|
| Interface | One local HTML page, a table; the page is the only place the user edits. |
| Table columns | Variable name, Value, Description, Default (for the BMW). |
| Scope v1 | 71 settings in 12 groups (engine, gearing, differential, brakes/steering, springs, dampers, alignment, fuel, display/meta). |
| Apply | Install only; the user starts and closes the game. A backup of the previous install is made every time. Apply is refused while the game runs. |
| Car identity | Own car id `ax_bmw_m3_e46_csl` (same length as the stock `ks_bmw_m3_e46_csl`); the stock car is never modified. |
| Apply modes | "Apply (update my BMW)" replaces the installed tuned car. "Save as new copy" installs another 17-character id next to it. |
| Descriptions | English. `verified` false = meaning guessed from names and values; shown as an "unverified" badge. |
| Base data | The stock E46 from the game's `content.kspkg`; every default is read from those files. |

## 3. Architecture (as built)

```
game content.kspkg --kspkg.py extract (prefix)--> <work>\base\content\cars\ks_bmw_m3_e46_csl   (tune.py init, once)
tuner\catalogue.json   settings list: id, group, label, kind, type, unit, description, verified, min/max, targets
<work>\tune_state.json values the user changed

browser page <--HTTP 127.0.0.1 only--> tools\tuner_server.py (stdlib http.server, one background job)
                                          |  imports tools\tune.py
   apply: clone_car.build (copy base -> same-length id, registration, localization, no pack)
          -> for every changed setting: car_json decode target file, set path, encode (ALL copies)
          -> kspkg pack -> clone_car.install (backup + copy to mods folder)
```

Work folder: `%USERPROFILE%\ace_modded_cars_work` (`--work` overrides): `base\`, `build\<id>\`, `backups\`, `tune_state.json`, `defaults.json`. It is deliberately outside AppData (the Claude desktop app redirects its AppData writes into a private folder, invisible to the user's terminal) and outside OneDrive (hundreds of MB of temporary data).

Files: `tools/kspkg.py` (packages, extract with path prefix), `tools/extract_protos.py` (schemas from the SDK Editor exe into `schemas/`), `tools/car_json.py` (lossless decode/encode, 29 extensions mapped, legacy fields and wire-type conflicts preserved under `_unknown`), `tools/clone_car.py` (clone under a same-length id, `.moddedcarcontent`, `uiresources\localization\en.cars.loc`, pack, install with backup), `tools/tune.py` (catalogue, state, defaults, set, apply, doc), `tools/tuner_server.py` (JSON API + job), `tuner/web/index.html` (the table page), `tuner/start_tuner.bat`.

## 4. Settings catalogue

One entry per setting: `id`, `group`, `label`, `kind` (`value`, `curve_scale`, `meta`), `type` (int, float, string, enum), `unit`, `description`, `verified`, optional `min`/`max` (soft hints, warnings only), and `targets` (file + field path inside the decoded JSON; dotted names, `[n]` list index, `[key=VALUE]` selector). A setting lists EVERY copy of a value: the standalone file and the inline copy inside `data/ks_bmw_m3_e46_csl.car` (the game's choice between them is not known yet). `default` is read from the base car; absent fields count as the proto3 default and are flagged. `power_scale` and `coast_scale` multiply every point of the engine's power / coast curve. Settings whose value exists for several wheels (springs, dampers, camber, toe, pressure) write all wheels of the axle.
The reference with defaults and descriptions is generated: `python tools/tune.py doc` -> `docs/BMW_SETTINGS.md`.

## 5. Build pipeline rules

1. Never modify the game folder, the SDK folder or the stock car. Write only to the work folder and the mods folder.
2. Every Apply starts from the pristine base: clone under the new id by same-length byte replacement (no length prefix changes), apply the changed settings, pack. An unchanged Apply is byte-identical to a plain clone (tested).
3. Edit only through `car_json` (decode, change by field path, encode).
4. Backup: before replacing an installed package, copy it to `<work>\backups\<id>_<timestamp>.kspkg`.
5. The server listens on 127.0.0.1 only, checks the Host header, and requires header `X-Tuner: 1` and JSON content type on every POST.
6. No vendor data in git: `schemas/`, the work folder, base car files and `*.kspkg` stay out of the repo.

## 6. Verification and tests done

- Catalogue: every target resolves in the real E46; all copies agree (floats within 1e-5 relative); defaults come from the files.
- Clone: no occurrence of the old id remains in names or contents; reverse replacement reproduces every stock file byte for byte (312 files).
- Edit tests (scratch folders): +20 hp edit changes exactly the power curve and the preset; setup, engine, gearbox, drivetrain, brake edits change exactly the expected values in all copies; `car_json.py check` has no failures.
- Server: API, input validation, Host/CSRF checks, game-running refusal, two copies side by side, backups.
- In game (laptop): the clone appears next to the stock car; physics log line identical to stock (see section 7).

## 7. Knowledge and open questions

- **Verification without driving:** at session start the game writes to `Saved Games\ACE\Logs\log-*.txt` lines such as `Creating car: ax_bmw_m3_e46_csl` and `POWER CLASS INDEX: 175.50609 (ax_bmw_m3_e46_csl) PW:266356.8 (357.18982 HP) W:1517.65`. Real power and mass changes can be checked there even if the renderer crashes. The unchanged clone matched the stock car exactly. Expected for the +20 hp edit (power_scale 1.056): about 377 HP. Not yet confirmed.
- The development laptop crashes in the render thread (Intel UHD Graphics, 128 MB) with stock cars too; the mod is not the cause.
- Which copy the game reads (standalone files vs inline copy in `.car`) is unknown; the tuner writes both.
- The E46 `.drivetrain` file holds a second, older gear set in fields outside the schema; the schema-known set is in `.gearbox`. The tuner changes the `.gearbox` set and its inline copy.
- Stock setup defaults exceed some stock limits (diff power 0.3 vs max 0.1, front anti-roll 70000 vs max 50000, some dampers). Effect of the limit settings in the game is untested.
- `diff_type` Spool (fully locked) and `engine_damage_rpm` etc. are untested in the game.
- Does the game load the numbered copies (other ids)? Only the default id was tested in the game.
- Not covered yet: tyre model/compounds (shared game files), aero, TC/ABS, bump stops, caster, damper limits, engine map values.
