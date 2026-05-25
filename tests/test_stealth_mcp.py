import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

import modules.scraping.stealth_mcp as stealth_mcp


class _MockStdout:
    def __init__(self, lines):
        self._lines = [line.encode() if isinstance(line, str) else line for line in lines]

    async def readline(self):
        if not self._lines:
            return b""
        return self._lines.pop(0)


@pytest.mark.asyncio
async def test_stealth_mcp_requires_configured_command(monkeypatch):
    monkeypatch.setattr(stealth_mcp.config, "MCP_COMMAND", "")
    with pytest.raises(RuntimeError, match="MCP command is not configured"):
        stealth_mcp.StealthMcpLayer()


@pytest.mark.asyncio
async def test_stealth_mcp_scrape_happy_path(monkeypatch):
    monkeypatch.setattr(stealth_mcp.config, "MCP_COMMAND", "/usr/bin/mcp-test")
    monkeypatch.setattr(stealth_mcp.config, "MCP_COMMAND_ARGS", ["--stdio"])

    process = MagicMock()
    process.stdin = MagicMock()
    process.stdin.write = MagicMock()
    process.stdin.drain = AsyncMock()
    process.stdout = _MockStdout([
        '{"result": {"protocolVersion": "2024-11-05"}}',
        '{"result": {"content": []}}',
        '{"result": {"content": [{"text": "<html>ok</html>"}]}}',
    ])
    process.terminate = MagicMock()
    process.wait = AsyncMock()
    process.kill = MagicMock()

    async def _create_subprocess_exec(*args, **kwargs):
        return process

    monkeypatch.setattr(stealth_mcp.asyncio, "create_subprocess_exec", _create_subprocess_exec)
    guard_mock = AsyncMock()
    guard_mock.validate.return_value = asyncio.sleep(0)
    monkeypatch.setattr(stealth_mcp, "SSRFGuard", lambda allow_private=False: guard_mock)

    scraper = stealth_mcp.StealthMcpLayer()
    html = await scraper.scrape("https://example.com")

    assert html == "<html>ok</html>"
    process.stdin.write.assert_called()
