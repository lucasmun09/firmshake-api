import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

images_bp = Blueprint("images", __name__)


def _allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


@images_bp.post("/api/images")
def upload_image():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No selected file"}), 400

    if not _allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type"}), 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    storage_dir: Path = current_app.config["STORAGE_DIR"]
    file.save(storage_dir / filename)

    return jsonify(
        {
            "filename": filename,
            "url": f"/api/images/{filename}",
        }
    ), 201


@images_bp.get("/api/images/<filename>")
def serve_image(filename: str):
    safe_name = secure_filename(filename)
    storage_dir: Path = current_app.config["STORAGE_DIR"]
    return send_from_directory(storage_dir, safe_name)
