# TIDAL – Data by Location + Date

Pull environmental and time-context data **by location and date** for:

| Category      | Variables | Source |
|---------------|-----------|--------|
| **Air Quality** | PM2.5 (mean, max), AQI, 24h trend | AirNow / PurpleAir |
| **Weather**   | Temperature (min/max), humidity, wind speed, pressure, rain | NOAA (api.weather.gov) |
| **Pollen**    | Tree / grass / weed index | Public pollen datasets (e.g. Google Maps Pollen API) |
| **Time Context** | Day of week, season, holidays | Derived |

## Setup

```bash
cd TIDAL2026
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set keys as needed:

- **AIRNOW_API_KEY** – Required for air quality. Get a key at [AirNow API](https://docs.airnowapi.org/).
- **PURPLEAIR_READ_KEY** – Optional; alternative/supplement for PM2.5 (PurpleAir).
- **POLLEN_API_KEY** – Optional; for pollen indices (e.g. Google Maps Pollen API).

## Usage

Pull data for a **location + date**:

```bash
# By latitude/longitude (required for weather and pollen)
python pull_by_location_date.py --lat 37.77 --lon -122.42 --date 2025-02-07

# By US ZIP (air quality only; weather/pollen still need lat/lon or a separate geocode step)
python pull_by_location_date.py --zip 94102 --date 2025-02-07

# Compact output (no raw API responses)
python pull_by_location_date.py --lat 37.77 --lon -122.42 --date 2025-02-07 --no-raw

# Save to file
python pull_by_location_date.py --lat 37.77 --lon -122.42 --date 2025-02-07 --out data.json
```

## Output shape

JSON with:

- **location** – `latitude`, `longitude`, `zip_code` (as provided).
- **date** – `YYYY-MM-DD`.
- **air_quality** – `pm25_mean`, `pm25_max`, `aqi`, `aqi_24h_trend`, `source`, optional `error`.
- **weather** – `temp_min_c`, `temp_max_c`, `humidity_mean`, `humidity_max`, `wind_speed_kmh`, `pressure_pa`, `rain_mm`, `source`, optional `error`.
- **pollen** – `tree_index`, `grass_index`, `weed_index`, `source`, optional `error`.
- **time_context** – `day_of_week`, `day_of_week_num`, `season`, `is_holiday`, `source`.

If an API key is missing or a request fails, the corresponding block includes an `error` field; other blocks still run.

## Programmatic use

```python
from datetime import date
from pull_by_location_date import pull_all

data = pull_all(
    latitude=37.77,
    longitude=-122.42,
    target_date=date(2025, 2, 7),
    include_raw=False,
)
# data["air_quality"], data["weather"], data["pollen"], data["time_context"]
```

## Notes

- **NOAA** (weather) does not require an API key; rate limits apply.
- **AirNow** historical data is by reporting area (zip or lat/lon); 24h trend is computed by comparing to the previous day when available.
- **Pollen**: set `POLLEN_PROVIDER=google` and a Google Maps API key with Pollen API enabled for tree/grass/weed indices.
