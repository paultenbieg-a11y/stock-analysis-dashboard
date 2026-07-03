"""Technical indicator computation on an OHLCV price history."""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_technical_indicators(data: pd.DataFrame) -> pd.DataFrame:
    df = data.copy()
    close  = df["Close"]
    high   = df["High"]
    low    = df["Low"]
    volume = df["Volume"].fillna(0)

    df["Return"]    = close.pct_change()
    df["LogReturn"] = np.log(close / close.shift(1))
    df["SMA_20"]  = close.rolling(20).mean()
    df["SMA_50"]  = close.rolling(50).mean()
    df["SMA_200"] = close.rolling(200).mean()
    df["EMA_12"]  = close.ewm(span=12, adjust=False).mean()
    df["EMA_26"]  = close.ewm(span=26, adjust=False).mean()
    df["MACD"]        = df["EMA_12"] - df["EMA_26"]
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"]   = df["MACD"] - df["MACD_Signal"]

    delta    = close.diff()
    avg_gain = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI_14"] = 100 - (100 / (1 + rs))

    rolling_std   = close.rolling(20).std()
    df["BB_Mid"]   = df["SMA_20"]
    df["BB_Upper"] = df["BB_Mid"] + 2 * rolling_std
    df["BB_Lower"] = df["BB_Mid"] - 2 * rolling_std
    df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / df["BB_Mid"]

    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    df["ATR_14"] = tr.ewm(alpha=1/14, min_periods=14, adjust=False).mean()

    up_move   = high.diff()
    down_move = -low.diff()
    plus_dm   = np.where((up_move > down_move) & (up_move > 0),   up_move,   0.0)
    minus_dm  = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr       = df["ATR_14"].replace(0, np.nan)
    plus_di   = 100 * pd.Series(plus_dm,  index=df.index).ewm(alpha=1/14, adjust=False).mean() / atr
    minus_di  = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / atr
    dx        = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    df["ADX_14"] = dx.ewm(alpha=1/14, adjust=False).mean()

    direction = np.sign(close.diff()).fillna(0)
    df["OBV"]          = (direction * volume).cumsum()
    df["Volume_SMA_20"] = volume.rolling(20).mean()

    return df
