# esi/data_collector.py
"""
Orchestrates full data collection for a character and their corporation.
Called on first login (via SSO callback) and can also be triggered manually.
Each ESI module is submitted as an independent background task so failures
are isolated and retried without re-running the whole pipeline.
"""
import logging

from util import task_queue
from util.collection_scope import run_with_character_scope

# ── personal fetchers ─────────────────────────────────────────────────────────
from esi.personal_assets       import fetch_all_assets
from esi.personal_skills       import fetch_all_skills
from esi.personal_wallet       import fetch_all_wallets
from esi.personal_industry_jobs import fetch_all_industry
from esi.personal_bookmarks    import update_personal_bookmarks
from esi.personal_attributes   import fetch_all_attributes
from esi.personal_clones       import fetch_all_clones
from esi.personal_contacts     import fetch_all_contacts
from esi.personal_contracts    import fetch_all_contracts
from esi.personal_mail         import fetch_all_mail
from esi.personal_calendar     import fetch_all_calendar
from esi.personal_notifications import fetch_all_notifications
from esi.personal_standings    import fetch_all_standings
from esi.personal_fittings     import fetch_all_fittings
from esi.personal_location     import fetch_all_location
from esi.personal_planetary    import fetch_all_planetary
from esi.personal_fatigue      import fetch_all_fatigue
from esi.personal_loyalty      import fetch_all_loyalty
from esi.personal_medals       import fetch_all_medals
from esi.personal_mining       import fetch_all_mining
from esi.personal_orders       import fetch_all_orders
from esi.personal_killmails    import fetch_all_killmails

# ── corp fetchers ─────────────────────────────────────────────────────────────
from esi.corp_info             import fetch_all_corp_info
from esi.corp_assets_full      import fetch_all_corp_assets
from esi.corp_blueprints_full  import fetch_all_corp_blueprints
from esi.corp_contacts_full    import fetch_all_corp_contacts
from esi.corp_contracts_full   import fetch_all_corp_contracts
from esi.corp_customs_offices  import fetch_all_corp_customs_offices
from esi.corp_divisions        import fetch_all_corp_divisions
from esi.corp_industry_full    import fetch_all_corp_industry
from esi.corp_killmails_full   import fetch_all_corp_killmails
from esi.corp_members_full     import fetch_all_corp_members
from esi.corp_mining_full      import fetch_all_corp_mining
from esi.corp_orders_full      import fetch_all_corp_orders
from esi.corp_roles_full       import fetch_all_corp_roles
from esi.corp_standings_full   import fetch_all_corp_standings
from esi.corp_structures_full  import fetch_all_corp_structures
from esi.corp_wallet_full      import fetch_all_corp_wallet

logger = logging.getLogger(__name__)

# ── task registries ───────────────────────────────────────────────────────────

# (label_suffix, fn) — fn signature: fn(owner_id)
PERSONAL_TASKS = [
    ("assets",          fetch_all_assets),
    ("skills",          fetch_all_skills),
    ("wallet",          fetch_all_wallets),
    ("industry",        fetch_all_industry),
    ("bookmarks",       update_personal_bookmarks),
    ("attributes",      fetch_all_attributes),
    ("clones",          fetch_all_clones),
    ("contacts",        fetch_all_contacts),
    ("contracts",       fetch_all_contracts),
    ("mail",            fetch_all_mail),
    ("calendar",        fetch_all_calendar),
    ("notifications",   fetch_all_notifications),
    ("standings",       fetch_all_standings),
    ("fittings",        fetch_all_fittings),
    ("location",        fetch_all_location),
    ("planetary",       fetch_all_planetary),
    ("fatigue",         fetch_all_fatigue),
    ("loyalty",         fetch_all_loyalty),
    ("medals",          fetch_all_medals),
    ("mining",          fetch_all_mining),
    ("orders",          fetch_all_orders),
    ("killmails",       fetch_all_killmails),
]

CORP_TASKS = [
    ("corp_info",           fetch_all_corp_info),
    ("corp_assets",         fetch_all_corp_assets),
    ("corp_blueprints",     fetch_all_corp_blueprints),
    ("corp_contacts",       fetch_all_corp_contacts),
    ("corp_contracts",      fetch_all_corp_contracts),
    ("corp_customs_offices", fetch_all_corp_customs_offices),
    ("corp_divisions",      fetch_all_corp_divisions),
    ("corp_industry",       fetch_all_corp_industry),
    ("corp_killmails",      fetch_all_corp_killmails),
    ("corp_members",        fetch_all_corp_members),
    ("corp_mining",         fetch_all_corp_mining),
    ("corp_orders",         fetch_all_corp_orders),
    ("corp_roles",          fetch_all_corp_roles),
    ("corp_standings",      fetch_all_corp_standings),
    ("corp_structures",     fetch_all_corp_structures),
    ("corp_wallet",         fetch_all_corp_wallet),
]

# ── public API ────────────────────────────────────────────────────────────────


def _run_scoped_collection(fn, owner_id: int, character_id: int | None = None):
    if character_id is None:
        return fn(owner_id)
    return run_with_character_scope(fn, {character_id}, owner_id)


def enqueue_full_collection(owner_id: int, character_id: int | None = None) -> list[str]:
    """
    Submit one task per module to the shared private task queue.
    When character_id is supplied, all token lookups are scoped to that toon.
    """
    task_ids = []
    label_suffix = f"[char={character_id}]" if character_id is not None else ""
    for label, fn in PERSONAL_TASKS:
        task_ids.append(
            task_queue.enqueue(
                f"personal/{label}{label_suffix}",
                _run_scoped_collection,
                fn,
                owner_id,
                character_id,
                owner_id=owner_id,
                queue="private",
            )
        )
    for label, fn in CORP_TASKS:
        task_ids.append(
            task_queue.enqueue(
                f"{label}{label_suffix}",
                _run_scoped_collection,
                fn,
                owner_id,
                character_id,
                owner_id=owner_id,
                queue="private",
            )
        )
    logger.info(
        "[data_collector] Enqueued %s personal + %s corp tasks for owner %s%s",
        len(PERSONAL_TASKS),
        len(CORP_TASKS),
        owner_id,
        f" scoped to character {character_id}" if character_id is not None else "",
    )
    return task_ids


