"""Thin HTTP companion adapter for desktop bootstrap routes."""

from __future__ import annotations

import argparse
import json
import os
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Mapping
from urllib.parse import urlparse

from companion.catalog import SUPPORTED_OUTPUT_FORMATS, SUPPORTED_PROFILES
from companion.errors import ApiRouteError
from companion.jobs import DEFAULT_JOB_MANAGER, EvaluationJobManager
from contracts.backend_api import API_VERSION, APP_VERSION, build_openapi_document

SERVICE_NAME = "stealth-lightbeacon-api"
API_AUTH_ENV = "SLB_API_AUTH_TOKEN"
DESKTOP_VERSION_HEADER = "X-Stealth-Lightbeacon-Desktop-Version"
MINIMUM_DESKTOP_VERSION = "0.1.0"
RECOMMENDED_DESKTOP_VERSION = "0.1.0"


def _parse_version_parts(value: str) -> tuple[int, ...]:
    cleaned = value.strip()
    if not cleaned:
        return tuple()
    parts: list[int] = []
    for part in cleaned.split("."):
        if not part.isdigit():
            return tuple()
        parts.append(int(part))
    return tuple(parts)


def _is_compatible_desktop_version(version: str, minimum: str) -> bool:
    candidate = _parse_version_parts(version)
    baseline = _parse_version_parts(minimum)
    if not candidate or not baseline:
        return False
    width = max(len(candidate), len(baseline))
    padded_candidate = candidate + (0,) * (width - len(candidate))
    padded_baseline = baseline + (0,) * (width - len(baseline))
    return padded_candidate >= padded_baseline


class CompanionHealth:
    """Tracks companion readiness for desktop lifecycle management."""

    def __init__(
        self,
        *,
        startup_delay_ms: int = 0,
        degraded_reason: str | None = None,
    ) -> None:
        self.started_at = time.monotonic()
        self.startup_delay_ms = max(0, startup_delay_ms)
        self.degraded_reason = (degraded_reason or "").strip() or None

    def status(self) -> str:
        if time.monotonic() < self.started_at + (self.startup_delay_ms / 1000):
            return "booting"
        if self.degraded_reason:
            return "degraded"
        return "ok"


class CompanionApi:
    """Pure route dispatcher for the desktop companion surface."""

    def __init__(
        self,
        base_url: str,
        job_manager: EvaluationJobManager | None = None,
        health: CompanionHealth | None = None,
        api_auth_token: str | None = None,
        minimum_desktop_version: str = MINIMUM_DESKTOP_VERSION,
        recommended_desktop_version: str = RECOMMENDED_DESKTOP_VERSION,
    ) -> None:
        self.base_url = base_url
        self.job_manager = job_manager or DEFAULT_JOB_MANAGER
        self.health = health or CompanionHealth()
        self.api_auth_token = (api_auth_token or "").strip() or None
        self.minimum_desktop_version = minimum_desktop_version
        self.recommended_desktop_version = recommended_desktop_version

    def health_response(self) -> Dict[str, Any]:
        return {
            "status": self.health.status(),
            "service": SERVICE_NAME,
            "apiVersion": API_VERSION,
            "appVersion": APP_VERSION,
            "authRequired": self.api_auth_token is not None,
            "compatibility": {
                "minimumDesktopVersion": self.minimum_desktop_version,
                "recommendedDesktopVersion": self.recommended_desktop_version,
            },
        }

    def capabilities_response(self) -> Dict[str, Any]:
        return {
            "apiMode": {
                "mode": "local",
                "baseUrl": self.base_url,
                "transport": "http",
                "apiVersion": API_VERSION,
                "supportsRemote": False,
            },
            "evaluationProfiles": list(SUPPORTED_PROFILES),
            "outputFormats": list(SUPPORTED_OUTPUT_FORMATS),
            "supportsRecon": True,
            "supportsArtifacts": True,
        }

    def dispatch(
        self,
        method: str,
        path: str,
        body: Dict[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> tuple[int, Dict[str, Any]]:
        normalized_path = path.rstrip("/") or "/"
        normalized_headers = headers or {}

        if normalized_path == "/health":
            if method != "GET":
                raise ApiRouteError(
                    status=HTTPStatus.METHOD_NOT_ALLOWED,
                    code="method_not_allowed",
                    message="Route does not support that HTTP method.",
                    details=f"{method} {normalized_path}",
                )
            return HTTPStatus.OK, self.health_response()
        if normalized_path == "/capabilities":
            if method != "GET":
                raise ApiRouteError(
                    status=HTTPStatus.METHOD_NOT_ALLOWED,
                    code="method_not_allowed",
                    message="Route does not support that HTTP method.",
                    details=f"{method} {normalized_path}",
                )
            self._require_protected_access(normalized_headers)
            return HTTPStatus.OK, self.capabilities_response()
        if normalized_path == "/openapi.json":
            if method != "GET":
                raise ApiRouteError(
                    status=HTTPStatus.METHOD_NOT_ALLOWED,
                    code="method_not_allowed",
                    message="Route does not support that HTTP method.",
                    details=f"{method} {normalized_path}",
                )
            return HTTPStatus.OK, build_openapi_document()
        if normalized_path == "/evaluations":
            if method != "POST":
                raise ApiRouteError(
                    status=HTTPStatus.METHOD_NOT_ALLOWED,
                    code="method_not_allowed",
                    message="Route does not support that HTTP method.",
                    details=f"{method} {normalized_path}",
                )
            self._require_protected_access(normalized_headers)
            return HTTPStatus.ACCEPTED, self.job_manager.submit(body or {})

        segments = [segment for segment in normalized_path.split("/") if segment]
        if len(segments) == 2 and segments[0] == "evaluations":
            if method != "GET":
                raise ApiRouteError(
                    status=HTTPStatus.METHOD_NOT_ALLOWED,
                    code="method_not_allowed",
                    message="Route does not support that HTTP method.",
                    details=f"{method} {normalized_path}",
                )
            self._require_protected_access(normalized_headers)
            return HTTPStatus.OK, self.job_manager.get_status(segments[1])
        if len(segments) == 3 and segments[0] == "evaluations" and segments[2] == "result":
            if method != "GET":
                raise ApiRouteError(
                    status=HTTPStatus.METHOD_NOT_ALLOWED,
                    code="method_not_allowed",
                    message="Route does not support that HTTP method.",
                    details=f"{method} {normalized_path}",
                )
            self._require_protected_access(normalized_headers)
            return HTTPStatus.OK, self.job_manager.get_result(segments[1])
        if len(segments) == 3 and segments[0] == "evaluations" and segments[2] == "artifacts":
            if method != "GET":
                raise ApiRouteError(
                    status=HTTPStatus.METHOD_NOT_ALLOWED,
                    code="method_not_allowed",
                    message="Route does not support that HTTP method.",
                    details=f"{method} {normalized_path}",
                )
            self._require_protected_access(normalized_headers)
            return HTTPStatus.OK, self.job_manager.get_artifacts(segments[1])

        raise ApiRouteError(
            status=HTTPStatus.NOT_FOUND,
            code="not_found",
            message="Route not found.",
            details=normalized_path,
        )

    def _require_protected_access(self, headers: Mapping[str, str]) -> None:
        self._require_compatible_desktop(headers)
        self._require_api_auth(headers)

    def _require_api_auth(self, headers: Mapping[str, str]) -> None:
        if self.api_auth_token is None:
            return
        authorization = headers.get("Authorization", "").strip()
        expected = f"Bearer {self.api_auth_token}"
        if authorization == expected:
            return
        raise ApiRouteError(
            status=HTTPStatus.UNAUTHORIZED,
            code="unauthorized",
            message="Remote API auth required.",
            details=API_AUTH_ENV,
        )

    def _require_compatible_desktop(self, headers: Mapping[str, str]) -> None:
        desktop_version = headers.get(DESKTOP_VERSION_HEADER, "").strip()
        if _is_compatible_desktop_version(
            desktop_version,
            self.minimum_desktop_version,
        ):
            return
        raise ApiRouteError(
            status=HTTPStatus.CONFLICT,
            code="incompatible_client",
            message="Desktop version is not supported by this backend.",
            details=desktop_version or "missing_desktop_version_header",
        )


class CompanionServer(ThreadingHTTPServer):
    """Server wrapper that carries backend companion state."""

    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        startup_delay_ms: int = 0,
        degraded_reason: str | None = None,
    ) -> None:
        super().__init__(server_address, CompanionRequestHandler)
        host, port = self.server_address
        self.base_url = f"http://{host}:{port}"
        self.api = CompanionApi(
            base_url=self.base_url,
            health=CompanionHealth(
                startup_delay_ms=startup_delay_ms,
                degraded_reason=degraded_reason,
            ),
            api_auth_token=os.getenv(API_AUTH_ENV),
        )


class CompanionRequestHandler(BaseHTTPRequestHandler):
    """JSON-only request handler for the desktop companion surface."""

    server: CompanionServer

    def do_GET(self) -> None:
        self._handle("GET")

    def do_POST(self) -> None:
        self._handle("POST")

    def do_PUT(self) -> None:
        self._handle("PUT")

    def do_DELETE(self) -> None:
        self._handle("DELETE")

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def _handle(self, method: str) -> None:
        parsed = urlparse(self.path)
        body = None
        try:
            if method in {"POST", "PUT"}:
                body = self._read_json_body()
            status, payload = self.server.api.dispatch(
                method=method,
                path=parsed.path,
                body=body,
                headers=self.headers,
            )
        except ApiRouteError as exc:
            self._send_json(exc.status, exc.to_payload())
            return
        except Exception:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    "code": "internal_error",
                    "message": "Internal server error.",
                    "status": HTTPStatus.INTERNAL_SERVER_ERROR,
                },
            )
            return

        self._send_json(status, payload)

    def _read_json_body(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ApiRouteError(
                status=HTTPStatus.BAD_REQUEST,
                code="invalid_request",
                message="Request body must be valid JSON.",
                details=str(exc),
            ) from exc
        if not isinstance(payload, dict):
            raise ApiRouteError(
                status=HTTPStatus.BAD_REQUEST,
                code="invalid_request",
                message="Request body must be a JSON object.",
            )
        return payload

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _startup_delay_ms_from_env() -> int:
    raw = os.getenv("SLB_COMPANION_STARTUP_DELAY_MS", "").strip()
    if not raw:
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def _degraded_reason_from_env() -> str | None:
    raw = os.getenv("SLB_COMPANION_DEGRADED_REASON", "").strip()
    return raw or None


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    startup_delay_ms: int | None = None,
    degraded_reason: str | None = None,
) -> CompanionServer:
    return CompanionServer(
        (host, port),
        startup_delay_ms=(
            _startup_delay_ms_from_env() if startup_delay_ms is None else startup_delay_ms
        ),
        degraded_reason=(
            _degraded_reason_from_env() if degraded_reason is None else degraded_reason
        ),
    )


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = create_server(host=host, port=port)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m companion.http_api",
        description="Starts the Stealth Lightbeacon desktop companion HTTP adapter.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
