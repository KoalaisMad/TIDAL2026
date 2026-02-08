#!/usr/bin/env python3
"""
Train a personalized risk/flare model. For use with predict_personalized.py ONLY.

Do NOT use this model for the general environmental risk pipeline (predict_flare.py,
predict_risk.py, api/week). Those use flare_model.joblib from D A T A/train_model.py.

Output: personalized_flare_model.joblib (default) → used by predict_personalized.py

The model output is always a risk score from 1 to 5:
- If trained on "risk" (1–5): expected value of class probabilities in [1, 5].
- If trained on "flare_day" (0/1): 1 + 4*P(flare), mapping [0,1] to [1, 5].
Saved bundle has output_scale="1_to_5". predict_personalized.py uses the same mapping.
"""
import argparse
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import HistGradientBoostingClassifier


class Risk1To5Predictor:
    """
    Wrapper so the model always outputs a risk score in the range [1, 5].
    - For risk (1-5): expected value of class probabilities.
    - For flare (0/1): 1 + 4 * P(flare), mapping [0,1] to [1,5].
    """

    def __init__(self, pipeline: Pipeline, target_type: str, classes: np.ndarray):
        self.pipeline = pipeline
        self.target_type = target_type
        self.classes = np.asarray(classes)

    def predict_risk_1_to_5(self, X) -> np.ndarray:
        """Return risk score(s) in [1, 5] for each row in X, rounded to 2 decimal places."""
        proba = self.pipeline.predict_proba(X)
        if self.target_type == "risk_1_5":
            # Expected value: sum over classes (1..5) * P(class)
            raw = np.clip(np.sum(proba * self.classes, axis=1), 1.0, 5.0)
        else:
            # flare_binary: 1 + 4 * P(flare)
            idx1 = np.where(self.classes == 1)[0]
            if len(idx1) == 0:
                idx1 = np.array([-1])  # use last column as fallback
            p_flare = proba[:, idx1[0]]
            raw = np.clip(1.0 + 4.0 * p_flare, 1.0, 5.0)
        return np.round(raw.astype(float), 2)


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Temp swing (support temp_min/max or temp_min_c/max_c)
    if {"temp_max_c", "temp_min_c"}.issubset(df.columns):
        df["temp_swing"] = df["temp_max_c"] - df["temp_min_c"]
    elif {"temp_max", "temp_min"}.issubset(df.columns):
        df["temp_swing"] = df["temp_max"] - df["temp_min"]

    # Deltas, rolling, lag – use PM2_5_mean/AQI (dataset convention) or pm25_mean/aqi
    pm = "PM2_5_mean" if "PM2_5_mean" in df.columns else "pm25_mean"
    aqi = "AQI" if "AQI" in df.columns else "aqi"
    if pm in df.columns:
        df["pm25_delta"] = df[pm].diff()
        df["pm25_roll3_mean"] = df[pm].rolling(3, min_periods=1).mean().shift(1)
        df["pm25_roll7_mean"] = df[pm].rolling(7, min_periods=1).mean().shift(1)
        df["pm25_lag1"] = df[pm].shift(1)
    if aqi in df.columns:
        df["aqi_roll3_mean"] = df[aqi].rolling(3, min_periods=1).mean().shift(1)
        df["aqi_roll7_mean"] = df[aqi].rolling(7, min_periods=1).mean().shift(1)
        df["aqi_lag1"] = df[aqi].shift(1)

    # Pollen total and lag
    if "pollen_total" in df.columns:
        df["pollen_total_lag1"] = df["pollen_total"].shift(1)
    elif {"pollen_tree", "pollen_grass", "pollen_weed"}.intersection(df.columns):
        pollen_cols = [c for c in ["pollen_tree", "pollen_grass", "pollen_weed"] if c in df.columns]
        df["pollen_total"] = df[pollen_cols].fillna(0).sum(axis=1)
        df["pollen_total_lag1"] = df["pollen_total"].shift(1)

    # Interactions
    hum = "humidity" if "humidity" in df.columns else "humidity_mean"
    wnd = "wind" if "wind" in df.columns else "wind_speed_kmh"
    if pm in df.columns and hum in df.columns:
        df["pm25_x_humidity"] = df[pm] * df[hum]
    if "pollen_total" in df.columns and wnd in df.columns:
        df["pollen_x_wind"] = df["pollen_total"] * df[wnd]

    return df


def main():
    parser = argparse.ArgumentParser()
    _script_dir = Path(__file__).resolve().parent
    _data_dir = _script_dir.parent / "D A T A"
    parser.add_argument("--data", default=str(_data_dir / "dataset_two_weeks.csv"))
    parser.add_argument("--out", default=str(_data_dir / "personalized_flare_model.joblib"),
                        help="Output model path (for predict_personalized.py only)")
    parser.add_argument("--test-ratio", type=float, default=0.2)
    args = parser.parse_args()

    path = Path(args.data)
    if not path.exists():
        print(f"Data file not found: {path}", flush=True)
        return 1

    df = pd.read_csv(path)

    # target
    if "risk" in df.columns:
        target_col = "risk"
        target_names = [f"risk_{i}" for i in range(1, 6)]
    elif "flare_day" in df.columns:
        target_col = "flare_day"
        target_names = ["non_flare", "flare"]
    else:
        print("CSV must contain 'risk' (1-5) or 'flare_day' (0/1).", flush=True)
        return 1

    df = add_time_features(df)

    # time split
    n = len(df)
    if n < 20:
        print(f"Too few rows ({n}). Need at least 20.", flush=True)
        return 1

    n_test = max(1, int(n * args.test_ratio))
    n_train = n - n_test
    train_df = df.iloc[:n_train].copy()
    test_df  = df.iloc[n_train:].copy()

    y_train = train_df[target_col].astype(int).values
    y_test  = test_df[target_col].astype(int).values

    # drop non-features
    exclude = {"date", "locationid", "zip_code", "flare_day", "risk"}
    feature_cols = [c for c in df.columns if c not in exclude]

    X_train = train_df[feature_cols]
    X_test  = test_df[feature_cols]

    # detect categorical vs numeric
    cat_cols = [c for c in X_train.columns if X_train[c].dtype == "object"]
    num_cols = [c for c in X_train.columns if c not in cat_cols]

    transformers = []
    if cat_cols:
        transformers.append(("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols))
    if num_cols:
        transformers.append(("num", "passthrough", num_cols))
    if not transformers:
        print("No feature columns available.", flush=True)
        return 1

    pre = ColumnTransformer(transformers=transformers)

    model = HistGradientBoostingClassifier(max_depth=6, learning_rate=0.08)

    pipe = Pipeline([("pre", pre), ("model", model)])

    pipe.fit(X_train, y_train)
    y_pred = pipe.predict(X_test)
    y_proba = pipe.predict_proba(X_test)

    print("Metrics (test set):")
    print(f"  Accuracy:  {accuracy_score(y_test, y_pred):.3f}")
    print(f"  Macro F1:  {f1_score(y_test, y_pred, average='macro', zero_division=0):.3f}")
    # Mean predicted probability for the chosen class
    classes = pipe.named_steps["model"].classes_
    idx = [np.where(classes == p)[0][0] for p in y_pred]
    proba_of_pred = np.mean([y_proba[i, idx[i]] for i in range(len(y_pred))])
    print(f"  Mean prob: {proba_of_pred:.3f}")
    report_labels = list(range(1, 6)) if target_col == "risk" else [0, 1]
    print(classification_report(y_test, y_pred, labels=report_labels, target_names=target_names, zero_division=0))

    # Ensure output is always 1–5: build wrapper and sanity-check
    target_type = "risk_1_5" if target_col == "risk" else "flare_binary"
    classes = pipe.named_steps["model"].classes_
    risk_1_to_5 = Risk1To5Predictor(pipe, target_type, classes)
    scores_1_5 = risk_1_to_5.predict_risk_1_to_5(X_test)
    print(f"  Risk 1–5 (test): min={scores_1_5.min():.2f}, max={scores_1_5.max():.2f}, mean={scores_1_5.mean():.2f}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline": pipe,
            "feature_cols": feature_cols,
            "target_col": target_col,
            "target_type": target_type,
            "target_names": target_names,
            "output_scale": "1_to_5",
        },
        out_path,
    )
    print(f"Saved to {out_path} (output: risk score 1–5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
