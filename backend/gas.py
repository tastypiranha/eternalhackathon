"""Gas (e-nose) spoilage estimation: trained model + replay of real e-nose recordings for simulated crates."""
import json
from collections import deque
from pathlib import Path

import joblib
import numpy as np

from model import CAL

BASE = Path(__file__).parent
SENSORS = CAL["gas_model"]["sensors"]
_MODEL = joblib.load(BASE / CAL["gas_model"]["path"])
_LIB = json.loads((BASE.parent / "data" / "processed" / "gas_library.json").read_text())["series"]
BASELINE_N, SMOOTH, LAG = 30, 15, 60
EMA_TAU_MIN = 30.0  # smooth the live gas estimate over ~30 min (sensor-fusion practice; raw e-nose is noisy)
MIN_READINGS = BASELINE_N


def features(gas_matrix):
    """Same features as calibration/build.py: log(smoothed / first-30 baseline) + 1-hour change. Rows = minutes."""
    g = np.asarray(gas_matrix, float)
    base = np.nanmean(g[:BASELINE_N], axis=0)
    base = np.where(np.abs(base) < 1e-6, 1e-6, base)
    kernel = np.ones(SMOOTH)
    sm = np.empty_like(g)
    for j in range(g.shape[1]):
        c = np.convolve(g[:, j], kernel)[: len(g)]
        n = np.minimum(np.arange(1, len(g) + 1), SMOOTH)
        sm[:, j] = c / n
    r = np.log(np.clip(sm / base, 1e-3, 1e3))
    sl = np.zeros_like(r)
    if len(r) > LAG:
        sl[LAG:] = r[LAG:] - r[:-LAG]
    return np.hstack([r, sl])


def predict_series(gas_matrix):
    """Gas-estimated TVC for every row (per-minute rows)."""
    if len(gas_matrix) < MIN_READINGS:
        return None
    return _MODEL.predict(features(gas_matrix))


class GasTrack:
    """Live gas stream for one simulated crate: replays a real e-nose recording matched to the crate's bacterial load,
    and keeps the running features so the model can estimate TVC from smell alone."""

    def __init__(self, rng):
        self.series = _LIB[rng.randrange(len(_LIB))]
        self.tvc = np.asarray(self.series["tvc"])
        self.gas = np.asarray(self.series["gas"], float)
        self.base = None
        self.first = []
        self.window = deque(maxlen=SMOOTH)
        self.hist = deque(maxlen=LAG + 1)
        self.last_reading = None
        self.estimate = None

    def prime(self, tvc_start, tvc_now):
        """The tag has been sniffing since packing: baseline = readings at the starting load (as in training),
        recent window/history = readings leading up to the current load. One model call."""
        first = [self.reading_for(tvc_start + (tvc_now - tvc_start) * k / 2000) for k in range(BASELINE_N)]
        b = np.mean(first, axis=0)
        self.base = np.where(np.abs(b) < 1e-6, 1e-6, b)
        self.first = first
        span = LAG + SMOOTH
        recent = [self.reading_for(tvc_start + (tvc_now - tvc_start) * (1 - (span - k) / max(span, 1) * 0.02))
                  for k in range(span)]
        for row in recent:
            self.window.append(row)
            sm = np.mean(self.window, axis=0)
            self.hist.append(np.log(np.clip(sm / self.base, 1e-3, 1e3)))
        self.last_reading = recent[-1]
        r = self.hist[-1]
        sl = r - self.hist[0] if len(self.hist) > LAG else np.zeros_like(r)
        self.estimate = float(_MODEL.predict(np.hstack([r, sl])[None, :])[0])
        return self.estimate

    def reading_for(self, tvc_true):
        i = int(np.argmin(np.abs(self.tvc - tvc_true)))
        return self.gas[i]

    def push(self, tvc_true):
        row = self.reading_for(tvc_true)
        self.last_reading = row
        if self.base is None:
            self.first.append(row)
            if len(self.first) >= BASELINE_N:
                b = np.mean(self.first, axis=0)
                self.base = np.where(np.abs(b) < 1e-6, 1e-6, b)
        self.window.append(row)
        if self.base is None:
            return None
        sm = np.mean(self.window, axis=0)
        r = np.log(np.clip(sm / self.base, 1e-3, 1e3))
        self.hist.append(r)
        sl = r - self.hist[0] if len(self.hist) > LAG else np.zeros_like(r)
        raw = float(_MODEL.predict(np.hstack([r, sl])[None, :])[0])
        a = 1.0 / EMA_TAU_MIN
        self.estimate = raw if self.estimate is None else (1 - a) * self.estimate + a * raw
        return self.estimate

    def reading_dict(self):
        if self.last_reading is None:
            return None
        return {k: round(float(v), 2) for k, v in zip(SENSORS, self.last_reading)}
