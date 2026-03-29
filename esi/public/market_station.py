import logging
import time

import requests

from util import sde_store
from util.esi_rate_limiter import esi_get
from util.utils import get_all_region_ids

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"
HEADERS = {"Accept": "application/json"}


def fetch_with_retries(url: str, params: dict, max_retries: int = 3) -> requests.Response:
    backoff = 1
    for attempt in range(1, max_retries + 1):
        try:
            resp = esi_get(url, headers=HEADERS, params=params)
            if resp.status_code == 420:
                logger.warning("420 rate limit on %s, sleeping 5s (attempt %s)", url, attempt)
                time.sleep(5)
                continue
            if resp.status_code in (429, 502, 503, 504):
                logger.warning(
                    "%s on %s, retrying after %ss (attempt %s)",
                    resp.status_code,
                    url,
                    backoff,
                    attempt,
                )
                time.sleep(backoff)
                backoff *= 2
                continue
            return resp
        except requests.RequestException as exc:
            logger.warning("Request error on %s (attempt %s): %s", url, attempt, exc)
            time.sleep(backoff)
            backoff *= 2
    return esi_get(url, headers=HEADERS, params=params)


def fetch_market_orders(region_id: int, page: int = 1) -> tuple[list, int]:
    url = f"{ESI_BASE}/markets/{region_id}/orders/"
    params = {"order_type": "all", "page": page, "datasource": "tranquility"}
    resp = fetch_with_retries(url, params)

    if resp.status_code in (400, 403, 404):
        logger.warning("Bad response %s for region %s, page %s", resp.status_code, region_id, page)
        return [], 0

    resp.raise_for_status()
    return resp.json(), int(resp.headers.get("X-Pages", 1))


def save_orders_to_db(region_id: int, orders: list[dict]) -> None:
    logger.debug("Saving %s orders for region %s", len(orders), region_id)
    rows = [{**order, "region_id": region_id} for order in orders]
    sde_store.upsert_market_orders(rows)


def fetch_all_market_data() -> None:
    region_ids = get_all_region_ids()
    logger.info("Found %s regions to process", len(region_ids))

    for region_id in region_ids:
        logger.info("=== Fetching region %s ===", region_id)
        try:
            first_page, total_pages = fetch_market_orders(region_id, page=1)
            if not first_page:
                logger.info("No market data for region %s", region_id)
                continue

            save_orders_to_db(region_id, first_page)

            for page in range(2, total_pages + 1):
                page_data, _ = fetch_market_orders(region_id, page)
                if not page_data:
                    break
                save_orders_to_db(region_id, page_data)

                if total_pages < 50 or page % 7 == 0:
                    logger.info("Region %s: %.2f%% complete", region_id, 100 * page / total_pages)

        except Exception as exc:
            logger.error("Failed fetching market data for region %s: %s", region_id, exc)

    logger.info("Completed fetch of all market data")
