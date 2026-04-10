"""collectors/corp/wallet.py — corp_wallets, corp_wallet_journals, corp_wallet_transactions, corp_killmails."""

from __future__ import annotations

import logging

from core.db.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"

_DIVISIONS = list(range(1, 8))  # wallet divisions 1-7


def _ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_wallets (
            division    INTEGER PRIMARY KEY,
            balance     DOUBLE NOT NULL,
            fetched_at  TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_wallet_journals (
            id              BIGINT NOT NULL,
            division        INTEGER NOT NULL,
            date            TIMESTAMP NOT NULL,
            ref_type        TEXT,
            first_party_id  BIGINT,
            second_party_id BIGINT,
            amount          DOUBLE,
            balance         DOUBLE,
            reason          TEXT,
            context_id      BIGINT,
            context_id_type TEXT,
            description     TEXT,
            tax             DOUBLE,
            tax_receiver_id BIGINT,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (id, division)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_wallet_transactions (
            transaction_id  BIGINT NOT NULL,
            division        INTEGER NOT NULL,
            date            TIMESTAMP NOT NULL,
            type_id         INTEGER NOT NULL,
            location_id     BIGINT NOT NULL,
            unit_price      DOUBLE NOT NULL,
            quantity        INTEGER NOT NULL,
            client_id       BIGINT NOT NULL,
            is_buy          BOOLEAN DEFAULT FALSE,
            journal_ref_id  BIGINT,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (transaction_id, division)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_killmails (
            killmail_id     BIGINT PRIMARY KEY,
            killmail_hash   TEXT NOT NULL,
            details_json    TEXT,
            fetched_at      TIMESTAMP DEFAULT now()
        )
    """)


def fetch_corp_wallet(corporation_id: int, character_id: int, access_token: str) -> None:
    headers = {"Authorization": f"Bearer {access_token}"}
    con = connect_entity(corporation_id)
    try:
        _ensure_tables(con)

        # Wallet balances
        w_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/wallets/", headers=headers)
        if w_resp.ok:
            for w in w_resp.json():
                con.execute("""
                    INSERT INTO corp_wallets (division, balance, fetched_at)
                    VALUES (?, ?, now())
                    ON CONFLICT (division) DO UPDATE SET balance = excluded.balance, fetched_at = now()
                """, [w["division"], w["balance"]])

        # Wallet journals per division (paginated)
        for div in _DIVISIONS:
            j_resp = esi_get(
                f"{ESI_BASE}/corporations/{corporation_id}/wallets/{div}/journal/",
                params={"page": 1}, headers=headers)
            if not j_resp.ok:
                continue
            journal = j_resp.json()
            total = int(j_resp.headers.get("X-Pages", 1))
            for page in range(2, total + 1):
                r = esi_get(
                    f"{ESI_BASE}/corporations/{corporation_id}/wallets/{div}/journal/",
                    params={"page": page}, headers=headers)
                if r.ok:
                    journal.extend(r.json())
            con.executemany("""
                INSERT INTO corp_wallet_journals
                    (id, division, date, ref_type, first_party_id, second_party_id,
                     amount, balance, reason, context_id, context_id_type, description,
                     tax, tax_receiver_id, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (id, division) DO NOTHING
            """, [(j["id"], div, j.get("date"), j.get("ref_type"),
                   j.get("first_party_id"), j.get("second_party_id"),
                   j.get("amount"), j.get("balance"), j.get("reason"),
                   j.get("context_id"), j.get("context_id_type"), j.get("description"),
                   j.get("tax"), j.get("tax_receiver_id")) for j in journal])

        # Wallet transactions per division (paginated)
        for div in _DIVISIONS:
            t_resp = esi_get(
                f"{ESI_BASE}/corporations/{corporation_id}/wallets/{div}/transactions/",
                params={"page": 1}, headers=headers)
            if not t_resp.ok:
                continue
            txns = t_resp.json()
            total = int(t_resp.headers.get("X-Pages", 1))
            for page in range(2, total + 1):
                r = esi_get(
                    f"{ESI_BASE}/corporations/{corporation_id}/wallets/{div}/transactions/",
                    params={"page": page}, headers=headers)
                if r.ok:
                    txns.extend(r.json())
            con.executemany("""
                INSERT INTO corp_wallet_transactions
                    (transaction_id, division, date, type_id, location_id, unit_price,
                     quantity, client_id, is_buy, journal_ref_id, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (transaction_id, division) DO NOTHING
            """, [(t["transaction_id"], div, t.get("date"), t["type_id"],
                   t["location_id"], t["unit_price"], t["quantity"],
                   t["client_id"], t.get("is_buy", False), t.get("journal_ref_id"))
                  for t in txns])

        # Killmails (paginated)
        km_resp = esi_get(
            f"{ESI_BASE}/corporations/{corporation_id}/killmails/recent/",
            params={"page": 1}, headers=headers)
        if km_resp.ok:
            killmails = km_resp.json()
            total = int(km_resp.headers.get("X-Pages", 1))
            for page in range(2, total + 1):
                r = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/killmails/recent/",
                            params={"page": page}, headers=headers)
                if r.ok:
                    killmails.extend(r.json())
            con.executemany("""
                INSERT INTO corp_killmails (killmail_id, killmail_hash, fetched_at)
                VALUES (?, ?, now())
                ON CONFLICT (killmail_id) DO NOTHING
            """, [(km["killmail_id"], km.get("killmail_hash", "")) for km in killmails])
    finally:
        con.close()
    logger.info("[corp.wallet] updated for corp %s", corporation_id)


def run_for_all_corps() -> None:
    from collectors.corp import get_corp_token_map
    token_map = get_corp_token_map()
    for corp_id, (char_id, access_token) in token_map.items():
        try:
            fetch_corp_wallet(corp_id, char_id, access_token)
        except Exception:
            logger.exception("[corp.wallet] failed for corp %s", corp_id)
