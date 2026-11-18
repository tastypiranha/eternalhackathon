# PERSON A — Backend Lead (strongest member, ~50% of the build)

> **For the AI assistant reading this:** you are helping Person A build the FreshSense backend in Python.
> You MUST also have `00_MASTER_PLAN.md`. **Section 6 of the master plan is the contract**: field names, endpoint paths, JSON shapes, constants and formulas there are final. Do not rename fields, change units, or invent new endpoints the frontend doesn't know about. If something is unclear, choose the simplest option consistent with the master plan and write a `# NOTE:` comment.

---

## 1. Your mission

Build a FastAPI backend that:
1. Simulates 12 crates (11 on 3 moving trucks + C-001 in a cold room) with temperature, humidity, VOC, door and shock.
2. Computes freshness every tick with the Arrhenius engine (master 6.4).
3. Keeps full history in SQLite and serves a journey report (master 6.9).
4. Raises alerts (master 6.7).
5. Redirects crates to the best Eternal destination (master 6.6) and re-orders truck stops.
6. Pushes the full State to the frontend every tick over WebSocket (master 6.9).
7. Accepts live tag readings from the Wokwi ESP32 over MQTT and from the dashboard slider over HTTP.
8. (Phase 2) Serves analytics and produces a FIFO-vs-FreshSense benchmark.

You also: create the repo at H0, unblock B and C quickly, tune the demo numbers, and answer technical questions from judges.

---

## 2. Setup (H0 – H0:30)

```bash
mkdir freshsense && cd freshsense && git init
mkdir -p backend/data backend/tests frontend firmware/wokwi notebooks data/raw pitch
python3 -m venv .venv && source .venv/bin/activate
```

`backend/requirements.txt`:
```
fastapi>=0.110
uvicorn[standard]>=0.29
paho-mqtt>=2.0
pytest>=8.0
```

`.gitignore`:
```
.venv/
__pycache__/
*.db
node_modules/
data/raw/
.env
dist/
```

Run command (from `backend/`): `uvicorn main:app --reload --port 8000`
(While the tick loop is running, `--reload` restarts the world whenever you save a file. That's fine during development. During the demo, run **without** `--reload`.)

Push the empty skeleton immediately and tell B and C the repo URL.

**Very important rule for all endpoints:** declare every route handler as `async def`. Then all handlers and the tick loop run on the same asyncio thread, so you never get two pieces of code changing the world at the same time. A plain `def` handler would run in a thread pool and could race with the tick loop. The only other thread is the MQTT thread, and it only writes to a small dict protected by a `threading.Lock`.

---

## 3. Step-by-step build plan (Phase 1: H0 → H8)

### Step A1 (H0:30 – H1:00): Stub API so B can start immediately
- `main.py` with FastAPI, CORS (`allow_origins=["http://localhost:5173"]`, all methods and headers).
- `GET /api/health` → `{"ok": true}`.
- `GET /api/state` → return a **hard-coded example State** copied from master 6.9 (expanded to 2 crates and 1 truck).
- `GET /api/locations` → read `data/locations.json`, `data/trucks.json`, `data/products.json` (C commits these by H0:30; if they're late, copy them from master 6.1/6.2 yourself).
- `WS /ws` → on connect, send the stub state every 1 s.

**Done when:** `curl localhost:8000/api/state` returns JSON, and B can connect to `ws://localhost:8000/ws`. Push.

### Step A2 (H1:00 – H2:00): `config.py` + `engine.py` + tests
`config.py`: all constants from master 6.3 as module-level variables. Load the three JSON files into `PRODUCTS` (dict), `LOCATIONS` (dict by id), `TRUCKS` (list). Read `MQTT_TOPIC` from the environment variable `FRESHSENSE_MQTT_TOPIC`, defaulting to `"freshsense/fs-CHANGE-ME/tag/C-001"`.

`engine.py`: pure functions, no global state.
```python
import math
R = 8.314

def rate(temp_c: float, product: dict) -> float:
    t = min(45.0, max(-5.0, temp_c))
    T = t + 273.15
    Tref = product["t_ref_c"] + 273.15
    return math.exp((product["ea_kj_mol"] * 1000 / R) * (1 / Tref - 1 / T))

def gas_factor(voc_index: float) -> float:
    return GAS_FACTOR if voc_index >= GAS_THRESHOLD else 1.0

def step(consumed: float, temp_c: float, voc_index: float, dt_h: float, product: dict) -> tuple[float, float, float]:
    """Returns (new_consumed, effective_rate, extra_loss_h)."""
    r = rate(temp_c, product) * gas_factor(voc_index)
    new = min(1.0, max(0.0, consumed + dt_h * r / product["shelf_life_ref_h"]))
    extra = max(0.0, r - 1.0) * dt_h
    return new, r, extra

def derived(consumed: float, effective_rate: float, voc_index: float, product: dict) -> dict:
    hours_left = (1 - consumed) * product["shelf_life_ref_h"]
    score = round(100 * (1 - consumed), 1)
    if score <= 0 or voc_index >= SPOILED_VOC: status = "spoiled"
    elif score < 15: status = "critical"
    elif score < 40: status = "at_risk"
    elif score < 70: status = "watch"
    else: status = "fresh"
    return {
        "hours_left": round(hours_left, 1),
        "hours_left_if_unchanged": round(hours_left / max(effective_rate, 1e-6), 1),
        "freshness_score": score,
        "status": status,
    }
```

`tests/test_engine.py` (run with `pytest` from `backend/`):
- `rate(2, chicken) == pytest.approx(1.0)`
- `rate(15, chicken) == pytest.approx(7.2, rel=0.05)`
- `rate(15, dairy) == pytest.approx(3.8, rel=0.05)`
- `rate(25, chicken) == pytest.approx(29, rel=0.07)`
- `rate(15, chicken) > rate(15, dairy)`
- 60 one-minute steps at `t_ref` consume exactly 1 hour: `consumed * 96 ≈ 1.0` for chicken.
- Status thresholds: 70→fresh, 69.9→watch, 39.9→at_risk, 14.9→critical, 0→spoiled, voc 450→spoiled.

**Done when:** all tests pass.

### Step A3 (H2:00 – H4:00): `db.py` + `world.py` (the simulator)

**`db.py`:** one `sqlite3` connection (`check_same_thread=False`), file `freshsense.db`.
```sql
CREATE TABLE IF NOT EXISTS readings (
  crate_id TEXT, ts TEXT, stage TEXT, location_name TEXT, truck_id TEXT,
  temp_c REAL, humidity REAL, voc_index REAL, door_open INTEGER,
  consumed REAL, freshness_score REAL, eff_rate REAL, extra_loss_h REAL, minutes REAL
);
CREATE INDEX IF NOT EXISTS idx_readings_crate ON readings(crate_id, ts);
```
Functions: `reset_db()` (drop + create), `insert_readings(rows: list[tuple])` using `executemany`, followed by one `commit()` per tick, and `get_readings(crate_id) -> list[dict]`. Events (alerts, redirects, deliveries) can stay in memory lists. They don't need the DB.

**`world.py`:** suggested data structures (dataclasses or plain dicts):

```
Crate: id, product (key), weight_kg, truck_id|None, warehouse_id|None, stage,
       temp_c, humidity, voc_index, door_open, consumed, eff_rate,
       status, loaded_at, destination_id, original_destination_id,
       redirected, redirect_reason, heat_until (sim datetime | None),
       excursion_ticks (int), in_excursion (bool), last_status,
       delivered (bool), delivered_to, discarded (bool)

Truck: id, name, driver, color, origin_id, setpoint_c, lat, lng,
       status ("en_route" | "at_warehouse"), stops: list[{location_id, crate_ids}],
       service_left_min (unloading timer), wait_ticks,
       compressor_ok (bool), door_until (sim datetime | None),
       live_extra_loss_h, live_excursions

World: sim_time, tick, paused, minutes_per_tick, crates {id: Crate},
       archive {id: Crate} (delivered/discarded), trucks {id: Truck},
       alerts [], redirects [], deliveries [], new_alerts [], new_redirects [],
       impact {...}, rng = random.Random(RANDOM_SEED), next_crate_num, counters for ids
```

#### `World.reset()`
1. `db.reset_db()`. Create `rng = random.Random(RANDOM_SEED)`. `sim_time` = today at 08:00. `tick = 0`. `paused = START_PAUSED`. `minutes_per_tick = SIM_MINUTES_PER_TICK`. Clear lists and impact counters (all zero).
2. Create the trucks from `trucks.json` at their origin warehouse coordinates, `status = "en_route"`.
3. Create the 12 seed crates exactly as in the master 6.5 seed table. For each crate, pick `target_hours_left = rng.uniform(lo, hi)` from its range.
4. **Back-fill** each crate's history (see below), then set its current temp, humidity, VOC and consumed from the last back-filled reading.
5. Assign the crates on each truck to stops (grouped by destination), then call `order_stops(truck)`.
6. C-001: `truck_id=None`, `warehouse_id="WH-1"`, `stage="cold_room"`, no destination.

#### Back-fill algorithm (deterministic: lands exactly on the target hours_left)
Stages, with readings every `BACKFILL_STEP_MIN` (10) minutes. Temperature for each reading = stage target + `rng.uniform(-0.3, 0.3)` (set directly, no smoothing). Humidity = stage humidity ± 1.

| Stage | location_name | Duration | Target temp | Humidity |
|---|---|---|---|---|
| `farm_pickup` | `"Supplier pickup – Hoskote farm cluster (demo)"` | 60 min | 8 °C | 80 |
| `loading_dock` | `"<warehouse name> – loading dock"` | 40–60 min (rng) | rng.uniform(9, 16) °C | 70 |
| `cold_room` | `"<warehouse name> – cold room"` | computed (below) | product `t_ref_c` | 88 |

- **C-003 special case:** loading dock = 50 min. The first 40 min are at 18 °C, the last 10 min at 10 °C.
- Start with `consumed = rng.uniform(0.0, 0.04)`. Run the farm and dock stages through `engine.step` with `dt_h = 10/60`.
- Then compute the cold-room duration so the crate lands on its target: at `t_ref` the rate ≈ 1, so `cold_hours = max(2, ((1 - target_hours_left / SL) - consumed_after_dock) * SL)`. Round to a multiple of 10 min and run those cold-room steps.
- The first reading's timestamp = `sim_time - total_duration`. Write every reading to the DB with `truck_id = None`.
- VOC during back-fill uses the master 6.5 VOC formula with smoothing 0.3 (start at 40).

Print one line per crate after reset: `C-003 chicken hours_left=28.6 score=29.8 status=at_risk`. Check every crate lands inside its range in master 6.5.

#### `World.tick()` — runs once per second unless paused
```
dt_min = minutes_per_tick ; dt_h = dt_min / 60
sim_time += dt_min ; tick += 1 ; new_alerts = [] ; new_redirects = []
1. expire scenarios: crate.heat_until / truck.door_until <= sim_time → None
2. move trucks (see "Truck movement")
3. for each active crate:
     target_temp, target_hum = targets(crate)          # see below
     if crate.id == LIVE_TAG_ID and live tag reading is fresh (≤ LIVE_TAG_TIMEOUT_S real seconds):
         temp, humidity, voc, door = values from the tag
     else:
         temp += (target_temp - temp) * TEMP_APPROACH + rng.uniform(-NOISE_TEMP_C, NOISE_TEMP_C)
         humidity += (target_hum - humidity) * 0.3 + rng.uniform(-1, 1)
         voc_target = 40 + 380 * consumed**2 + max(0, temp - max_safe_c) * 4
         voc += (voc_target - voc) * 0.3 + rng.uniform(-5, 5) ; clamp 0..500
     consumed, eff_rate, extra = engine.step(consumed, temp, voc, dt_h, product)
     derived = engine.derived(...)
     if crate is on a truck: truck.live_extra_loss_h += extra
     queue a DB row (stage, location_name = truck name or cold room name, truck_id, ..., minutes = dt_min)
4. alerts.check(world, crate)        # excursions, status changes (master 6.7)
5. redirect.evaluate(world)          # master 6.6, for crates on trucks only
6. db.insert_readings(rows)
7. build dispatch lists (see below)
```

`targets(crate)`:
- Crate in a warehouse (C-001, or crates waiting to load): `t_ref_c`, `HUMIDITY_NORMAL`.
- `crate.heat_until` active: `HEAT_EVENT_TARGET_C`, `HUMIDITY_DOOR_OPEN`.
- Its truck has `compressor_ok == False` or the door open: `AMBIENT_C`, `HUMIDITY_DOOR_OPEN`.
- Otherwise: truck `setpoint_c`, `HUMIDITY_NORMAL`.
- `crate.door_open` = its truck's door state (C-001 takes it from the live tag).

#### Truck movement (straight lines)
```
haversine_km(lat1,lng1,lat2,lng2)  # standard formula, Earth radius 6371 km
step_km = (TRUCK_SPEED_KMH / ROAD_FACTOR) * dt_h           # straight-line km per tick
if truck.status == "at_warehouse":
    wait_ticks -= 1 ; if wait_ticks <= 0: load_new_trip(truck) ; status = "en_route"
elif truck.service_left_min > 0:
    service_left_min -= dt_min ; if it reaches <= 0: deliver(truck, current stop) ; pop stop
elif stops:
    target = LOCATIONS[stops[0].location_id]
    d = haversine_km(truck, target)
    if d <= step_km: snap truck to target ; service_left_min = STOP_SERVICE_MIN
    else: move fraction f = step_km / d along the line: lat += (tlat-lat)*f ; lng += (tlng-lng)*f
else:  # no stops left
    teleport to origin warehouse ; status = "at_warehouse" ; wait_ticks = TRUCK_WAIT_TICKS
```
`deliver(truck, stop)`: for each crate in `stop.crate_ids` apply the master 6.6 delivery rule. Record `{"id": "D-n", "ts", "crate_id", "location_id", "accepted", "hours_left"}`, update the impact counters, and add a `delivery_rejected` alert if not accepted. Move the crate to `archive` with `delivered=True, delivered_to=location_id`.

`load_new_trip(truck)`: create 4 new crates (`C-013`, `C-014`, …). Pick a random product, a random **restaurant** destination, and `target_hours_left = rng.uniform(0.5, 0.9) * SL`. Back-fill 12–24 h with the same algorithm, then assign stops and call `order_stops`. **If you're short on time, skip respawning** (cut list item 5): trucks just stay at their warehouse.

#### `order_stops(truck)` (greedy urgency routing)
For each remaining stop: `urgency = min(hours_left of crates in that stop)`. Sort by `(urgency, distance from truck)` ascending. **Never re-order a stop the truck is currently unloading at** (`service_left_min > 0`). Keep it first.

#### ETA
Walk the route from the truck through the stops in order: `eta_min += road_km / TRUCK_SPEED_KMH * 60 + STOP_SERVICE_MIN` (count the service time for the stops before this one). Crate `eta_min` = the ETA of its stop.

#### `World.to_state()` → master 6.9 State object
- `crates`: active crates only, with all fields from master 6.9. `lat`/`lng` = the truck position (or the warehouse for C-001). `destination_name` comes from LOCATIONS.
- `trucks`: as in master. `route_points = [[truck.lat, truck.lng]] + [[stop.lat, stop.lng] for each stop]`.
- `dispatch.fefo`: crates on trucks sorted by `hours_left` ascending, with `feasible` = master 6.6 `feasible(current destination)`.
- `dispatch.fifo`: the same crates sorted by `loaded_at` ascending (tie → id), showing the **original** destination, with `would_be_rejected = not feasible(original destination)`.
- `alerts` last 30 and `redirects`/`deliveries` last 20, newest first. Also `new_alerts`, `new_redirects` and `impact`.
- Round numbers as master says.

**Done when (H4):** after a reset and Resume, the WebSocket streams real changing state. Trucks move across Bengaluru, temperatures hover near 3 °C, and the hours-left values match the seed ranges. B is connected to it. Push.

### Step A4 (H4:00 – H5:00): Scenario endpoints + `alerts.py`
- Implement every `/api/simulate/*`, `/api/sim/control` and `/api/demo/reset` from master 6.8. Unknown id → `HTTPException(404)`.
  - heat: `crate.heat_until = sim_time + HEAT_EVENT_MIN`
  - shock: `consumed += shock_penalty`, plus a `shock` alert
  - door: `truck.door_until = sim_time + DOOR_EVENT_MIN`, plus a `door_open` alert
  - compressor fail/fix: toggle `compressor_ok`, plus a `compressor_fail` alert on fail
- `alerts.py`: master 6.7 rules. Alert ids are `A-1, A-2, …`. Message examples:
  - `"C-003 Chicken at 9.4 °C (safe ≤ 5 °C)"`
  - `"C-003 status worsened: watch → at_risk (22.0 h left)"`
  - `"Truck 3 compressor failure — 4 crates warming"`
  - `"C-003 rerouted to Blinkit Dark Store – Whitefield (demo)"`
- Excursion tracking: if `temp > max_safe_c`, `excursion_ticks += 1`. When it reaches 2 and `in_excursion` is False, raise an alert, set `in_excursion = True` and (if the crate is on a truck) `truck.live_excursions += 1`. When the temp drops back to `max_safe_c` or below, reset both.
- Status change: compare to `last_status` using the order `fresh < watch < at_risk < critical < spoiled`. Alert only when it gets worse.

**Done when:** `curl -X POST localhost:8000/api/simulate/heat/C-003` makes C-003's temp climb toward 25 °C, an excursion alert appears within ~3 ticks, and hours_left drops visibly.

### Step A5 (H5:00 – H6:00): `redirect.py`
Implement master 6.6 **exactly**. Function `evaluate(world)`:
```
for crate in crates on trucks (not delivered/discarded):
    if feasible(crate, current destination): continue
    decide REDIRECT / DONATE / DISCARD
    apply decision:
        remove crate from its old stop (drop the stop if it is now empty, unless it is being unloaded)
        add it to the new destination's stop (create the stop if needed)
        crate.destination_id = new ; crate.redirected = True ; crate.redirect_reason = reason
        record = {id "RD-n", ts, crate_id, truck_id, product, weight_kg, hours_left, decision,
                  from_location_id (old dest), to_location_id, from_point [truck.lat, truck.lng],
                  travel_min, reason, alternatives (next 2 by score: location_id, name, score rounded 2), kg_saved}
        world.redirects.insert(0, record) ; world.new_redirects.append(record)
        alert "rerouted" / "donated" / "discarded"
        update impact counters (crates_donated += 1 for DONATE as well)
        order_stops(truck)
DISCARD: crate.discarded = True ; remove from truck ; move to archive ; to_location_id = None
```
`travel_h` uses `haversine_km(truck position, place) * ROAD_FACTOR / TRUCK_SPEED_KMH`.
For the DISCARD reason's `{biggest_cause_stage}`, use the journey blame stage (or "in_transit" if that's simpler).

`tests/test_redirect.py`: build a tiny world by hand (one truck, one crate):
- A crate with plenty of hours left keeps its destination.
- A chicken crate with 15 h left heading to a restaurant (needs 24) is REDIRECTed to a dark store.
- A crate with 5 h left is DONATEd to a food bank.
- A spoiled crate is DISCARDed.

**Done when:** tests pass. After a reset + Resume + heat on C-003, within ~15 seconds C-003 gets a REDIRECT to a Blinkit dark store and appears in `new_redirects`.

### Step A6 (H6:00 – H7:00): `journey.py`, `mqtt_tag.py`, `/api/tag/reading`
**`journey.py` → `build_journey(world, crate_id)`** (master 6.9 Journey object):
- Get the crate from `crates` or `archive` (404 if missing). Read all readings from the DB, oldest first.
- Group consecutive readings by `stage` (and, for `in_transit`, by `truck_id`) into stage blocks. For each block compute start, end, `duration_min` (sum of `minutes`), avg/min/max temp, avg humidity, `minutes_above_limit` (sum of `minutes` where `temp_c > max_safe_c`), `life_used_h` (difference in `consumed` across the block × SL; for the first block use consumed at start ≈ the first reading), and `extra_loss_h` (sum).
- Excursions: consecutive readings with `temp_c > max_safe_c` → `{start, end, minutes, peak_temp_c, stage}`.
- Blame: the stage block with the max `extra_loss_h`, as in master.
- Downsample readings to ≤ 400 by taking every k-th row (always include the last one).
- Summary: `picked_up_at` = first reading ts, `total_life_h` = SL, `life_used_h` = consumed × SL, `extra_loss_h` = total.

**`mqtt_tag.py`:**
```python
import json, threading, time
import paho.mqtt.client as mqtt
from config import MQTT_HOST, MQTT_PORT, MQTT_TOPIC

_lock = threading.Lock()
_latest: dict = {}

def get_latest() -> dict | None:
    with _lock:
        if _latest and time.time() - _latest.get("received_at", 0) <= LIVE_TAG_TIMEOUT_S:
            return dict(_latest)
    return None

def put_reading(data: dict):            # also used by POST /api/tag/reading
    with _lock:
        _latest.clear(); _latest.update(data); _latest["received_at"] = time.time()

def _on_connect(client, userdata, flags, reason_code, properties):
    client.subscribe(MQTT_TOPIC)

def _on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        put_reading(data)
    except Exception:
        pass

def start():
    try:
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        c.on_connect = _on_connect; c.on_message = _on_message
        c.connect_async(MQTT_HOST, MQTT_PORT); c.loop_start()
    except Exception as e:
        print("MQTT disabled:", e)      # never crash the backend because of MQTT
```
- `start()` is called once at app startup. `POST /api/tag/reading` calls `put_reading(body)`.
- When live, add `is_live_tag: true` to C-001 in the State (always true for C-001 is fine). When the tag's `door_open` flips to true, raise a `door_open` alert.

**Startup/tick loop in `main.py`** (FastAPI lifespan):
```python
@asynccontextmanager
async def lifespan(app):
    world.reset(); mqtt_tag.start()
    task = asyncio.create_task(tick_loop())
    yield
    task.cancel()

async def tick_loop():
    while True:
        await asyncio.sleep(TICK_SECONDS)
        try:
            if not world.paused: world.tick()
            await manager.broadcast(world.to_state())
        except Exception as e:
            import traceback; traceback.print_exc()   # never let the loop die
```
`manager.broadcast` sends JSON to every connected socket and drops sockets that error. On a new connection, send `world.to_state()` immediately. Keep the socket open with `while True: await ws.receive_text()` inside `try/except WebSocketDisconnect`.

**Done when:** a Wokwi message (ask C) or `curl -X POST localhost:8000/api/tag/reading -H 'content-type: application/json' -d '{"crate_id":"C-001","temp_c":20,"humidity":70,"voc_index":100,"door_open":false,"source":"slider"}'` makes C-001 show 20 °C within 1–2 s. `GET /api/crates/C-003/journey` returns stages including the loading dock with ~40 minutes above the limit, and the blame stage is `loading_dock` before any live heat event.

### Step A7 (H7:00 – H8:00): Demo tuning + freeze for Evaluation 1
Run this exact sequence three times after a reset:
1. Resume. Wait 20 s. Heat C-003. **Expect:** excursion alert in ≤ 5 s, REDIRECT to a dark store within ~15 s of the heat starting, and C-003 still not spoiled afterwards (hours_left should land around 12–20 h).
2. If the redirect is too slow or too fast, adjust in this order: C-003's `target_hours_left` range (master allows 27–30), then `HEAT_EVENT_MIN`. Tell B and C about any constant you change.
3. Check the trip timing at 1 min/tick: T-2 should reach R-06 about 2.4 real minutes after Resume, and T-3 should reach R-07 about 2.9 minutes after Resume. (Expected: 36 km and 43 km road distance at 15 km/h.) If they arrive much earlier, the demo moments at 1:40 and 2:30 come too late, so check your speed and road-factor math.

Freeze at H7:15, then fix bugs only. Rehearse with the team.

---

## 4. Phase 2 (H8 → H16)

### Step A8 (H8:30 – H10:00): Analytics, model card, robustness
- `GET /api/analytics` (master 6.9):
  - `hours_lost_by_truck` = `past_week_extra_loss_h + live_extra_loss_h` and `past_week_excursions + live_excursions`, sorted descending.
  - `hours_lost_by_stage` = SQL `SELECT stage, SUM(extra_loss_h) FROM readings GROUP BY stage`.
  - Include `impact`, plus `benchmark` and `model_card` (from the JSON files if they exist, else null).
- `GET /api/model-card` → the file contents or `{"available": false}`.
- Edge cases: a spoiled crate on a truck → the redirect rule gives DISCARD. Make sure nothing crashes when a truck has zero crates, or when all crates are critical. Avoid division by zero in the scores.

### Step A9 (H10:00 – H11:30): Compressor cascade tuning + `benchmark.py`
**Compressor scenario check** (after reset + Resume, wait 20 s, compressor fail on T-3):
- **Expected:** C-008 is REDIRECTed to a dark store, then (if the fault isn't fixed) DONATEd to a Feeding India partner within ~40 s.
- After "fix", C-008 should still be accepted at the food bank (hours_left ≥ 2 on arrival). If it spoils too fast, raise C-008's start range within 31–34 or lower `AMBIENT_C` to 28. Document the final numbers for C's demo script.

**`benchmark.py`** (standalone script, `python benchmark.py` → writes `data/benchmark_results.json`, schema in master 6.10). It reuses the `engine` functions and `LOCATIONS`:
```
rng = Random(7); N = 1000
for each crate:
    product = random; SL = shelf life
    hours_left = uniform(0.35, 0.9) * SL                     # at dispatch
    original = random restaurant; travel_h = uniform(1.0, 3.0)
    with probability 0.30: an excursion → hours_left -= uniform(5, 30)   (clamp ≥ 0)
    FIFO:       rejected if hours_left - travel_h < 24  → kg_wasted += weight
    FreshSense: if hours_left - travel_h >= 24 → delivered OK
                elif hours_left - uniform(0.3, 1.0) >= 8  → redirected (saved)
                elif hours_left - uniform(0.3, 1.5) >= 2  → donated (saved)
                else → rejected/wasted
rejection_reduction_pct = 100 * (fifo.rejected - fs.rejected) / max(1, fifo.rejected)
waste_reduction_pct     = same using kg
```
Print the summary. Tell C the two percentages for the slides, and label them "simulation".

### Step A10 (H11:30 – H13:00): Hardening
- **Stress test:** heat 10 crates in a row quickly. The server stays responsive and every tick takes < 100 ms (log the tick duration).
- `POST /api/demo/reset` works repeatedly, giving an identical start every time thanks to the fixed seed.
- Log one line per tick at most when debugging. Remove noisy prints before the demo.
- Write `backend/README.md`: setup, run, env var `FRESHSENSE_MQTT_TOPIC`, endpoints list.

### Step A11 (H13:00 – H14:00): Bug fixes with B, final freeze at H14
### H14 – H16: Rehearse. You present "how the brain decides" (engine + redirect rule) and the journey/analytics parts. You also answer technical Q&A.

**Stretch (only if everything above is done and frozen code is safe):** real road geometry via the public OSRM demo server for `route_points`, a cold-room rescue rule, Model 2.

---

## 5. Things you must NOT do
- Don't rename any field or endpoint in master section 6. B codes against them.
- Don't use plain `def` route handlers (race conditions with the tick loop).
- Don't let an exception in one tick kill the loop. Wrap it in try/except and print the traceback.
- Don't make MQTT failures crash the app.
- Don't add authentication, Docker or deployment. Localhost only.
- Don't push large DB files. `*.db` is git-ignored.

## 6. Your checkpoints (report at each sync)
| Time | You must have |
|---|---|
| H1 | Stub `/api/state` + `/ws` + `/api/locations` working, pushed |
| H2 | Engine + tests passing |
| H4 | Real simulator streaming over WS; trucks moving |
| H6 | Scenarios + alerts + redirect working; C-003 redirect visible on B's map |
| H7 | Journey endpoint + live tag (MQTT + HTTP); freeze |
| H11 | Analytics + model card endpoint + compressor cascade tuned |
| H13 | Benchmark numbers delivered to C; stress test passed |
| H14 | Frozen |
