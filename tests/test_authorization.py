import pytest

from services.authorization import (
    ALL_COMMUNITY_ID,
    can_lookup_user_by_email,
    can_manage_community_moderators,
    can_modify_target_moderator_access,
    can_moderate_listing,
    can_remove_listing,
    can_sync_listing_search,
    can_update_listing,
    can_write_listing,
    is_community_moderator,
    is_super_admin,
)


def test_is_super_admin():
    assert is_super_admin({"isSuperAdmin": True}) is True
    assert is_super_admin({"isAdmin": True}) is True
    assert is_super_admin({"isSuperAdmin": False}) is False


def test_can_moderate_listing_for_community_moderator():
    listing = {"status": "active", "communityIds": ["neighborhood-a", ALL_COMMUNITY_ID]}
    profile = {"moderatorCommunityIds": ["neighborhood-a"]}
    assert can_moderate_listing(profile, listing) is True


def test_can_remove_listing_seller_or_moderator():
    listing = {"status": "active", "communityIds": ["neighborhood-a"], "sellerId": "seller-1"}
    seller_profile = {"moderatorCommunityIds": []}
    mod_profile = {"moderatorCommunityIds": ["neighborhood-a"]}

    assert can_remove_listing(seller_profile, listing, "seller-1") is True
    assert can_remove_listing(mod_profile, listing, "mod-1") is True
    assert can_remove_listing(seller_profile, listing, "other-user") is False


def test_can_update_listing_requires_active_seller():
    listing = {"status": "active", "sellerId": "seller-1"}
    assert can_update_listing("seller-1", listing) is True
    assert can_update_listing("other-user", listing) is False


def test_can_sync_listing_search_seller_or_moderator():
    listing = {"status": "active", "communityIds": ["neighborhood-a"], "sellerId": "seller-1"}
    seller_profile = {"moderatorCommunityIds": []}
    mod_profile = {"moderatorCommunityIds": ["neighborhood-a"]}

    assert can_sync_listing_search(seller_profile, "seller-1", listing) is True
    assert can_sync_listing_search(mod_profile, "mod-1", listing) is True
    assert can_sync_listing_search(seller_profile, "other-user", listing) is False


def test_is_community_moderator_single_or_multiple_ids():
    profile = {"moderatorCommunityIds": ["neighborhood-a"]}
    assert is_community_moderator(profile, "neighborhood-a") is True
    assert is_community_moderator(profile, "neighborhood-b") is False
    assert is_community_moderator(profile, ["neighborhood-b", "neighborhood-a"]) is True
    assert is_community_moderator(profile, ALL_COMMUNITY_ID) is False


def test_is_community_moderator_super_admin():
    profile = {"isSuperAdmin": True, "moderatorCommunityIds": []}
    assert is_community_moderator(profile, "neighborhood-a") is True


def test_can_write_listing_active_seller_only():
    listing = {"status": "active", "sellerId": "seller-1"}
    assert can_write_listing("seller-1", listing) is True
    assert can_write_listing("other-user", listing) is False
    assert can_write_listing("seller-1", {"status": "removed", "sellerId": "seller-1"}) is False


def test_can_manage_community_moderators():
    mod_profile = {"moderatorCommunityIds": ["neighborhood-a"]}
    assert can_manage_community_moderators(mod_profile, "neighborhood-a") is True
    assert can_manage_community_moderators(mod_profile, ALL_COMMUNITY_ID) is False
    assert can_manage_community_moderators({"isSuperAdmin": True}, ALL_COMMUNITY_ID) is True


def test_can_lookup_user_by_email():
    assert can_lookup_user_by_email({"isSuperAdmin": True}) is True
    assert can_lookup_user_by_email({"moderatorCommunityIds": ["neighborhood-a"]}) is True
    assert can_lookup_user_by_email({"moderatorCommunityIds": []}) is False


def test_can_modify_target_moderator_access():
    actor = {"isSuperAdmin": True}
    target = {"moderatorCommunityIds": ["neighborhood-a"]}
    super_target = {"isSuperAdmin": True}
    assert can_modify_target_moderator_access(actor, target) is True
    assert can_modify_target_moderator_access(actor, super_target) is False


def test_can_remove_listing_client_signature():
    listing = {"status": "active", "communityIds": ["neighborhood-a"], "sellerId": "seller-1"}
    seller_profile = {"uid": "seller-1", "moderatorCommunityIds": []}
    mod_profile = {"uid": "mod-1", "moderatorCommunityIds": ["neighborhood-a"]}

    assert can_remove_listing(seller_profile, listing) is True
    assert can_remove_listing(mod_profile, listing) is True
    assert can_remove_listing(seller_profile, listing, "other-user") is False
