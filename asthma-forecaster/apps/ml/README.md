# ML pipeline: pull data → push to MongoDB → train

Run all commands from **TIDAL2026** (project root). Ensure `.env` has `MONGODB_URI` and `MONGODB_DB` (and optional `MONGODB_COLLECTION` / `ML_ENV_COLL`).

## 1. Pull data and push to MongoDB

Fetches air quality, weather, and pollen from external APIs and writes daily rows to MongoDB (collection `ml_daily` by default).

```bash
cd TIDAL2026

# Single location, date range
PYTHONPATH=asthma-forecaster python3 -m apps.ml.generate_ml_data \
  --collection ml_daily --lat 37.77 --lon -122.42 \
  --start 2026-02-01 --end 2026-02-07

# Multiple locations (more rows: N locations × days)
PYTHONPATH=asthma-forecaster python3 -m apps.ml.generate_ml_data \
  --collection ml_daily \
  --location 37.77,-122.42 --location 34.05,-118.24 \
  --start 2025-10-11 --end 2026-02-07 --batch 14
```

- **Pull:** AirNow/PurpleAir, NOAA/Open-Meteo, pollen (Open-Meteo or seasonal fallback).
- **Push:** Upserts into `ml_daily` (or `--collection <name>`). Schema: PM2_5_mean, AQI, temp_*, humidity, wind, pressure, rain, pollen_*, day_of_week, month, season, holiday_flag.

## 2. Train the risk model

Reads from MongoDB `ml_daily` (or `ML_ENV_COLL` / `ENV_COLL`), builds “high risk tomorrow” labels from AQI/PM2.5/pollen thresholds, and trains a classifier. Saves `risk_model_general.joblib` in the current directory.

```bash
cd TIDAL2026

PYTHONPATH=asthma-forecaster python3 -m apps.ml.trainingModel
```

To use a different collection:

```bash
ML_ENV_COLL=other_collection PYTHONPATH=asthma-forecaster python3 -m apps.ml.trainingModel
```

## 3. Full pipeline (pull → push → train)

```bash
cd TIDAL2026

# Pull and push
PYTHONPATH=asthma-forecaster python3 -m apps.ml.generate_ml_data \
  --collection ml_daily --lat 37.77 --lon -122.42 \
  --start 2025-10-11 --end 2026-02-07 --batch 14

# Train
PYTHONPATH=asthma-forecaster python3 -m apps.ml.trainingModel
```

## 4. Frontend (model + data)

The Next.js app in `apps/web` uses the trained model and `ml_daily` for risk by date:

- **predict_risk.py** – Loads `risk_model_general.joblib`, reads env from MongoDB, runs feature engineering, predicts risk and active factors. Outputs JSON for the API.
  ```bash
  PYTHONPATH=asthma-forecaster python3 -m apps.ml.predict_risk --date 2026-02-07
  ```
- **GET /api/risk?date=YYYY-MM-DD** – Calls the predictor and returns `{ date, risk: { score, level, label }, activeRiskFactors }`. If Python or the model is unavailable, returns a stub response.

Run the frontend from **TIDAL2026** (or set `TIDAL_ROOT` to the TIDAL2026 directory) so the API can find the model and `.env`:
  ```bash
  cd TIDAL2026/asthma-forecaster/apps/web && npm run dev
  ```

## Two risk pipelines (do not mix)

| Pipeline | Data | Train script | Model file | Used by |
|----------|------|--------------|------------|---------|
| **Non-personalized** (environmental tab) | `D A T A/dataset_two_weeks.csv` (env only) | `D A T A/train_model.py` | `D A T A/flare_model.joblib` | `predict_flare.py` → `/api/week`, `/api/risk` |
| **Personalized** (personalized tab) | `D A T A/personalized_synthetic_data.csv` (daily chars + flare_day) | `apps/ml/pgood.py` | `D A T A/personalized_flare_model.joblib` | `predict_personalized.py` → `/api/risk/personalized` |

Personalized data has the same daily characteristics as the app check-in: wheeze, cough, chestTightness, exerciseMinutes, linked to flare_day. Generate it, then train the personalized model:

```bash
cd TIDAL2026

# 1. Generate ~300 synthetic rows (daily chars + flare_day)
PYTHONPATH=asthma-forecaster python3 -m apps.ml.generate_personalized_data

# 2. Train personalized model (same procedure as D A T A/train_model.py)
PYTHONPATH=asthma-forecaster python3 -m apps.ml.pgood
```

Output: `D A T A/personalized_flare_model.joblib`. The personalized tab uses this; the environmental tab uses `flare_model.joblib` only.

## Other scripts

- **main.py** – Asthma flare model (uses `data.py`, optional `symptom_daily` labels):  
  `ML_ENV_COLL=ml_daily PYTHONPATH=asthma-forecaster python3 -m apps.ml.main --demo-labels`
- **seed_demo_labels.py** – Seeds `symptom_daily` from dates in the env collection for use with `main.py`.

## Requirements

See `requirements.txt`. Core: `pymongo`, `pandas`, `scikit-learn`, `joblib`, `python-dotenv`, `requests`.
