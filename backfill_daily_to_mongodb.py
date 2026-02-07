#!/usr/bin/env python3
"""
Backfill the MongoDB daily dataset for a location and date range.
One row per day per location; upserts into tidal.daily.

Usage:
  python backfill_daily_to_mongodb.py --lat 37.77 --lon -122.42 --start 2025-01-01 --end 2025-01-31
  python backfill_daily_to_mongodb.py --zip 94102 --start 2025-01-01 --end 2025-01-07
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

try:
    from dotenv import load_dotenv
    from pathlib import Path
    _root = Path(__file__).resolve().parent
    load_dotenv(_root / ".env")
except ImportError:
    pass

from pull_by_location_date import pull_all

# Add the asthma-forecaster directory to Python path
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / "asthma-forecaster"))

from apps.db.daily_dataset import get_collection, insert_many_daily_rows


def main():
    parser = argparse.ArgumentParser(description="Backfill daily rows to MongoDB")
    parser.add_argument("--lat", type=float, help="Latitude")
    parser.add_argument("--lon", type=float, help="Longitude")
    parser.add_argument("--zip", dest="zip_code", type=str, help="ZIP code (US)")
    parser.add_argument("--start", type=str, required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--batch", type=int, default=7, help="Upsert in batches of N (default 7)")
    args = parser.parse_args()

    if not args.zip_code and (args.lat is None or args.lon is None):
        parser.error("Provide either --lat and --lon or --zip")

    try:
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end)
    except ValueError:
        parser.error("--start and --end must be YYYY-MM-DD")
    if start > end:
        parser.error("--start must be <= --end")

    coll = get_collection()
    total = 0
    current = start
    while current <= end:
        batch_end = min(current + timedelta(days=args.batch - 1), end)
        results = []
        d = current
        while d <= batch_end:
            result = pull_all(
                latitude=args.lat,
                longitude=args.lon,
                zip_code=args.zip_code,
                target_date=d,
                include_raw=False,
            )
            results.append(result)
            d += timedelta(days=1)
        n = insert_many_daily_rows(results, coll=coll)
        total += n
        print(f"  {current} .. {batch_end}: {n} rows", file=sys.stderr)
        current = batch_end + timedelta(days=1)

    print(f"Done: {total} rows upserted", file=sys.stderr)


if __name__ == "__main__":
    main()
