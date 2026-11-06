import os

from google.cloud.firestore_v1 import FieldFilter

from services.auth import AuthError
from services.firebase_app import get_db


class ControlpanelAccessError(Exception):
    def __init__(self, message: str, status_code: int = 403):
        super().__init__(message)
        self.status_code = status_code


def _bootstrap_emails() -> set[str]:
    raw = os.getenv("CONTROLPANEL_BOOTSTRAP_EMAILS", "")
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def _user_profile(uid: str) -> dict | None:
    snapshot = get_db().collection("users").document(uid).get()
    if not snapshot.exists:
        return None
    return snapshot.to_dict() or {}


def is_super_admin(uid: str) -> bool:
    profile = _user_profile(uid)
    if not profile:
        return False
    return bool(profile.get("isSuperAdmin") or profile.get("isAdmin"))


def is_controlpanel_operator(uid: str) -> bool:
    if is_super_admin(uid):
        return True

    snapshot = get_db().collection("controlpanelOperators").document(uid).get()
    return snapshot.exists


def require_controlpanel_access(uid: str, email: str | None = None) -> None:
    if is_controlpanel_operator(uid):
        return

    normalized_email = (email or "").strip().lower()
    if normalized_email and normalized_email in _bootstrap_emails():
        return

    raise ControlpanelAccessError("Controlpanel access denied", 403)


def get_caller_email(uid: str) -> str:
    profile = _user_profile(uid)
    if profile and profile.get("email"):
        return str(profile["email"]).lower()

    from firebase_admin import auth

    try:
        user = auth.get_user(uid)
        return (user.email or "").lower()
    except Exception as exc:  # noqa: BLE001
        raise AuthError("Unable to resolve caller email", 401) from exc


def verify_controlpanel_request(authorization_header: str | None) -> tuple[str, str]:
    from services.auth import verify_firebase_token

    uid = verify_firebase_token(authorization_header)
    email = get_caller_email(uid)
    require_controlpanel_access(uid, email)
    return uid, email
