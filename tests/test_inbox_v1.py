from unittest.mock import MagicMock, patch

from services.inbox_pipeline import (
    InboxPipelineError,
    archive_thread,
    get_inbox_threads,
    mark_thread_read,
    unarchive_thread,
)

USER_ID = "user-1"
LISTING_ID = "listing-1"
BUYER_ID = "buyer-1"
THREAD_KEY = f"{LISTING_ID}_{BUYER_ID}"


def test_v1_inbox_threads_requires_auth(client):
    response = client.get("/api/v1/inbox/threads")
    assert response.status_code == 401


def test_v1_inbox_threads_success(client):
    with patch("routes.v1.inbox.verify_firebase_token", return_value=USER_ID):
        with patch("routes.v1.inbox.get_inbox_threads") as mock_get:
            mock_get.return_value = {
                "threads": [
                    {
                        "id": THREAD_KEY,
                        "listingId": LISTING_ID,
                        "buyerId": BUYER_ID,
                        "listingTitle": "Mountain Bike",
                        "listingImageUrl": "/bike.jpg",
                        "listingStatus": "active",
                        "sellerId": "seller-1",
                        "sellerName": "Sam",
                        "lastMessageText": "Hello",
                        "lastMessageSenderId": BUYER_ID,
                        "lastMessageSenderName": "Buyer Bob",
                        "lastMessageAt": 1_700_000_000_000,
                        "inboxState": {
                            "listingId": LISTING_ID,
                            "buyerId": BUYER_ID,
                            "hasViewed": False,
                            "isArchived": False,
                            "lastReadAt": None,
                            "archivedAt": None,
                        },
                    }
                ],
                "nextCursor": None,
                "hasMore": False,
            }

            response = client.get(
                "/api/v1/inbox/threads?limit=10",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200
    body = response.get_json()
    assert len(body["threads"]) == 1
    assert body["threads"][0]["id"] == THREAD_KEY
    mock_get.assert_called_once_with(USER_ID, cursor=None, limit=10)


def test_v1_inbox_threads_with_cursor(client):
    with patch("routes.v1.inbox.verify_firebase_token", return_value=USER_ID):
        with patch("routes.v1.inbox.get_inbox_threads") as mock_get:
            mock_get.return_value = {"threads": [], "nextCursor": None, "hasMore": False}

            response = client.get(
                f"/api/v1/inbox/threads?cursor={THREAD_KEY}",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200
    mock_get.assert_called_once_with(USER_ID, cursor=THREAD_KEY, limit=30)


def test_v1_inbox_read_requires_auth(client):
    response = client.post(f"/api/v1/inbox/threads/{THREAD_KEY}/read")
    assert response.status_code == 401


def test_v1_inbox_read_success(client):
    with patch("routes.v1.inbox.verify_firebase_token", return_value=USER_ID):
        with patch("routes.v1.inbox.mark_thread_read") as mock_read:
            mock_read.return_value = {
                "listingId": LISTING_ID,
                "buyerId": BUYER_ID,
                "hasViewed": True,
                "isArchived": False,
                "lastReadAt": 1_700_000_000_000,
                "archivedAt": None,
            }

            response = client.post(
                f"/api/v1/inbox/threads/{THREAD_KEY}/read",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200
    assert response.get_json()["inboxState"]["hasViewed"] is True
    mock_read.assert_called_once_with(USER_ID, THREAD_KEY)


def test_v1_inbox_archive_success(client):
    with patch("routes.v1.inbox.verify_firebase_token", return_value=USER_ID):
        with patch("routes.v1.inbox.archive_thread") as mock_archive:
            mock_archive.return_value = {
                "listingId": LISTING_ID,
                "buyerId": BUYER_ID,
                "hasViewed": True,
                "isArchived": True,
                "lastReadAt": 1_700_000_000_000,
                "archivedAt": 1_700_000_100_000,
            }

            response = client.post(
                f"/api/v1/inbox/threads/{THREAD_KEY}/archive",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200
    assert response.get_json()["inboxState"]["isArchived"] is True
    mock_archive.assert_called_once_with(USER_ID, THREAD_KEY)


def test_v1_inbox_unarchive_success(client):
    with patch("routes.v1.inbox.verify_firebase_token", return_value=USER_ID):
        with patch("routes.v1.inbox.unarchive_thread") as mock_unarchive:
            mock_unarchive.return_value = {
                "listingId": LISTING_ID,
                "buyerId": BUYER_ID,
                "hasViewed": True,
                "isArchived": False,
                "lastReadAt": 1_700_000_000_000,
                "archivedAt": None,
            }

            response = client.post(
                f"/api/v1/inbox/threads/{THREAD_KEY}/unarchive",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200
    assert response.get_json()["inboxState"]["isArchived"] is False
    mock_unarchive.assert_called_once_with(USER_ID, THREAD_KEY)


def test_v1_browse_listings_public(client):
    with patch("routes.v1.listings.browse_listings") as mock_browse:
        mock_browse.return_value = {
            "listings": [{"id": LISTING_ID, "title": "Bike", "status": "active"}],
            "nextCursor": None,
            "hasMore": False,
        }

        response = client.get("/api/v1/listings?communityId=all&limit=12")

    assert response.status_code == 200
    assert response.get_json()["listings"][0]["id"] == LISTING_ID
    mock_browse.assert_called_once()


def test_get_inbox_threads_enriches_listing():
    mock_db = MagicMock()

    thread_snapshot = MagicMock()
    thread_snapshot.id = THREAD_KEY
    thread_snapshot.to_dict.return_value = {
        "listingId": LISTING_ID,
        "buyerId": BUYER_ID,
        "listingTitle": "Stale title",
        "listingImageUrl": "",
        "listingStatus": "active",
        "sellerId": "seller-1",
        "sellerName": "Sam",
        "lastMessageText": "Hi",
        "lastMessageSenderId": BUYER_ID,
        "lastMessageSenderName": "Bob",
        "lastMessageAt": MagicMock(timestamp=lambda: 1_700_000_000.0),
    }

    threads_query = MagicMock()
    threads_query.order_by.return_value = threads_query
    threads_query.limit.return_value = threads_query
    threads_query.stream.return_value = [thread_snapshot]

    listing_snapshot = MagicMock()
    listing_snapshot.exists = True
    listing_snapshot.to_dict.return_value = {
        "title": "Fresh Bike",
        "imageUrl": "/bike.jpg",
        "status": "active",
        "sellerId": "seller-1",
        "sellerName": "Sam Seller",
    }

    inbox_snapshot = MagicMock()
    inbox_snapshot.exists = False
    inbox_snapshot.to_dict.return_value = None

    users_doc = MagicMock()
    threads_collection = MagicMock()
    threads_collection.order_by.return_value = threads_query
    users_doc.collection.return_value = threads_collection

    inbox_doc = MagicMock()
    inbox_doc.get.return_value = inbox_snapshot
    inbox_collection = MagicMock()
    inbox_collection.document.return_value = inbox_doc

    def collection_side_effect(name):
        if name == "users":
            users_collection = MagicMock()
            users_collection.document.return_value = users_doc
            return users_collection
        if name == "listings":
            listings_collection = MagicMock()
            listings_collection.document.return_value.get.return_value = listing_snapshot
            return listings_collection
        return MagicMock()

    users_doc.collection.side_effect = lambda sub: (
        threads_collection if sub == "threads" else inbox_collection
    )
    mock_db.collection.side_effect = collection_side_effect

    with patch("services.inbox_pipeline.get_db", return_value=mock_db):
        result = get_inbox_threads(USER_ID)

    assert len(result["threads"]) == 1
    assert result["threads"][0]["listingTitle"] == "Fresh Bike"
    assert result["threads"][0]["listingImageUrl"] == "/bike.jpg"


def test_mark_thread_read_invalid_key():
    with patch("services.inbox_pipeline.get_db"):
        try:
            mark_thread_read(USER_ID, "   ")
            assert False, "Expected InboxPipelineError"
        except InboxPipelineError as exc:
            assert exc.status_code == 400


def test_archive_thread_writes_state():
    mock_db = MagicMock()
    inbox_doc = MagicMock()
    written = {}

    def capture_set(payload, merge=False):
        written.update(payload)

    inbox_doc.set = capture_set
    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.to_dict.return_value = {
        "listingId": LISTING_ID,
        "buyerId": BUYER_ID,
        "isArchived": True,
        "archivedAt": MagicMock(timestamp=lambda: 1_700_000_100.0),
    }
    inbox_doc.get.return_value = snapshot

    inbox_collection = MagicMock()
    inbox_collection.document.return_value = inbox_doc
    users_doc = MagicMock()
    users_doc.collection.return_value = inbox_collection
    users_collection = MagicMock()
    users_collection.document.return_value = users_doc
    mock_db.collection.return_value = users_collection

    with patch("services.inbox_pipeline.get_db", return_value=mock_db):
        result = archive_thread(USER_ID, THREAD_KEY)

    assert written["isArchived"] is True
    assert result["listingId"] == LISTING_ID
    assert result["buyerId"] == BUYER_ID
