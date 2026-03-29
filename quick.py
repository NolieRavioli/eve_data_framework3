from datetime import datetime
import logging

from util import sde_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_structures_to_market_structures():
    rows = sde_store.query_browser_sql(
        """
        SELECT DISTINCT s.structure_id, s.name, s.solar_system_id, s.region_id, s.owner_id, s.type_id, s.position_json
        FROM structures AS s
        INNER JOIN market_orders AS mo
          ON mo.location_id = s.structure_id
        LEFT JOIN market_structures AS ms
          ON ms.structure_id = s.structure_id
        WHERE ms.structure_id IS NULL
        """
    )["rows"]

    payload = [
        {
            "structure_id": row["structure_id"],
            "name": row["name"],
            "solar_system_id": row["solar_system_id"],
            "region_id": row["region_id"],
            "owner_id": row["owner_id"],
            "type_id": row["type_id"],
            "position_json": row["position_json"],
            "last_seen": datetime.utcnow(),
        }
        for row in rows
    ]
    inserted = sde_store.upsert_market_structures(payload)
    logger.info("[Migration] Created %s MarketStructure entries from Structure.", inserted)


if __name__ == "__main__":
    migrate_structures_to_market_structures()
