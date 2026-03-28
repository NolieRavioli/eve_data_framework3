# esi/corp_roles_full.py
import logging

from db.database import get_private_session
from db.models import CorpRole, CorpTitle
from util.esi_rate_limiter import esi_get
from util.utils import get_token
from esi._corp_helpers import get_corp_id_for_char

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"

ROLE_TYPES = ["roles", "roles_at_hq", "roles_at_base", "roles_at_other"]


def fetch_roles(corp_id: int, access_token: str) -> list:
    resp = esi_get(f"{ESI}/corporations/{corp_id}/roles/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def fetch_titles(corp_id: int, access_token: str) -> list:
    resp = esi_get(f"{ESI}/corporations/{corp_id}/titles/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def store_roles_and_titles(owner_id: int, corp_id: int, roles: list, titles: list):
    db = get_private_session(owner_id)
    db.query(CorpRole).filter_by(corporation_id=corp_id).delete()
    for member in roles:
        char_id = member["character_id"]
        for rtype in ROLE_TYPES:
            for role_name in member.get(rtype, []):
                db.add(CorpRole(
                    character_id=char_id,
                    corporation_id=corp_id,
                    role_name=role_name,
                    role_type=rtype,
                ))

    db.query(CorpTitle).filter_by(corporation_id=corp_id).delete()
    for t in titles:
        db.add(CorpTitle(
            title_id=t["title_id"],
            corporation_id=corp_id,
            title_name=t.get("name"),
            roles=t.get("roles"),
        ))
    db.commit()
    db.close()


def fetch_all_corp_roles(owner_id: int):
    seen = set()
    for char_id, token_row in get_token(owner_id).items():
        corp_id = get_corp_id_for_char(owner_id, char_id)
        if not corp_id or corp_id in seen:
            continue
        seen.add(corp_id)
        try:
            roles = fetch_roles(corp_id, token_row["access_token"])
            titles = fetch_titles(corp_id, token_row["access_token"])
            store_roles_and_titles(owner_id, corp_id, roles, titles)
            logger.info(f"[corp_roles] {len(roles)} members, {len(titles)} titles for corp {corp_id}")
        except Exception as e:
            logger.warning(f"[corp_roles] Skipped corp {corp_id}: {e}")
