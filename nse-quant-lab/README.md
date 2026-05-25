# nse-quant-lab

`nse-quant-lab` is a Python-based quantitative trading research platform for the National Stock Exchange (NSE). It provides tools for data ingestion, backtesting strategies, calculating portfolio metrics, and managing background jobs with a FastAPI backend and a Streamlit frontend dashboard.

## High-Level Architecture

```text
                  +-----------------------------------+
                  |        Streamlit UI (app/ui)      |
                  +-----------------------------------+
                                    |
                                    v
                  +-----------------------------------+
                  |        FastAPI API (app/api)      |
                  +-----------------------------------+
                                    |
            +-----------------------+-----------------------+
            |                       |                       |
            v                       v                       v
+-----------------------+ +-----------------------+ +-----------------------+
|  Jobs (app/jobs)      | |  Engine (app/engine)  | | Analytics             |
|  - Ingestion schedule | |  - backtesting        | | (app/analytics)       |
|  - ETL tasks          | |  - vectorbt, backtrader| | - pyfolio, ffn, ta-lib|
+-----------------------+ +-----------------------+ +-----------------------+
            |                       |                       |
            +-----------------------+-----------------------+
                                    |
                                    v
                  +-----------------------------------+
                  |       Data Ingestion (app/data)   |
                  +-----------------------------------+
                                    |
            +-----------------------+-----------------------+
            |                                               |
            v                                               v
+-----------------------+                       +-----------------------+
|      DuckDB Storage   |                       |    PostgreSQL/Redis   |
|   (data/nse_quant.db) |                       |  (Analytical/Cache)   |
+-----------------------+                       +-----------------------+
```

## Directory Structure

- `app/`: Source code directory.
  - `api/`: FastAPI controller routers and endpoints.
  - `data/`: Ingestion engines, database adapters (DuckDB, Postgres, Redis), and ETL pipelines.
  - `engine/`: Strategy backtesting pipelines (VectorBT, Backtrader, Backtesting.py).
  - `analytics/`: Financial metrics, indicators, and optimization algorithms (TA-Lib, PyPortfolioOpt, PyFolio, FFN).
  - `ui/`: Streamlit dashboard visual interface.
  - `jobs/`: Background pipelines and cron-like jobs (APScheduler).
  - `models/`: Database schemas, Pydantic settings models, and DTOs.
- `data/`: Root persistent data folder.
- `docs/`: Progress logs and execution documentation.
- `scripts/`: Administrative scripts and utility setup tasks.
