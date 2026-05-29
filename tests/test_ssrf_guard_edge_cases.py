from __future__ import annotations

import socket
from unittest.mock import AsyncMock, MagicMock

import pytest

import utils.ssrf_guard as ssrf_guard


@pytest.mark.asyncio
async def test_ssrf_backend_connect_and_transport_construction(monkeypatch):
    guard = ssrf_guard.SSRFGuard()
    guard.validate_host = AsyncMock(return_value=None)
    guard.pinned_cache["example.com"] = "93.184.216.34"

    backend = ssrf_guard.SSRFNetworkBackend(guard)
    connect = AsyncMock(return_value=("reader", "writer"))
    monkeypatch.setattr(backend.backend, "connect_tcp", connect)

    stream = await backend.connect_tcp("example.com", 443)
    assert stream == ("reader", "writer")
    connect.assert_awaited_once()

    connect.reset_mock()
    stream = await backend.connect_tcp(
        "example.com",
        443,
        socket_options=[("TCP_NODELAY", 1)],
    )
    assert stream == ("reader", "writer")
    connect.assert_awaited_once()
    assert connect.await_args.kwargs["socket_options"] == [("TCP_NODELAY", 1)]

    guard_empty = ssrf_guard.SSRFGuard()
    guard_empty.validate_host = AsyncMock(return_value=None)
    with pytest.raises(socket.gaierror):
        await ssrf_guard.SSRFNetworkBackend(guard_empty).connect_tcp("example.com", 443)

    transport = ssrf_guard.SSRFHTTPTransport(guard)
    assert transport._pool is not None


@pytest.mark.asyncio
async def test_ssrf_validate_host_uses_cached_pin(monkeypatch):
    guard = ssrf_guard.SSRFGuard()
    guard.pinned_cache["example.com"] = "93.184.216.34"

    resolve_mock = AsyncMock()
    monkeypatch.setattr(ssrf_guard, "resolve_ips", resolve_mock)

    await guard.validate_host("example.com")

    resolve_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_ssrf_validate_host_rejects_malformed_and_invalid_ips(monkeypatch):
    guard = ssrf_guard.SSRFGuard()

    with pytest.raises(ssrf_guard.SSRFViolationError, match="Malformed host"):
        await guard.validate_host("")

    monkeypatch.setattr(ssrf_guard, "resolve_ips", AsyncMock(return_value=["not-an-ip"]))
    with pytest.raises(ssrf_guard.SSRFViolationError, match="invalid"):
        await guard.validate_host("example.org")
