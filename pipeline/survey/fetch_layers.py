"""FAA layers, terrain tiles, METARs, and a GEOID18 grid."""

from __future__ import annotations

import json
import subprocess
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import polars as pl
from shapely.geometry import LineString, Point, mapping, shape

from survey.constants import (
    BBOX_PAD_DEG,
    CORNERS_LONLAT,
    DEM_TILES,
    LONGITUDE_CORRECTION,
    METAR_STATIONS,
    STUDY_DATES,
)
from survey.geometry import as_feature, feature_collection, operating_polygon

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
LAYERS = DATA / "layers"
TERRAIN = DATA / "terrain"
NASR = DATA / "nasr"
AIRSPACE_URL = "https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/arcgis/rest/services/Class_Airspace/FeatureServer/0/query"
NASR_URL = "https://nfdc.faa.gov/webContent/28DaySub/extra/01_Oct_2026_APT_CSV.zip"
UA = "dfw-low-altitude-survey/1.0 (public measurement; educational)"


def bbox() -> tuple[float, float, float, float]:
    lons = [c[0] for c in CORNERS_LONLAT]
    lats = [c[1] for c in CORNERS_LONLAT]
    return (
        min(lons) - BBOX_PAD_DEG,
        min(lats) - BBOX_PAD_DEG,
        max(lons) + BBOX_PAD_DEG,
        max(lats) + BBOX_PAD_DEG,
    )


def _get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def ensure_dems() -> None:
    TERRAIN.mkdir(parents=True, exist_ok=True)
    for name, size in DEM_TILES.items():
        path = TERRAIN / f"USGS_1_{name}.tif"
        if path.exists() and path.stat().st_size == size:
            continue
        url = f"https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1/TIFF/current/{name}/USGS_1_{name}.tif"
        print(f"dem {name}")
        subprocess.run(["curl", "-fL", "--retry", "3", "-C", "-", "-o", str(path), url], check=True)
        if path.stat().st_size != size:
            raise RuntimeError(f"{path.name} is {path.stat().st_size} bytes, expected {size}")


def ensure_nasr() -> Path:
    NASR.mkdir(parents=True, exist_ok=True)
    zip_path = NASR / "APT_CSV.zip"
    if not zip_path.exists() or zip_path.stat().st_size < 1_000_000:
        print("nasr apt csv")
        subprocess.run(
            ["curl", "-fL", "--retry", "3", "-A", UA, "-o", str(zip_path), NASR_URL],
            check=True,
        )
    return zip_path


def fetch_airspace() -> dict:
    lon0, lat0, lon1, lat1 = bbox()
    features = []
    offset = 0
    while True:
        params = {
            "where": "1=1",
            "geometry": f"{lon0},{lat0},{lon1},{lat1}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "NAME,IDENT,ICAO_ID,TYPE_CODE,LOCAL_TYPE,CLASS,LOWER_VAL,LOWER_CODE,UPPER_VAL,UPPER_CODE,SECTOR,EXCLUSION",
            "returnGeometry": "true",
            "outSR": "4326",
            "resultOffset": str(offset),
            "resultRecordCount": "100",
            "f": "geojson",
        }
        url = AIRSPACE_URL + "?" + urllib.parse.urlencode(params)
        page = json.loads(_get(url))
        batch = page.get("features") or []
        features.extend(batch)
        print(f"airspace {len(features)}")
        if len(batch) < 100:
            break
        offset += len(batch)
    return {"type": "FeatureCollection", "features": features}


def _read_csv(zip_path: Path, name: str) -> pl.DataFrame:
    with zipfile.ZipFile(zip_path) as zf:
        return pl.read_csv(zf.read(name), infer_schema_length=10000)


def build_facilities(zip_path: Path) -> tuple[dict, dict]:
    lon0, lat0, lon1, lat1 = bbox()
    base = _read_csv(zip_path, "APT_BASE.csv").filter(
        (pl.col("LAT_DECIMAL") >= lat0)
        & (pl.col("LAT_DECIMAL") <= lat1)
        & (pl.col("LONG_DECIMAL") >= lon0)
        & (pl.col("LONG_DECIMAL") <= lon1)
    )
    ends = _read_csv(zip_path, "APT_RWY_END.csv").join(
        base.select(["SITE_NO", "FACILITY_USE_CODE", "SITE_TYPE_CODE", "ARPT_ID", "ARPT_NAME", "ELEV"]),
        on="SITE_NO",
        how="inner",
    )
    airports = []
    heliports = []
    for row in base.iter_rows(named=True):
        props = {
            "site_no": row["SITE_NO"],
            "id": row["ARPT_ID"],
            "name": row["ARPT_NAME"],
            "type": row["SITE_TYPE_CODE"],
            "use": row["FACILITY_USE_CODE"],
            "medical": row["MEDICAL_USE_FLAG"] == "Y",
            "elev_ft": row["ELEV"],
        }
        feat = as_feature(Point(row["LONG_DECIMAL"], row["LAT_DECIMAL"]), props)
        if row["SITE_TYPE_CODE"] == "H":
            heliports.append(feat)
        else:
            airports.append(feat)

    runways = []
    grouped: dict[tuple, list] = {}
    for row in ends.iter_rows(named=True):
        if row["LAT_DECIMAL"] is None or row["LONG_DECIMAL"] is None:
            continue
        grouped.setdefault((row["SITE_NO"], row["RWY_ID"]), []).append(row)
    for (site, rwy), points in grouped.items():
        coords = [(p["LONG_DECIMAL"], p["LAT_DECIMAL"]) for p in points]
        elevs = [p["RWY_END_ELEV"] for p in points if p["RWY_END_ELEV"] is not None]
        geom = LineString(coords) if len(coords) >= 2 else Point(coords[0])
        sample = points[0]
        runways.append(
            as_feature(
                geom,
                {
                    "site_no": site,
                    "rwy": rwy,
                    "id": sample["ARPT_ID"],
                    "use": sample["FACILITY_USE_CODE"],
                    "type": sample["SITE_TYPE_CODE"],
                    "elev_ft": float(np.mean(elevs)) if elevs else sample["ELEV"],
                },
            )
        )
    runway_ends = []
    for row in ends.iter_rows(named=True):
        if row["LAT_DECIMAL"] is None or row["LONG_DECIMAL"] is None or row["RWY_END_ELEV"] is None:
            continue
        runway_ends.append(
            {
                "lon": row["LONG_DECIMAL"],
                "lat": row["LAT_DECIMAL"],
                "elev_ft": float(row["RWY_END_ELEV"]),
                "use": row["FACILITY_USE_CODE"],
                "id": row["ARPT_ID"],
            }
        )
    (LAYERS / "runway_ends.json").write_text(json.dumps(runway_ends))
    return feature_collection(airports), feature_collection(heliports), feature_collection(runways)


def fetch_metar() -> list[dict]:
    start, end = STUDY_DATES[0], STUDY_DATES[-1]
    y1, m1, d1 = start.split("-")
    y2, m2, d2 = end.split("-")
    params = [
        ("data", "alti"),
        ("data", "tmpc"),
        ("year1", y1),
        ("month1", str(int(m1))),
        ("day1", str(int(d1))),
        ("year2", y2),
        ("month2", str(int(m2))),
        ("day2", str(int(d2))),
        ("tz", "Etc/UTC"),
        ("format", "onlycomma"),
        ("latlon", "yes"),
        ("missing", "M"),
        ("trace", "T"),
        ("direct", "no"),
        ("report_type", "3"),
    ]
    for station in METAR_STATIONS:
        params.append(("station", station))
    url = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?" + urllib.parse.urlencode(params)
    text = _get(url, timeout=180).decode("utf-8", "replace")
    rows = []
    lines = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    if not lines:
        return rows
    header = [h.strip() for h in lines[0].split(",")]
    for line in lines[1:]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < len(header):
            continue
        rec = dict(zip(header, parts))
        alti = rec.get("alti")
        if not alti or alti == "M":
            continue
        try:
            rows.append(
                {
                    "station": rec.get("station"),
                    "valid": rec.get("valid"),
                    "lat": float(rec["lat"]),
                    "lon": float(rec["lon"]),
                    "alti": float(alti),
                }
            )
        except (KeyError, ValueError):
            continue
    return rows


def fetch_geoid() -> dict:
    lat0, lon0, step = 32.0, -98.3, 0.2
    lats = np.round(np.arange(lat0, 33.81, step), 4)
    lons = np.round(np.arange(lon0, -95.59, step), 4)
    jobs = [(float(lat), float(lon)) for lat in lats for lon in lons]

    def one(lat: float, lon: float) -> tuple[float, float, float]:
        url = f"https://geodesy.noaa.gov/api/geoid/ght?lat={lat}&lon={lon}&model=14"
        doc = json.loads(_get(url, timeout=30))
        return lat, lon, float(doc["geoidHeight"])

    values = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(one, lat, lon) for lat, lon in jobs]
        done = 0
        for fut in as_completed(futures):
            lat, lon, height = fut.result()
            values[(lat, lon)] = height
            done += 1
            if done % 40 == 0:
                print(f"geoid {done}/{len(jobs)}")
    grid = []
    for lat in lats:
        row = []
        for lon in lons:
            row.append(values[(float(lat), float(lon))])
        grid.append(row)
    return {
        "model": "GEOID18",
        "lat0": lat0,
        "lon0": lon0,
        "step": step,
        "lats": lats.tolist(),
        "lons": lons.tolist(),
        "grid": grid,
        "sample_dfw_m": values.get((32.8, -97.0)),
    }


def write_operating_area() -> None:
    poly = operating_polygon()
    doc = feature_collection(
        [as_feature(poly, {"name": "DFW operating area", "note": LONGITUDE_CORRECTION})]
    )
    (LAYERS / "operating_area.geojson").write_text(json.dumps(doc))


def main() -> None:
    LAYERS.mkdir(parents=True, exist_ok=True)
    ensure_dems()
    write_operating_area()
    airspace_path = LAYERS / "class_airspace.geojson"
    if not airspace_path.exists():
        airspace_path.write_text(json.dumps(fetch_airspace()))
    zip_path = ensure_nasr()
    airports, heliports, runways = build_facilities(zip_path)
    (LAYERS / "airports.geojson").write_text(json.dumps(airports))
    (LAYERS / "heliports.geojson").write_text(json.dumps(heliports))
    (LAYERS / "runways.geojson").write_text(json.dumps(runways))
    print(f"airports {len(airports['features'])} heliports {len(heliports['features'])} runways {len(runways['features'])}")
    metar_path = LAYERS / "metar.json"
    if not metar_path.exists():
        rows = fetch_metar()
        metar_path.write_text(json.dumps(rows))
        print(f"metar {len(rows)}")
    geoid_path = LAYERS / "geoid18.json"
    if not geoid_path.exists():
        geoid_path.write_text(json.dumps(fetch_geoid()))
        print("geoid written")


if __name__ == "__main__":
    main()
