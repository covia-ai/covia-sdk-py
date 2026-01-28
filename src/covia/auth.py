"""Authentication providers for the Covia SDK.

Provides a generic :class:`Auth` interface and built-in implementations
for common authentication strategies.

Built-in providers:

- :class:`NoAuth` — no authentication (default when ``auth`` is omitted)
- :class:`BearerAuth` — ``Authorization: Bearer <token>``
- :class:`BasicAuth` — HTTP Basic authentication (``username:password``)

The interface is designed to accommodate future providers without
breaking changes:

- **OAuth 2.0** — token acquisition, refresh, and injection
- **Ed25519 signing** — proof of key possession via request signing
"""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod


class Auth(ABC):
    """Base class for Covia authentication providers.

    Subclass this to implement custom authentication strategies.
    :meth:`apply` is called before every HTTP request to inject
    credentials into the outgoing request headers.

    Example — custom API-key auth::

        class ApiKeyAuth(Auth):
            def __init__(self, key: str) -> None:
                self._key = key

            def apply(self, headers: dict[str, str]) -> None:
                headers["X-Api-Key"] = self._key
    """

    @abstractmethod
    def apply(self, headers: dict[str, str]) -> None:
        """Apply authentication credentials to request headers.

        Implementations should mutate *headers* in place, adding any
        fields required by the venue's authentication scheme.

        Args:
            headers: Mutable dict of HTTP headers for the outgoing request.
        """


class NoAuth(Auth):
    """No-op authentication provider.

    Explicitly signals that no credentials should be sent.
    Equivalent to omitting the ``auth`` parameter entirely.
    """

    def apply(self, headers: dict[str, str]) -> None:
        pass

    def __repr__(self) -> str:
        return "NoAuth()"


class BearerAuth(Auth):
    """Bearer token authentication.

    Adds ``Authorization: Bearer <token>`` to every request.

    Example::

        from covia import Grid
        from covia.auth import BearerAuth

        venue = Grid.connect(
            "https://venue.covia.ai",
            auth=BearerAuth("my-secret-token"),
        )
    """

    def __init__(self, token: str) -> None:
        self._token = token

    def apply(self, headers: dict[str, str]) -> None:
        headers["Authorization"] = f"Bearer {self._token}"

    def __repr__(self) -> str:
        return "BearerAuth(token=<redacted>)"


class BasicAuth(Auth):
    """HTTP Basic authentication.

    Adds ``Authorization: Basic <base64(username:password)>`` to every request.

    Example::

        from covia.auth import BasicAuth

        venue = Grid.connect(
            "https://venue.covia.ai",
            auth=BasicAuth("admin", "s3cret"),
        )
    """

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    def apply(self, headers: dict[str, str]) -> None:
        credentials = base64.b64encode(
            f"{self._username}:{self._password}".encode()
        ).decode("ascii")
        headers["Authorization"] = f"Basic {credentials}"

    def __repr__(self) -> str:
        return f"BasicAuth(username={self._username!r}, password=<redacted>)"
