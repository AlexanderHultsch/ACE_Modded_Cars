# BMW M3 E46 package: tuning levers (`hdc_bmw_e46_01`)

What can be changed in the E46 package, which values exist in several copies, and which fields are only candidates. Companion: `docs/car-anatomy.md` (files and references). All values come from `hdc_1.4/extracted/e46/content/cars/hdc_bmw_e46_01/` (read-only reference); file names in tables are relative to that car root. Nothing here has been tested in the game.

## 1. How to read this

**Labels.** `[verified]` = read from the files, computed by a script, or produced by a tool run for this document; `[inferred]` = guessed from values or names; `[unknown]` = no meaning established (field numbers only, no schema yet); `[general]` = general knowledge about cars/drifting, not from the files. Floats are printed as `pbedit.format_value` prints them (`%.9g` of the float32), so `0.85` appears as `0.850000024`; "rounded" columns say so.

**The redundancy problem** [verified, `docs/drift-deltas.md` section 1]. The same value lives in several places: a part file (for example the `.drivetrain`), the identical block inlined in `data/cardata.car`, the same block in `data/hdc_bmw_e46_01.car`, and often the setup default and the setup range. Which copy the game reads is [unknown]. **Rule: edit every copy**, otherwise a test cannot tell what the game uses and the copies drift apart.

`tools/tune.py` implements the rule: `spec/e46_levers.json` lists, per named lever, every copy as a target (`file`, `path`, `role` = `file` part file, `inline` in `cardata.car`, `devcopy` in `hdc_bmw_e46_01.car`, `setup` default, `limits` range). `check` reads all copies and reports `ok`, `MISMATCH`, `MISSING` or `INCONSISTENT <lever>`; `apply` copies the tree and sets every copy of every lever in a profile.

```
  python tools/tune.py check <spec> <car_root> [<profile>]
  python tools/tune.py apply <spec> <profile> <car_root> -o <out_root> [--roles r1,r2,...]
```

Worked example (profile `drift_v0`, output produced for this document with the apply target in a scratch folder; use `work/` in practice, it is git-ignored):

```
python tools/tune.py check spec/e46_levers.json hdc_1.4/extracted/e46
    -> 37 targets, 37 ok, 0 mismatch, 0 missing   (exit 0: all copies agree with the baselines)
python tools/tune.py check spec/e46_levers.json hdc_1.4/extracted/e46 spec/profiles/drift_v0.json
    -> 37 targets, 23 ok, 14 mismatch, 0 missing   (exit 1: expected, the profile values are not applied yet)
python tools/tune.py apply spec/e46_levers.json spec/profiles/drift_v0.json hdc_1.4/extracted/e46 -o work/e46_drift_v0
    diff_preload  file  data/ks_bmw_m3_e46_1.drivetrain  39.3  (f32) 10 -> (f32) 80
    diff_preload  inline  data/cardata.car  3.39.3  (f32) 10 -> (f32) 80
    diff_preload  devcopy  data/hdc_bmw_e46_01.car  3.39.3  (f32) 10 -> (f32) 80
    diff_preload  setup  data/setup/hdc_bmw_e46_01.carsetup  1.4.3  (f32) 10 -> (f32) 80
    diff_preload_max  limits  data/setup/limits_m3_e46.carsetuplimits  1.4.3.3  (f32) 30 -> (f32) 120
    engine_torque_scale  file  data/bmw_m3_e46_coupe_engine_power_1.curve  scaled 21 points by 1.2
    ... 16 lines in total, one per edited copy (exit 0)
python tools/tune.py check spec/e46_levers.json work/e46_drift_v0 spec/profiles/drift_v0.json
    -> 37 targets, 37 ok, 0 mismatch, 0 missing   (exit 0)
```

`apply` never edits `hdc_1.4/extracted/**`; it needs an output folder that does not exist. It prints `WARNING` lines when a new value lies outside the lever's `within` limits and `SKIPPED` lines for profile entries without a target under `--roles`. Repacking the edited tree is `python tools/kspkg.py pack work/e46_drift_v0 <out>.kspkg`.

## 2. Levers implemented

Generated from `spec/e46_levers.json` by script [verified]. File aliases: `drv` = `data/ks_bmw_m3_e46_1.drivetrain`, `card` = `data/cardata.car`, `dev` = `data/hdc_bmw_e46_01.car`, `setup` = `data/setup/hdc_bmw_e46_01.carsetup`, `lim` = `data/setup/limits_m3_e46.carsetuplimits`, `eng` = `data/ks_bmw_m3_e46_engine_1.carengine`, `gbx` = `data/ks_bmw_m3_e46_1.gearbox`, `crv` = `data/bmw_m3_e46_coupe_engine_power_1.curve`. `(int)` marks a target whose kind overrides the lever kind. `copies` = number of targets.

| id | meaning | confidence | kind | baseline | copies | roles | files:paths |
|---|---|---|---|---|---|---|---|
| `diff_power_lock` | diff power lock, 0..1 | inferred | `f32` | 0.85 | 4 | file, inline, devcopy, setup | `drv:39.1` `card:3.39.1` `dev:3.39.1` `setup:1.4.1` |
| `diff_coast_lock` | diff coast lock, 0..1 | inferred | `f32` | 0.7 | 4 | file, inline, devcopy, setup | `drv:39.2` `card:3.39.2` `dev:3.39.2` `setup:1.4.2` |
| `diff_preload` | diff preload in Nm | inferred | `f32` | 10 | 4 | file, inline, devcopy, setup | `drv:39.3` `card:3.39.3` `dev:3.39.3` `setup:1.4.3` |
| `diff_power_lock_min` | setup range minimum for diff power lock | inferred | `f32` | 0.7 | 1 | limits | `lim:1.4.1.2` |
| `diff_power_lock_max` | setup range maximum for diff power lock | inferred | `f32` | 1.0 | 1 | limits | `lim:1.4.1.3` |
| `diff_coast_lock_min` | setup range minimum for diff coast lock | inferred | `f32` | 0.55 | 1 | limits | `lim:1.4.2.2` |
| `diff_coast_lock_max` | setup range maximum for diff coast lock | inferred | `f32` | 0.85 | 1 | limits | `lim:1.4.2.3` |
| `diff_preload_min` | setup range minimum for diff preload | inferred | `f32` | 5 | 1 | limits | `lim:1.4.3.2` |
| `diff_preload_max` | setup range maximum for diff preload | inferred | `f32` | 30 | 1 | limits | `lim:1.4.3.3` |
| `rev_limiter_rpm` | engine rev limiter in rpm | inferred | `f32` | 8100 | 6 | file, inline, devcopy | `eng:6(int)` `eng:15` `card:4.6(int)` `card:4.15` `dev:4.6(int)` `dev:4.15` |
| `engine_torque_scale` | scale factor on the engine power curve torque values | inferred | `curve_scale` | - | 1 | file | `crv` |
| `final_drive_drivetrain` | final drive ratio as stored in the drivetrain | inferred | `f32` | 3.09 | 3 | file, inline, devcopy | `drv:11` `card:3.11` `dev:3.11` |
| `final_drive_gearbox` | final drive ratio as stored in the gearbox | inferred | `f32` | 3.91 | 3 | file, inline, devcopy | `gbx:3` `card:23.3` `dev:23.3` |
| `mass_kg` | car mass in kg | inferred | `f32` | 1495 | 2 | inline, devcopy | `card:1.1` `dev:1.1` |
| `steer_ratio` | steering ratio default in the setup | unknown | `f32` | 14 | 1 | setup | `setup:1.2` |
| `steer_ratio_limit_min` | setup range minimum for steering ratio | unknown | `f32` | 14 | 1 | limits | `lim:1.2.2` |
| `steer_ratio_limit_max` | setup range maximum for steering ratio | unknown | `f32` | 14 | 1 | limits | `lim:1.2.3` |
| `steer_ratio_limit_enabled` | enabled flag of the steering ratio range | unknown | `int` | 0 | 1 | limits | `lim:1.2.4` |

18 levers, 37 targets [verified]. The `within` links (min/max lever ids) are: `diff_power_lock` in [`diff_power_lock_min`, `diff_power_lock_max`], `diff_coast_lock` in [`diff_coast_lock_min`, `diff_coast_lock_max`], `diff_preload` in [`diff_preload_min`, `diff_preload_max`]. `steer_ratio*` are `confidence: unknown` in the spec.

### Profile `drift_v0` (`spec/profiles/drift_v0.json`)

Description in the file: "First experiment: lock the diff fully, add preload, raise engine torque 20 percent. Diff and torque meanings are inferred; not game-tested."

| lever | profile section | profile value | baseline | copies edited | roles |
|---|---|---|---|---|---|
| `diff_power_lock` | values | 1.0 | 0.85 | 4 | file, inline, devcopy, setup |
| `diff_coast_lock` | values | 1.0 | 0.7 | 4 | file, inline, devcopy, setup |
| `diff_preload` | values | 80 | 10 | 4 | file, inline, devcopy, setup |
| `diff_power_lock_max` | values | 1.0 | 1.0 | 1 | limits |
| `diff_coast_lock_max` | values | 1.0 | 0.85 | 1 | limits |
| `diff_preload_max` | values | 120 | 30 | 1 | limits |
| `engine_torque_scale` | scale | 1.2 | - | 1 | file |

drift_v0 touches 7 of 18 levers and 16 targets; untouched: `diff_power_lock_min`, `diff_coast_lock_min`, `diff_preload_min`, `rev_limiter_rpm`, `final_drive_drivetrain`, `final_drive_gearbox`, `mass_kg`, `steer_ratio`, `steer_ratio_limit_min`, `steer_ratio_limit_max`, `steer_ratio_limit_enabled`. Other profiles: `test_limiter4000` (Rev limiter 8100 -> 4000 rpm), `test_torque_half` (Engine torque curve x0.5) (tests of which copy the game reads, not tunes). Meanings of the diff and torque values are [inferred]; the profile has not been tried in the game.

## 3. Candidate levers not implemented yet

Every row is `file | pbedit path | current value | label`; the value is read by script with `pbedit.get_field` + `format_value` (nested messages collapsed to one line as `pbedit set` prints them). Paths: `N[i]` = i-th occurrence of field N (omitted when 0). Meanings are only those in `HANDOVER.md` section 7 (and the evidence noted), all [inferred]; everything else is [unknown]. None of these has a lever in `spec/e46_levers.json`; the redundant copies of each (if any) are noted, but not yet mapped to targets.

### (a) Setup defaults and ranges

Wheel index in the repeated setup fields: `[0]`,`[1]` look like front and `[2]`,`[3]` like rear [inferred: the front pair holds the values of `ks_bmw_m3_e46_front_1.coilover`, the rear pair those of `..._rear_1.coilover`, checked below]. Setup defaults (`carsetup`):

| file | pbedit path | current value | label |
|---|---|---|---|
| `data/setup/hdc_bmw_e46_01.carsetup` | `1.3.1` | `(f32) 63` | [inferred] brake bias % (HANDOVER 7) |
| `data/setup/hdc_bmw_e46_01.carsetup` | `1.3.2` | `(f32) 100` | [inferred] brake power % (HANDOVER 7) |
| `data/setup/hdc_bmw_e46_01.carsetup` | `2` | `1: (f32) 54000 2 {   1: (f32) 0.0193681   2: (f32) 80 } 3 {   1: (f32) 0.0556319   2: (f32) 500 }` | [inferred] wheel 0: `.1` spring N/m (HANDOVER 7); `.2` / `.3` [unknown] |
| `data/setup/hdc_bmw_e46_01.carsetup` | `2[1]` | `1: (f32) 54000 2 {   1: (f32) 0.0193681   2: (f32) 80 } 3 {   1: (f32) 0.0556319   2: (f32) 500 }` | [inferred] wheel 1: `.1` spring N/m (HANDOVER 7); `.2` / `.3` [unknown] |
| `data/setup/hdc_bmw_e46_01.carsetup` | `2[2]` | `1: (f32) 55000 2 {   1: (f32) 0.0746095   2: (f32) 500 } 3 {   1: (f32) 0.0153905   2: (f32) 500 }` | [inferred] wheel 2: `.1` spring N/m (HANDOVER 7); `.2` / `.3` [unknown] |
| `data/setup/hdc_bmw_e46_01.carsetup` | `2[3]` | `1: (f32) 55000 2 {   1: (f32) 0.0746095   2: (f32) 500 } 3 {   1: (f32) 0.0153905   2: (f32) 500 }` | [inferred] wheel 3: `.1` spring N/m (HANDOVER 7); `.2` / `.3` [unknown] |
| `data/setup/hdc_bmw_e46_01.carsetup` | `3` | `1: (f32) 3400 2: (f32) 1700 3: (f32) 9200 4: (f32) 4600` | [inferred] wheel 0: dampers bump/rebound slow/fast (HANDOVER 7); which of `.1`-`.4` is which [unknown] |
| `data/setup/hdc_bmw_e46_01.carsetup` | `3[1]` | `1: (f32) 3400 2: (f32) 1700 3: (f32) 9200 4: (f32) 4600` | [inferred] wheel 1: dampers bump/rebound slow/fast (HANDOVER 7); which of `.1`-`.4` is which [unknown] |
| `data/setup/hdc_bmw_e46_01.carsetup` | `3[2]` | `1: (f32) 4800 2: (f32) 1300 3: (f32) 5700 4: (f32) 3900` | [inferred] wheel 2: dampers bump/rebound slow/fast (HANDOVER 7); which of `.1`-`.4` is which [unknown] |
| `data/setup/hdc_bmw_e46_01.carsetup` | `3[3]` | `1: (f32) 4800 2: (f32) 1300 3: (f32) 5700 4: (f32) 3900` | [inferred] wheel 3: dampers bump/rebound slow/fast (HANDOVER 7); which of `.1`-`.4` is which [unknown] |
| `data/setup/hdc_bmw_e46_01.carsetup` | `4` | `1: (f32) 28 2: (f32) -3.5 4: (f32) -0.068 5: (f32) -4.41646 6: (f32) -0.000336083` | [inferred] wheel 0: `.1` tyre pressure psi, `.2` camber, `.3` toe (HANDOVER 7); `.3` absent on this wheel = proto default? [unknown]; `.4`-`.6` [unknown] |
| `data/setup/hdc_bmw_e46_01.carsetup` | `4[1]` | `1: (f32) 28 2: (f32) -3.5 4: (f32) -0.068 5: (f32) -4.41613 6: (f32) -0.000337018` | [inferred] wheel 1: `.1` tyre pressure psi, `.2` camber, `.3` toe (HANDOVER 7); `.3` absent on this wheel = proto default? [unknown]; `.4`-`.6` [unknown] |
| `data/setup/hdc_bmw_e46_01.carsetup` | `4[2]` | `1: (f32) 23 2: (f32) -0.5 3: (f32) 0.1 5: (f32) -0.39526 6: (f32) -0.000297485` | [inferred] wheel 2: `.1` tyre pressure psi, `.2` camber, `.3` toe (HANDOVER 7); `.4`-`.6` [unknown] |
| `data/setup/hdc_bmw_e46_01.carsetup` | `4[3]` | `1: (f32) 23 2: (f32) -0.5 3: (f32) 0.1 5: (f32) -0.395079 6: (f32) -0.000297457` | [inferred] wheel 3: `.1` tyre pressure psi, `.2` camber, `.3` toe (HANDOVER 7); `.4`-`.6` [unknown] |
| `data/setup/hdc_bmw_e46_01.carsetup` | `7.1` | `(f32) 30` | [inferred] fuel litres? (HANDOVER 7) |
| `data/setup/hdc_bmw_e46_01.carsetup` | `5` | `3: (f32) 1` | [unknown] |
| `data/setup/hdc_bmw_e46_01.carsetup` | `6` | `1: <16 bytes> 2: (f32) 130 3: (f32) 135` | [unknown] |

Ranges (`carsetuplimits`; a range = {`1` step, `2` min, `3` max, `4` enabled} [inferred]; an extra field `8` (value 2) on some ranges = display type? [inferred, HANDOVER 7]):

| file | pbedit path | current value | label |
|---|---|---|---|
| `data/setup/limits_m3_e46.carsetuplimits` | `1.3.1` | `1: (f32) 1 3: (f32) 65 2: (f32) 61 4: 1` | [inferred] brake bias range |
| `data/setup/limits_m3_e46.carsetuplimits` | `1.3.2` | `1: (f32) 1 2: (f32) 90 3: (f32) 100 4: 1` | [inferred] brake power range |
| `data/setup/limits_m3_e46.carsetuplimits` | `2.1` | `1: (f32) 2700 2: (f32) 48600 3: (f32) 59400 4: 1` | [inferred] spring range, wheel 0 |
| `data/setup/limits_m3_e46.carsetuplimits` | `2[2].1` | `1: (f32) 2750 2: (f32) 49500 3: (f32) 60500 4: 1` | [inferred] spring range, wheel 2 |
| `data/setup/limits_m3_e46.carsetuplimits` | `2.2` | `1 {   1: (f32) 0.001   2: (f32) 0.0193681   3: (f32) 0.0193681   4: 0 } 2 {   1: (f32) 10   3: (f32) 80   2: (f32) 80   4: 0 }` | [unknown] spring group 2, wheel 0 (limits side of setup `2.2` / `2.3`?) |
| `data/setup/limits_m3_e46.carsetuplimits` | `2.3` | `1 {   1: (f32) 0.001   2: (f32) 0.0556319   3: (f32) 0.0556319   4: 0 } 2 {   1: (f32) 10   3: (f32) 500   2: (f32) 500   4: 0 }` | [unknown] spring group 3, wheel 0 (limits side of setup `2.2` / `2.3`?) |
| `data/setup/limits_m3_e46.carsetuplimits` | `2.4` | `1: (f32) 500 3: (f32) 15000` | [unknown] spring group 4, wheel 0 (limits side of setup `2.2` / `2.3`?) |
| `data/setup/limits_m3_e46.carsetuplimits` | `2.5` | `1: (f32) 0.01 3: (f32) 0.1` | [unknown] spring group 5, wheel 0 (limits side of setup `2.2` / `2.3`?) |
| `data/setup/limits_m3_e46.carsetuplimits` | `2[2].2` | `1 {   1: (f32) 0.001   2: (f32) 0.0746095   3: (f32) 0.0746095   4: 0 } 2 {   1: (f32) 10   3: (f32) 500   2: (f32) 500   4: 0 }` | [unknown] spring group 2, wheel 2 (limits side of setup `2.2` / `2.3`?) |
| `data/setup/limits_m3_e46.carsetuplimits` | `2[2].3` | `1 {   1: (f32) 0.001   2: (f32) 0.0153905   3: (f32) 0.0153905   4: 0 } 2 {   1: (f32) 10   3: (f32) 500   2: (f32) 500   4: 0 }` | [unknown] spring group 3, wheel 2 (limits side of setup `2.2` / `2.3`?) |
| `data/setup/limits_m3_e46.carsetuplimits` | `2[2].4` | `1: (f32) 500 3: (f32) 15000` | [unknown] spring group 4, wheel 2 (limits side of setup `2.2` / `2.3`?) |
| `data/setup/limits_m3_e46.carsetuplimits` | `2[2].5` | `1: (f32) 0.01 3: (f32) 0.1` | [unknown] spring group 5, wheel 2 (limits side of setup `2.2` / `2.3`?) |
| `data/setup/limits_m3_e46.carsetuplimits` | `3.1` | `1: (f32) 170 2: (f32) 2890 3: (f32) 3910 4: 1` | [inferred] damper range 1, wheel 0; mapping to bump/rebound/slow/fast [unknown] |
| `data/setup/limits_m3_e46.carsetuplimits` | `3.2` | `1: (f32) 85 2: (f32) 1530 3: (f32) 1870 4: 1` | [inferred] damper range 2, wheel 0; mapping to bump/rebound/slow/fast [unknown] |
| `data/setup/limits_m3_e46.carsetuplimits` | `3.3` | `1: (f32) 460 2: (f32) 7820 3: (f32) 10580 4: 1` | [inferred] damper range 3, wheel 0; mapping to bump/rebound/slow/fast [unknown] |
| `data/setup/limits_m3_e46.carsetuplimits` | `3.4` | `1: (f32) 230 2: (f32) 4140 3: (f32) 5060 4: 1` | [inferred] damper range 4, wheel 0; mapping to bump/rebound/slow/fast [unknown] |
| `data/setup/limits_m3_e46.carsetuplimits` | `3[2].1` | `1: (f32) 240 3: (f32) 5520 2: (f32) 4080 4: 1` | [inferred] damper range 1, wheel 2; mapping to bump/rebound/slow/fast [unknown] |
| `data/setup/limits_m3_e46.carsetuplimits` | `3[2].2` | `1: (f32) 65 3: (f32) 1430 2: (f32) 1170 4: 1` | [inferred] damper range 2, wheel 2; mapping to bump/rebound/slow/fast [unknown] |
| `data/setup/limits_m3_e46.carsetuplimits` | `3[2].3` | `1: (f32) 285 3: (f32) 6555 2: (f32) 4845 4: 1` | [inferred] damper range 3, wheel 2; mapping to bump/rebound/slow/fast [unknown] |
| `data/setup/limits_m3_e46.carsetuplimits` | `3[2].4` | `1: (f32) 195 3: (f32) 4290 2: (f32) 3510 4: 1` | [inferred] damper range 4, wheel 2; mapping to bump/rebound/slow/fast [unknown] |
| `data/setup/limits_m3_e46.carsetuplimits` | `4.1` | `1: (f32) 1 2: (f32) 25 3: (f32) 31 4: 1` | [inferred] pressure range, wheel 0 |
| `data/setup/limits_m3_e46.carsetuplimits` | `4.2` | `1: (f32) 0.1 2: (f32) -4 3: (f32) -3 4: 1 8: 2` | [inferred] camber range, wheel 0 |
| `data/setup/limits_m3_e46.carsetuplimits` | `4.3` | `1: (f32) 0.01 2: (f32) -0.05 3: (f32) 0.05 4: 1 8: 2` | [inferred] toe range, wheel 0 |
| `data/setup/limits_m3_e46.carsetuplimits` | `4[2].1` | `1: (f32) 1 2: (f32) 21 3: (f32) 27 4: 1` | [inferred] pressure range, wheel 2 |
| `data/setup/limits_m3_e46.carsetuplimits` | `4[2].2` | `1: (f32) 0.1 2: (f32) -1 3: (f32) 0 4: 1 8: 2` | [inferred] camber range, wheel 2 |
| `data/setup/limits_m3_e46.carsetuplimits` | `4[2].3` | `1: (f32) 0.01 2: (f32) 0.05 3: (f32) 0.15 4: 1 8: 2` | [inferred] toe range, wheel 2 |

Limits rows not listed (the pair partner is byte-identical to the listed row) [verified]: `2` vs `2[1]` equal, `2[2]` vs `2[3]` equal, `3` vs `3[1]` equal, `3[2]` vs `3[3]` equal, `4` vs `4[1]` equal, `4[2]` vs `4[3]` equal. In the setup defaults all four wheels are listed; pairwise `2` vs `2[1]` equal, `2[2]` vs `2[3]` equal, `3` vs `3[1]` equal, `3[2]` vs `3[3]` equal, `4` vs `4[1]` differs, `4[2]` vs `4[3]` differs; the setup `4` / `4[1]` and `4[2]` / `4[3]` differ only in fields `5` and `6` (both [unknown]; compared by script).

Redundancy and structure [verified numerically]: setup `2.1` equals front coilover `1` and `2[2].1` equals rear coilover `1`; setup `3.1-3.4` equal front coilover `6.2.1`, `6.1.1`, `6.2.2`, `6.1.2` and `3[2].1-4` the same for the rear coilover. So spring and damper defaults exist in the setup, in the coilover file and in the `cardata.car` copy (`2.8` / `2.9`); only the setup copies are exposed in game [inferred]. Range endpoints are fixed fractions of the default: spring `2.1` min/default = 0.9, max/default = 1.1; front damper `3.1` 0.85 and 1.15 (rounded). A changed default therefore needs its range checked, as `tune.py` does for the diff via `within`.

### (b) Gear ratios

| file | pbedit path | current value | label |
|---|---|---|---|
| `data/ks_bmw_m3_e46_1.drivetrain` | `9` | `6` | [inferred] gear count |
| `data/ks_bmw_m3_e46_1.drivetrain` | `10.2` | `(f32) -3.67799997` | [inferred] ratio of gear R |
| `data/ks_bmw_m3_e46_1.drivetrain` | `10[2].2` | `(f32) 4.05499983` | [inferred] ratio of gear 1 |
| `data/ks_bmw_m3_e46_1.drivetrain` | `10[3].2` | `(f32) 2.39599991` | [inferred] ratio of gear 2 |
| `data/ks_bmw_m3_e46_1.drivetrain` | `10[4].2` | `(f32) 1.58200002` | [inferred] ratio of gear 3 |
| `data/ks_bmw_m3_e46_1.drivetrain` | `10[5].2` | `(f32) 1.19200003` | [inferred] ratio of gear 4 |
| `data/ks_bmw_m3_e46_1.drivetrain` | `10[6].2` | `(f32) 1` | [inferred] ratio of gear 5 |
| `data/ks_bmw_m3_e46_1.drivetrain` | `10[7].2` | `(f32) 0.871999979` | [inferred] ratio of gear 6 |
| `data/ks_bmw_m3_e46_1.drivetrain` | `11` | `(f32) 3.08999991` | [inferred] final drive (lever `final_drive_drivetrain`) |
| `data/ks_bmw_m3_e46_1.gearbox` | `1` | `6` | [inferred] gear count |
| `data/ks_bmw_m3_e46_1.gearbox` | `2.2` | `(f32) -3.74600005` | [inferred] ratio of gear R |
| `data/ks_bmw_m3_e46_1.gearbox` | `2[2].2` | `(f32) 3.5` | [inferred] ratio of gear 1 |
| `data/ks_bmw_m3_e46_1.gearbox` | `2[3].2` | `(f32) 2.0999999` | [inferred] ratio of gear 2 |
| `data/ks_bmw_m3_e46_1.gearbox` | `2[4].2` | `(f32) 1.66900003` | [inferred] ratio of gear 3 |
| `data/ks_bmw_m3_e46_1.gearbox` | `2[5].2` | `(f32) 1.22599995` | [inferred] ratio of gear 4 |
| `data/ks_bmw_m3_e46_1.gearbox` | `2[6].2` | `(f32) 1` | [inferred] ratio of gear 5 |
| `data/ks_bmw_m3_e46_1.gearbox` | `2[7].2` | `(f32) 0.828000009` | [inferred] ratio of gear 6 |
| `data/ks_bmw_m3_e46_1.gearbox` | `3` | `(f32) 3.91000009` | [inferred] final drive (lever `final_drive_gearbox`) |

Copies of the first gear and both final drives inside the two `.car` files:

| file | pbedit path | current value | label |
|---|---|---|---|
| `data/cardata.car` | `3.10[2].2` | `(f32) 4.05499983` | [inferred] copy of drivetrain gear 1 |
| `data/cardata.car` | `3.11` | `(f32) 3.08999991` | [inferred] copy of drivetrain final drive |
| `data/cardata.car` | `23.2[2].2` | `(f32) 3.5` | [inferred] copy of gearbox gear 1 |
| `data/cardata.car` | `23.3` | `(f32) 3.91000009` | [inferred] copy of gearbox final drive |
| `data/hdc_bmw_e46_01.car` | `3.10[2].2` | `(f32) 4.05499983` | [inferred] copy of drivetrain gear 1 |
| `data/hdc_bmw_e46_01.car` | `3.11` | `(f32) 3.08999991` | [inferred] copy of drivetrain final drive |
| `data/hdc_bmw_e46_01.car` | `23.2[2].2` | `(f32) 3.5` | [inferred] copy of gearbox gear 1 |
| `data/hdc_bmw_e46_01.car` | `23.3` | `(f32) 3.91000009` | [inferred] copy of gearbox final drive |

Copies [verified]: the `cardata.car` and `hdc_bmw_e46_01.car` copies (`3.10[i].2`, `3.11` of the drivetrain block and `23.2[i].2`, `23.3` of the gearbox block) equal the part files; 32 leaf comparisons, all equal.

**The two gear sets disagree** [verified]. Rounded comparison (4 significant digits; ratio columns are computed, overall = gear x final drive of the same file):

| gear | drivetrain `10[i].2` | gearbox `2[i].2` | drivetrain / gearbox | overall drivetrain (x `11`) | overall gearbox (x `3`) |
|---|---|---|---|---|---|
| R | -3.678 | -3.746 | 0.9818 | -11.37 | -14.65 |
| 1 | 4.055 | 3.5 | 1.1586 | 12.53 | 13.69 |
| 2 | 2.396 | 2.1 | 1.1410 | 7.404 | 8.211 |
| 3 | 1.582 | 1.669 | 0.9479 | 4.888 | 6.526 |
| 4 | 1.192 | 1.226 | 0.9723 | 3.683 | 4.794 |
| 5 | 1 | 1 | 1.0000 | 3.09 | 3.91 |
| 6 | 0.872 | 0.828 | 1.0531 | 2.694 | 3.237 |

Final drive: drivetrain (f32) 3.08999991 vs gearbox (f32) 3.91000009. Which set the simulation uses (or whether one only feeds UI / auto-shift data) is [unknown] (`docs/drift-deltas.md` question 5). **A third place holds the drivetrain's values** [verified]: the clutch file has a block `23` in gearbox layout (`1` count, repeated `2` = {name, ratio}, `3` final) whose 8 compared values (7 ratios, final drive) equal the drivetrain's, not the gearbox's; that block is also inside `cardata.car` and `hdc_bmw_e46_01.car` at `25.23.*` (field `25` is byte-identical to the clutch file). Whether it is read is [unknown]. To change gearing safely, edit all of these, until a test shows which one counts. The levers `final_drive_*` cover only the final drives of the part files and the `.car` blocks `3` / `23`.

### (c) Tyres

Top-level groups of the two `.tyre` files, one row per group and file. All meanings [unknown] except: group `1` is the tyre name shown in the UI [inferred], and `12.1` is the tyre width in mm [verified: equals the 235 / 265 of the file names `hdc_235_35_19_front.tyre`, `hdc_265_30_19_rear.tyre`]; `12.2` and `12.3` equal the 35 / 30 and 19 of the file names [verified numerically], read as aspect ratio and rim inches [inferred]. Paths in groups `4.14` and `5.25` are curve files (`hdc_wear.curve`, `hdc_temperature_*.curve`).

| file | pbedit path | current value | label |
|---|---|---|---|
| `data/tyres/hdc_235_35_19_front.tyre` | `1` | `"Hina's Drifters E46"` | [inferred] tyre name string |
| `data/tyres/hdc_235_35_19_front.tyre` | `2` | `"SC"` | [unknown] |
| `data/tyres/hdc_235_35_19_front.tyre` | `3` | `1: (f32) 0.235 2: (f32) 0.32355 3: (f32) 273000 4: (f32) 561.697 5: (f32) 1.76142 6: (f32) 0.2413 7: (f32) 0.001 8: (f32) 7 9: (f32) 6 10: (f32) 7 11: (f32) 38000 12: (f32) 2 13: (f32) 20000 14: (f32) 2.5 15: (f32) 450 16: (f32) 40 17: (f32) 0.1 19: (f32) 9.60401 20: (f32) 0.216261 21: (f32) 15.1357 29: 2 30: (f32) 1 31: (f32) 0.5 32: (f32) 3 22: (f32) 4 23: (f32) 1 24: (f32) 180` | [unknown] |
| `data/tyres/hdc_235_35_19_front.tyre` | `4` | `1: (f32) 1.35343 2: (f32) 1.326 3: (f32) 0.863332 4: (f32) 0.893332 5: (f32) 3720 6: (f32) 8.41818 7: (f32) 0.0207 8: (f32) 2 9: (f32) 0.05 10: (f32) 1.75 13: (f32) 0.77 14: "content\cars\hdc_bmw_e46_01\data\tyres\hdc_wear.curve" 15: (f32) 0.6 16: (f32) 0.001 17: (f32) 4 18: (f32) 0.10051 19: (f32) 0.10051 20: (f32) 0.12 21: (f32) 0.5 22: (f32) 0.2 23: (f32) 2.85 11: (f32) 0.96 12: (f32) 0.96` | [unknown] |
| `data/tyres/hdc_235_35_19_front.tyre` | `5` | `1: (f32) 40 2: (f32) 2 3: (f32) 0.2 16: (f32) 0.47 17: (f32) 0.47 18: (f32) 0.565 19: (f32) 0.845 20: (f32) 10.7255 23: (f32) 0.8 24: (f32) 0.0007 25: "content\cars\hdc_bmw_e46_01\data\tyres\hdc_temperature_front.curve" 26: (f32) 1.6 27: (f32) 75 28: (f32) 0.06 110: (f32) 1100 111: (f32) 1600 112: (f32) 0.15 113: (f32) 3 114: (f32) 1.4 115: (f32) 0.9 116: (f32) 1000 117: (f32) 0.3 118: (f32) 0.8 4: (f32) 0.05512 5: (f32) 0.0503469 6: (f32) 2.11121 7: (f32) 0.02396 8: (f32) 0.00321149 9: (f32) 0.000336 10: (f32) 0.002175 11: (f32) 547.073 12: (f32) 0.0005 13: (f32) 0.0005 14: (f32) 2 15: (f32) 100 29: (f32) 7 30: (f32) 0.1` | [unknown] |
| `data/tyres/hdc_235_35_19_front.tyre` | `6` | `1: (f32) 0.25 2: (f32) 1.2 3: (f32) 0.1 4: (f32) 0.0025 5: (f32) 31 6: (f32) 28 8: (f32) 10010 9: (f32) 1 10: (f32) 10` | [unknown] |
| `data/tyres/hdc_235_35_19_front.tyre` | `7` | `1: (f32) 0.2 2: (f32) 5 3: (f32) -0.1 4: (f32) 0.6 5: (f32) -11 6: (f32) 15 7: (f32) 8` | [unknown] |
| `data/tyres/hdc_235_35_19_front.tyre` | `8` | `8: (f32) 4.5 9: (f32) 0.78 11: (f32) 0.78 12: (f32) 0.025 13: (f32) 70 112: (f32) 0.7 113: (f32) 4 114: (f32) 0.62 115: (f32) 0.095 116: (f32) 80 1: (f32) 0.74 2: (f32) 0.3 3: (f32) 0.7 4: (f32) 22 5: (f32) 3.1 6: (f32) 22 7: 1` | [unknown] |
| `data/tyres/hdc_235_35_19_front.tyre` | `9` | `1: (f32) 18.9921 2: (f32) 0.002 3: (f32) 646 4: (f32) 0.14` | [unknown] |
| `data/tyres/hdc_235_35_19_front.tyre` | `10` | `1: (f32) 0.441 2: (f32) 0.45 3: (f32) 0.45` | [unknown] |
| `data/tyres/hdc_235_35_19_front.tyre` | `11` | `(f32) 28` | [unknown] |
| `data/tyres/hdc_235_35_19_front.tyre` | `12` | `1: (f32) 235 2: (f32) 35 3: (f32) 19 4: (f32) 91 6: (f32) 30` | `12.1` width mm [verified]; `12.2`, `12.3` [inferred]; `12.4`, `12.6` [unknown] |
| `data/tyres/hdc_235_35_19_front.tyre` | `21` | `2` | [unknown] |
| `data/tyres/hdc_265_30_19_rear.tyre` | `1` | `"Hina's Drifters E46"` | [inferred] tyre name string |
| `data/tyres/hdc_265_30_19_rear.tyre` | `2` | `"SC"` | [unknown] |
| `data/tyres/hdc_265_30_19_rear.tyre` | `3` | `1: (f32) 0.265 2: (f32) 0.3208 3: (f32) 312000 4: (f32) 641.94 5: (f32) 1.6718 6: (f32) 0.2413 7: (f32) 0.001 8: (f32) 7 9: (f32) 6 10: (f32) 7 11: (f32) 38000 12: (f32) 2 13: (f32) 20000 14: (f32) 2.5 15: (f32) 450 16: (f32) 40 17: (f32) 0.1 19: (f32) 7.68269 20: (f32) 0.207365 21: (f32) 14.204 29: 2 30: (f32) 1 31: (f32) 0.5 32: (f32) 3 22: (f32) 4 23: (f32) 1 24: (f32) 180` | [unknown] |
| `data/tyres/hdc_265_30_19_rear.tyre` | `4` | `1: (f32) 1.19931 2: (f32) 1.2659 3: (f32) 0.863332 4: (f32) 0.9041 5: (f32) 3720 6: (f32) 8.35 7: (f32) 0.0207 8: (f32) 2 9: (f32) 0.05 10: (f32) 1.75 13: (f32) 0.77 14: "content\cars\hdc_bmw_e46_01\data\tyres\hdc_wear.curve" 15: (f32) 0.6 16: (f32) 0.001 17: (f32) 4 18: (f32) 0.10051 19: (f32) 0.10051 20: (f32) 0.12 21: (f32) 0.5 22: (f32) 0.2 23: (f32) 2.85 11: (f32) 0.96 12: (f32) 0.96` | [unknown] |
| `data/tyres/hdc_265_30_19_rear.tyre` | `5` | `1: (f32) 40 2: (f32) 2 3: (f32) 0.2 16: (f32) 0.47 17: (f32) 0.47 18: (f32) 0.565 19: (f32) 0.845 20: (f32) 10.6208 23: (f32) 0.8 24: (f32) 0.0007 25: "content\cars\hdc_bmw_e46_01\data\tyres\hdc_temperature_rear.curve" 26: (f32) 1.6 27: (f32) 75 28: (f32) 0.06 110: (f32) 1100 111: (f32) 1600 112: (f32) 0.15 113: (f32) 3 114: (f32) 1.4 115: (f32) 0.85 116: (f32) 1000 117: (f32) 0.3 118: (f32) 0.8 4: (f32) 0.05661 5: (f32) 0.0503038 6: (f32) 2.11106 7: (f32) 0.02267 8: (f32) 0.00283352 9: (f32) 0.000414 10: (f32) 0.0012 11: (f32) 559.377 12: (f32) 0.0005 13: (f32) 0.0005 14: (f32) 2 15: (f32) 100 29: (f32) 7 30: (f32) 0.1` | [unknown] |
| `data/tyres/hdc_265_30_19_rear.tyre` | `6` | `1: (f32) 0.25 2: (f32) 1.2 3: (f32) 0.1 4: (f32) 0.0025 5: (f32) 30 6: (f32) 26 8: (f32) 11440 9: (f32) 1 10: (f32) 10` | [unknown] |
| `data/tyres/hdc_265_30_19_rear.tyre` | `7` | `1: (f32) 0.2 2: (f32) 5 3: (f32) -0.1 4: (f32) 0.6 5: (f32) -11 6: (f32) 15 7: (f32) 8` | [unknown] |
| `data/tyres/hdc_265_30_19_rear.tyre` | `8` | `8: (f32) 4.5 9: (f32) 0.78 11: (f32) 0.78 12: (f32) 0.025 13: (f32) 70 112: (f32) 0.7 113: (f32) 4 114: (f32) 0.62 115: (f32) 0.095 116: (f32) 80 1: (f32) 0.74 2: (f32) 0.3 3: (f32) 0.7 4: (f32) 22 5: (f32) 3.1 6: (f32) 22 7: 1` | [unknown] |
| `data/tyres/hdc_265_30_19_rear.tyre` | `9` | `1: (f32) 19.4366 2: (f32) 0.002 3: (f32) 646 4: (f32) 0.14` | [unknown] |
| `data/tyres/hdc_265_30_19_rear.tyre` | `10` | `1: (f32) 0.441 2: (f32) 0.45 3: (f32) 0.45` | [unknown] |
| `data/tyres/hdc_265_30_19_rear.tyre` | `11` | `(f32) 24` | [unknown] |
| `data/tyres/hdc_265_30_19_rear.tyre` | `12` | `1: (f32) 265 2: (f32) 30 3: (f32) 19 4: (f32) 104 6: (f32) 30` | `12.1` width mm [verified]; `12.2`, `12.3` [inferred]; `12.4`, `12.6` [unknown] |
| `data/tyres/hdc_265_30_19_rear.tyre` | `21` | `2` | [unknown] |

Front and rear differ in groups: `3`, `4`, `5`, `6`, `9`, `11`, `12`; identical: `1`, `2`, `7`, `8`, `10`, `21` [verified]. Tyre selection and compatibility:

| file | pbedit path | current value | label |
|---|---|---|---|
| `data/cardata.car` | `10` | `"content\cars\hdc_bmw_e46_01\data\tyres\hdc_235_35_19_front.tyre"` | [verified] path of the front tyre file |
| `data/cardata.car` | `11` | `"content\cars\hdc_bmw_e46_01\data\tyres\hdc_265_30_19_rear.tyre"` | [verified] path of the rear tyre file |
| `data/hdc_bmw_e46_01.car` | `10` | `"content\cars\hdc_bmw_e46_01\data\tyres\hdc_235_35_19_front.tyre"` | same, devcopy |
| `data/hdc_bmw_e46_01.car` | `11` | `"content\cars\hdc_bmw_e46_01\data\tyres\hdc_265_30_19_rear.tyre"` | same, devcopy |
| `presets/tyres_e46csl.compatibletyres` | `1` | `<3 bytes>` | [unknown] |
| `presets/tyres_e46csl.compatibletyres` | `2` | `1: 71 2: "content\cars\hdc_bmw_e46_01\data\tyres\hdc_235_35_19_front.tyre" 3: "content\cars\hdc_bmw_e46_01\data\tyres\hdc_265_30_19_rear.tyre"` | [verified] front / rear tyre paths; `2.1` = 71 and `3.1` = 71 are an id? [unknown] |
| `presets/tyres_e46csl.compatibletyres` | `3` | `1: 71` | [unknown] |

### (d) Suspension, coilover, wing, aero

Top-level fields of each file (meanings [unknown]; the file names suggest front/rear suspension geometry, spring/damper blocks and aero surfaces [inferred]). Wing fields `7` / `8` are curve-file paths and are not listed. Copies: `cardata.car` `2.8` / `2.9` / `2.40` / `2.41` and `12.3[0-2]` hold identical blocks (`docs/car-anatomy.md` section 3).

| file | pbedit path | current value | label |
|---|---|---|---|
| `data/ks_bmw_m3_e46_front_1.coilover` | `1` | `(f32) 54000` | [unknown] |
| `data/ks_bmw_m3_e46_front_1.coilover` | `3` | `1: (f32) 0.0193681 2: (f32) 0.04 3: (f32) 80 4: (f32) 1.5 5: (f32) 0.05 6: (f32) 200` | [unknown] |
| `data/ks_bmw_m3_e46_front_1.coilover` | `4` | `1: (f32) 0.0556319 2: (f32) 0.03 3: (f32) 500 4: (f32) 1.5 5: (f32) 0.04 6: (f32) 500` | [unknown] |
| `data/ks_bmw_m3_e46_front_1.coilover` | `5` | `(f32) 0.0656319186` | [unknown] |
| `data/ks_bmw_m3_e46_front_1.coilover` | `6` | `1 {   1: (f32) 1700   2: (f32) 4600 } 2 {   1: (f32) 3400   2: (f32) 9200 } 3: (f32) 0.15 4: (f32) 0.15 12: ""` | [unknown] |
| `data/ks_bmw_m3_e46_front_1.coilover` | `9` | `""` | [unknown] |
| `data/ks_bmw_m3_e46_rear_1.coilover` | `1` | `(f32) 55000` | [unknown] |
| `data/ks_bmw_m3_e46_rear_1.coilover` | `3` | `1: (f32) 0.0746095 2: (f32) 0.04 3: (f32) 500 4: (f32) 1.5 5: (f32) 0.05 6: (f32) 500` | [unknown] |
| `data/ks_bmw_m3_e46_rear_1.coilover` | `4` | `1: (f32) 0.0153905 2: (f32) 0.03 3: (f32) 500 4: (f32) 1.5 5: (f32) 0.04 6: (f32) 500` | [unknown] |
| `data/ks_bmw_m3_e46_rear_1.coilover` | `5` | `(f32) 0.0153905433` | [unknown] |
| `data/ks_bmw_m3_e46_rear_1.coilover` | `6` | `1 {   1: (f32) 1300   2: (f32) 3900 } 2 {   1: (f32) 4800   2: (f32) 5700 } 3: (f32) 0.12 4: (f32) 0.12 12: ""` | [unknown] |
| `data/ks_bmw_m3_e46_rear_1.coilover` | `9` | `""` | [unknown] |
| `data/ks_bmw_m3_e46_front_sus_1.suspension` | `1` | `3: (f32) 32 4: (f32) 0.0005 5: (f32) -1.5 6: (f32) 0.05 1: (f32) -0.182 2: (f32) 1.623` | [unknown] |
| `data/ks_bmw_m3_e46_front_sus_1.suspension` | `3` | `1 {   1: (f32) 0.25   2: (f32) 0.41947   3: (f32) -0.098 } 2 {   1: (f32) 0.20467   2: (f32) 0.0984   3: (f32) -0.019 } 3 {   1: (f32) 0.50098   2: (f32) -0.15828   3: (f32) 0.02243 } 4 {   1: (f32) 0.5055   2: (f32) -0.16024   3: (f32) -0.29877 } 5 {   1: (f32) 0.10506   2: (f32) -0.19273   3: (f32) 0.01 } 6 {   1: (f32) 0.45097   2: (f32) -0.1432   3: (f32) 0.12571 } 7 {   1: (f32) 0.035   2: (f32) -0.16867   3: (f32) 0.13323 }` | [unknown] |
| `data/ks_bmw_m3_e46_rear_sus_1.suspension` | `1` | `3: (f32) 35 4: (f32) 0.0002 5: (f32) -2 6: (f32) 0.05 1: (f32) -0.197 2: (f32) 1.609` | [unknown] |
| `data/ks_bmw_m3_e46_rear_sus_1.suspension` | `2` | `1 {   1: (f32) 0.45334   2: (f32) 0.08514   3: (f32) 0.13607 } 2 {   1: (f32) 0.45921   2: (f32) 0.08956   3: (f32) 0.03252 } 3 {   1: (f32) 0.09542   2: (f32) -0.0549   3: (f32) 0.43865 } 4 {   1: (f32) 0.49542   2: (f32) 0.0251   3: (f32) 0.1 } 5 {   1: (f32) 0.07344   2: (f32) 0.07251   3: (f32) 0.01 } 6 {   1: (f32) 0.04509   2: (f32) -0.05886   3: (f32) -0.1 } 7 {   1: (f32) 0.48136   2: (f32) 0.0455   3: (f32) 0.2 } 8 {   1: (f32) 0.090284   2: (f32) -0.02236   3: (f32) 0.2 }` | [unknown] |
| `data/ks_bmw_m3_e46_rear_sus_m2.suspension` | `1` | `3: (f32) 35 4: (f32) 0.0002 5: (f32) -1.6 1: (f32) -0.197 2: (f32) 1.609` | [unknown] |
| `data/ks_bmw_m3_e46_rear_sus_m2.suspension` | `5` | `1 {   1: (f32) 0.324887   2: (f32) 0.058295   3: (f32) 0.185905 } 1 {   1: (f32) 0.380237   2: (f32) 0.110343   3: (f32) -0.031525 } 1 {   1: (f32) 0.368038   2: (f32) -0.103737   3: (f32) 0.249803 } 1 {   1: (f32) 0.515867   2: (f32) -0.11327   3: (f32) -0.156548 } 1 {   1: (f32) 0.482838   2: (f32) -0.044287   3: (f32) -0.20717 } 2 {   1: (f32) 0.083261   2: (f32) 0.066299   3: (f32) 0.055376 } 2 {   1: (f32) 0.10581   2: (f32) 0.130454   3: (f32) 0.020348 } 2 {   1: (f32) 0.06396   2: (f32) -0.14544   3: (f32) 0.02646 } 2 {   1: (f32) 0.129052   2: (f32) -0.101334   3: (f32) -0.05899 } 2 {   1: (f32) 0.104347   2: (f32) -0.03408   3: (f32) -0.174475 }` | [unknown] |
| `data/wings/ks_bmw_m3_e460.wing` | `2` | `"BODY"` | [unknown] |
| `data/wings/ks_bmw_m3_e460.wing` | `3` | `(f32) 1` | [unknown] |
| `data/wings/ks_bmw_m3_e460.wing` | `4` | `(f32) 2.06999993` | [unknown] |
| `data/wings/ks_bmw_m3_e460.wing` | `6` | `2: (f32) 0.13 3: (f32) -0.3` | [unknown] |
| `data/wings/ks_bmw_m3_e460.wing` | `11` | `(f32) 1` | [unknown] |
| `data/wings/ks_bmw_m3_e460.wing` | `15` | `<16 bytes>` | [unknown] |
| `data/wings/ks_bmw_m3_e460.wing` | `16` | `<16 bytes>` | [unknown] |
| `data/wings/ks_bmw_m3_e461.wing` | `2` | `"FRONT"` | [unknown] |
| `data/wings/ks_bmw_m3_e461.wing` | `3` | `(f32) 0.5` | [unknown] |
| `data/wings/ks_bmw_m3_e461.wing` | `4` | `(f32) 1.79999995` | [unknown] |
| `data/wings/ks_bmw_m3_e461.wing` | `6` | `2: (f32) -0.34 3: (f32) 1.9` | [unknown] |
| `data/wings/ks_bmw_m3_e461.wing` | `12` | `(f32) -0.100000001` | [unknown] |
| `data/wings/ks_bmw_m3_e461.wing` | `14` | `(f32) -0.0399999991` | [unknown] |
| `data/wings/ks_bmw_m3_e461.wing` | `15` | `<16 bytes>` | [unknown] |
| `data/wings/ks_bmw_m3_e461.wing` | `16` | `<16 bytes>` | [unknown] |
| `data/wings/ks_bmw_m3_e462.wing` | `2` | `"REAR"` | [unknown] |
| `data/wings/ks_bmw_m3_e462.wing` | `3` | `(f32) 0.5` | [unknown] |
| `data/wings/ks_bmw_m3_e462.wing` | `4` | `(f32) 1.79999995` | [unknown] |
| `data/wings/ks_bmw_m3_e462.wing` | `6` | `2: (f32) 0.58 3: (f32) -2.05` | [unknown] |
| `data/wings/ks_bmw_m3_e462.wing` | `12` | `(f32) -0.600000024` | [unknown] |
| `data/wings/ks_bmw_m3_e462.wing` | `14` | `(f32) -0.0599999987` | [unknown] |
| `data/wings/ks_bmw_m3_e462.wing` | `15` | `<16 bytes>` | [unknown] |
| `data/wings/ks_bmw_m3_e462.wing` | `16` | `<16 bytes>` | [unknown] |
| `data/wings/ks_bmw_m3_e463.wing` | `2` | `"DIFFUSER"` | [unknown] |
| `data/wings/ks_bmw_m3_e463.wing` | `3` | `(f32) 0.5` | [unknown] |
| `data/wings/ks_bmw_m3_e463.wing` | `4` | `(f32) 2.30999994` | [unknown] |
| `data/wings/ks_bmw_m3_e463.wing` | `6` | `2: (f32) -0.31 3: (f32) -2.15` | [unknown] |
| `data/wings/ks_bmw_m3_e463.wing` | `12` | `(f32) 1.60000002` | [unknown] |
| `data/wings/ks_bmw_m3_e463.wing` | `13` | `(f32) 1` | [unknown] |
| `data/wings/ks_bmw_m3_e463.wing` | `14` | `(f32) -0.0399999991` | [unknown] |
| `data/wings/ks_bmw_m3_e463.wing` | `15` | `<16 bytes>` | [unknown] |
| `data/wings/ks_bmw_m3_e463.wing` | `16` | `<16 bytes>` | [unknown] |

Aero curves (`data/aero/*.curve`, used by the wings; repeated field `1` = point {`1` x, `10` y}; axes and units [unknown], "aoa" / "cl" / "cd" in the names read as angle of attack, lift and drag coefficient [inferred]). Rounded to 6 significant digits:

| file | points | x range (rounded) | y range (rounded) |
|---|---|---|---|
| `data/aero/wing_body_aoa_cd.curve` | 7 | -30 .. 30 | 0.33 .. 0.7 |
| `data/aero/wing_body_aoa_cl.curve` | 7 | -10 .. 10 | 0 .. 0 |
| `data/aero/wing_front_aoa_cd.curve` | 11 | -10 .. 12 | 0 .. 0.1 |
| `data/aero/wing_front_aoa_cl.curve` | 12 | -10 .. 12 | 0.05 .. 0.14 |
| `data/aero/wing_rear_aoa_cd.curve` | 11 | -10 .. 12 | 0 .. 0.2 |
| `data/aero/wing_rear_aoa_cl.curve` | 10 | -10 .. 12 | 0.02 .. 0.16 |

The nine `data/wings/*.curve` files and `ks_bmw_m3_e463.wing` (diffuser, names two `ks_bmw_m4_csl` curves) have no `content\` referrer (refgraph) [verified].

### (e) Clutch, brake system, AI data

Top-level fields whose one-line value is at most 160 characters are listed; longer ones are counted. Meanings [unknown] (names suggest clutch, brakes, AI driver tuning [inferred]).

| file | pbedit path | current value | label |
|---|---|---|---|
| `data/ks_bmw_m3_e46_1.brakesystem` | `1` | `(f32) 3700` | [unknown] |
| `data/ks_bmw_m3_e46_1.brakesystem` | `2` | `(f32) 68` | [unknown] |
| `data/ks_bmw_m3_e46_1.brakesystem` | `3` | `(f32) 1100` | [unknown] |
| `data/ks_bmw_m3_e46_1.brakesystem` | `5` | `(f32) 0.5` | [unknown] |
| `data/ks_bmw_m3_e46_1.brakesystem` | `8` | `""` | [unknown] |
| `data/ks_bmw_m3_e46_1.brakesystem` | `9` | `""` | [unknown] |
| `data/ks_bmw_m3_e46_1.brakesystem` | `14` | `""` | [unknown] |
| `data/ks_bmw_m3_e46_1.clutch` | `1` | `(f32) 0.129999995` | [unknown] |
| `data/ks_bmw_m3_e46_1.clutch` | `2` | `(f32) 1000` | [unknown] |
| `data/ks_bmw_m3_e46_1.clutch` | `3` | `1: "content\cars\hdc_bmw_e46_01\data\upShiftProfile.curve" 2: "content\cars\hdc_bmw_e46_01\data\downShiftProfile.curve" 3: 1 4: (f32) 1200 5: (f32) 2800` | [unknown] |
| `data/ks_bmw_m3_e46_1.clutch` | `6` | `1: ""` | [unknown] |
| `data/ks_bmw_m3_e46_1.clutch` | `8` | `1: (f32) 1.214 2: (f32) 380 3: (f32) 11.8 4: (f32) 0.00206 5: (f32) 1` | [unknown] |
| `data/ks_bmw_m3_e46_1.clutch` | `9` | `1 {   2: (f32) -0.272   3: (f32) 0.1 } 2 {   1: (f32) 1.7   2: (f32) 0.1   3: (f32) 4 }` | [unknown] |
| `data/ks_bmw_m3_e46_1.clutch` | `10` | `"content\cars\ks_alfa_romeo_giulia_gtam\data\street_265-30-20.tyre"` | [unknown] |
| `data/ks_bmw_m3_e46_1.clutch` | `11` | `"content\cars\ks_alfa_romeo_giulia_gtam\data\street_285-30-20.tyre"` | [unknown] |
| `data/ks_bmw_m3_e46_1.clutch` | `14` | `3: "" 3: "" 3: "" 3: ""` | [unknown] |
| `data/ks_bmw_m3_e46_1.clutch` | `18` | `1 {   2: (f32) -0.49   3: (f32) -0.06 } 2: "" 3 {   1: (f32) 1   2: (f32) 1   3: (f32) 1 }` | [unknown] |
| `data/ks_bmw_m3_e46_1.clutch` | `20` | `"content\cars\ks_alfa_romeo_giulia_gtam\data\ks_alfa_romeo_giulia_gtam.carengine"` | [unknown] |
| `data/ks_bmw_m3_e46_1.clutch` | `21` | `"content\cars\ks_alfa_romeo_giulia_gtam\collider\alfa_romeo_giulia_gtam_collider.mesh"` | [unknown] |
| `data/ks_bmw_m3_e46_1.clutch` | `22` | `"content\cars\ks_alfa_romeo_giulia_gtam\data\ks_alfa_romeo_giulia_gtam.drivetrain"` | [unknown] |
| `data/ks_bmw_m3_e46_1.clutch` | `24` | `"content\cars\ks_alfa_romeo_giulia_gtam\data\ks_alfa_romeo_giulia_gtam.gearbox"` | [unknown] |
| `data/ks_bmw_m3_e46_1.clutch` | `25` | `1: (f32) 0.017 2: (f32) 750 3 {   2: "content\cars\ks_alfa_romeo_giulia_gtam\data\downShiftProfile.curve"   4: (f32) 1200   5: (f32) 1800 }` | [unknown] |
| `data/ks_bmw_m3_e46_1.clutch` | `26` | `"content\cars\ks_alfa_romeo_giulia_gtam\data\ks_alfa_romeo_giulia_gtam.clutch"` | [unknown] |
| `data/ks_bmw_m3_e46_1.clutch` | `17` | `1 {   2: (f32) -0.49   3: (f32) -0.06 } 2: "" 3 {   1: (f32) 1   2: (f32) 1   3: (f32) 1 }` | [unknown] |
| `data/ks_bmw_m3_e46_1.aicardata` | `1` | `1: 7573 2: 4094 5: 7700` | [unknown] |

Fields too long to list (one-line length in characters): `ks_bmw_m3_e46_1.clutch` `1[1]` (259); `ks_bmw_m3_e46_1.clutch` `2[1]` (2306); `ks_bmw_m3_e46_1.clutch` `4` (696); `ks_bmw_m3_e46_1.clutch` `5` (494); `ks_bmw_m3_e46_1.clutch` `7` (622); `ks_bmw_m3_e46_1.clutch` `12` (1732); `ks_bmw_m3_e46_1.clutch` `23` (484); `ks_bmw_m3_e46_1.aicardata` `5` (4694).

Observation [verified]: the 4027-byte clutch file is not a small clutch message. After its first fields it holds blocks that look like a car-data message: `1[1].2` = "Alfa Romeo Giulia Quadrifoglio" (present), a wing block `12` named "BODY", a gear block `23` carrying the E46 drivetrain ratios (see (b)) and 30 `ks_alfa_romeo_giulia_gtam` paths. Whether the game reads those blocks is [unknown] (`docs/drift-deltas.md` question 6). The `cardata.car` copy at field `25` is the same 4027 bytes.

### (f) Steering

**No steering-lock or steering-angle field has been identified in this package [verified: none is named or documented; there are no field names in the data].** Answering it needs the schemas (`HANDOVER.md` section 6) or an in-game check. What exists, with the evidence for each:

| file | pbedit path | current value | label |
|---|---|---|---|
| `data/setup/hdc_bmw_e46_01.carsetup` | `1.2` | `(f32) 14` | [inferred] steer ratio default (HANDOVER 7; lever `steer_ratio`) |
| `data/setup/limits_m3_e46.carsetuplimits` | `1.2` | `1: (f32) 0.1 2: (f32) 14 3: (f32) 14 4: 0` | [inferred] its range: step, min, max, enabled; `4` = 0 means the setup screen does not offer it? [unknown] |
| `data/cardata.car` | `8` | `1: (f32) 1.5 2: (f32) 450 3: (f32) 14 4: (f32) 0.0026 5: (f32) 1` | [inferred] candidate steering block, see below |
| `data/cardata.car` | `8.2` | `(f32) 450` | [inferred] steering-wheel angle in degrees? [general: ~450 would be plausible for half-lock] |
| `data/cardata.car` | `8.3` | `(f32) 14` | [inferred] steer ratio: equals setup `1.2` in all six HDC cars, see below |
| `data/hdc_bmw_e46_01.car` | `8` | `1: (f32) 1.5 2: (f32) 450 3: (f32) 14 4: (f32) 0.0025 5: (f32) 1` | [inferred] same block, devcopy; differs from `cardata.car` in leaf `8.4` |
| `data/hdc_bmw_e46_01.car` | `8.3` | `(f32) 14` | [inferred] steer ratio, devcopy |

Evidence for `cardata.car` `8.3` [verified, six packages under `hdc_1.4/extracted/`]: it equals carsetup `1.2` in all six HDC cars, sign included:

| car | cardata `8.2` | cardata `8.3` | carsetup `1.2` | `8.3` vs `1.2` |
|---|---|---|---|---|
| ae86 | (f32) 450 | (f32) -14 | (f32) -14 | equal |
| datsun | (f32) 630 | (f32) 17.7999992 | (f32) 17.7999992 | equal |
| e46 | (f32) 450 | (f32) 14 | (f32) 14 | equal |
| mercedes | (f32) 486 | (f32) -15.2700005 | (f32) -15.2700005 | equal |
| rx7 | (f32) 450 | (f32) 14 | (f32) 14 | equal |
| s2000 | (f32) 422 | (f32) 13.8999996 | (f32) 13.8999996 | equal |

Reading [inferred]: `8.3` is the steering ratio (a second copy of the setup value; `tune.py` edits only the setup copy for `steer_ratio`), and `8.2` varies per car in a range that would fit steering-wheel degrees [general]; not proven. The limits entry for `1.2` has min = max and `enabled` = 0 for the E46, so the setup screen probably cannot change it [inferred]. Anything in the suspension files (geometry points) that sets the real wheel lock is [unknown]. Alternatives to a steering-angle field (a wheel-angle limit in the suspension or tyre data) are [unknown]: no field in the data can be justified by name or value.

## 4. Drifting: what to change and why

Everything in the "why" column is [general] (general knowledge about drifting, not from the files). The last column says what in this repository would implement it. No numbers are recommended beyond those already in `drift_v0`.

| topic | why it matters | repo lever or candidate group |
|---|---|---|
| Rear differential lock and preload | [general] a (near) locked rear diff makes both rear wheels spin together, which makes sustained slides easier to start and hold | `diff_power_lock`, `diff_coast_lock`, `diff_preload` + `*_min` / `*_max` limits (drift_v0 sets lock 1.0 / 1.0, preload 80, range maxima 1.0 / 1.0 / 120) |
| Torque and power band | [general] more torque at the rear wheels and a usable curve over the slide rpm range help break and keep traction | `engine_torque_scale` (drift_v0 x1.2); curve shape: no lever yet |
| Rev limiter / engine rpm range | [general] a limiter above the rpm used while sliding avoids bouncing off it | `rev_limiter_rpm` |
| Gearing | [general] gear and final-drive ratios set rpm and wheel torque at slide speeds | `final_drive_drivetrain`, `final_drive_gearbox`; per-gear ratios: no lever yet, candidate group (b) (two disagreeing sets) |
| Steering angle and ratio | [general] large steering angle lets the car hold deep angle without spinning out | no lever for angle; `steer_ratio*` (setup `1.2`, range disabled) and candidate `cardata.car` `8.2` / `8.3` (candidate group (f)) |
| Front / rear grip balance (tyres) | [general] rear grip lower than front and the tyre model's response shape the slide balance | no lever yet; candidate group (c) (all tyre fields [unknown]) |
| Tyre pressures, camber, toe | [general] cheap balance adjustments per axle | no lever yet; candidate group (a) (`carsetup` `4`, `carsetuplimits` `4`) |
| Springs, dampers, anti-roll, ride height | [general] weight transfer speed and body control | no lever yet; candidate groups (a) and (d) |
| Weight and weight distribution | [general] mass affects inertia and traction; distribution affects balance | `mass_kg` (`cardata.car` `1.1`); distribution: no lever, field [unknown] |
| Brake bias and brake power | [general] rear-biased braking and handbrake use are used to start slides | no lever yet; candidate group (a) (`carsetup` `1.3`) and (e) (`brakesystem`) |
| Aero | [general] little effect at drift speeds | no lever yet; candidate group (d) |

## 5. Verification status

Proven by the repo's tools and tests, re-run for this document [verified]:

| claim | command | result |
|---|---|---|
| pbedit lossless parse / re-encode of every E46 file | `python3 -I tools/pbedit.py roundtrip hdc_1.4/extracted/e46` | 157 files: 144 identical, 0 canonical-differs, 13 not-protobuf |
| unit tests (pbedit, tune, testkit) | `python3 -B -m unittest discover -s tests` | Ran 44 tests in 0.516s, OK |
| tune check: all copies agree with the baselines | `python3 -I tools/tune.py check spec/e46_levers.json hdc_1.4/extracted/e46` | 37 targets, 37 ok, 0 mismatch, 0 missing |
| tune apply then check: every copy of a profile changed consistently | section 1 example (`drift_v0`) | 37 targets, 37 ok, 0 mismatch, 0 missing; apply printed 16 edit lines |
| repack of the unchanged tree is byte-identical to the original package | `python3 -I tools/kspkg.py pack hdc_1.4/extracted/e46 <out>` | 123,731,968 bytes, sha256 `59d1bad1c5652d334c34351157a5ab85756b9b1a1aca5e2056e0d7c423669e47` = `spec/e46_package.sha256` |

Not proven [unknown]: **anything about in-game behaviour.** Nothing has been tested in the game: not that the game loads a repacked or edited package, not which copy of a value it reads, not whether the diff, rev-limiter, torque or gear fields mean what is inferred here, not that edited setup ranges appear in the setup screen, and not what any `[unknown]` field does. The PC test plan is `docs/pc-test-protocol.md` (variants A, B1, B2, C, D, F); its results decide which copies need editing.
