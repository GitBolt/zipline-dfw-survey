"""How many hours of each kind the study window holds, and whether the feed was up."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import polars as pl

from survey.constants import TIMEZONE


def window_hours(dates: list[str]) -> dict:
    """Count the window's hours by local hour of day and by weekday or weekend.

    Archive days are UTC, so the first and last local days are partial. Rates
    divide by the hours actually covered, not by a count of calendar days.
    """
    zone = ZoneInfo(TIMEZONE)
    by_hour = [0] * 24
    weekday = 0
    weekend = 0
    for date in dates:
        start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        for step in range(24):
            local = (start + timedelta(hours=step)).astimezone(zone)
            by_hour[local.hour] += 1
            if local.weekday() < 5:
                weekday += 1
            else:
                weekend += 1
    first = datetime.strptime(dates[0], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    last = datetime.strptime(dates[-1], "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
    return {
        "utc_days": list(dates),
        "hours": 24 * len(dates),
        "by_hour": by_hour,
        "weekday_hours": weekday,
        "weekend_hours": weekend,
        "local_start": first.astimezone(zone).strftime("%Y-%m-%d %H:%M"),
        "local_end": last.astimezone(zone).strftime("%Y-%m-%d %H:%M"),
    }


def feed_health(df: pl.DataFrame, dates: list[str]) -> dict:
    """Per-day volume, and hours in which the feed delivered little or nothing."""
    area = df.filter(pl.col("in_area"))
    days = []
    by_date = {
        row[0]: row[1:]
        for row in area.group_by("date")
        .agg(
            pl.len().alias("points"),
            pl.col("icao").n_unique().alias("aircraft"),
            pl.col("dt").sum().alias("seconds"),
            pl.col("icao").filter(pl.col("ac_class") == "large").n_unique().alias("large"),
            pl.col("icao").filter(pl.col("ac_class") == "light").n_unique().alias("light"),
        )
        .iter_rows()
    }
    for date in dates:
        points, aircraft, seconds, large, light = by_date.get(date, (0, 0, 0.0, 0, 0))
        days.append(
            {
                "date": date,
                "points": int(points),
                "aircraft": int(aircraft),
                "large_aircraft": int(large),
                "light_aircraft": int(light),
                "tracked_hours": float(seconds) / 3600.0,
            }
        )
    hourly = (
        area.with_columns((pl.col("ts") // 3600).cast(pl.Int64).alias("uh"))
        .group_by("uh")
        .agg(pl.len().alias("n"))
    )
    counts = {int(hour): int(n) for hour, n in hourly.iter_rows()}
    first = int(datetime.strptime(dates[0], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()) // 3600
    series = [counts.get(first + step, 0) for step in range(24 * len(dates))]
    thin = []
    for step, value in enumerate(series):
        same_hour = sorted(series[step % 24 :: 24])
        median = same_hour[len(same_hour) // 2]
        if median > 0 and value < 0.25 * median:
            stamp = datetime.fromtimestamp((first + step) * 3600, tz=timezone.utc)
            thin.append({"utc": stamp.strftime("%Y-%m-%d %H:00"), "points": value, "typical": median})
    return {"days": days, "thin_hours": thin, "hours_checked": len(series)}
