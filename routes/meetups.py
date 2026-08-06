from flask import Blueprint, jsonify, request

from services.auth import AuthError
from services.auth import verify_firebase_token
from services.meetups import MeetupError, update_meetup_location

meetups_bp = Blueprint("meetups", __name__)


@meetups_bp.post("/api/meetups/<agreement_id>/location")
def post_meetup_location(agreement_id: str):
    try:
        user_id = verify_firebase_token(request.headers.get("Authorization"))
        body = request.get_json(silent=True) or {}

        lat = body.get("lat")
        lng = body.get("lng")
        if lat is None or lng is None:
            return jsonify({"error": "lat and lng are required"}), 400

        result = update_meetup_location(
            agreement_id,
            user_id,
            float(lat),
            float(lng),
        )
        return jsonify(result), 200
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except MeetupError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except Exception:
        return jsonify({"error": "Failed to update meetup location"}), 500
