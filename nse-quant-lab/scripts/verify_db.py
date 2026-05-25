import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models import get_duckdb_conn, Base, Symbol, Strategy, Backtest


def verify_duckdb():
    print("Testing DuckDB connection...")
    conn = get_duckdb_conn(db_path="./data/test_prices.duckdb")
    try:
        # Load and run DDL
        ddl_path = Path(__file__).resolve().parent / "duckdb_ddl.sql"
        with open(ddl_path, "r") as f:
            ddl = f.read()
        conn.execute(ddl)
        print("DuckDB DDL applied successfully!")

        # Test query
        conn.execute(
            """
            INSERT OR REPLACE INTO prices (symbol, date, open, high, low, close, volume, source)
            VALUES ('RELIANCE', '2026-05-22', 2400.0, 2450.0, 2390.0, 2440.0, 1000000, 'NSE')
        """
        )
        row = conn.execute("SELECT * FROM prices").fetchone()
        print(f"Successfully queried DuckDB: {row}")

    finally:
        conn.close()
        # Clean up test database file
        Path("./data/test_prices.duckdb").unlink(missing_ok=True)


def verify_sqlalchemy():
    print("Testing SQLAlchemy Models compilation...")
    # Check that metadata has all tables
    tables = list(Base.metadata.tables.keys())
    print(f"Registered SQLAlchemy tables: {tables}")
    assert "symbols" in tables
    assert "strategies" in tables
    assert "backtests" in tables
    print("SQLAlchemy models compiled successfully!")


if __name__ == "__main__":
    verify_duckdb()
    verify_sqlalchemy()
    print("All validations completed successfully!")
