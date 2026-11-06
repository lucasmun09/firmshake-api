#!/usr/bin/env python3
"""Seed Firestore categories from SEED_CATEGORIES."""

from __future__ import annotations

import argparse

from google.cloud import firestore

from services.data.seed_categories import SEED_CATEGORIES
from services.firebase_app import get_db


def seed_categories(*, dry_run: bool = False) -> int:
    db = get_db()
    batch = db.batch()
    count = 0

    for entry in SEED_CATEGORIES:
        ref = db.collection("categories").document(entry["id"])
        payload = {
            "name": entry["name"],
            "slug": entry["slug"],
            "sortOrder": entry.get("sortOrder", 0),
            "active": entry.get("active", True),
        }
        if entry.get("parentId"):
            payload["parentId"] = entry["parentId"]

        if dry_run:
            print(f"would seed categories/{entry['id']}: {payload}")
        else:
            batch.set(ref, payload, merge=True)
        count += 1

    if not dry_run:
        batch.commit()

    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Firestore categories collection")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing")
    args = parser.parse_args()

    written = seed_categories(dry_run=args.dry_run)
    action = "Would seed" if args.dry_run else "Seeded"
    print(f"{action} {written} categories")


if __name__ == "__main__":
    main()
