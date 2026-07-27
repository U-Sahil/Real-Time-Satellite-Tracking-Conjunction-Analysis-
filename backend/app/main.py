import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.orbital.tle_store import tle_store
from app.routers import admin_router, auth_router, conjunctions_router, location_router, satellites_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Real-Time Satellite Tracking & Conjunction Screening Platform",
    description=(
        "Live satellite position tracking (SGP4) and close-approach "
        "conjunction screening (KD-tree spatial search) over the public "
        "CelesTrak TLE catalog."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # fine for a student/demo project; restrict in real production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(satellites_router.router)
app.include_router(conjunctions_router.router)
app.include_router(admin_router.router)
app.include_router(location_router.router)


@app.on_event("startup")
def load_initial_tles():
    try:
        count = tle_store.refresh()
        logger.info("Startup TLE load complete: %d satellites", count)
    except Exception as exc:
        # Don't crash the app if CelesTrak is briefly unreachable on boot —
        # the dashboard will just show "no data yet" until the next refresh.
        logger.warning("Startup TLE load failed, will retry on next scheduled refresh: %s", exc)


@app.get("/api/health", tags=["health"])
def health_check():
    return {"status": "ok", "satellites_loaded": len(tle_store.all())}


# Serve the dashboard (frontend/) at the site root. This must be mounted
# LAST, after all /api/... routes, so it doesn't shadow them.
_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.isdir(_FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
