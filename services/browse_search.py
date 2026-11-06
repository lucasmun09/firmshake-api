"""Browse search orchestration (Typesense with Firestore fallback).

Parallel-agent split:
- `browse_search_common.py` — client, serialize, shared filters
- `browse_search_typesense.py` — Typesense engine path
- `browse_search_firestore.py` — Firestore fallback path
- this module — public `browse_search()` + map-pin attach + re-exports
"""

from __future__ import annotations

import logging
from typing import Any

from services.browse_search_common import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    SORT_DISTANCE,
    SORT_NEWEST,
    SORT_PRICE_ASC,
    SORT_PRICE_DESC,
    TypesenseClient,
    VALID_SORTS,
    _category_filter_typesense,
    _finalize_browse_page,
    _firestore_fetch_limit,
    _get_blocked_seller_ids,
    _matches_category,
    _normalize_category_ids,
    _resolve_sort,
    _serialize_listing_hit,
    map_feed_doc,
)
from services.browse_search_firestore import (
    _apply_firestore_post_filters,
    _browse_search_firestore,
    _collect_firestore_feed_page,
    _sort_firestore_docs,
    browse_search_firestore,
)
from services.browse_search_typesense import (
    _browse_search_typesense,
    browse_search_typesense,
)
from services.search_relevance import matches_keyword

logger = logging.getLogger("firmshake.browse_search")

__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "SORT_DISTANCE",
    "SORT_NEWEST",
    "SORT_PRICE_ASC",
    "SORT_PRICE_DESC",
    "TypesenseClient",
    "VALID_SORTS",
    "_apply_firestore_post_filters",
    "_browse_search_firestore",
    "_browse_search_typesense",
    "_category_filter_typesense",
    "_collect_firestore_feed_page",
    "_finalize_browse_page",
    "_firestore_fetch_limit",
    "_get_blocked_seller_ids",
    "_matches_category",
    "_normalize_category_ids",
    "_resolve_sort",
    "_serialize_listing_hit",
    "_sort_firestore_docs",
    "browse_search",
    "browse_search_firestore",
    "browse_search_typesense",
    "map_feed_doc",
    "matches_keyword",
]


def browse_search(
    *,
    q: str = "",
    community_id: str = "all",
    category_id: str = "",
    category_ids: list[str] | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    has_location: bool | None = None,
    lat: float | None = None,
    lng: float | None = None,
    radius_miles: float | None = None,
    radius_km: float | None = None,
    sort: str = SORT_NEWEST,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    viewer_uid: str | None = None,
) -> dict[str, Any]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    community_id = (community_id or "all").strip() or "all"
    normalized_categories = _normalize_category_ids(category_id, category_ids)
    blocked_sellers = _get_blocked_seller_ids(viewer_uid)

    if radius_miles is not None and radius_km is None:
        radius_km = radius_miles * 1.60934
    elif radius_km is not None and radius_miles is None:
        radius_miles = radius_km / 1.60934

    client = TypesenseClient()
    if client.enabled:
        try:
            result = browse_search_typesense(
                client,
                q=q,
                community_id=community_id,
                category_ids=normalized_categories,
                min_price=min_price,
                max_price=max_price,
                has_location=has_location,
                lat=lat,
                lng=lng,
                radius_km=radius_km,
                sort=sort,
                page=page,
                page_size=page_size,
                blocked_sellers=blocked_sellers,
            )
            return _attach_map_pins(result)
        except Exception as exc:
            logger.warning(
                "Typesense browse search failed; falling back to Firestore",
                exc_info=exc,
            )

    result = browse_search_firestore(
        q=q,
        community_id=community_id,
        category_ids=normalized_categories,
        min_price=min_price,
        max_price=max_price,
        has_location=has_location,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        sort=sort,
        page=page,
        page_size=page_size,
        blocked_sellers=blocked_sellers,
    )
    return _attach_map_pins(result)


def _attach_map_pins(result: dict[str, Any]) -> dict[str, Any]:
    from services.browse_map_pins import aggregate_browse_map_pins

    enriched = dict(result)
    enriched["pinGroups"] = aggregate_browse_map_pins(result.get("listings") or [])
    return enriched
