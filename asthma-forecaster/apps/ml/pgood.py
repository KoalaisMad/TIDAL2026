#!/usr/bin/env python3
"""
Train a personalized risk/flare model. For use with predict_personalized.py ONLY.

Uses synthetic data from generate_personalized_data.py (daily characteristics:
wheeze, cough, chestTightness, exerciseMinutes linked to flare_day). Trains the same
way as D A T A/train_model.py: RandomForest + StandardScaler, time-based split,
optional --tune. Adds env time features (temp_swing, PM2.5 deltas/rolling, pollen lags)
and user symptom lags (wheeze_lag1, symptom_score, etc.). Outputs to a different path
(personalized_flare_model.joblib by default).

Do NOT use this model for the general environmental risk pipeline (predict_flare.py,
predict_risk.py, api/week). Those use flare_model.joblib from D A T A/train_model.py.

Data: D A T A/personalized_synthetic_data.csv (from apps.ml.generate_personalized_data).
Output: personalized_flare_model.joblib → used by predict_personalized.py (personalized tab).

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

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler


def add_symptom_lags(df: pd.DataFrame) -> pd.DataFrame:
    """Add per-user lags for wheeze, cough, chestTightness, exerciseMinutes and symptom_score."""
    df = df.copy()
    if "user_id" not in df.columns:
        return df
    check_cols = ["wheeze", "cough", "chestTightness", "exerciseMinutes"]
    if not any(c in df.columns for c in check_cols):
        return df
    df = df.sort_values(["user_id", "date"]).reset_index(drop=True)
    for col in check_cols:
        if col in df.columns:
            df[f"{col}_lag1"] = df.groupby("user_id")[col].shift(1).fillna(0)
    if {"wheeze", "cough", "chestTightness"}.issubset(df.columns):
        df["symptom_score"] = df["wheeze"] + df["cough"] + df["chestTightness"]
        df["symptom_score_lag1"] = df.groupby("user_id")["symptom_score"].shift(1).fillna(0)
    return df


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add time-derived env features (deltas, rolling, lags, interactions). With user_id, sort by (user_id, date) first so diffs/rolling are per-user."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    if "user_id" in df.columns:
        df = df.sort_values(["user_id", "date"]).reset_index(drop=True)
    else:
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
        if "user_id" in df.columns:
            df["pm25_delta"] = df.groupby("user_id")[pm].diff().fillna(0)
            df["pm25_roll3_mean"] = df.groupby("user_id")[pm].transform(lambda s: s.rolling(3, min_periods=1).mean().shift(1).fillna(0))
            df["pm25_roll7_mean"] = df.groupby("user_id")[pm].transform(lambda s: s.rolling(7, min_periods=1).mean().shift(1).fillna(0))
            df["pm25_lag1"] = df.groupby("user_id")[pm].shift(1).fillna(0)
        else:
            df["pm25_delta"] = df[pm].diff().fillna(0)
            df["pm25_roll3_mean"] = df[pm].rolling(3, min_periods=1).mean().shift(1).fillna(0)
            df["pm25_roll7_mean"] = df[pm].rolling(7, min_periods=1).mean().shift(1).fillna(0)
            df["pm25_lag1"] = df[pm].shift(1).fillna(0)
    if aqi in df.columns:
        if "user_id" in df.columns:
            df["aqi_roll3_mean"] = df.groupby("user_id")[aqi].transform(lambda s: s.rolling(3, min_periods=1).mean().shift(1).fillna(0))
            df["aqi_roll7_mean"] = df.groupby("user_id")[aqi].transform(lambda s: s.rolling(7, min_periods=1).mean().shift(1).fillna(0))
            df["aqi_lag1"] = df.groupby("user_id")[aqi].shift(1).fillna(0)
        else:
            df["aqi_roll3_mean"] = df[aqi].rolling(3, min_periods=1).mean().shift(1).fillna(0)
            df["aqi_roll7_mean"] = df[aqi].rolling(7, min_periods=1).mean().shift(1).fillna(0)
            df["aqi_lag1"] = df[aqi].shift(1).fillna(0)

    # Pollen total and lag
    if "pollen_total" in df.columns:
        df["pollen_total_lag1"] = df["pollen_total"].shift(1).fillna(0) if "user_id" not in df.columns else df.groupby("user_id")["pollen_total"].shift(1).fillna(0)
    elif {"pollen_tree", "pollen_grass", "pollen_weed"}.intersection(df.columns):
        pollen_cols = [c for c in ["pollen_tree", "pollen_grass", "pollen_weed"] if c in df.columns]
        df["pollen_total"] = df[pollen_cols].fillna(0).sum(axis=1)
        df["pollen_total_lag1"] = df["pollen_total"].shift(1).fillna(0) if "user_id" not in df.columns else df.groupby("user_id")["pollen_total"].shift(1).fillna(0)

    # Interactions
    hum = "humidity" if "humidity" in df.columns else "humidity_mean"
    wnd = "wind" if "wind" in df.columns else "wind_speed_kmh"
    if pm in df.columns and hum in df.columns:
        df["pm25_x_humidity"] = df[pm] * df[hum]
    if "pollen_total" in df.columns and wnd in df.columns:
        df["pollen_x_wind"] = df["pollen_total"] * df[wnd]

    return df


def prepare_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], object, object]:
    """
    Same as D A T A/train_model.prepare_features: build numeric feature matrix.
    Drops identifiers (including user_id) and target; encodes day_of_week and season; fills missing.
    Returns (X, feature_cols, le_dow, le_season) so encoders can be saved for prediction.
    """
    exclude = {"date", "locationid", "zip_code", "flare_day", "risk", "user_id"}
    df = df.copy()

    numeric_fill = df.select_dtypes(include=[np.number]).columns
    for col in numeric_fill:
        if col in exclude or col in ("flare_day", "risk"):
            continue
        if df[col].isna().any():
            med = df[col].median()
            df[col] = df[col].fillna(med if np.isfinite(med) else 0)

    le_dow = le_season = None
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
    return X, feature_cols, le_dow, le_season


def save_presentation_charts(
    out_dir: Path,
    model,
    feature_cols: list,
    target_names: list,
    classes: list,
    y_train,
    y_test,
    y_pred,
    y_prob,
    n_train: int,
    n_test: int,
) -> None:
    """Generate presentation charts explaining model training. Requires matplotlib."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Train/test split (sample counts)
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.bar(["Train", "Test"], [n_train, n_test], color=["#2ecc71", "#3498db"], edgecolor="black")
    ax.set_ylabel("Number of samples")
    ax.set_title("Time-based train/test split (personalized model)")
    for i, v in enumerate([n_train, n_test]):
        ax.text(i, v + max(n_train, n_test) * 0.02, str(v), ha="center", fontweight="bold")
    plt.tight_layout()
    plt.savefig(out_dir / "01_train_test_split.png", dpi=150, bbox_inches="tight")
    plt.close()

    # 2. Target distribution (train vs test)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, y, label in zip(axes, [y_train, y_test], ["Train", "Test"]):
        unique, counts = np.unique(y, return_counts=True)
        names = [target_names[list(classes).index(u)] if u in classes else str(u) for u in unique]
        ax.bar(names, counts, color="#9b59b6", edgecolor="black")
        ax.set_title(f"Target distribution ({label})")
        ax.set_ylabel("Count")
    plt.suptitle("Class distribution in train and test sets")
    plt.tight_layout()
    plt.savefig(out_dir / "02_target_distribution.png", dpi=150, bbox_inches="tight")
    plt.close()

    # 3. Feature importances (RandomForest)
    if hasattr(model, "feature_importances_"):
        imp = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=True)
        top_n = min(15, len(imp))
        imp = imp.tail(top_n)
        fig, ax = plt.subplots(figsize=(8, max(4, top_n * 0.35)))
        ax.barh(imp.index, imp.values, color="#3498db", edgecolor="black")
        ax.set_xlabel("Importance")
        ax.set_title("Feature importances (Random Forest, personalized)")
        plt.tight_layout()
        plt.savefig(out_dir / "03_feature_importances.png", dpi=150, bbox_inches="tight")
        plt.close()

    # 4. Confusion matrix
    cm = confusion_matrix(y_test, y_pred, labels=classes)
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(classes)))
    ax.set_yticks(range(len(classes)))
    ax.set_xticklabels(target_names)
    ax.set_yticklabels(target_names)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else "black")
    plt.colorbar(im, ax=ax, label="Count")
    ax.set_title("Confusion matrix (test set)")
    plt.tight_layout()
    plt.savefig(out_dir / "04_confusion_matrix.png", dpi=150, bbox_inches="tight")
    plt.close()

    # 5. ROC curve (binary) or one-vs-rest (multiclass)
    if y_prob is not None and len(np.unique(y_test)) > 1:
        n_classes = y_prob.shape[1]
        if n_classes == 2:
            pos_idx = 1 if 1 in classes else 0
            fpr, tpr, _ = roc_curve(y_test, y_prob[:, pos_idx], pos_label=classes[pos_idx])
            auc = roc_auc_score(y_test, y_prob[:, pos_idx])
            fig, ax = plt.subplots(figsize=(6, 5))
            ax.plot(fpr, tpr, color="#e74c3c", lw=2, label=f"ROC (AUC = {auc:.3f})")
            ax.plot([0, 1], [0, 1], "k--", lw=1)
            ax.set_xlabel("False positive rate")
            ax.set_ylabel("True positive rate")
            ax.set_title("ROC curve (test set)")
            ax.legend()
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
        else:
            from sklearn.preprocessing import label_binarize
            y_test_bin = label_binarize(y_test, classes=classes)
            fig, ax = plt.subplots(figsize=(6, 5))
            for i in range(n_classes):
                fpr, tpr, _ = roc_curve(y_test_bin[:, i], y_prob[:, i])
                auc_i = roc_auc_score(y_test_bin[:, i], y_prob[:, i])
                ax.plot(fpr, tpr, lw=2, label=f"{target_names[i]} (AUC = {auc_i:.3f})")
            ax.plot([0, 1], [0, 1], "k--", lw=1)
            ax.set_xlabel("False positive rate")
            ax.set_ylabel("True positive rate")
            ax.set_title("ROC curves – one-vs-rest (test set)")
            ax.legend(loc="lower right", fontsize=8)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
        plt.tight_layout()
        plt.savefig(out_dir / "05_roc_curve.png", dpi=150, bbox_inches="tight")
        plt.close()

    # 6. Metrics summary
    acc = accuracy_score(y_test, y_pred)
    f1_macro = f1_score(y_test, y_pred, average="macro", zero_division=0)
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.bar(["Accuracy", "Macro F1"], [acc, f1_macro], color=["#27ae60", "#f39c12"], edgecolor="black")
    ax.set_ylabel("Score")
    ax.set_ylim(0, 1)
    ax.set_title("Test set metrics")
    for i, v in enumerate([acc, f1_macro]):
        ax.text(i, v + 0.03, f"{v:.3f}", ha="center", fontweight="bold")
    plt.tight_layout()
    plt.savefig(out_dir / "06_metrics_summary.png", dpi=150, bbox_inches="tight")
    plt.close()

    print(f"Presentation charts saved to {out_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Train personalized risk/flare model (same procedure as train_model.py, extra user-specific features)"
    )
    _script_dir = Path(__file__).resolve().parent
    _data_dir = _script_dir.parent / "D A T A"
    parser.add_argument(
        "--data",
        default=str(_data_dir / "personalized_synthetic_data.csv"),
        help="CSV with daily characteristics (wheeze, cough, chestTightness, exerciseMinutes) + flare_day; from generate_personalized_data.py",
    )
    parser.add_argument(
        "--out",
        default=str(_data_dir / "personalized_flare_model.joblib"),
        help="Output model path (for predict_personalized.py only)",
    )
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument(
        "--tune",
        action="store_true",
        help="Run hyperparameter search (time-series CV on train) to reduce overfitting",
    )
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument(
        "--charts-only",
        action="store_true",
        help="Generate presentation charts only; do not save the model (current models are not replaced)",
    )
    parser.add_argument(
        "--charts-dir",
        default=str(_script_dir.parent / "presentation_charts_personalized"),
        help="Directory for chart output when using --charts-only",
    )
    args = parser.parse_args()

    path = Path(args.data)
    if not path.exists():
        print(f"Data file not found: {path}", flush=True)
        return 1

    df = pd.read_csv(path)

    if "risk" in df.columns:
        target_col = "risk"
        target_names = [f"risk_{i}" for i in range(1, 6)]
    elif "flare_day" in df.columns:
        target_col = "flare_day"
        target_names = ["non_flare", "flare"]
    else:
        print("CSV must contain 'risk' (1-5) or 'flare_day' (0/1).", flush=True)
        return 1

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # User-specific/time-derived features (then same prepare as train_model.py)
    df = add_time_features(df)
    X, feature_cols, le_dow, le_season = prepare_features(df)
    y = df[target_col].astype(int).values

    n = len(y)
    if n < 20:
        print(f"Too few rows ({n}). Need at least 20.", flush=True)
        return 1

    n_test = max(1, int(n * args.test_ratio))
    n_train = n - n_test
    X_train, X_test = X.iloc[:n_train], X.iloc[n_train:]
    y_train, y_test = y[:n_train], y[n_train:]

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    base_rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=12,
        max_features="sqrt",
        class_weight="balanced",
        random_state=args.random_state,
    )

    if args.tune:
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

    if hasattr(model, "feature_importances_"):
        imp = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False)
        print("Top feature importances:")
        for name, val in imp.head(10).items():
            print(f"  {name}: {val:.3f}")

    # Risk 1–5 sanity check (same mapping as predict_personalized)
    if target_col == "risk":
        scores_1_5 = np.clip(np.sum(y_prob * model.classes_, axis=1), 1.0, 5.0)
    else:
        idx1 = np.where(model.classes_ == 1)[0]
        p_flare = y_prob[:, idx1[0]] if len(idx1) else y_prob[:, -1]
        scores_1_5 = np.clip(1.0 + 4.0 * p_flare, 1.0, 5.0)
    print(f"  Risk 1–5 (test): min={scores_1_5.min():.2f}, max={scores_1_5.max():.2f}, mean={scores_1_5.mean():.2f}")

    pipe = Pipeline([("scaler", scaler), ("model", model)])
    target_type = "risk_1_5" if target_col == "risk" else "flare_binary"

    if args.charts_only:
        classes = model.classes_.tolist() if hasattr(model, "classes_") else sorted(np.unique(np.r_[y_train, y_test]).tolist())
        save_presentation_charts(
            Path(args.charts_dir),
            model=model,
            feature_cols=feature_cols,
            target_names=target_names,
            classes=classes,
            y_train=y_train,
            y_test=y_test,
            y_pred=y_pred,
            y_prob=y_prob,
            n_train=n_train,
            n_test=n_test,
        )
        print("Charts-only run: model was not saved (current models unchanged).")
        return 0

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
            "le_dow": le_dow,
            "le_season": le_season,
        },
        out_path,
    )
    print(f"Saved to {out_path} (output: risk score 1–5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
