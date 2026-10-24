"""Anomaly detection + root-cause attribution + ranked, explainable recommendations.

Pipeline:
 1. Detect: robust z-score of each building-day metric vs its own baseline
    (median of the same building & same day-type over the trailing 28 days,
    scaled by MAD). Also hourly pattern checks: meter stuck at zero, night-time
    baseload, solar under-generation vs peers/irradiance proxy.
 2. Attribute: score candidate causes using independent evidence:
    calendar events, manual-log narrative notes (keyword NLP), same-type peer
    behaviour, hour-of-day (shift) decomposition, weather, data-quality flags.
 3. Recommend: map the winning cause to an action, quantify Rs / kWh / CO2
    impact using README constants, rank by impact x confidence, and keep the
    evidence list so every recommendation is justified.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import config as C

METRICS = {
    "elec_fused": {"label": "Electricity", "unit": "kWh"},
    "water_fused": {"label": "Water", "unit": "L"},
    "landfill_kg": {"label": "Landfill waste", "unit": "kg"},
    "wet_organic_kg": {"label": "Wet organic waste", "unit": "kg"},
    "solar_hourly": {"label": "Solar generation", "unit": "kWh"},
}

# keyword -> (metric family, cause type)
NOTE_RULES = [
    (r"leak|pipe|wet patch|plumber|tank refill", "water", "leak"),
    (r"meter stuck|stuck at zero", "water", "sensor_fault"),
    (r"calibrat|flicker|not sure if the reading|reading looked odd", "any", "sensor_fault"),
    (r"composter|compost", "waste", "equipment_failure"),
    (r"inverter|solar", "solar", "equipment_failure"),
    (r"left on|lights were left|ac and lights", "electricity", "behaviour"),
    (r"higher than last month", "electricity", "unexplained_rise"),
    (r"alumni|expecting|extra cooking|guests|fest", "any", "event"),
]

EVENT_TYPE_AFFINITY = {  # event keyword -> building types affected
    "hackathon": ["labs", "food"], "alumni": ["food"], "feast": ["food", "hostel"],
    "library": ["library"], "exam": ["library", "hostel", "academic"], "placement": ["academic", "labs"],
    "check-in": ["hostel"], "hostel": ["hostel"], "lab": ["labs"], "iot": ["labs"], "expo": ["labs", "academic"],
    "sports": ["hostel", "food"], "orientation": ["academic", "library"], "fest": ["food", "academic"],
    "server": ["labs", "admin"], "substation": ["academic", "labs", "admin", "library"],
}

ACTIONS = {
    "leak": "Dispatch plumber to inspect supply lines; isolate the zone valve and verify with a 2 AM night-flow test.",
    "sensor_fault": "Flag meter for recalibration/vendor check; substitute fused estimate on dashboard until fixed.",
    "equipment_failure": "Raise priority maintenance ticket; reroute affected stream (e.g. wet waste to backup composter).",
    "behaviour": "Enable after-hours auto-shutoff (BMS schedule) and notify building warden; nudge occupants via eco-credits.",
    "event": "Pre-stage resources for the event (extra segregated bins, staggered HVAC, mess batch cooking) 6-12h ahead.",
    "occupancy": "Expected demand surge from occupancy; pre-cool/pre-pump in off-peak hours and add bins at entrances.",
    "weather": "Weather-driven load; tune HVAC set-points (+1 °C saves ~6%) and shift pumping to solar hours.",
    "unexplained_rise": "Run sub-metering audit by floor; check HVAC schedules and phantom loads.",
    "night_baseload": "High overnight base-load: audit HVAC/lighting schedules; enforce 22:00 shutdown checklist.",
    "data_gap": "Gateway connectivity degraded; check edge buffer health and uplink. Values are imputed.",
}


def _robust_z(x: pd.Series, base: pd.Series, mad: pd.Series):
    return (x - base) / (1.4826 * mad.replace(0, np.nan))


def detect_daily(fused: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    cal = calendar.copy()
    cal["date"] = pd.to_datetime(cal["date"]).dt.strftime("%Y-%m-%d")
    df = fused.merge(cal[["date", "day_type", "event", "avg_temp_c"]], on="date", how="left")
    df["day_group"] = df["day_type"].replace({"weekend": "off", "holiday": "off", "semester_break": "break",
                                              "working": "on", "exam": "on"})
    rows = []
    for (b, metric), _ in [((b, m), None) for b in df["building_id"].unique() for m in METRICS]:
        g = df[df["building_id"] == b].sort_values("date").reset_index(drop=True)
        if metric not in g or g[metric].fillna(0).sum() == 0:
            continue
        x = g[metric]
        base = pd.Series(np.nan, index=g.index); mad = pd.Series(np.nan, index=g.index)
        for i in range(len(g)):
            hist = g.loc[max(0, i - 35):i - 1]
            hist = hist[hist["day_group"] == g.loc[i, "day_group"]][metric].dropna()
            if len(hist) < 4:
                hist = g.loc[max(0, i - 14):i - 1, metric].dropna()
            if len(hist) >= 4:
                base[i] = hist.median(); mad[i] = (hist - hist.median()).abs().median()
        z = _robust_z(x, base, mad)
        dev = (x - base) / base.replace(0, np.nan)
        flag = (z.abs() > 3.5) & (dev.abs() > 0.2)
        if metric == "solar_hourly":
            flag = (z < -3.5) & (dev < -0.3)
        for i in g.index[flag.fillna(False)]:
            rows.append({"building_id": b, "building_name": g.loc[i, "building_name"], "building_type": g.loc[i, "building_type"],
                         "date": g.loc[i, "date"], "metric": metric, "value": float(x[i]), "expected": float(base[i]),
                         "deviation_pct": round(float(dev[i]) * 100, 1), "z": round(float(z[i]), 1),
                         "day_type": g.loc[i, "day_type"], "event": g.loc[i, "event"] if pd.notna(g.loc[i, "event"]) else None,
                         "conflict": bool(g.loc[i, "elec_conflict"] if metric == "elec_fused" else g.loc[i, "water_conflict"] if metric == "water_fused" else False),
                         "imputed_share": float(g.loc[i, "imputed_share"]) if pd.notna(g.loc[i, "imputed_share"]) else 0.0})
    return pd.DataFrame(rows)


def detect_hourly_patterns(hourly: pd.DataFrame) -> pd.DataFrame:
    """Stuck-at-zero water meters (>=6 consecutive zero hours in daytime-active buildings)."""
    rows = []
    for b, g in hourly.groupby("building_id"):
        g = g.sort_values("ts")
        z = (g["water_litres"] <= 0.5).astype(int)
        run = z.groupby((z != z.shift()).cumsum()).transform("sum") * z
        typical = g["water_litres"].median()
        if typical < 20:
            continue
        stuck = g[run >= 8]
        for d, gd in stuck.groupby(stuck["ts"].dt.strftime("%Y-%m-%d")):
            rows.append({"building_id": b, "date": d, "metric": "water_fused", "pattern": "meter_stuck_zero",
                         "hours": int(len(gd))})
    return pd.DataFrame(rows)


def _note_evidence(notes: pd.DataFrame, b: str, date: str, metric: str, window=4):
    fam = {"elec_fused": "electricity", "water_fused": "water", "landfill_kg": "waste",
           "wet_organic_kg": "waste", "solar_hourly": "solar"}[metric]
    d0 = pd.Timestamp(date)
    cand = notes[(notes["building_id"] == b) & (notes["logged_at"].dt.normalize() >= d0 - pd.Timedelta(days=window))
                 & (notes["logged_at"].dt.normalize() <= d0 + pd.Timedelta(days=2))]
    hits = []
    for _, n in cand.iterrows():
        txt = str(n["note"]).lower()
        for pat, nfam, ctype in NOTE_RULES:
            if re.search(pat, txt) and (nfam in (fam, "any")):
                days = abs((n["logged_at"].normalize() - d0).days)
                hits.append({"cause": ctype, "score": 0.9 - 0.1 * days, "text": n["note"],
                             "when": n["logged_at"].strftime("%Y-%m-%d %H:%M"), "by": n["logger_role"]})
                break
    return hits


def _event_evidence(event, btype, date, calendar):
    hits = []
    cal = calendar.copy(); cal["date"] = pd.to_datetime(cal["date"])
    d0 = pd.Timestamp(date)
    near = cal[(cal["date"] >= d0 - pd.Timedelta(days=1)) & (cal["date"] <= d0)].dropna(subset=["event"])
    for _, r in near.iterrows():
        ev = r["event"].lower()
        for kw, types in EVENT_TYPE_AFFINITY.items():
            if kw in ev and btype in types:
                hits.append({"cause": "event", "score": 0.75 if r["date"] == d0 else 0.5, "text": r["event"],
                             "when": r["date"].strftime("%Y-%m-%d")})
                break
    return hits


def attribute(anoms: pd.DataFrame, fused: pd.DataFrame, hourly: pd.DataFrame, manual: pd.DataFrame,
              calendar: pd.DataFrame, stuck: pd.DataFrame) -> list[dict]:
    notes = manual[manual["stream"] == "note"].copy()
    hourly = hourly.assign(date=hourly["ts"].dt.strftime("%Y-%m-%d"))
    out = []
    for _, a in anoms.iterrows():
        ev = []
        # 1) manual notes
        ev += _note_evidence(notes, a["building_id"], a["date"], a["metric"])
        # 2) calendar event affinity
        if a["deviation_pct"] > 0:
            ev += _event_evidence(a["event"], a["building_type"], a["date"], calendar)
        # 3) peer comparison (same building type, same day)
        peers = fused[(fused["building_type"] == a["building_type"]) & (fused["date"] == a["date"]) &
                      (fused["building_id"] != a["building_id"])]
        peer_note = None
        if len(peers) and a["metric"] in peers:
            pb = fused[(fused["building_type"] == a["building_type"]) & (fused["building_id"] != a["building_id"])]
            pmed = pb.groupby("building_id")[a["metric"]].median()
            pdev = (peers.set_index("building_id")[a["metric"]] / pmed - 1).mean() * 100
            if np.isfinite(pdev):
                same_dir = np.sign(pdev) == np.sign(a["deviation_pct"]) and abs(pdev) > 15
                peer_note = f"Same-type peers moved {pdev:+.0f}% that day"
                if not same_dir:
                    ev.append({"cause": "building_specific", "score": 0.3,
                               "text": f"Peers ({a['building_type']}) normal ({pdev:+.0f}%): issue is local to this building"})
                else:
                    ev.append({"cause": "occupancy", "score": 0.35, "text": f"Peers also deviated ({pdev:+.0f}%): campus-wide driver"})
        # 4) shift decomposition for hourly-backed metrics
        shift_txt = None
        col = {"elec_fused": "electricity_kwh", "water_fused": "water_litres"}.get(a["metric"])
        if col:
            hb = hourly[hourly["building_id"] == a["building_id"]]
            day = hb[hb["date"] == a["date"]]
            prof = hb.groupby(hb["ts"].dt.hour)[col].median()
            if len(day):
                excess = (day.set_index(day["ts"].dt.hour)[col] - prof).clip(lower=0)
                shifts = {"night (22-06)": excess[(excess.index >= 22) | (excess.index < 6)].sum(),
                          "morning (06-12)": excess[(excess.index >= 6) & (excess.index < 12)].sum(),
                          "afternoon (12-17)": excess[(excess.index >= 12) & (excess.index < 17)].sum(),
                          "evening (17-22)": excess[(excess.index >= 17) & (excess.index < 22)].sum()}
                tot = sum(shifts.values())
                if tot > 0:
                    top = max(shifts, key=shifts.get)
                    share = shifts[top] / tot
                    shift_txt = f"{share:.0%} of excess occurred in the {top} shift"
                    if top.startswith("night") and share > 0.4 and a["deviation_pct"] > 0:
                        ev.append({"cause": "leak" if col == "water_litres" else "night_baseload", "score": 0.55, "text": shift_txt})
        # 5) data quality
        if not stuck.empty and ((stuck["building_id"] == a["building_id"]) & (stuck["date"] == a["date"])).any():
            ev.append({"cause": "sensor_fault", "score": 0.85, "text": "Water meter reported zero for 8+ consecutive hours"})
        if a["imputed_share"] > 0.15:
            ev.append({"cause": "data_gap", "score": 0.5, "text": f"{a['imputed_share']:.0%} of hours imputed (gateway offline)"})
        if a["conflict"]:
            ev.append({"cause": "sensor_fault", "score": 0.4, "text": "Meter, daily summary and manual log disagree by >25%"})
        if a["day_type"] in ("holiday", "weekend") and a["metric"] == "elec_fused" and a["deviation_pct"] > 0:
            ev.append({"cause": "behaviour", "score": 0.45, "text": f"Elevated usage on a {a['day_type']} (building should be idle)"})
        if not ev:
            ev.append({"cause": "unexplained_rise" if a["deviation_pct"] > 0 else "sensor_fault", "score": 0.25,
                       "text": "No corroborating event/note found; needs inspection"})

        # aggregate scores by cause (noisy-OR)
        agg = {}
        for e in ev:
            c = e["cause"] if e["cause"] != "building_specific" else None
            if c:
                agg[c] = 1 - (1 - agg.get(c, 0)) * (1 - max(0.05, min(0.95, e["score"])))
        if not agg:
            agg = {"unexplained_rise": 0.3}
        ranked = sorted(agg.items(), key=lambda kv: -kv[1])
        cause, conf = ranked[0]

        # impact
        excess = a["value"] - a["expected"]
        if a["metric"] == "elec_fused":
            kwh = max(excess, 0)
        elif a["metric"] == "water_fused":
            kwh = max(excess, 0) / 1000 * C.WATER_KWH_PER_KL
        elif a["metric"] == "solar_hourly":
            kwh = max(-excess, 0)
        else:
            kwh = 0
        rs = kwh * C.TARIFF_RS_PER_KWH
        co2 = kwh * C.CO2_KG_PER_KWH
        if a["metric"] in ("landfill_kg", "wet_organic_kg"):
            co2 += max(excess, 0) * 0.5  # ~0.5 kgCO2e/kg landfilled MSW (IPCC-style approx.)
        if cause in ("sensor_fault", "data_gap"):
            rs, co2 = 0.0, 0.0  # not real consumption
        out.append({**{k: (None if (isinstance(v, float) and not np.isfinite(v)) else v) for k, v in a.items()},
                    "metric_label": METRICS[a["metric"]]["label"], "unit": METRICS[a["metric"]]["unit"],
                    "cause": cause, "confidence": round(conf, 2),
                    "alternatives": [{"cause": c, "p": round(p, 2)} for c, p in ranked[1:3]],
                    "evidence": ev, "peer": peer_note, "shift": shift_txt,
                    "action": ACTIONS.get(cause, ACTIONS["unexplained_rise"]),
                    "impact_rs": round(rs, 0), "impact_co2_kg": round(co2, 1),
                    "priority": round(conf * (np.log1p(rs + 1) + abs(a["z"]) / 5), 3)})
    out.sort(key=lambda r: (-r["priority"]))
    return out


def validate_against_notes(attributed: list[dict], manual: pd.DataFrame) -> dict:
    """How many field-reported incidents did the system independently flag?
    (Notes are ground truth written by staff; detection uses telemetry only, notes only for attribution.)"""
    notes = manual[(manual["stream"] == "note") & manual["building_id"].notna()]
    res = []
    for _, n in notes.iterrows():
        d = n["logged_at"].normalize()
        hit = [a for a in attributed if a["building_id"] == n["building_id"]
               and abs((pd.Timestamp(a["date"]) - d).days) <= 3]
        res.append({"note": n["note"], "building_id": n["building_id"], "date": d.strftime("%Y-%m-%d"),
                    "detected": bool(hit), "matched": [f"{h['date']} {h['metric_label']} {h['deviation_pct']:+.0f}% -> {h['cause']}" for h in hit[:2]]})
    det = sum(r["detected"] for r in res)
    return {"incidents": len(res), "detected": det, "recall_pct": round(100 * det / max(len(res), 1), 1), "details": res}
