from __future__ import annotations

import asyncio
import json
import ssl
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import parse_qs, urlparse

import config
from main import run_evaluation, select_active_evaluators
from modules.scraping import ScrapingFactory
from report.formats import build_report_payload
from utils.ontology import OntologyStore
from utils.recon import inspect_recon

from .contract import (
    DEFAULT_SERVICE_HOST,
    DEFAULT_SERVICE_PORT,
    build_capabilities,
    build_compatibility_response,
    load_openapi_document,
)


def _json_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")


class EvaluationService:
    def __init__(
        self,
        *,
        host: str = DEFAULT_SERVICE_HOST,
        port: int = DEFAULT_SERVICE_PORT,
        storage_dir: str = ".data/service",
        auth_token: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.mode = "local" if host in {"127.0.0.1", "localhost", "::1"} else "remote"
        self.auth_token = (auth_token or "").strip() or None
        self.storage_dir = Path(storage_dir)
        self.store = OntologyStore(root_dir=str(self.storage_dir / "ontology"))
        self.executor = ThreadPoolExecutor(max_workers=4)

    def health(self) -> Dict[str, Any]:
        payload = self.store.health()
        if hasattr(self.store.duck_conn, "tables"):
            evaluation_count = len(self.store.duck_conn.tables.get("evaluations", []))
        else:
            try:
                evaluation_count = self.store.duck_conn.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0]
            except Exception:
                evaluation_count = 0
        return {
            "status": "ok",
            "serviceVersion": load_openapi_document()["info"]["version"],
            "mode": self.mode,
            "transport": "http",
            "host": self.host,
            "port": self.port,
            "evaluationCount": evaluation_count,
            "storageReady": payload.get("duckDbReady", False),
        }

    def capabilities(self) -> Dict[str, Any]:
        return build_capabilities(self.mode)

    def compatibility(self, query: Dict[str, list[str]]) -> Dict[str, Any]:
        client_version = (query.get("clientVersion") or query.get("client_version") or [None])[0]
        return build_compatibility_response(
            client_version=client_version,
            host=self.host,
            transport="http",
            auth_required=bool(self.auth_token),
        )

    def ensure_auth(self, headers: Dict[str, str]) -> Tuple[bool, Dict[str, Any] | None]:
        if not self.auth_token:
            return True, None
        token = headers.get("authorization", "")
        if token == f"Bearer {self.auth_token}":
            return True, None
        return False, {"error": "auth_required", "message": "Missing or invalid bearer token."}

    def submit(self, request: Dict[str, Any]) -> Dict[str, Any]:
        target = str(request.get("target") or request.get("targetUrl") or request.get("target_url") or "").strip()
        profile = str(request.get("profile") or "default").strip() or "default"
        output_formats = request.get("outputFormats") or request.get("output_formats") or ["json"]
        accepted_at = request.get("acceptedAt") or request.get("accepted_at")
        if not target:
            raise ValueError("Evaluation target is required")

        create_request = {
            "target": target,
            "profile": profile,
            "outputFormats": output_formats,
            "maxDepth": int(request.get("maxDepth", request.get("max_depth", 1)) or 1),
            "maxUrls": int(request.get("maxUrls", request.get("max_urls", 10)) or 10),
            "failOnCritical": bool(request.get("failOnCritical", request.get("fail_on_critical", False))),
            "budgetGate": bool(request.get("budgetGate", request.get("budget_gate", False))),
            "audits": request.get("audits"),
            "allowPrivate": bool(request.get("allowPrivate", request.get("allow_private", False))),
            "crawlDepth": int(request.get("crawlDepth", request.get("crawl_depth", 0)) or 0),
            "render": bool(request.get("render", False)),
            "http2": bool(request.get("http2", False)),
            "checkLinks": bool(request.get("checkLinks", request.get("check_links", False))),
            "checkApi": bool(request.get("checkApi", request.get("check_api", False))),
            "engine": str(request.get("engine", "http")).strip() or "http",
            "recon": bool(request.get("recon", False)),
            "reconAuto": bool(request.get("reconAuto", request.get("recon_auto", False))),
            "authToken": request.get("authToken") or request.get("auth_token"),
        }
        created = asyncio.run(
            self.store.create_evaluation(
                create_request,
                accepted_at=accepted_at,
            )
        )
        self.executor.submit(self._run_job, created["evaluationId"], create_request)
        return created

    def _run_job(self, evaluation_id: str, request: Dict[str, Any]) -> None:
        try:
            asyncio.run(
                self.store.update_evaluation_status(
                    evaluation_id,
                    status="running",
                    stage="crawl",
                    progress_percent=5,
                    message="Evaluation started",
                )
            )
            audits = request.get("audits")
            active_evaluators = select_active_evaluators(
                ",".join(audits) if isinstance(audits, list) else audits
            )
            if not active_evaluators:
                raise ValueError("No evaluators selected for request")

            allow_private = bool(request.get("allowPrivate"))
            crawl_depth = int(request.get("crawlDepth", 0) or 0)
            max_urls = int(request.get("maxUrls", 10) or 10)
            render = bool(request.get("render", False))
            http2 = bool(request.get("http2", False))
            check_links = bool(request.get("checkLinks", False))
            check_api = bool(request.get("checkApi", False))
            engine = str(request.get("engine", "http")).strip() or "http"
            auth_token = request.get("authToken") or request.get("auth_token")
            recon_enabled = bool(request.get("recon") or request.get("reconAuto"))

            recon_payload = None
            if recon_enabled:
                recon_payload = asyncio.run(inspect_recon(request["target"]))
                if request.get("reconAuto") or request.get("recon_auto"):
                    engine = recon_payload["recommendation"]
                asyncio.run(
                    self.store.update_evaluation_status(
                        evaluation_id,
                        status="running",
                        stage="recon",
                        progress_percent=15,
                        message="Recon recommendation captured",
                    )
                )

            results = asyncio.run(
                run_evaluation(
                    request["target"],
                    active_evaluators,
                    allow_private=allow_private,
                    crawl_depth=crawl_depth,
                    max_urls=max_urls,
                    render=render,
                    http2=http2,
                    scraping_engine=ScrapingFactory.get_engine(engine, allow_private=allow_private),
                    check_links=check_links,
                    check_api=check_api,
                    store=self.store,
                    run_id=evaluation_id,
                    auth_token=auth_token,
                )
            )
            report_payload = build_report_payload(request["target"], results)
            result_payload = asyncio.run(
                self.store.complete_evaluation(
                    evaluation_id,
                    report_payload,
                    base_url=f"http://{self.host}:{self.port}",
                )
            )
        except Exception as exc:
            asyncio.run(
                self.store.update_evaluation_status(
                    evaluation_id,
                    status="failed",
                    stage="failed",
                    progress_percent=100,
                    message=str(exc),
                    exit_state="failure",
                    terminal=True,
                )
            )

    def list_evaluations(self) -> list[Dict[str, Any]]:
        if hasattr(self.store.duck_conn, "tables"):
            rows = [
                (
                    row.get("evaluation_id"),
                    row.get("status"),
                    row.get("stage"),
                    row.get("progress_percent"),
                    row.get("message"),
                    row.get("exit_state"),
                    row.get("terminal"),
                )
                for row in self.store.duck_conn.tables.get("evaluations", [])
            ]
        else:
            rows = self.store.duck_conn.execute(
                """
                SELECT evaluation_id, status, stage, progress_percent, message, exit_state, terminal
                FROM evaluations
                ORDER BY accepted_at DESC
                """
            ).fetchall()
        evaluations = []
        for row in rows:
            evaluation_id, status, stage, progress_percent, message, exit_state, terminal = row
            item = {
                "evaluationId": evaluation_id,
                "status": status,
                "terminal": bool(terminal),
            }
            if stage:
                item["stage"] = stage
            if progress_percent is not None:
                item["progressPercent"] = int(progress_percent)
            if message:
                item["message"] = message
            if exit_state:
                item["exitState"] = exit_state
            evaluations.append(item)
        return evaluations

    def get_evaluation(self, evaluation_id: str) -> Dict[str, Any]:
        return asyncio.run(self.store.get_evaluation_status(evaluation_id))

    def get_result(self, evaluation_id: str) -> Dict[str, Any]:
        return asyncio.run(self.store.get_evaluation_result(evaluation_id))

    def get_artifacts(self, evaluation_id: str) -> list[Dict[str, Any]]:
        return asyncio.run(self.store.get_evaluation_artifacts(evaluation_id, base_url=f"http://{self.host}:{self.port}"))

    def recon(self, target: str) -> Dict[str, Any]:
        return asyncio.run(inspect_recon(target))

    def close(self) -> None:
        self.executor.shutdown(wait=True, cancel_futures=True)
        self.store.close()


class _RequestHandler(BaseHTTPRequestHandler):
    server: "_ServiceHTTPServer"

    def _write_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _auth(self) -> Tuple[bool, Dict[str, Any] | None]:
        allowed, error = self.server.service.ensure_auth({k.lower(): v for k, v in self.headers.items()})
        if not allowed:
            self._write_json(HTTPStatus.UNAUTHORIZED, error or {"error": "auth_required"})
            return False, error
        return True, None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        if path == "/health":
            self._write_json(HTTPStatus.OK, self.server.service.health())
            return
        if path == "/capabilities":
            self._write_json(HTTPStatus.OK, self.server.service.capabilities())
            return
        if path == "/compatibility":
            self._write_json(HTTPStatus.OK, self.server.service.compatibility(query))
            return

        allowed, _ = self._auth()
        if not allowed:
            return

        if path == "/evaluations":
            self._write_json(HTTPStatus.OK, {"evaluations": self.server.service.list_evaluations()})
            return

        parts = [item for item in path.split("/") if item]
        if len(parts) >= 2 and parts[0] == "evaluations":
            evaluation_id = parts[1]
            if len(parts) == 2:
                try:
                    self._write_json(HTTPStatus.OK, self.server.service.get_evaluation(evaluation_id))
                except ValueError as exc:
                    self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": str(exc)})
                return
            if len(parts) == 3 and parts[2] == "result":
                try:
                    self._write_json(HTTPStatus.OK, self.server.service.get_result(evaluation_id))
                except ValueError as exc:
                    self._write_json(HTTPStatus.CONFLICT, {"error": "not_ready", "message": str(exc)})
                return
            if len(parts) == 3 and parts[2] == "artifacts":
                try:
                    self._write_json(
                        HTTPStatus.OK,
                        {"evaluationId": evaluation_id, "artifacts": self.server.service.get_artifacts(evaluation_id)},
                    )
                except ValueError as exc:
                    self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": str(exc)})
                return

        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": "Unknown route"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/recon":
            allowed, _ = self._auth()
            if not allowed:
                return
            body = self._read_json()
            target = str(body.get("target") or body.get("targetUrl") or body.get("target_url") or "").strip()
            if not target:
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": "missing_target"})
                return
            try:
                self._write_json(HTTPStatus.OK, self.server.service.recon(target))
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_GATEWAY, {"error": "recon_failed", "message": str(exc)})
            return

        allowed, _ = self._auth()
        if not allowed:
            return

        if path == "/evaluations":
            body = self._read_json()
            try:
                self._write_json(HTTPStatus.ACCEPTED, self.server.service.submit(body))
            except ValueError as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request", "message": str(exc)})
            return

        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": "Unknown route"})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


class _ServiceHTTPServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], service: EvaluationService):
        super().__init__(address, _RequestHandler)
        self.service = service


def run_service(
    *,
    host: str = DEFAULT_SERVICE_HOST,
    port: int = DEFAULT_SERVICE_PORT,
    storage_dir: str = ".data/service",
    auth_token: str | None = None,
    tls_certfile: str | None = None,
    tls_keyfile: str | None = None,
) -> None:
    service = EvaluationService(host=host, port=port, storage_dir=storage_dir, auth_token=auth_token)
    server = _ServiceHTTPServer((host, port), service)

    if tls_certfile and tls_keyfile:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=tls_certfile, keyfile=tls_keyfile)
        server.socket = context.wrap_socket(server.socket, server_side=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.close()
        server.shutdown()
        server.server_close()
