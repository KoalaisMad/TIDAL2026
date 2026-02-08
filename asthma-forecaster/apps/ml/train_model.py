#!/usr/bin/env python3
"""
Train a simple ML model for allergy severity prediction.

Uses historical checkins + environment_daily from MongoDB. Target: severe allergies
(symptomScore >= 4 on 0–5 scale). Features: pollen (tree/grass/weed), weather,
air quality, and recent symptom score. Saves a joblib model for use by main.py.

Usage (from repo root or apps/ml):
  python -m apps.ml.train_model [--out model.joblib] [--db asthma]
  Set MONGODB_URI and optionally ALLERGY_MODEL_PATH in .env.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow running from TIDAL2026 or asthma-forecaster root
_REPO = Path(__file__).resolve().parent.parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from dotenv import load_dotenv
    load_dotenv(_REPO / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

import joblib
import numpy as np
from pymongo import MongoClient
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# Must match main.FEATURE_ORDER
FEATURE_ORDER = [
    "aqi", "pm25", "tree_index", "grass_index", "weed_index", "weighted_pollen",
    "humidity", "wind_speed_kmh", "rain_mm", "temp_max_c", "symptom_score_today",
]

SEVERE_THRESHOLD = 4.0  # symptomScore >= 4 = severe


def _safe_float(x) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _flatten_env(doc: dict) -> dict:
    out = {"date": doc.get("date"), "locationKey": doc.get("locationKey")}
    aq = doc.get("air_quality") or {}
    out["aqi"] = aq.get("aqi")
    out["pm25_mean"] = aq.get("pm25_mean")
    out["pm25_max"] = aq.get("pm25_max")
    w = doc.get("weather") or {}
    out["humidity_mean"] = w.get("humidity_mean")
    out["humidity_max"] = w.get("humidity_max")
    out["wind_speed_kmh"] = w.get("wind_speed_kmh")
    out["rain_mm"] = w.get("rain_mm")
    out["temp_max_c"] = w.get("temp_max_c")
    p = doc.get("pollen") or {}
    out["tree_index"] = p.get("tree_index")
    out["grass_index"] = p.get("grass_index")
    out["weed_index"] = p.get("weed_index")
    return out


def load_training_data(db, location_key: str | None = None) -> tuple[list[list[float]], list[int]]:
    """Load checkins + environment_daily, build features and severe (0/1) target."""
    checkins = list(db.checkins.find({}))
    env_docs = list(db.environment_daily.find({}))
    if location_key:
        env_docs = [e for e in env_docs if e.get("locationKey") == location_key]

    env_by_date = {}
    for e in env_docs:
        d = e.get("date")
        if d:
            env_by_date[d] = _flatten_env(e)

    X_rows = []
    y_list = []
    for c in checkins:
        date_val = c.get("date")
        if not date_val:
            continue
        env = env_by_date.get(date_val)
        if not env:
            continue
        symptom = _safe_float(c.get("symptomScore")) or 0.0
        tree = _safe_float(env.get("tree_index"))
        grass = _safe_float(env.get("grass_index"))
        weed = _safe_float(env.get("weed_index"))
        weighted_pollen = (tree or 0) + (grass or 0) + (weed or 0)
        row = {
            "aqi": _safe_float(env.get("aqi")),
            "pm25": _safe_float(env.get("pm25_mean")) or _safe_float(env.get("pm25_max")),
            "tree_index": tree,
            "grass_index": grass,
            "weed_index": weed,
            "weighted_pollen": weighted_pollen,
            "humidity": _safe_float(env.get("humidity_mean")) or _safe_float(env.get("humidity_max")),
            "wind_speed_kmh": _safe_float(env.get("wind_speed_kmh")),
            "rain_mm": _safe_float(env.get("rain_mm")),
            "temp_max_c": _safe_float(env.get("temp_max_c")),
            "symptom_score_today": symptom,
        }
        vec = [float(row.get(k) if row.get(k) is not None else 0.0) for k in FEATURE_ORDER]
        X_rows.append(vec)
        y_list.append(1 if symptom >= SEVERE_THRESHOLD else 0)

    return X_rows, y_list


def main() -> int:
    parser = argparse.ArgumentParser(description="Train allergy severity model")
    parser.add_argument("--out", type=str, default="allergy_model.joblib", help="Output model path")
    parser.add_argument("--db", type=str, default="asthma", help="MongoDB database name")
    parser.add_argument("--location-key", type=str, help="Filter env by locationKey")
    parser.add_argument("--min-samples", type=int, default=20, help="Minimum samples to train")
    args = parser.parse_args()

    uri = os.environ.get("MONGODB_URI")
    if not uri:
        print("Set MONGODB_URI in .env")
        return 1

    client = MongoClient(uri)
    db = client[args.db]
    X_rows, y_list = load_training_data(db, args.location_key)

    if len(X_rows) < args.min_samples:
        print(f"Not enough data: {len(X_rows)} rows (need at least {args.min_samples}). Ingest checkins and environment_daily, then retry.")
        return 1

    X = np.array(X_rows, dtype=np.float64)
    y = np.array(y_list, dtype=np.int64)
    n_severe = int(y.sum())
    print(f"Training on {len(y)} samples ({n_severe} severe)")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = LogisticRegression(max_iter=500, random_state=42, class_weight="balanced")
    model.fit(X_train_s, y_train)
    acc = (model.predict(X_test_s) == y_test).mean()
    print(f"Test accuracy: {acc:.3f}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "scaler": scaler, "feature_order": FEATURE_ORDER}, out_path)
    print(f"Saved model + scaler to {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
