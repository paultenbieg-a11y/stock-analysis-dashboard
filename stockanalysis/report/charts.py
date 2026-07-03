"""All Plotly chart builders, styled through the shared theme."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from stockanalysis.report import theme
from stockanalysis.report.theme import fig_html, plotly_layout, style_axes
from stockanalysis.utils import human_number, pct, safe_float


def _empty_note(text: str) -> str:
    return f"<p class='muted' style='padding:16px'>{text}</p>"


def price_chart(df: pd.DataFrame, ticker: str, earnings_dates: list[str] | None = None) -> str:
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03,
        row_heights=[0.52, 0.16, 0.16, 0.16],
        subplot_titles=("Price, trend, and Bollinger envelope", "Volume", "RSI (14)", "MACD (12/26/9)"),
    )
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="OHLC",
        increasing_line_color=theme.GREEN, decreasing_line_color=theme.RED,
    ), row=1, col=1)
    for col, color in [("SMA_20", theme.TEAL), ("SMA_50", theme.GOLD), ("SMA_200", theme.RED)]:
        fig.add_trace(go.Scatter(x=df.index, y=df[col], name=col.replace("_", " "),
                                 line=dict(width=1.3, color=color)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Upper"], name="BB upper",
                             line=dict(width=1, color="rgba(110,168,254,.30)")), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Lower"], name="BB lower", fill="tonexty",
                             fillcolor="rgba(110,168,254,.05)",
                             line=dict(width=1, color="rgba(110,168,254,.30)")), row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volume",
                         marker_color="rgba(143,163,191,.55)"), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["Volume_SMA_20"], name="Vol SMA 20",
                             line=dict(color=theme.ACCENT, width=1.1)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI_14"], name="RSI 14",
                             line=dict(color=theme.PURPLE, width=1.3)), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color=theme.RED, line_width=1, row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color=theme.GREEN, line_width=1, row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD",
                             line=dict(color=theme.ACCENT, width=1.3)), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD_Signal"], name="Signal",
                             line=dict(color=theme.GOLD, width=1.1)), row=4, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df["MACD_Hist"], name="Histogram",
                         marker_color="rgba(143,163,191,.5)"), row=4, col=1)

    # Earnings-date markers on the price panel
    for d in earnings_dates or []:
        fig.add_vline(x=d, line_dash="dot", line_width=1,
                      line_color="rgba(217,164,65,.55)", row=1, col=1)
    if earnings_dates:
        # invisible trace to give the markers a legend entry
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="lines", name="Earnings date",
            line=dict(color="rgba(217,164,65,.8)", width=1, dash="dot"),
        ), row=1, col=1)

    fig.update_layout(plotly_layout(height=880, xaxis_rangeslider_visible=False))
    fig.update_annotations(font={"size": 12, "color": theme.MUTED})
    style_axes(fig)
    return fig_html(fig)


def risk_chart(
    df: pd.DataFrame,
    benchmark_df: pd.DataFrame | None,
    benchmark_sym: str,
) -> str:
    ret_col    = "AdjReturn" if "AdjReturn" in df.columns else "Return"
    returns    = df[ret_col].dropna()
    cumulative = (1 + returns).cumprod()
    drawdown   = cumulative / cumulative.cummax() - 1
    monthly    = df["Close"].resample("ME").last().pct_change().dropna()

    has_bench = (
        benchmark_df is not None
        and not benchmark_df.empty
        and "Return" in benchmark_df.columns
    )

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            f"Cumulative return{f' vs {benchmark_sym}' if has_bench else ''}",
            "Drawdown",
            "Daily return distribution",
            "Monthly returns",
        ),
    )
    fig.add_trace(go.Scatter(x=cumulative.index, y=cumulative, name="Stock",
                             line=dict(color=theme.GREEN, width=1.8)), row=1, col=1)
    if has_bench:
        bench_ret = benchmark_df["Return"].reindex(returns.index).fillna(0)
        bench_cum = (1 + bench_ret).cumprod()
        fig.add_trace(go.Scatter(x=bench_cum.index, y=bench_cum, name=benchmark_sym,
                                 line=dict(color=theme.GOLD, width=1.3, dash="dash")), row=1, col=1)

    fig.add_trace(go.Scatter(x=drawdown.index, y=drawdown, name="Drawdown", fill="tozeroy",
                             fillcolor="rgba(224,97,109,.16)",
                             line=dict(color=theme.RED, width=1.2)), row=1, col=2)
    fig.add_trace(go.Histogram(x=returns, nbinsx=80, name="Daily returns",
                               marker_color="rgba(110,168,254,.7)"), row=2, col=1)
    fig.add_trace(go.Bar(x=monthly.index, y=monthly, name="Monthly",
                         marker_color=np.where(monthly >= 0, theme.GREEN, theme.RED)), row=2, col=2)

    fig.update_yaxes(tickformat=".0%", row=1, col=2)
    fig.update_yaxes(tickformat=".0%", row=2, col=2)
    fig.update_layout(plotly_layout(height=640, showlegend=has_bench))
    fig.update_annotations(font={"size": 12, "color": theme.MUTED})
    style_axes(fig)
    return fig_html(fig)


def quarterly_chart(
    quarterly_income: pd.DataFrame, currency: str, ticker: str
) -> str:
    if quarterly_income is None or quarterly_income.empty:
        return _empty_note("Quarterly data unavailable for this ticker.")

    periods_raw   = list(quarterly_income.columns[:8])
    chart_periods = list(reversed(periods_raw))
    labels = []
    for p in chart_periods:
        try:
            dt = pd.to_datetime(p)
            q  = (dt.month - 1) // 3 + 1
            labels.append(f"{dt.year} Q{q}")
        except Exception:
            labels.append(str(p))

    index_map = {str(idx).lower(): idx for idx in quarterly_income.index}

    def _vals(names: list[str]) -> list[float | None]:
        for name in names:
            if name.lower() in index_map:
                row = quarterly_income.loc[index_map[name.lower()]]
                out = []
                for p in chart_periods:
                    try:
                        v = safe_float(row[p])
                        out.append(None if np.isnan(v) else v)
                    except Exception:
                        out.append(None)
                return out
        return [None] * len(chart_periods)

    rev_vals = _vals(["Total Revenue", "Operating Revenue"])
    gp_vals  = _vals(["Gross Profit"])
    ni_vals  = _vals(["Net Income", "Net Income Common Stockholders"])

    fig = go.Figure()
    for name, vals, color in [
        ("Revenue",      rev_vals, theme.ACCENT),
        ("Gross profit", gp_vals,  theme.GREEN),
        ("Net income",   ni_vals,  theme.PURPLE),
    ]:
        fig.add_trace(go.Bar(
            x=labels, y=vals, name=name, marker_color=color,
            hovertemplate=f"%{{x}}<br>{name}: %{{y:,.0f}} {currency}<extra></extra>",
        ))
    fig.update_layout(plotly_layout(height=380, barmode="group",
                                    bargap=0.24, bargroupgap=0.08))
    fig.update_xaxes(showgrid=False)
    style_axes(fig)
    return fig_html(fig)


def annual_statement_chart(
    statement: pd.DataFrame,
    series: list[tuple[str, list[str], str]],
    currency: str,
    value_getter: Any,
) -> str:
    if statement is None or statement.empty:
        return _empty_note("Chart unavailable (no annual statement data).")
    periods = list(statement.columns[:3])
    chart_p = list(reversed(periods))

    def _label(p: Any) -> str:
        try:
            return pd.to_datetime(p).strftime("%Y")
        except Exception:
            return str(p)

    years = [_label(p) for p in chart_p]
    fig = go.Figure()
    for name, aliases, color in series:
        vals = [
            (None if np.isnan(v := value_getter(statement, aliases, p)) else v)
            for p in chart_p
        ]
        fig.add_trace(go.Bar(
            x=years, y=vals, name=name, marker_color=color,
            hovertemplate=f"%{{x}}<br>{name}: %{{y:,.0f}} {currency}<extra></extra>",
        ))
    fig.update_layout(plotly_layout(height=380, barmode="group",
                                    bargap=0.24, bargroupgap=0.08))
    fig.update_xaxes(showgrid=False)
    style_axes(fig)
    return fig_html(fig)


def monte_carlo_chart(paths: pd.DataFrame, last_price: float) -> str:
    if paths.empty:
        return _empty_note("Monte Carlo unavailable (insufficient return history).")
    q   = paths.quantile([0.05, 0.25, 0.50, 0.75, 0.95], axis=1).T
    fig = go.Figure()
    sample = paths.iloc[:, : min(40, paths.shape[1])]
    for col in sample.columns:
        fig.add_trace(go.Scatter(x=sample.index, y=sample[col], mode="lines",
                                 line=dict(color="rgba(143,163,191,0.10)", width=1),
                                 showlegend=False, hoverinfo="skip"))
    for level, name, color in [
        (0.95, "95th pct", theme.GREEN), (0.75, "75th pct", theme.ACCENT),
        (0.50, "Median",   theme.INK),   (0.25, "25th pct", theme.GOLD),
        (0.05, "5th pct",  theme.RED),
    ]:
        lw = 2.0 if level == 0.5 else 1.4 if level in (0.05, 0.95) else 1.1
        fig.add_trace(go.Scatter(x=q.index, y=q[level], name=name,
                                 line=dict(color=color, width=lw)))
    fig.add_hline(y=last_price, line_dash="dot", line_color=theme.SLATE, line_width=1,
                  annotation_text="Last close",
                  annotation_font={"size": 11, "color": theme.MUTED})
    fig.update_layout(plotly_layout(height=480))
    style_axes(fig)
    return fig_html(fig)


def sensitivity_heatmap(
    matrix: pd.DataFrame, price: float, comparable: bool, currency: str
) -> str:
    """Fair value across WACC (rows) × terminal growth (columns)."""
    if matrix.empty:
        return _empty_note("Sensitivity unavailable (DCF inputs missing).")

    x_labels = [pct(c, 1) for c in matrix.columns]
    y_labels = [pct(r, 1) for r in matrix.index]
    z = matrix.values.astype(float)
    text = [
        ["" if np.isnan(v) else f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.1f}" for v in row]
        for row in z
    ]

    price = safe_float(price)
    if comparable and not np.isnan(price) and price > 0:
        colorscale = [[0.0, "#8c3a44"], [0.5, "#1a2130"], [1.0, "#2e8b6e"]]
        heat = go.Heatmap(
            z=z, x=x_labels, y=y_labels, text=text, texttemplate="%{text}",
            textfont={"size": 12, "color": theme.INK},
            colorscale=colorscale, zmid=price, showscale=False,
            hovertemplate=("WACC %{y} · terminal growth %{x}"
                           f"<br>Fair value: %{{z:,.2f}} {currency}<extra></extra>"),
            hoverongaps=False,
        )
        subtitle = "green = above current price, red = below"
    else:
        heat = go.Heatmap(
            z=z, x=x_labels, y=y_labels, text=text, texttemplate="%{text}",
            textfont={"size": 12, "color": theme.INK},
            colorscale=[[0.0, "#141926"], [1.0, "#33517e"]], showscale=False,
            hovertemplate=("WACC %{y} · terminal growth %{x}"
                           f"<br>Fair value: %{{z:,.2f}} {currency}<extra></extra>"),
            hoverongaps=False,
        )
        subtitle = "shown in statement currency; not price-comparable"

    fig = go.Figure(heat)
    fig.update_layout(plotly_layout(
        height=380,
        title={"text": f"DCF fair value per share ({currency}) — {subtitle}",
               "font": {"size": 13, "color": theme.MUTED}},
        xaxis_title="Terminal growth", yaxis_title="WACC",
        margin={"l": 70, "r": 24, "t": 56, "b": 48},
    ))
    fig.update_yaxes(autorange="reversed")
    return fig_html(fig)


def tornado_chart(drivers: list[dict[str, Any]], currency: str) -> str:
    """Horizontal fair-value ranges per DCF input driver."""
    if not drivers:
        return _empty_note("Driver sensitivity unavailable (DCF inputs missing).")
    base = drivers[0]["base"]
    labels = [d["driver"] for d in drivers][::-1]
    lows   = [d["low"]  for d in drivers][::-1]
    highs  = [d["high"] for d in drivers][::-1]
    spans  = [h - l for l, h in zip(lows, highs)]

    fig = go.Figure(go.Bar(
        y=labels, x=spans, base=lows, orientation="h",
        marker_color="rgba(110,168,254,.55)",
        marker_line={"color": theme.ACCENT, "width": 1},
        customdata=list(zip(lows, highs)),
        hovertemplate=("%{y}<br>Fair value range: "
                       f"%{{customdata[0]:,.2f}} – %{{customdata[1]:,.2f}} {currency}"
                       "<extra></extra>"),
    ))
    fig.add_vline(x=base, line_dash="dash", line_color=theme.GOLD, line_width=1.2,
                  annotation_text="base case",
                  annotation_font={"size": 11, "color": theme.MUTED})
    fig.update_layout(plotly_layout(
        height=280, showlegend=False,
        xaxis_title=f"Fair value per share ({currency})",
        margin={"l": 160, "r": 24, "t": 30, "b": 44},
    ))
    style_axes(fig)
    fig.update_yaxes(showgrid=False)
    return fig_html(fig)


def peer_scatter(frame: pd.DataFrame, subject_symbol: str) -> str:
    """Revenue growth vs EV/EBITDA, bubble size = market cap."""
    needed = {"revenue_growth", "ev_to_ebitda", "market_cap", "symbol"}
    if frame.empty or not needed.issubset(frame.columns):
        return ""
    d = frame.dropna(subset=["revenue_growth", "ev_to_ebitda"]).copy()
    if len(d) < 3:
        return ""

    caps  = d["market_cap"].fillna(d["market_cap"].median())
    scale = np.sqrt(caps / caps.max()).clip(0.25, 1.0)
    sizes = 14 + scale * 30
    colors = [theme.ACCENT if s == subject_symbol else "rgba(143,163,191,.6)" for s in d["symbol"]]
    line_c = [theme.ACCENT if s == subject_symbol else theme.LINE for s in d["symbol"]]

    fig = go.Figure(go.Scatter(
        x=d["revenue_growth"], y=d["ev_to_ebitda"],
        mode="markers+text", text=d["symbol"], textposition="top center",
        textfont={"size": 11, "color": theme.MUTED},
        marker={"size": sizes, "color": colors, "line": {"color": line_c, "width": 1.2}},
        customdata=np.stack([d["market_cap"].apply(human_number)], axis=-1),
        hovertemplate=("<b>%{text}</b><br>Revenue growth: %{x:.1%}"
                       "<br>EV/EBITDA: %{y:.1f}x<br>Market cap: %{customdata[0]}"
                       "<extra></extra>"),
    ))
    fig.update_layout(plotly_layout(
        height=420, showlegend=False,
        xaxis_title="Revenue growth (yoy)", yaxis_title="EV / EBITDA",
    ))
    fig.update_xaxes(tickformat=".0%")
    style_axes(fig)
    return fig_html(fig)


def earnings_history_chart(history: pd.DataFrame) -> str:
    """Estimate vs reported EPS for recent quarters."""
    if history is None or history.empty:
        return ""
    cols = set(history.columns)
    if not {"EPS Estimate", "Reported EPS"}.issubset(cols):
        return ""
    past = history.dropna(subset=["Reported EPS"]).copy()
    if past.empty:
        return ""
    past = past.sort_index().tail(8)
    idx = pd.to_datetime(past.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    labels = [d.strftime("%Y-%m-%d") for d in idx]

    est = [safe_float(v) for v in past["EPS Estimate"]]
    act = [safe_float(v) for v in past["Reported EPS"]]
    beat = [
        theme.GREEN if (not np.isnan(a) and not np.isnan(e) and a >= e) else theme.RED
        for a, e in zip(act, est)
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=est, name="EPS estimate",
                         marker_color="rgba(143,163,191,.45)"))
    fig.add_trace(go.Bar(x=labels, y=act, name="Reported EPS", marker_color=beat))
    fig.update_layout(plotly_layout(height=320, barmode="group",
                                    bargap=0.3, bargroupgap=0.1))
    fig.update_xaxes(showgrid=False, type="category")
    style_axes(fig)
    return fig_html(fig)
