"""Legacy listing search — delegates to browse_search for Typesense/Firestore search."""

from services.browse_search import (
    TypesenseClient,
    map_feed_doc,
    matches_keyword,
    browse_search,
)

__all__ = [
    "TypesenseClient",
    "map_feed_doc",
    "matches_keyword",
    "search_listings",
    "browse_search",
]


def search_listings(
    *,
    q: str = "",
    community_id: str = "all",
    category_id: str = "",
    min_price: float | None = None,
    max_price: float | None = None,
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float | None = None,
    page: int = 1,
    page_size: int = 24,
) -> dict:
    return browse_search(
        q=q,
        community_id=community_id,
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        page=page,
        page_size=page_size,
    )
