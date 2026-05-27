"""
config.py — Shared configuration and constants for Stealth Lightbeacon.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ─── PageSpeed Insights API ───────────────────────────────────────────────────
PAGESPEED_API_KEY = os.getenv("PAGESPEED_API_KEY", "")
PAGESPEED_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

# ─── HTTP Request Settings ────────────────────────────────────────────────────
REQUEST_TIMEOUT = 15  # seconds
REQUEST_HEADERS = {
    "User-Agent": (
        "StealthLightbeacon/1.2.4 (+https://github.com/pratik-saptarshi/stealth-lightbeacon) "
        "Mozilla/5.0 (compatible; StealthLightbeaconBot/1.2.4)"
    )
}


def build_request_headers(auth_token: str | None = None) -> dict:
    headers = dict(REQUEST_HEADERS)
    token = auth_token or os.getenv("SLB_AUTH_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

# ─── Scoring Thresholds ────────────────────────────────────────────────────────
# Core Web Vitals (Google thresholds)
LCP_GOOD = 2500  # ms
LCP_POOR = 4000  # ms
INP_GOOD = 200  # ms
INP_POOR = 500  # ms
CLS_GOOD = 0.1
CLS_POOR = 0.25
TTFB_GOOD = 800  # ms
TTFB_POOR = 1800  # ms

# ─── Issue Severity Levels ─────────────────────────────────────────────────────
SEVERITY_CRITICAL = "critical"
SEVERITY_WARNING = "warning"
SEVERITY_PASS = "pass"
SEVERITY_INFO = "info"

# ─── AEO ──────────────────────────────────────────────────────────────────────
DIRECT_ANSWER_MAX_WORDS = 50  # max words for a "direct answer" paragraph

# ─── GEO ──────────────────────────────────────────────────────────────────────
KEYWORD_STUFFING_DENSITY = 0.04  # 4% single-keyword density triggers a warning

# ─── Report ───────────────────────────────────────────────────────────────────
REPORT_OUTPUT_DIR = "reports"

# ─── Service ──────────────────────────────────────────────────────────────────
SERVICE_DEFAULT_HOST = os.getenv("SLB_SERVICE_HOST", "127.0.0.1")
SERVICE_DEFAULT_PORT = int(os.getenv("SLB_SERVICE_PORT", "8000"))
SERVICE_DEFAULT_SCHEME = os.getenv("SLB_SERVICE_SCHEME", "http")
SERVICE_DEFAULT_BASE_URL = os.getenv(
    "SLB_SERVICE_BASE_URL",
    f"{SERVICE_DEFAULT_SCHEME}://{SERVICE_DEFAULT_HOST}:{SERVICE_DEFAULT_PORT}",
)
SERVICE_REMOTE_SCHEME = os.getenv("SLB_SERVICE_REMOTE_SCHEME", "https")
SERVICE_STDIN_ADAPTER = os.getenv("SLB_SERVICE_STDIN_ADAPTER", "stdin")
SERVICE_STORAGE_DIR = os.getenv("SLB_SERVICE_STORAGE_DIR", ".data/service")
SERVICE_VERSION = os.getenv("SLB_SERVICE_VERSION", "1.2.4")

# ─── MCP ───────────────────────────────────────────────────────────────────────
MCP_COMMAND = os.getenv("SLB_MCP_COMMAND", "").strip() or None
MCP_ARGS = [arg.strip() for arg in os.getenv("SLB_MCP_ARGS", "").split() if arg.strip()]
MCP_HANDSHAKE_TIMEOUT = float(os.getenv("SLB_MCP_HANDSHAKE_TIMEOUT", "10"))
MCP_TOOL_TIMEOUT = float(os.getenv("SLB_MCP_TOOL_TIMEOUT", "30"))
MCP_SHUTDOWN_TIMEOUT = float(os.getenv("SLB_MCP_SHUTDOWN_TIMEOUT", "5"))
MCP_COMMAND_ARGS = MCP_ARGS
MCP_HANDSHAKE_TIMEOUT_SECONDS = MCP_HANDSHAKE_TIMEOUT
MCP_TOOL_TIMEOUT_SECONDS = MCP_TOOL_TIMEOUT
MCP_SHUTDOWN_TIMEOUT_SECONDS = MCP_SHUTDOWN_TIMEOUT


def describe_mcp_runtime() -> dict[str, object]:
    """Return the resolved MCP command, args, and timeout contract."""
    return {
        "command": MCP_COMMAND,
        "args": list(MCP_COMMAND_ARGS),
        "handshake_timeout_seconds": MCP_HANDSHAKE_TIMEOUT,
        "tool_timeout_seconds": MCP_TOOL_TIMEOUT,
        "shutdown_timeout_seconds": MCP_SHUTDOWN_TIMEOUT,
    }


def describe_service_connection() -> dict[str, object]:
    """Return the canonical service connection defaults."""
    return {
        "default_host": SERVICE_DEFAULT_HOST,
        "default_port": SERVICE_DEFAULT_PORT,
        "default_scheme": SERVICE_DEFAULT_SCHEME,
        "default_base_url": SERVICE_DEFAULT_BASE_URL,
        "remote_scheme": SERVICE_REMOTE_SCHEME,
        "stdin_adapter": SERVICE_STDIN_ADAPTER,
        "service_version": SERVICE_VERSION,
    }
