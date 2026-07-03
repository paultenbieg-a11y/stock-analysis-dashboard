import numpy as np
import pytest

from stockanalysis.fundamentals import (
    calculate_fundamentals,
    get_statement_value,
    get_statement_value_for_period,
)


def test_get_statement_value_aliases(statements):
    income = statements["income"]
    assert get_statement_value(income, ["Total Revenue"]) == 120e9
    # alias fallback: first name missing, second matches
    assert get_statement_value(income, ["Nonexistent", "Total Revenue"]) == 120e9
    # previous period
    assert get_statement_value(income, ["Total Revenue"], 1) == 110e9
    assert np.isnan(get_statement_value(income, ["Nope"]))


def test_get_statement_value_for_period(statements):
    income = statements["income"]
    col = income.columns[1]
    assert get_statement_value_for_period(income, ["Total Revenue"], col) == 110e9
    assert np.isnan(get_statement_value_for_period(income, ["Total Revenue"], "2019"))


def test_ratios(info, statements):
    ratios = calculate_fundamentals(info, statements)
    assert ratios["gross_margin"] == pytest.approx(54e9 / 120e9)
    assert ratios["operating_margin"] == pytest.approx(36e9 / 120e9)
    assert ratios["roe"] == pytest.approx(29e9 / 90e9)
    assert ratios["revenue_growth"] == pytest.approx(120 / 110 - 1)
    assert ratios["current_ratio"] == pytest.approx(80 / 50)
    assert ratios["currencies_comparable"] is True
    # free cash flow comes from info when present
    assert ratios["free_cash_flow"] == 30e9
    assert ratios["fcf_yield"] == pytest.approx(30e9 / 1.8e12)


def test_piotroski_perfect_score(info, statements):
    # The fixture is constructed to pass all nine tests.
    ratios = calculate_fundamentals(info, statements)
    assert ratios["piotroski_score"] == 9


def test_piotroski_none_when_statements_missing(info, statements):
    import pandas as pd

    incomplete = dict(statements)
    incomplete["cashflow"] = pd.DataFrame()
    ratios = calculate_fundamentals(info, incomplete)
    assert ratios["piotroski_score"] is None
