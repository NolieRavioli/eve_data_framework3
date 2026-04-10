"""Identity models — placeholder.

All auth tables (auth_users, auth_siteAdmins, auth_userRoles) are managed via
raw DuckDB DDL in ``core/io/public.py``.  Character token storage lives in
per-owner DuckDB entity databases managed by ``core/io/entity_db.py``.

No ORM models remain — this module is kept as a namespace anchor for
``core.io.models``.
"""
