#!/usr/bin/env python3
"""
Pull all TIDAL data by location + date.

Categories:
  - Air Quality: PM2.5 (mean, max), AQI, 24h trend  (AirNow / PurpleAir)
  - Weather: Temperature (min/max), humidity, wind speed, pressure, rain  (NOAA)
  - Pollen: Tree / grass / weed index  (public pollen datasets)
  - Time Context: Day of week, season, holidays  (derived)

Usage:
  python pull_by_location_date.py --lat 37.77 --lon -122.42 --date 2025-02-07
  python pull_by_location_date.py --zip 94102 --date 2025-02-07
  python pull_by_location_date.py --lat 37.77 --lon -122.42 --date 2025-02-07 --no-raw
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
import requests

# Load .env only (not .env.example)
try:
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parent
    load_dotenv(_root / ".env")
except ImportError:
    pass

import sys
from pathlib import Path

# Add the asthma-forecaster directory to Python path
sys.path.append(str(Path(__file__).parent / "asthma-forecaster"))

from apps.data_sources.air_quality import pull_air_quality
from apps.data_sources.weather import pull_noaa_weather
from apps.data_sources.pollen import pull_pollen
from apps.data_sources.time_context import pull_time_context


def get_zipcode_from_coordinates(latitude: float, longitude: float) -> str | None:
    """
    Get ZIP code from latitude/longitude using reverse geocoding.
    Uses OpenStreetMap Nominatim API (free, no API key required).
    """
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": latitude,
            "lon": longitude,
            "format": "json",
            "addressdetails": 1,
            "zoom": 18
        }
        headers = {
            "User-Agent": "TIDAL-Environmental-Data/1.0"
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Try to extract ZIP code from various possible fields
        address = data.get("address", {})
        zip_code = (
            address.get("postcode") or 
            address.get("postal_code") or 
            address.get("zipcode")
        )
        
        return zip_code
        
    except Exception as e:
        print(f"Warning: Could not determine ZIP code from coordinates: {e}")
        return None


def pull_all(
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    zip_code: str | None = None,
    target_date: date,
    include_raw: bool = True,
) -> dict:
    """
    Pull all data for the given location and date.
    Provide either (latitude, longitude) or zip_code.
    If coordinates are provided without zip_code, will attempt to lookup zip_code.
    """
    # If we have coordinates but no zip code, try to get it
    if latitude is not None and longitude is not None and zip_code is None:
        zip_code = get_zipcode_from_coordinates(latitude, longitude)
    
    out = {
        "location": {
            "latitude": latitude,
            "longitude": longitude,
            "zip_code": zip_code,
        },
        "date": target_date.isoformat(),
        "air_quality": None,
        "weather": None,
        "pollen": None,
        "time_context": None,
    }

    # Air Quality (AirNow or PurpleAir)
    aq = pull_air_quality(
        latitude=latitude,
        longitude=longitude,
        zip_code=zip_code,
        target_date=target_date,
    )
    out["air_quality"] = _strip_raw(aq) if not include_raw else aq

    # Weather (NOAA) — needs lat/lon
    lat = latitude
    lon = longitude
    if lat is None or lon is None:
        out["weather"] = {"error": "Weather requires latitude and longitude", "source": "NOAA"}
    else:
        w = pull_noaa_weather(latitude=lat, longitude=lon, target_date=target_date)
        out["weather"] = _strip_raw(w) if not include_raw else w

    # Pollen — needs lat/lon
    if lat is not None and lon is not None:
        p = pull_pollen(latitude=lat, longitude=lon, target_date=target_date)
        out["pollen"] = _strip_raw(p) if not include_raw else p
    else:
        out["pollen"] = {"error": "Pollen requires latitude and longitude", "source": "Pollen"}

    # Time context (derived)
    tc = pull_time_context(target_date)
    out["time_context"] = _strip_raw(tc) if not include_raw else tc

    return out


def _strip_raw(d: dict) -> dict:
    """Remove 'raw' key to keep output small."""
    return {k: v for k, v in d.items() if k != "raw"}


def main():
    parser = argparse.ArgumentParser(description="Pull TIDAL data by location + date")
    parser.add_argument("--lat", type=float, help="Latitude")
    parser.add_argument("--lon", type=float, help="Longitude")
    parser.add_argument("--zip", dest="zip_code", type=str, help="ZIP code (US)")
    parser.add_argument("--date", type=str, required=True, help="Date YYYY-MM-DD")
    parser.add_argument("--no-raw", action="store_true", help="Omit raw API responses from output")
    parser.add_argument("--out", type=str, help="Write JSON to file")
    parser.add_argument("--mongodb", action="store_true", help="Upsert one daily row into MongoDB (tidal.daily)")
    args = parser.parse_args()

    if not args.zip_code and (args.lat is None or args.lon is None):
        parser.error("Provide either --lat and --lon or --zip")

    try:
        target_date = date.fromisoformat(args.date)
    except ValueError:
        parser.error("--date must be YYYY-MM-DD")

    result = pull_all(
        latitude=args.lat,
        longitude=args.lon,
        zip_code=args.zip_code,
        target_date=target_date,
        include_raw=not args.no_raw,
    )

    if args.mongodb:
        try:
            from apps.db.daily_dataset import upsert_daily_row, get_collection
            r = upsert_daily_row(result)
            coll = get_collection()
            db_name, coll_name = coll.database.name, coll.name
            print(f"MongoDB: upserted 1 row -> database {db_name!r}, collection {coll_name!r}", file=sys.stderr)
        except Exception as e:
            print(f"MongoDB upsert failed: {e}", file=sys.stderr)

    json_str = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(json_str, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(json_str)


if __name__ == "__main__":
    main()
