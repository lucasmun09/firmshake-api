from flask import Blueprint, g, jsonify, request

from services.auth import AuthError, verify_firebase_token, verify_firebase_token_optional
from services.authorization import AuthorizationError
from services.community_pipeline import (
    CommunityPipelineError,
    create_community,
    join_community,
    leave_community,
    list_communities,
)
from services.user_pipeline import (
    UserPipelineError,
    fetch_community_moderators,
    grant_community_moderator,
    revoke_community_moderator,
)

communities_bp = Blueprint("v1_communities", __name__)


def _auth_error_response(exc: AuthError):
    return jsonify({"error": str(exc)}), exc.status_code


def _authorization_error_response(exc: AuthorizationError):
    return jsonify({"error": str(exc)}), exc.status_code


def _community_error_response(exc: CommunityPipelineError):
    return jsonify({"error": str(exc)}), exc.status_code


def _user_error_response(exc: UserPipelineError):
    return jsonify({"error": str(exc)}), exc.status_code


@communities_bp.get("")
def get_communities():
    try:
        verify_firebase_token_optional(request.headers.get("Authorization"))
        communities = list_communities()
        return jsonify({"communities": communities}), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to load communities"}), 500


@communities_bp.post("")
def post_community():
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        payload = request.get_json(silent=True) or {}
        community = create_community(
            actor_uid,
            str(payload.get("name", "")),
            str(payload.get("description", "")),
        )
        return jsonify(community), 201
    except AuthError as exc:
        return _auth_error_response(exc)
    except CommunityPipelineError as exc:
        return _community_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to create community"}), 500


@communities_bp.post("/<community_id>/join")
def post_join(community_id: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        result = join_community(actor_uid, community_id)
        return jsonify(result), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except CommunityPipelineError as exc:
        return _community_error_response(exc)
    except UserPipelineError as exc:
        return _user_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to join community"}), 500


@communities_bp.post("/<community_id>/leave")
def post_leave(community_id: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        result = leave_community(actor_uid, community_id)
        return jsonify(result), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except CommunityPipelineError as exc:
        return _community_error_response(exc)
    except UserPipelineError as exc:
        return _user_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to leave community"}), 500


@communities_bp.get("/<community_id>/moderators")
def get_moderators(community_id: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        moderators = fetch_community_moderators(actor_uid, community_id)
        return jsonify({"moderators": moderators}), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except AuthorizationError as exc:
        return _authorization_error_response(exc)
    except UserPipelineError as exc:
        return _user_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to load moderators"}), 500


@communities_bp.post("/<community_id>/moderators")
def post_moderator(community_id: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        payload = request.get_json(silent=True) or {}
        target_uid = str(payload.get("uid", "")).strip()
        if not target_uid:
            raise CommunityPipelineError("uid is required")
        grant_community_moderator(actor_uid, target_uid, community_id)
        return jsonify({"ok": True}), 201
    except AuthError as exc:
        return _auth_error_response(exc)
    except AuthorizationError as exc:
        return _authorization_error_response(exc)
    except CommunityPipelineError as exc:
        return _community_error_response(exc)
    except UserPipelineError as exc:
        return _user_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to grant moderator"}), 500


@communities_bp.delete("/<community_id>/moderators/<target_uid>")
def delete_moderator(community_id: str, target_uid: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        revoke_community_moderator(actor_uid, target_uid, community_id)
        return jsonify({"ok": True}), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except AuthorizationError as exc:
        return _authorization_error_response(exc)
    except UserPipelineError as exc:
        return _user_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to revoke moderator"}), 500
