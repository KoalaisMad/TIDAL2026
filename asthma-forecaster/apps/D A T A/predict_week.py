#!/usr/bin/env python3
"""
Predict risk scores for the next 7 days using the trained model.
Shows probability scores instead of binary predictions.
"""
import sys
from pathlib import Path
from datetime import date, timedelta
import joblib
import pandas as pd
import numpy as np

# Load the trained model
model_path = Path(__file__).parent / "flare_model.joblib"
if not model_path.exists():
    print(f"Model not found at {model_path}")
    print("Run train_model.py first to create the model.")
    sys.exit(1)

model_data = joblib.load(model_path)
pipeline = model_data.get("pipeline")
feature_cols = model_data.get("feature_cols")
target_col = model_data.get("target_col")
target_names = model_data.get("target_names", [])

print(f"Loaded model from {model_path}")
print(f"Features used: {feature_cols}")
print(f"Target: {target_col}")
print(f"Risk levels: {target_names}")
print()

# Load the most recent data from the dataset
dataset_path = Path(__file__).parent / "dataset_two_weeks.csv"
if not dataset_path.exists():
    print(f"Dataset not found at {dataset_path}")
    sys.exit(1)

df = pd.read_csv(dataset_path)
print(f"Loaded {len(df)} rows from dataset")
print(f"Dataset columns: {list(df.columns)}")

# Get the last 7 rows as a baseline for the next 7 days
# In a real scenario, you'd fetch new environmental data for future dates
# For now, we'll use the most recent patterns to show how the model predicts
last_week = df.tail(7).copy()

# Check which features exist in the dataset
available_features = [col for col in feature_cols if col in df.columns]
missing_features = [col for col in feature_cols if col not in df.columns]

if missing_features:
    print(f"\nWarning: Missing features in dataset: {missing_features}")
    print(f"Available features: {available_features}")
    
    # For missing features, try to find alternatives or use defaults
    for col in missing_features:
        if col == 'user_id' and 'locationid' in last_week.columns:
            last_week['user_id'] = last_week['locationid'].astype(str)
            print(f"  Using 'locationid' as 'user_id'")
        else:
            last_week[col] = 0
            print(f"  Setting '{col}' to default value 0")

# Ensure all columns are in the right order and type
X = last_week[feature_cols].copy()

# Convert user_id to string if it exists (for OneHotEncoder compatibility)
if 'user_id' in X.columns:
    X['user_id'] = X['user_id'].astype(str)

print(f"\nPreparing to predict with {len(X)} samples...")
print()

# Use the pipeline to predict (it handles scaling internally)
# predict_proba returns [prob_class_0, prob_class_1, prob_class_2, ...]
try:
    proba = pipeline.predict_proba(X)
    predicted_class = pipeline.predict(X)
except Exception as e:
    print(f"Error during prediction: {e}")
    print("\nAttempting simpler prediction...")
    # If there's an issue, try with just the available columns
    X_simple = last_week[available_features]
    print(f"Using only available features: {available_features}")
    sys.exit(1)

print("\n" + "="*80)
print("RISK FORECAST - NEXT 7 DAYS")
print("="*80)
print()

# Generate dates for the next 7 days
today = date.today()
future_dates = [today + timedelta(days=i) for i in range(7)]

# Display results
for i, (day, pred_class, prob_row) in enumerate(zip(future_dates, predicted_class, proba)):
    print(f"Day {i+1} ({day.strftime('%a, %b %d, %Y')})")
    
    # Show the predicted class name if available
    if target_names and pred_class < len(target_names):
        print(f"  Predicted Risk Level: {target_names[pred_class]}")
    else:
        print(f"  Predicted Risk Level: {pred_class}")
    
    # Show probabilities for each risk level
    print(f"  Probability Distribution:")
    for risk_idx, prob in enumerate(prob_row):
        if target_names and risk_idx < len(target_names):
            risk_label = target_names[risk_idx]
        else:
            risk_label = f"Level {risk_idx + 1}"
        print(f"    {risk_label}: {prob:.3f} ({prob*100:.1f}%)")
    
    # Show the highest probability
    max_prob_idx = np.argmax(prob_row)
    max_prob = prob_row[max_prob_idx]
    if target_names and max_prob_idx < len(target_names):
        max_label = target_names[max_prob_idx]
    else:
        max_label = f"Level {max_prob_idx + 1}"
    print(f"  → Most Likely: {max_label} with {max_prob*100:.1f}% confidence")
    print()

print("="*80)
print()
print("Note: These predictions are based on recent historical patterns.")
print("For accurate future predictions, fetch real environmental forecasts.")
print()

# Summary statistics
avg_predicted_level = np.mean([np.argmax(p) + 1 for p in proba])
print(f"Average predicted risk level for the week: {avg_predicted_level:.2f}")
print(f"Risk levels range from: {predicted_class.min()} to {predicted_class.max()}")
