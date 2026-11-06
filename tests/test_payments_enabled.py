"""Unit tests for PAYMENTS_ENABLED / deposit gating."""

from unittest.mock import patch

import pytest

from services.payments_flag import PAYMENTS_DISABLED_MESSAGE, are_payments_enabled
from services.agreement_pipeline import AgreementPipelineError, create_deposit
from services.stripe_deposits import is_stripe_configured


def test_are_payments_enabled_defaults_true(monkeypatch):
    monkeypatch.delenv("PAYMENTS_ENABLED", raising=False)
    monkeypatch.delenv("STRIPE_PAYMENTS_ENABLED", raising=False)
    assert are_payments_enabled() is True


def test_are_payments_enabled_false(monkeypatch):
    monkeypatch.delenv("STRIPE_PAYMENTS_ENABLED", raising=False)
    monkeypatch.setenv("PAYMENTS_ENABLED", "false")
    assert are_payments_enabled() is False


def test_stripe_alias_overrides_payments_enabled(monkeypatch):
    monkeypatch.setenv("PAYMENTS_ENABLED", "true")
    monkeypatch.setenv("STRIPE_PAYMENTS_ENABLED", "0")
    assert are_payments_enabled() is False


def test_is_stripe_configured_false_when_payments_disabled(monkeypatch):
    monkeypatch.setenv("PAYMENTS_ENABLED", "false")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")
    # Re-import module-level keys are already cached; is_stripe_configured
    # still gates on are_payments_enabled().
    assert is_stripe_configured() is False


def test_create_deposit_rejects_when_payments_disabled(monkeypatch):
    monkeypatch.setenv("PAYMENTS_ENABLED", "false")
    with pytest.raises(AgreementPipelineError) as exc_info:
        create_deposit("buyer-1", "agreement-1", {})
    assert exc_info.value.status_code == 503
    assert "unavailable" in str(exc_info.value).lower()
    assert str(exc_info.value) == PAYMENTS_DISABLED_MESSAGE


def test_stripe_webhook_disabled_mode(client, monkeypatch):
    monkeypatch.setenv("PAYMENTS_ENABLED", "false")
    with patch("routes.v1.agreements.are_payments_enabled", return_value=False):
        response = client.post("/api/v1/webhooks/stripe", data=b"{}")
    assert response.status_code == 200
    assert response.get_json()["mode"] == "disabled"


def test_deposit_route_returns_503_when_payments_disabled(client, monkeypatch):
    monkeypatch.setenv("PAYMENTS_ENABLED", "false")
    with patch("routes.v1.agreements.verify_firebase_token", return_value="buyer-1"):
        with patch(
            "routes.v1.agreements.create_deposit",
            side_effect=AgreementPipelineError(PAYMENTS_DISABLED_MESSAGE, 503),
        ):
            response = client.post(
                "/api/v1/agreements/agreement-1/deposit",
                headers={"Authorization": "Bearer fake-token"},
            )
    assert response.status_code == 503
    body = response.get_json()
    assert "unavailable" in str(body.get("error", "")).lower()


def test_deposit_pipeline_503_via_real_gate(client, monkeypatch):
    """End-to-end gate: route → create_deposit → payments flag (no Stripe)."""
    monkeypatch.setenv("PAYMENTS_ENABLED", "false")
    monkeypatch.delenv("STRIPE_PAYMENTS_ENABLED", raising=False)
    with patch("routes.v1.agreements.verify_firebase_token", return_value="buyer-1"):
        # Do not mock create_deposit — exercise the real payments-disabled raise.
        response = client.post(
            "/api/v1/agreements/agreement-1/deposit",
            headers={"Authorization": "Bearer fake-token"},
        )
    assert response.status_code == 503
    assert "unavailable" in str(response.get_json().get("error", "")).lower()
