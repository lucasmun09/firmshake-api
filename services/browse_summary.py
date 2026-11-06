"""Strip full browse search hits to local-first ListingSummary shape.

Used by POST /api/v1/browse/summary so clients cache/transfer primary image +
metadata only — detail fields (description, imageUrls[], sellerName) stay on
the listing detail path.
"""

from __future__ import annotations

from typing import Any

from services.browse_search import browse_search

# Fields kept on each listing in a summary response (mirrors client ListingSummary).
SUMMARY_LISTING_KEYS = (
    "id",
    "title",
    "price",
    "imageUrl",
    "status",
    "sellerId",
    "communityIds",
    "primaryCategoryId",
    "location",
    "createdAt",
)


def to_listing_summary(listing: dict[str, Any]) -> dict[str, Any]:
    """Project a full browse hit onto summary fields only."""
    image_url = str(listing.get("imageUrl") or "")
    if not image_url:
        image_urls = listing.get("imageUrls") or []
        if isinstance(image_urls, list) and image_urls:
            image_url = str(image_urls[0] or "")

    summary: dict[str, Any] = {
        "id": str(listing.get("id") or ""),
        "title": str(listing.get("title") or ""),
        "price": listing.get("price", 0),
        "imageUrl": image_url,
        "status": listing.get("status") or "active",
        "sellerId": str(listing.get("sellerId") or ""),
        "communityIds": list(listing.get("communityIds") or []),
        "primaryCategoryId": str(listing.get("primaryCategoryId") or "general"),
    }

    if listing.get("createdAt") is not None:
        summary["createdAt"] = listing["createdAt"]

    location = listing.get("location")
    if isinstance(location, dict) and location.get("lat") is not None and location.get("lng") is not None:
        summary["location"] = {
            "lat": float(location["lat"]),
            "lng": float(location["lng"]),
        }
        if location.get("geohash"):
            summary["location"]["geohash"] = location["geohash"]
        if location.get("city"):
            summary["location"]["city"] = location["city"]
        if location.get("region"):
            summary["location"]["region"] = location["region"]
    elif isinstance(location, list) and len(location) == 2:
        summary["location"] = {"lat": float(location[0]), "lng": float(location[1])}

    return summary


def summarize_browse_result(result: dict[str, Any]) -> dict[str, Any]:
    """Strip heavy fields from a full browse_search result."""
    listings = [to_listing_summary(item) for item in (result.get("listings") or [])]
    pin_groups = result.get("pinGroups") or []
    # pinGroups from aggregate_browse_map_pins already use listingIds only.
    return {
        "listings": listings,
        "total": result.get("total", len(listings)),
        "page": result.get("page", 1),
        "pageSize": result.get("pageSize", len(listings)),
        "hasMore": bool(result.get("hasMore")),
        "engine": result.get("engine"),
        "projectId": result.get("projectId"),
        "pinGroups": pin_groups,
        "shape": "summary",
    }


def browse_summary_search(**kwargs: Any) -> dict[str, Any]:
    """Run browse_search then project listings to summary shape."""
    return summarize_browse_result(browse_search(**kwargs))
