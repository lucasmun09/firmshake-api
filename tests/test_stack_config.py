"""Dual-stack identity + CORS catalog contracts."""

from __future__ import annotations

import re
from pathlib import Path

from services.stack_config import (
    CONTROLPANEL_ORIGIN,
    DEVO_CORS_ORIGINS_POST_CUTOVER,
    DEVO_CORS_ORIGINS_TRANSITIONAL,
    DEVO_FIREBASE_PROJECT_ID,
    PROD_CORS_ORIGINS,
    PROD_FIREBASE_PROJECT_ID,
    expected_gcs_bucket,
    join_cors_origins,
    prod_cors_must_exclude_controlpanel,
    resolve_api_stack,
)

ROOT = Path(__file__).resolve().parents[1]


def _yaml_cors_origins(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^CORS_ORIGINS:\s*['\"]?(.*?)['\"]?\s*$", text, re.M)
    assert match, f"CORS_ORIGINS missing in {path}"
    return match.group(1)


def test_resolve_api_stack_from_project_id():
    assert resolve_api_stack(project_id=DEVO_FIREBASE_PROJECT_ID, explicit_stack="") == "devo"
    assert resolve_api_stack(project_id=PROD_FIREBASE_PROJECT_ID, explicit_stack="") == "prod"
    assert resolve_api_stack(project_id="other", explicit_stack="") == "unknown"


def test_resolve_api_stack_explicit_overrides_project(monkeypatch):
    monkeypatch.setenv("FIREBASE_PROJECT_ID", PROD_FIREBASE_PROJECT_ID)
    assert resolve_api_stack(explicit_stack="devo") == "devo"
    assert resolve_api_stack(explicit_stack="production") == "prod"


def test_expected_gcs_buckets():
    assert expected_gcs_bucket("devo") == "firmshake-dev-images"
    assert expected_gcs_bucket("prod") == "firmshake-prod-images"
    assert expected_gcs_bucket("unknown") is None


def test_prod_cors_excludes_controlpanel():
    assert prod_cors_must_exclude_controlpanel(PROD_CORS_ORIGINS) is True
    bad = list(PROD_CORS_ORIGINS) + [CONTROLPANEL_ORIGIN]
    assert prod_cors_must_exclude_controlpanel(bad) is False


def test_devo_cors_includes_controlpanel():
    assert CONTROLPANEL_ORIGIN in DEVO_CORS_ORIGINS_TRANSITIONAL
    assert CONTROLPANEL_ORIGIN in DEVO_CORS_ORIGINS_POST_CUTOVER
    assert CONTROLPANEL_ORIGIN not in PROD_CORS_ORIGINS


def test_post_cutover_devo_drops_prod_domains():
    assert "https://firm-shake.com" in DEVO_CORS_ORIGINS_TRANSITIONAL
    assert "https://firm-shake.com" not in DEVO_CORS_ORIGINS_POST_CUTOVER
    assert "https://www.firm-shake.com" not in DEVO_CORS_ORIGINS_POST_CUTOVER


def test_join_cors_origins_matches_yaml_shape():
    joined = join_cors_origins(PROD_CORS_ORIGINS)
    assert joined.startswith("https://firm-shake.com,")
    assert "firmshake-prod.web.app" in joined
    assert CONTROLPANEL_ORIGIN not in joined


def test_cloudrun_yaml_cors_matches_stack_catalogs():
    """Keep Cloud Run env YAML and stack_config catalogs in lockstep."""
    deovo_yaml = _yaml_cors_origins(ROOT / ".cloudrun.env.yaml")
    prod_yaml = _yaml_cors_origins(ROOT / ".cloudrun.env.prod.yaml")
    assert deovo_yaml == join_cors_origins(DEVO_CORS_ORIGINS_TRANSITIONAL)
    assert prod_yaml == join_cors_origins(PROD_CORS_ORIGINS)
