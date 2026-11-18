"""FreshSense configuration.

Model parameters are NOT here: they come from data/calibration.json (built from public datasets by
calibration/build.py). This file only holds simulation timing and the operational assumptions for which no
public data exists (they live in data/assumptions.json and the location/truck files).
"""
import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = Path(__file__).parent / "freshsense.db"


def _load(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


ASSUMPTIONS = _load("assumptions.json")

# --- Simulation timing (presentation controls, not model parameters) ---
TICK_SECONDS = 1.0
SIM_MINUTES_PER_TICK = 1
START_PAUSED = True
BACKFILL_STEP_MIN = 10          # = resolution of the real temperature traces
RANDOM_SEED = 42                # first seed tried; reset searches upward for a demo-ready stock (see world.py)
SEED_SEARCH_LIMIT = 4000        # searched once, result saved to data/demo_seed.json (tied to the calibration version)

# --- Operational assumptions (no public data; see data/assumptions.json) ---
TRUCK_SPEED_KMH = ASSUMPTIONS["truck_speed_kmh"]
ROAD_FACTOR = ASSUMPTIONS["road_factor"]
STOP_SERVICE_MIN = ASSUMPTIONS["stop_service_min"]
TRUCK_WAIT_TICKS = ASSUMPTIONS["truck_wait_ticks"]
DOCK_DWELL_MIN = ASSUMPTIONS["loading_dock_dwell_min"]
CRATES_PER_TRUCK = ASSUMPTIONS["crates_per_truck"]

# --- Live tag ---
LIVE_TAG_ID = "C-001"
LIVE_TAG_TIMEOUT_S = 30

# --- MQTT ---
MQTT_HOST = os.environ.get("FRESHSENSE_MQTT_HOST", "broker.hivemq.com")
MQTT_PORT = int(os.environ.get("FRESHSENSE_MQTT_PORT", "1883"))
MQTT_TOPIC = os.environ.get("FRESHSENSE_MQTT_TOPIC", "freshsense/fs-CHANGE-ME/tag/C-001")
MQTT_ENABLED = os.environ.get("FRESHSENSE_MQTT_ENABLED", "1") != "0"

LOCATIONS: dict = {loc["id"]: loc for loc in _load("locations.json")}
TRUCKS: list = _load("trucks.json")

STAGE_LABELS = {
    "farm_pickup": "Pickup & pre-cooling",
    "loading_dock": "Loading dock",
    "cold_room": "Cold room",
    "in_transit": "In transit",
    "at_warehouse": "At warehouse",
}
STATUS_ORDER = ["fresh", "watch", "at_risk", "critical", "spoiled"]


def load_optional(name):
    try:
        return _load(name)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
