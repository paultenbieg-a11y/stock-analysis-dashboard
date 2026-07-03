"""HTML fragment builders for the report (cards, tables, sections)."""

from __future__ import annotations

import re
from html import escape
from typing import Any
from urllib.parse import quote_plus

import numpy as np
import pandas as pd

from stockanalysis.config import IR_URL_OVERRIDES
from stockanalysis.fundamentals import get_statement_value_for_period
from stockanalysis.peers import PEER_METRICS
from stockanalysis.report import charts
from stockanalysis.utils import (
    compact_text,
    human_number,
    pct,
    ratio_fmt,
    safe_float,
)


# ---------------------------------------------------------------------------
# Layout primitives
# ---------------------------------------------------------------------------

def metric_card(label: str, value: str, detail: str = "", tone: str = "") -> str:
    cls = f" class='{tone}'" if tone in ("up", "down") else ""
    detail_html = f"<span{cls}>{escape(detail)}</span>" if detail else ""
    return (
        f"<div class='metric'><small>{escape(label)}</small>"
        f"<strong>{escape(value)}</strong>{detail_html}</div>"
    )


def section_html(sec_id: str, index: int, title: str, body: str, lead: str = "") -> str:
    lead_html = f"<p class='section-lead'>{lead}</p>" if lead else ""
    return f"""
    <section id="{escape(sec_id)}">
      <div class="section-head">
        <span class="section-index">{index:02d}</span>
        <h2>{escape(title)}</h2>
      </div>
      {lead_html}
      {body}
    </section>"""


def panel(inner: str, padded: bool = True) -> str:
    pad = " panel-pad" if padded else ""
    return f"<div class='panel{pad}'>{inner}</div>"


def df_to_html_table(df: pd.DataFrame, classes: str = "data-table") -> str:
    return df.to_html(index=False, classes=classes, border=0, escape=False)


def kv_table(rows: list[list[str]], headers: tuple[str, str] = ("Metric", "Value")) -> str:
    head = f"<thead><tr><th>{escape(headers[0])}</th><th class='num'>{escape(headers[1])}</th></tr></thead>"
    body = "".join(
        f"<tr><td>{escape(str(k))}</td><td class='num'>{escape(str(v))}</td></tr>"
        for k, v in rows
    )
    return f"<div class='table-scroll'><table class='data-table'>{head}<tbody>{body}</tbody></table></div>"


# ---------------------------------------------------------------------------
# Financial statement tables
# ---------------------------------------------------------------------------

def statement_section(label: str) -> dict[str, Any]:
    return {"type": "section", "label": label}


def statement_line(
    label: str, aliases: list[str], kind: str = "currency",
    role: str = "normal", indent: int = 0,
) -> dict[str, Any]:
    return {"type": "line", "label": label, "aliases": aliases,
            "kind": kind, "role": role, "indent": indent}


INCOME_STATEMENT_ROWS = [
    statement_section("Revenue and gross profit"),
    statement_line("Total revenue",                 ["Total Revenue", "Operating Revenue"],                                              role="major"),
    statement_line("Cost of revenue",               ["Cost Of Revenue", "Reconciled Cost Of Revenue"],                                  indent=1),
    statement_line("Gross profit",                  ["Gross Profit"],                                                                   role="subtotal"),
    statement_section("Operating expenses and profit"),
    statement_line("Research and development",      ["Research And Development"],                                                        indent=1),
    statement_line("Selling, general and admin",    ["Selling General And Administration", "General And Administrative Expense"],        indent=1),
    statement_line("Total operating expenses",      ["Operating Expense", "Total Expenses"],                                            role="subtotal"),
    statement_line("Operating income / EBIT",       ["Operating Income", "Total Operating Income As Reported", "EBIT"],                 role="total"),
    statement_line("EBITDA",                        ["EBITDA", "Normalized EBITDA"],                                                    role="major"),
    statement_section("Below operating line"),
    statement_line("Interest income",               ["Interest Income", "Interest Income Non Operating"],                               indent=1),
    statement_line("Interest expense",              ["Interest Expense", "Interest Expense Non Operating"],                             indent=1),
    statement_line("Pretax income",                 ["Pretax Income"],                                                                  role="subtotal"),
    statement_line("Tax provision",                 ["Tax Provision"],                                                                  indent=1),
    statement_line("Net income",                    ["Net Income", "Net Income Common Stockholders"],                                   role="grand-total"),
    statement_section("Per-share and share data"),
    statement_line("Diluted EPS",                   ["Diluted EPS"],                                                                    kind="eps", role="major"),
    statement_line("Diluted average shares",        ["Diluted Average Shares"],                                                         kind="shares"),
]

BALANCE_SHEET_ROWS = [
    statement_section("Assets"),
    statement_line("Cash and short-term investments", ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"], indent=1),
    statement_line("Receivables",                   ["Receivables", "Accounts Receivable", "Net Receivables"],                         indent=1),
    statement_line("Inventory",                     ["Inventory"],                                                                     indent=1),
    statement_line("Current assets",                ["Current Assets", "Total Current Assets"],                                        role="subtotal"),
    statement_line("Goodwill and intangibles",      ["Goodwill And Other Intangible Assets", "Goodwill", "Other Intangible Assets"],    indent=1),
    statement_line("Property, plant and equipment", ["Net PPE", "Property Plant Equipment"],                                           indent=1),
    statement_line("Total assets",                  ["Total Assets"],                                                                   role="grand-total"),
    statement_section("Liabilities"),
    statement_line("Current liabilities",           ["Current Liabilities", "Total Current Liabilities"],                              role="subtotal"),
    statement_line("Total debt",                    ["Total Debt"],                                                                     indent=1),
    statement_line("Net debt",                      ["Net Debt"],                                                                      indent=1),
    statement_line("Total liabilities",             ["Total Liabilities Net Minority Interest", "Total Liab"],                         role="grand-total"),
    statement_section("Equity and capitalization"),
    statement_line("Shareholders equity",           ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"], role="grand-total"),
    statement_line("Minority interest",             ["Minority Interest"],                                                             indent=1),
    statement_line("Working capital",               ["Working Capital"],                                                               role="subtotal"),
    statement_line("Invested capital",              ["Invested Capital"],                                                              role="subtotal"),
    statement_line("Shares issued",                 ["Share Issued", "Ordinary Shares Number"],                                        kind="shares"),
]

CASH_FLOW_ROWS = [
    statement_section("Operating activities"),
    statement_line("Net income from continuing ops", ["Net Income From Continuing Operations", "Net Income"],                          role="major"),
    statement_line("Depreciation and amortization",  ["Depreciation And Amortization", "Depreciation Amortization Depletion"],        indent=1),
    statement_line("Stock-based compensation",        ["Stock Based Compensation"],                                                   indent=1),
    statement_line("Change in working capital",       ["Change In Working Capital"],                                                  indent=1),
    statement_line("Operating cash flow",             ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],      role="grand-total"),
    statement_section("Investing activities"),
    statement_line("Capital expenditure",             ["Capital Expenditure", "Capital Expenditures"],                                indent=1),
    statement_line("Free cash flow",                  ["Free Cash Flow"],                                                             role="grand-total"),
    statement_line("Investing cash flow",             ["Investing Cash Flow", "Cash Flow From Continuing Investing Activities"],      role="subtotal"),
    statement_line("Business acquisitions/disposals", ["Net Business Purchase And Sale", "Purchase Of Business", "Sale Of Business"], indent=1),
    statement_line("Investment purchases/sales",      ["Net Investment Purchase And Sale"],                                           indent=1),
    statement_section("Financing activities"),
    statement_line("Financing cash flow",             ["Financing Cash Flow", "Cash Flow From Continuing Financing Activities"],     role="subtotal"),
    statement_line("Dividends paid",                  ["Cash Dividends Paid", "Common Stock Dividend Paid"],                         indent=1),
    statement_line("Share repurchases",               ["Repurchase Of Capital Stock", "Common Stock Payments"],                      indent=1),
    statement_line("Debt issued",                     ["Issuance Of Debt", "Long Term Debt Issuance"],                               indent=1),
    statement_line("Debt repaid",                     ["Repayment Of Debt", "Long Term Debt Payments"],                              indent=1),
    statement_section("Cash reconciliation"),
    statement_line("Change in cash",                  ["Changes In Cash"],                                                           role="subtotal"),
    statement_line("Ending cash position",            ["End Cash Position"],                                                         role="grand-total"),
]


def period_label(period: Any) -> str:
    try:
        return pd.to_datetime(period).strftime("%Y")
    except Exception:
        return str(period)


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
    statement: pd.DataFrame, row_defs: list[dict[str, Any]], max_years: int = 3
) -> str:
    if statement is None or statement.empty:
        return "<p class='muted'>Annual statement data was not returned for this ticker.</p>"
    periods = list(statement.columns[:max_years])
    headers = "".join(
        f"<th class='number-cell'>{escape(period_label(p))}</th>" for p in periods
    )
    body_rows = []
    for rd in row_defs:
        if rd["type"] == "section":
            body_rows.append(
                f"<tr class='fs-section-row'><td colspan='{len(periods)+1}'>{escape(rd['label'])}</td></tr>"
            )
            continue
        role, indent = rd.get("role", "normal"), int(rd.get("indent", 0))
        classes = ["fs-line-row", f"fs-{role}", f"fs-indent-{indent}"]
        vals = []
        for p in periods:
            v   = get_statement_value_for_period(statement, rd["aliases"], p)
            fmt = format_statement_value(v, rd.get("kind", "currency"))
            vc  = "negative" if safe_float(v) < 0 else ""
            vals.append(f"<td class='number-cell {vc}'>{escape(fmt)}</td>")
        body_rows.append(
            f"<tr class='{' '.join(classes)}'>"
            f"<td class='line-item'>{escape(rd['label'])}</td>{''.join(vals)}</tr>"
        )
    return (
        f"<table class='financial-statement-table'>"
        f"<thead><tr><th class='line-item'>Line item</th>{headers}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table>"
    )


def annual_statement_body_html(
    financials: dict[str, pd.DataFrame], currency: str
) -> str:
    from stockanalysis.report import theme

    income   = financials.get("income",   pd.DataFrame())
    balance  = financials.get("balance",  pd.DataFrame())
    cashflow = financials.get("cashflow", pd.DataFrame())

    it = finance_statement_table_html(income,   INCOME_STATEMENT_ROWS)
    bt = finance_statement_table_html(balance,  BALANCE_SHEET_ROWS)
    ct = finance_statement_table_html(cashflow, CASH_FLOW_ROWS)

    getter = get_statement_value_for_period
    ic = charts.annual_statement_chart(income, [
        ("Revenue",          ["Total Revenue", "Operating Revenue"],                              theme.ACCENT),
        ("Gross profit",     ["Gross Profit"],                                                    theme.GREEN),
        ("Operating income", ["Operating Income", "Total Operating Income As Reported", "EBIT"],  theme.GOLD),
        ("Net income",       ["Net Income", "Net Income Common Stockholders"],                    theme.PURPLE),
    ], currency, getter)
    bc = charts.annual_statement_chart(balance, [
        ("Assets",            ["Total Assets"],                                                   theme.ACCENT),
        ("Equity",            ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"], theme.PURPLE),
        ("Debt",              ["Total Debt"],                                                     theme.RED),
        ("Cash & ST invest.", ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"], theme.GREEN),
    ], currency, getter)
    cc = charts.annual_statement_chart(cashflow, [
        ("Operating CF",   ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"], theme.TEAL),
        ("Capex",          ["Capital Expenditure", "Capital Expenditures"],                           theme.RED),
        ("Free cash flow", ["Free Cash Flow"],                                                        theme.GOLD),
        ("Dividends paid", ["Cash Dividends Paid", "Common Stock Dividend Paid"],                     theme.PURPLE),
    ], currency, getter)

    def _block(h3: str, desc: str, chart: str, table: str) -> str:
        return f"""
          <div class="statement-panel">
            <div class="statement-heading">
              <h3>{escape(h3)}</h3>
              <p class="muted">{escape(desc)}</p>
            </div>
            {panel(chart)}
            <div class="table-scroll">{table}</div>
          </div>"""

    return f"""
        <p class="statement-unit-note">Figures in <strong>{escape(currency)}</strong>.
           EPS in {escape(currency)} per share; share counts as shares.
           Most recent annual release plus the previous two periods, independent of the
           selected price-chart period.</p>
        <div class="statement-stack">
          {_block("Income Statement", "Revenue scale, profitability, and earnings power.", ic, it)}
          {_block("Balance Sheet",    "Capital structure, asset base, and liquidity.", bc, bt)}
          {_block("Cash Flow",        "Cash conversion, reinvestment, and financing.", cc, ct)}
        </div>"""


# ---------------------------------------------------------------------------
# Earnings section
# ---------------------------------------------------------------------------

def _naive(ts: Any) -> pd.Timestamp | None:
    try:
        t = pd.Timestamp(ts)
        if pd.isna(t):
            return None
        return t.tz_localize(None) if t.tzinfo is not None else t
    except Exception:
        return None


def next_earnings_summary(earnings: dict[str, Any]) -> tuple[str, str]:
    """(card value, card detail) for the next scheduled earnings date."""
    next_date = _naive(earnings.get("next_date")) if earnings else None
    if next_date is None:
        return "n/a", "no date announced"
    days = (next_date.normalize() - pd.Timestamp.now().normalize()).days
    if days < 0:
        return next_date.strftime("%Y-%m-%d"), "recently reported"
    if days == 0:
        return "Today", next_date.strftime("%Y-%m-%d")
    return f"{days} days", next_date.strftime("%Y-%m-%d")


def past_earnings_dates(earnings: dict[str, Any], start: Any, end: Any) -> list[str]:
    """Reported earnings dates inside [start, end] as YYYY-MM-DD strings."""
    history = earnings.get("history") if earnings else None
    if history is None or getattr(history, "empty", True):
        return []
    if "Reported EPS" in history.columns:
        history = history.dropna(subset=["Reported EPS"])
    lo, hi = _naive(start), _naive(end)
    out = []
    for ts in history.index:
        t = _naive(ts)
        if t is None:
            continue
        if (lo is None or t >= lo) and (hi is None or t <= hi):
            out.append(t.strftime("%Y-%m-%d"))
    return sorted(set(out))


def earnings_table_html(earnings: dict[str, Any]) -> str:
    history = earnings.get("history") if earnings else None
    if history is None or getattr(history, "empty", True):
        return "<p class='muted'>Earnings history unavailable for this ticker.</p>"
    cols = set(history.columns)
    if not {"EPS Estimate", "Reported EPS"}.issubset(cols):
        return "<p class='muted'>Earnings history unavailable for this ticker.</p>"
    past = history.dropna(subset=["Reported EPS"]).sort_index(ascending=False).head(8)
    if past.empty:
        return "<p class='muted'>No reported earnings inside the available window.</p>"

    rows = []
    for ts, row in past.iterrows():
        t   = _naive(ts)
        est = safe_float(row.get("EPS Estimate"))
        act = safe_float(row.get("Reported EPS"))
        if not np.isnan(est) and not np.isnan(act) and est != 0:
            surprise = (act - est) / abs(est)
            cls  = "up-text" if surprise >= 0 else "down-text"
            sur  = f"<span class='{cls}'>{surprise * 100:+.1f}%</span>"
        else:
            sur = "n/a"
        rows.append(
            f"<tr><td>{t.strftime('%Y-%m-%d') if t is not None else escape(str(ts))}</td>"
            f"<td class='num'>{ratio_fmt(est)}</td>"
            f"<td class='num'>{ratio_fmt(act)}</td>"
            f"<td class='num'>{sur}</td></tr>"
        )
    return (
        "<div class='table-scroll'><table class='data-table'>"
        "<thead><tr><th>Reported</th><th class='num'>EPS estimate</th>"
        "<th class='num'>Reported EPS</th><th class='num'>Surprise</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


# ---------------------------------------------------------------------------
# Peer comparison
# ---------------------------------------------------------------------------

def peer_table_html(frame: pd.DataFrame, subject_symbol: str) -> str:
    if frame.empty:
        return "<p class='muted'>No peer data available.</p>"

    def _fmt(value: float, kind: str) -> str:
        value = safe_float(value)
        if np.isnan(value):
            return "n/a"
        if kind == "x":
            return f"{value:.1f}x"
        if kind == "pct":
            return pct(value, 1)
        return f"{value:.2f}"

    heads = "".join(f"<th class='num'>{escape(label)}</th>" for _, label, _, _ in PEER_METRICS)
    body = []
    for _, row in frame.iterrows():
        sym = str(row.get("symbol", ""))
        cls = " class='peer-subject'" if sym == subject_symbol else ""
        cells = "".join(
            f"<td class='num'>{_fmt(row.get(key), kind)}</td>"
            for key, _, kind, _ in PEER_METRICS
        )
        body.append(
            f"<tr{cls}><td><b>{escape(sym)}</b></td>"
            f"<td>{escape(compact_text(row.get('name'))[:28])}</td>"
            f"<td class='num'>{human_number(row.get('market_cap'))}</td>{cells}</tr>"
        )
    return (
        "<div class='table-scroll'><table class='data-table'>"
        "<thead><tr><th>Ticker</th><th>Name</th><th class='num'>Mkt cap</th>"
        f"{heads}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


# ---------------------------------------------------------------------------
# Company overview / misc
# ---------------------------------------------------------------------------

def investor_relations_target(
    info: dict[str, Any], ticker: str, company: str
) -> tuple[str, str]:
    normalized = ticker.upper()
    if normalized in IR_URL_OVERRIDES:
        return IR_URL_OVERRIDES[normalized], "Investor relations"
    for key in ("irWebsite", "investorRelationsWebsite", "investorRelationsUrl"):
        v = info.get(key)
        if isinstance(v, str) and v.startswith(("http://", "https://")):
            return v, "Investor relations"
    website = info.get("website")
    if isinstance(website, str) and website.startswith(("http://", "https://")):
        return website, "Corporate website"
    return f"https://www.google.com/search?q={quote_plus(company + ' investor relations')}", "IR search"


def summary_sentences(summary: str, max_sentences: int = 4) -> str:
    summary = compact_text(summary)
    if not summary:
        return ""
    sentences, selected = re.split(r"(?<=[.!?])\s+", summary), []
    for s in sentences:
        if s := s.strip():
            selected.append(s)
        if len(selected) >= max_sentences:
            break
    return " ".join(selected)


def profile_fact(label: str, value: Any) -> str:
    value = compact_text(value) or "n/a"
    return (
        f"<div class='profile-fact'>"
        f"<small>{escape(label)}</small>"
        f"<strong>{escape(value)}</strong></div>"
    )


def employee_count(value: Any) -> str:
    v = safe_float(value)
    return "" if np.isnan(v) else f"{v:,.0f}"


def specialization_tags(info: dict[str, Any]) -> list[str]:
    sector   = compact_text(info.get("sector"))
    industry = compact_text(info.get("industry"))
    summary  = compact_text(info.get("longBusinessSummary")).lower()
    tags: list[str] = []
    for v in (sector, industry):
        if v and v not in tags:
            tags.append(v)
    for kw, lbl in [
        ("cloud","Cloud"),("software","Software"),("artificial intelligence","AI"),
        ("machine learning","Machine learning"),("semiconductor","Semiconductors"),
        ("electric vehicle","Electric vehicles"),("automotive","Automotive"),
        ("energy storage","Energy storage"),("solar","Solar"),("payments","Payments"),
        ("e-commerce","E-commerce"),("advertising","Advertising"),("streaming","Streaming"),
        ("cybersecurity","Cybersecurity"),("pharmaceutical","Pharmaceuticals"),
        ("biotechnology","Biotechnology"),("medical","Medical technology"),
        ("banking","Banking"),("insurance","Insurance"),("retail","Retail"),
        ("aerospace","Aerospace"),("industrial","Industrials"),("consumer","Consumer"),
        ("renewable","Renewables"),
    ]:
        if kw in summary and lbl not in tags:
            tags.append(lbl)
        if len(tags) >= 8:
            break
    return tags[:8]


def company_overview_body_html(
    info: dict[str, Any], ticker: str, company: str, ir_url: str, ir_label: str
) -> str:
    summary = summary_sentences(info.get("longBusinessSummary"), 4) or (
        "Yahoo Finance did not return a full business description for this ticker."
    )
    city    = compact_text(info.get("city"))
    state   = compact_text(info.get("state"))
    country = compact_text(info.get("country"))
    hq      = ", ".join(p for p in (city, state, country) if p)
    ws      = compact_text(info.get("website"))
    ws_url  = ws if ws.startswith(("http://", "https://")) else ""
    exchange  = compact_text(info.get("exchange") or info.get("fullExchangeName"))
    qt        = compact_text(info.get("quoteType"))
    employees = employee_count(info.get("fullTimeEmployees"))
    tags      = specialization_tags(info)
    tag_html  = "".join(f"<span class='specialty-tag'>{escape(t)}</span>" for t in tags) \
        or "<span class='specialty-tag'>Profile data limited</span>"
    facts = [
        profile_fact("Sector",        info.get("sector")),
        profile_fact("Industry",      info.get("industry")),
        profile_fact("Headquarters",  hq),
        profile_fact("Employees",     employees),
        profile_fact("Exchange",      exchange),
        profile_fact("Security type", qt),
    ]
    ws_html = (
        f"<a href='{escape(ws_url)}' target='_blank' rel='noopener noreferrer'>{escape(ws_url)}</a>"
        if ws_url else "n/a"
    )
    return f"""
        <div class="company-overview-grid">
          <div class="narrative company-intro">
            <p><b>{escape(company)}</b> ({escape(ticker)}) — {escape(compact_text(info.get("sector")) or "n/a")} / {escape(compact_text(info.get("industry")) or "n/a")}.</p>
            <p>{escape(summary)}</p>
            <div class="specialty-tags">{tag_html}</div>
          </div>
          <aside class="profile-card">
            <h3>Profile</h3>
            <div class="profile-facts">{''.join(facts)}</div>
            <p class="profile-link-row"><span>Website</span>{ws_html}</p>
            <p class="profile-link-row"><span>{escape(ir_label)}</span>
               <a href="{escape(ir_url)}" target="_blank" rel="noopener noreferrer">{escape(company)}</a></p>
          </aside>
        </div>"""


def data_notes_html(notes: list[str]) -> str:
    clean, seen = [], set()
    for n in notes:
        t = compact_text(n)
        if t and t not in seen:
            clean.append(t)
            seen.add(t)
    if not clean:
        return ""
    items = "".join(f"<li>{escape(n)}</li>" for n in clean)
    return f"<div class='data-notes'><h2>Data Notes</h2><ul>{items}</ul></div>"


def topbar_html(ticker: str, company: str, price_str: str, nav_items: list[tuple[str, str]]) -> str:
    links = "".join(f"<a href='#{escape(sid)}'>{escape(label)}</a>" for sid, label in nav_items)
    return f"""
  <div class="topbar"><div class="topbar-inner">
    <div class="brand"><span class="tk">{escape(ticker)}</span>
      <span class="nm">· {escape(company)}</span>
      <span class="px">· {escape(price_str)}</span></div>
    <nav>{links}</nav>
  </div></div>"""
