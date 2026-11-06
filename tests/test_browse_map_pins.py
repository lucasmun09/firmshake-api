from services.browse_map_pins import aggregate_browse_map_pins, browse_map_pin_group_key


def _listing(listing_id: str, seller_id: str, lat: float, lng: float, title: str = "Item"):
    return {
        "id": listing_id,
        "title": title,
        "sellerId": seller_id,
        "location": {"lat": lat, "lng": lng},
    }


def test_aggregate_browse_map_pins_same_seller_nearby():
    listings = [
        _listing("l1", "seller-a", 38.75011, -77.47091, "Alpha"),
        _listing("l2", "seller-a", 38.75014, -77.47096, "Beta"),
    ]

    groups = aggregate_browse_map_pins(listings)

    assert len(groups) == 1
    assert groups[0]["kind"] == "aggregated"
    assert groups[0]["listingIds"] == ["l1", "l2"]


def test_aggregate_browse_map_pins_different_sellers_same_coords():
    listings = [
        _listing("l1", "seller-a", 38.75, -77.47),
        _listing("l2", "seller-b", 38.75, -77.47),
    ]

    groups = aggregate_browse_map_pins(listings)

    assert len(groups) == 2
    assert all(group["kind"] == "single" for group in groups)


def test_browse_map_pin_group_key_matches_client_precision():
    key = browse_map_pin_group_key("seller-a", 38.75012, -77.47098)
    assert key == "seller-a:38.7501:-77.4710"
