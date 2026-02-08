"""
Fetch environmental data for the past N days for a lat/lon, fetch Google Trends
daily interest for "allergy" (or your keyword) for the same date range, join them, and
label "flare_day" for the top fraction of days by trends (or by a fixed threshold).

DATA SOURCES (chosen for speed/ease):
- Air quality (PM2.5): Open-Meteo Air Quality API (hourly PM2.5)
- Weather: Open-Meteo Forecast API (hourly temp, humidity, wind, pressure, rain)
- Trends: pytrends (unofficial Google Trends client)

INSTALL (PowerShell):
  python -m pip install pandas requests pytrends tqdm

USAGE (PowerShell):
  python dataset.py --lat 37.77 --lon -122.42 --geo US-CA-807 --keyword allergy
  python dataset.py --lat 37.77 --lon -122.42 --days 90 --flare-percentile 75
  python dataset.py --lat 37.77 --lon -122.42 --threshold 80   # fixed threshold instead of percentile

OUTPUT:
  dataset_two_weeks.csv (unless overridden with --out)

NOTES:
- Google Trends values are normalized 0–100 within the requested timeframe/geo, so a fixed
  threshold often marks most days as flare. Default uses --flare-percentile so only the
  top (100 - percentile)% of days in your range are labeled flare_day=1.
- Default date range is 300 days; use --days to change.
"""

import argparse
from datetime import date, timedelta
import time
import requests
import pandas as pd
from pytrends.request import TrendReq


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def fetch_open_meteo_weather(lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    """
    Returns hourly weather, then we aggregate to daily.
    Uses Historical Weather API (archive) so long date ranges (e.g. 300 days) are supported.
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "rain",
            "surface_pressure",
            "wind_speed_10m",
        ]),
        "timezone": "UTC"
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    j = r.json()

    hourly = j.get("hourly", {})
    df = pd.DataFrame({
        "time": hourly.get("time", []),
        "temp": hourly.get("temperature_2m", []),
        "humidity": hourly.get("relative_humidity_2m", []),
        "rain": hourly.get("rain", []),
        "pressure": hourly.get("surface_pressure", []),
        "wind": hourly.get("wind_speed_10m", []),
    })
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df["date"] = df["time"].dt.date.astype(str)

    daily = df.groupby("date", as_index=False).agg(
        temp_min=("temp", "min"),
        temp_max=("temp", "max"),
        humidity=("humidity", "mean"),
        wind=("wind", "mean"),
        pressure=("pressure", "mean"),
        rain=("rain", "sum"),
    )
    return daily


def fetch_open_meteo_air_quality(lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    """
    Returns hourly PM2.5, then we aggregate to daily mean/max.
    """
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": "pm2_5",
        "timezone": "UTC"
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    j = r.json()

    hourly = j.get("hourly", {})
    df = pd.DataFrame({
        "time": hourly.get("time", []),
        "pm2_5": hourly.get("pm2_5", []),
    })
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df["date"] = df["time"].dt.date.astype(str)

    daily = df.groupby("date", as_index=False).agg(
        PM2_5_mean=("pm2_5", "mean"),
        PM2_5_max=("pm2_5", "max"),
    )
    return daily


def fetch_google_trends_daily(keyword: str, geo: str, start: str, end: str, sleep_s: float = 1.0) -> pd.DataFrame:
    """
    Fetch daily interest over time for keyword between start and end inclusive.
    """
    timeframe = f"{start} {end}"
    pytrends = TrendReq(hl="en-US", tz=360)
    pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)

    iot = pytrends.interest_over_time()
    if iot is None or iot.empty:
        return pd.DataFrame(columns=["date", "trends_value"])

    out = iot.reset_index().rename(columns={keyword: "trends_value"})
    if "isPartial" in out.columns:
        out = out.drop(columns=["isPartial"])

    out["date"] = pd.to_datetime(out["date"]).dt.date.astype(str)

    time.sleep(sleep_s)
    return out[["date", "trends_value"]]


def add_calendar_cols(df: pd.DataFrame) -> pd.DataFrame:
    dts = pd.to_datetime(df["date"])
    df["day_of_week"] = dts.dt.day_name()
    df["month"] = dts.dt.month
    # crude season mapping (Northern Hemisphere)
    def season(m):
        if m in (12, 1, 2): return "winter"
        if m in (3, 4, 5): return "spring"
        if m in (6, 7, 8): return "summer"
        return "fall"
    df["season"] = df["month"].apply(season)
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--days", type=int, default=300, help="How many past days to fetch (inclusive of today). Default 300.")
    parser.add_argument("--geo", default="US", help="Google Trends geo, e.g. 'US' or 'US-CA-807' (SF DMA).")
    parser.add_argument("--keyword", default="allergy")
    parser.add_argument("--flare-percentile", type=float, default=75.0, help="Label flare_day=1 for days with trends >= this percentile (0-100). Default 75 = top 25%% of days. Ignored if --threshold is set.")
    parser.add_argument("--threshold", type=int, default=None, help="Optional fixed trends value (0-100); if set, overrides --flare-percentile.")
    parser.add_argument("--out", default="dataset_two_weeks.csv")
    args = parser.parse_args()

    end_d = date.today()
    start_d = end_d - timedelta(days=args.days - 1)

    start = start_d.isoformat()
    end = end_d.isoformat()

    # Fetch env data
    weather_daily = fetch_open_meteo_weather(args.lat, args.lon, start, end)
    air_daily = fetch_open_meteo_air_quality(args.lat, args.lon, start, end)

    env = weather_daily.merge(air_daily, on="date", how="outer").sort_values("date")

    # Optional: simple AQI-ish placeholder (real AQI calc is nonlinear; keep separate if you want)
    # Here we just keep PM2.5 stats and let the model learn.
    env["latitude"] = args.lat
    env["longitude"] = args.lon
    env["locationid"] = f"{args.lat:.2f}-{args.lon:.2f}"
    env["zip_code"] = None

    env = add_calendar_cols(env)

    # Fetch trends
    trends = fetch_google_trends_daily(args.keyword, args.geo, start, end)
    if trends.empty:
        raise RuntimeError("No Google Trends data returned. Try different geo/keyword/date range.")

    # Join and label
    ds = env.merge(trends, on="date", how="left")
    ds["trends_value"] = ds["trends_value"].ffill().bfill()
    if args.threshold is not None:
        flare_thresh = float(args.threshold)
        ds["flare_day"] = (ds["trends_value"] >= flare_thresh).astype(int)
    else:
        flare_thresh = float(ds["trends_value"].quantile(args.flare_percentile / 100.0))
        ds["flare_day"] = (ds["trends_value"] >= flare_thresh).astype(int)
    # Risk 1-5: quintiles of trends (1=lowest risk, 5=highest)
    ds["risk"] = pd.qcut(ds["trends_value"], q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    ds = ds.rename(columns={"trends_value": f"google_trends_{args.keyword.replace(' ', '_')}"})

    # Match your example column naming (optional)
    # env already uses PM2_5_mean / PM2_5_max
    # If you want AQI, pollen, holiday_flag you can add later.
    ds["AQI"] = None
    ds["pollen_tree"] = None
    ds["pollen_grass"] = None
    ds["pollen_weed"] = None
    ds["holiday_flag"] = False

    # Reorder (nice-to-have)
    cols = [
        "locationid","latitude","longitude","zip_code","date",
        "PM2_5_mean","PM2_5_max","AQI",
        "temp_min","temp_max","humidity","wind","pressure","rain",
        "pollen_tree","pollen_grass","pollen_weed",
        "day_of_week","month","season","holiday_flag",
        f"google_trends_{args.keyword.replace(' ', '_')}",
        "flare_day",
        "risk",
    ]
    # Keep any that are missing in case APIs change
    cols = [c for c in cols if c in ds.columns] + [c for c in ds.columns if c not in cols]
    ds = ds[cols]

    ds.to_csv(args.out, index=False)
    print(f"Wrote {len(ds)} rows to {args.out}")
    n_flare = int(ds["flare_day"].sum())
    if args.threshold is not None:
        print(f"Flare days (trends >= {args.threshold}): {n_flare} / {len(ds)}")
    else:
        print(f"Flare days (top {100 - args.flare_percentile:.0f}%, threshold >= {flare_thresh:.1f}): {n_flare} / {len(ds)}")
    print(f"Risk 1-5 distribution: {dict(ds['risk'].value_counts().sort_index())}")


if __name__ == "__main__":
    main()