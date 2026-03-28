# esi/personal_contacts.py
import logging

from db.database import get_private_session
from db.models import Contact, ContactLabel
from util.esi_rate_limiter import esi_get
from util.utils import get_token

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def fetch_contacts(char_id: int, access_token: str) -> list:
    contacts, page = [], 1
    headers = {"Authorization": f"Bearer {access_token}"}
    while True:
        resp = esi_get(f"{ESI}/characters/{char_id}/contacts/",
                       headers=headers, params={"page": page})
        resp.raise_for_status()
        data = resp.json()
        contacts.extend(data)
        if page >= int(resp.headers.get("x-pages", 1)):
            break
        page += 1
    return contacts


def fetch_contact_labels(char_id: int, access_token: str) -> list:
    resp = esi_get(f"{ESI}/characters/{char_id}/contacts/labels/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def store_contacts(owner_id: int, char_id: int, contacts: list, labels: list):
    db = get_private_session(owner_id)

    db.query(Contact).filter_by(character_id=char_id).delete()
    for c in contacts:
        db.add(Contact(
            character_id=char_id,
            contact_id=c["contact_id"],
            contact_type=c.get("contact_type"),
            standing=c.get("standing", 0.0),
            is_watched=c.get("is_watched"),
            is_blocked=c.get("is_blocked"),
            label_ids=c.get("label_ids"),
        ))

    db.query(ContactLabel).filter_by(character_id=char_id).delete()
    for lbl in labels:
        db.add(ContactLabel(
            character_id=char_id,
            label_id=lbl["label_id"],
            label_name=lbl.get("label_name"),
        ))

    db.commit()
    db.close()


def fetch_all_contacts(owner_id: int):
    for char_id, token_row in get_token(owner_id).items():
        try:
            contacts = fetch_contacts(char_id, token_row["access_token"])
            labels = fetch_contact_labels(char_id, token_row["access_token"])
            store_contacts(owner_id, char_id, contacts, labels)
            logger.info(f"[contacts] {len(contacts)} contacts, {len(labels)} labels for {char_id}")
        except Exception as e:
            logger.error(f"[contacts] Failed for {char_id}: {e}")
