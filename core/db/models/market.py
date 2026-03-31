"""Market models — MarketOrder, MarketStructure (DuckDB)."""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON
import datetime

from core.db.models.identity import PublicBase


class MarketOrder(PublicBase):
    __tablename__   = "market_orders"
    order_id        = Column(Integer, primary_key=True)
    type_id         = Column(Integer)
    location_id     = Column(Integer)
    region_id       = Column(Integer)
    is_buy_order    = Column(Boolean)
    issued          = Column(DateTime)
    duration        = Column(Integer)
    price           = Column(Float)
    order_range     = Column(String)
    volume_remain   = Column(Integer)
    volume_total    = Column(Integer)
    min_volume      = Column(Integer)
    last_seen       = Column(DateTime, default=datetime.datetime.utcnow)


class MarketStructure(PublicBase):
    __tablename__   = "market_structures"
    structure_id    = Column(Integer, primary_key=True)
    solar_system_id = Column(Integer, nullable=True)
    region_id       = Column(Integer, nullable=True)
    owner_id        = Column(Integer, nullable=True)
    name            = Column(String, nullable=True)
    type_id         = Column(Integer, nullable=True)
    position        = Column(JSON, nullable=True)
    last_seen       = Column(DateTime, default=datetime.datetime.utcnow)
