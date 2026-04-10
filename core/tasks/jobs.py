"""core/tasks/scheduler_jobs.py — hardcoded job catalog.

Call register_all_jobs(engine) once at startup.  The scheduler engine calls
this after its own table is ready so that job rows exist before the first tick.

To add a new scheduled job:
  1. Import the worker function (or reference it by dotted path).
  2. Append an entry to _JOBS.

Fields:
    job_id          — stable identifier; changing this creates a new row
    label           — display name shown in the scheduler UI
    fn              — callable (used at runtime); fn_path is derived automatically
    interval_s      — default interval in seconds
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _path(fn) -> str:
    return f"{fn.__module__}.{fn.__qualname__}"


# ---------------------------------------------------------------------------
# Job catalog — add new jobs here
# ---------------------------------------------------------------------------

def _build_catalog() -> list[dict]:
    jobs = []

    # ── Pre-existing live jobs (migrated import paths) ────────────────────────

    try:
        from collectors.public_data.market import fetch_region_orders
        jobs.append({
            "job_id": "market_refresh",
            "label": "Market Data Refresh",
            "fn": fetch_region_orders,
            "fn_path": _path(fetch_region_orders),
            "interval_s": 3600,
            "category": "market",
        })
    except Exception:
        logger.warning("[SchedulerJobs] Could not import market collector — skipping job")

    try:
        from collectors.public_data.structures import discover_structures
        jobs.append({
            "job_id": "structure_discovery",
            "label": "Structure Discovery",
            "fn": discover_structures,
            "fn_path": _path(discover_structures),
            "interval_s": 86400,
            "category": "market",
        })
    except Exception:
        logger.warning("[SchedulerJobs] Could not import structure collector — skipping job")

    try:
        from collectors.public_data.market import fetch_structure_orders
        jobs.append({
            "job_id": "structure_market_refresh",
            "label": "Structure Market Orders Refresh",
            "fn": fetch_structure_orders,
            "fn_path": _path(fetch_structure_orders),
            "interval_s": 3600,
            "category": "market",
        })
    except Exception:
        logger.warning("[SchedulerJobs] Could not import structure market collector — skipping job")

    try:
        from core.system.bootstrap import ensure_esi_ready as _ensure_esi_ready
        jobs.append({
            "job_id": "esi_spec_refresh",
            "label": "ESI Spec + Codegen Refresh",
            "fn": _ensure_esi_ready,
            "fn_path": _path(_ensure_esi_ready),
            "interval_s": 86400,
            "category": "system",
        })
    except Exception:
        logger.warning("[SchedulerJobs] Could not import bootstrap — skipping ESI spec refresh job")

    try:
        from collectors.character.extended import run_extended_refresh
        jobs.append({"job_id": "character_extended_refresh",
                     "label": "Character Extended Data Refresh",
                     "fn": run_extended_refresh, "fn_path": _path(run_extended_refresh),
                     "interval_s": 3600, "category": "character"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import character extended — skipping")

    # ── Phase 2: Skill Queue + Presence ───────────────────────────────────────

    try:
        from collectors.character.skillqueue import run_skillqueue_refresh
        jobs.append({"job_id": "character_skillqueue_refresh",
                     "label": "Character Skill Queue Refresh",
                     "fn": run_skillqueue_refresh, "fn_path": _path(run_skillqueue_refresh),
                     "interval_s": 1800, "category": "character"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import skillqueue — skipping")

    try:
        from collectors.character.presence import run_presence_refresh
        jobs.append({"job_id": "character_presence_refresh",
                     "label": "Character Presence Refresh",
                     "fn": run_presence_refresh, "fn_path": _path(run_presence_refresh),
                     "interval_s": 300, "category": "character"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import presence — skipping")

    # ── Phase 3: Corporation ──────────────────────────────────────────────────

    try:
        from collectors.corp.assets import run_for_all_corps as _corp_assets
        jobs.append({"job_id": "corp_assets_refresh", "label": "Corp Assets & Blueprints",
                     "fn": _corp_assets, "fn_path": _path(_corp_assets), "interval_s": 43200,
                     "category": "corporation"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import corp assets — skipping")

    try:
        from collectors.corp.contacts import run_for_all_corps as _corp_contacts
        jobs.append({"job_id": "corp_contacts_refresh", "label": "Corp Contacts & Standings",
                     "fn": _corp_contacts, "fn_path": _path(_corp_contacts), "interval_s": 43200,
                     "category": "corporation"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import corp contacts — skipping")

    try:
        from collectors.corp.contracts import run_for_all_corps as _corp_contracts
        jobs.append({"job_id": "corp_contracts_refresh", "label": "Corp Contracts",
                     "fn": _corp_contracts, "fn_path": _path(_corp_contracts), "interval_s": 14400,
                     "category": "corporation"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import corp contracts — skipping")

    try:
        from collectors.corp.industry import run_for_all_corps as _corp_industry
        jobs.append({"job_id": "corp_industry_refresh", "label": "Corp Industry & Mining",
                     "fn": _corp_industry, "fn_path": _path(_corp_industry), "interval_s": 1800,
                     "category": "corporation"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import corp industry — skipping")

    try:
        from collectors.corp.members import run_for_all_corps as _corp_members
        jobs.append({"job_id": "corp_members_refresh", "label": "Corp Members",
                     "fn": _corp_members, "fn_path": _path(_corp_members), "interval_s": 3600,
                     "category": "corporation"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import corp members — skipping")

    try:
        from collectors.corp.market import run_for_all_corps as _corp_market
        jobs.append({"job_id": "corp_market_refresh", "label": "Corp Market Orders",
                     "fn": _corp_market, "fn_path": _path(_corp_market), "interval_s": 3600,
                     "category": "corporation"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import corp market — skipping")

    try:
        from collectors.corp.infrastructure import run_for_all_corps as _corp_infra
        jobs.append({"job_id": "corp_infrastructure_refresh", "label": "Corp Infrastructure",
                     "fn": _corp_infra, "fn_path": _path(_corp_infra), "interval_s": 21600,
                     "category": "corporation"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import corp infrastructure — skipping")

    try:
        from collectors.corp.wallet import run_for_all_corps as _corp_wallet
        jobs.append({"job_id": "corp_wallet_refresh", "label": "Corp Wallet",
                     "fn": _corp_wallet, "fn_path": _path(_corp_wallet), "interval_s": 1800,
                     "category": "corporation"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import corp wallet — skipping")

    try:
        from collectors.corp.org import run_for_all_corps as _corp_org
        jobs.append({"job_id": "corp_org_refresh", "label": "Corp Org Data",
                     "fn": _corp_org, "fn_path": _path(_corp_org), "interval_s": 86400,
                     "category": "corporation"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import corp org — skipping")

    try:
        from collectors.corp.misc import run_for_all_corps as _corp_misc
        jobs.append({"job_id": "corp_misc_refresh", "label": "Corp Misc Data",
                     "fn": _corp_misc, "fn_path": _path(_corp_misc), "interval_s": 14400,
                     "category": "corporation"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import corp misc — skipping")

    try:
        from collectors.corp.stats import run_for_all_corps as _corp_stats
        jobs.append({"job_id": "corp_stats_refresh", "label": "Corp Stats & History",
                     "fn": _corp_stats, "fn_path": _path(_corp_stats), "interval_s": 86400,
                     "category": "corporation"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import corp stats — skipping")

    # ── Phase 4: Alliance ─────────────────────────────────────────────────────

    try:
        from collectors.alliance.contacts import run_for_all_alliances as _alliance_contacts
        jobs.append({"job_id": "alliance_contacts_refresh", "label": "Alliance Contacts",
                     "fn": _alliance_contacts, "fn_path": _path(_alliance_contacts),
                     "interval_s": 43200, "category": "alliance"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import alliance contacts — skipping")

    # ── Phase 5: Public Data ──────────────────────────────────────────────────

    try:
        from collectors.public_data.alliances import fetch_alliances
        jobs.append({"job_id": "alliances_refresh", "label": "Alliance Data",
                     "fn": fetch_alliances, "fn_path": _path(fetch_alliances), "interval_s": 86400,
                     "category": "public"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import alliances — skipping")

    try:
        from collectors.public_data.fw import fetch_fw_data
        jobs.append({"job_id": "fw_refresh", "label": "Faction Warfare Data",
                     "fn": fetch_fw_data, "fn_path": _path(fetch_fw_data), "interval_s": 3600,
                     "category": "public"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import FW — skipping")

    try:
        from collectors.public_data.sovereignty import fetch_sovereignty
        jobs.append({"job_id": "sovereignty_refresh", "label": "Sovereignty Data",
                     "fn": fetch_sovereignty, "fn_path": _path(fetch_sovereignty),
                     "interval_s": 1800, "category": "public"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import sovereignty — skipping")

    try:
        from collectors.public_data.universe_extras import fetch_universe_extras
        jobs.append({"job_id": "universe_extras_refresh", "label": "Universe Extras",
                     "fn": fetch_universe_extras, "fn_path": _path(fetch_universe_extras),
                     "interval_s": 3600, "category": "public"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import universe extras — skipping")

    try:
        from collectors.public_data.industry import fetch_industry_data
        jobs.append({"job_id": "industry_data_refresh", "label": "Industry Facilities & Costs",
                     "fn": fetch_industry_data, "fn_path": _path(fetch_industry_data),
                     "interval_s": 3600, "category": "public"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import industry data — skipping")

    try:
        from collectors.public_data.market import fetch_market_meta
        jobs.append({"job_id": "market_meta_refresh", "label": "Market Prices & Items",
                     "fn": fetch_market_meta, "fn_path": _path(fetch_market_meta),
                     "interval_s": 3600, "category": "market"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import market meta — skipping")

    # ── Phase 6: Market History Batch (starts DISABLED) ───────────────────────

    try:
        from collectors.public_data.market import fetch_active_market_history
        jobs.append({"job_id": "market_history_refresh", "label": "Market History Batch",
                     "fn": fetch_active_market_history, "fn_path": _path(fetch_active_market_history),
                     "interval_s": 86400, "category": "market"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import market history batch — skipping")

    # ── Phase 7: Analysis Enrichment (all start DISABLED) ────────────────────

    try:
        from analysis.affiliation_sync import run_affiliation_sync
        jobs.append({"job_id": "affiliation_sync", "label": "Character Affiliation Sync",
                     "fn": run_affiliation_sync, "fn_path": _path(run_affiliation_sync),
                     "interval_s": 3600, "category": "analysis"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import affiliation_sync — skipping")

    try:
        from analysis.asset_enrichment import run_asset_enrichment
        jobs.append({"job_id": "asset_enrichment", "label": "Asset Name & Position Enrichment",
                     "fn": run_asset_enrichment, "fn_path": _path(run_asset_enrichment),
                     "interval_s": 43200, "category": "analysis"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import asset_enrichment — skipping")

    try:
        from analysis.killmail_enrichment import run_killmail_enrichment
        jobs.append({"job_id": "killmail_enrichment", "label": "Killmail Detail Enrichment",
                     "fn": run_killmail_enrichment, "fn_path": _path(run_killmail_enrichment),
                     "interval_s": 86400, "category": "analysis"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import killmail_enrichment — skipping")

    try:
        from analysis.alliance_enrichment import run_alliance_enrichment
        jobs.append({"job_id": "alliance_enrichment", "label": "Alliance Detail Enrichment",
                     "fn": run_alliance_enrichment, "fn_path": _path(run_alliance_enrichment),
                     "interval_s": 86400, "category": "analysis"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import alliance_enrichment — skipping")

    try:
        from analysis.corporation_discovery import run_corporation_discovery
        jobs.append({"job_id": "corporation_discovery",
                     "label": "Corporation Discovery & Enrichment",
                     "fn": run_corporation_discovery,
                     "fn_path": _path(run_corporation_discovery), "interval_s": 86400,
                     "category": "analysis"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import corporation_discovery — skipping")

    try:
        from analysis.public_contract_enrichment import run_public_contract_enrichment
        jobs.append({"job_id": "public_contract_enrichment",
                     "label": "Public Contract Items & Bids",
                     "fn": run_public_contract_enrichment,
                     "fn_path": _path(run_public_contract_enrichment), "interval_s": 14400,
                     "category": "analysis"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import public_contract_enrichment — skipping")

    try:
        from analysis.war_enrichment import run_war_enrichment
        jobs.append({"job_id": "war_enrichment", "label": "War Detail & Killmail Enrichment",
                     "fn": run_war_enrichment, "fn_path": _path(run_war_enrichment),
                     "interval_s": 86400, "category": "analysis"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import war_enrichment — skipping")

    try:
        from analysis.freelance_enrichment import run_freelance_enrichment
        jobs.append({"job_id": "freelance_enrichment",
                     "label": "Freelance Job Detail Enrichment",
                     "fn": run_freelance_enrichment, "fn_path": _path(run_freelance_enrichment),
                     "interval_s": 14400, "category": "analysis"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import freelance_enrichment — skipping")

    try:
        from analysis.market_browser import run_market_browser
        jobs.append({"job_id": "market_browser_refresh", "label": "Universe Market Browser",
                     "fn": run_market_browser, "fn_path": _path(run_market_browser),
                     "interval_s": 3600, "category": "market"})
    except Exception:
        logger.warning("[SchedulerJobs] Could not import market_browser — skipping")

    return jobs


# Module-level catalog — built once on import
CATALOG: list[dict] = _build_catalog()


def register_all_jobs(engine) -> None:
    """Upsert all catalog entries into the scheduler_jobs table via *engine*."""
    for job in CATALOG:
        engine.register(
            job_id=job["job_id"],
            label=job["label"],
            fn=job["fn"],
            fn_path=job["fn_path"],
            interval_s=job["interval_s"],
            category=job.get("category", "other"),
        )
