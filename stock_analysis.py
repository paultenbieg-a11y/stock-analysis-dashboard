"""
Full scale stock analysis report generator.

Manual use:
    1. Change DEFAULT_TICKER below, then run:
       python stock_analysis.py

Command-line use:
    python stock_analysis.py --ticker MSFT --period 5y

The script downloads market and fundamental data with yfinance and writes a
single interactive HTML report to ./reports.
"""

from __future__ import annotations

import argparse
import base64
from html import escape
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    import yfinance as yf
except ImportError as exc:  # pragma: no cover - friendly runtime failure
    raise SystemExit(
        "Missing dependency: yfinance. Install dependencies with "
        "`pip install -r requirements.txt`."
    ) from exc


# ---------------------------------------------------------------------------
# Manual input area
# ---------------------------------------------------------------------------

DEFAULT_TICKER = "TSLA"
DEFAULT_PERIOD = "5y"
DEFAULT_INTERVAL = "1d"
REQUIRED_HISTORY_COLUMNS = {"Open", "High", "Low", "Close"}

# Optional manual overrides for investor-relations links when Yahoo only returns
# a generic corporate website. The report still works for any ticker without
# adding anything here.
IR_URL_OVERRIDES = {
    "SAP": "https://www.sap.com/investors/en.html",
    "SAP.DE": "https://www.sap.com/investors/en.html",
}


@dataclass(frozen=True)
class ReportConfig:
    ticker: str
    period: str = DEFAULT_PERIOD
    interval: str = DEFAULT_INTERVAL
    risk_free_rate: float = 0.045
    market_return: float = 0.085
    terminal_growth: float = 0.025
    forecast_years: int = 5
    monte_carlo_paths: int = 250
    monte_carlo_days: int = 252


def safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if value is None:
            return default
        result = float(value)
        if math.isfinite(result):
            return result
        return default
    except (TypeError, ValueError):
        return default


def human_number(value: Any, decimals: int = 2) -> str:
    value = safe_float(value)
    if np.isnan(value):
        return "n/a"
    sign = "-" if value < 0 else ""
    value = abs(value)
    units = [(1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]
    for threshold, suffix in units:
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
    text = str(value).strip().upper() if value is not None else ""
    if text in {"", "NAN", "NONE"}:
        return fallback
    return text or fallback


def same_currency(left: str, right: str) -> bool:
    return clean_currency(left, "") == clean_currency(right, "")


def safe_yfinance_frame(ticker: yf.Ticker, attr: str, label: str, warnings: list[str]) -> pd.DataFrame:
    try:
        data = getattr(ticker, attr)
    except Exception:
        warnings.append(f"{label} was unavailable from Yahoo Finance.")
        return pd.DataFrame()
    if isinstance(data, pd.DataFrame):
        return data
    warnings.append(f"{label} returned an unexpected data shape.")
    return pd.DataFrame()


def fetch_data(config: ReportConfig) -> dict[str, Any]:
    warnings = []
    ticker = yf.Ticker(config.ticker)
    history = ticker.history(period=config.period, interval=config.interval, auto_adjust=False)
    history = flatten_columns(history)
    if history.empty:
        raise RuntimeError(f"No price history returned for ticker {config.ticker!r}.")

    missing_columns = REQUIRED_HISTORY_COLUMNS - set(history.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise RuntimeError(f"Price history is missing required columns: {missing}.")
    if "Volume" not in history.columns:
        history["Volume"] = 0
        warnings.append("Volume data was unavailable, so volume-based indicators use zero volume.")

    financials = {
        "income": safe_yfinance_frame(ticker, "financials", "Annual income statement", warnings),
        "balance": safe_yfinance_frame(ticker, "balance_sheet", "Annual balance sheet", warnings),
        "cashflow": safe_yfinance_frame(ticker, "cashflow", "Annual cash flow statement", warnings),
    }

    try:
        info = ticker.info or {}
    except Exception:
        info = {}
        warnings.append("Company profile data was unavailable from Yahoo Finance.")

    return {"ticker": ticker, "history": history, "financials": financials, "info": info, "warnings": warnings}


def add_technical_indicators(data: pd.DataFrame) -> pd.DataFrame:
    df = data.copy()
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"].fillna(0)

    df["Return"] = close.pct_change()
    df["LogReturn"] = np.log(close / close.shift(1))
    df["SMA_20"] = close.rolling(20).mean()
    df["SMA_50"] = close.rolling(50).mean()
    df["SMA_200"] = close.rolling(200).mean()
    df["EMA_12"] = close.ewm(span=12, adjust=False).mean()
    df["EMA_26"] = close.ewm(span=26, adjust=False).mean()
    df["MACD"] = df["EMA_12"] - df["EMA_26"]
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI_14"] = 100 - (100 / (1 + rs))

    rolling_std = close.rolling(20).std()
    df["BB_Mid"] = df["SMA_20"]
    df["BB_Upper"] = df["BB_Mid"] + 2 * rolling_std
    df["BB_Lower"] = df["BB_Mid"] - 2 * rolling_std
    df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / df["BB_Mid"]

    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    df["ATR_14"] = true_range.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr = df["ATR_14"].replace(0, np.nan)
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / 14, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / 14, adjust=False).mean() / atr
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    df["ADX_14"] = dx.ewm(alpha=1 / 14, adjust=False).mean()

    direction = np.sign(close.diff()).fillna(0)
    df["OBV"] = (direction * volume).cumsum()
    df["Volume_SMA_20"] = volume.rolling(20).mean()

    return df


def latest(series: pd.Series) -> float:
    clean = series.dropna()
    return safe_float(clean.iloc[-1]) if not clean.empty else np.nan


def get_statement_value(statement: pd.DataFrame, possible_names: list[str], period: int = 0) -> float:
    if statement is None or statement.empty:
        return np.nan
    index_map = {str(idx).lower(): idx for idx in statement.index}
    for name in possible_names:
        key = name.lower()
        if key in index_map and statement.shape[1] > period:
            return safe_float(statement.loc[index_map[key]].iloc[period])
    return np.nan


def calculate_fundamentals(info: dict[str, Any], financials: dict[str, pd.DataFrame]) -> dict[str, Any]:
    income = financials.get("income", pd.DataFrame())
    balance = financials.get("balance", pd.DataFrame())
    cashflow = financials.get("cashflow", pd.DataFrame())

    quote_currency = clean_currency(info.get("currency"))
    financial_currency = clean_currency(info.get("financialCurrency"), quote_currency)
    currencies_comparable = same_currency(quote_currency, financial_currency)
    market_cap = safe_float(info.get("marketCap"))
    enterprise_value = safe_float(info.get("enterpriseValue"))
    price = safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
    shares = safe_float(info.get("sharesOutstanding"))
    beta = safe_float(info.get("beta"), 1.0)

    revenue = get_statement_value(income, ["Total Revenue", "Operating Revenue"])
    gross_profit = get_statement_value(income, ["Gross Profit"])
    operating_income = get_statement_value(income, ["Operating Income"])
    net_income = get_statement_value(income, ["Net Income", "Net Income Common Stockholders"])
    ebitda = get_statement_value(income, ["EBITDA", "Normalized EBITDA"])
    total_assets = get_statement_value(balance, ["Total Assets"])
    total_equity = get_statement_value(balance, ["Stockholders Equity", "Total Equity Gross Minority Interest"])
    total_debt = get_statement_value(balance, ["Total Debt", "Net Debt"])
    cash = get_statement_value(balance, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"])
    current_assets = get_statement_value(balance, ["Current Assets", "Total Current Assets"])
    current_liabilities = get_statement_value(balance, ["Current Liabilities", "Total Current Liabilities"])
    operating_cash_flow = get_statement_value(cashflow, ["Operating Cash Flow", "Total Cash From Operating Activities"])
    capex = get_statement_value(cashflow, ["Capital Expenditure", "Capital Expenditures"])
    free_cash_flow = safe_float(info.get("freeCashflow"))
    if np.isnan(free_cash_flow):
        free_cash_flow = operating_cash_flow + capex if not np.isnan(operating_cash_flow + capex) else np.nan

    revenue_prev = get_statement_value(income, ["Total Revenue", "Operating Revenue"], period=1)
    net_income_prev = get_statement_value(income, ["Net Income", "Net Income Common Stockholders"], period=1)
    total_assets_prev = get_statement_value(balance, ["Total Assets"], period=1)
    current_assets_prev = get_statement_value(balance, ["Current Assets", "Total Current Assets"], period=1)
    current_liabilities_prev = get_statement_value(balance, ["Current Liabilities", "Total Current Liabilities"], period=1)
    shares_prev = get_statement_value(balance, ["Ordinary Shares Number", "Share Issued"], period=1)

    gross_margin = gross_profit / revenue if revenue else np.nan
    operating_margin = operating_income / revenue if revenue else np.nan
    net_margin = net_income / revenue if revenue else np.nan
    roe = net_income / total_equity if total_equity else np.nan
    roa = net_income / total_assets if total_assets else np.nan
    debt_to_equity = total_debt / total_equity if total_equity else np.nan
    current_ratio = current_assets / current_liabilities if current_liabilities else np.nan
    revenue_growth = (revenue / revenue_prev - 1) if revenue_prev else np.nan
    earnings_growth = (net_income / net_income_prev - 1) if net_income_prev else np.nan
    asset_turnover = revenue / total_assets if total_assets else np.nan
    equity_multiplier = total_assets / total_equity if total_equity else np.nan

    ratios = {
        "price": price,
        "market_cap": market_cap,
        "enterprise_value": enterprise_value,
        "shares": shares,
        "beta": beta,
        "trailing_pe": safe_float(info.get("trailingPE")),
        "forward_pe": safe_float(info.get("forwardPE")),
        "peg": safe_float(info.get("pegRatio")),
        "price_to_book": safe_float(info.get("priceToBook")),
        "price_to_sales": safe_float(info.get("priceToSalesTrailing12Months")),
        "quote_currency": quote_currency,
        "financial_currency": financial_currency,
        "currencies_comparable": currencies_comparable,
        "ev_to_revenue": enterprise_value / revenue if currencies_comparable and revenue else np.nan,
        "ev_to_ebitda": enterprise_value / ebitda if currencies_comparable and ebitda else np.nan,
        "fcf_yield": free_cash_flow / market_cap if currencies_comparable and market_cap else np.nan,
        "earnings_yield": net_income / market_cap if currencies_comparable and market_cap else np.nan,
        "gross_margin": gross_margin,
        "operating_margin": operating_margin,
        "net_margin": net_margin,
        "roe": roe,
        "roa": roa,
        "debt_to_equity": debt_to_equity,
        "current_ratio": current_ratio,
        "revenue_growth": revenue_growth,
        "earnings_growth": earnings_growth,
        "asset_turnover": asset_turnover,
        "equity_multiplier": equity_multiplier,
        "free_cash_flow": free_cash_flow,
        "revenue": revenue,
        "net_income": net_income,
        "cash": cash,
        "debt": total_debt,
    }

    ratios["piotroski_score"] = piotroski_score(
        ratios=ratios,
        income=income,
        balance=balance,
        cashflow=cashflow,
        total_assets_prev=total_assets_prev,
        current_assets_prev=current_assets_prev,
        current_liabilities_prev=current_liabilities_prev,
        shares_prev=shares_prev,
    )
    return ratios


def piotroski_score(
    ratios: dict[str, float],
    income: pd.DataFrame,
    balance: pd.DataFrame,
    cashflow: pd.DataFrame,
    total_assets_prev: float,
    current_assets_prev: float,
    current_liabilities_prev: float,
    shares_prev: float,
) -> int | None:
    if income.empty or balance.empty or cashflow.empty:
        return None

    score = 0
    roa = ratios.get("roa", np.nan)
    ocf = ratios.get("free_cash_flow", np.nan)
    net_income = ratios.get("net_income", np.nan)
    total_assets = get_statement_value(balance, ["Total Assets"])
    total_debt = get_statement_value(balance, ["Total Debt", "Net Debt"])
    total_debt_prev = get_statement_value(balance, ["Total Debt", "Net Debt"], period=1)
    current_assets = get_statement_value(balance, ["Current Assets", "Total Current Assets"])
    current_liabilities = get_statement_value(balance, ["Current Liabilities", "Total Current Liabilities"])
    gross_margin = ratios.get("gross_margin", np.nan)
    revenue = ratios.get("revenue", np.nan)
    revenue_prev = get_statement_value(income, ["Total Revenue", "Operating Revenue"], period=1)
    gross_profit_prev = get_statement_value(income, ["Gross Profit"], period=1)
    shares = get_statement_value(balance, ["Ordinary Shares Number", "Share Issued"])

    roa_prev = (
        get_statement_value(income, ["Net Income", "Net Income Common Stockholders"], period=1) / total_assets_prev
        if total_assets_prev
        else np.nan
    )
    leverage = total_debt / total_assets if total_assets else np.nan
    leverage_prev = total_debt_prev / total_assets_prev if total_assets_prev else np.nan
    current_ratio = current_assets / current_liabilities if current_liabilities else np.nan
    current_ratio_prev = current_assets_prev / current_liabilities_prev if current_liabilities_prev else np.nan
    gross_margin_prev = gross_profit_prev / revenue_prev if revenue_prev else np.nan
    asset_turnover = revenue / total_assets if total_assets else np.nan
    asset_turnover_prev = revenue_prev / total_assets_prev if total_assets_prev else np.nan

    tests = [
        roa > 0,
        ocf > 0,
        roa > roa_prev,
        ocf > net_income,
        leverage < leverage_prev,
        current_ratio > current_ratio_prev,
        shares <= shares_prev if not np.isnan(shares_prev) else False,
        gross_margin > gross_margin_prev,
        asset_turnover > asset_turnover_prev,
    ]
    for passed in tests:
        if bool(passed) and not pd.isna(passed):
            score += 1
    return score


def dcf_valuation(ratios: dict[str, Any], config: ReportConfig) -> dict[str, Any]:
    fcf = safe_float(ratios.get("free_cash_flow"))
    shares = safe_float(ratios.get("shares"))
    beta = safe_float(ratios.get("beta"), 1.0)
    quote_currency = clean_currency(ratios.get("quote_currency"))
    financial_currency = clean_currency(ratios.get("financial_currency"), quote_currency)
    currencies_comparable = bool(ratios.get("currencies_comparable"))
    if np.isnan(fcf) or fcf <= 0 or np.isnan(shares) or shares <= 0:
        return {
            "fair_value": np.nan,
            "wacc_proxy": np.nan,
            "base_growth": np.nan,
            "quote_currency": quote_currency,
            "financial_currency": financial_currency,
            "comparable_to_price": currencies_comparable,
        }

    revenue_growth = safe_float(ratios.get("revenue_growth"), 0.03)
    earnings_growth = safe_float(ratios.get("earnings_growth"), revenue_growth)
    base_growth = np.nanmedian([revenue_growth, earnings_growth, 0.06])
    base_growth = float(np.clip(base_growth, -0.05, 0.15))

    cost_of_equity = config.risk_free_rate + beta * (config.market_return - config.risk_free_rate)
    discount_rate = float(np.clip(cost_of_equity, 0.07, 0.14))
    terminal_growth = min(config.terminal_growth, discount_rate - 0.01)

    projected = []
    current_fcf = fcf
    for year in range(1, config.forecast_years + 1):
        growth = base_growth * (1 - (year - 1) / (config.forecast_years * 1.5))
        current_fcf *= 1 + growth
        projected.append(current_fcf / ((1 + discount_rate) ** year))

    terminal_fcf = current_fcf * (1 + terminal_growth)
    terminal_value = terminal_fcf / (discount_rate - terminal_growth)
    discounted_terminal = terminal_value / ((1 + discount_rate) ** config.forecast_years)
    equity_value = sum(projected) + discounted_terminal
    fair_value = equity_value / shares

    return {
        "fair_value": fair_value,
        "wacc_proxy": discount_rate,
        "base_growth": base_growth,
        "terminal_growth": terminal_growth,
        "equity_value": equity_value,
        "quote_currency": quote_currency,
        "financial_currency": financial_currency,
        "comparable_to_price": currencies_comparable,
    }


def risk_metrics(df: pd.DataFrame) -> dict[str, float]:
    returns = df["Return"].dropna()
    log_returns = df["LogReturn"].dropna()
    if returns.empty:
        return {}
    annual_return = (1 + returns.mean()) ** 252 - 1
    annual_vol = returns.std() * np.sqrt(252)
    downside = returns[returns < 0].std() * np.sqrt(252)
    sharpe = annual_return / annual_vol if annual_vol else np.nan
    sortino = annual_return / downside if downside else np.nan
    cumulative = (1 + returns).cumprod()
    drawdown = cumulative / cumulative.cummax() - 1
    var_95 = returns.quantile(0.05)
    cvar_95 = returns[returns <= var_95].mean()
    skew = returns.skew()
    kurt = returns.kurtosis()
    return {
        "annual_return": annual_return,
        "annual_volatility": annual_vol,
        "sharpe_proxy": sharpe,
        "sortino_proxy": sortino,
        "max_drawdown": drawdown.min(),
        "daily_var_95": var_95,
        "daily_cvar_95": cvar_95,
        "skew": skew,
        "excess_kurtosis": kurt,
        "drift": log_returns.mean(),
        "daily_sigma": log_returns.std(),
    }


def monte_carlo(df: pd.DataFrame, config: ReportConfig) -> pd.DataFrame:
    last_price = latest(df["Close"])
    returns = df["LogReturn"].dropna()
    if returns.empty or np.isnan(last_price):
        return pd.DataFrame()
    mu = returns.mean()
    sigma = returns.std()
    if np.isnan(mu) or np.isnan(sigma) or sigma <= 0:
        return pd.DataFrame()
    rng = np.random.default_rng(42)
    shocks = rng.normal(
        loc=mu - 0.5 * sigma**2,
        scale=sigma,
        size=(config.monte_carlo_days, config.monte_carlo_paths),
    )
    paths = last_price * np.exp(np.cumsum(shocks, axis=0))
    dates = pd.bdate_range(df.index[-1], periods=config.monte_carlo_days + 1)[1:]
    return pd.DataFrame(paths, index=dates)


def technical_read(df: pd.DataFrame, currency: str) -> dict[str, str]:
    close = latest(df["Close"])
    sma_20 = latest(df["SMA_20"])
    sma_50 = latest(df["SMA_50"])
    sma_200 = latest(df["SMA_200"])
    rsi = latest(df["RSI_14"])
    macd = latest(df["MACD"])
    macd_signal = latest(df["MACD_Signal"])
    adx = latest(df["ADX_14"])
    atr = latest(df["ATR_14"])
    bb_upper = latest(df["BB_Upper"])
    bb_lower = latest(df["BB_Lower"])

    trend_parts = []
    if np.isnan(close) or np.isnan(sma_50) or np.isnan(sma_200):
        trend_parts.append("long-term trend is unavailable because the selected history is too short or incomplete")
    elif close > sma_200 and sma_50 > sma_200:
        trend_parts.append("primary uptrend: price and 50-day average are above the 200-day average")
    elif close < sma_200 and sma_50 < sma_200:
        trend_parts.append("primary downtrend: price and 50-day average are below the 200-day average")
    else:
        trend_parts.append("transitional trend: moving averages are not aligned")

    if np.isnan(close) or np.isnan(sma_20) or np.isnan(sma_50):
        trend_parts.append("short-term momentum is unavailable")
    elif close > sma_20 > sma_50:
        trend_parts.append("short-term momentum is constructive")
    elif close < sma_20 < sma_50:
        trend_parts.append("short-term momentum is weak")
    else:
        trend_parts.append("short-term momentum is mixed")

    if np.isnan(rsi):
        oscillator = "RSI is unavailable because the selected history is too short or incomplete."
    elif rsi >= 70:
        oscillator = "RSI is overbought; trend can persist, but upside risk/reward is less asymmetric."
    elif rsi <= 30:
        oscillator = "RSI is oversold; mean-reversion probability is elevated if fundamentals are intact."
    else:
        oscillator = "RSI is neutral, so price action is not at a classic oscillator extreme."

    if np.isnan(macd) or np.isnan(macd_signal):
        macd_text = "MACD is unavailable because the selected history is too short or incomplete."
    else:
        macd_text = "MACD is above signal, showing positive momentum." if macd > macd_signal else "MACD is below signal, showing fading momentum."
    trend_strength = (
        "ADX indicates a strong directional regime."
        if not np.isnan(adx) and adx >= 25
        else "ADX indicates a weaker or range-bound directional regime."
        if not np.isnan(adx)
        else "ADX is unavailable because the selected history is too short or incomplete."
    )
    if np.isnan(close) or np.isnan(atr):
        range_text = "ATR volatility band is unavailable because the selected history is too short or incomplete."
    else:
        range_text = (
            f"One ATR is about {money(atr, currency)}, making an approximate volatility band of "
            f"{money(close - atr, currency)} to {money(close + atr, currency)} around the last close."
        )
    if np.isnan(close) or np.isnan(bb_upper) or np.isnan(bb_lower):
        bollinger = "Bollinger Band position is unavailable because the selected history is too short or incomplete."
    elif close >= bb_upper:
        bollinger = "Price is pressing the upper Bollinger Band, often a sign of trend strength or short-term stretch."
    elif close <= bb_lower:
        bollinger = "Price is pressing the lower Bollinger Band, often a sign of capitulation or short-term weakness."
    else:
        bollinger = "Price sits inside its Bollinger envelope."

    return {
        "trend": "; ".join(trend_parts) + ".",
        "oscillator": oscillator,
        "macd": macd_text,
        "strength": trend_strength,
        "range": range_text,
        "bollinger": bollinger,
    }


def fundamental_read(ratios: dict[str, Any], valuation: dict[str, Any], quote_currency: str, financial_currency: str) -> dict[str, str]:
    roe = safe_float(ratios.get("roe"))
    debt_to_equity = safe_float(ratios.get("debt_to_equity"))
    revenue_growth = safe_float(ratios.get("revenue_growth"))
    fair_value = safe_float(valuation.get("fair_value"))
    price = safe_float(ratios.get("price"))
    piotroski = ratios.get("piotroski_score")
    comparable_to_price = bool(valuation.get("comparable_to_price"))

    quality = []
    if np.isnan(roe):
        quality.append("unavailable return-on-equity data")
    else:
        quality.append(
            "high return on equity" if roe >= 0.18 else "acceptable return on equity" if roe >= 0.10 else "modest return on equity"
        )
    if np.isnan(debt_to_equity):
        quality.append("unavailable leverage data")
    else:
        quality.append(
            "conservative leverage" if debt_to_equity < 0.8 else "meaningful leverage" if debt_to_equity < 2.0 else "high leverage"
        )
    if np.isnan(revenue_growth):
        quality.append("unavailable revenue-growth data")
    else:
        quality.append(
            "positive revenue growth" if revenue_growth > 0 else "contracting revenue" if revenue_growth < 0 else "flat revenue growth"
        )

    valuation_text = "DCF could not be estimated because free cash flow or share count is unavailable."
    if not np.isnan(fair_value) and not comparable_to_price:
        valuation_text = (
            f"DCF fair value is {money(fair_value, financial_currency)} in the financial statement currency. "
            f"It is not compared with the quoted share price because the quote currency is {quote_currency} "
            f"while the financial statements are reported in {financial_currency}."
        )
    elif not np.isnan(fair_value) and not np.isnan(price) and price > 0:
        gap = fair_value / price - 1
        if gap > 0.15:
            stance = "undervalued under the base assumptions"
        elif gap < -0.15:
            stance = "overvalued under the base assumptions"
        else:
            stance = "roughly fairly valued under the base assumptions"
        valuation_text = f"DCF fair value is {money(fair_value, quote_currency)} versus price {money(price, quote_currency)}, implying {pct(gap)} upside/downside and appearing {stance}."

    score_text = (
        "Piotroski F-score could not be computed from available statements."
        if piotroski is None
        else f"Piotroski F-score is {piotroski}/9, where higher values indicate stronger profitability, leverage, liquidity, and operating efficiency."
    )

    return {
        "quality": "The business profile shows " + ", ".join(quality) + ".",
        "valuation": valuation_text,
        "score": score_text,
    }


def scenario_table(df: pd.DataFrame, ratios: dict[str, Any], valuation: dict[str, Any], currency: str) -> pd.DataFrame:
    last_price = latest(df["Close"])
    atr = latest(df["ATR_14"])
    sma_200 = latest(df["SMA_200"])
    fair_value = safe_float(valuation.get("fair_value"))
    comparable_to_price = bool(valuation.get("comparable_to_price"))
    annual_vol = df["Return"].dropna().std() * np.sqrt(252)
    vol_move = last_price * annual_vol if not np.isnan(last_price) and not np.isnan(annual_vol) else np.nan
    bull_reference = last_price + vol_move * 0.5 if not np.isnan(vol_move) else last_price
    base_reference = fair_value if comparable_to_price and not np.isnan(fair_value) else last_price
    if comparable_to_price and not np.isnan(fair_value) and not np.isnan(bull_reference):
        bull_reference = max(bull_reference, fair_value)
    bear_reference = min(sma_200, last_price - 2 * atr) if not np.isnan(sma_200) and not np.isnan(atr) else last_price

    rows = [
        {
            "Scenario": "Bull case",
            "Trigger": "Price holds above rising 50/200-day averages; earnings revisions and cash flow trend improve.",
            "Reference Level": money(bull_reference, currency),
            "Interpretation": "Momentum and fundamentals align; valuation can re-rate if growth durability improves.",
        },
        {
            "Scenario": "Base case",
            "Trigger": "Price mean-reverts around trend while fundamentals evolve near current consensus.",
            "Reference Level": money(base_reference, currency),
            "Interpretation": "Expected return depends mainly on earnings delivery, buybacks/dividends, and multiple stability.",
        },
        {
            "Scenario": "Bear case",
            "Trigger": "Break below 200-day trend or deterioration in margins, balance sheet, or cash conversion.",
            "Reference Level": money(bear_reference, currency),
            "Interpretation": "Technical damage can amplify fundamental disappointment through multiple compression.",
        },
    ]
    return pd.DataFrame(rows)


def line_chart(df: pd.DataFrame, ticker: str) -> str:
    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.52, 0.16, 0.16, 0.16],
        subplot_titles=("Price, trend, and Bollinger envelope", "Volume", "RSI", "MACD"),
    )
    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="OHLC"), row=1, col=1)
    for col, color in [("SMA_20", "#47d7ac"), ("SMA_50", "#f4c542"), ("SMA_200", "#ff6b6b")]:
        fig.add_trace(go.Scatter(x=df.index, y=df[col], name=col, line=dict(width=1.4, color=color)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Upper"], name="Bollinger upper", line=dict(width=1, color="rgba(147,197,253,.35)")), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Lower"], name="Bollinger lower", fill="tonexty", line=dict(width=1, color="rgba(147,197,253,.35)")), row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volume", marker_color="#64748b"), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["Volume_SMA_20"], name="Volume SMA 20", line=dict(color="#38bdf8", width=1.2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI_14"], name="RSI 14", line=dict(color="#a78bfa", width=1.4)), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="#fb7185", row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#22c55e", row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD", line=dict(color="#38bdf8", width=1.4)), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD_Signal"], name="Signal", line=dict(color="#f97316", width=1.2)), row=4, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df["MACD_Hist"], name="Histogram", marker_color="#94a3b8"), row=4, col=1)
    fig.update_layout(
        template="plotly_dark",
        height=900,
        title=f"{ticker} Technical Market Structure",
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=30, r=25, t=80, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(2,6,23,0.95)",
    )
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def risk_chart(df: pd.DataFrame) -> str:
    returns = df["Return"].dropna()
    cumulative = (1 + returns).cumprod()
    drawdown = cumulative / cumulative.cummax() - 1
    monthly = df["Close"].resample("ME").last().pct_change().dropna()

    fig = make_subplots(
        rows=2,
        cols=2,
        specs=[[{"type": "xy"}, {"type": "xy"}], [{"type": "xy"}, {"type": "xy"}]],
        subplot_titles=("Cumulative return", "Drawdown", "Daily return distribution", "Monthly return bars"),
    )
    fig.add_trace(go.Scatter(x=cumulative.index, y=cumulative, name="Growth of $1", line=dict(color="#22c55e")), row=1, col=1)
    fig.add_trace(go.Scatter(x=drawdown.index, y=drawdown, name="Drawdown", fill="tozeroy", line=dict(color="#ef4444")), row=1, col=2)
    fig.add_trace(go.Histogram(x=returns, nbinsx=80, name="Daily returns", marker_color="#60a5fa"), row=2, col=1)
    fig.add_trace(go.Bar(x=monthly.index, y=monthly, name="Monthly returns", marker_color=np.where(monthly >= 0, "#22c55e", "#ef4444")), row=2, col=2)
    fig.update_yaxes(tickformat=".0%", row=1, col=2)
    fig.update_yaxes(tickformat=".0%", row=2, col=2)
    fig.update_layout(
        template="plotly_dark",
        height=680,
        title="Return, Drawdown, and Distribution Diagnostics",
        showlegend=False,
        margin=dict(l=30, r=25, t=80, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(2,6,23,0.95)",
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def monte_carlo_chart(paths: pd.DataFrame, last_price: float) -> str:
    if paths.empty:
        return "<p class='muted'>Monte Carlo chart unavailable because return history is insufficient.</p>"
    quantiles = paths.quantile([0.05, 0.25, 0.50, 0.75, 0.95], axis=1).T
    fig = go.Figure()
    sample = paths.iloc[:, : min(40, paths.shape[1])]
    for col in sample.columns:
        fig.add_trace(go.Scatter(x=sample.index, y=sample[col], mode="lines", line=dict(color="rgba(148,163,184,0.12)", width=1), showlegend=False))
    fig.add_trace(go.Scatter(x=quantiles.index, y=quantiles[0.95], name="95th percentile", line=dict(color="#22c55e", width=1.5)))
    fig.add_trace(go.Scatter(x=quantiles.index, y=quantiles[0.75], name="75th percentile", line=dict(color="#38bdf8", width=1.2)))
    fig.add_trace(go.Scatter(x=quantiles.index, y=quantiles[0.50], name="Median", line=dict(color="#f8fafc", width=2.2)))
    fig.add_trace(go.Scatter(x=quantiles.index, y=quantiles[0.25], name="25th percentile", line=dict(color="#f59e0b", width=1.2)))
    fig.add_trace(go.Scatter(x=quantiles.index, y=quantiles[0.05], name="5th percentile", line=dict(color="#ef4444", width=1.5)))
    fig.add_hline(y=last_price, line_dash="dot", line_color="#cbd5e1", annotation_text="Last close")
    fig.update_layout(
        template="plotly_dark",
        height=520,
        title="One-Year Monte Carlo Price Cone",
        margin=dict(l=30, r=25, t=70, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(2,6,23,0.95)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def metric_card(label: str, value: str, detail: str = "") -> str:
    detail_html = f"<span>{detail}</span>" if detail else ""
    return f"<div class='metric'><small>{label}</small><strong>{value}</strong>{detail_html}</div>"


def df_to_html_table(df: pd.DataFrame, classes: str = "data-table") -> str:
    return df.to_html(index=False, classes=classes, border=0, escape=False)


def statement_section(label: str) -> dict[str, Any]:
    return {"type": "section", "label": label}


def statement_line(
    label: str,
    aliases: list[str],
    kind: str = "currency",
    role: str = "normal",
    indent: int = 0,
) -> dict[str, Any]:
    return {
        "type": "line",
        "label": label,
        "aliases": aliases,
        "kind": kind,
        "role": role,
        "indent": indent,
    }


INCOME_STATEMENT_ROWS = [
    statement_section("Revenue and gross profit"),
    statement_line("Total revenue", ["Total Revenue", "Operating Revenue"], role="major"),
    statement_line("Cost of revenue", ["Cost Of Revenue", "Reconciled Cost Of Revenue"], indent=1),
    statement_line("Gross profit", ["Gross Profit"], role="subtotal"),
    statement_section("Operating expenses and profit"),
    statement_line("Research and development", ["Research And Development"], indent=1),
    statement_line("Selling, general and administrative", ["Selling General And Administration", "General And Administrative Expense"], indent=1),
    statement_line("Total operating expenses", ["Operating Expense", "Total Expenses"], role="subtotal"),
    statement_line("Operating income / EBIT", ["Operating Income", "Total Operating Income As Reported", "EBIT"], role="total"),
    statement_line("EBITDA", ["EBITDA", "Normalized EBITDA"], role="major"),
    statement_section("Below operating line"),
    statement_line("Interest income", ["Interest Income", "Interest Income Non Operating"], indent=1),
    statement_line("Interest expense", ["Interest Expense", "Interest Expense Non Operating"], indent=1),
    statement_line("Pretax income", ["Pretax Income"], role="subtotal"),
    statement_line("Tax provision", ["Tax Provision"], indent=1),
    statement_line("Net income", ["Net Income", "Net Income Common Stockholders"], role="grand-total"),
    statement_section("Per-share and share data"),
    statement_line("Diluted EPS", ["Diluted EPS"], kind="eps", role="major"),
    statement_line("Diluted average shares", ["Diluted Average Shares"], kind="shares"),
]

BALANCE_SHEET_ROWS = [
    statement_section("Assets"),
    statement_line("Cash and short-term investments", ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"], indent=1),
    statement_line("Receivables", ["Receivables", "Accounts Receivable", "Net Receivables"], indent=1),
    statement_line("Inventory", ["Inventory"], indent=1),
    statement_line("Current assets", ["Current Assets", "Total Current Assets"], role="subtotal"),
    statement_line("Goodwill and intangibles", ["Goodwill And Other Intangible Assets", "Goodwill", "Other Intangible Assets"], indent=1),
    statement_line("Property, plant and equipment", ["Net PPE", "Property Plant Equipment"], indent=1),
    statement_line("Total assets", ["Total Assets"], role="grand-total"),
    statement_section("Liabilities"),
    statement_line("Current liabilities", ["Current Liabilities", "Total Current Liabilities"], role="subtotal"),
    statement_line("Total debt", ["Total Debt"], indent=1),
    statement_line("Net debt", ["Net Debt"], indent=1),
    statement_line("Total liabilities", ["Total Liabilities Net Minority Interest", "Total Liab"], role="grand-total"),
    statement_section("Equity and capitalization"),
    statement_line("Shareholders equity", ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"], role="grand-total"),
    statement_line("Minority interest", ["Minority Interest"], indent=1),
    statement_line("Working capital", ["Working Capital"], role="subtotal"),
    statement_line("Invested capital", ["Invested Capital"], role="subtotal"),
    statement_line("Shares issued", ["Share Issued", "Ordinary Shares Number"], kind="shares"),
]

CASH_FLOW_ROWS = [
    statement_section("Operating activities"),
    statement_line("Net income from continuing operations", ["Net Income From Continuing Operations", "Net Income"], role="major"),
    statement_line("Depreciation and amortization", ["Depreciation And Amortization", "Depreciation Amortization Depletion"], indent=1),
    statement_line("Stock-based compensation", ["Stock Based Compensation"], indent=1),
    statement_line("Change in working capital", ["Change In Working Capital"], indent=1),
    statement_line("Operating cash flow", ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"], role="grand-total"),
    statement_section("Investing activities"),
    statement_line("Capital expenditure", ["Capital Expenditure", "Capital Expenditures"], indent=1),
    statement_line("Free cash flow", ["Free Cash Flow"], role="grand-total"),
    statement_line("Investing cash flow", ["Investing Cash Flow", "Cash Flow From Continuing Investing Activities"], role="subtotal"),
    statement_line("Business acquisitions / disposals", ["Net Business Purchase And Sale", "Purchase Of Business", "Sale Of Business"], indent=1),
    statement_line("Investment purchases / sales", ["Net Investment Purchase And Sale"], indent=1),
    statement_section("Financing activities"),
    statement_line("Financing cash flow", ["Financing Cash Flow", "Cash Flow From Continuing Financing Activities"], role="subtotal"),
    statement_line("Dividends paid", ["Cash Dividends Paid", "Common Stock Dividend Paid"], indent=1),
    statement_line("Share repurchases", ["Repurchase Of Capital Stock", "Common Stock Payments"], indent=1),
    statement_line("Debt issued", ["Issuance Of Debt", "Long Term Debt Issuance"], indent=1),
    statement_line("Debt repaid", ["Repayment Of Debt", "Long Term Debt Payments"], indent=1),
    statement_section("Cash reconciliation"),
    statement_line("Change in cash", ["Changes In Cash"], role="subtotal"),
    statement_line("Ending cash position", ["End Cash Position"], role="grand-total"),
]


def period_label(period: Any) -> str:
    try:
        return pd.to_datetime(period).strftime("%Y")
    except Exception:
        return str(period)


def get_statement_value_for_period(statement: pd.DataFrame, possible_names: list[str], period: Any) -> float:
    if statement is None or statement.empty or period not in statement.columns:
        return np.nan
    index_map = {str(idx).lower(): idx for idx in statement.index}
    for name in possible_names:
        key = name.lower()
        if key in index_map:
            return safe_float(statement.loc[index_map[key], period])
    return np.nan


def format_statement_value(value: Any, kind: str) -> str:
    value = safe_float(value)
    if np.isnan(value):
        return "n/a"
    if kind == "eps":
        return f"({abs(value):,.2f})" if value < 0 else f"{value:,.2f}"
    if kind == "shares":
        return human_number(value)
    return f"({human_number(abs(value))})" if value < 0 else human_number(value)


def finance_statement_table_html(
    statement: pd.DataFrame,
    row_defs: list[dict[str, Any]],
    max_years: int = 3,
) -> str:
    if statement is None or statement.empty:
        return "<p class='muted'>Annual statement data was not returned for this ticker.</p>"

    periods = list(statement.columns[:max_years])
    headers = "".join(f"<th class='number-cell'>{escape(period_label(period))}</th>" for period in periods)
    body_rows = []

    for row_def in row_defs:
        if row_def["type"] == "section":
            body_rows.append(
                f"<tr class='fs-section-row'><td colspan='{len(periods) + 1}'>{escape(row_def['label'])}</td></tr>"
            )
            continue

        role = row_def.get("role", "normal")
        indent = int(row_def.get("indent", 0))
        classes = ["fs-line-row", f"fs-{role}", f"fs-indent-{indent}"]
        values = []
        for period in periods:
            value = get_statement_value_for_period(statement, row_def["aliases"], period)
            formatted = format_statement_value(value, row_def.get("kind", "currency"))
            value_class = "negative" if safe_float(value) < 0 else ""
            values.append(f"<td class='number-cell {value_class}'>{escape(formatted)}</td>")

        body_rows.append(
            f"<tr class='{' '.join(classes)}'><td class='line-item'>{escape(row_def['label'])}</td>{''.join(values)}</tr>"
        )

    return f"""
      <table class="financial-statement-table">
        <thead>
          <tr>
            <th class="line-item">Line item</th>
            {headers}
          </tr>
        </thead>
        <tbody>
          {''.join(body_rows)}
        </tbody>
      </table>
    """


def statement_chart_values(statement: pd.DataFrame, aliases: list[str], periods: list[Any]) -> list[float | None]:
    values = []
    for period in periods:
        value = get_statement_value_for_period(statement, aliases, period)
        values.append(None if np.isnan(value) else value)
    return values


def annual_statement_chart(
    title: str,
    statement: pd.DataFrame,
    series: list[tuple[str, list[str], str]],
    currency: str,
) -> str:
    if statement is None or statement.empty:
        return "<p class='muted'>Chart unavailable because annual statement data was not returned.</p>"

    periods = list(statement.columns[:3])
    chart_periods = list(reversed(periods))
    years = [period_label(period) for period in chart_periods]

    fig = go.Figure()
    for name, aliases, color in series:
        fig.add_trace(
            go.Bar(
                x=years,
                y=statement_chart_values(statement, aliases, chart_periods),
                name=name,
                marker_color=color,
                hovertemplate=f"%{{x}}<br>{name}: %{{y:,.0f}} {currency}<extra></extra>",
            )
        )

    fig.update_layout(
        template="plotly_dark",
        barmode="group",
        height=430,
        title=f"{title} Snapshot ({currency})",
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="right", x=1),
        margin=dict(l=55, r=30, t=82, b=48),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(2,6,23,0.95)",
        bargap=0.22,
        bargroupgap=0.08,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(148,163,184,.18)", zerolinecolor="rgba(226,232,240,.35)")
    return fig.to_html(full_html=False, include_plotlyjs=False)


def annual_statement_section_html(financials: dict[str, pd.DataFrame], currency: str) -> str:
    income = financials.get("income", pd.DataFrame())
    balance = financials.get("balance", pd.DataFrame())
    cashflow = financials.get("cashflow", pd.DataFrame())
    income_table = finance_statement_table_html(income, INCOME_STATEMENT_ROWS)
    balance_table = finance_statement_table_html(balance, BALANCE_SHEET_ROWS)
    cashflow_table = finance_statement_table_html(cashflow, CASH_FLOW_ROWS)
    income_chart = annual_statement_chart(
        "Annual Income Statement",
        income,
        [
            ("Revenue", ["Total Revenue", "Operating Revenue"], "#38bdf8"),
            ("Gross profit", ["Gross Profit"], "#22c55e"),
            ("Operating income", ["Operating Income", "Total Operating Income As Reported", "EBIT"], "#f59e0b"),
            ("Net income", ["Net Income", "Net Income Common Stockholders"], "#a78bfa"),
        ],
        currency,
    )
    balance_chart = annual_statement_chart(
        "Annual Balance Sheet",
        balance,
        [
            ("Assets", ["Total Assets"], "#60a5fa"),
            ("Equity", ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"], "#a78bfa"),
            ("Debt", ["Total Debt"], "#f97316"),
            ("Cash and ST investments", ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"], "#22c55e"),
        ],
        currency,
    )
    cashflow_chart = annual_statement_chart(
        "Annual Cash Flow Statement",
        cashflow,
        [
            ("Operating cash flow", ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"], "#14b8a6"),
            ("Capex", ["Capital Expenditure", "Capital Expenditures"], "#ef4444"),
            ("Free cash flow", ["Free Cash Flow"], "#f59e0b"),
            ("Dividends paid", ["Cash Dividends Paid", "Common Stock Dividend Paid"], "#818cf8"),
        ],
        currency,
    )

    return f"""
      <section>
        <h2>Annual Financial Statements</h2>
        <p class="muted">Most recent annual release plus the previous two annual periods. These annual statement tables are independent of the selected price-chart period. Yahoo Finance standardizes statement labels, so IFRS reporters such as SAP and US GAAP reporters use a common layout where possible.</p>
        <p class="statement-unit-note">Financial statement table figures are shown in <strong>{escape(currency)}</strong> unless otherwise noted. EPS is shown in {escape(currency)} per share; share counts are shown as shares.</p>
        <div class="statement-stack">
          <article class="statement-panel">
            <div class="statement-heading">
              <h3>Annual Income Statement</h3>
              <p class="muted">Revenue scale, profitability, operating leverage, and earnings power.</p>
            </div>
            <div class="chart-wrap chart-wrap-spacious">{income_chart}</div>
            <div class="table-scroll">{income_table}</div>
          </article>
          <article class="statement-panel">
            <div class="statement-heading">
              <h3>Annual Balance Sheet</h3>
              <p class="muted">Capital structure, asset base, liquidity, and balance sheet resilience.</p>
            </div>
            <div class="chart-wrap chart-wrap-spacious">{balance_chart}</div>
            <div class="table-scroll">{balance_table}</div>
          </article>
          <article class="statement-panel">
            <div class="statement-heading">
              <h3>Annual Cash Flow Statement</h3>
              <p class="muted">Cash conversion, reinvestment needs, financing flows, and free cash flow.</p>
            </div>
            <div class="chart-wrap chart-wrap-spacious">{cashflow_chart}</div>
            <div class="table-scroll">{cashflow_table}</div>
          </article>
        </div>
      </section>
    """


def investor_relations_target(info: dict[str, Any], ticker: str, company: str) -> tuple[str, str]:
    normalized = ticker.upper()
    if normalized in IR_URL_OVERRIDES:
        return IR_URL_OVERRIDES[normalized], "Investor relations"

    for key in ("irWebsite", "investorRelationsWebsite", "investorRelationsUrl"):
        value = info.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value, "Investor relations"

    website = info.get("website")
    if isinstance(website, str) and website.startswith(("http://", "https://")):
        return website, "Corporate website"

    query = quote_plus(f"{company} investor relations")
    return f"https://www.google.com/search?q={query}", "Investor relations search"


def compact_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def summary_sentences(summary: str, max_sentences: int = 4) -> str:
    summary = compact_text(summary)
    if not summary:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", summary)
    selected = []
    for sentence in sentences:
        sentence = sentence.strip()
        if sentence:
            selected.append(sentence)
        if len(selected) >= max_sentences:
            break
    return " ".join(selected)


def profile_fact(label: str, value: Any) -> str:
    value = compact_text(value)
    if not value:
        value = "n/a"
    return f"<div class='profile-fact'><small>{escape(label)}</small><strong>{escape(value)}</strong></div>"


def employee_count(value: Any) -> str:
    value = safe_float(value)
    if np.isnan(value):
        return ""
    return f"{value:,.0f}"


def specialization_tags(info: dict[str, Any]) -> list[str]:
    sector = compact_text(info.get("sector"))
    industry = compact_text(info.get("industry"))
    summary = compact_text(info.get("longBusinessSummary")).lower()
    tags = []

    for value in (sector, industry):
        if value and value not in tags:
            tags.append(value)

    keyword_map = [
        ("cloud", "Cloud"),
        ("software", "Software"),
        ("artificial intelligence", "Artificial intelligence"),
        ("machine learning", "Machine learning"),
        ("semiconductor", "Semiconductors"),
        ("electric vehicle", "Electric vehicles"),
        ("automotive", "Automotive"),
        ("energy storage", "Energy storage"),
        ("solar", "Solar"),
        ("payments", "Payments"),
        ("e-commerce", "E-commerce"),
        ("advertising", "Advertising"),
        ("streaming", "Streaming"),
        ("cybersecurity", "Cybersecurity"),
        ("pharmaceutical", "Pharmaceuticals"),
        ("biotechnology", "Biotechnology"),
        ("medical", "Medical technology"),
        ("banking", "Banking"),
        ("insurance", "Insurance"),
        ("retail", "Retail"),
        ("aerospace", "Aerospace"),
        ("industrial", "Industrials"),
        ("consumer", "Consumer"),
        ("renewable", "Renewables"),
    ]
    for keyword, label in keyword_map:
        if keyword in summary and label not in tags:
            tags.append(label)
        if len(tags) >= 8:
            break
    return tags[:8]


def company_overview_html(info: dict[str, Any], ticker: str, company: str, ir_url: str, ir_label: str) -> str:
    summary = summary_sentences(info.get("longBusinessSummary"), max_sentences=4)
    if not summary:
        summary = (
            "Yahoo Finance did not return a full business description for this ticker. "
            "Use the linked company page and official filings to complete the qualitative business overview."
        )

    city = compact_text(info.get("city"))
    state = compact_text(info.get("state"))
    country = compact_text(info.get("country"))
    headquarters = ", ".join(part for part in (city, state, country) if part)
    website = compact_text(info.get("website"))
    website_url = website if website.startswith(("http://", "https://")) else ""
    exchange = compact_text(info.get("exchange") or info.get("fullExchangeName"))
    quote_type = compact_text(info.get("quoteType"))
    employees = employee_count(info.get("fullTimeEmployees"))
    tags = specialization_tags(info)
    tag_html = "".join(f"<span class='specialty-tag'>{escape(tag)}</span>" for tag in tags)
    if not tag_html:
        tag_html = "<span class='specialty-tag'>Profile data limited</span>"

    facts = [
        profile_fact("Sector", info.get("sector")),
        profile_fact("Industry", info.get("industry")),
        profile_fact("Headquarters", headquarters),
        profile_fact("Employees", employees),
        profile_fact("Exchange", exchange),
        profile_fact("Security type", quote_type),
    ]
    website_html = (
        f"<a href='{escape(website_url)}' target='_blank' rel='noopener noreferrer'>{escape(website_url)}</a>"
        if website_url
        else "n/a"
    )

    return f"""
      <section>
        <h2>Company Overview</h2>
        <div class="company-overview-grid">
          <div class="narrative company-intro">
            <p><strong>{escape(company)}</strong> ({escape(ticker)}) operates in the {escape(compact_text(info.get("sector")) or "n/a")} sector and is classified in the {escape(compact_text(info.get("industry")) or "n/a")} industry.</p>
            <p>{escape(summary)}</p>
            <div class="specialty-tags">{tag_html}</div>
          </div>
          <aside class="profile-card">
            <h3>Profile Facts</h3>
            <div class="profile-facts">{''.join(facts)}</div>
            <p class="profile-link-row"><span>Website</span>{website_html}</p>
            <p class="profile-link-row"><span>{escape(ir_label)}</span><a href="{escape(ir_url)}" target="_blank" rel="noopener noreferrer">{escape(company)}</a></p>
          </aside>
        </div>
      </section>
    """


def data_notes_html(notes: list[str]) -> str:
    clean_notes = []
    seen = set()
    for note in notes:
        text = compact_text(note)
        if text and text not in seen:
            clean_notes.append(text)
            seen.add(text)

    if not clean_notes:
        return ""

    items = "".join(f"<li>{escape(note)}</li>" for note in clean_notes)
    return f"""
      <section class="data-notes">
        <h2>Data Notes</h2>
        <ul>{items}</ul>
      </section>
    """


def safe_output_filename(ticker: str) -> str:
    safe_chars = []
    for char in ticker.upper():
        safe_chars.append(char if char.isalnum() or char in ("-", ".", "_") else "_")
    return "".join(safe_chars).strip("._") or "STOCK"


def build_report(config: ReportConfig, data: dict[str, Any]) -> Path:
    info = data["info"]
    df = add_technical_indicators(data["history"]).dropna(subset=["Close"])
    if df.empty:
        raise RuntimeError("Price history did not contain valid closing prices.")
    ratios = calculate_fundamentals(info, data["financials"])
    valuation = dcf_valuation(ratios, config)
    risk = risk_metrics(df)

    ticker = config.ticker.upper()
    company = info.get("longName") or info.get("shortName") or ticker
    quote_currency = clean_currency(ratios.get("quote_currency"))
    financial_currency = clean_currency(ratios.get("financial_currency"), quote_currency)
    currencies_comparable = same_currency(quote_currency, financial_currency)
    tech = technical_read(df, quote_currency)
    fund = fundamental_read(ratios, valuation, quote_currency, financial_currency)
    scenarios = scenario_table(df, ratios, valuation, quote_currency)
    paths = monte_carlo(df, config)
    ir_url, ir_label = investor_relations_target(info, ticker, company)
    company_overview = company_overview_html(info, ticker, company, ir_url, ir_label)
    data_notes = list(data.get("warnings", []))
    if not currencies_comparable:
        data_notes.append(
            f"Quote currency is {quote_currency}, while financial statements are reported in {financial_currency}. "
            "Currency-sensitive valuation ratios and DCF price comparison are therefore shown cautiously or marked n/a."
        )
    data_notes_section = data_notes_html(data_notes)
    last_close = latest(df["Close"])
    first_close = df["Close"].dropna().iloc[0]
    period_return = last_close / first_close - 1
    fair_value = safe_float(valuation.get("fair_value"))
    dcf_comparable = bool(valuation.get("comparable_to_price"))
    dcf_gap = fair_value / last_close - 1 if dcf_comparable and not np.isnan(fair_value) and last_close else np.nan
    dcf_currency = quote_currency if dcf_comparable else financial_currency
    dcf_detail = f"{pct(dcf_gap)} vs price" if dcf_comparable and not np.isnan(dcf_gap) else "not price-comparable"

    technical_html = line_chart(df, ticker)
    annual_statements_html = annual_statement_section_html(data["financials"], financial_currency)
    risk_html = risk_chart(df)
    monte_carlo_html = monte_carlo_chart(paths, last_close)

    metrics = [
        metric_card("Last close", money(last_close, quote_currency), quote_currency),
        metric_card("Market cap", human_number(ratios.get("market_cap")), quote_currency),
        metric_card("Period return", pct(period_return), config.period),
        metric_card("Annual volatility", pct(risk.get("annual_volatility")), "realized"),
        metric_card("Max drawdown", pct(risk.get("max_drawdown")), "history"),
        metric_card("DCF fair value", money(fair_value, dcf_currency), dcf_detail),
        metric_card("FCF yield", pct(ratios.get("fcf_yield")), "cash return"),
        metric_card("Piotroski", "n/a" if ratios.get("piotroski_score") is None else f"{ratios.get('piotroski_score')}/9", "quality score"),
    ]

    valuation_table = pd.DataFrame(
        [
            ["Quote currency", quote_currency],
            ["Financial statement currency", financial_currency],
            ["DCF price comparison", "available" if dcf_comparable else "not available: currency mismatch"],
            ["Trailing P/E", f"{safe_float(ratios.get('trailing_pe')):.2f}" if not np.isnan(safe_float(ratios.get("trailing_pe"))) else "n/a"],
            ["Forward P/E", f"{safe_float(ratios.get('forward_pe')):.2f}" if not np.isnan(safe_float(ratios.get("forward_pe"))) else "n/a"],
            ["PEG", f"{safe_float(ratios.get('peg')):.2f}" if not np.isnan(safe_float(ratios.get("peg"))) else "n/a"],
            ["Price / Sales", f"{safe_float(ratios.get('price_to_sales')):.2f}" if not np.isnan(safe_float(ratios.get("price_to_sales"))) else "n/a"],
            ["Price / Book", f"{safe_float(ratios.get('price_to_book')):.2f}" if not np.isnan(safe_float(ratios.get("price_to_book"))) else "n/a"],
            ["EV / Revenue", f"{safe_float(ratios.get('ev_to_revenue')):.2f}" if not np.isnan(safe_float(ratios.get("ev_to_revenue"))) else "n/a"],
            ["EV / EBITDA", f"{safe_float(ratios.get('ev_to_ebitda')):.2f}" if not np.isnan(safe_float(ratios.get("ev_to_ebitda"))) else "n/a"],
            ["DCF discount rate", pct(valuation.get("wacc_proxy"))],
            ["DCF growth assumption", pct(valuation.get("base_growth"))],
        ],
        columns=["Metric", "Value"],
    )

    quality_table = pd.DataFrame(
        [
            ["Statement currency", financial_currency],
            ["Revenue", human_number(ratios.get("revenue"))],
            ["Net income", human_number(ratios.get("net_income"))],
            ["Free cash flow", human_number(ratios.get("free_cash_flow"))],
            ["Gross margin", pct(ratios.get("gross_margin"))],
            ["Operating margin", pct(ratios.get("operating_margin"))],
            ["Net margin", pct(ratios.get("net_margin"))],
            ["ROE", pct(ratios.get("roe"))],
            ["ROA", pct(ratios.get("roa"))],
            ["Debt / Equity", f"{safe_float(ratios.get('debt_to_equity')):.2f}" if not np.isnan(safe_float(ratios.get("debt_to_equity"))) else "n/a"],
            ["Current ratio", f"{safe_float(ratios.get('current_ratio')):.2f}" if not np.isnan(safe_float(ratios.get("current_ratio"))) else "n/a"],
        ],
        columns=["Metric", "Value"],
    )

    risk_table = pd.DataFrame(
        [
            ["Annualized return", pct(risk.get("annual_return"))],
            ["Annualized volatility", pct(risk.get("annual_volatility"))],
            ["Sharpe proxy", f"{safe_float(risk.get('sharpe_proxy')):.2f}" if not np.isnan(safe_float(risk.get("sharpe_proxy"))) else "n/a"],
            ["Sortino proxy", f"{safe_float(risk.get('sortino_proxy')):.2f}" if not np.isnan(safe_float(risk.get("sortino_proxy"))) else "n/a"],
            ["Daily 95% VaR", pct(risk.get("daily_var_95"))],
            ["Daily 95% CVaR", pct(risk.get("daily_cvar_95"))],
            ["Skew", f"{safe_float(risk.get('skew')):.2f}" if not np.isnan(safe_float(risk.get("skew"))) else "n/a"],
            ["Excess kurtosis", f"{safe_float(risk.get('excess_kurtosis')):.2f}" if not np.isnan(safe_float(risk.get("excess_kurtosis"))) else "n/a"],
        ],
        columns=["Metric", "Value"],
    )

    logo_svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="180" height="180" viewBox="0 0 180 180">
      <defs>
        <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stop-color="#38bdf8"/>
          <stop offset="50%" stop-color="#22c55e"/>
          <stop offset="100%" stop-color="#f59e0b"/>
        </linearGradient>
      </defs>
      <rect width="180" height="180" rx="32" fill="#020617"/>
      <path d="M28 126 L58 92 L82 105 L122 52 L154 75" fill="none" stroke="url(#g)" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="122" cy="52" r="9" fill="#f8fafc"/>
      <text x="28" y="154" fill="#e2e8f0" font-family="Arial" font-size="24" font-weight="700">{ticker[:5]}</text>
    </svg>
    """
    logo_data = base64.b64encode(logo_svg.encode()).decode()
    company_html = escape(str(company))
    ticker_html = escape(ticker)
    ir_url_html = escape(ir_url)
    ir_label_html = escape(ir_label)

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{ticker} Stock Analysis</title>
  <style>
    :root {{
      --bg: #030712;
      --panel: #0f172a;
      --panel-2: #111827;
      --text: #e5e7eb;
      --muted: #94a3b8;
      --line: rgba(148, 163, 184, .22);
      --green: #22c55e;
      --blue: #38bdf8;
      --amber: #f59e0b;
      --red: #ef4444;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 15% 0%, rgba(56, 189, 248, .18), transparent 28rem),
        radial-gradient(circle at 85% 10%, rgba(34, 197, 94, .14), transparent 30rem),
        linear-gradient(180deg, #020617 0%, #030712 45%, #050816 100%);
    }}
    main {{ width: min(1480px, calc(100% - 48px)); margin: 0 auto; padding: 36px 0 84px; }}
    .hero {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 28px;
      align-items: center;
      padding: 34px;
      border: 1px solid var(--line);
      border-radius: 24px;
      background: linear-gradient(135deg, rgba(15,23,42,.92), rgba(17,24,39,.72));
      box-shadow: 0 24px 90px rgba(0,0,0,.34);
    }}
    .hero h1 {{ font-size: clamp(36px, 6vw, 78px); line-height: .94; margin: 0 0 14px; letter-spacing: 0; }}
    .hero p {{ color: var(--muted); font-size: 17px; max-width: 850px; margin: 0; }}
    .logo {{ width: 150px; height: 150px; border-radius: 28px; box-shadow: 0 20px 70px rgba(56,189,248,.22); }}
    .tag-row {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; }}
    .tag {{ border: 1px solid var(--line); color: #cbd5e1; padding: 6px 10px; border-radius: 999px; font-size: 13px; background: rgba(15,23,42,.72); }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin: 26px 0; }}
    .metric {{ padding: 20px; border: 1px solid var(--line); border-radius: 18px; background: rgba(15,23,42,.78); min-height: 118px; }}
    .metric small {{ display: block; color: var(--muted); margin-bottom: 10px; }}
    .metric strong {{ display: block; font-size: 26px; line-height: 1.1; }}
    .metric span {{ display: block; color: #cbd5e1; margin-top: 8px; font-size: 13px; }}
    section {{ margin-top: 32px; padding: 30px; border: 1px solid var(--line); border-radius: 22px; background: rgba(15,23,42,.70); }}
    h2 {{ margin: 0 0 16px; font-size: 25px; }}
    h3 {{ margin: 24px 0 10px; font-size: 19px; color: #e2e8f0; }}
    .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 22px; }}
    .company-overview-grid {{ display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(320px, .6fr); gap: 24px; align-items: start; }}
    .company-intro p {{ font-size: 16px; }}
    .specialty-tags {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }}
    .specialty-tag {{ display: inline-flex; align-items: center; min-height: 32px; padding: 7px 11px; border: 1px solid rgba(56,189,248,.28); border-radius: 999px; color: #dbeafe; background: rgba(14,165,233,.10); font-size: 13px; }}
    .profile-card {{ padding: 20px; border: 1px solid rgba(148,163,184,.18); border-radius: 18px; background: rgba(2,6,23,.34); }}
    .profile-card h3 {{ margin-top: 0; }}
    .profile-facts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .profile-fact {{ padding: 12px; border: 1px solid rgba(148,163,184,.14); border-radius: 12px; background: rgba(15,23,42,.58); }}
    .profile-fact small {{ display: block; color: var(--muted); margin-bottom: 5px; }}
    .profile-fact strong {{ display: block; color: #e2e8f0; font-size: 14px; line-height: 1.25; }}
    .profile-link-row {{ display: grid; grid-template-columns: 110px minmax(0, 1fr); gap: 10px; margin: 14px 0 0; color: #cbd5e1; overflow-wrap: anywhere; }}
    .profile-link-row span {{ color: var(--muted); }}
    .profile-link-row a {{ color: #93c5fd; }}
    .data-notes {{ border-color: rgba(245,158,11,.36); background: rgba(120,53,15,.18); }}
    .data-notes ul {{ margin: 0; padding-left: 20px; color: #fde68a; line-height: 1.55; }}
    .data-notes li + li {{ margin-top: 8px; }}
    .statement-stack {{ display: grid; gap: 28px; margin-top: 24px; }}
    .statement-panel {{ padding: 24px; border: 1px solid rgba(148,163,184,.18); border-radius: 18px; background: rgba(2,6,23,.34); }}
    .statement-heading {{ display: flex; justify-content: space-between; gap: 22px; align-items: end; margin-bottom: 16px; }}
    .statement-heading h3 {{ margin: 0; }}
    .statement-heading .muted {{ max-width: 620px; margin: 0; text-align: right; }}
    .narrative {{ color: #dbe4ef; line-height: 1.65; }}
    .narrative p {{ margin: 0 0 12px; }}
    .company-link {{ color: inherit; text-decoration: none; border-bottom: 1px solid rgba(56,189,248,.55); }}
    .company-link:hover {{ color: #bfdbfe; }}
    .table-scroll {{ overflow-x: auto; border-radius: 14px; border: 1px solid rgba(148,163,184,.16); margin-top: 18px; }}
    .data-table {{ width: 100%; border-collapse: collapse; overflow: hidden; border-radius: 12px; }}
    .table-scroll .data-table {{ min-width: 760px; }}
    .data-table th, .data-table td {{ padding: 14px 16px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; line-height: 1.35; }}
    .data-table th:first-child, .data-table td:first-child {{ width: 34%; min-width: 230px; }}
    .data-table th {{ color: #e2e8f0; background: rgba(30,41,59,.92); }}
    .data-table td {{ color: #cbd5e1; }}
    .statement-unit-note {{ margin: 16px 0 0; padding: 12px 14px; border: 1px solid rgba(56,189,248,.22); border-radius: 12px; color: #cbd5e1; background: rgba(14,165,233,.08); }}
    .financial-statement-table {{ width: 100%; min-width: 820px; border-collapse: collapse; font-variant-numeric: tabular-nums; }}
    .financial-statement-table th,
    .financial-statement-table td {{ padding: 12px 16px; border-bottom: 1px solid rgba(148,163,184,.16); line-height: 1.3; }}
    .financial-statement-table thead th {{ position: sticky; top: 0; z-index: 1; color: #e2e8f0; background: #1e293b; }}
    .financial-statement-table .line-item {{ width: 42%; min-width: 300px; text-align: left; }}
    .financial-statement-table .number-cell {{ text-align: right; white-space: nowrap; }}
    .financial-statement-table .fs-section-row td {{ padding: 12px 16px 9px; border-top: 1px solid rgba(148,163,184,.28); border-bottom: 1px solid rgba(148,163,184,.28); color: #bfdbfe; background: rgba(30,41,59,.68); font-size: 12px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }}
    .financial-statement-table .fs-indent-1 .line-item {{ padding-left: 34px; color: #b6c2d2; }}
    .financial-statement-table .fs-major .line-item,
    .financial-statement-table .fs-major .number-cell {{ font-weight: 700; color: #e2e8f0; }}
    .financial-statement-table .fs-subtotal td {{ border-top: 1px solid rgba(226,232,240,.32); font-weight: 700; color: #e2e8f0; }}
    .financial-statement-table .fs-total td {{ border-top: 2px solid rgba(226,232,240,.45); font-weight: 800; color: #f8fafc; }}
    .financial-statement-table .fs-grand-total td {{ border-top: 2px solid rgba(56,189,248,.65); border-bottom: 3px double rgba(226,232,240,.45); font-weight: 900; color: #f8fafc; background: rgba(14,165,233,.06); }}
    .financial-statement-table .negative {{ color: #fca5a5; }}
    .muted {{ color: var(--muted); }}
    .chart-wrap {{ overflow: hidden; border-radius: 18px; border: 1px solid var(--line); background: #020617; }}
    .chart-wrap-spacious {{ margin-top: 12px; }}
    footer {{ color: var(--muted); margin-top: 26px; line-height: 1.6; font-size: 13px; }}
    @media (max-width: 980px) {{
      .hero {{ grid-template-columns: 1fr; }}
      .logo {{ width: 110px; height: 110px; }}
      .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .grid-2 {{ grid-template-columns: 1fr; }}
      .company-overview-grid {{ grid-template-columns: 1fr; }}
      .statement-heading {{ display: block; }}
      .statement-heading .muted {{ max-width: none; text-align: left; margin-top: 8px; }}
    }}
    @media (max-width: 560px) {{
      main {{ width: min(100% - 24px, 1440px); padding-top: 14px; }}
      .hero, section {{ padding: 18px; border-radius: 16px; }}
      .statement-panel {{ padding: 16px; }}
      .metrics {{ grid-template-columns: 1fr; }}
      .metric strong {{ font-size: 22px; }}
    }}
  </style>
</head>
<body>
  <main>
    <div class="hero">
      <div>
        <div class="tag-row">
          <span class="tag">Generated {datetime.now().strftime("%Y-%m-%d %H:%M")}</span>
          <span class="tag">Period {config.period}</span>
          <span class="tag">Interval {config.interval}</span>
          <span class="tag">Quote currency {quote_currency}</span>
          <span class="tag">Financials {financial_currency}</span>
        </div>
        <h1><a class="company-link" href="{ir_url_html}" target="_blank" rel="noopener noreferrer" title="{ir_label_html}">{company_html}</a><br><span style="color:#38bdf8">{ticker_html}</span></h1>
        <p>Institutional-style research dashboard combining financial statement quality, valuation theory, price trend structure, volatility, drawdown, and scenario analysis.</p>
      </div>
      <img class="logo" src="data:image/svg+xml;base64,{logo_data}" alt="{ticker} report mark">
    </div>

    <div class="metrics">
      {''.join(metrics)}
    </div>

    {company_overview}

    {data_notes_section}

    <section>
      <h2>Executive View</h2>
      <div class="narrative">
        <p>{fund["quality"]} {fund["score"]}</p>
        <p>{fund["valuation"]}</p>
        <p>{tech["trend"]} {tech["macd"]} {tech["oscillator"]} {tech["strength"]} {tech["bollinger"]} {tech["range"]}</p>
        <p>Future movement is best treated as a distribution rather than a point forecast: valuation anchors long-run expected return, while liquidity, sentiment, and trend define the path. The most useful confirmation comes when fundamentals and price action point in the same direction.</p>
      </div>
    </section>

    <section>
      <h2>Technical Structure</h2>
      <div class="chart-wrap">{technical_html}</div>
    </section>

    {annual_statements_html}

    <section>
      <h2>Fundamental and Valuation Dashboard</h2>
      <div class="grid-2">
        <div>
          <h3>Valuation</h3>
          {df_to_html_table(valuation_table)}
        </div>
        <div>
          <h3>Quality and Balance Sheet</h3>
          {df_to_html_table(quality_table)}
        </div>
      </div>
    </section>

    <section>
      <h2>Risk and Historical Behavior</h2>
      <div class="chart-wrap">{risk_html}</div>
      <h3>Risk metrics</h3>
      {df_to_html_table(risk_table)}
    </section>

    <section>
      <h2>Forward Scenarios</h2>
      {df_to_html_table(scenarios)}
      <h3>Simulated price cone</h3>
      <div class="chart-wrap">{monte_carlo_html}</div>
      <p class="muted">Monte Carlo paths use historical daily log-return drift and volatility. This is a statistical stress map, not a prediction engine; it does not model regime shifts, jumps, dilution, litigation, macro shocks, or management changes.</p>
    </section>

    <footer>
      This report is for research and education only and is not investment advice. Data comes from Yahoo Finance through yfinance and may be delayed, incomplete, restated, or unavailable for some securities. The DCF is a simplified equity-value proxy based on available free cash flow, share count, beta, and growth assumptions.
    </footer>
  </main>
</body>
</html>"""

    output_dir = Path("reports")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{safe_output_filename(ticker)}_stock_analysis.html"
    output_path.write_text(html, encoding="utf-8")
    return output_path


def parse_args() -> ReportConfig:
    parser = argparse.ArgumentParser(description="Generate a full scale stock analysis HTML report.")
    parser.add_argument("--ticker", default=DEFAULT_TICKER, help="Ticker symbol, e.g. AAPL, MSFT, NVDA.")
    parser.add_argument("--period", default=DEFAULT_PERIOD, help="Price history period supported by yfinance, e.g. 1y, 5y, 10y, max.")
    parser.add_argument("--interval", default=DEFAULT_INTERVAL, help="Price interval supported by yfinance, e.g. 1d, 1wk.")
    parser.add_argument("--risk-free-rate", type=float, default=0.045, help="Risk-free rate used in DCF/CAPM proxy.")
    parser.add_argument("--market-return", type=float, default=0.085, help="Expected market return used in DCF/CAPM proxy.")
    parser.add_argument("--terminal-growth", type=float, default=0.025, help="Terminal growth rate for simplified DCF.")
    args = parser.parse_args()
    return ReportConfig(
        ticker=args.ticker.strip().upper(),
        period=args.period,
        interval=args.interval,
        risk_free_rate=args.risk_free_rate,
        market_return=args.market_return,
        terminal_growth=args.terminal_growth,
    )


def main() -> None:
    config = parse_args()
    try:
        print(f"Fetching data for {config.ticker}...")
        data = fetch_data(config)
        print("Building report...")
        output_path = build_report(config, data)
    except Exception as exc:
        message = str(exc)
        print("\nCould not build the report.", file=sys.stderr)
        print(f"Ticker attempted: {config.ticker}", file=sys.stderr)
        if "Could not resolve host" in message or "DNSError" in message:
            print(
                "Reason: Yahoo Finance could not be reached. Check your internet "
                "connection, VPN/firewall, or try again later.",
                file=sys.stderr,
            )
        elif "No price history returned" in message:
            print(
                "Reason: no price history came back for this ticker. For German "
                "listings, try the Yahoo suffix, for example SAP.DE instead of SAP.",
                file=sys.stderr,
            )
        else:
            print(f"Reason: {message}", file=sys.stderr)
            print(
                "Tip: verify the ticker on Yahoo Finance. Examples: SAP for the "
                "US ADR, SAP.DE for the German Xetra listing.",
                file=sys.stderr,
            )
        raise SystemExit(1) from exc

    print(f"Report written to: {output_path.resolve()}")


if __name__ == "__main__":
    main()
