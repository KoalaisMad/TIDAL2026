"""
Seed symptom_daily with demo labels so the ML pipeline can train.

Reads dates from the TIDAL daily collection, inserts { user_id, date, flare } with
synthetic flare (e.g. random or rule-based: flare=1 when AQI > 50 or PM2_5_mean > 15).

Usage (from TIDAL2026):
  python -m apps.ml.seed_demo_labels
  python -m apps.ml.seed_demo_labels --user demo_user --rule-based
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

def _load_env():
    try:
        from dotenv import load_dotenv
        root = Path(__file__).resolve().parent.parent.parent.parent
        for p in [root / ".env", Path.cwd() / ".env"]:
            if p.exists():
                load_dotenv(p)
                break
    except ImportError:
        pass


_load_env()

from pymongo import MongoClient


def _mongo_uri():
    uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    if "@" in uri and "://" in uri:
        from urllib.parse import quote_plus
        try:
            pre, rest = uri.split("://", 1)
            auth, host = rest.split("@", 1)
            if ":" in auth:
                user, password = auth.split(":", 1)
                auth = f"{user}:{quote_plus(password)}"
            uri = f"{pre}://{auth}@{host}"
        except Exception:
            pass
    return uri


DB_NAME = os.environ.get("MONGODB_DB") or os.environ.get("DB_NAME", "tidal")
ENV_COLL = os.environ.get("ML_ENV_COLL") or os.environ.get("ENV_COLL") or os.environ.get("MONGODB_COLLECTION", "pulldata")
LABEL_COLL = os.environ.get("LABEL_COLL", "symptom_daily")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="demo_user", help="user_id for labels")
    parser.add_argument("--rule-based", action="store_true", help="flare=1 when AQI>50 or PM2_5_mean>15; else random 0/1")
    parser.add_argument("--seed", type=int, default=42, help="random seed")
    args = parser.parse_args()

    client = MongoClient(_mongo_uri(), serverSelectionTimeoutMS=10000)
    db = client[DB_NAME]
    env_coll = db[ENV_COLL]
    label_coll = db[LABEL_COLL]

    docs = list(env_coll.find({}, {"_id": 0, "date": 1, "AQI": 1, "PM2_5_mean": 1}).sort("date", 1))
    if not docs:
        print(f"No docs in {DB_NAME}.{ENV_COLL}. Run TIDAL pull first.", file=sys.stderr)
        sys.exit(1)

    import random
    random.seed(args.seed)
    to_insert = []
    for d in docs:
        date_str = d.get("date")
        if not date_str:
            continue
        aqi = d.get("AQI")
        pm = d.get("PM2_5_mean")
        if args.rule_based:
            flare = 1 if (aqi is not None and aqi > 50) or (pm is not None and pm > 15) else 0
        else:
            flare = random.randint(0, 1)
        to_insert.append({"user_id": args.user, "date": date_str, "flare": flare})

    if to_insert:
        label_coll.delete_many({"user_id": args.user})
        label_coll.insert_many(to_insert)
        print(f"Inserted {len(to_insert)} labels for user_id={args.user!r} into {DB_NAME}.{LABEL_COLL}")
    else:
        print("No dates to label.", file=sys.stderr)


if __name__ == "__main__":
    main()
