#!/usr/bin/env python3
"""Backfill active listings into Typesense search index."""

from __future__ import annotations

import argparse

from services.browse_search import TypesenseClient, map_feed_doc
from services.firebase_app import get_db
from services.listing_pipeline import _sync_search_index


def backfill_typesense(*, limit: int | None = None, dry_run: bool = False) -> tuple[int, int]:
    client = TypesenseClient()
    if not client.enabled:
        raise RuntimeError(
            "Typesense is not configured. Set TYPESENSE_HOST and TYPESENSE_API_KEY."
        )

    db = get_db()
    query = db.collection("listings").where("status", "==", "active")
    if limit is not None:
        query = query.limit(limit)

    synced = 0
    skipped = 0

    for snapshot in query.stream():
        listing_id = snapshot.id
        data = snapshot.to_dict() or {}
        if data.get("status") != "active":
            skipped += 1
            continue

        created_at = data.get("createdAt")
        created_ms = 0
        if created_at is not None and hasattr(created_at, "timestamp"):
            created_ms = int(created_at.timestamp() * 1000)

        location = data.get("location")
        lat = data.get("lat")
        lng = data.get("lng")
        if location is not None and hasattr(location, "latitude"):
            lat = location.latitude
            lng = location.longitude

        listing = {
            **data,
            "createdAtMs": created_ms,
        }
        if lat is not None and lng is not None:
            listing["location"] = {
                "lat": lat,
                "lng": lng,
                "geohash": data.get("geohash"),
                "city": data.get("city"),
                "region": data.get("region"),
            }

        if dry_run:
            doc = map_feed_doc(listing_id, data)
            print(f"would upsert {listing_id}: {doc.get('title')}")
        else:
            _sync_search_index(listing_id, listing)

        synced += 1

    return synced, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Typesense listings index from Firestore")
    parser.add_argument("--limit", type=int, default=None, help="Max listings to sync")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing")
    args = parser.parse_args()

    synced, skipped = backfill_typesense(limit=args.limit, dry_run=args.dry_run)
    action = "Would sync" if args.dry_run else "Synced"
    print(f"{action} {synced} listings ({skipped} skipped)")


if __name__ == "__main__":
    main()
