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
from covia.agents import AsyncAgent, AsyncAgentManager
from covia.asset import resolve_asset_id
from covia.async_api.asset import AsyncAsset
from covia.async_api.job import AsyncJob
from covia.exceptions import CoviaError, CoviaTimeoutError
from covia.models import (
    AgentCard,
    AssetList,
    AssetPinResult,
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
        self._private = False
        self._config = config
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

    def agent(self, agent_id: str) -> AsyncAgent:
        """A handle to a single agent, bound to *agent_id* (async mirror of
        :meth:`Venue.agent <covia.venue.Venue.agent>`)."""
        return AsyncAgent(agent_id, self)

    @property
    def secrets(self) -> AsyncSecretManager:
        """Typed accessor for venue secret storage."""
        if self._secrets is None:
            self._secrets = AsyncSecretManager(self)
        return self._secrets

    @property
    def workspace(self) -> AsyncWorkspaceManager:
        """Typed accessor for ``v/ops/covia/*`` lattice operations.

        Name is provisional — see
        :attr:`Venue.workspace <covia.venue.Venue.workspace>`.
        """
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
        """The DID of this venue, if resolvable.

        Resolved once (from ``GET /api/v1/status``, falling back to the venue's
        DID document) and cached on the transport — the same source the
        audience-bound auth uses, so identity and ``aud`` never disagree.
        """
        return await self._client.venue_did()

    async def did_document(self) -> DIDDocument:
        """Get the full DID document for this venue."""
        return await self._client.get_did_document()

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    async def list_assets(self, *, offset: int = 0, limit: int | None = None) -> AssetList:
        """List assets registered at this venue."""
        return await self._client.list_assets(offset=offset, limit=limit)

    async def get_asset(self, ref: str) -> AsyncAsset:
        """Get an asset by lattice address.

        Async mirror of :meth:`Venue.get_asset <covia.venue.Venue.get_asset>` —
        *ref* may be a content hash (``<hash>``, ``a/<hash>``,
        ``<DID>/a/<hash>``) or a mutable lattice path the venue resolves
        (``w/my-assets/foo``, ``o/my-op``, ``<DID>/w/...``).

        Raises:
            ValueError: If a content-addressed *ref*'s hash does not match the
                returned metadata.
            AssetNotFoundError: If nothing resolves at *ref*.
        """
        metadata, metadata_raw = await self._client.get_asset_metadata(ref)
        return AsyncAsset(
            metadata=metadata,
            id=resolve_asset_id(ref, metadata_raw),
            venue=self,
            metadata_raw=metadata_raw,
        )

    async def register(self, asset: AsyncAsset | dict[str, Any]) -> AsyncAsset:
        """Register a new asset at this venue.

        Args:
            asset: An :class:`AsyncAsset` instance or a metadata dictionary.

        Returns:
            A registered :class:`AsyncAsset` with the server-assigned ID
            and this venue attached.
        """
        metadata = asset.metadata if isinstance(asset, AsyncAsset) else asset
        asset_id = await self._client.register_asset(metadata)
        return await self.get_asset(asset_id)

    async def get_asset_content(self, asset_id: str) -> bytes:
        """Download the binary content of an asset."""
        return await self._client.get_asset_content(asset_id)

    async def put_asset_content(self, asset_id: str, content: bytes) -> str:
        """Upload content for an asset. Returns the content hash."""
        return await self._client.put_asset_content(asset_id, content)

    async def pin_asset(self, path: str) -> AssetPinResult:
        """Pin a resolvable value into the content-addressed asset store.

        Idempotent — the same value always yields the same hash. *path* may
        be a hex hash, ``/a/<hash>``, ``/o/<name>``, a DID URL, or a
        workspace path. Returns the caller's asset DID URL and content hash.
        """
        return AssetPinResult.model_validate(await self.run("v/ops/asset/pin", {"path": path}))

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

    def set_private(self, enabled: bool) -> None:
        """Put this connection in **private-jobs mode** (covia #192): every
        subsequent :meth:`run` executes as a memory-only job — never persisted
        to the venue's job index, no durable record, gone on venue restart.
        Requires ``enablePrivateJobs`` on the venue.

        Prefer the per-call ``private=True`` argument to :meth:`run` when only
        selected operations should be private. A poll-style :meth:`invoke`
        raises while connection-wide private mode is enabled.
        """
        self._private = enabled

    async def invoke(self, operation: str, input: Any = None, *, ucans: list[str] | None = None) -> AsyncJob:
        """Invoke an operation, returning an AsyncJob for tracking.

        Args:
            operation: Operation identifier — accepts a hex asset ID,
                an operation name (e.g. ``"v/ops/schema/infer"``), or a DID URL.
            input: Input parameters for the operation.
            ucans: Optional UCAN proof tokens authorising
                capability-gated operations (e.g. cross-DID reads).
        """
        if self._private:
            raise CoviaError(
                "Private-jobs mode requires run(): a completed private job is "
                "immediately forgotten by the venue, so a poll-style Job cannot "
                "collect its result."
            )
        job_data = await self._client.invoke(operation, input, ucans=ucans)
        return AsyncJob(data=job_data, venue=self)

    async def run(
        self,
        operation: str,
        input: Any = None,
        *,
        timeout: float | None = None,
        ucans: list[str] | None = None,
        private: bool | None = None,
    ) -> Any:
        """Run an operation and return its result directly via ``/api/v1/run``.

        Args:
            operation: Operation identifier — accepts a hex asset ID,
                an operation name (e.g. ``"v/ops/schema/infer"``), or a DID URL.
            input: Input parameters for the operation.
            timeout: HTTP request timeout in seconds. ``None`` uses the
                connection default.
            ucans: Optional UCAN proof tokens (see :meth:`invoke`).
            private: Execute as a memory-only job. ``None`` uses the
                connection-wide setting from :meth:`set_private`.
        """
        effective_private = self._private if private is None else private
        return await self._client.run(operation, input, ucans=ucans, private=effective_private, timeout=timeout)

    async def _get_agents(self, suffix: str, params: dict[str, Any]) -> dict[str, Any]:
        """Internal: ``GET /api/v1/agents{suffix}`` — the job-free agent read
        transport (covia #180) behind :attr:`agents`' ``list``/``info``."""
        return await self._client.get_agents(suffix, params)

    async def _get_value(self, op: str, params: dict[str, Any]) -> dict[str, Any]:
        """Internal job-free read transport — see
        :meth:`Venue._get_value <covia.venue.Venue._get_value>`."""
        return await self._client.get_value(op, params)

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

    async def cancel_job(self, job_id: str, reason: str | None = None) -> JobData:
        """Cancel a running job, optionally recording a reason."""
        return await self._client.cancel_job(job_id, reason=reason)

    async def delete_job(self, job_id: str) -> None:
        """Delete a job record."""
        await self._client.delete_job(job_id)

    async def pause_job(self, job_id: str) -> JobData:
        """Pause a running job."""
        return await self._client.pause_job(job_id)

    async def resume_job(self, job_id: str) -> JobData:
        """Resume a paused job."""
        return await self._client.resume_job(job_id)

    async def send_job_message(self, job_id: str, message: Any) -> dict[str, Any]:
        """Deliver a message to a running job.

        Returns the venue's queue acknowledgement (``{"status", "queueDepth"}``).
        A non-object *message* is wrapped by the venue as ``{"content": message}``.
        """
        return await self._client.send_job_message(job_id, message)

    def stream_job_events(self, job_id: str) -> AsyncIterator[SSEEvent]:
        """Stream SSE events for a job.

        Returns the async iterator directly (not a coroutine) — iterate it with
        ``async for``, mirroring the sync :meth:`Venue.stream_job_events`.
        """
        return self._client.stream_job_events(job_id)

    # ------------------------------------------------------------------
    # Secrets (raw REST — see ``venue.secrets`` for the typed manager)
    # ------------------------------------------------------------------

    async def list_secrets(self) -> list[str]:
        """List secret names stored at this venue."""
        return await self._client.list_secrets()

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
