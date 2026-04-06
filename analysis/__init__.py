"""
analysis/ — Data Collection Layer
==================================

This package contains ESI data collectors that fetch raw data from EVE Online's
ESI API and write it to the framework's databases (DuckDB for public data,
SQLite for per-character private data).

Architecture:
    analysis/<domain>/
        __init__.py       — re-exports entry-point functions
        <module>.py       — ensure_tables(), data-fetch/write functions

Write Discipline:
    - DuckDB writes → core.db.writer (db_write, db_executemany, db_write_dataframe)
    - DuckDB DDL → direct public.connect() (synchronous, idempotent)
    - DuckDB reads → direct public.connect() (no serialization needed)
    - SQLite writes → SQLAlchemy engine.connect() with WAL mode (per-owner engine)

Future:
    When true analysis modules are added (derived computation, not raw collection),
    this package may be renamed to collectors/ with analysis/ reserved for
    derived-data modules. See ``website layout.md`` Part 4 for the full rationale.
"""

