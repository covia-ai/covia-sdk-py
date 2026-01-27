"""Venue — a digital space on the Covia grid.

Mirrors ``covia.grid.Venue`` from the Java SDK.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from covia._client import CoviaHTTPClient
from covia._sse import SSEEvent
from covia._transport import TransportConfig
from covia.asset import Asset
from covia.job import Job
from covia.models import (
    AgentCard,
    AssetList,
    DIDDocument,
    JobData,
    MCPDiscovery,
    OperationInfo,
    VenueStatus,
)


class Venue:
    """A Covia venue for managing assets, invoking operations, and tracking jobs.

    This is the primary class that SDK users interact with. Obtain an instance
    via :meth:`Grid.connect() <covia.grid.Grid.connect>`.

    Example::

        from covia import Grid

        with Grid.connect("https://venue.covia.ai") as venue:
            status = venue.status()
            result = venue.run("my-operation", {"prompt": "hello"})
    """

    def __init__(self, config: TransportConfig) -> None:
        self._client = CoviaHTTPClient(config)
        self._config = config

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> Venue:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Venue info
    # ------------------------------------------------------------------

    def status(self) -> VenueStatus:
        """Get venue status information."""
        return self._client.get_status()

    @property
    def url(self) -> str:
        """The base URL of this venue."""
        return self._config.base_url

    @property
    def did(self) -> str | None:
        """The DID of this venue, if available."""
        doc = self._client.get_did_document()
        return doc.id

    def did_document(self) -> DIDDocument:
        """Get the full DID document for this venue."""
        return self._client.get_did_document()

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    def list_assets(self, *, offset: int = 0, limit: int | None = None) -> AssetList:
        """List assets registered at this venue.

        Args:
            offset: Pagination offset.
            limit: Maximum number of assets to return.
        """
        return self._client.list_assets(offset=offset, limit=limit)

    def get_asset(self, asset_id: str) -> Asset:
        """Get an asset by its ID.

        Args:
            asset_id: Hex asset identifier.
        """
        metadata = self._client.get_asset_metadata(asset_id)
        return Asset(id=asset_id, metadata=metadata, venue=self)

    def register_asset(self, metadata: dict[str, Any]) -> str:
        """Register a new asset at this venue.

        Args:
            metadata: Asset metadata dictionary.

        Returns:
            The new asset ID (hex string).
        """
        return self._client.register_asset(metadata)

    def get_asset_content(self, asset_id: str) -> bytes:
        """Download the binary content of an asset.

        Args:
            asset_id: Hex asset identifier.
        """
        return self._client.get_asset_content(asset_id)

    def put_asset_content(self, asset_id: str, content: bytes) -> str:
        """Upload content for an asset.

        Args:
            asset_id: Hex asset identifier.
            content: Binary content to upload.

        Returns:
            Content hash string.
        """
        return self._client.put_asset_content(asset_id, content)

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def list_operations(self) -> list[OperationInfo]:
        """List all named operations available on this venue."""
        return self._client.list_operations()

    def get_operation(self, name: str) -> OperationInfo:
        """Get details of a named operation.

        Args:
            name: Operation name (e.g. ``"test:echo"``).
        """
        return self._client.get_operation(name)

    # ------------------------------------------------------------------
    # Invoke / Run
    # ------------------------------------------------------------------

    def invoke(self, operation: str, input: Any = None) -> Job:
        """Invoke an operation, returning a Job for tracking.

        The operation starts asynchronously on the venue. Use
        :meth:`job.wait() <covia.job.Job.wait>` to block until completion.

        Args:
            operation: Operation identifier — accepts a hex asset ID
                (e.g. ``"b8fc54e7..."``), an operation name
                (e.g. ``"test:echo"``), or a DID URL
                (e.g. ``"did:key:z6Mk.../a/b8fc54e7..."``).
            input: Input parameters for the operation.

        Returns:
            A :class:`~covia.job.Job` instance for tracking execution.
        """
        job_data = self._client.invoke(operation, input)
        return Job(data=job_data, venue=self)

    def run(
        self,
        operation: str,
        input: Any = None,
        *,
        timeout: float | None = None,
    ) -> Any:
        """Invoke an operation and block until the result is available.

        Convenience method combining :meth:`invoke`, :meth:`~covia.job.Job.wait`,
        and :attr:`~covia.job.Job.output`.

        Args:
            operation: Operation identifier — accepts a hex asset ID,
                an operation name (e.g. ``"test:echo"``), or a DID URL.
            input: Input parameters for the operation.
            timeout: Maximum seconds to wait for completion.

        Returns:
            The operation output.

        Raises:
            JobFailedError: If the job finishes with a non-COMPLETE status.
            CoviaTimeoutError: If the timeout is exceeded.
        """
        job = self.invoke(operation, input)
        job.wait(timeout=timeout)
        return job.output

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    def get_job(self, job_id: str) -> Job:
        """Get a job by its ID.

        Args:
            job_id: Job identifier.
        """
        job_data = self._client.get_job(job_id)
        return Job(data=job_data, venue=self)

    def list_jobs(self) -> list[str]:
        """List all job IDs at this venue."""
        return self._client.list_jobs()

    def cancel_job(self, job_id: str) -> JobData:
        """Cancel a running job.

        Args:
            job_id: Job identifier.
        """
        return self._client.cancel_job(job_id)

    def delete_job(self, job_id: str) -> None:
        """Delete a job record.

        Args:
            job_id: Job identifier.
        """
        self._client.delete_job(job_id)

    def stream_job_events(self, job_id: str) -> Iterator[SSEEvent]:
        """Stream SSE events for a job.

        Args:
            job_id: Job identifier.

        Yields:
            :class:`~covia._sse.SSEEvent` instances.
        """
        return self._client.stream_job_events(job_id)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def mcp_discovery(self) -> MCPDiscovery:
        """Get MCP (Model Context Protocol) discovery information."""
        return self._client.get_mcp_discovery()

    def agent_card(self) -> AgentCard:
        """Get the A2A (Agent-to-Agent) agent card."""
        return self._client.get_agent_card()

    def __repr__(self) -> str:
        return f"Venue({self._config.base_url!r})"
