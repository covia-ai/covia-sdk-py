"""Entry point for connecting to the Covia grid.

Mirrors ``covia.grid.Grid`` from the Java SDK.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from covia._transport import TransportConfig, make_timeout, resolve_connection
from covia.venue import Venue

if TYPE_CHECKING:
    from covia.auth import Auth

logger = logging.getLogger(__name__)


class Grid:
    """Static entry point for connecting to a Covia venue.

    Example::

        from covia import Grid

        venue = Grid.connect("https://venue.covia.ai")
        result = venue.run("my-operation", {"prompt": "hello"})

        # Or using a DID
        venue = Grid.connect("did:web:venue.covia.ai")

        # With authentication
        from covia.auth import BearerAuth
        venue = Grid.connect("https://venue.covia.ai", auth=BearerAuth("token"))
    """

    @staticmethod
    def connect(
        connection: str,
        *,
        timeout: float | None = None,
        headers: dict[str, str] | None = None,
        auth: Auth | None = None,
    ) -> Venue:
        """Connect to a Covia venue by URL or DID.

        Args:
            connection: Venue URL (``https://...``) or DID (``did:web:...``).
            timeout: Request timeout in seconds. Applies to connect, read,
                and write. Uses sensible defaults if not specified.
            headers: Extra HTTP headers sent with every request.
            auth: Authentication provider. See :mod:`covia.auth` for
                built-in options (``BearerAuth``, ``BasicAuth``).
                Defaults to no authentication.

        Returns:
            A connected :class:`~covia.venue.Venue` instance.

        Raises:
            ValueError: If *connection* is not a recognised format.
        """
        url = resolve_connection(connection)
        config = TransportConfig(
            base_url=url,
            timeout=make_timeout(timeout),
            headers=headers or {},
            auth=auth,
        )
        logger.debug("Connecting to venue: %s", url)
        return Venue(config)
