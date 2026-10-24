"""Behavioural + economic incentive loop: Eco-Credits leaderboard.

Fairness: every building competes against ITS OWN normalised baseline, not
against other buildings (a hostel can't be compared to an admin block).

  intensity = consumption / occupancy           (per-capita normalisation)
  baseline  = median weekly intensity over the first 4 'on-semester' weeks
  reduction = 1 - this_week / baseline           (per stream)
  score     = 40% electricity + 30% water + 30% waste-diversion improvement
  credits   = clip(100 * score, -50, +150) + segregation bonus (contamination < 10%)

Impact measurement (difference-in-differences): compare pre/post change in
intensity for buildings with the nudge vs a hold-out control group, controlling
for day-type and temperature. Here we report weekly trend vs baseline.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def leaderboard(fused: pd.DataFrame, calendar: pd.DataFrame) -> dict:
    cal = calendar.copy(); cal["date"] = pd.to_datetime(cal["date"]).dt.strftime("%Y-%m-%d")
    df = fused.merge(cal[["date", "day_type"]], on="date", how="left")
    df = df[df["day_type"].isin(["working", "exam", "weekend", "holiday"])].copy()  # semester only
    df["week"] = pd.to_datetime(df["date"]).dt.to_period("W-SUN").dt.start_time.dt.strftime("%Y-%m-%d")
    df["occ"] = df["occupancy_avg"].clip(lower=1)
    w = df.groupby(["building_id", "building_name", "building_type", "week"]).agg(
        elec=("elec_fused", "sum"), water=("water_fused", "sum"), occ=("occ", "mean"),
        landfill=("landfill_kg", "sum"), waste=("total_waste_kg", "sum"),
        contamination=("contamination_pct", "mean"), days=("date", "count")).reset_index()
    w = w[w["days"] >= 5]
    w["e_int"] = w["elec"] / w["occ"] / w["days"]
    w["w_int"] = w["water"] / w["occ"] / w["days"]
    w["landfill_share"] = w["landfill"] / w["waste"].replace(0, np.nan)
    weeks = sorted(w["week"].unique())
    base_weeks = weeks[:4]
    rows = []
    for b, g in w.groupby("building_id"):
        base = g[g["week"].isin(base_weeks)]
        be, bw, bl = base["e_int"].median(), base["w_int"].median(), base["landfill_share"].median()
        for _, r in g.iterrows():
            re_ = 1 - r["e_int"] / be if be else 0
            rw = 1 - r["w_int"] / bw if bw else 0
            rl = 1 - r["landfill_share"] / bl if bl and pd.notna(r["landfill_share"]) else 0
            score = 0.4 * re_ + 0.3 * rw + 0.3 * rl
            bonus = 20 if pd.notna(r["contamination"]) and r["contamination"] < 10 else 0
            credits = float(np.clip(100 * score, -50, 150) + bonus)
            rows.append({"building_id": b, "building_name": r["building_name"], "building_type": r["building_type"],
                         "week": r["week"], "elec_change_pct": round(-re_ * 100, 1), "water_change_pct": round(-rw * 100, 1),
                         "landfill_change_pct": round(-rl * 100, 1), "contamination_pct": round(float(r["contamination"]), 1) if pd.notna(r["contamination"]) else None,
                         "credits": round(credits, 1), "baseline": r["week"] in base_weeks})
    lb = pd.DataFrame(rows)
    last = lb[lb["week"] == lb["week"].max()].sort_values("credits", ascending=False)
    cum = lb[~lb["baseline"]].groupby(["building_id", "building_name"])["credits"].sum().reset_index().sort_values("credits", ascending=False)
    badges = []
    for _, r in last.iterrows():
        bdg = []
        if r["elec_change_pct"] < -5: bdg.append("⚡ Power Saver")
        if r["water_change_pct"] < -5: bdg.append("💧 Water Guardian")
        if r["landfill_change_pct"] < -5: bdg.append("♻️ Zero-Waste Hero")
        if r["contamination_pct"] is not None and r["contamination_pct"] < 10: bdg.append("🎯 Clean Sorter")
        badges.append(bdg)
    last = last.assign(badges=badges)
    return {"latest_week": lb["week"].max(), "baseline_weeks": base_weeks,
            "latest": last.to_dict("records"), "cumulative": cum.to_dict("records"),
            "history": lb.to_dict("records")}
