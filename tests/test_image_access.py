import pytest

from services.image_access import (
    ALL_COMMUNITY_ID,
    can_view_image,
    parse_community_ids,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, [ALL_COMMUNITY_ID]),
        ("", [ALL_COMMUNITY_ID]),
        ("church, school", ["church", "school"]),
        (["church", "school"], ["church", "school"]),
        (["  ", ""], [ALL_COMMUNITY_ID]),
    ],
)
def test_parse_community_ids(raw, expected):
    assert parse_community_ids(raw) == expected


def test_owner_can_always_view():
    assert can_view_image("u1", "u1", ["private-club"], ["other"]) is True


def test_all_community_image_visible_to_any_authenticated_viewer():
    assert can_view_image("u2", "u1", [ALL_COMMUNITY_ID], ["school-only"]) is True


def test_shared_community_allows_view():
    assert can_view_image("u2", "u1", ["church"], ["church", "all"]) is True


def test_no_shared_community_denies_view():
    assert can_view_image("u2", "u1", ["church"], ["school"]) is False


def test_empty_user_communities_without_all_image_tag_denies_view():
    assert can_view_image("u2", "u1", ["church"], []) is False
