"""AsyncJob — async interface for tracking Covia job execution."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from covia._sse import SSEEvent
from covia.exceptions import CoviaTimeoutError, JobFailedError
from covia.models import JobData
from covia.status import JobStatus

if TYPE_CHECKING:
    from covia.async_api.venue import AsyncVenue

logger = logging.getLogger(__name__)

# Polling backoff constants (matching Java VenueHTTP)
_INITIAL_POLL_DELAY = 0.3  # seconds
_BACKOFF_FACTOR = 1.5
_MAX_POLL_DELAY = 10.0


class AsyncJob:
    """Async version of :class:`~covia.job.Job`.

    Example::

        job = await venue.invoke("my-operation", {"prompt": "hello"})
        await job.wait(timeout=60)
        print(job.output)

        # Or use result() as a shorthand
        output = await (await venue.invoke("my-op", {"x": 1})).result(timeout=30)
    """

    def __init__(self, data: JobData, venue: AsyncVenue) -> None:
        self._data = data
        self._venue = venue

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str | None:
        """The job identifier."""
        return self._data.id

    @property
    def status(self) -> JobStatus:
        """Current status of the job."""
        return self._data.status

    @property
    def is_finished(self) -> bool:
        """Whether the job has reached a terminal state."""
        return self._data.status.is_finished

    @property
    def is_complete(self) -> bool:
        """Whether the job completed successfully."""
        return self._data.status == JobStatus.COMPLETE

    @property
    def is_paused(self) -> bool:
        """Whether the job is waiting for external input."""
        return self._data.status.is_paused

    @property
    def needs_input(self) -> bool:
        """Whether the job is paused awaiting caller input (``INPUT_REQUIRED``)."""
        return self._data.status == JobStatus.INPUT_REQUIRED

    @property
    def needs_auth(self) -> bool:
        """Whether the job is paused awaiting authentication (``AUTH_REQUIRED``)."""
        return self._data.status == JobStatus.AUTH_REQUIRED

    @property
    def output(self) -> Any:
        """The job output.

        Raises:
            ValueError: If the job has not finished yet.
            JobFailedError: If the job finished with a non-COMPLETE status.
        """
        if not self.is_finished:
            raise ValueError(f"Job is not finished (status: {self.status})")
        if not self.is_complete:
            raise JobFailedError(self._data)
        return self._data.output

    @property
    def error(self) -> str | None:
        """Error message if the job failed."""
        return self._data.error

    @property
    def data(self) -> JobData:
        """The full job data model."""
        return self._data

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def refresh(self) -> None:
        """Poll the venue for the latest job status."""
        if self.id is None:
            raise ValueError("Cannot refresh a job with no ID")
        self._data = await self._venue._client.get_job(self.id)

    async def wait(self, *, timeout: float | None = None) -> None:
        """Wait until the job reaches a terminal state.

        Uses exponential backoff polling (initial 300ms, factor 1.5, max 10s).

        Args:
            timeout: Maximum seconds to wait. ``None`` waits indefinitely.

        Raises:
            CoviaTimeoutError: If *timeout* is exceeded.
        """
        if self.is_finished:
            return

        delay = _INITIAL_POLL_DELAY
        start = time.monotonic()
        logger.debug("Polling job %s (status: %s)", self.id, self.status)

        while not self.is_finished:
            if timeout is not None and (time.monotonic() - start) > timeout:
                raise CoviaTimeoutError(f"Job {self.id} did not finish within {timeout}s")
            await asyncio.sleep(delay)
            await self.refresh()
            logger.debug("Job %s polled → %s (delay=%.1fs)", self.id, self.status, delay)
            delay = min(delay * _BACKOFF_FACTOR, _MAX_POLL_DELAY)

    async def cancel(self) -> None:
        """Cancel this job."""
        if self.id is None:
            raise ValueError("Cannot cancel a job with no ID")
        self._data = await self._venue.cancel_job(self.id)

    async def pause(self) -> None:
        """Pause this job, refreshing its local state."""
        if self.id is None:
            raise ValueError("Cannot pause a job with no ID")
        self._data = await self._venue.pause_job(self.id)

    async def resume(self) -> None:
        """Resume this paused job, refreshing its local state."""
        if self.id is None:
            raise ValueError("Cannot resume a job with no ID")
        self._data = await self._venue.resume_job(self.id)

    async def send_message(self, message: Any) -> dict[str, Any]:
        """Deliver a message to this running job.

        Useful for interactive jobs paused in ``INPUT_REQUIRED`` /
        ``AUTH_REQUIRED``. A non-object *message* is wrapped by the venue as
        ``{"content": message}``.

        Returns:
            The venue's queue acknowledgement (``{"status", "queueDepth"}``).
        """
        if self.id is None:
            raise ValueError("Cannot send a message to a job with no ID")
        return await self._venue.send_job_message(self.id, message)

    async def result(self, *, timeout: float | None = None) -> Any:
        """Wait for the job to complete and return its output.

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            The job output.

        Raises:
            JobFailedError: If the job finishes with a non-COMPLETE status.
            CoviaTimeoutError: If *timeout* is exceeded.
        """
        await self.wait(timeout=timeout)
        return self.output

    def stream(self) -> AsyncIterator[SSEEvent]:
        """Stream server-sent events for this job.

        Returns the async iterator directly — iterate it with ``async for``.
        """
        if self.id is None:
            raise ValueError("Cannot stream a job with no ID")
        return self._venue.stream_job_events(self.id)

    def __repr__(self) -> str:
        return f"AsyncJob(id={self.id!r}, status={self.status!r})"
