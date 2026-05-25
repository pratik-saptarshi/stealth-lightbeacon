"""
factory.py — Strategy selector factory for pluggable adversarial scraping engines.
"""

from typing import Optional
import config
from modules.scraping.base import ScrapingEngine
from modules.scraping.obscura import ObscuraEngine
from modules.scraping.zendriver import ZendriverEngine
from modules.scraping.stealth_mcp import StealthMcpLayer

class ScrapingFactory:
    """
    Factory creating ScrapingEngine strategies according to user CLI parameters.
    """
    @staticmethod
    def get_engine(
        engine_type: str = "http",
        allow_private: bool = False
    ) -> ScrapingEngine:
        """
        Instantiates and returns the designated ScrapingEngine class strategy.
        """
        engine_type = engine_type.lower().strip()
        
        if engine_type == "fast":
            # Rust static binary fast-path / TLS fingerprint spoof fallback
            return ObscuraEngine(binary_path="bin/obscura", allow_private=allow_private)
            
        elif engine_type == "stealth":
            # Anti-detect Playwright Chromium heavy-path
            return ZendriverEngine(allow_private=allow_private)
            
        elif engine_type == "mcp":
            # Model Context Protocol browser tools standard layer
            return StealthMcpLayer(
                mcp_command=config.MCP_COMMAND,
                mcp_args=config.MCP_ARGS or None,
                handshake_timeout=config.MCP_HANDSHAKE_TIMEOUT,
                tool_timeout=config.MCP_TOOL_TIMEOUT,
                shutdown_timeout=config.MCP_SHUTDOWN_TIMEOUT,
                allow_private=allow_private,
            )
            
        else:
            # "http" or other fallbacks -> Spoofed HTTP/2 client
            return ObscuraEngine(binary_path="bin/obscura_absent", allow_private=allow_private)
