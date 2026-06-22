"""Async Venue — async interface to a Covia venue."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from covia._async_client import AsyncCoviaHTTPClient
from covia._sse import SSEEvent
from covia._transport import TransportConfig
from covia.agents import AsyncAgentManager
from covia.asset import Asset
from covia.async_api.job import AsyncJob
from covia.exceptions import CoviaError, CoviaTimeoutError
from covia.models import (
    AgentCard,
    AssetList,
    DIDDocument,
    JobData,
    MCPDiscovery,
    OperationInfo,
    VenueStatus,
)
from covia.secrets import AsyncSecretManager
from covia.ucan import AsyncUCANManager
from covia.workspace import AsyncWorkspaceManager

logger = logging.getLogger(__name__)


class AsyncVenue:
    """Async version of :class:`~covia.venue.Venue`.

    Example::

        from covia.async_api import AsyncGrid

        async with AsyncGrid.connect("https://venue.covia.ai") as venue:
            status = await venue.status()
            result = await venue.run("my-operation", {"prompt": "hello"})
    """

    def __init__(self, config: TransportConfig) -> None:
        self._client = AsyncCoviaHTTPClient(config)
        self._config = config
        self._did: str | None = None
        self._did_resolved: bool = False
        self._agents: AsyncAgentManager | None = None
        self._secrets: AsyncSecretManager | None = None
        self._workspace: AsyncWorkspaceManager | None = None
        self._ucan: AsyncUCANManager | None = None

    @property
    def agents(self) -> AsyncAgentManager:
        """Typed accessor for ``v/ops/agent/*`` operations."""
        if self._agents is None:
            self._agents = AsyncAgentManager(self)
        return self._agents

    @property
    def secrets(self) -> AsyncSecretManager:
        """Typed accessor for venue secret storage."""
        if self._secrets is None:
            self._secrets = AsyncSecretManager(self)
        return self._secrets

    @property
    def workspace(self) -> AsyncWorkspaceManager:
        """Typed accessor for ``v/ops/covia/*`` workspace operations."""
        if self._workspace is None:
            self._workspace = AsyncWorkspaceManager(self)
        return self._workspace

    @property
    def ucan(self) -> AsyncUCANManager:
        """Typed accessor for ``v/ops/ucan/*`` operations."""
        if self._ucan is None:
            self._ucan = AsyncUCANManager(self)
        return self._ucan

    async def aclose(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._client.aclose()

    async def __aenter__(self) -> AsyncVenue:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    # ------------------------------------------------------------------
    # Venue info
    # ------------------------------------------------------------------

    async def status(self) -> VenueStatus:
        """Get venue status information."""
        return await self._client.get_status()

    async def wait_until_ready(
        self,
        *,
        timeout: float | None = 60.0,
        poll_interval: float = 1.0,
    ) -> VenueStatus:
        """Block until the venue's API is ready to serve operations.

        Async mirror of
        :meth:`Venue.wait_until_ready <covia.venue.Venue.wait_until_ready>`.
        Polls :meth:`status` (``GET /api/v1/status``) — not the root URL —
        because a venue accepts root-path connections before its invoke layer
        is initialised. Ready when ``status()`` returns and reports no
        ``status`` field or ``"OK"``; connection/HTTP/timeout errors are
        retried until *timeout*.

        Args:
            timeout: Maximum seconds to wait. ``None`` waits indefinitely.
            poll_interval: Seconds between status polls.

        Returns:
            The :class:`~covia.models.VenueStatus` from the first ready
            response.

        Raises:
            CoviaTimeoutError: If the venue is not ready within *timeout*.
        """
        start = time.monotonic()
        last_error: Exception | None = None
        attempt = 0
        while True:
            attempt += 1
            try:
                status = await self.status()
            except CoviaError as exc:
                last_error = exc
            else:
                if status.status is None or status.status.upper() == "OK":
                    logger.debug("Venue %s ready after %d attempt(s)", self._config.base_url, attempt)
                    return status
                last_error = None
            if timeout is not None and (time.monotonic() - start) >= timeout:
                msg = f"Venue {self._config.base_url} not ready within {timeout}s"
                raise CoviaTimeoutError(msg) from last_error
            await asyncio.sleep(poll_interval)

    @property
    def url(self) -> str:
        """The base URL of this venue."""
        return self._config.base_url

    async def get_did(self) -> str | None:
        """The DID of this venue, if available.

        The value is fetched from the venue's DID document on first access
        and cached for subsequent calls.
        """
        if not self._did_resolved:
            logger.debug("Fetching DID document for %s", self._config.base_url)
            doc = await self._client.get_did_document()
            self._did = doc.id
            self._did_resolved = True
            logger.debug("Resolved venue DID: %s", self._did)
        return self._did

    async def did_document(self) -> DIDDocument:
        """Get the full DID document for this venue."""
        return await self._client.get_did_document()

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    async def list_assets(self, *, offset: int = 0, limit: int | None = None) -> AssetList:
        """List assets registered at this venue."""
        return await self._client.list_assets(offset=offset, limit=limit)

    async def get_asset(self, asset_id: str) -> Asset:
        """Get an asset by its ID.

        Raises:
            ValueError: If the metadata hash does not match the requested ID.
        """
        metadata, metadata_raw = await self._client.get_asset_metadata(asset_id)
        if metadata_raw is not None:
            computed = Asset.compute_id(metadata_raw)
            if computed != asset_id:
                raise ValueError(f"Asset ID mismatch: requested {asset_id!r} but metadata hashes to {computed!r}")
        return Asset(metadata=metadata, id=asset_id, venue=self, metadata_raw=metadata_raw)

    async def register(self, asset: Asset | dict[str, Any]) -> Asset:
        """Register a new asset at this venue.

        Args:
            asset: An :class:`Asset` instance or a metadata dictionary.

        Returns:
            A registered :class:`Asset` with the server-assigned ID
            and this venue attached.
        """
        metadata = asset.metadata if isinstance(asset, Asset) else asset
        asset_id = await self._client.register_asset(metadata)
        return await self.get_asset(asset_id)

    async def get_asset_content(self, asset_id: str) -> bytes:
        """Download the binary content of an asset."""
        return await self._client.get_asset_content(asset_id)

    async def put_asset_content(self, asset_id: str, content: bytes) -> str:
        """Upload content for an asset. Returns the content hash."""
        return await self._client.put_asset_content(asset_id, content)

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    async def list_operations(self) -> list[OperationInfo]:
        """List all named operations available on this venue."""
        return await self._client.list_operations()

    async def get_operation(self, name: str) -> OperationInfo:
        """Get details of a named operation.

        Args:
            name: Operation name (e.g. ``"v/ops/schema/infer"``).
        """
        return await self._client.get_operation(name)

    # ------------------------------------------------------------------
    # Invoke / Run
    # ------------------------------------------------------------------

    async def invoke(self, operation: str, input: Any = None, *, ucans: list[str] | None = None) -> AsyncJob:
        """Invoke an operation, returning an AsyncJob for tracking.

        Args:
            operation: Operation identifier — accepts a hex asset ID,
                an operation name (e.g. ``"v/ops/schema/infer"``), or a DID URL.
            input: Input parameters for the operation.
            ucans: Optional UCAN proof tokens authorising
                capability-gated operations (e.g. cross-DID reads).
        """
        job_data = await self._client.invoke(operation, input, ucans=ucans)
        return AsyncJob(data=job_data, venue=self)

    async def run(
        self,
        operation: str,
        input: Any = None,
        *,
        timeout: float | None = None,
        ucans: list[str] | None = None,
    ) -> Any:
        """Invoke an operation and wait for the result.

        Args:
            operation: Operation identifier — accepts a hex asset ID,
                an operation name (e.g. ``"v/ops/schema/infer"``), or a DID URL.
            input: Input parameters for the operation.
            timeout: Maximum seconds to wait for completion.
            ucans: Optional UCAN proof tokens (see :meth:`invoke`).
        """
        job = await self.invoke(operation, input, ucans=ucans)
        await job.wait(timeout=timeout)
        return job.output

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    async def get_job(self, job_id: str) -> AsyncJob:
        """Get a job by its ID."""
        job_data = await self._client.get_job(job_id)
        return AsyncJob(data=job_data, venue=self)

    async def list_jobs(self) -> list[str]:
        """List all job IDs at this venue."""
        return await self._client.list_jobs()

    async def cancel_job(self, job_id: str) -> JobData:
        """Cancel a running job."""
        return await self._client.cancel_job(job_id)

    async def delete_job(self, job_id: str) -> None:
        """Delete a job record."""
        await self._client.delete_job(job_id)

    async def stream_job_events(self, job_id: str) -> AsyncIterator[SSEEvent]:
        """Stream SSE events for a job."""
        return self._client.stream_job_events(job_id)

    # ------------------------------------------------------------------
    # Secrets (raw REST — see ``venue.secrets`` for the typed manager)
    # ------------------------------------------------------------------

    async def list_secrets(self) -> list[str]:
        """List secret names stored at this venue."""
        return await self._client.list_secrets()

    async def put_secret(self, name: str, value: str) -> None:
        """Store (or replace) a secret value."""
        await self._client.put_secret(name, value)

    async def delete_secret(self, name: str) -> None:
        """Delete a stored secret."""
        await self._client.delete_secret(name)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    async def mcp_discovery(self) -> MCPDiscovery:
        """Get MCP discovery information."""
        return await self._client.get_mcp_discovery()

    async def agent_card(self) -> AgentCard:
        """Get the A2A agent card."""
        return await self._client.get_agent_card()

    def __repr__(self) -> str:
        return f"AsyncVenue({self._config.base_url!r})"
