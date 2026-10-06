"""Height above ground, and the choice between ellipsoid and MSL geometric altitude."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

FT_PER_M = 3.280839895


def agl_from_geometric(geom_ft: np.ndarray, terrain_m: np.ndarray, geoid_n_m: np.ndarray, as_msl: bool) -> np.ndarray:
    terrain_ft = terrain_m * FT_PER_M
    if as_msl:
        return geom_ft - terrain_ft
    # N is the geoid undulation: orthometric = HAE - N. CONUS N is negative.
    return geom_ft - geoid_n_m * FT_PER_M - terrain_ft


def agl_from_barometric(baro_ft: np.ndarray, terrain_m: np.ndarray, altimeter_inhg: np.ndarray) -> np.ndarray:
    indicated = baro_ft + (altimeter_inhg - 29.92) * 1000.0
    return indicated - terrain_m * FT_PER_M


def bilinear(grid: np.ndarray, lat0: float, lon0: float, step: float, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    row = (lat - lat0) / step
    col = (lon - lon0) / step
    r0 = np.floor(row).astype(np.int32)
    c0 = np.floor(col).astype(np.int32)
    r0 = np.clip(r0, 0, grid.shape[0] - 2)
    c0 = np.clip(c0, 0, grid.shape[1] - 2)
    dr = np.clip(row - r0, 0, 1)
    dc = np.clip(col - c0, 0, 1)
    g00 = grid[r0, c0]
    g01 = grid[r0, c0 + 1]
    g10 = grid[r0 + 1, c0]
    g11 = grid[r0 + 1, c0 + 1]
    return (
        g00 * (1 - dr) * (1 - dc)
        + g01 * (1 - dr) * dc
        + g10 * dr * (1 - dc)
        + g11 * dr * dc
    )


def load_geoid(path: Path) -> dict:
    return json.loads(path.read_text())


def sample_geoid(grid_doc: dict, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    grid = np.asarray(grid_doc["grid"], dtype=np.float64)
    return bilinear(grid, grid_doc["lat0"], grid_doc["lon0"], grid_doc["step"], lat, lon)


def summarize_residuals(residual_ft: np.ndarray) -> dict:
    residual_ft = residual_ft[np.isfinite(residual_ft)]
    if residual_ft.size == 0:
        return {"n": 0, "mae_ft": None, "p50_ft": None, "p90_abs_ft": None}
    abs_r = np.abs(residual_ft)
    return {
        "n": int(residual_ft.size),
        "mae_ft": float(np.mean(abs_r)),
        "p50_ft": float(np.median(residual_ft)),
        "p90_abs_ft": float(np.quantile(abs_r, 0.9)),
    }


def choose_basis(residual_hae: np.ndarray, residual_msl: np.ndarray) -> str:
    hae = summarize_residuals(residual_hae)
    msl = summarize_residuals(residual_msl)
    if not hae["n"] and not msl["n"]:
        return "hae"
    if not msl["n"]:
        return "hae"
    if not hae["n"]:
        return "msl"
    if msl["mae_ft"] + 25.0 < hae["mae_ft"]:
        return "msl"
    return "hae"


def residual_histogram(residual_ft: np.ndarray, bin_ft: float = 25.0, span: float = 250.0) -> list[dict]:
    residual_ft = residual_ft[np.isfinite(residual_ft)]
    edges = np.arange(-span, span + bin_ft, bin_ft)
    if residual_ft.size == 0:
        return [{"lo_ft": float(edges[i]), "n": 0} for i in range(len(edges) - 1)]
    counts, _ = np.histogram(np.clip(residual_ft, edges[0], edges[-1]), bins=edges)
    return [{"lo_ft": float(edges[i]), "n": int(counts[i])} for i in range(len(counts))]
