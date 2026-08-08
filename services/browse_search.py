"""Browse search via Typesense with Firestore fallback."""

from __future__ import annotations

import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from config import FIREBASE_PROJECT_ID
from services.search_relevance import matches_keyword, normalize_search_query, search_relevance_score

logger = logging.getLogger("firmshake.browse_search")

DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 100

SORT_NEWEST = "newest"
SORT_PRICE_ASC = "price_asc"
SORT_PRICE_DESC = "price_desc"
SORT_DISTANCE = "distance"

VALID_SORTS = {SORT_NEWEST, SORT_PRICE_ASC, SORT_PRICE_DESC, SORT_DISTANCE}


class TypesenseClient:
    def __init__(self) -> None:
        self.host = os.getenv("TYPESENSE_HOST", "").strip().rstrip("/")
        self.api_key = os.getenv("TYPESENSE_API_KEY", "").strip()
        self.collection = os.getenv("TYPESENSE_LISTINGS_COLLECTION", "listings")

    @property
    def enabled(self) -> bool:
        return bool(self.host and self.api_key)

    def upsert(self, document: dict[str, Any]) -> None:
        if not self.enabled:
            return

        payload = __import__("json").dumps(document).encode("utf-8")
        request = urllib.request.Request(
            f"{self.host}/collections/{self.collection}/documents?action=upsert",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-TYPESENSE-API-KEY": self.api_key,
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10):
            return

    def search(self, params: dict[str, str]) -> dict[str, Any]:
        if not self.enabled:
            return {"hits": [], "found": 0}

        query = "&".join(f"{key}={urllib.parse.quote(value)}" for key, value in params.items())
        request = urllib.request.Request(
            f"{self.host}/collections/{self.collection}/documents/search?{query}",
            headers={"X-TYPESENSE-API-KEY": self.api_key},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return __import__("json").loads(response.read().decode("utf-8"))


def map_feed_doc(doc_id: str, data: dict[str, Any]) -> dict[str, Any]:
    created_at = data.get("createdAt")
    created_ms = 0
    if created_at is not None and hasattr(created_at, "timestamp"):
        created_ms = int(created_at.timestamp() * 1000)

    location = data.get("location")
    lat_lng = None
    if location is not None and hasattr(location, "latitude"):
        lat_lng = [location.latitude, location.longitude]
    elif data.get("lat") is not None and data.get("lng") is not None:
        lat_lng = [float(data["lat"]), float(data["lng"])]

    return {
        "id": doc_id,
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "communityIds": data.get("communityIds", []),
        "primaryCategoryId": data.get("primaryCategoryId", "general"),
        "categoryIds": data.get("categoryIds", []),
        "price": data.get("price", 0),
        "status": data.get("status", "active"),
        "sellerId": data.get("sellerId", ""),
        "sellerName": data.get("sellerName", ""),
        "imageUrl": data.get("imageUrl", ""),
        "createdAt": created_ms,
        "location": lat_lng,
        "geohash": data.get("geohash"),
        "city": data.get("city"),
        "region": data.get("region"),
        "hasLocation": lat_lng is not None,
    }


def _normalize_category_ids(category_id: str, category_ids: list[str] | None) -> list[str]:
    ids: list[str] = []
    if category_id:
        ids.append(category_id.strip())
    if category_ids:
        ids.extend(str(value).strip() for value in category_ids if str(value).strip())
    return list(dict.fromkeys(ids))


def _category_filter_typesense(category_ids: list[str]) -> str | None:
    if not category_ids:
        return None
    if len(category_ids) == 1:
        cat = category_ids[0]
        return f"(primaryCategoryId:={cat} || categoryIds:={cat})"
    joined = ",".join(category_ids)
    return f"(primaryCategoryId:=[{joined}] || categoryIds:=[{joined}])"


def _matches_category(listing: dict[str, Any], category_ids: list[str]) -> bool:
    if not category_ids:
        return True
    primary = str(listing.get("primaryCategoryId") or "")
    all_cats = {str(value) for value in (listing.get("categoryIds") or [])}
    all_cats.add(primary)
    return any(cat in all_cats for cat in category_ids)


def _serialize_listing_hit(hit: dict[str, Any]) -> dict[str, Any]:
    location = hit.get("location")
    lat = hit.get("lat")
    lng = hit.get("lng")
    if isinstance(location, list) and len(location) == 2:
        lat = location[0]
        lng = location[1]

    response: dict[str, Any] = {
        "id": hit.get("id", ""),
        "title": hit.get("title", ""),
        "titleLower": str(hit.get("title", "")).lower(),
        "description": hit.get("description", ""),
        "price": hit.get("price", 0),
        "imageUrls": hit.get("imageUrls") or ([hit["imageUrl"]] if hit.get("imageUrl") else []),
        "imageUrl": hit.get("imageUrl", ""),
        "sellerId": hit.get("sellerId", ""),
        "sellerName": hit.get("sellerName", ""),
        "communityIds": hit.get("communityIds", []),
        "primaryCategoryId": hit.get("primaryCategoryId", "general"),
        "categoryIds": hit.get("categoryIds", []),
        "status": hit.get("status", "active"),
        "createdAt": hit.get("createdAt"),
    }

    if lat is not None and lng is not None:
        response["location"] = {
            "lat": float(lat),
            "lng": float(lng),
            "geohash": hit.get("geohash"),
            "city": hit.get("city"),
            "region": hit.get("region"),
        }

    return response


def _get_blocked_seller_ids(viewer_uid: str | None) -> set[str]:
    if not viewer_uid:
        return set()

    from services.block_pipeline import list_blocked_users

    return {entry["blockedUserId"] for entry in list_blocked_users(viewer_uid)}


def _resolve_sort(
    sort: str,
    *,
    lat: float | None,
    lng: float | None,
) -> str:
    normalized = (sort or SORT_NEWEST).strip().lower()
    if normalized not in VALID_SORTS:
        normalized = SORT_NEWEST

    if normalized == SORT_DISTANCE and lat is not None and lng is not None:
        return f"_geo_distance(location:({lat}, {lng})):asc"
    if normalized == SORT_PRICE_ASC:
        return "price:asc"
    if normalized == SORT_PRICE_DESC:
        return "price:desc"
    return "createdAt:desc"


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
            return _browse_search_typesense(
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
        except Exception as exc:
            logger.warning(
                "Typesense browse search failed; falling back to Firestore",
                exc_info=exc,
            )

    return _browse_search_firestore(
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


def _browse_search_typesense(
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

    return {
        "listings": hits,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "hasMore": page * page_size < total,
        "engine": "typesense",
        "projectId": FIREBASE_PROJECT_ID,
    }


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
) -> tuple[list[dict[str, Any]], bool]:
    """Walk the feed with Firestore cursors until we have target_end filtered rows or exhaust the feed."""
    from google.cloud.firestore_v1 import Query

    collected: list[dict[str, Any]] = []
    last_snapshot = None
    feed_exhausted = False
    batch_size = max(page_size * 2, 50)
    max_batches = 500
    batches = 0

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

    return collected, not feed_exhausted


def _browse_search_firestore(
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
        collected, feed_has_more = _collect_firestore_feed_page(
            base_query=base_query,
            target_end=target_end if not search_active else max(target_end, 10_000),
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
        # Non-newest sorts require in-memory ordering; scan a window large enough for this page.
        fetch_limit = min(max(page * page_size + page_size, page_size * 3), 1000)
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

    return {
        "listings": page_docs,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "hasMore": has_more,
        "engine": "firestore",
        "projectId": FIREBASE_PROJECT_ID,
    }
