"""Risk metrics (with benchmark-relative statistics) and Monte Carlo paths."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from stockanalysis.config import ReportConfig
from stockanalysis.utils import latest


def risk_metrics(
    df: pd.DataFrame,
    config: ReportConfig,
    benchmark_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    # Use dividend-adjusted returns if available (already computed in fetch_data)
    ret_col  = "AdjReturn" if "AdjReturn" in df.columns else "Return"
    returns  = df[ret_col].dropna()
    log_rets = df["LogReturn"].dropna()
    if returns.empty:
        return {}

    annual_return = float((1 + returns.mean()) ** 252 - 1)
    annual_vol    = float(returns.std() * np.sqrt(252))
    downside_vol  = float(returns[returns < 0].std() * np.sqrt(252))
    excess_return = annual_return - config.risk_free_rate
    sharpe        = excess_return / annual_vol    if annual_vol    else np.nan
    sortino       = excess_return / downside_vol  if downside_vol  else np.nan

    cumulative = (1 + returns).cumprod()
    drawdown   = cumulative / cumulative.cummax() - 1
    var_95     = float(returns.quantile(0.05))
    cvar_95    = float(returns[returns <= var_95].mean())

    out: dict[str, Any] = {
        "annual_return": annual_return,
        "annual_volatility": annual_vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": float(drawdown.min()),
        "daily_var_95": var_95,
        "daily_cvar_95": cvar_95,
        "skew": float(returns.skew()),
        "excess_kurtosis": float(returns.kurtosis()),
        "drift": float(log_rets.mean()),
        "daily_sigma": float(log_rets.std()),
    }

    # Benchmark comparison
    if benchmark_df is not None and not benchmark_df.empty and "Return" in benchmark_df.columns:
        bench = benchmark_df["Return"].reindex(returns.index).dropna()
        both  = returns.reindex(bench.index).dropna()
        bench = bench.reindex(both.index)
        if len(both) > 20:
            bench_annual    = float((1 + bench.mean()) ** 252 - 1)
            rel_return      = annual_return - bench_annual
            diff_returns    = both.values - bench.values
            tracking_error  = float(np.std(diff_returns, ddof=1) * np.sqrt(252))
            info_ratio      = rel_return / tracking_error if tracking_error else np.nan
            cov_mat         = np.cov(both.values, bench.values)
            bench_var       = np.var(bench.values, ddof=1)
            actual_beta     = float(cov_mat[0, 1] / bench_var) if bench_var else np.nan
            bench_excess    = bench_annual - config.risk_free_rate
            alpha           = annual_return - (config.risk_free_rate + actual_beta * bench_excess) if not np.isnan(actual_beta) else np.nan
            out.update({
                "benchmark_annual_return": bench_annual,
                "relative_return": rel_return,
                "tracking_error": tracking_error,
                "information_ratio": info_ratio,
                "actual_beta": actual_beta,
                "alpha_proxy": alpha,
            })

    return out


def monte_carlo(df: pd.DataFrame, config: ReportConfig) -> pd.DataFrame:
    last_price = latest(df["Close"])
    log_rets   = df["LogReturn"].dropna()
    if log_rets.empty or np.isnan(last_price):
        return pd.DataFrame()
    mu, sigma = log_rets.mean(), log_rets.std()
    if np.isnan(mu) or np.isnan(sigma) or sigma <= 0:
        return pd.DataFrame()
    rng    = np.random.default_rng(42)
    shocks = rng.normal(mu - 0.5 * sigma**2, sigma,
                        (config.monte_carlo_days, config.monte_carlo_paths))
    paths  = last_price * np.exp(np.cumsum(shocks, axis=0))
    dates  = pd.bdate_range(df.index[-1], periods=config.monte_carlo_days + 1)[1:]
    return pd.DataFrame(paths, index=dates)
