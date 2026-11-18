"""FreshSense calibration pipeline: raw public datasets -> model parameters, trained models, replay traces, test cases.

Run from the repo root (needs requirements-calibration.txt):
    python -I backend/calibration/build.py

Inputs (data/raw/, git-ignored; see README "Datasets"):
  beef_enose/TS*.csv                        Wijaya et al. 2018, Mendeley mwmhh766fc  (TVC + 9 MQ sensors + temp, 5 series)
  beef_12cuts/e-nose_dataset_12_beef_cuts.xlsx  Wijaya et al. 2020, Mendeley zm5yvskf5c (TVC + 11 MQ sensors, 12 cuts)
  beef_esp32/beef_4class.csv                Mendeley n8mc3nspfn (ESP32 + MQ sensors + DHT11 + TVC)
  foodkeeper/foodkeeper.json                USDA FSIS FoodKeeper (fridge shelf life, days)
  strawberry/s1..s6.parquet                 Abdella, Brecht & Uysal 2021 strawberry cold-chain shipments (HF copy)
  zenodo_coldchain/2nd_experiment.csv       Zenodo 20540723, DHT22 in a refrigerator with door openings

Outputs:
  backend/data/calibration.json   every fitted parameter + validation metrics + provenance
  backend/models/gas_model.joblib gas sensors -> bacterial load (log CFU/g) regressor
  data/processed/*.json           replayable temperature traces, door/warm-up/cool-down profiles, gas replay library
  backend/testcases/*.json        held-out real cases: inputs + expected outputs
"""
import glob
import json
import math
import os
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

RAW = "data/raw"
OUT_CAL = "backend/data/calibration.json"
OUT_MODEL = "backend/models/gas_model.joblib"
OUT_PROC = "data/processed"
OUT_CASES = "backend/testcases"

# The only literature constant (chosen by the team): minimum growth temperature of
# psychrotrophic spoilage bacteria (Pseudomonas spp.) in the Ratkowsky square-root model.
LITERATURE = {
    "ratkowsky_tmin_c": -8.0,
    "source": "Ratkowsky square-root model; Tmin ~ -8 °C for meat spoilage Pseudomonas (predictive microbiology literature)",
}
REFERENCE_TEMP_C = 4.4  # USDA 'danger zone' starts above 40 °F; also FoodKeeper's fridge reference
GAS_SENSORS = ["MQ2", "MQ3", "MQ4", "MQ5", "MQ135", "MQ136"]  # sensors present in all three beef datasets
HOLDOUT = {"TS5", "6.Striploin", "11.Shin"}  # never used for fitting; become the test cases

# FoodKeeper entries used per product (exact names in the file)
FOODKEEPER_ENTRIES = {
    "beef": "Beef (steaks)",
    "chicken": "Chicken (whole)",
    "dairy": "Yogurt",
    "greens": "Bagged greens (leaf, spinach, lettuce, etc.)",
    "strawberries": "Strawberries",
}
PRODUCT_META = {
    "beef": {"label": "Beef", "emoji": "🥩", "weight_kg": 20, "gas_model": True, "simulate": False},
    "chicken": {"label": "Chicken", "emoji": "🍗", "weight_kg": 20, "gas_model": True, "simulate": True},
    "dairy": {"label": "Dairy (curd/yogurt)", "emoji": "🥛", "weight_kg": 24, "gas_model": False, "simulate": True},
    "greens": {"label": "Leafy greens", "emoji": "🥬", "weight_kg": 10, "gas_model": False, "simulate": True},
    "strawberries": {"label": "Strawberries", "emoji": "🍓", "weight_kg": 8, "gas_model": False, "simulate": True},
}


# ----------------------------------------------------------------------------- loading
def load_beef_series():
    out = []
    for f in sorted(glob.glob(f"{RAW}/beef_enose/TS*.csv")):
        d = pd.read_csv(f)
        out.append({"name": os.path.basename(f)[:-4], "source": "Wijaya 2018 (mwmhh766fc)",
                    "minutes": d.minute.to_numpy(float), "tvc": d.TVC.to_numpy(float),
                    "temp": d.Temperature.to_numpy(float), "gas": d[GAS_SENSORS].to_numpy(float),
                    "label": d["class"].astype(str).to_numpy()})
    x = pd.ExcelFile(f"{RAW}/beef_12cuts/e-nose_dataset_12_beef_cuts.xlsx")
    names = {1: "excellent", 2: "good", 3: "acceptable", 4: "spoiled"}
    for s in x.sheet_names:
        d = pd.read_excel(x, s)
        out.append({"name": s, "source": "Wijaya 2020 (zm5yvskf5c)",
                    "minutes": d.Minute.to_numpy(float), "tvc": d.TVC.to_numpy(float), "temp": None,
                    "gas": d[GAS_SENSORS].to_numpy(float), "label": d.Label.map(names).to_numpy()})
    b = pd.read_csv(f"{RAW}/beef_esp32/beef_4class.csv")
    b.columns = [c.strip() for c in b.columns]
    b = b.groupby("minutes").mean(numeric_only=True).reset_index()
    out.append({"name": "esp32", "source": "ESP32 e-nose 2025 (n8mc3nspfn)",
                "minutes": b.minutes.to_numpy(float), "tvc": b.tvc.to_numpy(float),
                "temp": b.Temperature.to_numpy(float),
                "gas": b[["Mq-2", "Mq-3", "Mq-4", "Mq-5", "Mq-135", "Mq-136"]].to_numpy(float),
                "label": b["class"].round().astype(int).map(names).to_numpy()})
    return out


# ----------------------------------------------------------------------------- gas features
def gas_features(gas, baseline_n=30, smooth=15, slope_lag=60):
    """Drift-robust features: log ratio of smoothed reading to the crate's own first readings, plus 1-hour change."""
    gas = np.asarray(gas, float)
    base = np.nanmean(gas[:baseline_n], axis=0)
    base = np.where(np.abs(base) < 1e-6, 1e-6, base)
    sm = pd.DataFrame(gas).rolling(smooth, min_periods=1).mean().to_numpy()
    r = np.log(np.clip(sm / base, 1e-3, 1e3))
    sl = np.zeros_like(r)
    if len(r) > slope_lag:
        sl[slope_lag:] = r[slope_lag:] - r[:-slope_lag]
    return np.hstack([r, sl])


# ----------------------------------------------------------------------------- kinetics
def growth_slope(minutes, tvc, spoil=None):
    """Effective growth rate (log CFU/g per hour) from the start until the curve crosses `spoil` (a stage threshold).
    Real curves are S-shaped; a straight line through the plateau would underestimate the rate."""
    if spoil is not None:
        hit = np.where(tvc >= spoil)[0]
        if len(hit) and minutes[hit[0]] > minutes[0]:
            return float((tvc[hit[0]] - tvc[0]) / ((minutes[hit[0]] - minutes[0]) / 60.0))
    return float(np.polyfit(minutes / 60.0, tvc, 1)[0])


def kinetic_path(tvc0, minutes, temp, b, tmin):
    """Integrate Ratkowsky growth over a measured temperature history."""
    out = np.empty(len(minutes))
    v = tvc0
    out[0] = v
    for i in range(1, len(minutes)):
        dt_h = (minutes[i] - minutes[i - 1]) / 60.0
        mu = (b * max(0.0, temp[i] - tmin)) ** 2
        v += mu * dt_h
        out[i] = v
    return out


def stage_of(tvc, thr):
    return int(np.digitize([tvc], thr)[0])


def main():
    os.makedirs(OUT_PROC, exist_ok=True)
    os.makedirs(OUT_CASES, exist_ok=True)
    os.makedirs(os.path.dirname(OUT_MODEL), exist_ok=True)
    tmin = LITERATURE["ratkowsky_tmin_c"]
    series = load_beef_series()
    train = [s for s in series if s["name"] not in HOLDOUT]
    hold = [s for s in series if s["name"] in HOLDOUT]
    print(f"beef series: {len(series)} ({len(train)} train, {len(hold)} held out)")

    # ---- 1. stage thresholds from labelled data (median of each stage's minimum TVC) ----
    stage_names = ["excellent", "good", "acceptable", "spoiled"]
    mins = {k: [] for k in stage_names[1:]}
    for s in train:
        if s["source"].startswith("Wijaya 2018"):
            continue  # TS labels overlap (acceptable/spoiled share TVC) -> use the cleaner datasets
        for k in mins:
            sel = s["tvc"][s["label"] == k]
            if len(sel):
                mins[k].append(float(sel.min()))
    thresholds = [round(float(np.median(mins[k])), 2) for k in stage_names[1:]]
    spoil = thresholds[2]
    tvc0_all = [float(s["tvc"][0]) for s in train]
    tvc0 = round(float(np.median(tvc0_all)), 2)
    print("stage thresholds", thresholds, "initial TVC median", tvc0)

    # ---- 2. Ratkowsky b for beef from series with measured temperature ----
    temp_series = [s for s in train if s["temp"] is not None]
    pts = []
    for s in temp_series:
        mu = growth_slope(s["minutes"], s["tvc"], thresholds[1])
        T = float(np.mean(s["temp"]))
        pts.append({"series": s["name"], "mean_temp_c": round(T, 1), "growth_log_per_h": round(mu, 4),
                    "b": math.sqrt(mu) / (T - tmin)})
    b_beef = float(np.median([p["b"] for p in pts]))
    print("Ratkowsky b(beef)", round(b_beef, 5), "from", [(p["series"], p["mean_temp_c"], p["growth_log_per_h"]) for p in pts])

    # ---- 3. kinetic validation: leave-one-series-out over temp series ----
    kin_err = []
    kin_by = {}
    for s in temp_series:
        others = [p["b"] for p in pts if p["series"] != s["name"]]
        b_ = float(np.median(others))
        pred = kinetic_path(s["tvc"][0], s["minutes"], s["temp"], b_, tmin)
        e = np.abs(pred - s["tvc"])
        kin_err.append(e)
        kin_by[s["name"]] = round(float(e.mean()), 3)
    kin_mae = float(np.concatenate(kin_err).mean())
    print("kinetic LOSO MAE", round(kin_mae, 3), kin_by)

    # ---- 4. gas model: leave-one-series-out, then final fit ----
    feats = {s["name"]: gas_features(s["gas"]) for s in series}
    gas_by, gas_err, yt_all, yp_all = {}, [], [], []
    for s in train:
        tr = [o for o in train if o["name"] != s["name"]]
        X = np.vstack([feats[o["name"]] for o in tr])[::3]
        y = np.concatenate([o["tvc"] for o in tr])[::3]
        m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=0).fit(X, y)
        p = m.predict(feats[s["name"]])
        gas_by[s["name"]] = round(float(np.abs(p - s["tvc"]).mean()), 3)
        gas_err.append(np.abs(p - s["tvc"]))
        yt_all.append(s["tvc"])
        yp_all.append(p)
    gas_mae = float(np.concatenate(gas_err).mean())
    yt_all, yp_all = np.concatenate(yt_all), np.concatenate(yp_all)
    st = lambda v: np.digitize(v, thresholds)
    gas_metrics = {
        "mae_log_cfu": round(gas_mae, 3),
        "stage_accuracy": round(float((st(yt_all) == st(yp_all)).mean()), 3),
        "within_one_stage": round(float((np.abs(st(yt_all) - st(yp_all)) <= 1).mean()), 3),
        "spoiled_detection_accuracy": round(float(((yt_all >= spoil) == (yp_all >= spoil)).mean()), 3),
        "per_series_mae": gas_by,
    }
    print("gas LOSO", {k: v for k, v in gas_metrics.items() if k != "per_series_mae"})
    X = np.vstack([feats[o["name"]] for o in train])[::2]
    y = np.concatenate([o["tvc"] for o in train])[::2]
    gas_model = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=0).fit(X, y)
    joblib.dump(gas_model, OUT_MODEL)

    # ---- 5. fusion weight (inverse variance from LOSO errors) + fused validation on temp series ----
    var_k = float(np.mean(np.concatenate(kin_err) ** 2))
    var_g = float(np.mean(np.concatenate([gas_err[i] for i, s in enumerate(train) if s["temp"] is not None]) ** 2))
    w_kin = var_g / (var_k + var_g)
    fused_err = []
    for s in temp_series:
        others = [p["b"] for p in pts if p["series"] != s["name"]]
        kin = kinetic_path(s["tvc"][0], s["minutes"], s["temp"], float(np.median(others)), tmin)
        tr = [o for o in train if o["name"] != s["name"]]
        m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=0).fit(
            np.vstack([feats[o["name"]] for o in tr])[::3], np.concatenate([o["tvc"] for o in tr])[::3])
        g = m.predict(feats[s["name"]])
        fused_err.append(np.abs(w_kin * kin + (1 - w_kin) * g - s["tvc"]))
    fused_mae = float(np.concatenate(fused_err).mean())
    print("fusion w_kin", round(w_kin, 3), "fused MAE", round(fused_mae, 3), "(kinetic", round(kin_mae, 3), ")")

    # ---- 6. held-out test set metrics (never seen by any fit) ----
    hold_metrics = {}
    plot_series = None
    for s in hold:
        g = gas_model.predict(feats[s["name"]])
        pre = s["tvc"] < spoil  # the region that drives decisions: before the crate is spoiled
        row = {"gas_mae_log_cfu": round(float(np.abs(g - s["tvc"]).mean()), 3),
               "gas_mae_before_spoilage": round(float(np.abs(g - s["tvc"])[pre].mean()), 3)}
        temp = s["temp"] if s["temp"] is not None else np.full(len(s["minutes"]), np.mean([np.mean(o["temp"]) for o in temp_series]))
        kin = kinetic_path(s["tvc"][0], s["minutes"], temp, b_beef, tmin)
        fused = w_kin * kin + (1 - w_kin) * g
        row["temperature"] = "measured" if s["temp"] is not None else "not recorded: room temperature of the other experiments"
        row["kinetic_mae_log_cfu"] = round(float(np.abs(kin - s["tvc"]).mean()), 3)
        row["kinetic_mae_before_spoilage"] = round(float(np.abs(kin - s["tvc"])[pre].mean()), 3)
        row["fused_mae_log_cfu"] = round(float(np.abs(fused - s["tvc"]).mean()), 3)
        row["fused_mae_before_spoilage"] = round(float(np.abs(fused - s["tvc"])[pre].mean()), 3)
        hold_metrics[s["name"]] = row
        if s["name"] == "TS5":
            plot_series = (s, kin, g, fused)
    print("held-out", hold_metrics)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        os.makedirs("frontend/public/model", exist_ok=True)
        s, kin, g, fused = plot_series
        h = s["minutes"] / 60
        plt.figure(figsize=(8, 4))
        plt.plot(h, s["tvc"], "k-", lw=2.5, label="Actual (lab count)")
        plt.plot(h, kin, "--", color="#2563EB", label="Temperature model only")
        plt.plot(h, g, ":", color="#0D9488", label="Gas sensors only")
        plt.plot(h, fused, "-", color="#E23744", lw=2, label="FreshSense (fused)")
        for th, name in zip(thresholds, ["good", "acceptable", "spoiled"]):
            plt.axhline(th, color="#9CA3AF", lw=0.8, ls="--")
            plt.text(0.3, th + 0.05, name, fontsize=8, color="#6B7280")
        plt.xlabel("Hours"); plt.ylabel("Bacterial load (log CFU/g)")
        plt.title("Held-out beef series TS5 (never used for fitting)")
        plt.ylim(1.5, 7.5); plt.legend(fontsize=8, loc="upper left"); plt.tight_layout()
        plt.savefig("frontend/public/model/holdout_ts5.png", dpi=150); plt.close()
        temps_c = np.linspace(-1, 30, 63)
        plt.figure(figsize=(8, 4))
        for pid in ["chicken", "dairy", "greens", "strawberries", "beef"]:
            entry = FOODKEEPER_ENTRIES[pid]
            mid = float(np.mean({r["name"]: r for r in json.load(open(f"{RAW}/foodkeeper/foodkeeper.json"))}[entry]["fridge"]))
            beef_mid = 4.0
            b_p = b_beef * math.sqrt(beef_mid / mid)
            life = [(spoil - tvc0) / ((b_p * (t - tmin)) ** 2) / 24 for t in temps_c]
            plt.plot(temps_c, life, label=PRODUCT_META[pid]["label"])
        plt.yscale("log"); plt.axvline(REFERENCE_TEMP_C, color="#9CA3AF", ls="--")
        plt.xlabel("Storage temperature (°C)"); plt.ylabel("Shelf life from fresh (days, log scale)")
        plt.title("Calibrated shelf life vs temperature"); plt.legend(fontsize=8); plt.tight_layout()
        plt.savefig("frontend/public/model/shelf_life_vs_temp.png", dpi=150); plt.close()
    except Exception as e:  # plotting is optional
        print("plot skipped:", e)

    # ---- 7. FoodKeeper -> per-product growth constants (relative perishability vs beef) ----
    fk = {r["name"]: r for r in json.load(open(f"{RAW}/foodkeeper/foodkeeper.json"))}
    products = {}
    beef_fk = float(np.mean(fk[FOODKEEPER_ENTRIES["beef"]]["fridge"]))
    for pid, entry in FOODKEEPER_ENTRIES.items():
        days = fk[entry]["fridge"]
        mid = float(np.mean(days))
        b_p = b_beef * math.sqrt(beef_fk / mid)
        mu_ref = (b_p * (REFERENCE_TEMP_C - tmin)) ** 2
        products[pid] = {
            "id": pid, **PRODUCT_META[pid],
            "ratkowsky_b": round(b_p, 6),
            "foodkeeper_entry": entry, "foodkeeper_fridge_days": days,
            "model_shelf_life_days_at_ref": round((spoil - tvc0) / mu_ref / 24, 1),
            "max_safe_c": REFERENCE_TEMP_C,
            "t_ref_c": REFERENCE_TEMP_C,
        }
    print({k: (v["foodkeeper_fridge_days"], v["model_shelf_life_days_at_ref"]) for k, v in products.items()})

    # ---- 8. temperature traces + event profiles (real data) ----
    traces, warm, cool = [], [], []
    pts9 = ["Front_Top", "Front_Middle", "Front_Bottom", "Middle_Top", "Middle_Middle", "Middle_Bottom",
            "Rear_Top", "Rear_Middle", "Rear_Bottom"]
    for i in range(1, 7):
        s = pd.read_parquet(f"{RAW}/strawberry/s{i}.parquet")
        for p in pts9:
            t = s[p].astype(float)
            if t.notna().mean() < 0.4:
                continue
            t = t.interpolate(limit=6)
            arr = t.to_numpy()
            ok = ~np.isnan(arr)
            if ok.sum() < 300:
                continue
            first = int(np.argmax(ok))
            arr = arr[first:]
            cold = np.where(arr < 5.0)[0]
            if len(cold) == 0:
                continue
            c0 = int(cold[0])
            # end of cold chain: first time after c0 the 2-hour mean exceeds 8 °C
            roll = pd.Series(arr).rolling(12, min_periods=6).mean().to_numpy()
            after = np.where((np.arange(len(arr)) > c0 + 36) & (roll > 8.0))[0]
            c1 = int(after[0]) if len(after) else len(arr)
            seg = arr[: c1]
            if np.isnan(seg).mean() > 0.1 or c1 - c0 < 144:  # need >= 24 h of cold chain
                continue
            seg = pd.Series(seg).interpolate().bfill().ffill().to_numpy()
            traces.append({"id": f"S{i}-{p}", "shipment": f"S{i}", "point": p, "step_min": 10,
                           "precool_end_index": c0, "temps": [round(float(v), 1) for v in seg]})
            # cool-down profile (harvest heat -> cold), normalised 1 -> 0
            pre = arr[: c0 + 1]
            if len(pre) >= 3 and pre[0] - pre[-1] > 5:
                cool.append((pre - pre[-1]) / (pre[0] - pre[-1]))
            # warm-up profile after refrigeration ends: delta from start, 8 h
            if len(after):
                w0 = max(c1 - 6, 0)
                wseg = arr[w0: w0 + 48]
                if len(wseg) == 48 and not np.isnan(wseg).any():
                    warm.append(wseg - wseg[0])
    def avg_profile(profiles, n):
        m = np.full((len(profiles), n), np.nan)
        for k, p in enumerate(profiles):
            m[k, : min(n, len(p))] = p[:n]
        return [round(float(v), 3) for v in np.nanmean(m, axis=0)]
    warm_profile = avg_profile(warm, 48)
    cool_profile = avg_profile(cool, max(len(c) for c in cool))
    print(f"traces: {len(traces)}, warm-up profiles: {len(warm)}, cool-down profiles: {len(cool)}")

    z = pd.read_csv(f"{RAW}/zenodo_coldchain/2nd_experiment.csv", header=None, names=["i", "temp", "hum"])
    zt = z.temp.to_numpy(float)
    jump = int(np.argmax(np.diff(pd.Series(zt).rolling(20, min_periods=1).mean().to_numpy()) * (np.arange(len(zt) - 1) > 50)))
    start = max(0, jump - 20)
    base_t = float(np.median(zt[max(0, start - 200): start]))
    # sample index step is 3 s (column i increments by 3); resample to minutes for 90 min
    sec = (z.i.to_numpy(float) - z.i.iloc[start])
    door = []
    for minute in range(0, 91):
        idx = int(np.argmin(np.abs(sec - minute * 60)))
        door.append(round(float(zt[idx] - base_t), 2))
    door_rh = round(float(z.hum.iloc[jump: jump + 200].mean() - z.hum.iloc[max(0, start - 200): start].mean()), 1)
    fridge_rh = round(float(z.hum.iloc[max(0, start - 200): start].median()), 1)
    print("door profile peak +", max(door), "°C; humidity change", door_rh)

    profiles = {
        "warm_up_delta_c": {"step_min": 10, "values": warm_profile,
                            "source": "strawberry shipments: temperature rise after refrigeration stops (mean of %d)" % len(warm)},
        "cool_down_fraction": {"step_min": 10, "values": cool_profile,
                               "source": "strawberry shipments: pre-cooling from harvest heat (mean of %d)" % len(cool)},
        "door_open_delta_c": {"step_min": 1, "values": door, "humidity_delta": door_rh,
                              "source": "Zenodo 20540723 2nd_experiment: refrigerator door opening"},
        "fridge_humidity_pct": {"value": fridge_rh, "source": "Zenodo 20540723 2nd_experiment: refrigerator humidity before door opening"},
        "ambient_c": {"value": round(float(np.mean([np.mean(s["temp"]) for s in temp_series])), 1),
                      "source": "mean room temperature of the beef spoilage experiments"},
    }
    json.dump({"traces": traces}, open(f"{OUT_PROC}/temperature_traces.json", "w"))
    json.dump(profiles, open(f"{OUT_PROC}/event_profiles.json", "w"), indent=1)

    # ---- 9. gas replay library (train series only, every 5 min) ----
    lib = []
    for s in train:
        if s["name"] == "esp32":
            continue
        idx = np.arange(0, len(s["minutes"]), 5)
        lib.append({"series": s["name"], "minutes": s["minutes"][idx].round().astype(int).tolist(),
                    "tvc": s["tvc"][idx].round(3).tolist(), "gas": s["gas"][idx].round(2).tolist()})
    json.dump({"sensors": GAS_SENSORS, "series": lib}, open(f"{OUT_PROC}/gas_library.json", "w"))

    # ---- 10. test cases from held-out series ----
    cases = []
    for s in hold:
        for cut_h in (6, 15, 24, 30):
            cut = int(np.searchsorted(s["minutes"], cut_h * 60))
            if cut >= len(s["minutes"]) - 1:
                continue
            step = 5
            idx = np.arange(0, cut + 1, step)
            readings = []
            for j in idx:
                r = {"minute": int(s["minutes"][j]), "gas": {k: round(float(v), 2) for k, v in zip(GAS_SENSORS, s["gas"][j])}}
                r["temp_c"] = round(float(s["temp"][j]), 1) if s["temp"] is not None else None
                readings.append(r)
            actual = float(s["tvc"][cut])
            reach = np.where(s["tvc"] >= spoil)[0]
            hours_to_spoil = None
            if len(reach):
                hours_to_spoil = round(max(0.0, (s["minutes"][reach[0]] - s["minutes"][cut]) / 60.0), 1)
            cases.append({
                "id": f"{s['name']}_t{cut_h}h".replace(".", "_"),
                "description": f"Held-out beef series {s['name']} ({s['source']}), first {cut_h} h of readings",
                "input": {"product": "beef", "initial_tvc": None, "readings": readings,
                          "note": "temp_c is null for the 12-cuts dataset (room temperature not recorded); the API then uses the room temperature of the other experiments"},
                "expected": {"tvc_log_cfu": round(actual, 2), "stage": stage_names[stage_of(actual, thresholds)],
                             "hours_until_spoiled_at_same_conditions": hours_to_spoil,
                             "tolerance": {"tvc_log_cfu": 0.6, "stage": "same or neighbouring"}},
            })
    for c in cases:
        json.dump(c, open(f"{OUT_CASES}/{c['id']}.json", "w"), indent=1)
    print("test cases:", len(cases))

    cal = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "literature": LITERATURE,
        "reference_temp_c": REFERENCE_TEMP_C,
        "stage_names": stage_names,
        "stage_thresholds_log_cfu": thresholds,
        "spoilage_threshold_log_cfu": spoil,
        "max_tvc_observed_log_cfu": round(float(max(s["tvc"].max() for s in series)), 2),
        "initial_tvc_log_cfu": {"median": tvc0, "values": [round(v, 2) for v in tvc0_all]},
        "beef_growth_points": pts,
        "ratkowsky_b_beef": round(b_beef, 6),
        "products": products,
        "gas_model": {"path": "models/gas_model.joblib", "sensors": GAS_SENSORS,
                      "features": "log(smoothed/first-30-readings) per sensor + 1-hour change",
                      "loso": gas_metrics},
        "kinetic_model": {"loso_mae_log_cfu": round(kin_mae, 3), "per_series_mae": kin_by},
        "fusion": {"weight_kinetic": round(w_kin, 3), "weight_gas": round(1 - w_kin, 3),
                   "fused_loso_mae_log_cfu": round(fused_mae, 3)},
        "holdout": hold_metrics,
        "datasets": {
            "wijaya2018": "https://data.mendeley.com/datasets/mwmhh766fc",
            "wijaya2020_12cuts": "https://data.mendeley.com/datasets/zm5yvskf5c",
            "esp32_2025": "https://data.mendeley.com/datasets/n8mc3nspfn",
            "foodkeeper": "https://catalog.data.gov/dataset/fsis-foodkeeper-data",
            "strawberry_shipments": "https://huggingface.co/datasets/NifferLi/cold-chain-strawberry-sensors (Abdella et al. 2021)",
            "zenodo_coldchain": "https://zenodo.org/records/20540723",
        },
    }
    json.dump(cal, open(OUT_CAL, "w"), indent=1, ensure_ascii=False)
    print("wrote", OUT_CAL)


if __name__ == "__main__":
    main()
