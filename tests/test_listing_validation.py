import pytest

from services.listing_validation import ValidationError, validate_create_listing_payload


def test_validate_create_listing_payload_success():
    payload = validate_create_listing_payload(
        {
            "title": "Mountain Bike",
            "description": "Like new",
            "price": 400,
            "imageUrls": ["/api/images/abc.jpg"],
            "sellerName": "Sam",
            "communityIds": ["all"],
            "primaryCategoryId": "sports",
        }
    )
    assert payload["title"] == "Mountain Bike"
    assert payload["price"] == 400
    assert payload["imageUrl"] == "/api/images/abc.jpg"


def test_validate_create_listing_payload_requires_title():
    with pytest.raises(ValidationError, match="title"):
        validate_create_listing_payload({"price": 10, "imageUrls": ["/a.jpg"], "sellerName": "Sam"})


def test_validate_create_listing_payload_rejects_negative_price():
    with pytest.raises(ValidationError, match="price"):
        validate_create_listing_payload(
            {
                "title": "Item",
                "description": "Desc",
                "price": -1,
                "imageUrls": ["/a.jpg"],
                "sellerName": "Sam",
            }
        )
