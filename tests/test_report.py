import numpy as np
import pandas as pd

from stockanalysis.report import build_report

SECTION_TITLES = [
    "Company Overview",
    "Executive View",
    "Earnings and Quarterly Trends",
    "Technical Structure",
    "Annual Financial Statements",
    "Valuation and Fundamentals",
    "Peer Comparison",
    "Risk and Historical Behaviour",
    "Forward Scenarios",
]


def test_build_report_end_to_end(tmp_path, config, data_bundle):
    path = build_report(config, data_bundle, output_dir=tmp_path)
    assert path.exists()
    html = path.read_text(encoding="utf-8")

    for title in SECTION_TITLES:
        assert title in html, f"missing section: {title}"

    assert "TEST" in html
    assert "Test Corp" in html
    assert "Reverse DCF" in html
    assert "plotly" in html.lower()
    # peer table highlights the subject row
    assert "peer-subject" in html
    # earnings card present
    assert "Next earnings" in html


def test_build_report_without_optional_data(tmp_path, config, data_bundle):
    bundle = dict(data_bundle)
    bundle["peers"] = []
    bundle["earnings"] = {"next_date": None, "history": pd.DataFrame()}
    bundle["impl_vol"] = np.nan
    bundle["quarterly_income"] = pd.DataFrame()
    bundle["benchmark_df"] = pd.DataFrame()

    path = build_report(config, bundle, output_dir=tmp_path)
    html = path.read_text(encoding="utf-8")
    assert "Peer Comparison" not in html
    assert "Company Overview" in html
    assert "Forward Scenarios" in html


def test_build_report_currency_mismatch(tmp_path, config, data_bundle):
    bundle = dict(data_bundle)
    bundle["info"] = dict(bundle["info"], currency="USD", financialCurrency="EUR")
    path = build_report(config, bundle, output_dir=tmp_path)
    html = path.read_text(encoding="utf-8")
    assert "not price-comparable" in html
    assert "Data Notes" in html
