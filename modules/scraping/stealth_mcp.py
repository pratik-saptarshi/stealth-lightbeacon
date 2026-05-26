"""
stealth_mcp.py — Standardized MCP client protocol layer for executing scraping workloads.
Communicates with standard Model Context Protocol servers to execute visual playbooks.
"""

import asyncio
import json
import logging
from typing import Any, Optional

import config
from modules.scraping.base import ScrapingEngine
from modules.scraping.obscura import ObscuraEngine
from utils.ssrf_guard import SSRFGuard

logger = logging.getLogger("stealth_mcp")


class MCPConfigurationError(RuntimeError, ValueError):
    """Raised when MCP mode is requested without a pinned executable or versioned package."""


class StealthMcpLayer(ScrapingEngine):
    """
    Client layer wrapping scraping playbooks inside standard Model Context Protocol actions.
    """

    def __init__(
        self,
        mcp_command: Optional[str] = None,
        mcp_args: Optional[list] = None,
        handshake_timeout: Optional[float] = None,
        tool_timeout: Optional[float] = None,
        shutdown_timeout: Optional[float] = None,
        allow_private: bool = False,
    ):
        default_args = getattr(config, "MCP_COMMAND_ARGS", config.MCP_ARGS)
        self.mcp_command = (mcp_command or config.MCP_COMMAND or "").strip()
        self.mcp_args = list(mcp_args) if mcp_args is not None else list(default_args)
        self.handshake_timeout = float(
            handshake_timeout if handshake_timeout is not None else config.MCP_HANDSHAKE_TIMEOUT
        )
        self.tool_timeout = float(tool_timeout if tool_timeout is not None else config.MCP_TOOL_TIMEOUT)
        self.shutdown_timeout = float(
            shutdown_timeout if shutdown_timeout is not None else config.MCP_SHUTDOWN_TIMEOUT
        )
        self.allow_private = allow_private
        self.ssrf_guard = SSRFGuard(allow_private=allow_private)
        self._validate_command_config()

    def _validate_command_config(self) -> None:
        joined = " ".join([self.mcp_command, *self.mcp_args]).strip()
        if not self.mcp_command:
            raise MCPConfigurationError(
                "MCP command is not configured. Set SLB_MCP_COMMAND with a pinned executable or versioned package."
            )
        if self.mcp_command == "npx" and (
            self.mcp_args == ["-y", "@modelcontextprotocol/server-playwright"]
            or (
                "@modelcontextprotocol/server-playwright@" not in joined
                and not any(arg.startswith(".") or arg.startswith("/") for arg in self.mcp_args)
            )
        ):
            raise ValueError(
                "MCP mode requires an explicit pinned executable or versioned package; "
                "set SLB_MCP_COMMAND/SLB_MCP_ARGS instead of using the mutable runtime download default."
            )

    async def _drain(self, stream: Any) -> None:
        await asyncio.wait_for(stream.drain(), timeout=self.tool_timeout)

    async def _read_json(self, stream: Any, timeout: float, stage: str) -> dict:
        raw = await asyncio.wait_for(stream.readline(), timeout=timeout)
        if not raw:
            raise TimeoutError(f"{stage} timed out while waiting for MCP output")
        try:
            return json.loads(raw.decode())
        except Exception as exc:
            raise RuntimeError(f"Invalid MCP {stage} JSON payload: {raw!r}") from exc

    async def _terminate(self, process: Any) -> None:
        try:
            process.terminate()
        except Exception:
            pass
        try:
            await asyncio.wait_for(process.wait(), timeout=self.shutdown_timeout)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass
            try:
                await asyncio.wait_for(process.wait(), timeout=self.shutdown_timeout)
            except Exception:
                pass

    async def scrape(self, url: str) -> str:
        """
        Communicates with Playwright MCP server via stdin/stdout processes to scrape target page.
        """
        await self.ssrf_guard.validate(url)

        logger.info(
            "Connecting to Stealth Browser MCP server subprocess via: %s %s",
            self.mcp_command,
            " ".join(self.mcp_args),
        )

        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                self.mcp_command,
                *self.mcp_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            init_message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "StealthLightbeaconCLI",
                        "version": "1.0.0",
                    },
                },
            }
            process.stdin.write((json.dumps(init_message) + "\n").encode())
            await self._drain(process.stdin)

            handshake_resp = await self._read_json(process.stdout, self.handshake_timeout, "MCP handshake")
            if "error" in handshake_resp:
                raise RuntimeError(f"MCP handshake failed: {handshake_resp['error']}")

            navigate_call = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "playwright_navigate",
                    "arguments": {"url": url},
                },
            }
            process.stdin.write((json.dumps(navigate_call) + "\n").encode())
            await self._drain(process.stdin)

            navigate_resp = await self._read_json(process.stdout, self.tool_timeout, "MCP navigation")
            if "error" in navigate_resp:
                raise RuntimeError(f"MCP navigation failed: {navigate_resp['error']}")

            content_call = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "playwright_evaluate",
                    "arguments": {"script": "document.documentElement.outerHTML"},
                },
            }
            process.stdin.write((json.dumps(content_call) + "\n").encode())
            await self._drain(process.stdin)

            content_resp = await self._read_json(process.stdout, self.tool_timeout, "MCP content")
            result = content_resp.get("result", {})
            content_items = result.get("content", [])
            if not content_items:
                raise RuntimeError(f"Unexpected MCP content response: {content_resp}")

            text = content_items[0].get("text")
            if not isinstance(text, str):
                raise RuntimeError(f"Unexpected MCP content response structure: {content_resp}")

            close_call = {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "playwright_close",
                    "arguments": {},
                },
            }
            process.stdin.write((json.dumps(close_call) + "\n").encode())
            await self._drain(process.stdin)
            return text
        except Exception as exc:
            logger.error("Stealth Browser MCP Protocol Execution failed: %s", str(exc))
            logger.warning("Stealth Browser MCP failed; falling back to direct Http Client scraping...")
            direct_engine = ObscuraEngine(allow_private=self.allow_private)
            return await direct_engine.scrape(url)
        finally:
            if process is not None:
                await self._terminate(process)
