"""WACC estimation, DCF valuation, sensitivity analysis, reverse DCF, tornado."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from stockanalysis.config import ReportConfig
from stockanalysis.fundamentals import get_statement_value
from stockanalysis.utils import clean_currency, safe_float


def compute_wacc(
    ratios: dict[str, Any],
    config: ReportConfig,
    income: pd.DataFrame,
) -> dict[str, Any]:
    beta       = safe_float(ratios.get("beta"), 1.0)
    market_cap = safe_float(ratios.get("market_cap"))
    total_debt = safe_float(ratios.get("debt"))

    coe = config.risk_free_rate + beta * (config.market_return - config.risk_free_rate)
    coe = float(np.clip(coe, 0.06, 0.18))

    no_debt = np.isnan(total_debt) or total_debt <= 0 or np.isnan(market_cap) or market_cap <= 0
    if no_debt:
        wacc = float(np.clip(coe, 0.07, 0.14))
        return {
            "wacc": wacc, "cost_of_equity": coe,
            "cost_of_debt_pretax": np.nan, "after_tax_cost_of_debt": np.nan,
            "equity_weight": 1.0, "debt_weight": 0.0,
            "tax_rate": np.nan, "method": "cost of equity only (no debt)",
        }

    # Cost of debt: interest expense / total debt
    int_exp = abs(safe_float(get_statement_value(
        income, ["Interest Expense", "Interest Expense Non Operating"]
    )))
    if not np.isnan(int_exp) and int_exp > 0:
        cod = float(np.clip(int_exp / total_debt, 0.01, 0.15))
    else:
        cod = float(np.clip(config.risk_free_rate + 0.02, 0.03, 0.12))

    # Effective tax rate
    tax    = safe_float(get_statement_value(income, ["Tax Provision"]))
    pretax = safe_float(get_statement_value(income, ["Pretax Income"]))
    if not np.isnan(tax) and not np.isnan(pretax) and pretax > 0:
        tax_rate = float(np.clip(abs(tax) / pretax, 0.05, 0.40))
    else:
        tax_rate = 0.21

    total_cap = market_cap + total_debt
    eq_w      = market_cap / total_cap
    dbt_w     = total_debt / total_cap
    atcod     = cod * (1 - tax_rate)
    wacc      = float(np.clip(coe * eq_w + atcod * dbt_w, 0.06, 0.16))

    return {
        "wacc": wacc, "cost_of_equity": coe,
        "cost_of_debt_pretax": cod, "after_tax_cost_of_debt": atcod,
        "equity_weight": eq_w, "debt_weight": dbt_w,
        "tax_rate": tax_rate, "method": "WACC",
    }


def derive_base_growth(ratios: dict[str, Any]) -> float:
    """Blend revenue growth, earnings growth, and a normalized anchor."""
    revenue_growth  = safe_float(ratios.get("revenue_growth"),  0.03)
    earnings_growth = safe_float(ratios.get("earnings_growth"), revenue_growth)
    return float(np.clip(np.nanmedian([revenue_growth, earnings_growth, 0.06]), -0.05, 0.15))


def project_fair_value(
    fcf: float,
    shares: float,
    base_growth: float,
    discount_rate: float,
    terminal_growth: float,
    forecast_years: int = 5,
) -> float:
    """Core DCF: fading-growth explicit period plus Gordon terminal value.

    Growth fades linearly from base_growth toward roughly a third of it by the
    final explicit year. Returns fair value per share, or nan on bad inputs.
    """
    if any(np.isnan(v) for v in (fcf, shares, base_growth, discount_rate, terminal_growth)):
        return np.nan
    if fcf <= 0 or shares <= 0 or discount_rate <= 0:
        return np.nan
    terminal_growth = min(terminal_growth, discount_rate - 0.01)

    pv, current_fcf = 0.0, fcf
    for yr in range(1, forecast_years + 1):
        g = base_growth * (1 - (yr - 1) / (forecast_years * 1.5))
        current_fcf *= 1 + g
        pv += current_fcf / (1 + discount_rate) ** yr

    tv = (current_fcf * (1 + terminal_growth)) / (discount_rate - terminal_growth)
    return (pv + tv / (1 + discount_rate) ** forecast_years) / shares


def dcf_valuation(
    ratios: dict[str, Any], config: ReportConfig, wacc_details: dict[str, Any]
) -> dict[str, Any]:
    fcf    = safe_float(ratios.get("free_cash_flow"))
    shares = safe_float(ratios.get("shares"))
    quote_currency     = clean_currency(ratios.get("quote_currency"))
    financial_currency = clean_currency(ratios.get("financial_currency"), quote_currency)
    currencies_comparable = bool(ratios.get("currencies_comparable"))

    empty = {
        "fair_value": np.nan, "discount_rate": np.nan, "base_growth": np.nan,
        "terminal_growth": np.nan,
        "quote_currency": quote_currency, "financial_currency": financial_currency,
        "comparable_to_price": currencies_comparable,
    }
    if np.isnan(fcf) or fcf <= 0 or np.isnan(shares) or shares <= 0:
        return empty

    base_growth   = derive_base_growth(ratios)
    discount_rate = wacc_details.get("wacc", float(np.clip(
        config.risk_free_rate + safe_float(ratios.get("beta"), 1.0) * (config.market_return - config.risk_free_rate),
        0.07, 0.14,
    )))
    terminal_growth = min(config.terminal_growth, discount_rate - 0.01)

    fair_val = project_fair_value(
        fcf, shares, base_growth, discount_rate, terminal_growth, config.forecast_years
    )

    return {
        "fair_value": fair_val,
        "discount_rate": discount_rate,
        "base_growth": base_growth,
        "terminal_growth": terminal_growth,
        "quote_currency": quote_currency,
        "financial_currency": financial_currency,
        "comparable_to_price": currencies_comparable,
    }


def dcf_sensitivity(
    ratios: dict[str, Any], config: ReportConfig, wacc_details: dict[str, Any]
) -> pd.DataFrame:
    """Fair value across a WACC × terminal-growth grid.

    Index holds discount rates, columns hold terminal growth rates (as raw
    floats); cells where the spread would be below 1.5pp are nan.
    """
    fcf    = safe_float(ratios.get("free_cash_flow"))
    shares = safe_float(ratios.get("shares"))
    if np.isnan(fcf) or fcf <= 0 or np.isnan(shares) or shares <= 0:
        return pd.DataFrame()

    base_growth = derive_base_growth(ratios)
    dr0 = safe_float(wacc_details.get("wacc"), 0.09)
    tg0 = config.terminal_growth
    drs = [round(dr0 + o, 4) for o in (-0.02, -0.01, 0.0, 0.01, 0.02)]
    tgs = [round(max(0.0, tg0 + o), 4) for o in (-0.01, -0.005, 0.0, 0.005, 0.01)]

    grid = [
        [
            project_fair_value(fcf, shares, base_growth, dr, tg, config.forecast_years)
            if dr - tg >= 0.015 and dr > 0 else np.nan
            for tg in tgs
        ]
        for dr in drs
    ]
    return pd.DataFrame(grid, index=drs, columns=tgs)


def reverse_dcf(
    ratios: dict[str, Any],
    config: ReportConfig,
    wacc_details: dict[str, Any],
    price: float,
) -> float:
    """Initial FCF growth (with the model's fade) implied by the current price.

    Solves project_fair_value(g) = price by bisection over g in [-50%, +60%];
    fair value is monotonically increasing in g. Returns nan when the price
    cannot be reproduced inside that range or inputs are missing.
    """
    fcf    = safe_float(ratios.get("free_cash_flow"))
    shares = safe_float(ratios.get("shares"))
    price  = safe_float(price)
    if np.isnan(fcf) or fcf <= 0 or np.isnan(shares) or shares <= 0 or np.isnan(price) or price <= 0:
        return np.nan

    dr = safe_float(wacc_details.get("wacc"), 0.09)
    tg = min(config.terminal_growth, dr - 0.01)

    def gap(g: float) -> float:
        return project_fair_value(fcf, shares, g, dr, tg, config.forecast_years) - price

    lo, hi = -0.50, 0.60
    gap_lo, gap_hi = gap(lo), gap(hi)
    if np.isnan(gap_lo) or np.isnan(gap_hi) or gap_lo * gap_hi > 0:
        return np.nan
    for _ in range(60):
        mid = (lo + hi) / 2
        gap_mid = gap(mid)
        if np.isnan(gap_mid):
            return np.nan
        if gap_lo * gap_mid <= 0:
            hi = mid
        else:
            lo, gap_lo = mid, gap_mid
    return (lo + hi) / 2


def dcf_tornado(
    ratios: dict[str, Any], config: ReportConfig, wacc_details: dict[str, Any]
) -> list[dict[str, Any]]:
    """Fair-value range per input driver, sorted by impact (widest first)."""
    fcf    = safe_float(ratios.get("free_cash_flow"))
    shares = safe_float(ratios.get("shares"))
    if np.isnan(fcf) or fcf <= 0 or np.isnan(shares) or shares <= 0:
        return []

    g  = derive_base_growth(ratios)
    dr = safe_float(wacc_details.get("wacc"), 0.09)
    tg = min(config.terminal_growth, dr - 0.01)
    n  = config.forecast_years

    def value(fcf_=None, g_=None, dr_=None, tg_=None) -> float:
        return project_fair_value(
            fcf if fcf_ is None else fcf_,
            shares,
            g if g_ is None else g_,
            dr if dr_ is None else dr_,
            tg if tg_ is None else tg_,
            n,
        )

    base = value()
    if np.isnan(base):
        return []

    candidates = [
        ("Free cash flow ±10%",     value(fcf_=fcf * 0.9),   value(fcf_=fcf * 1.1)),
        ("Initial growth ±2pp",     value(g_=g - 0.02),      value(g_=g + 0.02)),
        ("Discount rate ±1pp",      value(dr_=dr + 0.01),    value(dr_=max(dr - 0.01, tg + 0.015))),
        ("Terminal growth ±0.5pp",  value(tg_=tg - 0.005),   value(tg_=min(tg + 0.005, dr - 0.015))),
    ]
    drivers = []
    for label, a, b in candidates:
        if np.isnan(a) or np.isnan(b):
            continue
        low, high = (a, b) if a <= b else (b, a)
        drivers.append({"driver": label, "low": low, "high": high, "base": base})
    drivers.sort(key=lambda d: d["high"] - d["low"], reverse=True)
    return drivers
