"""Integration-style tests for scripts/assert-cloudrun-env.sh."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "assert-cloudrun-env.sh"


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_assert_accepts_real_devo_env():
    result = _run(["devo", str(ROOT / ".cloudrun.env.yaml")])
    assert result.returncode == 0, result.stderr + result.stdout
    assert "firmshake-dev" in result.stdout


def test_assert_rejects_prod_env_with_placeholders(tmp_path: Path):
    env = tmp_path / "prod.yaml"
    env.write_text(
        textwrap.dedent(
            """\
            FIREBASE_PROJECT_ID: firmshake-prod
            GCS_BUCKET: firmshake-prod-images
            CORS_ORIGINS: 'https://firm-shake.com,https://www.firm-shake.com,https://firmshake-prod.web.app,https://firmshake-prod.firebaseapp.com,capacitor://localhost,ionic://localhost'
            PAYMENTS_ENABLED: 'false'
            RECAPTCHA_SITE_KEY: 'REPLACE_ME_PROD_RECAPTCHA_SITE_KEY'
            """
        )
    )
    result = _run(["prod", str(env)])
    assert result.returncode != 0
    assert "REPLACE_ME" in (result.stderr + result.stdout)


def test_assert_accepts_complete_prod_env(tmp_path: Path):
    env = tmp_path / "prod.yaml"
    env.write_text(
        textwrap.dedent(
            """\
            FIREBASE_PROJECT_ID: firmshake-prod
            GCS_BUCKET: firmshake-prod-images
            CORS_ORIGINS: 'https://firm-shake.com,https://www.firm-shake.com,https://firmshake-prod.web.app,https://firmshake-prod.firebaseapp.com,capacitor://localhost,ionic://localhost'
            PAYMENTS_ENABLED: 'false'
            RECAPTCHA_SITE_KEY: '6LeFakeProdKeyForAssertTestsOnly'
            # TYPESENSE_HOST: 'https://YOUR-PROD-TYPESENSE-HOST'
            """
        )
    )
    result = _run(["prod", str(env)])
    assert result.returncode == 0, result.stderr + result.stdout


def test_assert_rejects_prod_cors_with_controlpanel(tmp_path: Path):
    env = tmp_path / "prod.yaml"
    env.write_text(
        textwrap.dedent(
            """\
            FIREBASE_PROJECT_ID: firmshake-prod
            GCS_BUCKET: firmshake-prod-images
            CORS_ORIGINS: 'https://firm-shake.com,https://firmshake-controlpanel.web.app,https://firmshake-prod.web.app'
            PAYMENTS_ENABLED: 'false'
            RECAPTCHA_SITE_KEY: 'ok'
            """
        )
    )
    result = _run(["prod", str(env)])
    assert result.returncode != 0
    assert "control panel" in (result.stderr + result.stdout).lower()


def test_assert_rejects_prod_payments_enabled(tmp_path: Path):
    env = tmp_path / "prod.yaml"
    env.write_text(
        textwrap.dedent(
            """\
            FIREBASE_PROJECT_ID: firmshake-prod
            GCS_BUCKET: firmshake-prod-images
            CORS_ORIGINS: 'https://firm-shake.com,https://www.firm-shake.com,https://firmshake-prod.web.app,https://firmshake-prod.firebaseapp.com'
            PAYMENTS_ENABLED: 'true'
            RECAPTCHA_SITE_KEY: 'ok'
            """
        )
    )
    result = _run(["prod", str(env)])
    assert result.returncode != 0
    assert "PAYMENTS_ENABLED" in (result.stderr + result.stdout)


def test_assert_rejects_prod_active_stripe_keys(tmp_path: Path):
    env = tmp_path / "prod.yaml"
    env.write_text(
        textwrap.dedent(
            """\
            FIREBASE_PROJECT_ID: firmshake-prod
            GCS_BUCKET: firmshake-prod-images
            CORS_ORIGINS: 'https://firm-shake.com,https://www.firm-shake.com,https://firmshake-prod.web.app,https://firmshake-prod.firebaseapp.com,capacitor://localhost,ionic://localhost'
            PAYMENTS_ENABLED: 'false'
            RECAPTCHA_SITE_KEY: 'ok'
            STRIPE_SECRET_KEY: 'sk_test_should_not_be_here'
            """
        )
    )
    result = _run(["prod", str(env)])
    assert result.returncode != 0
    out = result.stderr + result.stdout
    assert "STRIPE_" in out
    assert "processor" in out.lower() or "payment" in out.lower()


def test_live_prod_yaml_still_blocked_on_recaptcha_placeholder():
    """Documents the exact human gate for deploy-prod.sh."""
    result = _run(["prod", str(ROOT / ".cloudrun.env.prod.yaml")])
    assert result.returncode != 0
    out = result.stderr + result.stdout
    assert "REPLACE_ME" in out
    assert "RECAPTCHA" in out or "REPLACE_ME_PROD_RECAPTCHA" in (
        ROOT / ".cloudrun.env.prod.yaml"
    ).read_text(encoding="utf-8")
