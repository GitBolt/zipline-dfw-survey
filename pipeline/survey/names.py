"""Readable facility names from the FAA's upper-case ones."""

from __future__ import annotations

import re

UPPER = {"DFW", "NAS", "JRB", "AHP", "TX", "USA", "II", "III", "LBJ", "UT", "HCA", "TCU", "CBS", "NBC", "KXAS", "WFAA", "MCP"}
EXPAND = {"INTL": "Intl", "MUNI": "Municipal", "RGNL": "Regional", "FLD": "Field", "NTL": "National", "EXEC": "Executive", "HOSP": "Hospital", "MEML": "Memorial", "CNTY": "County"}


def nice_name(raw: object) -> str:
    """'MCKINNEY NTL' -> 'McKinney National', keeping known initialisms upper-case."""
    words = []
    for token in re.split(r"(\s+|/|-|\()", str(raw or "").strip()):
        if not token or not token.strip() or token in "/-(":
            words.append(token)
            continue
        bare = token.rstrip(").,")
        tail = token[len(bare):]
        if bare in EXPAND:
            word = EXPAND[bare]
        elif bare in UPPER:
            word = bare
        elif bare.startswith("MC") and len(bare) > 3:
            word = "Mc" + bare[2:].capitalize()
        elif "'" in bare:
            head, _, rest = bare.partition("'")
            word = head.capitalize() + "'" + rest.lower()
        else:
            word = bare.capitalize()
        words.append(word + tail)
    return "".join(words)
