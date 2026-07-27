"""
tle_store.py
------------
Holds the current set of TLEs (Two-Line Element sets) in memory and knows
how to refresh them from CelesTrak.

Design choice: TLEs are kept in memory (a plain Python dict), not in the
database. They're re-downloaded periodically (via /api/admin/refresh-tles,
called on a cron by the Java scheduler) and are only ever "fresh for a few
hours" data anyway — there's no value in persisting them, and recomputing
positions from a live in-memory set is fast and simple.
"""
import logging
import threading

import requests
from skyfield.api import EarthSatellite, load

from app.config import settings

logger = logging.getLogger("tle_store")

_ts = load.timescale()


class TLEStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._satellites: dict[int, EarthSatellite] = {}

    def refresh(self) -> int:
        """
        Downloads the latest active-satellite TLE catalog from CelesTrak
        and rebuilds the in-memory satellite table. Returns how many
        objects were loaded.
        """
        response = requests.get(settings.celestrak_url, timeout=30)
        response.raise_for_status()
        lines = [ln.strip() for ln in response.text.splitlines() if ln.strip()]

        new_table: dict[int, EarthSatellite] = {}
        # TLE catalog files come in groups of 3 lines: name, line1, line2
        for i in range(0, len(lines) - 2, 3):
            name, line1, line2 = lines[i], lines[i + 1], lines[i + 2]
            try:
                sat = EarthSatellite(line1, line2, name, _ts)
                new_table[sat.model.satnum] = sat
            except Exception:  # skip malformed entries rather than fail the whole batch
                continue

        with self._lock:
            self._satellites = new_table

        logger.info("TLE refresh complete: %d satellites loaded", len(new_table))
        return len(new_table)

    def all(self) -> dict[int, EarthSatellite]:
        with self._lock:
            return dict(self._satellites)

    def get(self, norad_id: int) -> EarthSatellite | None:
        with self._lock:
            return self._satellites.get(norad_id)

    def is_empty(self) -> bool:
        with self._lock:
            return len(self._satellites) == 0


# a single shared store used by the whole app
tle_store = TLEStore()
