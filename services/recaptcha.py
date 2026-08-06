import json
import os
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import google.auth
import google.auth.transport.requests

from config import FIREBASE_PROJECT_ID

RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "").strip()
RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY", "").strip()
RECAPTCHA_PROJECT_ID = os.getenv("RECAPTCHA_PROJECT_ID", FIREBASE_PROJECT_ID).strip()
RECAPTCHA_MIN_SCORE = float(os.getenv("RECAPTCHA_MIN_SCORE", "0.5"))
RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


class RecaptchaError(Exception):
    def __init__(self, message: str, status_code: int = 403):
        super().__init__(message)
        self.status_code = status_code


def is_recaptcha_configured() -> bool:
    if RECAPTCHA_SECRET_KEY:
        return True
    return bool(RECAPTCHA_SITE_KEY and RECAPTCHA_PROJECT_ID)


def verify_recaptcha_token(token: str | None, action: str | None = None) -> None:
    if not is_recaptcha_configured():
        return

    if not token or not token.strip():
        raise RecaptchaError("Missing reCAPTCHA token", 400)

    cleaned = token.strip()
    if RECAPTCHA_SECRET_KEY:
        _verify_classic(cleaned, action)
    else:
        _verify_enterprise(cleaned, action)


def _verify_classic(token: str, action: str | None) -> None:
    payload = urlencode(
        {
            "secret": RECAPTCHA_SECRET_KEY,
            "response": token,
        }
    ).encode("utf-8")

    try:
        request = Request(
            RECAPTCHA_VERIFY_URL,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urlopen(request, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RecaptchaError("Could not verify reCAPTCHA", 503) from exc

    if not body.get("success"):
        raise RecaptchaError("reCAPTCHA verification failed")

    if action and body.get("action") and body.get("action") != action:
        raise RecaptchaError("reCAPTCHA action mismatch")

    score = body.get("score")
    if score is not None and float(score) < RECAPTCHA_MIN_SCORE:
        raise RecaptchaError("reCAPTCHA score too low")


def _verify_enterprise(token: str, action: str | None) -> None:
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    auth_request = google.auth.transport.requests.Request()
    credentials.refresh(auth_request)

    event: dict[str, str] = {
        "token": token,
        "siteKey": RECAPTCHA_SITE_KEY,
    }
    if action:
        event["expectedAction"] = action

    assessment_url = (
        f"https://recaptchaenterprise.googleapis.com/v1/projects/"
        f"{RECAPTCHA_PROJECT_ID}/assessments"
    )

    try:
        request = Request(
            assessment_url,
            data=json.dumps({"event": event}).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json",
            },
        )
        with urlopen(request, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RecaptchaError("Could not verify reCAPTCHA", 503) from exc

    token_properties = body.get("tokenProperties") or {}
    if not token_properties.get("valid"):
        invalid_reason = token_properties.get("invalidReason", "unknown")
        raise RecaptchaError(f"reCAPTCHA verification failed ({invalid_reason})")

    if action and token_properties.get("action") and token_properties.get("action") != action:
        raise RecaptchaError("reCAPTCHA action mismatch")

    score = (body.get("riskAnalysis") or {}).get("score")
    if score is not None and float(score) < RECAPTCHA_MIN_SCORE:
        raise RecaptchaError("reCAPTCHA score too low")
