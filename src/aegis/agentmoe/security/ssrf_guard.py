"""AgentMoe — SSRFGuard (Phase 2 security).

Prevents Server-Side Request Forgery (SSRF) attacks in Browser and HTTP tools.

Pattern adapted from Hermes Agent tools/url_safety.py (MIT license).
Adaptation: stripped Hermes-specific config/constant imports, integrated
with AgentMoeConfig, added IPv6 comprehensive coverage.

Security properties guaranteed:
  1. RFC 1918 private ranges (10.x, 172.16-31.x, 192.168.x) — BLOCKED
  2. RFC 5737 documentation ranges (192.0.2.x, 198.51.100.x, 203.0.113.x) — BLOCKED
  3. RFC 3927 link-local (169.254.x.x) — BLOCKED (incl. cloud metadata endpoint)
  4. RFC 4193 IPv6 ULA (fc00::/7) — BLOCKED
  5. RFC 4291 IPv6 loopback/link-local — BLOCKED
  6. Cloud metadata hostnames (169.254.169.254, metadata.google.internal, etc.) — ALWAYS BLOCKED
  7. Localhost (127.x, ::1, localhost) — BLOCKED
  8. DNS rebinding mitigation — resolves hostname and validates IP

Note on DNS rebinding (TOCTOU):
  An attacker-controlled DNS server with TTL=0 can return a public IP for the
  validation check, then a private IP for the actual TCP connect. Callers that
  own the HTTP client should re-validate immediately before TCP connect.
  SSRFGuard.validate_url() is a best-effort gate, not a complete solution.

Import safety: stdlib only (no AEGIS layer imports).
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Optional, Sequence
from urllib.parse import urlparse


__all__ = ["SSRFGuardError", "SSRFGuard"]

logger = logging.getLogger(__name__)


# SAFETY — always blocked regardless of config; these are never legitimate targets
_ALWAYS_BLOCKED_HOSTS: frozenset[str] = frozenset({
    "169.254.169.254",           # AWS/GCP/Azure IMDS
    "metadata.google.internal",  # GCP metadata
    "metadata.internal",         # GCP metadata alias
    "169.254.170.2",             # ECS container metadata
    "fd00:ec2::254",             # IPv6 AWS IMDS
})

_ALWAYS_BLOCKED_SCHEMES: frozenset[str] = frozenset({
    "file",    # local file access
    "ftp",     # FTP (legacy, often internal)
    "gopher",  # SSRF classic
    "dict",    # SSRF classic
    "ldap",    # directory access
    "ldaps",
    "sftp",
    "ssh",
})

_PRIVATE_RANGES: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    # IPv4
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),        # loopback
    ipaddress.ip_network("169.254.0.0/16"),     # link-local / cloud metadata
    ipaddress.ip_network("100.64.0.0/10"),      # shared address space (RFC 6598)
    ipaddress.ip_network("192.0.2.0/24"),       # TEST-NET-1 (RFC 5737)
    ipaddress.ip_network("198.51.100.0/24"),    # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),     # TEST-NET-3
    ipaddress.ip_network("0.0.0.0/8"),          # "this" network
    # IPv6
    ipaddress.ip_network("::1/128"),            # loopback
    ipaddress.ip_network("fc00::/7"),           # ULA
    ipaddress.ip_network("fe80::/10"),          # link-local
    ipaddress.ip_network("::/128"),             # unspecified
)


class SSRFGuardError(Exception):
    """Raised when a URL fails SSRF validation."""
    def __init__(self, message: str, url: Optional[str] = None) -> None:
        super().__init__(message)
        self.url = url


class SSRFGuard:
    """Validates URLs against SSRF attack patterns.

    Usage::

        guard = SSRFGuard()
        guard.validate_url("https://example.com/page")          # OK
        guard.validate_url("https://192.168.1.1/admin")         # raises SSRFGuardError
        guard.validate_url("file:///etc/passwd")                # raises SSRFGuardError
        guard.validate_url("https://169.254.169.254/latest")    # raises SSRFGuardError
    """

    def __init__(
        self,
        *,
        allowed_domains: Sequence[str] = (),
        blocked_domains: Sequence[str] = (),
        resolve_dns: bool = True,
    ) -> None:
        """
        Args:
            allowed_domains: If non-empty, ONLY these domains are allowed.
            blocked_domains: These domains are always blocked.
            resolve_dns:     If True, resolves hostname to IP and validates the IP.
                             Disable only in test environments.
        """
        self._allowed  = frozenset(d.lower() for d in allowed_domains)
        self._blocked  = frozenset(d.lower() for d in blocked_domains) | frozenset(
            h.lower() for h in _ALWAYS_BLOCKED_HOSTS
        )
        self._resolve  = resolve_dns

    def validate_url(self, url: str) -> str:
        """Validate a URL against SSRF rules.

        Returns:
            The URL if safe.

        Raises:
            SSRFGuardError: If the URL is unsafe.
        """
        if not url:
            raise SSRFGuardError("Empty URL", url=url)

        parsed = urlparse(url)
        scheme = (parsed.scheme or "").lower()
        host   = (parsed.hostname or "").lower()

        # 1. Scheme check
        if scheme in _ALWAYS_BLOCKED_SCHEMES:
            raise SSRFGuardError(f"URL scheme {scheme!r} is blocked", url=url)

        if scheme not in ("http", "https", "ws", "wss"):
            raise SSRFGuardError(f"URL scheme {scheme!r} is not permitted", url=url)

        if not host:
            raise SSRFGuardError("URL has no hostname", url=url)

        # 2. Always-blocked hostnames
        if host in self._blocked:
            raise SSRFGuardError(
                f"Host {host!r} is a blocked cloud/metadata endpoint",
                url=url,
            )

        # 3. User-defined blocked domains
        for blocked in self._blocked:
            if host == blocked or host.endswith("." + blocked):
                raise SSRFGuardError(f"Host {host!r} is in blocked domains", url=url)

        # 4. Allowlist check (if configured)
        if self._allowed:
            allowed = any(host == a or host.endswith("." + a) for a in self._allowed)
            if not allowed:
                raise SSRFGuardError(
                    f"Host {host!r} is not in allowed domains", url=url
                )

        # 5. IP literal check
        try:
            ip = ipaddress.ip_address(host)
            self._check_ip(ip, host, url)
        except ValueError:
            pass  # not an IP literal; proceed to DNS

        # 6. DNS resolution + IP validation
        if self._resolve:
            self._resolve_and_check(host, url)

        return url

    def is_safe(self, url: str) -> bool:
        """Return True if URL passes validation."""
        try:
            self.validate_url(url)
            return True
        except SSRFGuardError:
            return False

    # -- internals ---------------------------------------------------------

    def _check_ip(
        self,
        ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
        host: str,
        url: str,
    ) -> None:
        for network in _PRIVATE_RANGES:
            if ip in network:
                raise SSRFGuardError(
                    f"IP address {ip} ({host!r}) resolves to a private/restricted range "
                    f"({network}). SSRF protection blocked this request.",
                    url=url,
                )

    def _resolve_and_check(self, host: str, url: str) -> None:
        try:
            results = socket.getaddrinfo(host, None)
        except socket.gaierror as exc:
            raise SSRFGuardError(
                f"DNS resolution failed for host {host!r}: {exc}",
                url=url,
            ) from exc

        for _family, _type, _proto, _canonname, sockaddr in results:
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
                self._check_ip(ip, host, url)
            except SSRFGuardError:
                raise
            except ValueError:
                logger.warning("SSRFGuard: could not parse resolved IP %r", ip_str)
