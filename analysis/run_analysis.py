#!/usr/bin/env python3
"""
Data analysis: join checkins with environment_daily and run EDA.

Prerequisites:
  1. MongoDB has checkins (userId, date, rescueUsed?, symptomScore?) and
     environment_daily (locationKey, date, air_quality, weather, pollen, time_context).
  2. Ingest TIDAL data: python ingest_to_mongodb.py --lat ... --lon ... --start ... --end ...
  3. Checkins should include a "date" field (YYYY-MM-DD) for joining. If your API
     stores one doc per user, consider changing to userId+date so you keep history.

Usage (from TIDAL2026):
  python -m analysis.run_analysis
  python -m analysis.run_analysis --location-key "37.77_-122.42"
  python -m analysis.run_analysis --out analysis_summary.txt
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Run from TIDAL2026 repo root so data_sources and pull_by_location_date are importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

import pandas as pd
from pymongo import MongoClient


def _flatten_env(doc: dict) -> dict:
    """Turn one environment_daily doc into flat numeric/categorical fields for analysis."""
    out = {"date": doc.get("date"), "locationKey": doc.get("locationKey")}
    aq = doc.get("air_quality") or {}
    out["pm25_mean"] = aq.get("pm25_mean")
    out["pm25_max"] = aq.get("pm25_max")
    out["aqi"] = aq.get("aqi")
    out["aqi_24h_trend"] = aq.get("aqi_24h_trend")

    w = doc.get("weather") or {}
    out["temp_min_c"] = w.get("temp_min_c")
    out["temp_max_c"] = w.get("temp_max_c")
    out["humidity_mean"] = w.get("humidity_mean")
    out["humidity_max"] = w.get("humidity_max")
    out["wind_speed_kmh"] = w.get("wind_speed_kmh")
    out["pressure_pa"] = w.get("pressure_pa")
    out["rain_mm"] = w.get("rain_mm")

    p = doc.get("pollen") or {}
    out["tree_index"] = p.get("tree_index")
    out["grass_index"] = p.get("grass_index")
    out["weed_index"] = p.get("weed_index")

    tc = doc.get("time_context") or {}
    out["day_of_week_num"] = tc.get("day_of_week_num")
    out["season"] = tc.get("season")
    out["is_holiday"] = tc.get("is_holiday")
    return out


def _checkin_row(doc: dict) -> dict | None:
    """One checkin doc -> row with date for joining. Use date or updatedAt date."""
    date_val = doc.get("date")
    if not date_val and doc.get("updatedAt"):
        date_val = doc["updatedAt"].strftime("%Y-%m-%d") if hasattr(doc["updatedAt"], "strftime") else None
    if not date_val:
        return None
    return {
        "date": date_val,
        "userId": doc.get("userId"),
        "rescueUsed": bool(doc.get("rescueUsed", False)),
        "symptomScore": float(doc.get("symptomScore", 0)),
    }


def load_merged(db, location_key: str | None) -> pd.DataFrame:
    """Load checkins and environment_daily from MongoDB and merge by date."""
    checkins = list(db.checkins.find({}))
    env = list(db.environment_daily.find({}))
    if location_key:
        env = [e for e in env if e.get("locationKey") == location_key]

    rows_c = [_checkin_row(c) for c in checkins]
    rows_c = [r for r in rows_c if r is not None]
    df_c = pd.DataFrame(rows_c)
    if df_c.empty:
        return pd.DataFrame()

    rows_e = [_flatten_env(e) for e in env]
    df_e = pd.DataFrame(rows_e)
    if df_e.empty:
        return df_c

    # Merge: for each checkin date we get that day's env (any location or chosen one)
    merged = df_c.merge(
        df_e.drop(columns=["locationKey"], errors="ignore"),
        on="date",
        how="left",
        suffixes=("", "_env"),
    )
    return merged


def run_eda(merged: pd.DataFrame, out_path: str | None) -> str:
    """Run EDA and return a text summary."""
    lines = []
    lines.append("=" * 60)
    lines.append("Allergy Predictor – data analysis summary")
    lines.append("=" * 60)
    lines.append("")

    if merged.empty:
        lines.append("No data: ensure checkins and environment_daily have documents.")
        return "\n".join(lines)

    n = len(merged)
    lines.append(f"Rows (checkin–env join): {n}")
    lines.append("")

    # Outcome columns
    if "rescueUsed" in merged.columns:
        lines.append("Outcome: rescueUsed")
        lines.append(merged["rescueUsed"].value_counts().to_string())
        lines.append("")
    if "symptomScore" in merged.columns:
        lines.append("Outcome: symptomScore")
        lines.append(merged["symptomScore"].describe().to_string())
        lines.append("")

    # Missingness
    lines.append("Missingness (count per column):")
    miss = merged.isnull().sum()
    for col in miss.index:
        if miss[col] > 0:
            lines.append(f"  {col}: {miss[col]}")
    lines.append("")

    # Numeric columns: correlations with outcomes
    numeric = merged.select_dtypes(include=["number"]).columns.tolist()
    outcome_cols = [c for c in ["rescueUsed", "symptomScore"] if c in merged.columns]
    for target in outcome_cols:
        if target not in numeric:
            continue
        others = [c for c in numeric if c != target]
        if not others:
            continue
        lines.append(f"Correlations with {target}:")
        try:
            corr = merged[others + [target]].corr()[target].drop(target, errors="ignore")
            for c in corr.abs().sort_values(ascending=False).index:
                lines.append(f"  {c}: {corr[c]:.3f}")
        except Exception as e:
            lines.append(f"  (error: {e})")
        lines.append("")

    summary = "\n".join(lines)
    if out_path:
        Path(out_path).write_text(summary, encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Run data analysis (checkins + environment)")
    parser.add_argument("--location-key", type=str, help="Filter environment_daily by this locationKey")
    parser.add_argument("--out", type=str, help="Write summary to this file")
    parser.add_argument("--db", type=str, default="asthma", help="MongoDB database name")
    args = parser.parse_args()

    uri = os.environ.get("MONGODB_URI")
    if not uri:
        print("Set MONGODB_URI in .env")
        return 1

    client = MongoClient(uri)
    db = client[args.db]
    merged = load_merged(db, args.location_key)
    summary = run_eda(merged, args.out)
    print(summary)
    return 0


if __name__ == "__main__":
    exit(main() or 0)
