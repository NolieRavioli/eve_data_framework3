"""analysis — Cross-entity ESI enrichment workers.

All modules write to existing tables (no DDL ownership) and start DISABLED in the scheduler.
They are safe to run manually at any time.
"""
