import time
from collections import defaultdict


class RateLimitExceeded(Exception):
    def __init__(self, message: str = "Rate limit exceeded", status_code: int = 429):
        super().__init__(message)
        self.status_code = status_code


class InMemoryRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> bool:
        now = time.monotonic()
        window_start = now - self.window_seconds
        hits = [timestamp for timestamp in self._hits[key] if timestamp > window_start]

        if len(hits) >= self.max_requests:
            self._hits[key] = hits
            return False

        hits.append(now)
        self._hits[key] = hits
        return True

    def reset(self) -> None:
        self._hits.clear()


_image_upload_limiter: InMemoryRateLimiter | None = None


def configure_image_upload_limiter(max_requests: int, window_seconds: int) -> InMemoryRateLimiter:
    global _image_upload_limiter
    _image_upload_limiter = InMemoryRateLimiter(max_requests, window_seconds)
    return _image_upload_limiter


def get_image_upload_limiter() -> InMemoryRateLimiter:
    global _image_upload_limiter
    if _image_upload_limiter is None:
        from config import IMAGE_UPLOAD_RATE_LIMIT, IMAGE_UPLOAD_RATE_WINDOW_SECONDS

        _image_upload_limiter = InMemoryRateLimiter(
            IMAGE_UPLOAD_RATE_LIMIT,
            IMAGE_UPLOAD_RATE_WINDOW_SECONDS,
        )
    return _image_upload_limiter


def reset_image_upload_limiter() -> None:
    global _image_upload_limiter
    if _image_upload_limiter is not None:
        _image_upload_limiter.reset()


def assert_image_upload_allowed(user_id: str) -> None:
    if not get_image_upload_limiter().check(user_id):
        raise RateLimitExceeded("Upload rate limit exceeded. Try again later.")


_api_ip_limiter: InMemoryRateLimiter | None = None
_api_uid_limiter: InMemoryRateLimiter | None = None


def configure_api_rate_limiters(
    ip_max_requests: int,
    ip_window_seconds: int,
    uid_max_requests: int,
    uid_window_seconds: int,
) -> tuple[InMemoryRateLimiter, InMemoryRateLimiter]:
    global _api_ip_limiter, _api_uid_limiter
    _api_ip_limiter = InMemoryRateLimiter(ip_max_requests, ip_window_seconds)
    _api_uid_limiter = InMemoryRateLimiter(uid_max_requests, uid_window_seconds)
    return _api_ip_limiter, _api_uid_limiter


def get_api_ip_limiter() -> InMemoryRateLimiter:
    global _api_ip_limiter
    if _api_ip_limiter is None:
        from config import API_RATE_LIMIT_IP, API_RATE_LIMIT_IP_WINDOW_SECONDS

        _api_ip_limiter = InMemoryRateLimiter(
            API_RATE_LIMIT_IP,
            API_RATE_LIMIT_IP_WINDOW_SECONDS,
        )
    return _api_ip_limiter


def get_api_uid_limiter() -> InMemoryRateLimiter:
    global _api_uid_limiter
    if _api_uid_limiter is None:
        from config import API_RATE_LIMIT_UID, API_RATE_LIMIT_UID_WINDOW_SECONDS

        _api_uid_limiter = InMemoryRateLimiter(
            API_RATE_LIMIT_UID,
            API_RATE_LIMIT_UID_WINDOW_SECONDS,
        )
    return _api_uid_limiter


def reset_api_rate_limiters() -> None:
    global _api_ip_limiter, _api_uid_limiter
    if _api_ip_limiter is not None:
        _api_ip_limiter.reset()
    if _api_uid_limiter is not None:
        _api_uid_limiter.reset()


def assert_api_rate_allowed(remote_addr: str, user_id: str | None = None) -> None:
    """Per-IP and optional per-UID limits. In-memory only — not shared across Cloud Run instances."""
    if not get_api_ip_limiter().check(remote_addr or "unknown"):
        raise RateLimitExceeded("Too many requests from this IP. Try again later.")

    if user_id and not get_api_uid_limiter().check(user_id):
        raise RateLimitExceeded("Too many requests for this account. Try again later.")


_email_lookup_limiter: InMemoryRateLimiter | None = None


def configure_email_lookup_limiter(max_requests: int, window_seconds: int) -> InMemoryRateLimiter:
    global _email_lookup_limiter
    _email_lookup_limiter = InMemoryRateLimiter(max_requests, window_seconds)
    return _email_lookup_limiter


def get_email_lookup_limiter() -> InMemoryRateLimiter:
    global _email_lookup_limiter
    if _email_lookup_limiter is None:
        _email_lookup_limiter = InMemoryRateLimiter(10, 3600)
    return _email_lookup_limiter


def reset_email_lookup_limiter() -> None:
    global _email_lookup_limiter
    if _email_lookup_limiter is not None:
        _email_lookup_limiter.reset()


def assert_email_lookup_allowed(user_id: str) -> None:
    if not get_email_lookup_limiter().check(user_id):
        raise RateLimitExceeded("Email lookup rate limit exceeded. Try again later.")
