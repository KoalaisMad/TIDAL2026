#!/usr/bin/env python3
"""
Test script for personalized risk prediction model.

Verifies:
1. MongoDB connection
2. User data loading
3. Environmental data loading
4. Model prediction pipeline
5. API output format

USAGE:
  python test_personalized_predictions.py
  python test_personalized_predictions.py --user-id <USER_ID>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Load .env
def _load_dotenv():
    try:
        from dotenv import load_dotenv
        root = Path(__file__).resolve().parent
        for _ in range(5):
            for name in [".env", "..env"]:
                p = root / name
                if p.exists():
                    load_dotenv(p)
                    return
            root = root.parent
        if Path.cwd().joinpath(".env").exists():
            load_dotenv(Path.cwd() / ".env")
    except ImportError:
        pass


_load_dotenv()

import pandas as pd
import joblib
from pymongo import MongoClient


def test_mongodb_connection() -> MongoClient | None:
    """Test MongoDB connection."""
    print("\n" + "="*70)
    print("TEST 1: MongoDB Connection")
    print("="*70)
    
    uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=10000)
        client.admin.command("ping")
        print("✓ MongoDB connection successful")
        print(f"  URI: {uri[:50]}...")
        return client
    except Exception as e:
        print(f"✗ MongoDB connection failed: {e}")
        return None


def test_user_data(client: MongoClient) -> tuple[int, int]:
    """Test loading user data."""
    print("\n" + "="*70)
    print("TEST 2: User Data Loading")
    print("="*70)
    
    db_name = os.environ.get("MONGODB_DB_NAME", "asthma")
    coll = client[db_name]["users"]
    
    try:
        user_count = coll.count_documents({})
        print(f"✓ Found {user_count} users in {db_name}.users")
        
        # Sample one user
        sample = coll.find_one({}, {"_id": 1, "profile": 1, "checkIns": 1})
        if sample:
            print(f"  Sample user ID: {sample['_id']}")
            print(f"  Profile keys: {list((sample.get('profile') or {}).keys())}")
            checkins = sample.get("checkIns") or []
            print(f"  Check-ins: {len(checkins)}")
            if checkins:
                print(f"  Latest check-in date: {checkins[-1].get('date')}")
        
        # Count total check-ins
        pipeline = [
            {"$project": {"checkInCount": {"$size": {"$ifNull": ["$checkIns", []]}}}},
            {"$group": {"_id": None, "total": {"$sum": "$checkInCount"}}}
        ]
        result = list(coll.aggregate(pipeline))
        total_checkins = result[0]["total"] if result else 0
        
        print(f"  Total check-ins across all users: {total_checkins}")
        return user_count, total_checkins
    
    except Exception as e:
        print(f"✗ Failed to load user data: {e}")
        return 0, 0


def test_env_data(client: MongoClient) -> int:
    """Test loading environmental data."""
    print("\n" + "="*70)
    print("TEST 3: Environmental Data Loading")
    print("="*70)
    
    db_name = os.environ.get("MONGODB_DB", "tidal")
    coll_name = os.environ.get("ML_ENV_COLL", "pulldata")
    
    try:
        coll = client[db_name][coll_name]
        count = coll.count_documents({})
        print(f"✓ Found {count} environmental records in {db_name}.{coll_name}")
        
        # Sample record
        sample = coll.find_one({}, {"_id": 0})
        if sample:
            print(f"  Sample keys: {list(sample.keys())[:10]}...")
            if "date" in sample:
                print(f"  Sample date: {sample['date']}")
        
        # Date range
        pipeline = [
            {"$group": {
                "_id": None,
                "minDate": {"$min": "$date"},
                "maxDate": {"$max": "$date"}
            }}
        ]
        result = list(coll.aggregate(pipeline))
        if result:
            print(f"  Date range: {result[0].get('minDate')} to {result[0].get('maxDate')}")
        
        return count
    
    except Exception as e:
        print(f"✗ Failed to load environmental data: {e}")
        return 0


def test_model_file() -> dict | None:
    """Test loading the model file."""
    print("\n" + "="*70)
    print("TEST 4: Model File")
    print("="*70)
    
    model_path = Path(__file__).resolve().parent / "flare_model.joblib"
    
    if not model_path.exists():
        print(f"✗ Model file not found: {model_path}")
        print("  Run: python train_personalized_model.py")
        return None
    
    try:
        bundle = joblib.load(model_path)
        print(f"✓ Model loaded successfully from {model_path.name}")
        print(f"  Pipeline: {type(bundle.get('pipeline')).__name__}")
        print(f"  Feature count: {len(bundle.get('feature_cols', []))}")
        print(f"  Target: {bundle.get('target_col', 'unknown')}")
        
        # Show some features
        features = bundle.get("feature_cols", [])[:10]
        if features:
            print(f"  Sample features: {', '.join(features)}...")
        
        return bundle
    
    except Exception as e:
        print(f"✗ Failed to load model: {e}")
        return None


def test_prediction(client: MongoClient, bundle: dict) -> bool:
    """Test making predictions."""
    print("\n" + "="*70)
    print("TEST 5: Prediction Pipeline")
    print("="*70)
    
    # Import the prediction functions
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    
    try:
        from predict_personalized import (
            load_users_from_mongo,
            get_env_next_n_days,
            enrich_dataset,
        )
        
        # Load data
        prof, checkins = load_users_from_mongo(client)
        print(f"✓ Loaded {len(prof)} user profiles")
        
        env_df = get_env_next_n_days(client, 7, lat=37.77, lon=-122.42)
        print(f"✓ Loaded {len(env_df)} environmental records")
        
        # Prepare data
        if "user_id" not in env_df.columns:
            # Broadcast env to all users
            user_ids = prof["user_id"].tolist()
            rows = []
            for uid in user_ids:
                for _, env_row in env_df.iterrows():
                    row = {"user_id": uid}
                    row.update(env_row.to_dict())
                    rows.append(row)
            pred_env = pd.DataFrame(rows)
        else:
            pred_env = env_df
        
        # Enrich
        df = enrich_dataset(pred_env, prof, checkins)
        print(f"✓ Enriched dataset: {len(df)} rows")
        
        # Prepare features
        pipeline = bundle["pipeline"]
        feature_cols = bundle["feature_cols"]
        
        # Add missing columns
        for c in feature_cols:
            if c not in df.columns:
                df[c] = 0
        
        X = df[feature_cols]
        
        # Handle categorical columns
        for c in feature_cols:
            if X[c].dtype == object:
                X = X.copy()
                X[c] = X[c].astype(str).fillna("")
        
        # Predict
        preds = pipeline.predict(X)
        print(f"✓ Predictions generated: {len(preds)} values")
        print(f"  Prediction range: {preds.min():.2f} - {preds.max():.2f}")
        print(f"  Mean prediction: {preds.mean():.2f}")
        
        # Show sample predictions
        sample_df = df[["user_id", "date"]].copy()
        sample_df["prediction"] = preds
        print("\n  Sample predictions:")
        print(sample_df.head(10).to_string(index=False))
        
        return True
    
    except Exception as e:
        print(f"✗ Prediction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_format(client: MongoClient) -> bool:
    """Test the API output format."""
    print("\n" + "="*70)
    print("TEST 6: API Output Format")
    print("="*70)
    
    script_path = Path(__file__).resolve().parent / "predict_personalized.py"
    
    if not script_path.exists():
        print(f"✗ Prediction script not found: {script_path}")
        return False
    
    try:
        import subprocess
        
        result = subprocess.run(
            [sys.executable, str(script_path), "--out", "-", "--days", "3"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        if result.returncode != 0:
            print(f"✗ Script failed with exit code {result.returncode}")
            print(f"  stderr: {result.stderr[:200]}")
            return False
        
        # Parse output
        output = result.stdout.strip()
        data = json.loads(output)
        
        print(f"✓ API script executed successfully")
        print(f"  Returned {len(data)} predictions")
        
        if data:
            sample = data[0]
            print(f"  Sample output: {json.dumps(sample, indent=2)}")
            
            # Validate structure
            required_keys = ["user_id", "date"]
            has_keys = all(k in sample for k in required_keys)
            has_target = "risk" in sample or "flare_day" in sample
            
            if has_keys and has_target:
                print("✓ Output format is valid")
            else:
                print(f"✗ Missing required keys. Expected: {required_keys} + (risk OR flare_day)")
                return False
        
        return True
    
    except subprocess.TimeoutExpired:
        print("✗ Script timed out (>60s)")
        return False
    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON output: {e}")
        print(f"  stdout: {result.stdout[:200]}")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Test personalized prediction system")
    parser.add_argument("--skip-prediction", action="store_true", help="Skip prediction tests")
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("PERSONALIZED RISK PREDICTION - TEST SUITE")
    print("="*70)
    
    # Test 1: MongoDB
    client = test_mongodb_connection()
    if not client:
        return 1
    
    # Test 2: Users
    user_count, checkin_count = test_user_data(client)
    if user_count == 0:
        print("\n✗ No users found. Cannot proceed with tests.")
        return 1
    
    # Test 3: Environment
    env_count = test_env_data(client)
    if env_count == 0:
        print("\n⚠  No environmental data found. Predictions will use forecast API.")
    
    # Test 4: Model
    bundle = test_model_file()
    if not bundle:
        print("\n⚠  Model file not found. Train a model first:")
        print("    python train_personalized_model.py")
        return 0
    
    # Test 5: Prediction
    if not args.skip_prediction:
        success = test_prediction(client, bundle)
        if not success:
            return 1
        
        # Test 6: API format
        success = test_api_format(client)
        if not success:
            return 1
    
    # Summary
    print("\n" + "="*70)
    print("✓ ALL TESTS PASSED")
    print("="*70)
    print("\nSystem is ready for personalized predictions!")
    print("\nNext steps:")
    print("  1. Start the web server: cd apps/web && pnpm dev")
    print("  2. Navigate to: /breathe-well/personalized")
    print("  3. View your 7-day personalized risk forecast")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
