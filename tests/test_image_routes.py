import io
from unittest.mock import patch

from tests.conftest import IMAGE_ID, MINIMAL_JPEG, MINIMAL_PNG


def test_upload_requires_auth(client):
    response = client.post("/api/images")
    assert response.status_code == 401


def test_download_requires_auth_for_private_image(client):
    with patch("routes.images.assert_can_view_image_public") as mock_public:
        from services.image_metadata import ImageAccessError

        mock_public.side_effect = ImageAccessError("You do not have access to this image")

        response = client.get(f"/api/images/{IMAGE_ID}")

    assert response.status_code == 403


@patch("routes.images.read_image_bytes", return_value=MINIMAL_PNG)
@patch("routes.images.assert_can_view_image_public")
def test_download_allows_guest_public_image(mock_public, mock_read_bytes, client):
    mock_public.return_value = {
        "imageId": IMAGE_ID,
        "contentType": "image/png",
        "storageKey": "listing-images/seller-1/file.png",
    }

    response = client.get(f"/api/images/{IMAGE_ID}")

    assert response.status_code == 200
    assert response.data == MINIMAL_PNG


def test_download_rejects_invalid_image_id(client):
    with patch("routes.images.verify_firebase_token", return_value="user-1"):
        response = client.get(
            "/api/images/not-a-valid-id",
            headers={"Authorization": "Bearer token"},
        )

    assert response.status_code == 404


@patch("routes.images.create_image_record")
@patch("routes.images.verify_firebase_token", return_value="seller-1")
def test_upload_success(mock_verify, mock_create_record, client):
    mock_create_record.return_value = {"imageId": IMAGE_ID}

    data = {
        "file": (io.BytesIO(MINIMAL_JPEG), "photo.jpg"),
        "communityIds": '["church"]',
    }
    response = client.post(
        "/api/images",
        data=data,
        content_type="multipart/form-data",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["url"] == f"/api/images/{body['imageId']}"
    mock_create_record.assert_called_once()
    assert mock_create_record.call_args.kwargs["owner_id"] == "seller-1"
    assert mock_create_record.call_args.kwargs["community_ids"] == ["church"]


@patch("routes.images.verify_firebase_token", return_value="seller-1")
def test_upload_rejects_non_image(mock_verify, client):
    data = {"file": (io.BytesIO(b"plain-text"), "photo.jpg")}
    response = client.post(
        "/api/images",
        data=data,
        content_type="multipart/form-data",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 400
    assert "Unsupported" in response.get_json()["error"]


@patch("routes.images.read_image_bytes", return_value=MINIMAL_PNG)
@patch("routes.images.assert_can_view_image")
@patch("routes.images.verify_firebase_token_optional", return_value="buyer-1")
def test_download_success(mock_verify, mock_assert_view, mock_read_bytes, client):
    mock_assert_view.return_value = {
        "imageId": IMAGE_ID,
        "contentType": "image/png",
        "storageKey": "listing-images/seller-1/file.png",
    }

    response = client.get(
        f"/api/images/{IMAGE_ID}",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert response.data == MINIMAL_PNG
    assert response.mimetype == "image/png"


@patch("routes.images.create_image_record")
@patch("routes.images.verify_firebase_token", return_value="seller-1")
def test_upload_rate_limited(mock_verify, mock_create_record, client):
    from services.rate_limit import configure_image_upload_limiter

    configure_image_upload_limiter(max_requests=1, window_seconds=3600)
    mock_create_record.return_value = {"imageId": IMAGE_ID}

    headers = {"Authorization": "Bearer token"}
    first = client.post(
        "/api/images",
        data={
            "file": (io.BytesIO(MINIMAL_JPEG), "photo.jpg"),
            "communityIds": '["all"]',
        },
        content_type="multipart/form-data",
        headers=headers,
    )
    second = client.post(
        "/api/images",
        data={
            "file": (io.BytesIO(MINIMAL_JPEG), "photo-2.jpg"),
            "communityIds": '["all"]',
        },
        content_type="multipart/form-data",
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 429
    assert "rate limit" in second.get_json()["error"].lower()
