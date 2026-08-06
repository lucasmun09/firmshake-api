import os
import random
import secrets
import string

from firebase_admin import auth
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

from services.firebase_app import get_db

TEST_WORDS = (
    "apple",
    "beach",
    "brave",
    "cloud",
    "crisp",
    "delta",
    "eagle",
    "flame",
    "grape",
    "happy",
    "ivory",
    "jolly",
    "karma",
    "lemon",
    "magic",
    "noble",
    "ocean",
    "pearl",
    "quiet",
    "river",
    "spark",
    "tiger",
    "ultra",
    "vivid",
    "whale",
    "xenon",
    "yacht",
    "zebra",
    "amber",
    "blaze",
    "coral",
    "dream",
    "ember",
    "frost",
    "glide",
    "haven",
    "index",
    "jewel",
    "kiosk",
    "lunar",
    "maple",
    "nexus",
    "olive",
    "prism",
    "quest",
    "robin",
    "stone",
    "truce",
    "unity",
    "vapor",
    "wedge",
    "xylem",
    "yield",
    "zesty",
)

DEFAULT_TEST_PASSWORD = os.getenv("TEST_ACCOUNT_DEFAULT_PASSWORD", "FirmShakeTest123!")
DEFAULT_VERIFICATION_CODE = "12345"
DEFAULT_TEST_PHONE = "+15555550123"


class TestAccountError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _random_word() -> str:
    return random.choice(TEST_WORDS)


def generate_test_email() -> str:
    return f"test+{_random_word()}+{_random_word()}@gmail.com"


def _generate_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def list_test_accounts(limit: int = 50) -> list[dict]:
    db = get_db()
    query = (
        db.collection("users")
        .where(filter=FieldFilter("isTestAccount", "==", True))
        .limit(min(max(limit, 1), 200))
    )
    accounts: list[dict] = []
    for snapshot in query.stream():
        data = snapshot.to_dict() or {}
        accounts.append(
            {
                "uid": snapshot.id,
                "email": data.get("email", ""),
                "displayName": data.get("displayName", ""),
                "createdAt": _serialize_timestamp(data.get("createdAt")),
                "testPhone": data.get("testPhone", DEFAULT_TEST_PHONE),
                "verificationCode": data.get("testVerificationCode", DEFAULT_VERIFICATION_CODE),
            }
        )
    return accounts


def create_test_account(
    *,
    first_name: str = "Test",
    last_name: str = "User",
    email: str | None = None,
    password: str | None = None,
) -> dict:
    db = get_db()
    resolved_email = (email or generate_test_email()).strip().lower()
    if not resolved_email.startswith("test+") or not resolved_email.endswith("@gmail.com"):
        raise TestAccountError(
            'Test email must match test+<word>+<word>@gmail.com',
            400,
        )

    resolved_password = password or DEFAULT_TEST_PASSWORD
    if len(resolved_password) < 8:
        raise TestAccountError("Password must be at least 8 characters", 400)

    try:
        auth.get_user_by_email(resolved_email)
        raise TestAccountError(f"Email already exists: {resolved_email}", 409)
    except auth.UserNotFoundError:
        pass

    display_name = f"{first_name.strip()} {last_name.strip()}".strip() or "Test User"
    user_record = auth.create_user(
        email=resolved_email,
        password=resolved_password,
        display_name=display_name,
        email_verified=True,
    )

    profile = {
        "email": resolved_email,
        "firstName": first_name.strip() or "Test",
        "lastName": last_name.strip() or "User",
        "displayName": display_name,
        "communityIds": ["all"],
        "isAdmin": False,
        "isSuperAdmin": False,
        "moderatorCommunityIds": [],
        "profileComplete": True,
        "accountSetupComplete": True,
        "authProvider": "password",
        "isTestAccount": True,
        "testVerificationCode": DEFAULT_VERIFICATION_CODE,
        "testPhone": DEFAULT_TEST_PHONE,
        "testAccountPassword": resolved_password,
        "createdAt": firestore.SERVER_TIMESTAMP,
    }

    try:
        db.collection("users").document(user_record.uid).set(profile)
    except Exception as exc:  # noqa: BLE001
        auth.delete_user(user_record.uid)
        raise TestAccountError(f"Failed to create profile: {exc}", 500) from exc

    return {
        "uid": user_record.uid,
        "email": resolved_email,
        "password": resolved_password,
        "displayName": display_name,
        "emailVerificationCode": DEFAULT_VERIFICATION_CODE,
        "smsVerificationCode": DEFAULT_VERIFICATION_CODE,
        "testPhone": DEFAULT_TEST_PHONE,
    }


    return {
        "uid": user_record.uid,
        "email": resolved_email,
        "password": resolved_password,
        "displayName": display_name,
        "emailVerificationCode": DEFAULT_VERIFICATION_CODE,
        "smsVerificationCode": DEFAULT_VERIFICATION_CODE,
        "testPhone": DEFAULT_TEST_PHONE,
    }


def get_test_account(uid: str) -> dict:
    db = get_db()
    snapshot = db.collection("users").document(uid).get()
    if not snapshot.exists:
        raise TestAccountError("Test account not found", 404)

    data = snapshot.to_dict() or {}
    if not data.get("isTestAccount"):
        raise TestAccountError("User is not a test account", 404)

    auth_user = auth.get_user(uid)
    providers = [entry.provider_id for entry in auth_user.provider_data]

    listings = _listings_for_seller(uid)

    stored_password = data.get("testAccountPassword")
    password = stored_password or DEFAULT_TEST_PASSWORD
    password_source = "stored" if stored_password else "default"

    return {
        "uid": uid,
        "email": data.get("email", auth_user.email or ""),
        "displayName": data.get("displayName", auth_user.display_name or ""),
        "firstName": data.get("firstName", ""),
        "lastName": data.get("lastName", ""),
        "password": password,
        "passwordSource": password_source,
        "defaultPassword": DEFAULT_TEST_PASSWORD,
        "emailVerificationCode": data.get("testVerificationCode", DEFAULT_VERIFICATION_CODE),
        "smsVerificationCode": data.get("testVerificationCode", DEFAULT_VERIFICATION_CODE),
        "testPhone": data.get("testPhone", DEFAULT_TEST_PHONE),
        "communityIds": data.get("communityIds", []),
        "authProvider": data.get("authProvider", providers[0] if providers else "password"),
        "profileComplete": data.get("profileComplete", False),
        "accountSetupComplete": data.get("accountSetupComplete", False),
        "createdAt": _serialize_timestamp(data.get("createdAt")),
        "auth": {
            "emailVerified": auth_user.email_verified,
            "disabled": auth_user.disabled,
            "providers": providers,
            "lastSignIn": _serialize_timestamp(auth_user.user_metadata.last_sign_in_timestamp),
            "creationTime": _serialize_timestamp(auth_user.user_metadata.creation_timestamp),
        },
        "listings": listings,
    }


def _listings_for_seller(seller_id: str, limit: int = 100) -> list[dict]:
    db = get_db()
    query = (
        db.collection("listings")
        .where(filter=FieldFilter("sellerId", "==", seller_id))
        .limit(min(max(limit, 1), 200))
    )
    listings: list[dict] = []
    for snapshot in query.stream():
        listing = snapshot.to_dict() or {}
        location = listing.get("location")
        lat = listing.get("lat")
        lng = listing.get("lng")
        if location is not None and hasattr(location, "latitude"):
            lat = location.latitude
            lng = location.longitude

        listings.append(
            {
                "id": snapshot.id,
                "title": listing.get("title", ""),
                "description": listing.get("description", ""),
                "price": listing.get("price", 0),
                "status": listing.get("status", "active"),
                "communityIds": listing.get("communityIds", []),
                "imageUrl": listing.get("imageUrl", ""),
                "imageUrls": listing.get("imageUrls", []),
                "createdAt": _serialize_timestamp(listing.get("createdAt")),
                "location": {
                    "label": listing.get("locationLabel", ""),
                    "city": listing.get("city", ""),
                    "region": listing.get("region", ""),
                    "lat": lat,
                    "lng": lng,
                }
                if lat is not None and lng is not None
                else None,
            }
        )

    listings.sort(
        key=lambda entry: entry.get("createdAt") or "",
        reverse=True,
    )
    return listings


def _serialize_timestamp(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        from datetime import datetime, timezone

        seconds = value / 1000 if value > 1_000_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
    if isinstance(value, str):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "timestamp"):
        from datetime import datetime, timezone

        return datetime.fromtimestamp(value.timestamp(), tz=timezone.utc).isoformat()
    return str(value)
