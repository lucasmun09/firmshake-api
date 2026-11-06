import secrets

from google.cloud import firestore

from google.cloud.firestore_v1 import FieldFilter

from services.controlpanel_random_listings import (
    clamp_bulk_count,
    random_listing_description,
    random_listing_title,
    random_point_within_radius_miles,
    random_price,
)
from services.controlpanel_test_accounts import create_test_account
from services.community_pipeline import list_categories
from services.firebase_app import get_db
from services.geohash import encode_geohash
from services.listing_search import TypesenseClient


ALL_COMMUNITY_ID = "all"
DEFAULT_CATEGORY_ID = "general"
PICSUM_BASE_URL = "https://picsum.photos/seed"


class ListingError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def list_communities(limit: int = 100) -> list[dict]:
    db = get_db()
    communities: list[dict] = []
    for snapshot in db.collection("communities").limit(min(max(limit, 1), 200)).stream():
        data = snapshot.to_dict() or {}
        communities.append(
            {
                "id": snapshot.id,
                "name": data.get("name", snapshot.id),
                "type": data.get("type", "user"),
                "description": data.get("description", ""),
            }
        )
    communities.sort(key=lambda entry: entry.get("name", "").lower())
    return communities


def _random_listing_image(seed: str | None = None) -> str:
    resolved_seed = seed or secrets.token_hex(8)
    return f"{PICSUM_BASE_URL}/{resolved_seed}/800/600"


def create_test_listing(
    *,
    title: str,
    description: str,
    price: float,
    community_ids: list[str],
    seller_email: str | None = None,
    seller: dict | None = None,
    category_id: str = DEFAULT_CATEGORY_ID,
    lat: float | None = None,
    lng: float | None = None,
    city: str | None = None,
    region: str | None = None,
    location_label: str | None = None,
    use_random_image: bool = True,
    image_seed: str | None = None,
    image_url: str | None = None,
) -> dict:
    if not title.strip():
        raise ListingError("Title is required", 400)
    if price < 0:
        raise ListingError("Price must be zero or greater", 400)

    normalized_communities = [cid.strip() for cid in community_ids if cid.strip()]
    if not normalized_communities:
        normalized_communities = [ALL_COMMUNITY_ID]

    seller = seller or _resolve_seller(seller_email)
    listing_ref = get_db().collection("listings").document()
    title_lower = title.strip().lower()

    if image_url and image_url.strip():
        image_urls = [image_url.strip()]
    elif use_random_image:
        image_urls = [_random_listing_image(image_seed)]
    else:
        raise ListingError("Provide an image URL or enable random image", 400)

    payload: dict = {
        "title": title.strip(),
        "titleLower": title_lower,
        "description": description.strip(),
        "price": float(price),
        "imageUrls": image_urls,
        "imageUrl": image_urls[0],
        "sellerId": seller["uid"],
        "sellerName": seller["displayName"],
        "communityIds": normalized_communities,
        "primaryCategoryId": category_id or DEFAULT_CATEGORY_ID,
        "categoryIds": [category_id or DEFAULT_CATEGORY_ID],
        "status": "active",
        "createdAt": firestore.SERVER_TIMESTAMP,
    }

    if lat is not None and lng is not None:
        payload["location"] = firestore.GeoPoint(lat, lng)
        payload["lat"] = lat
        payload["lng"] = lng
        payload["geohash"] = encode_geohash(lat, lng)
        payload["city"] = (city or "").strip()
        payload["region"] = (region or "").strip()
        payload["locationLabel"] = (location_label or "").strip() or "Selected location"

    listing_ref.set(payload)
    listing_id = listing_ref.id

    created = {
        "id": listing_id,
        **payload,
        "createdAt": None,
    }
    _sync_feeds(listing_id, created, normalized_communities)
    _sync_search_index(listing_id, created)

    return {
        "id": listing_id,
        "title": title.strip(),
        "price": float(price),
        "communityIds": normalized_communities,
        "sellerId": seller["uid"],
        "sellerEmail": seller["email"],
        "imageUrl": image_urls[0],
    }


def create_bulk_test_listings(
    *,
    count: int,
    community_ids: list[str],
    seller_email: str | None = None,
    category_id: str = DEFAULT_CATEGORY_ID,
    randomize_categories: bool = False,
    center_lat: float | None = None,
    center_lng: float | None = None,
    radius_miles: float = 0,
    scatter_location: bool = True,
    city: str | None = None,
    region: str | None = None,
    location_label: str | None = None,
    min_price: float = 5,
    max_price: float = 250,
    use_random_image: bool = True,
) -> dict:
    resolved_count = clamp_bulk_count(count)
    if center_lat is None or center_lng is None:
        raise ListingError("centerLat and centerLng are required for bulk generation", 400)

    category_pool = [entry["id"] for entry in list_categories() if entry.get("id")]
    if not category_pool:
        category_pool = [DEFAULT_CATEGORY_ID]

    fixed_category = (category_id or DEFAULT_CATEGORY_ID).strip() or DEFAULT_CATEGORY_ID
    if not randomize_categories and fixed_category not in category_pool:
        category_pool.append(fixed_category)

    seller = _resolve_seller(seller_email)
    listing_ids: list[str] = []
    errors: list[str] = []

    for index in range(1, resolved_count + 1):
        try:
            chosen_category = (
                secrets.choice(category_pool) if randomize_categories else fixed_category
            )
            lat, lng = center_lat, center_lng
            if scatter_location and radius_miles > 0:
                lat, lng = random_point_within_radius_miles(center_lat, center_lng, radius_miles)

            listing = create_test_listing(
                title=random_listing_title(),
                description=random_listing_description(index),
                price=random_price(min_price, max_price),
                community_ids=community_ids,
                seller=seller,
                category_id=chosen_category,
                lat=lat,
                lng=lng,
                city=city,
                region=region,
                location_label=location_label,
                use_random_image=use_random_image,
            )
            listing_ids.append(listing["id"])
        except ListingError as exc:
            errors.append(str(exc))
        except Exception as exc:
            errors.append(f"Listing {index}: {exc}")

    return {
        "requested": resolved_count,
        "created": len(listing_ids),
        "failed": len(errors),
        "listingIds": listing_ids,
        "sellerEmail": seller["email"],
        "errors": errors[:20],
    }


def _resolve_seller(seller_email: str | None) -> dict:
    if seller_email:
        db = get_db()
        matches = (
            db.collection("users")
            .where(filter=FieldFilter("email", "==", seller_email.strip().lower()))
            .limit(1)
            .stream()
        )
        for snapshot in matches:
            data = snapshot.to_dict() or {}
            return {
                "uid": snapshot.id,
                "email": data.get("email", seller_email),
                "displayName": data.get("displayName", "Test Seller"),
            }
        raise ListingError(f"No seller found for {seller_email}", 404)

    created = create_test_account(first_name="Listing", last_name="Seller")
    return {
        "uid": created["uid"],
        "email": created["email"],
        "displayName": created["displayName"],
    }


def _feed_targets(community_ids: list[str]) -> list[str]:
    targets = {ALL_COMMUNITY_ID, *community_ids}
    return sorted(targets)


def _sync_feeds(listing_id: str, listing: dict, community_ids: list[str]) -> None:
    db = get_db()
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
            {
                "listingId": listing_id,
                "feedCommunityId": community_id,
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
                "status": listing["status"],
                "createdAt": firestore.SERVER_TIMESTAMP,
                **(
                    {
                        "location": listing["location"],
                        "lat": listing["lat"],
                        "lng": listing["lng"],
                        "geohash": listing["geohash"],
                        "city": listing.get("city", ""),
                        "region": listing.get("region", ""),
                        "locationLabel": listing.get("locationLabel", ""),
                    }
                    if "lat" in listing
                    else {}
                ),
            },
        )
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
        "status": listing["status"],
        "imageUrl": listing["imageUrl"],
    }
    if "lat" in listing:
        document["lat"] = listing["lat"]
        document["lng"] = listing["lng"]
        document["geohash"] = listing["geohash"]

    try:
        client.upsert(document)
    except Exception:
        pass


def _serialize_firestore_value(value):
    if value is None:
        return None
    if hasattr(value, "latitude") and hasattr(value, "longitude"):
        return {
            "_type": "geopoint",
            "latitude": value.latitude,
            "longitude": value.longitude,
        }
    if hasattr(value, "timestamp"):
        from datetime import datetime, timezone

        return datetime.fromtimestamp(value.timestamp(), tz=timezone.utc).isoformat()
    if isinstance(value, (int, float, str, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _serialize_firestore_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_firestore_value(item) for item in value]
    return str(value)


def _serialize_listing_doc(listing_id: str, data: dict) -> dict:
    serialized = _serialize_firestore_value(data)
    location = data.get("location")
    lat = data.get("lat")
    lng = data.get("lng")
    if location is not None and hasattr(location, "latitude"):
        lat = location.latitude
        lng = location.longitude

    return {
        "id": listing_id,
        **serialized,
        "location": {
            "label": data.get("locationLabel", ""),
            "city": data.get("city", ""),
            "region": data.get("region", ""),
            "geohash": data.get("geohash", ""),
            "lat": lat,
            "lng": lng,
        }
        if lat is not None and lng is not None
        else None,
    }


def _feed_entries_for_listing(listing_id: str, community_ids: list[str]) -> list[dict]:
    db = get_db()
    feeds: list[dict] = []
    for community_id in _feed_targets(community_ids):
        feed_ref = (
            db.collection("communityFeeds")
            .document(community_id)
            .collection("listings")
            .document(listing_id)
        )
        snapshot = feed_ref.get()
        if not snapshot.exists:
            feeds.append({"communityId": community_id, "exists": False, "data": None})
            continue

        feeds.append(
            {
                "communityId": community_id,
                "exists": True,
                "data": _serialize_firestore_value(snapshot.to_dict() or {}),
            }
        )
    return feeds


def get_listing_metadata(listing_id: str) -> dict:
    listing_id = listing_id.strip()
    if not listing_id:
        raise ListingError("Listing id is required", 400)

    db = get_db()
    snapshot = db.collection("listings").document(listing_id).get()
    if not snapshot.exists:
        raise ListingError("Listing not found", 404)

    data = snapshot.to_dict() or {}
    listing = _serialize_listing_doc(listing_id, data)
    community_ids = data.get("communityIds") or [ALL_COMMUNITY_ID]
    seller_id = str(data.get("sellerId", ""))

    seller = None
    if seller_id:
        seller_snapshot = db.collection("users").document(seller_id).get()
        if seller_snapshot.exists:
            seller_data = seller_snapshot.to_dict() or {}
            seller = {
                "uid": seller_id,
                "email": seller_data.get("email", ""),
                "displayName": seller_data.get("displayName", ""),
                "isTestAccount": bool(seller_data.get("isTestAccount")),
            }

    return {
        "id": listing_id,
        "listing": listing,
        "seller": seller,
        "feeds": _feed_entries_for_listing(listing_id, community_ids),
        "firestoreRaw": _serialize_firestore_value(data),
    }
