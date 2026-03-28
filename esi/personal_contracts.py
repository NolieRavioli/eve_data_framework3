# esi/personal_contracts.py
import logging
from datetime import datetime

from db.database import get_private_session
from db.models import PersonalContract, PersonalContractItem
from util.esi_rate_limiter import esi_get
from util.utils import get_token

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def _dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def fetch_contracts(char_id: int, access_token: str) -> list:
    contracts, page = [], 1
    headers = {"Authorization": f"Bearer {access_token}"}
    while True:
        resp = esi_get(f"{ESI}/characters/{char_id}/contracts/",
                       headers=headers, params={"page": page})
        resp.raise_for_status()
        data = resp.json()
        contracts.extend(data)
        if page >= int(resp.headers.get("x-pages", 1)):
            break
        page += 1
    return contracts


def fetch_contract_items(char_id: int, contract_id: int, access_token: str) -> list:
    resp = esi_get(
        f"{ESI}/characters/{char_id}/contracts/{contract_id}/items/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return resp.json()


def store_contracts(owner_id: int, char_id: int, contracts: list, access_token: str):
    db = get_private_session(owner_id)
    db.query(PersonalContract).filter_by(character_id=char_id).delete()
    db.query(PersonalContractItem).filter_by(character_id=char_id).delete()

    for c in contracts:
        db.add(PersonalContract(
            contract_id=c["contract_id"],
            character_id=char_id,
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
            buyout=c.get("buyout"),
            collateral=c.get("collateral"),
            days_to_complete=c.get("days_to_complete"),
            start_location_id=c.get("start_location_id"),
            end_location_id=c.get("end_location_id"),
            for_corporation=c.get("for_corporation"),
        ))
        # Only fetch items for completed/outstanding contracts that have items
        if c.get("type") in ("item_exchange", "auction"):
            try:
                items = fetch_contract_items(char_id, c["contract_id"], access_token)
                for item in items:
                    db.add(PersonalContractItem(
                        record_id=item["record_id"],
                        contract_id=c["contract_id"],
                        character_id=char_id,
                        type_id=item["type_id"],
                        quantity=item.get("quantity", 1),
                        is_included=item.get("is_included", True),
                        is_singleton=item.get("is_singleton", False),
                        raw_quantity=item.get("raw_quantity"),
                    ))
            except Exception as ie:
                logger.warning(f"[contracts] Could not fetch items for contract {c['contract_id']}: {ie}")

    db.commit()
    db.close()


def fetch_all_contracts(owner_id: int):
    for char_id, token_row in get_token(owner_id).items():
        try:
            contracts = fetch_contracts(char_id, token_row["access_token"])
            store_contracts(owner_id, char_id, contracts, token_row["access_token"])
            logger.info(f"[contracts] Stored {len(contracts)} for {char_id}")
        except Exception as e:
            logger.error(f"[contracts] Failed for {char_id}: {e}")
