"""Alert rules (master plan 6.7)."""
from config import STATUS_ORDER


def make(world, type_, severity, message, crate_id=None, truck_id=None):
    world.counters["alert"] += 1
    alert = {
        "id": f"A-{world.counters['alert']}",
        "ts": world.ts(),
        "type": type_,
        "severity": severity,
        "crate_id": crate_id,
        "truck_id": truck_id,
        "message": message,
    }
    world.alerts.insert(0, alert)
    del world.alerts[60:]
    world.new_alerts.append(alert)
    return alert


def check_crate(world, crate):
    """Excursion and status-change alerts for one crate (called once per tick)."""
    p = crate.p
    # --- temperature excursion: 2 consecutive ticks above the limit ---
    if crate.temp_c > p["max_safe_c"]:
        crate.excursion_ticks += 1
        if crate.excursion_ticks >= 2 and not crate.in_excursion:
            crate.in_excursion = True
            if crate.truck_id:
                world.trucks[crate.truck_id].live_excursions += 1
            make(
                world, "temp_excursion", "warning",
                f"{crate.id} {p['label']} at {crate.temp_c:.1f} °C (safe ≤ {p['max_safe_c']} °C)",
                crate.id, crate.truck_id,
            )
    else:
        crate.excursion_ticks = 0
        crate.in_excursion = False

    # --- status got worse ---
    if STATUS_ORDER.index(crate.status) > STATUS_ORDER.index(crate.last_status):
        severity = "critical" if crate.status in ("critical", "spoiled") else "warning"
        make(
            world, "status_change", severity,
            f"{crate.id} status worsened: {crate.last_status} → {crate.status} ({crate.hours_left:.1f} h left)",
            crate.id, crate.truck_id,
        )
    crate.last_status = crate.status
