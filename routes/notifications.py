from flask import Blueprint, g, jsonify, request

from services.auth import AuthError, verify_firebase_token
from services.notification_relationships import RelationshipError, verify_push_relationship
from services.push import send_push_to_user

notifications_bp = Blueprint("notifications", __name__)

ALLOWED_TYPES = {"message", "meetup", "system"}


@notifications_bp.post("/api/notifications/push")
def post_notification_push():
    try:
        actor_id = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_id
        body = request.get_json(silent=True) or {}

        recipient_id = body.get("recipientId")
        title = body.get("title")
        message_body = body.get("body")
        notification_type = body.get("type", "system")
        listing_id = body.get("listingId")

        if not recipient_id or not title or not message_body:
            return jsonify({"error": "recipientId, title, and body are required"}), 400

        if recipient_id == actor_id:
            return jsonify({"sent": 0}), 200

        if notification_type not in ALLOWED_TYPES:
            return jsonify({"error": "Invalid notification type"}), 400

        verify_push_relationship(
            actor_id,
            str(recipient_id),
            str(notification_type),
            str(listing_id) if listing_id else None,
        )

        data = {
            "type": notification_type,
            "actorId": actor_id,
        }
        if listing_id:
            data["listingId"] = str(listing_id)

        sent = send_push_to_user(
            str(recipient_id),
            str(title),
            str(message_body),
            data,
        )
        return jsonify({"sent": sent}), 200
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except RelationshipError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except Exception:
        return jsonify({"error": "Failed to send push notification"}), 500
