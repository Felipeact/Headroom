"""Write the API's OpenAPI schema to contracts/openapi.json (spec 09).

Run from services/core: `uv run python -m app.export_openapi`. Then run
`npm run api:types` from frontend. CI fails if either generated file is stale.
"""

import json
from pathlib import Path

from app.main import app

# Resolved from this file, not the cwd, so it always lands at the repository root.
CONTRACT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "openapi.json"


def main() -> None:
    CONTRACT_PATH.parent.mkdir(exist_ok=True)
    content = json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"
    with CONTRACT_PATH.open("w", encoding="utf-8", newline="\n") as file:
        file.write(content)
    print(f"Wrote {CONTRACT_PATH}")


if __name__ == "__main__":
    main()
