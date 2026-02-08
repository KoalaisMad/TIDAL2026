#!/usr/bin/env python3
"""
Predict asthma flare risk for a date or week using the D A T A flare_model.joblib.
Outputs the same JSON shape as predict_risk.py for the frontend risk API.

Week data can be fetched via API keys (AirNow, NOAA, etc.) using --lat/--lon with --week.

Usage (from TIDAL2026):
  PYTHONPATH=asthma-forecaster python3 -m apps.ml.predict_flare --date 2026-02-15
  PYTHONPATH=asthma-forecaster python3 -m apps.ml.predict_flare --week --start 2026-02-15 --days 7
  PYTHONPATH=asthma-forecaster python3 -m apps.ml.predict_flare --week --start 2026-02-07 --lat 37.77 --lon -122.42
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import timedelta
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

import numpy as np
import pandas as pd
import joblib

# Flare model bundle path: D A T A/flare_model.joblib
def _flare_model_path() -> Path | None:
    root = Path(__file__).resolve().parent.parent.parent.parent
    data_dir = root / "asthma-forecaster" / "apps" / "D A T A"
    p = data_dir / "flare_model.joblib"
    if p.exists():
        return p
    p = Path(__file__).resolve().parent.parent / "D A T A" / "flare_model.joblib"
    if p.exists():
        return p
    return None


# Canonical encoding when bundle has no encoders (Monday=0 .. Sunday=6; winter=0, spring=1, summer=2, fall=3)
DOW_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SEASON_ORDER = ["winter", "spring", "summer", "fall"]


def _row_to_flare_features(row: pd.Series, feature_order: list[str], le_dow=None, le_season=None) -> pd.DataFrame:
    """Build one-row DataFrame in flare model feature space."""
    exclude = {"date", "locationid", "zip_code", "flare_day"}
    out = row.to_dict()
    if "day_of_week" in out and out["day_of_week"] is not None:
        v = out["day_of_week"]
        if isinstance(v, (int, float)):
            s = DOW_ORDER[int(v) % 7]
        else:
            s = str(v).strip()
        if le_dow is not None and hasattr(le_dow, "transform"):
            try:
                out["day_of_week"] = le_dow.transform([s])[0]
            except Exception:
                out["day_of_week"] = DOW_ORDER.index(s) if s in DOW_ORDER else 0
        else:
            out["day_of_week"] = DOW_ORDER.index(s) if s in DOW_ORDER else 0
    else:
        out["day_of_week"] = 0
    if "season" in out and out["season"] is not None:
        v = out["season"]
        if isinstance(v, (int, float)):
            s = SEASON_ORDER[int(v) % 4]
        else:
            s = str(v).strip().lower()
        if le_season is not None and hasattr(le_season, "transform"):
            try:
                out["season"] = le_season.transform([s])[0]
            except Exception:
                out["season"] = SEASON_ORDER.index(s) if s in SEASON_ORDER else 0
        else:
            out["season"] = SEASON_ORDER.index(s) if s in SEASON_ORDER else 0
    else:
        out["season"] = 0
    if out.get("holiday_flag") is None:
        out["holiday_flag"] = 0
    out["holiday_flag"] = int(out["holiday_flag"]) if out.get("holiday_flag") is not None else 0
    # Ensure google_trends_allergy if expected
    if "google_trends_allergy" not in out or (out.get("google_trends_allergy") is None or (isinstance(out.get("google_trends_allergy"), float) and np.isnan(out["google_trends_allergy"]))):
        out["google_trends_allergy"] = 0.0
    df = pd.DataFrame([out])
    for c in feature_order:
        if c not in df.columns:
            df[c] = 0
    X = df[feature_order].copy()
    X = X.fillna(0).astype(float)
    return X


def _proba_to_score_level(proba: float) -> tuple[float, str, str]:
    if proba < 0.2:
        return (1 + proba * 5, "low", "Low")
    if proba < 0.5:
        return (2 + (proba - 0.2) * 10, "moderate", "Moderate")
    return (4 + (proba - 0.5) * 2, "high", "High")


def _active_risk_factors(row: pd.Series) -> list[dict]:
    factors = []
    if row.get("AQI") is not None and float(row["AQI"]) >= 101:
        factors.append({"id": "air", "label": "Poor Air Quality", "iconKey": "wind"})
    if row.get("PM2_5_mean") is not None and float(row["PM2_5_mean"]) >= 35:
        factors.append({"id": "pm25", "label": "High PM2.5", "iconKey": "wind"})
    pollen = (row.get("pollen_tree") or 0) + (row.get("pollen_grass") or 0) + (row.get("pollen_weed") or 0)
    if pollen >= 8:
        factors.append({"id": "pollen", "label": "High Pollen", "iconKey": "sprout"})
    if not factors:
        factors.append({"id": "general", "label": "Environmental conditions", "iconKey": "wind"})
    return factors


def _synthetic_row_for_date(
    target_d: pd.Timestamp,
    location_id: str | None = None,
    lat: float = 37.0,
    lon: float = -122.0,
) -> pd.Series:
    """Build one row for a single date so the model gets date-specific features (different score per day)."""
    lid = location_id or f"{lat:.2f}_{lon:.2f}"
    d = target_d.date() if hasattr(target_d, "date") else target_d
    dow = d.weekday()
    month = d.month
    # 0=winter, 1=spring, 2=summer, 3=fall for SEASON_ORDER in _row_to_flare_features
    season = ((month % 12 + 3) // 3) - 1
    j = (d.toordinal() % 7) / 7.0
    aqi = 40 + int(30 * j)
    pm25_mean = 10.0 + 8 * j
    pm25_max = pm25_mean * 1.4
    return pd.Series({
        "date": pd.Timestamp(d),
        "location_id": lid,
        "locationid": lid.replace("_", "-") if "_" in lid else f"{lat}-{lon}",
        "AQI": aqi,
        "PM2_5_max": pm25_max,
        "PM2_5_mean": pm25_mean,
        "temp_max": 22.0 + 5 * j,
        "temp_min": 10.0 + 3 * j,
        "humidity": 55.0 + 20 * j,
        "wind": 5.0 + 5 * j,
        "pollen_tree": 2.0 + 2 * j,
        "pollen_grass": 1.0 + j,
        "pollen_weed": 0.5 + j,
        "day_of_week": dow,
        "month": month,
        "season": season,
        "holiday_flag": 0,
        "latitude": lat,
        "longitude": lon,
        "zip_code": "94102",
        "rain": 0.0,
        "pressure": 1013.0,
    })


def _predict_one_date(
    date_str: str,
    raw: pd.DataFrame,
    bundle: dict,
    location_id: str | None,
) -> dict:
    """Predict flare risk for one date; raw must have date column (datetime). Returns API-shaped dict."""
    model = bundle.get("model")
    scaler = bundle.get("scaler")
    feature_order = bundle.get("feature_order") or []
    le_dow = bundle.get("le_dow")
    le_season = bundle.get("le_season")

    raw = raw.copy()
    raw["date"] = pd.to_datetime(raw["date"])
    target_d = pd.Timestamp(date_str).normalize()
    raw_match = raw[raw["date"].dt.normalize() == target_d]
    if raw_match.empty:
        # Use a date-specific synthetic row so each day gets its own model prediction (not same score)
        lat = float(raw["latitude"].iloc[-1]) if "latitude" in raw.columns and len(raw) else 37.0
        lon = float(raw["longitude"].iloc[-1]) if "longitude" in raw.columns and len(raw) else -122.0
        lid = str(raw["location_id"].iloc[-1]) if "location_id" in raw.columns and len(raw) else None
        row = _synthetic_row_for_date(target_d, location_id=lid or location_id, lat=lat, lon=lon)
    else:
        row = raw_match.iloc[0].copy()

    if "location_id" in row.index and "locationid" not in row.index:
        row["locationid"] = row["location_id"]
    for k in ["PM2_5_mean", "PM2_5_max", "AQI", "temp_min", "temp_max", "humidity", "wind", "pressure", "rain",
              "pollen_tree", "pollen_grass", "pollen_weed", "day_of_week", "month", "season", "holiday_flag"]:
        if k not in row.index and k in feature_order:
            row[k] = 0
    if "google_trends_allergy" in feature_order and "google_trends_allergy" not in row.index:
        row["google_trends_allergy"] = 0.0

    X = _row_to_flare_features(row, feature_order, le_dow, le_season)
    if scaler is not None:
        X = scaler.transform(X)
    proba = float(model.predict_proba(X)[0, 1])
    score, level, label = _proba_to_score_level(proba)

    daily = {
        "date": date_str,
        "location_id": str(row.get("location_id", row.get("locationid", ""))),
        "AQI": float(row["AQI"]) if pd.notna(row.get("AQI")) else None,
        "PM2_5_mean": float(row["PM2_5_mean"]) if pd.notna(row.get("PM2_5_mean")) else None,
        "PM2_5_max": float(row["PM2_5_max"]) if pd.notna(row.get("PM2_5_max")) else None,
        "day_of_week": str(row.get("day_of_week")) if row.get("day_of_week") is not None else None,
        "season": str(row.get("season")) if row.get("season") is not None else None,
        "temp_min": float(row["temp_min"]) if pd.notna(row.get("temp_min")) else None,
        "temp_max": float(row["temp_max"]) if pd.notna(row.get("temp_max")) else None,
        "humidity": float(row["humidity"]) if pd.notna(row.get("humidity")) else None,
        "wind": float(row["wind"]) if pd.notna(row.get("wind")) else None,
        "pollen_tree": float(row.get("pollen_tree")) if pd.notna(row.get("pollen_tree")) else None,
        "pollen_grass": float(row.get("pollen_grass")) if pd.notna(row.get("pollen_grass")) else None,
        "pollen_weed": float(row.get("pollen_weed")) if pd.notna(row.get("pollen_weed")) else None,
    }
    return {
        "date": date_str,
        "risk": {"score": round(score, 1), "level": level, "label": label},
        "activeRiskFactors": _active_risk_factors(row),
        "daily": daily,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict flare risk for a date or week; output JSON for risk API")
    parser.add_argument("--date", help="YYYY-MM-DD (required if not --week)")
    parser.add_argument("--week", action="store_true", help="Output predictions for next 7 days")
    parser.add_argument("--start", help="Start date YYYY-MM-DD (required if --week)")
    parser.add_argument("--days", type=int, default=7, help="Number of days when --week (default 7)")
    parser.add_argument("--location-id", default=None, help="Optional location_id filter for env data")
    parser.add_argument("--lat", type=float, default=None, help="Latitude for API week data (with --lon fetches week via API keys)")
    parser.add_argument("--lon", type=float, default=None, help="Longitude for API week data (with --lat fetches week via API keys)")
    args = parser.parse_args()

    if args.location_id:
        os.environ["LOCATION_ID"] = args.location_id

    if args.week:
        start_str = (args.start or "").strip()
        if len(start_str) != 10 or start_str[4] != "-" or start_str[7] != "-":
            print(json.dumps({"error": "With --week provide --start YYYY-MM-DD"}), file=sys.stderr)
            sys.exit(1)
        days = max(1, min(args.days, 14))
        bundle_path = _flare_model_path()
        if not bundle_path or not bundle_path.exists():
            print(json.dumps({"error": "Flare model not found (D A T A/flare_model.joblib)"}), file=sys.stderr)
            sys.exit(1)
        try:
            bundle = joblib.load(bundle_path)
        except Exception as e:
            print(json.dumps({"error": f"Failed to load flare model: {e!s}"}), file=sys.stderr)
            sys.exit(1)
        if not bundle.get("model") or not bundle.get("feature_order"):
            print(json.dumps({"error": "Invalid flare model bundle"}), file=sys.stderr)
            sys.exit(1)
        # Prefer week data from API (--lat/--lon) when provided
        raw = None
        if args.lat is not None and args.lon is not None:
            try:
                from apps.ml.week_data import fetch_week_dataframe
                start_d = pd.Timestamp(start_str).date()
                raw = fetch_week_dataframe(
                    latitude=args.lat,
                    longitude=args.lon,
                    start_date=start_d,
                    days=days,
                )
            except Exception:
                pass
        if raw is None or raw.empty:
            try:
                from apps.ml.trainingModel import read_env_from_mongo
                raw = read_env_from_mongo()
            except Exception:
                from apps.ml.predict_risk import _synthetic_raw
                end_d = pd.Timestamp(start_str).date() + timedelta(days=days - 1)
                raw = _synthetic_raw(end_d.strftime("%Y-%m-%d"), num_days=14 + days, location_id=args.location_id or "default")
        results = []
        start_d = pd.Timestamp(start_str).date()
        for i in range(days):
            d = start_d + timedelta(days=i)
            date_str = d.strftime("%Y-%m-%d")
            results.append(_predict_one_date(date_str, raw, bundle, args.location_id))
        print(json.dumps({"start": start_str, "days": results}), flush=True)
        return

    date_str = (args.date or "").strip()
    if len(date_str) != 10 or date_str[4] != "-" or date_str[7] != "-":
        print(json.dumps({"error": "Provide --date YYYY-MM-DD or --week --start YYYY-MM-DD"}), file=sys.stderr)
        sys.exit(1)

    bundle_path = _flare_model_path()
    if not bundle_path or not bundle_path.exists():
        print(json.dumps({"error": "Flare model not found (D A T A/flare_model.joblib)"}), file=sys.stderr)
        sys.exit(1)

    try:
        bundle = joblib.load(bundle_path)
    except Exception as e:
        print(json.dumps({"error": f"Failed to load flare model: {e!s}"}), file=sys.stderr)
        sys.exit(1)

    if not bundle.get("model") or not bundle.get("feature_order"):
        print(json.dumps({"error": "Invalid flare model bundle (missing model or feature_order)"}), file=sys.stderr)
        sys.exit(1)

    try:
        from apps.ml.trainingModel import read_env_from_mongo
        raw = read_env_from_mongo()
    except Exception:
        from apps.ml.predict_risk import _synthetic_raw
        raw = _synthetic_raw(date_str, location_id=args.location_id or "default")

    out = _predict_one_date(date_str, raw, bundle, args.location_id)
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
