"""Exception hierarchy for the Covia SDK."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from covia.models import JobData


class CoviaError(Exception):
    """Base exception for all Covia SDK errors."""


class GridError(CoviaError):
    """Raised when the Covia API returns an error response (4xx/5xx)."""

    def __init__(
        self,
        status_code: int,
        message: str,
        response_body: Any = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.response_body = response_body
        super().__init__(f"HTTP {status_code}: {message}")


class CoviaConnectionError(CoviaError, ConnectionError):
    """Raised when the SDK cannot connect to the venue.

    Subclasses both :class:`CoviaError` and Python's built-in
    :class:`ConnectionError`, so it can be caught with either.
    """


class CoviaTimeoutError(CoviaError, TimeoutError):
    """Raised when an operation or polling loop times out.

    Subclasses both :class:`CoviaError` and Python's built-in
    :class:`TimeoutError`, so it can be caught with either.
    """


class JobFailedError(CoviaError):
    """Raised when a job finishes with a non-COMPLETE status."""

    def __init__(self, job_data: JobData) -> None:
        self.job_data = job_data
        msg = f"Job {job_data.id} {job_data.status}"
        if job_data.error:
            msg += f": {job_data.error}"
        super().__init__(msg)


class NotFoundError(GridError):
    """Raised when a requested resource is not found (404).

    Base class for :class:`AssetNotFoundError` and :class:`JobNotFoundError`.
    Catch this to handle any 404 uniformly.
    """

    def __init__(self, message: str) -> None:
        super().__init__(404, message)


class AssetNotFoundError(NotFoundError):
    """Raised when an asset is not found (404)."""

    def __init__(self, asset_id: str) -> None:
        self.asset_id = asset_id
        super().__init__(f"Asset not found: {asset_id}")


class JobNotFoundError(NotFoundError):
    """Raised when a job is not found (404)."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(f"Job not found: {job_id}")
