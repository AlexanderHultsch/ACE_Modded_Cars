# CLAUDE.md

Project: local tuner for Assetto Corsa EVO cars (drift focus): read a car's data with real field names, change values, build and install an own copy.

- Read `docs/HANDOVER.md` first (state, rules, open questions), then `docs/TUNER_SPEC.md`. User guide: `README.md`.
- Follow `docs/working-contract.md` for every coding session: a planner who writes no code delegates verified steps to executors; ask Alex when a decision is his.
- Code review of 2026-11-12: findings in `docs/review/R1.md` .. `R5.md` (IDs like R1-005); fixes are applied step by step and referenced by ID.
- Tools are stdlib-only Python 3.9+ in `tools/`: kspkg, extract_protos, car_json, clone_car, tune, tuner_server, pb_raw, dump_car, refgraph. Tests: `python -m unittest discover -s tests` (runs in the cloud, needs no game data).
- Edit car data only through `tools/car_json.py` (lossless); a setting changes every copy of a value.
- Usage convention for all tools: usage block on stdout, exit code 2 (as `kspkg.py`); runtime errors as `error: ...` on stderr, exit 1.
- Vendor data stays out of git: `schemas/`, the work folder, `*.kspkg`, game and SDK files. Test with scratch folders (`--work`, `--mods`); never touch the real work folder, mods folder or game folder.
- Do not use `Nenkai/ACEvo.Package` (its AGENTS.md prohibits AI use).
- Do not publish tuned derivatives of Kunos' or Hina's cars. Hina's data in the repo stays as it is (decision of Alex, 2026-11-12).
- Do not delete cars or rewrite git history without Alex's explicit go-ahead.
- Game tests run on Alex's Windows PC; mods folder `%USERPROFILE%\Saved Games\ACE\mods\`. Always back up packages before replacing them.
