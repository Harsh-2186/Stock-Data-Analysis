"""Data loader for writing OHLCV data to DuckDB.

Handles upsert (insert or update) to avoid duplicates based on (symbol, date) primary key.
"""

import logging
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

from .fetcher import fetch_symbol_data

logger = logging.getLogger(__name__)


def load_symbol_data(
    symbol: str,
    start: date,
    end: date,
    db_path: str = "./data/prices.duckdb",
) -> int:
    """Fetch data for a symbol and load it into DuckDB.

    Args:
        symbol: Stock symbol (e.g., 'RELIANCE')
        start: Start date (inclusive)
        end: End date (inclusive)
        db_path: Path to DuckDB file

    Returns:
        Number of rows inserted/updated
    """
    from datetime import date  # local import to avoid circular issues

    df, source = fetch_symbol_data(symbol, start, end)
    if df is None:
        logger.error("[%s] Failed to fetch data: %s", symbol, source)
        return 0

    # Ensure we only keep the columns we need for the prices table
    # The fetcher already standardized columns, but we'll be explicit
    db_df = df[["symbol", "date", "open", "high", "low", "close", "volume", "source"]].copy()

    try:
        # Get DuckDB connection
        from app.models.db_config import get_duckdb_conn

        conn = get_duckdb_conn(db_path)

        # Create table if not exists (should already exist from DDL, but safe)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prices (
                symbol TEXT,
                date DATE,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                source TEXT,
                PRIMARY KEY (symbol, date)
            )
            """
        )

        # Perform upsert: insert new rows, update existing ones
        # DuckDB doesn't have native UPSERT, so we use INSERT OR REPLACE
        # First, create a temporary table
        conn.register("temp_data", db_df)
        conn.execute(
            """
            INSERT OR REPLACE INTO prices
            SELECT * FROM temp_data
            """
        )
        conn.unregister("temp_data")

        rows_affected = len(db_df)
        logger.info(
            "[%s] Loaded %d rows into DuckDB (source: %s)", symbol, rows_affected, source
        )
        return rows_affected

    except Exception as e:  # pragma: no cover
        logger.exception("[%s] Failed to load data into DuckDB: %s", symbol, e)
        return 0


def load_multiple_symbols(
    symbols: list[str],
    start: date,
    end: date,
    db_path: str = "./data/prices.duckdb",
) -> dict[str, int]:
    """Load data for multiple symbols.

    Returns:
        Dictionary mapping symbol to number of rows loaded
    """
    results = {}
    for symbol in symbols:
        rows = load_symbol_data(symbol, start, end, db_path)
        results[symbol] = rows
    return results


if __name__ == "__main__":  # pragma: no cover
    # Quick manual test
    import logging
    from datetime import date

    logging.basicConfig(level=logging.INFO)
    today = date.today()
    start = date(today.year - 1, today.month, today.day)  # Last 1 year

    test_symbols = ["RELIANCE", "INFY"]
    results = load_multiple_symbols(test_symbols, start, today)
    for symbol, rows in results.items():
        print(f"[{symbol}] Loaded {rows} rows")