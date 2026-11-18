"""FreshSense simulator driven by real data.

- Truck and cold-room temperatures replay real strawberry cold-chain shipment traces (42 logger series).
- Each crate's history replays a real trace from pickup/pre-cooling through cold storage, plus a loading-dock
  exposure shaped by the real warm-up curve.
- Events (crate left out, compressor failure, door opening) use warm-up / cool-down / door curves measured in
  the shipment and refrigerator datasets.
- Bacterial load follows the calibrated Ratkowsky model; meat crates also carry a replayed real e-nose stream
  whose smell-based estimate is fused with the kinetic estimate.
Nothing about a crate's freshness is hand-set: starting bacterial load comes from the measured initial loads,
and stock age / dock dwell / destination are random draws.
"""
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import alerts
import config as C
import db
import model as M
import mqtt_tag
import redirect
import traces as T
from config import LOCATIONS
from gas import GasTrack

TS_FMT = "%Y-%m-%dT%H:%M:%S"
FRIDGE_RH = M.PROFILES.get("fridge_humidity_pct", {}).get("value", 60.0)
DOOR_PEAK = max(M._DOOR) or 1.0


def haversine_km(lat1, lng1, lat2, lng2):
    la1, lo1, la2, lo2 = map(math.radians, (lat1, lng1, lat2, lng2))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


@dataclass
class Event:
    start: float
    end: float | None = None


@dataclass
class Crate:
    id: str
    product: str
    weight_kg: float
    truck_id: str | None = None
    warehouse_id: str | None = None
    stage: str = "in_transit"
    temp_c: float = 3.0
    humidity: float = 60.0
    door_open: bool = False
    tvc_kin: float = 2.0
    tvc_gas: float | None = None
    tvc: float = 2.0
    initial_tvc: float = 2.0
    rate: float = 1.0
    hours_left: float = 0.0
    hours_left_if_unchanged: float = 0.0
    freshness_score: float = 100.0
    stage_name: str = "excellent"
    status: str = "fresh"
    last_status: str = "fresh"
    loaded_at: str = ""
    destination_id: str | None = None
    original_destination_id: str | None = None
    redirected: bool = False
    redirect_reason: str | None = None
    heat: Event | None = None
    excursion_ticks: int = 0
    in_excursion: bool = False
    delivered: bool = False
    delivered_to: str | None = None
    discarded: bool = False
    last_tag_door: bool = False
    trace_id: str | None = None      # cold-room trace (crates not on a truck)
    trace_pos: float = 0.0
    gas: GasTrack | None = None

    @property
    def p(self):
        return M.PRODUCTS[self.product]

    def refresh(self):
        self.tvc = M.fuse(self.tvc_kin, self.tvc_gas)
        d = M.describe(self.tvc, self.temp_c, self.product)
        self.hours_left = d["hours_left"]
        self.hours_left_if_unchanged = d["hours_left_if_unchanged"]
        self.freshness_score = d["freshness_score"]
        self.status = d["status"]
        self.stage_name = d["stage"]


@dataclass
class Truck:
    id: str
    name: str
    driver: str
    color: str
    origin_id: str
    lat: float
    lng: float
    trace_id: str
    trace_pos: float
    status: str = "en_route"
    stops: list = field(default_factory=list)
    service_left_min: float = 0.0
    wait_ticks: int = 0
    compressor: Event | None = None
    door: Event | None = None
    live_extra_loss_h: float = 0.0
    live_excursions: int = 0

    @property
    def compressor_ok(self):
        return self.compressor is None or self.compressor.end is not None

    def door_open_at(self, now):
        return self.door is not None and now - self.door.start < 15


def _event_excess(ev, now):
    """Extra °C above the base trace for a warm-up event (real warm-up curve, then real cool-down curve)."""
    if ev is None:
        return 0.0
    if ev.end is None or now < ev.end:
        return M.warm_delta(now - ev.start)
    peak = M.warm_delta(ev.end - ev.start)
    return peak * M.cool_fraction(now - ev.end)


SEED_FILE = C.DATA_DIR / "demo_seed.json"


def _load_seed():
    """Reuse the demo-ready seed found earlier, as long as the calibration has not changed."""
    try:
        import json
        d = json.loads(SEED_FILE.read_text())
        if d.get("calibration") == M.CAL["generated_at"]:
            return d["seed"]
    except Exception:
        pass
    return None


def _save_seed(seed):
    import json
    try:
        SEED_FILE.write_text(json.dumps({"seed": seed, "calibration": M.CAL["generated_at"]}))
    except OSError:
        pass


class World:
    _seed_cache = None  # the demo-ready seed found on first start; resets reuse it (instant, identical demo)

    def __init__(self):
        self.reset()

    # ------------------------------------------------------------------ reset / seeding
    def reset(self, seed=None):
        db.reset_db()
        mqtt_tag.clear()
        start = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        if seed is None and World._seed_cache is None:
            World._seed_cache = _load_seed()
        if seed is None and World._seed_cache is not None:
            seed = World._seed_cache
        if seed is None:
            chosen = None
            for s in range(C.RANDOM_SEED, C.RANDOM_SEED + C.SEED_SEARCH_LIMIT):
                self._build(s, start)
                if self._demo_ready():
                    chosen = s
                    break
            if chosen is None:
                self._build(C.RANDOM_SEED, start)
                chosen = C.RANDOM_SEED
            World._seed_cache = chosen
            _save_seed(chosen)
        else:
            chosen = seed
            self._build(seed, start)
        self.seed = chosen
        db.insert_readings(self._rows)
        self._rows = []

    def _build(self, seed, start):
        self.rng = random.Random(seed)
        self.sim_time = start
        self.now = 0.0  # sim minutes since reset
        self.tick_n = 0
        self.paused = C.START_PAUSED
        self.minutes_per_tick = C.SIM_MINUTES_PER_TICK
        self.crates: dict[str, Crate] = {}
        self.archive: dict[str, Crate] = {}
        self.alerts, self.new_alerts = [], []
        self.redirects, self.new_redirects = [], []
        self.deliveries = []
        self.counters = {"alert": 0, "redirect": 0, "delivery": 0}
        self.next_crate_num = 1
        self.impact = {"crates_redirected": 0, "crates_donated": 0, "kg_saved": 0, "rejections_avoided": 0,
                       "deliveries_completed": 0, "deliveries_rejected": 0, "kg_wasted": 0}
        self._rows = []
        self.trucks: dict[str, Truck] = {}
        for t in C.TRUCKS:
            origin = LOCATIONS[t["origin_id"]]
            tid = self.rng.choice(T.TRACE_IDS)
            pos = self.rng.uniform(T.cold_start_minute(tid), T.length_minutes(tid))
            self.trucks[t["id"]] = Truck(
                id=t["id"], name=t["name"], driver=t["driver"], color=t["color"], origin_id=t["origin_id"],
                lat=origin["lat"], lng=origin["lng"], trace_id=tid, trace_pos=pos,
            )
        # live-tag crate in the Hoskote cold room
        tag = self._new_crate(None, "WH-1", None, product="dairy")
        self.crates[tag.id] = tag
        for t in self.trucks.values():
            self._load_trip(t, initial=True)

    def _demo_ready(self):
        """A demo-ready stock: every crate can still reach its planned stop, and at least one crate is close enough
        to its limit (1-3 h of slack, >= 2.5 h before delivery) that a real incident would force a redirect."""
        slacks, candidate = [], False
        for c in self.crates.values():
            if not c.truck_id:
                continue
            loc = LOCATIONS[c.destination_id]
            truck = self.trucks[c.truck_id]
            _, h = self.travel(truck, loc)
            s = c.hours_left - h - loc["min_hours_needed"]
            slacks.append(s)
            eta = next((e for st, e in zip(truck.stops, self.stop_etas(truck)) if c.id in st["crate_ids"]), 0)
            if 1 <= s <= 3 and eta >= 150:  # an incident has time to matter before delivery
                candidate = True
        return bool(slacks) and min(slacks) > 0.5 and candidate

    def _new_crate_id(self):
        cid = f"C-{self.next_crate_num:03d}"
        self.next_crate_num += 1
        return cid

    def _new_crate(self, truck, warehouse_id, dest_id, product=None):
        product = product or self.rng.choice(M.SIM_PRODUCTS)
        p = M.PRODUCTS[product]
        crate = Crate(id=self._new_crate_id(), product=product, weight_kg=p["weight_kg"])
        crate.initial_tvc = self.rng.choice(M.TVC0_VALUES)
        self._backfill(crate, warehouse_id)
        if p["gas_model"]:
            crate.gas = GasTrack(self.rng)
            crate.tvc_gas = crate.gas.prime(crate.initial_tvc, crate.tvc_kin)
        if truck is not None:
            crate.truck_id = truck.id
            crate.stage = "in_transit"
            crate.destination_id = crate.original_destination_id = dest_id
            stop = next((s for s in truck.stops if s["location_id"] == dest_id), None)
            if stop is None:
                truck.stops.append({"location_id": dest_id, "crate_ids": [crate.id]})
            else:
                stop["crate_ids"].append(crate.id)
        else:
            crate.warehouse_id = warehouse_id
            crate.stage = "cold_room"
            crate.trace_id = self.rng.choice(T.TRACE_IDS)
            crate.trace_pos = self.rng.uniform(T.cold_start_minute(crate.trace_id), T.length_minutes(crate.trace_id))
        crate.refresh()
        crate.last_status = crate.status
        return crate

    def _backfill(self, crate, warehouse_id):
        """History = a real trace from pickup through cold storage (random stock age), then a dock exposure."""
        rng = self.rng
        tid = rng.choice(T.TRACE_IDS)
        cold0 = T.cold_start_minute(tid)
        step = C.BACKFILL_STEP_MIN
        # Stock age: warehouses dispatch stock that is still 'excellent' or 'good' (assumptions.json), so the
        # latest possible dispatch is when this crate, on this real trace, would reach the 'acceptable' threshold.
        latest, v, m = T.length_minutes(tid), crate.initial_tvc, 0.0
        while m < T.length_minutes(tid):
            v, _, _ = M.step(v, T.temp_at(tid, m), step / 60, crate.product)
            if v >= M.THRESHOLDS[C.ASSUMPTIONS["max_stage_index_at_dispatch"] + 1]:
                latest = m
                break
            m += step
        end = rng.uniform(cold0 + 360, max(cold0 + 360, latest))  # at least 6 h of cold storage
        dock_min = rng.uniform(*C.DOCK_DWELL_MIN)
        n = int(end // step)
        wh = LOCATIONS[warehouse_id]["name"]
        tvc = crate.initial_tvc
        start_ts = self.sim_time - timedelta(minutes=step * (n + 1))
        crate.loaded_at = start_ts.strftime(TS_FMT)
        dock_start = end - dock_min
        temp = T.temp_at(tid, 0)
        for i in range(n + 1):
            minute = i * step
            base = T.temp_at(tid, minute)
            if minute < cold0:
                stage, loc = "farm_pickup", "Supplier pickup & pre-cooling (real shipment trace)"
                temp = base
            elif minute >= dock_start:
                stage, loc = "loading_dock", f"{wh} – loading dock"
                temp = base + M.warm_delta(minute - dock_start)
            else:
                stage, loc = "cold_room", f"{wh} – cold room"
                temp = base
            tvc, ratio, extra = M.step(tvc, temp, step / 60, crate.product)
            ts = (start_ts + timedelta(minutes=step * (i + 1))).strftime(TS_FMT)
            self._rows.append((crate.id, ts, stage, loc, None, round(temp, 2), round(FRIDGE_RH, 1), None, 0,
                               tvc, M.freshness_score(tvc), ratio, extra, step))
        crate.tvc_kin = tvc
        crate.temp_c = temp
        crate.humidity = FRIDGE_RH
        crate.rate = M.mu(temp, crate.product) / M.mu(M.REF_T, crate.product)

    def _load_trip(self, truck, initial=False):
        restaurants = [l for l in LOCATIONS.values() if l["type"] == "restaurant"]
        for _ in range(C.CRATES_PER_TRUCK):
            product = self.rng.choice(M.SIM_PRODUCTS)
            options = [r for r in restaurants if r["demand_kg_per_day"].get(product, 0) > 0]
            dest = self.rng.choice(options)
            crate = self._new_crate(truck, truck.origin_id, dest["id"], product=product)
            self.crates[crate.id] = crate
        truck.status = "en_route"
        self.order_stops(truck)
        if not initial:
            db.insert_readings(self._rows)
            self._rows = []

    # ------------------------------------------------------------------ helpers
    def ts(self):
        return self.sim_time.strftime(TS_FMT)

    def travel(self, truck, loc):
        km = haversine_km(truck.lat, truck.lng, loc["lat"], loc["lng"]) * C.ROAD_FACTOR
        return km, km / C.TRUCK_SPEED_KMH

    def order_stops(self, truck):
        if not truck.stops:
            return
        fixed, rest = ([truck.stops[0]], truck.stops[1:]) if truck.service_left_min > 0 else ([], truck.stops)

        def key(stop):
            hrs = [self.crates[c].hours_left for c in stop["crate_ids"] if c in self.crates]
            loc = LOCATIONS[stop["location_id"]]
            return (min(hrs) if hrs else 1e9, haversine_km(truck.lat, truck.lng, loc["lat"], loc["lng"]))

        truck.stops = fixed + sorted(rest, key=key)

    def stop_etas(self, truck):
        out, eta = [], 0.0
        lat, lng = truck.lat, truck.lng
        for i, stop in enumerate(truck.stops):
            loc = LOCATIONS[stop["location_id"]]
            if i == 0 and truck.service_left_min > 0:
                out.append(0)
                eta += truck.service_left_min
                continue
            km = haversine_km(lat, lng, loc["lat"], loc["lng"]) * C.ROAD_FACTOR
            eta += km / C.TRUCK_SPEED_KMH * 60
            out.append(round(eta))
            eta += C.STOP_SERVICE_MIN
            lat, lng = loc["lat"], loc["lng"]
        return out

    def biggest_cause(self, crate):
        try:
            import journey
            return journey.build(self, crate.id)["blame"]["stage"] or "in_transit"
        except Exception:
            return "in_transit"

    def _remove_from_stops(self, crate):
        if not crate.truck_id:
            return
        truck = self.trucks[crate.truck_id]
        for i, stop in enumerate(truck.stops):
            if crate.id in stop["crate_ids"]:
                stop["crate_ids"].remove(crate.id)
                if not stop["crate_ids"] and not (i == 0 and truck.service_left_min > 0):
                    truck.stops.pop(i)
                break

    def _archive(self, crate):
        self.crates.pop(crate.id, None)
        self.archive[crate.id] = crate

    # ------------------------------------------------------------------ redirect application
    def apply_redirect(self, crate, dec, reason):
        truck = self.trucks[crate.truck_id]
        from_id = crate.destination_id
        decision = dec["decision"]
        loc = dec["location"]
        self.counters["redirect"] += 1
        record = {
            "id": f"RD-{self.counters['redirect']}", "ts": self.ts(), "crate_id": crate.id, "truck_id": truck.id,
            "product": crate.product, "weight_kg": crate.weight_kg, "hours_left": crate.hours_left,
            "decision": decision, "from_location_id": from_id, "to_location_id": loc["id"] if loc else None,
            "from_point": [round(truck.lat, 5), round(truck.lng, 5)], "travel_min": round(dec["travel_h"] * 60),
            "reason": reason, "alternatives": dec["alternatives"],
            "kg_saved": crate.weight_kg if decision != "DISCARD" else 0,
        }
        self._remove_from_stops(crate)
        if decision == "DISCARD":
            crate.discarded = True
            crate.redirect_reason = reason
            self.impact["kg_wasted"] += crate.weight_kg
            self._archive(crate)
            alerts.make(self, "discarded", "critical", f"{crate.id} {crate.p['label']} discarded — {reason}", crate.id, truck.id)
        else:
            crate.destination_id = loc["id"]
            crate.redirected = True
            crate.redirect_reason = reason
            stop = next((s for s in truck.stops if s["location_id"] == loc["id"]), None)
            if stop is None:
                truck.stops.append({"location_id": loc["id"], "crate_ids": [crate.id]})
            else:
                stop["crate_ids"].append(crate.id)
            self.impact["crates_redirected"] += 1
            self.impact["kg_saved"] += crate.weight_kg
            self.impact["rejections_avoided"] += 1
            if decision == "DONATE":
                self.impact["crates_donated"] += 1
                alerts.make(self, "donated", "info", f"{crate.id} {crate.p['label']} donated to {loc['name']}", crate.id, truck.id)
            else:
                alerts.make(self, "rerouted", "info", f"{crate.id} rerouted to {loc['name']}", crate.id, truck.id)
        self.order_stops(truck)
        self.redirects.insert(0, record)
        del self.redirects[40:]
        self.new_redirects.append(record)

    # ------------------------------------------------------------------ scenarios
    def get_crate(self, crate_id):
        return self.crates.get(crate_id)

    def heat(self, crate, minutes=60):
        """Crate left outside refrigeration for `minutes` (real warm-up curve, then real cool-down)."""
        crate.heat = Event(start=self.now, end=self.now + max(1.0, float(minutes)))

    def shock(self, crate):
        # No public data links shocks to spoilage, so a shock is logged as an alert only (no freshness change).
        alerts.make(self, "shock", "warning", f"{crate.id} {crate.p['label']} shock detected (logged for inspection)",
                    crate.id, crate.truck_id)

    def door(self, truck):
        truck.door = Event(start=self.now)
        n = sum(1 for c in self.crates.values() if c.truck_id == truck.id)
        alerts.make(self, "door_open", "warning", f"{truck.name} door open — {n} crates exposed", None, truck.id)

    def compressor(self, truck, ok):
        if not ok and truck.compressor_ok:
            truck.compressor = Event(start=self.now)
            n = sum(1 for c in self.crates.values() if c.truck_id == truck.id)
            alerts.make(self, "compressor_fail", "critical", f"{truck.name} compressor failure — {n} crates warming", None, truck.id)
        elif ok and truck.compressor is not None and truck.compressor.end is None:
            truck.compressor.end = self.now

    # ------------------------------------------------------------------ tick
    def tick(self):
        dt_min = self.minutes_per_tick
        dt_h = dt_min / 60
        self.now += dt_min
        self.sim_time += timedelta(minutes=dt_min)
        self.tick_n += 1
        self.new_alerts, self.new_redirects = [], []
        for t in self.trucks.values():
            t.trace_pos += dt_min
            if t.door is not None and self.now - t.door.start > len(M._DOOR):
                t.door = None
        self._move_trucks(dt_min)
        rows = []
        tag = mqtt_tag.get_latest()
        for crate in list(self.crates.values()):
            self._update_crate(crate, dt_h, dt_min, tag, rows)
            alerts.check_crate(self, crate)
        redirect.evaluate(self)
        db.insert_readings(rows)

    def _crate_temp(self, crate):
        if crate.truck_id:
            t = self.trucks[crate.truck_id]
            base = T.temp_at(t.trace_id, t.trace_pos)
            excess = max(_event_excess(crate.heat, self.now), _event_excess(t.compressor, self.now))
            door = M.door_delta(self.now - t.door.start) if t.door else 0.0
            hum = FRIDGE_RH + (door / DOOR_PEAK) * M.DOOR_HUMIDITY_DELTA
            return base + excess + door, hum, t.door_open_at(self.now)
        crate.trace_pos += self.minutes_per_tick
        base = T.temp_at(crate.trace_id, crate.trace_pos)
        return base + _event_excess(crate.heat, self.now), FRIDGE_RH, False

    def _update_crate(self, crate, dt_h, dt_min, tag, rows):
        live = crate.id == C.LIVE_TAG_ID and tag is not None
        if live:
            crate.temp_c = M.safe_float(tag.get("temp_c"), crate.temp_c)
            crate.humidity = M.safe_float(tag.get("humidity"), crate.humidity)
            door = bool(tag.get("door_open", False))
            if door and not crate.last_tag_door:
                alerts.make(self, "door_open", "warning", f"{crate.id} live tag: door opened", crate.id, None)
            crate.last_tag_door = crate.door_open = door
        else:
            crate.temp_c, crate.humidity, crate.door_open = self._crate_temp(crate)
        crate.humidity = max(0.0, min(100.0, crate.humidity))
        crate.tvc_kin, crate.rate, extra = M.step(crate.tvc_kin, crate.temp_c, dt_h, crate.product)
        if crate.gas is not None:
            for _ in range(max(1, int(dt_min))):
                crate.tvc_gas = crate.gas.push(crate.tvc_kin)
        crate.refresh()
        if crate.truck_id:
            truck = self.trucks[crate.truck_id]
            truck.live_extra_loss_h += extra
            stage, loc_name = "in_transit", f"{truck.name} – {truck.driver}"
        else:
            stage, loc_name = "cold_room", f"{LOCATIONS[crate.warehouse_id]['name']} – cold room"
        crate.stage = stage
        rows.append((crate.id, self.ts(), stage, loc_name, crate.truck_id, round(crate.temp_c, 2),
                     round(crate.humidity, 1), M.gas_index(crate.tvc_gas), int(crate.door_open), crate.tvc,
                     crate.freshness_score, crate.rate, extra, dt_min))

    def _move_trucks(self, dt_min):
        speed_straight = C.TRUCK_SPEED_KMH / C.ROAD_FACTOR
        for t in self.trucks.values():
            if t.status == "at_warehouse":
                t.wait_ticks -= 1
                if t.wait_ticks <= 0:
                    self._load_trip(t)
                continue
            remaining = float(dt_min)
            while remaining > 1e-9:
                if t.service_left_min > 0:
                    use = min(remaining, t.service_left_min)
                    t.service_left_min -= use
                    remaining -= use
                    if t.service_left_min <= 1e-9:
                        t.service_left_min = 0.0
                        self._deliver(t, t.stops.pop(0))
                    continue
                if not t.stops:
                    origin = LOCATIONS[t.origin_id]
                    t.lat, t.lng = origin["lat"], origin["lng"]
                    t.status = "at_warehouse"
                    t.wait_ticks = C.TRUCK_WAIT_TICKS
                    break
                loc = LOCATIONS[t.stops[0]["location_id"]]
                d = haversine_km(t.lat, t.lng, loc["lat"], loc["lng"])
                step_km = speed_straight * remaining / 60
                if d <= step_km:
                    t.lat, t.lng = loc["lat"], loc["lng"]
                    remaining -= d / speed_straight * 60
                    t.service_left_min = C.STOP_SERVICE_MIN
                else:
                    f = step_km / d
                    t.lat += (loc["lat"] - t.lat) * f
                    t.lng += (loc["lng"] - t.lng) * f
                    remaining = 0

    def _deliver(self, truck, stop):
        loc = LOCATIONS[stop["location_id"]]
        for cid in stop["crate_ids"]:
            crate = self.crates.get(cid)
            if crate is None:
                continue
            accepted = crate.hours_left >= loc["min_hours_needed"] and crate.status != "spoiled"
            self.counters["delivery"] += 1
            self.deliveries.insert(0, {"id": f"D-{self.counters['delivery']}", "ts": self.ts(), "crate_id": cid,
                                       "location_id": loc["id"], "accepted": accepted, "hours_left": crate.hours_left})
            del self.deliveries[40:]
            self.impact["deliveries_completed"] += 1
            if not accepted:
                self.impact["deliveries_rejected"] += 1
                self.impact["kg_wasted"] += crate.weight_kg
                alerts.make(self, "delivery_rejected", "critical",
                            f"{cid} {crate.p['label']} rejected at {loc['name']} ({crate.hours_left:.1f} h left)", cid, truck.id)
            crate.delivered = True
            crate.delivered_to = loc["id"]
            self._archive(crate)

    # ------------------------------------------------------------------ serialisation
    def crate_dict(self, c):
        dest = LOCATIONS.get(c.destination_id) if c.destination_id else None
        if c.truck_id:
            t = self.trucks[c.truck_id]
            lat, lng = t.lat, t.lng
        else:
            wh = LOCATIONS[c.warehouse_id or "WH-1"]
            lat, lng = wh["lat"], wh["lng"]
        eta = None
        if c.truck_id and c.id in self.crates:
            t = self.trucks[c.truck_id]
            for stop, e in zip(t.stops, self.stop_etas(t)):
                if c.id in stop["crate_ids"]:
                    eta = e
        return {
            "id": c.id, "product": c.product, "product_label": c.p["label"], "emoji": c.p["emoji"],
            "weight_kg": c.weight_kg, "truck_id": c.truck_id, "stage": c.stage,
            "temp_c": round(c.temp_c, 1), "humidity": round(c.humidity, 1),
            "voc_index": M.gas_index(c.tvc_gas), "door_open": c.door_open,
            "tvc": round(c.tvc, 2), "tvc_kinetic": round(c.tvc_kin, 2),
            "tvc_gas": None if c.tvc_gas is None else round(c.tvc_gas, 2),
            "quality_stage": c.stage_name, "gas": c.gas.reading_dict() if c.gas else None,
            "freshness_score": c.freshness_score, "hours_left": c.hours_left,
            "hours_left_if_unchanged": c.hours_left_if_unchanged, "status": c.status,
            "loaded_at": c.loaded_at,
            "destination_id": c.destination_id, "destination_name": dest["name"] if dest else None,
            "original_destination_id": c.original_destination_id,
            "redirected": c.redirected, "redirect_reason": c.redirect_reason,
            "eta_min": eta, "is_live_tag": c.id == C.LIVE_TAG_ID,
            "heat_active": bool(c.heat and (c.heat.end is None or self.now < c.heat.end)),
            "lat": round(lat, 5), "lng": round(lng, 5),
        }

    def truck_dict(self, t):
        etas = self.stop_etas(t)
        return {
            "id": t.id, "name": t.name, "driver": t.driver, "color": t.color, "status": t.status,
            "lat": round(t.lat, 5), "lng": round(t.lng, 5),
            "compressor_ok": t.compressor_ok, "door_open": t.door_open_at(self.now),
            "temp_trace": t.trace_id, "air_temp_c": round(T.temp_at(t.trace_id, t.trace_pos), 1),
            "stops": [{"location_id": s["location_id"], "crate_ids": list(s["crate_ids"]), "eta_min": e}
                      for s, e in zip(t.stops, etas)],
            "route_points": [[round(t.lat, 5), round(t.lng, 5)]]
                            + [[LOCATIONS[s["location_id"]]["lat"], LOCATIONS[s["location_id"]]["lng"]] for s in t.stops],
            "crate_ids": [c.id for c in self.crates.values() if c.truck_id == t.id],
        }

    def to_state(self):
        on_trucks = [c for c in self.crates.values() if c.truck_id]
        fefo = sorted(on_trucks, key=lambda c: (c.hours_left, c.id))
        fifo = sorted(on_trucks, key=lambda c: (c.loaded_at, c.id))
        return {
            "type": "state", "tick": self.tick_n, "sim_time": self.ts(), "paused": self.paused,
            "minutes_per_tick": self.minutes_per_tick, "seed": self.seed,
            "crates": [self.crate_dict(c) for c in sorted(self.crates.values(), key=lambda c: c.id)],
            "trucks": [self.truck_dict(t) for t in self.trucks.values()],
            "dispatch": {
                "fefo": [{"rank": i + 1, "crate_id": c.id, "product": c.product, "hours_left": c.hours_left,
                          "destination_id": c.destination_id,
                          "feasible": redirect.feasible(self, c, c.destination_id)} for i, c in enumerate(fefo)],
                "fifo": [{"rank": i + 1, "crate_id": c.id, "product": c.product, "hours_left": c.hours_left,
                          "destination_id": c.original_destination_id,
                          "feasible": redirect.feasible(self, c, c.original_destination_id),
                          "would_be_rejected": not redirect.feasible(self, c, c.original_destination_id)}
                         for i, c in enumerate(fifo)],
            },
            "alerts": self.alerts[:30], "new_alerts": self.new_alerts,
            "redirects": self.redirects[:20], "new_redirects": self.new_redirects,
            "deliveries": self.deliveries[:20], "impact": dict(self.impact),
        }
