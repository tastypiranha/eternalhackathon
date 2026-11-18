"""Analytics endpoint data (master plan 6.9 Analytics object)."""
import db
import model as M
from config import STAGE_LABELS, load_optional


def build(world):
    trucks = sorted(
        (
            {
                "truck_id": t.id,
                "name": t.name,
                "driver": t.driver,
                "extra_loss_h": round(t.past_week_extra_loss_h + t.live_extra_loss_h, 1),
                "excursions": t.past_week_excursions + t.live_excursions,
            }
            for t in world.trucks.values()
        ),
        key=lambda x: x["extra_loss_h"],
        reverse=True,
    )
    by_stage = db.extra_loss_by_stage()
    stages = sorted(
        (
            {"stage": s, "label": STAGE_LABELS.get(s, s), "extra_loss_h": round(v, 1)}
            for s, v in by_stage.items()
        ),
        key=lambda x: x["extra_loss_h"],
        reverse=True,
    )
    return {
        "hours_lost_by_truck": trucks,
        "hours_lost_by_stage": stages,
        "impact": dict(world.impact),
        "benchmark": load_optional("benchmark_results.json"),
        "model_card": model_card(),
    }


def model_card():
    """Summary of the data-calibrated model for the dashboard (from calibration.json)."""
    c = M.CAL
    g = c["gas_model"]["loso"]
    return {
        "available": True,
        "thresholds_log_cfu": c["stage_thresholds_log_cfu"],
        "stage_names": c["stage_names"],
        "ratkowsky_b_beef": c["ratkowsky_b_beef"],
        "tmin_c": c["literature"]["ratkowsky_tmin_c"],
        "growth_points": c["beef_growth_points"],
        "kinetic_loso_mae": c["kinetic_model"]["loso_mae_log_cfu"],
        "gas_loso_mae": g["mae_log_cfu"],
        "gas_stage_accuracy": g["stage_accuracy"],
        "gas_within_one_stage": g["within_one_stage"],
        "gas_spoiled_detection": g["spoiled_detection_accuracy"],
        "fusion": c["fusion"],
        "holdout": c["holdout"],
        "products": {k: {"label": v["label"], "foodkeeper_entry": v["foodkeeper_entry"],
                         "foodkeeper_fridge_days": v["foodkeeper_fridge_days"],
                         "model_shelf_life_days_at_ref": v["model_shelf_life_days_at_ref"]}
                     for k, v in c["products"].items()},
        "reference_temp_c": c["reference_temp_c"],
        "datasets": c["datasets"],
        "images": ["/model/holdout_ts5.png", "/model/shelf_life_vs_temp.png"],
    }
