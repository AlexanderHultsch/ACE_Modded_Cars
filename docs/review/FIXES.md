# Fix plan for the 2026-11-12 review (decisions, rules, status)

Owner decision of 2026-11-13 (Alex), which overrides the earlier decision to leave third-party data as is: "From now on we have nothing to do with other mods; we build our own program." All third-party mod material (reference data, comparison document, names, credits and numbers taken from a third-party mod) was removed from the current files of the repository on 2026-11-13. The git history is not rewritten. The findings R3-024, R4-003 and R4-004 are obsolete because of this.

Findings: `R1.md` .. `R5.md` in this folder (IDs like R1-005). Owner decisions of 2026-11-12 (Alex):

- Fix all findings, except R3-024, R4-003, R4-004 (D3; obsolete since 2026-11-13, see above).
- Findings R5-A-* about `pbedit`, `make_testkit`, the old lever `tune.py`, the old `tests/` and branch docs are moot: those files are not in this tree (only `refgraph` and the working contract are ported from the old branch).
- D5, usage convention for ALL tools: wrong or missing arguments print the usage block (first paragraph after the one-line docstring title) on stdout and exit 2 (as `kspkg.py` does today); runtime errors are `error: ...` on stderr, exit 1.

## Decisions taken for findings that said "decision for the owner"

| ID | Decision |
|---|---|
| R2-001 | Option A: `car_json decode` of a file that does not round-trip prints `error: ...`, writes nothing, exit 1 |
| R3-003 | Minimal: `apply` raises `ValueError` ("tyre file inside the car folder not supported yet") for non-shared tyre files |
| R3-022 | Raise `max` of spring_front, spring_rear, spring_min_*, spring_max_* to 500000; widen `steer_ratio` min to -30; leave absent zeros |
| R3-035 | Full fix: move `game_running()` into `tune.py`, the CLI `apply` refuses while the game runs; server imports it |
| R4-007 | Server accepts `--game <content.kspkg>` and passes it on (`CONFIG["game"]`) |
| R4-013 | Exclusive bind on Windows (`SO_EXCLUSIVEADDRUSE`) |
| R4-014 | Add `X-Frame-Options: DENY` and `Content-Security-Policy: frame-ancestors 'none'` |
| R3-002 | Install copies to `<name>.kspkg.part` in the mods folder, size check, then `os.replace` |
| R1-010 | Chunked extract/hash (CHUNK 8 MiB) |
| apply --no-install | not refused while the game runs |
| R1-011 | Memoize `read_table` per (path, size, mtime) inside `kspkg.py` only (no signature change) |
| R3-011 | Cache resolved rows in `tune.py` (invalidate on init/tyre extraction/catalogue or `.car` mtime change), one-setting resolve for the edit path |
| R4-001 | Edits (set/unset/reset_all) are refused with 409 while a job runs |
| R4-002 | Ctrl+C with a running job waits for it (second Ctrl+C aborts) |
| R2-018 / R3-001 | Atomic state save; `apply` builds in `<new_id>.partial` and renames after success |
| R5-A-009 / R1-006 / R1-018 | D5 convention everywhere |

## Rules for fix delegations (executors)

- Read the finding blocks by ID in `docs/review/R*.md` (WHERE, FIX, CLOUD-VERIFY). Line numbers refer to origin/main of 2026-11-12 and drift as batches land: locate by the quoted text. If a FIX text does not match the current code, stop that finding and report it.
- The suite (`python3 -B -m unittest discover -s tests`) must stay green. For every finding you fix there may be an `expectedFailure` test naming its ID: after the fix it reports "unexpected success"; remove exactly that decorator and its ID comment line (and nothing else). Never touch the decorator of a finding you did not fix. Never weaken, delete or skip a test; if a test must change because behaviour changed on purpose (e.g. D5), say which and why.
- `ruff check --select F,B904 --no-cache tools` must not get worse; every changed `.py` file must pass `python3 -B -m py_compile`.
- Comment/docstring-only batches (T1) must leave the code AST identical (docstrings and comments excluded); the planner checks this with a script.
- Do not commit; do not touch files outside the batch.

## Findings found wrong or partly wrong during the fixes

- R3-019 (a)+(c): not applied; the `{stock_display_name}` placeholder is used (tests `test_default_template_placeholders`, `test_incomplete_stock_info_is_used_as_far_as_it_goes`, `test_stock_name_comes_from_the_mechanical_preset_without_stock_info`). Part (b) applied.
- R3-029: the finding's FIX wording was superseded by the test's range format (README says `136-142`).

## Status

All findings are fixed except the items under "Not applied / decisions" below. Suite after the last batch: 991 tests, 0 expected failures (`python3 -B -m unittest discover -s tests`). Commits in order (oldest first); batches K4, K5 and K7 have no commit of their own in the log.

| Batch | Commit subject | What |
|---|---|---|
| Review | `2b6afed` Add code review reports, working contract and CLAUDE.md | R1..R5 reports, `docs/working-contract.md`, `CLAUDE.md` |
| Tests 1-4 | `f89739d`, `dacfe11`, `ef8ab21`, `77572ca` Add test suite part 1..4 | tests for kspkg, pb_raw, dump_car; extract_protos, car_json; catalogue, settings engine, clone_car; tuner_server and page; findings not yet fixed are `expectedFailure` tests named by ID |
| H1 | `7621722` Review fixes H1: comments and docstrings in tools (18 findings) | comment and docstring fixes, code AST-identical; adds this file |
| H2 | `aef97e7` Review fixes H2: documentation and page comments (11 findings) | README, TUNER_SPEC, coverage.md, HANDOVER corrections, page comments |
| S0 | `ddcdf41` Review fixes S0: stdout capture lock (R3-005), README range (R3-029) | lock around every `redirect_stdout` block in `tune.py`; README range 136-142 |
| H3 | `f5a62f2` Review fixes H3: mechanical fixes in kspkg, extract_protos, car_json, clone_car | R1-001 (scan skips candidates that crash the strict parse), R1-008, R1-014, R1-021..023, R2-005..008 |
| H4a | `0555769` Review fixes H4a: mechanical fixes in tune.py and tuner_server.py | R2-006/R3-009, R2-017, R2-022, R2-024, R3-015..017, R3-019(b), R4-006, R4-008, R4-009, R4-011 |
| H4b | `e19db87` Review fixes H4b: page, start_tuner.bat, git config | page filter pass and aria labels, PORT variable in the bat, `.gitattributes`, `.gitignore` |
| K1 | `fc706e2` Review fixes K1: kspkg behaviour fixes and usage convention | R1-005 truncated entry is an error, R1-006 and D5 usage convention, R1-007 pack names, R1-009, R1-010 chunked extract/verify |
| R1-011 | `2c8922e` Review fix R1-011: cache the parsed package table per file | `read_table` memoized per path, size, mtime |
| K2 | `a2866a5` Review fixes K2: pb_raw, dump_car, extract_protos | R1-002, R1-003, R1-004, R1-012, R1-016..018, R1-020, usage convention |
| R1-013 | `d40b964` Review fix R1-013: parse each descriptor blob once per run | `parse_file` memoized by blob bytes |
| K3 | `f77ec56` Review fixes K3: car_json and clone_car behaviour, usage convention | R2-001 (decode refuses files that do not round-trip), R2-002, R2-009, R2-010; clone_car R1-025..028, R3-002 (install via `.part`), R3-018 |
| K6a | `d683414` Review fixes K6a: tune.py state files, errors and usage convention | atomic state saves, errors and warnings on stderr, `expand()` for work and mods paths, shared `parse_args`, R2-014..026, R3-006..008, R3-012, R3-020 |
| K6b | `e1fc4c0` Review fixes K6b: tune.py build, install, game check, performance | R3-001 (`<id>.partial` build), R3-003, R3-010, R3-011 (row cache), R3-018, R3-035 (CLI apply refuses while the game runs) |
| K8 | `6679ef8` Review fixes K8: tuner_server behaviour fixes | R4-001 (409 on edits during a job), R4-002 (Ctrl+C waits), R4-005, R4-007 (`--game`), R4-010, R4-013, R4-014, R4-015, R4-016, R4-043 |
| R4-012 | `de469e1` Review fix R4-012: precise HTTP status codes in the tuner server | 415, 413, 405 with `Allow: GET, POST` |
| K9 | `67f9886` Review fixes K9: web page behaviour and accessibility | R4-020, R4-021, R4-023, R4-024, R4-029, page parts of R4-001/R4-002, bat part of R4-007 |
| K10 | `0cd8021` Review fixes K10: catalogue data and generated settings docs | R3-004, R3-022, R3-023, R3-025, R3-026, R3-028; the five `docs/settings` files regenerated, defaults unchanged |
| refgraph | `34bb046` Port refgraph from the earlier work line, with tests | `tools/refgraph.py`, 33 tests |
| Docs | `ca4c821` Docs: server section, tests, review status and decisions | R4-037 (server and raw dump tools in TUNER_SPEC), R4-042 (contract pointer in HANDOVER, kspkg docstring), README, TUNER_SPEC and HANDOVER brought up to date, this section |
| K13 | Review fixes K13: leftovers | K13: leftovers (rear label, apply --no-install, hermetic tests, refgraph docstring) |

## Not applied / decisions

- R3-024, R4-003, R4-004 (third-party data in the repo): obsolete, the material was removed from the repository on 2026-11-13 (owner decision); the git history is not rewritten.
- R4-033 (start file for other Python installs): not applied; the owner chose Python 3.12 per user (`%LOCALAPPDATA%\Programs\Python\Python312\`), and the start file cannot be tested in the cloud.
- R3-027 (the 19 thermal curve choices duplicated in the front and rear setting): not applied; the finding recommends no change unless a family is added (a schema change would be an owner decision).
- R3-013, R1-029 (several reads and writes of the car tree per Apply): not applied; the findings recommend no change before measuring on the PC.
- R3-019 (a)(c): not applied, the tests contradict it (see above); (b) applied in H4a.
- R2-022, R3-016, R3-017: done in H4a.
- R4-037, R4-042: done in the documentation batch after `34bb046`.

Known limitation, not changed: `prefixed()` in `tools/refgraph.py` also tries the length prefix in plain text files, where the byte before a path is ordinary text, and can truncate a reference there. Not changed because there is no real data to validate a change; real car trees are protobuf, where the prefix is right.

## PC verification list

Everything above was verified in the cloud only (synthetic data, no game files, no Windows). What the CLOUD-VERIFY lines of `R1.md` .. `R4.md` mark as "needs PC":

- Real packages: `kspkg.py extract`, `pack`, `verify` on the game's `content.kspkg` and a real car (truncated entries, pack entry names, chunked extract, cached table; timing of `tune.py init`): R1-005, R1-007, R1-010, R1-011.
- `extract_protos.py` on the real SDK Editor exe: `acevo.desc` byte-identical to the current `schemas/acevo.desc` (R1-001, R1-003, R1-004, R1-012).
- Windows paths and newlines: `dump_car.py` and a full clone on a car with a path over 260 characters (Porsche), `tune_state.json` without 0x0D bytes, atomic replace over an open file: R1-016, R1-020, R2-017, R2-018.
- Codec on real files: `car_json.py decode`/`encode` on a real car file, `check` must report 0 failures (R2-001, R2-002), a decoded `compatibletyres` file (R3-007 and the tyre changes).
- `tune.py cars`, `defaults`, `doc --all` for the five cars: output identical to before and `git diff docs/settings` empty (R2-010, R3-004, R3-011, R3-022, R3-023).
- `tune.py apply --no-install`: same package bytes as before (R3-001), wall time of apply and of `init` (R1-029, R3-013, R2-022 optional), then a normal install and the game loads the car (R3-002).
- Tyres: R3-003 (find a game car whose tyre file is inside the car folder, not shared) and R3-007 (is `rear_tyre_data_paths` a list; if yes, change `referenced_tyres()` as the finding says).
- Game detection: `tasklist` cost and result with the game running and not running (R3-035, R4-005); `tune.py apply` and the server refuse while it runs.
- Server on Windows: second start fails with `WinError 10048` (R4-013), Ctrl+C or a closed console during a real Apply (R4-002), an edit during a real Apply shows the 409 message (R4-001), the browser loads the page on first start without F5 (R4-006), `X-Frame-Options` visible in a browser (R4-014).
- Page and start file in a browser: stale error clears after a server restart, polling every 30 s in a hidden tab, screen reader reads status and badge, table, filters and reset work (R4-020..R4-031); `start_tuner.bat` by double click on port 8765 and from a fresh ZIP download (R4-031, R4-032).
