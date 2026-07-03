"""Plain-English interpretation of technicals, fundamentals, and scenarios."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from stockanalysis.utils import latest, money, pct, safe_float


def technical_read(df: pd.DataFrame, currency: str) -> dict[str, str]:
    close     = latest(df["Close"])
    sma_20    = latest(df["SMA_20"])
    sma_50    = latest(df["SMA_50"])
    sma_200   = latest(df["SMA_200"])
    rsi       = latest(df["RSI_14"])
    macd      = latest(df["MACD"])
    macd_sig  = latest(df["MACD_Signal"])
    adx       = latest(df["ADX_14"])
    atr       = latest(df["ATR_14"])
    bb_upper  = latest(df["BB_Upper"])
    bb_lower  = latest(df["BB_Lower"])

    trend_parts = []
    if any(np.isnan(v) for v in (close, sma_50, sma_200)):
        trend_parts.append("long-term trend is unavailable because the selected history is too short or incomplete")
    elif close > sma_200 and sma_50 > sma_200:
        trend_parts.append("primary uptrend: price and 50-day average are above the 200-day average")
    elif close < sma_200 and sma_50 < sma_200:
        trend_parts.append("primary downtrend: price and 50-day average are below the 200-day average")
    else:
        trend_parts.append("transitional trend: moving averages are not aligned")

    if any(np.isnan(v) for v in (close, sma_20, sma_50)):
        trend_parts.append("short-term momentum is unavailable")
    elif close > sma_20 > sma_50:
        trend_parts.append("short-term momentum is constructive")
    elif close < sma_20 < sma_50:
        trend_parts.append("short-term momentum is weak")
    else:
        trend_parts.append("short-term momentum is mixed")

    oscillator = (
        "RSI is unavailable." if np.isnan(rsi)
        else "RSI is overbought; trend can persist, but upside risk/reward is less asymmetric." if rsi >= 70
        else "RSI is oversold; mean-reversion probability is elevated if fundamentals are intact." if rsi <= 30
        else "RSI is neutral, so price action is not at a classic oscillator extreme."
    )
    macd_text = (
        "MACD is unavailable." if np.isnan(macd) or np.isnan(macd_sig)
        else "MACD is above signal, showing positive momentum." if macd > macd_sig
        else "MACD is below signal, showing fading momentum."
    )
    trend_strength = (
        "ADX is unavailable." if np.isnan(adx)
        else "ADX indicates a strong directional regime." if adx >= 25
        else "ADX indicates a weaker or range-bound directional regime."
    )
    range_text = (
        "ATR band unavailable." if np.isnan(close) or np.isnan(atr)
        else f"One ATR ≈ {money(atr, currency)}, band {money(close - atr, currency)}–{money(close + atr, currency)}."
    )
    bollinger = (
        "Bollinger position unavailable." if any(np.isnan(v) for v in (close, bb_upper, bb_lower))
        else "Price is pressing the upper Bollinger Band." if close >= bb_upper
        else "Price is pressing the lower Bollinger Band." if close <= bb_lower
        else "Price sits inside its Bollinger envelope."
    )

    return {
        "trend": "; ".join(trend_parts) + ".",
        "oscillator": oscillator, "macd": macd_text,
        "strength": trend_strength, "range": range_text, "bollinger": bollinger,
    }


def fundamental_read(
    ratios: dict[str, Any], valuation: dict[str, Any],
    quote_currency: str, financial_currency: str,
) -> dict[str, str]:
    roe             = safe_float(ratios.get("roe"))
    d2e             = safe_float(ratios.get("debt_to_equity"))
    rev_growth      = safe_float(ratios.get("revenue_growth"))
    fair_value      = safe_float(valuation.get("fair_value"))
    price           = safe_float(ratios.get("price"))
    piotroski       = ratios.get("piotroski_score")
    comparable      = bool(valuation.get("comparable_to_price"))

    quality = []
    quality.append("unavailable return-on-equity" if np.isnan(roe)
        else "high return on equity" if roe >= 0.18
        else "acceptable return on equity" if roe >= 0.10
        else "modest return on equity")
    quality.append("unavailable leverage data" if np.isnan(d2e)
        else "conservative leverage" if d2e < 0.8
        else "meaningful leverage" if d2e < 2.0
        else "high leverage")
    quality.append("unavailable revenue-growth data" if np.isnan(rev_growth)
        else "positive revenue growth" if rev_growth > 0
        else "contracting revenue" if rev_growth < 0
        else "flat revenue growth")

    valuation_text = "DCF could not be estimated (free cash flow or share count unavailable)."
    if not np.isnan(fair_value) and not comparable:
        valuation_text = (
            f"DCF fair value is {money(fair_value, financial_currency)} in the financial statement currency "
            f"({financial_currency}), not compared with the quoted price ({quote_currency})."
        )
    elif not np.isnan(fair_value) and not np.isnan(price) and price > 0:
        gap = fair_value / price - 1
        stance = ("undervalued" if gap > 0.15 else "overvalued" if gap < -0.15 else "roughly fairly valued")
        valuation_text = (
            f"DCF fair value {money(fair_value, quote_currency)} vs price {money(price, quote_currency)}, "
            f"implying {pct(gap)} ({stance} under base assumptions)."
        )

    score_text = (
        "Piotroski F-score unavailable." if piotroski is None
        else f"Piotroski F-score {piotroski}/9."
    )
    return {
        "quality": "The business profile shows " + ", ".join(quality) + ".",
        "valuation": valuation_text, "score": score_text,
    }


def scenario_table(
    df: pd.DataFrame,
    valuation: dict[str, Any], currency: str,
) -> pd.DataFrame:
    last_price   = latest(df["Close"])
    atr          = latest(df["ATR_14"])
    sma_200      = latest(df["SMA_200"])
    fair_value   = safe_float(valuation.get("fair_value"))
    comparable   = bool(valuation.get("comparable_to_price"))
    annual_vol   = df["Return"].dropna().std() * np.sqrt(252)
    vol_move     = last_price * annual_vol if not np.isnan(last_price) and not np.isnan(annual_vol) else np.nan
    bull_ref     = last_price + vol_move * 0.5 if not np.isnan(vol_move) else last_price
    base_ref     = fair_value if comparable and not np.isnan(fair_value) else last_price
    if comparable and not np.isnan(fair_value) and not np.isnan(bull_ref):
        bull_ref = max(bull_ref, fair_value)
    bear_ref = min(sma_200, last_price - 2 * atr) if not np.isnan(sma_200) and not np.isnan(atr) else last_price

    return pd.DataFrame([
        {"Scenario": "Bull case",
         "Trigger": "Price holds above rising 50/200-day averages; earnings revisions improve.",
         "Reference Level": money(bull_ref, currency),
         "Interpretation": "Momentum and fundamentals align; valuation can re-rate."},
        {"Scenario": "Base case",
         "Trigger": "Price mean-reverts around trend while fundamentals evolve near consensus.",
         "Reference Level": money(base_ref, currency),
         "Interpretation": "Expected return depends on earnings delivery and multiple stability."},
        {"Scenario": "Bear case",
         "Trigger": "Break below 200-day trend or margin/balance-sheet deterioration.",
         "Reference Level": money(bear_ref, currency),
         "Interpretation": "Technical damage can amplify fundamental disappointment."},
    ])
