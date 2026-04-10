"""core/system/bootstrap.py — Subsystem readiness and update orchestration.

Called from ``main.py`` to ensure the SDE warehouse and ESI generated packages
are current before the server starts serving requests.

Public API
----------
bootstrap_all(settings)        — single entry point for main.py
ensure_sde_ready(auto_update)  — SDE warehouse readiness check + optional update
ensure_esi_ready(auto_update)  — ESI codegen readiness check + optional regenerate
prepare_sde_sources()          — ensure _sde/fsd exists (download if needed, no cleanup)
update_sde_full()              — full SDE: download → schema regen → warehouse → cleanup
update_esi_full(date)          — ESI spec fetch + codegen regeneration
update_config()                — regenerate example.config.yaml
get_subsystem_status()         — read-only status dict for all subsystems
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def get_subsystem_status() -> dict:
    """Return a read-only status dict for SDE warehouse, ESI spec, and ESI codegen."""
    status: dict = {
        "sde": {"ok": False},
        "esi_spec": {"ok": False},
        "esi_codegen": {"ok": False},
    }

    # SDE warehouse
    try:
        import core.io.public as _pub
        ws = _pub.get_warehouse_status()
        manifest = ws.get("manifest") or {}
        status["sde"] = {
            "ok": ws.get("initialized", False),
            "available": ws.get("available", False),
            "table_count": len(ws.get("tables") or []),
            "build_finished_at": manifest.get("build_finished_at"),
            "source_etag": manifest.get("source_etag"),
            "source_last_modified": manifest.get("source_last_modified"),
            "sde_version": manifest.get("sde_version"),
        }
    except Exception as exc:
        status["sde"] = {"ok": False, "detail": str(exc)}

    # ESI spec registry
    try:
        from core.esi.registry import get_registry_status
        reg = get_registry_status()
        status["esi_spec"] = {
            "ok": bool(reg.get("compatibility_date")),
            "compatibility_date": reg.get("compatibility_date"),
            "route_count": reg.get("route_count"),
            "scope_count": reg.get("scope_count"),
            "schema_count": reg.get("schema_count"),
        }
    except Exception as exc:
        status["esi_spec"] = {"ok": False, "detail": str(exc)}

    # ESI codegen (generated package)
    try:
        from core.esi.generated import COMPATIBILITY_DATE, OPERATION_COUNT
        status["esi_codegen"] = {
            "ok": True,
            "compatibility_date": COMPATIBILITY_DATE,
            "operation_count": OPERATION_COUNT,
        }
    except Exception as exc:
        status["esi_codegen"] = {"ok": False, "detail": str(exc)}

    return status


# ---------------------------------------------------------------------------
# SDE pipeline
# ---------------------------------------------------------------------------

def prepare_sde_sources() -> None:
    """Ensure SDE YAML sources exist locally.

    Downloads, extracts, and prunes the SDE archive if ``_sde/fsd/`` is missing.
    Does NOT clean up the downloaded archive or trigger a warehouse rebuild —
    this is the lightweight path used by build.py to make YAML files available
    for schema generation without a full runtime update cycle.

    If the SDE sources are already present this is a no-op.
    """
    import os
    sde_root = Path(os.getenv("SDE_PATH", "_sde"))
    if any(sde_root.glob("*.jsonl")):
        return  # Already available

    logger.info("SDE sources not found — downloading and preparing...")
    from core.io.sde_loader import download_sde, unzip_sde
    download_sde()
    unzip_sde()
    logger.info("SDE sources ready.")


def update_sde_full() -> dict:
    """Full SDE pipeline: download → extract → prune → schema regen → warehouse → cleanup.

    Unlike ``core.io.sde_loader.update_sde()``, this function regenerates
    ``core/io/generated/sde_schema.json`` from the freshly extracted YAML files
    *before* building the warehouse.  This keeps the schema in sync whenever CCP
    adds new SDE columns or tables between releases.

    Returns the warehouse status dict from ``core.io.sde_loader.rebuild_sde_warehouse()``.
    """
    from core.io.sde_loader import (
        download_sde, unzip_sde,
        rebuild_sde_warehouse, cleanup,
    )
    from utils.build.sde_codegen import generate_sde_schema

    logger.info("Starting full SDE update pipeline...")
    source_meta = download_sde()
    try:
        unzip_sde()
        logger.info("Regenerating SDE schema from extracted JSONL files...")
        sde_result = generate_sde_schema()
        logger.info("SDE schema done — %d tables", sde_result["table_count"])
        status = rebuild_sde_warehouse(source_meta)
    finally:
        cleanup()

    logger.info("SDE update complete.")
    return status


# ---------------------------------------------------------------------------
# ESI pipeline
# ---------------------------------------------------------------------------

def update_esi_full(date: str | None = None) -> dict:
    """Refresh ESI spec, regenerate cache DDL, ESI codegen, and domain collectors.

    Steps:
      1. ``refresh_esi_spec_registry(date)``   — fetch + persist OpenAPI spec
      2. ``generate_cache_schema(date)``        — regenerate cache_ddl.py
      3. ``generate(date)``                     — regenerate core/esi/generated/
      4. ``generate_collectors(date)``          — regenerate personal/corp/public/

    Returns a summary dict with keys: compatibility_date, route_count,
    scope_count, operation_count, schema_count, personal_files, corp_files,
    public_files.
    """
    from core.esi.registry import refresh_esi_spec_registry
    from utils.build.cache_codegen import generate_cache_schema
    from utils.build.esi_codegen import generate
    from utils.build.domain_codegen import generate_collectors

    logger.info("Refreshing ESI spec (date=%s)...", date or "latest")
    spec_status = refresh_esi_spec_registry(compatibility_date=date)
    compat_date = spec_status.get("compatibility_date")

    logger.info("Regenerating ESI cache DDL...")
    generate_cache_schema(compatibility_date=compat_date, force=True)

    logger.info("Regenerating ESI codegen packages...")
    codegen_result = generate(compatibility_date=compat_date, force=True)

    logger.info("Regenerating domain collector packages...")
    collector_result = generate_collectors(compatibility_date=compat_date, force=True)

    logger.info(
        "ESI update complete — %d operations.",
        codegen_result["operation_count"],
    )
    return {
        "compatibility_date": compat_date,
        "route_count": spec_status.get("route_count", 0),
        "scope_count": spec_status.get("scope_count", 0),
        "operation_count": codegen_result["operation_count"],
        "schema_count": codegen_result["schema_count"],
        "personal_files": collector_result["personal_files"],
        "corp_files": collector_result["corp_files"],
        "public_files": collector_result["public_files"],
    }


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def update_config() -> str:
    """Regenerate ``example.config.yaml``. Returns the path written."""
    from utils.build.config_codegen import generate_example_config
    path = generate_example_config()
    logger.info("example.config.yaml regenerated at %s", path)
    return path


# ---------------------------------------------------------------------------
# Readiness checks
# ---------------------------------------------------------------------------

def ensure_esi_ready(auto_update: bool = True) -> None:
    """Ensure the ESI spec and generated packages are present and current.

    Compares the COMPATIBILITY_DATE in ``core/esi/generated/__init__.py`` against
    ``_esi_specs/latest.json``.  If stale (or either file is missing),
    triggers a full ESI update when *auto_update* is True.

    Network or generation failures are caught and logged as warnings so they do
    not prevent the server from starting with existing (possibly stale) codegen.
    """
    latest_json = Path(
        __import__("os").getenv("ESI_SPECS_FOLDER", "_esi_specs")
    ) / "latest.json"

    if not latest_json.exists():
        if auto_update:
            logger.info("ESI spec not found — fetching and regenerating...")
            try:
                update_esi_full()
            except Exception as exc:
                logger.warning(
                    "ESI update failed: %s — continuing with existing codegen.", exc
                )
        else:
            logger.warning("ESI spec not found; auto-update disabled.")
        return

    try:
        from utils.build.esi_codegen import check_generated_is_current
        check_generated_is_current()
        logger.info("ESI codegen is current.")
    except RuntimeError as exc:
        if auto_update:
            logger.info("ESI codegen stale (%s) — regenerating...", exc)
            try:
                update_esi_full()
            except Exception as update_exc:
                logger.warning(
                    "ESI update failed: %s — continuing with existing codegen.",
                    update_exc,
                )
        else:
            logger.warning(
                "ESI codegen stale: %s; auto-update disabled.", exc
            )
    except Exception as exc:
        logger.warning("Could not verify ESI codegen currency: %s", exc)


def ensure_sde_ready(auto_update: bool = True) -> None:
    """Ensure the SDE warehouse is present and current.

    If the warehouse is missing or ETag-stale, triggers a full SDE update when
    *auto_update* is True.  Network or build failures are caught and logged so
    startup continues with whatever state the warehouse is currently in.
    """
    from core.io.sde_loader import warehouse_exists, check_sde_currency

    if not warehouse_exists():
        if auto_update:
            logger.info("SDE warehouse not found — building...")
            try:
                update_sde_full()
            except Exception as exc:
                logger.warning(
                    "SDE update failed: %s — startup will continue without SDE.", exc
                )
        else:
            logger.warning("SDE warehouse not found; auto-update disabled.")
        return

    currency = check_sde_currency()
    if currency["error"]:
        logger.warning(
            "Could not check SDE currency: %s (assuming current)",
            currency["error"],
        )
        return

    if not currency["current"]:
        if auto_update:
            logger.info(
                "SDE stale (local=%s, remote=%s) — updating...",
                currency["local_build"], currency["remote_build"],
            )
            try:
                update_sde_full()
            except Exception as exc:
                logger.warning(
                    "SDE update failed: %s — continuing with existing warehouse.", exc
                )
        else:
            logger.warning(
                "SDE is stale (local=%s, remote=%s); auto-update disabled.",
                currency["local_build"], currency["remote_build"],
            )
    else:
        logger.info("SDE warehouse is current.")


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def bootstrap_all(settings) -> None:
    """Ensure SDE and ESI subsystems are ready for the server to start.

    Called from ``main.py`` after the DB writer is running and the public schema
    exists.  Reads ``bootstrap_esi`` and ``bootstrap_sde`` from *settings* to
    decide whether to auto-update each subsystem — both default to ``True`` when
    not set.

    ESI is checked before SDE so that regenerated codegen is in place before the
    SDE warehouse build (which may sync the ESI registry into DuckDB).
    """
    esi_enabled = getattr(settings, "bootstrap_esi", True)
    sde_enabled = getattr(settings, "bootstrap_sde", True)

    if esi_enabled:
        ensure_esi_ready(auto_update=True)
    else:
        logger.info(
            "ESI auto-update disabled by config (Bootstrap.auto_update_esi: false)."
        )

    if sde_enabled:
        ensure_sde_ready(auto_update=True)
    else:
        logger.info(
            "SDE auto-update disabled by config (Bootstrap.auto_update_sde: false)."
        )
