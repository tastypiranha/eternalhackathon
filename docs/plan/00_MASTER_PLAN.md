# FreshSense — MASTER PLAN (single source of truth)

> **Read this first.** This file is shared by all 3 team members and by any AI assistant they use.
> Each person also has their own task file (`01_PERSON_A_...`, `02_PERSON_B_...`, `03_PERSON_C_...`).
> **When giving work to an AI model, always paste BOTH this master file AND your own person file.**
> If anything in a person file seems to conflict with this file, **this file wins**.
> Section 6 ("The Contract") must not be changed without telling the whole team.

---

## 1. Hackathon facts

| Item | Value |
|---|---|
| Event | Eternal hackathon (Eternal = Zomato, Blinkit, Hyperpure, District; Feeding India is Zomato's not-for-profit) |
| Track | Reducing Food Wastage through Data & Analytics (also: Delivery Route Optimization, Inventory Optimization) |
| Time left | **16 hours**, counted as H0 → H16 |
| Evaluation 1 | **At H8** |
| Final evaluation | **At H16** |
| Team | 3 people: **A** (strongest, backend lead), **B** (frontend), **C** (data + virtual hardware + pitch; lighter, well-scoped tasks) |
| Hardware | **None.** We use a simulated ESP32 on Wokwi.com + a software simulator + real public datasets |
| Demo | Live web dashboard running on one laptop (localhost) |
| Demo city | Bengaluru. All locations, trucks, drivers and orders are **demo data** and must be labelled "(demo)" |

---

## 2. The product in plain words

**Problem:** Fresh food (chicken, milk, leafy greens) spoils faster when it gets warm. Today the cold chain only looks at the printed date. A chicken crate that sat 40 minutes in a hot loading bay is treated the same as one kept cold, so it gets rejected at the restaurant and thrown away.

**FreshSense = Sense → Predict → Act**
1. **Sense** – a tag on each crate measures temperature, humidity, smell (VOC gas), door-open and shock.
2. **Predict** – software computes, for every crate, a **Freshness Score (0–100)**, **hours of shelf life left**, and keeps the **full journey history** (every reading, split into stages: farm pickup → loading dock → cold room → truck).
3. **Act** – when a crate can no longer reach its planned destination fresh enough, FreshSense **redirects it on a live map** to the best place in the Eternal network:
   - ⚡ a **Blinkit dark store** (sells the same day),
   - 🍽️ a nearer **Zomato partner restaurant**,
   - ❤️ a **Feeding India partner** (donate food that is still safe),
   - and if nothing works, it is marked for discard and the cause is logged.

**The one sentence pitch:** *"Others tell you a crate got warm. FreshSense tells you how many hours it has left and where in the Eternal network to send it so it isn't wasted."*

---

## 3. Final design decisions (what we build and what we do NOT build)

| Decision | Final choice | Why |
|---|---|---|
| Sensors | Software simulator for 12 crates + **1 Wokwi virtual ESP32** that drives crate **C-001** live + a dashboard slider as fallback | No hardware available; Wokwi shows real firmware |
| Freshness model | **Arrhenius relative-rate model** (no "A" constant needed) + small gas (VOC) correction factor | Scientifically credible, easy to explain, no training needed |
| Real-data ML | **Model 1**: classify spoilage stage from real e-nose gas data (beef dataset). Shown on Analytics page + slides | Proves "smell detects spoilage" on REAL data |
| Model 2 (residual ML) | **Not built** (roadmap slide only) | Not worth the time with 3 people |
| Map | **Leaflet** map of Bengaluru with OpenStreetMap tiles (no API key). If internet fails, markers and lines still draw on a blank background | The redirect on a map is the "wow" moment |
| Routing | **Greedy urgency routing** (most urgent stop first). Straight lines between points. No OR-Tools | Simple, explainable, reliable |
| Real-time | **WebSocket** push every tick (1 s) + polling fallback (`GET /api/state` every 2 s) | Live feel, safe fallback |
| Database | **SQLite** (one file) for readings and events; current state in memory | Zero setup |
| Backend | Python 3.11+, FastAPI, uvicorn, paho-mqtt ≥ 2.0 | |
| Frontend | React + Vite, Tailwind CSS, react-leaflet, recharts, react-hot-toast | |
| Charts | Yes — journey history charts are required | Judges asked-for "full history" feature |
| Branding | Product name "FreshSense". Accent red `#E23744`. Eternal brand **names as text only**; do not copy official logos unless the organisers provide them | Avoid misuse of logos |
| Time compression | 1 tick = **1 real second** = **1 simulated minute** (configurable 1–10). Trucks drive at Bengaluru traffic speed (15 km/h) so trips last 2–4 sim hours = 2–4 real minutes. After every reset the simulation starts **paused**; the presenter clicks Resume | Spoilage and truck movement both visible during a 5-min demo, and trucks don't finish their trips before the demo moments |

### What we took from the earlier "buddy plan" (and kept)
- Time compression (each tick represents simulated minutes) and **seed-data tuning** so a heat event shows a visible drop within ~10 seconds.
- Unit-testing the Arrhenius engine (chicken must degrade faster than dairy at the same temperature).
- **Shock event** (bruising, mainly leafy greens).
- **FIFO vs FreshSense side-by-side dispatch table**.
- Toast alerts (`react-hot-toast`), `POST reset` endpoint, polling fallback, pre-recorded backup video, "SPOILED" crates greyed out, stress test, mock data until integration, Zomato red accent.

### What we changed from the buddy plan (and why)
- Their formula `current_rsl = base_rsl - cumulative_damage * base_rsl` mixed units and needed an unknown constant `A`. We use the **relative rate** form (Section 6.4), which needs only `Ea` and a reference temperature.
- Static SVG route diagram → **real Leaflet map** (no API key is needed for OSM/CARTO tiles).
- "Shortest route for lowest RSL" only → **redirect to the best Eternal destination** (dark store / restaurant / food bank) using a feasibility + score rule.
- "No charts" → **full journey history report** with charts.
- Added **Wokwi virtual hardware** and **one real-data ML result** (hardware + data credibility).
- Their timeline assumed 24 h with a sleep block. We have **16 h with Evaluation 1 at H8**.

---

## 4. Architecture

```
 INPUTS                                BACKEND (FastAPI, port 8000)                       FRONTEND (React, port 5173)
 ┌───────────────────────┐            ┌──────────────────────────────────────┐            ┌─────────────────────────────┐
 │ Wokwi ESP32 (C-001)   │──MQTT────▶ │ mqtt_tag.py  (latest live reading)   │            │ Live Map (Leaflet)          │
 │  DHT22 + pot + button │ HiveMQ     │                                      │            │  - locations, trucks,       │
 └───────────────────────┘ broker     │ world.py  TICK LOOP every 1 s:       │──WS /ws──▶ │    routes, redirect lines   │
 ┌───────────────────────┐            │  1. move trucks                      │  (state    │ Right panel:                │
 │ Dashboard slider      │──HTTP────▶ │  2. update crate temp/humidity/VOC   │  every     │  - alerts & redirect feed   │
 │ POST /api/tag/reading │            │  3. engine.py  freshness + hours left│  tick)     │  - FEFO vs FIFO tables      │
 └───────────────────────┘            │  4. alerts.py  alerts                │            │ Crates tab (cards)          │
 ┌───────────────────────┐            │  5. redirect.py  redirect decisions  │◀─REST───── │ Journey drawer (charts)     │
 │ Control panel buttons │──HTTP────▶ │  6. deliveries + impact counters     │            │ Analytics tab               │
 │ POST /api/simulate/*  │            │  7. save readings → SQLite (db.py)   │            │ Control panel (bottom bar)  │
 └───────────────────────┘            │  8. broadcast state                  │            └─────────────────────────────┘
                                      │ journey.py, analytics.py (REST)      │
 ┌───────────────────────┐            │ data/*.json (config + results)       │
 │ Model 1 (C, offline)  │──JSON────▶ │  model1_results.json                 │
 │ notebooks/model1_...  │  + PNGs ─▶ frontend/public/model/*.png            │
 └───────────────────────┘            └──────────────────────────────────────┘
```

---

## 5. Repository layout (one Git repo, everyone pushes to `main`, each person owns their folders)

```
freshsense/
├── README.md                         # C writes (setup + run instructions)
├── .gitignore                        # include: data/raw/, __pycache__/, node_modules/, *.db, .env
├── backend/                          # OWNER: A
│   ├── main.py                       # FastAPI app, REST routes, WebSocket, startup of tick loop
│   ├── config.py                     # constants (Section 6.3) + loads data/*.json
│   ├── engine.py                     # freshness math (Section 6.4)
│   ├── world.py                      # simulator: crates, trucks, scenarios, back-fill, tick loop
│   ├── redirect.py                   # redirect decision rules (Section 6.6)
│   ├── journey.py                    # journey report builder (Section 6.8)
│   ├── alerts.py                     # alert rules (Section 6.7)
│   ├── analytics.py                  # analytics endpoint data
│   ├── db.py                         # SQLite helpers
│   ├── mqtt_tag.py                   # MQTT subscriber for Wokwi tag
│   ├── benchmark.py                  # FIFO vs FreshSense batch simulation (Phase 2)
│   ├── tests/test_engine.py
│   ├── tests/test_redirect.py
│   ├── requirements.txt
│   └── data/
│       ├── products.json             # C creates at H0 (content in Section 6.1) — then A owns
│       ├── locations.json            # C creates at H0 (content in Section 6.2) — then A owns
│       ├── trucks.json               # C creates at H0 (content in Section 6.2) — then A owns
│       ├── model1_results.json       # C produces (Section 6.10)
│       └── benchmark_results.json    # A produces (Section 6.10)
├── frontend/                         # OWNER: B
│   ├── public/model/                 # C drops PNGs here: confusion_matrix.png, feature_importance.png, spoilage_curve.png
│   └── src/ ...                      # see Person B file
├── firmware/wokwi/                   # OWNER: C  (sketch.ino, diagram.json, libraries.txt, README.md)
├── notebooks/                        # OWNER: C  (model1_train.py)
├── data/raw/                         # OWNER: C  (downloaded datasets, git-ignored)
└── pitch/                            # OWNER: C  (slides, demo_script.md, qa_sheet.md, backup video)
```

Ports: backend `http://localhost:8000`, frontend `http://localhost:5173`.

---

## 6. THE CONTRACT (all three people code against this — do not change silently)

### 6.1 `backend/data/products.json` (exact content)

```json
{
  "chicken": {
    "id": "chicken", "label": "Chicken", "emoji": "🍗",
    "t_ref_c": 2, "shelf_life_ref_h": 96, "ea_kj_mol": 100,
    "max_safe_c": 5, "shock_penalty": 0.01, "weight_kg": 20
  },
  "dairy": {
    "id": "dairy", "label": "Dairy (milk)", "emoji": "🥛",
    "t_ref_c": 4, "shelf_life_ref_h": 168, "ea_kj_mol": 80,
    "max_safe_c": 7, "shock_penalty": 0.01, "weight_kg": 24
  },
  "greens": {
    "id": "greens", "label": "Leafy greens", "emoji": "🥬",
    "t_ref_c": 4, "shelf_life_ref_h": 120, "ea_kj_mol": 60,
    "max_safe_c": 8, "shock_penalty": 0.05, "weight_kg": 10
  }
}
```
Meaning: `shelf_life_ref_h` = total shelf life if the crate stays exactly at `t_ref_c`. `max_safe_c` = above this, it is a temperature excursion. `shock_penalty` = fraction of life lost instantly on a shock. `weight_kg` = crate weight. Values are literature-style estimates for a demo (cite "published kinetic shelf-life ranges + USDA FoodKeeper" on slides), not lab measurements.

### 6.2 `backend/data/locations.json` and `backend/data/trucks.json` (exact content)

`min_hours_needed` = the crate must still have at least this many hours left **when it arrives** for this place to accept it (restaurants keep stock ~1 day; dark stores sell same day; food banks distribute within hours). Warehouses are not redirect targets (`min_hours_needed: null`).

```json
[
  {"id":"WH-1","name":"Hyperpure Warehouse – Hoskote (demo)","type":"warehouse","area":"Hoskote","lat":13.0707,"lng":77.7982,"min_hours_needed":null,"has_cold_room":true,"demand_kg_per_day":{"chicken":0,"dairy":0,"greens":0}},
  {"id":"WH-2","name":"Hyperpure Warehouse – Bommasandra (demo)","type":"warehouse","area":"Bommasandra","lat":12.8180,"lng":77.6950,"min_hours_needed":null,"has_cold_room":true,"demand_kg_per_day":{"chicken":0,"dairy":0,"greens":0}},

  {"id":"DS-01","name":"Blinkit Dark Store – Koramangala (demo)","type":"dark_store","area":"Koramangala","lat":12.9352,"lng":77.6245,"min_hours_needed":8,"has_cold_room":false,"demand_kg_per_day":{"chicken":40,"dairy":60,"greens":30}},
  {"id":"DS-02","name":"Blinkit Dark Store – Indiranagar (demo)","type":"dark_store","area":"Indiranagar","lat":12.9784,"lng":77.6408,"min_hours_needed":8,"has_cold_room":false,"demand_kg_per_day":{"chicken":35,"dairy":50,"greens":25}},
  {"id":"DS-03","name":"Blinkit Dark Store – HSR Layout (demo)","type":"dark_store","area":"HSR Layout","lat":12.9116,"lng":77.6389,"min_hours_needed":8,"has_cold_room":false,"demand_kg_per_day":{"chicken":30,"dairy":55,"greens":30}},
  {"id":"DS-04","name":"Blinkit Dark Store – Whitefield (demo)","type":"dark_store","area":"Whitefield","lat":12.9698,"lng":77.7500,"min_hours_needed":8,"has_cold_room":false,"demand_kg_per_day":{"chicken":45,"dairy":60,"greens":20}},
  {"id":"DS-05","name":"Blinkit Dark Store – Jayanagar (demo)","type":"dark_store","area":"Jayanagar","lat":12.9250,"lng":77.5938,"min_hours_needed":8,"has_cold_room":false,"demand_kg_per_day":{"chicken":25,"dairy":45,"greens":35}},
  {"id":"DS-06","name":"Blinkit Dark Store – Malleshwaram (demo)","type":"dark_store","area":"Malleshwaram","lat":13.0035,"lng":77.5710,"min_hours_needed":8,"has_cold_room":false,"demand_kg_per_day":{"chicken":20,"dairy":40,"greens":30}},
  {"id":"DS-07","name":"Blinkit Dark Store – Hebbal (demo)","type":"dark_store","area":"Hebbal","lat":13.0358,"lng":77.5970,"min_hours_needed":8,"has_cold_room":false,"demand_kg_per_day":{"chicken":30,"dairy":35,"greens":15}},
  {"id":"DS-08","name":"Blinkit Dark Store – Electronic City (demo)","type":"dark_store","area":"Electronic City","lat":12.8452,"lng":77.6602,"min_hours_needed":8,"has_cold_room":false,"demand_kg_per_day":{"chicken":35,"dairy":45,"greens":20}},

  {"id":"R-01","name":"Zomato Partner Restaurant – MG Road (demo)","type":"restaurant","area":"MG Road","lat":12.9756,"lng":77.6050,"min_hours_needed":24,"has_cold_room":true,"demand_kg_per_day":{"chicken":30,"dairy":20,"greens":15}},
  {"id":"R-02","name":"Zomato Partner Restaurant – Marathahalli (demo)","type":"restaurant","area":"Marathahalli","lat":12.9591,"lng":77.6974,"min_hours_needed":24,"has_cold_room":true,"demand_kg_per_day":{"chicken":25,"dairy":15,"greens":10}},
  {"id":"R-03","name":"Zomato Partner Restaurant – Bellandur (demo)","type":"restaurant","area":"Bellandur","lat":12.9260,"lng":77.6762,"min_hours_needed":24,"has_cold_room":true,"demand_kg_per_day":{"chicken":20,"dairy":20,"greens":15}},
  {"id":"R-04","name":"Zomato Partner Restaurant – BTM Layout (demo)","type":"restaurant","area":"BTM Layout","lat":12.9166,"lng":77.6101,"min_hours_needed":24,"has_cold_room":true,"demand_kg_per_day":{"chicken":25,"dairy":10,"greens":20}},
  {"id":"R-05","name":"Zomato Partner Restaurant – JP Nagar (demo)","type":"restaurant","area":"JP Nagar","lat":12.9063,"lng":77.5857,"min_hours_needed":24,"has_cold_room":true,"demand_kg_per_day":{"chicken":30,"dairy":15,"greens":10}},
  {"id":"R-06","name":"Zomato Partner Restaurant – Rajajinagar (demo)","type":"restaurant","area":"Rajajinagar","lat":12.9910,"lng":77.5525,"min_hours_needed":24,"has_cold_room":true,"demand_kg_per_day":{"chicken":40,"dairy":15,"greens":10}},
  {"id":"R-07","name":"Zomato Partner Restaurant – Yelahanka (demo)","type":"restaurant","area":"Yelahanka","lat":13.1007,"lng":77.5963,"min_hours_needed":24,"has_cold_room":true,"demand_kg_per_day":{"chicken":20,"dairy":25,"greens":10}},
  {"id":"R-08","name":"Zomato Partner Restaurant – Sarjapur Road (demo)","type":"restaurant","area":"Sarjapur Road","lat":12.9010,"lng":77.6860,"min_hours_needed":24,"has_cold_room":true,"demand_kg_per_day":{"chicken":25,"dairy":20,"greens":15}},
  {"id":"R-09","name":"Zomato Partner Restaurant – KR Puram (demo)","type":"restaurant","area":"KR Puram","lat":13.0076,"lng":77.6950,"min_hours_needed":24,"has_cold_room":true,"demand_kg_per_day":{"chicken":20,"dairy":15,"greens":20}},
  {"id":"R-10","name":"Zomato Partner Restaurant – Banashankari (demo)","type":"restaurant","area":"Banashankari","lat":12.9255,"lng":77.5468,"min_hours_needed":24,"has_cold_room":true,"demand_kg_per_day":{"chicken":25,"dairy":20,"greens":15}},

  {"id":"FB-01","name":"Feeding India Partner – Shivajinagar (demo)","type":"food_bank","area":"Shivajinagar","lat":12.9857,"lng":77.6057,"min_hours_needed":2,"has_cold_room":false,"demand_kg_per_day":{"chicken":50,"dairy":50,"greens":50}},
  {"id":"FB-02","name":"Feeding India Partner – Yeshwanthpur (demo)","type":"food_bank","area":"Yeshwanthpur","lat":13.0285,"lng":77.5409,"min_hours_needed":2,"has_cold_room":false,"demand_kg_per_day":{"chicken":50,"dairy":50,"greens":50}}
]
```

`backend/data/trucks.json`:
```json
[
  {"id":"T-1","name":"Truck 1","driver":"Ravi K. (demo)","origin_id":"WH-1","setpoint_c":3,"color":"#2563EB","past_week_extra_loss_h":14,"past_week_excursions":3},
  {"id":"T-2","name":"Truck 2","driver":"Imran S. (demo)","origin_id":"WH-1","setpoint_c":3,"color":"#9333EA","past_week_extra_loss_h":9,"past_week_excursions":2},
  {"id":"T-3","name":"Truck 3","driver":"Suresh M. (demo)","origin_id":"WH-2","setpoint_c":3,"color":"#0D9488","past_week_extra_loss_h":41,"past_week_excursions":9}
]
```
(`past_week_*` are seeded demo numbers so the analytics chart is not empty at start. Truck 3 is deliberately the "problem truck".)

### 6.3 Simulation constants (`backend/config.py`)

| Constant | Value | Meaning |
|---|---|---|
| `TICK_SECONDS` | 1.0 | real seconds between ticks |
| `SIM_MINUTES_PER_TICK` | 1 | simulated minutes per tick (changeable at runtime 1–10). The engine always uses the CURRENT value |
| `START_PAUSED` | true | after startup and after every reset the sim is paused until Resume |
| `TRUCK_SPEED_KMH` | 15 | average Bengaluru traffic speed (road km per hour) |
| `ROAD_FACTOR` | 1.3 | road distance = straight-line distance × 1.3 |
| `STOP_SERVICE_MIN` | 10 | sim minutes a truck stays at each stop to unload |
| `TRUCK_WAIT_TICKS` | 15 | ticks a truck waits at its warehouse before starting a new trip |
| `AMBIENT_C` | 30 | outside temperature |
| `TEMP_APPROACH` | 0.25 | each tick, temp moves 25% of the way to its target temperature |
| `NOISE_TEMP_C` | 0.2 | ± random noise on temperature per tick |
| `HUMIDITY_NORMAL` | 88 | normal relative humidity % |
| `HUMIDITY_DOOR_OPEN` | 60 | humidity target while door open / heated |
| `HEAT_EVENT_TARGET_C` | 25 | target temp during "heat" scenario |
| `HEAT_EVENT_MIN` | 30 | sim minutes the heat scenario lasts |
| `DOOR_EVENT_MIN` | 20 | sim minutes the door scenario lasts |
| `GAS_THRESHOLD` | 250 | VOC index at or above which spoilage speeds up |
| `GAS_FACTOR` | 1.3 | spoilage speed multiplier when VOC ≥ threshold |
| `SPOILED_VOC` | 450 | VOC index at or above which crate is spoiled |
| `LIVE_TAG_ID` | "C-001" | crate driven by the Wokwi tag |
| `LIVE_TAG_TIMEOUT_S` | 30 | if no tag reading for 30 real seconds, simulator takes over C-001 again |
| `BACKFILL_STEP_MIN` | 10 | spacing of back-filled history readings |
| `RANDOM_SEED` | 42 | fixed so every reset gives the same demo |
| `MQTT_HOST` | "broker.hivemq.com" | public broker |
| `MQTT_PORT` | 1883 | |
| `MQTT_TOPIC` | "freshsense/<TEAMCODE>/tag/C-001" | team picks ONE unique code (e.g. `fs-k7q2x`) and uses it in both firmware and backend |

Simulated clock: on reset, `sim_time` = today 08:00 local, ISO format `"YYYY-MM-DDTHH:MM:SS"` (no timezone). Every tick adds `SIM_MINUTES_PER_TICK`.

### 6.4 Freshness engine (exact math — `backend/engine.py`)

```
R = 8.314                                  # J/(mol·K)
T_K      = temp_c + 273.15                 # clamp temp_c to [-5, 45] first
Tref_K   = product.t_ref_c + 273.15
rate     = exp( (Ea_kj_mol * 1000 / R) * (1/Tref_K - 1/T_K) )     # = 1.0 at t_ref; >1 when warmer
gas      = GAS_FACTOR if voc_index >= GAS_THRESHOLD else 1.0
dt_h     = SIM_MINUTES_PER_TICK / 60
consumed = consumed + dt_h * rate * gas / shelf_life_ref_h       # fraction of total life used, clamp [0, 1]
on shock : consumed = consumed + shock_penalty                    # clamp [0, 1]

hours_left              = (1 - consumed) * shelf_life_ref_h       # remaining life if kept at reference temp
hours_left_if_unchanged = hours_left / (rate * gas)               # if it stays at the CURRENT temperature
freshness_score         = round(100 * (1 - consumed), 1)
extra_loss_h (per tick) = max(0, rate*gas - 1) * dt_h             # hours of life lost BECAUSE of heat/gas
```

Status (from freshness_score):

| Status | Rule | Colour |
|---|---|---|
| `fresh` | score ≥ 70 | `#16A34A` green |
| `watch` | 40 ≤ score < 70 | `#EAB308` yellow |
| `at_risk` | 15 ≤ score < 40 | `#F97316` orange |
| `critical` | 0 < score < 15 | `#DC2626` red |
| `spoiled` | score == 0 **or** voc_index ≥ 450 | `#6B7280` grey |

`dt_h` uses the **current** runtime minutes-per-tick. Back-fill uses `BACKFILL_STEP_MIN / 60`.

Sanity values (tests must check): chicken rate at 2 °C = 1.0; chicken at 15 °C ≈ 7.2; dairy at 15 °C ≈ 3.8; chicken at 25 °C ≈ 29; chicken at 30 °C ≈ 57. **Chicken must degrade faster than dairy at the same warm temperature.**

### 6.5 Simulator behaviour (summary — details in Person A file)

- **12 crates**: **C-001 sits in the WH-1 cold room** (it carries the live Wokwi tag, never leaves, never redirected) and **11 crates ride on 3 trucks** (T-1: 3 crates, T-2: 4, T-3: 4). Seed table below. Crate IDs `C-001`…`C-012`; later crates continue `C-013`, `C-014`, …
- Each truck drives from its warehouse through its stops (straight lines) at `TRUCK_SPEED_KMH / ROAD_FACTOR` straight-line km/h. At a stop it waits `STOP_SERVICE_MIN` and delivers the crates destined there. After the last stop it returns to its warehouse (instant), waits `TRUCK_WAIT_TICKS`, loads 4 new crates and starts a new trip.
- **Stop order (greedy urgency routing):** remaining stops sorted by the smallest `hours_left` among crates destined to that stop (most urgent first); ties → nearest first. Recomputed whenever a crate on that truck is redirected.
- **Temperature dynamics per tick:** `temp += (target - temp) * TEMP_APPROACH + uniform(-NOISE_TEMP_C, +NOISE_TEMP_C)`. Target = truck `setpoint_c` normally; `HEAT_EVENT_TARGET_C` during heat; `AMBIENT_C` during door-open or compressor failure.
- **Humidity:** moves toward `HUMIDITY_NORMAL` (±1 noise) or toward `HUMIDITY_DOOR_OPEN` during door-open/heat/compressor failure.
- **VOC index (0–500):** `voc_target = 40 + 380 * consumed**2 + max(0, temp_c - max_safe_c) * 4`; `voc += (voc_target - voc) * 0.3 + uniform(-5, 5)`; clamp 0–500.
- **Live tag:** if a tag reading for `C-001` arrived in the last `LIVE_TAG_TIMEOUT_S` seconds, C-001 uses the tag's `temp_c`, `humidity`, `voc_index`, `door_open` instead of simulated values (engine math still runs).
- **History back-fill** on reset: each crate gets 24–60 simulated hours of past readings every `BACKFILL_STEP_MIN`, in stages `farm_pickup` → `loading_dock` → `cold_room`, then live readings are stage `in_transit`.

**Seed crates (after back-fill, tune history so the start values land in these ranges):**

| Crate | Product | Truck | Original destination | hours_left at start | Role in demo |
|---|---|---|---|---|---|
| C-001 | dairy | none (WH-1 cold room, stage `cold_room`) | none | 100–130 | **Live Wokwi tag crate** (status + alerts + history only) |
| C-002 | greens | T-1 | R-09 | 60–90 | |
| C-004 | chicken | T-1 | R-02 | 45–60 | |
| C-010 | dairy | T-1 | R-01 | 90–130 | |
| **C-003** | **chicken** | **T-2** | **R-06** | **27–30** | **HERO: heat → redirect to a Blinkit dark store** |
| C-005 | dairy | T-2 | R-07 | 90–130 | |
| C-006 | greens | T-2 | R-01 | 60–90 | |
| C-011 | chicken | T-2 | R-06 | 45–60 | |
| **C-007** | **greens** | **T-3** | **R-04** | **50–70** | **Shock target** |
| **C-008** | **chicken** | **T-3** | **R-07** | **31–34** | **Compressor failure → redirect, then donate** |
| C-009 | dairy | T-3 | R-10 | 90–130 | |
| C-012 | greens | T-3 | R-03 | 50–80 | |

C-003's loading-dock stage must include a **40-minute excursion at 18 °C** so its journey report blames the loading dock.

### 6.6 Redirect rules (exact — `backend/redirect.py`)

Run every tick for every crate that is on a truck (not delivered, not discarded).

```
travel_km(crate, place) = haversine_km(truck_position, place) * ROAD_FACTOR
travel_h(crate, place)  = travel_km / TRUCK_SPEED_KMH

feasible(place) =
      place.type in {"restaurant","dark_store","food_bank"}
  and place.demand_kg_per_day[product] > 0
  and crate.status != "spoiled"
  and crate.hours_left - travel_h(place) >= place.min_hours_needed

1. If feasible(current destination)  → do nothing (keep plan).      # hysteresis: never move a crate that is still OK
2. Else build candidates = all feasible places of type restaurant or dark_store.
   For each candidate:
       demand_match  = min(1, demand_kg_per_day[product] / (crate.weight_kg * 2))
       time_margin   = min(1, (hours_left - travel_h - min_hours_needed) / 24)
       distance_pen  = min(1, travel_km / 40)
       type_bonus    = 0.10 if restaurant, 0.05 if dark_store
       score         = 0.4*demand_match + 0.3*time_margin - 0.2*distance_pen + type_bonus
   If candidates exist → choose highest score → decision "REDIRECT".
3. Else if any food_bank is feasible → choose the nearest → decision "DONATE".
4. Else → decision "DISCARD" (crate removed from truck, counted as wasted, cause logged).
```

After a REDIRECT/DONATE: set `crate.destination_id`, set `crate.redirected = true`, keep `original_destination_id` unchanged, store `redirect_reason`, recompute that truck's stop order, create a redirect record and an alert. Counters: `crates_redirected += 1` (REDIRECT and DONATE), `kg_saved += weight_kg`, `rejections_avoided += 1`. On DISCARD: `kg_wasted += weight_kg`.

Reason text template (exact style):
- REDIRECT: `"Only {hours_left:.0f} h left; it would reach {original_name} with ~{arrive_h:.0f} h, below the {orig_min} h it needs. {new_name} is {travel_min:.0f} min away and sells {demand} kg {product_label}/day."`
- DONATE: `"Only {hours_left:.0f} h left — too little to sell. Still safe, so donating to {fb_name} ({travel_min:.0f} min away)."`
- DISCARD: `"Spoiled or no destination reachable in time. Logged cause: {biggest_cause_stage}."`

**Delivery rule:** when a truck reaches a stop, each crate destined there is `accepted = (hours_left >= place.min_hours_needed and status != "spoiled")`. Counters: `deliveries_completed += 1`; if not accepted `deliveries_rejected += 1` and `kg_wasted += weight_kg`.

### 6.7 Alert rules (`backend/alerts.py`)

| type | When (create once per occurrence, no repeats every tick) | severity |
|---|---|---|
| `temp_excursion` | temp_c > max_safe_c for 2 consecutive ticks (new excursion) | warning |
| `door_open` | door-open scenario starts on a truck, or live tag reports door_open turning true | warning |
| `shock` | shock scenario on a crate | warning |
| `compressor_fail` | compressor failure starts on a truck | critical |
| `status_change` | crate status gets WORSE (e.g. watch → at_risk) | warning (critical/spoiled → critical) |
| `rerouted` | REDIRECT decision | info |
| `donated` | DONATE decision | info |
| `discarded` | DISCARD decision | critical |
| `delivery_rejected` | delivery not accepted | critical |

### 6.8 REST API (all JSON; prefix `/api`; CORS allow `http://localhost:5173`)

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/health` | – | `{"ok": true}` |
| GET | `/api/state` | – | the **State object** (6.9) — same as WebSocket message (polling fallback) |
| GET | `/api/locations` | – | `{"locations": [...6.2...], "trucks": [...trucks.json...], "products": {...6.1...}}` |
| GET | `/api/crates/{crate_id}/journey` | – | **Journey object** (6.9). 404 if unknown crate. Works for delivered crates too |
| GET | `/api/analytics` | – | **Analytics object** (6.9) |
| GET | `/api/model-card` | – | contents of `model1_results.json`, or `{"available": false}` |
| POST | `/api/simulate/heat/{crate_id}` | – | `{"ok": true}` – crate target temp 25 °C for 30 sim min |
| POST | `/api/simulate/shock/{crate_id}` | – | `{"ok": true}` – applies shock penalty |
| POST | `/api/simulate/door/{truck_id}` | – | `{"ok": true}` – door open 20 sim min |
| POST | `/api/simulate/compressor/{truck_id}/fail` | – | `{"ok": true}` – compressor off until fixed |
| POST | `/api/simulate/compressor/{truck_id}/fix` | – | `{"ok": true}` |
| POST | `/api/sim/control` | `{"paused": bool?, "minutes_per_tick": int?}` | `{"ok": true, "paused":..., "minutes_per_tick":...}` |
| POST | `/api/demo/reset` | – | `{"ok": true}` – clears DB, re-seeds with RANDOM_SEED, sim_time back to 08:00, `paused = true`, `minutes_per_tick = 1` |
| POST | `/api/tag/reading` | `{"crate_id":"C-001","temp_c":float,"humidity":float,"voc_index":int,"door_open":bool,"source":"slider"}` | `{"ok": true}` – same effect as an MQTT tag message |

Errors: unknown crate/truck → HTTP 404 `{"detail": "..."}`.

WebSocket: `ws://localhost:8000/ws`. On connect the server immediately sends the current State; then one State message every tick. Clients never need to send anything.

### 6.9 Data shapes (exact field names)

**State object** (WebSocket message and `GET /api/state`):
```json
{
  "type": "state",
  "tick": 123,
  "sim_time": "2026-11-19T12:06:00",
  "paused": false,
  "minutes_per_tick": 1,
  "crates": [
    {
      "id": "C-003", "product": "chicken", "product_label": "Chicken", "emoji": "🍗", "weight_kg": 20,
      "truck_id": "T-2", "stage": "in_transit",
      "temp_c": 3.1, "humidity": 88.2, "voc_index": 72, "door_open": false,
      "freshness_score": 32.4, "hours_left": 31.1, "hours_left_if_unchanged": 30.8, "status": "at_risk",
      "loaded_at": "2026-11-19T08:00:00",
      "destination_id": "R-06", "destination_name": "Zomato Partner Restaurant – Rajajinagar (demo)",
      "original_destination_id": "R-06",
      "redirected": false, "redirect_reason": null,
      "eta_min": 74,
      "is_live_tag": false,
      "lat": 13.01, "lng": 77.70
    }
  ],
  "trucks": [
    {
      "id": "T-2", "name": "Truck 2", "driver": "Imran S. (demo)", "color": "#9333EA",
      "status": "en_route",
      "lat": 13.01, "lng": 77.70,
      "compressor_ok": true, "door_open": false, "setpoint_c": 3,
      "stops": [ {"location_id": "R-06", "crate_ids": ["C-003","C-011"], "eta_min": 74} ],
      "route_points": [[13.01, 77.70], [12.9910, 77.5525]],
      "crate_ids": ["C-003","C-005","C-006","C-011"]
    }
  ],
  "dispatch": {
    "fefo": [ {"rank": 1, "crate_id": "C-003", "product": "chicken", "hours_left": 31.1, "destination_id": "R-06", "feasible": true} ],
    "fifo": [ {"rank": 1, "crate_id": "C-001", "product": "dairy", "hours_left": 118.0, "destination_id": "R-01", "feasible": true, "would_be_rejected": false} ]
  },
  "alerts":      [ {"id": "A-17", "ts": "2026-11-19T12:04:00", "type": "temp_excursion", "severity": "warning", "crate_id": "C-003", "truck_id": "T-2", "message": "C-003 Chicken at 9.4 °C (safe ≤ 5 °C)"} ],
  "new_alerts":  [ ],
  "redirects":   [ {
      "id": "RD-3", "ts": "2026-11-19T12:06:00", "crate_id": "C-003", "truck_id": "T-2",
      "product": "chicken", "weight_kg": 20, "hours_left": 22.4,
      "decision": "REDIRECT",
      "from_location_id": "R-06", "to_location_id": "DS-04",
      "from_point": [13.01, 77.70],
      "travel_min": 23,
      "reason": "Only 22 h left; Zomato Partner Restaurant – Rajajinagar (demo) needs 24 h on arrival. Blinkit Dark Store – Whitefield (demo) is 23 min away and sells 45 kg Chicken/day.",
      "alternatives": [ {"location_id": "DS-02", "name": "Blinkit Dark Store – Indiranagar (demo)", "score": 0.61} ],
      "kg_saved": 20
  } ],
  "new_redirects": [ ],
  "deliveries":  [ {"id": "D-5", "ts": "...", "crate_id": "C-006", "location_id": "R-01", "accepted": true, "hours_left": 70.2} ],
  "impact": {
    "crates_redirected": 1, "crates_donated": 0, "kg_saved": 20, "rejections_avoided": 1,
    "deliveries_completed": 4, "deliveries_rejected": 0, "kg_wasted": 0
  }
}
```
Rules: `crates` = crates currently on trucks or waiting at a warehouse (not delivered/discarded). For C-001 (and any crate not on a truck): `truck_id`, `destination_id`, `destination_name`, `original_destination_id`, `eta_min` are `null`, `stage` = `"cold_room"`, and `lat`/`lng` = its warehouse. `alerts` = last 30 (newest first). `redirects` and `deliveries` = last 20 (newest first). `new_alerts` / `new_redirects` = only those created **in this tick** (frontend uses them for toasts and animations). `stage` ∈ `farm_pickup | loading_dock | cold_room | in_transit | at_warehouse`. Truck `status` ∈ `en_route | at_warehouse`. `route_points` = truck position followed by each remaining stop's coordinates, in order. Times are sim times. Numbers: temps 1 decimal, hours 1 decimal, scores 1 decimal.

**Journey object** (`GET /api/crates/{id}/journey`):
```json
{
  "crate": { "...same fields as a State crate, plus": "delivered (bool), delivered_to (id or null)" },
  "product": { "id": "chicken", "label": "Chicken", "t_ref_c": 2, "max_safe_c": 5, "shelf_life_ref_h": 96 },
  "summary": {
    "picked_up_at": "2026-11-17T20:00:00",
    "total_life_h": 96, "life_used_h": 64.9, "extra_loss_h": 21.3,
    "hours_left": 31.1, "freshness_score": 32.4, "status": "at_risk"
  },
  "stages": [
    {
      "stage": "loading_dock", "label": "Loading dock",
      "location_name": "Hyperpure Warehouse – Hoskote (demo) – loading dock",
      "start": "2026-11-17T21:00:00", "end": "2026-11-17T21:50:00", "duration_min": 50,
      "avg_temp_c": 15.2, "min_temp_c": 9.8, "max_temp_c": 18.3, "avg_humidity": 71.0,
      "minutes_above_limit": 40, "life_used_h": 8.1, "extra_loss_h": 7.3
    }
  ],
  "readings": [ {"ts": "...", "temp_c": 2.1, "humidity": 88.0, "voc_index": 60, "freshness_score": 80.2, "stage": "cold_room"} ],
  "excursions": [ {"start": "...", "end": "...", "minutes": 40, "peak_temp_c": 18.3, "stage": "loading_dock"} ],
  "blame": { "stage": "loading_dock", "share_pct": 65, "text": "65% of the extra freshness loss happened at Loading dock (Hyperpure Warehouse – Hoskote (demo) – loading dock)." }
}
```
Rules: `readings` downsampled to **at most 400 points**, oldest first. Stage labels: `farm_pickup`→"Farm pickup", `loading_dock`→"Loading dock", `cold_room`→"Cold room", `in_transit`→"In transit", `at_warehouse`→"At warehouse". `blame` = stage with the largest `extra_loss_h`; `share_pct` = that stage's share of total extra loss (0 if no extra loss; then text = "No significant temperature abuse recorded.").

**Analytics object** (`GET /api/analytics`):
```json
{
  "hours_lost_by_truck": [ {"truck_id": "T-3", "name": "Truck 3", "driver": "Suresh M. (demo)", "extra_loss_h": 52.4, "excursions": 11} ],
  "hours_lost_by_stage": [ {"stage": "loading_dock", "label": "Loading dock", "extra_loss_h": 80.1} ],
  "impact": { "...same as State.impact..." },
  "benchmark": null,
  "model_card": null
}
```
`hours_lost_by_truck` = trucks.json `past_week_*` numbers **plus** live in-transit extra loss and excursions since reset. `benchmark` = contents of `benchmark_results.json` or `null`. `model_card` = contents of `model1_results.json` or `null`.

### 6.10 Result files

`backend/data/model1_results.json` (produced by C):
```json
{
  "available": true,
  "dataset_name": "Electronic nose dataset for beef quality monitoring (Wijaya et al.)",
  "dataset_url": "https://data.mendeley.com/datasets/mwmhh766fc",
  "task": "Classify beef spoilage stage from gas sensor + temperature + humidity readings",
  "n_samples": 0, "n_features": 0,
  "classes": ["excellent", "good", "acceptable", "spoiled"],
  "model": "RandomForestClassifier(n_estimators=200)",
  "validation": "leave-one-beef-cut-out (GroupKFold)",
  "accuracy": 0.0, "macro_f1": 0.0,
  "top_features": ["MQ135", "MQ136", "MQ2"],
  "images": ["/model/confusion_matrix.png", "/model/feature_importance.png", "/model/spoilage_curve.png"],
  "notes": "Real lab data. Shows that low-cost gas sensors can detect spoilage stage."
}
```

`backend/data/benchmark_results.json` (produced by A, Phase 2):
```json
{
  "crates_simulated": 1000,
  "fifo":       {"rejected": 0, "kg_wasted": 0},
  "freshsense": {"rejected": 0, "kg_wasted": 0, "redirected": 0, "donated": 0},
  "rejection_reduction_pct": 0.0,
  "waste_reduction_pct": 0.0,
  "note": "Simulation with literature-based parameters, not field data."
}
```

---

## 7. Who does what (unequal split on purpose)

| Person | Load | Owns |
|---|---|---|
| **A – Backend Lead** (strongest) | ~50% | Entire backend: engine, simulator, redirect logic, journey, alerts, analytics, WebSocket, MQTT, benchmark. Also technical Q&A at judging |
| **B – Frontend** | ~35% | Entire React dashboard: map, panels, control panel, crate cards, journey drawer, analytics page. Drives the screen during the demo |
| **C – Data, Virtual Hardware & Pitch** (lighter, well-scoped) | ~15% coding + pitch | Data JSON files (copy from this file), Wokwi virtual tag (code given), Model 1 notebook (code given), slides, demo script, Q&A sheet, QA testing, backup video, README. Opens and closes the pitch |

**Rule for C's work:** nothing C does blocks A or B. If C's Wokwi or Model 1 is late, the demo still works (slider fallback, model card shows "pending").

---

## 8. Master timeline

| Time | Milestone (everyone) |
|---|---|
| H0 | Repo created by A, everyone clones. C commits the 3 data JSON files by **H0:30** |
| H1 | A's backend returns a **stub State** on `/api/state` and `/ws`; B renders mock state on the map |
| H2 | **Sync 5 min** |
| H4 | Real simulator streaming; B connected to live WebSocket. **Sync 5 min** |
| H6 | Redirect working end-to-end on the map; Wokwi (or slider) drives C-001. **Sync 5 min** |
| H7 | **Feature freeze for Evaluation 1.** Bug fixes only. Rehearse twice. C records backup video |
| **H8** | **EVALUATION 1** |
| H8:30 | Judges' feedback written down (C) and plan adjusted (all) |
| H11 | **Sync 5 min** |
| H13 | **Sync 5 min**; benchmark + model card numbers in slides |
| **H14** | **HARD FEATURE FREEZE** – nothing new after this |
| H14–H15 | `/api/demo/reset`, 3 full rehearsals, final backup video |
| H15–H16 | Pitch practice + Q&A drill |
| **H16** | **FINAL EVALUATION** |

### Evaluation 1 must-show checklist (H8)
- [ ] Data diagram slide (where each dataset/parameter comes from)
- [ ] Live map with 11 crates on 3 moving trucks + C-001 in the Hoskote cold room
- [ ] Heat C-003 → temperature rises → hours left drop → alert toast → **C-003 redirected on the map to a Blinkit dark store** (grey dashed old route, bright new route)
- [ ] FEFO vs FIFO table updates
- [ ] Crate drawer with a basic temperature + humidity history chart
- [ ] Wokwi tag (or slider) changes C-001 live
- [ ] Model 1 first accuracy number (if ready; otherwise "in progress")
- [ ] Roadmap: full journey report, analytics heatmap, donation flow, benchmark

### Final must-show checklist (H16)
- [ ] Everything above, polished
- [ ] Compressor failure on T-3 → C-008 redirected, then **donated to Feeding India**
- [ ] Shock on C-007
- [ ] Full Journey Report (stage table, safe band, excursion shading, blame line)
- [ ] Analytics: hours lost by truck/stage, impact counters, benchmark, Model 1 card
- [ ] Slides + model card (real vs simulated clearly stated)

---

## 9. Final demo script (5 minutes) — B drives the screen

| Time | Speaker | Action on screen | Words (summary) |
|---|---|---|---|
| 0:00 | C | Title slide | Hook: "This chicken crate sat 40 minutes in a hot loading bay. Today's system thinks it's as fresh as one kept cold." Problem in 2 lines |
| 0:30 | C | Hardware + data slide, then Wokwi tab | "Our tag: ESP32 + temp/humidity + gas sensor, about ₹600–900. Here is the real firmware running on a simulated ESP32." Raise DHT22 temp → C-001 reacts |
| 1:15 | B | Live map (after a fresh Reset, sim is paused). B clicks ▶ Resume | "12 crates, 3 trucks, the Eternal network: Hyperpure warehouses, Blinkit stores, Zomato restaurants, Feeding India." |
| 1:40 | B + A | Control panel: 🔥 Heat C-003 | C-003 is already #1 in the FEFO table (most urgent). Its temperature climbs, hours left drop fast, toast fires, old route greys out, new route to Blinkit lights up. A reads the reason |
| 2:30 | B + A | ❄️ Compressor fail T-3, then ✅ Fix | C-008 redirected, then donated to Feeding India. 💥 Shock C-007 |
| 3:15 | A | Open C-003 Journey Report | Stage table, chart with safe band, and the blame line. Before the heat event it blames the loading dock; after the demo heat event it blames "In transit – Truck 2". Point out both stages in the table: the 40-min loading-dock excursion and the truck heat |
| 3:50 | A | Analytics tab | Truck 3 is the problem truck; Model 1 real accuracy; benchmark % |
| 4:30 | C | Impact + pilot slide | "X kg saved today in the demo, Y% fewer rejections in simulation. Pilot: 1 warehouse, 5 trucks, 3 products, 6–8 weeks." Close |

---

## 10. Cut list (if behind, cut from the top)
1. Benchmark script (show live impact counters instead)
2. Analytics "by stage" chart
3. Crates tab (map + drawer are enough)
4. Excursion shading in charts
5. Respawning new trips after trucks finish (instead: trucks stop at last stop)

**Never cut:** live map redirect · heat event dropping hours left · journey history chart · FEFO vs FIFO table · control panel · reset button.

## 11. Risks and fallbacks

| Risk | Fallback |
|---|---|
| Wokwi or public MQTT broker blocked at venue | Dashboard "Live tag" slider posts to `/api/tag/reading` |
| Map tiles don't load (no internet) | Leaflet still draws markers and lines on a blank background |
| WebSocket fails | Frontend polls `GET /api/state` every 2 s |
| Demo state gets messy | `POST /api/demo/reset` (fixed random seed, same demo every time) |
| Live demo crashes | Backup video recorded at H7:30 and H15 |
| Dataset download fails | Model 1 uses the backup fruit dataset, or model card says "pending"; demo unaffected |
| Judge: "your data is fake" | Model 1 = real lab data; fleet = simulation, clearly labelled; pilot provides real labels |

## 12. Datasets & references (for slides and Model 1)
- Beef e-nose time series (primary for Model 1): https://data.mendeley.com/datasets/mwmhh766fc
- Beef e-nose classification/regression version: https://data.mendeley.com/datasets/4n23zp92b5
- ESP32 + MQ sensors beef dataset (same hardware class as our tag): https://data.mendeley.com/datasets/n8mc3nspfn
- Fruit spoilage IoT cold storage (backup for Model 1): https://data.mendeley.com/datasets/czz68d9fwj
- Strawberry cold chain time-temperature dataset (reference for realistic temperatures): https://arxiv.org/abs/2103.12895
- USDA FSIS FoodKeeper (shelf-life reference): https://catalog.data.gov/dataset/fsis-foodkeeper-data
- Map tiles: © OpenStreetMap contributors
