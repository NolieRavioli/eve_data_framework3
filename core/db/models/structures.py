"""Structure model (DuckDB)."""

from sqlalchemy import Column, Integer, String, DateTime, JSON
import datetime

from core.db.models.identity import PublicBase


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
