"""Cross-repo prod readiness dry-run (wrapper + sibling script)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-prod-readiness.sh"
WEB_SCRIPT = ROOT.parent / "firmshake" / "scripts" / "check-prod-readiness.sh"


def test_api_wrapper_invokes_sibling_web_script():
    assert SCRIPT.is_file()
    assert WEB_SCRIPT.is_file(), "Expected sibling firmshake checkout with check-prod-readiness.sh"
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "FIRMSHAKE_WEB_ROOT": str(WEB_SCRIPT.parent.parent)},
    )
    # Live workspace is not prod-ready yet (RECAPTCHA placeholder).
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "prod readiness" in out.lower() or "NOT READY" in out
    assert "RECAPTCHA" in out or "REPLACE" in out
