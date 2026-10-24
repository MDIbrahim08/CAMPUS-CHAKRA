"""Ingestion, reconciliation and multi-source fusion.

Handles the real-world noise documented in README §3 and §5:
  * out-of-order arrival (timestamp != received_at) and burst buffering
  * duplicate retransmissions with jitter -> deterministic dedup
  * packet loss (missing hours) and null sensor readings -> imputation with flags
  * manual logs with building aliases and mixed units -> normalisation
  * conflicting sources (hourly meter vs daily summary vs manual) -> confidence-weighted fusion

Every function is pure (DataFrame in -> DataFrame out) so the same code runs on
the provided dataset AND on any fresh evaluation data uploaded via the API.
"""
from __future__ import annotations

import difflib
import re

import numpy as np
import pandas as pd

from . import config as C

METERS = ["electricity_kwh", "water_litres", "solar_generation_kwh", "footfall"]


# ----------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------
def load_table(name: str, data_dir=None) -> pd.DataFrame:
    """Load `<name>.csv` if present, else `<name>.xlsx` (dataset ships both formats)."""
    d = data_dir or C.DATA_DIR
    cache = C.CACHE_DIR / f"{name}.csv"
    for cand in [d / f"{name}.csv", d / "excel_format" / f"{name}.xlsx", d / f"{name}.xlsx"]:
        if cand.exists():
            if cand.suffix == ".csv":
                return pd.read_csv(cand)
            if cache.exists() and cache.stat().st_mtime >= cand.stat().st_mtime:
                return pd.read_csv(cache)
            df = pd.read_excel(cand)
            df.to_csv(cache, index=False)
            return df
    raise FileNotFoundError(f"{name} not found in {d}")


def read_any(file_bytes: bytes, filename: str) -> pd.DataFrame:
    import io
    if filename.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(file_bytes))
    return pd.read_csv(io.BytesIO(file_bytes))


# ----------------------------------------------------------------------------
# Hourly telemetry: dedup + reorder + gap detection + imputation
# ----------------------------------------------------------------------------
def clean_hourly(raw: pd.DataFrame, calendar: pd.DataFrame | None = None):
    """Return (fused_hourly, integrity_report).

    fused_hourly has one row per (building_id, hour) for every building and
    every hour in range — offline buildings are never dropped, their gaps are
    imputed and flagged instead.
    """
    h = raw.copy()
    h["ts"] = pd.to_datetime(h["timestamp"]).dt.floor("h")
    h["rx"] = pd.to_datetime(h.get("received_at", h["timestamp"]))
    h["lag_h"] = (h["rx"] - h["ts"]).dt.total_seconds() / 3600.0
    n_raw = len(h)

    # 1) Deterministic dedup: idempotency key = (building_id, ts).
    #    Keep the FIRST received copy (original transmission); retransmissions
    #    arrive later with jitter. Tie-break on row order for determinism.
    h = h.sort_values(["building_id", "ts", "rx"], kind="mergesort")
    dup_mask = h.duplicated(["building_id", "ts"], keep="first")
    dups_per_b = h[dup_mask].groupby("building_id").size()
    h = h[~dup_mask]

    # 2) Burst-buffered (late) records: normal uplink lag ~1h; >2h = held in edge buffer.
    late_per_b = h[h["lag_h"] > 2].groupby("building_id").size()

    # 3) Full grid so offline buildings stay visible.
    buildings = sorted(h["building_id"].unique())
    hours = pd.date_range(h["ts"].min(), h["ts"].max(), freq="h")
    grid = pd.MultiIndex.from_product([buildings, hours], names=["building_id", "ts"]).to_frame(index=False)
    g = grid.merge(h[["building_id", "ts", "lag_h"] + [m for m in METERS if m in h]], on=["building_id", "ts"], how="left")
    g["status"] = np.where(g["lag_h"].isna(), "lost", np.where(g["lag_h"] > 2, "buffered", "live"))
    meters = [m for m in METERS if m in g]
    g["sensor_null"] = g[meters].isna().any(axis=1) & (g["status"] != "lost")

    # 4) Imputation: short gaps (<=2h) linear interpolation; longer gaps use the
    #    building's median profile for the same hour-of-day & weekday/weekend type.
    g["hour"] = g["ts"].dt.hour
    g["dow"] = g["ts"].dt.dayofweek
    g["wkend"] = (g["dow"] >= 5).astype(int)
    g["imputed"] = g[meters].isna().any(axis=1)
    out = []
    for b, gb in g.groupby("building_id", sort=False):
        gb = gb.sort_values("ts").copy()
        for m in meters:
            s = gb[m]
            interp = s.interpolate(limit=2, limit_area="inside")
            prof = gb.groupby(["hour", "wkend"])[m].transform("median")
            gb[m] = interp.fillna(prof).fillna(s.median())
        out.append(gb)
    g = pd.concat(out, ignore_index=True)

    report = []
    for b in buildings:
        gb = g[g["building_id"] == b]
        report.append({
            "building_id": b,
            "expected_hours": int(len(gb)),
            "live": int((gb["status"] == "live").sum()),
            "buffered_late": int(late_per_b.get(b, 0)),
            "lost_imputed": int((gb["status"] == "lost").sum()),
            "sensor_nulls_imputed": int(gb["sensor_null"].sum()),
            "duplicates_removed": int(dups_per_b.get(b, 0)),
            "completeness_pct": round(100 * (1 - gb["imputed"].mean()), 2),
            "max_buffer_h": round(float(gb["lag_h"].max()), 1) if gb["lag_h"].notna().any() else None,
        })
    summary = {
        "raw_rows": int(n_raw),
        "duplicates_removed": int(dup_mask.sum()),
        "late_buffered": int(late_per_b.sum()),
        "lost_hours": int((g["status"] == "lost").sum()),
        "null_readings": int(g["sensor_null"].sum()),
        "clean_rows": int(len(g)),
    }
    return g.drop(columns=["hour", "dow", "wkend"]), {"summary": summary, "buildings": report}


# ----------------------------------------------------------------------------
# Manual logs: alias resolution + unit normalisation
# ----------------------------------------------------------------------------
_ALIAS_LOOKUP = {a: b for b, al in C.BUILDING_ALIASES.items() for a in al}


def _norm_txt(s: str) -> str:
    s = str(s).lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


_NORM_LOOKUP = {_norm_txt(k): v for k, v in _ALIAS_LOOKUP.items()}


def resolve_building(name) -> tuple[str | None, str]:
    """Map a free-text building name to B01..B08. Returns (id, method)."""
    if pd.isna(name):
        return None, "missing"
    raw = str(name).strip()
    if re.fullmatch(r"[Bb]0?[1-8]", raw):
        return f"B0{raw[-1]}", "id"
    n = _norm_txt(raw)
    if n in _NORM_LOOKUP:
        return _NORM_LOOKUP[n], "alias"
    # token heuristics
    toks = set(n.split())
    if "lib" in n:
        return "B03", "keyword"
    if toks & {"boys", "boy"}:
        return "B05", "keyword"
    if toks & {"girls", "girl"}:
        return "B06", "keyword"
    if toks & {"lab", "labs", "innovation", "eng", "engineering"}:
        return "B04", "keyword"
    if toks & {"food", "mess", "canteen", "cafeteria"}:
        return "B07", "keyword"
    if "admin" in n:
        return "B08", "keyword"
    if toks & {"a"} and toks & {"block", "acad", "academic"}:
        return "B01", "keyword"
    if toks & {"b"} and toks & {"block", "acad", "academic"}:
        return "B02", "keyword"
    m = difflib.get_close_matches(n, list(_NORM_LOOKUP), n=1, cutoff=0.6)
    if m:
        return _NORM_LOOKUP[m[0]], "fuzzy"
    return None, "unresolved"


UNIT_FACTORS = {  # -> canonical unit per stream
    ("electricity", "kwh"): 1.0, ("electricity", "units"): 1.0,
    ("water", "l"): 1.0, ("water", "kl"): 1000.0,
    ("waste", "kg"): 1.0, ("waste", "bags"): C.KG_PER_BAG,
}
CANON_UNIT = {"electricity": "kWh", "water": "L", "waste": "kg"}


def normalise_manual_logs(raw: pd.DataFrame) -> pd.DataFrame:
    ml = raw.copy()
    res = ml["building"].apply(resolve_building)
    ml["building_id"] = res.str[0]
    ml["resolve_method"] = res.str[1]
    ml["logged_at"] = pd.to_datetime(ml["logged_at"])
    ml["date"] = ml["logged_at"].dt.strftime("%Y-%m-%d")
    f = [UNIT_FACTORS.get((str(s).lower(), str(u).lower()), np.nan) for s, u in zip(ml["stream"], ml["unit"])]
    ml["value_canonical"] = ml["value"] * np.array(f, dtype=float)
    ml["canonical_unit"] = ml["stream"].map(CANON_UNIT)
    return ml


# ----------------------------------------------------------------------------
# Daily fusion: hourly meters + daily summary + manual logs
# ----------------------------------------------------------------------------
def fuse_daily(hourly: pd.DataFrame, daily: pd.DataFrame, manual: pd.DataFrame, buildings: pd.DataFrame):
    """Confidence-weighted daily fusion with explicit conflict flags.

    Priority/weights: hourly meter aggregate (high-rate, automated) w=0.5,
    daily summary (BMS roll-up) w=0.35, manual log (human, noisy) w=0.15.
    If a source is missing it is skipped and the weights renormalised — so a
    building that went offline still gets a fused value with lower confidence.
    """
    hd = hourly.assign(date=hourly["ts"].dt.strftime("%Y-%m-%d"))
    agg = hd.groupby(["building_id", "date"]).agg(
        e_hourly=("electricity_kwh", "sum"), w_hourly=("water_litres", "sum"),
        solar_hourly=("solar_generation_kwh", "sum"), footfall=("footfall", "sum"),
        imputed_share=("imputed", "mean"),
    ).reset_index()
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"]).dt.strftime("%Y-%m-%d")
    m = d.merge(agg, on=["building_id", "date"], how="outer")

    man = manual[manual["stream"].isin(["electricity", "water", "waste"]) & manual["building_id"].notna()]
    man_p = man.pivot_table(index=["building_id", "date"], columns="stream", values="value_canonical", aggfunc="mean").reset_index()
    man_p = man_p.rename(columns={"electricity": "e_manual", "water": "w_manual", "waste": "waste_manual"})
    m = m.merge(man_p, on=["building_id", "date"], how="left")

    def fuse(row, hcol, dcol, mcol):
        vals, wts = [], []
        # hourly confidence decays with imputed share
        if pd.notna(row.get(hcol)):
            vals.append(row[hcol]); wts.append(0.5 * (1 - 0.7 * (row.get("imputed_share") or 0)))
        if pd.notna(row.get(dcol)):
            vals.append(row[dcol]); wts.append(0.35)
        if mcol and pd.notna(row.get(mcol)):
            vals.append(row[mcol]); wts.append(0.15)
        if not vals:
            return np.nan, 0.0, False
        vals, wts = np.array(vals), np.array(wts)
        med = np.median(vals)
        keep = np.abs(vals - med) <= 0.25 * max(med, 1e-6)
        conflict = bool((~keep).any())
        if not vals.size or not keep.any() or wts[keep].sum() <= 0:
            v = float(np.mean(vals)) if vals.size else np.nan
            return v, 0.2, True
        v = float(np.average(vals[keep], weights=wts[keep]))
        conf = float(min(1.0, wts[keep].sum() / 0.85))
        return v, round(conf, 2), conflict

    rows = []
    for _, r in m.iterrows():
        e, ce, xe = fuse(r, "e_hourly", "electricity_kwh", "e_manual")
        w, cw, xw = fuse(r, "w_hourly", "water_litres", "w_manual")
        rows.append((e, ce, xe, w, cw, xw))
    m[["elec_fused", "elec_conf", "elec_conflict", "water_fused", "water_conf", "water_conflict"]] = pd.DataFrame(rows, index=m.index)

    waste_cols = ["wet_organic_kg", "dry_recyclable_kg", "ewaste_kg", "hazardous_kg"]
    # Fill missing wet organic via building-level median ratio to occupancy
    m["occupancy_avg"] = m.groupby("building_id")["occupancy_avg"].transform(lambda s: s.interpolate().bfill().ffill())
    for c in waste_cols:
        if c in m:
            m[c] = m.groupby("building_id")[c].transform(lambda s: s.interpolate(limit_direction="both"))
    m["total_waste_kg"] = m[[c for c in waste_cols if c in m]].sum(axis=1)
    m["diverted_kg"] = m.get("composted_kg", 0).fillna(0) + m.get("recycled_kg", 0).fillna(0)
    m["diversion_pct"] = 100 * m["diverted_kg"] / m["total_waste_kg"].replace(0, np.nan)
    m = m.merge(buildings[["building_id", "building_name", "building_type", "design_capacity", "area_sqm"]], on="building_id", how="left")
    m["elec_per_capita"] = m["elec_fused"] / m["occupancy_avg"].clip(lower=1)
    m["water_per_capita"] = m["water_fused"] / m["occupancy_avg"].clip(lower=1)
    return m.sort_values(["date", "building_id"]).reset_index(drop=True)
