"""Export the backend-owned OpenAPI contract artifact."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contracts.backend_api import build_openapi_document

OUTPUT = ROOT / "contracts" / "backend-api.openapi.json"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(build_openapi_document(), indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
