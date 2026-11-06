"""Dual-stack env / CI / health contract lockstep (no secrets)."""

from __future__ import annotations

import re
from pathlib import Path

from services.stack_config import (
    DEVO_CORS_ORIGINS_TRANSITIONAL,
    DEVO_FIREBASE_PROJECT_ID,
    DEVO_GCS_BUCKET,
    PROD_CORS_ORIGINS,
    PROD_FIREBASE_PROJECT_ID,
    PROD_GCS_BUCKET,
    join_cors_origins,
)

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _yaml_value(path: Path, key: str) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(key)}:\s*['\"]?(.*?)['\"]?\s*$", text, re.M)
    assert match, f"{key} missing in {path}"
    return match.group(1).strip()


def test_cloudrun_yaml_identity_and_payments_lockstep():
    deovo = ROOT / ".cloudrun.env.yaml"
    prod = ROOT / ".cloudrun.env.prod.yaml"

    assert _yaml_value(deovo, "FIREBASE_PROJECT_ID") == DEVO_FIREBASE_PROJECT_ID
    assert _yaml_value(deovo, "GCS_BUCKET") == DEVO_GCS_BUCKET
    assert _yaml_value(deovo, "PAYMENTS_ENABLED").lower() == "true"
    assert _yaml_value(deovo, "CORS_ORIGINS") == join_cors_origins(DEVO_CORS_ORIGINS_TRANSITIONAL)

    assert _yaml_value(prod, "FIREBASE_PROJECT_ID") == PROD_FIREBASE_PROJECT_ID
    assert _yaml_value(prod, "GCS_BUCKET") == PROD_GCS_BUCKET
    assert _yaml_value(prod, "PAYMENTS_ENABLED").lower() == "false"
    assert _yaml_value(prod, "CORS_ORIGINS") == join_cors_origins(PROD_CORS_ORIGINS)
    assert "controlpanel" not in _yaml_value(prod, "CORS_ORIGINS")
    assert "firmshake-dev" not in _yaml_value(prod, "CORS_ORIGINS")


def test_prod_yaml_has_no_active_stripe_keys():
    text = _read(".cloudrun.env.prod.yaml")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        assert not stripped.startswith("STRIPE_"), stripped


def test_ci_soft_gates_prod_behind_prod_deploy_enabled():
    # Live `.github/workflows` cannot be pushed without GitHub `workflow` scope.
    workflow = _read("docs/ci-workflows/deploy-api.yml")
    assert "vars.PROD_DEPLOY_ENABLED == 'true'" in workflow
    assert "assert-cloudrun-env.sh prod" in workflow
    assert "smoke-health.sh" in workflow
    assert "docs/ci-workflows/deploy-api.yml" in _read("docs/dual-stack.md")
    active = "\n".join(
        line for line in workflow.splitlines() if not line.lstrip().startswith("#")
    ).replace("vars.PROD_DEPLOY_ENABLED == 'true'", "")
    assert "PROD_DEPLOY_ENABLED: true" not in active
    assert "PROD_DEPLOY_ENABLED=true" not in active


def test_env_example_documents_dual_stack_and_no_processor():
    env = _read(".env.example")
    assert "firmshake-dev" in env
    assert "firmshake-prod" in env
    assert "PAYMENTS_ENABLED" in env
    assert "no payment processor" in env.lower() or "Do not add STRIPE_" in env
    assert "devo-prod-stacks" in env or "dual-stack" in env.lower()


def test_smoke_health_and_payload_share_required_fields():
    smoke = _read("scripts/smoke-health.sh")
    payload = _read("services/health_payload.py")
    routes = _read("routes/health.py")
    for field in ("status", "service", "stack", "firebaseProjectId", "paymentsEnabled"):
        assert field in smoke, field
        assert field in payload, field
    assert "/ready" in smoke
    assert "ready" in payload
    assert '@health_bp.get("/ready")' in routes or '@health_bp.get(\'/ready\')' in routes
    # Payload builder body (exclude module docstring) must not emit secret/stripe keys.
    body = payload.split('"""', 2)[-1] if '"""' in payload else payload
    assert "secret" not in body.lower()
    assert "stripe" not in body.lower()


def test_module_map_files_exist_for_parallel_agents():
    for rel in (
        "services/payments_flag.py",
        "services/stack_config.py",
        "services/health_payload.py",
        "services/browse_search.py",
        "services/browse_search_common.py",
        "services/browse_search_typesense.py",
        "services/browse_search_firestore.py",
        "scripts/assert-cloudrun-env.sh",
        "scripts/preflight-api.sh",
        "scripts/check-prod-readiness.sh",
        "scripts/smoke-health.sh",
        "docs/dual-stack.md",
    ):
        assert (ROOT / rel).is_file(), rel
