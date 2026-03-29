# db/models.py
"""SQLAlchemy ORM models.

PublicBase (DuckDB):   User, SiteAdmin, Structure, MarketOrder, MarketStructure
PrivateBase (SQLite):  Character
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON
from sqlalchemy.orm import declarative_base
import datetime

PublicBase = declarative_base()
PrivateBase = declarative_base()


class User(PublicBase):
    __tablename__   = "users"
    owner_id        = Column(Integer, index=True)
    character_id    = Column(Integer, primary_key=True)


class SiteAdmin(PublicBase):
    __tablename__     = "site_admins"
    owner_id          = Column(Integer, primary_key=True)
    is_site_owner     = Column(Boolean, default=False)
    granted_by        = Column(Integer, nullable=True)
    granted_at        = Column(DateTime, default=datetime.datetime.utcnow)


class Structure(PublicBase):
    __tablename__   = "structures"
    structure_id    = Column(Integer, primary_key=True)
    solar_system_id = Column(Integer, index=True)
    region_id       = Column(Integer, nullable=True)
    owner_id        = Column(Integer, nullable=True)
    name            = Column(String, nullable=True)
    type_id         = Column(Integer, nullable=True)
    position        = Column(JSON, nullable=True)
    last_seen       = Column(DateTime, default=datetime.datetime.utcnow)


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


class Character(PrivateBase):
    __tablename__   = "characters"
    character_id    = Column(Integer, primary_key=True)
    name            = Column(String)
    corporation_id  = Column(Integer)
    birthday        = Column(String)
    security_status = Column(Float, nullable=True)
    alliance_id     = Column(Integer, nullable=True)
    access_token    = Column(String)
    refresh_token   = Column(String)
    expires_at      = Column(Float)
    scopes          = Column(String)
