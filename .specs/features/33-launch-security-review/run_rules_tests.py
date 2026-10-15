"""Spec 33 C23: run exactly the tests that context/security/rules.md names.

Run from services/core:  uv run python ../../.specs/features/33-launch-security-review/run_rules_tests.py
"""

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RULES = REPO / "context" / "security" / "rules.md"


def main() -> int:
    names = re.findall(
        r"`((?:services/core|frontend)/tests/[^`]+)`", RULES.read_text(encoding="utf8")
    )
    api = sorted({n.removeprefix("services/core/") for n in names if n.startswith("services/core/")})
    web = sorted({n.removeprefix("frontend/") for n in names if n.startswith("frontend/")})
    code = 0
    if api:
        code |= subprocess.run(
            ["uv", "run", "pytest", "-q", *api], cwd=REPO / "services" / "core", check=False
        ).returncode
    if web:
        code |= subprocess.run(
            ["npx", "vitest", "run", *web], cwd=REPO / "frontend", check=False, shell=True
        ).returncode
    print(f"ran {len(api)} API tests and {len(web)} web tests: exit {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
