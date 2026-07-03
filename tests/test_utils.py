import numpy as np

from stockanalysis.utils import (
    clean_currency,
    human_number,
    money,
    pct,
    ratio_fmt,
    safe_float,
    safe_output_filename,
    same_currency,
)


def test_safe_float():
    assert safe_float("3.5") == 3.5
    assert np.isnan(safe_float(None))
    assert np.isnan(safe_float("abc"))
    assert np.isnan(safe_float(float("inf")))
    assert safe_float(None, 0.0) == 0.0


def test_human_number():
    assert human_number(1.5e9) == "1.50B"
    assert human_number(-2.3e12) == "-2.30T"
    assert human_number(950) == "950.00"
    assert human_number(None) == "n/a"


def test_pct_and_money():
    assert pct(0.1234) == "12.34%"
    assert pct(None) == "n/a"
    assert money(12.3, "USD") == "USD 12.30"
    assert money(12.3, "€") == "€12.30"
    assert money(np.nan) == "n/a"


def test_ratio_fmt():
    assert ratio_fmt(1.234) == "1.23"
    assert ratio_fmt(1.234, 1, "x") == "1.2x"
    assert ratio_fmt(np.nan) == "n/a"


def test_currency_helpers():
    assert clean_currency(None) == "USD"
    assert clean_currency(" eur ") == "EUR"
    assert clean_currency("nan", "CHF") == "CHF"
    assert same_currency("usd", "USD")
    assert not same_currency("USD", "EUR")


def test_safe_output_filename():
    assert safe_output_filename("SAP.DE") == "SAP.DE"
    assert safe_output_filename("a b/c") == "A_B_C"
    assert safe_output_filename("...") == "STOCK"
