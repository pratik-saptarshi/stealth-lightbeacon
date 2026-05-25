"""
stealth_mcp.py — Standardized MCP client protocol layer for executing scraping workloads.
Communicates with standard Model Context Protocol servers to execute visual playbooks.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import config
from modules.scraping.base import ScrapingEngine
from utils.ssrf_guard import SSRFGuard
from modules.scraping.obscura import ObscuraEngine

logger = logging.getLogger("stealth_mcp")


class StealthMcpLayer(ScrapingEngine):
    """
    Client layer wrapping scraping playbooks inside standard Model Context Protocol actions.
    """

    def __init__(
        self,
        mcp_command: Optional[str] = None,
        mcp_args: Optional[List[str]] = None,
        allow_private: bool = False,
        handshake_timeout: float = 6.0,
    ):
        resolved_command = (mcp_command or config.MCP_COMMAND or "").strip()
        if not resolved_command:
            raise RuntimeError(
                "MCP command is not configured. Set SLB_MCP_COMMAND with a pinned MCP executable."
            )

        resolved_args = list(mcp_args) if mcp_args is not None else list(config.MCP_COMMAND_ARGS)
        if not resolved_args and mcp_args is None:
            # Keep behavior deterministic without mutable defaults.
            resolved_args = []

        self.mcp_command = resolved_command
        self.mcp_args = resolved_args
        self.allow_private = allow_private
        self.handshake_timeout = float(handshake_timeout) if handshake_timeout is not None else 6.0
        self.ssrf_guard = SSRFGuard(allow_private=allow_private)

    async def _read_json(self, process: asyncio.subprocess.Process, marker: str) -> Dict[str, Any]:
        stdout_line = await asyncio.wait_for(process.stdout.readline(), timeout=self.handshake_timeout)
        if not stdout_line:
            raise RuntimeError(f"No MCP {marker} response from subprocess.")
        try:
            return json.loads(stdout_line.decode())
        except Exception as exc:
            raise RuntimeError(f"Invalid MCP {marker} JSON payload: {stdout_line!r}") from exc

    async def _write_json(self, process: asyncio.subprocess.Process, payload: Dict[str, Any]) -> None:
        process.stdin.write((json.dumps(payload) + "\n").encode())
        await process.stdin.drain()

    async def _run_tool(
        self,
        process: asyncio.subprocess.Process,
        payload: Dict[str, Any],
        marker: str,
    ) -> Dict[str, Any]:
        await self._write_json(process, payload)
        return await self._read_json(process, marker)

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

            handshake = await self._run_tool(process, init_message, "handshake")
            if "error" in handshake:
                raise RuntimeError(f"MCP handshake failed: {handshake['error']}")

            content_call = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "playwright_navigate",
                    "arguments": {
                        "url": url,
                    },
                },
            }
            nav_resp = await self._run_tool(process, content_call, "navigation")
            if "error" in nav_resp:
                raise RuntimeError(f"MCP navigation failed: {nav_resp['error']}")

            content_call = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "playwright_evaluate",
                    "arguments": {
                        "script": "document.documentElement.outerHTML"
                    },
                },
            }
            content_resp = await self._run_tool(process, content_call, "content")
            if "error" in content_resp:
                raise RuntimeError(f"MCP content call failed: {content_resp['error']}")

            result = content_resp.get("result", {})
            content_items = result.get("content", [])
            if not content_items:
                raise RuntimeError(f"Unexpected MCP content response: {content_resp}")

            text = content_items[0].get("text")
            if not isinstance(text, str):
                raise RuntimeError(f"Unexpected MCP content response structure: {content_resp}")
            return text
        except Exception as exc:
            logger.error("Stealth Browser MCP Protocol Execution failed: %s", str(exc))
            direct_engine = ObscuraEngine(allow_private=self.allow_private)
            return await direct_engine.scrape(url)
        finally:
            if process is not None:
                try:
                    process.terminate()
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(process.wait(), timeout=1.0)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
