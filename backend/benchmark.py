"""FIFO vs FreshSense on REAL cold-chain temperature histories.

    cd backend && python benchmark.py      -> data/benchmark_results.json

For every real shipment trace (42 logger series) and every simulated product, many crates are dispatched:
  - starting bacterial load: drawn from the measured initial loads in the beef datasets
  - stock age at dispatch: a random point in the trace's real cold-chain section (>= 6 h of storage)
  - loading-dock exposure: random dwell from data/assumptions.json, shaped by the real warm-up curve
  - trip: the following hours of the same real trace
FIFO sends every crate to its planned restaurant. FreshSense checks hours left at dispatch and redirects
crates that would arrive below the restaurant's requirement to a dark store, or donates them while safe.
The destination rules and trip lengths are operational assumptions (data/assumptions.json).
"""
import json
import os
import random

os.environ.setdefault("FRESHSENSE_MQTT_ENABLED", "0")
import model as M  # noqa: E402
import traces as T  # noqa: E402
from config import ASSUMPTIONS, DATA_DIR  # noqa: E402

NEED = ASSUMPTIONS["destination_min_hours_on_arrival"]
DOCK = ASSUMPTIONS["loading_dock_dwell_min"]
TRIP_H = (1.0, 3.5)          # Bengaluru warehouse -> restaurant trip, hours (assumption)
NEAR_DARK_STORE_H = 0.5      # a dark store is ~30 min from any point in the city (assumption)
NEAR_FOOD_BANK_H = 0.75
CRATES_PER_TRACE_PRODUCT = 60


def simulate_crate(rng, tid, product):
    tvc = rng.choice(M.TVC0_VALUES)
    cold0 = T.cold_start_minute(tid)
    end = rng.uniform(cold0 + 360, T.length_minutes(tid))
    dock = rng.uniform(*DOCK)
    step = 10
    m = 0.0
    while m < end:
        temp = T.temp_at(tid, m)
        if m >= end - dock:
            temp += M.warm_delta(m - (end - dock))
        tvc, _, _ = M.step(tvc, temp, step / 60, product)
        m += step
    hl_dispatch, _ = M.hours_left(tvc, M.REF_T, product)
    trip = rng.uniform(*TRIP_H)
    t = 0.0
    tvc_arr = tvc
    while t < trip * 60:
        tvc_arr, _, _ = M.step(tvc_arr, T.temp_at(tid, end + t), step / 60, product)
        t += step
    hl_arrival, _ = M.hours_left(tvc_arr, M.REF_T, product)
    return hl_dispatch, hl_arrival, trip, tvc_arr >= M.SPOIL


def run(seed=7):
    rng = random.Random(seed)
    res = {"fifo": {"delivered_ok": 0, "rejected": 0, "kg_wasted": 0},
           "freshsense": {"delivered_ok": 0, "rejected": 0, "kg_wasted": 0, "redirected": 0, "donated": 0, "kg_saved": 0}}
    by_product = {p: {"crates": 0, "fifo_rejected": 0, "freshsense_rejected": 0} for p in M.SIM_PRODUCTS}
    n = 0
    for tid in T.TRACE_IDS:
        for product in M.SIM_PRODUCTS:
            w = M.PRODUCTS[product]["weight_kg"]
            for _ in range(CRATES_PER_TRACE_PRODUCT):
                hl_d, hl_a, trip, spoiled = simulate_crate(rng, tid, product)
                n += 1
                by_product[product]["crates"] += 1
                ok = hl_a >= NEED["restaurant"] and not spoiled
                # FIFO
                if ok:
                    res["fifo"]["delivered_ok"] += 1
                else:
                    res["fifo"]["rejected"] += 1
                    res["fifo"]["kg_wasted"] += w
                    by_product[product]["fifo_rejected"] += 1
                # FreshSense: decide at dispatch using the predicted arrival (hours left minus trip at cold-chain speed)
                predicted_ok = hl_d - trip >= NEED["restaurant"]
                fs = res["freshsense"]
                if predicted_ok:
                    if ok:
                        fs["delivered_ok"] += 1
                    else:  # transit was worse than expected (real trace excursion) -> still rejected
                        fs["rejected"] += 1
                        fs["kg_wasted"] += w
                        by_product[product]["freshsense_rejected"] += 1
                elif hl_d - NEAR_DARK_STORE_H >= NEED["dark_store"]:
                    fs["redirected"] += 1
                    fs["kg_saved"] += w
                elif hl_d - NEAR_FOOD_BANK_H >= NEED["food_bank"]:
                    fs["donated"] += 1
                    fs["kg_saved"] += w
                else:
                    fs["rejected"] += 1
                    fs["kg_wasted"] += w
                    by_product[product]["freshsense_rejected"] += 1

    def pct(a, b):
        return round(100 * (a - b) / max(1, a), 1)

    return {
        "crates_simulated": n,
        "real_temperature_traces": len(T.TRACE_IDS),
        "fifo": res["fifo"],
        "freshsense": res["freshsense"],
        "rejection_reduction_pct": pct(res["fifo"]["rejected"], res["freshsense"]["rejected"]),
        "waste_reduction_pct": pct(res["fifo"]["kg_wasted"], res["freshsense"]["kg_wasted"]),
        "by_product": by_product,
        "method": "Real strawberry cold-chain temperature traces + calibrated spoilage model; destination rules and trip lengths are assumptions.",
        "note": "Simulation on real temperature data, not a field trial.",
    }


if __name__ == "__main__":
    out = run()
    with open(DATA_DIR / "benchmark_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
