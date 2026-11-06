from flask import Flask, g, jsonify, request

from services.auth import AuthError, verify_firebase_token_optional
from services.rate_limit import RateLimitExceeded, assert_api_rate_allowed


def init_api_middleware(app: Flask) -> None:
    @app.before_request
    def enforce_api_rate_limits():
        if not request.path.startswith("/api/"):
            return None

        uid = None
        try:
            uid = verify_firebase_token_optional(request.headers.get("Authorization"))
        except AuthError:
            uid = None

        if uid:
            g.authenticated_uid = uid

        try:
            assert_api_rate_allowed(request.remote_addr or "unknown", uid)
        except RateLimitExceeded as exc:
            return jsonify({"error": str(exc)}), exc.status_code

        return None
