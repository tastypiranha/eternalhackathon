"""Analytics endpoint data (master plan 6.9 Analytics object)."""
import db
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
        "model_card": load_optional("model1_results.json"),
    }
