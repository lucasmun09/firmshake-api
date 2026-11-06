"""Typesense browse query_by includes description for full-text body matching."""

from __future__ import annotations

from services.browse_search_typesense import browse_search_typesense


class _FakeTypesenseClient:
    def __init__(self) -> None:
        self.last_params: dict | None = None

    def search(self, params: dict) -> dict:
        self.last_params = params
        return {"hits": [], "found": 0}


def test_typesense_query_by_includes_description():
    client = _FakeTypesenseClient()
    browse_search_typesense(
        client,
        q="office desk",
        community_id="all",
        category_ids=[],
        min_price=None,
        max_price=None,
        has_location=None,
        lat=None,
        lng=None,
        radius_km=None,
        sort="newest",
        page=1,
        page_size=24,
        blocked_sellers=set(),
    )

    assert client.last_params is not None
    assert client.last_params["query_by"] == "title,sellerName,description"
    assert client.last_params["query_by_weights"] == "4,2,1"
    assert client.last_params["q"] == "office desk"
