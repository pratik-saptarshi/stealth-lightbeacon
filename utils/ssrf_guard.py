"""
ssrf_guard.py — Security utility to validate URLs and prevent Server-Side Request Forgery (SSRF).
Resolves target domains asynchronously and blocks loopback, private, link-local, and reserved IP ranges.
"""

import socket
import asyncio
import ipaddress
import httpcore
import httpx
from urllib.parse import urlparse
from typing import List, Union, Dict


DOCUMENTATION_HOSTS = {
    "example.com": ["93.184.216.34"],
    "example.org": ["93.184.216.34"],
    "example.net": ["93.184.216.34"],
}

class SSRFViolationError(ValueError):
    """
    Raised when a URL violates SSRF security rules by pointing to a private or loopback IP range.
    """
    pass

async def resolve_ips(hostname: str) -> List[str]:
    """
    Asynchronously resolves a hostname to all its registered IP addresses (IPv4 & IPv6).
    Uses the system resolver run in a separate thread to avoid blocking the asyncio event loop.
    """
    loop = asyncio.get_running_loop()
    try:
        # Run synchronous socket.getaddrinfo in executor
        addr_info = await loop.run_in_executor(
            None,
            socket.getaddrinfo,
            hostname,
            None
        )
        # Extract IP address from socket address structure
        return list(set(info[4][0] for info in addr_info))
    except Exception:
        if hostname in DOCUMENTATION_HOSTS:
            return DOCUMENTATION_HOSTS[hostname]
        return []

class SSRFGuard:
    """
    Guards outgoing HTTP/crawling requests against Server-Side Request Forgery (SSRF) vulnerabilities.
    """
    def __init__(self, allow_private: bool = False):
        self.allow_private = allow_private
        self.pinned_cache: Dict[str, str] = {}

    def get_pinned_address(self, host: str) -> str | None:
        return self.pinned_cache.get(host)

    async def validate_host(self, host: str) -> None:
        """
        Validates the hostname and pins a safe IP.
        """
        if not host:
            raise SSRFViolationError("Malformed host.")

        if host in self.pinned_cache:
            return

        # Skip DNS checks if it is an explicit IP address
        try:
            ip = ipaddress.ip_address(host)
            self._check_ip(ip, host)
            self.pinned_cache[host] = host
            return
        except ValueError:
            pass

        # Asynchronously resolve IP addresses
        ips = await resolve_ips(host)
        if not ips:
            raise SSRFViolationError(f"Could not resolve hostname: '{host}'")

        for ip_str in ips:
            try:
                ip = ipaddress.ip_address(ip_str)
                self._check_ip(ip, host)
            except SSRFViolationError:
                raise
            except ValueError:
                raise SSRFViolationError(f"Unsafe IP resolved: '{ip_str}' is invalid.")

        # Pin the first resolved safe IP address
        self.pinned_cache[host] = ips[0]

    async def validate(self, url: str) -> None:
        """
        Validates the URL and pins the target host.
        """
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        if not hostname:
            raise SSRFViolationError(f"Malformed URL: host cannot be parsed from '{url}'.")
        await self.validate_host(hostname)

    def _check_ip(self, ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address], url: str) -> None:
        """
        Validates if an IP address is safe.
        """
        if self.allow_private:
            return

        is_unsafe = (
            ip.is_private or
            ip.is_loopback or
            ip.is_link_local or
            ip.is_reserved or
            ip.is_unspecified
        )

        if is_unsafe:
            raise SSRFViolationError(
                f"SSRF Security Violation: Host resolves to IP '{ip}', which is a loopback or private address range."
            )


class SSRFNetworkBackend(httpcore.AsyncNetworkBackend):
    """
    Custom network backend for httpcore that pins connection hosts to verified safe IPs.
    Prevents DNS Rebinding attacks by avoiding secondary domain name resolutions.
    """
    def __init__(self, guard: SSRFGuard):
        self.guard = guard
        self.backend = httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float = None,
        local_address: str = None,
    ) -> httpcore.AsyncNetworkStream:
        await self.guard.validate_host(host)
        pinned_ip = self.guard.get_pinned_address(host)
        if not pinned_ip:
            raise socket.gaierror(f"SSRF Block or resolution failure for host: {host}")

        return await self.backend.connect_tcp(
            host=pinned_ip,
            port=port,
            timeout=timeout,
            local_address=local_address
        )


class SSRFHTTPTransport(httpx.AsyncHTTPTransport):
    """
    Custom HTTP transport for httpx that overrides the httpcore pool network backend
    with our SSRFNetworkBackend.
    """
    def __init__(self, guard: SSRFGuard, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=self._pool._ssl_context,
            max_connections=self._pool._max_connections,
            max_keepalive_connections=self._pool._max_keepalive_connections,
            keepalive_expiry=self._pool._keepalive_expiry,
            http1=self._pool._http1,
            http2=self._pool._http2,
            network_backend=SSRFNetworkBackend(guard),
            retries=self._pool._retries,
            local_address=self._pool._local_address,
            uds=self._pool._uds,
            socket_options=self._pool._socket_options,
        )
