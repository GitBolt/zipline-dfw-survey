"""Busy low-altitude areas that sit outside the public-runway stand-off."""

from __future__ import annotations

import math

import h3
import polars as pl

from survey.constants import HOTSPOT_MAX, HOTSPOT_MIN_S, MIN_DISTINCT, NM_TO_M
from survey.geometry import TO_ALBERS
from survey.reception import _bearing, compass


def _components(cells: set[str]) -> list[list[str]]:
    seen: set[str] = set()
    groups = []
    for start in sorted(cells):
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        group = []
        while stack:
            cell = stack.pop()
            group.append(cell)
            for other in h3.grid_disk(cell, 1):
                if other in cells and other not in seen:
                    seen.add(other)
                    stack.append(other)
        groups.append(sorted(group))
    return groups


def _nearest(lat: float, lon: float, places: list[dict]) -> dict | None:
    if not places:
        return None
    x, y = TO_ALBERS.transform(lon, lat)
    best = None
    for place in places:
        px, py = TO_ALBERS.transform(place["lon"], place["lat"])
        d = math.hypot(px - x, py - y) / NM_TO_M
        if best is None or d < best[0]:
            best = (d, place)
    d, place = best
    return {
        "id": place["id"],
        "name": place["name"],
        "nm": float(d),
        "dir": compass(_bearing(place["lat"], place["lon"], lat, lon)),
    }


def find_hotspots(band: pl.DataFrame, window_hours: float, public: list[dict], pads: list[dict]) -> list[dict]:
    """Group adjacent busy cells and describe each group.

    `band` holds in-band points already cut to outside the public-runway
    buffer. `public` and `pads` are {id, name, lon, lat} lists used to say
    where a group is.
    """
    if band.is_empty():
        return []
    per = band.group_by("h3").agg(pl.col("dt").sum().alias("s"), pl.col("icao").n_unique().alias("n"))
    busy = set(per.filter((pl.col("s") >= HOTSPOT_MIN_S) & (pl.col("n") >= MIN_DISTINCT))["h3"].to_list())
    busy.discard("")
    if not busy:
        return []
    groups = _components(busy)
    owner = {cell: i for i, group in enumerate(groups) for cell in group}
    tagged = band.filter(pl.col("h3").is_in(list(busy))).with_columns(
        pl.col("h3").replace_strict(owner, return_dtype=pl.Int32).alias("grp")
    )
    out = []
    totals = tagged.group_by("grp").agg(pl.col("dt").sum().alias("s"), pl.col("icao").n_unique().alias("n"))
    classes = {
        (g, c): s for g, c, s in tagged.group_by(["grp", "ac_class"]).agg(pl.col("dt").sum()).iter_rows()
    }
    hours = {(g, h): s for g, h, s in tagged.group_by(["grp", "hour"]).agg(pl.col("dt").sum()).iter_rows()}
    cell_s = {row[0]: row[1] for row in per.iter_rows()}
    for grp, seconds, aircraft in totals.sort("s", descending=True).head(HOTSPOT_MAX).iter_rows():
        cells = groups[int(grp)]
        weight = sum(cell_s[c] for c in cells) or 1.0
        lat = sum(h3.cell_to_latlng(c)[0] * cell_s[c] for c in cells) / weight
        lon = sum(h3.cell_to_latlng(c)[1] * cell_s[c] for c in cells) / weight
        by_class = {c: s / 3600.0 for (g, c), s in classes.items() if g == grp and c}
        by_hour = [hours.get((grp, h), 0.0) for h in range(24)]
        best = max(range(24), key=lambda h: sum(by_hour[(h + k) % 24] for k in range(3)))
        pad = _nearest(lat, lon, pads)
        out.append(
            {
                "lat": round(lat, 4),
                "lon": round(lon, 4),
                "cells": cells,
                "hours": seconds / 3600.0,
                "minutes_per_day": seconds / 60.0 / (window_hours / 24.0),
                "aircraft": int(aircraft),
                "by_class": by_class,
                "top_class": max(by_class, key=by_class.get) if by_class else None,
                "busiest_3h_start": best,
                "busiest_3h_share": sum(by_hour[(best + k) % 24] for k in range(3)) / (seconds or 1.0),
                "nearest_public": _nearest(lat, lon, public),
                "nearest_pad": pad if pad and pad["nm"] <= 2.0 else None,
            }
        )
    return out
