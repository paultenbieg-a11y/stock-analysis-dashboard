"""Shared synthetic fixtures shaped like yfinance output — no network needed."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stockanalysis.config import ReportConfig  # noqa: E402

ANNUAL_COLS = [
    pd.Timestamp("2025-12-31"),
    pd.Timestamp("2024-12-31"),
    pd.Timestamp("2023-12-31"),
]


def make_history(n: int = 700, start_price: float = 100.0, seed: int = 7) -> pd.DataFrame:
    rng   = np.random.default_rng(seed)
    idx   = pd.bdate_range("2023-01-02", periods=n)
    rets  = rng.normal(0.0004, 0.015, n)
    close = start_price * np.exp(np.cumsum(rets))
    open_ = close * (1 + rng.normal(0, 0.003, n))
    high  = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.004, n)))
    low   = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.004, n)))
    vol   = rng.integers(1_000_000, 5_000_000, n).astype(float)
    df = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close,
         "Adj Close": close, "Volume": vol},
        index=idx,
    )
    df["AdjReturn"] = df["Adj Close"].pct_change()
    return df


@pytest.fixture
def history() -> pd.DataFrame:
    return make_history()


@pytest.fixture
def statements() -> dict[str, pd.DataFrame]:
    income = pd.DataFrame(
        {
            "Total Revenue":          [120e9, 110e9, 100e9],
            "Cost Of Revenue":        [66e9, 62e9, 57e9],
            "Gross Profit":           [54e9, 48e9, 43e9],
            "Operating Income":       [36e9, 32e9, 28e9],
            "EBITDA":                 [42e9, 38e9, 33e9],
            "Interest Expense":       [1.5e9, 1.6e9, 1.7e9],
            "Pretax Income":          [35e9, 31e9, 27e9],
            "Tax Provision":          [6e9, 5.5e9, 5e9],
            "Net Income":             [29e9, 25.5e9, 22e9],
            "Diluted EPS":            [3.5, 3.05, 2.6],
            "Diluted Average Shares": [8.3e9, 8.4e9, 8.5e9],
        },
        index=ANNUAL_COLS,
    ).T
    balance = pd.DataFrame(
        {
            "Total Assets":               [200e9, 190e9, 180e9],
            "Current Assets":             [80e9, 75e9, 70e9],
            "Current Liabilities":        [50e9, 52e9, 54e9],
            "Total Debt":                 [40e9, 45e9, 48e9],
            "Cash And Cash Equivalents":  [30e9, 26e9, 22e9],
            "Stockholders Equity":        [90e9, 80e9, 70e9],
            "Ordinary Shares Number":     [8.3e9, 8.4e9, 8.5e9],
        },
        index=ANNUAL_COLS,
    ).T
    cashflow = pd.DataFrame(
        {
            "Operating Cash Flow":  [38e9, 34e9, 30e9],
            "Capital Expenditure":  [-8e9, -7e9, -6e9],
            "Free Cash Flow":       [30e9, 27e9, 24e9],
            "Cash Dividends Paid":  [-4e9, -3.8e9, -3.5e9],
            "End Cash Position":    [30e9, 26e9, 22e9],
        },
        index=ANNUAL_COLS,
    ).T
    return {"income": income, "balance": balance, "cashflow": cashflow}


@pytest.fixture
def quarterly_income() -> pd.DataFrame:
    cols = pd.date_range("2024-03-31", periods=8, freq="QE")[::-1]
    data = {
        "Total Revenue": np.linspace(27e9, 33e9, 8)[::-1],
        "Gross Profit":  np.linspace(12e9, 15e9, 8)[::-1],
        "Net Income":    np.linspace(6e9, 8e9, 8)[::-1],
    }
    return pd.DataFrame(data, index=cols).T


@pytest.fixture
def info() -> dict:
    return {
        "currency": "USD",
        "financialCurrency": "USD",
        "marketCap": 1.8e12,
        "enterpriseValue": 1.85e12,
        "currentPrice": 216.0,
        "sharesOutstanding": 8.3e9,
        "beta": 1.1,
        "trailingPE": 30.0,
        "forwardPE": 26.0,
        "priceToBook": 20.0,
        "priceToSalesTrailing12Months": 15.0,
        "freeCashflow": 30e9,
        "enterpriseToEbitda": 22.0,
        "grossMargins": 0.45,
        "operatingMargins": 0.30,
        "profitMargins": 0.24,
        "revenueGrowth": 0.09,
        "returnOnEquity": 0.32,
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "longName": "Test Corp",
        "shortName": "Test",
        "longBusinessSummary": (
            "Test Corp designs consumer electronics and cloud software. "
            "It sells devices worldwide. The company also runs a services segment. "
            "It is headquartered in Testville."
        ),
        "website": "https://example.com",
        "exchange": "NMS",
        "fullExchangeName": "NasdaqGS",
        "quoteType": "EQUITY",
        "fullTimeEmployees": 100000,
        "city": "Testville",
        "country": "United States",
    }


@pytest.fixture
def config() -> ReportConfig:
    return ReportConfig(ticker="TEST", period="3y", monte_carlo_paths=60)


@pytest.fixture
def benchmark_df(history: pd.DataFrame) -> pd.DataFrame:
    rng   = np.random.default_rng(11)
    noise = rng.normal(0, 0.005, len(history))
    out   = pd.DataFrame(index=history.index)
    out["Return"] = history["AdjReturn"].fillna(0) * 0.8 + noise
    return out


def make_peer(symbol: str, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    mcap = float(rng.uniform(2e11, 3e12))
    return {
        "symbol": symbol,
        "name": f"{symbol} Inc",
        "market_cap": mcap,
        "trailing_pe": float(rng.uniform(15, 45)),
        "forward_pe": float(rng.uniform(14, 40)),
        "ev_to_ebitda": float(rng.uniform(10, 30)),
        "price_to_sales": float(rng.uniform(3, 16)),
        "gross_margin": float(rng.uniform(0.3, 0.7)),
        "operating_margin": float(rng.uniform(0.15, 0.4)),
        "net_margin": float(rng.uniform(0.1, 0.35)),
        "revenue_growth": float(rng.uniform(-0.02, 0.25)),
        "roe": float(rng.uniform(0.1, 0.5)),
        "fcf_yield": float(rng.uniform(0.01, 0.06)),
    }


@pytest.fixture
def peer_rows() -> list[dict]:
    return [make_peer(s, i + 1) for i, s in enumerate(["PEER1", "PEER2", "PEER3", "PEER4"])]


@pytest.fixture
def earnings() -> dict:
    past = pd.date_range("2023-04-25", periods=8, freq="QE")
    est  = np.linspace(2.4, 3.4, 8)
    act  = est + np.array([0.05, -0.03, 0.08, 0.02, 0.1, -0.05, 0.06, 0.04])
    hist = pd.DataFrame(
        {"EPS Estimate": est, "Reported EPS": act, "Surprise(%)": (act - est) / est * 100},
        index=past,
    )
    future = pd.Timestamp.now().normalize() + pd.Timedelta(days=21)
    hist.loc[future] = [3.5, np.nan, np.nan]
    return {"next_date": future, "history": hist.sort_index(ascending=False)}


@pytest.fixture
def data_bundle(history, statements, quarterly_income, info, benchmark_df, earnings, peer_rows) -> dict:
    return {
        "history": history,
        "financials": statements,
        "quarterly_income": quarterly_income,
        "info": info,
        "warnings": [],
        "benchmark_df": benchmark_df,
        "benchmark_sym": "SPY",
        "impl_vol": 0.28,
        "earnings": earnings,
        "peers": peer_rows,
    }
