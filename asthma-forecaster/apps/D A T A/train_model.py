#!/usr/bin/env python3
"""
Train a classifier to predict allergy risk 1-5 from the dataset built by dataset.py.

Reads the CSV (e.g. dataset_two_weeks.csv), prepares numeric + encoded categorical
features, uses a time-based train/test split, and saves a joblib bundle (model +
scaler + feature names). Target: risk 1-5 (1=lowest, 5=highest). If CSV has no
'risk' column, falls back to binary 'flare_day' (0/1).

INSTALL (if needed):
  python -m pip install pandas scikit-learn joblib

USAGE (from D A T A folder):
  python train_model.py
  python train_model.py --data dataset_two_weeks.csv --out flare_model.joblib --test-ratio 0.2
"""

import argparse
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV
from sklearn.preprocessing import LabelEncoder, StandardScaler


def prepare_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Build numeric feature matrix from the dataset CSV.
    Drops identifiers and target; encodes day_of_week and season; fills missing.
    """
    # Exclude target and non-features
    exclude = {"date", "locationid", "zip_code", "flare_day", "risk"}
    # Optional: drop lat/lon to keep model location-agnostic; include them if you want location-aware
    # exclude |= {"latitude", "longitude"}

    df = df.copy()

    # Fill missing numeric (AQI, pollen often empty in dataset.py output)
    numeric_fill = df.select_dtypes(include=[np.number]).columns
    for col in numeric_fill:
        if col in exclude or col in ("flare_day", "risk"):
            continue
        if df[col].isna().any():
            med = df[col].median()
            df[col] = df[col].fillna(med if np.isfinite(med) else 0)

    # Encode categoricals
    if "day_of_week" in df.columns:
        le_dow = LabelEncoder()
        df["day_of_week"] = df["day_of_week"].astype(str)
        df["day_of_week"] = le_dow.fit_transform(df["day_of_week"])
    if "season" in df.columns:
        le_season = LabelEncoder()
        df["season"] = df["season"].astype(str)
        df["season"] = le_season.fit_transform(df["season"])
    if "holiday_flag" in df.columns:
        df["holiday_flag"] = df["holiday_flag"].astype(int)

    feature_cols = [c for c in df.columns if c not in exclude]
    X = df[feature_cols].copy()
    X = X.fillna(0).astype(float)
    return X, feature_cols


def main():
    parser = argparse.ArgumentParser(description="Train allergy risk 1-5 (or flare_day) classifier from dataset CSV")
    _script_dir = Path(__file__).resolve().parent
    parser.add_argument("--data", default=str(_script_dir / "dataset_two_weeks.csv"), help="Path to CSV from dataset.py")
    parser.add_argument("--out", default="flare_model.joblib", help="Output joblib path")
    parser.add_argument("--test-ratio", type=float, default=0.2, help="Fraction of rows (by time) for test set")
    parser.add_argument("--tune", action="store_true", help="Run hyperparameter search (time-series CV on train) to reduce overfitting")
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    path = Path(args.data)
    print(f"Using data: {path.resolve()}", flush=True)
    if not path.exists():
        print(f"Data file not found: {path}", flush=True)
        return 1

    print("Loading CSV...", flush=True)
    df = pd.read_csv(path)
    if "risk" in df.columns:
        target_col = "risk"
        target_names = [f"risk_{i}" for i in range(1, 6)]
    elif "flare_day" in df.columns:
        target_col = "flare_day"
        target_names = ["non_flare", "flare"]
    else:
        print("CSV must contain 'risk' (1-5) or 'flare_day' column.", flush=True)
        return 1

    print(f"Rows: {len(df)}, target={target_col}, training...", flush=True)
    # Sort by date for time-based split
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    X, feature_cols = prepare_features(df)
    y = df[target_col].astype(int).values

    n = len(y)
    if n < 20:
        print(f"Too few rows ({n}). Need at least 20.")
        return 1

    # Time-based split: last test_ratio of rows are test
    n_test = max(1, int(n * args.test_ratio))
    n_train = n - n_test
    X_train, X_test = X.iloc[:n_train], X.iloc[n_train:]
    y_train, y_test = y[:n_train], y[n_train:]

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    # Defaults: regularized to avoid overfitting (shallower trees, larger leaves)
    base_rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=12,
        max_features="sqrt",
        class_weight="balanced",
        random_state=args.random_state,
    )

    if args.tune:
        # Time-series CV on train only; pick params that generalize
        tscv = TimeSeriesSplit(n_splits=3)
        param_dist = {
            "max_depth": [6, 8, 10],
            "min_samples_leaf": [10, 15, 20],
            "n_estimators": [150, 200, 250],
        }
        search = RandomizedSearchCV(
            base_rf,
            param_distributions=param_dist,
            n_iter=12,
            scoring="f1_macro",
            cv=tscv,
            random_state=args.random_state,
            n_jobs=-1,
            verbose=0,
        )
        search.fit(X_train_s, y_train)
        model = search.best_estimator_
        print(f"Tuned params (best F1 macro on CV): {search.best_params_}", flush=True)
    else:
        model = base_rf
        model.fit(X_train_s, y_train)

    y_pred = model.predict(X_test_s)
    y_prob = model.predict_proba(X_test_s) if hasattr(model, "predict_proba") else None

    print("Metrics (test set):")
    print(f"  Accuracy:   {accuracy_score(y_test, y_pred):.3f}")
    print(f"  Macro F1:  {f1_score(y_test, y_pred, average='macro', zero_division=0):.3f}")
    if y_prob is not None and len(np.unique(y_test)) > 1:
        try:
            auc = roc_auc_score(y_test, y_prob, multi_class="ovr", average="macro")
            print(f"  ROC-AUC:    {auc:.3f}")
        except Exception:
            pass
    report_labels = list(range(1, 6)) if target_col == "risk" else [0, 1]
    print(classification_report(y_test, y_pred, labels=report_labels, target_names=target_names, zero_division=0))

    # Feature importances
    if hasattr(model, "feature_importances_"):
        imp = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False)
        print("Top feature importances:")
        for name, val in imp.head(10).items():
            print(f"  {name}: {val:.3f}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "scaler": scaler,
            "feature_order": feature_cols,
            "target_type": "risk_1_5" if target_col == "risk" else "flare_binary",
            "target_names": target_names,
        },
        out_path,
    )
    print(f"Saved model + scaler to {out_path} (predicts {target_col})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr, flush=True)
        raise
