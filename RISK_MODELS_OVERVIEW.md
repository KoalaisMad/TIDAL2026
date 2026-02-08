# TIDAL Risk Prediction Models Overview

TIDAL includes **two separate asthma risk prediction systems** to serve different use cases.

## 🌍 Environmental Risk (General Model)

**Purpose**: Provide location-based environmental risk assessments for all users.

### Model Details
- **Model File**: `risk_model_general.joblib`
- **Location**: `TIDAL2026/risk_model_general.joblib`
- **Algorithm**: HistGradientBoostingClassifier
- **Features**: ~20 environmental features (AQI, PM2.5, pollen, weather)

### Scripts
- **Training**: `apps/ml/trainingModel.py`
- **Prediction**: `apps/ml/predict_risk.py`
- **Data Source**: MongoDB `tidal.pulldata` (environmental data only)

### Web Interface
- **Page**: `/breathe-well/environmental`
- **API Endpoints**: 
  - `/api/risk?date=YYYY-MM-DD&location=...`
  - `/api/week?start=YYYY-MM-DD&days=7&location=...`

### Characteristics
- ❌ **Not personalized** - same predictions for all users at the same location
- ✅ **No login required** - accessible to everyone
- ✅ **Fast** - no user data lookup needed
- ✅ **Good for**: Quick environmental risk assessment

### Training the Model
```bash
cd TIDAL2026
PYTHONPATH=asthma-forecaster python3 -m apps.ml.trainingModel
```

---

## 👤 Personalized Risk (User-Specific Model)

**Purpose**: Provide individualized 7-day risk forecasts based on personal health data.

### Model Details
- **Model File**: `flare_model.joblib`
- **Location**: `TIDAL2026/asthma-forecaster/apps/D A T A/flare_model.joblib`
- **Algorithm**: HistGradientBoostingClassifier
- **Features**: ~40-50 features (environment + user profile + symptoms + lags)

### Scripts
- **Training**: `apps/D A T A/train_personalized_model.py`
- **Prediction**: `apps/D A T A/predict_personalized.py`
- **Testing**: `apps/D A T A/test_personalized_predictions.py`
- **Data Sources**: 
  - MongoDB `asthma.users` (profiles + check-ins)
  - MongoDB `tidal.pulldata` (environmental data)

### Web Interface
- **Page**: `/breathe-well/personalized`
- **API Endpoint**: `/api/risk/personalized`

### Characteristics
- ✅ **Fully personalized** - unique predictions per user
- ✅ **Login required** - uses saved user profile and symptom history
- ✅ **Cached** - predictions stored in `asthma.personalized_predictions`
- ✅ **Good for**: Individual health tracking and 7-day forecasting

### Training the Model
```bash
cd TIDAL2026/asthma-forecaster/apps/D A T A
python train_personalized_model.py
```

---

## 📊 Comparison Table

| Feature | Environmental Risk | Personalized Risk |
|---------|-------------------|-------------------|
| **Model File** | `risk_model_general.joblib` | `flare_model.joblib` |
| **Training Script** | `apps/ml/trainingModel.py` | `apps/D A T A/train_personalized_model.py` |
| **Prediction Script** | `apps/ml/predict_risk.py` | `apps/D A T A/predict_personalized.py` |
| **Web Page** | `/breathe-well/environmental` | `/breathe-well/personalized` |
| **API Endpoint** | `/api/risk`, `/api/week` | `/api/risk/personalized` |
| **Input Data** | Location + environment only | User profile + symptoms + environment |
| **MongoDB** | `tidal.pulldata` | `asthma.users` + `tidal.pulldata` |
| **Personalization** | ❌ None | ✅ Per-user |
| **Requires Login** | ❌ No | ✅ Yes |
| **Caching** | No | Yes |
| **Features** | ~20 | ~40-50 |
| **Response Time** | <5s | <15s (without cache), <1s (with cache) |

---

## 🎯 Which Model Should I Use?

### Use **Environmental Risk** when:
- You want a quick location-based risk assessment
- User is not logged in
- You don't have user symptom data
- You need the same prediction for everyone at a location
- Building public dashboards or maps

### Use **Personalized Risk** when:
- User is logged in with a profile
- User has check-in history (symptoms, exercise)
- You want predictions tailored to individual health
- Building personalized health tracking features
- Providing 7-day forecasts for individuals

---

## 🚀 Quick Start

### To Use Environmental Risk:
```bash
# 1. Train the general model
cd TIDAL2026
PYTHONPATH=asthma-forecaster python3 -m apps.ml.trainingModel

# 2. Test prediction
PYTHONPATH=asthma-forecaster python3 -m apps.ml.predict_risk --date 2026-02-09

# 3. Start web server and visit /breathe-well/environmental
cd asthma-forecaster/apps/web
pnpm dev
```

### To Use Personalized Risk:
```bash
# 1. Train the personalized model
cd TIDAL2026/asthma-forecaster/apps/D A T A
python train_personalized_model.py

# 2. Test the system
python test_personalized_predictions.py

# 3. Start web server and visit /breathe-well/personalized
cd ../web
pnpm dev
```

---

## 📚 Documentation

- **Environmental Risk**: See `apps/ml/README.md`
- **Personalized Risk**: See `apps/D A T A/PERSONALIZED_RISK_README.md` and `QUICKSTART.md`

---

## 🔧 Architecture

### Environmental Risk Flow
```
User Location
     ↓
Environmental Data → General Model → Risk Score
  (tidal.pulldata)   (risk_model_   (1-5)
                      general.joblib)
```

### Personalized Risk Flow
```
User Profile + Symptoms + Location
     ↓              ↓           ↓
(asthma.users)    Check-ins   Env Data
       ↓              ↓           ↓
       └──────────────┴───────────┘
                  ↓
          Personalized Model
          (flare_model.joblib)
                  ↓
          Risk Score (1-5)
          Cached in MongoDB
```

---

## 🎓 Key Takeaways

1. **Two separate models** for two different purposes
2. **Environmental** = Location-based, general risk
3. **Personalized** = User-specific, health data-based
4. **Both are valuable** for different use cases
5. **Can be used together** for comprehensive risk assessment

---

**Questions?**
- Environmental Risk: See `apps/ml/README.md`
- Personalized Risk: See `apps/D A T A/QUICKSTART.md`

**Last Updated**: February 8, 2026
