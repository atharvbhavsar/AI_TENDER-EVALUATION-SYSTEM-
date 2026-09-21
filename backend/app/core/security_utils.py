"""Security utilities for input validation, SSRF defense, and URL safety."""

import ipaddress
import socket
import urllib.parse
from fastapi import HTTPException, status

# Prohibited hostnames and IP schemes
PROHIBITED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "metadata.google.internal",
    "169.254.169.254",  # AWS/GCP/Azure link-local metadata endpoint
}

ALLOWED_URL_SCHEMES = {"http", "https"}


def is_private_or_loopback_ip(ip_str: str) -> bool:
    """Check if an IP address is private, loopback, link-local, reserved, or multicast."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )
    except ValueError:
        return True


def validate_url_safety(url: str) -> str:
    """
    Validate that a URL is safe to fetch and not attempting Server-Side Request Forgery (SSRF).
    - Enforces http/https schemes only.
    - Disallows embedded credentials (user:pass@host).
    - Blocks localhost, loopback, private IP ranges (RFC 1918), link-local cloud metadata (169.254.169.254).
    - Resolves DNS and checks target IP addresses against private ranges.
    """
    if not url or not isinstance(url, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid URL format.",
        )

    url_clean = url.strip()
    try:
        parsed = urllib.parse.urlparse(url_clean)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed URL.",
        ) from exc

    # 1. Scheme check
    if not parsed.scheme or parsed.scheme.lower() not in ALLOWED_URL_SCHEMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Prohibited URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are allowed.",
        )

    # 2. Hostname presence and credential check
    if not parsed.hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL is missing a valid hostname.",
        )

    if parsed.username or parsed.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Embedded credentials in URL are prohibited for security.",
        )

    hostname_lower = parsed.hostname.lower()

    # 3. Known prohibited hostnames
    if hostname_lower in PROHIBITED_HOSTNAMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSRF Violation: Access to loopback, localhost, and metadata endpoints is strictly blocked.",
        )

    # 4. Direct IP address check
    try:
        ip = ipaddress.ip_address(hostname_lower)
        if is_private_or_loopback_ip(str(ip)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SSRF Violation: Access to private or loopback IP ranges is prohibited.",
            )
        return url_clean
    except ValueError:
        pass  # Hostname is a domain name, proceed to DNS resolution check

    # 5. DNS resolution check (resolve all A/AAAA records and ensure none are private)
    try:
        addr_info = socket.getaddrinfo(hostname_lower, parsed.port or (443 if parsed.scheme == "https" else 80))
        for res in addr_info:
            sockaddr = res[4]
            ip_resolved = sockaddr[0]
            if is_private_or_loopback_ip(ip_resolved):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="SSRF Violation: Domain resolves to a private or restricted network address.",
                )
    except socket.gaierror:
        # If DNS cannot be resolved, reject safely
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL hostname could not be resolved.",
        )

    return url_clean
