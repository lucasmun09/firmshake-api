from flask import Blueprint, jsonify, make_response, request

from services.auth import AuthError, verify_firebase_token_optional
from services.community_pipeline import list_categories

catalog_bp = Blueprint("v1_catalog", __name__)

CATEGORIES_CACHE_SECONDS = 300


def _auth_error_response(exc: AuthError):
    return jsonify({"error": str(exc)}), exc.status_code


@catalog_bp.get("/categories")
def get_categories():
    try:
        verify_firebase_token_optional(request.headers.get("Authorization"))
        active_only = request.args.get("active", "").strip().lower() in {"1", "true", "yes"}
        categories = list_categories(active_only=active_only)
        response = make_response(jsonify({"categories": categories}), 200)
        response.headers["Cache-Control"] = f"public, max-age={CATEGORIES_CACHE_SECONDS}"
        return response
    except AuthError as exc:
        return _auth_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to load categories"}), 500
