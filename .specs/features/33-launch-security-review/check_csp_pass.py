"""Spec 33 C15: the Playwright pass over the screens under the report-only policy.

Exits 0 only when csp-pass.md lists every screen below with `ok`, and every violation row
in context/security/rules.md has a decision.
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
RULES = HERE.parents[2] / "context" / "security" / "rules.md"
SCREENS = ["/sign-in", "/", "/alerts", "/settings/banks", "/settings/email"]


def main() -> int:
    record = HERE / "csp-pass.md"
    if not record.is_file():
        print("csp-pass.md is missing")
        return 1
    text = record.read_text(encoding="utf8")
    failed = [
        s
        for s in SCREENS
        if not re.search(rf"^\| `{re.escape(s)}` \| ok \|", text, flags=re.MULTILINE)
    ]
    if failed:
        print("screens not recorded as ok:", ", ".join(failed))
        return 1
    table = RULES.read_text(encoding="utf8").split("## Content-Security-Policy", 1)[1]
    rows = [
        line
        for line in table.splitlines()
        if line.startswith("| ") and "Screen" not in line and "---" not in line
    ]
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if cells[0].startswith("_none") or cells[0] == "":
            continue
        if len(cells) < 3 or not cells[2]:
            print("violation without a decision:", row)
            return 1
    print("ok: every screen recorded, every violation decided")
    return 0


if __name__ == "__main__":
    sys.exit(main())
