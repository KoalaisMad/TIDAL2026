"""
Canonical data layer for ML: load env and labels from MongoDB, add time features.
Schema matches TIDAL daily rows: PM2_5_mean, AQI, temp_min, temp_max, humidity, wind, pressure, rain,
pollen_*, day_of_week, month, season, holiday_flag, etc.

Use ML_ENV_COLL or ENV_COLL to read from a different collection (e.g. ml_daily).
"""
from __future__ import annotations

import os
from pathlib import Path

def _load_env():
    try:
        from dotenv import load_dotenv
        root = Path(__file__).resolve().parent.parent.parent.parent
        for p in [root / ".env", Path.cwd() / ".env"]:
            if p.exists():
                load_dotenv(p)
                break
    except ImportError:
        pass


_load_env()

import pandas as pd
from pymongo import MongoClient


def _mongo_uri():
    uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    if "@" in uri and "://" in uri:
        from urllib.parse import quote_plus
        try:
            pre, rest = uri.split("://", 1)
            auth, host = rest.split("@", 1)
            if ":" in auth:
                user, password = auth.split(":", 1)
                auth = f"{user}:{quote_plus(password)}"
            uri = f"{pre}://{auth}@{host}"
        except Exception:
            pass
    return uri


DB_NAME = os.environ.get("MONGODB_DB") or os.environ.get("DB_NAME", "tidal")
ENV_COLL = os.environ.get("ML_ENV_COLL") or os.environ.get("ENV_COLL") or os.environ.get("MONGODB_COLLECTION", "pulldata")
LABEL_COLL = os.environ.get("LABEL_COLL", "symptom_daily")
USER_ID = os.environ.get("USER_ID", "demo_user")
LOCATION_ID = os.environ.get("LOCATION_ID") or None


def get_client() -> MongoClient:
    return MongoClient(_mongo_uri(), serverSelectionTimeoutMS=10000)


def load_env(client: MongoClient, collection_name: str | None = None) -> pd.DataFrame:
    """Load daily env data from MongoDB. Uses ENV_COLL or ML_ENV_COLL, or pass collection_name."""
    db = client[DB_NAME]
    coll_name = collection_name or ENV_COLL
    q = {}
    if LOCATION_ID:
        q["location_id"] = LOCATION_ID
    docs = list(db[coll_name].find(q, {"_id": 0}))
    if not docs:
        raise RuntimeError(f"No documents in {DB_NAME}.{coll_name}. Run generate_ml_data.py first or set ML_ENV_COLL.")
    df = pd.DataFrame(docs)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["location_id", "date"]).reset_index(drop=True)
    # Fill any remaining nulls so ML has no missing values
    numeric_cols = [
        "PM2_5_mean", "PM2_5_max", "AQI",
        "temp_min", "temp_max", "humidity", "wind", "pressure", "rain",
        "pollen_tree", "pollen_grass", "pollen_weed",
        "day_of_week", "month", "season",
    ]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
            if df[c].isna().any():
                df[c] = df[c].fillna(df[c].median() if df[c].notna().any() else 0)
    if "holiday_flag" in df.columns:
        df["holiday_flag"] = df["holiday_flag"].fillna(False)
    return df


def load_labels(client: MongoClient) -> pd.DataFrame:
    """Labels: { user_id, date, flare } or { user_id, date, flare_nextday }."""
    db = client[DB_NAME]
    docs = list(db[LABEL_COLL].find({"user_id": USER_ID}, {"_id": 0}))
    if not docs:
        return pd.DataFrame()
    lab = pd.DataFrame(docs)
    lab["date"] = pd.to_datetime(lab["date"])
    lab = lab.sort_values("date").reset_index(drop=True)
    if "flare_nextday" not in lab.columns and "flare" in lab.columns:
        lab["flare_nextday"] = lab["flare"].shift(-1)
    if "flare_nextday" not in lab.columns:
        return pd.DataFrame()
    lab = lab[["date", "flare_nextday"]].dropna()
    return lab


def add_time_features(env: pd.DataFrame, min_history: int = 7) -> pd.DataFrame:
    """Add derived + lag + rolling features. Drops rows without enough history unless fallback."""
    df = env.copy()
    df["temp_range"] = df["temp_max"] - df["temp_min"]
    df["pm_spike"] = df["PM2_5_max"] - df["PM2_5_mean"]
    df["humid_x_pm"] = df["humidity"] * (df["PM2_5_mean"].fillna(0) + 1e-6)
    df["wind_x_pm"] = df["wind"] * (df["PM2_5_mean"].fillna(0) + 1e-6)
    for col in ["pollen_tree", "pollen_grass", "pollen_weed"]:
        if col in df.columns:
            df[col + "_missing"] = df[col].isna().astype(int)
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    num_cols = [
        "PM2_5_mean", "PM2_5_max", "AQI",
        "temp_min", "temp_max", "temp_range",
        "humidity", "wind", "pressure", "rain",
        "pm_spike", "humid_x_pm", "wind_x_pm",
        "pollen_tree", "pollen_grass", "pollen_weed",
    ]
    num_cols = [c for c in num_cols if c in df.columns]
    g = df.groupby("location_id", group_keys=False)
    for c in num_cols:
        df[f"{c}_lag1"] = g[c].shift(1)
        df[f"{c}_lag2"] = g[c].shift(2)
        df[f"{c}_roll3"] = g[c].rolling(3).mean().reset_index(level=0, drop=True)
        df[f"{c}_roll7"] = g[c].rolling(7).mean().reset_index(level=0, drop=True)
    df = df.dropna().reset_index(drop=True)
    if len(df) == 0 and len(env) > 0:
        df = env.copy()
        df["temp_range"] = df["temp_max"] - df["temp_min"]
        df["pm_spike"] = df["PM2_5_max"] - df["PM2_5_mean"]
        df["humid_x_pm"] = df["humidity"] * (df["PM2_5_mean"].fillna(0) + 1e-6)
        df["wind_x_pm"] = df["wind"] * (df["PM2_5_mean"].fillna(0) + 1e-6)
        for col in ["pollen_tree", "pollen_grass", "pollen_weed"]:
            if col in df.columns:
                df[col + "_missing"] = df[col].isna().astype(int)
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        df = df.dropna(how="all", axis=1).fillna(0).reset_index(drop=True)
    return df
