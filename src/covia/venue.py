"""Venue — a digital space on the Covia grid.

Mirrors ``covia.grid.Venue`` from the Java SDK.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

from covia._client import CoviaHTTPClient
from covia._sse import SSEEvent
from covia._transport import TransportConfig
from covia.agents import Agent, AgentManager
from covia.asset import Asset, resolve_asset_id
from covia.exceptions import CoviaError, CoviaTimeoutError
from covia.job import Job
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
from covia.secrets import SecretManager
from covia.ucan import UCANManager
from covia.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


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
        self._private = False
        self._config = config
        self._agents: AgentManager | None = None
        self._secrets: SecretManager | None = None
        self._workspace: WorkspaceManager | None = None
        self._ucan: UCANManager | None = None

    @property
    def agents(self) -> AgentManager:
        """Typed accessor for ``v/ops/agent/*`` operations."""
        if self._agents is None:
            self._agents = AgentManager(self)
        return self._agents

    def agent(self, agent_id: str) -> Agent:
        """A handle to a single agent, bound to *agent_id*.

        ``venue.agent("a").info()`` is equivalent to ``venue.agents.info("a")``
        but reads more naturally for repeated operations on one agent, and
        provides :meth:`~covia.agents.Agent.chat_session` for multi-turn chat.
        """
        return Agent(agent_id, self)

    @property
    def secrets(self) -> SecretManager:
        """Typed accessor for venue secret storage."""
        if self._secrets is None:
            self._secrets = SecretManager(self)
        return self._secrets

    @property
    def workspace(self) -> WorkspaceManager:
        """Typed accessor for ``v/ops/covia/*`` lattice operations.

        Name is provisional — the accessor spans all covia namespaces, not
        just ``/w/``, so it may later gain a ``values`` alias (see
        :class:`~covia.workspace.WorkspaceManager`).
        """
        if self._workspace is None:
            self._workspace = WorkspaceManager(self)
        return self._workspace

    @property
    def ucan(self) -> UCANManager:
        """Typed accessor for ``v/ops/ucan/*`` operations."""
        if self._ucan is None:
            self._ucan = UCANManager(self)
        return self._ucan

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

    def wait_until_ready(
        self,
        *,
        timeout: float | None = 60.0,
        poll_interval: float = 1.0,
    ) -> VenueStatus:
        """Block until the venue's API is ready to serve operations.

        A venue process accepts connections on its root path *before* its
        operation/invoke layer has finished initialising, so polling
        :meth:`status` (``GET /api/v1/status``) — not the root URL — is the
        reliable readiness signal. Invoking operations before the venue is
        ready otherwise races and fails on a cold start.

        The venue is considered ready as soon as :meth:`status` returns
        successfully and reports either no explicit ``status`` field or
        ``"OK"``. Connection, HTTP, and per-request timeout errors are
        treated as "not ready yet" and retried until *timeout* elapses.

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
                status = self.status()
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
            time.sleep(poll_interval)

    @property
    def url(self) -> str:
        """The base URL of this venue."""
        return self._config.base_url

    @property
    def did(self) -> str | None:
        """The DID of this venue, if resolvable.

        Resolved once (from ``GET /api/v1/status``, falling back to the venue's
        DID document) and cached on the transport — the same source the
        audience-bound auth uses, so identity and ``aud`` never disagree.
        """
        return self._client.venue_did()

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

    def get_asset(self, ref: str) -> Asset:
        """Get an asset by lattice address.

        *ref* may be a content hash (``<hash>``, ``a/<hash>``,
        ``<DID>/a/<hash>``) or a mutable lattice path the venue resolves to an
        asset (``w/my-assets/foo``, ``o/my-op``, ``<DID>/w/...``). Build
        addresses with :func:`covia.did.did_url`. Cross-DID reads are
        capability-gated — present a UCAN bearer (auth) for another DID's
        namespace.

        For a content-addressed *ref* the returned metadata is verified against
        the hash; for a mutable path the venue's resolution is trusted and the
        asset's id is the canonical hash it resolved to.

        Raises:
            ValueError: If a content-addressed *ref*'s hash does not match the
                returned metadata.
            AssetNotFoundError: If nothing resolves at *ref*.
        """
        metadata, metadata_raw = self._client.get_asset_metadata(ref)
        return Asset(
            metadata=metadata,
            id=resolve_asset_id(ref, metadata_raw),
            venue=self,
            metadata_raw=metadata_raw,
        )

    def register(self, asset: Asset | dict[str, Any]) -> Asset:
        """Register a new asset at this venue.

        Args:
            asset: An :class:`Asset` instance or a metadata dictionary.

        Returns:
            A registered :class:`Asset` with the server-assigned ID
            and this venue attached.
        """
        metadata = asset.metadata if isinstance(asset, Asset) else asset
        asset_id = self._client.register_asset(metadata)
        return self.get_asset(asset_id)

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

    def pin_asset(self, path: str) -> AssetPinResult:
        """Pin a resolvable value into the content-addressed asset store.

        Idempotent — the same value always yields the same hash. *path* may
        be a hex hash, ``/a/<hash>``, ``/o/<name>``, a DID URL, or a
        workspace path.

        Args:
            path: Source address to pin.

        Returns:
            The caller's asset DID URL and the bare content hash.
        """
        return AssetPinResult.model_validate(self.run("v/ops/asset/pin", {"path": path}))

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def list_operations(self) -> list[OperationInfo]:
        """List all named operations available on this venue."""
        return self._client.list_operations()

    def get_operation(self, name: str) -> OperationInfo:
        """Get details of a named operation.

        Args:
            name: Operation name (e.g. ``"v/ops/schema/infer"``).
        """
        return self._client.get_operation(name)

    # ------------------------------------------------------------------
    # Invoke / Run
    # ------------------------------------------------------------------

    def set_private(self, enabled: bool) -> None:
        """Put this connection in **private-jobs mode** (covia #192): every
        subsequent :meth:`run` executes as a memory-only job — never persisted
        to the venue's job index, no durable record, gone on venue restart.
        Requires ``enablePrivateJobs`` on the venue.

        Because a completed private job is immediately forgotten, results are
        collected through the invoke ``wait`` window rather than polling — so
        private mode works with :meth:`run`; a poll-style :meth:`invoke`
        raises.
        """
        self._private = enabled

    def invoke(self, operation: str, input: Any = None, *, ucans: list[str] | None = None) -> Job:
        """Invoke an operation, returning a Job for tracking.

        The operation starts asynchronously on the venue. Use
        :meth:`job.wait() <covia.job.Job.wait>` to block until completion.

        Args:
            operation: Operation identifier — accepts a hex asset ID
                (e.g. ``"b8fc54e7..."``), an operation name
                (e.g. ``"v/ops/schema/infer"``), or a DID URL
                (e.g. ``"did:key:z6Mk.../a/b8fc54e7..."``).
            input: Input parameters for the operation.
            ucans: Optional UCAN proof tokens authorising
                capability-gated operations (e.g. cross-DID reads,
                ``secret:extract``). The venue verifies each proof
                against the caller's DID and the operation's path.

        Returns:
            A :class:`~covia.job.Job` instance for tracking execution.
        """
        if self._private:
            raise CoviaError(
                "Private-jobs mode requires run(): a completed private job is "
                "immediately forgotten by the venue, so a poll-style Job cannot "
                "collect its result."
            )
        job_data = self._client.invoke(operation, input, ucans=ucans)
        return Job(data=job_data, venue=self)

    def run(
        self,
        operation: str,
        input: Any = None,
        *,
        timeout: float | None = None,
        ucans: list[str] | None = None,
    ) -> Any:
        """Invoke an operation and block until the result is available.

        Convenience method combining :meth:`invoke`, :meth:`~covia.job.Job.wait`,
        and :attr:`~covia.job.Job.output`.

        Args:
            operation: Operation identifier — accepts a hex asset ID,
                an operation name (e.g. ``"v/ops/schema/infer"``), or a DID URL.
            input: Input parameters for the operation.
            timeout: Maximum seconds to wait for completion.
            ucans: Optional UCAN proof tokens (see :meth:`invoke`).

        Returns:
            The operation output.

        Raises:
            JobFailedError: If the job finishes with a non-COMPLETE status.
            CoviaTimeoutError: If the timeout is exceeded.
        """
        if self._private:
            # Memory-only job (covia #192): the result is collected through the
            # invoke wait window — a completed private job is immediately
            # forgotten, so polling cannot be used.
            wait: bool | int = int(timeout * 1000) if timeout else True
            job_data = self._client.invoke(operation, input, ucans=ucans, private=True, wait=wait)
            job = Job(data=job_data, venue=self)
            if job.is_finished:
                return job.output
            raise CoviaTimeoutError(
                f"Private job {job_data.id} did not finish within the wait window; "
                "its result cannot be collected by polling (private jobs are "
                "forgotten on completion). Use a longer timeout or a non-private run."
            )
        job = self.invoke(operation, input, ucans=ucans)
        job.wait(timeout=timeout)
        return job.output

    def _get_agents(self, suffix: str, params: dict[str, Any]) -> dict[str, Any]:
        """Internal: ``GET /api/v1/agents{suffix}`` — the job-free agent read
        transport (covia #180) behind :attr:`agents`' ``list``/``info``."""
        return self._client.get_agents(suffix, params)

    def _get_value(self, op: str, params: dict[str, Any]) -> dict[str, Any]:
        """Internal: ``GET /api/v1/values/{op}`` — the job-free read transport
        (covia #177) behind :attr:`workspace`'s ``read``/``list``/``slice``/
        ``inspect``/``count``/``aggregate``. Creates no Job.

        Not public API: it dispatches on a stringly-typed *op*. Use the typed
        ``venue.workspace.*`` methods instead.
        """
        return self._client.get_value(op, params)

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

    def pause_job(self, job_id: str) -> JobData:
        """Pause a running job.

        Args:
            job_id: Job identifier.
        """
        return self._client.pause_job(job_id)

    def resume_job(self, job_id: str) -> JobData:
        """Resume a paused job.

        Args:
            job_id: Job identifier.
        """
        return self._client.resume_job(job_id)

    def send_job_message(self, job_id: str, message: Any) -> dict[str, Any]:
        """Deliver a message to a running job (e.g. an interactive/paused job).

        Args:
            job_id: Job identifier.
            message: Message payload. A non-object value is wrapped by the
                venue as ``{"content": message}``.

        Returns:
            The venue's queue acknowledgement (``{"status", "queueDepth"}``).
        """
        return self._client.send_job_message(job_id, message)

    def stream_job_events(self, job_id: str) -> Iterator[SSEEvent]:
        """Stream SSE events for a job.

        Args:
            job_id: Job identifier.

        Yields:
            :class:`~covia._sse.SSEEvent` instances.
        """
        return self._client.stream_job_events(job_id)

    # ------------------------------------------------------------------
    # Secrets (raw REST — see ``venue.secrets`` for the typed manager)
    # ------------------------------------------------------------------

    def list_secrets(self) -> list[str]:
        """List secret names stored at this venue."""
        return self._client.list_secrets()

    def delete_secret(self, name: str) -> None:
        """Delete a stored secret."""
        self._client.delete_secret(name)

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
