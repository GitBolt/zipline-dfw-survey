"""How low the feed can hear: by map cell, and checked against airports.

A cell only shows that the feed heard something low there. It cannot tell a
quiet sky from a deaf receiver. Airports can: aircraft there are known to go
all the way to the ground, so the height at which the feed last hears them is a
direct reading of its floor at that spot.
"""

from __future__ import annotations

import math

import numpy as np
import polars as pl
from shapely import STRtree, distance, points

from survey.constants import (
    CRUISE_HI_FT,
    LOW_HI_FT,
    MIN_SUPPORT,
    MIN_VISITS,
    NM_TO_M,
    VISIT_BELOW_FT,
    VISIT_BREAK_S,
    VISIT_GROUND_FT,
    VISIT_RADIUS_NM,
)
from survey.geometry import TO_ALBERS
from survey.names import nice_name

TIERS = ("cruise", "low", "higher", "none")


def cell_reception(df: pl.DataFrame, cell_ids: list[str]) -> tuple[dict, dict]:
    """Tier per cell from the lowest heights at which different aircraft were heard."""
    airborne = df.filter(
        pl.col("in_area") & ~pl.col("on_ground") & pl.col("agl").is_not_null() & (pl.col("h3") != "")
    )
    per = airborne.group_by(["h3", "icao"]).agg(pl.col("agl").min().alias("mn"))
    stats = per.group_by("h3").agg(
        pl.len().alias("n"),
        (pl.col("mn") < CRUISE_HI_FT).sum().alias("n_cruise"),
        (pl.col("mn") < LOW_HI_FT).sum().alias("n_low"),
        pl.col("mn").sort().get(MIN_SUPPORT - 1, null_on_oob=True).alias("lowest"),
    )
    found = {row[0]: row[1:] for row in stats.iter_rows()}
    records = {}
    counts = dict.fromkeys(TIERS, 0)
    for cell in cell_ids:
        n, n_cruise, n_low, lowest = found.get(cell, (0, 0, 0, None))
        if n_cruise >= MIN_SUPPORT:
            tier = "cruise"
        elif n_low >= MIN_SUPPORT:
            tier = "low"
        elif n > 0:
            tier = "higher"
        else:
            tier = "none"
        counts[tier] += 1
        records[cell] = {
            "tier": tier,
            "lowest_ft": None if lowest is None else max(0.0, float(lowest)),
            "aircraft": int(n),
        }
    total = len(cell_ids) or 1
    summary = {
        "cells": len(cell_ids),
        "min_support": MIN_SUPPORT,
        "tiers": counts,
        "heard_cruise_share": counts["cruise"] / total,
        "heard_low_share": (counts["cruise"] + counts["low"]) / total,
        "not_shown_share": (counts["higher"] + counts["none"]) / total,
    }
    return summary, records


def _bearing(lat0: float, lon0: float, lat1: float, lon1: float) -> float:
    p0, p1 = math.radians(lat0), math.radians(lat1)
    dl = math.radians(lon1 - lon0)
    y = math.sin(dl) * math.cos(p1)
    x = math.cos(p0) * math.sin(p1) - math.sin(p0) * math.cos(p1) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def compass(bearing: float) -> str:
    names = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return names[int((bearing + 22.5) // 45) % 8]


def airport_reception(df: pl.DataFrame, airports: list[dict], ends: list[dict], hub: tuple[float, float]) -> dict:
    """Lowest height at which arriving and departing aircraft were heard, per airport.

    `airports` are GeoJSON features, `ends` are runway ends with an `id`. `hub`
    is (lon, lat) of the reference point distances are measured from.
    """
    index = {f["properties"]["id"]: f for f in airports if f["properties"].get("type") != "H"}
    ends = [e for e in ends if e["id"] in index]
    surveyed = {e["id"] for e in ends}
    for ident, feature in index.items():
        if ident not in surveyed:
            lon, lat = feature["geometry"]["coordinates"]
            ends.append({"id": ident, "lon": lon, "lat": lat})
    if not ends:
        return {"checked": 0, "table": [], "by_distance": []}
    ids = sorted({e["id"] for e in ends})
    code = {name: i for i, name in enumerate(ids)}
    end_xy = np.array(TO_ALBERS.transform([e["lon"] for e in ends], [e["lat"] for e in ends])).T
    end_pts = points(end_xy[:, 0], end_xy[:, 1])
    end_code = np.array([code[e["id"]] for e in ends])
    tree = STRtree(end_pts)
    near = df.filter(pl.col("on_ground") | (pl.col("agl").is_not_null() & (pl.col("agl") < 1500.0)))
    if near.is_empty():
        return {"checked": 0, "table": [], "by_distance": []}
    px, py = TO_ALBERS.transform(near["lon"].to_numpy(), near["lat"].to_numpy())
    pts = points(np.asarray(px), np.asarray(py))
    nearest = np.asarray(tree.nearest(pts))
    dist = np.asarray(distance(pts, end_pts[nearest]))
    inside = dist <= VISIT_RADIUS_NM * NM_TO_M
    height = np.where(near["on_ground"].to_numpy(), 0.0, np.maximum(near["agl"].fill_null(0.0).to_numpy(), 0.0))
    gap = near["gap"].to_numpy()
    prev = near["prev_gap"].to_numpy()
    broke = (
        near["on_ground"].to_numpy()
        | ~np.isfinite(gap)
        | (gap > VISIT_BREAK_S)
        | ~np.isfinite(prev)
        | (prev > VISIT_BREAK_S)
    )
    frame = pl.DataFrame(
        {
            "apt": end_code[nearest][inside],
            "icao": near["icao"].to_numpy()[inside],
            "day": near["local_date"].to_numpy()[inside],
            "h": height[inside],
            "broke": broke[inside],
        }
    )
    visits = (
        frame.group_by(["apt", "icao", "day"])
        .agg(pl.col("h").min().alias("mn"), pl.col("broke").any().alias("terminal"))
        .filter(pl.col("terminal") & (pl.col("mn") < VISIT_BELOW_FT))
    )
    per = visits.group_by("apt").agg(
        pl.len().alias("n"),
        pl.col("mn").median().alias("median"),
        (pl.col("mn") <= VISIT_GROUND_FT).mean().alias("to_ground"),
    )
    table = []
    for apt, n, median, to_ground in per.iter_rows():
        if n < MIN_VISITS:
            continue
        feature = index[ids[int(apt)]]
        lon, lat = feature["geometry"]["coordinates"]
        hx, hy = TO_ALBERS.transform(hub[0], hub[1])
        ax, ay = TO_ALBERS.transform(lon, lat)
        props = feature["properties"]
        table.append(
            {
                "id": props["id"],
                "name": nice_name(props["name"]),
                "use": props["use"],
                "lon": round(lon, 5),
                "lat": round(lat, 5),
                "visits": int(n),
                "median_lowest_ft": float(median),
                "to_ground_share": float(to_ground),
                "hub_nm": float(math.hypot(ax - hx, ay - hy) / NM_TO_M),
            }
        )
    table.sort(key=lambda row: -row["visits"])
    bands = []
    for lo, hi in ((0, 10), (10, 20), (20, 30), (30, 45), (45, 70)):
        rows = [r for r in table if lo <= r["hub_nm"] < hi]
        if not rows:
            continue
        weights = sum(r["visits"] for r in rows)
        bands.append(
            {
                "lo_nm": lo,
                "hi_nm": hi,
                "airports": len(rows),
                "visits": weights,
                "median_of_medians_ft": float(np.median([r["median_lowest_ft"] for r in rows])),
                "to_ground_share": sum(r["to_ground_share"] * r["visits"] for r in rows) / weights,
            }
        )
    tracked = [r for r in table if r["to_ground_share"] >= 0.5]
    return {
        "checked": len(table),
        "tracked_to_ground": len(tracked),
        "min_visits": MIN_VISITS,
        "radius_nm": VISIT_RADIUS_NM,
        "ground_ft": VISIT_GROUND_FT,
        "table": table,
        "by_distance": bands,
    }
