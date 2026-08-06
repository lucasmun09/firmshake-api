from unittest.mock import MagicMock, patch

import pytest

from services.auth import AuthError


def test_listings_sync_requires_auth(client):
    response = client.post("/api/listings/sync", json={"id": "listing-1"})
    assert response.status_code == 401


def test_listings_sync_rejects_unauthorized_user(client):
    with patch("routes.listings.verify_firebase_token", return_value="other-user"):
        with patch("routes.listings.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            listing_snapshot = MagicMock()
            listing_snapshot.exists = True
            listing_snapshot.to_dict.return_value = {
                "sellerId": "seller-1",
                "communityIds": ["all"],
                "status": "active",
            }
            mock_db.collection.return_value.document.return_value.get.return_value = listing_snapshot

            profile_snapshot = MagicMock()
            profile_snapshot.exists = True
            profile_snapshot.to_dict.return_value = {"moderatorCommunityIds": []}
            mock_db.collection.return_value.document.return_value.get.side_effect = [
                listing_snapshot,
                profile_snapshot,
            ]

            response = client.post(
                "/api/listings/sync",
                json={"id": "listing-1", "title": "Test"},
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 403


def test_listings_sync_allows_seller(client):
    with patch("routes.listings.verify_firebase_token", return_value="seller-1"):
        with patch("routes.listings.get_db") as mock_get_db:
            with patch("routes.listings.TypesenseClient") as mock_typesense:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db

                listing_snapshot = MagicMock()
                listing_snapshot.exists = True
                listing_snapshot.to_dict.return_value = {
                    "sellerId": "seller-1",
                    "communityIds": ["all"],
                    "status": "active",
                }

                profile_snapshot = MagicMock()
                profile_snapshot.exists = True
                profile_snapshot.to_dict.return_value = {"moderatorCommunityIds": []}

                listing_doc = MagicMock()
                listing_doc.get.side_effect = [listing_snapshot, profile_snapshot]
                mock_db.collection.return_value.document.return_value = listing_doc

                typesense_instance = MagicMock()
                typesense_instance.enabled = False
                mock_typesense.return_value = typesense_instance

                response = client.post(
                    "/api/listings/sync",
                    json={"id": "listing-1", "title": "Test"},
                    headers={"Authorization": "Bearer fake-token"},
                )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True


def test_v1_create_listing_requires_auth(client):
    response = client.post("/api/v1/listings", json={"title": "Test"})
    assert response.status_code == 401


def test_v1_create_listing_success(client):
    with patch("routes.v1.listings.verify_firebase_token", return_value="seller-1"):
        with patch("routes.v1.listings.create_listing") as mock_create:
            mock_create.return_value = {
                "id": "listing-1",
                "title": "Mountain Bike",
                "description": "Like new",
                "price": 400,
                "imageUrls": ["/bike.jpg"],
                "imageUrl": "/bike.jpg",
                "sellerId": "seller-1",
                "sellerName": "Sam",
                "communityIds": ["all"],
                "primaryCategoryId": "sports",
                "categoryIds": ["sports"],
                "status": "active",
            }

            response = client.post(
                "/api/v1/listings",
                json={
                    "title": "Mountain Bike",
                    "description": "Like new",
                    "price": 400,
                    "imageUrls": ["/bike.jpg"],
                    "sellerName": "Sam",
                },
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 201
    assert response.get_json()["id"] == "listing-1"


def test_notifications_push_requires_relationship(client):
    with patch("routes.notifications.verify_firebase_token", return_value="actor-1"):
        with patch(
            "routes.notifications.verify_push_relationship",
            side_effect=__import__(
                "services.notification_relationships", fromlist=["RelationshipError"]
            ).RelationshipError("Users do not share a listing context"),
        ):
            response = client.post(
                "/api/notifications/push",
                json={
                    "recipientId": "recipient-1",
                    "title": "Hi",
                    "body": "Hello",
                    "type": "message",
                    "listingId": "listing-1",
                },
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 403


def test_response_includes_request_id(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Request-Id")
