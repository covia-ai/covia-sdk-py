"""Shared HTTP transport configuration for Covia SDK clients."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

DEFAULT_TIMEOUT = httpx.Timeout(
    connect=10.0,
    read=30.0,
    write=10.0,
    pool=10.0,
)

DEFAULT_API_PATH = "/api/v1/"


@dataclass(frozen=True)
class TransportConfig:
    """Immutable configuration for HTTP transport to a Covia venue."""

    base_url: str
    timeout: httpx.Timeout = field(default_factory=lambda: DEFAULT_TIMEOUT)
    headers: dict[str, str] = field(default_factory=dict)
    follow_redirects: bool = True

    @property
    def api_url(self) -> str:
        """Full URL including the API base path."""
        base = self.base_url.rstrip("/")
        return f"{base}{DEFAULT_API_PATH}"


def resolve_connection(connection: str) -> str:
    """Resolve a connection string (URL or DID) to an HTTP(S) URL.

    Supports:
        - Direct URLs: ``https://venue.covia.ai``
        - DID Web: ``did:web:venue.covia.ai``

    Args:
        connection: URL or DID string.

    Returns:
        Resolved HTTPS URL.

    Raises:
        ValueError: If the connection string format is not recognised.
    """
    connection = connection.strip()
    if connection.startswith(("http://", "https://")):
        return connection
    if connection.startswith("did:web:"):
        host = connection.removeprefix("did:web:")
        return f"https://{host}"
    raise ValueError(f"Unrecognised connection format: {connection!r}")


def make_timeout(timeout: float | None) -> httpx.Timeout:
    """Create an httpx Timeout from an optional seconds value."""
    if timeout is None:
        return DEFAULT_TIMEOUT
    return httpx.Timeout(timeout)
