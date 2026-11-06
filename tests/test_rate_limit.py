from unittest.mock import patch

import pytest

from services.rate_limit import (
    InMemoryRateLimiter,
    RateLimitExceeded,
    assert_image_upload_allowed,
    configure_image_upload_limiter,
)


def test_allows_requests_under_limit():
    limiter = InMemoryRateLimiter(max_requests=3, window_seconds=60)

    assert limiter.check("user-1") is True
    assert limiter.check("user-1") is True
    assert limiter.check("user-1") is True


def test_blocks_requests_over_limit():
    limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60)

    assert limiter.check("user-1") is True
    assert limiter.check("user-1") is True
    assert limiter.check("user-1") is False


def test_limits_are_per_user():
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60)

    assert limiter.check("user-1") is True
    assert limiter.check("user-2") is True
    assert limiter.check("user-1") is False


def test_assert_image_upload_allowed_raises_when_limited():
    configure_image_upload_limiter(max_requests=1, window_seconds=60)
    assert_image_upload_allowed("user-1")

    with pytest.raises(RateLimitExceeded):
        assert_image_upload_allowed("user-1")
