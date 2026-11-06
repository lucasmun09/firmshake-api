from firebase_admin import auth
from google.cloud import firestore

from services.controlpanel_auth import is_super_admin
from services.firebase_app import get_db


class OperatorError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def list_operators() -> list[dict]:
    db = get_db()
    operators: list[dict] = []
    for snapshot in db.collection("controlpanelOperators").stream():
        data = snapshot.to_dict() or {}
        operators.append(
            {
                "uid": snapshot.id,
                "email": data.get("email", ""),
                "addedBy": data.get("addedBy", ""),
                "addedAt": _serialize_timestamp(data.get("addedAt")),
            }
        )
    operators.sort(key=lambda entry: entry.get("email", ""))
    return operators


def add_operator(*, email: str, added_by: str) -> dict:
    normalized = email.strip().lower()
    if not normalized:
        raise OperatorError("Email is required", 400)

    try:
        user = auth.get_user_by_email(normalized)
    except auth.UserNotFoundError as exc:
        raise OperatorError(
            f"No Firebase user found for {normalized}. They must sign up first.",
            404,
        ) from exc

    db = get_db()
    doc_ref = db.collection("controlpanelOperators").document(user.uid)
    if doc_ref.get().exists:
        raise OperatorError(f"{normalized} already has controlpanel access", 409)

    payload = {
        "email": normalized,
        "addedBy": added_by,
        "addedAt": firestore.SERVER_TIMESTAMP,
    }
    doc_ref.set(payload)
    return {"uid": user.uid, "email": normalized}


def remove_operator(*, uid: str, caller_uid: str) -> dict:
    if uid == caller_uid and not is_super_admin(caller_uid):
        raise OperatorError("You cannot remove your own controlpanel access", 400)

    db = get_db()
    doc_ref = db.collection("controlpanelOperators").document(uid)
    snapshot = doc_ref.get()
    if not snapshot.exists:
        raise OperatorError("Operator not found", 404)

    data = snapshot.to_dict() or {}
    doc_ref.delete()
    return {"uid": uid, "email": data.get("email", "")}


def _serialize_timestamp(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "timestamp"):
        from datetime import datetime, timezone

        return datetime.fromtimestamp(value.timestamp(), tz=timezone.utc).isoformat()
    return str(value)
