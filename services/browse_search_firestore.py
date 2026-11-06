"""Firestore fallback engine path for browse search."""

from __future__ import annotations

from typing import Any

from services.browse_search_common import (
    SORT_DISTANCE,
    SORT_NEWEST,
    SORT_PRICE_ASC,
    SORT_PRICE_DESC,
    _finalize_browse_page,
    _firestore_fetch_limit,
    _matches_category,
    _serialize_listing_hit,
    map_feed_doc,
)
from services.search_relevance import matches_keyword, normalize_search_query, search_relevance_score


def _apply_firestore_post_filters(
    docs: list[dict[str, Any]],
    *,
    q: str,
    category_ids: list[str],
    min_price: float | None,
    max_price: float | None,
    has_location: bool | None,
    lat: float | None,
    lng: float | None,
    radius_km: float | None,
    blocked_sellers: set[str],
) -> list[dict[str, Any]]:
    from services.geohash import haversine_distance_km

    if q:
        docs = [doc for doc in docs if matches_keyword(doc, q)]

    if len(category_ids) > 1:
        docs = [doc for doc in docs if _matches_category(doc, category_ids)]

    if min_price is not None:
        docs = [doc for doc in docs if doc.get("price", 0) >= min_price]
    if max_price is not None:
        docs = [doc for doc in docs if doc.get("price", 0) <= max_price]

    if has_location is True:
        docs = [doc for doc in docs if doc.get("location")]
    elif has_location is False:
        docs = [doc for doc in docs if not doc.get("location")]

    if lat is not None and lng is not None and radius_km is not None:
        docs = [
            doc
            for doc in docs
            if doc.get("location")
            and haversine_distance_km(lat, lng, doc["location"][0], doc["location"][1])
            <= radius_km
        ]

    if blocked_sellers:
        docs = [doc for doc in docs if doc.get("sellerId") not in blocked_sellers]

    return docs


def _sort_firestore_docs(
    docs: list[dict[str, Any]],
    *,
    sort: str,
    lat: float | None,
    lng: float | None,
    q: str = "",
) -> list[dict[str, Any]]:
    from services.geohash import haversine_distance_km

    normalized_query = normalize_search_query(q)
    if normalized_query:
        docs.sort(
            key=lambda doc: (
                -search_relevance_score(doc, normalized_query),
                -(doc.get("createdAt") or 0),
            )
        )
        return docs

    normalized_sort = (sort or SORT_NEWEST).strip().lower()
    if normalized_sort == SORT_DISTANCE and lat is not None and lng is not None:
        docs.sort(
            key=lambda doc: haversine_distance_km(
                lat,
                lng,
                doc["location"][0],
                doc["location"][1],
            )
            if doc.get("location")
            else float("inf"),
        )
    elif normalized_sort == SORT_PRICE_ASC:
        docs.sort(key=lambda doc: doc.get("price", 0))
    elif normalized_sort == SORT_PRICE_DESC:
        docs.sort(key=lambda doc: doc.get("price", 0), reverse=True)

    return docs


def _collect_firestore_feed_page(
    *,
    base_query,
    target_end: int,
    q: str,
    category_ids: list[str],
    min_price: float | None,
    max_price: float | None,
    has_location: bool | None,
    lat: float | None,
    lng: float | None,
    radius_km: float | None,
    blocked_sellers: set[str],
    page_size: int,
    max_scan_docs: int | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Walk the feed with Firestore cursors until we have target_end filtered rows or exhaust the feed."""
    from google.cloud.firestore_v1 import Query

    collected: list[dict[str, Any]] = []
    last_snapshot = None
    feed_exhausted = False
    batch_size = max(page_size * 2, 50)
    max_batches = 500
    batches = 0
    raw_scanned = 0

    while len(collected) < target_end and not feed_exhausted and batches < max_batches:
        batches += 1
        batch_query = base_query.order_by("createdAt", direction=Query.DESCENDING).limit(batch_size + 1)
        if last_snapshot is not None:
            batch_query = batch_query.start_after(last_snapshot)

        snapshots = list(batch_query.stream())
        if not snapshots:
            feed_exhausted = True
            break

        feed_has_more = len(snapshots) > batch_size
        page_snapshots = snapshots[:batch_size]
        last_snapshot = page_snapshots[-1]
        raw_scanned += len(page_snapshots)

        mapped = [map_feed_doc(doc.id, doc.to_dict() or {}) for doc in page_snapshots]
        filtered = _apply_firestore_post_filters(
            mapped,
            q=q,
            category_ids=category_ids,
            min_price=min_price,
            max_price=max_price,
            has_location=has_location,
            lat=lat,
            lng=lng,
            radius_km=radius_km,
            blocked_sellers=blocked_sellers,
        )
        collected.extend(filtered)

        if not feed_has_more:
            feed_exhausted = True

        if max_scan_docs is not None and raw_scanned >= max_scan_docs:
            break

    return collected, not feed_exhausted and (
        max_scan_docs is None or raw_scanned < max_scan_docs
    )


def browse_search_firestore(
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
    from google.cloud.firestore_v1 import FieldFilter

    from services.firebase_app import get_db

    db = get_db()
    feed_ref = (
        db.collection("communityFeeds")
        .document(community_id or "all")
        .collection("listings")
    )

    base_query = feed_ref.where(filter=FieldFilter("status", "==", "active"))
    if len(category_ids) == 1:
        base_query = base_query.where(filter=FieldFilter("primaryCategoryId", "==", category_ids[0]))

    normalized_sort = (sort or SORT_NEWEST).strip().lower()
    target_start = (page - 1) * page_size
    target_end = target_start + page_size
    search_active = bool(q.strip())

    if normalized_sort == SORT_NEWEST:
        fetch_limit = _firestore_fetch_limit(page, page_size)
        collect_target = fetch_limit if search_active else target_end
        collected, feed_has_more = _collect_firestore_feed_page(
            base_query=base_query,
            target_end=collect_target,
            q=q,
            category_ids=category_ids,
            min_price=min_price,
            max_price=max_price,
            has_location=has_location,
            lat=lat,
            lng=lng,
            radius_km=radius_km,
            blocked_sellers=blocked_sellers,
            page_size=page_size,
            max_scan_docs=fetch_limit,
        )
        if search_active:
            collected = _sort_firestore_docs(
                collected,
                sort=sort,
                lat=lat,
                lng=lng,
                q=q,
            )
        page_docs = [_serialize_listing_hit(doc) for doc in collected[target_start:target_end]]
        has_more = len(collected) > target_end or feed_has_more
        total = len(collected) if not has_more else max(len(collected), target_end + 1)
    else:
        # Non-newest sorts require in-memory ordering; scan a bounded window for this page.
        fetch_limit = _firestore_fetch_limit(page, page_size)
        query = base_query.order_by("createdAt", direction="DESCENDING").limit(fetch_limit)
        docs = [map_feed_doc(doc.id, doc.to_dict() or {}) for doc in query.stream()]
        docs = _apply_firestore_post_filters(
            docs,
            q=q,
            category_ids=category_ids,
            min_price=min_price,
            max_price=max_price,
            has_location=has_location,
            lat=lat,
            lng=lng,
            radius_km=radius_km,
            blocked_sellers=blocked_sellers,
        )
        docs = _sort_firestore_docs(docs, sort=sort, lat=lat, lng=lng, q=q)
        page_docs = [_serialize_listing_hit(doc) for doc in docs[target_start:target_end]]
        total = len(docs)
        has_more = target_end < total or len(docs) >= fetch_limit

    return _finalize_browse_page(
        listings=page_docs,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
        engine="firestore",
    )


# Backward-compatible private alias.
_browse_search_firestore = browse_search_firestore
