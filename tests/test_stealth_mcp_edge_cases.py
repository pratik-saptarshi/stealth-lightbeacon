from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import modules.scraping.stealth_mcp as stealth_mcp


class _Lines:
    def __init__(self, lines):
        self._lines = list(lines)
        self.writes = []

    def write(self, data):
        self.writes.append(data)

    async def readline(self):
        if not self._lines:
            return b""
        return self._lines.pop(0)

    async def drain(self):
        return None


class _FallbackEngine:
    def __init__(self, allow_private=False):
        self.allow_private = allow_private

    async def scrape(self, url):
        return "<html><body>fallback</body></html>"


class _FakeProcess:
    def __init__(self, stdout_lines):
        self.stdin = _Lines([])
        self.stdout = _Lines(stdout_lines)
        self.terminate_called = False
        self.kill_called = False
        self.wait_calls = 0

    def terminate(self):
        self.terminate_called = True

    def kill(self):
        self.kill_called = True

    async def wait(self):
        self.wait_calls += 1
        raise TimeoutError("still running")


def _configure_layer(monkeypatch):
    monkeypatch.setattr(stealth_mcp.config, "MCP_COMMAND", "/opt/mcp/playwright")
    monkeypatch.setattr(stealth_mcp.config, "MCP_COMMAND_ARGS", ["--stdio", "--pinned", "1.2.3"])
    return stealth_mcp.StealthMcpLayer()


@pytest.mark.asyncio
async def test_mcp_read_json_and_terminate_paths(monkeypatch):
    layer = _configure_layer(monkeypatch)

    with pytest.raises(RuntimeError, match="Invalid MCP handshake JSON payload"):
        await layer._read_json(_Lines([b"not-json\n"]), timeout=0.1, stage="handshake")

    with pytest.raises(TimeoutError, match="timed out"):
        await layer._read_json(_Lines([]), timeout=0.1, stage="handshake")

    process = _FakeProcess([])
    layer.shutdown_timeout = 0.1
    await layer._terminate(process)

    assert process.terminate_called is True
    assert process.kill_called is True
    assert process.wait_calls >= 2


@pytest.mark.asyncio
async def test_mcp_scrape_falls_back_on_handshake_error(monkeypatch):
    layer = _configure_layer(monkeypatch)
    process = _FakeProcess(
        [
            b'{"error": {"message": "handshake failed"}}\n',
        ]
    )

    async def fake_exec(*args, **kwargs):
        return process

    monkeypatch.setattr(stealth_mcp.asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(stealth_mcp, "ObscuraEngine", _FallbackEngine)
    layer.ssrf_guard.validate = AsyncMock(return_value=None)

    html = await layer.scrape("https://example.com")

    assert html == "<html><body>fallback</body></html>"
    assert process.terminate_called is True
