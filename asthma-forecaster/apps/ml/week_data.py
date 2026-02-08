#!/usr/bin/env python3
"""
Fetch a week of daily environmental data using API keys (AirNow, PurpleAir, NOAA, etc.)
and return rows in the flare-model schema:

  _id, locationid, latitude, longitude, zip_code, date,
  PM2_5_mean, PM2_5_max, AQI, temp_min, temp_max, humidity, wind, pressure, rain,
  pollen_tree, pollen_grass, pollen_weed, day_of_week, month, season, holiday_flag

Usage (from TIDAL2026):
  PYTHONPATH=asthma-forecaster python -m apps.ml.week_data --lat 37.77 --lon -122.42 --start 2026-02-07 --days 7
  PYTHONPATH=asthma-forecaster python -m apps.ml.week_data --lat 37.77 --lon -122.42 --start 2026-02-07 --days 7 --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Bootstrap .env and path
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

# Pull uses asthma-forecaster apps
from pull_by_location_date import pull_all
from apps.db.daily_dataset import pull_result_to_daily_row, location_id as _loc_id


def _season_string(month: int) -> str:
    """Return season name for flare schema (winter, spring, summer, fall)."""
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "fall"


def pull_result_to_week_row(pull_result: dict, *, row_id: str | None = None) -> dict:
    """
    Convert one pull_all() result into one row matching the user/flare schema:
    locationid "lat-lon", date "YYYY-MM-DD", day_of_week "Saturday", season "winter", etc.
    """
    row = pull_result_to_daily_row(pull_result)
    loc = pull_result.get("location") or {}
    lat = loc.get("latitude")
    lon = loc.get("longitude")
    zip_code = loc.get("zip_code")
    target_date_str = pull_result.get("date") or ""
    try:
        d = date.fromisoformat(target_date_str)
        month = d.month
        day_of_week_str = d.strftime("%A")  # Monday, Tuesday, ...
    except (TypeError, ValueError):
        month = None
        day_of_week_str = None

    # locationid format "37.77-122.42" (single dash) for API/flare schema
    lid = row.get("location_id") or _loc_id(lat, lon, zip_code)
    locationid_dash = (lid.replace("_", "") if isinstance(lid, str) else f"{lat or ''}{lon or ''}").replace(" ", "")

    out = {
        "locationid": locationid_dash,
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "zip_code": row.get("zip_code"),
        "date": target_date_str,
        "PM2_5_mean": row.get("PM2_5_mean"),
        "PM2_5_max": row.get("PM2_5_max"),
        "AQI": row.get("AQI"),
        "temp_min": row.get("temp_min"),
        "temp_max": row.get("temp_max"),
        "humidity": row.get("humidity"),
        "wind": row.get("wind"),
        "pressure": row.get("pressure"),
        "rain": row.get("rain"),
        "pollen_tree": row.get("pollen_tree"),
        "pollen_grass": row.get("pollen_grass"),
        "pollen_weed": row.get("pollen_weed"),
        "day_of_week": day_of_week_str or (row.get("day_of_week") if isinstance(row.get("day_of_week"), str) else None),
        "month": month or row.get("month"),
        "season": _season_string(month) if month else (row.get("season") if isinstance(row.get("season"), str) else "winter"),
        "holiday_flag": bool(row.get("holiday_flag", False)),
    }
    if row_id is not None:
        out["_id"] = row_id
    return out


def fetch_week_data(
    *,
    latitude: float,
    longitude: float,
    start_date: date,
    days: int = 7,
    zip_code: str | None = None,
    include_raw: bool = False,
) -> list[dict]:
    """
    Fetch `days` days of data starting at `start_date` using API keys (pull_all per day).
    Returns a list of dicts in the flare schema (locationid, date, PM2_5_mean, etc.).
    """
    rows = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        result = pull_all(
            latitude=latitude,
            longitude=longitude,
            zip_code=zip_code,
            target_date=d,
            include_raw=include_raw,
        )
        row = pull_result_to_week_row(result)
        rows.append(row)
    return rows


def fetch_week_dataframe(
    *,
    latitude: float,
    longitude: float,
    start_date: date,
    days: int = 7,
    zip_code: str | None = None,
) -> pd.DataFrame:
    """Fetch week data and return a pandas DataFrame (for flare model input)."""
    rows = fetch_week_data(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        days=days,
        zip_code=zip_code,
    )
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    # Alias for predict_flare (accepts location_id or locationid)
    if "locationid" in df.columns and "location_id" not in df.columns:
        df["location_id"] = df["locationid"].str.replace("-", "_", n=1)
    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch a week of env data using API keys; output flare schema")
    parser.add_argument("--lat", type=float, required=True, help="Latitude")
    parser.add_argument("--lon", type=float, required=True, help="Longitude")
    parser.add_argument("--start", type=str, required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=7, help="Number of days (default 7)")
    parser.add_argument("--zip", dest="zip_code", type=str, default=None, help="ZIP code (optional)")
    parser.add_argument("--json", action="store_true", help="Print JSON array to stdout")
    args = parser.parse_args()

    try:
        start_date = date.fromisoformat(args.start.strip())
    except ValueError:
        print(json.dumps({"error": "Invalid --start; use YYYY-MM-DD"}), file=sys.stderr)
        sys.exit(1)

    days = max(1, min(args.days, 14))
    rows = fetch_week_data(
        latitude=args.lat,
        longitude=args.lon,
        start_date=start_date,
        days=days,
        zip_code=args.zip_code,
    )
    if args.json:
        # Strip non-JSON types for clean output
        out = []
        for r in rows:
            o = dict(r)
            if "date" in o and hasattr(o["date"], "isoformat"):
                o["date"] = o["date"].isoformat()[:10] if hasattr(o["date"], "date") else str(o["date"])[:10]
            out.append(o)
        print(json.dumps(out, indent=2))
    else:
        df = pd.DataFrame(rows)
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
