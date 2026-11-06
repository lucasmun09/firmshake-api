import json
from unittest.mock import MagicMock, patch

import pytest

from services.recaptcha import RecaptchaError, verify_recaptcha_token


@pytest.fixture(autouse=True)
def recaptcha_secret(monkeypatch):
    monkeypatch.delenv("RECAPTCHA_SITE_KEY", raising=False)
    monkeypatch.setenv("RECAPTCHA_SECRET_KEY", "test-secret")


def test_verify_recaptcha_accepts_valid_response():
    response_body = b'{"success": true, "score": 0.9, "action": "login"}'

    with patch("services.recaptcha.urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = response_body
        verify_recaptcha_token("token-123", "login")


def test_verify_recaptcha_rejects_low_score():
    response_body = b'{"success": true, "score": 0.1, "action": "login"}'

    with patch("services.recaptcha.urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = response_body
        with pytest.raises(RecaptchaError, match="score too low"):
            verify_recaptcha_token("token-123", "login")


def test_verify_recaptcha_route(client):
    response_body = b'{"success": true, "score": 0.9, "action": "login"}'

    with patch("services.recaptcha.urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = response_body
        response = client.post(
            "/api/auth/verify-recaptcha",
            json={"token": "token-123", "action": "login"},
        )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True


def test_verify_recaptcha_enterprise(monkeypatch):
    monkeypatch.delenv("RECAPTCHA_SECRET_KEY", raising=False)
    monkeypatch.setenv("RECAPTCHA_SITE_KEY", "site-key")
    monkeypatch.setenv("RECAPTCHA_PROJECT_ID", "firmshake-dev")

    response_body = json.dumps(
        {
            "tokenProperties": {"valid": True, "action": "register"},
            "riskAnalysis": {"score": 0.9},
        }
    ).encode("utf-8")

    credentials = MagicMock()
    credentials.token = "access-token"

    with patch("services.recaptcha.google.auth.default", return_value=(credentials, None)):
        with patch("services.recaptcha.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = response_body
            verify_recaptcha_token("token-123", "register")
