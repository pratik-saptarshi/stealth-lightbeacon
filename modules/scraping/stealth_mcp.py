"""
stealth_mcp.py — Standardized MCP client protocol layer for executing scraping workloads.
Communicates with standard Model Context Protocol servers to execute visual playbooks.
"""

import logging
import json
import asyncio
from typing import Optional, Any
from modules.scraping.base import ScrapingEngine
from utils.ssrf_guard import SSRFGuard

logger = logging.getLogger("stealth_mcp")

class StealthMcpLayer(ScrapingEngine):
    """
    Client layer wrapping scraping playbooks inside standard Model Context Protocol actions.
    """
    def __init__(
        self,
        mcp_command: Optional[str] = None,
        mcp_args: Optional[list] = None,
        handshake_timeout: float = 10.0,
        tool_timeout: float = 30.0,
        shutdown_timeout: float = 5.0,
        allow_private: bool = False
    ):
        self.mcp_command = mcp_command or "npx"
        self.mcp_args = mcp_args or ["-y", "@modelcontextprotocol/server-playwright"]
        self.handshake_timeout = handshake_timeout
        self.tool_timeout = tool_timeout
        self.shutdown_timeout = shutdown_timeout
        self.allow_private = allow_private
        self.ssrf_guard = SSRFGuard(allow_private=allow_private)
        self._validate_command_config()

    def _validate_command_config(self) -> None:
        joined = " ".join([self.mcp_command, *self.mcp_args]).strip()
        if self.mcp_command == "npx" and self.mcp_args == ["-y", "@modelcontextprotocol/server-playwright"]:
            raise ValueError(
                "MCP mode requires an explicit pinned executable or versioned package; "
                "set SLB_MCP_COMMAND/SLB_MCP_ARGS instead of using the mutable runtime download default."
            )
        if self.mcp_command == "npx" and "@modelcontextprotocol/server-playwright@" not in joined and not any(
            arg.startswith(".") or arg.startswith("/") for arg in self.mcp_args
        ):
            raise ValueError(
                "MCP mode must use a pinned package version or a local executable path."
            )

    async def _drain(self, stream: Any) -> None:
        await asyncio.wait_for(stream.drain(), timeout=self.tool_timeout)

    async def _read_json(self, stream: Any, timeout: float, stage: str) -> dict:
        raw = await asyncio.wait_for(stream.readline(), timeout=timeout)
        if not raw:
            raise TimeoutError(f"{stage} timed out while waiting for MCP output")
        return json.loads(raw.decode())

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
        # Validate SSRF safety
        await self.ssrf_guard.validate(url)
        
        logger.info(f"Connecting to Stealth Browser MCP server subprocess via: {self.mcp_command} {' '.join(self.mcp_args)}")
        
        try:
            # Spawn the MCP server subprocess
            process = await asyncio.create_subprocess_exec(
                self.mcp_command,
                *self.mcp_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Formulate the standard MCP initialization message
            init_message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "DrupalEvaluatorStealthClient",
                        "version": "1.0.0"
                    }
                }
            }
            
            # Send initialization handshake
            process.stdin.write((json.dumps(init_message) + "\n").encode())
            await self._drain(process.stdin)
            
            # Read server handshake response
            handshake_resp = await self._read_json(process.stdout, self.handshake_timeout, "MCP handshake")
            logger.debug(f"MCP Server Handshake Received: {handshake_resp}")
            
            # Formulate playbooks execution call
            # We call the Playwright server's "playwright_navigate" tool
            mcp_call = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "playwright_navigate",
                    "arguments": {
                        "url": url
                    }
                }
            }
            
            process.stdin.write((json.dumps(mcp_call) + "\n").encode())
            await self._drain(process.stdin)
            
            # Read navigation response
            navigate_resp = await self._read_json(process.stdout, self.tool_timeout, "MCP navigation")
            logger.debug(f"MCP Navigation Completed: {navigate_resp}")
            
            # Fetch DOM content using standard page content call
            content_call = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "playwright_evaluate",
                    "arguments": {
                        "script": "document.documentElement.outerHTML"
                    }
                }
            }
            
            process.stdin.write((json.dumps(content_call) + "\n").encode())
            await self._drain(process.stdin)
            
            content_resp = await self._read_json(process.stdout, self.tool_timeout, "MCP content")
            
            # Extract content string
            try:
                html_content = content_resp["result"]["content"][0]["text"]
                
                # Standard teardown
                close_call = {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "playwright_close",
                        "arguments": {}
                    }
                }
                process.stdin.write((json.dumps(close_call) + "\n").encode())
                await self._drain(process.stdin)
                
                return html_content
            except Exception as e:
                raise ValueError(f"Unexpected response structure from Playwright MCP server: {content_resp}") from e
                
            finally:
                await self._terminate(process)
        except Exception as e:
            logger.error(f"Stealth Browser MCP Protocol Execution failed: {str(e)}")
            # Graceful fallback to standard browser-spoofing http client
            logger.warning("Stealth Browser MCP failed; falling back to direct Http Client scraping...")
            from modules.scraping.obscura import ObscuraEngine
            direct_engine = ObscuraEngine(allow_private=self.allow_private)
            return await direct_engine.scrape(url)
