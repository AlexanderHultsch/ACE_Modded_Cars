# ACE Modded Cars

Experiments with tuning Assetto Corsa EVO cars for drifting: unpack a car mod package (`.kspkg`), read and edit its physics data (engine torque, differential, setup limits), pack it again.

- **Start here:** [HANDOVER.md](HANDOVER.md)
- Tools (Python 3.9+, no dependencies): `tools/kspkg.py` (list / extract / pack / verify), `tools/pb_raw.py`, `tools/dump_car.py`, `tools/refgraph.py` (file cross-references), `tools/pbedit.py` (lossless value editor), `tools/tune.py` (apply tuning levers), `tools/make_testkit.py` (PC test packages)
- Docs: `docs/pc-test-protocol.md`, `docs/car-anatomy.md`, `docs/tuning-levers.md`, `docs/drift-deltas.md`, `docs/working-contract.md`
- Reference mod: Hina's Drift Club 1.4 in `hdc_1.4/` (credits in [NOTICE.md](NOTICE.md))

```bash
python tools/kspkg.py list    hinas_drift_club_e46_v1.4.kspkg
python tools/kspkg.py extract hinas_drift_club_e46_v1.4.kspkg work/e46
python tools/dump_car.py      work/e46 work/e46_decoded
python tools/kspkg.py pack    work/e46 work/e46.kspkg
python tools/kspkg.py verify  hinas_drift_club_e46_v1.4.kspkg work/e46.kspkg
```

Not affiliated with KUNOS Simulazioni. Requires a legal copy of Assetto Corsa EVO.
