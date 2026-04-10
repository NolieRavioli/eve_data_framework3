"""
collectors/ — Data Collection Layer
====================================

This package contains ESI data collectors that fetch raw data from EVE Online's
ESI API and write it to the framework's databases (DuckDB for public data,
per-entity DuckDB for per-character private data).

Architecture:
    collectors/<domain>/
        __init__.py       — re-exports entry-point functions
        <module>.py       — ensure_tables(), data-fetch/write functions

Write Discipline:
    - DuckDB writes → core.db.writer (db_write, db_executemany, db_write_dataframe)
    - DuckDB DDL → direct public.connect() (synchronous, idempotent)
    - DuckDB reads → direct public.connect() (no serialization needed)
    - Entity DuckDB writes → core.db.entity_db.connect_entity() per owner
"""

