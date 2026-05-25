## Module 3: NSE Data Ingestion - Completed (2026-05-25)

Implemented robust data ingestion layer with dual-source fallback (yfinance primary, nsepy secondary) to overcome nsepy compatibility issues on Python 3.14.

### Key Components:
- **app/data/fetcher.py**: 
  - Tries yfinance first (with `.NS` suffix for NSE symbols)
  - Falls back to nsepy if yfinance fails
  - Includes comprehensive validation, column standardization, and error handling
  - Logs detailed diagnostics for debugging

- **app/data/loader.py**:
  - Handles upsert operations into DuckDB prices table
  - Uses INSERT OR REPLACE to avoid duplicates based on (symbol, date) primary key
  - Provides batch loading for multiple symbols

- **tests/test_data_ingestion.py**:
  - Smoke tests verifying data fetch and load for RELIANCE and INFY
  - Uses temporary DuckDB files for isolation
  - Marks tests with @pytest.mark.smoke for easy filtering

### Design Decisions:
1. **Source Priority**: yfinance first due to nsepy's "FrameLocalsProxy" error on Python 3.14
2. **Error Handling**: Detailed logging of failures with exception types and messages
3. **Data Validation**: Checks for required columns, emptiness, and NaN values
4. **Idempotency**: Upsert ensures safe re-runs without duplicate data
5. **Testability**: Modular design allows unit testing of each component

### Known Limitations:
- nsepy source is currently non-functional due to Python 3.14 incompatibility
- yfinance may occasionally experience rate limiting or API changes
- Only OHLCV data is fetched (no adjusted prices for dividends/splits yet)

### Next Steps:
- Module 4: Strategy Engine (SMA crossover, RSI reversion)
- Consider adding adjusted close prices using dividend/split data from yfinance
- Evaluate alternative NSE data sources if yfinance proves unreliable
