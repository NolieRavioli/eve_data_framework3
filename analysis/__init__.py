"""Analysis — data collection modules that fetch from ESI and write to DuckDB/SQLite.

Each domain gets its own subdirectory under analysis/.
Analysis modules own their table DDL via ensure_tables(con) / ensure_columns(con).
"""

