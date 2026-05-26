"""Thin HTTP companion adapter for desktop bootstrap routes."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict
from urllib.parse import urlparse

from contracts.backend_api import API_VERSION, APP_VERSION, build_openapi_document
from utils.agent_card import build_agent_card

SERVICE_NAME = "stealth-lightbeacon-api"


class ApiRouteError(Exception):
    """Structured transport error for HTTP responses."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        details: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "status": self.status,
        }
        if self.details is not None:
            payload["details"] = self.details
        return payload


class CompanionApi:
    """Pure route dispatcher for the desktop companion surface."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def health_response(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "service": SERVICE_NAME,
            "apiVersion": API_VERSION,
            "appVersion": APP_VERSION,
        }

    def capabilities_response(self) -> Dict[str, Any]:
        card = build_agent_card()
        return {
            "apiMode": {
                "mode": "local",
                "baseUrl": self.base_url,
                "transport": "http",
                "apiVersion": API_VERSION,
                "supportsRemote": False,
            },
            "evaluationProfiles": list(card["audits"]),
            "outputFormats": list(card["outputs"]["formats"]),
            "supportsRecon": True,
            "supportsArtifacts": True,
        }

    def dispatch(self, method: str, path: str) -> tuple[int, Dict[str, Any]]:
        normalized_path = path.rstrip("/") or "/"
        if method != "GET":
            if normalized_path in {"/health", "/capabilities", "/openapi.json"}:
                raise ApiRouteError(
                    status=HTTPStatus.METHOD_NOT_ALLOWED,
                    code="method_not_allowed",
                    message="Route does not support that HTTP method.",
                    details=f"{method} {normalized_path}",
                )
            raise ApiRouteError(
                status=HTTPStatus.NOT_FOUND,
                code="not_found",
                message="Route not found.",
                details=normalized_path,
            )

        if normalized_path == "/health":
            return HTTPStatus.OK, self.health_response()
        if normalized_path == "/capabilities":
            return HTTPStatus.OK, self.capabilities_response()
        if normalized_path == "/openapi.json":
            return HTTPStatus.OK, build_openapi_document()

        raise ApiRouteError(
            status=HTTPStatus.NOT_FOUND,
            code="not_found",
            message="Route not found.",
            details=normalized_path,
        )


class CompanionServer(ThreadingHTTPServer):
    """Server wrapper that carries backend companion state."""

    daemon_threads = True

    def __init__(self, server_address: tuple[str, int]) -> None:
        super().__init__(server_address, CompanionRequestHandler)
        host, port = self.server_address
        self.base_url = f"http://{host}:{port}"
        self.api = CompanionApi(base_url=self.base_url)


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
        try:
            status, payload = self.server.api.dispatch(method=method, path=parsed.path)
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

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(host: str = "127.0.0.1", port: int = 8000) -> CompanionServer:
    return CompanionServer((host, port))


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
