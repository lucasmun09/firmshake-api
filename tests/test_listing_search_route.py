from services.listing_search import search_listings


def test_search_listings_firestore_fallback(monkeypatch):
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
                        "listing-1",
                        {
                            "title": "Mountain Bike",
                            "description": "Like new",
                            "price": 400,
                            "communityIds": ["all"],
                            "primaryCategoryId": "sports",
                            "categoryIds": ["sports"],
                            "status": "active",
                            "sellerId": "u1",
                            "sellerName": "Sam",
                            "imageUrl": "/bike.jpg",
                        },
                    )
                ]
            )

    class FakeDb:
        def collection(self, name):
            assert name == "communityFeeds"
            return FakeCollection()

    monkeypatch.setenv("TYPESENSE_HOST", "")
    monkeypatch.setattr("services.firebase_app.get_db", lambda: FakeDb())

    result = search_listings(q="mountain bike", community_id="all", page=1, page_size=10)
    assert result["engine"] == "firestore"
    assert result["total"] == 1
    assert result["listings"][0]["title"] == "Mountain Bike"
