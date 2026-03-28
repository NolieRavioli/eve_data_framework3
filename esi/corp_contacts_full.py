# esi/corp_contacts_full.py
import logging

from db.database import get_private_session
from db.models import CorpStanding
from util.esi_rate_limiter import esi_get
from util.utils import get_token
from esi._corp_helpers import get_corp_id_for_char, fetch_paginated

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"

# Corp contacts are stored as CorpStanding rows with from_type populated.


def store_corp_contacts(owner_id: int, corp_id: int, contacts: list):
    db = get_private_session(owner_id)
    # Only delete contact-type standings (not NPC standings)
    existing = db.query(CorpStanding).filter_by(corporation_id=corp_id).all()
    for row in existing:
        db.delete(row)
    for c in contacts:
        db.add(CorpStanding(
            corporation_id=corp_id,
            from_id=c["contact_id"],
            from_type=c.get("contact_type", "unknown"),
            standing=c.get("standing", 0.0),
        ))
    db.commit()
    db.close()


def fetch_all_corp_contacts(owner_id: int):
    seen = set()
    for char_id, token_row in get_token(owner_id).items():
        corp_id = get_corp_id_for_char(owner_id, char_id)
        if not corp_id or corp_id in seen:
            continue
        seen.add(corp_id)
        try:
            contacts = fetch_paginated(
                f"{ESI}/corporations/{corp_id}/contacts/",
                token_row["access_token"], esi_get)
            store_corp_contacts(owner_id, corp_id, contacts)
            logger.info(f"[corp_contacts] {len(contacts)} for corp {corp_id}")
        except Exception as e:
            logger.warning(f"[corp_contacts] Skipped corp {corp_id}: {e}")
