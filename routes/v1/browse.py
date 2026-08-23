from flask import Blueprint, g, jsonify, request

from services.auth import AuthError, verify_firebase_token_optional
from services.browse_search import browse_search
from services.browse_search_cache import (
    build_browse_search_cache_key,
    get_cached_browse_search,
    set_cached_browse_search,
)

browse_bp = Blueprint("v1_browse", __name__)


def _auth_error_response(exc: AuthError):
    return jsonify({"error": str(exc)}), exc.status_code


def _parse_float(value) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _parse_bool(value) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


def _parse_search_payload(payload: dict) -> dict:
    category_ids = payload.get("categoryIds")
    if category_ids is not None and not isinstance(category_ids, list):
        category_ids = [str(category_ids)]

    page = max(int(payload.get("page") or 1), 1)
    page_size_raw = payload.get("pageSize")
    page_size = min(max(int(page_size_raw or 24), 1), 100)

    return {
        "q": str(payload.get("q") or "").strip(),
        "community_id": str(payload.get("communityId") or "all").strip() or "all",
        "category_id": str(payload.get("categoryId") or "").strip(),
        "category_ids": [str(value).strip() for value in (category_ids or []) if str(value).strip()],
        "min_price": _parse_float(payload.get("priceMin", payload.get("minPrice"))),
        "max_price": _parse_float(payload.get("priceMax", payload.get("maxPrice"))),
        "has_location": _parse_bool(payload.get("hasLocation")),
        "lat": _parse_float(payload.get("lat")),
        "lng": _parse_float(payload.get("lng")),
        "radius_miles": _parse_float(payload.get("radiusMiles")),
        "radius_km": _parse_float(payload.get("radiusKm")),
        "sort": str(payload.get("sort") or "newest").strip().lower(),
        "page": page,
        "page_size": page_size,
    }


@browse_bp.post("/search")
def post_browse_search():
    """Public browse search — optional auth for block-list filtering.

    Response always includes seller-aggregated `pinGroups` for map rendering.
    """
    try:
        viewer_uid = verify_firebase_token_optional(request.headers.get("Authorization"))
        g.authenticated_uid = viewer_uid
        payload = request.get_json(silent=True) or {}
        params = _parse_search_payload(payload)
        cache_key = build_browse_search_cache_key(params, viewer_uid)
        cached = get_cached_browse_search(cache_key)
        if cached is not None:
            response = jsonify(cached)
            response.headers["X-Browse-Cache"] = "HIT"
            return response, 200

        result = browse_search(**params, viewer_uid=viewer_uid)
        set_cached_browse_search(cache_key, result)
        response = jsonify(result)
        response.headers["X-Browse-Cache"] = "MISS"
        return response, 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except ValueError:
        return jsonify({"error": "Invalid search parameters"}), 400
    except Exception:
        return jsonify({"error": "Search is temporarily unavailable"}), 500
