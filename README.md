# ACE Modded Cars: BMW E46 drift tuner

Change the driving settings of the Assetto Corsa EVO BMW M3 E46 CSL in a simple table, install your own tuned copy of the car next to the stock one, drive a lap, close the game, change again. About 70 settings: engine, gearing, differential, brakes, springs, dampers, alignment, fuel. No cosmetics.

Your tuned car is called **MY_BMW M3 E46 CSL** by default (`MY_` plus the stock car's name from the game; you can change the name in the table). The stock BMW is never changed.

## What you need

- Windows PC with **Assetto Corsa EVO** and the **Assetto Corsa EVO SDK** installed through Steam (both fully downloaded).
- **Python 3.12** from python.org, installed for the current user (the start file looks in `%LOCALAPPDATA%\Programs\Python\Python312\`).
- This repository (clone or download it).

## One-time setup

1. Open a terminal in the repository folder and extract the car data field names from the SDK (they belong to the game vendor, so they stay on your PC and are not part of this repository):
   ```
   python tools\extract_protos.py "C:\Program Files (x86)\Steam\steamapps\common\Assetto Corsa EVO SDK\AssettoCorsaEVOEditor.exe" schemas
   ```
2. Double-click **`tuner\start_tuner.bat`**. A console window opens and your browser shows the tuner at http://127.0.0.1:8765/ . Keep the console window open while you use it.
3. First start only: press **Extract stock car** (about 20 seconds). This copies the BMW's data out of the game into `%USERPROFILE%\ace_modded_cars_work`.

## Every time you tune

1. Close the game (the tuner refuses to install while it runs).
2. In the table, change values. Each row shows: variable name, your value, a description, and the BMW's default. Changed rows turn yellow and have a **reset** button. Use the search box to find a setting, or tick **changed only** to see what you changed.
3. Press **Apply (update my BMW)**. After a few seconds the green message tells you the package was installed. Press **Save as new copy…** instead to keep the previous tuned car and install another one next to it (you type a new car id with exactly 17 lowercase letters, digits or underscores).
4. Start the game, open Vehicle Selection, pick **MY_BMW M3 E46 CSL** (or the name you chose), drive.
5. Close the game and repeat.

"unverified" next to a description means the meaning is guessed from the setting's name and not yet confirmed in the game. Every setting is explained in [docs/BMW_SETTINGS.md](docs/BMW_SETTINGS.md).

## Good to know

- **Check a power change without driving:** when a session starts the game writes a line like `POWER CLASS INDEX ... (357.19 HP)` into the newest file in `%USERPROFILE%\Saved Games\ACE\Logs`. Stock is 357.19 HP; a power scale of 1.056 should show about 377 HP.
- **Undo:** every install keeps a backup of the previous package in `%USERPROFILE%\ace_modded_cars_work\backups`. Copy one over `%USERPROFILE%\Saved Games\ACE\mods\ax_bmw_m3_e46_csl.kspkg`, or delete that file to remove the tuned car completely.
- **Your values** are remembered in `%USERPROFILE%\ace_modded_cars_work\tune_state.json`; **Reset all** clears them.
- **Car not in the list?** Check that `ax_bmw_m3_e46_csl.kspkg` is directly inside `%USERPROFILE%\Saved Games\ACE\mods\`, and look at the newest game log for errors.
- **Python not found?** Install Python 3.12 for the current user, or edit the path in `tuner\start_tuner.bat`.
- Command-line use for the same functions: `python tools\tune.py init | defaults | show | set <id> <value> | apply | doc`.

## More

- [docs/TUNER_SPEC.md](docs/TUNER_SPEC.md): state of the project (what works, what is verified, what is open).
- [docs/HANDOVER.md](docs/HANDOVER.md): notes for continuing the work in a new session, local or cloud.
- `Example mods (reference only)/`: text dumps of the driving data of six drift cars by other authors, for research only.

## Credits and rights

Not affiliated with KUNOS Simulazioni; requires a legal copy of Assetto Corsa EVO. Car data, field names and game files belong to Kunos and stay out of this repository. The reference dumps in `Example mods (reference only)/` come from Hina's Drift Club 1.4 by Hina (OverTake.gg), all rights with the author, removed on request. Do not publish tuned versions of Kunos' or Hina's cars.
