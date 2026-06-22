"""AsyncAsset — async interface to a Covia data asset.

Async mirror of :class:`covia.asset.Asset`. The data accessors
(:attr:`name`, :attr:`metadata`, :attr:`is_operation`, …) are shared sync
properties via :class:`covia.asset._AssetBase`; the methods that reach the
venue (:meth:`get_content`, :meth:`put_content`, :meth:`invoke`, :meth:`run`,
:meth:`did_url`) are async.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from covia.asset import _AssetBase
from covia.did import Namespace, did_url

if TYPE_CHECKING:
    from covia.async_api.job import AsyncJob
    from covia.async_api.venue import AsyncVenue  # noqa: F401 — resolves the _AssetBase["AsyncVenue"] base


class AsyncAsset(_AssetBase["AsyncVenue"]):
    """Async version of :class:`~covia.asset.Asset`.

    Obtain instances via :meth:`AsyncVenue.get_asset` / :meth:`AsyncVenue.register`.
    Data accessors are plain sync properties; methods that reach the venue are
    async.

    Example::

        asset = await venue.get_asset("abc123...")
        print(asset.name)                       # sync (pure data)
        if asset.is_operation:
            result = await asset.run({"x": 1})  # async I/O
        data = await asset.get_content()
    """

    async def did_url(self) -> str | None:
        """DID URL for this asset, or ``None`` if no venue is attached or no ID assigned.

        This is an ``async`` method (the sync :attr:`Asset.did_url` is a
        property) because resolving the venue DID may require a network
        round-trip via :meth:`AsyncVenue.get_did`.
        """
        if self._id is None or self._venue is None:
            return None
        venue_did = await self._venue.get_did()
        if venue_did is None:
            return None
        return did_url(venue_did, Namespace.ASSET, self._id)

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------

    async def get_content(self) -> bytes:
        """Download the binary content of this asset.

        Raises:
            ValueError: If no venue is attached or no ID assigned.
        """
        venue, asset_id = self._require_registered("get content")
        return await venue.get_asset_content(asset_id)

    async def put_content(self, content: bytes) -> str:
        """Upload content for this asset.

        Returns:
            Content hash string.

        Raises:
            ValueError: If no venue is attached or no ID assigned.
        """
        venue, asset_id = self._require_registered("put content")
        return await venue.put_asset_content(asset_id, content)

    # ------------------------------------------------------------------
    # Invocation
    # ------------------------------------------------------------------

    async def invoke(self, input: Any = None) -> AsyncJob:
        """Invoke this asset as an operation, returning an :class:`~covia.async_api.job.AsyncJob`.

        Raises:
            ValueError: If no venue is attached or no ID assigned.
        """
        venue, asset_id = self._require_registered("invoke")
        return await venue.invoke(asset_id, input)

    async def run(self, input: Any = None, *, timeout: float | None = None) -> Any:
        """Invoke this asset and wait for the result.

        Args:
            input: Input parameters for the operation.
            timeout: Maximum seconds to wait for completion.

        Returns:
            The operation output.

        Raises:
            ValueError: If no venue is attached or no ID assigned.
            JobFailedError: If the job finishes with a non-COMPLETE status.
            CoviaTimeoutError: If the timeout is exceeded.
        """
        venue, asset_id = self._require_registered("run")
        return await venue.run(asset_id, input, timeout=timeout)
