"""
propagator.py
-------------
This is the orbital-mechanics core. Everything else in the project is
plumbing around this file.

Given a satellite's TLE, the SGP4 algorithm (implemented by the `sgp4`
library, wrapped here through `skyfield` for convenience) predicts that
satellite's exact position at any point in time — past or future. This
module turns that raw capability into the three things the app needs:

1. current_position()  -> live lat/lon/altitude, for the map
2. next_passes()        -> when a satellite will be visible from a given
                            ground location, for the "next pass" feature
3. eci_snapshot()        -> raw 3D positions (km) for every tracked
                            satellite at one instant, which is exactly
                            what conjunction.py needs to feed into its
                            KD-tree screening
"""
import datetime as dt

from skyfield.api import wgs84, load
from skyfield.toposlib import GeographicPosition

from app.orbital.tle_store import tle_store

_ts = load.timescale()


def current_position(norad_id: int):
    """Returns live lat/lon/altitude/velocity for one satellite, or None."""
    sat = tle_store.get(norad_id)
    if sat is None:
        return None

    t = _ts.now()
    geocentric = sat.at(t)
    subpoint = wgs84.subpoint(geocentric)
    velocity_km_s = geocentric.velocity.km_per_s
    speed = (velocity_km_s[0] ** 2 + velocity_km_s[1] ** 2 + velocity_km_s[2] ** 2) ** 0.5

    return {
        "norad_id": norad_id,
        "name": sat.name,
        "latitude_deg": subpoint.latitude.degrees,
        "longitude_deg": subpoint.longitude.degrees,
        "altitude_km": subpoint.elevation.km,
        "velocity_km_s": speed,
        "timestamp": t.utc_datetime(),
    }


def next_passes(norad_id: int, latitude_deg: float, longitude_deg: float, days: int = 3):
    """
    Predicts upcoming times this satellite rises above the horizon at a
    ground location, culminates (highest point), and sets again.
    """
    sat = tle_store.get(norad_id)
    if sat is None:
        return None

    observer: GeographicPosition = wgs84.latlon(latitude_deg, longitude_deg)
    t0 = _ts.now()
    t1 = _ts.from_datetime(t0.utc_datetime() + dt.timedelta(days=days))

    times, events = sat.find_events(observer, t0, t1, altitude_degrees=10.0)

    passes = []
    current = {}
    for t, event in zip(times, events):
        if event == 0:  # rise
            current = {"rise_time": t.utc_datetime()}
        elif event == 1:  # culminate
            difference = sat - observer
            alt, _, _ = difference.at(t).altaz()
            current["culminate_time"] = t.utc_datetime()
            current["max_elevation_deg"] = alt.degrees
        elif event == 2:  # set
            current["set_time"] = t.utc_datetime()
            if {"rise_time", "culminate_time", "set_time", "max_elevation_deg"} <= current.keys():
                passes.append(current)
            current = {}

    return passes


def bulk_positions(satellites: dict, norad_ids: list[int] | None = None, lookahead_seconds: float = 6.0, limit: int = 2500):
    """
    Propagates many satellites at once and returns, for each, BOTH its
    position right now AND its predicted position `lookahead_seconds`
    in the future.

    Why two positions instead of one: the browser polls this endpoint
    every few seconds, but satellites move continuously. If the frontend
    only had "position right now", the marker would visibly jump/teleport
    on every poll instead of gliding. By also returning where the
    satellite WILL be a few seconds from now, the frontend can smoothly
    interpolate ("lerp") between the two points every animation frame,
    so the motion on screen looks continuous and real-time — the same
    trick real tracking sites use — even though we only hit the server
    a few times a minute.

    norad_ids: if given, only propagate this subset (used for the
    handful of satellites the user has selected/saved/in an alert).
    If omitted, propagates up to `limit` satellites from the whole
    catalog, for the "swarm of dots" overview view.
    """
    t0 = _ts.now()
    t1 = _ts.from_datetime(t0.utc_datetime() + dt.timedelta(seconds=lookahead_seconds))

    if norad_ids is not None:
        items = [(nid, satellites[nid]) for nid in norad_ids if nid in satellites]
    else:
        items = list(satellites.items())[:limit]

    results = []
    for norad_id, sat in items:
        try:
            sub0 = wgs84.subpoint(sat.at(t0))
            sub1 = wgs84.subpoint(sat.at(t1))
            results.append({
                "norad_id": norad_id,
                "name": sat.name,
                "lat0": sub0.latitude.degrees,
                "lon0": sub0.longitude.degrees,
                "alt0": sub0.elevation.km,
                "lat1": sub1.latitude.degrees,
                "lon1": sub1.longitude.degrees,
                "alt1": sub1.elevation.km,
            })
        except Exception:
            continue
    return results


def eci_snapshot(satellites: dict) -> dict[int, tuple[float, float, float]]:
    """
    Propagates EVERY given satellite to the current instant and returns
    their raw Earth-Centered-Inertial (x, y, z) positions in kilometers.

    This is deliberately separate from current_position(): that function
    returns human-friendly lat/lon for one satellite, this one returns
    raw cartesian coordinates for many satellites at once, because that's
    the format the KD-tree spatial index needs for distance comparisons.
    """
    t = _ts.now()
    snapshot = {}
    for norad_id, sat in satellites.items():
        try:
            position = sat.at(t).position.km
            snapshot[norad_id] = (position[0], position[1], position[2])
        except Exception:
            continue
    return snapshot
