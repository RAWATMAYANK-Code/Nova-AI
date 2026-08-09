"""
security_utils.py
Centralized security utility functions for SSRF defense, input sanitization,
magic byte validation, and guardrails.
"""

import os
import re
import socket
import ipaddress
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv(override=True)

# Allow local network/localhost URLs during local testing (default True for local dev)
ALLOW_LOCAL_SSRF = os.getenv("ALLOW_LOCAL_SSRF", "true").lower() in ("true", "1", "yes")

# Maximum allowed text length for claim verification
MAX_TEXT_LENGTH = 2000

# Cloud metadata and forbidden IP networks
FORBIDDEN_NETWORKS = [
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local / AWS metadata
    ipaddress.ip_network("0.0.0.0/8"),        # Current network
]

PUBLIC_ONLY_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("10.0.0.0/8"),       # Private IPv4
    ipaddress.ip_network("172.16.0.0/12"),    # Private IPv4
    ipaddress.ip_network("192.168.0.0/16"),   # Private IPv4
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
    ipaddress.ip_network("fc00::/7"),         # IPv6 private
]


def is_safe_url(url_string, allow_local=None):
    """
    Validates a URL against Server-Side Request Forgery (SSRF).
    Checks protocol, host resolution, and IP range safety.
    If allow_local is True (default in local dev), localhost and local subnets are permitted for testing.
    """
    if allow_local is None:
        allow_local = ALLOW_LOCAL_SSRF

    if not url_string or not isinstance(url_string, str):
        return False, "Invalid URL string provided."

    parsed = urlparse(url_string.strip())

    # 1. Scheme restriction: only allow http and https
    if parsed.scheme.lower() not in ("http", "https"):
        return False, "Only HTTP and HTTPS protocols are permitted."

    hostname = parsed.hostname
    if not hostname:
        return False, "URL does not contain a valid hostname."

    hostname_lower = hostname.lower()

    # 2. Prevent cloud metadata resolution bypasses
    if hostname_lower in ("169.254.169.254", "metadata.google.internal"):
        return False, "Access to cloud metadata endpoints is blocked."

    # If running locally and allow_local is True, permit localhost/local IPs
    if allow_local and (hostname_lower in ("localhost", "127.0.0.1", "0.0.0.0", "[::1]") or hostname_lower.startswith("192.168.")):
        return True, "Local URL permitted in development mode."

    # 3. Resolve IP address to check subnet safety
    try:
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        return False, f"Could not resolve domain name: {hostname}"
    except Exception as e:
        return False, f"DNS resolution failure: {e}"

    for family, socktype, proto, canonname, sockaddr in addr_info:
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            return False, "Resolved address is not a valid IP address."

        # Always block metadata / link-local networks
        for net in FORBIDDEN_NETWORKS:
            if ip_obj in net:
                return False, f"URL resolves to forbidden subnet ({ip_str})."

        # Block private subnets only if allow_local is False (production mode)
        if not allow_local:
            if ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_reserved:
                return False, f"URL resolves to restricted IP address range ({ip_str})."

            for net in PUBLIC_ONLY_NETWORKS:
                if ip_obj in net:
                    return False, f"URL resolves to restricted subnet ({ip_str})."

    return True, "URL is safe."


def sanitize_input_text(text):
    """
    Sanitizes user input string: strips non-printable control characters,
    normalizes whitespace, and truncates to MAX_TEXT_LENGTH characters.
    """
    if not text or not isinstance(text, str):
        return ""

    # Strip control characters except newline and tab
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    cleaned = cleaned.strip()

    if len(cleaned) > MAX_TEXT_LENGTH:
        cleaned = cleaned[:MAX_TEXT_LENGTH]

    return cleaned


def validate_image_bytes(image_bytes):
    """
    Verifies that raw bytes belong to a valid image format (JPEG, PNG, WEBP, GIF)
    using magic header signatures.
    """
    if not image_bytes or not isinstance(image_bytes, (bytes, bytearray)):
        return False, "Invalid image data."

    if len(image_bytes) < 8:
        return False, "Image file header is too small."

    # Magic Bytes Signatures
    # PNG: \x89PNG\r\n\x1a\n
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return True, "image/png"

    # JPEG: \xff\xd8\xff
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return True, "image/jpeg"

    # WEBP: starts with RIFF and contains WEBP at byte 8
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return True, "image/webp"

    # GIF: GIF87a or GIF89a
    if image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
        return True, "image/gif"

    return False, "Uploaded file format is not a recognized image type (PNG, JPEG, WEBP)."
