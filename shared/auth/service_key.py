"""Service-to-service authentication.

Most calls between services forward the signed-in user's bearer token. Some
cannot: an organiser's action that tells other people, or a scheduled job
with no user at all. Those calls prove they come from one of our own
services with a shared secret in the `X-Service-Key` header instead.

The secret is the INTERNAL_SERVICE_KEY environment variable. It is never
sent to browsers, and the gateway must not forward this header from outside.
"""

import secrets

from shared.exceptions.http import forbidden

SERVICE_KEY_HEADER = "X-Service-Key"


def service_key_headers(key: str) -> dict[str, str]:
    """Headers a calling service adds. Empty when no key is configured."""
    return {SERVICE_KEY_HEADER: key} if key else {}


def require_service_key(provided: str | None, expected: str) -> None:
    """403 unless the caller sent the configured key.

    A service with no key configured refuses every caller, so a missing
    environment variable can never leave the route open.
    """
    if not expected or not provided or not secrets.compare_digest(provided.encode(), expected.encode()):
        raise forbidden("A valid service key is required")
