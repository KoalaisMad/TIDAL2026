"""
Air Quality: PM2.5 (mean, max), AQI, 24h trend.
Sources: AirNow (primary), PurpleAir (optional).
Pulled by location + date.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

import requests


AIRNOW_BASE = "https://www.airnowapi.org"
# Historical by lat/lon: https://www.airnowapi.org/aq/observation/latLong/historical/
# Current by lat/lon: https://www.airnowapi.org/aq/observation/latLong/current/
# Historical by zip: https://www.airnowapi.org/aq/observation/zipCode/historical/


def _parse_airnow_obs(obs: dict[str, Any]) -> dict[str, Any]:
    """Extract PM2.5, AQI, and parameter name from one observation."""
    out = {}
    if obs.get("ParameterName") == "PM2.5":
        out["pm25"] = obs.get("AQI")  # AirNow often returns AQI for PM2.5; Concentration may also be present
        try:
            out["concentration"] = float(obs.get("RawConcentration", 0) or 0)
        except (TypeError, ValueError):
            out["concentration"] = None
    out["aqi"] = obs.get("AQI")
    out["category"] = obs.get("Category", {}).get("Name") if isinstance(obs.get("Category"), dict) else obs.get("CategoryName")
    out["date_utc"] = obs.get("DateObserved")
    return out


def _pm25_from_aqi(aqi: int | float) -> float | None:
    """Approximate PM2.5 (µg/m³) from AQI using EPA breakpoints (linear segment)."""
    if aqi is None:
        return None
    aqi = float(aqi)
    # EPA PM2.5 breakpoints (AQI -> µg/m³): 0-12->0-12, 12.1-35.4->12.1-35.4, 35.5-55.4->35.5-55.4, ...
    breakpoints = [
        (0, 0, 12, 12.0),
        (12.1, 35.4, 50, 35.4),
        (35.5, 55.4, 100, 55.4),
        (55.5, 150.4, 150, 150.4),
        (150.5, 250.4, 200, 250.4),
        (250.5, 350.4, 300, 350.4),
        (350.5, 500.4, 500, 500.4),
    ]
    for c_lo, c_hi, aqi_hi, _ in breakpoints:
        if aqi <= aqi_hi:
            if aqi_hi == 12:
                return aqi  # 1:1
            aqi_lo = 0 if aqi_hi == 50 else (breakpoints[breakpoints.index((c_lo, c_hi, aqi_hi, _)) - 1][2])
            return c_lo + (aqi - aqi_lo) * (c_hi - c_lo) / (aqi_hi - aqi_lo)
    return 500.4


def pull_airnow(
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    zip_code: str | None = None,
    target_date: date,
) -> dict[str, Any]:
    """
    Pull AirNow observations for a location and date.
    Provide either (latitude, longitude) or zip_code.
    Returns: pm25_mean, pm25_max, aqi (current/max for day), 24h_trend, source.
    """
    api_key = os.environ.get("AIRNOW_API_KEY", "").strip()
    if not api_key:
        return {
            "pm25_mean": None,
            "pm25_max": None,
            "aqi": None,
            "aqi_24h_trend": None,
            "source": "AirNow",
            "error": "AIRNOW_API_KEY not set",
            "raw": [],
        }

    if zip_code:
        url = f"{AIRNOW_BASE}/aq/observation/zipCode/historical/"
        params = {"zipCode": zip_code, "date": target_date.isoformat(), "format": "application/json", "API_KEY": api_key}
    elif latitude is not None and longitude is not None:
        url = f"{AIRNOW_BASE}/aq/observation/latLong/historical/"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "date": target_date.isoformat(),
            "format": "application/json",
            "API_KEY": api_key,
        }
    else:
        return {
            "pm25_mean": None,
            "pm25_max": None,
            "aqi": None,
            "aqi_24h_trend": None,
            "source": "AirNow",
            "error": "Provide (latitude, longitude) or zip_code",
            "raw": [],
        }

    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return {
            "pm25_mean": None,
            "pm25_max": None,
            "aqi": None,
            "aqi_24h_trend": None,
            "source": "AirNow",
            "error": str(e),
            "raw": [],
        }

    if not isinstance(data, list):
        data = [data] if data else []

    pm25_values: list[float] = []
    aqi_values: list[int | float] = []
    for obs in data:
        parsed = _parse_airnow_obs(obs)
        if parsed.get("concentration") is not None:
            pm25_values.append(parsed["concentration"])
        if parsed.get("aqi") is not None:
            aqi_values.append(parsed["aqi"])
        if parsed.get("pm25") is not None and parsed.get("concentration") is None:
            pm25_approx = _pm25_from_aqi(parsed["pm25"])
            if pm25_approx is not None:
                pm25_values.append(pm25_approx)
            aqi_values.append(parsed["pm25"])

    pm25_mean = sum(pm25_values) / len(pm25_values) if pm25_values else None
    pm25_max = max(pm25_values) if pm25_values else None
    aqi_max = max(aqi_values) if aqi_values else None

    # 24h trend: compare to previous day if we have it
    aqi_24h_trend = None
    prev_date = target_date - timedelta(days=1)
    try:
        prev_params = {**params, "date": prev_date.isoformat()}
        r_prev = requests.get(url, params=prev_params, timeout=15)
        if r_prev.ok:
            prev_data = r_prev.json() or []
            if not isinstance(prev_data, list):
                prev_data = [prev_data]
            prev_aqis = []
            for obs in prev_data:
                p = _parse_airnow_obs(obs)
                if p.get("aqi") is not None:
                    prev_aqis.append(p["aqi"])
            if prev_aqis and aqi_max is not None:
                prev_avg = sum(prev_aqis) / len(prev_aqis)
                aqi_24h_trend = "up" if aqi_max > prev_avg else ("down" if aqi_max < prev_avg else "stable")
    except Exception:
        pass

    return {
        "pm25_mean": round(pm25_mean, 2) if pm25_mean is not None else None,
        "pm25_max": round(pm25_max, 2) if pm25_max is not None else None,
        "aqi": int(aqi_max) if aqi_max is not None else None,
        "aqi_24h_trend": aqi_24h_trend,
        "source": "AirNow",
        "error": None,
        "raw": data,
    }


def pull_purpleair(
    *,
    latitude: float,
    longitude: float,
    target_date: date,
    radius_km: float = 10,
) -> dict[str, Any]:
    """
    Optional: PurpleAir sensors near lat/lon. Requires PURPLEAIR_READ_KEY.
    Returns same shape as AirNow for compatibility (pm25_mean, pm25_max, aqi, trend).
    """
    read_key = os.environ.get("PURPLEAIR_READ_KEY", "").strip()
    if not read_key:
        return {
            "pm25_mean": None,
            "pm25_max": None,
            "aqi": None,
            "aqi_24h_trend": None,
            "source": "PurpleAir",
            "error": "PURPLEAIR_READ_KEY not set",
            "raw": [],
        }

    # PurpleAir API: get sensors in bounding box, then filter by radius
    # Bounding box approx from lat/lon + radius
    import math
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.0 * max(math.cos(math.radians(latitude)), 0.01))
    nwlat = latitude + lat_delta
    selat = latitude - lat_delta
    nwlng = longitude - lon_delta
    selng = longitude + lon_delta

    url = "https://api.purpleair.com/v1/sensors"
    params = {
        "nwlat": nwlat,
        "selat": selat,
        "nwlng": nwlng,
        "selng": selng,
        "fields": "pm2.5_60minute,pm2.5_24hour",
    }
    headers = {"X-API-Key": read_key}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return {
            "pm25_mean": None,
            "pm25_max": None,
            "aqi": None,
            "aqi_24h_trend": None,
            "source": "PurpleAir",
            "error": str(e),
            "raw": [],
        }

    sensors = (data or {}).get("data") or []
    pm25_24h = []
    pm25_60m = []
    for row in sensors:
        # fields order: pm2.5_60minute, pm2.5_24hour
        if len(row) >= 2:
            try:
                p60 = float(row[-2]) if row[-2] is not None else None
                p24 = float(row[-1]) if row[-1] is not None else None
                if p24 is not None:
                    pm25_24h.append(p24)
                if p60 is not None:
                    pm25_60m.append(p60)
            except (TypeError, ValueError):
                pass

    def _aqi_from_pm25(pm25: float) -> float:
        if pm25 <= 12.0:
            return pm25 * (50 / 12) if pm25 >= 0 else 0
        if pm25 <= 35.4:
            return 50 + (pm25 - 12) * (50 / (35.4 - 12))
        if pm25 <= 55.4:
            return 100 + (pm25 - 35.4) * (50 / (55.4 - 35.4))
        if pm25 <= 150.4:
            return 150 + (pm25 - 55.4) * (100 / (150.4 - 55.4))
        if pm25 <= 250.4:
            return 200 + (pm25 - 150.4) * (100 / (250.4 - 150.4))
        if pm25 <= 500.4:
            return 300 + (pm25 - 250.4) * (200 / (500.4 - 250.4))
        return 500

    pm25_mean = sum(pm25_24h) / len(pm25_24h) if pm25_24h else (sum(pm25_60m) / len(pm25_60m) if pm25_60m else None)
    pm25_max = max(pm25_24h or pm25_60m) if (pm25_24h or pm25_60m) else None
    aqi = int(_aqi_from_pm25(pm25_mean)) if pm25_mean is not None else None

    return {
        "pm25_mean": round(pm25_mean, 2) if pm25_mean is not None else None,
        "pm25_max": round(pm25_max, 2) if pm25_max is not None else None,
        "aqi": aqi,
        "aqi_24h_trend": None,  # PurpleAir doesn't give previous day in same call
        "source": "PurpleAir",
        "error": None,
        "raw": sensors,
    }


def pull_air_quality(
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    zip_code: str | None = None,
    target_date: date,
    prefer_purpleair: bool = False,
) -> dict[str, Any]:
    """
    Pull air quality by location + date. Prefer AirNow unless prefer_purpleair=True and
    lat/lon are provided. Merges keys so you get pm25_mean, pm25_max, aqi, aqi_24h_trend, source.
    """
    if prefer_purpleair and latitude is not None and longitude is not None:
        out = pull_purpleair(latitude=latitude, longitude=longitude, target_date=target_date)
        if out.get("error"):
            out = pull_airnow(latitude=latitude, longitude=longitude, zip_code=zip_code, target_date=target_date)
    else:
        out = pull_airnow(latitude=latitude, longitude=longitude, zip_code=zip_code, target_date=target_date)
        if out.get("error") and latitude is not None and longitude is not None:
            fallback = pull_purpleair(latitude=latitude, longitude=longitude, target_date=target_date)
            if not fallback.get("error"):
                out = fallback
    return out
