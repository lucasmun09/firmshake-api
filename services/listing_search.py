import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from config import FIREBASE_PROJECT_ID


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
    }


def matches_keyword(listing: dict[str, Any], query_text: str) -> bool:
    normalized = query_text.strip().lower()
    if not normalized:
        return True

    haystack = f"{listing.get('title', '')} {listing.get('description', '')}".lower()
    return all(term in haystack for term in normalized.split())


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
) -> dict[str, Any]:
    client = TypesenseClient()
    if client.enabled:
        filters = ["status:=active"]
        if community_id and community_id != "all":
            filters.append(f"communityIds:={community_id}")
        if category_id:
            filters.append(f"primaryCategoryId:={category_id}")
        if min_price is not None:
            filters.append(f"price:>={min_price}")
        if max_price is not None:
            filters.append(f"price:<={max_price}")

        params = {
            "q": q or "*",
            "query_by": "title,description,city,region",
            "filter_by": " && ".join(filters),
            "page": str(page),
            "per_page": str(page_size),
            "sort_by": "createdAt:desc",
        }

        if lat is not None and lng is not None and radius_km is not None:
            params["filter_by"] += f" && location:({lat}, {lng}, {radius_km * 1000} m)"

        result = client.search(params)
        hits = [hit["document"] for hit in result.get("hits", [])]
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

    from google.cloud.firestore_v1 import FieldFilter

    from services.firebase_app import get_db
    from services.geohash import haversine_distance_km

    db = get_db()
    feed_ref = (
        db.collection("communityFeeds")
        .document(community_id or "all")
        .collection("listings")
    )

    query = feed_ref.where(filter=FieldFilter("status", "==", "active"))
    if category_id:
        query = query.where(filter=FieldFilter("primaryCategoryId", "==", category_id))
    if min_price is not None:
        query = query.where(filter=FieldFilter("price", ">=", min_price))
    if max_price is not None:
        query = query.where(filter=FieldFilter("price", "<=", max_price))

    fetch_limit = page_size * 3
    if lat is not None and lng is not None and radius_km is not None:
        fetch_limit = max(fetch_limit, 200)

    query = query.order_by("createdAt", direction="DESCENDING").limit(fetch_limit)
    docs = [map_feed_doc(doc.id, doc.to_dict() or {}) for doc in query.stream()]

    if q:
        docs = [doc for doc in docs if matches_keyword(doc, q)]

    if lat is not None and lng is not None and radius_km is not None:
        docs = [
            doc
            for doc in docs
            if doc.get("location")
            and haversine_distance_km(lat, lng, doc["location"][0], doc["location"][1])
            <= radius_km
        ]

    start = (page - 1) * page_size
    page_docs = docs[start : start + page_size]
    total = len(docs)

    return {
        "listings": page_docs,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "hasMore": start + page_size < total,
        "engine": "firestore",
        "projectId": FIREBASE_PROJECT_ID,
    }
