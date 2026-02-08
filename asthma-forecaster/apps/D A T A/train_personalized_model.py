#!/usr/bin/env python3
"""
Train a personalized flare/risk prediction model using user profiles, check-ins, and environmental data.

This model predicts personalized asthma risk for each user based on:
- User profile (height, weight, age, asthma_severity, etc.)
- Historical check-ins (symptoms: wheeze, cough, chestTightness, exerciseMinutes)
- Environmental data (AQI, PM2.5, pollen, weather)
- Temporal features (day_of_week, month, season, holiday)
- Lag features (previous day's symptoms)

Output: flare_model.joblib (bundle with pipeline, feature_cols, target_col)

USAGE (from TIDAL2026 or D A T A directory):
  python train_personalized_model.py
  python train_personalized_model.py --out custom_model.joblib --target risk
  python train_personalized_model.py --days 90 --min-users 5
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Load .env from repo root
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
from pymongo import MongoClient
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report, roc_auc_score, precision_score, recall_score


# ============================================================================
# HELPER FUNCTIONS (same as predict_personalized.py)
# ============================================================================

def parse_height_in(height_str: str | None) -> float | None:
    """Parse height string like '5'10"' to total inches."""
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
    """Parse weight string like '150 lbs' to float."""
    if not weight_str or not isinstance(weight_str, str):
        return None
    s = weight_str.lower().replace("lbs", "").replace("lb", "").strip()
    try:
        return float(s)
    except Exception:
        return None


def _mongo_uri() -> str:
    """Get MongoDB URI from environment and encode password if needed."""
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


# ============================================================================
# DATA LOADING FROM MONGODB
# ============================================================================

def load_users_from_mongo(client: MongoClient) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load user profiles and check-ins from MongoDB (asthma.users collection).
    Returns: (profile_df, checkins_df)
    """
    db_name = os.environ.get("MONGODB_DB_NAME") or os.environ.get("MONGODB_USERS_DB", "asthma")
    coll = client[db_name]["users"]
    docs = list(coll.find({}, {"_id": 1, "profile": 1, "checkIns": 1}))
    
    if not docs:
        return (
            pd.DataFrame(columns=["user_id"]),
            pd.DataFrame(columns=["user_id", "date"]),
        )
    
    # Build profile DataFrame
    prof_records = []
    for d in docs:
        r = {"user_id": str(d["_id"])}
        profile = d.get("profile") or {}
        for k, v in profile.items():
            r[f"profile_{k}"] = v
        prof_records.append(r)
    
    prof = pd.DataFrame(prof_records)
    
    # Parse height and weight
    if "profile_height" in prof.columns:
        prof["profile_height_in"] = prof["profile_height"].apply(parse_height_in)
    if "profile_weight" in prof.columns:
        prof["profile_weight_lb"] = prof["profile_weight"].apply(parse_weight_lb)
    
    # Build check-ins DataFrame
    checkin_rows = []
    for d in docs:
        uid = str(d["_id"])
        for c in (d.get("checkIns") or []):
            row = {"user_id": uid}
            row["date"] = c.get("date")
            for k in ["wheeze", "cough", "chestTightness", "exerciseMinutes"]:
                if k in c:
                    row[k] = c[k]
            checkin_rows.append(row)
    
    checkins = pd.DataFrame(checkin_rows) if checkin_rows else pd.DataFrame(columns=["user_id", "date"])
    
    if "date" in checkins.columns:
        checkins["date"] = pd.to_datetime(checkins["date"])
    
    for col in ["wheeze", "cough", "chestTightness", "exerciseMinutes"]:
        if col in checkins.columns:
            checkins[col] = pd.to_numeric(checkins[col], errors="coerce").fillna(0)
        else:
            checkins[col] = 0
    
    return prof, checkins


def load_env_from_mongo(client: MongoClient, days: int = 90) -> pd.DataFrame | None:
    """
    Load environmental data from MongoDB (tidal database, pulldata collection).
    Returns last 'days' worth of data.
    """
    db_name = os.environ.get("MONGODB_DB") or os.environ.get("DB_NAME", "tidal")
    coll_name = os.environ.get("ML_ENV_COLL") or os.environ.get("MONGODB_COLLECTION", "pulldata")
    
    db = client[db_name]
    coll = db[coll_name]
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    q = {"date": {"$gte": start_date, "$lte": end_date}}
    docs = list(coll.find(q, {"_id": 0}))
    
    if not docs:
        return None
    
    df = pd.DataFrame(docs)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df.sort_values("date").reset_index(drop=True)
    
    # Normalize column names
    if "location_id" in df.columns and "locationid" not in df.columns:
        df["locationid"] = df["location_id"]
    
    return df


# ============================================================================
# FEATURE ENGINEERING
# ============================================================================

def enrich_dataset(env_df: pd.DataFrame, prof: pd.DataFrame, checkins: pd.DataFrame) -> pd.DataFrame:
    """
    Merge environment data with user profiles and check-ins.
    Add lag features for symptoms.
    """
    df = env_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    
    if "user_id" not in df.columns:
        # Create cartesian product: all users × all env dates
        user_ids = prof["user_id"].unique()
        rows = []
        for uid in user_ids:
            for _, env_row in df.iterrows():
                row = {"user_id": uid}
                row.update(env_row.to_dict())
                rows.append(row)
        df = pd.DataFrame(rows)
    
    # Merge profile
    df = df.merge(prof, on="user_id", how="left")
    
    # Merge check-ins
    df = df.merge(checkins, on=["user_id", "date"], how="left", suffixes=("", "_checkin"))
    
    # Fill missing symptoms
    for col in ["wheeze", "cough", "chestTightness", "exerciseMinutes"]:
        if col in df.columns:
            df[col] = df[col].fillna(0)
    
    # Sort by user and date
    df = df.sort_values(["user_id", "date"]).reset_index(drop=True)
    
    # Add lag features (previous day's symptoms)
    for col in ["wheeze", "cough", "chestTightness", "exerciseMinutes"]:
        if col in df.columns:
            df[f"{col}_lag1"] = df.groupby("user_id")[col].shift(1).fillna(0)
    
    # Symptom score
    if {"wheeze", "cough", "chestTightness"}.issubset(df.columns):
        df["symptom_score"] = df["wheeze"] + df["cough"] + df["chestTightness"]
        df["symptom_score_lag1"] = df.groupby("user_id")["symptom_score"].shift(1).fillna(0)
    
    return df


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add day_of_week, month, season if not present."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    
    if "day_of_week" not in df.columns:
        df["day_of_week"] = df["date"].dt.day_name()
    
    if "month" not in df.columns:
        df["month"] = df["date"].dt.month
    
    if "season" not in df.columns:
        def get_season(m):
            if m in (12, 1, 2):
                return "winter"
            elif m in (3, 4, 5):
                return "spring"
            elif m in (6, 7, 8):
                return "summer"
            else:
                return "fall"
        df["season"] = df["month"].apply(get_season)
    
    if "holiday_flag" not in df.columns:
        df["holiday_flag"] = False
    
    return df


def create_target(df: pd.DataFrame, target_col: str = "risk") -> pd.DataFrame:
    """
    Create target variable based on symptoms or environmental thresholds.
    
    For 'risk': Binary target based on high symptom score (>=4) or high env risk
    For 'flare_day': Binary target based on symptom flare (symptom_score >= 6)
    """
    df = df.copy()
    
    if target_col == "risk":
        # Define risk as: high symptoms (>=4) OR high environmental exposure
        high_symptoms = (df.get("symptom_score", 0) >= 4).astype(int)
        high_env = (
            ((df.get("AQI", 0) > 100) | (df.get("PM2_5_mean", 0) > 35)) |
            ((df.get("pollen_tree", 0) + df.get("pollen_grass", 0) + df.get("pollen_weed", 0)) > 20)
        ).astype(int)
        df[target_col] = (high_symptoms | high_env).astype(int)
    
    elif target_col == "flare_day":
        # Define flare based on symptom score
        df[target_col] = (df.get("symptom_score", 0) >= 6).astype(int)
    
    return df


# ============================================================================
# MODEL TRAINING
# ============================================================================

def train_personalized_model(
    df: pd.DataFrame,
    target_col: str = "risk",
    output_path: str = "flare_model.joblib"
) -> None:
    """
    Train a personalized risk/flare prediction model.
    
    Features:
    - User profile: age, height, weight, BMI, asthma severity
    - Environmental: AQI, PM2.5, pollen, weather
    - Temporal: day_of_week, month, season
    - Symptoms: current and lagged symptoms
    
    Model: HistGradientBoostingClassifier (handles missing values, fast)
    """
    # Identify categorical columns
    cat_cols = ["day_of_week", "season"]
    cat_cols = [c for c in cat_cols if c in df.columns]
    
    # Columns to exclude from features
    exclude_cols = {
        "date", "user_id", "locationid", "location_id", "zip_code", 
        "latitude", "longitude", target_col, "_id"
    }
    
    # Build feature list
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    
    # Prepare X and y
    X = df[feature_cols].copy()
    y = df[target_col].astype(int)
    
    print(f"\n{'='*70}")
    print(f"TRAINING PERSONALIZED {target_col.upper()} MODEL")
    print(f"{'='*70}")
    print(f"Total samples: {len(df)}")
    print(f"Features: {len(feature_cols)}")
    print(f"Categorical features: {cat_cols}")
    print(f"Target distribution: {y.value_counts().to_dict()}")
    print(f"Target rate: {y.mean():.2%}")
    
    # Handle categorical columns
    numeric_cols = [c for c in feature_cols if c not in cat_cols]
    
    # Build preprocessing pipeline
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]), numeric_cols),
            ("cat", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]), cat_cols),
        ],
        remainder="drop",
    )
    
    # Model
    model = HistGradientBoostingClassifier(
        max_depth=5,
        learning_rate=0.05,
        max_iter=200,
        random_state=42,
        early_stopping=True,
        validation_fraction=0.2,
        n_iter_no_change=20,
    )
    
    # Complete pipeline
    pipeline = Pipeline([
        ("preprocess", preprocessor),
        ("model", model),
    ])
    
    # Time-series cross-validation
    n_splits = min(5, len(X) // 50) or 2
    tscv = TimeSeriesSplit(n_splits=n_splits)
    
    print(f"\n{'='*70}")
    print(f"CROSS-VALIDATION ({n_splits} folds)")
    print(f"{'='*70}")
    
    aucs = []
    precisions = []
    recalls = []
    
    for fold, (train_idx, test_idx) in enumerate(tscv.split(X), start=1):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        
        # Check if test set has both classes
        if y_test.nunique() < 2:
            print(f"Fold {fold}: Skipped (test set has only one class)")
            continue
        
        pipeline.fit(X_train, y_train)
        
        # Predictions
        y_pred = pipeline.predict(X_test)
        y_proba = pipeline.predict_proba(X_test)[:, 1]
        
        # Metrics
        auc = roc_auc_score(y_test, y_proba)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        
        aucs.append(auc)
        precisions.append(precision)
        recalls.append(recall)
        
        print(f"Fold {fold}: AUC={auc:.3f}, Precision={precision:.3f}, Recall={recall:.3f}")
    
    if aucs:
        print(f"\n{'='*70}")
        print(f"AVERAGE METRICS")
        print(f"{'='*70}")
        print(f"Mean AUC:       {np.mean(aucs):.3f} (±{np.std(aucs):.3f})")
        print(f"Mean Precision: {np.mean(precisions):.3f} (±{np.std(precisions):.3f})")
        print(f"Mean Recall:    {np.mean(recalls):.3f} (±{np.std(recalls):.3f})")
    
    # Train final model on all data
    print(f"\n{'='*70}")
    print(f"TRAINING FINAL MODEL ON ALL DATA")
    print(f"{'='*70}")
    
    pipeline.fit(X, y)
    
    # Evaluation on full dataset (for reference)
    y_pred_final = pipeline.predict(X)
    print("\nClassification Report (Full Dataset):")
    print(classification_report(y, y_pred_final, zero_division=0))
    
    # Save model bundle
    bundle = {
        "pipeline": pipeline,
        "feature_cols": feature_cols,
        "target_col": target_col,
        "categorical_cols": cat_cols,
        "numeric_cols": numeric_cols,
    }
    
    output_file = Path(output_path)
    joblib.dump(bundle, output_file)
    
    print(f"\n{'='*70}")
    print(f"MODEL SAVED: {output_file.absolute()}")
    print(f"{'='*70}")
    print(f"\nBundle contents:")
    print(f"  - pipeline: {type(pipeline).__name__}")
    print(f"  - feature_cols: {len(feature_cols)} features")
    print(f"  - target_col: {target_col}")
    print(f"\nTo use for predictions:")
    print(f"  python predict_personalized.py --model {output_file.name}")


# ============================================================================
# MAIN
# ============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train personalized asthma risk/flare model from MongoDB users and environment data"
    )
    parser.add_argument(
        "--out",
        default="flare_model.joblib",
        help="Output model file path (default: flare_model.joblib)"
    )
    parser.add_argument(
        "--target",
        choices=["risk", "flare_day"],
        default="risk",
        help="Target variable: 'risk' (symptom+env) or 'flare_day' (symptoms only)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Number of days of historical data to use (default: 90)"
    )
    parser.add_argument(
        "--min-users",
        type=int,
        default=1,
        help="Minimum number of users required (default: 1)"
    )
    args = parser.parse_args()
    
    # Connect to MongoDB
    uri = _mongo_uri()
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    
    try:
        client.admin.command("ping")
        print("✓ MongoDB connection successful")
    except Exception as e:
        print(f"✗ MongoDB connection failed: {e}", file=sys.stderr)
        return 1
    
    # Load users
    print("\nLoading user profiles and check-ins...")
    prof, checkins = load_users_from_mongo(client)
    
    if prof.empty or len(prof) < args.min_users:
        print(f"Not enough users found: {len(prof)} (need at least {args.min_users})", file=sys.stderr)
        return 1
    
    print(f"✓ Loaded {len(prof)} users with {len(checkins)} check-ins")
    
    # Load environmental data
    print(f"\nLoading environmental data (last {args.days} days)...")
    env_df = load_env_from_mongo(client, days=args.days)
    
    if env_df is None or env_df.empty:
        print("No environmental data found", file=sys.stderr)
        return 1
    
    print(f"✓ Loaded {len(env_df)} environmental records")
    
    # Enrich dataset
    print("\nMerging data and creating features...")
    df = enrich_dataset(env_df, prof, checkins)
    df = add_time_features(df)
    df = create_target(df, target_col=args.target)
    
    # Filter out rows with no valid target
    df = df.dropna(subset=[args.target])
    
    print(f"✓ Created {len(df)} training samples")
    
    # Check if we have both classes
    if df[args.target].nunique() < 2:
        print(f"Error: Target '{args.target}' has only one class. Need both 0 and 1.", file=sys.stderr)
        print(f"Target distribution: {df[args.target].value_counts().to_dict()}")
        return 1
    
    # Train model
    train_personalized_model(df, target_col=args.target, output_path=args.out)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
