# Collectors

A **collector** is a Python module that fetches data from an external source (almost always the EVE ESI API) and writes it to the shared DuckDB warehouse or a character's private SQLite database. Collectors run as background tasks — either on a schedule or triggered manually from the UI.

---

## When to Write a Collector

Write a collector when you need to:
- Periodically fetch data from ESI and persist it
- Build a local DuckDB table that an application can query
- Collect per-character data from ESI into private SQLite

Do **not** write a collector for:
- One-off calculations on already-fetched data → use an [analysis worker](analysis)
- Serving data to the browser → that belongs in an [application route](creating-a-new-application)

---

## Collector Reference

<!-- inject:collectors -->

---

## Creating a New Collector

<!-- inject:task_new_collector -->

---

## Built-In Collectors

| Collector | Module | Target | Key Tables |
|-----------|--------|--------|------------|
| **Market Orders** | `collectors/market/regions.py` | DuckDB | `market_orders`, `market_region_cooldowns` |
| **Structure Markets** | `collectors/market/structures.py` | DuckDB | `market_structures` |
| **Market History** | `collectors/market/history.py` | DuckDB | `market_history` |
| **Structures** | `collectors/structures/discover.py` | DuckDB | `structures` |
| **Character Data** | `collectors/character/populate.py` | SQLite | `character_skills`, `character_wallet`, `character_assets` |

---

## Rules

1. **All ESI HTTP** goes through `core.esi` functions — never use `requests` directly
2. **Table DDL** lives in the owning collector's `ensure_tables()` — never in `core/io/public.py`
3. **Call `ensure_tables(con)` before any writes** — every `connect()` should be followed by `ensure_tables()`
4. **Thread-safe DuckDB** — get a fresh `db.connect()` per call; never share connections across threads
5. **Import from `core.*` only** — collectors never import from `applications/`
6. **Use the serialized writer** for multi-threaded write scenarios — `db_write()` and `db_executemany()`
