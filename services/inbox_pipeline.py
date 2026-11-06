"""Inbox thread reads and inboxState mutations via Admin SDK."""

from google.cloud import firestore

from services.firebase_app import get_db
from services.listing_pipeline import _serialize_listing_response

DEFAULT_THREADS_PAGE_SIZE = 30
MAX_THREADS_PAGE_SIZE = 50


class InboxPipelineError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _parse_thread_key(key: str) -> tuple[str, str | None]:
    thread_key = key.strip()
    if not thread_key:
        raise InboxPipelineError("Thread key is required", 400)

    if "_" in thread_key:
        listing_id, buyer_id = thread_key.split("_", 1)
        if not listing_id or not buyer_id:
            raise InboxPipelineError("Invalid thread key", 400)
        return listing_id, buyer_id

    return thread_key, None


def _timestamp_ms(value) -> int | None:
    if value is None:
        return None
    if hasattr(value, "timestamp"):
        return int(value.timestamp() * 1000)
    return None


def _map_inbox_state(doc_id: str, data: dict | None) -> dict:
    if not data:
        return {
            "listingId": doc_id.split("_")[0],
            "buyerId": doc_id.split("_", 1)[1] if "_" in doc_id else None,
            "hasViewed": False,
            "isArchived": False,
            "lastReadAt": None,
            "archivedAt": None,
        }

    listing_id = str(data.get("listingId") or doc_id.split("_")[0])
    buyer_id = data.get("buyerId")
    return {
        "listingId": listing_id,
        "buyerId": str(buyer_id) if buyer_id else None,
        "hasViewed": bool(data.get("hasViewed")),
        "isArchived": bool(data.get("isArchived")),
        "lastReadAt": _timestamp_ms(data.get("lastReadAt")),
        "archivedAt": _timestamp_ms(data.get("archivedAt")),
    }


def _serialize_thread(
    doc_id: str,
    data: dict,
    *,
    listing: dict | None,
    inbox_state: dict,
) -> dict:
    listing_id = str(data.get("listingId") or doc_id.split("_")[0])
    buyer_id = data.get("buyerId")
    buyer_id_str = str(buyer_id) if buyer_id else None

    listing_status = data.get("listingStatus", "active")
    listing_title = str(data.get("listingTitle", "Listing"))
    listing_image_url = str(data.get("listingImageUrl", ""))
    seller_id = str(data.get("sellerId", ""))
    seller_name = str(data.get("sellerName", "Seller"))

    if listing:
        serialized = _serialize_listing_response(listing_id, listing)
        listing_status = serialized.get("status", listing_status)
        listing_title = serialized.get("title", listing_title)
        listing_image_url = serialized.get("imageUrl", listing_image_url)
        seller_id = serialized.get("sellerId", seller_id)
        seller_name = serialized.get("sellerName", seller_name)

    return {
        "id": doc_id,
        "listingId": listing_id,
        "buyerId": buyer_id_str,
        "buyerName": str(data["buyerName"]) if data.get("buyerName") else None,
        "listingTitle": listing_title,
        "listingImageUrl": listing_image_url,
        "listingStatus": listing_status,
        "sellerId": seller_id,
        "sellerName": seller_name,
        "lastMessageText": str(data.get("lastMessageText", "")),
        "lastMessageSenderId": str(data.get("lastMessageSenderId", "")),
        "lastMessageSenderName": str(data.get("lastMessageSenderName", "")),
        "lastMessageAt": _timestamp_ms(data.get("lastMessageAt")),
        "inboxState": inbox_state,
    }


def _fetch_listings_by_ids(db, listing_ids: list[str]) -> dict[str, dict]:
    if not listing_ids:
        return {}

    listings: dict[str, dict] = {}
    for listing_id in listing_ids:
        snapshot = db.collection("listings").document(listing_id).get()
        if snapshot.exists:
            listings[listing_id] = snapshot.to_dict() or {}

    return listings


def _fetch_inbox_states(db, user_id: str, doc_ids: list[str]) -> dict[str, dict]:
    if not doc_ids:
        return {}

    states: dict[str, dict] = {}
    for doc_id in doc_ids:
        snapshot = (
            db.collection("users")
            .document(user_id)
            .collection("inboxState")
            .document(doc_id)
            .get()
        )
        states[doc_id] = _map_inbox_state(doc_id, snapshot.to_dict() if snapshot.exists else None)

    return states


def get_inbox_threads(
    user_id: str,
    *,
    cursor: str | None = None,
    limit: int = DEFAULT_THREADS_PAGE_SIZE,
) -> dict:
    page_size = min(max(limit, 1), MAX_THREADS_PAGE_SIZE)
    db = get_db()

    query = (
        db.collection("users")
        .document(user_id)
        .collection("threads")
        .order_by("lastMessageAt", direction=firestore.Query.DESCENDING)
        .limit(page_size + 1)
    )

    if cursor:
        cursor = cursor.strip()
        cursor_snapshot = (
            db.collection("users")
            .document(user_id)
            .collection("threads")
            .document(cursor)
            .get()
        )
        if not cursor_snapshot.exists:
            raise InboxPipelineError("Invalid cursor", 400)
        query = query.start_after(cursor_snapshot)

    snapshots = list(query.stream())
    has_more = len(snapshots) > page_size
    page_snapshots = snapshots[:page_size]

    thread_doc_ids = [snapshot.id for snapshot in page_snapshots]
    listing_ids = list(
        {
            str((snapshot.to_dict() or {}).get("listingId") or snapshot.id.split("_")[0])
            for snapshot in page_snapshots
        }
    )

    listings_by_id = _fetch_listings_by_ids(db, listing_ids)
    inbox_states = _fetch_inbox_states(db, user_id, thread_doc_ids)

    threads = []
    for snapshot in page_snapshots:
        data = snapshot.to_dict() or {}
        listing_id = str(data.get("listingId") or snapshot.id.split("_")[0])
        threads.append(
            _serialize_thread(
                snapshot.id,
                data,
                listing=listings_by_id.get(listing_id),
                inbox_state=inbox_states.get(snapshot.id, _map_inbox_state(snapshot.id, None)),
            )
        )

    next_cursor = page_snapshots[-1].id if has_more and page_snapshots else None

    return {
        "threads": threads,
        "nextCursor": next_cursor,
        "hasMore": has_more,
    }


def _write_inbox_state(user_id: str, thread_key: str, payload: dict) -> dict:
    listing_id, buyer_id = _parse_thread_key(thread_key)
    db = get_db()

    doc_ref = (
        db.collection("users")
        .document(user_id)
        .collection("inboxState")
        .document(thread_key)
    )

    write_payload = {
        "listingId": listing_id,
        "buyerId": buyer_id,
        **payload,
    }
    doc_ref.set(write_payload, merge=True)

    snapshot = doc_ref.get()
    return _map_inbox_state(thread_key, snapshot.to_dict() if snapshot.exists else write_payload)


def mark_thread_read(user_id: str, thread_key: str) -> dict:
    return _write_inbox_state(
        user_id,
        thread_key,
        {
            "lastReadAt": firestore.SERVER_TIMESTAMP,
            "hasViewed": True,
        },
    )


def archive_thread(user_id: str, thread_key: str) -> dict:
    return _write_inbox_state(
        user_id,
        thread_key,
        {
            "isArchived": True,
            "archivedAt": firestore.SERVER_TIMESTAMP,
        },
    )


def unarchive_thread(user_id: str, thread_key: str) -> dict:
    return _write_inbox_state(
        user_id,
        thread_key,
        {
            "isArchived": False,
            "archivedAt": None,
        },
    )
