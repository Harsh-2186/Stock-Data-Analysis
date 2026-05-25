"""Data fetcher for NSE symbols using multiple sources with fallback.

Tries yfinance first, then falls back to nsepy if yfinance fails.
Includes robust error handling and validation.
"""

import logging
from datetime import date
from typing import Optional, Tuple

import pandas as pd
import yfinance as yf

try:
    from nsepy import get_history
    NSEPY_AVAILABLE = True
except ImportError:
    NSEPY_AVAILABLE = False
    get_history = None  # type: ignore

logger = logging.getLogger(__name__)


def _validate_ohlcv_df(df: pd.DataFrame, symbol: str) -> bool:
    """Validate that the DataFrame has required OHLCV columns and is not empty."""
    if df.empty:
        logger.warning("[%s] Fetched data is empty", symbol)
        return False

    required_columns = {"date", "open", "high", "low", "close", "volume"}
    # yfinance returns 'Date' with capital D, we'll standardize later
    df_columns = {col.lower() for col in df.columns}
    if not required_columns.issubset(df_columns):
        logger.warning(
            "[%s] Missing required columns. Expected: %s, Got: %s",
            symbol,
            required_columns,
            df_columns,
        )
        return False

    # Check for NaNs in critical columns
    if df[["open", "high", "low", "close", "volume"]].isnull().any().any():
        logger.warning("[%s] Found NaN values in OHLCV data", symbol)
        return False

    return True


def _standardize_df(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Standardize DataFrame: ensure date column is lowercase and date type."""
    # yfinance returns 'Date', nsepy returns 'Date' (capital D)
    if "Date" in df.columns:
        df = df.rename(columns={"Date": "date"})
    # Ensure date is datetime.date (not datetime64)
    if pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = df["date"].dt.date
    # Ensure symbol column
    df["symbol"] = symbol
    # Reorder columns: symbol, date, open, high, low, close, volume, source
    cols = ["symbol", "date", "open", "high", "low", "close", "volume"]
    # Add any extra columns (like dividends, splits) at the end
    extra_cols = [c for c in df.columns if c not in cols]
    df = df[cols + extra_cols]
    return df


def fetch_with_yfinance(
    symbol: str, start: date, end: date
) -> Tuple[Optional[pd.DataFrame], str]:
    """Fetch data using yfinance for NSE symbol (append .NS)."""
    yf_symbol = f"{symbol}.NS"
    try:
        logger.debug("Fetching %s from yfinance (%s to %s)", yf_symbol, start, end)
        df = yf.download(yf_symbol, start=start, end=end, progress=False)
        if df.empty:
            logger.warning("[%s] yfinance returned empty DataFrame", symbol)
            return None, "yfinance: empty response"

        # yfinance returns multi-level columns if multiple symbols, but we have single
        if isinstance(df.columns, pd.MultiIndex):
            # This shouldn't happen with single symbol, but handle just in case
            df.columns = df.columns.get_level_values(0)

        if not _validate_ohlcv_df(df, symbol):
            return None, "yfinance: validation failed"

        df = _standardize_df(df, symbol)
        df["source"] = "yfinance"
        logger.info("[%s] Successfully fetched %d rows from yfinance", symbol, len(df))
        return df, "yfinance"

    except Exception as e:  # pragma: no cover - network errors are hard to test
        logger.exception("[%s] yfinance failed with exception: %s", symbol, e)
        return None, f"yfinance: {type(e).__name__}: {e}"


def fetch_with_nsepy(
    symbol: str, start: date, end: date
) -> Tuple[Optional[pd.DataFrame], str]:
    """Fetch data using nsepy."""
    if not NSEPY_AVAILABLE:
        return None, "nsepy: not installed"

    try:
        logger.debug("Fetching %s from nsepy (%s to %s)", symbol, start, end)
        df = get_history(symbol=symbol, start=start, end=end)
        if df.empty:
            logger.warning("[%s] nsepy returned empty DataFrame", symbol)
            return None, "nsepy: empty response"

        if not _validate_ohlcv_df(df, symbol):
            return None, "nsepy: validation failed"

        df = _standardize_df(df, symbol)
        df["source"] = "nsepy"
        logger.info("[%s] Successfully fetched %d rows from nsepy", symbol, len(df))
        return df, "nsepy"

    except Exception as e:  # pragma: no cover
        logger.exception("[%s] nsepy failed with exception: %s", symbol, e)
        return None, f"nsepy: {type(e).__name__}: {e}"


def fetch_symbol_data(
    symbol: str, start: date, end: date
) -> Tuple[Optional[pd.DataFrame], str]:
    """Fetch data for a symbol, trying yfinance first then nsepy as fallback.

    Returns:
        (DataFrame, source_used) if successful, (None, error_message) if failed.
    """
    # Try yfinance first
    df, source = fetch_with_yfinance(symbol, start, end)
    if df is not None:
        return df, source

    # If yfinance failed, try nsepy
    logger.info("[%s] yfinance failed (%s), trying nsepy...", symbol, source)
    df, source = fetch_with_nsepy(symbol, start, end)
    if df is not None:
        return df, source

    # Both failed
    return None, f"yfinance failed ({source}), nsepy failed ({source})"


if __name__ == "__main__":  # pragma: no cover
    # Quick manual test
    logging.basicConfig(level=logging.INFO)
    today = date.today()
    start = date(today.year - 5, today.month, today.day)
    for sym in ["RELIANCE", "INFY"]:
        df, src = fetch_symbol_data(sym, start, today)
        if df is not None:
            print(f"[{sym}] {src}: {len(df)} rows")
            print(df.head())
        else:
            print(f"[{sym}] Failed: {src}")