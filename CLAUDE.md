# CLAUDE.md

Project: tune Assetto Corsa EVO cars for drifting by reading, editing and repacking car data (`.kspkg` packages), goal: a local HTML table tuner for the BMW M3 E46.

- Read `HANDOVER.md` first (status, formats, field knowledge, next steps), then `docs/TUNER_SPEC.md` (agreed design).
- Tools are stdlib-only Python 3.9+ in `tools/`: `kspkg.py`, `pb_raw.py`, `dump_car.py`, `extract_protos.py`, `car_json.py`. No new dependencies without asking.
- Edit car data only through `car_json.py` (lossless); verify with `car_json.py check` and `kspkg.py verify`.
- Work on copies in `work/` (git-ignored). `hdc_1.4/decoded/` is read-only reference data. Never modify the game folder, the SDK folder or the stock cars.
- Keep vendor data out of git: `schemas/`, `work/`, `*.kspkg`, SDK/game files. `mod_examples/` is local, third-party and untracked.
- Do not use `Nenkai/ACEvo.Package` (its AGENTS.md prohibits AI use).
- Target machine for game tests: Alex's Windows PC; mods folder `%USERPROFILE%\Saved Games\ACE\mods\`. Always back up packages before replacing them. Python is not on PATH there; use the full interpreter path with `-I`.
- Do not publish tuned derivatives of Hina's or Kunos' cars.
