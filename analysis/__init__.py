"""Analysis — domain-specific data collection from ESI, written to DuckDB/SQLite.

Each domain gets its own subdirectory under analysis/.
Analysis modules own their table DDL via ensure_tables(con) / ensure_columns(con).

Note: The SDE pipeline (download → unzip → build warehouse) is a framework-level
task and lives in core/tasks/sde_loader.py rather than here.  Analysis collectors
may call core.tasks.sde_loader functions if they need to trigger SDE rebuilds.
"""

