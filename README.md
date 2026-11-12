# ACE Modded Cars

A local tuner for the Assetto Corsa EVO BMW M3 E46 CSL (drift focus): change about 70 settings (engine, gearing, differential, brakes, springs, dampers, alignment, fuel) in a table page, install your own tuned copy of the car next to the stock one, drive, close the game, change again.

- **Start here:** [HANDOVER.md](HANDOVER.md) (status, formats, field knowledge, open questions)
- **Specification:** [docs/TUNER_SPEC.md](docs/TUNER_SPEC.md); **all settings with defaults:** [docs/BMW_SETTINGS.md](docs/BMW_SETTINGS.md)

## Use the tuner (Windows)

1. Requirements: Assetto Corsa EVO and its SDK installed through Steam, Python 3.9+ (the batch file looks for `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`), Git for Windows if you clone.
2. First, extract the schemas once (they are Kunos property and stay local): `python tools/extract_protos.py "<Steam>/steamapps/common/Assetto Corsa EVO SDK/AssettoCorsaEVOEditor.exe" schemas`
3. Double-click `tuner\start_tuner.bat`. It opens http://127.0.0.1:8765/ . On first use press "Extract stock car" (about 20 s).
4. Edit values in the table, press "Apply (update my BMW)" (or "Save as new copy"). Close the game before applying. The tuned car "Alex E46 Drift" appears in the car list next to the stock E46. Every install keeps a backup in `%USERPROFILE%\ace_modded_cars_work\backups`.
5. Check a power change without driving: the game log `Saved Games\ACE\Logs\log-*.txt` contains `POWER CLASS INDEX ... (<hp> HP)` when a session starts.

Command line equivalents: `python tools/tune.py init | defaults | show | set <id> <value> | apply | doc`.

## Tools (Python 3.9+, stdlib only, in `tools/`)

- `kspkg.py` list / extract (optional path prefix) / pack / verify `.kspkg` packages
- `extract_protos.py` extract the protobuf schemas from an exe into `schemas/` (git-ignored)
- `car_json.py` decode / encode car data files as JSON with real field names (lossless)
- `clone_car.py` clone a game car under a same-length id, register it as a mod, pack, install with backup
- `tune.py`, `tuner_server.py` the settings engine and the local web server; `tuner/` holds the settings list and the page
- `pb_raw.py`, `dump_car.py` schema-less protobuf dumps; reference dumps of Hina's Drift Club 1.4 in `hdc_1.4/decoded/` (credits in [NOTICE.md](NOTICE.md))

Not affiliated with KUNOS Simulazioni. Requires a legal copy of Assetto Corsa EVO and its SDK. Vendor data (`schemas/`, SDK and game files, the work folder) is not part of this repository.
