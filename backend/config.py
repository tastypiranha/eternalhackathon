"""FreshSense configuration: constants from master plan 6.3 + data files."""
import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = Path(__file__).parent / "freshsense.db"

# --- Simulation timing ---
TICK_SECONDS = 1.0
SIM_MINUTES_PER_TICK = 1
START_PAUSED = True

# --- Trucks / routing ---
TRUCK_SPEED_KMH = 15
ROAD_FACTOR = 1.3
STOP_SERVICE_MIN = 10
TRUCK_WAIT_TICKS = 15

# --- Environment dynamics ---
AMBIENT_C = 30
TEMP_APPROACH = 0.25
NOISE_TEMP_C = 0.2
HUMIDITY_NORMAL = 88
HUMIDITY_DOOR_OPEN = 60

# --- Scenarios ---
HEAT_EVENT_TARGET_C = 25
HEAT_EVENT_MIN = 30
DOOR_EVENT_MIN = 20

# --- Gas ---
GAS_THRESHOLD = 250
GAS_FACTOR = 1.3
SPOILED_VOC = 450

# --- Live tag ---
LIVE_TAG_ID = "C-001"
LIVE_TAG_TIMEOUT_S = 30

# --- Misc ---
BACKFILL_STEP_MIN = 10
RANDOM_SEED = 42

# --- MQTT ---
MQTT_HOST = os.environ.get("FRESHSENSE_MQTT_HOST", "broker.hivemq.com")
MQTT_PORT = int(os.environ.get("FRESHSENSE_MQTT_PORT", "1883"))
MQTT_TOPIC = os.environ.get("FRESHSENSE_MQTT_TOPIC", "freshsense/fs-CHANGE-ME/tag/C-001")
MQTT_ENABLED = os.environ.get("FRESHSENSE_MQTT_ENABLED", "1") != "0"


def _load(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


PRODUCTS: dict = _load("products.json")
LOCATIONS: dict = {loc["id"]: loc for loc in _load("locations.json")}
TRUCKS: list = _load("trucks.json")

STAGE_LABELS = {
    "farm_pickup": "Farm pickup",
    "loading_dock": "Loading dock",
    "cold_room": "Cold room",
    "in_transit": "In transit",
    "at_warehouse": "At warehouse",
}

STATUS_ORDER = ["fresh", "watch", "at_risk", "critical", "spoiled"]


def load_optional(name):
    """Return parsed JSON from data/<name> or None if missing/invalid."""
    try:
        return _load(name)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
