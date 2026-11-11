# ACE Modded Cars

Experiments with tuning Assetto Corsa EVO cars for drifting: read a car's physics data with real field names, change values, pack the car again, drive it. Current goal: a local HTML table page to tune one car (BMW M3 E46) quickly, see [docs/TUNER_SPEC.md](docs/TUNER_SPEC.md).

- **Start here:** [HANDOVER.md](HANDOVER.md) (status, formats, field knowledge, next steps)
- **Specification:** [docs/TUNER_SPEC.md](docs/TUNER_SPEC.md)
- Tools (Python 3.9+, stdlib only), in `tools/`:
  - `kspkg.py` list / extract / pack / verify `.kspkg` packages
  - `pb_raw.py`, `dump_car.py` schema-less protobuf dumps
  - `extract_protos.py` extract the protobuf schemas from the SDK Editor exe into `schemas/` (git-ignored)
  - `car_json.py` decode / encode car data files as JSON with real field names (lossless)
- Reference: schema-less dumps of Hina's Drift Club 1.4 in `hdc_1.4/decoded/` (credits in [NOTICE.md](NOTICE.md))

```bash
python tools/kspkg.py list    <package>.kspkg
python tools/kspkg.py extract <package>.kspkg work/car
python tools/extract_protos.py "<Steam>/Assetto Corsa EVO SDK/AssettoCorsaEVOEditor.exe" schemas
python tools/car_json.py decode work/car/content/cars/<id>/data/<file>.carengine
python tools/car_json.py check  work/car
python tools/kspkg.py pack    work/car work/car.kspkg
python tools/kspkg.py verify  <package>.kspkg work/car.kspkg
```

On the author's PC Python is not on PATH; use the full path of the installed interpreter with `-I`.

Not affiliated with KUNOS Simulazioni. Requires a legal copy of Assetto Corsa EVO and its SDK. Vendor data (`schemas/`, SDK and game files) is not part of this repository.
