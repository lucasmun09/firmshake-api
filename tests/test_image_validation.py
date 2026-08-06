import pytest

from services.image_validation import detect_image_content_type
from tests.conftest import MINIMAL_JPEG, MINIMAL_PNG


def test_detects_jpeg():
    assert detect_image_content_type(MINIMAL_JPEG) == "image/jpeg"


def test_detects_png():
    assert detect_image_content_type(MINIMAL_PNG) == "image/png"


def test_rejects_too_short_payload():
    assert detect_image_content_type(b"\xff\xd8\xff") is None


def test_rejects_non_image_bytes():
    assert detect_image_content_type(b"not-an-image-file" * 2) is None


def test_rejects_webp_without_webp_marker():
    payload = b"RIFF" + b"\x00" * 4 + b"NOTWEBP" + b"\x00" * 4
    assert detect_image_content_type(payload) is None
