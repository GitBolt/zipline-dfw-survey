"""Operating-area geometry and small spatial helpers."""

from __future__ import annotations

from pyproj import Geod, Transformer
from shapely.geometry import Polygon, mapping, shape
from shapely.ops import transform, unary_union

from survey.constants import CORNERS_LONLAT, STATED_AREA_SQ_MI

GEOD = Geod(ellps="WGS84")
TO_ALBERS = Transformer.from_crs(4326, 5070, always_xy=True)
FROM_ALBERS = Transformer.from_crs(5070, 4326, always_xy=True)
SQ_M_PER_SQ_MI = 2_589_988.110336


def operating_polygon() -> Polygon:
    ring = list(CORNERS_LONLAT) + [CORNERS_LONLAT[0]]
    poly = Polygon(ring)
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly


def geodesic_area_sq_mi(poly: Polygon) -> float:
    lon, lat = poly.exterior.coords.xy
    area_m, _ = GEOD.polygon_area_perimeter(lon, lat)
    return abs(area_m) / SQ_M_PER_SQ_MI


def to_albers(geom):
    return transform(TO_ALBERS.transform, geom)


def to_wgs84(geom):
    return transform(FROM_ALBERS.transform, geom)


def buffer_nm(geom, nm: float):
    meters = nm * 1852.0
    return to_wgs84(to_albers(geom).buffer(meters))


def area_sq_mi(geom) -> float:
    if geom is None or geom.is_empty:
        return 0.0
    projected = to_albers(geom)
    return projected.area / SQ_M_PER_SQ_MI


def as_feature(geom, properties: dict | None = None) -> dict:
    return {
        "type": "Feature",
        "properties": properties or {},
        "geometry": mapping(geom),
    }


def feature_collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def load_geom(feature: dict):
    return shape(feature["geometry"])


def union_all(geoms: list):
    geoms = [g for g in geoms if g is not None and not g.is_empty]
    if not geoms:
        return Polygon()
    return unary_union(geoms)


def area_check(poly: Polygon | None = None) -> dict:
    poly = poly or operating_polygon()
    computed = geodesic_area_sq_mi(poly)
    delta = computed - STATED_AREA_SQ_MI
    pct = delta / STATED_AREA_SQ_MI
    return {
        "computed_sq_mi": computed,
        "stated_sq_mi": STATED_AREA_SQ_MI,
        "delta_sq_mi": delta,
        "delta_pct": pct,
        "within_half_percent": abs(pct) <= 0.005,
    }
