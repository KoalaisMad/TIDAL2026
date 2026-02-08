#!/usr/bin/env python3
"""
Flare model test on week data.

Uses a fixed week of daily rows in the schema:
  _id, locationid, latitude, longitude, zip_code, date,
  PM2_5_mean, PM2_5_max, AQI, temp_min, temp_max, humidity, wind, pressure, rain,
  pollen_tree, pollen_grass, pollen_weed, day_of_week, month, season, holiday_flag

Runs the D A T A flare_model.joblib on this week and prints predictions.

Usage (from TIDAL2026):
  PYTHONPATH=asthma-forecaster python -m apps.ml.test_flare_week
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

# Bootstrap paths and .env
def _bootstrap():
    try:
        from dotenv import load_dotenv
        root = Path(__file__).resolve().parent.parent.parent.parent
        for p in [root / ".env", Path.cwd() / ".env"]:
            if p.exists():
                load_dotenv(p)
                break
    except ImportError:
        pass
    tidal = Path(__file__).resolve().parent.parent.parent.parent
    if str(tidal) not in sys.path:
        sys.path.insert(0, str(tidal))
    if str(tidal / "asthma-forecaster") not in sys.path:
        sys.path.insert(0, str(tidal / "asthma-forecaster"))


_bootstrap()

import pandas as pd
import joblib

# Reuse predict_flare helpers
from apps.ml.predict_flare import (
    _flare_model_path,
    _predict_one_date,
)


def build_week_data() -> pd.DataFrame:
    """
    Build 7 days of test data in the user/flare schema.
    Day 1 matches the user example; days 2–7 use same env with updated date/day_of_week.
    """
    base = {
        "_id": "6987c86347afdb193af564f4",
        "locationid": "37.77-122.42",
        "latitude": 37.77,
        "longitude": -122.42,
        "zip_code": None,
        "PM2_5_mean": 13.78,
        "PM2_5_max": 101.3,
        "AQI": 53,
        "temp_min": -11.91,
        "temp_max": -8.21,
        "humidity": 84.12,
        "wind": 11.92,
        "pressure": 102350,
        "rain": 0,
        "pollen_tree": None,
        "pollen_grass": None,
        "pollen_weed": None,
        "holiday_flag": False,
    }
    start = date(2026, 2, 7)
    rows = []
    for i in range(7):
        d = start + timedelta(days=i)
        row = dict(base)
        row["date"] = d.isoformat()
        row["day_of_week"] = d.strftime("%A")
        row["month"] = d.month
        if d.month in (12, 1, 2):
            row["season"] = "winter"
        elif d.month in (3, 4, 5):
            row["season"] = "spring"
        elif d.month in (6, 7, 8):
            row["season"] = "summer"
        else:
            row["season"] = "fall"
        rows.append(row)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["location_id"] = df["locationid"].str.replace("-", "_", n=1)
    # Fill NaN numeric cols for model
    for col in ["pollen_tree", "pollen_grass", "pollen_weed"]:
        if col in df.columns and df[col].dtype in ("float64", "int64", "object"):
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def main() -> int:
    bundle_path = _flare_model_path()
    if not bundle_path or not bundle_path.exists():
        print("Flare model not found (D A T A/flare_model.joblib)", file=sys.stderr)
        return 1
    bundle = joblib.load(bundle_path)
    if not bundle.get("model") or not bundle.get("feature_order"):
        print("Invalid flare model bundle", file=sys.stderr)
        return 1

    raw = build_week_data()
    start_str = "2026-02-07"
    days = 7
    results = []
    for i in range(days):
        d = date(2026, 2, 7) + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        out = _predict_one_date(date_str, raw, bundle, None)
        results.append(out)

    print("Flare model test on week data (2026-02-07 .. 2026-02-13)")
    print("-" * 60)
    for r in results:
        risk = r.get("risk", {})
        print(f"  {r['date']}: score={risk.get('score')} level={risk.get('level')} label={risk.get('label')}")
    print("-" * 60)
    print(json.dumps({"start": start_str, "days": results}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
