from flask import Blueprint, jsonify, request

from services.auth import AuthError, verify_firebase_token_optional
from services.community_pipeline import list_categories

catalog_bp = Blueprint("v1_catalog", __name__)


def _auth_error_response(exc: AuthError):
    return jsonify({"error": str(exc)}), exc.status_code


@catalog_bp.get("/categories")
def get_categories():
    try:
        verify_firebase_token_optional(request.headers.get("Authorization"))
        categories = list_categories()
        return jsonify({"categories": categories}), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to load categories"}), 500
