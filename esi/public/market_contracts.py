import logging

from util import sde_store
from util.esi_rate_limiter import esi_get
from util.utils import get_all_region_ids

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def fetch_public_contracts(region_id: int) -> list[dict]:
    all_contracts = []
    page = 1
    url = f"{ESI}/contracts/public/{region_id}/"

    while True:
        resp = esi_get(url, params={"page": page})
        if resp.status_code == 204:
            logger.info("[Contracts] Region %s: no contracts (204) on page %s", region_id, page)
            break

        resp.raise_for_status()
        page_data = resp.json()

        if not page_data:
            logger.info("[Contracts] Region %s: empty page %s, stopping early", region_id, page)
            break

        all_contracts.extend(page_data)
        total_pages = int(resp.headers.get("X-Pages", page))
        logger.info("[Contracts] Region %s: fetched page %s/%s", region_id, page, total_pages)

        if page >= total_pages:
            break
        page += 1

    return all_contracts


def store_contracts(region_id: int, contracts: list[dict]) -> None:
    rows = [{**contract, "region_id": region_id} for contract in contracts]
    sde_store.upsert_public_contracts(rows)
    logger.info("[Contracts] Region %s: stored %s contracts", region_id, len(contracts))


def fetch_all_public_contracts() -> None:
    logger.info("[Contracts] Starting full public contracts fetch")
    region_ids = get_all_region_ids()

    for region_id in region_ids:
        try:
            logger.info("[Contracts] === Region %s ===", region_id)
            contracts = fetch_public_contracts(region_id)
            if contracts:
                store_contracts(region_id, contracts)
        except Exception as exc:
            logger.exception("[Contracts] Failed fetching region %s: %s", region_id, exc)

    logger.info("[Contracts] Completed fetching all public contracts")
