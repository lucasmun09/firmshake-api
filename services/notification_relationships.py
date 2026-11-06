"""Verify actor/recipient share a listing thread, agreement, or message context."""

from google.cloud.firestore_v1 import FieldFilter

from services.firebase_app import get_db


class RelationshipError(Exception):
    def __init__(self, message: str, status_code: int = 403):
        super().__init__(message)
        self.status_code = status_code


def _pair_key(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left <= right else (right, left)


def _users_blocked(blocker_id: str, blocked_id: str) -> bool:
    db = get_db()
    snapshot = db.collection("users").document(blocker_id).collection("blockedUsers").document(
        blocked_id
    ).get()
    return snapshot.exists


def _has_agreement_between(actor_id: str, recipient_id: str, listing_id: str | None = None) -> bool:
    db = get_db()
    queries = []
    for buyer_id, seller_id in ((actor_id, recipient_id), (recipient_id, actor_id)):
        query = (
            db.collection("agreements")
            .where(filter=FieldFilter("buyerId", "==", buyer_id))
            .where(filter=FieldFilter("sellerId", "==", seller_id))
            .limit(5)
        )
        queries.append(query)

    for query in queries:
        for snapshot in query.stream():
            if listing_id and snapshot.to_dict().get("listingId") != listing_id:
                continue
            return True
    return False


def _has_listing_message_context(
    actor_id: str,
    recipient_id: str,
    listing_id: str,
    seller_id: str,
) -> bool:
    db = get_db()
    if seller_id not in (actor_id, recipient_id):
        return False

    other_id = recipient_id if actor_id == seller_id else actor_id

    for field, user_id in (("senderId", actor_id), ("senderId", recipient_id)):
        messages = (
            db.collection("listings")
            .document(listing_id)
            .collection("messages")
            .where(filter=FieldFilter(field, "==", user_id))
            .limit(1)
            .stream()
        )
        for message in messages:
            data = message.to_dict() or {}
            participants = {data.get("senderId"), data.get("recipientId"), seller_id}
            if actor_id in participants and recipient_id in participants:
                return True

    thread_ref = (
        db.collection("users")
        .document(other_id)
        .collection("threads")
        .document(listing_id)
    )
    if thread_ref.get().exists:
        return True

    seller_thread_ref = (
        db.collection("users")
        .document(seller_id)
        .collection("threads")
        .document(f"{listing_id}_{other_id}")
    )
    if seller_thread_ref.get().exists:
        return True

    return _has_agreement_between(actor_id, recipient_id, listing_id)


def verify_push_relationship(
    actor_id: str,
    recipient_id: str,
    notification_type: str,
    listing_id: str | None = None,
) -> None:
    if actor_id == recipient_id:
        return

    if _users_blocked(recipient_id, actor_id):
        raise RelationshipError("Push not allowed to this recipient", 403)

    if notification_type == "meetup":
        if not listing_id:
            if _has_agreement_between(actor_id, recipient_id):
                return
            raise RelationshipError("Meetup push requires a shared agreement", 403)
        if _has_agreement_between(actor_id, recipient_id, listing_id):
            return
        raise RelationshipError("No meetup agreement between users for this listing", 403)

    if listing_id:
        db = get_db()
        listing_snapshot = db.collection("listings").document(listing_id).get()
        if not listing_snapshot.exists:
            raise RelationshipError("Listing not found", 404)

        listing = listing_snapshot.to_dict() or {}
        seller_id = str(listing.get("sellerId", ""))
        if _has_listing_message_context(actor_id, recipient_id, listing_id, seller_id):
            return
        if _has_agreement_between(actor_id, recipient_id, listing_id):
            return
        raise RelationshipError("Users do not share a listing context", 403)

    if _has_agreement_between(actor_id, recipient_id):
        return

    raise RelationshipError("Users do not share a message or agreement context", 403)
