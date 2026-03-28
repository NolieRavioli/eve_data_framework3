# esi/corp_contracts_full.py
import logging

from db.database import get_private_session
from db.models import CorpContract, CorpContractItem
from util.esi_rate_limiter import esi_get
from util.utils import get_token
from esi._corp_helpers import get_corp_id_for_char, fetch_paginated, _dt

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def fetch_contract_items(corp_id: int, contract_id: int, access_token: str) -> list:
    resp = esi_get(
        f"{ESI}/corporations/{corp_id}/contracts/{contract_id}/items/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return resp.json()


def store_corp_contracts(owner_id: int, corp_id: int, contracts: list, access_token: str):
    db = get_private_session(owner_id)
    db.query(CorpContract).filter_by(corporation_id=corp_id).delete()
    db.query(CorpContractItem).filter_by(corporation_id=corp_id).delete()
    for c in contracts:
        db.add(CorpContract(
            contract_id=c["contract_id"],
            corporation_id=corp_id,
            issuer_id=c.get("issuer_id"),
            issuer_corporation_id=c.get("issuer_corporation_id"),
            assignee_id=c.get("assignee_id"),
            acceptor_id=c.get("acceptor_id"),
            contract_type=c.get("type"),
            availability=c.get("availability"),
            status=c.get("status"),
            date_issued=_dt(c.get("date_issued")),
            date_expired=_dt(c.get("date_expired")),
            date_accepted=_dt(c.get("date_accepted")),
            date_completed=_dt(c.get("date_completed")),
            title=c.get("title"),
            volume=c.get("volume"),
            price=c.get("price"),
            reward=c.get("reward"),
            collateral=c.get("collateral"),
            buyout=c.get("buyout"),
            start_location_id=c.get("start_location_id"),
            end_location_id=c.get("end_location_id"),
        ))
        if c.get("type") in ("item_exchange", "auction"):
            try:
                items = fetch_contract_items(corp_id, c["contract_id"], access_token)
                for item in items:
                    db.add(CorpContractItem(
                        record_id=item["record_id"],
                        contract_id=c["contract_id"],
                        corporation_id=corp_id,
                        type_id=item["type_id"],
                        quantity=item.get("quantity", 1),
                        is_included=item.get("is_included", True),
                        is_singleton=item.get("is_singleton", False),
                    ))
            except Exception as ie:
                logger.warning(f"[corp_contracts] Items failed for {c['contract_id']}: {ie}")
    db.commit()
    db.close()


def fetch_all_corp_contracts(owner_id: int):
    seen = set()
    for char_id, token_row in get_token(owner_id).items():
        corp_id = get_corp_id_for_char(owner_id, char_id)
        if not corp_id or corp_id in seen:
            continue
        seen.add(corp_id)
        try:
            contracts = fetch_paginated(
                f"{ESI}/corporations/{corp_id}/contracts/",
                token_row["access_token"], esi_get)
            store_corp_contracts(owner_id, corp_id, contracts, token_row["access_token"])
            logger.info(f"[corp_contracts] {len(contracts)} for corp {corp_id}")
        except Exception as e:
            logger.warning(f"[corp_contracts] Skipped corp {corp_id}: {e}")
