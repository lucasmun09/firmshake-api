from flask import Blueprint, jsonify

from services.health_payload import build_health_payload

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    return jsonify(build_health_payload())
