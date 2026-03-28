# esi/corp_industry_full.py
import logging

from db.database import get_private_session
from db.models import CorpIndustryJob
from util.esi_rate_limiter import esi_get
from util.utils import get_token
from esi._corp_helpers import get_corp_id_for_char, fetch_paginated, _dt

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def store_corp_industry(owner_id: int, corp_id: int, jobs: list):
    db = get_private_session(owner_id)
    db.query(CorpIndustryJob).filter_by(corporation_id=corp_id).delete()
    for j in jobs:
        db.add(CorpIndustryJob(
            job_id=j["job_id"],
            corporation_id=corp_id,
            activity_id=j.get("activity_id", 0),
            blueprint_id=j.get("blueprint_id", 0),
            blueprint_type_id=j.get("blueprint_type_id", 0),
            cost=j.get("cost"),
            duration=j.get("duration", 0),
            facility_id=j.get("facility_id", 0),
            installer_id=j.get("installer_id", 0),
            licensed_runs=j.get("licensed_runs"),
            output_location_id=j.get("output_location_id", 0),
            runs=j.get("runs", 0),
            status=j.get("status"),
            start_date=_dt(j.get("start_date")),
            end_date=_dt(j.get("end_date")),
        ))
    db.commit()
    db.close()


def fetch_all_corp_industry(owner_id: int):
    seen = set()
    for char_id, token_row in get_token(owner_id).items():
        corp_id = get_corp_id_for_char(owner_id, char_id)
        if not corp_id or corp_id in seen:
            continue
        seen.add(corp_id)
        try:
            jobs = fetch_paginated(
                f"{ESI}/corporations/{corp_id}/industry/jobs/",
                token_row["access_token"], esi_get)
            store_corp_industry(owner_id, corp_id, jobs)
            logger.info(f"[corp_industry] {len(jobs)} jobs for corp {corp_id}")
        except Exception as e:
            logger.warning(f"[corp_industry] Skipped corp {corp_id}: {e}")
