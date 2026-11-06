from flask import Blueprint, jsonify, request

from services.recaptcha import RecaptchaError, is_recaptcha_configured, verify_recaptcha_token

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/api/auth/verify-recaptcha")
def verify_recaptcha():
    payload = request.get_json(silent=True) or {}
    token = payload.get("token")
    action = payload.get("action")

    if not isinstance(action, str) or not action.strip():
        return jsonify({"error": "Missing reCAPTCHA action"}), 400

    try:
        verify_recaptcha_token(
            token if isinstance(token, str) else None,
            action.strip(),
        )
    except RecaptchaError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    return jsonify({"ok": True, "configured": is_recaptcha_configured()})
