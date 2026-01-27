"""Async entry point for connecting to the Covia grid."""

from __future__ import annotations

from covia._transport import TransportConfig, make_timeout, resolve_connection
from covia.async_api.venue import AsyncVenue


class AsyncGrid:
    """Async version of :class:`~covia.grid.Grid`.

    Example::

        from covia.async_api import AsyncGrid

        async with AsyncGrid.connect("https://venue.covia.ai") as venue:
            result = await venue.run("my-operation", {"prompt": "hello"})
    """

    @staticmethod
    def connect(
        connection: str,
        *,
        timeout: float | None = None,
        headers: dict[str, str] | None = None,
    ) -> AsyncVenue:
        """Connect to a Covia venue by URL or DID.

        Args:
            connection: Venue URL (``https://...``) or DID (``did:web:...``).
            timeout: Request timeout in seconds.
            headers: Extra HTTP headers sent with every request.

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
        )
        return AsyncVenue(config)
