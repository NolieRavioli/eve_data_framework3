"""collectors/corp/market.py — corp_market_orders and corp_market_history."""

from __future__ import annotations

import logging

from core.db.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def _ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_market_orders (
            order_id        BIGINT PRIMARY KEY,
            type_id         INTEGER NOT NULL,
            location_id     BIGINT NOT NULL,
            region_id       INTEGER,
            volume_total    INTEGER,
            volume_remain   INTEGER,
            min_volume      INTEGER DEFAULT 1,
            price           DOUBLE NOT NULL,
            is_buy_order    BOOLEAN DEFAULT FALSE,
            issued          TIMESTAMP,
            issued_by       BIGINT,
            duration        INTEGER,
            order_range     TEXT,
            escrow          DOUBLE,
            wallet_division INTEGER,
            fetched_at      TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_market_history (
            order_id        BIGINT PRIMARY KEY,
            type_id         INTEGER NOT NULL,
            location_id     BIGINT,
            region_id       INTEGER,
            price           DOUBLE,
            volume_total    INTEGER,
            volume_remain   INTEGER,
            issued          TIMESTAMP,
            state           TEXT,
            is_buy_order    BOOLEAN DEFAULT FALSE,
            escrow          DOUBLE,
            wallet_division INTEGER,
            fetched_at      TIMESTAMP DEFAULT now()
        )
    """)


def _paginate(url: str, headers: dict) -> list:
    resp = esi_get(url, params={"page": 1}, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return []
        logger.warning("[corp.market] ESI %s for %s", resp.status_code, url)
        return []
    data = resp.json()
    total = int(resp.headers.get("X-Pages", 1))
    for page in range(2, total + 1):
        r = esi_get(url, params={"page": page}, headers=headers)
        if r.ok:
            data.extend(r.json())
    return data


def fetch_corp_orders(corporation_id: int, character_id: int, access_token: str) -> None:
    headers = {"Authorization": f"Bearer {access_token}"}
    orders = _paginate(f"{ESI_BASE}/corporations/{corporation_id}/orders/", headers)
    history = _paginate(f"{ESI_BASE}/corporations/{corporation_id}/orders/history/", headers)

    con = connect_entity(corporation_id)
    try:
        _ensure_tables(con)
        if orders:
            con.execute("DELETE FROM corp_market_orders")
            con.executemany("""
                INSERT INTO corp_market_orders
                    (order_id, type_id, location_id, region_id, volume_total, volume_remain,
                     min_volume, price, is_buy_order, issued, issued_by, duration,
                     order_range, escrow, wallet_division, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
            """, [(o["order_id"], o["type_id"], o["location_id"], o.get("region_id"),
                   o.get("volume_total"), o.get("volume_remain"), o.get("min_volume", 1),
                   o["price"], o.get("is_buy_order", False), o.get("issued"),
                   o.get("issued_by"), o.get("duration"), o.get("range"),
                   o.get("escrow"), o.get("wallet_division")) for o in orders])

        if history:
            for h in history:
                con.execute("""
                    INSERT INTO corp_market_history
                        (order_id, type_id, location_id, region_id, price, volume_total,
                         volume_remain, issued, state, is_buy_order, escrow, wallet_division, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                    ON CONFLICT (order_id) DO NOTHING
                """, [h["order_id"], h["type_id"], h.get("location_id"), h.get("region_id"),
                      h.get("price"), h.get("volume_total"), h.get("volume_remain"),
                      h.get("issued"), h.get("state"), h.get("is_buy_order", False),
                      h.get("escrow"), h.get("wallet_division")])
    finally:
        con.close()
    logger.info("[corp.market] %d orders, %d history for corp %s",
                len(orders), len(history), corporation_id)


def run_for_all_corps() -> None:
    from collectors.corp import get_corp_token_map
    token_map = get_corp_token_map()
    for corp_id, (char_id, access_token) in token_map.items():
        try:
            fetch_corp_orders(corp_id, char_id, access_token)
        except Exception:
            logger.exception("[corp.market] failed for corp %s", corp_id)
