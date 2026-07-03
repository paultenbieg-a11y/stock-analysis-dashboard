"""Command-line interface and per-ticker run orchestration."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import numpy as np

from stockanalysis.config import (
    DEFAULT_INTERVAL,
    DEFAULT_PERIOD,
    DEFAULT_TICKER,
    ReportConfig,
)
from stockanalysis.data import fetch_data
from stockanalysis.fundamentals import calculate_fundamentals
from stockanalysis.indicators import add_technical_indicators
from stockanalysis.report import build_report
from stockanalysis.risk import risk_metrics
from stockanalysis.terminal import (
    bold,
    cyan,
    green,
    interactive_prompt,
    print_watchlist_summary,
    yellow,
)
from stockanalysis.utils import (
    clean_currency,
    human_number,
    latest,
    money,
    pct,
    safe_float,
)


def parse_args() -> tuple[list[str], dict[str, Any], bool]:
    """Returns (tickers, config_kwargs, use_interactive)."""
    parser = argparse.ArgumentParser(
        description="Full scale stock analysis — generates an interactive HTML report."
    )
    parser.add_argument("--ticker",         default=None, help="Single ticker, e.g. AAPL")
    parser.add_argument("--watchlist",      nargs="+",    help="Multiple tickers, e.g. AAPL MSFT NVDA")
    parser.add_argument("--period",         default=DEFAULT_PERIOD)
    parser.add_argument("--interval",       default=DEFAULT_INTERVAL)
    parser.add_argument("--risk-free-rate", type=float, default=0.045)
    parser.add_argument("--market-return",  type=float, default=0.085)
    parser.add_argument("--terminal-growth",type=float, default=0.025)
    parser.add_argument("--benchmark",      default="SPY", help="Benchmark ticker (default SPY)")
    parser.add_argument("--peers",          nargs="+",
                        help="Peer tickers for the comparison section (default: built-in peer map)")
    parser.add_argument("--cache",          action="store_true", help="Cache downloads for 4 h")
    parser.add_argument("--no-interactive", action="store_true",
                        help="Skip the interactive prompt (use --ticker or DEFAULT_TICKER)")
    args = parser.parse_args()

    has_ticker = bool(args.ticker or args.watchlist)
    use_interactive = not has_ticker and not args.no_interactive

    if args.watchlist:
        tickers = [t.strip().upper() for t in args.watchlist]
    elif args.ticker:
        tickers = [args.ticker.strip().upper()]
    else:
        tickers = [DEFAULT_TICKER.strip().upper()] if DEFAULT_TICKER.strip() else []

    kwargs: dict[str, Any] = {
        "period":           args.period,
        "interval":         args.interval,
        "risk_free_rate":   args.risk_free_rate,
        "market_return":    args.market_return,
        "terminal_growth":  args.terminal_growth,
        "benchmark_ticker": args.benchmark,
        "use_cache":        args.cache,
        "peers":            tuple(p.strip().upper() for p in args.peers) if args.peers else (),
    }
    return tickers, kwargs, use_interactive


def _run_one(ticker: str, kwargs: dict[str, Any]) -> dict[str, Any] | None:
    config = ReportConfig(ticker=ticker, **kwargs)
    try:
        print(f"  {cyan('→')} {bold(ticker)}  fetching data…")
        data = fetch_data(config)
        print(f"  {cyan('→')} {bold(ticker)}  building report…")
        output_path = build_report(config, data)
        print(f"  {green('✓')} {bold(ticker)}  {output_path.resolve()}")

        # Collect summary for watchlist table
        info   = data["info"]
        ratios = calculate_fundamentals(info, data["financials"])
        df     = add_technical_indicators(data["history"]).dropna(subset=["Close"])
        risk   = risk_metrics(df, config)
        lc     = latest(df["Close"])
        fc     = df["Close"].dropna().iloc[0]
        q_cur  = clean_currency(ratios.get("quote_currency"))

        return {
            "ticker":        ticker,
            "price":         money(lc, q_cur),
            "mkt_cap":       human_number(ratios.get("market_cap")),
            "pe":            safe_float(ratios.get("trailing_pe")),
            "fcf_yield":     pct(ratios.get("fcf_yield")),
            "piotroski":     f"{ratios.get('piotroski_score')}/9" if ratios.get("piotroski_score") is not None else "n/a",
            "period_return": pct(lc / fc - 1),
            "vol":           pct(risk.get("annual_volatility")),
            "sharpe":        f"{safe_float(risk.get('sharpe')):.2f}" if not np.isnan(safe_float(risk.get("sharpe"))) else "n/a",
        }
    except Exception as exc:
        msg = str(exc)
        print(f"  {yellow('✗')} {ticker}  failed: {msg}", file=sys.stderr)
        if "No price history" in msg:
            print(f"    Tip: for German listings try {ticker}.DE", file=sys.stderr)
        elif "Could not resolve host" in msg or "DNSError" in msg:
            print("    Tip: check internet connection or VPN.", file=sys.stderr)
        return None


def main() -> None:
    tickers, kwargs, use_interactive = parse_args()

    if use_interactive:
        tickers, kwargs = interactive_prompt(kwargs)

    if not tickers:
        print("No ticker provided. Run with --ticker AAPL or without --no-interactive.", file=sys.stderr)
        raise SystemExit(1)

    print()
    results = [r for t in tickers if (r := _run_one(t, kwargs)) is not None]
    print()

    if len(tickers) > 1:
        print_watchlist_summary(results)


if __name__ == "__main__":
    main()
