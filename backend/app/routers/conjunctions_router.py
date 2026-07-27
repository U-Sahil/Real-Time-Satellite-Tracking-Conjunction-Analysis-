"""
conjunctions_router.py
-----------------------
GET /api/conjunctions           run a fresh live screening right now
GET /api/conjunctions/history   past detections stored in the database
                                 (this is the "historical conjunction
                                 reports" feature — every refresh cycle's
                                 findings get logged permanently)
"""
import datetime as dt

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session
from fastapi import Depends

from app.database import get_db
from app.models import ConjunctionEvent
from app.orbital import propagator
from app.orbital.conjunction import screen_for_conjunctions
from app.orbital.tle_store import tle_store
from app.schemas import ConjunctionResult

router = APIRouter(prefix="/api/conjunctions", tags=["conjunctions"])


@router.get("", response_model=list[ConjunctionResult])
def live_conjunctions(
    threshold_km: float = Query(default=25.0, gt=0),
    min_km: float = Query(default=0.5, ge=0, description="Excludes pairs closer than this (filters out permanently docked spacecraft)"),
):
    satellites = tle_store.all()
    snapshot = propagator.eci_snapshot(satellites)
    pairs = screen_for_conjunctions(snapshot, threshold_km=threshold_km, min_km=min_km)

    now = dt.datetime.utcnow()
    return [
        ConjunctionResult(
            norad_id_1=pair.norad_id_1,
            name_1=satellites[pair.norad_id_1].name,
            norad_id_2=pair.norad_id_2,
            name_2=satellites[pair.norad_id_2].name,
            distance_km=round(pair.distance_km, 3),
            detected_at=now,
        )
        for pair in pairs[:200]
    ]


@router.get("/history", response_model=list[ConjunctionResult])
def conjunction_history(
    limit: int = Query(default=100, le=1000),
    norad_id: int | None = Query(default=None, description="Filter to events involving this satellite"),
    db: Session = Depends(get_db),
):
    query = db.query(ConjunctionEvent)
    if norad_id is not None:
        query = query.filter(
            (ConjunctionEvent.norad_id_1 == norad_id) | (ConjunctionEvent.norad_id_2 == norad_id)
        )
    events = query.order_by(ConjunctionEvent.detected_at.desc()).limit(limit).all()
    return events
