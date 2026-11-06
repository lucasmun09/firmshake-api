from flask import Blueprint, g, jsonify, request

from services.auth import AuthError, verify_firebase_token
from services.authorization import AuthorizationError
from services.listing_pipeline import (
    DEFAULT_BROWSE_PAGE_SIZE,
    ListingPipelineError,
    browse_listings,
    create_listing,
    mark_listing_sold,
    remove_listing,
    update_listing,
)
from services.message_pipeline import MessagePipelineError, send_listing_message

listings_bp = Blueprint("v1_listings", __name__)


def _auth_error_response(exc: AuthError):
    return jsonify({"error": str(exc)}), exc.status_code


def _authorization_error_response(exc: AuthorizationError):
    return jsonify({"error": str(exc)}), exc.status_code


def _bff_error_response(exc: ListingPipelineError):
    return jsonify({"error": str(exc)}), exc.status_code


@listings_bp.get("")
def get_listings():
    """Public browse feed — active listings for a community with optional filters."""
    try:
        community_id = request.args.get("communityId", "all")
        category_id = request.args.get("categoryId")
        min_price = request.args.get("minPrice", type=float)
        max_price = request.args.get("maxPrice", type=float)
        cursor = request.args.get("cursor")
        limit_raw = request.args.get("limit", type=int)
        limit = limit_raw if limit_raw is not None else DEFAULT_BROWSE_PAGE_SIZE

        result = browse_listings(
            community_id=community_id,
            category_id=category_id,
            min_price=min_price,
            max_price=max_price,
            cursor=cursor,
            limit=limit,
        )
        return jsonify(result), 200
    except ListingPipelineError as exc:
        return _bff_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to load listings"}), 500


@listings_bp.post("")
def post_listing():
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        payload = request.get_json(silent=True) or {}
        listing = create_listing(actor_uid, payload)
        return jsonify(listing), 201
    except AuthError as exc:
        return _auth_error_response(exc)
    except AuthorizationError as exc:
        return _authorization_error_response(exc)
    except ListingPipelineError as exc:
        return _bff_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to create listing"}), 500


@listings_bp.patch("/<listing_id>")
def patch_listing(listing_id: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        payload = request.get_json(silent=True) or {}
        listing = update_listing(actor_uid, listing_id, payload)
        return jsonify(listing), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except AuthorizationError as exc:
        return _authorization_error_response(exc)
    except ListingPipelineError as exc:
        return _bff_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to update listing"}), 500


@listings_bp.post("/<listing_id>/messages")
def post_listing_message(listing_id: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        payload = request.get_json(silent=True) or {}
        message = send_listing_message(actor_uid, listing_id, payload)
        return jsonify({"message": message}), 201
    except AuthError as exc:
        return _auth_error_response(exc)
    except MessagePipelineError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except Exception:
        return jsonify({"error": "Failed to send message"}), 500


@listings_bp.post("/<listing_id>/remove")
def post_remove_listing(listing_id: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        listing = remove_listing(actor_uid, listing_id)
        return jsonify(listing), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except AuthorizationError as exc:
        return _authorization_error_response(exc)
    except ListingPipelineError as exc:
        return _bff_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to remove listing"}), 500


@listings_bp.post("/<listing_id>/sold")
def post_mark_listing_sold(listing_id: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        listing = mark_listing_sold(actor_uid, listing_id)
        return jsonify(listing), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except AuthorizationError as exc:
        return _authorization_error_response(exc)
    except ListingPipelineError as exc:
        return _bff_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to mark listing as sold"}), 500
