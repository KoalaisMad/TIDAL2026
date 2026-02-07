"""
Time Context: Day of week, season, holidays.
Source: Derived from date (no external API).
"""
from __future__ import annotations

from datetime import date
from typing import Any


# US federal holidays (date or (month, day)); add more as needed
US_HOLIDAYS: list[tuple[int, int] | str] = [
    (1, 1),   # New Year
    (7, 4),   # Independence
    (11, 11), # Veterans
    (12, 25), # Christmas
    # Monday-based
    (1, -1),  # MLK 3rd Mon Jan
    (2, -1),  # Presidents 3rd Mon Feb
    (9, -1),  # Labor 1st Mon Sep
    (10, -1), # Columbus 2nd Mon Oct
    (11, -1), # Thanksgiving 4th Thu Nov
]


def _nth_weekday_in_month(year: int, month: int, weekday: int, n: int) -> date:
    """n=1 first, n=2 second, ... weekday 0=Mon, 6=Sun."""
    first = date(year, month, 1)
    first_wd = first.weekday()
    # days until first occurrence of weekday
    days_until = (weekday - first_wd + 7) % 7
    if n == 1:
        day = 1 + days_until
    else:
        day = 1 + days_until + 7 * (n - 1)
    return date(year, month, day)


def _us_holidays_for_year(year: int) -> set[date]:
    out = set()
    for item in US_HOLIDAYS:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        month, day = item
        if day > 0:
            out.add(date(year, month, day))
        else:
            if month == 1:
                out.add(_nth_weekday_in_month(year, 1, 0, 3))   # MLK 3rd Mon
            elif month == 2:
                out.add(_nth_weekday_in_month(year, 2, 0, 3))   # Presidents 3rd Mon
            elif month == 9:
                out.add(_nth_weekday_in_month(year, 9, 0, 1))   # Labor 1st Mon
            elif month == 10:
                out.add(_nth_weekday_in_month(year, 10, 0, 2))  # Columbus 2nd Mon
            elif month == 11:
                out.add(_nth_weekday_in_month(year, 11, 3, 4))   # Thanksgiving 4th Thu
    return out


def pull_time_context(target_date: date) -> dict[str, Any]:
    """
    Derive day of week, season, and whether the date is a US federal holiday.
    """
    day_of_week = target_date.strftime("%A")  # Monday, Tuesday, ...
    day_of_week_num = target_date.weekday()   # 0=Mon, 6=Sun

    month = target_date.month
    if month in (12, 1, 2):
        season = "winter"
    elif month in (3, 4, 5):
        season = "spring"
    elif month in (6, 7, 8):
        season = "summer"
    else:
        season = "autumn"

    holidays = _us_holidays_for_year(target_date.year)
    is_holiday = target_date in holidays

    return {
        "day_of_week": day_of_week,
        "day_of_week_num": day_of_week_num,
        "season": season,
        "is_holiday": is_holiday,
        "source": "Derived",
        "error": None,
        "raw": None,
    }
