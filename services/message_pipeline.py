"""Listing message send with thread sync, in-app notification, and push."""

from google.cloud import firestore

from services.firebase_app import get_db
from services.message_authorization import (
    MessageAuthorizationError,
    assert_can_send_message,
    resolve_recipient_id,
)
from services.push import send_push_to_user

MAX_MESSAGE_TEXT_LENGTH = 1000


class MessagePipelineError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _seller_thread_doc_id(listing_id: str, buyer_id: str) -> str:
    return f"{listing_id}_{buyer_id}"


def _resolve_buyer_from_message(listing: dict, message: dict) -> str | None:
    seller_id = str(listing.get("sellerId", ""))
    sender_id = str(message.get("senderId", ""))

    if sender_id != seller_id:
        return sender_id

    recipient_id = message.get("recipientId")
    if recipient_id and str(recipient_id) != seller_id:
        return str(recipient_id)
    return None


def _write_thread_for_user(
    db,
    user_id: str,
    listing_id: str,
    listing: dict,
    message: dict,
    updated_by: str,
) -> None:
    seller_id = str(listing.get("sellerId", ""))
    is_seller = user_id == seller_id
    now = firestore.SERVER_TIMESTAMP

    base_payload = {
        "listingId": listing_id,
        "listingTitle": listing.get("title", "Listing"),
        "listingImageUrl": listing.get("imageUrl", ""),
        "listingStatus": listing.get("status", "active"),
        "sellerId": seller_id,
        "sellerName": listing.get("sellerName", "Seller"),
        "lastMessageText": message["text"],
        "lastMessageSenderId": message["senderId"],
        "lastMessageSenderName": message["senderName"],
        "lastMessageAt": now,
        "updatedAt": now,
        "updatedBy": updated_by,
    }

    if is_seller:
        buyer_id = _resolve_buyer_from_message(listing, message)
        if not buyer_id:
            return

        payload = {**base_payload, "buyerId": buyer_id}
        if message["senderId"] == buyer_id:
            payload["buyerName"] = message["senderName"]

        doc_id = _seller_thread_doc_id(listing_id, buyer_id)
    else:
        payload = base_payload
        doc_id = listing_id

    (
        db.collection("users")
        .document(user_id)
        .collection("threads")
        .document(doc_id)
        .set(payload, merge=True)
    )


def _sync_message_threads(
    db,
    listing_id: str,
    listing: dict,
    message: dict,
    actor_uid: str,
) -> None:
    participants = {str(listing.get("sellerId", "")), str(message["senderId"])}
    recipient_id = message.get("recipientId")
    if recipient_id:
        participants.add(str(recipient_id))

    for user_id in participants:
        if user_id:
            _write_thread_for_user(db, user_id, listing_id, listing, message, actor_uid)

    (
        db.collection("users")
        .document(actor_uid)
        .collection("messageListings")
        .document(listing_id)
        .set({"listingId": listing_id, "updatedAt": firestore.SERVER_TIMESTAMP}, merge=True)
    )


def _create_message_notification(
    db,
    *,
    recipient_id: str,
    actor_id: str,
    sender_name: str,
    listing_id: str,
    listing_title: str,
    text: str,
) -> None:
    if recipient_id == actor_id:
        return

    title = f"{sender_name} messaged you"
    body = f"{listing_title}: {text}"

    notification_ref = (
        db.collection("users").document(recipient_id).collection("notifications").document()
    )
    notification_ref.set(
        {
            "recipientId": recipient_id,
            "actorId": actor_id,
            "type": "message",
            "title": title,
            "body": body,
            "listingId": listing_id,
            "read": False,
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
    )

    send_push_to_user(
        recipient_id,
        title,
        body,
        {
            "type": "message",
            "actorId": actor_id,
            "listingId": listing_id,
        },
    )


def _serialize_message(listing_id: str, message_id: str, data: dict) -> dict:
    created_at = data.get("createdAt")
    created_ms = None
    if created_at is not None and hasattr(created_at, "timestamp"):
        created_ms = int(created_at.timestamp() * 1000)

    return {
        "id": message_id,
        "listingId": listing_id,
        "senderId": data.get("senderId", ""),
        "senderName": data.get("senderName", "Unknown"),
        "text": data.get("text", ""),
        "recipientId": data.get("recipientId"),
        "createdAt": created_ms,
    }


def _validate_payload(payload: dict) -> tuple[str, str, str | None]:
    text = str(payload.get("text", "")).strip()
    if not text:
        raise MessagePipelineError("Message cannot be empty", 400)
    if len(text) > MAX_MESSAGE_TEXT_LENGTH:
        raise MessagePipelineError(
            f"Message must be at most {MAX_MESSAGE_TEXT_LENGTH} characters",
            400,
        )

    sender_name = str(payload.get("senderName", "")).strip()
    if not sender_name:
        raise MessagePipelineError("senderName is required", 400)

    recipient_id = payload.get("recipientId")
    explicit_recipient = str(recipient_id).strip() if recipient_id else None
    if explicit_recipient == "":
        explicit_recipient = None

    return text, sender_name, explicit_recipient


def send_listing_message(actor_uid: str, listing_id: str, payload: dict) -> dict:
    listing_id = listing_id.strip()
    if not listing_id:
        raise MessagePipelineError("Listing id is required", 400)

    try:
        text, sender_name, explicit_recipient = _validate_payload(payload)
    except MessagePipelineError:
        raise
    except Exception as exc:
        raise MessagePipelineError(str(exc), 400) from exc

    db = get_db()
    listing_snapshot = db.collection("listings").document(listing_id).get()
    if not listing_snapshot.exists:
        raise MessagePipelineError("Listing not found", 404)

    listing = listing_snapshot.to_dict() or {}

    try:
        recipient_id = resolve_recipient_id(actor_uid, listing, explicit_recipient)
        assert_can_send_message(actor_uid, listing, recipient_id)
    except MessageAuthorizationError as exc:
        raise MessagePipelineError(str(exc), exc.status_code) from exc

    message_payload = {
        "senderId": actor_uid,
        "senderName": sender_name,
        "text": text,
        "recipientId": recipient_id,
        "createdAt": firestore.SERVER_TIMESTAMP,
    }

    message_ref = (
        db.collection("listings").document(listing_id).collection("messages").document()
    )
    message_ref.set(message_payload)

    message_for_sync = {
        **message_payload,
        "createdAt": firestore.SERVER_TIMESTAMP,
    }

    try:
        _sync_message_threads(db, listing_id, listing, message_for_sync, actor_uid)
    except Exception as exc:
        raise MessagePipelineError(
            f"Message sent but thread sync failed: {exc}",
            502,
        ) from exc

    try:
        _create_message_notification(
            db,
            recipient_id=recipient_id,
            actor_id=actor_uid,
            sender_name=sender_name,
            listing_id=listing_id,
            listing_title=str(listing.get("title", "Listing")),
            text=text,
        )
    except Exception:
        # Notification/push failure must not fail the send — message is already persisted.
        pass

    created_snapshot = message_ref.get()
    return _serialize_message(
        listing_id,
        message_ref.id,
        created_snapshot.to_dict() or message_payload,
    )
