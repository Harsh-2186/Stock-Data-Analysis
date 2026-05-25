"""Strategy implementations using vectorbt.

This module defines concrete strategy classes inheriting from :class:`app.engine.base.BaseStrategy`
and a simple runner that executes a backtest with the *vectorbt* library.

The strategies work on a **wide** price DataFrame where each column is a symbol
and the index is a ``pd.DatetimeIndex`` of trading dates.  The helper
``run_vectorbt_backtest`` pivots the signals produced by the strategy into
entries/exits for ``vectorbt.Portfolio.from_signals``.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any, Dict

import pandas as pd
import vectorbt as vbt

from .base import BaseStrategy, StrategyConfig
from .indicators import sma, rsi


@dataclass
class BacktestResult:
    """Container for a vectorbt back‑test summary.

    Attributes
    ----------
    equity : pd.Series
        Portfolio equity curve (total value over time).
    trades_count : int
        Number of executed trades.
    total_return : float
        Total portfolio return (as a decimal, e.g. 0.42 for 42%).
    max_drawdown : float
        Maximum draw‑down (decimal).
    sharpe : float
        Annualised Sharpe ratio.
    other_metrics : Dict[str, float]
        Any additional statistics returned by ``Portfolio.stats()``.
    """

    equity: pd.Series
    trades_count: int
    total_return: float
    max_drawdown: float
    sharpe: float
    other_metrics: Dict[str, float] = field(default_factory=dict)


class SMACrossStrategy(BaseStrategy):
    """Simple moving‑average crossover.

    Parameters are supplied via ``StrategyConfig.params``:
        - ``fast_window`` (int): Fast SMA period.
        - ``slow_window`` (int): Slow SMA period.
    The strategy goes **long** when ``fast_sma > slow_sma`` and flat otherwise.
    """

    def generate_signals(self) -> pd.DataFrame:
        fast_w = self.config.params.get("fast_window", 20)
        slow_w = self.config.params.get("slow_window", 50)
        signals = pd.DataFrame(index=self.prices.index)
        for sym in self.prices.columns:
            series = self.prices[sym]
            fast = sma(series, fast_w)
            slow = sma(series, slow_w)
            sig = (fast > slow).astype(int)
            signals[sym] = sig
        return signals


class RSIMeanReversionStrategy(BaseStrategy):
    """RSI‑based mean reversion.

    Expected ``params`` keys:
        - ``rsi_window`` (int)
        - ``lower`` (float) – RSI below which we **go long**.
        - ``upper`` (float) – RSI above which we **exit**.
    """

    def generate_signals(self) -> pd.DataFrame:
        w = self.config.params.get("rsi_window", 14)
        lower = self.config.params.get("lower", 30)
        upper = self.config.params.get("upper", 70)
        signals = pd.DataFrame(index=self.prices.index)
        for sym in self.prices.columns:
            r = rsi(self.prices[sym], w)
            # long when RSI < lower, flat otherwise; exit when RSI > upper
            sig = pd.Series(0, index=self.prices.index)
            sig[r < lower] = 1
            sig[r > upper] = 0
            signals[sym] = sig
        return signals


class BuyAndHoldStrategy(BaseStrategy):
    """Buy on the first bar and hold to the end.

    No external parameters are required.  The signal is ``1`` for every date
    after the first observation.
    """

    def generate_signals(self) -> pd.DataFrame:
        signals = pd.DataFrame(1, index=self.prices.index, columns=self.prices.columns)
        return signals


def _prepare_entries_exits(signals: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert a signal DataFrame into *entries*/*exits* DataFrames.

    ``signals`` is expected to contain ``1`` for long, ``0`` for flat and ``-1``
    for short (if a strategy uses shorts).  Entries are detected when a signal
    changes from non‑positive to positive; exits when it changes from positive to
    non‑positive.
    """
    diff = signals.diff().fillna(0)
    entries = (diff == 1).astype(int)
    exits = (diff == -1).astype(int)
    return entries, exits


def run_vectorbt_backtest(strategy: BaseStrategy, prices: pd.DataFrame) -> BacktestResult:
    """Run a vectorbt back‑test for a given ``BaseStrategy``.

    Parameters
    ----------
    strategy : BaseStrategy
        An instantiated strategy (already supplied with config and price data).
    prices : pd.DataFrame
        Wide‑format price data (columns = symbols, ``pd.DatetimeIndex`` rows).

    Returns
    -------
    BacktestResult
        Summary of the back‑test.
    """
    # Generate the raw signal matrix (1 / 0 / -1).
    signals = strategy.generate_signals()
    # Align signals to the price index – missing values become flat.
    signals = signals.reindex(prices.index).fillna(0)

    entries, exits = _prepare_entries_exits(signals)

    portfolio = vbt.Portfolio.from_signals(
        close=prices,
        entries=entries.astype(bool),
        exits=exits.astype(bool),
        freq="1D",
        fees=0.001,  # 0.1 % per trade
        init_cash=100_000,
        cash_sharing=False,
    )

    stats = portfolio.stats()
    # Extract a few core metrics.
    equity = portfolio.value
    trades = int(stats.get("#Trades", 0))
    total_ret = float(stats.get("Return", 0.0))
    drawdown = float(stats.get("MaxDrawdown", 0.0))
    sharpe = float(stats.get("SharpeRatio", 0.0))

    # Separate the remaining numeric stats.
    core_keys = {"#Trades", "Return", "MaxDrawdown", "SharpeRatio"}
    other = {k: float(v) for k, v in stats.items() if k not in core_keys and isinstance(v, (int, float))}

    return BacktestResult(
        equity=equity,
        trades_count=trades,
        total_return=total_ret,
        max_drawdown=drawdown,
        sharpe=sharpe,
        other_metrics=other,
    )
