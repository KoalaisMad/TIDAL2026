# Quick Start Guide: Personalized Risk Predictions

## 🎯 Which Risk System Do You Need?

TIDAL has **two separate risk prediction systems**:

### 🌍 Environmental Risk (General Model)
- **Purpose**: Location-based risk for everyone
- **Model**: `risk_model_general.joblib`
- **Page**: `/breathe-well/environmental`
- **No login required** - same predictions for all users at a location
- **Train with**: `apps/ml/trainingModel.py`

### 👤 Personalized Risk (This Guide)
- **Purpose**: Individual risk based on your health data
- **Model**: `flare_model.joblib`
- **Page**: `/breathe-well/personalized`
- **Login required** - unique predictions per user
- **Train with**: `apps/D A T A/train_personalized_model.py` (this guide)

---

## 🚀 Get Started in 3 Steps (Personalized Model)

### Step 1: Train the Model (One-time setup)

```bash
cd TIDAL2026/asthma-forecaster/apps/D A T A
python train_personalized_model.py
```

**What this does:**
- Loads your users from MongoDB (`asthma.users`)
- Loads environmental data from MongoDB (`tidal.pulldata`)
- Trains a machine learning model on user symptoms + environment
- Saves `flare_model.joblib` (the trained model)

**Expected time:** 15-30 seconds

---

### Step 2: Test the System

```bash
python test_personalized_predictions.py
```

**This verifies:**
- ✓ MongoDB connection works
- ✓ Users and check-ins are loaded
- ✓ Environmental data is available
- ✓ Model file exists and loads
- ✓ Predictions run successfully
- ✓ API output format is correct

---

### Step 3: View in the Web UI

```bash
cd ../web
pnpm dev
```

Navigate to: **http://localhost:3000/breathe-well/personalized**

**You should see:**
- 7-day risk forecast personalized for you
- Risk gauge showing today's risk level
- Daily breakdown with risk factors
- Recommendations based on your risk

---

## 📊 Understanding the Output

### Risk Scores

- **1.0 - 2.0**: 🟢 **Low Risk** - Normal day, maintain routine
- **2.0 - 4.0**: 🟡 **Moderate Risk** - Be cautious, have rescue inhaler ready
- **4.0 - 5.0**: 🔴 **High Risk** - Take preventive measures, avoid triggers

### What Influences Your Risk?

**Personal Factors:**
- Recent symptoms (wheeze, cough, chest tightness)
- Exercise levels
- Asthma severity
- BMI and age

**Environmental Factors:**
- Air quality (AQI, PM2.5)
- Pollen levels (tree, grass, weed)
- Weather (temperature, humidity, wind)
- Seasonal patterns

---

## 🔄 Updating Predictions

Predictions are cached in MongoDB for performance. To refresh:

### Option 1: Automatic (Recommended)
The cache expires after 24 hours. Just wait and predictions will auto-refresh.

### Option 2: Manual Refresh
```bash
cd TIDAL2026/asthma-forecaster/apps/D A T A
python predict_personalized.py
```

This regenerates predictions for all users for the next 7 days.

---

## 🛠️ Retraining the Model

Retrain when:
- You add new users
- After 30+ days of new data
- To improve accuracy with more check-ins

```bash
cd TIDAL2026/asthma-forecaster/apps/D A T A

# Default: 90 days of data
python train_personalized_model.py

# Use more data (180 days)
python train_personalized_model.py --days 180

# Train for flare prediction instead of risk
python train_personalized_model.py --target flare_day
```

---

## 📁 File Structure

```
TIDAL2026/
├── .env                                    # MongoDB credentials
└── asthma-forecaster/apps/
    ├── D A T A/
    │   ├── flare_model.joblib             # ← Trained model (generated)
    │   ├── train_personalized_model.py    # ← Train the model
    │   ├── predict_personalized.py        # ← Generate predictions
    │   ├── test_personalized_predictions.py # ← Test suite
    │   └── PERSONALIZED_RISK_README.md    # ← Full documentation
    └── web/
        └── src/app/api/risk/
            └── personalized/
                └── route.ts               # ← API endpoint
```

---

## ⚠️ Troubleshooting

### "Model not found" error

**Solution:**
```bash
cd TIDAL2026/asthma-forecaster/apps/D A T A
python train_personalized_model.py
```

### "No users found" error

**Check MongoDB:**
```bash
# Verify users collection exists and has data
mongosh "your-mongodb-uri" --eval "use asthma; db.users.count()"
```

### Web UI shows fallback/mock data

**Check:**
1. Is the model file present? `ls flare_model.joblib`
2. Is MongoDB connected? Run `python test_personalized_predictions.py`
3. Are there any errors in the terminal running `pnpm dev`?

### Predictions seem inaccurate

**Improve accuracy:**
1. Add more check-in data (log symptoms daily)
2. Retrain with more historical data: `python train_personalized_model.py --days 180`
3. Ensure environmental data is up-to-date in MongoDB

---

## 🎯 Best Practices

### For Accurate Predictions

1. **Log symptoms daily** in the app
   - Wheeze, cough, chest tightness
   - Exercise minutes
   - Consistency is key!

2. **Update your profile**
   - Keep height, weight current (affects BMI)
   - Update asthma severity if it changes

3. **Review recommendations**
   - Act on high-risk day warnings
   - Track what helps reduce your risk

### For System Maintenance

1. **Retrain monthly**
   ```bash
   python train_personalized_model.py
   ```

2. **Monitor data freshness**
   - Environmental data should be updated daily
   - Check with: `python test_personalized_predictions.py`

3. **Backup your model**
   ```bash
   cp flare_model.joblib flare_model_backup_$(date +%Y%m%d).joblib
   ```

---

## 📈 Monitoring Performance

### Check Model Quality

When training, look for:
- **AUC > 0.80**: Good predictive power
- **Precision > 0.60**: Reliable high-risk warnings
- **Recall > 0.60**: Catches most true high-risk days

### Check API Response Time

```bash
time curl http://localhost:3000/api/risk/personalized
```

Should be: <2 seconds (with cache), <15 seconds (without cache)

---

## 🔗 API Reference

### GET `/api/risk/personalized`

**Response:**
```json
{
  "start": "2026-02-09",
  "fromModel": true,
  "days": [
    {
      "date": "2026-02-09",
      "risk": {
        "score": 2.3,
        "level": "moderate",
        "label": "Moderate"
      },
      "activeRiskFactors": []
    },
    ...
  ]
}
```

**Fields:**
- `fromModel`: `true` if predictions from ML model, `false` if fallback
- `risk.score`: Continuous value 1.0-5.0
- `risk.level`: "low", "moderate", or "high"
- `risk.label`: Display string

---

## 💡 Tips

- **First time setup**: Run all 3 steps in order
- **Daily use**: Just open the web UI, predictions update automatically
- **After adding users**: Retrain the model
- **Debugging**: Use `test_personalized_predictions.py` to diagnose issues

---

## � Environmental vs. Personalized Risk

**Environmental Risk** (`/breathe-well/environmental`):
- Uses `risk_model_general.joblib` (general model)
- No user data needed
- Same predictions for everyone at a location
- Good for quick location-based assessment

**Personalized Risk** (`/breathe-well/personalized` - this guide):
- Uses `flare_model.joblib` (personalized model)
- Requires user profile + symptom check-ins
- Unique predictions per user
- Best for individualized health tracking

Choose **Personalized Risk** when you want predictions tailored to your health history!

---

## 📚 More Information

See [PERSONALIZED_RISK_README.md](PERSONALIZED_RISK_README.md) for:
- Detailed architecture
- MongoDB schema
- Feature engineering details
- Advanced configuration
- Troubleshooting guide
- Full comparison of both systems

---

**Need Help?** Run: `python test_personalized_predictions.py --help`
