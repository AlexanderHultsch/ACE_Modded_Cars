# HANDOVER: AC EVO car modding (drift focus)

Owner: Alex (GitHub: AlexanderHultsch). Game: Assetto Corsa EVO (Steam, Early Access 0.9.x), Windows PC.
Last updated 2026-11-11. Current target: a local HTML tuner for the BMW M3 E46, see [docs/TUNER_SPEC.md](docs/TUNER_SPEC.md).

## 1. Goal

Reuse an existing AC EVO car and change only its specs to get a fun drift car: more power (torque curve / turbo boost), locked differential (power/coast, preload), wider setup ranges (steering, diff), keep model and sounds untouched.

End state: understand all settings of the BMW E46 and change them quickly in a table page: edit, install, drive one lap, close the game, edit again. Own car id, stock car never touched.

## 2. Status

| Step | Status |
|---|---|
| Unpack `.kspkg` (0.7+ format) | done: `tools/kspkg.py extract` (handles the XOR flag) |
| Repack `.kspkg` | done: `tools/kspkg.py pack`; HDC packages repacked byte-identical (AE86 content-identical); of the 3 example mods Honda and Daytona content-identical (1 MiB smaller), Nissan differs (case, XOR flags, dirs, layout) |
| Decode car data (schema-less) | done: `tools/pb_raw.py`, `tools/dump_car.py` |
| Field names (schema) | **done 2026-11-11**: `tools/extract_protos.py` pulls 99 descriptors out of the SDK Editor exe into `schemas/` (git-ignored); CarData, CarSetup, CarSetupLimits, TyresData included |
| Edit by name and re-encode | **done for 14 file types**: `tools/car_json.py` (decode/encode/check/types); 176 files round-trip byte-exact; edit demo changed exactly 2 bytes. 17 other extensions do not fit the schema strictly (see section 6) |
| Tuner (page + install) | specified in `docs/TUNER_SPEC.md`, not built; waits for the game download (E46 source files) |
| Game loads a repacked / edited package | open: **untested** |

The SDK (`Assetto Corsa EVO SDK`) contains `AssettoCorsaEVOEditor.exe` and `sdk.kspkg` (shared `common_phsx` tyre data, common assets, modding sample); no documentation files.

## 3. Repo layout

```
README.md, HANDOVER.md, CLAUDE.md, NOTICE.md
docs/TUNER_SPEC.md          specification of the tuner (decisions, architecture, tests, risks)
tools/
  kspkg.py                  list / extract / pack / verify .kspkg (stdlib only)
  pb_raw.py                 schema-less protobuf dumper
  dump_car.py               dump every physics/config file of an extracted car to .txt
  extract_protos.py         extract the embedded protobuf schemas from an exe -> schemas/
  car_json.py               schema-driven lossless decode/encode of car files <-> JSON
hdc_1.4/decoded/<car>/      schema-less dumps of Hina's Drift Club cars (the packages, payload and
                            extracted files were removed 2026-11-11; they remain in git history before
                            commit 19f9817 and in Hina's download, see NOTICE.md)
mod_examples/               (untracked, local only) 3 example mods, pruned, see ANALYSIS.md
schemas/                    (git-ignored) generated .proto files + acevo.desc, vendor property
work/                       (git-ignored) scratch: extractions, builds, backups
```

Local Windows setup: Python 3.12 is installed but not on PATH: `C:\Users\alexa\AppData\Local\Programs\Python\Python312\python.exe`; run tools with `-I`. Git for Windows is installed.

HDC car ids: ae86 = ks_ae86_beginner_h_01 (Kunos id reused), datsun = hdc_datsun_240z_01, e46 = hdc_bmw_e46_01 (Kunos `ks_bmw_m3_e46` data), mercedes = hdc_mercedes_190e_01, rx7 = hdc_rx7_fd_01, s2000 = hdc_honda_s2000_ap1_01.

## 4. How EVO loads mod cars

- One `.kspkg` per car directly in `%USERPROFILE%\Saved Games\ACE\mods\` (no subfolder).
- UI files: HDC ships loose `uiresources/localization/cars/<car_id>/...` and `uiresources/branding/oem/<brand>/...` in the mods folder. The Honda/Nissan packages carry them inside (`content\cars\<id>\uiresources\...`, Nissan also `uiresources\branding\oem\evoforge` at the package root). Loose files are therefore not required (untested in game).
- The car's **live files are named by `data/cardata.car`**: fields 16 limits, 19 setup, 20 engine, 22 drivetrain, 24 gearbox, 26 clutch, 27 brakes, 29 AI, 77 electronics. Other loose files may be dead variants (section 10). `cardata.car` also embeds inline copies of the referenced components (path field N, inline copy N+1).
- Cars need no patching of the game's `content.kspkg` (only tracks do). Mod cars reference Kunos meshes, sounds, materials and even data curves (`ks_abarth_695_biposto\...`) by path.
- Possibly loose unpacked cars in the mods folder load too (untested).
- Online: since 0.8.1 servers reject mods not re-exported through the SDK. Single-player only.
- A Kunos modding skeleton car `ks_modded_car` exists (Daytona files are named `ks_modded_car.*`, EvoForge uses it as source; presets `modded_car_*`, brand `modded_brand`, `.moddedcarcontent`).

## 5. .kspkg format (0.7+ mod packages)

Verified on 6 HDC and 3 example packages (table, key, hash and entry layout identical in all 9, plus the SDK package `sdk.kspkg` lists with the same tool). The game reads strictly through the table.

```
[0, 0x100000)          1 MiB header, all zero (HDC/Honda/Daytona style; Nissan has none)
[0x100000, data_end)   file data, contiguous, largest file first (HDC style), zero padding to 1 MiB
[size-64MiB, size)     file table: 256-byte entries sorted ascending by hash, rest zero.
                       Whole 64 MiB XOR'd with 8-byte key c135117da921979f (repeating from table start)
entry +0x00  path, utf8, backslashes, <= 0xE0 bytes, zero padded
      +0xE4  int16 flags: 1 = directory, 0x100 = file data XOR'd with the same key (repeating from file start)
      +0xE6  int16 path length
      +0xE8  uint64 hash = FNV-1a 64 over the LOWER-CASE path encoded as UTF-16LE
      +0xF0  int64 size, +0xF8 int64 offset (directories: 0)
```

- XOR flag is used by mods: Nissan has 572 of 783 files flagged; `sdk.kspkg` has it too. `extract` handles it; `pack` writes flag 0.
- Nissan layout: data from offset 0, table directly after data, size not MiB-aligned, mixed-case paths kept (378 of 841). Hash is always over the lower-case path (case-insensitive lookup). Our `pack` lower-cases stored paths.
- Honda/Daytona contain orphaned gaps (552,690 B; 411,007 B + 677,367 B) from in-place replacement; repack is 1 MiB smaller.
- Directory entries: HDC/Honda/Daytona only below `content\cars\<id>`; Nissan also `content`, `content\cars`, `uiresources\...`.
- Pre-0.7 tools (`ntpopgetdope/ace-kspkg`) assume a 32 MiB table.

## 6. Schemas and tools (the new baseline)

- `python tools/extract_protos.py "<...>\Assetto Corsa EVO SDK\AssettoCorsaEVOEditor.exe" schemas` -> `schemas/acevo.desc` (dependency-ordered FileDescriptorSet, 565 KB) + 99 `.proto` text files. The Editor exe contains all car messages; the game exe is not needed. Options/extensions on fields (UI metadata) are not rendered.
- `python tools/car_json.py decode|encode|check|types`. JSON: keys are schema names in wire order, present only if present on the wire (absent = proto3 default; an empty nested message is `{}`); enums by name; floats as the shortest text that keeps the float32 bits; reserved keys `_order` (non-canonical wire order), `_packed`, `_unknown`. `encode` accepts a UTF-8 BOM.
- Mapped extensions (strict fit, 176 files, 0 failed): `.brakesystem .caranalogicsystem .carelectronics .carengine .carfinalstate .carsetup .carsetuplimits .cartests .compatiblerim .curve .mechanicalcarpreset .oemmultilayercolor .visualcarpreset .wing`.
- Not mapped: `.car .clutch .coilover .compatibletyres .design .drivetrain .gearbox .rimmesh .suspension .tyre .tyremesh .actor .aicardata .carexhaustbackfire .carledsystem .carlightingsystem .carwipersystem` (unknown fields or wire-type mismatches against the schema) and ties for `.cardesign .cardisplaysystem .turbo .moddedcarcontent` (tiny files fit many messages). The example mods apparently use an older or hybrid layout than the current Editor schema. **Re-run the fit test on the real game files before deciding** (relaxed mapping with `_unknown`, or keep out).
- Do not use `Nenkai/ACEvo.Package` (its AGENTS.md prohibits AI use). `Breakalien/ac-evo-data-tools` and `Seigneur-Machiavel/AC_EVO_Modding` (GPL-3) are references for the extension-to-message map and field paths.
- `mod_examples/*/_conversion_report.json` (EvoForge) maps AC1 `.ini` keys to EVO files; with AC1 originals it can still name fields independently of the exe.

## 7. Field knowledge (real names from the schema)

Engine (`EngineData`, `.carengine`): field 1 `inertia`, 2 `powerCurve` (path), 3 `coastCurve` (path), 5 `minimum` (idle rpm), 6 `limiter` (rpm), 7 `limiterCycles`, 14 `throttleResponseCurve`, 15 `nominal_rpm`, 16 `turboBoostDamageThreshold`, 17 `turboBoostDamageK`, 20 `starterEngineTorque`, 24 `turbos[]`, 29 `turbos_to_load[]` (paths), 34 `max_turbo_boost`, 40/41 `throttle_lag_up` / `throttle_lag_dn`, 27 `damage`, 28 `p2p`. Turbo (`TurboData`): `max_boost`, `lag_UP`, `lag_DN`, `rpm_Ref`, `gamma_Rpm`, `gamma_Gas`, `wastegate`.
Differential: drivetrain field 39 = `differential_data {power, coast, preload}`, mirrored in `.carsetup` 1.4 and ranges in `.carsetuplimits` 1.4 (`{1 step, 2 min, 3 max, 4 enabled, 8 display}`). Seen in 11 cars; Nissan S15 stock: 1.0 / 1.0 / 80 Nm, limits 0.5-1.0 and preload 30-120.
Curves (`CurveDataEx`): repeated points `{1 rpm, 10 torque}`; a zero rpm is omitted on the wire.
Setup (`CarSetupData`): 1.2 steer ratio, 1.3 brake {bias, power}, 1.4 diff, 2.x springs/bump, 3.x dampers, 4.1 tyre pressure (names to be filled from `CarSetup.proto`).
`.mechanicalcarpreset` stats are display text only (`{1 id, 3 unit, 4 value}`: 1 power, 2 torque, 9 top speed, 11 mass).
HDC E46 (from `hdc_1.4/decoded/e46`, to be replaced by the real Kunos files): limiter 8100, idle 700, peak about 378 Nm at 5000 rpm, diff 0.85 / 0.70 / 10, limits 0.70-1.00 / 0.55-0.85 / 5-30 Nm (a locked diff is not possible with those limits), steer ratio 14 (range disabled), brake bias 61-65.
Fields in HDC engine (4, 19, 27, 63) and drivetrain (46, 47, 102-104) are absent in all three example mods, so they are optional.

## 8. Next steps

1. Wait for the game download. Extract the E46 from the game's package (`kspkg.py list/extract`; check table size and XOR flag). Re-run the fit test on the real files.
2. Write the build plan for the tuner (docs/TUNER_SPEC.md) and get it approved: settings catalogue, base extraction, car-id renamer, build/backup/install, local server, HTML page, one verified step each.
3. First in-game test: repack the unchanged E46 under the new id and check it loads next to the stock car. Then one value change.
4. Resolve open questions (section 10) with in-game tests on the Daytona example and the tuned E46.
5. Cleanups: `tools/live_files.py` (print `cardata.car` refs), `pack` option to keep original case, XOR flags and layout.

## 9. Test protocol on the PC

- Close EVO before swapping packages; keep backups of every replaced `.kspkg`.
- Mods folder: `%USERPROFILE%\Saved Games\ACE\mods\` (create if missing).
- Check the car shows in the Vehicle Hub, loads in a single-player session, and the edited values show in the setup screen or behaviour.
- If the car is missing: check the game log, that the `.kspkg` sits in the mods root, and the UI loc files.

## 10. Open questions

- Does EVO verify package contents for single-player mods? Does it accept our pack variant (lower-case paths, no XOR flags)?
- Do loose folders in `mods\content\cars\<id>` load without packing?
- Which copy does the game read when a value exists twice: separate files vs inline copy in `cardata.car`; `.drivetrain` gears vs `.gearbox` gears; drivetrain diff vs `.carsetup` default? The Daytona has these disagreeing (drivetrain gears 3.46/2.13/1.47/1.13/0.92, final 3.18; gearbox 3.07/2.11/1.57/1.25/0.96, final 3.3; drivetrain diff 0.3/0.6/50 vs setup 0.2/0.3/50): check what its setup screen shows.
- Dead variants: Honda live engine is `ks_mini_jcs_1990_b16.carengine`; HDC AE86 live engine `parts\..._tuned`; HDC Datsun `tuning\*`. Always read the `cardata.car` refs first.
- Does the game let a mod reuse a Kunos car id (HDC AE86 did)? Not needed with an own id.
- Do the real game files fit the Editor schema (section 6)?
- Is the game's own `content.kspkg` the same table layout as mods?

## 11. Findings from the example mods

Details in `mod_examples/ANALYSIS.md` (local). Summary: format variants (section 5), `cardata.car` as manifest, zero-omission in protobuf (the encoder keeps presence, never invents defaults), cross-car references work, `ks_modded_car` skeleton, displayed stats are hand-written text, and the converter reports as a second route to field names. Earlier guesses corrected by the schema: engine field 7 is `limiterCycles` (not a frequency), 15 is `nominal_rpm`, 16/17 are turbo damage values, 34 is `max_turbo_boost`, 40/41 are throttle lag.

## 12. Rights

Hina's Drift Club is Hina's work (no license file); only schema-less dumps remain in this repo; the original download is linked in NOTICE.md. Car data is derived from Kunos content. The schemas (`schemas/`), SDK files and base car files are Kunos property: keep them local and git-ignored. Personal use; do not publish tuned derivatives of Hina's or Kunos' cars. `mod_examples/` holds third-party work (Honda EG6 and Nissan S15: AC1 mods by others converted with EvoForge; Daytona: author unknown, prefix `pg`) and stays local and untracked; its conversion reports contain the converter user's local paths.
