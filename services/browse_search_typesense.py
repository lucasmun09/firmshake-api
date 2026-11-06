"""Typesense engine path for browse search."""

from __future__ import annotations

from typing import Any

from services.browse_search_common import (
    SORT_NEWEST,
    TypesenseClient,
    _category_filter_typesense,
    _finalize_browse_page,
    _resolve_sort,
    _serialize_listing_hit,
)


def browse_search_typesense(
    client: TypesenseClient,
    *,
    q: str,
    community_id: str,
    category_ids: list[str],
    min_price: float | None,
    max_price: float | None,
    has_location: bool | None,
    lat: float | None,
    lng: float | None,
    radius_km: float | None,
    sort: str,
    page: int,
    page_size: int,
    blocked_sellers: set[str],
) -> dict[str, Any]:
    filters = ["status:=active"]
    if community_id and community_id != "all":
        filters.append(f"communityIds:={community_id}")

    category_filter = _category_filter_typesense(category_ids)
    if category_filter:
        filters.append(category_filter)

    if min_price is not None:
        filters.append(f"price:>={min_price}")
    if max_price is not None:
        filters.append(f"price:<={max_price}")
    if has_location is True:
        filters.append("hasLocation:=true")
    elif has_location is False:
        filters.append("hasLocation:=false")

    if lat is not None and lng is not None and radius_km is not None:
        filters.append(f"location:({lat}, {lng}, {radius_km * 1000} m)")

    if blocked_sellers:
        blocked = ",".join(sorted(blocked_sellers))
        filters.append(f"sellerId:!=[{blocked}]")

    params = {
        "q": q or "*",
        # TODO: add description to query_by when product wants full-text body matching.
        "query_by": "title,sellerName",
        "query_by_weights": "3,1",
        "filter_by": " && ".join(filters),
        "page": str(page),
        "per_page": str(page_size),
    }

    normalized_sort = (sort or SORT_NEWEST).strip().lower()
    if q.strip() and normalized_sort == SORT_NEWEST:
        params["sort_by"] = "_text_match:desc,createdAt:desc"
    else:
        params["sort_by"] = _resolve_sort(sort, lat=lat, lng=lng)

    result = client.search(params)
    hits = [_serialize_listing_hit(hit["document"]) for hit in result.get("hits", [])]
    total = int(result.get("found", 0))

    return _finalize_browse_page(
        listings=hits,
        total=total,
        page=page,
        page_size=page_size,
        has_more=page * page_size < total,
        engine="typesense",
    )


# Backward-compatible private alias used by older tests/imports.
_browse_search_typesense = browse_search_typesense
