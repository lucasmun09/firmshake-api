from google.cloud.firestore_v1.base_query import FieldFilter

from firebase_admin import firestore

from services.firebase_app import get_db
from services.image_access import ALL_COMMUNITY_ID, can_view_image, is_public_image, parse_community_ids


class ImageAccessError(Exception):
    def __init__(self, message: str, status_code: int = 403):
        super().__init__(message)
        self.status_code = status_code


class ImageNotFoundError(Exception):
    def __init__(self, message: str = "Image not found", status_code: int = 404):
        super().__init__(message)
        self.status_code = status_code


def _images_collection():
    return get_db().collection("images")


def create_image_record(
    image_id: str,
    owner_id: str,
    community_ids: list[str],
    storage_key: str,
    content_type: str,
) -> dict:
    community_ids = parse_community_ids(community_ids)
    record = {
        "ownerId": owner_id,
        "communityIds": community_ids,
        "storageKey": storage_key,
        "contentType": content_type,
        "createdAt": firestore.SERVER_TIMESTAMP,
    }
    _images_collection().document(image_id).set(record)
    return {**record, "imageId": image_id}


def get_image_record(image_id: str) -> dict:
    snapshot = _images_collection().document(image_id).get()
    if not snapshot.exists:
        raise ImageNotFoundError()

    data = snapshot.to_dict() or {}
    return {
        "imageId": image_id,
        "ownerId": str(data.get("ownerId") or ""),
        "communityIds": parse_community_ids(data.get("communityIds")),
        "storageKey": str(data.get("storageKey") or ""),
        "contentType": str(data.get("contentType") or "application/octet-stream"),
    }


def get_user_community_ids(user_id: str) -> list[str]:
    snapshot = get_db().collection("users").document(user_id).get()
    if not snapshot.exists:
        return [ALL_COMMUNITY_ID]

    data = snapshot.to_dict() or {}
    return parse_community_ids(data.get("communityIds"))


def is_image_on_active_listing(image_id: str) -> bool:
    image_url = f"/api/images/{image_id}"
    snapshots = (
        get_db()
        .collection("listings")
        .where(filter=FieldFilter("imageUrls", "array-contains", image_url))
        .limit(5)
        .stream()
    )
    for snapshot in snapshots:
        data = snapshot.to_dict() or {}
        if data.get("status") == "active":
            return True
    return False


def assert_can_view_image(viewer_id: str, image_id: str) -> dict:
    record = get_image_record(image_id)
    if viewer_id == record["ownerId"]:
        return record

    user_community_ids = get_user_community_ids(viewer_id)
    if not can_view_image(
        viewer_id,
        record["ownerId"],
        record["communityIds"],
        user_community_ids,
    ):
        raise ImageAccessError("You do not have access to this image")
    return record


def assert_can_view_image_public(image_id: str) -> dict:
    record = get_image_record(image_id)
    if is_public_image(record["communityIds"]):
        return record
    if is_image_on_active_listing(image_id):
        return record
    raise ImageAccessError("You do not have access to this image")
