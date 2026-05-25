# Run Instructions

## Module 1 – How to run

### Environment Setup
Create a virtual environment and install the pinned dependencies using classic Command Prompt (`cmd`):

```cmd
:: Using standard Python venv and pip
python -m venv venv
call venv\Scripts\activate
pip install -e .[dev]
```

Alternatively, if you are using `uv`:
```cmd
uv venv
uv pip install -e .[dev]
```

### Verification
Since this module establishes the scaffolding structure, you can verify it by checking that the folders can be successfully imported by Python:
```cmd
python -c "import app; print('Scaffolding imported successfully!')"
```cmd
python -c "import app; print('Scaffolding imported successfully!')"
```

**Full command workflow** (run in order):
1. Set up virtual environment and install deps:
   ```cmd
   python -m venv venv
   call venv\Scripts\activate
   pip install -e .[dev]
   ```
2. Initialize DuckDB schema:
   ```cmd
   python -c "import app.models as m; conn=m.get_duckdb_conn(); ddl=open('scripts/duckdb_ddl.sql').read(); conn.execute(ddl); conn.close()"
   ```
3. Initialize PostgreSQL schema (set env vars then run):
   ```cmd
   set POSTGRES_DB=nse_quant
   set POSTGRES_USER=postgres
   set POSTGRES_PASSWORD=postgres
   psql -h localhost -U postgres -d nse_quant -f scripts\postgres_ddl.sql
   ```
4. Run data ingestion:
   ```cmd
   python -m app.data.nse_ingest
   ```
5. Verify data load:
   ```cmd
   python -c "import duckdb; conn=duckdb.connect('data/prices.duckdb'); print(conn.execute('SELECT COUNT(*) FROM prices').fetchone())"
   ```
6. Test indicators and strategy (optional):
   ```cmd
   python - <<EOF
   from app.engine.indicators import sma
   import duckdb, pandas as pd
   conn=duckdb.connect('data/prices.duckdb')
   df=conn.execute("SELECT * FROM prices WHERE symbol='RELIANCE' ORDER BY date").fetchdf()
   print(sma(df['close'],20).tail())
   EOF
   ```

## Module 2 – How to run

### Prerequisites
Make sure your virtual environment is active:
```cmd
venv\Scripts\activate
```

### 1. Initializing DuckDB Schema
To create the DuckDB database file and the `prices` table, run the following Python command in the classic Command Prompt:
```cmd
python -c "import app.models as m; conn = m.get_duckdb_conn(); ddl = open('scripts/duckdb_ddl.sql').read(); conn.execute(ddl); conn.close(); print('DuckDB initialized successfully!')"
```
This creates the database file `data/prices.duckdb`. You can verify it by running:
```cmd
dir data
```

### 2. Initializing PostgreSQL Schema
Set the environment variables in your Command Prompt session if they differ from the defaults (host=localhost, port=5432, db=nse_quant, user=postgres, password=postgres):
```cmd
set POSTGRES_DB=nse_quant
set POSTGRES_USER=postgres
set POSTGRES_PASSWORD=postgres
```
Apply the DDL script `scripts\postgres_ddl.sql` to your PostgreSQL database. For example, using `psql`:
```cmd
psql -h localhost -U postgres -d nse_quant -f scripts\postgres_ddl.sql
```

### 3. Verification
Verify the compilation of SQLAlchemy models and DuckDB writes by running:
```cmd
python scripts\verify_db.py
```

## After Module 2
## Module 3 – Data Ingestion from NSE (nsepy/nsepython)

### How to run

1. Ensure your virtual environment is active:
   ```cmd
   venv\\Scripts\\activate
   ```
2. Initialize DuckDB schema if not done (see Module 2).
3. Run the ingestion script:
   ```cmd
   python -m app.data.nse_ingest
   ```
   This will fetch the last 5 years of EOD data for a default universe of symbols and upsert it into `data/prices.duckdb`.
4. Verify the data was inserted:
   ```cmd
   python -c "import duckdb, pandas as pd; conn=duckdb.connect('data/prices.duckdb'); print(conn.execute('SELECT COUNT(*) FROM prices').fetchone())"
   ```

*You can customize the universe and date range by editing `app/data/nse_ingest.py` or passing arguments (future feature).*

## Module 4 – Indicators and Base Strategy

### How to run

1. Ensure your virtual environment is active:
   ```cmd
   venv\\Scripts\\activate
   ```
2. Verify that DuckDB contains price data (see Module 3).
3. Open a Python REPL or notebook and import the indicators:
   ```python
   from app.engine.indicators import sma, ema, rsi, bollinger_bands
   import duckdb, pandas as pd
   conn = duckdb.connect('data/prices.duckdb')
   df = conn.execute("SELECT * FROM prices WHERE symbol='RELIANCE' ORDER BY date").fetchdf()
   print(sma(df['close'], 20).tail())
   ```
4. (Optional) Create a simple strategy subclass of `BaseStrategy` to test signal generation.
   ```python
   from app.engine.base import StrategyConfig, BaseStrategy
   class DummyStrategy(BaseStrategy):
       def generate_signals(self):
           df = self.prices.copy()
           df['signal'] = 0
           df.loc[df['close'] > df['close'].shift(), 'signal'] = 1
           df.loc[df['close'] < df['close'].shift(), 'signal'] = -1
           return df[['signal']]
   cfg = StrategyConfig(name='dummy', kind='dummy', params={}, universe=['RELIANCE'], date_start=df['date'].min().date(), date_end=df['date'].max().date())
   strat = DummyStrategy(cfg, df)
   signals = strat.generate_signals()
   print(signals.head())
   ```
5. You can now proceed to implement full backtesting using these building blocks.

*Feel free to edit `app/engine/indicators.py` and `app/engine/base.py` to suit your strategy needs.*
