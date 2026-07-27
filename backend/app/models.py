import datetime as dt

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    saved_satellites = relationship(
        "SavedSatellite", back_populates="owner", cascade="all, delete-orphan"
    )


class SavedSatellite(Base):
    __tablename__ = "saved_satellites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    norad_id = Column(Integer, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    email_alerts_enabled = Column(Boolean, default=True)
    added_at = Column(DateTime, default=dt.datetime.utcnow)

    owner = relationship("User", back_populates="saved_satellites")


class ConjunctionEvent(Base):
    """
    One row = one close-approach detection between two objects at a
    specific screening run. The same real-world pair can appear many
    times over hours/days as they keep passing near each other — that's
    intentional, it's what lets the dashboard show a history/trend.
    """
    __tablename__ = "conjunction_events"

    id = Column(Integer, primary_key=True, index=True)
    norad_id_1 = Column(Integer, index=True, nullable=False)
    name_1 = Column(String(255), nullable=False)
    norad_id_2 = Column(Integer, index=True, nullable=False)
    name_2 = Column(String(255), nullable=False)
    distance_km = Column(Float, nullable=False)
    relative_velocity_km_s = Column(Float, nullable=True)
    detected_at = Column(DateTime, default=dt.datetime.utcnow, index=True)
