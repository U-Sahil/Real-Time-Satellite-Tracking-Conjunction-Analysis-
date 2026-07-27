import os

_TEST_DB_PATH = "./test_satellite_platform.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB_PATH}")


if os.path.exists(_TEST_DB_PATH):
    os.remove(_TEST_DB_PATH)

import pytest
from fastapi.testclient import TestClient
from skyfield.api import EarthSatellite, load

from app.main import app
from app.orbital.tle_store import tle_store

client = TestClient(app)

# A real ISS TLE (any valid TLE works fine for structural tests like these —
# we're testing our own code's behavior, not tracking accuracy).
ISS_LINE1 = "1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9994"
ISS_LINE2 = "2 25544  51.6416 339.5152 0006703  55.5710 304.6008 15.50423123 12345"


@pytest.fixture(autouse=True)
def fake_satellite_catalog():
    ts = load.timescale()
    sat = EarthSatellite(ISS_LINE1, ISS_LINE2, "ISS (ZARYA)", ts)
    tle_store._satellites = {25544: sat}
    yield
    tle_store._satellites = {}


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["satellites_loaded"] == 1


def test_list_satellites():
    response = client.get("/api/satellites")
    assert response.status_code == 200
    names = [s["name"] for s in response.json()]
    assert "ISS (ZARYA)" in names


def test_get_position_success():
    response = client.get("/api/satellites/25544/position")
    assert response.status_code == 200
    body = response.json()
    assert body["norad_id"] == 25544
    assert -90 <= body["latitude_deg"] <= 90
    assert -180 <= body["longitude_deg"] <= 180


def test_get_position_unknown_satellite_returns_404():
    response = client.get("/api/satellites/999999/position")
    assert response.status_code == 404


def test_register_and_login_flow():
    register_response = client.post(
        "/api/auth/register",
        json={"username": "recruiter_demo", "email": "demo@example.com", "password": "strongpassword123"},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/auth/login",
        data={"username": "recruiter_demo", "password": "strongpassword123"},
    )
    assert login_response.status_code == 200
    assert "access_token" in login_response.json()


def test_saved_satellite_requires_auth():
    response = client.get("/api/satellites/saved")
    assert response.status_code == 401


def test_admin_refresh_requires_key():
    response = client.post("/api/admin/refresh-tles")
    assert response.status_code == 403


def test_bulk_positions_returns_current_and_lookahead():
    response = client.get("/api/satellites/positions/bulk?ids=25544")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    entry = body[0]
    assert entry["norad_id"] == 25544
    # both a "now" and a "lookahead" position must be present for smooth interpolation
    for key in ("lat0", "lon0", "alt0", "lat1", "lon1", "alt1"):
        assert key in entry


def test_bulk_positions_unknown_id_is_skipped_not_errored():
    response = client.get("/api/satellites/positions/bulk?ids=999999")
    assert response.status_code == 200
    assert response.json() == []
