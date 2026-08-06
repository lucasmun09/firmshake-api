import re

from firebase_admin import auth
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

from services.firebase_app import get_db


class BanError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value.strip())
    if not digits:
        raise BanError("Phone number is required", 400)
    if len(digits) == 10:
        return f"+1{digits}"
    if digits.startswith("1") and len(digits) == 11:
        return f"+{digits}"
    if value.strip().startswith("+"):
        return f"+{digits}"
    return f"+{digits}"


def _ban_doc_id(ban_type: str, value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", value)
    return f"{ban_type}_{safe}"


def list_bans(limit: int = 100) -> list[dict]:
    db = get_db()
    snapshots = (
        db.collection("platformBans")
        .where(filter=FieldFilter("active", "==", True))
        .limit(min(max(limit, 1), 200))
        .stream()
    )
    bans: list[dict] = []
    for snapshot in snapshots:
        data = snapshot.to_dict() or {}
        bans.append(
            {
                "id": snapshot.id,
                "type": data.get("type", ""),
                "value": data.get("value", ""),
                "reason": data.get("reason", ""),
                "bannedBy": data.get("bannedBy", ""),
                "bannedAt": _serialize_timestamp(data.get("bannedAt")),
            }
        )
    bans.sort(key=lambda entry: entry.get("bannedAt") or "", reverse=True)
    return bans


def create_ban(*, ban_type: str, value: str, reason: str, banned_by: str) -> dict:
    if ban_type not in {"email", "phone"}:
        raise BanError("Ban type must be email or phone", 400)

    normalized = normalize_email(value) if ban_type == "email" else normalize_phone(value)
    if not normalized:
        raise BanError("Value is required", 400)

    db = get_db()
    doc_id = _ban_doc_id(ban_type, normalized)
    doc_ref = db.collection("platformBans").document(doc_id)
    existing = doc_ref.get()
    if existing.exists and (existing.to_dict() or {}).get("active"):
        raise BanError(f"Already banned: {normalized}", 409)

    payload = {
        "type": ban_type,
        "value": normalized,
        "reason": reason.strip(),
        "bannedBy": banned_by,
        "bannedAt": firestore.SERVER_TIMESTAMP,
        "active": True,
    }
    doc_ref.set(payload)

    disabled_uids: list[str] = []
    if ban_type == "email":
        disabled_uids.extend(_disable_users_by_email(normalized))
    else:
        disabled_uids.extend(_disable_users_by_phone(normalized))

    return {
        "id": doc_id,
        "type": ban_type,
        "value": normalized,
        "reason": reason.strip(),
        "disabledUserIds": disabled_uids,
    }


def remove_ban(ban_id: str) -> dict:
    db = get_db()
    doc_ref = db.collection("platformBans").document(ban_id)
    snapshot = doc_ref.get()
    if not snapshot.exists:
        raise BanError("Ban not found", 404)

    data = snapshot.to_dict() or {}
    doc_ref.update({"active": False, "unbannedAt": firestore.SERVER_TIMESTAMP})

    reenabled: list[str] = []
    if data.get("type") == "email":
        reenabled.extend(_enable_users_by_email(str(data.get("value", ""))))
    elif data.get("type") == "phone":
        reenabled.extend(_enable_users_by_phone(str(data.get("value", ""))))

    return {"id": ban_id, "reenabledUserIds": reenabled}


def is_banned(*, email: str | None = None, phone: str | None = None) -> dict | None:
    db = get_db()
    checks: list[tuple[str, str]] = []
    if email:
        checks.append(("email", normalize_email(email)))
    if phone:
        checks.append(("phone", normalize_phone(phone)))

    for ban_type, value in checks:
        doc_id = _ban_doc_id(ban_type, value)
        snapshot = db.collection("platformBans").document(doc_id).get()
        if snapshot.exists and (snapshot.to_dict() or {}).get("active"):
            data = snapshot.to_dict() or {}
            return {
                "type": ban_type,
                "value": value,
                "reason": data.get("reason", ""),
            }
    return None


def _disable_users_by_email(email: str) -> list[str]:
    return _set_users_disabled_by_email(email, disabled=True)


def _enable_users_by_email(email: str) -> list[str]:
    return _set_users_disabled_by_email(email, disabled=False)


def _set_users_disabled_by_email(email: str, *, disabled: bool) -> list[str]:
    db = get_db()
    matches = (
        db.collection("users")
        .where(filter=FieldFilter("email", "==", email))
        .limit(20)
        .stream()
    )
    updated: list[str] = []
    for snapshot in matches:
        uid = snapshot.id
        try:
            auth.update_user(uid, disabled=disabled)
            updated.append(uid)
        except auth.UserNotFoundError:
            continue
    return updated


def _disable_users_by_phone(phone: str) -> list[str]:
    return _set_users_disabled_by_phone(phone, disabled=True)


def _enable_users_by_phone(phone: str) -> list[str]:
    return _set_users_disabled_by_phone(phone, disabled=False)


def _set_users_disabled_by_phone(phone: str, *, disabled: bool) -> list[str]:
    db = get_db()
    matches = (
        db.collection("users")
        .where(filter=FieldFilter("testPhone", "==", phone))
        .limit(20)
        .stream()
    )
    updated: list[str] = []
    for snapshot in matches:
        uid = snapshot.id
        try:
            auth.update_user(uid, disabled=disabled)
            updated.append(uid)
        except auth.UserNotFoundError:
            continue
    return updated


def _serialize_timestamp(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "timestamp"):
        from datetime import datetime, timezone

        return datetime.fromtimestamp(value.timestamp(), tz=timezone.utc).isoformat()
    return str(value)
