"""Download one day of adsb.lol history and keep points inside the study box."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from survey.constants import BBOX_PAD_DEG, CORNERS_LONLAT
from survey.traces import iter_trace_blobs, parse_trace

ROOT = Path(__file__).resolve().parents[2]
ARCHIVES = ROOT / "data" / "archives"
RAW = ROOT / "data" / "raw"

SCHEMA = pa.schema(
    [
        ("date", pa.string()),
        ("feed", pa.string()),
        ("icao", pa.string()),
        ("ts", pa.float64()),
        ("lat", pa.float64()),
        ("lon", pa.float64()),
        ("alt_baro", pa.float32()),
        ("alt_geom", pa.float32()),
        ("on_ground", pa.bool_()),
        ("source", pa.string()),
        ("category", pa.string()),
        ("type_code", pa.string()),
        ("db_flags", pa.int16()),
        ("gs", pa.float32()),
    ]
)


def study_bbox() -> tuple[float, float, float, float]:
    lons = [c[0] for c in CORNERS_LONLAT]
    lats = [c[1] for c in CORNERS_LONLAT]
    return (
        min(lons) - BBOX_PAD_DEG,
        min(lats) - BBOX_PAD_DEG,
        max(lons) + BBOX_PAD_DEG,
        max(lats) + BBOX_PAD_DEG,
    )


def release_names(date: str, kind: str) -> tuple[str, list[str]]:
    tag = f"v{date.replace('-', '.')}-planes-readsb-{kind}-0"
    if kind == "mlatonly":
        files = [f"{tag}.tar"]
    else:
        files = [f"{tag}.tar.aa", f"{tag}.tar.ab"]
    return tag, files


def ensure_archive(date: str, kind: str) -> list[Path]:
    tag, files = release_names(date, kind)
    ARCHIVES.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in files:
        path = ARCHIVES / name
        url = f"https://github.com/adsblol/globe_history_2026/releases/download/{tag}/{name}"
        if not path.exists() or path.stat().st_size < 1_000_000:
            print(f"download {name}")
            subprocess.run(
                ["curl", "-fL", "--retry", "3", "-C", "-", "-o", str(path), url],
                check=True,
            )
        paths.append(path)
    return paths


def _flush(writer, buffer: list[dict]):
    if not buffer:
        return writer
    table = pa.Table.from_pylist(buffer, schema=SCHEMA)
    if writer is None:
        raise RuntimeError("writer missing")
    writer.write_table(table)
    buffer.clear()
    return writer


def extract_day(date: str, kind: str, bbox: tuple[float, float, float, float]) -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    out = RAW / f"{date}-{kind}.parquet"
    if out.exists() and out.stat().st_size > 0:
        print(f"have {out.name}")
        return -1
    paths = ensure_archive(date, kind)
    part = out.with_suffix(".parquet.partial")
    writer = pq.ParquetWriter(part, SCHEMA, compression="zstd")
    buffer: list[dict] = []
    kept = 0
    files = 0
    errors = 0
    feed = "prod" if kind == "prod" else "mlatonly"
    try:
        for _name, blob in iter_trace_blobs([str(p) for p in paths]):
            files += 1
            try:
                rows = parse_trace(blob, feed, bbox)
            except Exception:
                errors += 1
                continue
            if not rows:
                continue
            for row in rows:
                row["date"] = date
                buffer.append(row)
            kept += len(rows)
            if len(buffer) >= 200_000:
                _flush(writer, buffer)
            if files % 5000 == 0:
                print(f"  {date} {kind} files {files} points {kept} errors {errors}")
        _flush(writer, buffer)
    finally:
        writer.close()
    if kept == 0:
        part.unlink(missing_ok=True)
        empty = pa.Table.from_pylist([], schema=SCHEMA)
        pq.write_table(empty, out)
        print(f"no study-box points in {date} {kind} ({files} files). Wrote an empty table.")
    else:
        part.replace(out)
        print(f"wrote {out.name} files {files} points {kept} errors {errors}")
    for path in paths:
        path.unlink(missing_ok=True)
    return kept


def extract_dates(dates: list[str]) -> None:
    box = study_bbox()
    for date in dates:
        extract_day(date, "prod", box)
        extract_day(date, "mlatonly", box)
