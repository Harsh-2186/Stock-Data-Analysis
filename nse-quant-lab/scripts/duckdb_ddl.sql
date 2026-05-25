-- DDL for DuckDB historical price storage

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
);
