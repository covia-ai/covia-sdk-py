"""Asset — a universal data asset on the Covia grid.

Mirrors ``covia.grid.Asset`` from the Java SDK.

The data and identity of an asset (metadata accessors, content-address
computation, equality) are shared between the sync :class:`Asset` and the
async :class:`covia.async_api.asset.AsyncAsset` via :class:`_AssetBase`; the
subclasses add the I/O methods (content, invoke, run) with their respective
sync/async call contracts.
"""

from __future__ import annotations

import hashlib
import re
import warnings
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from covia.did import Namespace, asset_hash, did_url

if TYPE_CHECKING:
    from covia.job import Job
    from covia.venue import Venue  # noqa: F401 — resolves the _AssetBase["Venue"] base

# Venue type the asset is bound to. Generic only so each subclass can type its
# ``_venue`` (and the venue-touching helpers) precisely under strict mypy — the
# public Asset / AsyncAsset classes are fully specialised, so callers never see
# the type variable.
_VenueT = TypeVar("_VenueT")


class _AssetBase(Generic[_VenueT]):
    """Shared metadata, identity, and equality for sync and async assets.

    Holds everything that does not touch the network. The sync/async
    subclasses add the I/O methods.
    """

    def __init__(
        self,
        metadata: dict[str, Any],
        *,
        id: str | None = None,
        venue: _VenueT | None = None,
        metadata_raw: str | None = None,
    ) -> None:
        self._id = id
        self._metadata = metadata
        self._venue: _VenueT | None = venue
        self._metadata_raw = metadata_raw

    @staticmethod
    def compute_id(metadata_raw: str) -> str:
        """Deprecated legacy JSON digest; this is NOT a Covia CAD3 asset ID.

        Use the ID returned by venue registration or retrieval instead.
        """
        warnings.warn("compute_id returns a legacy digest, not a CAD3 asset ID", DeprecationWarning, stacklevel=2)
        return hashlib.sha256(metadata_raw.encode("utf-8")).hexdigest()

    @property
    def id(self) -> str | None:
        """The venue-provided CAD3 asset ID, or ``None`` before registration.

        Raw JSON text alone cannot supply a CAD3 value hash.
        """
        return self._id

    @property
    def metadata(self) -> dict[str, Any]:
        """The full metadata dictionary."""
        return self._metadata

    @property
    def metadata_raw(self) -> str | None:
        """The raw UTF-8 JSON string of the metadata as returned by the server.

        Preserved for inspection; JSON formatting does not determine the
        asset's CAD3 identity.
        Returns ``None`` if the asset was constructed without raw metadata
        (e.g. created locally rather than fetched from a venue).
        """
        return self._metadata_raw

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
    def venue(self) -> _VenueT | None:
        """The venue this asset belongs to, or ``None``."""
        return self._venue

    def _require_registered(self, action: str) -> tuple[_VenueT, str]:
        """Return ``(venue, id)`` or raise if either is missing.

        *action* names the attempted operation for the error message
        (e.g. ``"get content"`` → ``"Cannot get content: ..."``).
        """
        if self._venue is None:
            raise ValueError(f"Cannot {action}: asset has no attached venue")
        if self._id is None:
            raise ValueError(f"Cannot {action}: asset has no ID (not yet registered)")
        return self._venue, self._id

    # ------------------------------------------------------------------
    # Dunder methods
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        if self.name:
            label = self.name
        elif self._id is not None:
            label = self._id[:16]
        else:
            label = "unregistered"
        return f"{type(self).__name__}({label!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _AssetBase):
            if self._id is None or other._id is None:
                return self is other
            return self._id == other._id
        return NotImplemented

    def __hash__(self) -> int:
        if self._id is None:
            return id(self)
        return hash(self._id)


class Asset(_AssetBase["Venue"]):
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

    @property
    def did_url(self) -> str | None:
        """DID URL for this asset, or ``None`` if no venue is attached or no ID assigned."""
        if self._id is None or self._venue is None:
            return None
        venue_did = self._venue.did
        if venue_did is None:
            return None
        return did_url(venue_did, Namespace.ASSET, self._id)

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------

    def get_content(self) -> bytes:
        """Download the binary content of this asset.

        Raises:
            ValueError: If no venue is attached or no ID assigned.
        """
        venue, asset_id = self._require_registered("get content")
        return venue.get_asset_content(asset_id)

    def put_content(self, content: bytes) -> str:
        """Upload content for this asset.

        Args:
            content: Binary content to upload.

        Returns:
            Content hash string.

        Raises:
            ValueError: If no venue is attached or no ID assigned.
        """
        venue, asset_id = self._require_registered("put content")
        return venue.put_asset_content(asset_id, content)

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
            ValueError: If no venue is attached or no ID assigned.
        """
        venue, asset_id = self._require_registered("invoke")
        return venue.invoke(asset_id, input)

    def run(self, input: Any = None, *, timeout: float | None = None) -> Any:
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
        return venue.run(asset_id, input, timeout=timeout)


def resolve_asset_id(ref: str, etag: str | None) -> str:
    """Use the venue's canonical CAD3 ETag, checking reference consistency.

    This trusts the venue's response, not a local verification of CAD3 bytes.
    Older responses without an ETag retain their requested hash or path.
    """
    expected = asset_hash(ref)
    if expected is not None:
        expected = expected.removeprefix("0x").lower()
    if etag is None:
        return expected or ref
    match = re.fullmatch(r'"(?:0x)?([0-9a-fA-F]{64})"', etag)
    if match is None:
        raise ValueError("Invalid CAD3 asset ETag")
    resolved = match.group(1).lower()
    if expected is not None and expected != resolved:
        raise ValueError(f"Asset ID mismatch: requested {ref!r} but venue returned {resolved!r}")
    return resolved
