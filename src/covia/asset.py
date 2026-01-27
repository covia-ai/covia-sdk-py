"""Asset — a universal data asset on the Covia grid.

Mirrors ``covia.grid.Asset`` from the Java SDK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from covia.job import Job
    from covia.venue import Venue


class Asset:
    """A Covia asset — an immutable, content-addressed data object.

    Assets can represent data (with downloadable content) or operations
    (invocable via :meth:`invoke` / :meth:`run`).

    Example::

        asset = venue.get_asset("abc123...")
        print(asset.name)
        print(asset.metadata)

        # If the asset is an operation
        if asset.is_operation:
            result = asset.run({"prompt": "hello"})

        # Download content
        data = asset.get_content()
    """

    def __init__(
        self,
        id: str,
        metadata: dict[str, Any],
        venue: Venue | None = None,
    ) -> None:
        self._id = id
        self._metadata = metadata
        self._venue = venue

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        """The asset identifier (SHA-256 hex hash of metadata)."""
        return self._id

    @property
    def metadata(self) -> dict[str, Any]:
        """The full metadata dictionary."""
        return self._metadata

    @property
    def name(self) -> str | None:
        """Asset name, if present in metadata."""
        return self._metadata.get("name")

    @property
    def description(self) -> str | None:
        """Asset description, if present in metadata."""
        return self._metadata.get("description")

    @property
    def content_type(self) -> str | None:
        """Content type (MIME), if present in metadata."""
        return self._metadata.get("content-type")

    @property
    def is_operation(self) -> bool:
        """Whether this asset is an invocable operation."""
        return "operation" in self._metadata

    @property
    def did_url(self) -> str | None:
        """DID URL for this asset, or ``None`` if no venue is attached."""
        if self._venue is None:
            return None
        venue_did = self._venue.did
        if venue_did is None:
            return None
        return f"{venue_did}/a/{self._id}"

    @property
    def venue(self) -> Venue | None:
        """The venue this asset belongs to."""
        return self._venue

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------

    def get_content(self) -> bytes:
        """Download the binary content of this asset.

        Raises:
            ValueError: If no venue is attached.
        """
        if self._venue is None:
            raise ValueError("Cannot get content: asset has no attached venue")
        return self._venue.get_asset_content(self._id)

    def put_content(self, content: bytes) -> str:
        """Upload content for this asset.

        Args:
            content: Binary content to upload.

        Returns:
            Content hash string.

        Raises:
            ValueError: If no venue is attached.
        """
        if self._venue is None:
            raise ValueError("Cannot put content: asset has no attached venue")
        return self._venue.put_asset_content(self._id, content)

    # ------------------------------------------------------------------
    # Invocation
    # ------------------------------------------------------------------

    def invoke(self, input: Any = None) -> Job:
        """Invoke this asset as an operation.

        Args:
            input: Input parameters for the operation.

        Returns:
            A :class:`~covia.job.Job` for tracking the execution.

        Raises:
            ValueError: If no venue is attached or the asset is not an operation.
        """
        if self._venue is None:
            raise ValueError("Cannot invoke: asset has no attached venue")
        return self._venue.invoke(self._id, input)

    def run(self, input: Any = None, *, timeout: float | None = None) -> Any:
        """Invoke this asset and wait for the result.

        Args:
            input: Input parameters for the operation.
            timeout: Maximum seconds to wait for completion.

        Returns:
            The operation output.

        Raises:
            ValueError: If no venue is attached.
            JobFailedError: If the job finishes with a non-COMPLETE status.
            CoviaTimeoutError: If the timeout is exceeded.
        """
        if self._venue is None:
            raise ValueError("Cannot run: asset has no attached venue")
        return self._venue.run(self._id, input, timeout=timeout)

    # ------------------------------------------------------------------
    # Dunder methods
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        label = self.name or self._id[:16]
        return f"Asset({label!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Asset):
            return self._id == other._id
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._id)
