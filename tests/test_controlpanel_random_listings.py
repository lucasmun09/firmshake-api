from services.controlpanel_random_listings import (
    clamp_bulk_count,
    random_listing_title,
    random_point_within_radius_miles,
    random_price,
)
from services.controlpanel_random_listings import EARTH_RADIUS_MILES
import math


def test_clamp_bulk_count():
    assert clamp_bulk_count(0) == 1
    assert clamp_bulk_count(100) == 100
    assert clamp_bulk_count(9999) == 9999
    assert clamp_bulk_count(15000) == 10000


def test_random_listing_title_not_empty():
    assert random_listing_title().strip()


def test_random_price_range():
    for _ in range(20):
        price = random_price(5, 50)
        assert 5 <= price <= 50


def test_random_point_within_radius_stays_inside():
    center_lat, center_lng = 37.7749, -122.4194
    radius = 25.0

    for _ in range(50):
        lat, lng = random_point_within_radius_miles(center_lat, center_lng, radius)
        distance = _haversine_miles(center_lat, center_lng, lat, lng)
        assert distance <= radius + 0.01


def test_random_point_zero_radius_returns_center():
    lat, lng = random_point_within_radius_miles(40.0, -74.0, 0)
    assert lat == 40.0
    assert lng == -74.0


def _haversine_miles(lat1, lng1, lat2, lng2):
    to_rad = math.radians
    d_lat = to_rad(lat2 - lat1)
    d_lng = to_rad(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(to_rad(lat1)) * math.cos(to_rad(lat2)) * math.sin(d_lng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))
