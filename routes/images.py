import json
import uuid

from flask import Blueprint, Response, jsonify, request

from services.auth import AuthError, verify_firebase_token, verify_firebase_token_optional
from services.image_access import parse_community_ids
from services.image_metadata import (
    ImageAccessError,
    ImageNotFoundError,
    assert_can_view_image,
    assert_can_view_image_public,
    create_image_record,
)
from services.image_storage import build_storage_key, read_image_bytes, save_image_bytes
from services.image_validation import detect_image_content_type
from services.rate_limit import RateLimitExceeded, assert_image_upload_allowed

images_bp = Blueprint("images", __name__)

IMAGE_ID_LENGTH = 32
CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}


def _auth_error_response(exc: AuthError):
    return jsonify({"error": str(exc)}), exc.status_code


def _access_error_response(exc: ImageAccessError):
    return jsonify({"error": str(exc)}), exc.status_code


def _not_found_response(exc: ImageNotFoundError):
    return jsonify({"error": str(exc)}), exc.status_code


def _rate_limit_error_response(exc: RateLimitExceeded):
    return jsonify({"error": str(exc)}), exc.status_code


def _parse_community_ids_from_form() -> list[str]:
    raw = request.form.get("communityIds")
    if not raw:
        return parse_community_ids(None)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return parse_community_ids(raw)

    return parse_community_ids(parsed)


def _is_image_id(value: str) -> bool:
    return len(value) == IMAGE_ID_LENGTH and all(ch in "0123456789abcdef" for ch in value)


@images_bp.post("/api/images")
def upload_image():
    try:
        owner_id = verify_firebase_token(request.headers.get("Authorization"))
        assert_image_upload_allowed(owner_id)
    except AuthError as exc:
        return _auth_error_response(exc)
    except RateLimitExceeded as exc:
        return _rate_limit_error_response(exc)

    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No selected file"}), 400

    data = file.read()
    content_type = detect_image_content_type(data)
    if not content_type:
        return jsonify({"error": "Unsupported or invalid image file"}), 400

    community_ids = _parse_community_ids_from_form()
    image_id = uuid.uuid4().hex
    extension = CONTENT_TYPE_EXTENSIONS.get(content_type, "jpg")
    storage_key = build_storage_key(owner_id, image_id, extension)

    save_image_bytes(storage_key, data, content_type)
    create_image_record(
        image_id=image_id,
        owner_id=owner_id,
        community_ids=community_ids,
        storage_key=storage_key,
        content_type=content_type,
    )

    return (
        jsonify(
            {
                "imageId": image_id,
                "url": f"/api/images/{image_id}",
            }
        ),
        201,
    )


@images_bp.get("/api/images/<image_id>")
def serve_image(image_id: str):
    if not _is_image_id(image_id):
        return jsonify({"error": "Not found"}), 404

    try:
        viewer_id = verify_firebase_token_optional(request.headers.get("Authorization"))
        if viewer_id:
            record = assert_can_view_image(viewer_id, image_id)
        else:
            record = assert_can_view_image_public(image_id)
        data = read_image_bytes(record["storageKey"])
    except AuthError as exc:
        return _auth_error_response(exc)
    except ImageNotFoundError as exc:
        return _not_found_response(exc)
    except ImageAccessError as exc:
        return _access_error_response(exc)
    except FileNotFoundError:
        return jsonify({"error": "Image file missing"}), 404

    return Response(data, mimetype=record["contentType"])
