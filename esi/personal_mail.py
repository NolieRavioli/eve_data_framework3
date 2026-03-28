# esi/personal_mail.py
import logging
from datetime import datetime

from db.database import get_private_session
from db.models import MailHeader, MailLabel, MailList
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


def fetch_mail_headers(char_id: int, access_token: str) -> list:
    """Fetch mail headers (not bodies) for the character."""
    headers_acc, last_mail_id = [], None
    http_headers = {"Authorization": f"Bearer {access_token}"}
    while True:
        params = {}
        if last_mail_id:
            params["last_mail_id"] = last_mail_id
        resp = esi_get(f"{ESI}/characters/{char_id}/mail/",
                       headers=http_headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        headers_acc.extend(data)
        if len(data) < 50:
            break
        last_mail_id = min(m["mail_id"] for m in data)
    return headers_acc


def fetch_mail_labels(char_id: int, access_token: str) -> list:
    resp = esi_get(f"{ESI}/characters/{char_id}/mail/labels/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json().get("labels", [])


def fetch_mail_lists(char_id: int, access_token: str) -> list:
    resp = esi_get(f"{ESI}/characters/{char_id}/mail/lists/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def store_mail(owner_id: int, char_id: int, mail_headers: list, labels: list, lists: list):
    db = get_private_session(owner_id)

    # Upsert headers (don't delete – preserve read status of old mails)
    existing_ids = {row.mail_id for row in db.query(MailHeader.mail_id)
                    .filter_by(character_id=char_id).all()}
    for m in mail_headers:
        if m["mail_id"] in existing_ids:
            continue
        db.add(MailHeader(
            mail_id=m["mail_id"],
            character_id=char_id,
            from_id=m.get("from"),
            subject=m.get("subject"),
            timestamp=_dt(m.get("timestamp")),
            label_ids=m.get("labels"),
            recipients=m.get("recipients"),
            is_read=m.get("is_read"),
        ))

    db.query(MailLabel).filter_by(character_id=char_id).delete()
    for lbl in labels:
        db.add(MailLabel(
            character_id=char_id,
            label_id=lbl["label_id"],
            label_name=lbl.get("name"),
            unread_count=lbl.get("unread_count"),
            color=lbl.get("color"),
        ))

    db.query(MailList).filter_by(character_id=char_id).delete()
    for ml in lists:
        db.add(MailList(
            character_id=char_id,
            mailing_list_id=ml["mailing_list_id"],
            name=ml.get("name"),
        ))

    db.commit()
    db.close()


def fetch_all_mail(owner_id: int):
    for char_id, token_row in get_token(owner_id).items():
        try:
            mail_headers = fetch_mail_headers(char_id, token_row["access_token"])
            labels = fetch_mail_labels(char_id, token_row["access_token"])
            lists = fetch_mail_lists(char_id, token_row["access_token"])
            store_mail(owner_id, char_id, mail_headers, labels, lists)
            logger.info(f"[mail] {len(mail_headers)} headers, "
                        f"{len(labels)} labels, {len(lists)} lists for {char_id}")
        except Exception as e:
            logger.error(f"[mail] Failed for {char_id}: {e}")
