from flask import Blueprint, jsonify, request

from services.auth import AuthError, verify_firebase_token
from services.authorization import (
    AuthorizationError,
    can_sync_listing_search,
    get_user_profile,
)
from services.firebase_app import get_db
from services.listing_search import TypesenseClient

listings_bp = Blueprint("listings", __name__, url_prefix="/api/listings")


@listings_bp.get("/search")
def search():
    from services.listing_search import search_listings

    args = request.args
    page = max(int(args.get("page", 1)), 1)
    page_size = min(max(int(args.get("pageSize", 24)), 1), 100)

    def parse_float(name: str):
        value = args.get(name)
        return float(value) if value not in (None, "") else None

    result = search_listings(
        q=args.get("q", "").strip(),
        community_id=args.get("communityId", "all").strip() or "all",
        category_id=args.get("categoryId", "").strip(),
        min_price=parse_float("minPrice"),
        max_price=parse_float("maxPrice"),
        lat=parse_float("lat"),
        lng=parse_float("lng"),
        radius_km=parse_float("radiusKm"),
        page=page,
        page_size=page_size,
    )
    return jsonify(result)


@listings_bp.post("/sync")
def sync():
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        payload = request.get_json(silent=True) or {}
        listing_id = str(payload.get("id", "")).strip()
        if not listing_id:
            return jsonify({"error": "Listing id is required"}), 400

        db = get_db()
        listing_snapshot = db.collection("listings").document(listing_id).get()
        if not listing_snapshot.exists:
            return jsonify({"error": "Listing not found"}), 404

        listing = listing_snapshot.to_dict() or {}
        profile = get_user_profile(db, actor_uid)
        if not can_sync_listing_search(profile, actor_uid, listing):
            raise AuthorizationError("You do not have permission to sync this listing")

        client = TypesenseClient()
        if client.enabled:
            try:
                client.upsert(payload)
            except Exception as exc:  # noqa: BLE001
                return jsonify({"error": str(exc)}), 502

        return jsonify({"ok": True, "typesense": client.enabled})
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
