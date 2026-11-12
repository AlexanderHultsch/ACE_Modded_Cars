# Fix plan for the 2026-11-12 review (decisions, rules, status)

Findings: `R1.md` .. `R5.md` in this folder (IDs like R1-005). Owner decisions of 2026-11-12 (Alex):

- Fix all findings, except the Hina-data items R3-024, R4-003, R4-004 (D3: leave as is).
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

Updated by the planner after each verified batch (see git log for the commits).
