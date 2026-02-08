"""
Pollen: Tree / grass / weed index.
Source: Open-Meteo Air Quality API (pollen forecast); fallback: regional pollen
calendar when Open-Meteo returns null (e.g. US). No API key required.

Why pollen is often null from Open-Meteo:
- Open-Meteo pollen is Europe-only (CAMS European forecast). US and other regions
  get null tree/grass/weed indices.
- In Europe, data is only produced during pollen season; outside season = null.
- Forecast length is ~4 days; beyond that values may be null.

When Open-Meteo returns all nulls, we try NAB-based data (Houston Health Dept,
NAB Station 188) for Texas/southern US; if that fails, use a regional pollen
calendar (seasonal 0–5 indices by region).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

OPENMETEO_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# Houston Health Department (NAB Station 188) – real daily counts for Texas region
HOUSTON_POLLEN_LISTING_URL = "https://www.houstonhealth.org/services/pollen-mold"
HOUSTON_POLLEN_BASE_URL = "https://www.houstonhealth.org"
USER_AGENT = "TIDAL-Pollen/1.0 (asthma-forecaster; educational)"
# NAB level → 0–5 index (None=0, Low=1, Medium=2, Heavy=3, Extremely Heavy=4–5)
NAB_LEVEL_TO_INDEX = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "heavy": 3,
    "extremely heavy": 4,
    "extremelyheavy": 4,
}

# Regional pollen calendar: approximate 0–5 index by month (1–12) for tree, grass, weed.
# NOT from measured data: inferred from seasonal descriptions (cedar winter, oak/grass
# spring, ragweed fall). To base on real data, use NAB station data (pollen.aaaai.org,
# AAAAI NAB data request), EPA modeled pollen, or published pollen calendars (e.g.
# PMC6934246 / Springer "Pollen calendars and maps of allergenic pollen in North America").
# Used when Open-Meteo returns null (e.g. US locations).
POLLEN_CALENDAR_US_SOUTH = [
    (4, 0, 0),   # Jan: tree (cedar), grass low, weed low
    (4, 0, 0),   # Feb: tree (cedar/elm), grass low, weed low
    (4, 1, 0),   # Mar: tree (oak, ash), grass low, weed low
    (4, 2, 0),   # Apr: tree high, grass rising, weed low
    (3, 4, 0),   # May: tree, grass peak, weed low
    (2, 4, 1),   # Jun: tree lower, grass high, weed rising
    (2, 3, 2),   # Jul: tree low, grass, weed
    (2, 2, 3),   # Aug: cedar elm, grass, ragweed rising
    (2, 1, 4),   # Sep: tree low, grass low, ragweed peak
    (1, 0, 4),   # Oct: tree low, grass none, ragweed high
    (1, 0, 2),   # Nov: tree low, grass none, weed tail
    (3, 0, 0),   # Dec: tree (cedar), grass none, weed low
]


def _region_for_coords(latitude: float, longitude: float) -> str | None:
    """Return region key for pollen calendar, or None if outside known regions."""
    # Continental US (rough)
    if 24 <= latitude <= 50 and -125 <= longitude <= -66:
        # US South (Texas, OK, LA, AR, MS, AL, GA, SC, FL, etc.)
        if latitude < 37:
            return "US_South"
        return "US"
    return None


def _pollen_from_calendar(region: str, target_date: date) -> dict[str, Any]:
    """Return tree/grass/weed indices from regional pollen calendar (0–5 scale)."""
    if region == "US_South":
        row = POLLEN_CALENDAR_US_SOUTH[target_date.month - 1]
    else:
        # Generic US: use same calendar for now; can add US_North later
        row = POLLEN_CALENDAR_US_SOUTH[target_date.month - 1]
    return {
        "tree_index": row[0],
        "grass_index": row[1],
        "weed_index": row[2],
        "source": "Regional pollen calendar",
        "error": None,
        "raw": None,
    }


def _pull_nab_houston() -> dict[str, Any] | None:
    """
    Scrape latest daily pollen counts from Houston Health Department (NAB Station 188).
    Returns tree_index, grass_index, weed_index (0–5) from real NAB data, or None on failure.
    Houston reports Mon–Fri; weekends/holidays may have no new report.
    """
    import requests

    headers = {"User-Agent": USER_AGENT}
    try:
        r = requests.get(HOUSTON_POLLEN_LISTING_URL, headers=headers, timeout=15)
        r.raise_for_status()
        html = r.text
    except Exception:
        return None

    # First link to a daily report: href like /services/pollen-mold/houston-pollen-mold-count-...
    match = re.search(
        r'href=["\']([^"\']*houston-pollen-mold-count-[^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if not match:
        return None
    report_path = match.group(1).strip()
    if report_path.startswith("/"):
        report_url = HOUSTON_POLLEN_BASE_URL + report_path
    elif report_path.startswith("http"):
        report_url = report_path
    else:
        report_url = HOUSTON_POLLEN_LISTING_URL.rstrip("/") + "/" + report_path.lstrip("/")

    try:
        r2 = requests.get(report_url, headers=headers, timeout=15)
        r2.raise_for_status()
        page = r2.text
    except Exception:
        return None

    # Parse TREE POLLEN / GRASS POLLEN / WEED POLLEN levels (HEAVY, LOW, MEDIUM, NONE, Extremely Heavy)
    # Page may have "TREE POLLENHEAVY1,832" or "TREE POLLEN HEAVY 1,832"
    tree_index = grass_index = weed_index = None
    for kind, key in [("TREE", "tree_index"), ("GRASS", "grass_index"), ("WEED", "weed_index")]:
        pat = re.compile(
            rf"{re.escape(kind)}\s*POLLEN\s*(HEAVY|LOW|MEDIUM|NONE|Extremely\s*Heavy)\s*[\d,]*",
            re.IGNORECASE,
        )
        m = pat.search(page)
        if m:
            level = m.group(1).strip().lower().replace(" ", "")
            idx = NAB_LEVEL_TO_INDEX.get(level)
            if idx is not None:
                if key == "tree_index":
                    tree_index = idx
                elif key == "grass_index":
                    grass_index = idx
                else:
                    weed_index = idx

    if tree_index is None and grass_index is None and weed_index is None:
        return None

    return {
        "tree_index": tree_index,
        "grass_index": grass_index,
        "weed_index": weed_index,
        "source": "NAB (Houston HHD)",
        "error": None,
        "raw": None,
    }


def pull_pollen(
    *,
    latitude: float,
    longitude: float,
    target_date: date,    
) -> dict[str, Any]:
    """
    Pull pollen indices (tree, grass, weed) by location + date. Uses Open-Meteo
    when available (Europe); when Open-Meteo returns all null (e.g. US), uses
    a regional pollen calendar (seasonal 0–5 indices by region).
    """
    result = _pull_openmeteo_pollen(
        latitude=latitude,
        longitude=longitude,
        target_date=target_date,
    )
    # If Open-Meteo returned no data (e.g. US), try NAB (Houston) then regional calendar
    if (
        result.get("tree_index") is None
        and result.get("grass_index") is None
        and result.get("weed_index") is None
        and result.get("error") is None
    ):
        region = _region_for_coords(latitude, longitude)
        if region:
            # Texas / US South: use real NAB data from Houston HHD (Station 188) when available
            if region == "US_South":
                nab = _pull_nab_houston()
                if nab and (
                    nab.get("tree_index") is not None
                    or nab.get("grass_index") is not None
                    or nab.get("weed_index") is not None
                ):
                    return nab
            return _pollen_from_calendar(region, target_date)
    return result


def _pull_openmeteo_pollen(
    *,
    latitude: float,
    longitude: float,
    target_date: date,
) -> dict[str, Any]:
    """Open-Meteo Air Quality API: hourly pollen by lat/lon, aggregated to daily."""
    import requests

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": target_date.isoformat(),
        "end_date": target_date.isoformat(),
        "hourly": "alder_pollen,birch_pollen,grass_pollen,mugwort_pollen,olive_pollen,ragweed_pollen",
    }
    try:
        r = requests.get(OPENMETEO_AIR_QUALITY_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return {
            "tree_index": None,
            "grass_index": None,
            "weed_index": None,
            "source": "Open-Meteo Air Quality",
            "error": str(e),
            "raw": None,
        }

    hourly = (data or {}).get("hourly") or {}
    times = hourly.get("time") or []
    date_str = target_date.isoformat()

    tree_vals = []
    grass_vals = []
    weed_vals = []

    for i, t in enumerate(times):
        if not (isinstance(t, str) and t.startswith(date_str)):
            continue
        # Tree: max of alder, birch, olive (grains/m³)
        alder = _float_or_none(hourly.get("alder_pollen"), i)
        birch = _float_or_none(hourly.get("birch_pollen"), i)
        olive = _float_or_none(hourly.get("olive_pollen"), i)
        if alder is not None or birch is not None or olive is not None:
            tree_vals.append(max((x for x in (alder, birch, olive) if x is not None), default=None))
        # Grass
        g = _float_or_none(hourly.get("grass_pollen"), i)
        if g is not None:
            grass_vals.append(g)
        # Weed: max of mugwort, ragweed
        mugwort = _float_or_none(hourly.get("mugwort_pollen"), i)
        ragweed = _float_or_none(hourly.get("ragweed_pollen"), i)
        if mugwort is not None or ragweed is not None:
            weed_vals.append(max((x for x in (mugwort, ragweed) if x is not None), default=None))

    tree_index = max(tree_vals) if tree_vals else None
    grass_index = max(grass_vals) if grass_vals else None
    weed_index = max(weed_vals) if weed_vals else None

    return {
        "tree_index": tree_index,
        "grass_index": grass_index,
        "weed_index": weed_index,
        "source": "Open-Meteo Air Quality",
        "error": None,
        "raw": data,
    }


def _float_or_none(arr: Any, index: int) -> float | None:
    if arr is None or not isinstance(arr, (list, tuple)) or index >= len(arr):
        return None
    val = arr[index]
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def update_database_with_pollen(
    *,
    latitude: float,
    longitude: float,
    target_date: date,
    pollen_result: dict[str, Any],
) -> None:
    """
    Write pollen result to MongoDB so it appears in environment_daily and daily.
    Requires MONGODB_URI in environment. Uses asthma.environment_daily and
    tidal.daily (or MONGODB_DB / MONGODB_COLLECTION from apps.db.daily_dataset).
    """
    import os
    from datetime import datetime

    from pymongo import MongoClient

    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise ValueError("MONGODB_URI is not set")

    # Strip raw for storage
    pollen_doc = {k: v for k, v in pollen_result.items() if k != "raw"}
    date_str = target_date.isoformat()
    location_key = f"{latitude:.4f}_{longitude:.4f}"

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    try:
        # 1) environment_daily (same shape as ingest_to_mongodb)
        db_name = os.environ.get("MONGODB_DB", "asthma")
        coll = client[db_name]["environment_daily"]
        coll.update_one(
            {"locationKey": location_key, "date": date_str},
            {
                "$set": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "pollen": pollen_doc,
                    "ingestedAt": datetime.utcnow(),
                }
            },
            upsert=True,
        )
        # 2) daily (flattened pollen_tree, pollen_grass, pollen_weed)
        # Use same case as existing DB: MONGODB_TIDAL_DB or MONGODB_DB (e.g. TIDAL)
        tidal_db = os.environ.get("MONGODB_TIDAL_DB") or os.environ.get("MONGODB_DB", "tidal")
        daily_coll_name = os.environ.get("MONGODB_COLLECTION", "daily")
        daily_coll = client[tidal_db][daily_coll_name]
        location_id = f"{round(latitude, 4)}_{round(longitude, 4)}"
        daily_coll.update_one(
            {"location_id": location_id, "date": date_str},
            {
                "$set": {
                    "pollen_tree": pollen_result.get("tree_index"),
                    "pollen_grass": pollen_result.get("grass_index"),
                    "pollen_weed": pollen_result.get("weed_index"),
                }
            },
            upsert=True,
        )
    finally:
        client.close()


if __name__ == "__main__":
    # Run from asthma-forecaster/: python -m apps.data_sources.pollen [lat lon date] [--update-db]
    import argparse
    import json
    import sys
    from pathlib import Path

    # Load .env so MONGODB_URI is set when using --update-db (try cwd, asthma-forecaster, repo root)
    try:
        from dotenv import load_dotenv
        _dir = Path(__file__).resolve().parent
        for _path in [Path.cwd() / ".env", _dir.parent.parent / ".env", _dir.parent.parent.parent / ".env"]:
            if _path.exists():
                load_dotenv(_path)
                break
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description="Pull pollen and optionally update MongoDB")
    parser.add_argument("lat", type=float, nargs="?", default=30.6280, help="Latitude (default: 30.63 College Station, TX)")
    parser.add_argument("lon", type=float, nargs="?", default=-96.3344, help="Longitude (default: -96.33 College Station, TX)")
    parser.add_argument("date", type=str, nargs="?", default=None, help="Date YYYY-MM-DD (default: today)")
    parser.add_argument("--update-db", "-u", action="store_true", help="Upsert pollen into MongoDB (requires MONGODB_URI)")
    args = parser.parse_args()

    lat, lon = args.lat, args.lon
    day = args.date or date.today().isoformat()
    target = date.fromisoformat(day)

    result = pull_pollen(latitude=lat, longitude=lon, target_date=target)

    if args.update_db:
        try:
            update_database_with_pollen(
                latitude=lat,
                longitude=lon,
                target_date=target,
                pollen_result=result,
            )
            print("Database updated.", file=sys.stderr)
        except Exception as e:
            print(f"Database update failed: {e}", file=sys.stderr)
            sys.exit(1)

    out = {k: v for k, v in result.items() if k != "raw"}
    print(json.dumps(out, indent=2))
