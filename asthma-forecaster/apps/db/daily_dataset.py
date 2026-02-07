"""
MongoDB daily dataset: one document per day per location.

Columns (raw):
  PM2.5_mean, PM2.5_max, AQI
  temp_min, temp_max, humidity, wind, pressure, rain
  pollen_tree, pollen_grass, pollen_weed
  day_of_week, month, season, holiday_flag
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database

# Load .env from project root so env is set when db is used from any script
def _load_env():
    try:
        from dotenv import load_dotenv
        _root = Path(__file__).resolve().parent.parent
        for _path in [_root / ".env", Path.cwd() / ".env"]:
            if _path.exists():
                load_dotenv(_path)
                break
    except ImportError:
        pass


def _uri_encode_password(uri: str) -> str:
    """URL-encode the password in a MongoDB URI (e.g. < and > in Atlas passwords)."""
    from urllib.parse import quote_plus
    if "://" not in uri or "@" not in uri:
        return uri
    try:
        pre, rest = uri.split("://", 1)
        auth, host = rest.split("@", 1)
        if ":" in auth:
            user, password = auth.split(":", 1)
            password = quote_plus(password)
            auth = f"{user}:{password}"
        return f"{pre}://{auth}@{host}"
    except Exception:
        return uri


def get_collection() -> Collection:
    """Return the daily dataset collection (creates DB/client from env)."""
    _load_env()
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    uri = _uri_encode_password(uri)
    db_name = os.environ.get("MONGODB_DB", "tidal")
    coll_name = os.environ.get("MONGODB_COLLECTION", "daily")
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db: Database = client[db_name]
    coll = db[coll_name]
    _ensure_indexes(coll)
    return coll


def _ensure_indexes(coll: Collection) -> None:
    """Unique index on (location_id, date) for upserts."""
    coll.create_index([("location_id", ASCENDING), ("date", ASCENDING)], unique=True)
    coll.create_index([("date", ASCENDING)])
    coll.create_index([("latitude", ASCENDING), ("longitude", ASCENDING), ("date", ASCENDING)])


def location_id(latitude: float | None, longitude: float | None, zip_code: str | None) -> str:
    """Stable string id for a location (one row per day per location)."""
    if zip_code:
        return f"zip_{zip_code}"
    if latitude is not None and longitude is not None:
        return f"{round(latitude, 4)}_{round(longitude, 4)}"
    return "unknown"


def pull_result_to_daily_row(pull_result: dict[str, Any]) -> dict[str, Any]:
    """
    Convert output of pull_by_location_date.pull_all() into one daily row document
    with the requested raw columns.
    """
    loc = pull_result.get("location") or {}
    lat = loc.get("latitude")
    lon = loc.get("longitude")
    zip_code = loc.get("zip_code")
    target_date_str = pull_result.get("date") or ""
    try:
        d = date.fromisoformat(target_date_str)
        month = d.month
    except (TypeError, ValueError):
        month = None

    aq = pull_result.get("air_quality") or {}
    weather = pull_result.get("weather") or {}
    pollen = pull_result.get("pollen") or {}
    tc = pull_result.get("time_context") or {}

    doc: dict[str, Any] = {
        "location_id": location_id(lat, lon, zip_code),
        "latitude": lat,
        "longitude": lon,
        "zip_code": zip_code,
        "date": target_date_str,
        # Air quality (no dots in keys - MongoDB treats dot as path)
        "PM2_5_mean": aq.get("pm25_mean"),
        "PM2_5_max": aq.get("pm25_max"),
        "AQI": aq.get("aqi"),
        # Weather
        "temp_min": weather.get("temp_min_c"),
        "temp_max": weather.get("temp_max_c"),
        "humidity": weather.get("humidity_mean"),
        "wind": weather.get("wind_speed_kmh"),
        "pressure": weather.get("pressure_pa"),
        "rain": weather.get("rain_mm"),
        # Pollen
        "pollen_tree": pollen.get("tree_index"),
        "pollen_grass": pollen.get("grass_index"),
        "pollen_weed": pollen.get("weed_index"),
        # Time context
        "day_of_week": tc.get("day_of_week"),
        "month": month or tc.get("month"),
        "season": tc.get("season"),
        "holiday_flag": tc.get("is_holiday", False),
    }
    return doc


def upsert_daily_row(pull_result: dict[str, Any], *, coll: Collection | None = None) -> Any:
    """
    Insert or replace one daily row (by location_id + date). Returns result of update_one.
    """
    if coll is None:
        coll = get_collection()
    row = pull_result_to_daily_row(pull_result)
    lid = row["location_id"]
    dt = row["date"]
    result = coll.replace_one(
        {"location_id": lid, "date": dt},
        row,
        upsert=True,
    )
    return result


def insert_many_daily_rows(pull_results: list[dict[str, Any]], *, coll: Collection | None = None) -> int:
    """Bulk upsert many daily rows. Returns number of documents upserted/modified."""
    if coll is None:
        coll = get_collection()
    from pymongo import UpdateOne
    ops = []
    for pr in pull_results:
        row = pull_result_to_daily_row(pr)
        ops.append(
            UpdateOne(
                {"location_id": row["location_id"], "date": row["date"]},
                {"$set": row},
                upsert=True,
            )
        )
    if not ops:
        return 0
    res = coll.bulk_write(ops)
    return res.upserted_count + res.modified_count
