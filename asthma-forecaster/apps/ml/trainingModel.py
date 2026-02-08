"""
Asthma/air-quality "high risk tomorrow" forecaster (general label)

Reads env data from MongoDB (default: ml_daily in DB from MONGODB_DB).
Uses .env from project root for MONGODB_URI, MONGODB_DB; ML_ENV_COLL or ENV_COLL for collection.

Run from TIDAL2026:
  PYTHONPATH=asthma-forecaster python -m apps.ml.trainingModel
  # Or specify collection: ML_ENV_COLL=ml_daily PYTHONPATH=asthma-forecaster python -m apps.ml.trainingModel

Implements:
Step 2 — Feature engineering
- Trends: pm25_delta (today - yesterday)
- Rolling: 3-day and 7-day rolling mean/max for PM2.5 + AQI
- Temp swing: temp_swing = temp_max - temp_min
- Interactions: pm25_mean * humidity, pollen_total * wind
- Lag features: yesterday’s PM2.5/AQI/pollen

Step 3 — Label
y = 1 if (AQI >= 101) OR (PM2_5_mean >= 35) OR (pollen_total >= high_threshold) else 0

Step 4 — Train/test split (time-series split)
- Train: first 80% of days
- Test: last 20% of days
Metrics:
- ROC-AUC
- Precision@K (top 20% risk days flagged)
- Calibration (Brier score)

Requires:
pip install pymongo pandas scikit-learn joblib
"""

import os
import math
from pathlib import Path

import pandas as pd
from pymongo import MongoClient

from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.ensemble import HistGradientBoostingClassifier
import joblib


# ----------------------------
# Config (aligns with .env and data.py: MONGODB_URI, MONGODB_DB, ML_ENV_COLL)
# ----------------------------
def _load_dotenv():
    try:
        from dotenv import load_dotenv
        root = Path(__file__).resolve().parent.parent.parent.parent
        for p in [root / ".env", Path.cwd() / ".env"]:
            if p.exists():
                load_dotenv(p)
                break
    except ImportError:
        pass


_load_dotenv()


def _mongo_uri() -> str:
    uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI", "mongodb://localhost:27017")
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


MONGO_URI = _mongo_uri()
DB_NAME = os.getenv("MONGODB_DB") or os.getenv("DB_NAME", "tidal")
COLL_NAME = os.getenv("ML_ENV_COLL") or os.getenv("ENV_COLL", "ml_daily")
LOCATION_ID = os.getenv("LOCATION_ID", None)
TRAIN_FRAC = float(os.getenv("TRAIN_FRAC", "0.8"))

# Label thresholds (edit via env or defaults; pollen_total = tree+grass+weed, typically 0–15)
AQI_HIGH = float(os.getenv("AQI_HIGH", "101"))           # "Unhealthy for Sensitive Groups"
PM25_HIGH = float(os.getenv("PM25_HIGH", "35"))          # ~24h mean threshold (μg/m³)
POLLEN_HIGH = float(os.getenv("POLLEN_HIGH", "8"))       # pollen_total (0–15 scale); use 8 for more positives


def read_env_from_mongo() -> pd.DataFrame:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    query = {}
    if LOCATION_ID:
        query["location_id"] = LOCATION_ID

    docs = list(db[COLL_NAME].find(query, {"_id": 0}))
    if not docs:
        raise RuntimeError(f"No documents found in {DB_NAME}.{COLL_NAME} for query={query}")

    df = pd.DataFrame(docs)

    # Ensure date is datetime
    df["date"] = pd.to_datetime(df["date"])

    # Sort (critical for time features)
    df = df.sort_values(["location_id", "date"]).reset_index(drop=True)
    return df


def feature_engineer(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # ---- pollen_total + missing flags ----
    for c in ["pollen_tree", "pollen_grass", "pollen_weed"]:
        if c not in out.columns:
            out[c] = pd.NA
        out[c + "_missing"] = out[c].isna().astype(int)
        out[c] = out[c].fillna(0)

    out["pollen_total"] = out["pollen_tree"] + out["pollen_grass"] + out["pollen_weed"]

    # ---- temp swing ----
    out["temp_swing"] = out["temp_max"] - out["temp_min"]

    # ---- interactions ----
    out["pm25_x_humidity"] = out["PM2_5_mean"] * out["humidity"]
    out["pollen_x_wind"] = out["pollen_total"] * out["wind"]

    # ---- lags / trends / rolling windows per location ----
    g = out.groupby("location_id", group_keys=False)

    # Lag features
    out["pm25_mean_lag1"] = g["PM2_5_mean"].shift(1)
    out["pm25_max_lag1"]  = g["PM2_5_max"].shift(1)
    out["aqi_lag1"]       = g["AQI"].shift(1)
    out["pollen_lag1"]    = g["pollen_total"].shift(1)

    # Trend (delta)
    out["pm25_delta"] = out["PM2_5_mean"] - out["pm25_mean_lag1"]

    # Rolling stats (mean + max)
    for win in [3, 7]:
        out[f"pm25_mean_roll{win}_mean"] = (
            g["PM2_5_mean"].rolling(win).mean().reset_index(level=0, drop=True)
        )
        out[f"pm25_mean_roll{win}_max"] = (
            g["PM2_5_mean"].rolling(win).max().reset_index(level=0, drop=True)
        )
        out[f"aqi_roll{win}_mean"] = (
            g["AQI"].rolling(win).mean().reset_index(level=0, drop=True)
        )
        out[f"aqi_roll{win}_max"] = (
            g["AQI"].rolling(win).max().reset_index(level=0, drop=True)
        )

    # Drop rows without enough history for lag/rolling features
    out = out.dropna().reset_index(drop=True)
    return out


def make_label_high_risk_tomorrow(df: pd.DataFrame) -> pd.DataFrame:
    """
    y_t is defined by thresholds at day t+1, aligned to features at day t.
    """
    out = df.copy()
    g = out.groupby("location_id", group_keys=False)

    # Tomorrow's conditions
    out["AQI_tomorrow"] = g["AQI"].shift(-1)
    out["PM2_5_mean_tomorrow"] = g["PM2_5_mean"].shift(-1)
    out["pollen_total_tomorrow"] = g["pollen_total"].shift(-1)

    # Binary label: "high risk tomorrow"
    out["y"] = (
        (out["AQI_tomorrow"] >= AQI_HIGH)
        | (out["PM2_5_mean_tomorrow"] >= PM25_HIGH)
        | (out["pollen_total_tomorrow"] >= POLLEN_HIGH)
    ).astype(int)

    # Last day per location has no tomorrow label
    out = out.dropna(subset=["AQI_tomorrow", "PM2_5_mean_tomorrow", "pollen_total_tomorrow"]).reset_index(drop=True)
    return out


def time_series_train_test_split(df: pd.DataFrame, train_frac: float = 0.8):
    """
    Global time split by date:
    - Train: earliest train_frac
    - Test: latest (1-train_frac)

    This is simplest and correct for "no leakage" as long as you're not mixing future into past.
    """
    df = df.sort_values("date").reset_index(drop=True)
    n = len(df)
    if n < 50:
        print(f"Warning: only {n} rows. Models/metrics may be unstable.")

    split_idx = max(1, min(n - 1, int(math.floor(n * train_frac))))
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()
    return train_df, test_df


def precision_at_k(y_true, y_proba, top_frac: float = 0.2) -> float:
    """
    Precision@K where K is top_frac of days ranked by predicted risk.
    """
    n = len(y_true)
    k = max(1, int(math.ceil(n * top_frac)))
    idx = pd.Series(y_proba).sort_values(ascending=False).index[:k]
    return float(pd.Series(y_true).iloc[idx].mean())


def train_and_evaluate(df: pd.DataFrame):
    # Choose feature columns (exclude raw tomorrow columns, target, and some IDs)
    drop_cols = {
        "y",
        "AQI_tomorrow", "PM2_5_mean_tomorrow", "pollen_total_tomorrow",
        "latitude", "longitude", "zip_code",
    }
    cat_cols = [c for c in ["day_of_week", "season"] if c in df.columns]
    # location_id can be treated as categorical if you have multiple locations
    if "location_id" in df.columns:
        cat_cols.append("location_id")

    feature_cols = [c for c in df.columns if c not in drop_cols and c != "date"]
    X = df[feature_cols]
    y = df["y"].astype(int)

    numeric_cols = [c for c in feature_cols if c not in cat_cols]

    preprocess = ColumnTransformer(
        transformers=[
            ("num", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
            ]), numeric_cols),
            ("cat", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore")),
            ]), cat_cols),
        ],
        remainder="drop",
    )

    model = HistGradientBoostingClassifier(
        max_depth=4,
        learning_rate=0.06,
        max_iter=400,
        random_state=42,
    )

    pipe = Pipeline([
        ("preprocess", preprocess),
        ("model", model),
    ])

    train_df, test_df = time_series_train_test_split(df, TRAIN_FRAC)

    X_train, y_train = train_df[feature_cols], train_df["y"].astype(int)
    X_test, y_test = test_df[feature_cols], test_df["y"].astype(int)

    pipe.fit(X_train, y_train)
    proba_test = pipe.predict_proba(X_test)[:, 1]

    # Metrics
    roc = roc_auc_score(y_test, proba_test) if y_test.nunique() > 1 else float("nan")
    p_at_20 = precision_at_k(y_test.values, proba_test, top_frac=0.2)
    brier = brier_score_loss(y_test, proba_test)

    print("\n=== Results (Time-series split) ===")
    print(f"Train rows: {len(train_df)} | Test rows: {len(test_df)}")
    print(f"Positive rate (test): {y_test.mean():.3f}")
    print(f"ROC-AUC: {roc:.3f}" if not math.isnan(roc) else "ROC-AUC: (not defined; test has 1 class)")
    print(f"Precision@20%: {p_at_20:.3f}")
    print(f"Brier score (calibration): {brier:.3f}  (lower is better)")
    print("\n--- Metrics guide (doing well) ---")
    print("  ROC-AUC:       >0.80 good, >0.90 very good, 0.5 = random. Measures ranking of risk.")
    print("  Precision@20%: Of top 20% risk days flagged, fraction that are truly high-risk. 1.0 = perfect.")
    print("  Brier score:   <0.15 good, <0.10 very good. Lower = better calibrated probabilities.")
    print("  Positive rate: 0.1–0.5 is healthy; 0 or 1.0 means labels may be too strict or too loose.")

    joblib.dump(pipe, "risk_model_general.joblib")
    print("\nSaved model: risk_model_general.joblib")

    # Optional: show top predicted days for sanity
    preview = test_df[["date"]].copy()
    preview["pred_risk"] = proba_test
    preview["y_true"] = y_test.values
    print("\nTop 10 highest predicted-risk test days:")
    print(preview.sort_values("pred_risk", ascending=False).head(10).to_string(index=False))


def main():
    raw = read_env_from_mongo()
    fe = feature_engineer(raw)
    labeled = make_label_high_risk_tomorrow(fe)

    # Basic sanity checks
    if labeled["y"].nunique() < 2:
        print(
            "Warning: label has only one class. "
            "Try lowering POLLEN_HIGH or check whether AQI/PM2.5 thresholds are too strict for your data."
        )

    train_and_evaluate(labeled)


if __name__ == "__main__":
    main()
