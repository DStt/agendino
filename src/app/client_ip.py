"""Client IP resolution that is safe behind a reverse proxy.

Bans are permanent by design, so it is critical to ban the real client and
not the proxy. Forwarding headers are only trusted when the operator opts in
via TRUST_PROXY_HEADERS; otherwise any client could spoof its address.
"""

import os

from starlette.requests import Request


def trust_proxy_headers() -> bool:
    return os.getenv("TRUST_PROXY_HEADERS", "false").strip().lower() in ("true", "1", "yes")


def get_client_ip(request: Request) -> str:
    """Return the client IP, honouring proxy headers only when configured."""
    if trust_proxy_headers():
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # X-Forwarded-For is a comma-separated list; the first entry is the client.
            first = forwarded.split(",", 1)[0].strip()
            if first:
                return first
        real_ip = request.headers.get("x-real-ip")
        if real_ip and real_ip.strip():
            return real_ip.strip()

    return request.client.host if request.client else "unknown"
