"""Blueprint profitability and manufacturing list generation."""

from __future__ import annotations

import logging
import math
import os
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import yaml
from sqlalchemy import func
from sqlalchemy.orm import Session

from db.database import get_private_session, get_public_session
from db.models import Blueprint as BlueprintRow, Character, MarketOrder
from util.sde import name_from_type_id
from util.settings_store import ManufacturingSettings

logger = logging.getLogger(__name__)

SDE_ROOT = os.getenv("SDE_PATH", "_sde")
BLUEPRINTS_FILE = os.path.join(SDE_ROOT, "fsd", "blueprints.yaml")


@dataclass
class BlueprintDefinition:
    blueprint_type_id: int
    product_type_id: int
    product_quantity: int
    manufacturing_time: int
    materials: List[Tuple[int, int]]


@dataclass
class MaterialCost:
    type_id: int
    name: str
    base_quantity: int
    adjusted_quantity: int
    price: float
    total_cost: float
    is_missing: bool = False


@dataclass
class MarketPrice:
    best_buy: float = 0.0
    best_sell: float = 0.0
    buy_order_count: int = 0
    sell_order_count: int = 0
    override: bool = False


@dataclass
class BlueprintLibraryEntry:
    blueprint_type_id: int
    blueprint_name: str
    blueprint_quantity: int
    character_name: str
    runs_per_blueprint: int
    total_runs: int
    me: int
    te: int
    is_original: bool
    product_type_id: int
    product_name: str
    product_quantity: int
    time_per_run_seconds: float
    total_time_hours: float
    material_cost_per_run: float
    revenue_per_run: float
    profit_per_run: float
    total_profit: float
    margin_percent: float
    isk_per_hour: float
    can_build: bool
    missing_components: List[str] = field(default_factory=list)
    materials: List[MaterialCost] = field(default_factory=list)


@dataclass
class ManufacturingQueueItem:
    product_type_id: int
    product_name: str
    blueprint_type_id: int
    blueprint_name: str
    total_runs: int
    total_profit: float
    isk_per_hour: float
    total_time_hours: float
    margin_percent: float
    me: int
    te: int
    is_original: bool


@dataclass
class IndustryReport:
    settings: ManufacturingSettings
    library: List[BlueprintLibraryEntry]
    manufacturing_plan: List[ManufacturingQueueItem]
    summary: Dict[str, object]


_BLUEPRINT_CACHE: Dict[int, BlueprintDefinition] | None = None
_BLUEPRINT_CACHE_PATH: Optional[str] = None


def clear_cache() -> None:
    """Reset cached blueprint metadata."""

    global _BLUEPRINT_CACHE, _BLUEPRINT_CACHE_PATH
    _BLUEPRINT_CACHE = None
    _BLUEPRINT_CACHE_PATH = None


def load_blueprint_definitions(sde_root: Optional[str] = None) -> Dict[int, BlueprintDefinition]:
    """Read the static data export blueprint file into memory."""

    global _BLUEPRINT_CACHE, _BLUEPRINT_CACHE_PATH

    root = sde_root or SDE_ROOT
    path = os.path.join(root, "fsd", "blueprints.yaml")

    if _BLUEPRINT_CACHE is not None and _BLUEPRINT_CACHE_PATH == path:
        return _BLUEPRINT_CACHE

    if not os.path.exists(path):
        logger.warning("Blueprint definitions not found at %s", path)
        _BLUEPRINT_CACHE = {}
        _BLUEPRINT_CACHE_PATH = path
        return _BLUEPRINT_CACHE

    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
    except OSError as exc:
        logger.error("Failed to read blueprint file %s: %s", path, exc)
        _BLUEPRINT_CACHE = {}
        _BLUEPRINT_CACHE_PATH = path
        return _BLUEPRINT_CACHE

    definitions: Dict[int, BlueprintDefinition] = {}
    for bp_id, payload in raw.items():
        try:
            blueprint_id = int(bp_id)
        except (TypeError, ValueError):
            continue

        activities = payload.get("activities") or {}
        manufacturing = activities.get("manufacturing")
        if not manufacturing:
            continue

        products = manufacturing.get("products") or []
        if not products:
            continue

        try:
            product_type_id = int(products[0].get("typeID"))
        except (TypeError, ValueError):
            continue

        product_quantity = int(products[0].get("quantity", 1))
        time_seconds = int(manufacturing.get("time", 0))

        materials_data = manufacturing.get("materials") or []
        materials: List[Tuple[int, int]] = []
        for entry in materials_data:
            try:
                mat_type = int(entry.get("typeID"))
                mat_qty = int(entry.get("quantity", 0))
            except (TypeError, ValueError):
                continue
            if mat_qty <= 0:
                continue
            materials.append((mat_type, mat_qty))

        definitions[blueprint_id] = BlueprintDefinition(
            blueprint_type_id=blueprint_id,
            product_type_id=product_type_id,
            product_quantity=product_quantity,
            manufacturing_time=time_seconds,
            materials=materials,
        )

    _BLUEPRINT_CACHE = definitions
    _BLUEPRINT_CACHE_PATH = path
    logger.info("Loaded %d blueprint manufacturing definitions", len(definitions))
    return definitions


def _coerce_tax(value: float) -> float:
    return value / 100 if value > 1 else value


def _material_quantity(base_qty: int, material_efficiency: Optional[int]) -> int:
    me = material_efficiency or 0
    modifier = max(0.0, 1 - (me / 100))
    adjusted = math.ceil(base_qty * modifier)
    return max(1, adjusted) if base_qty else 0


def _time_per_run(base_time: int, time_efficiency: Optional[int], settings: ManufacturingSettings) -> float:
    te = time_efficiency or 0
    time_modifier = max(0.05, 1 - (te / 100))
    facility_modifier = max(0.05, settings.facility_time_modifier)
    return max(1.0, base_time * time_modifier * facility_modifier)


def _collect_price_map(
    type_ids: Iterable[int],
    settings: ManufacturingSettings,
    public_session: Session,
    overrides: Optional[Mapping[int, float]] = None,
) -> Dict[int, MarketPrice]:
    ids = {int(tid) for tid in type_ids if tid is not None}
    overrides = overrides or {}
    prices: Dict[int, MarketPrice] = {}

    if not ids:
        return prices

    sell_query = (
        public_session.query(
            MarketOrder.type_id,
            func.min(MarketOrder.price).label("price"),
            func.count(MarketOrder.order_id).label("order_count"),
        )
        .filter(MarketOrder.type_id.in_(ids), MarketOrder.is_buy_order.is_(False))
    )
    buy_query = (
        public_session.query(
            MarketOrder.type_id,
            func.max(MarketOrder.price).label("price"),
            func.count(MarketOrder.order_id).label("order_count"),
        )
        .filter(MarketOrder.type_id.in_(ids), MarketOrder.is_buy_order.is_(True))
    )

    if settings.region_id is not None:
        sell_query = sell_query.filter(MarketOrder.region_id == settings.region_id)
        buy_query = buy_query.filter(MarketOrder.region_id == settings.region_id)

    for row in sell_query.group_by(MarketOrder.type_id).all():
        info = prices.setdefault(row.type_id, MarketPrice())
        info.best_sell = float(row.price or 0.0)
        info.sell_order_count = int(row.order_count or 0)

    for row in buy_query.group_by(MarketOrder.type_id).all():
        info = prices.setdefault(row.type_id, MarketPrice())
        info.best_buy = float(row.price or 0.0)
        info.buy_order_count = int(row.order_count or 0)

    for type_id, price in overrides.items():
        if price < 0:
            continue
        info = prices.setdefault(int(type_id), MarketPrice())
        info.best_buy = float(price)
        info.best_sell = float(price)
        availability = 1 if price > 0 else 0
        info.buy_order_count = max(info.buy_order_count, availability)
        info.sell_order_count = max(info.sell_order_count, availability)
        info.override = True

    for type_id in ids:
        prices.setdefault(type_id, MarketPrice())

    return prices


def generate_industry_report(
    owner_id: int,
    settings: ManufacturingSettings,
    *,
    library_limit: Optional[int] = None,
    plan_limit: Optional[int] = 12,
    sde_root: Optional[str] = None,
    public_session: Optional[Session] = None,
    private_session: Optional[Session] = None,
) -> IndustryReport:
    """Compute blueprint profitability and manufacturing plan for an owner."""

    definitions = load_blueprint_definitions(sde_root)
    priv = private_session or get_private_session(owner_id)
    pub = public_session or get_public_session()
    close_priv = private_session is None
    close_pub = public_session is None

    try:
        blueprints: Sequence[BlueprintRow] = priv.query(BlueprintRow).all()
        if not blueprints:
            summary = {
                "blueprint_total": 0,
                "buildable_total": 0,
                "profitable_total": 0,
                "plan_total": 0,
                "missing_blueprints": [],
                "total_profit": 0.0,
                "average_isk_per_hour": 0.0,
                "best_blueprint": None,
                "original_total": 0,
                "copy_total": 0,
                "unbuildable_total": 0,
                "average_me": 0.0,
                "average_te": 0.0,
            }
            return IndustryReport(settings=settings, library=[], manufacturing_plan=[], summary=summary)

        characters = {c.character_id: c.name for c in priv.query(Character).all()}

        relevant_types: set[int] = set()
        missing: List[int] = []
        for bp in blueprints:
            definition = definitions.get(bp.type_id)
            if not definition:
                missing.append(bp.type_id)
                continue
            relevant_types.add(definition.product_type_id)
            for mat_id, _ in definition.materials:
                relevant_types.add(mat_id)

        override_ids = set(settings.override_prices.keys())
        price_map = _collect_price_map(relevant_types | override_ids, settings, pub, settings.override_prices)

        library_entries: List[BlueprintLibraryEntry] = []
        for bp in blueprints:
            definition = definitions.get(bp.type_id)
            if not definition:
                continue

            quantity = max(1, bp.quantity or 1)
            available_runs = bp.runs
            is_original = available_runs is not None and available_runs < 0
            available_runs = available_runs or 0

            if is_original:
                runs_per_blueprint = settings.runs_per_blueprint
            elif available_runs > 0:
                runs_per_blueprint = min(available_runs, settings.runs_per_blueprint)
            else:
                runs_per_blueprint = settings.runs_per_blueprint

            total_runs = max(1, runs_per_blueprint * quantity)

            time_per_run = _time_per_run(definition.manufacturing_time, bp.time_efficiency, settings)
            total_time_hours = (time_per_run * total_runs) / max(1, settings.parallel_jobs) / 3600

            materials_breakdown: List[MaterialCost] = []
            material_cost_per_run = 0.0
            can_build = True
            missing_components: List[str] = []

            for mat_type_id, base_qty in definition.materials:
                adjusted_qty = _material_quantity(base_qty, bp.material_efficiency)
                price_info = price_map.get(mat_type_id)
                price = 0.0
                has_market = False
                if price_info:
                    price = price_info.best_sell
                    has_market = price_info.sell_order_count > 0 or price_info.override
                if has_market and price > 0:
                    material_cost_per_run += adjusted_qty * price
                else:
                    can_build = False
                    missing_components.append(f"{name_from_type_id(mat_type_id)} sell orders")
                materials_breakdown.append(
                    MaterialCost(
                        type_id=mat_type_id,
                        name=name_from_type_id(mat_type_id),
                        base_quantity=base_qty,
                        adjusted_quantity=adjusted_qty,
                        price=price,
                        total_cost=adjusted_qty * max(price, 0.0),
                        is_missing=not (has_market and price > 0),
                    )
                )

            product_name = name_from_type_id(definition.product_type_id)
            product_price_info = price_map.get(definition.product_type_id)
            product_price = 0.0
            product_has_market = False
            market_label = "sell orders" if settings.price_source == "sell" else "buy orders"
            if product_price_info:
                if settings.price_source == "buy":
                    product_price = product_price_info.best_buy
                    product_has_market = product_price_info.buy_order_count > 0 or product_price_info.override
                else:
                    product_price = product_price_info.best_sell
                    product_has_market = product_price_info.sell_order_count > 0 or product_price_info.override

            if not product_has_market or product_price <= 0:
                can_build = False
                missing_components.append(f"{product_name} {market_label}")

            revenue_per_run = product_price * definition.product_quantity if product_price > 0 else 0.0
            tax_rate = _coerce_tax(settings.facility_tax)
            job_cost = settings.job_cost_per_run if settings.include_job_cost else 0.0

            profit_per_run = 0.0
            total_profit = 0.0
            margin_percent = 0.0
            isk_per_hour = 0.0

            if can_build:
                revenue_after_tax = revenue_per_run * (1 - tax_rate)
                total_cost_per_run = material_cost_per_run + job_cost
                profit_per_run = revenue_after_tax - total_cost_per_run
                total_profit = profit_per_run * total_runs
                margin_percent = (
                    (profit_per_run / total_cost_per_run)
                    if total_cost_per_run > 0
                    else 0.0
                )
                isk_per_hour = total_profit / total_time_hours if total_time_hours > 0 else 0.0

            entry = BlueprintLibraryEntry(
                blueprint_type_id=bp.type_id,
                blueprint_name=name_from_type_id(bp.type_id),
                blueprint_quantity=quantity,
                character_name=characters.get(bp.character_id, f"Character {bp.character_id}"),
                runs_per_blueprint=runs_per_blueprint,
                total_runs=total_runs,
                me=bp.material_efficiency or 0,
                te=bp.time_efficiency or 0,
                is_original=is_original,
                product_type_id=definition.product_type_id,
                product_name=product_name,
                product_quantity=definition.product_quantity,
                time_per_run_seconds=time_per_run,
                total_time_hours=total_time_hours,
                material_cost_per_run=material_cost_per_run,
                revenue_per_run=revenue_per_run,
                profit_per_run=profit_per_run,
                total_profit=total_profit,
                margin_percent=margin_percent,
                isk_per_hour=isk_per_hour,
                can_build=can_build,
                missing_components=missing_components,
                materials=materials_breakdown,
            )
            library_entries.append(entry)

        buildable_entries = [entry for entry in library_entries if entry.can_build]
        profitable_entries = [e for e in buildable_entries if e.profit_per_run > 0 and e.isk_per_hour > 0]
        margin_threshold = _coerce_tax(settings.minimum_margin)
        plan_candidates = [e for e in profitable_entries if e.margin_percent >= margin_threshold]
        plan_candidates.sort(key=lambda entry: entry.isk_per_hour, reverse=True)

        grouped_candidates: Dict[int, List[BlueprintLibraryEntry]] = defaultdict(list)
        for entry in plan_candidates:
            grouped_candidates[entry.product_type_id].append(entry)

        aggregated_plan: List[ManufacturingQueueItem] = []
        for entries in grouped_candidates.values():
            entries.sort(key=lambda entry: entry.isk_per_hour, reverse=True)
            primary = entries[0]
            total_profit = sum(e.total_profit for e in entries)
            total_time = sum(e.total_time_hours for e in entries)
            isk_per_hour = total_profit / total_time if total_time > 0 else 0.0
            has_original = any(e.is_original for e in entries)
            total_runs = sum(e.total_runs for e in entries if not e.is_original)
            total_runs_display = primary.total_runs if has_original else total_runs
            total_cost = 0.0
            for e in entries:
                if e.margin_percent > 0 and e.profit_per_run > 0:
                    total_cost += (e.profit_per_run / e.margin_percent) * e.total_runs
            margin_percent = total_profit / total_cost if total_cost > 0 else 0.0
            if len(entries) > 1:
                blueprint_name = f"{primary.blueprint_name} (+{len(entries) - 1} more)"
            else:
                blueprint_name = primary.blueprint_name
            aggregated_plan.append(
                ManufacturingQueueItem(
                    product_type_id=primary.product_type_id,
                    product_name=primary.product_name,
                    blueprint_type_id=primary.blueprint_type_id,
                    blueprint_name=blueprint_name,
                    total_runs=total_runs_display,
                    total_profit=total_profit,
                    isk_per_hour=isk_per_hour,
                    total_time_hours=total_time,
                    margin_percent=margin_percent,
                    me=max(e.me for e in entries),
                    te=max(e.te for e in entries),
                    is_original=has_original,
                )
            )

        aggregated_plan.sort(key=lambda item: item.isk_per_hour, reverse=True)

        plan: List[ManufacturingQueueItem]
        if plan_limit is not None:
            plan = aggregated_plan[:plan_limit]
        else:
            plan = aggregated_plan

        display_library = library_entries
        if library_limit is not None:
            display_library = library_entries[:library_limit]

        summary: Dict[str, object] = {
            "blueprint_total": len(library_entries),
            "buildable_total": len(buildable_entries),
            "profitable_total": len(profitable_entries),
            "plan_total": len(aggregated_plan),
            "missing_blueprints": sorted(set(missing)),
            "total_profit": sum(item.total_profit for item in aggregated_plan),
            "average_isk_per_hour": statistics.mean([item.isk_per_hour for item in aggregated_plan]) if aggregated_plan else 0.0,
            "best_blueprint": plan_candidates[0] if plan_candidates else None,
            "original_total": sum(1 for e in library_entries if e.is_original),
            "copy_total": sum(1 for e in library_entries if not e.is_original),
            "unbuildable_total": sum(1 for e in library_entries if not e.can_build),
            "average_me": statistics.mean([e.me for e in library_entries]) if library_entries else 0.0,
            "average_te": statistics.mean([e.te for e in library_entries]) if library_entries else 0.0,
        }

        return IndustryReport(settings=settings, library=display_library, manufacturing_plan=plan, summary=summary)
    finally:
        if close_priv:
            priv.close()
        if close_pub:
            pub.close()
