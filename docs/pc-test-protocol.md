# PC test protocol: repacked E46 package

Run on the Windows PC, in Command Prompt (cmd), not PowerShell. Keep one cmd window open for the whole protocol: the `set` variables only live in that window.

## 0. Purpose and what the variants test

These are experiments to answer open questions, not tunes. The meanings of the diff fields (power lock, coast lock, preload) are inferred from values, not from the game's schema, and the game may clamp or ignore values. Questions (HANDOVER section 10):

- (a) Does the game load a repacked `.kspkg`?
- (b) Does the game validate package contents (signature, hash)?
- (c) Which copy of a value does the game read: the separate part file, the copy inlined in `data/cardata.car`, or the copy in `data/hdc_bmw_e46_01.car`?

| Variant | What is in the package | Tests |
|---|---|---|
| A_unchanged | Repack of the untouched tree, byte-identical to the original package | (a): the repack format loads |
| B1_limiter_file | Rev limiter 4000 rpm in the separate `.carengine` file only | (b), (c): file copy read? |
| B2_limiter_inline | Rev limiter 4000 rpm in `cardata.car` and `hdc_bmw_e46_01.car` only | (c): inline copy read? |
| C_torque_half | Engine torque curve x0.5 | edited curve files take effect |
| D_drift_v0 | Diff lock/preload (all copies), widened setup ranges, torque x1.2 | setup and limits files are read; combined drift tune |
| F_loose_unchanged | Unpacked `content` folder, no `.kspkg` | loose folders in `mods` load without packing |

Do not publish any of these packages (Hina's and Kunos' content).

## 1. Prerequisites

- Python 3.9 or newer. Check: `python --version`
- git. The repo cloned on the PC (step 2).
- Hina's Drift Club 1.4 installed with its own installer first, so the loose UI files and branding exist in the mods folder.
- The E46 launches once unmodified (Vehicle Hub entry, loads into a session).
- Assetto Corsa EVO closed for every file swap.

## 2. Build the kit

```
git clone https://github.com/AlexanderHultsch/ACE_Modded_Cars.git
cd ACE_Modded_Cars
python tools\make_testkit.py hdc_1.4\extracted\e46 spec\e46_package.sha256 work\testkit
```

The script must end with a table of five packages and `F_loose_unchanged`, and exit code 0. `A_unchanged` must print `ok: A_unchanged sha256 equals the original package`. If it prints `error:`, stop and send the output back. `work\testkit` must not exist beforehand (delete it to rebuild).

Set the shortcuts used below (still in the repo folder):

```
set "KIT=%CD%\work\testkit"
set "MODS=%USERPROFILE%\Saved Games\ACE\mods"
set "BK=%USERPROFILE%\Documents\ace_mods_backup_2026-11-11"
type "%KIT%\SHA256SUMS.txt"
```

## 3. Backup

Original sha256 of the E46 package: `59d1bad1c5652d334c34351157a5ab85756b9b1a1aca5e2056e0d7c423669e47`

```
mkdir "%BK%"
copy "%MODS%\hinas_drift_club_e46_v1.4.kspkg" "%BK%\hinas_drift_club_e46_v1.4.kspkg"
certutil -hashfile "%BK%\hinas_drift_club_e46_v1.4.kspkg" SHA256
```

Compare the printed hash with `59d1...9e47`. If it differs, continue but write the printed hash in your report.

Restore (any time, EVO closed):

```
copy /Y "%BK%\hinas_drift_club_e46_v1.4.kspkg" "%MODS%\hinas_drift_club_e46_v1.4.kspkg"
```

## 4. Procedure per variant

Order: A, B1, B2, C, D, F. Do one variant at a time. Between variants close EVO fully.

Replace the package (example for A; use the folder name of the variant instead of `A_unchanged`):

```
copy /Y "%KIT%\A_unchanged\hinas_drift_club_e46_v1.4.kspkg" "%MODS%\hinas_drift_club_e46_v1.4.kspkg"
certutil -hashfile "%MODS%\hinas_drift_club_e46_v1.4.kspkg" SHA256
```

The printed hash must match the line of that variant in `SHA256SUMS.txt`. Then start EVO and record, per variant:

1. Car appears in the garage / Vehicle Hub? (yes/no, name and look unchanged?)
2. Loads into a single-player session on any track (for example The Yard)? (yes/no, error message text if any)
3. Rev limiter: in 1st gear, full throttle, standing or rolling. At which rpm does the engine hit the limiter? (expected 8100 for A, C, D; 4000 if the edit is read)
4. Acceleration feel against the unmodified car: clearly weaker, same, stronger.
5. Setup screen: diff power, coast and preload default values and slider ranges. Original: power 0.85 (0.70 to 1.00), coast 0.70 (0.55 to 0.85), preload 10 (5 to 30).
6. Anything in the game log. The log location is not verified. Find recent logs:

```
dir /s /b /o-d "%USERPROFILE%\Saved Games\ACE\*.log"
dir /s /b /o-d "%USERPROFILE%\Documents\Assetto Corsa EVO\*.log"
```

Per variant:

- A: items 1, 2, 5.
- B1, B2: items 1, 2, 3.
- C: items 1, 2, 4.
- D: items 1, 2, 4, 5. Expected if read: diff power and coast ranges up to 1.00, preload range up to 120, default preload 80, torque 1.2x. Note whether the car feels locked or behaves differently, and anything odd (clamped values, values shown as 0, setup screen empty).

### Variant F (loose folder)

Do this last. First check that `mods\content` does not exist:

```
if exist "%MODS%\content" (echo EXISTS: do not run F, report this) else echo ok
```

If it prints `ok`, move the installed package out of the mods folder and copy the loose folder in:

```
move /Y "%MODS%\hinas_drift_club_e46_v1.4.kspkg" "%BK%\moved_for_F.kspkg"
xcopy /E /I /Y "%KIT%\F_loose_unchanged\content" "%MODS%\content"
dir "%MODS%\content\cars\hdc_bmw_e46_01"
```

The last command must list `data`, `skins` and the other car folders. Start EVO and record items 1, 2. Afterwards restore (step 6).

## 5. How to read the results

| Result | Meaning |
|---|---|
| A fails (car missing, does not load, error) | Repack format problem or install problem. Stop, report; do not test the others. |
| A ok, B1 fails to load or car missing | The game validates package or file contents (signature or hash?). Report the exact message. |
| A ok, B1 limiter at about 4000 | The separate carengine file is read. |
| A ok, B2 limiter at about 4000 | The inline copy in `cardata.car` / `hdc_bmw_e46_01.car` is read. |
| B1 and B2 both at about 4000 | Both copies are read, or either one wins depending on which is applied last. Report as both. |
| B1 and B2 both stay at 8100 (A ok) | Neither copy is the limiter source, or the edit is ignored. Report to the planner. |
| C torque obviously weak | Curve files are read and edits take effect. |
| C same as A | The edited curve is not the one in use (or torque is taken from elsewhere). Report. |
| D shows diff power/coast up to 1.00, preload up to 120, default preload 80 | Setup and limits files are read. |
| D ranges unchanged | Limits file not read from the package, or clamped. Report the values shown. |
| D physics differ from A (car locks up / drives differently) | Drivetrain file or inline diff copy is read. If the setup screen shows the new values but the car feels the same, report that. |
| F loads | Loose folders in `mods` work, which speeds iteration (no repacking). |
| F car missing | Loose folders are not loaded; keep packing. |

## 6. Restore and cleanup

EVO closed. Restore the original package:

```
copy /Y "%BK%\hinas_drift_club_e46_v1.4.kspkg" "%MODS%\hinas_drift_club_e46_v1.4.kspkg"
certutil -hashfile "%MODS%\hinas_drift_club_e46_v1.4.kspkg" SHA256
```

The hash must be `59d1...9e47` again (or the hash you noted in step 3). If F was run, remove the loose folder (only after the `if exist` check printed `ok` before F):

```
rmdir /S /Q "%MODS%\content"
```

Start EVO once and check that the E46 still loads. Keep `%BK%` and `work\testkit` until the results are sent.

## 7. What to send back

Fill this table, one row per variant, and add the notes below it:

| variant | car appears | loads in session | limiter hit at ~rpm | torque feel | diff values shown/ranges | notes |
|---|---|---|---|---|---|---|
| A_unchanged | | | | | | |
| B1_limiter_file | | | | | | |
| B2_limiter_inline | | | | | | |
| C_torque_half | | | | | | |
| D_drift_v0 | | | | | | |
| F_loose_unchanged | | | | | | |

Also send:

- The output of step 2 (the final table of `make_testkit.py`).
- The `certutil` hash printed in step 3.
- Any game log lines or error messages, and screenshots of the setup screen for A and D.
- Anything unexpected, even if it looks unrelated.
