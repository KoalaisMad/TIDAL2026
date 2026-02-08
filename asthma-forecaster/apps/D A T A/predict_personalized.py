#!/usr/bin/env python3
"""
PERSONALIZED RISK PREDICTIONS (used by Personalized Risk page in web UI)

Load users from MongoDB, get env for the next 7 days (from MongoDB or forecast API),
and run the personalized flare/risk model for each user for each of the next 7 days.

Predictions are cached in MongoDB (asthma.personalized_predictions). If cached values
exist for the requested users and date range, the model is skipped and cache is returned.
Requires: flare_model.joblib (trained with modelc.py), MONGODB_URI, users in asthma.users.
Uses the same feature pipeline as customizedModel.modelc (enrich_dataset, feature_cols).

API Integration:
- Called by: /api/risk/personalized/route.ts (Personalized Risk page)
- Model: flare_model.joblib (trained by customizedModel.py/modelc.py)
- Purpose: User-specific risk based on profile, symptoms, and environment

USAGE (from D A T A or TIDAL2026):
  python predict_personalized.py
  python predict_personalized.py --model flare_model.joblib --out predictions.json
  python predict_personalized.py --days 7
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Load .env from repo root so MONGODB_URI etc. are set
def _load_dotenv():
    try:
        from dotenv import load_dotenv
        root = Path(__file__).resolve().parent
        for _ in range(5):
            for name in [".env", "..env"]:
                p = root / name
                if p.exists():
                    load_dotenv(p)
                    return
            root = root.parent
        if Path.cwd().joinpath(".env").exists():
            load_dotenv(Path.cwd() / ".env")
    except ImportError:
        pass


_load_dotenv()

import pandas as pd
import numpy as np
import joblib
import requests
from pymongo import MongoClient, UpdateOne


# Reuse helpers and enrich_dataset from the personalized training model
def parse_height_in(height_str: str | None) -> float | None:
    if not height_str or not isinstance(height_str, str):
        return None
    s = height_str.strip().lower().replace(" ", "")
    if "'" not in s:
        return None
    try:
        feet, rest = s.split("'", 1)
        inches = rest.replace('"', "").strip() or "0"
        return float(feet) * 12.0 + float(inches)
    except Exception:
        return None


def parse_weight_lb(weight_str: str | None) -> float | None:
    if not weight_str or not isinstance(weight_str, str):
        return None
    s = weight_str.lower().replace("lbs", "").replace("lb", "").strip()
    try:
        return float(s)
    except Exception:
        return None


def load_users_from_mongo(client: MongoClient) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load user profile + checkIns from MongoDB (asthma.users). Returns (prof, checkins)."""
    db_name = os.environ.get("MONGODB_DB_NAME") or os.environ.get("MONGODB_USERS_DB", "asthma")
    coll = client[db_name]["users"]
    docs = list(coll.find({}, {"_id": 1, "profile": 1, "checkIns": 1}))
    if not docs:
        return (
            pd.DataFrame(columns=["user_id"]),
            pd.DataFrame(columns=["user_id", "date"]),
        )

    # Normalize to same shape as load_users(users_json): user_id + profile_* columns
    records = []
    for d in docs:
        r = {"user_id": str(d["_id"])}
        profile = d.get("profile") or {}
        for k, v in profile.items():
            r[f"profile_{k}"] = v
        records.append(r)

    prof = pd.DataFrame(records)

    if "profile_height" in prof.columns:
        prof["profile_height_in"] = prof["profile_height"].apply(parse_height_in)
    if "profile_weight" in prof.columns:
        prof["profile_weight_lb"] = prof["profile_weight"].apply(parse_weight_lb)

    rows = []
    for d in docs:
        uid = str(d["_id"])
        for c in (d.get("checkIns") or []):
            row = {"user_id": uid}
            row["date"] = c.get("date")
            for k in ["wheeze", "cough", "chestTightness", "exerciseMinutes"]:
                if k in c:
                    row[k] = c[k]
            rows.append(row)
    checkins = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["user_id", "date"])
    if "date" in checkins.columns:
        checkins["date"] = pd.to_datetime(checkins["date"])
    for col in ["wheeze", "cough", "chestTightness", "exerciseMinutes"]:
        if col in checkins.columns:
            checkins[col] = pd.to_numeric(checkins[col], errors="coerce").fillna(0)
        else:
            checkins[col] = 0

    return prof, checkins


def enrich_dataset(env_df: pd.DataFrame, prof: pd.DataFrame, checkins: pd.DataFrame) -> pd.DataFrame:
    """Same logic as modelc.enrich_dataset: merge profile + checkins, add lags."""
    df = env_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    if "user_id" not in df.columns:
        raise ValueError("env_df must have user_id")
    df = df.merge(prof, on="user_id", how="left")
    df = df.merge(checkins, on=["user_id", "date"], how="left", suffixes=("", "_checkin"))
    for col in ["wheeze", "cough", "chestTightness", "exerciseMinutes"]:
        if col in df.columns:
            df[col] = df[col].fillna(0)
    df = df.sort_values(["user_id", "date"]).reset_index(drop=True)
    for col in ["wheeze", "cough", "chestTightness", "exerciseMinutes"]:
        if col in df.columns:
            df[f"{col}_lag1"] = df.groupby("user_id")[col].shift(1).fillna(0)
    if {"wheeze", "cough", "chestTightness"}.issubset(df.columns):
        df["symptom_score"] = df["wheeze"] + df["cough"] + df["chestTightness"]
        df["symptom_score_lag1"] = df.groupby("user_id")["symptom_score"].shift(1).fillna(0)
    return df


def _mongo_uri() -> str:
    uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    if "@" in uri and "://" in uri:
        try:
            from urllib.parse import quote_plus
            pre, rest = uri.split("://", 1)
            auth, host = rest.split("@", 1)
            if ":" in auth:
                user, password = auth.split(":", 1)
                auth = f"{user}:{quote_plus(password)}"
            uri = f"{pre}://{auth}@{host}"
        except Exception:
            pass
    return uri


def load_env_from_mongo(client: MongoClient, start_date: date, end_date: date) -> pd.DataFrame | None:
    """Load env rows from tidal DB (MONGODB_DB / MONGODB_COLLECTION) for date range."""
    db_name = os.environ.get("MONGODB_DB") or os.environ.get("DB_NAME", "tidal")
    coll_name = os.environ.get("ML_ENV_COLL") or os.environ.get("MONGODB_COLLECTION", "pulldata")
    db = client[db_name]
    coll = db[coll_name]
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, datetime.max.time().replace(microsecond=0), tzinfo=timezone.utc)
    q = {"date": {"$gte": start_dt, "$lte": end_dt}}
    docs = list(coll.find(q, {"_id": 0}))
    if not docs:
        return None
    df = pd.DataFrame(docs)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df.sort_values("date").reset_index(drop=True)
    # Keep one location if multiple (e.g. first)
    if "location_id" in df.columns and df["location_id"].nunique() > 1:
        first_loc = df["location_id"].iloc[0]
        df = df[df["location_id"] == first_loc].reset_index(drop=True)
    return df


def fetch_forecast_env(lat: float, lon: float, start_date: date, end_date: date) -> pd.DataFrame:
    """Fetch weather + air quality for date range from Open-Meteo (archive + forecast)."""
    start_str = start_date.isoformat()
    end_str = end_date.isoformat()
    today = date.today()
    # Use forecast API for future, archive for past
    if start_date >= today:
        # Forecast: next 7–16 days
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat, "longitude": lon,
            "start_date": start_str, "end_date": end_str,
            "daily": "temperature_2m_min,temperature_2m_max,relative_humidity_mean_2m,windspeed_10m_mean,precipitation_sum",
            "timezone": "UTC",
        }
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        j = r.json()
        daily = j.get("daily", {})
        df = pd.DataFrame({
            "date": daily.get("time", []),
            "temp_min": daily.get("temperature_2m_min", []),
            "temp_max": daily.get("temperature_2m_max", []),
            "humidity": daily.get("relative_humidity_mean_2m", [np.nan] * len(daily.get("time", []))),
            "wind": daily.get("windspeed_10m_mean", []),
            "rain": daily.get("precipitation_sum", []),
        })
        # Air quality forecast (same API can return pm2_5 in some setups; fallback)
        aq_url = "https://air-quality.api.open-meteo.com/v1/air-quality"
        aq_params = {"latitude": lat, "longitude": lon, "start_date": start_str, "end_date": end_str, "timezone": "UTC"}
        try:
            aq = requests.get(aq_url, params=aq_params, timeout=30)
            if aq.ok:
                aq_j = aq.json()
                aq_daily = aq_j.get("daily", {})
                df["PM2_5_mean"] = aq_daily.get("pm2_5", [np.nan] * len(df))[:len(df)]
                df["PM2_5_max"] = df["PM2_5_mean"]
                df["AQI"] = aq_daily.get("us_aqi", [np.nan] * len(df))[:len(df)]
            else:
                df["PM2_5_mean"] = 10.0
                df["PM2_5_max"] = 10.0
                df["AQI"] = np.nan
        except Exception:
            df["PM2_5_mean"] = 10.0
            df["PM2_5_max"] = 10.0
            df["AQI"] = np.nan
        df["pressure"] = 1013.0
    else:
        # Archive for past dates
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": lat, "longitude": lon,
            "start_date": start_str, "end_date": end_str,
            "daily": "temperature_2m_min,temperature_2m_max,relative_humidity_mean_2m,windspeed_10m_mean,precipitation_sum,surface_pressure_mean",
            "timezone": "UTC",
        }
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        j = r.json()
        daily = j.get("daily", {})
        df = pd.DataFrame({
            "date": daily.get("time", []),
            "temp_min": daily.get("temperature_2m_min", []),
            "temp_max": daily.get("temperature_2m_max", []),
            "humidity": daily.get("relative_humidity_mean_2m", []),
            "wind": daily.get("windspeed_10m_mean", []),
            "rain": daily.get("precipitation_sum", []),
            "pressure": daily.get("surface_pressure_mean", [1013] * len(daily.get("time", []))),
        })
        aq_url = "https://air-quality-api.open-meteo.com/v1/air-quality"
        aq_params = {"latitude": lat, "longitude": lon, "start_date": start_str, "end_date": end_str, "hourly": "pm2_5", "timezone": "UTC"}
        try:
            aq = requests.get(aq_url, params=aq_params, timeout=60)
            if aq.ok:
                aq_j = aq.json()
                h = aq_j.get("hourly", {})
                pm = h.get("pm2_5", [])
                if pm:
                    n_days = len(df)
                    day_len = len(pm) // n_days if n_days else 24
                    means = [np.nanmean(pm[i*day_len:(i+1)*day_len]) for i in range(n_days)]
                    df["PM2_5_mean"] = means[:len(df)]
                    df["PM2_5_max"] = df["PM2_5_mean"]
                else:
                    df["PM2_5_mean"] = 10.0
                    df["PM2_5_max"] = 10.0
                df["AQI"] = np.nan
            else:
                df["PM2_5_mean"] = 10.0
                df["PM2_5_max"] = 10.0
                df["AQI"] = np.nan
        except Exception:
            df["PM2_5_mean"] = 10.0
            df["PM2_5_max"] = 10.0
            df["AQI"] = np.nan

    df["date"] = pd.to_datetime(df["date"])
    df["day_of_week"] = df["date"].dt.day_name()
    df["month"] = df["date"].dt.month
    def season(m):
        if m in (12, 1, 2): return "winter"
        if m in (3, 4, 5): return "spring"
        if m in (6, 7, 8): return "summer"
        return "fall"
    df["season"] = df["month"].apply(season)
    df["holiday_flag"] = False
    df["locationid"] = f"{lat:.2f}-{lon:.2f}"
    df["zip_code"] = None
    df["latitude"] = lat
    df["longitude"] = lon
    for c in ["pollen_tree", "pollen_grass", "pollen_weed"]:
        if c not in df.columns:
            df[c] = np.nan
    if "google_trends_allergy" not in df.columns:
        df["google_trends_allergy"] = 50.0
    return df


# --- Prediction cache (MongoDB) ---
PREDICTIONS_COLL = "personalized_predictions"


def get_predictions_coll(client: MongoClient):
    """Return the personalized predictions collection (asthma DB)."""
    db_name = os.environ.get("MONGODB_DB_NAME") or os.environ.get("MONGODB_USERS_DB", "asthma")
    return client[db_name][PREDICTIONS_COLL]


def load_cached_predictions(
    client: MongoClient,
    user_ids: list[str],
    date_strs: list[str],
    target_col: str,
) -> list[dict] | None:
    """
    Load cached predictions for (user_id, date). Returns list of {user_id, date, <target_col>}
    if we have all requested pairs; otherwise None.
    """
    if not user_ids or not date_strs:
        return []
    wanted = {(uid, d) for uid in user_ids for d in date_strs}
    coll = get_predictions_coll(client)
    cursor = coll.find(
        {"user_id": {"$in": user_ids}, "date": {"$in": date_strs}},
        {"_id": 0, "user_id": 1, "date": 1, "risk": 1, "flare_day": 1},
    )
    records = []
    for doc in cursor:
        uid = str(doc.get("user_id", ""))
        d = doc.get("date")
        if d and hasattr(d, "strftime"):
            d = d.strftime("%Y-%m-%d")
        else:
            d = str(d)[:10]
        val = doc.get("risk") if target_col == "risk" else doc.get("flare_day")
        if val is None:
            val = doc.get("risk", doc.get("flare_day", 0))
        records.append({"user_id": uid, "date": d, target_col: float(val)})
        wanted.discard((uid, d))
    if wanted:
        return None  # incomplete cache
    # Sort like model output: by date then user_id
    records.sort(key=lambda r: (r["date"], r["user_id"]))
    return records


def save_predictions(client: MongoClient, records: list[dict], target_col: str) -> None:
    """Upsert predictions into the cache collection. Each record: user_id, date, <target_col>."""
    if not records:
        return
    coll = get_predictions_coll(client)
    now = datetime.now(timezone.utc)
    ops = []
    for r in records:
        uid = str(r["user_id"])
        date_str = r.get("date")
        if hasattr(date_str, "strftime"):
            date_str = date_str.strftime("%Y-%m-%d")
        else:
            date_str = str(date_str)[:10]
        val = r.get(target_col, 0)
        ops.append(
            UpdateOne(
                {"user_id": uid, "date": date_str},
                {"$set": {target_col: float(val), "updated_at": now}},
                upsert=True,
            )
        )
    if ops:
        coll.bulk_write(ops)


def get_env_next_n_days(client: MongoClient, n_days: int, *, lat: float = 37.77, lon: float = -122.42) -> pd.DataFrame:
    """Get env for today + next n_days (so we have 1 + n_days rows; today is for lag1)."""
    today = date.today()
    start = today
    end = today + timedelta(days=n_days)
    df = load_env_from_mongo(client, start, end)
    if df is not None and len(df) >= min(2, n_days + 1):
        # Normalize column names to match training (locationid, etc.)
        if "location_id" in df.columns and "locationid" not in df.columns:
            df["locationid"] = df["location_id"]
        if "zip_code" not in df.columns:
            df["zip_code"] = None
        df["date"] = pd.to_datetime(df["date"])
        try:
            if getattr(df["date"].dtype, "tz", None) is not None:
                df["date"] = df["date"].dt.tz_localize(None)
        except Exception:
            pass
        for c in ["day_of_week", "month", "season"]:
            if c not in df.columns:
                if c == "day_of_week":
                    df["day_of_week"] = df["date"].dt.day_name()
                elif c == "month":
                    df["month"] = df["date"].dt.month
                elif c == "season":
                    df["season"] = df["month"].apply(lambda m: "winter" if m in (12,1,2) else "spring" if m in (3,4,5) else "summer" if m in (6,7,8) else "fall")
        if "holiday_flag" not in df.columns:
            df["holiday_flag"] = False
        if "google_trends_allergy" not in df.columns:
            df["google_trends_allergy"] = 50.0
        return df
    # Fallback: fetch from Open-Meteo
    return fetch_forecast_env(lat, lon, start, end)


def main() -> int:
    parser = argparse.ArgumentParser(description="Predict risk/flare for MongoDB users for the next 7 days")
    _script_dir = Path(__file__).resolve().parent
    parser.add_argument("--model", default=str(_script_dir / "flare_model.joblib"), help="Path to flare_model.joblib")
    parser.add_argument("--out", default="-", help="Output JSON file (default: stdout)")
    parser.add_argument("--days", type=int, default=7, help="Number of days to predict (default: 7)")
    parser.add_argument("--lat", type=float, default=37.77, help="Latitude for env if fetching forecast")
    parser.add_argument("--lon", type=float, default=-122.42, help="Longitude for env if fetching forecast")
    args = parser.parse_args()

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"Model not found: {model_path}", file=sys.stderr)
        return 1

    try:
        bundle = joblib.load(model_path)
    except Exception as e:
        print(f"Failed to load model: {e}", file=sys.stderr)
        return 1

    pipeline = bundle.get("pipeline")
    feature_cols = bundle.get("feature_cols", [])
    target_col = bundle.get("target_col", "risk")
    if pipeline is None or not feature_cols:
        print("Invalid model bundle: missing pipeline or feature_cols", file=sys.stderr)
        return 1

    uri = _mongo_uri()
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    try:
        client.admin.command("ping")
    except Exception as e:
        print(f"MongoDB connection failed: {e}", file=sys.stderr)
        return 1

    prof, checkins = load_users_from_mongo(client)
    if prof.empty or "user_id" not in prof.columns:
        print("No users found in MongoDB (asthma.users).", file=sys.stderr)
        return 1

    user_ids = prof["user_id"].tolist()
    n_days = max(1, args.days)
    env_df = get_env_next_n_days(client, n_days, lat=args.lat, lon=args.lon)
    if env_df is None or env_df.empty:
        print("No env data for the next days.", file=sys.stderr)
        return 1

    env_df["date"] = pd.to_datetime(env_df["date"])
    dates = env_df["date"].drop_duplicates().sort_values().tolist()
    today_dt = pd.Timestamp(date.today())
    future_dates = [d for d in dates if d > today_dt]
    if not future_dates:
        future_dates = [d for d in dates if d >= today_dt]
    if not future_dates:
        future_dates = dates
    date_strs = [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10] for d in future_dates]

    # Try cache first: if we have predictions for all (user_id, date), return them
    cached = load_cached_predictions(client, user_ids, date_strs, target_col)
    if cached is not None:
        out_json = json.dumps(cached, indent=2)
        if args.out == "-":
            print(out_json)
        else:
            Path(args.out).write_text(out_json, encoding="utf-8")
            print(f"Wrote {len(cached)} predictions (from cache) to {args.out}", file=sys.stderr)
        return 0

    # Build one row per (user_id, date)
    rows = []
    for uid in user_ids:
        for d in dates:
            row = {"user_id": uid, "date": d}
            for c in env_df.columns:
                if c != "date":
                    val = env_df.loc[env_df["date"] == d, c].iloc[0] if (env_df["date"] == d).any() else None
                    row[c] = val
            rows.append(row)
    pred_env = pd.DataFrame(rows)

    df = enrich_dataset(pred_env, prof, checkins)
    df_future = df[df["date"] > today_dt].copy()
    if df_future.empty:
        df_future = df[df["date"] >= today_dt].copy()
    if df_future.empty:
        df_future = df.tail(len(user_ids) * n_days)

    # Align to saved feature_cols: add missing cols with 0, drop extra
    for c in feature_cols:
        if c not in df_future.columns:
            df_future[c] = 0
    X = df_future[feature_cols]
    # Handle object columns (OneHotEncoder)
    for c in feature_cols:
        if X[c].dtype == object:
            X = X.copy()
            X[c] = X[c].astype(str).fillna("")
    try:
        preds = pipeline.predict(X)
    except Exception as e:
        print(f"Prediction failed: {e}", file=sys.stderr)
        return 1

    out_records = []
    for pos, (_, row) in enumerate(df_future.iterrows()):
        d = row["date"]
        date_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
        out_records.append({
            "user_id": row["user_id"],
            "date": date_str,
            target_col: float(preds[pos]),
        })

    # Store predictions in DB so next run can use cache
    try:
        save_predictions(client, out_records, target_col)
    except Exception as e:
        print(f"Warning: could not save predictions to DB: {e}", file=sys.stderr)

    out_json = json.dumps(out_records, indent=2)
    if args.out == "-":
        print(out_json)
    else:
        Path(args.out).write_text(out_json, encoding="utf-8")
        print(f"Wrote {len(out_records)} predictions to {args.out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
