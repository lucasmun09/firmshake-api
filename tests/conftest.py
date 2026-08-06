import pytest

from app import create_app
from services.rate_limit import (
    configure_api_rate_limiters,
    configure_email_lookup_limiter,
    configure_image_upload_limiter,
    reset_api_rate_limiters,
    reset_email_lookup_limiter,
    reset_image_upload_limiter,
)


@pytest.fixture
def app(tmp_path):
    storage_dir = tmp_path / "images"
    storage_dir.mkdir()

    application = create_app()
    application.config.update(
        {
            "TESTING": True,
            "STORAGE_DIR": storage_dir,
            "GCS_BUCKET": "",
        }
    )
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def isolated_rate_limiter():
    configure_image_upload_limiter(max_requests=20, window_seconds=3600)
    configure_api_rate_limiters(
        ip_max_requests=1000,
        ip_window_seconds=60,
        uid_max_requests=1000,
        uid_window_seconds=60,
    )
    configure_email_lookup_limiter(max_requests=100, window_seconds=3600)
    yield
    reset_image_upload_limiter()
    reset_api_rate_limiters()
    reset_email_lookup_limiter()


# Minimal JPEG file header (enough for magic-byte validation).
MINIMAL_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xd9"
)

MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\x0bIDAT\x08\xd7c\xf8\x0f\x00\x00\x01\x01\x01\x00"
    b"\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

IMAGE_ID = "a" * 32
