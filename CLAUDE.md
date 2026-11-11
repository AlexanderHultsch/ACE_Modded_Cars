# CLAUDE.md

Project: tune Assetto Corsa EVO cars for drifting by unpacking/editing/repacking `.kspkg` mod packages.

- Read `HANDOVER.md` first: status, owner decisions, what is proven and open, next steps.
- Follow `docs/working-contract.md` for every coding session: a planner who writes no code delegates verified steps to executors; ask Alex when a decision is his.
- Tools are stdlib-only Python 3.9+: `tools/kspkg.py` (list/extract/pack/verify), `tools/pb_raw.py`, `tools/dump_car.py`, `tools/refgraph.py`, `tools/pbedit.py`, `tools/tune.py`, `tools/make_testkit.py`. Tests: `python -m unittest discover -s tests`.
- Edit car data only through `pbedit`/`tune` (lossless, all redundant copies together); label every claim in docs as verified / inferred / unknown / general.
- Do not delete cars, the installer or rewrite git history without Alex's explicit go-ahead (cleanup is staged, see HANDOVER section 6).
- Treat `hdc_1.4/original/**` and `hdc_1.4/payload/**` as read-only reference copies of Hina's release. Work on copies (e.g. `work/`, git-ignored).
- Do not use `Nenkai/ACEvo.Package` (its AGENTS.md prohibits AI use).
- Target machine for game tests: Alex's Windows PC; mods folder `%USERPROFILE%\Saved Games\ACE\mods\`. Always back up packages before replacing them.
- Do not publish tuned derivatives of Hina's or Kunos' cars.
