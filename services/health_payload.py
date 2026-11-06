"""Public /health and /ready payloads for dual-stack smoke checks.

No secrets — only stack identity + payments gate boolean.
Used by CI curl smoke and scripts/smoke-health.sh.
"""

from __future__ import annotations

import os

from services.payments_flag import are_payments_enabled
from services.stack_config import DEVO_FIREBASE_PROJECT_ID, resolve_api_stack


def build_health_payload(*, ready: bool = False) -> dict:
    project_id = os.getenv("FIREBASE_PROJECT_ID", DEVO_FIREBASE_PROJECT_ID).strip()
    stack = resolve_api_stack(project_id=project_id)
    payload = {
        "status": "ok",
        "service": "firmshake-api",
        "stack": stack,
        "firebaseProjectId": project_id,
        "paymentsEnabled": are_payments_enabled(),
    }
    if ready:
        # Process is up and stack identity resolved — no credential/key dependency probes.
        payload["ready"] = True
    return payload


def build_ready_payload() -> dict:
    """Cloud Run / load-balancer readiness: same identity contract as /health + ready=true."""
    return build_health_payload(ready=True)
