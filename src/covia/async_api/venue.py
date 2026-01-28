"""Async Venue — async interface to a Covia venue."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from covia._async_client import AsyncCoviaHTTPClient
from covia._sse import SSEEvent
from covia._transport import TransportConfig
from covia.asset import Asset
from covia.async_api.job import AsyncJob
from covia.models import (
    AgentCard,
    AssetList,
    DIDDocument,
    JobData,
    MCPDiscovery,
    OperationInfo,
    VenueStatus,
)


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
            doc = await self._client.get_did_document()
            self._did = doc.id
            self._did_resolved = True
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
        """Get an asset by its ID."""
        metadata, metadata_raw = await self._client.get_asset_metadata(asset_id)
        return Asset(id=asset_id, metadata=metadata, metadata_raw=metadata_raw)

    async def register_asset(self, metadata: dict[str, Any]) -> str:
        """Register a new asset. Returns the asset ID."""
        return await self._client.register_asset(metadata)

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
            name: Operation name (e.g. ``"test:echo"``).
        """
        return await self._client.get_operation(name)

    # ------------------------------------------------------------------
    # Invoke / Run
    # ------------------------------------------------------------------

    async def invoke(self, operation: str, input: Any = None) -> AsyncJob:
        """Invoke an operation, returning an AsyncJob for tracking.

        Args:
            operation: Operation identifier — accepts a hex asset ID,
                an operation name (e.g. ``"test:echo"``), or a DID URL.
            input: Input parameters for the operation.
        """
        job_data = await self._client.invoke(operation, input)
        return AsyncJob(data=job_data, venue=self)

    async def run(
        self,
        operation: str,
        input: Any = None,
        *,
        timeout: float | None = None,
    ) -> Any:
        """Invoke an operation and wait for the result.

        Args:
            operation: Operation identifier — accepts a hex asset ID,
                an operation name (e.g. ``"test:echo"``), or a DID URL.
            input: Input parameters for the operation.
            timeout: Maximum seconds to wait for completion.
        """
        job = await self.invoke(operation, input)
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
