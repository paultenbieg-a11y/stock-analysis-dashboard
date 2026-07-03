"""Assemble the full HTML research report from a fetched data bundle."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from stockanalysis.config import ReportConfig
from stockanalysis.data import snapshot_from_info
from stockanalysis.fundamentals import calculate_fundamentals
from stockanalysis.indicators import add_technical_indicators
from stockanalysis.narrative import fundamental_read, scenario_table, technical_read
from stockanalysis.peers import build_peer_frame, positioning_text
from stockanalysis.report import charts, components as c, theme
from stockanalysis.risk import monte_carlo, risk_metrics
from stockanalysis.utils import (
    clean_currency,
    human_number,
    latest,
    money,
    pct,
    ratio_fmt,
    safe_float,
    safe_output_filename,
    same_currency,
)
from stockanalysis.valuation import (
    compute_wacc,
    dcf_sensitivity,
    dcf_tornado,
    dcf_valuation,
    reverse_dcf,
)


def build_report(
    config: ReportConfig, data: dict[str, Any], output_dir: Path = Path("reports")
) -> Path:
    info = data["info"]
    df   = add_technical_indicators(data["history"]).dropna(subset=["Close"])
    if df.empty:
        raise RuntimeError("Price history did not contain valid closing prices.")

    ratios        = calculate_fundamentals(info, data["financials"])
    wacc_details  = compute_wacc(ratios, config, data["financials"].get("income", pd.DataFrame()))
    valuation     = dcf_valuation(ratios, config, wacc_details)
    benchmark_df  = data.get("benchmark_df")
    benchmark_sym = data.get("benchmark_sym", config.benchmark_ticker)
    risk          = risk_metrics(df, config, benchmark_df)
    impl_vol      = safe_float(data.get("impl_vol"))
    earnings      = data.get("earnings") or {}
    peer_rows     = data.get("peers") or []

    ticker     = config.ticker.upper()
    company    = info.get("longName") or info.get("shortName") or ticker
    q_currency = clean_currency(ratios.get("quote_currency"))
    f_currency = clean_currency(ratios.get("financial_currency"), q_currency)
    comparable = same_currency(q_currency, f_currency)
    tech       = technical_read(df, q_currency)
    fund       = fundamental_read(ratios, valuation, q_currency, f_currency)
    scenarios  = scenario_table(df, valuation, q_currency)
    paths      = monte_carlo(df, config)
    ir_url, ir_label = c.investor_relations_target(info, ticker, company)

    # --- headline numbers ---------------------------------------------------
    last_close = latest(df["Close"])
    ret_series = df["Adj Close"] if "Adj Close" in df.columns else df["Close"]
    ret_clean  = ret_series.dropna()
    period_ret = ret_clean.iloc[-1] / ret_clean.iloc[0] - 1 if len(ret_clean) > 1 else np.nan

    fair_value   = safe_float(valuation.get("fair_value"))
    dcf_comp     = bool(valuation.get("comparable_to_price"))
    dcf_gap      = fair_value / last_close - 1 if dcf_comp and not np.isnan(fair_value) and last_close else np.nan
    dcf_currency = q_currency if dcf_comp else f_currency
    dcf_detail   = f"{pct(dcf_gap)} vs price" if dcf_comp and not np.isnan(dcf_gap) else "not price-comparable"
    dcf_tone     = "" if np.isnan(dcf_gap) else ("up" if dcf_gap > 0 else "down")

    implied_g    = reverse_dcf(ratios, config, wacc_details, last_close if dcf_comp else np.nan)
    sensitivity  = dcf_sensitivity(ratios, config, wacc_details)
    tornado      = dcf_tornado(ratios, config, wacc_details)

    # --- data notes -----------------------------------------------------------
    data_notes = list(data.get("warnings", []))
    if not comparable:
        data_notes.append(
            f"Quote currency is {q_currency}, financial statements in {f_currency}. "
            "Currency-sensitive ratios and DCF price comparison shown cautiously or as n/a."
        )

    # --- metric cards -----------------------------------------------------------
    rel_ret    = safe_float(risk.get("relative_return"))
    ret_detail = (
        f"{config.period} · {pct(rel_ret)} vs {benchmark_sym}"
        if not np.isnan(rel_ret) else f"{config.period} dividend-adjusted"
    )
    vol_detail = f"impl {pct(impl_vol)}" if not np.isnan(impl_vol) else "realized"
    next_val, next_detail = c.next_earnings_summary(earnings)
    piotroski = ratios.get("piotroski_score")

    metrics_html = "".join([
        c.metric_card("Last close",     money(last_close, q_currency),          q_currency),
        c.metric_card("Market cap",     human_number(ratios.get("market_cap")), q_currency),
        c.metric_card("Total return",   pct(period_ret),                        ret_detail,
                      tone="" if np.isnan(rel_ret) else ("up" if rel_ret > 0 else "down")),
        c.metric_card("Annual vol",     pct(risk.get("annual_volatility")),     vol_detail),
        c.metric_card("Max drawdown",   pct(risk.get("max_drawdown")),          "selected period"),
        c.metric_card("DCF fair value", money(fair_value, dcf_currency),        dcf_detail, tone=dcf_tone),
        c.metric_card("Piotroski",      "n/a" if piotroski is None else f"{piotroski}/9", "accounting quality"),
        c.metric_card("Next earnings",  next_val,                               next_detail),
    ])

    # --- dashboard tables ----------------------------------------------------------
    val_rows = [
        ["Quote currency",           q_currency],
        ["Financial stmt currency",  f_currency],
        ["DCF method",               wacc_details.get("method", "cost of equity")],
        ["Cost of equity",           pct(wacc_details.get("cost_of_equity"))],
        ["Cost of debt (after-tax)", pct(wacc_details.get("after_tax_cost_of_debt"))],
        ["Equity / Debt weights",    f"{pct(wacc_details.get('equity_weight'))} / {pct(wacc_details.get('debt_weight'))}"],
        ["WACC / discount rate",     pct(wacc_details.get("wacc"))],
        ["DCF growth assumption",    pct(valuation.get("base_growth"))],
        ["Terminal growth",          pct(valuation.get("terminal_growth"))],
        ["Trailing P/E",   ratio_fmt(ratios.get("trailing_pe"))],
        ["Forward P/E",    ratio_fmt(ratios.get("forward_pe"))],
        ["PEG",            ratio_fmt(ratios.get("peg"))],
        ["Price / Sales",  ratio_fmt(ratios.get("price_to_sales"))],
        ["Price / Book",   ratio_fmt(ratios.get("price_to_book"))],
        ["EV / Revenue",   ratio_fmt(ratios.get("ev_to_revenue"))],
        ["EV / EBITDA",    ratio_fmt(ratios.get("ev_to_ebitda"))],
    ]
    quality_rows = [
        ["Statement currency", f_currency],
        ["Revenue",            human_number(ratios.get("revenue"))],
        ["Net income",         human_number(ratios.get("net_income"))],
        ["Free cash flow",     human_number(ratios.get("free_cash_flow"))],
        ["Gross margin",       pct(ratios.get("gross_margin"))],
        ["Operating margin",   pct(ratios.get("operating_margin"))],
        ["Net margin",         pct(ratios.get("net_margin"))],
        ["ROE",                pct(ratios.get("roe"))],
        ["ROA",                pct(ratios.get("roa"))],
        ["Debt / Equity",      ratio_fmt(ratios.get("debt_to_equity"))],
        ["Current ratio",      ratio_fmt(ratios.get("current_ratio"))],
        ["FCF yield",          pct(ratios.get("fcf_yield"))],
    ]
    risk_rows = [
        ["Annualized return",     pct(risk.get("annual_return"))],
        ["Annualized volatility", pct(risk.get("annual_volatility"))],
        ["Implied volatility",    pct(impl_vol) if not np.isnan(impl_vol) else "n/a (no options data)"],
        ["Sharpe ratio",          ratio_fmt(risk.get("sharpe"))],
        ["Sortino ratio",         ratio_fmt(risk.get("sortino"))],
        ["Daily 95% VaR",         pct(risk.get("daily_var_95"))],
        ["Daily 95% CVaR",        pct(risk.get("daily_cvar_95"))],
        ["Skew",                  ratio_fmt(risk.get("skew"))],
        ["Excess kurtosis",       ratio_fmt(risk.get("excess_kurtosis"))],
    ]
    if "benchmark_annual_return" in risk:
        risk_rows += [
            [f"{benchmark_sym} return", pct(risk.get("benchmark_annual_return"))],
            ["Relative return",         pct(risk.get("relative_return"))],
            ["Tracking error",          pct(risk.get("tracking_error"))],
            ["Information ratio",       ratio_fmt(risk.get("information_ratio"))],
            ["Beta (vs benchmark)",     ratio_fmt(risk.get("actual_beta"))],
            ["Alpha proxy",             pct(risk.get("alpha_proxy"))],
        ]

    # --- executive narrative -----------------------------------------------------
    exec_extra: list[str] = []
    if not np.isnan(implied_g):
        base_g = safe_float(valuation.get("base_growth"))
        exec_extra.append(
            f"Reverse DCF: holding WACC at {pct(wacc_details.get('wacc'))} and terminal growth at "
            f"{pct(valuation.get('terminal_growth'))}, the current price implies roughly "
            f"{pct(implied_g, 1)} initial free-cash-flow growth versus the model's base assumption of "
            f"{pct(base_g, 1)}."
        )
    peer_line = positioning_text(snapshot_from_info(ticker, info), peer_rows) if peer_rows else ""
    if peer_line:
        exec_extra.append(peer_line)
    if next_val not in ("n/a",) and "reported" not in next_detail:
        exec_extra.append(f"Next scheduled earnings: {next_detail} ({next_val} away).")

    executive_body = f"""
      <div class="narrative">
        <p>{fund["quality"]} {fund["score"]}</p>
        <p>{fund["valuation"]}</p>
        <p>{tech["trend"]} {tech["macd"]} {tech["oscillator"]} {tech["strength"]} {tech["bollinger"]} {tech["range"]}</p>
        {''.join(f'<p>{escape(s)}</p>' for s in exec_extra)}
        <p>Future movement is best treated as a distribution rather than a point forecast: valuation
           anchors long-run expected return, while liquidity, sentiment, and trend define the path.</p>
      </div>"""

    # --- earnings & quarterly section ------------------------------------------------
    earnings_dates_in_window = c.past_earnings_dates(
        earnings, df.index.min(), df.index.max()
    )
    quarterly_html = charts.quarterly_chart(
        data.get("quarterly_income", pd.DataFrame()), f_currency, ticker
    )
    earnings_hist_chart = charts.earnings_history_chart(earnings.get("history", pd.DataFrame()))
    earnings_body = f"""
      <h3>Quarterly income trend</h3>
      <p class="muted">Last eight reported quarters — revenue, gross profit, and net income ({escape(f_currency)}).</p>
      {c.panel(quarterly_html)}
      <h3>Earnings vs expectations</h3>
      <p class="muted">Reported EPS against consensus estimates; green bars beat, red bars missed.
         Surprise is computed as (reported − estimate) / |estimate|.</p>
      {c.panel(earnings_hist_chart) if earnings_hist_chart else ''}
      {c.earnings_table_html(earnings)}"""

    # --- valuation section ----------------------------------------------------------
    reverse_callout = ""
    if not np.isnan(implied_g):
        stance = (
            "more optimistic than" if implied_g > safe_float(valuation.get("base_growth")) + 0.005
            else "more conservative than" if implied_g < safe_float(valuation.get("base_growth")) - 0.005
            else "in line with"
        )
        reverse_callout = f"""
      <div class="callout">
        <h3>Reverse DCF — what the price implies</h3>
        <p>At {money(last_close, q_currency)}, the market is pricing in about
           <b>{pct(implied_g, 1)}</b> initial free-cash-flow growth (fading over
           {config.forecast_years} years), given a {pct(wacc_details.get("wacc"))} WACC and
           {pct(valuation.get("terminal_growth"))} terminal growth. That is {stance} the model's
           base growth assumption of <b>{pct(valuation.get("base_growth"), 1)}</b>.
           Asking "is that implied growth plausible?" is usually more robust than
           trusting any single fair-value point estimate.</p>
      </div>"""

    valuation_body = f"""
      <div class="grid-2">
        <div><h3>Valuation and DCF inputs</h3>{c.kv_table(val_rows)}</div>
        <div><h3>Quality and balance sheet</h3>{c.kv_table(quality_rows)}</div>
      </div>
      <h3>Fair-value sensitivity</h3>
      <p class="muted">DCF output across discount-rate and terminal-growth assumptions.
         Wide dispersion is the honest picture: the point estimate above is one cell of this grid.</p>
      {c.panel(charts.sensitivity_heatmap(sensitivity, last_close if dcf_comp else np.nan, dcf_comp, dcf_currency))}
      <h3>What moves the fair value most</h3>
      {c.panel(charts.tornado_chart(tornado, dcf_currency))}
      {reverse_callout}"""

    # --- peer section --------------------------------------------------------------
    peer_section = ""
    if peer_rows:
        subject_row = snapshot_from_info(ticker, info)
        peer_frame  = build_peer_frame(subject_row, peer_rows)
        scatter     = charts.peer_scatter(peer_frame, ticker)
        pos = positioning_text(subject_row, peer_rows)
        peer_section = (
            "<p class='section-lead'>Valuation and quality relative to comparable companies "
            "(Yahoo profile data). Pass --peers SYM1 SYM2 … to override the peer set."
            + (f" {escape(pos)}" if pos else "")
            + "</p>"
            + c.peer_table_html(peer_frame, ticker)
            + (c.panel(scatter) if scatter else "")
        )

    # --- risk & scenarios -----------------------------------------------------------
    risk_body = f"""
      <p class="muted">Returns are dividend-adjusted where data is available. Sharpe and Sortino
         subtract the {pct(config.risk_free_rate)} risk-free-rate assumption.</p>
      {c.panel(charts.risk_chart(df, benchmark_df, benchmark_sym))}
      <h3>Risk metrics</h3>
      {c.kv_table(risk_rows)}"""

    scenario_html = c.df_to_html_table(scenarios)
    scenarios_body = f"""
      <div class="table-scroll">{scenario_html}</div>
      <h3>Simulated one-year price cone</h3>
      <p class="muted">Monte Carlo on historical daily log-return drift and volatility
         ({config.monte_carlo_paths} paths). It does not model regime shifts, jumps, dilution,
         or macro shocks — read it as a volatility map, not a forecast.</p>
      {c.panel(charts.monte_carlo_chart(paths, last_close))}"""

    # --- sections + nav ---------------------------------------------------------------
    sections: list[tuple[str, str, str, str]] = [
        ("overview",   "Overview",   "Company Overview",
         c.company_overview_body_html(info, ticker, company, ir_url, ir_label)),
        ("summary",    "Summary",    "Executive View", executive_body),
        ("earnings",   "Earnings",   "Earnings and Quarterly Trends", earnings_body),
        ("technicals", "Technicals", "Technical Structure",
         c.panel(charts.price_chart(df, ticker, earnings_dates_in_window))
         + ("<p class='muted' style='margin-top:10px'>Dotted gold verticals mark reported earnings dates.</p>"
            if earnings_dates_in_window else "")),
        ("statements", "Statements", "Annual Financial Statements",
         c.annual_statement_body_html(data["financials"], f_currency)),
        ("valuation",  "Valuation",  "Valuation and Fundamentals", valuation_body),
    ]
    if peer_section:
        sections.append(("peers", "Peers", "Peer Comparison", peer_section))
    sections += [
        ("risk",      "Risk",      "Risk and Historical Behaviour", risk_body),
        ("scenarios", "Scenarios", "Forward Scenarios", scenarios_body),
    ]

    nav_items    = [(sid, nav) for sid, nav, _, _ in sections]
    section_html = "".join(
        c.section_html(sid, i + 1, title, body)
        for i, (sid, _, title, body) in enumerate(sections)
    )

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    exchange  = (info.get("fullExchangeName") or info.get("exchange") or "").strip()
    sector    = (info.get("sector") or "n/a").strip()
    industry  = (info.get("industry") or "n/a").strip()

    meta_chips = "".join(
        f"<span class='meta-chip'>{escape(k)} <b>{escape(v)}</b></span>"
        for k, v in [
            ("Period",     config.period),
            ("Benchmark",  benchmark_sym),
            ("Quote",      q_currency),
            ("Financials", f_currency),
            ("WACC",       pct(wacc_details.get("wacc"))),
        ]
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(ticker)} · Equity Research</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="{theme.PLOTLY_CDN}" charset="utf-8"></script>
  <style>{theme.CSS}</style>
</head>
<body>
{c.topbar_html(ticker, str(company), money(last_close, q_currency), nav_items)}
  <main>
    <header class="hero">
      <p class="kicker">Equity research · {generated} · Not investment advice</p>
      <h1><a href="{escape(ir_url)}" target="_blank" rel="noopener noreferrer">{escape(str(company))}</a></h1>
      <p class="subline"><b>{escape(ticker)}</b>{(' · ' + escape(exchange)) if exchange else ''}
         · {escape(sector)} / {escape(industry)}</p>
      <div class="meta-row">{meta_chips}</div>
    </header>

    <div class="metrics">{metrics_html}</div>

    {c.data_notes_html(data_notes)}

    {section_html}

    <footer>
      Research and education only — not investment advice. Data via Yahoo Finance / yfinance;
      it may be delayed, restated, or unavailable. The DCF uses a WACC built from CAPM cost of
      equity, estimated after-tax cost of debt, and market-value weights; sensitivity and
      reverse-DCF views exist because the point estimate is assumption-driven. Peer metrics use
      Yahoo profile fields and can differ from statement-derived figures.
    </footer>
  </main>
</body>
</html>"""

    output_dir.mkdir(exist_ok=True, parents=True)
    output_path = output_dir / f"{safe_output_filename(ticker)}_stock_analysis.html"
    output_path.write_text(html, encoding="utf-8")
    return output_path
