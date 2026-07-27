"""
location_router.py
-------------------
GET /api/location/geocode?city=<name>

Turns a city name the user types ("Pune", "Tokyo", "New York") into
latitude/longitude, using OpenStreetMap's free Nominatim geocoding
service. This is what powers "enter your city and see when a satellite
passes overhead" — the frontend calls this first, then feeds the
returned lat/lon into the existing /api/satellites/{id}/passes endpoint.

Nominatim's usage policy requires a descriptive User-Agent and asks
callers not to hammer it — fine for this project's traffic level.
"""
import requests
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/location", tags=["location"])

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


@router.get("/geocode")
def geocode_city(city: str = Query(..., min_length=2)):
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={"q": city, "format": "json", "limit": 1},
            headers={"User-Agent": "orbital-watch-student-project/1.0"},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json()
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Location lookup service unavailable")

    if not results:
        raise HTTPException(status_code=404, detail=f"Could not find a location matching '{city}'")

    match = results[0]
    return {
        "latitude_deg": float(match["lat"]),
        "longitude_deg": float(match["lon"]),
        "display_name": match["display_name"],
    }
