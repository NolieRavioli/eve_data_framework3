"""Identity models — User, SiteAdmin (DuckDB), Character (SQLite)."""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
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
