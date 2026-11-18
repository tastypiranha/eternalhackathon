import pytest

import model as M
import predict
import run_testcases


def test_calibration_is_data_derived():
    # thresholds come from labelled data and are ordered
    assert M.THRESHOLDS == sorted(M.THRESHOLDS)
    assert 4.5 < M.SPOIL < 5.5
    assert 1.5 < M.TVC0 < 3.0
    assert set(M.SIM_PRODUCTS) == {"chicken", "dairy", "greens", "strawberries"}


def test_growth_increases_with_temperature():
    for p in M.PRODUCTS:
        assert M.mu(2, p) < M.mu(10, p) < M.mu(25, p)
    assert M.mu(M.TMIN - 1, "chicken") == 0.0


def test_perishability_order_follows_foodkeeper():
    # chicken spoils fastest, dairy slowest — same order as FoodKeeper fridge days
    life = {p: M.hours_left(M.TVC0, M.REF_T, p)[0] for p in M.PRODUCTS}
    assert life["chicken"] < life["strawberries"] < life["greens"] <= life["beef"] < life["dairy"]


def test_status_and_stage_follow_thresholds():
    assert M.status_for(M.THRESHOLDS[0] - 0.01) == "fresh"
    assert M.status_for(M.THRESHOLDS[0]) == "watch"
    assert M.status_for(M.THRESHOLDS[1]) == "at_risk"
    assert M.status_for(M.SPOIL - 0.01) == "critical"
    assert M.status_for(M.SPOIL) == "spoiled"
    assert M.STAGES[M.stage_index(M.SPOIL)] == "spoiled"


def test_extra_loss_only_when_warmer_than_reference():
    _, _, e_cold = M.step(2.0, M.REF_T - 2, 1, "chicken")
    _, _, e_warm = M.step(2.0, 20, 1, "chicken")
    assert e_cold == 0.0 and e_warm > 0


def test_event_profiles_come_from_data():
    assert M.warm_delta(0) == pytest.approx(0, abs=0.1)
    assert M.warm_delta(120) > M.warm_delta(30) > 0
    assert M.door_delta(3) > M.door_delta(60)
    assert M.cool_fraction(0) == pytest.approx(1.0)


def test_predict_rejects_bad_input():
    with pytest.raises(predict.PredictError):
        predict.predict({"product": "pizza", "readings": [{"minute": 0, "temp_c": 4}]})
    with pytest.raises(predict.PredictError):
        predict.predict({"product": "chicken", "readings": []})


def test_predict_cold_vs_warm():
    cold = predict.predict({"product": "chicken", "readings": [{"minute": m, "temp_c": 2} for m in range(0, 1441, 60)]})
    warm = predict.predict({"product": "chicken", "readings": [{"minute": m, "temp_c": 20} for m in range(0, 1441, 60)]})
    assert warm["tvc_estimate_log_cfu"] > cold["tvc_estimate_log_cfu"]
    assert warm["minutes_above_safe_temp"] > 0 and cold["minutes_above_safe_temp"] == 0
    assert cold["hours_left_at_reference_temp"] > warm["hours_left_at_reference_temp"]


def test_predict_recommendation():
    r = predict.predict({"product": "chicken", "initial_tvc": 4.6,
                         "readings": [{"minute": 0, "temp_c": 3}, {"minute": 60, "temp_c": 3}],
                         "location": {"lat": 12.97, "lng": 77.64}, "destination_id": "R-06"})
    assert r["recommendation"]["decision"] in {"REDIRECT", "DONATE", "DISCARD"}


def test_held_out_cases_pass():
    rows = run_testcases.run_all()
    assert len(rows) >= 10
    assert sum(r["pass"] for r in rows) / len(rows) >= 0.8


def test_example_inputs_match_documented_outputs():
    """docs/TESTING.md promises these outputs for backend/examples/*.json."""
    import json
    from pathlib import Path
    ex = Path(__file__).parent.parent / "examples"
    expected = json.loads((ex / "expected_outputs.json").read_text())
    for name, exp in expected.items():
        r = predict.predict(json.loads((ex / f"{name}.json").read_text()))
        assert r["quality_stage"] == exp["quality_stage"], name
        assert r["status"] == exp["status"], name
        assert r["tvc_estimate_log_cfu"] == pytest.approx(exp["tvc_estimate_log_cfu"], abs=0.02), name
        assert r["hours_left_at_reference_temp"] == pytest.approx(exp["hours_left_at_reference_temp"], abs=0.5), name
        rec = r["recommendation"]
        assert (rec and {"decision": rec["decision"], "location_id": rec["location_id"]}) == exp["recommendation"], name
