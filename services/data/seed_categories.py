"""Default marketplace categories — mirrors firmshake web SEED_CATEGORIES."""

SEED_CATEGORIES: list[dict] = [
    {"id": "general", "name": "General", "slug": "general", "sortOrder": 0, "active": True},
    {"id": "electronics", "name": "Electronics", "slug": "electronics", "sortOrder": 10, "active": True},
    {
        "id": "phones",
        "name": "Phones & Tablets",
        "slug": "phones",
        "parentId": "electronics",
        "sortOrder": 11,
        "active": True,
    },
    {
        "id": "computers",
        "name": "Computers",
        "slug": "computers",
        "parentId": "electronics",
        "sortOrder": 12,
        "active": True,
    },
    {"id": "home", "name": "Home & Garden", "slug": "home", "sortOrder": 20, "active": True},
    {
        "id": "furniture",
        "name": "Furniture",
        "slug": "furniture",
        "parentId": "home",
        "sortOrder": 21,
        "active": True,
    },
    {"id": "clothing", "name": "Clothing & Accessories", "slug": "clothing", "sortOrder": 30, "active": True},
    {"id": "sports", "name": "Sports & Outdoors", "slug": "sports", "sortOrder": 40, "active": True},
    {"id": "vehicles", "name": "Vehicles", "slug": "vehicles", "sortOrder": 50, "active": True},
    {"id": "books", "name": "Books & Media", "slug": "books", "sortOrder": 60, "active": True},
    {"id": "toys", "name": "Toys & Games", "slug": "toys", "sortOrder": 70, "active": True},
    {"id": "services", "name": "Services", "slug": "services", "sortOrder": 80, "active": True},
]
