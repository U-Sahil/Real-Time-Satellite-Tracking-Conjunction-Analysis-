"""
conjunction.py
--------------
Conjunction screening = finding which pairs of satellites are dangerously
close to each other right now.

THE NAIVE APPROACH: compare every satellite to every other satellite.
For N satellites that's N*(N-1)/2 distance checks. CelesTrak's active
catalog has 10,000+ objects, so the naive approach is ~50 million distance
calculations, every time you want an updated screening. That does not
scale.

THE APPROACH USED HERE: build a KD-tree, a data structure that organizes
the 3D positions so that "give me everything within X km of this point"
can be answered in roughly O(log N) time instead of O(N). scipy's
cKDTree does this for us — we just need to feed it the right data and
interpret the result.

query_ball_tree() is the key call: given two KD-trees (here, both built
from the same snapshot) and a radius, it returns every pair of points
within that radius of each other, across the WHOLE dataset, in one call.
That turns "50 million comparisons" into "one spatial query."
"""
from dataclasses import dataclass

from scipy.spatial import cKDTree

from app.config import settings


@dataclass
class ConjunctionPair:
    norad_id_1: int
    norad_id_2: int
    distance_km: float


def screen_for_conjunctions(
    snapshot: dict[int, tuple[float, float, float]],
    threshold_km: float | None = None,
    min_km: float = 0.5,
) -> list[ConjunctionPair]:
    """
    snapshot: {norad_id: (x_km, y_km, z_km)} for every tracked satellite
              at one instant (produced by propagator.eci_snapshot()).
    threshold_km: flag any pair closer than this. Defaults to the value
                  configured in app/config.py.
    min_km: pairs closer than THIS are excluded entirely. This matters
            because CelesTrak's active catalog lists things like the
            ISS's separate modules, or a Soyuz/Progress/Cygnus currently
            docked to the station, as distinct objects — they are
            physically attached, so they're always ~0 km apart. That's
            not a "close approach" in any meaningful sense (nothing is
            converging, there's no collision risk to flag), it's just
            noise from how the catalog is structured. Filtering out
            anything under `min_km` keeps results focused on genuinely
            independent objects that are actually converging.

    Returns every pair whose distance is between min_km and threshold_km,
    sorted by distance (closest / most dangerous first).
    """
    if threshold_km is None:
        threshold_km = settings.conjunction_threshold_km

    if len(snapshot) < 2:
        return []

    norad_ids = list(snapshot.keys())
    points = [snapshot[nid] for nid in norad_ids]

    tree = cKDTree(points)
    # query_pairs finds every pair of points within `threshold_km` of each
    # other in a single spatial pass — this is the O(log N) step that
    # replaces the naive O(N^2) all-pairs comparison.
    close_pairs = tree.query_pairs(r=threshold_km)

    results = []
    for i, j in close_pairs:
        id_a, id_b = norad_ids[i], norad_ids[j]
        ax, ay, az = points[i]
        bx, by, bz = points[j]
        distance = ((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2) ** 0.5
        if distance < min_km:
            continue  # almost certainly a docked/attached object, not a real conjunction
        results.append(ConjunctionPair(id_a, id_b, distance))

    results.sort(key=lambda pair: pair.distance_km)
    return results
