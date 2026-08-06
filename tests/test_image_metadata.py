from unittest.mock import MagicMock, patch

import pytest

from services.image_metadata import (
    ImageAccessError,
    ImageNotFoundError,
    assert_can_view_image,
    assert_can_view_image_public,
    create_image_record,
    get_image_record,
)
from tests.conftest import IMAGE_ID


def _mock_snapshot(exists: bool, data: dict | None = None):
    snapshot = MagicMock()
    snapshot.exists = exists
    snapshot.to_dict.return_value = data or {}
    return snapshot


@patch("services.image_metadata.get_db")
def test_create_image_record_writes_firestore(mock_get_db):
    mock_doc = MagicMock()
    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc
    mock_get_db.return_value.collection.return_value = mock_collection

    record = create_image_record(
        image_id=IMAGE_ID,
        owner_id="seller-1",
        community_ids=["church"],
        storage_key="listing-images/seller-1/abc.jpg",
        content_type="image/jpeg",
    )

    mock_doc.set.assert_called_once()
    assert record["imageId"] == IMAGE_ID
    assert record["ownerId"] == "seller-1"
    assert record["communityIds"] == ["church"]


@patch("services.image_metadata.get_db")
def test_get_image_record_raises_when_missing(mock_get_db):
    mock_doc = MagicMock()
    mock_doc.get.return_value = _mock_snapshot(False)
    mock_get_db.return_value.collection.return_value.document.return_value = mock_doc

    with pytest.raises(ImageNotFoundError):
        get_image_record(IMAGE_ID)


@patch("services.image_metadata.get_user_community_ids")
@patch("services.image_metadata.get_image_record")
def test_assert_can_view_image_allows_owner(mock_get_record, mock_get_user_communities):
    mock_get_record.return_value = {
        "imageId": IMAGE_ID,
        "ownerId": "seller-1",
        "communityIds": ["private"],
        "storageKey": "key",
        "contentType": "image/jpeg",
    }

    record = assert_can_view_image("seller-1", IMAGE_ID)

    assert record["imageId"] == IMAGE_ID
    mock_get_user_communities.assert_not_called()


@patch("services.image_metadata.get_user_community_ids")
@patch("services.image_metadata.get_image_record")
def test_assert_can_view_image_denies_non_member(mock_get_record, mock_get_user_communities):
    mock_get_record.return_value = {
        "imageId": IMAGE_ID,
        "ownerId": "seller-1",
        "communityIds": ["church"],
        "storageKey": "key",
        "contentType": "image/jpeg",
    }
    mock_get_user_communities.return_value = ["school"]

    with pytest.raises(ImageAccessError):
        assert_can_view_image("buyer-1", IMAGE_ID)


@patch("services.image_metadata.is_image_on_active_listing", return_value=False)
@patch("services.image_metadata.get_image_record")
def test_assert_can_view_image_public_allows_all_community(mock_get_record, _mock_listing):
    mock_get_record.return_value = {
        "imageId": IMAGE_ID,
        "ownerId": "seller-1",
        "communityIds": ["all"],
        "storageKey": "key",
        "contentType": "image/jpeg",
    }

    record = assert_can_view_image_public(IMAGE_ID)

    assert record["imageId"] == IMAGE_ID


@patch("services.image_metadata.is_image_on_active_listing", return_value=True)
@patch("services.image_metadata.get_image_record")
def test_assert_can_view_image_public_allows_active_listing_image(mock_get_record, _mock_listing):
    mock_get_record.return_value = {
        "imageId": IMAGE_ID,
        "ownerId": "seller-1",
        "communityIds": ["church"],
        "storageKey": "key",
        "contentType": "image/jpeg",
    }

    record = assert_can_view_image_public(IMAGE_ID)

    assert record["imageId"] == IMAGE_ID


@patch("services.image_metadata.is_image_on_active_listing", return_value=False)
@patch("services.image_metadata.get_image_record")
def test_assert_can_view_image_public_denies_private_image(mock_get_record, _mock_listing):
    mock_get_record.return_value = {
        "imageId": IMAGE_ID,
        "ownerId": "seller-1",
        "communityIds": ["church"],
        "storageKey": "key",
        "contentType": "image/jpeg",
    }

    with pytest.raises(ImageAccessError):
        assert_can_view_image_public(IMAGE_ID)
