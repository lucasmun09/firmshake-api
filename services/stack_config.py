"""Dual-stack identity and CORS origin catalogs for FirmShake API.

Devo = firmshake-dev / staging Cloud Run (us-central1).
Prod = firmshake-prod / Cloud Run us-east1.
Control panel is deovo-only — never add its origin to prod CORS.
See sibling firmshake/docs/devo-prod-stacks.md.
"""

from __future__ import annotations

import os
from typing import Literal

AppStack = Literal["devo", "prod", "unknown"]

DEVO_FIREBASE_PROJECT_ID = "firmshake-dev"
PROD_FIREBASE_PROJECT_ID = "firmshake-prod"

DEVO_GCS_BUCKET = "firmshake-dev-images"
PROD_GCS_BUCKET = "firmshake-prod-images"

CONTROLPANEL_ORIGIN = "https://firmshake-controlpanel.web.app"

# Canonical CORS origin lists (comma-join for Cloud Run env YAML).
# Devo transitional includes prod custom domains while apex still serves firmshake-dev.
DEVO_CORS_ORIGINS_TRANSITIONAL = (
    "https://firmshake-dev.web.app",
    "https://firmshake-dev.firebaseapp.com",
    CONTROLPANEL_ORIGIN,
    "https://firm-shake.com",
    "https://www.firm-shake.com",
    "http://localhost:5173",
    "http://localhost:5174",
    "capacitor://localhost",
    "ionic://localhost",
)

DEVO_CORS_ORIGINS_POST_CUTOVER = (
    "https://firmshake-dev.web.app",
    "https://firmshake-dev.firebaseapp.com",
    CONTROLPANEL_ORIGIN,
    "http://localhost:5173",
    "http://localhost:5174",
    "capacitor://localhost",
    "ionic://localhost",
)

PROD_CORS_ORIGINS = (
    "https://firm-shake.com",
    "https://www.firm-shake.com",
    "https://firmshake-prod.web.app",
    "https://firmshake-prod.firebaseapp.com",
    "capacitor://localhost",
    "ionic://localhost",
)


def join_cors_origins(origins: tuple[str, ...] | list[str]) -> str:
    return ",".join(origins)


def resolve_api_stack(
    *,
    project_id: str | None = None,
    explicit_stack: str | None = None,
) -> AppStack:
    """Resolve stack from FIREBASE_PROJECT_ID / optional APP_STACK env."""
    raw_explicit = (explicit_stack if explicit_stack is not None else os.getenv("APP_STACK", "")).strip().lower()
    if raw_explicit in {"devo", "deovo", "dev", "staging"}:
        return "devo"
    if raw_explicit in {"prod", "production"}:
        return "prod"

    pid = (
        project_id
        if project_id is not None
        else os.getenv("FIREBASE_PROJECT_ID", DEVO_FIREBASE_PROJECT_ID)
    ).strip()
    if pid == DEVO_FIREBASE_PROJECT_ID:
        return "devo"
    if pid == PROD_FIREBASE_PROJECT_ID:
        return "prod"
    return "unknown"


def expected_gcs_bucket(stack: AppStack) -> str | None:
    if stack == "devo":
        return DEVO_GCS_BUCKET
    if stack == "prod":
        return PROD_GCS_BUCKET
    return None


def prod_cors_must_exclude_controlpanel(origins: list[str] | tuple[str, ...]) -> bool:
    """True when prod CORS list is safe (no control panel origin)."""
    normalized = {o.strip().rstrip("/") for o in origins if o and o.strip()}
    return CONTROLPANEL_ORIGIN.rstrip("/") not in normalized
