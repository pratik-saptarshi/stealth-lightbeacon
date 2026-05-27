from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


DEFAULT_SERVICE_HOST = "127.0.0.1"
DEFAULT_SERVICE_PORT = 8000
DEFAULT_SERVICE_VERSION = "1.2.4"
DEFAULT_SERVICE_MODE = "local"
DEFAULT_SERVICE_TRANSPORT = "http"

CONTRACT_PATH = Path(__file__).resolve().parents[1] / "contracts" / "backend-api.openapi.json"


def load_openapi_document() -> Dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def detect_mode(host: str) -> str:
    return "local" if host in {"127.0.0.1", "localhost", "::1"} else "remote"


def build_capabilities(mode: str = DEFAULT_SERVICE_MODE) -> Dict[str, Any]:
    return {
        "apiMode": {"mode": mode, "transport": DEFAULT_SERVICE_TRANSPORT},
        "evaluationProfiles": [
            "seo",
            "performance",
            "accessibility",
            "aeo-geo",
            "ux",
            "security",
        ],
        "outputFormats": ["json", "html", "llm", "geo-xml"],
        "supportsRecon": True,
        "supportsArtifacts": True,
    }


def build_compatibility_response(
    *,
    client_version: str | None,
    host: str,
    transport: str = DEFAULT_SERVICE_TRANSPORT,
    auth_required: bool = False,
) -> Dict[str, Any]:
    version = client_version or ""
    version_match = not version or version.startswith("1.")
    compatible = transport == DEFAULT_SERVICE_TRANSPORT and version_match
    reasons = []
    if transport != DEFAULT_SERVICE_TRANSPORT:
        reasons.append(f"unsupported transport: {transport}")
    if not version_match:
        reasons.append(f"incompatible client version: {version}")
    if auth_required:
        reasons.append("auth token required for protected routes")
    return {
        "compatible": compatible,
        "serverMode": detect_mode(host),
        "transport": transport,
        "requiresAuth": auth_required,
        "clientVersion": version or None,
        "serviceVersion": DEFAULT_SERVICE_VERSION,
        "reasons": reasons,
    }
