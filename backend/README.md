# FreshSense backend

FastAPI simulator + freshness engine + redirect logic. Implements section 6 of `00_MASTER_PLAN.md`.

## Run
```bash
python3 -m venv .venv && source .venv/bin/activate      # from the repo root
pip install -r backend/requirements.txt
cd backend
export FRESHSENSE_MQTT_TOPIC="freshsense/<TEAMCODE>/tag/C-001"   # same topic as the Wokwi sketch
uvicorn main:app --port 8000          # add --reload only while coding (it resets the world on save)
```
The simulation starts **paused**. Resume it with `POST /api/sim/control {"paused": false}`, or with the dashboard's ▶ button.

| Env var | Default | Meaning |
|---|---|---|
| `FRESHSENSE_MQTT_TOPIC` | `freshsense/fs-CHANGE-ME/tag/C-001` | topic the Wokwi tag publishes to |
| `FRESHSENSE_MQTT_HOST` | `broker.hivemq.com` | change to `test.mosquitto.org` if HiveMQ is busy |
| `FRESHSENSE_MQTT_ENABLED` | `1` | `0` turns MQTT off (the HTTP tag endpoint still works) |
| `FRESHSENSE_DB` | `backend/freshsense.db` | SQLite file (tests use `:memory:`) |

## Test
```bash
cd backend && python -m pytest -q
```
There are 13 tests: engine math, redirect rules, the heat scenario, and the full API contract.

## Files
| File | What it does |
|---|---|
| `main.py` | REST + WebSocket, 1 s tick loop |
| `world.py` | crates, trucks, history back-fill, scenarios, movement, deliveries, State JSON |
| `engine.py` | Arrhenius freshness math |
| `redirect.py` | REDIRECT / DONATE / DISCARD rules |
| `alerts.py` | alert rules |
| `journey.py` | journey report (stages, excursions, blame) |
| `analytics.py` | hours lost by truck/stage, impact, benchmark, model card |
| `mqtt_tag.py` | live tag from Wokwi (MQTT) or the dashboard slider (HTTP) |
| `benchmark.py` | `python benchmark.py` writes `data/benchmark_results.json` (simulation) |

## Demo timing (default 1 sim-minute per tick, after Reset + Resume)
- **Heat C-003:** excursion alert in ~2 s. **REDIRECT to Blinkit Whitefield (DS-04)** in ~7 s. Ends with ~11 h left (critical, not spoiled).
- **Compressor fail on T-3** (about 75 s after Resume): C-008 is REDIRECTed to Blinkit Koramangala in ~9 s, then **DONATEd to Feeding India Shivajinagar** in ~24 s. Fix the compressor right after the donation toast. C-008 is still accepted at the food bank (~5 h left).
- T-2 reaches R-06 about 2.4 min after Resume, and T-3 reaches R-07 about 2.9 min after Resume.
- The C-003 journey blames the **loading dock** before the heat event, and **in transit (Truck 2)** after it.

## Endpoints
See master plan 6.8. Quick checks:
```bash
curl localhost:8000/api/health
curl -X POST localhost:8000/api/sim/control -H 'content-type: application/json' -d '{"paused": false}'
curl -X POST localhost:8000/api/simulate/heat/C-003
curl localhost:8000/api/crates/C-003/journey
curl -X POST localhost:8000/api/tag/reading -H 'content-type: application/json' \
  -d '{"crate_id":"C-001","temp_c":20,"humidity":70,"voc_index":100,"door_open":false,"source":"slider"}'
```
