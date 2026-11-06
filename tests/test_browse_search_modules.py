"""Browse-search module map + re-export contracts for parallel agents."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_browse_search_split_files_exist():
    for rel in (
        "services/browse_search.py",
        "services/browse_search_common.py",
        "services/browse_search_typesense.py",
        "services/browse_search_firestore.py",
        "services/browse_search_cache.py",
        "services/browse_map_pins.py",
        "services/browse_summary.py",
    ):
        assert (ROOT / rel).is_file(), rel


def test_browse_search_reexports_public_surface():
    from services import browse_search as mod

    for name in (
        "TypesenseClient",
        "browse_search",
        "browse_search_firestore",
        "browse_search_typesense",
        "map_feed_doc",
        "matches_keyword",
        "_serialize_listing_hit",
        "_finalize_browse_page",
        "_firestore_fetch_limit",
        "_category_filter_typesense",
        "_matches_category",
    ):
        assert hasattr(mod, name), name


def test_orchestrator_stays_thin():
    lines = (ROOT / "services" / "browse_search.py").read_text(encoding="utf-8").splitlines()
    assert len(lines) < 220, len(lines)
    text = "\n".join(lines)
    assert "browse_search_typesense" in text
    assert "browse_search_firestore" in text
    assert "class TypesenseClient" not in text
