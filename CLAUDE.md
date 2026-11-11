# CLAUDE.md

Project: tune Assetto Corsa EVO cars for drifting by unpacking/editing/repacking `.kspkg` mod packages.

- Read `HANDOVER.md` first: status, file formats, decoded values, next steps.
- Tools are stdlib-only Python 3.9+: `tools/kspkg.py` (list/extract/pack/verify), `tools/pb_raw.py`, `tools/dump_car.py`.
- Treat `hdc_1.4/original/**` and `hdc_1.4/payload/**` as read-only reference copies of Hina's release. Work on copies (e.g. `work/`, git-ignored).
- Do not use `Nenkai/ACEvo.Package` (its AGENTS.md prohibits AI use).
- Target machine for game tests: Alex's Windows PC; mods folder `%USERPROFILE%\Saved Games\ACE\mods\`. Always back up packages before replacing them.
- Do not publish tuned derivatives of Hina's or Kunos' cars.
