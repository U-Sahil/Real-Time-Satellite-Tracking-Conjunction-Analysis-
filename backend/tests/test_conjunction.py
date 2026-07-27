from app.orbital.conjunction import screen_for_conjunctions


def test_no_conjunctions_when_far_apart():
    snapshot = {
        1: (0.0, 0.0, 0.0),
        2: (10000.0, 0.0, 0.0),  # 10,000 km away — nowhere near close
    }
    result = screen_for_conjunctions(snapshot, threshold_km=25.0)
    assert result == []


def test_detects_close_pair():
    snapshot = {
        1: (0.0, 0.0, 0.0),
        2: (10.0, 0.0, 0.0),  # 10 km apart — inside a 25 km threshold
        3: (5000.0, 0.0, 0.0),  # far away, should not be flagged
    }
    result = screen_for_conjunctions(snapshot, threshold_km=25.0)
    assert len(result) == 1
    pair = result[0]
    assert {pair.norad_id_1, pair.norad_id_2} == {1, 2}
    assert abs(pair.distance_km - 10.0) < 1e-6


def test_results_sorted_closest_first():
    snapshot = {
        1: (0.0, 0.0, 0.0),
        2: (20.0, 0.0, 0.0),
        3: (5.0, 0.0, 0.0),
    }
    result = screen_for_conjunctions(snapshot, threshold_km=30.0)
    distances = [pair.distance_km for pair in result]
    assert distances == sorted(distances)


def test_min_km_filters_out_docked_objects():
    # Two objects 0.05 km apart simulate something like ISS modules —
    # physically attached, not a meaningful "conjunction".
    snapshot = {
        1: (0.0, 0.0, 0.0),
        2: (0.05, 0.0, 0.0),
        3: (10.0, 0.0, 0.0),  # a real independent close approach
    }
    result = screen_for_conjunctions(snapshot, threshold_km=25.0, min_km=0.5)
    pair_ids = [{pair.norad_id_1, pair.norad_id_2} for pair in result]
    assert {1, 2} not in pair_ids
    assert {1, 3} in pair_ids


def test_empty_snapshot_returns_no_pairs():
    assert screen_for_conjunctions({}, threshold_km=25.0) == []
    assert screen_for_conjunctions({1: (0, 0, 0)}, threshold_km=25.0) == []
