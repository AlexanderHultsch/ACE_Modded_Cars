# ACE - Simple Car Tuner: drift tuner for Assetto Corsa EVO

Change the driving settings of a car in a simple table, install your own tuned copy next to the stock one, drive a lap, close the game, change again. About 136-142 settings per car: engine, turbo, gearing, differential (setup and hardware), steering, brakes, springs, dampers, anti-roll bars, ride height and bump stops, alignment, tyres, driver aids, fuel. No cosmetics.

Tested cars: **BMW M3 E46 CSL**, **Toyota GR86**, **Mazda RX-7 FD**, **Alfa Romeo Giulia GTAm**, **Porsche 992 GT3 R Rennsport**. The selector lists all 71 game cars; the others are shown as "not extracted" and are untested (they extract and build without errors, but whether they load and drive is unknown). A tuned copy of a car is a **modded car**: the stock name plus a suffix (proposed `_MY`, then `_MY2`, `_MY3`, for example `BMW M3 E46 CSL_MY`), so it sorts right next to the stock car in the game's car list. You can make several modded cars of one stock car; each has its own saved values and its own suffix, and each is its own package in the mods folder. The stock cars are never changed.

## What you need

- Windows PC with **Assetto Corsa EVO** and the **Assetto Corsa EVO SDK** installed through Steam (both fully downloaded).
- **Python 3.12** from python.org, installed for the current user (the start file looks in `%LOCALAPPDATA%\Programs\Python\Python312\`).
- This repository (clone or download it).

## One-time setup

1. Open a terminal in the repository folder and extract the car data field names from the SDK (they belong to the game vendor, so they stay on your PC and are not part of this repository):
   ```
   python tools\extract_protos.py "C:\Program Files (x86)\Steam\steamapps\common\Assetto Corsa EVO SDK\AssettoCorsaEVOEditor.exe" schemas
   ```
2. Double-click **`tuner\start_tuner.bat`**. A console window opens and your browser shows the tuner at http://127.0.0.1:8765/ . Keep the console window open while you use it. (After updating the repository, close that window and start it again.)
3. Pick a car in the selector at the top. It has three groups: **Base Cars: tested**, **Base Cars: all other game cars** and **Modded Cars** (entries like `BMW M3 E46 CSL_MY - installed`). The first time you pick a base car, press **Extract stock car** (about 20 seconds). This copies that car's data out of the game into `%USERPROFILE%\ace_modded_cars_work\<car id>`. Only cars you pick are extracted.

## Every time you tune

1. Close the game (the tuner refuses to install while it runs).
2. Choose a base car (starts from the stock values) or a modded car (loads its saved values), then change values in the table. Each row shows: variable name, your value, the car's default (right next to your value) and a description. Changed rows turn yellow and have a **reset** button. Use the search box, or tick **changed only** to see what you changed. Settings a car does not have (for example turbo values on a naturally aspirated car) are hidden; the line under the title tells you how many.
3. With a base car selected, press **Create modded car…**. A panel proposes the tuned car id (same length as the stock id; the first one is `ax_<stock>`, further ones a counter id such as `ax_bmw_m3_e46_c01`) and the name suffix; edit them if you like and confirm. After a few seconds the green message tells you the new package was installed, the draft is emptied and the new car is selected under Modded Cars. Create never overwrites an existing modded car.
4. To rework it later, pick the car under **Modded Cars**, change values and press **Apply (update this car)**; this updates exactly that car. Press **Duplicate…** to copy a modded car to a new one (the panel proposes id and suffix; leave them empty for automatic ones).
5. Start the game, open Vehicle Selection, pick your modded car (for example `BMW M3 E46 CSL_MY`, next to the stock one), drive.
6. Close the game and repeat.

"unverified" next to a description means the meaning is guessed from the setting's name and not yet confirmed in the game. A "copies differ in stock" badge means the game's own files disagree about that value; applying writes your value to every copy. Every setting of every car is explained in `docs/settings/<car id>.md`, for example [docs/settings/ks_bmw_m3_e46_csl.md](docs/settings/ks_bmw_m3_e46_csl.md).

## Good to know

- **Check a power change without driving:** when a session starts the game writes a line like `POWER CLASS INDEX ... (357.19 HP)` into the newest file in `%USERPROFILE%\Saved Games\ACE\Logs`.
- **Undo:** every install keeps a backup of the previous package in `%USERPROFILE%\ace_modded_cars_work\backups`. Copy one over the file in `%USERPROFILE%\Saved Games\ACE\mods\`, or delete the tuned car's `.kspkg` there to remove it completely.
- **Remove a modded car:** the page has no delete button. Delete its folder `%USERPROFILE%\ace_modded_cars_work\<stock car id>\tunes\<id>` and its `<id>.kspkg` in the mods folder by hand. The first modded car `ax_<stock>` keeps its files in `<stock car id>\tune_state.json` and `<stock car id>\build\<id>` instead.
- **Your values** are remembered in `%USERPROFILE%\ace_modded_cars_work\<stock car id>`: the draft of a base car in `draft_state.json`, each modded car in `tunes\<id>\tune_state.json` (the first one, `ax_<stock>`, in `tune_state.json` next to the draft). **Reset all** clears the values of the selected car or draft.
- **Car not in the list in the game?** Check that its `ax_....kspkg` is directly inside `%USERPROFILE%\Saved Games\ACE\mods\`, and look at the newest game log for errors.
- **Python not found?** Install Python 3.12 for the current user, or edit the path in `tuner\start_tuner.bat`.
- Command-line use: `python tools\tune.py cars [--modded] | init --car <id> | defaults --car <id> | show | set <id> <value> | unset <id> | apply | duplicate | doc --all` (every command except `cars` takes `--car <id>`; `doc` takes `--car <id>` or `--all`). `cars --modded` lists the modded cars; `show`, `set`, `unset`, `defaults` and `apply` take `--tune <id>` to work on one modded car; `duplicate [--tune <id> | --draft] [--new-id <id>] [--suffix <text>]` copies a modded car or the draft to a new modded car.
  `apply` refuses to install while the game is running (`--no-install` only builds and is not refused). An install first writes `<name>.kspkg.part` into the mods folder and replaces the package atomically when the copy is complete, so a failed copy leaves the old package intact.
- **Do not close the console window while a job runs** (extract or apply): Ctrl+C waits for the running job, a second Ctrl+C aborts it. Edits are refused while a job runs.
- Server options: `python tools\tuner_server.py [--port N] [--work <dir>] [--mods <dir>] [--game <content.kspkg>]`; `--game` points at the game's `content.kspkg` when it is not in the default Steam folder.
- All tools print their usage block on stdout and exit with code 2 when called with wrong or missing arguments; runtime errors are `error: ...` on stderr with exit code 1.
- Tests: `python -m unittest discover -s tests` runs the test suite; it needs no game data and runs in the cloud as well.

## More

- [docs/TUNER_SPEC.md](docs/TUNER_SPEC.md): state of the project (what works, what is verified, what is open).
- [docs/HANDOVER.md](docs/HANDOVER.md): notes for continuing the work in a new session, local or cloud.

## Credits and rights

Not affiliated with KUNOS Simulazioni; requires a legal copy of Assetto Corsa EVO. Car data, field names and game files belong to Kunos and stay out of this repository. Do not publish tuned versions of Kunos' cars.
