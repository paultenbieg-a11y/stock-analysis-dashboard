"""Data acquisition from Yahoo Finance.

Everything network-facing lives here: price history, financial statements,
company profile, benchmark series, options-implied volatility, the earnings
calendar, and peer snapshots. The returned bundle contains only plain
DataFrames/dicts so it can be cached safely across yfinance versions.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: yfinance. Install with `pip install -r requirements.txt`."
    ) from exc

from stockanalysis.cache import load_from_cache, save_to_cache
from stockanalysis.config import (
    PEER_MAP,
    REQUIRED_HISTORY_COLUMNS,
    SECTOR_BENCHMARK_MAP,
    ReportConfig,
)
from stockanalysis.terminal import dim
from stockanalysis.utils import flatten_columns, safe_float


def safe_yfinance_frame(
    ticker: yf.Ticker, attr: str, label: str, warnings: list[str]
) -> pd.DataFrame:
    try:
        data = getattr(ticker, attr)
    except Exception:
        warnings.append(f"{label} was unavailable from Yahoo Finance.")
        return pd.DataFrame()
    if isinstance(data, pd.DataFrame):
        return data
    warnings.append(f"{label} returned an unexpected data shape.")
    return pd.DataFrame()


def _fetch_benchmark(
    sym: str, period: str, interval: str, ref_index: pd.DatetimeIndex
) -> pd.DataFrame:
    """Return a DataFrame with Return column aligned to ref_index, or empty."""
    try:
        raw = yf.Ticker(sym).history(
            period=period, interval=interval, auto_adjust=True
        )
        if raw.empty:
            return pd.DataFrame()
        raw = flatten_columns(raw)
        if "Close" not in raw.columns:
            return pd.DataFrame()
        out = pd.DataFrame(index=raw.index)
        out["Return"] = raw["Close"].pct_change()
        out = out.reindex(ref_index)
        return out
    except Exception:
        return pd.DataFrame()


def _fetch_implied_vol(ticker_obj: yf.Ticker, current_price: float) -> float:
    """Nearest-expiry ATM implied volatility, or nan if unavailable."""
    try:
        expiries = ticker_obj.options
        if not expiries:
            return np.nan
        today = pd.Timestamp.today()
        valid = [e for e in expiries if pd.Timestamp(e) > today + pd.Timedelta(days=7)]
        expiry = valid[0] if valid else expiries[0]
        chain = ticker_obj.option_chain(expiry)
        calls, puts = chain.calls, chain.puts
        if calls.empty or puts.empty:
            return np.nan
        call_atm = calls.iloc[(calls["strike"] - current_price).abs().argsort()[:1]]
        put_atm  = puts.iloc[(puts["strike"]  - current_price).abs().argsort()[:1]]
        iv_c = safe_float(call_atm["impliedVolatility"].iloc[0])
        iv_p = safe_float(put_atm["impliedVolatility"].iloc[0])
        return float(np.nanmean([iv_c, iv_p]))
    except Exception:
        return np.nan


def _fetch_earnings(ticker_obj: yf.Ticker) -> dict[str, Any]:
    """Next earnings date and recent estimate/actual EPS history.

    Returns {"next_date": Timestamp | None, "history": DataFrame}. The history
    frame keeps yfinance's columns ('EPS Estimate', 'Reported EPS', ...) with a
    DatetimeIndex; both fields degrade to None/empty when Yahoo has no data.
    """
    next_date: pd.Timestamp | None = None
    history = pd.DataFrame()

    try:
        cal = ticker_obj.calendar
        dates = None
        if isinstance(cal, dict):
            dates = cal.get("Earnings Date")
        elif isinstance(cal, pd.DataFrame) and not cal.empty and "Earnings Date" in cal.index:
            dates = list(cal.loc["Earnings Date"].dropna())
        if dates:
            next_date = pd.Timestamp(sorted(dates)[0])
    except Exception:
        pass

    try:
        ed = ticker_obj.get_earnings_dates(limit=12)
        if isinstance(ed, pd.DataFrame) and not ed.empty:
            history = ed
    except Exception:
        pass

    if next_date is None and not history.empty:
        try:
            idx = pd.to_datetime(history.index)
            naive = idx.tz_localize(None) if idx.tz is not None else idx
            future = naive[naive > pd.Timestamp.now()]
            if len(future):
                next_date = future.min()
        except Exception:
            pass

    return {"next_date": next_date, "history": history}


def snapshot_from_info(symbol: str, info: dict[str, Any]) -> dict[str, Any]:
    """Comparable-metrics row built from a Yahoo profile dict."""
    market_cap = safe_float(info.get("marketCap"))
    fcf        = safe_float(info.get("freeCashflow"))
    fcf_yield  = (
        fcf / market_cap
        if not np.isnan(fcf) and not np.isnan(market_cap) and market_cap > 0
        else np.nan
    )
    return {
        "symbol":           symbol,
        "name":             info.get("shortName") or info.get("longName") or symbol,
        "market_cap":       market_cap,
        "trailing_pe":      safe_float(info.get("trailingPE")),
        "forward_pe":       safe_float(info.get("forwardPE")),
        "ev_to_ebitda":     safe_float(info.get("enterpriseToEbitda")),
        "price_to_sales":   safe_float(info.get("priceToSalesTrailing12Months")),
        "gross_margin":     safe_float(info.get("grossMargins")),
        "operating_margin": safe_float(info.get("operatingMargins")),
        "net_margin":       safe_float(info.get("profitMargins")),
        "revenue_growth":   safe_float(info.get("revenueGrowth")),
        "roe":              safe_float(info.get("returnOnEquity")),
        "fcf_yield":        fcf_yield,
    }


def resolve_peers(config: ReportConfig) -> list[str]:
    """Explicit --peers wins; otherwise fall back to the built-in peer map."""
    subject = config.ticker.upper()
    peers = (
        [p.upper() for p in config.peers if p.strip()]
        if config.peers
        else PEER_MAP.get(subject, [])
    )
    seen: set[str] = set()
    out: list[str] = []
    for p in peers:
        if p != subject and p not in seen:
            out.append(p)
            seen.add(p)
    return out


def _fetch_peer_snapshots(peer_syms: list[str], warnings: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    failed: list[str] = []
    for sym in peer_syms:
        try:
            info = yf.Ticker(sym).info or {}
            if not info.get("marketCap") and not info.get("trailingPE"):
                failed.append(sym)
                continue
            rows.append(snapshot_from_info(sym, info))
        except Exception:
            failed.append(sym)
    if failed:
        warnings.append(
            f"Peer data unavailable for: {', '.join(failed)}."
        )
    return rows


def fetch_data(config: ReportConfig) -> dict[str, Any]:
    if config.use_cache:
        cached = load_from_cache(config)
        if cached is not None:
            print(dim("  (loaded from cache)"))
            return cached

    warnings: list[str] = []
    ticker = yf.Ticker(config.ticker)

    # Price history
    history = ticker.history(
        period=config.period, interval=config.interval, auto_adjust=False
    )
    history = flatten_columns(history)
    if history.empty:
        raise RuntimeError(f"No price history returned for ticker {config.ticker!r}.")
    missing = REQUIRED_HISTORY_COLUMNS - set(history.columns)
    if missing:
        raise RuntimeError(f"Price history is missing columns: {', '.join(sorted(missing))}.")
    if "Volume" not in history.columns:
        history["Volume"] = 0
        warnings.append("Volume data was unavailable.")

    # Dividend-adjusted return column for risk calculations
    if "Adj Close" in history.columns:
        history["AdjReturn"] = history["Adj Close"].pct_change()
    else:
        history["AdjReturn"] = history["Close"].pct_change()

    # Fundamental statements
    financials = {
        "income":   safe_yfinance_frame(ticker, "financials",    "Annual income statement",    warnings),
        "balance":  safe_yfinance_frame(ticker, "balance_sheet", "Annual balance sheet",       warnings),
        "cashflow": safe_yfinance_frame(ticker, "cashflow",      "Annual cash flow statement", warnings),
    }

    # Quarterly income (try two attribute names across yfinance versions)
    quarterly_income = pd.DataFrame()
    for attr in ("quarterly_financials", "quarterly_income_stmt"):
        try:
            qi = getattr(ticker, attr)
            if isinstance(qi, pd.DataFrame) and not qi.empty:
                quarterly_income = qi
                break
        except Exception:
            pass

    # Company info
    try:
        info = ticker.info or {}
    except Exception:
        info = {}
        warnings.append("Company profile data was unavailable from Yahoo Finance.")

    # Benchmark
    sector = (info.get("sector") or "").strip()
    benchmark_sym = SECTOR_BENCHMARK_MAP.get(sector, config.benchmark_ticker)
    benchmark_df = _fetch_benchmark(
        benchmark_sym, config.period, config.interval, history.index
    )
    if benchmark_df.empty:
        benchmark_sym = "SPY"
        benchmark_df = _fetch_benchmark(
            "SPY", config.period, config.interval, history.index
        )

    # Implied volatility
    current_price = safe_float(
        info.get("currentPrice") or info.get("regularMarketPrice")
    )
    impl_vol = _fetch_implied_vol(ticker, current_price) if not np.isnan(current_price) else np.nan

    # Earnings calendar and history
    earnings = _fetch_earnings(ticker)

    # Peer snapshots (profile data only — one light request per peer)
    peer_syms = resolve_peers(config)
    if peer_syms:
        print(dim(f"  fetching {len(peer_syms)} peers…"))
    peers = _fetch_peer_snapshots(peer_syms, warnings)

    data = {
        "history": history,
        "financials": financials,
        "quarterly_income": quarterly_income,
        "info": info,
        "warnings": warnings,
        "benchmark_df": benchmark_df,
        "benchmark_sym": benchmark_sym,
        "impl_vol": impl_vol,
        "earnings": earnings,
        "peers": peers,
    }

    if config.use_cache:
        save_to_cache(config, data)

    return data
