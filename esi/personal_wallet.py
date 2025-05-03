# fetchers/private/personal_wallet.py

import requests
import logging
from datetime import datetime

from db.database import get_private_session
from db.models import WalletTransaction
from util.utils import get_token

logger = logging.getLogger(__name__)

ESI = "https://esi.evetech.net/latest"

# ──────── Fetching ─────────────────────────────────────────────────────────────

def fetch_wallet_journal(char_id: int, access_token: str) -> list:
    """Fetch wallet journal entries for a character."""
    url = f"{ESI}/characters/{char_id}/wallet/journal/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()

# ──────── Storage ───────────────────────────────────────────────────────────────

def store_wallet_journal(owner_id: int, char_id: int, entries: list):
    """Store wallet journal entries into owner's private database."""
    db = get_private_session(owner_id)

    for entry in entries:
        txn_id = entry.get("id") or entry.get("ref_id")
        date = datetime.fromisoformat(entry["date"].replace("Z", "+00:00"))
        db.merge(WalletTransaction(
            id=txn_id,
            character_id=char_id,
            amount=entry.get("amount"),
            date=date,
            ref_type=entry.get("ref_type"),
            context_id=entry.get("context_id"),
            context_id_type=entry.get("context_id_type"),
        ))

    db.commit()
    db.close()

# ──────── Orchestrator ───────────────────────────────────────────────────────────

def fetch_all_wallets(owner_id: int):
    """Fetch and store wallet journals for all characters owned by the given owner."""
    tokens = get_token(owner_id)

    for char_id, token_row in tokens.items():
        logger.info(f"[fetch_all_wallets] Fetching wallet journal for {char_id}")
        try:
            entries = fetch_wallet_journal(char_id, token_row["access_token"])
            store_wallet_journal(owner_id, char_id, entries)
            logger.info(f"[fetch_all_wallets] Stored {len(entries)} transactions for {char_id}")
        except requests.HTTPError as e:
            logger.error(f"[fetch_all_wallets] Failed to fetch wallet journal for {char_id}: {e}")
