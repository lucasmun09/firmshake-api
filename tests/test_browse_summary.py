from unittest.mock import patch

from services.browse_summary import (
    browse_summary_search,
    summarize_browse_result,
    to_listing_summary,
)


def test_to_listing_summary_strips_heavy_fields_and_picks_primary_image():
    summary = to_listing_summary(
        {
            "id": "l1",
            "title": "Bike",
            "description": "Long body text",
            "price": 120,
            "imageUrl": "",
            "imageUrls": ["https://cdn.example/a.jpg", "https://cdn.example/b.jpg"],
            "sellerId": "seller-1",
            "sellerName": "Sam",
            "communityIds": ["all"],
            "primaryCategoryId": "sports",
            "categoryIds": ["sports", "outdoors"],
            "titleLower": "bike",
            "status": "active",
            "createdAt": 1_700_000_000_000,
            "location": {"lat": 38.75, "lng": -77.47, "city": "Fairfax"},
        }
    )

    assert summary == {
        "id": "l1",
        "title": "Bike",
        "price": 120,
        "imageUrl": "https://cdn.example/a.jpg",
        "status": "active",
        "sellerId": "seller-1",
        "communityIds": ["all"],
        "primaryCategoryId": "sports",
        "createdAt": 1_700_000_000_000,
        "location": {"lat": 38.75, "lng": -77.47, "city": "Fairfax"},
    }
    assert "description" not in summary
    assert "imageUrls" not in summary
    assert "sellerName" not in summary
    assert "categoryIds" not in summary
    assert "titleLower" not in summary


def test_summarize_browse_result_preserves_pin_groups_and_marks_shape():
    result = summarize_browse_result(
        {
            "listings": [
                {
                    "id": "l1",
                    "title": "Desk",
                    "description": "Oak",
                    "price": 40,
                    "imageUrl": "https://cdn.example/desk.jpg",
                    "sellerId": "s1",
                    "communityIds": ["all"],
                    "primaryCategoryId": "furniture",
                    "status": "active",
                }
            ],
            "total": 1,
            "page": 1,
            "pageSize": 24,
            "hasMore": False,
            "engine": "typesense",
            "projectId": "firmshake-dev",
            "pinGroups": [
                {
                    "key": "s1:38.7500:-77.4700",
                    "kind": "single",
                    "sellerId": "s1",
                    "position": {"lat": 38.75, "lng": -77.47},
                    "listingIds": ["l1"],
                }
            ],
        }
    )

    assert result["shape"] == "summary"
    assert result["listings"][0]["imageUrl"] == "https://cdn.example/desk.jpg"
    assert "description" not in result["listings"][0]
    assert result["pinGroups"][0]["listingIds"] == ["l1"]
    assert result["engine"] == "typesense"


def test_browse_summary_search_delegates_to_browse_search():
    full = {
        "listings": [
            {
                "id": "l9",
                "title": "Lamp",
                "description": "Bright",
                "price": 15,
                "imageUrl": "https://cdn.example/lamp.jpg",
                "sellerId": "s9",
                "communityIds": ["all"],
                "primaryCategoryId": "home",
                "status": "active",
            }
        ],
        "total": 1,
        "page": 1,
        "pageSize": 24,
        "hasMore": False,
        "engine": "firestore",
        "pinGroups": [],
    }

    with patch("services.browse_summary.browse_search", return_value=full) as mocked:
        result = browse_summary_search(q="lamp", page=1, page_size=24)

    mocked.assert_called_once()
    assert result["shape"] == "summary"
    assert result["listings"][0]["id"] == "l9"
    assert "description" not in result["listings"][0]


def test_post_browse_summary_route(client):
    full = {
        "listings": [
            {
                "id": "l2",
                "title": "Chair",
                "description": "Comfy",
                "price": 25,
                "imageUrl": "https://cdn.example/chair.jpg",
                "imageUrls": ["https://cdn.example/chair.jpg"],
                "sellerId": "s2",
                "sellerName": "Alex",
                "communityIds": ["all"],
                "primaryCategoryId": "furniture",
                "categoryIds": ["furniture"],
                "status": "active",
            }
        ],
        "total": 1,
        "page": 1,
        "pageSize": 24,
        "hasMore": False,
        "engine": "firestore",
        "projectId": "firmshake-dev",
        "pinGroups": [],
    }

    with patch("routes.v1.browse.browse_summary_search", return_value=full) as mocked:
        # Route wraps browse_summary_search which already summarizes; return summarized shape.
        mocked.return_value = {
            **full,
            "listings": [
                {
                    "id": "l2",
                    "title": "Chair",
                    "price": 25,
                    "imageUrl": "https://cdn.example/chair.jpg",
                    "status": "active",
                    "sellerId": "s2",
                    "communityIds": ["all"],
                    "primaryCategoryId": "furniture",
                }
            ],
            "shape": "summary",
        }
        response = client.post(
            "/api/v1/browse/summary",
            json={"q": "chair", "page": 1, "pageSize": 24},
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["shape"] == "summary"
    assert payload["listings"][0]["id"] == "l2"
    assert "description" not in payload["listings"][0]
    assert "sellerName" not in payload["listings"][0]
    mocked.assert_called_once()
