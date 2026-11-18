import pytest

import redirect
from config import LOCATIONS
from world import World


@pytest.fixture
def world():
    return World()


def set_hours_left(crate, hours):
    crate.consumed = 1 - hours / crate.p["shelf_life_ref_h"]
    crate.refresh()


def test_crate_with_plenty_of_time_keeps_destination(world):
    c = world.crates["C-011"]
    set_hours_left(c, 60)
    redirect.evaluate(world)
    assert c.destination_id == "R-06"
    assert not c.redirected
    assert world.new_redirects == []


def test_low_hours_chicken_is_redirected_to_dark_store(world):
    c = world.crates["C-003"]
    set_hours_left(c, 15)
    redirect.evaluate(world)
    assert c.redirected
    assert LOCATIONS[c.destination_id]["type"] == "dark_store"
    rec = world.new_redirects[-1]
    assert rec["decision"] == "REDIRECT" and rec["crate_id"] == "C-003"
    assert rec["from_location_id"] == "R-06"
    assert world.impact["crates_redirected"] == 1
    # the truck must now have a stop for the new destination
    stops = {s["location_id"]: s["crate_ids"] for s in world.trucks["T-2"].stops}
    assert "C-003" in stops[c.destination_id]
    assert "C-003" not in stops.get("R-06", [])


def test_very_low_hours_is_donated(world):
    c = world.crates["C-003"]
    set_hours_left(c, 5)
    redirect.evaluate(world)
    assert LOCATIONS[c.destination_id]["type"] == "food_bank"
    assert world.new_redirects[-1]["decision"] == "DONATE"
    assert world.impact["crates_donated"] == 1


def test_spoiled_is_discarded(world):
    c = world.crates["C-003"]
    set_hours_left(c, 0)
    redirect.evaluate(world)
    assert c.discarded
    assert "C-003" not in world.crates
    assert world.new_redirects[-1]["decision"] == "DISCARD"
    assert world.impact["kg_wasted"] == c.weight_kg


def test_heat_scenario_triggers_redirect_within_30_ticks(world):
    world.paused = False
    for _ in range(20):
        world.tick()
    world.heat(world.crates["C-003"])
    decisions = []
    for _ in range(30):
        world.tick()
        decisions += [r for r in world.new_redirects if r["crate_id"] == "C-003"]
    assert decisions and decisions[0]["decision"] == "REDIRECT"
