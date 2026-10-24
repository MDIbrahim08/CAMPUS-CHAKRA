"""Short-horizon (6h and 12h ahead) building-level demand forecasting.

One GLOBAL model per (meter, horizon) shared across all buildings, with
building metadata as features. This is the key scaling decision: adding
building #31 needs no new model, only its metadata row.

Models compared on a strict time-based hold-out (last 21 days):
  * seasonal-naive (same hour yesterday)      – zero compute baseline
  * Ridge regression on lag/calendar features – ~KB, microseconds
  * LightGBM (shallow, 200 trees)             – ~100s of KB, sub-ms per building
"""
from __future__ import annotations

import pickle
import time

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

HORIZONS = [6, 12]
TARGETS = ["electricity_kwh", "water_litres"]
DAYTYPE_CODE = {"working": 0, "weekend": 1, "semester_break": 2, "exam": 3, "holiday": 4}


def calendar_features(calendar: pd.DataFrame) -> pd.DataFrame:
    cal = calendar.copy()
    cal["date"] = pd.to_datetime(cal["date"]).dt.normalize()
    cal["day_type_code"] = cal["day_type"].map(DAYTYPE_CODE).fillna(0).astype(int)
    ev = cal["event"].fillna("").str.lower()
    cal["has_event"] = (ev != "").astype(int)
    cal["big_event"] = ev.str.contains("hackathon|alumni|fest|placement|feast|expo|exam|24x7|check-in").astype(int)
    return cal[["date", "day_type_code", "has_event", "big_event", "avg_temp_c", "rainfall_mm", "humidity_pct"]]


def build_frame(hourly: pd.DataFrame, calendar: pd.DataFrame, buildings: pd.DataFrame, target: str, h: int) -> pd.DataFrame:
    """Rows = (building, issue time t). Label = target at t+h. Features use only info known at t
    (plus the calendar/weather plan for the target day, which is known in advance)."""
    cal = calendar_features(calendar)
    btype = buildings.set_index("building_id")["building_type"].astype("category").cat.codes
    cap = buildings.set_index("building_id")["design_capacity"]
    frames = []
    for b, g in hourly.groupby("building_id"):
        g = g.sort_values("ts").set_index("ts")
        y = g[target]
        f = pd.DataFrame(index=g.index)
        f["building_code"] = int(b[1:])
        f["btype"] = btype.get(b, 0)
        f["capacity"] = cap.get(b, 0)
        f["y_t"] = y
        f["y_t1"] = y.shift(1)
        f["y_t2"] = y.shift(2)
        f["roll6"] = y.rolling(6).mean()
        f["roll24"] = y.rolling(24).mean()
        f["foot_t"] = g["footfall"]
        # same target-hour yesterday and last week (known at t since h <= 24)
        f["y_tgt_m24"] = y.shift(24 - h)
        f["y_tgt_m168"] = y.shift(168 - h)
        tgt_time = f.index + pd.Timedelta(hours=h)
        f["tgt_hour"] = tgt_time.hour
        f["tgt_dow"] = tgt_time.dayofweek
        f["tgt_date"] = tgt_time.normalize()
        f["label"] = y.shift(-h)
        f["building_id"] = b
        f["target_time"] = tgt_time
        frames.append(f.reset_index())
    df = pd.concat(frames, ignore_index=True)
    df = df.merge(cal, left_on="tgt_date", right_on="date", how="left").drop(columns=["date"])
    return df


FEATS = ["building_code", "btype", "capacity", "y_t", "y_t1", "y_t2", "roll6", "roll24", "foot_t",
         "y_tgt_m24", "y_tgt_m168", "tgt_hour", "tgt_dow", "day_type_code", "has_event", "big_event",
         "avg_temp_c", "rainfall_mm", "humidity_pct"]


def _wmape(y, p):
    return float(np.sum(np.abs(y - p)) / max(np.sum(np.abs(y)), 1e-9) * 100)


def _spike_scores(df, pred, thr_map):
    thr = df["building_id"].map(thr_map).values
    actual = df["label"].values > thr
    predicted = pred > thr
    tp = int((actual & predicted).sum()); fp = int((~actual & predicted).sum()); fn = int((actual & ~predicted).sum())
    prec = tp / max(tp + fp, 1); rec = tp / max(tp + fn, 1)
    return {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(2 * prec * rec / max(prec + rec, 1e-9), 3)}


def train_and_evaluate(hourly, calendar, buildings, holdout_days=21):
    """Train all (target, horizon) models, return (models, metrics)."""
    models, metrics = {}, []
    cutoff = hourly["ts"].max() - pd.Timedelta(days=holdout_days)
    for target in TARGETS:
        # spike threshold: building's 90th percentile in the training window
        thr_map = hourly[hourly["ts"] <= cutoff].groupby("building_id")[target].quantile(0.90).to_dict()
        for h in HORIZONS:
            df = build_frame(hourly, calendar, buildings, target, h).dropna(subset=FEATS + ["label"])
            tr, te = df[df["ts"] <= cutoff - pd.Timedelta(hours=h)], df[df["ts"] > cutoff]
            res = {"target": target, "horizon_h": h, "n_train": len(tr), "n_test": len(te)}

            p_naive = te["y_tgt_m24"].values
            res["naive"] = {"wmape": round(_wmape(te["label"].values, p_naive), 2), "size_kb": 0, "infer_us": 0,
                            "spike": _spike_scores(te, p_naive, thr_map)}

            ridge = make_pipeline(StandardScaler(), Ridge(alpha=1.0)).fit(tr[FEATS], tr["label"])
            t0 = time.perf_counter(); p_r = ridge.predict(te[FEATS]); dt = (time.perf_counter() - t0) / len(te)
            res["ridge"] = {"wmape": round(_wmape(te["label"].values, p_r), 2),
                            "size_kb": round(len(pickle.dumps(ridge)) / 1024, 1), "infer_us": round(dt * 1e6, 2),
                            "spike": _spike_scores(te, p_r, thr_map)}

            gbm = lgb.LGBMRegressor(n_estimators=250, learning_rate=0.05, num_leaves=31, min_child_samples=20,
                                    subsample=0.8, subsample_freq=1, colsample_bytree=0.9, verbose=-1, random_state=0)
            gbm.fit(tr[FEATS], tr["label"])
            t0 = time.perf_counter(); p_g = np.clip(gbm.predict(te[FEATS]), 0, None); dt = (time.perf_counter() - t0) / len(te)
            res["lightgbm"] = {"wmape": round(_wmape(te["label"].values, p_g), 2),
                               "size_kb": round(len(gbm.booster_.model_to_string()) / 1024, 1), "infer_us": round(dt * 1e6, 2),
                               "spike": _spike_scores(te, p_g, thr_map)}
            # per-building accuracy for the chosen model
            te = te.assign(pred=p_g)
            res["per_building_wmape"] = {b: round(_wmape(g["label"].values, g["pred"].values), 2) for b, g in te.groupby("building_id")}
            res["chosen"] = "lightgbm"
            metrics.append(res)

            # refit chosen model on all data for live forecasting
            gbm_full = lgb.LGBMRegressor(**gbm.get_params()).fit(df[FEATS], df["label"])
            models[(target, h)] = {"model": gbm_full, "thr": thr_map,
                                   "holdout": te[["building_id", "target_time", "label", "pred"]]}
    return models, metrics


def forecast_next(models, hourly, calendar, buildings):
    """Forecast 1..12h ahead from the latest timestamp for every building.

    Uses the 6h model for horizons 1-6 and the 12h model for 7-12 (direct strategy;
    we only train two horizons to keep the edge footprint small, then interpolate)."""
    out = []
    t_now = hourly["ts"].max()
    for target in TARGETS:
        for h in HORIZONS:
            df = build_frame(hourly, calendar, buildings, target, h)
            last = df[df["ts"] == t_now].copy()
            last[FEATS] = last[FEATS].fillna(0)
            m = models[(target, h)]
            last["pred"] = np.clip(m["model"].predict(last[FEATS]), 0, None)
            last["thr"] = last["building_id"].map(m["thr"])
            for _, r in last.iterrows():
                out.append({"building_id": r["building_id"], "target": target, "horizon_h": h,
                            "target_time": r["target_time"].strftime("%Y-%m-%d %H:%M"),
                            "pred": round(float(r["pred"]), 2), "spike_threshold": round(float(r["thr"]), 2),
                            "spike": bool(r["pred"] > r["thr"])})
    return out
