"""Request body validation for listing BFF endpoints."""

from services.authorization import ALL_COMMUNITY_ID, DEFAULT_CATEGORY_ID


class ValidationError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


MAX_TITLE_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 4000
MAX_PRICE = 1_000_000
MIN_PRICE = 0


def _require_string(value, field: str, *, max_length: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    trimmed = value.strip()
    if max_length is not None and len(trimmed) > max_length:
        raise ValidationError(f"{field} must be at most {max_length} characters")
    return trimmed


def _parse_image_urls(value) -> list[str]:
    if not isinstance(value, list):
        raise ValidationError("imageUrls must be an array")
    urls = [str(item).strip() for item in value if str(item).strip()]
    if not urls:
        raise ValidationError("At least one image is required")
    return urls


def _parse_community_ids(value) -> list[str]:
    if not isinstance(value, list) or not value:
        return [ALL_COMMUNITY_ID]
    community_ids = [str(item).strip() for item in value if str(item).strip()]
    return community_ids or [ALL_COMMUNITY_ID]


def _parse_category_ids(payload: dict, primary_category_id: str) -> list[str]:
    category_ids = payload.get("categoryIds")
    if isinstance(category_ids, list) and category_ids:
        return [str(item).strip() for item in category_ids if str(item).strip()]
    return [primary_category_id]


def _parse_location(payload: dict) -> dict | None:
    location = payload.get("location")
    if location is None:
        return None
    if not isinstance(location, dict):
        raise ValidationError("location must be an object")

    lat = location.get("lat")
    lng = location.get("lng")
    if lat is None or lng is None:
        raise ValidationError("location.lat and location.lng are required")

    try:
        lat_value = float(lat)
        lng_value = float(lng)
    except (TypeError, ValueError) as exc:
        raise ValidationError("location.lat and location.lng must be numbers") from exc

    if not (-90 <= lat_value <= 90 and -180 <= lng_value <= 180):
        raise ValidationError("location coordinates are out of range")

    return {
        "lat": lat_value,
        "lng": lng_value,
        "geohash": str(location.get("geohash", "")).strip() or None,
        "city": str(location.get("city", "")).strip(),
        "region": str(location.get("region", "")).strip(),
        "label": str(location.get("label", "")).strip(),
    }


def validate_create_listing_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object")

    title = _require_string(payload.get("title"), "title", max_length=MAX_TITLE_LENGTH)
    description = _require_string(
        payload.get("description"),
        "description",
        max_length=MAX_DESCRIPTION_LENGTH,
    )

    try:
        price = float(payload.get("price"))
    except (TypeError, ValueError) as exc:
        raise ValidationError("price must be a number") from exc

    if price < MIN_PRICE or price > MAX_PRICE:
        raise ValidationError(f"price must be between {MIN_PRICE} and {MAX_PRICE}")

    seller_name = _require_string(payload.get("sellerName"), "sellerName", max_length=120)
    image_urls = _parse_image_urls(payload.get("imageUrls"))
    community_ids = _parse_community_ids(payload.get("communityIds"))
    primary_category_id = str(payload.get("primaryCategoryId") or DEFAULT_CATEGORY_ID).strip()
    category_ids = _parse_category_ids(payload, primary_category_id)
    location = _parse_location(payload)

    return {
        "title": title,
        "titleLower": title.lower(),
        "description": description,
        "price": price,
        "imageUrls": image_urls,
        "imageUrl": image_urls[0],
        "sellerName": seller_name,
        "communityIds": community_ids,
        "primaryCategoryId": primary_category_id or DEFAULT_CATEGORY_ID,
        "categoryIds": category_ids,
        "location": location,
    }


def validate_update_listing_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object")

    title = _require_string(payload.get("title"), "title", max_length=MAX_TITLE_LENGTH)
    description = _require_string(
        payload.get("description"),
        "description",
        max_length=MAX_DESCRIPTION_LENGTH,
    )

    try:
        price = float(payload.get("price"))
    except (TypeError, ValueError) as exc:
        raise ValidationError("price must be a number") from exc

    if price < MIN_PRICE or price > MAX_PRICE:
        raise ValidationError(f"price must be between {MIN_PRICE} and {MAX_PRICE}")

    image_urls = _parse_image_urls(payload.get("imageUrls"))
    community_ids = _parse_community_ids(payload.get("communityIds"))
    primary_category_id = str(payload.get("primaryCategoryId") or DEFAULT_CATEGORY_ID).strip()
    category_ids = _parse_category_ids(payload, primary_category_id)
    location = _parse_location(payload) if "location" in payload else None

    return {
        "title": title,
        "titleLower": title.lower(),
        "description": description,
        "price": price,
        "imageUrls": image_urls,
        "imageUrl": image_urls[0],
        "communityIds": community_ids,
        "primaryCategoryId": primary_category_id or DEFAULT_CATEGORY_ID,
        "categoryIds": category_ids,
        "location": location,
    }
