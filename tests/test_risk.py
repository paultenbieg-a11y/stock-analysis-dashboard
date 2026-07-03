import numpy as np

from stockanalysis.indicators import add_technical_indicators
from stockanalysis.risk import monte_carlo, risk_metrics


def test_risk_metrics_basics(history, config):
    df = add_technical_indicators(history)
    out = risk_metrics(df, config)
    assert out["annual_volatility"] > 0
    assert out["max_drawdown"] <= 0
    assert out["daily_var_95"] < 0
    assert out["daily_cvar_95"] <= out["daily_var_95"]
    assert np.isfinite(out["sharpe"])


def test_risk_metrics_with_benchmark(history, benchmark_df, config):
    df = add_technical_indicators(history)
    out = risk_metrics(df, config, benchmark_df)
    for key in ("benchmark_annual_return", "relative_return", "tracking_error",
                "information_ratio", "actual_beta", "alpha_proxy"):
        assert key in out
    assert out["tracking_error"] > 0
    # Benchmark was built at ~0.8x the stock's returns, so beta vs the
    # benchmark should be around 1.25 within noise.
    assert 0.8 < out["actual_beta"] < 1.8


def test_monte_carlo_shape(history, config):
    df = add_technical_indicators(history)
    paths = monte_carlo(df, config)
    assert paths.shape == (config.monte_carlo_days, config.monte_carlo_paths)
    assert (paths.values > 0).all()
    # Deterministic seed: same call twice gives the same result.
    again = monte_carlo(df, config)
    assert np.allclose(paths.values, again.values)
