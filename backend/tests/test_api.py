from fastapi.testclient import TestClient

import main


def test_api_contract():
    with TestClient(main.app) as client:
        assert client.get("/api/health").json()["ok"] is True

        s = client.get("/api/state").json()
        assert s["type"] == "state" and s["paused"] is True
        assert len(s["trucks"]) == 3 and len(s["crates"]) == 13
        tag = next(c for c in s["crates"] if c["is_live_tag"])
        assert tag["truck_id"] is None and tag["stage"] == "cold_room"
        crate = next(c for c in s["crates"] if c["truck_id"])
        for k in ("tvc", "tvc_kinetic", "quality_stage", "hours_left", "freshness_score", "status"):
            assert k in crate
        assert len(s["dispatch"]["fefo"]) == 12

        loc = client.get("/api/locations").json()
        assert len(loc["locations"]) == 22 and "chicken" in loc["products"] and "assumptions" in loc

        cal = client.get("/api/calibration").json()
        assert cal["stage_thresholds_log_cfu"] and cal["products"]["chicken"]["ratkowsky_b"] > 0

        j = client.get(f"/api/crates/{crate['id']}/journey").json()
        assert [st["stage"] for st in j["stages"]][0] == "farm_pickup"
        assert len(j["readings"]) <= 401 and "tvc" in j["readings"][0]

        assert client.get("/api/crates/NOPE/journey").status_code == 404
        assert client.post("/api/simulate/heat/NOPE").status_code == 404
        assert client.post(f"/api/simulate/heat/{crate['id']}?minutes=90").json()["minutes"] == 90
        assert client.post(f"/api/simulate/heat/{crate['id']}?minutes=0").status_code == 400
        assert client.post(f"/api/simulate/shock/{crate['id']}").json() == {"ok": True}
        assert client.post("/api/simulate/door/T-1").json() == {"ok": True}
        assert client.post("/api/simulate/compressor/T-3/fail").json() == {"ok": True}
        assert client.post("/api/simulate/compressor/T-3/fix").json() == {"ok": True}
        r = client.post("/api/sim/control", json={"paused": False, "minutes_per_tick": 2}).json()
        assert r["paused"] is False and r["minutes_per_tick"] == 2
        assert client.post("/api/tag/reading", json={"crate_id": "C-001", "temp_c": 20}).json()["ok"]

        p = client.post("/api/predict", json={"product": "chicken", "readings": [{"minute": 0, "temp_c": 3}, {"minute": 600, "temp_c": 3}]})
        assert p.status_code == 200 and p.json()["quality_stage"] in cal["stage_names"]
        assert client.post("/api/predict", json={"product": "x", "readings": []}).status_code == 400

        cases = client.get("/api/testcases").json()
        assert len(cases) >= 10
        assert client.get(f"/api/testcases/{cases[0]['id']}").json()["input"]["readings"]
        run = client.post("/api/testcases/run").json()
        assert run["total"] == len(cases) and run["passed"] >= 0.8 * run["total"]

        a = client.get("/api/analytics").json()
        assert a["model_card"]["available"] and a["hours_lost_by_truck"]

        assert client.post("/api/demo/reset").json() == {"ok": True}
        s2 = client.get("/api/state").json()
        assert s2["tick"] == 0 and s2["paused"] is True and s2["seed"] == s["seed"]

        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json()["type"] == "state"
