"""Listing create/update/remove with feed and search sync via Admin SDK."""

from google.cloud import firestore

from services.authorization import (
    ALL_COMMUNITY_ID,
    AuthorizationError,
    can_remove_listing,
    can_update_listing,
    get_user_profile,
)
from services.firebase_app import get_db
from services.geohash import encode_geohash
from services.browse_search import TypesenseClient
from services.listing_validation import ValidationError, validate_create_listing_payload, validate_update_listing_payload


class ListingPipelineError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _feed_targets(community_ids: list[str]) -> list[str]:
    return sorted({ALL_COMMUNITY_ID, *community_ids})


def _location_fields(location: dict | None) -> dict:
    if not location:
        return {}

    geohash = location.get("geohash") or encode_geohash(location["lat"], location["lng"])
    return {
        "location": firestore.GeoPoint(location["lat"], location["lng"]),
        "lat": location["lat"],
        "lng": location["lng"],
        "geohash": geohash,
        "city": location.get("city", ""),
        "region": location.get("region", ""),
        "locationLabel": location.get("label", ""),
    }


def _feed_payload(listing_id: str, listing: dict, feed_community_id: str) -> dict:
    payload = {
        "listingId": listing_id,
        "feedCommunityId": feed_community_id,
        "title": listing["title"],
        "titleLower": listing["titleLower"],
        "description": listing["description"],
        "price": listing["price"],
        "imageUrls": listing["imageUrls"],
        "imageUrl": listing["imageUrl"],
        "sellerId": listing["sellerId"],
        "sellerName": listing["sellerName"],
        "communityIds": listing["communityIds"],
        "primaryCategoryId": listing["primaryCategoryId"],
        "categoryIds": listing["categoryIds"],
        "status": listing.get("status", "active"),
        "createdAt": listing.get("createdAt", firestore.SERVER_TIMESTAMP),
        **_location_fields(listing.get("location")),
    }
    if listing.get("updatedAt") is not None:
        payload["updatedAt"] = listing["updatedAt"]
    return payload


def _sync_feeds(
    db,
    listing_id: str,
    listing: dict,
    *,
    previous_community_ids: list[str] | None = None,
) -> None:
    next_targets = set(_feed_targets(listing.get("communityIds") or []))
    previous_targets = set(_feed_targets(previous_community_ids or []))
    to_remove = previous_targets - next_targets

    batch = db.batch()
    for community_id in next_targets:
        feed_ref = (
            db.collection("communityFeeds")
            .document(community_id)
            .collection("listings")
            .document(listing_id)
        )
        batch.set(feed_ref, _feed_payload(listing_id, listing, community_id), merge=True)

    for community_id in to_remove:
        feed_ref = (
            db.collection("communityFeeds")
            .document(community_id)
            .collection("listings")
            .document(listing_id)
        )
        batch.delete(feed_ref)

    batch.commit()


def _sync_search_index(listing_id: str, listing: dict) -> None:
    client = TypesenseClient()
    if not client.enabled:
        return

    document = {
        "id": listing_id,
        "title": listing["title"],
        "description": listing["description"],
        "price": listing["price"],
        "communityIds": listing["communityIds"],
        "primaryCategoryId": listing["primaryCategoryId"],
        "categoryIds": listing["categoryIds"],
        "sellerId": listing["sellerId"],
        "sellerName": listing.get("sellerName", ""),
        "status": listing.get("status", "active"),
        "imageUrl": listing["imageUrl"],
        "createdAt": listing.get("createdAtMs", 0),
    }

    location = listing.get("location")
    if location:
        lat = location["lat"]
        lng = location["lng"]
        document["lat"] = lat
        document["lng"] = lng
        document["location"] = [lat, lng]
        document["hasLocation"] = True
        document["geohash"] = location.get("geohash") or encode_geohash(lat, lng)
        if location.get("city"):
            document["city"] = location["city"]
        if location.get("region"):
            document["region"] = location["region"]
    else:
        document["hasLocation"] = False

    client.upsert(document)


def _serialize_listing_response(listing_id: str, data: dict) -> dict:
    created_at = data.get("createdAt")
    created_ms = 0
    if created_at is not None and hasattr(created_at, "timestamp"):
        created_ms = int(created_at.timestamp() * 1000)

    location = data.get("location")
    lat = data.get("lat")
    lng = data.get("lng")
    if location is not None and hasattr(location, "latitude"):
        lat = location.latitude
        lng = location.longitude

    response = {
        "id": listing_id,
        "title": data.get("title", ""),
        "titleLower": data.get("titleLower", ""),
        "description": data.get("description", ""),
        "price": data.get("price", 0),
        "imageUrls": data.get("imageUrls", []),
        "imageUrl": data.get("imageUrl", ""),
        "sellerId": data.get("sellerId", ""),
        "sellerName": data.get("sellerName", ""),
        "communityIds": data.get("communityIds", []),
        "primaryCategoryId": data.get("primaryCategoryId", "general"),
        "categoryIds": data.get("categoryIds", []),
        "status": data.get("status", "active"),
        "createdAt": created_ms or None,
        "removedBy": data.get("removedBy"),
    }

    if lat is not None and lng is not None:
        response["location"] = {
            "lat": lat,
            "lng": lng,
            "geohash": data.get("geohash"),
            "city": data.get("city"),
            "region": data.get("region"),
            "label": data.get("locationLabel"),
        }

    return response


def _get_listing_or_error(db, listing_id: str) -> tuple[str, dict]:
    listing_id = listing_id.strip()
    if not listing_id:
        raise ListingPipelineError("Listing id is required", 400)

    snapshot = db.collection("listings").document(listing_id).get()
    if not snapshot.exists:
        raise ListingPipelineError("Listing not found", 404)
    return listing_id, snapshot.to_dict() or {}


def create_listing(actor_uid: str, payload: dict) -> dict:
    try:
        validated = validate_create_listing_payload(payload)
    except ValidationError as exc:
        raise ListingPipelineError(str(exc), exc.status_code) from exc

    db = get_db()
    listing_ref = db.collection("listings").document()
    listing_id = listing_ref.id

    firestore_payload = {
        **validated,
        "sellerId": actor_uid,
        "status": "active",
        "createdAt": firestore.SERVER_TIMESTAMP,
    }
    if validated.get("location"):
        firestore_payload.update(_location_fields(validated["location"]))

    listing_ref.set(firestore_payload)

    listing_for_sync = {
        **firestore_payload,
        "location": validated.get("location"),
        "createdAtMs": 0,
    }

    _sync_feeds(db, listing_id, listing_for_sync)
    try:
        _sync_search_index(listing_id, listing_for_sync)
    except Exception as exc:
        raise ListingPipelineError(f"Search index sync failed: {exc}", 502) from exc

    created_snapshot = listing_ref.get()
    return _serialize_listing_response(listing_id, created_snapshot.to_dict() or {})


def update_listing(actor_uid: str, listing_id: str, payload: dict) -> dict:
    try:
        validated = validate_update_listing_payload(payload)
    except ValidationError as exc:
        raise ListingPipelineError(str(exc), exc.status_code) from exc

    db = get_db()
    listing_id, existing = _get_listing_or_error(db, listing_id)

    if not can_update_listing(actor_uid, existing):
        raise AuthorizationError("You do not have permission to update this listing")

    previous_community_ids = list(existing.get("communityIds") or [])
    update_payload: dict = {
        "title": validated["title"],
        "titleLower": validated["titleLower"],
        "description": validated["description"],
        "price": validated["price"],
        "imageUrls": validated["imageUrls"],
        "imageUrl": validated["imageUrl"],
        "communityIds": validated["communityIds"],
        "primaryCategoryId": validated["primaryCategoryId"],
        "categoryIds": validated["categoryIds"],
        "updatedAt": firestore.SERVER_TIMESTAMP,
    }

    if validated.get("location") is not None:
        update_payload.update(_location_fields(validated["location"]))
        merged_location = validated["location"]
    elif existing.get("lat") is not None and existing.get("lng") is not None:
        merged_location = {
            "lat": existing.get("lat"),
            "lng": existing.get("lng"),
            "geohash": existing.get("geohash"),
            "city": existing.get("city", ""),
            "region": existing.get("region", ""),
            "label": existing.get("locationLabel", ""),
        }
    else:
        merged_location = None

    listing_ref = db.collection("listings").document(listing_id)
    listing_ref.update(update_payload)

    merged = {
        **existing,
        **update_payload,
        "sellerId": existing.get("sellerId"),
        "sellerName": existing.get("sellerName"),
        "status": existing.get("status", "active"),
        "location": merged_location,
    }

    created_at = existing.get("createdAt")
    if created_at is not None and hasattr(created_at, "timestamp"):
        merged["createdAtMs"] = int(created_at.timestamp() * 1000)

    _sync_feeds(db, listing_id, merged, previous_community_ids=previous_community_ids)
    try:
        _sync_search_index(listing_id, merged)
    except Exception as exc:
        raise ListingPipelineError(f"Search index sync failed: {exc}", 502) from exc

    updated_snapshot = listing_ref.get()
    return _serialize_listing_response(listing_id, updated_snapshot.to_dict() or {})


def remove_listing(actor_uid: str, listing_id: str) -> dict:
    db = get_db()
    listing_id, existing = _get_listing_or_error(db, listing_id)

    if existing.get("status") != "active":
        raise ListingPipelineError("This listing is no longer active", 400)

    profile = get_user_profile(db, actor_uid)
    if not can_remove_listing(profile, existing, actor_uid):
        raise AuthorizationError("You do not have permission to remove this listing")

    listing_ref = db.collection("listings").document(listing_id)
    listing_ref.update(
        {
            "status": "removed",
            "removedAt": firestore.SERVER_TIMESTAMP,
            "removedBy": actor_uid,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
    )

    removed = {
        **existing,
        "status": "removed",
        "removedBy": actor_uid,
    }
    created_at = existing.get("createdAt")
    if created_at is not None and hasattr(created_at, "timestamp"):
        removed["createdAtMs"] = int(created_at.timestamp() * 1000)

    community_ids = list(existing.get("communityIds") or [])
    batch = db.batch()
    for community_id in _feed_targets(community_ids):
        feed_ref = (
            db.collection("communityFeeds")
            .document(community_id)
            .collection("listings")
            .document(listing_id)
        )
        batch.set(
            feed_ref,
            {"status": "removed", "updatedAt": firestore.SERVER_TIMESTAMP},
            merge=True,
        )
    batch.commit()

    try:
        _sync_search_index(listing_id, removed)
    except Exception as exc:
        raise ListingPipelineError(f"Search index sync failed: {exc}", 502) from exc

    updated_snapshot = listing_ref.get()
    return _serialize_listing_response(listing_id, updated_snapshot.to_dict() or {})


DEFAULT_BROWSE_PAGE_SIZE = 24
MAX_BROWSE_PAGE_SIZE = 48


def _feed_entry_to_listing(listing_id: str, data: dict) -> dict:
    """Map a communityFeeds listing entry to the browse listing shape."""
    created_at = data.get("createdAt")
    created_ms = None
    if created_at is not None and hasattr(created_at, "timestamp"):
        created_ms = int(created_at.timestamp() * 1000)

    lat = data.get("lat")
    lng = data.get("lng")
    location = data.get("location")
    if location is not None and hasattr(location, "latitude"):
        lat = location.latitude
        lng = location.longitude

    response = {
        "id": listing_id,
        "title": data.get("title", ""),
        "titleLower": data.get("titleLower", ""),
        "description": data.get("description", ""),
        "price": data.get("price", 0),
        "imageUrls": data.get("imageUrls", []),
        "imageUrl": data.get("imageUrl", ""),
        "sellerId": data.get("sellerId", ""),
        "sellerName": data.get("sellerName", ""),
        "communityIds": data.get("communityIds", []),
        "primaryCategoryId": data.get("primaryCategoryId", "general"),
        "categoryIds": data.get("categoryIds", []),
        "status": data.get("status", "active"),
        "createdAt": created_ms,
    }

    if lat is not None and lng is not None:
        response["location"] = {
            "lat": lat,
            "lng": lng,
            "geohash": data.get("geohash"),
            "city": data.get("city"),
            "region": data.get("region"),
            "label": data.get("locationLabel"),
        }

    return response


def _query_browse_feed(
    db,
    community_id: str,
    *,
    category_id: str | None,
    min_price: float | None,
    max_price: float | None,
    page_size: int,
    cursor: str | None,
) -> tuple[list[dict], str | None, bool]:
    query = (
        db.collection("communityFeeds")
        .document(community_id)
        .collection("listings")
        .where("status", "==", "active")
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .limit(page_size + 1)
    )

    if category_id:
        query = query.where("primaryCategoryId", "==", category_id)
    if min_price is not None:
        query = query.where("price", ">=", min_price)
    if max_price is not None:
        query = query.where("price", "<=", max_price)

    if cursor:
        cursor_snapshot = (
            db.collection("communityFeeds")
            .document(community_id)
            .collection("listings")
            .document(cursor)
            .get()
        )
        if not cursor_snapshot.exists:
            raise ListingPipelineError("Invalid cursor", 400)
        query = query.start_after(cursor_snapshot)

    snapshots = list(query.stream())
    has_more = len(snapshots) > page_size
    page_snapshots = snapshots[:page_size]

    listings = [
        _feed_entry_to_listing(snapshot.id, snapshot.to_dict() or {})
        for snapshot in page_snapshots
    ]
    next_cursor = page_snapshots[-1].id if has_more and page_snapshots else None
    return listings, next_cursor, has_more


def _query_browse_listings_fallback(
    db,
    community_id: str,
    *,
    category_id: str | None,
    page_size: int,
    cursor: str | None,
) -> tuple[list[dict], str | None, bool]:
    query = (
        db.collection("listings")
        .where("status", "==", "active")
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .limit(page_size + 1)
    )

    if community_id and community_id != ALL_COMMUNITY_ID:
        query = query.where("communityIds", "array-contains", community_id)
    if category_id:
        query = query.where("primaryCategoryId", "==", category_id)

    if cursor:
        cursor_snapshot = db.collection("listings").document(cursor).get()
        if not cursor_snapshot.exists:
            raise ListingPipelineError("Invalid cursor", 400)
        query = query.start_after(cursor_snapshot)

    snapshots = list(query.stream())
    has_more = len(snapshots) > page_size
    page_snapshots = snapshots[:page_size]

    listings = [
        _serialize_listing_response(snapshot.id, snapshot.to_dict() or {})
        for snapshot in page_snapshots
    ]
    next_cursor = page_snapshots[-1].id if has_more and page_snapshots else None
    return listings, next_cursor, has_more


def browse_listings(
    *,
    community_id: str = ALL_COMMUNITY_ID,
    category_id: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    cursor: str | None = None,
    limit: int = DEFAULT_BROWSE_PAGE_SIZE,
) -> dict:
    community_id = (community_id or ALL_COMMUNITY_ID).strip() or ALL_COMMUNITY_ID
    page_size = min(max(limit, 1), MAX_BROWSE_PAGE_SIZE)
    db = get_db()

    try:
        listings, next_cursor, has_more = _query_browse_feed(
            db,
            community_id,
            category_id=category_id,
            min_price=min_price,
            max_price=max_price,
            page_size=page_size,
            cursor=cursor,
        )
        if listings or cursor:
            return {"listings": listings, "nextCursor": next_cursor, "hasMore": has_more}
    except Exception:
        pass

    listings, next_cursor, has_more = _query_browse_listings_fallback(
        db,
        community_id,
        category_id=category_id,
        page_size=page_size,
        cursor=cursor,
    )
    return {"listings": listings, "nextCursor": next_cursor, "hasMore": has_more}
