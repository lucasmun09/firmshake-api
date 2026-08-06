from services.geohash import encode_geohash, haversine_distance_km
from services.listing_search import matches_keyword, map_feed_doc, search_listings


def test_encode_geohash():
    value = encode_geohash(37.7749, -122.4194, precision=9)
    assert len(value) == 9
    assert set(value).issubset(set("0123456789bcdefghjkmnpqrstuvwxyz"))


def test_haversine_distance():
    distance = haversine_distance_km(37.7749, -122.4194, 37.8044, -122.2712)
    assert 10 < distance < 20


def test_matches_keyword():
    listing = {"title": "Red Mountain Bike", "description": "Great condition"}
    assert matches_keyword(listing, "mountain bike") is True
    assert matches_keyword(listing, "blue car") is False


def test_map_feed_doc():
    doc = map_feed_doc(
        "listing-1",
        {
            "title": "Desk",
            "description": "Wood",
            "price": 50,
            "communityIds": ["all"],
            "primaryCategoryId": "furniture",
            "categoryIds": ["furniture"],
            "status": "active",
            "sellerId": "u1",
            "sellerName": "Sam",
            "imageUrl": "/img.jpg",
        },
    )
    assert doc["id"] == "listing-1"
    assert doc["primaryCategoryId"] == "furniture"
    assert doc["status"] == "active"


def test_map_feed_doc_reads_lat_lng_fields():
    doc = map_feed_doc(
        "listing-2",
        {
            "title": "Chair",
            "lat": 38.7512726,
            "lng": -77.4706769,
        },
    )
    assert doc["location"] == [38.7512726, -77.4706769]


def test_search_listings_firestore_geo_filter(monkeypatch):
    class FakeDoc:
        def __init__(self, doc_id, data):
            self.id = doc_id
            self._data = data

        def to_dict(self):
            return self._data

    class FakeQuery:
        def __init__(self, docs):
            self._docs = docs

        def where(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        def stream(self):
            return self._docs

    class FakeCollection:
        def document(self, _community_id):
            return self

        def collection(self, _name):
            return self

        def where(self, *args, **kwargs):
            return FakeQuery(
                [
                    FakeDoc(
                        "nearby",
                        {
                            "title": "Apple Sauce",
                            "description": "Local",
                            "price": 5,
                            "communityIds": ["all"],
                            "primaryCategoryId": "general",
                            "categoryIds": ["general"],
                            "status": "active",
                            "sellerId": "u1",
                            "sellerName": "Sam",
                            "imageUrl": "/img.jpg",
                            "lat": 38.7512726,
                            "lng": -77.4706769,
                        },
                    ),
                    FakeDoc(
                        "far-away",
                        {
                            "title": "Surfboard",
                            "description": "Coastal",
                            "price": 100,
                            "communityIds": ["all"],
                            "primaryCategoryId": "general",
                            "categoryIds": ["general"],
                            "status": "active",
                            "sellerId": "u2",
                            "sellerName": "Pat",
                            "imageUrl": "/board.jpg",
                            "lat": 37.7749,
                            "lng": -122.4194,
                        },
                    ),
                ]
            )

    class FakeDb:
        def collection(self, name):
            assert name == "communityFeeds"
            return FakeCollection()

    monkeypatch.setenv("TYPESENSE_HOST", "")
    monkeypatch.setattr("services.firebase_app.get_db", lambda: FakeDb())

    result = search_listings(
        community_id="all",
        lat=38.76576535362319,
        lng=-77.4706769,
        radius_km=40.2335,
        page=1,
        page_size=10,
    )
    assert result["engine"] == "firestore"
    assert result["total"] == 1
    assert result["listings"][0]["title"] == "Apple Sauce"
