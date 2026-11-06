"""Shared browse-search helpers (Typesense client, serialize, filters).

Parallel-agent module — keep orchestration in browse_search.py.
"""

from __future__ import annotations

import os
import urllib.parse
import urllib.request
from typing import Any

from config import FIREBASE_PROJECT_ID

DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 100
FIRESTORE_FALLBACK_MAX_SCAN = int(os.getenv("BROWSE_FIRESTORE_MAX_SCAN", "1000"))

SORT_NEWEST = "newest"
SORT_PRICE_ASC = "price_asc"
SORT_PRICE_DESC = "price_desc"
SORT_DISTANCE = "distance"

VALID_SORTS = {SORT_NEWEST, SORT_PRICE_ASC, SORT_PRICE_DESC, SORT_DISTANCE}


def _firestore_fetch_limit(page: int, page_size: int) -> int:
    """Max Firestore docs to read per fallback request (scan window, not a session cap)."""
    return min(max(page * page_size + page_size, page_size * 3), FIRESTORE_FALLBACK_MAX_SCAN)


def _finalize_browse_page(
    *,
    listings: list[dict[str, Any]],
    total: int,
    page: int,
    page_size: int,
    has_more: bool,
    engine: str,
) -> dict[str, Any]:
    return {
        "listings": listings,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "hasMore": has_more,
        "engine": engine,
        "projectId": FIREBASE_PROJECT_ID,
    }


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
