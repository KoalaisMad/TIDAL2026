"""
Weather: Temperature (min/max), humidity, wind speed, pressure, rain.
Source: NOAA (National Weather Service api.weather.gov).
Pulled by location + date.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import requests


NWS_USER_AGENT = "(TIDAL2026, contact@example.com)"


def _nws_get(url: str) -> dict[str, Any] | None:
    try:
        r = requests.get(url, headers={"User-Agent": NWS_USER_AGENT}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _parse_interval(valid_time: str) -> tuple[datetime | None, datetime | None]:
    """Parse ISO 8601 interval e.g. '2024-01-15T06:00:00+00:00/PT1H' -> (start, end)."""
    if "/" not in valid_time:
        return None, None
    start_str, _ = valid_time.split("/", 1)
    try:
        # Handle +00:00 or Z
        start_str = start_str.replace("Z", "+00:00")
        start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        return start, None  # end not needed for filtering
    except Exception:
        return None, None


def _values_for_date(series: list[dict[str, Any]] | None, target: date, value_key: str = "value") -> list[float]:
    """Extract numeric values from NWS time series that fall on target date."""
    if not series:
        return []
    values = []
    for item in series:
        valid_time = item.get("validTime")
        if not valid_time:
            continue
        start, _ = _parse_interval(valid_time)
        if start and start.date() == target:
            v = item.get(value_key)
            if v is not None:
                try:
                    values.append(float(v))
                except (TypeError, ValueError):
                    pass
    return values


def pull_noaa_weather(
    *,
    latitude: float,
    longitude: float,
    target_date: date,
) -> dict[str, Any]:
    """
    Pull NOAA NWS weather for a location and date.
    Uses api.weather.gov: points/{lat},{lon} -> gridpoints -> forecastGridData.
    Returns: temp_min, temp_max, humidity (mean/max), wind_speed, pressure, rain (precipitation).
    """
    points_url = f"https://api.weather.gov/points/{latitude:.4f},{longitude:.4f}"
    points = _nws_get(points_url)
    if not points:
        return {
            "temp_min_c": None,
            "temp_max_c": None,
            "humidity_mean": None,
            "humidity_max": None,
            "wind_speed_kmh": None,
            "pressure_pa": None,
            "rain_mm": None,
            "source": "NOAA",
            "error": "Failed to get NWS points",
            "raw": None,
        }

    props = points.get("properties") or {}
    grid_url = props.get("forecastGridData")
    if not grid_url:
        return {
            "temp_min_c": None,
            "temp_max_c": None,
            "humidity_mean": None,
            "humidity_max": None,
            "wind_speed_kmh": None,
            "pressure_pa": None,
            "rain_mm": None,
            "source": "NOAA",
            "error": "No forecastGridData link",
            "raw": None,
        }

    grid = _nws_get(grid_url)
    if not grid:
        return {
            "temp_min_c": None,
            "temp_max_c": None,
            "humidity_mean": None,
            "humidity_max": None,
            "wind_speed_kmh": None,
            "pressure_pa": None,
            "rain_mm": None,
            "source": "NOAA",
            "error": "Failed to get grid data",
            "raw": None,
        }

    grid_props = grid.get("properties") or {}

    # NWS uses Fahrenheit and mph in grid; we convert to Celsius and km/h, pressure in Pa
    def f_to_c(f: float) -> float:
        return (f - 32) * 5 / 9

    def mph_to_kmh(mph: float) -> float:
        return mph * 1.60934

    def inHg_to_pa(inHg: float) -> float:
        return inHg * 3386.389

    def in_to_mm(in_val: float) -> float:
        return in_val * 25.4

    temp_min_vals = _values_for_date(grid_props.get("minTemperature", {}).get("values"), target_date)
    temp_max_vals = _values_for_date(grid_props.get("maxTemperature", {}).get("values"), target_date)
    # If no min/max series, use temperature series for the day
    if not temp_min_vals and not temp_max_vals:
        temp_vals = _values_for_date(grid_props.get("temperature", {}).get("values"), target_date)
        temp_min_c = f_to_c(min(temp_vals)) if temp_vals else None
        temp_max_c = f_to_c(max(temp_vals)) if temp_vals else None
    else:
        temp_min_c = f_to_c(min(temp_min_vals)) if temp_min_vals else None
        temp_max_c = f_to_c(max(temp_max_vals)) if temp_max_vals else None

    humidity_vals = _values_for_date(grid_props.get("relativeHumidity", {}).get("values"), target_date)
    humidity_mean = sum(humidity_vals) / len(humidity_vals) if humidity_vals else None
    humidity_max = max(humidity_vals) if humidity_vals else None

    wind_speed_vals = _values_for_date(grid_props.get("windSpeed", {}).get("values"), target_date)
    wind_speed_kmh = mph_to_kmh(sum(wind_speed_vals) / len(wind_speed_vals)) if wind_speed_vals else None

    pressure_vals = _values_for_date(grid_props.get("pressure", {}).get("values"), target_date)
    uom = (grid_props.get("pressure") or {}).get("uom", "")
    pressure_pa = None
    if pressure_vals:
        if "pa" in uom.lower() or uom == "Pa":
            pressure_pa = sum(pressure_vals) / len(pressure_vals)
        else:
            # Often inHg
            pressure_pa = inHg_to_pa(sum(pressure_vals) / len(pressure_vals))

    # Quantitative precipitation (liquid)
    qpf_vals = _values_for_date(grid_props.get("quantitativePrecipitation", {}).get("values"), target_date)
    rain_mm = sum(qpf_vals) if qpf_vals else None
    if rain_mm is not None and (grid_props.get("quantitativePrecipitation") or {}).get("uom", "").lower() in ("in", "inch"):
        rain_mm = in_to_mm(rain_mm)

    return {
        "temp_min_c": round(temp_min_c, 2) if temp_min_c is not None else None,
        "temp_max_c": round(temp_max_c, 2) if temp_max_c is not None else None,
        "humidity_mean": round(humidity_mean, 2) if humidity_mean is not None else None,
        "humidity_max": round(humidity_max, 2) if humidity_max is not None else None,
        "wind_speed_kmh": round(wind_speed_kmh, 2) if wind_speed_kmh is not None else None,
        "pressure_pa": round(pressure_pa, 2) if pressure_pa is not None else None,
        "rain_mm": round(rain_mm, 2) if rain_mm is not None else None,
        "source": "NOAA",
        "error": None,
        "raw": grid_props,
    }
