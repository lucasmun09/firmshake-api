import logging

from firebase_admin import auth

from services.firebase_app import get_db

logger = logging.getLogger("firmshake.auth")


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


def verify_firebase_token_optional(authorization_header: str | None) -> str | None:
    if not authorization_header or not authorization_header.startswith("Bearer "):
        return None

    token = authorization_header.split(" ", 1)[1].strip()
    if not token:
        return None

    get_db()

    try:
        decoded = auth.verify_id_token(token)
    except Exception as exc:
        logger.info("Optional auth ignored invalid Firebase token", exc_info=exc)
        return None

    uid = decoded.get("uid")
    if not uid:
        logger.info("Optional auth ignored Firebase token without uid")
        return None
    return uid


def verify_firebase_token(authorization_header: str | None) -> str:
    if not authorization_header or not authorization_header.startswith("Bearer "):
        raise AuthError("Missing Authorization header", 401)

    token = authorization_header.split(" ", 1)[1].strip()
    if not token:
        raise AuthError("Missing Authorization header", 401)

    # Token verification requires Firebase Admin to be initialized first.
    get_db()

    try:
        decoded = auth.verify_id_token(token)
    except Exception as exc:
        raise AuthError("Invalid Firebase token", 401) from exc

    uid = decoded.get("uid")
    if not uid:
        raise AuthError("Invalid Firebase token", 401)
    return uid
