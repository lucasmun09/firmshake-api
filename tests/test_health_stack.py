"""Dual-stack /health payload contracts (no secrets)."""

from __future__ import annotations


def test_health_payload_devo_defaults(client, monkeypatch):
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "firmshake-dev")
    monkeypatch.delenv("APP_STACK", raising=False)
    monkeypatch.delenv("STRIPE_PAYMENTS_ENABLED", raising=False)
    monkeypatch.setenv("PAYMENTS_ENABLED", "true")

    response = client.get("/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["service"] == "firmshake-api"
    assert body["stack"] == "devo"
    assert body["firebaseProjectId"] == "firmshake-dev"
    assert body["paymentsEnabled"] is True


def test_health_payload_prod_payments_disabled(client, monkeypatch):
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "firmshake-prod")
    monkeypatch.delenv("APP_STACK", raising=False)
    monkeypatch.delenv("STRIPE_PAYMENTS_ENABLED", raising=False)
    monkeypatch.setenv("PAYMENTS_ENABLED", "false")

    response = client.get("/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["stack"] == "prod"
    assert body["firebaseProjectId"] == "firmshake-prod"
    assert body["paymentsEnabled"] is False


def test_health_payload_explicit_stack_override(client, monkeypatch):
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "firmshake-prod")
    monkeypatch.setenv("APP_STACK", "devo")
    monkeypatch.setenv("PAYMENTS_ENABLED", "false")

    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["stack"] == "devo"


def test_build_health_payload_unit(monkeypatch):
    from services.health_payload import build_health_payload

    monkeypatch.setenv("FIREBASE_PROJECT_ID", "firmshake-prod")
    monkeypatch.delenv("APP_STACK", raising=False)
    monkeypatch.setenv("PAYMENTS_ENABLED", "false")
    monkeypatch.delenv("STRIPE_PAYMENTS_ENABLED", raising=False)

    payload = build_health_payload()
    assert set(payload) >= {
        "status",
        "service",
        "stack",
        "firebaseProjectId",
        "paymentsEnabled",
    }
    assert "secret" not in str(payload).lower()
    assert "stripe" not in str(payload).lower()


def test_health_payload_stripe_alias_wins(client, monkeypatch):
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "firmshake-prod")
    monkeypatch.delenv("APP_STACK", raising=False)
    monkeypatch.setenv("PAYMENTS_ENABLED", "true")
    monkeypatch.setenv("STRIPE_PAYMENTS_ENABLED", "false")

    response = client.get("/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["stack"] == "prod"
    assert body["paymentsEnabled"] is False


def test_health_payload_unknown_project(client, monkeypatch):
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "some-other-project")
    monkeypatch.delenv("APP_STACK", raising=False)
    monkeypatch.setenv("PAYMENTS_ENABLED", "false")
    monkeypatch.delenv("STRIPE_PAYMENTS_ENABLED", raising=False)

    response = client.get("/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["stack"] == "unknown"
    assert body["firebaseProjectId"] == "some-other-project"
    assert body["paymentsEnabled"] is False
