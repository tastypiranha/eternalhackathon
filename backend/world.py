"""FreshSense simulator: crates, trucks, scenarios, history back-fill, tick loop (master plan 6.5)."""
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import alerts
import config as C
import db
import engine
import mqtt_tag
import redirect
from config import LOCATIONS, PRODUCTS

TS_FMT = "%Y-%m-%dT%H:%M:%S"

# (crate_id, product, truck_id, destination_id, (hours_left_lo, hours_left_hi))  — master 6.5
SEEDS = [
    ("C-001", "dairy", None, None, (100, 130)),
    ("C-002", "greens", "T-1", "R-09", (60, 90)),
    ("C-004", "chicken", "T-1", "R-02", (45, 60)),
    ("C-010", "dairy", "T-1", "R-01", (90, 130)),
    ("C-003", "chicken", "T-2", "R-06", (27, 30)),
    ("C-005", "dairy", "T-2", "R-07", (90, 130)),
    ("C-006", "greens", "T-2", "R-01", (60, 90)),
    ("C-011", "chicken", "T-2", "R-06", (45, 60)),
    ("C-007", "greens", "T-3", "R-04", (50, 70)),
    ("C-008", "chicken", "T-3", "R-07", (31, 34)),
    ("C-009", "dairy", "T-3", "R-10", (90, 130)),
    ("C-012", "greens", "T-3", "R-03", (50, 80)),
]
HERO_CRATE = "C-003"
FARM_AREA = {"WH-1": "Hoskote", "WH-2": "Anekal"}


def haversine_km(lat1, lng1, lat2, lng2):
    la1, lo1, la2, lo2 = map(math.radians, (lat1, lng1, lat2, lng2))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


@dataclass
class Crate:
    id: str
    product: str
    weight_kg: float
    truck_id: str | None = None
    warehouse_id: str | None = None
    stage: str = "in_transit"
    temp_c: float = 3.0
    humidity: float = 88.0
    voc_index: float = 40.0
    door_open: bool = False
    consumed: float = 0.0
    initial_consumed: float = 0.0
    eff_rate: float = 1.0
    hours_left: float = 0.0
    hours_left_if_unchanged: float = 0.0
    freshness_score: float = 100.0
    status: str = "fresh"
    last_status: str = "fresh"
    loaded_at: str = ""
    destination_id: str | None = None
    original_destination_id: str | None = None
    redirected: bool = False
    redirect_reason: str | None = None
    heat_until: datetime | None = None
    excursion_ticks: int = 0
    in_excursion: bool = False
    delivered: bool = False
    delivered_to: str | None = None
    discarded: bool = False
    last_tag_door: bool = False

    @property
    def p(self):
        return PRODUCTS[self.product]

    def refresh(self):
        d = engine.derived(self.consumed, self.eff_rate, self.voc_index, self.p)
        self.hours_left = d["hours_left"]
        self.hours_left_if_unchanged = d["hours_left_if_unchanged"]
        self.freshness_score = d["freshness_score"]
        self.status = d["status"]


@dataclass
class Truck:
    id: str
    name: str
    driver: str
    color: str
    origin_id: str
    setpoint_c: float
    lat: float
    lng: float
    past_week_extra_loss_h: float = 0.0
    past_week_excursions: int = 0
    status: str = "en_route"
    stops: list = field(default_factory=list)  # [{"location_id": str, "crate_ids": [str]}]
    service_left_min: float = 0.0
    wait_ticks: int = 0
    compressor_ok: bool = True
    door_until: datetime | None = None
    live_extra_loss_h: float = 0.0
    live_excursions: int = 0

    @property
    def door_open(self):
        return self.door_until is not None


class World:
    def __init__(self):
        self.reset()

    # ------------------------------------------------------------------ reset / seeding
    def reset(self):
        db.reset_db()
        mqtt_tag.clear()
        self.rng = random.Random(C.RANDOM_SEED)
        now = datetime.now()
        self.sim_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
        self.tick_n = 0
        self.paused = C.START_PAUSED
        self.minutes_per_tick = C.SIM_MINUTES_PER_TICK
        self.crates: dict[str, Crate] = {}
        self.archive: dict[str, Crate] = {}
        self.alerts, self.new_alerts = [], []
        self.redirects, self.new_redirects = [], []
        self.deliveries = []
        self.counters = {"alert": 0, "redirect": 0, "delivery": 0}
        self.next_crate_num = 13
        self.impact = {
            "crates_redirected": 0, "crates_donated": 0, "kg_saved": 0, "rejections_avoided": 0,
            "deliveries_completed": 0, "deliveries_rejected": 0, "kg_wasted": 0,
        }
        self.trucks: dict[str, Truck] = {}
        for t in C.TRUCKS:
            origin = LOCATIONS[t["origin_id"]]
            self.trucks[t["id"]] = Truck(
                id=t["id"], name=t["name"], driver=t["driver"], color=t["color"],
                origin_id=t["origin_id"], setpoint_c=t["setpoint_c"],
                lat=origin["lat"], lng=origin["lng"],
                past_week_extra_loss_h=t.get("past_week_extra_loss_h", 0),
                past_week_excursions=t.get("past_week_excursions", 0),
            )
        rows = []
        for cid, product, truck_id, dest, (lo, hi) in SEEDS:
            if cid == C.LIVE_TAG_ID:
                lo = max(lo, 122)  # keep the cold-room tag crate clearly "fresh" (no noisy status alert)
            target = self.rng.uniform(lo, hi)
            wh = self.trucks[truck_id].origin_id if truck_id else "WH-1"
            crate = self._new_crate(cid, product, truck_id, wh, dest, target, rows,
                                    hero=(cid == HERO_CRATE), hours_cap=90)
            self.crates[cid] = crate
        db.insert_readings(rows)
        for t in self.trucks.values():
            self.order_stops(t)

    def _new_crate(self, cid, product, truck_id, warehouse_id, dest, target_hours_left, rows,
                   hero=False, hours_cap=60):
        p = PRODUCTS[product]
        crate = Crate(id=cid, product=product, weight_kg=p["weight_kg"])
        self._backfill(crate, warehouse_id, target_hours_left, rows, hero=hero, hours_cap=hours_cap)
        if truck_id:
            crate.truck_id = truck_id
            crate.stage = "in_transit"
            crate.destination_id = dest
            crate.original_destination_id = dest
            truck = self.trucks[truck_id]
            stop = next((s for s in truck.stops if s["location_id"] == dest), None)
            if stop is None:
                truck.stops.append({"location_id": dest, "crate_ids": [cid]})
            else:
                stop["crate_ids"].append(cid)
        else:
            crate.warehouse_id = warehouse_id
            crate.stage = "cold_room"
        crate.refresh()
        crate.last_status = crate.status
        return crate

    def _backfill(self, crate, warehouse_id, target_hours_left, rows, hero=False, hours_cap=60):
        """Generate past readings: farm_pickup -> loading_dock -> cold_room, landing on the target."""
        p = crate.p
        rng = self.rng
        wh_name = LOCATIONS[warehouse_id]["name"]
        step_min = C.BACKFILL_STEP_MIN
        dt_h = step_min / 60
        consumed = rng.uniform(0.0, 0.04)
        crate.initial_consumed = consumed
        target_consumed = 1 - target_hours_left / p["shelf_life_ref_h"]

        plan = [("farm_pickup", f"Supplier pickup – {FARM_AREA.get(warehouse_id, 'farm')} farm cluster (demo)", 8.0, 80)
                for _ in range(60 // step_min)]
        dock_name = f"{wh_name} – loading dock"
        if hero:
            plan += [("loading_dock", dock_name, 18.0, 70)] * 4 + [("loading_dock", dock_name, 10.0, 70)]
        else:
            dock_temp = rng.uniform(9, 16)
            plan += [("loading_dock", dock_name, dock_temp, 70)] * (rng.choice([40, 50, 60]) // step_min)

        samples = []  # (stage, location, temp, hum, voc, consumed, score, rate, extra)
        voc = 40.0

        def run(stage, loc, temp_target, hum_target):
            nonlocal consumed, voc
            temp = temp_target + rng.uniform(-0.3, 0.3)
            hum = hum_target + rng.uniform(-1, 1)
            voc += (engine.voc_target(consumed, temp, p) - voc) * 0.3 + rng.uniform(-5, 5)
            voc = min(500.0, max(0.0, voc))
            consumed, r, extra = engine.step(consumed, temp, voc, dt_h, p)
            samples.append((stage, loc, temp, hum, voc, consumed, round(100 * (1 - consumed), 1), r, extra))

        for stage, loc, t, h in plan:
            run(stage, loc, t, h)
        cold_name = f"{wh_name} – cold room"
        max_steps = int(hours_cap * 60 / step_min)
        n = 0
        while (consumed < target_consumed and n < max_steps) or n < 12:
            run("cold_room", cold_name, p["t_ref_c"], C.HUMIDITY_NORMAL)
            n += 1

        start = self.sim_time - timedelta(minutes=step_min * len(samples))
        for i, (stage, loc, temp, hum, v, cons, score, r, extra) in enumerate(samples):
            ts = (start + timedelta(minutes=step_min * (i + 1))).strftime(TS_FMT)
            rows.append((crate.id, ts, stage, loc, None, round(temp, 2), round(hum, 1), round(v, 1), 0,
                         cons, score, r, extra, step_min))
        last = samples[-1]
        crate.temp_c, crate.humidity, crate.voc_index, crate.consumed, crate.eff_rate = last[2], last[3], last[4], last[5], last[7]
        crate.loaded_at = start.strftime(TS_FMT)

    # ------------------------------------------------------------------ helpers
    def ts(self):
        return self.sim_time.strftime(TS_FMT)

    def travel(self, truck, loc):
        """Road km and hours from the truck's position to a location."""
        km = haversine_km(truck.lat, truck.lng, loc["lat"], loc["lng"]) * C.ROAD_FACTOR
        return km, km / C.TRUCK_SPEED_KMH

    def order_stops(self, truck):
        """Greedy urgency routing: most urgent stop first, ties -> nearest. Never reorder the stop being unloaded."""
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
                being_unloaded = i == 0 and truck.service_left_min > 0
                if not stop["crate_ids"] and not being_unloaded:
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
            "id": f"RD-{self.counters['redirect']}",
            "ts": self.ts(),
            "crate_id": crate.id,
            "truck_id": truck.id,
            "product": crate.product,
            "weight_kg": crate.weight_kg,
            "hours_left": crate.hours_left,
            "decision": decision,
            "from_location_id": from_id,
            "to_location_id": loc["id"] if loc else None,
            "from_point": [round(truck.lat, 5), round(truck.lng, 5)],
            "travel_min": round(dec["travel_h"] * 60),
            "reason": reason,
            "alternatives": dec["alternatives"],
            "kg_saved": crate.weight_kg if decision != "DISCARD" else 0,
        }
        self._remove_from_stops(crate)
        if decision == "DISCARD":
            crate.discarded = True
            crate.redirect_reason = reason
            self.impact["kg_wasted"] += crate.weight_kg
            self._archive(crate)
            alerts.make(self, "discarded", "critical", f"{crate.id} {crate.p['label']} discarded — {reason}",
                        crate.id, truck.id)
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
                alerts.make(self, "donated", "info", f"{crate.id} {crate.p['label']} donated to {loc['name']}",
                            crate.id, truck.id)
            else:
                alerts.make(self, "rerouted", "info", f"{crate.id} rerouted to {loc['name']}", crate.id, truck.id)
        self.order_stops(truck)
        self.redirects.insert(0, record)
        del self.redirects[40:]
        self.new_redirects.append(record)

    # ------------------------------------------------------------------ scenarios
    def get_crate(self, crate_id):
        return self.crates.get(crate_id)

    def heat(self, crate):
        crate.heat_until = self.sim_time + timedelta(minutes=C.HEAT_EVENT_MIN)

    def shock(self, crate):
        crate.consumed = min(1.0, crate.consumed + crate.p["shock_penalty"])
        crate.refresh()
        alerts.make(self, "shock", "warning",
                    f"{crate.id} {crate.p['label']} shock detected — {crate.p['shock_penalty'] * 100:.0f}% of life lost",
                    crate.id, crate.truck_id)

    def door(self, truck):
        truck.door_until = self.sim_time + timedelta(minutes=C.DOOR_EVENT_MIN)
        n = sum(1 for c in self.crates.values() if c.truck_id == truck.id)
        alerts.make(self, "door_open", "warning", f"{truck.name} door open — {n} crates exposed", None, truck.id)

    def compressor(self, truck, ok):
        was_ok = truck.compressor_ok
        truck.compressor_ok = ok
        if was_ok and not ok:
            n = sum(1 for c in self.crates.values() if c.truck_id == truck.id)
            alerts.make(self, "compressor_fail", "critical", f"{truck.name} compressor failure — {n} crates warming",
                        None, truck.id)

    # ------------------------------------------------------------------ tick
    def tick(self):
        dt_min = self.minutes_per_tick
        dt_h = dt_min / 60
        self.sim_time += timedelta(minutes=dt_min)
        self.tick_n += 1
        self.new_alerts, self.new_redirects = [], []
        for c in self.crates.values():
            if c.heat_until and c.heat_until <= self.sim_time:
                c.heat_until = None
        for t in self.trucks.values():
            if t.door_until and t.door_until <= self.sim_time:
                t.door_until = None

        self._move_trucks(dt_min)

        rows = []
        tag = mqtt_tag.get_latest()
        for crate in list(self.crates.values()):
            self._update_crate(crate, dt_h, dt_min, tag, rows)
            alerts.check_crate(self, crate)
        redirect.evaluate(self)
        db.insert_readings(rows)

    def _targets(self, crate):
        if not crate.truck_id:
            return crate.p["t_ref_c"], C.HUMIDITY_NORMAL
        truck = self.trucks[crate.truck_id]
        if crate.heat_until:
            return C.HEAT_EVENT_TARGET_C, C.HUMIDITY_DOOR_OPEN
        if not truck.compressor_ok or truck.door_open:
            return C.AMBIENT_C, C.HUMIDITY_DOOR_OPEN
        return truck.setpoint_c, C.HUMIDITY_NORMAL

    def _update_crate(self, crate, dt_h, dt_min, tag, rows):
        rng = self.rng
        p = crate.p
        live = crate.id == C.LIVE_TAG_ID and tag is not None
        if live:
            crate.temp_c = float(tag.get("temp_c", crate.temp_c))
            crate.humidity = float(tag.get("humidity", crate.humidity))
            crate.voc_index = float(tag.get("voc_index", crate.voc_index))
            door = bool(tag.get("door_open", False))
            if door and not crate.last_tag_door:
                alerts.make(self, "door_open", "warning", f"{crate.id} live tag: door opened", crate.id, None)
            crate.last_tag_door = door
            crate.door_open = door
        else:
            target_t, target_h = self._targets(crate)
            crate.temp_c += (target_t - crate.temp_c) * C.TEMP_APPROACH + rng.uniform(-C.NOISE_TEMP_C, C.NOISE_TEMP_C)
            crate.humidity += (target_h - crate.humidity) * 0.3 + rng.uniform(-1, 1)
            crate.humidity = min(100.0, max(0.0, crate.humidity))
            crate.voc_index += (engine.voc_target(crate.consumed, crate.temp_c, p) - crate.voc_index) * 0.3 + rng.uniform(-5, 5)
            crate.voc_index = min(500.0, max(0.0, crate.voc_index))
            crate.door_open = self.trucks[crate.truck_id].door_open if crate.truck_id else False

        crate.consumed, crate.eff_rate, extra = engine.step(crate.consumed, crate.temp_c, crate.voc_index, dt_h, p)
        crate.refresh()
        if crate.truck_id:
            truck = self.trucks[crate.truck_id]
            truck.live_extra_loss_h += extra
            stage, loc_name = "in_transit", f"{truck.name} – {truck.driver}"
        else:
            stage, loc_name = "cold_room", f"{LOCATIONS[crate.warehouse_id]['name']} – cold room"
        crate.stage = stage
        rows.append((crate.id, self.ts(), stage, loc_name, crate.truck_id, round(crate.temp_c, 2),
                     round(crate.humidity, 1), round(crate.voc_index, 1), int(crate.door_open), crate.consumed,
                     crate.freshness_score, crate.eff_rate, extra, dt_min))

    def _move_trucks(self, dt_min):
        speed_straight = C.TRUCK_SPEED_KMH / C.ROAD_FACTOR  # straight-line km per hour
        for t in self.trucks.values():
            if t.status == "at_warehouse":
                t.wait_ticks -= 1
                if t.wait_ticks <= 0:
                    self._load_new_trip(t)
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
            self.deliveries.insert(0, {
                "id": f"D-{self.counters['delivery']}", "ts": self.ts(), "crate_id": cid,
                "location_id": loc["id"], "accepted": accepted, "hours_left": crate.hours_left,
            })
            del self.deliveries[40:]
            self.impact["deliveries_completed"] += 1
            if not accepted:
                self.impact["deliveries_rejected"] += 1
                self.impact["kg_wasted"] += crate.weight_kg
                alerts.make(self, "delivery_rejected", "critical",
                            f"{cid} {crate.p['label']} rejected at {loc['name']} ({crate.hours_left:.1f} h left)",
                            cid, truck.id)
            crate.delivered = True
            crate.delivered_to = loc["id"]
            self._archive(crate)

    def _load_new_trip(self, truck):
        restaurants = [l for l in LOCATIONS.values() if l["type"] == "restaurant"]
        rows = []
        for _ in range(4):
            cid = f"C-{self.next_crate_num:03d}"
            self.next_crate_num += 1
            product = self.rng.choice(list(PRODUCTS))
            dest = self.rng.choice([r for r in restaurants if r["demand_kg_per_day"][product] > 0])
            target = self.rng.uniform(0.5, 0.9) * PRODUCTS[product]["shelf_life_ref_h"]
            crate = self._new_crate(cid, product, truck.id, truck.origin_id, dest["id"], target, rows,
                                    hours_cap=self.rng.uniform(12, 24))
            self.crates[cid] = crate
        db.insert_readings(rows)
        truck.status = "en_route"
        self.order_stops(truck)

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
            etas = self.stop_etas(t)
            for stop, e in zip(t.stops, etas):
                if c.id in stop["crate_ids"]:
                    eta = e
        return {
            "id": c.id, "product": c.product, "product_label": c.p["label"], "emoji": c.p["emoji"],
            "weight_kg": c.weight_kg, "truck_id": c.truck_id, "stage": c.stage,
            "temp_c": round(c.temp_c, 1), "humidity": round(c.humidity, 1), "voc_index": round(c.voc_index),
            "door_open": c.door_open,
            "freshness_score": c.freshness_score, "hours_left": c.hours_left,
            "hours_left_if_unchanged": c.hours_left_if_unchanged, "status": c.status,
            "loaded_at": c.loaded_at,
            "destination_id": c.destination_id, "destination_name": dest["name"] if dest else None,
            "original_destination_id": c.original_destination_id,
            "redirected": c.redirected, "redirect_reason": c.redirect_reason,
            "eta_min": eta,
            "is_live_tag": c.id == C.LIVE_TAG_ID,
            "lat": round(lat, 5), "lng": round(lng, 5),
        }

    def truck_dict(self, t):
        etas = self.stop_etas(t)
        return {
            "id": t.id, "name": t.name, "driver": t.driver, "color": t.color, "status": t.status,
            "lat": round(t.lat, 5), "lng": round(t.lng, 5),
            "compressor_ok": t.compressor_ok, "door_open": t.door_open, "setpoint_c": t.setpoint_c,
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
            "type": "state",
            "tick": self.tick_n,
            "sim_time": self.ts(),
            "paused": self.paused,
            "minutes_per_tick": self.minutes_per_tick,
            "crates": [self.crate_dict(c) for c in sorted(self.crates.values(), key=lambda c: c.id)],
            "trucks": [self.truck_dict(t) for t in self.trucks.values()],
            "dispatch": {
                "fefo": [
                    {"rank": i + 1, "crate_id": c.id, "product": c.product, "hours_left": c.hours_left,
                     "destination_id": c.destination_id, "feasible": redirect.feasible(self, c, c.destination_id)}
                    for i, c in enumerate(fefo)
                ],
                "fifo": [
                    {"rank": i + 1, "crate_id": c.id, "product": c.product, "hours_left": c.hours_left,
                     "destination_id": c.original_destination_id,
                     "feasible": redirect.feasible(self, c, c.original_destination_id),
                     "would_be_rejected": not redirect.feasible(self, c, c.original_destination_id)}
                    for i, c in enumerate(fifo)
                ],
            },
            "alerts": self.alerts[:30],
            "new_alerts": self.new_alerts,
            "redirects": self.redirects[:20],
            "new_redirects": self.new_redirects,
            "deliveries": self.deliveries[:20],
            "impact": dict(self.impact),
        }
