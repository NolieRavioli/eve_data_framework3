"""collectors/public_data — Public ESI collectors writing to shared DuckDB.

All modules in this package write to ``_publicData/public.duckdb`` via
``core.io.public.connect()``.  No per-entity DuckDB is involved.
"""
