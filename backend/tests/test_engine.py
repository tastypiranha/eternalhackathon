import pytest

import engine
from config import PRODUCTS

chicken = PRODUCTS["chicken"]
dairy = PRODUCTS["dairy"]


def test_rate_reference_is_one():
    assert engine.rate(2, chicken) == pytest.approx(1.0)
    assert engine.rate(4, dairy) == pytest.approx(1.0)


def test_rate_sanity_values():
    assert engine.rate(15, chicken) == pytest.approx(7.2, rel=0.05)
    assert engine.rate(15, dairy) == pytest.approx(3.8, rel=0.05)
    assert engine.rate(25, chicken) == pytest.approx(29, rel=0.07)
    assert engine.rate(30, chicken) == pytest.approx(57, rel=0.07)


def test_chicken_faster_than_dairy_when_warm():
    assert engine.rate(15, chicken) > engine.rate(15, dairy)


def test_one_hour_at_reference_consumes_one_hour():
    consumed = 0.0
    for _ in range(60):
        consumed, _, extra = engine.step(consumed, 2, 50, 1 / 60, chicken)
        assert extra == pytest.approx(0.0, abs=1e-9)
    assert consumed * chicken["shelf_life_ref_h"] == pytest.approx(1.0)


def test_gas_factor_speeds_up():
    c1, r1, _ = engine.step(0.5, 2, 100, 1, chicken)
    c2, r2, _ = engine.step(0.5, 2, 300, 1, chicken)
    assert r2 == pytest.approx(r1 * 1.3)
    assert c2 > c1


def test_status_thresholds():
    assert engine.status_for(70, 50) == "fresh"
    assert engine.status_for(69.9, 50) == "watch"
    assert engine.status_for(39.9, 50) == "at_risk"
    assert engine.status_for(14.9, 50) == "critical"
    assert engine.status_for(0, 50) == "spoiled"
    assert engine.status_for(80, 450) == "spoiled"


def test_derived_hours_left():
    d = engine.derived(0.5, 2.0, 50, chicken)
    assert d["hours_left"] == 48.0
    assert d["hours_left_if_unchanged"] == 24.0
    assert d["freshness_score"] == 50.0
    assert d["status"] == "watch"
