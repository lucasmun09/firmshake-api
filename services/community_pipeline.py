"""Community list/create/join/leave mirroring firmshake client communities.ts + users.ts."""

import logging

from google.cloud import firestore

from services.authorization import ALL_COMMUNITY_ID, get_user_profile
from services.firebase_app import get_db
from services.user_pipeline import UserPipelineError

logger = logging.getLogger("firmshake.community_pipeline")


class CommunityPipelineError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _map_community(doc_id: str, data: dict) -> dict:
    return {
        "id": doc_id,
        "name": str(data.get("name") or ""),
        "type": data.get("type") or "user",
        "description": str(data.get("description") or ""),
    }


def _sort_communities(communities: list[dict]) -> list[dict]:
    def sort_key(community: dict) -> tuple:
        if community["id"] == ALL_COMMUNITY_ID:
            return (0, community["name"].lower())
        return (1, community["name"].lower())

    return sorted(communities, key=sort_key)


def list_communities() -> list[dict]:
    db = get_db()
    snapshot = db.collection("communities").stream()
    communities = [_map_community(doc.id, doc.to_dict() or {}) for doc in snapshot]
    return _sort_communities(communities)


def create_community(actor_uid: str, name: str, description: str) -> dict:
    trimmed_name = name.strip()
    trimmed_description = description.strip()
    if not trimmed_name:
        raise CommunityPipelineError("Community name is required")

    db = get_db()
    _, doc_ref = db.collection("communities").add(
        {
            "name": trimmed_name,
            "type": "user",
            "description": trimmed_description,
            "createdBy": actor_uid,
            "memberCount": 1,
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
    )

    join_community(actor_uid, doc_ref.id)
    snapshot = doc_ref.get()
    return _map_community(doc_ref.id, snapshot.to_dict() or {})


def join_community(uid: str, community_id: str) -> dict:
    db = get_db()
    community_ref = db.collection("communities").document(community_id)
    if not community_ref.get().exists:
        raise CommunityPipelineError("Community not found", 404)

    user_ref = db.collection("users").document(uid)
    user_snapshot = user_ref.get()
    if not user_snapshot.exists:
        raise UserPipelineError("User profile not found", 404)

    profile = user_snapshot.to_dict() or {}
    community_ids = [str(cid) for cid in (profile.get("communityIds") or ["all"])]
    if community_id in community_ids:
        return _map_profile_community_ids(uid, profile)

    user_ref.update({"communityIds": community_ids + [community_id]})
    refreshed = user_ref.get()
    return _map_profile_community_ids(uid, refreshed.to_dict() or {})


def leave_community(uid: str, community_id: str) -> dict:
    if community_id == ALL_COMMUNITY_ID:
        raise CommunityPipelineError("Cannot leave the All community")

    db = get_db()
    user_ref = db.collection("users").document(uid)
    user_snapshot = user_ref.get()
    if not user_snapshot.exists:
        raise UserPipelineError("User profile not found", 404)

    profile = user_snapshot.to_dict() or {}
    community_ids = [str(cid) for cid in (profile.get("communityIds") or ["all"])]
    user_ref.update({"communityIds": [cid for cid in community_ids if cid != community_id]})
    refreshed = user_ref.get()
    return _map_profile_community_ids(uid, refreshed.to_dict() or {})


def _map_profile_community_ids(uid: str, profile: dict) -> dict:
    return {
        "uid": uid,
        "communityIds": [str(cid) for cid in (profile.get("communityIds") or ["all"])],
    }


def list_categories() -> list[dict]:
    db = get_db()
    snapshot = (
        db.collection("categories")
        .order_by("sortOrder")
        .stream()
    )
    categories = []
    for doc in snapshot:
        data = doc.to_dict() or {}
        categories.append(
            {
                "id": doc.id,
                "name": str(data.get("name") or doc.id),
                "slug": str(data.get("slug") or doc.id),
                "parentId": data.get("parentId"),
                "sortOrder": data.get("sortOrder"),
            }
        )
    return categories
