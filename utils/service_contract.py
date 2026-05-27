"""Canonical client/service contract helpers and drift validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTRACT_DIR = Path("contracts")
CONTRACT_PATH = CONTRACT_DIR / "backend-api.openapi.json"
CONTRACT_OPENAPI_VERSION = "3.1.0"
CONTRACT_API_VERSION = "1.2.5"
CONTRACT_DEFAULT_HOST = "127.0.0.1"
CONTRACT_DEFAULT_PORT = 8000
CONTRACT_DEFAULT_SCHEME = "http"
CONTRACT_DEFAULT_BASE_URL = f"{CONTRACT_DEFAULT_SCHEME}://{CONTRACT_DEFAULT_HOST}:{CONTRACT_DEFAULT_PORT}"
CONTRACT_REMOTE_SCHEME = "https"
CONTRACT_STDIN_ADAPTER = "stdin"

CONTRACT_ROUTE_SET = (
    "/health",
    "/capabilities",
    "/evaluations",
    "/evaluations/{evaluation_id}",
    "/evaluations/{evaluation_id}/result",
    "/evaluations/{evaluation_id}/artifacts",
    "/recon",
)


def build_service_contract() -> dict[str, Any]:
    """Build the canonical OpenAPI snapshot for client alignment."""
    return {
        "openapi": CONTRACT_OPENAPI_VERSION,
        "info": {
            "title": "Stealth Lightbeacon Service API",
            "version": CONTRACT_API_VERSION,
            "description": "Canonical contract for local and remote Stealth Lightbeacon clients.",
        },
        "servers": [
            {
                "url": CONTRACT_DEFAULT_BASE_URL,
                "description": "Local loopback service",
            },
            {
                "url": "https://api.stealth-lightbeacon.example",
                "description": "Cloud-hosted service",
            },
        ],
        "paths": {
            "/health": {
                "get": {
                    "operationId": "getHealth",
                    "summary": "Check service liveness.",
                    "responses": {"200": {"description": "Service is healthy."}},
                }
            },
            "/capabilities": {
                "get": {
                    "operationId": "getCapabilities",
                    "summary": "List service transport and feature capabilities.",
                    "responses": {"200": {"description": "Capability payload."}},
                }
            },
            "/evaluations": {
                "post": {
                    "operationId": "createEvaluation",
                    "summary": "Submit a new evaluation request.",
                    "responses": {"202": {"description": "Evaluation accepted."}},
                }
            },
            "/evaluations/{evaluation_id}": {
                "get": {
                    "operationId": "getEvaluationStatus",
                    "summary": "Poll an evaluation until completion.",
                    "responses": {"200": {"description": "Evaluation status."}},
                }
            },
            "/evaluations/{evaluation_id}/result": {
                "get": {
                    "operationId": "getEvaluationResult",
                    "summary": "Fetch the terminal result for an evaluation.",
                    "responses": {"200": {"description": "Evaluation result."}},
                }
            },
            "/evaluations/{evaluation_id}/artifacts": {
                "get": {
                    "operationId": "getEvaluationArtifacts",
                    "summary": "List the evaluation artifacts.",
                    "responses": {"200": {"description": "Artifact listing."}},
                }
            },
            "/recon": {
                "post": {
                    "operationId": "runRecon",
                    "summary": "Run advisory reconnaissance.",
                    "responses": {"200": {"description": "Recon payload."}},
                }
            },
        },
        "x-transport": {
            "local": {
                "scheme": CONTRACT_DEFAULT_SCHEME,
                "host": CONTRACT_DEFAULT_HOST,
                "port": CONTRACT_DEFAULT_PORT,
                "base_url": CONTRACT_DEFAULT_BASE_URL,
            },
            "cloud": {
                "scheme": CONTRACT_REMOTE_SCHEME,
                "auth": "bearer",
                "base_url": "https://api.stealth-lightbeacon.example",
            },
            "stdin": {
                "adapter": CONTRACT_STDIN_ADAPTER,
                "purpose": "embedded fallback",
            },
        },
    }


def load_service_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    """Load a checked-in contract snapshot."""
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_service_contract(contract: dict[str, Any]) -> list[str]:
    """Return drift errors for the checked-in OpenAPI snapshot."""
    errors: list[str] = []

    def as_mapping(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    if contract.get("openapi") != CONTRACT_OPENAPI_VERSION:
        errors.append(f"openapi version drift: {contract.get('openapi')!r}")

    info = as_mapping(contract.get("info", {}))
    if info.get("title") != "Stealth Lightbeacon Service API":
        errors.append(f"info.title drift: {info.get('title')!r}")
    if info.get("version") != CONTRACT_API_VERSION:
        errors.append(f"info.version drift: {info.get('version')!r}")

    servers = contract.get("servers", [])
    if not isinstance(servers, list) or len(servers) < 2:
        errors.append("servers list missing local and cloud entries")
    else:
        local_server = as_mapping(servers[0])
        if local_server.get("url") != CONTRACT_DEFAULT_BASE_URL:
            errors.append(f"local server url drift: {local_server.get('url')!r}")
        cloud_server = as_mapping(servers[1])
        if cloud_server.get("url") != "https://api.stealth-lightbeacon.example":
            errors.append(f"cloud server url drift: {cloud_server.get('url')!r}")

    paths = contract.get("paths", {})
    if not isinstance(paths, dict):
        errors.append("paths payload is not an object")
        return errors

    actual_routes = set(paths)
    expected_routes = set(CONTRACT_ROUTE_SET)
    missing_routes = sorted(expected_routes - actual_routes)
    extra_routes = sorted(actual_routes - expected_routes)
    if missing_routes:
        errors.append(f"missing routes: {missing_routes}")
    if extra_routes:
        errors.append(f"unexpected routes: {extra_routes}")

    transport = as_mapping(contract.get("x-transport", {}))
    local_transport = as_mapping(transport.get("local", {}))
    if local_transport.get("host") != CONTRACT_DEFAULT_HOST:
        errors.append(f"local host drift: {local_transport.get('host')!r}")
    if local_transport.get("port") != CONTRACT_DEFAULT_PORT:
        errors.append(f"local port drift: {local_transport.get('port')!r}")
    if local_transport.get("base_url") != CONTRACT_DEFAULT_BASE_URL:
        errors.append(f"local base url drift: {local_transport.get('base_url')!r}")

    cloud_transport = as_mapping(transport.get("cloud", {}))
    if cloud_transport.get("scheme") != CONTRACT_REMOTE_SCHEME:
        errors.append(f"cloud scheme drift: {cloud_transport.get('scheme')!r}")
    if cloud_transport.get("auth") != "bearer":
        errors.append(f"cloud auth drift: {cloud_transport.get('auth')!r}")

    stdin_transport = as_mapping(transport.get("stdin", {}))
    if stdin_transport.get("adapter") != CONTRACT_STDIN_ADAPTER:
        errors.append(f"stdin adapter drift: {stdin_transport.get('adapter')!r}")

    return errors


def validate_service_contract_snapshot(path: Path = CONTRACT_PATH) -> list[str]:
    """Validate the checked-in contract snapshot against the code contract."""
    return validate_service_contract(load_service_contract(path))
