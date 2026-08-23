"""Unit tests for PAYMENTS_ENABLED / deposit gating."""

from unittest.mock import patch

import pytest

from config import are_payments_enabled
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
    assert "disabled" in str(exc_info.value).lower()


def test_stripe_webhook_disabled_mode(client, monkeypatch):
    monkeypatch.setenv("PAYMENTS_ENABLED", "false")
    with patch("routes.v1.agreements.are_payments_enabled", return_value=False):
        response = client.post("/api/v1/webhooks/stripe", data=b"{}")
    assert response.status_code == 200
    assert response.get_json()["mode"] == "disabled"
