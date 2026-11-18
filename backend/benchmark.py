"""FIFO vs FreshSense batch simulation. Run: python benchmark.py  -> data/benchmark_results.json

This is a SIMULATION with literature-based parameters, not field data. Label it that way on slides.
"""
import json
import random

from config import DATA_DIR, LOCATIONS, PRODUCTS

N = 1000
RESTAURANT_MIN_H = 24
DARK_STORE_MIN_H = 8
FOOD_BANK_MIN_H = 2


def run(seed=7, n=N):
    rng = random.Random(seed)
    restaurants = [l for l in LOCATIONS.values() if l["type"] == "restaurant"]
    fifo = {"rejected": 0, "kg_wasted": 0}
    fs = {"rejected": 0, "kg_wasted": 0, "redirected": 0, "donated": 0}
    for _ in range(n):
        product = rng.choice(list(PRODUCTS))
        p = PRODUCTS[product]
        sl = p["shelf_life_ref_h"]
        weight = p["weight_kg"]
        hours_left = rng.uniform(0.15, 0.85) * sl  # at dispatch (stock age varies a lot)
        rng.choice(restaurants)  # original destination (only travel time matters here)
        travel_h = rng.uniform(1.0, 3.5)
        if rng.random() < 0.30:  # temperature excursion somewhere in the chain
            hours_left = max(0.0, hours_left - rng.uniform(5, 40))

        # FIFO: always goes to the original restaurant
        if hours_left - travel_h < RESTAURANT_MIN_H:
            fifo["rejected"] += 1
            fifo["kg_wasted"] += weight

        # FreshSense: keep if fine, else redirect to a dark store, else donate, else waste.
        # Realism: the problem is caught in time only 85% of the time (tag/connectivity gaps),
        # a nearby dark store has spare demand 70% of the time, a food bank can take it 80% of the time.
        if hours_left - travel_h >= RESTAURANT_MIN_H:
            continue
        caught = rng.random() < 0.85
        if caught and rng.random() < 0.70 and hours_left - rng.uniform(0.3, 1.0) >= DARK_STORE_MIN_H:
            fs["redirected"] += 1
        elif caught and rng.random() < 0.80 and hours_left - rng.uniform(0.3, 1.5) >= FOOD_BANK_MIN_H:
            fs["donated"] += 1
        else:
            fs["rejected"] += 1
            fs["kg_wasted"] += weight

    def pct(a, b):
        return round(100 * (a - b) / max(1, a), 1)

    return {
        "crates_simulated": n,
        "fifo": fifo,
        "freshsense": fs,
        "rejection_reduction_pct": pct(fifo["rejected"], fs["rejected"]),
        "waste_reduction_pct": pct(fifo["kg_wasted"], fs["kg_wasted"]),
        "note": "Simulation with literature-based parameters, not field data.",
    }


if __name__ == "__main__":
    result = run()
    with open(DATA_DIR / "benchmark_results.json", "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))
