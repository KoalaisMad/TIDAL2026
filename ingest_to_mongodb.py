#!/usr/bin/env python3
"""
Ingest TIDAL data (weather, air quality, pollen, time context) into MongoDB
for use by the Allergy Predictor app and data analysis.

Collection: environment_daily
Document: { locationKey, date, latitude, longitude, zipCode?, air_quality, weather, pollen, time_context, ingestedAt }

Usage:
  python ingest_to_mongodb.py --lat 37.77 --lon -122.42 --date 2025-02-07
  python ingest_to_mongodb.py --lat 37.77 --lon -122.42 --start 2025-02-01 --end 2025-02-07
  python ingest_to_mongodb.py --zip 94102 --date 2025-02-07
"""
from __future__ import annotations

import argparse
import os
from datetime import date, datetime, timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pymongo import MongoClient

from pull_by_location_date import pull_all


def location_key(lat: float | None, lon: float | None, zip_code: str | None) -> str:
    if lat is not None and lon is not None:
        return f"{lat:.4f}_{lon:.4f}"
    if zip_code:
        return f"zip_{zip_code}"
    return "unknown"


def ingest_one(
    *,
    latitude: float | None,
    longitude: float | None,
    zip_code: str | None,
    target_date: date,
    db,
    include_raw: bool = False,
) -> bool:
    data = pull_all(
        latitude=latitude,
        longitude=longitude,
        zip_code=zip_code,
        target_date=target_date,
        include_raw=include_raw,
    )
    key = location_key(latitude, longitude, zip_code)
    doc = {
        "locationKey": key,
        "date": target_date.isoformat(),
        "latitude": data["location"].get("latitude"),
        "longitude": data["location"].get("longitude"),
        "zipCode": data["location"].get("zip_code"),
        "air_quality": data["air_quality"],
        "weather": data["weather"],
        "pollen": data["pollen"],
        "time_context": data["time_context"],
        "ingestedAt": datetime.utcnow(),
    }

    coll = db.environment_daily
    coll.update_one(
        {"locationKey": key, "date": doc["date"]},
        {"$set": doc},
        upsert=True,
    )
    return True


def main():
    parser = argparse.ArgumentParser(description="Ingest TIDAL data into MongoDB")
    parser.add_argument("--lat", type=float, help="Latitude")
    parser.add_argument("--lon", type=float, help="Longitude")
    parser.add_argument("--zip", dest="zip_code", type=str, help="ZIP code (US)")
    parser.add_argument("--date", type=str, help="Single date YYYY-MM-DD")
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD (range)")
    parser.add_argument("--end", type=str, help="End date YYYY-MM-DD (range)")
    parser.add_argument("--no-raw", action="store_true", help="Do not store raw API responses")
    parser.add_argument("--db", type=str, default="asthma", help="MongoDB database name")
    args = parser.parse_args()

    if not args.zip_code and (args.lat is None or args.lon is None):
        parser.error("Provide either --lat and --lon or --zip")

    uri = os.environ.get("MONGODB_URI")
    if not uri:
        print("Set MONGODB_URI in .env")
        return 1

    if args.date:
        try:
            start_d = end_d = date.fromisoformat(args.date)
        except ValueError:
            parser.error("--date must be YYYY-MM-DD")
    elif args.start and args.end:
        try:
            start_d = date.fromisoformat(args.start)
            end_d = date.fromisoformat(args.end)
            if start_d > end_d:
                start_d, end_d = end_d, start_d
        except ValueError:
            parser.error("--start and --end must be YYYY-MM-DD")
    else:
        parser.error("Provide --date or both --start and --end")

    client = MongoClient(uri)
    db = client[args.db]
    include_raw = not args.no_raw

    d = start_d
    while d <= end_d:
        ingest_one(
            latitude=args.lat,
            longitude=args.lon,
            zip_code=args.zip_code,
            target_date=d,
            db=db,
            include_raw=include_raw,
        )
        print(f"Ingested {d.isoformat()}")
        d += timedelta(days=1)

    print("Done.")
    return 0


if __name__ == "__main__":
    exit(main() or 0)
