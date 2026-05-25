import asyncio

import pytest

from modules.scraping.stealth_mcp import StealthMcpLayer


class _FakeStream:
    def __init__(self, lines):
        self._lines = list(lines)
        self.writes = []

    def write(self, data):
        self.writes.append(data)

    async def drain(self):
        return None

    async def readline(self):
        if not self._lines:
            return b""
        return self._lines.pop(0)


class _FakeProcess:
    def __init__(self, lines):
        self.stdin = _FakeStream(lines)
        self.stdout = _FakeStream(lines)
        self.stderr = _FakeStream([])
        self.terminate_called = False
        self.kill_called = False
        self.wait_called = False

    def terminate(self):
        self.terminate_called = True

    def kill(self):
        self.kill_called = True

    async def wait(self):
        self.wait_called = True
        return 0


def test_mcp_layer_rejects_mutable_runtime_download_default():
    with pytest.raises(ValueError, match="pinned executable or versioned package"):
        StealthMcpLayer()


@pytest.mark.asyncio
async def test_mcp_layer_scrape_uses_bounded_timeouts_and_shutdown(monkeypatch):
    lines = [
        b'{"result": {"capabilities": {}}}\n',
        b'{"result": {"ok": true}}\n',
        b'{"result": {"content": [{"text": "<html><body>ok</body></html>"}]}}\n',
    ]
    fake_process = _FakeProcess(lines)
    timeouts = []

    async def fake_wait_for(awaitable, timeout):
        timeouts.append(timeout)
        return await awaitable

    async def fake_subprocess_exec(*args, **kwargs):
        return fake_process

    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_subprocess_exec)

    layer = StealthMcpLayer(
        mcp_command="/opt/mcp/playwright",
        mcp_args=["--pinned", "1.2.3"],
        handshake_timeout=3.5,
        tool_timeout=7.5,
        shutdown_timeout=2.5,
    )

    html = await layer.scrape("https://example.com")

    assert html == "<html><body>ok</body></html>"
    assert fake_process.terminate_called is True
    assert fake_process.wait_called is True
    assert 3.5 in timeouts
    assert 7.5 in timeouts
    assert 2.5 in timeouts
