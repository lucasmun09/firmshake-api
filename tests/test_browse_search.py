from unittest.mock import patch

from services.browse_search import (
    browse_search,
    map_feed_doc,
    matches_keyword,
    _category_filter_typesense,
    _matches_category,
    _serialize_listing_hit,
)


def test_matches_keyword():
    listing = {"title": "Red Mountain Bike", "sellerName": "Sam", "description": "Great condition"}
    assert matches_keyword(listing, "mountain bike") is True
    assert matches_keyword(listing, "blue car") is False
    assert matches_keyword(listing, "condition") is True


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
    assert doc["hasLocation"] is True


def test_category_filter_typesense_single():
    assert _category_filter_typesense(["electronics"]) == (
        "(primaryCategoryId:=electronics || categoryIds:=electronics)"
    )


def test_category_filter_typesense_multi():
    result = _category_filter_typesense(["electronics", "phones"])
    assert "primaryCategoryId:=[electronics,phones]" in result
    assert "categoryIds:=[electronics,phones]" in result


def test_matches_category_or_semantics():
    listing = {"primaryCategoryId": "general", "categoryIds": ["phones", "electronics"]}
    assert _matches_category(listing, ["phones"]) is True
    assert _matches_category(listing, ["furniture"]) is False


def test_serialize_listing_hit_location_array():
    hit = {
        "id": "l1",
        "title": "Desk",
        "price": 50,
        "location": [38.7, -77.4],
        "city": "Fairfax",
    }
    result = _serialize_listing_hit(hit)
    assert result["location"]["lat"] == 38.7
    assert result["location"]["lng"] == -77.4


def test_browse_search_firestore_geo_filter(monkeypatch):
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

    result = browse_search(
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


def test_browse_search_excludes_blocked_sellers(monkeypatch):
    class FakeDoc:
        def __init__(self, doc_id, data):
            self.id = doc_id
            self._data = data

        def to_dict(self):
            return self._data

    class FakeQuery:
        def where(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        def stream(self):
            return [
                FakeDoc(
                    "blocked-listing",
                    {
                        "title": "Blocked seller item",
                        "description": "",
                        "price": 10,
                        "communityIds": ["all"],
                        "primaryCategoryId": "general",
                        "categoryIds": ["general"],
                        "status": "active",
                        "sellerId": "blocked-1",
                        "sellerName": "Blocked",
                        "imageUrl": "/img.jpg",
                    },
                ),
                FakeDoc(
                    "allowed-listing",
                    {
                        "title": "Allowed seller item",
                        "description": "",
                        "price": 20,
                        "communityIds": ["all"],
                        "primaryCategoryId": "general",
                        "categoryIds": ["general"],
                        "status": "active",
                        "sellerId": "allowed-1",
                        "sellerName": "Allowed",
                        "imageUrl": "/img.jpg",
                    },
                ),
            ]

    class FakeCollection:
        def document(self, _community_id):
            return self

        def collection(self, _name):
            return self

        def where(self, *args, **kwargs):
            return FakeQuery()

    class FakeDb:
        def collection(self, name):
            assert name in {"communityFeeds", "users"}
            if name == "users":
                return self
            return FakeCollection()

        def document(self, _uid):
            return self

        def stream(self):
            return []

    monkeypatch.setenv("TYPESENSE_HOST", "")
    monkeypatch.setattr("services.firebase_app.get_db", lambda: FakeDb())
    monkeypatch.setattr(
        "services.block_pipeline.list_blocked_users",
        lambda _uid: [{"blockedUserId": "blocked-1", "blockedAt": 1}],
    )

    result = browse_search(viewer_uid="viewer-1", page_size=10)
    assert result["total"] == 1
    assert result["listings"][0]["sellerId"] == "allowed-1"


def test_browse_search_firestore_paginates_beyond_three_pages(monkeypatch):
    class FakeDoc:
        def __init__(self, doc_id, data):
            self.id = doc_id
            self._data = data

        def to_dict(self):
            return self._data

    all_docs = [
        FakeDoc(
            f"listing-{index}",
            {
                "title": f"Item {index}",
                "description": "",
                "price": 10,
                "communityIds": ["all"],
                "primaryCategoryId": "general",
                "categoryIds": ["general"],
                "status": "active",
                "sellerId": f"u{index}",
                "sellerName": "Seller",
                "imageUrl": "/img.jpg",
                "createdAt": type("Ts", (), {"timestamp": lambda self, ms=index: ms / 1000})(),
            },
        )
        for index in range(100)
    ]

    class FakeQuery:
        def __init__(self, docs):
            self._docs = docs
            self._start_after = None
            self._limit = len(docs)

        def where(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def limit(self, value):
            self._limit = value
            return self

        def start_after(self, snapshot):
            self._start_after = snapshot
            return self

        def stream(self):
            docs = self._docs
            if self._start_after is not None:
                start_index = next(
                    (index for index, doc in enumerate(docs) if doc.id == self._start_after.id),
                    len(docs),
                )
                docs = docs[start_index + 1 :]
            return docs[: self._limit]

    class FakeCollection:
        def document(self, _community_id):
            return self

        def collection(self, _name):
            return self

        def where(self, *args, **kwargs):
            return FakeQuery(all_docs)

    class FakeDb:
        def collection(self, name):
            assert name == "communityFeeds"
            return FakeCollection()

    monkeypatch.setenv("TYPESENSE_HOST", "")
    monkeypatch.setattr("services.firebase_app.get_db", lambda: FakeDb())

    page1 = browse_search(page=1, page_size=24)
    page4 = browse_search(page=4, page_size=24)

    assert page1["engine"] == "firestore"
    assert page1["hasMore"] is True
    assert len(page1["listings"]) == 24
    assert page4["hasMore"] is True
    assert len(page4["listings"]) == 24
    assert page4["listings"][0]["id"] == "listing-72"


def test_browse_search_firestore_price_filter(monkeypatch):
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
                        "cheap",
                        {
                            "title": "Small lamp",
                            "description": "",
                            "price": 15,
                            "communityIds": ["all"],
                            "primaryCategoryId": "general",
                            "categoryIds": ["general"],
                            "status": "active",
                            "sellerId": "u1",
                            "sellerName": "Sam",
                            "imageUrl": "/img.jpg",
                        },
                    ),
                    FakeDoc(
                        "expensive",
                        {
                            "title": "Luxury sofa",
                            "description": "",
                            "price": 900,
                            "communityIds": ["all"],
                            "primaryCategoryId": "general",
                            "categoryIds": ["general"],
                            "status": "active",
                            "sellerId": "u2",
                            "sellerName": "Pat",
                            "imageUrl": "/sofa.jpg",
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

    result = browse_search(min_price=10, max_price=500, page_size=10)
    assert result["engine"] == "firestore"
    assert result["total"] == 1
    assert result["listings"][0]["title"] == "Small lamp"


def test_browse_search_always_includes_pin_groups(monkeypatch):
    class FakeDoc:
        def __init__(self, doc_id, data):
            self.id = doc_id
            self._data = data

        def to_dict(self):
            return self._data

    class FakeQuery:
        def where(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        def stream(self):
            return [
                FakeDoc(
                    "l1",
                    {
                        "title": "Alpha",
                        "description": "",
                        "price": 10,
                        "communityIds": ["all"],
                        "primaryCategoryId": "general",
                        "categoryIds": ["general"],
                        "status": "active",
                        "sellerId": "seller-a",
                        "sellerName": "Sam",
                        "imageUrl": "/img.jpg",
                        "lat": 38.75011,
                        "lng": -77.47091,
                    },
                ),
                FakeDoc(
                    "l2",
                    {
                        "title": "Beta",
                        "description": "",
                        "price": 20,
                        "communityIds": ["all"],
                        "primaryCategoryId": "general",
                        "categoryIds": ["general"],
                        "status": "active",
                        "sellerId": "seller-a",
                        "sellerName": "Sam",
                        "imageUrl": "/img2.jpg",
                        "lat": 38.75014,
                        "lng": -77.47096,
                    },
                ),
            ]

    class FakeCollection:
        def document(self, _community_id):
            return self

        def collection(self, _name):
            return self

        def where(self, *args, **kwargs):
            return FakeQuery()

    class FakeDb:
        def collection(self, name):
            assert name == "communityFeeds"
            return FakeCollection()

    monkeypatch.setenv("TYPESENSE_HOST", "")
    monkeypatch.setattr("services.firebase_app.get_db", lambda: FakeDb())

    result = browse_search(page_size=10)

    assert "pinGroups" in result
    assert len(result["pinGroups"]) == 1
    assert result["pinGroups"][0]["kind"] == "aggregated"
    assert set(result["pinGroups"][0]["listingIds"]) == {"l1", "l2"}


def test_post_browse_search_ignores_invalid_token(client):
    with patch("routes.v1.browse.browse_search") as mock_search:
        mock_search.return_value = {
            "listings": [],
            "total": 0,
            "page": 1,
            "pageSize": 24,
            "hasMore": False,
            "engine": "firestore",
            "projectId": "firmshake-dev",
        }
        response = client.post(
            "/api/v1/browse/search",
            json={"communityId": "all", "lat": 42.5, "lng": -83.1, "radiusMiles": 3},
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 200
    assert mock_search.call_args.kwargs["viewer_uid"] is None


def test_post_browse_search_route(client):
    payload = {
        "q": "bike",
        "communityId": "all",
        "categoryId": "sports",
        "page": 1,
        "pageSize": 12,
    }
    with patch("routes.v1.browse.browse_search") as mock_search:
        mock_search.return_value = {
            "listings": [],
            "total": 0,
            "page": 1,
            "pageSize": 12,
            "hasMore": False,
            "engine": "firestore",
            "projectId": "firmshake-dev",
        }
        response = client.post("/api/v1/browse/search", json=payload)

    assert response.status_code == 200
    mock_search.assert_called_once()
    call_kwargs = mock_search.call_args.kwargs
    assert call_kwargs["q"] == "bike"
    assert call_kwargs["category_id"] == "sports"
    assert call_kwargs["viewer_uid"] is None


def test_post_browse_search_passes_auth_uid(client):
    with patch("routes.v1.browse.verify_firebase_token_optional", return_value="user-1"):
        with patch("routes.v1.browse.browse_search") as mock_search:
            mock_search.return_value = {
                "listings": [],
                "total": 0,
                "page": 1,
                "pageSize": 24,
                "hasMore": False,
                "engine": "firestore",
                "projectId": "firmshake-dev",
            }
            response = client.post(
                "/api/v1/browse/search",
                json={"communityId": "all"},
                headers={"Authorization": "Bearer fake-token"},
            )

    assert response.status_code == 200
    assert mock_search.call_args.kwargs["viewer_uid"] == "user-1"


def test_firestore_fetch_limit_caps_scan_window():
    from services.browse_search import _firestore_fetch_limit

    assert _firestore_fetch_limit(1, 24) == 72
    assert _firestore_fetch_limit(10, 24) == 264
    assert _firestore_fetch_limit(50, 24) == 1000


def test_finalize_browse_page_passes_through_pagination():
    from services.browse_search import _finalize_browse_page

    page = _finalize_browse_page(
        listings=[{"id": "listing-1"}],
        total=500,
        page=3,
        page_size=100,
        has_more=True,
        engine="firestore",
    )

    assert page["total"] == 500
    assert page["hasMore"] is True
    assert "maxResults" not in page

    last_page = _finalize_browse_page(
        listings=[{"id": "listing-1"}],
        total=500,
        page=5,
        page_size=100,
        has_more=False,
        engine="firestore",
    )
    assert last_page["hasMore"] is False


def test_get_categories_cache_headers(client):
    with patch("routes.v1.catalog.list_categories") as mock_list:
        mock_list.return_value = [{"id": "general", "name": "General", "slug": "general", "active": True}]
        response = client.get("/api/v1/categories?active=true")

    assert response.status_code == 200
    assert "Cache-Control" in response.headers
    mock_list.assert_called_once_with(active_only=True)
