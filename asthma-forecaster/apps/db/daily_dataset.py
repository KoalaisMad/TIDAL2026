"""
MongoDB daily dataset: one document per day per location.

Columns (raw):
  PM2.5_mean, PM2.5_max, AQI
  temp_min, temp_max, humidity, wind, pressure, rain
  pollen_tree, pollen_grass, pollen_weed
  day_of_week, month, season, holiday_flag

Time-series: The "date" field is stored as BSON Date (datetime UTC) so it can
serve as timeField for a MongoDB time-series collection. Use
create_timeseries_collection() once to create a new collection with
timeseries={ "timeField": "date" }; existing collections cannot be converted.
"""
from __future__ import annotations

import os
from datetime import date, datetime, time, timezone
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


def get_collection(collection_name: str | None = None) -> Collection:
    """Return the daily dataset collection. If collection_name is set, use that instead of MONGODB_COLLECTION."""
    _load_env()
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    uri = _uri_encode_password(uri)
    db_name = os.environ.get("MONGODB_DB", "tidal")
    coll_name = collection_name or os.environ.get("MONGODB_COLLECTION", "daily")
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db: Database = client[db_name]
    coll = db[coll_name]
    _ensure_indexes(coll)
    return coll


def create_timeseries_collection(
    collection_name: str | None = None,
    *,
    time_field: str = "date",
    client: MongoClient | None = None,
) -> Collection:
    """
    Create a time-series collection for the daily dataset (if it does not exist).
    The timeField must be a BSON date; we store "date" as datetime in pull_result_to_daily_row.

    Use this once before writing to a new collection you want as time-series.
    Existing collections cannot be converted to time-series.
    """
    _load_env()
    if client is None:
        uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
        uri = _uri_encode_password(uri)
        client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db_name = os.environ.get("MONGODB_DB", "tidal")
    coll_name = collection_name or os.environ.get("MONGODB_COLLECTION", "daily")
    db: Database = client[db_name]
    if coll_name not in db.list_collection_names():
        db.create_collection(
            coll_name,
            timeseries={"timeField": time_field},
        )
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


# Defaults for missing values so stored rows have minimal nulls
_DAILY_DEFAULTS: dict[str, Any] = {
    "PM2_5_mean": 0.0,
    "PM2_5_max": 0.0,
    "AQI": 50,
    "temp_min": 15.0,
    "temp_max": 20.0,
    "humidity": 50.0,
    "wind": 0.0,
    "pressure": 101325.0,
    "rain": 0.0,
    "pollen_tree": 0.0,
    "pollen_grass": 0.0,
    "pollen_weed": 0.0,
    "holiday_flag": False,
}


def _season_from_month(m: int) -> int:
    """1=winter, 2=spring, 3=summer, 4=fall."""
    if m in (12, 1, 2):
        return 1
    if m in (3, 4, 5):
        return 2
    if m in (6, 7, 8):
        return 3
    return 4


def _fill_daily_row_nulls(doc: dict[str, Any]) -> dict[str, Any]:
    """Replace None with sensible defaults so most fields are non-null."""
    out = dict(doc)
    dt = out.get("date")
    for key, default in _DAILY_DEFAULTS.items():
        if key in out and out[key] is None:
            out[key] = default
    if out.get("day_of_week") is None and dt is not None:
        d = dt.date() if hasattr(dt, "date") else (date.fromisoformat(str(dt)[:10]) if isinstance(dt, str) else None)
        if d is not None:
            out["day_of_week"] = d.weekday()  # 0=Monday
    if out.get("month") is None and dt is not None:
        d = dt.date() if hasattr(dt, "date") else (date.fromisoformat(str(dt)[:10]) if isinstance(dt, str) else None)
        if d is not None:
            out["month"] = d.month
    if out.get("season") is None and out.get("month") is not None:
        out["season"] = _season_from_month(int(out["month"]))
    for key in ("day_of_week", "month", "season"):
        if key in out and out[key] is None:
            out[key] = 0
    return out


def pull_result_to_daily_row(pull_result: dict[str, Any]) -> dict[str, Any]:
    """
    Convert output of pull_by_location_date.pull_all() into one daily row document
    with the requested raw columns. Fills nulls with sensible defaults.
    """
    loc = pull_result.get("location") or {}
    lat = loc.get("latitude")
    lon = loc.get("longitude")
    zip_code = loc.get("zip_code")
    target_date_str = pull_result.get("date") or ""
    try:
        d = date.fromisoformat(target_date_str)
        month = d.month
        # BSON Date for time-series timeField (required for MongoDB time-series collections)
        date_bson = datetime.combine(d, time.min, tzinfo=timezone.utc)
    except (TypeError, ValueError):
        month = None
        date_bson = None

    aq = pull_result.get("air_quality") or {}
    weather = pull_result.get("weather") or {}
    pollen = pull_result.get("pollen") or {}
    tc = pull_result.get("time_context") or {}

    doc: dict[str, Any] = {
        "location_id": location_id(lat, lon, zip_code),
        "latitude": lat,
        "longitude": lon,
        "zip_code": zip_code,
        "date": date_bson if date_bson is not None else target_date_str,
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
    return _fill_daily_row_nulls(doc)


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
