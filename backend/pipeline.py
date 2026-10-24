"""End-to-end pipeline: load -> clean -> fuse -> classify -> forecast -> attribute -> incentivise.

Run:  python -m backend.pipeline        (writes cache/state.pkl + web/data/dashboard.json)
The API re-runs parts of this on uploaded evaluation data.
"""
from __future__ import annotations

import json
import pickle
import time

import numpy as np
import pandas as pd

from . import anomaly as A
from . import classifier as CL
from . import config as C
from . import forecast as FC
from . import incentives as INC
from . import ingest as I


def _jsonable(o):
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.bool_,)): return bool(o)
    if isinstance(o, (pd.Timestamp,)): return o.strftime("%Y-%m-%d %H:%M")
    if isinstance(o, float) and not np.isfinite(o): return None
    return str(o)


def _clean(o):
    if isinstance(o, dict): return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list): return [_clean(v) for v in o]
    if isinstance(o, float) and not np.isfinite(o): return None
    return o


def run(log=print):
    T = {}
    t0 = time.time()
    tables = {n: I.load_table(n) for n in ["buildings", "calendar", "daily_summary", "hourly_streams",
                                           "manual_logs", "waste_events_train", "waste_events_test"]}
    T["load"] = time.time() - t0; log(f"loaded in {T['load']:.1f}s")

    t = time.time()
    hourly, integrity = I.clean_hourly(tables["hourly_streams"], tables["calendar"])
    manual = I.normalise_manual_logs(tables["manual_logs"])
    fused = I.fuse_daily(hourly, tables["daily_summary"], manual, tables["buildings"])
    T["ingest"] = time.time() - t; log(f"ingest+fusion {T['ingest']:.1f}s")

    t = time.time()
    cv = CL.cross_validate(tables["waste_events_train"])
    full, edge, clf_info = CL.train_final(tables["waste_events_train"])
    preds = CL.predict(full, tables["waste_events_test"])
    preds[["event_id", "predicted_class"]].to_csv(C.ROOT / "waste_events_test_predictions.csv", index=False)
    edge_json = CL.export_edge_json(edge, clf_info["features"])
    T["classifier"] = time.time() - t; log(f"classifier {T['classifier']:.1f}s  cv={cv['full']['accuracy']}% edge={cv['edge']['accuracy']}%")

    t = time.time()
    models, fc_metrics = FC.train_and_evaluate(hourly, tables["calendar"], tables["buildings"])
    fc_next = FC.forecast_next(models, hourly, tables["calendar"], tables["buildings"])
    T["forecast"] = time.time() - t; log(f"forecast {T['forecast']:.1f}s")

    t = time.time()
    anoms = A.detect_daily(fused, tables["calendar"])
    stuck = A.detect_hourly_patterns(hourly)
    attributed = A.attribute(anoms, fused, hourly, manual, tables["calendar"], stuck)
    validation = A.validate_against_notes(attributed, manual)
    T["anomaly"] = time.time() - t; log(f"anomaly {T['anomaly']:.1f}s  {len(attributed)} anomalies, note recall {validation['recall_pct']}%")

    lb = INC.leaderboard(fused, tables["calendar"])

    state = {"tables": tables, "hourly": hourly, "manual": manual, "fused": fused, "full": full, "edge": edge,
             "models": models, "clf_info": clf_info}
    with open(C.CACHE_DIR / "state.pkl", "wb") as f:
        pickle.dump(state, f)

    dash = build_dashboard(tables, hourly, fused, manual, integrity, cv, clf_info, preds, fc_metrics, fc_next,
                           models, attributed, validation, lb, T)
    out = C.WEB_DIR / "data"; out.mkdir(parents=True, exist_ok=True)
    (out / "dashboard.json").write_text(json.dumps(_clean(dash), default=_jsonable), encoding="utf-8")
    (out / "edge_model.json").write_text(json.dumps(edge_json), encoding="utf-8")
    log(f"done in {time.time() - t0:.1f}s")
    return state, dash


def build_dashboard(tables, hourly, fused, manual, integrity, cv, clf_info, preds, fc_metrics, fc_next,
                    models, attributed, validation, lb, T):
    b = tables["buildings"]
    # campus KPIs
    sem = fused
    kwh = float(sem["elec_fused"].sum()); water = float(sem["water_fused"].sum())
    solar = float(sem["solar_generation_kwh"].fillna(sem["solar_hourly"]).sum())
    waste = float(sem["total_waste_kg"].sum()); diverted = float(sem["diverted_kg"].sum())
    kpis = {"electricity_kwh": kwh, "water_kl": water / 1000, "solar_kwh": solar,
            "solar_share_pct": 100 * solar / max(kwh + solar, 1), "waste_kg": waste,
            "diversion_pct": 100 * diverted / max(waste, 1), "landfill_kg": float(sem["landfill_kg"].sum()),
            "compost_produced_kg": float(sem["composted_kg"].sum()) / C.COMPOST_RATIO,
            "co2_t": (kwh + water / 1000 * C.WATER_KWH_PER_KL) * C.CO2_KG_PER_KWH / 1000,
            "cost_rs": (kwh + water / 1000 * C.WATER_KWH_PER_KL) * C.TARIFF_RS_PER_KWH,
            "solar_co2_avoided_t": solar * C.CO2_KG_PER_KWH / 1000,
            "days": int(sem["date"].nunique()), "buildings": int(len(b))}
    # per-building daily series (compact)
    daily = {}
    for bid, g in fused.groupby("building_id"):
        g = g.sort_values("date")
        daily[bid] = {k: g[c].round(1).tolist() for k, c in [("elec", "elec_fused"), ("water", "water_fused"),
                      ("solar", "solar_hourly"), ("occ", "occupancy_avg"), ("waste", "total_waste_kg"),
                      ("landfill", "landfill_kg"), ("diverted", "diverted_kg"), ("conf", "elec_conf")]}
    dates = sorted(fused["date"].unique().tolist())
    # last 72h hourly + forecast per building
    t_end = hourly["ts"].max()
    recent = hourly[hourly["ts"] > t_end - pd.Timedelta(hours=72)]
    hourly_recent = {bid: {"ts": g["ts"].dt.strftime("%m-%d %H:%M").tolist(), "elec": g["electricity_kwh"].round(2).tolist(),
                           "water": g["water_litres"].round(0).tolist(), "status": g["status"].tolist()}
                     for bid, g in recent.sort_values("ts").groupby("building_id")}
    # holdout overlay (last 7 days) for chosen model, per building
    holdout = {}
    for (target, h), m in models.items():
        ho = m["holdout"]; ho = ho[ho["target_time"] > ho["target_time"].max() - pd.Timedelta(days=7)]
        for bid, g in ho.groupby("building_id"):
            holdout.setdefault(bid, {}).setdefault(target, {})[str(h)] = {
                "t": g["target_time"].dt.strftime("%m-%d %H:%M").tolist(), "y": g["label"].round(2).tolist(),
                "p": g["pred"].round(2).tolist()}
    # sample of live stream events for the edge demo (test set, chronological)
    test = tables["waste_events_test"].copy()
    test = test.merge(preds[["event_id", "predicted_class", "confidence"]], on="event_id", how="left")
    stream = test.sort_values("timestamp").head(400)
    stream = stream.where(pd.notna(stream), None).to_dict("records")
    pred_dist = preds["predicted_class"].value_counts().to_dict()
    manual_notes = manual[manual["stream"] == "note"][["logged_at", "building", "building_id", "logger_role", "note"]]
    alias_examples = manual.groupby(["building", "building_id", "resolve_method"]).size().reset_index(name="n").sort_values("n", ascending=False)
    unit_examples = manual[manual["stream"] != "note"].groupby(["stream", "unit"]).size().reset_index(name="n")
    conflicts = fused[(fused["elec_conflict"] == True) | (fused["water_conflict"] == True)][
        ["date", "building_id", "electricity_kwh", "e_hourly", "e_manual", "elec_fused", "elec_conf",
         "water_litres", "w_hourly", "w_manual", "water_fused", "water_conf"]].tail(25)
    return {
        "generated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
        "campus": C.CAMPUS, "constants": {"co2": C.CO2_KG_PER_KWH, "tariff": C.TARIFF_RS_PER_KWH, "water_kwh_per_kl": C.WATER_KWH_PER_KL},
        "buildings": b.to_dict("records"), "kpis": kpis, "dates": dates, "daily": daily,
        "calendar": tables["calendar"].where(pd.notna(tables["calendar"]), None).to_dict("records"),
        "integrity": integrity, "conflicts": conflicts.to_dict("records"),
        "alias_examples": alias_examples.to_dict("records"), "unit_examples": unit_examples.to_dict("records"),
        "classifier": {"cv": cv, "info": clf_info, "test_pred_dist": pred_dist, "n_test": int(len(preds)),
                       "ms_per_event_batch": preds.attrs.get("ms_per_event")},
        "stream": stream,
        "forecast": {"metrics": fc_metrics, "next": fc_next, "hourly_recent": hourly_recent, "holdout": holdout,
                     "t_now": t_end.strftime("%Y-%m-%d %H:%M")},
        "anomalies": attributed[:150], "anomaly_count": len(attributed), "validation": validation,
        "notes": manual_notes.assign(logged_at=manual_notes["logged_at"].dt.strftime("%Y-%m-%d %H:%M")).to_dict("records"),
        "leaderboard": lb, "timings_s": {k: round(v, 2) for k, v in T.items()},
    }


if __name__ == "__main__":
    run()
