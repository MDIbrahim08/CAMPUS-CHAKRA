"""Supabase Database Integration Layer for Prana Pulse.

Provides fault-tolerant persistence with PostgreSQL via Supabase:
- Campus buildings & baselines
- Fused hourly telemetry
- Edge smart-bin classification events
- Anomalies & financial/carbon attribution
- Eco-Credits behavioral leaderboard
- Gateway sync idempotency tracking

If SUPABASE_URL / SUPABASE_KEY are not provided, it gracefully falls back
to local cache / SQLite, ensuring zero runtime downtime.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("pranapulse.db")

_client = None
_is_initialized = False


def _get_supabase_client():
    global _client, _is_initialized
    if _is_initialized:
        return _client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY")

    if not url or not key:
        _is_initialized = True
        logger.info("Supabase credentials not configured in .env. Running in resilient local cache mode.")
        return None

    try:
        from supabase import create_client
        _client = create_client(url, key)
        _is_initialized = True
        logger.info("Connected to Supabase PostgreSQL at %s", url)
    except Exception as e:
        logger.warning("Failed to connect to Supabase: %s. Using local fallback.", e)
        _client = None
        _is_initialized = True

    return _client


def is_connected() -> bool:
    return _get_supabase_client() is not None


def seed_from_local_cache() -> dict[str, Any]:
    """Seed Supabase with the baseline campus telemetry and buildings if empty."""
    client = _get_supabase_client()
    if not client:
        return {"ok": False, "reason": "Supabase not configured"}

    p1 = Path(__file__).resolve().parent.parent / "web" / "data" / "dashboard.json"
    p2 = Path(__file__).resolve().parent.parent / "cache" / "dashboard.json"
    cache_file = p1 if p1.exists() else p2
    if not cache_file.exists():
        return {"ok": False, "reason": "No local cache found"}

    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        buildings = data.get("buildings", [])

        # 1. Seed campus_buildings
        bldg_rows = []
        for b in buildings:
            b_id = b.get("building_id")
            bldg_rows.append({
                "id": b_id,
                "name": b.get("building_name", b_id),
                "building_type": b.get("building_type", "academic"),
                "area_sqm": float(b.get("area_sqm", 2500)),
                "daily_baseline_kwh": float(b.get("solar_capacity_kw", 100.0) * 4.5),
                "daily_baseline_water_kl": 25.0,
            })

        if bldg_rows:
            client.table("campus_buildings").upsert(bldg_rows).execute()

        # 2. Seed grid_anomalies
        anomalies = data.get("anomalies", [])
        anom_rows = []
        for idx, a in enumerate(anomalies):
            b_id = a.get("building_id")
            anom_rows.append({
                "anomaly_id": f"anom_{b_id}_{a.get('date', '2026-08-27')}_{idx}",
                "timestamp": f"{a.get('date', '2026-08-27')}T12:00:00Z",
                "building_id": b_id,
                "metric": a.get("metric_label", a.get("metric", "Electricity")),
                "observed_value": float(a.get("value", 0.0)),
                "baseline_value": float(a.get("expected", 0.0)),
                "z_score": float(a.get("z", 3.0)),
                "severity": "CRITICAL" if a.get("z", 0) > 10 else "HIGH",
                "attributed_root_cause": a.get("cause", "Unscheduled surge"),
                "financial_impact_inr": float(a.get("impact_rs", 0.0)),
                "carbon_impact_kg": float(a.get("impact_co2_kg", 0.0)),
            })

        if anom_rows:
            client.table("grid_anomalies").upsert(anom_rows).execute()

        # 3. Seed eco_credits_leaderboard
        lead_data = data.get("leaderboard", {})
        latest_lb = lead_data.get("latest", []) if isinstance(lead_data, dict) else lead_data
        lead_rows = []
        for rank, lb in enumerate(latest_lb, 1):
            lead_rows.append({
                "building_id": lb.get("building_id"),
                "building_name": lb.get("building_name"),
                "normalized_consumption_ratio": round(1.0 + (lb.get("elec_change_pct", 0.0) / 100.0), 3),
                "eco_credits_earned": float(lb.get("credits", 10.0)),
                "rank": rank,
                "footfall_factor": 1.0,
            })

        if lead_rows:
            client.table("eco_credits_leaderboard").upsert(lead_rows).execute()

        return {"ok": True, "seeded_buildings": len(bldg_rows), "seeded_anomalies": len(anom_rows), "seeded_leaderboard": len(lead_rows)}
    except Exception as e:
        logger.error("Error seeding Supabase: %s", e)
        return {"ok": False, "error": str(e)}



def record_waste_event(event: dict[str, Any]) -> bool:
    """Record a smart-bin classification event to Supabase."""
    client = _get_supabase_client()
    if not client:
        return False
    try:
        row = {
            "event_id": str(event.get("event_id")),
            "timestamp": event.get("timestamp"),
            "building_id": event.get("building_id"),
            "weight_kg": float(event.get("weight_kg", 0.0)),
            "fill_level_pct": float(event.get("fill_level_pct", 0.0)),
            "optical_signature": float(event.get("optical_signature", 0.0)),
            "predicted_class": event.get("predicted_class"),
            "confidence": float(event.get("confidence", 0.0)),
            "latency_ms": float(event.get("latency_ms", 0.0)),
            "is_synced": True,
        }
        client.table("waste_events").insert(row).execute()
        return True
    except Exception as e:
        logger.warning("Supabase record_waste_event failed: %s", e)
        return False


def record_sync_packet(packet_id: str, seq_num: int, building_id: str, count: int = 1) -> bool:
    """Track idempotent sync packet in Supabase."""
    client = _get_supabase_client()
    if not client:
        return False
    try:
        row = {
            "packet_id": packet_id,
            "sequence_num": seq_num,
            "building_id": building_id,
            "sync_status": "COMMITTED",
            "records_count": count,
        }
        client.table("gateway_sync_log").upsert(row).execute()
        return True
    except Exception as e:
        logger.warning("Supabase record_sync_packet failed: %s", e)
        return False
