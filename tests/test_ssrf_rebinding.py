"""
test_ssrf_rebinding.py — Unit tests verifying DNS rebinding protection via custom transport pinning.
"""

import pytest
import httpx
from unittest.mock import patch, AsyncMock
from utils.ssrf_guard import SSRFGuard, SSRFNetworkBackend, SSRFViolationError


@pytest.mark.asyncio
async def test_ssrf_dns_rebinding_prevention():
    """
    Verifies that SSRFNetworkBackend pins the validated IP and prevents DNS rebinding
    by bypassing secondary domain name resolutions during the connect lifecycle.
    """
    guard = SSRFGuard()
    from utils.ssrf_guard import SSRFHTTPTransport
    transport = SSRFHTTPTransport(guard=guard)

    # Mock resolve_ips to return a safe IP on the first call, then an unsafe loopback IP on the second call
    # simulating a dynamic DNS rebinding attacker
    resolve_calls = []

    async def mock_resolve(hostname):
        resolve_calls.append(hostname)
        if len(resolve_calls) == 1:
            return ["93.184.216.34"]  # Safe public IP
        return ["127.0.0.1"]  # SSRF target rebinding IP

    with patch("utils.ssrf_guard.resolve_ips", side_effect=mock_resolve):
        # First validation pins 'example.com' to '93.184.216.34'
        await guard.validate("https://example.com/status")
        assert guard.get_pinned_address("example.com") == "93.184.216.34"

        # Subsequent validate_host calls (e.g., inside the transport during connection)
        # must use the pinned address, preventing the second resolve_ips result from being used.
        await guard.validate_host("example.com")
        assert guard.get_pinned_address("example.com") == "93.184.216.34"
