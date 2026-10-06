"""Reproduce the survey from public sources."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import polars as pl

from survey.constants import (
    CRUISE_FT,
    CRUISE_HI_FT,
    CRUISE_LO_FT,
    ENROUTE_CEILING_FT,
    GAP_CAP_S,
    H3_RES,
    HELIPORT_BUFFER_NM,
    LONGITUDE_CORRECTION,
    LOW_HI_FT,
    LOW_LO_FT,
    REPLAY_DATE,
    RUNWAY_BUFFER_NM,
    SITE_RADIUS_MI,
    STUDY_DATES,
    TIMEZONE,
)
from survey.export_web import update_readme, write_findings, write_layers, write_replay
from survey.fetch_layers import main as fetch_layers
from survey.fetch_tracks import extract_dates
from survey.geometry import area_check
from survey.metrics import CLASSES, LINKS, compute
from survey.prepare import load_raw, prepare
from survey.terrain import Terrain
from survey.zones import build_masks

ROOT = Path(__file__).resolve().parents[2]


def _clean(value):
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items() if k != "masks"}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return round(value, 6)
    if hasattr(value, "item"):
        return _clean(value.item())
    return value


def _features(path: Path) -> list[dict]:
    return json.loads(path.read_text())["features"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dates", nargs="*", default=STUDY_DATES)
    parser.add_argument("--from-raw", action="store_true", help="skip downloads; use data/raw")
    parser.add_argument("--from-prepared", action="store_true", help="skip height and zones; use data/agl")
    parser.add_argument("--out", type=Path, default=ROOT / "web" / "public" / "data")
    args = parser.parse_args()
    dates = args.dates
    layers = ROOT / "data" / "layers"
    cache = ROOT / "data" / "agl" / "prepared.parquet"
    cal_cache = cache.with_suffix(".calibration.json")
    offline = args.from_raw or args.from_prepared
    if not offline and (not (layers / "class_airspace.geojson").exists() or not (layers / "geoid18.json").exists()):
        fetch_layers()
    if not offline:
        extract_dates(dates)
    terrain = Terrain(ROOT / "data" / "terrain")
    try:
        if args.from_prepared and cache.exists():
            prepared = pl.read_parquet(cache)
            calibration = json.loads(cal_cache.read_text())
            areas = {"masks": build_masks(layers, terrain)}
        else:
            print("loading")
            frame = load_raw(ROOT / "data" / "raw", dates)
            prepared, calibration, areas = prepare(frame, layers, terrain)
            calibration = _clean(calibration)
            cache.parent.mkdir(parents=True, exist_ok=True)
            prepared.write_parquet(cache, compression="zstd")
            cal_cache.write_text(json.dumps(calibration))
    finally:
        terrain.close()
    print(f"prepared {prepared.height} points")
    facilities = {
        "airports": _features(layers / "airports.geojson"),
        "heliports": _features(layers / "heliports.geojson"),
        "runway_ends": json.loads((layers / "runway_ends.json").read_text()),
    }
    findings, cells = compute(prepared, areas, dates, facilities)
    findings = _clean(findings)
    replay_day = REPLAY_DATE
    findings["study"] = {
        "name": "DFW Low-Altitude Surveillance Survey",
        "window": [dates[0], dates[-1]],
        "timezone": TIMEZONE,
        "area": _clean(area_check(areas["masks"]["area"])),
        "longitude_correction": LONGITUDE_CORRECTION,
        "instrument": "adsb.lol readsb archives, production feed plus mlat-only feed",
        "replay_date": replay_day,
        "low_band_ft": [LOW_LO_FT, LOW_HI_FT],
        "cruise_band_ft": [CRUISE_LO_FT, CRUISE_HI_FT],
        "cruise_ft": CRUISE_FT,
        "enroute_ceiling_ft": ENROUTE_CEILING_FT,
        "runway_buffer_nm": RUNWAY_BUFFER_NM,
        "heliport_buffer_nm": HELIPORT_BUFFER_NM,
        "site_radius_mi": SITE_RADIUS_MI,
        "gap_cap_s": GAP_CAP_S,
        "h3_resolution": H3_RES,
        "classes": CLASSES,
        "links": LINKS,
    }
    findings["calibration"] = calibration
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    write_findings(findings, out / "findings.json")
    (out / "cells.json").write_text(json.dumps(cells, separators=(",", ":")))
    write_layers(areas["masks"], layers, out / "layers.geojson", findings["q2"]["airports"])
    replay_info = write_replay(prepared, out / "replay.json", replay_day)
    if out == ROOT / "web" / "public" / "data":
        update_readme(ROOT / "README.md", findings)
        for name in ("METHODS.md", "LIMITS.md"):
            shutil.copyfile(ROOT / name, ROOT / "web" / "public" / name)
    for key in ("q1", "q3", "q5"):
        print(key, json.dumps({k: v for k, v in findings[key].items() if not isinstance(v, (dict, list))}))
    print("q2", {k: v for k, v in findings["q2"].items() if k != "airports"}, {k: v for k, v in findings["q2"]["airports"].items() if k not in ("table",)})
    print("replay", replay_info)
    print("thin hours", len(findings["health"]["thin_hours"]))


if __name__ == "__main__":
    main()
