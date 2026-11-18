"""Freshness engine: Arrhenius relative-rate model (master plan 6.4). Pure functions."""
import math

from config import GAS_FACTOR, GAS_THRESHOLD, SPOILED_VOC

R = 8.314  # J/(mol*K)


def rate(temp_c: float, product: dict) -> float:
    """Spoilage speed relative to the product's reference temperature (1.0 at t_ref)."""
    t = min(45.0, max(-5.0, temp_c))
    T = t + 273.15
    Tref = product["t_ref_c"] + 273.15
    return math.exp((product["ea_kj_mol"] * 1000 / R) * (1 / Tref - 1 / T))


def gas_factor(voc_index: float) -> float:
    return GAS_FACTOR if voc_index >= GAS_THRESHOLD else 1.0


def step(consumed: float, temp_c: float, voc_index: float, dt_h: float, product: dict):
    """Advance one time step. Returns (new_consumed, effective_rate, extra_loss_h)."""
    r = rate(temp_c, product) * gas_factor(voc_index)
    new = min(1.0, max(0.0, consumed + dt_h * r / product["shelf_life_ref_h"]))
    extra = max(0.0, r - 1.0) * dt_h
    return new, r, extra


def status_for(score: float, voc_index: float) -> str:
    if score <= 0 or voc_index >= SPOILED_VOC:
        return "spoiled"
    if score < 15:
        return "critical"
    if score < 40:
        return "at_risk"
    if score < 70:
        return "watch"
    return "fresh"


def derived(consumed: float, effective_rate: float, voc_index: float, product: dict) -> dict:
    hours_left = (1 - consumed) * product["shelf_life_ref_h"]
    score = round(100 * (1 - consumed), 1)
    return {
        "hours_left": round(hours_left, 1),
        "hours_left_if_unchanged": round(hours_left / max(effective_rate, 1e-6), 1),
        "freshness_score": score,
        "status": status_for(score, voc_index),
    }


def voc_target(consumed: float, temp_c: float, product: dict) -> float:
    return 40 + 380 * consumed ** 2 + max(0.0, temp_c - product["max_safe_c"]) * 4
