# BMW M3 E46 package: car anatomy (`hdc_bmw_e46_01`)

Knowledge base for the E46 package `hinas_drift_club_e46_v1.4.kspkg`, extracted at `hdc_1.4/extracted/e46/content/cars/hdc_bmw_e46_01/` (read-only reference). Companion: `docs/tuning-levers.md`. Facts only; no tuning advice here.

**Labels.** `[verified]` = read from the files or computed by a script from them; `[inferred]` = guessed from values or names; `[unknown]` = nothing established; `[general]` = general knowledge about cars/drifting, not from the files. File paths below are relative to the car root (`content/cars/hdc_bmw_e46_01/`) unless they start with `hdc_1.4/`.

Totals [verified]: 157 files, 54,586,019 bytes; refgraph (`python3 -I tools/refgraph.py hdc_1.4/extracted/e46`) scans 157 files, 96 with `content\` references, 336 distinct refs (60 inside this car, 276 external), 0 MISSING.

## 1. Package and folder layout

**Container** [verified]: a `.kspkg` is a 1 MiB zero header, file data, and a 64 MiB XOR-obscured table of 256-byte entries; see `HANDOVER.md` section 5 and `tools/kspkg.py` (not repeated here). The E46 package holds 157 files plus 21 directory entries (178 entries), raw size 123,731,968 bytes (`hdc_1.4/extracted/e46_filelist.txt` header), original sha256 `59d1bad1c5652d334c34351157a5ab85756b9b1a1aca5e2056e0d7c423669e47` (`spec/e46_package.sha256`); `kspkg.py pack` of the extracted tree reproduces it byte for byte (re-run for this document, see `docs/tuning-levers.md` section 5).

| folder | files | bytes | content (role label) |
|---|---|---|---|
| `(car root)` | 3 | 12,510 | `.actor` (scene graph / part nodes), `.scene`, `.moddedcarcontent` [inferred] |
| `camera/` | 1 | 11 | one camera graphics override [inferred] |
| `collider/` | 1 | 6,812 | collision mesh [inferred] |
| `data/ (top level)` | 21 | 24,424 | physics: `.car` x2, engine, drivetrain, gearbox, clutch, brakes, AI data, suspension, coilover, curves |
| `data/aero/` | 6 | 750 | aero curves referenced by `cardata.car` [verified] |
| `data/setup/` | 2 | 2,201 | default setup + setup limits |
| `data/tyres/` | 5 | 3,170 | two `.tyre` files + their curves |
| `data/wings/` | 13 | 1,611 | four `.wing` files + 9 curves (9 curves unreferenced by path) |
| `displays/ (top level)` | 4 | 29,616 | in-car display web page (html/css/js/less) |
| `displays/images/` | 3 | 1,923,706 | display background image + texture pair |
| `generated/thumbnails/` | 2 | 1,048,660 | generated car thumbnail texture pair [inferred] |
| `generated/windshield/` | 4 | 50,331,672 | baked windshield textures (name only) |
| `instruments/` | 4 | 3,203 | gauges, LEDs, lights, backfire definitions [inferred] |
| `materials/` | 70 | 1,188,483 | 70 material files |
| `presets/` | 4 | 2,084 | carfinalstate, mechanical/visual presets, compatible tyres |
| `skins/` | 6 | 3,492 | designs, compatible rim, rim descriptors |
| `uiresources/` | 4 | 1,779 | localization text (4 `.loc`) |
| `vfx/` | 4 | 1,835 | particle emitter, its mesh and curves |

**Loose files outside the package** [verified from `hdc_1.4/original/Source/ProductConfig.cs`, line 3, arrays `ProductModsPaths` / `ProductUiRoots`]. The HDC installer copies, per car, loose UI files into the mods folder next to the `.kspkg` files. For the E46:

```
"hinas_drift_club_e46_v1.4.kspkg"
"uiresources/localization/cars/hdc_bmw_e46_01/en.loc"
"uiresources/localization/cars/hdc_bmw_e46_01/preset_hdc_e46_mech_1.en.loc"
"uiresources/localization/cars/hdc_bmw_e46_01/setup.en.loc"
"uiresources/branding/oem/hina_drift_club/badge.texture"   (+ badge.texturemips, logo.texture, logo.texturemips)
ProductUiRoots: "uiresources/localization/cars/hdc_bmw_e46_01", "uiresources/branding/oem/hina_drift_club"
```

- Sources in this repo: `hdc_1.4/payload/uiresources/...` [verified]. The three car `.loc` files there are byte-identical to the copies inside the package (`uiresources/localization/*.loc`, cmp run) [verified]; `en.cars.loc` exists only inside the package and is not in `ProductModsPaths` [verified].
- Branding files are shared by all six HDC cars (`hina_drift_club` folder, not per car) [inferred from the path]: `badge.texture` 247 B, `badge.texturemips` 6,029,312 B, `logo.texture` 73 B, `logo.texturemips` 524,288 B [verified sizes]. The brand id `hina_drift_club` appears in `moddedcarcontent` field 10 and in both presets, field 1 (section 6) [verified].
- README line 6: "Cars/UI use the current account's active Saved Games/ACE/mods folder. Official stock game assets are required." [verified quote].

## 2. File inventory

| extension | files | bytes | role (label) | class |
|---|---|---|---|---|
| `.actor` | 1 | 12,140 | scene graph: part/node names, lights, sound events, cameras, wheel nodes, references to presets and Kunos assets [verified strings] | visual |
| `.aicardata` | 1 | 1,273 | AI driver data [inferred from name] | physics (AI) |
| `.brakesystem` | 1 | 26 | brake system parameters, 26 B [inferred from name] | physics |
| `.car` | 2 | 16,178 | main car data; embeds engine/drivetrain/gearbox/clutch/brake blocks inline (section 3) [verified] | physics |
| `.caranalogicsystem` | 1 | 398 | analogue gauge needles (e.g. "ARROW_RPM") [verified strings] | visual |
| `.cardesign` | 1 | 118 | links a `.design` to a `.compatiblerim` [verified refs] | visual |
| `.carengine` | 1 | 449 | engine parameters, curve paths, rpm limits | physics |
| `.carexhaustbackfire` | 1 | 62 | backfire thresholds [inferred from name] | visual |
| `.carfinalstate` | 1 | 1,166 | preset combination: points at car data, actor, materials, presets [verified refs] | meta |
| `.carledsystem` | 1 | 1,728 | shift-LED definitions [inferred] | visual |
| `.carlightingsystem` | 1 | 1,015 | light behaviour (e.g. "ON_200ms_200ms") [verified strings] | visual |
| `.carsetup` | 1 | 472 | default setup values | physics |
| `.carsetuplimits` | 1 | 1,729 | setup ranges (step/min/max/enabled) [inferred] | physics |
| `.clutch` | 1 | 4,027 | clutch parameters [inferred from name]; also carries paths of another Kunos car | physics |
| `.coilover` | 2 | 228 | spring/damper block, front and rear [inferred] | physics |
| `.compatiblerim` | 1 | 412 | rim <-> tyre mesh compatibility [verified refs] | visual |
| `.compatibletyres` | 1 | 143 | lists the front/rear `.tyre` files [verified refs] | physics |
| `.css` | 1 | 20,725 | in-car display style | ui |
| `.curve` | 28 | 4,278 | lookup curves: engine, aero, tyre, shift profiles (26 physics) and 2 vfx curves | physics |
| `.design` | 2 | 2,024 | paint / rim design options (colour tables) [inferred] | visual |
| `.drivetrain` | 1 | 398 | diff and gear data, see section 4 | physics |
| `.gearbox` | 1 | 202 | gear ratios and shift data, see section 4 | physics |
| `.graphicsoverride` | 1 | 11 | camera graphics override, 11 B [inferred] | visual |
| `.html` | 1 | 1,973 | in-car display page | ui |
| `.js` | 1 | 1,071 | in-car display script | ui |
| `.less` | 1 | 5,847 | in-car display style source | ui |
| `.loc` | 4 | 1,779 | localization text (en) | ui |
| `.material` | 70 | 1,188,483 | materials, named EXT_/INT_ [verified names]; texture refs point to the Kunos E46 | visual |
| `.mechanicalcarpreset` | 1 | 268 | UI preset: brand id, names, numeric stat entries (read as displayed stats [inferred]), links [verified] | ui / meta |
| `.mesh` | 2 | 7,359 | collider mesh (6,812 B) and a vfx mirror mesh (547 B) | physics (collider [inferred]) / visual |
| `.moddedcarcontent` | 1 | 61 | mod metadata: name, year, brand id [inferred] | meta |
| `.particleemitter` | 1 | 1,126 | smoke puff emitter [inferred from refs] | visual |
| `.png` | 1 | 23,027 | image for the in-car display | ui |
| `.rimmesh` | 2 | 938 | 469 B rim descriptors referencing Kunos rim meshes [verified refs] | visual |
| `.scene` | 1 | 309 | showroom scene: car actor + showroom mesh ref [verified refs] | meta |
| `.suspension` | 3 | 524 | suspension geometry points [inferred] | physics |
| `.texture` | 4 | 243 | texture headers (pair with `.texturemips`) [inferred] | visual / ui |
| `.texturemips` | 4 | 53,280,768 | texture pixel data [inferred]; 53.3 MB of the total | visual / ui |
| `.tyre` | 2 | 1,735 | tyre model (front, rear) | physics |
| `.visualcarpreset` | 1 | 507 | UI/visual preset: names + material colours [verified] | visual / meta |
| `.wing` | 4 | 799 | aero surfaces (BODY, FRONT, REAR, DIFFUSER) [verified names] | physics |
| **total** | **157** | **54,586,019** |  |  |

Largest 12 files [verified sizes]:

| file | bytes | role (label) |
|---|---|---|
| `generated/windshield/bakedpositions.texturemips` | 33,554,432 | baked windshield texture data [inferred from name] |
| `generated/windshield/bakednormals.texturemips` | 16,777,216 | baked windshield texture data [inferred from name] |
| `displays/images/bgr.texturemips` | 1,900,544 | display background texture data [inferred] |
| `generated/thumbnails/hdc_bmw_e46_01-preset_hdc_e46_mech_1-preset_hdc_e46_visual_1.texturemips` | 1,048,576 | generated thumbnail pixel data [inferred] |
| `materials/ext_disc.material` | 29,877 | materials, named EXT_/INT_ (visual) |
| `materials/int_belt.material` | 26,051 | materials, named EXT_/INT_ (visual) |
| `displays/images/bgr.png` | 23,027 | image for the in-car display (ui) |
| `materials/ext_skin.material` | 21,755 | materials, named EXT_/INT_ (visual) |
| `materials/ext_skin_2.material` | 21,583 | materials, named EXT_/INT_ (visual) |
| `materials/int_display.material` | 21,190 | materials, named EXT_/INT_ (visual) |
| `displays/display.css` | 20,725 | in-car display style (ui) |
| `materials/ext_mech_base.material` | 19,933 | materials, named EXT_/INT_ (visual) |

## 3. How the files connect

Method [verified]: `tools/refgraph.py` scans every file as raw bytes for strings starting with `content\` and classifies them as inside this car (`ok`) or external. It does not see relative paths (for example `../../common_assets/...` in `displays/display.html`) nor material names used as plain strings (for example `INT_DECALS` in the actor). So "referenced by `none`" means no `content\` path string anywhere, not "unused".

Chain from the entry point (every edge below was asserted against the refgraph data by the generating script) [verified]:

```
presets/..._preset_hdc_e46_mech_1_preset_hdc_e46_visual_1.carfinalstate      (entry point [inferred])
  +-- data/CarData.car  (string "CarData.car"; the file is data/cardata.car)
  |     +-- engine .carengine --> power_1.curve, engine_coast_1.curve, throttle_response_1.curve
  |     +-- drivetrain, gearbox, clutch, brakesystem, aicardata        (blocks also embedded inline)
  |     +-- setup/hdc_bmw_e46_01.carsetup, setup/limits_m3_e46.carsetuplimits
  |     +-- 2 x .tyre --> temperature / wear curves
  |     +-- 2 x .coilover, 2 x .suspension, wings e460..e462 --> data/aero/*.curve
  |     +-- collider/bmw_m3_e46_csl_collider.mesh
  |     +-- (also strings naming ks_alfa_romeo_giulia_gtam files: external)
  +-- hdc_bmw_e46_01.actor
  |     +-- displays/display.html, materials/int_display.material
  |     +-- instruments/* (4), camera/hdc_gopro.graphicsoverride, vfx/hdc13/main_puff.particleemitter
  |     +-- presets (mech, visual), skins/rim_e46csl.compatiblerim, skins/design_e46csl_1.cardesign
  |     +-- external: ks_bmw_m3_e46_csl meshes/animations, ks_audi_rs_6_avant animations, sfx *.bank, common_assets
  +-- presets/preset_hdc_e46_mech_1.mechanicalcarpreset --> visualcarpreset, compatiblerim
  +-- presets/preset_hdc_e46_visual_1.visualcarpreset --> cardesign, rimdesign.design, EXT_SKIN / EXT_RIM materials
  +-- skins: cardesign --> design_e46csl_1.design --> EXT_SKIN, INT_ELEC_CARPAINT materials
            compatiblerim --> compatibletyres (--> 2 .tyre), 2 x .rimmesh --> rimdesign_e46csl.design --> rim materials
hdc_bmw_e46_01.scene --> actor + external showroom_arctic mesh;  hdc_bmw_e46_01.car: same refs as cardata.car, referenced by nobody
```

The entry point role of the `carfinalstate` is [inferred]: it is the only file that names both `CarData.car` and the actor, and nothing refers to it [verified]. Materials are mostly looked up by name (the actor holds names such as `EXT_LIGHTS_CHROME`, `INT_DECALS`), not by path [verified strings, mechanism inferred]. `moddedcarcontent`, `.loc` files, `generated/*`, `displays/*` (except `display.html`) and 64 of 70 materials have no `content\` referrer [verified].

**`data/cardata.car` blocks vs separate files** [verified by byte comparison; `docs/drift-deltas.md` section 1 reaches the same result]:

| cardata field | payload | byte-identical to | path field |
|---|---|---|---|
| `3` | 398 B message | `data/ks_bmw_m3_e46_1.drivetrain` | `22` -> same file |
| `4` | 449 B message | `data/ks_bmw_m3_e46_engine_1.carengine` | `20` -> same file |
| `5` | 26 B message | `data/ks_bmw_m3_e46_1.brakesystem` | `27` -> same file |
| `23` | 202 B message | `data/ks_bmw_m3_e46_1.gearbox` | `24` -> same file |
| `25` | 4,027 B message | `data/ks_bmw_m3_e46_1.clutch` | `26` -> same file |
| `2.8` | sub-message | `data/ks_bmw_m3_e46_front_1.coilover` | no path field; nested copy |
| `2.9` | sub-message | `data/ks_bmw_m3_e46_rear_1.coilover` | no path field; nested copy |
| `2.40` | sub-message | `data/ks_bmw_m3_e46_front_sus_1.suspension` | no path field; nested copy |
| `2.41` | sub-message | `data/ks_bmw_m3_e46_rear_sus_m2.suspension` | no path field; nested copy |
| `12.3` | sub-message | `data/wings/ks_bmw_m3_e460.wing` | no path field; nested copy |
| `12.3[1]` | sub-message | `data/wings/ks_bmw_m3_e461.wing` | no path field; nested copy |
| `12.3[2]` | sub-message | `data/wings/ks_bmw_m3_e462.wing` | no path field; nested copy |

Other `cardata.car` top-level fields [verified]: message blocks without a separate file: `1`, `6`, `7`, `8`, `18`, `30` (`1.1` is read as mass by the lever `mass_kg` [inferred], `1.2` holds the car name [verified string]; `8` is discussed in `docs/tuning-levers.md` 3f). String fields: `10` -> `data/tyres/hdc_235_35_19_front.tyre`; `11` -> `data/tyres/hdc_265_30_19_rear.tyre`; `16` -> `data/setup/limits_m3_e46.carsetuplimits`; `19` -> `data/setup/hdc_bmw_e46_01.carsetup`; `20` -> `data/ks_bmw_m3_e46_engine_1.carengine`; `21` -> `collider/bmw_m3_e46_csl_collider.mesh`; `22` -> `data/ks_bmw_m3_e46_1.drivetrain`; `24` -> `data/ks_bmw_m3_e46_1.gearbox`; `26` -> `data/ks_bmw_m3_e46_1.clutch`; `27` -> `data/ks_bmw_m3_e46_1.brakesystem`; `29` -> `data/ks_bmw_m3_e46_1.aicardata`; `190` -> `data/setup/hdc_bmw_e46_01.carsetup`; `202` -> `Hina's Drift Club - BMW M3 CSL`.
`data/hdc_bmw_e46_01.car` is 8089 B like `cardata.car` and differs in exactly 3 bytes (offsets 2170-2172), which is leaf `8.4` ((f32) 0.00260000001 vs (f32) 0.00249999994) [verified]. No file refers to it [verified]; whether the game reads it is [unknown].

**Per-file reference table** (refgraph; groups aggregate their files and sum their counts; "referenced by" lists up to 3 file names, `none` = no `content\` string anywhere; ext = external refs):

| file | referenced by | references (counts) | external targets (refs per group) |
|---|---|---|---|
| `presets/...carfinalstate` | `none` | ok 11, ext 2 | common_assets 2 |
| `presets/preset_hdc_e46_mech_1.mechanicalcarpreset` | `*.carfinalstate`, `hdc_bmw_e46_01.actor` | ok 2, ext 0 | - |
| `presets/preset_hdc_e46_visual_1.visualcarpreset` | `*.carfinalstate`, `hdc_bmw_e46_01.actor`, `preset_hdc_e46_mech_1.mechanicalcarpreset` | ok 4, ext 2 | common_assets 2 |
| `presets/tyres_e46csl.compatibletyres` | `rim_e46csl.compatiblerim` | ok 2, ext 0 | - |
| `hdc_bmw_e46_01.actor` | `*.carfinalstate`, `hdc_bmw_e46_01.scene` | ok 12, ext 70 | common_assets 10, ks_audi_rs_6_avant 17, ks_bmw_m3_e46_csl 31, sfx banks 12 |
| `hdc_bmw_e46_01.scene` | `none` | ok 1, ext 1 | common_assets 1 |
| `hdc_bmw_e46_01.moddedcarcontent` | `none` | ok 0, ext 0 | - |
| `data/cardata.car` | `*.carfinalstate` | ok 30, ext 30 | ks_alfa_romeo_giulia_gtam 30 |
| `data/hdc_bmw_e46_01.car` | `none` | ok 30, ext 30 | ks_alfa_romeo_giulia_gtam 30 |
| `data/ks_bmw_m3_e46_1.drivetrain` | `cardata.car`, `hdc_bmw_e46_01.car` | ok 0, ext 2 | ks_alfa_romeo_giulia_gtam 2 |
| `data/ks_bmw_m3_e46_1.gearbox` | `cardata.car`, `hdc_bmw_e46_01.car` | ok 1, ext 0 | - |
| `data/ks_bmw_m3_e46_1.clutch` | `cardata.car`, `hdc_bmw_e46_01.car` | ok 2, ext 30 | ks_alfa_romeo_giulia_gtam 30 |
| `data/ks_bmw_m3_e46_engine_1.carengine` | `cardata.car`, `hdc_bmw_e46_01.car` | ok 3, ext 0 | - |
| `.brakesystem`, `.aicardata` | `cardata.car`, `hdc_bmw_e46_01.car` | ok 0, ext 0 | - |
| `data/setup/*` (carsetup, limits) | `cardata.car`, `hdc_bmw_e46_01.car` | ok 0, ext 0 | - |
| `data/tyres/*.tyre` (2) | `cardata.car`, `hdc_bmw_e46_01.car`, `tyres_e46csl.compatibletyres` | ok 4, ext 0 | - |
| `data/tyres/*.curve` (3) | `hdc_235_35_19_front.tyre`, `hdc_265_30_19_rear.tyre` | ok 0, ext 0 | - |
| coilover x2, suspension x3 | `cardata.car`, `hdc_bmw_e46_01.car` | ok 0, ext 0 | - |
| `data/wings/ks_bmw_m3_e46[0-2].wing` | `cardata.car`, `hdc_bmw_e46_01.car` | ok 6, ext 0 | - |
| `data/wings/ks_bmw_m3_e463.wing` | `none` | ok 0, ext 2 | ks_bmw_m4_csl 2 |
| `data/aero/*.curve` (6) | `cardata.car`, `hdc_bmw_e46_01.car`, `ks_bmw_m3_e460.wing` +2 | ok 0, ext 0 | - |
| `data/wings/*.curve` (9) | `none` | ok 0, ext 0 | - |
| other `data/*.curve` (engine, coast, throttle, shift and blip profiles: 8) | `cardata.car`, `hdc_bmw_e46_01.car`, `ks_bmw_m3_e46_1.clutch` +2 | ok 0, ext 0 | - |
| `collider/*.mesh` | `cardata.car`, `hdc_bmw_e46_01.car` | ok 0, ext 0 | - |
| `skins/*.design`, `.cardesign` (3) | `*.carfinalstate`, `hdc_bmw_e46_01.actor`, `preset_hdc_e46_visual_1.visualcarpreset` +2 | ok 7, ext 6 | common_assets 4, ks_lamborghini_huracan_sto 2 |
| `skins/*.compatiblerim`, `.rimmesh` (3) | `*.carfinalstate`, `design_e46csl_1.cardesign`, `hdc_bmw_e46_01.actor` +1 | ok 5, ext 12 | common_assets 4, ks_bmw_m3_e46_csl 8 |
| `instruments/*` (4), `camera/*` (1) | `hdc_bmw_e46_01.actor` | ok 0, ext 0 | - |
| `vfx/hdc13/*` (4) | `hdc_bmw_e46_01.actor` | ok 3, ext 7 | particles/smoke 7 |
| 6 materials referenced by path | `*.carfinalstate`, `design_e46csl_1.design`, `hdc_bmw_e46_01.actor` +2 | ok 0, ext 28 | common_assets 13, ks_bmw_m3_e46_csl 15 |
| 64 other materials | `none` | ok 0, ext 364 | common_assets 230, ks_abarth_695_biposto 1, ks_bmw_m3_e30_evo_iii 1, ks_bmw_m3_e46_csl 132 |
| `displays/*` (7) | `hdc_bmw_e46_01.actor` | ok 0, ext 0 | - |
| `generated/*` (6) | `none` | ok 0, ext 0 | - |
| `uiresources/localization/*.loc` (4) | `none` | ok 0, ext 0 | - |

**References into the installed game** (refgraph lists 21 groups; its 12 `content\sfx\*.bank` entries are one row here) [verified]:

| external group (first path segments) | distinct refs | files using them |
|---|---|---|
| `common_assets` | 106 | 72 |
| `ks_bmw_m3_e46_csl` | 99 | 67 |
| `ks_alfa_romeo_giulia_gtam` | 30 | 4 |
| `ks_audi_rs_6_avant` | 17 | 1 |
| `sfx banks` | 12 | 1 |
| `particles/smoke` | 7 | 2 |
| `ks_bmw_m4_csl` | 2 | 1 |
| `ks_abarth_695_biposto` | 1 | 1 |
| `ks_bmw_m3_e30_evo_iii` | 1 | 1 |
| `ks_lamborghini_huracan_sto` | 1 | 2 |

Group counts: `ks_bmw_m3_e46_csl` 99 refs in 67 files; `common_assets` 106 refs in 72 files; `content\sfx\*.bank` 12 refs (one file: the actor); `content\particles\smoke` 7 refs in 2 files [verified]. The remaining 52 refs name files of six other Kunos cars (Alfa Giulia GTAm via `cardata.car`, `hdc_bmw_e46_01.car`, clutch, drivetrain; Audi RS 6 animations via the actor; single refs to Abarth 695, E30 Evo III, M4 CSL, Huracan STO) [verified].
Implication [inferred]: the package ships no body, interior or wheel mesh (see 5a); it names the installed game's Kunos E46 CSL assets by path, so the mod needs the game's own content installed (README: "Official stock game assets are required" [verified quote]). Whether the leftover Alfa/Audi/other-car paths are ever opened at run time is [unknown].

## 4. Which files are physics

Everything under `data/` (47 files) plus `collider/` (1 file) is the physics-related set [inferred from folder and extensions; the game's own use of each file is [unknown]]. Meanings below are only those in `HANDOVER.md` section 7 and `docs/drift-deltas.md`, all [inferred] unless marked; schemas are not available, so unlisted field numbers are [unknown].

| file(s) | role | field numbers known so far |
|---|---|---|
| `data/cardata.car`, `data/hdc_bmw_e46_01.car` (2) | aggregate car data: inline copies of drivetrain `3`, engine `4`, brakes `5`, gearbox `23`, clutch `25`, plus blocks `1 2 6 7 8 12 18 30` and path fields (section 3) | `1.1` = (f32) 1495 read as mass [inferred]; `1.2` car name; `3.39.1-3` diff, `3.11`, `4.6`, `4.15`, `23.3` copies of the part-file values; `8.2` / `8.3` see tuning-levers 3f; the rest [unknown] |
| `data/ks_bmw_m3_e46_engine_1.carengine` | engine | `5` = 700 idle rpm, `6` = 8100 limiter rpm, `15` = (f32) 8100 (same number), `2` / `3` power / coast curve path, `4.3` and `14` throttle-response curve path; rest (`1 4.x 7 8 19 20 27 40 41 63`) [unknown] |
| `data/bmw_m3_e46_coupe_engine_power_1.curve` (+ `engine_power.curve`, coast, throttle response x2: 5 files) | torque / lookup curves | repeated `1` = point {`1` rpm f32, `10` torque Nm f32}; the used power curve has 22 points (21 carry field `10`), peak 377.878 at 5000 rpm [verified computation, meaning inferred]; coast / throttle curve axes [unknown] |
| `data/ks_bmw_m3_e46_1.drivetrain` | diff + gear ratios | `39.1` / `39.2` / `39.3` diff power / coast / preload Nm; `9` gear count; repeated `10` = {`1` name, `2` ratio}; `11` final?; `39.4`, `39.11`, `39.12`, `4`, `12-14`, `17-28`, `46`, `47`, `102-104` [unknown] |
| `data/ks_bmw_m3_e46_1.gearbox` | gear ratios + shift data | `1` gear count; repeated `2` = {`1` name, `2` ratio}; `3` final drive; `13.1` auto-shift rpm?; rest [unknown]. Ratios differ from the drivetrain's (tuning-levers 3b) |
| `data/ks_bmw_m3_e46_1.clutch`, `.brakesystem`, `.aicardata` (3) | clutch, brakes, AI | all field meanings [unknown] |
| `data/setup/hdc_bmw_e46_01.carsetup` | default setup | `1.2` steer ratio?, `1.3.1` / `1.3.2` brake bias % / power %, `1.4.1-3` diff, `2[i].1` spring N/m, `3[i]` dampers, `4[i].1-3` pressure psi / camber / toe, `7.1` fuel L?; `9` preset id string [verified] |
| `data/setup/limits_m3_e46.carsetuplimits` | setup ranges | range = {`1` step, `2` min, `3` max, `4` enabled}; same top-level numbering as the setup (`1.2`, `1.3`, `1.4`, `2`, `3`, `4`) |
| `data/tyres/*.tyre` (2) + 3 curves | front / rear tyre model | `1` name string, `12.1` width mm (matches the file name) [verified]; all other groups [unknown] (tuning-levers 3c) |
| `data/ks_bmw_m3_e46_{front,rear}_1.coilover` (2), `*.suspension` (3) | springs / dampers, suspension points | all [unknown] |
| `data/wings/*.wing` (4) + 9 curves, `data/aero/*.curve` (6) | aero surfaces BODY / FRONT / REAR / DIFFUSER and their lift/drag curves [inferred from names] | all numeric fields [unknown] |
| `data/{autoblip,upshift,downshift}profile.curve` (3) and the other 5 top-level `data/*.curve` | shift / blip profiles, engine curves | [unknown] beyond the engine curves above |
| `collider/bmw_m3_e46_csl_collider.mesh` | collision mesh [inferred] | path in `cardata.car` field `21` |

Data files that no `content\` string points to (refgraph) [verified, 14 of 47]: `bmw_m3_e46_coupe_engine_power.curve`, `bmw_m3_e46_coupe_throttle_response.curve`, `hdc_bmw_e46_01.car`, `ks_bmw_m3_e46_rear_sus_1.suspension`, `wings/ks_bmw_m3_e463.wing`, and the 9 curves in `data/wings/`. Whether the game ignores them is [unknown]. Which copy of a duplicated value the game reads (part file, inline block in `cardata.car`, or `hdc_bmw_e46_01.car`) is [unknown] (HANDOVER section 10; tests in `docs/pc-test-protocol.md`).

## 5. Removal candidates for the owner's cleanup request

Facts only; nothing here recommends or decides a removal. "Referenced by" = refgraph (a `content\` path string in another file); "references" = what the file itself names (ok = inside this car, ext = external, per group); `none` = no such string.

### a) Model / mesh files

| file | bytes | referenced by | references | note |
|---|---|---|---|---|
| `collider/bmw_m3_e46_csl_collider.mesh` | 6,812 | `cardata.car`, `hdc_bmw_e46_01.car` | `none` | referenced by `cardata.car` / `hdc_bmw_e46_01.car` field `21`; collision geometry [inferred from folder name] |
| `vfx/hdc13/main_puff_mirrors.mesh` | 547 | `main_puff.particleemitter` | ext: particles/smoke 1 | mesh named by the smoke-puff emitter (`6`); purpose [inferred] |
| `skins/rim_e46csl_8.5jx18.rimmesh` | 469 | `rim_e46csl.compatiblerim` | ok: `rimdesign_e46csl.design`; ext: common_assets 1, ks_bmw_m3_e46_csl 4 | 469 B descriptor, not geometry itself [verified]: names 4 Kunos rim meshes + a tyre mesh + `rimdesign_e46csl.design` |
| `skins/rim_e46csl_9.5jx19.rimmesh` | 469 | `rim_e46csl.compatiblerim` | ok: `rimdesign_e46csl.design`; ext: common_assets 1, ks_bmw_m3_e46_csl 4 | same structure, rear rims [inferred from name] |

Total a): 4 files, 8,297 bytes [verified]. No other geometry file identified (`.texturemips` is pixel data [inferred]). The car body, interior, belts, wheels and animations are not in the package: the actor names 15 external `.mesh` files (for example `ks_bmw_m3_e46_csl\meshes\bmw_m3_e46_csl_exterior.mesh`, `..._interior.mesh`, 4 rim and 4 rim-blur meshes, 2 belt meshes, a plate mesh, 2 tyre meshes), the scene names one showroom mesh, and `cardata.car` names the Alfa Giulia collider mesh [verified refs].

### b) Windshield texture

| file | bytes | referenced by | references | note |
|---|---|---|---|---|
| `generated/windshield/bakednormals.texture` | 12 | `none` | `none` | name only (`bakednormals` / `bakedpositions`, meaning [inferred]); each is a header + `.texturemips` data pair [inferred] |
| `generated/windshield/bakednormals.texturemips` | 16,777,216 | `none` | `none` | pair partner |
| `generated/windshield/bakedpositions.texture` | 12 | `none` | `none` | pair partner |
| `generated/windshield/bakedpositions.texturemips` | 33,554,432 | `none` | `none` | pair partner |
| `materials/int_windshield.material` | 10,074 | `none` | ext: common_assets 5, ks_bmw_m3_e30_evo_iii 1, ks_bmw_m3_e46_csl 2 | material (shader property `VehicleWindshield`, refs Kunos dirt/wet textures); the only other file with windshield/baked in its name [verified] |

Total b): `generated/windshield/` 4 files 50,331,672 bytes; with the material 5 files 50,341,746 bytes [verified]. Also: the shader property `IsWindshield` appears inside `ext_lights_glass`, `ext_windows`, `int_windows` and `int_windshield` materials (not file references) [verified].

### c) Stickers / decals / designs

No file name contains `sticker` or `livery`; 4 contain `decal` [verified]. `skins/` holds 3 design files plus 3 other files (`compatiblerim`, 2 `rimmesh`, listed in a/section 3).

| file | bytes | referenced by | references | note |
|---|---|---|---|---|
| `materials/ext_decals.material` | 19,100 | `none` | ext: common_assets 2, ks_bmw_m3_e46_csl 8 | material; its textures are external game files (`ks_bmw_m3_e46_csl` / `common_assets`), none inside the package [verified] |
| `materials/ext_rim_decal.material` | 18,953 | `none` | ext: common_assets 1, ks_bmw_m3_e46_csl 4 | material; its textures are external game files (`ks_bmw_m3_e46_csl` / `common_assets`), none inside the package [verified] |
| `materials/ext_rim_decal_blur.material` | 18,953 | `none` | ext: common_assets 1, ks_bmw_m3_e46_csl 4 | material; its textures are external game files (`ks_bmw_m3_e46_csl` / `common_assets`), none inside the package [verified] |
| `materials/int_decals.material` | 18,225 | `none` | ext: common_assets 4, ks_bmw_m3_e46_csl 11 | material; its textures are external game files (`ks_bmw_m3_e46_csl` / `common_assets`), none inside the package [verified]; the actor holds the string `INT_DECALS` (103.26.1) [verified] |
| `skins/design_e46csl_1.cardesign` | 118 | `hdc_bmw_e46_01.actor`, `preset_hdc_e46_visual_1.visualcarpreset` | ok: `design_e46csl_1.design`, `rim_e46csl.compatiblerim` | links a `.design` to a `.compatiblerim` [verified refs] |
| `skins/design_e46csl_1.design` | 841 | `design_e46csl_1.cardesign` | ok: `ext_skin.material`, `int_elec_carpaint.material`; ext: common_assets 3, ks_lamborghini_huracan_sto 1 | design colour options [inferred]; refs `ks_lamborghini_huracan_sto\skins\colouroem_sto.table` [verified] |
| `skins/rimdesign_e46csl.design` | 1,183 | `*.carfinalstate`, `preset_hdc_e46_visual_1.visualcarpreset`, `rim_e46csl_8.5jx18.rimmesh` +1 | ok: `ext_rim.material`, `ext_rim_blur.material`, `ext_rim_blur_static.material`; ext: common_assets 1, ks_lamborghini_huracan_sto 1 | design colour options [inferred]; refs `ks_lamborghini_huracan_sto\skins\colouroem_sto.table` [verified] |

Total c): decal materials 4 files 75,231 bytes; designs 3 files 2,142 bytes; together 7 files 77,373 bytes [verified]. Material file stems containing `decal`: `ext_decals`, `ext_rim_decal`, `ext_rim_decal_blur`, `int_decals`; the actor and presets refer to materials by upper-case stem names such as `INT_DECALS` [verified for `INT_DECALS`; the other three names are inferred].

### d) displays/ (in-car dashboard UI)

| file | bytes | referenced by | references | note |
|---|---|---|---|---|
| `displays/display.css` | 20,725 | `none` | `none` | refers to `images/bgr.texture` by relative url |
| `displays/display.html` | 1,973 | `hdc_bmw_e46_01.actor` | `none` | referenced by the actor (ok ref); links css/js by relative path |
| `displays/display.js` | 1,071 | `none` | `none` |  |
| `displays/display.less` | 5,847 | `none` | `none` |  |
| `displays/images/bgr.png` | 23,027 | `none` | `none` |  |
| `displays/images/bgr.texture` | 135 | `none` | `none` | relative url in `display.css` |
| `displays/images/bgr.texturemips` | 1,900,544 | `none` | `none` |  |

Total d): 7 files, 1,953,322 bytes [verified]. `materials/int_display.material` (21,190 B, referenced by the actor) is not in `displays/` and is not counted here.

### What I could not determine

Whether removing a group breaks loading is [unknown] in every case; it needs the game. Files that refer to the candidates (what would dangle) [verified from refgraph]:

| group | what refers to it / what is unknown |
|---|---|
| a) meshes | `cardata.car` and `hdc_bmw_e46_01.car` (field `21` -> collider); `main_puff.particleemitter` (-> `main_puff_mirrors.mesh`); `rim_e46csl.compatiblerim` (-> both `.rimmesh`). The actor and rim descriptors also name external Kunos meshes that are not in the package. |
| b) windshield | no file refers to `generated/windshield/*` or to `int_windshield.material` by path. Who reads the baked textures (game by folder convention? [unknown]) and whether the actor selects the material by name [unknown]. |
| c) decals / designs | decal materials: no path referrer; the actor names `INT_DECALS` as a string. Designs: `design_e46csl_1.cardesign` <- actor, `...carfinalstate`, `preset_hdc_e46_visual_1.visualcarpreset`; `design_e46csl_1.design` <- `design_e46csl_1.cardesign`; `rimdesign_e46csl.design` <- `...carfinalstate`, visual preset, both `.rimmesh`. |
| d) displays | `hdc_bmw_e46_01.actor` -> `displays/display.html`; the actor also -> `materials/int_display.material`. Inside `displays/`: html -> css/js, css -> `bgr.texture` (relative paths, invisible to refgraph). |

Not in a)-d) but large and visual [verified]: `materials/` 70 files 1,188,483 bytes (6 referenced by path, 64 by `none`), `generated/thumbnails/` 2 files 1,048,660 bytes (no referrer).

## 6. Hina's Drift Club references

Method [verified]: all 157 files were searched case-insensitively for the byte strings `hina`, `hdc` and `drift club`. Protobuf-parseable files were walked recursively with `pbedit.parse` (string and bytes leaves; a printable string that is really a nested message, as in actor field `103.13`, was descended into); the 3 text files with hits were searched line by line; non-parseable files were searched as raw bytes. Result: 211 raw matches in 28 files = 190 inside protobuf leaves (152 leaf strings) + 21 in `.loc` text; per-file raw count equals leaf count for all 25 protobuf files; unclassified raw hits: 0. No hit in the 5 non-protobuf non-text files (`bgr.png` and 4 `.texturemips`), in `display.*`, or in UTF-16 form (checked). No file or folder name contains `hina`.

### (i) Ids, paths, folder and file names (summary by pattern; counts = leaf strings carrying the pattern, a leaf can carry several)

| pattern | leaf strings (names: files) | files | status |
|---|---|---|---|
| the id `hdc_bmw_e46_01` in `content\cars\hdc_bmw_e46_01\...` path strings (and the id inside the preset id) | 137 | 24 | keep for now |
| preset ids `preset_hdc_e46_mech_1`, `preset_hdc_e46_visual_1` in paths | 6 | 4 | keep for now |
| tyre files `hdc_235_35_19_front.tyre`, `hdc_265_30_19_rear.tyre` | 6 | 3 | keep for now |
| curves `hdc_temperature_front/rear.curve`, `hdc_wear.curve` | 4 | 2 | keep for now |
| folder `vfx/hdc13/` | 5 | 2 | keep for now |
| file `camera/hdc_gopro.graphicsoverride` | 1 | 1 | keep for now |
| preset-combination id string `hdc_bmw_e46_01_preset_hdc_e46_mech_1_preset_hdc_e46_visual_1` (`data/setup/hdc_bmw_e46_01.carsetup` field `9`; equals the `.carfinalstate` file name stem) | 1 | 1 | keep for now |
| file names containing `hdc` (basename; includes the car-id root files, tyre files, presets, instruments, thumbnails, `hdc_gopro`) and folder(s) `hdc13` (4 files inside) | 21 | 21 | keep for now |

These are 137 of the 152 matching leaf strings (every one starts with `content\cars\hdc_bmw_e46_01\`, except the preset id string and the actor's embedded path list); they contain `hdc` only, never `hina`. The `.loc` key prefix `hdc_bmw_e46_01_` is in table (ii). The owner's plan is to keep ids, variable and folder names unchanged for now (project context).

### (ii) Human-visible strings and branding

Protobuf leaves (columns `file` and `pbedit path`; re-readable with `python3 -I tools/pbedit.py get <car_root>/<file> <path>`):

| file | pbedit path | exact string | what it probably is |
|---|---|---|---|
| `data/cardata.car` | `1.2` | `"Hina's Drift Club - BMW M3 CSL"` | car display name [inferred] |
| `data/cardata.car` | `30.11` | `"HDC Drift"` | name/tag inside block `30` (33 B), purpose [unknown] |
| `data/cardata.car` | `202` | `"Hina's Drift Club - BMW M3 CSL"` | car display name, second copy [inferred] |
| `data/hdc_bmw_e46_01.car` | `1.2` | `"Hina's Drift Club - BMW M3 CSL"` | car display name (devcopy) [inferred] |
| `data/hdc_bmw_e46_01.car` | `30.11` | `"HDC Drift"` | name/tag inside block `30` (devcopy), purpose [unknown] |
| `data/hdc_bmw_e46_01.car` | `202` | `"Hina's Drift Club - BMW M3 CSL"` | car display name, second copy (devcopy) [inferred] |
| `data/tyres/hdc_235_35_19_front.tyre` | `1` | `"Hina's Drifters E46"` | tyre name shown in the UI [inferred] |
| `data/tyres/hdc_265_30_19_rear.tyre` | `1` | `"Hina's Drifters E46"` | tyre name shown in the UI [inferred] |
| `hdc_bmw_e46_01.moddedcarcontent` | `4` | `"Hina's Drift Club - BMW M3 CSL"` | mod / car name [inferred] |
| `hdc_bmw_e46_01.moddedcarcontent` | `10` | `"hina_drift_club"` | brand id = folder `uiresources/branding/oem/hina_drift_club` [inferred] |
| `presets/preset_hdc_e46_mech_1.mechanicalcarpreset` | `1` | `"hina_drift_club"` | brand id [inferred] |
| `presets/preset_hdc_e46_mech_1.mechanicalcarpreset` | `2` | `"HDC - NA"` | preset short name; loc key `hdc_bmw_e46_01_hdc_na` has the same text [inferred] |
| `presets/preset_hdc_e46_mech_1.mechanicalcarpreset` | `3` | `"HDC E46 Drift Setup"` | mechanical preset name; loc key `hdc_bmw_e46_01_hdc_e46_drift_setup` has the same text [inferred] |
| `presets/preset_hdc_e46_visual_1.visualcarpreset` | `1` | `"hina_drift_club"` | brand id [inferred] |
| `presets/preset_hdc_e46_visual_1.visualcarpreset` | `2` | `"HDC"` | visual preset name; loc key `hdc_bmw_e46_01_hdc` has the same text [inferred] |

Text files (column `line` = 1-based line number; `exact string` = the whole line for `en.cars.loc`, else the matching phrases):

| file | line | exact string | what it probably is |
|---|---|---|---|
| `uiresources/localization/en.cars.loc` | 1 | `brand_hina_drift_club=Hina's Drift Club` | brand display name; key = `brand_` + brand id [inferred] |
| `uiresources/localization/en.cars.loc` | 2 | `hdc_bmw_e46_01_hdc_e46_drift_setup=HDC E46 Drift Setup` | mechanical preset name (= mechanicalcarpreset `3`) [inferred] |
| `uiresources/localization/en.cars.loc` | 3 | `hdc_bmw_e46_01_hdc_csl=HDC CSL` | concatenation of visual preset names `2` + `3` ("HDC" + "CSL") [inferred] |
| `uiresources/localization/en.cars.loc` | 4 | `hdc_bmw_e46_01_csl=CSL` | visual preset name (= visualcarpreset `3`, contains no Hina/HDC string; its key does) [inferred] |
| `uiresources/localization/en.cars.loc` | 5 | `hdc_bmw_e46_01_hdc_na=HDC - NA` | preset short name (= mechanicalcarpreset `2`) [inferred] |
| `uiresources/localization/en.cars.loc` | 6 | `hdc_bmw_e46_01_hdc=HDC` | visual preset name (= visualcarpreset `2`) [inferred] |
| `uiresources/localization/en.loc` | 1 | `Hina's Drift Club` | car description text (UI) [inferred] |
| `uiresources/localization/en.loc` | 3 | `Hina's Drifters E46` + `HDC` | car description text (UI) [inferred] |
| `uiresources/localization/preset_hdc_e46_mech_1.en.loc` | 1 | `Hina's Drifters E46` | description text of the mechanical preset (UI) [inferred] |

Match accounting [verified]: protobuf leaves 190 + text 21 = 211 raw matches. `uiresources/localization/setup.en.loc` has no match. The same three `.loc` texts are shipped loose by the installer (section 1) and would need the same edit there.

Branding outside the 157 files [verified]: folder `uiresources/branding/oem/hina_drift_club/` with `badge.texture` 247 B, `badge.texturemips` 6,029,312 B, `logo.texture` 73 B, `logo.texturemips` 524,288 B; the brand id also appears as `moddedcarcontent` `10` and preset `1` fields (rows above). What the textures show is not described here.

## 7. Open questions

| # | question | answered by |
|---|---|---|
| 1 | Which copy of a duplicated value does the game read: part file, inline block in `data/cardata.car`, or `data/hdc_bmw_e46_01.car`? | in-game variants B1, B2, D of `docs/pc-test-protocol.md` |
| 2 | Is `data/hdc_bmw_e46_01.car` read at all (no referrer, differs from `cardata.car` only in leaf `8.4`)? | same variants; schema of the `.car` message |
| 3 | Can the candidates in section 5 a)-d) be removed without breaking loading (collider, windshield bake, decal materials, designs, displays)? | one in-game test per group on a copy of the package; nothing has been tested |
| 4 | What reads `generated/windshield/*` and `generated/thumbnails/*` (no `content\` referrer), and are they regenerated when missing? | in-game test with the files absent; game exe / schemas |
| 5 | How are materials bound to the model: by name from the actor (strings such as `INT_DECALS`) or otherwise? | actor schema (`.actor` message) and a removal test |
| 6 | Are the leftover paths of other Kunos cars (Alfa Giulia in clutch / drivetrain / `.car`, Audi RS 6 animations, Huracan colour table, M4 CSL diffuser curves) ever opened? | game log during load; removal test; schemas |
| 7 | Which loc text wins in the UI: the in-package `uiresources/localization/*.loc` or the loose copies under `mods/uiresources/localization/cars/hdc_bmw_e46_01/`? | in-game test changing one copy only |
| 8 | Which strings must change together to rename the car in the UI (`cardata.car` `1.2` / `202`, `moddedcarcontent` `4`, tyre names, preset names with their `.loc` keys)? | in-game test after editing all copies; schemas |
| 9 | What do the unlabelled physics fields mean (clutch, brakes, tyre groups, coilover, suspension, wings, aicardata)? | schemas from the game executable (`HANDOVER.md` section 6) |
| 10 | Does the game validate package contents, and do loose folders under `mods/content/cars/<id>` load? | variants A, B1 and F of `docs/pc-test-protocol.md` |
