"""
Pollen: Tree / grass / weed index.
Source: Public pollen datasets (e.g. Google Maps Pollen API, Ambee, Tomorrow.io).
Pulled by location + date.
"""
from __future__ import annotations

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
    Requires POLLEN_API_KEY and a provider (e.g. Google, Ambee). This module
    provides the interface; implement the actual API call for your chosen provider.

    Google Maps Pollen API: tree/grass/weed in Universal Pollen Index (0-5 scale).
    Ambee: tree, grass, weed risk levels.
    """
    api_key = os.environ.get("POLLEN_API_KEY", "").strip()
    if not api_key:
        return {
            "tree_index": None,
            "grass_index": None,
            "weed_index": None,
            "source": "Pollen",
            "error": "POLLEN_API_KEY not set. Use Google Maps Pollen API, Ambee, or Tomorrow.io.",
            "raw": None,
        }

    # Optional: Google Maps Pollen API (forecast.lookup by lat/lon and date)
    # https://developers.google.com/maps/documentation/pollen/reference/rest/v1/forecast/lookup
    provider = os.environ.get("POLLEN_PROVIDER", "google").lower()
    if provider == "google":
        return _pull_google_pollen(latitude=latitude, longitude=longitude, target_date=target_date, api_key=api_key)

    # Placeholder for other providers
    return {
        "tree_index": None,
        "grass_index": None,
        "weed_index": None,
        "source": "Pollen",
        "error": f"Provider '{provider}' not implemented. Set POLLEN_PROVIDER=google or add implementation.",
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
