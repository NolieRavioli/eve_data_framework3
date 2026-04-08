# applications/sde_browser/routes.py
"""SDE Browser blueprint — status dashboard and lookup tool."""

from __future__ import annotations

import logging

from flask import Blueprint, redirect, render_template, request, url_for

from applications._api import base_ctx, require_admin, db, tasks

logger = logging.getLogger(__name__)

sde_bp = Blueprint("sde_browser", __name__,
                   template_folder="templates",
                   static_folder="static")

_SDE_TABLES = [
    "sde_types", "sde_groups", "sde_categories", "sde_marketGroups",
    "sde_mapRegions", "sde_mapConstellations", "sde_mapSolarSystems", "sde_npcStations",
]


@sde_bp.route("/")
@require_admin
def index():
    table_counts = {}
    for tbl in _SDE_TABLES:
        try:
            row = db.query_one(f"SELECT COUNT(*) AS cnt FROM {tbl}")
            table_counts[tbl] = row["cnt"] if row else 0
        except Exception:
            table_counts[tbl] = None
    return render_template(
        "sde_index.html",
        table_counts=table_counts,
        **base_ctx("sde_browser"),
    )


@sde_bp.route("/update", methods=["POST"])
@require_admin
def update():
    from core.db.sde_loader import update_sde
    task_id = tasks.enqueue("SDE Update", update_sde, queue="public")
    return redirect(url_for("task_viewer.task_detail", task_id=task_id))


@sde_bp.route("/lookup")
@require_admin
def lookup():
    q = request.args.get("q", "").strip()
    if not q:
        return render_template("sde_lookup.html", results=None, query="", **base_ctx("sde_browser"))

    results = {"types": [], "systems": [], "regions": []}
    con = db.connect()
    try:
        # Numeric ID lookup
        if q.isdigit():
            tid = int(q)
            row = con.execute(
                "SELECT type_id, name_en FROM sde_types WHERE type_id = ?", [tid]
            ).fetchone()
            if row:
                results["types"].append({"type_id": row[0], "name": row[1]})

            srow = con.execute(
                "SELECT system_id, name_en FROM sde_mapSolarSystems WHERE system_id = ?", [tid]
            ).fetchone()
            if srow:
                results["systems"].append({"system_id": srow[0], "name": srow[1]})

            rrow = con.execute(
                "SELECT region_id, name_en FROM sde_mapRegions WHERE region_id = ?", [tid]
            ).fetchone()
            if rrow:
                results["regions"].append({"region_id": rrow[0], "name": rrow[1]})

        # Name search (case-insensitive LIKE)
        name_param = f"%{q}%"
        types = con.execute(
            "SELECT type_id, name_en FROM sde_types WHERE name_en ILIKE ? LIMIT 50",
            [name_param],
        ).fetchall()
        for r in types:
            if not any(t["type_id"] == r[0] for t in results["types"]):
                results["types"].append({"type_id": r[0], "name": r[1]})

        systems = con.execute(
            "SELECT system_id, name_en FROM sde_mapSolarSystems WHERE name_en ILIKE ? LIMIT 50",
            [name_param],
        ).fetchall()
        for r in systems:
            if not any(s["system_id"] == r[0] for s in results["systems"]):
                results["systems"].append({"system_id": r[0], "name": r[1]})

        regions = con.execute(
            "SELECT region_id, name_en FROM sde_mapRegions WHERE name_en ILIKE ? LIMIT 50",
            [name_param],
        ).fetchall()
        for r in regions:
            if not any(rg["region_id"] == r[0] for rg in results["regions"]):
                results["regions"].append({"region_id": r[0], "name": r[1]})
    except Exception:
        logger.exception("SDE lookup error")
    finally:
        con.close()

    return render_template("sde_lookup.html", results=results, query=q, **base_ctx("sde_browser"))


@sde_bp.route("/lookup/type/<int:type_id>")
@require_admin
def type_detail(type_id: int):
    row = db.query_one(
        """
        SELECT t.type_id, t.name_en AS type_name, t.group_id,
               t.market_group_id, t.published, t.mass, t.volume, t.capacity, t.portion_size,
               g.name_en AS group_name, g.category_id,
               c.name_en AS category_name,
               mg.name_en AS market_group_name
        FROM sde_types t
        LEFT JOIN sde_groups g ON t.group_id = g.group_id
        LEFT JOIN sde_categories c ON g.category_id = c.category_id
        LEFT JOIN sde_marketGroups mg ON t.market_group_id = mg.market_group_id
        WHERE t.type_id = ?
        """,
        [type_id],
    )
    if row is None:
        return render_template("sde_type.html", item=None, type_id=type_id, **base_ctx("sde_browser"))
    return render_template("sde_type.html", item=row, type_id=type_id, **base_ctx("sde_browser"))


@sde_bp.route("/lookup/system/<int:system_id>")
@require_admin
def system_detail(system_id: int):
    row = db.query_one(
        """
        SELECT s.system_id, s.name_en AS system_name,
               s.constellation_id, s.region_id,
               s.security_status AS security, s.star_id AS sun_type_id,
               json_array_length(s.planet_ids_json) AS planet_count,
               json_array_length(s.stargate_ids_json) AS stargate_count,
               cn.name_en AS constellation_name,
               r.name_en AS region_name
        FROM sde_mapSolarSystems s
        LEFT JOIN sde_mapConstellations cn ON s.constellation_id = cn.constellation_id
        LEFT JOIN sde_mapRegions r ON s.region_id = r.region_id
        WHERE s.system_id = ?
        """,
        [system_id],
    )
    stations = []
    if row:
        stations = db.query(
            "SELECT station_id, station_id AS station_name FROM sde_npcStations WHERE solar_system_id = ? ORDER BY station_id",
            [system_id],
        )
    return render_template(
        "sde_system.html",
        item=row,
        stations=stations,
        system_id=system_id,
        **base_ctx("sde_browser"),
    )


@sde_bp.route("/lookup/region/<int:region_id>")
@require_admin
def region_detail(region_id: int):
    row = db.query_one(
        "SELECT region_id, name_en AS region_name, faction_id FROM sde_mapRegions WHERE region_id = ?",
        [region_id],
    )
    constellations = []
    station_count = 0
    if row:
        constellations = db.query(
            """
            SELECT cn.constellation_id, cn.name_en AS constellation_name,
                   COUNT(s.system_id) AS system_count
            FROM sde_mapConstellations cn
            LEFT JOIN sde_mapSolarSystems s ON s.constellation_id = cn.constellation_id
            WHERE cn.region_id = ?
            GROUP BY cn.constellation_id, cn.name_en
            ORDER BY cn.name_en
            """,
            [region_id],
        )
        sc = db.scalar(
            "SELECT COUNT(*) FROM sde_npcStations WHERE solar_system_id IN (SELECT system_id FROM sde_mapSolarSystems WHERE region_id = ?)",
            [region_id],
        )
        station_count = sc or 0
    return render_template(
        "sde_region.html",
        item=row,
        constellations=constellations,
        station_count=station_count,
        region_id=region_id,
        **base_ctx("sde_browser"),
    )
