from flask import Blueprint, g, jsonify, request

from services.auth import AuthError, verify_firebase_token
from services.inbox_pipeline import (
    DEFAULT_THREADS_PAGE_SIZE,
    InboxPipelineError,
    archive_thread,
    get_inbox_threads,
    mark_thread_read,
    unarchive_thread,
)

inbox_bp = Blueprint("v1_inbox", __name__)


def _auth_error_response(exc: AuthError):
    return jsonify({"error": str(exc)}), exc.status_code


def _inbox_error_response(exc: InboxPipelineError):
    return jsonify({"error": str(exc)}), exc.status_code


@inbox_bp.get("/threads")
def get_threads():
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid

        cursor = request.args.get("cursor")
        limit_raw = request.args.get("limit", type=int)
        limit = limit_raw if limit_raw is not None else DEFAULT_THREADS_PAGE_SIZE

        result = get_inbox_threads(actor_uid, cursor=cursor, limit=limit)
        return jsonify(result), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except InboxPipelineError as exc:
        return _inbox_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to load inbox threads"}), 500


@inbox_bp.post("/threads/<path:thread_key>/read")
def post_thread_read(thread_key: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        inbox_state = mark_thread_read(actor_uid, thread_key)
        return jsonify({"inboxState": inbox_state}), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except InboxPipelineError as exc:
        return _inbox_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to mark thread read"}), 500


@inbox_bp.post("/threads/<path:thread_key>/archive")
def post_thread_archive(thread_key: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        inbox_state = archive_thread(actor_uid, thread_key)
        return jsonify({"inboxState": inbox_state}), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except InboxPipelineError as exc:
        return _inbox_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to archive thread"}), 500


@inbox_bp.post("/threads/<path:thread_key>/unarchive")
def post_thread_unarchive(thread_key: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        inbox_state = unarchive_thread(actor_uid, thread_key)
        return jsonify({"inboxState": inbox_state}), 200
    except AuthError as exc:
        return _auth_error_response(exc)
    except InboxPipelineError as exc:
        return _inbox_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to unarchive thread"}), 500
