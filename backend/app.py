"""Campus Chakra FastAPI server.

  uvicorn backend.app:app --port 8000      then open http://localhost:8000

Endpoints
  GET  /api/dashboard                 precomputed campus dashboard JSON
  POST /api/classify                  classify one smart-bin event (JSON) – edge latency demo
  POST /api/evaluate/waste            upload CSV/XLSX of bin events -> predictions (+accuracy if labelled)
  POST /api/evaluate/hourly           upload hourly telemetry -> integrity report + 12h forecast + anomalies
  POST /api/evaluate/manual           upload manual logs -> alias/unit normalisation
  POST /api/gateway/sync              edge gateway flushes its offline buffer (idempotent merge)
  GET  /api/gateway/state             server-side view of merged telemetry
  POST /api/copilot                   multi-agent LLM brief grounded on analytics evidence
  GET  /api/llm/status                which LLM providers are configured
  GET  /api/predictions.csv           test-set predictions file
"""
from __future__ import annotations

import io
import json
import os
import pickle
import time
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import anomaly as A
from . import classifier as CL
from . import config as C
from . import db
from . import forecast as FC
from . import ingest as I
from . import llm
from .pipeline import _clean, _jsonable

app = FastAPI(title="Campus Chakra – Predictive Circular-Resource Grid")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STATE: dict[str, Any] = {}
FORECAST_BUNDLE: dict[str, Any] = {}


def state():
    if not STATE:
        STATE["classifier"] = CL.load_edge_model()
    return STATE


def forecast_bundle():
    """Load or build the small forecast-only cache used for uploaded telemetry."""
    if FORECAST_BUNDLE:
        return FORECAST_BUNDLE

    cache_path = C.CACHE_DIR / "forecast_bundle.pkl"
    if cache_path.exists():
        with open(cache_path, "rb") as cache_file:
            FORECAST_BUNDLE.update(pickle.load(cache_file))
        return FORECAST_BUNDLE

    calendar = I.load_table("calendar")
    buildings = I.load_table("buildings")
    hourly_raw = I.load_table("hourly_streams")
    hourly, _ = I.clean_hourly(hourly_raw, calendar)
    models, metrics = FC.train_and_evaluate(hourly, calendar, buildings)
    FORECAST_BUNDLE.update({"calendar": calendar, "buildings": buildings, "models": models, "metrics": metrics})
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = cache_path.with_suffix(".tmp")
    with open(temporary_path, "wb") as cache_file:
        pickle.dump(FORECAST_BUNDLE, cache_file)
    temporary_path.replace(cache_path)
    return FORECAST_BUNDLE


def J(obj):
    return JSONResponse(json.loads(json.dumps(_clean(obj), default=_jsonable)))


@app.on_event("startup")
def _warm():
    state()


@app.get("/api/dashboard")
def get_dashboard():
    p = C.WEB_DIR / "data" / "dashboard.json"
    if p.exists():
        return JSONResponse(json.loads(p.read_text(encoding="utf-8")))
    raise HTTPException(404, "Dashboard data not generated yet")


@app.get("/api/weather/live")
def weather_live():
    """Fetch live meteorological observations for Chanakya University Global Campus (Devanahalli)."""
    api_key = os.environ.get("OPENWEATHER_API_KEY")
    if not api_key:
        return {"ok": False, "error": "OPENWEATHER_API_KEY is not configured", "temp_c": 26.8,
                "humidity_pct": 75, "description": "Partly Cloudy"}
    url = f"https://api.openweathermap.org/data/2.5/weather?lat=13.2846&lon=77.6078&appid={api_key}&units=metric"
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read().decode())
        return {
            "ok": True,
            "campus": "Chanakya University - Global Campus (Devanahalli)",
            "temp_c": round(data["main"]["temp"], 1),
            "humidity_pct": data["main"]["humidity"],
            "wind_speed_ms": data["wind"]["speed"],
            "description": data["weather"][0]["description"].title(),
            "solar_radiation_index": "High" if data["clouds"]["all"] < 30 else "Moderate" if data["clouds"]["all"] < 70 else "Low (Cloudy)",
            "impact_on_grid": "Higher HVAC demand expected" if data["main"]["temp"] > 28 else "Normal baseline meteorological load"
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "temp_c": 26.8, "humidity_pct": 75, "description": "Partly Cloudy"}


@app.post("/api/copilot/transcribe")
async def copilot_transcribe(file: UploadFile = File(...)):
    """Transcribe vocal prompt using open-source Whisper Large v3 on Groq."""
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        raise HTTPException(400, "Groq API key required for Whisper transcription")
    content = await file.read()
    # Call Groq Whisper endpoint
    import urllib.request
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file.filename or "speech.wav"}"\r\n'
        f"Content-Type: audio/wav\r\n\r\n"
    ).encode() + content + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="model"\r\n\r\n'
        f"whisper-large-v3-turbo\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        data=body,
        headers={
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "curl/7.68.0",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        res = json.loads(r.read().decode())
    return {"text": res.get("text", "")}


# --------------------------------------------------------------------------- classify
class Event(BaseModel):
    weight_g: float | None = None
    moisture_pct: float | None = None
    metal_signal: float | None = None
    transparency: float | None = None
    acoustic_hardness: float | None = None
    building_id: str | None = None
    timestamp: str | None = None
    event_id: str | None = None


@app.post("/api/classify")
def classify(ev: Event):
    s = state()
    df = pd.DataFrame([ev.model_dump()])
    t0 = time.perf_counter()
    out = CL.predict(s["classifier"], df).iloc[0]
    ms = (time.perf_counter() - t0) * 1000
    proba = s["classifier"].predict_proba(CL.featurize(df))[0]
    out_dict = {"predicted_class": out["predicted_class"], "confidence": float(out["confidence"]), "route": out["route"],
                "latency_ms": round(ms, 2), "probabilities": dict(zip(s["classifier"].classes_.tolist(), np.round(proba, 3).tolist()))}
    # Asynchronous or non-blocking Supabase write
    try:
        db.record_waste_event({
            "event_id": ev.event_id or f"evt_{int(time.time()*1000)}",
            "timestamp": ev.timestamp or pd.Timestamp.now().isoformat(),
            "building_id": ev.building_id or "academic_block",
            "weight_kg": (ev.weight_g or 100.0) / 1000.0,
            "fill_level_pct": 50.0,
            "optical_signature": ev.metal_signal or 0.0,
            "predicted_class": out["predicted_class"],
            "confidence": float(out["confidence"]),
            "latency_ms": round(ms, 2)
        })
    except Exception:
        pass
    return J(out_dict)


# --------------------------------------------------------------------------- evaluation uploads
async def _read(file: UploadFile) -> pd.DataFrame:
    try:
        return I.read_any(await file.read(), file.filename or "x.csv")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Could not parse file: {e}")


@app.post("/api/evaluate/waste")
async def evaluate_waste(file: UploadFile = File(...)):
    s = state()
    df = await _read(file)
    required = {"weight_g", "moisture_pct", "metal_signal", "transparency", "acoustic_hardness"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise HTTPException(400, f"waste file is missing required sensor columns: {missing}")
    if df.empty:
        raise HTTPException(400, "waste file contains no records")
    invalid = [column for column in required if pd.to_numeric(df[column], errors="coerce").isna().all()]
    if invalid:
        raise HTTPException(400, f"waste file has no numeric values for: {invalid}")
    t0 = time.perf_counter()
    preds = CL.predict(s["classifier"], df)
    total_ms = (time.perf_counter() - t0) * 1000
    res = {"rows": len(df), "ms_per_event": round(total_ms / max(len(df), 1), 3), "total_ms": round(total_ms, 1),
           "distribution": preds["predicted_class"].value_counts().to_dict(),
           "preview": preds.head(50).to_dict("records")}
    lc = CL.label_col(df)
    if lc:
        from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
        y = df[lc].astype(str).values; p = preds["predicted_class"].values
        labels = C.WASTE_CLASSES
        res["labelled"] = True
        res["accuracy"] = round(accuracy_score(y, p) * 100, 2)
        res["macro_f1"] = round(f1_score(y, p, average="macro") * 100, 2)
        res["report"] = classification_report(y, p, labels=labels, output_dict=True, zero_division=0)
        res["confusion"] = confusion_matrix(y, p, labels=labels).tolist(); res["labels"] = labels
    else:
        res["labelled"] = False
    STATE["last_eval_preds"] = preds
    return J(res)


@app.get("/api/evaluate/waste/download")
def download_eval():
    p = STATE.get("last_eval_preds")
    if p is None:
        raise HTTPException(404, "Run an evaluation first")
    buf = io.StringIO(); p.to_csv(buf, index=False)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=predictions.csv"})


@app.get("/api/predictions.csv")
def predictions_csv():
    return FileResponse(C.ROOT / "waste_events_test_predictions.csv", filename="waste_events_test_predictions.csv")


@app.post("/api/evaluate/hourly")
async def evaluate_hourly(file: UploadFile = File(...)):
    raw = await _read(file)
    need = {"timestamp", "building_id", "electricity_kwh", "water_litres"}
    if not need.issubset(raw.columns):
        raise HTTPException(400, f"hourly file needs columns {sorted(need)}")
    if raw.empty:
        raise HTTPException(400, "hourly file contains no records")
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], errors="coerce")
    if raw["timestamp"].isna().any():
        raise HTTPException(400, "hourly file contains invalid timestamp values")
    for column in (need - {"timestamp", "building_id"}):
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    if raw[["electricity_kwh", "water_litres"]].isna().all(axis=None):
        raise HTTPException(400, "hourly file needs numeric electricity_kwh or water_litres values")
    for c in ["solar_generation_kwh", "footfall"]:
        if c not in raw:
            raw[c] = 0.0
    bundle = forecast_bundle()
    cal, bld = bundle["calendar"], bundle["buildings"]
    invalid_buildings = sorted(set(raw["building_id"].dropna()) - set(bld["building_id"]))
    if invalid_buildings:
        raise HTTPException(400, f"unknown building_id values: {invalid_buildings}")
    # extend calendar if uploaded data is outside known range (unknown days -> 'working', no event)
    hourly, integrity = I.clean_hourly(raw, cal)
    days = pd.date_range(hourly["ts"].min().normalize(), (hourly["ts"].max() + pd.Timedelta(hours=12)).normalize())
    calx = cal.copy(); calx["date"] = pd.to_datetime(calx["date"])
    missing = [d for d in days if d not in set(calx["date"])]
    if missing:
        add = pd.DataFrame({"date": missing, "day_of_week": [d.day_name() for d in missing],
                            "day_type": ["weekend" if d.dayofweek >= 5 else "working" for d in missing],
                            "event": None, "avg_temp_c": calx["avg_temp_c"].median(),
                            "rainfall_mm": 0.0, "humidity_pct": calx["humidity_pct"].median()})
        calx = pd.concat([calx, add], ignore_index=True)
    fc = FC.forecast_next(bundle["models"], hourly, calx, bld)
    # evaluate forecast accuracy on the uploaded window itself (backtest with trained models)
    back = []
    for (target, h), m in bundle["models"].items():
        df = FC.build_frame(hourly, calx, bld, target, h).dropna(subset=["label"])
        if len(df):
            X = df[FC.FEATS].fillna(0)
            p = np.clip(m["model"].predict(X), 0, None)
            back.append({"target": target, "horizon_h": h, "n": len(df),
                         "wmape": round(float(np.abs(df["label"] - p).sum() / max(df["label"].abs().sum(), 1e-9) * 100), 2)})
    return J({"integrity": integrity, "forecast": fc, "backtest": back,
              "range": [hourly["ts"].min().strftime("%Y-%m-%d %H:%M"), hourly["ts"].max().strftime("%Y-%m-%d %H:%M")]})


@app.post("/api/evaluate/manual")
async def evaluate_manual(file: UploadFile = File(...)):
    raw = await _read(file)
    if raw.empty:
        raise HTTPException(400, "manual log file contains no records")
    ml = I.normalise_manual_logs(raw)
    ml["logged_at"] = ml["logged_at"].dt.strftime("%Y-%m-%d %H:%M")
    return J({"rows": len(ml), "resolved_pct": round(100 * ml["building_id"].notna().mean(), 1),
              "methods": ml["resolve_method"].value_counts().to_dict(),
              "preview": ml.head(100).to_dict("records")})


# --------------------------------------------------------------------------- edge gateway sync
GATEWAY: dict[tuple, dict] = {}
SYNC_LOG: list[dict] = []


class Reading(BaseModel):
    building_id: str
    timestamp: str
    electricity_kwh: float | None = None
    water_litres: float | None = None
    seq: int | None = None
    sent_at: str | None = None


class SyncBatch(BaseModel):
    gateway_id: str
    readings: list[Reading]


@app.post("/api/gateway/sync")
def gateway_sync(batch: SyncBatch):
    """Idempotent merge. Key = (building_id, timestamp). Rules:
       - new key -> insert
       - same key, same values (retransmission) -> duplicate, ignored
       - same key, different values -> keep the record with the HIGHER seq (later firmware correction),
         and log a conflict. Dashboard aggregates are recomputed from the merged store, never appended."""
    ins = dup = upd = 0
    conflicts = []
    for r in batch.readings:
        k = (r.building_id, r.timestamp)
        cur = GATEWAY.get(k)
        rec = r.model_dump()
        if cur is None:
            GATEWAY[k] = rec; ins += 1
        elif abs((cur.get("electricity_kwh") or 0) - (r.electricity_kwh or 0)) < 1e-6 and abs((cur.get("water_litres") or 0) - (r.water_litres or 0)) < 1e-6:
            dup += 1
        else:
            if (r.seq or 0) > (cur.get("seq") or 0):
                GATEWAY[k] = rec; upd += 1
            conflicts.append({"key": list(k), "kept_seq": max(r.seq or 0, cur.get("seq") or 0)})
    entry = {"gateway": batch.gateway_id, "received": len(batch.readings), "inserted": ins, "duplicates": dup,
             "updated": upd, "conflicts": len(conflicts), "at": pd.Timestamp.now().strftime("%H:%M:%S")}
    SYNC_LOG.append(entry)
    try:
        packet_sequence = time.time_ns()
        db.record_sync_packet(f"pkt_{batch.gateway_id}_{packet_sequence}", packet_sequence, batch.gateway_id, ins + upd)
    except Exception:
        pass
    return J({**entry, "store_size": len(GATEWAY)})


@app.get("/api/gateway/state")
def gateway_state():
    df = pd.DataFrame(GATEWAY.values())
    agg = {} if df.empty else df.groupby("building_id")[["electricity_kwh", "water_litres"]].sum().round(2).to_dict("index")
    return J({"store_size": len(GATEWAY), "per_building": agg, "log": SYNC_LOG[-20:]})


@app.post("/api/gateway/reset")
def gateway_reset():
    GATEWAY.clear(); SYNC_LOG.clear()
    return {"ok": True}


# --------------------------------------------------------------------------- LLM copilot
@app.get("/api/llm/status")
def llm_status():
    return {"providers": llm.available(), "models": {p: c["model"] for p, c in llm.PROVIDERS.items()}}


class CopilotReq(BaseModel):
    question: str | None = None
    building_id: str | None = None


@app.post("/api/copilot")
def copilot(req: CopilotReq):
    dash = json.loads((C.WEB_DIR / "data" / "dashboard.json").read_text(encoding="utf-8"))
    an = dash["anomalies"]
    if req.building_id:
        an = [a for a in an if a["building_id"] == req.building_id]
    spikes = [f for f in dash["forecast"]["next"] if f["spike"] and (not req.building_id or f["building_id"] == req.building_id)]
    evidence = {
        "campus": dash["campus"]["name"], "constants": dash["constants"],
        "top_anomalies": [{k: a.get(k) for k in ("building_name", "date", "metric_label", "value", "expected", "deviation_pct",
                                                  "cause", "confidence", "impact_rs", "impact_co2_kg", "action")}
                          | {"evidence": [e["text"] for e in a["evidence"]][:3]} for a in an[:8]],
        "forecast_spikes_next_12h": spikes[:10],
        "kpis": dash["kpis"],
    }
    try:
        return J(llm.multi_agent_brief(evidence, req.question))
    except Exception as e:  # noqa: BLE001 – deterministic fallback keeps the product working offline
        lines = [f"{i+1}. {a['building_name']} – {a['metric_label']} {a['deviation_pct']:+.0f}% on {a['date']}: "
                 f"probable cause **{a['cause']}** ({a['confidence']:.0%}). Action: {a['action']} "
                 f"(≈ Rs {a['impact_rs']:.0f}, {a['impact_co2_kg']} kg CO2)" for i, a in enumerate(evidence["top_anomalies"][:5])]
        return J({"ok": False, "fallback": True, "error": str(e),
                  "trace": [{"agent": "Deterministic engine", "provider": "local", "output": "\n".join(lines)}],
                  "final": "\n".join(lines)})


# --------------------------------------------------------------------------- Supabase DB
@app.get("/api/db/status")
def db_status():
    return {
        "supabase_connected": db.is_connected(),
        "mode": "supabase_cloud" if db.is_connected() else "local_resilient_cache",
        "features": ["campus_buildings", "telemetry_hourly", "waste_events", "grid_anomalies", "eco_credits_leaderboard", "gateway_sync_log"],
    }


@app.post("/api/db/seed")
def db_seed():
    return db.seed_from_local_cache()


# --------------------------------------------------------------------------- static UI
app.mount("/", StaticFiles(directory=C.WEB_DIR, html=True), name="web")
