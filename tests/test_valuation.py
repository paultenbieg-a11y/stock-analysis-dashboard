import numpy as np
import pytest

from stockanalysis.fundamentals import calculate_fundamentals
from stockanalysis.valuation import (
    compute_wacc,
    dcf_sensitivity,
    dcf_tornado,
    dcf_valuation,
    project_fair_value,
    reverse_dcf,
)


@pytest.fixture
def ratios(info, statements):
    return calculate_fundamentals(info, statements)


@pytest.fixture
def wacc(ratios, config, statements):
    return compute_wacc(ratios, config, statements["income"])


def test_wacc_structure(wacc):
    assert wacc["method"] == "WACC"
    assert wacc["equity_weight"] + wacc["debt_weight"] == pytest.approx(1.0)
    assert 0.06 <= wacc["wacc"] <= 0.16
    assert 0 < wacc["after_tax_cost_of_debt"] < wacc["cost_of_debt_pretax"]


def test_dcf_valuation_positive(ratios, config, wacc):
    val = dcf_valuation(ratios, config, wacc)
    assert np.isfinite(val["fair_value"])
    assert val["fair_value"] > 0
    assert val["comparable_to_price"] is True


def test_project_fair_value_monotonic():
    base = dict(fcf=30e9, shares=8e9, terminal_growth=0.025, forecast_years=5)
    low_g  = project_fair_value(base_growth=0.02, discount_rate=0.09, **base)
    high_g = project_fair_value(base_growth=0.10, discount_rate=0.09, **base)
    assert high_g > low_g
    low_dr  = project_fair_value(base_growth=0.06, discount_rate=0.08, **base)
    high_dr = project_fair_value(base_growth=0.06, discount_rate=0.12, **base)
    assert low_dr > high_dr


def test_project_fair_value_bad_inputs():
    assert np.isnan(project_fair_value(-1e9, 8e9, 0.05, 0.09, 0.025))
    assert np.isnan(project_fair_value(30e9, 0, 0.05, 0.09, 0.025))
    assert np.isnan(project_fair_value(np.nan, 8e9, 0.05, 0.09, 0.025))


def test_sensitivity_grid(ratios, config, wacc):
    grid = dcf_sensitivity(ratios, config, wacc)
    assert grid.shape == (5, 5)
    mid_col = grid.columns[2]
    col = grid[mid_col].dropna()
    # Higher WACC (rows are ascending discount rates) → lower fair value.
    assert col.is_monotonic_decreasing
    # Higher terminal growth → higher fair value along a row.
    mid_row = grid.iloc[2].dropna()
    assert mid_row.is_monotonic_increasing


def test_reverse_dcf_roundtrip(ratios, config, wacc):
    g0 = 0.08
    dr = wacc["wacc"]
    tg = min(config.terminal_growth, dr - 0.01)
    price = project_fair_value(
        ratios["free_cash_flow"], ratios["shares"], g0, dr, tg, config.forecast_years
    )
    implied = reverse_dcf(ratios, config, wacc, price)
    assert implied == pytest.approx(g0, abs=1e-3)


def test_reverse_dcf_unreachable_price(ratios, config, wacc):
    assert np.isnan(reverse_dcf(ratios, config, wacc, 1e9))  # absurd price
    assert np.isnan(reverse_dcf(ratios, config, wacc, np.nan))


def test_tornado(ratios, config, wacc):
    drivers = dcf_tornado(ratios, config, wacc)
    assert len(drivers) >= 3
    spans = [d["high"] - d["low"] for d in drivers]
    assert spans == sorted(spans, reverse=True)
    for d in drivers:
        assert d["low"] <= d["base"] <= d["high"]
