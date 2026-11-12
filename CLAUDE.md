# CLAUDE.md

Project: local table tuner for the Assetto Corsa EVO BMW M3 E46 CSL (drift focus): read the car's data with real field names, change values, build an own car copy, install it in the mods folder.

- Read `HANDOVER.md` first (status, formats, field knowledge, open questions), then `docs/TUNER_SPEC.md` (design, pipeline rules). `docs/BMW_SETTINGS.md` is generated (`python tools/tune.py doc`), do not edit it by hand.
- Tools are stdlib-only Python 3.9+ in `tools/`: `kspkg.py`, `extract_protos.py`, `car_json.py`, `clone_car.py`, `tune.py`, `tuner_server.py`, `pb_raw.py`, `dump_car.py`. No new dependencies without asking.
- Edit car data only through `car_json.py` (lossless); verify with `car_json.py check` and, for builds, byte comparison against a plain `clone_car.py build`.
- A setting must change every copy of a value (standalone file and the inline copy in `data/<id>.car`); the settings list is `tuner/catalogue.json`.
- Work data lives in `%USERPROFILE%\ace_modded_cars_work` (outside OneDrive and outside AppData: the Claude desktop app redirects AppData writes into a private folder the user cannot see). Use a scratch `--work` folder for tests; never touch the real work folder's state, the real mods folder, the game folder, the SDK folder or the stock cars while testing.
- Keep vendor data out of git: `schemas/`, the work folder, `*.kspkg`, SDK/game files. `mod_examples/` is local, third-party and untracked. `hdc_1.4/decoded/` is read-only reference data.
- Do not use `Nenkai/ACEvo.Package` (its AGENTS.md prohibits AI use).
- Game tests: Alex's Windows PC; mods folder `%USERPROFILE%\Saved Games\ACE\mods\`. Always back up packages before replacing them (the tools do). The development laptop crashes in the renderer for every car (Intel UHD); verify power/mass through the game log line `POWER CLASS INDEX ... (<hp> HP) W:<kg>`. Python is not on PATH; use the full interpreter path with `-I`.
- Do not publish tuned derivatives of Hina's or Kunos' cars.
