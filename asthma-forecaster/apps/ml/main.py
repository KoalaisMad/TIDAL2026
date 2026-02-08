"""
Asthma flare prediction: train a classifier to predict flare_nextday from TIDAL daily env data.
Data loading and feature logic live in data.py (same schema as generated data).

Usage:
  # 1. Generate data into a collection (e.g. ml_daily):
  #    python -m apps.ml.generate_ml_data --collection ml_daily --lat 37.77 --lon -122.42 --start 2026-01-01 --end 2026-02-07
  # 2. Train on that collection:
  #    ML_ENV_COLL=ml_daily python -m apps.ml.main --demo-labels
  # Or use default collection (pulldata): python -m apps.ml.main --demo-labels
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

# Ensure data.py is importable (same package)
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

# Canonical data layer: load_env, load_labels, add_time_features
from apps.ml.data import get_client, load_env, load_labels, add_time_features


def build_and_train(df: pd.DataFrame, output_path: str = "asthma_flare_model.joblib") -> None:
    target = "flare_nextday"
    cat_cols = [c for c in ["day_of_week", "season"] if c in df.columns]
    drop_cols = {"date", "latitude", "longitude", "zip_code", "location_id", target}
    feature_cols = [c for c in df.columns if c not in drop_cols]
    X = df[feature_cols]
    y = df[target].astype(int)

    n_splits = min(4, len(X) // 20) or 2
    tscv = TimeSeriesSplit(n_splits=n_splits)
    numeric_cols = [c for c in feature_cols if c not in cat_cols]
    pre = ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), numeric_cols),
            ("cat", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore")),
            ]), cat_cols),
        ],
        remainder="drop",
    )
    model = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.06, max_iter=300)
    pipe = Pipeline([("preprocess", pre), ("model", model)])

    aucs = []
    for fold, (tr, te) in enumerate(tscv.split(X), start=1):
        pipe.fit(X.iloc[tr], y.iloc[tr])
        proba = pipe.predict_proba(X.iloc[te])[:, 1]
        auc = roc_auc_score(y.iloc[te], proba)
        aucs.append(auc)
        print(f"Fold {fold} AUROC: {auc:.3f}")
    print(f"\nMean AUROC: {sum(aucs)/len(aucs):.3f}")

    pipe.fit(X, y)
    out_file = Path(__file__).resolve().parent / output_path
    joblib.dump(pipe, out_file)
    print(f"\nSaved: {out_file}")

    last_n = max(30, len(X) // 5)
    preds = pipe.predict(X.tail(last_n))
    print("\nClassification report (last window):")
    print(classification_report(y.tail(last_n), preds))


def main():
    parser = argparse.ArgumentParser(description="Train asthma flare model; data from data.py (env + labels)")
    parser.add_argument("--demo-labels", action="store_true", help="Use synthetic labels from env")
    parser.add_argument("--env-coll", type=str, default=None, help="MongoDB collection for env data (overrides ML_ENV_COLL)")
    parser.add_argument("--output", default="asthma_flare_model.joblib", help="Output model path")
    args = parser.parse_args()

    client = get_client()
    env = load_env(client, collection_name=args.env_coll)
    env = add_time_features(env)

    labels = load_labels(client)
    if labels.empty and args.demo_labels:
        random.seed(42)
        env_with_next = env.copy()
        env_with_next["date"] = pd.to_datetime(env_with_next["date"])
        g = env_with_next.groupby("location_id", group_keys=False)
        env_with_next["AQI_next"] = g["AQI"].shift(-1)
        env_with_next["PM2_5_mean_next"] = g["PM2_5_mean"].shift(-1)
        rule = (env_with_next["AQI_next"] > 50) | (env_with_next["PM2_5_mean_next"] > 15)
        env_with_next["flare_nextday"] = rule.fillna(False).astype(int)
        missing = env_with_next["flare_nextday"].isna()
        if missing.any():
            env_with_next.loc[missing, "flare_nextday"] = [random.randint(0, 1) for _ in range(missing.sum())]
        if env_with_next["flare_nextday"].nunique() < 2:
            n = len(env_with_next)
            idx = env_with_next.index.tolist()
            random.shuffle(idx)
            for ind in idx[: max(1, n // 2)]:
                env_with_next.loc[ind, "flare_nextday"] = 1 - env_with_next.loc[ind, "flare_nextday"]
        df = env_with_next.drop(columns=["AQI_next", "PM2_5_mean_next"], errors="ignore").reset_index(drop=True)
        print("Using --demo-labels: synthetic flare_nextday (with variety).")
    elif not labels.empty:
        df = env.merge(labels, on="date", how="inner")
    else:
        print(
            "No labels. Run: python -m apps.ml.seed_demo_labels  or use --demo-labels.",
            file=sys.stderr,
        )
        sys.exit(1)

    if df["flare_nextday"].nunique() < 2:
        print("Need both 0 and 1 in flare_nextday.", file=sys.stderr)
        sys.exit(1)

    build_and_train(df, output_path=args.output)


if __name__ == "__main__":
    main()
