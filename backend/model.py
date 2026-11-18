"""Data-calibrated freshness model.

Everything numeric comes from backend/data/calibration.json, produced by calibration/build.py from public
datasets. The state of a crate is its bacterial load (TVC, log CFU/g). It grows at the Ratkowsky rate
mu(T) = (b * (T - Tmin))^2, with b fitted to real beef spoilage curves and scaled per product by
USDA FoodKeeper fridge shelf lives. A crate is spoiled at the TVC threshold found in the labelled data.
"""
import json
import math
from pathlib import Path

import numpy as np

BASE = Path(__file__).parent
CAL = json.loads((BASE / "data" / "calibration.json").read_text())
PROFILES = json.loads((BASE.parent / "data" / "processed" / "event_profiles.json").read_text())

TMIN = CAL["literature"]["ratkowsky_tmin_c"]
REF_T = CAL["reference_temp_c"]
THRESHOLDS = CAL["stage_thresholds_log_cfu"]          # excellent | good | acceptable | spoiled
SPOIL = CAL["spoilage_threshold_log_cfu"]
TVC0 = CAL["initial_tvc_log_cfu"]["median"]
TVC0_VALUES = CAL["initial_tvc_log_cfu"]["values"]
STAGES = CAL["stage_names"]
PRODUCTS = CAL["products"]
SIM_PRODUCTS = [p for p, v in PRODUCTS.items() if v["simulate"]]
W_KIN = CAL["fusion"]["weight_kinetic"]
AMBIENT_C = PROFILES["ambient_c"]["value"]
MAX_HOURS = 9999.0
MAX_TVC = CAL.get("max_tvc_observed_log_cfu", SPOIL + 1.2)  # stationary phase: counts plateau (highest count in the data)


def mu(temp_c, product):
    """Growth rate in log CFU/g per hour."""
    b = PRODUCTS[product]["ratkowsky_b"]
    return (b * max(0.0, temp_c - TMIN)) ** 2


def step(tvc, temp_c, dt_h, product):
    """Advance bacterial load. Returns (new_tvc, rate_vs_reference, extra_loss_h).

    extra_loss_h = shelf-life hours lost beyond what the same time at the reference temperature would cost.
    """
    m = mu(temp_c, product)
    ratio = m / mu(REF_T, product)
    return min(MAX_TVC, tvc + m * dt_h), ratio, max(0.0, ratio - 1.0) * dt_h


def stage_index(tvc):
    return int(np.digitize([tvc], THRESHOLDS)[0])


def status_for(tvc):
    """UI status from data thresholds; 'critical' = upper half of the acceptable stage."""
    if tvc >= SPOIL:
        return "spoiled"
    if tvc >= (THRESHOLDS[1] + SPOIL) / 2:
        return "critical"
    if tvc >= THRESHOLDS[1]:
        return "at_risk"
    if tvc >= THRESHOLDS[0]:
        return "watch"
    return "fresh"


def freshness_score(tvc):
    return round(max(0.0, min(100.0, 100 * (SPOIL - tvc) / (SPOIL - TVC0))), 1)


def hours_left(tvc, temp_c, product):
    remaining = max(0.0, SPOIL - tvc)
    ref = remaining / mu(REF_T, product)
    m = mu(temp_c, product)
    now = remaining / m if m > 0 else MAX_HOURS
    return round(min(ref, MAX_HOURS), 1), round(min(now, MAX_HOURS), 1)


def describe(tvc, temp_c, product):
    hl, hl_now = hours_left(tvc, temp_c, product)
    return {
        "tvc": round(tvc, 3),
        "stage": STAGES[stage_index(tvc)],
        "status": status_for(tvc),
        "freshness_score": freshness_score(tvc),
        "hours_left": hl,
        "hours_left_if_unchanged": hl_now,
    }


def fuse(tvc_kin, tvc_gas):
    if tvc_gas is None:
        return tvc_kin
    return W_KIN * tvc_kin + (1 - W_KIN) * tvc_gas


def gas_index(tvc_gas):
    """0-500 'gas spoilage index' for the UI: where the gas-estimated load sits between fresh and spoiled."""
    if tvc_gas is None:
        return None
    return int(round(max(0.0, min(500.0, 500 * (tvc_gas - TVC0) / (SPOIL - TVC0)))))


# ---------------------------------------------------------------- event temperature profiles (real data)
_WARM = PROFILES["warm_up_delta_c"]["values"]          # every 10 min, delta °C after refrigeration stops
_DOOR = PROFILES["door_open_delta_c"]["values"]        # every 1 min, delta °C after a door opening
_cool_raw = PROFILES["cool_down_fraction"]["values"]   # every 10 min, fraction of excess heat remaining
_c0 = next((i for i, v in enumerate(_cool_raw) if v < 0.95), 0)
_COOL = [v / _cool_raw[_c0] for v in _cool_raw[_c0:]]  # starts at 1.0 once active cooling begins
DOOR_HUMIDITY_DELTA = PROFILES["door_open_delta_c"].get("humidity_delta", 0)


def _interp(series, step_min, minutes):
    if minutes <= 0:
        return series[0]
    x = minutes / step_min
    i = int(x)
    if i >= len(series) - 1:
        return series[-1]
    f = x - i
    return series[i] * (1 - f) + series[i + 1] * f


def warm_delta(minutes_since_start):
    return _interp(_WARM, 10, minutes_since_start)


def cool_fraction(minutes_since_end):
    return max(0.0, _interp(_COOL, 10, minutes_since_end))


def door_delta(minutes_since_open):
    if minutes_since_open > (len(_DOOR) - 1):
        return 0.0
    return max(0.0, _interp(_DOOR, 1, minutes_since_open))


def safe_float(x, default=None):
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default
