"""Peer-comparison analytics: comparable table and percentile positioning."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from stockanalysis.utils import safe_float

# (key, label, format kind, direction of "richer/stronger")
PEER_METRICS: list[tuple[str, str, str, str]] = [
    ("trailing_pe",      "P/E (ttm)",   "x",   "expensive"),
    ("forward_pe",       "Fwd P/E",     "x",   "expensive"),
    ("ev_to_ebitda",     "EV/EBITDA",   "x",   "expensive"),
    ("price_to_sales",   "P/S",         "x",   "expensive"),
    ("gross_margin",     "Gross m.",    "pct", "strong"),
    ("operating_margin", "Op. m.",      "pct", "strong"),
    ("net_margin",       "Net m.",      "pct", "strong"),
    ("revenue_growth",   "Rev growth",  "pct", "strong"),
    ("roe",              "ROE",         "pct", "strong"),
    ("fcf_yield",        "FCF yield",   "pct", "cheap"),
]


def build_peer_frame(
    subject_row: dict[str, Any], peer_rows: list[dict[str, Any]]
) -> pd.DataFrame:
    """Subject first, then peers sorted by market cap descending."""
    peers = sorted(
        peer_rows,
        key=lambda r: -(safe_float(r.get("market_cap")) if not np.isnan(safe_float(r.get("market_cap"))) else 0.0),
    )
    return pd.DataFrame([subject_row] + peers)


def percentile_rank(values: list[float], subject_value: float) -> float:
    """Midpoint percentile of subject_value within values (subject included)."""
    vals = [v for v in values if not np.isnan(safe_float(v))]
    subject_value = safe_float(subject_value)
    if np.isnan(subject_value) or len(vals) < 4:
        return np.nan
    below = sum(1 for v in vals if v < subject_value)
    equal = sum(1 for v in vals if v == subject_value)
    return (below + 0.5 * equal) / len(vals)


def peer_percentiles(
    subject_row: dict[str, Any], peer_rows: list[dict[str, Any]]
) -> dict[str, float]:
    """Subject percentile per metric across the full group (subject + peers)."""
    out: dict[str, float] = {}
    group = [subject_row] + peer_rows
    for key, *_ in PEER_METRICS:
        values = [safe_float(r.get(key)) for r in group]
        out[key] = percentile_rank(values, safe_float(subject_row.get(key)))
    return out


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def positioning_text(
    subject_row: dict[str, Any], peer_rows: list[dict[str, Any]]
) -> str:
    """One-sentence relative positioning built from percentile ranks."""
    if len(peer_rows) < 3:
        return ""
    ranks = peer_percentiles(subject_row, peer_rows)
    n = len(peer_rows) + 1
    parts: list[str] = []

    val = ranks.get("ev_to_ebitda")
    if np.isnan(safe_float(val)):
        val = ranks.get("trailing_pe")
        label = "trailing P/E"
    else:
        label = "EV/EBITDA"
    if not np.isnan(safe_float(val)):
        parts.append(f"the {ordinal(round(val * 100))} percentile on {label} (higher = more expensive)")

    for key, phrase in [
        ("operating_margin", "operating margin"),
        ("revenue_growth",   "revenue growth"),
        ("fcf_yield",        "free-cash-flow yield"),
    ]:
        val = safe_float(ranks.get(key))
        if not np.isnan(val):
            parts.append(f"the {ordinal(round(val * 100))} on {phrase}")

    if not parts:
        return ""
    sym = subject_row.get("symbol", "The company")
    return f"Within its {n}-name peer group, {sym} sits at " + ", ".join(parts) + "."
