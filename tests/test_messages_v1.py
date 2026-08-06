from unittest.mock import MagicMock, patch

import pytest

from services.message_authorization import MessageAuthorizationError
from services.message_pipeline import MessagePipelineError, send_listing_message


LISTING_ID = "listing-1"
SELLER_ID = "seller-1"
BUYER_ID = "buyer-1"


def _listing_snapshot():
    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.to_dict.return_value = {
        "sellerId": SELLER_ID,
        "sellerName": "Sam Seller",
        "title": "Mountain Bike",
        "imageUrl": "/bike.jpg",
        "status": "active",
    }
    return snapshot


def test_v1_send_message_requires_auth(client):
    response = client.post(
        f"/api/v1/listings/{LISTING_ID}/messages",
        json={"text": "Hello", "senderName": "Buyer"},
    )
    assert response.status_code == 401


def test_v1_send_message_success(client):
    with patch("routes.v1.listings.verify_firebase_token", return_value=BUYER_ID):
        with patch("routes.v1.listings.send_listing_message") as mock_send:
            mock_send.return_value = {
                "id": "msg-1",
                "listingId": LISTING_ID,
                "senderId": BUYER_ID,
                "senderName": "Buyer Bob",
                "text": "Is this still available?",
                "recipientId": SELLER_ID,
                "createdAt": 1_700_000_000_000,
            }

            response = client.post(
                f"/api/v1/listings/{LISTING_ID}/messages",
                json={
                    "text": "Is this still available?",
                    "senderName": "Buyer Bob",
                },
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 201
    body = response.get_json()
    assert body["message"]["id"] == "msg-1"
    assert body["message"]["recipientId"] == SELLER_ID
    mock_send.assert_called_once_with(
        BUYER_ID,
        LISTING_ID,
        {"text": "Is this still available?", "senderName": "Buyer Bob"},
    )


def test_v1_send_message_rejects_blocked(client):
    with patch("routes.v1.listings.verify_firebase_token", return_value=BUYER_ID):
        with patch(
            "routes.v1.listings.send_listing_message",
            side_effect=MessagePipelineError(
                "This user is not accepting messages from you",
                403,
            ),
        ):
            response = client.post(
                f"/api/v1/listings/{LISTING_ID}/messages",
                json={"text": "Hello", "senderName": "Buyer"},
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 403
    assert "not accepting messages" in response.get_json()["error"]


def test_send_listing_message_rejects_empty_text():
    with patch("services.message_pipeline.get_db"):
        with pytest.raises(MessagePipelineError, match="cannot be empty"):
            send_listing_message(BUYER_ID, LISTING_ID, {"text": "   ", "senderName": "Bob"})


def test_send_listing_message_rejects_missing_sender_name():
    with patch("services.message_pipeline.get_db"):
        with pytest.raises(MessagePipelineError, match="senderName"):
            send_listing_message(BUYER_ID, LISTING_ID, {"text": "Hi"})


def test_send_listing_message_rejects_text_over_limit():
    with patch("services.message_pipeline.get_db"):
        with pytest.raises(MessagePipelineError, match="1000"):
            send_listing_message(
                BUYER_ID,
                LISTING_ID,
                {"text": "x" * 1001, "senderName": "Bob"},
            )


def test_send_listing_message_happy_path():
    mock_db = MagicMock()
    listing_snapshot = _listing_snapshot()

    message_doc = MagicMock()
    message_doc.id = "msg-1"
    created_snapshot = MagicMock()
    created_snapshot.to_dict.return_value = {
        "senderId": BUYER_ID,
        "senderName": "Buyer Bob",
        "text": "Hello",
        "recipientId": SELLER_ID,
        "createdAt": MagicMock(timestamp=lambda: 1_700_000_000.0),
    }
    message_doc.get.return_value = created_snapshot

    messages_collection = MagicMock()
    messages_collection.document.return_value = message_doc

    listing_doc = MagicMock()
    listing_doc.get.return_value = listing_snapshot
    listing_doc.collection.return_value = messages_collection

    listings_collection = MagicMock()
    listings_collection.document.return_value = listing_doc

    mock_db.collection.return_value = listings_collection

    with patch("services.message_pipeline.get_db", return_value=mock_db):
        with patch("services.message_authorization.is_user_blocked", return_value=False):
            with patch("services.message_pipeline._sync_message_threads") as mock_sync:
                with patch("services.message_pipeline._create_message_notification") as mock_notify:
                    result = send_listing_message(
                        BUYER_ID,
                        LISTING_ID,
                        {"text": "Hello", "senderName": "Buyer Bob"},
                    )

    assert result["id"] == "msg-1"
    assert result["senderId"] == BUYER_ID
    assert result["recipientId"] == SELLER_ID
    message_doc.set.assert_called_once()
    mock_sync.assert_called_once()
    mock_notify.assert_called_once()


def test_send_listing_message_listing_not_found():
    mock_db = MagicMock()
    listing_snapshot = MagicMock()
    listing_snapshot.exists = False
    mock_db.collection.return_value.document.return_value.get.return_value = listing_snapshot

    with patch("services.message_pipeline.get_db", return_value=mock_db):
        with pytest.raises(MessagePipelineError, match="not found"):
            send_listing_message(
                BUYER_ID,
                "missing",
                {"text": "Hello", "senderName": "Bob"},
            )


def test_assert_can_send_message_blocked():
    from services.message_authorization import assert_can_send_message

    listing = {"sellerId": SELLER_ID}
    with patch(
        "services.message_authorization.is_user_blocked",
        return_value=True,
    ):
        with pytest.raises(MessageAuthorizationError, match="not accepting"):
            assert_can_send_message(BUYER_ID, listing, SELLER_ID)
