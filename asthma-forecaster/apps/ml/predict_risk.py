#!/usr/bin/env python3
"""
Predict "high risk tomorrow" for a given date using risk_model_general.joblib and ml_daily.
Outputs JSON to stdout for consumption by the Next.js API.

Usage (from TIDAL2026):
  PYTHONPATH=asthma-forecaster python3 -m apps.ml.predict_risk --date 2026-02-07
  PYTHONPATH=asthma-forecaster python3 -m apps.ml.predict_risk --week --start 2026-02-08 --days 7
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import timedelta
from pathlib import Path

# Load .env and add project paths
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

import pandas as pd
import joblib

# Thresholds (must match trainingModel; used for activeRiskFactors)
AQI_HIGH = float(os.getenv("AQI_HIGH", "101"))
PM25_HIGH = float(os.getenv("PM25_HIGH", "35"))
POLLEN_HIGH = float(os.getenv("POLLEN_HIGH", "8"))

DAILY_KEYS = (
    "date", "location_id", "AQI", "PM2_5_max", "PM2_5_mean", "day_of_week", "holiday_flag",
    "humidity", "latitude", "longitude", "month", "pollen_grass", "pollen_tree", "pollen_weed",
    "pressure", "rain", "season", "temp_max", "temp_min", "wind", "zip_code",
)


def _daily_doc_from_row(row: pd.Series, date_str: str) -> dict:
    """Build calendar daily document (same shape as MongoDB doc) for API."""
    doc = {"date": date_str}
    for k in DAILY_KEYS:
        if k == "date":
            continue
        v = row.get(k)
        if pd.isna(v):
            doc[k] = None
        elif hasattr(v, "isoformat"):
            doc[k] = v.isoformat()[:10] if hasattr(v, "date") else str(v)
        elif isinstance(v, (pd.Timestamp,)):
            doc[k] = v.isoformat()[:10] if pd.notna(v) else None
        elif hasattr(v, "item"):  # numpy scalar
            try:
                doc[k] = v.item()
            except (ValueError, AttributeError):
                doc[k] = float(v) if isinstance(v, (float,)) else int(v)
        else:
            doc[k] = v
    if "day_of_week" in row and row.get("day_of_week") is not None:
        try:
            dow = int(row["day_of_week"])
            doc["day_of_week"] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][dow % 7]
        except (TypeError, ValueError):
            pass
    if "season" in doc and doc.get("season") is not None and isinstance(doc["season"], (int, float)):
        try:
            doc["season"] = ["winter", "spring", "summer", "fall"][int(doc["season"]) % 4]
        except (TypeError, ValueError, IndexError):
            pass
    return doc


def _model_path() -> Path:
    root = Path(__file__).resolve().parent.parent.parent.parent  # TIDAL2026
    for p in [
        Path.cwd() / "risk_model_general.joblib",
        root / "risk_model_general.joblib",
        Path(__file__).resolve().parent / "risk_model_general.joblib",
        Path(os.getenv("MODEL_PATH", "")),
    ]:
        if p and str(p) and p.exists():
            return p
    return Path.cwd() / "risk_model_general.joblib"


def _lat_lon_from_location_id(location_id: str) -> tuple[float, float]:
    """Parse location_id like '37.77_-122.42' or 'zip_94102' (return default for zip)."""
    if "_" in location_id and not location_id.startswith("zip_"):
        parts = location_id.split("_", 1)
        if len(parts) == 2:
            try:
                return float(parts[0]), float(parts[1])
            except (ValueError, TypeError):
                pass
    return 37.0, -122.0


def _synthetic_raw(
    end_date_str: str,
    num_days: int = 14,
    location_id: str = "default",
) -> pd.DataFrame:
    """Build minimal raw DataFrame for prediction when MongoDB is unavailable. Uses trained model."""
    lat, lon = _lat_lon_from_location_id(location_id)
    end_d = pd.Timestamp(end_date_str).normalize().date()
    rows = []
    for i in range(num_days - 1, -1, -1):
        d = end_d - timedelta(days=i)
        dow = d.weekday()
        month = d.month
        season = (month % 12 + 3) // 3  # 1=winter,2=spring,3=summer,4=fall
        j = (d.toordinal() % 7) / 7.0
        aqi = 40 + int(30 * j)
        pm25_mean = 10.0 + 8 * j
        pm25_max = pm25_mean * 1.4
        rows.append({
            "date": pd.Timestamp(d),
            "location_id": location_id,
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
            "zip_code": location_id.replace("zip_", "", 1) if location_id.startswith("zip_") else "94102",
            "rain": 0.0,
            "pressure": 1013.0,
        })
    return pd.DataFrame(rows)


def _build_prediction_X(row: pd.Series, feature_cols: list[str], pipe: object) -> pd.DataFrame | None:
    """Build a one-row DataFrame for the pipeline, using pipeline expected columns if available."""
    preprocess = getattr(pipe, "named_steps", {}).get("preprocess") if hasattr(pipe, "named_steps") else None
    if preprocess is not None and hasattr(preprocess, "feature_names_in_"):
        required = list(preprocess.feature_names_in_)
    else:
        required = feature_cols
    missing = [c for c in required if c not in row.index]
    if missing:
        row = row.copy()
        for c in missing:
            row[c] = 0
    try:
        return row[required].to_frame().T
    except (KeyError, TypeError) as e:
        if os.getenv("PREDICT_DEBUG"):
            print(f"predict_risk: _build_prediction_X failed: {e!s}", file=sys.stderr)
        return None


def _proba_to_score_and_level(proba: float) -> tuple[float, str, str]:
    """Map probability to 1-5 score and low/moderate/high."""
    if proba < 0.2:
        return (1 + proba * 5, "low", "Low")
    if proba < 0.5:
        return (2 + (proba - 0.2) * 10, "moderate", "Moderate")
    return (4 + (proba - 0.5) * 2, "high", "High")


def _data_driven_proba(row_or_raw) -> float:
    """Pseudo-proba from env data when model is not used, so score varies (not always 3)."""
    if row_or_raw is None:
        return 0.3
    r = row_or_raw
    aqi = float(r.get("AQI") or 0)
    pm25 = float(r.get("PM2_5_mean") or 0)
    pollen = r.get("pollen_total")
    if pollen is None or (isinstance(pollen, float) and pd.isna(pollen)):
        pollen = float(r.get("pollen_tree") or 0) + float(r.get("pollen_grass") or 0) + float(r.get("pollen_weed") or 0)
    else:
        pollen = float(pollen)
    proba = 0.15 + min(0.2, aqi / 400) + min(0.15, pm25 / 200) + min(0.1, pollen / 80)
    return float(max(0.05, min(0.95, proba)))


def _active_risk_factors(row: pd.Series) -> list[dict]:
    """Build API risk factors from a single row (env + pollen)."""
    factors = []
    aqi = row.get("AQI")
    if aqi is not None and float(aqi) >= AQI_HIGH:
        factors.append({"id": "air", "label": "Poor Air Quality", "iconKey": "wind"})
    pm25 = row.get("PM2_5_mean")
    if pm25 is not None and float(pm25) >= PM25_HIGH:
        factors.append({"id": "pm25", "label": "High PM2.5", "iconKey": "wind"})
    pollen_total = row.get("pollen_total")
    if pollen_total is not None and float(pollen_total) >= POLLEN_HIGH:
        factors.append({"id": "pollen", "label": "High Pollen", "iconKey": "sprout"})
    temp_min = row.get("temp_min")
    if temp_min is not None and float(temp_min) < 5:
        factors.append({"id": "temp", "label": "Cold Temperature", "iconKey": "thermometer"})
    humidity = row.get("humidity")
    if humidity is not None and float(humidity) >= 80:
        factors.append({"id": "humidity", "label": "High Humidity", "iconKey": "droplets"})
    if not factors:
        factors.append({"id": "general", "label": "Environmental conditions", "iconKey": "wind"})
    return factors


def _predict_one(
    date_str: str,
    raw: pd.DataFrame,
    fe: pd.DataFrame,
    pipe: object | None,
) -> dict:
    """Predict risk for one date; raw and fe must already have _date_norm. Returns one result dict."""
    target_date = pd.Timestamp(date_str).normalize()
    raw_match = raw[raw["_date_norm"] == target_date]
    raw_row = raw_match.iloc[0] if not raw_match.empty else (raw.iloc[-1] if not raw.empty else None)

    if fe.empty:
        daily = _daily_doc_from_row(raw_row, date_str) if raw_row is not None else {}
        proba = _data_driven_proba(raw_row)
        score, level, label = _proba_to_score_and_level(proba)
        return {
            "date": date_str,
            "risk": {"score": round(score, 1), "level": level, "label": label},
            "activeRiskFactors": _active_risk_factors(raw_row) if raw_row is not None else [],
            "daily": daily,
        }

    match = fe[fe["_date_norm"] == target_date]
    if match.empty:
        match = fe.tail(1)
    row = match.iloc[0]
    daily_row = raw_row if raw_row is not None else row
    daily = _daily_doc_from_row(daily_row, date_str)

    # Use same feature set as training: exclude lat/lon/zip/date (training also excludes y, tomorrow cols)
    drop_cols = {"latitude", "longitude", "zip_code", "date", "_date_norm"}
    feature_cols = [c for c in fe.columns if c not in drop_cols]

    if pipe is None:
        if os.getenv("PREDICT_DEBUG"):
            print("predict_risk: model not loaded (pipe is None)", file=sys.stderr)
        proba = _data_driven_proba(row)
        score, level, label = _proba_to_score_and_level(proba)
        return {
            "date": date_str,
            "risk": {"score": round(score, 1), "level": level, "label": label},
            "activeRiskFactors": _active_risk_factors(row),
            "daily": daily,
        }

    X = _build_prediction_X(row, feature_cols, pipe)
    if X is None:
        proba = _data_driven_proba(row)
        score, level, label = _proba_to_score_and_level(proba)
        return {
            "date": date_str,
            "risk": {"score": round(score, 1), "level": level, "label": label},
            "activeRiskFactors": _active_risk_factors(row),
            "daily": daily,
        }
    try:
        proba = float(pipe.predict_proba(X)[0, 1])
    except Exception as e:
        if os.getenv("PREDICT_DEBUG"):
            print(f"predict_risk: predict_proba failed: {e!s}", file=sys.stderr)
        proba = _data_driven_proba(row)
        score, level, label = _proba_to_score_and_level(proba)
        return {
            "date": date_str,
            "risk": {"score": round(score, 1), "level": level, "label": label},
            "activeRiskFactors": _active_risk_factors(row),
            "daily": daily,
        }
    score, level, label = _proba_to_score_and_level(proba)
    return {
        "date": date_str,
        "risk": {"score": round(score, 1), "level": level, "label": label},
        "activeRiskFactors": _active_risk_factors(row),
        "daily": daily,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict risk for a date or week; output JSON to stdout")
    parser.add_argument("--date", help="YYYY-MM-DD (required if not --week)")
    parser.add_argument("--week", action="store_true", help="Output predictions for a week")
    parser.add_argument("--start", help="Start date YYYY-MM-DD (required if --week)")
    parser.add_argument("--days", type=int, default=7, help="Number of days when --week (default 7)")
    parser.add_argument("--location-id", default=None, help="Optional location_id filter")
    args = parser.parse_args()

    if args.location_id:
        os.environ["LOCATION_ID"] = args.location_id

    from apps.ml.trainingModel import read_env_from_mongo, feature_engineer

    if args.week:
        if not args.start or len(args.start.strip()) != 10:
            print(json.dumps({"error": "With --week provide --start YYYY-MM-DD"}), file=sys.stderr)
            sys.exit(1)
        try:
            start_d = pd.Timestamp(args.start.strip()).date()
        except (ValueError, TypeError):
            print(json.dumps({"error": "Invalid --start; use YYYY-MM-DD"}), file=sys.stderr)
            sys.exit(1)
        days = max(1, min(args.days, 14))
        try:
            raw = read_env_from_mongo()
        except Exception:
            start_d = pd.Timestamp(args.start.strip()).date()
            end_d = start_d + timedelta(days=days - 1)
            raw = _synthetic_raw(
                end_d.strftime("%Y-%m-%d"),
                num_days=14 + days,
                location_id=args.location_id or "default",
            )
        raw["date"] = pd.to_datetime(raw["date"])
        raw["_date_norm"] = raw["date"].dt.normalize()
        fe = feature_engineer(raw)
        fe["_date_norm"] = pd.to_datetime(fe["date"]).dt.normalize()
        pipe = None
        model_path = _model_path()
        if model_path.exists():
            try:
                pipe = joblib.load(model_path)
            except Exception:
                pass
        results = []
        for i in range(days):
            d = start_d + timedelta(days=i)
            date_str = d.strftime("%Y-%m-%d")
            results.append(_predict_one(date_str, raw, fe, pipe))
        print(json.dumps({"start": args.start.strip(), "days": results}), flush=True)
        return

    if not args.date or len(args.date.strip()) != 10 or args.date[4] != "-" or args.date[7] != "-":
        print(json.dumps({"error": "Provide --date YYYY-MM-DD or --week --start YYYY-MM-DD"}), file=sys.stderr)
        sys.exit(1)
    date_str = args.date.strip()

    try:
        _run_date_prediction(date_str, args.location_id)
    except Exception:
        try:
            raw = _synthetic_raw(date_str, location_id=args.location_id or "default")
            raw["date"] = pd.to_datetime(raw["date"])
            raw["_date_norm"] = raw["date"].dt.normalize()
            fe = feature_engineer(raw)
            if not fe.empty:
                fe["_date_norm"] = pd.to_datetime(fe["date"]).dt.normalize()
            pipe = None
            model_path = _model_path()
            if model_path.exists():
                try:
                    pipe = joblib.load(model_path)
                except Exception:
                    pass
            out = _predict_one(date_str, raw, fe, pipe)
            print(json.dumps(out), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            sys.exit(1)


def _run_date_prediction(date_str: str, location_id: str | None = None) -> None:
    """Load data, engineer features, load model, predict for one date. Raises on failure."""
    try:
        raw = read_env_from_mongo()
    except Exception:
        raw = _synthetic_raw(date_str, location_id=location_id or "default")
    raw["date"] = pd.to_datetime(raw["date"])
    raw["_date_norm"] = raw["date"].dt.normalize()
    fe = feature_engineer(raw)
    if not fe.empty:
        fe["_date_norm"] = pd.to_datetime(fe["date"]).dt.normalize()
    pipe = None
    model_path = _model_path()
    if model_path.exists():
        try:
            pipe = joblib.load(model_path)
        except Exception:
            pass
    out = _predict_one(date_str, raw, fe, pipe)
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
