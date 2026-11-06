"""Public /health payload for dual-stack smoke checks.

No secrets — only stack identity + payments gate boolean.
Used by CI curl smoke and scripts/smoke-health.sh.
"""

from __future__ import annotations

import os

from services.payments_flag import are_payments_enabled
from services.stack_config import DEVO_FIREBASE_PROJECT_ID, resolve_api_stack


def build_health_payload() -> dict:
    project_id = os.getenv("FIREBASE_PROJECT_ID", DEVO_FIREBASE_PROJECT_ID).strip()
    stack = resolve_api_stack(project_id=project_id)
    return {
        "status": "ok",
        "service": "firmshake-api",
        "stack": stack,
        "firebaseProjectId": project_id,
        "paymentsEnabled": are_payments_enabled(),
    }
