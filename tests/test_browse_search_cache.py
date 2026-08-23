import time

from services.browse_search_cache import (
    build_browse_search_cache_key,
    clear_browse_search_cache,
    get_cached_browse_search,
    set_cached_browse_search,
)


def setup_function():
    clear_browse_search_cache()


def test_build_browse_search_cache_key_is_stable():
    params = {
        "q": "bike",
        "community_id": "all",
        "lat": 38.75,
        "lng": -77.47,
        "radius_miles": 10.0,
        "page": 1,
        "page_size": 24,
        "sort": "newest",
    }
    first = build_browse_search_cache_key(params, "user-a")
    second = build_browse_search_cache_key(dict(params), "user-a")
    different_user = build_browse_search_cache_key(params, "user-b")

    assert first == second
    assert first != different_user


def test_browse_search_cache_ttl_expires(monkeypatch):
    params = {"q": "", "community_id": "all", "page": 1, "page_size": 24}
    key = build_browse_search_cache_key(params, None)
    payload = {"listings": [], "total": 0, "page": 1, "pageSize": 24, "hasMore": False}

    now = {"value": 1000.0}

    def fake_monotonic():
        return now["value"]

    monkeypatch.setattr(time, "monotonic", fake_monotonic)

    set_cached_browse_search(key, payload, ttl_seconds=45)
    assert get_cached_browse_search(key) == payload

    now["value"] = 1046.0
    assert get_cached_browse_search(key) is None
