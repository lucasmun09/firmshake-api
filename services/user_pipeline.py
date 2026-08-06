"""User profile read/update mirroring firmshake client users.ts."""

import logging
import re

from google.cloud import firestore

from services.authorization import (
    AuthorizationError,
    can_lookup_user_by_email,
    get_user_profile,
)
from services.firebase_app import get_db

logger = logging.getLogger("firmshake.user_pipeline")

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class UserPipelineError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _format_display_name(first_name: str, last_name: str) -> str:
    parts = [first_name.strip(), last_name.strip()]
    combined = " ".join(part for part in parts if part)
    return combined or "FirmShake User"


def _resolve_account_setup_complete(data: dict) -> bool:
    if data.get("accountSetupComplete") is not None:
        return bool(data.get("accountSetupComplete"))
    auth_provider = data.get("authProvider")
    if auth_provider == "password":
        return False
    return auth_provider == "google.com"


def _map_profile_full(uid: str, data: dict) -> dict:
    is_super = bool(data.get("isSuperAdmin") or data.get("isAdmin"))
    stored_first = str(data.get("firstName") or "")
    stored_last = str(data.get("lastName") or "")
    legacy_display = str(data.get("displayName") or "")
    first_name = stored_first or legacy_display.split(" ", 1)[0]
    last_name = stored_last or (legacy_display.split(" ", 1)[1] if " " in legacy_display else "")
    display_name = legacy_display.strip() or _format_display_name(first_name, last_name)

    return {
        "uid": uid,
        "email": str(data.get("email") or ""),
        "firstName": first_name,
        "lastName": last_name,
        "displayName": display_name,
        "photoUrl": data.get("photoUrl"),
        "communityIds": [str(cid) for cid in (data.get("communityIds") or ["all"])],
        "isAdmin": is_super,
        "isSuperAdmin": is_super,
        "moderatorCommunityIds": [
            str(cid) for cid in (data.get("moderatorCommunityIds") or [])
        ],
        "profileComplete": bool(data.get("profileComplete"))
        if data.get("profileComplete") is not None
        else bool(first_name.strip() and last_name.strip()),
        "accountSetupComplete": _resolve_account_setup_complete(data),
        "authProvider": data.get("authProvider"),
    }


def _map_profile_public(uid: str, data: dict) -> dict:
    full = _map_profile_full(uid, data)
    return {
        "uid": full["uid"],
        "displayName": full["displayName"],
        "photoUrl": full.get("photoUrl"),
    }


def get_current_user(uid: str) -> dict:
    db = get_db()
    profile = get_user_profile(db, uid)
    if not profile:
        raise UserPipelineError("User profile not found", 404)
    return _map_profile_full(uid, profile)


def get_public_user(uid: str) -> dict:
    db = get_db()
    profile = get_user_profile(db, uid)
    if not profile:
        raise UserPipelineError("User not found", 404)
    return _map_profile_public(uid, profile)


def update_current_user(uid: str, payload: dict) -> dict:
    db = get_db()
    user_ref = db.collection("users").document(uid)
    snapshot = user_ref.get()
    if not snapshot.exists:
        raise UserPipelineError("User profile not found", 404)

    updates: dict = {}

    if "firstName" in payload or "lastName" in payload:
        first_name = str(payload.get("firstName", snapshot.get("firstName") or "")).strip()
        last_name = str(payload.get("lastName", snapshot.get("lastName") or "")).strip()
        if not first_name or not last_name:
            raise UserPipelineError("First name and last name are required")
        updates["firstName"] = first_name
        updates["lastName"] = last_name
        updates["displayName"] = _format_display_name(first_name, last_name)
        updates["profileComplete"] = True

    if "photoUrl" in payload:
        photo_url = payload.get("photoUrl")
        if photo_url is not None and not isinstance(photo_url, str):
            raise UserPipelineError("photoUrl must be a string")
        updates["photoUrl"] = photo_url

    if payload.get("accountSetupComplete") is True:
        updates["accountSetupComplete"] = True
        updates["profileComplete"] = True

    if payload.get("profileComplete") is True:
        updates["profileComplete"] = True

    forbidden = {"email", "communityIds", "moderatorCommunityIds", "isAdmin", "isSuperAdmin", "uid"}
    attempted = forbidden.intersection(payload.keys())
    if attempted:
        raise AuthorizationError(
            f"Cannot update restricted fields: {', '.join(sorted(attempted))}"
        )

    if not updates:
        raise UserPipelineError("No valid fields to update")

    user_ref.update(updates)
    refreshed = user_ref.get()
    return _map_profile_full(uid, refreshed.to_dict() or {})


def find_user_by_email(actor_uid: str, email: str) -> dict:
    db = get_db()
    actor_profile = get_user_profile(db, actor_uid)
    if not can_lookup_user_by_email(actor_profile):
        raise AuthorizationError("You do not have permission to look up users by email")

    normalized = email.strip().lower()
    if not normalized or not EMAIL_PATTERN.match(normalized):
        raise UserPipelineError("A valid email address is required")

    logger.info(
        "email lookup",
        extra={"actor_uid": actor_uid, "email_domain": normalized.split("@")[-1]},
    )

    matches = (
        db.collection("users")
        .where("email", "==", normalized)
        .limit(1)
        .stream()
    )
    docs = list(matches)
    if not docs:
        legacy_matches = (
            db.collection("users")
            .where("email", "==", email.strip())
            .limit(1)
            .stream()
        )
        docs = list(legacy_matches)

    if not docs:
        raise UserPipelineError("No user found with that email", 404)

    doc = docs[0]
    return _map_profile_full(doc.id, doc.to_dict() or {})


def fetch_community_moderators(actor_uid: str, community_id: str) -> list[dict]:
    from services.authorization import can_manage_community_moderators

    db = get_db()
    actor_profile = get_user_profile(db, actor_uid)
    if not can_manage_community_moderators(actor_profile, community_id):
        raise AuthorizationError(
            "You do not have permission to view moderators for this community"
        )

    snapshot = (
        db.collection("users")
        .where("moderatorCommunityIds", "array-contains", community_id)
        .stream()
    )
    return [_map_profile_full(doc.id, doc.to_dict() or {}) for doc in snapshot]


def grant_community_moderator(actor_uid: str, target_uid: str, community_id: str) -> None:
    from services.authorization import (
        can_manage_community_moderators,
        is_community_moderator,
        is_super_admin,
    )

    db = get_db()
    actor_profile = get_user_profile(db, actor_uid)
    if not can_manage_community_moderators(actor_profile, community_id):
        raise AuthorizationError(
            "You do not have permission to grant moderators for this community"
        )

    target_profile = get_user_profile(db, target_uid)
    if not target_profile:
        raise UserPipelineError("User not found", 404)

    if is_super_admin(target_profile):
        raise UserPipelineError("Super admin moderator access cannot be changed")

    moderator_ids = target_profile.get("moderatorCommunityIds") or []
    if community_id in moderator_ids:
        return

    if not is_super_admin(actor_profile) and not is_community_moderator(
        actor_profile, community_id
    ):
        raise AuthorizationError(
            "You can only grant moderators for communities you moderate"
        )

    db.collection("users").document(target_uid).update(
        {"moderatorCommunityIds": firestore.ArrayUnion([community_id])}
    )


def revoke_community_moderator(actor_uid: str, target_uid: str, community_id: str) -> None:
    from services.authorization import (
        can_manage_community_moderators,
        is_community_moderator,
        is_super_admin,
    )

    db = get_db()
    actor_profile = get_user_profile(db, actor_uid)
    if not can_manage_community_moderators(actor_profile, community_id):
        raise AuthorizationError(
            "You do not have permission to revoke moderators for this community"
        )

    target_profile = get_user_profile(db, target_uid)
    if not target_profile:
        raise UserPipelineError("User not found", 404)

    if is_super_admin(target_profile):
        raise UserPipelineError("Super admin moderator access cannot be changed")

    if not is_super_admin(actor_profile) and not is_community_moderator(
        actor_profile, community_id
    ):
        raise AuthorizationError(
            "You can only revoke moderators for communities you moderate"
        )

    moderator_ids = target_profile.get("moderatorCommunityIds") or []
    if community_id not in moderator_ids:
        return

    db.collection("users").document(target_uid).update(
        {"moderatorCommunityIds": firestore.ArrayRemove([community_id])}
    )
