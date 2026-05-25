import os
from pathlib import Path
import duckdb
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# ----------------- DuckDB Configuration -----------------
DUCKDB_PATH = os.getenv("DUCKDB_PATH", "./data/prices.duckdb")


def get_duckdb_conn(db_path: str = DUCKDB_PATH) -> duckdb.DuckDBPyConnection:
    """Establishes and returns a connection to the DuckDB file.

    Automatically handles the creation of any missing directories for the DB file.
    """
    path_obj = Path(db_path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path_obj))


# ----------------- PostgreSQL Configuration -----------------
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "nse_quant")

# Use standard postgresql+asyncpg driver for SQLAlchemy async interface
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
)

# Async SQLAlchemy Engine setup
engine = create_async_engine(DATABASE_URL, echo=False)

# SessionMaker generating AsyncSession instances for database requests
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
