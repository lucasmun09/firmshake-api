"""
Marketplace integration chain without payments:
browse/summary → create listing → send message → inbox mark-read.

These are Flask client + mocked service contracts (no Stripe / deposit routes).
"""

from unittest.mock import patch


LISTING_ID = "listing-bike-1"
SELLER_ID = "seller-1"
BUYER_ID = "buyer-1"


def _created_listing():
    return {
        "id": LISTING_ID,
        "title": "Mountain Bike",
        "description": "Light trail bike",
        "price": 250,
        "imageUrls": ["/bike.jpg"],
        "imageUrl": "/bike.jpg",
        "sellerId": SELLER_ID,
        "sellerName": "Sam Seller",
        "communityIds": ["all"],
        "primaryCategoryId": "sports",
        "categoryIds": ["sports"],
        "status": "active",
        "createdAt": 1_700_000_000_000,
    }


def test_marketplace_chain_browse_create_message_inbox_without_payments(client):
    # 1) Guest-accessible browse summary returns summary-shaped listings.
    with patch("routes.v1.browse.browse_summary_search") as mock_summary:
        mock_summary.return_value = {
            "listings": [
                {
                    "id": LISTING_ID,
                    "title": "Mountain Bike",
                    "price": 250,
                    "imageUrl": "/bike.jpg",
                    "status": "active",
                    "sellerId": SELLER_ID,
                    "communityIds": ["all"],
                    "primaryCategoryId": "sports",
                }
            ],
            "total": 1,
            "page": 1,
            "pageSize": 24,
            "hasMore": False,
            "engine": "typesense",
            "pinGroups": [],
        }
        browse = client.post(
            "/api/v1/browse/summary",
            json={"communityId": "all", "page": 1, "pageSize": 24},
        )

    assert browse.status_code == 200
    browse_body = browse.get_json()
    assert browse_body["listings"][0]["id"] == LISTING_ID
    assert "description" not in browse_body["listings"][0]
    assert "paymentIntentId" not in browse_body["listings"][0]
    assert "depositAmount" not in browse_body["listings"][0]

    # 2) Authenticated seller creates a listing (no payment fields required).
    with patch("routes.v1.listings.verify_firebase_token", return_value=SELLER_ID):
        with patch("routes.v1.listings.create_listing") as mock_create:
            mock_create.return_value = _created_listing()
            create = client.post(
                "/api/v1/listings",
                json={
                    "title": "Mountain Bike",
                    "description": "Light trail bike",
                    "price": 250,
                    "imageUrls": ["/bike.jpg"],
                    "sellerName": "Sam Seller",
                    "communityIds": ["all"],
                    "primaryCategoryId": "sports",
                    "categoryIds": ["sports"],
                },
                headers={"Authorization": "Bearer fake-token"},
            )

    assert create.status_code == 201
    listing = create.get_json()
    assert listing["id"] == LISTING_ID
    assert listing["status"] == "active"
    assert "stripe" not in str(listing).lower()

    # 3) Buyer sends a message (marketplace messaging, not deposits).
    with patch("routes.v1.listings.verify_firebase_token", return_value=BUYER_ID):
        with patch("routes.v1.listings.send_listing_message") as mock_send:
            mock_send.return_value = {
                "id": "msg-1",
                "listingId": LISTING_ID,
                "senderId": BUYER_ID,
                "senderName": "Buyer Bob",
                "text": "Is this still available?",
                "recipientId": SELLER_ID,
                "createdAt": 1_700_000_100_000,
            }
            message = client.post(
                f"/api/v1/listings/{LISTING_ID}/messages",
                json={"text": "Is this still available?", "senderName": "Buyer Bob"},
                headers={"Authorization": "Bearer fake-token"},
            )

    assert message.status_code == 201
    assert message.get_json()["message"]["recipientId"] == SELLER_ID

    # 4) Inbox mark-read stays available without payment processor.
    thread_key = f"{LISTING_ID}_{BUYER_ID}"
    with patch("routes.v1.inbox.verify_firebase_token", return_value=SELLER_ID):
        with patch("routes.v1.inbox.mark_thread_read") as mock_read:
            mock_read.return_value = {
                "listingId": LISTING_ID,
                "buyerId": BUYER_ID,
                "hasViewed": True,
                "isArchived": False,
                "lastReadAt": 1_700_000_200_000,
                "archivedAt": None,
            }
            read = client.post(
                f"/api/v1/inbox/threads/{thread_key}/read",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert read.status_code == 200
    assert read.get_json()["inboxState"]["hasViewed"] is True


def test_marketplace_payment_routes_remain_disabled_or_absent(client):
    """Payments must not be required for the core marketplace chain."""
    for path in (
        "/api/v1/payments/checkout",
        "/api/v1/payments/intent",
        "/api/v1/deposits/create",
        "/api/stripe/webhook",
    ):
        response = client.post(path, json={})
        assert response.status_code in (404, 405, 501, 503), path
