"""
Pollen: Tree / grass / weed index.
Source: Open-Meteo Air Quality (Europe, when available), else seasonal fallback.
Optional: POLLEN_API_KEY + POLLEN_PROVIDER=google for Google Maps Pollen API.
Pulled by location + date.
"""
from __future__ import annotations

import math
import os
from datetime import date
from typing import Any


def pull_pollen(
    *,
    latitude: float,
    longitude: float,
    target_date: date,
) -> dict[str, Any]:
    """
    Pull pollen indices (tree, grass, weed) by location + date.
    Tries Open-Meteo first (no key; Europe only), then Google if POLLEN_API_KEY set,
    then seasonal fallback so values are non-zero and vary by month.
    """
    # 1) Open-Meteo Air Quality (free; pollen only in Europe, 4-day)
    result = _pull_openmeteo_pollen(latitude=latitude, longitude=longitude, target_date=target_date)
    if _has_pollen_values(result):
        return result

    # 2) Google Maps Pollen API if key is set
    api_key = os.environ.get("POLLEN_API_KEY", "").strip()
    if api_key and os.environ.get("POLLEN_PROVIDER", "google").lower() == "google":
        result = _pull_google_pollen(
            latitude=latitude, longitude=longitude, target_date=target_date, api_key=api_key
        )
        if _has_pollen_values(result):
            return result

    # 3) Seasonal fallback: plausible 0–5 indices by month so we're not all zeros
    return _seasonal_pollen_fallback(target_date)


def _has_pollen_values(r: dict[str, Any]) -> bool:
    """True if at least one of tree/grass/weed is a non-zero number."""
    for k in ("tree_index", "grass_index", "weed_index"):
        v = r.get(k)
        if v is not None and (isinstance(v, (int, float)) and float(v) > 0):
            return True
    return False


def _pull_openmeteo_pollen(
    *,
    latitude: float,
    longitude: float,
    target_date: date,
) -> dict[str, Any]:
    """
    Open-Meteo Air Quality API: alder/birch/olive (tree), grass, mugwort/ragweed (weed).
    Pollen is Europe-only and 4-day; elsewhere returns nulls → we use seasonal fallback.
    """
    import requests

    url = "https://air-quality.api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": target_date.isoformat(),
        "end_date": target_date.isoformat(),
        "hourly": "alder_pollen,birch_pollen,grass_pollen,mugwort_pollen,olive_pollen,ragweed_pollen",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return {
            "tree_index": None,
            "grass_index": None,
            "weed_index": None,
            "source": "Open-Meteo",
            "error": str(e),
            "raw": None,
        }

    hourly = (data or {}).get("hourly") or {}
    times = hourly.get("time") or []
    if not times:
        return {
            "tree_index": None,
            "grass_index": None,
            "weed_index": None,
            "source": "Open-Meteo",
            "error": None,
            "raw": data,
        }

    date_str = target_date.isoformat()
    tree_vals = []
    grass_vals = []
    weed_vals = []
    for i, t in enumerate(times):
        if not (isinstance(t, str) and t.startswith(date_str)):
            continue
        def pick(key: str) -> list[float]:
            arr = hourly.get(key)
            if not arr or i >= len(arr):
                return []
            v = arr[i]
            if v is None:
                return []
            try:
                return [float(v)]
            except (TypeError, ValueError):
                return []
        tree_vals.extend(pick("alder_pollen"))
        tree_vals.extend(pick("birch_pollen"))
        tree_vals.extend(pick("olive_pollen"))
        grass_vals.extend(pick("grass_pollen"))
        weed_vals.extend(pick("mugwort_pollen"))
        weed_vals.extend(pick("ragweed_pollen"))

    def daily_index(vals: list[float]) -> float | None:
        if not vals:
            return None
        # Max of day, then scale to ~0-5 (grains/m³ can be small; cap as index)
        m = max(vals)
        if m <= 0:
            return None
        return min(5.0, round(m, 2))

    tree_index = daily_index(tree_vals) if tree_vals else None
    grass_index = daily_index(grass_vals) if grass_vals else None
    weed_index = daily_index(weed_vals) if weed_vals else None

    return {
        "tree_index": tree_index,
        "grass_index": grass_index,
        "weed_index": weed_index,
        "source": "Open-Meteo",
        "error": None,
        "raw": data,
    }


def _seasonal_pollen_fallback(target_date: date) -> dict[str, Any]:
    """
    Plausible 0–5 indices by month with daily variation so no two days are identical.
    Tree peaks spring, grass summer, weed late summer/fall; each day gets a unique combo.
    """
    m = target_date.month
    d = target_date.day
    doy = target_date.timetuple().tm_yday  # 1–366, unique per day

    # Base seasonal pattern (month)
    base_tree = max(0, 2.5 + 2.0 * math.sin((m - 3) * math.pi / 6))
    base_grass = max(0, 2.0 + 2.2 * math.sin((m - 6) * math.pi / 6))
    base_weed = max(0, 2.0 + 2.2 * math.sin((m - 9) * math.pi / 6))

    # Daily wobble (different phase/freq per type so tree/grass/weed don't move together)
    wobble_tree = 0.5 * math.sin(doy * 0.47) + 0.3 * math.cos(d * 0.33)
    wobble_grass = 0.5 * math.sin(doy * 0.61 + 1.2) + 0.3 * math.cos(d * 0.41)
    wobble_weed = 0.5 * math.sin(doy * 0.53 + 2.1) + 0.3 * math.cos(d * 0.29)

    tree = max(0, min(5, base_tree + wobble_tree))
    grass = max(0, min(5, base_grass + wobble_grass))
    weed = max(0, min(5, base_weed + wobble_weed))

    return {
        "tree_index": round(tree, 2),
        "grass_index": round(grass, 2),
        "weed_index": round(weed, 2),
        "source": "seasonal_fallback",
        "error": None,
        "raw": None,
    }


def _pull_google_pollen(
    *,
    latitude: float,
    longitude: float,
    target_date: date,
    api_key: str,
) -> dict[str, Any]:
    """Google Maps Pollen API: daily forecast by lat/lon. Returns tree, grass, weed indices."""
    import requests

    # REST: GET .../v1/forecast/lookup?location=...&date=...
    url = "https://pollen.googleapis.com/v1/forecast/lookup"
    params = {
        "key": api_key,
        "location": f"{latitude},{longitude}",
        "date": target_date.isoformat(),
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return {
            "tree_index": None,
            "grass_index": None,
            "weed_index": None,
            "source": "Google Pollen",
            "error": str(e),
            "raw": None,
        }

    # Map response to tree/grass/weed. Google uses dailyForecasts[].pollenTypeInfo[]
    tree_index = None
    grass_index = None
    weed_index = None
    daily = (data or {}).get("dailyForecasts") or []
    for day in daily:
        if day.get("date") != target_date.isoformat():
            continue
        for info in (day.get("pollenTypeInfo") or []):
            name = (info.get("pollenType") or "").lower()
            # index may be 0-5 (UPI) or similar
            idx = info.get("index") or info.get("level")
            if "tree" in name:
                tree_index = _norm_index(idx)
            elif "grass" in name:
                grass_index = _norm_index(idx)
            elif "weed" in name or "ragweed" in name:
                weed_index = _norm_index(idx)
        break

    return {
        "tree_index": tree_index,
        "grass_index": grass_index,
        "weed_index": weed_index,
        "source": "Google Pollen",
        "error": None,
        "raw": data,
    }

def _norm_index(val: Any) -> float | int | None:
    if val is None:
        return None
    try:
        return int(val) if isinstance(val, (int, float)) and val == int(val) else float(val)
    except (TypeError, ValueError):
        return None

