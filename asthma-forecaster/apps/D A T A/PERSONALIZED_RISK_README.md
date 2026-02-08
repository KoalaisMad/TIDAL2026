# Personalized Risk Prediction System

This system provides **personalized 7-day asthma risk forecasts** for users based on their profile, symptom history, and environmental conditions.

## Two Risk Prediction Systems

The TIDAL platform includes **two separate risk prediction systems**:

### 1. Environmental Risk (General Model)
**Page**: `/breathe-well/environmental`
- **Model**: `risk_model_general.joblib`
- **Training Script**: `apps/ml/trainingModel.py`
- **Prediction Script**: `apps/ml/predict_risk.py`
- **Basis**: Location and environmental conditions only
- **Personalization**: None - same predictions for all users at the same location
- **API Endpoints**: `/api/risk`, `/api/week`
- **Use Case**: Quick environmental risk assessment based on location

### 2. Personalized Risk (User-Specific Model)
**Page**: `/breathe-well/personalized`
- **Model**: `flare_model.joblib` (this document)
- **Training Script**: `apps/D A T A/train_personalized_model.py`
- **Prediction Script**: `apps/D A T A/predict_personalized.py`
- **Basis**: User profile + symptom history + environmental conditions
- **Personalization**: Fully personalized - unique predictions per user
- **API Endpoint**: `/api/risk/personalized`
- **Use Case**: Individualized 7-day forecast based on personal health data

---

## Overview (Personalized Model)

The personalized risk prediction model combines:
- **User Profile**: Age, height, weight, BMI, asthma severity
- **Symptom History**: Wheeze, cough, chest tightness, exercise minutes from check-ins
- **Environmental Data**: AQI, PM2.5, pollen, weather conditions
- **Temporal Features**: Day of week, month, season, holidays
- **Lag Features**: Previous day's symptoms for trend detection

## Architecture (Personalized Model)

```
┌─────────────────┐
│  MongoDB Users  │  (profiles + check-ins)
└────────┬────────┘
         │
         ├──────────┐
         │          │
         v          v
    ┌────────┐  ┌────────┐
    │ Train  │  │Predict │
    │Personalized│  API   │
    │  Model │  │        │
    └───┬────┘  └────┬───┘
        │            │
        v            v
 flare_model    JSON Output
   .joblib      (7 days)
                      │
                      v
              ┌───────────────┐
              │  Web Frontend │
              │ /breathe-well │
              │  /personalized│
              └───────────────┘
```

**Note**: The Environmental Risk system uses a separate architecture with `risk_model_general.joblib` and does not require user data.

## Files

### Core Scripts

1. **`train_personalized_model.py`** - Train the personalized model
   - Loads user profiles and check-ins from MongoDB
   - Loads environmental data (historical)
   - Creates features and target variable
   - Trains HistGradientBoostingClassifier
   - Saves model to `flare_model.joblib`

2. **`predict_personalized.py`** - Generate 7-day predictions
   - Loads all users from MongoDB
   - Gets environmental forecast for next 7 days
   - Enriches with user profiles and recent symptoms
   - Runs model predictions
   - Outputs JSON: `[{user_id, date, risk}]`
   - Caches predictions in MongoDB

3. **`test_personalized_predictions.py`** - Test suite
   - Verifies MongoDB connection
   - Checks user data
   - Validates environmental data
   - Tests model loading
   - Runs sample predictions
   - Validates API output format

### API Integration

**`apps/web/src/app/api/risk/personalized/route.ts`**
- GET endpoint: `/api/risk/personalized`
- Calls `predict_personalized.py` script
- Returns 7-day forecast for the logged-in user
- Includes risk score (1-5), level (low/moderate/high), and label

## MongoDB Schema

### Users Collection (`asthma.users`)

```javascript
{
  _id: ObjectId("..."),
  profile: {
    height: "5'10\"",
    weight: "170 lbs",
    age: 35,
    asthma_severity: "moderate",
    // ... other profile fields
  },
  checkIns: [
    {
      date: "2026-02-08",
      wheeze: 2,
      cough: 1,
      chestTightness: 0,
      exerciseMinutes: 30
    },
    // ... more check-ins
  ]
}
```

### Environmental Collection (`tidal.pulldata`)

```javascript
{
  date: ISODate("2026-02-08T00:00:00Z"),
  location_id: "37.77-122.42",
  AQI: 45,
  PM2_5_mean: 12.5,
  pollen_tree: 3,
  pollen_grass: 2,
  pollen_weed: 1,
  temp_max: 72,
  temp_min: 55,
  humidity: 65,
  wind: 8,
  rain: 0,
  pressure: 1013,
  day_of_week: "Friday",
  month: 2,
  season: "winter",
  holiday_flag: false
}
```

### Predictions Cache (`asthma.personalized_predictions`)

```javascript
{
  user_id: "507f1f77bcf86cd799439011",
  date: "2026-02-09",
  risk: 2.5,
  updated_at: ISODate("2026-02-08T12:00:00Z")
}
```

## Setup & Installation

### 1. Environment Variables

Create `.env` in `TIDAL2026/` with:

```bash
# MongoDB connection
MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/
MONGODB_DB_NAME=asthma          # Users database
MONGODB_DB=tidal                # Environmental data database
ML_ENV_COLL=pulldata            # Environmental collection name

# Optional: coordinates for forecast fallback
DEFAULT_LAT=37.77
DEFAULT_LON=-122.42
```

### 2. Install Dependencies

```bash
cd TIDAL2026/asthma-forecaster/apps/D A T A
pip install pandas numpy scikit-learn joblib pymongo requests python-dotenv
```

or use the requirements file:

```bash
cd TIDAL2026
pip install -r asthma-forecaster/apps/ml/requirements.txt
```

### 3. Verify Data

Check that you have:
- Users in MongoDB (`asthma.users`)
- Environmental data in MongoDB (`tidal.pulldata`)

Run the test suite:

```bash
cd TIDAL2026/asthma-forecaster/apps/D A T A
python test_personalized_predictions.py
```

## Usage

### Training the Model

**From `TIDAL2026` directory:**

```bash
# Train with default settings (90 days of data, 'risk' target)
cd asthma-forecaster/apps/D A T A
python train_personalized_model.py

# Customize training
python train_personalized_model.py --days 180 --target flare_day --out my_model.joblib

# Options:
#   --out FILE          Output model file (default: flare_model.joblib)
#   --target TYPE       'risk' or 'flare_day' (default: risk)
#   --days N            Days of historical data (default: 90)
#   --min-users N       Minimum users required (default: 1)
```

**Expected output:**

```
✓ MongoDB connection successful

Loading user profiles and check-ins...
✓ Loaded 25 users with 450 check-ins

Loading environmental data (last 90 days)...
✓ Loaded 90 environmental records

Merging data and creating features...
✓ Created 2250 training samples

======================================================================
TRAINING PERSONALIZED RISK MODEL
======================================================================
Total samples: 2250
Features: 45
Target distribution: {0: 1800, 1: 450}
Target rate: 20.00%

======================================================================
CROSS-VALIDATION (5 folds)
======================================================================
Fold 1: AUC=0.823, Precision=0.650, Recall=0.720
Fold 2: AUC=0.845, Precision=0.680, Recall=0.740
...

======================================================================
MODEL SAVED: flare_model.joblib
======================================================================
```

### Making Predictions

**From `TIDAL2026` directory:**

```bash
cd asthma-forecaster/apps/D A T A

# Generate 7-day predictions for all users
python predict_personalized.py

# Output JSON to file
python predict_personalized.py --out predictions.json

# Use custom model
python predict_personalized.py --model my_model.joblib

# Change number of days
python predict_personalized.py --days 14
```

**Output format:**

```json
[
  {
    "user_id": "507f1f77bcf86cd799439011",
    "date": "2026-02-09",
    "risk": 2.3
  },
  {
    "user_id": "507f1f77bcf86cd799439011",
    "date": "2026-02-10",
    "risk": 3.1
  },
  ...
]
```

### Running the Web UI

**From `TIDAL2026` directory:**

```bash
cd asthma-forecaster/apps/web
pnpm install
pnpm dev
```

Navigate to: **http://localhost:3000/breathe-well/personalized**

The UI will:
1. Call `/api/risk/personalized`
2. The API executes `predict_personalized.py`
3. Returns 7-day forecast for logged-in user
4. Displays risk gauge and daily forecasts

## Features

### Model Features

The model uses ~40-50 features including:

**Environmental:**
- `AQI`, `PM2_5_mean`, `PM2_5_max`
- `pollen_tree`, `pollen_grass`, `pollen_weed`
- `temp_min`, `temp_max`, `humidity`, `wind`, `rain`, `pressure`

**Temporal:**
- `day_of_week` (Monday-Sunday)
- `month` (1-12)
- `season` (winter/spring/summer/fall)
- `holiday_flag` (boolean)

**User Profile:**
- `profile_height_in` (parsed to inches)
- `profile_weight_lb` (parsed to pounds)
- `profile_age`
- `profile_asthma_severity`

**Symptoms (current & lag):**
- `wheeze`, `wheeze_lag1`
- `cough`, `cough_lag1`
- `chestTightness`, `chestTightness_lag1`
- `exerciseMinutes`, `exerciseMinutes_lag1`
- `symptom_score`, `symptom_score_lag1`

### Target Variables

**`risk`** (default):
- Binary target based on high symptoms OR high environmental exposure
- High symptoms: `symptom_score >= 4`
- High environment: `AQI > 100` OR `PM2.5 > 35` OR `total_pollen > 20`

**`flare_day`**:
- Binary target based only on symptoms
- Flare: `symptom_score >= 6` (sum of wheeze + cough + chestTightness)

## Prediction Caching

To improve performance, predictions are cached in MongoDB:
- Collection: `asthma.personalized_predictions`
- Cache key: `(user_id, date)`
- Auto-updated when script runs
- Use `--no-cache` flag to force recomputation (if implemented)

## Troubleshooting

### No predictions returned

```bash
# Check MongoDB connection
python test_personalized_predictions.py

# Verify users exist
mongo "mongodb://..." --eval "db.users.count()"

# Check environmental data
mongo "mongodb://..." --eval "db.pulldata.count()"
```

### Model not found

```bash
# Train the model first
cd TIDAL2026/asthma-forecaster/apps/D A T A
python train_personalized_model.py
```

### Prediction errors

```bash
# Run with debug output
PYTHONPATH=. python predict_personalized.py --days 7

# Check feature alignment
python test_personalized_predictions.py
```

### API returns fallback data

The API falls back to synthetic data if:
- Python script not found
- Model file missing
- Script execution error
- No users in database

Check the server logs for specific errors.

## Performance

**Training:**
- ~90 days of data × 25 users = 2,250 samples
- Training time: ~10-30 seconds
- Model size: ~5-10 MB

**Prediction:**
- 7 days × N users queries
- With cache: <1 second
- Without cache: 5-15 seconds
- API timeout: 60 seconds

## Model Evaluation

**Cross-validation metrics:**
- **AUC-ROC**: 0.80+ is good, 0.85+ is excellent
- **Precision**: Fraction of predicted high-risk days that are truly high-risk
- **Recall**: Fraction of true high-risk days that are predicted

**Interpretation:**
- Risk score 1-5 (continuous)
- Mapped to: Low (1-2), Moderate (2-4), High (4-5)
- Frontend displays as gauge + color

## Next Steps

1. **Add more features**: Medication adherence, rescue inhaler usage, sleep quality
2. **Improve target**: Use actual symptom escalations or ER visits
3. **Personalize further**: Train individual models per user (if enough data)
4. **Add explanations**: SHAP values or feature importance for interpretability
5. **A/B testing**: Compare model predictions vs. actual outcomes

## Support

For issues or questions:
1. Run the test suite: `python test_personalized_predictions.py`
2. Check the logs in `apps/web/.next/server-logs`
3. Verify MongoDB collections and schema
4. Review this README for setup steps

---

## Comparison: Environmental vs. Personalized Risk

| Feature | Environmental Risk | Personalized Risk |
|---------|-------------------|-------------------|
| **Model File** | `risk_model_general.joblib` | `flare_model.joblib` |
| **Training Script** | `apps/ml/trainingModel.py` | `apps/D A T A/train_personalized_model.py` |
| **Prediction Script** | `apps/ml/predict_risk.py` | `apps/D A T A/predict_personalized.py` |
| **Location** | TIDAL2026/risk_model_general.joblib | TIDAL2026/asthma-forecaster/apps/D A T A/flare_model.joblib |
| **Web Page** | `/breathe-well/environmental` | `/breathe-well/personalized` |
| **API Endpoint** | `/api/risk`, `/api/week` | `/api/risk/personalized` |
| **Input Data** | Location + environmental conditions | User profile + symptoms + environment |
| **MongoDB Collections** | `tidal.pulldata` (env only) | `asthma.users` + `tidal.pulldata` |
| **Personalization** | ❌ None (same for all users) | ✅ Fully personalized per user |
| **Requires Login** | ❌ No | ✅ Yes |
| **Caching** | No | Yes (`asthma.personalized_predictions`) |
| **Features** | ~20 environmental features | ~40-50 features (env + profile + symptoms) |
| **Target** | High environmental risk | High symptom/flare risk |
| **Use Case** | Quick location-based risk | Personal 7-day health forecast |

**Recommendation**: 
- Use **Environmental Risk** for general location-based risk assessment
- Use **Personalized Risk** for logged-in users with symptom tracking history

---

**Last Updated**: February 8, 2026
