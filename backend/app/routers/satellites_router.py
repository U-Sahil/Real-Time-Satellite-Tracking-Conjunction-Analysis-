"""
satellites_router.py
---------------------
Everything about individual satellites:

GET    /api/satellites                       list all currently tracked satellites
GET    /api/satellites/{norad_id}/position    live lat/lon/alt/speed
GET    /api/satellites/{norad_id}/passes      upcoming visible passes over a location
POST   /api/satellites/saved                  save a satellite to your account   (auth)
GET    /api/satellites/saved                  list your saved satellites          (auth)
DELETE /api/satellites/saved/{norad_id}       stop tracking a satellite            (auth)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import SavedSatellite, User
from app.orbital import propagator
from app.orbital.tle_store import tle_store
from app.schemas import (
    BulkPosition,
    PassPrediction,
    SatellitePosition,
    SatelliteSummary,
    SaveSatelliteRequest,
    SavedSatelliteOut,
)

router = APIRouter(prefix="/api/satellites", tags=["satellites"])


@router.get("/positions/bulk", response_model=list[BulkPosition])
def bulk_positions(
    ids: str | None = Query(default=None, description="Comma-separated NORAD IDs. Omit for a broad catalog sample."),
    limit: int = Query(default=1500, le=4000),
):
    """
    Returns current + ~6-seconds-ahead positions for many satellites at
    once, which the frontend uses to animate markers smoothly instead of
    jumping on every poll. Pass `ids=25544,20580,...` for a specific set
    (selected/saved satellites), or omit it to get a broad sample of the
    whole catalog for the "swarm" overview.
    """
    satellites = tle_store.all()
    norad_ids = None
    if ids:
        try:
            norad_ids = [int(x) for x in ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="ids must be comma-separated integers")
    return propagator.bulk_positions(satellites, norad_ids=norad_ids, limit=limit)


@router.get("", response_model=list[SatelliteSummary])
def list_satellites(search: str | None = Query(default=None, description="Filter by name substring")):
    satellites = tle_store.all()
    items = [SatelliteSummary(norad_id=nid, name=sat.name) for nid, sat in satellites.items()]
    if search:
        items = [s for s in items if search.lower() in s.name.lower()]
    return sorted(items, key=lambda s: s.name)[:500]


@router.get("/{norad_id}/position", response_model=SatellitePosition)
def get_position(norad_id: int):
    position = propagator.current_position(norad_id)
    if position is None:
        raise HTTPException(status_code=404, detail="Satellite not found in current TLE catalog")
    return position


@router.get("/{norad_id}/passes", response_model=list[PassPrediction])
def get_passes(
    norad_id: int,
    lat: float = Query(..., description="Observer latitude in degrees"),
    lon: float = Query(..., description="Observer longitude in degrees"),
    days: int = Query(default=3, ge=1, le=10),
):
    passes = propagator.next_passes(norad_id, lat, lon, days)
    if passes is None:
        raise HTTPException(status_code=404, detail="Satellite not found in current TLE catalog")
    return passes


@router.post("/saved", response_model=SavedSatelliteOut, status_code=201)
def save_satellite(
    payload: SaveSatelliteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sat = tle_store.get(payload.norad_id)
    if sat is None:
        raise HTTPException(status_code=404, detail="Satellite not found in current TLE catalog")

    existing = (
        db.query(SavedSatellite)
        .filter(SavedSatellite.user_id == current_user.id, SavedSatellite.norad_id == payload.norad_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already saved")

    saved = SavedSatellite(
        user_id=current_user.id,
        norad_id=payload.norad_id,
        name=sat.name,
        email_alerts_enabled=payload.email_alerts_enabled,
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)
    return saved


@router.get("/saved", response_model=list[SavedSatelliteOut])
def list_saved(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(SavedSatellite).filter(SavedSatellite.user_id == current_user.id).all()


@router.delete("/saved/{norad_id}", status_code=204)
def unsave_satellite(
    norad_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    saved = (
        db.query(SavedSatellite)
        .filter(SavedSatellite.user_id == current_user.id, SavedSatellite.norad_id == norad_id)
        .first()
    )
    if not saved:
        raise HTTPException(status_code=404, detail="Not found in your saved satellites")
    db.delete(saved)
    db.commit()
