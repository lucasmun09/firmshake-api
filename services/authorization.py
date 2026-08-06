"""Authorization helpers mirroring firmshake client moderation.ts."""

ALL_COMMUNITY_ID = "all"
DEFAULT_CATEGORY_ID = "general"


class AuthorizationError(Exception):
    def __init__(self, message: str, status_code: int = 403):
        super().__init__(message)
        self.status_code = status_code


def get_user_profile(db, uid: str) -> dict | None:
    snapshot = db.collection("users").document(uid).get()
    if not snapshot.exists:
        return None
    return snapshot.to_dict() or {}


def is_super_admin(profile: dict | None) -> bool:
    if not profile:
        return False
    return bool(profile.get("isSuperAdmin") or profile.get("isAdmin"))


def is_community_moderator(
    profile: dict | None,
    community_ids: str | list[str],
) -> bool:
    """True when profile moderates the given community or any id in the list."""
    if isinstance(community_ids, str):
        return _is_community_moderator_for_id(profile, community_ids)
    return any(_is_community_moderator_for_id(profile, community_id) for community_id in community_ids)


def _is_community_moderator_for_id(profile: dict | None, community_id: str) -> bool:
    if not profile or community_id == ALL_COMMUNITY_ID:
        return False
    if is_super_admin(profile):
        return True
    moderator_ids = profile.get("moderatorCommunityIds") or []
    return community_id in moderator_ids


def listing_moderatable_community_ids(listing: dict) -> list[str]:
    community_ids = listing.get("communityIds") or []
    return [cid for cid in community_ids if cid != ALL_COMMUNITY_ID]


def can_moderate_listing(profile: dict | None, listing: dict) -> bool:
    if not profile or listing.get("status") != "active":
        return False
    if is_super_admin(profile):
        return True

    moderatable = listing_moderatable_community_ids(listing)
    if not moderatable:
        return False

    moderator_ids = set(profile.get("moderatorCommunityIds") or [])
    return any(community_id in moderator_ids for community_id in moderatable)


def can_delist_own_listing(profile_uid: str, listing: dict) -> bool:
    if listing.get("status") != "active":
        return False
    return listing.get("sellerId") == profile_uid


def can_remove_listing(
    user_profile: dict | None,
    listing: dict,
    user_uid: str | None = None,
    *,
    profile_uid: str | None = None,
) -> bool:
    """Mirror client canRemoveListing(profile, listing). Accepts uid as 3rd arg or profile_uid kwarg."""
    actor_uid = user_uid or profile_uid
    if actor_uid is None:
        actor_uid = user_profile.get("uid") if user_profile else None
    if not actor_uid:
        return False
    return can_delist_own_listing(actor_uid, listing) or can_moderate_listing(
        user_profile, listing
    )


def can_write_listing(user_uid: str, listing: dict) -> bool:
    """Seller may update an active listing they own."""
    return can_update_listing(user_uid, listing)


def can_update_listing(user_uid: str, listing: dict) -> bool:
    return listing.get("status") == "active" and listing.get("sellerId") == user_uid


def can_sync_listing_search(profile: dict | None, profile_uid: str, listing: dict) -> bool:
    """Seller or community moderator may sync search index for a listing."""
    if listing.get("sellerId") == profile_uid:
        return True
    return can_moderate_listing(profile, listing)


def can_manage_community_moderators(profile: dict | None, community_id: str) -> bool:
    """Mirror client canManageCommunityModerators(profile, communityId)."""
    if community_id == ALL_COMMUNITY_ID:
        return is_super_admin(profile)
    return is_community_moderator(profile, community_id)


def can_modify_target_moderator_access(actor: dict | None, target: dict | None) -> bool:
    """Mirror client canModifyTargetModeratorAccess — super-admin only, not for super-admin targets."""
    if not actor or not target:
        return False
    if is_super_admin(target):
        return False
    return is_super_admin(actor)


def can_lookup_user_by_email(profile: dict | None) -> bool:
    """Moderator or super-admin may look up users by email (rate limited at route layer)."""
    if not profile:
        return False
    if is_super_admin(profile):
        return True
    moderator_ids = profile.get("moderatorCommunityIds") or []
    return len(moderator_ids) > 0
