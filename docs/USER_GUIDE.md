# ACE - Simple Car Tuner: user guide

How to install and use the tuner step by step, with all the details. The short overview is in the [README](README.md).

Change the driving settings of a car in a simple table, install your own tuned copy next to the stock one, drive a lap, close the game, change again. About 136-142 settings per car: engine, turbo, gearbox and clutch, differential (setup and hardware), steering, brakes, springs, dampers, anti-roll bars, ride height and bump stops, alignment, tyres, driver aids, fuel. No cosmetics.

The selector lists all 71 cars of the game. A tuned copy of a car is a **modded car** (steps 3 and 4 of "Every time you tune"). The stock cars are never changed.

## What you need

- Windows PC with **Assetto Corsa EVO** and the **Assetto Corsa EVO SDK** installed through Steam (both fully downloaded).
- **Python 3.12** from python.org, installed for the current user (the start file looks in `%LOCALAPPDATA%\Programs\Python\Python312\`).
- This repository (clone or download it).

## One-time setup

1. Open a terminal in the repository folder and extract the car data field names from the SDK (they belong to the game vendor, so they stay on your PC and are not part of this repository):
   ```
   python tools\extract_protos.py "C:\Program Files (x86)\Steam\steamapps\common\Assetto Corsa EVO SDK\AssettoCorsaEVOEditor.exe" schemas
   ```
2. Double-click **`start_tuner.bat`** in the repository root (the top folder, next to `docs`, `tools` and `tuner`). A console window opens and your browser shows the tuner (dark theme) at http://127.0.0.1:8080/ACESCT/ . The console also prints the address for other devices in your home network, for example `http://192.168.1.20:8080/ACESCT/`: open that on your phone or tablet (same Wi-Fi). The first time, Windows asks whether Python may use the private network: choose **Allow**. Only devices in your home network (addresses like 192.168.x.x or 10.x.x.x) are let in, there is no password, so use it on a network you trust. On an iPhone open the address in Safari, tap Share and **Add to Home Screen**: the page then starts like an app with its own icon (a rev counter). Keep the console window open while you use it. (After updating the repository, close that window and start it again.)
3. Pick a car in the selector at the top. Its groups, top to bottom, are **Modded Cars** (entries like `BMW M3 E46 CSL_MY - installed`), **Installed Cars** (the car's game files were pulled) and **Other Cars** (not pulled yet). The first time you pick a car from Other Cars, press **Install car (pull game files)** (about 20 seconds). This copies that car's data and its shared tyre files out of the game into `%USERPROFILE%\ace_modded_cars_work\<car id>`. Every car of the game is installed the same way: select it in the list and press **Install car (pull game files)**.

## Every time you tune

1. Close the game (the tuner refuses to install while it runs).
2. Choose an installed car (starts from the stock values) or a modded car (loads its saved values), then change values in the table. The settings are in categories (Meta, Display, Engine, ...) that are all collapsed when a car is loaded: click a category, or use **Expand all** / **Collapse all**; an open category shows a short description under its name. Each row shows: variable name, your value, the car's default (right next to your value), the **Range for base cars** (the lowest and highest default found over all game cars; only a guide, you can go beyond it; `–` for settings that are not numbers or that no installed car stores) and a description. Changed rows are highlighted blue and have a **reset** button. Use the search box, or tick **changed only** to see what you changed; both open the categories that match while they are set. The spring collar positions are hidden unless you tick **show advanced settings** (Kunos says the editor's Auto Setup computes them; a changed one stays listed). Settings a car does not have (for example turbo values on a naturally aspirated car) are hidden; the line under the title tells you how many.
3. With an installed car selected, press **Create modded car…**. A panel proposes the tuned car id (same length as the stock id; the first one is `ax_<stock>`, further ones a counter id such as `ax_bmw_m3_e46_c01`) and the name suffix; edit them if you like and confirm. The name of the modded car is the stock name plus the suffix (proposed `_MY`, then `_MY2`, `_MY3`), so it sorts right next to the stock car in the game's car list; you can make several modded cars of one stock car, each with its own saved values, suffix and package in the mods folder. After a few seconds the green message tells you the new package was installed, the draft is emptied and the new car is selected under Modded Cars. Create never overwrites an existing modded car.
4. To rework it later, pick the car under **Modded Cars**, change values and press **Apply (update this car)**; this updates exactly that car. Press **Duplicate…** to copy a modded car to a new one (the panel proposes id and suffix; leave them empty for automatic ones).
5. Start the game, open Vehicle Selection, pick your modded car (for example `BMW M3 E46 CSL_MY`, next to the stock one), drive.
6. Close the game and repeat.

Own tyres (optional, not verified in the game yet):

- The page has two tabs, **Car Tuner** (everything above) and **Tyre Creator**, which builds own tyres. A tyre has a name, a source (a front/rear pair of game tyre files taken from the tyre presets of an installed car) and the tyre settings you changed against that source (12 front, 12 rear; the default column shows the source tyre's value). Kunos advises against changing the tyre model values (the tab shows a warning): change little and test in the game. Use **New tyre…**, **Rename…**, **Delete**, the **Source** selector and **Reset all values**. Tyres are saved in `%USERPROFILE%\ace_modded_cars_work\tyres` and shared by all cars; a tyre edit reaches a car at its next Apply or Create. Delete is refused while a modded car or draft has the tyre ticked.
- The **Garage tyres** panel (Car Tuner tab, at the bottom below the settings table, closed at the start) lists your own tyres first, then the car's stock compounds. Ticked tyres are what the modded car offers in the game's garage; the first ticked one in the list is the starting tyre, at least one stays ticked. Nothing stored means all stock compounds and the car is not touched; **Reset to stock tyres** goes back to that. The selection is saved per modded car and draft and used by Apply and Create. If you also change tyre settings in the table, the car's stock default compound must stay ticked, otherwise Apply refuses.

"unverified" next to a description means the meaning is guessed from the setting's name and not yet confirmed in the game. A "copies differ in stock" badge means the game's own files disagree about that value; applying writes your value to every copy. Every setting of every car is explained in `docs/settings/<car id>.md`, for example [docs/settings/ks_bmw_m3_e46_csl.md](settings/ks_bmw_m3_e46_csl.md). Where a setting has an entry in the official physics documentation of the game (https://docs.assetto.cn/en/evo/car/physics/), its description starts with the official statement and continues with our notes; the rules learned from it are in [docs/TUNER_SPEC.md](TUNER_SPEC.md) section 6c.

## Good to know

- **Refresh the ranges:** install the cars you want in the ranges, then run `python tools\tune.py ranges` once (about 20 seconds for 71 cars; it only reads your work folder, never the game). It writes `%USERPROFILE%\ace_modded_cars_work\ranges.json`; reload the page afterwards. Without that file the column shows `–`.

- **Check a power change without driving:** when a session starts the game writes a line like `POWER CLASS INDEX ... (357.19 HP)` into the newest file in `%USERPROFILE%\Saved Games\ACE\Logs`.
- **Undo:** every install keeps a backup of the previous package in `%USERPROFILE%\ace_modded_cars_work\backups`. Copy one over the file in `%USERPROFILE%\Saved Games\ACE\mods\`, or delete the tuned car's `.kspkg` there to remove it completely.
- **Remove a modded car:** the page has no delete button. Delete its folder `%USERPROFILE%\ace_modded_cars_work\<stock car id>\tunes\<id>` and its `<id>.kspkg` in the mods folder by hand. The first modded car `ax_<stock>` keeps its files in `<stock car id>\tune_state.json` and `<stock car id>\build\<id>` instead.
- **Your values** are remembered in `%USERPROFILE%\ace_modded_cars_work\<stock car id>`: the draft of an installed car in `draft_state.json`, each modded car in `tunes\<id>\tune_state.json` (the first one, `ax_<stock>`, in `tune_state.json` next to the draft). **Reset all** clears the values of the selected car or draft, including its garage tyre selection.
- **Car not in the list in the game?** Check that its `ax_....kspkg` is directly inside `%USERPROFILE%\Saved Games\ACE\mods\`, and look at the newest game log for errors.
- **Python not found?** Install Python 3.12 for the current user, or edit the path in `start_tuner.bat` (repository root).
- Command-line use: `python tools\tune.py cars [--modded] | init --car <id> | defaults --car <id> | show | set <id> <value> | unset <id> | apply | duplicate | doc --all` (every command except `cars` takes `--car <id>`; `doc` takes `--car <id>` or `--all`). Tyres: `tyres | tyre-sources | tyre-new --name <text> --source <key> | tyre-show <id> | tyre-set <id> <setting> <value> | tyre-unset <id> <setting> | tyre-delete <id>` (library commands, no `--car`; `<key>` is the key `tyre-sources` prints); garage: `garage | garage-set <key> [<key> ...] | garage-reset`, each with `[--tune <id> | --draft] [--car <id>]`. `cars --modded` lists the modded cars; `show`, `set`, `unset`, `defaults` and `apply` take `--tune <id>` to work on one modded car; `duplicate [--tune <id> | --draft] [--new-id <id>] [--suffix <text>]` copies a modded car or the draft to a new modded car.
  `apply` refuses to install while the game is running (`--no-install` only builds and is not refused). An install first writes `<name>.kspkg.part` into the mods folder and replaces the package atomically when the copy is complete, so a failed copy leaves the old package intact.
- **Do not close the console window while a job runs** (install a car or apply): Ctrl+C waits for the running job, a second Ctrl+C aborts it. Edits are refused while a job runs.
- Server options: `python tools\tuner_server.py [--port N] [--work <dir>] [--mods <dir>] [--game <content.kspkg>]`; `--game` points at the game's `content.kspkg` when it is not in the default Steam folder.
- All tools print their usage block on stdout and exit with code 2 when called with wrong or missing arguments; runtime errors are `error: ...` on stderr with exit code 1.
- Tests: `python -m unittest discover -s tests` runs the test suite; it needs no game data and runs in the cloud as well.

## More

- [README](README.md): the short overview.
- [docs/TUNER_SPEC.md](TUNER_SPEC.md): state of the project (what works, what is verified, what is open).
- [docs/HANDOVER.md](HANDOVER.md): notes for continuing the work in a new session, local or cloud.

## Credits and rights

Not affiliated with KUNOS Simulazioni; requires a legal copy of Assetto Corsa EVO. Car data, field names and game files belong to Kunos and stay out of this repository. Do not publish tuned versions of Kunos' cars.
