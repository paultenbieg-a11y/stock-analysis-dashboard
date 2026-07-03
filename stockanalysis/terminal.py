"""Terminal colour helpers, the interactive prompt, and the watchlist table."""

from __future__ import annotations

import re
import sys
from typing import Any

import numpy as np

from stockanalysis.config import DEFAULT_INTERVAL, DEFAULT_PERIOD, VALID_PERIODS
from stockanalysis.utils import safe_float

_TTY = sys.stdout.isatty()


def _a(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _TTY else text


def bold(t: str) -> str:   return _a("1", t)
def cyan(t: str) -> str:   return _a("1;36", t)
def green(t: str) -> str:  return _a("32", t)
def yellow(t: str) -> str: return _a("33", t)
def dim(t: str) -> str:    return _a("2;37", t)


def _ask(label: str, default: str = "", hint: str = "") -> str:
    parts = [f"  {cyan('▶')} {bold(label)}"]
    if default:
        parts.append(dim(f"[{default}]"))
    if hint:
        parts.append(dim(hint))
    try:
        val = input(" ".join(parts) + ": ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(0)
    return val or default


def _parse_rate(raw: str, fallback: float) -> float:
    raw = raw.strip().rstrip("%")
    try:
        v = float(raw)
        return v / 100 if v > 1 else v
    except ValueError:
        return fallback


def interactive_prompt(defaults: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    """Show a styled terminal prompt; returns (tickers, config_kwargs)."""
    w = 58
    print()
    print(_a("1;36", "  ╔" + "═" * w + "╗"))
    print(_a("1;36", "  ║") + bold("  Full Scale Stock Analysis") + " " * (w - 27) + _a("1;36", "║"))
    print(_a("1;36", "  ║") + dim("  Institutional research dashboard") + " " * (w - 35) + _a("1;36", "║"))
    print(_a("1;36", "  ╚" + "═" * w + "╝"))
    print()
    print(dim("  Ticker examples:  AAPL · MSFT · SAP.DE · 7203.T · NESN.SW"))
    print(dim("  Watchlist mode:   enter comma-separated tickers, e.g.  AAPL, MSFT, NVDA"))
    print()

    raw = _ask("Ticker(s)")
    while not raw.strip():
        print(yellow("  Ticker is required."))
        raw = _ask("Ticker(s)")
    tickers = [t.strip().upper() for t in re.split(r"[,\s]+", raw) if t.strip()]

    print()
    print(dim(f"  Periods:  {' · '.join(VALID_PERIODS)}"))
    period = _ask("History period", default=defaults.get("period", DEFAULT_PERIOD))

    print()
    peers_raw = _ask("Peers", hint="(optional, comma-separated; Enter = built-in defaults)")
    peers = tuple(
        p.strip().upper() for p in re.split(r"[,\s]+", peers_raw) if p.strip()
    ) if peers_raw.strip() else ()

    print()
    cache_raw = _ask("Cache downloads for 4 h?", default="n", hint="(y/n)")
    use_cache = cache_raw.lower() in ("y", "yes", "1", "true")

    print()
    print(dim("  " + "─" * w))
    print(dim("  Advanced DCF settings — press Enter to keep defaults"))
    print(dim("  " + "─" * w))

    rfr     = _parse_rate(_ask("Risk-free rate",  default="4.5%"), 0.045)
    mktret  = _parse_rate(_ask("Market return",   default="8.5%"), 0.085)
    tgrowth = _parse_rate(_ask("Terminal growth", default="2.5%"), 0.025)

    print()
    print(_a("1;36", "  " + "─" * w))
    print()

    kwargs = {
        "period": period,
        "interval": defaults.get("interval", DEFAULT_INTERVAL),
        "risk_free_rate": rfr,
        "market_return": mktret,
        "terminal_growth": tgrowth,
        "use_cache": use_cache,
        "benchmark_ticker": defaults.get("benchmark_ticker", "SPY"),
        "peers": peers,
    }
    return tickers, kwargs


def print_watchlist_summary(results: list[dict[str, Any]]) -> None:
    if not results:
        return
    print()
    print(_a("1;36", "  " + "═" * 72))
    print(bold("  Watchlist Summary"))
    print(_a("1;36", "  " + "═" * 72))
    hdr = f"  {'Ticker':<8} {'Price':>10} {'Mkt Cap':>9} {'P/E':>7} {'FCF Yld':>8} {'Piotroski':>10} {'Return':>8} {'Vol':>7} {'Sharpe':>7}"
    print(dim(hdr))
    print(dim("  " + "─" * 72))
    for r in results:
        p_e = r.get("pe", np.nan)
        row = (
            f"  {r['ticker']:<8}"
            f" {r.get('price','n/a'):>10}"
            f" {r.get('mkt_cap','n/a'):>9}"
            f" {f'{p_e:.1f}x' if not np.isnan(safe_float(p_e)) else 'n/a':>7}"
            f" {r.get('fcf_yield','n/a'):>8}"
            f" {r.get('piotroski','n/a'):>10}"
            f" {r.get('period_return','n/a'):>8}"
            f" {r.get('vol','n/a'):>7}"
            f" {r.get('sharpe','n/a'):>7}"
        )
        print(row)
    print()
