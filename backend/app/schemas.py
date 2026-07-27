import datetime as dt
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ---------- Auth ----------
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8)


class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    created_at: dt.datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Satellites ----------
class SatellitePosition(BaseModel):
    norad_id: int
    name: str
    latitude_deg: float
    longitude_deg: float
    altitude_km: float
    velocity_km_s: float
    timestamp: dt.datetime


class SatelliteSummary(BaseModel):
    norad_id: int
    name: str


class BulkPosition(BaseModel):
    norad_id: int
    name: str
    lat0: float
    lon0: float
    alt0: float
    lat1: float
    lon1: float
    alt1: float


class PassPrediction(BaseModel):
    rise_time: dt.datetime
    culminate_time: dt.datetime
    set_time: dt.datetime
    max_elevation_deg: float


class SaveSatelliteRequest(BaseModel):
    norad_id: int
    email_alerts_enabled: bool = True


class SavedSatelliteOut(BaseModel):
    norad_id: int
    name: str
    email_alerts_enabled: bool
    added_at: dt.datetime

    class Config:
        from_attributes = True


# ---------- Conjunctions ----------
class ConjunctionResult(BaseModel):
    norad_id_1: int
    name_1: str
    norad_id_2: int
    name_2: str
    distance_km: float
    relative_velocity_km_s: Optional[float] = None
    detected_at: dt.datetime

    class Config:
        from_attributes = True


class RefreshResult(BaseModel):
    satellites_loaded: int
    new_conjunctions_found: int
    alerts_sent: int
