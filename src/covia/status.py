"""Job status constants for the Covia grid.

Mirrors ``covia.grid.Status`` from the Java SDK.
"""

from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    """Status of a Covia job throughout its lifecycle."""

    PENDING = "PENDING"
    STARTED = "STARTED"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"
    INPUT_REQUIRED = "INPUT_REQUIRED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    PAUSED = "PAUSED"

    @property
    def is_finished(self) -> bool:
        """Whether the job has reached a terminal state."""
        return self in _FINISHED_STATUSES

    @property
    def is_paused(self) -> bool:
        """Whether the job is waiting for external input."""
        return self in _PAUSED_STATUSES


_FINISHED_STATUSES = frozenset({
    JobStatus.COMPLETE,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
    JobStatus.REJECTED,
    JobStatus.TIMEOUT,
})

_PAUSED_STATUSES = frozenset({
    JobStatus.PAUSED,
    JobStatus.INPUT_REQUIRED,
    JobStatus.AUTH_REQUIRED,
})
