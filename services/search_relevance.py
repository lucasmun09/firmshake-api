"""Title / seller / description search relevance helpers for browse search."""

from __future__ import annotations

from typing import Any


def normalize_search_query(query_text: str) -> str:
    return " ".join(query_text.strip().lower().split())


def search_relevance_score(listing: dict[str, Any], query_text: str) -> int:
    """
    Higher score = stronger match.
    exact title > starts-with > all tokens in title > any token in title
    > seller name > description body.
    """
    normalized = normalize_search_query(query_text)
    if not normalized:
        return 0

    title = str(listing.get("title", "")).strip().lower()
    seller = str(listing.get("sellerName", "")).strip().lower()
    description = str(listing.get("description", "")).strip().lower()
    terms = normalized.split()

    if title == normalized:
        return 1000
    if title.startswith(normalized):
        return 900
    if all(term in title for term in terms):
        first_index = min(
            (title.find(term) for term in terms if term in title),
            default=0,
        )
        return 800 - min(first_index, 99)
    if any(term in title for term in terms):
        return 500
    if all(term in seller for term in terms):
        return 300
    if any(term in seller for term in terms):
        return 200
    if all(term in description for term in terms):
        return 100
    if any(term in description for term in terms):
        return 50

    return 0


def matches_keyword(listing: dict[str, Any], query_text: str) -> bool:
    return search_relevance_score(listing, query_text) > 0
