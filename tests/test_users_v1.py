from unittest.mock import MagicMock, patch

import pytest

from services.authorization import AuthorizationError
from services.block_pipeline import block_user
from services.user_pipeline import UserPipelineError, find_user_by_email, update_current_user


def test_get_me_requires_auth(client):
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401


def test_get_me_success(client):
    with patch("routes.v1.users.verify_firebase_token", return_value="user-1"):
        with patch("routes.v1.users.get_current_user") as mock_get:
            mock_get.return_value = {
                "uid": "user-1",
                "email": "user@example.com",
                "displayName": "Test User",
                "communityIds": ["all"],
            }
            response = client.get(
                "/api/v1/users/me",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200
    assert response.get_json()["uid"] == "user-1"


def test_patch_me_updates_profile(client):
    with patch("routes.v1.users.verify_firebase_token", return_value="user-1"):
        with patch("routes.v1.users.update_current_user") as mock_update:
            mock_update.return_value = {
                "uid": "user-1",
                "firstName": "Jane",
                "lastName": "Doe",
                "displayName": "Jane Doe",
            }
            response = client.patch(
                "/api/v1/users/me",
                json={"firstName": "Jane", "lastName": "Doe"},
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200
    assert response.get_json()["displayName"] == "Jane Doe"


def test_get_public_profile(client):
    with patch("routes.v1.users.verify_firebase_token", return_value="viewer-1"):
        with patch("routes.v1.users.get_public_user") as mock_get:
            mock_get.return_value = {
                "uid": "user-2",
                "displayName": "Public User",
                "photoUrl": "/api/images/abc",
            }
            response = client.get(
                "/api/v1/users/user-2/public",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200
    body = response.get_json()
    assert body["displayName"] == "Public User"
    assert "email" not in body


def test_by_email_requires_moderator(client):
    with patch("routes.v1.users.verify_firebase_token", return_value="user-1"):
        with patch(
            "routes.v1.users.find_user_by_email",
            side_effect=AuthorizationError("You do not have permission to look up users by email"),
        ):
            response = client.get(
                "/api/v1/users/by-email?email=target@example.com",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 403


def test_by_email_success(client):
    with patch("routes.v1.users.verify_firebase_token", return_value="mod-1"):
        with patch("routes.v1.users.find_user_by_email") as mock_find:
            mock_find.return_value = {
                "uid": "target-1",
                "email": "target@example.com",
                "displayName": "Target User",
            }
            response = client.get(
                "/api/v1/users/by-email?email=target@example.com",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200
    assert response.get_json()["uid"] == "target-1"


def test_block_user_requires_auth(client):
    response = client.post("/api/v1/users/me/blocks/blocked-1")
    assert response.status_code == 401


def test_block_user_success(client):
    with patch("routes.v1.blocks.verify_firebase_token", return_value="blocker-1"):
        with patch("routes.v1.blocks.block_user") as mock_block:
            mock_block.return_value = {"blockedUserId": "blocked-1", "blockedAt": 123}
            response = client.post(
                "/api/v1/users/me/blocks/blocked-1",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 201
    assert response.get_json()["blockedUserId"] == "blocked-1"


def test_unblock_user_success(client):
    with patch("routes.v1.blocks.verify_firebase_token", return_value="blocker-1"):
        with patch("routes.v1.blocks.unblock_user") as mock_unblock:
            response = client.delete(
                "/api/v1/users/me/blocks/blocked-1",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200
    mock_unblock.assert_called_once_with("blocker-1", "blocked-1")


def test_list_communities(client):
    with patch("routes.v1.communities.list_communities") as mock_list:
        mock_list.return_value = [
            {"id": "all", "name": "All", "type": "system", "description": ""},
        ]
        response = client.get("/api/v1/communities")

    assert response.status_code == 200
    assert response.get_json()["communities"][0]["id"] == "all"


def test_create_community_requires_auth(client):
    response = client.post("/api/v1/communities", json={"name": "Neighborhood"})
    assert response.status_code == 401


def test_create_community_success(client):
    with patch("routes.v1.communities.verify_firebase_token", return_value="user-1"):
        with patch("routes.v1.communities.create_community") as mock_create:
            mock_create.return_value = {
                "id": "community-1",
                "name": "Neighborhood",
                "type": "user",
                "description": "Local group",
            }
            response = client.post(
                "/api/v1/communities",
                json={"name": "Neighborhood", "description": "Local group"},
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 201
    assert response.get_json()["id"] == "community-1"


def test_join_community(client):
    with patch("routes.v1.communities.verify_firebase_token", return_value="user-1"):
        with patch("routes.v1.communities.join_community") as mock_join:
            mock_join.return_value = {"uid": "user-1", "communityIds": ["all", "community-1"]}
            response = client.post(
                "/api/v1/communities/community-1/join",
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200
    assert "community-1" in response.get_json()["communityIds"]


def test_grant_moderator(client):
    with patch("routes.v1.communities.verify_firebase_token", return_value="mod-1"):
        with patch("routes.v1.communities.grant_community_moderator") as mock_grant:
            response = client.post(
                "/api/v1/communities/community-1/moderators",
                json={"uid": "target-1"},
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 201
    mock_grant.assert_called_once_with("mod-1", "target-1", "community-1")


def test_get_categories(client):
    with patch("routes.v1.catalog.list_categories") as mock_list:
        mock_list.return_value = [{"id": "general", "name": "General", "slug": "general"}]
        response = client.get("/api/v1/categories")

    assert response.status_code == 200
    assert response.get_json()["categories"][0]["id"] == "general"


def test_update_current_user_rejects_restricted_fields():
    mock_db = MagicMock()
    user_ref = MagicMock()
    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.get.side_effect = lambda key, default=None: {"firstName": "A", "lastName": "B"}.get(key, default)
    user_ref.get.return_value = snapshot
    mock_db.collection.return_value.document.return_value = user_ref

    with patch("services.user_pipeline.get_db", return_value=mock_db):
        with pytest.raises(AuthorizationError):
            update_current_user("user-1", {"email": "hack@example.com"})


def test_find_user_by_email_requires_moderator():
    mock_db = MagicMock()
    profile_snapshot = MagicMock()
    profile_snapshot.to_dict.return_value = {"moderatorCommunityIds": []}
    mock_db.collection.return_value.document.return_value.get.return_value = profile_snapshot

    with patch("services.user_pipeline.get_db", return_value=mock_db):
        with pytest.raises(AuthorizationError):
            find_user_by_email("user-1", "someone@example.com")


def test_block_user_cannot_block_self():
    mock_db = MagicMock()
    with patch("services.block_pipeline.get_db", return_value=mock_db):
        from services.block_pipeline import BlockPipelineError

        with pytest.raises(BlockPipelineError):
            block_user("user-1", "user-1")
