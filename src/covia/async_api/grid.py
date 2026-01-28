"""Async entry point for connecting to the Covia grid."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from covia._transport import TransportConfig, make_timeout, resolve_connection
from covia.async_api.venue import AsyncVenue

if TYPE_CHECKING:
    from covia.auth import Auth

logger = logging.getLogger(__name__)


class AsyncGrid:
    """Async version of :class:`~covia.grid.Grid`.

    Example::

        from covia.async_api import AsyncGrid

        async with AsyncGrid.connect("https://venue.covia.ai") as venue:
            result = await venue.run("my-operation", {"prompt": "hello"})

        # With authentication
        from covia.auth import BearerAuth
        async with AsyncGrid.connect("https://venue.covia.ai", auth=BearerAuth("token")) as venue:
            ...
    """

    @staticmethod
    def connect(
        connection: str,
        *,
        timeout: float | None = None,
        headers: dict[str, str] | None = None,
        auth: Auth | None = None,
    ) -> AsyncVenue:
        """Connect to a Covia venue by URL or DID.

        Args:
            connection: Venue URL (``https://...``) or DID (``did:web:...``).
            timeout: Request timeout in seconds.
            headers: Extra HTTP headers sent with every request.
            auth: Authentication provider. See :mod:`covia.auth` for
                built-in options (``BearerAuth``, ``BasicAuth``).
                Defaults to no authentication.

        Returns:
            A connected :class:`~covia.async_api.venue.AsyncVenue` instance.

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
        return AsyncVenue(config)
