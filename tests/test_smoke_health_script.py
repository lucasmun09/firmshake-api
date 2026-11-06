"""Integration-style tests for scripts/smoke-health.sh (local fake HTTP)."""

from __future__ import annotations

import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "smoke-health.sh"


def _serve_health(payload: dict, *, ready_payload: dict | None = None) -> tuple[HTTPServer, str]:
    health_body = json.dumps(payload).encode("utf-8")
    ready = dict(ready_payload) if ready_payload is not None else {**payload, "ready": True}
    ready_body = json.dumps(ready).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = self.path.rstrip("/")
            if path == "/health":
                body = health_body
            elif path == "/ready":
                body = ready_body
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, f"http://{host}:{port}"


def _run(url: str, stack: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), url, stack],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_smoke_health_accepts_devo_payload():
    server, base = _serve_health(
        {
            "status": "ok",
            "service": "firmshake-api",
            "stack": "devo",
            "firebaseProjectId": "firmshake-dev",
            "paymentsEnabled": True,
        }
    )
    try:
        result = _run(base, "deovo")
        assert result.returncode == 0, result.stderr + result.stdout
        assert "OK:" in result.stdout
        assert "ready" in result.stdout.lower() or "OK: ready" in result.stdout
    finally:
        server.shutdown()


def test_smoke_health_rejects_wrong_stack():
    server, base = _serve_health(
        {
            "status": "ok",
            "service": "firmshake-api",
            "stack": "prod",
            "firebaseProjectId": "firmshake-prod",
            "paymentsEnabled": False,
        }
    )
    try:
        result = _run(base, "deovo")
        assert result.returncode != 0
    finally:
        server.shutdown()


def test_smoke_health_rejects_prod_with_payments_on():
    server, base = _serve_health(
        {
            "status": "ok",
            "service": "firmshake-api",
            "stack": "prod",
            "firebaseProjectId": "firmshake-prod",
            "paymentsEnabled": True,
        }
    )
    try:
        result = _run(base, "prod")
        assert result.returncode != 0
    finally:
        server.shutdown()


def test_smoke_health_accepts_prod_payments_disabled():
    server, base = _serve_health(
        {
            "status": "ok",
            "service": "firmshake-api",
            "stack": "prod",
            "firebaseProjectId": "firmshake-prod",
            "paymentsEnabled": False,
        }
    )
    try:
        result = _run(base, "prod")
        assert result.returncode == 0, result.stderr + result.stdout
        assert "OK:" in result.stdout
        assert "paymentsEnabled=False" in result.stdout or "paymentsEnabled=false" in result.stdout.lower()
    finally:
        server.shutdown()


def test_smoke_health_rejects_cross_wired_project():
    server, base = _serve_health(
        {
            "status": "ok",
            "service": "firmshake-api",
            "stack": "prod",
            "firebaseProjectId": "firmshake-dev",
            "paymentsEnabled": False,
        }
    )
    try:
        result = _run(base, "prod")
        assert result.returncode != 0
    finally:
        server.shutdown()


def test_smoke_health_rejects_ready_without_ready_flag():
    payload = {
        "status": "ok",
        "service": "firmshake-api",
        "stack": "devo",
        "firebaseProjectId": "firmshake-dev",
        "paymentsEnabled": True,
    }
    server, base = _serve_health(payload, ready_payload=payload)
    try:
        result = _run(base, "deovo")
        assert result.returncode != 0
    finally:
        server.shutdown()
