"""In-process TTL cache for browse search responses (Cloud Run warm instances).

For multi-instance deployments, add Redis/Memorystore with the same key shape.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

DEFAULT_TTL_SECONDS = float(os.getenv("BROWSE_SEARCH_CACHE_TTL_SECONDS", "45"))
MAX_ENTRIES = int(os.getenv("BROWSE_SEARCH_CACHE_MAX_ENTRIES", "256"))

_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def build_browse_search_cache_key(params: dict[str, Any], viewer_uid: str | None) -> str:
    """Stable hash of normalized search params plus viewer (block-list varies per user)."""
    payload = {
        **params,
        "viewerUid": viewer_uid or "",
    }
    normalized = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_cached_browse_search(key: str) -> dict[str, Any] | None:
    entry = _cache.get(key)
    if entry is None:
        return None

    expires_at, value = entry
    if time.monotonic() > expires_at:
        _cache.pop(key, None)
        return None

    return value


def set_cached_browse_search(
    key: str,
    value: dict[str, Any],
    *,
    ttl_seconds: float | None = None,
) -> None:
    ttl = DEFAULT_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    if len(_cache) >= MAX_ENTRIES:
        oldest_key = min(_cache, key=lambda cache_key: _cache[cache_key][0])
        _cache.pop(oldest_key, None)

    _cache[key] = (time.monotonic() + ttl, value)


def clear_browse_search_cache() -> None:
    _cache.clear()
