"""collectors/corp/contracts.py — corp_contracts with inline bids/items enrichment."""

from __future__ import annotations

import json
import logging

from core.io.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def _ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_contracts (
            contract_id         BIGINT PRIMARY KEY,
            acceptor_id         BIGINT,
            assignee_id         BIGINT,
            issuer_id           BIGINT NOT NULL,
            issuer_corporation_id BIGINT,
            status              TEXT,
            type                TEXT,
            availability        TEXT,
            for_corporation     BOOLEAN DEFAULT FALSE,
            date_issued         TIMESTAMP,
            date_expired        TIMESTAMP,
            date_accepted       TIMESTAMP,
            date_completed      TIMESTAMP,
            days_to_complete    INTEGER,
            end_location_id     BIGINT,
            start_location_id   BIGINT,
            price               DOUBLE DEFAULT 0,
            reward              DOUBLE DEFAULT 0,
            collateral          DOUBLE DEFAULT 0,
            buyout              DOUBLE DEFAULT 0,
            volume              DOUBLE DEFAULT 0,
            title               TEXT,
            items_json          TEXT,
            bids_json           TEXT,
            fetched_at          TIMESTAMP DEFAULT now()
        )
    """)


def fetch_corp_contracts(corporation_id: int, character_id: int, access_token: str) -> None:
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/contracts/",
                   params={"page": 1}, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[corp.contracts] ESI %s for corp %s", resp.status_code, corporation_id)
        return
    data = resp.json()
    total = int(resp.headers.get("X-Pages", 1))
    for page in range(2, total + 1):
        r = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/contracts/",
                    params={"page": page}, headers=headers)
        if r.ok:
            data.extend(r.json())

    con = connect_entity(corporation_id)
    try:
        _ensure_tables(con)
        for c in data:
            cid = c["contract_id"]
            # Inline enrichments
            items_json = None
            bids_json = None
            items_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/contracts/{cid}/items/",
                                 headers=headers)
            if items_resp.ok:
                items_json = json.dumps(items_resp.json())
            bids_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/contracts/{cid}/bids/",
                                headers=headers)
            if bids_resp.ok:
                bids_json = json.dumps(bids_resp.json())

            con.execute("""
                INSERT INTO corp_contracts
                    (contract_id, acceptor_id, assignee_id, issuer_id, issuer_corporation_id,
                     status, type, availability, for_corporation,
                     date_issued, date_expired, date_accepted, date_completed, days_to_complete,
                     end_location_id, start_location_id, price, reward, collateral, buyout, volume,
                     title, items_json, bids_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (contract_id) DO UPDATE SET
                    status = excluded.status, fetched_at = now()
            """, [cid, c.get("acceptor_id"), c.get("assignee_id"), c["issuer_id"],
                  c.get("issuer_corporation_id"), c.get("status"), c.get("type"),
                  c.get("availability"), c.get("for_corporation", False),
                  c.get("date_issued"), c.get("date_expired"), c.get("date_accepted"),
                  c.get("date_completed"), c.get("days_to_complete"),
                  c.get("end_location_id"), c.get("start_location_id"),
                  c.get("price", 0), c.get("reward", 0), c.get("collateral", 0),
                  c.get("buyout", 0), c.get("volume", 0), c.get("title"),
                  items_json, bids_json])
    finally:
        con.close()
    logger.info("[corp.contracts] %d for corp %s", len(data), corporation_id)


def run_for_all_corps() -> None:
    from collectors.corp import get_corp_token_map
    token_map = get_corp_token_map()
    for corp_id, (char_id, access_token) in token_map.items():
        try:
            fetch_corp_contracts(corp_id, char_id, access_token)
        except Exception:
            logger.exception("[corp.contracts] failed for corp %s", corp_id)
