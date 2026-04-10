"""analysis/freelance_enrichment.py — Fetch full details for freelance jobs.

Reads unenriched ``freelance_jobs`` rows (details_json IS NULL) from the public
DuckDB and calls GET /freelance-jobs/{job_id} (public endpoint, no auth).
"""

from __future__ import annotations

import json
import logging

import core.db.public as db
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def run_freelance_enrichment() -> None:
    """Enrich bare freelance job rows with full details."""
    con = db.connect()
    try:
        rows = con.execute(
            "SELECT job_id FROM freelance_jobs WHERE details_json IS NULL LIMIT 500"
        ).fetchall()
    finally:
        con.close()

    if not rows:
        logger.info("[freelance_enrichment] All freelance jobs already enriched.")
        return

    logger.info("[freelance_enrichment] Enriching %s freelance jobs", len(rows))
    enriched = 0
    for (job_id,) in rows:
        try:
            resp = esi_get(f"{ESI_BASE}/freelance-jobs/{job_id}/")
            if resp.ok:
                details = json.dumps(resp.json())
            elif resp.status_code == 404:
                details = "null"
            else:
                continue

            con = db.connect()
            try:
                con.execute(
                    "UPDATE freelance_jobs SET details_json = ?, fetched_at = now() WHERE job_id = ?",
                    [details, job_id]
                )
            finally:
                con.close()
            enriched += 1
        except Exception:
            logger.exception("[freelance_enrichment] Failed for job %s", job_id)

    logger.info("[freelance_enrichment] Done — %s/%s jobs enriched", enriched, len(rows))
