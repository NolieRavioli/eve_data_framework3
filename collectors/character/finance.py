"""collectors/character/finance.py — contracts, market orders, wallet, loyalty collectors.

Writes to the owner's per-entity DuckDB (`<owner_id>.duckdb`).
"""

from __future__ import annotations

import json
import logging

from core.io.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


# ─────────────────────────────────────────────────────────────────────────────
# DDL
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_contracts (
            character_id        BIGINT NOT NULL,
            contract_id         BIGINT NOT NULL,
            issuer_id           BIGINT NOT NULL,
            issuer_corporation_id BIGINT,
            assignee_id         BIGINT,
            acceptor_id         BIGINT,
            type                TEXT,
            status              TEXT,
            availability        TEXT,
            title               TEXT,
            for_corporation     BOOLEAN DEFAULT FALSE,
            date_issued         TIMESTAMP,
            date_expired        TIMESTAMP,
            date_accepted       TIMESTAMP,
            date_completed      TIMESTAMP,
            days_to_complete    INTEGER,
            start_location_id   BIGINT,
            end_location_id     BIGINT,
            price               DOUBLE DEFAULT 0,
            reward              DOUBLE DEFAULT 0,
            collateral          DOUBLE DEFAULT 0,
            buyout              DOUBLE DEFAULT 0,
            volume              DOUBLE DEFAULT 0,
            items_json          TEXT,
            bids_json           TEXT,
            fetched_at          TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, contract_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_market_orders (
            character_id    BIGINT NOT NULL,
            order_id        BIGINT NOT NULL,
            type_id         INTEGER NOT NULL,
            region_id       INTEGER,
            location_id     BIGINT,
            volume_total    INTEGER,
            volume_remain   INTEGER,
            min_volume      INTEGER DEFAULT 1,
            price           DOUBLE NOT NULL,
            is_buy_order    BOOLEAN DEFAULT FALSE,
            issued          TIMESTAMP,
            duration        INTEGER,
            order_range     TEXT,
            escrow          DOUBLE,
            is_corporation  BOOLEAN DEFAULT FALSE,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, order_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_market_history (
            character_id    BIGINT NOT NULL,
            order_id        BIGINT NOT NULL,
            type_id         INTEGER NOT NULL,
            region_id       INTEGER,
            location_id     BIGINT,
            price           DOUBLE,
            volume_total    INTEGER,
            volume_remain   INTEGER,
            issued          TIMESTAMP,
            state           TEXT,
            is_buy_order    BOOLEAN DEFAULT FALSE,
            escrow          DOUBLE,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, order_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_wallet_journal (
            character_id    BIGINT NOT NULL,
            id              BIGINT NOT NULL,
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
            PRIMARY KEY (character_id, id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_wallet_transactions (
            character_id    BIGINT NOT NULL,
            transaction_id  BIGINT NOT NULL,
            date            TIMESTAMP NOT NULL,
            type_id         INTEGER NOT NULL,
            location_id     BIGINT NOT NULL,
            unit_price      DOUBLE NOT NULL,
            quantity        INTEGER NOT NULL,
            client_id       BIGINT NOT NULL,
            is_buy          BOOLEAN DEFAULT FALSE,
            is_personal     BOOLEAN DEFAULT TRUE,
            journal_ref_id  BIGINT,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, transaction_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_loyalty_points (
            character_id    BIGINT NOT NULL,
            corporation_id  BIGINT NOT NULL,
            loyalty_points  INTEGER NOT NULL,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, corporation_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_wallet (
            character_id    BIGINT PRIMARY KEY,
            balance         DOUBLE NOT NULL,
            fetched_at      TIMESTAMP DEFAULT now()
        )
    """)


# ─────────────────────────────────────────────────────────────────────────────
# Contracts (with inline enrichment for bids + items)
# ─────────────────────────────────────────────────────────────────────────────

def populate_contracts(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/contracts/"
    headers = {"Authorization": f"Bearer {access_token}"}

    contracts = []
    resp = esi_get(url, headers=headers, params={"page": 1})
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[finance.contracts] ESI %s for char %s", resp.status_code, character_id)
        return
    contracts.extend(resp.json())
    total_pages = int(resp.headers.get("X-Pages", 1))
    for page in range(2, total_pages + 1):
        r = esi_get(url, headers=headers, params={"page": page})
        if r.ok:
            contracts.extend(r.json())

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for c in contracts:
            cid = c["contract_id"]
            # Inline enrichment: bids + items (bounded by contract count)
            bids_json = None
            items_json = None
            bids_url = f"{ESI_BASE}/characters/{character_id}/contracts/{cid}/bids/"
            br = esi_get(bids_url, headers=headers)
            if br.ok:
                bids_json = json.dumps(br.json())
            items_url = f"{ESI_BASE}/characters/{character_id}/contracts/{cid}/items/"
            ir = esi_get(items_url, headers=headers)
            if ir.ok:
                items_json = json.dumps(ir.json())

            con.execute("""
                INSERT INTO character_contracts
                    (character_id, contract_id, issuer_id, issuer_corporation_id,
                     assignee_id, acceptor_id, type, status, availability, title,
                     for_corporation, date_issued, date_expired, date_accepted,
                     date_completed, days_to_complete, start_location_id, end_location_id,
                     price, reward, collateral, buyout, volume, items_json, bids_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, contract_id) DO UPDATE SET
                    status = excluded.status, date_completed = excluded.date_completed,
                    items_json = excluded.items_json, bids_json = excluded.bids_json,
                    fetched_at = now()
            """, [character_id, cid, c.get("issuer_id"), c.get("issuer_corporation_id"),
                  c.get("assignee_id"), c.get("acceptor_id"), c.get("type"), c.get("status"),
                  c.get("availability"), c.get("title"), c.get("for_corporation", False),
                  c.get("date_issued"), c.get("date_expired"), c.get("date_accepted"),
                  c.get("date_completed"), c.get("days_to_complete"),
                  c.get("start_location_id"), c.get("end_location_id"),
                  c.get("price", 0), c.get("reward", 0), c.get("collateral", 0),
                  c.get("buyout", 0), c.get("volume", 0), items_json, bids_json])
    finally:
        con.close()
    logger.info("[finance.contracts] %d for char %s", len(contracts), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Market orders (active + history)
# ─────────────────────────────────────────────────────────────────────────────

def populate_orders(owner_id: int, character_id: int, access_token: str) -> None:
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{ESI_BASE}/characters/{character_id}/orders/"
    hist_url = f"{ESI_BASE}/characters/{character_id}/orders/history/"

    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[finance.orders] ESI %s for char %s", resp.status_code, character_id)
        return
    orders = resp.json()

    hist_orders = []
    hr = esi_get(hist_url, headers=headers, params={"page": 1})
    if hr.ok:
        hist_orders.extend(hr.json())
        for page in range(2, int(hr.headers.get("X-Pages", 1)) + 1):
            r2 = esi_get(hist_url, headers=headers, params={"page": page})
            if r2.ok:
                hist_orders.extend(r2.json())

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for o in orders:
            con.execute("""
                INSERT INTO character_market_orders
                    (character_id, order_id, type_id, region_id, location_id,
                     volume_total, volume_remain, min_volume, price, is_buy_order,
                     issued, duration, order_range, escrow, is_corporation, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, order_id) DO UPDATE SET
                    price = excluded.price, volume_remain = excluded.volume_remain,
                    fetched_at = now()
            """, [character_id, o["order_id"], o["type_id"], o.get("region_id"),
                  o.get("location_id"), o.get("volume_total"), o.get("volume_remain"),
                  o.get("min_volume", 1), o.get("price", 0), o.get("is_buy_order", False),
                  o.get("issued"), o.get("duration"), o.get("range"), o.get("escrow"),
                  o.get("is_corporation", False)])
        for o in hist_orders:
            con.execute("""
                INSERT INTO character_market_history
                    (character_id, order_id, type_id, region_id, location_id,
                     price, volume_total, volume_remain, issued, state,
                     is_buy_order, escrow, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, order_id) DO UPDATE SET
                    state = excluded.state, fetched_at = now()
            """, [character_id, o["order_id"], o["type_id"], o.get("region_id"),
                  o.get("location_id"), o.get("price"), o.get("volume_total"),
                  o.get("volume_remain"), o.get("issued"), o.get("state"),
                  o.get("is_buy_order", False), o.get("escrow")])
    finally:
        con.close()
    logger.info("[finance.orders] %d active, %d history for char %s",
                len(orders), len(hist_orders), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Wallet journal + transactions
# ─────────────────────────────────────────────────────────────────────────────

def populate_wallet(owner_id: int, character_id: int, access_token: str) -> None:
    headers = {"Authorization": f"Bearer {access_token}"}

    # Wallet balance (scalar float)
    balance: float | None = None
    bal_resp = esi_get(f"{ESI_BASE}/characters/{character_id}/wallet/", headers=headers)
    if bal_resp.ok:
        balance = float(bal_resp.json())
    elif bal_resp.status_code == 403:
        return
    else:
        logger.warning("[finance.wallet] balance ESI %s for char %s",
                       bal_resp.status_code, character_id)

    # Journal (paginated)
    journal = []
    j_url = f"{ESI_BASE}/characters/{character_id}/wallet/journal/"
    jr = esi_get(j_url, headers=headers, params={"page": 1})
    if jr.ok:
        journal.extend(jr.json())
        for page in range(2, int(jr.headers.get("X-Pages", 1)) + 1):
            r = esi_get(j_url, headers=headers, params={"page": page})
            if r.ok:
                journal.extend(r.json())

    # Transactions (paginated)
    transactions = []
    t_url = f"{ESI_BASE}/characters/{character_id}/wallet/transactions/"
    tr = esi_get(t_url, headers=headers, params={"page": 1})
    if tr.ok:
        transactions.extend(tr.json())
        for page in range(2, int(tr.headers.get("X-Pages", 1)) + 1):
            r = esi_get(t_url, headers=headers, params={"page": page})
            if r.ok:
                transactions.extend(r.json())

    if balance is None and not journal and not transactions:
        return

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        if balance is not None:
            con.execute("""
                INSERT INTO character_wallet (character_id, balance, fetched_at)
                VALUES (?, ?, now())
                ON CONFLICT (character_id) DO UPDATE SET
                    balance = excluded.balance, fetched_at = now()
            """, [character_id, balance])
        for j in journal:
            con.execute("""
                INSERT INTO character_wallet_journal
                    (character_id, id, date, ref_type, first_party_id, second_party_id,
                     amount, balance, reason, context_id, context_id_type, description,
                     tax, tax_receiver_id, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, id) DO NOTHING
            """, [character_id, j["id"], j.get("date"), j.get("ref_type"),
                  j.get("first_party_id"), j.get("second_party_id"), j.get("amount"),
                  j.get("balance"), j.get("reason"), j.get("context_id"),
                  j.get("context_id_type"), j.get("description"),
                  j.get("tax"), j.get("tax_receiver_id")])
        for t in transactions:
            con.execute("""
                INSERT INTO character_wallet_transactions
                    (character_id, transaction_id, date, type_id, location_id,
                     unit_price, quantity, client_id, is_buy, is_personal, journal_ref_id, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, transaction_id) DO NOTHING
            """, [character_id, t["transaction_id"], t.get("date"), t["type_id"],
                  t["location_id"], t["unit_price"], t["quantity"], t["client_id"],
                  t.get("is_buy", False), t.get("is_personal", True), t.get("journal_ref_id")])
    finally:
        con.close()
    logger.info("[finance.wallet] balance=%.2f, %d journal, %d txn for char %s",
                balance or 0.0, len(journal), len(transactions), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Loyalty points
# ─────────────────────────────────────────────────────────────────────────────

def populate_loyalty(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/loyalty/points/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[finance.loyalty] ESI %s for char %s", resp.status_code, character_id)
        return
    data = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for lp in data:
            con.execute("""
                INSERT INTO character_loyalty_points
                    (character_id, corporation_id, loyalty_points, fetched_at)
                VALUES (?, ?, ?, now())
                ON CONFLICT (character_id, corporation_id) DO UPDATE SET
                    loyalty_points = excluded.loyalty_points, fetched_at = now()
            """, [character_id, lp["corporation_id"], lp.get("loyalty_points", 0)])
    finally:
        con.close()
    logger.info("[finance.loyalty] %d corps for char %s", len(data), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Scope → Collector registry
# ─────────────────────────────────────────────────────────────────────────────

SCOPE_COLLECTORS: list[tuple[str, str, object]] = [
    ("esi-contracts.read_character_contracts.v1",   "contracts",  populate_contracts),
    ("esi-markets.read_character_orders.v1",        "orders",     populate_orders),
    ("esi-wallet.read_character_wallet.v1",         "wallet",     populate_wallet),
    ("esi-characters.read_loyalty.v1",              "loyalty",    populate_loyalty),
]
NO_SCOPE_COLLECTORS: list[tuple[str, object]] = []
