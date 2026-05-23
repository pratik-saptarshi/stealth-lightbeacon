"""
stealth_mcp.py — Standardized MCP client protocol layer for executing scraping workloads.
Communicates with standard Model Context Protocol servers to execute visual playbooks.
"""

import logging
import json
import asyncio
from typing import Optional
from modules.scraping.base import ScrapingEngine
from utils.ssrf_guard import SSRFGuard

logger = logging.getLogger("stealth_mcp")

class StealthMcpLayer(ScrapingEngine):
    """
    Client layer wrapping scraping playbooks inside standard Model Context Protocol actions.
    """
    def __init__(
        self,
        mcp_command: str = "npx",
        mcp_args: Optional[list] = None,
        allow_private: bool = False
    ):
        self.mcp_command = mcp_command
        self.mcp_args = mcp_args or ["-y", "@modelcontextprotocol/server-playwright"]
        self.allow_private = allow_private
        self.ssrf_guard = SSRFGuard(allow_private=allow_private)

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
            await process.stdin.drain()
            
            # Read server handshake response
            stdout_line = await process.stdout.readline()
            handshake_resp = json.loads(stdout_line.decode())
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
            await process.stdin.drain()
            
            # Read navigation response
            stdout_line = await process.stdout.readline()
            navigate_resp = json.loads(stdout_line.decode())
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
            await process.stdin.drain()
            
            stdout_line = await process.stdout.readline()
            content_resp = json.loads(stdout_line.decode())
            
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
                await process.stdin.drain()
                
                return html_content
            except Exception as e:
                raise ValueError(f"Unexpected response structure from Playwright MCP server: {content_resp}") from e
                
            finally:
                try:
                    process.terminate()
                    await process.wait()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Stealth Browser MCP Protocol Execution failed: {str(e)}")
            # Graceful fallback to standard browser-spoofing http client
            logger.warning("Stealth Browser MCP failed; falling back to direct Http Client scraping...")
            from modules.scraping.obscura import ObscuraEngine
            direct_engine = ObscuraEngine(allow_private=self.allow_private)
            return await direct_engine.scrape(url)
