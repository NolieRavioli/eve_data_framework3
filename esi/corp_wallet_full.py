# esi/corp_wallet_full.py
import logging

from db.database import get_private_session
from db.models import CorpWalletJournal, CorpWalletTransaction
from util.esi_rate_limiter import esi_get
from util.utils import get_token
from esi._corp_helpers import get_corp_id_for_char, fetch_paginated, _dt

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"

DIVISIONS = range(1, 8)  # EVE corps have up to 7 wallet divisions


def fetch_division_journal(corp_id: int, division: int, access_token: str) -> list:
    return fetch_paginated(
        f"{ESI}/corporations/{corp_id}/wallets/{division}/journal/",
        access_token, esi_get)


def fetch_division_transactions(corp_id: int, division: int, access_token: str) -> list:
    return fetch_paginated(
        f"{ESI}/corporations/{corp_id}/wallets/{division}/transactions/",
        access_token, esi_get)


def store_corp_wallet(owner_id: int, corp_id: int, journal_by_div: dict, txn_by_div: dict):
    db = get_private_session(owner_id)
    db.query(CorpWalletJournal).filter_by(corporation_id=corp_id).delete()
    db.query(CorpWalletTransaction).filter_by(corporation_id=corp_id).delete()

    for div, entries in journal_by_div.items():
        for e in entries:
            db.add(CorpWalletJournal(
                journal_id=e["id"],
                division=div,
                corporation_id=corp_id,
                date=e.get("date", ""),
                description=e.get("description"),
                ref_type=e.get("ref_type"),
                amount=e.get("amount"),
                balance=e.get("balance"),
                context_id=e.get("context_id"),
                context_id_type=e.get("context_id_type"),
                first_party_id=e.get("first_party_id"),
                second_party_id=e.get("second_party_id"),
                reason=e.get("reason"),
            ))

    for div, txns in txn_by_div.items():
        for t in txns:
            db.add(CorpWalletTransaction(
                transaction_id=t["transaction_id"],
                division=div,
                corporation_id=corp_id,
                location_id=t.get("location_id", 0),
                type_id=t.get("type_id", 0),
                quantity=t.get("quantity", 0),
                amount=t.get("unit_price", 0.0) * t.get("quantity", 1),
                unit_price=t.get("unit_price", 0.0),
                date=_dt(t.get("date")),
                is_buy=t.get("is_buy", False),
                journal_ref_id=t.get("journal_ref_id"),
            ))

    db.commit()
    db.close()


def fetch_all_corp_wallet(owner_id: int):
    seen = set()
    for char_id, token_row in get_token(owner_id).items():
        corp_id = get_corp_id_for_char(owner_id, char_id)
        if not corp_id or corp_id in seen:
            continue
        seen.add(corp_id)
        try:
            journal_by_div, txn_by_div = {}, {}
            for div in DIVISIONS:
                try:
                    journal_by_div[div] = fetch_division_journal(corp_id, div, token_row["access_token"])
                except Exception:
                    journal_by_div[div] = []
                try:
                    txn_by_div[div] = fetch_division_transactions(corp_id, div, token_row["access_token"])
                except Exception:
                    txn_by_div[div] = []
            total_j = sum(len(v) for v in journal_by_div.values())
            total_t = sum(len(v) for v in txn_by_div.values())
            store_corp_wallet(owner_id, corp_id, journal_by_div, txn_by_div)
            logger.info(f"[corp_wallet] {total_j} journal, {total_t} txns for corp {corp_id}")
        except Exception as e:
            logger.warning(f"[corp_wallet] Skipped corp {corp_id}: {e}")
