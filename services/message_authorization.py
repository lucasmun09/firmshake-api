"""Authorization for listing message sends (mirrors firmshake client messages.ts)."""

from services.firebase_app import get_db


class MessageAuthorizationError(Exception):
    def __init__(self, message: str, status_code: int = 403):
        super().__init__(message)
        self.status_code = status_code


def is_user_blocked(blocker_id: str, blocked_id: str) -> bool:
    db = get_db()
    snapshot = (
        db.collection("users")
        .document(blocker_id)
        .collection("blockedUsers")
        .document(blocked_id)
        .get()
    )
    return snapshot.exists


def resolve_recipient_id(
    actor_uid: str,
    listing: dict,
    explicit_recipient_id: str | None,
) -> str:
    seller_id = str(listing.get("sellerId", ""))

    if actor_uid != seller_id:
        if not seller_id:
            raise MessageAuthorizationError("Listing has no seller", 400)
        return seller_id

    recipient_id = (explicit_recipient_id or "").strip()
    if not recipient_id:
        raise MessageAuthorizationError("Choose a buyer before replying", 400)
    if recipient_id == actor_uid:
        raise MessageAuthorizationError("Invalid message recipient", 400)
    return recipient_id


def assert_can_send_message(
    actor_uid: str,
    listing: dict,
    recipient_id: str,
) -> None:
    seller_id = str(listing.get("sellerId", ""))
    participants = {actor_uid, recipient_id, seller_id}

    if actor_uid not in participants or recipient_id not in participants:
        raise MessageAuthorizationError("Invalid message participants", 403)

    if actor_uid == recipient_id:
        raise MessageAuthorizationError("Cannot message yourself", 400)

    if is_user_blocked(recipient_id, actor_uid):
        raise MessageAuthorizationError(
            "This user is not accepting messages from you",
            403,
        )
