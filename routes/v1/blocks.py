from flask import Blueprint, g, jsonify, request

from services.auth import AuthError, verify_firebase_token
from services.block_pipeline import BlockPipelineError, block_user, list_blocked_users, unblock_user

blocks_bp = Blueprint("v1_blocks", __name__)


def _auth_error_response(exc: AuthError):
    return jsonify({"error": str(exc)}), exc.status_code


def _block_error_response(exc: BlockPipelineError):
    return jsonify({"error": str(exc)}), exc.status_code


@blocks_bp.get("")
def get_blocks():
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        entries = list_blocked_users(actor_uid)
        return jsonify({"blocks": entries}), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to load blocked users"}), 500


@blocks_bp.post("/<blocked_uid>")
def post_block(blocked_uid: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        entry = block_user(actor_uid, blocked_uid)
        return jsonify(entry), 201
    except AuthError as exc:
        return _auth_error_response(exc)
    except BlockPipelineError as exc:
        return _block_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to block user"}), 500


@blocks_bp.delete("/<blocked_uid>")
def delete_block(blocked_uid: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        unblock_user(actor_uid, blocked_uid)
        return jsonify({"ok": True}), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to unblock user"}), 500
