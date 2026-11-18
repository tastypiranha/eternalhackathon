"""Redirect decision rules (master plan 6.6)."""
from config import ASSUMPTIONS, LOCATIONS

SELL_TYPES = ("restaurant", "dark_store")
TARGET_TYPES = ("restaurant", "dark_store", "food_bank")
W = ASSUMPTIONS["redirect_score_weights"]
TYPE_BONUS = {"restaurant": W["type_bonus_restaurant"], "dark_store": W["type_bonus_dark_store"]}


def feasible(world, crate, loc_id):
    if not loc_id or not crate.truck_id:
        return False
    loc = LOCATIONS[loc_id]
    if loc["type"] not in TARGET_TYPES:
        return False
    if loc["demand_kg_per_day"].get(crate.product, 0) <= 0:
        return False
    if crate.status == "spoiled":
        return False
    _, travel_h = world.travel(world.trucks[crate.truck_id], loc)
    return crate.hours_left - travel_h >= loc["min_hours_needed"]


def score(crate, loc, travel_km, travel_h):
    demand_match = min(1.0, loc["demand_kg_per_day"][crate.product] / (crate.weight_kg * 2))
    time_margin = min(1.0, (crate.hours_left - travel_h - loc["min_hours_needed"]) / 24)
    distance_pen = min(1.0, travel_km / 40)
    return (W["demand_match"] * demand_match + W["time_margin"] * time_margin
            - W["distance_penalty"] * distance_pen + TYPE_BONUS.get(loc["type"], 0))


def decide(world, crate):
    """Return a decision dict for a crate whose current destination is not feasible."""
    truck = world.trucks[crate.truck_id]
    scored = []
    for loc in LOCATIONS.values():
        if loc["type"] in SELL_TYPES and loc["id"] != crate.destination_id and feasible(world, crate, loc["id"]):
            km, h = world.travel(truck, loc)
            scored.append((score(crate, loc, km, h), loc, km, h))
    scored.sort(key=lambda x: x[0], reverse=True)
    if scored:
        s, loc, km, h = scored[0]
        return {
            "decision": "REDIRECT", "location": loc, "travel_km": km, "travel_h": h,
            "alternatives": [
                {"location_id": l["id"], "name": l["name"], "score": round(sc, 2)}
                for sc, l, _, _ in scored[1:3]
            ],
        }
    banks = []
    for loc in LOCATIONS.values():
        if loc["type"] == "food_bank" and feasible(world, crate, loc["id"]):
            km, h = world.travel(truck, loc)
            banks.append((km, loc, h))
    if banks:
        banks.sort(key=lambda x: x[0])
        km, loc, h = banks[0]
        return {"decision": "DONATE", "location": loc, "travel_km": km, "travel_h": h, "alternatives": []}
    return {"decision": "DISCARD", "location": None, "travel_km": 0.0, "travel_h": 0.0, "alternatives": []}


def reason_text(world, crate, dec):
    p = crate.p
    orig = LOCATIONS.get(crate.destination_id)
    travel_min = dec["travel_h"] * 60
    if dec["decision"] == "REDIRECT":
        loc = dec["location"]
        _, orig_h = world.travel(world.trucks[crate.truck_id], orig)
        arrive = max(0.0, crate.hours_left - orig_h)
        return (
            f"Only {crate.hours_left:.0f} h left; it would reach {orig['name']} with ~{arrive:.0f} h, "
            f"below the {orig['min_hours_needed']} h it needs. "
            f"{loc['name']} is {travel_min:.0f} min away and sells "
            f"{loc['demand_kg_per_day'][crate.product]} kg {p['label']}/day."
        )
    if dec["decision"] == "DONATE":
        return (
            f"Only {crate.hours_left:.0f} h left — too little to sell. Still safe, so donating to "
            f"{dec['location']['name']} ({travel_min:.0f} min away)."
        )
    return f"Spoiled or no destination reachable in time. Logged cause: {world.biggest_cause(crate)}."


def evaluate(world):
    for crate in list(world.crates.values()):
        if not crate.truck_id or crate.delivered or crate.discarded:
            continue
        truck = world.trucks[crate.truck_id]
        # Crate is being unloaded at its destination right now: delivery rule decides.
        if truck.service_left_min > 0 and truck.stops and crate.id in truck.stops[0]["crate_ids"]:
            continue
        if feasible(world, crate, crate.destination_id):
            continue
        dec = decide(world, crate)
        world.apply_redirect(crate, dec, reason_text(world, crate, dec))
