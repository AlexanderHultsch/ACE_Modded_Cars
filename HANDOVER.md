# HANDOVER: AC EVO car modding (drift focus)

Handover from a Claude chat session (2026-11-11) to a Claude Code session.
Owner: Alex (GitHub: AlexanderHultsch). Game: Assetto Corsa EVO (Steam, Early Access 0.9.x), Windows PC.

## 1. Goal

Reuse an existing AC EVO car (official or modded) and change only its specs to get a fun drift car:

- more power (torque curve / turbo boost)
- locked differential (power/coast lock, preload)
- wider setup ranges (steering angle, diff, etc.)
- keep 3D model, sounds etc. untouched

End state: a small, repeatable tool chain `unpack -> edit JSON/values -> repack -> copy to mods -> drive`.

## 2. Status (what is proven, what is not)

| Step | Status |
|---|---|
| Find free EVO car mods | done: Hina's Drift Club 1.4 (6 drift cars + track), included here |
| Unpack `.kspkg` mod packages (0.7+ format) | done: `tools/kspkg.py extract` |
| Decode car data files (protobuf, schema-less) | done: `tools/pb_raw.py`, `tools/dump_car.py`; all physics files decode |
| Repack `.kspkg` | done: `tools/kspkg.py pack`; 5 of 6 HDC packages repack **byte-identical**, AE86 content-identical (original has gaps). Of the 3 `mod_examples` packages Honda and Daytona repack content-identical (1 MiB smaller), Nissan differs (case, XOR flags, dir entries, layout), see section 5 and `mod_examples/ANALYSIS.md` |
| Cross-check with 3 more mods (`mod_examples/`) | done 2026-11-11: confirms diff/limits/curve fields, corrects format and `.car` notes (sections 4, 5, 10, 11) |
| Field names (schema) | open: needs `AssettoCorsaEVO.exe` (see section 6) |
| Edit a value and re-encode protobuf | open: not implemented yet (re-encoder needed, see section 8) |
| Game loads a repacked / edited package | open: **untested**, needs the PC |

Nothing has been tested in the game yet. Alex was away from the PC when this was written.

## 3. Repo layout

```
HANDOVER.md                 this file
CLAUDE.md                   pointer for Claude Code
NOTICE.md                   credits / rights (Hina's mod, Kunos)
tools/
  kspkg.py                  list / extract / pack / verify .kspkg (stdlib only)
  pb_raw.py                 schema-less protobuf dumper (field numbers, guessed types)
  dump_car.py               dump every physics/config file of an extracted car to .txt
hdc_1.4/                    Hina's Drift Club 1.4, complete release
  original/
    README.txt, SHA256SUMS.txt, HDC_Setup_1.4.exe   as shipped
    Source/                 installer C# source (as shipped; documents the install logic)
    kspkg/*.kspkg.gz        the 6 original car packages, gzip'd (byte-exact, ~6 MB each;
                            raw files are 115-125 MB, mostly padding, over GitHub's 100 MB limit)
  payload/                  HDC.payload.zip contents except the .kspkg files
    content/tracks/hdc_drift_1r/   "The Yard" drift track
    registration/                  track registry rows (installer patches the game package)
    uiresources/                   car localization, HDC branding, track maps
    SHA256SUMS.txt                 checksums of the full payload
  extracted/<car>/          each .kspkg unpacked (all files), + <car>_filelist.txt
  decoded/<car>/            protobuf/text dumps of all physics/config files
mod_examples/               3 more mods for comparison (see ANALYSIS.md)
  ANALYSIS.md               findings vs this baseline
  <mod>/<mod>.kspkg         original (git-ignored), <mod>_filelist.txt,
        extracted/          pruned: physics/setup/config/UI files only (no meshes/textures/sounds)
        decoded/            schema-less dumps
  ks_honda_ci_f, ks_nissan_s_9 = AC1 mods converted by EvoForge; pg_daytona = hand-built
```

Car short names to car ids:

| short | car id (folder under content/cars) | base |
|---|---|---|
| ae86 | ks_ae86_beginner_h_01 | Toyota AE86 (Kunos id reused!) |
| datsun | hdc_datsun_240z_01 | Datsun 240Z |
| e46 | hdc_bmw_e46_01 | BMW M3 E46 CSL (Kunos `ks_bmw_m3_e46` data) |
| mercedes | hdc_mercedes_190e_01 | Mercedes 190E Evo II |
| rx7 | hdc_rx7_fd_01 | Mazda RX-7 FD |
| s2000 | hdc_honda_s2000_ap1_01 | Honda S2000 AP1 (has extra `_drift` engine/drivetrain) |

Restore an original package: `python -c "import gzip,shutil;shutil.copyfileobj(gzip.open('hdc_1.4/original/kspkg/hinas_drift_club_e46_v1.4.kspkg.gz'),open('e46.kspkg','wb'))"`

## 4. How EVO loads mod cars (from the HDC installer source)

- Car mods = one `.kspkg` per car, placed **directly** in `%USERPROFILE%\Saved Games\ACE\mods\` (no subfolder).
- Plus loose UI files in the same mods folder: `uiresources/localization/cars/<car_id>/{en.loc, preset_*.en.loc, setup.en.loc}` and `uiresources/branding/oem/<brand>/{badge,logo}.texture(+mips)`. (HDC way. The Honda/Nissan packages instead carry `content\cars\<id>\uiresources\localization\*.loc` and `...\branding\oem\modded_brand` inside the package, Nissan also `uiresources\branding\oem\evoforge` at the package root, so loose files are not required. Untested in game.)
- The car's **live files are named by `data/cardata.car`** (fields 16 limits, 19 setup, 20 engine, 22 drivetrain, 24 gearbox, 26 clutch, 27 brakes, 29 AI, 77 electronics). Other loose files may be dead variants (see section 10).
- Cars need **no** patching of the game's own `content.kspkg`. (Only the track does: the installer appends edited `system/tracks.table` and `system/track_containers.table` to the game package. Ignore the track for car work.)
- "Official stock game assets are required": mod cars reference Kunos meshes/sounds/materials from the installed game by path.
- Installer refuses loose dev resources at `mods/content/cars/<id>/` when installed, so loose (unpacked) cars in the mods folder might also load. **Untested**, but worth trying: it would avoid repacking during iteration.
- Online: since 0.8.1, servers reject mods not re-exported through the official SDK ("JSON auth"). Single-player is the target for now. Modded cars are not allowed in the Daily Racing Portal.

## 5. .kspkg format (0.7+ mod packages) - verified

Verified on all 6 HDC packages and 3 `mod_examples` packages (table, key, hash and entry layout identical in all 9); `tools/kspkg.py` implements it. The data area layout below is the HDC/Kunos-style one; the Nissan package shows it is **not mandatory** (see variants list after the block). The game reads strictly through the table.

```
[0x000000, 0x100000)   1 MiB header, all zero
[0x100000, data_end)   file data, contiguous, no alignment, sorted largest file first
                       (zero padding up to next 1 MiB boundary)
[size-64MiB, size)     file table: 256-byte entries sorted ascending by hash, rest zero.
                       Whole 64 MiB XOR'd with 8-byte key c135117da921979f
                       (repeating from table start; same key as the game's content.kspkg)
entry +0x00  path, utf8, backslashes, lower case, <= 0xE0 bytes, zero padded
      +0xE0  int32 0
      +0xE4  int16 flags: 1 = directory, 0x100 = file data XOR'd (same 8-byte key, repeating from the file start).
                          Used by mods too: Nissan has 572 of 783 files flagged (all but .texturemips). extract handles it; pack writes 0.
      +0xE6  int16 path length
      +0xE8  uint64 hash = FNV-1a 64 over the path encoded as UTF-16LE
      +0xF0  int64 size   (dirs: 0)
      +0xF8  int64 offset (dirs: 0)
```

Directory entries: HDC and Honda/Daytona only have them for `content\cars\<id>` and below. The Nissan package also has `content`, `content\cars` and `uiresources\...` entries, so no fixed rule.

Layout variants seen in `mod_examples` (all index-driven, so all valid):
- Nissan: data starts at offset 0 (no 1 MiB header), table follows data directly, size not a multiple of 1 MiB, **mixed-case paths kept** (378 of 841).
- Hash is always over the **lower-case** path (841/841 in Nissan), so lookup is case-insensitive. Our `pack` lower-cases the stored paths as well.
- Honda and Daytona: HDC layout but with orphaned gaps (552,690 B; 411,007 B + 677,367 B) left by in-place file replacement; repack is therefore 1 MiB smaller.
Pre-0.7 tools (`ntpopgetdope/ace-kspkg`) assume a 32 MiB table and find 0 entries in these files.

## 6. Data format and how to get field names

All car data files are serialized **Protocol Buffers** (no field names in the files). `tools/pb_raw.py` prints field numbers with guessed types; floats are fixed32.

Getting real names (do this first on the PC):
- `Breakalien/ac-evo-data-tools` (Python, free, GitHub): Settings tab, "Extract protos" from the AC EVO install folder. Writes `data editor/proto/acevo.desc` plus about 90 `.proto` files. Its extension-to-message map (`acevo_decode.py`): `.car` CarData, `.carengine` EngineData, `.drivetrain` DrivetrainData, `.gearbox` GearBoxData, `.carsetup` CarSetupData, `.carsetuplimits` CarSetupDataLimits, `.curve` CurveDataEx, `.clutch` ClutchData, `.coilover` CoiloverData, `.suspension`, `.tyre`, `.mechanicalcarpreset` MechanicalCarPresetData, ...
- Alternative without the exe: the EvoForge conversion reports in `mod_examples/ks_*/.../_conversion_report.json` map AC1 `.ini` keys to EVO files (e.g. `engine.ini HEADER.POWER_CURVE -> header_power.curve`). With the original AC1 mod folders (`tw_honda_civic_eg6`, `wdts_nissan_silvia_s15`) every `.ini` value can be paired with its protobuf field. See `mod_examples/ANALYSIS.md` section 6.
- With `acevo.desc` + `google.protobuf` (`MessageToDict` / `ParseDict`) we get lossless JSON round trips with real names. Commit the generated `.proto` files to `schemas/` (reference only).
- Do not use `Nenkai/ACEvo.Package`: its AGENTS.md prohibits use by AI tools.
- `Seigneur-Machiavel/AC_EVO_Modding` (GPL-3, WIP) clones Kunos cars and patches `.carsetuplimits` (steer ratio, torque multiplier, turbo boost ranges) by field path. Useful as a reference for field paths.

## 7. E46 (hdc_bmw_e46_01) - decoded values

Field meanings marked (?) are inferred from values, not from the schema.

Engine `data/ks_bmw_m3_e46_engine_1.carengine` (uses `bmw_m3_e46_coupe_engine_power_1.curve`):
- field 5 = 700 (idle rpm), 6 = 8100 (limiter rpm), 15 = 8100, 2 = power curve path, 3 = coast curve path
- Confirmed by 3 more mods (inferred meanings): 1 = inertia, 7 = limiter frequency Hz, 29 = `.turbo` path(s) with 24 = inline copy. `.turbo` field 1 = max boost bar, 2/3 = lag up/down, 4 = reference rpm, 5 = gamma. Autoshift thresholds = drivetrain 28 = gearbox 13 (`{1 up rpm, 2 down rpm}`), not the 7900 guessed below.

Torque curve `.curve`: repeated field 1 = point { 1: rpm (f32), 10: torque Nm (f32) }
- `_power_1.curve` (used): peak about 378 Nm at 5000 rpm; original Kunos `_power.curve` also in package: 368 Nm
- This is the easiest "more power" lever: scale field 10 of every point.

Drivetrain `data/ks_bmw_m3_e46_1.drivetrain`:
- field 39 = { 1: 0.85, 2: 0.70, 3: 10, 11: 2.5, 12: 3, 4: 0 }: LSD (?) power 0.85, coast 0.70, preload 10 Nm.
  Strong evidence: identical triple in `.carsetup` field 1.4 and ranges in `.carsetuplimits` field 1.4.
- field 9 = 6 + repeated field 10 = gears (R -3.678, 1st 4.055 ... 6th 0.872), 11 = 3.09 (final?). Note: separate `.gearbox` exists with different ratios, so check which one the car uses (`.car` / preset references).

Gearbox `data/ks_bmw_m3_e46_1.gearbox`: 6 gears 3.5 / 2.1 / 1.669 / 1.226 / 1.0 / 0.828, R -3.746, field 3 = 3.91 (final drive), field 13.1 = 7900 (auto shift rpm?).

Setup `data/setup/hdc_bmw_e46_01.carsetup` (default setup):
- 1.2 = 14 (steer ratio?), 1.3 = {63, 100} (brake bias %, brake power %?), 1.4 = {0.85, 0.70, 10} (diff power / coast / preload)
- 2.x per wheel: 1 = spring N/m (54000 front / 55000 rear) + damper sub-messages
- 3.x per wheel: dampers bump/rebound slow/fast (3400/1700/9200/4600 front)
- 4.x per wheel: 1 = tyre pressure psi (28 front / 23 rear), 2 = camber (-3.5 / -0.5), 3 = toe
- 7.1 = 30 (fuel L?)

Setup limits `data/setup/limits_m3_e46.carsetuplimits`: each range = { 1: step, 2: min, 3: max, 4: enabled (0/1) }
- 1.2 steer ratio: step 0.1, min = max = 14, **disabled**
- 1.3.1 brake bias 61-65, 1.3.2 brake power 90-100
- 1.4.1 diff power 0.70-1.00, 1.4.2 diff coast 0.55-0.85, 1.4.3 preload 5-30 Nm (field 8 = display type?)
- So a fully locked diff is impossible in-game: raise 1.4.2 max to 1.0, preload max, set defaults.

UI preset `presets/preset_hdc_e46_mech_1.mechanicalcarpreset`: display stats (375 / 378 / 1460 kg / 63 ...), brand "hina_drift_club", name "HDC E46 Drift Setup". Car name/brand also in `hdc_bmw_e46_01.moddedcarcontent` ("Hina's Drift Club - BMW M3 CSL", 2003).

## 8. Next steps (suggested order)

1. **Baseline in game (PC):** install HDC 1.4 with its own installer (or copy `hinas_drift_club_e46_v1.4.kspkg` + `payload/uiresources/...` to the mods folder). Drive the E46 once. Confirms the mod works on this game build.
2. **Repack test:** `kspkg.py extract` then `kspkg.py pack` unchanged, replace the installed E46 package (keep a backup). E46 repack is byte-identical, so it must load. Then test a trivial change (e.g. one torque point) to see whether the game validates contents.
3. **Schemas:** extract `.proto`s from `AssettoCorsaEVO.exe` (section 6). Write `tools/car_json.py`: decode to JSON with names / encode back. Prove byte-exact round trip on all HDC files.
   Fallback without schemas: write a schema-less re-encoder that keeps the original bytes of every untouched field and only rewrites edited fixed32 floats (same size, so in-place patching is trivial). Changing a float value in place does not change lengths, so even a byte-patch at the known offset works for a first test.
4. **Drift tune profile** (E46 first): torque curve x1.2, diff power/coast 1.0/1.0, preload 100+ Nm, open setup limits (diff, preload, steer ratio), maybe steering lock in `.car`. Keep car id first (replace package); later fork into own id (e.g. `alex_e46_drift_01`), which requires renaming every path in all files plus the UI loc folder.
   Reference for a drift setup: the Nissan S15 mod ships diff 1.0 / 1.0, preload 80 Nm, with limits 0.5-1.0 (power, coast) and preload 30-120 Nm (`mod_examples/ks_nissan_s_9`).
   Remember proto3 omits zero values (a missing `min` means 0), so the encoder must be able to insert fields.
5. **Apply to an official Kunos car**: also consider the Kunos modding skeleton `ks_modded_car` (used by the Daytona and by EvoForge: files `ks_modded_car.*`, presets `modded_car_*`). It avoids cloning a Kunos car. Original plan: unpack the game's `content.kspkg` (same tool should work; game package may use the XOR flag on files and older layout, so check), copy `content\cars\ks_<car>\` into a new mod id, edit, pack to `mods\`. That is the original goal (reuse any car, change specs).
6. Optional: GUI/CLI "tuner" for the whole flow.

## 9. Test protocol on the PC

- Close EVO before swapping packages. Keep backups of every replaced `.kspkg`.
- Mods folder: `%USERPROFILE%\Saved Games\ACE\mods\` (create if missing).
- Check car shows in Vehicle Hub, loads into a session (single player, The Yard or any track), values visible in setup screen.
- If the car is missing: check the game log, check the `.kspkg` sits in the root of `mods`, check the UI loc files.

## 10. Open questions

- Does EVO verify package contents/signatures for single-player mods? (auth JSON is only mentioned for servers)
- Do loose folders in `mods\content\cars\<id>` load without packing?
- **Important:** `data/cardata.car` and `data/hdc_bmw_e46_01.car` (both 8089 bytes, differ from byte 2171) embed full engine / drivetrain / aero blocks inline (same values and curve paths as the separate files). Find out which copy the game actually reads: the separate part files, the `.car`, or the `.car` referenced by preset/actor. Safest first tests: change a value in all copies.
  Update from `mod_examples`: only the E46 has both files; the other 8 packages have just `cardata.car`, so it is the standard one and `<id>.car` is probably a redundant extra. Inline copies follow the pattern "path field N, inline copy N+1" (e.g. engine 29 path / 24 inline turbo). Editing order: read the `cardata.car` refs (see section 4), edit the referenced files, then mirror the change in the inline copies.
- Dead variants: not every loose file is used. Honda live engine = `ks_mini_jcs_1990_b16.carengine` (not `ks_honda_ci_1.carengine`); HDC AE86 live engine = `parts\ks_ae86_beginner_h_01_tuned.carengine`; HDC Datsun live = `tuning\*` (L28 engine, LSD drivetrain, 5-speed gearbox). Verify the E46 refs (they point at `ks_bmw_m3_e46_engine_1`, `_1.drivetrain`, `_1.gearbox`, `limits_m3_e46`).
- Which of `.drivetrain` gears vs `.gearbox` is used. Daytona has them **disagreeing** (drivetrain gears 3.46/2.13/1.47/1.13/0.92, final 3.18; gearbox 3.07/2.11/1.57/1.25/0.96, final 3.3), and its drivetrain diff 0.3/0.6/50 differs from the `.carsetup` default 0.2/0.3/50. Test in game on the Daytona which values the setup screen shows.
- Exact meaning of setup fields (resolved by schemas)
- Game's own `content.kspkg`: same table layout as mods? (pre-0.7 game package had a 32 MiB table)

## 11. Findings from `mod_examples/` (2026-11-11)

Short list, details in `mod_examples/ANALYSIS.md`:
- Confirmed in 11 cars: diff = drivetrain field 39 {power, coast, preload} = `.carsetup` 1.4 = limits 1.4; limits range `{1 step, 2 min, 3 max, 4 enabled, 8 display}`.
- Format and `.car` corrections are folded into sections 4, 5, 8 and 10 above.
- `.mechanicalcarpreset` stats are display text only (`{1 id, 3 unit, 4 value}`: 1 power, 2 torque, 9 top speed, 11 mass); edit them by hand after a power change.
- HDC-only fields (engine 4/19/27/63, drivetrain 46/47/102-104) are absent in all 3 mods, so they are optional.
- Tooling gaps: a `tools/live_files.py` that prints the `cardata.car` refs; `pack` should optionally preserve original case, XOR flags and layout.

## 12. Rights

Hina's Drift Club is Hina's work, redistributed here as shipped (no license file in the release). Car data is derived from Kunos content. Personal use; do not publish tuned derivatives. See NOTICE.md.

`mod_examples/` holds third-party work (Honda EG6 and Nissan S15 are AC1 mods by others, converted by EvoForge; Daytona author unknown, prefix `pg`). The packages are git-ignored; do not commit `mod_examples/*/extracted` or `decoded` to the public repo before deciding on rights (the conversion reports also contain the converter user's local paths).
