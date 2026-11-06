from flask import Blueprint, jsonify

from services.health_payload import build_health_payload, build_ready_payload

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    return jsonify(build_health_payload())


@health_bp.get("/ready")
def ready():
    """Readiness probe — stack identity + payments gate; no secret fields."""
    return jsonify(build_ready_payload())
