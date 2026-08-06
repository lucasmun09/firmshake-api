from datetime import datetime, timezone

from services.auth import AuthError, verify_firebase_token
from services.eta import eta_from_coordinates
from services.firebase_app import get_db


class MeetupError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def update_meetup_location(
    agreement_id: str,
    user_id: str,
    lat: float,
    lng: float,
) -> dict:
    db = get_db()
    doc_ref = db.collection("agreements").document(agreement_id)
    snapshot = doc_ref.get()

    if not snapshot.exists:
        raise MeetupError("Meetup agreement not found", 404)

    agreement = snapshot.to_dict() or {}
    buyer_id = agreement.get("buyerId")
    seller_id = agreement.get("sellerId")
    meetup_lat = agreement.get("meetupLat")
    meetup_lng = agreement.get("meetupLng")

    if user_id not in {buyer_id, seller_id}:
        raise MeetupError("You are not part of this meetup", 403)

    if meetup_lat is None or meetup_lng is None:
        raise MeetupError("Meetup location is not set", 400)

    status = agreement.get("status")
    if status != "en_route":
        raise MeetupError("Location sharing is only available when en route", 400)

    eta_minutes, progress_percent, _distance = eta_from_coordinates(
        lat, lng, float(meetup_lat), float(meetup_lng)
    )

    role = "buyer" if user_id == buyer_id else "seller"
    now = datetime.now(timezone.utc)

    updates = {
        f"{role}EtaMinutes": eta_minutes,
        f"{role}ProgressPercent": progress_percent,
        f"{role}LastUpdatedAt": now,
        "updatedAt": now,
    }

    doc_ref.update(updates)

    other_role = "seller" if role == "buyer" else "buyer"
    return {
        "role": role,
        "etaMinutes": eta_minutes,
        "progressPercent": progress_percent,
        "otherParty": {
            "etaMinutes": agreement.get(f"{other_role}EtaMinutes"),
            "progressPercent": agreement.get(f"{other_role}ProgressPercent"),
        },
    }
