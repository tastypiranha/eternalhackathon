"""FreshSense backend: REST + WebSocket (master plan 6.8). Run: uvicorn main:app --port 8000

All handlers are `async def` so they run on the same asyncio thread as the tick loop (no races).
"""
import asyncio
import time
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import analytics
import config as C
import journey
import mqtt_tag
from world import World

world: World | None = None


class Manager:
    def __init__(self):
        self.sockets: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.sockets.add(ws)
        await ws.send_json(world.to_state())

    def disconnect(self, ws: WebSocket):
        self.sockets.discard(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in list(self.sockets):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.sockets.discard(ws)


manager = Manager()


async def tick_loop():
    while True:
        await asyncio.sleep(C.TICK_SECONDS)
        try:
            started = time.perf_counter()
            if not world.paused:
                world.tick()
            await manager.broadcast(world.to_state())
            elapsed = (time.perf_counter() - started) * 1000
            if elapsed > 200:
                print(f"[tick] slow tick: {elapsed:.0f} ms")
        except Exception:
            traceback.print_exc()  # never let the loop die


@asynccontextmanager
async def lifespan(app: FastAPI):
    global world
    world = World()
    mqtt_tag.start()
    task = asyncio.create_task(tick_loop())
    yield
    task.cancel()


app = FastAPI(title="FreshSense API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _crate(crate_id):
    c = world.get_crate(crate_id)
    if c is None:
        raise HTTPException(404, f"Unknown or inactive crate {crate_id}")
    return c


def _truck(truck_id):
    t = world.trucks.get(truck_id)
    if t is None:
        raise HTTPException(404, f"Unknown truck {truck_id}")
    return t


# ----------------------------------------------------------------------------- read endpoints
@app.get("/api/health")
async def health():
    return {"ok": True, "mqtt": mqtt_tag.status}


@app.get("/api/state")
async def state():
    return world.to_state()


@app.get("/api/locations")
async def locations():
    return {"locations": list(C.LOCATIONS.values()), "trucks": C.TRUCKS, "products": C.PRODUCTS}


@app.get("/api/crates/{crate_id}/journey")
async def crate_journey(crate_id: str):
    j = journey.build(world, crate_id)
    if j is None:
        raise HTTPException(404, f"Unknown crate {crate_id}")
    return j


@app.get("/api/analytics")
async def get_analytics():
    return analytics.build(world)


@app.get("/api/model-card")
async def model_card():
    return C.load_optional("model1_results.json") or {"available": False}


# ----------------------------------------------------------------------------- scenarios
@app.post("/api/simulate/heat/{crate_id}")
async def sim_heat(crate_id: str):
    world.heat(_crate(crate_id))
    return {"ok": True}


@app.post("/api/simulate/shock/{crate_id}")
async def sim_shock(crate_id: str):
    world.shock(_crate(crate_id))
    return {"ok": True}


@app.post("/api/simulate/door/{truck_id}")
async def sim_door(truck_id: str):
    world.door(_truck(truck_id))
    return {"ok": True}


@app.post("/api/simulate/compressor/{truck_id}/fail")
async def sim_compressor_fail(truck_id: str):
    world.compressor(_truck(truck_id), False)
    return {"ok": True}


@app.post("/api/simulate/compressor/{truck_id}/fix")
async def sim_compressor_fix(truck_id: str):
    world.compressor(_truck(truck_id), True)
    return {"ok": True}


class SimControl(BaseModel):
    paused: bool | None = None
    minutes_per_tick: int | None = None


@app.post("/api/sim/control")
async def sim_control(body: SimControl):
    if body.paused is not None:
        world.paused = body.paused
    if body.minutes_per_tick is not None:
        if not 1 <= body.minutes_per_tick <= 10:
            raise HTTPException(400, "minutes_per_tick must be 1-10")
        world.minutes_per_tick = body.minutes_per_tick
    return {"ok": True, "paused": world.paused, "minutes_per_tick": world.minutes_per_tick}


@app.post("/api/demo/reset")
async def demo_reset():
    world.reset()
    await manager.broadcast(world.to_state())
    return {"ok": True}


class TagReading(BaseModel):
    crate_id: str = C.LIVE_TAG_ID
    temp_c: float
    humidity: float = C.HUMIDITY_NORMAL
    voc_index: float = 60
    door_open: bool = False
    source: str = "slider"


@app.post("/api/tag/reading")
async def tag_reading(body: TagReading):
    mqtt_tag.put_reading(body.model_dump())
    return {"ok": True}


# ----------------------------------------------------------------------------- websocket
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)
