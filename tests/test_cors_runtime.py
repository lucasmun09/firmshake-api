"""Runtime CORS lockstep: Flask Access-Control headers honor stack catalogs."""

from __future__ import annotations

import app as app_module
from services.stack_config import (
    CONTROLPANEL_ORIGIN,
    DEVO_CORS_ORIGINS_TRANSITIONAL,
    PROD_CORS_ORIGINS,
)


def _client_with_origins(monkeypatch, origins: tuple[str, ...] | list[str]):
    monkeypatch.setattr(app_module, "CORS_ORIGINS", list(origins))
    application = app_module.create_app()
    application.config["TESTING"] = True
    return application.test_client()


def _preflight(client, *, path: str, origin: str):
    return client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        },
    )


def test_devo_cors_allows_controlpanel_and_hosting(monkeypatch):
    client = _client_with_origins(monkeypatch, DEVO_CORS_ORIGINS_TRANSITIONAL)

    for origin in (
        CONTROLPANEL_ORIGIN,
        "https://firmshake-dev.web.app",
        "https://firm-shake.com",
        "http://localhost:5173",
    ):
        response = _preflight(client, path="/health", origin=origin)
        assert response.status_code in {200, 204}, origin
        assert response.headers.get("Access-Control-Allow-Origin") == origin, origin


def test_prod_cors_allows_public_hosts_blocks_controlpanel(monkeypatch):
    client = _client_with_origins(monkeypatch, PROD_CORS_ORIGINS)

    for origin in (
        "https://firm-shake.com",
        "https://www.firm-shake.com",
        "https://firmshake-prod.web.app",
    ):
        response = _preflight(client, path="/api/v1/browse/search", origin=origin)
        assert response.status_code in {200, 204}, origin
        assert response.headers.get("Access-Control-Allow-Origin") == origin, origin

    blocked = _preflight(client, path="/health", origin=CONTROLPANEL_ORIGIN)
    assert blocked.headers.get("Access-Control-Allow-Origin") != CONTROLPANEL_ORIGIN

    deovo = _preflight(client, path="/health", origin="https://firmshake-dev.web.app")
    assert deovo.headers.get("Access-Control-Allow-Origin") != "https://firmshake-dev.web.app"


def test_ready_endpoint_cors_matches_health(monkeypatch):
    client = _client_with_origins(monkeypatch, PROD_CORS_ORIGINS)
    origin = "https://firmshake-prod.web.app"
    health = _preflight(client, path="/health", origin=origin)
    ready = _preflight(client, path="/ready", origin=origin)
    assert health.headers.get("Access-Control-Allow-Origin") == origin
    assert ready.headers.get("Access-Control-Allow-Origin") == origin
