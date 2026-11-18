from fastapi.testclient import TestClient

import main


def test_api_contract():
    with TestClient(main.app) as client:
        assert client.get("/api/health").json()["ok"] is True

        s = client.get("/api/state").json()
        assert s["type"] == "state" and s["paused"] is True
        assert len(s["crates"]) == 12 and len(s["trucks"]) == 3
        c001 = next(c for c in s["crates"] if c["id"] == "C-001")
        assert c001["truck_id"] is None and c001["stage"] == "cold_room" and c001["is_live_tag"]
        for key in ("fefo", "fifo"):
            assert len(s["dispatch"][key]) == 11
        assert s["dispatch"]["fefo"][0]["crate_id"] == "C-003"

        loc = client.get("/api/locations").json()
        assert len(loc["locations"]) == 22 and len(loc["trucks"]) == 3 and "chicken" in loc["products"]

        j = client.get("/api/crates/C-003/journey").json()
        assert [st["stage"] for st in j["stages"]][:3] == ["farm_pickup", "loading_dock", "cold_room"]
        assert j["blame"]["stage"] == "loading_dock"
        assert len(j["readings"]) <= 401

        assert client.get("/api/crates/NOPE/journey").status_code == 404
        assert client.post("/api/simulate/heat/NOPE").status_code == 404
        assert client.post("/api/simulate/door/T-9").status_code == 404

        assert client.post("/api/simulate/heat/C-003").json() == {"ok": True}
        assert client.post("/api/simulate/shock/C-007").json() == {"ok": True}
        assert client.post("/api/simulate/door/T-1").json() == {"ok": True}
        assert client.post("/api/simulate/compressor/T-3/fail").json() == {"ok": True}
        assert client.post("/api/simulate/compressor/T-3/fix").json() == {"ok": True}
        r = client.post("/api/sim/control", json={"paused": False, "minutes_per_tick": 2}).json()
        assert r["paused"] is False and r["minutes_per_tick"] == 2
        assert client.post("/api/sim/control", json={"minutes_per_tick": 50}).status_code == 400

        assert client.post("/api/tag/reading", json={"crate_id": "C-001", "temp_c": 20, "humidity": 70,
                                                     "voc_index": 100, "door_open": False, "source": "slider"}).json()["ok"]
        a = client.get("/api/analytics").json()
        assert a["hours_lost_by_truck"][0]["truck_id"] == "T-3"
        assert "available" in client.get("/api/model-card").json()

        assert client.post("/api/demo/reset").json() == {"ok": True}
        s2 = client.get("/api/state").json()
        assert s2["paused"] is True and s2["tick"] == 0 and s2["minutes_per_tick"] == 1

        with client.websocket_connect("/ws") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "state"
