# Drift deltas in Hina's Drift Club 1.4 cars

Facts extracted from the six HDC car packages under `hdc_1.4/extracted/` (read-only reference, Hina's release). Reference only: no tuned derivative is published from this. Short names: ae86 = `ks_ae86_beginner_h_01`, datsun = `hdc_datsun_240z_01`, e46 = `hdc_bmw_e46_01`, mercedes = `hdc_mercedes_190e_01`, rx7 = `hdc_rx7_fd_01`, s2000 = `hdc_honda_s2000_ap1_01`.

## 0. Method and legend

- Every number was computed from the extracted files by a throw-away script (not in the repo) that uses `tools/pbedit.py` (`parse`, `get_field`, `format_value`). A leaf is a field not descended into (scalar, string, or bytes that `format_value` does not treat as a message); paths are pbedit paths with `[i]` omitted when i = 0. Section 2 value cells are exactly `format_value` output (floats `%.9g`; a nested message, if one side holds one, is collapsed to one line as `pbedit set` does); Sections 1, 3 and the curve tables round to 6 significant digits (`%.6g`).
- Labels: `[verified]` = read directly from files or computed by diff; `[inferred]` = meaning guessed from values or naming (only these meanings are used: drivetrain `39.1/39.2/39.3` = diff power lock/coast lock/preload Nm; carsetup `1.4.1-3` and carsetuplimits `1.4.n.1-4` = same triple and step/min/max/enabled; carengine `5`/`6` = idle/limiter rpm, `2`/`3` = power/coast curve path; curve field `1` = rpm, `10` = torque Nm; gearbox/drivetrain gear-count, ratio and final-drive fields as in HANDOVER section 7; `.tyre` `12.1` = width mm); `[unknown]` = no meaning established. In Section 2 tables the values are [verified]; the `label` column carries only the meaning label of the path.
- File cells in Sections 1 and 2 are relative to the car root `hdc_1.4/extracted/<short>/content/cars/<car_id>/` (so they start with `data/`); the car is named in the sub-section heading. Counting rule for diffs: leaves are compared by path, so a field present in one file only counts once, and a value present as `(absent)` may be a proto3 default [unknown].
- Checker (scratchpad, not in repo): re-reads every Section 2 row with 6 cells (`file A | file B | path | value A | value B | label`), calls `pbedit.get_field` + `format_value` on both files and compares with the cells; `(absent)` rows assert that the path does not exist.

## 1. Inline vs separate copies

For each top-level length-delimited field of `data/cardata.car`, the table lists the files of the same package with a byte-identical payload (all files up to 3 MB were compared). Message fields without such a file also get the files referenced by `content\cars\<id>\...` strings inside them (only those that exist in the package): a referenced file counts as embedded if a nested sub-block of the field is byte-identical (`=`), leaf-identical with different bytes (`~`), or shares at least half of its leaves (then the differing leaf paths are listed, up to 10); otherwise it is reported as not embedded. String (path) fields cannot be byte-identical to a file, so all string fields of a car are summarised in its last row with the file each path resolves to (case-insensitive) and the inline field that is byte-identical to that file. [verified]

Inline block equals the file named by its path field (inline field = path field): 

| car | 3 = 22 (drivetrain) | 4 = 20 (engine) | 5 = 27 (brakesystem) | 23 = 24 (gearbox) | 25 = 26 (clutch) |
|---|---|---|---|---|---|
| ae86 | yes | yes | yes | yes | yes |
| datsun | yes | yes | yes | yes | yes |
| e46 | yes | yes | yes | yes | yes |
| mercedes | yes | yes | yes | yes | yes |
| rx7 | yes | yes | yes | yes | yes |
| s2000 | yes | yes | yes | yes | yes |

### ae86 (ks_ae86_beginner_h_01)
- top-level field numbers in `data/cardata.car` (file order, `xN` = repeated): 1, 2, 3, 4, 5, 6, 7, 8, 9x3, 12, 16, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 29, 190, 10, 11 [verified]
- no `data/ks_ae86_beginner_h_01.car` in this package (only `data/cardata.car`) [verified]
- field 25: present, 153 B, byte-identical to data/ks_ae86_beginner_h_01.clutch; inner top-level field numbers: 1, 2, 3; `content\cars\<id>\` ids inside: own id `ks_ae86_beginner_h_01` x2, no other car id [verified]; other car ids in all string leaves of `data/cardata.car`: none

| car | cardata.car field | payload | byte-identical separate file(s) | note |
|---|---|---|---|---|
| ae86 | 2 | msg 1301 B | no identical file | nested byte-identical: `2.8` = `data/ks_ae86_beginner_h_01_front.coilover`; `2.9` = `data/ks_ae86_beginner_h_01_rear.coilover`; `2.40` = `data/ks_ae86_beginner_h_01_front.suspension`; `2.41` = `data/ks_ae86_beginner_h_01rear_rear.suspension` |
| ae86 | 3 | msg 84 B | `data/ks_ae86_beginner_h_01.drivetrain` | path field 22 points to this file |
| ae86 | 4 | msg 296 B | `data/parts/ks_ae86_beginner_h_01_tuned.carengine` | path field 20 points to this file |
| ae86 | 5 | msg 26 B | `data/ks_ae86_beginner_h_01.brakesystem` | path field 27 points to this file |
| ae86 | 12 | msg 848 B | no identical file | nested byte-identical: `12.3` = `data/ks_ae86_beginner_h_010.wing`; `12.3[1]` = `data/ks_ae86_beginner_h_011.wing`; `12.3[2]` = `data/ks_ae86_beginner_h_012.wing`; 6 referenced file(s) not embedded as a sub-block: data/wing_body_aoa_cd.curve, data/wing_body_aoa_cl.curve, data/wing_front_aoa_cd.curve (+3) |
| ae86 | 23 | msg 204 B | `data/ks_ae86_beginner_h_01.gearbox` | path field 24 points to this file |
| ae86 | 25 | msg 153 B | `data/ks_ae86_beginner_h_01.clutch` | path field 26 points to this file |
| ae86 | 1, 6, 7, 8, 9[0], 9[1], 9[2], 18 | msg, 8 fields | no identical file | message fields with no `content\cars\...` string and no leaf-identical file; sizes: 1 (116 B), 6 (2 B), 7 (55 B), 8 (25 B), 9[0] (34 B), 9[1] (34 B), 9[2] (34 B), 18 (36 B) |
| ae86 | 16,19,20,21,22,24,26,27,29,190,10,11 (strings) | 12 fields | no identical file (strings) | 16 -> `data/setup/toyota_ae86_tuned.carsetuplimits`; 19 -> `data/setup/toyota_ae86_tuned.carsetup`; 20 -> `data/parts/ks_ae86_beginner_h_01_tuned.carengine` (inline 4 identical); 21 -> `collider/toyota_ae86_sprinter_trueno_collider.mesh`; 22 -> `data/ks_ae86_beginner_h_01.drivetrain` (inline 3 identical); 24 -> `data/ks_ae86_beginner_h_01.gearbox` (inline 23 identical); 26 -> `data/ks_ae86_beginner_h_01.clutch` (inline 25 identical); 27 -> `data/ks_ae86_beginner_h_01.brakesystem` (inline 5 identical); 29 -> `data/ks_ae86_beginner_h_01.aicardata`; 190 -> `data/setup/toyota_ae86_tuned.carsetup`; 10 -> `tyres/gs_philosophy_v1/gs_derived_185_60_14_front.tyre`; 11 -> `tyres/gs_philosophy_v1/gs_derived_185_60_14_rear.tyre` |

### datsun (hdc_datsun_240z_01)
- top-level field numbers in `data/cardata.car` (file order, `xN` = repeated): 1, 2, 3, 4, 5, 6, 7, 8, 9x3, 12, 16, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 29, 202, 17, 10, 11, 190 [verified]
- no `data/hdc_datsun_240z_01.car` in this package (only `data/cardata.car`) [verified]
- field 25: present, 145 B, byte-identical to data/tuning/hdc_datsun_240z_01_clutch_5speed.clutch; inner top-level field numbers: 1, 2, 3; `content\cars\<id>\` ids inside: own id `hdc_datsun_240z_01` x2, no other car id [verified]; other car ids in all string leaves of `data/cardata.car`: none

| car | cardata.car field | payload | byte-identical separate file(s) | note |
|---|---|---|---|---|
| datsun | 2 | msg 1230 B | no identical file | nested byte-identical: `2.8` = `data/tuning/hdc_datsun_240z_01_g_nose_front.coilover`; `2.9` = `data/tuning/hdc_datsun_240z_01_g_nose_rear.coilover`; `2.40` = `data/hdc_datsun_240z_01_front.suspension`; `2.41` = `data/hdc_datsun_240z_01_rear.suspension` |
| datsun | 3 | msg 393 B | `data/tuning/hdc_datsun_240z_01_lsd.drivetrain` | path field 22 points to this file |
| datsun | 4 | msg 311 B | `data/tuning/hdc_datsun_240z_01_l28engine.carengine` | path field 20 points to this file |
| datsun | 5 | msg 26 B | `data/tuning/hdc_datsun_240z_01_brakes.brakesystem` | path field 27 points to this file |
| datsun | 12 | msg 833 B | no identical file | nested byte-identical: `12.3` = `data/aero/ks_datsun_240z_body.wing`; `12.3[1]` = `data/aero/ks_datsun_240z_front.wing`; `12.3[2]` = `data/aero/ks_datsun_240z_rear.wing`; 6 referenced file(s) not embedded as a sub-block: data/aero/wing_body_aoa_cd.curve, data/aero/wing_body_aoa_cl.curve, data/aero/wing_front_aoa_cd.curve (+3) |
| datsun | 23 | msg 187 B | `data/tuning/hdc_datsun_240z_01_5speed.gearbox` | path field 24 points to this file |
| datsun | 25 | msg 145 B | `data/tuning/hdc_datsun_240z_01_clutch_5speed.clutch` | path field 26 points to this file |
| datsun | 1, 6, 7, 8, 9[0], 9[1], 9[2], 18, 17 | msg, 9 fields | no identical file | message fields with no `content\cars\...` string and no leaf-identical file; sizes: 1 (121 B), 6 (2 B), 7 (2 B), 8 (25 B), 9[0] (29 B), 9[1] (29 B), 9[2] (29 B), 18 (36 B), 17 (36 B) |
| datsun | 16,19,20,21,22,24,26,27,29,202,10,11,190 (strings) | 13 fields | no identical file (strings) | 16 -> `data/setup/hdc_datsun_240z_01_g_nose.carsetuplimits`; 19 -> `data/setup/hdc_datsun_240z_01_g_nose.carsetup`; 20 -> `data/tuning/hdc_datsun_240z_01_l28engine.carengine` (inline 4 identical); 21 -> `collider/datsun_240z_fairlady_collider.mesh`; 22 -> `data/tuning/hdc_datsun_240z_01_lsd.drivetrain` (inline 3 identical); 24 -> `data/tuning/hdc_datsun_240z_01_5speed.gearbox` (inline 23 identical); 26 -> `data/tuning/hdc_datsun_240z_01_clutch_5speed.clutch` (inline 25 identical); 27 -> `data/tuning/hdc_datsun_240z_01_brakes.brakesystem` (inline 5 identical); 29 -> `data/hdc_datsun_240z_01.aicardata`; 202: string `Hina's Drift Club - 240Z G-Nose`; 10 -> `data/tyres/hdc_225_50_15_front.tyre`; 11 -> `data/tyres/hdc_225_50_15_rear.tyre`; 190 -> `data/setup/hdc_datsun_240z_01_g_nose.carsetup` |

### e46 (hdc_bmw_e46_01)
- top-level field numbers in `data/cardata.car` (file order, `xN` = repeated): 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 29, 202, 30, 190, 10, 11 [verified]
- `data/hdc_bmw_e46_01.car` exists (8089 B vs 8089 B). Differing leaf paths cardata.car vs hdc_bmw_e46_01.car: 1 [verified]; `8.4` `(f32) 0.00260000001` vs `(f32) 0.00249999994`
- field 25: present, 4027 B, byte-identical to data/ks_bmw_m3_e46_1.clutch; inner top-level field numbers: 1x2, 2x2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 18, 20, 21, 22, 23, 24, 25, 26, 17; `content\cars\<id>\` ids inside: own id `hdc_bmw_e46_01` x2, `ks_alfa_romeo_giulia_gtam` x30 [verified]; other car ids in all string leaves of `data/cardata.car`: `ks_alfa_romeo_giulia_gtam` x32

| car | cardata.car field | payload | byte-identical separate file(s) | note |
|---|---|---|---|---|
| e46 | 2 | msg 949 B | no identical file | nested byte-identical: `2.8` = `data/ks_bmw_m3_e46_front_1.coilover`; `2.9` = `data/ks_bmw_m3_e46_rear_1.coilover`; `2.40` = `data/ks_bmw_m3_e46_front_sus_1.suspension`; `2.41` = `data/ks_bmw_m3_e46_rear_sus_m2.suspension` |
| e46 | 3 | msg 398 B | `data/ks_bmw_m3_e46_1.drivetrain` | path field 22 points to this file |
| e46 | 4 | msg 449 B | `data/ks_bmw_m3_e46_engine_1.carengine` | path field 20 points to this file |
| e46 | 5 | msg 26 B | `data/ks_bmw_m3_e46_1.brakesystem` | path field 27 points to this file |
| e46 | 12 | msg 794 B | no identical file | nested byte-identical: `12.3` = `data/wings/ks_bmw_m3_e460.wing`; `12.3[1]` = `data/wings/ks_bmw_m3_e461.wing`; `12.3[2]` = `data/wings/ks_bmw_m3_e462.wing`; 6 referenced file(s) not embedded as a sub-block: data/aero/wing_body_aoa_cd.curve, data/aero/wing_body_aoa_cl.curve, data/aero/wing_front_aoa_cd.curve (+3) |
| e46 | 23 | msg 202 B | `data/ks_bmw_m3_e46_1.gearbox` | path field 24 points to this file |
| e46 | 25 | msg 4027 B | `data/ks_bmw_m3_e46_1.clutch` | path field 26 points to this file |
| e46 | 1, 6, 7, 8, 18, 30 | msg, 6 fields | no identical file | message fields with no `content\cars\...` string and no leaf-identical file; sizes: 1 (105 B), 6 (2 B), 7 (205 B), 8 (25 B), 18 (36 B), 30 (33 B) |
| e46 | 16,19,20,21,22,24,26,27,29,202,190,10,11 (strings) | 13 fields | no identical file (strings) | 16 -> `data/setup/limits_m3_e46.carsetuplimits`; 19 -> `data/setup/hdc_bmw_e46_01.carsetup`; 20 -> `data/ks_bmw_m3_e46_engine_1.carengine` (inline 4 identical); 21 -> `collider/bmw_m3_e46_csl_collider.mesh`; 22 -> `data/ks_bmw_m3_e46_1.drivetrain` (inline 3 identical); 24 -> `data/ks_bmw_m3_e46_1.gearbox` (inline 23 identical); 26 -> `data/ks_bmw_m3_e46_1.clutch` (inline 25 identical); 27 -> `data/ks_bmw_m3_e46_1.brakesystem` (inline 5 identical); 29 -> `data/ks_bmw_m3_e46_1.aicardata`; 202: string `Hina's Drift Club - BMW M3 CSL`; 190 -> `data/setup/hdc_bmw_e46_01.carsetup`; 10 -> `data/tyres/hdc_235_35_19_front.tyre`; 11 -> `data/tyres/hdc_265_30_19_rear.tyre` |

### mercedes (hdc_mercedes_190e_01)
- top-level field numbers in `data/cardata.car` (file order, `xN` = repeated): 1, 2, 3, 4, 5, 6, 7, 8, 9x2, 12, 16, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 29, 17, 202, 10, 11, 190 [verified]
- no `data/hdc_mercedes_190e_01.car` in this package (only `data/cardata.car`) [verified]
- field 25: present, 3020 B, byte-identical to data/hdc_mercedes_190e_01.clutch; inner top-level field numbers: 1x2, 2x2, 3, 4, 5, 6, 7, 8, 9x2, 10, 11, 12, 14, 18, 20, 21, 22, 23, 24, 25, 26, 17; `content\cars\<id>\` ids inside: own id `hdc_mercedes_190e_01` x23, `ks_mercedes_190e_evo_ii` x2 [verified]; other car ids in all string leaves of `data/cardata.car`: `ks_mercedes_190e_evo_ii` x2

| car | cardata.car field | payload | byte-identical separate file(s) | note |
|---|---|---|---|---|
| mercedes | 2 | msg 1275 B | no identical file | nested byte-identical: `2.8` = `data/hdc_mercedes_190e_01_front.coilover`; `2.9` = `data/hdc_mercedes_190e_01_rear.coilover`; `2.40` = `data/hdc_mercedes_190e_01_front.suspension`; `2.41` = `data/hdc_mercedes_190e_01_rear.suspension` |
| mercedes | 3 | msg 363 B | `data/hdc_mercedes_190e_01.drivetrain` | path field 22 points to this file |
| mercedes | 4 | msg 220 B | `data/hdc_mercedes_190e_01.carengine` | path field 20 points to this file |
| mercedes | 5 | msg 28 B | `data/hdc_mercedes_190e_01.brakesystem` | path field 27 points to this file |
| mercedes | 12 | msg 960 B | no identical file | nested byte-identical: `12.3` = `data/hdc_mercedes_190e_010.wing`; `12.3[1]` = `data/hdc_mercedes_190e_011.wing`; `12.3[2]` = `data/hdc_mercedes_190e_012.wing`; 8 referenced file(s) not embedded as a sub-block: data/height_front_cd.curve, data/height_front_cl.curve, data/wing_body_aoa_cd.curve (+5) |
| mercedes | 23 | msg 189 B | `data/hdc_mercedes_190e_01.gearbox` | path field 24 points to this file |
| mercedes | 25 | msg 3020 B | `data/hdc_mercedes_190e_01.clutch` | path field 26 points to this file |
| mercedes | 1, 6, 7, 8, 9[0], 9[1], 18, 17 | msg, 8 fields | no identical file | message fields with no `content\cars\...` string and no leaf-identical file; sizes: 1 (125 B), 6 (2 B), 7 (60 B), 8 (25 B), 9[0] (29 B), 9[1] (29 B), 18 (36 B), 17 (36 B) |
| mercedes | 16,19,20,21,22,24,26,27,29,202,10,11,190 (strings) | 13 fields | no identical file (strings) | 16 -> `data/setup/mercedes_190e_evo_ii.carsetuplimits`; 19 -> `data/setup/mercedes_190e_evo_ii.carsetup`; 20 -> `data/hdc_mercedes_190e_01.carengine` (inline 4 identical); 21 -> `collider/mercedes_190e_evo_ii_collider.mesh`; 22 -> `data/hdc_mercedes_190e_01.drivetrain` (inline 3 identical); 24 -> `data/hdc_mercedes_190e_01.gearbox` (inline 23 identical); 26 -> `data/hdc_mercedes_190e_01.clutch` (inline 25 identical); 27 -> `data/hdc_mercedes_190e_01.brakesystem` (inline 5 identical); 29 -> `data/hdc_mercedes_190e_01.aicardata`; 202: string `Hina's Drift Club - Mercedes 190E Evo II`; 10 -> `data/tyres/hdc_245_40_17_front.tyre`; 11 -> `data/tyres/hdc_245_40_17_rear.tyre`; 190 -> `data/setup/mercedes_190e_evo_ii.carsetup` |

### rx7 (hdc_rx7_fd_01)
- top-level field numbers in `data/cardata.car` (file order, `xN` = repeated): 1, 2, 3, 4, 5, 6, 7, 8, 9x2, 12, 16, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 29, 190, 202, 17, 101x3, 10, 11 [verified]
- no `data/hdc_rx7_fd_01.car` in this package (only `data/cardata.car`) [verified]
- field 25: present, 3767 B, byte-identical to data/hdc_rx7_fd_01.clutch; inner top-level field numbers: 1x2, 2x2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 16, 18, 19, 20, 21, 22, 23, 24, 25, 26, 17, 101x3; `content\cars\<id>\` ids inside: own id `hdc_rx7_fd_01` x24, `ks_mazda_rx7_fd` x4, `mazda_rx7` x3 [verified]; other car ids in all string leaves of `data/cardata.car`: `ks_mazda_rx7_fd` x4, `mazda_rx7` x6

| car | cardata.car field | payload | byte-identical separate file(s) | note |
|---|---|---|---|---|
| rx7 | 2 | msg 1289 B | no identical file | nested byte-identical: `2.8` = `data/hdc_rx7_fd_01_front.coilover`; `2.9` = `data/hdc_rx7_fd_01_rear.coilover`; `2.40` = `data/hdc_rx7_fd_01_front.suspension`; `2.41` = `data/hdc_rx7_fd_01_rear.suspension` |
| rx7 | 3 | msg 429 B | `data/hdc_rx7_fd_01.drivetrain` | path field 22 points to this file |
| rx7 | 4 | msg 529 B | `data/engine/rx7_engine.carengine` | path field 20 points to this file |
| rx7 | 5 | msg 24 B | `data/hdc_rx7_fd_01.brakesystem` | path field 27 points to this file |
| rx7 | 6 | empty 0 B | `data/mazda_rx7_build.cartuning` | trivial match (empty payload equals 0-byte file); no path field points to it |
| rx7 | 12 | msg 597 B | no identical file | nested byte-identical: `12.3` = `data/wing_body.wing`; `12.3[1]` = `data/wing_front_modifier.wing`; `12.3[2]` = `data/wing_rear_modifier.wing`; 5 referenced file(s) not embedded as a sub-block: data/wing_body_aoa_cd.curve, data/wing_body_aoa_cl.curve, data/wing_front_aoa_cl.curve (+2) |
| rx7 | 23 | msg 203 B | `data/hdc_rx7_fd_01.gearbox` | path field 24 points to this file |
| rx7 | 25 | msg 3767 B | `data/hdc_rx7_fd_01.clutch` | path field 26 points to this file |
| rx7 | 1, 7, 8, 9[0], 9[1], 18, 17 | msg, 7 fields | no identical file | message fields with no `content\cars\...` string and no leaf-identical file; sizes: 1 (109 B), 7 (55 B), 8 (25 B), 9[0] (29 B), 9[1] (29 B), 18 (31 B), 17 (31 B) |
| rx7 | 16,19,20,21,22,24,26,27,29,190,202,101[0],101[1],101[2],10,11 (strings) | 16 fields | no identical file (strings) | 16 -> `data/setup/hdc_rx7_fd_01.carsetuplimits`; 19 -> `data/setup/hdc_rx7_fd_01.carsetup`; 20 -> `data/engine/rx7_engine.carengine` (inline 4 identical); 21 -> `collider/mazda_rx7_spirit_r_collider.mesh`; 22 -> `data/hdc_rx7_fd_01.drivetrain` (inline 3 identical); 24 -> `data/hdc_rx7_fd_01.gearbox` (inline 23 identical); 26 -> `data/hdc_rx7_fd_01.clutch` (inline 25 identical); 27 -> `data/hdc_rx7_fd_01.brakesystem` (inline 5 identical); 29 -> `data/hdc_rx7_fd_01.aicardata`; 190 -> `data/setup/hdc_rx7_fd_01.carsetup`; 202: string `Hina's Drift Club - RX-7`; 101[0] -> `content/cars/mazda_rx7/data/Street90S (SV)REAR.tyre` (not in package); 101[1] -> `content/cars/mazda_rx7/data/Street (ST)REAR.tyre` (not in package); 101[2] -> `content/cars/mazda_rx7/data/Semislicks (SM)REAR.tyre` (not in package); 10 -> `data/tyres/hdc_235_45_17_front.tyre`; 11 -> `data/tyres/hdc_255_40_17_rear.tyre` |

### s2000 (hdc_honda_s2000_ap1_01)
- top-level field numbers in `data/cardata.car` (file order, `xN` = repeated): 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 16, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 29, 17, 202, 190 [verified]
- no `data/hdc_honda_s2000_ap1_01.car` in this package (only `data/cardata.car`) [verified]
- field 25: present, 2927 B, byte-identical to data/hdc_honda_s2000_ap1_01.clutch; inner top-level field numbers: 1x2, 2x2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 18, 20, 21, 22, 23, 24, 25, 26, 17; `content\cars\<id>\` ids inside: own id `hdc_honda_s2000_ap1_01` x21, `ks_honda_s2000_ap1` x2 [verified]; other car ids in all string leaves of `data/cardata.car`: `ks_honda_s2000_ap1` x2

| car | cardata.car field | payload | byte-identical separate file(s) | note |
|---|---|---|---|---|
| s2000 | 2 | msg 1323 B | no identical file | nested byte-identical: `2.8` = `data/hdc_honda_s2000_ap1_01_front.coilover`; `2.9` = `data/hdc_honda_s2000_ap1_01_rear.coilover`; `2.40` = `data/hdc_honda_s2000_ap1_01_front.suspension`; nested leaf-identical but bytes differ (field order): `2.41` ~ `data/hdc_honda_s2000_ap1_01_rear.suspension` |
| s2000 | 3 | msg 365 B | `data/hdc_honda_s2000_ap1_01.drivetrain` | path field 22 points to this file |
| s2000 | 4 | msg 311 B | `data/hdc_honda_s2000_ap1_01.carengine` | path field 20 points to this file |
| s2000 | 5 | msg 197 B | `data/hdc_honda_s2000_ap1_01.brakesystem` | path field 27 points to this file |
| s2000 | 12 | msg 865 B | no identical file | nested byte-identical: `12.3` = `data/hdc_honda_s2000_ap1_010.wing`; `12.3[1]` = `data/hdc_honda_s2000_ap1_011.wing`; `12.3[2]` = `data/hdc_honda_s2000_ap1_012.wing`; 6 referenced file(s) not embedded as a sub-block: data/wing_body_aoa_cd.curve, data/wing_body_aoa_cl.curve, data/wing_front_aoa_cd.curve (+3) |
| s2000 | 23 | msg 201 B | `data/hdc_honda_s2000_ap1_01.gearbox` | path field 24 points to this file |
| s2000 | 25 | msg 2927 B | `data/hdc_honda_s2000_ap1_01.clutch` | path field 26 points to this file |
| s2000 | 1, 6, 7, 8, 9, 18, 17 | msg, 7 fields | no identical file | message fields with no `content\cars\...` string and no leaf-identical file; sizes: 1 (120 B), 6 (2 B), 7 (136 B), 8 (25 B), 9 (29 B), 18 (36 B), 17 (31 B) |
| s2000 | 10,11,16,19,20,21,22,24,26,27,29,202,190 (strings) | 13 fields | no identical file (strings) | 10 -> `data/tyres/hdc_205_55_16_front.tyre`; 11 -> `data/tyres/hdc_225_50_16_rear.tyre`; 16 -> `data/setup/hdc_honda_s2000_ap1_01.carsetuplimits`; 19 -> `data/setup/hdc_honda_s2000_ap1_01.carsetup`; 20 -> `data/hdc_honda_s2000_ap1_01.carengine` (inline 4 identical); 21 -> `collider/honda_s2000_ap1_collider.mesh`; 22 -> `data/hdc_honda_s2000_ap1_01.drivetrain` (inline 3 identical); 24 -> `data/hdc_honda_s2000_ap1_01.gearbox` (inline 23 identical); 26 -> `data/hdc_honda_s2000_ap1_01.clutch` (inline 25 identical); 27 -> `data/hdc_honda_s2000_ap1_01.brakesystem` (inline 5 identical); 29 -> `data/hdc_honda_s2000_ap1_01.aicardata`; 202: string `Hina's Drift Club - Honda S2000 AP1`; 190 -> `data/setup/hdc_honda_s2000_ap1_01.carsetup` |

## 2. What Hina changed for drifting

Pairing rule: a pair is made only from obviously sibling names (same stem plus a suffix such as `_drift`, `_tuned`, `_20v`, `_open`, `_spool`, `_35`, `_sadev`, `_l28`, `_5speed`); the few pairs made by which file an engine or tuningpart points to say so in the `basis` column (A = default/normal sibling, B = variant). Per car: a pair table (`ref by` = other files of the same package whose bytes contain the `content\cars\<id>\...` path of that file, case-insensitive; [verified]), then a leaf-diff table with the 6 columns `file A | file B | path | value A | value B | label`, then a curve summary. Leaf-diff rows are in file order (A's leaves, then leaves only in B); a pair with more than 10 differing leaves shows only its first 8 (setup/limits files with more than 8: first 4); the full count is in the pair table. Curve summaries use x = field 1 and y = field 10 of every repeated field-1 point (a point without field 1 or 10 is read as 0 [inferred: proto default]), %.6g; y is torque Nm only for `header_power*` / `*engine_power*` curves [inferred], for other curves the meaning of y is [unknown]; `B/A` = y_B / y_A at x values present in both curves (A y = 0 skipped).

Curve files named by each engine variant (carengine string leaves, [verified]):

| car | carengine | curve strings inside (field: file) |
|---|---|---|
| s2000 | `data/hdc_honda_s2000_ap1_01.carengine` | 2: `HEADER_POWER.curve`; 3: `coast.curve`; 4.3: `throttle.curve`; 14: `throttle.curve` |
| s2000 | `data/hdc_honda_s2000_ap1_01_drift.carengine` | 2: `HEADER_POWER_drift.curve`; 3: `coast.curve`; 14: `throttle.curve` |
| ae86 | `data/ks_ae86_beginner_h_01.carengine` | 2: `HEADER_POWER.curve`; 3: `coast.curve`; 14: `throttle.curve` |
| ae86 | `data/parts/ks_ae86_beginner_h_01_20v.carengine` | 2: `parts/HEADER_POWER_20v.curve`; 3: `parts/coast_20v.curve`; 4.3: `parts/throttle_20v.curve`; 14: `parts/throttle_20v.curve` |
| ae86 | `data/parts/ks_ae86_beginner_h_01_tuned.carengine` | 2: `na_character_v1/power_na_friendly.curve`; 3: `na_character_v1/coast_second_compensated.curve`; 14: `na_character_v1/throttle_linear.curve` |
| datsun | `data/hdc_datsun_240z_01.carengine` | 2: `HEADER_POWER.curve`; 3: `hdc_datsun_240z_01_coast1.curve`; 4.3: `throttle.curve`; 14: `throttle.curve` |
| datsun | `data/tuning/hdc_datsun_240z_01_l28engine.carengine` | 2: `hdc13/l28_power.curve`; 3: `hdc13/l28_coast.curve`; 4.3: `hdc13/l28_throttle.curve`; 14: `hdc13/l28_throttle.curve` |
| rx7 | `data/engine/rx7_engine.carengine` | 2: `engine/HEADER_POWER.curve`; 3: `engine/coast.curve`; 4.3: `engine/throttle.curve`; 25.2.3: `engine/ctrl_turbo0_controller0.curve`; 29: `engine/rx7_turbo0.turbo`; 29[1]: `engine/rx7_turbo1.turbo` |
| rx7 | `data/parts/hdc_rx7_fd_01_tuned.carengine` | 2: `parts/HEADER_POWER_tuned.curve`; 3: `parts/coast_tuned.curve`; 4.3: `parts/throttle_tuned.curve`; 14: `engine/throttle.curve`; 25.2.3: `parts/ctrl_turbo0_controller0_tuned.curve`; 29: `parts/rx7_turbo_tuned_0.turbo`; 29[1]: `parts/rx7_turbo_tuned_1.turbo`; 29[2]: `parts/rx7_turbo_tuned_2.turbo` |

### 2a. s2000 (hdc_honda_s2000_ap1_01)

S2000 has the `_drift` engine, drivetrain, front suspension and power curve next to the normal files; it has no `_drift` rear suspension.

| # | file A | file B | basis | A ref by | B ref by | byte-identical | differing leaf paths (A/B leaves) | rows shown |
|---|---|---|---|---|---|---|---|---|
| 1 | `data/hdc_honda_s2000_ap1_01.carengine` | `data/hdc_honda_s2000_ap1_01_drift.carengine` | suffix | data/cardata.car, data/hdc_honda_s2000_ap1_01.clutch | none | no | 16 (23/11) | 16 |
| 2 | `data/hdc_honda_s2000_ap1_01.drivetrain` | `data/hdc_honda_s2000_ap1_01_drift.drivetrain` | suffix | data/cardata.car, data/hdc_honda_s2000_ap1_01.clutch | none | no | 4 (53/51) | 4 |
| 3 | `data/hdc_honda_s2000_ap1_01_front.suspension` | `data/hdc_honda_s2000_ap1_01_front_drift.suspension` | suffix | data/cardata.car | none | no | 7 (30/30) | 7 |
| 4 | `data/header_power.curve` | `data/header_power_drift.curve` | suffix | data/cardata.car, data/hdc_honda_s2000_ap1_01.carengine, data/hdc_honda_s2000_ap1_01.clutch | data/hdc_honda_s2000_ap1_01_drift.carengine | no | 131 (170/79) | curve summary |

| file A | file B | path | value A | value B | label |
|---|---|---|---|---|---|
| `data/hdc_honda_s2000_ap1_01.carengine` | `data/hdc_honda_s2000_ap1_01_drift.carengine` | `1` | `(f32) 0.137999997` | `(f32) 0.104999997` | [unknown] |
| `data/hdc_honda_s2000_ap1_01.carengine` | `data/hdc_honda_s2000_ap1_01_drift.carengine` | `2` | `"content\cars\hdc_honda_s2000_ap1_01\data\HEADER_POWER.curve"` | `"content\cars\hdc_honda_s2000_ap1_01\data\HEADER_POWER_drift.curve"` | [inferred] power curve path |
| `data/hdc_honda_s2000_ap1_01.carengine` | `data/hdc_honda_s2000_ap1_01_drift.carengine` | `4.1` | `(f32) 1` | (absent) | [unknown] |
| `data/hdc_honda_s2000_ap1_01.carengine` | `data/hdc_honda_s2000_ap1_01_drift.carengine` | `4.2` | `(f32) 1` | (absent) | [unknown] |
| `data/hdc_honda_s2000_ap1_01.carengine` | `data/hdc_honda_s2000_ap1_01_drift.carengine` | `4.3` | `"content\cars\hdc_honda_s2000_ap1_01\data\throttle.curve"` | (absent) | [verified] path string; meaning of field [unknown] |
| `data/hdc_honda_s2000_ap1_01.carengine` | `data/hdc_honda_s2000_ap1_01_drift.carengine` | `4.6` | `(f32) 0.930000007` | (absent) | [unknown] |
| `data/hdc_honda_s2000_ap1_01.carengine` | `data/hdc_honda_s2000_ap1_01_drift.carengine` | `4.7` | `(f32) 0.949999988` | (absent) | [unknown] |
| `data/hdc_honda_s2000_ap1_01.carengine` | `data/hdc_honda_s2000_ap1_01_drift.carengine` | `4.9` | `1` | (absent) | [unknown] |
| `data/hdc_honda_s2000_ap1_01.carengine` | `data/hdc_honda_s2000_ap1_01_drift.carengine` | `4.10` | `(f32) 0.200000003` | (absent) | [unknown] |
| `data/hdc_honda_s2000_ap1_01.carengine` | `data/hdc_honda_s2000_ap1_01_drift.carengine` | `4.5` | `(f32) 2000` | (absent) | [unknown] |
| `data/hdc_honda_s2000_ap1_01.carengine` | `data/hdc_honda_s2000_ap1_01_drift.carengine` | `5` | `500` | `780` | [inferred] idle rpm |
| `data/hdc_honda_s2000_ap1_01.carengine` | `data/hdc_honda_s2000_ap1_01_drift.carengine` | `7` | `10` | `50` | [unknown] |
| `data/hdc_honda_s2000_ap1_01.carengine` | `data/hdc_honda_s2000_ap1_01_drift.carengine` | `20` | `(f32) 30` | (absent) | [unknown] |
| `data/hdc_honda_s2000_ap1_01.carengine` | `data/hdc_honda_s2000_ap1_01_drift.carengine` | `40` | `(f32) 0.970000029` | (absent) | [unknown] |
| `data/hdc_honda_s2000_ap1_01.carengine` | `data/hdc_honda_s2000_ap1_01_drift.carengine` | `41` | `(f32) 0.949999988` | (absent) | [unknown] |
| `data/hdc_honda_s2000_ap1_01.carengine` | `data/hdc_honda_s2000_ap1_01_drift.carengine` | `50` | `""` | (absent) | [unknown] |
| `data/hdc_honda_s2000_ap1_01.drivetrain` | `data/hdc_honda_s2000_ap1_01_drift.drivetrain` | `39.1` | `(f32) 0.819999993` | (absent) | [inferred] diff power lock |
| `data/hdc_honda_s2000_ap1_01.drivetrain` | `data/hdc_honda_s2000_ap1_01_drift.drivetrain` | `39.2` | `(f32) 0.680000007` | (absent) | [inferred] diff coast lock |
| `data/hdc_honda_s2000_ap1_01.drivetrain` | `data/hdc_honda_s2000_ap1_01_drift.drivetrain` | `39.12` | `(f32) 3` | `(f32) 2` | [unknown] |
| `data/hdc_honda_s2000_ap1_01.drivetrain` | `data/hdc_honda_s2000_ap1_01_drift.drivetrain` | `39.4` | `0` | `1` | [unknown] |
| `data/hdc_honda_s2000_ap1_01_front.suspension` | `data/hdc_honda_s2000_ap1_01_front_drift.suspension` | `1.2` | `(f32) 1.47000003` | `(f32) 1.76999998` | [unknown] |
| `data/hdc_honda_s2000_ap1_01_front.suspension` | `data/hdc_honda_s2000_ap1_01_front_drift.suspension` | `2.1.2` | `(f32) 0.123109996` | `(f32) 0.0831099972` | [unknown] |
| `data/hdc_honda_s2000_ap1_01_front.suspension` | `data/hdc_honda_s2000_ap1_01_front_drift.suspension` | `2.2.2` | `(f32) 0.124509998` | `(f32) 0.0845099986` | [unknown] |
| `data/hdc_honda_s2000_ap1_01_front.suspension` | `data/hdc_honda_s2000_ap1_01_front_drift.suspension` | `2.5.1` | `(f32) 0.124789998` | `(f32) 0.11479` | [unknown] |
| `data/hdc_honda_s2000_ap1_01_front.suspension` | `data/hdc_honda_s2000_ap1_01_front_drift.suspension` | `2.6.1` | `(f32) 0.0904999971` | `(f32) 0.0804999992` | [unknown] |
| `data/hdc_honda_s2000_ap1_01_front.suspension` | `data/hdc_honda_s2000_ap1_01_front_drift.suspension` | `2.6.2` | `(f32) -0.135020003` | `(f32) -0.105020002` | [unknown] |
| `data/hdc_honda_s2000_ap1_01_front.suspension` | `data/hdc_honda_s2000_ap1_01_front_drift.suspension` | `2.7.2` | `(f32) -0.0199999996` | `(f32) -0.0500000007` | [unknown] |

| # | curve A | curve B | points A/B | x range A | x range B | y range A | y range B | peak y @ x (A) | peak y @ x (B) | shared x | B/A min..max |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | `data/header_power.curve` | `data/header_power_drift.curve` | 43/20 | 0..9500 | 0..9500 | 0..303.106 | 150..330 | 303.106 @ 6200 | 330 @ 6500 | 11 | 1.06108..1.90527 |

Torque ratio drift/normal at each shared rpm, pair #4 (`data/header_power_drift.curve` / `data/header_power.curve`, y = field 10 read as Nm [inferred]; rpm 0 skipped because normal y = 0):

| rpm | normal y | drift y | drift/normal |
|---|---|---|---|
| 1000 | 110.22 | 210 | 1.90527 |
| 2000 | 206.663 | 254 | 1.22905 |
| 3000 | 243.863 | 293 | 1.2015 |
| 4000 | 250.752 | 306 | 1.22033 |
| 5000 | 264.529 | 299 | 1.13031 |
| 6000 | 293.462 | 323 | 1.10065 |
| 7000 | 294.84 | 326 | 1.10569 |
| 8000 | 289.329 | 307 | 1.06108 |
| 9000 | 228.707 | 259 | 1.13245 |
| 9500 | 179.108 | 230 | 1.28414 |

### 2b. ae86 (ks_ae86_beginner_h_01)

AE86 alternatives sit in `data/parts/`. Engines: stock = `data/ks_ae86_beginner_h_01.carengine`, `_20v`, `_tuned`; drivetrains: `data/ks_ae86_beginner_h_01.drivetrain` (default, the part `ae86_diff_lsd` points to it), `_open`, `_spool`; clutch and gearbox: default, `_35`, `_sadev`; setups: `toyota_ae86` and `toyota_ae86_tuned`.

| # | file A | file B | basis | A ref by | B ref by | byte-identical | differing leaf paths (A/B leaves) | rows shown |
|---|---|---|---|---|---|---|---|---|
| 1 | `data/ks_ae86_beginner_h_01.carengine` | `data/parts/ks_ae86_beginner_h_01_20v.carengine` | suffix | data/parts/ae86_16engine_stock.tuningpart | data/parts/ae86_16engine_20v_blacktop.tuningpart | no | 14 (12/19) | 8 |
| 2 | `data/ks_ae86_beginner_h_01.carengine` | `data/parts/ks_ae86_beginner_h_01_tuned.carengine` | suffix | data/parts/ae86_16engine_stock.tuningpart | data/cardata.car, data/parts/ae86_16engine_16v_tuned.tuningpart | no | 11 (12/15) | 8 |
| 3 | `data/ks_ae86_beginner_h_01.drivetrain` | `data/parts/ks_ae86_beginner_h_01_open.drivetrain` | suffix | data/cardata.car, data/parts/ae86_diff_lsd.tuningpart | none | no | 4 (21/21) | 4 |
| 4 | `data/ks_ae86_beginner_h_01.drivetrain` | `data/parts/ks_ae86_beginner_h_01_spool.drivetrain` | suffix | data/cardata.car, data/parts/ae86_diff_lsd.tuningpart | data/parts/ae86_diff_spool.tuningpart | no | 4 (21/21) | 4 |
| 5 | `data/ks_ae86_beginner_h_01.clutch` | `data/parts/ks_ae86_beginner_h_01_35.clutch` | suffix | data/cardata.car, data/parts/ae86_clutch_stock.tuningpart | data/parts/ae86_clutch_35.tuningpart | no | 5 (8/7) | 5 |
| 6 | `data/ks_ae86_beginner_h_01.clutch` | `data/parts/ks_ae86_beginner_h_01_sadev.clutch` | suffix | data/cardata.car, data/parts/ae86_clutch_stock.tuningpart | data/parts/ae86_clutch_sadev.tuningpart | no | 6 (8/7) | 6 |
| 7 | `data/ks_ae86_beginner_h_01.gearbox` | `data/parts/ks_ae86_beginner_h_01_35.gearbox` | suffix | data/cardata.car, data/parts/ae86_gear_stock.tuningpart | data/parts/ae86_gear_35.tuningpart | no | 14 (32/27) | 8 |
| 8 | `data/ks_ae86_beginner_h_01.gearbox` | `data/parts/ks_ae86_beginner_h_01_sadev.gearbox` | suffix | data/cardata.car, data/parts/ae86_gear_stock.tuningpart | data/parts/ae86_gear_sadev.tuningpart | no | 21 (32/29) | 8 |
| 9 | `data/header_power.curve` | `data/parts/header_power_20v.curve` | suffix | data/ks_ae86_beginner_h_01.carengine | data/parts/ks_ae86_beginner_h_01_20v.carengine | no | 64 (82/107) | curve summary |
| 10 | `data/header_power.curve` | `data/parts/header_power_tuned.curve` | suffix | data/ks_ae86_beginner_h_01.carengine | none | no | 61 (82/103) | curve summary |
| 11 | `data/coast.curve` | `data/parts/coast_20v.curve` | suffix | data/ks_ae86_beginner_h_01.carengine | data/parts/ks_ae86_beginner_h_01_20v.carengine | no | 45 (51/25) | curve summary |
| 12 | `data/coast.curve` | `data/parts/coast_tuned.curve` | suffix | data/ks_ae86_beginner_h_01.carengine | none | yes | 0 (51/51) | 0 |
| 13 | `data/throttle.curve` | `data/parts/throttle_20v.curve` | suffix | data/ks_ae86_beginner_h_01.carengine | data/parts/ks_ae86_beginner_h_01_20v.carengine | no | 31 (21/42) | curve summary |
| 14 | `data/throttle.curve` | `data/parts/throttle_tuned.curve` | suffix | data/ks_ae86_beginner_h_01.carengine | none | no | 31 (21/42) | curve summary |
| 15 | `data/autoblipprofile.curve` | `data/parts/autoblipprofile_35.curve` | suffix | data/cardata.car, data/ks_ae86_beginner_h_01.gearbox | data/parts/ks_ae86_beginner_h_01_35.gearbox | no | 1 (13/13) | curve summary |
| 16 | `data/autoblipprofile.curve` | `data/parts/autoblipprofile_sadev.curve` | suffix | data/cardata.car, data/ks_ae86_beginner_h_01.gearbox | data/parts/ks_ae86_beginner_h_01_sadev.gearbox | no | 5 (13/13) | curve summary |
| 17 | `data/downshiftprofile.curve` | `data/parts/downshiftprofile_sadev.curve` | suffix | data/cardata.car, data/ks_ae86_beginner_h_01.clutch, data/parts/ks_ae86_beginner_h_01_35.clutch | data/parts/ks_ae86_beginner_h_01_sadev.clutch | no | 2 (13/13) | curve summary |
| 18 | `data/upshiftprofile.curve` | `data/parts/upshiftprofile_35.curve` | suffix | data/cardata.car, data/ks_ae86_beginner_h_01.clutch | data/parts/ks_ae86_beginner_h_01_35.clutch | no | 1 (13/13) | curve summary |
| 19 | `data/upshiftprofile.curve` | `data/parts/upshiftprofile_sadev.curve` | suffix | data/cardata.car, data/ks_ae86_beginner_h_01.clutch | data/parts/ks_ae86_beginner_h_01_sadev.clutch | no | 2 (13/13) | curve summary |
| 20 | `data/header_power.curve` | `data/na_character_v1/power_na_friendly.curve` | engine pointer | data/ks_ae86_beginner_h_01.carengine | data/cardata.car, data/parts/ks_ae86_beginner_h_01_tuned.carengine | no | 32 (82/84) | curve summary |
| 21 | `data/coast.curve` | `data/na_character_v1/coast_second_compensated.curve` | engine pointer | data/ks_ae86_beginner_h_01.carengine | data/cardata.car, data/parts/ks_ae86_beginner_h_01_tuned.carengine | no | 46 (51/72) | curve summary |
| 22 | `data/throttle.curve` | `data/na_character_v1/throttle_linear.curve` | engine pointer | data/ks_ae86_beginner_h_01.carengine | data/cardata.car, data/parts/ks_ae86_beginner_h_01_tuned.carengine | no | 8 (21/21) | curve summary |
| 23 | `data/setup/toyota_ae86.carsetup` | `data/setup/toyota_ae86_tuned.carsetup` | suffix | none | data/cardata.car, data/parts/ae86_suspension_tune.tuningpart | no | 52 (71/65) | 4 |
| 24 | `data/setup/toyota_ae86.carsetuplimits` | `data/setup/toyota_ae86_tuned.carsetuplimits` | suffix | none | data/cardata.car | no | 154 (245/285) | 4 |

| file A | file B | path | value A | value B | label |
|---|---|---|---|---|---|
| `data/ks_ae86_beginner_h_01.carengine` | `data/parts/ks_ae86_beginner_h_01_20v.carengine` | `1` | `(f32) 0.129999995` | `(f32) 0.0900000036` | [unknown] |
| `data/ks_ae86_beginner_h_01.carengine` | `data/parts/ks_ae86_beginner_h_01_20v.carengine` | `2` | `"content\cars\ks_ae86_beginner_h_01\data\HEADER_POWER.curve"` | `"content\cars\ks_ae86_beginner_h_01\data\parts\HEADER_POWER_20v.curve"` | [inferred] power curve path |
| `data/ks_ae86_beginner_h_01.carengine` | `data/parts/ks_ae86_beginner_h_01_20v.carengine` | `3` | `"content\cars\ks_ae86_beginner_h_01\data\coast.curve"` | `"content\cars\ks_ae86_beginner_h_01\data\parts\coast_20v.curve"` | [inferred] coast curve path |
| `data/ks_ae86_beginner_h_01.carengine` | `data/parts/ks_ae86_beginner_h_01_20v.carengine` | `5` | `500` | `1000` | [inferred] idle rpm |
| `data/ks_ae86_beginner_h_01.carengine` | `data/parts/ks_ae86_beginner_h_01_20v.carengine` | `6` | `7250` | `11000` | [inferred] limiter rpm |
| `data/ks_ae86_beginner_h_01.carengine` | `data/parts/ks_ae86_beginner_h_01_20v.carengine` | `7` | `16` | `30` | [unknown] |
| `data/ks_ae86_beginner_h_01.carengine` | `data/parts/ks_ae86_beginner_h_01_20v.carengine` | `14` | `"content\cars\ks_ae86_beginner_h_01\data\throttle.curve"` | `"content\cars\ks_ae86_beginner_h_01\data\parts\throttle_20v.curve"` | [verified] path string; meaning of field [unknown] |
| `data/ks_ae86_beginner_h_01.carengine` | `data/parts/ks_ae86_beginner_h_01_20v.carengine` | `4.1` | (absent) | `(f32) 1` | [unknown] |
| `data/ks_ae86_beginner_h_01.carengine` | `data/parts/ks_ae86_beginner_h_01_tuned.carengine` | `1` | `(f32) 0.129999995` | `(f32) 0.114869729` | [unknown] |
| `data/ks_ae86_beginner_h_01.carengine` | `data/parts/ks_ae86_beginner_h_01_tuned.carengine` | `2` | `"content\cars\ks_ae86_beginner_h_01\data\HEADER_POWER.curve"` | `"content\cars\ks_ae86_beginner_h_01\data\na_character_v1\power_na_friendly.curve"` | [inferred] power curve path |
| `data/ks_ae86_beginner_h_01.carengine` | `data/parts/ks_ae86_beginner_h_01_tuned.carengine` | `3` | `"content\cars\ks_ae86_beginner_h_01\data\coast.curve"` | `"content\cars\ks_ae86_beginner_h_01\data\na_character_v1\coast_second_compensated.curve"` | [inferred] coast curve path |
| `data/ks_ae86_beginner_h_01.carengine` | `data/parts/ks_ae86_beginner_h_01_tuned.carengine` | `5` | `500` | `1000` | [inferred] idle rpm |
| `data/ks_ae86_beginner_h_01.carengine` | `data/parts/ks_ae86_beginner_h_01_tuned.carengine` | `6` | `7250` | `9000` | [inferred] limiter rpm |
| `data/ks_ae86_beginner_h_01.carengine` | `data/parts/ks_ae86_beginner_h_01_tuned.carengine` | `7` | `16` | `18` | [unknown] |
| `data/ks_ae86_beginner_h_01.carengine` | `data/parts/ks_ae86_beginner_h_01_tuned.carengine` | `14` | `"content\cars\ks_ae86_beginner_h_01\data\throttle.curve"` | `"content\cars\ks_ae86_beginner_h_01\data\na_character_v1\throttle_linear.curve"` | [verified] path string; meaning of field [unknown] |
| `data/ks_ae86_beginner_h_01.carengine` | `data/parts/ks_ae86_beginner_h_01_tuned.carengine` | `15` | `(f32) 7500` | `(f32) 9250` | [unknown] |
| `data/ks_ae86_beginner_h_01.drivetrain` | `data/parts/ks_ae86_beginner_h_01_open.drivetrain` | `39.1` | `(f32) 0.850000024` | `(f32) 0.25` | [inferred] diff power lock |
| `data/ks_ae86_beginner_h_01.drivetrain` | `data/parts/ks_ae86_beginner_h_01_open.drivetrain` | `39.2` | `(f32) 0.699999988` | `(f32) 0.25` | [inferred] diff coast lock |
| `data/ks_ae86_beginner_h_01.drivetrain` | `data/parts/ks_ae86_beginner_h_01_open.drivetrain` | `39.3` | `(f32) 10` | `(f32) 5` | [inferred] diff preload Nm |
| `data/ks_ae86_beginner_h_01.drivetrain` | `data/parts/ks_ae86_beginner_h_01_open.drivetrain` | `39.4` | `0` | `1` | [unknown] |
| `data/ks_ae86_beginner_h_01.drivetrain` | `data/parts/ks_ae86_beginner_h_01_spool.drivetrain` | `39.1` | `(f32) 0.850000024` | `(f32) 0.25` | [inferred] diff power lock |
| `data/ks_ae86_beginner_h_01.drivetrain` | `data/parts/ks_ae86_beginner_h_01_spool.drivetrain` | `39.2` | `(f32) 0.699999988` | `(f32) 0.25` | [inferred] diff coast lock |
| `data/ks_ae86_beginner_h_01.drivetrain` | `data/parts/ks_ae86_beginner_h_01_spool.drivetrain` | `39.3` | `(f32) 10` | `(f32) 5` | [inferred] diff preload Nm |
| `data/ks_ae86_beginner_h_01.drivetrain` | `data/parts/ks_ae86_beginner_h_01_spool.drivetrain` | `39.4` | `0` | `1` | [unknown] |
| `data/ks_ae86_beginner_h_01.clutch` | `data/parts/ks_ae86_beginner_h_01_35.clutch` | `2` | `(f32) 600` | `(f32) 300` | [unknown] |
| `data/ks_ae86_beginner_h_01.clutch` | `data/parts/ks_ae86_beginner_h_01_35.clutch` | `3.1` | `"content\cars\ks_ae86_beginner_h_01\data\upShiftProfile.curve"` | `"content\cars\ks_ae86_beginner_h_01\data\parts\upShiftProfile_35.curve"` | [verified] path string; meaning of field [unknown] |
| `data/ks_ae86_beginner_h_01.clutch` | `data/parts/ks_ae86_beginner_h_01_35.clutch` | `3.4` | `(f32) 1300` | `(f32) 1200` | [unknown] |
| `data/ks_ae86_beginner_h_01.clutch` | `data/parts/ks_ae86_beginner_h_01_35.clutch` | `3.6` | `0` | `1` | [unknown] |
| `data/ks_ae86_beginner_h_01.clutch` | `data/parts/ks_ae86_beginner_h_01_35.clutch` | `3.3` | `0` | (absent) | [unknown] |
| `data/ks_ae86_beginner_h_01.clutch` | `data/parts/ks_ae86_beginner_h_01_sadev.clutch` | `2` | `(f32) 600` | `(f32) 300` | [unknown] |
| `data/ks_ae86_beginner_h_01.clutch` | `data/parts/ks_ae86_beginner_h_01_sadev.clutch` | `3.1` | `"content\cars\ks_ae86_beginner_h_01\data\upShiftProfile.curve"` | `"content\cars\ks_ae86_beginner_h_01\data\parts\upShiftProfile_sadev.curve"` | [verified] path string; meaning of field [unknown] |
| `data/ks_ae86_beginner_h_01.clutch` | `data/parts/ks_ae86_beginner_h_01_sadev.clutch` | `3.2` | `"content\cars\ks_ae86_beginner_h_01\data\downShiftProfile.curve"` | `"content\cars\ks_ae86_beginner_h_01\data\parts\downShiftProfile_sadev.curve"` | [verified] path string; meaning of field [unknown] |
| `data/ks_ae86_beginner_h_01.clutch` | `data/parts/ks_ae86_beginner_h_01_sadev.clutch` | `3.4` | `(f32) 1300` | `(f32) 1200` | [unknown] |
| `data/ks_ae86_beginner_h_01.clutch` | `data/parts/ks_ae86_beginner_h_01_sadev.clutch` | `3.6` | `0` | `1` | [unknown] |
| `data/ks_ae86_beginner_h_01.clutch` | `data/parts/ks_ae86_beginner_h_01_sadev.clutch` | `3.3` | `0` | (absent) | [unknown] |
| `data/ks_ae86_beginner_h_01.gearbox` | `data/parts/ks_ae86_beginner_h_01_35.gearbox` | `3` | `(f32) 4` | `(f32) 4.30000019` | [inferred] final drive ratio |
| `data/ks_ae86_beginner_h_01.gearbox` | `data/parts/ks_ae86_beginner_h_01_35.gearbox` | `12.1` | `"content\cars\ks_ae86_beginner_h_01\data\autoBlipProfile.curve"` | `"content\cars\ks_ae86_beginner_h_01\data\parts\autoBlipProfile_35.curve"` | [verified] path string; meaning of field [unknown] |
| `data/ks_ae86_beginner_h_01.gearbox` | `data/parts/ks_ae86_beginner_h_01_35.gearbox` | `12.2` | `0` | (absent) | [unknown] |
| `data/ks_ae86_beginner_h_01.gearbox` | `data/parts/ks_ae86_beginner_h_01_35.gearbox` | `13.1` | `8300` | `7200` | [unknown] |
| `data/ks_ae86_beginner_h_01.gearbox` | `data/parts/ks_ae86_beginner_h_01_35.gearbox` | `13.5` | `4200` | (absent) | [unknown] |
| `data/ks_ae86_beginner_h_01.gearbox` | `data/parts/ks_ae86_beginner_h_01_35.gearbox` | `20` | `(f32) 100` | (absent) | [unknown] |
| `data/ks_ae86_beginner_h_01.gearbox` | `data/parts/ks_ae86_beginner_h_01_35.gearbox` | `18` | `(f32) 1` | (absent) | [unknown] |
| `data/ks_ae86_beginner_h_01.gearbox` | `data/parts/ks_ae86_beginner_h_01_35.gearbox` | `19` | `0` | (absent) | [unknown] |
| `data/ks_ae86_beginner_h_01.gearbox` | `data/parts/ks_ae86_beginner_h_01_sadev.gearbox` | `1` | `5` | `6` | [inferred] gear count |
| `data/ks_ae86_beginner_h_01.gearbox` | `data/parts/ks_ae86_beginner_h_01_sadev.gearbox` | `3` | `(f32) 4` | `(f32) 5.85699987` | [inferred] final drive ratio |
| `data/ks_ae86_beginner_h_01.gearbox` | `data/parts/ks_ae86_beginner_h_01_sadev.gearbox` | `4` | `(f32) 260` | `(f32) 80` | [unknown] |
| `data/ks_ae86_beginner_h_01.gearbox` | `data/parts/ks_ae86_beginner_h_01_sadev.gearbox` | `5` | `(f32) 270` | `(f32) 170` | [unknown] |
| `data/ks_ae86_beginner_h_01.gearbox` | `data/parts/ks_ae86_beginner_h_01_sadev.gearbox` | `11` | `(f32) 0.0182000007` | `(f32) 0.0164000001` | [unknown] |
| `data/ks_ae86_beginner_h_01.gearbox` | `data/parts/ks_ae86_beginner_h_01_sadev.gearbox` | `12.1` | `"content\cars\ks_ae86_beginner_h_01\data\autoBlipProfile.curve"` | `"content\cars\ks_ae86_beginner_h_01\data\parts\autoBlipProfile_sadev.curve"` | [verified] path string; meaning of field [unknown] |
| `data/ks_ae86_beginner_h_01.gearbox` | `data/parts/ks_ae86_beginner_h_01_sadev.gearbox` | `12.2` | `0` | (absent) | [unknown] |
| `data/ks_ae86_beginner_h_01.gearbox` | `data/parts/ks_ae86_beginner_h_01_sadev.gearbox` | `13.1` | `8300` | `10800` | [unknown] |
| `data/setup/toyota_ae86.carsetup` | `data/setup/toyota_ae86_tuned.carsetup` | `1.1` | `<8 bytes>` | `<8 bytes>` | [unknown]; printed text equal, raw bytes differ: A=0x0050c34600401c46 B=0x00c0da4600004845 |
| `data/setup/toyota_ae86.carsetup` | `data/setup/toyota_ae86_tuned.carsetup` | `1.2` | `(f32) -18.6000004` | `(f32) -14` | [inferred] steer ratio |
| `data/setup/toyota_ae86.carsetup` | `data/setup/toyota_ae86_tuned.carsetup` | `1.4.2` | `(f32) 0.75` | `(f32) 0.699999988` | [inferred] diff coast lock |
| `data/setup/toyota_ae86.carsetup` | `data/setup/toyota_ae86_tuned.carsetup` | `2.1` | `(f32) 28000` | `(f32) 40000` | [unknown] |
| `data/setup/toyota_ae86.carsetuplimits` | `data/setup/toyota_ae86_tuned.carsetuplimits` | `1.1.1` | `(f32) 800` | `(f32) 2800` | [unknown] |
| `data/setup/toyota_ae86.carsetuplimits` | `data/setup/toyota_ae86_tuned.carsetuplimits` | `1.1.2` | `(f32) 8000` | `(f32) 22400` | [unknown] |
| `data/setup/toyota_ae86.carsetuplimits` | `data/setup/toyota_ae86_tuned.carsetuplimits` | `1.1.3` | `(f32) 80000` | `(f32) 33600` | [unknown] |
| `data/setup/toyota_ae86.carsetuplimits` | `data/setup/toyota_ae86_tuned.carsetuplimits` | `1.1[1].1` | `(f32) 600` | `(f32) 320` | [unknown] |

| # | curve A | curve B | points A/B | x range A | x range B | y range A | y range B | peak y @ x (A) | peak y @ x (B) | shared x | B/A min..max |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 9 | `data/header_power.curve` | `data/parts/header_power_20v.curve` | 21/27 | 0..9000 | 0..12000 | 0..138 | 40..182 | 138 @ 5200 | 182 @ 8947 | 1 | 0.5..0.5 |
| 10 | `data/header_power.curve` | `data/parts/header_power_tuned.curve` | 21/26 | 0..9000 | 0..10000 | 0..138 | 10..183 | 138 @ 5200 | 183 @ 6224 | 1 | 0.1..0.1 |
| 11 | `data/coast.curve` | `data/parts/coast_20v.curve` | 13/6 | 0..7000 | 0..12000 | -50..10 | -95..14 | 10 @ 500 | 14 @ 0 | 2 | 2.02588..2.8 |
| 12 | `data/coast.curve` | `data/parts/coast_tuned.curve` | - | - | - | - | - | - | - | - | byte-identical |
| 13 | `data/throttle.curve` | `data/parts/throttle_20v.curve` | 11/11 | 0..100 | 0..100 | 0..100 | 0..100 | 100 @ 100 | 100 @ 100 | 11 | 0.233333..1 |
| 14 | `data/throttle.curve` | `data/parts/throttle_tuned.curve` | 11/11 | 0..100 | 0..100 | 0..100 | 0..100 | 100 @ 100 | 100 @ 100 | 11 | 0.333333..1 |
| 15 | `data/autoblipprofile.curve` | `data/parts/autoblipprofile_35.curve` | 4/4 | 0..250 | 0..250 | 0..0.7 | 0..0.8 | 0.7 @ 10 | 0.8 @ 10 | 4 | 1..1.14286 |
| 16 | `data/autoblipprofile.curve` | `data/parts/autoblipprofile_sadev.curve` | 4/4 | 0..250 | 0..160 | 0..0.7 | 0..0.5 | 0.7 @ 10 | 0.5 @ 20 | 1 | - |
| 17 | `data/downshiftprofile.curve` | `data/parts/downshiftprofile_sadev.curve` | 4/4 | 0..0.5 | 0..0.37 | 0..1 | 0..1 | 1 @ 0 | 1 @ 0 | 2 | 1..1 |
| 18 | `data/upshiftprofile.curve` | `data/parts/upshiftprofile_35.curve` | 4/4 | 0..0.45 | 0..0.35 | 0..1 | 0..1 | 1 @ 0 | 1 @ 0 | 3 | 1..1 |
| 19 | `data/upshiftprofile.curve` | `data/parts/upshiftprofile_sadev.curve` | 4/4 | 0..0.45 | 0..0.2 | 0..1 | 0..1 | 1 @ 0 | 1 @ 0 | 2 | 1..1 |
| 20 | `data/header_power.curve` | `data/na_character_v1/power_na_friendly.curve` | 21/21 | 0..9000 | 0..10000 | 0..138 | 10..215 | 138 @ 5200 | 215 @ 6500 | 19 | 0.1..1.93684 |
| 21 | `data/coast.curve` | `data/na_character_v1/coast_second_compensated.curve` | 13/18 | 0..7000 | 0..10004.9 | -50..10 | -62.2627..17.6134 | 10 @ 500 | 17.6134 @ 0 | 2 | 2.20167..2.54876 |
| 22 | `data/throttle.curve` | `data/na_character_v1/throttle_linear.curve` | 11/11 | 0..100 | 0..100 | 0..100 | 0..100 | 100 @ 100 | 100 @ 100 | 11 | 0.333333..1 |

Part-file chain, ae86 (paths are the string leaves inside the part files, [verified]; `field` = pbedit path of that string; mesh/sfx paths and carpart field 31 (other carparts) omitted).

| physics carpart | tuningpart(s) it points to (field) | data file(s) those tuningparts point to (field) |
|---|---|---|
| `ae86_16engine_16v_tuned.carpart` | `ae86_16engine_16v_tuned.tuningpart` (102.1) | `data/parts/ks_ae86_beginner_h_01_tuned.carengine` (2.1, in ae86_16engine_16v_tuned.tuningpart) |
| `ae86_16engine_20v_blacktop.carpart` | `ae86_16engine_20v_blacktop.tuningpart` (102.1) | `data/parts/ks_ae86_beginner_h_01_20v.carengine` (2.1, in ae86_16engine_20v_blacktop.tuningpart) |
| `ae86_16engine_stock.carpart` | `ae86_16engine_stock.tuningpart` (102.1) | `data/ks_ae86_beginner_h_01.carengine` (2.1, in ae86_16engine_stock.tuningpart) |
| `ae86_diff_lsd.carpart` | `ae86_diff_lsd.tuningpart` (102.1) | `data/ks_ae86_beginner_h_01.drivetrain` (4.1, in ae86_diff_lsd.tuningpart) |
| `ae86_diff_spool.carpart` | `ae86_diff_spool.tuningpart` (102.1) | `data/parts/ks_ae86_beginner_h_01_spool.drivetrain` (4.1, in ae86_diff_spool.tuningpart) |
| `ae86_gear_35.carpart` | `ae86_gear_35.tuningpart` (102.1); `ae86_clutch_35.tuningpart` (102[1].1) | `data/parts/ks_ae86_beginner_h_01_35.gearbox` (3.1, in ae86_gear_35.tuningpart); `data/parts/ks_ae86_beginner_h_01_35.clutch` (5.1, in ae86_clutch_35.tuningpart) |
| `ae86_gear_sadev.carpart` | `ae86_gear_sadev.tuningpart` (102.1); `ae86_clutch_sadev.tuningpart` (102[1].1) | `data/parts/ks_ae86_beginner_h_01_sadev.gearbox` (3.1, in ae86_gear_sadev.tuningpart); `data/parts/ks_ae86_beginner_h_01_sadev.clutch` (5.1, in ae86_clutch_sadev.tuningpart) |
| `ae86_gear_stock.carpart` | `ae86_gear_stock.tuningpart` (102.1); `ae86_clutch_stock.tuningpart` (102[1].1) | `data/ks_ae86_beginner_h_01.gearbox` (3.1, in ae86_gear_stock.tuningpart); `data/ks_ae86_beginner_h_01.clutch` (5.1, in ae86_clutch_stock.tuningpart) |
| `ae86_suspension_tune.carpart` | `ae86_suspension_tune.tuningpart` (102.1) | `data/setup/toyota_ae86_tuned.carsetup` (30.1, in ae86_suspension_tune.tuningpart) |

9 of 9 physics `.compatiblepart` files have field 1 = path of the same-named `.carpart` [verified].

### 2c. datsun (hdc_datsun_240z_01)

Datsun alternatives: `data/hdc_datsun_240z_01*` (4-speed, open drivetrain, original engine/clutch) against `data/tuning/hdc_datsun_240z_01_*` (LSD, L28 engine, 5-speed, 5-speed clutch, brakes, g_nose coilovers) and `data/setup/*_g_nose`; `data/aero` against `data/aero_dst`.

| # | file A | file B | basis | A ref by | B ref by | byte-identical | differing leaf paths (A/B leaves) | rows shown |
|---|---|---|---|---|---|---|---|---|
| 1 | `data/hdc_datsun_240z_01_open.drivetrain` | `data/tuning/hdc_datsun_240z_01_lsd.drivetrain` | suffix | none | data/cardata.car, data/tuning/hdc_datsun_240z_01_lsd.tuningpart | no | 7 (54/56) | 7 |
| 2 | `data/hdc_datsun_240z_01.carengine` | `data/tuning/hdc_datsun_240z_01_l28engine.carengine` | suffix | data/hdc_datsun_240z_01.clutch | data/cardata.car, data/tuning/hdc_datsun_240z_01_l28engine.tuningpart | no | 14 (20/20) | 8 |
| 3 | `data/hdc_datsun_240z_01_4speed.gearbox` | `data/tuning/hdc_datsun_240z_01_5speed.gearbox` | suffix | none | data/cardata.car, data/tuning/hdc_datsun_240z_01_5speed.tuningpart | no | 10 (27/28) | 10 |
| 4 | `data/hdc_datsun_240z_01.clutch` | `data/tuning/hdc_datsun_240z_01_clutch_5speed.clutch` | suffix | none | data/cardata.car, data/tuning/hdc_datsun_240z_01_clutch_5speed.tuningpart | no | 229 (230/7) | 8 |
| 5 | `data/hdc_datsun_240z_01.brakesystem` | `data/tuning/hdc_datsun_240z_01_brakes.brakesystem` | suffix | none | data/cardata.car, data/tuning/hdc_datsun_240z_01_brake.tuningpart | no | 2 (7/7) | 2 |
| 6 | `data/hdc_datsun_240z_01_front.coilover` | `data/tuning/hdc_datsun_240z_01_g_nose_front.coilover` | suffix | none | data/cardata.car, data/tuning/hdc_datsun_240z_01_g_nose_coilovers.tuningpart | no | 14 (22/22) | 8 |
| 7 | `data/hdc_datsun_240z_01_rear.coilover` | `data/tuning/hdc_datsun_240z_01_g_nose_rear.coilover` | suffix | none | data/cardata.car, data/tuning/hdc_datsun_240z_01_g_nose_coilovers.tuningpart | no | 14 (22/22) | 8 |
| 8 | `data/setup/hdc_datsun_240z_01.carsetup` | `data/setup/hdc_datsun_240z_01_g_nose.carsetup` | suffix | none | data/cardata.car, data/tuning/hdc_datsun_240z_01_g_nose_setup.tuningpart, data/tuning/hdc_datsun_240z_01_g_nose_setuplimits.tuningpart | no | 27 (75/71) | 4 |
| 9 | `data/setup/hdc_datsun_240z_01.carsetuplimits` | `data/setup/hdc_datsun_240z_01_g_nose.carsetuplimits` | suffix | none | data/cardata.car, data/tuning/hdc_datsun_240z_01_g_nose_setuplimits.tuningpart | no | 66 (381/381) | 4 |
| 10 | `data/header_power.curve` | `data/tuning/header_power_l28.curve` | suffix | data/hdc_datsun_240z_01.carengine, data/hdc_datsun_240z_01.clutch | none | no | 51 (99/95) | curve summary |
| 11 | `data/throttle.curve` | `data/tuning/throttle_l28.curve` | suffix | data/hdc_datsun_240z_01.carengine, data/hdc_datsun_240z_01.clutch | none | no | 38 (6/42) | curve summary |
| 12 | `data/coast.curve` | `data/tuning/coast_l28.curve` | suffix | data/hdc_datsun_240z_01.clutch | none | no | 57 (67/18) | curve summary |
| 13 | `data/header_power.curve` | `data/hdc13/l28_power.curve` | engine pointer | data/hdc_datsun_240z_01.carengine, data/hdc_datsun_240z_01.clutch | data/cardata.car, data/tuning/hdc_datsun_240z_01_l28engine.carengine | no | 68 (99/64) | curve summary |
| 14 | `data/hdc_datsun_240z_01_coast1.curve` | `data/hdc13/l28_coast.curve` | engine pointer | data/hdc_datsun_240z_01.carengine | data/cardata.car, data/tuning/hdc_datsun_240z_01_l28engine.carengine | no | 24 (23/36) | curve summary |
| 15 | `data/throttle.curve` | `data/hdc13/l28_throttle.curve` | engine pointer | data/hdc_datsun_240z_01.carengine, data/hdc_datsun_240z_01.clutch | data/cardata.car, data/tuning/hdc_datsun_240z_01_l28engine.carengine | no | 40 (6/44) | curve summary |
| 16 | `data/aero/ks_datsun_240z_front.wing` | `data/aero_dst/ks_datsun_240z_front.wing` | suffix | data/cardata.car | none | yes | 0 (11/11) | 0 |
| 17 | `data/aero/ks_datsun_240z_rear.wing` | `data/aero_dst/ks_datsun_240z_rear.wing` | suffix | data/cardata.car | none | yes | 0 (11/11) | 0 |
| 18 | `data/aero/wing_front_aoa_cd.curve` | `data/aero_dst/wing_front_aoa_cd.curve` | suffix | data/aero/ks_datsun_240z_front.wing, data/aero_dst/ks_datsun_240z_front.wing, data/cardata.car | none | yes | 0 (43/43) | 0 |
| 19 | `data/aero/wing_front_aoa_cl.curve` | `data/aero_dst/wing_front_aoa_cl.curve` | suffix | data/aero/ks_datsun_240z_front.wing, data/aero_dst/ks_datsun_240z_front.wing, data/cardata.car | none | yes | 0 (8/8) | 0 |
| 20 | `data/aero/wing_rear_aoa_cd.curve` | `data/aero_dst/wing_rear_aoa_cd.curve` | suffix | data/aero/ks_datsun_240z_rear.wing, data/aero_dst/ks_datsun_240z_rear.wing, data/cardata.car | none | yes | 0 (43/43) | 0 |
| 21 | `data/aero/wing_rear_aoa_cl.curve` | `data/aero_dst/wing_rear_aoa_cl.curve` | suffix | data/aero/ks_datsun_240z_rear.wing, data/aero_dst/ks_datsun_240z_rear.wing, data/cardata.car | none | yes | 0 (11/11) | 0 |

| file A | file B | path | value A | value B | label |
|---|---|---|---|---|---|
| `data/hdc_datsun_240z_01_open.drivetrain` | `data/tuning/hdc_datsun_240z_01_lsd.drivetrain` | `39` | `""` | `1: (f32) 0.8 3: (f32) 12 2: (f32) 0.65` | [unknown]; other side holds a nested message here (dump collapsed to one line) |
| `data/hdc_datsun_240z_01_open.drivetrain` | `data/tuning/hdc_datsun_240z_01_lsd.drivetrain` | `46` | `(f32) 250` | `(f32) 300` | [unknown] |
| `data/hdc_datsun_240z_01_open.drivetrain` | `data/tuning/hdc_datsun_240z_01_lsd.drivetrain` | `47` | `(f32) 0.0299999993` | `(f32) 0.0500000007` | [unknown] |
| `data/hdc_datsun_240z_01_open.drivetrain` | `data/tuning/hdc_datsun_240z_01_lsd.drivetrain` | `102` | `(f32) 20` | `(f32) 10` | [unknown] |
| `data/hdc_datsun_240z_01_open.drivetrain` | `data/tuning/hdc_datsun_240z_01_lsd.drivetrain` | `39.1` | (absent) | `(f32) 0.800000012` | [inferred] diff power lock |
| `data/hdc_datsun_240z_01_open.drivetrain` | `data/tuning/hdc_datsun_240z_01_lsd.drivetrain` | `39.3` | (absent) | `(f32) 12` | [inferred] diff preload Nm |
| `data/hdc_datsun_240z_01_open.drivetrain` | `data/tuning/hdc_datsun_240z_01_lsd.drivetrain` | `39.2` | (absent) | `(f32) 0.649999976` | [inferred] diff coast lock |
| `data/hdc_datsun_240z_01.carengine` | `data/tuning/hdc_datsun_240z_01_l28engine.carengine` | `2` | `"content\cars\hdc_datsun_240z_01\data\HEADER_POWER.curve"` | `"content\cars\hdc_datsun_240z_01\data\hdc13\l28_power.curve"` | [inferred] power curve path |
| `data/hdc_datsun_240z_01.carengine` | `data/tuning/hdc_datsun_240z_01_l28engine.carengine` | `3` | `"content\cars\hdc_datsun_240z_01\data\hdc_datsun_240z_01_coast1.curve"` | `"content\cars\hdc_datsun_240z_01\data\hdc13\l28_coast.curve"` | [inferred] coast curve path |
| `data/hdc_datsun_240z_01.carengine` | `data/tuning/hdc_datsun_240z_01_l28engine.carengine` | `4.3` | `"content\cars\hdc_datsun_240z_01\data\throttle.curve"` | `"content\cars\hdc_datsun_240z_01\data\hdc13\l28_throttle.curve"` | [verified] path string; meaning of field [unknown] |
| `data/hdc_datsun_240z_01.carengine` | `data/tuning/hdc_datsun_240z_01_l28engine.carengine` | `4.10` | `(f32) 0.300000012` | `(f32) 0.100000001` | [unknown] |
| `data/hdc_datsun_240z_01.carengine` | `data/tuning/hdc_datsun_240z_01_l28engine.carengine` | `5` | `600` | `700` | [inferred] idle rpm |
| `data/hdc_datsun_240z_01.carengine` | `data/tuning/hdc_datsun_240z_01_l28engine.carengine` | `6` | `7000` | `7300` | [inferred] limiter rpm |
| `data/hdc_datsun_240z_01.carengine` | `data/tuning/hdc_datsun_240z_01_l28engine.carengine` | `7` | `8` | `16` | [unknown] |
| `data/hdc_datsun_240z_01.carengine` | `data/tuning/hdc_datsun_240z_01_l28engine.carengine` | `14` | `"content\cars\hdc_datsun_240z_01\data\throttle.curve"` | `"content\cars\hdc_datsun_240z_01\data\hdc13\l28_throttle.curve"` | [verified] path string; meaning of field [unknown] |
| `data/hdc_datsun_240z_01_4speed.gearbox` | `data/tuning/hdc_datsun_240z_01_5speed.gearbox` | `2.2` | `(f32) -3.65700006` | `(f32) -3.38199997` | [inferred] gear ratio |
| `data/hdc_datsun_240z_01_4speed.gearbox` | `data/tuning/hdc_datsun_240z_01_5speed.gearbox` | `2[2].2` | `(f32) 3.59200001` | `(f32) 2.19199991` | [inferred] gear ratio |
| `data/hdc_datsun_240z_01_4speed.gearbox` | `data/tuning/hdc_datsun_240z_01_5speed.gearbox` | `2[3].2` | `(f32) 2.24600005` | `(f32) 1.60099995` | [inferred] gear ratio |
| `data/hdc_datsun_240z_01_4speed.gearbox` | `data/tuning/hdc_datsun_240z_01_5speed.gearbox` | `2[4].2` | `(f32) 1.41499996` | `(f32) 1.296` | [inferred] gear ratio |
| `data/hdc_datsun_240z_01_4speed.gearbox` | `data/tuning/hdc_datsun_240z_01_5speed.gearbox` | `2[5].2` | `(f32) 1` | `(f32) 1.13800001` | [inferred] gear ratio |
| `data/hdc_datsun_240z_01_4speed.gearbox` | `data/tuning/hdc_datsun_240z_01_5speed.gearbox` | `3` | `(f32) 3.36400008` | `(f32) 4.0999999` | [inferred] final drive ratio |
| `data/hdc_datsun_240z_01_4speed.gearbox` | `data/tuning/hdc_datsun_240z_01_5speed.gearbox` | `13.1` | `6200` | `7000` | [unknown] |
| `data/hdc_datsun_240z_01_4speed.gearbox` | `data/tuning/hdc_datsun_240z_01_5speed.gearbox` | `20` | `(f32) 100` | (absent) | [unknown] |
| `data/hdc_datsun_240z_01_4speed.gearbox` | `data/tuning/hdc_datsun_240z_01_5speed.gearbox` | `2[6].1` | (absent) | `"5"` | [inferred] gear name |
| `data/hdc_datsun_240z_01_4speed.gearbox` | `data/tuning/hdc_datsun_240z_01_5speed.gearbox` | `2[6].2` | (absent) | `(f32) 1` | [inferred] gear ratio |
| `data/hdc_datsun_240z_01.clutch` | `data/tuning/hdc_datsun_240z_01_clutch_5speed.clutch` | `1` | `(f32) 0.0219999999` | `(f32) 0.0182000007` | [unknown] |
| `data/hdc_datsun_240z_01.clutch` | `data/tuning/hdc_datsun_240z_01_clutch_5speed.clutch` | `2` | `(f32) 290` | `(f32) 500` | [unknown] |
| `data/hdc_datsun_240z_01.clutch` | `data/tuning/hdc_datsun_240z_01_clutch_5speed.clutch` | `3.4` | `(f32) 1500` | `(f32) 2000` | [unknown] |
| `data/hdc_datsun_240z_01.clutch` | `data/tuning/hdc_datsun_240z_01_clutch_5speed.clutch` | `3.5` | `(f32) 3000` | `(f32) 2500` | [unknown] |
| `data/hdc_datsun_240z_01.clutch` | `data/tuning/hdc_datsun_240z_01_clutch_5speed.clutch` | `40` | `"content\cars\hdc_datsun_240z_01\data\clutch_profile.curve"` | (absent) | [verified] path string; meaning of field [unknown] |
| `data/hdc_datsun_240z_01.clutch` | `data/tuning/hdc_datsun_240z_01_clutch_5speed.clutch` | `1[1].1` | `(f32) 1166` | (absent) | [unknown] |
| `data/hdc_datsun_240z_01.clutch` | `data/tuning/hdc_datsun_240z_01_clutch_5speed.clutch` | `1[1].2` | `"Datsun 240R Fairlady"` | (absent) | [unknown] |
| `data/hdc_datsun_240z_01.clutch` | `data/tuning/hdc_datsun_240z_01_clutch_5speed.clutch` | `1[1].4.2` | `(f32) 0.150000006` | (absent) | [unknown] |
| `data/hdc_datsun_240z_01.brakesystem` | `data/tuning/hdc_datsun_240z_01_brakes.brakesystem` | `1` | `(f32) 1500` | `(f32) 1800` | [unknown] |
| `data/hdc_datsun_240z_01.brakesystem` | `data/tuning/hdc_datsun_240z_01_brakes.brakesystem` | `2` | `(f32) 67` | `(f32) 62` | [unknown] |
| `data/hdc_datsun_240z_01_front.coilover` | `data/tuning/hdc_datsun_240z_01_g_nose_front.coilover` | `1` | `(f32) 20150` | `(f32) 54000` | [unknown] |
| `data/hdc_datsun_240z_01_front.coilover` | `data/tuning/hdc_datsun_240z_01_g_nose_front.coilover` | `3.3` | `(f32) 2000` | `(f32) 800` | [unknown] |
| `data/hdc_datsun_240z_01_front.coilover` | `data/tuning/hdc_datsun_240z_01_g_nose_front.coilover` | `3.4` | `(f32) 3` | `(f32) 1.79999995` | [unknown] |
| `data/hdc_datsun_240z_01_front.coilover` | `data/tuning/hdc_datsun_240z_01_g_nose_front.coilover` | `3.5` | `(f32) 0.0299999993` | `(f32) 0.0350000001` | [unknown] |
| `data/hdc_datsun_240z_01_front.coilover` | `data/tuning/hdc_datsun_240z_01_g_nose_front.coilover` | `3.6` | `(f32) 350` | `(f32) 1250` | [unknown] |
| `data/hdc_datsun_240z_01_front.coilover` | `data/tuning/hdc_datsun_240z_01_g_nose_front.coilover` | `4.2` | `(f32) 0.0199999996` | `(f32) 0.0149999997` | [unknown] |
| `data/hdc_datsun_240z_01_front.coilover` | `data/tuning/hdc_datsun_240z_01_g_nose_front.coilover` | `4.3` | `(f32) 1000` | `(f32) 500` | [unknown] |
| `data/hdc_datsun_240z_01_front.coilover` | `data/tuning/hdc_datsun_240z_01_g_nose_front.coilover` | `4.4` | `(f32) 2` | `(f32) 1.5` | [unknown] |
| `data/hdc_datsun_240z_01_rear.coilover` | `data/tuning/hdc_datsun_240z_01_g_nose_rear.coilover` | `1` | `(f32) 17750` | `(f32) 48000` | [unknown] |
| `data/hdc_datsun_240z_01_rear.coilover` | `data/tuning/hdc_datsun_240z_01_g_nose_rear.coilover` | `3.2` | `(f32) 0.0199999996` | `(f32) 0.0250000004` | [unknown] |
| `data/hdc_datsun_240z_01_rear.coilover` | `data/tuning/hdc_datsun_240z_01_g_nose_rear.coilover` | `3.3` | `(f32) 2000` | `(f32) 800` | [unknown] |
| `data/hdc_datsun_240z_01_rear.coilover` | `data/tuning/hdc_datsun_240z_01_g_nose_rear.coilover` | `3.4` | `(f32) 3` | `(f32) 1.79999995` | [unknown] |
| `data/hdc_datsun_240z_01_rear.coilover` | `data/tuning/hdc_datsun_240z_01_g_nose_rear.coilover` | `3.5` | `(f32) 0.0299999993` | `(f32) 0.0399999991` | [unknown] |
| `data/hdc_datsun_240z_01_rear.coilover` | `data/tuning/hdc_datsun_240z_01_g_nose_rear.coilover` | `3.6` | `(f32) 350` | `(f32) 1250` | [unknown] |
| `data/hdc_datsun_240z_01_rear.coilover` | `data/tuning/hdc_datsun_240z_01_g_nose_rear.coilover` | `4.4` | `(f32) 2` | `(f32) 1.5` | [unknown] |
| `data/hdc_datsun_240z_01_rear.coilover` | `data/tuning/hdc_datsun_240z_01_g_nose_rear.coilover` | `4.6` | `(f32) 300` | `(f32) 500` | [unknown] |
| `data/setup/hdc_datsun_240z_01.carsetup` | `data/setup/hdc_datsun_240z_01_g_nose.carsetup` | `2.2.2` | `(f32) 2000` | `(f32) 800` | [unknown] |
| `data/setup/hdc_datsun_240z_01.carsetup` | `data/setup/hdc_datsun_240z_01_g_nose.carsetup` | `2.3.1` | `(f32) -0.0599999987` | `(f32) -0.0700000003` | [unknown] |
| `data/setup/hdc_datsun_240z_01.carsetup` | `data/setup/hdc_datsun_240z_01_g_nose.carsetup` | `2.3.2` | `(f32) 200` | `(f32) 800` | [unknown] |
| `data/setup/hdc_datsun_240z_01.carsetup` | `data/setup/hdc_datsun_240z_01_g_nose.carsetup` | `2[1].2.2` | `(f32) 2000` | `(f32) 800` | [unknown] |
| `data/setup/hdc_datsun_240z_01.carsetuplimits` | `data/setup/hdc_datsun_240z_01_g_nose.carsetuplimits` | `1.3.2.2` | `(f32) 100` | `(f32) 90` | [inferred] brake power limit min |
| `data/setup/hdc_datsun_240z_01.carsetuplimits` | `data/setup/hdc_datsun_240z_01_g_nose.carsetuplimits` | `1.3.2.4` | `0` | `1` | [inferred] brake power limit enabled |
| `data/setup/hdc_datsun_240z_01.carsetuplimits` | `data/setup/hdc_datsun_240z_01_g_nose.carsetuplimits` | `2.1.1` | `(f32) 1000` | `(f32) 2700` | [unknown] |
| `data/setup/hdc_datsun_240z_01.carsetuplimits` | `data/setup/hdc_datsun_240z_01_g_nose.carsetuplimits` | `2.1.2` | `(f32) 54000` | `(f32) 48600` | [unknown] |

| # | curve A | curve B | points A/B | x range A | x range B | y range A | y range B | peak y @ x (A) | peak y @ x (B) | shared x | B/A min..max |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 10 | `data/header_power.curve` | `data/tuning/header_power_l28.curve` | 25/24 | 0..8000 | 0..8500 | 14.6667..220 | 80..227 | 220 @ 4400 | 227 @ 5972 | 1 | 0.610687..0.610687 |
| 11 | `data/throttle.curve` | `data/tuning/throttle_l28.curve` | 2/11 | 0..100 | 0..100 | 0..100 | 0..100 | 100 @ 100 | 100 @ 100 | 2 | 1..1 |
| 12 | `data/coast.curve` | `data/tuning/coast_l28.curve` | 17/5 | 0..7492.68 | 0..8000 | -18.1287..3.57143 | -95..35 | 3.57143 @ 0 | 35 @ 0 | 1 | 9.8..9.8 |
| 13 | `data/header_power.curve` | `data/hdc13/l28_power.curve` | 25/16 | 0..8000 | 0..8000 | 14.6667..220 | 70..270 | 220 @ 4400 | 270 @ 5000 | 2 | 0.534351..8.18182 |
| 14 | `data/hdc_datsun_240z_01_coast1.curve` | `data/hdc13/l28_coast.curve` | 6/9 | 0..8000 | 0..8000 | -80..30 | -80..35 | 30 @ 0 | 35 @ 0 | 4 | 0..1.16667 |
| 15 | `data/throttle.curve` | `data/hdc13/l28_throttle.curve` | 2/11 | 0..100 | 0..100 | 0..100 | 0..100 | 100 @ 100 | 100 @ 100 | 2 | 1..1 |
| 18 | `data/aero/wing_front_aoa_cd.curve` | `data/aero_dst/wing_front_aoa_cd.curve` | - | - | - | - | - | - | - | - | byte-identical |
| 19 | `data/aero/wing_front_aoa_cl.curve` | `data/aero_dst/wing_front_aoa_cl.curve` | - | - | - | - | - | - | - | - | byte-identical |
| 20 | `data/aero/wing_rear_aoa_cd.curve` | `data/aero_dst/wing_rear_aoa_cd.curve` | - | - | - | - | - | - | - | - | byte-identical |
| 21 | `data/aero/wing_rear_aoa_cl.curve` | `data/aero_dst/wing_rear_aoa_cl.curve` | - | - | - | - | - | - | - | - | byte-identical |

Part-file chain, datsun (paths are the string leaves inside the part files, [verified]; `field` = pbedit path of that string; mesh/sfx paths and carpart field 31 (other carparts) omitted).

| physics carpart | tuningpart(s) it points to (field) | data file(s) those tuningparts point to (field) |
|---|---|---|
| `240z_brake_tune.carpart` | `hdc_datsun_240z_01_brake.tuningpart` (102.1) | `data/tuning/hdc_datsun_240z_01_brakes.brakesystem` (36.1, in hdc_datsun_240z_01_brake.tuningpart) |
| `240z_diff_lsd.carpart` | `hdc_datsun_240z_01_lsd.tuningpart` (102.1) | `data/tuning/hdc_datsun_240z_01_lsd.drivetrain` (4.1, in hdc_datsun_240z_01_lsd.tuningpart) |
| `240z_engine_l28.carpart` | `hdc_datsun_240z_01_l28engine.tuningpart` (102.1) | `data/tuning/hdc_datsun_240z_01_l28engine.carengine` (2.1, in hdc_datsun_240z_01_l28engine.tuningpart) |
| `240z_gear_5speed.carpart` | `hdc_datsun_240z_01_5speed.tuningpart` (102.1); `hdc_datsun_240z_01_clutch_5speed.tuningpart` (102[1].1) | `data/tuning/hdc_datsun_240z_01_5speed.gearbox` (3.1, in hdc_datsun_240z_01_5speed.tuningpart); `data/tuning/hdc_datsun_240z_01_clutch_5speed.clutch` (5.1, in hdc_datsun_240z_01_clutch_5speed.tuningpart) |
| `240z_suspension_tune.carpart` | `hdc_datsun_240z_01_g_nose_setup.tuningpart` (102.1); `hdc_datsun_240z_01_g_nose_setuplimits.tuningpart` (102[1].1); `hdc_datsun_240z_01_g_nose_coilovers.tuningpart` (102[2].1) | `data/setup/hdc_datsun_240z_01_g_nose.carsetup` (30.1, in hdc_datsun_240z_01_g_nose_setup.tuningpart); `data/setup/hdc_datsun_240z_01_g_nose.carsetuplimits` (31.1, in hdc_datsun_240z_01_g_nose_setuplimits.tuningpart); `data/tuning/hdc_datsun_240z_01_g_nose_front.coilover` (7.1, in hdc_datsun_240z_01_g_nose_coilovers.tuningpart); `data/tuning/hdc_datsun_240z_01_g_nose_rear.coilover` (7.4, in hdc_datsun_240z_01_g_nose_coilovers.tuningpart) |

5 of 5 physics `.compatiblepart` files have field 1 = path of the same-named `.carpart` [verified].

### 2d. rx7 (hdc_rx7_fd_01)

RX-7 alternatives: `data/engine/` (stock engine, curves, turbos) against `data/parts/` (`*_tuned` engine, drivetrain, gearbox, clutch, curves, turbos). `data/mazda_rx7_build.cartuning` is a 0-byte file: it lists nothing; `cardata.car` field 6 is an empty payload (the same 0 bytes), and no other file in the package contains its path [verified].

| # | file A | file B | basis | A ref by | B ref by | byte-identical | differing leaf paths (A/B leaves) | rows shown |
|---|---|---|---|---|---|---|---|---|
| 1 | `data/engine/rx7_engine.carengine` | `data/parts/hdc_rx7_fd_01_tuned.carengine` | engine pointer (cardata 20 vs engine_drift.tuningpart) | data/cardata.car, data/hdc_rx7_fd_01.clutch, data/parts/hdc_rx7_fd_01_tuned.clutch | data/parts/hdc_rx7_fd_01_engine_drift.tuningpart | no | 35 (42/50) | 8 |
| 2 | `data/hdc_rx7_fd_01.drivetrain` | `data/parts/hdc_rx7_fd_01_tuned.drivetrain` | suffix | data/cardata.car, data/hdc_rx7_fd_01.clutch, data/parts/hdc_rx7_fd_01_tuned.clutch | data/parts/hdc_rx7_fd_01_drivetrain_drift.tuningpart | no | 9 (66/65) | 9 |
| 3 | `data/hdc_rx7_fd_01.gearbox` | `data/parts/hdc_rx7_fd_01_tuned.gearbox` | suffix | data/cardata.car, data/hdc_rx7_fd_01.clutch, data/parts/hdc_rx7_fd_01_tuned.clutch | data/parts/hdc_rx7_fd_01_gearbox_drift.tuningpart | no | 10 (32/28) | 10 |
| 4 | `data/hdc_rx7_fd_01.clutch` | `data/parts/hdc_rx7_fd_01_tuned.clutch` | suffix | data/cardata.car, data/parts/hdc_rx7_fd_01_tuned.clutch | data/parts/hdc_rx7_fd_01_clutch_drift.tuningpart | no | 9 (380/376) | 9 |
| 5 | `data/engine/header_power.curve` | `data/parts/header_power_tuned.curve` | suffix | data/cardata.car, data/engine/rx7_engine.carengine, data/hdc_rx7_fd_01.clutch (+1) | data/parts/hdc_rx7_fd_01_tuned.carengine | no | 49 (91/83) | curve summary |
| 6 | `data/engine/coast.curve` | `data/parts/coast_tuned.curve` | suffix | data/cardata.car, data/engine/rx7_engine.carengine, data/hdc_rx7_fd_01.clutch (+1) | data/parts/hdc_rx7_fd_01_tuned.carengine | no | 6 (17/17) | curve summary |
| 7 | `data/engine/throttle.curve` | `data/parts/throttle_tuned.curve` | suffix | data/cardata.car, data/engine/rx7_engine.carengine, data/hdc_rx7_fd_01.clutch (+2) | data/parts/hdc_rx7_fd_01_tuned.carengine | yes | 0 (6/6) | 0 |
| 8 | `data/engine/autoblipprofile.curve` | `data/parts/autoblipprofile_tuned.curve` | suffix | data/cardata.car, data/hdc_rx7_fd_01.clutch, data/hdc_rx7_fd_01.drivetrain (+3) | data/parts/hdc_rx7_fd_01_tuned.gearbox | no | 13 (6/13) | curve summary |
| 9 | `data/engine/ctrl_turbo0_controller0.curve` | `data/parts/ctrl_turbo0_controller0_tuned.curve` | suffix | data/cardata.car, data/engine/rx7_engine.carengine, data/hdc_rx7_fd_01.clutch (+1) | data/parts/hdc_rx7_fd_01_tuned.carengine | no | 48 (89/83) | curve summary |
| 10 | `data/engine/rx7_turbo0.turbo` | `data/parts/rx7_turbo_tuned_0.turbo` | suffix | data/cardata.car, data/engine/rx7_engine.carengine | data/parts/hdc_rx7_fd_01_tuned.carengine | no | 5 (5/4) | 5 |
| 11 | `data/engine/rx7_turbo1.turbo` | `data/parts/rx7_turbo_tuned_1.turbo` | suffix | data/cardata.car, data/engine/rx7_engine.carengine | data/parts/hdc_rx7_fd_01_tuned.carengine | no | 5 (5/4) | 5 |

| file A | file B | path | value A | value B | label |
|---|---|---|---|---|---|
| `data/engine/rx7_engine.carengine` | `data/parts/hdc_rx7_fd_01_tuned.carengine` | `1` | `(f32) 0.140000001` | `(f32) 0.129999995` | [unknown] |
| `data/engine/rx7_engine.carengine` | `data/parts/hdc_rx7_fd_01_tuned.carengine` | `2` | `"content\cars\hdc_rx7_fd_01\data\engine\HEADER_POWER.curve"` | `"content\cars\hdc_rx7_fd_01\data\parts\HEADER_POWER_tuned.curve"` | [inferred] power curve path |
| `data/engine/rx7_engine.carengine` | `data/parts/hdc_rx7_fd_01_tuned.carengine` | `3` | `"content\cars\hdc_rx7_fd_01\data\engine\coast.curve"` | `"content\cars\hdc_rx7_fd_01\data\parts\coast_tuned.curve"` | [inferred] coast curve path |
| `data/engine/rx7_engine.carengine` | `data/parts/hdc_rx7_fd_01_tuned.carengine` | `4.1` | `(f32) 0.980000019` | `(f32) 1` | [unknown] |
| `data/engine/rx7_engine.carengine` | `data/parts/hdc_rx7_fd_01_tuned.carengine` | `4.3` | `"content\cars\hdc_rx7_fd_01\data\engine\throttle.curve"` | `"content\cars\hdc_rx7_fd_01\data\parts\throttle_tuned.curve"` | [verified] path string; meaning of field [unknown] |
| `data/engine/rx7_engine.carengine` | `data/parts/hdc_rx7_fd_01_tuned.carengine` | `4.9` | `2` | `1` | [unknown] |
| `data/engine/rx7_engine.carengine` | `data/parts/hdc_rx7_fd_01_tuned.carengine` | `4.10` | `(f32) 0.150000006` | `(f32) 0.200000003` | [unknown] |
| `data/engine/rx7_engine.carengine` | `data/parts/hdc_rx7_fd_01_tuned.carengine` | `5` | `700` | `1400` | [inferred] idle rpm |
| `data/hdc_rx7_fd_01.drivetrain` | `data/parts/hdc_rx7_fd_01_tuned.drivetrain` | `39.1` | `(f32) 0.850000024` | `(f32) 0.330000013` | [inferred] diff power lock |
| `data/hdc_rx7_fd_01.drivetrain` | `data/parts/hdc_rx7_fd_01_tuned.drivetrain` | `39.2` | `(f32) 0.699999988` | `(f32) 0.330000013` | [inferred] diff coast lock |
| `data/hdc_rx7_fd_01.drivetrain` | `data/parts/hdc_rx7_fd_01_tuned.drivetrain` | `39.11` | `(f32) 2.5` | `(f32) 3` | [unknown] |
| `data/hdc_rx7_fd_01.drivetrain` | `data/parts/hdc_rx7_fd_01_tuned.drivetrain` | `39.12` | `(f32) 3` | (absent) | [unknown] |
| `data/hdc_rx7_fd_01.drivetrain` | `data/parts/hdc_rx7_fd_01_tuned.drivetrain` | `39.4` | `0` | (absent) | [unknown] |
| `data/hdc_rx7_fd_01.drivetrain` | `data/parts/hdc_rx7_fd_01_tuned.drivetrain` | `47` | `(f32) 0.300000012` | `(f32) 0.0599999987` | [unknown] |
| `data/hdc_rx7_fd_01.drivetrain` | `data/parts/hdc_rx7_fd_01_tuned.drivetrain` | `102` | `(f32) 30` | `(f32) 25` | [unknown] |
| `data/hdc_rx7_fd_01.drivetrain` | `data/parts/hdc_rx7_fd_01_tuned.drivetrain` | `104` | `(f32) 2` | `(f32) 2.5` | [unknown] |
| `data/hdc_rx7_fd_01.drivetrain` | `data/parts/hdc_rx7_fd_01_tuned.drivetrain` | `39.13` | (absent) | `(f32) 0.5` | [unknown] |
| `data/hdc_rx7_fd_01.gearbox` | `data/parts/hdc_rx7_fd_01_tuned.gearbox` | `2[4].2` | `(f32) 1.60000002` | `(f32) 1.39100003` | [inferred] gear ratio |
| `data/hdc_rx7_fd_01.gearbox` | `data/parts/hdc_rx7_fd_01_tuned.gearbox` | `3` | `(f32) 4` | `(f32) 4.30000019` | [inferred] final drive ratio |
| `data/hdc_rx7_fd_01.gearbox` | `data/parts/hdc_rx7_fd_01_tuned.gearbox` | `12.1` | `"content\cars\hdc_rx7_fd_01\data\engine\autoBlipProfile.curve"` | `"content\cars\hdc_rx7_fd_01\data\parts\autoBlipProfile_tuned.curve"` | [verified] path string; meaning of field [unknown] |
| `data/hdc_rx7_fd_01.gearbox` | `data/parts/hdc_rx7_fd_01_tuned.gearbox` | `12.2` | `0` | (absent) | [unknown] |
| `data/hdc_rx7_fd_01.gearbox` | `data/parts/hdc_rx7_fd_01_tuned.gearbox` | `13.1` | `7500` | `7900` | [unknown] |
| `data/hdc_rx7_fd_01.gearbox` | `data/parts/hdc_rx7_fd_01_tuned.gearbox` | `13.5` | `4500` | (absent) | [unknown] |
| `data/hdc_rx7_fd_01.gearbox` | `data/parts/hdc_rx7_fd_01_tuned.gearbox` | `20` | `(f32) 100` | (absent) | [unknown] |
| `data/hdc_rx7_fd_01.gearbox` | `data/parts/hdc_rx7_fd_01_tuned.gearbox` | `19` | `0` | (absent) | [unknown] |
| `data/hdc_rx7_fd_01.gearbox` | `data/parts/hdc_rx7_fd_01_tuned.gearbox` | `18` | `(f32) 1` | (absent) | [unknown] |
| `data/hdc_rx7_fd_01.gearbox` | `data/parts/hdc_rx7_fd_01_tuned.gearbox` | `6` | (absent) | `(f32) 260` | [unknown] |
| `data/hdc_rx7_fd_01.clutch` | `data/parts/hdc_rx7_fd_01_tuned.clutch` | `1` | `(f32) 0.0170000009` | `(f32) 0.0370000005` | [unknown] |
| `data/hdc_rx7_fd_01.clutch` | `data/parts/hdc_rx7_fd_01_tuned.clutch` | `2` | `(f32) 600` | `(f32) 800` | [unknown] |
| `data/hdc_rx7_fd_01.clutch` | `data/parts/hdc_rx7_fd_01_tuned.clutch` | `3.1` | `"content\cars\hdc_rx7_fd_01\data\upShiftProfile.curve"` | (absent) | [verified] path string; meaning of field [unknown] |
| `data/hdc_rx7_fd_01.clutch` | `data/parts/hdc_rx7_fd_01_tuned.clutch` | `3.2` | `"content\cars\hdc_rx7_fd_01\data\downShiftProfile.curve"` | (absent) | [verified] path string; meaning of field [unknown] |
| `data/hdc_rx7_fd_01.clutch` | `data/parts/hdc_rx7_fd_01_tuned.clutch` | `3.4` | `(f32) 1500` | `(f32) 100` | [unknown] |
| `data/hdc_rx7_fd_01.clutch` | `data/parts/hdc_rx7_fd_01_tuned.clutch` | `3.5` | `(f32) 2500` | `""` | [unknown] |
| `data/hdc_rx7_fd_01.clutch` | `data/parts/hdc_rx7_fd_01_tuned.clutch` | `3.5[1]` | `""` | (absent) | [unknown] |
| `data/hdc_rx7_fd_01.clutch` | `data/parts/hdc_rx7_fd_01_tuned.clutch` | `3.6` | `0` | `""` | [unknown] |
| `data/hdc_rx7_fd_01.clutch` | `data/parts/hdc_rx7_fd_01_tuned.clutch` | `3.3` | `0` | (absent) | [unknown] |
| `data/engine/rx7_turbo0.turbo` | `data/parts/rx7_turbo_tuned_0.turbo` | `2` | `(f32) 0.995000005` | `(f32) 0.996999979` | [unknown] |
| `data/engine/rx7_turbo0.turbo` | `data/parts/rx7_turbo_tuned_0.turbo` | `3` | `(f32) 0.99000001` | `(f32) 0.996999979` | [unknown] |
| `data/engine/rx7_turbo0.turbo` | `data/parts/rx7_turbo_tuned_0.turbo` | `4` | `(f32) 3000` | `(f32) 3700` | [unknown] |
| `data/engine/rx7_turbo0.turbo` | `data/parts/rx7_turbo_tuned_0.turbo` | `5` | `(f32) 1` | (absent) | [unknown] |
| `data/engine/rx7_turbo0.turbo` | `data/parts/rx7_turbo_tuned_0.turbo` | `6` | `(f32) 0.699999988` | `(f32) 2` | [unknown] |
| `data/engine/rx7_turbo1.turbo` | `data/parts/rx7_turbo_tuned_1.turbo` | `2` | `(f32) 0.987999976` | `(f32) 0.996749997` | [unknown] |
| `data/engine/rx7_turbo1.turbo` | `data/parts/rx7_turbo_tuned_1.turbo` | `3` | `(f32) 0.985000014` | `(f32) 0.995999992` | [unknown] |
| `data/engine/rx7_turbo1.turbo` | `data/parts/rx7_turbo_tuned_1.turbo` | `4` | `(f32) 5000` | `(f32) 4450` | [unknown] |
| `data/engine/rx7_turbo1.turbo` | `data/parts/rx7_turbo_tuned_1.turbo` | `5` | `(f32) 1` | (absent) | [unknown] |
| `data/engine/rx7_turbo1.turbo` | `data/parts/rx7_turbo_tuned_1.turbo` | `6` | `(f32) 0.699999988` | `(f32) 2` | [unknown] |

| # | curve A | curve B | points A/B | x range A | x range B | y range A | y range B | peak y @ x (A) | peak y @ x (B) | shared x | B/A min..max |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | `data/engine/header_power.curve` | `data/parts/header_power_tuned.curve` | 23/21 | 0..8200 | 0..9000 | 80.62..263.359 | 100..145 | 263.359 @ 2292 | 145 @ 6524 | 1 | 0.854489..0.854489 |
| 6 | `data/engine/coast.curve` | `data/parts/coast_tuned.curve` | 4/4 | 0..9000 | 0..9000 | -40..10 | -40..10 | 10 @ 0 | 10 @ 0 | 3 | -0.5..1 |
| 7 | `data/engine/throttle.curve` | `data/parts/throttle_tuned.curve` | - | - | - | - | - | - | - | - | byte-identical |
| 8 | `data/engine/autoblipprofile.curve` | `data/parts/autoblipprofile_tuned.curve` | 4/4 | 0..200 | 0..180 | 0..0.8 | 0..0.6 | 0.8 @ 20 | 0.6 @ 20 | 2 | 0.75..0.75 |
| 9 | `data/engine/ctrl_turbo0_controller0.curve` | `data/parts/ctrl_turbo0_controller0_tuned.curve` | 23/21 | 0..8300 | 0..9000 | 0..0.741 | 0.016..2.047 | 0.741 @ 3728 | 2.047 @ 5068 | 1 | - |

Part-file chain, rx7 (paths are the string leaves inside the part files, [verified]; `field` = pbedit path of that string; mesh/sfx paths and carpart field 31 (other carparts) omitted).

| physics carpart | tuningpart(s) it points to (field) | data file(s) those tuningparts point to (field) |
|---|---|---|
| `rx7fd_drivetrain_drift.carpart` | `hdc_rx7_fd_01_drivetrain_drift.tuningpart` (102.1); `hdc_rx7_fd_01_gearbox_drift.tuningpart` (102[1].1); `hdc_rx7_fd_01_clutch_drift.tuningpart` (102[2].1) | `data/parts/hdc_rx7_fd_01_tuned.drivetrain` (4.1, in hdc_rx7_fd_01_drivetrain_drift.tuningpart); `data/parts/hdc_rx7_fd_01_tuned.gearbox` (3.1, in hdc_rx7_fd_01_gearbox_drift.tuningpart); `data/parts/hdc_rx7_fd_01_tuned.clutch` (5.1, in hdc_rx7_fd_01_clutch_drift.tuningpart) |
| `rx7fd_engine_drift.carpart` | `hdc_rx7_fd_01_engine_drift.tuningpart` (102.1) | `data/parts/hdc_rx7_fd_01_tuned.carengine` (2.1, in hdc_rx7_fd_01_engine_drift.tuningpart) |
| `rx7fd_suspension_drift.carpart` | - | - |

3 of 3 physics `.compatiblepart` files have field 1 = path of the same-named `.carpart` [verified].

### 2e. mercedes (hdc_mercedes_190e_01)

Mercedes has no `data/parts`, `data/tuning` or `.tuningpart`/`.carpart` files (`presets/` has only the mechanical and visual presets, one carfinalstate and one compatibletyres file); the only sibling pair is the coast curve (`coast.curve` / `coast_kurve.curve`).

| # | file A | file B | basis | A ref by | B ref by | byte-identical | differing leaf paths (A/B leaves) | rows shown |
|---|---|---|---|---|---|---|---|---|
| 1 | `data/coast.curve` | `data/coast_kurve.curve` | suffix | data/cardata.car, data/hdc_mercedes_190e_01.clutch | data/cardata.car, data/hdc_mercedes_190e_01.carengine | no | 356 (370/23) | curve summary |

| # | curve A | curve B | points A/B | x range A | x range B | y range A | y range B | peak y @ x (A) | peak y @ x (B) | shared x | B/A min..max |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `data/coast.curve` | `data/coast_kurve.curve` | 93/7 | 0..9200 | 0..9600 | -140..52.299 | -64..80 | 52.299 @ 0 | 80 @ 500 | 4 | -0.478571..1.91429 |

### 2f. e46 (hdc_bmw_e46_01)

E46 (extra): the Kunos original and the `_1` HDC versions of the power and throttle curves.

| # | file A | file B | basis | A ref by | B ref by | byte-identical | differing leaf paths (A/B leaves) | rows shown |
|---|---|---|---|---|---|---|---|---|
| 1 | `data/bmw_m3_e46_coupe_engine_power.curve` | `data/bmw_m3_e46_coupe_engine_power_1.curve` | suffix | none | data/cardata.car, data/hdc_bmw_e46_01.car, data/ks_bmw_m3_e46_engine_1.carengine | no | 44 (79/87) | curve summary |
| 2 | `data/bmw_m3_e46_coupe_throttle_response.curve` | `data/bmw_m3_e46_coupe_throttle_response_1.curve` | suffix | none | data/cardata.car, data/hdc_bmw_e46_01.car, data/ks_bmw_m3_e46_engine_1.carengine | no | 34 (38/6) | curve summary |

| # | curve A | curve B | points A/B | x range A | x range B | y range A | y range B | peak y @ x (A) | peak y @ x (B) | shared x | B/A min..max |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `data/bmw_m3_e46_coupe_engine_power.curve` | `data/bmw_m3_e46_coupe_engine_power_1.curve` | 20/22 | -1000.08..8500 | -1000..8500 | 0..368 | 0..377.878 | 368 @ 5000 | 377.878 @ 5000 | 18 | 1.01658..1.40709 |
| 2 | `data/bmw_m3_e46_coupe_throttle_response.curve` | `data/bmw_m3_e46_coupe_throttle_response_1.curve` | 10/2 | 0..100 | 0..100 | 0..100 | 0..100 | 100 @ 100 | 100 @ 100 | 2 | 1..1 |

## 3. Cross-car key values

Paths: mass = `data/cardata.car` `1.1`; files used per car are the ones named by `cardata.car` string fields 19 (carsetup), 16 (carsetuplimits), 20 (carengine), 22 (drivetrain), 24 (gearbox), 10/11 (front/rear `.tyre`), resolved case-insensitively. diff drivetrain = drivetrain `39.1/39.2/39.3`; diff carsetup = carsetup `1.4.1/1.4.2/1.4.3`; diff limits = carsetuplimits `1.4.n.1..4` printed `step/min/max/enabled` (`-` = field absent); steer = carsetup `1.2` and limits `1.2.1..4`; brake bias = carsetup `1.3.1`, limits `1.3.1.1..4`; brake power = carsetup `1.3.2`, limits `1.3.2.1..4`; idle/limiter = carengine `5`/`6`; peak torque = max of field 10 over points of the curve named by carengine `2` (x = field 1); gears dt/gb = drivetrain `9` / gearbox `1`; final dt/gb = drivetrain `11` / gearbox `3`; tyre = `.tyre` `1` (name) with `12.1` (width, equals the number in the file name). Floats rounded to 6 significant digits. All values [verified]; their meanings are [inferred] (see Section 0).

| car | mass `1.1` | diff drivetrain `39.1/.2/.3` | diff carsetup `1.4.1/.2/.3` | limits `1.4.1` | limits `1.4.2` | limits `1.4.3` | steer `1.2` (limits `1.2`) | brake bias `1.3.1` (limits) | brake power `1.3.2` (limits) | idle/limiter `5`/`6` | peak torque @ rpm | gears dt/gb | final dt/gb | tyre front (width) | tyre rear (width) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ae86 | 995 | 0.85/0.7/10 | 0.85/0.7/10 | 0.05/0.1/1/1 | 0.05/0.1/1/1 | 1/1/62/1 | -14 (0.1/-14/-14/0) | 74 (1/68/90/1) | 100 (1/90/100/1) | 1000/9000 | 215 @ 6500 | absent/5 | absent/4 | Hina's Drifters AE86 (185) | Hina's Drifters AE86 (185) |
| datsun | 1190 | 0.8/0.65/12 | 0.8/0.65/12 | 0.05/0.7/1/1 | 0.05/0.5/0.8/1 | 1/5/25/1 | 17.8 (0.1/17.8/17.8/0) | 62 (1/58/66/1) | 100 (1/90/100/1) | 700/7300 | 270 @ 5000 | 5/5 | 3.9/4.1 | Hina's Drifters - 240Z (225) | Hina's Drifters - 240Z (225) |
| e46 | 1495 | 0.85/0.7/10 | 0.85/0.7/10 | 0.05/0.7/1/1 | 0.05/0.55/0.85/1 | 5/5/30/1 | 14 (0.1/14/14/0) | 63 (1/61/65/1) | 100 (1/90/100/1) | 700/8100 | 377.878 @ 5000 | 6/6 | 3.09/3.91 | Hina's Drifters E46 (235) | Hina's Drifters E46 (265) |
| mercedes | 1420 | 0.85/0.7/10 | 0.85/0.7/10 | 0.05/0.8/0.9/1 | 0.05/0.65/0.75/1 | 1/8/12/1 | -15.27 (1.527/-15.27/-15.27/-) | 75 (1/73/77/1) | 100 (1/90/100/1) | 500/7800 | 470 @ 4543.11 | 6/5 | 4.45/3.7 | Hina's Drifters 190E (245) | Hina's Drifters 190E (245) |
| rx7 | 1345 | 0.85/0.7/10 | 0.85/0.7/10 | 0.05/0.7/1/1 | 0.05/0.55/0.85/1 | 5/5/30/1 | 14 (0.1/14/14/0) | 69 (1/67/71/1) | 100 (1/90/100/1) | 700/8000 | 263.359 @ 2292 | 5/5 | 4.3/4 | Hina's Drifters RX-7 (235) | Hina's Drifters RX-7 (255) |
| s2000 | 1351 | 0.82/0.68/10 | 0.82/0.68/10 | 0.05/0.7/1/1 | 0.05/0.55/0.85/1 | 5/5/30/1 | 13.9 (0.1/13.9/13.9/0) | 74 (1/72/76/1) | 110 (1/100/100/-) | 500/9200 | 303.106 @ 6200 | 6/6 | 4.756/4.4 | Hina's Drifters S2000 (205) | Hina's Drifters S2000 (225) |

Files used (from the same `cardata.car` fields): ae86: carsetup `data/setup/toyota_ae86_tuned.carsetup`, limits `data/setup/toyota_ae86_tuned.carsetuplimits`, engine `data/parts/ks_ae86_beginner_h_01_tuned.carengine` (curve `data/na_character_v1/power_na_friendly.curve`), drivetrain `data/ks_ae86_beginner_h_01.drivetrain`, gearbox `data/ks_ae86_beginner_h_01.gearbox`; datsun: carsetup `data/setup/hdc_datsun_240z_01_g_nose.carsetup`, limits `data/setup/hdc_datsun_240z_01_g_nose.carsetuplimits`, engine `data/tuning/hdc_datsun_240z_01_l28engine.carengine` (curve `data/hdc13/l28_power.curve`), drivetrain `data/tuning/hdc_datsun_240z_01_lsd.drivetrain`, gearbox `data/tuning/hdc_datsun_240z_01_5speed.gearbox`; e46: carsetup `data/setup/hdc_bmw_e46_01.carsetup`, limits `data/setup/limits_m3_e46.carsetuplimits`, engine `data/ks_bmw_m3_e46_engine_1.carengine` (curve `data/bmw_m3_e46_coupe_engine_power_1.curve`), drivetrain `data/ks_bmw_m3_e46_1.drivetrain`, gearbox `data/ks_bmw_m3_e46_1.gearbox`; mercedes: carsetup `data/setup/mercedes_190e_evo_ii.carsetup`, limits `data/setup/mercedes_190e_evo_ii.carsetuplimits`, engine `data/hdc_mercedes_190e_01.carengine` (curve `data/header_power.curve`), drivetrain `data/hdc_mercedes_190e_01.drivetrain`, gearbox `data/hdc_mercedes_190e_01.gearbox`; rx7: carsetup `data/setup/hdc_rx7_fd_01.carsetup`, limits `data/setup/hdc_rx7_fd_01.carsetuplimits`, engine `data/engine/rx7_engine.carengine` (curve `data/engine/header_power.curve`), drivetrain `data/hdc_rx7_fd_01.drivetrain`, gearbox `data/hdc_rx7_fd_01.gearbox`; s2000: carsetup `data/setup/hdc_honda_s2000_ap1_01.carsetup`, limits `data/setup/hdc_honda_s2000_ap1_01.carsetuplimits`, engine `data/hdc_honda_s2000_ap1_01.carengine` (curve `data/header_power.curve`), drivetrain `data/hdc_honda_s2000_ap1_01.drivetrain`, gearbox `data/hdc_honda_s2000_ap1_01.gearbox`.

## 4. Observations

1. [verified] In all six cars the inline blocks `cardata.car` 3, 4, 5, 23, 25 are byte-identical to the file named by the path field 22, 20, 27, 24, 26 (30 of 30 comparisons, table in Section 1). The pointed-to file is the variant, not the default-named sibling: ae86 points to `parts/ks_ae86_beginner_h_01_tuned.carengine` (stock engine file is `data/ks_ae86_beginner_h_01.carengine`), datsun to the `data/tuning/*` LSD, L28 engine, 5-speed gearbox, 5-speed clutch and brakes.
2. [verified] Field 2 embeds the two coilover and two suspension files and field 12 embeds the three `.wing` files in every car: 18 of 18 wings and 23 of 24 suspension/coilover blocks are byte-identical, the 24th (s2000 `2.41` rear suspension) has identical leaves but different field order. Curves (engine, shift profiles, aero), setups, limits, tyres and aicardata are never embedded; they exist once as separate files.
3. [verified] E46 `data/cardata.car` and `data/hdc_bmw_e46_01.car` have the same size and differ in exactly one leaf, `8.4` (0.0026 vs 0.0025). The other five cars have no `<car_id>.car`.
4. [verified] Field 25 is byte-identical to the `.clutch` file in all six cars. For e46, mercedes, rx7 and s2000 (2.9 to 4.0 KB) it holds a second message after the clutch fields (inner field numbers repeat 1 and 2) containing Kunos source-car ids: e46 `ks_alfa_romeo_giulia_gtam` x30, mercedes `ks_mercedes_190e_evo_ii` x2, rx7 `ks_mazda_rx7_fd` x4 and `mazda_rx7` x3, s2000 `ks_honda_s2000_ap1` x2. [inferred] these are leftover car-data blocks from the Kunos source cars; ae86 and datsun clutches (153 and 145 B) contain only their own id.
5. [verified] S2000 drift vs normal: engine 16 differing leaves (field 5: 500 to 780, field 7: 10 to 50, the `4.*` block and fields 20, 40, 41, 50 absent in the drift engine, field 1 0.138 to 0.105, field 2 points to `HEADER_POWER_drift.curve`); drivetrain 4 leaves (`39.1` and `39.2` absent in the drift file, `39.4` 0 to 1, `39.12` 3 to 2); front suspension 7 leaves (`1.2` 1.47 to 1.77 and six values under `2.*`); power curve peak 303.106 @ 6200 to 330 @ 6500 with drift/normal torque 1.06108 to 1.90527 at the ten shared nonzero rpm. Limiter field 6 and the final-drive fields do not differ.
6. [verified] No file in the s2000 package contains a path to the `_drift` engine, drivetrain or front suspension (only `_drift.carengine` names `header_power_drift.curve`), the package has no `.tuningpart` or physics `.carpart` files, and `cardata.car` points to the normal files. [unknown] whether and how the game ever selects the `_drift` files.
7. [verified] ae86 `_open.drivetrain` and `_spool.drivetrain` are byte-identical to each other (`39.1` = `39.2` = 0.25, `39.3` = 5, `39.4` = 1) against the default 0.85 / 0.7 / 10 and `39.4` = 0; the `ae86_diff_lsd` part points to the default drivetrain, and no file references `_open.drivetrain`. Datsun `hdc_datsun_240z_01_open.drivetrain` (empty `39`) is also referenced by no file; `tuning/*_lsd.drivetrain` (0.8 / 0.65 / 12) is the one in `cardata.car`.
8. [verified] rx7 `parts/*_tuned.*` are referenced only through the `*_drift.tuningpart` files; `cardata.car` uses the non-tuned rx7 files. The tuned drivetrain has `39.1` = `39.2` = 0.33 (default 0.85 / 0.7), a new `39.13` = 0.5 and no `39.12` / `39.4`; the tuned engine has fields 5 / 6 = 1400 / 7000 (default 700 / 8000). `rx7fd_suspension_drift.carpart` has no tuningpart pointer, and `mazda_rx7_build.cartuning` is empty.
9. [verified] The diff default triple is the same in the used drivetrain and the used carsetup in all six cars (0.85 / 0.7 / 10 for ae86, e46, mercedes, rx7; datsun 0.8 / 0.65 / 12; s2000 0.82 / 0.68 / 10).
10. [verified] The diff limit ranges differ per car (Section 3): power-lock max is 1 in five cars (0.9 in mercedes); only ae86 allows coast lock up to 1, and only ae86 has min 0.1 for both locks; coast-lock max of the others is 0.8 (datsun), 0.85 (e46, rx7, s2000), 0.75 (mercedes); preload max is 62 (ae86), 25 (datsun), 30 (e46, rx7, s2000), 12 (mercedes). The six cars do not share one diff limit range.
11. [verified] Steer-ratio limit `1.2` has min = max = the carsetup default in all six cars (enabled flag 0 in five, absent in mercedes); ae86 and mercedes defaults are negative (-14, -15.27) [unknown meaning of the sign]. S2000 default brake power (`1.3.2`) is 110 while its limit range is 100 to 100 with no enabled flag.
12. [verified] Drivetrain and gearbox disagree on gearing: mercedes 6 gears (drivetrain `9`) vs 5 (gearbox `1`); final drive differs in all five cars that have drivetrain `11` (datsun 3.9 / 4.1, e46 3.09 / 3.91, mercedes 4.45 / 3.7, rx7 4.3 / 4, s2000 4.756 / 4.4); the ae86 drivetrain has no gear fields. [unknown] which one the game uses.

### Questions that need the game or schemas

1. Which copy does the game read: the inline blocks of `cardata.car` or the files its path fields name? They are byte-identical for every shared block, so only an in-game test with a value changed in one copy only can tell.
2. Does the game read `data/<car_id>.car` (E46 only, one differing leaf `8.4`) in addition to or instead of `data/cardata.car`?
3. What selects the `_drift` (s2000) and `_tuned` (rx7) files, given that nothing references them and the s2000 package has no part files: file naming, the preset / carfinalstate files, or nothing?
4. What does an absent `39.1` / `39.2` mean in a drivetrain (s2000 drift, datsun open: proto default 0 or no limited-slip model), and what is `39.4` (0 default, 1 in s2000 drift, ae86 open/spool)?
5. Which gearing drives the simulation: drivetrain `9` / `10` / `11` or gearbox `1` / `2` / `3`?
6. Are the second-message blocks inside the four large `.clutch` files read by the game or ignored?
7. What is the sign of a negative steer ratio, and what does an absent limit `enabled` flag (mercedes `1.2`, s2000 `1.3.2`) mean?
8. What is carsetup `1.1` (an 8-byte value that differs between ae86 `toyota_ae86` and `toyota_ae86_tuned`)?

