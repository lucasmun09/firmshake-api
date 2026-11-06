from services.search_relevance import matches_keyword, normalize_search_query, search_relevance_score


def test_normalize_search_query():
    assert normalize_search_query("  Office   Chair ") == "office chair"


def test_search_relevance_exact_beats_contains():
    exact = search_relevance_score({"title": "Office Chair", "sellerName": "Sam"}, "office chair")
    contains = search_relevance_score({"title": "Used Office Chair Set", "sellerName": "Sam"}, "office chair")
    assert exact > contains


def test_search_relevance_starts_with_beats_contains():
    starts_with = search_relevance_score({"title": "Office supplies bundle", "sellerName": "Sam"}, "office")
    contains = search_relevance_score({"title": "Home office desk", "sellerName": "Sam"}, "office")
    assert starts_with > contains


def test_matches_keyword_title_and_seller():
    listing = {"title": "Red Mountain Bike", "sellerName": "Office Cyclery"}
    assert matches_keyword(listing, "mountain bike") is True
    assert matches_keyword(listing, "office") is True
    assert matches_keyword(listing, "blue car") is False


def test_matches_keyword_description_only():
    listing = {"title": "Desk lamp", "description": "Great for your office", "sellerName": "Pat"}
    assert matches_keyword(listing, "office") is True
    # Single-token query hits the all-tokens description branch.
    assert search_relevance_score(listing, "office") == 100


def test_search_relevance_description_ranks_below_seller():
    description_only = search_relevance_score(
        {"title": "Desk lamp", "description": "Great for your office", "sellerName": "Pat"},
        "office",
    )
    seller_hit = search_relevance_score(
        {"title": "Desk lamp", "description": "", "sellerName": "Office Depot"},
        "office",
    )
    assert seller_hit > description_only


def test_search_relevance_all_description_tokens_beat_any():
    all_tokens = search_relevance_score(
        {"title": "Lamp", "description": "Bright office desk light", "sellerName": "Pat"},
        "office desk",
    )
    any_token = search_relevance_score(
        {"title": "Lamp", "description": "Bright office light", "sellerName": "Pat"},
        "office desk",
    )
    assert all_tokens == 100
    assert any_token == 50
