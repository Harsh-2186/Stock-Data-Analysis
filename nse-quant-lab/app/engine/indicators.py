"""Technical Indicators Helpers

This module provides pandas‑friendly wrappers for a few common technical analysis indicators.
It tries to use :pypi:`ta-lib` if it is available; otherwise it falls back to pure‑pandas
implementations that are sufficient for most back‑testing scenarios.

All functions return a :class:`pandas.Series` aligned with the input series index.
Missing values at the start of the series are left as ``NaN`` – callers can forward‑fill
or drop them as required.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Tuple

# Try to import TA‑Lib; if unavailable we will use pandas based implementations.
try:  # pragma: no‑cover – optional dependency
    import talib  # type: ignore
    _HAS_TALIB = True
except Exception:  # pragma: no‑cover – fallback path
    _HAS_TALIB = False


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple Moving Average.

    Parameters
    ----------
    series: pd.Series
        Input price series (e.g., closing prices).
    window: int
        Rolling window length.

    Returns
    -------
    pd.Series
        SMA series aligned with ``series`` index.
    """
    if _HAS_TALIB:
        return pd.Series(talib.SMA(series.values, timeperiod=window), index=series.index)
    return series.rolling(window, min_periods=window).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    """Exponential Moving Average.

    Parameters
    ----------
    series: pd.Series
        Input price series.
    window: int
        Span for the EMA.

    Returns
    -------
    pd.Series
        EMA series aligned with ``series`` index.
    """
    if _HAS_TALIB:
        return pd.Series(talib.EMA(series.values, timeperiod=window), index=series.index)
    return series.ewm(span=window, adjust=False).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index.

    Parameters
    ----------
    series: pd.Series
        Input price series (usually closing prices).
    window: int, optional
        Look‑back period, default 14.

    Returns
    -------
    pd.Series
        RSI values in the range [0, 100].
    """
    if _HAS_TALIB:
        return pd.Series(talib.RSI(series.values, timeperiod=window), index=series.index)
    # Pure‑pandas implementation (see TA‑Lib reference).
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1 / window, adjust=False).mean()
    roll_down = down.ewm(alpha=1 / window, adjust=False).mean()
    rs = roll_up / roll_down
    return 100 - (100 / (1 + rs))


def bollinger_bands(
    series: pd.Series, window: int = 20, n_std: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands (upper, middle, lower).

    Parameters
    ----------
    series: pd.Series
        Input price series.
    window: int, optional
        Rolling window for the moving average, default 20.
    n_std: float, optional
        Number of standard deviations for the band width, default 2.0.

    Returns
    -------
    tuple(pd.Series, pd.Series, pd.Series)
        Upper, middle (SMA), and lower band series.
    """
    if _HAS_TALIB:
        upper, middle, lower = talib.BBAND(series.values, timeperiod=window, nbdevup=n_std, nbdevdn=n_std, matype=0)
        return (
            pd.Series(upper, index=series.index),
            pd.Series(middle, index=series.index),
            pd.Series(lower, index=series.index),
        )
    sma_series = sma(series, window)
    std = series.rolling(window, min_periods=window).std()
    upper = sma_series + n_std * std
    lower = sma_series - n_std * std
    return upper, sma_series, lower
