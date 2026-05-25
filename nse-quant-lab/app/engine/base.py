"""Base strategy infrastructure.

Provides a small Pydantic configuration model and an abstract base class that
strategy implementations can inherit from. The class stores the config and the
prices DataFrame (already filtered for the desired universe and date range) and
exposes a ``generate_signals`` method that must return a DataFrame of signals.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, List

import pandas as pd
from pydantic import BaseModel, Field


class StrategyConfig(BaseModel):
    """Configuration for a trading strategy.

    Attributes
    ----------
    name: str
        Human‑readable name of the strategy.
    kind: str
        Identifier used by the system (e.g., ``"sma_crossover"``).
    params: dict[str, Any]
        Arbitrary parameters required by the concrete implementation.
    universe: List[str]
        List of symbol ticker strings the strategy will operate on.
    date_start: _dt.date
        Inclusive start date for back‑testing.
    date_end: _dt.date
        Inclusive end date for back‑testing.
    """

    name: str
    kind: str
    params: dict[str, Any] = Field(default_factory=dict)
    universe: List[str]
    date_start: _dt.date
    date_end: _dt.date

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {"date": lambda v: v.isoformat()}


class BaseStrategy:
    """Abstract base class for all strategies.

    Sub‑classes must implement :meth:`generate_signals` which returns a DataFrame
    indexed by date (and optionally symbol) containing at least a ``signal``
    column with values ``-1`` (sell), ``0`` (flat), or ``1`` (buy).
    """

    def __init__(self, config: StrategyConfig, prices: pd.DataFrame):
        self.config = config
        # Ensure the DataFrame has a datetime index for consistent handling.
        if not isinstance(prices.index, pd.DatetimeIndex):
            if "date" in prices.columns:
                prices = prices.set_index(pd.to_datetime(prices["date"]))
            else:
                raise ValueError("prices DataFrame must contain a 'date' column or a DatetimeIndex")
        self.prices = prices.sort_index()

    @property
    def name(self) -> str:
        """Return the configured strategy name."""
        return self.config.name

    def generate_signals(self) -> pd.DataFrame:
        """Generate trading signals.

        Returns
        -------
        pd.DataFrame
            Indexed by date (and optionally symbol) with a ``signal`` column.
        """
        raise NotImplementedError("Sub‑classes must implement generate_signals")
