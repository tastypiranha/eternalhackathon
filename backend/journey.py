"""Journey report builder (master plan 6.9 Journey object). Life is measured in hours at the reference temperature."""
import db
import model as M
from config import STAGE_LABELS

MAX_POINTS = 400


def _find(world, crate_id):
    return world.crates.get(crate_id) or world.archive.get(crate_id)


def build(world, crate_id):
    crate = _find(world, crate_id)
    if crate is None:
        return None
    p = crate.p
    mu_ref = M.mu(M.REF_T, crate.product)
    sl = (M.SPOIL - crate.initial_tvc) / mu_ref  # total life in hours at the reference temperature
    limit = p["max_safe_c"]
    rows = db.get_readings(crate_id)

    # ---- stage blocks (consecutive readings with the same stage + truck) ----
    blocks = []
    prev_tvc = crate.initial_tvc
    for r in rows:
        key = (r["stage"], r["truck_id"])
        if not blocks or blocks[-1]["key"] != key:
            blocks.append({"key": key, "rows": [], "tvc_before": prev_tvc})
        blocks[-1]["rows"].append(r)
        prev_tvc = r["tvc"]

    stages = []
    for b in blocks:
        rs = b["rows"]
        temps = [r["temp_c"] for r in rs]
        mins = sum(r["minutes"] for r in rs)
        start_ts = rs[0]["ts"]
        stages.append({
            "stage": rs[0]["stage"],
            "label": STAGE_LABELS.get(rs[0]["stage"], rs[0]["stage"]),
            "location_name": rs[0]["location_name"],
            "start": start_ts,
            "end": rs[-1]["ts"],
            "duration_min": round(mins),
            "avg_temp_c": round(sum(temps) / len(temps), 1),
            "min_temp_c": round(min(temps), 1),
            "max_temp_c": round(max(temps), 1),
            "avg_humidity": round(sum(r["humidity"] for r in rs) / len(rs), 1),
            "minutes_above_limit": round(sum(r["minutes"] for r in rs if r["temp_c"] > limit)),
            "life_used_h": round((rs[-1]["tvc"] - b["tvc_before"]) / mu_ref, 1),
            "extra_loss_h": round(sum(r["extra_loss_h"] for r in rs), 1),
        })

    # ---- excursions ----
    excursions, cur = [], None
    for r in rows:
        if r["temp_c"] > limit:
            if cur is None:
                cur = {"start": r["ts"], "end": r["ts"], "minutes": 0.0, "peak_temp_c": r["temp_c"], "stage": r["stage"]}
            cur["end"] = r["ts"]
            cur["minutes"] += r["minutes"]
            cur["peak_temp_c"] = max(cur["peak_temp_c"], r["temp_c"])
        elif cur is not None:
            excursions.append(cur)
            cur = None
    if cur is not None:
        excursions.append(cur)
    for e in excursions:
        e["minutes"] = round(e["minutes"])
        e["peak_temp_c"] = round(e["peak_temp_c"], 1)

    # ---- blame ----
    total_extra = sum(s["extra_loss_h"] for s in stages)
    if stages and total_extra > 0.05:
        worst = max(stages, key=lambda s: s["extra_loss_h"])
        share = round(100 * worst["extra_loss_h"] / total_extra)
        blame = {
            "stage": worst["stage"],
            "share_pct": share,
            "text": f"{share}% of the extra freshness loss happened at {worst['label']} ({worst['location_name']}).",
        }
    else:
        blame = {"stage": None, "share_pct": 0, "text": "No significant temperature abuse recorded."}

    # ---- downsample readings ----
    k = max(1, -(-len(rows) // MAX_POINTS))
    picked = rows[::k]
    if rows and picked[-1] is not rows[-1]:
        picked.append(rows[-1])
    readings = [
        {"ts": r["ts"], "temp_c": round(r["temp_c"], 1), "humidity": round(r["humidity"], 1),
         "voc_index": None if r["voc_index"] is None else round(r["voc_index"]),
         "tvc": round(r["tvc"], 3), "freshness_score": r["freshness_score"], "stage": r["stage"]}
        for r in picked
    ]

    crate_d = world.crate_dict(crate)
    crate_d["delivered"] = crate.delivered
    crate_d["delivered_to"] = crate.delivered_to
    crate_d["discarded"] = crate.discarded
    return {
        "crate": crate_d,
        "product": {"id": p["id"], "label": p["label"], "t_ref_c": p["t_ref_c"],
                    "max_safe_c": p["max_safe_c"], "shelf_life_ref_h": round(sl, 1),
                    "foodkeeper_entry": p["foodkeeper_entry"], "foodkeeper_fridge_days": p["foodkeeper_fridge_days"]},
        "summary": {
            "picked_up_at": rows[0]["ts"] if rows else crate.loaded_at,
            "total_life_h": round(sl, 1),
            "life_used_h": round((crate.tvc - crate.initial_tvc) / mu_ref, 1),
            "tvc": round(crate.tvc, 2), "initial_tvc": round(crate.initial_tvc, 2),
            "tvc_kinetic": round(crate.tvc_kin, 2), "tvc_gas": None if crate.tvc_gas is None else round(crate.tvc_gas, 2),
            "quality_stage": crate.stage_name,
            "extra_loss_h": round(total_extra, 1),
            "hours_left": crate.hours_left,
            "freshness_score": crate.freshness_score,
            "status": crate.status,
        },
        "thresholds_log_cfu": M.THRESHOLDS,
        "stage_names": M.STAGES,
        "stages": stages,
        "readings": readings,
        "excursions": excursions,
        "blame": blame,
    }
