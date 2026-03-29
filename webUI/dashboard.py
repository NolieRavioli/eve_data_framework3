# webUI/dashboard.py

from collections import defaultdict
import logging
from typing import Any

from flask import Blueprint, redirect, render_template, session, url_for
from sqlalchemy import func

from analysis.job_slots import analyze_slots
from db.database import get_private_session
from db.models import (
    Asset,
    Character,
    IndustryJob,
    Skill,
    SkillQueue,
    WalletBalance,
    WalletJournal,
    WalletTransaction,
)
from util.sde import name_from_type_id
from util.utils import get_portrait, get_runtime_settings
from webUI.context import base_ctx

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__)


def _format_timestamp(value: Any) -> str:
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _load_wallet_data(db, char_id: int, txn_limit: int, journal_limit: int):
    balance_row = db.query(WalletBalance).filter_by(character_id=char_id).first()
    txn_rows = (
        db.query(WalletTransaction)
        .filter_by(character_id=char_id)
        .order_by(WalletTransaction.date.desc())
        .limit(txn_limit)
        .all()
    )
    journal_rows = (
        db.query(WalletJournal)
        .filter_by(character_id=char_id)
        .order_by(WalletJournal.date.desc())
        .limit(journal_limit)
        .all()
    )

    wallet_txns = [
        {
            "amount": row.amount or 0.0,
            "is_buy": row.is_buy,
            "quantity": row.quantity or 0,
            "type_name": name_from_type_id(int(row.type_id)) if row.type_id else "Unknown",
            "unit_price": row.unit_price or 0.0,
            "date": _format_timestamp(row.date),
        }
        for row in txn_rows
    ]
    wallet_journal = [
        {
            "date": _format_timestamp(row.date),
            "ref_type": (row.ref_type or "").replace("_", " ").title(),
            "amount": row.amount or 0.0,
            "balance": row.balance or 0.0,
            "description": row.description,
        }
        for row in journal_rows
    ]

    gross_buys = sum((row.amount or 0.0) for row in txn_rows if row.is_buy)
    gross_sells = sum((row.amount or 0.0) for row in txn_rows if not row.is_buy)
    journal_credits = sum(max(row.amount or 0.0, 0.0) for row in journal_rows)
    journal_debits = sum(abs(min(row.amount or 0.0, 0.0)) for row in journal_rows)

    wallet_summary = {
        "transactions": len(wallet_txns),
        "journal_entries": len(wallet_journal),
        "buys": sum(1 for row in txn_rows if row.is_buy),
        "sells": sum(1 for row in txn_rows if not row.is_buy),
        "gross_buys": gross_buys,
        "gross_sells": gross_sells,
        "net_transactions": gross_sells - gross_buys,
        "journal_credits": journal_credits,
        "journal_debits": journal_debits,
        "journal_net": journal_credits - journal_debits,
        "last_transaction_at": wallet_txns[0]["date"] if wallet_txns else None,
        "last_journal_at": wallet_journal[0]["date"] if wallet_journal else None,
    }

    return (balance_row.balance if balance_row else 0.0), wallet_txns, wallet_journal, wallet_summary


def _sync_sections():
    personal = [
        ("Assets", "update_personal.update_assets"),
        ("Wallet", "update_personal.update_wallet"),
        ("Skills", "update_personal.update_skills"),
        ("Industry Jobs", "update_personal.update_industry"),
        ("Bookmarks", "update_personal.update_bookmarks"),
        ("Contacts", "update_personal.update_contacts"),
        ("Contracts", "update_personal.update_contracts"),
        ("Mail", "update_personal.update_mail"),
        ("Notifications", "update_personal.update_notifications"),
        ("Calendar", "update_personal.update_calendar"),
        ("Standings", "update_personal.update_standings"),
        ("Fittings", "update_personal.update_fittings"),
        ("Attributes", "update_personal.update_attributes"),
        ("Clones", "update_personal.update_clones"),
        ("Planetary", "update_personal.update_planetary"),
        ("Mining", "update_personal.update_mining"),
        ("Market Orders", "update_personal.update_orders"),
        ("Killmails", "update_personal.update_killmails"),
        ("Loyalty Points", "update_personal.update_loyalty"),
        ("Medals", "update_personal.update_medals"),
        ("Jump Fatigue", "update_personal.update_fatigue"),
        ("Location", "update_personal.update_location"),
    ]
    corporation = [
        ("Corp Info", "update_corp.update_corp_info"),
        ("Assets", "update_corp.update_corp_assets"),
        ("Blueprints", "update_corp.update_corp_blueprints"),
        ("Contacts", "update_corp.update_corp_contacts"),
        ("Contracts", "update_corp.update_corp_contracts"),
        ("Divisions", "update_corp.update_corp_divisions"),
        ("Industry", "update_corp.update_corp_industry"),
        ("Killmails", "update_corp.update_corp_killmails"),
        ("Members", "update_corp.update_corp_members"),
        ("Mining", "update_corp.update_corp_mining"),
        ("Market Orders", "update_corp.update_corp_orders"),
        ("Roles", "update_corp.update_corp_roles"),
        ("Standings", "update_corp.update_corp_standings"),
        ("Structures", "update_corp.update_corp_structures"),
        ("Customs Offices", "update_corp.update_corp_customs_offices"),
        ("Wallet", "update_corp.update_corp_wallet"),
    ]
    public = [
        ("Refresh SDE", "update_public.update_public_sde"),
        ("Refresh ESI Spec", "update_public.update_public_esi_spec"),
        ("Discover Structures", "update_public.update_public_structures"),
        ("Structure Markets", "update_public.update_public_structure_markets"),
        ("Station Market Orders", "update_public.update_public_market"),
        ("Public Contracts", "update_public.update_public_contracts"),
    ]

    return [
        {
            "title": "Personal",
            "subtitle": "Character-scoped collection for the active pilot.",
            "tone": "primary",
            "actions": [{"label": label, "endpoint": endpoint} for label, endpoint in personal],
        },
        {
            "title": "Corporation",
            "subtitle": "Corp APIs for members, roles, industry, and finance.",
            "tone": "primary",
            "actions": [{"label": label, "endpoint": endpoint} for label, endpoint in corporation],
        },
        {
            "title": "Public",
            "subtitle": "Shared SDE and market crawls. These tend to be the slow ones.",
            "tone": "public",
            "actions": [{"label": label, "endpoint": endpoint} for label, endpoint in public],
        },
    ]


@dashboard_bp.route("/")
def home():
    """Landing page. Show dashboard if logged in, otherwise show the login view."""

    runtime = get_runtime_settings()
    wallet_txns = []
    wallet_journal = []
    wallet_summary = {}
    assets_summary = []
    slot_status = []
    toon_cards = []
    portrait = None
    char_id = None
    owner_id = None
    current_name = None
    wallet_balance = 0.0
    asset_meta = {"total_items": 0, "unique_types": 0}
    logged_in = False

    if "character_id" in session and "owner_id" in session:
        char_id = session["character_id"]
        owner_id = session["owner_id"]
        logged_in = True

        db = get_private_session(owner_id)
        try:
            characters = db.query(Character).order_by(Character.name.asc()).all()
            for char in characters:
                toon_cards.append(
                    {
                        "name": char.name or f"Character {char.character_id}",
                        "id": char.character_id,
                        "portrait_url": (
                            f"https://images.evetech.net/characters/{char.character_id}/portrait"
                            "?tenant=tranquility&size=128"
                        ),
                        "is_active": char.character_id == char_id,
                        "switch_url": url_for(
                            "auth.switch_character",
                            character_id=char.character_id,
                            next=url_for("dashboard.home"),
                        ),
                    }
                )
                if char.character_id == char_id:
                    current_name = char.name or str(char.character_id)

            try:
                portrait = get_portrait(char_id)
            except Exception as exc:  # pragma: no cover - diagnostic resilience
                logger.warning("Failed to load portrait for %s: %s", char_id, exc)

            (
                wallet_balance,
                wallet_txns,
                wallet_journal,
                wallet_summary,
            ) = _load_wallet_data(db, char_id, txn_limit=12, journal_limit=8)

            asset_rows = db.query(Asset).filter_by(character_id=char_id).all()
            asset_meta["total_items"] = len(asset_rows)

            summary = defaultdict(lambda: {"quantity": 0, "stacks": 0, "locations": set()})
            for asset in asset_rows:
                bucket = summary[asset.type_id]
                bucket["quantity"] += asset.quantity or 0
                bucket["stacks"] += 1
                bucket["locations"].add(str(asset.location_flag or asset.location_type or "?"))

            asset_meta["unique_types"] = len(summary)
            for type_id, info in summary.items():
                assets_summary.append(
                    {
                        "type_id": type_id,
                        "name": name_from_type_id(type_id),
                        "quantity": info["quantity"],
                        "stacks": info["stacks"],
                        "locations": sorted(info["locations"]),
                    }
                )

            assets_summary.sort(key=lambda row: row["quantity"], reverse=True)
            assets_summary = assets_summary[:18]
        finally:
            db.close()

        try:
            slot_status = analyze_slots(owner_id)
        except Exception as exc:
            logger.warning("analyze_slots failed for owner %s: %s", owner_id, exc)

    return render_template(
        "dashboard.html",
        **base_ctx("overview"),
        logged_in=logged_in,
        char_id=char_id,
        owner_id=owner_id,
        toon_cards=toon_cards,
        portrait=portrait,
        current_name=current_name,
        wallet_balance=wallet_balance,
        wallet_txns=wallet_txns,
        wallet_journal=wallet_journal,
        wallet_summary=wallet_summary,
        slot_status=slot_status,
        assets_summary=assets_summary,
        asset_meta=asset_meta,
        runtime=runtime,
    )


@dashboard_bp.route("/wallet")
def wallet():
    if "character_id" not in session:
        return redirect(url_for("dashboard.home"))

    char_id = session["character_id"]
    owner_id = session["owner_id"]
    db = get_private_session(owner_id)
    try:
        char = db.query(Character).filter_by(character_id=char_id).first()
        current_name = char.name if char else str(char_id)
        (
            wallet_balance,
            wallet_txns,
            wallet_journal,
            wallet_summary,
        ) = _load_wallet_data(db, char_id, txn_limit=200, journal_limit=200)
    finally:
        db.close()

    return render_template(
        "wallet.html",
        **base_ctx("wallet"),
        current_name=current_name,
        wallet_balance=wallet_balance,
        wallet_txns=wallet_txns,
        wallet_journal=wallet_journal,
        wallet_summary=wallet_summary,
    )


@dashboard_bp.route("/assets")
def assets():
    if "character_id" not in session:
        return redirect(url_for("dashboard.home"))

    char_id = session["character_id"]
    owner_id = session["owner_id"]
    db = get_private_session(owner_id)
    try:
        asset_rows = db.query(Asset).filter_by(character_id=char_id).all()
        summary = defaultdict(lambda: {"quantity": 0, "stacks": 0, "locations": set()})
        for asset in asset_rows:
            bucket = summary[asset.type_id]
            bucket["quantity"] += asset.quantity or 0
            bucket["stacks"] += 1
            bucket["locations"].add(str(asset.location_flag or asset.location_type or "?"))

        assets_summary = sorted(
            [
                {
                    "type_id": type_id,
                    "name": name_from_type_id(type_id),
                    "quantity": info["quantity"],
                    "stacks": info["stacks"],
                    "locations": sorted(info["locations"]),
                }
                for type_id, info in summary.items()
            ],
            key=lambda row: row["quantity"],
            reverse=True,
        )
        asset_meta = {"total_items": len(asset_rows), "unique_types": len(summary)}
        char = db.query(Character).filter_by(character_id=char_id).first()
        current_name = char.name if char else str(char_id)
    finally:
        db.close()

    return render_template(
        "assets.html",
        **base_ctx("assets"),
        current_name=current_name,
        assets_summary=assets_summary,
        asset_meta=asset_meta,
    )


@dashboard_bp.route("/industry")
def industry():
    if "character_id" not in session:
        return redirect(url_for("dashboard.home"))

    char_id = session["character_id"]
    owner_id = session["owner_id"]
    db = get_private_session(owner_id)
    try:
        raw_jobs = (
            db.query(IndustryJob)
            .filter_by(character_id=char_id)
            .order_by(IndustryJob.start_date.desc())
            .limit(100)
            .all()
        )
        activity_map = {
            1: "Manufacturing",
            3: "TE Research",
            4: "ME Research",
            5: "Copying",
            7: "Reverse Eng",
            8: "Invention",
            11: "Reactions",
        }
        jobs = [
            {
                "activity": activity_map.get(job.activity_id, str(job.activity_id)),
                "blueprint_name": (
                    name_from_type_id(job.blueprint_type_id) if job.blueprint_type_id else "-"
                ),
                "runs": job.runs,
                "status": job.status or "-",
                "start_date": _format_timestamp(job.start_date),
                "end_date": _format_timestamp(job.end_date),
            }
            for job in raw_jobs
        ]
        char = db.query(Character).filter_by(character_id=char_id).first()
        current_name = char.name if char else str(char_id)
    finally:
        db.close()

    return render_template(
        "industry.html",
        **base_ctx("industry"),
        current_name=current_name,
        jobs=jobs,
        slot_status=analyze_slots(owner_id),
    )


@dashboard_bp.route("/character")
def character():
    if "character_id" not in session:
        return redirect(url_for("dashboard.home"))

    char_id = session["character_id"]
    owner_id = session["owner_id"]
    db = get_private_session(owner_id)
    try:
        characters = db.query(Character).order_by(Character.name.asc()).all()
        toon_cards = [
            {
                "name": char.name or str(char.character_id),
                "id": char.character_id,
                "portrait_url": (
                    f"https://images.evetech.net/characters/{char.character_id}/portrait"
                    "?tenant=tranquility&size=128"
                ),
                "is_active": char.character_id == char_id,
                "switch_url": url_for(
                    "auth.switch_character",
                    character_id=char.character_id,
                    next=url_for("dashboard.character"),
                ),
            }
            for char in characters
        ]
        char_detail = db.query(Character).filter_by(character_id=char_id).first()
        total_sp = (
            db.query(Skill)
            .filter_by(character_id=char_id)
            .with_entities(func.sum(Skill.skillpoints_in_skill))
            .scalar()
            or 0
        )
        trained = db.query(Skill).filter_by(character_id=char_id).count()
        level_five = db.query(Skill).filter_by(character_id=char_id, trained_skill_level=5).count()
        queue_rows = (
            db.query(SkillQueue)
            .filter_by(character_id=char_id)
            .order_by(SkillQueue.queue_position)
            .limit(10)
            .all()
        )
        queue = [
            {
                "skill_name": name_from_type_id(row.skill_id) if row.skill_id else "?",
                "finish_level": row.finish_level,
                "finish_date": _format_timestamp(row.finish_date) or "Paused",
            }
            for row in queue_rows
        ]
        skills_summary = {
            "total_sp": total_sp,
            "trained": trained,
            "level_five": level_five,
            "queue": queue,
        }
        current_name = char_detail.name if char_detail else str(char_id)
    finally:
        db.close()

    return render_template(
        "character.html",
        **base_ctx("character"),
        current_name=current_name,
        char_id=char_id,
        owner_id=owner_id,
        toon_cards=toon_cards,
        char_detail=char_detail,
        skills_summary=skills_summary,
    )


@dashboard_bp.route("/sync")
def sync():
    if "owner_id" not in session:
        return redirect(url_for("dashboard.home"))
    sections = _sync_sections()
    return render_template(
        "sync.html",
        **base_ctx("sync"),
        sync_sections=sections,
        sync_totals={
            "personal": len(sections[0]["actions"]),
            "corporation": len(sections[1]["actions"]),
            "public": len(sections[2]["actions"]),
            "all": sum(len(section["actions"]) for section in sections),
        },
    )
