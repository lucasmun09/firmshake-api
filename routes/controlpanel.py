from flask import Blueprint, jsonify, request

from services.auth import AuthError
from services.controlpanel_auth import ControlpanelAccessError, verify_controlpanel_request
from services.controlpanel_bans import BanError, create_ban, is_banned, list_bans, remove_ban
from services.community_pipeline import list_categories
from services.controlpanel_listings import (
    ListingError,
    create_bulk_test_listings,
    create_test_listing,
    get_listing_metadata,
    list_communities,
)
from services.controlpanel_operators import OperatorError, add_operator, list_operators, remove_operator
from services.controlpanel_test_accounts import (
    TestAccountError,
    create_test_account,
    get_test_account,
    list_test_accounts,
)

controlpanel_bp = Blueprint("controlpanel", __name__, url_prefix="/api/controlpanel")


def _auth_error_response(exc: AuthError):
    return jsonify({"error": str(exc)}), exc.status_code


def _access_error_response(exc: ControlpanelAccessError):
    return jsonify({"error": str(exc)}), exc.status_code


@controlpanel_bp.get("/me")
def me():
    try:
        uid, email = verify_controlpanel_request(request.headers.get("Authorization"))
    except AuthError as exc:
        return _auth_error_response(exc)
    except ControlpanelAccessError as exc:
        return _access_error_response(exc)

    return jsonify({"uid": uid, "email": email, "access": True})


@controlpanel_bp.get("/test-accounts")
def get_test_accounts():
    try:
        verify_controlpanel_request(request.headers.get("Authorization"))
    except AuthError as exc:
        return _auth_error_response(exc)
    except ControlpanelAccessError as exc:
        return _access_error_response(exc)

    limit = int(request.args.get("limit", 50))
    return jsonify({"accounts": list_test_accounts(limit=limit)})


@controlpanel_bp.post("/test-accounts")
def post_test_account():
    try:
        verify_controlpanel_request(request.headers.get("Authorization"))
    except AuthError as exc:
        return _auth_error_response(exc)
    except ControlpanelAccessError as exc:
        return _access_error_response(exc)

    payload = request.get_json(silent=True) or {}
    try:
        account = create_test_account(
            first_name=str(payload.get("firstName", "Test")),
            last_name=str(payload.get("lastName", "User")),
            email=payload.get("email"),
            password=payload.get("password"),
        )
    except TestAccountError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    return jsonify(account), 201


@controlpanel_bp.get("/test-accounts/<uid>")
def get_test_account_detail(uid: str):
    try:
        verify_controlpanel_request(request.headers.get("Authorization"))
    except AuthError as exc:
        return _auth_error_response(exc)
    except ControlpanelAccessError as exc:
        return _access_error_response(exc)

    try:
        account = get_test_account(uid)
    except TestAccountError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    return jsonify(account)


@controlpanel_bp.get("/communities")
def get_communities():
    try:
        verify_controlpanel_request(request.headers.get("Authorization"))
    except AuthError as exc:
        return _auth_error_response(exc)
    except ControlpanelAccessError as exc:
        return _access_error_response(exc)

    return jsonify({"communities": list_communities()})


@controlpanel_bp.get("/categories")
def get_categories():
    try:
        verify_controlpanel_request(request.headers.get("Authorization"))
    except AuthError as exc:
        return _auth_error_response(exc)
    except ControlpanelAccessError as exc:
        return _access_error_response(exc)

    return jsonify({"categories": list_categories()})


@controlpanel_bp.post("/test-listings/bulk")
def post_bulk_test_listings():
    try:
        verify_controlpanel_request(request.headers.get("Authorization"))
    except AuthError as exc:
        return _auth_error_response(exc)
    except ControlpanelAccessError as exc:
        return _access_error_response(exc)

    payload = request.get_json(silent=True) or {}
    community_ids = payload.get("communityIds") or []
    if isinstance(community_ids, str):
        community_ids = [community_ids]

    try:
        result = create_bulk_test_listings(
            count=int(payload.get("count", 1)),
            community_ids=[str(value) for value in community_ids],
            seller_email=payload.get("sellerEmail"),
            category_id=str(payload.get("categoryId", "general")),
            randomize_categories=bool(payload.get("randomizeCategories", False)),
            center_lat=payload.get("centerLat"),
            center_lng=payload.get("centerLng"),
            radius_miles=float(payload.get("radiusMiles", 0)),
            scatter_location=bool(payload.get("scatterLocation", True)),
            city=payload.get("city"),
            region=payload.get("region"),
            location_label=payload.get("locationLabel"),
            min_price=float(payload.get("minPrice", 5)),
            max_price=float(payload.get("maxPrice", 250)),
            use_random_image=bool(payload.get("useRandomImage", True)),
        )
    except ListingError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    return jsonify(result), 201


@controlpanel_bp.post("/test-listings")
def post_test_listing():
    try:
        verify_controlpanel_request(request.headers.get("Authorization"))
    except AuthError as exc:
        return _auth_error_response(exc)
    except ControlpanelAccessError as exc:
        return _access_error_response(exc)

    payload = request.get_json(silent=True) or {}
    community_ids = payload.get("communityIds") or []
    if isinstance(community_ids, str):
        community_ids = [community_ids]

    try:
        listing = create_test_listing(
            title=str(payload.get("title", "")),
            description=str(payload.get("description", "")),
            price=float(payload.get("price", 0)),
            community_ids=[str(value) for value in community_ids],
            seller_email=payload.get("sellerEmail"),
            category_id=str(payload.get("categoryId", "general")),
            lat=payload.get("lat"),
            lng=payload.get("lng"),
            city=payload.get("city"),
            region=payload.get("region"),
            location_label=payload.get("locationLabel"),
            use_random_image=bool(payload.get("useRandomImage", True)),
            image_seed=payload.get("imageSeed"),
            image_url=payload.get("imageUrl"),
        )
    except ListingError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    return jsonify(listing), 201


@controlpanel_bp.get("/listings/<listing_id>")
def get_listing_detail(listing_id: str):
    try:
        verify_controlpanel_request(request.headers.get("Authorization"))
    except AuthError as exc:
        return _auth_error_response(exc)
    except ControlpanelAccessError as exc:
        return _access_error_response(exc)

    try:
        listing = get_listing_metadata(listing_id)
    except ListingError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    return jsonify(listing)


@controlpanel_bp.get("/bans")
def get_bans():
    try:
        verify_controlpanel_request(request.headers.get("Authorization"))
    except AuthError as exc:
        return _auth_error_response(exc)
    except ControlpanelAccessError as exc:
        return _access_error_response(exc)

    return jsonify({"bans": list_bans()})


@controlpanel_bp.post("/bans")
def post_ban():
    try:
        uid, _email = verify_controlpanel_request(request.headers.get("Authorization"))
    except AuthError as exc:
        return _auth_error_response(exc)
    except ControlpanelAccessError as exc:
        return _access_error_response(exc)

    payload = request.get_json(silent=True) or {}
    try:
        ban = create_ban(
            ban_type=str(payload.get("type", "")),
            value=str(payload.get("value", "")),
            reason=str(payload.get("reason", "")),
            banned_by=uid,
        )
    except BanError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    return jsonify(ban), 201


@controlpanel_bp.delete("/bans/<ban_id>")
def delete_ban(ban_id: str):
    try:
        verify_controlpanel_request(request.headers.get("Authorization"))
    except AuthError as exc:
        return _auth_error_response(exc)
    except ControlpanelAccessError as exc:
        return _access_error_response(exc)

    try:
        result = remove_ban(ban_id)
    except BanError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    return jsonify(result)


@controlpanel_bp.get("/operators")
def get_operators():
    try:
        verify_controlpanel_request(request.headers.get("Authorization"))
    except AuthError as exc:
        return _auth_error_response(exc)
    except ControlpanelAccessError as exc:
        return _access_error_response(exc)

    return jsonify({"operators": list_operators()})


@controlpanel_bp.post("/operators")
def post_operator():
    try:
        uid, email = verify_controlpanel_request(request.headers.get("Authorization"))
    except AuthError as exc:
        return _auth_error_response(exc)
    except ControlpanelAccessError as exc:
        return _access_error_response(exc)

    payload = request.get_json(silent=True) or {}
    try:
        operator = add_operator(email=str(payload.get("email", "")), added_by=email or uid)
    except OperatorError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    return jsonify(operator), 201


@controlpanel_bp.delete("/operators/<operator_uid>")
def delete_operator(operator_uid: str):
    try:
        caller_uid, _email = verify_controlpanel_request(request.headers.get("Authorization"))
    except AuthError as exc:
        return _auth_error_response(exc)
    except ControlpanelAccessError as exc:
        return _access_error_response(exc)

    try:
        result = remove_operator(uid=operator_uid, caller_uid=caller_uid)
    except OperatorError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    return jsonify(result)


@controlpanel_bp.post("/check-ban")
def check_ban():
    payload = request.get_json(silent=True) or {}
    email = payload.get("email")
    phone = payload.get("phone")
    ban = is_banned(email=email, phone=phone)
    if not ban:
        return jsonify({"banned": False})
    return jsonify({"banned": True, **ban})
