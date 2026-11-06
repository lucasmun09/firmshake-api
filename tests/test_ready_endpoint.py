"""GET /ready readiness contract (dual-stack, no secrets)."""

from __future__ import annotations


def test_ready_payload_devo(client, monkeypatch):
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "firmshake-dev")
    monkeypatch.delenv("APP_STACK", raising=False)
    monkeypatch.delenv("STRIPE_PAYMENTS_ENABLED", raising=False)
    monkeypatch.setenv("PAYMENTS_ENABLED", "true")

    response = client.get("/ready")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["service"] == "firmshake-api"
    assert body["stack"] == "devo"
    assert body["firebaseProjectId"] == "firmshake-dev"
    assert body["paymentsEnabled"] is True
    assert body["ready"] is True
    assert "secret" not in str(body).lower()
    assert "stripe" not in str(body).lower()


def test_ready_payload_prod_payments_disabled(client, monkeypatch):
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "firmshake-prod")
    monkeypatch.delenv("APP_STACK", raising=False)
    monkeypatch.delenv("STRIPE_PAYMENTS_ENABLED", raising=False)
    monkeypatch.setenv("PAYMENTS_ENABLED", "false")

    response = client.get("/ready")
    assert response.status_code == 200
    body = response.get_json()
    assert body["stack"] == "prod"
    assert body["firebaseProjectId"] == "firmshake-prod"
    assert body["paymentsEnabled"] is False
    assert body["ready"] is True


def test_health_does_not_require_ready_field(client, monkeypatch):
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "firmshake-dev")
    monkeypatch.delenv("APP_STACK", raising=False)
    monkeypatch.setenv("PAYMENTS_ENABLED", "true")

    body = client.get("/health").get_json()
    assert "ready" not in body
