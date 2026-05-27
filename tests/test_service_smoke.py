from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


class _TargetHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = b"<html><head><title>Smoke Target</title></head><body>ok</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A003
        return


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _start_target_server() -> tuple[HTTPServer, threading.Thread, str]:
    port = _free_port()
    server = HTTPServer(("127.0.0.1", port), _TargetHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{port}"


def _read_json(url: str, method: str = "GET", data: dict | None = None, headers: dict | None = None) -> dict:
    payload = None if data is None else json.dumps(data).encode("utf-8")
    request = Request(url, data=payload, headers=headers or {}, method=method)
    if payload is not None:
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_for_health(base_url: str, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            return _read_json(f"{base_url}/health")
        except Exception as exc:  # pragma: no cover - retry loop
            last_error = exc
            time.sleep(0.25)
    raise AssertionError(f"service did not become healthy: {last_error}")


def test_service_boots_and_handles_core_routes(tmp_path):
    target_server, target_thread, target_url = _start_target_server()
    service_port = _free_port()
    base_url = f"http://127.0.0.1:{service_port}"
    service_storage = tmp_path / "service"
    proc = subprocess.Popen(
        [
            sys.executable,
            "main.py",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(service_port),
            "--storage-dir",
            str(service_storage),
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    try:
        health = _wait_for_health(base_url)
        assert health["status"] == "ok"
        assert health["host"] == "127.0.0.1"
        assert health["port"] == service_port

        capabilities = _read_json(f"{base_url}/capabilities")
        assert capabilities["supportsRecon"] is True
        assert capabilities["supportsArtifacts"] is True
        assert capabilities["apiMode"]["transport"] == "http"

        compatibility = _read_json(f"{base_url}/compatibility?clientVersion=1.2.4")
        assert compatibility["compatible"] is True
        assert compatibility["serverMode"] == "local"

        recon = _read_json(
            f"{base_url}/recon",
            method="POST",
            data={"target": target_url},
        )
        assert recon["target"] == target_url
        assert "recommendation" in recon

        created = _read_json(
            f"{base_url}/evaluations",
            method="POST",
            data={
                "target": target_url,
                "profile": "default",
                "audits": "seo",
                "outputFormats": ["both"],
                "allowPrivate": True,
                "recon": True,
            },
        )
        evaluation_id = created["evaluationId"]
        assert created["status"] == "queued"

        deadline = time.time() + 90.0
        status = {}
        while time.time() < deadline:
            status = _read_json(f"{base_url}/evaluations/{evaluation_id}")
            if status.get("status") in {"completed", "failed"}:
                break
            time.sleep(0.5)

        assert status["status"] == "completed", status
        assert status["terminal"] is True

        result = _read_json(f"{base_url}/evaluations/{evaluation_id}/result")
        assert result["evaluationId"] == evaluation_id
        assert result["status"] == "completed"
        assert result["summary"]["target_url"] == target_url

        artifacts = _read_json(f"{base_url}/evaluations/{evaluation_id}/artifacts")
        names = [artifact["name"] for artifact in artifacts["artifacts"]]
        assert "report.json" in names
        assert "report.html" in names
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=15)
        target_server.shutdown()
        target_thread.join(timeout=5)
