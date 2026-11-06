"""API ↔ web host constant lockstep for CORS catalogs (skips without sibling)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from services.stack_config import (
    CONTROLPANEL_ORIGIN,
    DEVO_CORS_ORIGINS_POST_CUTOVER,
    DEVO_CORS_ORIGINS_TRANSITIONAL,
    PROD_CORS_ORIGINS,
)

ROOT = Path(__file__).resolve().parents[1]
WEB_STACK_HOSTS = ROOT.parent / "firmshake" / "src" / "common" / "config" / "stackHosts.ts"


pytestmark = pytest.mark.skipif(
    not WEB_STACK_HOSTS.is_file(),
    reason="Sibling firmshake checkout missing",
)


def _ts_string_array(source: str, const_name: str) -> list[str]:
    match = re.search(
        rf"export const {re.escape(const_name)}\s*=\s*\[(.*?)\]\s*as const",
        source,
        re.S,
    )
    assert match, f"{const_name} missing in stackHosts.ts"
    return re.findall(r"'([^']+)'", match.group(1))


def _ts_string_set(source: str, const_name: str) -> set[str]:
    match = re.search(
        rf"export const {re.escape(const_name)}\s*=\s*new Set\(\[(.*?)\]\)",
        source,
        re.S,
    )
    assert match, f"{const_name} missing in stackHosts.ts"
    return set(re.findall(r"'([^']+)'", match.group(1)))


def test_web_host_constants_appear_in_api_cors_catalogs():
    source = WEB_STACK_HOSTS.read_text(encoding="utf-8")
    deovo_hosts = _ts_string_array(source, "DEVO_HOSTING_HOSTNAMES")
    prod_hosts = _ts_string_array(source, "PROD_HOSTING_HOSTNAMES")
    public_hosts = _ts_string_set(source, "PROD_PUBLIC_HOSTNAMES")

    assert re.search(
        r"export const CONTROLPANEL_HOSTING_ORIGIN\s*=\s*'([^']+)'",
        source,
    ).group(1) == CONTROLPANEL_ORIGIN

    for host in deovo_hosts:
        origin = f"https://{host}"
        assert origin in DEVO_CORS_ORIGINS_TRANSITIONAL
        assert origin in DEVO_CORS_ORIGINS_POST_CUTOVER
        assert origin not in PROD_CORS_ORIGINS

    for host in prod_hosts:
        origin = f"https://{host}"
        assert origin in PROD_CORS_ORIGINS

    for host in public_hosts:
        origin = f"https://{host}"
        assert origin in PROD_CORS_ORIGINS
        assert origin in DEVO_CORS_ORIGINS_TRANSITIONAL
        assert origin not in DEVO_CORS_ORIGINS_POST_CUTOVER
