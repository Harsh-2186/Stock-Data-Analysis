"""Smoke tests for data ingestion module."""

import os
from datetime import date, timedelta

import pytest

from app.data.fetcher import fetch_symbol_data
from app.data.loader import load_symbol_data, load_multiple_symbols


@pytest.mark.smoke
def test_fetch_reliance_yfinance():
    """Test that we can fetch RELIANCE data from yfinance (or nsepy as fallback)."""
    today = date.today()
    start = today - timedelta(days=5)  # Last 5 days

    df, source = fetch_symbol_data("RELIANCE", start, today)
    assert df is not None, f"Failed to fetch data: {source}"
    assert len(df) > 0, "No data returned"
    assert {"symbol", "date", "open", "high", "low", "close", "volume"}.issubset(set(df.columns))
    # Check that symbol column is set correctly
    assert (df["symbol"] == "RELIANCE").all()


@pytest.mark.smoke
def test_load_reliance_to_duckdb(tmp_path):
    """Test loading RELIANCE data into a temporary DuckDB database."""
    today = date.today()
    start = today - timedelta(days=5)

    # Use a temporary DuckDB file
    db_path = tmp_path / "test_prices.duckdb"

    rows_loaded = load_symbol_data("RELIANCE", start, today, db_path=str(db_path))
    assert rows_loaded > 0, "Failed to load data into DuckDB"

    # Verify data was written
    import duckdb

    conn = duckdb.connect(str(db_path))
    result = conn.execute(
        "SELECT COUNT(*) FROM prices WHERE symbol = 'RELIANCE'"
    ).fetchone()
    assert result[0] == rows_loaded, "Row count mismatch in DuckDB"
    conn.close()


@pytest.mark.smoke
def test_load_multiple_symbols(tmp_path):
    """Test loading multiple symbols into DuckDB."""
    today = date.today()
    start = today - timedelta(days=5)

    db_path = tmp_path / "test_prices_multi.duckdb"
    symbols = ["RELIANCE", "INFY"]

    results = load_multiple_symbols(symbols, start, today, db_path=str(db_path))
    assert isinstance(results, dict)
    for symbol in symbols:
        assert symbol in results
        assert results[symbol] >= 0, f"Negative rows for {symbol}"

    # At least one symbol should have data
    assert any(rows > 0 for rows in results.values()), "No data loaded for any symbol"


if __name__ == "__main__":  # pragma: no cover
    # Allow running as a script for manual verification
    import logging

    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__, "-v"])