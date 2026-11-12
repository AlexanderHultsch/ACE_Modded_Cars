# ACE Modded Cars: drift tuner for Assetto Corsa EVO

Change the driving settings of a car in a simple table, install your own tuned copy next to the stock one, drive a lap, close the game, change again. About 75-80 settings per car: engine, turbo, gearing, differential, brakes, springs, dampers, alignment, fuel. No cosmetics.

Tested cars: **BMW M3 E46 CSL**, **Toyota GR86**, **Mazda RX-7 FD**, **Alfa Romeo Giulia GTAm**, **Porsche 992 GT3 R Rennsport**. The selector lists all 71 game cars; the others are shown as "not extracted" and are untested (they extract and build without errors, but whether they load and drive is unknown). Your tuned copy of a car is always called the stock name plus `_MY` (for example `BMW M3 E46 CSL_MY`), so it sorts right next to the stock car in the game's car list. The stock cars are never changed.

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
3. Pick a car in the selector at the top ("Tested cars" first, then all other game cars). The first time you pick a car, press **Extract stock car** (about 20 seconds). This copies that car's data out of the game into `%USERPROFILE%\ace_modded_cars_work\<car id>`. Only cars you pick are extracted.

## Every time you tune

1. Close the game (the tuner refuses to install while it runs).
2. Choose the car, then change values in the table. Each row shows: variable name, your value, the car's default (right next to your value) and a description. Changed rows turn yellow and have a **reset** button. Use the search box, or tick **changed only** to see what you changed. Settings a car does not have (for example turbo values on a naturally aspirated car) are hidden; the line under the title tells you how many.
3. Press **Apply (update my car)**. After a few seconds the green message tells you the package was installed. Press **Save as new copy…** instead to keep the previous tuned car and install another one next to it (you type a new car id with exactly the length shown).
4. Start the game, open Vehicle Selection, pick your `..._MY` car (next to the stock one), drive.
5. Close the game and repeat.

"unverified" next to a description means the meaning is guessed from the setting's name and not yet confirmed in the game. A "copies differ in stock" badge means the game's own files disagree about that value; applying writes your value to every copy. Every setting of every car is explained in `docs/settings/<car id>.md`, for example [docs/settings/ks_bmw_m3_e46_csl.md](docs/settings/ks_bmw_m3_e46_csl.md).

## Good to know

- **Check a power change without driving:** when a session starts the game writes a line like `POWER CLASS INDEX ... (357.19 HP)` into the newest file in `%USERPROFILE%\Saved Games\ACE\Logs`.
- **Undo:** every install keeps a backup of the previous package in `%USERPROFILE%\ace_modded_cars_work\backups`. Copy one over the file in `%USERPROFILE%\Saved Games\ACE\mods\`, or delete the tuned car's `.kspkg` there to remove it completely.
- **Your values** are remembered per car in `%USERPROFILE%\ace_modded_cars_work\<car id>\tune_state.json`; **Reset all** clears them for the selected car.
- **Car not in the list in the game?** Check that its `ax_....kspkg` is directly inside `%USERPROFILE%\Saved Games\ACE\mods\`, and look at the newest game log for errors.
- **Python not found?** Install Python 3.12 for the current user, or edit the path in `tuner\start_tuner.bat`.
- Command-line use: `python tools\tune.py cars | init --car <id> | defaults --car <id> | show | set <id> <value> | apply | doc --all` (every command takes `--car <id>`).

## More

- [docs/TUNER_SPEC.md](docs/TUNER_SPEC.md): state of the project (what works, what is verified, what is open).
- [docs/HANDOVER.md](docs/HANDOVER.md): notes for continuing the work in a new session, local or cloud.
- `Example mods (reference only)/`: text dumps of the driving data of six drift cars by other authors, for research only.

## Credits and rights

Not affiliated with KUNOS Simulazioni; requires a legal copy of Assetto Corsa EVO. Car data, field names and game files belong to Kunos and stay out of this repository. The reference dumps in `Example mods (reference only)/` come from Hina's Drift Club 1.4 by Hina (OverTake.gg), all rights with the author, removed on request. Do not publish tuned versions of Kunos' or Hina's cars.
