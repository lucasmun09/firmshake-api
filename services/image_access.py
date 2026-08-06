ALL_COMMUNITY_ID = "all"


def parse_community_ids(raw_value) -> list[str]:
    if not raw_value:
        return [ALL_COMMUNITY_ID]
    if isinstance(raw_value, str):
        parts = [part.strip() for part in raw_value.split(",") if part.strip()]
        return parts or [ALL_COMMUNITY_ID]
    if isinstance(raw_value, list):
        ids = [str(item).strip() for item in raw_value if str(item).strip()]
        return ids or [ALL_COMMUNITY_ID]
    return [ALL_COMMUNITY_ID]


def is_public_image(image_community_ids: list[str]) -> bool:
    return ALL_COMMUNITY_ID in set(image_community_ids or [ALL_COMMUNITY_ID])


def can_view_image(viewer_id: str, owner_id: str, image_community_ids: list[str], user_community_ids: list[str]) -> bool:
    if viewer_id == owner_id:
        return True

    image_communities = set(image_community_ids or [ALL_COMMUNITY_ID])
    if ALL_COMMUNITY_ID in image_communities:
        return True

    user_communities = set(user_community_ids or [])
    return bool(image_communities & user_communities)
