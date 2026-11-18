"""Real cold-chain temperature traces (strawberry shipments, 10-min resolution) for trucks and crate histories."""
import json
from pathlib import Path

_DATA = json.loads((Path(__file__).parent.parent / "data" / "processed" / "temperature_traces.json").read_text())
TRACES = {t["id"]: t for t in _DATA["traces"]}
TRACE_IDS = sorted(TRACES)
STEP = 10


def temp_at(trace_id, minute):
    """Temperature at `minute` into the trace. Past the end, loops over the cold-chain part (after pre-cooling)."""
    t = TRACES[trace_id]
    temps = t["temps"]
    cold0 = t["precool_end_index"]
    n = len(temps)
    x = minute / STEP
    if x >= n - 1:
        span = (n - 1) - cold0
        x = cold0 + ((x - cold0) % span) if span > 0 else n - 1
    i = int(x)
    f = x - i
    if i >= n - 1:
        return temps[-1]
    return temps[i] * (1 - f) + temps[i + 1] * f


def cold_start_minute(trace_id):
    return TRACES[trace_id]["precool_end_index"] * STEP


def length_minutes(trace_id):
    return (len(TRACES[trace_id]["temps"]) - 1) * STEP
