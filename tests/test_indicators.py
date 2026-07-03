import numpy as np

from stockanalysis.indicators import add_technical_indicators

EXPECTED_COLUMNS = [
    "Return", "LogReturn", "SMA_20", "SMA_50", "SMA_200", "MACD", "MACD_Signal",
    "MACD_Hist", "RSI_14", "BB_Upper", "BB_Lower", "BB_Width", "ATR_14",
    "ADX_14", "OBV", "Volume_SMA_20",
]


def test_columns_present(history):
    df = add_technical_indicators(history)
    for col in EXPECTED_COLUMNS:
        assert col in df.columns, col


def test_rsi_bounds(history):
    df  = add_technical_indicators(history)
    rsi = df["RSI_14"].dropna()
    assert not rsi.empty
    assert rsi.between(0, 100).all()


def test_sma_matches_manual(history):
    df = add_technical_indicators(history)
    manual = history["Close"].rolling(20).mean()
    assert np.allclose(df["SMA_20"].dropna(), manual.dropna())


def test_atr_positive_and_bollinger_ordered(history):
    df = add_technical_indicators(history)
    assert (df["ATR_14"].dropna() > 0).all()
    valid = df.dropna(subset=["BB_Upper", "BB_Lower"])
    assert (valid["BB_Upper"] >= valid["BB_Lower"]).all()


def test_original_frame_untouched(history):
    before = history.copy()
    add_technical_indicators(history)
    assert list(history.columns) == list(before.columns)
