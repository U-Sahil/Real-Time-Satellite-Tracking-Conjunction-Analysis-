"""
admin_router.py
----------------
POST /api/admin/refresh-tles

This is the ONE endpoint the Java scheduler component calls, on a cron
schedule (see java-scheduler/). It:

  1. re-downloads the TLE catalog from CelesTrak
  2. runs a fresh conjunction screening across the whole catalog
  3. saves any NEW close-approach pairs to the database (skips ones
     already logged in the last hour, so re-running every few minutes
     doesn't spam duplicate rows for the same ongoing pass)
  4. emails any user who has saved either satellite in a newly-found pair

Protected by a shared secret (X-Admin-Key header) so random people can't
trigger it — set the same value in .env (ADMIN_API_KEY) and in the Java
scheduler's config.properties.
"""
import datetime as dt

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.alerts import send_conjunction_alert
from app.config import settings
from app.database import get_db
from app.models import ConjunctionEvent, SavedSatellite, User
from app.orbital import propagator
from app.orbital.conjunction import screen_for_conjunctions
from app.orbital.tle_store import tle_store
from app.schemas import RefreshResult

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin_key(x_admin_key: str = Header(default="")):
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")


@router.post("/refresh-tles", response_model=RefreshResult, dependencies=[Depends(_require_admin_key)])
def refresh_tles(db: Session = Depends(get_db)):
    satellites_loaded = tle_store.refresh()

    satellites = tle_store.all()
    snapshot = propagator.eci_snapshot(satellites)
    pairs = screen_for_conjunctions(snapshot)

    recent_cutoff = dt.datetime.utcnow() - dt.timedelta(hours=1)
    new_events = 0
    alerts_sent = 0

    for pair in pairs:
        already_logged = (
            db.query(ConjunctionEvent)
            .filter(
                ConjunctionEvent.norad_id_1 == pair.norad_id_1,
                ConjunctionEvent.norad_id_2 == pair.norad_id_2,
                ConjunctionEvent.detected_at >= recent_cutoff,
            )
            .first()
        )
        if already_logged:
            continue

        name_1 = satellites[pair.norad_id_1].name
        name_2 = satellites[pair.norad_id_2].name

        event = ConjunctionEvent(
            norad_id_1=pair.norad_id_1,
            name_1=name_1,
            norad_id_2=pair.norad_id_2,
            name_2=name_2,
            distance_km=pair.distance_km,
        )
        db.add(event)
        new_events += 1

        # notify anyone tracking either object in this pair
        watchers = (
            db.query(SavedSatellite, User)
            .join(User, User.id == SavedSatellite.user_id)
            .filter(
                SavedSatellite.norad_id.in_([pair.norad_id_1, pair.norad_id_2]),
                SavedSatellite.email_alerts_enabled.is_(True),
            )
            .all()
        )
        for saved, user in watchers:
            if send_conjunction_alert(user.email, name_1, name_2, pair.distance_km):
                alerts_sent += 1

    db.commit()

    return RefreshResult(
        satellites_loaded=satellites_loaded,
        new_conjunctions_found=new_events,
        alerts_sent=alerts_sent,
    )
