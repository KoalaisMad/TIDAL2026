#!/usr/bin/env python3
"""
Generate ML env data by running the TIDAL pull pipeline and writing to a configurable
MongoDB collection. Schema matches data.py (TIDAL daily: PM2_5_mean, AQI, temp_*, etc.).

Usage (from TIDAL2026):
  PYTHONPATH=asthma-forecaster python -m apps.ml.generate_ml_data --collection ml_daily --lat 37.77 --lon -122.42 --start 2026-01-01 --end 2026-02-07
  # More data: multiple locations (N locations × days = rows)
  PYTHONPATH=asthma-forecaster python -m apps.ml.generate_ml_data --collection ml_daily --location 37.77,-122.42 --location 34.05,-118.24 --start 2025-10-11 --end 2026-02-07
  # Time-series collection (timeField=date, BSON Date): add --timeseries
  # Or set env: ML_ENV_COLL=ml_daily

Then run training on that collection:
  ML_ENV_COLL=ml_daily PYTHONPATH=asthma-forecaster python -m apps.ml.main --demo-labels
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Project root and .env
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

# TIDAL pull and db live in parent project; ensure we can import them
_tidal_root = Path(__file__).resolve().parent.parent.parent.parent
if str(_tidal_root) not in sys.path:
    sys.path.insert(0, str(_tidal_root))
if str(_tidal_root / "asthma-forecaster") not in sys.path:
    sys.path.insert(0, str(_tidal_root / "asthma-forecaster"))

from apps.db.daily_dataset import get_collection, create_timeseries_collection, insert_many_daily_rows

# Pull is in TIDAL2026 root
from pull_by_location_date import pull_all


def main():
    parser = argparse.ArgumentParser(description="Generate ML env data into a MongoDB collection (TIDAL schema)")
    parser.add_argument("--collection", default=os.environ.get("ML_ENV_COLL", "ml_daily"), help="Target collection name")
    parser.add_argument("--lat", type=float, help="Latitude (single location)")
    parser.add_argument("--lon", type=float, help="Longitude (single location)")
    parser.add_argument("--zip", dest="zip_code", type=str, help="ZIP code (single location)")
    parser.add_argument("--location", action="append", metavar="LAT,LON", help="Add a location (repeat for multiple). E.g. --location 37.77,-122.42 --location 34.05,-118.24")
    parser.add_argument("--start", type=str, required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--batch", type=int, default=7, help="Batch size for upserts")
    parser.add_argument("--timeseries", action="store_true", help="Create collection as MongoDB time-series (timeField=date, BSON Date)")
    args = parser.parse_args()

    # Build list of (lat, lon, zip_code): either from --location or single --lat/--lon or --zip
    locations: list[tuple[float | None, float | None, str | None]] = []
    if args.location:
        for s in args.location:
            try:
                part = s.strip().replace(" ", "").split(",")
                if len(part) != 2:
                    raise ValueError("Need lat,lon")
                lat, lon = float(part[0]), float(part[1])
                locations.append((lat, lon, None))
            except (ValueError, IndexError) as e:
                parser.error(f"Invalid --location {s!r}: use lat,lon (e.g. 37.77,-122.42)")
        if not locations:
            parser.error("Provide at least one --location lat,lon")
    elif args.zip_code:
        locations = [(None, None, args.zip_code)]
    elif args.lat is not None and args.lon is not None:
        locations = [(args.lat, args.lon, None)]
    else:
        parser.error("Provide --lat and --lon, or --zip, or one or more --location lat,lon")

    try:
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end)
    except ValueError:
        parser.error("--start and --end must be YYYY-MM-DD")
    if start > end:
        parser.error("--start must be <= --end")

    coll = create_timeseries_collection(collection_name=args.collection) if args.timeseries else get_collection(collection_name=args.collection)
    total = 0
    current = start
    num_locs = len(locations)
    while current <= end:
        batch_end = min(current + timedelta(days=args.batch - 1), end)
        results = []
        d = current
        while d <= batch_end:
            for lat, lon, zip_code in locations:
                result = pull_all(
                    latitude=lat,
                    longitude=lon,
                    zip_code=zip_code,
                    target_date=d,
                    include_raw=False,
                )
                results.append(result)
            d += timedelta(days=1)
        n = insert_many_daily_rows(results, coll=coll)
        total += n
        print(f"  {current} .. {batch_end}: {n} rows ({num_locs} locs)", file=sys.stderr)
        current = batch_end + timedelta(days=1)

    print(f"Done: {total} rows in {args.collection}", file=sys.stderr)
    print(f"Train with: ML_ENV_COLL={args.collection} python -m apps.ml.main [--demo-labels]", file=sys.stderr)


if __name__ == "__main__":
    main()
