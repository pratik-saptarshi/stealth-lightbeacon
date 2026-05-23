"""
test_ssrf_protection.py — Unit tests for the SSRF Guard utility.
"""

import pytest
from unittest.mock import patch, AsyncMock
from utils.ssrf_guard import SSRFGuard, SSRFViolationError

@pytest.mark.asyncio
async def test_ssrf_guard_public_allowed():
    """
    Verifies that a standard public domain (e.g., example.com resolving to a public IP) passes SSRF validation.
    """
    guard = SSRFGuard()
    
    # Mock DNS resolution to return a public IP
    with patch("utils.ssrf_guard.resolve_ips", return_value=["93.184.216.34"]):
        # Should not raise any exceptions
        await guard.validate("https://example.com/some-page")

@pytest.mark.asyncio
async def test_ssrf_guard_private_blocked():
    """
    Verifies that private IP addresses, loopbacks, and local link addresses are blocked.
    """
    guard = SSRFGuard()
    
    # 1. Loopback
    with patch("utils.ssrf_guard.resolve_ips", return_value=["127.0.0.1"]):
        with pytest.raises(SSRFViolationError) as exc_info:
            await guard.validate("http://localhost/admin")
        assert "is a loopback or private address" in str(exc_info.value)
        
    # 2. Private Class C
    with patch("utils.ssrf_guard.resolve_ips", return_value=["192.168.1.50"]):
        with pytest.raises(SSRFViolationError):
            await guard.validate("http://192.168.1.50/status")

    # 3. Private Class A
    with patch("utils.ssrf_guard.resolve_ips", return_value=["10.0.0.1"]):
        with pytest.raises(SSRFViolationError):
            await guard.validate("http://internal-host.local/secrets")

@pytest.mark.asyncio
async def test_ssrf_guard_allow_private_flag():
    """
    Verifies that private IPs are permitted if allow_private=True is explicitly set.
    """
    guard = SSRFGuard(allow_private=True)
    
    # Mock resolve to a loopback IP
    with patch("utils.ssrf_guard.resolve_ips", return_value=["127.0.0.1"]):
        # Should pass successfully when allowed
        await guard.validate("http://127.0.0.1/local-test")

@pytest.mark.asyncio
async def test_ssrf_guard_unresolvable_fails():
    """
    Verifies that unresolvable hosts fail validation to prevent bypassing checks.
    """
    guard = SSRFGuard()
    
    with patch("utils.ssrf_guard.resolve_ips", return_value=[]):
        with pytest.raises(SSRFViolationError) as exc_info:
            await guard.validate("http://unresolvable.invalid-domain-name")
        assert "Could not resolve hostname" in str(exc_info.value)
