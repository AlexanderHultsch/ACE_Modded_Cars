# HANDOVER: AC EVO drift-car modding (state 2026-11-11, for a local Claude session on Alex's PC)

Owner: Alex (GitHub: AlexanderHultsch). Game: Assetto Corsa EVO (Steam, Early Access 0.9.x), Windows PC.
Work branch: `claude/exciting-ramanujan-i0haq5` (origin `https://github.com/AlexanderHultsch/ACE_Modded_Cars`). `main` is untouched and still holds the original import.
Previous sessions: a Claude chat session (research), then a cloud Claude Code session (this state). Nothing has been tested in the game yet.

Read in this order: this file, `CLAUDE.md`, `docs/working-contract.md` (how Alex wants every coding session run: planner + executors), then the docs listed in section 7.

## 1. Goal and owner decisions

- Goal: tune cars for **drifting** by editing the physics data of AC EVO cars, repack, copy to the game's mods folder, drive. 3D model/visuals are NOT wanted or changed. (The E46 package contains no 3D model anyway, see section 3.)
- End state: Alex's own repo with his own values; only a small baseline of Hina's E46 is carried over as a working template. Hina's Drift Club (HDC) is the source of the example cars.
- Decisions already made by Alex:
  - Baseline car = **BMW M3 E46 only**. All other HDC cars, the installer, her track and her exe are to be deleted from the repo (not yet done, see section 6).
  - Fresh history: the repo history must end up without Hina's release (new repo or orphan branch). **Never force-push `main` or rewrite remote history without Alex's explicit go-ahead.**
  - Visible "Hina's Drift Club" text on the car is replaced by neutral names: car `BMW M3 CSL Drift`, brand display `ACE Modded`, tyre `Drift Tyre E46`, presets `Drift Setup` / `Drift`, a short neutral description text. **Ids, variable names and folder names stay unchanged for now** (`hdc_bmw_e46_01`, `hina_drift_club` brand id, ...). A rename to an own car id is deferred until the unchanged car is proven to load.
  - Keep `collider/bmw_m3_e46_csl_collider.mesh` (physics-side, tiny).
  - Wanted removed from the baseline: windshield texture (`generated/windshield`, 50 MB), other mesh files except the collider, stickers/decals (materials `*decal*`, skin designs), dashboard `displays/`. Whether the game still loads the car without them is unknown, so removal is **staged** (section 6).
  - Cleanup is **on hold** until Alex has put at least one other car mod next to the E46 for comparison (he downloads them to this PC).
- Workflow wish: do everything that does not need the PC first (done), then live-debug on the PC with a local Claude session (this one).

## 2. Status

| Step | Status |
|---|---|
| Unpack/repack `.kspkg` (0.7+ mod packages) | done: `tools/kspkg.py`; all 6 HDC packages repack, 5 byte-identical, AE86 content-identical |
| Schema-less decode of all car data files | done: `tools/pb_raw.py`, `tools/dump_car.py` |
| Lossless value editing (no schema needed) | done and tested: `tools/pbedit.py` (all 1,025 protobuf files of the six cars re-encode byte-identically) |
| Cross-reference map between files | done: `tools/refgraph.py` |
| Lever spec + tuning tool (all redundant copies edited together) | done: `spec/e46_levers.json`, `tools/tune.py`, profile `spec/profiles/drift_v0.json` |
| PC test kit (5 package variants + loose-folder variant) | built and verified here: `tools/make_testkit.py`, `docs/pc-test-protocol.md`. **Not run on the PC yet.** |
| Knowledge docs | `docs/drift-deltas.md`, `docs/car-anatomy.md`, `docs/tuning-levers.md` |
| Field names (schema) | open: need the game executable (section 5) |
| Does the game load a repacked/edited package? Which data copy does it read? | open: PC test (section 4) |
| Other cars for comparison | open: Alex downloads them to the PC |
| Cleanup of Hina's files / fresh history | open, on hold (section 6) |
| Own car id/brand | open, deferred |

Commits on the work branch (oldest first, after the original import): refgraph, pbedit + tests, drift-deltas doc, tune + spec, make_testkit + protocol, anatomy + levers docs, this handover. Full unit suite: 44 tests, `python -m unittest discover -s tests` (use `python3` on Linux). They read `hdc_1.4/extracted/...`, so **do not delete `hdc_1.4/extracted/e46` before updating the test constants** (section 6).

## 3. What we know (short; details in docs/)

- A car is one folder `content/cars/<car_id>/` inside a `.kspkg`. The E46 package has 157 files, 54.6 MB: physics data in `data/`, materials, presets, skins, UI text, displays, a 50 MB generated windshield texture, and **no body/interior/wheel meshes**: the actor names 15 external Kunos `.mesh` files that the installed game provides (`content\cars\ks_bmw_m3_e46_csl\...`, `common_assets`, sfx banks, particles). So an HDC-style mod is "data + materials + presets", and it needs the official game assets installed.
- Entry point (inferred from references): `presets/*.carfinalstate` -> `data\CarData.car` + `.actor` + materials/presets.
- **Redundancy problem.** The same value exists in several copies and nobody knows which one the game reads. For the E46: the separate part file (`.drivetrain`, `.carengine`, `.gearbox`, ...), the inline block inside `data/cardata.car`, the dev copy `data/hdc_bmw_e46_01.car` (identical to `cardata.car` except one unrelated float, `8.4`), the defaults in `data/setup/*.carsetup`, and the ranges in `data/setup/*.carsetuplimits`. In all six HDC cars the inline blocks 3, 4, 5, 23, 25 of `cardata.car` are byte-identical to the file named by path fields 22, 20, 27, 24, 26 (30 of 30), so only a game test with one copy changed can tell. Therefore every lever edits all copies; experiments can restrict to a role subset (`file`, `inline`, `devcopy`, `setup`, `limits`).
- Known by value only (schema not available, so labelled inferred): drivetrain `39.1/39.2/39.3` = diff power lock / coast lock / preload Nm (same triple in `.carsetup 1.4` and ranges in `.carsetuplimits 1.4.*`); carengine `5`/`6` = idle/limiter rpm; `.curve` repeated field 1 = `{1: rpm, 10: torque Nm}`; carsetup `1.2` = steer ratio, its limit entry `1.2` is disabled (`enabled` = 0, min = max); `cardata.car 8.3` equals the setup steer ratio in all six HDC cars (second copy, not yet in the spec); `cardata.car 8.2` may be steering wheel degrees (450 in the E46; unverified).
- No steering lock/angle lever has been identified. Diff limits are narrow in the E46 (power 0.70-1.00, coast 0.55-0.85, preload 5-30 Nm), which blocks a fully locked drift diff until the limits are widened (that is what `drift_v0` does).
- Gear ratios exist in three places and disagree: drivetrain (`10[i].2`, final `11`), gearbox (`2[i].2`, final `3`), and a third copy inside the clutch file's block `23` (also at `cardata.car 25.23.*`). The drivetrain ones are the Kunos Alfa Giulia template ratios. Which one the game uses is unknown. The spec has `final_drive_drivetrain` and `final_drive_gearbox` as separate levers on purpose; the clutch-block copy is not covered yet.
- `cardata.car` field 25 is byte-identical to the `.clutch` file and, in four cars, carries leftover Kunos source-car data (E46: 30 `ks_alfa_romeo_giulia_gtam` paths).
- HDC cars differ in how they were built: S2000 `_drift` and RX-7 `_tuned` variants are referenced by no file; AE86/Datsun use part files. See `docs/drift-deltas.md`.

## 4. First thing to do on the PC: run the test protocol

1. `git fetch origin claude/exciting-ramanujan-i0haq5 && git checkout claude/exciting-ramanujan-i0haq5`. Python 3.9+ needed (stdlib only).
2. `python -m unittest discover -s tests` (expect 44 OK).
3. Follow `docs/pc-test-protocol.md` exactly: HDC 1.4 must be installed with its own installer first (it puts the loose UI files and branding into `%USERPROFILE%\Saved Games\ACE\mods\`). Build the kit: `python tools\make_testkit.py hdc_1.4\extracted\e46 spec\e46_package.sha256 work\testkit`. Variants, in order:
   - `A_unchanged`: repack, must be byte-identical to the original package (sha256 `59d1bad1c5652d334c34351157a5ab85756b9b1a1aca5e2056e0d7c423669e47`). Does a repacked package load?
   - `B1_limiter_file` / `B2_limiter_inline`: rev limiter 4000 in the separate `.carengine` only / in `cardata.car` + `hdc_bmw_e46_01.car` only. Which copy does the game read? Does it validate contents?
   - `C_torque_half`: curve x0.5, are edited curves used?
   - `D_drift_v0`: diff lock/preload (all copies), widened limits, torque x1.2: are setup and limits files read?
   - `F_loose_unchanged`: unpacked `content` folder in `mods\` without packing (would remove repacking from the loop).
4. Record the results in a new `docs/test-results.md` (table from protocol section 7) and update section 2 of this file. **Always back up the installed packages first**, close EVO before swapping files, keep the original file name `hinas_drift_club_e46_v1.4.kspkg`.
5. If a variant fails, do not guess: keep the observation, check the game log (location unverified in the protocol), and re-plan with Alex.

## 5. Schemas (field names)

All car data files are Protocol Buffers without names. `tools/pb_raw.py` prints field numbers and guessed types; `tools/pbedit.py` addresses fields by number path (`39.1`, `10[2].2`; see its docstring).
- Get real names on the PC with `Breakalien/ac-evo-data-tools` (Python, free, GitHub): Settings tab, "Extract protos" from the AC EVO install folder; writes `acevo.desc` and about 90 `.proto` files. Extension map in its `acevo_decode.py`: `.car` CarData, `.carengine` EngineData, `.drivetrain` DrivetrainData, `.gearbox` GearBoxData, `.carsetup` CarSetupData, `.carsetuplimits` CarSetupDataLimits, `.curve` CurveDataEx, `.clutch` ClutchData, `.coilover`, `.suspension`, `.tyre`, `.mechanicalcarpreset`, ... Commit the generated `.proto` files to `schemas/` (reference only), then add names to `spec/e46_levers.json` / docs and look for the steering-lock field.
- Do **not** use `Nenkai/ACEvo.Package` (its AGENTS.md prohibits AI use). `Seigneur-Machiavel/AC_EVO_Modding` (GPL-3, WIP) patches `.carsetuplimits` by field path and is a reference for paths only.
- With `acevo.desc` + `google.protobuf` a name-based JSON round trip is possible, but `pbedit` already edits losslessly without it; any new encoder must keep the byte-exact round trip proof (`python tools/pbedit.py roundtrip <dir>`).

## 6. Comparison cars and the (staged) cleanup

Alex downloads at least one other car mod to the PC. For each comparison car:
1. Put the `.kspkg` outside the repo (it is git-ignored anyway and 100+ MB), `python tools/kspkg.py list <pkg>` then `extract <pkg> work/<name>`. If a package is not the 0.7+ layout (32 MiB table, XOR-flagged files, official `content.kspkg`), stop and report the differences instead of patching the tool silently.
2. Run `python tools/refgraph.py work/<name>`, `python tools/pbedit.py roundtrip work/<name>`, `python tools/dump_car.py work/<name> work/<name>_decoded`.
3. Compare with the E46 using `docs/car-anatomy.md` and `docs/tuning-levers.md`: does it contain meshes/textures of its own (a package that includes its model is especially useful)? Is `cardata.car` laid out the same (field numbers 1-8, 12, 16-29, 202)? Are values in the same copies? Write the result as `docs/compare-<name>.md`, labels `[verified]/[inferred]/[unknown]` as in the other docs. Do not copy third-party mod files into the repo (rights).

Cleanup, only after the comparison and with Alex's go-ahead on the final list (**staged**):
1. Delete now-safe things: `hdc_1.4/original`, `hdc_1.4/payload` (keep a copy of the E46's 3 loose `.loc` files if needed for tests/protocol), `hdc_1.4/extracted|decoded` of the other five cars, and update NOTICE.md (the E46 baseline stays Hina's derivative until renamed: credit honestly, "personal use, do not publish").
2. Move the E46 tree to a baseline folder (e.g. `baseline/e46/`) and update everything that points to `hdc_1.4/extracted/e46`: `tests/test_pbedit.py` (CORPUS), `tests/test_tune.py` (CAR_ROOT), `tests/test_testkit.py`, `docs/pc-test-protocol.md`, README, tool docstrings, `CLAUDE.md`. The tests must keep failing (not skipping) when the corpus is missing.
3. Keep the baseline **complete and byte-verifiable** (`spec/e46_package.sha256`) until the PC test has run. Add a tool + manifest that builds slim variants: (S1) neutral names (pbedit `set ... str:` on the 15 visible protobuf strings listed in `docs/car-anatomy.md` section 6, plus the `.loc` value texts), (S2) minus `generated/windshield`, (S3) minus non-collider meshes, decal materials, skin designs and `displays/`. Extend `make_testkit.py` with these variants, test them on the PC, and only then commit the final slim baseline and remove the rest. Removed files can always be restored from the installed original HDC package.
4. Fresh history: create an orphan branch from the cleaned tree, local first. Pushing it over the work branch needs a force-push; replacing `main` or deleting old branches/commits on GitHub needs Alex's explicit approval (or a new repo). Old objects stay fetchable on GitHub until then.
5. Own car id/brand: after the unchanged car is proven. Renaming needs every path inside all binary files rewritten (pbedit `str` edits recompute lengths) and the loose UI folder renamed; verify with `refgraph` (0 missing) and a no-`hdc`/`hina` grep.

## 7. Repo layout and tools

```
CLAUDE.md                 project rules (read first)
HANDOVER.md               this file
NOTICE.md  README.md
docs/
  working-contract.md     planner/executor process Alex requires for every coding session
  pc-test-protocol.md     in-game experiments A, B1, B2, C, D, F and how to read them
  drift-deltas.md         what Hina changed for drifting + inline-vs-file copy facts (all 6 cars)
  car-anatomy.md          E46 file inventory, reference chain, removal candidates, every Hina string
  tuning-levers.md        implemented levers, candidate levers with values, drift rationale (labelled)
spec/
  e46_levers.json         17 levers, 37 targets (file/inline/devcopy/setup/limits copies)
  e46_package.sha256      sha256 of the original E46 package
  profiles/               drift_v0 (first tune), test_limiter4000, test_torque_half
tools/                    stdlib-only Python 3.9+
  kspkg.py                list / extract / pack / verify .kspkg
  pb_raw.py  dump_car.py  schema-less protobuf text dump (one file / a whole car)
  refgraph.py             which file references which content\ path (ok / MISSING / external)
  pbedit.py               get / set / scale-curve / roundtrip, lossless, by field-number path
  tune.py                 check / apply levers from a spec + profile onto a COPY of an extracted car
  make_testkit.py         builds the PC test packages
tests/                    44 unittest tests (pbedit, tune, testkit); real-data tests read hdc_1.4/extracted
hdc_1.4/                  Hina's Drift Club 1.4 release (original/ payload/ extracted/ decoded/), READ-ONLY reference, to be removed (section 6)
```

Typical commands (E46):
```
python tools/tune.py check  spec/e46_levers.json hdc_1.4/extracted/e46
python tools/tune.py apply  spec/e46_levers.json spec/profiles/drift_v0.json hdc_1.4/extracted/e46 -o work/e46_drift_v0
python tools/tune.py check  spec/e46_levers.json work/e46_drift_v0 spec/profiles/drift_v0.json
python tools/kspkg.py pack  work/e46_drift_v0 work/e46_drift_v0.kspkg
python tools/kspkg.py verify <original.kspkg> work/e46_drift_v0.kspkg      # lists exactly the changed files
```
`apply` refuses an existing output folder and prints SKIPPED/WARNING lines (e.g. a default outside the limit range). `drift_v0` values (diff 1.0/1.0, preload 80, coast max 1.0, preload max 120, torque x1.2) are a **first experiment with inferred meanings, not a tuned car**.

## 8. Rules and gotchas

- `CLAUDE.md` rules apply: hdc_1.4 is read-only; work on copies in `work/` (git-ignored, as are `*.kspkg`); do not use `Nenkai/ACEvo.Package`; back up packages before replacing them; do not publish tuned derivatives of Hina's or Kunos' cars.
- Process: follow `docs/working-contract.md`: a planner who writes no code, delegating one verified step at a time to executors, with the verification command named up front and re-run by the planner. Ask Alex when a decision is his.
- Online play rejects non-SDK mods (JSON auth since 0.8.1); target is single player. Modded cars are not allowed in the Daily Racing Portal.
- `.gitattributes` keeps mirrored files byte-exact; do not let git change line endings of anything under `hdc_1.4/` or any binary. GitHub rejects files over 100 MB, so raw `.kspkg` (about 124 MB, mostly zero padding) can only be committed gzip'd.
- `refgraph` uses the protobuf length prefix before `content\` for exact paths; text files fall back to a regex (e.g. doubled backslashes in `caraudio.data`), shown in its FALLBACK section.
- Labels in docs: `[verified]` read from files/computed, `[inferred]` guessed from values/names, `[unknown]`, `[general]` general car knowledge. Keep this discipline: field meanings are inferred until the schemas are extracted or the game confirms them.

## 9. Open questions (answered by the PC test unless noted)

1. Does a repacked package load, and does the game validate package contents? (A, B1)
2. Which copy of a value does the game read: part file, inline `cardata.car`, or `hdc_bmw_e46_01.car`? (B1 vs B2; D for setup/limits)
3. Do loose folders `mods\content\cars\<id>\` load without packing? (F)
4. Which gearing is used: drivetrain, gearbox, or the clutch-block copy? (needs a gear-ratio variant; not built yet)
5. Which field limits steering angle? (schemas + in-game check; `cardata.car 8.2/8.3` and setup `1.2` are the candidates)
6. What selects the S2000 `_drift` and RX-7 `_tuned` variants, if anything? (schemas / game)
7. Which of the removal candidates (windshield, decals, designs, displays, meshes) can go without breaking the load? (staged variants, section 6)
8. Does the game's own `content.kspkg` use the same table layout as mod packages? (comparison/official car task)

## 10. Rights

Hina's Drift Club is Hina's work, redistributed here as shipped (no license file in the release). Car data derives from Kunos content. Personal use only; do not publish tuned derivatives. See NOTICE.md. The E46 baseline remains a Hina-derived template until it has been renamed and re-based on own values.
