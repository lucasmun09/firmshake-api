from unittest.mock import MagicMock, patch

import pytest

from services.agreement_authorization import (
    AgreementAuthorizationError,
    assert_can_accept,
    assert_can_propose,
    get_block_cancel_action,
)
from services.agreement_pipeline import AgreementPipelineError, propose_agreement, cancel_agreement


LISTING_ID = "listing-1"
AGREEMENT_ID = "agreement-1"
SELLER_ID = "seller-1"
BUYER_ID = "buyer-1"


def _listing_snapshot():
    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.to_dict.return_value = {
        "sellerId": SELLER_ID,
        "title": "Mountain Bike",
        "price": 200,
        "status": "active",
    }
    return snapshot


def _agreement_data(status="proposed"):
    return {
        "listingId": LISTING_ID,
        "buyerId": BUYER_ID,
        "buyerName": "Buyer Bob",
        "sellerId": SELLER_ID,
        "price": 200,
        "meetupLat": 37.77,
        "meetupLng": -122.42,
        "meetupAt": MagicMock(),
        "depositAmount": 10,
        "status": status,
    }


# --- Route tests ---


def test_v1_get_agreement_requires_auth(client):
    response = client.get(f"/api/v1/agreements/{AGREEMENT_ID}")
    assert response.status_code == 401


def test_v1_get_agreement_success(client):
    with patch("routes.v1.agreements.verify_firebase_token", return_value=BUYER_ID):
        with patch("routes.v1.agreements.get_agreement") as mock_get:
            mock_get.return_value = {"id": AGREEMENT_ID, "status": "proposed"}
            response = client.get(
                f"/api/v1/agreements/{AGREEMENT_ID}",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200
    assert response.get_json()["agreement"]["id"] == AGREEMENT_ID


def test_v1_list_agreements_requires_role(client):
    with patch("routes.v1.agreements.verify_firebase_token", return_value=BUYER_ID):
        response = client.get(
            "/api/v1/agreements",
            headers={"Authorization": "Bearer fake-token"},
        )
    assert response.status_code == 400


def test_v1_list_agreements_success(client):
    with patch("routes.v1.agreements.verify_firebase_token", return_value=BUYER_ID):
        with patch("routes.v1.agreements.list_agreements") as mock_list:
            mock_list.return_value = [{"id": AGREEMENT_ID, "status": "proposed"}]
            response = client.get(
                "/api/v1/agreements?role=buyer&listingId=listing-1",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200
    assert len(response.get_json()["agreements"]) == 1
    mock_list.assert_called_once_with(BUYER_ID, role="buyer", listing_id="listing-1")


def test_v1_propose_agreement_success(client):
    with patch("routes.v1.agreements.verify_firebase_token", return_value=BUYER_ID):
        with patch("routes.v1.agreements.propose_agreement") as mock_propose:
            mock_propose.return_value = {"id": "new-agreement", "status": "proposed"}
            response = client.post(
                "/api/v1/agreements",
                json={
                    "listingId": LISTING_ID,
                    "buyerId": BUYER_ID,
                    "buyerName": "Buyer Bob",
                    "sellerId": SELLER_ID,
                    "price": 200,
                    "meetupLat": 37.77,
                    "meetupLng": -122.42,
                    "meetupAt": "2026-08-10T18:00:00Z",
                    "depositAmount": 10,
                },
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 201
    assert response.get_json()["agreement"]["status"] == "proposed"


def test_v1_accept_agreement_success(client):
    with patch("routes.v1.agreements.verify_firebase_token", return_value=SELLER_ID):
        with patch("routes.v1.agreements.accept_agreement") as mock_accept:
            mock_accept.return_value = {"id": AGREEMENT_ID, "status": "accepted"}
            response = client.post(
                f"/api/v1/agreements/{AGREEMENT_ID}/accept",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200
    assert response.get_json()["agreement"]["status"] == "accepted"


def test_v1_decline_agreement_success(client):
    with patch("routes.v1.agreements.verify_firebase_token", return_value=SELLER_ID):
        with patch("routes.v1.agreements.decline_agreement") as mock_decline:
            mock_decline.return_value = {"id": AGREEMENT_ID, "status": "cancelled"}
            response = client.post(
                f"/api/v1/agreements/{AGREEMENT_ID}/decline",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200
    assert response.get_json()["agreement"]["status"] == "cancelled"


def test_v1_cancel_agreement_success(client):
    with patch("routes.v1.agreements.verify_firebase_token", return_value=BUYER_ID):
        with patch("routes.v1.agreements.cancel_agreement") as mock_cancel:
            mock_cancel.return_value = {"id": AGREEMENT_ID, "status": "cancelled"}
            response = client.post(
                f"/api/v1/agreements/{AGREEMENT_ID}/cancel",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200


def test_v1_deposit_mock_mode(client):
    with patch("routes.v1.agreements.verify_firebase_token", return_value=BUYER_ID):
        with patch("routes.v1.agreements.create_deposit") as mock_deposit:
            mock_deposit.return_value = {
                "mode": "mock",
                "agreement": {"id": AGREEMENT_ID, "status": "deposit_paid"},
            }
            response = client.post(
                f"/api/v1/agreements/{AGREEMENT_ID}/deposit",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200
    assert response.get_json()["mode"] == "mock"


def test_v1_en_route_success(client):
    with patch("routes.v1.agreements.verify_firebase_token", return_value=BUYER_ID):
        with patch("routes.v1.agreements.start_en_route") as mock_en_route:
            mock_en_route.return_value = {"id": AGREEMENT_ID, "status": "en_route"}
            response = client.post(
                f"/api/v1/agreements/{AGREEMENT_ID}/en-route",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200
    assert response.get_json()["agreement"]["status"] == "en_route"


def test_v1_location_requires_coords(client):
    with patch("routes.v1.agreements.verify_firebase_token", return_value=BUYER_ID):
        response = client.post(
            f"/api/v1/agreements/{AGREEMENT_ID}/location",
            json={},
            headers={"Authorization": "Bearer fake-token"},
        )
    assert response.status_code == 400


def test_v1_stripe_webhook_stub(client):
    with patch("routes.v1.agreements.is_stripe_configured", return_value=False):
        response = client.post("/api/v1/webhooks/stripe", data=b"{}")
    assert response.status_code == 200
    assert response.get_json()["mode"] == "stub"


# --- Service unit tests ---


def test_assert_can_accept_rejects_buyer():
    agreement = _agreement_data("proposed")
    with pytest.raises(AgreementAuthorizationError, match="seller"):
        assert_can_accept(BUYER_ID, agreement)


def test_get_block_cancel_action_buyer_proposed():
    agreement = _agreement_data("proposed")
    assert get_block_cancel_action(agreement, BUYER_ID) == "buyer-cancel-proposed"


def test_get_block_cancel_action_seller_proposed():
    agreement = _agreement_data("proposed")
    assert get_block_cancel_action(agreement, SELLER_ID) == "seller-decline-proposed"


def test_get_block_cancel_action_direct_cancel():
    agreement = _agreement_data("accepted")
    assert get_block_cancel_action(agreement, BUYER_ID) == "direct-cancel"


def test_propose_rejects_deposit_under_minimum():
    listing = {"sellerId": SELLER_ID, "price": 200}
    payload = {"buyerId": BUYER_ID, "sellerId": SELLER_ID, "depositAmount": 5}
    with pytest.raises(AgreementAuthorizationError, match="at least"):
        assert_can_propose(BUYER_ID, listing, payload)


def test_propose_agreement_rejects_missing_listing():
    mock_db = MagicMock()
    listing_snapshot = MagicMock()
    listing_snapshot.exists = False
    mock_db.collection.return_value.document.return_value.get.return_value = listing_snapshot

    with patch("services.agreement_pipeline.get_db", return_value=mock_db):
        with pytest.raises(AgreementPipelineError, match="not found"):
            propose_agreement(
                BUYER_ID,
                {
                    "listingId": "missing",
                    "buyerName": "Bob",
                    "meetupAt": "2026-08-10T18:00:00Z",
                    "depositAmount": 10,
                },
            )


def test_cancel_agreement_buyer_proposed_only():
    mock_db = MagicMock()
    agreement_snapshot = MagicMock()
    agreement_snapshot.exists = True
    agreement_snapshot.to_dict.return_value = _agreement_data("proposed")

    doc_ref = MagicMock()
    doc_ref.get.return_value = agreement_snapshot

    mock_db.collection.return_value.document.return_value = doc_ref

    with patch("services.agreement_pipeline.get_db", return_value=mock_db):
        result = cancel_agreement(BUYER_ID, AGREEMENT_ID)

    assert result["status"] == "cancelled"
    doc_ref.set.assert_called_once()


def test_cancel_agreement_rejects_seller_on_proposed():
    mock_db = MagicMock()
    agreement_snapshot = MagicMock()
    agreement_snapshot.exists = True
    agreement_snapshot.to_dict.return_value = _agreement_data("proposed")

    doc_ref = MagicMock()
    doc_ref.get.return_value = agreement_snapshot
    mock_db.collection.return_value.document.return_value = doc_ref

    with patch("services.agreement_pipeline.get_db", return_value=mock_db):
        with pytest.raises(AgreementPipelineError, match="cancel your own"):
            cancel_agreement(SELLER_ID, AGREEMENT_ID)
