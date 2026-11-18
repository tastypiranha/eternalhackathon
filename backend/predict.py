"""Stateless prediction: one crate's reading history in, freshness + recommendation out.

Used by POST /api/predict, the Test Lab in the dashboard, and run_testcases.py.

Input (dict):
  product        one of calibration products: beef | chicken | dairy | greens | strawberries
  readings       list of {minute, temp_c?, humidity?, gas?: {MQ2, MQ3, MQ4, MQ5, MQ135, MQ136}}
                 minute = minutes since the crate was packed (any spacing; resampled to 1 min).
                 temp_c missing/null -> room temperature of the calibration experiments.
  initial_tvc    optional starting bacterial load (log CFU/g); default = median measured initial load
  location       optional {lat, lng} of the crate now   } both needed for a routing recommendation
  destination_id optional planned stop (location id)    }
"""
import math

import numpy as np

import gas as G
import model as M
import redirect
from config import LOCATIONS, ROAD_FACTOR, TRUCK_SPEED_KMH


class PredictError(ValueError):
    pass


def _resample(readings):
    rs = sorted(readings, key=lambda r: float(r["minute"]))
    minutes = np.array([float(r["minute"]) for r in rs])
    if len(minutes) == 0:
        raise PredictError("readings is empty")
    if np.any(np.diff(minutes) < 0):
        raise PredictError("minutes must not go backwards")
    grid = np.arange(minutes[0], minutes[-1] + 1e-9, 1.0) if minutes[-1] > minutes[0] else minutes[:1]
    temps_raw = [M.safe_float(r.get("temp_c")) for r in rs]
    temp_known = [t is not None for t in temps_raw]
    if any(temp_known):
        xs = minutes[temp_known]
        ys = np.array([t for t in temps_raw if t is not None])
        temps = np.interp(grid, xs, ys)
        temp_source = "measured"
    else:
        temps = np.full(len(grid), M.AMBIENT_C)
        temp_source = f"not provided: assumed room temperature {M.AMBIENT_C} °C (mean of the calibration experiments)"
    gas_rows = [r.get("gas") for r in rs]
    gas = None
    if all(isinstance(g, dict) and all(k in g for k in G.SENSORS) for g in gas_rows):
        mat = np.array([[float(g[k]) for k in G.SENSORS] for g in gas_rows])
        gas = np.column_stack([np.interp(grid, minutes, mat[:, j]) for j in range(mat.shape[1])])
    return grid, temps, gas, temp_source


def predict(payload):
    product = payload.get("product")
    if product not in M.PRODUCTS:
        raise PredictError(f"unknown product '{product}'. Use one of: {', '.join(M.PRODUCTS)}")
    readings = payload.get("readings") or []
    if not isinstance(readings, list):
        raise PredictError("readings must be a list")
    grid, temps, gas, temp_source = _resample(readings)
    tvc0 = M.safe_float(payload.get("initial_tvc"), M.TVC0)

    # kinetic path (Ratkowsky over the measured temperature history)
    tvc = tvc0
    extra = 0.0
    above = 0.0
    limit = M.PRODUCTS[product]["max_safe_c"]
    path = [tvc]
    for i in range(1, len(grid)):
        dt_h = (grid[i] - grid[i - 1]) / 60
        tvc, _, e = M.step(tvc, temps[i], dt_h, product)
        extra += e
        above += (grid[i] - grid[i - 1]) if temps[i] > limit else 0
        path.append(tvc)
    tvc_kin = tvc

    tvc_gas, gas_note = None, None
    if gas is not None:
        if not M.PRODUCTS[product]["gas_model"]:
            gas_note = "gas readings ignored: the gas model is trained on meat (beef) e-nose data only"
        elif len(gas) < G.MIN_READINGS:
            gas_note = f"gas readings ignored: need at least {G.MIN_READINGS} minutes of readings for the baseline"
        else:
            tvc_gas = float(G.predict_series(gas)[-1])
    elif any(r.get("gas") for r in readings):
        gas_note = f"gas readings ignored: every reading needs all sensors {G.SENSORS}"

    tvc_est = M.fuse(tvc_kin, tvc_gas)
    now = M.describe(tvc_est, float(temps[-1]), product)
    mu_ref = M.mu(M.REF_T, product)
    result = {
        "product": product,
        "product_label": M.PRODUCTS[product]["label"],
        "minutes_covered": float(grid[-1] - grid[0]),
        "temperature_source": temp_source,
        "last_temp_c": round(float(temps[-1]), 2),
        "initial_tvc_log_cfu": round(tvc0, 2),
        "tvc_kinetic_log_cfu": round(tvc_kin, 3),
        "tvc_gas_log_cfu": None if tvc_gas is None else round(tvc_gas, 3),
        "tvc_estimate_log_cfu": round(tvc_est, 3),
        "fusion": {"weight_kinetic": M.W_KIN if tvc_gas is not None else 1.0,
                   "weight_gas": round(1 - M.W_KIN, 3) if tvc_gas is not None else 0.0},
        "quality_stage": now["stage"],
        "status": now["status"],
        "freshness_score": now["freshness_score"],
        "hours_left_at_reference_temp": now["hours_left"],
        "reference_temp_c": M.REF_T,
        "hours_left_if_temperature_stays": now["hours_left_if_unchanged"],
        "minutes_above_safe_temp": round(above),
        "safe_temp_c": limit,
        "extra_life_lost_to_heat_h": round(extra, 1),
        "life_used_h": round((tvc_est - tvc0) / mu_ref, 1),
        "stage_thresholds_log_cfu": M.THRESHOLDS,
        "notes": [n for n in [gas_note] if n],
    }
    result["recommendation"] = _recommend(payload, product, now["hours_left"], now["status"])
    return result


def _recommend(payload, product, hours_left, status):
    loc = payload.get("location")
    dest_id = payload.get("destination_id")
    if not loc or dest_id not in LOCATIONS:
        return None
    lat, lng = M.safe_float(loc.get("lat")), M.safe_float(loc.get("lng"))
    if lat is None or lng is None:
        return None

    class _T:  # minimal truck/crate stand-ins so the redirect rules can be reused unchanged
        pass

    truck = _T()
    truck.lat, truck.lng = lat, lng
    crate = _T()
    crate.truck_id, crate.product, crate.weight_kg = "X", product, M.PRODUCTS[product]["weight_kg"]
    crate.hours_left, crate.status, crate.destination_id = hours_left, status, dest_id
    crate.p = M.PRODUCTS[product]

    class _W:
        trucks = {"X": truck}

        @staticmethod
        def travel(t, l):
            from world import haversine_km
            km = haversine_km(t.lat, t.lng, l["lat"], l["lng"]) * ROAD_FACTOR
            return km, km / TRUCK_SPEED_KMH

        @staticmethod
        def biggest_cause(c):
            return "temperature history"

    w = _W()
    if redirect.feasible(w, crate, dest_id):
        _, h = w.travel(truck, LOCATIONS[dest_id])
        return {"decision": "KEEP", "location_id": dest_id, "location_name": LOCATIONS[dest_id]["name"],
                "travel_min": round(h * 60), "reason": f"Arrives with ~{hours_left - h:.0f} h left; needs {LOCATIONS[dest_id]['min_hours_needed']} h."}
    dec = redirect.decide(w, crate)
    loc_ = dec["location"]
    return {"decision": dec["decision"], "location_id": loc_["id"] if loc_ else None,
            "location_name": loc_["name"] if loc_ else None, "travel_min": round(dec["travel_h"] * 60),
            "reason": redirect.reason_text(w, crate, dec), "alternatives": dec["alternatives"]}


def score_case(case, result):
    """Compare a prediction with a test case's expected values."""
    exp = case["expected"]
    err = abs(result["tvc_estimate_log_cfu"] - exp["tvc_log_cfu"])
    stages = M.STAGES
    stage_gap = abs(stages.index(result["quality_stage"]) - stages.index(exp["stage"]))
    tol = exp.get("tolerance", {}).get("tvc_log_cfu", 0.6)
    return {"id": case["id"], "expected_tvc": exp["tvc_log_cfu"], "predicted_tvc": result["tvc_estimate_log_cfu"],
            "kinetic_tvc": result["tvc_kinetic_log_cfu"], "gas_tvc": result["tvc_gas_log_cfu"],
            "abs_error": round(err, 3), "expected_stage": exp["stage"], "predicted_stage": result["quality_stage"],
            "expected_hours_until_spoiled": exp.get("hours_until_spoiled_at_same_conditions"),
            "predicted_hours_if_temperature_stays": result["hours_left_if_temperature_stays"],
            "pass": bool(err <= tol and stage_gap <= 1)}
