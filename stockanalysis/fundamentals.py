"""Financial statement parsing, fundamental ratios, and the Piotroski score."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from stockanalysis.utils import clean_currency, safe_float, same_currency


def get_statement_value(
    statement: pd.DataFrame, possible_names: list[str], period: int = 0
) -> float:
    if statement is None or statement.empty:
        return np.nan
    index_map = {str(idx).lower(): idx for idx in statement.index}
    for name in possible_names:
        key = name.lower()
        if key in index_map and statement.shape[1] > period:
            return safe_float(statement.loc[index_map[key]].iloc[period])
    return np.nan


def get_statement_value_for_period(
    statement: pd.DataFrame, possible_names: list[str], period: Any
) -> float:
    if statement is None or statement.empty:
        return np.nan
    try:
        if period not in statement.columns:
            return np.nan
    except (TypeError, KeyError):
        return np.nan
    index_map = {str(idx).lower(): idx for idx in statement.index}
    for name in possible_names:
        if name.lower() in index_map:
            try:
                return safe_float(statement.loc[index_map[name.lower()], period])
            except Exception:
                return np.nan
    return np.nan


def calculate_fundamentals(
    info: dict[str, Any], financials: dict[str, pd.DataFrame]
) -> dict[str, Any]:
    income   = financials.get("income",   pd.DataFrame())
    balance  = financials.get("balance",  pd.DataFrame())
    cashflow = financials.get("cashflow", pd.DataFrame())

    quote_currency     = clean_currency(info.get("currency"))
    financial_currency = clean_currency(info.get("financialCurrency"), quote_currency)
    currencies_comparable = same_currency(quote_currency, financial_currency)

    market_cap       = safe_float(info.get("marketCap"))
    enterprise_value = safe_float(info.get("enterpriseValue"))
    price            = safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
    shares           = safe_float(info.get("sharesOutstanding"))
    beta             = safe_float(info.get("beta"), 1.0)

    revenue          = get_statement_value(income,   ["Total Revenue", "Operating Revenue"])
    gross_profit     = get_statement_value(income,   ["Gross Profit"])
    operating_income = get_statement_value(income,   ["Operating Income"])
    net_income       = get_statement_value(income,   ["Net Income", "Net Income Common Stockholders"])
    ebitda           = get_statement_value(income,   ["EBITDA", "Normalized EBITDA"])
    total_assets     = get_statement_value(balance,  ["Total Assets"])
    total_equity     = get_statement_value(balance,  ["Stockholders Equity", "Total Equity Gross Minority Interest"])
    total_debt       = get_statement_value(balance,  ["Total Debt", "Net Debt"])
    cash             = get_statement_value(balance,  ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"])
    current_assets   = get_statement_value(balance,  ["Current Assets", "Total Current Assets"])
    current_liab     = get_statement_value(balance,  ["Current Liabilities", "Total Current Liabilities"])
    op_cash_flow     = get_statement_value(cashflow, ["Operating Cash Flow", "Total Cash From Operating Activities"])
    capex            = get_statement_value(cashflow, ["Capital Expenditure", "Capital Expenditures"])
    free_cash_flow   = safe_float(info.get("freeCashflow"))
    if np.isnan(free_cash_flow):
        free_cash_flow = op_cash_flow + capex if not np.isnan(op_cash_flow + capex) else np.nan

    revenue_prev      = get_statement_value(income,  ["Total Revenue", "Operating Revenue"], 1)
    net_income_prev   = get_statement_value(income,  ["Net Income", "Net Income Common Stockholders"], 1)
    total_assets_prev = get_statement_value(balance, ["Total Assets"], 1)
    cur_assets_prev   = get_statement_value(balance, ["Current Assets", "Total Current Assets"], 1)
    cur_liab_prev     = get_statement_value(balance, ["Current Liabilities", "Total Current Liabilities"], 1)
    shares_prev       = get_statement_value(balance, ["Ordinary Shares Number", "Share Issued"], 1)

    gross_margin      = gross_profit     / revenue      if revenue      else np.nan
    operating_margin  = operating_income / revenue      if revenue      else np.nan
    net_margin        = net_income       / revenue      if revenue      else np.nan
    roe               = net_income       / total_equity if total_equity else np.nan
    roa               = net_income       / total_assets if total_assets else np.nan
    debt_to_equity    = total_debt       / total_equity if total_equity else np.nan
    current_ratio     = current_assets   / current_liab if current_liab else np.nan
    revenue_growth    = (revenue / revenue_prev - 1)       if revenue_prev    else np.nan
    earnings_growth   = (net_income / net_income_prev - 1) if net_income_prev else np.nan
    asset_turnover    = revenue / total_assets if total_assets else np.nan
    equity_multiplier = total_assets / total_equity if total_equity else np.nan

    ratios: dict[str, Any] = {
        "price": price, "market_cap": market_cap, "enterprise_value": enterprise_value,
        "shares": shares, "beta": beta,
        "trailing_pe":     safe_float(info.get("trailingPE")),
        "forward_pe":      safe_float(info.get("forwardPE")),
        "peg":             safe_float(info.get("pegRatio")),
        "price_to_book":   safe_float(info.get("priceToBook")),
        "price_to_sales":  safe_float(info.get("priceToSalesTrailing12Months")),
        "quote_currency":  quote_currency,
        "financial_currency": financial_currency,
        "currencies_comparable": currencies_comparable,
        "ev_to_revenue":  enterprise_value / revenue if currencies_comparable and revenue  else np.nan,
        "ev_to_ebitda":   enterprise_value / ebitda  if currencies_comparable and ebitda   else np.nan,
        "fcf_yield":      free_cash_flow / market_cap if currencies_comparable and market_cap else np.nan,
        "earnings_yield": net_income     / market_cap if currencies_comparable and market_cap else np.nan,
        "gross_margin": gross_margin, "operating_margin": operating_margin,
        "net_margin": net_margin, "roe": roe, "roa": roa,
        "debt_to_equity": debt_to_equity, "current_ratio": current_ratio,
        "revenue_growth": revenue_growth, "earnings_growth": earnings_growth,
        "asset_turnover": asset_turnover, "equity_multiplier": equity_multiplier,
        "free_cash_flow": free_cash_flow, "revenue": revenue,
        "net_income": net_income, "cash": cash, "debt": total_debt,
    }

    ratios["piotroski_score"] = piotroski_score(
        ratios=ratios, income=income, balance=balance, cashflow=cashflow,
        total_assets_prev=total_assets_prev,
        current_assets_prev=cur_assets_prev,
        current_liabilities_prev=cur_liab_prev,
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

    score      = 0
    roa        = ratios.get("roa", np.nan)
    ocf        = ratios.get("free_cash_flow", np.nan)
    net_income = ratios.get("net_income", np.nan)
    total_assets  = get_statement_value(balance, ["Total Assets"])
    total_debt    = get_statement_value(balance, ["Total Debt", "Net Debt"])
    total_debt_p  = get_statement_value(balance, ["Total Debt", "Net Debt"], 1)
    cur_assets    = get_statement_value(balance, ["Current Assets", "Total Current Assets"])
    cur_liab      = get_statement_value(balance, ["Current Liabilities", "Total Current Liabilities"])
    gross_margin  = ratios.get("gross_margin", np.nan)
    revenue       = ratios.get("revenue", np.nan)
    revenue_prev  = get_statement_value(income, ["Total Revenue", "Operating Revenue"], 1)
    gp_prev       = get_statement_value(income, ["Gross Profit"], 1)
    shares        = get_statement_value(balance, ["Ordinary Shares Number", "Share Issued"])

    roa_prev      = (
        get_statement_value(income, ["Net Income", "Net Income Common Stockholders"], 1) / total_assets_prev
        if total_assets_prev else np.nan
    )
    leverage      = total_debt / total_assets if total_assets else np.nan
    leverage_prev = total_debt_p / total_assets_prev if total_assets_prev else np.nan
    cr            = cur_assets / cur_liab if cur_liab else np.nan
    cr_prev       = current_assets_prev / current_liabilities_prev if current_liabilities_prev else np.nan
    gm_prev       = gp_prev / revenue_prev if revenue_prev else np.nan
    at            = revenue / total_assets if total_assets else np.nan
    at_prev       = revenue_prev / total_assets_prev if total_assets_prev else np.nan

    tests = [
        roa > 0, ocf > 0, roa > roa_prev, ocf > net_income,
        leverage < leverage_prev, cr > cr_prev,
        shares <= shares_prev if not np.isnan(shares_prev) else False,
        gross_margin > gm_prev, at > at_prev,
    ]
    for passed in tests:
        if bool(passed) and not pd.isna(passed):
            score += 1
    return score
