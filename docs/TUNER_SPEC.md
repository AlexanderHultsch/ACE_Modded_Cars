# Specification: BMW E46 drift tuner

Status: agreed design, not built yet (decisions of 2026-11-11). Blocked on the game download (E46 source files).
Process rule: Claude plans and reviews, subagents write all code under the executor contract; one verified step at a time.

## 1. Goal and loop

Understand and quickly change the settings of one car, the BMW M3 E46, without touching the stock car:

1. Open the tuner page (local), change values in a table, press Apply.
2. The tool builds and installs the tuned BMW into `%USERPROFILE%\Saved Games\ACE\mods\`.
3. The user starts the game, drives a lap, closes the game, and repeats.

Out of scope for v1: other cars, online play, tracks, 3D/visual changes, starting or closing the game.

## 2. Decisions

| Topic | Decision |
|---|---|
| Interface | One local HTML page, a table. The page is the only place the user edits (no text file for the user). |
| Table columns | Variable name, Value, Description, Default (for the BMW). |
| Scope v1 | Essentials: about 40-60 drift-relevant settings. An "all settings" view comes later. |
| Apply | Install only. The user starts and closes the game. A backup of the previous install is made every time. |
| Car identity | Own car id (working name `alex_e46_drift`); the stock `ks_bmw_m3_e46` is never modified. |
| Apply modes | Default "Update my tuned BMW" (replaces the installed one). Second button "Save as new copy" (numbered id, e.g. `alex_e46_drift_02`). |
| Descriptions | English. Entries whose meaning is guessed from names and values carry an `unverified` flag shown in the table. |
| Base data | Kunos `ks_bmw_m3_e46` from the installed game. Defaults are read from those files, not typed in. |

## 3. Architecture

```
game content.kspkg --kspkg.py extract--> work/base/        (E46 files, git-ignored)
settings catalogue  (which settings, group, unit, description, verified flag)
work/tune_state.json (values the user changed; hidden, git-ignored)

browser page  <--HTTP, 127.0.0.1 only-->  local server (stdlib http.server)
                                              |
   Apply: copy base -> rename to new car id -> car_json decode -> set values -> encode
          -> kspkg.py pack -> backup old install -> copy to mods folder
```

Existing building blocks (committed): `tools/kspkg.py` (list/extract/pack/verify), `tools/extract_protos.py` (schema from the SDK Editor exe into `schemas/`), `tools/car_json.py` (decode/encode with real field names, byte-exact round trip).
To build (final file layout is set by the build plan): settings catalogue, base extraction step, car-id renamer, build/pack/install step with backup, local server, HTML page.

## 4. Settings catalogue

One entry per setting: `id`, `group` (Engine, Turbo, Drivetrain, Gearing, Steering/Setup limits, Brakes, Tyres, ...), `file` (which car file), `path` (field path in the `car_json` representation), `type`, `unit`, `description`, `verified` (true/false), `hint` (sensible range, optional). `default` is filled by reading the base car, never hand-typed.
Derived settings are allowed where one table row changes many values, e.g. `torque_scale` multiplies every point of the power curve (the easiest power lever).

Draft essentials (names from the extracted schema; to be confirmed against the real E46 files):

- Engine (`EngineData`): `limiter`, `minimum` (idle), `limiterCycles`, `inertia`, power-curve scale, `throttle_lag_up` / `throttle_lag_dn`.
- Turbo (`TurboData`, if the BMW has none this group is hidden): `max_boost`, `lag_UP`, `lag_DN`, `rpm_Ref`, `wastegate`, `max_turbo_boost`.
- Differential: `differential_data.power`, `.coast`, `.preload` (also default in `.carsetup`, range in `.carsetuplimits`; all three must be changed together).
- Gearing: gear ratios, final drive, auto-shift rpm.
- Setup limits (`CarSetupDataLimits`): diff ranges, preload range, steering ratio/lock, brake bias range, so the in-game setup screen allows the new values.
- Setup defaults (`CarSetupData`): spring/damper rates, camber, toe, tyre pressure, brake bias.
- Tyres: only what the real files expose; verify after extraction.
- Display text (`.mechanicalcarpreset` stats, car name) is cosmetic; the tool should offer the name only.

## 5. Build pipeline rules

1. Never modify the game folder or the stock car. Write only to `work/` and the mods folder.
2. Rename the car id in every path inside the copied files and in the package (folder, `cardata.car` refs, presets, loc), including the UI loc keys. A script must verify that no old id remains.
3. Edit only through `car_json` (decode, change by field path, encode). Settings that live in more than one file (diff) are changed in every copy; `cardata.car` inline copies are kept in sync.
4. Pack with `kspkg.py pack`; run `kspkg.py verify` against the extracted tree.
5. Backup: before replacing an installed package, copy it to `work/backups/<id>_<timestamp>.kspkg`.
6. The server listens on 127.0.0.1 only and accepts only the configured paths.
7. No vendor data in git: `schemas/`, `work/`, base car files and `*.kspkg` stay ignored.

## 6. Acceptance tests (per component)

- Catalogue: every `path` resolves in the base E46 decoded JSON; every `default` equals the base value.
- Rename: unpacked output contains zero occurrences of the old car id (grep).
- Build: with no edits, the built package verifies content-identical to the base apart from the id rename; with one edit, exactly the expected values differ.
- Server/page: starts, shows the table, lists defaults, marks changed rows, Apply returns the installed path and backup path.
- In game (manual, by the user): the tuned car appears next to the stock E46, loads, shows the edited value in the setup screen or in behaviour.

## 7. Open risks and questions

- Do the real game files fit the Editor schema? The older mod files did not for `.car`, `.drivetrain`, `.gearbox`, `.clutch`, `.suspension`, `.tyre`, `.rimmesh`, `.tyremesh`, `.actor` (see `mod_examples/ANALYSIS.md`). If the E46 files do not fit either, a decision is needed: map on a relaxed fit (unknown fields preserved) or keep those files out of the table.
- Does the game load a packed car under a new id that is not in its own tables? (First test: repack the unchanged E46 as `alex_e46_drift`.)
- Which copy wins when the same value exists twice (drivetrain vs `.carsetup`, drivetrain gears vs `.gearbox`)? Plan: change all copies; learn the rule from in-game tests.
- Does the game accept our pack variant (lower-cased paths, no XOR flags)? The unchanged-repack test covers it.
- Descriptions are not from official documentation; unverified ones are flagged.
