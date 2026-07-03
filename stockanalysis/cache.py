"""Optional on-disk cache for downloaded data (4-hour TTL)."""

from __future__ import annotations

import hashlib
import pickle
import time
from pathlib import Path

from stockanalysis.config import CACHE_DIR, CACHE_TTL_SECONDS, ReportConfig


def _cache_path(config: ReportConfig) -> Path:
    peers = ",".join(sorted(config.peers))
    key = hashlib.md5(
        f"{config.ticker}|{config.period}|{config.interval}|{peers}".encode()
    ).hexdigest()
    return CACHE_DIR / f"{key}.pkl"


def load_from_cache(config: ReportConfig) -> dict | None:
    path = _cache_path(config)
    if path.exists() and (time.time() - path.stat().st_mtime) < CACHE_TTL_SECONDS:
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    return None


def save_to_cache(config: ReportConfig, data: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    try:
        with open(_cache_path(config), "wb") as f:
            pickle.dump(data, f)
    except Exception:
        pass
