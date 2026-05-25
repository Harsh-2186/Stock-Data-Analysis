"""
app/data/nse_ingest.py
======================
NSE historical OHLCV data ingestion into DuckDB.

Fetch strategy
--------------
1. Primary  : nsepy.get_history   (NSE official source)
2. Fallback : yfinance <SYMBOL>.NS (Yahoo Finance NSE listing)

The two-source approach protects against the periodic breakage that nsepy
experiences whenever NSE changes their website or rate-limits scrapers.

Usage (CLI)
-----------
    python -m app.data.nse_ingest

Public API
----------
    fetch_ohlcv(symbol, start, end) -> pd.DataFrame
    upsert_prices(df)               -> None
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

import pandas as pd

# ── optional imports ──────────────────────────────────────────────────────────
try:
    from nsepy import get_history as _nsepy_get_history  # type: ignore
    _NSEPY_OK = True
except Exception:
    _NSEPY_OK = False

try:
    import nsepython  # type: ignore
    _NSEPYTHON_OK = True
except Exception:
    _NSEPYTHON_OK = False

try:
    import yfinance as yf  # type: ignore
    _YF_OK = True
except Exception:
    _YF_OK = False

from app.models.db_config import get_duckdb_conn

# ── module logger ─────────────────────────────────────────────────────────────
log = logging.getLogger(__name__)

# ── constants ─────────────────────────────────────────────────────────────────
REQUIRED_COLS = ["symbol", "date", "open", "high", "low", "close", "volume", "source"]

# nsepy returns these column names (among many others)
_NSEPY_RENAME = {
    "Open":   "open",
    "High":   "high",
    "Low":    "low",
    "Close":  "close",
    "Volume": "volume",
}

# yfinance column names (auto_adjust=True collapses Adj Close → Close)
_YF_RENAME = {
    "Open":   "open",
    "High":   "high",
    "Low":    "low",
    "Close":  "close",
    "Volume": "volume",
}


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_via_nsepy(symbol: str, start: date, end: date) -> Optional[pd.DataFrame]:
    """Attempt a fetch via nsepy. Returns None on any error or empty result."""
    if not _NSEPY_OK:
        log.debug("nsepy not available.")
        return None
    try:
        raw: pd.DataFrame = _nsepy_get_history(symbol=symbol, start=start, end=end)
    except Exception as exc:
        log.warning("nsepy.get_history raised for %s: %s", symbol, exc)
        return None

    if raw is None or raw.empty:
        log.debug("nsepy returned empty DataFrame for %s.", symbol)
        return None

    # nsepy: Date is the index, rename columns we care about
    df = raw.reset_index().rename(columns={"Date": "date"})
    df = df.rename(columns=_NSEPY_RENAME)
    df["symbol"] = symbol
    df["source"] = "nsepy"

    # Keep only what we need (extra nsepy columns are dropped)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        log.warning("nsepy response missing columns %s for %s.", missing, symbol)
        return None

    return df[REQUIRED_COLS].copy()


def _flatten_yf_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    yfinance ≥ 0.2.38 sometimes returns a MultiIndex (field, ticker) for
    single-ticker downloads in certain call patterns. Flatten it to simple
    column names so rename logic works uniformly.
    """
    if isinstance(df.columns, pd.MultiIndex):
        # MultiIndex: ('Close', 'RELIANCE.NS') → 'Close'
        df.columns = [col[0] for col in df.columns]
    return df


def _fetch_via_yfinance(symbol: str, start: date, end: date) -> Optional[pd.DataFrame]:
    """Attempt a fetch via yfinance using the .NS (NSE) ticker suffix."""
    if not _YF_OK:
        log.debug("yfinance not available.")
        return None

    ticker = f"{symbol}.NS"
    try:
        raw: pd.DataFrame = yf.download(
            ticker,
            start=start,
            end=end + timedelta(days=1),  # yfinance end is exclusive
            auto_adjust=True,
            progress=False,
            multi_level_index=False,      # keep columns flat (yf ≥ 0.2.48)
        )
    except TypeError:
        # Older yfinance versions don't have multi_level_index kwarg
        try:
            raw = yf.download(
                ticker,
                start=start,
                end=end + timedelta(days=1),
                auto_adjust=True,
                progress=False,
            )
        except Exception as exc:
            log.warning("yfinance.download raised for %s: %s", ticker, exc)
            return None
    except Exception as exc:
        log.warning("yfinance.download raised for %s: %s", ticker, exc)
        return None

    if raw is None or raw.empty:
        log.debug("yfinance returned empty DataFrame for %s.", ticker)
        return None

    raw = _flatten_yf_columns(raw)
    df = raw.reset_index().rename(columns={"Date": "date", "Datetime": "date"})
    df = df.rename(columns=_YF_RENAME)
    df["symbol"] = symbol
    df["source"] = "yfinance"

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        log.warning("yfinance response missing columns %s for %s.", missing, ticker)
        return None

    return df[REQUIRED_COLS].copy()


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sanitise a raw DataFrame before upsert:
    - Normalise date column to Python ``date`` objects (strip time component).
    - Coerce OHLC to float; coerce volume to int (NaN → 0).
    - Drop rows where all of OHLC are NaN (completely useless rows).
    - Drop rows dated in the future.
    - Deduplicate on (symbol, date), keeping the first occurrence.
    """
    df = df.copy()

    # Dates
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df = df.dropna(subset=["date"])

    # OHLC
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"], how="all")

    # Volume
    df["volume"] = (
        pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")
    )

    # No future rows
    today = date.today()
    df = df[df["date"] <= today]

    # Deduplicate
    df = df.drop_duplicates(subset=["symbol", "date"]).reset_index(drop=True)

    return df[REQUIRED_COLS]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def fetch_ohlcv(symbol: str, start: date, end: date) -> pd.DataFrame:
    """
    Fetch historical OHLCV data for an NSE-listed equity.

    Tries ``nsepy`` first; falls back to ``yfinance`` (<symbol>.NS) if
    nsepy returns empty or raises an exception.

    Parameters
    ----------
    symbol : str
        NSE ticker (e.g. ``'RELIANCE'``). Case-insensitive.
    start  : date
        Inclusive start date.
    end    : date
        Inclusive end date.

    Returns
    -------
    pd.DataFrame
        Columns: symbol, date, open, high, low, close, volume, source.
        Empty DataFrame if both sources fail.
    """
    symbol = symbol.upper().strip()
    log.info("[%s] Fetching %s → %s", symbol, start, end)

    df = _fetch_via_nsepython(symbol, start, end)
    if df is not None and not df.empty:
        cleaned = _clean(df)
        log.info("[%s] nsepython → %d clean rows", symbol, len(cleaned))
        return cleaned

    log.info("[%s] nsepython returned nothing; trying yfinance …", symbol)
    df = _fetch_via_yfinance(symbol, start, end)
    if df is not None and not df.empty:
        cleaned = _clean(df)
        log.info("[%s] yfinance → %d clean rows", symbol, len(cleaned))
        return cleaned

    log.warning("[%s] Both sources returned no data.", symbol)
    return pd.DataFrame(columns=REQUIRED_COLS)


def upsert_prices(df: pd.DataFrame) -> None:
    """
    Upsert rows into the DuckDB ``prices`` table.

    Uses ``ON CONFLICT (symbol, date) DO UPDATE`` so re-running the ingest
    is fully idempotent — existing rows are refreshed, new rows are inserted.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain exactly the columns in ``REQUIRED_COLS``.
        Silently skips if the DataFrame is empty.
    """
    if df.empty:
        log.debug("Empty DataFrame — nothing to upsert.")
        return

    conn = get_duckdb_conn()
    try:
        conn.register("_staging", df)
        conn.execute(
            """
            INSERT INTO prices (symbol, date, open, high, low, close, volume, source)
            SELECT symbol, date, open, high, low, close, volume, source
            FROM   _staging
            ON CONFLICT (symbol, date) DO UPDATE SET
                open   = EXCLUDED.open,
                high   = EXCLUDED.high,
                low    = EXCLUDED.low,
                close  = EXCLUDED.close,
                volume = EXCLUDED.volume,
                source = EXCLUDED.source
            """
        )
        conn.unregister("_staging")
        log.info("Upserted %d rows into prices.", len(df))
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from datetime import date

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    # ── universe ──────────────────────────────────────────────────────────────
    UNIVERSE: list[str] = [
        "RELIANCE",
        "INFY",
        "HDFCBANK",
        "TCS",
        "ICICIBANK",
        "SBIN",
        "HINDUNILVR",
        "BAJFINANCE",
        "WIPRO",
        "LT",
    ]

    END_DATE   = date.today()
    START_DATE = END_DATE.replace(year=END_DATE.year - 5)  # 5-year backfill

    log.info("=== NSE Ingest — universe: %d symbols, %s → %s ===",
             len(UNIVERSE), START_DATE, END_DATE)

    # ── optional progress bar ─────────────────────────────────────────────────
    try:
        from tqdm import tqdm  # type: ignore
        iterator = tqdm(UNIVERSE, desc="Ingesting", unit="symbol", ncols=70)
    except ImportError:
        iterator = UNIVERSE  # type: ignore

    total_rows: int = 0
    failed:     list[str] = []

    for sym in iterator:
        df = fetch_ohlcv(sym, START_DATE, END_DATE)
        if df.empty:
            failed.append(sym)
            continue
        upsert_prices(df)
        total_rows += len(df)

    # ── summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*55}")
    print(f"  Ingest complete.")
    print(f"  Symbols  : {len(UNIVERSE) - len(failed)} / {len(UNIVERSE)} succeeded")
    print(f"  Rows     : {total_rows:,} written to DuckDB")
    if failed:
        print(f"  No data  : {', '.join(failed)}")
    print(f"{'='*55}\n")
    sys.exit(0)
