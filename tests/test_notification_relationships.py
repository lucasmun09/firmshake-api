from unittest.mock import MagicMock, patch

import pytest

from services.notification_relationships import RelationshipError, verify_push_relationship


def test_verify_push_relationship_blocks_self():
    verify_push_relationship("user-1", "user-1", "message", "listing-1")


def test_verify_push_relationship_requires_listing_context_for_message():
    with patch("services.notification_relationships.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        listing_snapshot = MagicMock()
        listing_snapshot.exists = True
        listing_snapshot.to_dict.return_value = {"sellerId": "seller-1"}

        blocked_snapshot = MagicMock()
        blocked_snapshot.exists = False

        empty_stream = iter([])

        def collection(name):
            collection_mock = MagicMock()
            if name == "listings":
                doc_mock = MagicMock()
                doc_mock.get.return_value = listing_snapshot
                doc_mock.collection.return_value.where.return_value.limit.return_value.stream.return_value = empty_stream
                collection_mock.document.return_value = doc_mock
            elif name == "users":
                user_doc = MagicMock()
                user_doc.collection.return_value.document.return_value.get.return_value = blocked_snapshot
                collection_mock.document.return_value = user_doc
            elif name == "agreements":
                collection_mock.where.return_value.where.return_value.limit.return_value.stream.return_value = empty_stream
            return collection_mock

        mock_db.collection.side_effect = collection

        with pytest.raises(RelationshipError, match="listing context"):
            verify_push_relationship("actor-1", "recipient-1", "message", "listing-1")
