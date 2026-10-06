"""Aircraft class and surveillance-source rules."""

from __future__ import annotations

from survey.constants import (
    ADSB_SOURCES,
    ADSR_SOURCES,
    HELI_TYPES,
    MLAT_SOURCES,
    TISB_SOURCES,
)

# Priority when a point falls in more than one remainder zone.
REMAINDER_PRIORITY = ("private_runway", "hospital_pad", "other_heliport", "elsewhere")


def normalize_source(source: str | None, feed: str) -> str:
    src = (source or "").strip().lower()
    if feed == "mlatonly" and src in {"other", "mlat", "mode_s", ""}:
        return "mlat"
    return src or "unknown"


def link_class(sources: set[str]) -> str:
    """Aircraft-level picture for a receive-only dual-band ADS-B In receiver.

    ADS-R counts as a 978 MHz broadcast. A single ADS-B position anywhere in
    the study box makes the aircraft a broadcaster, including when other
    points were multilaterated.
    """
    if sources & ADSB_SOURCES:
        return "adsb_1090"
    if sources & ADSR_SOURCES:
        return "uat_or_adsr"
    if sources & MLAT_SOURCES:
        return "mlat_only"
    if sources & TISB_SOURCES:
        return "tisb_only"
    return "other"


def is_broadcast(link: str) -> bool:
    return link in {"adsb_1090", "uat_or_adsr"}


def is_miss(link: str) -> bool:
    return link in {"mlat_only", "tisb_only"}


def aircraft_class(category: str | None, type_code: str | None) -> str | None:
    """Crewed class, or None when the emitter is not a crewed aircraft."""
    cat = (category or "").upper()
    code = (type_code or "").upper()
    if cat.startswith("C") or cat == "B6":
        return None
    if cat == "A7" or (cat in {"", "A0"} and code in HELI_TYPES):
        return "rotorcraft"
    if cat == "A1":
        return "light"
    if cat == "A2":
        return "small"
    if cat in {"A3", "A4", "A5"}:
        return "large"
    if cat in {"", "A0"}:
        return "unknown"
    return "other"


def capped_dt(gap_s: float | None) -> float:
    if gap_s is None or gap_s <= 0 or gap_s >= 6 * 3600:
        return 0.0
    return float(min(gap_s, 30.0))
