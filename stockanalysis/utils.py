"""Small formatting and type-coercion helpers shared across the package."""

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
import pandas as pd


def safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if value is None:
            return default
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def human_number(value: Any, decimals: int = 2) -> str:
    value = safe_float(value)
    if np.isnan(value):
        return "n/a"
    sign = "-" if value < 0 else ""
    value = abs(value)
    for threshold, suffix in [(1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if value >= threshold:
            return f"{sign}{value / threshold:.{decimals}f}{suffix}"
    return f"{sign}{value:.{decimals}f}"


def pct(value: Any, decimals: int = 2) -> str:
    value = safe_float(value)
    if np.isnan(value):
        return "n/a"
    return f"{value * 100:.{decimals}f}%"


def money(value: Any, currency: str = "USD", decimals: int = 2) -> str:
    value = safe_float(value)
    if np.isnan(value):
        return "n/a"
    if currency in {"$", "€", "£", "¥"}:
        return f"{currency}{value:,.{decimals}f}"
    return f"{currency} {value:,.{decimals}f}"


def ratio_fmt(value: Any, decimals: int = 2, suffix: str = "") -> str:
    """Format a plain ratio, or n/a."""
    value = safe_float(value)
    if np.isnan(value):
        return "n/a"
    return f"{value:.{decimals}f}{suffix}"


def flatten_columns(data: pd.DataFrame) -> pd.DataFrame:
    if isinstance(data.columns, pd.MultiIndex):
        data = data.copy()
        data.columns = [col[0] if isinstance(col, tuple) else col for col in data.columns]
    return data


def clean_currency(value: Any, fallback: str = "USD") -> str:
    try:
        if pd.isna(value):
            return fallback
    except (TypeError, ValueError):
        pass
    if value is None:
        return fallback
    text = str(value).strip().upper()
    return text if text not in {"", "NAN", "NONE"} else fallback


def same_currency(left: str, right: str) -> bool:
    return clean_currency(left, "") == clean_currency(right, "")


def latest(series: pd.Series) -> float:
    clean = series.dropna()
    return safe_float(clean.iloc[-1]) if not clean.empty else np.nan


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value)).strip() if value is not None else ""


def safe_output_filename(ticker: str) -> str:
    safe = "".join(c if c.isalnum() or c in ("-", ".", "_") else "_" for c in ticker.upper())
    return safe.strip("._") or "STOCK"
