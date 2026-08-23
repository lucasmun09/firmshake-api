"""Seller-aware browse map pin aggregation (mirrors client browseMapPinAggregation.ts)."""

from __future__ import annotations

from typing import Any, Literal

from services.geohash import haversine_distance_km

BROWSE_MAP_AGGREGATE_RADIUS_MILES = 0.02
BROWSE_MAP_LOCATION_PRECISION = 4
MILES_TO_KM = 1.60934
AGGREGATE_RADIUS_KM = BROWSE_MAP_AGGREGATE_RADIUS_MILES * MILES_TO_KM

BrowseMapPinKind = Literal["single", "aggregated"]


def location_bucket_key(lat: float, lng: float, precision: int = BROWSE_MAP_LOCATION_PRECISION) -> str:
    return f"{lat:.{precision}f}:{lng:.{precision}f}"


def browse_map_pin_group_key(
    seller_id: str,
    lat: float,
    lng: float,
    precision: int = BROWSE_MAP_LOCATION_PRECISION,
) -> str:
    return f"{seller_id}:{location_bucket_key(lat, lng, precision)}"


def _listing_sort_key(listing: dict[str, Any]) -> tuple[str, str]:
    return (str(listing.get("title") or "").lower(), str(listing.get("id") or ""))


def _centroid_position(listings: list[dict[str, Any]]) -> dict[str, float]:
    lat_sum = 0.0
    lng_sum = 0.0
    for listing in listings:
        location = listing.get("location") or {}
        lat_sum += float(location["lat"])
        lng_sum += float(location["lng"])
    count = len(listings)
    return {"lat": lat_sum / count, "lng": lng_sum / count}


def _listings_within_radius(
    anchor: dict[str, Any],
    candidates: list[dict[str, Any]],
    radius_km: float,
) -> list[dict[str, Any]]:
    anchor_location = anchor["location"]
    filtered: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_location = candidate["location"]
        distance_km = haversine_distance_km(
            anchor_location["lat"],
            anchor_location["lng"],
            candidate_location["lat"],
            candidate_location["lng"],
        )
        if distance_km <= radius_km:
            filtered.append(candidate)
    return filtered


def _cluster_seller_listings(
    listings: list[dict[str, Any]],
    radius_km: float = AGGREGATE_RADIUS_KM,
) -> list[list[dict[str, Any]]]:
    sorted_listings = sorted(listings, key=_listing_sort_key)
    remaining = list(sorted_listings)
    clusters: list[list[dict[str, Any]]] = []

    while remaining:
        seed = remaining.pop(0)
        cluster = _listings_within_radius(seed, [seed, *remaining], radius_km)
        cluster_ids = {listing["id"] for listing in cluster}
        remaining = [listing for listing in remaining if listing["id"] not in cluster_ids]
        clusters.append(sorted(cluster, key=_listing_sort_key))

    return clusters


def _normalize_listing_for_pins(listing: dict[str, Any]) -> dict[str, Any] | None:
    location = listing.get("location")
    seller_id = str(listing.get("sellerId") or "").strip()
    listing_id = str(listing.get("id") or "").strip()

    lat: float | None = None
    lng: float | None = None

    if isinstance(location, dict):
        if location.get("lat") is not None and location.get("lng") is not None:
            lat = float(location["lat"])
            lng = float(location["lng"])
    elif isinstance(location, list) and len(location) == 2:
        lat = float(location[0])
        lng = float(location[1])

    if lat is None or lng is None or not seller_id or not listing_id:
        return None

    return {
        "id": listing_id,
        "title": str(listing.get("title") or ""),
        "sellerId": seller_id,
        "location": {"lat": lat, "lng": lng},
    }


def aggregate_browse_map_pins(listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group listings into map pins (same seller + nearby coords → one pin)."""
    by_seller: dict[str, list[dict[str, Any]]] = {}

    for listing in listings:
        normalized = _normalize_listing_for_pins(listing)
        if normalized is None:
            continue
        by_seller.setdefault(normalized["sellerId"], []).append(normalized)

    pin_groups: list[dict[str, Any]] = []

    for seller_id, seller_listings in by_seller.items():
        for cluster in _cluster_seller_listings(seller_listings):
            position = _centroid_position(cluster)
            key = browse_map_pin_group_key(seller_id, position["lat"], position["lng"])
            pin_groups.append(
                {
                    "key": key,
                    "kind": "aggregated" if len(cluster) > 1 else "single",
                    "sellerId": seller_id,
                    "position": position,
                    "listingIds": [listing["id"] for listing in cluster],
                }
            )

    pin_groups.sort(key=lambda group: group["key"])
    return pin_groups
