# NOTICE

## Hina's Drift Club 1.4 (`hdc_1.4/`)

- Author: **Hina** ("HDC 1.4 — Hina's Drift Club", developer: Hina).
- Source: OverTake.gg, "Introducing Hina's Drift Club — three drift cars, three personalities, ready to drive in ACE EVO":
  https://www.overtake.gg/downloads/introducing-hina%E2%80%99s-drift-club-%E2%80%94-three-drift-cars-three-personalities-ready-to-drive-in-ace-evo.87009/
- The release ships without a license file. All rights remain with the author. Since 2026-11-11 the repo keeps only schema-less text dumps of the car data (`hdc_1.4/decoded/`) for research; the packages, payload and extracted files were removed (they remain in git history before commit 19f9817). Get the official download from the link above.
- Track imagery credits (formerly in the payload): GSI Japan, Japan Public Data Licence 1.0.
- Will be removed on request of the author.

## Kunos Simulazioni / Assetto Corsa EVO

Car data, physics values and referenced assets derive from Assetto Corsa EVO by KUNOS Simulazioni. Assetto Corsa is a trademark of its owners. Requires a legal copy of the game. Not affiliated with or endorsed by KUNOS Simulazioni or 505 Games.

## Tools (`tools/`)

Written in this repo. `.kspkg` table layout originally documented by ntpopgetdope/ace-kspkg (MIT); 0.7+ changes (64 MiB table, UTF-16LE FNV-1a hash, data layout) found here. `extract_protos.py` reads the protobuf descriptors embedded in the user's own SDK Editor executable; the generated `schemas/` are Kunos property and are never committed.
