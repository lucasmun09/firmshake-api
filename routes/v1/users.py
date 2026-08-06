from flask import Blueprint, g, jsonify, request

from services.auth import AuthError, verify_firebase_token
from services.authorization import AuthorizationError
from services.rate_limit import RateLimitExceeded, assert_email_lookup_allowed
from services.user_pipeline import (
    UserPipelineError,
    find_user_by_email,
    get_current_user,
    get_public_user,
    update_current_user,
)

users_bp = Blueprint("v1_users", __name__)


def _auth_error_response(exc: AuthError):
    return jsonify({"error": str(exc)}), exc.status_code


def _authorization_error_response(exc: AuthorizationError):
    return jsonify({"error": str(exc)}), exc.status_code


def _user_error_response(exc: UserPipelineError):
    return jsonify({"error": str(exc)}), exc.status_code


def _rate_limit_response(exc: RateLimitExceeded):
    return jsonify({"error": str(exc)}), exc.status_code


@users_bp.get("/me")
def get_me():
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        profile = get_current_user(actor_uid)
        return jsonify(profile), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except UserPipelineError as exc:
        return _user_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to load profile"}), 500


@users_bp.patch("/me")
def patch_me():
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        payload = request.get_json(silent=True) or {}
        profile = update_current_user(actor_uid, payload)
        return jsonify(profile), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except AuthorizationError as exc:
        return _authorization_error_response(exc)
    except UserPipelineError as exc:
        return _user_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to update profile"}), 500


@users_bp.get("/by-email")
def get_by_email():
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        assert_email_lookup_allowed(actor_uid)
        email = request.args.get("email", "")
        profile = find_user_by_email(actor_uid, email)
        return jsonify(profile), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except AuthorizationError as exc:
        return _authorization_error_response(exc)
    except RateLimitExceeded as exc:
        return _rate_limit_response(exc)
    except UserPipelineError as exc:
        return _user_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to look up user"}), 500


@users_bp.get("/<uid>/public")
def get_public(uid: str):
    try:
        verify_firebase_token(request.headers.get("Authorization"))
        profile = get_public_user(uid)
        return jsonify(profile), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except UserPipelineError as exc:
        return _user_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to load public profile"}), 500
