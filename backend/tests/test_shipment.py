import pytest

import shipment as S


def base(**kw):
    p = {"product": "strawberries", "origin_id": "ORG-MBW", "destination_city": "BLR", "vehicle": "reefer",
         "packed_hours_ago": 12, "printed_expiry_days": 5}
    p.update(kw)
    return p


def test_options_cover_products_origins_cities():
    o = S.options()
    assert {"chicken", "dairy", "greens", "strawberries"} <= set(o["products"])
    assert len(o["origins"]) >= 5 and len(o["cities"]) == 4
    assert all(c["outlets"] for c in o["cities"])


def test_clean_reefer_trip_is_assigned_to_an_accepting_outlet():
    r = S.simulate(base())
    assert r["timeline"][0]["stage"] == "origin_loading" and r["timeline"][-1]["stage"] == "arrival_dock"
    assert r["arrival"]["status"] in ("fresh", "watch")
    assert r["decision"]["decision"] == "ASSIGN"
    chosen = [c for c in r["candidates"] if c["chosen"]]
    assert len(chosen) == 1 and chosen[0]["accepts"]
    assert r["decision"]["accepting"] >= 10


def test_deterministic_for_same_input():
    assert S.simulate(base())["arrival"] == S.simulate(base())["arrival"]


CHICKEN = dict(product="chicken", origin_id="ORG-NMK", destination_city="BLR", vehicle="reefer",
               printed_expiry_days=4, planned_outlet_id="R-06")


def test_disruptions_cost_shelf_life():
    clean = S.simulate(base())
    bad = S.simulate(base(incidents=[{"type": "compressor", "at_h": 6, "minutes": 240}, {"type": "dock", "minutes": 90}]))
    assert bad["arrival"]["hours_left"] < clean["arrival"]["hours_left"] - 20
    assert bad["arrival"]["extra_life_lost_h"] > clean["arrival"]["extra_life_lost_h"]
    assert any(e["type"] == "compressor" for e in bad["events"])


def test_demo_presets_redirect_and_donate():
    redirect = S.simulate({**CHICKEN, "packed_hours_ago": 44, "incidents": [{"type": "compressor", "at_h": 2, "minutes": 300}]})
    assert redirect["decision"]["decision"] == "REDIRECT"
    assert redirect["decision"]["location"]["type"] in ("dark_store", "restaurant")
    donate = S.simulate({**CHICKEN, "packed_hours_ago": 54,
                         "incidents": [{"type": "compressor", "at_h": 2, "minutes": 300}, {"type": "dock", "minutes": 90}]})
    assert donate["decision"]["decision"] == "DONATE"
    assert donate["decision"]["location"]["type"] == "food_bank"


def test_planned_outlet_kept_or_redirected():
    ok = S.simulate(base(planned_outlet_id="R-06"))
    assert ok["decision"]["decision"] == "DELIVER"
    late = S.simulate(base(planned_outlet_id="R-06", packed_hours_ago=60,
                           incidents=[{"type": "compressor", "at_h": 4, "minutes": 300}]))
    assert late["decision"]["decision"] in ("REDIRECT", "DONATE", "DISCARD")


def test_insulated_van_warms_more_than_reefer():
    reefer = S.simulate(base(product="chicken", origin_id="ORG-NMK", destination_city="CHE"))
    van = S.simulate(base(product="chicken", origin_id="ORG-NMK", destination_city="CHE", vehicle="insulated"))
    assert van["arrival"]["minutes_above_safe"] > reefer["arrival"]["minutes_above_safe"]
    assert van["arrival"]["hours_left"] < reefer["arrival"]["hours_left"]


def test_label_vs_real():
    r = S.simulate(base(printed_expiry_days=5))
    assert r["arrival"]["label_hours_left"] == pytest.approx(5 * 24 - 12 - r["shipment"]["total_h"], abs=0.2)


def test_bad_input():
    with pytest.raises(S.ShipmentError):
        S.simulate(base(product="pizza"))
    with pytest.raises(S.ShipmentError):
        S.simulate(base(destination_city="XXX"))
    with pytest.raises(S.ShipmentError):
        S.simulate(base(incidents=[{"type": "alien"}]))
