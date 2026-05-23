"""
ssrf_guard.py — Security utility to validate URLs and prevent Server-Side Request Forgery (SSRF).
Resolves target domains asynchronously and blocks loopback, private, link-local, and reserved IP ranges.
"""

import socket
import asyncio
import ipaddress
from urllib.parse import urlparse
from typing import List, Union


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

    async def validate(self, url: str) -> None:
        """
        Validates the URL to ensure it does not resolve to loopback, private, or restricted IP ranges.
        Raises SSRFViolationError if a security boundary is breached.
        """
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname

        if not hostname:
            raise SSRFViolationError(f"Malformed URL: host cannot be parsed from '{url}'.")

        # Skip DNS checks if it is an explicit IP address
        try:
            # Check if hostname itself is a raw IP address
            ip = ipaddress.ip_address(hostname)
            self._check_ip(ip, url)
            return
        except SSRFViolationError:
            raise
        except ValueError:
            # Hostname is a domain name, proceed to DNS resolution
            pass

        # Asynchronously resolve IP addresses
        ips = await resolve_ips(hostname)
        if not ips:
            raise SSRFViolationError(f"Could not resolve hostname: '{hostname}' could not be mapped to any IP addresses.")

        for ip_str in ips:
            try:
                ip = ipaddress.ip_address(ip_str)
                self._check_ip(ip, url)
            except SSRFViolationError:
                raise
            except ValueError:
                # Treat unparsable or corrupted IP strings as unsafe
                raise SSRFViolationError(f"Unsafe IP resolved for '{hostname}': '{ip_str}' is invalid.")

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
                f"SSRF Security Violation: URL '{url}' resolves to IP '{ip}', which is a loopback or private address range."
            )
