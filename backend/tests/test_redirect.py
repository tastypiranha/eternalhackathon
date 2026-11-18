import pytest

import model as M
import redirect
from config import LOCATIONS
from world import World


@pytest.fixture(scope="module")
def base_world():
    return World()


@pytest.fixture
def world(base_world):
    base_world.reset(base_world.seed)
    return base_world


def chicken_on_truck(world):
    return next(c for c in world.crates.values() if c.truck_id and c.product == "chicken")


def set_hours_left(crate, hours):
    crate.tvc_kin = M.SPOIL - hours * M.mu(M.REF_T, crate.product)
    crate.tvc_gas = None
    crate.refresh()


def test_world_is_demo_ready_and_feasible(world):
    for c in world.crates.values():
        if c.truck_id:
            assert redirect.feasible(world, c, c.destination_id)


def test_plenty_of_time_keeps_destination(world):
    c = chicken_on_truck(world)
    set_hours_left(c, 70)
    dest = c.destination_id
    redirect.evaluate(world)
    assert c.destination_id == dest and not c.redirected


def test_low_hours_redirected_to_dark_store(world):
    c = chicken_on_truck(world)
    set_hours_left(c, 15)
    redirect.evaluate(world)
    assert c.redirected and LOCATIONS[c.destination_id]["type"] == "dark_store"
    stops = {s["location_id"]: s["crate_ids"] for s in world.trucks[c.truck_id].stops}
    assert c.id in stops[c.destination_id]


def test_very_low_hours_donated(world):
    c = chicken_on_truck(world)
    set_hours_left(c, 5)
    redirect.evaluate(world)
    assert LOCATIONS[c.destination_id]["type"] == "food_bank"
    assert world.impact["crates_donated"] == 1


def test_spoiled_discarded(world):
    c = chicken_on_truck(world)
    set_hours_left(c, 0)
    redirect.evaluate(world)
    assert c.discarded and c.id not in world.crates


def test_compressor_failure_heats_cargo_with_real_warm_up_curve(world):
    world.paused = False
    c = next(c for c in world.crates.values() if c.truck_id)
    truck = world.trucks[c.truck_id]
    for _ in range(5):
        world.tick()
    before_temp, before_rate = c.temp_c, c.rate
    world.compressor(truck, False)
    for _ in range(60):  # 60 sim minutes at 1 min/tick
        world.tick()
        if c.id not in world.crates:
            pytest.skip("crate delivered during the test window")
    assert c.temp_c > before_temp + 5          # real curve: about +8 °C after 60 min
    assert c.rate > 2 * before_rate            # spoilage clearly faster
    assert any(a["type"] == "temp_excursion" for a in world.alerts)
    world.compressor(truck, True)
    for _ in range(240):
        world.tick()
        if c.id not in world.crates:
            return
    assert c.temp_c < before_temp + 4          # cools back down along the real cool-down curve
